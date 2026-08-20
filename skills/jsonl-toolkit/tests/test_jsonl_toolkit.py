#!/usr/bin/env -S uv run
# /// script
# requires-python = "==3.12.*"
# dependencies = ["pyyaml", "pydantic"]
# ///

import doctest
import json
import pathlib
import re
import sys
import unittest

SCRIPTS = pathlib.Path(__file__).resolve().parents[1] / "scripts"
FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures"
sys.path.insert(0, str(SCRIPTS))

import analyze_transcript_json
import pi_session
import render_transcript_review


def holds_a_long_string(value: object) -> bool:
    """True when a string of at least PROSE_MIN characters sits anywhere inside."""
    if isinstance(value, str):
        return len(value) >= render_transcript_review.PROSE_MIN
    if isinstance(value, dict):
        return any(holds_a_long_string(nested) for nested in value.values())
    if isinstance(value, list):
        return any(holds_a_long_string(nested) for nested in value)
    return False


def message(index: int, role: str, content: list[object]) -> dict[str, object]:
    return {
        "type": "user-message" if role == "user" else "assistant-response",
        "role": role,
        "original_index": index,
        "content": content,
    }


class JsonlToolkitTests(unittest.TestCase):
    def test_analyzer_expands_multi_file_reads(self) -> None:
        transcript_message = analyze_transcript_json.Message(
            1,
            "assistant",
            "assistant-response",
            [{"type": "tool-input", "name": "read_many_files", "paths": ["a", "b"]}],
        )

        report = analyze_transcript_json.build_report([transcript_message], 8)

        self.assertEqual(
            report.get("files", {}).get("unique_files"),
            2,
            f"The analyzer did not count each multi-file read path: {report!r}",
        )

    def test_pi_active_path_excludes_abandoned_branches(self) -> None:
        entries = [
            {"type": "session", "id": "session"},
            {"type": "message", "id": "root", "parentId": None},
            {"type": "message", "id": "abandoned", "parentId": "root"},
            {"type": "message", "id": "leaf", "parentId": "root"},
        ]

        _, active = pi_session.extract_active_path(entries)

        self.assertEqual(
            [entry.get("id") for entry in active],
            ["root", "leaf"],
            f"The active path included an abandoned branch: {active!r}",
        )

    def test_review_pairs_tools_by_id_and_flags_orphans(self) -> None:
        source = [
            message(1, "assistant", [
                {"type": "tool-input", "name": "Bash", "id": "call-a", "command": "echo A"},
                {"type": "tool-input", "name": "Bash", "id": "input-only", "command": "echo orphan"},
            ]),
            message(2, "user", [{"type": "tool-output", "name": "Bash", "id": "call-a", "content": "A result"}]),
            message(3, "user", [{"type": "tool-output", "name": "Bash", "id": "output-only", "content": "stray"}]),
        ]

        rendered = render_transcript_review.render(source)

        for heading in (
            "### Tool event `call-a` — paired",
            "### Tool event `input-only` — unmatched input",
            "### Tool event `output-only` — unmatched output",
        ):
            self.assertIn(heading, rendered, f"The review omitted {heading!r}:\n{rendered}")
        self.assertEqual(rendered.count("A result"), 1, f"The paired result was duplicated:\n{rendered}")

    def test_review_elides_only_identical_skill_bodies(self) -> None:
        shared = '<skill name="demo">Shared rules</skill>'
        changed = '<skill name="demo">Changed rules</skill>'
        source = [
            message(10, "user", [shared + "\n\nfirst task"]),
            message(20, "user", [shared + "\n\nsecond task"]),
            message(30, "user", [changed + "\n\nthird task"]),
        ]

        rendered = render_transcript_review.render(source)

        self.assertEqual(rendered.count(shared), 1, f"The shared body was repeated:\n{rendered}")
        self.assertIn('<skill-body-elided duplicate-of="10"/>', rendered)
        self.assertIn(changed, rendered)
        for instruction in ("first task", "second task", "third task"):
            self.assertIn(instruction, rendered, f"The review lost {instruction!r}:\n{rendered}")

    def test_review_labels_native_compaction_as_a_boundary(self) -> None:
        source = [
            message(1, "assistant", ["Before"]),
            {"type": "compaction", "role": "user", "original_index": 2, "content": ["Summary"]},
            message(3, "assistant", ["After"]),
        ]

        rendered = render_transcript_review.render(source)

        self.assertIn("## Compaction boundary [i=2]", rendered)
        self.assertNotIn("## User [i=2]", rendered)


class AnnotateGateTests(unittest.TestCase):
    def test_gate_accepts_every_real_provider_export(self) -> None:
        for name in ("pi.json", "claude.json", "codex.json"):
            with self.subTest(fixture=name):
                raw = json.loads((FIXTURES / name).read_text(encoding="utf-8"))

                verdict = render_transcript_review.gate(raw)

                self.assertTrue(
                    verdict.ok,
                    f"The gate refused the real {name} export: {verdict.reason!r}",
                )

    def test_gate_refuses_a_malformed_known_block_instead_of_passing_it_through(self) -> None:
        transcript = [message(1, "assistant", [{"type": "tool-input", "id": "x"}])]

        verdict = render_transcript_review.gate(transcript)

        self.assertFalse(
            verdict.ok,
            "A nameless tool-input was absorbed by the opaque catch-all instead of refused",
        )
        self.assertIn(
            "name",
            verdict.reason,
            f"The refusal did not say which field was wrong: {verdict.reason!r}",
        )

    def test_gate_refuses_a_native_session_rather_than_rendering_it_empty(self) -> None:
        """Native Pi records conform to nothing this mode knows, so none of them fail.

        Conformance alone would therefore pass and emit an empty view. Only the
        coverage floor turns that into a refusal.
        """
        native_records = [
            {"type": "session", "id": "s", "cwd": "/x", "version": "1", "timestamp": "t"},
            {"type": "model_change", "id": "m", "parentId": "s", "modelId": "o", "provider": "p", "timestamp": "t"},
            {"type": "message", "id": "a", "parentId": "s", "message": {"role": "user"}, "timestamp": "t"},
        ]

        verdict = render_transcript_review.gate(native_records)

        self.assertFalse(
            verdict.ok,
            "A native session passed the gate and would have rendered as an empty view",
        )
        self.assertIn(
            "no messages",
            verdict.reason,
            f"The refusal blamed the wrong thing: {verdict.reason!r}",
        )

    def test_gate_tolerates_unknown_block_types_and_unknown_keys(self) -> None:
        transcript = [
            message(1, "assistant", [{"type": "thinking", "thought": "quiet"}]),
            {
                "type": "assistant-response",
                "role": "assistant",
                "original_index": 2,
                "content": [{"type": "tool-input", "name": "Future", "novel_key": 3}],
                "some_future_message_key": True,
            },
        ]

        verdict = render_transcript_review.gate(transcript)

        self.assertTrue(
            verdict.ok,
            f"The gate broke on additions it should pass through: {verdict.reason!r}",
        )


