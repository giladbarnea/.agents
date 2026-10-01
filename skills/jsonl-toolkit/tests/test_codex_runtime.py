#!/usr/bin/env -S uv run
# /// script
# requires-python = "==3.12.*"
# dependencies = []
# ///
"""Imported runtime state must preserve opaque history without owning source sessions."""
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(Path(__file__).parent))
import codex_to_pi
import pi_to_codex
from test_codex_to_pi import ROOT_ID, record, session_meta, write_rollout


class OpaqueReplayTests(unittest.TestCase):
    def test_encrypted_delivery_has_replay_provenance_without_changing_the_archive(self) -> None:
        delivery = {"type": "agent_message", "id": "amsg_task", "author": "/root", "recipient": "/root/worker",
                    "content": [{"type": "input_text", "text": "Task:"}, {"type": "encrypted_content", "encrypted_content": "sealed-task"}]}
        records = [session_meta(ROOT_ID, 0), record(1, "turn_context", {"model": "gpt-6-luna", "effort": "high"}),
                   record(2, "response_item", delivery)]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = write_rollout(root / "codex" / "sessions", ROOT_ID, records)
            target = codex_to_pi.main(source, root / "pi", "Replay")[ROOT_ID]
            entries = [json.loads(line) for line in target.read_text().splitlines()]
            replay_entries = [entry for entry in entries if "codexReplay" in entry]
            self.assertEqual(len(replay_entries), 1, "The encrypted delivery needs an explicit supported replay marker")
            entry = replay_entries[0]
            self.assertEqual(entry["codexReplay"], {"model": "gpt-6-luna", "items": [delivery]})
            self.assertEqual(entry["details"]["codexReplayEntryId"], entry["id"])
            self.assertEqual(pi_to_codex.restore_session(target), records, "Runtime metadata must not change exact restoration")

    def test_supported_hooks_send_original_encrypted_items_in_order(self) -> None:
        delivery = {"type": "agent_message", "id": "amsg_task", "author": "/root", "recipient": "/root/worker",
                    "content": [{"type": "input_text", "text": "Task:"}, {"type": "encrypted_content", "encrypted_content": "sealed-task"}]}
        call = {"type": "function_call", "id": "fc_reply", "call_id": "call_reply", "namespace": "collaboration", "name": "send_message",
                "arguments": '{"target":"/root","message":"gAAAAA-sealed-reply"}', "encrypted_function_args": ["message"]}
        output = {"type": "function_call_output", "call_id": "call_reply", "output": [{"type": "encrypted_content", "encrypted_content": "sealed-receipt"}]}
        records = [session_meta(ROOT_ID, 0), record(1, "turn_context", {"model": "gpt-6-luna", "effort": "high"}),
                   *[record(index + 2, "response_item", item) for index, item in enumerate([delivery, call, output])]]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = write_rollout(root / "codex" / "sessions", ROOT_ID, records)
            target = codex_to_pi.main(source, root / "pi", "Replay")[ROOT_ID]
            result = subprocess.run(["bun", str(ROOT / "tests" / "codex-runtime-replay.ts"), str(target)], capture_output=True, text=True, check=True)
            replay = json.loads(result.stdout)
            self.assertFalse(replay.get("aborted"), replay)
            self.assertEqual(replay.get("input"), [delivery, call, output], "Only the original raw items, not markers or placeholders, may reach OpenAI")

    def test_context_edits_and_checkpoints_do_not_resurrect_opaque_deliveries(self) -> None:
        delivery = {"type": "agent_message", "id": "amsg_old", "author": "/root", "recipient": "/root/worker",
                    "content": [{"type": "encrypted_content", "encrypted_content": "sealed-old"}]}
        records = [session_meta(ROOT_ID, 0), record(1, "turn_context", {"model": "gpt-6-luna", "effort": "high"}), record(2, "response_item", delivery)]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = codex_to_pi.main(write_rollout(root / "codex" / "sessions", ROOT_ID, records), root / "pi", "Projection")[ROOT_ID]
            original = [json.loads(line) for line in target.read_text().splitlines()]
            opaque = next(entry for entry in original if "codexReplay" in entry)
            for replacement in (None, {"content": "An intentional replacement"}):
                with self.subTest(replacement=replacement):
                    entries = [*original, {"type": "context_edit", "id": "edit", "parentId": original[-1]["id"], "targetId": opaque["id"], "replacement": replacement, "timestamp": opaque["timestamp"]}]
                    target.write_text("".join(json.dumps(entry) + "\n" for entry in entries))
                    result = subprocess.run(["bun", str(ROOT / "tests" / "codex-runtime-replay.ts"), str(target)], capture_output=True, text=True, check=True)
                    replay = json.loads(result.stdout)
                    self.assertNotIn("sealed-old", json.dumps(replay), "Replay must honor omission and replacement edits")
                    self.assertFalse(replay.get("aborted"), replay)
            entries = [*original, {"type": "compaction", "id": "checkpoint", "parentId": original[-1]["id"], "firstKeptEntryId": "checkpoint", "summary": "New checkpoint", "tokensBefore": 100, "timestamp": opaque["timestamp"]}]
            target.write_text("".join(json.dumps(entry) + "\n" for entry in entries))
            result = subprocess.run(["bun", str(ROOT / "tests" / "codex-runtime-replay.ts"), str(target)], capture_output=True, text=True, check=True)
            self.assertNotIn("sealed-old", result.stdout, "A checkpoint must not reintroduce old opaque history")

    def test_incompatible_models_abort_instead_of_sending_placeholders(self) -> None:
        delivery = {"type": "agent_message", "id": "amsg_old", "author": "/root", "recipient": "/root/worker",
                    "content": [{"type": "encrypted_content", "encrypted_content": "sealed-old"}]}
        records = [session_meta(ROOT_ID, 0), record(1, "turn_context", {"model": "gpt-6-luna", "effort": "high"}), record(2, "response_item", delivery)]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = codex_to_pi.main(write_rollout(root / "codex" / "sessions", ROOT_ID, records), root / "pi", "Incompatible")[ROOT_ID]
            result = subprocess.run(["bun", str(ROOT / "tests" / "codex-runtime-replay.ts"), str(target), "gpt-5.6-luna"], capture_output=True, text=True, check=True)
            replay = json.loads(result.stdout)
            self.assertTrue(replay.get("aborted"), "Throwing alone is unsafe because Pi catches request-hook errors")
            self.assertIn("Cannot replay encrypted", replay.get("error", ""))

    def test_native_split_compaction_gets_only_each_spans_opaque_items_and_complete_pairs(self) -> None:
        def delivery(identifier: str) -> dict[str, object]:
            return {"type": "agent_message", "id": identifier, "author": "/root", "recipient": "/root/worker",
                    "content": [{"type": "encrypted_content", "encrypted_content": "sealed-" + identifier}]}
        first, second, future = [delivery(identifier) for identifier in ("amsg_one", "amsg_two", "amsg_future")]
        call = {"type": "function_call", "id": "fc_first", "call_id": "call_first", "namespace": "collaboration", "name": "send_message", "arguments": '{"target":"/root","message":"gAAAAA-sealed"}'}
        output = {"type": "function_call_output", "call_id": "call_first", "output": "Original plaintext receipt"}
        items = [first, call, output, second, future]
        records = [session_meta(ROOT_ID, 0), record(1, "turn_context", {"model": "gpt-6-luna", "effort": "high"}), *[record(index + 2, "response_item", item) for index, item in enumerate(items)]]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = codex_to_pi.main(write_rollout(root / "codex" / "sessions", ROOT_ID, records), root / "pi", "Split")[ROOT_ID]
            result = subprocess.run(["bun", str(ROOT / "tests" / "codex-runtime-compaction.ts"), str(target)], capture_output=True, text=True, check=True)
            replay = json.loads(result.stdout)
            self.assertFalse(replay["aborted"], replay)
            self.assertEqual(len(replay["captured"]), 2, "Use Pi's two native split summaries, not a replacement compactor")
            self.assertEqual(replay["captured"][0]["input"][:3], [first, call, output], "History summary needs the encrypted call with its original plaintext receipt")
            self.assertEqual(replay["captured"][1]["input"][0], second, "Turn-prefix summary needs only its own opaque delivery")
            self.assertNotIn("sealed-amsg_two", json.dumps(replay["captured"][0]))
            self.assertNotIn("sealed-amsg_one", json.dumps(replay["captured"][1]))
            self.assertNotIn("sealed-amsg_future", json.dumps(replay["captured"]), "Never inject retained future context into either summary")
            self.assertIn("SUMMARY-1", replay["result"]["summary"])
            self.assertIn("SUMMARY-2", replay["result"]["summary"])


if __name__ == "__main__":
    unittest.main()
