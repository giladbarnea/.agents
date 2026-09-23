#!/usr/bin/env -S uv run
# /// script
# requires-python = "==3.12.*"
# dependencies = []
# ///
"""Convert one Codex session into a native Claude Code session that restores to the same rollout.

Every rollout record rides verbatim on exactly one Claude line, under a top-level `codex` key.
Records the model reads or writes become Claude message entries, one content block per entry,
which is how Claude Code itself stores assistant turns. Tool calls keep their Codex name and
input, with ciphertext strings shown as a placeholder. Every other record becomes an inert
`codex-record` line that Claude Code ignores. `restore` is therefore a plain unfold.

Claude cannot read Codex reasoning or any other OpenAI ciphertext. The assistant entries carry the
Codex model id, so Claude Code drops the reasoning before each API call instead of failing on it.

Fork children and sessions that span several rollout files are refused. Shapes that stopped
before July 2026, such as `web_search_call` and `image_generation_call`, are not handled.
"""

import json
import re
import sys
import uuid
from pathlib import Path

from codex_to_pi import ENCRYPTED_PLACEHOLDER, INJECTED_USER_PREFIXES, CodexSessionGraph, compaction_summary, hide_ciphertext, resolve_codex_input, text_of

CLAUDE_VERSION = "2.1.280"
INERT_TYPE = "codex-record"
OUTPUT_ITEMS = {"custom_tool_call_output", "function_call_output", "tool_search_output"}

Record = dict[str, object]


def claude_blocks(content: str | list[Record]) -> list[Record]:
    """Render Codex content as Claude content blocks.

    >>> claude_blocks([{"type": "input_text", "text": "hi"}, {"type": "encrypted_content", "encrypted_content": "gA=="}])
    [{'type': 'text', 'text': 'hi'}, {'type': 'text', 'text': '[Codex ciphertext: only OpenAI can read this part]'}]
    """
    if isinstance(content, str):
        content = [{"type": "input_text", "text": content}]
    blocks: list[Record] = []
    for block in content:
        if block["type"] in ("input_text", "output_text"):
            blocks.append({"type": "text", "text": block["text"]})
        elif block["type"] == "input_image":
            header, _, data = str(block["image_url"]).partition(",")
            media_type = header.removeprefix("data:").removesuffix(";base64")
            blocks.append({"type": "image", "source": {"type": "base64", "media_type": media_type, "data": data}})
        elif block["type"] == "encrypted_content":
            blocks.append({"type": "text", "text": ENCRYPTED_PLACEHOLDER})
        else:
            raise ValueError(f"Cannot render Codex content block {block['type']!r}")
    return [block for block in blocks if block["type"] != "text" or block["text"]]


def is_model_facing(payload: Record) -> bool:
    """Whether Claude should see this item. Codex harness injections stay inert, because Claude Code injects its own."""
    if payload["type"] == "message" and payload["role"] == "developer":
        return False
    if payload["type"] == "message" and payload["role"] == "user":
        return not text_of(payload["content"]).startswith(INJECTED_USER_PREFIXES)
    return True


def claude_project_directory(projects_root: Path, cwd: str) -> Path:
    """Name the directory where Claude Code looks for sessions of a working directory.

    >>> claude_project_directory(Path("/p"), "/Users/me/.agents/my_repo")
    PosixPath('/p/-Users-me--agents-my-repo')
    """
    return projects_root / re.sub(r"[^A-Za-z0-9]", "-", cwd)


