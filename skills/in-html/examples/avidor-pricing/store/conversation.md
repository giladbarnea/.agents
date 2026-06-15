---
description: Chronological Q&A from the two pricing-interrogation pages (index.html round 1, index-2nd-round.html round 2), reconstructed from annotations.json
last_updated: 26-06-14
source_files: [index.html, index-2nd-round.html, annotations.json]
---

# Avidor V1 Pricing — Q&A Timeline

This is the **store**: the lossless, append-only record the round-3 page
(`../index.html`) is re-derived from. Nothing here is shown to the user verbatim;
the page is the agent's current understanding, this is its memory. Block
properties (`key:: value`) carry the cross-references between a round-2 item and
the round-1 question it descends from.

Reconstructed from `annotations.json`. Each block is one annotation: the **Q** is
the prompt from the page (fuller wording pulled from the HTML where the pinned
element was too terse), the **A** is Gilad's typed answer with its timestamp.
Round 1 = `index.html` (the 30-question interrogation). Round 2 =
`index-2nd-round.html` (answers folded in, drafts to approve).

---

## Round 1 — `index.html` · the interrogation (2026-06-11 afternoon)

### q-hours-so-far — Hours already spent on Avidor
round:: 1
file:: index.html
section:: §1 Calibrate the estimator
flag:: optimism
seeds:: [[a-calibration-verdict]]

**Q:** Tally the hours already spent on Avidor (3 meetings + transcripts, the email/VPN saga, the all-night dump import, an exploration day, docs). Write the number — it's the calibration datum for what "simple" costs in this account.
**A** `[15:06:29]`: As of June 11, 3PM IST, we're at about 8 hours.

### q-multiplier — Personal optimism multiplier
round:: 1
file:: index.html
section:: §1 Calibrate the estimator
flag:: optimism
seeds:: [[a-calibration-verdict]]

**Q:** For the last three finished tasks (VPN access, dump→DuckDB, DB orientation), write silent-estimate vs actual. Divide. Apply that multiplier to every estimate on the page.
**A** `[15:09:22]`: Thought getting VPN would take an offline week; dump→DuckDB ~1h once I had access; DB orientation ~2h — both took 3h, and I was asleep while it happened (autonomous agent).

### q-practically-done — "We only need ___ and it's practically done"
round:: 1
file:: index.html
section:: §1 Calibrate the estimator
flag:: optimism

**Q:** Complete the sentence, then write three concrete ways the ___ turns out 3× harder. (You named this as your failure mode.)
**A** `[15:36:01]`: Six unpacked optimisms —
1. "Get the AI agent harness right and Ran has a competent analyst." Harder: agent *works* but does a bad job too often — ignores data sources (horizontal) / data points (vertical), mislabels junk columns as real, misreads business reality so picks wrong aggregations. Second class: latency/cost — one query = 15 min, $15 — which forces "one big smart expensive agent" → "big agent managing a fleet of small cheap models," real work.
2. "It'll run somewhere — AWS or local on Ran's laptop, does it matter?"
3. "We'll just adapt to whatever Ran's lawyers say." Actually I need help figuring out the privacy/legal probing directions — not a lawyer, Ran isn't a hospital, not sure it's "medical data," but not trivial.
4. "Nightly dump = same as the one-time dump." How exactly the same? We must automate it. Where does it live, where's it loaded (DuckDB?), where does the agent run with easy DB access?
5. Maybe need delta/diff logic — though wholesale nightly replace is fine if it saves complexity.
6. "Cloud account is Ran's, on his card; I'll just help set it up." In my mind it's "browse to GCP together, create account, billing, services, APIs, deploy, done."

### (page-level pin) — Definition of Done
round:: 1
file:: index.html
pinned-element:: main#content > h1 (annotated the whole page)
note:: The user attached this to the page title because the page never defined a DoD — fuller scope is the whole document.
becomes:: [[dod-restated]]

