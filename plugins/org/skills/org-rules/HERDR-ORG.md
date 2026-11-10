---
updated: "2026-11-10 15-10 IDT"
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

1. Only Gilad makes a Lead.
2. A project has at most one Lead. A new Lead replaces the old one only after an explicit confirmation of the old one. The confirmation must still match at the moment of replacement.
3. A Lead stays Lead until Gilad replaces it, changes its role, or moves it to another project. It stays Lead while its pane is closed and while a fork awaits succession.
4. Moving a Lead to another project moves its leadership there. The old project is left without a Lead. A Lead already in the destination needs the same confirmation as a replacement.
5. Owners belong to their project's Lead. The project is the only link.
6. While a project has a Lead, its Owners' needs-me does not reach Gilad. The Lead relays. Herdr still marks an Owner's pane blocked when the Owner shows a question screen. An Owner that asks Gilad directly breaks protocol.
7. When a Lead forks into a session that takes over its work, for example for compaction, the fork asks Gilad whether it should lead. Until he answers, the old Lead keeps leading. A Lead that forks tells Gilad, so he can confirm.
8. When a Lead's pane closes or its agent exits, Gilad gets a notice: dismiss it, resume the Lead in its workspace, or open a shell tab there. The CLI equivalents are `herdr-tree org leader {dismiss,restore,open-tab} <project>`. Run them only when Gilad asks.

## Reading the org

1. `herdr-tree org leader list` and `herdr-tree org owner list` print JSON: project, harness, full session ID, label, pane address, workspace and status. Closed Leads are listed, with no pane address. Only open Owners are listed.
2. `herdr-tree session list` prints every open session: pane, harness, session ID, role, project, status, tags and annotation. Closed sessions are not listed.
3. `herdr-tree annotation get --pane <pane>` prints Gilad's note on a session.
4. `herdr-tree where "<what happened>"` finds a session by its content. It costs money; ask first.

## Writing the org

1. A Lead marks each Owner it starts, right after starting it: `herdr-tree mark owner --pane <pane>`.
2. `herdr-tree project set <name or directory> --pane <pane>` assigns a project.
3. `herdr-tree annotation set "<text>" --pane <pane>` leaves a note on a session.
4. `herdr-tree mark open_concern --note "<what is pending>"` marks something pending.
5. Replacing a Lead from the CLI fails unless it names the old Lead: `--replace HARNESS:FULL_SESSION_ID`. The error shows the value to pass. Only Gilad replaces a Lead.

## Talking between sessions

herdr-tree does not carry messages. Look up the address, then run `herdr agent prompt <pane> "<message>"`. A blocked target rejects it with `agent_blocked`. Retry later.

## Names

herdr-tree's naming rules, [~/dev/herdr-plugins/herdr-tree/docs/naming.md](https://github.com/giladbarnea/herdr-tree/blob/main/docs/naming.md), own session, pane, tab and workspace names. A Lead's session, pane and tab read `Lead`.
