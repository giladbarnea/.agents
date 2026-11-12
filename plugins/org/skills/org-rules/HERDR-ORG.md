---
updated: "2026-11-12 17-05 IST"
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

1. A project has at most one Coordinator. Without one it has at most one Lead; with one it may have several Leads. Replacing a Coordinator or a specific Lead requires explicit confirmation of that incumbent, checked again at the moment of replacement. Under a Coordinator, marking another Lead adds it without replacing its peers.
2. Leads and Coordinators keep their roles until Gilad replaces them, changes their roles, or moves them to another project. Closing a pane or awaiting succession does not end the role. A Coordinator cannot be cleared, demoted or moved away while that would leave more than one Lead behind; clear all but one Lead first.
3. Moving a Lead to another project moves its leadership there. The old project is left without a Lead. A Lead already in the destination needs the same confirmation as a replacement.
4. An Owner reports to the Lead in the same project that declared it, or its confirmed successor: named replacement inherits predecessor identities transitively without rewriting `declared_by`. Without a Coordinator, the project is the link and every Owner reports to its sole Lead regardless of declarer. With one, an unmatched identity is null, never guessed.
5. While a project has a Lead, its Owners' needs-me does not reach Gilad. With a Coordinator, the Leads report to it and it reports to Gilad; both Owners' and Leads' needs-me is dropped, not rolled up. The Coordinator prioritizes and relays with less judgment-calling than a Lead. Native Herdr blocked notifications are unchanged. Pending role-succession questions still reach Gilad.
6. When a Lead or Coordinator forks into a session that takes over its work in the same project, for example for compaction, the fork asks Gilad whether it should succeed. Until he answers, the old session keeps its role. Yes replaces that specific predecessor; No makes the fork a detour. The originating session tells Gilad, so he can confirm.

## Reading the org

1. `herdr-tree org coordinator list`, `herdr-tree org leader list` and `herdr-tree org owner list` print JSON: project, harness, full session ID, label, pane address, workspace and status. Closed Coordinators, Leads and Owners are listed too, with no pane address. Each row also has `declared_at` and `declared_by`: `gilad`, or the declaring agent's harness and session ID (null before Nov 10 2026). Each Owner row also names its `lead` (`harness` and `session_id`), or null when unresolved.
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
5. Use `herdr-tree mark coordinator` to appoint a Coordinator, `clear` to unset it, and `mark leader` to appoint a Lead. A replacement fails unless it names the old session with `--replace HARNESS:FULL_SESSION_ID`; the error shows the value to pass.
6. Only Gilad makes, replaces or ends a Coordinator or Lead. herdr-tree does not enforce this: the CLI accepts these changes from an agent's pane and records the agent as `by` in `history`. Do not make them unless Gilad asks.
7. Close herdr panes after their work is complete. This is not a destructive action anyway: roles, history and desks stay, and the session can be resumed.

## Talking between sessions

herdr-tree does not carry messages. Look up the address, read to check that it makes sense to prompt the target at that point (e.g. input box is empty, pane has no blocking dialogues, etc), then run `herdr agent prompt <pane> "[<your name>] <message>"`. A blocked target rejects it with `agent_blocked`. Retry later.

## Names

herdr-tree's naming rules, [~/dev/herdr-plugins/herdr-tree/docs/naming.md](https://github.com/giladbarnea/herdr-tree/blob/main/docs/naming.md), own session, pane, tab and workspace names. A Lead's session, pane and tab read `Lead`; a Coordinator's read `Coordinator`. Leads keep ★ and bold; under a Coordinator they lose bright white, which belongs to ❖. Working rows still pulse and stale rows darken.

Chief of Staff is reserved for a future system-wide role above Coordinators, or a project's sole Lead when no Coordinator exists. It is not implemented.