**Q:** (Reacting to the page as a whole.)
**A** `[15:43:42]`: We haven't even defined the DoD of Milestone 1 (aka "the project"). **DEFINITION OF DONE:** Ran goes to https://… , logs in, sees a ChatGPT-like interface (past sessions in a left sidebar), has a back-and-forth with the agent. Everything rudimentary — "no features" — the agent is basically a Claude-Code/Codex-style process: capable autonomous agent in a loop in the filesystem with tools, bash, Python, and access to the DuckDB data, able to explore and iterate on ad-hoc Python-driven analysis per Ran's requests, responding in the chat UI normally. **Soft bar:** Ran reasonably satisfied with the value — doesn't need to be mind-blowing, just needs to not suck.

### q-medical-data — Privacy law / DPA / cyber company
round:: 1
file:: index.html
section:: §3 Data layer
flag:: omitted
answered-in-round-2:: [[privacy-explainer]] [[q2-sandbox]]

**Q:** Full medical data sits on your laptop. תיקון 13 has opinions. DPA with Avidor? Encryption at rest? Ran's cyber company may audit you. Price a compliance pass or write an explicit exclusion.
**A** `[15:57:20]`: I have no idea what תיקון 13 and DPA are. And good call on Ran's cyber company — I totally forgot about it.

### q-users-day1 — Who are the day-1 users?
round:: 1
file:: index.html
section:: §2 Definition of Done
flag:: scope
restated:: [[a-users-day1]]

**Q:** Ran alone? +עמית? +שמוליק? A מוקדנית? Each persona adds permissions, training, question styles.
**A** `[16:00:01]`: Ran alone. I asked if he wanted branch managers too — he does, but that's not part of V1. Out of scope.

### q-readonly-or-act — Read-only, or does V1 act?
round:: 1
file:: index.html
section:: §2 Definition of Done
flag:: scope
restated:: [[a-readonly]]

**Q:** "Send WhatsApp to this segment" crosses into activation territory — a scope cliff. In or out, in writing.
**A** `[16:01:21]`: None of that. Purely AI agent doing real data analytics — natural-language Q&A over the company's database.

### q-mentoring-noam — Mentoring נועם
round:: 1
file:: index.html
section:: §4 Peripheral work
flag:: offline
refined:: [[a-mentoring]]

**Q:** Billable, bounded goodwill, or out of V1? Decide before he's seated next to you.
**A** `[16:02:56]`: Goodwill. Already set up a first lesson; Amit will join. Filed under networking and trust-building.

### q-docs-training — Docs, handoff, training
round:: 1
file:: index.html
section:: §4 Peripheral work
flag:: omitted
refined:: [[a-docs-training]]

**Q:** Documentation, handoff, training Ran/עמית to ask good questions. Hours?
**A** `[16:03:59]`: Another case for retainer — I'll only learn the bad ways they prompt the agent as they use it over time.

### q-support-boundary — The 21:30 "number looks weird" WhatsApp
round:: 1
file:: index.html
section:: §4 Peripheral work
flag:: offline
refined:: [[a-support]]

**Q:** During the project — included? After delivery — where's the boundary? Write the sentence you'll say to Ran.
**A** `[16:05:16]`: "Document all the session IDs where you got weird/bad responses and let's have a look in our weekly meeting."

### q-chasing-billable — Is chasing Aviv/LOGI/Bezeq billable?
round:: 1
file:: index.html
section:: §5 Dependencies
flag:: integration
answered-in-round-2:: [[draft-clauses]] [[a-rate-craft]]

**Q:** If not, you're donating your scarcest resource to their dysfunction. Price what you preach.
**A** `[16:06:33]`: I want chasing people/companies "to get the job done" (what I stand for) billable. No idea how to price it in.

### q-rate-discipline — Does ₪300/hr apply to ALL hour types?
round:: 1
file:: index.html
section:: §7 The deal
flag:: optimism
answered-in-round-2:: [[a-rate-craft]]
related:: [[q-meetings-overhead]]

