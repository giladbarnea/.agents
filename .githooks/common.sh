#!/usr/bin/env bash

TARGETS=(
  ~/.pi/agent/AGENTS.md.j2
  ~/.codex/AGENTS.md.j2
  ~/.claude/CLAUDE.md.j2
  ~/.gemini/GEMINI.md.j2
)

can_prompt_for_render() {
  [[ -t 1 ]]
}

show_render_diff() {
  local actual="$1"
  local rendered="$2"

  if command -v comview >/dev/null 2>&1; then
    git --no-pager diff --no-index "$actual" "$rendered" | comview
  else
    DELTA_FEATURES="${DELTA_FEATURES} narrow" delta "$actual" "$rendered"
  fi
}

render_one() {
  local target="$1"
  local output="${target%.j2}"
  local rendered_tmp reply

  if ./render.py --dry-run "$target"; then
    return 0
  fi

  can_prompt_for_render || return 1

  printf 'Show diff? Y/N/R ' > /dev/tty
  read -r reply < /dev/tty || return 1

  case "$reply" in
    [Yy])
      rendered_tmp="$(mktemp)"
      ./render.py --stdout "$target" > "$rendered_tmp"
      show_render_diff "$output" "$rendered_tmp"
      rm -f "$rendered_tmp"

      printf 'Render %s now? Y/N ' "$output" > /dev/tty
      read -r reply < /dev/tty || return 1
      if [[ "$reply" == "Y" || "$reply" == "y" ]]; then
        ./render.py "$target" || return 1
      else
        printf '⊘ Skipped %s\n' "$output" > /dev/tty
      fi
      ;;
    [Rr])
      ./render.py "$target" || return 1
      ;;
    *)
      return 1
      ;;
  esac
}

render_agents_md() {
  local target

  for target in "${TARGETS[@]}"; do
    render_one "$target" || return 1
  done
}
