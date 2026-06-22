---
description: Ready-made copy-paste components for in-html pages, with layer requirements and markup.
last_updated: 2026-06-19 17:08
---

# in-html ready-made components

Use these snippets inside `<main class="col" id="content">`.

Layer guide:

1. Layer 1 (`style.css`) renders the visual shape, plus native interactive disclosure, step expansion, and segmented tabs (pure CSS, no JS).
2. Layer 2 (`interactions.js`) enables chip highlights and bar clicks.
3. Layer 3 (`annotations.css`, `annotations.js`, `annotation-writer.mjs`) enables Shift+click annotations.

All layers work with plain taps on touch screens; annotation gestures surface as a tap-summoned ✎ action bar and bottom sheets. Markup is identical.

## Mintlify opening screen

Requires layer 1. Use this shape for the first viewport of a docs-like page: short title, useful metadata, and two orientation cards. The layer-2/3 shell supplies the top bar, side nav, right TOC, theme toggle, and tag legend from headings and tags — do not author that chrome yourself.

```html
<span class="eyebrow">Harness review</span>
<h1>Meta-harness tuning</h1>
<p class="sub">What the run-set teaches about improving future runs without leaking answers.</p>
<div class="stats">
  <span class="stat"><b>8</b> runs</span>
  <span class="stat"><b>6</b> proposals</span>
  <span class="stat">all pass the gate</span>
</div>
<p class="lead">Two findings reframe the exercise.</p>
<div class="cardgroup">
  <div class="card lift">
    <div class="card-ic">◎</div>
    <h3>The harness teaches its own pitfalls</h3>
    <p>The repeated stumbles show where the map is teaching a bad habit.</p>
  </div>
  <div class="card lift">
    <div class="card-ic">✦</div>
    <h3>The best moves were mindsets</h3>
    <p>The behavior can be induced by better framing, not a bigger model.</p>
  </div>
</div>
```

## Gate / governing rule

Requires layer 1. Use for the one test that governs a page or a section.

```html
<div class="gate" data-annotate-whole data-annotation-id="overfit-gate">
  <div class="gate-head">Would this help an agent answering a different question? <span class="lbl">The test</span></div>
  <p>Yes means durable terrain or skill. Only helping this exact question means overfit.</p>
</div>
```

## Segmented toggle + content panels

Requires layer 1. Pure CSS via hidden radios + `:has()` (any 2022+ browser).

Each `.seg label` maps to the panel at the same position inside `.panels`. Mark one radio `checked` for the default. Give every group a unique `name`. Supports up to six panels.

```html
<div class="tabs">
  <div class="seg">
    <label><input type="radio" name="example-toggle" checked /><span>Option A</span></label>
    <label><input type="radio" name="example-toggle" /><span>Option B</span></label>
  </div>
  <div class="panels">
    <div class="qbox">
      <div class="qtext">Panel A text.</div>
      <span class="verdict ok">Good</span>
      <p>Explanation for A.</p>
    </div>
    <div class="qbox">
      <div class="qtext">Panel B text.</div>
      <span class="verdict no">Risk</span>
      <p>Explanation for B.</p>
    </div>
  </div>
</div>
```

Bare click switches panels. With layer 3, Shift+click annotates instead.

## Line / word-level diff

Requires layer 1. The native shape for **"what changed between these two texts"** — a precise line + intraline-word diff with a Side-by-side ↔ Unified toggle (pure CSS, the same `.seg` + `:has()` mechanism as the panels above), collapsible unchanged context, and change blocks that are `#`-addressable so **Prev / Next** are plain anchor jumps (no JS — works in iOS Quick Look). Reach for it over `.ba` panes whenever the comparison is two *versions of the same text* rather than two unrelated alternatives.

Don't hand-write the rows — **generate them**. The diff is mechanical; only the *meaning* of each change is yours:

```bash
# two files (to diff git revisions, materialize them first with `git show ref:path > /tmp/x`)
scripts/diff_to_html.py OLD NEW --left-label before --right-label after --id d1 > frag.html
# with annotations, and a unique id when a page holds more than one diff:
scripts/diff_to_html.py a.md b.md --id pricing --annotations notes.json
```

Paste the fragment into the `CONTENT` block, then inline `style.css` as usual. `--context N` sets how many unchanged lines stay inline before a run collapses into a `<details>`.

