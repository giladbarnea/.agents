Yes.

High-level reusable process, based only on what I actually did across the 3 docs:

1. **Enumerate current state**
   - Read the `.md`
   - Extract all `![Image](...)` refs
   - List artifact files in sibling `_artifacts/`

2. **Build per-image inventory**
   - For each referenced image, collect:
     - path
     - reference count
     - byte size
     - dimensions
     - content hash
   - Group by hash to detect byte-identical duplicates

3. **Create visual review aids**
   - Generate contact sheets / montages of:
     - all artifact images
     - current referenced images only
   - This is what made repeated logo/stamp/signature patterns obvious quickly

4. **Classify what is obviously mechanical noise**
   - Repeated byte-identical branding logos
   - Tiny stamps / signatures / seals
   - Small institutional marks
   - Remove these from the keep set
   - Keep substantive maps, plans, tables, photos, scans

5. **Use document context for ambiguous cases**
   - Read surrounding markdown near each image ref
   - Match image purpose to nearby headings/text
   - This is how I distinguished:
     - substantive plan/table/map images
     - versus page furniture / decorative identity marks
   - This step needed judgment

6. **Decide final keep set**
   - For each doc, define the exact refs to keep
   - Everything else becomes removable noise

7. **Rewrite markdown**
   - Delete removed image refs
   - Delete their adjacent generated caption lines when present
   - Clean leftover `Logo` / `Other` text artifacts
   - Normalize spacing around removed blocks

8. **Prune artifacts**
   - Delete artifact files not in final keep set
   - End state: artifact dir contains only images still referenced by markdown

9. **Regenerate downstream script**
   - Rebuild `copy-...sh` image array directly from cleaned markdown refs
   - This keeps follow-up captioning/idempotent workflows aligned

10. **Validate**
   - Every remaining markdown image ref exists
   - No extra artifact files remain unreferenced
   - Script refs match cleaned markdown refs exactly

What was deterministic vs judgment-based:

- **Deterministic**
  - extract refs
  - inventory size/dim/hash/count
  - detect duplicates
  - generate contact sheets
  - remove non-keep refs/files once keep set is known
  - regenerate scripts
  - validate closure

- **Needed AI judgment**
  - deciding whether an image was substantive content or page noise
  - using nearby markdown context to interpret an image’s role
  - deciding whether a captioned image should still remain
  - spotting/removing stray textual remnants like `Logo` / `Other` when cleanup left them behind

Condensed mental model:

**Inventory → visually cluster → read local context → choose keep set → rewrite md → prune artifacts → regenerate script → validate.**
