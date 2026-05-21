#!/usr/bin/env -S uv run
# /// script
# requires-python = "==3.12.*"
# ///
"""Scrape GitHub releases changelogs between two versions (inclusive).

Usage:
  scrape_changelogs.py owner/repo v2.1.33 v2.1.143
  scrape_changelogs.py owner/repo v2.1.33 v2.1.33   # single version
"""

import subprocess
import re
import sys
import os


def fetch_page(owner_repo: str, page_num: int) -> str:
    url = f"https://github.com/{owner_repo}/releases?page={page_num}"
    result = subprocess.run(
        ["rf", "--scraper", "markitdown", url],
        capture_output=True, text=True, timeout=60,
        env={**os.environ, "FORCE_OMZ": "1"},
    )
    return result.stdout


def parse_releases(markdown: str) -> list[tuple[str, str]]:
    """Extract (version, changelog_body) pairs from markdown."""
    releases = []
    parts = re.split(r"\n## (v\d+\.\d+\.\d+)\s*\n", markdown)
    for i in range(1, len(parts) - 1, 2):
        version = parts[i].strip()
        content = parts[i + 1]
        m = re.search(
            r"## What.s changed\s*\n(.*?)(?=\n## |\nAssets|\Z)", content, re.DOTALL
        )
        changelog = m.group(1).strip() if m else ""
        releases.append((version, changelog))
    return releases


def parse_version(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in v.removeprefix("v").split("."))


def main():
    if len(sys.argv) != 4:
        print("Usage: scrape_changelogs.py owner/repo VERSION_FROM VERSION_TO", file=sys.stderr)
        sys.exit(1)

    owner_repo = sys.argv[1]
    from_ver = parse_version(sys.argv[2])
    to_ver = parse_version(sys.argv[3])

    all_releases: list[tuple[str, str]] = []
    for page in range(1, 20):
        md = fetch_page(owner_repo, page)
        releases = parse_releases(md)
        if not releases:
            break
        for ver, body in releases:
            pv = parse_version(ver)
            if from_ver <= pv <= to_ver:
                all_releases.append((ver, body))
        if parse_version(releases[-1][0]) < from_ver:
            break

    all_releases.sort(key=lambda x: parse_version(x[0]), reverse=True)

    for ver, changelog in all_releases:
        items = [
            l.strip().lstrip("* ") for l in changelog.split("\n") if l.strip().startswith("*")
        ]
        print(f"\n## {ver}")
        for item in items:
            print(f"- {item}")


if __name__ == "__main__":
    main()
