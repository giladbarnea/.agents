#!/usr/bin/env bash
set -euo pipefail

repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if git -C "$repository_root" diff --cached --quiet HEAD -- plugins/soft-skills; then
  exit 0
fi
pending_file="$(git -C "$repository_root" rev-parse --path-format=absolute --git-path soft-skills-publication-pending)"
[[ ! -f "$pending_file" ]] || {
  printf 'Publication pending for source commit %s. Retry with .githooks/publish-soft-skills.sh --retry. If validation rejected the source, use --cancel-pending before committing a correction.\n' "$(<"$pending_file")" >&2
  exit 1
}

while IFS= read -r variable; do
  unset "$variable"
done < <(git -C "$repository_root" rev-parse --local-env-vars)
published_repository="$repository_root/plugins/.published-soft-skills"
[[ -d "$published_repository/.git" ]] || {
  printf 'The public repository is missing: %s\n' "$published_repository" >&2
  exit 1
}
if [[ -n "$(git -C "$published_repository" status --porcelain --untracked-files=all)" ]]; then
  printf 'The public repository has uncommitted changes; resolve them before committing plugin changes:\n' >&2
  git -C "$published_repository" status --short >&2
  exit 1
fi
[[ "$(git -C "$published_repository" symbolic-ref --short HEAD)" == main ]] || {
  printf 'Check out main in the public repository before committing plugin changes.\n' >&2
  exit 1
}
git -C "$published_repository" fetch --quiet origin main --tags
[[ "$(git -C "$published_repository" rev-parse HEAD)" == "$(git -C "$published_repository" rev-parse origin/main)" ]] || {
  printf 'The public repository has unpublished commits or remote changes. Bring main in sync before committing plugin changes.\n' >&2
  exit 1
}
version="$(jq -r .version "$published_repository/plugins/soft-skills/.claude-plugin/plugin.json")"
[[ "$(git -C "$published_repository" rev-parse -q --verify "refs/tags/v$version^{}" 2>/dev/null || true)" == "$(git -C "$published_repository" rev-parse HEAD)" ]] || {
  printf 'The public repository has a release pending for v%s. Retry publication before committing plugin changes.\n' "$version" >&2
  exit 1
}
gh release view "v$version" --repo giladbarnea/soft-skills --json tagName --jq .tagName >/dev/null 2>&1 || {
  printf 'The public repository has a release pending for v%s. Retry publication before committing plugin changes.\n' "$version" >&2
  exit 1
}
