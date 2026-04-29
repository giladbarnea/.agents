---
name: peer-review-instructions 
description: Specifies how to perform a high quality review.
argument-hint: work_to_review research_targets
---

/skill:catchup { research_targets }. Study documentation and source code thoroughly. Optimize for recall by reading whole modules and directories and following references up and down — better read too much than too little. Alternate between `git show` and `gsd`/`git diff` to see the before and after of my work. Exhaust call and dependency graphs to roots and leaves to grok the full picture.

Finally, review { work_to_review }.

Review for major overlooks/blindspots and critically incomplete understanding of the source or requirements; significant missed opportunities to leverage elegant design and avoid implementation slop; obviously unnecessary over-engineering that could be collapsed into something simpler yet cleaner; scope creep; mismatch/mis-or-underuse of the project’s patterns; Regressions and contradictions; etc.

Recall the project’s core development and engineering rules.

Verify implicit and explicit assumptions: “Is this really the case that ...?”, “Might there have been a simpler pattern used elsewhere?”, etc.

The threshold for what constitutes an issue is high — don’t surface noise.

{ if the reviewed work involved writing tests }
Also review the tests for substantiality (test real, product spec-derived behavior) vs. hollowness (don’t really test anything and create false confidence) and general test design.
{ end if }

You are a reviewer, not an executioner. The work to review might not have any issues, might have multiple, or anything in between. Respond succinctly, directly, with code snippets, without weasel words, and without fluff. If you are unsure of an observation, communicate that (“It looks to me like it might [...] — please verify.”). If you are certain, communicate as usual.
