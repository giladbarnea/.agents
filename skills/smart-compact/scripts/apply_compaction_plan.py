#!/usr/bin/env -S uv run
# /// script
# requires-python = "==3.12.*"
# dependencies = []
# ///
"""Apply stable-index semantic decisions to a deterministically pruned transcript."""

import argparse
import hashlib
import json
import pathlib
import sys
import xml.etree.ElementTree

import transcript_common


def load_messages(data: bytes) -> list[dict[str, object]]:
    raw = json.loads(data)
    if not isinstance(raw, list) or not all(isinstance(message, dict) for message in raw):
        raise ValueError("source must be a JSON array of message objects")
    messages = [dict(message) for message in raw if isinstance(message, dict)]
    indices = [message.get("original_index") for message in messages]
    if not all(isinstance(index, int) for index in indices) or len(indices) != len(set(indices)):
        raise ValueError("source original_index values must be unique integers")
    return messages


def tool_ids(message: dict[str, object]) -> set[str]:
    content = message.get("content")
    if not isinstance(content, list):
        return set()
    return {
        identifier
        for block in content
        if isinstance(block, dict)
        for identifier in [block.get("id")]
        if isinstance(identifier, str)
    }


def is_footer(block: object) -> bool:
    return isinstance(block, str) and block.strip().startswith("<affected-files>")


def is_tool_skeleton(block: object) -> bool:
    if not isinstance(block, str):
        return False
    try:
        element = xml.etree.ElementTree.fromstring(block.strip())
    except xml.etree.ElementTree.ParseError:
        return False
    return element.tag == "tool-skeleton"


def replacement_tool_skeletons(
    replacement: dict[str, object],
    source_message: dict[str, object],
    original_index: int,
) -> dict[str, str] | None:
    """Validate and return exact tool-to-skeleton associations when present.

    >>> skeleton = '<tool-skeleton name="Bash" command="pytest" purpose="test" outcome="pass"/>'
    >>> replacement_tool_skeletons(
    ...     {'content': [skeleton], 'tool_skeletons': [{'tool_id': 'full', 'content': skeleton}]},
    ...     {'content': [{'type': 'tool-input', 'id': 'short', 'native_tool_call_id': 'full'}]},
    ...     4,
    ... )
    {'full': '<tool-skeleton name="Bash" command="pytest" purpose="test" outcome="pass"/>'}
    """
    raw = replacement.get("tool_skeletons")
    if raw is None:
        return None
    if not isinstance(raw, list) or not all(isinstance(item, dict) for item in raw):
        raise ValueError(f"replacement {original_index} tool_skeletons must be objects")

    associations: dict[str, str] = {}
    for item in raw:
        if set(item) != {"tool_id", "content"}:
            raise ValueError(
                f"replacement {original_index} tool_skeletons need exactly tool_id and content"
            )
        tool_id = item.get("tool_id")
        content = item.get("content")
        if not isinstance(tool_id, str) or not tool_id or not is_tool_skeleton(content):
            raise ValueError(
                f"replacement {original_index} has an invalid tool_skeleton association"
            )
        if tool_id in associations:
            raise ValueError(
                f"replacement {original_index} repeats tool_skeleton id {tool_id!r}"
            )
        associations[tool_id] = content

    source_content = source_message.get("content")
    if not isinstance(source_content, list):
        raise ValueError(f"message {original_index} has no content array")
    source_tool_ids = {
        identifier
        for block in source_content
        if isinstance(block, dict) and block.get("type") == "tool-input"
        for identifier in [block.get("native_tool_call_id") or block.get("id")]
        if isinstance(identifier, str)
    }
    unknown_ids = sorted(set(associations) - source_tool_ids)
    if unknown_ids:
        raise ValueError(
            f"replacement {original_index} tool_skeleton IDs do not match source: {unknown_ids}"
        )

    content = replacement.get("content")
    skeleton_content = (
        [block for block in content if is_tool_skeleton(block)]
        if isinstance(content, list)
        else []
    )
    if sorted(skeleton_content) != sorted(associations.values()):
        raise ValueError(
            f"replacement {original_index} tool_skeletons do not match replacement content"
        )
    return associations


def footer(paths: list[str]) -> str:
    entries = "\n".join(f"- @{path}" for path in paths)
    return "<affected-files>\n" + (entries + "\n" if entries else "") + "</affected-files>"


