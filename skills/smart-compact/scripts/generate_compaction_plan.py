#!/usr/bin/env -S uv run
# /// script
# requires-python = "==3.12.*"
# dependencies = []
# ///
"""Generate a complete compaction plan from semantic decisions only.

Reads the pruned transcript plus a semantic decisions file and emits a plan
ready for apply_compaction_plan.py, deriving every mechanical field: the
checksum, the raw-tool drop set, skeleton replacement entries with their tool
IDs, and affected-file provenance. Prints a concise audit to stderr.
Raises on unresolved blocks, invalid anchors, conflicting decisions, and
artifact-extractor failures.
"""

import argparse
import collections
import dataclasses
import hashlib
import json
import pathlib
import re
import sys
import xml.sax.saxutils

import apply_compaction_plan
import transcript_common


ARTIFACT_TOOLS = frozenset({"generate_visual", "lumen-generate_visual"})
ARTIFACT_PATH_PATTERN = re.compile(r"/[^\s\"'<>()\[\]]+\.(?:html|pdf|png|svg|pptx)\b")
SKELETON_ATTRIBUTES = ("name", "command", "purpose", "outcome", "meaning")


@dataclasses.dataclass
class SkeletonDeclaration:
    original_index: int
    command: str
    purpose: str
    outcome: str
    meaning: str | None = None
    tool_id: str | None = None
    name: str | None = None


@dataclasses.dataclass(frozen=True)
class FileReferenceDecision:
    original_index: int
    operation: str
    path: str


@dataclasses.dataclass
class Decisions:
    source_sha256: str | None
    drop_texts: list[int]
    drop_text_blocks: list[tuple[int, str]]
    drop_file_references: list[FileReferenceDecision]
    skeletons: list[SkeletonDeclaration]
    scratchpad_paths: list[str]
    opaque_artifacts: list[str]


def render_skeleton(attributes: dict[str, str]) -> str:
    """Serialize a tool-skeleton element with safe XML attribute escaping.

    >>> render_skeleton({'name': 'Bash', 'command': 'pytest', 'purpose': 'Validate', 'outcome': '12 passed'})
    '<tool-skeleton name="Bash" command="pytest" purpose="Validate" outcome="12 passed"/>'
    """
    rendered = " ".join(
        f"{key}={xml.sax.saxutils.quoteattr(attributes[key])}"
        for key in SKELETON_ATTRIBUTES
        if attributes.get(key)
    )
    return f"<tool-skeleton {rendered}/>"


def make_text_blocks_adjacent(content: list[object]) -> list[object]:
    """Group strings without changing structured block values or relative order.

    >>> make_text_blocks_adjacent(['before', {'type': 'thinking'}, 'after'])
    ['before', 'after', {'type': 'thinking'}]
    """
    first_text_index = next(
        (index for index, block in enumerate(content) if isinstance(block, str)),
        len(content),
    )
    return (
        content[:first_text_index]
        + [block for block in content[first_text_index:] if isinstance(block, str)]
        + [block for block in content[first_text_index:] if not isinstance(block, str)]
    )


def output_text(block: dict[str, object]) -> str:
    """Collect the text of a tool-output block across known transcript shapes.

    >>> output_text({'content': [{'type': 'text', 'text': 'a'}, {'type': 'text', 'text': 'b'}]})
    'ab'
    >>> output_text({'content': 'plain'})
    'plain'
    """
    content = block.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            part.get("text", "")
            for part in content
            if isinstance(part, dict) and part.get("type") == "text"
        )
    return ""


