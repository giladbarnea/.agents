---
name: post-implementation
description: Capture a completed implementation in a high level document. Ask user before loading this skill. 
last_updated: 2026-08-26
---
Write a short document — at most ~40 lines for a major effort, otherwise ~20 lines — about how the implementations had transpired, the decisions made (the "why"s), any challenges encountered (and how solved eventually), and if you've been working with a plan file — any drift from that plan, if it exists. Include no code snippets or line numbers, only references to files and symbols. Reference paths to docs that proved useful. 

Assume the reader of your doc has already read all the relevant code. Therefore, don't explain in words what can be obviously inferred from reading the actual source files. This is redundant, like repeating the same information once in code and again in English. Make your result _complementary_ to the source code so there is added value in reading it that couldn't be gained from just reading the source.

Treat intermediate-work docs as temporary memory. Promote the information vectors worth keeping for future agents into the post-implementation doc, then remove the intermediate docs. Keep an interim doc only when it serves a distinct durable purpose or audience that wouldn't fit into the post-implementation doc. Such docs are probably meant to be reviewed by the human.

Also, of you have been working with a plan file or similar:
2. there should be a directory dedicated to documenting the implemented effort (`thoughts/`, `efforts/`, `work/`, etc). Write there.
1. bidirectionally link the plan file and the content you write via the YAML front matter.
