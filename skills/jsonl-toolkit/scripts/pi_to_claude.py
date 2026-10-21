#!/usr/bin/env -S uv run
# /// script
# requires-python = "==3.12.*"
# dependencies = []
# ///
"""Convert a native Pi session into a native Claude Code session.

Pi's own reader builds the model context along the active path, so compaction summaries, branch
summaries and custom messages arrive the way Pi sends them. Each content block becomes one Claude
entry, which is how Claude Code itself stores assistant turns.

Anthropic thinking keeps its Pi signature byte for byte, and the entry keeps the Pi model id,
so Claude Code sends the block and the API decides whether the model reads it. Thinking from
another vendor becomes visible assistant text, the way codex_to_claude.py shows Codex summaries.
A text-less signed block from another vendor stays a thinking block under its own model id,
which makes Claude Code drop it before each API call.

Pi's replay rules for Anthropic carry over: errored and aborted turns are skipped, a tool call
without a result gets an error result, and tool call ids are normalized to what Anthropic accepts.
"""

import json
import re
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from codex_to_claude import CLAUDE_VERSION, claude_project_directory
from codex_to_pi import dumps
from pi_session import JsonObject, load_entries, resolve_session

ANTHROPIC_API = "anthropic-messages"
MISSING_RESULT = "No result provided"
STOP_REASONS = {"stop": "end_turn", "toolUse": "tool_use", "length": "max_tokens"}


def normalized_tool_call_id(identifier: str) -> str:
    """Make a tool call id valid for Anthropic, the way Pi's Anthropic provider does.

    >>> normalized_tool_call_id("call_abc|fc_123")
    'call_abc_fc_123'
    """
    return re.sub(r"[^a-zA-Z0-9_-]", "_", identifier)[:64]