def apply_plan(
    source_bytes: bytes, manifest: dict[str, object]
) -> list[dict[str, object]]:
    if manifest.get("version") != 1:
        raise ValueError("manifest version must be 1")
    expected_checksum = manifest.get("source_sha256")
    actual_checksum = hashlib.sha256(source_bytes).hexdigest()
    if expected_checksum != actual_checksum:
        raise ValueError(
            f"source checksum mismatch: expected {expected_checksum}, got {actual_checksum}"
        )

    messages = load_messages(source_bytes)
    messages_by_index = {
        message["original_index"]: message for message in messages
    }
    drop_raw = manifest.get("drop_messages", [])
    replace_raw = manifest.get("replace_messages", [])
    extra_raw = manifest.get("affected_files_extra", [])
    if not isinstance(drop_raw, list) or not all(isinstance(index, int) for index in drop_raw):
        raise ValueError("drop_messages must be an integer array")
    if not isinstance(replace_raw, list) or not all(isinstance(item, dict) for item in replace_raw):
        raise ValueError("replace_messages must be an object array")
    if not isinstance(extra_raw, list) or not all(isinstance(path, str) for path in extra_raw):
        raise ValueError("affected_files_extra must be a string array")

    drops = set(drop_raw)
    missing_drops = sorted(drops - set(messages_by_index))
    if missing_drops:
        raise ValueError(f"drop_messages references missing indices: {missing_drops}")

    replacements: dict[int, list[object]] = {}
    for item in replace_raw:
        original_index = item.get("original_index")
        expected_tool_ids = item.get("expected_tool_ids", [])
        content = item.get("content")
        if not isinstance(original_index, int) or original_index not in messages_by_index:
            raise ValueError(f"replacement references missing index {original_index!r}")
        if original_index in replacements or original_index in drops:
            raise ValueError(f"replacement conflicts at index {original_index}")
        if not isinstance(expected_tool_ids, list) or not all(
            isinstance(identifier, str) for identifier in expected_tool_ids
        ):
            raise ValueError(f"replacement {original_index} expected_tool_ids must be strings")
        if set(expected_tool_ids) != tool_ids(messages_by_index[original_index]):
            raise ValueError(f"replacement {original_index} tool IDs do not match source")
        if not isinstance(content, list) or not content or not all(
            isinstance(block, (str, dict)) for block in content
        ):
            raise ValueError(
                f"replacement {original_index} content must contain strings or structured blocks"
            )
        replacement_tool_skeletons(
            item,
            messages_by_index[original_index],
            original_index,
        )
        replacements[original_index] = [
            block for block in content if not is_footer(block)
        ]

    compacted: list[dict[str, object]] = []
    for source_message in messages:
        original_index = source_message["original_index"]
        if original_index in drops:
            continue
        content = replacements.get(original_index, source_message.get("content"))
        if not isinstance(content, list):
            raise ValueError(f"message {original_index} has no content array")
        content = [block for block in content if not is_footer(block)]
        if not content:
            continue
        if any(
            isinstance(block, dict)
            and block.get("type") in {"tool-input", "tool-output"}
            for block in content
        ):
            raise ValueError(f"message {original_index} still contains raw tool blocks")
        message = dict(source_message)
        message.pop("remove", None)
        message["content"] = content
        compacted.append(message)
    if not compacted:
        raise ValueError("manifest removed every message")

    referenced_paths = [
        path
        for message in compacted
        for block in message["content"]
        if isinstance(block, str)
        for path in [transcript_common.reference_path(block)]
        if path is not None
    ]
    affected_paths: list[str] = []
    affected_identities: set[str] = set()
    for path in referenced_paths + extra_raw:
        identity = transcript_common.path_identity(path)
        if identity in affected_identities:
            continue
        affected_identities.add(identity)
        affected_paths.append(path)
    final_content = compacted[-1]["content"]
    if not isinstance(final_content, list):
        raise ValueError("final message has no content array")
    final_content.append(footer(affected_paths))
    return compacted


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_json", type=pathlib.Path)
    parser.add_argument("manifest_json", type=pathlib.Path)
    arguments = parser.parse_args()

    source_bytes = arguments.source_json.read_bytes()
    manifest = json.loads(arguments.manifest_json.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("manifest must be a JSON object")
    compacted = apply_plan(source_bytes, manifest)
    json.dump(compacted, sys.stdout, ensure_ascii=False, indent=2)
    print()
    print(f"messages: {len(load_messages(source_bytes))} -> {len(compacted)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
