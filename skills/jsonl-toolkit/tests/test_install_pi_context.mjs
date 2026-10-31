import assert from 'node:assert/strict';
import { existsSync, mkdtempSync, readFileSync, rmSync, symlinkSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { SessionManager } from '/opt/homebrew/lib/node_modules/@earendil-works/pi-coding-agent/dist/core/session-manager.js';
import { installPiContext } from '../scripts/install_pi_context.mjs';
import { getUsageCostBreakdown } from '/opt/homebrew/lib/node_modules/@earendil-works/pi-coding-agent/dist/core/usage-totals.js';
import { estimateProjectedContextTokens } from '/opt/homebrew/lib/node_modules/@earendil-works/pi-coding-agent/dist/core/compaction/compaction.js';

const installer = fileURLToPath(new URL('../scripts/install_pi_context.mjs', import.meta.url));
const timestamp = '2026-10-31T17:00:00.000Z';
const sessionHeader = { type: 'session', version: 3, id: 'archive-session', timestamp, cwd: '/tmp/project' };
const userMessage = text => ({ role: 'user', content: [{ type: 'text', text }], timestamp: Date.parse(timestamp) });
const userEntry = (id, parentId, text) => ({ type: 'message', id, parentId, timestamp, message: userMessage(text) });
const usage = {
  input: 100_000, output: 10, cacheRead: 0, cacheWrite: 0, totalTokens: 100_010,
  cost: { input: 2, output: 0, cacheRead: 0, cacheWrite: 0, total: 2 },
};
const assistantMessage = content => ({ role: 'assistant', content, provider: 'anthropic', api: 'anthropic-messages', model: 'claude-opus-5-5', timestamp: Date.parse(timestamp), usage, stopReason: 'stop' });

function fixture(t, entries, prepared) {
  const directory = mkdtempSync(join(tmpdir(), 'pi-context-install-'));
  t.after(() => rmSync(directory, { recursive: true, force: true }));
  const session = join(directory, 'session.jsonl');
  const context = join(directory, 'context.json');
  const output = join(directory, 'installed.jsonl');
  const bytes = Buffer.from([sessionHeader, ...entries].map(entry => JSON.stringify(entry)).join('\n') + '\n');
  writeFileSync(session, bytes);
  writeFileSync(context, JSON.stringify(prepared));
  return { session, context, output, bytes };
}

test('install prepared context without changing the archived session or its identity', t => {
  const prepared = [userMessage('Only this prepared message belongs in context.')];
  const { session, context, output, bytes } = fixture(t, [userEntry('old-user', null, 'Old context must stay archived.')], prepared);
  const contextBytes = readFileSync(context);
  installPiContext(session, context, output);
  assert(existsSync(output), 'The installer must write a resumable output session');
  assert(readFileSync(output).subarray(0, bytes.length).equals(bytes), 'The archive must survive byte for byte as the output prefix');
  assert(readFileSync(session).equals(bytes), 'The archive input must remain unchanged');
  assert(readFileSync(context).equals(contextBytes), 'The prepared-context input must remain unchanged');
  const installed = SessionManager.open(output);
  assert.equal(installed.getSessionId(), 'archive-session');
  assert.equal(installed.getCwd(), '/tmp/project');
  assert.deepEqual(installed.buildSessionContext().messages, prepared, 'Only the prepared context should reach the next turn');
  assert(installed.getEntry('old-user'), 'The original message must remain inspectable in history');
});

test('installing history does not charge twice or reuse its old context-token count', t => {
  const message = assistantMessage([{ type: 'text', text: 'A compact answer.' }]);
  const { session, context, output } = fixture(t, [
    userEntry('old-user', null, 'Original question'),
    { type: 'message', id: 'old-answer', parentId: 'old-user', timestamp, message },
  ], [userMessage('Prepared question'), message]);
  const original = SessionManager.open(session);
  installPiContext(session, context, output);
  const installed = SessionManager.open(output);
  assert.deepEqual(getUsageCostBreakdown(installed.getEntries()), getUsageCostBreakdown(original.getEntries()), 'Installing context makes no API call and must not add historical billing');
  const estimate = estimateProjectedContextTokens(installed.buildSessionProjection(), installed.getBranch());
  assert(estimate.tokens < 100, `The small prepared context must not inherit its old 100k usage checkpoint: ${estimate.tokens}`);
  assert.equal(estimate.usageTokens, 0);
});

test('unknown prepared message roles fail instead of silently disappearing', t => {
  const { session, context, output, bytes } = fixture(t, [userEntry('old-user', null, 'History')], [{ role: 'typo', content: 'Important text' }]);
  assert.throws(() => installPiContext(session, context, output), /prepared.*role/i);
  assert(!existsSync(output), 'Invalid prepared context must not produce an output file');
  assert(readFileSync(session).equals(bytes));
});

test('structured messages keep tool pairs, images, and thinking payloads intact', t => {
  const thinking = { type: 'thinking', thinking: 'Keep this exact reasoning.', thinkingSignature: 'original-signature' };
  const call = { type: 'toolCall', id: 'call_1', name: 'read', arguments: { path: '/tmp/source' } };
  const result = { role: 'toolResult', toolCallId: 'call_1', toolName: 'read', isError: false, content: [{ type: 'text', text: 'Tool output' }], timestamp: Date.parse(timestamp), usage };
  const prepared = [
    { role: 'system', content: 'Prepared system prompt', timestamp: Date.parse(timestamp) },
    { ...userMessage('Use the image'), content: [{ type: 'text', text: 'Use the image' }, { type: 'image', mimeType: 'image/png', data: 'AQID' }] },
    { ...assistantMessage([thinking, call]), stopReason: 'toolUse' },
    result,
    assistantMessage([{ type: 'text', text: 'Finished' }]),
  ];
  const { session, context, output } = fixture(t, [userEntry('old-user', null, 'Old context')], prepared);
  installPiContext(session, context, output);
  const messages = SessionManager.open(output).buildSessionContext().messages;
  const stripAccounting = message => Object.fromEntries(Object.entries(message).filter(([key]) => key !== 'usage'));
  assert.deepEqual(messages.map(stripAccounting), prepared.map(stripAccounting), 'Installing context must not rewrite prepared message payloads');
  assert.deepEqual(messages[2].content, [thinking, call]);
  assert.equal(messages[3].toolCallId, messages[2].content[1].id);
  assert.equal(messages[2].usage.totalTokens, 0);
  assert.equal(messages[3].usage, undefined, 'Historical tool usage must not be charged again');
});

test('archive system, Bash, and compaction messages do not leak into prepared context', t => {
  const prepared = [{ role: 'system', content: 'Only the new system prompt', timestamp: Date.parse(timestamp) }, userMessage('Only the new question')];
  const { session, context, output } = fixture(t, [
    { type: 'message', id: 'old-system', parentId: null, timestamp, message: { role: 'system', content: 'Old system prompt' } },
    userEntry('old-user', 'old-system', 'Old question'),
    { type: 'message', id: 'old-bash', parentId: 'old-user', timestamp, message: { role: 'bashExecution', command: 'old-command', output: 'old output', exitCode: 0, timestamp: Date.parse(timestamp) } },
    { type: 'compaction', id: 'old-compaction', parentId: 'old-bash', timestamp, summary: 'Old compaction summary', firstKeptEntryId: 'old-user', tokensBefore: 99_000 },
  ], prepared);
  installPiContext(session, context, output);
  assert.deepEqual(SessionManager.open(output).buildSessionContext().messages, prepared);
});

test('preserve the archive name, selected model, thinking level, and abandoned branches', t => {
  const { session, context, output } = fixture(t, [
    { type: 'model_change', id: 'selected-model', parentId: null, timestamp, provider: 'openai-codex', modelId: 'gpt-6-astra' },
    { type: 'thinking_level_change', id: 'selected-thinking', parentId: 'selected-model', timestamp, thinkingLevel: 'high' },
    userEntry('old-user', 'selected-thinking', 'Old question'),
    userEntry('abandoned', 'old-user', 'Abandoned work'),
    { type: 'session_info', id: 'archive-name', parentId: 'old-user', timestamp, name: 'The original session title' },
  ], [assistantMessage([{ type: 'text', text: 'Prepared historical reply from another model' }])]);
  installPiContext(session, context, output);
  const installed = SessionManager.open(output);
  assert.equal(installed.getSessionName(), 'The original session title');
  assert.deepEqual(installed.buildSessionContext().model, { provider: 'openai-codex', modelId: 'gpt-6-astra' });
  assert.equal(installed.buildSessionContext().thinkingLevel, 'high');
  assert(installed.getEntry('abandoned'));
  assert(!installed.getBranch().some(entry => entry.id === 'abandoned'));
});

test('empty and repeated installations replace context rather than accumulate it', t => {
  const { session, context, output } = fixture(t, [userEntry('old-user', null, 'Old context')], []);
  installPiContext(session, context, output);
  assert.deepEqual(SessionManager.open(output).buildSessionContext().messages, []);
  const firstInstalledBytes = readFileSync(output);
  writeFileSync(context, JSON.stringify([userMessage('Second prepared context')]));
  const secondOutput = output + '.second.jsonl';
  installPiContext(output, context, secondOutput);
  assert(readFileSync(secondOutput).subarray(0, firstInstalledBytes.length).equals(firstInstalledBytes));
  assert.deepEqual(SessionManager.open(secondOutput).buildSessionContext().messages, [userMessage('Second prepared context')]);
  const identifiers = SessionManager.open(secondOutput).getEntries().map(entry => entry.id);
  assert.equal(new Set(identifiers).size, identifiers.length, 'Each installation needs fresh native entry identities');
});

test('refuse existing output paths and never overwrite either input', t => {
  const { session, context, output, bytes } = fixture(t, [userEntry('old-user', null, 'History')], [userMessage('New context')]);
  const preparedBytes = readFileSync(context);
  writeFileSync(output, 'Existing output');
  for (const destination of [session, context, output]) {
    assert.throws(() => installPiContext(session, context, destination), { code: 'EEXIST' });
  }
  assert(readFileSync(session).equals(bytes));
  assert(readFileSync(context).equals(preparedBytes));
  assert.equal(readFileSync(output, 'utf8'), 'Existing output');
});

test('missing final newline does not cause the input loader to modify the archive', t => {
  const { session, context, output } = fixture(t, [userEntry('old-user', null, 'History')], [userMessage('New context')]);
  const noNewline = readFileSync(session).subarray(0, -1);
  writeFileSync(session, noNewline);
  installPiContext(session, context, output);
  assert(readFileSync(session).equals(noNewline));
  assert(readFileSync(output).subarray(0, noNewline.length).equals(noNewline));
  assert.deepEqual(SessionManager.open(output).buildSessionContext().messages, [userMessage('New context')]);
});

test('reject invalid archive structure before writing an output', t => {
  const { session, context, output } = fixture(t, [], [userMessage('Prepared context')]);
  for (const entries of [
    [{ ...sessionHeader, version: 2 }],
    [{ type: 'not-a-session' }],
    [sessionHeader, userEntry('duplicate', null, 'One'), userEntry('duplicate', null, 'Two')],
    [sessionHeader, userEntry('orphan', 'missing-parent', 'No parent')],
  ]) {
    const bytes = entries.map(entry => JSON.stringify(entry)).join('\n') + '\n';
    writeFileSync(session, bytes);
    assert.throws(() => installPiContext(session, context, output), /native Pi|archive entry/i);
    assert(!existsSync(output));
    assert.equal(readFileSync(session, 'utf8'), bytes);
  }
});

test('the CLI accepts a JSON message array and reports usage errors clearly', t => {
  const { session, context, output } = fixture(t, [userEntry('old-user', null, 'History')], [userMessage('Prepared via CLI')]);
  const result = spawnSync(process.execPath, [installer, session, context, output], { encoding: 'utf8' });
  assert.equal(result.status, 0, result.stderr);
  assert.equal(result.stdout.trim(), output);
  assert.deepEqual(SessionManager.open(output).buildSessionContext().messages, [userMessage('Prepared via CLI')]);
  const usageError = spawnSync(process.execPath, [installer], { encoding: 'utf8' });
  assert.equal(usageError.status, 2);
  assert.match(usageError.stderr, /SESSION.jsonl PREPARED.json OUTPUT.jsonl/);
});

test('the CLI works through a skill symlink', t => {
  const { session, context, output } = fixture(t, [userEntry('old-user', null, 'History')], [userMessage('Prepared through a skill link')]);
  const linkedInstaller = output + '.installer.mjs';
  symlinkSync(installer, linkedInstaller);
  const result = spawnSync(process.execPath, [linkedInstaller, session, context, output], { encoding: 'utf8' });
  assert.equal(result.status, 0, result.stderr);
  assert(existsSync(output), 'Calling the script through ~/.pi/agent/skills must execute its CLI');
});

test('native custom, Bash, and summary messages use Pi normal model conversion', t => {
  const { session, context, output } = fixture(t, [], [
    { role: 'custom', customType: 'note', content: 'A custom note', timestamp: Date.parse(timestamp) },
    { role: 'bashExecution', command: 'pwd', output: '/tmp', exitCode: 0, timestamp: Date.parse(timestamp) },
    { role: 'branchSummary', summary: 'A branch summary', fromId: 'old-branch', timestamp: Date.parse(timestamp) },
    { role: 'compactionSummary', summary: 'A compaction summary', tokensBefore: 1234, timestamp: Date.parse(timestamp) },
  ]);
  installPiContext(session, context, output);
  const messages = SessionManager.open(output).buildSessionContext().messages;
  assert.deepEqual(messages.map(message => message.role), ['user', 'user', 'user', 'user']);
  assert.equal(messages[0].content[0].text, 'A custom note');
  assert.equal(messages[1].content[0].text, 'Ran `pwd`\n```\n/tmp\n```');
  assert(messages[2].content[0].text.includes('<summary>\nA branch summary</summary>'));
  assert(messages[3].content[0].text.includes('<summary>\nA compaction summary\n</summary>'));
});
