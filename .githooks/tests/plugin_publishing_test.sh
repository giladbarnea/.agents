#!/usr/bin/env bash
set -euo pipefail

hooks_directory="$(cd "$(dirname "$0")/.." && pwd)"
temporary_directory="$(mktemp -d)"
trap 'rm -rf "$temporary_directory"' EXIT
hub="$temporary_directory/hub"
published="$hub/plugins/.published-soft-skills"
mkdir -p "$hub/.githooks" "$hub/plugins/soft-skills/skills/example" "$published"
cp "$hooks_directory/pre-commit" "$hooks_directory/guard-published-soft-skills.sh" "$hub/.githooks/"
cat >"$hub/.githooks/common.sh" <<'EOF'
GITHOOKS_DIRECTORY="$PWD/.githooks"
section() { :; }
render_agents_md() { :; }
render_skills() { :; }
clean_orphaned_skill_links() { :; }
EOF
printf '%s\n' 'old source' >"$hub/plugins/soft-skills/skills/example/SKILL.md"
for repository in "$hub" "$published"; do
  git -C "$repository" init -q
  git -C "$repository" config user.name Test
  git -C "$repository" config user.email test@example.com
done
git -C "$hub" add plugins/soft-skills
git -C "$hub" -c core.hooksPath=/dev/null commit -qm 'Initial source'
git -C "$hub" config core.hooksPath .githooks
printf '%s\n' 'old public' >"$published/manual.md"
git -C "$published" add manual.md
git -C "$published" -c core.hooksPath=/dev/null commit -qm 'Initial public'
printf '%s\n' 'user edit' >"$published/manual.md"
printf '%s\n' 'new source' >"$hub/plugins/soft-skills/skills/example/SKILL.md"
git -C "$hub" add plugins/soft-skills

if (cd "$hub" && git commit -qm 'Blocked source' >"$temporary_directory/report" 2>&1); then
  printf '%s\n' 'A dirty public repository did not block the source commit.' >&2
  exit 1
fi
rg -q 'public repository has uncommitted changes' "$temporary_directory/report"
[[ "$(<"$published/manual.md")" == 'user edit' ]]
[[ "$(git -C "$hub" rev-parse HEAD:plugins/soft-skills/skills/example/SKILL.md)" != "$(git -C "$hub" hash-object plugins/soft-skills/skills/example/SKILL.md)" ]]

git -C "$hub" reset -q HEAD -- plugins/soft-skills
printf '%s\n' 'unrelated edit' >"$hub/notes.md"
git -C "$hub" add notes.md
(cd "$hub" && .githooks/pre-commit >"$temporary_directory/unrelated-report" 2>&1)
[[ "$(<"$published/manual.md")" == 'user edit' ]]

git -C "$hub" reset -q HEAD -- notes.md
git -C "$hub" add plugins/soft-skills
git -C "$published" restore manual.md
git init -q --bare "$temporary_directory/remote.git"
git -C "$published" remote add origin "$temporary_directory/remote.git"
git -C "$published" push -q origin HEAD:main
printf '%s\n' 'Unpublished local commit' >"$published/other.md"
git -C "$published" add other.md
git -C "$published" -c core.hooksPath=/dev/null commit -qm 'Unpublished change'
if (cd "$hub" && git commit -qm 'Blocked by unpublished public commit' >"$temporary_directory/ahead-report" 2>&1); then
  printf '%s\n' 'An unpublished public commit did not block the source commit.' >&2
  exit 1
fi
rg -q 'unpublished commits' "$temporary_directory/ahead-report"
