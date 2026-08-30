#!/usr/bin/env zsh

GITHOOKS_DIRECTORY="$(cd "$(dirname "${(%):-%x}")" && pwd)"
REPOSITORY_ROOT="$(cd "$GITHOOKS_DIRECTORY/.." && pwd)"
source "$GITHOOKS_DIRECTORY/runtime-skills.sh"

# I want ~/.antigravity here too, but I'm not sure it has a .j2 file
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

# ---[ Output styling ]---
# Three tiers: dim gray = structure and routine detail; green ✓ = one milestone
# summary per phase; yellow/red/bold = the few things that need attention.
[[ -t 2 ]] && source "$HOME/dev/land/term.zsh"

section() { printf "\n${CbrBlk}──[ ${C0}${Cb}%s${Cb0}${CbrBlk} ]────────────────────────────${C0}\n" "$1" >&2; }
ok()      { printf "${Cgrn}✓${C0} %b\n" "$*" >&2; }
dim()     { printf "${CbrBlk}%b${C0}\n" "$*" >&2; }
warn()    { printf "${Cylw}⚠ %b${C0}\n" "$*" >&2; }
err()     { printf "${Cred}✗ %b${C0}\n" "$*" >&2; }
ask()     { printf "  ${CbrGrn}?${C0} ${Cb}%b${Cb0} ${CbrBlk}%s${C0} ${CbrBlu}❯${C0} " "$1" "$2" >/dev/tty; }

can_prompt_for_render() {
  [[ -t 1 ]]
}

show_render_diff() {
  setopt localoptions pipefail errreturn
  local actual="$1"
  local rendered="$2"
  
  if command -v hunk >/dev/null 2>&1; then
     hunk diff "$actual" "$rendered"
     return
  fi
  if command -v comview >/dev/null 2>&1; then
    git --no-pager diff --no-index "$actual" "$rendered" | comview && return 0
    return
  fi
  if command -v delta >/dev/null 2>&1; then
    DELTA_FEATURES="${DELTA_FEATURES} narrow" delta "$actual" "$rendered"
    return
  fi
  git diff --no-index "$actual" "$rendered" 
}

render_one() {
  local target="$1"
  local output="${target%.j2}"
  local display="${output/#$HOME/~}"
  local rendered_tmp reply dry_run_report

  if dry_run_report="$(./render.py --dry-run "$target" 2>&1)"; then
    ((RENDER_UNCHANGED_COUNT += 1))
    return 0
  fi
  [[ "$dry_run_report" == *"would have been changed"* ]] || {
    err "$dry_run_report"
    return 1
  }

  printf "${Cylw}${Cb}✱ %s is stale${Cb0}${C0}\n" "$display" >&2
  can_prompt_for_render || return 1

  ask "Show diff?" "[y]es · [n]o · [r]ender now"
  read -r reply </dev/tty || return 1

  case "$reply" in
  [Yy])
    rendered_tmp="$(mktemp)"
    ./render.py --stdout "$target" >"$rendered_tmp"
    show_render_diff "$output" "$rendered_tmp"
    rm -f "$rendered_tmp"

    ask "Render ${display} now?" "[y/n]"
    read -r reply </dev/tty || return 1
    if [[ "$reply" == "Y" || "$reply" == "y" ]]; then
      ./render.py "$target" >/dev/null || return 1
      ok "Rendered → ${Cb}${display}${Cb0}"
    else
      dim "⊘ Skipped ${display}"
    fi
    ;;
  [Rr])
    ./render.py "$target" >/dev/null || return 1
    ok "Rendered → ${Cb}${display}${Cb0}"
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
  typeset -gi RENDER_UNCHANGED_COUNT=0

  render_one AGENTS.md.j2 || return 1
  [[ -n "$stage" ]] && git add AGENTS.md

  for target in "${TARGETS[@]}"; do
    render_one "$target" || return 1
  done
  ok "${Cb}${RENDER_UNCHANGED_COUNT}${Cb0}/$((${#TARGETS} + 1)) instruction files up to date"
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
    err "Refusing to link over non-symlink destination: $link"
    return 1
  }
  ln -sfn "$target" "$link" || {
    err "Failed to link $target → $link"
    return 1
  }
}

