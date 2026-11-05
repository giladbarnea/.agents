---
name: qmd
description: Map a domain by meaning with `qmd` (local hybrid BM25 + vector search over Markdown and code) before exact search. Use for high-recall discovery in a codebase, docs, notes, or exported session transcripts.
updated: 2026-11-05
---

# qmd

Use `qmd` to discover the semantic neighborhood first. Use exact search only after `qmd` gives you the local vocabulary.

Written against qmd 2.8. For the full, version-matched CLI reference, run `qmd skills get qmd --full`.

## How qmd spends time

Each `qmd` CLI process loads up to three local GGUF models through node-llama-cpp on Metal:

| Model | Job | Used by |
|---|---|---|
| `qmd-query-expansion-1.7B` | rewrites a bare query into `lex:`/`vec:`/`hyde:` lines | bare `qmd query "…"` **and** bare `qmd vsearch "…"` |
| `embeddinggemma-300M` | embeds `vec:`/`hyde:` lines | `query`, `vsearch` |
| `Qwen3-Reranker-0.6B` | reranks candidates | `query` unless `--no-rerank` |

Measured on an M2 Pro, warm models, 73 docs:

| Call | Latency |
|---|---|
| `qmd search` (BM25) | 0.05–0.2 s |
| bare `qmd query "…"` or `qmd vsearch "…"` | 4–13 s; the expansion model dominates |
| typed `qmd query $'lex: …\nvec: …'` | ~1.8 s |
| warm daemon, typed, no rerank | ~0.15 s |
| warm daemon, typed, rerank | 1.4–2.5 s |

Do not parallelize CLI calls to save time. Four parallel `qmd query` processes saved a third, not half, and the daemon serializes on one GPU model.

## Workflow

1. Check coverage.

```bash
qmd status
qmd collection list
qmd update && qmd embed
```

If no collection covers the target, create one. Without `--mask`, qmd indexes Markdown only.

```bash
qmd collection add "$PWD" --name <collection> [--mask="**/*.{py,md,tsx,ts,css,json,html,yaml}"]
qmd embed -c <collection>
```

2. Start the warm daemon when you will run more than a couple of queries. Stop it when done.

```bash
qmd mcp --http --daemon --port 8199
qmd_query() {  # usage: qmd_query COLLECTION RERANK(true|false) LEX VEC
  curl -s localhost:8199/query -H 'content-type: application/json' -d "$(jq -n \
    --arg c "$1" --argjson r "$2" --arg lex "$3" --arg vec "$4" \
    '{collections: [$c], limit: 30, rerank: $r, searches: [{type: "lex", query: $lex}, {type: "vec", query: $vec}]}')" \
    | jq -r '.results[] | "\(.score)\t\(.file)\t\(.title)"'
}
# ...
qmd mcp stop
```

Without the daemon, use the CLI with typed lines: `qmd query $'lex: …\nvec: …' -c <collection> -n 30 --files --no-rerank`.

3. Search by meaning, not names. Write the `lex:` and `vec:` lines yourself. You know the goal and the vocabulary better than the expansion model, and skipping it is most of the speedup. Run several probes from different angles: user behavior, UI surfaces, state ownership, backend effects, docs, tests, and old plans.

- `lex:` the exact terms, aliases, symbols, and rare words you expect in the source.
- `vec:` the idea paraphrased in source-like natural language.
- `hyde:` (optional) a sketch of the passage that would answer the question.
- `intent:` (optional, first line) what you want and what nearby-but-wrong concepts to avoid.

4. First pass: no rerank. Rerank only the probes whose top results look unconvincing. On a 73-session benchmark with one known target, rerank cost about 17× the latency and did not improve hit rate or ranking.

5. Cross-check with orthogonal modes. `lex` and `vec` fail differently. In the same benchmark, `lex` alone found the target in all 8 probes, and `vec` alone missed 2. Neither alone is the method: lexical search needs vocabulary you may not have yet.

```bash
qmd search "<known exact terms after discovery>" -c <collection> -n 30 --files
```

6. Union candidates. Do not trust the first screen. Keep the long tail until you understand why it is irrelevant. Near-duplicates, such as forks, copies, and vendored files, crowd the top results. Raise the limit until distinct documents appear.

7. Read enough context to extract vocabulary.

```bash
qmd get qmd://<collection>/<path> -l 120
qmd multi-get qmd://<collection>/<path-a>,qmd://<collection>/<path-b> -l 80 --format md
```

Prefer explicit comma-separated paths for `multi-get`; quoted brace globs may not expand as intended.

8. Switch to exact expansion. Search **AND FULLY READ** the first few dozen yielded files. Optimize for recall; no such thing as too much context. You need to grok the researched domain as well as know its blast radius; this includes understanding the upstream and downstream domains as well. Climb up to the roots and to the leaves of the call and dependency graphs.

## Rules

- Optimize for recall first; precision comes during reading.
- Map a domain with `--files` (`--format files`) before reading snippets.
- Query with relationships, behavior, purpose, nouns, verbs, and lifecycle phrases.
- Treat low-score results as leads, not answers.
- qmd caches expansion and rerank results in the index. Benchmark with fresh query strings.
- Let `qmd` provide you with a complete map of the target space; read the files in full to intimately know the reality on the ground.
