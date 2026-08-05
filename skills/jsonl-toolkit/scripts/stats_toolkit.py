#!/usr/bin/env python3
"""
JSONL Aggregate Analysis Control Panel — a toolkit for IPython.

Designed for probing, analyzing, and pruning large collections of AI agent
session transcriptions (.jsonl files) whose shape is unknown in advance.
Nothing runs automatically — you call functions, observe prints, iterate.

Usage:
    %load toolkit.py    # in IPython
    from toolkit import *

Mental model — three phases, each gated on what the previous reveals:

    1. PROBE     — understand file shapes without reading content.
                   probe_schema, probe_type_counts, probe_sample.

    2. COLLECT   — aggregate stats across all files.
                   stat_one (single), collect_stats (recursive),
                   save_stats / load_stats (persist).
    3. INSPECT   — filter, print distributions, visualise.

    3. INSPECT   — filter, print distributions, visualize.
                   filter_sessions, print_overview, print_percentiles,
                   histogram, print_daily_histogram,
                   print_project_breakdown, print_by_project,
                   print_top, print_smallest, print_density.

    4. LABEL     — use a cheap LLM to classify sessions on a dimension
                   no stat can capture (e.g. readonly/scouting vs editing).
                   label_one (single), label_batch (parallel),
                   parse_labels.

    5. DELETE    — always dry-run first.
                   delete_paths.

You mix and match phases as the picture sharpens. The single-session
functions (stat_one, print_session, label_one) are primitives; the
multi-session functions compose them.

depends on: pi (for labeling phase). All other functions are pure Python stdlib.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable

# ═══════════════════════════════════════════════════════════════════════════════
# Data structures
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class SessionStats:
    """Aggregate stats for a single .jsonl session file."""
    path: str
    size: int
    mtime: float
    lines: int
    user_msgs: int
    type_counts: dict[str, int] = field(default_factory=dict)
    project: str = ""
    is_subagent: bool = False

    @property
    def size_kb(self) -> float:
        return self.size / 1024

    @property
    def size_mb(self) -> float:
        return self.size / 1024 / 1024

    @property
    def mtime_dt(self) -> datetime:
        return datetime.fromtimestamp(self.mtime, tz=timezone.utc)

    @property
    def days_ago(self) -> float:
        return (datetime.now().timestamp() - self.mtime) / 86400

    def to_dict(self) -> dict:
        return {
            'path': self.path,
            'size': self.size,
            'mtime': self.mtime,
            'lines': self.lines,
            'user_msgs': self.user_msgs,
            'types': self.type_counts,
        }

    @classmethod
    def from_dict(cls, d: dict) -> SessionStats:
        return cls(
            path=d['path'],
            size=d['size'],
            mtime=d['mtime'],
            lines=d['lines'],
            user_msgs=d['user_msgs'],
            type_counts=d.get('types', {}),
            project=d['path'].split('/')[0],
            is_subagent='subagents' in d['path'],
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Probing — understand file shapes without reading fully
# ═══════════════════════════════════════════════════════════════════════════════


def probe_schema(path: str, n_lines: int = 5) -> None:
    """Print schema summary of first N lines of a .jsonl file.

    Shows: key names, value types, string lengths, list/dict shapes.
    Does NOT print actual content — safe for privacy.
    """
    print(f"=== {path} ===")
    try:
        with open(path) as f:
            for i, line in enumerate(f):
                if i >= n_lines:
                    break
                obj = json.loads(line)
                t = obj.get('type', 'NO_TYPE')
                summary = {}
                for k, v in obj.items():
                    if isinstance(v, str):
                        summary[k] = f"str(len={len(v)})"
                    elif isinstance(v, bool):
                        summary[k] = repr(v)
                    elif isinstance(v, (int, float)):
                        summary[k] = repr(v)
                    elif isinstance(v, list):
                        summary[k] = f"list(len={len(v)})"
                    elif isinstance(v, dict):
                        summary[k] = f"dict(keys={list(v.keys())[:5]})"
                    elif v is None:
                        summary[k] = None
                    else:
                        summary[k] = type(v).__name__
                print(f"  L{i}: type={t} keys={list(obj.keys())}")
    except Exception as e:
        print(f"  ERROR: {e}")
    print()


def probe_type_counts(path: str) -> dict[str, int]:
    """Return dict of message type -> count for a single .jsonl file."""
    counts: dict[str, int] = {}
    with open(path) as f:
        for line in f:
            obj = json.loads(line)
            t = obj.get('type', 'NO_TYPE')
            counts[t] = counts.get(t, 0) + 1
    return counts


def probe_sample(root: str, n_files: int = 3) -> None:
    """Randomly sample N .jsonl files from root and probe their schema + types."""
    all_files = _find_jsonl_files(root)
    import random
    samples = random.sample(all_files, min(n_files, len(all_files)))
    for f in samples:
        probe_schema(f)
        counts = probe_type_counts(f)
        print(f"  Type counts: {counts}")
        print()


# ═══════════════════════════════════════════════════════════════════════════════
# Single-session stats + inspection
# ═══════════════════════════════════════════════════════════════════════════════


def stat_one(path: str) -> SessionStats | None:
    """Scan one .jsonl file and return its SessionStats. Returns None on parse error.

    >>> s = stat_one('/some/session.jsonl')
    >>> print(s.lines, s.user_msgs, s.size_kb)
    """
    try:
        fstat = os.stat(path)
    except OSError as e:
        print(f"ERROR: {path}: {e}", file=sys.stderr)
        return None

    lines = 0
    user_count = 0
    type_counts: dict[str, int] = {}
    try:
        with open(path) as f:
            for line in f:
                lines += 1
                obj = json.loads(line)
                t = obj.get('type', 'NO_TYPE')
                type_counts[t] = type_counts.get(t, 0) + 1
                if t == 'user':
                    user_count += 1
    except Exception as e:
        print(f"SKIP (parse error): {path}: {e}", file=sys.stderr)
        return None

    return SessionStats(
        path=path,
        size=fstat.st_size,
        mtime=fstat.st_mtime,
        lines=lines,
        user_msgs=user_count,
        type_counts=type_counts,
        project=path.split('/')[0],
        is_subagent='subagents' in path,
    )


def print_session(path: str) -> None:
    """Print a one-line summary of a single session file.

    Does not read message content — just stats.
    """
    s = stat_one(path)
    if s is None:
        return
    print(f"  {s.mtime_dt.strftime('%Y-%m-%d %H:%M')}  "
          f"size={s.size_kb:.0f}KB  lines={s.lines}  user_msgs={s.user_msgs}  "
          f"types={dict(s.type_counts)}")


# ═══════════════════════════════════════════════════════════════════════════════
# Multi-session collection
# ═══════════════════════════════════════════════════════════════════════════════


def collect_stats(root: str) -> list[SessionStats]:
    """Walk root, scan every .jsonl file, return list of SessionStats.

    Delegates to stat_one() per file. Use this for the initial full sweep.
    """
    results: list[SessionStats] = []
    for dirpath, _, filenames in os.walk(root):
        for fn in filenames:
            if not fn.endswith('.jsonl'):
                continue
            fullpath = os.path.join(dirpath, fn)
            relpath = os.path.relpath(fullpath, root)
            s = stat_one(fullpath)
            if s is None:
                continue
            s.path = relpath  # store relative for portability
            results.append(s)
    return results


def save_stats(sessions: Iterable[SessionStats], path: str) -> None:
    """Save SessionStats to JSONL artifact."""
    with open(path, 'w') as f:
        for s in sessions:
            f.write(json.dumps(s.to_dict()) + '\n')


def load_stats(path: str) -> list[SessionStats]:
    """Load SessionStats from a previously saved JSONL artifact."""
    results: list[SessionStats] = []
    with open(path) as f:
        for line in f:
            results.append(SessionStats.from_dict(json.loads(line)))
    return results


# ═══════════════════════════════════════════════════════════════════════════════
# Filtering
# ═══════════════════════════════════════════════════════════════════════════════


def filter_sessions(
    sessions: list[SessionStats],
    min_lines: int | None = None,
    max_lines: int | None = None,
    min_user_msgs: int | None = None,
    max_user_msgs: int | None = None,
    min_size: int | None = None,
    max_size: int | None = None,
    exclude_subagents: bool = False,
    projects: list[str] | None = None,
) -> list[SessionStats]:
    """Return filtered list of sessions."""
    result = sessions
    if min_lines is not None:
        result = [s for s in result if s.lines >= min_lines]
    if max_lines is not None:
        result = [s for s in result if s.lines <= max_lines]
    if min_user_msgs is not None:
        result = [s for s in result if s.user_msgs >= min_user_msgs]
    if max_user_msgs is not None:
        result = [s for s in result if s.user_msgs <= max_user_msgs]
    if min_size is not None:
        result = [s for s in result if s.size >= min_size]
    if max_size is not None:
        result = [s for s in result if s.size <= max_size]
    if exclude_subagents:
        result = [s for s in result if not s.is_subagent]
    if projects:
        result = [s for s in result if s.project in projects]
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# Printing — distributions, summaries, histograms
# ═══════════════════════════════════════════════════════════════════════════════


def print_overview(sessions: list[SessionStats]) -> None:
    """Quick overview: count, total size, total messages."""
    total_size = sum(s.size for s in sessions)
    total_lines = sum(s.lines for s in sessions)
    total_users = sum(s.user_msgs for s in sessions)
    main = [s for s in sessions if not s.is_subagent]
    sub = [s for s in sessions if s.is_subagent]
    print(f"Total sessions: {len(sessions)}")
    print(f"Total size:     {total_size:,} bytes ({total_size/1024/1024:.1f} MB)")
    print(f"Total messages: {total_lines:,}")
    print(f"Total user msgs:{total_users:,}")
    print(f"Main sessions:  {len(main)} ({sum(s.size for s in main)/1024/1024:.1f} MB)")
    print(f"Subagents:      {len(sub)} ({sum(s.size for s in sub)/1024/1024:.1f} MB)")


def print_percentiles(sessions: list[SessionStats], attr: str = 'size') -> None:
    """Print min/p25/median/p75/max for a numeric attribute."""
    values = sorted([getattr(s, attr) for s in sessions])
    n = len(values)
    labels = ['min', 'p25', 'median', 'p75', 'max']
    indices = [0, n // 4, n // 2, 3 * n // 4, n - 1]
    print(f"{attr} distribution:")
    for label, idx in zip(labels, indices):
        v = values[idx]
        if attr == 'size':
            print(f"  {label:>8}: {v:>12,} bytes ({v/1024:.0f} KB)")
        else:
            print(f"  {label:>8}: {v:>12,}")


def histogram(sessions: list[SessionStats], attr: str, bins: int | list[str] = 10,
              title: str = "", width: int = 20, bar_char: str = "█") -> None:
    """Print ASCII histogram for any numeric attribute.

    If bins is an int, auto-generate equal-width bins with labels.
    If bins is a list of strings, use them as bucket labels (for predefined bucketing).
    """
    values = [getattr(s, attr) for s in sessions]

    if not values:
        print("(empty)")
        return

    if isinstance(bins, int):
        n_bins = bins
        vmin, vmax = min(values), max(values)
        if vmin == vmax:
            vmin -= 1
            vmax += 1
        width_val = (vmax - vmin) / n_bins
        buckets = [0] * n_bins
        labels = []
        for i in range(n_bins):
            lo = vmin + i * width_val
            hi = vmin + (i + 1) * width_val
            labels.append(f"{_fmt_num(lo)}-{_fmt_num(hi)}")
            for v in values:
                if lo <= v < hi or (i == n_bins - 1 and v == hi):
                    buckets[i] += 1
    else:
        # Predefined labels — use index as value
        labels = list(bins)
        buckets = [values.count(i) if all(isinstance(v, int) for v in values) else 0
                    for i in range(len(bins))]
        # If values are strings (e.g., project names), count frequencies
        if all(isinstance(v, str) for v in values):
            counter = Counter(values)
            labels = [str(k) for k in counter]
            buckets = list(counter.values())

    max_val = max(buckets) if buckets else 1
    max_label_len = max(len(l) for l in labels)

    if title:
        print(f"=== {title} ===")
    for label, count in zip(labels, buckets):
        bar_len = max(1, int(count / max_val * width)) if count > 0 else 0
        bar = bar_char * bar_len if bar_len > 0 else " "
        print(f"  {label:>{max_label_len}s} │{bar:>{width}s}│ {count}")


def _fmt_num(n: float) -> str:
    if n >= 1_048_576:
        return f"{n/1_048_576:.0f}MB"
    if n >= 1024:
        return f"{n/1024:.0f}KB"
    if isinstance(n, float) and n == int(n):
        return str(int(n))
    return f"{n:.1f}"


def print_project_breakdown(sessions: list[SessionStats], top_n: int = 20) -> None:
    """Print sessions per project with size, lines, user msgs, and date span."""
    groups: dict[str, dict] = defaultdict(lambda: {
        'count': 0, 'size': 0, 'lines': 0, 'user_msgs': 0, 'mtimes': []
    })
    for s in sessions:
        g = groups[s.project]
        g['count'] += 1
        g['size'] += s.size
        g['lines'] += s.lines
        g['user_msgs'] += s.user_msgs
        g['mtimes'].append(s.mtime)

    print(f"{'Project':<55s} {'Sessions':>8} {'Size':>8} {'Lines':>8} {'U-Msgs':>8} {'Span'}")
    print("-" * 100)
    for proj, g in sorted(groups.items(), key=lambda x: x[1]['count'], reverse=True)[:top_n]:
        times = sorted(g['mtimes'])
        first = datetime.fromtimestamp(times[0], tz=timezone.utc).strftime('%m-%d')
        last = datetime.fromtimestamp(times[-1], tz=timezone.utc).strftime('%m-%d')
        span = f"{first} → {last}"
        print(f"{proj:<55s} {g['count']:>8d} {g['size']/1024/1024:>7.1f}M {g['lines']:>8d} {g['user_msgs']:>8d} {span}")


def print_by_project(sessions: list[SessionStats]) -> None:
    """Print detailed per-project breakdown: count, total size, lines, user msgs, date span."""
    project_data: dict[str, dict] = defaultdict(
        lambda: {'count': 0, 'size': 0, 'lines': 0, 'user_msgs': 0, 'mtimes': []}
    )
    for s in sessions:
        pd = project_data[s.project]
        pd['count'] += 1
        pd['size'] += s.size
        pd['lines'] += s.lines
        pd['user_msgs'] += s.user_msgs
        pd['mtimes'].append(s.mtime)

    for proj, pd in sorted(project_data.items(), key=lambda x: x[1]['size'], reverse=True):
        times = sorted(pd['mtimes'])
        first = datetime.fromtimestamp(times[0], tz=timezone.utc).strftime('%m-%d')
        last = datetime.fromtimestamp(times[-1], tz=timezone.utc).strftime('%m-%d')
        span_days = (times[-1] - times[0]) / 86400
        print(f"  {proj}:")
        print(f"    {pd['count']} sessions, {pd['size']/1024/1024:.1f} MB, "
              f"{pd['lines']} lines, {pd['user_msgs']} user msgs")
        print(f"    {first} → {last} ({span_days:.0f}d)")


def print_top(sessions: list[SessionStats], by: str = 'size', n: int = 20) -> None:
    """Print top N sessions sorted by a given attribute."""
    sorted_sessions = sorted(sessions, key=lambda s: getattr(s, by), reverse=True)
    print(f"Top {n} by {by}:")
    for s in sorted_sessions[:n]:
        path = '/'.join(s.path.rsplit('/', 2)[-2:]) if '/' in s.path else s.path
        print(f"  {path:65s} {s.size/1024/1024:>6.1f}MB {s.lines:>5d}l {s.user_msgs:>4d}u")


def print_smallest(sessions: list[SessionStats], n: int = 10) -> None:
    """Print N smallest sessions (by size)."""
    for s in sorted(sessions, key=lambda x: x.size)[:n]:
        path = '/'.join(s.path.rsplit('/', 2)[-2:]) if '/' in s.path else s.path
        print(f"  {s.mtime_dt.strftime('%m-%d %H:%M')} {path:55s} "
              f"{s.size/1024:.0f}KB {s.lines}l {s.user_msgs}u")


def print_density(sessions: list[SessionStats]) -> None:
    """Print work density: size per user message, bucketed visually.

    High density = agent did a lot per prompt (code-heavy sessions).
    Low density = mostly chat/scouting.
    """
    data: dict[str, dict] = defaultdict(lambda: {'size': 0, 'users': 0})
    for s in sessions:
        if s.user_msgs == 0:
            continue
        data[s.project]['size'] += s.size
        data[s.project]['users'] += s.user_msgs

    for proj, d in sorted(data.items(), key=lambda x: x[1]['size'] / x[1]['users'], reverse=True):
        ratio = d['size'] / d['users']
        print(f"  {proj:55s} {ratio/1024:>6.0f} KB/msg  "
              f"({d['size']/1024/1024:.1f}MB / {d['users']} msgs)")


def print_daily_histogram(sessions: list[SessionStats]) -> None:
    """Print daily session count as ASCII histogram."""
    daily: dict[str, int] = defaultdict(int)
    for s in sessions:
        day = s.mtime_dt.strftime('%m-%d')
        daily[day] += 1

    sorted_days = sorted(daily.keys())
    max_label = max(len(d) for d in sorted_days)
    max_val = max(daily.values())
    width = 20

    print("=== Daily session distribution ===")
    for day in sorted_days:
        count = daily[day]
        bar_len = max(1, int(count / max_val * width)) if count > 0 else 0
        bar = "█" * bar_len if bar_len > 0 else " "
        print(f"  {day:>{max_label}s} │{bar:>{width}s}│ {count}")


# ═══════════════════════════════════════════════════════════════════════════════
# Subagent labeling — cheap LLM classifier for readonly/scouting vs editing
# ═══════════════════════════════════════════════════════════════════════════════

LABEL_PROMPT_TEMPLATE = (
    "Read {path} in full. "
    "It is a transcription of an AI coding session between a user and an assistant. "
    "is this session 100% readonly, scouting/research? "
    "Answer YES/NO then one sentence justification. Only one sentence."
)


def label_one(path: str, model: str = "ds4f", pi_binary: str = "/opt/homebrew/bin/pi") -> str:
    """Label a single .jsonl session using a cheap LLM.

    Returns raw output (stdout + stderr).
    """
    prompt = LABEL_PROMPT_TEMPLATE.format(path=path)
    result = subprocess.run(
        [pi_binary, "--model", model, "--no-session", "--print", prompt],
        capture_output=True,
        text=True,
        timeout=180,
    )
    output = result.stdout
    if result.stderr:
        # Only include stderr if it has real content (not extension errors)
        stderr_lines = [l for l in result.stderr.split('\n')
                        if l.strip() and not l.strip().startswith('file://')]
        if stderr_lines:
            output += "\n--- STDERR ---\n" + "\n".join(stderr_lines)
    return output.strip()


def label_batch(paths: list[str], output_dir: str, model: str = "ds4f",
                max_workers: int = 20, pi_binary: str = "/opt/homebrew/bin/pi") -> None:
    """Label many sessions in parallel, saving each result to output_dir/<basename>.txt."""
    os.makedirs(output_dir, exist_ok=True)

    def _label(path):
        fname = os.path.basename(path)
        out = os.path.join(output_dir, f"{fname}.txt")
        if os.path.exists(out) and os.path.getsize(out) > 0:
            return (path, "SKIP")
        result = label_one(path, model=model, pi_binary=pi_binary)
        with open(out, 'w') as f:
            f.write(result)
        return (path, result.split('\n')[0])

    print(f"Labeling {len(paths)} sessions with {max_workers} workers...")
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_label, p): p for p in paths}
        done = 0
        for future in as_completed(futures):
            done += 1
            path, preview = future.result()
            short = '/'.join(path.rsplit('/', 2)[-2:])
            print(f"[{done}/{len(paths)}] {preview[:80]} — {short}")


def parse_labels(paths: list[str], labels_dir: str) -> tuple[list[str], list[str], list[str]]:
    """Parse YES/NO labels from label output files.

    Returns: (yes_paths, no_paths, error_paths)
    """
    yes_paths = []
    no_paths = []
    errors = []

    for path in paths:
        fname = os.path.basename(path)
        out = os.path.join(labels_dir, f"{fname}.txt")
        if not os.path.exists(out) or os.path.getsize(out) == 0:
            errors.append(path)
            continue
        with open(out) as f:
            first_line = f.readline().strip()
        cleaned = re.sub(r'^\*\*', '', first_line)
        cleaned = re.sub(r'\*\*', '', cleaned).strip()
        if cleaned.upper().startswith('YES'):
            yes_paths.append(path)
        elif cleaned.upper().startswith('NO'):
            no_paths.append(path)
        else:
            errors.append(path)

    print(f"YES (readonly/scouting): {len(yes_paths)}")
    print(f"NO  (edits/writes):      {len(no_paths)}")
    print(f"Errors/unparseable:      {len(errors)}")
    return yes_paths, no_paths, errors


# ═══════════════════════════════════════════════════════════════════════════════
# Deletion helpers
# ═══════════════════════════════════════════════════════════════════════════════


def delete_paths(paths: list[str], root: str, dry_run: bool = True) -> None:
    """Delete a list of session files.

    If dry_run=True, only print what would be deleted.
    """
    total_size = 0
    for path in paths:
        try:
            total_size += os.path.getsize(path)
        except OSError:
            pass

    print(f"{'[DRY RUN] ' if dry_run else ''}Deleting {len(paths)} files "
          f"({total_size/1024/1024:.1f} MB)...")
    if dry_run:
        for p in paths[:10]:
            print(f"  would delete: {p}")
        if len(paths) > 10:
            print(f"  ... and {len(paths) - 10} more")
        return

    for p in paths:
        try:
            os.remove(p)
        except OSError as e:
            print(f"  FAILED: {p}: {e}")
    print("Done.")


# ═══════════════════════════════════════════════════════════════════════════════
# Internal helpers
# ═══════════════════════════════════════════════════════════════════════════════


def _find_jsonl_files(root: str) -> list[str]:
    """Return all .jsonl files under root."""
    results: list[str] = []
    for dirpath, _, filenames in os.walk(root):
        for fn in filenames:
            if fn.endswith('.jsonl'):
                results.append(os.path.join(dirpath, fn))
    return results


def sessions_to_paths(sessions: list[SessionStats], root: str) -> list[str]:
    """Convert SessionStats list to absolute paths."""
    return [os.path.join(root, s.path) for s in sessions]


def paths_to_sessions(paths: list[str], root: str) -> list[SessionStats]:
    """Build SessionStats from a list of absolute paths (useful after filtering)."""
    # Simple rebuild by scanning
    all_sessions = collect_stats(root)
    path_set = set(paths)
    return [s for s in all_sessions if os.path.join(root, s.path) in path_set]


# ═══════════════════════════════════════════════════════════════════════════════
# Auto-export everything
# ═══════════════════════════════════════════════════════════════════════════════

__all__ = [
    'SessionStats',
    'probe_schema', 'probe_type_counts', 'probe_sample',
    'stat_one', 'print_session',
    'collect_stats', 'save_stats', 'load_stats',
    'filter_sessions',
    'print_overview', 'print_percentiles', 'histogram',
    'print_project_breakdown', 'print_by_project',
    'print_top', 'print_smallest', 'print_density',
    'print_daily_histogram',
    'label_one', 'label_batch', 'parse_labels',
    'delete_paths',
    'sessions_to_paths', 'paths_to_sessions',
]
