---
name: qmd
description: High-recall semantic codebase search with the qmd CLI. Use when the user has instructed to research a scope, when you to find all files, symbols, docs, plans, or cross-stack implementation paths related to a domain, feature, behavior, or vague concept whose relevant code may not contain the user's literal words.
---

# qmd

Use `qmd` to discover the semantic neighborhood first. Use exact search only after `qmd` gives you the local vocabulary.

## Workflow

1. Check coverage.

```bash
qmd status
qmd collection list
qmd ls
```

Then run:

```bash
qmd update
qmd embed
```

2. Search by meaning, not names.

Run several broad `query` probes from different angles. Ask about user behavior, UI surfaces, state ownership, backend effects, docs, tests, and old plans.

```bash
qmd query "anything related related <domain>; include UI, state, hooks, reducers, routes, storage, call graph upstream and downstream, dependencies, usages, tests and docs." -c <collection> -n 30 --files
qmd query "<domain described as user behavior, not feature name>" -c <collection> -n 30 --files
qmd query "<domain described as data/control flow>" -c <collection> -n 30 --files
```

3. Cross-check with orthogonal modes.

```bash
qmd vsearch "<compact concept cloud>" -c <collection> -n 30 --files
qmd search "<known exact terms after discovery>" -c <collection> -n 30 --files  # `search` is BM-125, like Lucene engine
```

Use:

- `query` for best recall: expansion, vector search, reranking.
- `vsearch` for related concepts with different words.
- `search` for exact terms, never as the only pass.

4. Union candidates.

Do not trust the first screen. Keep the long tail until you understand why it is irrelevant.

5. Read enough context to extract vocabulary.

```bash
qmd get qmd://<collection>/<path> -l 120 --line-numbers
qmd multi-get qmd://<collection>/<path-a>,qmd://<collection>/<path-b> -l 80 --md
```

Prefer explicit comma-separated paths for `multi-get`; quoted brace globs may not expand as intended.

6. Switch to exact expansion.

Search **AND FULLY READ** the first few dozen yielded files. Optimize for recall; no such thing as too much context. You need to grok the researched domain as well as know it's blast radius; this includes understanding the upstream and downstream domains as well. Climb up to the roots and to the leaves of the call and dependency graphs.

---

## Rules

- Optimize for recall first; precision comes during reading.
- Use `--files` before snippets when mapping a domain.
- Query with relationships, behavior, purpose, nouns, verbs, and lifecycle phrases.
- Treat low-score results as leads, not answers.
- Let `qmd` provide you with a complete map of the target space; Read the files in full to intimately know the reality on the ground.
