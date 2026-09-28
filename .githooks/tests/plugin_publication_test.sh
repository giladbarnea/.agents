#!/usr/bin/env bash
set -euo pipefail

hub_source="$(cd "$(dirname "$0")/../.." && pwd)"
temporary_directory="$(mktemp -d)"
trap 'rm -rf "$temporary_directory"' EXIT
hub="$temporary_directory/hub"
published="$hub/plugins/.published-interaction"
remote="$temporary_directory/public.git"
mkdir -p "$hub/.githooks" "$hub/plugins" "$temporary_directory/bin"
git -C "$hub_source" archive HEAD plugins/interaction | tar -x -C "$hub"
for script in pre-commit post-commit guard-published-interaction.sh publish-interaction.sh sync-published-interaction.sh; do
  [[ -e "$hub_source/.githooks/$script" ]] && cp "$hub_source/.githooks/$script" "$hub/.githooks/$script"
done
cat >"$hub/.githooks/common.sh" <<'EOF'
GITHOOKS_DIRECTORY="$PWD/.githooks"
section() { :; }
render_agents_md() { :; }
render_skills() { :; }
clean_orphaned_skill_links() { :; }
EOF
git -C "$hub" init -q
git -C "$hub" config user.name Test
git -C "$hub" config user.email test@example.com
git -C "$hub" add plugins/interaction
git -C "$hub" -c core.hooksPath=/dev/null commit -qm 'Initial source'
git -C "$hub" config core.hooksPath .githooks

git clone -q "$hub_source/plugins/.published-interaction" "$published"
git -C "$published" config user.name Test
git -C "$published" config user.email test@example.com
git -C "$published" config core.hooksPath /dev/null
git -C "$published" remote remove origin
git init -q --bare "$remote"
git -C "$published" remote add origin "$remote"
git -C "$published" push -q origin main
git -C "$published" push -q origin --tags
git -C "$published" fetch -q origin main
export TEST_PUBLISHED_SOURCE="$published" TEST_REMOTE="$remote"
cat >"$temporary_directory/bin/pi" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
prompt="${!#}"
published_directory="${prompt#*at }"
published_directory="${published_directory%%, in place*}"
for file in \
  plugins/interaction/skills/ai-to-leader/references/human.md \
  plugins/interaction/skills/ai-to-leader/references/help.md \
  plugins/interaction/skills/ai-to-delegated/coordination/leading-leaders.md \
  plugins/interaction/roles.md; do
  cp "$TEST_PUBLISHED_SOURCE/$file" "$published_directory/$file"
done
if [[ "${TEST_PI_TOUCH_OTHER:-}" == '1' ]]; then
  printf '%s\n' 'Unexpected AI edit' >>"$published_directory/README.md"
fi
if [[ "${TEST_PI_SYMLINK:-}" == '1' ]]; then
  ln -s "$TEST_PUBLISHED_SOURCE/README.md" "$published_directory/unexpected-link.md"
fi
EOF
cat >"$temporary_directory/bin/gh" <<'EOF'
#!/usr/bin/env bash
[[ "$1 $2" == 'release view' ]]
git --git-dir="$TEST_REMOTE" show-ref --verify --quiet "refs/tags/$3"
EOF
chmod +x "$temporary_directory/bin/pi" "$temporary_directory/bin/gh"
export PATH="$temporary_directory/bin:$PATH"
initial_version="$(jq -r .version "$published/plugins/interaction/.claude-plugin/plugin.json")"
expected_version="${initial_version%.*}.$((${initial_version##*.} + 1))"
source_file="$hub/plugins/interaction/skills/ai-to-delegated/briefing/forked-context.md"
original_source_hash="$(git -C "$hub" hash-object "$source_file")"
printf '\nTest addition.\n' >>"$source_file"
git -C "$hub" add plugins/interaction
printf '\nUnstaged change.\n' >>"$source_file"
(cd "$hub" && git commit -qm 'Change plugin source' 2>"$temporary_directory/publish.log")
if ! git --git-dir="$remote" show-ref --verify --quiet "refs/tags/v$expected_version"; then
  printf '%s\n' 'The source commit did not publish a new version.' >&2
  cat "$temporary_directory/publish.log" >&2
  exit 1
fi
git -C "$hub" show HEAD:plugins/interaction/skills/ai-to-delegated/briefing/forked-context.md | cmp - "$published/plugins/interaction/skills/ai-to-delegated/briefing/forked-context.md"
! rg -q 'Unstaged change' "$published/plugins/interaction/skills/ai-to-delegated/briefing/forked-context.md"
! git -C "$published" show --format= --name-only HEAD | rg -q '^\.venv/'
[[ -z "$(git -C "$published" status --porcelain --untracked-files=all)" ]]
git -C "$hub" restore "$source_file"

