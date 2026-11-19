#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
import argparse
import json
import math
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, TextIO, cast

Action = Literal["send", "reload", "model", "thinking"]
READY = ("idle", "done")
SESSION_ID = r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}"
RELOAD_COMPLETE = "Reloaded keybindings, extensions, skills, prompts, themes, and context files"
RELOAD_PENDING = "Reloading keybindings, extensions, skills, prompts, themes, and context files"


class Refused(Exception):
    pass


class Parser(argparse.ArgumentParser):
    def print_help(self, file: TextIO | None = None) -> None:
        super().print_help(file or sys.stderr)

    def error(self, message: str) -> None:
        raise Refused(message)


def positive_seconds(value: str) -> float:
    seconds = float(value)
    if not math.isfinite(seconds) or seconds <= 0:
        raise argparse.ArgumentTypeError("timeout must be a positive finite number of seconds")
    return seconds


@dataclass(frozen=True)
class Command:
    action: Action
    target: str
    prompt: str
    expected: str
    wait: bool
    timeout: float

    @property
    def label(self) -> str:
        return self.action if self.action in ("reload", "send") else f"{self.action}={self.expected}"


def parse(action: Action, arguments: list[str]) -> Command:
    script = {"send": "send-session-command", "reload": "reload-session",
              "model": "set-model", "thinking": "set-thinking"}[action]
    parser = Parser(prog=f"{script}.sh", allow_abbrev=False)
    parser.add_argument("target", help="self, full Pi session UUID, or Herdr pane address")
    wait = parser.add_mutually_exclusive_group()
    wait.add_argument("--wait-for-idle", dest="wait", action="store_true", default=True)
    wait.add_argument("--no-wait-for-idle", dest="wait", action="store_false")
    parser.add_argument("--timeout", type=positive_seconds, metavar="SECONDS")
    if action == "send":
        parser.add_argument("--prompt", required=True)
    if action == "model":
        parser.add_argument("--model", required=True, metavar="PROVIDER/MODEL")
    if action == "thinking":
        parser.add_argument("--level", required=True, choices=("off", "minimal", "low", "medium", "high", "xhigh", "max"))
    options = parser.parse_args(arguments)
    expected = getattr(options, "model", getattr(options, "level", ""))
    if action == "model" and not re.fullmatch(r"[\w.-]+/[\w.:-]+", expected, flags=re.ASCII):
        raise Refused("--model requires an exact PROVIDER/MODEL")
    prompt = {"reload": "/reload", "model": f"/model {expected}", "thinking": f"/thinking {expected}",
              "send": getattr(options, "prompt", "")}[action]
    if not prompt.strip() or prompt.startswith("-") or any(ord(character) < 32 or 127 <= ord(character) < 160 for character in prompt):
        raise Refused("prompt must be nonempty, single-line text without a leading dash or control characters")
    return Command(action, options.target, prompt, expected, options.wait,
                   options.timeout if options.timeout is not None else (300 if options.wait else 30))


@dataclass(frozen=True)
class Target:
    pane: str
    path: Path
    session: str


@dataclass
class Settings:
    model: str = "unknown"
    thinking: str = "unknown"

    def observe(self, record: dict[str, str]) -> None:
        if record["type"] == "model_change":
            self.model = f"{record['provider']}/{record['modelId']}"
        if record["type"] == "thinking_level_change":
            self.thinking = record["thinkingLevel"]

    def __str__(self) -> str:
        return f"model={self.model} thinking={self.thinking}"


def settings_from(file: Path, start: int = 0) -> list[dict[str, str]]:
    with file.open("rb") as stream:
        stream.seek(start)
        return [json.loads(line) for line in stream if line.endswith(b"\n") and line.startswith(
            (b'{"type":"model_change"', b'{"type":"thinking_level_change"'))]


