#!/usr/bin/env -S uv run
# /// script
# requires-python = "==3.12.*"
# dependencies = []
# ///

import json
import pathlib
import sys
import tempfile
import unittest

SCRIPTS = pathlib.Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import codex_to_pi

TIMESTAMP = "2026-09-08T12:00:00.000Z"
ROOT_ID = "01a00000-0000-7000-8000-000000000001"
CHILD_ID = "01a00000-0000-7000-8000-000000000002"
SIBLING_ID = "01a00000-0000-7000-8000-000000000003"
GRANDCHILD_ID = "01a00000-0000-7000-8000-000000000004"
SUBAGENT_ID = "01a00000-0000-7000-8000-000000000005"


def record(ordinal: int, record_type: str, payload: dict[str, object]) -> dict[str, object]:
    return {"timestamp": TIMESTAMP, "ordinal": ordinal, "type": record_type, "payload": payload}


def session_meta(
    session_id: str,
    ordinal: int,
    parent_id: str | None = None,
    fork_ordinal: int | None = None,
    source: object = "cli",
) -> dict[str, object]:
    history_base = None
    if parent_id is not None:
        history_base = {
            "thread_id": parent_id,
            "end_ordinal_exclusive": fork_ordinal,
            "end_byte_offset": 1,
        }
    return record(
        ordinal,
        "session_meta",
        {
            "id": session_id,
            "session_id": session_id,
            "timestamp": TIMESTAMP,
            "cwd": "/tmp/project",
            "source": source,
            "forked_from_id": parent_id,
            "forked_from_ordinal_exclusive": fork_ordinal,
            "history_base": history_base,
        },
    )


def turn_context(ordinal: int) -> dict[str, object]:
    return record(ordinal, "turn_context", {"model": "gpt-test", "effort": "high"})


def message(ordinal: int, identifier: str, role: str, text: str) -> dict[str, object]:
    content_type = "output_text" if role == "assistant" else "input_text"
    return record(
        ordinal,
        "response_item",
        {
            "type": "message",
            "id": identifier,
            "role": role,
            "content": [{"type": content_type, "text": text}],
        },
    )


def write_rollout(
    root: pathlib.Path,
    session_id: str,
    records: list[dict[str, object]],
    suffix: str = "",
) -> pathlib.Path:
    path = root / "2026" / "09" / "08" / f"rollout-{session_id}{suffix}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(item) + "\n" for item in records), encoding="utf-8")
    return path


