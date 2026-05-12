#!/usr/bin/env -S uv run
# /// script
# requires-python = "==3.12.*"
# dependencies = ["pyyaml"]
# ///
"""Deterministic transcript pruning — no heuristics, no semantics.

Reads a transcript JSON from stdin (or file argument), removes:
  1. All todo tool-input and tool-output messages (always noise).
  2. All Read/Write/Edit tool-output messages (file content, rule 4).
  3. Transforms Read/Write/Edit tool-input blocks to path-only references.

Outputs the pruned JSON to stdout. Does NOT mutate the input file.
"""
import json
import sys

FILE_CRUD_TOOLS = {"Read", "Write", "Edit"}


def prune(data: list[dict]) -> list[dict]:
    result: list[dict] = []

    # ── Pass 2: prune ───────────────────────────────────────────────

    for msg in data:
        blocks = msg.get("content", [])
        if not isinstance(blocks, list):
            result.append(msg)
            continue

        # Separate blocks by type
        todo_blocks = [
            b for b in blocks
            if isinstance(b, dict) and b.get("name") == "todo"
        ]
        file_output_blocks = [
            b for b in blocks
            if isinstance(b, dict)
            and b.get("type") == "tool-output"
            and b.get("name") in FILE_CRUD_TOOLS
        ]
        file_input_blocks = [
            b for b in blocks
            if isinstance(b, dict)
            and b.get("type") == "tool-input"
            and b.get("name") in FILE_CRUD_TOOLS
        ]
        other_blocks = [
            b for b in blocks
            if b not in todo_blocks
            and b not in file_output_blocks
            and b not in file_input_blocks
        ]

        # Rule 1: pure todo messages → drop
        if todo_blocks and not other_blocks and not file_input_blocks:
            continue

        # Rule 2: pure file output messages → drop
        if file_output_blocks and not other_blocks and not todo_blocks and not file_input_blocks:
            continue

        # Rule 3: transform file input blocks to path-only
        if file_input_blocks:
            new_blocks = list(other_blocks)
            for b in file_input_blocks:
                name = b["name"]
                path = b.get("path", b.get("file_path", ""))
                rid = b.get("id", "?")
                new_blocks.append(f'<{name} path="{path}" id="{rid}"/>')
            msg = dict(msg)
            msg["content"] = new_blocks

        result.append(msg)

    return result


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "/dev/stdin"
    with open(path) as f:
        data = json.load(f)
    pruned = prune(data)
    json.dump(pruned, sys.stdout, indent=2)
    print(file=sys.stderr, flush=True)
    print(f"Input: {len(data)} messages  →  Output: {len(pruned)} messages", file=sys.stderr)


if __name__ == "__main__":
    main()
