---
description: Remove unquestionable noise and repetition; reduce noise in mixed passages without losing their signal.
last_updated: 2026-11-04
---

# Conservative Pareto compaction

Apply the same bar to messages, tool payloads and readable reasoning:

1. **Remove** only what is unquestionably noise or repetition. For repeated content, keep one full version and link to it as described below.
2. **Summarize or tree-shake** only passages with an unquestionably very poor signal-to-noise ratio. Reduce the noise while keeping the signal intact: do not dilute unique assumptions, qualifications, disagreements or corrections.
3. **Keep as-is** everything else, including borderline cases. Size alone is not a reason to cut, and there is no token-reduction target.

If the user names a domain or chapter to optimize for, weigh signal by its relevance to that scope, including its dependencies and the history needed to understand it. Do not infer a narrower scope from the latest turn alone. Fewer changed messages do not prove less knowledge loss: one message can contain many important distinctions.

## Keep the reasoning, not every representation of it

A passage earns retention when it adds an assumption, reason, disagreement, correction, or distinct unresolved alternative. Superseded content can meet this test. The latest conclusion alone does not explain why earlier approaches failed or changed.

Keep enough of an earlier proposal for a later correction to make sense. Do not remove a rejected implementation merely because it was rejected.

## Compare passages across representations

Use the passage, not the record or tool type, as the unit of comparison. User messages, Write inputs, Read results, Bash outputs, Edits and later rereads can repeat the same meaning. Deduplicate content across these forms, regardless of who supplied it or how it entered the context. Repetition can span overlapping line ranges across several events.

An important document is not an indivisible unit. It can mix unique reasoning, repeated definitions, generic instructions and unrelated troubleshooting. Read it before deciding which passages earn retention. Do not retain the whole document merely because one passage matters.

Same meaning does not require identical bytes. Check scope, qualifications, uncertainty, authority and time before calling two passages repeats. Normalize only known display differences for exact comparisons, such as Read line numbers. Similar headings or fuzzy matches identify candidates, not proof.

A repeated-looking output can still add an example or qualification that explains a later change. A file-tool result may be the only surviving copy of user-authored notes or dialogue. Do not replace it with a path merely because its tool name is `Read`.

## Keep each event and link its repeated content

Repeated content does not make two events identical. The same input can trigger separate attempts with different answers. Keep those attempts and their distinct reasoning.

Replace repeated passages with short semantic placeholders, not silent deletion. Name what stayed the same. Identify the surviving full version through a stable message or tool identity and a section or line range.

> Unchanged §2: same as the earlier Write of `docs/design.md` (call `abc`). The full text remains there.

If only part changed, link the unchanged part and keep the differences. Complete versions can also make their diff encodings redundant. Check for unique deleted wording, comments or examples before replacing a diff.

Every placeholder must resolve to a full version that survives the final selection. Do not build chains of placeholders with no retained content. Keep the event's historical state explicit when referring to a later version.

## Summarize what was believed at the time

Generic instruction catalogues, navigation maps, operational manuals and obsolete handoffs can mix signal with noise. Their type or age does not establish a poor ratio: inspect the passages against the bar above.

For a passage that meets that bar, preserve signal-bearing wording and summarize or tree-shake the surrounding noise. Mark the transformation; do not call unique content a duplicate. Preserve its source identity and the reason it mattered. Do not make an earlier agent sound as though it already knew the later conclusion.

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

Readable reasoning follows the same remove / summarize / keep bar as messages and tools. It is neither exempt from cuts nor automatically cut because an associated tool output was summarized. Read its own content and its surrounding work.

Encrypted reasoning cannot be inspected or summarized. A visible reasoning summary does not expose the whole encrypted block:

1. First select surrounding work for removal or summarization under the same bar above.
2. Attribute the encrypted block to that work using preceding events and subsequent responses.
3. Remove the block only when it is clearly attributable entirely to the selected work and the retained account preserves that work's signal. Keep it when attribution is uncertain or its context includes retained work.

Do not guess what ciphertext contains. Age, size, a broad chapter label or a token target alone never justifies removal.

Remove a selected block and its associated signature together. Never partially rewrite a native signed or encrypted payload. When plaintext needs summarization or replay could fail, use the parent's [ordinary-text promotion](../SKILL.md#keep-thinking-with-the-work-it-explains). Preserve unselected native blocks and signatures unchanged.

Audit each reasoning change by stable identity and the evidence that it meets the same bar, including surrounding-work attribution for encrypted blocks.

## Measure text savings separately from encoding savings

Base64 images and opaque reasoning signatures can dominate serialized-file token counts. Removing an image payload does not save the same number of API tokens as removing its base64 text representation.

Report readable-text estimates, image-payload changes, thinking-block removals and archive size separately. Measure net savings after including placeholders and summaries. Label tokenizer estimates as estimates, not API-billed counts. Large opaque payloads are not removable prose; apply the thinking-block selection rule above.

## Apply only the selected changes

Use the [parent toolkit](../../SKILL.md) for formats, exports, backups, and stable identities. Make a copy before changing a native session. Bind every decision to the exact source checksum and stable occurrence. Preserve unselected content and validate that preservation, not merely that the result parses.

**The standard pipeline does not support this conservative selection.** Its pruner removes raw structured-file outputs; its plan generator removes unselected raw tools; its applier rejects surviving raw tools. Do not run destructive preprocessing before deciding what must remain. Use a checksum-bound selective transformation when retained raw payloads or passage-level cuts are required.

The native applier supports Pi, not Claude. A selective native Claude transformation must preserve message UUIDs, parent links, exact tool-call/result identities, and unselected thinking blocks and signatures. Keep changes to selected payloads and their duplicate caches explicit. Inspect caches separately: model-visible results can contain harness text that cached payloads omit. Preserve unselected cache metadata. A readable export is not a resumable native session.

Validate every linked passage against its retained version. Confirm that reference targets remain unchanged and available after all cuts. Verify semantic repeats by accounting for their differences, not by byte equality alone.

For a new Claude session, generate a fresh UUID and use it in the filename and matching top-level session identity fields.

Update the session title's `[f:....]` marker, or add it if absent. `f` means fork. The four characters are the second hyphen-separated part of the original session UUID being compacted. For example, `7e47a8f3-4e1d-4243-b049-2170501d6920` gives `[f:4e1d]`.

Ask the user before placing the compacted copy alongside the original in the appropriate Claude project directory. Never overwrite the original.

Preserve ancestor session identities, message identities, and historical paths. Do not globally replace the old UUID inside prose or tool payloads. Distinguish structural validation, session recognition, and successful resume when reporting validation.

Respect the user's model and cost preferences. Bounded historical review does not automatically justify the most expensive delegate. Use quick lookups with moderate thinking for simple content-selection questions over broad scopes. Ask for candidate passages, retained references and unique differences, not another full transcript.

## Report the boundary, not only the reduction

Explain what was removed, what was borderline and retained, and why the remaining history still explains the latest state. Stop when no further cuts meet the bar above.