class AnnotateCoverageTests(unittest.TestCase):
    """No message that carries content may disappear from the annotated view."""

    def test_no_message_with_content_is_silently_dropped(self) -> None:
        transcript = [
            {"type": "user-message", "role": "user", "original_index": 1, "content": ["ask"]},
            {"type": "recap", "role": "assistant", "original_index": 51, "content": ["RECAP BODY"]},
            {"type": "agent", "role": "user", "original_index": 74, "agent_id": "a8b",
             "subagent_type": "fork", "content": ["AGENT BODY"]},
            {"type": "custom", "role": "custom", "original_index": 237,
             "custom_type": "pi-user-agents", "content": ["CUSTOM BODY"]},
            {"type": "session-rename", "role": "user", "original_index": 300, "content": ["RENAME BODY"]},
            {"type": "a-type-invented-after-this-code", "role": "user",
             "original_index": 400, "content": ["FUTURE BODY"]},
        ]

        verdict = render_transcript_review.gate(transcript)
        self.assertTrue(verdict.ok, f"A valid export was refused: {verdict.reason!r}")
        annotated = render_transcript_review.render_annotated(verdict.messages)

        for index, marker in (
            (51, "RECAP BODY"),
            (74, "AGENT BODY"),
            (237, "CUSTOM BODY"),
            (300, "RENAME BODY"),
        ):
            self.assertIn(
                marker,
                annotated,
                f"Message {index} was dropped from the annotated view:\n{annotated}",
            )
        self.assertIn(
            "400",
            annotated,
            f"An unrecognized message type left no trace at all:\n{annotated}",
        )
        for identity in ("subagent_type='fork'", "custom_type='pi-user-agents'"):
            self.assertIn(
                identity,
                annotated,
                f"A delegate turn rendered anonymously, losing {identity}:\n{annotated}",
            )


class AnnotateProjectorTests(unittest.TestCase):
    def tool_calls_in(self, fixture: str) -> list[object]:
        raw = json.loads((FIXTURES / fixture).read_text(encoding="utf-8"))
        verdict = render_transcript_review.gate(raw)
        self.assertTrue(verdict.ok, f"{fixture} was refused: {verdict.reason!r}")
        return [
            block
            for message in verdict.messages
            for block in message.content
            if isinstance(block, render_transcript_review.ToolInputBlock)
        ]

    def test_projector_never_goes_blind_on_a_tool_call_that_has_arguments(self) -> None:
        for fixture in ("pi.json", "claude.json", "codex.json"):
            with self.subTest(fixture=fixture):
                calls = self.tool_calls_in(fixture)
                self.assertTrue(calls, f"{fixture} exposed no tool calls to project")

                missed = [
                    call.name
                    for call in calls
                    if holds_a_long_string(call.model_extra or {})
                    and not render_transcript_review.project_arguments(call)[0]
                ]

                self.assertEqual(
                    missed,
                    [],
                    f"These {fixture} calls hold a long string the walk never reached: {missed!r}",
                )

    def test_an_empty_container_argument_still_leaves_a_trace(self) -> None:
        block = render_transcript_review.ToolInputBlock.model_validate(
            {"type": "tool-input", "name": "T", "id": "e", "paths": [], "opts": {}}
        )

        prose, tags = render_transcript_review.project_arguments(block)

        self.assertEqual(
            sorted(tags),
            ["opts", "paths"],
            f"Empty containers vanished without a trace: prose={prose!r} tags={tags!r}",
        )

    def test_projector_reaches_prose_nested_in_a_list_of_objects(self) -> None:
        block = render_transcript_review.ToolInputBlock.model_validate(
            {
                "type": "tool-input",
                "name": "ask_user_question",
                "id": "q1",
                "questions": [{"header": "Fleet", "question": "A" * 120}],
            }
        )

        prose, tags = render_transcript_review.project_arguments(block)

        self.assertEqual(
            [path for path, _ in prose],
            ["questions.0.question"],
            f"The walk did not reach prose inside a list of objects: {prose!r}",
        )
        self.assertEqual(
            tags.get("questions.0.header"),
            "Fleet",
            f"The walk lost a short nested value: {tags!r}",
        )


class AnnotateOutputTests(unittest.TestCase):
    @staticmethod
    def output(text: str, is_error: bool = False) -> object:
        return render_transcript_review.ToolOutputBlock.model_validate(
            {
                "type": "tool-output",
                "name": "teamsend",
                "id": "a",
                "is_error": is_error,
                "content": [{"type": "text", "text": text}],
            }
        )

    def test_the_result_budget_clears_the_longest_real_decision(self) -> None:
        """Guards against a budget cut that silently truncates real answers."""
        raw = json.loads((FIXTURES / "decisions.json").read_text(encoding="utf-8"))
        longest = max(
            len(render_transcript_review.ToolOutputBlock.model_validate(block).text())
            for message in raw
            for block in message.get("content", [])
            if isinstance(block, dict) and block.get("type") == "tool-output"
        )

        self.assertGreater(
            render_transcript_review.OUTPUT_BUDGET,
            longest,
            f"OUTPUT_BUDGET {render_transcript_review.OUTPUT_BUDGET} cannot hold the "
            f"longest real user decision ({longest} characters)",
        )

    def test_a_non_text_result_is_reported_rather_than_read_as_empty(self) -> None:
        screenshot = render_transcript_review.ToolOutputBlock.model_validate(
            {
                "type": "tool-output",
                "id": "b",
                "content": [
                    {"type": "image", "source": {"type": "base64", "data": "/9j/4AAQ" * 400}}
                ],
            }
        )

        summary = render_transcript_review.summarize_output(screenshot)

        self.assertIn(
            "image",
            summary,
            f"A result carrying only an image looked like an empty result: {summary!r}",
        )

    def test_an_error_output_survives_however_short_it_is(self) -> None:
        summary = render_transcript_review.summarize_output(
            self.output("Unknown team: momentum-1-0", is_error=True)
        )

        self.assertIn(
            "Unknown team",
            summary,
            f"A short error was suppressed like a receipt: {summary!r}",
        )

    def test_every_user_decision_in_a_real_session_is_readable_in_the_view(self) -> None:
        """The property the mode exists for: a skeleton outcome is writable from the view."""
        raw = json.loads((FIXTURES / "decisions.json").read_text(encoding="utf-8"))
        verdict = render_transcript_review.gate(raw)
        annotated = render_transcript_review.render_annotated(verdict.messages)

        answers = [
            block
            for message in raw
            for block in message.get("content", [])
            if isinstance(block, dict)
            and block.get("type") == "tool-output"
            and "User has answered" in json.dumps(block.get("content", ""))
        ]
        self.assertGreater(len(answers), 10, "the fixture stopped carrying user answers")

        lines_by_id = {
            line.split(" id=")[1].split(":")[0]: line
            for line in annotated.splitlines()
            if "]   OUT" in line
        }
        truncated = []
        for block in answers:
            identity = block.get("id")
            text = render_transcript_review.ToolOutputBlock.model_validate(block).text()
            tail = " ".join(text.split())[-40:]
            if tail not in lines_by_id.get(identity, ""):
                truncated.append(identity)

        self.assertEqual(
            truncated,
            [],
            f"{len(truncated)} of {len(answers)} user decisions are cut off in the view: {truncated!r}",
        )


