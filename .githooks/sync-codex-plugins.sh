#!/usr/bin/env bash

set -euo pipefail

readonly SCRIPT_DIRECTORY="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly REPOSITORY_ROOT="$(cd -- "$SCRIPT_DIRECTORY/.." && pwd)"
readonly SOURCE_PLUGINS_DIRECTORY="$REPOSITORY_ROOT/plugins"
readonly PLUGIN_VERSION="0.0.0"
readonly CODEX_DIRECTORY="$HOME/.codex"
readonly CONFIGURATION_FILE="$CODEX_DIRECTORY/config.toml"
readonly UPDATED_AT="$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
readonly TEMPORARY_DIRECTORY="$(mktemp -d "$CODEX_DIRECTORY/.sync-codex-plugins.XXXXXX")"

trap 'rm -R "$TEMPORARY_DIRECTORY"' EXIT

fail() {
  echo "$1" >&2
  exit 1
}

sync_plugin() {
  local source_plugin_directory="$1"
  local plugin_name
  local marketplace_name
  local source_skills_directory
  local marketplace_directory
  local generated_plugin_directory
  local cache_directory
  local plugin_identifier
  local temporary_configuration_file
  local has_non_empty_skill
  local skill_file
  local -a skill_files

  plugin_name="$(basename "$source_plugin_directory")"
  marketplace_name="$plugin_name"
  source_skills_directory="$source_plugin_directory/skills"
  marketplace_directory="$CODEX_DIRECTORY/plugins/marketplaces/$marketplace_name"
  generated_plugin_directory="$marketplace_directory/plugins/$plugin_name"
  cache_directory="$CODEX_DIRECTORY/plugins/cache/$marketplace_name/$plugin_name/$PLUGIN_VERSION"
  plugin_identifier="$plugin_name@$marketplace_name"

  [[ -d "$source_skills_directory" ]] || fail "Missing plugin skills directory: $source_skills_directory"
  skill_files=("$source_skills_directory"/*/SKILL.md)
  has_non_empty_skill=0
  for skill_file in "${skill_files[@]}"; do
    [[ -s "$skill_file" ]] && has_non_empty_skill=1
  done
  (( has_non_empty_skill == 1 )) || fail "Plugin has no non-empty skills/*/SKILL.md: $source_plugin_directory"

  mkdir -p \
    "$generated_plugin_directory/.codex-plugin" \
    "$generated_plugin_directory/skills" \
    "$marketplace_directory/.agents/plugins" \
    "$cache_directory"

  rsync -a --delete "$source_skills_directory/" "$generated_plugin_directory/skills/"

  jq --null-input \
    --arg name "$plugin_name" \
    --arg version "$PLUGIN_VERSION" \
    '{
      name: $name,
      version: $version,
      description: "A locally synchronized plugin.",
      skills: "./skills/"
    }' > "$generated_plugin_directory/.codex-plugin/plugin.json"

  jq --null-input \
    --arg name "$marketplace_name" \
    --arg plugin_name "$plugin_name" \
    '{
      name: $name,
      interface: {displayName: $name},
      plugins: [{
        name: $plugin_name,
        source: {source: "local", path: ("./plugins/" + $plugin_name)},
        policy: {installation: "AVAILABLE", authentication: "ON_INSTALL"},
        category: "Productivity"
      }]
    }' > "$marketplace_directory/.agents/plugins/marketplace.json"

  rsync -a --delete "$generated_plugin_directory/" "$cache_directory/"

  temporary_configuration_file="$TEMPORARY_DIRECTORY/config.toml"
  cp -p "$CONFIGURATION_FILE" "$temporary_configuration_file"

  uv run -p python3 --with=tomlkit python3 - \
    "$temporary_configuration_file" \
    "$plugin_identifier" \
    "$marketplace_name" \
    "$marketplace_directory" \
    "$UPDATED_AT" <<'PYTHON'
from pathlib import Path
import sys

import tomlkit

configuration_path = Path(sys.argv[1])
plugin_identifier = sys.argv[2]
marketplace_name = sys.argv[3]
marketplace_directory = sys.argv[4]
updated_at = sys.argv[5]

document = tomlkit.parse(configuration_path.read_text())

features = document.get("features")
if features is None:
    features = tomlkit.table()
    document["features"] = features
features["plugins"] = True

plugins = document.get("plugins")
if plugins is None:
    plugins = tomlkit.table()
    document["plugins"] = plugins

plugin = plugins.get(plugin_identifier)
if plugin is None:
    plugin = tomlkit.table()
    plugins[plugin_identifier] = plugin
plugin["enabled"] = True

marketplaces = document.get("marketplaces")
if marketplaces is None:
    marketplaces = tomlkit.table()
    document["marketplaces"] = marketplaces

marketplace = marketplaces.get(marketplace_name)
if marketplace is None:
    marketplace = tomlkit.table()
    marketplaces[marketplace_name] = marketplace
marketplace["last_updated"] = updated_at
marketplace["source_type"] = "local"
marketplace["source"] = marketplace_directory

configuration_path.write_text(tomlkit.dumps(document))
PYTHON

  mv "$temporary_configuration_file" "$CONFIGURATION_FILE"

  jq empty "$generated_plugin_directory/.codex-plugin/plugin.json"
  jq empty "$marketplace_directory/.agents/plugins/marketplace.json"

  echo "Synchronized $plugin_identifier for Codex."
}

[[ $# -eq 0 ]] || fail "Usage: $0"

for required_command in jq rsync uv; do
  command -v "$required_command" >/dev/null 2>&1 || fail "Missing command: $required_command"
done

[[ -f "$CONFIGURATION_FILE" ]] || fail "Missing Codex configuration: $CONFIGURATION_FILE"

plugin_directories=("$SOURCE_PLUGINS_DIRECTORY"/*/)
[[ -d "${plugin_directories[0]}" ]] || fail "No plugins found in: $SOURCE_PLUGINS_DIRECTORY"

for plugin_directory in "${plugin_directories[@]}"; do
  sync_plugin "${plugin_directory%/}"
done
