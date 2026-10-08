#!/usr/bin/env bash
set -euo pipefail

hub_source="$(cd "$(dirname "$0")/../.." && pwd)"
temporary_directory="$(mktemp -d)"
trap 'rm -rf "$temporary_directory"' EXIT
hub="$temporary_directory/hub"
published="$hub/plugins/.published-soft-skills"
remote="$temporary_directory/public.git"
mkdir -p "$hub/.githooks" "$hub/plugins" "$temporary_directory/bin"
git -C "$hub_source" archive HEAD plugins/soft-skills | tar -x -C "$hub"
for script in pre-commit post-commit post-merge guard-published-soft-skills.sh publish-soft-skills.sh sync-published-soft-skills.sh check-published-private-names.sh; do
  [[ -e "$hub_source/.githooks/$script" ]] && cp "$hub_source/.githooks/$script" "$hub/.githooks/$script"
done
cat >"$hub/.githooks/common.sh" <<'EOF'
GITHOOKS_DIRECTORY="$PWD/.githooks"
section() { :; }
render_agents_md() {
  [[ "${TEST_RENDER_FAILURE:-}" != '1' ]] || { printf '%s\n' 'Render blocked for test.' >&2; return 1; }
}
render_skills() { :; }
clean_orphaned_skill_links() { :; }
EOF
git -C "$hub" init -q
git -C "$hub" config user.name Test
git -C "$hub" config user.email test@example.com
git -C "$hub" add plugins/soft-skills
git -C "$hub" -c core.hooksPath=/dev/null commit -qm 'Initial source'
git -C "$hub" config core.hooksPath .githooks

git clone -q "$hub_source/plugins/.published-soft-skills" "$published"
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
  plugins/soft-skills/skills/ai-to-leader/references/human.md \
  plugins/soft-skills/skills/ai-to-leader/references/help.md \
  plugins/soft-skills/skills/ai-to-delegated/coordination/leading-leaders.md \
  plugins/soft-skills/roles.md; do
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
set -euo pipefail
case "$1 $2" in
  'release view')
    git --git-dir="$TEST_REMOTE" show-ref --verify --quiet "refs/tags/$3"
    [[ ! -f "$TEST_RELEASE_PENDING_FILE" || "$3" != "$(<"$TEST_RELEASE_PENDING_FILE")" ]]
    ;;
  'run list')
    printf '[{"databaseId":42,"status":"completed","headSha":"%s"}]\n' "$(git --git-dir="$TEST_REMOTE" rev-parse refs/heads/main)"
    ;;
  'run rerun')
    [[ "$3" == '42' ]]
    touch "$TEST_RERUN_MARKER"
    rm "$TEST_RELEASE_PENDING_FILE"
    ;;
  *) exit 1 ;;
esac
EOF
cat >"$temporary_directory/bin/sleep" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF
chmod +x "$temporary_directory/bin/pi" "$temporary_directory/bin/gh" "$temporary_directory/bin/sleep"
export TEST_RELEASE_PENDING_FILE="$temporary_directory/release-pending" TEST_RERUN_MARKER="$temporary_directory/rerun-called"
export PATH="$temporary_directory/bin:$PATH"
initial_version="$(jq -r .version "$published/plugins/soft-skills/.claude-plugin/plugin.json")"
expected_version="${initial_version%.*}.$((${initial_version##*.} + 1))"
source_file="$hub/plugins/soft-skills/skills/ai-to-delegated/briefing/forked-context.md"
original_source_hash="$(git -C "$hub" hash-object "$source_file")"
printf '\nTest addition.\n' >>"$source_file"
printf '\nTest README addition.\n' >>"$hub/plugins/soft-skills/README.md"
git -C "$hub" add plugins/soft-skills
printf '\nUnstaged change.\n' >>"$source_file"
cat >"$remote/hooks/update" <<'EOF'
#!/usr/bin/env bash
if [[ "$1" == refs/heads/main && -e "$(git rev-parse --git-dir)/reject-main" ]]; then
  printf '%s\n' 'Main push refused for retry test.' >&2
  exit 1
fi
EOF
chmod +x "$remote/hooks/update"
touch "$remote/reject-main"
(cd "$hub" && git commit -qm 'Change plugin source' 2>"$temporary_directory/publish.log")
! git --git-dir="$remote" show-ref --verify --quiet "refs/tags/v$expected_version"
[[ -f "$hub/.git/soft-skills-publication-pending" ]]
git -C "$hub" restore "$source_file"
git -C "$hub" restore --source=HEAD^ "$source_file"
git -C "$hub" add plugins/soft-skills
if (cd "$hub" && git commit -qm 'Revert while release is pending' >"$temporary_directory/blocked-pending.log" 2>&1); then
  printf '%s\n' 'A second plugin commit passed while the first release was pending.' >&2
  exit 1