link_skill() {
  local skill_directory="$1"
  shift
  local skill_name="$(basename "$skill_directory")"
  local provider

  for provider in "$@"; do
    ensure_symlink "$skill_directory" "$provider/$skill_name" || return 1
  done
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
  local skill_path skill_directory generator has_generator provider providers_display
  local -i hub_skill_count=0 plugin_skill_count=0
  local -a provider_shorts=()

  for skill_path in "${RUNTIME_SKILL_PATHS[@]}"; do
    skill_directory="$REPOSITORY_ROOT/$skill_path"
    [[ -d "$skill_directory" ]] || {
      err "Registered runtime skill does not exist: $skill_directory"
      return 1
    }
    [[ -f "$skill_directory/create/create.py" ]] || {
      err "Registered runtime skill has no generator: $skill_directory"
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
      err "Runtime skill is missing from $GITHOOKS_DIRECTORY/runtime-skills.sh: $skill_path"
      return 1
    }

    ((has_generator == 0)) || [[ -x "$generator" ]] || {
      err "Skill runtime is not executable: $generator"
      return 1
    }
    ((has_generator == 0)) || "$generator" || return 1
    [[ -f "$skill_directory/SKILL.md" ]] || {
      err "Runtime did not produce SKILL.md: $skill_directory"
      return 1
    }
    if ((has_generator == 1)) && [[ -n "$stage" ]]; then
      git -C "$REPOSITORY_ROOT" add "$skill_path/SKILL.md"
    fi

    link_skill "$skill_directory" "${SKILL_PROVIDERS[@]}" || return 1
    ((hub_skill_count += 1))
  done

  for provider in "${SKILL_PROVIDERS[@]}"; do
    provider="${provider#"$HOME"/}"
    provider="${provider%%/*}"
    provider_shorts+=("${provider#.}")
  done
  providers_display="$(join_braced "${provider_shorts[@]}")"
  ok "Linked ${Cb}${hub_skill_count}${Cb0} hub skills → ${CbrBlk}${providers_display/#$HOME/~}${C0}"

  for skill_directory in "$REPOSITORY_ROOT"/plugins/*/skills/*/; do
    skill_directory="${skill_directory%/}"
    [[ -s "$skill_directory/SKILL.md" ]] || continue
    link_pi_plugin_skill "$skill_directory" || return 1
    ((plugin_skill_count += 1))
  done
  ok "Materialized ${Cb}${plugin_skill_count}${Cb0} plugin skills → ${CbrBlk}~/.pi/agent/skills${C0} (flat references)"
}

# Materializes one plugin skill for Pi as a real directory of symlinks instead
# of one skill-directory symlink. This lets the plugin-level references/* land
# flat inside <skill>/references/ without writing into the hub source.
# Reference links are rebuilt each run; on a name clash the earlier entry wins
# (skill's own references before plugin-level ones) and the loser is skipped
# with a warning.
link_pi_plugin_skill() {
  setopt localoptions nullglob
  local skill_directory="$1"
  local plugin_directory="${skill_directory%/skills/*}"
  local skill_name="$(basename "$skill_directory")"
  local destination="$HOME/.pi/agent/skills/$skill_name"
  local entry link

  [[ -L "$destination" ]] && rm "$destination"
  mkdir -p "$destination/references"
  find "$destination/references" -maxdepth 1 -type l -delete

  for entry in "$skill_directory"/*; do
    [[ "$(basename "$entry")" == "references" ]] && continue
    ensure_symlink "$entry" "$destination/$(basename "$entry")" || return 1
  done

  for entry in "$skill_directory"/references/* "$plugin_directory"/references/*; do
    link="$destination/references/$(basename "$entry")"
    if [[ -e "$link" || -L "$link" ]]; then
      warn "Reference name clash: kept ${link/#$HOME/~}, skipped ${entry/#$HOME/~}"
      continue
    fi
    ensure_symlink "$entry" "$link" || return 1
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
        warn "Orphaned link: ${link/#$HOME/~} → missing ${target/#$HOME/~}"

        if can_prompt_for_render; then
          ask "Remove orphaned link ${link_name}?" "[y/n]"
          local reply
          read -r reply </dev/tty || continue
          if [[ "$reply" == "Y" || "$reply" == "y" ]]; then
            rm -f "$link" && ok "Removed ${link/#$HOME/~}"
          else
            dim "⊘ Kept ${link/#$HOME/~}"
          fi
        else
          dim "⊘ (no TTY; skipping) ${link/#$HOME/~}"
        fi
      fi
    done < <(find "$skills_dir" -maxdepth 1 -mindepth 1 -type l -print)
  done

  if ((found_orphans == 0)); then
    dim "No orphaned skill links"
  fi
}

sync_plugins() {
  local git_range="${1:-}"

  PLUGIN_SYNC_GIT_RANGE="$git_range" "$GITHOOKS_DIRECTORY/sync-claude-plugins.sh" || return 1
  PLUGIN_SYNC_GIT_RANGE="$git_range" "$GITHOOKS_DIRECTORY/sync-codex-plugins.sh" || return 1
}
