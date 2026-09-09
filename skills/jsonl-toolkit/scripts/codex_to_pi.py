#!/usr/bin/env -S uv run
# /// script
# requires-python = "==3.12.*"
# dependencies = []
# ///
"""Synthesize a native Pi session tree from any persisted Codex session node.

The converter follows native fork ancestry in both directions, rebuilds paginated rollout
segments, copies each fork-point history into its Pi child, and sets `parentSession`.
It also ports messages, reasoning, shell tools, compaction, and native Codex sub-agents.
Sub-agents become pi-user-agents objects and separate Pi sessions. Codex side chats remain
absent because Codex keeps them ephemeral and writes no rollout. Codex-internal
notes/history/collaboration calls carry only ciphertext and are dropped.
"""

import json
import os
import re
import secrets
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal

PROVIDER = "openai-codex"
API = "openai-codex-responses"
ZERO_USAGE = {
    "input": 0,
    "output": 0,
    "cacheRead": 0,
    "cacheWrite": 0,
    "totalTokens": 0,
    "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0, "total": 0},
}
INJECTED_USER_PREFIXES = ("<environment_context>", "# AGENTS.md instructions", "<recommended_plugins>")
DROPPED_NAMESPACES = {"notes", "history", "collaboration"}
SQUASH_PREFACE = "The user has dispatched a background sub-agent with a task. The sub-agent is done. The following is the back and forth between them:"
ENCRYPTED_NOTE = "[Encrypted by Codex. Only the ciphertext was stored.]"

Role = Literal["root", "subagent"]


def uuidv7(at_ms: int) -> str:
    value = (at_ms << 80) | (0x7 << 76) | (secrets.randbits(12) << 64) | (0b10 << 62) | secrets.randbits(62)
    hex_value = f"{value:032x}"
    return f"{hex_value[:8]}-{hex_value[8:12]}-{hex_value[12:16]}-{hex_value[16:20]}-{hex_value[20:]}"


def epoch_ms(iso: str) -> int:
    return int(datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp() * 1000)