def convert(rollout: Path) -> list[Record]:
    """Turn every record of one rollout into exactly one Claude line, plus a summary line per compaction."""
    records = [json.loads(line) for line in rollout.read_text().split("\n") if line]
    cwd = records[0]["payload"]["cwd"]
    session_id = str(uuid.uuid4())
    lines: list[Record] = []
    state = {"parent": None, "model": "gpt-codex", "message_id": None}

    def entry(kind: str, record: Record, body: Record, stash: bool = True) -> None:
        entry_uuid = str(uuid.uuid4())
        lines.append({"parentUuid": state["parent"], "isSidechain": False, "type": kind, **body, "uuid": entry_uuid, "timestamp": record["timestamp"],
                      "userType": "external", "entrypoint": "cli", "cwd": cwd, "sessionId": session_id, "version": CLAUDE_VERSION, "gitBranch": "HEAD",
                      **({"codex": record} if stash else {})})
        state["parent"] = entry_uuid

    def assistant(record: Record, block: Record, stop_reason: str | None) -> None:
        state["message_id"] = state["message_id"] or f"msg_codex_{uuid.uuid4().hex[:20]}"
        message = {"model": state["model"], "id": state["message_id"], "type": "message", "role": "assistant", "content": [block],
                   "stop_reason": stop_reason, "stop_sequence": None, "usage": {"input_tokens": 0, "output_tokens": 0}}
        entry("assistant", record, {"message": message})

    def user(record: Record, content: str | list[Record], stash: bool = True, **extra: object) -> None:
        state["message_id"] = None
        entry("user", record, {"message": {"role": "user", "content": content}, **extra}, stash)

    for record in records:
        payload = record["payload"]
        if record["type"] == "turn_context":
            state["model"] = payload["model"]
        if record["type"] == "compacted":
            logical_parent = state["parent"]
            state["parent"] = None
            entry("system", record, {"subtype": "compact_boundary", "content": "Conversation compacted", "logicalParentUuid": logical_parent, "level": "info", "isMeta": False,
                                     "compactMetadata": {"trigger": "auto", "preTokens": (payload.get("latest_token_usage_record") or {"usage": {"total_tokens": 0}})["usage"]["total_tokens"]}})
            user(record, compaction_summary(payload["replacement_history"]), stash=False, isCompactSummary=True, isVisibleInTranscriptOnly=True)
            continue
        if record["type"] != "response_item" or not is_model_facing(payload):
            lines.append({"type": INERT_TYPE, "sessionId": session_id, "codex": record})
            continue

        item_type = payload["type"]
        if item_type == "reasoning":
            summary = "\n\n".join(str(part["text"]) for part in payload.get("summary") or [])
            assistant(record, {"type": "thinking", "thinking": summary, "signature": payload["encrypted_content"]}, None)
        elif item_type == "message" and payload["role"] == "assistant":
            assistant(record, {"type": "text", "text": text_of(payload["content"])}, "end_turn")
        elif item_type == "custom_tool_call":
            assistant(record, {"type": "tool_use", "id": payload["call_id"], "name": payload["name"], "input": {"input": payload["input"]}}, "tool_use")
        elif item_type == "function_call":
            name = "__".join(part for part in (payload.get("namespace"), payload["name"]) if part)
            assistant(record, {"type": "tool_use", "id": payload["call_id"], "name": name, "input": hide_ciphertext(json.loads(payload["arguments"]))}, "tool_use")
        elif item_type == "tool_search_call":
            assistant(record, {"type": "tool_use", "id": payload["call_id"], "name": "tool_search", "input": payload["arguments"]}, "tool_use")
        elif item_type in OUTPUT_ITEMS:
            output = json.dumps(payload["tools"]) if item_type == "tool_search_output" else payload["output"]
            user(record, [{"type": "tool_result", "tool_use_id": payload["call_id"], "content": claude_blocks(output) or ""}], sourceToolAssistantUUID=state["parent"])
        elif item_type == "message" and payload["role"] == "user":
            user(record, claude_blocks(payload["content"]))
        elif item_type == "agent_message":
            header = f"[Codex sub-agent message from {payload['author']} to {payload['recipient']}]"
            user(record, [{"type": "text", "text": header}, *claude_blocks(payload["content"])])
        else:
            raise ValueError(f"Unhandled response item {item_type!r} at {record['timestamp']}")
    return lines


def restore(claude_lines: list[Record]) -> list[Record]:
    """Unfold the stash: every line that carries a Codex record gives it back, in file order."""
    return [line["codex"] for line in claude_lines if "codex" in line]


def main(source: str | Path, projects_root: Path) -> Path:
    """Write the Claude session for one Codex session. Raises NotImplementedError for forks and multi-file sessions."""
    session_id, sessions_root = resolve_codex_input(source)
    graph = CodexSessionGraph.load(sessions_root)
    node = graph.nodes[session_id]
    if node.fork_parent_id or len(node.segments) > 1:
        raise NotImplementedError(f"Codex session {session_id} is a fork child or spans {len(node.segments)} rollout files. Only single-file sessions are supported.")
    lines = convert(node.rollout)
    claude_session_id = str(lines[0]["sessionId"])
    if session_id in graph.names:
        lines.append({"type": "custom-title", "customTitle": f"{graph.names[session_id]} (from Codex)", "sessionId": claude_session_id})
    cwd = str(lines[0]["codex"]["payload"]["cwd"])
    target = claude_project_directory(projects_root, cwd) / f"{claude_session_id}.jsonl"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("".join(json.dumps(line, ensure_ascii=False, separators=(",", ":")) + "\n" for line in lines))
    print(f"wrote {target}", file=sys.stderr)
    print(f"resume with: cd {cwd} && claude --resume {claude_session_id}", file=sys.stderr)
    return target


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        sys.exit("usage: codex_to_claude.py <codex-session-id-or-rollout.jsonl> [claude-projects-root]")
    main(sys.argv[1], Path(sys.argv[2]) if len(sys.argv) == 3 else Path.home() / ".claude" / "projects")
