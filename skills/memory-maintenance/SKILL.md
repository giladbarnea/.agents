---
name: memory-maintenance
description: Maintain project documentation as compact, truthful institutional memory. Only for memory-maintaining projects. Needs user approval.
last_updated: 2026-08-05 17:00
---

# Project memory is a maintained model of reality

An archive answers, "What was once said?" Project memory answers, "What should I believe now, why do we believe it, what remains undecided, and how should that affect my work?"

Raw meetings, chats, research, and experiments are evidence. They are not automatically memory. Memory is the smaller, resolved model distilled from them for the next agent.

Two things depend on it: recovering the decisions taken over time and the rationale behind them, and letting a new session resume work effectively, truthfully, and efficiently. A newcomer should be able to form the true, coherent, internally consistent story of how the project got here.

Memory maintenance has two modes:
Live mode: On-the-job bookkeeping keeps memory healthy as work happens, and is the default; it is the first half of this document.
Hindsight mode: A retrospective pass treats the corpus (the memory layer) itself as the work product, and is the second half of this doc. A retrospective pass is due upon completing a substantial body of work, on upon request.

## Think and work in information vectors

**What is an information vector:**
An information vector is the smallest independently meaningful claim about a thing. It is an atomic unit in our current context. Can be thought of as "a statement" or "a claim."

An information vector nudges an agent's understanding or behavior in its direction.
How an information vector is written dictates how much weight the nudge has, ranging from subtle to aggressive.

Toy information vector examples include:
- "The webhook reached this exact endpoint."
- "Filesystem persistence is undecided."
- "The worker retries a failed job three times."
- "This approach was rejected because it created unacceptable operational work."
- "The database is Postgres."
- "We decided to rewrite the server to Rust because we couldn't get sufficient performance from the old Python implementation."

**The gist:**
- Every useful vector should have a clear epistemic state: current truth, validated capability, decision, constraint, open question, false claim, superseded claim, historical rationale, or raw evidence.
- Preserve historical rationale only when it prevents future confusion or repeated mistakes.
- When a claim's status cannot be established from the corpus, keep the uncertainty visible rather than guessing.
- A few distinguished vectors never lose relevance, because they are global and permanent — the project's purpose, the durable rules agents work under. The vast majority of vector do lose relevance; controlled forgetting is covered below.

**Misinformation is worse than missing information. Failure states to avoid:**
- A proposal is a proposal. It must not quietly read like a decision.
- A guess must not read like an observation.
- Distinguish a hypothetical or an assumption from an empirical observation: state a hypothetical's assumptions explicitly and write it in an advisory tone, so it cannot be misread as an assertion; Conversely, support an empirical observation with the minimal set of references.
- A narrow test must not inflate into a broad capability claim.
- Insufficient evidence is an asset that must be recorded proudly. It must not be swept under the rug.
- De-facto behavior (status-quo) must not be confused with an intentional, top-down constitution, unless such a canonical manifest exists.
- Overturned or disproved notions must be exposed or discarded.
- Etc.

---

## Live mode: Maintain memory while doing the work

When new work changes the project's model, update the relevant memory in the same unit of work. Identify the new vector, its epistemic state, and record it in its canonical home. Then find every vector it displaces and decay or remove it. ‘Controlled Forgetting’ below governs which.
Record at the narrowest truthful scope.

Retain enough reason to recover consequential decisions, but do not retell the whole path that produced them. The project should remember why it took an important turn without forcing every future agent to relive the conversation.

Tell the user when a decision or development has made previously written documentation stale.

Keep the docs the user told you to read for baseline context true to the present state.

## Metadata carries the why

Raw text covers the what. Metadata covers the why, how we got here, and what a thing relates to.

The conventions are `yy-mm-dd` filename prefixes; YAML frontmatter carrying at least `description: <one short phrase>` and `last_updated: yyyy-mm-dd hh:mm`; and Logseq-style `annotation:: ...` metadata inside the doc’s body on sections, paragraphs, blocks or individual items.

Four rules hold for every kind of doc:

1. Everything carries date and time at the minimum. Many recorded items deserve at least one further `something:: ...` annotation beyond the timestamp.
2. Metadata both annotates content and references other content, across time and space, describing relationships in their present true state. Bidirectional references — between files and between vectors — are good practice, and keeping them truthful takes frequent updating as the project evolves.
3. Do not record what is already recorded. Avoid duplicating information; see the MECE sections below.
4. Write annotations in a very terse, dense style.