def dumps(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def text_of(content: str | list[dict[str, object]]) -> str:
    if isinstance(content, str):
        return content
    return "".join(str(block.get("text", "")) for block in content if block.get("type") in ("input_text", "output_text"))


def escape_attribute(value: str) -> str:
    return value.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")


JS_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f", "v": "\v", "0": "\0"}


def read_js_string(script: str, start: int) -> str:
    """Decode a double-quoted JavaScript string literal whose opening quote is at `start`.

    >>> read_js_string('cmd:"echo \\\\"hi\\\\"\\\\n"', 4)
    'echo "hi"\\n'
    """
    assert script[start] == '"'
    characters: list[str] = []
    index = start + 1
    while script[index] != '"':
        if script[index] != "\\":
            characters.append(script[index])
            index += 1
            continue
        escaped = script[index + 1]
        if escaped == "u":
            characters.append(chr(int(script[index + 2 : index + 6], 16)))
            index += 6
        elif escaped == "x":
            characters.append(chr(int(script[index + 2 : index + 4], 16)))
            index += 4
        else:
            characters.append(JS_ESCAPES.get(escaped, escaped))
            index += 2
    return "".join(characters)


def js_call_arguments(script: str, open_paren: int) -> str:
    """Return the balanced source text between the parentheses opening at `open_paren`.

    >>> js_call_arguments('f({a:"x)",b:[1,(2)]}) + g()', 1)
    '{a:"x)",b:[1,(2)]}'
    """
    depth = 0
    index = open_paren
    while True:
        character = script[index]
        if character in "\"'`":
            index = script.index(character, index + 1)
            while script[index - 1] == "\\":
                index = script.index(character, index + 1)
        elif character in "([{":
            depth += 1
        elif character in ")]}":
            depth -= 1
            if depth == 0:
                return script[open_paren + 1 : index]
        index += 1


def parse_tool_calls(script: str) -> list[tuple[str, str]]:
    """List every `tools.<name>(...)` call in a Codex exec script as (name, argument source).

    >>> parse_tool_calls('text(await tools.exec_command({cmd:"ls"}));')
    [('exec_command', '{cmd:"ls"}')]
    """
    return [(match.group(1), js_call_arguments(script, match.end() - 1)) for match in re.finditer(r"tools\.(\w+)\(", script)]


def js_string_field(source: str, name: str) -> str | None:
    match = re.search(rf'(?<![\w"]){name}\s*:\s*"', source)
    return read_js_string(source, match.end() - 1) if match else None


def tool_call_to_bash(name: str, arguments: str) -> str | None:
    """Render one Codex exec tool call as a bash line, or None when its shape is not recognized.

    >>> tool_call_to_bash("exec_command", '{cmd:"ls",workdir:"/tmp"}')
    'cd /tmp && ls'
    >>> tool_call_to_bash("write_stdin", '{session_id:42,chars:"",yield_time_ms:1000}')
    '# Codex: poll background session 42 for output'
    """
    if name == "exec_command":
        command = js_string_field(arguments, "cmd")
        workdir = js_string_field(arguments, "workdir")
        if command is None:
            return None
        return f"cd {workdir} && {command}" if workdir else command
    if name == "apply_patch":
        if not arguments.startswith('"'):
            return None
        return f"apply_patch <<'PATCH'\n{read_js_string(arguments, 0)}\nPATCH"
    if name == "write_stdin":
        session = re.search(r"session_id\s*:\s*(\d+)", arguments)
        characters = js_string_field(arguments, "chars")
        if session is None or characters is None:
            return None
        if characters:
            return f"# Codex: write to background session {session.group(1)} stdin: {characters!r}"
        return f"# Codex: poll background session {session.group(1)} for output"
    compact = " ".join(arguments.split())
    return f"# Codex tool {name}({compact[:300]})"


def bash_command_for_exec(script: str) -> str:
    """Turn a Codex exec script into a bash command, one line per tool call it makes.

    >>> bash_command_for_exec('text(await tools.exec_command({cmd:"ls -la",workdir:"/tmp"}));')
    'cd /tmp && ls -la'
    """
    lines = [tool_call_to_bash(name, arguments) for name, arguments in parse_tool_calls(script)]
    if not lines or None in lines:
        return "# Codex exec script (JavaScript), run by the Codex exec tool\n" + script
    return "\n".join(line for line in lines if line is not None)


def bash_command_for_wait(arguments: dict[str, object]) -> str:
    return f"# Codex: wait up to {int(arguments['yield_time_ms']) // 1000}s for background exec cell {arguments['cell_id']}"


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
            exit_codes.append(int(record.get("exit_code", 0)))
        elif record:
            lines.append(dumps(record))
    text = "\n".join(lines)
    failures = [code for code in exit_codes if code != 0]
    if failures:
        return f"{text}\n\nCommand exited with code {failures[0]}", True
    return text, False


def question_text(arguments: dict[str, object]) -> str:
    parts: list[str] = ["Question to the user:"]
    for question in arguments["questions"]:
        parts.append(str(question["title"]))
        parts.extend(f"- {option}" for option in question.get("options", []))
    return "\n".join(parts)


@dataclass
class Item:
    timestamp: str
    ordinal: int
    kind: str
    payload: dict[str, object]


def item_from_record(record: dict[str, object], default_ordinal: int) -> Item:
    return Item(
        str(record["timestamp"]),
        int(record.get("ordinal", default_ordinal)),
        str(record["type"]),
        record["payload"],
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
class SquashMessage:
    role: Literal["user", "assistant"]
    text: str
    timestamp: str


@dataclass
class Subagent:
    agent_path: str
    nickname: str
    started_at: str
    model: str
    session_id: str
    task: str
    messages: list[SquashMessage]
    tool_call_timestamps: list[str]
    rollout: Path

    @classmethod
    def from_rollout(cls, rollout: Path, agent_path: str, started_at: str) -> "Subagent":
        items = load_items(rollout)
        meta = items[0].payload
        spawn = meta["source"]["subagent"]["thread_spawn"]
        model = next(str(item.payload["model"]) for item in items if item.kind == "turn_context")
        task = f"{ENCRYPTED_NOTE} Codex sub-agent {agent_path} (nickname {spawn['agent_nickname']})."
        messages = [SquashMessage("user", task, started_at)]
        tool_call_timestamps: list[str] = []
        for item in items[1:]:
            if item.kind != "response_item":
                continue
            item_type = item.payload["type"]
            if item_type == "message" and item.payload["role"] == "assistant":
                messages.append(SquashMessage("assistant", text_of(item.payload["content"]), item.timestamp))
            elif item_type == "agent_message":
                header = text_of(item.payload["content"]).split("\n")[0]
                if header == "Message Type: MESSAGE":
                    messages.append(SquashMessage("user", f"{ENCRYPTED_NOTE} Steering message from the root agent.", item.timestamp))
                elif header == "Message Type: NEW_TASK" and len(messages) > 1:
                    messages.append(SquashMessage("user", f"{ENCRYPTED_NOTE} Follow-up task from the root agent.", item.timestamp))
            elif item_type in ("custom_tool_call", "function_call"):
                tool_call_timestamps.append(item.timestamp)
        return cls(agent_path, spawn["agent_nickname"], started_at, model, uuidv7(epoch_ms(meta["timestamp"])), task, messages, tool_call_timestamps, rollout)

    def select_squashed(self, until: str) -> list[SquashMessage]:
        selected: list[SquashMessage] = []
        latest_assistant: SquashMessage | None = None
        for message in self.messages:
            if message.timestamp > until:
                break
            if message.role == "assistant" and message.text.strip():
                latest_assistant = message
                continue
            if latest_assistant:
                selected.append(latest_assistant)
            latest_assistant = None
            selected.append(message)
        if latest_assistant:
            selected.append(latest_assistant)
        return selected

    def result_message(self, until: str, agent_id: str) -> dict[str, object]:
        selected = self.select_squashed(until)
        model_label = f"{PROVIDER}/{self.model}"
        lines = [SQUASH_PREFACE, f'<user_agent model="{escape_attribute(model_label)}" inherited_context="true">']
        for index, message in enumerate(selected, start=1):
            tag = "user_message" if message.role == "user" else "assistant_response"
            lines.append(f"  <{tag} i={index}>")
            lines.extend(f"  {line}" for line in message.text.split("\n"))
            lines.append(f"  </{tag}>")
        lines.append("</user_agent>")
        responses = [message for message in selected if message.role == "assistant"]
        details = {
            "agentId": agent_id,
            "command": "agent",
            "mainContextState": "squashed",
            "inheritedContext": True,
            "model": model_label,
            "modelLabel": self.model,
            "task": self.task,
            "ok": True,
            "durationMs": epoch_ms(until) - epoch_ms(self.started_at),
            "toolUses": sum(1 for timestamp in self.tool_call_timestamps if timestamp <= until),
            "turnCount": sum(1 for message in selected if message.role == "user"),
            "responseText": responses[-1].text if responses else "",
        }
        return {"customType": "pi-user-agents", "content": "\n".join(lines), "display": False, "details": details}


@dataclass(frozen=True)
class PiPrefix:
    lines: list[str]
    source_ordinals: list[int | None]
    codex_id_to_pi_id: dict[str, str]


@dataclass
class PiWriter:
    lines: list[str] = field(default_factory=list)
    source_ordinals: list[int | None] = field(default_factory=list)
    leaf_id: str | None = None
    used_ids: set[str] = field(default_factory=set)
    codex_id_to_pi_id: dict[str, str] = field(default_factory=dict)

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
            codex_id_to_pi_id=dict(prefix.codex_id_to_pi_id),
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
        codex_ids: list[str] | tuple[str, ...] = (),
        source_ordinal: int | None = None,
    ) -> str:
        entry_id = self.new_id()
        self.lines.append(dumps({"type": entry_type, "id": entry_id, "parentId": self.leaf_id, "timestamp": timestamp, **body}))
        self.source_ordinals.append(source_ordinal)
        self.leaf_id = entry_id
        for codex_id in codex_ids:
            self.codex_id_to_pi_id[codex_id] = entry_id
        return entry_id

    def prefix_before(self, source_ordinal: int) -> PiPrefix:
        selected_count = len(self.lines)
        for index, ordinal in enumerate(self.source_ordinals):
            if ordinal is not None and ordinal >= source_ordinal:
                selected_count = index
                break
        residues = self.source_ordinals[selected_count:]
        if any(ordinal is None or ordinal < source_ordinal for ordinal in residues):
            raise ValueError(f"Pi entries are not ordered at Codex fork ordinal {source_ordinal}")
        lines = self.lines[:selected_count]
        identifiers = {str(json.loads(line)["id"]) for line in lines}
        mapping = {
            codex_id: pi_id
            for codex_id, pi_id in self.codex_id_to_pi_id.items()
            if pi_id in identifiers
        }
        return PiPrefix(lines, self.source_ordinals[:selected_count], mapping)

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


@dataclass
class PendingAssistant:
    blocks: list[dict[str, object]] = field(default_factory=list)
    codex_ids: list[str] = field(default_factory=list)
    source_ordinals: list[int] = field(default_factory=list)
    timestamp: str | None = None


def reasoning_block(payload: dict[str, object]) -> dict[str, object]:
    summary_text = "\n\n".join(str(part["text"]) for part in payload["summary"])
    signature = {key: payload[key] for key in ("id", "type", "content", "encrypted_content", "summary") if key in payload}
    return {"type": "thinking", "thinking": summary_text, "thinkingSignature": dumps(signature)}


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
    role: Role
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
        model, thinking_level = writer.current_settings()
        pending = PendingAssistant()
        call_names: dict[str, str] = {}
        call_pi_ids: dict[str, str] = {}
        dropped_call_ids: set[str] = set()
        dropped: dict[str, int] = {}
        delivered_agent_ids: dict[str, str] = {}

        def drop(reason: str) -> None:
            dropped[reason] = dropped.get(reason, 0) + 1

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
            writer.append(
                "message",
                pending.timestamp,
                {"message": message},
                pending.codex_ids,
                max(pending.source_ordinals),
            )
            pending.blocks, pending.codex_ids, pending.source_ordinals, pending.timestamp = [], [], [], None

        def add_pending(block: dict[str, object], codex_id: str, timestamp: str, source_ordinal: int) -> None:
            pending.timestamp = pending.timestamp or timestamp
            pending.blocks.append(block)
            pending.codex_ids.append(codex_id)
            pending.source_ordinals.append(source_ordinal)

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
            add_pending(
                {"type": "toolCall", "id": pi_call_id, "name": name, "arguments": arguments},
                str(payload["id"]),
                timestamp,
                source_ordinal,
            )

        def add_tool_result(
            payload: dict[str, object],
            text: str,
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
                "content": [{"type": "text", "text": text}],
                "details": {},
                "isError": is_error,
                "timestamp": epoch_ms(timestamp),
            }
            writer.append("message", timestamp, {"message": message}, [str(payload["id"])], source_ordinal)

        def add_user_message(text: str, codex_id: str, timestamp: str, source_ordinal: int) -> None:
            flush("stop")
            message = {"role": "user", "content": [{"type": "text", "text": text}], "timestamp": epoch_ms(timestamp)}
            writer.append("message", timestamp, {"message": message}, [codex_id], source_ordinal)

        for item in items[1:]:
            timestamp, payload = item.timestamp, item.payload
            if item.ordinal in self.fork_cutoffs:
                flush("stop")

            if item.kind == "turn_context":
                next_model = str(payload["model"])
                next_thinking_level = str(payload["effort"])
                if next_model != model or next_thinking_level != thinking_level:
                    flush("stop")
                if next_model != model:
                    model = next_model
                    writer.append("model_change", timestamp, {"provider": PROVIDER, "modelId": model}, source_ordinal=item.ordinal)
                if next_thinking_level != thinking_level:
                    thinking_level = next_thinking_level
                    writer.append(
                        "thinking_level_change",
                        timestamp,
                        {"thinkingLevel": thinking_level},
                        source_ordinal=item.ordinal,
                    )
                continue

            if item.kind == "compacted":
                flush("stop")
                guardian = payload["guardian_history"]
                first_tail_index = next(index for index, entry in enumerate(guardian) if not (entry["type"] == "message" and entry["role"] == "user"))
                summary = "Codex compacted the context here. It kept no summary. It kept the following user messages verbatim, together with the most recent items:\n\n" + "\n\n---\n\n".join(
                    f"<user_message>\n{text_of(entry['content'])}\n</user_message>" for entry in guardian[:first_tail_index]
                )
                first_kept_codex_id = next(entry["id"] for entry in guardian[first_tail_index:] if entry["id"] in writer.codex_id_to_pi_id)
                writer.append(
                    "compaction",
                    timestamp,
                    {"summary": summary, "firstKeptEntryId": writer.codex_id_to_pi_id[first_kept_codex_id], "tokensBefore": payload["latest_token_usage_record"]["usage"]["total_tokens"]},
                    source_ordinal=item.ordinal,
                )
                continue

            if item.kind != "response_item":
                drop(item.kind)
                continue

            item_type = payload["type"]

            if item_type == "reasoning":
                add_pending(reasoning_block(payload), str(payload["id"]), timestamp, item.ordinal)
            elif item_type == "message" and payload["role"] == "assistant":
                add_pending({"type": "text", "text": text_of(payload["content"])}, str(payload["id"]), timestamp, item.ordinal)
            elif item_type == "custom_tool_call":
                add_tool_call(
                    payload,
                    "bash",
                    {"command": bash_command_for_exec(str(payload["input"]))},
                    timestamp,
                    item.ordinal,
                )
            elif item_type == "function_call":
                arguments = json.loads(str(payload["arguments"]))
                name = str(payload["name"])
                if payload.get("namespace") in DROPPED_NAMESPACES:
                    dropped_call_ids.add(str(payload["call_id"]))
                    drop(f"function_call:{payload['namespace']}.{name}")
                elif name == "wait":
                    add_tool_call(
                        payload,
                        "bash",
                        {"command": bash_command_for_wait(arguments)},
                        timestamp,
                        item.ordinal,
                    )
                elif name == "request_user_input_async":
                    dropped_call_ids.add(str(payload["call_id"]))
                    add_pending(
                        {"type": "text", "text": question_text(arguments)},
                        str(payload["id"]),
                        timestamp,
                        item.ordinal,
                    )
                else:
                    raise ValueError(f"Unhandled function_call {name} at {timestamp}")
            elif item_type in ("custom_tool_call_output", "function_call_output"):
                if payload["call_id"] in dropped_call_ids:
                    drop("dropped_call_output")
                    continue
                text, is_error = bash_result(text_of(payload["output"]))
                add_tool_result(payload, text, is_error, timestamp, item.ordinal)
            elif item_type == "message" and payload["role"] == "user":
                text = text_of(payload["content"])
                if text.startswith(INJECTED_USER_PREFIXES):
                    drop("injected_user_message")
                    continue
                add_user_message(text, str(payload["id"]), timestamp, item.ordinal)
            elif item_type == "message" and payload["role"] == "developer":
                drop("developer_message")
            elif item_type == "agent_message" and self.role == "subagent":
                add_user_message(
                    text_of(payload["content"]) + ENCRYPTED_NOTE,
                    str(payload["id"]),
                    timestamp,
                    item.ordinal,
                )
            elif item_type == "agent_message":
                flush("stop")
                subagent = self.subagents[str(payload["author"])]
                agent_id = delivered_agent_ids.setdefault(subagent.agent_path, f"codex-{len(delivered_agent_ids) + 1}")
                writer.append(
                    "custom_message",
                    timestamp,
                    subagent.result_message(timestamp, agent_id),
                    [str(payload["id"])],
                    item.ordinal,
                )
                if text_of(payload["content"]).startswith("Message Type: FINAL_ANSWER"):
                    writer.append(
                        "custom",
                        timestamp,
                        {"customType": "pi-user-agents-detached", "data": {"sessionId": subagent.session_id}},
                        source_ordinal=item.ordinal,
                    )
            else:
                raise ValueError(f"Unhandled response_item type at {timestamp}: {item_type}")

        flush("stop")

        header: dict[str, object] = {"type": "session", "version": 3, "id": self.session_id, "timestamp": started_at, "cwd": cwd}
        if self.parent_session:
            header["parentSession"] = self.parent_session

        directory = session_directory(self.sessions_root, cwd)
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / session_filename(started_at, self.session_id)
        with target.open("w") as out:
            out.write(dumps(header) + "\n")
            out.write("\n".join(writer.lines) + "\n")
        print(f"wrote {target}", file=sys.stderr)
        print(f"  entries: {len(writer.lines)}", file=sys.stderr)
        print(f"  dropped: {dumps(dropped)}", file=sys.stderr)
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
    ordinals = [item.ordinal for item in merged]
    if ordinals != sorted(set(ordinals)):
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
    subagents: dict[str, Subagent] = {}
    for item in items:
        activity = item.payload.get("item", {}) if item.kind == "event_msg" else {}
        if activity.get("type") != "SubAgentActivity" or activity.get("kind") != "started":
            continue
        rollout = next(codex_sessions_root.rglob(f"*{activity['agent_thread_id']}*.jsonl"))
        subagents[str(activity["agent_path"])] = Subagent.from_rollout(rollout, str(activity["agent_path"]), item.timestamp)
    return subagents


def fork_prefix(node: CodexSessionNode, parent: ConvertedSession) -> PiPrefix | None:
    if node.fork_ordinal is None:
        if node.history_base is not None:
            raise ValueError(f"Codex fork {node.session_id} has history_base without a fork ordinal")
        return None
    if node.history_base is None:
        raise ValueError(f"Codex fork {node.session_id} has a fork ordinal without history_base")
    expected = {
        "thread_id": node.fork_parent_id,
        "end_ordinal_exclusive": node.fork_ordinal,
    }
    actual = {key: node.history_base.get(key) for key in expected}
    if actual != expected:
        raise ValueError(f"Codex fork {node.session_id} has inconsistent history_base: {actual!r} != {expected!r}")
    return parent.prefix_before(node.fork_ordinal)


def convert_fork_tree(
    selected_session_id: str,
    codex_sessions_root: Path,
    pi_sessions_root: Path,
    selected_name: str,
) -> dict[str, Path]:
    """Convert the complete persisted fork tree containing one Codex session.

    The selected session can sit anywhere in the tree. Native Codex sub-agents remain
    pi-user-agents sessions and are not mistaken for user-created forks.
    """
    graph = CodexSessionGraph.load(codex_sessions_root)
    tree_root_id = graph.root_of(selected_session_id)
    converted_sessions: dict[str, ConvertedSession] = {}

    def convert_node(session_id: str) -> None:
        node = graph.nodes[session_id]
        parent = converted_sessions.get(node.fork_parent_id) if node.fork_parent_id else None
        prefix = fork_prefix(node, parent) if parent else None
        parent_session = str(parent.path) if parent else None
        source_items = load_node_items(node)
        items = list(source_items)
        subagents = find_subagents(items, codex_sessions_root)
        name = graph.names.get(session_id, f"{selected_name} — Codex fork {session_id}")
        if session_id == selected_session_id:
            name = selected_name
        direct_cutoffs = {
            graph.nodes[child_id].fork_ordinal
            for child_id in graph.fork_children[session_id]
            if graph.nodes[child_id].fork_ordinal is not None
        }
        session_id_for_pi = uuidv7(epoch_ms(str(items[0].payload["timestamp"])))
        converted = Conversion(
            node.rollout,
            pi_sessions_root,
            name,
            "root",
            session_id_for_pi,
            subagents,
            parent_session,
            prefix,
            direct_cutoffs,
            source_items,
        ).run()
        converted_sessions[session_id] = converted

        for subagent in subagents.values():
            child_name = f"{name} — sub-agent {subagent.agent_path} ({subagent.nickname})"
            Conversion(
                subagent.rollout,
                pi_sessions_root,
                child_name,
                "subagent",
                subagent.session_id,
                parent_session=str(converted.path),
            ).run()

        for child_id in graph.fork_children[session_id]:
            convert_node(child_id)

    convert_node(tree_root_id)
    return {session_id: converted.path for session_id, converted in converted_sessions.items()}


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
