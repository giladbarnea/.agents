#!/usr/bin/env -S uv run
# /// script
# requires-python = "==3.12.*"
# dependencies = []
# ///

import json
import pathlib
import sys
import tempfile
import unittest

SCRIPTS = pathlib.Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import codex_to_pi

TIMESTAMP = "2026-09-08T12:00:00.000Z"
ROOT_ID = "01a00000-0000-7000-8000-000000000001"
CHILD_ID = "01a00000-0000-7000-8000-000000000002"
SIBLING_ID = "01a00000-0000-7000-8000-000000000003"
GRANDCHILD_ID = "01a00000-0000-7000-8000-000000000004"
SUBAGENT_ID = "01a00000-0000-7000-8000-000000000005"


def record(ordinal: int, record_type: str, payload: dict[str, object]) -> dict[str, object]:
    return {"timestamp": TIMESTAMP, "ordinal": ordinal, "type": record_type, "payload": payload}


def session_meta(
    session_id: str,
    ordinal: int,
    parent_id: str | None = None,
    fork_ordinal: int | None = None,
    source: object = "cli",
) -> dict[str, object]:
    history_base = None
    if parent_id is not None:
        history_base = {
            "thread_id": parent_id,
            "end_ordinal_exclusive": fork_ordinal,
            "end_byte_offset": 1,
        }
    return record(
        ordinal,
        "session_meta",
        {
            "id": session_id,
            "session_id": session_id,
            "timestamp": TIMESTAMP,
            "cwd": "/tmp/project",
            "source": source,
            "forked_from_id": parent_id,
            "forked_from_ordinal_exclusive": fork_ordinal,
            "history_base": history_base,
        },
    )


def turn_context(ordinal: int) -> dict[str, object]:
    return record(ordinal, "turn_context", {"model": "gpt-test", "effort": "high"})


def message(ordinal: int, identifier: str, role: str, text: str) -> dict[str, object]:
    content_type = "output_text" if role == "assistant" else "input_text"
    return record(
        ordinal,
        "response_item",
        {
            "type": "message",
            "id": identifier,
            "role": role,
            "content": [{"type": content_type, "text": text}],
        },
    )


def write_rollout(
    root: pathlib.Path,
    session_id: str,
    records: list[dict[str, object]],
    suffix: str = "",
) -> pathlib.Path:
    path = root / "2026" / "09" / "08" / f"rollout-{session_id}{suffix}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(item) + "\n" for item in records), encoding="utf-8")
    return path


