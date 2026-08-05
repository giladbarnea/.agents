# Handoff: migrate `smart-compact` into `jsonl-toolkit`

## Task overview

The user wanted to rename the former `smart-compact` skill to `jsonl-toolkit`.

The parent skill must support large JSONL and AI-session work without compaction assumptions. Smart-compaction must live under `jsonl-toolkit/smart-compact/` and reuse parent modules.

The user specified these constraints:

- Read and classify every original file before moving it.
- Move compaction-agnostic tools to the parent.
- Split easy mixed files into parent and smart-compaction parts.
- Leave `scripts/transfer_to_pi_session.py` at the parent level until its reusable vectors are understood.
- Do not preserve backward compatibility.
- Retire the unsafe legacy `compact_jsonl.py` rather than keep it active.

## Current state

The migration is complete under:

```text
/Users/giladbarnea/.agents/skills/jsonl-toolkit/
```

The parent now contains:

- `SKILL.md`
- `references/pi-session-jsonl.md`
- `scripts/analyze_transcript_json.py`
- `scripts/filestats.sh`
- `scripts/pi_session.py`
- `scripts/pi-goldload.mjs`
- `scripts/render_transcript_review.py`
- `scripts/rgjsonl.sh`
- `scripts/stats_toolkit.py`
- `scripts/transcript_common.py`
- `scripts/transfer_to_pi_session.py`
- `tests/test_jsonl_toolkit.py`
- Provider fixtures under `tests/fixtures/`

Smart-compaction now contains:

- `smart-compact/SKILL.md`
- `smart-compact/references/agent-feedback-wanted.md`
- `smart-compact/references/native-pi-session.md`
- `smart-compact/scripts/analyze_compaction_candidates.py`
- `smart-compact/scripts/apply_compaction_plan.py`
- `smart-compact/scripts/compact_native_pi_session.py`
- `smart-compact/scripts/compile_annotations.py`
- `smart-compact/scripts/generate_compaction_plan.py`
- `smart-compact/scripts/prune_transcript.py`
- `smart-compact/tests/test_smart_compact.py`

The old `skills/smart-compact/` directory is empty. It remains only because the original session used it as its current directory.

Archived material lives at:

```text
/Users/giladbarnea/.agents/archive/smart-compact/
```

It contains:

- `compact_jsonl.py`
- `emerging-needs.md`

The user committed most migration work as commit:

```text
212a6bb Build JSONL/session toolkit and provenance-safe smart compaction workflows
```

Current relevant dirty state:

```text
 M skills/jsonl-toolkit/smart-compact/scripts/analyze_compaction_candidates.py
 M skills/jsonl-toolkit/smart-compact/tests/test_smart_compact.py
?? archive/
```

`skills/cautious-refactor/SKILL.md` is also modified, but that change is unrelated. Do not touch it.

## Verification completed

All checks passed after the migration:

- Parent suite: 5 tests passed.
- Smart-compaction suite: 37 tests passed.
- Python compilation passed.
- The generic analyzer ran against `tests/fixtures/claude.json`.
- The compaction analyzer ran against the same fixture.
- The transcript renderer produced Markdown.
- The native compactor completed a synthetic `--dry-run --outline` smoke test.
- Every relative Markdown link resolved.

The intentionally malformed `tests/fixtures/pi.json` makes the analyzer fail on a `Read` path with integer value `42`. This is expected fail-loud behavior, not a migration regression.

## Important discoveries

### The parent handles two formats

Native session tools consume JSONL. Transcript analyzers and renderers consume `ch -f json` top-level JSON arrays.

Keep this distinction explicit in documentation and CLI contracts.

### `pi_session.py` now owns the first generic native-session extraction

`compact_native_pi_session.py` now imports these parent operations from `pi_session.py`:

- Session resolution
- JSONL loading
- Active-path extraction
- Session-ID audits and rewriting
- New session path generation
- Pi loader and `ch` discovery checks

### `transfer_to_pi_session.py` still contains mixed parent and child logic

There is no substantial vector that can safely become a one-line import today. Its richer raw-line and provenance requirements exceed current parent APIs.

The useful vectors divide as follows.

#### Move into `pi_session.py`

These belong to the canonical native Pi owner:

- `SessionLine`
- `NativeToolCall`
- `NativeToolResult`
- `NativeToolOccurrence`
- `parse_session`
- `message_data`
- `native_tools`
- `split_tool_occurrence_keys`
- `is_default_export_entry`
- `native_result_text`
- `native_text`
- `thinking_blocks`
- `render_rechained`
- `validate_result`
- `next_backup_path`
- `atomic_write`

`SessionLine` should become the canonical representation because it preserves raw lines and tracks changed entries.

`pi_session.load_entries()` and `extract_active_path()` can then become wrappers or use the richer model directly.

#### Move into `transcript_common.py`

These belong to the normalized transcript vocabulary:

- `normalize`
- `output_text`
- `canonical_tool_name`
- `names_match`
- `source_prose`
- The richer native-provenance parsing from `parse_file_reference`

A parent `FileReference` model should carry:

- Operation
- Path
- Display tool ID
- Native tool-call ID
- Native content index

The existing `file_reference()` and `reference_path()` functions can become projections from that model.

#### Unique reusable vector

The exact bridge from a `ch` export back to native Pi occurrences remains unique:

- `validate_source_tail`
- `map_source_tools`
- `verify_source_outputs`

This vector proves message mapping, exact tool occurrence mapping, result fidelity, and retry-safe reused IDs.

It spans `transcript_common.py` and `pi_session.py`. Moving it into either module would blur that module's ownership.

A possible canonical owner is a new parent module such as `pi_transcript_bridge.py`. The user explicitly wants to inspect this unique vector before any refactor starts.

### Smart-compaction-only transfer logic must stay in the child

Do not promote these parts to the parent:

- Watermark and tail-boundary models and functions
- `unmatched_tool_calls`
- `source_tool_events`
- `apply_text_changes`
- `apply_tool_changes`
- `verify_complete_reviewed_tail`
- `latest_resume_anchor`
- `new_watermark`
- `apply_native_plan`
- `main`

They implement compaction policy, plans, incremental passes, or mutations.

## Necessary next steps

1. Wait for the user to inspect or decide the unique export-to-native bridge vector.
2. Do not refactor `transfer_to_pi_session.py` before that decision.
3. When approved, first enrich `pi_session.py` with the raw-line session model and native occurrence pairing.
4. Adapt `compact_native_pi_session.py` to the same canonical model.
5. Then enrich `transcript_common.py` with the richer file-reference and tool-name primitives.
6. Reassess the remaining bridge before creating a new module.
7. Keep the parent and smart-compaction tests green after each vertical refactor step.

## Context to preserve

The user prefers minimal, declarative code and rejects compatibility shims. Fail loudly instead of adding fallbacks.

Use complete names rather than abbreviations. Avoid nested conditionals and speculative abstractions.

The baseline files read in full were every file from the former `skills/smart-compact/` tree, including all scripts, tests, fixtures, references, and historical notes.

The migration also loaded the `ai-to-ai`, `tdd`, `write-tests`, and `handoff` skills.
