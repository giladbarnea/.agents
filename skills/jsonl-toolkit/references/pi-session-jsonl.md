# A native Pi session is a tree stored as JSONL

Read this reference before inspecting or changing a native Pi session file.

This contract comes from Pi's `dist/core/session-manager.js`. Consult that source when this reference does not cover a case.

## The first line is not part of the message tree

A native session uses strict LF-delimited JSON objects.

Line 1 is the session header:

```json
{"type":"session","version":3,"id":"<uuidv7>","timestamp":"...","cwd":"..."}
```

The header has no `parentId`. Pi reads it separately for session discovery.

Every later line is a tree entry:

```json
{"type":"message","id":"<8-hex>","parentId":"<8-hex-or-null>","timestamp":"...","message":{}}
```

Known entry types include:

- `message`
- `model_change`
- `thinking_level_change`
- `session_info`
- `custom`
- `custom_message`
- `compaction`
- `branch_summary`
- `label`

Message roles include `user`, `assistant`, `toolResult`, and `bashExecution`.

Assistant content can contain `text`, `thinking`, and `toolCall` blocks. A tool result links through `message.toolCallId` to the call block's `id`.

Pi can reuse a tool-call ID for a later retry. Pair each result with its one unmatched preceding call on the active path.

## The last line selects the active path

Pi treats the last tree entry as the active leaf. It follows `parentId` links back to the root.

Entries outside that walk are abandoned branches. Raw file order is not conversation order when the session contains rewinds.

Use `scripts/pi_session.py` to resolve a session, load its entries, and extract its active path.

## Five invariants keep a session resumable

1. Exactly one tree entry has `parentId: null`.
2. Every non-null `parentId` resolves to another tree entry.
3. The chain from the last entry reaches every active entry exactly once.
4. Every surviving tool call has its matching result occurrence.
5. The header ID and intended session identity agree.

When a transformation removes active entries, re-chain the survivors in order. Set the first survivor's `parentId` to null.

Never keep a call without its result. Remove the occurrence as a unit, or preserve both sides.

## Discovery uses the header ID

Pi discovers session files through `*.jsonl`. A `.json` file is not discoverable.

The filename convention is:

```text
<ISO-timestamp-with-colons-and-dots-replaced>_<session-id>.jsonl
```

The header's `id` field is authoritative. Renaming a copied file does not give it a new session identity.

Text that mentions an old session ID is historical content. Do not rewrite it unless the task requires that change.

## Exported transcript provenance maps back to native entries

A current `ch -f json` Pi export adds provenance fields:

- Every visible native message gets `native_entry_id`.
- Tool inputs get `native_tool_call_id` and `native_content_index`.
- Tool outputs get `native_tool_call_id`.

These fields preserve exact native occurrences. The short display `id` is not enough because retries can reuse it.

`ch parse` accepts the fields and omits them from rendered XML.

## Protect explicit copies before writing

When a user names a target copy, protect the original session rather than the named copy.

1. Resolve the original and target paths.
2. Confirm that they are different files and inodes.
3. Record both SHA-256 hashes.
4. Confirm that the target contains the intended source snapshot.
5. Give the target its intended header ID.
6. Create a verified sibling backup before the first write.
7. Replace the target atomically.
8. Confirm that the original hash did not change.

If the live original grew after the copy, accept only an exact target-to-source prefix match.

Preserve untouched native lines byte-for-byte when the transformation supports it.

## Verify structure through both implementations

First verify the JSONL structure directly:

1. Confirm one root.
2. Resolve every parent.
3. Walk from the last entry and reach every active entry.
4. Pair every tool-call occurrence with one result occurrence.
5. Compare conversation text against the source when text must remain unchanged.

Then load the result through Pi's own session manager:

```js
import {
  loadEntriesFromFile,
  buildContextEntries,
  buildSessionContext,
} from '/opt/homebrew/lib/node_modules/@earendil-works/pi-coding-agent/dist/core/session-manager.js';

const entries = loadEntriesFromFile(file);
const byId = new Map(entries.map(entry => [entry.id, entry]));
const reached = buildContextEntries(entries, undefined, byId).length;
const context = buildSessionContext(entries, undefined, byId);
```

`reached` must equal `entries.length - 1`. Pass `undefined` as the leaf ID. `null` asks Pi for an empty context.

Run the packaged loader with:

```bash
node scripts/pi-goldload.mjs session.jsonl
```

When `ch` is available, also confirm discovery:

```bash
ch <session-id> -l
```
