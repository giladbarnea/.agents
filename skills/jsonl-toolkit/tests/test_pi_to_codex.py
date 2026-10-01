#!/usr/bin/env -S uv run
# /// script
# requires-python = "==3.12.*"
# dependencies = []
# ///
"""Native Pi conversations become new, resumable Codex rollouts."""

import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = pathlib.Path(__file__).resolve().parents[1] / "scripts"
TIMESTAMP = "2026-09-29T07:00:00.000Z"
SOURCE_ID = "01a00000-0000-7000-8000-000000000011"
MODEL = "gpt-6-luna"


class NativeConversionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = pathlib.Path(self.directory.name)
        self.source = self.root / "pi.jsonl"
        self.codex_home = self.root / "codex"
        self.codex_home.mkdir()
        (self.codex_home / "models_cache.json").write_text(json.dumps({
            "models": [{"slug": MODEL}, {"slug": "gpt-6-astra"}],
        }))
        self.header = {"type": "session", "version": 3, "id": SOURCE_ID,
                       "timestamp": TIMESTAMP, "cwd": str(self.root)}

    def convert(self, entries: list[dict[str, object]], expected_error: str | None = None) -> tuple[list[dict[str, object]], str]:
        lines = [self.header]
        for index, entry in enumerate(entries):
            lines.append({"id": f"entry{index}", "parentId": f"entry{index - 1}" if index else None,
                          "timestamp": TIMESTAMP, **entry})
        original = "".join(json.dumps(line) + "\n" for line in lines)
        self.source.write_text(original)
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "pi_to_codex.py"), str(self.source), str(self.codex_home / "sessions")],
            env={**os.environ, "CODEX_HOME": str(self.codex_home)},
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(self.source.read_text(), original, "Conversion must not modify the Pi session")
        outputs = list((self.codex_home / "sessions").glob("rollout-*.jsonl"))
        if expected_error is not None:
            self.assertNotEqual(result.returncode, 0, "A lossy import must fail")
            self.assertIn(expected_error, result.stderr)
            self.assertEqual(outputs, [], "A rejected import must not write a rollout")
            return [], result.stderr
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(outputs), 1, "Conversion must create exactly one standalone rollout")
        return [json.loads(line) for line in outputs[0].read_text().splitlines()], result.stderr

    def test_native_conversation_gets_a_new_codex_identity_and_bare_model_id(self) -> None:
        records, stderr = self.convert([
            {"type": "model_change", "provider": "openai-codex", "modelId": f"openai-codex/{MODEL}"},
            {"type": "message", "message": {"role": "user", "content": "Remember the codeword: coral", "timestamp": 0}},
            {"type": "message", "message": {
                "role": "assistant", "provider": "openai-codex", "api": "openai-codex-responses",
                "model": f"openai-codex/{MODEL}", "stopReason": "stop", "timestamp": 0,
                "content": [{"type": "text", "text": "The codeword is coral.",
                             "textSignature": json.dumps({"v": 1, "id": "msg_answer", "phase": "final_answer"})}],
            }},
        ])
        metadata = records[0]["payload"]
        self.assertNotEqual(metadata["id"], SOURCE_ID, "A native import must create a new Codex identity")
        self.assertEqual(metadata["id"], metadata["session_id"])
        self.assertEqual(metadata.get("multi_agent_version"), "v2", "Native resume must expose the restored team's messaging tools")
        self.assertEqual(metadata["cwd"], str(self.root))
        contexts = [record["payload"] for record in records if record["type"] == "turn_context"]
        self.assertEqual(contexts[-1]["model"], MODEL, "Codex must not receive a Pi provider prefix")
        messages = [record["payload"] for record in records if record["type"] == "response_item"]
        self.assertEqual([message["content"][0]["text"] for message in messages],
                         ["Remember the codeword: coral", "The codeword is coral."])
        self.assertEqual(messages[-1]["id"], "msg_answer")
        self.assertEqual(messages[-1]["phase"], "final_answer")
        self.assertNotIn("Warning:", stderr)
        self.assertIn(f"--model {MODEL}", stderr)

    def test_non_codex_provider_without_reasoning_warns_and_uses_luna(self) -> None:
        records, stderr = self.convert([
            {"type": "message", "message": {"role": "user", "content": "Keep this conversation", "timestamp": 0}},
            {"type": "message", "message": {
                "role": "assistant", "provider": "anthropic", "api": "anthropic-messages",
                "model": "claude-opus-4-7", "stopReason": "stop", "timestamp": 0,
                "content": [
                    {"type": "text", "text": "Kept", "textSignature": "foreign-message-id"},
                ],
            }},
        ])
        self.assertIn("Warning:", stderr)
        self.assertIn("anthropic/claude-opus-4-7", stderr)
        self.assertIn(MODEL, stderr)
        self.assertEqual(records[1]["payload"]["model"], MODEL)
        self.assertNotIn("foreign-message-id", json.dumps(records))
        self.assertIn("Kept", json.dumps(records))

    def test_unknown_codex_model_warns_and_falls_back_to_luna(self) -> None:
        records, stderr = self.convert([
            {"type": "model_change", "provider": "openai-codex", "modelId": "gpt-unknown"},
            {"type": "message", "message": {"role": "user", "content": "hello", "timestamp": 0}},
        ])
        self.assertIn("Warning:", stderr)
        self.assertIn("openai-codex/gpt-unknown", stderr)
        self.assertEqual(records[1]["payload"]["model"], MODEL)

    def test_reasoning_images_and_namespaced_tool_history_survive(self) -> None:
        reasoning = {"type": "reasoning", "id": "rs_native", "summary": [{"type": "summary_text", "text": "Check the image"}],
                     "encrypted_content": "opaque-replay-data"}
        image = {"type": "image", "mimeType": "image/png", "data": "aW1hZ2U="}
        records, _ = self.convert([
            {"type": "message", "message": {"role": "user", "content": [{"type": "text", "text": "Inspect"}, image], "timestamp": 0}},
            {"type": "message", "message": {
                "role": "assistant", "provider": "openai-codex", "api": "openai-codex-responses",
                "model": MODEL, "stopReason": "toolUse", "timestamp": 0,
                "content": [
                    {"type": "thinking", "thinking": "Check the image", "thinkingSignature": json.dumps(reasoning)},
                    {"type": "toolCall", "id": "call_native|fc_native", "namespace": "functions", "name": "read",
                     "arguments": {"path": "/tmp/שלום.png"}},
                ],
            }},
            {"type": "message", "message": {"role": "toolResult", "toolCallId": "call_native|fc_native",
                                             "toolName": "read", "content": [{"type": "text", "text": "Image loaded"}, image], "timestamp": 0}},
        ])
        items = [record["payload"] for record in records if record["type"] == "response_item"]
        self.assertEqual(items[1], reasoning, "Same-model OpenAI replay state must survive unchanged")
        self.assertEqual(items[0]["content"][1]["image_url"], "data:image/png;base64,aW1hZ2U=")
        self.assertEqual(items[2]["id"], "fc_native")
        self.assertEqual(items[2]["call_id"], items[3]["call_id"])
        self.assertEqual(items[2]["namespace"], "functions")
        self.assertEqual(json.loads(items[2]["arguments"]), {"path": "/tmp/שלום.png"})
        self.assertEqual(items[3]["output"][1]["image_url"], items[0]["content"][1]["image_url"])

    def test_native_import_uses_the_active_compacted_context_not_abandoned_history(self) -> None:
        records, _ = self.convert([
            {"type": "model_change", "provider": "openai-codex", "modelId": MODEL},
            {"type": "message", "message": {"role": "user", "content": "Already summarized", "timestamp": 0}},
            {"type": "message", "message": {"role": "user", "content": "Retained question", "timestamp": 0}},
            {"type": "compaction", "summary": "Earlier decisions", "firstKeptEntryId": "entry2", "tokensBefore": 50000},
            {"type": "custom", "customType": "extension-state", "data": {"private": "Not model context"}},
            {"type": "custom_message", "customType": "notification", "content": "Agent finished", "display": True},
            {"type": "message", "message": {"role": "user", "content": "Abandoned branch", "timestamp": 0}},
            {"type": "message", "parentId": "entry5", "message": {"role": "user", "content": "Active branch", "timestamp": 0}},
        ])
        items = [record["payload"] for record in records if record["type"] == "response_item"]
        text = json.dumps(items)
        for expected in ["Earlier decisions", "Retained question", "Agent finished", "Active branch"]:
            self.assertIn(expected, text)
        for excluded in ["Already summarized", "Abandoned branch", "Not model context"]:
            self.assertNotIn(excluded, text)

    def test_codex_to_pi_separates_the_provider_from_the_model_id(self) -> None:
        records, _ = self.convert([
            {"type": "model_change", "provider": "openai-codex", "modelId": MODEL},
            {"type": "message", "message": {"role": "user", "content": "hello", "timestamp": 0}},
        ])
        records[1]["payload"]["model"] = f"openai-codex/{MODEL}"
        rollout = next((self.codex_home / "sessions").glob("*.jsonl"))
        rollout.write_text("".join(json.dumps(record) + "\n" for record in records))
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "codex_to_pi.py"), str(rollout), str(self.root / "pi"), "Imported"],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        output = next((self.root / "pi").rglob("*.jsonl"))
        entries = [json.loads(line) for line in output.read_text().splitlines()]
        setting = next(entry for entry in entries if entry["type"] == "model_change")
        self.assertEqual(setting["provider"], "openai-codex")
        self.assertEqual(setting["modelId"], MODEL, "Pi stores the provider separately, not inside modelId")
        original = next(record for entry in entries for record in entry.get("codex", [])
                        if isinstance(record, dict) and record["type"] == "turn_context")
        self.assertEqual(original["payload"]["model"], f"openai-codex/{MODEL}", "The exact-restoration archive must not change")

    def test_foreign_or_unsigned_reasoning_rejects_the_import_without_writing(self) -> None:
        for provider, model, api, signature in [
            ("anthropic", "claude-opus-4-7", "anthropic-messages", "foreign-ciphertext"),
            ("openai-codex", MODEL, "openai-codex-responses", None),
        ]:
            with self.subTest(provider=provider):
                self.convert([
                    {"type": "message", "message": {
                        "role": "assistant", "provider": provider, "model": model, "api": api,
                        "timestamp": 0, "stopReason": "stop",
                        "content": [{"type": "thinking", "thinking": "Must not disappear or become ordinary text",
                                     "thinkingSignature": signature}, {"type": "text", "text": "done"}],
                    }},
                ], expected_error="Cannot preserve reasoning")

    def test_gpt_model_changes_keep_all_original_reasoning_items(self) -> None:
        reasoning = {"type": "reasoning", "id": "rs_previous_model", "summary": [], "encrypted_content": "opaque-state"}
        records, _ = self.convert([
            {"type": "message", "message": {
                "role": "assistant", "provider": "openai-codex", "model": MODEL, "api": "openai-codex-responses",
                "timestamp": 0, "stopReason": "stop",
                "content": [{"type": "thinking", "thinking": "", "thinkingSignature": json.dumps(reasoning)},
                            {"type": "text", "text": "done"}],
            }},
            {"type": "model_change", "provider": "openai-codex", "modelId": "gpt-6-astra"},
        ])
        self.assertEqual(records[1]["payload"]["model"], "gpt-6-astra")
        retained = [record["payload"] for record in records
                    if record["type"] == "response_item" and record["payload"]["type"] == "reasoning"]
        self.assertEqual(retained, [reasoning], "Changing GPT models must not delete opaque reasoning")

    def test_reasoning_filtered_by_the_provider_rejects_the_import(self) -> None:
        reasoning = {"type": "reasoning", "id": "rs_failed", "summary": [], "encrypted_content": "must-not-disappear"}
        self.convert([
            {"type": "message", "message": {
                "role": "assistant", "provider": "openai-codex", "model": MODEL, "api": "openai-codex-responses",
                "timestamp": 0, "stopReason": "error",
                "content": [{"type": "thinking", "thinking": "", "thinkingSignature": json.dumps(reasoning)}],
            }},
        ], expected_error="message conversion changed or removed replay payloads")

    def test_luna_fallback_cannot_discard_an_incompatible_reasoning_family(self) -> None:
        reasoning = {"type": "reasoning", "id": "rs_other_family", "summary": [], "encrypted_content": "family-bound-state"}
        self.convert([
            {"type": "message", "message": {
                "role": "assistant", "provider": "openai-codex", "model": "gpt-5.6-retired", "api": "openai-codex-responses",
                "timestamp": 0, "stopReason": "stop",
                "content": [{"type": "thinking", "thinking": "", "thinkingSignature": json.dumps(reasoning)},
                            {"type": "text", "text": "done"}],
            }},
        ], expected_error="incompatible model families")


if __name__ == "__main__":
    unittest.main()
