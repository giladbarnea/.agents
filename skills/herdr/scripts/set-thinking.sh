#!/bin/sh
if uv run --quiet --no-project "$(dirname "$0")/session-command.py" thinking "$@"; then
    exit 0
fi
exit 1
