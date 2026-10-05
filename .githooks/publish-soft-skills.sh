#!/usr/bin/env bash
set -euo pipefail

repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
published_repository="$repository_root/plugins/.published-soft-skills"
while IFS= read -r variable; do
  unset "$variable"
done < <(git -C "$repository_root" rev-parse --local-env-vars)

wait_for_release() {
  local tag="$1"
  for ((attempt = 0; attempt < 30; attempt++)); do
    if gh release view "$tag" --repo giladbarnea/soft-skills --json tagName --jq .tagName >/dev/null 2>&1; then
      printf 'Published soft-skills %s.\n' "$tag" >&2
      return 0
    fi
    sleep 10
  done
  printf 'Publication pending: the GitHub release for %s did not succeed. Retry with %s --retry.\n' "$tag" "$0" >&2
  return 1
}

rerun_completed_release() {
  local tag="$1" commit="$2" run
  if gh release view "$tag" --repo giladbarnea/soft-skills --json tagName --jq .tagName >/dev/null 2>&1; then
    return 0
  fi
  run="$(gh run list --repo giladbarnea/soft-skills --workflow release.yml --branch "$tag" --commit "$commit" --json databaseId,status,headSha --limit 5 | jq -c --arg commit "$commit" '[.[] | select(.headSha == $commit)][0] // empty')"
  [[ "$(jq -r '.status // empty' <<<"$run")" == completed ]] || return 0
  gh run rerun "$(jq -r .databaseId <<<"$run")" --repo giladbarnea/soft-skills
}

case "${1:-}" in
  --retry|--cancel-pending) ;;
  --merge) git -C "$repository_root" diff --quiet ORIG_HEAD HEAD -- plugins/soft-skills && exit 0 ;;
  *) git -C "$repository_root" diff --quiet HEAD^ HEAD -- plugins/soft-skills && exit 0 ;;
esac
pending_file="$(git -C "$repository_root" rev-parse --path-format=absolute --git-path soft-skills-publication-pending)"
source_commit="$(git -C "$repository_root" rev-parse HEAD)"
if [[ -f "$pending_file" ]]; then
  pending_commit="$(<"$pending_file")"
  [[ "${1:-}" == '--retry' || "${1:-}" == '--cancel-pending' || "$pending_commit" == "$source_commit" ]] || {
    printf 'Publication pending for earlier source commit %s. Retry it before publishing another commit.\n' "$pending_commit" >&2
    exit 1
  }
  source_commit="$pending_commit"
else
  [[ "${1:-}" != '--cancel-pending' ]] || { printf 'There is no pending publication to cancel.\n' >&2; exit 1; }
  printf '%s\n' "$source_commit" >"$pending_file"
fi

[[ -d "$published_repository/.git" ]] || {
  printf 'Publication pending: the public repository is missing: %s\n' "$published_repository" >&2
  exit 1
}
[[ -z "$(git -C "$published_repository" status --porcelain --untracked-files=all)" ]] || {
  printf 'Publication pending: the public repository has uncommitted changes.\n' >&2
  git -C "$published_repository" status --short >&2
  exit 1
}
[[ "$(git -C "$published_repository" symbolic-ref --short HEAD)" == main ]] || {
  printf 'Publication pending: check out main in the public repository.\n' >&2
  exit 1
}
git -C "$published_repository" fetch --quiet origin main --tags
if [[ "$(git -C "$published_repository" rev-parse HEAD)" != "$(git -C "$published_repository" rev-parse origin/main)" ]]; then
  git -C "$published_repository" merge --ff-only --quiet origin/main
fi
if [[ "${1:-}" == '--cancel-pending' ]]; then
  released_version="$(jq -r .version "$published_repository/plugins/soft-skills/.claude-plugin/plugin.json")"
  [[ "$(git -C "$published_repository" rev-parse -q --verify "refs/tags/v$released_version^{}" 2>/dev/null || true)" == "$(git -C "$published_repository" rev-parse HEAD)" ]] &&
    gh release view "v$released_version" --repo giladbarnea/soft-skills --json tagName --jq .tagName >/dev/null 2>&1 || {
      printf 'Cannot cancel: the public commit has not completed its release. Retry that release instead.\n' >&2
      exit 1
    }
  rm "$pending_file"
  printf 'Cancelled pending publication for %s. Commit the corrected plugin source.\n' "$source_commit" >&2
  exit 0
fi

