# Comment on an existing Pi issue: one non-caching extension component freezes long sessions

A comment on earendil-works/pi#9549, November 23, 2026.

## Before

````markdown
Thanks for Pi.

Numbers on 1.6.0 for the third point in @petrroll's list above, in case they help. In fullscreen, each working-indicator frame still calls `render()` on every transcript component, including the ones far above the viewport.

**Measured:** pi-tui 1.6.0 (`TuiAltScreen`, `ScrollView`, `Container`, `Text`, `Loader`, public exports only), Node 26, M2 Pro, 120×40. A transcript of N three-line `Text` entries, each wrapped to count its `render()` calls, and a `Loader` with default frames in the status row, for 5 s:

| Entries | Loader | Frames/s | Off-screen entries | `render()` calls/s, visible entry | `render()` calls/s, off-screen entry |
|---|---|---|---|---|---|
| 1,000 | off | 0 | 987 | 0.2 | 0.2 |
| 1,000 | on | 12.4 | 987 | 12.6 | 12.6 |
| 5,000 | on | 12.4 | 4,987 | 12.6 | 12.6 |

Each frame goes `Loader.updateDisplay` → `requestRender()` → `contentChanged = true` (`packages/tui/src/components/loader.ts:82-98`, `tui.ts:1152-1159`). `doRender` then drops the previous frame's output (`tui-alt-screen.ts:1702`), and `renderCached` calls `render()` for the whole scroll document (`layout.ts:84`, `:169`), which `Container` passes to every child (`tui.ts:398`).

**Why it shows up:** Pi's own components return their cached arrays, so stock Pi stays cheap here. The frame cost, though, is the sum of every transcript component's `render()`, so one extension component that does not cache ends up re-rendering the whole history 12 times a second. `[Gilad]` In my case it was a user-message renderer that stops caching past 256 messages: with 400–500 user messages a frame took 135–215 ms (median), longer than the 80 ms interval. I've reported that one to its maintainer as well `[link to the Kendex issue, Gilad]`.

The script and raw output are in [gist link `[Gilad]`].

Used Opus 5.5 in this work. `[Gilad]` adjust the model line if needed.
````

## After

````markdown
Thanks for Pi.

On 1.6.0 in fullscreen, one extension component that does not cache its `render()` output can keep a CPU core busy and freeze a long session.

Every frame of the "Working…" indicator, about 12 per second, calls `render()` on every component in the transcript, including those far above the viewport. Pi's own components return cached arrays, so stock Pi stays cheap here. But a frame's CPU cost is the sum of every component's `render()`, so one non-caching extension component re-renders the whole history on every frame.

In my case that was a user-message renderer that stops caching past 256 messages. With 400–500 user messages, a frame took 135–215 ms of CPU (median), longer than the 80 ms indicator interval. The session stopped responding, and a few such sessions made the whole machine barely usable. I've reported that one to its maintainer: <KENDEX ISSUE LINK>.

This is the per-frame full-document render that @albersg pointed to above for 1.2.0; it is unchanged in 1.6.0.

Measurements, in case they help: pi-tui 1.6.0 (`TuiAltScreen`, `ScrollView`, `Container`, `Text`, `Loader`, public exports only), Node 26, M2 Pro, 120×40.

A transcript of N three-line `Text` entries, each wrapped to count its `render()` calls, with a default `Loader` in the status row, for 5 s:

| Entries | Loader | Frames/s | Off-screen entries | `render()` calls/s, visible entry | `render()` calls/s, off-screen entry |
|---|---|---|---|---|---|
| 1,000 | off | 0 | 987 | 0.2 | 0.2 |
| 1,000 | on | 12.4 | 987 | 12.6 | 12.6 |
| 5,000 | on | 12.4 | 4,987 | 12.6 | 12.6 |

The script and raw output: https://gist.github.com/giladbarnea/8a3cf4c2285f83d384e5da1e97103a17
````