There is no strict schema, deliberately. These docs are never parsed programmatically, so metadata should serve the content, the current truth, and the relationships first, and adapt its shape as the project and the real world change.

Small illustrations, to generalize from rather than copy:

- Asked to summarize `a.md` and `b.md` into `summary.md`, write `summary.md` with `description`, `last_updated`, and `based_on: [a.md, b.md]`, which records the semantic cause and effect.
- Told that approach B replaces approach A, record it in the ledger with `added:: mm-dd hh:mm` and `supersedes:: §{canonical approach A reference}`, add `superseded_by:: §{the new item}` everywhere approach A is specified, and give approach A its first decay pass. The moment B replaced it, its reason for being documented changed too — from the leading way to go, to history that helps trace how decisions evolved — so it no longer holds center stage.
- Add `context:: <a phrase or two answering the "wait, but why?" a reader will feel>` on a decision or state that looks unexpected.
- On encountering a stale vector, finish the reading you set out to do, then tell the user briefly.

## Three content-type homes

At a single directory level, three doc types own three disjoint content types, with source evidence subordinate to all of them.

**Ledger**, typically `LEDGER.md`.

- Content: events, decisions, why's, rationale, turn-of-events, hypothesis then versus now, empirical observations, disillusionments, successes, hard-won wisdom, battle scars, project-impacting real-world events, overturned decisions, commitments.
- Nature: timestamped and time-decaying, spanning N time slices — each vector happened at one of them.
- Style: terse and dense per entry, or ledgers blow up in volume.
- Maintenance: log small, short, dated items reflecting present progress. A dry but data-dense ledger gets a reader up to speed efficiently.

**Readme**, typically `README.md`.

- Content: the resulting present state — what-is and how-to.
- Nature: the whole document is a single time slice, the present moment. No history, not by hint or otherwise.
- Style: a little more detail per present-true vector. Your typical README.
- Maintenance: keep it faithful to current truth and project state. A README carrying stale vectors defies its own definition.

**Agent instructions**, `AGENTS.md`, with `CLAUDE.md` as a read-only symlink to it.

- Content: durable rules and context for how agents should work in the project. The system message.
- Style: as a readme.
- Maintenance: none by agents. The user maintains this file.

**Source evidence** lives in `meetings/`, `research/`, `references/`, and arbitrary `{topic}/` directories. It stays subordinate to canonical memory and must never masquerade as current guidance.

Use the project's existing structure when it already provides these roles. Do not create documents merely to satisfy these example names, and read the project's own `AGENTS.md` for conventions that extend or override them.

## Keep the corpus MECE across two axes

Every doc should be mutually exclusive and collectively exhaustive with its peers. Two cross-axis principles govern where a single vector lives:

1. A vector is owned by exactly one canonical *directory level*.
2. Within that owning level, each content-type home owns a distinct *lens* on it.

Together these are what "each vector has one authoritative home" means, and they are what makes progressive disclosure possible.

### Horizontal — same level, disjoint lenses

Each document at a level has one recognizable job, per the three homes above. When two sibling docs must touch a common vector, they split it into disjoint lenses rather than repeating it: the README's what and how-to, strictly over the present true state, versus the ledger's decisions, why's, and turn-of-events across the level's N time slices, each entry slim and to the point, avoiding repeating the README’s “what” lens.

A present, important vector may therefore appear in both the README and the late (present-moment) part of the LEDGER, and rarely also in `AGENTS.md`. That is legitimate functional overlap — the ledger records that a decision occurred while the README describes the resulting system. Semantic duplication is the problem: several passages independently claiming what the current truth is. The tail of a ledger and a README both describe the present moment, and that inherent overlap is tolerated but minimized. It must never be the same words twice.

### Vertical — one owning directory level

Ledgers live at multiple directory levels: the project root and each nested subdomain, each with its own `LEDGER.md`. A level's ledger records only two kinds of item.

**Sole ownership.** A vector squarely in that level's scope, of which the level is the only owner. At project level: "we're building a data-analysis AI agent for Avidor." In a `frontend` subdomain: "added RTL support."

**Connective tissue.** An overarching theme, decision, or intent that governs several children at once and exists *only* in the parent. More abstract, reads like a thought, does not drill down to files, and points down with `see:: child1, child2`. Root example: "AI work is versioned on one unified scale wherever it runs — lab or production — so performance stays comparable across time. `see::` agent-rig, frontend, deploy." Each child still records its own concrete versioning vector.

