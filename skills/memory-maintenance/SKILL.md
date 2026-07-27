---
name: memory-maintenance
description: Maintain project documentation as compact, trustworthy institutional memory while working. Use when recording decisions, discoveries, constraints, validations, open questions, or changes to current truth. For an intentional retrospective corpus audit, also read references/maintenance.md.
---

# Project memory is a maintained model of reality

An archive answers, “What was once said?” Project memory answers, “What should I believe now, why do we believe it, what remains undecided, and how should that affect my work?”

Raw meetings, chats, research, and experiments are evidence. They are not automatically memory. Memory is the smaller, resolved model distilled from them for the next agent.

## Work in information vectors

An information vector is the smallest independently meaningful claim that changes an agent's understanding or behavior.

Examples include:

- “The webhook reached this exact endpoint.”
- “Filesystem persistence is undecided.”
- “The worker retries a failed job three times.”
- “This approach was rejected because it created unacceptable operational work.”
- “The database is Postgres.”

Every useful vector should have a clear epistemic state: current truth, validated capability, decision, constraint, open question, or historical rationale. Preserve historical rationale only when it prevents future confusion or repeated mistakes.

A proposal must not quietly read like a decision. A narrow test must not inflate into a broad capability claim. An old assumption must not remain beside its replacement.

## Maintain memory while doing the work

When new work changes the project's model, update the relevant memory in the same unit of work. Identify the new vector, its epistemic state, and its canonical home. Then resolve any vector it contradicts. Do not merely add the new statement and leave reconciliation to the next agent.

Record the result at the narrowest truthful scope. Distinguish what was directly observed from what was inferred. If the answer is not known, write a short open question rather than filling the gap with plausible architecture. Distinguish a hypothetical and assumption from an empirical observation. If it’s a hypothetical, state your assumptions explicitly and use an advisory tone when writing it so that it does not wrongly read as an assertion. Conversely, if it’s an empirical observation, support it with the minimal set of references. 

Retain enough reason to recover consequential decisions, but do not retell the whole path that produced them. The project should remember why it took an important turn without forcing every future agent to relive the conversation.

## Keep the corpus MECE across two axes

The horizontal axis assigns each kind of memory one document role. A common division is:

- `AGENTS.md`: durable instructions for how agents should work in the project.
- `README.md`: the present model—what exists, how it works, and what is currently true.
- `LEDGER.md`: dated decisions, validations, reversals, and the reasons behind consequential changes.
- `meetings/`, `research/`, `references/`, and arbitrary `{topic}/`: source evidence, subordinate to canonical memory.

Use the project's existing structure when it already provides these roles. Do not create documents merely to satisfy these example names.

The vertical axis gives each information vector one canonical home. Other documents may link to it or record that it changed, but should not independently maintain competing versions of the same current truth.

The two-dimensional test is simple:

1. Does every useful vector have a home?
2. Does each vector have only one authoritative home?

Functional overlap is sometimes legitimate. A ledger may record that a decision occurred while current-state describes the resulting system. Semantic duplication is the problem: several passages independently claiming what the current truth is.

## Do not start a yelling contest

A yelling contest begins when an agent wants to record a fresh vector, finds several pre-existing vectors that contradict it, and tries to overpower them with more detail, heavier emphasis, repeated warnings, bold text, or all-caps. The corpus quickly becomes a room full of teenagers, each talking louder to become the center of attention.

Do not make the fresh vector louder. Decay the stale or contradictory vectors: delete false claims, replace superseded present-state claims, compress valuable history into its proper historical home, and remove obsolete prominence. Clear the space first. Then write the fresh vector calmly, at the ordinary length, detail, and emphasis it deserves.

## Evidence remains as narrow as the test

A validation establishes only what was observed. One successful HTTP request does not prove unrestricted network access. One process launched under a user account does not prove arbitrary installation capability. One observed workflow does not prove that every case follows it.

Broader conclusions may be recorded, but label them as inferences or open assumptions. Do not let convenient language silently widen evidence.

## Open questions are first-class memory

An unresolved question is useful project state. State it once and keep it short. It should name the decision surface without prematurely designing the answer.

Supporting possibilities belong only when they materially explain why the question exists. A long speculative branch is not a better open question.

## Let project complexity determine memory complexity

A small early project usually benefits from direct deletion. There is little value in preserving the ancestry of every discarded thought. A mature project may need more decision history because surprising constraints, reversals, and institutional precedent affect future work.

History earns its place when it explains a current constraint, prevents a likely repeated mistake, or preserves meaningful accountability. It should not survive merely because it once existed.

## Good memory reads like one informed mind

Current reality appears before history. Claims are precise about scope and certainty. Important rationale survives without taking over the page. Open questions are visibly unresolved. Failed assumptions do not linger as ambient possibilities. Links connect documents instead of prose duplicating them. The amount of documentation matches the project's actual complexity.

The governing test is:

> Could a capable new agent read this corpus once and proceed with approximately the same model of reality as the person maintaining the project?

If the agent must reconcile contradictions, distinguish plans from decisions, or repeatedly discover which passages are obsolete, the memory system has passed its bookkeeping cost to every future session.

## Retrospective maintenance is a separate operation

Ordinary bookkeeping keeps memory healthy as work happens. An intentional retrospective maintenance pass treats the corpus itself as the work product.

When asked to audit, clean up, reconcile, prune, or maintain an existing corpus, read [the maintenance procedure](references/maintenance.md) in full before editing. 