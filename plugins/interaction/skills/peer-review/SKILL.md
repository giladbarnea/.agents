---
name: peer-review
description: Initiate a peer review of completed work. Pick the mode that matches who is doing the reviewing and load the corresponding reference.
argument-hint: work_to_review
---

Pick the mode that matches the situation:

- The user is directing you to review another agent’s work → @references/peer-review-instructions.md work_to_review=work_to_review [...args] 
- You just completed work and want a subagent to review it → @references/self-peer-review.md where work_to_review=work_to_review
