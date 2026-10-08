#!/usr/bin/env bash
# Rejects a published soft-skills tree whose Markdown names Gilad or ADHD.
# The GitHub handle giladbarnea is allowed, hence the word boundaries.
set -euo pipefail

published_repository="$1"
if rg -il '\bgilad\b|\badhd\b' --glob '*.md' --glob '!.git' "$published_repository"; then
  printf 'Private names remain in published Markdown.\n' >&2
  exit 1
fi
