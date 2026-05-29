#!/usr/bin/env -S uv run
# /// script
# requires-python = "==3.12.*"
# dependencies = ["python-dateutil", "rich", "websocket-client"]
# ///

"""Scrape and compute AI usage limits for Claude and Codex.

Single idempotent script:
1. Connects to a remote-debugging Chrome session over CDP
2. Scrapes Claude/Codex usage pages from already-open authenticated tabs
3. Computes burn rates and exhaustion estimates
"""

import dataclasses
import json
import random
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from dateutil import tz
from rich.console import Console
from rich.text import Text
import websocket

IDT = tz.gettz("Asia/Jerusalem")
# Direct CDP lets us scrape the real logged-in Chrome tabs without headless bot checks.
CDP_PORT = 9222
CDP_BASE_URL = f"http://localhost:{CDP_PORT}"
PAGE_LOAD_DELAY_SECONDS = 3
CLAUDE_URL = "https://claude.ai/settings/usage"
CODEX_URL = "https://chatgpt.com/codex/cloud/settings/analytics"
SESSION_DURATION = timedelta(hours=5)
BODY_TEXT_EXPRESSION = "document.body.innerText"


@dataclasses.dataclass(frozen=True)
class BrowserTarget:
    target_id: str
    title: str
    url: str
    websocket_debugger_url: str


def read_json(url: str) -> object:
    try:
        with urllib.request.urlopen(url) as response:
            return json.load(response)
    except urllib.error.URLError as error:
        raise RuntimeError(f"Failed to reach Chrome CDP at {url}: {error}") from error


def list_page_targets() -> list[BrowserTarget]:
    payload = read_json(f"{CDP_BASE_URL}/json/list")
    if not isinstance(payload, list):
        raise RuntimeError("Unexpected payload from Chrome target list")

    page_targets: list[BrowserTarget] = []
    for entry in payload:
        if not isinstance(entry, dict):
            raise RuntimeError("Unexpected target entry payload")
        if entry.get("type") != "page":
            continue

        target_id = entry.get("id")
        title = entry.get("title")
        url = entry.get("url")
        websocket_debugger_url = entry.get("webSocketDebuggerUrl")
        if not isinstance(target_id, str):
            raise RuntimeError("Target id is missing")
        if not isinstance(title, str):
            raise RuntimeError("Target title is missing")
        if not isinstance(url, str):
            raise RuntimeError("Target url is missing")
        if not isinstance(websocket_debugger_url, str):
            raise RuntimeError("Target websocket url is missing")

        page_targets.append(
            BrowserTarget(
                target_id=target_id,
                title=title,
                url=url,
                websocket_debugger_url=websocket_debugger_url,
            )
        )
    return page_targets


def find_target(url: str) -> BrowserTarget | None:
    for target in list_page_targets():
        if target.url == url:
            return target
    return None


def find_target_by_id(target_id: str) -> BrowserTarget | None:
    for target in list_page_targets():
        if target.target_id == target_id:
            return target
    return None


def browser_websocket_debugger_url() -> str:
    payload = read_json(f"{CDP_BASE_URL}/json/version")
    if not isinstance(payload, dict):
        raise RuntimeError("Unexpected payload from Chrome version endpoint")
    websocket_debugger_url = payload.get("webSocketDebuggerUrl")
    if not isinstance(websocket_debugger_url, str):
        raise RuntimeError("Chrome browser websocket url is missing")
    return websocket_debugger_url


def wait_for_target(target_id: str) -> BrowserTarget:
    for _ in range(30):
        target = find_target_by_id(target_id)
        if target is not None:
            return target
        time.sleep(1)
    raise RuntimeError(f"Timed out waiting for Chrome target {target_id}")


