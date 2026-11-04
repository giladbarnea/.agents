---
name: smart-compact
parent: jsonl-toolkit
description: Tree-shake an AI session transcript while preserving its semantic story
last_updated: 2026-11-04
---

Read [`../SKILL.md`](../SKILL.md) first. The parent owns file formats, large-file inspection, stable identities, generic transcript analysis, and native Pi structure.

> **This skill's scripts and pipelines should eventually be eliminated in favor of [`lib/pi.mjs`](../references/pi-lib.md).** Never extend them. Remove them or cut their scope whenever you safely can, and build missing capability into the library. The judgment guidance in this skill stays: what to keep, how to summarize, and the thinking rules.

Smart-compaction removes redundant information while keeping contentful messages intact.

For conservative or Pareto compaction, read [Conservative Pareto compaction](references/conservative-pareto-compaction.md) before applying the rules below. Its remove / summarize / keep bar takes precedence over the rules below, including thinking selection, broad file-payload replacement, tool removal and deterministic preprocessing.

## Keep thinking with the work it explains

During compaction, treat thinking according to its associated messages and tools:

1. **Unchanged work:** preserve its reasoning verbatim.
2. **Summarized work:** summarize plaintext reasoning proportionately. Remove associated encrypted reasoning.
3. **Removed work:** remove its associated reasoning too.

Signed thinking can become invalid if its text or surrounding context changes. If replay could fail, promote retained plaintext to ordinary assistant text inside `<thinking>…</thinking>` or after `Thinking:`. Keep it verbatim or summarize it under the rules above. Do not attach the original signature to this text representation. It is editable historical reasoning, not authenticated thinking.

Never invent plaintext for encrypted reasoning. Preserve original blocks in source history or a verified backup.

## Split analysis from background editing

The main agent owns semantic decisions. One teammate owns edits to the copied JSONL. Do not run concurrent writers.

1. Load the `ai-to-delegated` and `pseudocode` skills. Confirm the teammate's model with the user.
2. Create one idle, context-forked teammate with `thinking: low`.
3. Analyze the next part yourself, using scripts and reading. Clearly categorize passages as retain, remove, summarize or duplicate. Identify surviving duplicate references and protect unique reasoning.
4. Send the editing batch at the pseudocode skill's detail level: intent, selected stable identities, expected result and preservation boundaries. Leave implementation choices to the teammate.
5. Let the teammate edit the copy in the background while you analyze the next part. Queue further batches to the same teammate; it applies them sequentially.
6. Repeat until analysis and all editing batches are complete. The teammate reports each batch's changes, savings and validation against its source checksum.
7. Validate the final session's structure, tool pairing, retained references and unselected payloads before installing it. Apply the [thinking rules](#keep-thinking-with-the-work-it-explains), using surrounding work to select blocks.

The teammate executes your classifications; it does not independently broaden removal or summarization. For conservative work, use the selective workflow in the reference above, not destructive preprocessing.

## Drop the struggle and keep the resolution

Identify a sequence of failed attempts that serves one purpose. Remove the failed loop and preserve the successful resolution.

Drop external technical failures such as user interrupts, connection retries, and transport problems.

Do not remove failed experiments that changed the technical conclusion. Those failures remain part of the story.

## Remove murmurs and technical receipts

Drop isolated narration such as:

- `Good, that worked.`
- `Now I will check the file.`
- `The file was updated successfully.`
- A tool completed with no output.
- Todo state updates.

These messages can have either the user or assistant role.

Drop local user commands that only adjust the harness. Keep commands that supply semantic instructions or trigger relevant context gathering.

## Replace structured file operations with references

Keep only the operation, path, and stable tool identity for file CRUD tools.

```json
{"type":"tool-input","name":"Read","path":"/path/to/file.py","id":"read-id"}
```

becomes:

```xml
<Read path="/path/to/file.py" id="read-id"/>
```

This rule applies to `Read`, `read_many_files`, `Write`, `Edit`, `Patch`, and `Delete`.

Expand a multi-file read into one reference per path. Preserve the source block's native provenance when available.

Pure mechanical Bash setup can also reduce to a path-only reference. A Bash command that discovers decisive information or validates completion follows the skeleton rule instead.

