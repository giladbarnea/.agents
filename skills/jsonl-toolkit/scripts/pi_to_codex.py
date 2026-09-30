#!/usr/bin/env -S uv run
# /// script
# requires-python = "==3.12.*"
# dependencies = []
# ///
"""Convert a native Pi conversation to Codex, or restore its preserved Codex records.

Native imports use Pi's own active-context and OpenAI message conversion. Imported Codex
sessions still unfold their original records without translating later Pi turns.
"""

import json
import os
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from codex_to_pi import REASONING_FAMILY_PREFIXES, restored_rollout, write_restored_rollout
from pi_session import JsonObject, extract_active_path, load_entries, uuidv7


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
    header, active = extract_active_path(load_entries(session_path))
    if "codex" in header:
        return write_restored_rollout(restored_rollout(restore_records(header, active)), output_directory)

    catalog_path = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "models_cache.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    result = subprocess.run(
        ["node", str(Path(__file__).with_name("pi-to-codex-context.mjs"))],
        input=json.dumps({"entries": [header, *active], "modelIds": [model["slug"] for model in catalog["models"]],
                          "reasoningFamilyPrefixes": REASONING_FAMILY_PREFIXES}),
        text=True, stdout=subprocess.PIPE, check=True,
    )
    context = json.loads(result.stdout)
    version = subprocess.run(["codex", "--version"], text=True, stdout=subprocess.PIPE, check=True).stdout.strip().split()[-1]
    identifier = uuidv7()
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    payloads = [
        ("session_meta", {
            "id": identifier, "session_id": identifier, "timestamp": timestamp,
            "cwd": header["cwd"], "originator": "pi_to_codex", "cli_version": version,
            "source": "cli", "model_provider": "openai",
        }),
        ("turn_context", {
            "cwd": header["cwd"], "model": context["model"], "effort": context["effort"],
            "summary": "auto", "approval_policy": "on-request", "sandbox_policy": {"type": "read-only"},
        }),
        *(("response_item", item) for item in context["items"]),
    ]
    records = [{"timestamp": timestamp, "ordinal": ordinal, "type": kind, "payload": payload}
               for ordinal, (kind, payload) in enumerate(payloads)]
    output = write_restored_rollout(records, output_directory)
    print(f"resume with: codex resume {identifier} --model {shlex.quote(context['model'])}", file=sys.stderr)
    return output


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: pi_to_codex.py <pi-session.jsonl> <output-directory>")
    main(Path(sys.argv[1]), Path(sys.argv[2]))
