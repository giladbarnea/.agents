---
description: Hub ownership model and current instruction and skill materialization behavior
last_updated: 2026-10-05 10:45
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
It sets provider-specific variables and overrides Jinja blocks such as `communication_style` and `shell_usage`.
The shared `shell_usage` block uses `zshi -c '...'`. Pi overrides it in `~/.pi/agent/AGENTS.md.j2` to use the `zsh` tool.
The existing hook renders propagate that override without changing the other consumers.

`common.sh` stores the downstream template paths in `TARGETS`.
The hub hooks call `render.py` for the local template and every downstream template.

## Shared communication rules come from the `soft-skills` plugin

The shared communication rules live in `~/.agents/plugins/soft-skills/skills/ai-to-leader/references/human.md`.
The base template inserts them with:

```jinja2
{{ skill_body("plugins/soft-skills/skills/ai-to-leader/references/human.md") | trim }}
```

`render.py` creates one Jinja loader for each rendered template.
The loader searches the rendered template's directory first, the hub directory second, and the filesystem root last.

For a hub render, the first search root finds the canonical plugin source.
For a consumer render, a matching consumer file can override it.
Otherwise, the hub search root finds the same canonical plugin source.

The base template therefore names the plugin source without knowing any consumer's plugin layout.
The `soft-skills` plugin owns the content, while the plugin materialization code owns each consumer-specific layout.

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

## Hooks render instructions and materialize skills

`pre-commit` first blocks staged plugin changes if the public repository has local edits, unpublished commits, or a pending release. It then renders instruction files, generates runtime skills, links shared skills, materializes local Pi plugin skills, and inspects broken links. It never writes to the public repository.

`pre-commit` also stages the local `AGENTS.md` and generated runtime `SKILL.md` files. `post-commit` publishes changed plugin commits. `post-merge` publishes plugin changes before it renders local instructions and skills, so a local render failure cannot skip publication. The submodule update in `post-merge` is commented out.

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

## Claude Code, Codex, and Pi consume the published plugin

`plugins/soft-skills` holds the personal source.
`plugins/.published-soft-skills` is a separate Git repository for the public distribution.
The hub no longer generates local Claude or Codex marketplaces, plugin installations, or cache entries.
Claude Code and Codex consume the published GitHub marketplace instead.

All three consumers retain the published `plugins/soft-skills` layout, including the root `roles.md` map and individual `skills` directories.
Claude Code uses `.claude-plugin` metadata.
Codex uses `.agents/plugins/marketplace.json` and `.codex-plugin/plugin.json`, whose `skills` field points to `./skills/`.
Pi uses the root `package.json`, whose `pi.skills` field points to `./plugins/soft-skills/skills`. The release workflow publishes it to npm as `soft-skills`.
Gemini receives no plugin materialization from these hooks.

### A source commit or merge publishes the public plugin

`post-commit` calls `publish-soft-skills.sh` when the commit changes `plugins/soft-skills`. `post-merge` also calls it when a merge changes that path. It reads the committed plugin tree, not unstaged files. It refuses a dirty public repository and builds in an isolated Git worktree.

`sync-published-soft-skills.sh` mirrors five named skills and the root `roles.md`, then asks Pi to anonymize `human.md`, `help.md`, `coordination/leading-leaders.md`, and `roles.md`. It rejects AI edits outside those files and rejects `Gilad` or `ADHD` in the published skill content. These checks catch known leaks, but cannot prove that anonymization removed every private detail.

The publisher then bumps both plugin manifests and `package.json` by one patch version, commits, pushes, tags, and waits for the GitHub release workflow. That workflow publishes to npm before it creates the GitHub release, so a release implies an npm version. `.plugin-source-checksum` identifies the current published source. The publisher skips only when that source matches the current public commit and its release succeeded. A return to earlier content makes a new release.

A failed publication cannot undo the source commit or merge. The publisher records its source commit under `.git/soft-skills-publication-pending`; `pre-commit` blocks another plugin commit until that release succeeds. Run `.githooks/publish-soft-skills.sh --retry` after fixing the cause. If validation rejects the source, run `--cancel-pending` before committing a correction; cancellation works only while the current public commit has a successful release. A partial push resumes the same version, and retry reruns a completed GitHub workflow when the release is missing. The skill and root-file whitelists remain hardcoded in `sync-published-soft-skills.sh`.

## Local Pi skills are symlinks to personal content

`theory-of-mind` is a standalone skill. Dependent skills load it by name, not through reference copies.

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

Instruction rendering remains separate from these distribution layouts.
It reads canonical plugin content through the hub loader instead of reconstructing consumer-specific paths.

## Link handling can cross ownership boundaries

`ensure_symlink` keeps a destination that already points to the expected hub skill.
It refuses to replace a concrete destination, warns, and continues the remaining materialization work.
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

An instruction-rendering, runtime-generation, structure-validation, or symlink-creation failure stops the hook before broken-link cleanup.
A concrete destination refusal does not stop the hook.
Cleanup's result does not control the final hook exit status.
A dirty or pending public repository blocks a staged plugin change before rendering. A publication failure after a commit or merge reports a pending release but cannot undo the Git operation.

---

## Relative imports now prefer consumer content

<pseudocode>
Render each consumer template with the consumer directory before the hub directory in Jinja’s lookup roots.

For every relative skill import, let Jinja select the first matching file.

Load the selected file through the same active Jinja loader. Remove leading frontmatter when present. Preserve the content unchanged when frontmatter is absent.
</pseudocode>

The ordered lookup and non-destructive skill materialization are active:

<pseudocode>
For skill discovery, create a hub link only when the consumer destination is empty. Keep an existing correct hub link. Preserve every other existing destination as consumer-owned.

Keep overload knowledge out of the ownership manifest. The manifest supplies source-to-destination mappings. Ordered lookup and non-destructive materialization produce overload behavior generically.
</pseudocode>

```text
Consumer template
        │
        │ skill_body("plugins/soft-skills/skills/ai-to-leader/references/human.md")
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
