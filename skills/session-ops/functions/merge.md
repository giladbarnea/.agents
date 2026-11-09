# merge

```
Act = { askSessionsForHandoffs, catchUpOwners } | bool
  a bool sets both keys to that value
  default: false
```

```
merge(session_a, session_b, vector_1, vector_2, *, act=false) -> (owner_1, owner_2)
  input:  two sessions, each holding knowledge items
          two vectors that branch from shared ground
  output: sister owner session clades: each owner holds one vector and knows everything about it
          (or, when owners are not caught up, the packages that would do it)

  1. assign
     give each vector to the session that holds more of its open work
     and more of its expensive-to-rebuild knowledge (reasoning, evidence)

  2. export
     if act.askSessionsForHandoffs:
       each session writes a handoff
     else:
       read each session's transcript thoroughly yourself, important tool calls and results included
       fork yourself for this if reading the transcripts would overflow your own context
       extract the knowledge items into your context
     either way, a session's own items are the baseline of what it knows

  3. dedupe
     pool the items, keyed by idea
     keep the newest version of each idea; older versions show it was overruled
     items in a shared fork prefix are known to both: skip them
     two contradicting current versions are a conflict

  4. route
     an item about the other session's vector goes to that session
     an item about both vectors goes to both, each from its own angle
     drop what the receiver already knows
     conflicts and ownership gaps go to the human

  5. curate a package per owner that fully catches it up on what it doesn't know
     the package is handoff-shaped: the routed items, with what the owner already knows taken out
     (when handoffs exist, that is each handoff with those parts removed)

  6. deliver
     if act.catchUpOwners:
       point each owner to its package
       each owner acks, or names what is missing; a missing item goes back to step 4
     else:
       return the packages to your caller
```

Merging exposes governance questions that did not exist with one session, such as who writes shared memory or who owns names that cross vectors. They are a normal output of the route step: take them to the human.
