#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = ["pyyaml"]
# ///
"""Add smart-compaction candidate hints to the generic transcript report."""

from __future__ import annotations

import argparse
import collections
import dataclasses
import pathlib
import re
import sys

import yaml

PARENT_SCRIPTS = pathlib.Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(PARENT_SCRIPTS))

import analyze_transcript_json

MURMUR_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
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
    )
)
SCRATCHPAD_PATTERNS = tuple(
    re.compile(pattern)
    for pattern in (r"^/tmp/", r"/tmp/", r"\.tmp$", r"\.bak$", r"/scratch/")
)
MUTATION_TOOL_NAMES = frozenset({"Write", "Edit", "Patch"})


@dataclasses.dataclass(slots=True)
class IndexedSnippet:
    index: int
    text: str


def looks_like_murmur(message: analyze_transcript_json.Message) -> bool:
    """Return whether short prose matches a configured murmur pattern."""
    text = analyze_transcript_json.normalize_whitespace(message.text_content)
    return bool(text) and len(text) <= 220 and any(
        pattern.search(text) for pattern in MURMUR_PATTERNS
    )


def looks_like_write_edit_receipt(message: analyze_transcript_json.Message) -> bool:
    """Return whether a mutation output looks like a success-only receipt."""
    return any(
        isinstance(block.get("name"), str)
        and block.get("name") in MUTATION_TOOL_NAMES
        and "success" in analyze_transcript_json.block_text(block).lower()
        for block in message.tool_outputs
    )


def looks_like_bash_success_receipt(message: analyze_transcript_json.Message) -> bool:
    """Return whether a Bash output looks like a success-only receipt."""
    fragments = (
        "successfully",
        "completed with no output",
        "no content change, skipping",
        "is up to date, skipping",
        "tooling installation complete",
    )
    return any(
        block.get("name") == "Bash"
        and any(
            fragment in analyze_transcript_json.block_text(block).lower()
            for fragment in fragments
        )
        for block in message.tool_outputs
    )


def is_local_command_caveat(message: analyze_transcript_json.Message) -> bool:
    """Return whether the message contains a local-command caveat."""
    return any(
        isinstance(block, str) and "<local-command-caveat>" in block
        for block in message.content
    )


def is_scratchpad_path(path: str) -> bool:
    """Return whether a path matches a configured transient-path pattern."""
    return any(pattern.search(path) for pattern in SCRATCHPAD_PATTERNS)


def collect_snippets(
    messages: list[analyze_transcript_json.Message],
    predicate: object,
) -> list[IndexedSnippet]:
    """Collect indexed excerpts from messages accepted by a predicate."""
    if not callable(predicate):
        raise TypeError("predicate must be callable")
    return [
        IndexedSnippet(
            message.index,
            analyze_transcript_json.excerpt(message.all_block_text),
        )
        for message in messages
        if predicate(message)
    ]


def noise_block(snippets: list[IndexedSnippet], top: int) -> dict[str, object]:
    """Render count, indices, and samples for one candidate family."""
    return {
        "count": len(snippets),
        "indices": [snippet.index for snippet in snippets],
        "samples": [dataclasses.asdict(snippet) for snippet in snippets[:top]],
    }


def build_report(
    messages: list[analyze_transcript_json.Message], top: int
) -> dict[str, object]:
    """Build the generic report plus smart-compaction candidate hints."""
    report = analyze_transcript_json.build_report(messages, top)
    touches_by_path: dict[str, dict[str, list[int]]] = collections.defaultdict(
        lambda: collections.defaultdict(list)
    )
    for touch in analyze_transcript_json.detect_file_touches(messages):
        touches_by_path[touch.path][touch.tool].append(touch.index)

    report["noise"] = {
        "murmur_candidates": noise_block(collect_snippets(messages, looks_like_murmur), top),
        "write_edit_receipts": noise_block(
            collect_snippets(messages, looks_like_write_edit_receipt), top
        ),
        "bash_success_receipts": noise_block(
            collect_snippets(messages, looks_like_bash_success_receipt), top
        ),
        "local_command_caveats": noise_block(
            collect_snippets(messages, is_local_command_caveat), top
        ),
        "scratchpad_paths": [
            {
                "path": path,
                "ops": {
                    tool.lower(): indices
                    for tool, indices in sorted(touches_by_path[path].items())
                },
            }
            for path in sorted(touches_by_path)
            if is_scratchpad_path(path)
        ][:top],
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("json_path", type=pathlib.Path)
    parser.add_argument("--top", type=int, default=8)
    arguments = parser.parse_args()

    messages = analyze_transcript_json.load_messages(arguments.json_path)
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
