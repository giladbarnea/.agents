#!/usr/bin/env -S uv run
# /// script
# requires-python = "==3.12.*"
# dependencies = []
# ///
"""Codex → Pi → Codex and Codex → Claude Code → Codex must give back the same Codex records.

Every scenario runs through both converters, so a fix on one side cannot leave the other behind.
The expected records are written out from the Codex rollouts themselves, never from converter code.
"""

import json
import pathlib
import sys
import tempfile
import unittest
from collections.abc import Callable

SCRIPTS = pathlib.Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import claude_to_codex
import codex_to_claude
import codex_to_pi
import pi_to_codex
from test_codex_to_pi import CHILD_ID, GRANDCHILD_ID, ROOT_ID, SUBAGENT_ID, TIMESTAMP, message, record, session_meta, turn_context, write_rollout

FIXTURE_SESSIONS = pathlib.Path(__file__).resolve().parent / "fixtures" / "codex" / "sessions"
NESTED_ID = "01a00000-0000-7000-8000-000000000006"
FORK_KEYS = ("forked_from_id", "forked_from_ordinal_exclusive", "history_base")

Records = list[dict[str, object]]


def load_records(path: pathlib.Path) -> Records:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").split("\n") if line]


def through_pi(rollout: pathlib.Path, temporary: pathlib.Path) -> dict[str, Records]:
    converted = codex_to_pi.main(rollout, temporary / "pi", "Scenario")
    return {codex_id: pi_to_codex.restore_session(path) for codex_id, path in converted.items()}


def through_claude(rollout: pathlib.Path, temporary: pathlib.Path) -> dict[str, Records]:
    converted = codex_to_claude.main(rollout, temporary / "claude")
    return {codex_id: claude_to_codex.restore_session(path) for codex_id, path in converted.items()}


CONVERTERS: dict[str, Callable[[pathlib.Path, pathlib.Path], dict[str, Records]]] = {"pi": through_pi, "claude": through_claude}


def subagent_started(ordinal: int, thread_id: str, agent_path: str) -> dict[str, object]:
    return record(ordinal, "event_msg", {"type": "sub_agent_activity", "item": {"type": "SubAgentActivity", "kind": "started", "agent_thread_id": thread_id, "agent_path": agent_path}})


def delivery(ordinal: int, author: str, recipient: str, text: str) -> dict[str, object]:
    return record(ordinal, "response_item", {"type": "agent_message", "author": author, "recipient": recipient, "content": [{"type": "input_text", "text": text}]})


def subagent_meta(session_id: str, parent_id: str, agent_path: str, nickname: str) -> dict[str, object]:
    return session_meta(session_id, 0, source={"subagent": {"thread_spawn": {"parent_thread_id": parent_id, "agent_path": agent_path, "agent_nickname": nickname}}})


def standalone(meta: dict[str, object]) -> dict[str, object]:
    """The session_meta of a fork child whose restored rollout holds its parent history inline."""
    return {**meta, "ordinal": 0, "payload": {key: value for key, value in meta["payload"].items() if key not in FORK_KEYS}}


