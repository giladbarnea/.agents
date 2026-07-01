# X / Twitter threads

Goal: get the **full reply tree** of a post — every reply, not the handful an index surfaces.

Use `scripts/x_thread.mjs`. It calls x.com's internal `TweetDetail` GraphQL endpoint and paginates every cursor:

```bash
# with explicit cookies
AUTH_TOKEN=... CT0=... node scripts/x_thread.mjs <tweetId|url>

# or pull cookies from a logged-in debug Chrome over CDP (needs `ws`)
node scripts/x_thread.mjs <url> --from-chrome        # default port 9222
```

Output is a JSON array of `{id, username, name, text, likes, created}` on stdout; progress (`pages=… replies=…`) goes to stderr. Element `[0]` is the focal post; the rest are replies.

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
