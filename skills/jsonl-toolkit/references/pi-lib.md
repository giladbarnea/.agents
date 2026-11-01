---
description: Node building blocks for reading and changing native Pi sessions, and the design approach that governs them.
last_updated: 2026-11-01
---

# Work with a Pi session through `lib/pi.mjs`

Import the library in a Node script. It gives you building blocks that chain. It does not decide what to keep.

## Design approach

Gilad set this approach on 2026-11-01, when the library replaced a scattered set of scripts. Keep it when you change the library. Other agents will extend the library as they find cases where it fails. The approach is what must survive those changes.

1. **Building blocks, not a solution.** The library gives small atomic operations: open a session, select entries, decide edits, preview, check and write. The agent composes them for the case in front of it. Do not add an operation that does a whole job, such as "compact this session" or "drop the noise". The library makes the agent's chosen actions convenient. It does not choose them.
2. **Blocks chain and feed each other.** A selection feeds a draft. A draft gives a preview context. A context gives selections again. A new block takes and returns these same types, so it composes with every existing block.
3. **The library knows the harness, never the case.** The table below draws the line.
4. **Pi first.** Pi is about 95% of the use. Do not generalize for Codex or Claude in advance. Add their knowledge only when a real task needs it, and keep Pi's path unchanged.
5. **Keep it small.** An ORM such as SQLAlchemy is a useful picture only for chained queries and for pending changes that commit at once. This problem is about ten thousand times simpler than a database, and it grew out of a scrappy collection of scripts. Keep one small file of plain classes and functions: no configuration, plugin system, schema layer or registry.
6. **Node, to use Pi itself.** The library imports Pi's session projection, token estimator and message conversion, so its view of a session is Pi's view. Do not reimplement what Pi exports. Work around a Pi behavior only where it does harm, as `open()` does for Pi's loader, which rewrites the file it reads.
7. **Fail loudly.** Refuse instead of guessing: an ambiguous session reference, an entry Pi cannot edit, a broken tool exchange, a file that changed after it was read. Never repair input silently.
8. **Remove before you add.** Before you add a block, check whether an existing block covers the need, or whether two blocks can collapse into one. Before you add a script, check whether it should be a block. When the library makes a script redundant, remove the script.

| Knowledge | Where it belongs |
|---|---|
| Pi's session format, tree, active path and discovery | The library |
| What `context_edit` can target, and that a later edit of an entry wins | The library |
| How Pi pairs tool calls with results, and how it converts custom, Bash and summary messages for providers | The library |
| Safe writing: no repair on read, fingerprints, backups, append-only output, reload checks | The library |
| smart-compact's notation formats, such as the skeleton | The library, as pure formatters of text the agent writes |
| Which entries matter, what to summarize, summary wording, chapters, thresholds, custom types to drop | The agent's own script for the case |
| How to judge relevance and compaction quality | The [`smart-compact`](../smart-compact/SKILL.md) skill |

Facts about the harness belong in the library, because without them it is not useful. Facts about one session, one project or one compaction policy never do. If a block needs a value that only one case would set, the case passes it in or does that step itself.

### When you extend it

1. Start from a real task where the library failed or forced a workaround. Name the task in the commit message.
2. Add the smallest block that removes the workaround. Prefer a new selection filter or draft operation to a new class.
3. Add a falsifiable test to `tests/test_pi_lib.mjs`. Break the guarantee on purpose and confirm that the test fails.
4. Update this reference, and remove whatever the change made redundant.

## Shrink everything else

Gilad decided on 2026-11-01 that this library is where the toolkit's capability grows. Every other script, pipeline and tool reference in `jsonl-toolkit` and `smart-compact` should eventually be eliminated. Help that happen: keep a light finger on the trigger.

1. When an old resource fails or falls short, do not repair or extend it. Add the missing building block to the library, under the design approach above.
2. When the library covers all or part of an old resource's job, remove the resource, or cut it down to what the library does not cover yet. Remove its docs and tests with it. `compact_native_pi_session.py` went this way on 2026-11-01.
3. The judgment guidance in `smart-compact`, such as relevance, summaries and thinking rules, is not a resource to eliminate. It tells the agent what to decide; the library carries out the decisions.

