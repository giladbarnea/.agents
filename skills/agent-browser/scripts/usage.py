#!/usr/bin/env -S uv run
# /// script
# requires-python = "==3.12.*"
# dependencies = ["python-dateutil", "rich"]
# ///

"""Scrape and compute AI usage limits for Claude and Codex.

Single idempotent script:
1. Launches Chrome with remote debugging if not already running
2. Opens Claude/Codex tabs if not already open, reloads if they are
3. Scrapes usage data, errors out if not logged in
4. Computes burn rates and exhaustion estimates
"""

import json
import random
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta
from dateutil import tz
from rich.console import Console
from rich.text import Text

IDT = tz.gettz("Asia/Jerusalem")
CDP_PORT = 9222
CHROME_CMD = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    f"--remote-debugging-port={CDP_PORT}",
    f"--user-data-dir=/Users/giladbarnea/.agent-browser/custom-debug-profile",
]
CLAUDE_URL = "https://claude.ai/settings/usage"
CODEX_URL = "https://chatgpt.com/codex/cloud/settings/analytics"


def _agent(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["agent-browser", "--cdp", str(CDP_PORT), *args],
        capture_output=True, text=True,
    )


def _agent_json(*args: str) -> dict:
    result = _agent(*args)
    return json.loads(result.stdout)


def _curl(url: str) -> subprocess.CompletedProcess:
    return subprocess.run(["curl", "-s", url], capture_output=True, text=True)


def chrome_is_reachable() -> bool:
    result = _curl(f"http://localhost:{CDP_PORT}/json/version")
    if result.returncode != 0:
        return False
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return False
    return bool(data.get("webSocketDebuggerUrl"))


def launch_chrome():
    print("Launching Chrome with remote debugging...", file=sys.stderr)
    subprocess.Popen(CHROME_CMD, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(30):
        time.sleep(1)
        if chrome_is_reachable():
            return
    print("ERROR: Chrome did not become reachable within 30s", file=sys.stderr)
    sys.exit(1)


def ensure_tab(url: str, url_substring: str) -> None:
    """Activate existing tab matching url_substring, or create a new one."""
    result = _agent_json("tab", "--json")
    tabs = result.get("data", {}).get("tabs", [])
    for tab in tabs:
        if url_substring in tab.get("url", ""):
            _agent("tab", tab["tabId"])
            _agent("reload")
            return
    print(f"Opening new tab: {url}", file=sys.stderr)
    _agent("tab", "new", url)


def scrape_body() -> str:
    result = _agent("get", "text", "body")
    return result.stdout


# ── Parsing ───────────────────────────────────────────────────────────

def _first_match(pattern: str, text: str, group: int = 1) -> str:
    m = re.search(pattern, text, re.DOTALL)
    if not m:
        raise ValueError(f"Pattern not found: {pattern!r}")
    return m.group(group)


def parse_claude(text: str) -> dict:
    """Extract Claude usage stats from raw body text."""
    session_match = re.search(
        r"Current session\s*Resets\s+(.+?)\s*(\d+)%\s*used", text, re.DOTALL
    )
    if not session_match:
        raise ValueError("Cannot find Claude 'Current session' block")
    session_reset_raw = session_match.group(1).strip()
    session_pct = int(session_match.group(2))

    weekly_match = re.search(
        r"Weekly limits.*?Resets\s+(.+?)\s*(\d+)%\s*used", text, re.DOTALL
    )
    if not weekly_match:
        raise ValueError("Cannot find Claude 'Weekly limits' block")
    reset_raw = weekly_match.group(1).strip()
    weekly_pct = int(weekly_match.group(2))

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
    rel = re.match(r"in\s+(\d+)\s*hr(?:\s+(\d+)\s*min)?", reset_raw, re.I)
    if rel:
        hours = int(rel.group(1))
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
) -> Text:
    """One horizontal track with magenta session band anchored at ┊.

    Slack:    ━━━━●░░░░░░┊███───  (band cells: dim magenta = used, black = remaining)
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
    band_width = max(4, proportional)
    band_end = min(band_start + band_width, width)
    sess_used_cells = round(session_pct / 100 * band_width)

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
            text.append("█", style="magenta dim" if is_used else "black")
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
    """Return [(name, used_pct, elapsed_pct, session_pct, session_offset_pct, next_reset), ...]."""
    week = timedelta(weeks=1)

    claude_last, claude_next = parse_reset_claude(claude["reset_raw"], now)
    claude_elapsed_pct = (now - claude_last) / week * 100
    claude_session_next = parse_reset_claude(claude["session_reset_raw"], now)[1]
    claude_session_offset_pct = (claude_session_next - now) / week * 100

    codex_next = parse_reset_codex(codex["weekly_reset_raw"], now=now)
    codex_last = codex_next - week
    codex_elapsed_pct = (now - codex_last) / week * 100
    codex_hour5_next = parse_reset_codex(codex["hour5_reset_raw"], now=now)
    codex_hour5_offset_pct = (codex_hour5_next - now) / week * 100

    return [
        ("CLAUDE",
         float(claude["weekly_pct"]),
         claude_elapsed_pct,
         float(claude["session_pct"]),
         claude_session_offset_pct,
         claude_next),
        ("CODEX",
         100 - float(codex["weekly_remaining_pct"]),
         codex_elapsed_pct,
         100 - float(codex["hour5_remaining_pct"]),
         codex_hour5_offset_pct,
         codex_next),
    ]


def print_picasso(claude: dict, codex: dict, now: datetime, *, console: Console) -> None:
    rows = _picasso_row_data(claude, codex, now)
    width = 50
    for name, used, elapsed, session, session_off, next_reset in rows:
        reset_str = f"resets {fmt_dh(next_reset - now)}"
        track = _track(
            used, elapsed,
            session_pct=session,
            session_offset_pct=session_off,
            width=width,
        )
        console.print(Text(f"  {name:<7}  ", style="bold") + track + Text(f"  {reset_str}", style="dim"))


# ── Main ──────────────────────────────────────────────────────────────

def main() -> None:
    if not chrome_is_reachable():
        launch_chrome()

    # Claude
    ensure_tab(CLAUDE_URL, "claude.ai/settings/usage")
    time.sleep(3)
    claude_text = scrape_body()
    try:
        claude = parse_claude(claude_text)
    except ValueError as e:
        print(f"ERROR: Failed to parse Claude usage — likely not logged in: {e}", file=sys.stderr)
        sys.exit(1)

    # Codex
    ensure_tab(CODEX_URL, "chatgpt.com/codex/cloud/settings/analytics")
    time.sleep(3)
    codex_text = scrape_body()
    try:
        codex = parse_codex(codex_text)
    except ValueError as e:
        print(f"ERROR: Failed to parse Codex usage — likely not logged in: {e}", file=sys.stderr)
        sys.exit(1)

    now = datetime.now(tz=IDT)
    console = Console()

    console.print()
    print_picasso(claude, codex, now, console=console)
    console.print()

    console.rule("[bold] legacy text (for reference) [/bold]", style="grey50")
    console.print()
    print_stats(claude, codex, now)


if __name__ == "__main__":
    main()
