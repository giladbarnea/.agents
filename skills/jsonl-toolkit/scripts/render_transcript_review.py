#!/usr/bin/env -S uv run
# /// script
# requires-python = "==3.12.*"
# dependencies = ["pydantic"]
# ///
"""Render a structured transcript as chronological Markdown for review."""

import argparse
import dataclasses
import json
import pathlib
import sys
import typing
from typing import Annotated, Literal, Union

import pydantic

import transcript_common

# Inner block types this mode has vetted. They still render, as a type and a size.
# Tool blocks parse into their own classes and never reach the branch that reads this.
VETTED_BLOCKS = frozenset({"thinking", "subagent-task"})
# Result part types seen across every real export. Anything else is drift.
VETTED_PARTS = frozenset({"text", "image", "input_image", "tool_reference"})


class Loose(pydantic.BaseModel):
    """Duck typing. Unknown keys are data, not errors."""

    model_config = pydantic.ConfigDict(extra="allow")


class TextPart(Loose):
    type: Literal["text"]
    text: str


def parse_part(raw: object) -> object:
    """A part must name its type, and one claiming text must validate as text."""
    if not isinstance(raw, dict):
        return raw
    if raw.get("type") == "text":
        return TextPart.model_validate(raw)
    if not raw.get("type"):
        raise ValueError("result part has no type")
    return raw


ContentPart = Annotated[Union[TextPart, Loose], pydantic.BeforeValidator(parse_part)]


class ToolInputBlock(Loose):
    type: Literal["tool-input"]
    name: str = pydantic.Field(min_length=1)
    id: str | None = None
    native_tool_call_id: str | None = None
    native_content_index: int | None = None
    # Every remaining key is a tool argument of an unknown shape. They stay in
    # model_extra so the projector walks them without this mode naming any tool.


class ToolOutputBlock(Loose):
    type: Literal["tool-output"]
    # Present on every result in ~/.pi, ~/.codex and top-level ~/.claude sessions, but
    # absent on all 298 results of a real Claude *subagent* transcript, so it stays
    # optional. See .claude/projects/*/subagents/agent-agatekeep-a0f211a2904f78d0.jsonl.
    name: str | None = None
    id: str | None = None
    native_tool_call_id: str | None = None
    is_error: bool = False
    # Required on purpose. Every real export carries it, and a default here would
    # turn a renamed payload key into an empty result with every tripwire green.
    content: str | list[ContentPart]

    def text(self) -> str:
        """Collapse this result to plain text across the shapes exports use."""
        if isinstance(self.content, str):
            return self.content
        return "\n".join(
            part.text for part in self.content if isinstance(part, TextPart)
        )

    def non_text_kinds(self) -> list[str]:
        """Name and size the parts `text` cannot represent, such as images.

        >>> ToolOutputBlock(type="tool-output", content="plain").non_text_kinds()
        []
        """
        if isinstance(self.content, str):
            return []
        sizes: dict[str, int] = {}
        for part in self.content:
            kind = getattr(part, "type", None)
            if isinstance(part, TextPart) or not kind:
                continue
            held = sum(
                len(str(value)) for value in part.model_dump(exclude={"type"}).values()
            )
            sizes[str(kind)] = sizes.get(str(kind), 0) + held
        return [f"{kind} +{held} chars" for kind, held in sorted(sizes.items())]


class OpaqueBlock(Loose):
    """Thinking blocks, subagent tasks, anything else this mode passes through."""

    type: str


def parse_block(raw: object) -> object:
    """Choose the model by the block's own `type`, so its errors name real fields."""
    if isinstance(raw, str):
        return raw
    if not isinstance(raw, dict):
        raise ValueError("content item must be a string or an object")
    match raw.get("type"):
        case "tool-input":
            return ToolInputBlock.model_validate(raw)
        case "tool-output":
            return ToolOutputBlock.model_validate(raw)
        case None:
            raise ValueError("content block has no type")
        case _:
            return OpaqueBlock.model_validate(raw)


ContentItem = Annotated[
    Union[str, ToolInputBlock, ToolOutputBlock, OpaqueBlock],
    pydantic.BeforeValidator(parse_block),
]