def load_session(path: pathlib.Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def message_texts(entries: list[dict[str, object]]) -> list[str]:
    return [
        str(block["text"])
        for entry in entries
        if entry.get("type") == "message"
        for block in entry["message"].get("content", [])
        if block.get("type") == "text"
    ]


class CodexForkTreeTests(unittest.TestCase):
    def test_selecting_a_child_materializes_its_parent_prefix_as_a_pi_fork(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = pathlib.Path(temporary_directory)
            codex_sessions = temporary / "codex" / "sessions"
            pi_sessions = temporary / "pi" / "sessions"
            write_rollout(
                codex_sessions,
                ROOT_ID,
                [
                    session_meta(ROOT_ID, 0),
                    turn_context(1),
                    message(2, "root-user-shared", "user", "shared question"),
                    message(3, "root-assistant-shared", "assistant", "shared answer"),
                    message(4, "root-user-later", "user", "parent-only continuation"),
                    message(5, "root-assistant-later", "assistant", "parent-only answer"),
                ],
            )
            write_rollout(
                codex_sessions,
                CHILD_ID,
                [
                    session_meta(CHILD_ID, 4, ROOT_ID, 4),
                    turn_context(5),
                    message(6, "child-user", "user", "child question"),
                    message(7, "child-assistant", "assistant", "child answer"),
                ],
            )

            converted = codex_to_pi.convert_fork_tree(
                CHILD_ID,
                codex_sessions,
                pi_sessions,
                "Selected child",
            )

            self.assertEqual(
                set(converted),
                {ROOT_ID, CHILD_ID},
                f"The converter did not materialize the direct fork family: {converted!r}",
            )
            parent_entries = load_session(converted[ROOT_ID])
            child_entries = load_session(converted[CHILD_ID])
            self.assertEqual(
                child_entries[0].get("parentSession"),
                str(converted[ROOT_ID]),
                f"The child does not point to its converted parent: {child_entries[0]!r}",
            )
            self.assertEqual(
                message_texts(child_entries),
                ["shared question", "shared answer", "child question", "child answer"],
                f"The child did not copy exactly the history visible at its fork point: {message_texts(child_entries)!r}",
            )
            self.assertEqual(
                message_texts(parent_entries),
                ["shared question", "shared answer", "parent-only continuation", "parent-only answer"],
                f"Converting the child changed its parent conversation: {message_texts(parent_entries)!r}",
            )
            parent_shared_ids = {
                entry["id"]
                for entry in parent_entries
                if entry.get("type") == "message"
                and any(
                    block.get("text") in {"shared question", "shared answer"}
                    for block in entry["message"].get("content", [])
                )
            }
            child_shared_ids = {
                entry["id"]
                for entry in child_entries
                if entry.get("type") == "message"
                and any(
                    block.get("text") in {"shared question", "shared answer"}
                    for block in entry["message"].get("content", [])
                )
            }
            self.assertEqual(
                child_shared_ids,
                parent_shared_ids,
                "The Pi fork did not preserve the shared parent entry identities",
            )

    def test_paginated_rollout_segments_form_one_complete_session(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = pathlib.Path(temporary_directory)
            codex_sessions = temporary / "codex" / "sessions"
            pi_sessions = temporary / "pi" / "sessions"
            write_rollout(
                codex_sessions,
                ROOT_ID,
                [
                    session_meta(ROOT_ID, 0),
                    turn_context(1),
                    message(2, "root-user-shared", "user", "shared question"),
                    message(3, "root-assistant-shared", "assistant", "shared answer"),
                    message(4, "stale-overlap", "user", "stale overlap"),
                ],
                "-first",
            )
            continuation_meta = session_meta(ROOT_ID, 4)
            continuation_meta["payload"]["history_base"] = {
                "thread_id": ROOT_ID,
                "end_ordinal_exclusive": 4,
                "end_byte_offset": 1,
            }
            write_rollout(
                codex_sessions,
                ROOT_ID,
                [
                    continuation_meta,
                    turn_context(5),
                    message(6, "root-user-later", "user", "current continuation"),
                    message(7, "root-assistant-later", "assistant", "current answer"),
                ],
                "-current",
            )
            write_rollout(
                codex_sessions,
                CHILD_ID,
                [
                    session_meta(CHILD_ID, 4, ROOT_ID, 4),
                    turn_context(5),
                    message(6, "child-user", "user", "child question"),
                    message(7, "child-assistant", "assistant", "child answer"),
                ],
            )

            converted = codex_to_pi.convert_fork_tree(
                CHILD_ID,
                codex_sessions,
                pi_sessions,
                "Selected child",
            )

            parent_texts = message_texts(load_session(converted[ROOT_ID]))
            child_texts = message_texts(load_session(converted[CHILD_ID]))
            self.assertEqual(
                parent_texts,
                ["shared question", "shared answer", "current continuation", "current answer"],
                f"The paginated parent was not rebuilt from its active segment chain: {parent_texts!r}",
            )
            self.assertEqual(
                child_texts,
                ["shared question", "shared answer", "child question", "child answer"],
                f"The child did not fork from the rebuilt parent history: {child_texts!r}",
            )

    def test_selecting_a_middle_node_materializes_the_complete_recursive_fork_tree(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = pathlib.Path(temporary_directory)
            codex_sessions = temporary / "codex" / "sessions"
            pi_sessions = temporary / "pi" / "sessions"
            write_rollout(
                codex_sessions,
                ROOT_ID,
                [
                    session_meta(ROOT_ID, 0),
                    turn_context(1),
                    message(2, "root-user-shared", "user", "shared question"),
                    message(3, "root-assistant-shared", "assistant", "shared answer"),
                    message(4, "root-user-later", "user", "parent-only continuation"),
                    message(5, "root-assistant-later", "assistant", "parent-only answer"),
                ],
            )
            write_rollout(
                codex_sessions,
                CHILD_ID,
                [
                    session_meta(CHILD_ID, 4, ROOT_ID, 4),
                    turn_context(5),
                    message(6, "child-user", "user", "child question"),
                    message(7, "child-assistant", "assistant", "child answer"),
                ],
            )
            write_rollout(
                codex_sessions,
                SIBLING_ID,
                [
                    session_meta(SIBLING_ID, 4, ROOT_ID, 4),
                    turn_context(5),
                    message(6, "sibling-user", "user", "sibling question"),
                    message(7, "sibling-assistant", "assistant", "sibling answer"),
                ],
            )
            write_rollout(
                codex_sessions,
                GRANDCHILD_ID,
                [
                    session_meta(GRANDCHILD_ID, 8, CHILD_ID, 8),
                    turn_context(9),
                    message(10, "grandchild-user", "user", "grandchild question"),
                    message(11, "grandchild-assistant", "assistant", "grandchild answer"),
                ],
            )
            write_rollout(
                codex_sessions,
                SUBAGENT_ID,
                [
                    session_meta(
                        SUBAGENT_ID,
                        4,
                        ROOT_ID,
                        4,
                        {"subagent": {"thread_spawn": {"parent_thread_id": ROOT_ID}}},
                    )
                ],
            )

            converted = codex_to_pi.convert_fork_tree(
                CHILD_ID,
                codex_sessions,
                pi_sessions,
                "Selected child",
            )

            self.assertEqual(
                set(converted),
                {ROOT_ID, CHILD_ID, SIBLING_ID, GRANDCHILD_ID},
                f"Traversal missed a persisted fork or treated a native sub-agent as a fork: {converted!r}",
            )
            child_header = load_session(converted[CHILD_ID])[0]
            sibling_header = load_session(converted[SIBLING_ID])[0]
            grandchild_entries = load_session(converted[GRANDCHILD_ID])
            self.assertEqual(
                child_header.get("parentSession"),
                str(converted[ROOT_ID]),
                f"The selected node lost its parent: {child_header!r}",
            )
            self.assertEqual(
                sibling_header.get("parentSession"),
                str(converted[ROOT_ID]),
                f"The sibling lost its parent: {sibling_header!r}",
            )
            self.assertEqual(
                grandchild_entries[0].get("parentSession"),
                str(converted[CHILD_ID]),
                f"The grandchild lost its parent: {grandchild_entries[0]!r}",
            )
            self.assertEqual(
                message_texts(grandchild_entries),
                [
                    "shared question",
                    "shared answer",
                    "child question",
                    "child answer",
                    "grandchild question",
                    "grandchild answer",
                ],
                f"The grandchild did not inherit its complete fork path: {message_texts(grandchild_entries)!r}",
            )


if __name__ == "__main__":
    unittest.main()
