#!/usr/bin/env -S uv run
# /// script
# requires-python = "==3.12.*"
# dependencies = []
# ///
"""Codex → Claude Code must restore every record and must produce entries the Claude API accepts.

The API rules below were each found by a real `claude --resume` that failed without them:
an unknown key inside a content block is rejected, a thinking block signed by another vendor
is rejected unless the message names a non-Claude model, and every tool_use needs its
tool_result in the next message.
"""

import json
import pathlib
import re
import sys
import tempfile
import unittest

SCRIPTS = pathlib.Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import codex_to_claude
from test_codex_to_pi import CHILD_ID, ROOT_ID, message, record, session_meta, turn_context, write_rollout

FIXTURE_SESSIONS = pathlib.Path(__file__).resolve().parent / "fixtures" / "codex" / "sessions"
ALLOWED_BLOCK_KEYS = {
    "text": {"type", "text"},
    "thinking": {"type", "thinking", "signature"},
    "tool_use": {"type", "id", "name", "input"},
    "tool_result": {"type", "tool_use_id", "content", "is_error"},
    "image": {"type", "source"},
}
CIPHERTEXT = "gAAAAABq-sealed-by-openai"


def load_records(path: pathlib.Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").split("\n") if line]


def reloaded(lines: list[dict[str, object]]) -> list[dict[str, object]]:
    """Serialize and parse again, the way the lines reach and leave the session file."""
    return [json.loads(json.dumps(line, ensure_ascii=False)) for line in lines]


def message_entries(lines: list[dict[str, object]]) -> list[dict[str, object]]:
    return [line for line in lines if "message" in line]


def blocks(entry: dict[str, object]) -> list[dict[str, object]]:
    content = entry["message"]["content"]
    return content if isinstance(content, list) else [{"type": "text", "text": content}]


def claude_visible_text(lines: list[dict[str, object]]) -> str:
    """Everything the Claude model reads. Thinking is excluded, because Claude Code drops foreign thinking."""
    return json.dumps([block for entry in message_entries(lines) for block in blocks(entry) if block["type"] != "thinking"])


def stored_ciphertexts(records: list[dict[str, object]]) -> set[str]:
    """Collect the ciphertexts Codex stored: every `encrypted_content` value, and tool arguments that are ciphertext whole."""
    found: set[str] = set()

    def walk(value: object) -> None:
        if isinstance(value, dict):
            found.update(item for key, item in value.items() if key == "encrypted_content" and isinstance(item, str))
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)
        elif isinstance(value, str) and value.startswith("gAAAAA"):
            found.add(value)

    for record in records:
        payload = record["payload"]
        walk(payload)
        if payload.get("type") == "function_call":
            walk(json.loads(payload["arguments"]))
    return found


def convert_records(temporary: pathlib.Path, records: list[dict[str, object]]) -> list[dict[str, object]]:
    return reloaded(codex_to_claude.convert(write_rollout(temporary / "sessions", ROOT_ID, records)))


