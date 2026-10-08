#!/usr/bin/env bash
set -euo pipefail

other_files_checksum() (
  cd "$1"
  find . \( -type f -o -type l \) ! -name .git -print0 | sort -z | while IFS= read -r -d '' file; do
    case "$file" in
    ./plugins/soft-skills/skills/ai-to-leader/references/human.md | \
      ./plugins/soft-skills/skills/ai-to-leader/references/help.md | \
      ./plugins/soft-skills/skills/ai-to-delegated/coordination/leading-leaders.md | \
      ./plugins/soft-skills/roles.md) continue ;;
    esac
    if [[ -L "$file" ]]; then
      printf '%s -> %s\n' "$file" "$(readlink "$file")"
      continue
    fi
    stat -f '%Sp' "$file"
    shasum -a 256 "$file"
  done | shasum -a 256 | awk '{print $1}'
)

# Counts private markers in the four anonymized files: Gilad, ADHD, and a
# standalone first-person "I". A clean published copy scores zero.
private_marker_count() {
  rg -io --no-filename -e 'gilad' -e 'adhd' -e '\bi\b' "$@" | wc -l | tr -d ' '
}

main() {
  local personal_plugin_directory="$1"
  local published_repository="$2"
  local published_plugin_directory="$published_repository/plugins/soft-skills"
  local anonymized_files=(
    "$published_plugin_directory/skills/ai-to-leader/references/human.md"
    "$published_plugin_directory/skills/ai-to-leader/references/help.md"
    "$published_plugin_directory/skills/ai-to-delegated/coordination/leading-leaders.md"
    "$published_plugin_directory/roles.md"
  )

  cd "$published_repository"
  local markers_before="$(private_marker_count "${anonymized_files[@]}")"

  # Mirror the personal plugin verbatim, excluding hidden files (private
  # notes stay private). Skill and root file names are a hardcoded whitelist.
  local skill_name
  for skill_name in ai-to-leader ai-to-delegated handoff peer-review theory-of-mind; do
    rsync -a --delete --exclude='.*' "$personal_plugin_directory/skills/$skill_name/" "$published_plugin_directory/skills/$skill_name/"
  done
  rm -f "$published_plugin_directory/references/roles.md"
  rmdir "$published_plugin_directory/references" 2>/dev/null || true
  rsync -a "$personal_plugin_directory/roles.md" "$published_plugin_directory/"
  rsync -a "$personal_plugin_directory/README.md" "$published_repository/README.md"

  # The copy just overwrote the anonymized files with personal-voice sources.
  # Only a rise in private markers means there is something new to anonymize;
  # rerunning the LLM on already-clean files paraphrases them for no gain.
  local markers_after="$(private_marker_count "${anonymized_files[@]}")"
  if ((markers_after <= markers_before)); then
    printf 'Anonymization skipped: private markers did not rise (%s before, %s after).\n' "$markers_before" "$markers_after" >&2
    "$(dirname "${BASH_SOURCE[0]}")/check-published-private-names.sh" "$published_repository"
    return
  fi

  # The personal plugin speaks in Gilad's personal voice (Gilad, ADHD, first
  # person). The published copies of the whitelisted files below must be
  # anonymized (a generic human leader, cognitive overload, direct assertions
  # softened). An LLM rewrites exactly those files in place.
  local anonymization_prompt
  IFS= read -r -d '' anonymization_prompt <<'EOF' || true
Anonymize exactly these files in the published repository at __PUBLISHED_REPOSITORY__, in place. Do not touch any other file.
- __PUBLISHED_REPOSITORY__/plugins/soft-skills/skills/ai-to-leader/references/human.md
- __PUBLISHED_REPOSITORY__/plugins/soft-skills/skills/ai-to-leader/references/help.md
- __PUBLISHED_REPOSITORY__/plugins/soft-skills/skills/ai-to-delegated/coordination/leading-leaders.md
- __PUBLISHED_REPOSITORY__/plugins/soft-skills/roles.md

They were copied from ~/.agents/plugins/soft-skills/, which speaks in Gilad's personal voice (Gilad, ADHD, first person).
The published copies must be anonymized (a generic human leader, cognitive overload, direct assertions softened).
Read the actual files before editing. The previous Git version is not the current source.
Preserve every instruction that does not need anonymization verbatim, including newly added instructions. Do not restore files from Git or remove source changes.
Preserve current skill-loading instructions.
Leave an already-clean file unchanged. A file is clean when it does not mention Gilad or ADHD and does not speak in an unintended first person. Do not paraphrase, soften, or restyle a clean file.
The last pushed git revision of the files you are anonymizing may be exactly, or almost exactly what you need barring novel content not in origin.

EOF
  anonymization_prompt="${anonymization_prompt//__PUBLISHED_REPOSITORY__/$published_repository}"

  local unchanged_checksum="$(other_files_checksum "$published_repository")"
  pi --model openai-codex/gpt-6-sol --thinking low --no-session --no-skills --no-prompt-templates --no-extensions --no-themes --no-context-files -p "$anonymization_prompt"
  [[ "$unchanged_checksum" == "$(other_files_checksum "$published_repository")" ]] || {
    printf 'Anonymization changed a file outside its four-file list.\n' >&2
    return 1
  }
  local file
  for file in "${anonymized_files[@]}"; do
    [[ -f "$file" && ! -L "$file" ]] || {
      printf 'Anonymization removed or replaced %s.\n' "$file" >&2
      return 1
    }
  done
  "$(dirname "${BASH_SOURCE[0]}")/check-published-private-names.sh" "$published_repository"
}

main "$@"
