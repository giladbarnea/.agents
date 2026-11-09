# consolidate

Calls [`collapse`](collapse.md) and [`merge`](merge.md).

```
Act = { askSessionsForHandoffs, catchUpOwners, closeDonorPanes, renameDonors } | bool
  a bool sets all four keys to that value
  default: false
  askSessionsForHandoffs and catchUpOwners pass through to merge
```

```
consolidate(sessions, vectors, *, act=false) -> sister owner session clades
  sessions = collapse(sessions)
  the tournament: fold the sessions pairwise through merge(..., act=act)
  after each merge, the stronger candidate keeps each vector
  the losing session's knowledge flows to the owners through merge

  if act.renameDonors:
    suffix each donor's session name with [absorbed into <first two groups of its owner's session ID>]

  if act.closeDonorPanes:
    close each donor's pane; keep its session file
  else:
    give each owner session its own tab
    apply ~/dev/herdr-plugins/herdr-tree/docs/naming.md
```
