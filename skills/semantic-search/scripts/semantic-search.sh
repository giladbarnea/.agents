#!/usr/bin/env bash

set -euo pipefail

interactive=false
query=""
search_path="$(pwd)"
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

for arg in "$@"; do
  if [[ "$arg" == "-i" ]]; then
    interactive=true
  elif [[ -z "$query" ]]; then
    query="$arg"
  else
    search_path="$arg"
  fi
done

if [[ -z "$query" ]]; then
  printf 'Usage: %s [-i] <query> [search_path]\n' "${0##*/}" >&2
  exit 1
fi

prompt_template="$(<"$script_dir/../references/prompt.md")"
full_prompt="$(printf "$prompt_template" "$search_path" "$query")"
pi_args=(--model openai-codex/gpt-5.6-luna --thinking medium --no-skills -np --no-extensions -e npm:@ff-labs/pi-fff -e npm:@monotykamary/pi-vcc -e ~/.pi/agent/extensions/read-many-files/index.ts -e ~/.pi/agent/extensions/smart-truncation/index.ts -a --no-session)

if [[ $interactive = false ]]; then
  pi_args+=(--print)
fi

printf "[log] Launching ‘pi’ with a fast model prompted well with respect to ‘${search_path}’ and your query. Ignore warnings (if you see any) about not finding claude models — these are irrelevant. The search process can take a few long minutes, be patient. It will simply print its results to stdout when it’s done."
pi "${pi_args[@]}" "$full_prompt" 2>&1
