---
updated: "2026-11-11 14:25 IST"
description: The quota situation, its tradeoffs, and how a Lead reads it with `quota`
author: usage Lead
---

# Quota

## Situation

All agents on this Mac spend from the same subscriptions, in every project:

1. **Claude** (Anthropic, the `anthropic/*` models). The plan is Ultra (the former Max 20x). It has one weekly limit for all models and no five-hour limit. **Fable** has its own weekly limit, equal to 50% of the Claude weekly limit. Fable use counts against both: a full Fable meter is 50% of the weekly meter.
2. **Codex** (ChatGPT, the `openai-codex/*` models). It has one weekly limit.
3. **OpenRouter** (API). Its budget is $20 per 30 days.

The numbers are account-wide. One Lead's spend reduces what every other project has.

A rate of **1×** means one weekly allowance spread evenly over one week.

## Tradeoffs

1. Quota that is left at the weekly reset is lost. Quota that runs out early stops every agent on that provider until the reset. The goal is to arrive at the reset with little quota left.
2. Two pools give room to move. When one provider is ahead of its pace, move work to the other. The `ai-to-delegated` skill's budget-balancing guidance covers this.
3. Fable spends both its own allowance and the shared Claude allowance. Either can stop it. If other models have spent more than 50% of shared Claude, shared Claude runs out before Fable reaches 100%, without a reset.
4. Claude also grants **banked resets**. A full reset clears the weekly limit and Fable together. A Fable limit reset gives back only the Fable part of the weekly usage. `BANKED` counts each limit's resets. Only Gilad redeems them.
5. Codex sometimes grants **banked resets**. A redeemed reset refills the week. The new 7-day window starts at the first model request after the redemption, not at the click. A reset is worth more when it is redeemed close to 100% used: its value is used% minus elapsed% at redemption. `quota` never redeems. Only Gilad redeems, so a redemption is a "needs the delegator first" item.

## Read the numbers

The tool is `quota` (renamed from `aiuse` on Nov 11). Non-interactive callers (launchd, cron, scripts) must call `~/.local/bin/quota`: without it on PATH, macOS runs its own `/usr/bin/quota`.

`quota` keeps a five-minute shared cache, so a read within five minutes costs no request. Extra Claude requests can cause a rate limit (HTTP 429) of several minutes. Do not call `quota` in a loop.

1. To get a quick overview, run `quota`. Each column is one limit:
   1. `USED` is the used share, and `ELAPSED` is the elapsed share of the window.
   2. `BURN` is used divided by elapsed. Above 1×, you spend faster than the week allows.
   3. `TARGET RATE` is the rate that uses exactly the remaining quota by `RESET IN`. Spend below it and quota is lost. Spend above it and quota runs out early.
   4. `BANKED` is the number of unexpired banked resets. `RESET NOW` is what one redemption now gains, in days of allowance.
   5. `STAY ON PLAN` is the rate the fixed 1× plan supports until its next checkpoint. `OBSERVED 2H` is the account-wide rate over the last 2 hours. When observed is above stay-on-plan, slow down or move work to another pool.
2. To get the same data as JSON:

   ```sh
   quota -f json | jq '.providers[] | select(.windows.weekly) | {name, weekly: (.windows.weekly | {used_percent, elapsed_percent, burn_rate, target_rate, reset_at}), banked: .reset_value.banked_count}'
   ```

3. To check pacing against a fixed plan, name the limit (`codex`, `claude` or `fable`; Codex if omitted) and the pace Gilad assigned (`1x` if he gave none):

   ```sh
   quota boost claude 1x -f json | jq '{status, error, observations, pacing: .plans[0].pacing}'
   ```

   Fable also counts against the Claude weekly limit, so an agent that runs on Fable checks both `fable` and `claude`.

   1. `pacing.rate_to_stay_on_plan` is the rate the remaining quota supports until the next checkpoint. Compare your spend with it.
   2. `observations` lists the account-wide rate over the last 2, 6, 12 and 24 hours. None is preferred: pick the window that fits your question. Read `window_seconds` and `covers_full_window` first. A null rate means unknown, not zero.
   3. `pacing.checkpoints` lists the times to check again, in order. At a redemption checkpoint, ask Gilad to redeem.
   4. Reading a plan does not restart it. `quota boost --help` explains the full contract.

4. To pick a pool quickly, run `quota pick` (or `-f json`). It ranks Claude, Fable and Codex by the rate each can still support, best first, and marks which are usable. It is a lazy hint. Check the pool's own plan before heavy work.
5. To subscribe to the quota service, load its Pi extension (`pi -e ~/dev/usage/extensions/pi/quota-service.ts`), declare your appetite with `quota_appetite`, and work as if quota were infinite. It tells you when your grant changes. See `~/dev/usage/docs/quota-service.md`.
6. To ask about `quota`, or to report that a grant or spend number is way off, message the usage Lead.

## Known gaps (Nov 11 2026)

1. **The quota service v1 is new (Nov 11).** Its per-agent costs are rough first estimates, tuned from Leads' corrections. Codex's dollar-to-quota conversion does not match yet. An idle subscriber hears about changes only at its next run.
2. **Full Claude reset timing is unverified.** A recorded Fable-only redemption on Nov 11 cleared Fable, returned shared weekly allowance and kept both deadlines. The full weekly reset has not been redeemed; its fixed-deadline behavior remains an assumption.
3. **Short observations are noisy.** The providers round used% to whole numbers.
4. **Claude and Fable are planned separately.** `quota pick` caps Fable by the shared room (twice Claude's rate). The fixed plans still treat them as separate budgets. A joint planner is not built yet.

## Planned (by intent)

1. **One set of terms.** The text, JSON and menu bar outputs will show the same data under the same names.
