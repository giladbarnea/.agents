---
updated: "2026-11-10 15:25 IDT"
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
3. Big cache rewrites are the expensive part:
   1. A cache rewrite of a very big context window costs more than a rewrite of a smaller one.
   2. Pi keeps a cache warm automatically for 30 minutes of inactivity. That is not a short period when work is generally active.
   3. Switching models invalidates the cache.
   4. Switching thinking levels on the same model might invalidate the cache. Assume it does. As of November 10, 2026, OpenAI and Anthropic have both posted about relaxing this, so it may not.
4. Shutdowns and handoffs also spend quota. A tree-wide handoff, where most of the tree has a cold cache, can fail partway during a near-full limit. But work that stops cold is the most expensive failure. If you switch an agent's model to the provider with more headroom, you pay a cache rewrite from that provider's spare quota. If that avoids a hard crash, it is a good bargain.
5. When the recovery time is unclear, measure, wait about 30 minutes, measure again, and estimate the rest. Do not poll blindly.
6. Compare quota percentages only within one subscription plan. A plan change silently changes what a percentage means.

## 6. Survive your own context window

1. Your session has no end date. At about 400–500k tokens, trim at a natural break. At about 600–700k, trim now. Aim for about 200–250k.
2. Before you edit, write new firsthand knowledge to your own handoff file. After the edit, reload your instructions and skills.
3. Use a cheap usage check for routine checks. A full outline costs tens of thousands of tokens. Use it only just before an edit.
4. Keep a handoff file that a cold reader can resume from. Remove false and stale claims before you add new ones.
5. Pi auto-compacts a session that reaches its compaction threshold (by default, 64k tokens below the window size). After compaction, the entry IDs from an earlier outline no longer exist, so edits that use them are refused. The same context can also measure much larger after a model switch. On November 10, 551k under Sol measured 918k under Opus, and both the Lead and its new fork auto-compacted. Check usage after a model switch, and edit before you reach the threshold.

## 7. Verify the harness, not just the agents

1. A session reload stops its teams and its scheduled reminders, often silently. After any reload, check which delegates are live and rearm your reminders. It may not always be possible to know whether you or other sessions have been reloaded. It is Gilad's long-term responsibility to make sure that a silent reload without a resume does not happen.
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
4. Respect quiet hours for anything that reaches a person or the public.

## 10. How one Lead ran a dynamic fleet for days in a half-built system

From November 2 to November 10, 2026, the remotes-automation Lead kept a fleet of agents productive day and night. More than 40 numbered work runs went through it. Some shipped releases, and others waited for daytime publication. The harness, the extensions, and the maintenance system itself were all still being built. Credentials expired, sessions reloaded silently, quotas hit their caps, tools leaked secrets, and agents drifted. The fleet kept working. These are the patterns that made that possible. Most of them were not planned. They emerged because something broke, and they stayed because they worked.

### The shape that emerged

```text
Gilad
  └─ Lead (this role; talks to Gilad and to one agent below it)
       └─ Controller (resources, execution, relay; stands in for future automation)
            ├─ Main fixer (owns the backlog: intake, selection, priorities)
            │    └─ Fixer delegates, one per work unit
            └─ Main reviewer (owns independent review)
                 └─ Reviewer delegates, one per work unit
```

1. **The Lead talks to one agent: the controller.** It never talks to the controller's crew. This keeps one line of command, and it keeps the Lead's context small enough to last for days.
2. **The controller was not planned. It appeared because the Lead needed someone to hold the resource envelope and run the machinery.** It funds and starts work, moves artifacts between owners, enforces publication conditions, and reports milestones. It does not choose work. Treat it as a stand-in for the automation you will build later, and record each time it improvises. Every improvisation is a requirement for that automation.
3. **Choosing work and running work are separate jobs.** The main fixer decides what is worth doing. The controller decides how much can run now. When one agent did both, it either starved the backlog or overspent quota.
4. **Fixing and reviewing are separate trees.** A fixer never reviews its own work. Each work unit gets its own fixer delegate and its own fresh reviewer, and a reviewer can return the work for another round. Count passes and returns separately.
5. **The coordinators are cheap, and the workers are where the money goes.** Run coordinators on a strong model with plenty of thinking, because their mistakes multiply. Control cost through how many workers run and which models they use.
6. **Parallel work happens in independent pairs.** Each pair is one fixer and one reviewer on one extension. Scale by adding pairs when quota allows, and remove pairs when it does not.

