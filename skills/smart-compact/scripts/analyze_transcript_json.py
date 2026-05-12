#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = ["pyyaml"]
# ///

import argparse
import collections
import dataclasses
import json
import pathlib
import re
import sys

import yaml


MURMUR_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"\b(?:good|great|nice|done|perfect|cool)\b[.!]?$",
        r"\bnow let me\b",
        r"\blet me (?:check|read|run|verify|inspect|look at|try|also)\b",
        r"\b(?:build|lint|tests?) (?:passes?|passed|clean)\b",
        r"\bimplementation complete and verified\b",
        r"\bfile (?:created|updated|written) successfully\b",
        r"\bhas been updated successfully\b",
        r"\bfile state is current in your context\b",
        r"\bbash completed with no output\b",
        r"\bno response requested\b",
    ]
]
VALIDATION_KEYWORDS = {
    "build": ("npm run build", "vite build", "cargo build", "go build", "make build"),
    "lint": ("npm run lint", "ruff", "eslint", "biome", "cargo clippy"),
    "test": ("pytest", "npm test", "vitest", "jest", "cargo test", "go test"),
}
SCRATCHPAD_PATTERNS = [
    re.compile(pattern)
    for pattern in [
        r"^/tmp/",
        r"/tmp/",
        r"\.tmp$",
        r"\.bak$",
        r"/scratch/",
    ]
]


def _flatten_tool_output(content: str | list[dict[str, str]]) -> str:
    """Convert structured tool-output content to a single string.

    >>> _flatten_tool_output('hello')
    'hello'
    >>> result = _flatten_tool_output([{'type': 'text', 'text': 'a'}, {'type': 'text', 'text': 'b'}])
    >>> result.count('\\n')
    1
    """
    if isinstance(content, str):
        return content
    return "\n".join(item.get("text", "") for item in content)


def _block_text(block: str | dict[str, object]) -> str:
    """Render any content block as readable text for pattern-matching."""
    if isinstance(block, str):
        return block
    block_type = block.get("type")
    if block_type == "tool-output":
        return _flatten_tool_output(block.get("content", ""))
    if block_type == "tool-input":
        command = block.get("command")
        if isinstance(command, str):
            return command
        path = block.get("path") or block.get("file_path")
        if isinstance(path, str):
            return path
        return ""
    return ""


def normalize_whitespace(text: str) -> str:
    """Collapse whitespace for cheap content bucketing.

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
    """Return a readable trailing path.

    >>> shorten_path('/a/b/c/d.txt')
    'b/c/d.txt'
    >>> shorten_path('client/src/App.jsx')
    'client/src/App.jsx'
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
        parts: list[str] = []
        for block in self.content:
            if isinstance(block, str):
                parts.append(block)
            else:
                text = _block_text(block)
                if text:
                    parts.append(text)
        return "\n".join(parts)

    @property
    def tool_inputs(self) -> list[dict[str, object]]:
        return [
            block for block in self.content
            if isinstance(block, dict) and block.get("type") == "tool-input"
        ]

    @property
    def tool_outputs(self) -> list[dict[str, object]]:
        return [
            block for block in self.content
            if isinstance(block, dict) and block.get("type") == "tool-output"
        ]


@dataclasses.dataclass(slots=True)
class ToolTag:
    name: str
    identifier: str | None


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


@dataclasses.dataclass(slots=True)
class IndexedSnippet:
    index: int
    text: str


def load_messages(path: pathlib.Path) -> list[Message]:
    raw = json.loads(path.read_text())
    if not isinstance(raw, list):
        raise ValueError("expected top-level JSON array")
    messages: list[Message] = []
    for item_index, item in enumerate(raw):
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = item.get("content")
        message_type = item.get("type")
        original_index = item.get("original_index")
        if (
            isinstance(role, str)
            and isinstance(content, list)
            and isinstance(message_type, str)
            and isinstance(original_index, int)
        ):
            messages.append(
                Message(
                    index=original_index,
                    role=role,
                    message_type=message_type,
                    content=content,
                )
            )
    return messages


