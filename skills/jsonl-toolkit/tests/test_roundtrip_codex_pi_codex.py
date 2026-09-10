#!/usr/bin/env -S uv run
# /// script
# requires-python = "==3.12.*"
# dependencies = []
# ///
"""Codex → Pi → Codex must keep every byte the model reads or writes.

The oracle is `model_facing`: a projection of a Codex rollout onto the fields that enter
or leave the model. Ids, timestamps, ordinals, token usage, events, and the harness
injections that codex_to_pi drops on purpose are outside the projection.
"""

import json
import pathlib
import sys
import tempfile
import unittest

SCRIPTS = pathlib.Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import codex_to_pi
import pi_to_codex
from test_codex_to_pi import ROOT_ID, SUBAGENT_ID, message, record, session_meta, turn_context, write_rollout

ModelFact = tuple[object, ...]


def content_blocks(content: str | list[dict[str, object]]) -> tuple[ModelFact, ...]:
    if isinstance(content, str):
        return (("text", content),)
    blocks: list[ModelFact] = []
    for block in content:
        if block["type"] in ("input_text", "output_text"):
            blocks.append(("text", block["text"]))
        elif block["type"] == "input_image":
            blocks.append(("image", block["image_url"], block.get("detail")))
        elif block["type"] == "encrypted_content":
            blocks.append(("encrypted", block["encrypted_content"]))
        else:
            raise AssertionError(f"projection does not know content block {block!r}")
    return tuple(blocks)


def model_facing_item(payload: dict[str, object]) -> ModelFact | None:
    item_type = payload["type"]
    if item_type == "reasoning":
        summary = tuple(str(part["text"]) for part in payload.get("summary") or [])
        return ("reasoning", payload.get("encrypted_content"), summary)
    if item_type == "message" and payload["role"] == "developer":
        return None
    if item_type == "message" and payload["role"] == "user":
        blocks = content_blocks(payload["content"])
        first_text = next((str(block[1]) for block in blocks if block[0] == "text"), "")
        if first_text.startswith(codex_to_pi.INJECTED_USER_PREFIXES):
            return None
        return ("user", blocks)
    if item_type == "message":
        return ("assistant", content_blocks(payload["content"]))
    if item_type == "custom_tool_call":
        return ("custom_tool_call", payload["name"], payload["input"])
    if item_type == "function_call":
        return ("function_call", payload.get("namespace"), payload["name"], payload["arguments"])
    if item_type in ("custom_tool_call_output", "function_call_output"):
        return (item_type, content_blocks(payload["output"]))
    if item_type == "agent_message":
        return ("agent_message", payload["author"], payload["recipient"], content_blocks(payload["content"]))
    if item_type == "tool_search_call":
        return ("tool_search_call", json.dumps(payload["arguments"], sort_keys=True))
    if item_type == "tool_search_output":
        return ("tool_search_output", json.dumps(payload["tools"], sort_keys=True))
    if item_type == "compaction":
        return ("compaction", payload["encrypted_content"])
    raise AssertionError(f"projection does not know response item {item_type!r}")


def model_facing(records: list[dict[str, object]]) -> list[ModelFact]:
    """Project rollout records onto the facts the model reads or writes, in order.

    >>> model_facing([{"type": "event_msg", "payload": {}}, {"type": "response_item", "payload": {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "hi"}]}}])
    [('assistant', (('text', 'hi'),))]
    """
    facts: list[ModelFact] = []
    for entry in records:
        if entry["type"] == "response_item":
            fact = model_facing_item(entry["payload"])
            if fact is not None:
                facts.append(fact)
        elif entry["type"] == "compacted":
            replacement = entry["payload"]["replacement_history"]
            facts.append(("compacted", tuple(fact for fact in map(model_facing_item, replacement) if fact is not None)))
    return facts


def reasoning(ordinal: int, identifier: str, encrypted: str, summary: list[str] | None = None) -> dict[str, object]:
    payload: dict[str, object] = {
        "type": "reasoning",
        "id": identifier,
        "encrypted_content": encrypted,
        "internal_chat_message_metadata_passthrough": {"turn_id": "turn-1"},
    }
    if summary is not None:
        payload["summary"] = [{"type": "summary_text", "text": text} for text in summary]
    return record(ordinal, "response_item", payload)


