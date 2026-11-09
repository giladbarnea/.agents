---
name: session-ops
description: Operations on agent sessions as sets of knowledge, such as merging two sessions or consolidating many into one owner per vector of work. Load when asked to merge, consolidate, or otherwise combine sessions; other skills build on these operations.
---

# Session operations

Each operation is a function in `functions/`. Read only the one you were asked for, and the ones it calls.

| Function | What it does |
|---|---|
| [`collapse`](functions/collapse.md) | Sessions in scope: keeps only the active ones, each folding in its inactive ancestors |
| [`merge`](functions/merge.md) | Two sessions, two vectors: each session becomes the owner of one vector and is caught up on it |
| [`consolidate`](functions/consolidate.md) | Many sessions: collapses them, folds them through `merge`, keeps one owner per vector, prunes the rest |

## Shared terms

- **Knowledge item:** an (idea, version, time) a session holds. An item is keyed by the idea alone. Time only decides which version is current, because ideas are restated and overruled over time.
- **Vector:** one direction of work. Vectors branch from shared ground; they need not be disjoint.
- **Sister owner session clades:** the shape the owners end in. Like an uppercase Y, they branch from a shared trunk, and each holds its own territory.
- **Read-only by default:** every action that touches a session or Herdr is behind a boolean in `act`, default `false`. Without it, the agent does the work in its own context.

Load `jsonl-toolkit` to read transcripts. Read [`ANCESTRY.md`](/Users/giladbarnea/top/ANCESTRY.md) to find fork parents and inherited prefixes.
