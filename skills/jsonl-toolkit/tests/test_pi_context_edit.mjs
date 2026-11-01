import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import { SessionManager } from '/opt/homebrew/lib/node_modules/@earendil-works/pi-coding-agent/dist/core/session-manager.js';

const script = fileURLToPath(new URL('../scripts/pi_context_edit.mjs', import.meta.url));
const timestamp = '2026-11-01T08:00:00.000Z';
const at = Date.parse(timestamp);
const usage = { input: 1, output: 1, cacheRead: 0, cacheWrite: 0, totalTokens: 2, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } };
const assistant = content => ({ role: 'assistant', content, provider: 'anthropic', api: 'anthropic-messages', model: 'claude-opus-5-5', timestamp: at, usage, stopReason: 'stop' });
const entries = [
  { type: 'session', version: 3, id: 'session-under-test', timestamp, cwd: '/tmp/project' },
  { type: 'message', id: 'question', parentId: null, timestamp, message: { role: 'user', content: [{ type: 'text', text: 'Why is the tree slow?' }], timestamp: at } },
  { type: 'message', id: 'call', parentId: 'question', timestamp, message: assistant([{ type: 'toolCall', id: 'tool-1', name: 'bash', arguments: { command: 'time herdr-tree session list' } }]) },
  { type: 'message', id: 'result', parentId: 'call', timestamp, message: { role: 'toolResult', toolCallId: 'tool-1', toolName: 'bash', content: [{ type: 'text', text: 'real 1.3s '.repeat(200) }], isError: false, timestamp: at } },
  { type: 'message', id: 'answer', parentId: 'result', timestamp, message: assistant([{ type: 'text', text: 'Reading every session file takes 1.3 s.' }]) },
];

function fixture(t) {
  const directory = mkdtempSync(join(tmpdir(), 'pi-context-edit-'));
  t.after(() => rmSync(directory, { recursive: true, force: true }));
  const session = join(directory, 'session.jsonl');
  const bytes = Buffer.from(entries.map(entry => JSON.stringify(entry)).join('\n') + '\n');
  writeFileSync(session, bytes);
  const edits = join(directory, 'edits.json');
  return { directory, session, bytes, edits };
}

const run = (...args) => spawnSync(process.execPath, [script, ...args], { encoding: 'utf8' });

test('apply folds a tool pair into text and keeps every original byte', t => {
  const { session, bytes, edits } = fixture(t);
  writeFileSync(edits, JSON.stringify([
    { targetId: 'call', replacement: { content: [{ type: 'text', text: '<tool-skeleton name="bash" outcome="1.3 s"/>' }] } },
    { targetId: 'result', replacement: null },
  ]));
  const applied = run('apply', session, edits);
  assert.equal(applied.status, 0, applied.stderr);
  const after = readFileSync(session);
  assert(after.subarray(0, bytes.length).equals(bytes), 'The archive must survive as an exact prefix');
  assert(readFileSync(`${session}.backup-0`).equals(bytes), 'A verified backup must hold the source bytes');
  const context = SessionManager.open(session).buildSessionContext().messages;
  assert.deepEqual(context.map(message => message.role), ['user', 'assistant', 'assistant']);
  assert.equal(context[1].content[0].text, '<tool-skeleton name="bash" outcome="1.3 s"/>');
  assert.equal(SessionManager.open(session).getEntry('result').message.content[0].text.length, 2000, 'Stored history must stay inspectable');
});

test('apply refuses edits that orphan a tool call, before writing anything', t => {
  const { session, bytes, edits } = fixture(t);
  writeFileSync(edits, JSON.stringify([{ targetId: 'result', replacement: null }]));
  const refused = run('apply', session, edits);
  assert.equal(refused.status, 1);
  assert.match(refused.stderr, /Tool call tool-1 in call has no result in context/);
  assert(readFileSync(session).equals(bytes), 'A refused edit must leave the session unchanged');
  assert(!existsSync(`${session}.backup-0`), 'A refused edit must not create a backup');
});

test('dry-run reports savings without writing', t => {
  const { session, bytes, edits } = fixture(t);
  writeFileSync(edits, JSON.stringify([{ targetId: 'call', replacement: { content: 'folded' } }, { targetId: 'result', replacement: null }]));
  const report = run('apply', session, edits, '--dry-run');
  assert.equal(report.status, 0, report.stderr);
  const parsed = JSON.parse(report.stdout);
  assert(parsed.estimatedTokens.after < parsed.estimatedTokens.before);
  assert(readFileSync(session).equals(bytes));
});

test('apply --to writes a reviewed copy and leaves the session alone', t => {
  const { directory, session, bytes, edits } = fixture(t);
  writeFileSync(edits, JSON.stringify([{ targetId: 'call', replacement: { content: 'folded' } }, { targetId: 'result', replacement: null }]));
  const copy = join(directory, 'copy.jsonl');
  const applied = run('apply', session, edits, '--to', copy, '--marker', '{"pass":3}');
  assert.equal(applied.status, 0, applied.stderr);
  assert(readFileSync(session).equals(bytes));
  assert.equal(SessionManager.open(copy).buildSessionContext().messages.length, 3);
  assert.equal(SessionManager.open(copy).getEntries().at(-1).data.pass, 3);
});

test('dump writes a readable view and a one-line-per-entry outline', t => {
  const { directory, session } = fixture(t);
  const dumped = run('dump', session, join(directory, 'out'));
  assert.equal(dumped.status, 0, dumped.stderr);
  assert.equal(JSON.parse(dumped.stdout).items, 4);
  assert.deepEqual(readFileSync(join(directory, 'out', 'outline.txt'), 'utf8').trim().split('\n').map(line => line.split(' ')[0]), ['question', 'call', 'result', 'answer']);
  assert.match(readFileSync(join(directory, 'out', 'context.md'), 'utf8'), /### \[call\] assistant .*\n→ toolCall bash id=tool-1\n  command: time herdr-tree session list/);
});