def iso_timestamp(milliseconds: int) -> str:
    """
    >>> iso_timestamp(0)
    '1970-01-01T00:00:00.000Z'
    """
    return datetime.fromtimestamp(milliseconds / 1000, timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def claude_content(blocks: str | list[JsonObject]) -> list[JsonObject]:
    """Render Pi text and image blocks as Claude content blocks, without blank text.

    >>> claude_content([{"type": "text", "text": " "}, {"type": "image", "data": "iVBO", "mimeType": "image/png"}])
    [{'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/png', 'data': 'iVBO'}}]
    """
    if isinstance(blocks, str):
        blocks = [{"type": "text", "text": blocks}]
    rendered = [
        {"type": "text", "text": block["text"]} if block["type"] == "text" else {"type": "image", "source": {"type": "base64", "media_type": block["mimeType"], "data": block["data"]}}
        for block in blocks
    ]
    return [block for block in rendered if block["type"] != "text" or block["text"].strip()]


def assistant_blocks(message: JsonObject) -> list[JsonObject]:
    """Render one Pi assistant message as Claude content blocks."""
    is_anthropic = message["api"] == ANTHROPIC_API
    blocks: list[JsonObject] = []
    for block in message["content"]:
        if block["type"] == "text" and block["text"].strip():
            blocks.append({"type": "text", "text": block["text"]})
        elif block["type"] == "toolCall":
            blocks.append({"type": "tool_use", "id": normalized_tool_call_id(block["id"]), "name": block["name"], "input": block.get("arguments") or {}})
        elif block["type"] == "thinking" and block.get("redacted"):
            blocks.append({"type": "redacted_thinking", "data": block["thinkingSignature"]})
        elif block["type"] == "thinking" and block.get("thinkingSignature") and (is_anthropic or not block["thinking"].strip()):
            blocks.append({"type": "thinking", "thinking": block["thinking"], "signature": block["thinkingSignature"]})
        elif block["type"] == "thinking" and block["thinking"].strip():
            blocks.append({"type": "text", "text": block["thinking"]})
    return blocks


def with_missing_results(messages: list[JsonObject]) -> list[JsonObject]:
    """Drop errored and aborted turns, and answer each tool call left without a result, as Pi does before an Anthropic request."""
    result: list[JsonObject] = []
    pending: list[JsonObject] = []

    def answer_pending(timestamp: int) -> None:
        answered = {item["toolCallId"] for item in result if item["role"] == "toolResult"}
        result.extend({"role": "toolResult", "toolCallId": call["id"], "content": [{"type": "text", "text": MISSING_RESULT}], "isError": True, "timestamp": timestamp}
                      for call in pending if call["id"] not in answered)
        pending.clear()

    for message in messages:
        if message["role"] in ("assistant", "user"):
            answer_pending(message["timestamp"])
        if message["role"] == "assistant" and message["stopReason"] in ("error", "aborted"):
            continue
        if message["role"] == "assistant":
            pending.extend(block for block in message["content"] if block["type"] == "toolCall")
        result.append(message)
    answer_pending(result[-1]["timestamp"] if result else 0)
    return result


def convert_session(messages: list[JsonObject], session_id: str, cwd: str) -> list[JsonObject]:
    """Turn Pi's model context into Claude Code entries, one content block per entry."""
    lines: list[JsonObject] = []
    state: dict[str, str | None] = {"parent": None, "assistant": None}

    def entry(kind: str, timestamp: int, body: JsonObject) -> None:
        entry_uuid = str(uuid.uuid4())
        lines.append({"parentUuid": state["parent"], "isSidechain": False, "type": kind, **body, "uuid": entry_uuid, "timestamp": iso_timestamp(timestamp),
                      "userType": "external", "entrypoint": "cli", "cwd": cwd, "sessionId": session_id, "version": CLAUDE_VERSION, "gitBranch": "HEAD"})
        state["parent"] = entry_uuid

    for message in with_missing_results(messages):
        if message["role"] == "user" and (content := claude_content(message["content"])):
            entry("user", message["timestamp"], {"message": {"role": "user", "content": content}})
        elif message["role"] == "toolResult":
            if message["isError"] and any(block["type"] == "image" for block in message["content"]):
                raise ValueError(f"Tool call {message['toolCallId']} failed with an image, which Anthropic rejects in an error result")
            result = {"type": "tool_result", "tool_use_id": normalized_tool_call_id(message["toolCallId"]), "content": claude_content(message["content"]) or "", "is_error": message["isError"]}
            entry("user", message["timestamp"], {"message": {"role": "user", "content": [result]}, "sourceToolAssistantUUID": state["assistant"]})
        elif message["role"] == "assistant" and (blocks := assistant_blocks(message)):
            message_id = message.get("responseId") or f"msg_pi_{uuid.uuid4().hex[:20]}"
            stop_reason = message.get("rawStopReason") or STOP_REASONS[message["stopReason"]]
            for index, block in enumerate(blocks):
                body = {"model": message["model"], "id": message_id, "type": "message", "role": "assistant", "content": [block],
                        "stop_reason": stop_reason if index == len(blocks) - 1 else None, "stop_sequence": None, "usage": {"input_tokens": 0, "output_tokens": 0}}
                entry("assistant", message["timestamp"], {"message": body})
            state["assistant"] = state["parent"]
    return lines


def pi_context(entries: list[JsonObject]) -> list[JsonObject]:
    """Ask the installed Pi for the messages it would send to a model."""
    result = subprocess.run(["node", str(Path(__file__).with_name("pi-to-claude-context.mjs"))], input=json.dumps(entries), text=True, stdout=subprocess.PIPE, check=True)
    return json.loads(result.stdout)


def main(source: str | Path, projects_root: Path) -> Path:
    """Write the Claude Code session for one Pi session and print its resume command."""
    entries = load_entries(resolve_session(str(source)))
    cwd = str(entries[0]["cwd"])
    session_id = str(uuid.uuid4())
    lines = convert_session(pi_context(entries), session_id, cwd)
    name = next((entry["name"] for entry in reversed(entries) if entry["type"] == "session_info"), f"Pi session {entries[0]['id']}")
    target = claude_project_directory(projects_root, cwd) / f"{session_id}.jsonl"
    target.parent.mkdir(parents=True, exist_ok=True)
    title_line = {"type": "custom-title", "customTitle": f"{name} (from Pi)", "sessionId": session_id}
    target.write_text("".join(dumps(line) + "\n" for line in [*lines, title_line]), encoding="utf-8")
    print(f"wrote {target}\n  resume with: cd {cwd} && claude --resume {session_id}", file=sys.stderr)
    return target


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        sys.exit("usage: pi_to_claude.py <pi-session-id-or-path.jsonl> [claude-projects-root]")
    main(sys.argv[1], Path(sys.argv[2]) if len(sys.argv) == 3 else Path.home() / ".claude" / "projects")
