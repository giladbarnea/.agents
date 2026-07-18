# Smart-Compact Plan Authoring Improvement

## Planning status

This file records planning pass 1: the smallest production-ready path from the current workflow to semantic-only plan authoring. The user has approved the direction and asked that correctness gaps be resolved without turning the work into a larger subsystem.

No separate ledger, interactive editor, or new workflow framework is needed. One small authoring command and the existing apply stage are sufficient.

## The author should express decisions, not reconstruct machinery

The authoring input should contain only decisions that cannot be derived safely from the pruned transcript:

1. Contentful text messages to remove.
2. Pivotal tool activity to preserve as semantic skeletons, with `command`, `purpose`, `outcome`, optional `meaning`, and an optional tool-name override.
3. File-operation messages that belong to disposable scratchpad work.
4. Rare artifact paths created through opaque shell behavior that no structured tool can report.

The ordinary case should require only the first two. The author must never enumerate routine raw-tool messages, copy tool identifiers, write XML inside JSON, calculate checksums, or reconstruct the affected-file set.

## The mechanical behavior must be unambiguous

### Raw tool blocks are removed by default

Every remaining structured tool-input and tool-output block is provisional noise unless a skeleton declaration preserves its meaning. The generator derives the complete raw-tool drop set and subtracts skeleton anchors automatically.

Pure raw-tool messages become removals. Text-only messages remain untouched unless explicitly removed.

### Mixed-content messages keep their prose

A mixed-content message must not be dropped wholesale and cannot survive unchanged with raw blocks. The generator therefore:

1. Preserves existing string blocks in their original order.
2. Removes routine structured tool blocks.
3. Inserts a declared skeleton where the selected pivotal tool block appeared.
4. Drops the message only if no content remains.

Any structured block that is not a recognized tool input or output fails plan generation; preprocessed file references are already strings. Mixed content is handled mechanically rather than pushed back to the author.

### Skeleton generation uses one stable anchor

A skeleton declaration names one `original_index`, which is both its stable anchor and final placement. The generator derives the tool name and every tool identifier in that source message, escapes the XML safely, and emits the complete replacement entry. A name override is sufficient when the skeleton summarizes a wider bout because all other raw-tool messages are already inferred removals; any text-only noise in that bout remains an explicit text decision.

A skeleton anchor must resolve to a message containing a tool input. Missing and output-only anchors fail loudly. If one message contains different tool names, the declaration must provide the name override; all identifiers in the anchored message remain guarded. Paired outputs remain inferred removals.

## Affected-file provenance is automatic in the ordinary case

Provenance is collected from the pruned transcript before semantic removal. The generator gathers and deduplicates paths from:

1. The existing preprocessed Read, Write, Edit, Patch, and Delete references.
2. A small explicit extractor table for known artifact-producing tools such as Lumen.
3. The narrow opaque-artifact escape hatch in the semantic input.

Scratchpad operation indices remove those provenance events and transcript references before paths are deduplicated. A path still appears when any non-scratchpad operation touched it. The generator mechanically populates the existing plan field consumed by the apply stage; the author does not write `affected_files_extra` directly.

Do not attempt to infer arbitrary shell side effects. That would become a separate tracing project and still be unreliable. Opaque shell-created artifacts use the explicit exception, while supported structured tools remain fully automatic. A tool registered as artifact-producing but lacking a working extractor is an error, never a silent omission.

## Generation always presents a concise audit

The authoring command emits the complete checksum-bound plan and always prints a compact audit containing:

- Inferred raw-tool removals, grouped by tool.
- Mixed-content messages normalized mechanically.
- Skeleton anchors.
- Explicit text removals.
- Scratchpad exclusions.
- Affected paths and their provenance category.
- Final kept, removed, and replaced message counts.

Unresolved structured blocks, invalid anchors, conflicting decisions, or artifact-extractor failures stop generation. No interactive confirmation step or separate review UI is needed; the generated plan stays inspectable and the existing apply stage retains its validation.

## `ch` canonicalization is part of the data contract

`ch` preserves the rendered transcript but canonicalizes adjacent text blocks and timestamp precision. Reference and footer handling must therefore recognize generated XML-like fragments inside a larger text block rather than assuming one element per content entry.

Use small exact scanners for the known generated tags; do not build a general XML-in-Markdown parser. Tests compare stable rerendered Markdown and normalized semantic JSON, not byte-identical JSON.

## High-level path to production

### 1. Add one semantic plan-authoring command

Accept the pruned transcript plus the minimal semantic-decision input. Produce the complete plan already accepted by `apply_compaction_plan.py`, including source checksum, inferred drops, generated replacements, and mechanically populated affected-file provenance.

Done means the existing application stage needs no hand-authored mechanical fields.

### 2. Implement deterministic block handling and skeleton serialization

Infer pure raw-tool removals, preserve prose in mixed messages, create skeleton replacements from stable anchors, and reject unsupported or conflicting input.

Done means the real transcript's roughly two-hundred routine tool indices disappear without manual enumeration, while its mixed prose-and-tool message retains the prose.

### 3. Carry affected-file provenance through application

Collect standard file references and known structured artifacts before removals, exclude declared scratchpads, and use the explicit opaque-artifact exception only where structured provenance is impossible.

Done means the real transcript produces its complete footer without manual recovery of ordinary paths, including the Lumen artifact through its extractor.

### 4. Add the audit and retain the guarded apply boundary

Print the mandatory concise audit during generation. Keep plan generation and plan application as two commands so the artifact remains inspectable and reusable. Preserve the apply stage's loud failures for stale checksums, invalid indices, mismatched identifiers, unresolved raw blocks, and duplicate footers.

Done means forgetting a mechanical step is impossible and inferred decisions are visible before application.

### 5. Prove the workflow on focused fixtures and the real transcript

Cover:

- Paired tool calls and outputs.
- Pure and mixed-content tool messages.
- Multiple tool identifiers and invalid skeleton anchors.
- Multi-file reads before and after a `ch` round trip.
- Existing footers embedded in a canonicalized text block.
- Duplicate paths and scratchpad exclusion.
- A known artifact-producing tool and the opaque-artifact exception.
- Deterministic plan generation, stale-source rejection, and Markdown fixed-point round trips.

Then replay the session that exposed the roughly two-hundred-index drop list. The generated compacted result must match the accepted semantic result without manual raw-tool enumeration, identifier copying, XML escaping, or ordinary affected-file reconstruction.

### 6. Update the actual source-of-truth documentation

`~/.pi/agent/skills/smart-compact` is a symlink to `~/.agents/skills/smart-compact`; these are not separate copies. Treat `~/.agents/skills/smart-compact/SKILL.md.j2` as the canonical template, regenerate `SKILL.md`, and document the semantic authoring command beside the existing `ch parse` workflow.

Done means regenerating the skill cannot erase either the round-trip or plan-authoring instructions.

## Minimal production boundary

The deliverable ends when one semantic-decision input can generate a safe, inspectable plan with inferred raw-tool removals, prose-preserving mixed-content handling, generated skeletons, and an automatic ordinary-case affected-files footer; the existing apply command can apply it; `ch` can round-trip the result; and the real transcript proves the workflow.

Out of scope: graphical review, interactive editing, heuristic selection of pivotal tools, automatic skeleton prose, generalized shell tracing, and a new workflow engine.

