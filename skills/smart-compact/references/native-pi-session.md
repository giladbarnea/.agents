# Native pi session (.jsonl): format & resumable-compaction contract

Read this when the user asks to compact the **native pi session file itself** so the
compacted session stays **resumable** (as opposed to compacting a `ch` transcription
export). Everything here was reverse-engineered from
`/opt/homebrew/lib/node_modules/@earendil-works/pi-coding-agent/dist/core/session-manager.js`;
consult it directly for anything not covered.

## Choose the workflow by the required output

The current tools have separate contracts:

| Workflow | Output | Supports semantic skeletons | Write behavior |
|---|---|---:|---|
| `generate_compaction_plan.py` + `apply_compaction_plan.py` | Compacted `ch` transcription | Yes | Writes a new transcription |
| `compact_native_pi_session.py` | Resumable native session | No | Creates a new session beside the source |
| `transfer_to_pi_session.py` | Resumable native session | Yes | Edits an explicit target copy after backup |

The transcription apply stage and native plan applier consume the same semantic plan in
different ways. The transcription apply stage writes a compacted transcription. The
native plan applier consumes the pruned source, the plan, and a native target copy.
Do not pass the compacted transcription to the native plan applier.

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
- Shrink in place (keeps pairing, zero tree risk): toolResult text above the configured
  threshold (800 by default). `read`/`read_many_files`/`write` use a 400-character
  minimum instead.
- Keep verbatim: user/assistant `text` blocks (byte-for-byte), structural entries,
  `custom`/`pi-user-agents`, `bashExecution`, small tool results.

## Discovery and resolution facts

- pi discovers sessions by globbing `*.jsonl` — a file named `<uuid>.json` (no `l`)
  would be **silently undiscoverable**. Always use the `.jsonl` extension.
- Session id resolves via the **header's `id` field** (line 1). The filename is
  convention (`<ts>_<id>.jsonl`) but not authoritative — header wins.
- pi loads messages without content-type validation: a message containing only
  `thinking` blocks (e.g. after todo-stripping removes the toolCall) is harmless.
- `ch -f json` preserves Pi provenance in additive JSON-only fields. Native messages
  carry `native_entry_id`; tool inputs carry full `native_tool_call_id` and zero-based
  `native_content_index`; tool outputs carry full `native_tool_call_id`. The shortened
  display `id` remains for compatibility. `ch parse` accepts these fields and omits them
  from XML output.

## Native default-policy compaction script

`scripts/compact_native_pi_session.py` performs structural native compaction with its
fixed decisions schema. It accepts a **session id or file path** as its source argument.
It does not consume `compaction-plan.json`, create semantic skeletons, select a tail
boundary, or edit a user-named target in place.

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
3. **Checks** structure (single root, chain reaches all, pairing, text fidelity
   vs source active path, no off-path leakage). After writing, it also runs pi's own
   session-manager loader and `ch` discovery smoke checks when available. Those two
   smoke checks report failure but do not currently change the command's exit status.
4. `--rewrite-content-id`: optionally replaces old session id inside message content
   with the new id (off by default; the census tells you if it matters).

This script never modifies its source. It can still write its new output before
reporting a structural verification failure, so inspect the exit status and verification
report before using the new session. Output on success is JSON on stdout:
`{new_id, new_file, stats}`.

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

## Native semantic-plan applier

`scripts/transfer_to_pi_session.py` applies the semantic plan directly to a named native
target copy:

```bash
uv run scripts/transfer_to_pi_session.py \
  pruned.json compaction-plan.json session-copy.jsonl
```

`pruned.json` must come from the current `ch -f json` Pi export and the current pruner.
The applier requires `native_entry_id`, `native_tool_call_id`, and
`native_content_index` provenance instead of prefix or text matching. An older pruned
export fails before writing with instructions to re-export and re-prune.

It validates the source-bound plan and all mappings before writing. It applies text drops
and block-level tool drops or replacements, inserts skeleton and file-reference strings
where tool-call blocks were, and removes paired tool-result entries. It preserves
surrounding text and native thinking blocks, keeps only the active path, and re-chains
the survivors.

Each planned skeleton has an exact association in its replacement entry:
```json
{
  "tool_skeletons": [
    {"tool_id": "toolu_full-native-id", "content": "<tool-skeleton .../>"}
  ]
}
```
The generator derives this full ID from the selected source block. The native applier maps
the skeleton by this ID only. It never infers the target from a command or tool name.

After all checks pass, it writes a verified sibling `<target>.backup-N` and atomically
replaces the target. It does not mint or rewrite the session ID. Prepare the target copy
with its intended identity before running it.

For compatibility, an older plan without `tool_skeletons` remains safe only when its message
has exactly one skeleton and one source tool input. The applier binds that pair through the
source input's full native provenance. It refuses every ambiguous older plan before writing
and asks for a regenerated plan.

`compact_native_pi_session.py` does not subsume this applier. The native compactor creates
a new session using its fixed decisions schema. The native plan applier transfers the
semantic plan onto an existing named copy.

## Safe named-copy in-place workflow

The protected file is the original session. A copy that the user explicitly names as
the target is not the original and may be edited in place.

1. Resolve both paths and confirm that the target is not the original file or inode.
2. Record the original and target SHA-256 hashes before any write.
3. Confirm that the target contains the intended source snapshot. If the live original
   gained entries after the copy, accept only an exact target-to-source prefix match.
4. Create a sibling backup of the target before its first write. Never overwrite an
   existing backup.
5. Give the target its own header session ID. The header is authoritative for discovery;
   a copied filename alone does not change session identity. Leave old session IDs inside
   historical message content unchanged unless the user asks.
6. Apply changes only to the target. Preserve untouched native lines byte-for-byte when
   the writer supports it, especially any prefix outside the requested compaction scope.
7. Run all verification below against the target. Confirm that the original hash stayed
   unchanged and keep the backup until the user accepts the result.

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
