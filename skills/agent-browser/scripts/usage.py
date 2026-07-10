#!/usr/bin/env -S uv run
# /// script
# requires-python = "==3.12.*"
# dependencies = ["pycryptodome", "python-dateutil", "requests", "rich", "websocket-client"]
# ///

"""Read and render AI usage limits for Claude, Codex and OpenRouter.

Claude and Codex use two strategies, tried in order:
1. Hit the JSON usage endpoints directly, authenticated with cookies decrypted
   from the logged-in Chrome profile on disk (no browser process required).
2. Fall back to driving the already-open Chrome tabs over CDP and scraping the
   rendered usage text.

OpenRouter has no rate windows — just a balance that drains — so it gets a cumulative
budget model instead, chosen deliberately:

- Metric: lifetime spend since a fixed anchor, measured against an allowance that accrues
  at $20 per 30 days. Burn rate = spent / accrued-allowance. A past overspend keeps
  weighing on the rate until enough time passes to absorb it — it never forgets. (A rolling
  30-day window was rejected for the opposite reason: a binge silently vanishes once it
  scrolls out of the trailing window.)
- Source: spent = total_usage_now - OPENROUTER_ANCHOR_TOTAL_USAGE, both from /api/v1/credits,
  which reports cumulative all-time usage. Top-ups are intentionally invisible — refilling
  credits doesn't change what you've already spent, only usage does. Using total_usage also
  sidesteps /api/v1/activity's ~30-day history cap, which can't reach a months-old anchor.
- Constants (not derivable, must be hardcoded): OPENROUTER_ANCHOR_DATE is the user's chosen
  "start of discipline"; OPENROUTER_ANCHOR_TOTAL_USAGE is total_usage as it stood that day,
  back-computed once from activity while still in range; OPENROUTER_BUDGET is the $20/month
  self-imposed cap. No reset concept — the window only opens, so OpenRouter shows no ↻.

Burn-rate smoothing: each displayed burn rate carries a Bayesian-shrinkage companion
(the ×B value), (used + m) / (elapsed + m), which shrinks toward a 1.0× prior so a
fresh window doesn't scream 5× after one burst. The pseudo-elapsed weight m is derived
per provider at every invocation from the last four weeks of local transcripts
(Claude Code, Codex CLI, and Pi sessions — Pi activity is attributed per assistant
message, so mid-session model switches don't leak across providers).
"""

import argparse
import dataclasses
import json
import math
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence
from dateutil import tz
from Crypto.Cipher import AES
from Crypto.Hash import SHA1
from Crypto.Protocol.KDF import PBKDF2
import requests
from rich.console import Console
from rich.text import Text
import websocket

IDT = tz.gettz("Asia/Jerusalem")
UTC = timezone.utc
# Direct CDP lets us scrape the real logged-in Chrome tabs without headless bot checks.
CDP_PORT = 9222
CDP_BASE_URL = f"http://localhost:{CDP_PORT}"
PAGE_LOAD_DELAY_SECONDS = 3
CLAUDE_URL = "https://claude.ai/new#settings/usage"
CODEX_URL = "https://chatgpt.com/codex/cloud/settings/analytics"
SESSION_DURATION = timedelta(hours=5)
BODY_TEXT_EXPRESSION = "document.body.innerText"
SCRAPE_READY_TIMEOUT_SECONDS = 30
SCRAPE_POLL_SECONDS = 1
PICASSO_RESET_DURATION_WIDTH = len("28d 23h")
CHROME_COOKIES_DB = os.path.expanduser("~/.agent-browser/custom-debug-profile/Default/Cookies")
OPENROUTER_MANAGEMENT_KEY_PATH = os.path.expanduser("~/.openrouter-management-key")
OPENROUTER_BUDGET = 20.0  # dollars of allowance accrued per 30 days
OPENROUTER_WINDOW = timedelta(days=30)
# Cumulative budget anchor: spending discipline starts here and never forgets.
# total_usage as it stood on the anchor date; spent-since = total_usage_now - this.
OPENROUTER_ANCHOR_DATE = datetime(2026, 5, 23, tzinfo=IDT)
OPENROUTER_ANCHOR_TOTAL_USAGE = 139.897
BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36"
)

# Bayesian burn-rate smoothing: m is the pseudo-elapsed percent of window carrying a 1.0×
# prior — at elapsed == m the prior and observed data weigh equally. m is derived per
# provider at each invocation from the last BURN_SMOOTHING_LOOKBACK of transcripts: the
# weekly m rides BURN_SMOOTHING_GAP_MARGIN above the p95 routine inter-burst gap (so a
# normal night away doesn't spike the ratio), the session m sits at
# BURN_SMOOTHING_LULL_FRACTION of the median largest intra-window lull (so it absorbs the
# front-load burst yet releases before genuine signal takes over). Clamp bands come from
# the June–July 2026 empirical analysis: one day-night cycle ≈ 15% of a week; sparse
# marathon-and-dry-spell regimes justify at most 25.
BURN_SMOOTHING_DEFAULT_PCT = 15.0
BURN_SMOOTHING_WEEKLY_BAND = (15.0, 25.0)
BURN_SMOOTHING_SESSION_BAND = (15.0, 20.0)
BURN_SMOOTHING_SANITY_BAND = (10.0, 20.0)  # a derived m at or beyond either edge smells like broken derivation
BURN_SMOOTHING_GAP_MARGIN = 1.25
BURN_SMOOTHING_LULL_FRACTION = 0.75
BURN_SMOOTHING_LOOKBACK = timedelta(weeks=4)
BURST_GAP = timedelta(minutes=20)
CLAUDE_TRANSCRIPT_ROOTS = (Path("~/.claude/projects"),)
CODEX_TRANSCRIPT_ROOTS = (Path("~/.codex/sessions"), Path("~/.codex/.tmp"))
PI_TRANSCRIPT_ROOTS = (Path("~/.pi/agent/sessions"),)

UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)


@dataclasses.dataclass(frozen=True)
class BrowserTarget:
    target_id: str
    title: str
    url: str
    websocket_debugger_url: str


@dataclasses.dataclass(frozen=True)
class Limit:
    """A usage window: percent spent, when the window opened, and how long it runs.

    resets=True windows (Claude/Codex rate limits) show a ↻ countdown to the next reset.
    resets=False windows (OpenRouter's cumulative budget) only accrue, so elapsed_pct can
    exceed 100 — the bar clamps, but the burn-rate label keeps the true ratio.
    """
    used_pct: float
    window_start: datetime
    window_duration: timedelta = timedelta(weeks=1)
    resets: bool = True
    smoothing_m: float = BURN_SMOOTHING_DEFAULT_PCT

    @classmethod
    def until(cls, used_pct: float, next_reset: datetime,
              window_duration: timedelta = timedelta(weeks=1)) -> "Limit":
        """Construct a resetting rate window from the moment it next resets."""
        return cls(used_pct, next_reset - window_duration, window_duration)

    @property
    def next_reset(self) -> datetime:
        return self.window_start + self.window_duration

    def elapsed_pct(self, now: datetime) -> float:
        return (now - self.window_start) / self.window_duration * 100


@dataclasses.dataclass(frozen=True)
class Usage:
    name: str
    session: Limit | None  # 5-hour / current-session window; None for providers without sessions
    weekly: Limit


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


def is_claude_usage_url(url: str) -> bool:
    parsed_url = urllib.parse.urlparse(url)
    return parsed_url.netloc == "claude.ai" and (
        parsed_url.path == "/settings/usage" or parsed_url.fragment == "settings/usage"
    )


def target_matches_url(target: BrowserTarget, url: str) -> bool:
    if url == CLAUDE_URL:
        return is_claude_usage_url(target.url)
    return target.url == url


def find_target(url: str) -> BrowserTarget | None:
    for target in list_page_targets():
        if target_matches_url(target, url):
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


