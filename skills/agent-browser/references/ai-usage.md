# AI Usage Limits

Run `uv run ~/.agents/skills/agent-browser/scripts/usage.py`.

Keep a real logged-in Chrome running with remote debugging on `:9222`, for example:

```bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222 --user-data-dir="$HOME/.agent-browser/custom-debug-profile"
```

This workflow uses direct CDP against that Chrome session because Claude and ChatGPT/Codex usage pages trip bot checks in headless runs. The script reloads matching tabs in place, or opens missing ones in the background.