## Replace pivotal non-file tools with semantic skeletons

Keep the decision rather than the raw payload.

```xml
<tool-skeleton name="Bash" command="pytest" purpose="Validate the fix" outcome="148 tests passed" meaning="Proved the change before release"/>
```

The required attributes are `name`, `command`, `purpose`, and `outcome`. Add `meaning` when the result explains a consequential decision.

Describe the executed command faithfully. Keep exact syntax only when that syntax matters to the story.

The skeleton replaces both the raw call and its output. Do not duplicate the same evidence in nearby narration.

File references take precedence over skeletons. Omit every non-pivotal tool event.

## Keep the final observation and definitive validation

Group exploratory calls by semantic purpose. Keep only the call that successfully obtains the information used later.

Drop reads and writes of temporary scratchpads created only to help the agent reach an answer.

For builds, tests, and other validation, keep the final successful proof. Remove the debugging loop that preceded it.

## End with the affected-file set

The compacted transcript ends with:

```xml
<affected-files>
- @path/to/file1.ext
- @path/to/file2.ext
</affected-files>
```

Collect the unique paths from surviving structured file references and registered artifact-producing tools.

Use the parent file reporter when presenting the set:

```bash
../scripts/filestats.sh <path> [path ...]
```

## Read the session through the library

Read a Pi session with [`lib/pi.mjs`](../references/pi-lib.md): `context.outline()` gives one line per entry and `context.render({ clip })` gives the text. It reads the session file itself, so it cannot lose entries a `ch` export leaves out. Collect decisions in a `Draft`, as [the native workflow](#choose-the-native-workflow-explicitly) describes.

## Legacy: finish an existing transcript plan

The plan commands below are legacy tools for finishing an existing `ch`-transcript plan. Use its saved source; do not start new work with this pipeline. The export must have been made with `-t` rather than `-t:s`.

`-t:s` splices long tool values down to about 500 characters, keeping both ends around a bare `...` line. It cuts arguments as well as results, so a skeleton `command` and a skeleton `outcome` can both be silently wrong. `--annotate` counts spliced values on its stderr summary.

Use `original_index` rather than a shifting array position.

The native plan applier requires current Pi provenance fields. If the saved source lacks them, use `lib/pi.mjs` on the native session instead.

Always back up a transcript before changing it in place. Do not rerun index-based decisions against already transformed output.

## Choose the native workflow explicitly

When the result must remain a resumable Pi session, read [`references/native-pi-session.md`](references/native-pi-session.md).

The original session is protected. An explicitly named target copy can be changed after its identity, snapshot, and backup validate.

To compact a Pi session in place, including one compacted before, [edit its live context](references/native-pi-session.md#edit-the-live-context-in-place) with [`lib/pi.mjs`](../references/pi-lib.md). Read the context, collect your decisions in a draft, preview them, then apply. This path needs no `ch` export, keeps every stored byte, and checks tool pairing before it writes. The semantic-plan applier remains for a plan made from a `ch` transcript; it changes a named target copy.

If the context is already prepared, use the [context installer](references/native-pi-session.md#install-a-prepared-context-window):

```bash
node ../scripts/install_pi_context.mjs session.jsonl prepared-context.json output.jsonl
```

It preserves the original archive and installs an ordered JSON message array as the active context in a new output file.

## Offer to resume the compacted session

After validation, ask whether the user wants to resume the compacted session in Herdr, in a new sibling pane or an existing pane they choose. If approved, load the `herdr` skill, create or inspect the agreed pane, then run `cd <session.header.cwd>` and `pi --session <session-id>`. Wait until Pi is ready, then send: “Welcome back. Your context was compacted for <current effort — under 10 words>. Read <handoff doc path if one exists>, then continue <pending work — under 10 words>.” Verify that Pi accepted the message. 

Note this can work with `claude -r <session-id>` and `codex resume <session-id>` as well.

## Use generic and compaction-specific diagnostics separately

Start with the parent structural report:

```bash
uv run --script ../scripts/analyze_transcript_json.py transcription.json
```

Add smart-compaction candidate hints with:

```bash
uv run --script scripts/analyze_compaction_candidates.py transcription.json
```

Candidate hints include murmurs, success receipts, local-command caveats, and scratchpad paths. They are not semantic decisions.

Read the transcript in full regardless of either report.

## Render one chronological review view

```bash
uv run --script ../scripts/render_transcript_review.py source.json > review.md
```

The parent renderer preserves message order, pairs tools by exact ID, labels boundaries, and elides only byte-identical skill bodies.

Prefer the annotated view when repetitive tool traffic dominates the transcript:

```bash
uv run --script ../scripts/render_transcript_review.py --annotate source.json > annotated.txt
```

Every tool call and result line carries the `original_index` and the tool identity that a skeleton anchors on, so reading it is the annotation work. Message text prints verbatim, so a long message spans lines that carry no index. Results are shown whole up to a generous budget, because a skeleton `outcome` is usually written from a result.

Check the stderr summary before you trust the view. Any entry on `unrecognized block and wrapper types` is a block type the mode has not vetted, which means the export format moved. Its size is still reported, but nothing else about it is read. A `NOT UNIQUE` verdict on the `tool ids` line means a skeleton anchor may be ambiguous and `no-result-in-file` cannot be believed.

In an edited transcript, `no-result-in-file` can reflect an intentionally removed result rather than an interrupted call. Review and annotate the exact saved source: `compile_annotations.py` rejects an index that no longer exists.

## Annotate judgments instead of mechanical plan fields

Create `annotations.yaml` containing only semantic decisions:

```yaml
drop:
  indices: [90, 262]
  ranges:
    - [432, 437]
drop_text_blocks:
  - {original_index: 12, contains: "Now I will wrap up"}
drop_file_references:
  - {original_index: 6, operation: Read, path: /path/to/stale.py}
skeletons:
  - original_index: 236
    tool_id: "R3Ul"
    command: "pytest"
    purpose: "Validate the change"
    outcome: "148 tests passed"
    meaning: "Proved the final implementation"
scratchpad_paths: [/tmp/render_helper.py]
opaque_artifacts: [/path/created/by/opaque/shell.csv]
```

Ranges are inclusive over stable indices that exist in the saved source transcript. Every direct index must exist.

Compile the annotations against the exact source:

```bash
uv run --script scripts/compile_annotations.py \
  source.json annotations.yaml > decisions.json
```

The compiler rejects unknown keys and malformed selections. It binds the result to the saved source checksum.

Do not hand-edit the generated decisions file.

## Generate and apply the version-2 plan

```bash
uv run --script scripts/generate_compaction_plan.py \
  source.json decisions.json > compaction-plan.json

uv run --script scripts/apply_compaction_plan.py \
  source.json compaction-plan.json > compacted.json
```

The generator:

- Infers removal of unselected raw tool blocks.
- Escapes skeleton attributes.
- Resolves exact tool occurrences.
- Collects affected-file provenance.
- Audits every inferred and explicit change.
- Verifies the plan through the apply stage before emitting it.

Non-tool structured blocks pass through unchanged, including thinking and subagent task blocks. The standard appliers do not implement thinking promotion or removal. Use a checksum-bound selective transformation for those [thinking rules](#keep-thinking-with-the-work-it-explains).

The apply stage rejects stale checksums, missing indices, changed tool IDs, surviving raw tools, changed passthrough blocks, and duplicate footers.

Version-1 plans are unsupported. Regenerate them.

## Transfer the same plan to a named native Pi copy

Do not pass `compacted.json` to the native applier.

Pass the saved source, plan, and native target:

```bash
uv run --script ../scripts/compact_existing_pi_session_inline.py \
  source.json compaction-plan.json session-copy.jsonl
```

The native applier currently remains at the parent script level while its reusable Pi-session logic is refactored.

## Render the final context

Preview a library edit with `draft.context().render()` before applying it. From a shell, `node ../scripts/pi_context_edit.mjs dump SESSION out/` writes `context.md`.

For the legacy pipeline's `compacted.json`:

```bash
ch parse compacted.json > compacted.md
```

Do not hand-render the final transcript or use an ad hoc converter.
