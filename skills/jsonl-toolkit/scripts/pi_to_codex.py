#!/usr/bin/env -S uv run
# /// script
# requires-python = "==3.12.*"
# dependencies = []
# ///
"""Convert a native Pi conversation to Codex, or restore its preserved Codex records.

Native imports use Pi's own active-context and OpenAI message conversion. Imported Codex
sessions still unfold their original records without translating later Pi turns.
"""

import json
import os
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from codex_to_pi import REASONING_FAMILY_PREFIXES, restored_rollout, write_restored_rollout
from pi_session import JsonObject, extract_active_path, load_entries, uuidv7
from pi_session_tree import discover_session_tree
from pi_runtime import capture_runtime


def restore_records(header: JsonObject, active: list[JsonObject]) -> list[JsonObject]:
    """Unfold the Codex records along the active path.

    Raises ValueError for a session an older converter wrote, and for a turn added in Pi after the conversion.
    """
    if "payload" not in header.get("codex", {}):
        raise ValueError("This Pi session was written by an older codex_to_pi.py. Convert the Codex session again.")
    records = [header["codex"]]
    for entry in active:
        if entry["type"] in ("message", "custom_message", "compaction", "branch_summary", "context_edit") and "codex" not in entry:
            raise ValueError(f"Pi entry {entry['id']} was added after the conversion, and Codex cannot express it yet.")
        records.extend(entry.get("codex", []))
    return records


def restore_session(session_path: Path) -> list[JsonObject]:
    header, active = extract_active_path(load_entries(Path(session_path)))
    return restored_rollout(restore_records(header, active))


def convert_session_tree(session_path: Path, output_directory: Path) -> dict[str, Path]:
    """Convert existing child JSONLs once, preserving their own context without delivering new messages."""
    nodes = discover_session_tree(session_path)
    imported = ["codex" in node.header for node in nodes.values()]
    if any(imported) and not all(imported):
        raise ValueError("Cannot restore a Codex tree containing a newly added Pi child session")
    if all(imported):
        records = {identifier: restored_rollout(restore_records(node.header, node.entries)) for identifier, node in nodes.items()}
        return {identifier: write_restored_rollout(items, output_directory) for identifier, items in records.items()}

    catalog_path = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "models_cache.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    version = subprocess.run(["codex", "--version"], text=True, stdout=subprocess.PIPE, check=True).stdout.strip().split()[-1]
    identifiers = {identifier: uuidv7() for identifier in nodes}
    agent_paths: dict[str, str] = {}
    for source_id, node in nodes.items():
        agent_paths[source_id] = f"{agent_paths[node.parent_id]}/agent_{identifiers[source_id].replace('-', '_')}" if node.parent_id else "/root"
    prepared: dict[str, list[JsonObject]] = {}
    for source_id, node in nodes.items():
        result = subprocess.run(
            ["node", str(Path(__file__).with_name("pi-to-codex-context.mjs"))],
            input=json.dumps({"entries": [node.header, *node.entries], "modelIds": [model["slug"] for model in catalog["models"]],
                              "reasoningFamilyPrefixes": REASONING_FAMILY_PREFIXES}),
            text=True, stdout=subprocess.PIPE, check=True,
        )
        context = json.loads(result.stdout)
        identifier = identifiers[source_id]
        timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        source = {"subagent": {"thread_spawn": {
            "parent_thread_id": identifiers[node.parent_id], "agent_path": agent_paths[source_id],
            "agent_nickname": node.name, "agent_role": "default", "depth": agent_paths[source_id].count("/") - 1,
        }}} if node.parent_id else "cli"
        payloads = [
            ("session_meta", {
                "id": identifier, "session_id": identifier, "timestamp": timestamp,
                "cwd": node.header["cwd"], "originator": "pi_to_codex", "cli_version": version,
                "source": source, "model_provider": "openai", "multi_agent_version": "v2",
                "piRuntime": capture_runtime(node),
            }),
            ("turn_context", {
                "cwd": node.header["cwd"], "model": context["model"], "effort": context["effort"],
                "summary": "auto", "approval_policy": "on-request", "sandbox_policy": {"type": "read-only"},
            }),
            *(("response_item", item) for item in context["items"]),
        ]
        children = [child for child in nodes.values() if child.parent_id == source_id]
        if children:
            routes = [{"name": child.name, "sourceSessionId": child.identifier, "canonicalPath": agent_paths[child.identifier],
                       "ownership": "user" if child.origin == "pi-user-agents" else "assistant"} for child in children]
            routing_note = ("Restored saved agents are dormant, not newly spawned. list_agents may omit dormant agents. "
                            "Use these canonical paths in tool targets AND in instructions sent to another agent; do not substitute relative names. "
                            "Contact user-owned children only when the user explicitly requests it. These records contain identity/routing metadata only.\n"
                            + json.dumps(routes, ensure_ascii=False))
            payloads.append(("response_item", {"type": "message", "role": "developer", "content": [{"type": "input_text", "text": routing_note}]}))
        for child in children:
            payloads.append(("event_msg", {"type": "sub_agent_activity", "event_id": uuidv7(),
                "agent_thread_id": identifiers[child.identifier], "agent_path": agent_paths[child.identifier], "kind": "started"}))
        prepared[source_id] = [{"timestamp": timestamp, "ordinal": ordinal, "type": kind, "payload": payload}
                               for ordinal, (kind, payload) in enumerate(payloads)]
    outputs = {identifier: write_restored_rollout(records, output_directory) for identifier, records in prepared.items()}
    for identifier, records in prepared.items():
        model = records[1]["payload"]["model"]
        print(f"resume with: codex resume {identifiers[identifier]} --model {shlex.quote(model)}", file=sys.stderr)
    return outputs


def main(session_path: Path, output_directory: Path) -> Path:
    """Convert the selected session tree and return its root rollout path."""
    return next(iter(convert_session_tree(session_path, output_directory).values()))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: pi_to_codex.py <pi-session.jsonl> <output-directory>")
    main(Path(sys.argv[1]), Path(sys.argv[2]))
