// Read and edit the model context of a native Pi session in place, through Pi's own context_edit entries.
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { copyFileSync, existsSync, mkdirSync, readFileSync, writeFileSync, appendFileSync } from 'node:fs';
import { join } from 'node:path';
import {
  SessionManager,
  buildSessionProjection,
  loadEntriesFromFile,
} from '/opt/homebrew/lib/node_modules/@earendil-works/pi-coding-agent/dist/core/session-manager.js';
import {
  estimateProjectedContextTokens,
  estimateTokens,
} from '/opt/homebrew/lib/node_modules/@earendil-works/pi-coding-agent/dist/core/compaction/compaction.js';

const USAGE = `usage:
  node pi_context_edit.mjs dump SESSION.jsonl OUT_DIR
  node pi_context_edit.mjs apply SESSION.jsonl EDITS.json [--dry-run] [--marker JSON]

dump   writes OUT_DIR/context.jsonl (one record per context entry), OUT_DIR/context.md (readable view),
       and OUT_DIR/messages.jsonl ({entryId, messages}: the exact projected messages, to build replacements from).
apply  appends one context_edit per {targetId, replacement} in EDITS.json, after a verified backup.
       replacement null omits the entry. {content} replaces its content. A later edit of a target wins.`;

const sha256 = bytes => createHash('sha256').update(bytes).digest('hex');

/** Pi's character-based estimate of a projection. An empty branch has no usage checkpoint, so Pi falls back to characters. */
const estimatedTokens = projection => estimateProjectedContextTokens(projection, []).tokens;

function renderValue(value) {
  return typeof value === 'string' ? value : JSON.stringify(value, null, 1);
}

function renderBlock(block) {
  if (block.type === 'text') return block.text;
  if (block.type === 'image') return `[image ${block.mimeType ?? ''} ${block.data?.length ?? 0} base64 chars]`;
  if (block.type === 'thinking') {
    const opaque = block.thinkingSignature ? ` signature=${block.thinkingSignature.length} chars` : '';
    return block.thinking ? `<thinking${opaque}>\n${block.thinking}\n</thinking>` : `[opaque thinking${opaque}]`;
  }
  if (block.type === 'toolCall') {
    const fields = Object.entries(block.arguments ?? {}).map(([key, value]) => `  ${key}: ${renderValue(value)}`);
    return `→ toolCall ${block.name} id=${block.id}\n${fields.join('\n')}`;
  }
  return `[${block.type} block ${JSON.stringify(block).length} chars]`;
}

function renderMessage(message) {
  if (message.role === 'bashExecution') return `$ ${message.command}\n${message.output ?? ''}`;
  if (typeof message.content === 'string') return message.content;
  if (!Array.isArray(message.content)) return '';
  return message.content.map(renderBlock).join('\n');
}

/** Project the active context with each contributing entry's identity, size and edit state. */
export function describeContext(entries) {
  const projection = buildSessionProjection(entries);
  const edits = new Map(projection.entries.filter(item => item.sourceEntry.type === 'context_edit').map(item => [item.sourceEntry.targetId, item.sourceEntry]));
  const records = projection.entries.filter(item => item.messages.length > 0).map(({ sourceEntry, messages }) => ({
    entryId: sourceEntry.id,
    timestamp: sourceEntry.timestamp,
    role: messages.map(message => message.role === 'custom' ? `custom:${message.customType}` : message.role).join('+'),
    tokens: messages.reduce((total, message) => total + estimateTokens(message), 0),
    edited: edits.has(sourceEntry.id),
    blocks: messages.flatMap(message => Array.isArray(message.content) ? message.content.map(block => block.type === 'toolCall' ? `toolCall:${block.name}` : block.type) : ['text']),
    toolCallIds: messages.flatMap(message => message.role === 'assistant' ? message.content.filter(block => block.type === 'toolCall').map(block => block.id) : []),
    toolResultFor: messages.find(message => message.role === 'toolResult')?.toolCallId,
    text: messages.map(renderMessage).join('\n'),
  }));
  return { projection, records };
}

/** Fail when a projected tool call lacks its result or a result lacks its call. */
export function assertToolPairing(messages) {
  const open = new Map();
  for (const message of messages) {
    if (message.role === 'assistant') {
      for (const block of message.content.filter(candidate => candidate.type === 'toolCall')) open.set(block.id, (open.get(block.id) ?? 0) + 1);
    }
    if (message.role === 'toolResult') {
      assert((open.get(message.toolCallId) ?? 0) > 0, `Tool result ${message.toolCallId} has no preceding call in context`);
      open.set(message.toolCallId, open.get(message.toolCallId) - 1);
    }
  }
  const unanswered = [...open].filter(([, count]) => count > 0).map(([id]) => id);
  assert.deepEqual(unanswered, [], `Tool calls without results in context: ${unanswered.join(', ')}`);
}

