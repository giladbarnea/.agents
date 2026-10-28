---
name: cleanup
description: "Cleanup best practices. Load after work is finished."
last_updated: 2026-10-28
---
Clean up after yourself. Is there a Git worktree to merge, or unpushed work? Are there files, scripts, drafts, or junk that need to be deleted? Are there things in temporary directories or work desks that should be promoted to become an official part of the project, and perhaps with files in their periphery consolidated or thrown away? Terminal multiplexer windows you opened that are no longer needed? Subagents/forks which the harness keeps technically "active" unless shut down explicitly? Artifacts (build, etc), bloated caches, or environments that are no longer needed (global or local alike)? Will a `git -C /Users/giladbarnea/clients repack -a -d --cruft` make a difference and won’t hurt anything?
Tell and confirm with the user.
