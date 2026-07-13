#!/usr/bin/env python3
"""Mark one transcript object for removal by index, guarded by a content substring.

The transcript is a JSON array of message objects, each with a `content` list whose
items are strings and/or dicts (thinking / tool-input / tool-output). We flatten that
content into a single searchable blob; if `--safeguard` is found there, we set
`"remove": true` on the object at `--index`. The safeguard is a soft sanity check that
the index still points at the object we think it does, so a hand-authored (index,
substring) pair can't silently mark the wrong message.
"""
import argparse
import json
import sys


def flatten_content(content: list) -> str:
    parts: list[str] = []
    for item in content:
        if isinstance(item, str):
            parts.append(item)
        else:
            parts.append(json.dumps(item, ensure_ascii=False))
    return "\n".join(parts)


def preview(content: list, width: int = 240) -> str:
    blob = flatten_content(content).replace("\n", " ")
    return blob[:width]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("path")
    ap.add_argument("-i", "--index", type=int, required=True, help="0-based array index")
    ap.add_argument("--safeguard", required=True,
                    help="plain substring expected inside the target object's content")
    args = ap.parse_args()

    with open(args.path, encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        print(f"ERROR: {args.path} is not a JSON array", file=sys.stderr)
        return 2
    if not (0 <= args.index < len(data)):
        print(f"ERROR: index {args.index} out of range 0..{len(data) - 1}", file=sys.stderr)
        return 2

    obj = data[args.index]
    haystack = flatten_content(obj.get("content", []))

    if args.safeguard not in haystack:
        print(f"MISMATCH at index {args.index}: safeguard not found.", file=sys.stderr)
        print(f"  safeguard : {args.safeguard!r}", file=sys.stderr)
        print(f"  obj type  : {obj.get('type')} / {obj.get('role')}", file=sys.stderr)
        print(f"  preview   : {preview(obj.get('content', []))}", file=sys.stderr)
        return 1

    already = obj.get("remove") is True
    obj["remove"] = True

    with open(args.path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")

    tag = "already marked" if already else "marked"
    print(f"OK [{args.index}] {tag} remove=true | {obj.get('type')} | {preview(obj.get('content', []), 120)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