revert_version="${expected_version%.*}.$((${expected_version##*.} + 1))"
(cd "$hub" && git revert --no-edit HEAD >"$temporary_directory/revert.log" 2>&1)
if ! git --git-dir="$remote" show-ref --verify --quiet "refs/tags/v$revert_version"; then
  printf '%s\n' 'Reverting to previously published content did not make a new release.' >&2
  cat "$temporary_directory/revert.log" >&2
  exit 1
fi
[[ "$(git -C "$hub" hash-object "$source_file")" == "$original_source_hash" ]]
cmp "$source_file" "$published/plugins/interaction/skills/ai-to-delegated/briefing/forked-context.md"

pending_version="${revert_version%.*}.$((${revert_version##*.} + 1))"
printf '\nAnother change.\n' >>"$source_file"
git -C "$hub" add plugins/interaction
cat >"$remote/hooks/update" <<'EOF'
#!/usr/bin/env bash
if [[ "$1" == refs/tags/* && -e "$(git rev-parse --git-dir)/reject-tag" ]]; then
  printf '%s\n' 'Tag push refused for retry test.' >&2
  exit 1
fi
EOF
chmod +x "$remote/hooks/update"
touch "$remote/reject-tag"
(cd "$hub" && git commit -qm 'Publish across a tag failure' 2>"$temporary_directory/pending.log")
rg -q 'Publication pending' "$temporary_directory/pending.log"
[[ "$(jq -r .version "$published/plugins/interaction/.claude-plugin/plugin.json")" == "$pending_version" ]]
! git --git-dir="$remote" show-ref --verify --quiet "refs/tags/v$pending_version"
printf '\nDo not publish yet.\n' >>"$source_file"
git -C "$hub" add plugins/interaction
if (cd "$hub" && .githooks/pre-commit >"$temporary_directory/pending-guard.log" 2>&1); then
  printf '%s\n' 'The next plugin commit did not wait for the unfinished release.' >&2
  exit 1
fi
rg -q 'release pending' "$temporary_directory/pending-guard.log"
git -C "$hub" reset -q HEAD -- plugins/interaction
git -C "$hub" restore "$source_file"
printf '\nNew source while release pending.\n' >>"$source_file"
git -C "$hub" add plugins/interaction
git -C "$hub" -c core.hooksPath=/dev/null commit -qm 'Simulate bypassed guard'
if (cd "$hub" && .githooks/publish-interaction.sh --retry >"$temporary_directory/out-of-order.log" 2>&1); then
  printf '%s\n' 'A later source commit published over an unfinished release.' >&2
  exit 1
fi
rg -q 'earlier release is pending' "$temporary_directory/out-of-order.log"
git -C "$hub" -c core.hooksPath=/dev/null revert --no-edit HEAD >/dev/null
rm "$remote/reject-tag"
(cd "$hub" && .githooks/publish-interaction.sh --retry >"$temporary_directory/retry.log" 2>&1)
git --git-dir="$remote" show-ref --verify --quiet "refs/tags/v$pending_version"
! git --git-dir="$remote" show-ref --verify --quiet "refs/tags/v${pending_version%.*}.$((${pending_version##*.} + 1))"
[[ -z "$(git -C "$published" status --porcelain --untracked-files=all)" ]]

private_version="${pending_version%.*}.$((${pending_version##*.} + 1))"
remote_head="$(git --git-dir="$remote" rev-parse refs/heads/main)"
printf '\nOne more change.\n' >>"$source_file"
git -C "$hub" add plugins/interaction
(cd "$hub" && TEST_PI_TOUCH_OTHER=1 git commit -qm 'Reject extra AI edit' 2>"$temporary_directory/ai-failure.log")
rg -q 'Anonymization changed a file outside' "$temporary_directory/ai-failure.log"
[[ "$(git --git-dir="$remote" rev-parse refs/heads/main)" == "$remote_head" ]]
[[ -z "$(git -C "$published" status --porcelain --untracked-files=all)" ]]
if (cd "$hub" && TEST_PI_SYMLINK=1 .githooks/publish-interaction.sh --retry >"$temporary_directory/symlink.log" 2>&1); then
  printf '%s\n' 'An unexpected AI symlink was published.' >&2
  exit 1
fi
rg -q 'outside its four-file list' "$temporary_directory/symlink.log"
[[ "$(git --git-dir="$remote" rev-parse refs/heads/main)" == "$remote_head" ]]
(cd "$hub" && .githooks/publish-interaction.sh --retry >"$temporary_directory/ai-retry.log" 2>&1)
git --git-dir="$remote" show-ref --verify --quiet "refs/tags/v$private_version"

remote_head="$(git --git-dir="$remote" rev-parse refs/heads/main)"
printf '\nGilad is private.\n' >>"$source_file"
git -C "$hub" add plugins/interaction
(cd "$hub" && git commit -qm 'Reject private source outside AI list' 2>"$temporary_directory/private-source.log")
rg -q 'private names' "$temporary_directory/private-source.log"
[[ "$(git --git-dir="$remote" rev-parse refs/heads/main)" == "$remote_head" ]]
[[ -z "$(git -C "$published" status --porcelain --untracked-files=all)" ]]
