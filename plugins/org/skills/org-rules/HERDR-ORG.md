---
updated: "2026-11-12 19-30 IST"
description: How the org maps onto Herdr and herdr-tree, and how agents read and change it
author: `herdr-tree` Lead
---

# herdr-tree: the org's record

herdr-tree records who leads each project, who owns what, and where each session runs. Read the org from it. Do not keep your own roster.

## Terms

1. Coordinator is herdr-tree's `coordinator` role (❖), Lead its `leader` role (★), and Owner its `owner` role (▲). Workers have no role. As teammates without panes, herdr-tree mostly does not see them.
2. A session's project is its manual assignment, else its git repository, else its directory. Each project has one Herdr workspace.
3. A session's identity is its harness plus its full session ID. A pane address (`w69:p2`) changes when panes move. Look it up just before you use it.

## Rules herdr-tree enforces

1. A project has at most one Coordinator. With exactly one Lead and no Coordinator, another Lead needs explicit intent: `--replace HARNESS:FULL_SESSION_ID` replaces that incumbent; `--add` keeps it. The popup offers Replace / Cancel / Add another Lead. With several Leads already, or a Coordinator, marking another Lead adds silently.
2. Leads and Coordinators lose their roles when their last known pane closes/exits, their agent is released, or their tab/workspace closes. Normal unset effects apply: attention reaches Gilad again, inks change, and history records `by: "herdr-tree"` with the causal `reason`. Server stop/crash, client detach and a missing pane in a poll never unset. Another known host keeps the same session reachable. Startup does not sweep existing closed declarations. Clearing, demoting or moving a Coordinator keeps every Lead and generates no announcement or new attention; only the lint reports missing coordination.
3. Moving a Lead preserves its declaration and leaves its peers behind. `project set` and `project clear` accept the same `--replace` / `--add` choice at the destination. Named replacement is checked again under the store lock before saving.
4. An Owner reports to the Lead in the same project that declared it, or a predecessor inherited through a named replacement, without rewriting `declared_by`. `--add` transfers no Owners. With one Lead and no Coordinator, the project alone determines its Owners; otherwise unmatched identities are null.
5. Owners' needs-me does not reach Gilad while their project has a Lead. With a Coordinator, Leads' needs-me is dropped too, not rolled up. Without one, Leads surface their own needs-me. Native Herdr blocked notifications are unchanged.
6. A migrating fork in another pane never inherits a project role or asks for it; its reachable parent keeps the declared role and the fork is an automatic detour. Pi `/new`, `/resume` or an in-place `/fork` to a different session unsets the previous project role and grants the replacement none. Fresh process startup, extension reload and same-ID resume release nothing, including after Herdr restarts.

## Reading the org

1. `herdr-tree org coordinator list`, `herdr-tree org leader list` and `herdr-tree org owner list` print JSON: project, harness, full session ID, label, pane address, workspace and status. Closed Coordinators, Leads and Owners are listed too, with no pane address. Each row also has `declared_at` and `declared_by`: `gilad`, or the declaring agent's harness and session ID (null before Nov 10 2026). Each Owner row also names its `lead` (`harness` and `session_id`), or null when unresolved.
2. `herdr-tree session list` prints every open session: pane, harness, session ID, role, suggested role, project, status, tags and annotation. Closed sessions are not listed.
3. `herdr-tree history [--pane <pane> | --session <id>]` prints role and project changes: what changed, when, and by whom. Automatic unreachable clears name their native event or Pi switch in `reason` and use `by: "herdr-tree"`.
4. `herdr-tree project list` prints the known projects.
5. `herdr-tree annotation get --pane <pane>` prints Gilad's note on a session.
6. `herdr-tree where "<what happened>"` finds a session by its content; `--passages` adds the matching passage. It costs money; ask first.

## Writing the org

1. A Lead marks each Owner it starts, right after starting it: `herdr-tree mark owner --pane <pane>`. Run it from the Lead's own pane: that records the Lead as `declared_by`, which is the stored link from Owner to Lead.
2. `herdr-tree project set <name or directory> --pane <pane>` assigns a project.
3. `herdr-tree annotation set "<text>" --pane <pane>` leaves a note on a session.
4. `herdr-tree mark open_concern --note "<what is pending>"` marks something pending.
5. Use `herdr-tree mark coordinator` to appoint a Coordinator, `clear` to unset it, and `mark leader` to appoint a Lead. Choose `--replace HARNESS:FULL_SESSION_ID` or `--add` for the one-Lead conflict; the flags are mutually exclusive. Re-marking an existing Lead is idempotent.
6. Only Gilad manually makes, replaces or ends a Coordinator or Lead. The event-driven unreachable-role clears in rule 2 are the automatic exception. The CLI does not enforce who makes manual changes; it records the actor in history. Do not change these roles unless Gilad asks.
7. Close herdr panes after their work is complete. This is not a destructive action anyway: roles, history and desks stay, and the session can be resumed.

## Talking between sessions

herdr-tree does not carry messages. Look up the address, read to check that it makes sense to prompt the target at that point (e.g. input box is empty, pane has no blocking dialogues, etc), then run `herdr agent prompt <pane> "[<your name>] <message>"`. A blocked target rejects it with `agent_blocked`. Retry later.

## Names

herdr-tree's naming rules, [~/dev/herdr-plugins/herdr-tree/docs/naming.md](https://github.com/giladbarnea/herdr-tree/blob/main/docs/naming.md), own session, pane, tab and workspace names. A Lead's session, pane and tab read `Lead`; a Coordinator's read `Coordinator`. Leads keep ★ and bold. Only a sole Lead without a Coordinator is bright white; every other Lead uses white `sublead` ink. The Coordinator stays bright. Working rows still pulse and stale rows darken.

Chief of Staff is reserved for a future system-wide role above Coordinators, or a project's sole Lead when no Coordinator exists. It is not implemented.
