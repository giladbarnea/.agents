#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Apply `remove: true` marks from a smart-compacted transcript JSON to the native
pi session JSONL it originated from, deleting the matching lines in place.

Correspondence is established deterministically, strongest key first:
  1. tool-call id — the importer derives each compacted block id from the first
     4 characters of the JSONL toolCall id (`call_<id>|…`). A compacted
     tool-output maps to the `toolResult` line with that toolCallId prefix; a
     compacted tool-input maps to the assistant line containing that toolCall.
     Every id join is content-proven (tool name + output text must agree).
  2. exact (role, full text) for id-less pure-text objects, order-disambiguated.
  3. order-anchored gap-fill: mapped objects are monotonic in line number, so a
     still-unmapped object must match the only same-role orphan line in the gap
     between its mapped neighbours.

Safety gates (all run before anything is written; any failure aborts untouched):
  - input integrity: tool-input ids and tool-output ids in the compacted JSON
    form a bijection;
  - pair closure: for every tool call, the object holding its input is marked
    for removal if and only if the object holding its output is — otherwise
    line deletion would orphan a toolCall or a toolResult;
  - total, injective mapping: every compacted object resolves to distinct JSONL
    lines, so marked lines can never be shared with kept content.

The session is always backed up first to a sibling `<name>.jsonl.backup-N`
(first free N). After deletion the parentId chain is spliced across removed
lines and the result is re-validated in memory before the file is replaced.

Usage:
    uv run transfer-to-pi-session.py compacted.json session.jsonl