def scrape_body(target: BrowserTarget, ready_text: str) -> str:
    deadline = time.monotonic() + SCRAPE_READY_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
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
        if ready_text in value:
            return value
        time.sleep(SCRAPE_POLL_SECONDS)
    raise RuntimeError(f"Timed out waiting for {ready_text!r} on {target.url}")


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
    """Extract Codex usage stats from raw body text.

    The 'Resets ...' line is omitted by Codex when the limit is fresh (no usage),
    so reset_raw fields can be None.
    """
    hour5_pct = int(_first_match(r"5\s*hour\s*usage\s*limit.*?(\d+)\s*%\s*remaining", text))
    hour5_reset_match = re.search(r"5\s*hour\s*usage\s*limit.*?Resets\s+(.+?)\n", text, re.DOTALL)
    hour5_reset = hour5_reset_match.group(1).strip() if hour5_reset_match else None

    weekly_pct = int(_first_match(r"Weekly\s*usage\s*limit.*?(\d+)\s*%\s*remaining", text))
    weekly_reset_match = re.search(r"Weekly\s*usage\s*limit.*?Resets\s+(.+?)\n", text, re.DOTALL)
    weekly_reset = weekly_reset_match.group(1).strip() if weekly_reset_match else None

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
    total_seconds = td.total_seconds()
    days = int(total_seconds // 86400)
    hours = int(total_seconds % 86400 // 3600)
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h"
    minutes = int(total_seconds % 3600 // 60)
    return f"{minutes}m"


def _isoformat_seconds(value: datetime) -> str:
    """Return a timezone-aware ISO timestamp at second precision.

    >>> _isoformat_seconds(datetime(2026, 1, 1, 1, 2, 3, 456789, tzinfo=IDT))
    '2026-01-01T01:02:03+02:00'
    """
    return value.isoformat(timespec="seconds")


def _duration_json(value: timedelta) -> dict[str, object]:
    return {
        "seconds": round(value.total_seconds()),
        "human": fmt_dh(value),
    }


def smoothed_burn_rate(used_pct: float, elapsed_pct: float, smoothing_m: float) -> float:
    """Burn rate shrunk toward a 1.0× prior; converges to used/elapsed as the window fills.

    >>> smoothed_burn_rate(6.0, 1.2, 15.0)
    1.2962962962962963
    """
    return (used_pct + smoothing_m) / (elapsed_pct + smoothing_m)


def _limit_json(limit: Limit, now: datetime) -> dict[str, object]:
    elapsed_percent = limit.elapsed_pct(now)
    burn_rate = limit.used_pct / elapsed_percent if elapsed_percent > 0 else None
    reset_at = _isoformat_seconds(limit.next_reset) if limit.resets else None
    remaining = limit.next_reset - now
    remaining_json = {
        "seconds": round(remaining.total_seconds()),
        "human": fmt_dh(remaining),
    } if limit.resets else None

    return {
        "used_percent": round(limit.used_pct, 2),
        "elapsed_percent": round(elapsed_percent, 2),
        "burn_rate": round(burn_rate, 4) if burn_rate is not None else None,
        "burn_rate_smoothed": round(
            smoothed_burn_rate(limit.used_pct, elapsed_percent, limit.smoothing_m), 4
        ),
        "burn_smoothing_m": round(limit.smoothing_m, 2),
        "over_elapsed_pace": limit.used_pct > elapsed_percent,
        "resets": limit.resets,
        "started_at": _isoformat_seconds(limit.window_start),
        "ends_at": reset_at,
        "reset_at": reset_at,
        "elapsed_reference_end_at": _isoformat_seconds(limit.next_reset),
        "duration": _duration_json(limit.window_duration),
        "remaining": remaining_json,
    }


def _usage_json(usage: Usage, now: datetime) -> dict[str, object]:
    return {
        "name": usage.name,
        "windows": {
            "weekly": _limit_json(usage.weekly, now),
            "session": _limit_json(usage.session, now) if usage.session is not None else None,
        },
    }


def _usage_report_json(
    usages: list[Usage],
    now: datetime,
    *,
    warnings: list[str],
    claude_codex_source: str,
    openrouter_source: str,
) -> dict[str, object]:
    return {
        "generated_at": _isoformat_seconds(now),
        "timezone": "Asia/Jerusalem",
        "sources": {
            "claude_codex": claude_codex_source,
            "openrouter": openrouter_source,
        },
        "warnings": warnings,
        "providers": [_usage_json(usage, now) for usage in usages],
    }


# ── Picasso rendering ─────────────────────────────────────────────────

def _track(used_pct: float, elapsed_pct: float, width: int = 50) -> Text:
    """One horizontal week-scale track.

    Slack:    ━━━━●░░░░░░┊──────
    Scarcity: ━━━┊▓▓▓●──────
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
            text.append("●", style="bold bright_red" if over else "bold cyan")
        elif i == elapsed_pos:
            text.append("┊", style="bold white")
        elif lo < i < hi:
            text.append("▓" if over else "░", style="red" if over else "cyan")
        elif i < lo:
            text.append("━", style="white")
        else:
            text.append("─", style="grey39")
    return text


def _label(
    used_pct: float,
    elapsed_pct: float,
    *,
    width: int = 50,
    used_style_slack: str = "cyan",
    used_style_over: str = "bright_red",
    smoothing_m: float = BURN_SMOOTHING_DEFAULT_PCT,
) -> Text:
    """Glyph-tagged atoms (●used% ┊elapsed%) + raw and B-smoothed burn rates.

    >>> _label(164.53, 141.08, width=36).plain
    '●165% ┊141% · 1.17× · 1.15×B'
    """
    used_pos = round(max(0.0, min(100.0, used_pct)) / 100 * (width - 1))
    elapsed_pos = round(max(0.0, min(100.0, elapsed_pct)) / 100 * (width - 1))
    over = used_pct > elapsed_pct

    used_label = f"{round(used_pct)}%"
    elapsed_label = f"{round(elapsed_pct)}%"

    text = Text()
    if used_pos == elapsed_pos and used_label == elapsed_label:
        text.append("◆", style="yellow")
        text.append(f"{used_label:>3}", style="dim")
    else:
        text.append("●", style=used_style_over if over else used_style_slack)
        text.append(f"{used_label:>3} ", style="dim")
        text.append("┊", style="white")
        text.append(f"{elapsed_label:>3}", style="dim")
    if elapsed_pct >= 1:
        burn = used_pct / elapsed_pct
        text.append(" · ", style="black")
        text.append(f"{burn:.2f}×", style="dim")
    text.append(" · ", style="black")
    text.append(f"{smoothed_burn_rate(used_pct, elapsed_pct, smoothing_m):.2f}×", style="dim")
    text.append("B", style="dim")
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


DEFAULT_PICASSO_WIDTH = 36
PICASSO_RESERVED_COLUMNS = 51


def _parse_positive_int(raw_value: str | None) -> int | None:
    """Parse a positive integer environment variable value."""
    try:
        value = int(raw_value or "")
    except ValueError:
        return None
    return value if value > 0 else None


def _parse_picasso_width(raw_width: str | None, raw_columns: str | None) -> int:
    """Parse the meter width, shrinking to fit the terminal when its width is known.

    The resolved width is capped by the configured/default width and by the
    available terminal space after reserving 51 columns for non-meter content.

    >>> _parse_picasso_width(None, None)
    36
    >>> _parse_picasso_width("42", None)
    42
    >>> _parse_picasso_width("oops", None)
    36
    >>> _parse_picasso_width(None, "65")
    14
    >>> _parse_picasso_width(None, "90")
    36
    >>> _parse_picasso_width("50", "65")
    14
    >>> _parse_picasso_width(None, "0")
    36
    """
    configured_width = _parse_positive_int(raw_width) or DEFAULT_PICASSO_WIDTH
    columns = _parse_positive_int(raw_columns)
    if columns is None:
        return configured_width
    return max(1, min(configured_width, columns - PICASSO_RESERVED_COLUMNS))


def _picasso_line(
    label: str,
    limit: Limit,
    now: datetime,
    *,
    track,
    slack: str,
    over: str,
    picasso_width: int,
) -> Text:
    """One track line: name, bar, optional ↻ countdown (omitted when the window never resets), legend."""
    elapsed = limit.elapsed_pct(now)
    bar = track(limit.used_pct, elapsed, width=picasso_width)
    legend = _label(limit.used_pct, elapsed, width=picasso_width,
                    used_style_slack=slack, used_style_over=over,
                    smoothing_m=limit.smoothing_m)

    text = Text(f" {label:<7}  ", style="bold") + bar + Text("  ")
    if limit.resets:
        text += Text(f"↻ {fmt_dh(limit.next_reset - now):>{PICASSO_RESET_DURATION_WIDTH}}", style="dim")
        text += Text(" · ", style="black")
    return text + legend


def print_picasso(usages: list[Usage], now: datetime, *, console: Console, picasso_width: int) -> None:
    for idx, usage in enumerate(usages):
        if idx > 0:
            console.print()
        console.print(_picasso_line(usage.name, usage.weekly, now,
                                    track=_track, slack="cyan", over="bright_red", picasso_width=picasso_width))
        if usage.session is not None:
            console.print(_picasso_line("", usage.session, now,
                                        track=_session_track, slack="magenta", over="bright_magenta", picasso_width=picasso_width))


# ── Option 1: direct API via decrypted Chrome cookies ─────────────────

def _safe_storage_key() -> bytes:
    """Derive Chrome's macOS cookie-encryption key from the Keychain secret."""
    password = subprocess.check_output(
        ["security", "find-generic-password", "-w", "-s", "Chrome Safe Storage"]
    ).strip()
    return PBKDF2(password, b"saltysalt", dkLen=16, count=1003, hmac_hash_module=SHA1)


def _decrypt_cookie(value: bytes, key: bytes) -> str:
    if value[:3] != b"v10":
        return value.decode("utf-8", "replace")
    plain = AES.new(key, AES.MODE_CBC, b" " * 16).decrypt(value[3:])
    plain = plain[: -plain[-1]]  # strip PKCS7 padding
    # Chrome 130+ on macOS prepends a 32-byte SHA256(host) integrity prefix.
    try:
        return plain[32:].decode("utf-8")
    except UnicodeDecodeError:
        return plain.decode("utf-8", "replace")


def _authenticated_session(host_substring: str) -> requests.Session:
    """Build a session carrying the logged-in Chrome cookies for hosts matching host_substring.

    Cookies stay domain-scoped (not flattened by name) so per-subdomain Cloudflare
    tokens like __cf_bm on .chatgpt.com vs .ws.chatgpt.com don't clobber each other,
    which otherwise sends the wrong bot token and trips an intermittent 403.
    """
    key = _safe_storage_key()
    with tempfile.NamedTemporaryFile(suffix=".db") as snapshot:
        shutil.copy(CHROME_COOKIES_DB, snapshot.name)  # copy to dodge Chrome's WAL lock
        connection = sqlite3.connect(snapshot.name)
        rows = connection.execute(
            "SELECT host_key, name, encrypted_value FROM cookies WHERE host_key LIKE ?",
            (f"%{host_substring}%",),
        ).fetchall()
        connection.close()

    session = requests.Session()
    session.headers.update({"User-Agent": BROWSER_UA, "Accept": "application/json"})
    for host_key, name, value in rows:
        session.cookies.set(name, _decrypt_cookie(value, key), domain=host_key)
    return session


def _claude_usage_json() -> dict:
    session = _authenticated_session("claude.ai")
    organizations = session.get("https://claude.ai/api/organizations", timeout=20)
    organizations.raise_for_status()
    org_list = organizations.json()
    organization = next((org for org in org_list if not org.get("archived_at")), org_list[0])
    response = session.get(f"https://claude.ai/api/organizations/{organization['uuid']}/usage", timeout=20)
    response.raise_for_status()
    return response.json()


def _codex_rate_limit_json() -> dict:
    session = _authenticated_session("chatgpt.com")
    auth = session.get("https://chatgpt.com/api/auth/session", timeout=20)
    auth.raise_for_status()
    access_token = auth.json()["accessToken"]
    response = session.get(
        "https://chatgpt.com/backend-api/wham/usage",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=20,
    )
    response.raise_for_status()
    return response.json()["rate_limit"]


def _claude_reset_datetime(reset_raw: str | None, now: datetime, window_duration: timedelta) -> datetime:
    """Parse Claude's reset timestamp, using now+window when no window has started yet.

    >>> _claude_reset_datetime(None, datetime(2026, 1, 1, tzinfo=IDT), SESSION_DURATION).isoformat()
    '2026-01-01T05:00:00+02:00'
    """
    if reset_raw is None:
        return now + window_duration
    return datetime.fromisoformat(reset_raw).astimezone(IDT)


def fetch_via_cookies(now: datetime) -> list[Usage]:
    """First-line: read usage straight from the JSON endpoints, no browser process needed."""
    claude = _claude_usage_json()
    codex = _codex_rate_limit_json()
    claude_session_reset = _claude_reset_datetime(claude["five_hour"]["resets_at"], now, SESSION_DURATION)
    claude_weekly_reset = _claude_reset_datetime(claude["seven_day"]["resets_at"], now, timedelta(weeks=1))
    return [
        Usage(
            name="CLAUDE",
            session=Limit.until(float(claude["five_hour"]["utilization"]),
                                claude_session_reset,
                                SESSION_DURATION),
            weekly=Limit.until(float(claude["seven_day"]["utilization"]),
                               claude_weekly_reset),
        ),
        Usage(
            name="CODEX",
            session=Limit.until(float(codex["primary_window"]["used_percent"]),
                                datetime.fromtimestamp(codex["primary_window"]["reset_at"], tz=IDT),
                                SESSION_DURATION),
            weekly=Limit.until(float(codex["secondary_window"]["used_percent"]),
                               datetime.fromtimestamp(codex["secondary_window"]["reset_at"], tz=IDT)),
        ),
    ]


# ── Option 2 (fallback): drive logged-in Chrome tabs over CDP and scrape ──

def scrape_via_browser(now: datetime) -> list[Usage]:
    claude = parse_claude(scrape_body(ensure_target(CLAUDE_URL), "Current session"))
    codex = parse_codex(scrape_body(ensure_target(CODEX_URL), "Codex Analytics"))

    codex_session_next = (
        parse_reset_codex(codex["hour5_reset_raw"], now=now)
        if codex["hour5_reset_raw"] else now + SESSION_DURATION
    )
    codex_weekly_next = (
        parse_reset_codex(codex["weekly_reset_raw"], now=now)
        if codex["weekly_reset_raw"] else now + timedelta(weeks=1)
    )
    return [
        Usage(
            name="CLAUDE",
            session=Limit.until(float(claude["session_pct"]), parse_reset_claude(claude["session_reset_raw"], now)[1],
                                SESSION_DURATION),
            weekly=Limit.until(float(claude["weekly_pct"]), parse_reset_claude(claude["reset_raw"], now)[1]),
        ),
        Usage(
            name="CODEX",
            session=Limit.until(100 - float(codex["hour5_remaining_pct"]), codex_session_next,
                                SESSION_DURATION),
            weekly=Limit.until(100 - float(codex["weekly_remaining_pct"]), codex_weekly_next),
        ),
    ]


# ── OpenRouter: cumulative budget anchored at a fixed start date ──────

def _openrouter_usage(now: datetime) -> Usage:
    """Cumulative spend since the anchor vs an accruing $20/30d budget (rationale in module docstring)."""
    management_key = open(OPENROUTER_MANAGEMENT_KEY_PATH).read().strip()
    response = requests.get(
        "https://openrouter.ai/api/v1/credits",
        headers={"Authorization": f"Bearer {management_key}"},
        timeout=20,
    )
    response.raise_for_status()
    spent = float(response.json()["data"]["total_usage"]) - OPENROUTER_ANCHOR_TOTAL_USAGE
    used_pct = spent / OPENROUTER_BUDGET * 100
    return Usage(
        name="OPENR",
        session=None,
        weekly=Limit(used_pct, OPENROUTER_ANCHOR_DATE, OPENROUTER_WINDOW, resets=False),
    )


# ── Transcript scanning (feeds burn-smoothing m) ──────────────────────
# One Event = one assistant/model response, the comparable activity unit across
# Claude Code, Codex CLI, and Pi logs. Pi events are attributed per assistant
# message (each self-tags provider/model), so mid-session model switches don't
# leak across providers.

@dataclasses.dataclass(frozen=True, slots=True)
class Event:
    timestamp: datetime
    provider: str
    source: str
    model: str
    tokens: int
    session_id: str
    event_id: str


@dataclasses.dataclass(slots=True)
class ScanStats:
    roots: list[str] = dataclasses.field(default_factory=list)
    roots_missing: list[str] = dataclasses.field(default_factory=list)
    files_considered: int = 0
    files_read: int = 0
    files_skipped_by_mtime: int = 0
    files_with_events: int = 0
    lines_read: int = 0
    candidate_lines: int = 0
    parse_errors: int = 0
    events_before_dedup: int = 0
    events_after_dedup: int = 0
    fallback_events: int = 0


def parse_timestamp(value: Any) -> datetime | None:
    """Parse ISO-8601 strings or epoch seconds/milliseconds/microseconds."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        magnitude = abs(number)
        if magnitude > 1e14:  # microseconds
            number /= 1_000_000
        elif magnitude > 1e11:  # milliseconds
            number /= 1_000
        try:
            return datetime.fromtimestamp(number, tz=UTC)
        except (OverflowError, OSError, ValueError):
            return None
    if not isinstance(value, str):
        return None
    raw = value.strip()
    if not raw:
        return None
    if re.fullmatch(r"-?\d+(?:\.\d+)?", raw):
        try:
            return parse_timestamp(float(raw))
        except ValueError:
            return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        # Some emitters use more than six fractional digits. Trim to microseconds.
        match = re.match(r"^(.*?\.\d{6})\d*(Z|[+-]\d\d:\d\d)?$", value.strip())
        if not match:
            return None
        repaired = match.group(1) + (match.group(2) or "+00:00")
        if repaired.endswith("Z"):
            repaired = repaired[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(repaired)
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def session_id_for(path: Path) -> str:
    matches = UUID_RE.findall(path.name)
    return matches[-1].lower() if matches else path.stem


def positive_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return max(0, int(value))
    if isinstance(value, str):
        try:
            return max(0, int(float(value)))
        except ValueError:
            return 0
    return 0


def token_total(mapping: Any, *, prefer_total: bool = True) -> int:
    """Best-effort extraction across snake_case and camelCase usage objects."""
    if not isinstance(mapping, dict):
        return 0
    if prefer_total:
        for key in ("totalTokens", "total_tokens", "total", "tokens"):
            value = positive_int(mapping.get(key))
            if value:
                return value
    keys = (
        "input",
        "input_tokens",
        "inputTokens",
        "output",
        "output_tokens",
        "outputTokens",
        "reasoning",
        "reasoning_tokens",
        "reasoningTokens",
        "cacheRead",
        "cache_read",
        "cache_read_input_tokens",
        "cacheReadInputTokens",
        "cacheWrite",
        "cache_write",
        "cache_creation_input_tokens",
        "cacheCreationInputTokens",
    )
    return sum(positive_int(mapping.get(key)) for key in keys)


def iter_jsonl_files(
    roots: Sequence[Path], cutoff_utc: datetime, stats: ScanStats, *, mtime_prune: bool
) -> Iterator[Path]:
    cutoff_epoch = cutoff_utc.timestamp()
    seen: set[tuple[int, int] | str] = set()
    for root in roots:
        expanded = root.expanduser()
        stats.roots.append(str(expanded))
        if not expanded.exists():
            stats.roots_missing.append(str(expanded))
            continue
        try:
            candidates = expanded.rglob("*.jsonl") if expanded.is_dir() else [expanded]
            for path in candidates:
                try:
                    st = path.stat()
                except OSError:
                    continue
                stats.files_considered += 1
                identity: tuple[int, int] | str
                identity = (st.st_dev, st.st_ino) if st.st_ino else str(path.resolve())
                if identity in seen:
                    continue
                seen.add(identity)
                if mtime_prune and st.st_mtime < cutoff_epoch:
                    stats.files_skipped_by_mtime += 1
                    continue
                yield path
        except OSError:
            continue


def in_period(ts: datetime | None, start_utc: datetime, end_utc: datetime) -> bool:
    return ts is not None and start_utc <= ts < end_utc


def scan_claude_code(
    roots: Sequence[Path], start_utc: datetime, end_utc: datetime, *, mtime_prune: bool
) -> tuple[list[Event], ScanStats]:
    stats = ScanStats()
    events: list[Event] = []
    for path in iter_jsonl_files(roots, start_utc, stats, mtime_prune=mtime_prune):
        stats.files_read += 1
        found = False
        sid = session_id_for(path)
        seen_message_ids: set[str] = set()
        try:
            with path.open("r", encoding="utf-8", errors="replace") as handle:
                for line_no, line in enumerate(handle, 1):
                    stats.lines_read += 1
                    # Cheap rejection: Claude assistant records always expose one of these.
                    if (
                        '"type":"assistant"' not in line
                        and '"type": "assistant"' not in line
                        and '"role":"assistant"' not in line
                        and '"role": "assistant"' not in line
                    ):
                        continue
                    if '"timestamp"' not in line:
                        continue
                    stats.candidate_lines += 1
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        stats.parse_errors += 1
                        continue
                    message = obj.get("message") if isinstance(obj.get("message"), dict) else obj
                    if obj.get("type") != "assistant" and message.get("role") != "assistant":
                        continue
                    ts = parse_timestamp(obj.get("timestamp") or message.get("timestamp"))
                    if not in_period(ts, start_utc, end_utc):
                        continue
                    message_id = str(message.get("id") or obj.get("uuid") or f"line-{line_no}")
                    if message_id in seen_message_ids:
                        continue
                    seen_message_ids.add(message_id)
                    model = str(message.get("model") or obj.get("model") or "unknown")
                    usage = message.get("usage") if isinstance(message.get("usage"), dict) else {}
                    tokens = token_total(usage)
                    events.append(
                        Event(
                            timestamp=ts,
                            provider="claude",
                            source="claude_code",
                            model=model,
                            tokens=tokens,
                            session_id=sid,
                            event_id=message_id,
                        )
                    )
                    found = True
        except OSError:
            continue
        if found:
            stats.files_with_events += 1
    stats.events_before_dedup = len(events)
    events = dedupe_events(events)
    stats.events_after_dedup = len(events)
    return events, stats


def pi_provider_for(provider: str, model: str) -> str | None:
    provider = provider.strip()
    model = model.strip()
    if provider == "claude-bridge" or model.startswith("claude-bridge/"):
        return "claude"
    if provider == "openai-codex" or model.startswith("openai-codex/"):
        return "codex"
    return None


def scan_pi(
    roots: Sequence[Path], start_utc: datetime, end_utc: datetime, *, mtime_prune: bool
) -> tuple[dict[str, list[Event]], ScanStats]:
    stats = ScanStats()
    output: dict[str, list[Event]] = {"claude": [], "codex": []}

    for path in iter_jsonl_files(roots, start_utc, stats, mtime_prune=mtime_prune):
        stats.files_read += 1
        sid = session_id_for(path)
        current_provider = ""
        current_model = ""
        seen_ids: set[str] = set()
        try:
            with path.open("r", encoding="utf-8", errors="replace") as handle:
                for line_no, line in enumerate(handle, 1):
                    stats.lines_read += 1
                    # model_change is needed as fallback for old Pi records whose message
                    # does not self-tag; assistant records are the actual activity events.
                    if (
                        '"model_change"' not in line
                        and '"role":"assistant"' not in line
                        and '"role": "assistant"' not in line
                    ):
                        continue
                    stats.candidate_lines += 1
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        stats.parse_errors += 1
                        continue
                    event_type = str(obj.get("type") or "")
                    if event_type == "model_change":
                        current_provider = str(obj.get("provider") or "")
                        current_model = str(obj.get("modelId") or obj.get("model") or "")
                        continue
                    message = obj.get("message") if isinstance(obj.get("message"), dict) else obj
                    if message.get("role") != "assistant":
                        continue
                    provider = str(message.get("provider") or obj.get("provider") or current_provider)
                    model = str(
                        message.get("model")
                        or message.get("modelId")
                        or obj.get("model")
                        or current_model
                        or "unknown"
                    )
                    normalized = pi_provider_for(provider, model)
                    if normalized is None:
                        continue
                    ts = parse_timestamp(obj.get("timestamp") or message.get("timestamp"))
                    if not in_period(ts, start_utc, end_utc):
                        continue
                    raw_id = message.get("id") or obj.get("id") or obj.get("uuid")
                    message_id = str(raw_id or f"line-{line_no}")
                    dedup_id = f"{normalized}:{message_id}"
                    if dedup_id in seen_ids:
                        continue
                    seen_ids.add(dedup_id)
                    usage = message.get("usage") if isinstance(message.get("usage"), dict) else {}
                    tokens = token_total(usage)
                    output[normalized].append(
                        Event(
                            timestamp=ts,
                            provider=normalized,
                            source=(
                                "pi_claude_bridge"
                                if normalized == "claude"
                                else "pi_openai_codex"
                            ),
                            model=model,
                            tokens=tokens,
                            session_id=sid,
                            event_id=message_id,
                        )
                    )
        except OSError:
            continue

    for provider in ("claude", "codex"):
        output[provider] = dedupe_events(output[provider])
    return output, stats


def codex_last_usage(payload: dict[str, Any]) -> int:
    info = payload.get("info")
    if not isinstance(info, dict):
        return 0
    last = info.get("last_token_usage") or info.get("lastTokenUsage")
    if isinstance(last, dict):
        return token_total(last)
    return 0


def collapse_codex_fallback(events: list[Event], within_seconds: float = 2.0) -> list[Event]:
    """Collapse adjacent assistant response items likely emitted by one API response."""
    if not events:
        return []
    events = sorted(events, key=lambda event: event.timestamp)
    collapsed = [events[0]]
    for event in events[1:]:
        previous = collapsed[-1]
        if (
            event.session_id == previous.session_id
            and event.model == previous.model
            and (event.timestamp - previous.timestamp).total_seconds() <= within_seconds
        ):
            continue
        collapsed.append(event)
    return collapsed


def scan_codex_cli(
    roots: Sequence[Path], start_utc: datetime, end_utc: datetime, *, mtime_prune: bool
) -> tuple[list[Event], ScanStats]:
    stats = ScanStats()
    all_events: list[Event] = []
    for path in iter_jsonl_files(roots, start_utc, stats, mtime_prune=mtime_prune):
        stats.files_read += 1
        sid = session_id_for(path)
        current_model = "unknown"
        token_events: list[Event] = []
        fallback_events: list[Event] = []
        try:
            with path.open("r", encoding="utf-8", errors="replace") as handle:
                for line_no, line in enumerate(handle, 1):
                    stats.lines_read += 1
                    if not any(
                        marker in line
                        for marker in (
                            '"type":"turn_context"',
                            '"type": "turn_context"',
                            '"type":"event_msg"',
                            '"type": "event_msg"',
                            '"type":"response_item"',
                            '"type": "response_item"',
                        )
                    ):
                        continue
                    stats.candidate_lines += 1
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        stats.parse_errors += 1
                        continue
                    record_type = str(obj.get("type") or "")
                    payload = obj.get("payload") if isinstance(obj.get("payload"), dict) else {}
                    ts = parse_timestamp(obj.get("timestamp") or payload.get("timestamp"))

                    if record_type == "turn_context":
                        model = payload.get("model") or payload.get("model_id")
                        if model:
                            current_model = str(model)
                        continue

                    if record_type == "event_msg" and payload.get("type") == "token_count":
                        tokens = codex_last_usage(payload)
                        if tokens <= 0 or not in_period(ts, start_utc, end_utc):
                            continue
                        token_events.append(
                            Event(
                                timestamp=ts,
                                provider="codex",
                                source="codex_cli",
                                model=current_model,
                                tokens=tokens,
                                session_id=sid,
                                event_id=f"line-{line_no}-token-count",
                            )
                        )
                        continue

                    if record_type == "response_item":
                        role = payload.get("role")
                        item_type = payload.get("type")
                        if role == "assistant" and item_type in (None, "message") and in_period(
                            ts, start_utc, end_utc
                        ):
                            fallback_events.append(
                                Event(
                                    timestamp=ts,
                                    provider="codex",
                                    source="codex_cli",
                                    model=current_model,
                                    tokens=0,
                                    session_id=sid,
                                    event_id=str(payload.get("id") or f"line-{line_no}-response-item"),
                                )
                            )
        except OSError:
            continue

        selected = token_events if token_events else collapse_codex_fallback(fallback_events)
        if selected:
            stats.files_with_events += 1
            if not token_events:
                stats.fallback_events += len(selected)
            all_events.extend(selected)

    stats.events_before_dedup = len(all_events)
    all_events = dedupe_events(all_events)
    stats.events_after_dedup = len(all_events)
    return all_events, stats


def dedupe_events(events: Iterable[Event]) -> list[Event]:
    seen: set[tuple[Any, ...]] = set()
    result: list[Event] = []
    for event in sorted(events, key=lambda item: item.timestamp):
        key = (
            event.provider,
            event.source,
            event.session_id,
            event.event_id,
            event.timestamp.isoformat(),
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(event)
    return result


def percentile(values: Sequence[float | int], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(float(value) for value in values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * p
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return ordered[lower]
    fraction = rank - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def build_bursts(events: Sequence[Event], gap: timedelta) -> list[list[Event]]:
    if not events:
        return []
    ordered = sorted(events, key=lambda event: event.timestamp)
    bursts: list[list[Event]] = [[ordered[0]]]
    for event in ordered[1:]:
        if event.timestamp - bursts[-1][-1].timestamp > gap:
            bursts.append([event])
        else:
            bursts[-1].append(event)
    return bursts


# ── Burn-smoothing m derivation ───────────────────────────────────────

def _clamped(value: float, band: tuple[float, float]) -> float:
    """Clamp value into an inclusive (low, high) band.

    >>> _clamped(8.2, (15.0, 25.0))
    15.0
    >>> _clamped(77.0, (15.0, 25.0))
    25.0
    >>> _clamped(17.7, (15.0, 20.0))
    17.7
    """
    low, high = band
    return min(high, max(low, value))


def _weekly_smoothing_m(events: Sequence[Event]) -> float:
    """m rides above the routine idle tail: p95 inter-burst gap (% of week) with margin."""
    bursts = build_bursts(events, BURST_GAP)
    gaps_pct = [
        (right[0].timestamp - left[-1].timestamp) / timedelta(weeks=1) * 100
        for left, right in zip(bursts, bursts[1:])
    ]
    p95 = percentile(gaps_pct, 0.95)
    if p95 is None:
        return BURN_SMOOTHING_DEFAULT_PCT
    return _clamped(BURN_SMOOTHING_GAP_MARGIN * p95, BURN_SMOOTHING_WEEKLY_BAND)


def _chain_session_windows(events: Sequence[Event]) -> list[list[Event]]:
    """Activity-triggered 5h windows: first event opens one; the first event at or after expiry opens the next."""
    ordered = sorted(events, key=lambda event: event.timestamp)
    grouped: list[list[Event]] = [[ordered[0]]]
    window_start = ordered[0].timestamp
    for event in ordered[1:]:
        if event.timestamp < window_start + SESSION_DURATION:
            grouped[-1].append(event)
        else:
            grouped.append([event])
            window_start = event.timestamp
    return grouped


def _session_smoothing_m(events: Sequence[Event]) -> float:
    """m stays below the typical largest intra-window lull (a fraction of its median)."""
    largest_lulls_pct = [
        max(right.timestamp - left.timestamp for left, right in zip(window, window[1:]))
        / SESSION_DURATION * 100
        for window in _chain_session_windows(events)
        if len(window) > 1
    ]
    median = percentile(largest_lulls_pct, 0.50)
    if median is None:
        return BURN_SMOOTHING_DEFAULT_PCT
    return _clamped(BURN_SMOOTHING_LULL_FRACTION * median, BURN_SMOOTHING_SESSION_BAND)


def derive_burn_smoothing(now: datetime) -> dict[str, dict[str, float]]:
    """Scan the last four weeks of local transcripts into per-provider, per-window m values."""
    end_utc = now.astimezone(UTC)
    start_utc = end_utc - BURN_SMOOTHING_LOOKBACK
    claude_events, _ = scan_claude_code(CLAUDE_TRANSCRIPT_ROOTS, start_utc, end_utc, mtime_prune=True)
    codex_events, _ = scan_codex_cli(CODEX_TRANSCRIPT_ROOTS, start_utc, end_utc, mtime_prune=True)
    pi_events, _ = scan_pi(PI_TRANSCRIPT_ROOTS, start_utc, end_utc, mtime_prune=True)
    merged = {
        "CLAUDE": dedupe_events([*claude_events, *pi_events["claude"]]),
        "CODEX": dedupe_events([*codex_events, *pi_events["codex"]]),
    }
    return {
        name: {"weekly": _weekly_smoothing_m(events), "session": _session_smoothing_m(events)}
        for name, events in merged.items()
        if events
    }


def _with_smoothing(usage: Usage, m_by_window: dict[str, float] | None) -> Usage:
    """Stamp derived m values onto a provider's windows; None keeps the defaults."""
    if m_by_window is None:
        return usage
    session = (
        dataclasses.replace(usage.session, smoothing_m=m_by_window["session"])
        if usage.session is not None
        else None
    )
    return dataclasses.replace(
        usage,
        session=session,
        weekly=dataclasses.replace(usage.weekly, smoothing_m=m_by_window["weekly"]),
    )


# ── Main ──────────────────────────────────────────────────────────────

def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read and render AI usage limits.")
    parser.add_argument(
        "-f",
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format. Use json for structured non-visual output.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()
    now = datetime.now(tz=IDT)
    warnings: list[str] = []
    claude_codex_source = "direct_cookie_api"
    openrouter_source = "api"

    try:
        usages = fetch_via_cookies(now)
    except Exception as error:
        warning = (
            f"Direct cookie-based fetch failed ({type(error).__name__}: {error}); "
            "falling back to browser scraping."
        )
        warnings.append(warning)
        print(f"WARNING: {warning}", file=sys.stderr)
        claude_codex_source = "browser_scrape"
        usages = scrape_via_browser(now)

    try:
        usages.append(_openrouter_usage(now))
    except Exception as error:
        warning = f"OpenRouter fetch failed ({type(error).__name__}: {error})"
        warnings.append(warning)
        print(f"WARNING: {warning}", file=sys.stderr)
        openrouter_source = "unavailable"

    try:
        smoothing_by_provider = derive_burn_smoothing(now)
    except Exception as error:
        warning = (
            f"Burn-smoothing derivation failed ({type(error).__name__}: {error}); "
            f"using m={BURN_SMOOTHING_DEFAULT_PCT:g} everywhere."
        )
        warnings.append(warning)
        print(f"WARNING: {warning}", file=sys.stderr)
        smoothing_by_provider = {}
    for provider_name, m_by_window in smoothing_by_provider.items():
        for window_name, m in m_by_window.items():
            if not (BURN_SMOOTHING_SANITY_BAND[0] < m < BURN_SMOOTHING_SANITY_BAND[1]):
                warning = (
                    f"Derived burn-smoothing m={m:.1f} for {provider_name} {window_name} is outside "
                    f"{BURN_SMOOTHING_SANITY_BAND}; the derivation logic may be out of whack."
                )
                warnings.append(warning)
                print(f"WARNING: {warning}", file=sys.stderr)
    usages = [_with_smoothing(usage, smoothing_by_provider.get(usage.name)) for usage in usages]

    if args.format == "json":
        json.dump(
            _usage_report_json(
                usages,
                now,
                warnings=warnings,
                claude_codex_source=claude_codex_source,
                openrouter_source=openrouter_source,
            ),
            sys.stdout,
            indent=2,
        )
        print()
        return

    console = Console()
    picasso_width = _parse_picasso_width(os.environ.get("PICASSO_WIDTH"), str(console.size.width))
    console.print()
    print_picasso(usages, now, console=console, picasso_width=picasso_width)


if __name__ == "__main__":
    main()
