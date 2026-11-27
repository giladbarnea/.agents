---
last_updated: 2026-11-27T11-44
---

# Send a command to an open Pi session

Run these scripts from `~/.agents/skills/herdr/scripts/` or use their full paths. They require `herdr` and `uv` on `PATH`.

```text
reload-session.sh TARGET
set-model.sh TARGET --model PROVIDER/MODEL
set-thinking.sh TARGET --level LEVEL
send-session-command.sh TARGET --prompt COMMAND
```

**`TARGET` is required.** Use `self` to resolve `$PI_SESSION_ID`, a full Pi session UUID, or a Herdr pane address such as `wBF:p1D`. Run inside Herdr. The scripts require one open, file-backed Pi leading the pane's foreground process group; its children (extension helpers, teammates) are fine. They refuse drafts, blocked panes and ambiguous targets. Do not type into the target while a script runs. The preflight and submission are separate Herdr calls.

| Flag | Default timeout | If the target is working |
|---|---:|---|
| Neither flag or `--wait-for-idle` | 300 seconds | Wait for idle or done before sending. |
| `--no-wait-for-idle` | 30 seconds | Refuse immediately without sending. |

Use `--timeout SECONDS` to override either default. The deadline covers preflight, idle wait, submission and verification. An agent mid-work can take 5–10 minutes to settle.

**From inside a running Pi turn, use `self`** (for example, `reload-session.sh self`). By default the script schedules a detached worker and returns immediately. End your turn so the worker can run, then read the result with the `cat` command in the scheduling receipt. An empty log means the worker has not reported a result yet. Wait for that result before requesting another change. `self --no-wait-for-idle` still refuses while the turn is running; an explicit UUID or pane address for the running caller also refuses instead of waiting on itself.

**Exit `0` means success for synchronous calls, but only scheduling for a running `self`. Exit `1` means refusal, error or timeout.** Invalid arguments print usage and the specific error to stderr before any Herdr call. The output (or log for a scheduled call) reports the requested and observed settings. Values that could not be checked are `unknown`. After a timeout, inspect the session before retrying. Pi may have applied the command.

- `reload-session.sh` checks for a fresh Pi reload confirmation.
- `set-model.sh` uses `/model PROVIDER/MODEL` and checks the exact native selection. Pi may change the thinking level when changing models. Use `set-thinking.sh` if you need a specific level. If Pi opens a picker instead of switching, the script leaves it open and does not select a row.
- `set-thinking.sh` uses `/thinking LEVEL` and checks the resulting level. Neither settings wrapper saves global defaults.
- `send-session-command.sh` accepts one line of text. It verifies Herdr submitted it, not that Pi applied it or finished a turn. Prefer the specific wrappers for the three supported operations.
