---
name: "plan"
description: "Planning best practices. Load when planning a multi-phase deliverable."
---

# Planning Best Practices

Each of the points below is a single standalone pass that you should perform and present to the user. Moving to the next step requires user approval. Step #1 usually ends with writing a plan file; steps #2 and #3 end with updating it. Ask the user whether to keep a separate ledger file throughout, so the process can resume if this session hits the context window cap.

1. High-level steps to get from right now to “Done and in production.” No implementation details. High-level means high-level.
2. Dependency graph of the steps. Aspects:
    2.1. What blocks what -> derive the necessary ordering and what can be fanned out in parallel.
    2.2. What needs me.
    2.3. Decisions we still haven’t made that affect the graph. If the possible choices for a decision are known and final, express them as forks.
    2.4. For each step (node): complexity, risk, rough diff size, and reversibility. These four aren’t independent (each predicts the others to some extent), so keep the #2.4 assessment short and to the point.
3. High-quality specificity. For each step: testable definition of done, testable failure criteria, very light pseudocode (load the `/pseudocode` skill), and a short, to-the-point list of “What we kept out of scope to keep this plan minimal.”


## Self-inspect with the user

Is the final deliverable truly minimal? Signs that it is _not_ minimal:
- Some steps are arguably optimization: they improve the quality, user experience, or our own dev experience “for next time” of something that already works regardless.
- It is possible to imagine the end user happy to receive the deliverable at an earlier stage than where the current plan ends.
