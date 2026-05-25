# AI Usage Limits

Run `~/.agents/skills/agent-browser/scripts/scrape_usage.sh | uv run ~/.agents/skills/agent-browser/scripts/compute_usage.py`.

If Chrome isn't on port 9222, launch it first:
```
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222 --user-data-dir="$HOME/.agent-browser/custom-debug-profile"
```
