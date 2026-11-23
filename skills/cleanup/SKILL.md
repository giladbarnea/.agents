---
name: cleanup
description: "Close out work: leave no loose system-resource ends and reclaim disk space. Work means any footprint on this machine's resources: more than negligible file-system changes, spun-up processes, and so on. Load and apply after each finished work milestone, even a partial one. Also load when the user wants system resources back, or when declining system resources affect your work."
last_updated: 2026-11-23
---
# Cleanup

Cleanup has two goals:
1. **No loose ends.** The next person or agent finds committed, pushed, documented work, and no stray processes, panes, forks or drafts.
2. **Disk space.** Reclaim every byte that is stale, superseded or rebuildable.

**Span: the whole project and its footprint on this machine, not only what you created.** Include leftovers from earlier sessions and teams, project temp folders, and global caches this project's tools filled. Exclude other projects, protected items, and anything a live session uses.

## Domains

1. **Git:** worktrees, unpushed branches, stashes, the object store.
2. **Live state:** processes, locks, terminal panes, agents and forks you started.
3. **Documents:** promote desk or temp content that belongs in the project. Consolidate or delete its periphery. Fix pointers to stale entries.
4. **Build outputs and caches:** compiled artifacts, packaged builds, and the caches of compilers, bundlers and engines.
5. **Temporary areas:** temp folders, scratchpads, run folders.
6. **Environments and tool caches.**

## Method

1. Run the loose-ends checks and report them.
2. Measure every candidate, project-wide and global. Rank by size.
3. For each candidate, check what references it and what it rebuilds from. Shared or cloned files can make a measured size overstate the gain.
4. Present one table: item, size, rebuilds from, references, risk, default action. Get one approval.
5. Delete, then report the space actually freed.
