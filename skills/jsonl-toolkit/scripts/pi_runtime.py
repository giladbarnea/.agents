#!/usr/bin/env -S uv run
# /// script
# requires-python = "==3.12.*"
# dependencies = []
# ///
"""Capture known Pi attachments and restore dormant attachments to converted session copies."""
import json
import os
from pathlib import Path
import sys
from datetime import datetime, timezone
from urllib.parse import quote

from pi_session_tree import PiSessionNode, discover_session_tree

REPLAY_EXTENSION = Path(__file__).with_name("codex-replay.ts").resolve()
MEMBER_CONFIGURATION = ("name", "systemPrompt", "model", "thinking", "inheritMainContext", "canManageOwnTeams")


def capture_runtime(node: PiSessionNode) -> dict[str, object]:
    """Keep extension attachment inputs outside model context, without copying a live runtime."""
    runtime: dict[str, object] = {"origin": node.origin, "sourceSessionId": node.identifier}
    dispatches = [entry["data"] for entry in node.entries if entry.get("customType") == "pi-user-agents-dispatch"]
    if dispatches:
        runtime["dispatch"] = dispatches[-1]
    agent_directory = Path(os.environ.get("PI_CODING_AGENT_DIR", Path.home() / ".pi" / "agent"))
    teams = [json.loads(path.read_text()) for path in (agent_directory / "pi-simple-team" / "teams-v2").glob("*.json")]
    owned = [team for team in teams if team["originMainSessionId"] == node.identifier]
    if owned:
        runtime["teams"] = owned
    return runtime


def restored_dispatch(runtime: dict[str, object]) -> dict[str, object] | None:
    """Restore user-agent dispatch options with explicit replay loading, without delivering its result.

    >>> restored_dispatch({}) is None
    True
    """
    dispatch = runtime.get("dispatch")
    if dispatch is None:
        return None
    arguments = list(dispatch["forwardedArgs"])
    if str(REPLAY_EXTENSION) not in arguments:
        arguments.extend(["--extension", str(REPLAY_EXTENSION)])
    return {**dispatch, "forwardedArgs": arguments}


def restore_runtime(session_path: Path, agent_directory: Path) -> list[Path]:
    """Register fresh dormant teams for converted copies, leaving existing attachments and source teams untouched."""
    nodes = discover_session_tree(session_path)
    source_to_destination = {node.header["codex"]["payload"].get("piRuntime", {}).get("sourceSessionId"): node for node in nodes.values() if "codex" in node.header}
    created: list[Path] = []
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    for parent in nodes.values():
        children = [node for node in nodes.values() if node.parent_id == parent.identifier]
        children = [node for node in children if isinstance(node.header["codex"]["payload"].get("source"), dict)]
        automatic = [node for node in children if node.header["codex"]["payload"].get("piRuntime", {}).get("origin") != "pi-user-agents"]
        source_runtime = parent.header.get("codex", {}).get("payload", {}).get("piRuntime", {})
        groups: list[tuple[str, str, list[tuple[PiSessionNode, dict[str, object]]]]] = []
        assigned: set[str] = set()
        for team in source_runtime.get("teams", []):
            members = [(source_to_destination[member["teammateId"]], member) for member in team["members"] if member["teammateId"] in source_to_destination and source_to_destination[member["teammateId"]].parent_id == parent.identifier]
            if not members:
                continue
            groups.append((team["name"], team["teamPrompt"], members))
            assigned.update(node.identifier for node, _ in members)
        native_members = []
        for child in automatic:
            if child.identifier in assigned:
                continue
            source = child.header["codex"]["payload"]["source"]["subagent"]["thread_spawn"]
            settings = [entry for entry in child.entries if entry["type"] == "model_change"]
            thinking = [entry["thinkingLevel"] for entry in child.entries if entry["type"] == "thinking_level_change"]
            native_members.append((child, {"name": source["agent_path"], "systemPrompt": f"Continue the saved work of {source['agent_path']}. Use the current team tools for new messages.", "model": f"{settings[-1]['provider']}/{settings[-1]['modelId']}", "thinking": thinking[-1] if thinking else "high", "inheritMainContext": False, "canManageOwnTeams": any(node.parent_id == child.identifier for node in nodes.values())}))
        if native_members:
            groups.append(("converted-codex", "Continue the converted conversations. Original agent paths are the teammate names; use main for their parent.", native_members))
        for name, prompt, members in groups:
            team_id = f"{parent.identifier}-{name}"
            directory = agent_directory / "pi-simple-team" / "teams-v2"
            directory.mkdir(parents=True, exist_ok=True)
            target = directory / (quote(team_id, safe="!~*'()") + ".json")
            roster = [{**{key: configuration[key] for key in MEMBER_CONFIGURATION}, "teammateId": child.identifier, "sessionFile": str(child.path.resolve()), "sessionMaterialized": True, "showOnHerdrPane": False, "live": False, "active": False, "extensionPaths": list(dict.fromkeys([*configuration.get("extensionPaths", []), str(REPLAY_EXTENSION)]))} for child, configuration in members]
            manifest = {"version": 2, "id": team_id, "name": name, "originMainSessionId": parent.identifier, "projectDirectory": str(Path(parent.header["cwd"]).resolve(strict=True)), "teamPrompt": prompt, "showOnHerdrPanes": False, "members": roster, "state": "dormant", "createdAt": timestamp, "updatedAt": timestamp}
            if target.exists():
                existing = json.loads(target.read_text())
                expected = {(member["teammateId"], member["sessionFile"]) for member in roster}
                actual = {(member["teammateId"], member["sessionFile"]) for member in existing["members"]}
                if existing["originMainSessionId"] != parent.identifier or not expected.issubset(actual):
                    raise ValueError(f"Refusing to overwrite a different team attachment: {target}")
                created.append(target)
                continue
            with target.open("x", encoding="utf-8") as output:
                output.write(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
            target.chmod(0o600)
            created.append(target)
    return created


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: pi_runtime.py <converted-pi-session.jsonl>")
    directory = Path(os.environ.get("PI_CODING_AGENT_DIR", Path.home() / ".pi" / "agent"))
    print(json.dumps([str(path) for path in restore_runtime(Path(sys.argv[1]), directory)]))