class AnnotateRenderDefectTests(unittest.TestCase):
    def test_a_result_line_names_the_call_it_belongs_to(self) -> None:
        batch = [
            {
                "type": "assistant-response", "role": "assistant", "original_index": 5,
                "content": [
                    {"type": "tool-input", "name": "A", "id": "aaa", "q": "x" * 90},
                    {"type": "tool-input", "name": "B", "id": "bbb", "q": "y" * 90},
                    {"type": "tool-output", "id": "bbb", "content": "B finished second"},
                    {"type": "tool-output", "id": "aaa", "content": "A finished first"},
                ],
            }
        ]

        verdict = render_transcript_review.gate(batch)
        annotated = render_transcript_review.render_annotated(verdict.messages)

        for line in annotated.splitlines():
            if "B finished second" in line:
                self.assertIn(
                    "bbb", line, f"A result line did not name its call: {line!r}"
                )
            if "A finished first" in line:
                self.assertIn(
                    "aaa", line, f"A result line did not name its call: {line!r}"
                )

    def test_a_repeated_argument_body_is_printed_once_and_then_referenced(self) -> None:
        spawn_prompt = "You own the worktree. " + "".join(
            f"Rule {number} is distinct and must be obeyed. " for number in range(20)
        )
        transcript = [
            {"type": "assistant-response", "role": "assistant", "original_index": 10,
             "content": [{"type": "tool-input", "name": "spawn", "id": "s1", "prompt": spawn_prompt}]},
            {"type": "assistant-response", "role": "assistant", "original_index": 20,
             "content": [{"type": "tool-input", "name": "spawn", "id": "s2", "prompt": spawn_prompt}]},
        ]

        verdict = render_transcript_review.gate(transcript)
        annotated = render_transcript_review.render_annotated(verdict.messages)

        self.assertEqual(
            annotated.count(spawn_prompt[:120]),
            1,
            f"An identical argument body was printed twice:\n{annotated}",
        )
        self.assertIn(
            "identical to i=10 id=s1",
            [line for line in annotated.splitlines() if line.startswith("[20]   prompt")][0],
            f"The repeat did not point back to where the body was printed:\n{annotated}",
        )

    def test_a_compaction_boundary_stays_labelled_as_a_boundary(self) -> None:
        transcript = [
            {"type": "user-message", "role": "user", "original_index": 1, "content": ["go"]},
            {"type": "compaction", "role": "user", "original_index": 801,
             "content": ["This summary captures work done before the most recent messages."]},
        ]

        verdict = render_transcript_review.gate(transcript)
        annotated = render_transcript_review.render_annotated(verdict.messages)

        boundary = [line for line in annotated.splitlines() if line.startswith("[801]")]
        self.assertTrue(boundary, f"The compaction message vanished:\n{annotated}")
        self.assertNotIn(
            "USER",
            boundary[0],
            f"The compaction boundary reads as an ordinary user turn: {boundary[0]!r}",
        )

    def test_refusal_names_the_real_problem_for_a_block_with_no_type(self) -> None:
        transcript = [message(1, "assistant", [{"foo": "bar"}])]

        verdict = render_transcript_review.gate(transcript)

        self.assertFalse(verdict.ok, "A block with no type was accepted")
        self.assertIn(
            "type",
            verdict.reason,
            f"The refusal blamed a missing name instead of the missing type: {verdict.reason!r}",
        )


class AnnotateDeduplicationTests(unittest.TestCase):
    def test_a_late_sorting_path_argument_is_not_clipped_away(self) -> None:
        """A file path is short, so it is a tag. Tags must not lose whole keys."""
        block = {"type": "tool-input", "name": "Edit", "id": "anti"}
        for filler in range(40):
            block[f"ArtifactMetadata.Field{filler:02d}"] = f"value-{filler}"
        block["TargetFile"] = "/Users/giladbarnea/dev/land/completions/_pi"
        transcript = [{"type": "assistant-response", "role": "assistant",
                       "original_index": 16, "content": [block]}]

        annotated = render_transcript_review.render_annotated(
            render_transcript_review.gate(transcript).messages
        )

        self.assertIn(
            "/Users/giladbarnea/dev/land/completions/_pi",
            annotated,
            f"The edited path was clipped out of the tag line:\n{annotated}",
        )

    def test_two_results_sharing_a_long_prefix_are_not_called_identical(self) -> None:
        shared = "F" * (render_transcript_review.OUTPUT_BUDGET + 50)
        transcript = [
            {"type": "assistant-response", "role": "assistant", "original_index": 1,
             "content": [{"type": "tool-output", "id": "a", "content": shared + " 148 passed in 3.21s"}]},
            {"type": "assistant-response", "role": "assistant", "original_index": 2,
             "content": [{"type": "tool-output", "id": "b", "content": shared + " 148 passed in 9.99s"}]},
        ]

        annotated = render_transcript_review.render_annotated(
            render_transcript_review.gate(transcript).messages
        )

        self.assertNotIn(
            "identical to i=1",
            annotated,
            f"Two different results were declared identical on a shared prefix:\n{annotated[:400]}",
        )

    def test_a_back_reference_resolves_to_a_line_that_exists(self) -> None:
        """A reference naming only an index is unresolvable when that index has many."""
        body = "R" * 500
        transcript = [
            {"type": "assistant-response", "role": "assistant", "original_index": 2,
             "content": [
                 {"type": "tool-output", "id": "aa", "content": body},
                 {"type": "tool-output", "id": "bb", "content": "something else"},
                 {"type": "tool-output", "id": "cc", "content": "a third thing"},
             ]},
            {"type": "assistant-response", "role": "assistant", "original_index": 3,
             "content": [{"type": "tool-output", "id": "dd", "content": body}]},
        ]

        annotated = render_transcript_review.render_annotated(
            render_transcript_review.gate(transcript).messages
        )

        reference = [line for line in annotated.splitlines() if "identical to" in line]
        self.assertTrue(reference, f"the repeat was not collapsed at all:\n{annotated}")
        self.assertIn(
            "id=aa",
            reference[0],
            f"the reference names an index holding three results, so it resolves to nothing: {reference[0]!r}",
        )

    def test_a_reference_is_not_used_when_it_costs_more_than_the_value(self) -> None:
        transcript = [
            {"type": "assistant-response", "role": "assistant", "original_index": 1,
             "content": [{"type": "tool-output", "id": "a", "content": "{}"}]},
            {"type": "assistant-response", "role": "assistant", "original_index": 2,
             "content": [{"type": "tool-output", "id": "b", "content": "{}"}]},
        ]

        annotated = render_transcript_review.render_annotated(
            render_transcript_review.gate(transcript).messages
        )

        self.assertNotIn(
            "identical to",
            annotated,
            f"A two-character result was replaced by a longer reference:\n{annotated}",
        )

    def test_an_interrupted_call_is_marked_as_unpaired(self) -> None:
        transcript = [
            {"type": "assistant-response", "role": "assistant", "original_index": 230,
             "content": [{"type": "tool-input", "name": "Bash", "id": "QeR5", "command": "sleep 90"}]},
        ]

        annotated = render_transcript_review.render_annotated(
            render_transcript_review.gate(transcript).messages
        )

        self.assertIn(
            "no-result-in-file",
            annotated,
            f"An interrupted call is indistinguishable from a completed one:\n{annotated}",
        )

    def test_an_unvetted_block_reports_how_much_it_held(self) -> None:
        """A vetted type shows its content. An unknown one shows at least its size."""
        transcript = [
            {"type": "assistant-response", "role": "assistant", "original_index": 14,
             "content": [{"type": "some-future-block", "content": "t" * 2783}]},
        ]

        annotated = render_transcript_review.render_annotated(
            render_transcript_review.gate(transcript).messages
        )

        self.assertIn(
            "2783",
            annotated,
            f"An elided block gave no hint of its size: {annotated!r}",
        )

    def test_the_drift_line_is_empty_for_a_healthy_export(self) -> None:
        transcript = [
            {"type": "assistant-response", "role": "assistant", "original_index": 1,
             "content": [{"type": "thinking", "content": "quiet"},
                         {"type": "subagent-task", "content": "delegated"}]},
        ]

        summary = "\n".join(
            render_transcript_review.projection_summary(
                render_transcript_review.gate(transcript).messages
            )
        )

        drift = [line for line in summary.splitlines() if "unrecognized" in line][0]
        self.assertIn(
            "none",
            drift,
            f"Known elided block types were reported as drift: {drift!r}",
        )