def open_new_background_target(url: str) -> BrowserTarget:
    result = send_cdp_command(
        browser_websocket_debugger_url(),
        "Target.createTarget",
        {"url": url, "background": True},
    )
    target_id = result.get("targetId")
    if not isinstance(target_id, str):
        raise RuntimeError(f"Target.createTarget did not return a target id for {url}")
    time.sleep(PAGE_LOAD_DELAY_SECONDS)
    return wait_for_target(target_id)


def reload_target(target: BrowserTarget) -> BrowserTarget:
    send_cdp_command(target.websocket_debugger_url, "Page.reload")
    time.sleep(PAGE_LOAD_DELAY_SECONDS)
    refreshed_target = find_target_by_id(target.target_id)
    if refreshed_target is None:
        raise RuntimeError(f"Reloaded tab disappeared for {target.url}")
    return refreshed_target


def ensure_target(url: str) -> BrowserTarget:
    # Reuse+reload when possible, otherwise open in background, so runs stay idempotent and unobtrusive.
    existing_target = find_target(url)
    if existing_target is not None:
        return reload_target(existing_target)
    return open_new_background_target(url)


def send_cdp_command(
    websocket_debugger_url: str,
    method: str,
    params: dict[str, object] | None = None,
) -> dict[str, object]:
    connection = websocket.create_connection(
        websocket_debugger_url,
        suppress_origin=True,
    )
    try:
        connection.send(json.dumps({"id": 1, "method": method, "params": params or {}}))
        while True:
            message = json.loads(connection.recv())
            if message.get("id") != 1:
                continue
            if "error" in message:
                raise RuntimeError(f"CDP {method} failed: {message['error']}")
            result = message.get("result", {})
            if not isinstance(result, dict):
                raise RuntimeError(f"CDP {method} returned a non-dict result")
            return result
    finally:
        connection.close()


def scrape_body(target: BrowserTarget) -> str:
    result = send_cdp_command(
        target.websocket_debugger_url,
        "Runtime.evaluate",
        {"expression": BODY_TEXT_EXPRESSION, "returnByValue": True},
    )
    remote_result = result.get("result")
    if not isinstance(remote_result, dict):
        raise RuntimeError(f"CDP Runtime.evaluate returned an unexpected payload for {target.url}")
    value = remote_result.get("value")
    if not isinstance(value, str):
        raise RuntimeError(f"CDP Runtime.evaluate did not return text for {target.url}")
    return value


# ── Parsing ───────────────────────────────────────────────────────────

def _first_match(pattern: str, text: str, group: int = 1) -> str:
    m = re.search(pattern, text, re.DOTALL)
    if not m:
        raise ValueError(f"Pattern not found: {pattern!r}")
    return m.group(group)


def parse_claude(text: str) -> dict:
    """Extract Claude usage stats from raw body text."""
    session_match = re.search(
        r"Current session\s*(?:Resets\s+(.+?)\s*(\d+)%\s*used"
        r"|Starts when a message is sent\s*(\d+)%\s*used)",
        text, re.DOTALL,
    )
    if not session_match:
        raise ValueError("Cannot find Claude 'Current session' block")
    if session_match.group(1):
        session_reset_raw = session_match.group(1).strip()
        session_pct = int(session_match.group(2))
    else:
        session_reset_raw = f"in {SESSION_DURATION.total_seconds() // 3600:.0f} hr 0 min"
        session_pct = int(session_match.group(3))

    weekly_match = re.search(
        r"Weekly limits.*?(?:Resets\s+(.+?)\s*(\d+)%\s*used"
        r"|Starts when a message is sent\s*(\d+)%\s*used)",
        text, re.DOTALL,
    )
    if not weekly_match:
        raise ValueError("Cannot find Claude 'Weekly limits' block")
    if weekly_match.group(1):
        reset_raw = weekly_match.group(1).strip()
        weekly_pct = int(weekly_match.group(2))
    else:
        reset_raw = "in 168 hr 0 min"
        weekly_pct = int(weekly_match.group(3))

    return {
        "session_pct": session_pct,
        "session_reset_raw": session_reset_raw,
        "weekly_pct": weekly_pct,
        "reset_raw": reset_raw,
    }


