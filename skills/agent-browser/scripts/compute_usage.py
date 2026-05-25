#!/usr/bin/env -S uv run
# /// script
# requires-python = "==3.12.*"
# dependencies = ["python-dateutil"]
# ///

"""Compute AI usage burn rates and cap-exhaustion estimates.

Reads the raw text from scrape_usage.sh on stdin, parses Claude and Codex
usage percentages and reset times, computes elapsed time and burn ratios.
When the burn rate exceeds linear pace, estimates when the quota will be
exhausted.

Usage:
    scrape_usage.sh | uv run compute_usage.py
"""

import re
import sys
from datetime import datetime, timedelta
from dateutil import tz

IDT = tz.gettz("Asia/Jerusalem")


# ── Parsing ───────────────────────────────────────────────────────────

def _first_match(pattern: str, text: str, group: int = 1) -> str:
    m = re.search(pattern, text, re.DOTALL)
    if not m:
        raise ValueError(f"Pattern not found: {pattern!r}")
    return m.group(group)


def parse_claude(text: str) -> dict:
    """Extract Claude usage stats from raw body text."""
    session_pct = int(_first_match(r"Current session.*?(\d+)%\s*used", text))
    weekly_pct  = int(_first_match(r"Weekly limits.*?(\d+)%\s*used", text))
    reset_raw   = _first_match(r"Weekly limits.*?Resets\s+(.+?)\n", text).strip()
    return {"session_pct": session_pct, "weekly_pct": weekly_pct, "reset_raw": reset_raw}


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
    """Given 'Wed 8:00 PM', return (last_reset, next_reset)."""
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
    return f"{int(total_h // 24)}d {int(total_h % 24)}h"


def fmt_dt(dt: datetime) -> str:
    return dt.strftime("%a %b %d, %I:%M %p")


def print_stats(claude: dict, codex: dict, now: datetime) -> None:
    # ── Claude ──
    claude_last, claude_next = parse_reset_claude(claude["reset_raw"], now)
    claude_elapsed = now - claude_last
    claude_total = claude_next - claude_last
    claude_pct_time = claude_elapsed / claude_total * 100
    claude_burn = claude["weekly_pct"] / claude_pct_time

    print("=== CLAUDE (Pro) ===")
    print(f"  Week:      {fmt_dt(claude_last)} → {fmt_dt(claude_next)}")
    print(f"  Elapsed:   {fmt_dh(claude_elapsed)} / {fmt_dh(claude_total)} ({claude_pct_time:.1f}%)")
    print(f"  Session:   {claude['session_pct']}% used")
    print(f"  Weekly:    {claude['weekly_pct']}% used")
    direction = "OVER" if claude_burn > 1 else "under"
    print(f"  Burn:      {claude_burn:.2f}× ({direction} pace)")

    if claude_burn > 1 and claude["weekly_pct"] < 100:
        remaining_pct = 100 - claude["weekly_pct"]
        hours_left = remaining_pct / claude["weekly_pct"] * claude_elapsed.total_seconds() / 3600
        exhaust = now + timedelta(hours=hours_left)
        print(f"  Exhaustion: {fmt_dt(exhaust)} (~{hours_left:.0f}h)")

    # ── Codex ──
    hour5_reset = parse_reset_codex(codex["hour5_reset_raw"], now=now)
    hour5_remaining = timedelta(hours=5) * codex["hour5_remaining_pct"] / 100
    hour5_used_pct = 100 - codex["hour5_remaining_pct"]

    weekly_reset = parse_reset_codex(codex["weekly_reset_raw"], now=now)
    week_last = weekly_reset - timedelta(weeks=1)
    week_total = timedelta(weeks=1)
    weekly_elapsed = now - week_last
    weekly_used_pct = 100 - codex["weekly_remaining_pct"]
    weekly_pct_time = weekly_elapsed / week_total * 100
    weekly_burn = weekly_used_pct / weekly_pct_time if weekly_pct_time > 0 else 0

    print()
    print("=== CODEX ===")
    print(f"  5h rolling: {codex['hour5_remaining_pct']}% remaining ({fmt_dh(hour5_remaining)} left, resets {fmt_dt(hour5_reset)}, in {fmt_dh(hour5_reset - now)})")
    print(f"  5h used:    {hour5_used_pct}%")
    print(f"  Week:       {fmt_dt(week_last)} → {fmt_dt(weekly_reset)}")
    print(f"  Elapsed:    {fmt_dh(weekly_elapsed)} / {fmt_dh(week_total)} ({weekly_pct_time:.1f}%)")
    print(f"  Weekly:     {codex['weekly_remaining_pct']}% remaining ({weekly_used_pct}% used)")
    direction = "OVER" if weekly_burn > 1 else "under"
    print(f"  Burn:       {weekly_burn:.2f}× ({direction} pace)")

    if weekly_burn > 1 and weekly_used_pct < 100:
        remaining_pct = 100 - weekly_used_pct
        hours_left = remaining_pct / weekly_used_pct * weekly_elapsed.total_seconds() / 3600
        exhaust = now + timedelta(hours=hours_left)
        print(f"  Exhaustion: {fmt_dt(exhaust)} (~{hours_left:.0f}h)")


# ── Main ──────────────────────────────────────────────────────────────

def main() -> None:
    raw = sys.stdin.read()
    now = datetime.now(tz=IDT)

    try:
        claude_section = raw.split("=== CLAUDE ===", 1)[1].split("=== CODEX ===", 1)[0]
        codex_section = raw.split("=== CODEX ===", 1)[1]
    except IndexError:
        print("ERROR: Could not split input into Claude/Codex sections. Did you pipe scrape_usage.sh?", file=sys.stderr)
        sys.exit(1)

    try:
        claude = parse_claude(claude_section)
    except ValueError as e:
        print(f"ERROR: Failed to parse Claude section: {e}", file=sys.stderr)
        print(claude_section, file=sys.stderr)
        sys.exit(1)

    try:
        codex = parse_codex(codex_section)
    except ValueError as e:
        print(f"ERROR: Failed to parse Codex section: {e}", file=sys.stderr)
        print(codex_section, file=sys.stderr)
        sys.exit(1)

    print_stats(claude, codex, now)


if __name__ == "__main__":
    main()