class AnnotateIdentityTests(unittest.TestCase):
    def test_non_unique_tool_ids_are_reported_because_pairing_depends_on_them(self) -> None:
        """One provider emits a constant id, which silently defeats `unmatched`."""
        transcript = [
            {"type": "assistant-response", "role": "assistant", "original_index": 2,
             "content": [
                 {"type": "tool-input", "name": "Read", "id": "anti", "file_path": "/a.md"},
                 {"type": "tool-input", "name": "Read", "id": "anti", "file_path": "/b.md"},
                 {"type": "tool-output", "id": "anti", "content": "one result only"},
             ]},
        ]

        summary = "\n".join(
            render_transcript_review.projection_summary(
                render_transcript_review.gate(transcript).messages
            )
        )

        self.assertIn(
            "NOT UNIQUE",
            summary,
            f"Colliding tool ids went unreported, so pairing and anchoring look sound: {summary!r}",
        )

    def test_a_block_that_moved_its_payload_off_content_still_reports_its_size(self) -> None:
        transcript = [
            {"type": "assistant-response", "role": "assistant", "original_index": 1,
             "content": [{"type": "thinking", "reasoning": "R" * 5000}]},
        ]

        annotated = render_transcript_review.render_annotated(
            render_transcript_review.gate(transcript).messages
        )

        self.assertNotIn(
            "+0 chars",
            annotated,
            f"A 5000-character block reported itself as empty: {annotated!r}",
        )

    def test_an_unknown_wrapper_holding_odd_content_does_not_crash(self) -> None:
        transcript = [
            {"type": "user-message", "role": "user", "original_index": 1, "content": ["go"]},
            {"type": "a-future-wrapper", "content": [["nested"], 42, {"type": "x"}]},
        ]

        verdict = render_transcript_review.gate(transcript)
        annotated = render_transcript_review.render_annotated(verdict.messages)

        self.assertNotIn(
            "[None]",
            annotated,
            f"A wrapper with no index rendered an anchor that cannot anchor:\n{annotated}",
        )


class AnnotateSummaryTests(unittest.TestCase):
    @staticmethod
    def summary_of(transcript: list[dict]) -> str:
        return "\n".join(
            render_transcript_review.projection_summary(
                render_transcript_review.gate(transcript).messages
            )
        )

    def test_a_result_line_names_its_tool(self) -> None:
        transcript = [
            {"type": "assistant-response", "role": "assistant", "original_index": 3,
             "content": [{"type": "tool-output", "name": "Read", "id": "anti",
                          "content": "Created At: 2026-06-19"}]},
        ]

        annotated = render_transcript_review.render_annotated(
            render_transcript_review.gate(transcript).messages
        )

        self.assertIn(
            "Read",
            annotated,
            f"The result line does not say which tool produced it: {annotated!r}",
        )

    def test_ids_colliding_across_messages_do_not_warn_about_anchoring(self) -> None:
        """resolve_anchors scopes to one message, so a cross-message collision is safe."""
        transcript = [
            {"type": "assistant-response", "role": "assistant", "original_index": index,
             "content": [{"type": "tool-input", "name": "Bash", "id": "01Ab", "command": "ls"}]}
            for index in (1, 2)
        ]

        summary = self.summary_of(transcript)

        self.assertNotIn(
            "anchor is ambiguous",
            summary,
            f"A safe cross-message collision was reported as an anchoring risk: {summary!r}",
        )
        self.assertIn(
            "cannot be believed",
            summary,
            f"The pairing hazard, which is real in this case, went unreported: {summary!r}",
        )

    def test_ids_colliding_inside_one_message_do_warn_about_anchoring(self) -> None:
        transcript = [
            {"type": "assistant-response", "role": "assistant", "original_index": 2,
             "content": [
                 {"type": "tool-input", "name": "Read", "id": "anti", "file_path": "/a"},
                 {"type": "tool-input", "name": "Read", "id": "anti", "file_path": "/b"},
             ]},
        ]

        summary = self.summary_of(transcript)

        self.assertIn(
            "anchor",
            summary,
            f"A real anchoring hazard went unreported: {summary!r}",
        )

    def test_a_short_repeated_argument_is_printed_rather_than_referenced(self) -> None:
        path = "/Users/giladbarnea/dev/some/reasonably/long/but/entirely/scannable/path/to/a/deeply/nested/file.py"
        transcript = [
            {"type": "assistant-response", "role": "assistant", "original_index": index,
             "content": [{"type": "tool-input", "name": "Read", "id": f"i{index}", "file_path": path}]}
            for index in (747, 845)
        ]

        annotated = render_transcript_review.render_annotated(
            render_transcript_review.gate(transcript).messages
        )

        self.assertEqual(
            annotated.count(path),
            2,
            f"A scannable path was replaced by a reference that saves almost nothing:\n{annotated}",
        )


