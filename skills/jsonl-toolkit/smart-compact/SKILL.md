---
name: smart-compact
parent: jsonl-toolkit
description: Tree-shake an AI session transcript while preserving its semantic story
last_updated: 2026-08-05
---

Read [`../SKILL.md`](../SKILL.md) first. The parent owns file formats, large-file inspection, stable identities, generic transcript analysis, and native Pi structure.

Smart-compaction removes redundant information while keeping contentful messages intact.

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

## Build from a current structured export

Follow the parent `ch` export contract. Use `original_index` rather than a shifting array position.

The native plan applier requires current Pi provenance fields. Re-export and re-prune an older transcript that lacks them.

Always back up a transcript before changing it in place. Do not rerun index-based decisions against already transformed output.

## Choose the native workflow explicitly

When the result must remain a resumable Pi session, read [`references/native-pi-session.md`](references/native-pi-session.md).

The original session is protected. An explicitly named target copy can be changed after its identity, snapshot, and backup validate.

The default native compactor creates a new session. The semantic-plan applier changes a named target copy.

## Run deterministic preprocessing before semantic review

```bash
uv run --script scripts/prune_transcript.py transcription.json > pruned.json
```

The pruner:

- Removes todos.
- Removes raw outputs from structured file tools.
- Expands multi-file reads.
- Replaces file inputs without reordering mixed content.
- Keeps the first byte-identical skill body.
- Preserves every invocation-specific user instruction.

An interrupted file-tool call without a path fails loudly. Inspect it before authorizing its removal:

```bash
uv run --script scripts/prune_transcript.py \
  transcription.json \
  --drop-orphan-tool-id <tool-id> \
  > pruned.json
```

The exception accepts only one uniquely identified, payload-free, unpaired file-tool call.

## Select a tail through a stable boundary

For an exported transcript, exclude the boundary message itself:

```bash
uv run --script scripts/prune_transcript.py \
  transcription.json \
  --from-index 194 \
  > pruned.json
```

For a native Pi target, let the latest completed watermark select the tail:

```bash
uv run --script scripts/prune_transcript.py \
  transcription.json \
  --native-session session-copy.jsonl \
  > pruned.json
```

Use `--from-entry-id <native-id>` with `--native-session` for an explicit native boundary.

If the selected tail is empty, stop. Do not create a plan, backup, or watermark.

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
uv run --script ../scripts/render_transcript_review.py pruned.json > review.md
```

The parent renderer preserves message order, pairs tools by exact ID, labels boundaries, and elides only byte-identical skill bodies.

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
    tool_id: "toolu_full-native-id"
    command: "pytest"
    purpose: "Validate the change"
    outcome: "148 tests passed"
    meaning: "Proved the final implementation"
scratchpad_paths: [/tmp/render_helper.py]
opaque_artifacts: [/path/created/by/opaque/shell.csv]
```

Ranges are inclusive over stable indices that exist in the pruned transcript. Every direct index must exist.

Compile the annotations against the exact source:

```bash
uv run --script scripts/compile_annotations.py \
  pruned.json annotations.yaml > decisions.json
```

The compiler rejects unknown keys and malformed selections. It binds the result to the pruned source checksum.

Do not hand-edit the generated decisions file.

## Generate and apply the version-2 plan

```bash
uv run --script scripts/generate_compaction_plan.py \
  pruned.json decisions.json > compaction-plan.json

uv run --script scripts/apply_compaction_plan.py \
  pruned.json compaction-plan.json > compacted.json
```

The generator:

- Infers removal of unselected raw tool blocks.
- Escapes skeleton attributes.
- Resolves exact tool occurrences.
- Collects affected-file provenance.
- Audits every inferred and explicit change.
- Verifies the plan through the apply stage before emitting it.

Non-tool structured blocks pass through unchanged. This includes thinking and subagent task blocks.

The apply stage rejects stale checksums, missing indices, changed tool IDs, surviving raw tools, changed passthrough blocks, and duplicate footers.

Version-1 plans are unsupported. Regenerate them.

## Transfer the same plan to a named native Pi copy

Do not pass `compacted.json` to the native applier.

Pass the pruned source, plan, and native target:

```bash
uv run --script ../scripts/transfer_to_pi_session.py \
  pruned.json compaction-plan.json session-copy.jsonl
```

The native applier currently remains at the parent script level while its reusable Pi-session logic is refactored.

## Regenerate Markdown from final JSON

```bash
ch parse compacted.json > compacted.md
```

Do not hand-render the final transcript or use an ad hoc converter.
