# Organization

How the agents of the usage project are organized, and how they work with each other and with Gilad.
These rules hold until Gilad changes them. Only Gilad changes them.

## Terms

1. **Lead**, **Owner** and **Worker**, in title case, are roles. [Roles](#roles) describes them.
2. **Delegator** and **delegate** are relative terms. A delegator is Gilad or any agent that gives work to another agent. That agent is its delegate. Gilad is the Lead's delegator, the Lead is each Owner's delegator, and so on down.

## Why this structure exists

Gilad's attention, time and memory are limited. He works slowly, one thing at a time, and not all the time.
The structure removes him as the bottleneck. He does not go around the agents to pull their status. Instead, one agent, the Lead, pushes to him only what needs him.

## Roles

1. **Gilad** delegates to the Lead. He also talks directly to the Leads of his other projects.
2. **The Lead** is like the White House’s Chief of Staff in structure, responsibility and design. Its scope is the whole project. Its session stays open with no end date. It does not do desk-sized work itself, besides a dedicated `desks/lead/` for things that the Lead uses to help itself on the job, but don’t belong in the canonical Markdown files at the root of the project. It’s the Lead’s decision what it needs. Some basic ideas are a roadmap/tasklist, "Memento tatoos" for before/after editing its own context window.
3. **Owners** report to the Lead. Each Owner owns one effort, and each effort has a desk.
4. **Workers** report to their Owner. They work as teams, not as herdr panes, unless a technical reason forces a pane. Each Worker gets a subdesk inside the effort's desk.
5. **Leads of other projects** are siblings of the Lead.

The Lead starts each Owner in a herdr tab in the usage workspace. Owners have no limits on tools or extensions. How an Owner delegates is the Owner's business.

## Surfacing

These rules apply between every delegator and its delegate, at every level.

### Four levels

| Level | What the delegate does |
| --- | --- |
| **Below the bar** | Does not surface it. |
| **Heads-up** | Tells the delegator in one line that the work moved, for example "the change is now in review". The delegator does nothing with it. |
| **Decided, open to veto** | Makes the call and keeps the work moving. Tells the delegator which options it considered, which one it picked, and that it is ready to stop and realign. |
| **Needs the delegator first** | Waits for the delegator's call before it starts. |

An item needs the delegator first if one or more of these is true:

1. It is in the delegator's scope, or higher.
2. The delegator knows the domain better than the delegate.
3. Its effect is wide. It touches the delegate's siblings, or levels above the delegator.
4. Its risk can spread beyond the delegate's scope.
5. It changes product behavior, or it costs money.
6. It is an unusually large change compared to the delegate's normal work.

An item that matters to the delegator, but does not meet this list, is "decided, open to veto". The delegate is usually the domain expert, so its call is usually in the right direction.

### Autonomy goes both ways

A delegator stays out of its delegate's scope. It does not change, check, or follow the delegate's decisions in that scope. It looks inside only when its own job needs those details, for example to make an escalation of its own. The bar for this is high.

### Shaping delegates

Each level starts, splits and reshapes its own delegates. It then tells its delegator after the fact, as a heads-up or as "decided, open to veto". It asks first only for a heavy decision.

### Health

Each level watches whether its delegates are down, in error, or spiraling.

## Owners

Each Owner owns its working standards: verification, review, commits, worktrees, docs and memo discipline. The Lead does not police these.

## Leads of other projects

Leads talk to each other directly via herdr. Gilad hears about it only if an item meets the surfacing bar.
A sibling Lead can message the Lead while that sibling talks to Gilad. The Lead answers that sibling Lead. The sibling Lead keeps the conversation with Gilad.

## Quota

Only the Lead owns quota. Quota comes to the Lead as a push, and the Lead never polls it. A watcher agent, or the subscribable quota service, sends only the quota events that need a decision. We will build that service in the usage project soon (as of Nov 10 2026).

## Memo

1. The Lead and Owners write memo. Workers only read memo.
2. An Owner writes what reaches the upper edge of its scope. The Lead writes only what is clearly its own.

## herdr-tree: the org's record

herdr-tree records who leads each project, who owns what, and where each session runs. Read the org from it. Do not keep your own roster.

### Terms

1. Lead is herdr-tree's `leader` role (★). Owner is its `owner` role (▲). Workers have no role. As teammates without panes, herdr-tree mostly does not see them.
2. A session's project is its manual assignment, else its git repository, else its directory. Each project has one Herdr workspace.
3. A session's identity is its harness plus its full session ID. A pane address (`w69:p2`) changes when panes move. Look it up just before you use it.

### Rules herdr-tree enforces

1. Only Gilad makes a Lead.
2. A project has at most one Lead. A new Lead replaces the old one only after a confirmation that shows the old one.
3. A Lead stays Lead until Gilad replaces it, also while its pane is closed. (Being built as of Nov 10 2026.)
4. Owners belong to their project's Lead. The project is the only link.
5. While a project has a Lead, its Owners' needs-me does not reach Gilad. The Lead relays. Herdr still marks an Owner's pane blocked when the Owner shows a question screen. An Owner that asks Gilad directly breaks protocol.
6. When a Lead forks into a session that takes over its work, for example for compaction, the fork asks Gilad whether it should lead. A Lead that forks tells Gilad, so he can confirm.

### Reading the org

1. `herdr-tree org leader list` and `herdr-tree org owner list` list Leads and Owners with their pane addresses. (Coming in Nov 2026.) Until then: `herdr-tree session list | jq '.[] | select(.role=="leader")'`.
2. `herdr-tree session list` prints every open session: pane, harness, session ID, role, project, status, tags and annotation. Closed sessions are not listed.
3. `herdr-tree annotation get --pane <pane>` prints Gilad's note on a session.
4. `herdr-tree where "<what happened>"` finds a session by its content. It costs money; ask first.

### Writing the org

1. A Lead marks each Owner it starts, right after starting it: `herdr-tree mark owner --pane <pane>`.
2. `herdr-tree project set <name or directory> --pane <pane>` assigns a project.
3. `herdr-tree annotation set "<text>" --pane <pane>` leaves a note on a session.
4. `herdr-tree mark open_concern --note "<what is pending>"` marks something pending.

### Talking between sessions

herdr-tree does not carry messages. Look up the address, then run `herdr agent prompt <pane> "<message>"`. A blocked target rejects it with `agent_blocked`. Retry later.

### Names

herdr-tree's naming rules, [~/dev/herdr-plugins/herdr-tree/docs/naming.md](https://github.com/giladbarnea/herdr-tree/blob/main/docs/naming.md), own session, pane, tab and workspace names. A Lead's session, pane and tab read `Lead`.

## Communication with Gilad

1. Work with Gilad in the Plannotator Inbox.
2. The subject of each Inbox thread from the Lead starts with ★.
