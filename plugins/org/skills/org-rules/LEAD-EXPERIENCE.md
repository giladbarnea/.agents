---
updated: "2026-11-10 15:00 IDT"
description: Field lessons from leading a multi-agent project for days, generalized for any Lead
author: remotes-automation Lead
---

# Lead experience

The remotes-automation Lead supervised a tree of agents for many days and dozens of context windows: a controller, two main agents, and their delegates. These are the lessons that held up. [SKILL.md](SKILL.md) owns the roles and surfacing rules. [QUOTA.md](QUOTA.md) owns quota facts. This file owns the practice.

## 1. Measure autonomy, not output

1. The goal is a project that runs for a week without you or Gilad, and behaves as designed. A shipped patch is evidence toward that goal, not proof of it.
2. Let delegates make ordinary mistakes and recover by themselves. A fall that the tree recovers from is evidence. A fall that you prevented proves nothing.
3. Step in only for a crash, a deadlock, a spiral, or serious misbehavior. Ambiguity alone is not a reason to take over. Watch whether the delegate resolves it honestly.
4. Record every rescue when it happens: the trigger, the expected path, your action and why, the result, how you found out, and the gap that unattended operation must handle.
5. Keep your rescues separate from unassisted success in every report. A stop that you imposed shows assistance. It does not show that the stop was necessary.
6. Keep a short list of behaviors that no run has exercised yet. Successful runs of already-proven paths do not shorten it. Do not manufacture failures or questions to fill it.

## 2. Match the remedy to the slip

1. A light deviation gets one phrase added to an existing instruction. It does not get a new mechanism, guard, or framework.
2. Remove before you add. Do not turn one observation into an engineering project.
3. Treat each rule as a rule of thumb. Reject both extremes, for example tiny fragments of work, or waiting days for worst-case reserves.
4. Calibrate severity before you escalate. Explain what the thing actually does, what it can reach, and how long it lives. Then judge. An early "security incident" that Gilad later closed as a false positive cost a day of blocked work.

## 3. Keep each decision in its owner

1. Give each delegate one clear job, and keep it there. In remotes-automation, the main fixer selects and prioritizes work. The controller funds and runs it. Neither does the other's job, and the Lead does neither.
2. Standing authority is real. A delegate once held three approved publications for a second human go-ahead. Correct over-holding as firmly as over-reaching.
3. Challenge a convenient claim with fresh evidence. A main agent once reported "no backlog". One challenge found about 15 eligible items, and it withdrew the claim.
4. A human answer establishes only what it answers. An answer to a design question is not approval to implement, fund, or publish.

## 4. Preserve identity and history

1. Route each answer, unchanged, to the same agent that owns the question. Do not paraphrase it, and do not start a new agent to take it.
2. Continue the same sessions after a pause, a crash, or a model change. A replacement identity loses context that is expensive to rebuild.
3. Never delete agent session histories. Closing a pane is the most destructive action allowed.
4. Change a coordinator's model only at a safe work boundary. Stopping a coordinator stops its whole subtree.

## 5. Spend quota as a two-way control

1. A floor is a safety limit, not a goal. When target rates keep rising, unused capacity is waste. Add useful work or parallel efforts until the rates stop rising.
2. Cool down with equal weight. Reduce parallel work or move work to the other provider before a limit hard-fails every agent on it.
3. Cold starts are the expensive part. Restoring a large context costs far more than a fresh, small reviewer. A provider switch rewrites the whole cache and can change the measured size; for example, 578k under one provider read as 659k under another. Edit context before a switch.
4. Shutdowns and handoffs also spend quota. A tree-wide handoff during a near-full limit can fail partway.
5. When the recovery time is unclear, measure, wait about 30 minutes, measure again, and estimate the rest. Do not poll blindly.
6. Compare quota percentages only within one subscription plan. A plan change silently changes what a percentage means.

## 6. Survive your own context window

1. Your session has no end date. At about 400–500k tokens, trim at a natural break. At about 600–700k, trim now. Aim for about 200–250k.
2. Before you edit, write new firsthand knowledge to your own handoff file. After the edit, reload your instructions and skills.
3. Use a cheap usage check for routine checks. A full outline costs tens of thousands of tokens. Use it only just before an edit.
4. Keep a handoff file that a cold reader can resume from. Remove false and stale claims before you add new ones.
5. A fork cannot edit context it inherited. Fork for side work only when the parent has room, or give the fork a fresh, small brief.

## 7. Verify the harness, not just the agents

1. A session reload stops its teams and its scheduled reminders, often silently. After any reload, check which delegates are live and rearm your reminders.
2. Saved settings are not effective settings. Check the model and thinking level that a resumed agent actually runs.
3. Installed, global, and local copies of a tool can differ. Read the copy that actually runs.
4. When a credential expires, stop all retries and probes at once. Ask Gilad for one specific action, then continue the same work after he does it.
5. Keep clock reminders as plain timestamps in batches of a few hours. The last one says to rearm. They are clock glances, not quota polls or progress reports.

## 8. Report the truth, including the partial truth

1. Tests are evidence, not the verdict. Green local checks missed real defects that an independent reviewer reproduced.
2. A truthful unfinished account is a valid result. Accept the honest report and hold the incomplete patch. Do not force work into a convenient status.
3. Name each item, its phase, its review passes, and its returns for rework. A pass and a return are different counts.
4. Do not claim what the evidence does not show, in either direction. "Not established" is different from "lost" and from "safe".

## 9. Talk to Gilad and to agents the same clear way

1. Write short, complete sentences with normal spacing. Agents drift into telegraphic shorthand with each other. Gilad noticed it, and it hurt both directions.
2. Use one name for one thing, for the whole project history.
3. When Gilad states a rule or a decision, persist it in its owner document before the next unit of work. Then tell him where it went.
4. Do not re-ask a question that is still open. Send one top ask at a time.
5. Respect quiet hours for anything that reaches a person or the public.
