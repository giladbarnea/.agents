# Annotation note editing (Layer 3) — implementation notes

Date: 2026-06-12 · Files: `scripts/annotations.js`, `scripts/annotations.css`, `scripts/annotation-writer.mjs`, `SKILL.md`

The ask: notes inside an open annotation preview become editable on click, with the caret landing
where the user clicked, and Save/Revert controls appearing only once the text actually differs
from what's on disk.

Decisions and why:

1. **Always-on `contenteditable="plaintext-only"`** on the note paragraph, instead of a
   click-to-arm step. The browser places the caret at the click point natively, which removed any
   need for `caretRangeFromPoint` bookkeeping. The ignored-elements selector already excluded
   `[contenteditable]` and `.annotation-preview`, so the Shift+click/Cmd+click machinery needed no
   changes to coexist.
2. **The note's `timestamp` is its identity.** It was already unique per submit (used for write
   read-back verification), so edits are a `PUT` of `{selector, timestamp, userInput}` that
   replaces text in place and never touches the timestamp. Legacy string-form notes have no
   timestamp and deliberately stay read-only. A non-matching timestamp 404s — no upsert.
3. **Same trust chain as creation:** save goes write → read-back → only then update in-memory
   state, reusing `annotationWasPersisted` unchanged since it matches on text + timestamp.
4. Keyboard semantics mirror the editor (Enter saves, Escape reverts); the note's Escape stops
   propagation so it doesn't bubble into the document-level "close all previews" handler.

Verification was browser-driven (agent-browser) against a real server: caret-at-click was proven
by text inserting mid-note, plus dirty-toggle, revert, save-to-disk, both themes, and a
no-regression pass on annotation creation. One trap worth remembering: `component-gallery.html`
hardcodes its `annotation-endpoint` meta to port 8765, so a test server on another port silently
reads a *different* session's annotations — point the meta at the relative `/annotations` when
testing a copy.

A parallel effort adds mobile analogues for Shift/Cmd+click on `main`; this feature touches the
preview's internals and the server, not the click bindings, so the eventual merge should be clean.
