---
name: in-html
description: Build a reusable local HTML page for a CLI-agent review loop, with selectable boilerplate layers — styling, browser interactions, and optional Shift+click annotations persisted to JSON.
---

# in-html

Use this skill when the user wants an answer or artifact as a local HTML page. Choose only the layers the current environment can support.

Native HTML can import CSS and JavaScript, but not useful HTML partials. The old HTML Imports feature is dead; iframes import whole pages; `fetch()`-based partials require JavaScript. So this skill keeps small HTML shells and modularizes the CSS/JS around them. If the delivery channel truly supports only one physical HTML file, inline the chosen CSS/JS into `<style>` / `<script>` tags instead of linking external files.

## Layer choice

- If JavaScript is unsupported, read `template-style.html` and `style.css`; create self-contained HTML.
- If local writes / Node are unsupported, read `template-interactive.html`, `style.css`, and `interactions.js`; create self-contained HTML.
- If local Node is available, read `template.html`, `style.css`, `interactions.js`, `annotations.css`, `annotations.js`, and `annotation-writer.mjs`.

### Layer 1: style only

Use when the page must render without JavaScript. Disclosure, step expansion, and segmented tabs are still interactive here — they run on pure CSS (`<details>` and `:has()`). Only chip highlights and bar clicks need layer 2. layer 1 result has to be a single self-contained HTML file. Usually when the user requests layer 1, they want to view it on their iPhone. Ask whether to do it and if yes, cp the HTML into '/Users/giladbarnea/Library/Mobile Documents/com~apple~CloudDocs/'

```bash
workdir=$(mktemp -d)
cp /Users/giladbarnea/.agents/skills/in-html/templates/template-style.html "$workdir/index.html"
cp /Users/giladbarnea/.agents/skills/in-html/scripts/style.css "$workdir/"
cd "$workdir"
```

Ship a single self-contained file by inlining the CSS: `./scripts/inline-css.py index.html style.css -o page.html`. Usually the user will want the output page synced into iCloud, at `~/Library/Mobile Documents/com~apple~CloudDocs/<domainful-name>.html`.

### Layers 1+2: style plus interactions

Use when JavaScript works, but filesystem writes / Node server are unavailable.

```bash
workdir=$(mktemp -d)
cp /Users/giladbarnea/.agents/skills/in-html/templates/template-interactive.html "$workdir/index.html"
cp /Users/giladbarnea/.agents/skills/in-html/scripts/style.css "$workdir/"
cp /Users/giladbarnea/.agents/skills/in-html/scripts/interactions.js "$workdir/"
cd "$workdir"
```

### Layers 1+2+3: full annotated review page

Use when a local Node process can run.

```bash
workdir=$(mktemp -d)
cp /Users/giladbarnea/.agents/skills/in-html/templates/template.html "$workdir/index.html"
cp /Users/giladbarnea/.agents/skills/in-html/scripts/style.css "$workdir/"
cp /Users/giladbarnea/.agents/skills/in-html/scripts/interactions.js "$workdir/"
cp /Users/giladbarnea/.agents/skills/in-html/scripts/annotations.css "$workdir/"
cp /Users/giladbarnea/.agents/skills/in-html/scripts/annotations.js "$workdir/"
cp /Users/giladbarnea/.agents/skills/in-html/scripts/annotation-writer.mjs "$workdir/"
cd "$workdir"
node annotation-writer.mjs
```

Then open `http://127.0.0.1:8765/index.html`. If using a separate static server, run `node annotation-writer.mjs` too; annotation writes still post to `http://127.0.0.1:8765/annotations`.

## Design principles

The page's job is to install knowledge, not to restyle text. The source material was already prose; if the page renders the same facts as paragraphs inside prettier boxes, the reader still does all the extraction work and the transformation added nothing. Before authoring, identify the **shapes** hiding in the material and give each shape its native representation:

| Content shape | Representation |
| --- | --- |
| Actions, statuses, owners, open questions | `.tasks` status checklist |
| A path with barriers (locks, approvals, hops, conversions) | `.chain` gate chain |
| Hierarchy, org chart, who-controls-what | `.tree` |
| Process / sequence of stages | `.pipe` |
| Comparison, before/after, either/or | `.ba` panes, segmented tabs |
| Asked → answered → replied (multi-round review loops) | `.qa` dialogue block |
| Line items, build-ups, per-row facts with numbers | `table.data` |
| Background, reference, "later" material | `.disclose`, collapsed |
| Insight, caveat, judgment | short prose, `aside.note`, `.callout` |

