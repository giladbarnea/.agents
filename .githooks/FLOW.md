```text
./.githooks/post-merge
│
├── Load sync rules from common.sh
│   ├── Instruction targets: Claude, Codex, Gemini, Pi
│   ├── Skill-provider directories for those four tools
│   └── Runtime-skill registry
│       └── simplify-code
│
├── Align the plugin checkout with ~/.agents
│   │
│   ├── Read the claude-plugins commit pinned by the parent repo
│   │
│   └── git submodule update --init --recursive
│       ├── Checkout absent?
│       │   └── Register it, fetch the pinned commit, and check it out
│       ├── Checkout at another commit?
│       │   └── Move it to the pinned commit
│       └── Already aligned?
│           └── No-op
│
│   Note: this follows ~/.agents' pinned commit.
│         It does not advance to the latest claude-plugins/main.
│
├── Render global agent instructions
│   │
│   ├── Shared base
│   │   └── ~/.agents/AGENTS.md.j2
│   │           └── ~/.agents/AGENTS.md
│   │
│   └── Provider templates inherit that shared base
│       ├── ~/.claude/CLAUDE.md.j2
│       │       └── ~/.claude/CLAUDE.md
│       ├── ~/.codex/AGENTS.md.j2
│       │       └── ~/.codex/AGENTS.md
│       ├── ~/.gemini/GEMINI.md.j2
│       │       └── ~/.gemini/GEMINI.md
│       └── ~/.pi/agent/AGENTS.md.j2
│               └── ~/.pi/agent/AGENTS.md
│
│       For each render:
│       ├── Output unchanged ──> no-op
│       └── Output changed
│           ├── Interactive terminal ──> offer diff and ask to render
│           └── No terminal ───────────> fail; never overwrite silently
│
├── Validate the runtime-skill registry
│   ├── Every registered directory must exist
│   ├── It must contain a create/create.py generator
│   └── A skill containing a generator but missing from the
│       registry is rejected
│
├── Traverse every source under ~/.agents/skills/
│   │
│   ├── Plugin-backed skills resolve into the shared checkout
│   │   ├── skills/in-html
│   │   │       └── plugins/claude-plugins/plugins/in-html
│   │   └── skills/instruct-another-ai
│   │           └── plugins/claude-plugins/plugins/instruct-another-ai
│   │
│   ├── Ordinary static skills
│   │   └── Require an existing SKILL.md; otherwise skip
│   │
│   └── simplify-code
│       └── Run create/create.py
│           ├── Ask GitHub for the latest relevant upstream commit
│           ├── Compare it with the commit recorded in SKILL.md
│           ├── Upstream file unchanged ──> keep existing SKILL.md
│           └── Upstream file changed
│               ├── Fetch the upstream skill
│               ├── Combine it with the local Anthropic version
│               └── Write a new SKILL.md
│
│   Every skill is then whole-directory symlinked into all four
│   provider skill roots.
│
└── Clean orphaned provider links
    ├── Scan Claude, Codex, Gemini, and Pi skill directories
    ├── Find symlinks whose ~/.agents source no longer exists
    ├── Interactive terminal ──> ask before removing each one
    └── No terminal ───────────> report it and leave it alone


Failure behavior
│
├── Submodule alignment fails ────────────> stop
├── Instruction rendering fails ─────────> stop
├── Runtime generation fails ────────────> stop
├── Invalid skill structure is found ─────> stop
└── Only after all succeed does orphan cleanup run
