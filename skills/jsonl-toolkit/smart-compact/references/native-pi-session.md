# Native Pi smart-compaction preserves resumability

Read [`../../references/pi-session-jsonl.md`](../../references/pi-session-jsonl.md) first. It owns Pi's format, tree, identity, backup, and verification contracts.

Paths below are relative to the `jsonl-toolkit` root.

## Choose the workflow by its output

| Workflow | Output | Semantic skeletons | Write behavior |
|---|---|---:|---|
| `generate_compaction_plan.py` and `apply_compaction_plan.py` | Compacted `ch` transcript | Yes | Writes a new transcript |
| `compact_native_pi_session.py` | Resumable native session | No | Creates a new session beside the source |
| `transfer_to_pi_session.py` | Resumable native session | Yes | Backs up and changes an explicit target copy |

The transcript applier and native applier consume one semantic plan in different ways.

Do not pass a compacted transcript to the native applier. Pass the pruned source, plan, and native target copy.

## The default native compactor uses a fixed decisions schema

Run its dry-run before other investigation:

```bash
uv run smart-compact/scripts/compact_native_pi_session.py \
  <session-id-or-path> --dry-run --outline
```

The dry-run resolves the file and prints:

- Entry and message counts
- Active and abandoned branch counts
- Byte weights by role
- Tool distribution
- Shrink candidates
- Old session-ID occurrences
- The active-path story with `DROP`, `SHRINK`, and `KEEP` actions

Commit the reviewed policy with:

```bash
uv run smart-compact/scripts/compact_native_pi_session.py \
  <session-id-or-path> \
  [--decisions decisions.json] \
  [--rewrite-content-id]
```

The optional decisions file has this shape:

```json
{
  "drop_custom_types": ["pi-time-sense"],
  "drop_tool_units": ["todo"],
  "keep_thinking": true,
  "shrink_always": ["read", "read_many_files", "write"],
  "shrink_threshold": 800,
  "drop_entry_ids": []
}
```

The compactor creates a new session identity and file. It never changes its source.

It keeps only the active path, removes selected tool units atomically, shrinks selected results, and re-chains survivors.

It verifies the result through the parent Pi-session helpers. It also runs Pi's loader and `ch` discovery when available.

## The semantic-plan applier changes an explicit target copy

The native semantic-plan applier currently lives at the parent script level:

```bash
uv run scripts/transfer_to_pi_session.py \
  pruned.json \
  compaction-plan.json \
  session-copy.jsonl
```

The pruned transcript must come from a current `ch -f json` Pi export. It must carry complete native provenance.

The applier validates every mapping before it creates a backup. It then:

1. Applies message and text drops.
2. Replaces selected native tool calls with skeleton or file-reference text.
3. Removes each matching tool-result entry.
4. Preserves surrounding text and thinking positions.
5. Keeps only the active path.
6. Re-chains surviving entries.
7. Adds a hidden smart-compact watermark.

The applier accepts version-2 plans only.

## Watermarks make later passes incremental

Each completed native pass appends a hidden `smart-compact-watermark` custom entry.

The watermark records:

- The latest surviving exported message
- The latest reviewed source message
- The pass number
- Compaction statistics

The next pruning and transfer pass selects messages after the latest watermark automatically.

Set an explicit native boundary with the same entry ID in both commands:

```bash
uv run smart-compact/scripts/prune_transcript.py \
  transcription.json \
  --native-session session-copy.jsonl \
  --from-entry-id <native-id> \
  > pruned.json

uv run scripts/transfer_to_pi_session.py \
  pruned.json \
  compaction-plan.json \
  session-copy.jsonl \
  --from-entry-id <native-id>
```

The boundary message itself is excluded. A boundary cannot split a tool-call and result occurrence.

Completed retries can reuse one full tool ID on both sides of a boundary.

## Skeletons map by exact native occurrence

Each skeleton replacement carries its source and native positions:

```json
{
  "tool_skeletons": [
    {
      "source_content_index": 2,
      "tool_id": "toolu_full-native-id",
      "native_entry_id": "native-assistant-entry",
      "native_content_index": 4,
      "content": "<tool-skeleton .../>"
    }
  ]
}
```

The native applier maps by `native_entry_id` and `native_content_index`. It verifies the tool ID and name without using them as occurrence identity.

## The target copy gets a backup before replacement

After every preflight passes, the applier creates a verified sibling backup:

```text
session-copy.jsonl.backup-0
```

It then atomically replaces the target. It does not mint or rewrite the target's session ID.

Prepare the copy with its intended identity before transfer. Keep the backup until the user accepts the result.