def tool_uses(lines: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    return {block["name"]: block for entry in message_entries(lines) for block in blocks(entry) if block["type"] == "tool_use"}


def tool_result_texts(lines: list[dict[str, object]]) -> list[str]:
    return [
        inner["text"]
        for entry in message_entries(lines)
        for block in blocks(entry)
        if block["type"] == "tool_result"
        for inner in (block["content"] if isinstance(block["content"], list) else [{"text": block["content"]}])
    ]


class RealSessionTests(unittest.TestCase):
    def test_every_fixture_session_restores_its_exact_records(self) -> None:
        rollouts = sorted(FIXTURE_SESSIONS.glob("*.jsonl"))
        self.assertGreaterEqual(len(rollouts), 5, f"Expected the real fixture sessions. Got: {rollouts!r}")
        for rollout in rollouts:
            with self.subTest(rollout=rollout.name):
                original = load_records(rollout)
                restored = codex_to_claude.restore(reloaded(codex_to_claude.convert(rollout)))
                first_difference = next((index for index, pair in enumerate(zip(original, restored)) if pair[0] != pair[1]), None)
                self.assertEqual(
                    restored,
                    original,
                    f"Restore changed the rollout. First difference at record {first_difference}. Counts: original={len(original)} restored={len(restored)}",
                )

    def test_fixture_sessions_obey_the_rules_the_claude_api_enforces(self) -> None:
        for rollout in sorted(FIXTURE_SESSIONS.glob("*.jsonl")):
            with self.subTest(rollout=rollout.name):
                entries = message_entries(reloaded(codex_to_claude.convert(rollout)))
                ciphertexts = stored_ciphertexts(load_records(rollout))
                self.assertGreater(len(ciphertexts), 10, f"A real fixture must carry stored ciphertexts. Got {len(ciphertexts)}")
                self.assertGreater(len(entries), 50, f"A real fixture must yield many message entries. Got {len(entries)}")
                for index, entry in enumerate(entries):
                    for block in blocks(entry):
                        extra_keys = set(block) - ALLOWED_BLOCK_KEYS.get(block["type"], set())
                        self.assertFalse(extra_keys, f"Entry {index} has a {block['type']!r} block with keys the API rejects: {extra_keys}")
                    if entry["type"] == "assistant":
                        model = entry["message"]["model"]
                        self.assertFalse(model.startswith("claude"), f"Entry {index} names Claude model {model!r}, so Claude Code would send the OpenAI reasoning and the API would reject it")
                    call_ids = [block["id"] for block in blocks(entry) if block["type"] == "tool_use"]
                    if call_ids:
                        following = entries[index + 1] if index + 1 < len(entries) else {"type": "none", "message": {"content": []}}
                        answered = [block.get("tool_use_id") for block in blocks(following) if block["type"] == "tool_result"]
                        self.assertEqual(answered, call_ids, f"Entry {index} calls {call_ids}, but the next message answers {answered}")
                leaked = ciphertexts & set(re.findall(r"gAAAAA[A-Za-z0-9_=-]+", claude_visible_text(entries)))
                self.assertFalse(leaked, f"{len(leaked)} stored Codex ciphertexts reached a block that Claude reads, for example {sorted(leaked)[:1]!r}")


class ToolCallTests(unittest.TestCase):
    def test_an_exec_script_reaches_claude_as_the_exact_javascript_and_output(self) -> None:
        script = 'if ((await tools.exec_command({cmd:"test -f a.txt"})).exit_code !== 0) {\n  text(await tools.exec_command({cmd:"rm -rf build"}));\n}'
        envelope = 'Script completed\nWall time 0.2 seconds\nOutput:\n{"chunk_id":"c1","exit_code":1,"output":""}'
        with tempfile.TemporaryDirectory() as temporary_directory:
            lines = convert_records(
                pathlib.Path(temporary_directory),
                [
                    session_meta(ROOT_ID, 0),
                    turn_context(1),
                    message(2, "user-1", "user", "clean the build only if a.txt is missing"),
                    record(3, "response_item", {"type": "custom_tool_call", "id": "ctc_1", "call_id": "call_exec", "name": "exec", "input": script, "status": "completed"}),
                    record(4, "response_item", {"type": "custom_tool_call_output", "call_id": "call_exec", "output": [{"type": "input_text", "text": envelope}]}),
                ],
            )
        call = tool_uses(lines).get("exec", {})
        self.assertEqual(call.get("input"), {"input": script}, f"Claude must see the script itself, with its condition. Got tool calls: {tool_uses(lines)!r}")
        self.assertIn(envelope, tool_result_texts(lines), f"Claude must see the output Codex saw. Got: {tool_result_texts(lines)!r}")

    def test_subagent_coordination_stays_readable_and_only_ciphertext_is_masked(self) -> None:
        spawn_arguments = {"task_name": "hud", "agent_type": "worker", "model": "gpt-6-astra", "message": CIPHERTEXT}
        wait_output = '{"message":"hud finished: 3 files changed","timed_out":false}'
        with tempfile.TemporaryDirectory() as temporary_directory:
            lines = convert_records(
                pathlib.Path(temporary_directory),
                [
                    session_meta(ROOT_ID, 0),
                    turn_context(1),
                    message(2, "user-1", "user", "delegate the HUD work"),
                    record(3, "response_item", {"type": "function_call", "id": "fc_1", "call_id": "call_spawn", "namespace": "collaboration", "name": "spawn_agent", "arguments": json.dumps(spawn_arguments)}),
                    record(4, "response_item", {"type": "function_call_output", "call_id": "call_spawn", "output": '{"task_name":"/root/hud"}'}),
                    record(5, "response_item", {"type": "function_call", "id": "fc_2", "call_id": "call_wait", "namespace": "collaboration", "name": "wait_agent", "arguments": '{"timeout_ms":60000}'}),
                    record(6, "response_item", {"type": "function_call_output", "call_id": "call_wait", "output": wait_output}),
                ],
            )
        spawn = tool_uses(lines).get("collaboration__spawn_agent", {})
        expected_input = {**spawn_arguments, "message": codex_to_claude.ENCRYPTED_PLACEHOLDER}
        self.assertEqual(spawn.get("input"), expected_input, f"The spawn call must show its readable fields and mask only the ciphertext. Got tool calls: {tool_uses(lines)!r}")
        self.assertIn(wait_output, tool_result_texts(lines), f"Claude must read what wait_agent returned. Got: {tool_result_texts(lines)!r}")


class CompactionTests(unittest.TestCase):
    def test_the_summary_replays_subagent_messages_but_not_harness_instructions(self) -> None:
        replacement_history = [
            {"type": "message", "role": "developer", "content": [{"type": "input_text", "text": "<permissions instructions>sandbox</permissions instructions>"}]},
            {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "make the game faster"}]},
            {"type": "agent_message", "author": "/root/hud", "recipient": "/root", "content": [{"type": "input_text", "text": "Message Type: FINAL_ANSWER\nThe HUD redraws every frame."}]},
            {"type": "compaction", "id": "cmp_1", "encrypted_content": CIPHERTEXT},
        ]
        with tempfile.TemporaryDirectory() as temporary_directory:
            lines = convert_records(
                pathlib.Path(temporary_directory),
                [
                    session_meta(ROOT_ID, 0),
                    turn_context(1),
                    message(2, "user-1", "user", "make the game faster"),
                    record(3, "compacted", {"message": "", "replacement_history": replacement_history}),
                    message(4, "msg-1", "assistant", "Next I will batch the draw calls."),
                ],
            )
        summaries = [entry["message"]["content"] for entry in message_entries(lines) if entry.get("isCompactSummary")]
        self.assertEqual(len(summaries), 1, f"Expected one compaction summary. Got: {summaries!r}")
        self.assertIn("The HUD redraws every frame.", summaries[0], "Codex replayed the sub-agent answer, so Claude must see it after the boundary")
        self.assertIn("make the game faster", summaries[0], "Codex replayed the user message, so Claude must see it after the boundary")
        self.assertNotIn("permissions instructions", summaries[0], "Codex harness instructions must stay out, because Claude Code adds its own")