**Q:** Meetings, chasing, mentoring, travel, support — one honest rate × everything beats a proud rate × donated hours.
**A** `[16:11:23]`: Good question — how do people in my position usually price this? I'm also the project's PM (I sign up for it, clients accept it). Do 1-man companies whose work is inherently variable (yelling at Bezeq while driving to Ran's office to debug on his laptop) bill each activity type differently? And we haven't mentioned research time — sometimes hours of searching/reading before I can deliver something we agreed on.

### q-demo-script — The five golden questions
round:: 1
file:: index.html
section:: §2 Definition of Done
flag:: scope
status:: pinned-for-later
answered-in-round-2:: [[draft-golden-questions]]

**Q:** Write the exact five questions Ran types on acceptance day + what a correct answer looks like. These become golden-questions test set AND milestone acceptance criteria.
**A** `[16:24:54]`: Pinning for later to not forget.

### q-channel-ui — The V1 surface (chat page, login, RTL)
round:: 1
file:: index.html
section:: §2 Definition of Done
flag:: scope
answered-in-round-2:: [[q2-streaming]]

**Q:** Web chat? WhatsApp bot? Where does it live, how does Ran log in, is it Hebrew-RTL-decent?
**A** `[16:25:55]`: Everyone speaks with the agent in Hebrew. The agent operates/thinks/tool-uses in English, but user messages and user-facing responses are Hebrew.
**A** `[16:27:27]`: Haven't thought much about auth — never implemented an auth system. Planning to use a ready-made open-source GUI app with my agent on a server driving the session; these apps ship session-history out of the box.

### q-saved-queries — Saved-question-becomes-a-button in V1?
round:: 1
file:: index.html
section:: §2 Definition of Done
flag:: scope
refined:: [[a-saved-queries]]

**Q:** You promised this in meeting 2. Parametrized saved reports (and scheduling?) in V1? Hours?
**A** `[16:30:18]`: Not for the immediate next release. A version later.

### q-nightly-unattended — Nightly-unattended pipeline item list
round:: 1
file:: index.html
section:: §3 Data layer
flag:: optimism
status:: pinned-for-later
answered-in-round-2:: [[draft-nightly-items]]

**Q:** Scheduling, VPN auto-connect, dump-arrival detection, retries, idempotent re-import, schema-drift check, alerting. Write the item list with hours each.
**A** `[16:30:33]`: Pinning for later to not forget.

### q-where-runs — Where does production run, who owns the account?
round:: 1
file:: index.html
section:: §3 Data layer
flag:: omitted
status:: pinned-for-later
answered-in-round-2:: [[draft-nightly-items]] [[q2-sandbox]]

**Q:** Your MacBook is not a server. Cloud setup, hardening, backups, ₪/month — yours or Avidor's account?
**A** `[16:30:39]`: Pinning for later to not forget.

### q-semantic-maintenance — The semantic layer is maintained forever
round:: 1
file:: index.html
section:: §3 Data layer
flag:: omitted
status:: pinned-for-later
answered-in-round-2:: [[draft-retainer]]

**Q:** When Aviv adds a column/code value ([DRIFT]) — who updates the curated views and glossary, under what billing? (Strongest argument FOR the retainer.)
**A** `[16:30:47]`: Pinning for later to not forget.

### q-wrong-answer — Wrong-answer protocol / accuracy bar
round:: 1
file:: index.html
section:: §2 Definition of Done
flag:: scope
status:: pinned-for-later
answered-in-round-2:: [[q2-not-suck]]

**Q:** Ran makes money decisions on outputs. Define the accuracy bar, how it shows its work (SQL? row counts vs anchors?), what happens when wrong.
**A** `[16:30:52]`: Pinning for later to not forget.

### q-meetings-overhead — Weekly sit-downs, inside the quote or on top?
round:: 1
file:: index.html
section:: §4 Peripheral work
flag:: offline
related:: [[q-rate-discipline]]

**Q:** Each visit ≈ 5h; six weeks ≈ 30h ≈ ₪9K — potentially a third of the "₪30K = 100 hours" budget, spent sitting down.
**A** `[16:32:21]`: Same follow-up as for "Does ₪300/hr apply to ALL hour types?"

### q-hidden-parties — Every party that can veto/delay V1
round:: 1
file:: index.html
section:: §5 Dependencies
flag:: integration
status:: pinned-for-later
answered-in-round-2:: [[draft-veto-table]]

**Q:** VPN account owner (Bezeq? LOGI?), firewall rules, cyber-company audit, WhatsApp Business approval. For each: what do you need, by when?
**A** `[16:44:31]`: Pinning for later to not forget.

### q-export-stops — Nightly export silently changes/stops — whose problem?
round:: 1
file:: index.html
section:: §5 Dependencies
flag:: integration
status:: pinned-for-later
answered-in-round-2:: [[draft-clauses]]

**Q:** Yuval owes you nothing contractually. Write the clause: detection yours (alerting), resolution-via-Aviv is Avidor's escalation, hours billable.
**A** `[16:44:35]`: Pinning for later to not forget.

### q-yuval-cycles — Measure the Yuval base rate
round:: 1
file:: index.html
section:: §5 Dependencies
flag:: integration
answered-in-round-2:: [[draft-veto-table]]

**Q:** "I'll send a user/password today" actually took days + a meeting + chasing. Count remaining Yuval-cycles × that delay.
**A** `[16:45:27]`: Good question on its own, but should be generalized to "count how many more chasing cycles you'll need for *each* of the people you'll have to chase."

### q-hybrid-structure — Retainer-from-day-1 vs milestone hybrid
round:: 1
file:: index.html
section:: §7 The deal
flag:: decide
corrected-in-round-2:: [[a-retainer-attribution]]

**Q:** Write the hybrid: fixed-scope V1 + milestone payments + optional monthly retainer starting after acceptance. What % upfront?
**A** `[16:47:42]`: Slightly wrong — it was Amit (the marketing guy) who advised retainer-from-day-1 as general business advice. I can suggest it to Ran — maybe better for both — but Ran doesn't want it more than per-project, as far as I can tell.

### q-value-check — Sanity-check against value, not just hours
round:: 1
file:: index.html
section:: §7 The deal
flag:: decide
answered-in-round-2:: [[a-winback-breakdown]]

**Q:** Winback ≈ 10,400 customers; even 2% reactivation ≈ ₪290K. Would you defend your number 1.5× higher? Why not?
**A** `[16:48:51]`: Break down this number for me. Ran doesn't have 10K active customers. Is that unique customers ever in the system?

### q-milestones — Write M1/M2/M3 with acceptance criteria and ₪
round:: 1
file:: index.html
section:: §7 The deal
flag:: decide
status:: pinned-for-later
answered-in-round-2:: [[q2-milestone-split]]

**Q:** One line each, ₪ attached (e.g. M1 = nightly ingest runs a week; M2 = agent answers five golden questions; M3 = self-serve segment + handoff).
**A** `[16:49:42]`: Pinning for later to not forget.

### q-warranty — Define end-of-warranty
round:: 1
file:: index.html
section:: §6 After delivery
flag:: scope
status:: pinned-for-later
answered-in-round-2:: [[draft-clauses]]

**Q:** The date/event after which fixes are paid. Counter-anchor to "full refund if it fails."
**A** `[16:49:47]`: Pinning for later to not forget.

### q-maintenance-retainer — Price the retainer NOW as a line item
round:: 1
file:: index.html
section:: §6 After delivery
flag:: omitted
status:: pinned-for-later
answered-in-round-2:: [[draft-retainer]]

**Q:** Drift fixes, new questions, quarterly tune-up. If not priced at signing, it becomes free labor by default.
**A** `[16:49:52]`: Pinning for later to not forget.

### q-running-costs — Monthly running costs, who pays, mark up?
round:: 1
file:: index.html
section:: §6 After delivery
flag:: omitted
refined:: [[a-running-costs]] [[q2-cost-expectations]]

**Q:** Server + LLM tokens + monitoring. Token spend scales with how chatty Ran is. Cap it or pass it through?
**A** `[16:52:16]`: Depends on Ran's preferences. I usually present two options: lean on big expensive models → I spend far less time onboarding/babysitting agents = I cost less, but running costs a few× higher. Ask me to optimize → I slash costs to a fraction, but that means orchestration = time = I cost more.

### anchors-reference — Pricing your differentiators
round:: 1
file:: index.html
section:: anchors box
refined:: [[a-differentiators]]

**Q:** (Reacting to the anchors box: free research phase, iterate-until-confident, quarterly returns — each is hours that must appear in the price.)
**A** `[16:54:50]`: I don't think the free research phase should be priced in (it's free). But iterate-until-confident *will* be priced — it's directly my time, just "work." And quarterly returns: yes, that ties to the value Ran gains.

