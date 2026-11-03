# X / Twitter threads

Goal: get the **full reply tree** of a post — every reply, not the handful an index surfaces.

Use `scripts/x_thread.mjs`. It calls x.com's internal `TweetDetail` GraphQL endpoint and paginates every cursor:

```bash
# with explicit cookies
AUTH_TOKEN=... CT0=... node scripts/x_thread.mjs <tweetId|url>

# or pull cookies from a logged-in debug Chrome over CDP (needs `ws`)
node scripts/x_thread.mjs <url> --from-chrome        # default port 9222
```

`--from-chrome` imports the `ws` package. If it is missing, install `ws` beside the script; `npx -p ws` alone may still fail because ESM resolves imports from the script’s directory rather than npx’s transient executable path.

Output is a JSON array of `{id, username, name, text, likes, created}` on stdout; progress (`pages=… replies=…`) goes to stderr. Element `[0]` is the focal post; the rest are replies. Long Note posts may be truncated because the script currently reads `legacy.full_text`; when the focal text ends mid-sentence or at a stray `t.co` URL, read the rendered post in the logged-in browser or update the collector to prefer `note_tweet.note_tweet_results.result.text`.

## X Articles are not threads

A post whose only text is a `t.co` link may be an X Article (`https://x.com/i/article/<articleId>`), not a normal tweet/thread. `x_thread.mjs` will correctly fetch the focal post and replies, but it will not return the article body.

For an Article, drive a logged-in browser once and inspect the site's own GraphQL calls:

```bash
agent-browser connect 9222
agent-browser tab new
agent-browser open 'https://x.com/i/article/<articleId>'
agent-browser wait --load networkidle
agent-browser network requests --filter 'TweetResultByRestId'
```

Fetch that `TweetResultByRestId` URL with the normal X bearer token plus `auth_token`/`ct0` cookies. The Article body is structured Draft.js-like JSON at:

```text
data.tweetResult.result.article.article_results.result.content_state
```

Use `content_state.blocks` for text, headings, lists and blockquotes; `inlineStyleRanges` for bold/italic spans; `entityRanges` + `entityMap` for links, embedded tweets and media. Image URLs live under `article_results.result.media_entities[*].media_info.original_img_url`. Embedded tweets often need the `TweetResultsByRestIds` request the page also emits; prefer `note_tweet.note_tweet_results.result.text` over `legacy.full_text` because `legacy.full_text` can be truncated.

Fast fallback: `agent-browser get text 'body'` after opening the Article captures the visible article text, but it includes UI chrome and loses reliable links, embeds, image URLs and formatting. Use it only to confirm that the article loaded or when rough text is enough.

## Getting cookies

Two `x.com` cookies authorize everything: `auth_token` and `ct0`. Either paste them as env vars (browser devtools → Application → Cookies → x.com), or, if you're logged into x.com in a debug Chrome (`--remote-debugging-port=9222`), let `--from-chrome` read them via CDP `Storage.getCookies` (decrypted, no disk decryption). The cookies belong to a real account — treat them as secrets and don't commit them.

## The trade-off: internal endpoint vs. official API

There are two ways to read a thread, and they are **different tools**, not better/worse versions of one thing.

**`TweetDetail`** — the private, undocumented GraphQL endpoint x.com's own website calls to render a tweet page. You impersonate a logged-in browser with session cookies. This is what `x_thread.mjs` uses.

**Official X API v2** — the public, documented, contract-backed product. Bearer token / OAuth.

| | `TweetDetail` (internal) | Official API v2 |
|---|---|---|
| Reply coverage | Full tree, deep pagination (hundreds) | Search index only; ~40; 7-day window |
| Auth | Session cookies (a real account) | Bearer token / OAuth |
| Cost | Free | Paid tiers, tight rate limits |
| Stability | Can break anytime — unversioned, query IDs rotate | Versioned, stable contract |
| ToS | Gray area; looks like automation to X | Sanctioned |
| Account risk | Real — the account can get flagged | None |
| Output | Raw nested JSON you must parse | Clean documented schema |

**When to use which:** one-off deep reads where you need *every* reply and coverage beats durability → `TweetDetail` (this script). Anything production, recurring, or account-safety-sensitive → the official API.

