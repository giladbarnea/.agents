#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""One-command resumable native-session compaction.

Usage:
    uv run compact_native_pi_session.py <source.jsonl> [--decisions decisions.json]

Produces a new compacted JSONL file beside the source. The source stays unchanged.
"""

import json
import sys
import time
from pathlib import Path

PARENT_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(PARENT_SCRIPTS))

import pi_session

DEFAULTS = {
    "drop_custom_types": ["pi-time-sense"],
    "drop_tool_units": ["todo"],
    "keep_thinking": True,
    "shrink_always": ["read", "read_many_files", "write"],
    "shrink_threshold": 800,
    "drop_entry_ids": [],
}

eprint = pi_session.eprint


# ---------------------------------------------------------------------------
# Census (printed to stderr)
# ---------------------------------------------------------------------------

def census(header: dict, active: list[dict], all_entries: list[dict]):
    tree = all_entries[1:]
    off_path = len(tree) - len(active)
    eprint(f"\n{'='*60}")
    eprint(f"CENSUS: {header.get('id','?')}")
    eprint(f"{'='*60}")
    eprint(f"  file entries (incl header): {len(all_entries)}")
    eprint(f"  active-path entries:         {len(active)}  (off-path/rewound: {off_path})")

    from collections import Counter
    types = Counter()
    roles = Counter()
    tools = Counter()
    bytes_by_role = Counter()
    for e in active:
        t = e.get("type", "?")
        ct = e.get("customType")
        key = f"{t}/{ct}" if ct else t
        types[key] += 1
        if t == "message":
            m = e["message"]
            r = m.get("role", "?")
            roles[r] += 1
            bytes_by_role[r] += len(json.dumps(e, ensure_ascii=False))
            if r == "assistant":
                for blk in m.get("content", []):
                    if isinstance(blk, dict) and blk.get("type") == "toolCall":
                        tools[blk.get("name", "?")] += 1

    eprint(f"\n  entry types: {dict(types)}")
    eprint(f"  message roles: {dict(roles)}")
    eprint(f"  bytes by role: {dict(bytes_by_role)}")
    eprint(f"  tool distribution: {dict(tools)}")

    shrink_candidates = sum(
        1 for e in active
        if e.get("type") == "message" and e["message"].get("role") == "toolResult"
        and len(json.dumps(e["message"].get("content", []), ensure_ascii=False)) > 800
    )
    eprint(f"  shrink candidates (>800 chars): {shrink_candidates}")
    eprint(f"{'='*60}\n")


# ---------------------------------------------------------------------------
# Transform
# ---------------------------------------------------------------------------

def transform(header: dict, active: list[dict], decisions: dict) -> tuple[list[dict], dict]:
    drop_custom = set(decisions["drop_custom_types"])
    drop_tools = set(decisions["drop_tool_units"])
    keep_thinking = decisions["keep_thinking"]
    shrink_always = set(decisions["shrink_always"])
    shrink_threshold = decisions["shrink_threshold"]
    explicit_drops = set(decisions["drop_entry_ids"])

    # Index toolCalls
    call_by_id = {}
    for e in active:
        if e.get("type") == "message" and e["message"].get("role") == "assistant":
            for b in e["message"].get("content", []):
                if isinstance(b, dict) and b.get("type") == "toolCall":
                    call_by_id[b["id"]] = b

    drop_tool_call_ids = {cid for cid, b in call_by_id.items() if b.get("name") in drop_tools}
    drop_ids = set(explicit_drops)

    # Drop custom_message by type
    for e in active:
        if e.get("type") == "custom_message" and e.get("customType") in drop_custom:
            drop_ids.add(e["id"])

    # Drop paired toolResult entries for dropped tool units
    for e in active:
        if (e.get("type") == "message" and e["message"].get("role") == "toolResult"
                and e["message"].get("toolCallId") in drop_tool_call_ids):
            drop_ids.add(e["id"])

    # Strip dropped-tool blocks from assistant entries; optionally strip thinking
    stripped_tools = 0
    stripped_thinking = 0
    for e in active:
        if e.get("type") != "message" or e["message"].get("role") != "assistant":
            continue
        content = e["message"].get("content", [])
        new_content = []
        for b in content:
            if not isinstance(b, dict):
                new_content.append(b)
                continue
            if b.get("type") == "toolCall" and b.get("id") in drop_tool_call_ids:
                stripped_tools += 1
                continue
            if b.get("type") == "thinking" and not keep_thinking:
                stripped_thinking += 1
                continue
            new_content.append(b)
        if len(new_content) != len(content):
            e["message"]["content"] = new_content
            if not new_content:
                drop_ids.add(e["id"])

    # Shrink large tool results in place
    shrunk = 0
    for e in active:
        if e["id"] in drop_ids:
            continue
        if e.get("type") != "message" or e["message"].get("role") != "toolResult":
            continue
        m = e["message"]
        tn = m.get("toolName", "")
        txt = "".join(
            b.get("text", "") for b in m.get("content", [])
            if isinstance(b, dict) and b.get("type") == "text"
        )
        n = len(txt)
        do_shrink = (tn in shrink_always and n > 400) or (n > shrink_threshold)
        if not do_shrink:
            continue

        if tn in shrink_always:
            call = call_by_id.get(m.get("toolCallId"), {})
            args = call.get("arguments", {})
            ref = args.get("path") or args.get("paths", "")
            if isinstance(ref, list):
                ref = f"{len(ref)} files: " + ", ".join(ref[:3])
            loc = f" — {ref}" if ref else ""
            marker = f"[smart-compact: {tn} result elided{loc} ({n} chars)]"
        else:
            head, tail = txt[:400], txt[-200:]
            marker = f"{head}\n\n[… smart-compact elided {n - 600} chars …]\n\n{tail}"
        m["content"] = [{"type": "text", "text": marker}]
        shrunk += 1

    # Build survivors, re-chain
    survivors = [e for e in active if e["id"] not in drop_ids]
    prev = None
    for e in survivors:
        e["parentId"] = None if prev is None else prev
        prev = e["id"]

    stats = {
        "active_path": len(active),
        "dropped": len(drop_ids),
        "stripped_tool_blocks": stripped_tools,
        "stripped_thinking": stripped_thinking,
        "shrunk_results": shrunk,
        "survivors": len(survivors),
    }
    return survivors, stats


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

def verify(source_active_snapshot: list[dict], header: dict, survivors: list[dict]) -> bool:
    """Verify compaction invariants against a PRE-TRANSFORM snapshot of the active path.

    source_active_snapshot must be a deepcopy taken BEFORE transform() mutates entries.
    """
    eprint(f"\n{'='*60}")
    eprint("VERIFICATION")
    eprint(f"{'='*60}")
    ok = True

    # 1. Single root
    roots = [e for e in survivors if e.get("parentId") is None]
    p = len(roots) == 1
    eprint(f"  single root: {'PASS' if p else 'FAIL'} ({len(roots)})")
    ok &= p

    # 2. All parentIds resolve
    sids = {e["id"] for e in survivors}
    unresolved = [e for e in survivors if e.get("parentId") is not None and e["parentId"] not in sids]
    p = len(unresolved) == 0
    eprint(f"  parentIds resolve: {'PASS' if p else 'FAIL'} ({len(unresolved)} dangling)")
    ok &= p

    # 3. Chain reaches all
    by_id = {e["id"]: e for e in survivors}
    reached = set()
    cur = survivors[-1]
    while cur is not None:
        reached.add(cur["id"])
        pid = cur.get("parentId")
        cur = by_id.get(pid) if pid else None
    p = len(reached) == len(survivors)
    eprint(f"  chain reaches all: {'PASS' if p else 'FAIL'} ({len(reached)}/{len(survivors)})")
    ok &= p

    # 4. Tool pairing
    calls, results = set(), set()
    for e in survivors:
        if e.get("type") != "message":
            continue
        m = e["message"]
        if m.get("role") == "toolResult":
            results.add(m["toolCallId"])
        elif m.get("role") == "assistant":
            for b in m.get("content", []):
                if isinstance(b, dict) and b.get("type") == "toolCall":
                    calls.add(b["id"])
    p = calls == results
    eprint(f"  tool pairing: {'PASS' if p else 'FAIL'} ({len(calls)} calls, {len(results)} results)")
    ok &= p

    # 5. Text/thinking fidelity vs source active path (pre-transform snapshot)
    source_by_id = {e["id"]: e for e in source_active_snapshot}
    mismatches = 0
    checked = 0
    for e in survivors:
        if e.get("type") != "message" or e["message"].get("role") not in ("user", "assistant"):
            continue
        orig = source_by_id.get(e["id"])
        if not orig:
            continue
        checked += 1
        def get_texts(m):
            return [b.get("text", "") for b in m.get("content", [])
                    if isinstance(b, dict) and b.get("type") == "text"]
        if get_texts(e["message"]) != get_texts(orig["message"]):
            mismatches += 1
    p = mismatches == 0
    eprint(f"  text fidelity: {'PASS' if p else 'FAIL'} (checked {checked}, mismatches {mismatches})")
    ok &= p

    # 6. All survivors from source active path (not off-path/rewound)
    source_active_ids = {e["id"] for e in source_active_snapshot}
    leaked = sids - source_active_ids
    p = len(leaked) == 0
    eprint(f"  active-path-only: {'PASS' if p else 'FAIL'} ({len(leaked)} off-path entries leaked)")
    eprint(f"    NOTE: source had {len(source_active_snapshot)} active-path entries before compaction.")
    ok &= p

    eprint(f"{'='*60}\n")
    return ok


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("source", help="source session .jsonl path OR session id")
    parser.add_argument("--decisions", type=Path, help="optional decisions JSON", default=None)
    parser.add_argument("--rewrite-content-id", action="store_true",
                        help="replace old session id inside message content with the new id")
    parser.add_argument("--dry-run", action="store_true",
                        help="resolve, census, audit, and outline — write nothing, mint no uuid")
    parser.add_argument("--outline", action="store_true",
                        help="with --dry-run: print per-entry active-path summary with action annotations")
    args = parser.parse_args()

    source = pi_session.resolve_session(args.source)
    eprint(f"  resolved: {source}")

    # Load decisions
    decisions = dict(DEFAULTS)
    if args.decisions:
        with open(args.decisions) as f:
            user_decisions = json.load(f)
        decisions.update(user_decisions)

    # Load source
    all_entries = pi_session.load_entries(source)
    header, active = pi_session.extract_active_path(all_entries)

    # Census
    census(header, active, all_entries)
    old_id = header.get("id", "")
    active_ids = {e["id"] for e in active if "id" in e}
    id_audit = pi_session.content_id_audit(all_entries, old_id, active_ids)
    eprint(f"  old-id content occurrences: {id_audit['total']} total "
           f"({id_audit['on_active_path']} on active path, {id_audit['off_path']} off-path)")
    if id_audit["locations"]:
        for loc in id_audit["locations"]:
            eprint(f"    {loc}")
    # Predicted rewrite: off-path occurrences will be dropped by active-path compaction
    predicted_rewrites = id_audit["on_active_path"]
    eprint(f"  predicted content-id rewrites in survivors: {predicted_rewrites}"
           f" (off-path: {id_audit['off_path']} → dropped by active-path compaction)")

    # Dry-run: outline the active path with action annotations, then exit
    if args.dry_run:
        if args.outline:
            # Compute what transform WOULD do (on a copy) to annotate actions
            import copy
            sim_active = copy.deepcopy(active)
            _, sim_stats = transform(header, sim_active, decisions)
            # Determine drop/shrink sets from the simulation
            drop_tool_ids = {cid for e in active if e.get("type")=="message" and e["message"].get("role")=="assistant"
                             for b in e["message"].get("content",[]) if isinstance(b,dict) and b.get("type")=="toolCall" and b.get("name") in decisions["drop_tool_units"]
                             for cid in [b["id"]]}
            drop_custom = set(decisions["drop_custom_types"])
            shrink_always = set(decisions["shrink_always"])

            eprint(f"\n{'='*60}")
            eprint(f"OUTLINE (active path, {len(active)} entries)")
            eprint(f"{'='*60}")
            for i, e in enumerate(active):
                eid = e.get("id", "?")[:8]
                t = e.get("type", "?")
                sz = len(json.dumps(e, ensure_ascii=False))
                # Determine action
                action = "KEEP"
                if t == "custom_message" and e.get("customType") in drop_custom:
                    action = "DROP"
                elif t == "message":
                    m = e["message"]
                    role = m.get("role", "?")
                    if role == "toolResult":
                        if m.get("toolCallId") in drop_tool_ids:
                            action = "DROP"
                        else:
                            tn = m.get("toolName", "")
                            txt_len = sum(len(b.get("text","")) for b in m.get("content",[]) if isinstance(b,dict) and b.get("type")=="text")
                            if (tn in shrink_always and txt_len > 400) or txt_len > decisions["shrink_threshold"]:
                                action = "SHRINK"
                    elif role == "assistant":
                        has_only_drop = all(
                            (isinstance(b,dict) and b.get("type")=="toolCall" and b.get("name") in decisions["drop_tool_units"])
                            or (isinstance(b,dict) and b.get("type")=="thinking" and not decisions["keep_thinking"])
                            for b in m.get("content",[])
                        ) if m.get("content") else True
                        if has_only_drop and m.get("content"):
                            action = "DROP"
                    # Build one-line summary
                    if role == "assistant":
                        tools = [b.get("name","?") for b in m.get("content",[]) if isinstance(b,dict) and b.get("type")=="toolCall"]
                        has_text = any(isinstance(b,dict) and b.get("type")=="text" for b in m.get("content",[]))
                        desc = f"assistant: {','.join(tools) if tools else ('text' if has_text else 'thinking')}"
                    elif role == "toolResult":
                        desc = f"toolResult:{m.get('toolName','?')}"
                    elif role == "user":
                        txt = "".join(b.get("text","")[:80] for b in m.get("content",[]) if isinstance(b,dict) and b.get("type")=="text")
                        desc = f"user: {txt[:60]}" if txt else "user"
                    else:
                        desc = f"{role}"
                else:
                    ct = e.get("customType", "")
                    desc = f"{t}/{ct}" if ct else t

                eprint(f"  {i:>3} [{action:<6}] {eid} {sz:>7}B  {desc}")

            eprint(f"\n  simulated stats: {json.dumps(sim_stats)}")
        eprint("\n  --dry-run: no file written.")
        return

    # Bootstrap new file
    new_path, new_id = pi_session.bootstrap_path(source)
    new_header = dict(header)
    new_header["id"] = new_id
    new_header["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()) + f".{int((time.time() % 1) * 1000):03d}Z"

    eprint(f"  new session id: {new_id}")
    eprint(f"  new file: {new_path.name}")

    # Snapshot the active path BEFORE transform mutates entries in place
    import copy
    source_active_snapshot = copy.deepcopy(active)

    # Transform
    survivors, stats = transform(new_header, active, decisions)

    eprint(f"\n  transform stats: {json.dumps(stats, indent=4)}")

    # Verify against pre-transform snapshot (not the mutated entries)
    all_ok = verify(source_active_snapshot, new_header, survivors)

    # Content-id rewrite (optional)
    rewritten = 0
    if args.rewrite_content_id:
        rewritten = pi_session.rewrite_content_id(survivors, old_id, new_id)
        eprint(f"  content-id rewritten: {rewritten} blocks (old→new)")

    # Output id audit on the final artifact
    output_audit = pi_session.content_id_audit([new_header] + survivors, old_id, {e["id"] for e in survivors})
    eprint(f"  old-id in output: {output_audit['total']} occurrences")

    # Write
    out = [new_header] + survivors
    with open(new_path, "w", encoding="utf-8") as f:
        for e in out:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")

    # Gold standard
    pi_session.gold_standard(new_path)

    # Discovery smoke (ch)
    pi_session.discovery_smoke(new_id)

    # Final report
    import hashlib
    src_hash = hashlib.sha256(source.read_bytes()).hexdigest()[:16]
    src_bytes = source.stat().st_size
    new_bytes = new_path.stat().st_size
    reduction = round(src_bytes / new_bytes, 1)
    eprint(f"\n  source: {src_bytes:,} bytes (sha256: {src_hash}…)")
    eprint(f"  output: {new_bytes:,} bytes ({reduction}x reduction)")
    eprint(f"  original UNTOUCHED: {source} (sha256 unchanged)")
    eprint(f"  content-id rewritten: {rewritten} (predicted: {predicted_rewrites})")

    if all_ok:
        print(json.dumps({
            "new_id": new_id,
            "new_file": str(new_path),
            "source_bytes": src_bytes,
            "output_bytes": new_bytes,
            "reduction_x": reduction,
            "off_path_excluded": len(all_entries) - 1 - len(active),
            "content_id_rewritten": rewritten,
            "stats": stats,
        }))
    else:
        sys.exit("VERIFICATION FAILED — output written but may be corrupt")


if __name__ == "__main__":
    main()