class Herdr:
    def __init__(self, timeout: float) -> None:
        self.deadline = time.monotonic() + timeout

    def remaining(self) -> float:
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise Refused("timeout expired")
        return remaining

    def call(self, *arguments: str) -> str:
        result = subprocess.run(["herdr", *arguments], check=False, capture_output=True, text=True, timeout=self.remaining())
        if result.returncode != 0:
            # Do not relay raw terminal content or the submitted prompt on errors.
            raise Refused(f"Herdr {' '.join(arguments[:2])} failed (exit {result.returncode})")
        return result.stdout

    def response(self, *arguments: str) -> dict[str, object]:
        return cast(dict[str, object], json.loads(self.call(*arguments))["result"])

    def resolve(self, argument: str) -> Target:
        requested = os.environ.get("PI_SESSION_ID", "") if argument == "self" else argument
        by_pane = re.fullmatch(r"w[\da-zA-Z]+:p[\da-zA-Z]+", requested) is not None
        if not by_pane and not re.fullmatch(SESSION_ID, requested):
            raise Refused("target must be self with PI_SESSION_ID set, a full Pi session UUID, or a pane address")
        agents = cast(list[dict[str, object]], self.response("agent", "list")["agents"])
        sessions = [target_from(agent) for agent in agents]
        matches = [item for item in sessions if item and (item.pane if by_pane else item.session) == requested]
        if len(matches) != 1:
            raise Refused(f"expected exactly one open, file-backed Pi session for {argument}; found {len(matches)}")
        return matches[0]

    def agent(self, target: Target) -> dict[str, object]:
        agent = cast(dict[str, object], self.response("agent", "get", target.pane)["agent"])
        if target_from(agent) != target:
            raise Refused("pane no longer hosts the same Pi session")
        return agent

    def foreground(self, target: Target) -> int:
        info = cast(dict[str, object], self.response("pane", "process-info", "--pane", target.pane)["process_info"])
        processes = cast(list[dict[str, object]], info["foreground_processes"])
        if len(processes) != 1 or Path(str(processes[0]["argv0"])).name != "pi":
            raise Refused("cannot verify a unique foreground Pi process")
        return int(cast(int, processes[0]["pid"]))

    def screen(self, target: Target) -> str:
        return self.call("agent", "read", target.pane, "--source", "visible")

    def wait_ready(self, target: Target, wait: bool) -> dict[str, object]:
        agent = self.agent(target)
        state = agent["agent_status"]
        if state in READY:
            return agent
        if state != "working" or not wait:
            raise Refused(f"Pi is not ready (Herdr state={state})")
        if target.session == os.environ.get("PI_SESSION_ID"):
            raise Refused("the running caller cannot wait for its own turn to settle")
        self.call("agent", "wait", target.pane, "--until", "idle", "--until", "done", "--until", "blocked",
                  "--timeout", str(max(1, int(self.remaining() * 1000))))
        return self.wait_ready(target, False)


def target_from(agent: dict[str, object]) -> Target | None:
    session = cast(dict[str, str] | None, agent.get("agent_session"))
    if agent.get("agent") != "pi" or not session or session.get("kind") != "path":
        return None
    path = Path(session["value"])
    match = re.search(rf"_({SESSION_ID})\.jsonl$", path.name)
    if not match or not path.is_absolute():
        return None
    return Target(str(agent["pane_id"]), path, match[1])


def editor(screen: str) -> str | None:
    """Extract the editor text from Pi's visible pane."""
    dividers = list(re.finditer(r"^─+[ \t]*$", screen, re.MULTILINE))
    if len(dividers) < 2:
        return None
    return screen[dividers[-2].end():dividers[-1].start()].strip()


def observe(settings: Settings, records: list[dict[str, str]]) -> None:
    for record in records:
        settings.observe(record)