fi
rg -q 'Publication pending' "$temporary_directory/blocked-pending.log"
git -C "$hub" reset -q HEAD -- plugins/soft-skills
git -C "$hub" restore "$source_file"
rm "$remote/reject-main"
(cd "$hub" && .githooks/publish-soft-skills.sh --retry >"$temporary_directory/main-retry.log" 2>&1)
[[ ! -e "$hub/.git/soft-skills-publication-pending" ]]
if ! git --git-dir="$remote" show-ref --verify --quiet "refs/tags/v$expected_version"; then
  printf '%s\n' 'The source commit did not publish a new version.' >&2
  cat "$temporary_directory/publish.log" >&2
  exit 1
fi
git -C "$hub" show HEAD:plugins/soft-skills/skills/ai-to-delegated/briefing/forked-context.md | cmp - "$published/plugins/soft-skills/skills/ai-to-delegated/briefing/forked-context.md"
! rg -q 'Unstaged change' "$published/plugins/soft-skills/skills/ai-to-delegated/briefing/forked-context.md"
git -C "$hub" show HEAD:plugins/soft-skills/README.md | cmp - "$published/README.md"
changed_paths="$(git -C "$published" show --format= --name-only HEAD)"
! rg -q '^\.venv/' <<<"$changed_paths"
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
cmp "$source_file" "$published/plugins/soft-skills/skills/ai-to-delegated/briefing/forked-context.md"

pending_version="${revert_version%.*}.$((${revert_version##*.} + 1))"
printf '\nAnother change.\n' >>"$source_file"
git -C "$hub" add plugins/soft-skills
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
[[ "$(jq -r .version "$published/plugins/soft-skills/.claude-plugin/plugin.json")" == "$pending_version" ]]
! git --git-dir="$remote" show-ref --verify --quiet "refs/tags/v$pending_version"
if (cd "$hub" && .githooks/publish-soft-skills.sh --cancel-pending >"$temporary_directory/cancel-after-push.log" 2>&1); then
  printf '%s\n' 'Cancellation discarded a public commit that has no release.' >&2
  exit 1
fi
rg -q 'Cannot cancel' "$temporary_directory/cancel-after-push.log"
[[ -f "$hub/.git/soft-skills-publication-pending" ]]
printf '\nDo not publish yet.\n' >>"$source_file"
git -C "$hub" add plugins/soft-skills
if (cd "$hub" && .githooks/pre-commit >"$temporary_directory/pending-guard.log" 2>&1); then
  printf '%s\n' 'The next plugin commit did not wait for the unfinished release.' >&2
  exit 1
fi
rg -q 'Publication pending' "$temporary_directory/pending-guard.log"
git -C "$hub" reset -q HEAD -- plugins/soft-skills
git -C "$hub" restore "$source_file"
printf '\nNew source while release pending.\n' >>"$source_file"
git -C "$hub" add plugins/soft-skills
git -C "$hub" -c core.hooksPath=/dev/null commit -qm 'Simulate bypassed guard'
if (cd "$hub" && .githooks/publish-soft-skills.sh --retry >"$temporary_directory/out-of-order.log" 2>&1); then
  printf '%s\n' 'A later source commit published over an unfinished release.' >&2
  exit 1
fi
rg -q 'Tag push refused' "$temporary_directory/out-of-order.log"
[[ "$(jq -r .version "$published/plugins/soft-skills/.claude-plugin/plugin.json")" == "$pending_version" ]]
! git --git-dir="$remote" show-ref --verify --quiet "refs/tags/v${pending_version%.*}.$((${pending_version##*.} + 1))"
git -C "$hub" -c core.hooksPath=/dev/null revert --no-edit HEAD >/dev/null
rm "$remote/reject-tag"
(cd "$hub" && .githooks/publish-soft-skills.sh --retry >"$temporary_directory/retry.log" 2>&1)
git --git-dir="$remote" show-ref --verify --quiet "refs/tags/v$pending_version"
! git --git-dir="$remote" show-ref --verify --quiet "refs/tags/v${pending_version%.*}.$((${pending_version##*.} + 1))"
[[ -z "$(git -C "$published" status --porcelain --untracked-files=all)" ]]

private_version="${pending_version%.*}.$((${pending_version##*.} + 1))"
remote_head="$(git --git-dir="$remote" rev-parse refs/heads/main)"
printf '\nOne more change.\n' >>"$source_file"
git -C "$hub" add plugins/soft-skills
(cd "$hub" && TEST_PI_TOUCH_OTHER=1 git commit -qm 'Reject extra AI edit' 2>"$temporary_directory/ai-failure.log")
rg -q 'Anonymization changed a file outside' "$temporary_directory/ai-failure.log"
[[ "$(git --git-dir="$remote" rev-parse refs/heads/main)" == "$remote_head" ]]
[[ -z "$(git -C "$published" status --porcelain --untracked-files=all)" ]]
if (cd "$hub" && TEST_PI_SYMLINK=1 .githooks/publish-soft-skills.sh --retry >"$temporary_directory/symlink.log" 2>&1); then
  printf '%s\n' 'An unexpected AI symlink was published.' >&2
  exit 1
fi
rg -q 'outside its four-file list' "$temporary_directory/symlink.log"
[[ "$(git --git-dir="$remote" rev-parse refs/heads/main)" == "$remote_head" ]]
(cd "$hub" && .githooks/publish-soft-skills.sh --retry >"$temporary_directory/ai-retry.log" 2>&1)
git --git-dir="$remote" show-ref --verify --quiet "refs/tags/v$private_version"

