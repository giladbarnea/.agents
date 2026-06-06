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
"""

import dataclasses
import json
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
from datetime import datetime, timedelta
from dateutil import tz
from Crypto.Cipher import AES
from Crypto.Hash import SHA1
from Crypto.Protocol.KDF import PBKDF2
import requests
from rich.console import Console
from rich.text import Text
import websocket

IDT = tz.gettz("Asia/Jerusalem")
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
) -> Text:
    """Glyph-tagged atoms (●used% ┊elapsed%) + burn rate, mirroring the track's legend."""
    used_pos = round(max(0.0, min(100.0, used_pct)) / 100 * (width - 1))
    elapsed_pos = round(max(0.0, min(100.0, elapsed_pct)) / 100 * (width - 1))
    over = used_pct > elapsed_pct

    used_label = f"{round(used_pct)}%"
    elapsed_label = f"{round(elapsed_pct)}%"

    text = Text()
    if used_pos == elapsed_pos:
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


PICASSO_WIDTH = 50


def _picasso_line(label: str, limit: Limit, now: datetime, *, track, slack: str, over: str) -> Text:
    """One track line: name, bar, optional ↻ countdown (omitted when the window never resets), legend."""
    elapsed = limit.elapsed_pct(now)
    bar = track(limit.used_pct, elapsed, width=PICASSO_WIDTH)
    legend = _label(limit.used_pct, elapsed, width=PICASSO_WIDTH, used_style_slack=slack, used_style_over=over)

    text = Text(f"  {label:<7}  ", style="bold") + bar + Text("  ")
    if limit.resets:
        text += Text(f"↻ {fmt_dh(limit.next_reset - now):>{PICASSO_RESET_DURATION_WIDTH}}", style="dim")
        text += Text(" · ", style="black")
    return text + legend


def print_picasso(usages: list[Usage], now: datetime, *, console: Console) -> None:
    for idx, usage in enumerate(usages):
        if idx > 0:
            console.print()
        console.print(_picasso_line(usage.name, usage.weekly, now,
                                    track=_track, slack="cyan", over="bright_red"))
        if usage.session is not None:
            console.print(_picasso_line("", usage.session, now,
                                        track=_session_track, slack="magenta", over="bright_magenta"))


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


def fetch_via_cookies() -> list[Usage]:
    """First-line: read usage straight from the JSON endpoints, no browser process needed."""
    claude = _claude_usage_json()
    codex = _codex_rate_limit_json()
    return [
        Usage(
            name="CLAUDE",
            session=Limit.until(float(claude["five_hour"]["utilization"]),
                                datetime.fromisoformat(claude["five_hour"]["resets_at"]).astimezone(IDT),
                                SESSION_DURATION),
            weekly=Limit.until(float(claude["seven_day"]["utilization"]),
                               datetime.fromisoformat(claude["seven_day"]["resets_at"]).astimezone(IDT)),
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


# ── Main ──────────────────────────────────────────────────────────────

def main() -> None:
    now = datetime.now(tz=IDT)
    console = Console()

    try:
        usages = fetch_via_cookies()
    except Exception as error:
        print(
            f"WARNING: Direct cookie-based fetch failed ({type(error).__name__}: {error}); "
            "falling back to browser scraping.",
            file=sys.stderr,
        )
        usages = scrape_via_browser(now)

    try:
        usages.append(_openrouter_usage(now))
    except Exception as error:
        print(f"WARNING: OpenRouter fetch failed ({type(error).__name__}: {error})", file=sys.stderr)

    console.print()
    print_picasso(usages, now, console=console)


if __name__ == "__main__":
    main()