Prose is the fallback for what genuinely has no shape — insights, caveats, synthesis — not the default.

1. Order by reader need: actions and answers first, the explanatory model second, reference material last and collapsed. Don't make the reader scroll past theory to find their next move.
2. State each fact exactly once, in its best representation. If the same fact appears in two sections, one of them is the wrong representation — cut it from there. Target roughly a third of the source's word count.
3. Encode state and urgency visually — state badges, gate colors, verdicts — never only in words. A status page where everything looks equally calm has failed.
4. Disclosure polarity: collapse background and reference; never collapse operationally critical content. `open`-by-default is reserved for what the reader needs right now.
5. Interaction must pay for itself: a click should reveal something the reader didn't need before clicking. Highlighting prose the reader must read anyway is decoration — omit it.
6. The visually loudest element must be the most consequential one. Audit every `hot`, badge, and accent: does emphasis track importance?
7. Don't force the densest content into the narrowest container, and don't let one section mix timescales or audiences (now vs. later, action vs. reference) — split it instead.
8. The installation test, before shipping: after a 30-second read, could the reader redraw the diagrams and recite the next actions from memory? If a section only re-reads well rather than recalls well, reshape it.

## Authoring rules

Edit `index.html` by replacing only the `CONTENT START` block with arbitrary page content. Keep the imports intact for the chosen layer set.

Use normal HTML first: `h1`, `.sub`, `.lead`, `h2`, `p`, `aside.note`, `.card`, `.callout`, `.grid`, `.pane`, `.row`, `.chip`, `.btn`, `.kbd`.

For ready-made components, read `/Users/giladbarnea/.agents/skills/in-html/scripts/components.md`. For a rendered reference, open `/Users/giladbarnea/.agents/skills/in-html/scripts/component-gallery.html` with the full layer set.

Cross-references: never write a bare "§7", "Draft 2", or "the table above" — you know what it points to; the reader doesn't share your mental map of the page. Make every such mention a link: `<a href="#stable-name">§7</a>`. Every `data-annotation-id` doubles as a link target (`interactions.js` mirrors it into `id`), so important elements are already addressable; in layer 1 (no JS) write the `id` attribute on the target yourself. Internal links are styled automatically (no class needed), scroll smoothly, and flash the target on arrival. A link whose target doesn't exist renders red with a console warning — fix it before shipping.

Multi-round loops: when a previous round's questions were answered via annotations, regenerate the page with the answered items as `.qa` dialogue blocks (question → reviewer's answer → your reply) and give new asks fresh `data-annotation-id`s — old JSON keys then stay harmlessly orphaned instead of colliding with new content.

When annotations are enabled, add `data-annotation-id="stable-name"` to important elements so JSON keys survive later edits. Without one, the key is a structural CSS path (tag + id + `:nth-of-type`, never classes) from the nearest `data-annotation-id` ancestor or `<body>` down to the element. Classes are visual/interaction state, not persistent identity. Add `data-annotate-whole` when Shift+click should annotate the whole box rather than a leaf text node. Bare clicks remain available for page interactions; annotations open with Shift+click. Elements with saved annotations get a subtle `※` marker; clicking the marker or Cmd+clicking the element toggles a styled preview beside the content column, and multiple previews can remain open. Bare Enter submits; modified Enter inserts a line break. Escape closes annotation UI. The editor can be dragged by the grip at its top (kept within the viewport) and grown from its bottom-right corner like a native textarea. Submitting reads the note back from disk and only confirms once the write is verified present.

Selecting text inside the annotated element before Shift+click, or drag-selecting it while the editor is open, captures that span alongside the note. The captured phrase is subtly highlighted in the page and shown in the editor as `↳ “selected text”`; only selections fully inside the annotated element are recorded.

Annotation JSON shape — each key maps to the element text plus the accumulated reviewer notes (re-annotating the same element appends rather than overwrites). Every note is an object carrying `userInput` and a local ISO 8601 `timestamp` with timezone offset (e.g. `+03:00` for IST); `specificallySelected` is present only when the reviewer had text selected:

```json
{
  "body > main > section#summary > div > p:nth-of-type(2)": {
    "text": "The element text",
    "userInputs": [
      {"userInput": "A note on the whole element", "timestamp": "2026-06-03T14:32:07+03:00"},
      {"userInput": "A note on a specific phrase", "specificallySelected": "the highlighted phrase", "timestamp": "2026-06-03T14:33:11+03:00"}
    ]
  }
}
```
