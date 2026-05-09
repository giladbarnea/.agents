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


TOOL_INPUT_PATTERN = re.compile(r'<tool-input name="([^"]+)"(?: id="([^"]+)")?[^>]*>')
TOOL_OUTPUT_PATTERN = re.compile(r'<tool-output name="([^"]+)"(?: id="([^"]+)")?[^>]*>')
FILE_PATH_PATTERN = re.compile(r'file_path="([^"]+)"')
FILE_REF_PATTERNS = [
    re.compile(r'\b(?:Read|Write|Edit|Delete)\b[^\n]*\b(?:path|file_path)="([^"]+)"'),
    re.compile(r'\b(?:Read|Write|Edit|Delete)\b[^\n]*\b(?:path|file_path)=([^\s>]+)'),
]
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
LOCAL_COMMAND_CAVEAT = "<local-command-caveat>"


@dataclasses.dataclass(slots=True)
class Message:
    index: int
    role: str
    content: str


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


def normalize_whitespace(text: str) -> str:
    """Collapse whitespace for cheap content bucketing.

    >>> normalize_whitespace(' a\n  b ')
    'a b'
    """
    return " ".join(text.split())


def excerpt(text: str, limit: int = 88) -> str:
    """Return a short one-line excerpt.

    >>> excerpt('a\n b\n c', 5)
    'a b…'
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


def load_messages(path: pathlib.Path) -> list[Message]:
    raw = json.loads(path.read_text())
    if not isinstance(raw, list):
        raise ValueError("expected top-level JSON array")
    messages: list[Message] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = item.get("content")
        if isinstance(role, str) and isinstance(content, str):
            messages.append(Message(index=index, role=role, content=content))
    return messages


def parse_tool_input(content: str) -> ToolTag | None:
    match = TOOL_INPUT_PATTERN.search(content)
    if not match:
        return None
    return ToolTag(name=match.group(1), identifier=match.group(2))


def parse_tool_output(content: str) -> ToolTag | None:
    match = TOOL_OUTPUT_PATTERN.search(content)
    if not match:
        return None
    return ToolTag(name=match.group(1), identifier=match.group(2))


def detect_file_touches(messages: list[Message]) -> list[FileTouch]:
    touches: list[FileTouch] = []
    for message in messages:
        input_tag = parse_tool_input(message.content)
        if input_tag and input_tag.name in {"Read", "Write", "Edit", "Delete"}:
            match = FILE_PATH_PATTERN.search(message.content)
            if match:
                touches.append(FileTouch(tool=input_tag.name, path=match.group(1), index=message.index))
                continue
        if input_tag and input_tag.name == "Bash":
            for pattern in FILE_REF_PATTERNS:
                for match in pattern.finditer(message.content):
                    touches.append(
                        FileTouch(
                            tool="Bash",
                            path=match.group(1).strip('"\''),
                            index=message.index,
                        )
                    )
    return touches


def looks_like_murmur(message: Message) -> bool:
    text = normalize_whitespace(message.content)
    if len(text) > 220:
        return False
    return any(pattern.search(text) for pattern in MURMUR_PATTERNS)


def looks_like_success_receipt(message: Message) -> bool:
    text = normalize_whitespace(message.content).lower()
    if "<tool-output" not in message.content:
        return False
    receipts = (
        "successfully",
        "completed with no output",
        "no content change, skipping",
        "is up to date, skipping",
        "tooling installation complete",
    )
    return any(fragment in text for fragment in receipts)


def is_local_command_caveat(message: Message) -> bool:
    return LOCAL_COMMAND_CAVEAT in message.content


def is_scratchpad_path(path: str) -> bool:
    return any(pattern.search(path) for pattern in SCRATCHPAD_PATTERNS)


def extract_validation_family(message: Message) -> str | None:
    if message.role != "assistant":
        return None
    input_tag = parse_tool_input(message.content)
    if input_tag is None or input_tag.name != "Bash":
        return None
    lowered = message.content.lower()
    for family, needles in VALIDATION_KEYWORDS.items():
        if any(needle in lowered for needle in needles):
            return family
    return None


def extract_error_flag(content: str) -> bool:
    lowered = content.lower()
    return (
        'is_error="true"' in lowered
        or "exit code " in lowered
        or "traceback" in lowered
        or "module not found" in lowered
        or "bad request" in lowered
        or "error:" in lowered
    )


def collect_tool_calls(messages: list[Message]) -> list[ToolCall]:
    inputs_by_id: dict[str, tuple[str, int]] = {}
    calls: list[ToolCall] = []
    for message in messages:
        input_tag = parse_tool_input(message.content)
        if input_tag is not None:
            if input_tag.identifier:
                inputs_by_id[input_tag.identifier] = (input_tag.name, message.index)
            else:
                calls.append(
                    ToolCall(
                        tool=input_tag.name,
                        identifier=None,
                        input_index=message.index,
                        output_index=None,
                        failed=False,
                    )
                )
            continue

        output_tag = parse_tool_output(message.content)
        if output_tag is None or not output_tag.identifier:
            continue
        if output_tag.identifier not in inputs_by_id:
            continue
        tool_name, input_index = inputs_by_id.pop(output_tag.identifier)
        calls.append(
            ToolCall(
                tool=tool_name,
                identifier=output_tag.identifier,
                input_index=input_index,
                output_index=message.index,
                failed=extract_error_flag(message.content),
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
        IndexedSnippet(index=message.index, text=excerpt(message.content))
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
        family = extract_validation_family(messages[call.input_index])
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
            "indexing": "zero-based JSON array offsets",
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
