---
name: instruct-another-ai
description: Best practices for getting a step-function leap in performance from other AI agents when instructing or communicating with them. Note that Markdown docs are AI agents’ bread-and-butter, not only humans’. Load `instruct-another-ai` autonomously before spawning a sub-agent, creating a team of sub-agents, talking to a teammate agent, or writing documentation.
---

## Why delegate at all?

The main agent already holds all the context, so why not just do the work directly? Context management. Both sub-agents and teams spin up a *fresh* context window and hand back only the bottom line, sparing you the token-heavy process that produced it. Two payoffs: (1) you reach the crux of the problem with plenty of headroom left in your own context window, instead of arriving running on fumes; and (2) you escape your own accrued bias.

The flip side: if none of these payoffs apply, don't delegate. The anti-pattern is the user asking for something straightforward and the main agent handing the *whole* task to another agent, ending the session: no context-window hygiene, no synergy, no parallelism, no bias mitigation, just duplicated tokens and a game of broken telephone.

Classic use cases — *generalize* the principles, this isn't a comprehensive list:
- **Exploration** — one sub-agent for a single domain, or parallel sub-agents when your can fan the scope out. Keeps your own context light, and parallel agents save wall-clock time too.
- **Debating the best plan** — an adversarial team handed the user's goal at large plus the exploration results. Synergistic judgement, and it mitigates any single teammate's bias.
- **Reviewing an implementation** — a sub-agent handed the user's goal at large, the exploration results, the finalized plan, and the implementation's commit SHA. Mitigates the main agent's bias toward its own work.

---

1. Orient the agent to the project: the user has mostly likely told you to load a context-gathering skill first thing in the session. Tell the AI agent to load the same skill, with the same arguments the user has specified. On top of that, if throughout the session, you have created, read or edited additional files that are not referenced by the skill, reference them too.  

2. Be generous in giving the agent wider context—understanding *why* it's performing the task will boost its performance. Don't micromanage or over-instruct it. The agent already has the same system prompt as you do out of the box (e.g. `CLAUDE.md` or `AGENTS.md`). It is essentially an equivalent instantiation of yourself. It is highly and equally intelligent as you are, and can navigate uncertainties well without spoon-feeding. Avoid prescribing instructions, giving "how-to" examples, providing examples as to what to think about, or dictating which files, symbols, or paths to look at; avoid any form of providing hints for possible answers for your own queries — this is circular and useless. Just *declare what is the bottom line added value YOU are seeking for yourself*. Instead of specifying which steps to take (dictating the "how" is bad), share only why it was dispatched with it and what you hope to gain. This directly frees the agent to find the best way to reach *your* goal, unbiased and unconstrained by your own assumptions.
    Essentially, all the “Don’ts” above over-fit the agent.
    <negative-example-1 why-bad="main agent shoots its own foot by limiting the sub-agent’s research scope">
    User to main agent: "Why does Vercel claims their integrated version is beneficial?"
    Main agent spawns a sub-agent and prompts it: "Research why Vercel claims their integrated version is beneficial (edge runtime, seamless DX, zero-config, billing, monitoring, tight coupling to `vercel` CLI / dashboard / functions)."
    </negative-example-1>
    <positive-example-1 why-good="main agent declares the bottom line added value it needs without prescribing what and how to do it">
    User to main agent: "Why does Vercel claims their integrated version is beneficial?"
    Main agent spawns a sub-agent and prompts it: "I want to know why Vercel claims their integrated version is beneficial."
    </positive-example-1>
    
    <negative-example-2 why-bad="main agent fails to leverage the harness and instead prescribes what to do; moreover it makes the same scope-narrowing mistake as in example-1" settings="the `load-context` skill instructs to read CLAUDE.md, ARCHITECTURE.md, docs/webserver/API.md, docs/data/architecture.md, server/api.py, and server/db.py.">
    User to main agent: "/skill:load-context and explore the following subdomains: the public REST API and the data layer. I want to plan a view layer with you later, so let’s understand the foundations."
    Main agent spawns a sub-agent and prompts it: "Read CLAUDE.md, ARCHITECTURE.md, docs/webserver/API.md, docs/data/architecture.md, server/api.py, server/db.py, and summarize how the REST API and data layers work. Cover how function `server/api.py:from_db` fetches the data by calling the `server/db.py:get_data` function, and how [...proceeds to prescribe ironically specific locations to “discover”]"
    </negative-example-2>
    <positive-example-2 why-good="main agent recognizes the work can be distributed concurrently, shortly shares the wider context (the “why”), replicates the context-gathering levers the user used, and does not micro-manage the agents with how-exactly instructions">
    User to main agent: "/skill:load-context and explore the following subdomains: the public REST API and the data layer. I want to plan a view layer with you later, so let’s understand the foundations."
    Main agent fans out research scope horizontally to two parallel sub-agents and prompts them: "/skill:load-context. The user an I are planning a new view layer, so we need a thorough understanding of the [to one agent] public REST API [to the other agent] data layer. Study it deeply and exhaustively."
    [Main agent receives the two independent sub-agents’ responses, thinks hard to synthesize them]
    Main agent responds to user: "I have deep understanding of both layers and their relationships. What did you have in mind?"
    </positive-example-2>

3. Sub-agents are isolated from each other and report only to you; teammates can talk amongst themselves live, without routing through you. So spawn a *team* when that live interaction would add value through synergy, the classic case being a GAN-inspired adversarial pairing (planner–reviewer, implementer–reviewer) where one produces and the other pokes holes until both are content. Spawn multiple parallel *sub-agents* when a wide task fans out horizontally into independent threads and you expect to do the synthesis yourself — i.e. when exchanging findings and opinions between them would not be clearly helpful.   

4. Subagents can take several minutes to run - use a 15-minute timeout.
