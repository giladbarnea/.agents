---
name: "plan"
description: "Planning best practices. Load when planning a multi-phase, heavyweight deliverable. Unfit for small-medium sized efforts."
---

# Planning Best Practices

Each of the 1, 2 and 3 phases below is a single standalone pass that you should perform and present to the user. Ask the user whether to confirm with them before moving to the next phase or work through all three in one go. Phase #1 usually ends with writing a plan file; phases #2 and #3 end with updating it. Ask the user whether to maintain some kind of memory throughout the effort.

Come up with:

1. High-level steps to get from right now to “Done and in production.” No implementation details. High-level means high-level: product, _behavior_, user stories.
2. Dependency graph of the steps. Aspects:
    2.1. What blocks what -> derive the necessary ordering and what can be fanned out in parallel.
    2.2. What absolutely requires the human.
    2.3. Major decisions we still haven’t made that affect the graph. If the possible choices for a decision are known and final, express them as forks.
    2.4. For each step (node): assess complexity, risk, rough diff size, and reversibility. These four aren’t independent (each predicts the others to some extent), so keep this #2.4 assessment short and to the point.
3. High-quality specificity. For each node in the graph: testable definition of done, testable failure criteria, very light pseudocode (load the `/pseudocode` skill), and a short, to-the-point list of “What we kept out of scope to keep this plan minimal.”


## Self-inspect with the user

Is the final deliverable truly minimal? Signs that it is _not_ minimal:
- Some steps are premature optimization: they only improve the quality or user experience when non was requested, or prepare the ground for a hypothetical future development iteration.
- The end user would be happy with an earlier version of the deliverable.