def parse_decisions(raw: dict[str, object]) -> Decisions:
    known_keys = {
        "source_sha256",
        "drop_texts",
        "drop_text_blocks",
        "drop_file_references",
        "skeletons",
        "scratchpad_paths",
        "opaque_artifacts",
    }
    unknown = sorted(set(raw) - known_keys)
    if unknown:
        raise ValueError(f"unknown decision keys: {unknown}")

    source_sha256 = raw.get("source_sha256")
    if source_sha256 is not None and (
        not isinstance(source_sha256, str)
        or re.fullmatch(r"[0-9a-f]{64}", source_sha256) is None
    ):
        raise ValueError("source_sha256 must be a lowercase SHA-256 digest")

    drop_texts = raw.get("drop_texts", [])
    if not isinstance(drop_texts, list) or not all(isinstance(index, int) for index in drop_texts):
        raise ValueError("drop_texts must be an integer array")

    drop_text_blocks: list[tuple[int, str]] = []
    for entry in raw.get("drop_text_blocks", []):
        if not isinstance(entry, dict) or not isinstance(entry.get("original_index"), int) or not isinstance(entry.get("contains"), str) or not entry["contains"]:
            raise ValueError(f"drop_text_blocks entry needs original_index and non-empty contains: {entry!r}")
        drop_text_blocks.append((entry["original_index"], entry["contains"]))

    drop_file_references: list[FileReferenceDecision] = []
    for entry in raw.get("drop_file_references", []):
        if (
            not isinstance(entry, dict)
            or set(entry) != {"original_index", "operation", "path"}
            or not isinstance(entry.get("original_index"), int)
            or entry.get("operation") not in transcript_common.FILE_TOOLS
            or not isinstance(entry.get("path"), str)
            or not entry["path"]
        ):
            raise ValueError(
                "drop_file_references entries need exactly original_index, "
                f"operation, and non-empty path: {entry!r}"
            )
        drop_file_references.append(FileReferenceDecision(**entry))

    skeletons: list[SkeletonDeclaration] = []
    for entry in raw.get("skeletons", []):
        if not isinstance(entry, dict):
            raise ValueError(f"skeleton entry must be an object: {entry!r}")
        try:
            skeletons.append(SkeletonDeclaration(**entry))
        except TypeError as error:
            raise ValueError(f"invalid skeleton entry {entry!r}: {error}") from error
        if not isinstance(entry.get("original_index"), int):
            raise ValueError(f"skeleton entry needs an integer original_index: {entry!r}")
        if entry.get("tool_id") is not None and (
            not isinstance(entry["tool_id"], str) or not entry["tool_id"]
        ):
            raise ValueError(
                f"skeleton at index {entry.get('original_index')!r} has invalid tool_id"
            )
        for field in ("command", "purpose", "outcome"):
            if not isinstance(entry.get(field), str) or not entry[field]:
                raise ValueError(f"skeleton at index {entry.get('original_index')!r} missing {field}")

    for key in ("scratchpad_paths", "opaque_artifacts"):
        values = raw.get(key, [])
        if not isinstance(values, list) or not all(isinstance(path, str) and path for path in values):
            raise ValueError(f"{key} must be an array of non-empty strings")

    return Decisions(
        source_sha256=source_sha256,
        drop_texts=drop_texts,
        drop_text_blocks=drop_text_blocks,
        drop_file_references=drop_file_references,
        skeletons=skeletons,
        scratchpad_paths=list(raw.get("scratchpad_paths", [])),
        opaque_artifacts=list(raw.get("opaque_artifacts", [])),
    )


def resolve_anchors(
    decisions: Decisions, messages_by_index: dict[int, dict[str, object]]
) -> dict[int, SkeletonDeclaration]:
    """Map python object ids of anchored tool-input blocks to their declarations."""
    anchors: dict[int, SkeletonDeclaration] = {}
    for declaration in decisions.skeletons:
        message = messages_by_index.get(declaration.original_index)
        if message is None:
            raise ValueError(f"skeleton anchor {declaration.original_index} not in transcript")
        content = message.get("content", [])
        tool_inputs = [
            block
            for block in content
            if isinstance(block, dict) and block.get("type") == "tool-input"
        ]
        if not tool_inputs:
            raise ValueError(f"skeleton anchor {declaration.original_index} has no tool-input block")
        if declaration.tool_id is None and len(tool_inputs) > 1:
            available = [
                block.get("native_tool_call_id") or block.get("id")
                for block in tool_inputs
            ]
            raise ValueError(
                f"skeleton anchor {declaration.original_index} is ambiguous; "
                f"specify tool_id from {available}"
            )
        if declaration.tool_id is None:
            block = tool_inputs[0]
        else:
            matches = [
                block
                for block in tool_inputs
                if declaration.tool_id
                in {block.get("id"), block.get("native_tool_call_id")}
            ]
            if len(matches) != 1:
                raise ValueError(
                    f"skeleton anchor {declaration.original_index} tool_id "
                    f"{declaration.tool_id!r} matches {len(matches)} blocks"
                )
            block = matches[0]
        if id(block) in anchors:
            raise ValueError(
                f"two skeletons anchor the same block in message {declaration.original_index}"
            )
        anchors[id(block)] = declaration
    return anchors


