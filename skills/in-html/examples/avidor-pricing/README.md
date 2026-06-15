# Avidor pricing — the continuous-conversation experience

A worked instance of the in-html skill used the way it's actually used: a long
back-and-forth perfecting a decision (here, how to price a freelance project),
across many rounds. It demonstrates the model we want every multi-round in-html
page to follow. It is **Avidor-specific on purpose** — get this one real, then
generalize into the skill.

## The idea in one line

The HTML page is **not** the memory and **not** a transcript. It is the agent's
*current understanding, re-materialized every turn*. The lossless memory lives in
`store/conversation.md`; the page is a fresh re-authoring of it.

- **Model** — `store/conversation.md`: the append-only, lossless record of every
  question and annotation across all rounds, with `descends-from:: / spawns:: /
  principle::` edges. Nothing here is shown to the user verbatim.
- **View** — `index.html`: round 3, re-derived from the store. Five regions, not
  forty Q&A blocks.
- **Delta** — `annotations.json`: the user's reactions to *this* view. Consumed
  each turn, folded into the store, then reset.

## The five regions of the view

1. **The story so far** — a short living recap, regenerated (not accreted) each
   turn, so the user re-enters the conversation in seconds.
2. **§1 Constitution** — the governing principles that *emerged* from the
   annotations and now overrule earlier drafts. The loudest region, because it's
   the most consequential thing this round produced. Each card is a whole-unit:
   hover and **Lock** to ratify, or Shift-click to push back.
3. **§2 Now** — the live frontier: exactly the items that need the user's input
   this turn. The "Next unanswered" pill walks these.
4. **§3 Settled** — where we've landed. Each settled thread shows only its head;
   the turns that got it there fold away behind a one-line disclosure.
5. **§4 Hold** — durable facts kept within reach (the winback funnel, the
   calibration datum).
6. **§5 Retired** — drafts tried in earlier rounds and cut, each with its cause
   of death, collapsed. One read away, never in the working column.

Only the principles and the frontier are marked `data-annotate-whole`, so the
verdict controls and the "Next unanswered" walk surface exactly what's being
asked this turn. Settled and reference content stays annotatable (Shift-click any
line to re-open a thread) but isn't solicited.

## What the agent re-authored this turn (the decision log)

Re-deriving round 3 from the store was not a render. The moves:

- **Promoted three principles** to a top-level constitution: only-estimate-what-
  you-control (P1), price-by-value-not-hours (P2), split-by-capability-tier (P3).
  They were born inside annotations (`draft-veto-table`, `draft-nightly-items`,
  `q2-milestone-split`), not stated as principles.
- **Retracted four of the agent's own earlier drafts** — the 38-hour pipeline
  table, the clock-stop clauses, the per-question cost numbers, the "doesn't suck"
  bar — moving them to tombstones *with the principle that killed each*.
- **Quarantined the WhatsApp/activation branch** as a different project, with a
  one-line scar so it can't drift back.
- **Re-coordinatized** milestones, acceptance, and cost onto the capability-tier
  axis the user invented in round 2.
- **Re-scheduled** the work: surfaced step-mapping as "do first" and marked the
  milestone split and the recount as blocked on it — the user edited the agenda,
  not just the content.
- **Surfaced a hidden risk** the rounds had under-addressed: the privacy/legal
  exposure, which round 2 only touched on the technical side.

## Run it

```bash
./setup.sh          # copies the layer-3 runtime files in, starts the server
# open http://127.0.0.1:8765/index.html
```

`setup.sh` copies the skill's canonical `style.css`, `interactions.js`,
`annotations.css`, `annotations.js`, and `annotation-writer.mjs` from
`../../scripts` (they're git-ignored here to stay canonical there).

## The round loop

1. The user reads the page and annotates (Shift-click a line; hover a whole-unit
   to set a verdict). Saves persist to `annotations.json`.
2. The user tells the agent to read the new annotations.
3. The agent folds them into `store/conversation.md` (append-only), then
   **re-authors** `index.html` from the whole store — promoting, retracting,
   quarantining, re-coordinatizing, re-scheduling as the meaning requires — and
   resets `annotations.json` for the next round.
