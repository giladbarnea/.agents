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
import json
import os
import re
import tempfile
import xml.etree.ElementTree
from pathlib import Path

import apply_compaction_plan
import transcript_common


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


@dataclasses.dataclass
class SourceToolEvent:
    original_index: int
    name: str
    replacements: list[str]
    native_entry_id: str
    native_identifier: str
    native_content_index: int
    native_call: NativeToolCall | None = None


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


def message_data(line: SessionLine) -> dict[str, object] | None:
    if line.data.get("type") != "message":
        return None
    message = line.data.get("message")
    return message if isinstance(message, dict) else None


def native_tools(
    active: list[SessionLine],
) -> tuple[list[NativeToolCall], dict[str, SessionLine]]:
    calls: list[NativeToolCall] = []
    results: dict[str, SessionLine] = {}
    for line in active:
        message = message_data(line)
        if message is None:
            continue
        role = message.get("role")
        if role == "toolResult":
            tool_call_id = message.get("toolCallId")
            if not isinstance(tool_call_id, str) or tool_call_id in results:
                raise fail(f"entry {line.identifier!r} has an invalid or duplicate toolCallId")
            results[tool_call_id] = line
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
            calls.append(NativeToolCall(line, content_index, identifier, name))
    if len({call.identifier for call in calls}) != len(calls):
        raise fail("native active path contains duplicate full toolCall ids")
    return calls, results


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
        source_tool_inputs = [
            block
            for block in source_content
            if isinstance(block, dict) and block.get("type") == "tool-input"
        ]
        final_skeletons = [
            block for block in final_strings if apply_compaction_plan.is_tool_skeleton(block)
        ]
        if declared_skeletons is None and final_skeletons:
            if len(source_tool_inputs) != 1 or len(final_skeletons) != 1:
                raise fail(
                    f"plan replacement at message {original_index} lacks exact "
                    "tool_skeletons associations; regenerate the plan"
                )
            legacy_tool_id = source_tool_inputs[0].get("native_tool_call_id")
            if not isinstance(legacy_tool_id, str):
                raise fail(
                    f"legacy skeleton at message {original_index} lacks native provenance; "
                    "regenerate the plan"
                )
            declared_skeletons = {legacy_tool_id: final_skeletons[0]}
        exact_skeletons = declared_skeletons or {}
        source_native_tool_ids = {
            identifier
            for block in source_tool_inputs
            for identifier in [block.get("native_tool_call_id")]
            if isinstance(identifier, str)
        }
        nonnative_ids = sorted(set(exact_skeletons) - source_native_tool_ids)
        if nonnative_ids:
            raise fail(
                f"plan replacement at message {original_index} does not use exact full "
                f"native tool IDs: {nonnative_ids}"
            )
        unplaced_skeleton_ids = set(exact_skeletons)
        final_cursor = 0
        native_entry_id = source_message.get("native_entry_id")
        previous_reference_event: SourceToolEvent | None = None
        final_prose: list[str] = []

        for block in source_content:
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
            skeleton = exact_skeletons.get(native_identifier_raw)
            replacements: list[str] = []
            if skeleton is not None:
                if final_cursor >= len(final_strings) or final_strings[final_cursor] != skeleton:
                    raise fail(
                        f"skeleton for native tool {native_identifier_raw!r} is not at "
                        f"its source position in message {original_index}"
                    )
                replacements.append(skeleton)
                final_cursor += 1
                unplaced_skeleton_ids.remove(native_identifier_raw)
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

        if unplaced_skeleton_ids:
            raise fail(
                f"plan replacement at message {original_index} has unplaced skeleton IDs: "
                f"{sorted(unplaced_skeleton_ids)}"
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


def map_source_tools(events: list[SourceToolEvent], calls: list[NativeToolCall]) -> None:
    calls_by_identifier = {call.identifier: call for call in calls}
    source_identifiers = [event.native_identifier for event in events]
    if len(source_identifiers) != len(set(source_identifiers)):
        raise fail("pruned source maps more than one tool event to the same native toolCall")
    for event in events:
        call = calls_by_identifier.get(event.native_identifier)
        if call is None:
            raise fail(
                f"source message {event.original_index} names missing native toolCall "
                f"{event.native_identifier!r}"
            )
        if call.entry.identifier != event.native_entry_id:
            raise fail(
                f"source message {event.original_index} points to native entry "
                f"{event.native_entry_id!r}, but its tool is in {call.entry.identifier!r}"
            )
        if call.content_index != event.native_content_index:
            raise fail(
                f"source tool {event.native_identifier!r} has stale native_content_index "
                f"{event.native_content_index}; native value is {call.content_index}"
            )
        if not names_match(event.name, call.name):
            raise fail(
                f"source tool {event.native_identifier!r} changed name from "
                f"{event.name!r} to {call.name!r}"
            )
        event.native_call = call


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
    results: dict[str, SessionLine],
) -> None:
    events_by_identifier = {event.native_identifier: event for event in events}
    seen_identifiers: set[str] = set()
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
            event = events_by_identifier.get(native_identifier)
            if event is None or event.native_call is None:
                raise fail(
                    f"source tool-output {name} {identifier!r} has no mapped tool-input"
                )
            if native_identifier in seen_identifiers:
                raise fail(f"source repeats tool-output {native_identifier!r}")
            seen_identifiers.add(native_identifier)
            if not names_match(event.name, name):
                raise fail(
                    f"source tool-output {native_identifier!r} has name {name!r}, "
                    f"but its input has {event.name!r}"
                )
            result = results.get(native_identifier)
            if result is None:
                raise fail(
                    f"native toolCall {native_identifier!r} has no toolResult"
                )
            native_entry_id = source_message.get("native_entry_id")
            if not isinstance(native_entry_id, str) or result.identifier != native_entry_id:
                raise fail(
                    f"source tool-output message {original_index} has stale native_entry_id"
                )
            expected = normalize(output_text(block))[:100]
            actual = normalize(native_result_text(result))[:100]
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


