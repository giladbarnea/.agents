#!/usr/bin/env bash

set -euo pipefail

if [ "$#" -lt 1 ]; then
  printf 'Usage: %s <query>\n' "${0##*/}" >&2
  exit 1
fi

query="$*"
path="$(pwd)"

printf -v prompt \
  "Search relevant files in '%s'/**/* to the following query, then list them in a 2 column table: file path and relevancy score, as you judged it, from 0 to 10. don't explain or describe the files. optimize for recall. better include with low relevancy than a false negative. the query is: %s" \
  "$path" \
  "$query"

pi --model ds4f --no-skills -np --no-session --no-extensions --print $(printf '%q' "$prompt")
