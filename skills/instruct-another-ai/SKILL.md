---
name: instruct-another-ai
description: Best practices for getting a step-function leap in performance from other AI agents when instructing or communicating with them. Note that Markdown docs are AI agents’ bread-and-butter, not only humans’. Load `instruct-another-ai` autonomously before spawning a sub-agent, creating a team of sub-agents, talking to a teammate agent, or writing documentation. Trigger words are “dispatch an agent”, “spawn a team”, etc.
---

## Why delegate at all?

The main agent already holds all the context, so why not have it just do the work directly? Context management. Both sub-agents and teams spin up a *fresh* context window and hand back only the bottom line, sparing you the token-heavy process that produced it. Two payoffs: (1) you reach the crux of the problem with plenty of headroom left in your own context window, instead of arriving running on fumes; and (2) you escape your own accrued bias.

The flip side: if none of these payoffs apply, don't delegate. The anti-pattern is the user asking for something straightforward and the main agent handing the *whole* task to another agent, ending the session: no context-window hygiene, no synergy, no parallelism, no bias mitigation, just duplicated tokens and a game of broken telephone.

Classic use cases — *generalize* the principles, this isn't a comprehensive list:
- **Exploration** — one sub-agent for a single domain, or parallel sub-agents when your can fan the scope out. Keeps your own context light, and parallel agents save wall-clock time too.
- **Debating the best plan** — an adversarial team handed the user's goal at large plus the exploration results. Synergistic judgement, and it mitigates any single teammate's bias.
- **Reviewing an implementation** — a sub-agent handed the user's goal at large, the exploration results, the finalized plan, and the implementation's commit SHA. Mitigates the main agent's bias toward its own work.

---

1. Orient the agent to the project: the user has mostly likely told you to load a context-gathering skill first thing in the session. Tell the AI agent to load the same skill, with the same arguments the user has specified. On top of that, if throughout the session, you have created, read or edited additional files that are not referenced by the skill, reference them too.  

2. Be generous in giving the agent wider context—understanding *why* it's performing the task will boost its performance. Don't micromanage or over-instruct it. The agent already has the same system prompt as you do out of the box (e.g. `CLAUDE.md` or `AGENTS.md`). It is essentially an equivalent instantiation of yourself. It is highly and equally intelligent as you are, and can navigate uncertainties well without spoon-feeding. What kind of input do YOU thrive on? Exactly — wide contextual understanding and aspired end state. Avoid prescribing instructions, giving "how-to" examples, providing examples as to what to think about, or dictating which files, symbols, or paths to look at; avoid any form of providing hints for possible answers for your own queries — this is circular and useless. Just *declare what is the bottom line added value YOU are seeking for yourself*. Instead of specifying which steps to take (dictating the "how" is bad), share with the agent only why it was dispatched and what you hope to gain. This directly frees the agent to find the best way to reach *your* goal, unbiased and unconstrained by your own assumptions.
    Essentially, all the “Don’ts” above over-fit the agent.
    <negative-example-1 why-bad="main agent shoots its own foot by limiting the sub-agent’s research scope">
    User to main agent: "Why does Vercel claim their integrated version is beneficial?"
    Main agent spawns a sub-agent and prompts it: "Research why Vercel claim their integrated version is beneficial (edge runtime, seamless DX, zero-config, billing, monitoring, tight coupling to `vercel` CLI / dashboard / functions)."
    </negative-example-1>
    <positive-example-1 why-good="main agent declares the bottom line added value it needs without prescribing what and how to do it">
    User to main agent: "Why does Vercel claim their integrated version is beneficial?"
    Main agent spawns a sub-agent and prompts it: "I want to know why Vercel claim their integrated version is beneficial."
    </positive-example-1>
    
    Example 2 settings: the `load-context` skill instructs to read CLAUDE.md, ARCHITECTURE.md, docs/webserver/API.md, docs/data/architecture.md, server/api.py, and server/db.py.    
    <negative-example-2 why-bad="main agent fails to leverage the harness and instead prescribes what to do; moreover it makes the same scope-narrowing mistake as in example-1">
    User to main agent: "/skill:load-context domain: acme, subdomain1: the public REST API, subdomain2: the data layer. I want to plan a view layer with you later, so let’s understand the foundations."
    Main agent spawns a sub-agent and prompts it: "Read CLAUDE.md, ARCHITECTURE.md, docs/webserver/API.md, docs/data/architecture.md, server/api.py, server/db.py, and summarize how the REST API and data layers work. Cover how function `server/api.py:from_db` fetches the data by calling the `server/db.py:get_data` function, and how [...proceeds to prescribe ironically specific locations to “discover”]"
    </negative-example-2>
    <positive-example-2 why-good="main agent recognizes the work can be distributed concurrently, shortly shares the wider context (the “why”), forwards the user’s context levers — keeping the shared domain and handing each agent one of the two subdomains rather than dropping them — and does not micro-manage the agents with how-exactly instructions">
    User to main agent: "/skill:load-context domain: acme, subdomain1: the public REST API, subdomain2: the data layer. I want to plan a view layer with you later, so let’s understand the foundations."
    Main agent fans out research scope horizontally to two parallel sub-agents and prompts them: "The user and I are planning a new view layer, so we need a thorough understanding of the foundations. [to one agent] /skill:load-context domain: acme, subdomain: the public REST API [to the other agent] /skill:load-context domain: acme, subdomain: the data layer. [to both] Study your subdomain deeply and exhaustively."
    [Main agent receives the two independent sub-agents’ responses, thinks hard to synthesize them]
    Main agent responds to user: "I have deep understanding of both layers and their relationships. What did you have in mind?"
    </positive-example-2>

    
    <positive-example-3 why-good="main agent writes as simple a prompt as possible. adds only what is necessary to get the reviewer up to speed. does not put words in the user’s mouth." note="this example has no negative counterpart. this is a positive example.">
    User to main agent: "Spawn a sub-agent to review your work. I’m mostly interested in blindspots in the implementation, bugs, and opportunities to get the same results with a simpler, collapsed approach."
    Main agent spawns a sub-agent and prompts it: "load the load-project-context and peer-review skills. the user asked me to <user request>. after the first iteration, a review pointed out that <review gist>, and we decided to proceed with <committed direction>. i’ve implemented it. review my work (the current main dirty tree). do you spot any blindspots, bugs, or opportunities to achieve the same results with a simpler, collapsed approach?"
    </positive-example-3>