"""

import argparse
import difflib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path


def fail(message: str) -> "SystemExit":
    return SystemExit(f"ABORT (session file untouched): {message}")


def short_tool_id(call_id: str) -> str:
    """The 4-char prefix the smart-compact importer uses as a block id.

    >>> short_tool_id("call_9tMRssh7XFy7QfUqtVn4Qfap|fc_0bec0afe")
    '9tMR'
    """
    return call_id.split("|", 1)[0].removeprefix("call_")[:4]


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


# --------------------------- compacted-JSON side ---------------------------

class CompactedObject:
    def __init__(self, index: int, obj: dict):
        self.index = index
        self.marked: bool = obj.get("remove") is True
        self.role: str = "user" if obj.get("type") == "user-message" else "assistant"
        self.input_ids: list[str] = []
        self.output_ids: list[str] = []
        self.output_names: dict[str, str] = {}
        self.output_texts: dict[str, str] = {}
        text_parts: list[str] = []
        for block in obj.get("content", []):
            if isinstance(block, str):
                text_parts.append(block)
                continue
            block_type = block.get("type")
            if block_type == "tool-input":
                self.input_ids.append(block["id"])
            elif block_type == "tool-output":
                self.output_ids.append(block["id"])
                self.output_names[block["id"]] = str(block.get("name", ""))
                self.output_texts[block["id"]] = _output_text(block)
        self.text: str = "".join(text_parts)

    @property
    def is_pure_text(self) -> bool:
        return not self.input_ids and not self.output_ids


def _output_text(block: dict) -> str:
    content = block.get("content", "")
    if isinstance(content, list):
        return "".join(
            part.get("text", "") for part in content if isinstance(part, dict)
        )
    return str(content)


# ----------------------------- pi-JSONL side -------------------------------

class SessionLine:
    def __init__(self, lineno: int, raw: str, obj: dict):
        self.lineno = lineno
        self.raw = raw
        self.obj = obj
        message = obj.get("message", {}) if obj.get("type") == "message" else {}
        self.role: str | None = message.get("role")
        self.tool_name: str = str(message.get("toolName", ""))
        self.result_prefix: str | None = None
        self.call_prefixes: list[str] = []
        self.text = ""
        if self.role == "toolResult":
            self.result_prefix = short_tool_id(message["toolCallId"])
            self.text = "".join(
                block.get("text", "")
                for block in message.get("content", [])
                if isinstance(block, dict) and block.get("type") == "text"
            )
        elif self.role in ("user", "assistant"):
            for block in message.get("content", []):
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "toolCall":
                    self.call_prefixes.append(short_tool_id(block["id"]))
                elif block.get("type") == "text":
                    self.text += block.get("text", "")


def parse_session(path: Path) -> list[SessionLine]:
    lines = []
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines()):
        if raw.strip():
            lines.append(SessionLine(lineno, raw, json.loads(raw)))
    return lines


# ------------------------------ safety gates -------------------------------

def check_input_pairing(objects: list[CompactedObject]) -> None:
    inputs = [tool_id for o in objects for tool_id in o.input_ids]
    outputs = [tool_id for o in objects for tool_id in o.output_ids]
    problems = []
    if len(set(inputs)) != len(inputs):
        problems.append("duplicate tool-input ids")
    if len(set(outputs)) != len(outputs):
        problems.append("duplicate tool-output ids")
    if set(inputs) != set(outputs):
        missing_out = sorted(set(inputs) - set(outputs))[:5]
        missing_in = sorted(set(outputs) - set(inputs))[:5]
        problems.append(
            f"inputs without outputs {missing_out}, outputs without inputs {missing_in}"
        )
    if problems:
        raise fail("compacted JSON tool pairing is broken: " + "; ".join(problems))


def check_pair_closure(objects: list[CompactedObject]) -> None:
    input_owner = {tid: o for o in objects for tid in o.input_ids}
    output_owner = {tid: o for o in objects for tid in o.output_ids}
    violations = []
    for tool_id, out_obj in output_owner.items():
        in_obj = input_owner[tool_id]
        if out_obj.marked != in_obj.marked:
            side = "output" if out_obj.marked else "input"
            violations.append(f"{tool_id} ({side} marked, pair kept)")
    if violations:
        raise fail(
            f"{len(violations)} tool pair(s) are marked on one side only — deleting "
            f"them would orphan their toolCall/toolResult partner. Either mark both "
            f"sides or neither. First few: {violations[:8]}"
        )


# ---------------------------- cross-referencing ----------------------------

def cross_reference(
    objects: list[CompactedObject], session: list[SessionLine]
) -> dict[int, list[int]]:
    """Map every compacted-object index to its JSONL line number(s)."""
    result_line = {l.result_prefix: l.lineno for l in session if l.result_prefix}
    call_line: dict[str, int] = {}
    for line in session:
        for prefix in line.call_prefixes:
            if prefix in call_line:
                raise fail(f"toolCall prefix {prefix!r} is not unique in the session")
            call_line[prefix] = line.lineno

    line_by_no = {l.lineno: l for l in session}
    mapping: dict[int, list[int]] = {}

    # 1) id joins, content-proven
    for o in objects:
        if o.output_ids:
            linenos = set()
            for tool_id in o.output_ids:
                prefix = tool_id[:4]
                if prefix not in result_line:
                    raise fail(f"object {o.index}: no toolResult matches id {tool_id!r}")
                line = line_by_no[result_line[prefix]]
                _prove_output(o, tool_id, line)
                linenos.add(line.lineno)
            mapping[o.index] = sorted(linenos)
        elif o.input_ids:
            linenos = set()
            for tool_id in o.input_ids:
                prefix = tool_id[:4]
                if prefix not in call_line:
                    raise fail(f"object {o.index}: no toolCall matches id {tool_id!r}")
                linenos.add(call_line[prefix])
            mapping[o.index] = sorted(linenos)

    # grouping invariant: one assistant line is owned by at most one object
    owner_by_line: dict[int, int] = {}
    for index, linenos in mapping.items():
        for lineno in linenos:
            if owner_by_line.setdefault(lineno, index) != index:
                raise fail(
                    f"line {lineno} is claimed by objects {owner_by_line[lineno]} "
                    f"and {index} — grouping assumption broken"
                )

    # 2) exact (role, text) with order disambiguation
    text_index: dict[tuple[str, str], list[int]] = defaultdict(list)
    for line in session:
        if line.role in ("user", "assistant") and line.lineno not in owner_by_line:
            text_index[(line.role, line.text)].append(line.lineno)
    cursor: dict[tuple[str, str], int] = defaultdict(int)
    for o in objects:
        if not o.is_pure_text:
            continue
        key = (o.role, o.text)
        candidates = text_index.get(key, [])
        if cursor[key] < len(candidates):
            mapping[o.index] = [candidates[cursor[key]]]
            cursor[key] += 1

    # 3) order-anchored gap-fill for the rest (importer-reformatted text)
    mapped_pairs = sorted((i, mapping[i][0]) for i in mapping)
    for (a, line_a), (b, line_b) in zip(mapped_pairs, mapped_pairs[1:]):
        if line_a > line_b:
            raise fail(f"mapping is not order-preserving ({a}->{line_a}, {b}->{line_b})")
    claimed = {lineno for linenos in mapping.values() for lineno in linenos}
    orphans = [
        l for l in session
        if l.role in ("user", "assistant", "toolResult") and l.lineno not in claimed
    ]
    for o in objects:
        if o.index in mapping:
            continue
        low = max((mapping[i][0] for i in mapping if i < o.index), default=-1)
        high = min((mapping[i][0] for i in mapping if i > o.index), default=10**9)
        candidates = [l for l in orphans if low < l.lineno < high and l.role == o.role]
        if not candidates:
            raise fail(f"object {o.index} ({o.role}) cannot be located in the session")
        best = candidates[0] if len(candidates) == 1 else max(
            candidates,
            key=lambda l: difflib.SequenceMatcher(None, o.text, l.text).ratio(),
        )
        mapping[o.index] = [best.lineno]
        orphans = [l for l in orphans if l.lineno != best.lineno]

    # totality + injectivity
    unmapped = [o.index for o in objects if o.index not in mapping]
    if unmapped:
        raise fail(f"{len(unmapped)} object(s) could not be mapped: {unmapped[:10]}")
    claims: dict[int, list[int]] = defaultdict(list)
    for index, linenos in mapping.items():
        for lineno in linenos:
            claims[lineno].append(index)
    collisions = {k: v for k, v in claims.items() if len(v) > 1}
    if collisions:
        raise fail(f"line(s) claimed by multiple objects: {dict(list(collisions.items())[:5])}")
    return mapping


def _prove_output(o: CompactedObject, tool_id: str, line: SessionLine) -> None:
    expected_name = o.output_names[tool_id].lower()
    if expected_name and line.tool_name.lower() != expected_name:
        raise fail(
            f"object {o.index}: tool name mismatch on {tool_id!r} "
            f"({expected_name!r} vs {line.tool_name!r})"
        )
    expected = normalize(o.output_texts[tool_id])[:100]
    actual = normalize(line.text)[:100]
    if expected != actual:
        raise fail(
            f"object {o.index}: output content mismatch on {tool_id!r} "
            f"({expected[:60]!r} vs {actual[:60]!r})"
        )


# -------------------------------- applying ---------------------------------

def next_backup_path(jsonl_path: Path) -> Path:
    for n in range(1000):
        candidate = jsonl_path.with_name(jsonl_path.name + f".backup-{n}")
        if not candidate.exists():
            return candidate
    raise fail("more than 1000 backups exist")


def apply_removals(session: list[SessionLine], removed: set[int]) -> list[str]:
    parent_of = {
        l.obj["id"]: l.obj.get("parentId") for l in session if "id" in l.obj
    }
    removed_ids = {l.obj["id"] for l in session if l.lineno in removed and "id" in l.obj}

    def surviving_ancestor(parent_id: str | None) -> str | None:
        while parent_id in removed_ids:
            parent_id = parent_of.get(parent_id)
        return parent_id

    output: list[str] = []
    for line in session:
        if line.lineno in removed:
            continue
        parent_id = line.obj.get("parentId")
        if parent_id in removed_ids:
            spliced = surviving_ancestor(parent_id)
            if spliced is None:
                raise fail(f"line {line.lineno}: no surviving ancestor after splice")
            line.obj["parentId"] = spliced
            output.append(json.dumps(line.obj, ensure_ascii=False))
        else:
            output.append(line.raw)
    return output


def validate_result(new_lines: list[str], expected_count: int) -> None:
    parsed = [json.loads(line) for line in new_lines]
    if len(parsed) != expected_count:
        raise fail(f"expected {expected_count} surviving lines, got {len(parsed)}")
    ids = {o["id"] for o in parsed if "id" in o}
    dangling = [
        o.get("parentId") for o in parsed
        if o.get("parentId") and o["parentId"] not in ids
    ]
    if dangling:
        raise fail(f"{len(dangling)} dangling parentId(s) after splice")
    calls, results = set(), set()
    for o in parsed:
        if o.get("type") != "message":
            continue
        message = o["message"]
        if message.get("role") == "toolResult":
            results.add(short_tool_id(message["toolCallId"]))
        elif message.get("role") == "assistant":
            calls.update(
                short_tool_id(block["id"])
                for block in message.get("content", [])
                if isinstance(block, dict) and block.get("type") == "toolCall"
            )
    if calls != results:
        raise fail(
            f"tool pairing broken after removal: {len(calls - results)} calls without "
            f"results, {len(results - calls)} results without calls"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("compacted_json", type=Path)
    parser.add_argument("session_jsonl", type=Path)
    args = parser.parse_args()

    compacted = json.loads(args.compacted_json.read_text(encoding="utf-8"))
    if not isinstance(compacted, list):
        raise fail(f"{args.compacted_json} is not a JSON array")
    objects = [CompactedObject(i, o) for i, o in enumerate(compacted)]
    marked = [o for o in objects if o.marked]
    if not marked:
        raise fail("no objects carry remove:true — nothing to transfer")

    check_input_pairing(objects)
    check_pair_closure(objects)

    session = parse_session(args.session_jsonl)
    mapping = cross_reference(objects, session)

    removed_lines = {
        lineno for o in marked for lineno in mapping[o.index]
    }
    new_lines = apply_removals(session, removed_lines)
    validate_result(new_lines, len(session) - len(removed_lines))

    backup = next_backup_path(args.session_jsonl)
    backup.write_bytes(args.session_jsonl.read_bytes())
    args.session_jsonl.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

    size_before = backup.stat().st_size
    size_after = args.session_jsonl.stat().st_size
    print(f"backup        : {backup}")
    print(f"marked objects: {len(marked)} -> {len(removed_lines)} JSONL lines removed")
    print(f"lines         : {len(session)} -> {len(new_lines)}")
    print(f"bytes         : {size_before} -> {size_after} "
          f"({100 * (1 - size_after / size_before):.1f}% smaller)")


if __name__ == "__main__":
    main()