temporary_directory="$(mktemp -d)"
cleanup() {
  if [[ -e "$temporary_directory/published/.git" ]]; then
    git -C "$published_repository" worktree remove --force "$temporary_directory/published"
  fi
  rm -rf "$temporary_directory"
}
trap cleanup EXIT
mkdir "$temporary_directory/source"
git -C "$repository_root" archive "$source_commit" plugins/soft-skills | tar -x -C "$temporary_directory/source"
personal_plugin_directory="$temporary_directory/source/plugins/soft-skills"
source_checksum="$(cd "$personal_plugin_directory" && find . -mindepth 1 \( -type d -name '.*' -prune \) -o \( -type f -name '*.md' ! -name '.*' -print0 \) | sort -z | xargs -0 shasum -a 256 | shasum -a 256 | awk '{print $1}')"
checksum_file="$published_repository/.plugin-source-checksum"

if [[ "$source_checksum" == "$(<"$checksum_file")" ]]; then
  version="$(jq -r .version "$published_repository/plugins/soft-skills/.claude-plugin/plugin.json")"
  tag="v$version"
  tagged_commit="$(git -C "$published_repository" rev-parse -q --verify "refs/tags/$tag^{}" 2>/dev/null || true)"
  [[ -z "$tagged_commit" || "$tagged_commit" == "$(git -C "$published_repository" rev-parse HEAD)" ]] || {
    printf 'Publication pending: %s points to a different public commit.\n' "$tag" >&2
    exit 1
  }
  [[ -n "$tagged_commit" ]] || git -C "$published_repository" tag -a "$tag" -m "Soft Skills $tag"
  git -C "$published_repository" push origin "$tag"
  if [[ "${1:-}" == '--retry' ]]; then
    rerun_completed_release "$tag" "$(git -C "$published_repository" rev-parse HEAD)"
  fi
  wait_for_release "$tag"
  rm "$pending_file"
  exit
fi

version="$(jq -r .version "$published_repository/plugins/soft-skills/.claude-plugin/plugin.json")"
[[ "$version" == "$(jq -r .version "$published_repository/plugins/soft-skills/.codex-plugin/plugin.json")" && "$version" == "$(jq -r .version "$published_repository/package.json")" ]] || {
  printf 'Publication pending: the public manifest versions disagree.\n' >&2
  exit 1
}
current_tag="v$version"
[[ "$(git -C "$published_repository" rev-parse -q --verify "refs/tags/$current_tag^{}" 2>/dev/null || true)" == "$(git -C "$published_repository" rev-parse HEAD)" ]] &&
  gh release view "$current_tag" --repo giladbarnea/soft-skills --json tagName --jq .tagName >/dev/null 2>&1 || {
    printf 'Publication pending: an earlier release is pending for %s.\n' "$current_tag" >&2
    exit 1
  }
version="${version%.*}.$((${version##*.} + 1))"
tag="v$version"
[[ -z "$(git -C "$published_repository" rev-parse -q --verify "refs/tags/$tag^{}" 2>/dev/null || true)" ]] || {
  printf 'Publication pending: %s already exists.\n' "$tag" >&2
  exit 1
}
git -C "$published_repository" worktree add --quiet --detach "$temporary_directory/published" HEAD
worktree="$temporary_directory/published"
"$repository_root/.githooks/sync-published-soft-skills.sh" "$personal_plugin_directory" "$worktree"
for manifest in \
  "$worktree/plugins/soft-skills/.claude-plugin/plugin.json" \
  "$worktree/plugins/soft-skills/.codex-plugin/plugin.json" \
  "$worktree/package.json"; do
  jq --arg version "$version" '.version = $version' "$manifest" >"$manifest.tmp"
  mv "$manifest.tmp" "$manifest"
done
printf '%s\n' "$source_checksum" >"$worktree/.plugin-source-checksum"
git -C "$worktree" add --all
git -C "$worktree" diff --cached --check
git -C "$worktree" -c core.hooksPath=/dev/null commit -m "Release soft-skills $tag from ${source_commit:0:12}"
published_commit="$(git -C "$worktree" rev-parse HEAD)"
[[ -z "$(git -C "$published_repository" status --porcelain --untracked-files=all)" ]] || {
  printf 'Publication pending: the public repository changed during the build.\n' >&2
  exit 1
}
git -C "$published_repository" push origin "$published_commit:refs/heads/main"
git -C "$published_repository" merge --ff-only --quiet "$published_commit"
git -C "$published_repository" tag -a "$tag" -m "Soft Skills $tag"
git -C "$published_repository" push origin "$tag"
wait_for_release "$tag"
rm "$pending_file"