class AnnotateResultFidelityTests(unittest.TestCase):
    def test_a_repeated_failure_is_still_marked_as_a_failure(self) -> None:
        """Collapsing happens before the ERROR prefix is added, so it can erase it."""
        body = "connection reset by peer " * 20
        transcript = [
            {"type": "assistant-response", "role": "assistant", "original_index": 1,
             "content": [{"type": "tool-output", "name": "teamsend", "id": "ok", "content": body}]},
            {"type": "assistant-response", "role": "assistant", "original_index": 2,
             "content": [{"type": "tool-output", "name": "teamsend", "id": "bad",
                          "is_error": True, "content": body}]},
        ]

        annotated = render_transcript_review.render_annotated(
            render_transcript_review.gate(transcript).messages
        )

        failure = [line for line in annotated.splitlines() if "id=bad" in line][0]
        self.assertIn(
            "ERROR",
            failure,
            f"A failure was rendered as a pointer to an earlier success: {failure!r}",
        )

    def test_a_repeated_result_keeps_its_image_marker(self) -> None:
        parts = [{"type": "text", "text": "screenshot captured " * 10}]
        transcript = [
            {"type": "assistant-response", "role": "assistant", "original_index": 1,
             "content": [{"type": "tool-output", "id": "a", "content": parts}]},
            {"type": "assistant-response", "role": "assistant", "original_index": 2,
             "content": [{"type": "tool-output", "id": "b",
                          "content": parts + [{"type": "image", "source": {"data": "x"}}]}]},
        ]

        annotated = render_transcript_review.render_annotated(
            render_transcript_review.gate(transcript).messages
        )

        carried = [line for line in annotated.splitlines() if "id=b" in line][0]
        self.assertIn(
            "[image ",
            carried,
            f"An image payload was collapsed away by a text-only identity: {carried!r}",
        )

    def test_a_text_part_whose_key_moved_is_refused_not_read_as_empty(self) -> None:
        """The same reasoning as the block level, carried down to the part level."""
        transcript = [
            {"type": "assistant-response", "role": "assistant", "original_index": 1,
             "content": [{"type": "tool-output", "name": "Read", "id": "a",
                          "content": [{"type": "text", "value": "R" * 720}]}]},
        ]

        verdict = render_transcript_review.gate(transcript)

        self.assertFalse(
            verdict.ok,
            "A text part whose payload key moved emptied the result, with every "
            "tripwire green",
        )

    def test_a_non_text_part_is_still_carried_rather_than_refused(self) -> None:
        transcript = [
            {"type": "assistant-response", "role": "assistant", "original_index": 1,
             "content": [{"type": "tool-output", "name": "Read", "id": "a",
                          "content": [{"type": "text", "text": "shot"},
                                      {"type": "image", "source": {"data": "x"}}]}]},
        ]

        verdict = render_transcript_review.gate(transcript)

        self.assertTrue(
            verdict.ok,
            f"A legitimate image part was refused: {verdict.reason!r}",
        )

    def test_a_result_whose_payload_key_moved_is_refused_not_read_as_empty(self) -> None:
        transcript = [
            {"type": "assistant-response", "role": "assistant", "original_index": 1,
             "content": [{"type": "tool-output", "name": "Bash", "id": "a",
                          "result_body": "R" * 720}]},
        ]

        verdict = render_transcript_review.gate(transcript)

        self.assertFalse(
            verdict.ok,
            "A result whose payload moved to another key was read as empty, with every "
            "tripwire green",
        )


class AnnotateRoundNineteenTests(unittest.TestCase):
    def test_clipping_a_thinking_block_counts_toward_the_view_residue(self) -> None:
        """Thinking is the largest clipping channel on reasoning-heavy sessions."""
        transcript = [
            {"type": "assistant-response", "role": "assistant", "original_index": 1,
             "content": [{"type": "thinking", "content": "t" * 10000}]},
        ]

        summary = "\n".join(
            render_transcript_review.projection_summary(
                render_transcript_review.gate(transcript).messages
            )
        )

        self.assertNotIn(
            "clipped: nothing",
            summary,
            f"A 10,000-character thinking block was clipped and never counted: {summary!r}",
        )

    def test_every_message_key_the_exporter_emits_is_vetted(self) -> None:
        """Sourced from _MESSAGE_JSON_KEYS in the exporter."""
        emitted = {
            "type", "role", "original_index", "content", "branch", "isMeta",
            "sourceToolUserId", "agent_id", "subagent_type", "name", "model",
            "custom_type", "inherited_context", "status", "timestamp", "native_entry_id",
        }

        unvetted = sorted(emitted - render_transcript_review.VETTED_MESSAGE_KEYS)

        self.assertEqual(
            unvetted,
            [],
            f"These keys would fire the drift line on a healthy export: {unvetted!r}",
        )

    def test_a_delegate_brief_is_distinguishable_from_its_report(self) -> None:
        """`agent` turns come in all three roles, and the type alone cannot say which."""
        transcript = [
            {"type": "agent", "role": "user", "original_index": 74, "agent_id": "a8b",
             "subagent_type": "fork", "content": ["audit what the pruner dropped"]},
            {"type": "agent", "role": "assistant", "original_index": 87, "agent_id": "a8b",
             "subagent_type": "fork", "content": ["the pruner dropped 31 messages"]},
        ]

        annotated = render_transcript_review.render_annotated(
            render_transcript_review.gate(transcript).messages
        )

        brief = [line for line in annotated.splitlines() if line.startswith("[74]")][0]
        report = [line for line in annotated.splitlines() if line.startswith("[87]")][0]
        self.assertNotEqual(
            brief.partition("] ")[2].partition(":")[0],
            report.partition("] ")[2].partition(":")[0],
            f"A delegate's brief reads the same as its report:\n{brief}\n{report}",
        )

    def test_an_unchanged_attribution_is_not_repeated_every_turn(self) -> None:
        transcript = [
            {"type": "agent", "role": "assistant", "original_index": index,
             "agent_id": "a8b", "subagent_type": "fork",
             "content": [{"type": "tool-input", "name": "Read", "id": f"i{index}",
                          "file_path": "/tmp/x"}]}
            for index in range(75, 80)
        ]

        annotated = render_transcript_review.render_annotated(
            render_transcript_review.gate(transcript).messages
        )

        self.assertEqual(
            annotated.count("subagent_type='fork'"),
            1,
            f"The same attribution was repeated on every turn:\n{annotated}",
        )


