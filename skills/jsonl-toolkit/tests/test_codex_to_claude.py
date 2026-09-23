#!/usr/bin/env -S uv run
# /// script
# requires-python = "==3.12.*"
# dependencies = []
# ///
"""What the Claude model reads after Codex → Claude Code, and the rules the Claude API enforces on it.

The API rules below were each found by a real `claude --resume` that failed without them:
an unknown key inside a content block is rejected, a thinking block signed by another vendor
is rejected unless the message names a non-Claude model, and every tool_use needs its
tool_result in the next message. `test_codex_restore.py` checks that the records come back.
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
from test_codex_restore import NESTED_ID, delivery, subagent_meta, subagent_started
from test_codex_to_pi import CHILD_ID, ROOT_ID, SUBAGENT_ID, message, record, session_meta, turn_context, write_rollout

FIXTURE_SESSIONS = pathlib.Path(__file__).resolve().parent / "fixtures" / "codex" / "sessions"
FIXTURE_ROOTS = ("rollout-2026-09-05T10-46-02-01a07088-19c9-7532-a9fe-b264c55379f0.jsonl", "rollout-2026-09-08T10-32-19-01a07fee-9ed9-70b0-b6c1-85cc01822d5d.jsonl")
ALLOWED_BLOCK_KEYS = {
    "text": {"type", "text"},
    "thinking": {"type", "thinking", "signature"},
    "tool_use": {"type", "id", "name", "input"},
    "tool_result": {"type", "tool_use_id", "content", "is_error"},
    "image": {"type", "source"},
}
CIPHERTEXT = "gAAAAABq-sealed-by-openai"

Lines = list[dict[str, object]]


def load_records(path: pathlib.Path) -> Lines:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").split("\n") if line]


def message_entries(lines: Lines) -> Lines:
    return [line for line in lines if "message" in line]


def blocks(entry: dict[str, object]) -> Lines:
    content = entry["message"]["content"]
    return content if isinstance(content, list) else [{"type": "text", "text": content}]


def claude_visible_text(lines: Lines) -> str:
    """Everything the Claude model reads. Thinking is excluded, because Claude Code drops foreign thinking."""
    return json.dumps([block for entry in message_entries(lines) for block in blocks(entry) if block["type"] != "thinking"])


def stored_ciphertexts(records: Lines) -> set[str]:
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


def convert(temporary: pathlib.Path, rollouts: dict[str, Lines], selected: str = ROOT_ID) -> dict[str, Lines]:
    """Write the rollouts, convert the tree that holds the selected one, and read back every Claude session by Codex id."""
    paths = {session_id: write_rollout(temporary / "codex" / "sessions", session_id, records) for session_id, records in rollouts.items()}
    converted = codex_to_claude.main(paths[selected], temporary / "claude")
    return {session_id: load_records(path) for session_id, path in converted.items()}


def tool_uses(lines: Lines) -> dict[str, dict[str, object]]:
    return {block["name"]: block for entry in message_entries(lines) for block in blocks(entry) if block["type"] == "tool_use"}


def tool_result_texts(lines: Lines) -> list[str]:
    return [
        inner["text"]
        for entry in message_entries(lines)
        for block in blocks(entry)
        if block["type"] == "tool_result"
        for inner in (block["content"] if isinstance(block["content"], list) else [{"text": block["content"]}])
    ]


def texts(lines: Lines, role: str) -> list[str]:
    return [block["text"] for entry in message_entries(lines) if entry["type"] == role for block in blocks(entry) if block["type"] == "text"]


class RealSessionTests(unittest.TestCase):
    def test_fixture_sessions_obey_the_rules_the_claude_api_enforces(self) -> None:
        for root in FIXTURE_ROOTS:
            with tempfile.TemporaryDirectory() as temporary_directory:
                converted = codex_to_claude.main(FIXTURE_SESSIONS / root, pathlib.Path(temporary_directory))
                sessions = {session_id: load_records(path) for session_id, path in converted.items()}
            for session_id, lines in sessions.items():
                with self.subTest(codex_session=session_id):
                    entries = message_entries(lines)
                    ciphertexts = stored_ciphertexts([line["codex"] for line in lines if "codex" in line])
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


class ContentTests(unittest.TestCase):
    def test_an_exec_script_reaches_claude_as_the_exact_javascript_and_output(self) -> None:
        script = 'if ((await tools.exec_command({cmd:"test -f a.txt"})).exit_code !== 0) {\n  text(await tools.exec_command({cmd:"rm -rf build"}));\n}'
        envelope = 'Script completed\nWall time 0.2 seconds\nOutput:\n{"chunk_id":"c1","exit_code":1,"output":""}'
        with tempfile.TemporaryDirectory() as temporary_directory:
            lines = convert(pathlib.Path(temporary_directory), {ROOT_ID: [
                session_meta(ROOT_ID, 0),
                turn_context(1),
                message(2, "user-1", "user", "clean the build only if a.txt is missing"),
                record(3, "response_item", {"type": "custom_tool_call", "id": "ctc_1", "call_id": "call_exec", "name": "exec", "input": script, "status": "completed"}),
                record(4, "response_item", {"type": "custom_tool_call_output", "call_id": "call_exec", "output": [{"type": "input_text", "text": envelope}]}),
            ]})[ROOT_ID]
        call = tool_uses(lines).get("exec", {})
        self.assertEqual(call.get("input"), {"input": script}, f"Claude must see the script itself, with its condition. Got tool calls: {tool_uses(lines)!r}")
        self.assertIn(envelope, tool_result_texts(lines), f"Claude must see the output Codex saw. Got: {tool_result_texts(lines)!r}")

    def test_subagent_coordination_stays_readable_and_only_ciphertext_is_masked(self) -> None:
        spawn_arguments = {"task_name": "hud", "agent_type": "worker", "model": "gpt-6-astra", "message": CIPHERTEXT}
        wait_output = '{"message":"hud finished: 3 files changed","timed_out":false}'
        with tempfile.TemporaryDirectory() as temporary_directory:
            lines = convert(pathlib.Path(temporary_directory), {ROOT_ID: [
                session_meta(ROOT_ID, 0),
                turn_context(1),
                message(2, "user-1", "user", "delegate the HUD work"),
                record(3, "response_item", {"type": "function_call", "id": "fc_1", "call_id": "call_spawn", "namespace": "collaboration", "name": "spawn_agent", "arguments": json.dumps(spawn_arguments)}),
                record(4, "response_item", {"type": "function_call_output", "call_id": "call_spawn", "output": '{"task_name":"/root/hud"}'}),
                record(5, "response_item", {"type": "function_call", "id": "fc_2", "call_id": "call_wait", "namespace": "collaboration", "name": "wait_agent", "arguments": '{"timeout_ms":60000}'}),
                record(6, "response_item", {"type": "function_call_output", "call_id": "call_wait", "output": wait_output}),
            ]})[ROOT_ID]
        spawn = tool_uses(lines).get("collaboration__spawn_agent", {})
        expected_input = {**spawn_arguments, "message": codex_to_claude.ENCRYPTED_PLACEHOLDER}
        self.assertEqual(spawn.get("input"), expected_input, f"The spawn call must show its readable fields and mask only the ciphertext. Got tool calls: {tool_uses(lines)!r}")
        self.assertIn(wait_output, tool_result_texts(lines), f"Claude must read what wait_agent returned. Got: {tool_result_texts(lines)!r}")

    def test_a_reasoning_summary_reaches_claude_as_text_the_way_pi_shows_foreign_thinking(self) -> None:
        summarized = {"type": "reasoning", "id": "rs_1", "summary": [{"type": "summary_text", "text": "**Checking the build** The linker cannot find libfoo."}], "encrypted_content": CIPHERTEXT}
        unsummarized = {"type": "reasoning", "id": "rs_2", "summary": [], "encrypted_content": CIPHERTEXT + "-2"}
        with tempfile.TemporaryDirectory() as temporary_directory:
            lines = convert(pathlib.Path(temporary_directory), {ROOT_ID: [
                session_meta(ROOT_ID, 0),
                turn_context(1),
                message(2, "user-1", "user", "why does the build fail?"),
                record(3, "response_item", summarized),
                record(4, "response_item", unsummarized),
                message(5, "msg-1", "assistant", "The linker cannot find libfoo."),
            ]})[ROOT_ID]
        self.assertIn("**Checking the build** The linker cannot find libfoo.", texts(lines, "assistant"), "Claude Code drops foreign thinking blocks, so a readable summary must be text to reach Claude")
        thinking = [block for entry in message_entries(lines) for block in blocks(entry) if block["type"] == "thinking"]
        self.assertEqual(len(thinking), 1, f"Reasoning with nothing readable stays a thinking block, which Claude Code drops. Got: {thinking!r}")

    def test_the_compaction_summary_replays_subagent_messages_but_not_harness_instructions(self) -> None:
        replacement_history = [
            {"type": "message", "role": "developer", "content": [{"type": "input_text", "text": "<permissions instructions>sandbox</permissions instructions>"}]},
            {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "make the game faster"}]},
            {"type": "agent_message", "author": "/root/hud", "recipient": "/root", "content": [{"type": "input_text", "text": "Message Type: FINAL_ANSWER\nThe HUD redraws every frame."}]},
            {"type": "compaction", "id": "cmp_1", "encrypted_content": CIPHERTEXT},
        ]
        with tempfile.TemporaryDirectory() as temporary_directory:
            lines = convert(pathlib.Path(temporary_directory), {ROOT_ID: [
                session_meta(ROOT_ID, 0),
                turn_context(1),
                message(2, "user-1", "user", "make the game faster"),
                record(3, "compacted", {"message": "", "replacement_history": replacement_history}),
                message(4, "msg-1", "assistant", "Next I will batch the draw calls."),
            ]})[ROOT_ID]
        summaries = [entry["message"]["content"] for entry in message_entries(lines) if entry.get("isCompactSummary")]
        self.assertEqual(len(summaries), 1, f"Expected one compaction summary. Got: {summaries!r}")
        self.assertIn("The HUD redraws every frame.", summaries[0], "Codex replayed the sub-agent answer, so Claude must see it after the boundary")
        self.assertIn("make the game faster", summaries[0], "Codex replayed the user message, so Claude must see it after the boundary")
        self.assertNotIn("permissions instructions", summaries[0], "Codex harness instructions must stay out, because Claude Code adds its own")


class SessionTreeTests(unittest.TestCase):
    def test_a_fork_child_shows_claude_its_parent_history_the_way_claude_forks_do(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            sessions = convert(pathlib.Path(temporary_directory), {
                ROOT_ID: [session_meta(ROOT_ID, 0), turn_context(1), message(2, "user-1", "user", "shared question"), message(3, "msg-1", "assistant", "shared answer"), message(4, "user-2", "user", "parent-only question")],
                CHILD_ID: [session_meta(CHILD_ID, 4, ROOT_ID, 4), turn_context(5), message(6, "user-3", "user", "child question")],
            }, selected=CHILD_ID)
        child_texts = [*texts(sessions[CHILD_ID], "user"), *texts(sessions[CHILD_ID], "assistant")]
        self.assertEqual(sorted(child_texts), ["child question", "shared answer", "shared question"], f"Claude must see the history before the fork point, and nothing after it. Got: {child_texts!r}")
        parent_ids = {line["uuid"] for line in message_entries(sessions[ROOT_ID])}
        copied = [line for line in message_entries(sessions[CHILD_ID]) if line["uuid"] in parent_ids]
        self.assertEqual(len(copied), 2, "The child copies the parent's entries with their ids, the way `claude --fork-session` does")
        self.assertEqual({line["sessionId"] for line in copied}, {sessions[CHILD_ID][0]["sessionId"]}, "Copied entries must carry the child's session id")

    def test_each_session_lands_where_claude_code_looks_and_names_its_parent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = pathlib.Path(temporary_directory)
            (temporary / "codex").mkdir()
            (temporary / "codex" / "session_index.jsonl").write_text(json.dumps({"id": ROOT_ID, "thread_name": "[09-23][project] audit"}) + "\n")
            rollouts = {
                SUBAGENT_ID: [subagent_meta(SUBAGENT_ID, ROOT_ID, "/root/auditor", "auditor"), turn_context(1), subagent_started(2, NESTED_ID, "/root/auditor/reader")],
                NESTED_ID: [subagent_meta(NESTED_ID, SUBAGENT_ID, "/root/auditor/reader", "reader"), turn_context(1)],
                ROOT_ID: [session_meta(ROOT_ID, 0), turn_context(1), subagent_started(2, SUBAGENT_ID, "/root/auditor"), delivery(3, "/root/auditor", "/root", "Message Type: FINAL_ANSWER\nclean")],
            }
            paths = {session_id: write_rollout(temporary / "codex" / "sessions", session_id, records) for session_id, records in rollouts.items()}
            converted = codex_to_claude.main(paths[ROOT_ID], temporary / "claude")
            titles = {session_id: [line.get("customTitle") for line in load_records(path) if line["type"] == "custom-title"] for session_id, path in converted.items()}
            first_lines = {session_id: load_records(path)[0] for session_id, path in converted.items()}
        for session_id, path in converted.items():
            self.assertEqual(path.parent, temporary / "claude" / "-tmp-project", f"Claude Code lists sessions for /tmp/project only from this directory. Got: {path}")
            self.assertEqual(path.stem, first_lines[session_id]["sessionId"], "Claude Code resumes a session by the id in its file name")
        self.assertEqual(titles[ROOT_ID], ["[09-23][project] audit (from Codex)"], "The /resume list must show the Codex thread name")
        self.assertEqual(
            titles[NESTED_ID],
            ["[09-23][project] audit — sub-agent /root/auditor (auditor) — sub-agent /root/auditor/reader (reader) (from Codex)"],
            "A sub-agent session must name the chain of sessions above it, because Claude Code has no parent link",
        )


if __name__ == "__main__":
    unittest.main()
