---
updated: "2026-11-13 12:45 IST"
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

The tool is `quota`. Non-interactive callers (launchd, cron, scripts) must call `~/.local/bin/quota`: without it on PATH, macOS runs its own `/usr/bin/quota`.

`quota` keeps a five-minute shared cache, so a read within five minutes costs no request. Extra Claude requests can cause a rate limit (HTTP 429) of several minutes. Do not call `quota` in a loop.

**One metric, two forms.** The pace to steer by is the **target rate**: the rate that uses exactly the remaining quota by the next checkpoint. Spend below it and quota is lost; above it and quota runs out early. It comes in two forms, named everywhere:

- `target_rate_without_resets`: ignores banked resets.
- `target_rate_with_resets`: counts the banked resets that its schedule redeems.

Which one to steer by is Gilad's call. If he hasn't said, ask. Both already include the Claude–Fable dependency: Fable's rates count its room in the shared Claude week, so a Lead can mix models without its own adjustments.

1. To get a quick overview, run `quota`. Each column is one limit:
   1. `USED` is the used share, and `ELAPSED` is the elapsed share of the window. `BURN` is used divided by elapsed.
   2. `OBSERVED 2H` is the account-wide rate over the last 2 hours.
   3. `TARGET RATE`, as two rows: `WITHOUT RESETS` and `WITH RESETS`. When observed is above the target rate you steer by, slow down or move work to another pool.
   4. `BANKED` counts unexpired banked resets and the soonest expiry. `RESET NOW` is what one redemption now gains, in days of 1× work; `IF EMPTY NOW` is what it would gain if the pool were empty.
2. To get the same data as JSON (schema 6):

   ```sh
   quota -f json | jq '.providers[] | {name, target_rate_without_resets, target_rate_with_resets}'
   ```

   1. Each rate is `{status, error, rate, range {low, high}, until, limited_by}`. The number is `.rate`. `status` is `ok`, `awaiting_first_use`, `redemption_due` (rate 0 until a due reset is redeemed: ask Gilad), `unfunded` or `unavailable` (rate null). `error.message` explains every status but `ok`. A null rate never falls back to the other form.
   2. `target_rate_with_resets` adds `checkpoints[]` (times to check again; at a redemption, ask Gilad), `resets_counted[]` (empty when it counts none) and `since`.
   3. `limited_by` (`fable` or `claude_weekly`) says which meter binds a Fable rate.
   4. `.observations` lists the account-wide rate over the last 2, 6, 12 and 24 hours. None is preferred. Read `window_seconds` and `covers_full_window` first. A null rate means unknown, not zero.
3. What-ifs (faster or slower paces, previews of redeeming) live in `quota simulate` (`--help`). They are for Gilad and the usage Lead when setting policy, not a Lead's daily steering.
4. To subscribe to the quota service, load its Pi extension (`pi -e ~/dev/usage/extensions/pi/quota-service.ts`), declare your appetite with `quota_appetite`, and work as if quota were infinite. It tells you when your grant changes. See `~/dev/usage/docs/quota-service.md`. While its numbers mature, the target rate you steer by wins over a grant.
5. To ask about `quota`, or to report that a grant or spend number is way off, message the usage Lead.

## Known gaps (Nov 13 2026)

1. **The quota service's prices are being re-measured.** Two independent passes found Opus under-priced by about a third (an agent unit is about $13/hour of Opus, not $20). The fix awaits Gilad.
2. **Full Claude reset timing is assumed**, not observed: Gilad's rule is that every Anthropic reset keeps the weekly deadline.
3. **Short observations are noisy.** The providers round used% to whole numbers; ranges show it.
