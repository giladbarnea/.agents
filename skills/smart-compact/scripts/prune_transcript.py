#!/usr/bin/env -S uv run
# /// script
# requires-python = "==3.12.*"
# dependencies = []
# ///
"""Deterministically remove transcript noise that needs no semantic judgment.

Reads a transcript JSON from stdin or a file argument and writes pruned JSON to
stdout. The input is never mutated.
"""

import argparse
import dataclasses
import json
import pathlib
import sys

import transcript_common


NOISE_TOOL_NAMES = frozenset({"todo"})
EMPTY_ORPHAN_KEYS = frozenset(
    {"type", "name", "id", "native_tool_call_id", "native_content_index"}
)


@dataclasses.dataclass
class EmptyOrphan:
    original_index: int
    tool_name: str
    tool_id: str
    block: dict[str, object]


def find_empty_orphans(data: list[dict[str, object]]) -> list[EmptyOrphan]:
    """Find payload-free file-tool inputs with no corresponding output.

    >>> source = [{'original_index': 1, 'content': [{'type': 'tool-input', 'name': 'Edit', 'id': 'x'}]}]
    >>> [(orphan.original_index, orphan.tool_id) for orphan in find_empty_orphans(source)]
    [(1, 'x')]
    """
    output_ids = {
        identifier
        for message in data
        for block in message.get("content", [])
        if isinstance(block, dict) and block.get("type") == "tool-output"
        for identifier in [block.get("id")]
        if isinstance(identifier, str)
    }
    orphans: list[EmptyOrphan] = []
    for message in data:
        original_index = message.get("original_index")
        blocks = message.get("content")
        if not isinstance(original_index, int) or not isinstance(blocks, list):
            continue
        for block in blocks:
            if not isinstance(block, dict) or block.get("type") != "tool-input":
                continue
            tool_name = block.get("name")
            tool_id = block.get("id")
            if tool_name not in transcript_common.FILE_TOOLS or not isinstance(tool_id, str):
                continue
            if set(block) - EMPTY_ORPHAN_KEYS or tool_id in output_ids:
                continue
            orphans.append(EmptyOrphan(original_index, str(tool_name), tool_id, block))
    return orphans


def drop_authorized_empty_orphans(
    data: list[dict[str, object]], authorized_tool_ids: set[str]
) -> tuple[list[dict[str, object]], list[EmptyOrphan]]:
    """Drop only explicitly authorized, uniquely identifiable empty orphans.

    >>> source = [{'original_index': 1, 'content': [{'type': 'tool-input', 'name': 'Edit', 'id': 'x'}]}]
    >>> drop_authorized_empty_orphans(source, {'x'})[0]
    []
    """
    candidates_by_id: dict[str, list[EmptyOrphan]] = {}
    for orphan in find_empty_orphans(data):
        candidates_by_id.setdefault(orphan.tool_id, []).append(orphan)

    invalid_ids = sorted(
        tool_id
        for tool_id in authorized_tool_ids
        if len(candidates_by_id.get(tool_id, [])) != 1
    )
    if invalid_ids:
        raise ValueError(
            "authorized orphan IDs must each identify exactly one payload-free, "
            f"unpaired file-tool call: {invalid_ids}"
        )

    unapproved_orphans = sorted(
        (
            orphan
            for candidates in candidates_by_id.values()
            for orphan in candidates
            if orphan.tool_id not in authorized_tool_ids
        ),
        key=lambda orphan: orphan.original_index,
    )
    if unapproved_orphans:
        descriptions = ", ".join(
            f"{orphan.tool_name} {orphan.tool_id!r} at message {orphan.original_index}"
            for orphan in unapproved_orphans
        )
        flags = " ".join(
            f"--drop-orphan-tool-id {orphan.tool_id}" for orphan in unapproved_orphans
        )
        raise ValueError(
            f"found empty interrupted file-tool calls: {descriptions}; inspect them, "
            f"then authorize removal with {flags}"
        )

    dropped = sorted(
        (candidates_by_id[tool_id][0] for tool_id in authorized_tool_ids),
        key=lambda orphan: orphan.original_index,
    )
    dropped_block_identities = {id(orphan.block) for orphan in dropped}
    cleaned: list[dict[str, object]] = []
    for message in data:
        blocks = message.get("content")
        if not isinstance(blocks, list):
            cleaned.append(message)
            continue
        remaining_blocks = [block for block in blocks if id(block) not in dropped_block_identities]
        if not remaining_blocks:
            continue
        cleaned_message = dict(message)
        cleaned_message["content"] = remaining_blocks
        cleaned.append(cleaned_message)
    return cleaned, dropped


def prune(data: list[dict[str, object]]) -> list[dict[str, object]]:
    """Prune deterministic noise while preserving message and block order.

    >>> prune([{'content': [{'type': 'tool-input', 'name': 'todo'}]}])
    []
    """
    result: list[dict[str, object]] = []
    seen_skill_bodies: set[str] = set()
    for message in data:
        blocks = message.get("content")
        if not isinstance(blocks, list):
            result.append(message)
            continue

        pruned_blocks: list[object] = []
        for block in blocks:
            if isinstance(block, str):
                invocation = transcript_common.split_skill_invocation(block)
                if invocation is None:
                    pruned_blocks.append(block)
                    continue
                skill_body, instruction = invocation
                if skill_body not in seen_skill_bodies:
                    seen_skill_bodies.add(skill_body)
                    pruned_blocks.append(skill_body)
                if instruction:
                    pruned_blocks.append(instruction)
                continue
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
                native_tool_call_id = block.get("native_tool_call_id")
                native_content_index = block.get("native_content_index")
                pruned_blocks.extend(
                    transcript_common.render_reference(
                        *reference,
                        native_tool_call_id=(
                            native_tool_call_id
                            if isinstance(native_tool_call_id, str)
                            else None
                        ),
                        native_content_index=(
                            native_content_index
                            if isinstance(native_content_index, int)
                            else None
                        ),
                    )
                    for reference in references
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("transcript_json", nargs="?", type=pathlib.Path, default=pathlib.Path("/dev/stdin"))
    parser.add_argument(
        "--drop-orphan-tool-id",
        action="append",
        default=[],
        metavar="TOOL_ID",
        help="drop one inspected payload-free file-tool call with no matching output",
    )
    arguments = parser.parse_args()

    with arguments.transcript_json.open(encoding="utf-8") as transcript_file:
        data = json.load(transcript_file)
    if not isinstance(data, list) or not all(isinstance(message, dict) for message in data):
        raise ValueError("expected a top-level JSON array of message objects")

    cleaned, dropped_orphans = drop_authorized_empty_orphans(
        data, set(arguments.drop_orphan_tool_id)
    )
    pruned = prune(cleaned)
    json.dump(pruned, sys.stdout, ensure_ascii=False, indent=2)
    print(file=sys.stdout)
    if dropped_orphans:
        rendered_orphans = ", ".join(
            f"{orphan.tool_name} {orphan.tool_id!r} at message {orphan.original_index}"
            for orphan in dropped_orphans
        )
        print(f"Dropped empty orphan tool calls: {rendered_orphans}", file=sys.stderr)
    print(f"Input: {len(data)} messages  →  Output: {len(pruned)} messages", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