def detect_file_touches(messages: list[Message]) -> list[FileTouch]:
    touches: list[FileTouch] = []
    for message in messages:
        for block in message.tool_inputs:
            tool_name = block.get("name")
            if not isinstance(tool_name, str):
                continue
            path = block.get("path") or block.get("file_path")
            if isinstance(path, str):
                touches.append(FileTouch(tool=tool_name, path=path, index=message.index))
    return touches


def looks_like_murmur(message: Message) -> bool:
    text = normalize_whitespace(message.text_content)
    if len(text) > 220:
        return False
    if not text:
        return False
    return any(pattern.search(text) for pattern in MURMUR_PATTERNS)


def looks_like_success_receipt(message: Message) -> bool:
    if not message.tool_outputs:
        return False
    receipts = (
        "successfully",
        "completed with no output",
        "no content change, skipping",
        "is up to date, skipping",
        "tooling installation complete",
    )
    for block in message.tool_outputs:
        text = _block_text(block).lower()
        if any(fragment in text for fragment in receipts):
            return True
    return False


def is_local_command_caveat(message: Message) -> bool:
    for block in message.content:
        if isinstance(block, str) and "<local-command-caveat>" in block:
            return True
    return False


def is_scratchpad_path(path: str) -> bool:
    return any(pattern.search(path) for pattern in SCRATCHPAD_PATTERNS)


def extract_validation_family(message: Message) -> str | None:
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
    if block.get("is_error"):
        return True
    text = _block_text(block).lower()
    return (
        "exit code " in text
        or "traceback" in text
        or "module not found" in text
        or "bad request" in text
        or "error:" in text
    )


def collect_tool_calls(messages: list[Message]) -> list[ToolCall]:
    inputs_by_id: dict[str, tuple[str, int]] = {}
    calls: list[ToolCall] = []
    for message in messages:
        for block in message.tool_inputs:
            tool_name = block.get("name")
            identifier = block.get("id")
            if not isinstance(tool_name, str):
                continue
            if isinstance(identifier, str):
                inputs_by_id[identifier] = (tool_name, message.index)
            else:
                calls.append(
                    ToolCall(
                        tool=tool_name,
                        identifier=None,
                        input_index=message.index,
                        output_index=None,
                        failed=False,
                    )
                )
        for block in message.tool_outputs:
            tool_name = block.get("name")
            identifier = block.get("id")
            if not isinstance(tool_name, str) or not isinstance(identifier, str):
                continue
            if identifier not in inputs_by_id:
                continue
            _, input_index = inputs_by_id.pop(identifier)
            calls.append(
                ToolCall(
                    tool=tool_name,
                    identifier=identifier,
                    input_index=input_index,
                    output_index=message.index,
                    failed=extract_error_flag(block),
                )
            )

    for identifier, (tool_name, input_index) in inputs_by_id.items():
        calls.append(
            ToolCall(
                tool=tool_name,
                identifier=identifier,
                input_index=input_index,
                output_index=None,
                failed=False,
            )
        )
    calls.sort(key=lambda call: call.input_index)
    return calls


def collect_indexed_snippets(messages: list[Message], predicate) -> list[IndexedSnippet]:
    return [
        IndexedSnippet(index=message.index, text=excerpt(message.all_block_text))
        for message in messages
        if predicate(message)
    ]


def build_noise_block(snippets: list[IndexedSnippet], top: int) -> dict[str, object]:
    return {
        "count": len(snippets),
        "indices": [snippet.index for snippet in snippets],
        "samples": [dataclasses.asdict(snippet) for snippet in snippets[:top]],
    }


def build_scratchpad_block(touches_by_path: dict[str, dict[str, list[int]]], top: int) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for path in sorted(touches_by_path):
        if not is_scratchpad_path(path):
            continue
        rows.append(
            {
                "path": path,
                "ops": {tool.lower(): indices for tool, indices in sorted(touches_by_path[path].items())},
            }
        )
    return rows[:top]


def build_file_rows(paths: list[str], touches_by_path: dict[str, dict[str, list[int]]], top: int) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for path in paths[:top]:
        tool_map = touches_by_path[path]
        rows.append(
            {
                "path": path,
                "short": shorten_path(path),
                "touches": sum(len(indices) for indices in tool_map.values()),
                "ops": {tool.lower(): indices for tool, indices in sorted(tool_map.items())},
            }
        )
    return rows


