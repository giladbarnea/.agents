---
name: jsonl-toolkit
description: Tools and workflows for inspecting large JSONL files and AI session transcripts
last_updated: 2026-08-05
---

Use this skill to inspect, search, summarize, or transform large JSONL files without loading unwieldy lines into the terminal.

The toolkit also has specialized support for AI session collections, exported transcripts, and native Pi sessions.

Load [`smart-compact/SKILL.md`](smart-compact/SKILL.md) only when the task is session compaction.

## Identify the file format

The toolkit handles three formats:

1. Ordinary JSONL contains one JSON value per line. Its schema can be arbitrary.
2. A native AI session is JSONL with a provider-specific session schema.
3. An exported transcript is usually one top-level JSON array stored in a `.json` file.

Do not use JSON-array commands on JSONL. Avoid commands that slurp a large JSONL file into memory.

When the format is unknown, inspect only a bounded prefix first:

```bash
scripts/filestats.sh path/to/file
head -c 300 path/to/file
```

Then choose only the sections below that match the file and task.

## Inspect any large JSONL file

Start by measuring the file:

```bash
scripts/filestats.sh data.jsonl
```

The report includes bytes, lines, words, and token estimates. It also accepts ordinary text and binary files.

Inspect the first few object shapes without printing full values:

```bash
jq -c 'keys_unsorted' data.jsonl | head -20
```

Count a known discriminator when the schema has one:

```bash
jq -r '.type // "NO_TYPE"' data.jsonl | sort | uniq -c | sort -nr
```

Use streaming processing for aggregate work. In Python, parse and process one line at a time rather than building one list of every object.

## Search huge JSONL lines safely

Plain `rg` can print hundreds of kilobytes for one matching line. Use `scripts/rgjsonl.sh` to print a bounded window around a literal match.

```bash
scripts/rgjsonl.sh data.jsonl 'search text'
scripts/rgjsonl.sh data.jsonl query='"role":"user"' span=40:120 rows=1
scripts/rgjsonl.sh data.jsonl query=162 200 1 -m5
```

The script uses PCRE2 literal quoting. It clips match and context lines to the requested width.

Use `query=TEXT` when the query looks like a number or an existing path.

## Probe collections of session JSONL files

Load `scripts/stats_toolkit.py` in IPython when the task spans many AI sessions.

Its functions support:

- Schema probes that omit content values
- Entry-type counts
- Per-session size, line, role, project, and modification statistics
- Collection filtering and distributions
- Optional model-based session labels
- Dry-run deletion of selected paths

The module runs nothing at import time. Start with `probe_schema`, `probe_type_counts`, or `probe_sample` when the provider schema is unknown.

## Work with an exported AI transcript

A `ch -f json` export is a JSON array, not JSONL.

Export a supported session with:

```bash
ch <session-id> -t:s -f json > transcription.json
ch <session-id> -t:s > transcription.md
```

Treat the structured JSON as the source of truth. Convert between the structured export and rendered Markdown with:

```bash
ch parse transcription.json > transcription.md
ch parse -f json transcription.md > transcription.json
```

A Markdown round trip can merge adjacent text blocks and normalize timestamp precision. Compare rendered Markdown rather than raw JSON bytes.

Analyze transcript structure with:

```bash
uv run --script scripts/analyze_transcript_json.py transcription.json
```

The report covers messages, roles, tool pairing, failures, output indices, repeated operations, file touches, and validation commands.

Render a chronological review with:

```bash
uv run --script scripts/render_transcript_review.py transcription.json > review.md
```

The renderer preserves chronology, pairs tools by exact ID, flags unmatched events, and elides only byte-identical repeated skill bodies.

## Work with a native Pi session

Read [`references/pi-session-jsonl.md`](references/pi-session-jsonl.md) before changing a native Pi session.

Use `scripts/pi_session.py` for session resolution, JSONL loading, active-path extraction, identity work, and loader checks.

Run Pi's own loader with:

```bash
node scripts/pi-goldload.mjs session.jsonl
```

A current Pi transcript export includes exact native provenance:

- Messages have `native_entry_id`.
- Tool inputs have `native_tool_call_id` and `native_content_index`.
- Tool outputs have `native_tool_call_id`.

Keep these fields when work must map an exported transcript back to native session entries.

## Transform data through stable identities

Back up a file before changing it in place:

```bash
cp source.jsonl source.backup.jsonl
```

Address records through stable identifiers rather than positions that shift after removal. Transcript examples include `original_index`, `native_entry_id`, and exact tool occurrences.

When decisions are stored separately from their source, bind them to the source checksum. Reject stale decisions before writing.

After a transformation, compare stable identifier sets and count remaining record or block types. This reveals unintended removals and residues without comparing full payloads.

## JSON-array inspection recipes

These commands apply to exported transcript arrays, not JSONL.

Print a flat message inventory:

```bash
jq -r '.[] | "\(.original_index) | \(.type) | \(.role) | \(if .content[0] | type == "object" then .content[0].type + " " + (.content[0].name // "") else "text" end)"' transcription.json
```

Find messages with unusually many content blocks:

```bash
jq '[.[] | {index: .original_index, blocks: (.content | length)}] | sort_by(-.blocks) | .[0:10]' transcription.json
```

Compare stable indices before and after a transformation:

```python
before_indices = {message["original_index"] for message in before}
after_indices = {message["original_index"] for message in after}
removed_indices = sorted(before_indices - after_indices)
added_indices = sorted(after_indices - before_indices)
```
