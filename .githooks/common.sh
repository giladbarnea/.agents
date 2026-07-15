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

# Per-provider skills root and its allowed SKILL.md frontmatter fields,
# as "<skills-dir>|<space-separated whitelist>". `name` and `description`
# are always kept. A non-empty whitelist materializes a real per-provider
# SKILL.md, but only for templated skills (those with a SKILL.md.j2); plain
# skills and empty-whitelist providers get a whole-dir symlink to the source.
SKILL_PROVIDERS=(
  "$HOME/.claude/skills|hidden disable-model-invocation"
  "$HOME/.codex/skills|"
  "$HOME/.gemini/skills|"
  "$HOME/.pi/agent/skills|"
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

# Reads a rendered SKILL.md on stdin and drops any leading-frontmatter field
# whose key is not `name`, `description`, or one of the whitelisted fields.
filter_frontmatter() {
  local allowed=" name description $1 "

  awk -v allowed="$allowed" '
    NR == 1 && $0 == "---" { in_fm = 1; print; next }
    in_fm && $0 == "---"   { in_fm = 0; print; next }
    in_fm {
      if ($0 ~ /^[A-Za-z0-9_-]+:/) {
        key = $0
        sub(/:.*/, "", key)
        keep = index(allowed, " " key " ") > 0
      }
      if (keep) print
      next
    }
    { print }
  '
}

# Emits a skill's raw markdown: the rendered SKILL.md.j2 if present, else the
# plain committed SKILL.md.
emit_skill_source() {
  local skill_dir="$1"

  if [[ -f "$skill_dir/SKILL.md.j2" ]]; then
    ./render.py --stdout "$skill_dir/SKILL.md.j2"
  else
    cat "$skill_dir/SKILL.md"
  fi
}

# Pipes <skill_dir>'s source through filter_frontmatter(<whitelist>) and writes
# it to <output>, using the same Y/N/R dialog as render_one. No-op when unchanged.
render_skill_one() {
  local skill_dir="$1"
  local output="$2"
  local whitelist="$3"
  local rendered_tmp cmp_base reply

  rendered_tmp="$(mktemp)"
  emit_skill_source "$skill_dir" | filter_frontmatter "$whitelist" > "$rendered_tmp"

  cmp_base="$output"
  [[ -f "$output" ]] || cmp_base=/dev/null

  if diff -q "$cmp_base" "$rendered_tmp" >/dev/null 2>&1; then
    rm -f "$rendered_tmp"
    return 0
  fi

  if ! can_prompt_for_render; then
    rm -f "$rendered_tmp"
    return 1
  fi

  printf 'Show diff for %s? Y/N/R ' "$output" > /dev/tty
  read -r reply < /dev/tty || { rm -f "$rendered_tmp"; return 1; }

  case "$reply" in
    [Yy])
      show_render_diff "$cmp_base" "$rendered_tmp"
      printf 'Render %s now? Y/N ' "$output" > /dev/tty
      read -r reply < /dev/tty || { rm -f "$rendered_tmp"; return 1; }
      if [[ "$reply" == "Y" || "$reply" == "y" ]]; then
        mkdir -p "$(dirname "$output")"
        cp "$rendered_tmp" "$output"
        printf '✓ Rendered → %s\n' "$output" > /dev/tty
      else
        printf '⊘ Skipped %s\n' "$output" > /dev/tty
      fi
      ;;
    [Rr])
      mkdir -p "$(dirname "$output")"
      cp "$rendered_tmp" "$output"
      printf '✓ Rendered → %s\n' "$output" > /dev/tty
      ;;
    *)
      rm -f "$rendered_tmp"
      return 1
      ;;
  esac

  rm -f "$rendered_tmp"
}

