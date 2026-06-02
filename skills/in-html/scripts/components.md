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
