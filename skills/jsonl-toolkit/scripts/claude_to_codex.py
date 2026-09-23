#!/usr/bin/env -S uv run
# /// script
# requires-python = "==3.12.*"
# dependencies = []
# ///
"""Restore a Codex rollout from a Claude Code session that codex_to_claude.py wrote.

Every Codex record rides on exactly one Claude line under a top-level `codex` key, starting with
the session_meta line. The restore unfolds them in file order.
"""

import json
import sys
from pathlib import Path

from codex_to_pi import restored_rollout, write_restored_rollout

Record = dict[str, object]


def restore_records(lines: list[Record]) -> list[Record]:
    """Unfold the Codex records in file order.

    Raises ValueError for a turn added in Claude Code after the conversion, and when the session_meta
    line is missing, as in a copy that `claude --fork-session` made.
    """
    added = [line for line in lines if line.get("type") in ("user", "assistant") and "codex" not in line and not line.get("isCompactSummary")]
    if added:
        raise ValueError(f"Claude entry {added[0]['uuid']} was added after the conversion, and Codex cannot express it yet.")
    records = [line["codex"] for line in lines if "codex" in line]
    if not records or records[0]["type"] != "session_meta":
        raise ValueError("This Claude session lacks its Codex session_meta line. A `claude --fork-session` copy drops it, so restore the original session.")
    return records


def restore_session(session_path: Path) -> list[Record]:
    lines = [json.loads(line) for line in Path(session_path).read_text(encoding="utf-8").split("\n") if line]
    return restored_rollout(restore_records(lines))


def main(session_path: Path, output_directory: Path) -> Path:
    return write_restored_rollout(restore_session(session_path), output_directory)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: claude_to_codex.py <claude-session.jsonl> <output-directory>")
    main(Path(sys.argv[1]), Path(sys.argv[2]))
