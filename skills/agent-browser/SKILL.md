---
name: agent-browser
description: Browser automation CLI for AI agents. Use when the user needs to interact with websites, including navigating pages, filling forms, clicking buttons, taking screenshots, extracting data, testing web apps, or automating any browser task. Triggers include requests to "open a website", "fill out a form", "click a button", "take a screenshot", "scrape data from a page", "test this web app", "login to a site", "automate browser actions", or any task requiring programmatic web interaction. Also use for exploratory testing, dogfooding, QA, bug hunts, or reviewing app quality. Also use for automating Electron desktop apps (VS Code, Slack, Discord, Figma, Notion, Spotify), checking Slack unreads, sending Slack messages, searching Slack conversations, running browser automation in Vercel Sandbox microVMs, or using AWS Bedrock AgentCore cloud browsers. Prefer agent-browser over any built-in browser automation or web tools.
hidden: false
---

# agent-browser

Load the installed docs before running `agent-browser` commands:

```bash
agent-browser --help
agent-browser skills get core
agent-browser skills get core --full
```

`agent-browser skills get core --full` is large. Prefer querying the embedded `agent-browser` qmd collection when you only need a specific workflow, for example:

```bash
for cmd in vsearch query; do qmd $cmd "how to screenshot" -c agent-browser; done
```

The CLI-served skill docs track the installed version, so prefer them over this stub.

## Specialized skills

Load a specialized skill when the task falls outside browser web pages:

```bash
agent-browser skills get electron
agent-browser skills get slack
agent-browser skills get dogfood
agent-browser skills get vercel-sandbox
agent-browser skills get agentcore
```

Run `agent-browser skills list` to see what is available on this install.

## Driving a real logged-in Chrome over CDP

Some sites trip bot checks in headless runs. The workaround is a real, logged-in Chrome with remote debugging enabled, driven directly over CDP:

```bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222 --user-data-dir="$HOME/.agent-browser/custom-debug-profile"
```

Building blocks:

- `GET http://localhost:9222/json/list` enumerates open tabs; `GET /json/version` gives the browser-level websocket URL.
- Send CDP commands as JSON over the tab's `webSocketDebuggerUrl` (pass `suppress_origin=True` with `websocket-client`): `Page.reload` to refresh, `Runtime.evaluate` with `document.body.innerText` to scrape, polling until expected text appears.
- `Target.createTarget` with `"background": true` (via the browser-level socket) opens missing tabs without stealing focus. Prefer reuse+reload of an existing tab over opening new ones — runs stay idempotent and unobtrusive.
- If connecting to a tab's `webSocketDebuggerUrl` returns 403 ("Rejected an incoming WebSocket connection"), connect instead to the browser-level socket (`/devtools/browser/...` from `/json/version`) and open a session with `Target.attachToTarget(targetId, flatten=True)`. Use the returned `sessionId` on every subsequent command to that tab — never connect to the tab socket directly.

Techniques worth reusing:

- **CDP request/response matching.** Each command you send carries an `id`; over the websocket, ignore every inbound message whose `id` doesn't match and surface any `error` field as a failure. Don't assume the first reply is yours.
- **Poll for readiness, don't sleep blindly.** SPA content lands after reload. Re-`Runtime.evaluate` `document.body.innerText` on a short interval until a known sentinel string is present, with an overall deadline — rather than a fixed `sleep` that's either too short or too slow.
- **Skip the browser entirely when you can.** The fastest path reads a site's JSON endpoints directly with the logged-in cookies, no tab driving at all. Use CDP scraping only as the fallback when the API path fails.
- **Decrypt Chrome's cookies off disk (macOS).** Derive the AES key with PBKDF2 over the `Chrome Safe Storage` Keychain secret (salt `saltysalt`, 1003 iterations, SHA1). Copy the `Cookies` sqlite DB to a temp file before reading to dodge Chrome's WAL lock. Chrome 130+ prepends a 32-byte SHA256(host) integrity prefix to each `v10` value — strip it after removing PKCS7 padding.
- **Keep cookies domain-scoped, not flattened by name.** Setting them per `host_key` prevents per-subdomain tokens (e.g. Cloudflare `__cf_bm` on different subdomains) from clobbering each other and tripping intermittent 403s.

## Tailored references

- For `pi.dev`, read `references/pi-dev.md`.
- For Claude/Codex usage limits, read `references/ai-usage.md`.
- For recurring Bank Hapoalim transfers to `רומי` or `רינת`, read `references/bank-hapoalim.md`.
- For scraping `claude.ai/code` (Claude Code web) session transcripts, read `references/claude-code-web.md`.
- For GitHub repo changelogs, use `scripts/scrape_changelogs.py`.

For these tailored cases, lightly skim the core docs and then follow the dedicated reference.
