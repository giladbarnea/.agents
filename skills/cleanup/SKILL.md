---
name: cleanup
description: "Close out work: leave no loose system-resource ends and reclaim disk space. Work means any footprint on this machine's resources: more than negligible file-system changes, spun-up processes, and so on. Load and apply after each finished work milestone, even a partial one. Also load when the user wants system resources back, or when declining system resources affect your work."
last_updated: 2026-11-23
---
# Cleanup

Cleanup has three goals:
1. **No loose ends.** The next person or agent finds committed, pushed, documented work, and no stray processes, panes, forks or drafts.
2. **Disk space.** Reclaim every byte that is stale, superseded or rebuildable.
3. **Idle cost.** Nothing that is no longer needed keeps using CPU, memory or file activity.

**Span: everywhere you worked that left a footprint on this machine's resources, inside or outside the project.** Include leftovers from earlier sessions and teams, shared temp folders, and global caches your tools filled. Exclude protected items and anything a live session still needs.

## Domains

1. **Git:** dirty current tree, worktrees in progress or abandoned, unpushed branches, stashes, the object store.
2. **Live state:** processes, locks, terminal panes, agents and forks. Include live but idle ones: agent sessions and teammates, file watchers and indexers, browser instances, dev servers. Ask whether each is still needed and what it costs while idle.
3. **Documents:** promote desk or temp content that deserves a more canonical home up the project's directory tree. Consolidate the work docs where meaningful, otherwise delete. Fix pointers to stale entries. Low-key package what you've written while work was in-progress to make historical investigations in the future easier. A cleaned-up desk should have a much lower total line count than before.
3. **Documents:** Move desk content that deserves a more canonical home higher up the project's directory tree. Consolidate meaningful information in work docs; otherwise, delete them. Fix pointers to stale entries. Delete throwaway or one-off content and files you've written. Organize what you've written during the work to make future historical investigations easier. A cleaned-up desk should have a much lower total line count than before.
4. **Build outputs and caches:** compiled artifacts, packaged builds, and the caches of compilers, bundlers and engines.
5. **Containers and VMs:** containers, images, volumes, and the VM running them.
6. **Temporary areas:** temp folders, including `/tmp`, `/var/`* and `$TMPDIR`, scratchpads, run folders.
7. **Environments and tool caches.**

## Where load comes from

Not a recipe, just a taste. A few cases we've seen that caused resource hogs: fresh installs on every test run, agent sessions started in huge or busy folders, several parallel processes that kept indexing the same folder until it got out of control, and extensions that redid uncached work on every screen redraw in long sessions.

## Recommended method

1. Run the loose-ends checks and report them.
2. Measure everything: disk size, and CPU, memory, file activity, network activity, open ports and sockets, and GPU for processes, sampled over time. Rank by cost.
3. For each candidate, check what references it and what it rebuilds from.
4. Present one table: item, cost, rebuilds from, references, risk, default action. Get one approval.
5. Delete or stop, then report what was actually freed.
