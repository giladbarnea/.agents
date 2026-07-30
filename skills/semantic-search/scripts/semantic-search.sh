#!/usr/bin/env bash

set -euo pipefail

interactive=false
query=""
search_path="$(pwd)"

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

full_prompt="$(
  printf "Search relevant files in '%s'/**/* to the following query, then list them in a 2 column table: file path and relevancy score, as you judged it, from 0 to 10. Read files in full. No ‘head’, no ’tail’. Just read them. Don't explain or describe the files. Optimize for recall. Better include with low relevancy than a false negative. The query is: %s" \
    "$search_path" \
    "$query"
)"
pi_args=(--model ds4f --thinking high --no-skills -np --no-extensions -e ~/.pi/agent/extensions/read-many-files.ts -e ~/.pi/agent/extensions/smart-truncation.ts -a --no-session)

if [[ $interactive = false ]]; then
  pi_args+=(--print)
fi

printf "[log] Launching ‘pi’ with a fast model prompted well with respect to ‘${search_path}’ and your query. Ignore process init warnings about not finding claude models — these are irrelevant. The search process can take a few long minutes, be patient. It will simply print its results to stdout when it’s done."
pi "${pi_args[@]}" "$full_prompt" 2>&1
