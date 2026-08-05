#!/usr/bin/env -S uv run
# /// script
# requires-python = "==3.12.*"
# dependencies = ["pyyaml"]
# ///

import pathlib
import sys
import unittest

SCRIPTS = pathlib.Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import analyze_transcript_json
import pi_session
import render_transcript_review


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


if __name__ == "__main__":
    unittest.main()