### q-refundability — Accept the refund precedent or counter it?
round:: 1
file:: index.html
section:: §7 The deal
flag:: decide
refined:: [[a-refund]] [[q2-milestone-split]]

**Q:** Last dev refunded in full; the anchor exists in Ran's head. One line: accepted milestones non-refundable, in-progress one refundable. Where's your line?
**A** `[16:56:14]`: I don't think I should refund. I do want billable-per-milestone. For clarity, the next milestone is the DoD.

### q-scope-valve — Scope-change valve sentence
round:: 1
file:: index.html
section:: §7 The deal
flag:: scope
refined:: [[a-scope-valve]]

**Q:** "New requests land on the Phase-2 list and are priced separately." One sentence, pointed to weekly.
**A** `[16:57:21]`: My approach: after each release (each done milestone/version) we have a feedback, planning and pricing session for the next milestone. Inspired by Agile.

---

## Round 2 — `index-2nd-round.html` · answers folded in (2026-06-11 evening → 06-14)

### a-saved-queries — Phase-2 list (my read challenged)
round:: 2
file:: index-2nd-round.html
section:: §1 Settled
descends-from:: [[q-saved-queries]]

**Q (my read):** Phase-2 list is born — saved reports/buttons, branch-manager users, cost-optimized model fleet, activation (WhatsApp campaigns). Write these four under "later versions."
**A** `[21:26:44]`: Hold on — you jumped too fast and you're conflating the WhatsApp idea with the AI-agent-over-data idea. FORGET everything near WhatsApp / talking to customers / "AI business assistant." That's a completely different PROJECT, not a milestone or phase. The project we're discussing is AI agent over data. You're directionally right that these are *probably* roadmap (not phase 1), but I don't know which phase: 'Save as Skill' (named slash-commands that load a prompt into the agent's context — NOT literal buttons) and branch-manager users (different data-access tier). Cost-optimized model fleet — also TBD; I should ask Ran, maybe it's so important to him it must ship in phase 1.

