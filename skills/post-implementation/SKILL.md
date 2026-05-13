---
name: post-implementation
description: Load this skill upon finishing an implementation that was approved by the user to document it.
last_updated: 2026-04-30 17:19, 4e222f3
---
Write a short document — at most ~40 lines for a major effort, otherwise ~20 lines — about how the implementations went, the decisions made (the "why"s), any challenges encountered, and if you've been working with a plan file — any drift from that plan. Include no code snippets or line numbers, only references to files and symbols. Reference paths to docs that proved useful. 

Don't just explain in words what can be obviously inferred from reading the actual source files. This is redundant, like repeating the same information once in JavaScript and again in English. Make your result complementary to the source code so there is added value in reading it that couldn't be gained from just reading the source. 

Also, of you have been working with a plan file or similar: 
2. there should be a directory dedicated to implementation files. Write there. 
1. bidirectionally link the plan file and the content you write via the YAML front matter.
