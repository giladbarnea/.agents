#!/usr/bin/env -S uv run
# /// script
# requires-python = "==3.12.*"
# dependencies = []
# ///
"""Render a structured transcript as chronological Markdown for review."""

import argparse
import json
import pathlib
import sys

import transcript_common


def tool_blocks_by_id(
    messages: list[dict[str, object]], block_type: str
) -> dict[str, list[dict[str, object]]]:
    grouped: dict[str, list[dict[str, object]]] = {}
    for message in messages:
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict) or block.get("type") != block_type:
                continue
            identifier = block.get("id")
            if not isinstance(identifier, str):
                continue
            grouped.setdefault(identifier, []).append(block)
    return grouped


def json_block(block: dict[str, object]) -> str:
    return "```json\n" + json.dumps(block, ensure_ascii=False, indent=2) + "\n```"


def tool_event(
    identifier: str,
    status: str,
    input_block: dict[str, object] | None,
    output_block: dict[str, object] | None,
) -> str:
    parts = [f"### Tool event `{identifier}` — {status}"]
    if input_block is not None:
        parts.extend(["**Input**", json_block(input_block)])
    if output_block is not None:
        parts.extend(["**Output**", json_block(output_block)])
    return "\n\n".join(parts)


def render_tool_block(
    block: dict[str, object],
    inputs_by_id: dict[str, list[dict[str, object]]],
    outputs_by_id: dict[str, list[dict[str, object]]],
) -> list[str]:
    block_type = block.get("type")
    identifier_value = block.get("id")
    identifier = identifier_value if isinstance(identifier_value, str) else "missing-id"
    inputs = inputs_by_id.get(identifier, [])
    outputs = outputs_by_id.get(identifier, [])
    is_pair = len(inputs) == 1 and len(outputs) == 1
    if block_type == "tool-output" and is_pair:
        return []
    if block_type == "tool-input" and is_pair:
        return [tool_event(identifier, "paired", block, outputs[0])]
    if block_type == "tool-input":
        return [tool_event(identifier, "unmatched input", block, None)]
    if block_type == "tool-output":
        return [tool_event(identifier, "unmatched output", None, block)]
    return [json_block(block)]


def render_block(
    block: object,
    original_index: int,
    first_skill_indices: dict[str, int],
    inputs_by_id: dict[str, list[dict[str, object]]],
    outputs_by_id: dict[str, list[dict[str, object]]],
) -> list[str]:
    if isinstance(block, dict):
        return render_tool_block(block, inputs_by_id, outputs_by_id)
    if not isinstance(block, str):
        return [json.dumps(block, ensure_ascii=False, indent=2)]
    invocation = transcript_common.split_skill_invocation(block)
    if invocation is None:
        return [block]
    skill_body, tail = invocation
    first_index = first_skill_indices.get(skill_body)
    if first_index is None:
        first_skill_indices[skill_body] = original_index
        return [skill_body, tail]
    return [f'<skill-body-elided duplicate-of="{first_index}"/>', tail]


def message_heading(message: dict[str, object], original_index: int) -> str:
    if message.get("type") == "compaction":
        return f"Compaction boundary [i={original_index}]"
    role = "User" if message.get("role") == "user" else "Assistant"
    return f"{role} [i={original_index}]"


def render(messages: list[dict[str, object]]) -> str:
    """Render transcript messages as a review-oriented Markdown view."""
    first_skill_indices: dict[str, int] = {}
    inputs_by_id = tool_blocks_by_id(messages, "tool-input")
    outputs_by_id = tool_blocks_by_id(messages, "tool-output")
    sections: list[str] = []
    for message in messages:
        original_index = message.get("original_index")
        blocks = message.get("content", [])
        if not isinstance(original_index, int) or not isinstance(blocks, list):
            raise ValueError("every message needs an integer original_index and content array")
        rendered_blocks = [
            rendered
            for block in blocks
            for rendered in render_block(
                block,
                original_index,
                first_skill_indices,
                inputs_by_id,
                outputs_by_id,
            )
            if rendered
        ]
        if not rendered_blocks:
            continue
        heading = message_heading(message, original_index)
        sections.append(f"## {heading}\n\n" + "\n\n".join(rendered_blocks))
    return "\n\n---\n\n".join(sections) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "transcript_json",
        nargs="?",
        type=pathlib.Path,
        default=pathlib.Path("/dev/stdin"),
    )
    arguments = parser.parse_args()
    with arguments.transcript_json.open(encoding="utf-8") as transcript_file:
        raw_messages = json.load(transcript_file)
    if not isinstance(raw_messages, list) or not all(
        isinstance(message, dict) for message in raw_messages
    ):
        raise ValueError("expected a top-level JSON array of message objects")
    messages = [message for message in raw_messages if isinstance(message, dict)]
    sys.stdout.write(render(messages))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
