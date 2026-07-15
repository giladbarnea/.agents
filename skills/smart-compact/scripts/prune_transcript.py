#!/usr/bin/env -S uv run
# /// script
# requires-python = "==3.12.*"
# dependencies = []
# ///
"""Deterministically remove transcript noise that needs no semantic judgment.

Reads a transcript JSON from stdin or a file argument and writes pruned JSON to
stdout. The input is never mutated.
"""

import json
import sys

import transcript_common


NOISE_TOOL_NAMES = frozenset({"todo"})


def prune(data: list[dict[str, object]]) -> list[dict[str, object]]:
    """Prune deterministic noise while preserving message and block order.

    >>> prune([{'content': [{'type': 'tool-input', 'name': 'todo'}]}])
    []
    """
    result: list[dict[str, object]] = []
    for message in data:
        blocks = message.get("content")
        if not isinstance(blocks, list):
            result.append(message)
            continue

        pruned_blocks: list[object] = []
        for block in blocks:
            if not isinstance(block, dict):
                pruned_blocks.append(block)
                continue
            if block.get("name") in NOISE_TOOL_NAMES:
                continue
            if (
                block.get("type") == "tool-output"
                and block.get("name") in transcript_common.FILE_OUTPUT_TOOLS
            ):
                continue

            references = transcript_common.file_references(block)
            if references:
                pruned_blocks.extend(
                    transcript_common.render_reference(*reference) for reference in references
                )
                continue
            pruned_blocks.append(block)

        if not pruned_blocks:
            continue
        pruned_message = dict(message)
        pruned_message["content"] = pruned_blocks
        result.append(pruned_message)
    return result


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else "/dev/stdin"
    with open(path, encoding="utf-8") as transcript_file:
        data = json.load(transcript_file)
    if not isinstance(data, list) or not all(isinstance(message, dict) for message in data):
        raise ValueError("expected a top-level JSON array of message objects")

    pruned = prune(data)
    json.dump(pruned, sys.stdout, ensure_ascii=False, indent=2)
    print(file=sys.stdout)
    print(f"Input: {len(data)} messages  →  Output: {len(pruned)} messages", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
