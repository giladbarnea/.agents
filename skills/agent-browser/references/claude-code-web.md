# Scraping claude.ai/code (Claude Code web) sessions

Given a URL like `https://claude.ai/code/session_XXXX`, get the transcript from the **events API**, not the DOM.

- **The DOM is virtualized** — only rows near the viewport are mounted, so scrolling/`innerText` can never reach the whole conversation. Don't scrape it.
- **The data lives at** `GET /v1/sessions/session_XXXX/events?limit=500` (same host, logged-in cookies). `has_more`/`last_id` paginate via `&after=<last_id>` for >500 events.
- **A plain page `fetch` returns `not_found`** — the app adds auth headers cookies alone don't satisfy. So **capture the response off the wire**: navigate the open tab to the session URL and read the `/events` body via CDP `Network.responseReceived` → `Network.getResponseBody`.

## Parse

`body.data` is a list of events. Keep two types, sort by `created_at`:

- `type:"user"` → `message.content` is a **string**; strip `<system-reminder>…</system-reminder>`.
- `type:"assistant"` → `message.content` is a **list of blocks**; keep `type:"text"` blocks, drop `thinking` and `tool_use`.

Everything else (`system`, `env_manager_log`, `control_*`, `rate_limit_event`) is noise.

## Forks

Sessions fork: several `session_` ids can share the same opening message (abandoned retries). The sidebar's **topmost/latest** entry is usually the real thread, and it's **self-contained** — build from that one id alone, don't merge siblings by timestamp (you'll get duplicate openers). List candidates via `GET /v1/code/sessions`.

## Minimal capture (CDP)

```python
# connect to tab ws (ws://localhost:9222/devtools/page/<tabId>, suppress_origin=True)
send("Network.enable"); send("Page.enable")
send("Page.navigate", {"url": f"https://claude.ai/code/{sid}"})
# read frames until Network.responseReceived whose response.url contains f"/v1/sessions/{sid}/events"
rid = ...   # its requestId
body = json.loads(send_and_wait("Network.getResponseBody", {"requestId": rid})["body"])
turns = []
for e in body["data"]:
    if e["type"] == "user" and isinstance(e["message"]["content"], str):
        turns.append((e["created_at"], "user", re.sub(r"<system-reminder>.*?</system-reminder>\s*", "", e["message"]["content"], flags=re.S).strip()))
    elif e["type"] == "assistant" and isinstance(e["message"]["content"], list):
        txt = "\n\n".join(b["text"] for b in e["message"]["content"] if b.get("type") == "text" and b.get("text", "").strip())
        if txt: turns.append((e["created_at"], "assistant", txt))
turns.sort()
```
