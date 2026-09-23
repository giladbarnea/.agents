#!/usr/bin/env -S uv run
# /// script
# requires-python = "==3.12.*"
# dependencies = []
# ///
"""Convert the Codex fork tree that holds one session into native Claude Code sessions that restore to the same records.

Every Codex record rides verbatim on exactly one Claude line, under a top-level `codex` key.
Records the model reads or writes become Claude message entries, one content block per entry,
which is how Claude Code itself stores assistant turns. Tool calls keep their Codex name and
input, with ciphertext strings shown as a placeholder. Every other record becomes an inert
`codex-record` line that Claude Code ignores. `claude_to_codex.py` unfolds the lines again.

A fork child copies its parent's lines before the fork point, the way `claude --fork-session`
copies a session. Sub-agents, at any depth, become sessions of their own, titled after their parent.

Claude cannot read Codex reasoning ciphertext. A reasoning summary becomes visible assistant text,
the way Pi shows another vendor's thinking. A reasoning item without a summary stays a thinking
block, and the Codex model id on the entry makes Claude Code drop it before each API call.
"""

import json
import re
import sys
import uuid
from collections.abc import Sequence
from pathlib import Path

from codex_to_pi import (
    ENCRYPTED_PLACEHOLDER,
    INJECTED_USER_PREFIXES,
    CodexSessionGraph,
    Item,
    Subagent,
    compaction_summary,
    dumps,
    find_subagents,
    fork_cutoff,
    hide_ciphertext,
    load_items,
    load_node_items,
    resolve_codex_input,
    text_of,
    tool_name,
)

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


def inherited_lines(parent_lines: Sequence[Record], cutoff: int) -> list[Record]:
    """Return the parent's lines before a fork point, without the parent's own session_meta line."""
    inherited: list[Record] = []
    for line in parent_lines[1:]:
        ordinal = line.get("codex", {}).get("ordinal")
        if ordinal is not None and ordinal >= cutoff:
            break
        inherited.append(line)
    return inherited


def convert_session(items: Sequence[Item], session_id: str, prefix: Sequence[Record]) -> list[Record]:
    """Turn every Codex record into exactly one Claude line, after the session_meta line and any inherited parent lines."""
    cwd = str(items[0].payload["cwd"])
    lines: list[Record] = [{"type": INERT_TYPE, "sessionId": session_id, "codex": items[0].record}, *({**line, "sessionId": session_id} for line in prefix)]
    inherited_models = [line["codex"]["payload"]["model"] for line in prefix if line.get("codex", {}).get("type") == "turn_context"]
    state = {"parent": next((line["uuid"] for line in reversed(prefix) if "uuid" in line), None), "model": (inherited_models or ["gpt-codex"])[-1], "message_id": None}

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

    for item in items[1:]:
        record, payload = item.record, item.payload
        if item.kind == "turn_context":
            state["model"] = payload["model"]
        if item.kind == "compacted":
            logical_parent = state["parent"]
            state["parent"] = None
            entry("system", record, {"subtype": "compact_boundary", "content": "Conversation compacted", "logicalParentUuid": logical_parent, "level": "info", "isMeta": False,
                                     "compactMetadata": {"trigger": "auto", "preTokens": (payload.get("latest_token_usage_record") or {"usage": {"total_tokens": 0}})["usage"]["total_tokens"]}})
            user(record, compaction_summary(payload["replacement_history"]), stash=False, isCompactSummary=True, isVisibleInTranscriptOnly=True)
            continue
        if item.kind != "response_item" or not is_model_facing(payload):
            lines.append({"type": INERT_TYPE, "sessionId": session_id, "codex": record})
            continue

        item_type = payload["type"]
        if item_type == "reasoning":
            summary = "\n\n".join(str(part["text"]) for part in payload.get("summary") or [])
            block = {"type": "text", "text": summary} if summary.strip() else {"type": "thinking", "thinking": "", "signature": payload["encrypted_content"]}
            assistant(record, block, None)
        elif item_type == "message" and payload["role"] == "assistant":
            assistant(record, {"type": "text", "text": text_of(payload["content"])}, "end_turn")
        elif item_type == "custom_tool_call":
            assistant(record, {"type": "tool_use", "id": payload["call_id"], "name": payload["name"], "input": {"input": payload["input"]}}, "tool_use")
        elif item_type == "function_call":
            assistant(record, {"type": "tool_use", "id": payload["call_id"], "name": tool_name(payload), "input": hide_ciphertext(json.loads(payload["arguments"]))}, "tool_use")
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


def main(source: str | Path, projects_root: Path) -> dict[str, Path]:
    """Write a Claude Code session for every session in the selected Codex session's fork tree, and for every sub-agent."""
    selected_session_id, codex_sessions_root = resolve_codex_input(source)
    graph = CodexSessionGraph.load(codex_sessions_root)
    converted: dict[str, list[Record]] = {}
    paths: dict[str, Path] = {}

    def write(codex_session_id: str, lines: list[Record], title: str) -> None:
        claude_session_id = str(lines[0]["sessionId"])
        cwd = str(lines[0]["codex"]["payload"]["cwd"])
        target = claude_project_directory(projects_root, cwd) / f"{claude_session_id}.jsonl"
        target.parent.mkdir(parents=True, exist_ok=True)
        title_line = {"type": "custom-title", "customTitle": f"{title} (from Codex)", "sessionId": claude_session_id}
        target.write_text("".join(dumps(line) + "\n" for line in [*lines, title_line]))
        paths[codex_session_id] = target
        print(f"wrote {target}\n  resume with: cd {cwd} && claude --resume {claude_session_id}", file=sys.stderr)

    def convert_subagents(subagents: dict[str, Subagent], parent_title: str) -> None:
        for subagent in subagents.values():
            items = load_items(subagent.rollout)
            title = f"{parent_title} — sub-agent {subagent.agent_path} ({subagent.nickname})"
            write(str(items[0].payload["id"]), convert_session(items, str(uuid.uuid4()), []), title)
            convert_subagents(find_subagents(items, codex_sessions_root), title)

    def convert_node(session_id: str) -> None:
        node = graph.nodes[session_id]
        items = list(load_node_items(node))
        cutoff = fork_cutoff(node, graph.ancestors(session_id)) if node.fork_parent_id in converted else None
        prefix = inherited_lines(converted[node.fork_parent_id], cutoff) if cutoff is not None else []
        converted[session_id] = convert_session(items, str(uuid.uuid4()), prefix)
        title = graph.names.get(session_id, f"Codex session {session_id}")
        write(session_id, converted[session_id], title)
        convert_subagents(find_subagents(items, codex_sessions_root), title)
        for child_id in graph.fork_children[session_id]:
            convert_node(child_id)

    convert_node(graph.root_of(selected_session_id))
    return paths


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        sys.exit("usage: codex_to_claude.py <codex-session-id-or-rollout.jsonl> [claude-projects-root]")
    main(sys.argv[1], Path(sys.argv[2]) if len(sys.argv) == 3 else Path.home() / ".claude" / "projects")
