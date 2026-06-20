#!/usr/bin/env bash

TARGETS=(
  ~/.pi/agent/AGENTS.md.j2
  ~/.codex/AGENTS.md.j2
  ~/.claude/CLAUDE.md.j2
  ~/.gemini/GEMINI.md.j2
)

# Per-provider skills root and its allowed SKILL.md frontmatter fields,
# as "<skills-dir>|<space-separated whitelist>". `name` and `description`
# are always kept; an empty whitelist means a plain whole-dir symlink to the
# in-repo source, while a non-empty one renders a real per-provider SKILL.md.
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

# Renders <j2> through filter_frontmatter(<whitelist>) and writes it to
# <output>, using the same Y/N/R dialog as render_one. No-op when unchanged.
render_skill_one() {
  local j2="$1"
  local output="$2"
  local whitelist="$3"
  local rendered_tmp cmp_base reply

  rendered_tmp="$(mktemp)"
  ./render.py --stdout "$j2" | filter_frontmatter "$whitelist" > "$rendered_tmp"

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

# Idempotently point <link> at <target> (an absolute path).
ensure_symlink() {
  local target="$1"
  local link="$2"

  [[ -L "$link" && "$(readlink "$link")" == "$target" ]] && return 0
  ln -sfn "$target" "$link"
}

# Idempotently make <link> a whole-dir symlink to <abs_src>, replacing any
# stale symlink or previously-materialized real dir.
ensure_dir_symlink() {
  local abs_src="$1"
  local link="$2"

  [[ -L "$link" && "$(readlink "$link")" == "$abs_src" ]] && return 0
  rm -rf "$link"
  ln -sfn "$abs_src" "$link"
}

# Materialize <target_dir> as a real directory: a rendered SKILL.md plus a
# symlink to every source top-level entry except SKILL.md / SKILL.md.j2.
materialize_real_skill() {
  local abs_src="$1"
  local j2="$2"
  local target_dir="$3"
  local whitelist="$4"
  local entry

  [[ -L "$target_dir" || -f "$target_dir" ]] && rm -f "$target_dir"
  mkdir -p "$target_dir"

  while IFS= read -r -d '' entry; do
    ensure_symlink "$entry" "$target_dir/$(basename "$entry")"
  done < <(find "$abs_src" -maxdepth 1 -mindepth 1 ! -name 'SKILL.md' ! -name 'SKILL.md.j2' -print0)

  render_skill_one "$j2" "$target_dir/SKILL.md" "$whitelist"
}

# Renders every templated skill: the in-repo base SKILL.md (empty whitelist,
# committed) plus each provider's materialization. Pass "stage" to git-add the
# in-repo base renders (pre-commit only).
render_skills() {
  local stage="${1:-}"
  local j2 skill_dir skill_name abs_src base_output entry provider whitelist target_dir

  for j2 in skills/*/SKILL.md.j2; do
    [[ -e "$j2" ]] || continue
    skill_dir="$(dirname "$j2")"
    skill_name="$(basename "$skill_dir")"
    abs_src="$PWD/$skill_dir"
    base_output="$skill_dir/SKILL.md"

    render_skill_one "$j2" "$base_output" "" || return 1
    [[ -n "$stage" ]] && git add "$base_output"

    for entry in "${SKILL_PROVIDERS[@]}"; do
      provider="${entry%%|*}"
      whitelist="${entry#*|}"
      target_dir="$provider/$skill_name"
      if [[ -z "$whitelist" ]]; then
        ensure_dir_symlink "$abs_src" "$target_dir"
      else
        materialize_real_skill "$abs_src" "$j2" "$target_dir" "$whitelist" || return 1
      fi
    done
  done
}
