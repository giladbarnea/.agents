---
name: web-search
description: Web search and content extraction via Perplexity AI
argument-hint: query
---

# Web Search

Search using Perplexity AI via OpenRouter.

## Usage

```bash
./scripts/perplexity_search.py "your search query"
./scripts/perplexity_search.py "query" --model sonar-pro-search
```

Requires `OPENROUTER_API_KEY` in environment or `~/.openrouter-api-key-personal`.

If Perplexity has no funds left on the API key, fall back to using `~/.brave-search-api-key`.
