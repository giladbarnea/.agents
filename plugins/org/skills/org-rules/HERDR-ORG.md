---
updated: "2026-11-12 18-40 IST"
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
2. Leads and Coordinators keep their roles until Gilad deliberately replaces them, changes their roles, or moves them to another project. Closure and forks never transfer a project role. Clearing, demoting or moving a Coordinator keeps every Lead and raises no announcement, question or generated attention. Only the lint reports several Leads without a Coordinator, offering appoint Coordinator or clear all but one.
3. Moving a Lead preserves its declaration and leaves its peers behind. `project set` and `project clear` accept the same `--replace` / `--add` choice at the destination. Named replacement is checked again under the store lock before saving.
4. An Owner reports to the Lead in the same project that declared it, or a predecessor inherited through a named replacement, without rewriting `declared_by`. `--add` transfers no Owners. With one Lead and no Coordinator, the project alone determines its Owners; otherwise unmatched identities are null.
5. Owners' needs-me does not reach Gilad while their project has a Lead. With a Coordinator, Leads' needs-me is dropped too, not rolled up. Without one, Leads surface their own needs-me. Native Herdr blocked notifications are unchanged.
6. A migrating fork of a declared Lead or Coordinator is an ordinary automatic detour, even across project assignments. Its parent keeps the declared role. There is no succession question, generated attention or leadership suggestion; deliberate named replacement remains available.

## Reading the org

1. `herdr-tree org coordinator list`, `herdr-tree org leader list` and `herdr-tree org owner list` print JSON: project, harness, full session ID, label, pane address, workspace and status. Closed Coordinators, Leads and Owners are listed too, with no pane address. Each row also has `declared_at` and `declared_by`: `gilad`, or the declaring agent's harness and session ID (null before Nov 10 2026). Each Owner row also names its `lead` (`harness` and `session_id`), or null when unresolved.
2. `herdr-tree session list` prints every open session: pane, harness, session ID, role, suggested role, project, status, tags and annotation. Closed sessions are not listed.
3. `herdr-tree history [--pane <pane> | --session <id>]` prints role and project changes: what changed, when, and by whom.
4. `herdr-tree project list` prints the known projects.
5. `herdr-tree annotation get --pane <pane>` prints Gilad's note on a session.
6. `herdr-tree where "<what happened>"` finds a session by its content; `--passages` adds the matching passage. It costs money; ask first.

## Writing the org

1. A Lead marks each Owner it starts, right after starting it: `herdr-tree mark owner --pane <pane>`. Run it from the Lead's own pane: that records the Lead as `declared_by`, which is the stored link from Owner to Lead.
2. `herdr-tree project set <name or directory> --pane <pane>` assigns a project.
3. `herdr-tree annotation set "<text>" --pane <pane>` leaves a note on a session.
4. `herdr-tree mark open_concern --note "<what is pending>"` marks something pending.
5. Use `herdr-tree mark coordinator` to appoint a Coordinator, `clear` to unset it, and `mark leader` to appoint a Lead. Choose `--replace HARNESS:FULL_SESSION_ID` or `--add` for the one-Lead conflict; the flags are mutually exclusive. Re-marking an existing Lead is idempotent.
6. Only Gilad makes, replaces or ends a Coordinator or Lead. herdr-tree does not enforce this: the CLI accepts these changes from an agent's pane and records the agent as `by` in `history`. Do not make them unless Gilad asks.
7. Close herdr panes after their work is complete. This is not a destructive action anyway: roles, history and desks stay, and the session can be resumed.

## Talking between sessions

herdr-tree does not carry messages. Look up the address, read to check that it makes sense to prompt the target at that point (e.g. input box is empty, pane has no blocking dialogues, etc), then run `herdr agent prompt <pane> "[<your name>] <message>"`. A blocked target rejects it with `agent_blocked`. Retry later.

## Names

herdr-tree's naming rules, [~/dev/herdr-plugins/herdr-tree/docs/naming.md](https://github.com/giladbarnea/herdr-tree/blob/main/docs/naming.md), own session, pane, tab and workspace names. A Lead's session, pane and tab read `Lead`; a Coordinator's read `Coordinator`. Leads keep ★ and bold. Only a sole Lead without a Coordinator is bright white; every other Lead uses white `sublead` ink. The Coordinator stays bright. Working rows still pulse and stale rows darken.

Chief of Staff is reserved for a future system-wide role above Coordinators, or a project's sole Lead when no Coordinator exists. It is not implemented.
