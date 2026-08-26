---
last_updated: 2026-08-26 09:40
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

## Downloading an attached artifact (`sandbox:/...`) file

A share page embeds only the `sandbox:` link text, never the file bytes. Bytes are served per-conversation behind auth. Recipe (needs the logged-in debug Chrome on :9222):

```bash
# 1. Confirm a sandbox link exists + grab its path (anonymous):
uv run ~/.agents/skills/.agent-browser/scripts/chatgpt_share_to_markdown.py "<share-url>" | rg 'sandbox:/'
```

2. Get `conv_id` + the assistant `message_id` whose parts contain the link:
   - `curl -fsSL "https://chatgpt.com/share/<id>"` — parse the embedded payload.
   - If `/backend-api/conversation/<that id>` 404s (the share payload's `conversation_id`
     often does NOT work here), find the real id via authed
     `GET /backend-api/conversations?limit=100`, matched by title.
3. Two-hop fetch in one `Runtime.evaluate` (awaitPromise) inside any logged-in `chatgpt.com` tab:

```js
const token = (await fetch('/api/auth/session', {credentials:'include'})).json().accessToken;
const dl = await fetch(`/backend-api/conversation/${convId}/interpreter/download`
    + `?message_id=${msgId}&sandbox_path=${encodeURIComponent(sandboxPath)}`,
    {credentials:'include', headers:{Authorization:`Bearer ${token}`}})
  .then(r => r.json());                       // hop 1: returns {status, download_url}; Bearer REQUIRED even with cookies
const res = await fetch(dl.download_url, {credentials:'include'});   // hop 2: signed estuary URL, no auth needed
const buf = new Uint8Array(await res.arrayBuffer());
// base64 out in 0x8000 chunks, decode locally
```

4. Verify before writing: HTTP 200, plausible size, head matches expected content. Never write on non-200.
5. Missing/wrong ids → discover empirically: open `chatgpt.com/c/<convId>`, wait for the sentinel link text,
   enable Network, click `button[aria-label*="<link text>"]`, read the `interpreter/download` request
   off the wire — it carries both `message_id` and `sandbox_path`.
