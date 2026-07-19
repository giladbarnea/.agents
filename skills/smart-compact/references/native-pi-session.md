# Native pi session (.jsonl): format & resumable-compaction contract

Read this when the user asks to compact the **native pi session file itself** so the
compacted session stays **resumable** (as opposed to compacting a `ch` transcription
export). Everything here was reverse-engineered from
`/opt/homebrew/lib/node_modules/@earendil-works/pi-coding-agent/dist/core/session-manager.js`;
consult it directly for anything not covered.

## File anatomy

One JSON object per line (strict LF framing).

- **Line 1 — session header**: `{"type":"session","version":3,"id":"<uuidv7>","timestamp":...,"cwd":...}`.
  pi parses it separately (reads only the first line for discovery). It has **no
  `parentId`** and is NOT part of the message tree.
- **Every other line — tree entry**: `{"type":..., "id":"<8-hex>", "parentId":..., "timestamp":..., ...}`.
  Types: `message` (roles: `user`, `assistant`, `toolResult`, `bashExecution`),
  `model_change`, `thinking_level_change`, `session_info`, `custom`,
  `custom_message` (e.g. `pi-time-sense` murmur, `pi-user-agents` sub-agents),
  `compaction`, `branch_summary`, `label`.
- Assistant message content blocks: `text`, `thinking`, `toolCall{id,name,arguments}`.
  A `toolResult` entry links back via `.message.toolCallId` == the toolCall block's `.id`
  (this pairing is content-level and independent of the tree). Result payloads live in
  `.message.content[]` text blocks.

## The five invariants of a resumable file

1. **Single root.** Exactly one tree entry has `"parentId": null` — literal null, not an
   absent key (pi's root test is `parentId === null`).
2. **Active path only.** On resume pi takes the LAST line as leaf and walks `parentId`
   up to the root. Entries not on that walk are abandoned branches (rewinds) and are
   never replayed. **Compact the active path; do not linearize raw file order** — that
   resurrects rewound content.
3. **Re-chain after drops.** When entries are removed, re-link survivors in order:
   first survivor gets `parentId: null`, each next points to the previous survivor's
   `id` (this mirrors pi's own `createBranchedSession`).
4. **Pairing closure.** Never orphan a toolCall or a toolResult. Drop call+result as a
   unit, or keep both and shrink the result's text in place.
5. **Header identity.** For a NEW resumable session: new uuidv7 `id` in the header,
   filename `<ISO-timestamp with : . replaced by ->_<id>.jsonl` in the same sessions
   directory. Occurrences of the old id inside message *content* are history — leave
   them unless the user asks (flag it).

## What maps to the skill's compaction rules

- Drop: `pi-time-sense` entries; `todo` toolCall+toolResult units; messages emptied by
  block removal. Keep `thinking` blocks unless the user opts out — ask if unstated.
- Shrink in place (keeps pairing, zero tree risk): toolResult text > ~800 chars, and
  always for `read`/`read_many_files`/`write` results.
- Keep verbatim: user/assistant `text` blocks (byte-for-byte), structural entries,
  `custom`/`pi-user-agents`, `bashExecution`, small tool results.

## Discovery and resolution facts

- pi discovers sessions by globbing `*.jsonl` — a file named `<uuid>.json` (no `l`)
  would be **silently undiscoverable**. Always use the `.jsonl` extension.
- Session id resolves via the **header's `id` field** (line 1). The filename is
  convention (`<ts>_<id>.jsonl`) but not authoritative — header wins.
- pi loads messages without content-type validation: a message containing only
  `thinking` blocks (e.g. after todo-stripping removes the toolCall) is harmless.

## Native compaction script

`scripts/compact_native_pi_session.py` — one command that does the full native-resumable
compaction. Accepts a **session id or file path** as argument.

**Protocol — your first command is the dry-run:**
```bash
uv run scripts/compact_native_pi_session.py <session-id-or-path> --dry-run --outline
```
Don't pre-investigate. This resolves the file (prints the path), runs the census
(entry types, byte weights, tool distribution, shrink candidates), audits old-id
content occurrences with locations, and prints the active-path story annotated with
what the default decisions would do (`DROP`/`SHRINK`/`KEEP` per entry). Read this
outline to make your semantic decisions — then commit:

```bash
uv run scripts/compact_native_pi_session.py <session-id-or-path> [--decisions decisions.json] [--rewrite-content-id]
```

The commit run:
1. **Bootstraps** a new resumable copy (fresh uuidv7, pi filename convention, header swap).
2. **Transforms** driven by decisions (or defaults): drop custom_message types,
   drop tool units (call+result as atomic pairs), optional thinking strip, in-place
   shrink of large tool results. Active-path-only, re-chaining, and pairing closure
   are hard-coded invariants.
3. **Verifies** structurally (single root, chain reaches all, pairing, text fidelity
   vs source active path, no off-path leakage) and via pi's own session-manager
   gold-standard loader (`pi-goldload.mjs`, SKIPPED gracefully if node absent).
4. `--rewrite-content-id`: optionally replaces old session id inside message content
   with the new id (off by default; the census tells you if it matters).

The original file is **never modified**. Output is JSON on stdout: `{new_id, new_file, stats}`.

Also useful for orientation: `ch <session-id> -t:s` renders the session as a readable
transcript with tools shortened — use it if the outline isn't enough story context.

Decisions file format (all fields optional, defaults apply for omitted):
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

## Legacy helper

`scripts/transfer_to_pi_session.py` applies a ch-transcript compaction to the native
jsonl by **deletion only** (no in-place shrinking). It enforces pairing closure, splices
`parentId` across deletions, backs up first, and re-validates. Use
`compact_native_pi_session.py` for new work — it subsumes this script's capabilities.

## Verification (do all three)

1. Structural: one root; every `parentId` resolves; chain from last line reaches every
   tree entry; toolCall ids == toolResult toolCallIds as sets; active-path user+assistant
   text byte-identical to the original's active path.
2. Gold standard — load through pi's own code (note: `leafId` must be `undefined`,
   NOT `null`, which means "empty"):
   ```js
   import { loadEntriesFromFile, buildContextEntries, buildSessionContext } from
     '/opt/homebrew/lib/node_modules/@earendil-works/pi-coding-agent/dist/core/session-manager.js';
   const entries = loadEntriesFromFile(file);
   const byId = new Map(entries.map(e => [e.id, e]));
   const reached = buildContextEntries(entries, undefined, byId).length; // must equal entries.length - 1
   ```
3. Discovery smoke: `ch <new-id> -l` resolves the new session (if `ch` is available).
