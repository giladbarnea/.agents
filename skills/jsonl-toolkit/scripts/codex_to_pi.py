#!/usr/bin/env -S uv run
# /// script
# requires-python = "==3.12.*"
# dependencies = []
# ///
"""Synthesize a native Pi session tree from any persisted Codex session node.

The converter follows native fork ancestry in both directions, rebuilds paginated rollout
segments, copies each fork-point history into its Pi child, and sets `parentSession`.
It ports messages, reasoning, complete tool history, compaction, and persisted Codex sub-agents.

Every Codex record rides verbatim under a `codex` key, so `pi_to_codex.py` restores the same
records: the session_meta on the header, and every other record, in order, in the list of the
Pi entry written next. Records the model never reads, such as events and harness injections,
ride along the same way. Reasoning also stays in `thinkingSignature` and assistant ids in
`textSignature`, the slots Pi's own Codex provider reads back. Sub-agents, at any depth, become
attributed notifications plus separate Pi child sessions. Calls keep their original name,
namespace, arguments, and results, with only ciphertext coordination content masked. Codex side chats
remain absent because Codex writes no rollout for them.

Shapes that stopped before July 2026 are out of scope. The function-call form of exec,
`web_search_call`, and `multi_agent_v1` are not handled.
"""

import json
import os
import secrets
import shlex
import sys
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from pi_runtime import restored_dispatch

PROVIDER = "openai-codex"
API = "openai-codex-responses"
REASONING_FAMILY_PREFIXES = ("gpt-6-", "gpt-5.6-")
ZERO_USAGE = {
    "input": 0,
    "output": 0,
    "cacheRead": 0,
    "cacheWrite": 0,
    "totalTokens": 0,
    "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0, "total": 0},
}
INJECTED_USER_PREFIXES = ("<environment_context>", "# AGENTS.md instructions", "<recommended_plugins>")
SUBAGENT_NOTIFICATION_TYPE = "subagent-notification"
SUBAGENT_RECORD_TYPE = "subagents:record"
CODEX_RECORD_TYPE = "codex-record"
FORK_KEYS = ("forked_from_id", "forked_from_ordinal_exclusive", "history_base")
ENCRYPTED_PLACEHOLDER = "[Codex ciphertext: only OpenAI can read this part]"
CIPHERTEXT_PREFIX = "gAAAAA"
COMPACTION_PREFACE = "Codex compacted the context here. Its summary is encrypted and unreadable outside Codex. It replayed the following messages verbatim after the summary:\n\n"

def reasoning_family(model: str) -> str:
    """Group documented compatible GPT models; unknown models match only themselves.

    >>> reasoning_family("openai-codex/gpt-6-sol") == reasoning_family("gpt-6-luna")
    True
    >>> reasoning_family("gpt-5.6-sol") == reasoning_family("gpt-6-sol")
    False
    """
    identifier = model.removeprefix("openai-codex/")
    return next((prefix[:-1] for prefix in REASONING_FAMILY_PREFIXES if identifier.startswith(prefix)), identifier)


def uuidv7(at_ms: int) -> str:
    value = (at_ms << 80) | (0x7 << 76) | (secrets.randbits(12) << 64) | (0b10 << 62) | secrets.randbits(62)
    hex_value = f"{value:032x}"
    return f"{hex_value[:8]}-{hex_value[8:12]}-{hex_value[12:16]}-{hex_value[16:20]}-{hex_value[20:]}"


def epoch_ms(iso: str) -> int:
    return int(datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp() * 1000)