class AnnotateOwnResidueTests(unittest.TestCase):
    def test_the_summary_reports_what_this_view_itself_removed(self) -> None:
        """Per-line markers do not scale: 44 scattered residues need an aggregate."""
        transcript = [
            {"type": "assistant-response", "role": "assistant", "original_index": index,
             "content": [{"type": "tool-output", "name": "Bash", "id": f"i{index}",
                          "content": f"result {index} " + "C" * 5000}]}
            for index in range(1, 4)
        ]

        summary = "\n".join(
            render_transcript_review.projection_summary(
                render_transcript_review.gate(transcript).messages
            )
        )

        line = [line for line in summary.splitlines() if "this view clipped" in line][0]
        self.assertRegex(
            line,
            r"9\d{3} characters",
            f"The view did not report its own clipping: {line!r}",
        )

    def test_a_view_that_clipped_nothing_says_so(self) -> None:
        transcript = [
            {"type": "assistant-response", "role": "assistant", "original_index": 1,
             "content": [{"type": "tool-output", "name": "Bash", "id": "a",
                          "content": "148 passed"}]},
        ]

        summary = "\n".join(
            render_transcript_review.projection_summary(
                render_transcript_review.gate(transcript).messages
            )
        )

        self.assertIn(
            "this view clipped: nothing",
            summary,
            f"A complete view did not say it was complete: {summary!r}",
        )


class AnnotateSignalQualityTests(unittest.TestCase):
    def test_a_session_with_no_tool_calls_is_not_reported_as_drift(self) -> None:
        """A warning that fires on healthy input teaches the reader to skip the line."""
        transcript = [
            {"type": "user-message", "role": "user", "original_index": 1, "content": ["hi"]},
            {"type": "assistant-response", "role": "assistant", "original_index": 2,
             "content": ["hello"]},
        ]

        summary = "\n".join(
            render_transcript_review.projection_summary(
                render_transcript_review.gate(transcript).messages
            )
        )

        self.assertNotIn(
            "none found",
            summary,
            f"A conversation with no tool calls was reported as format drift: {summary!r}",
        )

    def test_a_refusal_points_at_the_stable_index_not_the_array_position(self) -> None:
        """The toolkit's own rule is to address records by stable identity."""
        transcript = [
            {"type": "user-message", "role": "user", "original_index": 100, "content": ["a"]},
            {"type": "assistant-response", "role": "assistant", "original_index": 205,
             "content": [{"type": "tool-input", "id": "x"}]},
        ]

        verdict = render_transcript_review.gate(transcript)

        self.assertFalse(verdict.ok, "the malformed call was accepted")
        self.assertIn(
            "i=205",
            verdict.reason,
            f"The refusal located the fault by array position: {verdict.reason!r}",
        )


class AnnotateMessageKeyTests(unittest.TestCase):
    def test_a_harness_injected_turn_is_distinguishable_from_a_typed_one(self) -> None:
        """smart-compact drops harness turns and keeps typed ones. Claude flags it here."""
        transcript = [
            {"type": "user-message", "role": "user", "original_index": 7, "isMeta": True,
             "content": ["<local-command-caveat>Caveat: generated while running local commands"]},
            {"type": "user-message", "role": "user", "original_index": 8,
             "content": ["please fix the parser"]},
        ]

        annotated = render_transcript_review.render_annotated(
            render_transcript_review.gate(transcript).messages
        )

        injected = [line for line in annotated.splitlines() if line.startswith("[7]")][0]
        typed = [line for line in annotated.splitlines() if line.startswith("[8]")][0]
        self.assertIn(
            "isMeta",
            injected,
            f"A harness-injected turn reads as something the user typed: {injected!r}",
        )
        self.assertNotIn(
            "isMeta", typed, f"A typed turn was marked as harness-injected: {typed!r}"
        )

    def test_an_unknown_message_key_reaches_the_drift_line(self) -> None:
        transcript = [
            {"type": "user-message", "role": "user", "original_index": 1,
             "spoken_by": "a-future-delegate-field", "content": ["hello"]},
        ]

        summary = "\n".join(
            render_transcript_review.projection_summary(
                render_transcript_review.gate(transcript).messages
            )
        )

        self.assertIn(
            "spoken_by",
            summary,
            f"An unknown message-level key was invisible: {summary!r}",
        )

    def test_the_known_message_keys_of_every_real_export_are_vetted(self) -> None:
        """The drift line must read `none` on real data, or it is noise."""
        for fixture in ("pi.json", "claude.json", "codex.json"):
            with self.subTest(fixture=fixture):
                raw = json.loads((FIXTURES / fixture).read_text(encoding="utf-8"))
                summary = "\n".join(
                    render_transcript_review.projection_summary(
                        render_transcript_review.gate(raw).messages
                    )
                )

                line = [line for line in summary.splitlines() if "unrecognized" in line][0]
                self.assertIn(
                    "none", line, f"{fixture} reported drift on a healthy export: {line!r}"
                )


class AnnotatePartFidelityTests(unittest.TestCase):
    def test_a_non_text_part_reports_its_size_like_an_unvetted_block(self) -> None:
        """`[tool_reference]` alone loses the name it referenced."""
        transcript = [
            {"type": "assistant-response", "role": "assistant", "original_index": 36,
             "content": [{"type": "tool-output", "name": "ToolSearch", "id": "01Jy",
                          "content": [{"type": "tool_reference",
                                       "tool_name": "ScheduleWakeup"}]}]},
        ]

        annotated = render_transcript_review.render_annotated(
            render_transcript_review.gate(transcript).messages
        )

        self.assertRegex(
            annotated,
            r"tool_reference \+\d+ chars",
            f"A non-text part vanished without even a size: {annotated!r}",
        )

    def test_an_unknown_part_type_reaches_the_drift_line(self) -> None:
        transcript = [
            {"type": "assistant-response", "role": "assistant", "original_index": 1,
             "content": [{"type": "tool-output", "name": "T", "id": "a",
                          "content": [{"type": "some_future_part", "body": "x"}]}]},
        ]

        summary = "\n".join(
            render_transcript_review.projection_summary(
                render_transcript_review.gate(transcript).messages
            )
        )

        self.assertIn(
            "some_future_part",
            summary,
            f"An unknown result part never reached the drift line: {summary!r}",
        )

    def test_an_unknown_key_on_a_result_reaches_the_drift_line(self) -> None:
        """Renaming is_error would turn every failure into a success."""
        transcript = [
            {"type": "assistant-response", "role": "assistant", "original_index": 1,
             "content": [{"type": "tool-output", "name": "Bash", "id": "a",
                          "error": True, "content": "boom: exit 1"}]},
        ]

        summary = "\n".join(
            render_transcript_review.projection_summary(
                render_transcript_review.gate(transcript).messages
            )
        )

        self.assertIn(
            "error",
            summary,
            f"An unknown key on a result was invisible: {summary!r}",
        )


