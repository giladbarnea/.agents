import { readFileSync } from "node:fs";
import { buildSessionProjection } from "/opt/homebrew/lib/node_modules/@earendil-works/pi-coding-agent/dist/core/session-manager.js";
import { convertToLlm } from "/opt/homebrew/lib/node_modules/@earendil-works/pi-coding-agent/dist/core/messages.js";
import { openaiCodexProvider } from "/opt/homebrew/lib/node_modules/@earendil-works/pi-coding-agent/node_modules/@earendil-works/pi-ai/dist/providers/openai-codex.js";
import { convertResponsesMessages } from "/opt/homebrew/lib/node_modules/@earendil-works/pi-coding-agent/node_modules/@earendil-works/pi-ai/dist/api/openai-responses-shared.js";
import extension from "../scripts/codex-replay.ts";

const entries = readFileSync(process.argv[2], "utf8").trim().split("\n").map(line => JSON.parse(line));
const projection = buildSessionProjection(entries);
const identifier = process.argv[3] ?? projection.model.modelId;
const model = openaiCodexProvider().getModels().find(model => model.id === identifier);
const handlers = new Map();
let aborted = false;
extension({ on: (name, handler) => handlers.set(name, handler) });
const context = { model, sessionManager: { buildSessionProjection: () => projection }, abort: () => { aborted = true; } };
try {
  const transformed = await handlers.get("context")?.({ messages: structuredClone(projection.messages) }, context);
  const messages = transformed?.messages ?? projection.messages;
  const payload = { model: identifier, input: convertResponsesMessages(model, { messages: convertToLlm(messages) }, new Set(["openai-codex"]), { includeSystemPrompt: false }) };
  const rewritten = await handlers.get("before_provider_request")?.({ payload }, context) ?? payload;
  console.log(JSON.stringify({ ...rewritten, aborted }));
} catch (error) {
  console.log(JSON.stringify({ aborted, error: String(error) }));
}
