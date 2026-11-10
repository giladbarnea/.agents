---
updated: "2026-11-10 16:45 IST"
description: The quota situation, its tradeoffs, and how a Lead reads it with `aiuse`
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
3. Fable's limit is the tightest. Use Fable for bounded tasks that need the most intelligence, and do not use it for long missions.
4. Claude has **Fable limit resets** (1–3 per account, from the Fable 5.2 launch, expiring Mar 8 2027). One gives back only the Fable part of the weekly usage. Other models' usage stays.
5. Codex sometimes grants **banked resets**. A redeemed reset refills the week. The new 7-day window starts at the first model request after the redemption, not at the click. A reset is worth more when it is redeemed close to 100% used: its value is used% minus elapsed% at redemption. `aiuse` never redeems. Only Gilad redeems, so a redemption is a "needs the delegator first" item.

## Read the numbers

`aiuse` keeps a five-minute shared cache, so a read within five minutes costs no request. Extra Claude requests can cause a rate limit (HTTP 429) of several minutes. Do not call `aiuse` in a loop.

1. To get a quick overview, run `aiuse`. Each column is one limit:
   1. `USED` is the used share, and `ELAPSED` is the elapsed share of the window.
   2. `BURN` is used divided by elapsed. Above 1×, you spend faster than the week allows.
   3. `TARGET RATE` is the rate that uses exactly the remaining quota by `RESET IN`. Spend below it and quota is lost. Spend above it and quota runs out early.
   4. `BANKED` is the number of unexpired banked resets. `RESET NOW` is what one redemption now gains, in days of allowance.
2. To get the same data as JSON:

   ```sh
   aiuse -f json | jq '.providers[] | select(.windows.weekly) | {name, weekly: (.windows.weekly | {used_percent, elapsed_percent, burn_rate, target_rate, reset_at}), banked: .reset_value.banked_count}'
   ```

3. To check pacing against a fixed plan, name the limit (`codex`, `claude` or `fable`; Codex if omitted) and the pace Gilad assigned (`1x` if he gave none):

   ```sh
   aiuse boost claude 1x -f json | jq '{status, error, observation, pacing: .plans[0].pacing}'
   ```

   Fable also counts against the Claude weekly limit, so an agent that runs on Fable checks both `fable` and `claude`.

   1. `pacing.rate_to_stay_on_plan` is the rate the remaining quota supports until the next checkpoint. Compare your spend with it.
   2. `observation.observed_rate` is the recent account-wide rate, over up to two hours. Read `window_seconds` first. A null value means the measurement is unknown, not zero.
   3. `pacing.checkpoints` lists the times to check again, in order. At a redemption checkpoint, ask Gilad to redeem.
   4. Reading a plan does not restart it. `aiuse boost --help` explains the full contract.

4. To pick a pool quickly, run `aiuse pick` (or `-f json`). It ranks Claude, Fable and Codex by the rate each can still support, best first, and marks which are usable. It is a lazy hint. Check the pool's own plan before heavy work.
5. To ask about `aiuse` or quota, message the usage Lead.

## Known gaps (Nov 10 2026)

1. **There is no push.** A Lead must read the numbers at its own decision points. A subscription does not exist yet.
2. **Claude reset behavior is unverified.** `aiuse boost fable` budgets the Fable limit reset, assuming it keeps the weekly deadline. No real redemption has tested this yet. `BANKED` in the `aiuse` grid still shows 0 for Claude, because it counts only resets that clear the whole weekly limit.
3. **One observation window.** The observed rate covers only the last 2 hours, so one burst distorts it. Rates over 2, 6, 12 and 24 hours are planned.
4. **Short observations are noisy.** The providers round used% to whole numbers.
5. **There is no attribution.** `aiuse` cannot tell which project or agent spent the quota.
6. **Higher fixed plans can choose tiny boosts.** The 1.5× and 2× plans can pick a boost that lasts minutes, next to one that lasts days. A fix is in progress.

## Planned (by intent)

1. **A subscribable quota service.** It will push to subscribed agents only the quota events that need a decision. Then Leads stop reading on demand.
2. **One set of terms.** The text, JSON and menu bar outputs will show the same data under the same names.