class RestoreTests(unittest.TestCase):
    def assert_restores(self, scenario: Callable[[pathlib.Path], tuple[pathlib.Path, dict[str, Records]]]) -> None:
        for converter_name, convert_and_restore in CONVERTERS.items():
            with self.subTest(converter=converter_name), tempfile.TemporaryDirectory() as temporary_directory:
                temporary = pathlib.Path(temporary_directory)
                selected, expected = scenario(temporary / "codex" / "sessions")
                restored = convert_and_restore(selected, temporary)
                self.assertEqual(sorted(restored), sorted(expected), f"{converter_name} must convert exactly these Codex sessions")
                for codex_id, records in expected.items():
                    first_difference = next((index for index, pair in enumerate(zip(records, restored[codex_id])) if pair[0] != pair[1]), None)
                    self.assertEqual(
                        restored[codex_id],
                        records,
                        f"{converter_name} changed Codex session {codex_id}. First difference at record {first_difference}. Counts: expected={len(records)} restored={len(restored[codex_id])}",
                    )

    def test_every_fixture_session_comes_back_record_for_record(self) -> None:
        fixtures = {str(load_records(path)[0]["payload"]["id"]): path for path in FIXTURE_SESSIONS.glob("*.jsonl")}
        trees = {"01a07088-19c9-7532-a9fe-b264c55379f0": set(fixtures) - {"01a07fee-9ed9-70b0-b6c1-85cc01822d5d"}, "01a07fee-9ed9-70b0-b6c1-85cc01822d5d": {"01a07fee-9ed9-70b0-b6c1-85cc01822d5d"}}
        for root_id, session_ids in trees.items():

            def scenario(sessions: pathlib.Path, root_id: str = root_id, session_ids: set[str] = session_ids) -> tuple[pathlib.Path, dict[str, Records]]:
                return fixtures[root_id], {session_id: load_records(fixtures[session_id]) for session_id in session_ids}

            self.assert_restores(scenario)

    def test_a_record_without_an_ordinal_keeps_its_place(self) -> None:
        rename = {"timestamp": TIMESTAMP, "type": "event_msg", "payload": {"type": "thread_name_updated", "thread_name": "✓ renamed"}}
        records = [session_meta(ROOT_ID, 0), turn_context(1), message(2, "user-1", "user", "hello"), rename, message(3, "msg-1", "assistant", "hi")]

        def scenario(sessions: pathlib.Path) -> tuple[pathlib.Path, dict[str, Records]]:
            return write_rollout(sessions, ROOT_ID, records), {ROOT_ID: records}

        self.assert_restores(scenario)

    def test_a_fork_child_comes_back_standalone_with_its_parent_history(self) -> None:
        parent = [
            session_meta(ROOT_ID, 0),
            turn_context(1),
            message(2, "user-1", "user", "shared question"),
            message(3, "msg-1", "assistant", "shared answer"),
            message(4, "user-2", "user", "parent-only question"),
            message(5, "msg-2", "assistant", "parent-only answer"),
        ]
        child = [session_meta(CHILD_ID, 4, ROOT_ID, 4), turn_context(5), message(6, "user-3", "user", "child question"), message(7, "msg-3", "assistant", "child answer")]

        def scenario(sessions: pathlib.Path) -> tuple[pathlib.Path, dict[str, Records]]:
            write_rollout(sessions, ROOT_ID, parent)
            selected = write_rollout(sessions, CHILD_ID, child)
            return selected, {ROOT_ID: parent, CHILD_ID: [standalone(child[0]), *parent[1:4], *child[1:]]}

        self.assert_restores(scenario)

    def test_a_fork_of_a_fork_can_read_its_history_from_the_grandparent(self) -> None:
        root = [session_meta(ROOT_ID, 0), turn_context(1), message(2, "user-1", "user", "shared question"), message(3, "msg-1", "assistant", "shared answer"), message(4, "user-2", "user", "root-only question")]
        child = [session_meta(CHILD_ID, 4, ROOT_ID, 4), turn_context(5), message(6, "user-3", "user", "child question")]
        grandchild = [session_meta(GRANDCHILD_ID, 3, ROOT_ID, 3), turn_context(4), message(5, "user-4", "user", "grandchild question")]
        grandchild[0]["payload"]["forked_from_id"] = CHILD_ID

        def scenario(sessions: pathlib.Path) -> tuple[pathlib.Path, dict[str, Records]]:
            write_rollout(sessions, ROOT_ID, root)
            write_rollout(sessions, CHILD_ID, child)
            selected = write_rollout(sessions, GRANDCHILD_ID, grandchild)
            return selected, {ROOT_ID: root, CHILD_ID: [standalone(child[0]), *root[1:4], *child[1:]], GRANDCHILD_ID: [standalone(grandchild[0]), *root[1:3], *grandchild[1:]]}

        self.assert_restores(scenario)

    def test_a_delivery_from_a_subagent_without_a_start_event_comes_back(self) -> None:
        records = [session_meta(ROOT_ID, 0), turn_context(1), message(2, "user-1", "user", "status?"), delivery(3, "/root/auditor", "/root", "Message Type: MESSAGE\nstill reading")]

        def scenario(sessions: pathlib.Path) -> tuple[pathlib.Path, dict[str, Records]]:
            return write_rollout(sessions, ROOT_ID, records), {ROOT_ID: records}

        self.assert_restores(scenario)

    def test_a_paginated_session_and_its_fork_child_come_back_as_their_active_history(self) -> None:
        first = [session_meta(ROOT_ID, 0), turn_context(1), message(2, "user-1", "user", "question"), message(3, "msg-1", "assistant", "answer"), message(4, "stale", "user", "superseded")]
        continuation_meta = session_meta(ROOT_ID, 4)
        continuation_meta["payload"]["history_base"] = {"thread_id": ROOT_ID, "end_ordinal_exclusive": 4, "end_byte_offset": 1}
        current = [continuation_meta, turn_context(5), message(6, "user-2", "user", "current question"), message(7, "msg-2", "assistant", "current answer")]
        child = [session_meta(CHILD_ID, 4, ROOT_ID, 4), turn_context(5), message(6, "user-3", "user", "child question")]

        def scenario(sessions: pathlib.Path) -> tuple[pathlib.Path, dict[str, Records]]:
            write_rollout(sessions, ROOT_ID, first, "-first")
            write_rollout(sessions, ROOT_ID, current, "-current")
            write_rollout(sessions, CHILD_ID, child)
            return sessions / "2026" / "09" / "08" / f"rollout-{ROOT_ID}-current.jsonl", {ROOT_ID: [*first[:4], *current[1:]], CHILD_ID: [standalone(child[0]), *first[1:4], *child[1:]]}

        self.assert_restores(scenario)

    def test_nested_subagents_each_come_back(self) -> None:
        root = [
            session_meta(ROOT_ID, 0),
            turn_context(1),
            message(2, "user-1", "user", "delegate the audit"),
            subagent_started(3, SUBAGENT_ID, "/root/auditor"),
            delivery(4, "/root/auditor", "/root", "Message Type: FINAL_ANSWER\nThe audit is clean."),
        ]
        auditor = [
            subagent_meta(SUBAGENT_ID, ROOT_ID, "/root/auditor", "auditor"),
            turn_context(1),
            delivery(2, "/root", "/root/auditor", "Message Type: NEW_TASK\nAudit the repo."),
            subagent_started(3, NESTED_ID, "/root/auditor/reader"),
            delivery(4, "/root/auditor/reader", "/root/auditor", "Message Type: FINAL_ANSWER\nRead 12 files."),
            message(5, "msg-1", "assistant", "The audit is clean."),
        ]
        reader = [
            subagent_meta(NESTED_ID, SUBAGENT_ID, "/root/auditor/reader", "reader"),
            turn_context(1),
            delivery(2, "/root/auditor", "/root/auditor/reader", "Message Type: NEW_TASK\nRead the files."),
            message(3, "msg-2", "assistant", "Read 12 files."),
        ]

        def scenario(sessions: pathlib.Path) -> tuple[pathlib.Path, dict[str, Records]]:
            write_rollout(sessions, SUBAGENT_ID, auditor)
            write_rollout(sessions, NESTED_ID, reader)
            return write_rollout(sessions, ROOT_ID, root), {ROOT_ID: root, SUBAGENT_ID: auditor, NESTED_ID: reader}

        self.assert_restores(scenario)


