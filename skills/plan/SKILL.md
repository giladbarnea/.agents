---
name: "plan"
description: "Planning best practices. Load when planning a multi-phase deliverable."
---

# Planning Best Practices

Each of the following 1–3 points is a single standalone pass by the agent presented to the user. Proceeding to next step requires user approval. Step #1 likely ends with writing a plan file. Steps #2 end with updating that file. Ask the user whether to maintain a separate ledger file throughout the process to enable resumability in case this session hits context window cap. 

1. High-level required steps to get from right now to “Done and in production.” No implementation details. High-level is a high level.
2. Dependency graph of the steps. Aspects:
    2.1. What blocks what -> derive the necessary ordering and what can be fanned out in parallel.
    2.2. What needs me.
    2.3. Decisions we still haven’t made which affect the graph. If the set of possible choices for a decision is known, express them as forks.  
    2.4. For each step (node): complexity, risk, estimated diff size (roughly), and reversibility. I know these four items are not independent (each predicts the other to some extent), so keep the #2.4 assessment short and to-the-point. 
3. High-quality specificity. For each step: testable definition of done, testable failure criteria, very very light pseudocode (load the `/pseudocode` skill), and a “What we kept out-of-scope to keep this plan minimal” (short to the point list.) 


## Self-inspect with the user

Is the final deliverable truly minimal? Signs that it is _not_ minimal:
- Some steps are arguably optimization (they improve the quality/user experience/our own dev experience “for next time” of something that otherwise works regardless)
- It is possible to imagine the end user happy to receive the deliverable at an earlier stage than where the current plan ends. 