That fragility is the price of the internal endpoint. The script pins a `QUERY_ID` and a `FEATURES` blob captured from a live request; when X rotates them you'll get HTTP 400/404. Refresh both from a real browser `graphql/.../TweetDetail` request — expected maintenance, not a bug.

## What a search-index fetch gives instead

A `conversation_id:<id>` search (e.g. the vendored bird-search client in the `last30days` skill) returns only indexed replies — typically the top ~40, and it lags for fresh or low-engagement replies. Fine for a quick read of the loudest replies; wrong tool if you need completeness or a specific reply that may not be indexed yet.

# Finding what an account said

The reply-tree script needs a post id. To learn what an account said about a topic across many posts, use the logged-in debug Chrome, with your own `--session` and `--pin-tab`.

## Read a profile and collect post ids

Open `https://x.com/<handle>`. `agent-browser get text main` reads the pinned and recent posts. To collect post URLs, for example the pinned one for `x_thread.mjs`, evaluate:

```js
Array.from(document.querySelectorAll('article a[href*="/status/"] time')).map(t => t.closest('a').href)
```

Post fields inside each `article`: `[data-testid=User-Name]` (its second line is the handle), `[data-testid=tweetText]`, and `time[datetime]`. On a post page, the focal post is `article[tabindex="-1"]`.

X unmounts posts that scroll off screen. Collecting once after scrolling misses the posts you scrolled past. Collect at every scroll step and dedupe. The `with_replies` tab also mixes in old posts, so prefer search.

## Advanced search

Run searches with operators in the logged-in browser:

```bash
scripts/x_search.sh 'from:herdrdev since:2026-10-28 (migrate OR sync OR sunset)'
scripts/x_search.sh 'from:herdrdev to:eitanpo'        # did the account answer this user?
scripts/x_search.sh 'from:herdrdev filter:replies since:2026-10-29' 8
scripts/x_search.sh 'rex herdr' 5 top                  # tab: live (default) or top
```

It prints `<datetime> <@handle> <Replying to ...> :: <text> :: <url>`, one line per post. Useful operators: `from:`, `to:`, `since:`/`until:`, `filter:replies`, `-filter:replies`, `( OR )`, and `"exact phrase"`. Keyword search misses paraphrases, typos and other languages.

## Grok

Grok (`https://x.com/i/grok`, "Grok" in the left sidebar) searches X semantically. It complements operator search; for thoroughness, do both.

- A free account offers only the Fast model. Choosing Auto or Expert redirects to the Premium sign-up page.
- Brief Grok like any fresh-context delegate: load the `ai-to-delegated` skill. State why you are asking and what you want to know. Do not hint at the answers you expect.
- Fill the "Ask anything" textbox, press Enter, and wait until the text of `main` stops growing. A first answer took about 35 seconds.
- To get an answer as markdown, click the response's own `Copy` button. It sits beside "Good response", while "Copy message" copies your prompt. Then run `pbpaste`. The click overwrites the user's clipboard. If that matters, save and restore the clipboard, or scrape the response element with `get text`, which loses links and tables. A Share button also exists.

In one test on whether an account planned to retire a product, Grok matched the operator-search conclusion. All 9 links it cited were real. It also found 4 on-topic user questions that keyword search had missed. It also missed a direct on-topic reply from the account and stated that the account had answered no one. Therefore verify every cited link, and check Grok's "nobody said X" claims with `from:<account> to:<user>` and `filter:replies`.

## Logged out

Use the logged-in browser whenever you can. Without login:

- `rf <post url>` returns a single post's text.
- `lightpanda fetch --dump markdown --wait-until networkidle https://x.com/<handle>` renders the profile timeline.
- Search, `with_replies`, and Grok redirect to the login page.

## Tabs and window focus

- A fresh `--pin-tab` session creates its own tab and raises Chrome to the front once. `tab new` raises it too. Later commands, including clicks and the Copy button, work while Chrome stays behind other windows.
- Without `--pin-tab`, `open` navigates one of the user's existing tabs.
- Binding a session to a tab created with `Target.createTarget` (`background: true`) still raises Chrome, through either `tab <targetId>` or a page-level WebSocket `connect`.
- If the user switches to another tab, the pinned tab becomes hidden and infinite scroll stops loading.
- `close` ends the session but leaves its tab open, so run `tab close` first. A session name remembers its tab after `close`; use a fresh session name for each run.
