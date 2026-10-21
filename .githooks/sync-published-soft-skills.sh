#!/usr/bin/env bash
set -euo pipefail

other_files_checksum() (
  cd "$1"
  shift
  local file exclusions=()
  for file in "$@"; do
    exclusions+=(! -path "./$file")
  done
  find . \( -type f -o -type l \) ! -name .git "${exclusions[@]}" -print0 | sort -z | while IFS= read -r -d '' file; do
    if [[ -L "$file" ]]; then
      printf '%s -> %s\n' "$file" "$(readlink "$file")"
      continue
    fi
    stat -f '%Sp' "$file"
    shasum -a 256 "$file"
  done | shasum -a 256 | awk '{print $1}'
)

main() {
  local personal_plugin_directory="$1"
  local published_repository="$2"
  local source_commit="$3"
  local repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
  local published_plugin_directory="$published_repository/plugins/soft-skills"
  local anonymizable_files=(
    plugins/soft-skills/skills/ai-to-leader/references/human.md
    plugins/soft-skills/skills/ai-to-leader/references/help.md
    plugins/soft-skills/skills/ai-to-delegated/coordination/leading-leaders.md
    plugins/soft-skills/roles.md
  )
  local published_release published_source_commit
  published_release="$(git -C "$published_repository" log -1 --format=%s)"
  published_source_commit="$(git -C "$repository_root" rev-parse --verify "${published_release##* from }^{commit}")"

  cd "$published_repository"

  # Mirror the personal plugin verbatim, excluding hidden files (private
  # notes stay private). Skill and root file names are a hardcoded whitelist.
  local skill_name
  for skill_name in ai-to-leader ai-to-delegated handoff peer-review theory-of-mind; do
    rsync -a --delete --exclude='.*' "$personal_plugin_directory/skills/$skill_name/" "$published_plugin_directory/skills/$skill_name/"
  done
  rm -f "$published_plugin_directory/references/roles.md"
  rmdir "$published_plugin_directory/references" 2>/dev/null || true
  rsync -a "$personal_plugin_directory/roles.md" "$personal_plugin_directory/token-economic-communication.md" "$published_plugin_directory/"
  rsync -a "$personal_plugin_directory/README.md" "$published_repository/README.md"

  local file files_to_anonymize=()
  for file in "${anonymizable_files[@]}"; do
    if git -C "$repository_root" diff --quiet "$published_source_commit" "$source_commit" -- "$file"; then
      git restore --source=HEAD --worktree -- "$file"
      continue
    fi
    if rg -qi '\bgilad\b|\badhd\b' "$file"; then
      files_to_anonymize+=("$file")
    fi
  done
  if ((${#files_to_anonymize[@]} == 0)); then
    printf 'Anonymization skipped: no changed source file contains Gilad or ADHD.\n' >&2
    "$repository_root/.githooks/check-published-private-names.sh" "$published_repository"
    return
  fi

  local anonymization_prompt anonymization_file_list=''
  for file in "${files_to_anonymize[@]}"; do
    anonymization_file_list+="- $published_repository/$file"$'\n'
  done
  IFS= read -r -d '' anonymization_prompt <<'EOF' || true
Anonymize exactly these files in the published repository at __PUBLISHED_REPOSITORY__, in place. Do not touch any other file.
__ANONYMIZATION_FILES__

They were copied from ~/.agents/plugins/soft-skills/, which speaks in Gilad's personal voice (Gilad, ADHD, first person).
The published copies must be anonymized (a generic human leader, cognitive overload, direct assertions softened).
Read the actual files before editing. The previous Git version is not the current source.
Preserve every instruction that does not need anonymization verbatim, including newly added instructions. Do not restore files from Git or remove source changes.
Preserve current skill-loading instructions.
Leave an already-clean file unchanged. A file is clean when it does not mention Gilad or ADHD and does not speak in an unintended first person. Do not paraphrase, soften, or restyle a clean file.
The last pushed git revision of the files you are anonymizing may be exactly, or almost exactly what you need barring novel content not in origin.

EOF
  anonymization_prompt="${anonymization_prompt//__PUBLISHED_REPOSITORY__/$published_repository}"
  anonymization_prompt="${anonymization_prompt//__ANONYMIZATION_FILES__/$anonymization_file_list}"

  local unchanged_checksum
  unchanged_checksum="$(other_files_checksum "$published_repository" "${files_to_anonymize[@]}")"
  pi --model openai-codex/gpt-6-sol --thinking low --no-session --no-skills --no-prompt-templates --no-extensions --no-themes --no-context-files -p "$anonymization_prompt"
  [[ "$unchanged_checksum" == "$(other_files_checksum "$published_repository" "${files_to_anonymize[@]}")" ]] || {
    printf 'Anonymization changed a file outside its requested file list.\n' >&2
    return 1
  }
  for file in "${files_to_anonymize[@]}"; do
    [[ -f "$file" && ! -L "$file" ]] || {
      printf 'Anonymization removed or replaced %s.\n' "$file" >&2
      return 1
    }
  done
  "$repository_root/.githooks/check-published-private-names.sh" "$published_repository"
}

main "$@"
