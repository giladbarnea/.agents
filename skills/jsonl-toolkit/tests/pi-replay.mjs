import { readFileSync } from 'node:fs';
import { buildSessionContext } from '/opt/homebrew/lib/node_modules/@earendil-works/pi-coding-agent/dist/core/session-manager.js';
import { convertToLlm } from '/opt/homebrew/lib/node_modules/@earendil-works/pi-coding-agent/dist/core/messages.js';
import { openaiCodexProvider } from '/opt/homebrew/lib/node_modules/@earendil-works/pi-coding-agent/node_modules/@earendil-works/pi-ai/dist/providers/openai-codex.js';
import { convertResponsesMessages } from '/opt/homebrew/lib/node_modules/@earendil-works/pi-coding-agent/node_modules/@earendil-works/pi-ai/dist/api/openai-responses-shared.js';

const entries = readFileSync(process.argv[2], 'utf8').trim().split('\n').map(line => JSON.parse(line));
const context = buildSessionContext(entries);
const model = openaiCodexProvider().getModels().find(model => model.id === context.model.modelId);
if (!model) throw new Error(`Pi does not know ${context.model.modelId}`);
const items = convertResponsesMessages(model, { messages: convertToLlm(context.messages) }, new Set(['openai-codex']), { includeSystemPrompt: false });
console.log(JSON.stringify({ model: context.model.modelId, items }));
