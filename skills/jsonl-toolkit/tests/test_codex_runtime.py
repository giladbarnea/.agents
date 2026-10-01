#!/usr/bin/env -S uv run
# /// script
# requires-python = "==3.12.*"
# dependencies = []
# ///
"""Imported runtime state must preserve opaque history without owning source sessions."""
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(Path(__file__).parent))
import codex_to_pi
import pi_to_codex
import pi_runtime
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
            self.assertEqual([tool["name"] for namespace in replay.get("tools", []) for tool in namespace.get("tools", [])], ["send_message"], "Encrypted arguments need their native schema, not unrelated historical tools")
            self.assertEqual(replay.get("tool_choice"), "none", "Replay declarations must not enable historical tool execution")

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

    def test_encrypted_checkpoint_reaches_its_summary_span_and_normal_replay_exactly_once(self) -> None:
        checkpoint = {"type": "compaction", "id": "cmp_saved", "encrypted_content": "sealed-checkpoint", "internal_chat_message_metadata_passthrough": {"turn_id": "checkpoint-turn"}}
        deliveries = [{"type": "agent_message", "id": identifier, "author": "/root", "recipient": "/root/worker", "content": [{"type": "encrypted_content", "encrypted_content": "sealed-" + identifier}]} for identifier in ("amsg_two", "amsg_future")]
        records = [session_meta(ROOT_ID, 0), record(1, "turn_context", {"model": "gpt-6-luna", "effort": "high"}), record(2, "compacted", {"replacement_history": [checkpoint]}), *[record(index + 3, "response_item", item) for index, item in enumerate(deliveries)]]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = codex_to_pi.main(write_rollout(root / "codex" / "sessions", ROOT_ID, records), root / "pi", "Checkpoint")[ROOT_ID]
            replay = json.loads(subprocess.run(["bun", str(ROOT / "tests" / "codex-runtime-replay.ts"), str(target)], capture_output=True, text=True, check=True).stdout)
            self.assertEqual([item for item in replay["input"] if item.get("type") == "compaction"], [checkpoint])
            summary = json.loads(subprocess.run(["bun", str(ROOT / "tests" / "codex-runtime-compaction.ts"), str(target)], capture_output=True, text=True, check=True).stdout)
            self.assertEqual([item for item in summary["captured"][0]["input"] if item.get("type") == "compaction"], [checkpoint])
            self.assertNotIn("sealed-checkpoint", json.dumps(summary["captured"][1]), "The checkpoint belongs only to the history summary, not the split prefix")
            incompatible = json.loads(subprocess.run(["bun", str(ROOT / "tests" / "codex-runtime-replay.ts"), str(target), "gpt-5.6-luna"], capture_output=True, text=True, check=True).stdout)
            self.assertTrue(incompatible["aborted"], incompatible)

    def test_real_pi_sends_no_request_when_an_opaque_rewrite_fails(self) -> None:
        requests: list[bytes] = []
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *arguments: object) -> None:
                pass
            def do_POST(self) -> None:
                requests.append(self.rfile.read(int(self.headers["content-length"])))
                self.send_response(500)
                self.end_headers()
                self.wfile.write(b'{"error":{"message":"Unexpected provider request"}}')
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        delivery = {"type": "agent_message", "id": "amsg_failure", "author": "/root", "recipient": "/root/worker", "content": [{"type": "encrypted_content", "encrypted_content": "sealed-private"}]}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            agent = root / "agent"
            agent.mkdir()
            (agent / "models.json").write_text(json.dumps({"providers": {"openai-codex": {"baseUrl": f"http://127.0.0.1:{server.server_port}/v1", "api": "openai-responses", "apiKey": "test-only", "models": [{"id": "gpt-6-luna", "name": "Probe", "reasoning": False, "input": ["text"], "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0}, "contextWindow": 32000, "maxTokens": 100}]}}}))
            (agent / "settings.json").write_text(json.dumps({"retry": {"enabled": False}, "compaction": {"enabled": False}}))
            records = [session_meta(ROOT_ID, 0), record(1, "turn_context", {"model": "gpt-6-luna", "effort": "low"}), record(2, "response_item", delivery)]
            records[0]["payload"]["cwd"] = str(root)
            target = codex_to_pi.main(write_rollout(root / "codex" / "sessions", ROOT_ID, records), agent / "sessions", "Abort")[ROOT_ID]
            sabotage = root / "remove-marker.ts"
            sabotage.write_text('export default function(pi) { pi.on("before_provider_request", event => ({...event.payload, input: []})); }\n')
            environment = {key: value for key, value in os.environ.items() if not key.startswith("PI_SIMPLE_TEAM_")}
            environment.update({"PI_CODING_AGENT_DIR": str(agent), "PI_OFFLINE": "1"})
            result = subprocess.run(["pi", "--mode", "json", "--session", str(target), "--no-extensions", "-e", str(sabotage), "-e", str(ROOT / "scripts" / "codex-replay.ts"), "--no-tools", "--no-skills", "--no-context-files", "--no-prompt-templates", "Continue"], cwd=root, env=environment, capture_output=True, text=True, timeout=30)
            self.assertIn("replay marker was removed", result.stderr, "The test must fail at the rewrite guard, not authentication or fixture loading")
            self.assertEqual(requests, [], "Pi catches extension errors, so the hook must abort before any network request")


class PlaintextCoordinationTests(unittest.TestCase):
    def test_explicit_empty_encryption_metadata_keeps_literal_ciphertext_looking_text(self) -> None:
        call = {"type": "function_call", "id": "fc_plain", "call_id": "call_plain", "namespace": "collaboration", "name": "send_message", "arguments": '{"target":"/root","message":"gAAAAA-is-literal-text"}', "encrypted_function_args": []}
        output = {"type": "function_call_output", "call_id": "call_plain", "output": ""}
        records = [session_meta(ROOT_ID, 0), record(1, "turn_context", {"model": "gpt-6-luna", "effort": "high"}), record(2, "response_item", call), record(3, "response_item", output)]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = codex_to_pi.main(write_rollout(root / "codex" / "sessions", ROOT_ID, records), root / "pi", "Plaintext")[ROOT_ID]
            entries = [json.loads(line) for line in target.read_text().splitlines()]
            arguments = next(block["arguments"] for entry in entries for block in entry.get("message", {}).get("content", []) if block.get("type") == "toolCall")
            self.assertEqual(arguments["message"], "gAAAAA-is-literal-text", "Codex's explicit [] means plaintext, regardless of its prefix")
            result = subprocess.run(["bun", str(ROOT / "tests" / "codex-runtime-replay.ts"), str(target)], capture_output=True, text=True, check=True)
            replay = json.loads(result.stdout)
            self.assertEqual(replay["input"][0], call, "The plaintext override must survive Pi's provider serializer")
            self.assertNotIn("tools", replay, "Plaintext-only coordination needs no encrypted schema declaration")


class CoordinationSchemaTests(unittest.TestCase):
    def test_only_active_imported_schemas_are_added_and_original_execution_intent_is_preserved(self) -> None:
        call = {"type": "function_call", "namespace": "collaboration", "name": "send_message", "call_id": "old", "arguments": '{"message":"gAAAAA-sealed","target":"/root"}'}
        current = {"type": "function", "name": "read", "parameters": {"type": "object"}}
        namespace = {"type": "namespace", "name": "probe", "tools": [{"type": "function", "name": "echo", "parameters": {"type": "object"}}]}
        cases = []
        choices = ["auto", "required", "none", {"type": "function", "name": "read"}, {"type": "allowed_tools", "mode": "auto", "tools": [{"type": "function", "name": "read"}]}]
        for choice in choices:
            cases.append({"payload": {"input": [call, {"type": "additional_tools", "tools": [namespace]}], "tools": [current], "tool_choice": choice}, "imported": [call]})
        cases.extend([
            {"payload": {"input": [call], "tool_choice": "auto"}, "imported": [call]},
            {"payload": {"input": [], "tools": [current], "tool_choice": "auto"}, "imported": [call]},
            {"payload": {"input": [call], "tool_choice": {"type": "function", "namespace": "collaboration", "name": "send_message"}}, "imported": [call]},
            {"payload": {"input": [call], "tool_choice": {"type": "function", "name": "send_message"}}, "imported": [call]},
            {"payload": {"input": [{**call, "name": "unsupported_coordination"}]}, "imported": [{**call, "name": "unsupported_coordination"}]},
        ])
        process = subprocess.run(["bun", str(ROOT / "tests" / "codex-runtime-tools.ts")], input=json.dumps(cases), capture_output=True, text=True, check=True)
        results = json.loads(process.stdout)
        allowed = [{"type": "function", "name": "read"}, {"type": "function", "name": "echo", "namespace": "probe"}]
        for index, original_choice in enumerate(choices):
            payload = results[index]["payload"]
            self.assertEqual(payload["input"], cases[index]["payload"]["input"], "Ciphertext, IDs and all history must remain unchanged")
            self.assertEqual(payload["tools"][:2], [current, namespace], "Existing top-level and anchored declarations must remain executable")
            historical = payload["tools"][2]
            self.assertEqual([tool["name"] for tool in historical["tools"]], ["send_message"], "Do not expose unrelated historical functions")
            self.assertTrue(historical["tools"][0]["parameters"]["properties"]["message"]["encrypted"])
            expected_choice = {"type": "allowed_tools", "mode": original_choice, "tools": allowed} if original_choice in ("auto", "required") else original_choice
            self.assertEqual(payload["tool_choice"], expected_choice)
        self.assertEqual(results[5]["payload"]["tool_choice"], "none", "An empty original tool set must remain non-executable")
        self.assertEqual(results[6]["payload"], cases[6]["payload"], "An omitted imported call must not add any schema")
        self.assertIn("cannot enable replay-only", results[7]["error"])
        self.assertIn("cannot enable replay-only", results[8]["error"])
        self.assertIn("Unsupported encrypted coordination schema", results[9]["error"])
        self.assertNotIn("payload", results[9], "Unsupported schema must not produce a plaintext fallback request")


class RuntimeRestorationTests(unittest.TestCase):
    def test_team_configuration_returns_with_fresh_ids_and_private_user_agents_stay_separate(self) -> None:
        from test_roundtrip_pi_codex_pi import conversation, write_session
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_agent = root / "source-agent"
            destination_agent = root / "destination-agent"
            codex = root / "codex"
            codex.mkdir()
            (codex / "models_cache.json").write_text(json.dumps({"models": [{"slug": "gpt-6-luna"}]}))
            sessions = source_agent / "sessions" / "project"
            parent = write_session(sessions / "parent.jsonl", "source-parent", conversation("Main work"))
            child = write_session(sessions / "child.jsonl", "source-child", conversation("Child work"), parentSession=str(parent))
            dispatch = {"task": "Private user task", "isolate": True, "forwardedArgs": ["--tools", "read"]}
            private = write_session(sessions / "private.jsonl", "source-private", [{"type": "custom", "customType": "pi-user-agents-dispatch", "data": dispatch}, *conversation("PRIVATE RESULT")], parentSession=str(parent))
            configuration = {"name": "reader", "systemPrompt": "Read only.", "model": "openai-codex/gpt-6-luna", "thinking": "high", "inheritMainContext": True, "canManageOwnTeams": False, "teammateId": "source-child", "sessionFile": str(child)}
            manifest = {"version": 2, "id": "source-parent-reader's-team", "name": "reader's-team", "originMainSessionId": "source-parent", "teamPrompt": "Preserve this exact team prompt.", "members": [configuration], "state": "active"}
            source_manifest = source_agent / "pi-simple-team" / "teams-v2" / "source.json"
            source_manifest.parent.mkdir(parents=True)
            source_manifest.write_text(json.dumps(manifest))
            original_manifest = source_manifest.read_bytes()
            original_child = child.read_bytes()
            with patch.dict(os.environ, {"CODEX_HOME": str(codex), "PI_CODING_AGENT_DIR": str(source_agent)}):
                forward = pi_to_codex.convert_session_tree(parent, codex / "sessions")
                forward_records = [json.loads(line) for line in forward["source-parent"].read_text().splitlines()]
                root_id = forward_records[0]["payload"]["id"]
                routing = next(item["payload"]["content"][0]["text"] for item in forward_records if item["type"] == "response_item" and item["payload"].get("role") == "developer")
                self.assertIn('"name": "reader"', routing)
                self.assertIn('"sourceSessionId": "source-child"', routing)
                self.assertIn('"ownership": "user"', routing)
                self.assertNotIn("PRIVATE RESULT", routing)
                self.assertNotIn(dispatch["task"], routing, "Routing metadata must not expose a user-owned task")
                returned = codex_to_pi.main(forward["source-parent"], destination_agent / "sessions", "Runtime")
                paths = pi_runtime.restore_runtime(returned[root_id], destination_agent)
                self.assertEqual(len(paths), 1, "Private user agents must not become automatically connected team members")
                restored = json.loads(paths[0].read_text())
                parent_header = json.loads(returned[root_id].read_text().split("\n", 1)[0])
                self.assertEqual(restored["originMainSessionId"], parent_header["id"])
                self.assertNotEqual(restored["originMainSessionId"], "source-parent")
                self.assertEqual(restored["state"], "dormant")
                self.assertEqual(restored["teamPrompt"], manifest["teamPrompt"])
                self.assertEqual(restored["projectDirectory"], str(sessions.resolve()))
                member = restored["members"][0]
                self.assertEqual(member["systemPrompt"], configuration["systemPrompt"])
                self.assertEqual(member["extensionPaths"], [str(pi_runtime.REPLAY_EXTENSION)])
                self.assertFalse(member["live"] or member["active"])
                self.assertNotEqual(member["teammateId"], "source-child")
                self.assertNotEqual(member["sessionFile"], str(child))
                self.assertIn("reader's-team", paths[0].name, "Filename encoding must match encodeURIComponent used by pi-simple-team")
                self.assertFalse(list(paths[0].parent.glob("*.lease")), "Registration must never claim or start a runtime")
                current = {**restored, "state": "active", "teamPrompt": "Updated after restoration"}
                paths[0].write_text(json.dumps(current))
                pi_runtime.restore_runtime(returned[root_id], destination_agent)
                self.assertEqual(json.loads(paths[0].read_text()), current, "Reopening a session must not overwrite an existing team's current state")
                added = write_session(destination_agent / "sessions" / "new-child.jsonl", "new-pi-child", conversation("Later Pi work"), parentSession=str(returned[root_id]))
                current["members"].append({**member, "name": "new", "teammateId": "new-pi-child", "sessionFile": str(added)})
                paths[0].write_text(json.dumps(current))
                with patch.dict(os.environ, {"PI_CODING_AGENT_DIR": str(destination_agent)}):
                    pi_runtime.restore_runtime(returned[root_id], destination_agent)
                self.assertEqual(json.loads(paths[0].read_text()), current, "Later native Pi members must not be dropped or mistaken for imported Codex sessions")
                returned_private = next(path for path in returned.values() if json.loads(path.read_text().split("\n", 1)[0])["codex"]["payload"].get("piRuntime", {}).get("sourceSessionId") == "source-private")
                entries = [json.loads(line) for line in returned_private.read_text().splitlines()]
                returned_dispatch = next(entry["data"] for entry in entries if entry.get("customType") == "pi-user-agents-dispatch")
                self.assertEqual(returned_dispatch["task"], dispatch["task"])
                self.assertEqual(returned_dispatch["forwardedArgs"], ["--tools", "read", "--extension", str(pi_runtime.REPLAY_EXTENSION)])
            self.assertEqual(source_manifest.read_bytes(), original_manifest)
            self.assertEqual(child.read_bytes(), original_child)


if __name__ == "__main__":
    unittest.main()
