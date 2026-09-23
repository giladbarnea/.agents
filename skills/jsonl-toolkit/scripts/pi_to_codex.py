#!/usr/bin/env -S uv run
# /// script
# requires-python = "==3.12.*"
# dependencies = []
# ///
"""Restore a Codex rollout from a Pi session that codex_to_pi.py wrote.

Every Codex record rides under a `codex` key: the session_meta on the header, and every other
record, in order, in the lists of the entries along the active path. The restore unfolds them.
"""

import sys
from pathlib import Path

from codex_to_pi import restored_rollout, write_restored_rollout
from pi_session import JsonObject, extract_active_path, load_entries


def restore_records(header: JsonObject, active: list[JsonObject]) -> list[JsonObject]:
    """Unfold the Codex records along the active path.

    Raises ValueError for a session an older converter wrote, and for a turn added in Pi after the conversion.
    """
    if "payload" not in header.get("codex", {}):
        raise ValueError("This Pi session was written by an older codex_to_pi.py. Convert the Codex session again.")
    records = [header["codex"]]
    for entry in active:
        if entry["type"] == "message" and "codex" not in entry:
            raise ValueError(f"Pi entry {entry['id']} was added after the conversion, and Codex cannot express it yet.")
        records.extend(entry.get("codex", []))
    return records


def restore_session(session_path: Path) -> list[JsonObject]:
    header, active = extract_active_path(load_entries(Path(session_path)))
    return restored_rollout(restore_records(header, active))


def main(session_path: Path, output_directory: Path) -> Path:
    return write_restored_rollout(restore_session(session_path), output_directory)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: pi_to_codex.py <pi-session.jsonl> <output-directory>")
    main(Path(sys.argv[1]), Path(sys.argv[2]))
