---
name: in-html
description: Build a reusable local HTML page for a CLI-agent review loop, with selectable boilerplate layers — styling, browser interactions, and optional Shift+click annotations persisted to JSON.
last_updated: 2026-06-21
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

The result must be a single self-contained HTML file — inline the CSS with `/Users/giladbarnea/.agents/skills/in-html/scripts/inline-css.py index.html style.css -o page.html`. Usually the user requests layer 1 to view the page on their iPhone; ask, and if yes, cp the output to `/Users/giladbarnea/Library/Mobile Documents/com~apple~CloudDocs/<domainful-name>.html` (iCloud-synced to the phone).

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

Then open `http://127.0.0.1:8765/index.html`. The server binds `0.0.0.0`, so the page also works from other devices on the same LAN/tailnet (e.g. `http://gilads-macbook-pro.taila610c4.ts.net:8765/` from the user's iPhone over Tailscale) — annotation saves included, since the template's `annotation-endpoint` meta is the relative `/annotations` and CORS accepts same-origin requests. If serving the page from a *separate* static server instead, run `node annotation-writer.mjs` too and set the meta to the absolute `http://127.0.0.1:8765/annotations` — the relative default would post to the wrong server.

## Design principles

### Mintlify docs contract

Layer 2 and 3 pages should feel like a small docs product, not an essay with sidebars. The shell already builds the Mintlify-style furniture — top bar, left section navigation, right “On this page”, tag legend, theme toggle — so do not hand-build chrome. What makes the page land is the first screen: an eyebrow or short `h1`, a direct `.sub`/`.lead`, `.stats` for the facts the reader needs at a glance, then one strong `.callout`, `.cardgroup`, or `.record` set. If the first viewport is only title + paragraphs, the factory did not do its job.

Use the provided classes as the visual vocabulary: `.record` for repeated proposals/findings, `.cardgroup` + `.card` for two to four overview ideas, `.gate` for one governing rule/test, `.callout` for one boxed judgment, `.stats` for quiet Mintlify-style metadata badges, and `table.data` only for row facts. Keep the page’s own structure to real `h2` sections; the shell reads those headings to build navigation. The style system supplies the Mintlify palette, spacing, code pills, card shadows, and dark-mode behavior — authors supply the information architecture.

The page's job is to install knowledge, not to restyle text. The source material was already prose; if the page renders the same facts as paragraphs inside prettier boxes, the reader still does all the extraction work and the transformation added nothing. Before authoring, identify the **shapes** hiding in the material and give each shape its native representation:

| Content shape | Representation |
| --- | --- |
| Actions, statuses, owners, open questions | `.tasks` status checklist |
| A set of proposals/findings, each with the same fields (rank, source, kind, score) | `.record` card |
| A magnitude, ranking, or score | `.meter` bar |
| A path with barriers (locks, approvals, hops, conversions) | `.chain` gate chain |
| Hierarchy, org chart, who-controls-what | `.tree` |
| Cause → cure, problem → owner, any A-maps-to-B relation | `.relmap` relation map |
| Process / sequence of stages | `.pipe` |
| Comparison, before/after, either/or | `.ba` panes, segmented tabs |
| Two versions of one text; exactly what changed | `.diff` line/word-level changeset (`diff_to_html.py`) |
| Asked → answered → replied (multi-round review loops) | `.qa` dialogue block |
| Line items, build-ups, per-row facts with numbers | `table.data` |
| Counts / status at a glance for a page header | `.stats` stat row |
| A jargon term that needs defining in place | `.term` glossary tooltip |
| Background, reference, "later" material | `.disclose`, collapsed |
| Insight, caveat, judgment, status | short prose, `aside.note`, `.callout` (semantic variants: note/tip/check/warning/danger) |

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

Edit `index.html` by replacing only the `CONTENT START` block with arbitrary page content. Keep the imports intact for the chosen layer set, including the small inline `<script>` in `<head>` — it picks a warm dark or light theme from the local time before first paint (the OS color-scheme setting is the fallback when JS is off). Theming is fully automatic across every layer; author content as usual and leave the colors alone.

At layers 2 and 3 the page is automatically wrapped in a three-pane docs frame — a top bar, a left section-nav, and a right "On this page" TOC — built by `interactions.js` from the page's `h2` headings, so give the page real `h2` sections and author nothing else for it. The frame collapses to a single column with a nav drawer on phones, fades its TOC out of the way whenever an annotation panel opens, and is absent at layer 1 (which stays a clean single column). A tag-filter legend, code-block copy buttons, and touch-tap glossary tooltips come with the same layer-2 set, also with no extra markup.

Use normal HTML first: `h1`, `.sub`, `.lead`, `h2`, `p`, `aside.note`, `.card`, `.callout`, `.grid`, `.pane`, `.row`, `.chip`, `.btn`, `.kbd`.

For ready-made components, read `/Users/giladbarnea/.agents/skills/in-html/scripts/components.md`. For a rendered reference, open `/Users/giladbarnea/.agents/skills/in-html/scripts/component-gallery.html` with the full layer set. To show exactly what changed between two versions of a text, don't hand-build it — generate the `.diff` component with `/Users/giladbarnea/.agents/skills/in-html/scripts/diff_to_html.py` (see the "Line / word-level diff" section of `components.md`).

Cross-references: never write a bare "§7", "Draft 2", or "the table above" — you know what it points to; the reader doesn't share your mental map of the page. Make every such mention a link: `<a href="#stable-name">§7</a>`. Every `data-annotation-id` doubles as a link target (`interactions.js` mirrors it into `id`), so important elements are already addressable; in layer 1 (no JS) write the `id` attribute on the target yourself. Internal links are styled automatically (no class needed), scroll smoothly, and flash the target on arrival; a "↩ Back to where you were" pill then returns the reader to their departure point (chained jumps unwind in order). A link whose target doesn't exist renders red with a console warning — fix it before shipping.

Multi-round loops: when a previous round's questions were answered via annotations, regenerate the page with the answered items as `.qa` dialogue blocks (question → reviewer's answer → your reply) and give new asks fresh `data-annotation-id`s — old JSON keys then stay harmlessly orphaned instead of colliding with new content.

