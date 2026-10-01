import { readFileSync } from 'node:fs';
import { isDeepStrictEqual } from 'node:util';
import { buildSessionContext } from '/opt/homebrew/lib/node_modules/@earendil-works/pi-coding-agent/dist/core/session-manager.js';
import { convertToLlm } from '/opt/homebrew/lib/node_modules/@earendil-works/pi-coding-agent/dist/core/messages.js';
import { convertResponsesMessages } from '/opt/homebrew/lib/node_modules/@earendil-works/pi-coding-agent/node_modules/@earendil-works/pi-ai/dist/api/openai-responses-shared.js';

const { entries, modelIds, reasoningFamilyPrefixes } = JSON.parse(readFileSync(0, 'utf8'));
function reasoningFamily(identifier) {
  const bareIdentifier = identifier.replace(/^openai-codex\//, '');
  return reasoningFamilyPrefixes.find(prefix => bareIdentifier.startsWith(prefix))?.slice(0, -1) ?? bareIdentifier;
}
const context = buildSessionContext(entries);
const warnedModels = new Set();
function codexModel(provider, identifier) {
  const bareIdentifier = identifier?.replace(/^openai-codex\//, '');
  if (provider === 'openai-codex' && modelIds.includes(bareIdentifier)) return bareIdentifier;
  const source = `${provider ?? 'unknown'}/${identifier ?? 'unknown'}`;
  if (!warnedModels.has(source)) {
    console.error(`Warning: unsupported source model ${source}; fallback is gpt-6-luna, only if reasoning can be preserved.`);
    warnedModels.add(source);
  }
  return 'gpt-6-luna';
}
const modelId = codexModel(context.model?.provider, context.model?.modelId);
const originalReasoning = [];
for (const message of context.messages.filter(message => message.role === 'assistant')) {
  codexModel(message.provider, message.model);
  for (const block of message.content.filter(block => block.type === 'thinking')) {
    if (message.provider !== 'openai-codex' || message.api !== 'openai-codex-responses' || !block.thinkingSignature) {
      throw new Error(`Cannot preserve reasoning from ${message.provider}/${message.model}: no verified OpenAI replay payload. Import stopped.`);
    }
    if (reasoningFamily(message.model) !== reasoningFamily(modelId)) {
      throw new Error(`Cannot preserve reasoning across incompatible model families: ${message.model} -> ${modelId}`);
    }
    const reasoning = JSON.parse(block.thinkingSignature);
    if (reasoning.type !== 'reasoning') throw new Error('Cannot preserve reasoning: unexpected replay payload.');
    originalReasoning.push(reasoning);
  }
}
const model = {
  id: modelId,
  provider: 'openai-codex',
  api: 'openai-codex-responses',
  input: ['text', 'image'],
  reasoning: true,
};
const attributedMessages = context.messages.map(message => {
  if (message.role !== 'custom' || message.customType !== 'pi-simple-team' || !message.details?.from) return message;
  const { team, from, to = 'main' } = message.details;
  const content = typeof message.content === 'string' ? [{ type: 'text', text: message.content }] : message.content;
  return { ...message, content: [{ type: 'text', text: `[Pi team ${team}: from ${from} to ${to}]` }, ...content] };
});
const messages = convertToLlm(attributedMessages)
  .filter(message => message.role !== 'system')
  // Codex replays OpenAI reasoning across GPT model changes. Pi's model-switch filter would discard it.
  .map(message => message.role === 'assistant' && message.provider === 'openai-codex'
    ? { ...message, model: modelId }
    : message);
const items = convertResponsesMessages(model, { messages }, new Set(['openai-codex']))
  .map(item => ({ ...item, type: item.type ?? 'message' }));
if (!isDeepStrictEqual(items.filter(item => item.type === 'reasoning'), originalReasoning)) {
  throw new Error('Cannot preserve reasoning: message conversion changed or removed replay payloads. Import stopped.');
}
console.log(JSON.stringify({ model: modelId, effort: context.thinkingLevel === 'off' ? 'none' : context.thinkingLevel, items }));
