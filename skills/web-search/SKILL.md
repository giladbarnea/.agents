---
name: web-search
description: Web search and content extraction via Perplexity AI
argument-hint: query
---

# Web Search

Search using Perplexity AI through OpenRouter first.

## Usage

```bash
./scripts/perplexity_search.py "your search query"
./scripts/perplexity_search.py "query" --model sonar-pro-search
```

The script first uses `OPENROUTER_API_KEY` or `~/.openrouter-api-key`.

If OpenRouter fails, it uses `PERPLEXITY_API_KEY` or `~/.perplexity-api-key` with the Perplexity API.

If both fail, use Brave Search with `~/.brave-search-api-key`.
