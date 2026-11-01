---
last_updated: 2026-11-01
---

# Native Pi smart-compaction preserves resumability

Read [`../../references/pi-session-jsonl.md`](../../references/pi-session-jsonl.md) first. It owns Pi's format, tree, identity, backup, and verification contracts.

Paths below are relative to the `jsonl-toolkit` root.

## Choose the workflow by its output

| Workflow | Output | Semantic skeletons | Write behavior |
|---|---|---:|---|
| [`lib/pi.mjs`](../../references/pi-lib.md) `Draft` | The same session, with selected context entries omitted or replaced | Written by you | Appends native `context_edit` entries in place after a verified backup, or writes a copy |
| `lib/pi.mjs` `Session.install` | Original archive with a prepared context installed | Already prepared | Writes a new output file with the archive's identity |
| `generate_compaction_plan.py` and `apply_compaction_plan.py` | Compacted `ch` transcript | Yes | Writes a new transcript |
| `compact_existing_pi_session_inline.py` | Resumable native session | Yes | Backs up and changes an explicit target copy |

Prefer the library for a native Pi session. It reads the session file itself, so it needs no `ch` export and cannot lose entries an export leaves out. Every other row is [being sunset](../../references/pi-lib.md#everything-else-is-being-sunset). Until it is removed, the inline applier serves only to transfer an existing `ch`-transcript plan.

Do not pass a compacted transcript to the native applier. Pass the pruned source, plan, and native target copy.

## Edit the live context in place

Use this for a session that keeps running, including one compacted this way before. Pi's own `context_edit` entry omits or replaces one model-visible entry. A later edit of the same entry wins. Stored history stays untouched.

Work in a Node script with [the library](../../references/pi-lib.md). Read `context.outline()` and `context.render()`, select spans, and collect decisions in a `Draft`. Preview with `draft.context()`, then `apply()`. To fold a tool exchange, replace the assistant entry with a skeleton and omit its result. `selection.complete()` finds both sides.

From a shell, `node scripts/pi_context_edit.mjs dump SESSION out/` writes `context.md` and `outline.txt`. `apply SESSION decisions.json` applies decisions that `draft.save()` wrote.

A running Pi process keeps its context in memory and would append its next turn to the old leaf, which orphans the edits. Apply only to a stopped session, or restart that Pi and resume the session before its next turn.

## Install a prepared context window

```bash
node scripts/install_pi_context.mjs session.jsonl prepared-context.json output.jsonl
```

In a script, call `open('session.jsonl').install(messages).apply({ to: 'output.jsonl' })`.

`prepared-context.json` is an ordered JSON array of Pi messages, not a `ch` export. It needs no session header or tree entries.

The output preserves the archive's bytes, session identity, title, selected model, and thinking level. Only the prepared messages enter the active context. A new native root starts that context because Pi's `context_edit` API cannot omit system, Bash, or summary entries.

The installer uses Pi's normal conversion for custom, Bash, and summary messages. It preserves message content, tool-call IDs, and thinking payloads. It clears imported usage so context installation neither duplicates costs nor reuses historical context-token counts. It makes no compaction or thinking decisions.

Both inputs stay unchanged. The output must not exist. Keep it outside Pi's session directory until replacing the stopped original, since both files carry the same session ID.

Run its tests with `node --test tests/test_install_pi_context.mjs`. They use the installed Pi loader without model calls.

## The semantic-plan applier changes an explicit target copy

The native semantic-plan applier currently lives at the parent script level:

```bash
uv run scripts/compact_existing_pi_session_inline.py \
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

uv run scripts/compact_existing_pi_session_inline.py \
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