## Use it

```js
import { open, skeleton } from '/Users/giladbarnea/.pi/agent/skills/jsonl-toolkit/lib/pi.mjs';

const session = open('01a18383-2386');              // a path, or a unique session-ID prefix
const context = session.context();                   // what the model receives now
console.log(context.outline());                      // one line per entry: ID, role, tokens, time, first line
const draft = session.edit()
  .omit(context.custom('pi-time-sense'))
  .omit(context.between('c73b1603', '2a3102af').editable().except('851591e9'))
  .replace('777c6690', skeleton({ name: 'codemode', command: 'pytest', purpose: 'Validate', outcome: '152 passed' }))
  .rewrite('4d4d6c84', content => content.filter(block => block.type !== 'thinking'));
console.log(draft.report());                          // entries and estimated tokens, before and after
console.log(draft.context().render({ clip: 300 }));   // the preview; nothing is written yet
draft.apply({ marker: { pass: 2 } });                 // checked, backed up, appended in place
```

UUIDv7 session IDs start with a timestamp, so sessions created in the same minute share a short prefix. `open()` then lists the candidates and stops.

## The parts

1. **`open(reference)` returns a `Session`.** It has `path`, `bytes`, `fingerprint`, `header`, `entries`, `entry(id)`, `branch`, `context()`, `edit(decisions)`, `install(messages)` and `check()`. Reading never changes the file.
2. **`Context` is the whole model context.** It adds `item(id)`, `messages`, `model`, `tokens`, `usage` and `wire(model)` to a selection. `tokens` is Pi's character estimate, counting the current system prompt once. `usage` is what the provider billed for the last assistant message. `wire()` is async and returns the messages after Pi's provider conversion.
3. **`Selection` is an ordered subset.** `where`, `except`, `between`, `roles`, `custom`, `editable`, `find`, `largest` and `complete` each return a new selection. `ids`, `length`, `tokens`, `first`, `last`, `outline()` and `render({ clip })` read it.
4. **Each item** has `id`, `role`, `label`, `customType`, `timestamp`, `content`, `messages`, `entry`, `model`, `tokens`, `editable`, `edited`, `toolCalls`, `answers` and `text`.
5. **`Draft` collects decisions.** `omit`, `replace`, `rewrite` and `keep` take IDs, items, selections, or arrays of them. The last decision for an entry wins. `decisions` and `save(path)` export them, and `session.edit(decisions)` restores them. `context()`, `check()`, `report()` and `apply({ to, marker })` act on them.
6. **`Change` holds the entries to append.** It materializes them once, so the checked entries are the written entries. It has `context`, `check()` and `apply({ to })`.
7. **Notation:** `skeleton({ name, command, purpose, outcome, meaning })` and `fileReference(operation, path, id)` format smart-compact's notation with escaped attributes.

## The library enforces these rules

1. Pi's `context_edit` can change only user, assistant, tool-result and custom-message entries. Targeting a system or Bash entry raises.
2. `check()` raises when a tool call lacks its result, or a result lacks its call. `complete()` adds the missing side of every exchange.
3. A draft's `check()` also raises when the context would start with a non-user message. Pi sends custom, Bash and summary messages as user messages, so those count as user.
4. `apply()` runs `check()` first. In place, it refuses a file that changed since `open()`, backs up to `.backup-N`, appends, then reloads and compares. With `{ to }`, it writes the original bytes plus the new entries to a new file, and never overwrites one.
5. A running Pi keeps its context in memory and appends its next turn to the old leaf. Apply only to a stopped session, or restart Pi and resume the session before its next turn.

## Shell access

`node scripts/pi_context_edit.mjs dump SESSION OUT_DIR` writes `context.md` and `outline.txt`. `apply SESSION DECISIONS.json [--dry-run] [--to COPY.jsonl] [--marker JSON]` applies saved decisions. `scripts/install_pi_context.mjs` wraps `Session.install`.

Run the tests with `node --test tests/test_pi_lib.mjs tests/test_pi_context_edit.mjs tests/test_install_pi_context.mjs`.
