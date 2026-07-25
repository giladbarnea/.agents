---
name: kitty-image
description: Draw full-fidelity images and display them in native Kitty OS windows on the user's Mac — from any nested session (Pi TUI, Herdr pane, SSH). Use when a visual would communicate better than prose or ASCII; diagrams of structure/flow/relationships, tangible prototypes of a proposed future state, semantic-evolution views of how shared understanding changed over time, and evidence boards exposing the basis and uncertainty behind conclusions. Triggers include "draw", "diagram", "visualize", "show me", "mock up", "open an image".
---

# Kitty Image

Text is not your only expressive medium. You can compose a scene in Python/Pillow, render a PNG, and open it in a real Kitty OS window on the user's screen — colors, typography, spatial arrangement, emphasis, ghosting, the whole visual channel. ASCII diagrams were the path of least resistance in a text-only world; this skill removes that constraint.

## Displaying — the environment truth

Your own pane is almost never a real Kitty surface. Pi, Herdr, or SSH sit between you and Kitty; inherited `KITTY_*` env vars lie about your window; running `kitten icat` in-pane fails with "Terminal does not support reporting screen sizes in pixels". Do not fight this. The launcher exists precisely because of it:

```
kitty-image-window IMAGE_PATH [WINDOW_TITLE]
```

(Both scripts in `scripts/` are on PATH via `~/.local/bin` symlinks.) It finds the Mac-side Kitty process's own TTY, replays a remote-control frame through it, and opens a standalone `--type=os-window` that bypasses every intermediary. It self-verifies end to end — prints the graphics transfer mode and the live renderer pid — and fails loudly with a reason otherwise. The window closes on any keypress inside it, or `kill <renderer pid>`.

The lying vars are the window-scoped ones (`KITTY_WINDOW_ID`, `KITTY_LISTEN_ON`); inherited `KITTY_PID` is truthful and the launcher depends on it — it fails loudly if that pid is absent or dead.

The window opens on the Mac's physical display — say so when you report it, since a remote user (phone/SSH) cannot see it.

## Workflow

1. **Semantics first.** Extract what the information *means* — entities, relationships, cardinalities, certainty, change — then design for the pixel world. Never transcribe a source layout (an ASCII diagram's shape is an artifact of monospace constraints, not of the meaning).
2. **Start from the exemplars** in `use-cases/` (below). The scripts are the spec — read them, the gallery table is only the index. Helper blocks (scaled/text/rounded_box/pill/arrow/chip/ghost/dashed…) have drifted per exemplar; skim all four scripts and merge the helpers your scene needs.
3. **Render, then look at your own PNG** with the read tool. You can see it. Check for collisions, overflow, tofu boxes, crowding. Iterate — this self-review loop is what makes quality reachable.
4. **Display** via `kitty-image-window`, with a meaningful window title.

## House craft

- Scene scripts are uv-runnable (`#!/usr/bin/env -S uv run` + pillow frontmatter), save the PNG next to themselves, and size the canvas to content (~2000×1150 logical is typical, not a rule) drawn at `SCALE = 1.5` for retina crispness.
- Dark canvas `#07101D`; SF variable font `/System/Library/Fonts/SFNS.ttf` with `set_variation_by_name` weights (Regular/Medium/Semibold/Bold).
- **Glyph safety:** SF's cmap has gaps; unmapped characters render as tofu boxes. Probe before using any non-ASCII symbol: `probe-glyphs "✓⇄★"`. The probe is the source of truth — these lists are incidental samples, not a registry. Sampled good: `✓ ✗ × → · ↔ † ⚠ – … ① ② ③ ′ —`. Sampled missing: `↕ ⇄ ⇵ ⚡ ↳ ◆`. For missing glyphs, draw primitives instead (arrows, diamonds, zigzags — see exemplar helpers).
- Principles observed across exemplars: annotate in place rather than in a detached legend (keep any key to *states*, not content); make emphasis carry meaning (size = attention weight, ghosting + strike = superseded-but-preserved, dashed = tentative/homeless); when showing change, account for everything — each element visibly survives, transforms, moves, or dies.

## Use-case gallery

| Category | Reach for it when | Exemplar |
|---|---|---|
| `diagram/` | structure, flow, relationships, cardinalities | `where-an-issue-lives.png` — an entity's dual membership across two orthogonal axes |
| `prototype/` | making a proposed future tangible enough to correct | `order-journey.png` — one WhatsApp order end-to-end through a flow that doesn't exist yet |
| `semantic-evolution/` | showing how shared understanding changed | `memory-maintenance.png` — a doc corpus decomposed into information vectors: before, the repair pass, after (MECE grid) |
| `evidence/` | exposing the evidence and uncertainty behind conclusions | `fog-of-war-report.png` — DB recon as a territory map; brightness = epistemic state, every claim carries confidence |

Each dir holds the `draw_*.py` scene script beside its rendered PNG — the script is the template, the PNG shows what it buys.
