#!/usr/bin/env bash
# Run an X advanced search in the logged-in debug Chrome (CDP 9222) and print one line per post:
#   <datetime> <@handle> <Replying to ...> :: <text> :: <url>
# Usage: x_search.sh '<query with operators>' [scroll_steps=5] [tab=live|top]
set -euo pipefail

query="$1"
scroll_steps="${2:-5}"
tab="${3:-live}"
# A session remembers its bound tab across runs, so each run gets its own session and tab.
session_flags=(--session "x-search-$$" --pin-tab)

agent-browser "${session_flags[@]}" connect 9222 >/dev/null
encoded_query="$(jq -rn --arg q "$query" '$q|@uri')"
agent-browser "${session_flags[@]}" open "https://x.com/search?q=${encoded_query}&f=${tab}" >/dev/null
agent-browser "${session_flags[@]}" wait 3500 >/dev/null

# X unmounts off-screen posts, so collect at every scroll step and dedupe.
collect='JSON.stringify(Array.from(document.querySelectorAll("article")).map(a => {
  const datetime = a.querySelector("time")?.getAttribute("datetime")?.slice(0, 16) || "";
  const handle = a.querySelector("[data-testid=User-Name]")?.innerText.split("\n")[1] || "";
  const replyingTo = (a.innerText.match(/Replying to[^\n]*\n?[^\n]*/)?.[0] || "").replace(/\n/g, " ");
  const text = (a.querySelector("[data-testid=tweetText]")?.innerText || "").replace(/\n/g, " ");
  const url = a.querySelector("time")?.closest("a")?.href || "";
  return `${datetime} ${handle} ${replyingTo} :: ${text} :: ${url}`;
}))'

for _ in $(seq 1 "$scroll_steps"); do
  agent-browser "${session_flags[@]}" eval "$collect" | jq -r 'fromjson | .[]'
  agent-browser "${session_flags[@]}" scroll down 2500 >/dev/null
  agent-browser "${session_flags[@]}" wait 1500 >/dev/null
done | awk '!seen[$0]++'

# `close` ends the session but leaves its pinned tab open.
agent-browser "${session_flags[@]}" tab close >/dev/null
agent-browser "${session_flags[@]}" close >/dev/null
