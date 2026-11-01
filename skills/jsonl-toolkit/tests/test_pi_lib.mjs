import assert from 'node:assert/strict';
import { appendFileSync, existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';
import { fileReference, open, skeleton } from '../lib/pi.mjs';

const timestamp = '2026-11-01T08:00:00.000Z';
const at = Date.parse(timestamp);
const usage = { input: 10, output: 5, cacheRead: 0, cacheWrite: 0, totalTokens: 15, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } };
const assistant = content => ({ role: 'assistant', content, provider: 'anthropic', api: 'anthropic-messages', model: 'claude-opus-5-5', timestamp: at, usage, stopReason: 'stop' });
const user = text => ({ role: 'user', content: [{ type: 'text', text }], timestamp: at });
const header = id => ({ type: 'session', version: 3, id, timestamp, cwd: '/tmp/project' });
const chain = records => records.map(([id, fields], index) => ({ id, parentId: index === 0 ? null : records[index - 1][0], timestamp, ...fields }));
const ENTRIES = chain([
  ['model', { type: 'model_change', provider: 'anthropic', modelId: 'claude-opus-5-5' }],
  ['system', { type: 'message', message: { role: 'system', content: 'You are a fixture.', timestamp: at } }],
  ['question', { type: 'message', message: user('Why is the tree slow?') }],
  ['call', { type: 'message', message: assistant([{ type: 'thinking', thinking: 'Measure first.', thinkingSignature: 'signed' }, { type: 'toolCall', id: 'tool-1', name: 'bash', arguments: { command: 'time herdr-tree session list' } }]) }],
  ['result', { type: 'message', message: { role: 'toolResult', toolCallId: 'tool-1', toolName: 'bash', content: [{ type: 'text', text: 'real 1.3s '.repeat(300) }], isError: false, timestamp: at } }],
  ['bash', { type: 'message', message: { role: 'bashExecution', command: 'pwd', output: '/tmp/project', exitCode: 0, timestamp: at } }],
  ['tick', { type: 'custom_message', customType: 'pi-time-sense', content: 'It is 10:00.', display: false }],
  ['answer', { type: 'message', message: assistant([{ type: 'text', text: 'Reading every session file takes 1.3 s.' }]) }],
  ['followup', { type: 'message', message: user('Make it faster.') }],
  ['final', { type: 'message', message: assistant([{ type: 'text', text: 'Read the daemon snapshot instead.' }]) }],
]);

function fixture(t, { id = '01a19999-aaaa-7000-8000-000000000001', entries = ENTRIES, finalNewline = true } = {}) {
  const directory = mkdtempSync(join(tmpdir(), 'pi-lib-'));
  t.after(() => rmSync(directory, { recursive: true, force: true }));
  const sessions = join(directory, 'sessions');
  mkdirSync(join(sessions, '--tmp-project--'), { recursive: true });
  const path = join(sessions, '--tmp-project--', `2026-11-01T08-00-00-000Z_${id}.jsonl`);
  const text = [header(id), ...entries].map(entry => JSON.stringify(entry)).join('\n');
  writeFileSync(path, finalNewline ? text + '\n' : text);
  return { directory, sessions, path, bytes: readFileSync(path) };
}

test('open finds a session by path or by a unique ID prefix, and fails loudly otherwise', t => {
  const { sessions, path } = fixture(t);
  assert.equal(open(path).id, '01a19999-aaaa-7000-8000-000000000001');
  assert.equal(open('01a19999-aaaa', { sessionsDirectory: sessions }).path, path);
  writeFileSync(join(sessions, '--tmp-project--', '2026-11-01T08-00-01-000Z_01a19999-bbbb-7000-8000-000000000002.jsonl'), JSON.stringify(header('01a19999-bbbb-7000-8000-000000000002')) + '\n');
  assert.throws(() => open('01a19999', { sessionsDirectory: sessions }), /ambiguous/);
  assert.throws(() => open('01a1ffff', { sessionsDirectory: sessions }), /No Pi session matches/);
});

