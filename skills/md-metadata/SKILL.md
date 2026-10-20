---
name: "md-metadata"
description: "Metadata, frontmatter, refs and relationship best practices for Markdown docs. Load once when working with Markdown."
last_updated: 2026-10-20T09-22
---

# (How to) Write Markdown files that relate

## YAML Frontmatter

Every Markdown file should have a YAML frontmatter. The basic mandatory field is `last_updated: yyyy-mm-ddTHH-MM`.

Use free fields to explain the document's sources, limits, and relationships. Add only what changes how a reader should use the document. The examples below show selected fields, not a required schema.

### Record evidence and its limits

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

### State what changed and what survives

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

Keep valid YAML. Use `key: value`, not `key:: value`. Quote prose containing `: `. Use curly quotes to avoid escaping issues.

### <a title that says to be proportional with how heavyhanded and rich the frontmatter is with how truly the connections are strong... my point is not to force it>

The following examples are perfectly plausible:

<two yaml frontmatter examples, again that are different from each other, which read as the more casual little siblings of the two above. yes, with 2-3 more fields other than last_updated, but not nested, not multiline, etc.>

## Markdown body inline-metadata

Mark a section, paragraph or a line with named footnotes. 

<also fill in here please>