def map_source_messages(
    source_messages: list[dict[str, object]],
    active: list[SessionLine],
    required_indices: set[int],
) -> dict[int, SessionLine]:
    active_by_identifier = {
        line.identifier: line for line in active if line.identifier is not None
    }
    source_by_index = {
        message["original_index"]: message for message in source_messages
    }
    mapped: dict[int, SessionLine] = {}
    for original_index in required_indices:
        source_message = source_by_index[original_index]
        native_entry_id = source_message.get("native_entry_id")
        if not isinstance(native_entry_id, str):
            raise fail(
                f"changed source message {original_index} lacks native_entry_id; "
                "export it again with the current ch and prune it again"
            )
        native_entry = active_by_identifier.get(native_entry_id)
        if native_entry is None:
            raise fail(
                f"changed source message {original_index} names missing native entry "
                f"{native_entry_id!r}"
            )
        mapped[original_index] = native_entry
    return mapped


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
    calls: list[NativeToolCall],
    results: dict[str, SessionLine],
    original_thinking: dict[str, list[dict[str, object]]],
) -> tuple[list[SessionLine], int]:
    mapped = {
        event.native_call.identifier: event
        for event in events
        if event.native_call is not None
    }
    unmatched = [call for call in calls if call.identifier not in mapped]
    removable_unmatched = [
        call
        for call in unmatched
        if canonical_tool_name(call.name) == "todo"
        or (
            canonical_tool_name(call.name)
            in {canonical_tool_name(name) for name in transcript_common.FILE_TOOLS}
            and call.identifier not in results
        )
    ]
    unsafe_unmatched = [call for call in unmatched if call not in removable_unmatched]
    if unsafe_unmatched:
        rendered = [
            f"{call.name} {call.identifier!r}" for call in unsafe_unmatched[:8]
        ]
        raise fail(f"native tools are absent from the pruned source: {rendered}")

    removed_call_ids = set(mapped) | {
        call.identifier for call in removable_unmatched
    }
    removed_entry_ids = {
        result.identifier
        for identifier, result in results.items()
        if identifier in removed_call_ids and result.identifier is not None
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
            identifier = block.get("id")
            if not isinstance(identifier, str) or identifier not in removed_call_ids:
                changed_content.append(block)
                continue
            event = mapped.get(identifier)
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


def validate_result(lines: list[str]) -> None:
    parsed = [json.loads(line) for line in lines]
    if len(parsed) < 2 or parsed[0].get("type") != "session":
        raise fail("output has no session header or tree")
    tree = parsed[1:]
    roots = [entry for entry in tree if entry.get("parentId") is None]
    if len(roots) != 1:
        raise fail(f"output has {len(roots)} roots instead of one")
    previous_identifier: str | None = None
    calls: set[str] = set()
    results: set[str] = set()
    for entry in tree:
        if entry.get("parentId") != previous_identifier:
            raise fail(f"output chain breaks at entry {entry.get('id')!r}")
        identifier = entry.get("id")
        if not isinstance(identifier, str):
            raise fail("output tree entry has no string id")
        previous_identifier = identifier
        if entry.get("type") != "message" or not isinstance(entry.get("message"), dict):
            continue
        message = entry["message"]
        if message.get("role") == "toolResult":
            tool_call_id = message.get("toolCallId")
            if isinstance(tool_call_id, str):
                results.add(tool_call_id)
        elif message.get("role") == "assistant":
            content = message.get("content", [])
            if isinstance(content, list):
                calls.update(
                    block["id"]
                    for block in content
                    if isinstance(block, dict)
                    and block.get("type") == "toolCall"
                    and isinstance(block.get("id"), str)
                )
    if calls != results:
        raise fail(
            f"tool pairing is broken: {len(calls - results)} calls without results, "
            f"{len(results - calls)} results without calls"
        )


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
) -> tuple[list[str], dict[str, int]]:
    source_messages = apply_compaction_plan.load_messages(source_bytes)
    compacted_messages = apply_compaction_plan.apply_plan(source_bytes, manifest)
    header, active = parse_session(session_path)
    calls, results = native_tools(active)
    original_thinking = {
        line.identifier: thinking_blocks(line)
        for line in active
        if line.identifier is not None
    }
    events, final_prose_by_index = source_tool_events(
        source_messages, compacted_messages, manifest
    )
    map_source_tools(events, calls)
    verify_source_outputs(source_messages, events, results)
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
    mapped_messages = map_source_messages(
        source_messages,
        active,
        text_changed_indices,
    )
    apply_text_changes(
        source_messages,
        final_prose_by_index,
        mapped_messages,
        text_changed_indices,
    )
    survivors, removed_entries = apply_tool_changes(
        active, events, calls, results, original_thinking
    )
    rendered = render_rechained(header, survivors)
    validate_result(rendered)
    return rendered, {
        "active_entries": len(active),
        "tool_calls_replaced": sum(bool(event.replacements) for event in events),
        "tool_calls_dropped": sum(not event.replacements for event in events),
        "entries_removed": removed_entries,
        "survivors": len(survivors),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("pruned_json", type=Path)
    parser.add_argument("compaction_plan_json", type=Path)
    parser.add_argument("session_copy_jsonl", type=Path)
    arguments = parser.parse_args()

    source_bytes = arguments.pruned_json.read_bytes()
    manifest_raw = json.loads(
        arguments.compaction_plan_json.read_text(encoding="utf-8")
    )
    if not isinstance(manifest_raw, dict):
        raise fail("compaction plan must be a JSON object")
    original_bytes = arguments.session_copy_jsonl.read_bytes()
    rendered, stats = apply_native_plan(
        source_bytes, manifest_raw, arguments.session_copy_jsonl
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
