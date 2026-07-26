#!/usr/bin/env -S uv run
# /// script
# requires-python = "==3.12.*"
# dependencies = ["pyyaml"]
# ///

import hashlib
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

import analyze_transcript_json
import apply_compaction_plan
import generate_compaction_plan
import markremove
import prune_transcript
import render_review_view


def message(index: int, role: str, content: list[object]) -> dict[str, object]:
    return {
        "type": "user-message" if role == "user" else "assistant-response",
        "role": role,
        "original_index": index,
        "content": content,
    }


class SmartCompactTests(unittest.TestCase):
    def test_pruner_handles_multi_read_delete_and_mixed_order(self) -> None:
        mixed = [
            "before",
            {"type": "tool-input", "name": "read_many_files", "id": "many", "paths": ["a", "b"]},
            {"type": "tool-input", "name": "Bash", "id": "bash", "command": "pytest"},
            {"type": "tool-input", "name": "Delete", "id": "delete", "path": "old"},
            "after",
        ]
        source = [
            message(1, "assistant", mixed),
            message(2, "user", [{"type": "tool-output", "name": "read_many_files", "id": "many"}]),
            message(3, "user", [{"type": "tool-output", "name": "Delete", "id": "delete"}]),
        ]

        pruned = prune_transcript.prune(source)
        diagnostics = analyze_transcript_json.build_report(
            [analyze_transcript_json.Message(1, "assistant", "assistant-response", mixed)], 8
        )

        self.assertEqual([item["original_index"] for item in pruned], [1], f"Got: {pruned!r}")
        self.assertEqual(
            pruned[0]["content"],
            [
                "before",
                '<Read path="a" id="many"/>',
                '<Read path="b" id="many"/>',
                mixed[2],
                '<Delete path="old" id="delete"/>',
                "after",
            ],
            f"Block order changed: {pruned!r}",
        )
        self.assertEqual(diagnostics["files"]["unique_affected_files"], 3, f"Got: {diagnostics!r}")

    def test_pruner_drops_explicit_empty_orphan_and_audits_it(self) -> None:
        source = [
            message(46, "user", ["keep"]),
            message(47, "assistant", [{"type": "tool-input", "name": "Edit", "id": "01CC"}]),
        ]
        with tempfile.TemporaryDirectory() as temporary_directory:
            source_path = pathlib.Path(temporary_directory, "transcript.json")
            source_path.write_text(json.dumps(source))
            result = subprocess.run(
                [
                    sys.executable,
                    str(pathlib.Path(prune_transcript.__file__)),
                    str(source_path),
                    "--drop-orphan-tool-id",
                    "01CC",
                ],
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(result.returncode, 0, f"Pruner failed: {result.stderr}")
        self.assertEqual(
            [item["original_index"] for item in json.loads(result.stdout)],
            [46],
            f"Orphan remained: {result.stdout}",
        )
        self.assertIn(
            "Dropped empty orphan tool calls: Edit '01CC' at message 47",
            result.stderr,
            f"Missing audit: {result.stderr}",
        )

    def test_pruner_explains_how_to_authorize_empty_orphan(self) -> None:
        source = [message(47, "assistant", [{"type": "tool-input", "name": "Edit", "id": "01CC"}])]
        with tempfile.TemporaryDirectory() as temporary_directory:
            source_path = pathlib.Path(temporary_directory, "transcript.json")
            source_path.write_text(json.dumps(source))
            result = subprocess.run(
                [sys.executable, str(pathlib.Path(prune_transcript.__file__)), str(source_path)],
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertNotEqual(result.returncode, 0, "Unapproved orphan was silently dropped")
        self.assertIn(
            "--drop-orphan-tool-id 01CC",
            result.stderr,
            f"Failure was not actionable: {result.stderr}",
        )

    def test_pruner_elides_repeated_skill_body_and_preserves_each_instruction(self) -> None:
        shared_skill = (
            '<skill name="instruct-another-ai" location="/skills/instruct-another-ai/SKILL.md">'
            "Shared delegation instructions"
            "</skill>"
        )
        changed_skill = (
            '<skill name="instruct-another-ai" location="/skills/instruct-another-ai/SKILL.md">'
            "Changed delegation instructions"
            "</skill>"
        )
        first_instruction = "\n\nplan the dev sandbox"
        second_instruction = "\n\nplan the Rapier integration"
        changed_instruction = "\n\nuse the changed instructions"
        source = [
            message(36, "user", [shared_skill + first_instruction]),
            message(195, "user", [shared_skill + second_instruction]),
            message(196, "user", [changed_skill + changed_instruction]),
        ]

        pruned = prune_transcript.prune(source)
        content_by_index = {
            item["original_index"]: item["content"]
            for item in pruned
        }

        self.assertEqual(
            content_by_index.get(36),
            [shared_skill, first_instruction],
            f"The first skill body and its instruction should become separate blocks. Got: {pruned!r}",
        )
        self.assertEqual(
            content_by_index.get(195),
            [second_instruction],
            f"Only the repeated body should be elided; its new instruction must survive. Got: {pruned!r}",
        )
        self.assertEqual(
            content_by_index.get(196),
            [changed_skill, changed_instruction],
            f"A nonidentical same-named skill body must remain intact. Got: {pruned!r}",
        )

    def test_review_view_elides_only_identical_skill_bodies(self) -> None:
        shared_skill = (
            '<skill name="in-html" location="/skills/in-html/SKILL.md">'
            "Shared decision-board instructions"
            "</skill>"
        )
        changed_skill = (
            '<skill name="in-html" location="/skills/in-html/SKILL.md">'
            "Changed decision-board instructions"
            "</skill>"
        )
        source = [
            message(94, "user", [shared_skill + "\n\nread the decision-board reference"]),
            message(100, "user", [shared_skill + "\n\nmake the decision board"]),
            message(101, "user", [changed_skill + "\n\nuse the changed skill"]),
        ]

        rendered = render_review_view.render(source)

        self.assertEqual(
            rendered.count(shared_skill),
            1,
            f"The identical skill body should be rendered once. Got:\n{rendered}",
        )
        self.assertIn(
            '<skill-body-elided duplicate-of="94"/>',
            rendered,
            f"The repeated invocation was not marked as elided. Got:\n{rendered}",
        )
        self.assertIn(
            changed_skill,
            rendered,
            f"A nonidentical same-named skill must remain intact. Got:\n{rendered}",
        )
        instructions = [
            "read the decision-board reference",
            "make the decision board",
            "use the changed skill",
        ]
        positions = [rendered.find(instruction) for instruction in instructions]
        self.assertTrue(
            all(position >= 0 for position in positions),
            f"Every user instruction must survive. Got positions {positions}:\n{rendered}",
        )
        self.assertEqual(
            positions,
            sorted(positions),
            f"User instructions must retain chronological order. Got:\n{rendered}",
        )

    def test_review_view_renders_compaction_as_a_boundary(self) -> None:
        summary = "This summary captures work done before the most recent messages."
        source = [
            message(78, "assistant", ["Before compaction"]),
            {
                "type": "compaction",
                "role": "user",
                "original_index": 79,
                "content": [summary],
            },
            message(80, "assistant", ["After compaction"]),
        ]

        rendered = render_review_view.render(source)

        expected_fragments = [
            "## Assistant [i=78]",
            "## Compaction boundary [i=79]",
            summary,
            "## Assistant [i=80]",
        ]
        positions = [rendered.find(fragment) for fragment in expected_fragments]
        self.assertTrue(
            all(position >= 0 for position in positions),
            f"The boundary and accessible summary must all be present. Got {positions}:\n{rendered}",
        )
        self.assertEqual(
            positions,
            sorted(positions),
            f"The compaction boundary must preserve chronology. Got:\n{rendered}",
        )
        self.assertNotIn(
            "## User [i=79]",
            rendered,
            f"A compaction must not masquerade as a user turn. Got:\n{rendered}",
        )

    def test_review_view_pairs_tools_by_id_and_flags_orphans(self) -> None:
        source = [
            message(1, "assistant", [
                {"type": "tool-input", "name": "Bash", "id": "call-a", "command": "echo A"},
                {"type": "tool-input", "name": "Bash", "id": "call-b", "command": "echo B"},
                {"type": "tool-input", "name": "Bash", "id": "input-only", "command": "echo orphan"},
            ]),
            message(2, "user", [{
                "type": "tool-output",
                "name": "Bash",
                "id": "call-b",
                "content": "B result arrived first",
            }]),
            message(3, "user", [{
                "type": "tool-output",
                "name": "Bash",
                "id": "call-a",
                "content": "A result arrived second",
            }]),
            message(4, "user", [{
                "type": "tool-output",
                "name": "Bash",
                "id": "output-only",
                "content": "stray result",
            }]),
        ]

        rendered = render_review_view.render(source)

        headings = [
            "### Tool event `call-a` — paired",
            "### Tool event `call-b` — paired",
            "### Tool event `input-only` — unmatched input",
            "### Tool event `output-only` — unmatched output",
        ]
        positions = [rendered.find(heading) for heading in headings]
        self.assertTrue(
            all(position >= 0 for position in positions),
            f"Every paired or unmatched event must be explicit. Got {positions}:\n{rendered}",
        )
        call_a_section = rendered[positions[0] : positions[1]]
        call_b_section = rendered[positions[1] : positions[2]]
        self.assertIn(
            "A result arrived second",
            call_a_section,
            f"call-a was not paired with its own result. Got:\n{call_a_section}",
        )
        self.assertNotIn(
            "B result arrived first",
            call_a_section,
            f"call-a was paired by proximity instead of ID. Got:\n{call_a_section}",
        )
        self.assertIn(
            "B result arrived first",
            call_b_section,
            f"call-b was not paired with its own result. Got:\n{call_b_section}",
        )
        self.assertEqual(
            rendered.count("A result arrived second"),
            1,
            f"A paired output must be rendered exactly once. Got:\n{rendered}",
        )
        self.assertEqual(
            rendered.count("B result arrived first"),
            1,
            f"A paired output must be rendered exactly once. Got:\n{rendered}",
        )

    def test_manifest_replaces_by_stable_index_and_builds_footer(self) -> None:
        source = [
            message(1, "user", ["Investigate"]),
            message(2, "assistant", [
                '<Read path="notes.md" id="read"/>',
                {"type": "tool-input", "name": "Bash", "id": "test", "command": "pytest"},
            ]),
            message(3, "user", [{"type": "tool-output", "name": "Bash", "id": "test"}]),
            message(4, "assistant", ["Done"]),
        ]
        source_bytes = (json.dumps(source) + "\n").encode()
        manifest: dict[str, object] = {
            "version": 1,
            "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
            "drop_messages": [3],
            "replace_messages": [{
                "original_index": 2,
                "expected_tool_ids": ["test"],
                "content": [
                    '<Read path="notes.md" id="read"/>',
                    '<tool-skeleton name="Bash" command="pytest" purpose="Validate" outcome="12 passed"/>',
                ],
            }],
            "affected_files_extra": ["artifact.csv"],
        }

        compacted = apply_compaction_plan.apply_plan(source_bytes, manifest)

        self.assertEqual([item["original_index"] for item in compacted], [1, 2, 4], f"Got: {compacted!r}")
        self.assertEqual(
            compacted[-1]["content"],
            ["Done", "<affected-files>\n- @notes.md\n- @artifact.csv\n</affected-files>"],
            f"Wrong footer: {compacted!r}",
        )

    def test_manifest_refuses_stale_source(self) -> None:
        with self.assertRaisesRegex(ValueError, "checksum mismatch"):
            apply_compaction_plan.apply_plan(
                b'[{"original_index":1,"content":["x"]}]',
                {"version": 1, "source_sha256": "0" * 64},
            )

    def test_generator_infers_drops_and_places_skeletons(self) -> None:
        source = [
            message(1, "user", ["Investigate the failure"]),
            message(2, "assistant", [
                "Running checks",
                {"type": "tool-input", "name": "Bash", "id": "aa", "command": "ls"},
                {"type": "tool-input", "name": "Bash", "id": "bb", "command": "pytest"},
                '<Read path="notes.md" id="cc"/>',
                '<Write path="/tmp/scratch.py" id="dd"/>',
            ]),
            message(3, "user", [{"type": "tool-output", "name": "Bash", "id": "bb", "content": "12 passed"}]),
            message(4, "assistant", ["Now I'll wrap up: murmur", "All fixed"]),
        ]
        source_bytes = json.dumps(source).encode()
        decisions = generate_compaction_plan.parse_decisions({
            "skeletons": [{
                "original_index": 2,
                "tool_id": "bb",
                "command": "pytest",
                "purpose": "Validate",
                "outcome": "12 passed",
            }],
            "drop_text_blocks": [{"original_index": 4, "contains": "murmur"}],
            "scratchpad_paths": ["/tmp/scratch.py"],
            "opaque_artifacts": ["artifact.csv"],
        })

        plan, audit = generate_compaction_plan.generate_plan(source_bytes, decisions)
        compacted = apply_compaction_plan.apply_plan(source_bytes, plan)

        self.assertEqual(plan["drop_messages"], [3], f"Got: {plan!r}")
        replacement_by_index = {item["original_index"]: item for item in plan["replace_messages"]}
        self.assertEqual(sorted(replacement_by_index), [2, 4], f"Got: {plan!r}")
        self.assertEqual(replacement_by_index[2]["expected_tool_ids"], ["aa", "bb"], f"Got: {plan!r}")
        self.assertEqual(
            replacement_by_index[2]["content"],
            [
                "Running checks",
                '<tool-skeleton name="Bash" command="pytest" purpose="Validate" outcome="12 passed"/>',
                '<Read path="notes.md" id="cc"/>',
            ],
            f"Got: {plan!r}",
        )
        self.assertEqual(replacement_by_index[4]["content"], ["All fixed"], f"Got: {plan!r}")
        self.assertEqual(plan["affected_files_extra"], ["notes.md", "artifact.csv"], f"Got: {plan!r}")
        self.assertEqual(
            compacted[-1]["content"][-1],
            "<affected-files>\n- @notes.md\n- @artifact.csv\n</affected-files>",
            f"Got: {compacted!r}",
        )
        self.assertTrue(any("skeleton anchors: 2" in line for line in audit), f"Got: {audit!r}")

    def test_generator_drops_one_file_reference_by_index_operation_and_path(self) -> None:
        main_path = "/Users/giladbarnea/dev/tractor-ami/main.js"
        terrain_path = "/Users/giladbarnea/dev/tractor-ami/src/terrain.js"
        source = [
            message(6, "assistant", [
                f'<Read path="{main_path}" id="0199"/>',
                f'<Read path="{terrain_path}" id="01Au"/>',
            ]),
            message(12, "assistant", [f'<Read path="{main_path}" id="01NF"/>']),
            message(35, "assistant", ["Done"]),
        ]
        source_bytes = json.dumps(source).encode()
        decisions = generate_compaction_plan.parse_decisions({
            "drop_file_references": [{
                "original_index": 6,
                "operation": "Read",
                "path": main_path,
            }],
        })

        plan, audit = generate_compaction_plan.generate_plan(source_bytes, decisions)
        compacted = apply_compaction_plan.apply_plan(source_bytes, plan)

        content_by_index = {
            item["original_index"]: item["content"]
            for item in compacted
        }
        self.assertEqual(
            content_by_index.get(6),
            [f'<Read path="{terrain_path}" id="01Au"/>'],
            f"Only the selected stale read should be removed. Got: {compacted!r}",
        )
        self.assertEqual(
            content_by_index.get(12),
            [f'<Read path="{main_path}" id="01NF"/>'],
            f"A later read of the same path must survive. Got: {compacted!r}",
        )
        self.assertTrue(
            any("file reference drops: 6 Read" in line for line in audit),
            f"The first-class decision must be audited. Got: {audit!r}",
        )

    def test_generator_requires_file_reference_decision_to_match_exactly_once(self) -> None:
        path = "/Users/giladbarnea/dev/tractor-ami/main.js"
        decision = generate_compaction_plan.parse_decisions({
            "drop_file_references": [{
                "original_index": 6,
                "operation": "Read",
                "path": path,
            }],
        })
        cases = {
            "missing": [
                message(6, "assistant", ['<Read path="different.js" id="read"/>']),
                message(35, "assistant", ["Done"]),
            ],
            "ambiguous": [
                message(6, "assistant", [
                    f'<Read path="{path}" id="first"/>',
                    f'<Read path="{path}" id="second"/>',
                ]),
                message(35, "assistant", ["Done"]),
            ],
        }

        for case, source in cases.items():
            with self.subTest(case=case):
                with self.assertRaisesRegex(ValueError, "must match exactly one"):
                    generate_compaction_plan.generate_plan(
                        json.dumps(source).encode(),
                        decision,
                    )

    def test_generator_and_apply_deduplicate_file_aliases(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            real_directory = pathlib.Path(temporary_directory, "real")
            real_directory.mkdir()
            alias_directory = pathlib.Path(temporary_directory, "alias")
            alias_directory.symlink_to(real_directory, target_is_directory=True)
            first_path = str(real_directory / "board.json")
            aliased_path = str(alias_directory / "board.json")
            source = [
                message(1, "assistant", [f'<Write path="{first_path}" id="write"/>']),
                message(2, "assistant", [f'<Read path="{aliased_path}" id="read"/>']),
                message(3, "assistant", ["Done"]),
            ]
            source_bytes = json.dumps(source).encode()

            plan, _ = generate_compaction_plan.generate_plan(
                source_bytes, generate_compaction_plan.parse_decisions({})
            )
            compacted = apply_compaction_plan.apply_plan(source_bytes, plan)

            self.assertEqual(
                compacted[-1]["content"][-1],
                f"<affected-files>\n- @{first_path}\n</affected-files>",
                f"Expected filesystem aliases to produce one footer entry. Got: {compacted!r}",
            )

    def test_generator_collects_registered_artifact_paths(self) -> None:
        source = [
            message(1, "assistant", [{"type": "tool-input", "name": "generate_visual", "id": "vv", "command": "chart"}]),
            message(2, "user", [{
                "type": "tool-output",
                "name": "generate_visual",
                "id": "vv",
                "content": [{"type": "text", "text": "Wrote /Users/g/.agent/lumen/experiment.html and opened it"}],
            }]),
            message(3, "assistant", ["Done"]),
        ]
        source_bytes = json.dumps(source).encode()
        decisions = generate_compaction_plan.parse_decisions({})

        plan, _ = generate_compaction_plan.generate_plan(source_bytes, decisions)

        self.assertEqual(plan["drop_messages"], [1, 2], f"Got: {plan!r}")
        self.assertEqual(
            plan["affected_files_extra"], ["/Users/g/.agent/lumen/experiment.html"], f"Got: {plan!r}"
        )

    def test_generator_fails_loudly(self) -> None:
        two_inputs = [
            {"type": "tool-input", "name": "Bash", "id": "aa", "command": "ls"},
            {"type": "tool-input", "name": "Bash", "id": "bb", "command": "pytest"},
        ]
        source_bytes = json.dumps([message(1, "assistant", two_inputs), message(2, "assistant", ["ok"])]).encode()
        skeleton = {"command": "c", "purpose": "p", "outcome": "o"}

        ambiguous = generate_compaction_plan.parse_decisions(
            {"skeletons": [{"original_index": 1, **skeleton}]}
        )
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            generate_compaction_plan.generate_plan(source_bytes, ambiguous)

        unknown_scratchpad = generate_compaction_plan.parse_decisions(
            {"scratchpad_paths": ["/never/touched.py"], "skeletons": [{"original_index": 1, "tool_id": "bb", **skeleton}]}
        )
        with self.assertRaisesRegex(ValueError, "never referenced"):
            generate_compaction_plan.generate_plan(source_bytes, unknown_scratchpad)

        artifact_without_path = json.dumps([
            message(1, "user", [{"type": "tool-output", "name": "generate_visual", "id": "vv", "content": "opened in browser"}]),
            message(2, "assistant", ["ok"]),
        ]).encode()
        with self.assertRaisesRegex(ValueError, "no extractable path"):
            generate_compaction_plan.generate_plan(
                artifact_without_path, generate_compaction_plan.parse_decisions({})
            )

    def test_markremove_targets_original_index(self) -> None:
        messages = [message(10, "user", ["keep"]), message(20, "user", ["remove this"])]
        markremove.mark_message(messages, 20, "remove this")
        self.assertNotIn("remove", messages[0], f"Wrong message marked: {messages!r}")
        self.assertIs(messages[1].get("remove"), True, f"Target not marked: {messages!r}")


if __name__ == "__main__":
    unittest.main()
