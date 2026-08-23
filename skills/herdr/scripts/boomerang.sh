#!/usr/bin/env bash

set -euo pipefail

main() {
  local before=""
  local after=""
  local text=""
  local text_set=0

  while (($#)); do
    case "$1" in
      --before=*) before="${1#--before=}" ;;
      --after=*) after="${1#--after=}" ;;
      --before | --after)
        if (($# < 2)); then
          printf 'boomerang: %s requires a value\n' "$1" >&2
          return 2
        fi
        if [[ "$1" == "--before" ]]; then
          before="$2"
        else
          after="$2"
        fi
        shift
        ;;
      --*)
        printf 'boomerang: unknown option: %s\n' "$1" >&2
        return 2
        ;;
      *)
        if ((text_set)); then
          printf 'boomerang: expected exactly one text argument\n' >&2
          return 2
        fi
        text="$1"
        text_set=1
        ;;
    esac
    shift
  done

  if ((!text_set)) || [[ -z "$text" ]]; then
    printf 'usage: boomerang.sh [--before="BASH"] [--after="BASH"] "TEXT"\n' >&2
    return 2
  fi

  [[ "${HERDR_ENV:-}" == "1" ]] || {
    printf 'boomerang: this Pi session is not running inside Herdr\n' >&2
    return 1
  }
  [[ -n "${PI_SESSION_ID:-}" ]] || {
    printf 'boomerang: PI_SESSION_ID is unavailable\n' >&2
    return 1
  }
  command -v herdr >/dev/null || {
    printf 'boomerang: herdr is unavailable\n' >&2
    return 1
  }
  command -v jq >/dev/null || {
    printf 'boomerang: jq is unavailable\n' >&2
    return 1
  }

  [[ -z "$before" ]] || eval "$before"

  local location
  location="$(
    herdr agent list | jq -r --arg session_id "$PI_SESSION_ID" '
      .result.agents[]
      | select(.agent == "pi")
      | select((.agent_session.value // "") | contains($session_id))
      | [.workspace_id, .tab_id, .pane_id]
      | @tsv
    '
  )"

  if [[ -z "$location" ]]; then
    printf 'boomerang: no live Herdr Pi agent matches session %s\n' "$PI_SESSION_ID" >&2
    return 1
  fi
  if [[ "$location" == *$'\n'* ]]; then
    printf 'boomerang: multiple Herdr Pi agents match session %s\n' "$PI_SESSION_ID" >&2
    return 1
  fi

  local workspace_id
  local tab_id
  local pane_id
  IFS=$'\t' read -r workspace_id tab_id pane_id <<<"$location"
  if [[ -z "$workspace_id" || -z "$tab_id" || -z "$pane_id" ]]; then
    printf 'boomerang: incomplete Herdr location for session %s\n' "$PI_SESSION_ID" >&2
    return 1
  fi

  herdr agent prompt "$pane_id" "$text"

  [[ -z "$after" ]] || eval "$after"
}

main "$@" </dev/null >>"${BOOMERANG_LOG:-/dev/null}" 2>&1 &
