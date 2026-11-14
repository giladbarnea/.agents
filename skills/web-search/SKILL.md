---
name: web-search
description: Web search via Perplexity, Google results (Serper, SerpAPI) and Exa
argument-hint: query
---

# Web Search

Search using Perplexity AI through OpenRouter first.

## Usage

```bash
./scripts/perplexity_search.py "your search query"
./scripts/perplexity_search.py "query" --model sonar-pro-search
```

The script first uses `OPENROUTER_API_KEY` or `~/.openrouter-gilad-barnea-api-key`.

If OpenRouter fails, it uses `PERPLEXITY_API_KEY` or `~/.perplexity-api-key` with the Perplexity API.

If both fail, use Brave Search with `~/.brave-search-api-key`.

Pitfall: Perplexity gives a synthesized answer, not Google's ranking. Its counts and numbers can differ from the source page.

## Google results: Serper and SerpAPI

Use these when you need real Google organic results in order. Key files: `~/.serper-api-key` (Serper) and `~/.serp-api-key` (SerpAPI; it holds the SerpAPI key despite its name).

```bash
# Serper
curl -s -X POST https://google.serper.dev/search \
  -H "X-API-KEY: $(cat ~/.serper-api-key)" -H 'Content-Type: application/json' \
  --data-raw '{"q":"your query","num":8,"gl":"us","hl":"en"}' | jq -r '.organic[] | .title, .link'

# SerpAPI
curl -s -G https://serpapi.com/search.json \
  --data-urlencode engine=google --data-urlencode "q=your query" --data-urlencode num=8 \
  --data-urlencode "api_key=$(cat ~/.serp-api-key)" | jq -r '.organic_results[] | .title, .link'
```

Pitfalls:
- Read only the organic fields. Ads and promoted entries sit in separate fields or look like organic ones, so check them.
- Rank depends on `gl`, `hl` and the exact wording. Rewording changes the order.
- In one run, SerpAPI returned noisier results than Serper, with opaque Google redirect links. Try Serper first.

## Exa

Use it for long-tail discovery: pages that Google and Perplexity did not show. Key file: `~/.exa-api-key`.

```bash
curl -s -X POST https://api.exa.ai/search \
  -H "x-api-key: $(cat ~/.exa-api-key)" -H 'Content-Type: application/json' \
  --data-raw '{"query":"your query","numResults":8,"contents":{"highlights":true}}' | jq -r '.results[] | .title, .url'
```

Pitfalls:
- Exa returned unrelated entities and excerpt numbers that were slightly wrong. Verify every fact on the source page.
- If the key fails, use the web UI at exa.ai.

## Tip: use all three

Use Perplexity, Google (Serper or SerpAPI) and Exa together. They complement each other: each has a different signal-to-noise profile, and each finds results the others miss. Treat any one tool's output as leads. Confirm on the source page.

## Pitfall: curl and `@`

A `-d` value that starts with `@` is read as a file name. Use `--data-raw` for any message or JSON body that may start with `@`.
