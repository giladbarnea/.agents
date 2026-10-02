---
name: task-graph
description: Add a high-ish-level task graph to a plan.
---

# Task Graph

This skill assumes you already have a plan made of prose and pseudocode, whether in your head or written down.

Use both prose and pseudocode, and add a high-ish-level task graph, first in pseudocode and then in Unicode. High-ish means mostly subsystems and lightly some modules, but no deeper.

The added value of a task graph over prose and pseudocode is that it communicates:

1. Proofs and disproofs, technical dependencies, and thus the sensible order.
2. Relations between subsystems and modules: domain, flow, and rough contracts. Express contracts in pseudocode, not hard definitions.
3. For each meaningful node, standalone estimates, with no carryover, of:
   - **Added ongoing complexity to the project if successful:** four T-shirt size bins.
   - **Chance of not successfully completing the task** because of inherent difficulty, uncertainty in the bet, or unexpected surprises along the way: four T-shirt size bins.
   - **Measurable definition of failure:** one or two short bullet-point lines. If there are two, they must approach the task from as different angles as possible, both in subdomain and in the technology stack invoked.
   - **Measurable definition of success:** one or two short bullet-point lines. If there are two, apply the same requirement for different angles as above.

Not all four per-node data points are justified for every node. Pick a sensible combination that matches the node's size, impact, meaning, and other relevant qualities.

Think really thoroughly about each aspect of this definition. It is information-dense, with much to unpack.