def load_session(path: pathlib.Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def message_texts(entries: list[dict[str, object]]) -> list[str]:
    return [
        str(block["text"])
        for entry in entries
        if entry.get("type") == "message"
        for block in entry["message"].get("content", [])
        if block.get("type") == "text"
    ]


class CodexForkTreeTests(unittest.TestCase):
    def test_selecting_a_child_materializes_its_parent_prefix_as_a_pi_fork(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = pathlib.Path(temporary_directory)
            codex_sessions = temporary / "codex" / "sessions"
            pi_sessions = temporary / "pi" / "sessions"
            write_rollout(
                codex_sessions,
                ROOT_ID,
                [
                    session_meta(ROOT_ID, 0),
                    turn_context(1),
                    message(2, "root-user-shared", "user", "shared question"),
                    message(3, "root-assistant-shared", "assistant", "shared answer"),
                    message(4, "root-user-later", "user", "parent-only continuation"),
                    message(5, "root-assistant-later", "assistant", "parent-only answer"),
                ],
            )
            write_rollout(
                codex_sessions,
                CHILD_ID,
                [
                    session_meta(CHILD_ID, 4, ROOT_ID, 4),
                    turn_context(5),
                    message(6, "child-user", "user", "child question"),
                    message(7, "child-assistant", "assistant", "child answer"),
                ],
            )

            converted = codex_to_pi.convert_fork_tree(
                CHILD_ID,
                codex_sessions,
                pi_sessions,
                "Selected child",
            )

            self.assertEqual(
                set(converted),
                {ROOT_ID, CHILD_ID},
                f"The converter did not materialize the direct fork family: {converted!r}",
            )
            parent_entries = load_session(converted[ROOT_ID])
            child_entries = load_session(converted[CHILD_ID])
            self.assertEqual(
                child_entries[0].get("parentSession"),
                str(converted[ROOT_ID]),
                f"The child does not point to its converted parent: {child_entries[0]!r}",
            )
            self.assertEqual(
                message_texts(child_entries),
                ["shared question", "shared answer", "child question", "child answer"],
                f"The child did not copy exactly the history visible at its fork point: {message_texts(child_entries)!r}",
            )
            self.assertEqual(
                message_texts(parent_entries),
                ["shared question", "shared answer", "parent-only continuation", "parent-only answer"],
                f"Converting the child changed its parent conversation: {message_texts(parent_entries)!r}",
            )
            parent_shared_ids = {
                entry["id"]
                for entry in parent_entries
                if entry.get("type") == "message"
                and any(
                    block.get("text") in {"shared question", "shared answer"}
                    for block in entry["message"].get("content", [])
                )
            }
            child_shared_ids = {
                entry["id"]
                for entry in child_entries
                if entry.get("type") == "message"
                and any(
                    block.get("text") in {"shared question", "shared answer"}
                    for block in entry["message"].get("content", [])
                )
            }
            self.assertEqual(
                child_shared_ids,
                parent_shared_ids,
                "The Pi fork did not preserve the shared parent entry identities",
            )

    def test_paginated_rollout_segments_form_one_complete_session(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = pathlib.Path(temporary_directory)
            codex_sessions = temporary / "codex" / "sessions"
            pi_sessions = temporary / "pi" / "sessions"
            write_rollout(
                codex_sessions,
                ROOT_ID,
                [
                    session_meta(ROOT_ID, 0),
                    turn_context(1),
                    message(2, "root-user-shared", "user", "shared question"),
                    message(3, "root-assistant-shared", "assistant", "shared answer"),
                    message(4, "stale-overlap", "user", "stale overlap"),
                ],
                "-first",
            )
            continuation_meta = session_meta(ROOT_ID, 4)
            continuation_meta["payload"]["history_base"] = {
                "thread_id": ROOT_ID,
                "end_ordinal_exclusive": 4,
                "end_byte_offset": 1,
            }
            write_rollout(
                codex_sessions,
                ROOT_ID,
                [
                    continuation_meta,
                    turn_context(5),
                    message(6, "root-user-later", "user", "current continuation"),
                    message(7, "root-assistant-later", "assistant", "current answer"),
                ],
                "-current",
            )
            write_rollout(
                codex_sessions,
                CHILD_ID,
                [
                    session_meta(CHILD_ID, 4, ROOT_ID, 4),
                    turn_context(5),
                    message(6, "child-user", "user", "child question"),
                    message(7, "child-assistant", "assistant", "child answer"),
                ],
            )

            converted = codex_to_pi.convert_fork_tree(
                CHILD_ID,
                codex_sessions,
                pi_sessions,
                "Selected child",
            )

            parent_texts = message_texts(load_session(converted[ROOT_ID]))
            child_texts = message_texts(load_session(converted[CHILD_ID]))
            self.assertEqual(
                parent_texts,
                ["shared question", "shared answer", "current continuation", "current answer"],
                f"The paginated parent was not rebuilt from its active segment chain: {parent_texts!r}",
            )
            self.assertEqual(
                child_texts,
                ["shared question", "shared answer", "child question", "child answer"],
                f"The child did not fork from the rebuilt parent history: {child_texts!r}",
            )

    def test_selecting_a_middle_node_materializes_the_complete_recursive_fork_tree(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = pathlib.Path(temporary_directory)
            codex_sessions = temporary / "codex" / "sessions"
            pi_sessions = temporary / "pi" / "sessions"
            write_rollout(
                codex_sessions,
                ROOT_ID,
                [
                    session_meta(ROOT_ID, 0),
                    turn_context(1),
                    message(2, "root-user-shared", "user", "shared question"),
                    message(3, "root-assistant-shared", "assistant", "shared answer"),
                    message(4, "root-user-later", "user", "parent-only continuation"),
                    message(5, "root-assistant-later", "assistant", "parent-only answer"),
                ],
            )
            write_rollout(
                codex_sessions,
                CHILD_ID,
                [
                    session_meta(CHILD_ID, 4, ROOT_ID, 4),
                    turn_context(5),
                    message(6, "child-user", "user", "child question"),
                    message(7, "child-assistant", "assistant", "child answer"),
                ],
            )
            write_rollout(
                codex_sessions,
                SIBLING_ID,
                [
                    session_meta(SIBLING_ID, 4, ROOT_ID, 4),
                    turn_context(5),
                    message(6, "sibling-user", "user", "sibling question"),
                    message(7, "sibling-assistant", "assistant", "sibling answer"),
                ],
            )
            write_rollout(
                codex_sessions,
                GRANDCHILD_ID,
                [
                    session_meta(GRANDCHILD_ID, 8, CHILD_ID, 8),
                    turn_context(9),
                    message(10, "grandchild-user", "user", "grandchild question"),
                    message(11, "grandchild-assistant", "assistant", "grandchild answer"),
                ],
            )
            write_rollout(
                codex_sessions,
                SUBAGENT_ID,
                [
                    session_meta(
                        SUBAGENT_ID,
                        4,
                        ROOT_ID,
                        4,
                        {"subagent": {"thread_spawn": {"parent_thread_id": ROOT_ID}}},
                    )
                ],
            )

            converted = codex_to_pi.convert_fork_tree(
                CHILD_ID,
                codex_sessions,
                pi_sessions,
                "Selected child",
            )

            self.assertEqual(
                set(converted),
                {ROOT_ID, CHILD_ID, SIBLING_ID, GRANDCHILD_ID},
                f"Traversal missed a persisted fork or treated a native sub-agent as a fork: {converted!r}",
            )
            child_header = load_session(converted[CHILD_ID])[0]
            sibling_header = load_session(converted[SIBLING_ID])[0]
            grandchild_entries = load_session(converted[GRANDCHILD_ID])
            self.assertEqual(
                child_header.get("parentSession"),
                str(converted[ROOT_ID]),
                f"The selected node lost its parent: {child_header!r}",
            )
            self.assertEqual(
                sibling_header.get("parentSession"),
                str(converted[ROOT_ID]),
                f"The sibling lost its parent: {sibling_header!r}",
            )
            self.assertEqual(
                grandchild_entries[0].get("parentSession"),
                str(converted[CHILD_ID]),
                f"The grandchild lost its parent: {grandchild_entries[0]!r}",
            )
            self.assertEqual(
                message_texts(grandchild_entries),
                [
                    "shared question",
                    "shared answer",
                    "child question",
                    "child answer",
                    "grandchild question",
                    "grandchild answer",
                ],
                f"The grandchild did not inherit its complete fork path: {message_texts(grandchild_entries)!r}",
            )


def convert_root(temporary: pathlib.Path, records: list[dict[str, object]]) -> list[dict[str, object]]:
    rollout = write_rollout(temporary / "codex" / "sessions", ROOT_ID, records)
    return load_session(codex_to_pi.main(rollout, temporary / "pi" / "sessions", "Pi context")[ROOT_ID])


def tool_calls(entries: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    return {
        str(block["name"]): block
        for entry in entries
        if entry.get("type") == "message" and entry["message"]["role"] == "assistant"
        for block in entry["message"]["content"]
        if block["type"] == "toolCall"
    }


def tool_result_texts(entries: list[dict[str, object]]) -> list[str]:
    return [
        str(block["text"])
        for entry in entries
        if entry.get("type") == "message" and entry["message"]["role"] == "toolResult"
        for block in entry["message"]["content"]
        if block["type"] == "text"
    ]


class PiContextTests(unittest.TestCase):
    """What the Pi model reads after the conversion. The restore oracle cannot see these losses, because the originals stay stashed."""

    def test_subagent_coordination_reaches_the_pi_model_with_only_ciphertext_masked(self) -> None:
        spawn_arguments = {"task_name": "hud", "agent_type": "worker", "model": "gpt-6-astra", "message": "gAAAAABq-sealed-by-openai"}
        wait_output = '{"message":"hud finished: 3 files changed","timed_out":false}'
        with tempfile.TemporaryDirectory() as temporary_directory:
            entries = convert_root(
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
        spawn = tool_calls(entries).get("collaboration__spawn_agent", {})
        expected_arguments = {**spawn_arguments, "message": codex_to_pi.ENCRYPTED_PLACEHOLDER}
        self.assertEqual(spawn.get("arguments"), expected_arguments, f"The Pi model must see the spawn call's readable fields, with only the ciphertext masked. Got tool calls: {tool_calls(entries)!r}")
        self.assertIn(wait_output, tool_result_texts(entries), f"The Pi model must read what wait_agent returned. Got: {tool_result_texts(entries)!r}")


    def test_the_compaction_summary_replays_subagent_messages_but_not_harness_injections(self) -> None:
        replacement_history = [
            {"type": "message", "role": "developer", "content": [{"type": "input_text", "text": "<permissions instructions>sandbox</permissions instructions>"}]},
            {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "# AGENTS.md instructions for /tmp/project"}]},
            {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "make the game faster"}]},
            {"type": "agent_message", "author": "/root/hud", "recipient": "/root", "content": [{"type": "input_text", "text": "Message Type: FINAL_ANSWER\nThe HUD redraws every frame."}]},
            {"type": "compaction", "id": "cmp_1", "encrypted_content": "gAAAAABq-compaction-summary"},
        ]
        with tempfile.TemporaryDirectory() as temporary_directory:
            entries = convert_root(
                pathlib.Path(temporary_directory),
                [
                    session_meta(ROOT_ID, 0),
                    turn_context(1),
                    message(2, "user-1", "user", "make the game faster"),
                    record(3, "compacted", {"message": "", "replacement_history": replacement_history}),
                    message(4, "msg-1", "assistant", "Next I will batch the draw calls."),
                ],
            )
        summaries = [str(entry["summary"]) for entry in entries if entry.get("type") == "compaction"]
        self.assertEqual(len(summaries), 1, f"Expected one compaction entry. Got: {summaries!r}")
        self.assertIn("The HUD redraws every frame.", summaries[0], "Codex replayed the sub-agent answer, so the Pi model must see it after the compaction")
        self.assertIn("make the game faster", summaries[0], "Codex replayed the user message, so the Pi model must see it after the compaction")
        self.assertNotIn("AGENTS.md instructions", summaries[0], "Harness injections stay out of Pi's context, as everywhere else in the conversion")
        self.assertNotIn("permissions instructions", summaries[0], "Developer messages stay out of Pi's context, as everywhere else in the conversion")


    def test_bash_rendering_is_used_only_when_every_tool_call_runs_unconditionally(self) -> None:
        conditional = 'if ((await tools.exec_command({cmd:"test -f a.txt"})).exit_code !== 0) {\n  text(await tools.exec_command({cmd:"rm -rf build"}));\n}'
        straight_line = 'const r = await tools.exec_command({cmd:"ls -la"}); text(r.output);'
        with tempfile.TemporaryDirectory() as temporary_directory:
            entries = convert_root(
                pathlib.Path(temporary_directory),
                [
                    session_meta(ROOT_ID, 0),
                    turn_context(1),
                    message(2, "user-1", "user", "clean the build only if a.txt is missing"),
                    record(3, "response_item", {"type": "custom_tool_call", "id": "ctc_1", "call_id": "call_1", "name": "exec", "input": conditional, "status": "completed"}),
                    record(4, "response_item", {"type": "custom_tool_call_output", "call_id": "call_1", "output": [{"type": "input_text", "text": "Script completed"}]}),
                    record(5, "response_item", {"type": "custom_tool_call", "id": "ctc_2", "call_id": "call_2", "name": "exec", "input": straight_line, "status": "completed"}),
                    record(6, "response_item", {"type": "custom_tool_call_output", "call_id": "call_2", "output": [{"type": "input_text", "text": "Script completed"}]}),
                ],
            )
        commands = [
            str(block["arguments"]["command"])
            for entry in entries
            if entry.get("type") == "message" and entry["message"]["role"] == "assistant"
            for block in entry["message"]["content"]
            if block["type"] == "toolCall" and block["name"] == "bash"
        ]
        self.assertEqual(len(commands), 2, f"Expected two bash calls. Got: {commands!r}")
        self.assertIn(conditional, commands[0], f"A script whose condition decides what runs must reach the Pi model whole. A bare 'rm -rf build' line claims it always ran. Got: {commands[0]!r}")
        self.assertEqual(commands[1], "ls -la", "A straight-line script must still render as its shell command")


    def test_namespaced_calls_keep_their_namespace_so_same_named_tools_stay_distinct(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            entries = convert_root(
                pathlib.Path(temporary_directory),
                [
                    session_meta(ROOT_ID, 0),
                    turn_context(1),
                    message(2, "user-1", "user", "take a screenshot, then evaluate 1+1"),
                    record(3, "response_item", {"type": "function_call", "id": "fc_1", "call_id": "call_cua", "namespace": "mcp__cua_repl", "name": "js", "arguments": '{"code":"screenshot()"}'}),
                    record(4, "response_item", {"type": "function_call_output", "call_id": "call_cua", "output": "saved shot.png"}),
                    record(5, "response_item", {"type": "function_call", "id": "fc_2", "call_id": "call_node", "namespace": "mcp__node_repl", "name": "js", "arguments": '{"code":"1+1"}'}),
                    record(6, "response_item", {"type": "function_call_output", "call_id": "call_node", "output": "2"}),
                ],
            )
        names = sorted(
            str(block["name"])
            for entry in entries
            if entry.get("type") == "message" and entry["message"]["role"] == "assistant"
            for block in entry["message"]["content"]
            if block["type"] == "toolCall"
        )
        self.assertEqual(names, ["mcp__cua_repl__js", "mcp__node_repl__js"], f"Two servers' js tools must stay distinct for the Pi model, as they do in the Claude conversion. Got: {names!r}")


    def test_notes_and_history_calls_reach_the_pi_model_with_only_ciphertext_masked(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            entries = convert_root(
                pathlib.Path(temporary_directory),
                [
                    session_meta(ROOT_ID, 0),
                    turn_context(1),
                    message(2, "user-1", "user", "save a checkpoint, then find my earlier request"),
                    record(3, "response_item", {"type": "function_call", "id": "fc_1", "call_id": "call_note", "namespace": "notes", "name": "append_to_file", "arguments": '{"path":"checkpoint","text":"gAAAAABq-note"}'}),
                    record(4, "response_item", {"type": "function_call_output", "call_id": "call_note", "output": [{"type": "encrypted_content", "encrypted_content": "gAAAAABq-ack"}]}),
                    record(5, "response_item", {"type": "function_call", "id": "fc_2", "call_id": "call_search", "namespace": "history", "name": "search_contents", "arguments": '{"role":"user","limit":2,"query":"gAAAAABq-query"}'}),
                    record(6, "response_item", {"type": "function_call_output", "call_id": "call_search", "output": [{"type": "encrypted_content", "encrypted_content": "gAAAAABq-results"}]}),
                ],
            )
        calls = tool_calls(entries)
        placeholder = codex_to_pi.ENCRYPTED_PLACEHOLDER
        self.assertEqual(calls.get("notes__append_to_file", {}).get("arguments"), {"path": "checkpoint", "text": placeholder}, f"The Pi model must see which note was written, with only its text masked. Got tool calls: {calls!r}")
        self.assertEqual(calls.get("history__search_contents", {}).get("arguments"), {"role": "user", "limit": 2, "query": placeholder}, f"The Pi model must see the history search, with only its query masked. Got tool calls: {calls!r}")


    def test_ciphertext_inside_messages_and_outputs_shows_as_a_placeholder(self) -> None:
        delivery = [
            {"type": "input_text", "text": "Message Type: MESSAGE\nTask name: /root\nSender: /root/worker\nPayload:\n"},
            {"type": "encrypted_content", "encrypted_content": "gAAAAABq-progress"},
        ]
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = pathlib.Path(temporary_directory)
            sessions = temporary / "codex" / "sessions"
            write_rollout(
                sessions,
                SUBAGENT_ID,
                [session_meta(SUBAGENT_ID, 0, source={"subagent": {"thread_spawn": {"parent_thread_id": ROOT_ID, "agent_nickname": "worker"}}}), turn_context(1)],
            )
            rollout = write_rollout(
                sessions,
                ROOT_ID,
                [
                    session_meta(ROOT_ID, 0),
                    turn_context(1),
                    message(2, "user-1", "user", "save a checkpoint and delegate"),
                    record(3, "response_item", {"type": "function_call", "id": "fc_1", "call_id": "call_note", "namespace": "notes", "name": "append_to_file", "arguments": '{"path":"checkpoint","text":"gAAAAABq-note"}'}),
                    record(4, "response_item", {"type": "function_call_output", "call_id": "call_note", "output": [{"type": "encrypted_content", "encrypted_content": "gAAAAABq-ack"}]}),
                    record(5, "event_msg", {"type": "sub_agent_activity", "item": {"type": "SubAgentActivity", "kind": "started", "agent_thread_id": SUBAGENT_ID, "agent_path": "/root/worker"}}),
                    record(6, "response_item", {"type": "agent_message", "author": "/root/worker", "recipient": "/root", "content": delivery}),
                ],
            )
            entries = load_session(codex_to_pi.main(rollout, temporary / "pi" / "sessions", "Pi context")[ROOT_ID])
        placeholder = codex_to_pi.ENCRYPTED_PLACEHOLDER
        notifications = [str(entry["content"]) for entry in entries if entry.get("type") == "custom_message"]
        self.assertEqual(len(notifications), 1, f"Expected one sub-agent notification. Got: {notifications!r}")
        self.assertIn(placeholder, notifications[0], f"The sub-agent's encrypted payload must show as a placeholder, not as an empty payload. Got: {notifications[0]!r}")
        self.assertIn(placeholder, tool_result_texts(entries), f"The encrypted notes output must show as a placeholder, not as an empty result. Got: {tool_result_texts(entries)!r}")


if __name__ == "__main__":
    unittest.main()
