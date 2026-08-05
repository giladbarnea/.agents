---
name: jsonl-toolkit
description: Tools and workflows for inspecting large JSONL files and AI session transcripts
last_updated: 2026-08-05
---

Use this skill for large JSONL files, exported AI transcripts, and native Pi session files.

The parent toolkit makes no smart-compaction decisions. Load [`smart-compact/SKILL.md`](smart-compact/SKILL.md) only when the task is session compaction.

## Choose the correct file contract first

The toolkit handles two related formats:

1. Native session files use one JSON object per line and end in `.jsonl`.
2. `ch -f json` exports use one top-level JSON array and usually end in `.json`.

Do not pass one format to a script that expects the other.

## Sample huge JSONL lines without flooding the terminal

Use `scripts/rgjsonl.sh` when ordinary `rg` prints hundreds of kilobytes per matching line.

```bash
scripts/rgjsonl.sh session.jsonl '"toolName":"Bash"'
scripts/rgjsonl.sh session.jsonl query='"role":"user"' span=40:120 rows=1
scripts/rgjsonl.sh session.jsonl query=162 200 1 -m5
```

The script finds a literal anchor through PCRE2. It prints a bounded character window and clipped context rows.

Use `query=TEXT` when the query looks like a number or an existing path.

## Measure files before choosing an inspection strategy

```bash
scripts/filestats.sh path/to/file.jsonl path/to/export.json
```

The report includes bytes, lines, words, and token estimates. It also handles arbitrary text and binary files.

## Probe collections of session JSONL files

Load `scripts/stats_toolkit.py` in IPython when the task spans many sessions.

Its workflow has five phases:

1. Probe unknown schemas without printing private content.
2. Collect per-session size, line, role, project, and entry-type statistics.
3. Filter and inspect distributions.
4. Label sessions through a selected Pi model when structure cannot answer the question.
5. Delete selected paths only after a dry-run.

The module runs nothing at import time.

## Export and parse supported AI sessions with `ch`

```bash
ch <session-id> -t:s -f json > transcription.json
ch <session-id> -t:s > transcription.md
```

Treat the structured JSON as the source of truth.

Convert in either direction with:

```bash
ch parse transcription.json > transcription.md
ch parse -f json transcription.md > transcription.json
```

For Pi exports, `ch -f json` adds native provenance:

- Messages carry `native_entry_id`.
- Tool inputs carry `native_tool_call_id` and `native_content_index`.
- Tool outputs carry `native_tool_call_id`.

`ch parse` accepts these JSON-only fields and omits them from XML output.

A Markdown round trip can merge adjacent text blocks and normalize timestamp precision. Compare rendered Markdown rather than raw JSON bytes.

## Analyze an exported transcript without compaction assumptions

```bash
uv run --script scripts/analyze_transcript_json.py transcription.json
```

The report includes:

- Message and role counts
- Tool-call pairing and failures
- Tool-output indices
- Repeated tools and duplicate Bash commands
- File touches, repeated reads, and repeated mutations
- Build, lint, and test command runs

The analyzer uses deterministic structure and configured error markers. Read source content when semantic conclusions matter.

## Render a chronological transcript review

```bash
uv run --script scripts/render_transcript_review.py transcription.json > review.md
```

The renderer:

- Preserves message and prose order
- Pairs tool inputs and outputs by exact ID
- Flags unmatched calls and results
- Emits repeated skill bodies once while preserving each invocation instruction
- Labels native compaction entries as boundaries

## Work with native Pi session trees through one parent module

Read [`references/pi-session-jsonl.md`](references/pi-session-jsonl.md) before changing a native Pi file.

Use `scripts/pi_session.py` for:

- Session ID and path resolution
- Native JSONL loading
- Active-path extraction
- Session ID audits and rewrites
- New session path generation
- Pi loader and `ch` discovery checks

Run Pi's own loader directly with:

```bash
node scripts/pi-goldload.mjs session.jsonl
```

## Use stable identities before transforming data

Back up a source before an in-place transformation:

```bash
cp transcription.json transcription.backup.json
```

Use a stable identifier such as `original_index`, `native_entry_id`, or an exact tool occurrence. Do not use a shifting array position after removals.

Bind a transformation plan to the exact source checksum when stale decisions could corrupt output.

## Useful inspection recipes

A flat inventory reveals message shape before content analysis:

```bash
jq -r '.[] | "\(.original_index) | \(.type) | \(.role) | \(if .content[0] | type == "object" then .content[0].type + " " + (.content[0].name // "") else "text" end)"' transcription.json
```

Find messages with unusually many content blocks:

```bash
jq '[.[] | {index: .original_index, blocks: (.content | length)}] | sort_by(-.blocks) | .[0:10]' transcription.json
```

Compare stable index sets before and after a transformation:

```python
before_indices = {message["original_index"] for message in before}
after_indices = {message["original_index"] for message in after}
removed_indices = sorted(before_indices - after_indices)
added_indices = sorted(after_indices - before_indices)
```

Count remaining block types after each transformation:

```python
from collections import Counter

block_types = Counter()
for message in data:
    for block in message.get("content", []):
        if isinstance(block, str):
            block_types["text"] += 1
            continue
        block_types[f'{block.get("type", "?")}:{block.get("name", "?")}'] += 1

print(block_types.most_common())
```
