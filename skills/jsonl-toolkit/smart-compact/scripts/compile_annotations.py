#!/usr/bin/env -S uv run
# /// script
# requires-python = "==3.12.*"
# dependencies = ["pyyaml"]
# ///
"""Compile ergonomic YAML annotations into strict compaction decisions."""

import argparse
import hashlib
import json
import pathlib
import sys

import yaml

import apply_compaction_plan
import generate_compaction_plan


ANNOTATION_KEYS = frozenset(
    {
        "drop",
        "drop_text_blocks",
        "drop_file_references",
        "skeletons",
        "scratchpad_paths",
        "opaque_artifacts",
    }
)
DROP_KEYS = frozenset({"indices", "ranges"})
PASSTHROUGH_KEYS = (
    "drop_text_blocks",
    "drop_file_references",
    "skeletons",
    "scratchpad_paths",
    "opaque_artifacts",
)


def parse_drop_annotations(raw: object) -> tuple[list[int], list[tuple[int, int]]]:
    """Parse direct indices and inclusive stable-index ranges."""
    if raw is None:
        return [], []
    if not isinstance(raw, dict):
        raise ValueError("drop must be an object")

    unknown_keys = sorted(set(raw) - DROP_KEYS)
    if unknown_keys:
        raise ValueError(f"unknown drop keys: {unknown_keys}")

    raw_indices = raw.get("indices", [])
    if not isinstance(raw_indices, list) or not all(type(index) is int for index in raw_indices):
        raise ValueError("drop.indices must be an integer array")

    raw_ranges = raw.get("ranges", [])
    if not isinstance(raw_ranges, list):
        raise ValueError("drop.ranges must be an array of [start, end] pairs")

    ranges: list[tuple[int, int]] = []
    for entry in raw_ranges:
        if not isinstance(entry, list) or len(entry) != 2:
            raise ValueError(f"drop range must be [start, end]: {entry!r}")
        start, end = entry
        if type(start) is not int or type(end) is not int:
            raise ValueError(f"drop range bounds must be integers: {entry!r}")
        if start > end:
            raise ValueError(f"drop range start exceeds end: {entry!r}")
        ranges.append((start, end))
    return raw_indices, ranges


def expand_drop_indices(
    existing_indices: set[int],
    declared_indices: list[int],
    ranges: list[tuple[int, int]],
) -> list[int]:
    """Expand ranges over messages that exist in the reviewed transcript.

    >>> expand_drop_indices({10, 20, 40}, [20], [(30, 50)])
    [20, 40]
    """
    missing_indices = sorted(set(declared_indices) - existing_indices)
    if missing_indices:
        raise ValueError(f"drop.indices references missing messages: {missing_indices}")

    expanded = set(declared_indices)
    for start, end in ranges:
        matches = {index for index in existing_indices if start <= index <= end}
        if not matches:
            raise ValueError(f"drop range [{start}, {end}] matches no messages")
        expanded.update(matches)
    return sorted(expanded)


def annotation_list(raw: dict[str, object], key: str) -> list[object]:
    values = raw.get(key, [])
    if not isinstance(values, list):
        raise ValueError(f"{key} must be an array")
    return values


def compile_annotations(
    source_bytes: bytes, raw_annotations: dict[str, object]
) -> dict[str, object]:
    """Compile annotations against one exact pruned transcript."""
    unknown_keys = sorted(set(raw_annotations) - ANNOTATION_KEYS)
    if unknown_keys:
        raise ValueError(f"unknown annotation keys: {unknown_keys}")

    messages = apply_compaction_plan.load_messages(source_bytes)
    existing_indices = {
        index
        for message in messages
        for index in [message.get("original_index")]
        if isinstance(index, int)
    }
    declared_indices, ranges = parse_drop_annotations(raw_annotations.get("drop"))
    decisions: dict[str, object] = {
        "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "drop_texts": expand_drop_indices(existing_indices, declared_indices, ranges),
    }
    decisions.update(
        {key: annotation_list(raw_annotations, key) for key in PASSTHROUGH_KEYS}
    )
    generate_compaction_plan.parse_decisions(decisions)
    return decisions


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pruned_json", type=pathlib.Path)
    parser.add_argument("annotations_yaml", type=pathlib.Path)
    arguments = parser.parse_args()

    source_bytes = arguments.pruned_json.read_bytes()
    raw_annotations = yaml.safe_load(
        arguments.annotations_yaml.read_text(encoding="utf-8")
    )
    if raw_annotations is None:
        raw_annotations = {}
    if not isinstance(raw_annotations, dict):
        raise ValueError("annotations must be a top-level object")

    annotations = {
        str(key): value for key, value in raw_annotations.items()
    }
    decisions = compile_annotations(source_bytes, annotations)
    json.dump(decisions, sys.stdout, ensure_ascii=False, indent=2)
    print()
    print(
        f"Compiled {len(decisions['drop_texts'])} text drops and "
        f"{len(decisions['skeletons'])} skeletons",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