class KnownMessage(Loose):
    type: Literal[
        "user-message",
        "user-command-input",
        "user-command-output",
        "recap",
        "compaction",
        "assistant-response",
        "agent",
        "custom",
        "session-rename",
    ]
    original_index: int
    content: list[ContentItem]
    role: str | None = None


class ForeignMessage(Loose):
    """A wrapper this code does not know.

    Its content is rendered as a trace rather than dropped, but it must still be a
    list. A wrapper shaped otherwise refuses the file, which is the loud failure.
    """

    type: str
    original_index: int | None = None
    content: list[object] = []


# Derived so the wrapper list lives in exactly one place, on KnownMessage.type.
KNOWN_MESSAGES = frozenset(typing.get_args(KnownMessage.model_fields["type"].annotation))


def parse_message(raw: object) -> object:
    """Choose the model by the message's own `type`, for the same reason."""
    if not isinstance(raw, dict):
        raise ValueError("message must be an object")
    kind = raw.get("type")
    if kind is None:
        raise ValueError("message has no type")
    if kind in KNOWN_MESSAGES:
        return KnownMessage.model_validate(raw)
    return ForeignMessage.model_validate(raw)


Message = Annotated[
    Union[KnownMessage, ForeignMessage], pydantic.BeforeValidator(parse_message)
]

TRANSCRIPT = pydantic.TypeAdapter(list[Message])


@dataclasses.dataclass(frozen=True)
class Verdict:
    """Whether --annotate may run, and why not when it may not."""

    ok: bool
    reason: str = ""
    messages: tuple[Message, ...] = ()


PROSE_MIN = 80
OUTPUT_BUDGET = 2000
PROSE_BUDGET = 900
# How much of a clipped value is kept from its end, where a verdict usually sits.
TAIL_SHARE = 600
# Only collapse an argument big enough that a back-reference is worth chasing.
COLLAPSE_MIN = 400
# Keys that say who or what produced a turn, when its type alone cannot. `isMeta`
# marks a harness-injected turn, which smart-compact drops and a typed turn is kept.
ATTRIBUTION_KEYS = frozenset(
    {"agent_id", "subagent_type", "name", "custom_type", "isMeta"}
)
# Message keys every real export carries. Anything else is drift worth reporting.
VETTED_MESSAGE_KEYS = (
    frozenset({
        "type", "role", "original_index", "content", "timestamp", "model",
        "native_entry_id", "sourceToolUserId", "branch", "status",
        "inherited_context",
    })
    | ATTRIBUTION_KEYS
)
MESSAGE_LABELS = {
    "user-message": "USER",
    "assistant-response": "SAY",
    "compaction": "COMPACTION-BOUNDARY",
    "recap": "RECAP",
    "agent": "AGENT",
    "custom": "CUSTOM",
    "user-command-input": "CMD-IN",
    "user-command-output": "CMD-OUT",
    "session-rename": "RENAME",
}