class AnnotateTruncationTests(unittest.TestCase):
    @staticmethod
    def summary_of(transcript: list[dict]) -> str:
        return "\n".join(
            render_transcript_review.projection_summary(
                render_transcript_review.gate(transcript).messages
            )
        )

    def test_a_spliced_argument_is_reported(self) -> None:
        """`ch -t:s` splices head and tail around a bare `...` line, in arguments too."""
        transcript = [
            {"type": "assistant-response", "role": "assistant", "original_index": 73,
             "content": [{"type": "tool-input", "name": "Write", "id": "anti",
                          "CodeContent": "<!DOCTYPE html>" + "h" * 240 + "\n...\n"
                                         + "t" * 240 + "</html>"}]},
        ]

        summary = self.summary_of(transcript)

        self.assertIn(
            "1 argument",
            summary,
            f"A truncated tool argument was invisible to every tripwire: {summary!r}",
        )

    def test_a_spliced_result_is_reported(self) -> None:
        transcript = [
            {"type": "assistant-response", "role": "assistant", "original_index": 1,
             "content": [{"type": "tool-output", "name": "Bash", "id": "a",
                          "content": "start of output\n...\nend of output"}]},
        ]

        self.assertIn(
            "1 result",
            self.summary_of(transcript),
            f"A truncated result was not reported: {self.summary_of(transcript)!r}",
        )

    def test_an_untruncated_export_reports_no_splices(self) -> None:
        for fixture in ("pi.json", "claude.json"):
            with self.subTest(fixture=fixture):
                raw = json.loads((FIXTURES / fixture).read_text(encoding="utf-8"))
                summary = "\n".join(
                    render_transcript_review.projection_summary(
                        render_transcript_review.gate(raw).messages
                    )
                )

                line = [line for line in summary.splitlines() if "spliced" in line][0]
                self.assertIn(
                    "none",
                    line,
                    f"{fixture} was wrongly reported as truncated: {line!r}",
                )

    def test_calls_carrying_no_arguments_are_counted(self) -> None:
        """A payload-key rename would empty every call, and nothing else would notice."""
        transcript = [
            {"type": "assistant-response", "role": "assistant", "original_index": index,
             "content": [{"type": "tool-input", "name": "team_list", "id": f"i{index}"}]}
            for index in range(1, 4)
        ]

        self.assertIn(
            "3 of 3",
            self.summary_of(transcript),
            f"Calls with no arguments went uncounted: {self.summary_of(transcript)!r}",
        )


class AnnotateClippingTests(unittest.TestCase):
    def test_a_clipped_result_keeps_the_verdict_that_sits_at_its_end(self) -> None:
        """An outcome is an exit status or a final tally, and those come last."""
        block = render_transcript_review.ToolOutputBlock.model_validate(
            {"type": "tool-output", "name": "Bash", "id": "a",
             "content": "collecting ... " * 900 + "148 passed, 0 failed in 3.21s"}
        )

        summary = render_transcript_review.summarize_output(block)

        self.assertIn(
            "148 passed, 0 failed",
            summary,
            f"The verdict at the end of a long result was clipped away: {summary[-160:]!r}",
        )
        self.assertIn(
            "collecting",
            summary,
            f"The head of the result was lost as well: {summary[:160]!r}",
        )

    def test_a_clipped_value_still_reports_the_residue_it_removed(self) -> None:
        clipped = render_transcript_review.clip("x" * 3000, 2000)

        self.assertIn(
            "+1000 chars",
            clipped,
            f"Clipping stopped reporting what it removed: {clipped!r}",
        )
        self.assertLessEqual(
            len(clipped),
            2000 + 40,
            f"Clipping exceeded its budget: {len(clipped)} characters",
        )


class AnnotateVettedBlockTests(unittest.TestCase):
    def test_a_thinking_block_shows_its_content_not_only_its_size(self) -> None:
        """A drop decision removes the whole message, so its content must be readable."""
        transcript = [
            {"type": "assistant-response", "role": "assistant", "original_index": 14,
             "content": [{"type": "thinking",
                          "content": "The eyeless pack cannot meet the request. " * 3}]},
        ]

        annotated = render_transcript_review.render_annotated(
            render_transcript_review.gate(transcript).messages
        )

        self.assertIn(
            "eyeless pack cannot meet",
            annotated,
            f"A thinking block was reduced to a byte count: {annotated!r}",
        )

    def test_a_result_part_with_no_type_is_refused_not_read_as_empty(self) -> None:
        transcript = [
            {"type": "assistant-response", "role": "assistant", "original_index": 1,
             "content": [{"type": "tool-output", "name": "Bash", "id": "a",
                          "content": [{"kind": "text", "text": "148 passed, 0 failed"}]}]},
        ]

        verdict = render_transcript_review.gate(transcript)

        self.assertFalse(
            verdict.ok,
            "A result part with no type emptied the result, with every tripwire green",
        )

    def test_the_id_tally_counts_the_same_handle_the_renderer_anchors_on(self) -> None:
        transcript = [
            {"type": "assistant-response", "role": "assistant", "original_index": 1,
             "content": [{"type": "tool-input", "name": "Bash",
                          "native_tool_call_id": "call_abc", "command": "pytest"}]},
        ]

        summary = "\n".join(
            render_transcript_review.projection_summary(
                render_transcript_review.gate(transcript).messages
            )
        )

        self.assertNotIn(
            "none found",
            summary,
            f"The tally ignored the handle the renderer actually anchors on: {summary!r}",
        )


