---
last_updated: 2026-10-26T23-28
description: Source and verification record for the latest-design explainer video.
---

# Source of truth

Read all 3,125 lines of `transcript.md`, produced by `ch 01a17187-b686-749f-8acd-6b9cf55cce74`.
The transcript ends before the implementation and protocol repairs completed.

Current implementation and operational documentation: `/Users/giladbarnea/dev/remotes-automation`, main `9650860ae58fcac37539bf8e6885b83484b63491`.
The remote main has the same commit. The local checkout is clean. The live configuration says `enabled: false`.

Precise approved design: `desks/2026-10-22-one-scope-design/FLOW.md` and its README.
Later process-lifetime decision: `desks/2026-10-25-two-tree-build/DECISIONS.md`.
Current open questions: `LOCK-DIFF.md`. Its five confirmed protocol gaps were subsequently repaired, as recorded in `PROTOCOL-FIXES.md`.
Bend model: `.worktrees/bend-design-lock`, commit `450d2eb`, its design README and `bend/REVIEWS.md`.

Every script entry names its supporting section in `source`. All captions were checked against these documents before synthesis.

# Facts and boundaries

- Two trees share the overall scope. Fixer delegates edit persistent extension clones. Reviewer delegates alone decide approval.
- Main reviewer passes verdicts unchanged. Main fixer alone judges across extensions and takes release, return or hold actions.
- Release requires approval. Publication uses the reviewed tree and base. Product changes need a separate current push tap.
- A return retains original reviewer text and ordering. Changes or dropped findings carry reasons. Both delegates see the same findings list.
- The third return causes two handoffs. Holds and answers do not consume a return. There is no universal three-review cap.
- Main fixer can ask directly without review. Delegate questions require approval and release. Dependent items can wait on a named question.
- One Telegram question at a time. Answers resume the current main fixer when idle. A retired owner is replaced, with the answer and private context note.
- Scheduled new work starts a fresh run only when work is not in progress. Quota pauses retain agents. Three checks per day are scheduled.
- Each event uses a new RPC process with the saved main session, then closes it after the result. Delegates resume their saved sessions.
- Phase one stores state but assumes no unexpected process death. Crash reconstruction is phase two. Automatic default answers are deferred.
- Pi 1.4 acceptance must discard the two carried unpublished patches without questions. Silent removal of pi-simple-team's Pi 1.3 workaround fails.
- Phase one is built but disabled. Documentation records 65 tests, 20 doctests and two real Pi rehearsals. The acceptance run has not started.
- Bend checks 52 single-step component safety laws. It proves neither Python conformance, composition nor progress. Its branch remains unmerged.
- Q1: return budget per item or per delegate batch. Build currently counts each item.
- Q2: response after rejecting an invalid action. Build pauses, sends ntfy and retries on a scheduled check.
- Q3: after refusing a moved-base push, what lifecycle should replace the old approval? Build refreshes and returns the item to the gate.
- Q4: an explicit way to discard unreleased obsolete items. Existing adoption and held-question withdrawal do not form a complete closure rule.
- Laws approval and connecting the unmerged lock to the implementation remain user decisions. Five repaired protocol gaps are not pending choices.

# Success and falsification

Success: a 4–4.5 minute 1080-square H.264/AAC video at 24 fps, 28 illustrated scenes, matching narration and captions, soft music under the voice, and readable 720p delivery.
Every open policy choice gets narration, a concrete mechanism diagram and a visible OPEN label.
Each scene has a 0.4-second lead and a 2.3-second silent pause. The complete picture must stop changing before narration ends.

Failure: any replaced design presented as current, any build interpretation presented as approved policy, any claim that Bend proves the Python system, omitted Q1–Q4, clipped captions, wrong narration, audio/video drift, unexplained jargon, late entrances, or options shown only as lists.

Visual vocabulary: red wrench = fixer, navy magnifier = reviewer, double ring = main agent, striped box = persistent clone, paper = item/evidence, mustard = system/gate/open choice. Green means approved/passed. Open decisions use numbered mustard markers.

# Revision from Gilad's feedback

The skill's updated `tts.py`, `render.py`, `audio.py` and `render_all.sh` were copied first.
`tts.py` now calls ElevenLabs with Bella, the warm educational narrator, using Multilingual v2 and speed 0.83.
The key is read from the user-specified file at runtime. It is never printed, stored in another file, or included in the source.
`speech.json` owns start, lead, speech length and scene duration. Render, audio and captions read that timeline.
ElevenLabs supports the requested speed setting and 24 kHz PCM output. See the [official API reference](https://elevenlabs.io/docs/api-reference/text-to-speech/convert).

The narration was condensed from 32 to 28 scenes. All four open policies remain. Q1, Q2 and Q3 each use two scenes; Q4 uses three.
Q1 shows two paths and their return counts. Q2 shows refusal, waiting, notification and the next scheduled retry.
Q3 shows the old patch blocked, an updated copy, and the fresh review and push tap for replacement product work.
Q4 shows today's reappearing question, then drop versus wider withdrawal, then run-start closure. Each keeps OPEN and current behavior visible.
The narrower withdrawal option closes questions; it leaves a policy to choose for old patches. This is a consequence to assess, not a new approved rule.

Term introductions:

| First scene | Term and explanation |
| --- | --- |
| r01 | Pi is the coding assistant; extensions are its add-ons. |
| r02 | Main agents lead; delegates are specialists who fix or review. |
| r03 | A clone is called an extension copy. |
| r04 | The picture pairs the patch document with the label “code changes”; a question is the other kind of item. |
| r05–r09 | Release sends approved work forward; return sends it back for revision; hold waits for a named answer. |
| r06 | Push means publish; GitHub holds shared code; a product change changes what users see. |
| r08 | Handoffs are notes for replacements. |
| r11 | Retired means replaced; private notes carry the answer's context. |
| r12 | A run groups maintenance work. Quota is replaced with usage limits. |
| r13 | RPC is replaced with a picture of programs waiting for messages, closing and resuming saved conversations. |
| r17 | Bend is the checker; laws are design rules; the model is a simplified system. “Bend lock” is not used. |
| r23 | “Moved base” becomes a changed starting version of the shared code. |

# Verification

The Bend checker was run locally and reported `ALL PROOFS CHECK`. The optional Lean verdict was not run.
Mid-scene and end-scene contact sheets were inspected. The first check found three overflowing titles; they were shortened.
The narration was transcribed back for all 28 scenes. Captions match the speech metadata.
`inspect_pacing.py` confirms all 28 source pauses are silent, including music. It compares screenshot hashes before speech ends and twice during each pause.
Every comparison matches: pictures finish before speech ends and remain unchanged during pauses. Each early frame differs, so animation still occurs before the pause.
The updated spoken timeline lasts 255.230 seconds. Final stream measurements and sizes are recorded in `build/video-check.json`.
The mix uses quiet generated music only under speech, voice-controlled ducking and loudness normalization. Pauses remain silent.
Both final streams last exactly 255.250000 seconds at 24 fps. The 1080p file is 48,343,572 bytes; the 720p copy is 10,151,511 bytes.
Five exported frames were inspected. Full decoding passes, and all 28 pauses remain silent in the decoded AAC audio.
