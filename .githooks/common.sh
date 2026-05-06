#!/usr/bin/env bash

render_agents_md() {
  local targets=(
    ~/.pi/agent/AGENTS.md.j2
    ~/.codex/AGENTS.md.j2
    ~/.claude/CLAUDE.md.j2
    ~/.gemini/GEMINI.md.j2
  )
  for target in "${targets[@]}"; do
    ./render.py --dry-run "$target" || exit 1
  done
}