class AnnotateDelegateTests(unittest.TestCase):
    def test_a_delegate_turn_carrying_only_tools_still_says_whose_it_is(self) -> None:
        """Most delegate turns are pure tool traffic, and identity only rode on text."""
        transcript = [
            {"type": "agent", "role": "assistant", "original_index": 75,
             "agent_id": "a8bad7da3c957de67", "subagent_type": "fork",
             "content": [{"type": "tool-input", "name": "Read", "id": "01UV",
                          "file_path": "/tmp/x.py"}]},
        ]

        annotated = render_transcript_review.render_annotated(
            render_transcript_review.gate(transcript).messages
        )

        self.assertIn(
            "subagent_type='fork'",
            annotated,
            f"A delegate's tool run is indistinguishable from the main agent's:\n{annotated}",
        )

    def test_a_pruned_delegate_turn_still_says_whose_it_is(self) -> None:
        """After pruning, a delegate's file work is a string block, not a tool block."""
        transcript = [
            {"type": "agent", "role": "assistant", "original_index": 75,
             "agent_id": "a8bad7da3c957de67", "subagent_type": "fork",
             "content": ['<Write path="/tmp/out.py" id="01UV"/>']},
        ]

        annotated = render_transcript_review.render_annotated(
            render_transcript_review.gate(transcript).messages
        )

        self.assertIn(
            "subagent_type='fork'",
            annotated,
            f"A pruned delegate's file write reads as the main agent's own:\n{annotated}",
        )

    def test_a_wrapper_that_carries_text_does_not_announce_itself_twice(self) -> None:
        transcript = [
            {"type": "compaction", "role": "user", "original_index": 801,
             "content": ["This summary captures work done before the recent messages."]},
        ]

        annotated = render_transcript_review.render_annotated(
            render_transcript_review.gate(transcript).messages
        )

        self.assertEqual(
            annotated.count("COMPACTION-BOUNDARY"),
            1,
            f"The wrapper announced itself on both a header and its text:\n{annotated}",
        )

    def test_the_main_agent_gets_no_wrapper_header(self) -> None:
        transcript = [
            {"type": "assistant-response", "role": "assistant", "original_index": 1,
             "content": [{"type": "tool-input", "name": "Read", "id": "a", "file_path": "/tmp/x"}]},
        ]

        annotated = render_transcript_review.render_annotated(
            render_transcript_review.gate(transcript).messages
        )

        self.assertEqual(
            len(annotated.strip().splitlines()),
            1,
            f"An ordinary assistant turn gained a header it does not need:\n{annotated}",
        )


class AnnotateFileReferenceTests(unittest.TestCase):
    def test_a_pruned_file_reference_keeps_its_path_and_id_and_no_speaker(self) -> None:
        """`drop_file_references` annotations are transcribed from exactly these fields."""
        reference = '<Read path="/Users/giladbarnea/dev/tractor-ami/docs/brief.md" id="c1L2"/>'
        transcript = [
            {"type": "assistant-response", "role": "assistant", "original_index": 102,
             "content": [reference]},
        ]

        annotated = render_transcript_review.render_annotated(
            render_transcript_review.gate(transcript).messages
        )

        self.assertEqual(
            annotated.strip(),
            f"[102] {reference}",
            f"A pruned file reference was mangled or prefixed as prose: {annotated!r}",
        )


class AnnotateCliTests(unittest.TestCase):
    def test_the_command_refuses_a_native_session_and_reports_what_it_saw(self) -> None:
        import subprocess
        import tempfile

        script = SCRIPTS / "render_transcript_review.py"
        with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as handle:
            handle.write('{"type":"session","id":"s"}\n{"type":"message","id":"a"}\n')
            native = handle.name

        refusal = subprocess.run(
            ["uv", "run", "--script", str(script), "--annotate", native],
            capture_output=True, text=True, timeout=180,
        )

        self.assertNotEqual(refusal.returncode, 0, "a native session was accepted")
        self.assertIn(
            "JSON",
            refusal.stderr,
            f"the refusal did not name the format problem: {refusal.stderr!r}",
        )

    def test_the_command_renders_a_real_export_and_summarizes_to_stderr(self) -> None:
        import subprocess

        script = SCRIPTS / "render_transcript_review.py"

        run = subprocess.run(
            ["uv", "run", "--script", str(script), "--annotate", str(FIXTURES / "codex.json")],
            capture_output=True, text=True, timeout=180,
        )

        self.assertEqual(run.returncode, 0, f"a real export failed: {run.stderr!r}")
        self.assertIn("annotate | unrecognized", run.stderr, f"no summary: {run.stderr!r}")
        self.assertRegex(run.stdout, r"^\[\d+\] ", f"no keyed lines: {run.stdout[:200]!r}")


class AnnotateRenderTests(unittest.TestCase):
    def test_every_tool_line_can_anchor_a_skeleton_and_the_view_is_smaller(self) -> None:
        raw = json.loads((FIXTURES / "claude.json").read_text(encoding="utf-8"))
        verdict = render_transcript_review.gate(raw)
        real_ids = {
            block.get("id")
            for message in raw
            for block in message.get("content", [])
            if isinstance(block, dict) and block.get("type") == "tool-input"
        }

        annotated = render_transcript_review.render_annotated(verdict.messages)

        tool_line = re.compile(r"^\[(\d+)\] <(\S+) id=(\S+?)>?(?: |$)")
        anchors = [tool_line.match(line) for line in annotated.splitlines()]
        found = [match for match in anchors if match is not None]
        self.assertTrue(found, f"No anchorable tool lines were emitted:\n{annotated[:400]}")
        for match in found:
            self.assertIn(
                match.group(3),
                real_ids,
                f"A tool line named an id absent from the source: {match.group(0)!r}",
            )
        call_count = sum(
            1
            for m in raw
            for b in m.get("content", [])
            if isinstance(b, dict) and b.get("type") == "tool-input"
        )
        self.assertEqual(
            len(found),
            call_count,
            f"Expected one anchor line per source tool call, got {len(found)} of {call_count}",
        )

    def test_the_annotated_view_is_smaller_on_each_provider_fixture(self) -> None:
        """The general claim. The ratio varies with how repetitive the session is."""
        for fixture in ("pi.json", "claude.json", "codex.json", "decisions.json"):
            with self.subTest(fixture=fixture):
                raw = json.loads((FIXTURES / fixture).read_text(encoding="utf-8"))

                annotated = render_transcript_review.render_annotated(
                    render_transcript_review.gate(raw).messages
                )
                verbose = render_transcript_review.render(raw)

                self.assertLess(
                    len(annotated),
                    len(verbose),
                    f"{fixture} got bigger: {len(annotated)} against {len(verbose)}",
                )

    def test_the_dense_view_halves_a_transcript_dominated_by_tool_traffic(self) -> None:
        """Size is only claimed for the case the mode exists to fix."""
        raw = json.loads((FIXTURES / "tool_traffic.json").read_text(encoding="utf-8"))

        annotated = render_transcript_review.render_annotated(
            render_transcript_review.gate(raw).messages
        )
        verbose = render_transcript_review.render(raw)

        self.assertLess(
            len(annotated),
            len(verbose) // 2,
            f"The dense view saved little: {len(annotated)} against {len(verbose)}",
        )


def load_tests(loader, tests, ignore):  # noqa: ARG001
    """Run the scripts' doctests as part of this suite."""
    import transcript_common

    tests.addTests(doctest.DocTestSuite(render_transcript_review))
    tests.addTests(doctest.DocTestSuite(transcript_common))
    tests.addTests(doctest.DocTestSuite(analyze_transcript_json))
    return tests


if __name__ == "__main__":
    unittest.main()
