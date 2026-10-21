#!/usr/bin/env -S uv run
# /// script
# requires-python = "==3.12.*"
# dependencies = []
# ///
"""Native Pi sessions become Claude Code sessions whose signed Anthropic thinking reaches the API unchanged.

Requires Node and the installed Pi package, because Pi's own reader builds the context.
A real `claude -p --resume` of a converted Opus 5.5 session sent all 25 thinking blocks
byte for byte and got a 200; these tests keep the converter's side of that contract.
"""

import json
import pathlib
import sys
import tempfile
import unittest

SCRIPTS = pathlib.Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import pi_to_claude
from test_codex_to_claude import ALLOWED_BLOCK_KEYS, blocks, load_records, message_entries

TIMESTAMP = "2026-10-20T05:59:03.292Z"
SOURCE_ID = "01a00000-0000-7000-8000-000000000021"
SIGNATURE = "CAQSigUKEAgTGAI4AUIIdGhpbmtpbmcSDJ+9wfs38618Z4na4RoM0df6ek3/+HDwcjn/Ij=="
ALLOWED_KEYS = {**ALLOWED_BLOCK_KEYS, "redacted_thinking": {"type", "data"}}

Lines = list[dict[str, object]]


def assistant(content: Lines, stop_reason: str = "stop", provider: str = "anthropic", api: str = "anthropic-messages", model: str = "claude-opus-5-5") -> dict[str, object]:
    return {"type": "message", "message": {"role": "assistant", "provider": provider, "api": api, "model": model, "stopReason": stop_reason, "timestamp": 1792479583624, "content": content}}


def user(text: str) -> dict[str, object]:
    return {"type": "message", "message": {"role": "user", "content": [{"type": "text", "text": text}], "timestamp": 1792479583000}}


def tool_result(call_id: str, text: str) -> dict[str, object]:
    return {"type": "message", "message": {"role": "toolResult", "toolCallId": call_id, "toolName": "bash", "content": [{"type": "text", "text": text}], "isError": False, "timestamp": 1792479584000}}


class ConversionTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = pathlib.Path(directory.name)

    def convert(self, entries: Lines) -> Lines:
        header = {"type": "session", "version": 3, "id": SOURCE_ID, "timestamp": TIMESTAMP, "cwd": "/tmp/project"}
        lines = [header, *({"id": f"entry{index:04d}", "parentId": f"entry{index - 1:04d}" if index else None, "timestamp": TIMESTAMP, **entry} for index, entry in enumerate(entries))]
        source = self.root / f"2026-10-20T05-59-02-664Z_{SOURCE_ID}.jsonl"
        original = "".join(json.dumps(line) + "\n" for line in lines)
        source.write_text(original)
        target = pi_to_claude.main(source, self.root / "claude")
        self.assertEqual(source.read_text(), original, "Conversion must not modify the Pi session")
        self.assertEqual(target.parent, self.root / "claude" / "-tmp-project", "Claude Code lists sessions for /tmp/project only from this directory")
        return load_records(target)

    def test_anthropic_thinking_keeps_its_signature_text_and_model(self) -> None:
        lines = self.convert([
            {"type": "model_change", "provider": "anthropic", "modelId": "claude-opus-5-5"},
            user("Pick a number"),
            assistant([{"type": "thinking", "thinking": "I pick 31415926.", "thinkingSignature": SIGNATURE}, {"type": "text", "text": "Done."}]),
        ])
        thinking = [(entry["message"]["model"], block) for entry in message_entries(lines) for block in blocks(entry) if block["type"] == "thinking"]
        self.assertEqual(thinking, [("claude-opus-5-5", {"type": "thinking", "thinking": "I pick 31415926.", "signature": SIGNATURE})],
                         "The API rebuilds reasoning from the signature, so it must arrive byte for byte under the Claude model that signed it")

    def test_another_vendors_thinking_becomes_text_or_a_block_claude_code_drops(self) -> None:
        openai = {"provider": "openai-codex", "api": "openai-codex-responses", "model": "gpt-6-astra"}
        lines = self.convert([
            user("Plan it"),
            assistant([{"type": "thinking", "thinking": "Summary of the plan.", "thinkingSignature": '{"type":"reasoning"}'}], **openai),
            assistant([{"type": "thinking", "thinking": "", "thinkingSignature": '{"type":"reasoning","encrypted_content":"gAAAA"}'}, {"type": "text", "text": "Planned."}], **openai),
        ])
        rendered = [(entry["message"]["model"], block["type"], block.get("text", block.get("signature"))) for entry in message_entries(lines) if entry["type"] == "assistant" for block in blocks(entry)]
        self.assertEqual(rendered, [
            ("gpt-6-astra", "text", "Summary of the plan."),
            ("gpt-6-astra", "thinking", '{"type":"reasoning","encrypted_content":"gAAAA"}'),
            ("gpt-6-astra", "text", "Planned."),
        ], "A readable summary must stay visible, and an unreadable block must keep a non-Claude model id so Claude Code drops it")

    def test_history_obeys_the_rules_the_claude_api_enforces(self) -> None:
        lines = self.convert([
            user("Run it"),
            assistant([{"type": "toolCall", "id": "call_a|fc_1", "name": "bash", "arguments": {"command": "ls"}}], stop_reason="toolUse"),
            tool_result("call_a|fc_1", "file.txt"),
            assistant([{"type": "toolCall", "id": "toolu_orphan", "name": "bash", "arguments": {"command": "sleep 99"}}], stop_reason="toolUse"),
            assistant([{"type": "thinking", "thinking": "partial", "thinkingSignature": ""}], stop_reason="aborted"),
            {"type": "custom_message", "customType": "pi-time-sense", "content": "<automatic-current-time-message>now</automatic-current-time-message>", "display": False},
            user("Again"),
        ])
        entries = message_entries(lines)
        for entry in entries:
            for block in blocks(entry):
                self.assertLessEqual(set(block), ALLOWED_KEYS[block["type"]], f"The API rejects unknown keys inside a content block. Got: {block!r}")
        messages: Lines = []
        for entry in entries:
            if messages and messages[-1]["role"] == entry["message"]["role"]:
                messages[-1]["content"].extend(blocks(entry))
            else:
                messages.append({"role": entry["message"]["role"], "content": list(blocks(entry))})
        for index, message in enumerate(messages):
            calls = [block["id"] for block in message["content"] if block["type"] == "tool_use"]
            results = [block["tool_use_id"] for block in messages[index + 1]["content"] if block["type"] == "tool_result"] if calls else []
            self.assertEqual(calls, results, "Every tool_use needs its tool_result in the next message")
        self.assertEqual([block["id"] for message in messages for block in message["content"] if block["type"] == "tool_use"], ["call_a_fc_1", "toolu_orphan"],
                         "Tool call ids must match ^[a-zA-Z0-9_-]+$ the way Pi normalizes them")
        texts = [block["text"] for message in messages for block in message["content"] if block["type"] == "text"]
        self.assertIn("<automatic-current-time-message>now</automatic-current-time-message>", texts, "Pi sends custom messages to the model as user text")
        self.assertNotIn("partial", json.dumps(messages), "Pi never replays an aborted turn")
        self.assertEqual([line["customTitle"] for line in lines if line["type"] == "custom-title"], [f"Pi session {SOURCE_ID} (from Pi)"])


if __name__ == "__main__":
    unittest.main()