def exec_call(ordinal: int, call_id: str, script: str) -> dict[str, object]:
    payload = {"type": "custom_tool_call", "id": f"ctc_{call_id}", "call_id": call_id, "name": "exec", "input": script, "status": "completed"}
    return record(ordinal, "response_item", payload)


def exec_output(ordinal: int, call_id: str, chunks: list[str]) -> dict[str, object]:
    output = [{"type": "input_text", "text": chunk} for chunk in chunks]
    return record(ordinal, "response_item", {"type": "custom_tool_call_output", "call_id": call_id, "output": output})


def function_call(ordinal: int, call_id: str, name: str, arguments: str, namespace: str | None = None) -> dict[str, object]:
    payload: dict[str, object] = {"type": "function_call", "id": f"fc_{call_id}", "call_id": call_id, "name": name, "arguments": arguments}
    if namespace is not None:
        payload["namespace"] = namespace
    return record(ordinal, "response_item", payload)


def function_output(ordinal: int, call_id: str, output: str | list[str]) -> dict[str, object]:
    value = output if isinstance(output, str) else [{"type": "input_text", "text": chunk} for chunk in output]
    return record(ordinal, "response_item", {"type": "function_call_output", "call_id": call_id, "output": value})


EXEC_SCRIPT ='text(await tools.exec_command({cmd:"npm test 2>&1 | tail -20",workdir:"/tmp/project",yield_time_ms:10000,max_output_tokens:8000}));'
POLL_SCRIPT = 'text(await tools.write_stdin({session_id:42,chars:"",yield_time_ms:5000}));'
RUNNING_ENVELOPE = 'Script completed\nWall time 10.0 seconds\nOutput:\n{"chunk_id":"a1","original_token_count":12,"output":"> project@1.0.0 test\\n","session_id":42,"wall_time_seconds":10.0}'
FINISHED_ENVELOPE = 'Script completed\nWall time 3.1 seconds\nOutput:\n{"chunk_id":"a2","exit_code":1,"original_token_count":40,"output":"FAIL tests/build.test.ts\\n","wall_time_seconds":3.1}'


