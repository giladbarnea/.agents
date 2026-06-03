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

Use when the page must render without JavaScript. Disclosure, step expansion, and segmented tabs are still interactive here — they run on pure CSS (`<details>` and `:has()`). Only chip highlights and bar clicks need layer 2.

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

## Authoring rules

Edit `index.html` by replacing only the `CONTENT START` block with arbitrary page content. Keep the imports intact for the chosen layer set.

Use normal HTML first: `h1`, `.sub`, `.lead`, `h2`, `p`, `aside.note`, `.card`, `.callout`, `.grid`, `.pane`, `.row`, `.chip`, `.btn`, `.kbd`.

For ready-made components, read `/Users/giladbarnea/.agents/skills/in-html/scripts/components.md`. For a rendered reference, open `/Users/giladbarnea/.agents/skills/in-html/scripts/component-gallery.html` with the full layer set.

When annotations are enabled, add `data-annotation-id="stable-name"` to important elements so JSON keys survive later edits. Without one, the key is a unique, descriptive CSS path (tag + id + classes + `:nth-of-type`) from the nearest `data-annotation-id` ancestor or `<body>` down to the element, so you can tell where it lives in the page. Add `data-annotate-whole` when Shift+click should annotate the whole box rather than a leaf text node. Bare clicks remain available for page interactions; annotations open with Shift+click. Elements with saved annotations get a subtle `※` marker; clicking the marker or Cmd+clicking the element toggles a styled preview beside the content column, and multiple previews can remain open. Bare Enter submits; modified Enter inserts a line break. Escape closes annotation UI.

Selecting text inside the annotated element before Shift+click, or drag-selecting it while the editor is open, captures that span alongside the note. The captured phrase is subtly highlighted in the page and shown in the editor as `↳ “selected text”`; only selections fully inside the annotated element are recorded.

Annotation JSON shape — each key maps to the element text plus the accumulated reviewer notes (re-annotating the same element appends rather than overwrites). A note is a plain string, or an object when the reviewer had text selected:

```json
{
  "body > main.wrap > section#summary > div.card > p:nth-of-type(2)": {
    "text": "The element text",
    "userInputs": [
      "A note on the whole element",
      {"userInput": "A note on a specific phrase", "specificallySelected": "the highlighted phrase"}
    ]
  }
}
```
