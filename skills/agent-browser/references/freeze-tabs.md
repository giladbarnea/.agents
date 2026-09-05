# Freeze Chrome tabs

1. Find the oldest Chrome process with `pgrep -falo 'Google Chrome'`.
2. Measure its tabs through the CDP port, usually `9222`.
3. Stop browser-control clients that auto-attach to all page targets.
4. Enable internal pages through `chrome://chrome-urls`.
5. Use `chrome://discards` to discard safe hidden tabs.
6. Freeze tabs with edited content instead of discarding them.
7. Close `chrome://discards` because its live table can use significant CPU.
8. Disable internal pages again.

## Map resources to tabs

1. Get page targets from `http://127.0.0.1:9222/json/list`.
2. Call `Performance.getMetrics` on each page twice, a few seconds apart.
3. Calculate tab CPU as `ΔProcessTime / sample_seconds × 100`.
4. Read `JSHeapUsedSize` for the tab JavaScript heap.
5. Call browser-level `SystemInfo.getProcessInfo` for renderer IDs and cumulative CPU time.
6. Match each tab `ProcessTime` to the nearest renderer `cpuTime`.
7. Read that renderer PID from `ps` to get its RSS memory.
8. Call `Performance.disable` and detach after the sample.

## `chrome-devtools-axi` quirk

Skip `chrome-devtools-axi` for this task and use direct CDP. Its MCP child auto-attaches to every tab, which blocks discarding. `chrome-devtools-axi stop` can leave the `chrome-devtools-mcp` child running, so stop that child separately.
