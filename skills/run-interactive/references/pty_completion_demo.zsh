#!/usr/bin/env zsh

# Toy example: drive an interactive zsh completion session through a PTY.
#
# This is meant as a reference for future agents, not a polished test harness.
# It shows the key idea:
#   1. Start `zsh -fi` inside a pseudo-terminal.
#   2. Send commands incrementally, like a human typing.
#   3. Send a literal Tab character.
#   4. Read back whatever the terminal emitted.
#
# Usage:
#   zsh /tmp/pty_completion_demo.zsh /absolute/path/to/completion_file [command_prefix]
#
# Example:
#   zsh /tmp/pty_completion_demo.zsh \
#     /Users/giladbarnea/dev/land/completions/_pi \
#     'pi --model '

set -u

if (( $# < 1 )); then
  print -u2 -- "Usage: zsh $0 /absolute/path/to/completion_file [command_prefix]"
  exit 1
fi

local completion_file=$1
local command_prefix=${2:-'pi --model '}

if [[ ! -f $completion_file ]]; then
  print -u2 -- "Completion file not found: $completion_file"
  exit 1
fi

zmodload zsh/zpty || {
  print -u2 -- "Failed to load zsh/zpty"
  exit 1
}
autoload -Uz zpty

local session=demo_completion_$$
local line

cleanup() {
  zpty -d "$session" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# Start a real interactive shell.
zpty -b "$session" /bin/zsh -fi

# Helper: write bytes to the PTY, then wait briefly.
send() {
  local payload=$1
  zpty -w "$session" "$payload"
  sleep 0.2
}

# Helper: drain whatever output is currently available.
drain() {
  while zpty -r -t "$session" line 2>/dev/null; do
    print -r -- "$line"
  done
}

print -- "=== Bootstrapping interactive zsh ==="
send $'autoload -Uz compinit\n'
drain

send $'compinit -D\n'
drain

send $"source ${completion_file}\n"
drain

print -- "=== Sending command prefix ==="
send "$command_prefix"
drain

print -- "=== Sending literal TAB ==="
send $'\t'
drain

print -- "=== Done ==="
print -- "If completion worked, you should see a list, a prompt redraw, or the buffer change."
print -- "If it failed, you may see a bell, an error message, or no output at all."