def verify(herdr: Herdr, target: Target, command: Command, before: str, start: int, pid: int, settings: Settings) -> None:
    marker = {"model": f"Model: {command.expected.split('/')[-1]}", "thinking": f"Thinking level: {command.expected}",
              "reload": RELOAD_COMPLETE}[command.action]
    before = " ".join(before.split())
    saw_reload = False
    while True:
        agent = herdr.agent(target)
        if herdr.foreground(target) != pid:
            raise Refused("the foreground Pi process changed after submission")
        records = settings_from(target.path, start)
        observe(settings, records)
        raw = herdr.screen(target)
        screen = " ".join(raw.split())
        input_box = editor(raw)
        picker = input_box is not None and "Enter to select" in input_box and any(
            line.strip() == f"> {command.expected}" for line in input_box.splitlines()
        )
        if command.action == "model" and picker:
            raise Refused("Pi opened the model picker instead of selecting the exact model; no selection made")
        error = {"model": "No API key for", "thinking": "Unknown thinking level", "reload": "Reload failed:"}[command.action]
        if screen.count(error) > before.count(error):
            raise Refused(f"Pi reported {error.rstrip(':')}")
        saw_reload |= RELOAD_PENDING in screen
        fresh_marker = screen.count(marker) > before.count(marker)
        verified = {
            "model": settings.model == command.expected and any(row["type"] == "model_change" for row in records),
            "thinking": settings.thinking == command.expected and (fresh_marker or any(
                row["type"] == "thinking_level_change" for row in records
            )),
            "reload": marker in screen and (fresh_marker or saw_reload) and RELOAD_PENDING not in screen,
        }
        if agent["agent_status"] in READY and input_box == "" and verified[command.action]:
            return
        time.sleep(min(0.15, herdr.remaining()))


def main(arguments: list[str]) -> int:
    command: Command | None = None
    target: Target | None = None
    settings = Settings()
    attempted = False
    try:
        command = parse(cast(Action, arguments[0]), arguments[1:])
        if os.environ.get("HERDR_ENV") != "1":
            raise Refused("run inside a Herdr pane (HERDR_ENV=1)")
        herdr = Herdr(command.timeout)
        target = herdr.resolve(command.target)
        initial_size = target.path.stat().st_size
        observe(settings, settings_from(target.path))
        agent = herdr.wait_ready(target, command.wait)
        pid = herdr.foreground(target)
        before = herdr.screen(target)
        if editor(before) != "":
            raise Refused("cannot confirm an empty Pi editor without a picker or draft")
        start = target.path.stat().st_size
        observe(settings, settings_from(target.path, initial_size))
        current = herdr.agent(target)
        if (current["agent_status"] not in READY or current.get("state_change_seq") != agent.get("state_change_seq")
                or herdr.foreground(target) != pid or herdr.screen(target) != before or target.path.stat().st_size != start):
            raise Refused("pane or editor changed during preflight; nothing sent")
        attempted = True
        response = herdr.response("agent", "prompt", target.pane, command.prompt)
        confirmed = cast(dict[str, object], response["agent"])
        if response["type"] != "agent_prompted" or target_from(confirmed) != target:
            raise Refused("could not confirm delivery to the intended session")
        if command.action != "send":
            verify(herdr, target, command, before, start, pid, settings)
        result = "delivered (application not checked)" if command.action == "send" else "verified"
        print(f"OK {target.pane} ({target.session}): {command.label} {result}; {settings}", file=sys.stderr)
        return 0
    except (Refused, OSError, subprocess.TimeoutExpired, ValueError, KeyError) as error:
        reason = str(error) if isinstance(error, Refused) else (
            "timeout expired during Herdr command" if isinstance(error, subprocess.TimeoutExpired)
            else type(error).__name__
        )
        subject = target.pane if target else command.target if command else "target not verified"
        request = command.label if command else "not accepted"
        delivery = "may have been delivered; not retried" if attempted else "nothing sent"
        print(f"Error {subject}: {reason}; requested={request}; observed {settings}; {delivery}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
