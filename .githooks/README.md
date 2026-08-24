---
description: Hub ownership model and current instruction and skill materialization behavior
last_updated: 2026-08-03 15:34
---
# Hub materialization

`~/.agents` stores shared agent instructions and skills.
Its Git hooks render instruction files and link shared skills into four downstream consumers.

## Ownership boundary

| Relationship | Owner |
|---|---|
| Hub source → consumer input | `~/.agents` |
| Consumer input → consumer output | The consumer |
| Hub source → hub output | `~/.agents` |
| Consumer configuration → consumer behavior | The consumer |

The intended instruction flow is:

```text
~/.agents canonical consumer template
        ↓ hub materialization
~/.claude/CLAUDE.md.j2
        ↓ Claude-owned rendering
~/.claude/CLAUDE.md
```

The same boundary applies to Codex, Gemini, and Pi.

The hub owns the consumer templates because it distributes shared knowledge into those consumers.
Each consumer owns the rendering of its local template into its final instruction file.

The hub also owns skill links into consumer skill roots.
Each consumer decides which linked skills it loads and how it uses them.

Consumer hooks, settings, authentication, extensions, and extra skill sources stay downstream.

## Current instruction mismatch

The current implementation does not yet follow the instruction ownership boundary.

The consumer templates live downstream and import `~/.agents/AGENTS.md.j2` through an absolute path.
Meanwhile, `common.sh` hardcodes those template paths and renders their final instruction files.

This makes each consumer know the hub location and makes the hub own consumer rendering.

## The hub currently renders every final instruction file

The shared base template lives at `~/.agents/AGENTS.md.j2`.
It renders locally and also serves as the parent of four downstream templates.

```text
~/.agents/AGENTS.md.j2              → ~/.agents/AGENTS.md
~/.claude/CLAUDE.md.j2              → ~/.claude/CLAUDE.md
~/.codex/AGENTS.md.j2               → ~/.codex/AGENTS.md
~/.gemini/GEMINI.md.j2              → ~/.gemini/GEMINI.md
~/.pi/agent/AGENTS.md.j2            → ~/.pi/agent/AGENTS.md
```

Each downstream template extends the shared base through its absolute path.
It sets provider-specific variables and overrides Jinja blocks such as `communication_style`.

`common.sh` stores the downstream template paths in `TARGETS`.
The hub hooks call `render.py` for the local template and every downstream template.

## Shared communication rules come from the `interaction` plugin

The shared communication rules live in `~/.agents/plugins/interaction/skills/ai-to-leader/references/human.md`.
The base template inserts them with:

```jinja2
{{ skill_body("plugins/interaction/skills/ai-to-leader/references/human.md") | trim }}
```

`render.py` creates one Jinja loader for each rendered template.
The loader searches the rendered template's directory first, the hub directory second, and the filesystem root last.

For a hub render, the first search root finds the canonical plugin source.
For a consumer render, a matching consumer file can override it.
Otherwise, the hub search root finds the same canonical plugin source.

The base template therefore names the plugin source without knowing any consumer's plugin layout.
The `interaction` plugin owns the content, while the plugin materialization code owns each consumer-specific layout.

`skill_body` reads through the active Jinja loader.
It removes leading YAML frontmatter when present and preserves frontmatter-free Markdown unchanged.
The `trim` filter prevents the extracted body from adding boundary whitespace to the rendered document.

## Rendering is review-gated

`render.py` supports three modes:

```text
./render.py TEMPLATE             Write the rendered output beside the template
./render.py --dry-run TEMPLATE   Exit nonzero when the output would change
./render.py --stdout TEMPLATE    Print the render without writing
```

The output path is the template path with `.j2` removed.
Dry-run comparison ignores leading and trailing whitespace in both versions.

`render_one` first runs dry-run mode.
An unchanged output returns immediately.

When an output differs:

```text
Interactive terminal
├── Y: show the diff, then ask whether to render
├── R: render immediately
└── Any other answer: fail without rendering

No interactive terminal
└── Fail without rendering
```

## Hooks render instructions before materializing skills and plugins

`post-merge` runs this pipeline:

```text
Align the pinned claude-plugins submodule
→ Render the hub and downstream instruction files
→ Validate and generate runtime skills
→ Link bare hub skills into every consumer skill root
→ Link plugin skills into Pi's skill root
→ Inspect broken consumer skill links
→ Synchronize Claude and Codex plugins
```

`pre-commit` runs the same pipeline without submodule alignment.
It stages the local `AGENTS.md` and generated runtime `SKILL.md` files.
It cannot stage rendered files or skill links inside downstream repositories.