**Annotations** are an optional JSON list that tags change blocks. Match a block by 1-based change index (`n`) or by a `match` substring found anywhere in it; `tag` ∈ `blue` `amber` `green` `red` (reuses the `.tag` palette as the block's left-rail accent). The diff component invents nothing — supply the labels:

```json
[
  {"n": 1, "tag": "blue", "label": "META", "title": "Header sync", "note": "Why this block matters; <em>emphasis</em> allowed."},
  {"match": "recipes", "tag": "amber", "label": "DEBIAS", "note": "Matched by substring instead of index."}
]
```

Class anatomy, if you ever need to author or post-edit a block by hand: `.diff` wraps a `.diff-bar` (holds the `.seg.diff-view` toggle), a `.dcols` header (`.l`/`.r` labels), and `.diff-body`. Inside, each line is a `.drow` of two cells `.dc.l` / `.dc.r`; changed cells carry `.del` (red) or `.add` (green), an absent side is `.dc.empty` (hatched), and intraline spans are `.wd.del` / `.wd.add`. An annotated change is a `<section class="dchange {tag}" id="{id}-c{n}">` with a `.dhead` and a `.dnav` (Prev/All/Next anchors). Unchanged runs collapse inside `<details class="dctx">`. Narrow screens fold to the unified stacked form automatically.

## Chip toggle + highlights/notes

Requires layers 1+2.

```html
<div class="row" data-chip-toggle data-scope="#chip-demo">
  <span class="chip q" data-key="city">“city center”</span>
  <span class="chip q" data-key="energy">“energy sector”</span>
</div>

<div id="chip-demo" class="ba">
  <div class="pane">
    <h4><span>Raw text</span><span>literal</span></h4>
    <p>Rothschild 22, Tel Aviv. Tenant: Sonol.</p>
    <div class="nomatch" data-chip-target="city">
      ✗ “city center” is not explicit.
    </div>
    <div class="nomatch" data-chip-target="energy">
      ✗ “energy sector” is not explicit.
    </div>
  </div>
  <div class="pane">
    <h4><span>Generated profile</span><span>conceptual</span></h4>
    <p>
      <span class="hl" data-chip-target="city"
        >central Tel Aviv, a city-center location</span
      >.
      <span class="hl" data-chip-target="energy"
        >Sonol, an energy-sector company</span
      >.
    </p>
    <div class="matchnote" data-chip-target="city energy">
      ✓ Said out loud in the profile.
    </div>
  </div>
</div>
```

Targets with class `.hl` receive `.lit`; other `[data-chip-target]` elements receive `.show`. Override with `data-active-class="..."`.

## Disclosure

Requires layer 1. Native `<details>`/`<summary>` — collapses and expands with no JS.

```html
<details class="disclose" data-annotate-whole>
  <summary class="head"><span class="tri">▸</span> Click to expand</summary>
  <div class="body">
    <p>Hidden body.</p>
  </div>
</details>
```

## Step pipeline

Requires layer 1. Each step is a native `<details>`; the always-visible label goes in `<summary>`, the detail in `.d`. Add `open` to a step to start it expanded.

```html
<div class="pipe">
  <details class="step" data-annotate-whole>
    <summary>
      <div class="k">STEP 1</div>
      <div class="t">Parse intent</div>
    </summary>
    <div class="d">Long detail shown only after click.</div>
  </details>
  <details class="step hot" data-annotate-whole>
    <summary>
      <div class="badge">key</div>
      <div class="k">STEP 2</div>
      <div class="t">Judge candidates</div>
    </summary>
    <div class="d">The important step.</div>
  </details>
</div>
```

Bare click on the summary expands the step. With layer 3, Shift+click annotates the whole step instead.

## Click-to-compile bar chart

Requires layers 1+2.

```html
<div class="dist" data-bar-compile data-compiled-prefix="Compiled hot paths: ">
  <div class="bars">
    <div class="bar" data-axis="date" style="height: 140px"></div>
    <div class="bar" data-axis="client" style="height: 118px"></div>
    <div class="bar" data-axis="sector" style="height: 96px"></div>
    <div class="bar" style="height: 40px; opacity: 0.55"></div>
    <div class="bar" style="height: 28px; opacity: 0.55"></div>
  </div>
  <div class="axislabels">
    <span>← recurring head</span><span>long tail →</span>
  </div>
  <div class="band">The default path covers the whole curve.</div>
  <div class="compiledList" data-compiled-list></div>
</div>
```

Bars with `data-axis` or `data-label` are clickable. Other bars render as inert visual tail bars.

## Gap visual

Requires layer 1 only.

```html
<div class="gap">
  <div class="side">
    <h4>Input</h4>
    <span class="v">raw text</span>
  </div>
  <div class="mid">
    <span class="arrow">→</span><span class="lbl">night,<br />cheap model</span>
  </div>
  <div class="side">
    <h4>Output</h4>
    <span class="v">profile</span><span class="v">embedding</span>
  </div>
</div>
```

## Schema/chip box

Requires layer 1 only.

```html
<div class="schemaBox">
  <span class="chip field">client_sector</span>
  <span class="chip field">location_character</span>
</div>
<p class="qline">
  <span class="counter">#1</span> A question ⇒
  <span class="imp">needs field_name</span>
</p>
```

## Status checklist

Requires layer 1 only. The opening section of any status/brief page: one row per item, each with a state badge. States: `wait` (blue — blocked on someone else), `act` (amber — the reader's move), `flag` (red — open question or risk), `done` (green), `dim` (gray — deferred/later). Badge text is free-form; the class only sets the color.

```html
<ol class="tasks">
  <li>
    <span class="state wait">waiting</span>
    <div><strong>Vendor sends credentials</strong> — promised today; chase if late.</div>
  </li>
  <li>
    <span class="state act">your move</span>
    <div><strong>Forward credentials to ops</strong> and request the copy.</div>
  </li>
  <li>
    <span class="state flag">open question</span>
    <div><strong>Which path is real?</strong> Two sources disagree.</div>
  </li>
  <li>
    <span class="state dim">later</span>
    <div><strong>Identify the file format</strong> once it arrives.</div>
  </li>
</ol>
```

## Gate chain

Requires layer 1 only. A path through nodes with barriers between them — locks, approvals, network hops, format conversions. Each `.cgate` names the barrier, who holds its key, and its state: `open` (green), `shut` (red), or no class (neutral). Alternate `.cnode` and `.cgate` freely; nodes flex, gates are fixed-width. Stacks vertically on narrow screens.

```html
<div class="chain">
  <div class="cnode">
    <h4>Your laptop</h4>
    <p>Where the file must land.</p>
  </div>
  <div class="cgate shut">
    <span class="gicon">🔒</span>
    <span class="gname">Network gate</span>
    <span class="gwho">key: ops → host</span>
    <span class="gstate">shut — no route</span>
  </div>
  <div class="cnode">
    <h4>Server</h4>
    <p>Holds the artifact; not publicly routable.</p>
  </div>
  <div class="cgate open">
    <span class="gicon">🔓</span>
    <span class="gname">Permission gate</span>
    <span class="gwho">key: vendor</span>
    <span class="gstate">opening today</span>
  </div>
  <div class="cnode">
    <h4>The artifact</h4>
    <p>Readable only with the vendor's credentials.</p>
  </div>
</div>
```

## Tree

Requires layer 1 only. Hierarchies, org charts, who-controls-what. Rows of nodes joined by connector pieces: `.tstem` (vertical line), `.tsplit` (one parent fans out to two children), `.tjoin` (two parents merge into one child). `.trow.two` holds two siblings with an optional `.tnote` between them (add `.bad` to color it as a warning, e.g. "don't know each other"). `.tag` pills (`blue`/`amber`/`green`/`red`) mark layers or categories — reuse the same tag colors elsewhere on the page to cross-reference.

```html
<div class="tree">
  <div class="trow">
    <div class="tnode">
      <h4>Client</h4>
      <p>Contracted both vendors separately.</p>
    </div>
  </div>
  <div class="tstem"></div>
  <div class="tsplit"></div>
  <div class="trow two">
    <div class="tnode">
      <h4>Vendor A <span class="tag blue">machine layer</span></h4>
      <p>Administers the box. Can't touch the app's files.</p>
    </div>
    <div class="tnote bad">don't know<br />each other</div>
    <div class="tnode">
      <h4>Vendor B <span class="tag amber">file layer</span></h4>
      <p>Owns the app and its files. No admin access to the box.</p>
    </div>
  </div>
  <div class="tjoin"></div>
  <div class="tstem"></div>
  <div class="trow">
    <div class="tnode">
      <h4>The box</h4>
      <p>One machine, two controllers on different layers.</p>
    </div>
  </div>
</div>
```

## Dialogue / Q&A exchange

Requires layer 1 only. The native shape for **multi-round review loops**: a question the agent asked, the reviewer's answer (harvested from `annotations.json`), and the agent's reply on top. Use it when regenerating a page whose previous round was answered via annotations — answered questions become closed `.qa` blocks instead of open asks, and the conversation evolves in place.

Speaker labels default to "YOU" (`.ans`) and "ME" (`.resp`); override with `data-speaker`. Add `dir="auto"` on `.ans` when answers may be RTL. Follow-up questions nest naturally as a `.tasks` list inside the block.

```html
<div class="qa" data-annotate-whole data-annotation-id="a-topic">
  <p class="q">The question as originally asked, condensed.</p>
  <div class="ans" dir="auto">The reviewer's answer, quoted or lightly trimmed.</div>
  <p class="resp">The agent's reply: what this settles, what it implies.</p>
  <ol class="tasks" style="margin:0.6rem 0 0">
    <li data-annotate-whole data-annotation-id="q2-topic-followup">
      <span class="state act">answer</span>
      <div><strong>Optional follow-up question</strong> raised by the answer.</div>
    </li>
  </ol>
</div>
```

## Data table

Requires layer 1 only. For line items, build-ups, and per-row facts with numbers — estimates × hours, party × risk × move, cohort funnels. `td.num` right-aligns with tabular numerals; `tr.total` draws a summing rule. Headers/cells use logical alignment (`text-align: start/end`), so RTL works.

```html
<table class="data" data-annotate-whole data-annotation-id="buildup">
  <tr><th>work item</th><th class="num">hours</th></tr>
  <tr><td>First line item</td><td class="num">38</td></tr>
  <tr><td>Second line item</td><td class="num">20</td></tr>
  <tr class="total"><td>Total</td><td class="num">58</td></tr>
</table>
```

## Semantic callouts

Requires layer 1. An icon-led tinted box for a single insight, caveat, or status. The variant sets the hue and the icon; the default (no variant) uses the page accent. The icon is a CSS glyph — nothing to author beyond the class, and it renders offline. `good` and `bad` remain as aliases for `check` and `danger`.

```html
<div class="callout note">A neutral note worth keeping in mind.</div>
<div class="callout tip">A helpful suggestion.</div>
<div class="callout check">Confirmation that something holds.</div>
<div class="callout warning">Something to watch out for.</div>
<div class="callout danger">This will break things.</div>
<div class="callout">Default — the gold-accented generic callout.</div>
```

## Record card

Requires layer 1. The native shape for a set of structured proposals or findings — each a record with typed fields (rank, source, kind, magnitude, evidence, links) rather than a paragraph. Reach for it whenever the material is "several items, each with the same handful of attributes." Pair the leverage slot with `.meter`; mark the card `data-annotate-whole` for layer 3. Drop `hot` for a non-emphasized record, and keep only the fields a record actually has.

```html
<div class="record hot" data-annotate-whole data-annotation-id="tweak-rollup">
  <div class="rec-head">
    <span class="rec-rank">1</span>
    <div class="rec-main">
      <div class="rec-eyebrow"><span class="rec-file">orient.py</span><span class="tag blue">method</span></div>
      <div class="rec-title">Qualify the rollup endorsement</div>
    </div>
    <div class="rec-lev">
      <div class="rec-lev-lbl">Leverage</div>
      <div class="meter"><i style="width:96%"></i></div>
    </div>
  </div>
  <div class="rec-body">Coalesce across the rollup, till date, and order date; never read the rollup alone.</div>
  <div class="rec-props">
    <span class="rec-prop"><span class="k">Evidence</span><b>≥5 runs</b></span>
    <span class="rec-prop"><span class="k">Cures</span><a href="#pit-rollup">rollup raggedness</a></span>
  </div>
</div>
```

## Meter

Requires layer 1. A magnitude bar for a ranked or scored value — leverage, priority, confidence. The inner `<i>` width encodes the value. For inline use, set `display:inline-block;width:120px;vertical-align:middle` on the `.meter`.

```html
<div class="meter"><i style="width:72%"></i></div>
```

## Glossary term

Requires layer 1 for the hover tooltip; touch-tap support is layer 2. An inline definition for a jargon term, shown in place without a glossary detour. The `tabindex` makes it keyboard-reachable.

```html
the <span class="term" tabindex="0">rollup<span class="tip">A pre-aggregated per-customer summary table — trustworthy in total, not row-complete.</span></span> is fast but ragged
```

## Relation / cure map

Requires layer 1. A pure-CSS map of left-item → right-item relations — cause→cure, problem→owner, any A-maps-to-B set. Pure CSS rather than a diagram engine, so it survives layer 1 and iOS Quick Look; it stacks on narrow screens. Wire the reciprocal links to the records or pitfalls it connects so the relation is navigable in both directions.

```html
<div class="relmap">
  <div class="relrow">
    <div class="rel-from"><span class="tag red">induced</span> Rollup-alone raggedness</div>
    <div class="rel-arrow">→</div>
    <div class="rel-to"><span class="k">cured by</span><a href="#tweak-rollup">Tweak #1 · qualify the rollup</a></div>
  </div>
</div>
```

## Stat row

Requires layer 1. A row of compact Mintlify-style `Badge shape="pill"` metadata — counts, dates, status at a glance. Use it for facts, not controls; interactive switches belong in segmented tabs or `.chip.q` toggles.

```html
<div class="stats">
  <span class="stat"><b>8</b> runs</span>
  <span class="stat"><b>6</b> tweaks</span>
  <span class="stat">all pass the gate</span>
</div>
```
