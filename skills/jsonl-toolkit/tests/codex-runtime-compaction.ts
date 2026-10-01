import { readFileSync } from "node:fs";
import { buildSessionProjection } from "/opt/homebrew/lib/node_modules/@earendil-works/pi-coding-agent/dist/core/session-manager.js";
import { compact } from "/opt/homebrew/lib/node_modules/@earendil-works/pi-coding-agent/dist/core/compaction/compaction.js";
import { openaiCodexProvider } from "/opt/homebrew/lib/node_modules/@earendil-works/pi-coding-agent/node_modules/@earendil-works/pi-ai/dist/providers/openai-codex.js";
import { convertResponsesMessages } from "/opt/homebrew/lib/node_modules/@earendil-works/pi-coding-agent/node_modules/@earendil-works/pi-ai/dist/api/openai-responses-shared.js";
import extension from "../scripts/codex-replay.ts";

const entries = readFileSync(process.argv[2], "utf8").trim().split("\n").map(line => JSON.parse(line));
const projection = buildSessionProjection(entries);
const prefix = projection.entries.findIndex(entry => entry.sourceEntry.codexReplay?.items.some(item => item.id === "amsg_two"));
const future = projection.entries.findIndex(entry => entry.sourceEntry.codexReplay?.items.some(item => item.id === "amsg_future"));
const preparation = {
  messagesToSummarize: projection.entries.slice(0, prefix).flatMap(entry => entry.messages),
  turnPrefixMessages: projection.entries.slice(prefix, future).flatMap(entry => entry.messages),
  isSplitTurn: true, firstKeptEntryId: projection.entries[future].sourceEntry.id,
  tokensBefore: 1000, settings: { reserveTokens: 1000, keepRecentTokens: 100 },
  fileOps: { read: new Set(), written: new Set(), edited: new Set() },
};
const model = openaiCodexProvider().getModels().find(model => model.id === "gpt-6-luna");
const handlers = new Map();
const captured = [];
let aborted = false;
extension({ on: (name, handler) => handlers.set(name, handler) });
const context = { model, sessionManager: { buildSessionProjection: () => projection, getBranch: () => entries.slice(1) }, abort: () => { aborted = true; }, ui: { notify: () => {} } };
const before = await handlers.get("session_before_compact")?.({ preparation, signal: new AbortController().signal }, context);
if (before?.cancel) throw new Error("Compaction was cancelled");
const result = await compact(preparation, model, "test", undefined, undefined, undefined, "low", async (requestModel, providerContext) => {
  const payload = { model: requestModel.id, input: convertResponsesMessages(requestModel, providerContext, new Set(["openai-codex"])) };
  const rewritten = await handlers.get("before_provider_request")?.({ payload }, context) ?? payload;
  captured.push(rewritten);
  return { result: async () => ({ role: "assistant", content: [{ type: "text", text: `SUMMARY-${captured.length}` }], stopReason: "stop", usage: { input: 1, output: 1, cacheRead: 0, cacheWrite: 0, totalTokens: 2, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } } }) };
});
await handlers.get("session_compact")?.({}, context);
console.log(JSON.stringify({ captured, result, aborted }));