test('reading never modifies a session, and broken files fail before any use', t => {
  const { path, bytes } = fixture(t, { finalNewline: false });
  assert.equal(open(path).entries.length, ENTRIES.length);
  assert(readFileSync(path).equals(bytes), 'Pi repairs a missing final newline on load; the library must not');
  for (const [text, message] of [
    [JSON.stringify(header('x')) + '\n{not json\n', /Malformed JSON on line 2/],
    [JSON.stringify({ ...header('x'), version: 2 }) + '\n', /native Pi v3/],
    [[header('x'), ...chain([['a', { type: 'message', message: user('one') }]]), { type: 'message', id: 'b', parentId: 'missing', timestamp, message: user('two') }].map(entry => JSON.stringify(entry)).join('\n'), /archive entry "b"/],
  ]) {
    writeFileSync(path, text);
    assert.throws(() => open(path), message);
  }
});

test('the context lists model-visible entries with their roles, edit rights and tool exchanges', t => {
  const context = open(fixture(t).path).context();
  assert.deepEqual(context.ids, ['system', 'question', 'call', 'result', 'bash', 'tick', 'answer', 'followup', 'final']);
  assert.deepEqual(context.where(item => !item.editable).ids, ['system', 'bash']);
  assert.deepEqual(context.item('call').toolCalls, ['tool-1']);
  assert.equal(context.item('result').answers, 'tool-1');
  assert.equal(context.usage.totalTokens, 15);
  assert(context.tokens > context.item('result').tokens);
  assert.match(context.outline(), /^call +assistant +\d+t/m);
  const rendered = context.render({ clip: 40 });
  assert.match(rendered, /### \[call\] assistant ~\d+t .*\n<thinking signature=6 chars>\nMeasure first\.\n<\/thinking>\n→ toolCall bash id=tool-1\n  command: time herdr-tree session list/);
  assert.match(rendered, /### \[bash\] bashExecution .*\n\$ pwd\n\/tmp\/project/);
  assert.match(rendered, /real 1\.3s real 1\.3s real 1\.3s real 1\.3s … \[\+2960 chars\]/);
  assert.match(rendered, /\[system prompt: 18 chars\]/);
});

test('selections chain, keep context order, and complete tool exchanges', t => {
  const context = open(fixture(t).path).context();
  assert.deepEqual(context.between('call', 'tick').ids, ['call', 'result', 'bash', 'tick']);
  assert.throws(() => context.between('tick', 'call'), /comes after/);
  assert.deepEqual(context.between('call', 'tick').editable().except('result').ids, ['call', 'tick']);
  assert.deepEqual(context.roles('user').ids, ['question', 'followup']);
  assert.deepEqual(context.custom('pi-time-sense').ids, ['tick']);
  assert.deepEqual(context.find('1.3 s').ids, ['answer']);
  assert.deepEqual(context.find(/daemon/).ids, ['final']);
  assert.deepEqual(context.largest(1).ids, ['result']);
  assert.deepEqual(context.where(item => item.id === 'result').complete().ids, ['call', 'result']);
  assert.deepEqual(context.where(item => item.id === 'call').complete().ids, ['call', 'result']);
});

test('a draft collects decisions, previews them, and reports what they save', t => {
  const session = open(fixture(t).path);
  const draft = session.edit()
    .omit(session.context().between('call', 'result'), 'tick')
    .replace('answer', 'Measured: 1.3 s.')
    .rewrite('final', content => [...content, { type: 'text', text: 'Then measure again.' }])
    .omit('followup')
    .keep('followup');
  assert.deepEqual(draft.decisions.map(({ targetId }) => targetId), ['call', 'result', 'tick', 'answer', 'final']);
  const preview = draft.context();
  assert.deepEqual(preview.ids, ['system', 'question', 'bash', 'answer', 'followup', 'final']);
  assert.deepEqual(preview.item('answer').content, [{ type: 'text', text: 'Measured: 1.3 s.' }]);
  assert(preview.item('answer').edited);
  assert.equal(preview.item('final').content.at(-1).text, 'Then measure again.');
  const report = draft.report();
  assert.deepEqual([report.omitted, report.replaced, report.items.before, report.items.after], [3, 2, 9, 6]);
  assert(report.estimatedTokens.after < report.estimatedTokens.before);
  assert.throws(() => session.edit().omit('call').rewrite('call', content => content), /omitted/);
  assert.throws(() => session.edit().omit('bash'), /bashExecution entry/);
  assert.throws(() => session.edit().omit('model'), /not in the model context/);
});

test('check refuses an orphaned tool exchange and a context that starts with the assistant', t => {
  const session = open(fixture(t).path);
  assert.throws(() => session.edit().omit('result').check(), /Tool call tool-1 in call has no result/);
  assert.throws(() => session.edit().omit('call').check(), /Tool result result answers tool-1, which has no call/);
  assert.throws(() => session.edit().omit('question').check(), /start with an assistant message/);
  assert.doesNotThrow(() => session.edit().omit('question', 'call', 'result').check(), 'Pi sends a Bash execution as a user message');
});

test('apply appends checked edits in place after a verified backup, and Pi reloads the preview', t => {
  const { path, bytes } = fixture(t);
  const draft = open(path).edit().omit('call', 'result', 'tick');
  const preview = draft.context().messages;
  const result = draft.apply({ marker: { pass: 7 } });
  assert.equal(result.backup, `${path}.backup-0`);
  assert(readFileSync(result.backup).equals(bytes));
  assert(readFileSync(path).subarray(0, bytes.length).equals(bytes), 'Stored history must survive byte for byte');
  const reopened = open(path);
  assert.deepEqual(reopened.context().messages, preview);
  assert.equal(reopened.entry('result').message.content[0].text.length, 3000, 'Omitted entries stay inspectable in the archive');
  const marker = reopened.entries.at(-1);
  assert.equal(marker.customType, 'smart-compact-context-edits');
  assert.deepEqual([marker.data.pass, marker.data.edits, marker.data.leafBefore], [7, 3, 'final']);
  assert.equal(reopened.edit().replace('answer', 'Again').apply().backup, `${path}.backup-1`);
  assert.deepEqual(reopened.check().abandoned, 0);
});

test('apply refuses a session that changed after it was opened, before writing anything', t => {
  const { path } = fixture(t);
  const session = open(path);
  appendFileSync(path, JSON.stringify({ type: 'message', id: 'late', parentId: 'final', timestamp, message: user('Late') }) + '\n');
  const changed = readFileSync(path);
  assert.throws(() => session.edit().omit('tick').apply(), /changed since it was opened/);
  assert(readFileSync(path).equals(changed));
  assert(!existsSync(`${path}.backup-0`));
});

test('apply can write a reviewed copy instead, and never overwrites a file', t => {
  const { directory, path, bytes } = fixture(t);
  const copy = join(directory, 'copy.jsonl');
  const draft = open(path).edit().omit('tick');
  draft.apply({ to: copy });
  assert(readFileSync(path).equals(bytes), 'The source must stay untouched');
  assert.deepEqual(open(copy).context().ids, ['system', 'question', 'call', 'result', 'bash', 'answer', 'followup', 'final']);
  assert.throws(() => draft.apply({ to: copy }), { code: 'EEXIST' });
});

test('saved decisions restore the same draft', t => {
  const { directory, path } = fixture(t);
  const saved = join(directory, 'decisions.json');
  const draft = open(path).edit().omit('tick').replace('answer', 'Short').save(saved);
  assert.deepEqual(open(path).edit(JSON.parse(readFileSync(saved, 'utf8'))).decisions, draft.decisions);
});

test('install puts prepared messages on a new root and keeps the archive', t => {
  const { directory, path } = fixture(t);
  const output = join(directory, 'installed.jsonl');
  open(path).install([user('Only this question')]).apply({ to: output });
  const installed = open(output);
  assert.deepEqual(installed.context().messages, [user('Only this question')]);
  assert(installed.entry('result'), 'The old context stays in the archive');
  assert.throws(() => open(path).install([{ role: 'typo' }]), /Prepared message 0 has an unsupported role/);
});

test('wire converts the context through Pi for the session model', async t => {
  const context = open(fixture(t).path).context();
  const messages = await context.wire();
  assert.equal(messages.at(-1).content[0].text, 'Read the daemon snapshot instead.');
  await assert.rejects(context.wire({ provider: 'anthropic', modelId: 'no-such-model' }), /does not know the model/);
});

test('notation helpers escape attribute values', () => {
  assert.equal(skeleton({ name: 'bash', command: 'a && b', purpose: 'Say "hi"', outcome: '<ok>' }), '<tool-skeleton name="bash" command="a &amp;&amp; b" purpose="Say &quot;hi&quot;" outcome="&lt;ok&gt;"/>');
  assert.equal(fileReference('Read', 'src/a.py', 'r1'), '<Read path="src/a.py" id="r1"/>');
});