The owning level represents its vector in one, sometimes two, and rarely three of its content-type homes, per the horizontal rules: in the LEDGER if it is historically important, past or present; in the README if it is an important piece of the present true snapshot, or of the necessary how-to.

Non-owning levels, parents and children alike, never repeat a vector another level owns. The default is not to reference it at all. Only when a vector you do own is directly affected do you reference the owner thinly — its location, not its content.

Connective tissue is the one exception. If and only if two or more direct children own distinct vectors that interact or affect each other, the parent is responsible for defining the seam between them. That content is MECE with the child vectors: it describes only the seam. Its home follows a simple rule — if any of those child vectors lives in a child ledger, the connective tissue lives in the parent ledger; if all of them live in child readmes, it lives in the parent readme.

Two vertical anti-patterns:

- **False connective tissue** — inventing a parent theme over children that merely *resemble* one another, with no overarching intent binding them. No shared intent, no parent vector; each child keeps its own.
- **Parent as index** — a parent restating a child's vector verbatim ("added RTL, see frontend" while the frontend subdomain says the same). One vector written twice; the abstraction leaks. A parent records only what adds value not found below.

### The two-dimensional test

1. Does every useful vector have a home?
2. Does each vector have only one authoritative home — one owning level, and one lens per home within it?

Other documents may link to a vector or record that it changed. They must not independently maintain competing versions of the same current truth.
Optimize for a capable agent reaching the right model quickly and knowing where to update it next time, not for a perfect taxonomy.

--- 

## Controlled Forgetting

> So far, we have covered the desired shapes and hierarchies of a good memory layer. This section deals with the crucial act of continuously keeping the memory layer truthful to the present moment. As the present moment advances, so does the memory layer must adapt its center of gravity to what is *currently* true, by re-fitting the weights of the vectors it is made of, or remove them outright.

**What should be partially or fully forgotten — the gist:**
- Stale information.
- Disproportional shouting (over-emphasized) or unjustified possession of large textual real estate for something not as a big deal.
- Unjustified information duplication within and across the memory layer.
- Any combination of these three items.

### Old information must be decayed and ultimately removed

- All vectors lose relevance simply by living in the ledger for a while (aging).
- Vectors recording wrong things — mistakes made, decisions and assumptions overturned — should be removed, or in case decaying them to a gravestone directly helps understand the *why* behind current, true vectors, they should be replaced by their gravestones.

**Examples of what ages out; generalize, this is not a recipe:**

- A month-old "path X proved a dead end, so we chose path Y." That mattered a lot while we were still in the maze. Two months on, subsequent decision were built on having walked path Y, so it is ambiently apparent. Remembering that “X = dead end” might still help path Y click -> decay, don’t remove.
- "Windows Vista used to be called Longhorn before the release." Good to know before or at the time of release. A while after the release, it affects no decision and no agent run. It’s just noise -> remove. 
- A hypothesis that turned out wrong and was superseded by a truer one. Recently wrong, it explains why the new decision was taken; long since wrong, it is only noise -> remove.

**How to decay a vector.** Tone it down: dilute its detail, shorten it a little, weaken its footprint in the semantic space and its weight in the next reader's attention, calm down its Markdown formatting, de-fluff its writing. Make it decayed.

A vector can be decayed at most once. There is no second: past some irrelevancy threshold it is plainly removed. That threshold is not eager, but it’s not very conservative either.

Decay is not a disclaimer placed beside stale text. It means giving obsolete information less weight, attention, and real estate than an ordinary current vector. When even a small footprint is more than the vector is worth, remove it instead.
When history remains valuable, move it off the current-state surface and compress it to the reason future work still needs.

History earns its place when it explains a current constraint, prevents a likely repeated mistake, or preserves meaningful accountability. It does not survive merely because it once existed. Let project complexity set memory complexity: a small early project usually benefits from direct deletion, since there is little value in preserving the ancestry of every discarded thought, while a mature project may need more decision history, because surprising constraints, reversals, and institutional precedent affect future work.

**Some vectors must never be forgotten.** Durable battle scars and permanent operating context — "verify IAP fails closed before a data-bearing deploy" — are annotated `forget::never` with the user's consent and hold full weight indefinitely. Never decay or remove one. A vector that merely *looks* permanently relevant but carries no such marker is not yours to exempt: surface it to the user and let them decide.

