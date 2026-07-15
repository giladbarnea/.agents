#!/usr/bin/env -S uv run
# /// script
# requires-python = "==3.12.*"
# dependencies = ["pyyaml"]
# ///

import hashlib
import json
import unittest

import analyze_transcript_json
import apply_compaction_plan
import markremove
import prune_transcript


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

    def test_markremove_targets_original_index(self) -> None:
        messages = [message(10, "user", ["keep"]), message(20, "user", ["remove this"])]
        markremove.mark_message(messages, 20, "remove this")
        self.assertNotIn("remove", messages[0], f"Wrong message marked: {messages!r}")
        self.assertIs(messages[1].get("remove"), True, f"Target not marked: {messages!r}")


if __name__ == "__main__":
    unittest.main()
