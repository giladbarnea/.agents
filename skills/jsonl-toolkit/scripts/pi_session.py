#!/usr/bin/env python3
"""Shared operations for native Pi session JSONL files."""

from __future__ import annotations

import json
import secrets
import subprocess
import sys
import time
from collections.abc import Iterable
from pathlib import Path

JsonObject = dict[str, object]
PI_SOURCE = Path("/opt/homebrew/lib/node_modules/@earendil-works/pi-coding-agent")
GOLDLOAD = Path(__file__).parent / "pi-goldload.mjs"


def eprint(*values: object) -> None:
    print(*values, file=sys.stderr)


def uuidv7() -> str:
    """Create a UUIDv7 string using the current Unix time."""
    milliseconds = int(time.time() * 1000)
    value = bytearray(milliseconds.to_bytes(6, "big") + secrets.token_bytes(10))
    value[6] = (value[6] & 0x0F) | 0x70
    value[8] = (value[8] & 0x3F) | 0x80
    hexadecimal = value.hex()
    return (
        f"{hexadecimal[0:8]}-{hexadecimal[8:12]}-{hexadecimal[12:16]}-"
        f"{hexadecimal[16:20]}-{hexadecimal[20:32]}"
    )


def load_entries(path: Path) -> list[JsonObject]:
    """Load the non-empty JSON objects from a native session file."""
    entries: list[JsonObject] = []
    with path.open(encoding="utf-8") as session_file:
        for line_number, line in enumerate(session_file, 1):
            if not line.strip():
                continue
            entry = json.loads(line)
            if not isinstance(entry, dict):
                raise ValueError(f"line {line_number} is not a JSON object")
            entries.append(entry)
    if len(entries) < 2:
        raise ValueError("native session needs a header and at least one tree entry")
    return entries


def extract_active_path(entries: list[JsonObject]) -> tuple[JsonObject, list[JsonObject]]:
    """Return the session header and the root-to-leaf active path.

    >>> header = {"type": "session", "id": "session"}
    >>> root = {"type": "message", "id": "root", "parentId": None}
    >>> abandoned = {"type": "message", "id": "old", "parentId": "root"}
    >>> leaf = {"type": "message", "id": "leaf", "parentId": "root"}
    >>> [entry["id"] for entry in extract_active_path([header, root, abandoned, leaf])[1]]
    ['root', 'leaf']
    """
    header = entries[0]
    if header.get("type") != "session":
        raise ValueError("line 1 is not a session header")

    tree = entries[1:]
    identifiers = [entry.get("id") for entry in tree]
    if not all(isinstance(identifier, str) for identifier in identifiers):
        raise ValueError("every tree entry needs a string id")
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("native tree entry ids must be unique")

    by_identifier = {
        identifier: entry
        for entry, identifier in zip(tree, identifiers, strict=True)
        if isinstance(identifier, str)
    }
    active_reversed: list[JsonObject] = []
    seen: set[str] = set()
    current: JsonObject | None = tree[-1]
    while current is not None:
        identifier = current["id"]
        if not isinstance(identifier, str) or identifier in seen:
            raise ValueError(f"native parent chain cycles at {identifier!r}")
        active_reversed.append(current)
        seen.add(identifier)
        parent_identifier = current.get("parentId")
        if parent_identifier is None:
            current = None
            continue
        if not isinstance(parent_identifier, str) or parent_identifier not in by_identifier:
            raise ValueError(
                f"entry {identifier!r} has unresolved parentId {parent_identifier!r}"
            )
        current = by_identifier[parent_identifier]

    active = list(reversed(active_reversed))
    if active[0].get("parentId") is not None:
        raise ValueError("active path has no root with parentId:null")
    return header, active


def session_roots() -> list[Path]:
    """Return existing directories that can contain supported session files."""
    candidates = [
        Path.home() / ".pi" / "agent" / "sessions",
        Path.home() / ".claude" / "projects",
    ]
    return [candidate for candidate in candidates if candidate.is_dir()]


def resolve_session(argument: str) -> Path:
    """Resolve a session ID or direct JSONL path."""
    path = Path(argument)
    if path.exists() and path.suffix == ".jsonl":
        return path.resolve()

    for root in session_roots():
        candidates = list(root.rglob(f"*_{argument}.jsonl"))
        if candidates:
            return candidates[0].resolve()

    for root in session_roots():
        for jsonl_path in root.rglob("*.jsonl"):
            try:
                with jsonl_path.open(encoding="utf-8") as session_file:
                    header = json.loads(session_file.readline())
            except (json.JSONDecodeError, OSError):
                continue
            if isinstance(header, dict) and header.get("id") == argument:
                return jsonl_path.resolve()

    raise FileNotFoundError(f"could not resolve session: {argument}")


