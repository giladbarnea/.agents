#!/usr/bin/env zsh
set -e

temporary_directory="$(mktemp -d)"
trap 'rm -rf "$temporary_directory"' EXIT
export HOME="$temporary_directory/home"
mkdir -p "$HOME"

source "${0:A:h:h}/common.sh"

REPOSITORY_ROOT="$temporary_directory/repository"
GITHOOKS_DIRECTORY="$REPOSITORY_ROOT/.githooks"
RUNTIME_SKILL_PATHS=()
SKILL_PROVIDERS=(
  "$HOME/.claude/skills"
  "$HOME/.codex/skills"
  "$HOME/.gemini/skills"
  "$HOME/.pi/agent/skills"
)
CbrBlk=""
Cb=""
Cb0=""
Cgrn=""
C0=""

for provider in "${SKILL_PROVIDERS[@]}"; do
  mkdir -p "$provider"
done

mkdir -p \
  "$REPOSITORY_ROOT/skills/colliding" \
  "$REPOSITORY_ROOT/skills/following" \
  "$REPOSITORY_ROOT/plugins/example/skills/plugin-skill"
touch \
  "$REPOSITORY_ROOT/skills/colliding/SKILL.md" \
  "$REPOSITORY_ROOT/skills/following/SKILL.md"
echo "plugin skill" >"$REPOSITORY_ROOT/plugins/example/skills/plugin-skill/SKILL.md"

colliding_destination="$HOME/.claude/skills/colliding"
mkdir -p "$colliding_destination"
echo "consumer-owned" >"$colliding_destination/owner"

report="$temporary_directory/report"
render_skills 2>"$report"

[[ "$(cat "$colliding_destination/owner")" == "consumer-owned" ]] || {
  echo "The materializer changed the consumer-owned destination." >&2
  exit 1
}
[[ ! -L "$colliding_destination" ]] || {
  echo "The materializer replaced the consumer-owned destination with a symlink." >&2
  exit 1
}
for provider in "${SKILL_PROVIDERS[@]}"; do
  [[ -L "$provider/following" ]] || {
    echo "The materializer stopped before linking the following skill into $provider." >&2
    exit 1
  }
done
[[ -L "$HOME/.codex/skills/colliding" ]] || {
  echo "The materializer stopped linking the colliding skill after the refusal." >&2
  exit 1
}
[[ -L "$HOME/.pi/agent/skills/plugin-skill/SKILL.md" ]] || {
  echo "The materializer stopped before the plugin skill phase." >&2
  exit 1
}
rg -Fq "Refusing to link over non-symlink destination: $colliding_destination" "$report" || {
  echo "The materializer did not report the concrete destination refusal." >&2
  exit 1
}
