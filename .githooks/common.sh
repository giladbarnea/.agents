#!/usr/bin/env bash

can_prompt_for_render() {
  [[ -t 1 ]]
}

render_all_agents_md() {
  local targets=(
    ~/.pi/agent/AGENTS.md.j2
    ~/.codex/AGENTS.md.j2
    ~/.claude/CLAUDE.md.j2
    ~/.gemini/GEMINI.md.j2
  )
  local target

  for target in "${targets[@]}"; do
    ./render.py "$target" || return 1
  done
}

render_agents_md() {
  local targets=(
    ~/.pi/agent/AGENTS.md.j2
    ~/.codex/AGENTS.md.j2
    ~/.claude/CLAUDE.md.j2
    ~/.gemini/GEMINI.md.j2
  )
  local target
  local reply

  for target in "${targets[@]}"; do
    if ! ./render.py --dry-run "$target"; then
      if ! can_prompt_for_render; then
        return 1
      fi

      printf 'Render all .md.j2 files now? Y/N ' > /dev/tty
      read -r reply < /dev/tty || return 1
      [[ "$reply" == "Y" || "$reply" == "y" ]] || return 1
      render_all_agents_md || return 1
      exec "$0"
    fi
  done
}
