"""Discover persisted Pi subagents without treating ordinary forks as delivered work."""

import json
import os
from dataclasses import dataclass
from pathlib import Path
import sys

from pi_session import JsonObject, extract_active_path, load_entries


@dataclass
class PiSessionNode:
    path: Path
    header: JsonObject
    entries: list[JsonObject]
    parent_id: str | None = None
    origin: str = "main"
    name: str = "main"

    @property
    def identifier(self) -> str:
        return str(self.header["id"])


def team_result_children(entries: list[JsonObject]) -> list[tuple[Path, str]]:
    """Read durable team-tool receipts, including fresh children without a parentSession header.

    >>> team_result_children([])
    []
    """
    children: list[tuple[Path, str]] = []
    for entry in entries:
        message = entry.get("message", {})
        if message.get("role") != "toolResult" or message.get("toolName") not in ("team_spawn", "team_add_teammates", "team_resume"):
            continue
        for block in message["content"]:
            if block.get("type") != "text":
                continue
            try:
                result = json.loads(block["text"])
            except json.JSONDecodeError:
                continue
            if not isinstance(result, dict):
                continue
            children.extend((Path(member["sessionFile"]), member["name"]) for member in result.get("teammates", []) if member.get("sessionFile"))
    return children


def discover_session_tree(source: Path) -> dict[str, PiSessionNode]:
    """Find the selected session and its persisted descendants using explicit dispatch provenance."""
    source = source.resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Pi session JSONL does not exist: {source}")
    local_root = source.parent.parent if source.parent.name.startswith("--") else source.parent
    sessions_root = next((parent for parent in source.parents if parent.name == "sessions"), local_root)
    header_children: dict[Path, list[Path]] = {}
    for path in sorted(sessions_root.rglob("*.jsonl")):
        with path.open(encoding="utf-8") as handle:
            header = json.loads(handle.readline())
        if header.get("type") != "session" or not header.get("parentSession"):
            continue
        header_children.setdefault(Path(header["parentSession"]).resolve(), []).append(path.resolve())

    manifest_children: dict[str, list[tuple[Path, str]]] = {}
    agent_directory = Path(os.environ.get("PI_CODING_AGENT_DIR", Path.home() / ".pi" / "agent"))
    for path in sorted((agent_directory / "pi-simple-team" / "teams-v2").glob("*.json")):
        manifest = json.loads(path.read_text())
        manifest_children.setdefault(manifest["originMainSessionId"], []).extend(
            (Path(member["sessionFile"]), member["name"]) for member in manifest["members"] if member.get("sessionFile")
        )

    nodes: dict[str, PiSessionNode] = {}
    visiting: set[Path] = set()

    def visit(path: Path, parent_id: str | None, origin: str, name: str) -> None:
        path = path.resolve()
        if path in visiting:
            raise ValueError(f"Pi child-session links cycle at {path}")
        if not path.is_file():
            print(f"Skipping missing child JSONL: {path}", file=sys.stderr)
            return
        header, entries = extract_active_path(load_entries(path))
        node = PiSessionNode(path, header, entries, parent_id, origin, name)
        previous = nodes.get(node.identifier)
        if previous is not None and (previous.path != path or previous.parent_id != parent_id):
            raise ValueError(f"Ambiguous Pi child identity {node.identifier}: {previous.path} and {path}")
        if previous is not None:
            return
        nodes[node.identifier] = node
        visiting.add(path)
        receipts = [] if "codex" in header else team_result_children(entries)
        explicit = {child.resolve(): nickname for child, nickname in [*manifest_children.get(node.identifier, []), *receipts]}
        for child in header_children.get(path, []):
            if child in explicit:
                continue
            child_header, child_entries = extract_active_path(load_entries(child))
            dispatch = any(entry.get("customType") == "pi-user-agents-dispatch" for entry in child_entries)
            imported = "codex" in child_header and "codex" in header
            if dispatch or imported:
                visit(child, node.identifier, "pi-user-agents" if dispatch else "codex", str(child_header["id"]))
        for child, nickname in explicit.items():
            visit(child, node.identifier, "pi-simple-team", nickname)
        visiting.remove(path)

    visit(source, None, "main", "main")
    return nodes