def parse_codex(text: str) -> dict:
    """Extract Codex usage stats from raw body text."""
    hour5_pct = int(_first_match(r"5\s*hour\s*usage\s*limit.*?(\d+)\s*%\s*remaining", text))
    hour5_reset = _first_match(r"5\s*hour\s*usage\s*limit.*?Resets\s+(.+?)\n", text).strip()

    weekly_pct = int(_first_match(r"Weekly\s*usage\s*limit.*?(\d+)\s*%\s*remaining", text))
    weekly_reset = _first_match(r"Weekly\s*usage\s*limit.*?Resets\s+(.+?)\n", text).strip()

    return {
        "hour5_remaining_pct": hour5_pct,
        "hour5_reset_raw": hour5_reset,
        "weekly_remaining_pct": weekly_pct,
        "weekly_reset_raw": weekly_reset,
    }


# ── Time helpers ──────────────────────────────────────────────────────

DAY_MAP = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6,
           "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
           "friday": 4, "saturday": 5, "sunday": 6}


def parse_reset_claude(reset_raw: str, now: datetime) -> tuple[datetime, datetime]:
    """Given 'Wed 8:00 PM' or 'in 13 hr 2 min', return (last_reset, next_reset)."""
    rel = re.match(r"in\s+(?:(\d+)\s*hr)?\s*(?:(\d+)\s*min)?", reset_raw, re.I)
    if rel and (rel.group(1) or rel.group(2)):
        hours = int(rel.group(1)) if rel.group(1) else 0
        minutes = int(rel.group(2)) if rel.group(2) else 0
        next_reset = now + timedelta(hours=hours, minutes=minutes)
        last_reset = next_reset - timedelta(weeks=1)
        return last_reset, next_reset

    m = re.match(r"(\w{3,9})\s+(\d{1,2}):(\d{2})\s*(AM|PM)", reset_raw, re.I)
    if not m:
        raise ValueError(f"Cannot parse Claude reset: {reset_raw!r}")
    day_name, hour_s, minute_s, ampm = m.groups()
    hour = int(hour_s) + (12 if ampm.upper() == "PM" and int(hour_s) != 12 else 0) - (12 if ampm.upper() == "AM" and int(hour_s) == 12 else 0)
    target_wday = DAY_MAP[day_name.lower()]

    cand = now.replace(hour=hour, minute=int(minute_s), second=0, microsecond=0)
    days_behind = (cand.weekday() - target_wday) % 7
    last_reset = cand - timedelta(days=days_behind if days_behind else 0)
    if last_reset > now:
        last_reset -= timedelta(weeks=1)
    next_reset = last_reset + timedelta(weeks=1)
    return last_reset, next_reset


def parse_reset_codex(reset_raw: str, *, now: datetime) -> datetime:
    """Given 'May 25, 2026 12:42 AM' or bare '6:35 PM', return the reset datetime."""
    m = re.match(r"(\w{3} \d{1,2}, \d{4} \d{1,2}:\d{2} [AP]M)", reset_raw)
    if m:
        return datetime.strptime(m.group(1), "%b %d, %Y %I:%M %p").replace(tzinfo=IDT)
    bare = re.match(r"(\d{1,2}):(\d{2})\s*(AM|PM)", reset_raw, re.I)
    if bare:
        hour = int(bare.group(1)) + (12 if bare.group(3).upper() == "PM" and int(bare.group(1)) != 12 else 0) - (12 if bare.group(3).upper() == "AM" and int(bare.group(1)) == 12 else 0)
        cand = now.replace(hour=hour, minute=int(bare.group(2)), second=0, microsecond=0)
        if cand <= now:
            cand += timedelta(days=1)
        return cand
    raise ValueError(f"Cannot parse Codex reset: {reset_raw!r}")


# ── Formatting ────────────────────────────────────────────────────────

