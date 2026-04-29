---
name: run-interactive
description: Run interactive CLI workflows (wizards, auth prompts, TUI menus) requiring stdin. Uses tmux for precise screen capture, state reading, and keystroke injection.
---

# run-interactive

Use `tmux` for interactive CLI processes (`npm init`, `aws configure`, passwords). `tmux` handles ANSI natively, supports full-screen TUIs, and prevents auto-closures.

## Primary Method: `tmux`

Launch background shell, inject commands, read pane state, send keystrokes.

### 1. Init
```bash
S="wizard_1"
tmux kill-session -t "$S" 2>/dev/null || true
tmux new-session -d -s "$S" -c ./
tmux send-keys -t "$S" "npm init" C-m
```

### 2. Read State
```bash
tmux capture-pane -t "$S" -p
```
*Wait ~0.5s after input before capturing. Allows UI render.*

### 3. Send Input
```bash
tmux send-keys -t "$S" "text_input" C-m  # string + Enter
tmux send-keys -t "$S" C-m               # default (Empty Enter)
tmux send-keys -t "$S" Up Down TAB       # Menu nav / Completion
tmux send-keys -t "$S" C-c               # SIGINT (Cancel)
```

### 4. Verify & Cleanup
```bash
tmux send-keys -t "$S" "echo EXIT_CODE:\$?" C-m
tmux capture-pane -t "$S" -p
tmux kill-session -t "$S"
```

---

## Fallback: `driver.py`

Use `scripts/driver.py` if `tmux` unavailable. Uses OS heuristics to log blocking states.

1. **Start:** `python3 ${__dirname}/scripts/driver.py <id> <cmd> &`
2. **Read log:** `cat /tmp/interactive_<id>.log` (Poll for `[AWAIT]`)
3. **Send input:** `printf 'value\n' > /tmp/interactive_<id>.in`
4. **Loop:** Repeat 2-3 until `[EXIT:code]`.
