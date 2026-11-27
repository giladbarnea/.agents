---
updated: "2026-11-23 10:48 IST"
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
4. Both providers sometimes grant **banked resets**. See [Banked resets](#banked-resets).

## Read the numbers

The tool is `quota`. Non-interactive callers (launchd, cron, scripts) must call `~/.local/bin/quota`: without it on PATH, macOS runs its own `/usr/bin/quota`.

`quota` keeps a five-minute shared cache, so a read within five minutes costs no request. Extra Claude requests can cause a rate limit (HTTP 429) of several minutes. Do not call `quota` in a loop.

**One metric, two forms.** The pace to steer by is the **target rate**: the rate that uses exactly the remaining quota by the next checkpoint. Spend below it and quota is lost; above it and quota runs out early. It comes in two forms, named everywhere:

- `target_rate_without_resets`: ignores banked resets.
- `target_rate_with_resets`: counts the banked resets that its schedule redeems.

Which one to steer by is Gilad's call. If he hasn't said, ask through the [topmost agent](TOPMOST.md), as with reset decisions below. Both already include the Claude–Fable dependency: Fable's rates count its room in the shared Claude week, so a Lead can mix models without its own adjustments.

1. To get the pragmatic minimum, run `quota`. It prints one plain line per window. It leaves out resets and Gemini on purpose: no protocol for them exists yet.
   1. `target_rate` is the pace, in multiples of 1x, that uses exactly the quota left by the time the window resets, ignoring banked resets. 1x spends one week's allowance per week.
   2. `observed_2h` is the account-wide pace over the last 2 hours. `n/a` means unknown, not zero.
   3. When `observed_2h` is above `target_rate`, slow down or move work to another pool.
2. To get the full data as JSON (schema 6):

   ```sh
   quota -f json | jq '.providers[] | {name, target_rate_without_resets, target_rate_with_resets}'
   ```

   1. Each rate is `{status, error, rate, range {low, high}, until, limited_by}`. The number is `.rate`. `status` is `ok`, `awaiting_first_use`, `redemption_due` (rate 0 until a due reset is redeemed: see Banked resets), `unfunded` or `unavailable` (rate null). `error.message` explains every status but `ok`. A null rate never falls back to the other form.
   2. `target_rate_with_resets` adds `checkpoints[]` (times to check again; at a redemption, ask Gilad), `resets_counted[]` (empty when it counts none) and `since`.
   3. `limited_by` (`fable` or `claude_weekly`) says which meter binds a Fable rate.
   4. `.observations` lists the account-wide rate over the last 2, 6, 12 and 24 hours. None is preferred. Read `window_seconds` and `covers_full_window` first. A null rate means unknown, not zero.
3. What-ifs (faster or slower paces, previews of redeeming) live in `quota simulate` (`--help`). They are for Gilad and the usage Lead when setting policy, not a Lead's daily steering.
4. To subscribe to the quota service, load its Pi extension (`pi -e ~/dev/usage/extensions/pi/quota-service.ts`), declare your appetite with `quota_appetite`, and work as if quota were infinite. It tells you when your grant changes. See `~/dev/usage/docs/quota-service.md`. While its numbers mature, the target rate you steer by wins over a grant.
5. To ask about `quota`, or to report that a grant or spend number is way off, message the usage Lead.

## Balance the two subscriptions (every Lead)

Most Leads do not need the quota service. They need one habit:

1. Before a long task, and when you delegate, run `quota` and compare the target rates of Claude and Codex.
2. When one pool's target rate is clearly lower than the other's, move work to the pool with more room. Switch your own model, your delegates' models, or both, to the model with equal performance on the other provider.
3. Keep Fable at high thinking or above for work that needs it. Codex has no equal for it.

Models with about the same performance, by thinking level (ai-scores Lead, Nov 17, from Artificial Analysis benchmarks; general and coding tests weighted most). These are overlapping bands, not exact equals. Where a band spans levels, Gilad chose the higher one: Opus is a larger model, with strengths benchmarks measure poorly, and Sol is cheap:

| Opus 5.5 | GPT-6.1 Sol | GPT-6 Astra | Fable 5.2 |
|---|---|---|---|
| medium | xhigh | medium | below Fable low |
| high | max | xhigh | low to medium |
| xhigh | no equal (max is lower) | max | medium to high |
| max | no equal | max is nearest | high |

Fable xhigh and max have no equal on Codex. Fable low matches Sol and Astra at max on coding, but knows more and makes up less. The bands come from benchmarks, so they are not proven for long coordination, judgment in conversation, medical reasoning or following instructions.

A model switch rereads the whole context once on the new provider. So switch at a natural break, or choose the model when you start a delegate.

## Choose the model by the task

Gilad's two tiers, as of Nov 26:

**Excellent models:** Astra high or xhigh, Opus high to xhigh, Fable medium to xhigh. Use one when the task:

1. needs you to hold a wide, complex web of factors, or has delicate details where one mistake makes a large part of the result wrong (the usage algorithm Owner's mission has both);
2. needs judgment and taste in ambiguous cases, where deep understanding turns a coin flip into the right decision;
3. needs an especially large amount of information, where connections between far-apart facts help;
4. is the plan for a large task, which needs both breadth and depth of quality;
5. is the review of important work that a good model did.

They cost a little more (Opus high costs about the same as Opus medium), reasonably more, or much more (Fable xhigh, the extreme).

**Good models:** more cost-effective, and they do a great job. Use them when none of the above applies: Opus high, or Sol xhigh or max, for harder or more important tasks; otherwise Opus medium or Sol high.

Example: a new plain output mode and a flag for `quota` (Nov 27) is a task for Opus medium or high, or Sol xhigh, not Astra.

## Banked resets

A banked reset refills a meter on demand. There are three kinds:

1. **Codex reset:** refills Codex and starts a new 7-day week at the first request after redemption. The free refill that was coming moves out with it.
2. **Anthropic full reset:** sets the Claude week and Fable to 0% used. The weekly deadline stays.
3. **Anthropic Fable-only reset:** sets Fable to 0% used, and gives half of Fable's used points back to the Claude week. The weekly deadline stays.

**The trade-off.** Redeeming overwrites whatever is still unused, so a reset is worth the most at the moment its meter runs out (100% used), and less the later in the week that happens. Using one early buys pace now at the price of less work overall. A full reset redeemed while only Fable has run out also throws away the Claude week's unused room, which a Fable-only reset keeps. A Codex reset can be worth less than nothing, because it also postpones the free refill. Whether to pay for pace now or wait is Gilad's call at the time.

**Read it:** `quota resets` (or `quota -f json | jq '.resets, .reset_kinds'`) lists each banked reset with its value now, what it throws away, its value on each day its meter could run out this week, its value in a fresh week, and a forecast at the measured paces. It states a conclusion only when one option wins regardless of priorities. Otherwise it gives the numbers, and the choice is Gilad's. `quota simulate reset` shows the same values for any stated quota state.

**Who redeems.** Redeem only:

1. when Gilad has told you to, naming resets that are banked now, not hypothetical ones; or
2. after you surface the option with its trade-off, and Gilad confirms explicitly.

Surface it in his terms, for example: "Using `<reset>` now lets us keep this pace and gains X days of work. Slowing down and using it when the meter runs out would gain Y." Raise it when you see a need or an opportunity: the work wants more than the target rate allows, a meter is about to run out early in a week, or a reset is near expiry.

## Known gaps (Nov 13 2026)

1. **The quota service's prices are being re-measured.** Two independent passes found Opus under-priced by about a third (an agent unit is about $13/hour of Opus, not $20). The fix awaits Gilad.
2. **Full Claude reset timing is assumed**, not observed: Gilad's rule is that every Anthropic reset keeps the weekly deadline.
3. **Short observations are noisy.** The providers round used% to whole numbers; ranges show it.