def fmt_dh(td: timedelta) -> str:
    total_h = td.total_seconds() / 3600
    days = int(total_h // 24)
    hours = int(total_h % 24)
    if days:
        return f"{days}d {hours}h"
    return f"{hours}h"


def fmt_dt(dt: datetime) -> str:
    return dt.strftime("%a %b %d, %I:%M %p")


def print_stats(claude: dict, codex: dict, now: datetime) -> None:
    # ── Parse ──
    # Claude
    claude_last, claude_next = parse_reset_claude(claude["reset_raw"], now)

    # Codex
    codex_short_reset = parse_reset_codex(codex["hour5_reset_raw"], now=now)
    codex_weekly_reset = parse_reset_codex(codex["weekly_reset_raw"], now=now)

    # ── Print ──
    _print_tool(
        name="CLAUDE (Pro)",
        short_label="Session",
        short_pct=claude["session_pct"],
        short_reset=None,
        weekly_pct=claude["weekly_pct"],
        weekly_last=claude_last,
        weekly_next=claude_next,
        now=now,
    )
    print()
    _print_tool(
        name="CODEX",
        short_label="5h limit",
        short_pct=100 - codex["hour5_remaining_pct"],
        short_reset=codex_short_reset,
        weekly_pct=100 - codex["weekly_remaining_pct"],
        weekly_last=codex_weekly_reset - timedelta(weeks=1),
        weekly_next=codex_weekly_reset,
        now=now,
    )


def _print_tool(
    *,
    name: str,
    short_label: str,
    short_pct: int,
    short_reset: datetime | None,
    weekly_pct: int,
    weekly_last: datetime,
    weekly_next: datetime,
    now: datetime,
) -> None:
    week_total = timedelta(weeks=1)
    elapsed = now - weekly_last
    pct_time = elapsed / week_total * 100
    burn = weekly_pct / pct_time if pct_time > 0 else 0
    direction = "OVER" if burn > 1 else "under"

    def _reset_suffix(dt: datetime) -> str:
        return f"  (resets {fmt_dt(dt)}, in {fmt_dh(dt - now)})"

    print(f"=== {name} ===")

    if short_reset:
        print(f"  {short_label:<11} {short_pct}% used{_reset_suffix(short_reset)}")
    else:
        print(f"  {short_label:<11} {short_pct}% used")

    print(f"  {'Weekly':<11} {weekly_pct}% used{_reset_suffix(weekly_next)}")
    print(f"  {'Elapsed':<11} {fmt_dh(elapsed)} / {fmt_dh(week_total)} ({pct_time:.1f}%)")
    print(f"  {'Burn':<11} {burn:.2f}× ({direction} pace)")

    if burn > 1 and weekly_pct < 100:
        remaining_pct = 100 - weekly_pct
        hours_left = remaining_pct / weekly_pct * elapsed.total_seconds() / 3600
        exhaust = now + timedelta(hours=hours_left)
        print(f"  {'Exhaustion':<11} {fmt_dt(exhaust)} (~{hours_left:.0f}h)")


# ── Picasso rendering ─────────────────────────────────────────────────

def _track(
    used_pct: float,
    elapsed_pct: float,
    *,
    session_pct: float = 0.0,
    session_offset_pct: float = 0.0,
    width: int = 50,
    session_used_style: str = "magenta",
    session_remaining_style: str = "magenta dim",
) -> Text:
    """One horizontal track with magenta session band (full blocks) anchored at ┊.

    Slack:    ━━━━●░░░░░░┊███───  (cells styled per session_*_style args)
    Scarcity: ━━━┊▓▓▓●███───      (gap wins inside ┊→● region)
    """
    u = max(0.0, min(100.0, used_pct))
    e = max(0.0, min(100.0, elapsed_pct))
    used_pos = round(u / 100 * (width - 1))
    elapsed_pos = round(e / 100 * (width - 1))
    over = used_pct > elapsed_pct
    lo, hi = min(used_pos, elapsed_pos), max(used_pos, elapsed_pos)

    band_start = elapsed_pos + 1
    proportional = round(session_offset_pct / 100 * width)
    band_width = max(8, proportional)
    band_end = min(band_start + band_width, width)
    sess_used_cells = int(session_pct / 100 * band_width)

    text = Text()
    for i in range(width):
        if used_pos == elapsed_pos and i == used_pos:
            text.append("◆", style="bold yellow")
        elif i == used_pos:
            text.append("●", style="bold bright_red" if over else "bold cyan")
        elif i == elapsed_pos:
            text.append("┊", style="bold white")
        elif lo < i < hi:
            text.append("▓" if over else "░", style="red" if over else "cyan")
        elif band_start <= i < band_end:
            is_used = (i - band_start) < sess_used_cells
            text.append("█", style=session_used_style if is_used else session_remaining_style)
        elif i < lo:
            text.append("━", style="white")
        else:
            text.append("─", style="grey39")
    return text


def _session_track(used_pct: float, elapsed_pct: float, width: int = 50) -> Text:
    """Session-scale track in magenta. Same anatomy as _track, no band overlay.

    Full width represents one session window (SESSION_DURATION).
    """
    u = max(0.0, min(100.0, used_pct))
    e = max(0.0, min(100.0, elapsed_pct))
    used_pos = round(u / 100 * (width - 1))
    elapsed_pos = round(e / 100 * (width - 1))
    over = used_pct > elapsed_pct
    lo, hi = min(used_pos, elapsed_pos), max(used_pos, elapsed_pos)

    text = Text()
    for i in range(width):
        if used_pos == elapsed_pos and i == used_pos:
            text.append("◆", style="bold yellow")
        elif i == used_pos:
            text.append("●", style="bold bright_magenta" if over else "bold magenta")
        elif i == elapsed_pos:
            text.append("┊", style="bold white")
        elif lo < i < hi:
            text.append("▓" if over else "░", style="bright_magenta" if over else "magenta")
        elif i < lo:
            text.append("━", style="white")
        else:
            text.append("─", style="grey39")
    return text


def _synth_gap_history(used_pct: float, elapsed_pct: float, samples: int = 50) -> list[float]:
    """Plausible (synthetic) gap-over-time history ending at the current gap."""
    random.seed(int(used_pct * 7919 + elapsed_pct * 6857))
    target = used_pct - elapsed_pct
    history = []
    drift = 0.0
    for i in range(samples):
        t = i / max(samples - 1, 1)
        drift += random.uniform(-2.5, 2.5)
        drift *= 0.85
        history.append(target * t + drift * (1 - t))
    history[-1] = target
    return history


def _sparkline(values: list[float], width: int) -> Text:
    """Magnitude as block height, sign as color. Red = scarcity, cyan = slack."""
    if not values:
        return Text(" " * width)
    if len(values) != width:
        step = (len(values) - 1) / max(width - 1, 1)
        values = [values[round(i * step)] for i in range(width)]
    max_abs = max((abs(v) for v in values), default=1.0) or 1.0
    blocks = "▁▂▃▄▅▆▇█"
    text = Text()
    for v in values:
        level = int(abs(v) / max_abs * (len(blocks) - 1))
        block = blocks[min(level, len(blocks) - 1)]
        if abs(v) < 1.0:
            text.append("·", style="grey39")
        elif v > 0:
            text.append(block, style="red")
        else:
            text.append(block, style="cyan")
    return text


def _picasso_row_data(claude: dict, codex: dict, now: datetime) -> list[tuple]:
    """Return [(name, used_pct, elapsed_pct, session_pct, session_offset_pct, session_elapsed_pct, next_reset, session_next), ...]."""
    week = timedelta(weeks=1)

    claude_last, claude_next = parse_reset_claude(claude["reset_raw"], now)
    claude_elapsed_pct = (now - claude_last) / week * 100
    claude_session_next = parse_reset_claude(claude["session_reset_raw"], now)[1]
    claude_session_offset = claude_session_next - now
    claude_session_offset_pct = claude_session_offset / week * 100
    claude_session_elapsed_pct = max(0.0, min(100.0, (1 - claude_session_offset / SESSION_DURATION) * 100))

    codex_next = parse_reset_codex(codex["weekly_reset_raw"], now=now)
    codex_last = codex_next - week
    codex_elapsed_pct = (now - codex_last) / week * 100
    codex_hour5_next = parse_reset_codex(codex["hour5_reset_raw"], now=now)
    codex_hour5_offset = codex_hour5_next - now
    codex_hour5_offset_pct = codex_hour5_offset / week * 100
    codex_hour5_elapsed_pct = max(0.0, min(100.0, (1 - codex_hour5_offset / SESSION_DURATION) * 100))

    return [
        ("CLAUDE",
         float(claude["weekly_pct"]),
         claude_elapsed_pct,
         float(claude["session_pct"]),
         claude_session_offset_pct,
         claude_session_elapsed_pct,
         claude_next,
         claude_session_next),
        ("CODEX",
         100 - float(codex["weekly_remaining_pct"]),
         codex_elapsed_pct,
         100 - float(codex["hour5_remaining_pct"]),
         codex_hour5_offset_pct,
         codex_hour5_elapsed_pct,
         codex_next,
         codex_hour5_next),
    ]


def print_picasso(claude: dict, codex: dict, now: datetime, *, console: Console) -> None:
    rows = _picasso_row_data(claude, codex, now)
    width = 50
    for idx, (name, used, elapsed, session, session_off, session_elapsed, next_reset, session_next) in enumerate(rows):
        if idx > 0:
            console.print()
        reset_str = f"resets {fmt_dh(next_reset - now)}"
        session_reset_str = f"resets {fmt_dh(session_next - now)}"
        weekly = _track(
            used, elapsed,
            session_pct=session,
            session_offset_pct=session_off,
            width=width,
            session_used_style="magenta",
            session_remaining_style="magenta dim",
        )
        session_view = _session_track(session, session_elapsed, width=width)
        console.print(Text(f"  {name:<7}  ", style="bold") + weekly + Text(f"  {reset_str}", style="dim"))
        console.print(Text(f"  {'':<7}  ") + session_view + Text(f"  {session_reset_str}", style="dim"))


# ── Main ──────────────────────────────────────────────────────────────

def main() -> None:
    try:
        claude_target = ensure_target(CLAUDE_URL)
    except RuntimeError as error:
        print(f"ERROR: Failed to prepare Claude usage tab: {error}", file=sys.stderr)
        sys.exit(1)
    try:
        claude_text = scrape_body(claude_target)
    except RuntimeError as error:
        print(f"ERROR: Failed to scrape Claude usage page: {error}", file=sys.stderr)
        sys.exit(1)
    try:
        claude = parse_claude(claude_text)
    except ValueError as error:
        print(f"ERROR: Failed to parse Claude usage page: {error}", file=sys.stderr)
        sys.exit(1)

    try:
        codex_target = ensure_target(CODEX_URL)
    except RuntimeError as error:
        print(f"ERROR: Failed to prepare Codex usage tab: {error}", file=sys.stderr)
        sys.exit(1)
    try:
        codex_text = scrape_body(codex_target)
    except RuntimeError as error:
        print(f"ERROR: Failed to scrape Codex usage page: {error}", file=sys.stderr)
        sys.exit(1)
    try:
        codex = parse_codex(codex_text)
    except ValueError as error:
        print(f"ERROR: Failed to parse Codex usage page: {error}", file=sys.stderr)
        sys.exit(1)

    now = datetime.now(tz=IDT)
    console = Console()

    console.print()
    print_picasso(claude, codex, now, console=console)


if __name__ == "__main__":
    main()
