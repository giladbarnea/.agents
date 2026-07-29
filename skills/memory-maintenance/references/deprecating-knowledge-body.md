---
description: Procedure for deprecating an entire body of knowledge from project memory — itemize, dedup, collapse, delete. Only load if the user instructs so explicitly.
last_updated: 2026-07-16 11:10
---

# Deprecating a knowledge body

Use when a whole plan, approach, or design era has been superseded and its documentation must be aggressively pruned. The goal is not selective editing — it is removing an entire semantic stratum from the project while preserving the few empirical results that can't be rederived.

## Inputs

1. **The boundary** — which docs belong to the deprecated body. Files are used only to define the space; the unit of work is the information vector (an item), not the file.
2. **The salvage criterion** — what, if anything, survives. Typically: empirical results from brute-force iteration that can't be inferred without repeating the work. Everything else goes.

## Procedure

### Phase 1 — Make the deprecated body internally MECE

The body accumulated duplicates across docs over time. Before removing anything, collapse the duplicates so every idea has exactly one home. This prevents orphaned copies surviving the deletion.

Flow in pseudo-python:
Don't take the flow control literally — if the pseudocode does an O(N) pass, that doesn't mean dispatching an agent for a full pass. Focus on the semantic data story: what we need to know and what we need to do.

```
roster = [doc for doc in project if contains_deprecated_items(doc)]

items = flatten(extract_items(doc) for doc in roster)
    # item = one information vector, smallest a line, largest a section
    # follow source granularity; don't atomize transcripts

deprecated_items = [item for item in items if is_deprecated(item)]

groups = group_by_semantic_near_duplicate(deprecated_items)
    # each group: 2+ items asserting the same idea across different docs
    # order members chronologically; earliest = keeper
    # items with no near-duplicate stay out — they're singletons

for group in groups:
    essence = extract_common_essence(group)  # precision, not union
    replace(group[0], essence)  # earliest member becomes the essence
    delete(group[1:])           # remaining copies removed from their docs
```

**Checkpoint:** skim the group list before proceeding. A wrong merge silently destroys a distinct idea. The list should be dozens of rows, not hundreds — titles and member counts are enough to spot bad merges.

### Phase 2 — Delete and salvage

After dedup, every deprecated idea exists in exactly one place.

```
for item in all_deprecated_items:
    if meets_salvage_criterion(item):
        move to salvage doc
    else:
        delete

for doc in roster:
    if now_empty(doc):
        delete file

write salvage_doc  # one terse document, not a ledger
update broken references in living docs (AGENTS.md, skill manifests, etc.)
```

The salvage doc is a how-to, not a history. No narrative, no decisions, no dated events — just the facts and the recipe someone would need to avoid repeating the work.

## Delegation shape

Phase 1 itemization fans out by domain — split the roster into 2–3 cohesive doc clusters, one reader agent per cluster. Each returns a flat list of `(id, path, section, date, gist, in/out)` records. Lean on recall over precision when assigning docs to clusters; overlap is fine, gaps are not.

Phase 1 grouping is inherently global (duplicates cross docs) — one synthesis agent over the merged item lists. This is the bottleneck; it cannot be parallelized.

Phase 2 is mechanical — one agent with the approved group list and the salvage criterion.

```
          ┌── reader A (domain 1) ──┐
roster ──►├── reader B (domain 2) ──┤──► grouper (global) ──► ★ human skim ──► executor
          └── reader C (domain 3) ──┘
```
