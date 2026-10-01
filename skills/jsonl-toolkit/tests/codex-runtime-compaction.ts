import { readFileSync } from "node:fs";
import { buildSessionProjection } from "/opt/homebrew/lib/node_modules/@earendil-works/pi-coding-agent/dist/core/session-manager.js";
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
extension({ on: (name, handler) => handlers.set(name, handler), events: { emit: () => {} } });
const context = { model, cwd: "/tmp", thinkingLevel: "low", sessionManager: { buildSessionProjection: () => projection, getBranch: () => entries.slice(1) }, abort: () => { aborted = true; }, ui: { notify: message => console.error(message) },
  modelRegistry: { streamSimple: (requestModel, providerContext, options) => ({ result: async () => {
    const payload = { model: requestModel.id, input: convertResponsesMessages(requestModel, providerContext, new Set(["openai-codex"])) };
    const rewritten = await options.onPayload(payload, requestModel);
    captured.push(rewritten);
    return { role: "assistant", content: [{ type: "text", text: `SUMMARY-${captured.length}` }], stopReason: "stop", usage: { input: 1, output: 1, cacheRead: 0, cacheWrite: 0, totalTokens: 2, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } } };
  } }) },
};
const before = await handlers.get("session_before_compact")?.({ preparation, signal: new AbortController().signal }, context);
if (before?.cancel) throw new Error("Compaction was cancelled");
const result = before.compaction;
await handlers.get("session_compact")?.({}, context);
console.log(JSON.stringify({ captured, result, aborted }));