### Do not start a yelling contest

A yelling contest begins when an agent wants to record a fresh vector, finds several pre-existing vectors that contradict it, and tries to overpower them with more detail, heavier emphasis, repetition, bold text, or all-caps. The corpus quickly becomes a room full of teenagers, each talking louder to become the center of attention.

Do not make the fresh vector louder, and do not out-repeat the old ones. Clear the space first: delete false claims, replace superseded present-state claims, compress valuable history into its proper historical home, and remove obsolete prominence. Then write the fresh vector calmly, at the ordinary length, detail, and emphasis it deserves — as if it had never had to compete.

---

### Evidence remains as narrow as the test  <!-- this section should be shortened. less text -->

A validation establishes only what was observed. One successful HTTP request does not prove unrestricted network access. One process launched under a user account does not prove arbitrary installation capability. One observed workflow does not prove that every case follows it.

Broader conclusions may be recorded, but label them as inferences or open assumptions. Do not let convenient language silently widen evidence.

### Open questions are first-class memory

An unresolved question is useful project state. State it once and keep it short. It should name the decision surface without prematurely designing the answer.

Supporting possibilities belong only when they materially explain why the question exists. A long speculative branch is not a better open question.

### Good memory reads like one informed mind

Current reality appears before history. Claims are precise about scope and certainty. Important rationale survives without taking over the page. Open questions are visibly unresolved. Failed assumptions do not linger as ambient possibilities. Links connect documents instead of prose duplicating them. The amount of documentation matches the project's actual complexity.

The governing test is:

> Could a capable new agent read this corpus once and proceed with approximately the same model of reality as the person maintaining the project — able to explain the present system, its important reasons, its validated boundaries, and its unresolved questions, without reconciling contradictory passages?

If the agent must reconcile contradictions, distinguish plans from decisions, or repeatedly discover which passages are obsolete, the memory system has passed its bookkeeping cost to every future session.

---

## Hindsight mode: Retrospective maintenance passes

A retrospective pass is an intentional effort to repair the project model after information has accumulated. The work is not a side effect of another task; the corpus itself is the task. Use this when asked to inspect, audit, clean up, reconcile, prune, or repair project memory: old decisions, ledgers, `AGENTS.md`, client docs, stale notes, superseded claims, or documentation that has grown louder and harder to trust over time.

The goal is not prettier documentation. It is a smaller, more trustworthy model of reality that a new agent can absorb without textual archaeology. Everything above is the standard this pass enforces; what follows is the procedure.

### Define success before editing

A successful pass leaves one coherent present truth, explicit open questions, narrowly stated evidence, and only the history that still pays rent. The corpus should contain no unresolved contradictions and no stale vector competing for attention with its replacement.

Match the ambition of the pass to the project. A young, simple project should usually become short and direct. A mature project may retain more precedent, but only where that precedent affects future judgment.

### Orient and bound the pass

Load the relevant client or project context before judging memory. If the project provides a context-loading skill or reference manifest — `load-client-context` or its equivalent — (re-)load it first. Read the project instructions and every core doc in full, then follow their Markdown references down that bounded graph. Always read the README, AGENTS and LEDGER trio in referenced subdirectories, even where the manifest does not list all three. Respect explicit exclusions — meeting transcriptions, generated runs and worlds, dependency directories — unless the user asks otherwise.

Search is useful for finding repeated language and suspected contradictions, but snippets cannot reveal the contract or authority of a whole document.

Based on what that context-gathering pass surfaced, define the maintenance boundary — an inclusion list and an exclusion list — before starting.

<!-- The few H3 sections below, up to (excluding) ‘Rewrite at ordinary volume’, repeat a lot of the information above. Should sharpen sometime -->

### Inventory and classify

First identify the existing document roles. Determine which surface represents present truth, which records decisions, which governs agent behavior, and which contains source evidence. Do not impose a new file taxonomy when the project already has a clear one.

Then inventory the information vectors and classify each: current truth, validated capability, decision, constraint, open question, false claim, superseded claim, useful historical rationale, or raw evidence. Where a claim's status cannot be established from the corpus, keep the uncertainty visible rather than guessing.

### Audit for forgetting failures

