---
name: "md-metadata"
description: "Metadata, frontmatter, refs and relationship best practices for Markdown docs. Load once when working with Markdown."
---

# (How to) Write Markdown files that relate

## YAML Frontmatter

Every Markdown file should have a YAML frontmatter. The basic mandatory field is `last_updated: yyyy-mm-ddTHH-MM`. `SKILL.md` files are an exception because they answer their own protocol.

### Keep metadata proportional to the document

Add fields only for real sources, limits, relationships, project context, or timeline context that change how a reader should use the document.
A simple relationship needs only a path or short phrase. Use richer structures only when a shorter form would hide an important distinction. These examples illustrate choices, not a checklist.

A short research note:

```yaml
last_updated: 2026-10-20T09-30
description: Notes on the August sales report
based_on: reports/august-sales.csv
confidence: preliminary; refund totals not checked
```

A revised plan:

```yaml
last_updated: 2026-10-20T09-30
description: Plan for the next client visit
status: working draft for discussion with Joe
supersedes: visit-plan-v1.md
```

### Richer examples for cases that need them

#### Record evidence and its limits

Sources explain where claims came from. Confidence explains how much to trust them. Keep these separate so detailed provenance does not imply verification.

Adapted from a marketing-attribution research summary:

```yaml
based_on:
  - research/recommendations.md
  - research/per-run-reviews/
provenance: >-
  Six independent AI analyst runs over a mid-June database copy,
  followed by one AI reviewer. No human checked the numbers.
confidence: >-
  Low for the numbers, medium for the data traps.
  Treat these as leads to verify, not findings.
```

#### State what changed and what survives

A replacement can invalidate only part of an older document. Name those parts explicitly, and point the older document forward with `superseded_by` or `superseded_in_part_by`.

Adapted from a design revision:

```yaml
revision: 2
status: substantial work done, not signed off yet
based_on:
  - ../evidence/design-notes.md
supersedes:
  - document: design.rev-1.md
    scope: the two classification axes; see sections 3.3 and 3.4 for their replacements
  - document: scenario-draft.md
    scope: steps 1 and 2 and the memory architecture; steps 3 to 7 still apply
```

Keep valid YAML.

## Markdown body inline-metadata

Use named footnotes for metadata that applies to one section, paragraph, or line rather than the whole file.
Avoid repeating the content of the referenced files. Note how in the example below I have only enumerated the relevant superseded subjects. This avoid drift.

```markdown
## Model and inputs

- One work unit equals one full weekly allowance.
- A saved reset also refills the allowance to 100%. It does not change scheduled reset dates.[^superseded-reset]
- Each saved reset has an independent identity, acquisition timestamp, and expiration timestamp.

// ... at the bottom of the file: 

[^superseded-reset]: [Codex reset forecast](codex-reset-forecast.md): newer notions about live reset and maximum work.
```
