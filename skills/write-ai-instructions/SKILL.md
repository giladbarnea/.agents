---
name: write-ai-instructions
description: Instructions for how to write AI prompts — both when prompting an agent directly and when writing content whose target audience is AI agents. Load this skill before doing either.
---

1. Orient the agent to the project: tell it to read key context files (`README.md`, `AGENTS.md`, `ARCHITECTURE.md`, etc.) and any relevant domain context directories—enough for it to understand *the project’s purpose* before starting the task. If the user referenced any context-gathering skills at the beginning of the main session, point the agent to them as well.

2. Be generous in giving the agent wider context—understanding *why* it's performing the task will boost its performance. Don't micromanage or over-instruct it. The agent already has a highly detailed system prompt. It is highly intelligent, just like you, and can navigate uncertainties well without being spoon-fed. Avoid prescribing instructions, giving "how-to" examples, providing examples as to what to think about, or dictating which files, symbols, or paths to look at; avoid any form of providing hints for possible answers for your own queries — this is circular and useless. Just *declare* what kind of *understanding* YOU are seeking for *yourself*. Instead of specifying which steps to take (dictating the "how" is bad), share only why it was dispatched and what you hope to achieve. This directly frees the agent to find the best way to reach *your* goal, unbiased and unconstrained by your own limited knowledge and assumptions.
    <negative-example description="listing potential answers to own question">
    Research why Vercel claims their integrated version is beneficial (edge runtime, seamless DX, zero-config, billing, monitoring, tight coupling to `vercel` CLI / dashboard / functions).
    </negative-example>
    <positive-example description="saying what your need, not instructing what to do">
    I want to know why Vercel claims their integrated version is beneficial.
    </positive-example>

3. Remind the agent that it can also spawn subagents to perform tasks, utilize skills, etc.

4. Subagents can take several minutes to run - use a 10-minute timeout.