class SessionFileTests(unittest.TestCase):
    def test_the_session_lands_where_claude_code_looks_for_its_working_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = pathlib.Path(temporary_directory)
            rollout = write_rollout(temporary / "codex" / "sessions", ROOT_ID, [session_meta(ROOT_ID, 0), turn_context(1), message(2, "user-1", "user", "hello")])
            (temporary / "codex" / "session_index.jsonl").write_text(json.dumps({"id": ROOT_ID, "thread_name": "[09-23][project] say hello"}) + "\n")
            target = codex_to_claude.main(rollout, temporary / "claude-projects")
            lines = load_records(target)
        self.assertEqual(target.parent, temporary / "claude-projects" / "-tmp-project", f"Claude Code lists sessions for /tmp/project only from this directory. Got: {target}")
        self.assertEqual(target.stem, lines[0]["sessionId"], "Claude Code resumes a session by the id in its file name")
        titles = [line.get("customTitle") for line in lines if line["type"] == "custom-title"]
        self.assertEqual(titles, ["[09-23][project] say hello (from Codex)"], f"The /resume list must show the Codex thread name. Got: {titles!r}")

    def test_a_fork_child_is_refused_instead_of_losing_its_parent_history(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = pathlib.Path(temporary_directory)
            sessions = temporary / "codex" / "sessions"
            write_rollout(sessions, ROOT_ID, [session_meta(ROOT_ID, 0), turn_context(1), message(2, "user-1", "user", "parent history")])
            child = write_rollout(sessions, CHILD_ID, [session_meta(CHILD_ID, 3, parent_id=ROOT_ID, fork_ordinal=3), message(4, "user-2", "user", "child history")])
            with self.assertRaises(NotImplementedError, msg="A fork child holds only the turns after its fork point, so converting it alone would lose the parent history"):
                codex_to_claude.main(child, temporary / "claude-projects")
            self.assertFalse((temporary / "claude-projects").exists(), "A refused conversion must not write a partial session")


if __name__ == "__main__":
    unittest.main()
