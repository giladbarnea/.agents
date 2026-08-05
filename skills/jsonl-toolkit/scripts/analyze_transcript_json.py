#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = ["pyyaml"]
# ///
"""Report deterministic structure and activity in an exported AI transcript."""

from __future__ import annotations

import argparse
import collections
import dataclasses
import json
import pathlib
import sys

import yaml

import transcript_common

VALIDATION_KEYWORDS = {
    "build": ("npm run build", "vite build", "cargo build", "go build", "make build"),
    "lint": ("npm run lint", "ruff", "eslint", "biome", "cargo clippy"),
    "test": ("pytest", "npm test", "vitest", "jest", "cargo test", "go test"),
}


def flatten_tool_output(content: str | list[dict[str, str]]) -> str:
    """Convert structured tool-output content to one string.

    >>> flatten_tool_output([{'type': 'text', 'text': 'a'}, {'type': 'text', 'text': 'b'}])
    'a\nb'
    """
    if isinstance(content, str):
        return content
    return "\n".join(item.get("text", "") for item in content)


def block_text(block: str | dict[str, object]) -> str:
    """Return readable text from a transcript content block."""
    if isinstance(block, str):
        return block
    block_type = block.get("type")
    if block_type == "tool-output":
        content = block.get("content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list) and all(isinstance(item, dict) for item in content):
            return flatten_tool_output(content)
        return ""
    if block_type != "tool-input":
        return ""
    command = block.get("command")
    if isinstance(command, str):
        return command
    path = block.get("path") or block.get("file_path")
    return path if isinstance(path, str) else ""


def normalize_whitespace(text: str) -> str:
    """Collapse whitespace for stable content bucketing.

    >>> normalize_whitespace(' a   b ')
    'a b'
    """
    return " ".join(text.split())


def excerpt(text: str, limit: int = 88) -> str:
    """Return a short one-line excerpt.

    >>> excerpt('a b c d', 5)
    'a b …'
    """
    compact = normalize_whitespace(text)
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1] + "…"


def shorten_path(path: str) -> str:
    """Return at most three trailing path components.

    >>> shorten_path('/a/b/c/d.txt')
    'b/c/d.txt'
    """
    parts = pathlib.PurePosixPath(path).parts
    if len(parts) <= 3:
        return path
    return str(pathlib.PurePosixPath(*parts[-3:]))


@dataclasses.dataclass(slots=True)
class Message:
    index: int
    role: str
    message_type: str
    content: list[str | dict[str, object]]

    @property
    def text_content(self) -> str:
        return "\n".join(block for block in self.content if isinstance(block, str))

    @property
    def all_block_text(self) -> str:
        return "\n".join(
            text
            for block in self.content
            for text in [block_text(block)]
            if text
        )

    @property
    def tool_inputs(self) -> list[dict[str, object]]:
        return [
            block
            for block in self.content
            if isinstance(block, dict) and block.get("type") == "tool-input"
        ]

    @property
    def tool_outputs(self) -> list[dict[str, object]]:
        return [
            block
            for block in self.content
            if isinstance(block, dict) and block.get("type") == "tool-output"
        ]


@dataclasses.dataclass(slots=True)
class FileTouch:
    tool: str
    path: str
    index: int


@dataclasses.dataclass(slots=True)
class ToolCall:
    tool: str
    identifier: str | None
    input_index: int
    output_index: int | None
    failed: bool