### a-mentoring — Bound the cadence
round:: 2
file:: index-2nd-round.html
section:: §1 Settled
descends-from:: [[q-mentoring-noam]]

**Q (my read):** Bound it now — a cadence, not an open door, or it becomes unpriced work wearing a friendly face.
**A** `[21:46:04]`: Comfortable with a lesson once every two weeks. If I ever feel pressured toward weekly, I'll cap the total number of lessons. Lock: once every two weeks.

### a-support — Session IDs + transcript access implied
round:: 2
file:: index-2nd-round.html
section:: §1 Settled
descends-from:: [[q-support-boundary]]

**Q (my read):** Your support sentence secretly adds two scope items — UI must show session IDs/links, and you need server-side transcript access to replay them.
**A** `[21:49:53]`: I know pi-gui provides session IDs/links out of the box, but I need to verify server-side transcript files (.jsonl). If written at all, it'll be where the runtime is (the server). Eyeing Pi SDK for the agent flow; Pi CLI definitely writes .jsonl to disk (like Claude Code, Codex, Gemini CLI) — need to verify the SDK does too. 2-minute check. If not, implementing it ourselves is quick anyway.

### a-docs-training — One handoff session stays in V1
round:: 2
file:: index-2nd-round.html
section:: §1 Settled
descends-from:: [[q-docs-training]]

**Q (my read):** Carve-out — a single 1–2h handoff session stays inside V1 (Ran must operate it on acceptance day); ongoing coaching is retainer.
**A** `[21:56:22]`: Agreed. That 1–2h session is also the one where I install it on his laptop.

### a-refund — DoD = several agile milestones
round:: 2
file:: index-2nd-round.html
section:: §1 Settled
descends-from:: [[q-refundability]]
spawns:: [[q2-milestone-split]]

