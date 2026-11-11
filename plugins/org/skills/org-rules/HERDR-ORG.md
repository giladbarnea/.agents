---
updated: "2026-11-11 16-45 IST"
description: How the org maps onto Herdr and herdr-tree, and how agents read and change it
author: `herdr-tree` Lead
---

# herdr-tree: the org's record

herdr-tree records who leads each project, who owns what, and where each session runs. Read the org from it. Do not keep your own roster.

## Terms

1. Lead is herdr-tree's `leader` role (★). Owner is its `owner` role (▲). Workers have no role. As teammates without panes, herdr-tree mostly does not see them.
2. A session's project is its manual assignment, else its git repository, else its directory. Each project has one Herdr workspace.
3. A session's identity is its harness plus its full session ID. A pane address (`w69:p2`) changes when panes move. Look it up just before you use it.

## Rules herdr-tree enforces

1. A project has at most one Lead. A new Lead replaces the old one only after an explicit confirmation of the old one. The confirmation must still match at the moment of replacement.
2. A Lead stays Lead until Gilad replaces it, changes its role, or moves it to another project. It stays Lead while its pane is closed and while a fork awaits succession.
3. Moving a Lead to another project moves its leadership there. The old project is left without a Lead. A Lead already in the destination needs the same confirmation as a replacement.
4. Owners belong to their project's Lead. The project is the only link.
5. While a project has a Lead, its Owners' needs-me does not reach Gilad. The Lead relays. Herdr still marks an Owner's pane blocked when the Owner shows a question screen. An Owner that asks Gilad directly breaks protocol.
6. When a Lead forks into a session that takes over its work, for example for compaction, the fork asks Gilad whether it should lead. Until he answers, the old Lead keeps leading. A Lead that forks tells Gilad, so he can confirm.

## Reading the org

1. `herdr-tree org leader list` and `herdr-tree org owner list` print JSON: project, harness, full session ID, label, pane address, workspace and status. Closed Leads and Owners are listed too, with no pane address. Each row also has `declared_at` and `declared_by`: `gilad`, or the declaring agent's harness and session ID (null before Nov 10 2026).
2. `herdr-tree session list` prints every open session: pane, harness, session ID, role, suggested role, pending succession, project, status, tags and annotation. Closed sessions are not listed.
3. `herdr-tree history [--pane <pane> | --session <id>]` prints role and project changes: what changed, when, and by whom.
4. `herdr-tree project list` prints the known projects.
5. `herdr-tree annotation get --pane <pane>` prints Gilad's note on a session.
6. `herdr-tree where "<what happened>"` finds a session by its content; `--passages` adds the matching passage. It costs money; ask first.

## Writing the org

1. A Lead marks each Owner it starts, right after starting it: `herdr-tree mark owner --pane <pane>`. Run it from the Lead's own pane: that records the Lead as `declared_by`, which is the stored link from Owner to Lead.
2. `herdr-tree project set <name or directory> --pane <pane>` assigns a project.
3. `herdr-tree annotation set "<text>" --pane <pane>` leaves a note on a session.
4. `herdr-tree mark open_concern --note "<what is pending>"` marks something pending.
5. Replacing a Lead from the CLI fails unless it names the old Lead: `--replace HARNESS:FULL_SESSION_ID`. The error shows the value to pass.
6. Only Gilad makes, replaces or ends a Lead. herdr-tree does not enforce this: the CLI accepts these changes from an agent's pane and records the agent as `by` in `history`. Do not make them unless Gilad asks.
7. Close herdr panes after their work is complete. This is not a destructive action anyway: roles, history and desks stay, and the session can be resumed.

## Talking between sessions

herdr-tree does not carry messages. Look up the address, read to check that it makes sense to prompt the target at that point (e.g. input box is empty, pane has no blocking dialogues, etc), then run `herdr agent prompt <pane> "[<your name>] <message>"`. A blocked target rejects it with `agent_blocked`. Retry later.

## Names

herdr-tree's naming rules, [~/dev/herdr-plugins/herdr-tree/docs/naming.md](https://github.com/giladbarnea/herdr-tree/blob/main/docs/naming.md), own session, pane, tab and workspace names. A Lead's session, pane and tab read `Lead`.