def build_report(messages: list[Message], top: int) -> dict[str, object]:
    role_counts = collections.Counter(message.role for message in messages)
    tool_calls = collect_tool_calls(messages)
    tool_counts = collections.Counter(call.tool for call in tool_calls)
    touches = detect_file_touches(messages)

    touches_by_path: dict[str, dict[str, list[int]]] = collections.defaultdict(lambda: collections.defaultdict(list))
    for touch in touches:
        touches_by_path[touch.path][touch.tool].append(touch.index)

    murmur_candidates = collect_indexed_snippets(messages, looks_like_murmur)
    success_receipts = collect_indexed_snippets(messages, looks_like_success_receipt)
    local_caveats = collect_indexed_snippets(messages, is_local_command_caveat)
    failed_calls = [call for call in tool_calls if call.failed]

    repeated_read_paths = sorted(
        [path for path, ops in touches_by_path.items() if len(ops.get("Read", [])) > 1],
        key=lambda path: (-len(touches_by_path[path].get("Read", [])), path),
    )
    repeated_mutation_paths = sorted(
        [
            path
            for path, ops in touches_by_path.items()
            if sum(len(ops.get(tool, [])) for tool in ("Write", "Edit", "Delete")) > 1
        ],
        key=lambda path: (
            -sum(len(touches_by_path[path].get(tool, [])) for tool in ("Write", "Edit", "Delete")),
            path,
        ),
    )
    hot_paths = sorted(
        touches_by_path,
        key=lambda path: (-sum(len(indices) for indices in touches_by_path[path].values()), path),
    )

    validation_rows: dict[str, dict[str, object]] = {}
    validation_runs: dict[str, list[ToolCall]] = collections.defaultdict(list)
    for call in tool_calls:
        input_message = next((m for m in messages if m.index == call.input_index), None)
        if input_message is None:
            continue
        family = extract_validation_family(input_message)
        if family is not None:
            validation_runs[family].append(call)
    for family, runs in sorted(validation_runs.items()):
        validation_rows[family] = {
            "runs": len(runs),
            "input_indices": [call.input_index for call in runs],
            "failed_input_indices": [call.input_index for call in runs if call.failed],
            "status_marks": [f"{call.input_index}{'!' if call.failed else ''}" for call in runs],
        }

    return {
        "overview": {
            "messages": len(messages),
            "indexing": "original_index field from JSON",
            "roles": dict(sorted(role_counts.items())),
            "tool_calls": len(tool_calls),
            "unique_tools": len(tool_counts),
        },
        "noise": {
            "murmur_candidates": build_noise_block(murmur_candidates, top),
            "success_receipts": build_noise_block(success_receipts, top),
            "local_command_caveats": build_noise_block(local_caveats, top),
            "scratchpad_paths": build_scratchpad_block(touches_by_path, top),
        },
        "failed_tool_calls": {
            "count": len(failed_calls),
            "items": [
                {
                    "tool": call.tool,
                    "input_index": call.input_index,
                    "output_index": call.output_index,
                }
                for call in failed_calls
            ],
        },
        "files": {
            "unique_affected_files": len(touches_by_path),
            "file_touch_events": len(touches),
            "repeated_read_files": build_file_rows(repeated_read_paths, touches_by_path, top),
            "repeated_mutation_files": build_file_rows(repeated_mutation_paths, touches_by_path, top),
            "hot_files": build_file_rows(hot_paths, touches_by_path, top),
        },
        "validation": validation_rows,
        "tool_repetition": dict(sorted((tool, count) for tool, count in tool_counts.items() if count > 1)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Cheap deterministic diagnostics for transcript-like JSON.")
    parser.add_argument("json_path", type=pathlib.Path)
    parser.add_argument("--top", type=int, default=8, help="How many detailed entries to include per section.")
    args = parser.parse_args()

    messages = load_messages(args.json_path)
    if not messages:
        raise SystemExit("no messages found")

    report = build_report(messages, args.top)
    yaml.safe_dump(report, sys.stdout, sort_keys=False, allow_unicode=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