def load_messages(path: pathlib.Path) -> list[Message]:
    """Load normalized messages from an exported transcript JSON array."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("expected top-level JSON array")

    messages: list[Message] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = item.get("content")
        message_type = item.get("type")
        original_index = item.get("original_index")
        if not (
            isinstance(role, str)
            and isinstance(content, list)
            and isinstance(message_type, str)
            and isinstance(original_index, int)
        ):
            continue
        messages.append(Message(original_index, role, message_type, content))
    return messages


def detect_file_touches(messages: list[Message]) -> list[FileTouch]:
    """Return every structured file operation, expanding multi-file reads.

    >>> message = Message(1, 'assistant', 'assistant-response', [{'type': 'tool-input', 'name': 'read_many_files', 'paths': ['a', 'b']}])
    >>> [touch.path for touch in detect_file_touches([message])]
    ['a', 'b']
    """
    return [
        FileTouch(tool=operation, path=path, index=message.index)
        for message in messages
        for block in message.tool_inputs
        for operation, path, _ in transcript_common.file_references(block)
    ]


def extract_validation_family(message: Message) -> str | None:
    """Return the validation command family used by an assistant message."""
    if message.role != "assistant":
        return None
    for block in message.tool_inputs:
        if block.get("name") != "Bash":
            continue
        command = block.get("command")
        if not isinstance(command, str):
            continue
        lowered = command.lower()
        for family, needles in VALIDATION_KEYWORDS.items():
            if any(needle in lowered for needle in needles):
                return family
    return None


def extract_error_flag(block: dict[str, object]) -> bool:
    """Return whether a tool-output block reports failure."""
    if block.get("is_error"):
        return True
    text = block_text(block).lower()
    return any(
        fragment in text
        for fragment in (
            "exit code ",
            "traceback",
            "module not found",
            "bad request",
            "error:",
        )
    )


def collect_tool_calls(messages: list[Message]) -> list[ToolCall]:
    """Pair tool inputs and outputs by their exact transcript ID."""
    inputs_by_identifier: dict[str, tuple[str, int]] = {}
    calls: list[ToolCall] = []
    for message in messages:
        for block in message.tool_inputs:
            tool_name = block.get("name")
            identifier = block.get("id")
            if not isinstance(tool_name, str):
                continue
            if isinstance(identifier, str):
                inputs_by_identifier[identifier] = (tool_name, message.index)
                continue
            calls.append(ToolCall(tool_name, None, message.index, None, False))

        for block in message.tool_outputs:
            tool_name = block.get("name")
            identifier = block.get("id")
            if not isinstance(tool_name, str) or not isinstance(identifier, str):
                continue
            input_event = inputs_by_identifier.pop(identifier, None)
            if input_event is None:
                continue
            _, input_index = input_event
            calls.append(
                ToolCall(
                    tool_name,
                    identifier,
                    input_index,
                    message.index,
                    extract_error_flag(block),
                )
            )

    calls.extend(
        ToolCall(tool_name, identifier, input_index, None, False)
        for identifier, (tool_name, input_index) in inputs_by_identifier.items()
    )
    calls.sort(key=lambda call: call.input_index)
    return calls


def build_file_rows(
    paths: list[str],
    touches_by_path: dict[str, dict[str, list[int]]],
    top: int,
) -> list[dict[str, object]]:
    """Render detailed rows for ordered file paths."""
    return [
        {
            "path": path,
            "short": shorten_path(path),
            "touches": sum(len(indices) for indices in touches_by_path[path].values()),
            "ops": {
                tool.lower(): indices
                for tool, indices in sorted(touches_by_path[path].items())
            },
        }
        for path in paths[:top]
    ]


def build_report(messages: list[Message], top: int) -> dict[str, object]:
    """Build a compaction-agnostic transcript activity report."""
    role_counts = collections.Counter(message.role for message in messages)
    tool_calls = collect_tool_calls(messages)
    tool_counts = collections.Counter(call.tool for call in tool_calls)
    touches = detect_file_touches(messages)

    touches_by_path: dict[str, dict[str, list[int]]] = collections.defaultdict(
        lambda: collections.defaultdict(list)
    )
    for touch in touches:
        touches_by_path[touch.path][touch.tool].append(touch.index)

    repeated_read_paths = sorted(
        [path for path, operations in touches_by_path.items() if len(operations.get("Read", [])) > 1],
        key=lambda path: (-len(touches_by_path[path].get("Read", [])), path),
    )
    repeated_mutation_paths = sorted(
        [
            path
            for path, operations in touches_by_path.items()
            if sum(len(operations.get(tool, [])) for tool in ("Write", "Edit", "Delete")) > 1
        ],
        key=lambda path: (
            -sum(len(touches_by_path[path].get(tool, [])) for tool in ("Write", "Edit", "Delete")),
            path,
        ),
    )
    hot_paths = sorted(
        touches_by_path,
        key=lambda path: (
            -sum(len(indices) for indices in touches_by_path[path].values()),
            path,
        ),
    )

    validation_runs: dict[str, list[ToolCall]] = collections.defaultdict(list)
    messages_by_index = {message.index: message for message in messages}
    for call in tool_calls:
        family = extract_validation_family(messages_by_index[call.input_index])
        if family is not None:
            validation_runs[family].append(call)
    validation = {
        family: {
            "runs": len(runs),
            "input_indices": [call.input_index for call in runs],
            "failed_input_indices": [call.input_index for call in runs if call.failed],
            "status_marks": [f"{call.input_index}{'!' if call.failed else ''}" for call in runs],
        }
        for family, runs in sorted(validation_runs.items())
    }

    tool_outputs_by_tool: dict[str, list[int]] = collections.defaultdict(list)
    bash_calls_by_command: dict[str, list[int]] = collections.defaultdict(list)
    for message in messages:
        for block in message.tool_outputs:
            name = block.get("name")
            if isinstance(name, str):
                tool_outputs_by_tool[name].append(message.index)
        for block in message.tool_inputs:
            if block.get("name") != "Bash":
                continue
            command = block.get("command")
            if isinstance(command, str):
                bash_calls_by_command[command].append(message.index)

    return {
        "overview": {
            "messages": len(messages),
            "indexing": "original_index field from JSON",
            "roles": dict(sorted(role_counts.items())),
            "tool_calls": len(tool_calls),
            "unique_tools": len(tool_counts),
        },
        "failed_tool_calls": {
            "count": sum(call.failed for call in tool_calls),
            "items": [
                {
                    "tool": call.tool,
                    "input_index": call.input_index,
                    "output_index": call.output_index,
                }
                for call in tool_calls
                if call.failed
            ],
        },
        "tool_output_indices": {
            name: {"count": len(indices), "indices": sorted(indices)}
            for name, indices in sorted(tool_outputs_by_tool.items())
        },
        "duplicate_commands": {
            excerpt(command, 120): {"count": len(indices), "indices": sorted(indices)}
            for command, indices in sorted(bash_calls_by_command.items())
            if len(indices) > 1
        },
        "files": {
            "unique_files": len(touches_by_path),
            "file_touch_events": len(touches),
            "repeated_read_files": build_file_rows(repeated_read_paths, touches_by_path, top),
            "repeated_mutation_files": build_file_rows(repeated_mutation_paths, touches_by_path, top),
            "hot_files": build_file_rows(hot_paths, touches_by_path, top),
        },
        "validation": validation,
        "tool_repetition": dict(
            sorted((tool, count) for tool, count in tool_counts.items() if count > 1)
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("json_path", type=pathlib.Path)
    parser.add_argument("--top", type=int, default=8)
    arguments = parser.parse_args()

    messages = load_messages(arguments.json_path)
    if not messages:
        raise SystemExit("no messages found")
    yaml.safe_dump(
        build_report(messages, arguments.top),
        sys.stdout,
        sort_keys=False,
        allow_unicode=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
