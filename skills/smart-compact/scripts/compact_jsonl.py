#!/usr/bin/env -S uv run
# /// script
# requires-python = "==3.12.*"
# dependencies = []
# ///
"""Remove JSONL message lines corresponding to transcript messages compacted away.

Given an original transcript JSON, a compacted transcript JSON, and a target
session JSONL, this script computes which original_index values were dropped
by the compaction and removes the corresponding message-type lines from the
JSONL. Non-message lines (session, model_change, session_info, etc.) are always
preserved.

Mapping: transcript original_index N maps to the Nth message-type line in the
JSONL (1-indexed). If the JSONL has fewer messages than the transcript, indices
that fall outside the JSONL message count are silently ignored.

Usage:
    uv run compact_jsonl.py original.json compacted.json target.jsonl
"""

import json
import shutil
import sys


def main():
    if len(sys.argv) != 4:
        print(f"Usage: {sys.argv[0]} original.json compacted.json target.jsonl", file=sys.stderr)
        sys.exit(2)

    original_path = sys.argv[1]
    compacted_path = sys.argv[2]
    jsonl_path = sys.argv[3]

    # 1. Compute removed indices (original_index in backup but not in compacted)
    with open(original_path) as f:
        original = json.load(f)
    with open(compacted_path) as f:
        compacted = json.load(f)

    original_indices = {m["original_index"] for m in original}
    kept_indices = {m["original_index"] for m in compacted}
    removed_indices = original_indices - kept_indices

    print(f"Original messages: {len(original_indices)}", file=sys.stderr)
    print(f"Kept messages:     {len(kept_indices)}", file=sys.stderr)
    print(f"Removed messages:  {len(removed_indices)}", file=sys.stderr)

    # 2. Backup target JSONL
    backup_path = jsonl_path + ".pre_compact.bak"
    shutil.copy2(jsonl_path, backup_path)
    print(f"Backup: {backup_path}", file=sys.stderr)

    # 3. Filter JSONL
    kept_lines: list[str] = []
    msg_idx = 0          # 1-based counter for message-type lines
    kept_count = 0
    removed_count = 0
    non_msg_count = 0
    out_of_range = 0

    with open(jsonl_path) as f:
        for line in f:
            line = line.rstrip("\n")
            if not line:
                continue
            entry = json.loads(line)
            if entry.get("type") == "message":
                msg_idx += 1
                if msg_idx in kept_indices:
                    kept_lines.append(line)
                    kept_count += 1
                elif msg_idx in removed_indices:
                    removed_count += 1
                else:
                    # Index present in neither set (shouldn't happen), keep it
                    kept_lines.append(line)
                    out_of_range += 1
            else:
                kept_lines.append(line)
                non_msg_count += 1

    print(f"Messages:  {kept_count} kept, {removed_count} removed, {out_of_range} out-of-range", file=sys.stderr)
    print(f"Non-message lines preserved: {non_msg_count}", file=sys.stderr)
    print(f"Total output lines: {len(kept_lines)}", file=sys.stderr)

    # 4. Write result
    with open(jsonl_path, "w") as f:
        f.write("\n".join(kept_lines) + "\n")

    print(f"Compacted JSONL written to: {jsonl_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
