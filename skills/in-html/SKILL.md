---
name: in-html
description: Build a reusable local interactive HTML page, usually for a CLI-agent review loop, with Tufte-ish styling and optional Shift+click annotations persisted to JSON.
---

# in-html

Use this skill when the user wants an answer or artifact as an interactive local HTML page. Prefer the reusable template; do not start from a content-specific demo unless the user explicitly asks for that demo.

## Fast path

```bash
workdir=$(mktemp -d)
cp /Users/giladbarnea/.agents/skills/in-html/scripts/template.html "$workdir/index.html"
cp /Users/giladbarnea/.agents/skills/in-html/scripts/annotation-writer.mjs "$workdir/"
cd "$workdir"
```

Edit `index.html` by replacing only the `CONTENT START` block with the page body. Keep the style and script boilerplate intact.

Then run either one local server:

```bash
node annotation-writer.mjs
```

and open `http://127.0.0.1:8765/index.html`; or, if the user specifically wants `serve`, run the writer and static server separately:

```bash
node annotation-writer.mjs &
npx -y serve .
```

The template posts annotation writes to `http://127.0.0.1:8765/annotations` and the writer merges them into `annotations.json` by default. Override with `PORT=...`, `SERVE_DIR=...`, or `ANNOTATIONS_FILE=...`; if `PORT` changes, update the template’s `<meta name="annotation-endpoint">` too.

## Authoring rules

1. Put arbitrary content inside `<main class="col" id="content">`. The content can be completely unrelated to any previous page.
2. Use normal HTML first: `h1`, `.sub`, `.lead`, `h2`, `p`, `aside.note`, `.card`, `.callout`, `.grid`, `.pane`, `.row`, `.chip`, `.btn`, `.kbd`.
3. Add `data-annotation-id="stable-name"` to important elements so JSON keys survive later edits. Without it, the script generates a CSS selector.
4. Add `data-annotate-whole` to a component when Shift+click should annotate the whole box rather than a leaf text node.
5. Bare clicks remain available for page interactions. Annotations open with Shift+click. Bare Enter submits; modified Enter inserts a line break. Escape closes the input.
6. Richer progressive-disclosure mechanics are intentionally minimal for now. The template includes only a small `.disclose` expand/collapse handler.

Annotation JSON shape:

```json
{
  "[data-annotation-id=\"some-element\"]": {
    "text": "The element text",
    "userInput": "The reviewer note"
  }
}
```