**Q (my read):** No-refund + per-milestone is coherent only if milestones are small. One milestone = whole DoD means you work 5–7 weeks unpaid and Ran pays ₪38K on faith. §7 splits the DoD into three gates.
**A** `[22:03:06]`: Yes — miscommunication on my side. Phase 1 has a DoD, made of multiple agile milestones for feedback, iteration, trust and incremental value. I want Ran not anxious about each step's risk, and I don't want to run without oxygen (money and feedback) for many weeks.

### a-running-costs — Soften the cost regime / numbers
round:: 2
file:: index-2nd-round.html
section:: §1 Settled
descends-from:: [[q-running-costs]]

**Q (my read):** Keep the menu, but V1 ships on regime A by decree (big model, simple architecture, costs on Ran's card). V1 numbers ≈ ₪300–1,200/mo.
**A** `[22:21:28]`: Soften this — it's not a lock yet. At most: "most probably Ran will agree to the Agile/rational choice — delay cost reduction to later versions."
**A** `[22:24:05]`: You sure on the numbers? There's zero scale; this looks 10× what it actually costs. Keep it as "need to check."

### q2-streaming — What does Ran see during a 1–10 min agent run?
round:: 2
file:: index-2nd-round.html
section:: §2 DoD implications
state:: answer
descends-from:: [[q-channel-ui]]

**Q:** Ready-made UIs stream tokens; an agent loop emits steps. Without progress Ran thinks it's broken by minute two. Minimal step-streaming IN scope — confirm or strike.
**A** `[22:28:48]`: Wrong base assumption — agent loops emit thinking blocks trivially (or automatically, in pi-gui's case), visible to the user.

### q2-sandbox — Sandbox / read-only / no egress
round:: 2
file:: index-2nd-round.html
section:: §2 DoD implications
state:: answer
descends-from:: [[q-medical-data]] [[q-where-runs]]

**Q:** Baseline hygiene: container sandbox, read-only DuckDB mount, no internet egress except the LLM API. Agree in scope?
**A** `[22:34:09]`: Yes to read-only DuckDB mount + no egress except the LLM API. Probably NOT "sandbox" — I'll use Docker because that's how you deploy *anything*, but not as a security means. The word "sandbox" carries a huge rabbit-hole. No sandbox. Just no network, and DuckDB read-only.

### a-winback-breakdown — The 10,377 winback funnel
round:: 2
file:: index-2nd-round.html
section:: §3 Corrections
descends-from:: [[q-value-check]]

**Q (my answer to your challenge):** Not active, not everyone-ever. Funnel: 303,622 ever in CRM → 37,446 with a typed insole visit → 16,620 active (0–2y) → **10,377 winback (2–4y)** → 10,449 colder (4y+). 99.9% have a phone; median lifetime spend ₪2,450; 1–2% reactivation ≈ ₪250–500K.
**A** `[23:17:44]`: That whole funnel is valuable — let's remember it. Good negotiation material (even if just in my own head).

### q2-milestone-split — Split the DoD into 3 payable milestones?
round:: 2
file:: index-2nd-round.html
section:: §1 Settled (under a-refund)
state:: answer
descends-from:: [[a-refund]] [[q-milestones]]

**Q:** Do you accept splitting the DoD into 3 payable milestones (pipeline / agent / UI+handoff)? If not, what split?
**A** `[12:05:40, 06-14]`: We'll split into A FEW payable milestones, probably ≥3, but I'm not committing to 3 right now. I need to dive into 1–2 more aspects of the DoD and split them too, for finer effort granularity for both Ran and me. Vague idea: split not by the *time-effort* axis but by the *quality/AI-ability* axis. There are ≥2 capability tiers, from tier-0 ("ask basic things about your data — basic NL-to-SQL") through tier-N (highly intelligent, experienced data analyst with deep business familiarity, doing complex *analyses* — what-if simulations, cause-and-effect — categorically beyond "queries"). Each tier jump directly costs me more time — a hands-on continuous light-eval loop distilling wisdom into the agent harness.

### a-differentiators — Research free; quarterly tune-up TBD
round:: 2
file:: index-2nd-round.html
section:: §1 Settled
descends-from:: [[anchors-reference]]

**Q (my read):** The ~dozen hours to date stay unbilled, stated explicitly ("שלב המחקר והאפיון — ללא עלות. החיוב מתחיל מחתימה"). Iteration inside milestones; quarterly tune-up into the retainer.
**A** `[12:16:43, 06-14]`: Yes to "שלב המחקר והאפיון ללא עלות." NOT YET DECIDED about the quarterly tune-up retainer — I'll decide after the initial proposal draft, because it depends on what work/issues I predict Ran's business and the system will need over time.

### q2-cost-expectations — Commit to per-question cost numbers?
round:: 2
file:: index-2nd-round.html
section:: §2 DoD implications
state:: answer
descends-from:: [[q-running-costs]]

**Q:** State expected per-question cost ₪1–7 and 1–5 min typical, with regime B as the escape hatch. OK to commit as "typical"?
**A** `[12:28:41, 06-14]`: No — not doing per-question cost prediction yet. I'll propose two high-level paths (Ran chooses): expensive-slow-less-work-for-Gilad vs cheaper-somewhat-quicker-more-work-for-Gilad (orchestrating an agentic pipeline). This axis plays nice with the capability-tier axis; there are different ways to control tiers in each path, each with tradeoffs. Need to think more.

### q2-not-suck — Golden-questions-as-acceptance
round:: 2
file:: index-2nd-round.html
section:: §2 DoD implications
state:: answer
descends-from:: [[q-wrong-answer]] [[q-demo-script]]

**Q:** "Doesn't suck" is a mood, not acceptance criteria. Adopt golden-questions-as-acceptance (M2 accepted when the agent answers all five correctly on fresh data)?
**A** `[12:30:13, 06-14]`: Agree 'doesn't suck' is unacceptable — drop the term. This ties to the capability-tier idea, and I like tying tiers to a lightweight eval result (a specific dataset) — makes each tier measurable. We'll have to design that.

### a-retainer-attribution — Focus on the plan, not the post-project model
round:: 2
file:: index-2nd-round.html
section:: §3 Corrections
descends-from:: [[q-hybrid-structure]]

**Q (my read):** Corrected — per-project milestones are what Ran wants AND what you wanted; Amit's advice survives as the post-V1 maintenance retainer.
**A** `[14:07:25, 06-14]`: Give less weight to which business model I apply *after* the project (this retainer or the other), and focus on getting the plan right: feasible, granular enough to mitigate the "wow that's a big sum" effect on Ran, building trust.

### a-calibration-verdict — Map the steps first
round:: 2
file:: index-2nd-round.html
section:: §3 Corrections
descends-from:: [[q-hours-so-far]] [[q-multiplier]]
spawns:: [[q2-recount]]

**Q (my read):** On solo technical work your estimates are honest (×1–1.5); agents decouple wall-clock from attended hours. The 3× monster lives in *other-people* work. So: estimate build hours honestly, pad coordination brutally, bill fixed-per-milestone.
**A** `[14:20:41, 06-14]`: I want to complete thinking through and mapping out all the steps required from here to V1 before thinking about this.

### draft-golden-questions — The five golden questions (draft)
round:: 2
file:: index-2nd-round.html
section:: §4 Drafts
state:: approve / edit
descends-from:: [[q-demo-script]]
related:: [[q2-not-suck]]

**Q:** Approve/edit these five Hebrew golden questions (double as M2 acceptance + eval harness).
**A** `[18:25:41, 06-14]`: Hold on, these questions are stale — I've formed better ones grounded in Ran's real data. No time for this now; let's just remember that AI capability tiers should have a dataset to be measured against.

### draft-nightly-items — Don't price background automation by time
round:: 2
file:: index-2nd-round.html
section:: §4 Drafts
pinned-element:: §4 "Draft 2 — Nightly-unattended pipeline" heading
state:: approve / edit
descends-from:: [[q-nightly-unattended]] [[q-where-runs]]

**Q:** (The itemized 38-attended-hour pipeline table, "₪11.4K at your rate.") Challenge any line's hours.
**A** `[19:31:45, 06-14]`: I don't think that's the business model to price such automatic background work. The only way to price it is NOT "how much time it'd take me without AI" but how much money it saves / opportunity it gains for Ran. Scratch these calculations. Pricing is more complex and nuanced than that.

### draft-veto-table — Never estimate third-party time (the father-in-law rule)
round:: 2
file:: index-2nd-round.html
section:: §4 Drafts
descends-from:: [[q-hidden-parties]] [[q-yuval-cycles]]
principle:: only-estimate-what-you-control

**Q:** (The veto-party table: Bezeq/LOGI, Yuval/Aviv, cyber company, Ran — three external loops, each 3–10 elapsed days.)
**A** `[19:43:28, 06-14]`: My father-in-law's wisdom: never even pretend to estimate how long third parties take. Only estimate steps fully under my control. When presenting a timeline to Ran, there should be clear blocks for "I need LOGI to give me X" *without a time label*. That puts the weight to make them deliver ASAP on Ran, not me — HE pays them, HE has the relationship. It IS professional of me to make as many calls as needed, spread requirements around, and drive the project — but Ran should always know what I need from third parties and when, and be the one holding the whip.

### draft-clauses — Restructure the protective clauses
round:: 2
file:: index-2nd-round.html
section:: §4 Drafts
state:: approve / edit
descends-from:: [[q-chasing-billable]] [[q-export-stops]] [[q-warranty]]
related:: [[draft-veto-table]]

**Q:** Approve three clauses — clock-stop (coordination included up to 8h, then ₪300/hr), upstream changes (4h/incident pre-approved), warranty (21 days, accepted milestones final).
**A** `[19:50:57, 06-14]`: On the first two clauses — I don't like the sudden flip in attitude, like "I'm a team player for N hours then I'm a princess." I prefer my Draft-3 approach ("My father-in-law…"): don't commit to things outside my control, so there's nothing to defend against. It's others' responsibility; every minute lost chasing them is Ran's and the chasees' inefficiency.
**A** `[19:58:40, 06-14]`: On warranty — structure it differently. Two categories merit 'extra' work: my bugs/defects (things I should have predicted) and outside-world issues (upstream changes, new requests, data-content surprises — things I couldn't predict, same as feature requests). IN ANY CASE accepted milestones are final and what's done is done. Fixing my bugs/defects are legit blocks in the next iteration, counting against time=cost, prioritized and committed to at the post-release feedback/planning/pricing meetings — just like an employed dev whose employer doesn't deduct bugs from salary; it's part of the job. Outside-my-control events (support a new schema, fix a sync broken by a Bezeq server migration) are likewise topics to discuss, estimate, price and commit to at post-release FP&P meetings.

---

## Open frontier carried into round 3

These are the live threads the round-3 page (`../index.html`, §2) puts back to the user:

- **f-map-steps** — map every step from here to V1 (Gilad wants this first; blocks the split and the recount). ← [[a-calibration-verdict]]
- **f-privacy** — privacy/legal exposure (תיקון 13 / DPA / cyber audit) still under-scoped. ← [[q-medical-data]]
- **f-tiers** — define capability tiers + per-tier eval datasets. ← [[q2-milestone-split]] [[q2-not-suck]] [[draft-golden-questions]]
- **f-milestone-split** — split the DoD into ≥3 milestones along the tier axis. ← [[q2-milestone-split]] [[q-milestones]]
- **f-cost-paths** — frame the two cost/effort paths for Ran. ← [[q2-cost-expectations]] [[q-running-costs]]
- **f-rate-types** — which hour-types the rate covers (meetings, research, travel). ← [[q-rate-discipline]] [[q-meetings-overhead]] [[q-chasing-billable]]
- **f-verify-jsonl** — confirm Pi SDK writes `.jsonl` transcripts. ← [[a-support]]
- **f-retainer** — decide post-V1 maintenance retainer after the first draft. ← [[a-differentiators]] [[a-retainer-attribution]]
- **f-recount** — redo the hours calibration after step-mapping. ← [[a-calibration-verdict]]

## Constitution extracted this round

- **P1 only-estimate-what-you-control** ← [[draft-veto-table]] (retired [[draft-clauses]] clock-stop)
- **P2 price-by-value-not-hours** ← [[draft-nightly-items]]
- **P3 split-by-capability-tier-measured-by-eval** ← [[q2-milestone-split]] [[q2-not-suck]]
