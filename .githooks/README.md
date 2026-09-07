---
description: Hub ownership model and current instruction and skill materialization behavior
last_updated: 2026-09-07 10:38
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
│   ├── Y: render
│   └── Any other answer: skip rendering and continue
├── R: render immediately
└── Any other answer: fail without rendering

No interactive terminal
└── Fail without rendering
```

## Hooks render instructions before materializing skills and plugins

`post-merge` and `pre-commit` run this pipeline:

```text
Render the hub and downstream instruction files
→ Validate and generate runtime skills
→ Link bare hub skills into every consumer skill root
→ Materialize plugin skills in Pi with flat references
→ Inspect broken consumer skill links
→ Sync and anonymize changed interaction content in the published repository
```

`pre-commit` also stages the local `AGENTS.md` and generated runtime `SKILL.md` files.
Neither hub hook stages files in downstream repositories or the separate published repository.
The submodule update in `post-merge` is commented out.

Rendering does not require existing consumer links.
When a consumer-relative import is absent, the loader falls back to the canonical hub source.

## Setup only enables the hooks

`../setup.sh` only sets this repository's `core.hooksPath` to `.githooks`.
It does not run the hooks, render instructions, materialize skills, or sync the published repository.

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

Generation and linking happen in the same traversal, one skill at a time.
Static skills must contain `SKILL.md`.
Directories without a skill file or a generator are skipped.

Every participating skill directory is linked into:

```text
~/.claude/skills
~/.codex/skills
~/.gemini/skills
~/.pi/agent/skills
```

The whole directory is linked, so its references, scripts, and other files remain available.

## Claude Code and Codex consume the published plugin

`plugins/interaction` holds the personal source.
`plugins/.published-interaction` is a separate Git repository for the public distribution.
The hub no longer generates local Claude or Codex marketplaces, plugin installations, or cache entries.
Claude Code and Codex consume the published GitHub marketplace instead.

Both consumers retain the published `plugins/interaction` layout, including shared plugin-level `references` and individual `skills` directories.
Claude Code uses `.claude-plugin` metadata.
Codex uses `.agents/plugins/marketplace.json` and `.codex-plugin/plugin.json`, whose `skills` field points to `./skills/`.
Gemini receives no plugin materialization from these hooks.

### The hub syncs public content, but does not release it

`sync_plugins` calls `sync-published-interaction.sh`.
The script returns without changes if either source or published repository is absent, or the source checksum matches `.plugin-source-checksum`.
The checksum covers non-hidden Markdown files outside hidden directories in the personal plugin.

When the checksum differs, the script:

1. Mirrors five whitelisted skills with `rsync --delete`, excluding hidden files: `ai-to-leader`, `ai-to-delegated`, `handoff`, `peer-review`, and `theory-of-mind`.
2. Copies the whitelisted shared reference: `roles.md`.
3. Rewrites absolute personal shared-reference links in skill Markdown to `../../references/` links.
4. Launches Pi to anonymize five named files: `human.md`, `help.md`, `leading-leaders.md`, `hats/head-of-product.md`, and shared `roles.md`.
5. Writes the new source checksum and prints the review and release steps.

Set `AGENTS_SKIP_ANONYMIZATION=1` to skip the Pi invocation. The sync still writes the source checksum and leaves the copied personal content unchanged.

The skill and reference whitelists are hardcoded.
Adding or moving a shared reference or skill therefore requires updating this script, not just the source tree.
Shared-reference copying does not remove obsolete destination files.

The hub hook does not build, commit, or push the published repository.
Review the synced content there, run `./build-plugins.sh`, then commit and push, including `.plugin-source-checksum`.

## Local Pi skills and published Pi skills use different builds

Both Pi layouts place shared references inside individual skill directories, but they reach that layout differently.
`theory-of-mind` is a standalone skill in both Pi layouts and the published plugin. Dependent skills load it by name, not through reference copies.

### Local Pi uses symlinks to personal content

`render_skills` discovers non-empty `plugins/*/skills/*/SKILL.md` files and calls `link_pi_plugin_skill` for each skill.
The destination, `~/.pi/agent/skills/<skill>`, is a real directory, not a skill-directory symlink.

The materializer:

1. Replaces an existing destination symlink with a real directory.
2. Links non-hidden skill entries other than `references` directly to the personal source.
3. Rebuilds direct symlinks inside the destination's `references` directory.
4. Links the skill's own references, then plugin-level references, into that directory.

A reference name clash keeps the earlier entry and emits a warning.
Existing concrete reference entries also remain in place.
Every plugin skill receives the shared references, whether its Markdown uses them or not.
The materializer does not rewrite Markdown paths.

### Published Pi skills are generated copies

`plugins/.published-interaction/build-plugins.sh` discovers each published skill containing `SKILL.md` and copies it into a temporary build tree.
For skills containing `../../references/`, it copies the shared references into the skill and rewrites that substring to `references/` in Markdown.
It does not generally resolve or validate Markdown link targets.

The build replaces tracked `pi/skills` with the generated tree and creates the ignored `interaction-pi-skills.zip` with normalized archive timestamps.
It also copies the repository `LICENSE` into the Claude/Codex plugin and the Pi archive.
The published repository's own `.githooks/pre-commit` runs this build and stages `pi/skills` and the plugin license.

Unlike the hub sync whitelist, the Pi build discovers new skill directories automatically.
Pi users install the archive's skill directories into `~/.pi/agent/skills`.

Instruction rendering remains separate from these distribution layouts.
It reads canonical plugin content through the hub loader instead of reconstructing consumer-specific paths.

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

## Failures stop the remaining pipeline

An instruction-rendering, runtime-generation, structure-validation, or skill-linking failure stops the hook before broken-link cleanup.
Cleanup's result does not control the final hook exit status.
Published-sync failure stops the hook after cleanup.

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
