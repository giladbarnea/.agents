#!/usr/bin/env -S uv run
# /// script
# requires-python = "==3.12.*"
# dependencies = []
# ///

import json
import os
import re
import subprocess
import sys
from pathlib import Path

TOKEN = Path("~/.notion-api-key-haushner").expanduser().read_text().strip()
DEST = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/ntn/sandbox")


def ntn(*args: str) -> str:
    result = subprocess.run(
        ["ntn", *args],
        capture_output=True,
        text=True,
        env={**os.environ, "NOTION_API_TOKEN": TOKEN},
    )
    if result.returncode != 0:
        print(f"  [warn] ntn {' '.join(args[:2])}: {result.stderr.strip()}", file=sys.stderr)
    return result.stdout


def search_all_pages() -> list[dict]:
    pages = []
    cursor = None
    while True:
        body: dict = {"filter": {"value": "page", "property": "object"}, "page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        data = json.loads(ntn("api", "v1/search", "-d", json.dumps(body)))
        pages.extend(data["results"])
        if not data.get("has_more"):
            break
        cursor = data["next_cursor"]
    return pages


def page_title(page: dict) -> str:
    try:
        return page["properties"]["title"]["title"][0]["plain_text"]
    except (KeyError, IndexError):
        return page["id"]


def slugify(title: str) -> str:
    title = re.sub(r'[/\\:*?"<>|]', "-", title.strip())
    return re.sub(r"\s+", "_", title)


def build_tree(pages: list[dict]) -> tuple[dict, dict, list[str]]:
    by_id = {p["id"]: p for p in pages}
    children: dict[str, list[str]] = {}
    roots: list[str] = []

    for page in pages:
        parent = page["parent"]
        if parent["type"] == "workspace":
            roots.append(page["id"])
        else:
            parent_id = parent.get("page_id") or parent.get("database_id")
            if parent_id in by_id:
                children.setdefault(parent_id, []).append(page["id"])
            else:
                roots.append(page["id"])  # orphan — treat as root

    return by_id, children, roots


def dump(page_id: str, dest_dir: Path, by_id: dict, children: dict) -> int:
    page = by_id.get(page_id)
    slug = slugify(page_title(page)) if page else page_id
    filepath = dest_dir / f"{slug}.md"

    print(f"  {filepath.relative_to(DEST)}")
    filepath.write_text(ntn("pages", "get", page_id))

    count = 1
    for child_id in children.get(page_id, []):
        subdir = dest_dir / slug
        subdir.mkdir(exist_ok=True)
        count += dump(child_id, subdir, by_id, children)

    return count


DEST.mkdir(parents=True, exist_ok=True)
print(f"Fetching page list...")
pages = search_all_pages()
print(f"  {len(pages)} pages found\n")

by_id, children, roots = build_tree(pages)
total = 0
for root_id in roots:
    total += dump(root_id, DEST, by_id, children)

print(f"\n{total} files written to {DEST}")