# Joins provider short-names into a brace-expansion summary rooted at $HOME,
# e.g. (claude codex) -> "$HOME/.{claude,codex}", (claude) -> "$HOME/.claude".
join_braced() {
  local IFS=,
  if (( $# == 1 )); then
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
  ln -sfn "$target" "$link" || { printf '✗ Failed to link %s → %s\n' "$target" "$link" >&2; return 1; }
}

# Materialize <target_dir> as a real directory: a rendered SKILL.md plus a
# symlink to every source top-level entry except SKILL.md / SKILL.md.j2.
materialize_real_skill() {
  local abs_src="$1"
  local skill_dir="$2"
  local target_dir="$3"
  local whitelist="$4"
  local entry entry_name expected_source

  [[ ! -e "$target_dir" && ! -L "$target_dir" ]] && mkdir -p "$target_dir"
  [[ -d "$target_dir" && ! -L "$target_dir" ]] || {
    printf '✗ Materialized skill destination is not a real directory: %s\n' "$target_dir" >&2
    return 1
  }

  while IFS= read -r -d '' entry; do
    entry_name="$(basename "$entry")"
    [[ "$entry_name" == 'SKILL.md' ]] && continue
    expected_source="$abs_src/$entry_name"
    [[ "$entry_name" != 'SKILL.md.j2' && ( -e "$expected_source" || -L "$expected_source" ) ]] || {
      printf '✗ Unexpected materialized skill entry: %s\n' "$entry" >&2
      return 1
    }
  done < <(find "$target_dir" -maxdepth 1 -mindepth 1 -print0)

  while IFS= read -r -d '' entry; do
    ensure_symlink "$entry" "$target_dir/$(basename "$entry")" || return 1
  done < <(find "$abs_src" -maxdepth 1 -mindepth 1 ! -name 'SKILL.md' ! -name 'SKILL.md.j2' -print0)

  render_skill_one "$skill_dir" "$target_dir/SKILL.md" "$whitelist"
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
  local skill_path skill_directory skill_name generator template
  local has_generator has_template runtime_count registered
  local entry provider whitelist target_dir short
  local -a linked materialized

  for skill_path in "${RUNTIME_SKILL_PATHS[@]}"; do
    skill_directory="$REPOSITORY_ROOT/$skill_path"
    [[ -d "$skill_directory" ]] || {
      printf '✗ Registered runtime skill does not exist: %s\n' "$skill_directory" >&2
      return 1
    }
    [[ -f "$skill_directory/create/create.py" || -f "$skill_directory/SKILL.md.j2" ]] || {
      printf '✗ Registered runtime skill has no supported runtime: %s\n' "$skill_directory" >&2
      return 1
    }
  done

  for skill_directory in "$REPOSITORY_ROOT"/skills/*/; do
    skill_directory="${skill_directory%/}"
    skill_path="${skill_directory#"$REPOSITORY_ROOT"/}"
    skill_name="$(basename "$skill_directory")"
    generator="$skill_directory/create/create.py"
    template="$skill_directory/SKILL.md.j2"
    has_generator=0
    has_template=0
    registered=0
    [[ -f "$generator" ]] && has_generator=1
    [[ -f "$template" ]] && has_template=1
    is_runtime_skill_path "$skill_path" && registered=1
    runtime_count=$((has_generator + has_template))

    [[ -f "$skill_directory/SKILL.md" || $runtime_count -gt 0 ]] || continue
    (( runtime_count == 0 || registered == 1 )) || {
      printf '✗ Runtime skill is missing from %s: %s\n' \
        "$GITHOOKS_DIRECTORY/runtime-skills.sh" "$skill_path" >&2
      return 1
    }

    (( has_generator == 0 )) || [[ -x "$generator" ]] || {
      printf '✗ Skill runtime is not executable: %s\n' "$generator" >&2
      return 1
    }
    (( has_generator == 0 )) || "$generator" || return 1
    (( has_template == 0 )) || render_skill_one "$skill_path" "$skill_path/SKILL.md" "" || return 1
    [[ -f "$skill_directory/SKILL.md" ]] || {
      printf '✗ Runtime did not produce SKILL.md: %s\n' "$skill_directory" >&2
      return 1
    }
    if (( registered == 1 )) && [[ -n "$stage" ]]; then
      git -C "$REPOSITORY_ROOT" add "$skill_path/SKILL.md"
    fi

    linked=()
    materialized=()
    for entry in "${SKILL_PROVIDERS[@]}"; do
      provider="${entry%%|*}"
      whitelist="${entry#*|}"
      target_dir="$provider/$skill_name"
      short="${provider#"$HOME"/}"; short="${short%%/*}"; short="${short#.}"

      if (( registered == 1 && has_template == 1 )) && [[ -n "$whitelist" ]]; then
        materialize_real_skill "$skill_directory" "$skill_path" "$target_dir" "$whitelist" || return 1
        materialized+=("$short")
      else
        ensure_symlink "$skill_directory" "$target_dir" || return 1
        linked+=("$short")
      fi
    done

    if (( ${#linked[@]} && ${#materialized[@]} )); then
      printf '✓ Synced %s → linked %s, materialized %s\n' \
        "$skill_name" "$(join_braced "${linked[@]}")" "$(join_braced "${materialized[@]}")" >&2
    elif (( ${#materialized[@]} )); then
      printf '✓ Materialized %s → %s\n' "$skill_name" "$(join_braced "${materialized[@]}")" >&2
    else
      printf '✓ Linked %s → %s\n' "$skill_name" "$(join_braced "${linked[@]}")" >&2
    fi
  done
}

# Detects and removes orphaned symlinks in provider skill directories.
# Orphaned links are symlinks pointing to source skills that no longer exist.
# Concrete (materialized) skill directories are left alone. Prompts for each removal.
clean_orphaned_skill_links() {
  local provider entry whitelist skills_dir link target link_name
  local found_orphans=0

  for entry in "${SKILL_PROVIDERS[@]}"; do
    provider="${entry%%|*}"
    skills_dir="$provider"

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
          printf 'Remove orphaned link %s? Y/N ' "$link_name" > /dev/tty
          local reply
          read -r reply < /dev/tty || continue
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

  if (( found_orphans == 0 )); then
    printf '✓ No orphaned skill links found\n' >&2
  fi
}