When annotations are enabled, add `data-annotation-id="stable-name"` to important elements so JSON keys survive later edits. Without one, the key is a structural CSS path (tag + id + `:nth-of-type`, never classes) from the nearest `data-annotation-id` ancestor or `<body>` down to the element. Classes are visual/interaction state, not persistent identity. Add `data-annotate-whole` when Shift+click should annotate the whole box rather than a leaf text node. Bare clicks remain available for page interactions; annotations open with Shift+click. Elements with saved annotations get a subtle `※` marker; clicking the marker or Cmd+clicking the element toggles a styled preview beside the content column, and multiple previews can remain open. Bare Enter submits; modified Enter inserts a line break. Escape closes annotation UI. The editor can be dragged by the grip at its top (kept within the viewport) and grown from its bottom-right corner like a native textarea. Submitting reads the note back from disk and only confirms once the write is verified present. Saved notes are editable in place: clicking into a note's text inside a preview starts editing right at the click point. Each note carries a permanent Save / Revert / Delete row — Save and Revert sit inactive until the text differs from what's on disk (Enter saves, Escape reverts), while Delete is always live and removes the note from the JSON (the element's marker disappears with its last note). A deleted note stays in the open preview as a struck-through tombstone where only Revert is live: pressing it restores the annotations file exactly as it was the moment before the deletion (the undo lives only as long as the preview stays open). Saving replaces the note's text in place — its timestamp is its identity and stays unchanged — and every mutation, deletion and restoration included, is confirmed by read-back verification. A fixed "Next unanswered" pill in the corner walks downward through the whole-annotation units (`data-annotate-whole`, `.step`, `.bar`, `.record`, `.callout`, `.relrow`) that have no note yet — scrolling to the nearest one whose center sits below the viewport center and lighting the reticle on it, wrapping to the top once the walk runs out the bottom; it appears only when the page has such units, so "important enough to answer" tracks the same author markup the annotation engine already uses, not arbitrary elements. Each block you mark `data-annotate-whole` (such as a `.record` card) can also carry a one-word **verdict** for statements that invite agreement rather than a written reply. The verdict lives on the block's top-border rail beside the notes badge — never over content. On a hover-capable pointer it is revealed as a ghost split-button when the block is hovered (the primary side commits "Yes" or toggles it off; the caret opens the other mutually-exclusive choices, Agreed and Locked); on touch the same picker rides the tap action bar as a segmented control, while the rail shows a display-only pill. A committed verdict is always present as a solid checked pill on the rail. Unlike free-text notes, which accumulate, the verdict is single-valued and overwrites the previous one (kept in a separate `choice` field), so a block can hold many notes and exactly one verdict — and a block with a verdict counts as answered for the "Next unanswered" walk. (The component units pulled in automatically — `.step`, `.bar`, `.callout`, `.relrow` — and tables take notes only; the verdict is reserved for blocks you explicitly mark `data-annotate-whole`.)

Selecting text inside the annotated element before Shift+click, or drag-selecting it while the editor is open, captures that span alongside the note. The captured phrase is subtly highlighted in the page and shown in the editor as `↳ “selected text”`; only selections fully inside the annotated element are recorded.

Every layer adapts to touch screens on its own — same files, same markup rules, nothing extra to author. Tapping an element parks the highlight reticle on it and offers a single ✎ Annotate action whose label shows the existing note count when the element already carries annotations (viewing those notes is the ※ rail badge's job, as on desktop — the bar never shows a second button); the editor and note previews open as bottom sheets with explicit Save / Cancel / close buttons; a phrase selected by long-press while the editor is open is captured exactly like a desktop drag-selection.

Annotation JSON shape — each key maps to the element text plus the accumulated reviewer notes (re-annotating the same element appends rather than overwrites). Every note is an object carrying `userInput` and a local ISO 8601 `timestamp` with timezone offset (e.g. `+03:00` for IST); `specificallySelected` is present only when the reviewer had text selected. An optional `choice` object holds the single mutually-exclusive quick-answer (`value` + `timestamp`); it is overwritten on re-selection and dropped on clear, independent of `userInputs`:

```json
{
  "body > main > section#summary > div > p:nth-of-type(2)": {
    "text": "The element text",
    "userInputs": [
      {"userInput": "A note on the whole element", "timestamp": "2026-06-03T14:32:07+03:00"},
      {"userInput": "A note on a specific phrase", "specificallySelected": "the highlighted phrase", "timestamp": "2026-06-03T14:33:11+03:00"}
    ],
    "choice": {"value": "Agreed", "timestamp": "2026-06-03T14:34:02+03:00"}
  }
}
```
