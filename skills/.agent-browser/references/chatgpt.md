---
last_updated: 2026-07-20 15:35
---
# ChatGPT shared conversations → Markdown

For a public `https://chatgpt.com/share/<id>` link, skip the browser and run:

```bash
scripts/chatgpt_share_to_markdown.py "https://chatgpt.com/share/<id>" > conversation.md
```

The share page is a lazy-hydrated SPA, so `agent-browser open`/`read` returns only the
sidebar, not the transcript. The script instead parses the server-rendered payload embedded
in the page and needs no auth or tab driving.

## Decision graph

The script is data-driven, not mode-driven — nothing is sniffed, every branch reads a field the
payload already declares:

- **Which messages are visible** — walk parents from `current_node` to the root. Skip the root
  (the node whose `message` is null). Drop `system`/`tool` roles and internal assistant content
  (`thoughts`, `code`, `reasoning_recap`); keep `user`/`assistant` text.
- **How each message part renders** — dispatch on the part's own `content_type`: a plain string
  is text, `audio_transcription` contributes its `.text` (voice chats), `image_asset_pointer`
  becomes an attachment note.
- **Inline UI tokens inside text** — ChatGPT embeds citations and interactive widgets as
  private-use-delimited spans (`U+E200 type U+E202 payload U+E201`). A `genui` widget collapses to
  a titled placeholder; a `cite` token becomes `[cite: [source](url), ...]`, its sources read from
  the message's `content_references` (keyed by the token's `matched_text`); other tokens drop out.
  Delimiters are exact codepoints, so this is parsed, not guessed.

So a text chat, a voice chat, an image chat, and one with interactive visualizations all flow
through the same code; the shape is read off the data, never guessed. The script fails loud on
malformed structure rather than emitting a partial transcript.
