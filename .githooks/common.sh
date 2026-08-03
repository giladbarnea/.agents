#!/usr/bin/env bash

GITHOOKS_DIRECTORY="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPOSITORY_ROOT="$(cd "$GITHOOKS_DIRECTORY/.." && pwd)"
source "$GITHOOKS_DIRECTORY/runtime-skills.sh"

TARGETS=(
  ~/.pi/agent/AGENTS.md.j2
  ~/.codex/AGENTS.md.j2
  ~/.claude/CLAUDE.md.j2
  ~/.gemini/GEMINI.md.j2
)

SKILL_PROVIDERS=(
  "$HOME/.claude/skills"
  "$HOME/.codex/skills"
  "$HOME/.gemini/skills"
  "$HOME/.pi/agent/skills"
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

  printf 'Show diff? Y/N/R ' >/dev/tty
  read -r reply </dev/tty || return 1

  case "$reply" in
  [Yy])
    rendered_tmp="$(mktemp)"
    ./render.py --stdout "$target" >"$rendered_tmp"
    show_render_diff "$output" "$rendered_tmp"
    rm -f "$rendered_tmp"

    printf 'Render %s now? Y/N ' "$output" >/dev/tty
    read -r reply </dev/tty || return 1
    if [[ "$reply" == "Y" || "$reply" == "y" ]]; then
      ./render.py "$target" || return 1
    else
      printf '⊘ Skipped %s\n' "$output" >/dev/tty
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

# Renders the in-repo base AGENTS.md.j2 (committed) plus each external
# provider target. Pass "stage" to git-add the in-repo base render
# (pre-commit only).
render_agents_md() {
  local stage="${1:-}"
  local target

  render_one AGENTS.md.j2 || return 1
  [[ -n "$stage" ]] && git add AGENTS.md

  for target in "${TARGETS[@]}"; do
    render_one "$target" || return 1
  done
}

