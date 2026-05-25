#!/usr/bin/env bash
set -euo pipefail

main() {
  local localhost_response
  localhost_response="$(curl -s http://localhost:9222/json/version 2>/dev/null | jq -r '.webSocketDebuggerUrl // empty')"
  if [[ $? != 0 || -z "$localhost_response" ]]; then
    echo 'Chrome not reachable on port 9222. Launch it first:' 1>&2
    echo '  /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222 --user-data-dir="$HOME/.agent-browser/custom-debug-profile"' 1>&2
    return 1
  fi

  local tab_id

  # ── Claude ──────────────────────────────────────────────
  tab_id="$(agent-browser --cdp 9222 tab --json 2>/dev/null | jq -r '.data.tabs[] | select(.url | contains("claude.ai/settings/usage")) | .tabId')"
  if [[ -n "$tab_id" ]]; then
    agent-browser --cdp 9222 tab "$tab_id" >/dev/null 2>&1
    agent-browser --cdp 9222 reload >/dev/null 2>&1
  else
    agent-browser --cdp 9222 tab new https://claude.ai/settings/usage >/dev/null 2>&1
  fi
  sleep 3

  echo "=== CLAUDE ==="
  agent-browser --cdp 9222 get text "body" 2>/dev/null | grep -A 4 -i -E "Current session|Weekly|Usage|Messages|remaining|limit" | head -20
  echo ""

  # ── Codex ───────────────────────────────────────────────
  tab_id="$(agent-browser --cdp 9222 tab --json 2>/dev/null | jq -r '.data.tabs[] | select(.url | contains("chatgpt.com")) | .tabId')"
  if [[ -n "$tab_id" ]]; then
    agent-browser --cdp 9222 tab "$tab_id" >/dev/null 2>&1
    agent-browser --cdp 9222 reload >/dev/null 2>&1
  else
    agent-browser --cdp 9222 tab new https://chatgpt.com/codex/cloud/settings/analytics >/dev/null 2>&1
  fi
  sleep 3

  echo "=== CODEX ==="
  agent-browser --cdp 9222 get text "body" 2>/dev/null | grep -A 4 -i -E "usage limit|Usage|remaining|limit|hour" | head -20
}

main "$@"
