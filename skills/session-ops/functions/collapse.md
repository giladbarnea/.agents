# collapse

```
collapse(sessions) -> active sessions
  input:  sessions in scope, such as those open in one Herdr workspace
  output: only the active sessions, each standing for its inactive ancestors too

  trace each session's mechanical ancestry with ~/top/ANCESTRY.md
  fold each inactive ancestor into its topmost active descendant:
    that descendant now holds the ancestor's ideas
  ancestors outside the scope count only through the descendants they fold into
```

Touches nothing.
