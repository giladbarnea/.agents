#!/usr/bin/env bash

set -euo pipefail

readonly SCRIPT_DIRECTORY="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly REPOSITORY_ROOT="$(cd "$SCRIPT_DIRECTORY/.." && pwd)"
readonly SOURCE_PLUGINS_DIRECTORY="$REPOSITORY_ROOT/plugins"
readonly PLUGIN_VERSION="0.0.0"
readonly CLAUDE_DIRECTORY="$HOME/.claude"
readonly SETTINGS_FILE="$CLAUDE_DIRECTORY/settings.json"
readonly KNOWN_MARKETPLACES_FILE="$CLAUDE_DIRECTORY/plugins/known_marketplaces.json"
readonly INSTALLED_PLUGINS_FILE="$CLAUDE_DIRECTORY/plugins/installed_plugins.json"
readonly CURRENT_TIMESTAMP="$(date -u +'%Y-%m-%dT%H:%M:%S.000Z')"
readonly TEMPORARY_DIRECTORY="$(mktemp -d)"

trap 'rm -rf "$TEMPORARY_DIRECTORY"' EXIT

fail() {
  printf '✗ %s\n' "$1" >&2
  exit 1
}

replace_file() {
  local source_file="$1"
  local destination_file="$2"
  local destination_mode

  destination_mode="$(stat -f '%Lp' "$destination_file")"
  chmod "$destination_mode" "$source_file"
  mv "$source_file" "$destination_file"
}

