---
name: prompt-subagent
description: Instructions for _how_ to prompt a subagent to perform any task. Load this skill before dispatching a subagent.
---

1. Orient the agent to the project: tell it to read key context files (`README.md`, `CLAUDE.md`/`AGENTS.md`, `ARCHITECTURE.md`) and any relevant domain context directories—enough for it to understand *what this project is for* before starting the task. If the user used a context-gathering skill at the beginning of the main session, point the agent to that as well.

2. Be generous in giving the agent wider context—understanding *why* it's performing the task will boost its performance. Don't micromanage or over-instruct it. The agent already has a highly detailed system prompt. It is highly intelligent, just like you, and can navigate uncertainties well without being spoonfed. Avoid prescribing instructions, giving "how-to" examples, or dictating which files, symbols, or paths to look at; just *declare* what kind of *understanding* YOU are seeking for *yourself*. Instead of specifying which steps to take (dictating the "how" is bad), share only why it was dispatched and what you hope to achieve. This directly frees the agent to find the best way to reach *your* goal, unbiased and unconstrained by your own knowledge and assumptions.

3. Remind the agent that it can also spawn subagents to perform tasks, utilize skills, etc.

4. Subagents can take several minutes to run - use a 10-minute timeout.