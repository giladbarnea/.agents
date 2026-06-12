# Tech debt: post-merge cohesion review

Date: 2026-06-12 · Scope: the skill as one unit, after merging the annotation-editing effort
(`docs/2026-06-12-annotation-note-editing.md`) with the mobile-support effort (commit `5b61841`).

Verdict: about 85% one organism, with a handful of identifiable seams — none structural, but a
sharp reviewer would spot two or three in the first minute.

## Where it genuinely reads as one effort

The two features share a single data philosophy — every mutation (create, edit, delete, restore)
is write → read-back-from-disk → only then local state, through the same helpers; the extracted
`submitActiveAnnotationEditor` and the note flows are structurally parallel functions a reader
would assume were written together. The chrome shares one vocabulary: accent-tinted 999px pills
(marker, touch action bar, crossref return pill, note actions) all look like siblings. Note
editing also lands on the right side of the mobile architecture by construction — plain buttons
and contenteditable are input-agnostic, the touch layer explicitly ignores everything inside a
preview, so notes needed zero device-branching, exactly the contract AGENTS.md prescribes.
Keyboard grammar is parallel: Enter commits and Escape backs out in both the composer and the
notes.

## The seams, ranked by how loudly they betray the two efforts

1. **Desktop chrome asymmetry.** The composer (new-annotation editor) on desktop is deliberately
   chromeless — its Save/Cancel footer exists but only materializes on touch screens ("hidden
   where Enter and Escape do the job"). Two centimeters away, every note carries three permanently
   visible buttons. The same product holds two opposite opinions about whether buttons are a touch
   crutch or a permanent affordance. There is a defense — the note row is partly a *state display*
   (disabled Save/Revert says "unchanged"), while the composer has no saved state to diff — but a
   fresh reviewer flags it before hearing the defense.
2. **Two different "Save" buttons.** The editor footer's Save is a rectangular (8px radius)
   filled-accent button at 0.92rem/2.6rem; the note Save is a tinted pill at 0.72rem/2.4rem. On a
   phone, both are visible in adjacent bottom sheets. Same word, same role, two designs — the most
   mechanical "two hands" tell.
3. **Two failure languages, asymmetric success feedback.** The composer reports via the popping
   ✓/✕ status dot; a failed note action just reddens its own button, and a successful note save
   has no positive signal at all (the buttons simply fade). Neither is wrong; having both is the
   inconsistency.
4. **The mobile interaction model quietly weakens the tombstone undo.** On desktop, previews
   persist until closed, so the post-delete Revert is stable. On touch, any page tap closes all
   previews and sheets are one-at-a-time — the undo evaporates on the first stray tap, making
   Delete effectively near-irreversible on mobile with nothing communicating that. The two
   features are individually coherent; their *composition* has an unexamined corner.
5. **SKILL.md accretion.** The layer-3 behavior paragraph now carries markers, previews, dragging,
   in-place editing, three buttons, tombstones, and verification in one ever-lengthening
   paragraph, with the mobile capabilities bolted after it as a separate paragraph. The doc
   betrays the layering of efforts more than the product does — appended sentences, not a
   composed description.
6. Trivia: "Cancel" (composer) vs "Revert" (notes) — semantically distinct, defensible; the
   preview title counts "ANNOTATIONS" while the touch action bar counts "notes"; the 2.4rem vs
   2.6rem touch-target mismatch from item 2.

## Highest-leverage fixes, if tightening

Unify the Save button design and the failure/success feedback (items 2–3, mechanical), then make
one deliberate decision on item 1 — either give the composer its footer on desktop too, or accept
the state-display rationale and write it down in AGENTS.md so the asymmetry reads as intent rather
than accident. Item 4 deserves a think before any code: e.g., a tap-again-to-confirm Delete on
coarse pointers, or exempting tombstoned previews from tap-to-dismiss.