sync_plugin() {
  local source_plugin_directory="$1"
  local plugin_name
  local marketplace_name
  local marketplace_directory
  local generated_plugin_directory
  local cache_directory
  local plugin_identifier
  local plugin_description
  local has_non_empty_skill
  local skill_file
  local skill_directory
  local expected_skill_name
  local skill_name
  local skill_description
  local settings_temporary_file
  local known_marketplaces_temporary_file
  local installed_plugins_temporary_file
  local -a skill_files

  plugin_name="$(basename "$source_plugin_directory")"
  marketplace_name="$plugin_name"
  marketplace_directory="$CLAUDE_DIRECTORY/plugins/marketplaces/$marketplace_name"
  generated_plugin_directory="$marketplace_directory/plugins/$plugin_name"
  cache_directory="$CLAUDE_DIRECTORY/plugins/cache/$marketplace_name/$plugin_name/$PLUGIN_VERSION"
  plugin_identifier="$plugin_name@$marketplace_name"

  [[ -d "$source_plugin_directory/skills" ]] || fail "Missing plugin skills directory: $source_plugin_directory/skills"

  skill_files=("$source_plugin_directory"/skills/*/SKILL.md)
  has_non_empty_skill=0
  for skill_file in "${skill_files[@]}"; do
    [[ -s "$skill_file" ]] && has_non_empty_skill=1
  done
  (( has_non_empty_skill == 1 )) || fail "Plugin has no non-empty skills/*/SKILL.md: $source_plugin_directory"

  plugin_description=""
  for skill_file in "${skill_files[@]}"; do
    skill_directory="$(dirname "$skill_file")"
    expected_skill_name="$(basename "$skill_directory")"
    skill_name="$(yq --front-matter=extract '.name // ""' "$skill_file")"
    skill_description="$(yq --front-matter=extract '.description // ""' "$skill_file")"

    [[ "$skill_name" == "$expected_skill_name" ]] || fail "Skill name does not match its directory: $skill_file"
    [[ -n "$skill_description" ]] || fail "Skill has no description: $skill_file"
    [[ -n "$plugin_description" ]] || plugin_description="$skill_description"
  done

  mkdir -p "$marketplace_directory/.claude-plugin"
  mkdir -p "$generated_plugin_directory/.claude-plugin"
  mkdir -p "$generated_plugin_directory/skills"
  mkdir -p "$cache_directory"

  rsync -a --delete "$source_plugin_directory/skills/" "$generated_plugin_directory/skills/"

  jq -n \
    --arg name "$plugin_name" \
    --arg version "$PLUGIN_VERSION" \
    --arg description "$plugin_description" \
    '{name: $name, version: $version, description: $description}' \
    > "$generated_plugin_directory/.claude-plugin/plugin.json"

  jq -n \
    --arg name "$marketplace_name" \
    --arg plugin_name "$plugin_name" \
    --arg plugin_description "$plugin_description" \
    '{
      name: $name,
      description: ("Local marketplace for " + $name + "."),
      owner: {name: "Gilad Barnea"},
      plugins: [{
        name: $plugin_name,
        source: ("./plugins/" + $plugin_name),
        description: $plugin_description,
        category: "productivity"
      }]
    }' \
    > "$marketplace_directory/.claude-plugin/marketplace.json"

  rsync -a --delete "$generated_plugin_directory/" "$cache_directory/"

  settings_temporary_file="$TEMPORARY_DIRECTORY/settings.json"
  jq \
    --arg marketplace_name "$marketplace_name" \
    --arg marketplace_path "$marketplace_directory" \
    --arg plugin_identifier "$plugin_identifier" \
    '.extraKnownMarketplaces[$marketplace_name] = {
        source: {source: "directory", path: $marketplace_path}
      }
      | .enabledPlugins[$plugin_identifier] = true' \
    "$SETTINGS_FILE" \
    > "$settings_temporary_file"
  replace_file "$settings_temporary_file" "$SETTINGS_FILE"

  known_marketplaces_temporary_file="$TEMPORARY_DIRECTORY/known-marketplaces.json"
  jq \
    --arg marketplace_name "$marketplace_name" \
    --arg marketplace_path "$marketplace_directory" \
    --arg current_timestamp "$CURRENT_TIMESTAMP" \
    '.[$marketplace_name] = {
        source: {source: "directory", path: $marketplace_path},
        installLocation: $marketplace_path,
        lastUpdated: $current_timestamp
      }' \
    "$KNOWN_MARKETPLACES_FILE" \
    > "$known_marketplaces_temporary_file"
  replace_file "$known_marketplaces_temporary_file" "$KNOWN_MARKETPLACES_FILE"

  installed_plugins_temporary_file="$TEMPORARY_DIRECTORY/installed-plugins.json"
  jq \
    --arg plugin_identifier "$plugin_identifier" \
    --arg cache_directory "$cache_directory" \
    --arg plugin_version "$PLUGIN_VERSION" \
    --arg current_timestamp "$CURRENT_TIMESTAMP" \
    '.version = 2
      | .plugins[$plugin_identifier] = [{
          scope: "user",
          installPath: $cache_directory,
          version: $plugin_version,
          installedAt: $current_timestamp,
          lastUpdated: $current_timestamp
        }]' \
    "$INSTALLED_PLUGINS_FILE" \
    > "$installed_plugins_temporary_file"
  replace_file "$installed_plugins_temporary_file" "$INSTALLED_PLUGINS_FILE"

  jq empty \
    "$marketplace_directory/.claude-plugin/marketplace.json" \
    "$generated_plugin_directory/.claude-plugin/plugin.json" \
    "$SETTINGS_FILE" \
    "$KNOWN_MARKETPLACES_FILE" \
    "$INSTALLED_PLUGINS_FILE"

  printf '✓ Synced %s into Claude as %s\n' "$source_plugin_directory" "$plugin_identifier"
}

[[ $# -eq 0 ]] || fail "Usage: $0"

for required_command in jq rsync yq; do
  command -v "$required_command" >/dev/null 2>&1 || fail "Missing command: $required_command"
done

[[ -f "$SETTINGS_FILE" ]] || fail "Missing Claude settings: $SETTINGS_FILE"
[[ -f "$KNOWN_MARKETPLACES_FILE" ]] || fail "Missing Claude marketplace registry: $KNOWN_MARKETPLACES_FILE"
[[ -f "$INSTALLED_PLUGINS_FILE" ]] || fail "Missing Claude plugin registry: $INSTALLED_PLUGINS_FILE"

plugin_directories=("$SOURCE_PLUGINS_DIRECTORY"/*/)
[[ -d "${plugin_directories[0]}" ]] || fail "No plugins found in: $SOURCE_PLUGINS_DIRECTORY"

for plugin_directory in "${plugin_directories[@]}"; do
  sync_plugin "${plugin_directory%/}"
done
