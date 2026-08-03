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
import compile_annotations
import generate_compaction_plan
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
    def test_annotation_compiler_expands_ranges_over_existing_messages(self) -> None:
        source = [
            message(10, "user", ["keep"]),
            message(20, "assistant", ["drop directly"]),
            message(40, "assistant", ["drop through range"]),
            message(70, "assistant", ["keep too"]),
        ]
        source_bytes = json.dumps(source).encode()

        decisions = compile_annotations.compile_annotations(
            source_bytes,
            {
                "drop": {
                    "indices": [20],
                    "ranges": [[30, 60]],
                },
                "skeletons": [],
            },
        )

        self.assertEqual(
            decisions.get("drop_texts"),
            [20, 40],
            f"Drop declarations were not compiled against existing stable indices: {decisions!r}",
        )
        self.assertEqual(
            decisions.get("source_sha256"),
            hashlib.sha256(source_bytes).hexdigest(),
            f"Compiled decisions were not bound to their reviewed source: {decisions!r}",
        )
        generate_compaction_plan.parse_decisions(decisions)

    def test_compiled_annotations_refuse_a_different_source(self) -> None:
        source_bytes = json.dumps(
            [message(10, "user", ["reviewed"]), message(20, "assistant", ["drop"])]
        ).encode()
        decisions = compile_annotations.compile_annotations(
            source_bytes,
            {"drop": {"indices": [20]}},
        )
        changed_source_bytes = json.dumps(
            [message(10, "user", ["changed"]), message(20, "assistant", ["drop"])]
        ).encode()

        with self.assertRaisesRegex(ValueError, "annotation source checksum mismatch"):
            generate_compaction_plan.generate_plan(
                changed_source_bytes,
                generate_compaction_plan.parse_decisions(decisions),
            )

    def test_annotation_cli_produces_decisions_accepted_by_the_existing_pipeline(self) -> None:
        source = [
            message(10, "user", ["Investigate"]),
            message(20, "assistant", ["Discard this"]),
            message(
                40,
                "assistant",
                [{"type": "tool-input", "name": "Bash", "id": "test", "command": "pytest"}],
            ),
            message(
                41,
                "user",
                [{"type": "tool-output", "name": "Bash", "id": "test", "content": "12 passed"}],
            ),
            message(70, "assistant", ["Done"]),
        ]
        source_bytes = json.dumps(source).encode()
        annotations = """\
drop:
  indices: [20]
skeletons:
  - original_index: 40
    command: pytest
    purpose: Validate
    outcome: 12 passed
"""
        with tempfile.TemporaryDirectory() as temporary_directory:
            source_path = pathlib.Path(temporary_directory, "pruned.json")
            annotations_path = pathlib.Path(temporary_directory, "annotations.yaml")
            source_path.write_bytes(source_bytes)
            annotations_path.write_text(annotations)
            result = subprocess.run(
                [
                    sys.executable,
                    str(pathlib.Path(compile_annotations.__file__)),
                    str(source_path),
                    str(annotations_path),
                ],
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(result.returncode, 0, f"Compiler failed: {result.stderr}")
        raw_decisions = json.loads(result.stdout)
        decisions = generate_compaction_plan.parse_decisions(raw_decisions)
        plan, _ = generate_compaction_plan.generate_plan(source_bytes, decisions)
        compacted = apply_compaction_plan.apply_plan(source_bytes, plan)

        self.assertEqual(
            [item["original_index"] for item in compacted],
            [10, 40, 70],
            f"Compiled annotations did not drive the existing pipeline: {compacted!r}",
        )
        self.assertEqual(
            compacted[1]["content"],
            [
                '<tool-skeleton name="Bash" command="pytest" purpose="Validate" outcome="12 passed"/>'
            ],
            f"Skeleton annotations were not preserved: {compacted!r}",
        )

    def test_pruner_handles_multi_read_delete_and_mixed_order(self) -> None:
        mixed = [
            "before",
            {
                "type": "tool-input",
                "name": "read_many_files",
                "id": "many",
                "paths": ["a", "b"],
                "native_tool_call_id": "call_many-full",
                "native_content_index": 1,
            },
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
                '<Read path="a" id="many" native_tool_call_id="call_many-full" native_content_index="1"/>',
                '<Read path="b" id="many" native_tool_call_id="call_many-full" native_content_index="1"/>',
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
            message(47, "assistant", [{
                "type": "tool-input",
                "name": "Edit",
                "id": "01CC",
                "native_tool_call_id": "call_01CC-full",
                "native_content_index": 0,
            }]),
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

    def test_manifest_refuses_a_stale_skeleton_tool_id(self) -> None:
        skeleton = (
            '<tool-skeleton name="Bash" command="pytest" purpose="Validate" '
            'outcome="12 passed"/>'
        )
        source = [message(2, "assistant", [{
            "type": "tool-input",
            "name": "Bash",
            "id": "01AB",
            "native_tool_call_id": "toolu_current-full",
            "native_content_index": 0,
            "command": "pytest",
        }])]
        source_bytes = json.dumps(source).encode()
        manifest = {
            "version": 1,
            "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
            "drop_messages": [],
            "replace_messages": [{
                "original_index": 2,
                "expected_tool_ids": ["01AB"],
                "content": [skeleton],
                "tool_skeletons": [{
                    "tool_id": "toolu_stale-full",
                    "content": skeleton,
                }],
            }],
            "affected_files_extra": [],
        }

        with self.assertRaisesRegex(ValueError, "tool_skeleton IDs do not match source"):
            apply_compaction_plan.apply_plan(source_bytes, manifest)

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

    def test_annotation_to_native_plan_maps_same_name_skeletons_by_full_tool_id(self) -> None:
        source = [
            message(8, "assistant", [
                {
                    "type": "tool-input",
                    "name": "Bash",
                    "id": "01AA",
                    "native_tool_call_id": "toolu_first-full",
                    "native_content_index": 1,
                    "command": "same command",
                },
                {
                    "type": "tool-input",
                    "name": "Bash",
                    "id": "01BB",
                    "native_tool_call_id": "toolu_second-full",
                    "native_content_index": 2,
                    "command": "same command",
                },
            ]),
            message(9, "user", [{
                "type": "tool-output",
                "name": "Bash",
                "id": "01AA",
                "native_tool_call_id": "toolu_first-full",
                "content": "first result",
            }]),
            message(10, "user", [{
                "type": "tool-output",
                "name": "Bash",
                "id": "01BB",
                "native_tool_call_id": "toolu_second-full",
                "content": "second result",
            }]),
            message(11, "assistant", ["Done"]),
        ]
        source[0]["native_entry_id"] = "assistant-tools"
        source[1]["native_entry_id"] = "result-first"
        source[2]["native_entry_id"] = "result-second"
        source[3]["native_entry_id"] = "done"
        source_bytes = json.dumps(source).encode()
        decisions_raw = compile_annotations.compile_annotations(
            source_bytes,
            {
                "skeletons": [
                    {
                        "original_index": 8,
                        "tool_id": "toolu_second-full",
                        "command": "same command",
                        "purpose": "Keep the second result",
                        "outcome": "second result",
                    },
                    {
                        "original_index": 8,
                        "tool_id": "toolu_first-full",
                        "command": "same command",
                        "purpose": "Keep the first result",
                        "outcome": "first result",
                    },
                ],
            },
        )
        plan, _ = generate_compaction_plan.generate_plan(
            source_bytes,
            generate_compaction_plan.parse_decisions(decisions_raw),
        )
        replacement = plan["replace_messages"][0]
        first_skeleton, second_skeleton = replacement["content"]

        self.assertEqual(
            replacement.get("tool_skeletons"),
            [
                {"tool_id": "toolu_first-full", "content": first_skeleton},
                {"tool_id": "toolu_second-full", "content": second_skeleton},
            ],
            f"The plan lost each skeleton's full tool ID: {replacement!r}",
        )

        native_lines = [
            {"type": "session", "version": 3, "id": "target-session", "timestamp": "now", "cwd": "/tmp"},
            {
                "type": "message",
                "id": "assistant-tools",
                "parentId": None,
                "timestamp": "now",
                "message": {
                    "role": "assistant",
                    "content": [
                        {"type": "thinking", "thinking": "Keep this"},
                        {"type": "toolCall", "id": "toolu_first-full", "name": "Bash", "arguments": {"command": "same command"}},
                        {"type": "toolCall", "id": "toolu_second-full", "name": "Bash", "arguments": {"command": "same command"}},
                    ],
                },
            },
            {
                "type": "message",
                "id": "result-first",
                "parentId": "assistant-tools",
                "timestamp": "now",
                "message": {
                    "role": "toolResult",
                    "toolCallId": "toolu_first-full",
                    "toolName": "Bash",
                    "content": [{"type": "text", "text": "first result"}],
                },
            },
            {
                "type": "message",
                "id": "result-second",
                "parentId": "result-first",
                "timestamp": "now",
                "message": {
                    "role": "toolResult",
                    "toolCallId": "toolu_second-full",
                    "toolName": "Bash",
                    "content": [{"type": "text", "text": "second result"}],
                },
            },
            {
                "type": "message",
                "id": "done",
                "parentId": "result-second",
                "timestamp": "now",
                "message": {"role": "assistant", "content": [{"type": "text", "text": "Done"}]},
            },
        ]

        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = pathlib.Path(temporary_directory)
            source_path = directory / "pruned.json"
            plan_path = directory / "compaction-plan.json"
            session_path = directory / "target.jsonl"
            source_path.write_bytes(source_bytes)
            plan_path.write_text(json.dumps(plan))
            session_path.write_text("".join(json.dumps(line) + "\n" for line in native_lines))
            result = subprocess.run(
                [
                    sys.executable,
                    str(pathlib.Path(__file__).with_name("transfer_to_pi_session.py")),
                    str(source_path),
                    str(plan_path),
                    str(session_path),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            output = [json.loads(line) for line in session_path.read_text().splitlines()]

        self.assertEqual(result.returncode, 0, f"Exact skeleton mapping failed: {result.stderr}")
        self.assertEqual(
            output[1]["message"]["content"],
            [
                {"type": "thinking", "thinking": "Keep this"},
                {"type": "text", "text": first_skeleton},
                {"type": "text", "text": second_skeleton},
            ],
            f"Same-name skeletons mapped to the wrong full tool IDs: {output!r}",
        )

    def test_native_plan_application_preserves_thinking_and_replaces_tools_atomically(self) -> None:
        source = [
            message(10, "assistant", [
                "Before tools",
                {"type": "tool-input", "name": "Bash", "id": "01AB", "command": "false", "native_tool_call_id": "toolu_01AB-full", "native_content_index": 2},
                {"type": "tool-input", "name": "Bash", "id": "01CD", "command": "pytest", "native_tool_call_id": "toolu_01CD-full", "native_content_index": 4},
                "After tools",
            ]),
            message(11, "user", [
                {"type": "tool-output", "name": "Bash", "id": "01AB", "native_tool_call_id": "toolu_01AB-full", "content": "failed"}
            ]),
            message(12, "user", [
                {"type": "tool-output", "name": "Bash", "id": "01CD", "native_tool_call_id": "toolu_01CD-full", "content": "12 passed"}
            ]),
            message(13, "assistant", ["Done"]),
        ]
        source[0]["native_entry_id"] = "entry-a"
        source[1]["native_entry_id"] = "entry-b"
        source[2]["native_entry_id"] = "entry-c"
        source_bytes = json.dumps(source).encode()
        skeleton = (
            '<tool-skeleton name="Bash" command="pytest" purpose="Validate" '
            'outcome="12 passed"/>'
        )
        plan = {
            "version": 1,
            "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
            "drop_messages": [11, 12],
            "replace_messages": [{
                "original_index": 10,
                "expected_tool_ids": ["01AB", "01CD"],
                "content": ["Before tools", skeleton, "After tools"],
                "tool_skeletons": [
                    {"tool_id": "toolu_01CD-full", "content": skeleton}
                ],
            }],
            "affected_files_extra": [],
        }
        native_lines = [
            {"type": "session", "version": 3, "id": "target-session", "timestamp": "now", "cwd": "/tmp"},
            {
                "type": "message",
                "id": "entry-a",
                "parentId": None,
                "timestamp": "now",
                "message": {
                    "role": "assistant",
                    "content": [
                        {"type": "thinking", "thinking": "Keep this reasoning"},
                        {"type": "text", "text": "Before tools"},
                        {"type": "toolCall", "id": "toolu_01AB-full", "name": "Bash", "arguments": {"command": "false"}},
                        {"type": "thinking", "thinking": "Keep this too"},
                        {"type": "toolCall", "id": "toolu_01CD-full", "name": "Bash", "arguments": {"command": "pytest"}},
                        {"type": "text", "text": "After tools"},
                    ],
                },
            },
            {
                "type": "message",
                "id": "entry-b",
                "parentId": "entry-a",
                "timestamp": "now",
                "message": {
                    "role": "toolResult",
                    "toolCallId": "toolu_01AB-full",
                    "toolName": "Bash",
                    "content": [{"type": "text", "text": "failed"}],
                },
            },
            {
                "type": "message",
                "id": "entry-c",
                "parentId": "entry-b",
                "timestamp": "now",
                "message": {
                    "role": "toolResult",
                    "toolCallId": "toolu_01CD-full",
                    "toolName": "Bash",
                    "content": [{"type": "text", "text": "12 passed"}],
                },
            },
            {
                "type": "message",
                "id": "entry-d",
                "parentId": "entry-c",
                "timestamp": "now",
                "message": {"role": "assistant", "content": [{"type": "text", "text": "Done"}]},
            },
        ]

        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = pathlib.Path(temporary_directory)
            source_path = directory / "pruned.json"
            plan_path = directory / "compaction-plan.json"
            session_path = directory / "target.jsonl"
            source_path.write_bytes(source_bytes)
            plan_path.write_text(json.dumps(plan))
            original_session_bytes = b"".join(
                json.dumps(line).encode() + b"\n" for line in native_lines
            )
            session_path.write_bytes(original_session_bytes)

            result = subprocess.run(
                [
                    sys.executable,
                    str(pathlib.Path(__file__).with_name("transfer_to_pi_session.py")),
                    str(source_path),
                    str(plan_path),
                    str(session_path),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            output = [json.loads(line) for line in session_path.read_text().splitlines()]
            backups = list(directory.glob("target.jsonl.backup-*"))
            backup_bytes = backups[0].read_bytes() if len(backups) == 1 else None
            goldload = subprocess.run(
                [
                    "node",
                    str(pathlib.Path(__file__).with_name("pi-goldload.mjs")),
                    str(session_path),
                ],
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(result.returncode, 0, f"Native plan application failed: {result.stderr}")
        self.assertEqual(goldload.returncode, 0, f"Pi could not load the output: {goldload.stderr}")
        self.assertIn("PASS=true", goldload.stdout, f"Pi did not reach the full output chain: {goldload.stdout}")
        self.assertEqual(len(backups), 1, f"Expected one safety backup. Got: {backups!r}")
        self.assertEqual(backup_bytes, original_session_bytes, "The safety backup changed")
        self.assertEqual(
            [line.get("id") for line in output[1:]],
            ["entry-a", "entry-d"],
            f"Paired tool results survived: {output!r}",
        )
        content = output[1]["message"]["content"]
        self.assertEqual(
            content,
            [
                {"type": "thinking", "thinking": "Keep this reasoning"},
                {"type": "text", "text": "Before tools"},
                {"type": "thinking", "thinking": "Keep this too"},
                {"type": "text", "text": skeleton},
                {"type": "text", "text": "After tools"},
            ],
            f"Thinking moved or the skeleton was placed at the wrong tool block: {content!r}",
        )
        self.assertFalse(
            any(block.get("type") == "toolCall" for block in content),
            f"Raw tool calls survived: {content!r}",
        )
        self.assertEqual(
            output[2].get("parentId"),
            "entry-a",
            f"The survivor chain was not repaired: {output!r}",
        )

    def test_native_plan_application_applies_text_replacements_and_message_drops(self) -> None:
        source = [
            message(20, "assistant", ["Keep this", "Drop this murmur"]),
            message(21, "user", ["Drop this whole turn"]),
            message(22, "assistant", ["Done"]),
        ]
        source[0]["native_entry_id"] = "entry-a"
        source[1]["native_entry_id"] = "entry-b"
        source[2]["native_entry_id"] = "entry-c"
        source_bytes = json.dumps(source).encode()
        plan = {
            "version": 1,
            "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
            "drop_messages": [21],
            "replace_messages": [{
                "original_index": 20,
                "expected_tool_ids": [],
                "content": ["Keep this"],
            }],
            "affected_files_extra": [],
        }
        native_lines = [
            {"type": "session", "version": 3, "id": "target-session", "timestamp": "now", "cwd": "/tmp"},
            {
                "type": "message",
                "id": "entry-a",
                "parentId": None,
                "timestamp": "now",
                "message": {
                    "role": "assistant",
                    "content": [
                        {"type": "thinking", "thinking": "Preserve me"},
                        {"type": "text", "text": "Keep this"},
                        {"type": "text", "text": "Drop this murmur"},
                    ],
                },
            },
            {
                "type": "message",
                "id": "entry-b",
                "parentId": "entry-a",
                "timestamp": "now",
                "message": {"role": "user", "content": [{"type": "text", "text": "Drop this whole turn"}]},
            },
            {
                "type": "message",
                "id": "entry-c",
                "parentId": "entry-b",
                "timestamp": "now",
                "message": {"role": "assistant", "content": [{"type": "text", "text": "Done"}]},
            },
        ]

        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = pathlib.Path(temporary_directory)
            source_path = directory / "pruned.json"
            plan_path = directory / "compaction-plan.json"
            session_path = directory / "target.jsonl"
            source_path.write_bytes(source_bytes)
            plan_path.write_text(json.dumps(plan))
            session_path.write_text(
                "".join(json.dumps(line) + "\n" for line in native_lines)
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(pathlib.Path(__file__).with_name("transfer_to_pi_session.py")),
                    str(source_path),
                    str(plan_path),
                    str(session_path),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            output = [json.loads(line) for line in session_path.read_text().splitlines()]

        self.assertEqual(result.returncode, 0, f"Native text application failed: {result.stderr}")
        self.assertEqual(
            [line.get("id") for line in output[1:]],
            ["entry-a", "entry-c"],
            f"The dropped user message survived: {output!r}",
        )
        self.assertEqual(
            output[1]["message"]["content"],
            [
                {"type": "thinking", "thinking": "Preserve me"},
                {"type": "text", "text": "Keep this"},
            ],
            f"The text replacement did not preserve adjacent thinking: {output!r}",
        )
        self.assertEqual(
            output[2].get("parentId"),
            "entry-a",
            f"The dropped message was not spliced from the chain: {output!r}",
        )

    def test_native_plan_application_replaces_multi_file_read_from_pruned_references(self) -> None:
        first_reference = '<Read path="a.md" id="01RF" native_tool_call_id="toolu_01RF-complete" native_content_index="1"/>'
        second_reference = '<Read path="b.md" id="01RF" native_tool_call_id="toolu_01RF-complete" native_content_index="1"/>'
        source = [
            message(30, "assistant", [first_reference, second_reference]),
            message(31, "assistant", ["Done"]),
        ]
        source[0]["native_entry_id"] = "entry-a"
        source[1]["native_entry_id"] = "entry-c"
        source_bytes = json.dumps(source).encode()
        plan = {
            "version": 1,
            "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
            "drop_messages": [],
            "replace_messages": [{
                "original_index": 30,
                "expected_tool_ids": [],
                "content": [second_reference],
            }],
            "affected_files_extra": ["b.md"],
        }
        native_lines = [
            {"type": "session", "version": 3, "id": "target-session", "timestamp": "now", "cwd": "/tmp"},
            {
                "type": "message",
                "id": "entry-a",
                "parentId": None,
                "timestamp": "now",
                "message": {
                    "role": "assistant",
                    "content": [
                        {"type": "thinking", "thinking": "Read both files"},
                        {
                            "type": "toolCall",
                            "id": "toolu_01RF-complete",
                            "name": "read_many_files",
                            "arguments": {"paths": ["a.md", "b.md"]},
                        },
                    ],
                },
            },
            {
                "type": "message",
                "id": "entry-b",
                "parentId": "entry-a",
                "timestamp": "now",
                "message": {
                    "role": "toolResult",
                    "toolCallId": "toolu_01RF-complete",
                    "toolName": "read_many_files",
                    "content": [{"type": "text", "text": "large file contents"}],
                },
            },
            {
                "type": "message",
                "id": "entry-c",
                "parentId": "entry-b",
                "timestamp": "now",
                "message": {"role": "assistant", "content": [{"type": "text", "text": "Done"}]},
            },
        ]

        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = pathlib.Path(temporary_directory)
            source_path = directory / "pruned.json"
            plan_path = directory / "compaction-plan.json"
            session_path = directory / "target.jsonl"
            source_path.write_bytes(source_bytes)
            plan_path.write_text(json.dumps(plan))
            session_path.write_text(
                "".join(json.dumps(line) + "\n" for line in native_lines)
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(pathlib.Path(__file__).with_name("transfer_to_pi_session.py")),
                    str(source_path),
                    str(plan_path),
                    str(session_path),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            output = [json.loads(line) for line in session_path.read_text().splitlines()]

        self.assertEqual(result.returncode, 0, f"Native file-reference application failed: {result.stderr}")
        self.assertEqual(
            [line.get("id") for line in output[1:]],
            ["entry-a", "entry-c"],
            f"The read result survived its replaced call: {output!r}",
        )
        self.assertEqual(
            output[1]["message"]["content"],
            [
                {"type": "thinking", "thinking": "Read both files"},
                {"type": "text", "text": second_reference},
            ],
            f"The selected file reference was not applied at block level: {output!r}",
        )

    def test_native_plan_application_maps_repeated_short_ids_by_full_id(self) -> None:
        first_skeleton = '<tool-skeleton name="Bash" command="first" purpose="Check first" outcome="first result"/>'
        second_skeleton = '<tool-skeleton name="Bash" command="second" purpose="Check second" outcome="second result"/>'
        source = [
            message(40, "assistant", [{"type": "tool-input", "name": "Bash", "id": "01CN", "native_tool_call_id": "toolu_01CN-first", "native_content_index": 0, "command": "first"}]),
            message(41, "user", [{"type": "tool-output", "name": "Bash", "id": "01CN", "native_tool_call_id": "toolu_01CN-first", "content": "first result"}]),
            message(42, "assistant", [{"type": "tool-input", "name": "Bash", "id": "01CN", "native_tool_call_id": "toolu_01CN-second", "native_content_index": 0, "command": "second"}]),
            message(43, "user", [{"type": "tool-output", "name": "Bash", "id": "01CN", "native_tool_call_id": "toolu_01CN-second", "content": "second result"}]),
            message(44, "assistant", ["Done"]),
        ]
        source[0]["native_entry_id"] = "assistant-first"
        source[1]["native_entry_id"] = "result-first"
        source[2]["native_entry_id"] = "assistant-second"
        source[3]["native_entry_id"] = "result-second"
        source[4]["native_entry_id"] = "done"
        source_bytes = json.dumps(source).encode()
        plan = {
            "version": 1,
            "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
            "drop_messages": [41, 43],
            "replace_messages": [
                {"original_index": 40, "expected_tool_ids": ["01CN"], "content": [first_skeleton]},
                {"original_index": 42, "expected_tool_ids": ["01CN"], "content": [second_skeleton]},
            ],
            "affected_files_extra": [],
        }
        native_lines: list[dict[str, object]] = [
            {"type": "session", "version": 3, "id": "target-session", "timestamp": "now", "cwd": "/tmp"},
        ]
        parent_identifier: str | None = None
        for suffix, command, result_text in (
            ("first", "first", "first result"),
            ("second", "second", "second result"),
        ):
            assistant_identifier = f"assistant-{suffix}"
            result_identifier = f"result-{suffix}"
            full_call_id = f"toolu_01CN-{suffix}"
            native_lines.extend([
                {
                    "type": "message",
                    "id": assistant_identifier,
                    "parentId": parent_identifier,
                    "timestamp": "now",
                    "message": {
                        "role": "assistant",
                        "content": [{"type": "toolCall", "id": full_call_id, "name": "Bash", "arguments": {"command": command}}],
                    },
                },
                {
                    "type": "message",
                    "id": result_identifier,
                    "parentId": assistant_identifier,
                    "timestamp": "now",
                    "message": {
                        "role": "toolResult",
                        "toolCallId": full_call_id,
                        "toolName": "Bash",
                        "content": [{"type": "text", "text": result_text}],
                    },
                },
            ])
            parent_identifier = result_identifier
        native_lines.append({
            "type": "message",
            "id": "done",
            "parentId": parent_identifier,
            "timestamp": "now",
            "message": {"role": "assistant", "content": [{"type": "text", "text": "Done"}]},
        })

        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = pathlib.Path(temporary_directory)
            source_path = directory / "pruned.json"
            plan_path = directory / "compaction-plan.json"
            session_path = directory / "target.jsonl"
            source_path.write_bytes(source_bytes)
            plan_path.write_text(json.dumps(plan))
            session_path.write_text("".join(json.dumps(line) + "\n" for line in native_lines))
            result = subprocess.run(
                [
                    sys.executable,
                    str(pathlib.Path(__file__).with_name("transfer_to_pi_session.py")),
                    str(source_path),
                    str(plan_path),
                    str(session_path),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            output = [json.loads(line) for line in session_path.read_text().splitlines()]

        self.assertEqual(result.returncode, 0, f"Repeated short IDs were not resolved: {result.stderr}")
        self.assertEqual(
            [line.get("id") for line in output[1:]],
            ["assistant-first", "assistant-second", "done"],
            f"Repeated-ID tool results survived: {output!r}",
        )
        self.assertEqual(
            [output[1]["message"]["content"][0]["text"], output[2]["message"]["content"][0]["text"]],
            [first_skeleton, second_skeleton],
            f"The skeletons crossed repeated short IDs: {output!r}",
        )

    def test_native_plan_application_leaves_target_untouched_when_plan_is_stale(self) -> None:
        source_bytes = json.dumps([message(50, "assistant", ["Done"])]).encode()
        stale_plan = {
            "version": 1,
            "source_sha256": "0" * 64,
            "drop_messages": [],
            "replace_messages": [],
            "affected_files_extra": [],
        }
        native_lines = [
            {"type": "session", "version": 3, "id": "target-session", "timestamp": "now", "cwd": "/tmp"},
            {
                "type": "message",
                "id": "entry-a",
                "parentId": None,
                "timestamp": "now",
                "message": {"role": "assistant", "content": [{"type": "text", "text": "Done"}]},
            },
        ]
        original_session_bytes = b"".join(
            json.dumps(line).encode() + b"\n" for line in native_lines
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = pathlib.Path(temporary_directory)
            source_path = directory / "pruned.json"
            plan_path = directory / "compaction-plan.json"
            session_path = directory / "target.jsonl"
            source_path.write_bytes(source_bytes)
            plan_path.write_text(json.dumps(stale_plan))
            session_path.write_bytes(original_session_bytes)
            result = subprocess.run(
                [
                    sys.executable,
                    str(pathlib.Path(__file__).with_name("transfer_to_pi_session.py")),
                    str(source_path),
                    str(plan_path),
                    str(session_path),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            final_session_bytes = session_path.read_bytes()
            backups = list(directory.glob("target.jsonl.backup-*"))

        self.assertNotEqual(result.returncode, 0, "A stale plan unexpectedly succeeded")
        self.assertIn("checksum mismatch", result.stderr, f"The failure was not specific: {result.stderr}")
        self.assertEqual(
            final_session_bytes,
            original_session_bytes,
            "A stale plan changed the native target",
        )
        self.assertFalse(backups, f"Validation failure created a misleading backup: {backups!r}")

if __name__ == "__main__":
    unittest.main()
