---
description: Preserve explanatory history while removing the highest-cost duplication and support material.
last_updated: 2026-10-07
---

# Conservative Pareto compaction

Use this approach when the user wants large token savings with little loss of explanatory knowledge. Preserve content by default. Fewer changed messages do not prove less knowledge loss: one message can contain many important distinctions.

## Keep the reasoning, not every representation of it

A passage earns retention when it adds an assumption, reason, disagreement, correction, or distinct unresolved alternative. Superseded content can meet this test. The latest conclusion alone does not explain why earlier approaches failed or changed.

Keep enough of an earlier proposal for a later correction to make sense. Do not remove a rejected implementation merely because it was rejected.

## Compare passages across representations

Use the passage, not the record or tool type, as the unit of comparison. User messages, Write inputs, Read results, Bash outputs, Edits and later rereads can repeat the same meaning. Deduplicate content across these forms, regardless of who supplied it or how it entered the context. Repetition can span overlapping line ranges across several events.

An important document is not an indivisible unit. It can mix unique reasoning, repeated definitions, generic instructions and unrelated troubleshooting. Read it before deciding which passages earn retention. Do not retain the whole document merely because one passage matters.

Same meaning does not require identical bytes. Check scope, qualifications, uncertainty, authority and time before calling two passages repeats. Normalize only known display differences for exact comparisons, such as Read line numbers. Similar headings or fuzzy matches identify candidates, not proof.

Target large, low-value spans rather than many small cuts. A repeated-looking output can still add an example or qualification that explains a later change. A file-tool result may be the only surviving copy of user-authored notes or dialogue. Do not replace it with a path merely because its tool name is `Read`.

## Keep each event and link its repeated content

Repeated content does not make two events identical. The same input can trigger separate attempts with different answers. Keep those attempts and their distinct reasoning.

Replace repeated passages with short semantic placeholders, not silent deletion. Name what stayed the same. Identify the surviving full version through a stable message or tool identity and a section or line range.

> Unchanged §2: same as the earlier Write of `docs/design.md` (call `abc`). The full text remains there.

If only part changed, link the unchanged part and keep the differences. Complete versions can also make their diff encodings redundant. Check for unique deleted wording, comments or examples before replacing a diff.

Every placeholder must resolve to a full version that survives the final selection. Do not build chains of placeholders with no retained content. Keep the event's historical state explicit when referring to a later version.

## Summarize what was believed at the time

A large output can be unique and still hold little useful detail for the effort or its continuation. Summarize it without claiming it was a duplicate. Generic instruction catalogues, navigation maps, operational manuals and obsolete handoffs are candidates, not automatic removals.

When exact wording matters less than historical meaning, replace a selected payload or passage with a short, marked summary. Preserve its source identity and the reason it mattered. Do not make an earlier agent sound as though it already knew the later conclusion.

A useful historical summary preserves:

1. The earlier position.
2. Its reason or assumption.
3. The objection or new evidence.
4. The resulting change.

Keep uncertainty, disagreement, and unresolved alternatives explicit. A path reference alone cannot carry this meaning. Do not erase important corrections merely because a later document incorporates them.

## Refresh historical file snapshots only with approval

Check whether files in retained Reads, Writes, Edits and shell file operations changed or moved after those events. Compare their recorded contents and paths with the current files.

Ask the user before replacing historical snapshots with current contents or paths. An explicit request to refresh them already grants approval. Without approval, preserve historical snapshots.

After approval:

1. Update retained file-operation paths and payloads to the current files. Keep one complete current version and link repeated passages to it.
2. Mark refreshed content with its snapshot date and original source identity. Do not imply the earlier operation observed today's state.
3. Keep historical objections, alternatives and reasons that explain the current design. Summarize superseded details rather than presenting them as current truth.
4. Update associated payload caches consistently. Preserve message identities, tool pairing and retained reasoning signatures.

If a file is absent, do not invent a current version. Keep a marked historical summary and record any unresolved replacement path.

## Select thinking blocks through their surrounding work

Preserve thinking blocks by default. With user approval, remove only whole blocks whose surrounding work clearly supports that decision.

1. First decide independently which readable notions or content deserve removal or dilution.
2. Use preceding events and subsequent responses to attribute a thinking block to that selected work. For example: a stale file read, opaque thinking, then a response using those stale assumptions.
3. Remove the whole block only when that attribution is clear. Keep it when its context is mixed, includes retained work, or leaves its subject uncertain.

Do not guess what ciphertext contains. Age, size, a broad chapter label or a token target alone never justifies removal.

Remove a selected block and its associated signature together. Never truncate, rewrite or partially summarize a thinking payload. Preserve retained blocks and signatures unchanged.

Audit each removal by stable identity, the surrounding evidence and the independent removal or dilution decision it follows.

## Measure text savings separately from encoding savings

Base64 images and opaque reasoning signatures can dominate serialized-file token counts. Removing an image payload does not save the same number of API tokens as removing its base64 text representation.

Report readable-text estimates, image-payload changes, thinking-block removals and archive size separately. Measure net savings after including placeholders and summaries. Label tokenizer estimates as estimates, not API-billed counts. Large opaque payloads are not removable prose; apply the thinking-block selection rule above.

## Apply only the selected changes

Use the [parent toolkit](../../SKILL.md) for formats, exports, backups, and stable identities. Make a copy before changing a native session. Bind every decision to the exact source checksum and stable occurrence. Preserve unselected content and validate that preservation, not merely that the result parses.

**The standard pipeline does not support this conservative selection.** Its pruner removes raw structured-file outputs; its plan generator removes unselected raw tools; its applier rejects surviving raw tools. Do not run destructive preprocessing before deciding what must remain. Use a checksum-bound selective transformation when retained raw payloads or passage-level cuts are required.

The native applier supports Pi, not Claude. A selective native Claude transformation must preserve message UUIDs, parent links, exact tool-call/result identities, and retained thinking blocks and signatures. Keep changes to selected payloads and their duplicate caches explicit. Inspect caches separately: model-visible results can contain harness text that cached payloads omit. Preserve unselected cache metadata. A readable export is not a resumable native session.

Validate every linked passage against its retained version. Confirm that reference targets remain unchanged and available after all cuts. Verify semantic repeats by accounting for their differences, not by byte equality alone.

For a new Claude session, generate a fresh UUID and use it in the filename and matching top-level session identity fields.

Update the session title's `[f:....]` marker, or add it if absent. `f` means fork. The four characters are the second hyphen-separated part of the original session UUID being compacted. For example, `7e47a8f3-4e1d-4243-b049-2170501d6920` gives `[f:4e1d]`.

Ask the user before placing the compacted copy alongside the original in the appropriate Claude project directory. Never overwrite the original.

Preserve ancestor session identities, message identities, and historical paths. Do not globally replace the old UUID inside prose or tool payloads. Distinguish structural validation, session recognition, and successful resume when reporting validation.

Respect the user's model and cost preferences. Bounded historical review does not automatically justify the most expensive delegate. Use quick lookups with moderate thinking for simple content-selection questions over broad scopes. Ask for candidate passages, retained references and unique differences, not another full transcript.

## Report the boundary, not only the reduction

Explain what was removed, what was borderline and retained, and why the remaining history still explains the latest state. Stop when further savings would remove unique reasoning rather than another representation of it.