**Stale contradictions.** An older vector that a later, truer one has overtaken, yet which still reads as active. A healthy stale vector is either already partially decayed and carrying a meta note pointing at the newer truth, or else completely removed, metadata included. Find the ones that meet neither criterion.

**Yelling contests.** Find documents fighting themselves: a newer entry grown louder and heavier than its content warrants. The cause is usually a new item that superseded an old one without decaying or removing it, so the author over-built it to win back attention. Loudness is a tell, not a metric — do not mechanically equalize formatting. Make the semantic call about what is true now, what is historical, what still earns a small footprint, and what adds no value by existing and should therefore be plainly removed.

Both resolve the same way. The stale item shrinks to match how irrelevant it has become, or is plainly removed where even leaving a gravestone behind would add noise; and the newer one reads as ordinary again, as if it had never had to compete. The trap is doing only one of the two — de-shouting the loud new item while leaving the old one undecayed keeps the contradiction standing, now louder by comparison.

### Audit for MECE violations

Memory inevitably drifts out of MECE, on both axes. This is where you check that the two-category ledger rule and the three content-type homes still hold, applied recursively down the filesystem.

Check the horizontal axis first: does each document have one recognizable job, and do siblings sharing a vector split it into disjoint lenses? Move or remove vectors that violate those contracts. Merge documents when their distinction creates ceremony without a real semantic boundary.

Then check the vertical axis: does each useful vector have exactly one owning directory level? Replace duplicated claims with links or brief historical references. Look for the two anti-patterns — false connective tissue, and a parent acting as an index of its children. A ledger may say that a decision changed; it must not become a second current-state document.

### Diagnose before editing

Maintenance is semantic before it is editorial. Decide what the project should currently believe before deciding where sentences belong. Identify the stale vector, the newer truth, and the conflict between them before touching anything.

Prefer direct observation and explicit user decisions over earlier proposals or agent inferences. Preserve the boundary of each validation. When two credible sources still conflict and the resolution would materially change the project, surface the conflict to the user instead of choosing the more convenient story.

Decide per stale vector: delete, decay, or mark `forget::never` — the last is rare, and belongs to the user. Concretely:

1. Remove a false claim.
2. Replace a superseded present-state claim.
3. Reduce a consequential reversal to the shortest useful ledger entry.
4. Keep raw source material subordinate; do not let it masquerade as current guidance.
5. Convert unresolved design space into one concise open question.

Keep the scars and root-cause lessons that explain why the current state exists or that prevent a repeat of a meaningful mistake. Remove active-looking fragments that add nothing once the lesson is preserved. Respect `forget::never`, and escalate anything that looks permanent but carries no marker.

### Rewrite at ordinary volume

After contradictory vectors have been decayed or removed, write the surviving model in a calm voice. Do not compensate for past confusion with extra bold, repetition, warnings, or detail. The fresh truth should occupy exactly the space its own importance requires.

Prefer claim-shaped headings and connected prose. Use lists for genuine sets, procedures, or options, not as the default shape of thought. Preserve the user's language where it carries domain meaning, but remove conversational repetition and speculative padding.

Keep open questions short. Keep validations narrow. Keep rationale close enough to the decision that the next agent does not have to rediscover it.

### Verify and report

Re-read every edited document in full. Search the corpus for rejected terms, obsolete providers, old names, duplicated claims, and language that widens a validation beyond its evidence. Check internal links and document references. Then run the governing test above.

Report the outcome in terms of the model, not the editing activity: what is now canonical, what remains open, which stale vectors were removed or decayed, and whether any unresolved conflict still needs the user's judgment.

### Delegate to subagents

For a large memory surface, delegate bounded reading or comparison to subagents, fanning out across separate cohesive domains. Give them the project purpose and the maintenance question; do not seed them with guessed answers. The two useful shapes are agents-as-a-search-function and agents-as-a-diff-tool. You collect their results and remain the sole owner of judgment.

### Note: Retiring a whole body of knowledge is a different operation

"Whole body of knowledge" = controlled-forgetting at a sub-corpus scale, not individual docs.

When an entire plan, approach, or design era has been superseded and its documentation must be removed as a stratum rather than edited item by item, that is a distinct procedure — itemize across the affected docs, collapse near-duplicates so each idea has exactly one home, then delete or salvage against an explicit criterion. It is covered by the separate `deprecating-knowledge-body` reference, which is loaded only on explicit instruction.
