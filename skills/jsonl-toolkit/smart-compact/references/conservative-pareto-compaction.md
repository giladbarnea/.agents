---
description: Preserve explanatory history while removing the highest-cost duplication and support material.
last_updated: 2026-10-04
---

# Conservative Pareto compaction

Use this approach when the user wants large token savings with little loss of explanatory knowledge. Preserve content by default. Fewer changed messages do not prove less knowledge loss: one message can contain many important distinctions.

## Keep the reasoning, not every representation of it

A passage earns retention when it adds an assumption, reason, disagreement, correction, or distinct unresolved alternative. Superseded content can meet this test. The latest conclusion alone does not explain why earlier approaches failed or changed.

Keep enough of an earlier proposal for a later correction to make sense. Do not remove a rejected implementation merely because it was rejected.

## Judge passages inside each tool output

An important historical transcript is not an indivisible unit. One output can contain unique reasoning, repeated definitions, injected skills, and unrelated troubleshooting. Read it before deciding which passages to retain.

Target large, low-value spans rather than many small cuts. Session-navigation instructions, access repairs, rendering code, and deployment narration can occupy substantial space without changing the design. Conversely, a repeated-looking output can contain one new example or qualification that explains a later change.

A file-tool result may be the only surviving copy of user-authored notes or dialogue. Do not replace it with a path merely because its tool name is `Read`.

## Preserve separate attempts without repeating their inputs

Text equality does not prove that two events are duplicates. The user may deliberately present the same input to separate agents and receive different answers. Preserve those attempts and their distinct reasoning. Replace a repeated quoted input with an explicit reference to a surviving copy.

Complete versions can make their additional diff encodings redundant. Keep the versions and the reason for their differences. Check for unique deleted wording, comments, or examples before removing a diff. Verify exact duplication rather than assuming it from similar headings.

## Summarize what was believed at the time

When exact wording matters less than historical meaning, replace a selected payload or passage with a short, marked summary. Preserve its source identity and the reason it mattered. Do not make an earlier agent sound as though it already knew the later conclusion.

A useful historical summary preserves:

1. The earlier position.
2. Its reason or assumption.
3. The objection or new evidence.
4. The resulting change.

Keep uncertainty, disagreement, and unresolved alternatives explicit. A path reference alone cannot carry this meaning. Do not erase important corrections merely because a later document incorporates them.

## Measure text savings separately from encoding savings

Base64 images and opaque reasoning signatures can dominate serialized-file token counts. Removing an image payload does not save the same number of API tokens as removing its base64 text representation.

Report readable-text estimates, image-payload changes, and archive size separately. Label tokenizer estimates as estimates, not API-billed counts. Preserve opaque reasoning and signatures rather than treating their large serialized size as removable prose.

## Apply only the selected changes

Use the [parent toolkit](../../SKILL.md) for formats, exports, backups, and stable identities. Make a copy before changing a native session. Bind every decision to the exact source checksum and stable occurrence. Preserve unselected content and validate that preservation, not merely that the result parses.

**The standard pipeline does not support this conservative selection.** Its pruner removes raw structured-file outputs; its plan generator removes unselected raw tools; its applier rejects surviving raw tools. Do not run destructive preprocessing before deciding what must remain. Use a checksum-bound selective transformation when retained raw payloads or passage-level cuts are required.

The native applier supports Pi, not Claude. A selective native Claude transformation must preserve message UUIDs, parent links, exact tool-call/result identities, and reasoning signatures. Keep changes to selected payloads and their duplicate caches explicit. A readable export is not a resumable native session.

For a new Claude session, generate a fresh UUID and use it in the filename and matching top-level session identity fields. Preserve ancestor session identities, message identities, and historical paths. Do not globally replace the old UUID inside prose or tool payloads. Distinguish structural validation, session recognition, and successful resume when reporting validation.

Respect the user's model and cost preferences. Bounded historical review does not automatically justify the most expensive delegate.

## Report the boundary, not only the reduction

Explain what was removed, what was borderline and retained, and why the remaining history still explains the latest state. Stop when further savings would remove unique reasoning rather than another representation of it.
