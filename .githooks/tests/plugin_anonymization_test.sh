#!/usr/bin/env bash
set -euo pipefail

hub_source="$(cd "$(dirname "$0")/../.." && pwd)"
temporary_directory="$(mktemp -d)"
trap 'rm -rf "$temporary_directory"' EXIT
hub="$temporary_directory/hub"
public_repository="$temporary_directory/public"
published="$hub/plugins/.published-soft-skills"
mkdir -p "$hub/.githooks" "$temporary_directory/bin"
git -C "$hub_source" archive HEAD plugins/soft-skills | tar -x -C "$hub"
cp "$hub_source/.githooks/sync-published-soft-skills.sh" "$hub_source/.githooks/check-published-private-names.sh" "$hub/.githooks/"
git -C "$hub" init -q
git -C "$hub" config user.name Test
git -C "$hub" config user.email test@example.com
git -C "$hub" config core.hooksPath /dev/null
git -C "$hub" add plugins/soft-skills
git -C "$hub" commit -qm 'Initial source'
initial_source_commit="$(git -C "$hub" rev-parse HEAD)"
git clone -q "$hub_source/plugins/.published-soft-skills" "$public_repository"
git -C "$public_repository" config user.name Test
git -C "$public_repository" config user.email test@example.com
git -C "$public_repository" config core.hooksPath /dev/null
git -C "$public_repository" commit --allow-empty -qm "Release soft-skills v0.0.0 from ${initial_source_commit:0:12}"
git -C "$public_repository" worktree add -q --detach "$published" HEAD

export TEST_PUBLISHED_DIRECTORY="$published" TEST_PI_LOG="$temporary_directory/pi.log"
touch "$TEST_PI_LOG"
cat >"$temporary_directory/bin/pi" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
prompt="${!#}"
while IFS= read -r line; do
  [[ "$line" == "- $TEST_PUBLISHED_DIRECTORY/plugins/soft-skills/"* ]] || continue
  file="${line#- }"
  printf '%s\n' "$file" >>"$TEST_PI_LOG"
  perl -pi -e 's/\bgilad\b/a human leader/gi; s/\badhd\b/cognitive-overload/gi' "$file"
done <<<"$prompt"
if [[ "${TEST_PI_TOUCH_PRESERVED:-}" == 1 ]]; then
  printf '\nUnexpected agent edit.\n' >>"$TEST_PUBLISHED_DIRECTORY/plugins/soft-skills/roles.md"
fi
EOF
chmod +x "$temporary_directory/bin/pi"
export PATH="$temporary_directory/bin:$PATH"

printf '\nUnrelated skill update.\n' >>"$hub/plugins/soft-skills/skills/ai-to-leader/SKILL.md"
git -C "$hub" add plugins/soft-skills
git -C "$hub" commit -qm 'Change only a skill entry point'
"$hub/.githooks/sync-published-soft-skills.sh" "$hub/plugins/soft-skills" "$published" "$(git -C "$hub" rev-parse HEAD)"
if [[ -s "$TEST_PI_LOG" ]]; then
  printf 'An unrelated skill change ran the anonymization agent.\n' >&2
  exit 1
fi
git -C "$published" diff --exit-code -- \
  plugins/soft-skills/skills/ai-to-leader/references/human.md \
  plugins/soft-skills/skills/ai-to-leader/references/help.md \
  plugins/soft-skills/skills/ai-to-delegated/coordination/leading-leaders.md \
  plugins/soft-skills/roles.md
printf 'PASS: unrelated edits preserve anonymized files without an agent.\n'

human_file=plugins/soft-skills/skills/ai-to-leader/references/human.md
printf 'I need short reports. The GitHub account is giladbarnea.\n' >"$hub/$human_file"
git -C "$hub" add "$human_file"
git -C "$hub" commit -qm 'Replace a personal reference with clean first-person text'
"$hub/.githooks/sync-published-soft-skills.sh" "$hub/plugins/soft-skills" "$published" "$(git -C "$hub" rev-parse HEAD)"
if [[ -s "$TEST_PI_LOG" ]]; then
  printf 'Clean first-person text or a GitHub handle ran the anonymization agent.\n' >&2
  exit 1
fi
cmp "$hub/$human_file" "$published/$human_file"
printf 'PASS: changed clean text copies directly, including I and giladbarnea.\n'

help_file=plugins/soft-skills/skills/ai-to-leader/references/help.md
printf '\nNever drop this newly added instruction.\n' >>"$hub/$help_file"
git -C "$hub" add "$help_file"
git -C "$hub" commit -qm 'Change private text without adding private markers'
printf '\nAnother unrelated update.\n' >>"$hub/plugins/soft-skills/skills/ai-to-leader/SKILL.md"
git -C "$hub" add plugins/soft-skills
git -C "$hub" commit -qm 'Leave the private change in an earlier unpublished commit'
source_commit="$(git -C "$hub" rev-parse HEAD)"
"$hub/.githooks/sync-published-soft-skills.sh" "$hub/plugins/soft-skills" "$published" "$source_commit"
if [[ "$(<"$TEST_PI_LOG")" != "$published/$help_file" ]]; then
  printf 'Expected only %s to reach the agent. Got:\n%s\n' "$help_file" "$(<"$TEST_PI_LOG")" >&2
  exit 1
fi
rg -q 'Never drop this newly added instruction\.' "$published/$help_file"
cmp "$hub/$human_file" "$published/$human_file"
git -C "$published" diff --exit-code -- \
  plugins/soft-skills/skills/ai-to-delegated/coordination/leading-leaders.md \
  plugins/soft-skills/roles.md
printf 'PASS: only changed private text reaches the agent, across unpublished commits.\n'

git -C "$published" add --all
git -C "$published" commit -qm "Release soft-skills v0.0.1 from ${source_commit:0:12}"
: >"$TEST_PI_LOG"
"$hub/.githooks/sync-published-soft-skills.sh" "$hub/plugins/soft-skills" "$published" "$source_commit"
if [[ -s "$TEST_PI_LOG" ]]; then
  printf 'Already-published personal source ran the agent again.\n' >&2
  exit 1
fi
[[ -z "$(git -C "$published" status --porcelain)" ]]
printf 'PASS: a repeated sync keeps the published wording without an agent.\n'

printf '\nOne more private-source instruction.\n' >>"$hub/$help_file"
git -C "$hub" add "$help_file"
git -C "$hub" commit -qm 'Request another private-file update'
if TEST_PI_TOUCH_PRESERVED=1 "$hub/.githooks/sync-published-soft-skills.sh" "$hub/plugins/soft-skills" "$published" "$(git -C "$hub" rev-parse HEAD)" >"$temporary_directory/guard.log" 2>&1; then
  printf 'The agent changed an unchanged anonymized file outside its request.\n' >&2
  exit 1
fi
rg -q 'outside its requested file list' "$temporary_directory/guard.log"
printf 'PASS: the agent cannot edit preserved anonymized files.\n'
