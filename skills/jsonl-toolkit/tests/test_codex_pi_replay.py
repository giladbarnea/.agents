#!/usr/bin/env -S uv run
# /// script
# requires-python = "==3.12.*"
# dependencies = []
# ///
"""The installed Pi provider must send original Codex reasoning, not just archive it."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(Path(__file__).parent))

import codex_to_pi
import pi_to_codex
from test_codex_to_pi import CHILD_ID, ROOT_ID, message, record, session_meta, write_rollout


class NativeReplayTests(unittest.TestCase):
    def convert_and_replay(self, records: list[dict[str, object]]) -> dict[str, object]:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rollout = write_rollout(root / "codex" / "sessions", ROOT_ID, records)
            converted = codex_to_pi.main(rollout, root / "pi", "Replay test")[ROOT_ID]
            self.assertEqual(pi_to_codex.restore_session(converted), records, "Replay fixes must not change exact restoration")
            result = subprocess.run(["node", str(ROOT / "tests" / "pi-replay.mjs"), str(converted)],
                                    text=True, capture_output=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(result.stdout)

    def test_compatible_model_changes_keep_every_reasoning_item_in_the_request(self) -> None:
        first = {"type": "reasoning", "id": "rs_first", "summary": [], "encrypted_content": "sealed-first"}
        second = {"type": "reasoning", "id": "rs_second", "summary": [], "encrypted_content": "sealed-second"}
        replay = self.convert_and_replay([
            session_meta(ROOT_ID, 0),
            record(1, "turn_context", {"model": "gpt-6-sol", "effort": "high"}),
            message(2, "u_first", "user", "Start"),
            record(3, "response_item", first),
            message(4, "m_first", "assistant", "First answer"),
            record(5, "turn_context", {"model": "gpt-6-luna", "effort": "high"}),
            message(6, "u_second", "user", "Continue"),
            record(7, "response_item", second),
            message(8, "m_second", "assistant", "Second answer"),
        ])
        self.assertEqual(replay["model"], "gpt-6-luna")
        actual = [item for item in replay["items"] if item.get("type") == "reasoning"]
        self.assertEqual(actual, [first, second], "Pi's exact-model filter must not discard compatible imported reasoning")

    def test_encrypted_checkpoint_and_retained_messages_reach_the_request(self) -> None:
        checkpoint = {"type": "compaction", "id": "cmp_saved", "encrypted_content": "sealed-checkpoint",
                      "internal_chat_message_metadata_passthrough": {"turn_id": "original-turn"}}
        previous = {"type": "reasoning", "id": "rs_old", "summary": [], "encrypted_content": "summarized-away"}
        subsequent = {"type": "reasoning", "id": "rs_new", "summary": [], "encrypted_content": "after-checkpoint"}
        replay = self.convert_and_replay([
            session_meta(ROOT_ID, 0),
            record(1, "turn_context", {"model": "gpt-6-sol", "effort": "high"}),
            message(2, "u_old", "user", "Old request"),
            record(3, "response_item", previous),
            message(4, "m_old", "assistant", "Old answer"),
            record(5, "compacted", {"message": "", "replacement_history": [
                {"type": "message", "role": "developer", "content": [{"type": "input_text", "text": "Old Codex harness"}]},
                {"type": "message", "role": "user", "content": [
                    {"type": "input_text", "text": "# AGENTS.md instructions for /tmp/project"},
                    {"type": "input_text", "text": "Actual retained request"},
                ]},
                checkpoint,
            ]}),
            record(6, "turn_context", {"model": "gpt-6-luna", "effort": "high"}),
            message(7, "u_new", "user", "Continue after the checkpoint"),
            record(8, "response_item", subsequent),
            message(9, "m_new", "assistant", "New answer"),
        ])
        opaque = [item for item in replay["items"] if item.get("type") in ("reasoning", "compaction")]
        self.assertEqual(opaque, [checkpoint, subsequent], "The checkpoint must replace old reasoning, not disappear into a prose summary")
        text = json.dumps(replay["items"])
        self.assertIn("Actual retained request", text, "A harness block must not hide another block containing the user request")
        self.assertNotIn("Old request", text)
        self.assertNotIn("Old Codex harness", text)
        self.assertNotIn("AGENTS.md instructions", text)

    def test_incompatible_reasoning_families_fail_before_writing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rollout = write_rollout(root / "codex" / "sessions", ROOT_ID, [
                session_meta(ROOT_ID, 0),
                record(1, "turn_context", {"model": "gpt-5.6-sol", "effort": "high"}),
                record(2, "response_item", {"type": "reasoning", "id": "rs_old_family", "summary": [], "encrypted_content": "sealed"}),
                message(3, "m_old", "assistant", "Old family answer"),
                record(4, "turn_context", {"model": "gpt-6-luna", "effort": "high"}),
            ])
            with self.assertRaisesRegex(ValueError, "incompatible model families"):
                codex_to_pi.main(rollout, root / "pi", "Must refuse")
            self.assertEqual(list((root / "pi").rglob("*.jsonl")), [], "An incompatible import must not write a partial session")

    def test_fork_prefix_replays_with_each_destination_model(self) -> None:
        shared = {"type": "reasoning", "id": "rs_shared", "summary": [], "encrypted_content": "shared-state"}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sessions = root / "codex" / "sessions"
            write_rollout(sessions, ROOT_ID, [
                session_meta(ROOT_ID, 0),
                record(1, "turn_context", {"model": "gpt-6-sol", "effort": "high"}),
                message(2, "u_shared", "user", "Shared question"),
                record(3, "response_item", shared),
                message(4, "m_shared", "assistant", "Shared answer"),
                record(5, "turn_context", {"model": "gpt-6-astra", "effort": "high"}),
                message(6, "m_parent", "assistant", "Parent-only answer"),
            ])
            selected = write_rollout(sessions, CHILD_ID, [
                session_meta(CHILD_ID, 5, ROOT_ID, 5),
                record(6, "turn_context", {"model": "gpt-6-luna", "effort": "high"}),
                message(7, "u_child", "user", "Child-only question"),
            ])
            converted = codex_to_pi.main(selected, root / "pi", "Selected child")
            for identifier, model in ((ROOT_ID, "gpt-6-astra"), (CHILD_ID, "gpt-6-luna")):
                with self.subTest(model=model):
                    result = subprocess.run(["node", str(ROOT / "tests" / "pi-replay.mjs"), str(converted[identifier])],
                                            text=True, capture_output=True, timeout=30)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    replay = json.loads(result.stdout)
                    self.assertEqual(replay["model"], model)
                    self.assertEqual([item for item in replay["items"] if item.get("type") == "reasoning"], [shared])

    def test_latest_checkpoint_keeps_only_its_replacement_history(self) -> None:
        earlier = {"type": "compaction", "id": "cmp_earlier", "encrypted_content": "old-state"}
        latest = {"type": "compaction", "id": "cmp_latest", "encrypted_content": "latest-state"}
        replay = self.convert_and_replay([
            session_meta(ROOT_ID, 0),
            record(1, "turn_context", {"model": "gpt-6-luna", "effort": "high"}),
            record(2, "compacted", {"replacement_history": [earlier]}),
            message(3, "u_between", "user", "Between checkpoints"),
            record(4, "compacted", {"replacement_history": [latest]}),
            message(5, "u_after", "user", "After the latest checkpoint"),
        ])
        self.assertEqual([item for item in replay["items"] if item.get("type") == "compaction"], [latest])
        self.assertNotIn("Between checkpoints", json.dumps(replay["items"]))


if __name__ == "__main__":
    unittest.main()