def dumps(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def text_of(content: str | list[dict[str, object]]) -> str:
    """Join the text of Codex content, with a placeholder where Codex stored ciphertext.

    >>> text_of([{"type": "input_text", "text": "Payload:\\n"}, {"type": "encrypted_content", "encrypted_content": "gAAAAABq"}])
    'Payload:\\n[Codex ciphertext: only OpenAI can read this part]'
    """
    if isinstance(content, str):
        return content
    return "".join(ENCRYPTED_PLACEHOLDER if block.get("type") == "encrypted_content" else str(block.get("text", "")) for block in content if block.get("type") in ("input_text", "output_text", "encrypted_content"))


def agent_message_text(payload: dict[str, object]) -> str:
    """Preserve message attribution without changing or XML-escaping its readable body.

    >>> agent_message_text({"author": "/root/a", "recipient": "/root", "content": "a < b"})
    '[Codex message from /root/a to /root]\\na < b'
    """
    return f"[Codex message from {payload['author']} to {payload['recipient']}]\n{text_of(payload['content'])}"


def replay_text(item: dict[str, object]) -> str | None:
    """Render one item that Codex replayed after a compaction, or None for the encrypted summary and harness injections.

    >>> replay_text({"type": "agent_message", "author": "/root/hud", "recipient": "/root", "content": [{"type": "input_text", "text": "done"}]})
    '[/root/hud to /root]\\ndone'
    >>> replay_text({"type": "message", "role": "developer", "content": [{"type": "input_text", "text": "<permissions>"}]}) is None
    True
    """
    if item["type"] == "agent_message":
        return f"[{item['author']} to {item['recipient']}]\n{text_of(item['content'])}"
    if item["type"] != "message" or item["role"] == "developer" or text_of(item["content"]).startswith(INJECTED_USER_PREFIXES):
        return None
    return f"[{item['role']}]\n{text_of(item['content'])}"


def compaction_summary(replacement_history: list[dict[str, object]]) -> str:
    """Describe a Codex compaction to a model that cannot read its encrypted summary: the preface, then every replayed message."""
    return COMPACTION_PREFACE + "\n\n---\n\n".join(text for text in map(replay_text, replacement_history) if text is not None)


def image_block(data_url: str) -> dict[str, object]:
    """Split a Codex data URL into Pi's image block.

    >>> image_block("data:image/png;base64,iVBOR")
    {'type': 'image', 'mimeType': 'image/png', 'data': 'iVBOR'}
    """
    header, _, data = data_url.partition(",")
    return {"type": "image", "mimeType": header.removeprefix("data:").removesuffix(";base64"), "data": data}


def pi_content_blocks(content: str | list[dict[str, object]]) -> list[dict[str, object]]:
    """Render Codex message content as Pi content blocks: text stays text, images become image blocks, ciphertext becomes a placeholder."""
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    blocks: list[dict[str, object]] = []
    for block in content:
        if block["type"] in ("input_text", "output_text"):
            blocks.append({"type": "text", "text": block["text"]})
        elif block["type"] == "input_image":
            blocks.append(image_block(str(block["image_url"])))
        elif block["type"] == "encrypted_content":
            blocks.append({"type": "text", "text": ENCRYPTED_PLACEHOLDER})
        else:
            raise ValueError(f"Cannot render Codex content block {block['type']!r} in Pi")
    return blocks


def tool_name(payload: dict[str, object]) -> str:
    """Name a Codex function call for another harness, keeping its namespace so same-named tools stay distinct.

    >>> tool_name({"namespace": "mcp__cua_repl", "name": "js"})
    'mcp__cua_repl__js'
    >>> tool_name({"name": "wait"})
    'wait'
    """
    return "__".join(str(part) for part in (payload.get("namespace"), payload["name"]) if part)


def hide_ciphertext(value: object) -> object:
    """Replace every ciphertext string inside tool arguments with a placeholder, keeping the readable fields.

    >>> hide_ciphertext({"task_name": "hud", "message": "gAAAAABqsX_G", "timeout_ms": 60000})
    {'task_name': 'hud', 'message': '[Codex ciphertext: only OpenAI can read this part]', 'timeout_ms': 60000}
    """
    if isinstance(value, str) and value.startswith(CIPHERTEXT_PREFIX):
        return ENCRYPTED_PLACEHOLDER
    if isinstance(value, dict):
        return {key: hide_ciphertext(item) for key, item in value.items()}
    if isinstance(value, list):
        return [hide_ciphertext(item) for item in value]
    return value


def needs_coordination_replay(payload: dict[str, object]) -> bool:
    """Identify opaque coordination items that Pi's ordinary content cannot represent.

    >>> needs_coordination_replay({"type": "agent_message", "content": [{"type": "encrypted_content"}]})
    True
    >>> needs_coordination_replay({"type": "function_call", "name": "write", "arguments": '{"content":"gAAAAA-file-text"}'})
    False
    """
    if payload["type"] == "function_call":
        arguments = json.loads(str(payload["arguments"]))
        return bool(payload.get("encrypted_function_args")) or (
            payload.get("namespace") in ("collaboration", "notes", "history") and hide_ciphertext(arguments) != arguments
        )
    content = payload.get("content", payload.get("output", []))
    return isinstance(content, list) and any(block.get("type") == "encrypted_content" for block in content)


def bash_result(raw: str) -> tuple[str, bool]:
    """Unwrap a Codex exec result into Pi bash result text and an error flag.

    >>> bash_result('Script completed\\nWall time 1s\\nOutput:\\n{"chunk_id":"a","exit_code":1,"output":"boom"}')
    ('boom\\n\\nCommand exited with code 1', True)
    """
    head, separator, rest = raw.partition("Output:\n")
    if not separator:
        return raw, False
    lines = [line for line in head.split("\n") if line and line != "Script completed" and not line.startswith("Wall time")]
    exit_codes: list[int] = []
    decoder = json.JSONDecoder()
    position = 0
    while position < len(rest):
        if rest[position].isspace():
            position += 1
            continue
        try:
            value, end = decoder.raw_decode(rest, position)
        except json.JSONDecodeError:
            newline = rest.find("\n", position)
            end = len(rest) if newline < 0 else newline
            lines.append(rest[position:end])
            position = end
            continue
        position = end
        record = value.get("value", value) if isinstance(value, dict) else value
        if isinstance(record, dict) and "output" in record:
            lines.append(str(record["output"]))
            exit_codes.append(record.get("exit_code"))
        elif record:
            lines.append(dumps(record))
    text = "\n".join(lines)
    failures = [code for code in exit_codes if code not in (0, None)]
    if failures:
        return f"{text}\n\nCommand exited with code {failures[0]}", True
    return text, False


@dataclass
class Item:
    timestamp: str
    ordinal: int
    kind: str
    payload: dict[str, object]
    record: dict[str, object] | None


def with_compaction_replay(items: Iterable[Item]) -> Iterator[Item]:
    """Expand a checkpoint into the items Codex replays without archiving them a second time.

    >>> checkpoint = Item("now", 3, "compacted", {"replacement_history": [{"type": "compaction"}]}, {})
    >>> [(item.kind, item.record) for item in with_compaction_replay([checkpoint])]
    [('compacted', {}), ('response_item', None)]
    """
    for item in items:
        yield item
        if item.kind != "compacted":
            continue
        for payload in item.payload["replacement_history"]:
            yield Item(item.timestamp, item.ordinal, "response_item", payload, None)


def item_from_record(record: dict[str, object], default_ordinal: int) -> Item:
    return Item(
        str(record["timestamp"]),
        int(record.get("ordinal", default_ordinal)),
        str(record["type"]),
        record["payload"],
        record,
    )


def load_items(path: Path) -> list[Item]:
    with path.open() as handle:
        return [
            item_from_record(json.loads(line), ordinal)
            for ordinal, line in enumerate(handle)
        ]


def load_first_item(path: Path) -> Item:
    with path.open() as handle:
        return item_from_record(json.loads(handle.readline()), 0)


@dataclass
class Subagent:
    """A native Codex sub-agent, modeled as a pi-subagents task whose child session is the sub-agent rollout."""

    agent_path: str
    nickname: str
    started_at: str
    session_id: str
    tool_call_timestamps: list[str]
    rollout: Path

    @classmethod
    def from_rollout(cls, rollout: Path, agent_path: str, started_at: str) -> "Subagent":
        items = load_items(rollout)
        meta = items[0].payload
        nickname = str(meta["source"]["subagent"]["thread_spawn"]["agent_nickname"])
        tool_call_timestamps = [item.timestamp for item in items[1:] if item.kind == "response_item" and item.payload["type"] in ("custom_tool_call", "function_call")]
        return cls(agent_path, nickname, started_at, uuidv7(epoch_ms(meta["timestamp"])), tool_call_timestamps, rollout)

    @property
    def description(self) -> str:
        return f"Codex sub-agent {self.agent_path} ({self.nickname})"

    def notification(self, payload: dict[str, object], until: str) -> dict[str, object]:
        """Render a delivered message with its original attribution and task status."""
        text = text_of(payload["content"])
        status = "completed" if text.startswith("Message Type: FINAL_ANSWER") else "running"
        details = {
            "id": self.session_id,
            "description": self.description,
            "status": status,
            "toolUses": sum(1 for timestamp in self.tool_call_timestamps if timestamp <= until),
            "turnCount": 0,
            "totalTokens": 0,
            "durationMs": epoch_ms(until) - epoch_ms(self.started_at),
            "resultPreview": text[:500],
        }
        content = agent_message_text(payload)
        details.update({"author": payload["author"], "recipient": payload["recipient"]})
        return {"customType": SUBAGENT_NOTIFICATION_TYPE, "content": content, "display": True, "details": details}

    def record(self, payload: dict[str, object], until: str) -> dict[str, object]:
        return {
            "id": self.session_id,
            "type": "codex-subagent",
            "description": self.description,
            "status": "completed",
            "result": text_of(payload["content"]),
            "startedAt": epoch_ms(self.started_at),
            "completedAt": epoch_ms(until),
        }


@dataclass(frozen=True)
class PiPrefix:
    lines: list[str]
    source_ordinals: list[int | None]


@dataclass
class PiWriter:
    lines: list[str] = field(default_factory=list)
    source_ordinals: list[int | None] = field(default_factory=list)
    leaf_id: str | None = None
    used_ids: set[str] = field(default_factory=set)

    @classmethod
    def from_prefix(cls, prefix: PiPrefix | None) -> "PiWriter":
        if prefix is None:
            return cls()
        identifiers = {str(json.loads(line)["id"]) for line in prefix.lines}
        return cls(
            lines=list(prefix.lines),
            source_ordinals=list(prefix.source_ordinals),
            leaf_id=str(json.loads(prefix.lines[-1])["id"]),
            used_ids=identifiers,
        )

    def new_id(self) -> str:
        while True:
            candidate = secrets.token_hex(4)
            if candidate not in self.used_ids:
                self.used_ids.add(candidate)
                return candidate

    def append(
        self,
        entry_type: str,
        timestamp: str,
        body: dict[str, object],
        source_ordinal: int | None = None,
        entry_id: str | None = None,
    ) -> str:
        entry_id = entry_id or self.new_id()
        self.lines.append(dumps({"type": entry_type, "id": entry_id, "parentId": self.leaf_id, "timestamp": timestamp, **body}))
        self.source_ordinals.append(source_ordinal)
        self.leaf_id = entry_id
        return entry_id

    def prefix_before(self, source_ordinal: int) -> PiPrefix:
        selected_count = len(self.lines)
        for index, ordinal in enumerate(self.source_ordinals):
            if ordinal is not None and ordinal >= source_ordinal:
                selected_count = index
                break
        residues = self.source_ordinals[selected_count:]
        if any(ordinal is not None and ordinal < source_ordinal for ordinal in residues):
            raise ValueError(f"Pi entries are not ordered at Codex fork ordinal {source_ordinal}")
        return PiPrefix(self.lines[:selected_count], self.source_ordinals[:selected_count])

    def current_settings(self) -> tuple[str | None, str | None]:
        model: str | None = None
        thinking_level: str | None = None
        for line in self.lines:
            entry = json.loads(line)
            if entry["type"] == "model_change":
                model = str(entry["modelId"])
            elif entry["type"] == "thinking_level_change":
                thinking_level = str(entry["thinkingLevel"])
            elif entry["type"] == "message" and entry["message"]["role"] == "assistant":
                model = str(entry["message"]["model"])
        return model, thinking_level

    def replay_lines(self) -> list[str]:
        """Label imported assistant messages for the destination model without changing their archived originals."""
        model, _ = self.current_settings()
        entries = [json.loads(line) for line in self.lines]
        for entry in entries:
            replay = entry.get("codexReplay")
            if replay and (model is None or replay["model"] is None or reasoning_family(replay["model"]) != reasoning_family(model)):
                raise ValueError(f"Cannot preserve opaque coordination across incompatible model families: {replay['model']} -> {model}")
            message = entry.get("message", {})
            if message.get("role") != "assistant":
                continue
            has_reasoning = any(block.get("thinkingSignature") for block in message["content"])
            if has_reasoning and (model is None or message["model"] is None or reasoning_family(message["model"]) != reasoning_family(model)):
                raise ValueError(f"Cannot preserve reasoning across incompatible model families: {message['model']} -> {model}")
            message["model"] = model
        return [dumps(entry) for entry in entries]


@dataclass
class PendingAssistant:
    blocks: list[dict[str, object]] = field(default_factory=list)
    source_ordinals: list[int] = field(default_factory=list)
    timestamp: str | None = None


def reasoning_block(payload: dict[str, object]) -> dict[str, object]:
    """Carry an opaque OpenAI reasoning or compaction item in Pi's provider replay signature."""
    summary_text = "\n\n".join(str(part["text"]) for part in payload.get("summary") or [])
    return {"type": "thinking", "thinking": summary_text, "thinkingSignature": dumps(payload)}


def text_block(payload: dict[str, object]) -> dict[str, object]:
    """Carry the Codex assistant message id and phase in the slot Pi's Codex provider reads back."""
    signature = {"v": 1, "id": payload["id"]}
    if "phase" in payload:
        signature["phase"] = payload["phase"]
    return {"type": "text", "text": text_of(payload["content"]), "textSignature": dumps(signature)}


def session_directory(sessions_root: Path, cwd: str) -> Path:
    return sessions_root / ("--" + cwd.replace("/", "-").lstrip("-") + "--")


def session_filename(started_at: str, session_id: str) -> str:
    return f"{started_at.replace(':', '-').replace('.', '-')}_{session_id}.jsonl"


@dataclass
class ConvertedSession:
    path: Path
    writer: PiWriter

    def prefix_before(self, source_ordinal: int) -> PiPrefix:
        return self.writer.prefix_before(source_ordinal)


@dataclass
class Conversion:
    rollout: Path
    sessions_root: Path
    name: str
    session_id: str
    subagents: dict[str, Subagent] = field(default_factory=dict)
    parent_session: str | None = None
    prefix: PiPrefix | None = None
    fork_cutoffs: set[int] = field(default_factory=set)
    source_items: tuple[Item, ...] | None = None

    def run(self) -> ConvertedSession:
        items = list(self.source_items) if self.source_items is not None else load_items(self.rollout)
        meta = items[0].payload
        cwd = str(meta["cwd"])
        started_at = str(meta["timestamp"])
        writer = PiWriter.from_prefix(self.prefix)
        writer.append("session_info", started_at, {"name": self.name})
        dispatch = restored_dispatch(meta.get("piRuntime", {}))
        if dispatch is not None:
            writer.append("custom", started_at, {"customType": "pi-user-agents-dispatch", "data": dispatch, "codex": []})
        model, thinking_level = writer.current_settings()
        pending = PendingAssistant()
        call_names: dict[str, str] = {}
        call_pi_ids: dict[str, str] = {}
        staged: list[Item] = []
        current: list[Item] = []

        def carried(consume_current: bool) -> dict[str, object]:
            """Take every staged record, and the item being converted when asked, for the entry written next."""
            records = [*staged, *current] if consume_current else list(staged)
            staged.clear()
            if consume_current:
                current.clear()
            replay = [item.payload for item in records if item.kind == "response_item" and needs_coordination_replay(item.payload)]
            return {"codex": [item.record for item in records if item.record is not None],
                    **({"codexReplay": {"model": model, "items": replay}} if replay else {})}

        def emit(entry_type: str, timestamp: str, body: dict[str, object], entry_id: str | None = None) -> str:
            archived = carried(True)
            entry_id = entry_id or writer.new_id()
            if entry_type == "custom_message" and "codexReplay" in archived:
                body = {**body, "details": {**body.get("details", {}), "codexReplayEntryId": entry_id}}
            return writer.append(entry_type, timestamp, {**body, **archived}, source_ordinal=item.ordinal, entry_id=entry_id)

        def flush(stop_reason: str) -> None:
            if not pending.blocks:
                return
            message = {
                "role": "assistant",
                "content": pending.blocks,
                "api": API,
                "provider": PROVIDER,
                "model": model,
                "usage": ZERO_USAGE,
                "stopReason": stop_reason,
                "timestamp": epoch_ms(pending.timestamp),
            }
            source_ordinal = max(staged_item.ordinal for staged_item in staged)
            writer.append("message", pending.timestamp, {"message": message, **carried(False)}, source_ordinal)
            pending.blocks, pending.source_ordinals, pending.timestamp = [], [], None

        def flush_records() -> None:
            """Write the assistant turn and any records still waiting, so nothing crosses a fork point."""
            flush("stop")
            if staged:
                last = staged[-1]
                writer.append("custom", last.timestamp, {"customType": CODEX_RECORD_TYPE, **carried(False)}, source_ordinal=last.ordinal)

        def add_pending(block: dict[str, object], timestamp: str, source_ordinal: int) -> None:
            pending.timestamp = pending.timestamp or timestamp
            pending.blocks.append(block)
            pending.source_ordinals.append(source_ordinal)
            staged.extend(current)
            current.clear()

        def add_tool_call(
            payload: dict[str, object],
            name: str,
            arguments: dict[str, object],
            timestamp: str,
            source_ordinal: int,
        ) -> None:
            pi_call_id = f"{payload['call_id']}|{payload['id']}"
            call_names[str(payload["call_id"])] = name
            call_pi_ids[str(payload["call_id"])] = pi_call_id
            add_pending({"type": "toolCall", "id": pi_call_id, "name": name, "arguments": arguments,
                         **({"namespace": payload["namespace"]} if payload.get("namespace") else {})}, timestamp, source_ordinal)

        def add_tool_result(
            payload: dict[str, object],
            content: list[dict[str, object]],
            is_error: bool,
            timestamp: str,
            source_ordinal: int,
        ) -> None:
            flush("toolUse")
            call_id = str(payload["call_id"])
            message = {
                "role": "toolResult",
                "toolCallId": call_pi_ids[call_id],
                "toolName": call_names[call_id],
                "content": content,
                "isError": is_error,
                "timestamp": epoch_ms(timestamp),
            }
            emit("message", timestamp, {"message": message})

        def add_user_message(payload: dict[str, object], blocks: list[dict[str, object]], timestamp: str, source_ordinal: int) -> None:
            flush("stop")
            message = {"role": "user", "content": blocks, "timestamp": epoch_ms(timestamp)}
            emit("message", timestamp, {"message": message})

        cutoffs_ahead = sorted(self.fork_cutoffs)
        for item in with_compaction_replay(items[1:]):
            timestamp, payload = item.timestamp, item.payload
            if cutoffs_ahead and item.ordinal >= cutoffs_ahead[0]:
                flush_records()
                cutoffs_ahead = [cutoff for cutoff in cutoffs_ahead if cutoff > item.ordinal]
            current.append(item)

            if item.kind == "turn_context":
                next_model = str(payload["model"]).removeprefix("openai-codex/")
                next_thinking_level = str(payload["effort"])
                if next_model != model or next_thinking_level != thinking_level:
                    flush("stop")
                if next_model != model:
                    model = next_model
                    emit("model_change", timestamp, {"provider": PROVIDER, "modelId": model})
                if next_thinking_level != thinking_level:
                    thinking_level = next_thinking_level
                    emit("thinking_level_change", timestamp, {"thinkingLevel": thinking_level})
                staged.extend(current)
                current.clear()
                continue

            if item.kind == "compacted":
                flush("stop")
                summary = "Codex checkpoint. The retained conversation and replay state follow."
                usage_record = payload.get("latest_token_usage_record") or {"usage": {"total_tokens": 0}}
                entry_id = writer.new_id()
                emit("compaction", timestamp, {"summary": summary, "firstKeptEntryId": entry_id, "tokensBefore": usage_record["usage"]["total_tokens"]}, entry_id=entry_id)
                continue

            if item.kind != "response_item":
                staged.extend(current)
                current.clear()
                continue

            item_type = payload["type"]

            if item_type in ("reasoning", "compaction", "context_compaction"):
                add_pending(reasoning_block(payload), timestamp, item.ordinal)
            elif item_type == "message" and payload["role"] == "assistant":
                add_pending(text_block(payload), timestamp, item.ordinal)
            elif item_type == "custom_tool_call":
                add_tool_call(
                    payload,
                    str(payload["name"]),
                    {"input": payload["input"]},
                    timestamp,
                    item.ordinal,
                )
            elif item_type == "function_call":
                arguments = json.loads(str(payload["arguments"]))
                arguments = hide_ciphertext(arguments) if payload.get("namespace") in ("collaboration", "notes", "history") else arguments
                add_tool_call(payload, str(payload["name"]), arguments, timestamp, item.ordinal)
            elif item_type in ("custom_tool_call_output", "function_call_output"):
                _, is_error = bash_result(text_of(payload["output"]))
                add_tool_result(payload, pi_content_blocks(payload["output"]), is_error, timestamp, item.ordinal)
            elif item_type == "tool_search_call":
                add_tool_call(payload, "tool_search", dict(payload["arguments"]), timestamp, item.ordinal)
            elif item_type == "tool_search_output":
                add_tool_result(payload, [{"type": "text", "text": dumps(payload["tools"])}], False, timestamp, item.ordinal)
            elif item_type == "message" and payload["role"] == "user":
                blocks = [block for block in pi_content_blocks(payload["content"])
                          if block["type"] != "text" or not block["text"].startswith(INJECTED_USER_PREFIXES)]
                if not blocks:
                    staged.extend(current)
                    current.clear()
                    continue
                add_user_message(payload, blocks, timestamp, item.ordinal)
            elif item_type == "message" and payload["role"] == "developer":
                staged.extend(current)
                current.clear()
            elif item_type == "agent_message" and str(payload["author"]) in self.subagents:
                flush("stop")
                subagent = self.subagents[str(payload["author"])]
                emit("custom_message", timestamp, subagent.notification(payload, timestamp))
                if text_of(payload["content"]).startswith("Message Type: FINAL_ANSWER"):
                    emit("custom", timestamp, {"customType": SUBAGENT_RECORD_TYPE, "data": subagent.record(payload, timestamp)})
            elif item_type == "agent_message" and needs_coordination_replay(payload):
                flush("stop")
                emit("custom_message", timestamp, {"customType": "codex-agent-message", "content": agent_message_text(payload), "display": True})
            elif item_type == "agent_message":
                blocks = [{"type": "text", "text": agent_message_text(payload)}]
                add_user_message(payload, blocks, timestamp, item.ordinal)
            else:
                raise ValueError(f"Unhandled response_item type at {timestamp}: {item_type}")

        flush_records()

        header: dict[str, object] = {"type": "session", "version": 3, "id": self.session_id, "timestamp": started_at, "cwd": cwd, "codex": items[0].record}
        if self.parent_session:
            header["parentSession"] = self.parent_session

        replay_lines = writer.replay_lines()
        directory = session_directory(self.sessions_root, cwd)
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / session_filename(started_at, self.session_id)
        with target.open("w") as out:
            out.write(dumps(header) + "\n")
            out.write("\n".join(replay_lines) + "\n")
        print(f"wrote {target}", file=sys.stderr)
        print(f"  entries: {len(writer.lines)}", file=sys.stderr)
        replay_extension = Path(__file__).with_name("codex-replay.ts").resolve()
        extension_argument = f" --extension {shlex.quote(str(replay_extension))}"
        print(f"  resume with: pi{extension_argument} --session {shlex.quote(str(target))}", file=sys.stderr)
        return ConvertedSession(target, writer)


def is_subagent_source(source: object) -> bool:
    """Return whether Codex created the session as a native sub-agent.

    >>> is_subagent_source({"subagent": {"thread_spawn": {}}})
    True
    >>> is_subagent_source("cli")
    False
    """
    return isinstance(source, dict) and "subagent" in source


@dataclass(frozen=True)
class CodexRolloutSegment:
    rollout: Path
    metadata: Item


@dataclass(frozen=True)
class CodexSessionNode:
    session_id: str
    rollout: Path
    segments: tuple[CodexRolloutSegment, ...]
    fork_parent_id: str | None
    fork_ordinal: int | None
    history_base: dict[str, object] | None


def segment_history_base(segment: CodexRolloutSegment) -> dict[str, object] | None:
    value = segment.metadata.payload.get("history_base")
    return value if isinstance(value, dict) else None


def build_session_node(session_id: str, segments: list[CodexRolloutSegment]) -> CodexSessionNode:
    current = max(
        segments,
        key=lambda segment: (
            segment.metadata.ordinal,
            segment.metadata.timestamp,
            str(segment.rollout),
        ),
    )
    reverse_chain = [current]
    seen_paths = {current.rollout}
    while True:
        history_base = segment_history_base(current)
        if history_base is None or history_base.get("thread_id") != session_id:
            break
        cutoff = int(history_base["end_ordinal_exclusive"])
        if cutoff != current.metadata.ordinal:
            raise ValueError(
                f"Codex rollout segment {current.rollout} starts at {current.metadata.ordinal}, "
                f"but its history base ends at {cutoff}"
            )
        candidates = [
            segment
            for segment in segments
            if segment.rollout not in seen_paths and segment.metadata.ordinal < cutoff
        ]
        predecessor = max(
            candidates,
            key=lambda segment: (
                segment.metadata.ordinal,
                segment.metadata.timestamp,
                str(segment.rollout),
            ),
            default=None,
        )
        if predecessor is None:
            raise FileNotFoundError(
                f"Codex rollout segment {current.rollout} refers to missing history before ordinal {cutoff}"
            )
        reverse_chain.append(predecessor)
        seen_paths.add(predecessor.rollout)
        current = predecessor

    chain = list(reversed(reverse_chain))
    oldest = chain[0]
    payload = oldest.metadata.payload
    source = payload.get("source")
    parent = None if is_subagent_source(source) else payload.get("forked_from_id")
    fork_ordinal = payload.get("forked_from_ordinal_exclusive")
    history_base = segment_history_base(oldest)
    return CodexSessionNode(
        session_id,
        reverse_chain[0].rollout,
        tuple(chain),
        str(parent) if parent else None,
        int(fork_ordinal) if fork_ordinal is not None else None,
        history_base,
    )


def load_node_items(node: CodexSessionNode) -> tuple[Item, ...]:
    merged = [node.segments[0].metadata]
    for index, segment in enumerate(node.segments):
        items = load_items(segment.rollout)
        upper_bound = node.segments[index + 1].metadata.ordinal if index + 1 < len(node.segments) else None
        if upper_bound is not None and max(item.ordinal for item in items) < upper_bound - 1:
            raise FileNotFoundError(
                f"Codex rollout segment {segment.rollout} does not reach required ordinal {upper_bound - 1}"
            )
        merged.extend(
            item
            for item in items
            if item.kind != "session_meta" and (upper_bound is None or item.ordinal < upper_bound)
        )
    ordinals = [item.ordinal for item in merged if "ordinal" in item.record]
    if ordinals != sorted(set(ordinals)):  # A thread rename is written without an ordinal.
        raise ValueError(f"Codex rollout segments for {node.session_id} do not form one ordered history")
    return tuple(merged)


@dataclass
class CodexSessionGraph:
    sessions_root: Path
    nodes: dict[str, CodexSessionNode]
    fork_children: dict[str, list[str]]
    names: dict[str, str]

    @classmethod
    def load(cls, sessions_root: Path) -> "CodexSessionGraph":
        segments_by_session: dict[str, list[CodexRolloutSegment]] = {}
        for rollout in sorted(sessions_root.rglob("*.jsonl")):
            with rollout.open() as handle:
                first_record = json.loads(handle.readline())
            if first_record.get("type") != "session_meta":
                continue
            metadata = item_from_record(first_record, 0)
            session_id = str(metadata.payload["id"])
            segments_by_session.setdefault(session_id, []).append(CodexRolloutSegment(rollout, metadata))

        nodes = {
            session_id: build_session_node(session_id, segments)
            for session_id, segments in segments_by_session.items()
        }
        fork_children = {session_id: [] for session_id in nodes}
        for node in nodes.values():
            if node.fork_parent_id in fork_children:
                fork_children[node.fork_parent_id].append(node.session_id)
        for children in fork_children.values():
            children.sort()
        return cls(sessions_root, nodes, fork_children, load_session_names(sessions_root.parent / "session_index.jsonl"))

    def descendants(self, session_id: str) -> list[str]:
        """List every fork descendant of a session, because a grandchild can fork inside history its parent inherited."""
        return [descendant for child_id in self.fork_children[session_id] for descendant in (child_id, *self.descendants(child_id))]

    def ancestors(self, session_id: str) -> list[str]:
        """List the fork ancestors of a session, nearest first."""
        chain: list[str] = []
        current = self.nodes[session_id].fork_parent_id
        while current in self.nodes:
            chain.append(current)
            current = self.nodes[current].fork_parent_id
        return chain

    def root_of(self, session_id: str) -> str:
        if session_id not in self.nodes:
            raise FileNotFoundError(f"Could not find Codex session {session_id} under {self.sessions_root}")
        seen: set[str] = set()
        current = session_id
        while self.nodes[current].fork_parent_id:
            if current in seen:
                raise ValueError(f"Codex fork ancestry cycles at {current}")
            seen.add(current)
            parent = self.nodes[current].fork_parent_id
            if parent not in self.nodes:
                raise FileNotFoundError(f"Codex session {current} refers to missing fork parent {parent}")
            current = parent
        return current


def load_session_names(index_path: Path) -> dict[str, str]:
    names: dict[str, str] = {}
    if not index_path.exists():
        return names
    with index_path.open() as handle:
        for line in handle:
            record = json.loads(line)
            session_id = record.get("id")
            name = record.get("thread_name")
            if isinstance(session_id, str) and isinstance(name, str):
                names[session_id] = name
    return names


def find_subagents(items: list[Item], codex_sessions_root: Path) -> dict[str, Subagent]:
    """Map the path of every sub-agent that these items start to the sub-agent."""
    subagents: dict[str, Subagent] = {}
    for item in items:
        activity = item.payload.get("item", item.payload) if item.kind == "event_msg" else {}
        if activity.get("type") not in ("SubAgentActivity", "sub_agent_activity") or activity.get("kind") != "started":
            continue
        rollout = next(codex_sessions_root.rglob(f"*{activity['agent_thread_id']}*.jsonl"), None)
        if rollout is None:
            print(f"Skipping missing child JSONL: {activity['agent_thread_id']}", file=sys.stderr)
            continue
        subagents[str(activity["agent_path"])] = Subagent.from_rollout(rollout, str(activity["agent_path"]), item.timestamp)
    return subagents


def fork_cutoff(node: CodexSessionNode, ancestry: list[str]) -> int | None:
    """Return the parent ordinal where a fork child's own history starts, or None when its rollout holds its whole history.

    The history before that ordinal can live in any ancestor's rollout, so `history_base` may name a grandparent.
    """
    if node.fork_ordinal is None:
        if node.history_base is not None:
            raise ValueError(f"Codex fork {node.session_id} has history_base without a fork ordinal")
        return None
    if node.history_base is None:
        raise ValueError(f"Codex fork {node.session_id} has a fork ordinal without history_base")
    if node.history_base.get("thread_id") not in ancestry or node.history_base.get("end_ordinal_exclusive") != node.fork_ordinal:
        raise ValueError(f"Codex fork {node.session_id} has a history_base outside its ancestry {ancestry}: {node.history_base!r}")
    return node.fork_ordinal


def inlines_parent_history(meta: dict[str, object]) -> bool:
    """Whether a session_meta record belongs to a fork child that reads its parent's history by reference."""
    history_base = meta["payload"].get("history_base")
    return isinstance(history_base, dict) and history_base.get("thread_id") != meta["payload"]["id"]


def restored_rollout(records: list[dict[str, object]]) -> list[dict[str, object]]:
    """Return a converted session's Codex records as one rollout that Codex can resume on its own.

    A converted fork child holds its parent's history inline, so its session_meta drops the fork links and takes ordinal 0.

    >>> meta = {"type": "session_meta", "ordinal": 4, "payload": {"id": "child", "forked_from_id": "parent", "history_base": {"thread_id": "parent"}}}
    >>> restored_rollout([meta])
    [{'type': 'session_meta', 'ordinal': 0, 'payload': {'id': 'child'}}]
    """
    meta, *rest = records
    if not inlines_parent_history(meta):
        return records
    standalone = {**meta, "payload": {key: value for key, value in meta["payload"].items() if key not in FORK_KEYS}}
    if "ordinal" in meta:
        standalone["ordinal"] = 0
    return [standalone, *rest]


def rollout_filename(meta: dict[str, object]) -> str:
    """Name a rollout the way Codex does, because `codex resume` finds a session by the id at the end of its file name.

    >>> rollout_filename({"id": "01a0", "timestamp": "2026-09-08T07:32:19.851Z"})
    'rollout-2026-09-08T07-32-19-01a0.jsonl'
    """
    return f"rollout-{str(meta['timestamp'])[:19].replace(':', '-')}-{meta['id']}.jsonl"


def write_restored_rollout(records: list[dict[str, object]], output_directory: Path) -> Path:
    """Write restored Codex records under the file name that `codex resume` looks for."""
    output_directory.mkdir(parents=True, exist_ok=True)
    target = output_directory / rollout_filename(records[0]["payload"])
    target.write_text("".join(dumps(record) + "\n" for record in records), encoding="utf-8")
    print(f"wrote {target}", file=sys.stderr)
    return target


def convert_fork_tree(
    selected_session_id: str,
    codex_sessions_root: Path,
    pi_sessions_root: Path,
    selected_name: str,
) -> dict[str, Path]:
    """Convert the complete persisted fork tree containing one Codex session.

    The selected session can sit anywhere in the tree. Native Codex sub-agents become
    pi-subagents child sessions and are not mistaken for user-created forks.
    """
    graph = CodexSessionGraph.load(codex_sessions_root)
    tree_root_id = graph.root_of(selected_session_id)
    converted_sessions: dict[str, ConvertedSession] = {}
    subagent_paths: dict[str, Path] = {}

    def convert_subagents(subagents: dict[str, Subagent], parent: ConvertedSession, parent_name: str) -> None:
        for subagent in subagents.values():
            items = load_items(subagent.rollout)
            nested = find_subagents(items, codex_sessions_root)
            name = f"{parent_name} — sub-agent {subagent.agent_path} ({subagent.nickname})"
            converted = Conversion(subagent.rollout, pi_sessions_root, name, subagent.session_id, nested, str(parent.path), source_items=tuple(items)).run()
            subagent_paths[str(items[0].payload["id"])] = converted.path
            convert_subagents(nested, converted, name)

    def convert_node(session_id: str) -> None:
        node = graph.nodes[session_id]
        parent = converted_sessions.get(node.fork_parent_id) if node.fork_parent_id else None
        cutoff = fork_cutoff(node, graph.ancestors(session_id)) if parent else None
        prefix = parent.prefix_before(cutoff) if cutoff is not None else None
        parent_session = str(parent.path) if parent else None
        source_items = load_node_items(node)
        items = list(source_items)
        subagents = find_subagents(items, codex_sessions_root)
        name = graph.names.get(session_id, f"{selected_name} — Codex fork {session_id}")
        if session_id == selected_session_id:
            name = selected_name
        descendant_cutoffs = {
            graph.nodes[descendant_id].fork_ordinal
            for descendant_id in graph.descendants(session_id)
            if graph.nodes[descendant_id].fork_ordinal is not None
        }
        session_id_for_pi = uuidv7(epoch_ms(str(items[0].payload["timestamp"])))
        converted = Conversion(
            node.rollout,
            pi_sessions_root,
            name,
            session_id_for_pi,
            subagents,
            parent_session,
            prefix,
            descendant_cutoffs,
            source_items,
        ).run()
        converted_sessions[session_id] = converted
        convert_subagents(subagents, converted, name)

        for child_id in graph.fork_children[session_id]:
            convert_node(child_id)

    convert_node(tree_root_id)
    return {**{session_id: converted.path for session_id, converted in converted_sessions.items()}, **subagent_paths}


def sessions_root_for_rollout(rollout: Path) -> Path:
    for parent in rollout.parents:
        if parent.name == "sessions":
            return parent
    raise ValueError(f"Codex rollout is not under a sessions directory: {rollout}")


def resolve_codex_input(source: str | Path) -> tuple[str, Path]:
    rollout = Path(source).expanduser()
    if rollout.exists():
        items = load_items(rollout)
        return str(items[0].payload["id"]), sessions_root_for_rollout(rollout.resolve())
    codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    return str(source), codex_home / "sessions"


def main(source: str | Path, sessions_root: Path, name: str) -> dict[str, Path]:
    selected_session_id, codex_sessions_root = resolve_codex_input(source)
    return convert_fork_tree(selected_session_id, codex_sessions_root, sessions_root, name)


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit("usage: codex_to_pi.py <codex-session-id-or-rollout.jsonl> <pi-sessions-root> <session-name>")
    main(sys.argv[1], Path(sys.argv[2]), sys.argv[3])
