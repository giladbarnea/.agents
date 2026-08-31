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
  printf "${Cred:-}✗ %s${C0:-}\n" "$1" >&2
  exit 1
}

collect_plugin_names() {
  local output_file="$1"
  local plugin_directory

  {
    for plugin_directory in "$SOURCE_PLUGINS_DIRECTORY"/*/; do
      [[ -d "$plugin_directory" ]] || continue
      basename "$plugin_directory"
    done

    {
      git -C "$REPOSITORY_ROOT" diff --no-renames --name-only --diff-filter=D -- plugins
      git -C "$REPOSITORY_ROOT" diff --cached --no-renames --name-only --diff-filter=D -- plugins
      if [[ -n "${PLUGIN_SYNC_GIT_RANGE:-}" ]]; then
        git -C "$REPOSITORY_ROOT" diff --no-renames --name-only --diff-filter=D "$PLUGIN_SYNC_GIT_RANGE" -- plugins
      fi
    } | awk -F/ '$1 == "plugins" && $2 !~ /^\./ && NF >= 3 {print $2}'
  } | sort -u >"$output_file"
}

plugin_has_non_empty_skill() {
  local source_plugin_directory="$1"
  local skill_file

  for skill_file in "$source_plugin_directory"/skills/*/SKILL.md; do
    [[ -s "$skill_file" ]] && return 0
  done
  return 1
}

update_configuration() {
  local action="$1"
  local plugin_identifier="$2"
  local marketplace_name="$3"
  local marketplace_directory="$4"
  local temporary_configuration_file="$TEMPORARY_DIRECTORY/config.toml"

  cp -p "$CONFIGURATION_FILE" "$temporary_configuration_file"

  uv run -p python3 --with=tomlkit python3 - \
    "$temporary_configuration_file" \
    "$action" \
    "$plugin_identifier" \
    "$marketplace_name" \
    "$marketplace_directory" \
    "$UPDATED_AT" <<'PYTHON'
from pathlib import Path
import sys

import tomlkit

configuration_path = Path(sys.argv[1])
action = sys.argv[2]
plugin_identifier = sys.argv[3]
marketplace_name = sys.argv[4]
marketplace_directory = sys.argv[5]
updated_at = sys.argv[6]

document = tomlkit.parse(configuration_path.read_text())

if action == "remove":
    document.get("plugins", {}).pop(plugin_identifier, None)
    document.get("marketplaces", {}).pop(marketplace_name, None)
    configuration_path.write_text(tomlkit.dumps(document))
    raise SystemExit

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
}

remove_plugin() {
  local plugin_name="$1"
  local marketplace_name="$plugin_name"
  local marketplace_directory="$CODEX_DIRECTORY/plugins/marketplaces/$marketplace_name"
  local cache_directory="$CODEX_DIRECTORY/plugins/cache/$marketplace_name"
  local plugin_identifier="$plugin_name@$marketplace_name"

  update_configuration remove "$plugin_identifier" "$marketplace_name" "$marketplace_directory"
  rm -rf "$marketplace_directory" "$cache_directory"

  printf "${Cgrn:-}✓${C0:-} Removed ${Cb:-}%s${Cb0:-} from Codex ${CbrBlk:-}(%s)${C0:-}\n" \
    "$plugin_name" "$plugin_identifier" >&2
}

sync_plugin() {
  local source_plugin_directory="$1"
  local plugin_name
  local marketplace_name
  local marketplace_directory
  local generated_plugin_directory
  local cache_directory
  local plugin_identifier

  plugin_name="$(basename "$source_plugin_directory")"
  marketplace_name="$plugin_name"
  marketplace_directory="$CODEX_DIRECTORY/plugins/marketplaces/$marketplace_name"
  generated_plugin_directory="$marketplace_directory/plugins/$plugin_name"
  cache_directory="$CODEX_DIRECTORY/plugins/cache/$marketplace_name/$plugin_name/$PLUGIN_VERSION"
  plugin_identifier="$plugin_name@$marketplace_name"

  [[ -d "$source_plugin_directory/skills" ]] || fail "Missing plugin skills directory: $source_plugin_directory/skills"

  mkdir -p \
    "$generated_plugin_directory" \
    "$marketplace_directory/.agents/plugins" \
    "$cache_directory"

  rsync -a --delete "$source_plugin_directory/" "$generated_plugin_directory/"
  mkdir -p "$generated_plugin_directory/.codex-plugin"

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
  update_configuration sync "$plugin_identifier" "$marketplace_name" "$marketplace_directory"

  jq empty "$generated_plugin_directory/.codex-plugin/plugin.json"
  jq empty "$marketplace_directory/.agents/plugins/marketplace.json"

  printf "${Cgrn:-}✓${C0:-} Synced ${Cb:-}%s${Cb0:-} → Codex ${CbrBlk:-}(%s)${C0:-}\n" \
    "$plugin_name" "$plugin_identifier" >&2
}

reconcile_plugin() {
  local plugin_name="$1"
  local source_plugin_directory="$SOURCE_PLUGINS_DIRECTORY/$plugin_name"

  if [[ ! -d "$source_plugin_directory" ]]; then
    remove_plugin "$plugin_name"
    return
  fi

  if plugin_has_non_empty_skill "$source_plugin_directory"; then
    sync_plugin "$source_plugin_directory"
    return
  fi

  printf "${Cylw:-}⚠ Plugin exists without a non-empty skills/*/SKILL.md; leaving Codex unchanged: %s${C0:-}\n" \
    "$source_plugin_directory" >&2
}

[[ $# -eq 0 ]] || fail "Usage: $0"

for required_command in jq rsync uv; do
  command -v "$required_command" >/dev/null 2>&1 || fail "Missing command: $required_command"
done

[[ -f "$CONFIGURATION_FILE" ]] || fail "Missing Codex configuration: $CONFIGURATION_FILE"

plugin_names_file="$TEMPORARY_DIRECTORY/plugin-names"
collect_plugin_names "$plugin_names_file"

while IFS= read -r plugin_name; do
  reconcile_plugin "$plugin_name"
done <"$plugin_names_file"