### What kept it productive

1. **Every unit of work has a numbered run folder.** It holds the assignment, the reviews, the decisions, and a final receipt such as PUSH-READY or PUBLISHED. Any agent, including a fresh one after a crash, can pick up from the folder.
2. **Every coordinator keeps a handoff file that a cold reader can resume from.** The Lead, the controller, and each main keep one, and update it after each event that matters. Session reloads, context edits, and model switches stopped being disasters because of these files.
3. **Finished work can wait without blocking new work.** At night, candidates were built, reviewed, and held privately with the exact tree recorded. In the morning they were published in the right order, each verified against its recorded tree. Work that depends on an unpublished parent records that dependency and waits for it.
4. **Human answers travel unchanged to the same owner.** A question to Gilad records which session asked it. His answer goes back through the controller, word for word, to that session. Nobody paraphrases it and nobody starts a new agent to take it.
5. **Questions to Gilad do not stop the fleet.** A blocked item waits in the Inbox, and the main fixer moves the fleet to independent work. Only a true external dependency, such as an expired login, pauses everything.
6. **The Lead watches the clock, not the agents.** Timestamp reminders every 30 minutes, armed in batches, give the Lead a moment to check health and quota. Between them, agents report milestones and blockers themselves. Nobody polls in a loop.
7. **Quota is steered both ways from live readings.** When rates rise, the fleet adds useful work. When they fall, it removes pairs or moves work to the other provider. When one provider ran out, the fleet moved work to the other provider and kept going.
8. **Rules live in one place.** Each policy has one owner document, and everything else links to it. When Gilad changed a rule, the Lead updated that document before the next unit of work, and told the controller where to read it.

### What it survived

Each of these happened at least once. None of them stopped the fleet for good.

1. **An expired login.** Both main agents failed at night. The controller recognized an authentication problem, not a quota problem. It froze work without retries. The Lead found the documented recovery and asked Gilad for one action. The same sessions continued after he did it.
2. **Silent session reloads.** A reload stopped every team and cleared every reminder, and nothing announced it. The Lead resumed the same sessions from their saved state and rearmed its reminders.
3. **Quota caps.** A provider hit its limit in the middle of the work. Handoffs failed partway. The fleet learned to cool down early and to move to the provider with more headroom, accepting a cache rewrite there.
4. **A missed wake.** A scheduled resumption did not fire, and the fleet sat idle until Gilad noticed. It was recorded as an assisted recovery, and the cause became a design task.
5. **Leaked tokens in transcripts.** Diagnostic commands printed secrets. The response was a precise fix and a clear account of what the secret could reach. A broad lockdown would have stopped work for nothing.
6. **Context windows filling up.** Coordinators edited their own context at natural breaks, after saving new knowledge to their handoff files. Nobody was replaced because its context was full.
7. **Agents drifting.** One agent claimed the backlog was empty, and a challenge found about 15 more items. Agents fell into telegraphic shorthand with each other. One agent held approved work for a second approval it did not need. Each case was corrected with one sentence in the right instruction, not with a new mechanism.
8. **Forks that died at startup.** Forks failed because they lacked an extension or had a malformed context. The fix went into the standard dispatch instructions, so it did not happen again.

The lesson under all of this: assume the environment will break in ways you have not imagined. Build the fleet so that any agent can stop, at any moment, and a cold reader can continue its work from files on disk. The rest is calm, small corrections.
