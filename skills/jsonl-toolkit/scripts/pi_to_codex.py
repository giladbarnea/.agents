#!/usr/bin/env -S uv run
# /// script
# requires-python = "==3.12.*"
# dependencies = []
# ///
"""Restore a Codex rollout from a Pi session that codex_to_pi.py wrote.

Every model-facing Codex item rides inside the Pi entry that replaced it: reasoning in
`thinkingSignature`, assistant ids in `textSignature`, and verbatim payloads in `codex`
slots. The reverse walks the active path and unfolds those slots in order.
"""

import json
import sys
from pathlib import Path

from codex_to_pi import ENCRYPTED_CALL_TYPE, SUBAGENT_NOTIFICATION_TYPE, SUBAGENT_RECORD_TYPE
from pi_session import JsonObject, extract_active_path, load_entries

RESPONSE_ITEM = "response_item"


def dumps(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def assistant_text_item(block: JsonObject) -> JsonObject:
    """Rebuild a Codex assistant message from a Pi text block and its signature.

    >>> assistant_text_item({"type": "text", "text": "hi", "textSignature": '{"v":1,"id":"msg_1","phase":"final_answer"}'})
    {'type': 'message', 'role': 'assistant', 'content': [{'type': 'output_text', 'text': 'hi'}], 'id': 'msg_1', 'phase': 'final_answer'}
    """
    signature = json.loads(str(block["textSignature"]))
    item: JsonObject = {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": block["text"]}], "id": signature["id"]}
    if "phase" in signature:
        item["phase"] = signature["phase"]
    return item


def assistant_items(message: JsonObject) -> list[JsonObject]:
    items: list[JsonObject] = []
    for block in message["content"]:
        if block["type"] == "thinking":
            items.append(json.loads(str(block["thinkingSignature"])))
        elif block["type"] == "text":
            items.append(assistant_text_item(block))
        elif block["type"] == "toolCall":
            items.append(block["codex"])
        else:
            raise ValueError(f"Cannot restore Pi assistant block {block['type']!r}")
    return items


FORK_KEYS = ("forked_from_id", "forked_from_ordinal_exclusive", "history_base")


def standalone_session_meta(header: JsonObject) -> JsonObject:
    """Restore the Codex session_meta as a standalone session: a Pi session already holds its whole fork history inline.

    >>> standalone_session_meta({"codex": {"id": "s", "cwd": "/p", "forked_from_id": "parent", "history_base": {}}})
    {'id': 's', 'cwd': '/p'}
    """
    return {key: value for key, value in header["codex"].items() if key not in FORK_KEYS}


def restore_records(header: JsonObject, active: list[JsonObject]) -> list[JsonObject]:
    records: list[JsonObject] = [{"timestamp": header["timestamp"], "type": "session_meta", "payload": standalone_session_meta(header)}]
    model: str | None = None
    effort: str | None = None

    def add(timestamp: object, record_type: str, payload: JsonObject) -> None:
        records.append({"timestamp": timestamp, "type": record_type, "payload": payload})

    for entry in active:
        entry_type = entry["type"]
        if entry_type == "session_info":
            continue
        if entry_type in ("model_change", "thinking_level_change"):
            model = str(entry["modelId"]) if entry_type == "model_change" else model
            effort = str(entry["thinkingLevel"]) if entry_type == "thinking_level_change" else effort
            if model is not None and effort is not None:
                add(entry["timestamp"], "turn_context", {"cwd": header["cwd"], "model": model, "effort": effort})
            continue
        if entry_type == "compaction":
            add(entry["timestamp"], "compacted", entry["details"]["codex"])
            continue
        if entry_type == "custom" and entry["customType"] == ENCRYPTED_CALL_TYPE:
            add(entry["timestamp"], RESPONSE_ITEM, entry["data"]["codex"])
            continue
        if entry_type == "custom" and entry["customType"] == SUBAGENT_RECORD_TYPE:
            continue
        if entry_type == "custom_message" and entry["customType"] == SUBAGENT_NOTIFICATION_TYPE:
            add(entry["timestamp"], RESPONSE_ITEM, entry["details"]["codex"])
            continue
        if entry_type == "message":
            message = entry["message"]
            role = message["role"]
            if role == "user":
                add(entry["timestamp"], RESPONSE_ITEM, entry["codex"])
            elif role == "assistant":
                for item in assistant_items(message):
                    add(entry["timestamp"], RESPONSE_ITEM, item)
            elif role == "toolResult":
                add(entry["timestamp"], RESPONSE_ITEM, message["details"]["codex"])
            else:
                raise ValueError(f"Cannot restore Pi message role {role!r}")
            continue
        raise ValueError(f"Cannot restore Pi entry type {entry_type!r}")

    for ordinal, record in enumerate(records):
        record["ordinal"] = ordinal
    return records


def main(session_path: Path, output_directory: Path) -> Path:
    header, active = extract_active_path(load_entries(Path(session_path)))
    records = restore_records(header, active)
    output_directory.mkdir(parents=True, exist_ok=True)
    target = output_directory / f"rollout-{header['id']}.jsonl"
    with target.open("w", encoding="utf-8") as out:
        out.write("".join(dumps(record) + "\n" for record in records))
    print(f"wrote {target}", file=sys.stderr)
    print(f"  records: {len(records)}", file=sys.stderr)
    return target


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: pi_to_codex.py <pi-session.jsonl> <output-directory>")
    main(Path(sys.argv[1]), Path(sys.argv[2]))