# Joins provider short-names into a brace-expansion summary rooted at $HOME,
# e.g. (claude codex) -> "$HOME/.{claude,codex}", (claude) -> "$HOME/.claude".
join_braced() {
  local IFS=,
  if (($# == 1)); then
    printf '%s/.%s' "$HOME" "$1"
  else
    printf '%s/.{%s}' "$HOME" "$*"
  fi
}

# Idempotently point <link> at <target> (an absolute path). Fails rather than
# placing a nested symlink inside a concrete destination.
ensure_symlink() {
  local target="$1"
  local link="$2"

  [[ -L "$link" && "$(readlink "$link")" == "$target" ]] && return 0
  [[ ! -e "$link" || -L "$link" ]] || {
    printf '✗ Refusing to link over non-symlink destination: %s\n' "$link" >&2
    return 1
  }
  ln -sfn "$target" "$link" || {
    printf '✗ Failed to link %s → %s\n' "$target" "$link" >&2
    return 1
  }
}

link_skill() {
  local skill_directory="$1"
  shift
  local skill_name="$(basename "$skill_directory")"
  local provider short
  local -a linked

  linked=()
  for provider in "$@"; do
    short="${provider#"$HOME"/}"
    short="${short%%/*}"
    short="${short#.}"
    ensure_symlink "$skill_directory" "$provider/$skill_name" || return 1
    linked+=("$short")
  done

  printf '✓ Linked %s → %s\n' "$skill_name" "$(join_braced "${linked[@]}")" >&2
}

is_runtime_skill_path() {
  local skill_path="$1"
  local registered_skill_path

  for registered_skill_path in "${RUNTIME_SKILL_PATHS[@]}"; do
    [[ "$registered_skill_path" == "$skill_path" ]] && return 0
  done
  return 1
}

# Compiles each registered runtime skill immediately before exposing it. Every
# skill and provider is otherwise handled by this single traversal.
render_skills() {
  local stage="${1:-}"
  local skill_path skill_directory generator has_generator

  for skill_path in "${RUNTIME_SKILL_PATHS[@]}"; do
    skill_directory="$REPOSITORY_ROOT/$skill_path"
    [[ -d "$skill_directory" ]] || {
      printf '✗ Registered runtime skill does not exist: %s\n' "$skill_directory" >&2
      return 1
    }
    [[ -f "$skill_directory/create/create.py" ]] || {
      printf '✗ Registered runtime skill has no generator: %s\n' "$skill_directory" >&2
      return 1
    }
  done

  for skill_directory in "$REPOSITORY_ROOT"/skills/*/; do
    skill_directory="${skill_directory%/}"
    skill_path="${skill_directory#"$REPOSITORY_ROOT"/}"
    generator="$skill_directory/create/create.py"
    has_generator=0
    [[ -f "$generator" ]] && has_generator=1

    [[ -f "$skill_directory/SKILL.md" || $has_generator -eq 1 ]] || continue
    ((has_generator == 0)) || is_runtime_skill_path "$skill_path" || {
      printf '✗ Runtime skill is missing from %s: %s\n' \
        "$GITHOOKS_DIRECTORY/runtime-skills.sh" "$skill_path" >&2
      return 1
    }

    ((has_generator == 0)) || [[ -x "$generator" ]] || {
      printf '✗ Skill runtime is not executable: %s\n' "$generator" >&2
      return 1
    }
    ((has_generator == 0)) || "$generator" || return 1
    [[ -f "$skill_directory/SKILL.md" ]] || {
      printf '✗ Runtime did not produce SKILL.md: %s\n' "$skill_directory" >&2
      return 1
    }
    if ((has_generator == 1)) && [[ -n "$stage" ]]; then
      git -C "$REPOSITORY_ROOT" add "$skill_path/SKILL.md"
    fi

    link_skill "$skill_directory" "${SKILL_PROVIDERS[@]}" || return 1
  done

  for skill_directory in "$REPOSITORY_ROOT"/plugins/*/skills/*/; do
    skill_directory="${skill_directory%/}"
    [[ -s "$skill_directory/SKILL.md" ]] || continue
    link_skill "$skill_directory" "$HOME/.pi/agent/skills" || return 1
  done
}

# Detects and removes orphaned symlinks in provider skill directories.
# Orphaned links are symlinks pointing to source skills that no longer exist.
# Prompts for each removal.
clean_orphaned_skill_links() {
  local skills_dir link target link_name
  local found_orphans=0

  for skills_dir in "${SKILL_PROVIDERS[@]}"; do
    [[ -d "$skills_dir" ]] || continue

    while IFS= read -r link; do
      [[ -L "$link" ]] || continue

      target="$(readlink "$link")"
      if [[ ! -d "$target" ]]; then
        found_orphans=$((found_orphans + 1))
        link_name="$(basename "$link")"
        printf 'Found orphaned link: %s\n' "$link" >&2
        printf '  → points to (missing): %s\n' "$target" >&2

        if can_prompt_for_render; then
          printf 'Remove orphaned link %s? Y/N ' "$link_name" >/dev/tty
          local reply
          read -r reply </dev/tty || continue
          if [[ "$reply" == "Y" || "$reply" == "y" ]]; then
            rm -f "$link" && printf '✓ Removed %s\n' "$link" >&2
          else
            printf '⊘ Kept %s\n' "$link" >&2
          fi
        else
          printf '⊘ (no TTY; skipping) %s\n' "$link" >&2
        fi
      fi
    done < <(find "$skills_dir" -maxdepth 1 -mindepth 1 -type l -print)
  done

  if ((found_orphans == 0)); then
    printf '✓ No orphaned skill links found\n' >&2
  fi
}

sync_plugins() {
  local git_range="${1:-}"

  PLUGIN_SYNC_GIT_RANGE="$git_range" "$GITHOOKS_DIRECTORY/sync-claude-plugins.sh" || return 1
  PLUGIN_SYNC_GIT_RANGE="$git_range" "$GITHOOKS_DIRECTORY/sync-codex-plugins.sh" || return 1
}
