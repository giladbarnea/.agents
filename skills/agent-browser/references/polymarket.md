# Polymarket Search

Goal: find every relevant bet (high recall) without drowning in keyword-coincidence hits (high precision). The relevant unit is the **event**, not the individual dated market — each event holds a full ladder of date-markets.

Two steps:

## 1. Discover events via the rendered search page

The gamma API `?search=` endpoint returns 403 — skip it.

Open `https://polymarket.com/search?q=<query>` (redirects to `/predictions?q=...`) and read `agent-browser get text body`. Do **not** filter DOM anchors by `innerText` — cards are icon links with empty anchor text, so the regex returns `[]`. If you need hrefs, filter anchors by href substring instead.

- The "*N* results" header is your recall gauge. If it says 101 and you've read 8 cards, you have a gap — keep reading until card relevance visibly tails off, and try one or two query variants. UI ranking is the only recall guarantee at this step; a relevant event ranked deep in the list is invisible to everything downstream.
- Most results are noise (keyword coincidence). Relevant events cluster as a small, consistently-named set. Collect their slugs from the card hrefs (`/event/<slug>`).

## 2. Extract each event by slug from the API

```
GET https://gamma-api.polymarket.com/events?slug=<slug>
```

Returns 200, no browser or cookies needed. One request gives the complete structured event: every date-laddered market — **including closed/resolved ones the UI hides behind "View resolved"** — with exact `outcomePrices`, `bestBid`/`bestAsk`, `lastTradePrice`, `volumeNum`. Recall within an event is then total; numbers are exact, not eyeballed off a card.

Per market, Yes probability = `outcomePrices[0]`; `closed: true` means resolved (`outcomePrices: ["0","1"]` → resolved No).

Use CDP browser-driving (below) only if the slug API starts 403-ing like search does.
