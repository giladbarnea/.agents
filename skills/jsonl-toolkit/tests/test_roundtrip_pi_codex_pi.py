#!/usr/bin/env -S uv run
# /// script
# requires-python = "==3.12.*"
# dependencies = []
# ///
"""Pi-origin conversions preserve the actual provider-visible conversation and child histories."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import codex_to_pi
import pi_to_codex

MODEL = "gpt-6-luna"
TIMESTAMP = "2026-10-01T06:00:00.000Z"


def write_session(path: Path, identifier: str, entries: list[dict[str, object]], **header: object) -> Path:
    records = [{"type": "session", "version": 3, "id": identifier, "cwd": str(path.parent),
                "timestamp": TIMESTAMP, **header}]
    for index, entry in enumerate(entries):
        records.append({"id": f"entry{index}", "parentId": f"entry{index - 1}" if index else None,
                        "timestamp": TIMESTAMP, **entry})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(record) + "\n" for record in records))
    return path


def conversation(text: str) -> list[dict[str, object]]:
    return [{"type": "model_change", "provider": "openai-codex", "modelId": MODEL},
            {"type": "message", "message": {"role": "user", "content": text, "timestamp": 0}}]


def replay(path: Path) -> list[dict[str, object]]:
    result = subprocess.run(["node", str(ROOT / "tests" / "pi-replay.mjs"), str(path)],
                            text=True, capture_output=True, check=True)
    return json.loads(result.stdout)["items"]


class PiOriginRoundTripTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.agent = self.directory / "agent"
        self.codex = self.directory / "codex"
        self.codex.mkdir()
        (self.codex / "models_cache.json").write_text(json.dumps({"models": [{"slug": MODEL}]}))
        environment = patch.dict(os.environ, {"CODEX_HOME": str(self.codex), "PI_CODING_AGENT_DIR": str(self.agent)})
        environment.start()
        self.addCleanup(environment.stop)

    def test_core_tools_and_reasoning_reach_pi_unchanged_after_the_round_trip(self) -> None:
        entries = conversation("Keep the exact operations, including failures.")
        operations = [
            ("read", {"path": "/tmp/שלום file.txt", "offset": 5, "limit": 8}, "Output:\n{\"output\":\"This is literal file content\"}"),
            ("write", {"path": "/tmp/new file.txt", "content": "gAAAAA-literal-file-content\none\n'quoted'\n"}, "Successfully wrote the file"),
            ("edit", {"path": "/tmp/new file.txt", "oldText": "one", "newText": "two"}, "No unique match. File unchanged."),
            ("bash", {"command": "printf '%s\\n' 'a && b'; exit 7", "timeout": 30}, "a && b\n\nCommand exited with code 7"),
        ]
        reasoning = {"type": "reasoning", "id": "rs_preserved", "summary": [], "encrypted_content": "sealed-state"}
        for index, (name, arguments, output) in enumerate(operations):
            entries.extend([
                {"type": "message", "message": {
                    "role": "assistant", "provider": "openai-codex", "api": "openai-codex-responses", "model": MODEL,
                    "stopReason": "toolUse", "timestamp": 0, "usage": codex_to_pi.ZERO_USAGE,
                    "content": ([{"type": "thinking", "thinking": "", "thinkingSignature": json.dumps(reasoning)}] if index == 0 else [])
                               + [{"type": "toolCall", "id": f"call_{index}|fc_{index}", "namespace": "functions",
                                   "name": name, "arguments": arguments}],
                }},
                {"type": "message", "message": {"role": "toolResult", "toolCallId": f"call_{index}|fc_{index}",
                    "toolName": name, "content": [{"type": "text", "text": output}], "isError": index >= 2, "timestamp": 0}},
            ])
        source = write_session(self.agent / "sessions" / "project" / "main.jsonl", "pi-main", entries)
        original_bytes = source.read_bytes()
        expected = replay(source)
        rollout = pi_to_codex.main(source, self.codex / "sessions")
        identifier = json.loads(rollout.read_text().splitlines()[0])["payload"]["id"]
        returned = codex_to_pi.main(rollout, self.directory / "returned", "Round trip")[identifier]
        self.assertEqual(replay(returned), expected, "The destination request must retain exact core-tool names, namespaces, arguments, results and reasoning")
        self.assertEqual(source.read_bytes(), original_bytes, "Conversion must not change the source session")

    def test_recursive_user_agent_sessions_survive_without_delivering_private_results(self) -> None:
        directory = self.agent / "sessions" / "project"
        source = write_session(directory / "main.jsonl", "pi-main", conversation("Only this belongs in main."))
        dispatch = {"type": "custom", "customType": "pi-user-agents-dispatch", "data": {"task": "private task", "isolate": True, "forwardedArgs": []}}
        child = write_session(directory / "child.jsonl", "pi-child", [dispatch, *conversation("PRIVATE CHILD RESULT")], parentSession=str(source))
        grandchild = write_session(directory / "grandchild.jsonl", "pi-grandchild", [dispatch, *conversation("PRIVATE GRANDCHILD RESULT")], parentSession=str(child))
        write_session(directory / "ordinary-fork.jsonl", "ordinary-fork", conversation("Unrelated fork"), parentSession=str(source))
        rollout = pi_to_codex.main(source, self.codex / "sessions")
        rollouts = list((self.codex / "sessions").glob("*.jsonl"))
        self.assertEqual(len(rollouts), 3, "Convert each persisted subagent once, recursively, but not ordinary forks")
        for path in rollouts:
            metadata = json.loads(path.read_text().splitlines()[0])["payload"]
            if isinstance(metadata["source"], dict):
                self.assertRegex(metadata["source"]["subagent"]["thread_spawn"]["agent_path"], r"^/root(?:/[a-z0-9_]+)+$", "Codex rejects hyphens and other non-native path characters")
        returned = codex_to_pi.main(rollout, self.directory / "returned", "Recursive")
        self.assertEqual(len(returned), 3, "Native Codex child links must be usable by the reverse converter")
        root_identifier = json.loads(rollout.read_text().splitlines()[0])["payload"]["id"]
        self.assertEqual(replay(returned[root_identifier]), replay(source), "Undelivered child work must stay outside main's context")
        returned_contents = [replay(path) for identifier, path in returned.items() if identifier != root_identifier]
        self.assertCountEqual(returned_contents, [replay(child), replay(grandchild)], "Every child's own context must survive")

    def test_team_receipts_and_manifests_discover_fresh_children_once_and_keep_deliveries(self) -> None:
        directory = self.agent / "sessions" / "project"
        source = write_session(directory / "main.jsonl", "pi-main", conversation("Main question"))
        first = write_session(directory / "first.jsonl", "pi-first", conversation("PRIVATE FIRST CHILD"), parentSession=str(source))
        second = write_session(directory / "second.jsonl", "pi-second", [*conversation("PRIVATE SECOND CHILD"),
            {"type": "custom_message", "customType": "pi-simple-team", "display": True,
             "content": "A sibling delivered this exact message.",
             "details": {"team": "audit", "from": "first", "to": "second", "message": "A sibling delivered this exact message."}}])
        members = [{"name": "first", "teammateId": "pi-first", "sessionFile": str(first)},
                   {"name": "second", "teammateId": "pi-second", "sessionFile": str(second)},
                   {"name": "missing", "teammateId": "pi-missing", "sessionFile": str(directory / "missing.jsonl")}]
        manifest_directory = self.agent / "pi-simple-team" / "teams-v2"
        manifest_directory.mkdir(parents=True)
        (manifest_directory / "audit.json").write_text(json.dumps({"version": 2, "id": "audit", "originMainSessionId": "pi-main", "members": members[:1]}))
        write_session(source, "pi-main", [*conversation("Main question"),
            {"type": "message", "message": {"role": "assistant", "api": "openai-codex-responses", "provider": "openai-codex", "model": MODEL,
                "stopReason": "toolUse", "timestamp": 0, "usage": codex_to_pi.ZERO_USAGE,
                "content": [{"type": "toolCall", "id": "call_spawn|fc_spawn", "name": "team_spawn", "arguments": {"teamName": "audit"}}]}},
            {"type": "message", "message": {"role": "toolResult", "toolName": "team_spawn", "toolCallId": "call_spawn|fc_spawn",
                "content": [{"type": "text", "text": json.dumps({"teamId": "audit", "teammates": members})}], "timestamp": 0, "isError": False}}])
        rollout = pi_to_codex.main(source, self.codex / "sessions")
        returned = codex_to_pi.main(rollout, self.directory / "returned", "Team")
        self.assertEqual(len(returned), 3, "Deduplicate receipt/manifest links and skip members without a JSONL")
        root_identifier = json.loads(rollout.read_text().splitlines()[0])["payload"]["id"]
        self.assertNotIn("PRIVATE FIRST CHILD", json.dumps(replay(returned[root_identifier])))
        child_contexts = [json.dumps(replay(path)) for identifier, path in returned.items() if identifier != root_identifier]
        delivered = next(text for text in child_contexts if "A sibling delivered this exact message." in text)
        self.assertIn("from first to second", delivered, "The destination must retain the sender and recipient, not just the body")
        restored = pi_to_codex.convert_session_tree(returned[root_identifier], self.directory / "restored")
        self.assertEqual(len(restored), 3, "Restoration must follow converted children, not old source paths inside historical tool receipts")
        original_records = {path.name: path.read_text() for path in (self.codex / "sessions").glob("*.jsonl")}
        self.assertEqual({path.name: path.read_text() for path in restored.values()}, original_records, "Every original Codex record must return unchanged")

    def test_restoration_rejects_new_context_messages_instead_of_dropping_them(self) -> None:
        source = write_session(self.agent / "sessions" / "project" / "main.jsonl", "pi-main", conversation("Original"))
        rollout = pi_to_codex.main(source, self.codex / "sessions")
        root_identifier = json.loads(rollout.read_text().splitlines()[0])["payload"]["id"]
        converted = codex_to_pi.main(rollout, self.directory / "returned", "Imported")[root_identifier]
        records = [json.loads(line) for line in converted.read_text().splitlines()]
        with converted.open("a") as output:
            output.write(json.dumps({"type": "custom_message", "id": "new-delivery", "parentId": records[-1]["id"],
                "timestamp": TIMESTAMP, "customType": "pi-simple-team", "content": "A new delivered result", "display": True}) + "\n")
        with self.assertRaisesRegex(ValueError, "added after the conversion"):
            pi_to_codex.main(converted, self.directory / "must-not-write")
        self.assertFalse((self.directory / "must-not-write").exists(), "Rejected restoration must not create a misleading rollout")

    def test_readable_agent_deliveries_keep_sender_recipient_and_exact_body(self) -> None:
        from test_codex_to_pi import ROOT_ID, record, session_meta, write_rollout
        body = "Use a < b, not a & b.\nThe task is still pending."
        records = [session_meta(ROOT_ID, 0), record(1, "turn_context", {"model": MODEL, "effort": "high"}),
                   record(2, "response_item", {"type": "agent_message", "author": "/root/reader", "recipient": "/root/writer",
                       "content": [{"type": "input_text", "text": body}]})]
        rollout = write_rollout(self.codex / "sessions", ROOT_ID, records)
        converted = codex_to_pi.main(rollout, self.directory / "returned", "Messages")[ROOT_ID]
        text = "\n".join(block.get("text", "") for item in replay(converted) for block in item.get("content", []))
        self.assertIn("from /root/reader to /root/writer", text, "A sibling delivery must not become an unattributed user instruction")
        self.assertIn(body, text, "Readable message text must not be altered by display escaping")

    def test_codex_exec_and_wait_keep_the_complete_operation_and_result(self) -> None:
        from test_codex_to_pi import ROOT_ID, record, session_meta, write_rollout
        script = 'const result = await tools.exec_command({cmd:"printf hello",workdir:"/tmp/a b",yield_time_ms:1000}); text(result);'
        output = 'Script completed\nOutput:\n{"output":"hello","session_id":42,"exit_code":0}'
        arguments = {"cell_id": "12", "yield_time_ms": 5000, "max_tokens": 1000}
        records = [session_meta(ROOT_ID, 0), record(1, "turn_context", {"model": MODEL, "effort": "high"}),
                   record(2, "response_item", {"type": "custom_tool_call", "id": "ctc_exec", "call_id": "call_exec", "name": "exec", "input": script}),
                   record(3, "response_item", {"type": "custom_tool_call_output", "call_id": "call_exec", "output": output}),
                   record(4, "response_item", {"type": "function_call", "id": "fc_wait", "call_id": "call_wait", "name": "wait", "arguments": json.dumps(arguments)}),
                   record(5, "response_item", {"type": "function_call_output", "call_id": "call_wait", "output": "Still running"})]
        rollout = write_rollout(self.codex / "sessions", ROOT_ID, records)
        converted = codex_to_pi.main(rollout, self.directory / "returned", "Core operations")[ROOT_ID]
        items = replay(converted)
        calls = [item for item in items if item.get("type") == "function_call"]
        self.assertEqual([(item["name"], json.loads(item["arguments"])) for item in calls],
                         [("exec", {"input": script}), ("wait", arguments)], "Historical operations must not become incomplete or fictitious bash commands")
        outputs = [item["output"] for item in items if item.get("type") == "function_call_output"]
        self.assertEqual(outputs, [output, "Still running"], "Unwrapping must not discard exit/status/session information or change literal output")
        self.assertEqual(pi_to_codex.restore_session(converted), records, "Original records must still restore exactly")


if __name__ == "__main__":
    unittest.main()
