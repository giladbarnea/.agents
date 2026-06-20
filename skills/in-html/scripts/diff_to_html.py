#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Render two texts as an in-html `.diff` fragment — line + word-level changeset.

Emits the `.diff` component markup (see the "Line/word-level diff" section of
components.md): a side-by-side ↔ unified view (pure-CSS toggle), collapsible
unchanged context, intraline word highlights, and #-addressable change blocks
with Prev/Next stepping. Paste the output into the `CONTENT` block of a
template, then inline `style.css` with `inline-css.py`.

The diff is the reusable kernel; the *meaning* of each change is yours to
supply. An optional annotations JSON tags change blocks with a badge/title/note:

    [
      {"n": 1, "tag": "blue",  "label": "META",   "title": "...", "note": "..."},
      {"match": "recipes", "tag": "amber", "label": "DEBIAS", "note": "..."}
    ]

Match a block by 1-based change index (`n`) or by a `match` substring found
anywhere in the block. `tag` ∈ {blue, amber, green, red} (reuses `.tag` colors).

Usage:
    ./diff_to_html.py OLD NEW --left-label "world" --right-label "main"
    ./diff_to_html.py a.md b.md --id pricing --annotations notes.json -o frag.html

To diff two git revisions, materialize them first:
    git show main:path/to/file > /tmp/new.md
    git show other:path/to/file > /tmp/old.md
    ./diff_to_html.py /tmp/old.md /tmp/new.md --left-label other --right-label main
