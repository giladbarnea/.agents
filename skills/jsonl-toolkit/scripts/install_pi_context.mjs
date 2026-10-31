import { readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { SessionManager } from '/opt/homebrew/lib/node_modules/@earendil-works/pi-coding-agent/dist/core/session-manager.js';
import { convertToLlm } from '/opt/homebrew/lib/node_modules/@earendil-works/pi-coding-agent/dist/core/messages.js';

const MESSAGE_ROLES = new Set(['system', 'user', 'assistant', 'toolResult', 'custom', 'bashExecution', 'branchSummary', 'compactionSummary']);

/** Install prepared messages as a new native context branch, keeping the original session bytes intact. */
export function installPiContext(sessionPath, preparedContextPath, outputPath) {
  const archive = readFileSync(sessionPath);
  const entries = archive.toString('utf8').split('\n').filter(line => line.trim()).map(line => JSON.parse(line));
  const header = entries[0];
  if (header?.type !== 'session' || header.version !== 3 || typeof header.id !== 'string' || typeof header.cwd !== 'string') {
    throw new Error('Session input must be native Pi v3 JSONL with a session header');
  }
  const identifiers = new Set();
  for (const entry of entries.slice(1)) {
    if (typeof entry.id !== 'string' || entry.type === 'session' || identifiers.has(entry.id) || (entry.parentId !== null && !identifiers.has(entry.parentId))) {
      throw new Error(`Invalid archive entry: ${JSON.stringify(entry.id)}`);
    }
    identifiers.add(entry.id);
  }
  const prepared = JSON.parse(readFileSync(preparedContextPath, 'utf8'));
  if (!Array.isArray(prepared)) throw new Error('Prepared context must be a JSON array of Pi messages');
  for (const [index, message] of prepared.entries()) {
    if (!MESSAGE_ROLES.has(message?.role)) throw new Error(`Prepared message ${index} has an unsupported role`);
  }
  const originalEntryCount = entries.length - 1;
  const manager = SessionManager.inMemory(entries[0].cwd, undefined, entries);
  const originalSettings = manager.buildSessionContext();
  const originalLeaf = manager.getLeafId();
  // Context edits cannot omit system, Bash, or summary entries. A new native root isolates the complete prepared context.
  manager.resetLeaf();
  manager.appendCustomEntry('jsonl-toolkit-context-install', { previousLeafId: originalLeaf });
  for (const message of convertToLlm(prepared)) {
    // Installing historical messages is not another model call or billable tool execution.
    const { usage, ...historical } = message;
    const recorded = message.role === 'assistant' ? {
      ...historical,
      usage: {
        input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0,
        cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 },
      },
    } : historical;
    manager.appendMessage(recorded);
  }
  if (originalSettings.model) manager.appendModelChange(originalSettings.model.provider, originalSettings.model.modelId);
  manager.appendThinkingLevelChange(originalSettings.thinkingLevel);
  const added = manager.getEntries().slice(originalEntryCount);
  const separator = archive.at(-1) === 10 ? '' : '\n';
  const suffix = separator + added.map(entry => JSON.stringify(entry) + '\n').join('');
  writeFileSync(outputPath, Buffer.concat([archive, Buffer.from(suffix)]), { flag: 'wx' });
  return resolve(outputPath);
}

if (import.meta.main) {
  if (process.argv.length !== 5) {
    console.error('Usage: node install_pi_context.mjs SESSION.jsonl PREPARED.json OUTPUT.jsonl');
    process.exitCode = 2;
  } else {
    try {
      console.log(installPiContext(...process.argv.slice(2)));
    } catch (error) {
      console.error(error.message);
      process.exitCode = 1;
    }
  }
}