def collect_provenance(
    messages: list[dict[str, object]], decisions: Decisions
) -> list[tuple[str, str]]:
    """Ordered, deduplicated (path, provenance category) pairs for the footer."""
    scratchpad_identities = {
        transcript_common.path_identity(path) for path in decisions.scratchpad_paths
    }
    collected: dict[str, tuple[str, str]] = {}
    referenced_identities: set[str] = set()
    for message in messages:
        for block in message.get("content", []):
            if isinstance(block, str):
                path = transcript_common.reference_path(block)
                if path is None:
                    continue
                identity = transcript_common.path_identity(path)
                referenced_identities.add(identity)
                if identity not in scratchpad_identities and identity not in collected:
                    collected[identity] = (path, "file reference")
                continue
            if not isinstance(block, dict) or block.get("type") != "tool-output":
                continue
            tool_name = block.get("name")
            if tool_name not in ARTIFACT_TOOLS:
                continue
            artifact_paths = [
                "/" + match.lstrip("/")
                for match in ARTIFACT_PATH_PATTERN.findall(output_text(block))
            ]
            if not artifact_paths:
                raise ValueError(
                    f"artifact tool {tool_name!r} in message {message.get('original_index')} "
                    "produced no extractable path"
                )
            for path in artifact_paths:
                identity = transcript_common.path_identity(path)
                if identity not in scratchpad_identities and identity not in collected:
                    collected[identity] = (path, f"artifact ({tool_name})")

    unreferenced_scratchpads = sorted(
        path
        for path in decisions.scratchpad_paths
        if transcript_common.path_identity(path) not in referenced_identities
    )
    if unreferenced_scratchpads:
        raise ValueError(f"scratchpad paths never referenced in transcript: {unreferenced_scratchpads}")

    for path in decisions.opaque_artifacts:
        identity = transcript_common.path_identity(path)
        if identity not in collected:
            collected[identity] = (path, "opaque artifact")
    return list(collected.values())