def clip_with_residue(text: str, budget: int) -> tuple[str, int]:
    """Clip a value and report how many characters that removed.

    >>> clip_with_residue("x" * 12, 10)[1]
    2
    """
    collapsed = transcript_common.normalize_whitespace(text)
    if len(collapsed) <= budget:
        return collapsed, 0
    tail = min(TAIL_SHARE, budget // 2)
    head = budget - tail
    removed = len(collapsed) - budget
    return f"{collapsed[:head]} …(+{removed} chars)… {collapsed[-tail:]}", removed


def clip(text: str, budget: int) -> str:
    """Collapse whitespace and, when clipping, keep both ends and say what went.

    A command result puts its verdict last: an exit status, a final tally, the
    error that stopped it. Keeping only the head throws that away.

    >>> clip("a  b", 10)
    'a b'
    >>> clip("start" + "x" * 30 + "end", 20)
    'startxxxxx …(+18 chars)… xxxxxxxend'
    """
    return clip_with_residue(text, budget)[0]


def summarize_output(block: ToolOutputBlock) -> str:
    """Clip a result to its budget. Never drop one.

    Size does not track value. A refused request, a chosen option, and a routine
    receipt are all about the same length, so any size rule that hides the
    receipt hides the verdict with it.

    >>> summarize_output(ToolOutputBlock(type="tool-output", content="ok"))
    'ok'
    """
    carried = "".join(f" [{kind}]" for kind in block.non_text_kinds())
    body = clip(block.text(), OUTPUT_BUDGET)
    return f"{'ERROR: ' if block.is_error else ''}{body}{carried}"


def project_arguments(
    block: ToolInputBlock,
) -> tuple[list[tuple[str, str]], dict[str, object]]:
    """Split a tool call's arguments into prose and tags by shape, not by tool name.

    A string at or above PROSE_MIN carries meaning. Everything else is a label.
    Containers are walked, so nesting depth and key names never matter.

    >>> call = ToolInputBlock(type="tool-input", name="T", note="x" * 90, retries=2)
    >>> paths, tags = project_arguments(call)
    >>> [path for path, _ in paths], tags
    (['note'], {'retries': 2})
    """
    prose: list[tuple[str, str]] = []
    tags: dict[str, object] = {}

    def walk(value: object, path: str) -> None:
        if isinstance(value, str):
            if len(value) >= PROSE_MIN:
                prose.append((path, value))
            else:
                tags[path] = value
            return
        if isinstance(value, (dict, list)) and not value:
            tags[path] = value
            return
        if isinstance(value, dict):
            for key, nested in value.items():
                walk(nested, f"{path}.{key}" if path else str(key))
            return
        if isinstance(value, list):
            for position, nested in enumerate(value):
                walk(nested, f"{path}.{position}" if path else str(position))
            return
        tags[path] = value

    if block.model_extra:
        walk(block.model_extra, "")
    return prose, tags


def gate(raw: object) -> Verdict:
    """Accept a transcript only when nothing it recognizes is malformed.

    >>> gate([{"type": "user-message", "original_index": 1, "content": ["hi"]}]).ok
    True
    >>> gate([{"type": "user-message", "original_index": 1, "content": []}]).reason
    'no messages match the assumed export shape'
    """
    if not isinstance(raw, list):
        return Verdict(False, "expected a top-level JSON array of message objects")
    try:
        parsed = TRANSCRIPT.validate_python(raw)
    except pydantic.ValidationError as error:
        first = error.errors()[0]
        location = [str(part) for part in first.get("loc", ())]
        if location and location[0].isdigit():
            position = int(location[0])
            entry = raw[position] if position < len(raw) else None
            stable = entry.get("original_index") if isinstance(entry, dict) else None
            location[0] = f"i={stable}" if stable is not None else f"position {position}"
        return Verdict(False, f"{'.'.join(location)}: {first.get('msg')}")
    if not any(
        isinstance(message, KnownMessage) and message.content for message in parsed
    ):
        return Verdict(False, "no messages match the assumed export shape")
    return Verdict(True, messages=tuple(parsed))


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


def vetted_block_text(block: object) -> str:
    """The readable content of a block this mode renders but does not model."""
    return " ".join(
        str(value) for value in block.model_dump(exclude={"type"}).values()
    )


def block_kind(item: object) -> str:
    """Name a content item of unknown shape.

    >>> block_kind({"type": "thinking"}), block_kind([1]), block_kind(7)
    ('thinking', 'list', 'int')
    """
    if isinstance(item, dict):
        return str(item.get("type", "block"))
    return type(item).__name__


def render_annotated(messages: tuple[Message, ...]) -> str:
    """Render one line per element, keyed for transcription into annotations.

    Each tool line carries the stable index and the tool identity that
    `smart-compact` skeletons anchor on, so reading it is the annotation work.
    """
    answered = {
        block.id or block.native_tool_call_id
        for message in messages
        if isinstance(message, KnownMessage)
        for block in message.content
        if isinstance(block, ToolOutputBlock)
    }
    lines: list[str] = []
    announced = ""
    first_seen: dict[str, tuple[object, str]] = {}
    for message in messages:
        index = message.original_index if message.original_index is not None else "?"
        if not isinstance(message, KnownMessage):
            lines.append(f"[{index}] <unrecognized wrapper {message.type}>")
            lines.extend(
                f"[{index}]   {item}"
                if isinstance(item, str)
                else f"[{index}]   <{block_kind(item)} +{len(str(item))} chars>"
                for item in message.content
            )
            continue
        speaker = MESSAGE_LABELS.get(message.type, message.type.upper())
        if message.type == "agent" and message.role:
            speaker = f"{speaker}<-{message.role}" if message.role == "user" else speaker
        attribution = " ".join(
            f"{key}={value!r}"
            for key, value in (message.model_extra or {}).items()
            if key in ATTRIBUTION_KEYS
        )
        carries_text = any(
            isinstance(block, str) and transcript_common.file_reference(block) is None
            for block in message.content
        )
        if not carries_text and (
            attribution or message.type not in {"user-message", "assistant-response"}
        ):
            header = f"{speaker} {attribution}".strip()
            if header != announced:
                lines.append(f"[{index}] <{header}>")
                announced = header
        speaker = f"{speaker} {attribution}" if attribution else speaker
        for block in message.content:
            if isinstance(block, str):
                reference = transcript_common.file_reference(block)
                lines.append(
                    f"[{index}] {block}"
                    if reference is not None
                    else f"[{index}] {speaker}: {block}"
                )
            elif isinstance(block, ToolInputBlock):
                prose, tags = project_arguments(block)
                handle = block.id or block.native_tool_call_id or "missing-id"
                rendered_tags = " ".join(f"{key}={value!r}" for key, value in tags.items())
                unanswered = "" if handle in answered else " no-result-in-file"
                head = f"{block.name} id={handle}{unanswered}"
                lines.append(f"[{index}] <{head} {rendered_tags}>" if rendered_tags else f"[{index}] <{head}>")
                for path, value in prose:
                    origin, origin_handle = first_seen.setdefault(value, (index, handle))
                    shown = clip(value, PROSE_BUDGET)
                    reference = f"<identical to i={origin} id={origin_handle}>"
                    lines.append(
                        f"[{index}]   {path}: {reference}"
                        if origin != index and len(shown) >= COLLAPSE_MIN
                        else f"[{index}]   {path}: {shown}"
                    )
            elif isinstance(block, ToolOutputBlock):
                handle = block.id or block.native_tool_call_id or "no-id"
                body = summarize_output(block)
                # Identity is the whole result, not the clipped body and not the text
                # alone. The body would fuse two results that differ past the budget.
                # The text alone would drop the error flag and the carried payloads.
                identity = f"out:{block.is_error}:{block.non_text_kinds()}:{block.text()}"
                origin, origin_handle = first_seen.setdefault(identity, (index, handle))
                reference = f"<identical to i={origin} id={origin_handle}>"
                label = f"OUT {block.name} id={handle}" if block.name else f"OUT id={handle}"
                lines.append(
                    f"[{index}]   {label}: {reference}"
                    if origin != index and len(body) > len(reference)
                    else f"[{index}]   {label}: {body}"
                )
            elif block.type in VETTED_BLOCKS:
                lines.append(
                    f"[{index}] <{block.type}> "
                    f"{clip(vetted_block_text(block), PROSE_BUDGET)}"
                )
            else:
                held = sum(
                    len(str(value)) for value in block.model_dump(exclude={"type"}).values()
                )
                lines.append(f"[{index}] <{block.type} +{held} chars>")
    return "\n".join(lines) + "\n"


def spliced(text: str) -> bool:
    r"""True when a value carries the bare `...` line that marks a truncated export.

    >>> spliced("head\n...\ntail")
    True
    >>> spliced("an ordinary ... ellipsis")
    False
    """
    return any(line.strip() == "..." for line in text.splitlines())


def projection_summary(messages: tuple[Message, ...]) -> list[str]:
    """Report what the projector saw, so a future export change is visible."""
    passthrough: dict[str, int] = {}
    identities: list[str] = []
    colliding_anchors = 0
    calls = payload_free = cut_arguments = cut_results = 0
    clipped_values = clipped_characters = 0

    for message in messages:
        if not isinstance(message, KnownMessage):
            key = f"wrapper:{message.type}"
            passthrough[key] = passthrough.get(key, 0) + 1
            continue
        for key in message.model_extra or {}:
            if key not in VETTED_MESSAGE_KEYS:
                passthrough[f"message key:{key}"] = (
                    passthrough.get(f"message key:{key}", 0) + 1
                )
        in_message: list[str] = []
        for block in message.content:
            if isinstance(block, ToolInputBlock):
                calls += 1
                arguments = block.model_extra or {}
                if not arguments:
                    payload_free += 1
                prose, _ = project_arguments(block)
                cut_arguments += sum(spliced(value) for _, value in prose)
                for _, value in prose:
                    lost = clip_with_residue(value, PROSE_BUDGET)[1]
                    clipped_values += bool(lost)
                    clipped_characters += lost
                handle = block.id or block.native_tool_call_id
                if handle:
                    identities.append(handle)
                    in_message.append(handle)
            elif isinstance(block, ToolOutputBlock):
                cut_results += spliced(block.text())
                lost = clip_with_residue(block.text(), OUTPUT_BUDGET)[1]
                clipped_values += bool(lost)
                clipped_characters += lost
                for key in block.model_extra or {}:
                    passthrough[f"result key:{key}"] = (
                        passthrough.get(f"result key:{key}", 0) + 1
                    )
                for part in block.content if isinstance(block.content, list) else []:
                    kind = getattr(part, "type", None)
                    if kind and str(kind) not in VETTED_PARTS:
                        passthrough[f"result part:{kind}"] = (
                            passthrough.get(f"result part:{kind}", 0) + 1
                        )
            elif not isinstance(block, str) and block.type in VETTED_BLOCKS:
                held = vetted_block_text(block)
                cut_arguments += spliced(held)
                lost = clip_with_residue(held, PROSE_BUDGET)[1]
                clipped_values += bool(lost)
                clipped_characters += lost
            elif not isinstance(block, str):
                passthrough[block.type] = passthrough.get(block.type, 0) + 1
        colliding_anchors += len(in_message) - len(set(in_message))

    tally = (
        ", ".join(f"{name}×{count}" for name, count in sorted(passthrough.items()))
        or "none"
    )

    if colliding_anchors:
        identity_note = (
            f"NOT UNIQUE within a message ({colliding_anchors} calls collide), so a "
            "skeleton anchor is ambiguous and `unmatched` cannot be believed"
        )
    elif not calls:
        identity_note = "not applicable, this session made no tool calls"
    elif not identities:
        identity_note = (
            "none found, so this export carries no per-call handle to anchor on"
        )
    elif len(identities) != len(set(identities)):
        identity_note = (
            f"NOT UNIQUE across messages ({len(identities)} calls share "
            f"{len(set(identities))} ids), so `unmatched` cannot be believed. Skeleton "
            "anchors resolve per message and stay sound"
        )
    else:
        identity_note = "unique"

    splices = (
        f"{cut_arguments} arguments and {cut_results} results carry a bare `...` line"
        if cut_arguments or cut_results
        else "none"
    )
    own_losses = (
        f"{clipped_characters} characters from {clipped_values} values, each marked "
        "in place with its own residue count"
        if clipped_values
        else "nothing"
    )
    return [
        f"annotate | unrecognized block and wrapper types: {tally}",
        f"annotate | values spliced with `...`: {splices}",
        f"annotate | tool ids: {identity_note}",
        f"annotate | calls carrying no arguments: {payload_free} of {calls}",
        f"annotate | this view clipped: {own_losses}",
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "transcript_json",
        nargs="?",
        type=pathlib.Path,
        default=pathlib.Path("/dev/stdin"),
    )
    parser.add_argument(
        "--annotate",
        action="store_true",
        help="Render a compact, annotation-ready view instead of the full JSON review.",
    )
    arguments = parser.parse_args()
    with arguments.transcript_json.open(encoding="utf-8") as transcript_file:
        try:
            raw_messages = json.load(transcript_file)
        except json.JSONDecodeError as error:
            raise SystemExit(
                f"{arguments.transcript_json} is not one JSON document, so it is not a "
                f"`ch -f json` export. A native session is JSONL and must be exported "
                f"first. ({error})"
            ) from error
    if arguments.annotate:
        verdict = gate(raw_messages)
        if not verdict.ok:
            raise SystemExit(f"--annotate does not apply to this file: {verdict.reason}")
        sys.stdout.write(render_annotated(verdict.messages))
        print("\n".join(projection_summary(verdict.messages)), file=sys.stderr)
        return 0
    if not isinstance(raw_messages, list) or not all(
        isinstance(message, dict) for message in raw_messages
    ):
        raise ValueError("expected a top-level JSON array of message objects")
    messages = [message for message in raw_messages if isinstance(message, dict)]
    sys.stdout.write(render(messages))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
