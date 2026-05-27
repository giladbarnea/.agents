---
name: semantic-search
description: Lightweight semantic search to query any arbitrary directory tree. Returns a list of files ranked by relevance. Go-to approach to scout questions like ‘Where is everything to do with X?’ as well as Q&A over your docs such as ‘What was the most pressing issue for the client in May?’ Use when you need to know which files to read before a deep dive in. Typically used in the earlier stages of a session when gathering full context.
---
## Semantic Search 

Run `./scripts/semantic_search.sh "<query>" [optionaldirpath]`. 

The query should be in natural language. It can and should cast a wide and vague net. Don't narrow down its search space; this is this tool's service to you. The examples in this skill's description are good in that sense. The query should never suggest or hint at possible answers to itself. It should never specify candidate paths and should have zero micromanagement language. Style should be short, general, and as if you're asking a human with deep context over the directory. It should have zero instructions; only one question.

Good examples:
- "What files touch the client's IT constraints?"
- "What does step X in process Y involve technically?"
- "What is the call graph of the scraping system?"
- "Where is the toast notification implemented?"
- "What commitments were made in the last meeting?"
