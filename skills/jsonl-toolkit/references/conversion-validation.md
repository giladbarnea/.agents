# Conversion runtime validation

Verified on 2026-10-01 with Pi 0.99.1–0.99.2 and Codex 0.159.3. Models remained in compatible OpenAI families. See [runtime requirements and limits](../SKILL.md#converted-runtime).

## Proven behavior

| Check | Evidence |
|---|---|
| Native Codex team restart | Actual Pi-origin converter output resumed its existing children. A second process routed worker → sibling → parent. The user prompt used original names, not destination UUID paths. No replacement agents or toolkit database writes occurred. |
| Pi team restart | Actual converted sessions and generated dormant manifests resumed through real Pi processes and `pi-simple-team` IPC. Parent/child and sibling messages survived shutdown and restart with unchanged destination IDs. A local deterministic model isolated runtime behavior. |
| Restored encrypted child | A real OpenAI child resumed through the generated Pi team, read its original encrypted task, and sent the retrieved sentence to its parent. The outgoing request contained the original ciphertext, not the plaintext answer. |
| Private user-agent attachment | `/agent-attach` reopened the converted child, restored its `read`-only tool choice and explicit extensions, and did not deliver its private result to main. |
| Opaque delivery and argument replay | Native Codex and production Pi replay retrieved the same task sentence. A no-item control returned `NONE`. Fresh read/write/edit/Bash operations remained usable. |
| Replay-only schemas | Only required coordination schemas were declared. The execution allowlist contained the original Pi tools, not the historical coordination tools. Explicit historical-tool requests could not execute those tools. |
| New Pi compaction | The native summarizer received the opaque items for its exact span. A fact available only in encrypted task content survived in the resulting summary. Without supplementation, it did not. Split summaries received separate spans and complete call/result pairs. |
| Encrypted checkpoint compaction | A genuine checkpoint reached the actual summary request unchanged and exactly once. Compaction and continuation succeeded. This is request-preservation evidence, not a checkpoint-specific fact-retrieval experiment. |
| Failure handling | A removed replay marker aborted a real Pi run before any provider request. Incompatible families reject replay. There is no plaintext fallback. |

The source conversation files used by these checks stayed unchanged. Live gates used isolated runtime homes, and temporary credentials were removed. Private payloads and generated probe transcripts are not part of the repository.

## Repeat the local checks

From the toolkit directory:

```bash
for suite in tests/test_*.py smart-compact/tests/test_smart_compact.py; do
  uv run --script "$suite" || exit 1
done
uv run -p python3 -m doctest scripts/codex_to_pi.py scripts/pi_runtime.py
node --check scripts/pi-to-codex-context.mjs
```

These tests need the installed Pi/Codex tools and Bun. The default tests do not call a paid model service.

For `pi-simple-team`, run `bun test` with all inherited `PI_SIMPLE_TEAM_*` environment variables removed. This prevents test callbacks from reaching the team running the test.

## Repeat a live preservation check

Use isolated `CODEX_HOME` and `PI_CODING_AGENT_DIR` directories. Convert copies with fresh identities. Keep the original files and runtimes unchanged.

For encrypted retrieval, use a real delivery or call whose answer appears nowhere else in the request. Compare native Codex, converted Pi, and a no-item control. Capture final outgoing payloads without authorization headers. Check both retrieval and exact ciphertext preservation, then perform another turn with fresh core tools.

For runtime restoration, resume a converted parent and child, exchange a new message, stop both processes, and repeat after restart. Verify the same destination IDs and no substitute spawn. Test sibling routing separately. Keep local-model IPC checks distinct from real OpenAI replay checks.

For compaction, compact before revealing the hidden fact in visible conversation. Confirm its opaque item reaches the summary request, then retrieve the fact after compaction without replaying the old item. A successful request alone is not a retrieval result.