"""
import argparse
import difflib
import html
import json
import re
import sys
from pathlib import Path

_WORD = re.compile(r"(\s+)")


def esc(s: str) -> str:
    return html.escape(s, quote=True)


def word_diff(a: str, b: str) -> tuple[str, str]:
    """Intraline diff of two lines → (left_html, right_html) with .wd add/del spans.

    >>> word_diff("the cat sat", "the dog sat")
    ('the <span class="wd del">cat</span> sat', 'the <span class="wd add">dog</span> sat')
    """
    at = [t for t in _WORD.split(a) if t != ""]
    bt = [t for t in _WORD.split(b) if t != ""]
    sm = difflib.SequenceMatcher(a=at, b=bt, autojunk=False)
    left, right = [], []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        lt, rt = esc("".join(at[i1:i2])), esc("".join(bt[j1:j2]))
        if tag == "equal":
            left.append(lt)
            right.append(rt)
        elif tag == "replace":
            if lt:
                left.append(f'<span class="wd del">{lt}</span>')
            if rt:
                right.append(f'<span class="wd add">{rt}</span>')
        elif tag == "delete":
            left.append(f'<span class="wd del">{lt}</span>')
        elif tag == "insert":
            right.append(f'<span class="wd add">{rt}</span>')
    return "".join(left), "".join(right)


def _ctx_row(l: str, r: str) -> str:
    return (
        f'<div class="drow ctx"><div class="dc l" dir="auto">{esc(l) or "&nbsp;"}</div>'
        f'<div class="dc r" dir="auto">{esc(r) or "&nbsp;"}</div></div>'
    )


def _change_rows(left_lines: list[str], right_lines: list[str]) -> str:
    rows = []
    paired = min(len(left_lines), len(right_lines))
    for n in range(paired):
        lh, rh = word_diff(left_lines[n], right_lines[n])
        rows.append(
            f'<div class="drow"><div class="dc l del" dir="auto">{lh or "&nbsp;"}</div>'
            f'<div class="dc r add" dir="auto">{rh or "&nbsp;"}</div></div>'
        )
    for n in range(paired, len(left_lines)):  # extra deletions
        rows.append(
            f'<div class="drow"><div class="dc l del" dir="auto">{esc(left_lines[n]) or "&nbsp;"}</div>'
            f'<div class="dc r empty"></div></div>'
        )
    for n in range(paired, len(right_lines)):  # extra insertions
        rows.append(
            f'<div class="drow"><div class="dc l empty"></div>'
            f'<div class="dc r add" dir="auto">{esc(right_lines[n]) or "&nbsp;"}</div></div>'
        )
    return "".join(rows)


def _annotation_for(n: int, block_text: str, annotations: list[dict]) -> dict | None:
    for a in annotations:
        if a.get("n") == n:
            return a
    plain = html.unescape(re.sub(r"<[^>]+>", "", block_text))
    for a in annotations:
        if "n" not in a and a.get("match") and a["match"] in plain:
            return a
    return None


def render_diff(
    left: str,
    right: str,
    *,
    left_label: str = "before",
    right_label: str = "after",
    diff_id: str = "d1",
    annotations: list[dict] | None = None,
    context: int = 3,
) -> str:
    """Return the `.diff` fragment comparing left → right (whole texts)."""
    annotations = annotations or []
    llines, rlines = left.splitlines(), right.splitlines()
    sm = difflib.SequenceMatcher(a=llines, b=rlines, autojunk=False)

    # split opcodes into context runs and change groups
    raw = []  # ("ctx", l1, l2, r1, r2) | ("chg", l1, l2, r1, r2)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        raw.append(("ctx" if tag == "equal" else "chg", i1, i2, j1, j2))

    body, n = [], 0
    total = sum(1 for kind, *_ in raw if kind == "chg")
    for kind, i1, i2, j1, j2 in raw:
        if kind == "ctx":
            length = i2 - i1
            rows = "".join(_ctx_row(llines[i1 + k], rlines[j1 + k]) for k in range(length))
            if length > context:
                body.append(
                    f'<details class="dctx"><summary>{length} unchanged line'
                    f'{"s" if length != 1 else ""}</summary>{rows}</details>'
                )
            else:
                body.append(rows)
            continue
        n += 1
        rows = _change_rows(llines[i1:i2], rlines[j1:j2])
        ann = _annotation_for(n, rows, annotations)
        accent = f' {ann["tag"]}' if ann and ann.get("tag") else ""
        badge = f'<span class="tag {ann["tag"]}">{esc(ann["label"])}</span> ' if ann and ann.get("label") else ""
        title = f'<span class="dtitle">{esc(ann["title"])}</span>' if ann and ann.get("title") else ""
        note = f'<p class="why">{ann["note"]}</p>' if ann and ann.get("note") else ""
        head = (
            f'<div class="dhead">{badge}<span class="dnum">Change {n} / {total}</span>'
            f'{title}{note}</div>'
        )
        prev = (
            f'<a class="btn" href="#{diff_id}-c{n-1}">&lsaquo;&nbsp;Prev</a>'
            if n > 1 else '<span class="btn off">&lsaquo;&nbsp;Prev</span>'
        )
        nxt = (
            f'<a class="btn" href="#{diff_id}-c{n+1}">Next&nbsp;&rsaquo;</a>'
            if n < total else '<span class="btn off">Next&nbsp;&rsaquo;</span>'
        )
        nav = (
            f'<div class="dnav">{prev}<span class="dpos">Change {n} / {total}</span>'
            f'<a class="btn" href="#{diff_id}">&uarr;&nbsp;All</a>{nxt}</div>'
        )
        body.append(
            f'<section class="dchange{accent}" id="{diff_id}-c{n}">{head}{rows}{nav}</section>'
        )

    step = f'<a class="btn" href="#{diff_id}-c1">Step through &rarr;</a>' if total else ""
    return (
        f'<div class="diff" id="{diff_id}">'
        f'<div class="diff-bar"><div class="seg diff-view">'
        f'<label><input type="radio" name="{diff_id}-view" checked><span>Side&#8209;by&#8209;side</span></label>'
        f'<label><input type="radio" name="{diff_id}-view"><span>Unified</span></label>'
        f'</div><span class="grow"></span>{step}</div>'
        f'<div class="dcols"><span class="l">{esc(left_label)}</span>'
        f'<span class="r">{esc(right_label)}</span></div>'
        f'<div class="diff-body">{"".join(body)}</div></div>'
    )


def main() -> None:
    p = argparse.ArgumentParser(description="Render two files as an in-html .diff fragment.")
    p.add_argument("left", type=Path, help="the 'before' / left file")
    p.add_argument("right", type=Path, help="the 'after' / right file")
    p.add_argument("--left-label", default="before")
    p.add_argument("--right-label", default="after")
    p.add_argument("--id", dest="diff_id", default="d1", help="unique id prefix (for multiple diffs on one page)")
    p.add_argument("--context", type=int, default=3, help="unchanged lines shown inline before collapsing")
    p.add_argument("--annotations", type=Path, help="JSON list of change-block annotations")
    p.add_argument("-o", "--output", type=Path, help="write fragment here (default: stdout)")
    args = p.parse_args()

    annotations = json.loads(args.annotations.read_text()) if args.annotations else None
    if annotations is not None and not isinstance(annotations, list):
        sys.exit("error: --annotations must be a JSON list")

    fragment = render_diff(
        args.left.read_text(),
        args.right.read_text(),
        left_label=args.left_label,
        right_label=args.right_label,
        diff_id=args.diff_id,
        annotations=annotations,
        context=args.context,
    )
    if args.output:
        args.output.write_text(fragment)
        print(f"wrote .diff fragment → {args.output}", file=sys.stderr)
    else:
        print(fragment)


if __name__ == "__main__":
    main()