class ContinuedSessionTests(unittest.TestCase):
    def test_a_turn_added_after_the_conversion_stops_the_restore_with_a_clear_error(self) -> None:
        records = [session_meta(ROOT_ID, 0), turn_context(1), message(2, "user-1", "user", "hello"), message(3, "msg-1", "assistant", "hi")]
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = pathlib.Path(temporary_directory)
            rollout = write_rollout(temporary / "codex" / "sessions", ROOT_ID, records)
            pi_session = codex_to_pi.main(rollout, temporary / "pi", "Continued")[ROOT_ID]
            leaf = load_records(pi_session)[-1]["id"]
            with pi_session.open("a") as handle:
                handle.write(json.dumps({"type": "message", "id": "added01", "parentId": leaf, "timestamp": TIMESTAMP, "message": {"role": "user", "content": [{"type": "text", "text": "a new question in Pi"}], "timestamp": 0}}) + "\n")
            claude_session = codex_to_claude.main(rollout, temporary / "claude")[ROOT_ID]
            with claude_session.open("a") as handle:
                handle.write(json.dumps({"parentUuid": None, "type": "user", "uuid": "added-in-claude", "sessionId": "x", "message": {"role": "user", "content": "a new question in Claude"}}) + "\n")
            for name, restore, session in (("pi", pi_to_codex.restore_session, pi_session), ("claude", claude_to_codex.restore_session, claude_session)):
                with self.subTest(converter=name), self.assertRaisesRegex(ValueError, "added after the conversion", msg="Codex cannot hold a Pi or Claude turn yet, so a silent restore would drop it"):
                    restore(session)


if __name__ == "__main__":
    unittest.main()