def load_records(path: pathlib.Path) -> list[dict[str, object]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def roundtrip(temporary: pathlib.Path, records: list[dict[str, object]]) -> tuple[list[ModelFact], list[ModelFact]]:
    codex_sessions = temporary / "codex" / "sessions"
    pi_sessions = temporary / "pi" / "sessions"
    rollout = write_rollout(codex_sessions, ROOT_ID, records)
    converted = codex_to_pi.main(rollout, pi_sessions, "Round trip")
    restored = pi_to_codex.main(converted[ROOT_ID], temporary / "restored")
    return model_facing(load_records(rollout)), model_facing(load_records(restored))


class RoundTripTests(unittest.TestCase):
    def assert_same_model_facts(self, original: list[ModelFact], restored: list[ModelFact]) -> None:
        first_difference = next((index for index, pair in enumerate(zip(original, restored, strict=False)) if pair[0] != pair[1]), None)
        self.assertEqual(
            restored,
            original,
            f"Round trip changed model-facing data. First difference at fact {first_difference}: "
            f"original={original[first_difference] if first_difference is not None else None!r} "
            f"restored={restored[first_difference] if first_difference is not None else None!r}. "
            f"Counts: original={len(original)} restored={len(restored)}",
        )

    def test_text_and_encrypted_reasoning_survive(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            original, restored = roundtrip(
                pathlib.Path(temporary_directory),
                [
                    session_meta(ROOT_ID, 0),
                    turn_context(1),
                    message(2, "user-1", "user", "<environment_context>injected by the harness</environment_context>"),
                    message(3, "user-2", "user", "why does the build fail?"),
                    reasoning(4, "rs_1", "gAAAAAB-first-thought"),
                    reasoning(5, "rs_2", "gAAAAAB-second-thought", ["Looking at the build log"]),
                    message(6, "msg-1", "assistant", "The linker cannot find libfoo."),
                ],
            )
            self.assertEqual(len(original), 4, f"The projection must skip the injected message only. Got: {original!r}")
            self.assert_same_model_facts(original, restored)

    def test_exec_scripts_and_output_envelopes_survive_byte_for_byte(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            original, restored = roundtrip(
                pathlib.Path(temporary_directory),
                [
                    session_meta(ROOT_ID, 0),
                    turn_context(1),
                    message(2, "user-1", "user", "run the tests"),
                    exec_call(3, "call_run", EXEC_SCRIPT),
                    exec_output(4, "call_run", ["Script completed\nWall time 10.0 seconds\nOutput:\n", RUNNING_ENVELOPE.partition("Output:\n")[2]]),
                    exec_call(5, "call_poll", POLL_SCRIPT),
                    exec_output(6, "call_poll", [FINISHED_ENVELOPE]),
                    message(7, "msg-1", "assistant", "One test fails."),
                ],
            )
            scripts = [fact[2] for fact in original if fact[0] == "custom_tool_call"]
            self.assertEqual(scripts, [EXEC_SCRIPT, POLL_SCRIPT], f"The fixture must carry the model's own scripts. Got: {scripts!r}")
            self.assert_same_model_facts(original, restored)

    def test_function_calls_keep_their_argument_bytes_and_the_user_answer(self) -> None:
        question = '{"questions":[{"title":"May I run the browser test?","options":["Yes","Code checks only"]}]}'
        with tempfile.TemporaryDirectory() as temporary_directory:
            original, restored = roundtrip(
                pathlib.Path(temporary_directory),
                [
                    session_meta(ROOT_ID, 0),
                    turn_context(1),
                    message(2, "user-1", "user", "keep waiting for the build"),
                    function_call(3, "call_wait", "wait", '{"cell_id":"10","yield_time_ms":30000,"max_tokens":30000}'),
                    function_output(4, "call_wait", ["Script completed\nWall time 4.2 seconds\nOutput:\n", "build done\n"]),
                    function_call(5, "call_ask", "request_user_input_async", question),
                    function_output(6, "call_ask", '{"accepted":true}'),
                    message(7, "user-2", "user", "Yes"),
                    message(8, "msg-1", "assistant", "Running the browser test."),
                ],
            )
            answers = [fact for fact in original if fact[0] == "function_call_output"]
            self.assertEqual(len(answers), 2, f"The fixture must carry both tool answers. Got: {answers!r}")
            self.assert_same_model_facts(original, restored)

    def test_images_survive_in_user_messages_and_tool_outputs(self) -> None:
        screenshot = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        user_content = [
            {"type": "input_text", "text": "why is this button clipped?"},
            {"type": "input_image", "image_url": screenshot, "detail": "high"},
        ]
        with tempfile.TemporaryDirectory() as temporary_directory:
            original, restored = roundtrip(
                pathlib.Path(temporary_directory),
                [
                    session_meta(ROOT_ID, 0),
                    turn_context(1),
                    record(2, "response_item", {"type": "message", "id": "user-1", "role": "user", "content": user_content}),
                    function_call(3, "call_view", "view_image", '{"path":"/tmp/project/button.png"}'),
                    record(4, "response_item", {"type": "function_call_output", "call_id": "call_view", "output": [{"type": "input_image", "image_url": screenshot, "detail": "auto"}]}),
                    message(5, "msg-1", "assistant", "The container has overflow hidden."),
                ],
            )
            images = [block for fact in original for block in fact[-1] if isinstance(block, tuple) and block[0] == "image"]
            self.assertEqual(len(images), 2, f"The fixture must carry two images. Got: {images!r}")
            self.assert_same_model_facts(original, restored)

    def test_compaction_keeps_the_encrypted_summary_and_the_replayed_user_messages(self) -> None:
        kept_user = {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "why does the build fail?"}]}
        summary = {"type": "compaction", "id": "cmp_1", "encrypted_content": "gAAAAAB-compaction-summary"}
        compacted = {
            "message": "",
            "replacement_history": [kept_user, summary],
            "latest_token_usage_record": {"usage": {"total_tokens": 180000}},
            "window_id": "w2",
            "window_number": 2,
            "previous_window_id": "w1",
            "first_window_id": "w1",
        }
        with tempfile.TemporaryDirectory() as temporary_directory:
            original, restored = roundtrip(
                pathlib.Path(temporary_directory),
                [
                    session_meta(ROOT_ID, 0),
                    turn_context(1),
                    message(2, "user-1", "user", "why does the build fail?"),
                    reasoning(3, "rs_1", "gAAAAAB-thought"),
                    message(4, "msg-1", "assistant", "Investigating."),
                    record(5, "compacted", compacted),
                    message(6, "user-2", "user", "and now?"),
                    message(7, "msg-2", "assistant", "Fixed by relinking libfoo."),
                ],
            )
            compaction_facts = [fact for fact in original if fact[0] == "compacted"]
            self.assertEqual(len(compaction_facts), 1, f"The fixture must carry one compaction. Got: {compaction_facts!r}")
            self.assert_same_model_facts(original, restored)

    def test_ciphertext_only_calls_and_their_outputs_survive_in_sequence(self) -> None:
        spawn_arguments = '{"task":"gAAAAAB-encrypted-task","agent_type":"worker"}'
        with tempfile.TemporaryDirectory() as temporary_directory:
            original, restored = roundtrip(
                pathlib.Path(temporary_directory),
                [
                    session_meta(ROOT_ID, 0),
                    turn_context(1),
                    message(2, "user-1", "user", "spawn a worker and note the plan"),
                    function_call(3, "call_spawn", "spawn_agent", spawn_arguments, namespace="collaboration"),
                    function_output(4, "call_spawn", '{"agent_path":"/root/worker","status":"running"}'),
                    function_call(5, "call_note", "append_to_file", '{"content":"gAAAAAB-encrypted-note"}', namespace="notes"),
                    function_output(6, "call_note", "gAAAAAB-encrypted-ack"),
                    message(7, "msg-1", "assistant", "Worker spawned and plan noted."),
                ],
            )
            namespaces = [fact[1] for fact in original if fact[0] == "function_call"]
            self.assertEqual(namespaces, ["collaboration", "notes"], f"The fixture must carry both namespaced calls. Got: {namespaces!r}")
            self.assert_same_model_facts(original, restored)

    def test_tool_search_calls_survive_as_tool_calls(self) -> None:
        search_call = {"type": "tool_search_call", "id": "tsc_1", "call_id": "call_search", "status": "completed", "execution": "client", "arguments": {"query": "screenshot macOS window"}}
        search_output = {"type": "tool_search_output", "id": "tso_1", "call_id": "call_search", "status": "completed", "execution": "client", "tools": [{"type": "namespace", "name": "mcp__node_repl", "description": "Run JavaScript"}]}
        with tempfile.TemporaryDirectory() as temporary_directory:
            original, restored = roundtrip(
                pathlib.Path(temporary_directory),
                [
                    session_meta(ROOT_ID, 0),
                    turn_context(1),
                    message(2, "user-1", "user", "take a screenshot"),
                    record(3, "response_item", search_call),
                    record(4, "response_item", search_output),
                    message(5, "msg-1", "assistant", "I will use the node repl."),
                ],
            )
            searches = [fact for fact in original if fact[0] in ("tool_search_call", "tool_search_output")]
            self.assertEqual(len(searches), 2, f"The fixture must carry the search call and its output. Got: {searches!r}")
            self.assert_same_model_facts(original, restored)

    def test_subagent_deliveries_and_the_subagent_session_survive(self) -> None:
        delivery = "Message Type: FINAL_ANSWER\nTask name: /root\nSender: /root/worker\nPayload:\nThe flaky test is tests/build.test.ts."
        task_content = [
            {"type": "input_text", "text": "Message Type: NEW_TASK\nTask name: /root/worker\nSender: /root\nPayload:"},
            {"type": "encrypted_content", "encrypted_content": "gAAAAAB-encrypted-task"},
        ]
        root_records = [
            session_meta(ROOT_ID, 0),
            turn_context(1),
            message(2, "user-1", "user", "find the flaky test"),
            function_call(3, "call_spawn", "spawn_agent", '{"task":"gAAAAAB-encrypted-task"}', namespace="collaboration"),
            record(4, "event_msg", {"type": "sub_agent_activity", "item": {"type": "SubAgentActivity", "kind": "started", "agent_thread_id": SUBAGENT_ID, "agent_path": "/root/worker"}}),
            function_output(5, "call_spawn", '{"agent_path":"/root/worker"}'),
            record(6, "response_item", {"type": "agent_message", "author": "/root/worker", "recipient": "/root", "content": [{"type": "input_text", "text": delivery}]}),
            message(7, "msg-1", "assistant", "The worker found it: tests/build.test.ts."),
        ]
        subagent_records = [
            session_meta(SUBAGENT_ID, 0, source={"subagent": {"thread_spawn": {"parent_thread_id": ROOT_ID, "agent_nickname": "worker"}}}),
            turn_context(1),
            record(2, "response_item", {"type": "agent_message", "author": "/root", "recipient": "/root/worker", "content": task_content}),
            reasoning(3, "rs_w1", "gAAAAAB-worker-thought"),
            message(4, "msg-w1", "assistant", "The flaky test is tests/build.test.ts."),
        ]
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = pathlib.Path(temporary_directory)
            codex_sessions = temporary / "codex" / "sessions"
            pi_sessions = temporary / "pi" / "sessions"
            root_rollout = write_rollout(codex_sessions, ROOT_ID, root_records)
            subagent_rollout = write_rollout(codex_sessions, SUBAGENT_ID, subagent_records)
            converted = codex_to_pi.main(root_rollout, pi_sessions, "Round trip")
            pi_root = converted[ROOT_ID]
            pi_children = [path for path in pi_sessions.rglob("*.jsonl") if load_records(path)[0].get("parentSession") == str(pi_root)]
            self.assertEqual(len(pi_children), 1, f"The sub-agent must become exactly one Pi child session of the root. Got: {pi_children!r}")

            restored_root = pi_to_codex.main(pi_root, temporary / "restored")
            restored_child = pi_to_codex.main(pi_children[0], temporary / "restored")

            original_root = model_facing(load_records(root_rollout))
            deliveries = [fact for fact in original_root if fact[0] == "agent_message"]
            self.assertEqual(len(deliveries), 1, f"The fixture must carry one delivery to the root. Got: {deliveries!r}")
            self.assert_same_model_facts(original_root, model_facing(load_records(restored_root)))
            self.assert_same_model_facts(model_facing(load_records(subagent_rollout)), model_facing(load_records(restored_child)))


class RealRolloutRoundTripTests(unittest.TestCase):
    """Anchor the projection on real September 2026 Codex sessions copied into tests/fixtures."""

    FIXTURE_SESSIONS = pathlib.Path(__file__).resolve().parent / "fixtures" / "codex" / "sessions"

    def test_every_fixture_session_round_trips(self) -> None:
        rollouts = {load_records(path)[0]["payload"]["id"]: path for path in self.FIXTURE_SESSIONS.glob("*.jsonl")}
        roots = [path for path in rollouts.values() if not codex_to_pi.is_subagent_source(load_records(path)[0]["payload"].get("source"))]
        self.assertGreaterEqual(len(roots), 2, f"Expected at least two root fixtures. Got: {roots!r}")
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = pathlib.Path(temporary_directory)
            for root in roots:
                codex_to_pi.main(root, temporary / "pi", root.stem)
            pi_sessions = sorted((temporary / "pi").rglob("*.jsonl"))
            self.assertEqual(len(pi_sessions), len(rollouts), f"Every fixture rollout must become one Pi session. Got {len(pi_sessions)} for {len(rollouts)} rollouts")
            for pi_session in pi_sessions:
                codex_id = load_records(pi_session)[0]["codex"]["id"]
                with self.subTest(codex_session=codex_id):
                    restored = pi_to_codex.main(pi_session, temporary / "restored")
                    original = model_facing(load_records(rollouts[codex_id]))
                    self.assertGreater(len(original), 10, f"A real fixture must carry a meaningful number of model facts. Got {len(original)}")
                    RoundTripTests.assert_same_model_facts(self, original, model_facing(load_records(restored)))


if __name__ == "__main__":
    unittest.main()