Rendering does not require existing consumer links.
When a consumer-relative import is absent, the loader falls back to the canonical hub source.

## Setup only enables the hooks

`../setup.sh` only sets this repository's `core.hooksPath` to `.githooks`.
It does not run the hooks, initialize the plugin submodule, render instructions, or create skill links.

## Every valid hub skill is linked into every consumer

`render_skills` traverses each directory under `~/.agents/skills`.
A static skill participates when it contains `SKILL.md`.

A runtime skill must be listed in `runtime-skills.sh`.
It must contain an executable `create/create.py`, which must produce `SKILL.md`.
The only registered runtime skill is currently `skills/simplify-code`.

A skill with a generator must appear in the registry.
The hook rejects unregistered generators.

The `simplify-code` generator:

1. Checks the latest relevant upstream GitHub commit.
2. Compares it with the commit recorded in `SKILL.md`.
3. Stops when the upstream file did not change.
4. Fetches the upstream skill when it changed.
5. Combines the upstream body with the local Anthropic version.
6. Writes the generated `SKILL.md`.

After generation, the hook traverses every directory under `~/.agents/skills`.
Static skills must contain `SKILL.md`.
Directories without a skill file or a registered generator are skipped.

<!-- Stale
Two hub skill paths resolve through the pinned `claude-plugins` submodule:

```text
skills/in-html              → plugins/claude-plugins/plugins/in-html
skills/instruct-another-ai  → plugins/claude-plugins/plugins/instruct-another-ai
```

/Stale -->

Every participating skill directory is linked into:

```text
~/.claude/skills
~/.codex/skills
~/.gemini/skills
~/.pi/agent/skills
```

The whole directory is linked, so its references, scripts, and other files remain available.

## Plugin skills use three consumer-specific layouts

`~/.agents/plugins` is the canonical source tree for virtual plugin packages.
Each plugin contains a `skills` directory, but consumers do not receive this source tree unchanged.

Claude sync generates a local Claude marketplace, a proper plugin, and its cache entry.
Codex sync generates the equivalent Codex marketplace, plugin, and cache entry.
Pi has no matching plugin package flow, so `render_skills` links each plugin skill directly into `~/.pi/agent/skills`.
Gemini receives no plugin materialization.

These layouts serve consumer discovery only.
Instruction rendering reads canonical plugin content through the hub loader instead of reconstructing consumer-specific paths.

## Link handling can cross ownership boundaries

`ensure_symlink` keeps a destination that already points to the expected hub skill.
It refuses to replace a concrete destination.
It replaces any different symlink, including one created by a downstream consumer.

Downstream consumer hooks also manage entries inside some consumer skill roots.
Two systems can therefore claim the same skill name.
The last system to replace the symlink becomes the effective owner.

`clean_orphaned_skill_links` scans every direct symlink in every consumer skill root.
It treats a link as broken when its target directory is missing.
It does not check whether the hub created that link.

An interactive run asks before removing each broken link.
A non-interactive run reports each link and leaves it unchanged.

## Failures stop before cleanup

The hook stops when submodule alignment, instruction rendering, runtime generation, structure validation, or skill linking fails.
Broken-link cleanup runs only after those steps succeed.
Its result does not control the final hook exit status.

---

## Relative imports now prefer consumer content

<pseudocode>
Render each consumer template with the consumer directory before the hub directory in Jinja’s lookup roots.

For every relative skill import, let Jinja select the first matching file.

Load the selected file through the same active Jinja loader. Remove leading frontmatter when present. Preserve the content unchanged when frontmatter is absent.
</pseudocode>

The ordered lookup is active.
Non-destructive skill materialization remains future work:

<pseudocode>
For skill discovery, create a hub link only when the consumer destination is empty. Keep an existing correct hub link. Preserve every other existing destination as consumer-owned.

Keep overload knowledge out of the ownership manifest. The manifest supplies source-to-destination mappings. Ordered lookup and non-destructive materialization produce overload behavior generically.
</pseudocode>

```text
Consumer template
        │
        │ skill_body("plugins/interaction/skills/ai-to-leader/references/human.md")
        ▼
Jinja lookup, first match wins
        │
        ├── 1. Consumer root
        │       │
        │       ├── Local skill exists ──────> use local overload
        │       │
        │       └── No local skill
        │
        ├── 2. Hub root
        │       │
        │       └── Canonical source exists ─> use shared default
        │
        └── No match ────────────────────────> fail clearly


Hub skill materializer
        │
        ├── Destination absent ──────────────> create shared link
        │
        ├── Correct shared link exists ──────> no change
        │
        └── Other destination exists ────────> preserve consumer ownership
```
