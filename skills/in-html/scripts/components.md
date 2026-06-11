# in-html ready-made components

Use these snippets inside `<main class="col" id="content">`.

Layer guide:

1. Layer 1 (`style.css`) renders the visual shape, plus native interactive disclosure, step expansion, and segmented tabs (pure CSS, no JS).
2. Layer 2 (`interactions.js`) enables chip highlights and bar clicks.
3. Layer 3 (`annotations.css`, `annotations.js`, `annotation-writer.mjs`) enables Shift+click annotations.

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
