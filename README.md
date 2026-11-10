# `org`

Organization rulebook. Skills live under `skills/<name>/SKILL.md`, and a push to `main` publishes them.

## Install

**Claude Code**

```text
/plugin marketplace add giladbarnea/org
/plugin install org@org-rulebook
```

**Codex**

```bash
codex plugin marketplace add giladbarnea/org
codex plugin add org@org-rulebook
```

**Pi**

```bash
pi install git:github.com/giladbarnea/org
```

## Releasing

There is no version field and no release step. Claude Code and Codex take the plugin version from the commit, and Pi tracks the branch, so users get each pushed commit on their next update.

## License

[MIT](LICENSE).
