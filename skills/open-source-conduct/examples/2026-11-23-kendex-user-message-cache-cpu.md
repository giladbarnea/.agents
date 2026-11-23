# New Kendex issue: past 256 user messages, every frame rebuilds every message

A new issue for vanillagreencom/kendex (pi-tool-renderer), November 23, 2026.

## Before

````markdown
**Title:** pi-tool-renderer: past 256 user messages, every frame rebuilds the Markdown of every user message

Thanks for pi-tool-renderer. I use it daily.

**The problem:** With `compactUserMessages` on (the default), a session with more than 256 user messages renders noticeably slower on every frame. `[Gilad]` I noticed this in my own sessions with 444–525 user messages, where a profile showed 0.3–0.4 s per frame, against 0.001–0.012 s in sessions under 256. Pi requests a frame about every 80 ms while the agent works, so the TUI stays behind for the whole turn.

**The cause, as I read it:** `userMessageLayouts` holds at most 256 entries and replaces the whole `WeakMap` when the 257th arrives ([`messages.ts:191-197`](https://github.com/vanillagreencom/kendex/blob/0a2d90cab69b8bfac4402a0aaf86ecbedf843916/pi-extensions/pi-tool-renderer/extensions/tool-renderer/messages.ts#L191-L197)). Pi renders the whole transcript in order on each frame, so with N > 256 each message's layout is dropped before its next frame. Every user message then gets a new `Markdown` (`messages.ts:173-180`) and is parsed again, every frame. Separately, a message is never kept when its text, or its rendered lines including ANSI codes, exceed 64 KB (`messages.ts:155`, `:188`, `:199`). With `compactUserMessages: false` this path is not used and the cost goes away.

**Measured:** Pi 1.6.0, pi-tool-renderer 2.0.13 (`main` at `0a2d90ca`, same `messages.ts` as my install), Node 26, M2 Pro. Real `UserMessageComponent` plus an assistant reply per message, in Pi's fullscreen renderer at 120×40, 60 frames, three runs each:

| User messages | Fastest frame (ms) | Median frame (ms) | Markdown time per frame (ms) | New `Markdown` per frame |
|---|---|---|---|---|
| 200 | 19.4 | 42.7 | 0.05 | 0 |
| 256 | 24.8 | 35.0 | 0.06 | 0 |
| 257 | 48.1 | 55.3 | 24.9 | 257 |
| 400 | 77.5 | 214.5 | 99.6 | 400 |
| 500 | 95.7 | 134.7 | 66.2 | 500 |
| 500, `compactUserMessages: false` | 0.30 | 0.43 | 0.03 | 0 |

The machine was under load, so frame times are noisy. The last two columns are not: up to 256 nothing is rebuilt, and from 257 every message is. The remaining ~20–40 ms at 200–256 is mostly `truncateToWidth` in `renderUserMessageBorder`, which also runs every frame.

The script and raw numbers are in [gist link `[Gilad]`].

**A possible direction, only if it fits:** keeping the layout on the component itself (for example under a symbol) would free it with the component and need no count bound. If another direction fits better, I'm happy to align, please let me know.

Used Opus 5.5 in this work. `[Gilad]` adjust the model line if needed.
````

## After

````markdown
**Title:** pi-tool-renderer: past 256 user messages, CPU chokes because every frame rebuilds the Markdown of every user message

Thanks for pi-tool-renderer. I use it daily.

**The problem:** With `compactUserMessages` on (the default), a session with more than 256 user messages takes enough CPU on every frame to make Pi unusable.

I noticed this in my own sessions with 444–525 user messages, where Pi stayed at about 100% of one CPU core in bursts while the agent worked. This froze the TUI. No reaction from keyboard or mouse actions. I killed the Pi processes and resumed them without the extension.

A profile showed 0.3–0.4 s per frame, against 0.001–0.012 s in sessions under 256. Pi requests a frame about every 80 ms while the agent works, so the TUI stays behind for the whole turn.

**The cause, as I read it:**

1. `userMessageLayouts` holds at most 256 entries and replaces the whole `WeakMap` when the 257th arrives ([`messages.ts:191-197`](https://github.com/vanillagreencom/kendex/blob/0a2d90cab69b8bfac4402a0aaf86ecbedf843916/pi-extensions/pi-tool-renderer/extensions/tool-renderer/messages.ts#L191-L197)).
2. Pi renders the whole transcript in order on each frame. With N > 256, each message's layout is dropped before its next frame.
3. Every user message then gets a new `Markdown` (`messages.ts:173-180`) and is parsed again, every frame.

Separately, a message is never kept when its text, or its rendered lines including ANSI codes, exceed 64 KB (`messages.ts:155`, `:188`, `:199`).

With `compactUserMessages: false` this path is not used and the cost goes away.

**Measurements:** Pi 1.6.0, pi-tool-renderer 2.0.13 (`main` at `0a2d90ca`, same `messages.ts` as my install), Node 26, M2 Pro.

Real `UserMessageComponent` plus an assistant reply per message, in Pi's fullscreen renderer at 120×40, 60 frames, three runs each:

| User messages | CPU per frame (median, ms) | Fastest frame (ms) | `Markdown` rebuilt per frame | `Markdown` time per frame (ms) |
|---|---|---|---|---|
| 200 | 42.7 | 19.4 | 0 | 0.05 |
| 256 | 35.0 | 24.8 | 0 | 0.06 |
| 257 | 55.3 | 48.1 | 257 | 24.9 |
| 400 | 214.5 | 77.5 | 400 | 99.6 |
| 500 | 134.7 | 95.7 | 500 | 66.2 |
| 500, `compactUserMessages: false` | 0.43 | 0.30 | 0 | 0.03 |

The cost is a step at 257, then it grows with the message count.

- Up to 256, nothing is rebuilt and the frame time stays flat.
- At 257, every user message is rebuilt on every frame.
- Past that, the rebuilt count equals the message count, so the `Markdown` work grows about linearly with it.

The machine was under load, so frame times are noisy, but the rebuild counts are exact. The fastest frames show the growth best: 48.1 ms at 257, 77.5 ms at 400, 95.7 ms at 500. The medians are noisier: 400 shows more `Markdown` time than 500 (99.6 ms against 66.2 ms), although 500 rebuilds more.

The remaining ~20–40 ms at 200–256 is mostly `truncateToWidth` in `renderUserMessageBorder`, which also runs every frame.

The script and raw numbers: https://gist.github.com/giladbarnea/dcdcb6adac9c0f6ca70d7e1694131f5e

**I'm suggesting to drop the count bound.** A `WeakMap` entry is already freed with its message component, so the map does not need a reset. Before (`messages.ts:191-197`):

```ts
if (userMessageLayoutCount >= 256) {
	userMessageLayouts = new WeakMap();
	userMessageLayoutCount = 0;
}
```

After:

```ts
// No count bound: each entry is freed with its message component.
userMessageLayouts.set(component, layout);
```

The trade-off is memory, and it is small. The map then holds a layout for every live user-message component, and frees it with that component. I measured about 4 KB per cached layout, with user messages of 200–2,000 characters. That is about 1 MB more than today at 500 user messages, and about 3.4 MB more at 1,000, in a test heap of about 60 MB. The 64 KB per-message bound stays, so no single huge message is cached.

The framed card from `renderUserMessageBorder` can also be kept on the same layout until its lines or the width change. A PR with this change follows. If another direction fits better, I'm happy to align, please let me know.
````