def generate_plan(
    source_bytes: bytes, decisions: Decisions
) -> tuple[dict[str, object], list[str]]:
    source_sha256 = hashlib.sha256(source_bytes).hexdigest()
    if decisions.source_sha256 is not None and decisions.source_sha256 != source_sha256:
        raise ValueError(
            "annotation source checksum mismatch: "
            f"expected {decisions.source_sha256}, got {source_sha256}"
        )
    messages = apply_compaction_plan.load_messages(source_bytes)
    messages_by_index = {message["original_index"]: message for message in messages}

    missing_drop_texts = sorted(set(decisions.drop_texts) - set(messages_by_index))
    if missing_drop_texts:
        raise ValueError(f"drop_texts references missing indices: {missing_drop_texts}")
    anchors = resolve_anchors(decisions, messages_by_index)
    anchor_indices = {declaration.original_index for declaration in decisions.skeletons}
    marked_removals = {
        message["original_index"] for message in messages if message.get("remove") is True
    }
    whole_message_drops = set(decisions.drop_texts) | marked_removals
    conflicts = sorted(whole_message_drops & anchor_indices)
    if conflicts:
        raise ValueError(f"messages both dropped and skeleton-anchored: {conflicts}")

    scratchpad_identities = {
        transcript_common.path_identity(path) for path in decisions.scratchpad_paths
    }
    file_reference_drops = set(decisions.drop_file_references)
    matched_file_reference_drops: collections.Counter[FileReferenceDecision] = collections.Counter()
    block_drops_by_index: dict[int, list[str]] = collections.defaultdict(list)
    for index, substring in decisions.drop_text_blocks:
        if index not in messages_by_index:
            raise ValueError(f"drop_text_blocks references missing index {index}")
        block_drops_by_index[index].append(substring)

    drop_messages: list[int] = []
    replace_messages: list[dict[str, object]] = []
    dropped_tool_counts: collections.Counter[str] = collections.Counter()
    mixed_normalized: list[int] = []
    kept_untouched = 0
    matched_substrings: set[tuple[int, str]] = set()

    for message in messages:
        index = message["original_index"]
        drop_message_text = index in whole_message_drops
        original_content = message.get("content")
        if not isinstance(original_content, list):
            raise ValueError(f"message {index} has no content array")

        new_content: list[object] = []
        tool_skeletons: list[dict[str, object]] = []
        changed = False
        had_prose = False
        had_tools = False
        for source_content_index, block in enumerate(original_content):
            if isinstance(block, str):
                had_prose = True
                if drop_message_text:
                    changed = True
                    continue
                reference = transcript_common.file_reference(block)
                path = reference[1] if reference is not None else None
                if (
                    path is not None
                    and transcript_common.path_identity(path) in scratchpad_identities
                ):
                    changed = True
                    continue
                file_reference_decision = (
                    FileReferenceDecision(index, *reference)
                    if reference is not None
                    else None
                )
                if file_reference_decision in file_reference_drops:
                    matched_file_reference_drops[file_reference_decision] += 1
                    changed = True
                    continue
                matching = [s for s in block_drops_by_index.get(index, []) if s in block]
                if matching:
                    matched_substrings.update((index, s) for s in matching)
                    changed = True
                    continue
                new_content.append(block)
                continue
            if (
                not isinstance(block, dict)
                or not isinstance(block.get("type"), str)
                or not block["type"]
            ):
                raise ValueError(f"message {index} contains an unresolved structured block: {block!r}")
            if block["type"] not in {"tool-input", "tool-output"}:
                new_content.append(block)
                continue
            if not block.get("name"):
                raise ValueError(f"message {index} contains an unresolved structured block: {block!r}")
            had_tools = True
            changed = True
            declaration = anchors.get(id(block))
            if declaration is None:
                dropped_tool_counts[str(block["name"])] += 1
                continue
            skeleton = render_skeleton({
                    "name": declaration.name or str(block["name"]),
                    "command": declaration.command,
                    "purpose": declaration.purpose,
                    "outcome": declaration.outcome,
                    "meaning": declaration.meaning or "",
                })
            new_content.append(skeleton)
            tool_identifier = block.get("native_tool_call_id") or block.get("id")
            if not isinstance(tool_identifier, str) or not tool_identifier:
                raise ValueError(
                    f"skeleton anchor {index} has no tool identifier"
                )
            tool_skeletons.append({"tool_id": tool_identifier, "content": skeleton})
            tool_skeleton = tool_skeletons[-1]
            tool_skeleton["source_content_index"] = source_content_index
            native_entry_id = message.get("native_entry_id")
            native_content_index = block.get("native_content_index")
            has_native_provenance = any(
                value is not None
                for value in (
                    block.get("native_tool_call_id"),
                    native_entry_id,
                    native_content_index,
                )
            )
            if has_native_provenance and not (
                isinstance(block.get("native_tool_call_id"), str)
                and isinstance(native_entry_id, str)
                and isinstance(native_content_index, int)
            ):
                raise ValueError(
                    f"skeleton anchor {index} has incomplete native occurrence provenance"
                )
            if has_native_provenance:
                tool_skeleton["native_entry_id"] = native_entry_id
                tool_skeleton["native_content_index"] = native_content_index

        normalized_content = make_text_blocks_adjacent(new_content)
        text_blocks_normalized = normalized_content != new_content
        new_content = normalized_content
        changed = changed or text_blocks_normalized
        if not new_content:
            drop_messages.append(index)
            continue
        if not changed:
            kept_untouched += 1
            continue
        if (had_prose and had_tools) or text_blocks_normalized:
            mixed_normalized.append(index)
        replacement: dict[str, object] = {
            "original_index": index,
            "expected_tool_ids": sorted(apply_compaction_plan.tool_ids(message)),
            "content": new_content,
        }
        if tool_skeletons:
            replacement["tool_skeletons"] = tool_skeletons
        replace_messages.append(replacement)

    invalid_file_reference_drops = [
        (decision, matched_file_reference_drops[decision])
        for decision in decisions.drop_file_references
        if matched_file_reference_drops[decision] != 1
    ]
    if invalid_file_reference_drops:
        details = ", ".join(
            f"{decision.original_index} {decision.operation} {decision.path!r} "
            f"matched {match_count}"
            for decision, match_count in invalid_file_reference_drops
        )
        raise ValueError(f"drop_file_references must match exactly one block: {details}")

    unmatched = sorted(set(decisions.drop_text_blocks) - matched_substrings)
    if unmatched:
        raise ValueError(f"drop_text_blocks matched no string block: {unmatched}")

    provenance = collect_provenance(messages, decisions)
    plan: dict[str, object] = {
        "version": 2,
        "source_sha256": source_sha256,
        "drop_messages": sorted(drop_messages),
        "replace_messages": replace_messages,
        "affected_files_extra": [path for path, _ in provenance],
    }

    tool_summary = ", ".join(f"{name}×{count}" for name, count in dropped_tool_counts.most_common())
    audit = [
        f"inferred raw-tool removals: {sum(dropped_tool_counts.values())} blocks ({tool_summary or 'none'})",
        f"mixed-content messages normalized: {mixed_normalized or 'none'}",
        "skeleton anchors: "
        + (", ".join(str(d.original_index) for d in decisions.skeletons) or "none"),
        f"explicit text drops: {sorted(decisions.drop_texts) or 'none'}"
        + (f"; marked removals: {sorted(marked_removals)}" if marked_removals else ""),
        f"text block drops: {sorted(matched_substrings) or 'none'}",
        "file reference drops: "
        + (
            ", ".join(
                f"{decision.original_index} {decision.operation} {decision.path}"
                for decision in sorted(
                    matched_file_reference_drops,
                    key=lambda decision: (
                        decision.original_index,
                        decision.operation,
                        decision.path,
                    ),
                )
            )
            or "none"
        ),
        f"scratchpad exclusions: {sorted(decisions.scratchpad_paths) or 'none'}",
        "affected files: "
        + ("; ".join(f"{path} [{category}]" for path, category in provenance) or "none"),
        f"messages: {len(messages)} total → {kept_untouched} untouched, "
        f"{len(replace_messages)} replaced, {len(drop_messages)} dropped",
    ]
    return plan, audit


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pruned_json", type=pathlib.Path)
    parser.add_argument("decisions_json", type=pathlib.Path)
    arguments = parser.parse_args()

    source_bytes = arguments.pruned_json.read_bytes()
    raw_decisions = json.loads(arguments.decisions_json.read_text(encoding="utf-8"))
    if not isinstance(raw_decisions, dict):
        raise ValueError("decisions must be a JSON object")
    decisions = parse_decisions(raw_decisions)
    plan, audit = generate_plan(source_bytes, decisions)

    apply_compaction_plan.apply_plan(source_bytes, plan)

    json.dump(plan, sys.stdout, ensure_ascii=False, indent=2)
    print()
    print("\n".join(f"audit | {line}" for line in audit), file=sys.stderr)
    print("audit | plan verified against apply stage", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