def content_id_audit(
    entries: list[JsonObject], old_identifier: str, active_identifiers: set[str]
) -> dict[str, object]:
    """Count old session-ID occurrences in content rather than structural fields."""
    total = 0
    on_active_path = 0
    locations: list[str] = []
    for entry in entries[1:]:
        raw = json.dumps(entry, ensure_ascii=False)
        structural_hits = int(entry.get("id") == old_identifier) + int(
            entry.get("parentId") == old_identifier
        )
        content_hits = raw.count(old_identifier) - structural_hits
        if content_hits <= 0:
            continue
        total += content_hits
        identifier = entry.get("id")
        is_active = isinstance(identifier, str) and identifier in active_identifiers
        if is_active:
            on_active_path += content_hits
        location = identifier if isinstance(identifier, str) else "?"
        locations.append(
            f"{location} ({'active' if is_active else 'off-path'}): {content_hits}"
        )
    return {
        "total": total,
        "on_active_path": on_active_path,
        "off_path": total - on_active_path,
        "locations": locations,
    }


def rewrite_content_id(
    entries: Iterable[JsonObject], old_identifier: str, new_identifier: str
) -> int:
    """Replace a session ID inside text and custom data, returning changed blocks."""
    replacements = 0
    for entry in entries:
        entry_type = entry.get("type")
        if entry_type == "message":
            message = entry.get("message")
            if not isinstance(message, dict):
                continue
            content = message.get("content")
            if not isinstance(content, list):
                continue
            for block in content:
                if not isinstance(block, dict) or block.get("type") != "text":
                    continue
                text = block.get("text")
                if not isinstance(text, str) or old_identifier not in text:
                    continue
                block["text"] = text.replace(old_identifier, new_identifier)
                replacements += 1
            continue
        if entry_type not in {"custom", "custom_message"}:
            continue
        data = entry.get("data")
        if not isinstance(data, dict):
            continue
        raw = json.dumps(data, ensure_ascii=False)
        if old_identifier not in raw:
            continue
        entry["data"] = json.loads(raw.replace(old_identifier, new_identifier))
        replacements += 1
    return replacements


def bootstrap_path(source: Path) -> tuple[Path, str]:
    """Return a fresh Pi session path and UUID without writing the file."""
    new_identifier = uuidv7()
    now = time.time()
    iso_timestamp = (
        time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(now))
        + f".{int((now % 1) * 1000):03d}Z"
    )
    filename_timestamp = iso_timestamp.replace(":", "-").replace(".", "-")
    return source.parent / f"{filename_timestamp}_{new_identifier}.jsonl", new_identifier


def gold_standard(output_path: Path) -> None:
    """Load a native session through Pi's session manager when available."""
    if not GOLDLOAD.exists():
        eprint("  gold-standard: SKIPPED (pi-goldload.mjs not found)")
        return
    if not PI_SOURCE.exists():
        eprint("  gold-standard: SKIPPED (pi source not at expected path)")
        return
    try:
        result = subprocess.run(
            ["node", str(GOLDLOAD), str(output_path)],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except FileNotFoundError:
        eprint("  gold-standard: SKIPPED (node not found)")
        return
    except subprocess.TimeoutExpired:
        eprint("  gold-standard: SKIPPED (timeout)")
        return

    for line in result.stdout.strip().splitlines():
        eprint(f"  gold-standard: {line}")
    if result.returncode == 0:
        return
    eprint(f"  gold-standard: FAILED (exit {result.returncode})")
    if result.stderr:
        eprint(f"    {result.stderr[:200]}")


def discovery_smoke(session_identifier: str) -> None:
    """Check whether `ch` can discover a native session identifier."""
    try:
        result = subprocess.run(
            ["ch", session_identifier, "-l"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except FileNotFoundError:
        eprint("  discovery (ch): SKIPPED (ch not found)")
        return
    except subprocess.TimeoutExpired:
        eprint("  discovery (ch): SKIPPED (timeout)")
        return

    if result.returncode == 0 and "history_path" in result.stdout:
        eprint(f"  discovery (ch): PASS — session {session_identifier[:12]}… resolves")
        return
    eprint(f"  discovery (ch): FAIL — ch could not resolve {session_identifier}")
    if result.stderr:
        eprint(f"    {result.stderr[:150]}")