3. Sub-agents are isolated from each other and report only to you; teammates can talk amongst themselves live, without routing through you. So spawn a *team* when that live interaction would add value through synergy, the classic case being a GAN-inspired adversarial pairing (planner–reviewer, implementer–reviewer) where one produces and the other pokes holes until both are content. Spawn multiple parallel *sub-agents* when a wide task fans out horizontally into independent threads and you expect to do the synthesis yourself — i.e. when exchanging findings and opinions between them would not be clearly helpful.

4. Since teammates talk to each other, tell each of them to load the this skill (`instruct-other-ai`) on top of the context-gathering skill. If you are spawning an adversary among them, tell it to load the `peer-review` skill too.

    Example 4 settings: at the session’s start the user ran `/skill:load-context domain: acme, subdomain1: the public REST API, subdomain2: the data layer`; the main session explored the code, and the user approved a plan to add rate limiting to the public REST API.
    <negative-example-4 why-bad="main agent burns its own context shuttling the diff and the feedback back and forth — dives into the sub-agent’s work and clogs its own context window worse than doing the task solo would have, acts as a reviewer when biased">
    User to main agent: "Great, go ahead and build it."
    Main agent spawns one sub-agent to implement; when it returns the diff, studies and reviews it; relays the review the sub-agent; and keeps ferrying revisions until the diff settles.
    </negative-example-4>
    <positive-example-4 why-good="main agent picks a team because the adversarial iteration is synergistic, replicates the user’s context levers verbatim — including the domain and the subdomains the user specified when loading the context skill — has the reviewer also load `peer-review`, declares only the bottom line it wants, and stays out of the loop while they converge">
    User to main agent: "Great, go ahead and implement the plan."
    Main agent spawns an implementer–reviewer team and prompts them: "/skill:load-context domain: acme, subdomain1: the public REST API, subdomain2: the data layer, then load `instruct-another-ai`. You are an implementer–reviewer team. Here is the user’s original message to me, verbatim, for the bigger picture: <the-user-message-describing-the-task>. [to the implementer] Implement the plan, and ping your teammate when you think you’re done. [to the reviewer] Also load `peer-review`, and review your teammate’s work when it pings you. [to both] The user and I finalized a plan to add rate limiting to the public REST API — here it is: <the plan>. Build it and tear it apart between yourselves until you’re confident it’s the simplest working, correct solution faithful to the plan."
    [The team implements and reviews live, converging without the main agent in the loop; the main agent receives the finished, reviewed result.]
    Main agent responds to user: "Done — implemented and adversarially reviewed between the two of them. Here’s what landed: …"
    </positive-example-4>

    **Note to Teammates:** Set your own status frequently. Figuratively: nod when receiving a message; advertise that you're responding before you send a message; expose when you've messaged your teammate and are waiting for reply; show when you're exploring, implementing, testing, reviewing, blocked, or waiting. Keep statuses short but current so your teammates and main can see the live state.

5. Subagents and teams can take a long time to run - use a 20-minute timeout.