merge_version="${private_version%.*}.$((${private_version##*.} + 1))"
git -C "$hub" checkout -qb feature
printf '\nMerged plugin change.\n' >>"$source_file"
git -C "$hub" add plugins/soft-skills
git -C "$hub" -c core.hooksPath=/dev/null commit -qm 'Change plugin on branch'
git -C "$hub" checkout -q main
(cd "$hub" && git merge --no-ff --no-edit feature >"$temporary_directory/merge.log" 2>&1)
if ! git --git-dir="$remote" show-ref --verify --quiet "refs/tags/v$merge_version"; then
  printf '%s\n' 'The merged plugin change did not publish.' >&2
  cat "$temporary_directory/merge.log" >&2
  exit 1
fi

failed_render_version="${merge_version%.*}.$((${merge_version##*.} + 1))"
git -C "$hub" checkout -qb render-failure
printf '\nMerged despite local render failure.\n' >>"$source_file"
git -C "$hub" add plugins/soft-skills
git -C "$hub" -c core.hooksPath=/dev/null commit -qm 'Change plugin before render failure'
git -C "$hub" checkout -q main
(cd "$hub" && TEST_RENDER_FAILURE=1 git merge --no-ff --no-edit render-failure >"$temporary_directory/render-failure.log" 2>&1)
rg -q 'Render blocked for test' "$temporary_directory/render-failure.log"
if ! git --git-dir="$remote" show-ref --verify --quiet "refs/tags/v$failed_render_version"; then
  printf '%s\n' 'A local rendering failure stopped the merged plugin release.' >&2
  exit 1
fi
[[ ! -e "$hub/.git/soft-skills-publication-pending" ]]
merge_version="$failed_render_version"

remote_head="$(git --git-dir="$remote" rev-parse refs/heads/main)"
printf '\nGilad is private.\n' >>"$source_file"
git -C "$hub" add plugins/soft-skills
(cd "$hub" && git commit -qm 'Reject private source outside AI list' 2>"$temporary_directory/private-source.log")
rg -q 'private names' "$temporary_directory/private-source.log"
[[ "$(git --git-dir="$remote" rev-parse refs/heads/main)" == "$remote_head" ]]
[[ -z "$(git -C "$published" status --porcelain --untracked-files=all)" ]]
[[ -f "$hub/.git/soft-skills-publication-pending" ]]
git -C "$hub" restore --source=HEAD^ "$source_file"
git -C "$hub" add plugins/soft-skills
if (cd "$hub" && git commit -qm 'Correct rejected source' >"$temporary_directory/correction-blocked.log" 2>&1); then
  printf '%s\n' 'The pending release did not block an unreviewed replacement commit.' >&2
  exit 1
fi
(cd "$hub" && .githooks/publish-soft-skills.sh --cancel-pending >"$temporary_directory/cancel.log" 2>&1)
[[ ! -e "$hub/.git/soft-skills-publication-pending" ]]
[[ "$(git --git-dir="$remote" rev-parse refs/heads/main)" == "$remote_head" ]]
(cd "$hub" && git commit -qm 'Correct rejected source' 2>"$temporary_directory/corrected.log")
[[ ! -e "$hub/.git/soft-skills-publication-pending" ]]
[[ "$(git --git-dir="$remote" rev-parse refs/heads/main)" == "$remote_head" ]]

failed_release_version="${merge_version%.*}.$((${merge_version##*.} + 1))"
printf 'v%s\n' "$failed_release_version" >"$TEST_RELEASE_PENDING_FILE"
printf '\nRelease workflow retry test.\n' >>"$source_file"
git -C "$hub" add plugins/soft-skills
(cd "$hub" && git commit -qm 'Publish with a failed release workflow' 2>"$temporary_directory/workflow-failure.log")
[[ -f "$hub/.git/soft-skills-publication-pending" ]]
git --git-dir="$remote" show-ref --verify --quiet "refs/tags/v$failed_release_version"
remote_head="$(git --git-dir="$remote" rev-parse refs/heads/main)"
(cd "$hub" && .githooks/publish-soft-skills.sh --retry >"$temporary_directory/workflow-retry.log" 2>&1)
[[ -f "$TEST_RERUN_MARKER" ]]
[[ ! -e "$hub/.git/soft-skills-publication-pending" ]]
[[ "$(git --git-dir="$remote" rev-parse refs/heads/main)" == "$remote_head" ]]

printf '\nAnother source change.\n' >>"$source_file"
git -C "$hub" add plugins/soft-skills
printf '\nUncommitted public edit.\n' >>"$published/README.md"
if (cd "$hub" && GIT_INDEX_FILE="$hub/.git/index" .githooks/guard-published-soft-skills.sh >"$temporary_directory/inherited-index.log" 2>&1); then
  printf '%s\n' 'An inherited source index bypassed the dirty-public guard.' >&2
  exit 1
fi
rg -q 'public repository has uncommitted changes' "$temporary_directory/inherited-index.log"
! rg -q 'fatal:' "$temporary_directory/inherited-index.log"