function dump(sessionPath, outputDirectory) {
  const entries = loadEntriesFromFile(sessionPath);
  const { projection, records } = describeContext(entries);
  mkdirSync(outputDirectory, { recursive: true });
  writeFileSync(join(outputDirectory, 'context.jsonl'), records.map(({ text, ...record }) => JSON.stringify({ ...record, chars: text.length })).join('\n') + '\n');
  writeFileSync(join(outputDirectory, 'messages.jsonl'), projection.entries.filter(item => item.messages.length > 0)
    .map(({ sourceEntry, messages }) => JSON.stringify({ entryId: sourceEntry.id, messages })).join('\n') + '\n');
  writeFileSync(join(outputDirectory, 'context.md'), records.map(record =>
    `### [${record.entryId}] ${record.role} ~${record.tokens}t${record.edited ? ' (edited)' : ''} ${record.timestamp}\n${record.text}\n`).join('\n'));
  const branch = SessionManager.open(sessionPath).getBranch();
  console.log(JSON.stringify({ contextEntries: records.length, estimatedTokens: estimatedTokens(projection), piContextTokens: estimateProjectedContextTokens(projection, branch).tokens, outputDirectory }));
}

function apply(sessionPath, editsPath, { dryRun, marker }) {
  const before = readFileSync(sessionPath);
  const edits = JSON.parse(readFileSync(editsPath, 'utf8'));
  assert(Array.isArray(edits) && edits.length > 0, 'EDITS.json must be a non-empty array of {targetId, replacement}');
  const entries = loadEntriesFromFile(sessionPath);
  const beforeProjection = buildSessionProjection(entries);
  const storedEntries = entries.length - 1;
  const manager = SessionManager.inMemory(entries[0].cwd, undefined, entries);  // appends into this same array
  const piContextTokens = estimateProjectedContextTokens(beforeProjection, manager.getBranch()).tokens;  // billed usage when Pi has it
  const leafBefore = manager.getLeafId();
  for (const edit of edits) manager.appendContextEdit(edit.targetId, edit.replacement);
  manager.appendCustomEntry('smart-compact-context-edits', { ...marker, leafBefore, edits: edits.length });
  const added = manager.getEntries().slice(storedEntries);
  assert.equal(added.length, edits.length + 1, 'Every edit and the marker must be appended');
  const afterProjection = buildSessionProjection(manager.getEntries());
  assertToolPairing(afterProjection.messages);
  const report = {
    edits: edits.length,
    omitted: edits.filter(edit => edit.replacement === null).length,
    replaced: edits.filter(edit => edit.replacement !== null).length,
    contextMessages: { before: beforeProjection.messages.length, after: afterProjection.messages.length },
    estimatedTokens: { before: estimatedTokens(beforeProjection), after: estimatedTokens(afterProjection) },
    piContextTokensBefore: piContextTokens,
  };
  if (dryRun) return console.log(JSON.stringify({ dryRun: true, ...report }, null, 1));
  let index = 0;
  while (existsSync(`${sessionPath}.backup-${index}`)) index++;
  const backup = `${sessionPath}.backup-${index}`;
  copyFileSync(sessionPath, backup);
  assert.equal(sha256(readFileSync(backup)), sha256(before), 'Backup must match the source bytes');
  assert.equal(sha256(readFileSync(sessionPath)), sha256(before), 'Session changed while edits were prepared; rerun');
  const separator = before.at(-1) === 10 ? '' : '\n';
  appendFileSync(sessionPath, separator + added.map(entry => JSON.stringify(entry) + '\n').join(''));
  const after = readFileSync(sessionPath);
  assert(after.subarray(0, before.length).equals(before), 'Original bytes must survive as an exact prefix');
  const reloaded = buildSessionProjection(loadEntriesFromFile(sessionPath));
  assert.deepEqual(reloaded.messages, afterProjection.messages, 'Reloaded context must match the validated context');
  console.log(JSON.stringify({ ...report, backup, sourceSha256: sha256(before), resultSha256: sha256(after) }, null, 1));
}

if (import.meta.main) {
  const [command, sessionPath, target, ...options] = process.argv.slice(2);
  const markerIndex = options.indexOf('--marker');
  try {
    if (command === 'dump' && sessionPath && target) dump(sessionPath, target);
    else if (command === 'apply' && sessionPath && target) apply(sessionPath, target, {
      dryRun: options.includes('--dry-run'),
      marker: markerIndex >= 0 ? JSON.parse(options[markerIndex + 1]) : {},
    });
    else {
      console.error(USAGE);
      process.exitCode = 2;
    }
  } catch (error) {
    console.error(error.message);
    process.exitCode = 1;
  }
}
