#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Apply a semantic compaction plan to an explicit native Pi session copy.

The source transcript is required because the plan addresses its stable
``original_index`` values. The target JSONL is changed in place only after the
plan, native mapping, transformed tree, and tool pairing all validate. A
byte-identical sibling backup is created before the atomic replacement.

Usage:
    uv run transfer_to_pi_session.py pruned.json compaction-plan.json session-copy.jsonl
"""

import argparse
import dataclasses
import datetime
import json
import os
import re
import secrets
import sys
import tempfile
import xml.etree.ElementTree
from pathlib import Path

SMART_COMPACT_SCRIPTS = Path(__file__).resolve().parents[1] / "smart-compact" / "scripts"
sys.path.insert(0, str(SMART_COMPACT_SCRIPTS))

import apply_compaction_plan
import transcript_common

WATERMARK_TYPE = "smart-compact-watermark"


def fail(message: str) -> SystemExit:
    return SystemExit(f"ABORT (session file untouched): {message}")


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


@dataclasses.dataclass
class SessionLine:
    raw: str
    data: dict[str, object]
    changed: bool = False

    @property
    def identifier(self) -> str | None:
        identifier = self.data.get("id")
        return identifier if isinstance(identifier, str) else None


@dataclasses.dataclass(frozen=True)
class NativeToolCall:
    entry: SessionLine
    content_index: int
    identifier: str
    name: str
    block: dict[str, object]

    @property
    def occurrence_key(self) -> tuple[str, int]:
        entry_identifier = self.entry.identifier
        if entry_identifier is None:
            raise fail("native tool call entry has no string id")
        return entry_identifier, self.content_index


@dataclasses.dataclass(frozen=True)
class NativeToolResult:
    entry: SessionLine
    identifier: str
    name: str


@dataclasses.dataclass(frozen=True)
class NativeToolOccurrence:
    call: NativeToolCall
    result: NativeToolResult | None


@dataclasses.dataclass
class SourceToolEvent:
    original_index: int
    name: str
    replacements: list[str]
    native_entry_id: str
    native_identifier: str
    native_content_index: int
    native_occurrence: NativeToolOccurrence | None = None


@dataclasses.dataclass(frozen=True)
class Watermark:
    entry: SessionLine
    resume_after_entry_id: str
    source_through_entry_id: str
    pass_number: int


@dataclasses.dataclass(frozen=True)
class TailBoundary:
    resume_after_entry_id: str | None
    native_cutoff_index: int
    next_pass_number: int


def parse_session(path: Path) -> tuple[SessionLine, list[SessionLine]]:
    parsed: list[SessionLine] = []
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise fail(f"line {line_number} is not a JSON object")
        parsed.append(SessionLine(raw, value))
    if len(parsed) < 2 or parsed[0].data.get("type") != "session":
        raise fail("native JSONL needs a session header and at least one tree entry")

    header = parsed[0]
    tree = parsed[1:]
    by_identifier = {
        line.identifier: line for line in tree if line.identifier is not None
    }
    if len(by_identifier) != len(tree):
        raise fail("every native tree entry must have a unique string id")

    active_reversed: list[SessionLine] = []
    seen: set[str] = set()
    current: SessionLine | None = tree[-1]
    while current is not None:
        identifier = current.identifier
        if identifier is None or identifier in seen:
            raise fail(f"native parent chain cycles at {identifier!r}")
        active_reversed.append(current)
        seen.add(identifier)
        parent_identifier = current.data.get("parentId")
        if parent_identifier is None:
            current = None
            continue
        if not isinstance(parent_identifier, str) or parent_identifier not in by_identifier:
            raise fail(
                f"entry {identifier!r} has unresolved parentId {parent_identifier!r}"
            )
        current = by_identifier[parent_identifier]

    active = list(reversed(active_reversed))
    if active[0].data.get("parentId") is not None:
        raise fail("active path has no root with parentId:null")
    return header, active


def watermarks(header: SessionLine, active: list[SessionLine]) -> list[Watermark]:
    """Return validated smart-compaction watermarks on the active path."""
    session_id = header.data.get("id")
    positions = {
        line.identifier: index
        for index, line in enumerate(active)
        if line.identifier is not None
    }
    found: list[Watermark] = []
    for index, line in enumerate(active):
        if line.data.get("customType") != WATERMARK_TYPE:
            continue
        data = line.data.get("data")
        if (
            line.data.get("type") != "custom"
            or line.data.get("display") is not False
            or not isinstance(data, dict)
            or data.get("version") != 1
            or data.get("session_id") != session_id
        ):
            raise fail(f"entry {line.identifier!r} is a malformed smart-compact watermark")
        resume_after_entry_id = data.get("resume_after_entry_id")
        source_through_entry_id = data.get("source_through_entry_id")
        pass_number = data.get("pass")
        stats = data.get("stats")
        if (
            not isinstance(resume_after_entry_id, str)
            or not isinstance(source_through_entry_id, str)
            or not isinstance(pass_number, int)
            or pass_number < 1
            or not isinstance(stats, dict)
        ):
            raise fail(f"entry {line.identifier!r} has invalid watermark data")
        resume_position = positions.get(resume_after_entry_id)
        if resume_position is None or resume_position >= index:
            raise fail(
                f"watermark {line.identifier!r} has an invalid resume anchor "
                f"{resume_after_entry_id!r}"
            )
        found.append(
            Watermark(
                line,
                resume_after_entry_id,
                source_through_entry_id,
                pass_number,
            )
        )
    pass_numbers = [watermark.pass_number for watermark in found]
    if pass_numbers != sorted(set(pass_numbers)):
        raise fail("active smart-compact watermark pass numbers are not strictly increasing")
    return found


def resolve_tail_boundary(
    header: SessionLine,
    active: list[SessionLine],
    from_entry_id: str | None,
) -> TailBoundary:
    """Resolve an explicit entry or the latest watermark to one exclusive cutoff."""
    positions = {
        line.identifier: index
        for index, line in enumerate(active)
        if line.identifier is not None
    }
    found_watermarks = watermarks(header, active)
    latest = found_watermarks[-1] if found_watermarks else None
    next_pass_number = latest.pass_number + 1 if latest is not None else 1
    if from_entry_id is None:
        if latest is None:
            return TailBoundary(None, -1, next_pass_number)
        return TailBoundary(
            latest.resume_after_entry_id,
            positions[latest.entry.identifier],
            next_pass_number,
        )

    explicit_position = positions.get(from_entry_id)
    if explicit_position is None:
        raise fail(f"boundary entry {from_entry_id!r} is not on the native active path")
    if latest is not None and from_entry_id == latest.resume_after_entry_id:
        return TailBoundary(
            from_entry_id,
            positions[latest.entry.identifier],
            next_pass_number,
        )
    if latest is not None and explicit_position <= positions[latest.entry.identifier]:
        raise fail(
            f"boundary entry {from_entry_id!r} is not after the latest smart-compact watermark"
        )
    if active[explicit_position].data.get("customType") == WATERMARK_TYPE:
        raise fail("use a watermark's resume_after_entry_id, not its custom entry id")
    return TailBoundary(from_entry_id, explicit_position, next_pass_number)


def message_data(line: SessionLine) -> dict[str, object] | None:
    if line.data.get("type") != "message":
        return None
    message = line.data.get("message")
    return message if isinstance(message, dict) else None


def native_tools(active: list[SessionLine]) -> list[NativeToolOccurrence]:
    """Pair native calls and results through active-path execution order."""
    calls: list[NativeToolCall] = []
    pending_calls: dict[str, list[NativeToolCall]] = {}
    paired_results: dict[tuple[str, int], NativeToolResult] = {}
    for line in active:
        message = message_data(line)
        if message is None:
            continue
        role = message.get("role")
        if role == "toolResult":
            tool_call_id = message.get("toolCallId")
            tool_name = message.get("toolName")
            if not isinstance(tool_call_id, str) or not isinstance(tool_name, str):
                raise fail(f"entry {line.identifier!r} contains a malformed toolResult")
            candidates = pending_calls.get(tool_call_id, [])
            if len(candidates) != 1:
                qualifier = "no" if not candidates else str(len(candidates))
                raise fail(
                    f"entry {line.identifier!r} has {qualifier} unmatched preceding "
                    f"toolCalls for toolCallId {tool_call_id!r}"
                )
            call = candidates.pop()
            if not names_match(call.name, tool_name):
                raise fail(
                    f"native tool occurrence {call.occurrence_key!r} changes name "
                    f"from {call.name!r} to {tool_name!r}"
                )
            paired_results[call.occurrence_key] = NativeToolResult(
                line,
                tool_call_id,
                tool_name,
            )
            continue
        if role != "assistant":
            continue
        content = message.get("content")
        if not isinstance(content, list):
            raise fail(f"assistant entry {line.identifier!r} has no content array")
        for content_index, block in enumerate(content):
            if not isinstance(block, dict) or block.get("type") != "toolCall":
                continue
            identifier = block.get("id")
            name = block.get("name")
            if not isinstance(identifier, str) or not isinstance(name, str):
                raise fail(f"entry {line.identifier!r} contains a malformed toolCall")
            call = NativeToolCall(line, content_index, identifier, name, block)
            calls.append(call)
            pending_calls.setdefault(identifier, []).append(call)
    return [
        NativeToolOccurrence(call, paired_results.get(call.occurrence_key))
        for call in calls
    ]


def split_tool_occurrence_keys(
    occurrences: list[NativeToolOccurrence],
    positions: dict[str, int],
    cutoff_index: int,
) -> list[tuple[str, int]]:
    """Return call occurrences whose paired results fall after the cutoff."""
    return [
        occurrence.call.occurrence_key
        for occurrence in occurrences
        if occurrence.result is not None
        and positions[occurrence.call.occurrence_key[0]]
        <= cutoff_index
        < positions[occurrence.result.entry.identifier]
    ]


def is_default_export_entry(line: SessionLine) -> bool:
    """Return whether default `ch` exports account for this native entry type.

    >>> is_default_export_entry(SessionLine('', {'type': 'message'}))
    True
    >>> is_default_export_entry(SessionLine('', {'type': 'custom'}))
    False
    """
    return line.data.get("type") in {"message", "compaction"}


def validate_source_tail(
    source_messages: list[dict[str, object]],
    active_tail: list[SessionLine],
) -> tuple[dict[int, SessionLine], set[str]]:
    """Map every source message to the ordered native active tail."""
    tail_by_identifier = {
        line.identifier: line
        for line in active_tail
        if line.identifier is not None
    }
    positions = {
        line.identifier: index
        for index, line in enumerate(active_tail)
        if line.identifier is not None
    }
    mapped: dict[int, SessionLine] = {}
    native_entry_ids: list[str] = []
    for message in source_messages:
        original_index = message.get("original_index")
        native_entry_id = message.get("native_entry_id")
        if not isinstance(original_index, int) or not isinstance(native_entry_id, str):
            raise fail(
                "every pruned Pi source message needs original_index and native_entry_id; "
                "export and prune the active tail again"
            )
        native_entry = tail_by_identifier.get(native_entry_id)
        if native_entry is None:
            raise fail(
                f"source message {original_index} is not after the resolved native boundary: "
                f"{native_entry_id!r}"
            )
        mapped[original_index] = native_entry
        native_entry_ids.append(native_entry_id)
    if len(native_entry_ids) != len(set(native_entry_ids)):
        raise fail("pruned Pi source repeats native_entry_id values")
    source_positions = [positions[identifier] for identifier in native_entry_ids]
    if source_positions != sorted(source_positions):
        raise fail("pruned Pi source messages do not follow native active-path order")
    return mapped, set(native_entry_ids)


def unmatched_tool_calls(
    events: list[SourceToolEvent],
    occurrences: list[NativeToolOccurrence],
) -> tuple[list[NativeToolOccurrence], list[NativeToolOccurrence]]:
    mapped_occurrence_keys = {
        event.native_occurrence.call.occurrence_key
        for event in events
        if event.native_occurrence is not None
    }
    unmatched = [
        occurrence
        for occurrence in occurrences
        if occurrence.call.occurrence_key not in mapped_occurrence_keys
    ]
    removable = [
        occurrence
        for occurrence in unmatched
        if canonical_tool_name(occurrence.call.name) == "todo"
        or (
            canonical_tool_name(occurrence.call.name)
            in {canonical_tool_name(name) for name in transcript_common.FILE_TOOLS}
            and occurrence.result is None
        )
    ]
    removable_keys = {
        occurrence.call.occurrence_key for occurrence in removable
    }
    unsafe = [
        occurrence
        for occurrence in unmatched
        if occurrence.call.occurrence_key not in removable_keys
    ]
    return removable, unsafe


def parse_file_reference(
    block: str,
) -> tuple[str, str, str, str | None, int | None] | None:
    try:
        element = xml.etree.ElementTree.fromstring(block.strip())
    except xml.etree.ElementTree.ParseError:
        return None
    if element.tag not in transcript_common.FILE_TOOLS or list(element):
        return None
    path = element.attrib.get("path")
    identifier = element.attrib.get("id")
    if not path or not identifier:
        return None
    native_identifier = element.attrib.get("native_tool_call_id")
    native_content_index_raw = element.attrib.get("native_content_index")
    native_content_index = (
        int(native_content_index_raw)
        if native_content_index_raw is not None
        and native_content_index_raw.isdecimal()
        else None
    )
    return element.tag, path, identifier, native_identifier, native_content_index


def source_tool_events(
    source_messages: list[dict[str, object]],
    compacted_messages: list[dict[str, object]],
    manifest: dict[str, object],
) -> tuple[list[SourceToolEvent], dict[int, list[str]]]:
    compacted_by_index = {
        message["original_index"]: message for message in compacted_messages
    }
    raw_replacements = manifest.get("replace_messages", [])
    if not isinstance(raw_replacements, list):
        raise fail("compaction plan replace_messages is malformed")
    replacements_by_index = {
        replacement["original_index"]: replacement
        for replacement in raw_replacements
        if isinstance(replacement, dict)
        and isinstance(replacement.get("original_index"), int)
    }
    events: list[SourceToolEvent] = []
    final_prose_by_index: dict[int, list[str]] = {}
    for source_message in source_messages:
        original_index = source_message["original_index"]
        if not isinstance(original_index, int):
            raise fail("source message has a non-integer original_index")
        source_content = source_message.get("content")
        if not isinstance(source_content, list):
            raise fail(f"source message {original_index} has no content array")
        compacted_message = compacted_by_index.get(original_index)
        final_content = (
            compacted_message.get("content", []) if compacted_message is not None else []
        )
        if not isinstance(final_content, list):
            raise fail(f"compacted message {original_index} has no content array")
        final_strings = [
            block
            for block in final_content
            if isinstance(block, str) and not apply_compaction_plan.is_footer(block)
        ]
        replacement = replacements_by_index.get(original_index)
        declared_skeletons = (
            apply_compaction_plan.replacement_tool_skeletons(
                replacement,
                source_message,
                original_index,
            )
            if replacement is not None
            else None
        )
        final_skeletons = [
            block for block in final_strings if apply_compaction_plan.is_tool_skeleton(block)
        ]
        if declared_skeletons is None and final_skeletons:
            raise fail(
                f"plan replacement at message {original_index} lacks exact "
                "tool_skeletons associations; regenerate the plan"
            )
        exact_skeletons = {
            association.source_content_index: association
            for association in declared_skeletons or []
        }
        nonnative_occurrences = [
            association.source_content_index
            for association in exact_skeletons.values()
            if association.native_entry_id is None
            or association.native_content_index is None
        ]
        if nonnative_occurrences:
            raise fail(
                f"plan replacement at message {original_index} lacks exact native "
                f"occurrences at source content indices {nonnative_occurrences}; "
                "regenerate from a current Pi export"
            )
        unplaced_skeleton_indices = set(exact_skeletons)
        final_cursor = 0
        native_entry_id = source_message.get("native_entry_id")
        previous_reference_event: SourceToolEvent | None = None
        final_prose: list[str] = []

        for source_content_index, block in enumerate(source_content):
            if isinstance(block, str):
                reference = parse_file_reference(block)
                kept = (
                    final_cursor < len(final_strings)
                    and final_strings[final_cursor] == block
                )
                if kept:
                    final_cursor += 1
                if reference is None:
                    if kept:
                        final_prose.append(block)
                    previous_reference_event = None
                    continue
                (
                    name,
                    _path,
                    _identifier,
                    native_identifier,
                    native_content_index,
                ) = reference
                if (
                    not isinstance(native_entry_id, str)
                    or native_identifier is None
                    or native_content_index is None
                ):
                    raise fail(
                        f"file reference in source message {original_index} lacks native provenance; "
                        "export it again with the current ch and prune it again"
                    )
                if (
                    previous_reference_event is not None
                    and previous_reference_event.native_identifier == native_identifier
                    and previous_reference_event.native_entry_id == native_entry_id
                    and previous_reference_event.native_content_index
                    == native_content_index
                ):
                    if kept:
                        previous_reference_event.replacements.append(block)
                    continue
                event = SourceToolEvent(
                    original_index=original_index,
                    name=name,
                    replacements=[block] if kept else [],
                    native_entry_id=native_entry_id,
                    native_identifier=native_identifier,
                    native_content_index=native_content_index,
                )
                events.append(event)
                previous_reference_event = event
                continue

            previous_reference_event = None
            if not isinstance(block, dict) or block.get("type") != "tool-input":
                continue
            identifier = block.get("id")
            name = block.get("name")
            if not isinstance(identifier, str) or not isinstance(name, str):
                raise fail(f"source message {original_index} has a malformed tool-input")
            native_identifier_raw = block.get("native_tool_call_id")
            native_content_index_raw = block.get("native_content_index")
            if (
                not isinstance(native_entry_id, str)
                or not isinstance(native_identifier_raw, str)
                or not isinstance(native_content_index_raw, int)
            ):
                raise fail(
                    f"tool-input in source message {original_index} lacks native provenance; "
                    "export it again with the current ch and prune it again"
                )
            association = exact_skeletons.get(source_content_index)
            skeleton = association.content if association is not None else None
            replacements: list[str] = []
            if skeleton is not None:
                if (
                    association is None
                    or association.tool_id != native_identifier_raw
                    or association.native_entry_id != native_entry_id
                    or association.native_content_index != native_content_index_raw
                ):
                    raise fail(
                        f"skeleton at message {original_index} source content index "
                        f"{source_content_index} has stale native occurrence provenance"
                    )
                if final_cursor >= len(final_strings) or final_strings[final_cursor] != skeleton:
                    raise fail(
                        f"skeleton for native tool {native_identifier_raw!r} is not at "
                        f"its source position in message {original_index}"
                    )
                replacements.append(skeleton)
                final_cursor += 1
                unplaced_skeleton_indices.remove(source_content_index)
            events.append(
                SourceToolEvent(
                    original_index=original_index,
                    name=name,
                    replacements=replacements,
                    native_entry_id=native_entry_id,
                    native_identifier=native_identifier_raw,
                    native_content_index=native_content_index_raw,
                )
            )

        if unplaced_skeleton_indices:
            raise fail(
                f"plan replacement at message {original_index} has unplaced skeleton "
                f"source content indices: {sorted(unplaced_skeleton_indices)}"
            )
        if final_cursor != len(final_strings):
            raise fail(
                f"plan replacement at message {original_index} cannot be aligned "
                "to its source blocks"
            )
        final_prose_by_index[original_index] = final_prose
    return events, final_prose_by_index


def canonical_tool_name(name: str) -> str:
    normalized = name.casefold().replace("-", "_")
    if normalized == "read_many_files":
        return "read"
    if normalized == "apply_patch":
        return "patch"
    return normalized


def names_match(source_name: str, native_name: str) -> bool:
    return canonical_tool_name(source_name) == canonical_tool_name(native_name)


def map_source_tools(
    events: list[SourceToolEvent],
    occurrences: list[NativeToolOccurrence],
) -> None:
    occurrences_by_key = {
        occurrence.call.occurrence_key: occurrence
        for occurrence in occurrences
    }
    for event in events:
        occurrence_key = (event.native_entry_id, event.native_content_index)
        occurrence = occurrences_by_key.get(occurrence_key)
        if occurrence is None:
            raise fail(
                f"source message {event.original_index} names missing native tool "
                f"occurrence {occurrence_key!r}"
            )
        call = occurrence.call
        if call.identifier != event.native_identifier:
            raise fail(
                f"source tool occurrence {occurrence_key!r} changed toolCallId from "
                f"{event.native_identifier!r} to {call.identifier!r}"
            )
        if not names_match(event.name, call.name):
            raise fail(
                f"source tool occurrence {occurrence_key!r} changed name from "
                f"{event.name!r} to {call.name!r}"
            )
        event.native_occurrence = occurrence


def output_text(block: dict[str, object]) -> str:
    content = block.get("content")
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    return "".join(
        part.get("text", "")
        for part in content
        if isinstance(part, dict) and isinstance(part.get("text"), str)
    )


def native_result_text(line: SessionLine) -> str:
    message = message_data(line)
    if message is None:
        return ""
    content = message.get("content")
    if not isinstance(content, list):
        return ""
    return "".join(
        block.get("text", "")
        for block in content
        if isinstance(block, dict) and isinstance(block.get("text"), str)
    )


def verify_source_outputs(
    source_messages: list[dict[str, object]],
    events: list[SourceToolEvent],
) -> None:
    events_by_result_entry_id = {
        event.native_occurrence.result.entry.identifier: event
        for event in events
        if event.native_occurrence is not None
        and event.native_occurrence.result is not None
    }
    seen_result_entry_ids: set[str] = set()
    for source_message in source_messages:
        original_index = source_message["original_index"]
        content = source_message.get("content", [])
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "tool-output":
                continue
            identifier = block.get("id")
            name = block.get("name")
            if not isinstance(identifier, str) or not isinstance(name, str):
                raise fail(f"source message {original_index} has a malformed tool-output")
            native_identifier = block.get("native_tool_call_id")
            if not isinstance(native_identifier, str):
                raise fail(
                    f"tool-output in source message {original_index} lacks native provenance; "
                    "export it again with the current ch and prune it again"
                )
            native_entry_id = source_message.get("native_entry_id")
            if not isinstance(native_entry_id, str):
                raise fail(
                    f"tool-output message {original_index} lacks native_entry_id; "
                    "export it again with the current ch and prune it again"
                )
            event = events_by_result_entry_id.get(native_entry_id)
            if event is None or event.native_occurrence is None:
                raise fail(
                    f"source tool-output {name} {identifier!r} has no mapped native occurrence"
                )
            if native_entry_id in seen_result_entry_ids:
                raise fail(f"source repeats native toolResult entry {native_entry_id!r}")
            seen_result_entry_ids.add(native_entry_id)
            if native_identifier != event.native_identifier:
                raise fail(
                    f"source tool-output occurrence {native_entry_id!r} changed toolCallId "
                    f"from {event.native_identifier!r} to {native_identifier!r}"
                )
            if not names_match(event.name, name):
                raise fail(
                    f"source tool-output occurrence {native_entry_id!r} has name {name!r}, "
                    f"but its input has {event.name!r}"
                )
            result = event.native_occurrence.result
            if result is None:
                raise fail(f"native tool occurrence {event.native_occurrence.call.occurrence_key!r} has no toolResult")
            expected = normalize(output_text(block))[:100]
            actual = normalize(native_result_text(result.entry))[:100]
            if expected and expected != actual:
                raise fail(
                    f"tool-output content mismatch at source message {original_index}: "
                    f"{expected[:60]!r} vs {actual[:60]!r}"
                )


def source_prose(message: dict[str, object]) -> list[str]:
    content = message.get("content")
    if not isinstance(content, list):
        return []
    return [
        block
        for block in content
        if isinstance(block, str) and parse_file_reference(block) is None
    ]


def native_text(line: SessionLine) -> list[str]:
    message = message_data(line)
    if message is None:
        return []
    content = message.get("content")
    if not isinstance(content, list):
        return []
    return [
        block["text"]
        for block in content
        if isinstance(block, dict)
        and block.get("type") == "text"
        and isinstance(block.get("text"), str)
    ]


def apply_text_changes(
    source_messages: list[dict[str, object]],
    final_prose_by_index: dict[int, list[str]],
    mapped_messages: dict[int, SessionLine],
    changed_indices: set[int],
) -> None:
    source_by_index = {
        message["original_index"]: message for message in source_messages
    }
    for original_index in sorted(changed_indices):
        source_message = source_by_index[original_index]
        original_prose = source_prose(source_message)
        final_prose = final_prose_by_index[original_index]
        if original_prose == final_prose:
            continue
        line = mapped_messages[original_index]
        message = message_data(line)
        if message is None or message.get("role") not in {"user", "assistant"}:
            raise fail(f"changed source message {original_index} is not native conversation text")
        content = message.get("content")
        if not isinstance(content, list):
            raise fail(f"native entry {line.identifier!r} has no content array")
        native_prose = native_text(line)
        original_joined = "".join(original_prose)
        native_joined = "".join(native_prose)
        if native_joined != original_joined and not native_joined.endswith(original_joined):
            raise fail(
                f"native text at source message {original_index} differs from the reviewed source"
            )

        changed_content: list[object] = []
        final_cursor = 0
        if native_prose == original_prose:
            for block in content:
                if not (
                    isinstance(block, dict)
                    and block.get("type") == "text"
                    and isinstance(block.get("text"), str)
                ):
                    changed_content.append(block)
                    continue
                if (
                    final_cursor < len(final_prose)
                    and block["text"] == final_prose[final_cursor]
                ):
                    changed_content.append(block)
                    final_cursor += 1
        else:
            first_text_written = False
            for block in content:
                if not (isinstance(block, dict) and block.get("type") == "text"):
                    changed_content.append(block)
                    continue
                if first_text_written:
                    continue
                changed_content.extend(
                    {"type": "text", "text": text} for text in final_prose
                )
                final_cursor = len(final_prose)
                first_text_written = True
        if final_cursor != len(final_prose):
            raise fail(
                f"plan text replacement at message {original_index} cannot be placed safely"
            )
        message["content"] = changed_content
        line.changed = True


def thinking_blocks(line: SessionLine) -> list[dict[str, object]]:
    message = message_data(line)
    if message is None:
        return []
    content = message.get("content")
    if not isinstance(content, list):
        return []
    return [
        block
        for block in content
        if isinstance(block, dict) and block.get("type") == "thinking"
    ]


def apply_tool_changes(
    active: list[SessionLine],
    events: list[SourceToolEvent],
    occurrences: list[NativeToolOccurrence],
    original_thinking: dict[str, list[dict[str, object]]],
) -> tuple[list[SessionLine], int]:
    mapped = {
        event.native_occurrence.call.occurrence_key: event
        for event in events
        if event.native_occurrence is not None
    }
    removable_unmatched, unsafe_unmatched = unmatched_tool_calls(
        events,
        occurrences,
    )
    if unsafe_unmatched:
        rendered = [
            f"{occurrence.call.name} {occurrence.call.occurrence_key!r}"
            for occurrence in unsafe_unmatched[:8]
        ]
        raise fail(f"native tools are absent from the pruned source: {rendered}")

    removed_occurrence_keys = set(mapped) | {
        occurrence.call.occurrence_key for occurrence in removable_unmatched
    }
    removed_entry_ids = {
        occurrence.result.entry.identifier
        for occurrence in occurrences
        if occurrence.call.occurrence_key in removed_occurrence_keys
        and occurrence.result is not None
        and occurrence.result.entry.identifier is not None
    }
    occurrences_by_block_identity = {
        id(occurrence.call.block): occurrence
        for occurrence in occurrences
    }

    for line in active:
        message = message_data(line)
        if message is None or message.get("role") != "assistant":
            continue
        content = message.get("content")
        if not isinstance(content, list):
            continue
        changed_content: list[object] = []
        changed = False
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "toolCall":
                changed_content.append(block)
                continue
            occurrence = occurrences_by_block_identity.get(id(block))
            if (
                occurrence is None
                or occurrence.call.occurrence_key not in removed_occurrence_keys
            ):
                changed_content.append(block)
                continue
            event = mapped.get(occurrence.call.occurrence_key)
            if event is not None:
                changed_content.extend(
                    {"type": "text", "text": replacement}
                    for replacement in event.replacements
                )
            changed = True
        if changed:
            message["content"] = changed_content
            line.changed = True

    for line in active:
        message = message_data(line)
        content = message.get("content") if message is not None else None
        if line.changed and isinstance(content, list) and not content:
            identifier = line.identifier
            if identifier is not None:
                removed_entry_ids.add(identifier)

    survivors = [
        line for line in active if line.identifier not in removed_entry_ids
    ]
    if not survivors:
        raise fail("compaction removed every native tree entry")
    removed_thinking = {
        identifier
        for identifier in removed_entry_ids
        if original_thinking.get(identifier)
    }
    if removed_thinking:
        raise fail(f"compaction would remove thinking entries: {sorted(removed_thinking)}")
    for line in survivors:
        identifier = line.identifier
        if identifier is None:
            continue
        if thinking_blocks(line) != original_thinking[identifier]:
            raise fail(f"thinking blocks changed in native entry {identifier!r}")
    return survivors, len(removed_entry_ids)


def render_rechained(header: SessionLine, survivors: list[SessionLine]) -> list[str]:
    rendered = [header.raw]
    previous_identifier: str | None = None
    for line in survivors:
        expected_parent = previous_identifier
        if line.data.get("parentId") != expected_parent:
            line.data["parentId"] = expected_parent
            line.changed = True
        rendered.append(
            json.dumps(line.data, ensure_ascii=False) if line.changed else line.raw
        )
        previous_identifier = line.identifier
    return rendered


def verify_complete_reviewed_tail(
    active_tail: list[SessionLine],
    source_entry_ids: set[str],
    events: list[SourceToolEvent],
    removable_unmatched: list[NativeToolOccurrence],
) -> str:
    """Require the pruned source to account for every export-visible tail entry."""
    reviewed_entry_ids = set(source_entry_ids)
    for event in events:
        occurrence = event.native_occurrence
        if (
            occurrence is not None
            and occurrence.result is not None
            and occurrence.result.entry.identifier is not None
        ):
            reviewed_entry_ids.add(occurrence.result.entry.identifier)
    for occurrence in removable_unmatched:
        if occurrence.call.entry.identifier is not None:
            reviewed_entry_ids.add(occurrence.call.entry.identifier)
        if occurrence.result is not None and occurrence.result.entry.identifier is not None:
            reviewed_entry_ids.add(occurrence.result.entry.identifier)

    visible_tail = [
        line.identifier
        for line in active_tail
        if line.identifier is not None
        and (is_default_export_entry(line) or line.identifier in source_entry_ids)
    ]
    unreviewed = [
        identifier
        for identifier in visible_tail
        if identifier not in reviewed_entry_ids
    ]
    if unreviewed:
        raise fail(
            "pruned source does not cover the complete native tail; re-export and prune: "
            f"{unreviewed[:8]}"
        )
    if not visible_tail:
        raise fail("native tail has no export-visible messages to compact")
    return visible_tail[-1]


def latest_resume_anchor(
    survivors: list[SessionLine],
    source_entry_ids: set[str],
    prior_resume_after_entry_id: str | None,
) -> str:
    for line in reversed(survivors):
        identifier = line.identifier
        if identifier in source_entry_ids:
            return identifier
    if prior_resume_after_entry_id is not None:
        return prior_resume_after_entry_id
    for line in reversed(survivors):
        if is_default_export_entry(line) and line.identifier is not None:
            return line.identifier
    raise fail("compaction left no export-visible message for the next tail boundary")


def new_watermark(
    header: SessionLine,
    survivors: list[SessionLine],
    resume_after_entry_id: str,
    source_through_entry_id: str,
    pass_number: int,
    stats: dict[str, int],
) -> SessionLine:
    existing_identifiers = {
        line.identifier for line in survivors if line.identifier is not None
    }
    identifier = secrets.token_hex(4)
    while identifier in existing_identifiers:
        identifier = secrets.token_hex(4)
    parent_identifier = survivors[-1].identifier
    if parent_identifier is None:
        raise fail("cannot attach a watermark to an entry without an id")
    session_id = header.data.get("id")
    if not isinstance(session_id, str):
        raise fail("native session header has no string id")
    data: dict[str, object] = {
        "type": "custom",
        "customType": WATERMARK_TYPE,
        "display": False,
        "id": identifier,
        "parentId": parent_identifier,
        "timestamp": datetime.datetime.now(datetime.UTC).isoformat().replace("+00:00", "Z"),
        "data": {
            "version": 1,
            "session_id": session_id,
            "resume_after_entry_id": resume_after_entry_id,
            "source_through_entry_id": source_through_entry_id,
            "pass": pass_number,
            "stats": stats,
        },
    }
    return SessionLine("", data, changed=True)


def validate_result(lines: list[str]) -> None:
    parsed = [json.loads(line) for line in lines]
    if len(parsed) < 2 or parsed[0].get("type") != "session":
        raise fail("output has no session header or tree")
    tree = parsed[1:]
    roots = [entry for entry in tree if entry.get("parentId") is None]
    if len(roots) != 1:
        raise fail(f"output has {len(roots)} roots instead of one")
    previous_identifier: str | None = None
    for entry in tree:
        if entry.get("parentId") != previous_identifier:
            raise fail(f"output chain breaks at entry {entry.get('id')!r}")
        identifier = entry.get("id")
        if not isinstance(identifier, str):
            raise fail("output tree entry has no string id")
        previous_identifier = identifier
    session_lines = [
        SessionLine(lines[index + 1], entry)
        for index, entry in enumerate(tree)
    ]
    unpaired = [
        occurrence.call.occurrence_key
        for occurrence in native_tools(session_lines)
        if occurrence.result is None
    ]
    if unpaired:
        raise fail(f"tool pairing is broken for call occurrences: {unpaired[:8]}")


def next_backup_path(jsonl_path: Path) -> Path:
    for number in range(1000):
        candidate = jsonl_path.with_name(jsonl_path.name + f".backup-{number}")
        if not candidate.exists():
            return candidate
    raise fail("more than 1000 backups exist")


def atomic_write(path: Path, lines: list[str]) -> None:
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            output.write("\n".join(lines) + "\n")
            output.flush()
            os.fsync(output.fileno())
        os.chmod(temporary_path, path.stat().st_mode)
        os.replace(temporary_path, path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def apply_native_plan(
    source_bytes: bytes,
    manifest: dict[str, object],
    session_path: Path,
    from_entry_id: str | None = None,
) -> tuple[list[str], dict[str, int]]:
    source_messages = apply_compaction_plan.load_messages(source_bytes)
    compacted_messages = apply_compaction_plan.apply_plan(source_bytes, manifest)
    header, active = parse_session(session_path)
    boundary = resolve_tail_boundary(header, active, from_entry_id)
    active_positions = {
        line.identifier: index
        for index, line in enumerate(active)
        if line.identifier is not None
    }
    all_occurrences = native_tools(active)
    split_occurrences = split_tool_occurrence_keys(
        all_occurrences,
        active_positions,
        boundary.native_cutoff_index,
    )
    if split_occurrences:
        raise fail(
            "native boundary splits tool call/result pairs at call occurrences: "
            f"{split_occurrences}"
        )
    prefix = active[: boundary.native_cutoff_index + 1]
    active_tail = active[boundary.native_cutoff_index + 1 :]
    mapped_source_messages, source_entry_ids = validate_source_tail(
        source_messages,
        active_tail,
    )
    occurrences = [
        occurrence
        for occurrence in all_occurrences
        if active_positions[occurrence.call.entry.identifier]
        > boundary.native_cutoff_index
    ]
    original_thinking = {
        line.identifier: thinking_blocks(line)
        for line in active_tail
        if line.identifier is not None
    }
    events, final_prose_by_index = source_tool_events(
        source_messages, compacted_messages, manifest
    )
    map_source_tools(events, occurrences)
    verify_source_outputs(source_messages, events)
    removable_unmatched, unsafe_unmatched = unmatched_tool_calls(
        events,
        occurrences,
    )
    if unsafe_unmatched:
        rendered_unsafe = [
            f"{occurrence.call.name} {occurrence.call.occurrence_key!r}"
            for occurrence in unsafe_unmatched[:8]
        ]
        raise fail(f"native tools are absent from the pruned source: {rendered_unsafe}")
    source_through_entry_id = verify_complete_reviewed_tail(
        active_tail,
        source_entry_ids,
        events,
        removable_unmatched,
    )
    drop_messages = manifest.get("drop_messages", [])
    replace_messages = manifest.get("replace_messages", [])
    if not isinstance(drop_messages, list) or not isinstance(replace_messages, list):
        raise fail("compaction plan drop_messages or replace_messages is malformed")
    changed_indices = {
        index for index in drop_messages if isinstance(index, int)
    } | {
        replacement["original_index"]
        for replacement in replace_messages
        if isinstance(replacement, dict)
        and isinstance(replacement.get("original_index"), int)
    }
    source_by_index = {
        message["original_index"]: message for message in source_messages
    }
    text_changed_indices = {
        index
        for index in changed_indices
        if source_prose(source_by_index[index]) != final_prose_by_index[index]
    }
    mapped_messages = {
        index: mapped_source_messages[index]
        for index in text_changed_indices
    }
    apply_text_changes(
        source_messages,
        final_prose_by_index,
        mapped_messages,
        text_changed_indices,
    )
    tail_survivors, removed_entries = apply_tool_changes(
        active_tail, events, occurrences, original_thinking
    )
    survivors = prefix + tail_survivors
    stats = {
        "messages": len(source_messages),
        "active_entries": len(active_tail),
        "tool_calls_replaced": sum(bool(event.replacements) for event in events),
        "tool_calls_dropped": sum(not event.replacements for event in events),
        "entries_removed": removed_entries,
        "survivors": len(tail_survivors),
    }
    resume_after_entry_id = latest_resume_anchor(
        survivors,
        source_entry_ids,
        boundary.resume_after_entry_id,
    )
    watermark = new_watermark(
        header,
        survivors,
        resume_after_entry_id,
        source_through_entry_id,
        boundary.next_pass_number,
        stats,
    )
    rendered = render_rechained(header, survivors + [watermark])
    protected_raw = [header.raw] + [line.raw for line in prefix]
    if rendered[: len(protected_raw)] != protected_raw:
        raise fail("compaction changed native lines at or before the tail boundary")
    validate_result(rendered)
    return rendered, stats


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("pruned_json", type=Path)
    parser.add_argument("compaction_plan_json", type=Path)
    parser.add_argument("session_copy_jsonl", type=Path)
    parser.add_argument(
        "--from-entry-id",
        help="compact active Pi entries strictly after this native entry",
    )
    arguments = parser.parse_args()

    source_bytes = arguments.pruned_json.read_bytes()
    manifest_raw = json.loads(
        arguments.compaction_plan_json.read_text(encoding="utf-8")
    )
    if not isinstance(manifest_raw, dict):
        raise fail("compaction plan must be a JSON object")
    original_bytes = arguments.session_copy_jsonl.read_bytes()
    rendered, stats = apply_native_plan(
        source_bytes,
        manifest_raw,
        arguments.session_copy_jsonl,
        arguments.from_entry_id,
    )
    if arguments.session_copy_jsonl.read_bytes() != original_bytes:
        raise fail("native target changed during validation; rerun against a stable copy")

    backup = next_backup_path(arguments.session_copy_jsonl)
    backup.write_bytes(original_bytes)
    if backup.read_bytes() != original_bytes:
        raise fail("backup verification failed")
    atomic_write(arguments.session_copy_jsonl, rendered)

    output_bytes = arguments.session_copy_jsonl.stat().st_size
    print(
        json.dumps(
            {
                "backup": str(backup),
                "source_bytes": len(original_bytes),
                "output_bytes": output_bytes,
                "stats": stats,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
