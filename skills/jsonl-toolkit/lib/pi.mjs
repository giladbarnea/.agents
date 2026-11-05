// Building blocks for reading and changing native Pi sessions. Compose them; nothing here decides what to keep.
// Before changing this file, read the design approach in ../references/pi-lib.md: building blocks only, harness
// knowledge yes, case knowledge never, Pi first, small, fail loudly, remove before adding.
//
//   const session = open('01a18383');                     // a session ID prefix or a path
//   const context = session.context();                    // what the model receives now
//   const span = context.between('c73b1603', '2a3102af').editable();
//   const draft = session.edit().omit(span).replace('777c6690', 'A short summary');
//   draft.context().outline();                            // preview, without writing
//   draft.apply({ marker: { pass: 2 } });                 // checked, backed up, appended in place
import { createHash } from 'node:crypto';
import { appendFileSync, copyFileSync, existsSync, globSync, readFileSync, writeFileSync } from 'node:fs';
import { isDeepStrictEqual } from 'node:util';
import { homedir } from 'node:os';
import { basename, join, resolve } from 'node:path';
import { SessionManager, buildSessionProjection } from '/opt/homebrew/lib/node_modules/@earendil-works/pi-coding-agent/dist/core/session-manager.js';
import { estimateProjectedContextTokens, estimateTokens } from '/opt/homebrew/lib/node_modules/@earendil-works/pi-coding-agent/dist/core/compaction/compaction.js';
import { convertToLlm } from '/opt/homebrew/lib/node_modules/@earendil-works/pi-coding-agent/dist/core/messages.js';

export const PI_PACKAGE = '/opt/homebrew/lib/node_modules/@earendil-works/pi-coding-agent';
export const SESSIONS_DIRECTORY = join(homedir(), '.pi/agent/sessions');
const MESSAGE_ROLES = new Set(['system', 'user', 'assistant', 'toolResult', 'custom', 'bashExecution', 'branchSummary', 'compactionSummary']);
const EDITABLE_ROLES = new Set(['user', 'assistant', 'toolResult']);
const ZERO_USAGE = { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } };
// Signed reasoning and binary payloads: changing any of their strings corrupts them.
const OPAQUE_BLOCK_TYPES = new Set(['thinking', 'image']);
const PAYLOAD_REFERENCE = /\[Exact duplicate of payload ([^\s\]]+)\.\]/g;
const payloadAnchor = label => `[Payload ${label}]`;
const payloadReference = label => `[Exact duplicate of payload ${label}.]`;

function demand(condition, message) {
  if (!condition) throw new Error(message);
}

const sha256 = bytes => createHash('sha256').update(bytes).digest('hex');

/** Open a native Pi session by path, or by a unique prefix of its session ID under the sessions directory. */
export function open(reference, { sessionsDirectory = SESSIONS_DIRECTORY } = {}) {
  const path = existsSync(reference) ? resolve(reference) : findSession(reference, sessionsDirectory);
  return new Session(path, readFileSync(path));
}

function findSession(reference, sessionsDirectory) {
  const matches = globSync('*/*.jsonl', { cwd: sessionsDirectory }).filter(file => basename(file, '.jsonl').split('_').at(-1).startsWith(reference));
  demand(matches.length > 0, `No Pi session matches ${reference} under ${sessionsDirectory}`);
  demand(matches.length === 1, `Session reference ${reference} is ambiguous: ${matches.join(', ')}`);
  return join(sessionsDirectory, matches[0]);
}

/** Parse session bytes strictly. Unlike Pi's own loader, reading never repairs or rewrites the file. */
function parse(bytes, path) {
  const records = bytes.toString('utf8').split('\n').flatMap((line, index) => {
    if (!line.trim()) return [];
    try {
      return [JSON.parse(line)];
    } catch {
      throw new Error(`Malformed JSON on line ${index + 1} of ${path}`);
    }
  });
  const [header, ...entries] = records;
  demand(header?.type === 'session' && header.version === 3 && typeof header.id === 'string' && typeof header.cwd === 'string', `Not a native Pi v3 session: ${path}`);
  const seen = new Set();
  for (const entry of entries) {
    demand(typeof entry.id === 'string' && entry.type !== 'session' && !seen.has(entry.id) && (entry.parentId === null || seen.has(entry.parentId)), `Invalid archive entry ${JSON.stringify(entry.id)} in ${path}`);
    seen.add(entry.id);
  }
  return { header, entries };
}

/** One native session file as it was when opened. Its methods read; only Change.apply writes. */
export class Session {
  #context;

  constructor(path, bytes) {
    this.path = path;
    this.bytes = bytes;
    this.fingerprint = sha256(bytes);
    ({ header: this.header, entries: this.entries } = parse(bytes, path));
    this.byId = new Map(this.entries.map(entry => [entry.id, entry]));
  }

  get id() {
    return this.header.id;
  }

  entry(id) {
    demand(this.byId.has(id), `No entry ${id} in ${this.path}`);
    return this.byId.get(id);
  }

  /** The active ancestry, root first. Pi treats the last stored entry as the leaf. */
  get branch() {
    const path = [];
    for (let entry = this.entries.at(-1); entry; entry = this.byId.get(entry.parentId)) path.unshift(entry);
    return path;
  }

  /** What the model receives now: compactions and context edits applied, abandoned branches left out. */
  context() {
    this.#context ??= contextOf(this.entries);
    return this.#context;
  }

  /** Start a set of context edits. Accepts saved decisions, the array Draft.save writes. */
  edit(decisions = []) {
    return new Draft(this, decisions);
  }

  /** Install prepared Pi messages as a new root context. The archive stays, the old context leaves the active path. */
  install(messages) {
    demand(Array.isArray(messages), 'Prepared context must be a JSON array of Pi messages');
    messages.forEach((message, index) => demand(MESSAGE_ROLES.has(message?.role), `Prepared message ${index} has an unsupported role`));
    return new Change(this, manager => {
      const settings = manager.buildSessionContext();
      const previousLeafId = manager.getLeafId();
      // Context edits cannot omit system, Bash, or summary entries. A new native root isolates the complete prepared context.
      manager.resetLeaf();
      manager.appendCustomEntry('jsonl-toolkit-context-install', { previousLeafId });
      // Installing history is not another model call, so it must neither bill again nor reuse old context-token counts.
      for (const { usage, ...message } of convertToLlm(messages)) manager.appendMessage(message.role === 'assistant' ? { ...message, usage: ZERO_USAGE } : message);
      if (settings.model) manager.appendModelChange(settings.model.provider, settings.model.modelId);
      manager.appendThinkingLevelChange(settings.thinkingLevel);
    });
  }

  /** Structural facts about the session. Raises when the current context pairs tool calls and results wrongly. */
  check() {
    const context = this.context();
    demand(context.problems.length === 0, `${this.path} has an invalid context:\n${context.problems.join('\n')}`);
    const branch = this.branch;
    return {
      session: this.id,
      entries: this.entries.length,
      branch: branch.length,
      abandoned: this.entries.length - branch.length,
      contextItems: context.length,
      estimatedTokens: context.tokens,
    };
  }
}

function contextOf(entries) {
  const projection = buildSessionProjection(entries);
  const edited = new Set(projection.entries.filter(({ sourceEntry }) => sourceEntry.type === 'context_edit').map(({ sourceEntry }) => sourceEntry.targetId));
  const items = projection.entries.filter(({ messages }) => messages.length > 0).map(projected => itemOf(projected, edited));
  return new Context(items, projection);
}

function itemOf({ sourceEntry: entry, messages }, edited) {
  const message = messages.at(-1);
  return Object.freeze({
    id: entry.id,
    entry,
    messages,
    role: message.role,
    customType: message.customType,
    label: message.role === 'custom' ? `custom:${message.customType}` : message.role,
    timestamp: entry.timestamp,
    content: message.content,
    model: message.model,
    tokens: messages.reduce((total, part) => total + estimateTokens(part), 0),
    editable: entry.type === 'custom_message' || (entry.type === 'message' && EDITABLE_ROLES.has(entry.message.role)),
    edited: edited.has(entry.id),
    toolCalls: message.role === 'assistant' ? message.content.filter(block => block.type === 'toolCall').map(block => block.id) : [],
    answers: message.role === 'toolResult' ? message.toolCallId : undefined,
    text: messages.map(part => renderMessage(part)).join('\n'),
  });
}

/** Item IDs from strings, items, selections, or arrays of them. */
function idsOf(targets) {
  return targets.flatMap(target => {
    if (typeof target === 'string') return [target];
    if (target instanceof Selection) return target.ids;
    if (Array.isArray(target)) return idsOf(target);
    return [target.id];
  });
}

/** An ordered subset of a context. Every query returns a new selection of the same context. */
export class Selection {
  constructor(items, context) {
    this.items = items;
    this.context = context ?? this;
  }

  #select(items) {
    return new Selection(items, this.context);
  }

  [Symbol.iterator]() {
    return this.items[Symbol.iterator]();
  }

  get length() {
    return this.items.length;
  }

  get ids() {
    return this.items.map(item => item.id);
  }

  get first() {
    return this.items[0];
  }

  get last() {
    return this.items.at(-1);
  }

  /** The sum of each item's estimate. */
  get tokens() {
    return this.items.reduce((total, item) => total + item.tokens, 0);
  }

  where(predicate) {
    return this.#select(this.items.filter(predicate));
  }

  except(...targets) {
    const excluded = new Set(idsOf(targets));
    return this.where(item => !excluded.has(item.id));
  }

  /** Items from first to last, inclusive, in context order. */
  between(firstId, lastId) {
    const start = this.items.findIndex(item => item.id === firstId);
    const end = this.items.findIndex(item => item.id === lastId);
    demand(start >= 0 && end >= 0, `between(${firstId}, ${lastId}): both entries must be in this selection`);
    demand(start <= end, `between(${firstId}, ${lastId}): ${firstId} comes after ${lastId}`);
    return this.#select(this.items.slice(start, end + 1));
  }

  roles(...roles) {
    return this.where(item => roles.includes(item.role));
  }

  custom(...customTypes) {
    return this.where(item => customTypes.includes(item.customType));
  }

  /** Items Pi's context_edit can omit or replace: user, assistant, tool-result and custom messages. */
  editable() {
    return this.where(item => item.editable);
  }

  /** Items whose text contains a string or matches a regular expression. */
  find(pattern) {
    return this.where(item => typeof pattern === 'string' ? item.text.includes(pattern) : pattern.test(item.text));
  }

  /** The heaviest items, heaviest first. */
  largest(count) {
    return this.#select([...this.items].sort((left, right) => right.tokens - left.tokens).slice(0, count));
  }

  /**
   * Groups of byte-identical strings at least minLength long, each with every {entryId, path} it sits at, largest saving first.
   * Matching is exact: a differently encoded copy, such as a JSON-stringified one, does not match.
   * Strings inside signed thinking and images are never listed. A group feeds draft.dedupe.
   */
  duplicateStrings({ minLength }) {
    demand(Number.isInteger(minLength) && minLength > 0, 'duplicateStrings needs a positive integer minLength');
    const locationsByText = new Map();
    for (const item of this.items) {
      for (const { path, text } of stringsOf(item.content).filter(({ text }) => text.length >= minLength)) {
        locationsByText.set(text, [...(locationsByText.get(text) ?? []), { entryId: item.id, path }]);
      }
    }
    const saving = ({ length, locations }) => length * (locations.length - 1);
    return [...locationsByText]
      .filter(([, locations]) => locations.length > 1)
      .map(([text, locations]) => ({ text, length: text.length, locations }))
      .sort((left, right) => saving(right) - saving(left));
  }

  /** Add the other side of every tool exchange the selection touches, so omitting it cannot orphan a call or a result. */
  complete() {
    const ids = new Set(this.ids.flatMap(id => [id, ...(this.context.partners.get(id) ?? [])]));
    return this.#select(this.context.items.filter(item => ids.has(item.id)));
  }

  /** One line per item, for triage. */
  outline() {
    return this.items.map(item => [
      item.id, item.label.padEnd(26), `${String(item.tokens).padStart(6)}t`, item.timestamp?.slice(0, 16) ?? '', item.edited ? 'edited' : '      ',
      (item.text.split('\n').find(line => line.trim()) ?? '').slice(0, 100),
    ].join('  ')).join('\n');
  }

  /** Readable Markdown with entry IDs. clip shortens each block and states what it removed. */
  render({ clip = Infinity } = {}) {
    return this.items.map(item => {
      const body = item.messages.map(message => renderMessage(message, clip)).join('\n');
      return `### [${item.id}] ${item.label} ~${item.tokens}t${item.edited ? ' (edited)' : ''} ${item.timestamp ?? ''}\n${body}\n`;
    }).join('\n');
  }
}

/** The model-visible context of a session, or of a change previewed before writing. */
export class Context extends Selection {
  constructor(items, projection) {
    super(items);
    this.projection = projection;
    this.messages = projection.messages;
    this.model = projection.model;
    this.thinkingLevel = projection.thinkingLevel;
    this.byId = new Map(items.map(item => [item.id, item]));
    ({ partners: this.partners, problems: this.problems } = pairToolExchanges(items));
  }

  item(id) {
    demand(this.byId.has(id), `${id} is not in the model context`);
    return this.byId.get(id);
  }

  /** Pi's own character estimate for the whole context, counting only the current system prompt. */
  get tokens() {
    return estimateProjectedContextTokens(this.projection, []).tokens;
  }

  /** The usage the provider reported for the last assistant message in context. It predates any later edit. */
  get usage() {
    return this.messages.findLast(message => message.role === 'assistant' && message.usage)?.usage ?? null;
  }

  /** The messages Pi would send to a model, through its own conversion. Defaults to the session's selected model. */
  async wire(model = this.model) {
    const { getModel } = await import(`${PI_PACKAGE}/node_modules/@earendil-works/pi-ai/dist/compat.js`);
    const { transformMessages } = await import(`${PI_PACKAGE}/node_modules/@earendil-works/pi-ai/dist/api/transform-messages.js`);
    const resolved = getModel(model.provider, model.modelId);
    demand(resolved, `Pi does not know the model ${model.provider}/${model.modelId}`);
    return transformMessages(convertToLlm(this.messages), resolved);
  }
}

/** Pair each tool result with its unmatched preceding call, as Pi replays them. Unpaired sides are problems. */
function pairToolExchanges(items) {
  const partners = new Map();
  const open = new Map();
  const problems = [];
  for (const item of items) {
    for (const callId of item.toolCalls) open.set(callId, [...(open.get(callId) ?? []), item.id]);
    if (item.answers === undefined) continue;
    const callerId = open.get(item.answers)?.shift();
    if (callerId === undefined) {
      problems.push(`Tool result ${item.id} answers ${item.answers}, which has no call before it in context`);
      continue;
    }
    partners.set(item.id, [...(partners.get(item.id) ?? []), callerId]);
    partners.set(callerId, [...(partners.get(callerId) ?? []), item.id]);
  }
  for (const [callId, callerIds] of open) {
    for (const callerId of callerIds) problems.push(`Tool call ${callId} in ${callerId} has no result in context`);
  }
  return { partners, problems };
}

const blocks = content => typeof content === 'string' ? [{ type: 'text', text: content }] : content;
const samePath = (left, right) => JSON.stringify(left) === JSON.stringify(right);

/** Every string in message content with its path from the message, skipping signed thinking and images. */
function stringsOf(content) {
  const found = [];
  const walk = (value, path) => {
    if (typeof value === 'string') return void found.push({ path, text: value });
    if (value === null || typeof value !== 'object' || OPAQUE_BLOCK_TYPES.has(value.type)) return;
    for (const [key, nested] of Object.entries(value)) walk(nested, [...path, Array.isArray(value) ? Number(key) : key]);
  };
  walk(blocks(content), ['content']);
  return found;
}

/** The string at a path from the message. Raises when the path is not a string or runs through signed thinking or an image. */
function stringAt(content, { entryId, path }) {
  demand(path[0] === 'content', `Path ${JSON.stringify(path)} must start at the message content`);
  let value = { content };
  for (const key of path) {
    demand(!OPAQUE_BLOCK_TYPES.has(value?.type), `${entryId} ${JSON.stringify(path)} runs through a ${value?.type} block, which must not change`);
    value = value?.[key];
  }
  demand(typeof value === 'string', `${entryId} ${JSON.stringify(path)} is not a string`);
  return value;
}

/** Context edits under construction: one decision per entry, the last one wins. Nothing is written until apply. */
export class Draft {
  #session;
  #decisions = new Map();

  constructor(session, decisions) {
    this.#session = session;
    for (const { targetId, replacement } of decisions) this.#decide(this.#items([targetId]), () => replacement);
  }

  #items(targets) {
    const context = this.#session.context();
    return idsOf(targets).map(id => {
      const item = context.item(id);
      demand(item.editable, `${id} is a ${item.label} entry, which Pi's context_edit cannot change`);
      return item;
    });
  }

  #decide(items, decision) {
    for (const item of items) this.#decisions.set(item.id, decision(item));
    return this;
  }

  /** Leave these entries out of the model context. */
  omit(...targets) {
    return this.#decide(this.#items(targets), () => null);
  }

  /** Give these entries new content: a string becomes one text block. */
  replace(targets, content) {
    return this.#decide(this.#items([targets]), () => ({ content: blocks(content) }));
  }

  /** Change content through a function of the current content, after earlier decisions. Return null to omit. */
  rewrite(targets, change) {
    return this.#decide(this.#items([targets]), item => {
      const current = this.#decisions.has(item.id) ? this.#decisions.get(item.id) : { content: blocks(item.content) };
      demand(current !== null, `${item.id} is omitted; keep it before rewriting it`);
      const next = change(current.content, item);
      return next === null ? null : { content: blocks(next) };
    });
  }

  /**
   * Keep the first location's string as a marked payload anchor and replace each other location with a reference to it.
   * Takes a group from selection.duplicateStrings, or an array of {entryId, path}. Raises unless every string is byte-identical.
   * Matching is exact: a differently encoded copy, such as a JSON-stringified one, does not match.
   */
  dedupe(locations) {
    const [survivor, ...repeats] = locations.locations ?? locations;
    demand(repeats.length > 0, 'dedupe needs a surviving location and at least one repeat');
    demand(new Set([survivor, ...repeats].map(location => JSON.stringify(location))).size === repeats.length + 1, 'dedupe got the same location twice');
    const text = this.#stringAt(survivor);
    for (const repeat of repeats) {
      demand(this.#stringAt(repeat) === text, `${repeat.entryId} ${JSON.stringify(repeat.path)} is not byte-identical to ${survivor.entryId} ${JSON.stringify(survivor.path)}`);
    }
    const label = this.#nextLabel(survivor.entryId);
    this.#setString(survivor, `${payloadAnchor(label)}\n${text}\n[/Payload]`);
    for (const repeat of repeats) this.#setString(repeat, payloadReference(label));
    return this;
  }

  /**
   * Mark one passage of a string as a payload anchor, and replace its other occurrences in the within entries with a reference to it.
   * start and end index the string as context.item(entryId) shows it. Strings inside signed thinking and images are left alone.
   * Raises when the passage is not unique in its own string, occurs nowhere else, or sits in an entry Pi cannot edit.
   * Matching is exact: a differently encoded copy, such as a JSON-stringified one, does not match.
   */
  dedupePassage({ entryId, path, start, end }, { within }) {
    const context = this.#session.context();
    const passage = stringAt(blocks(context.item(entryId).content), { entryId, path }).slice(start, end);
    demand(passage.length > 0 && passage.length === end - start, `Passage [${start}, ${end}) of ${entryId} is empty or out of range`);
    const survivor = this.#stringAt({ entryId, path });
    demand(survivor.split(passage).length === 2, `The passage must occur exactly once in ${entryId} ${JSON.stringify(path)}`);
    const items = idsOf([within]).map(id => context.item(id));
    const blocked = items.filter(item => !item.editable && item.text.includes(passage)).map(item => item.id);
    demand(blocked.length === 0, `${blocked.join(', ')} contain the passage, but Pi's context_edit cannot change them; narrow within`);
    const repeats = items
      .filter(item => item.editable && this.#decisions.get(item.id) !== null)
      .flatMap(item => stringsOf(this.#current(item.id)).map(found => ({ entryId: item.id, ...found })))
      .filter(found => found.text.includes(passage) && !(found.entryId === entryId && samePath(found.path, path)));
    demand(repeats.length > 0, `The passage of ${entryId} occurs nowhere else within the given entries`);
    const label = this.#nextLabel(entryId);
    this.#setString({ entryId, path }, survivor.replace(passage, () => `${payloadAnchor(label)}\n${passage}\n[/Payload]`));
    for (const repeat of repeats) this.#setString(repeat, repeat.text.split(passage).join(payloadReference(label)));
    return this;
  }

  #current(id) {
    const [item] = this.#items([id]);
    const decision = this.#decisions.has(id) ? this.#decisions.get(id) : { content: blocks(item.content) };
    demand(decision !== null, `${id} is omitted; keep it before deduplicating it`);
    return decision.content;
  }

  #stringAt(location) {
    return stringAt(this.#current(location.entryId), location);
  }

  #setString({ entryId, path }, text) {
    this.rewrite(entryId, content => {
      const next = structuredClone(content);
      path.slice(1, -1).reduce((value, key) => value[key], next)[path.at(-1)] = text;
      return next;
    });
  }

  /** The next free anchor label in an entry: its ID and one more than the anchors it already holds. */
  #nextLabel(entryId) {
    const existing = stringsOf(this.#current(entryId)).reduce((total, { text }) => total + text.split(`[Payload ${entryId}:`).length - 1, 0);
    return `${entryId}:${existing + 1}`;
  }

  /** Drop the decisions for these entries, so they stay as they are. */
  keep(...targets) {
    for (const id of idsOf(targets)) this.#decisions.delete(id);
    return this;
  }

  /** The decisions in context order, as {targetId, replacement}. session.edit(decisions) restores them. */
  get decisions() {
    return this.#session.context().ids.filter(id => this.#decisions.has(id)).map(id => ({ targetId: id, replacement: this.#decisions.get(id) }));
  }

  save(path) {
    writeFileSync(path, JSON.stringify(this.decisions, null, 1) + '\n');
    return this;
  }

  /** The pending entries: one context_edit per decision, then a marker that records the pass. */
  change(marker = {}) {
    const decisions = this.decisions;
    demand(decisions.length > 0, 'The draft has no decisions');
    const anchors = decisions
      .filter(({ replacement }) => replacement !== null)
      .flatMap(({ replacement }) => stringsOf(replacement.content).flatMap(({ text }) => [...text.matchAll(PAYLOAD_REFERENCE)].map(match => match[1])));
    return new Change(this.#session, manager => {
      const leafBefore = manager.getLeafId();
      for (const { targetId, replacement } of decisions) manager.appendContextEdit(targetId, replacement);
      manager.appendCustomEntry('smart-compact-context-edits', { ...marker, leafBefore, edits: decisions.length });
    }, { userFirst: true, anchors: [...new Set(anchors)] });
  }

  /** The context as it would be after these edits. */
  context() {
    return this.change().context;
  }

  check() {
    this.change().check();
    return this;
  }

  report() {
    const before = this.#session.context();
    const after = this.context();
    const decisions = this.decisions;
    const omitted = decisions.filter(({ replacement }) => replacement === null).length;
    return {
      omitted,
      replaced: decisions.length - omitted,
      items: { before: before.length, after: after.length },
      estimatedTokens: { before: before.tokens, after: after.tokens },
      lastBilledTokens: before.usage?.totalTokens ?? null,
    };
  }

  /** Check, then write: in place after a verified backup, or to a new file with { to }. */
  apply({ to, marker } = {}) {
    return this.change(marker).apply({ to });
  }
}

/** Entries to append to a session, materialized once, so the checked entries are the written ones. */
export class Change {
  constructor(session, append, { userFirst = false, anchors = [] } = {}) {
    this.session = session;
    const manager = SessionManager.inMemory(session.header.cwd, undefined, [session.header, ...session.entries]);
    append(manager);
    this.entries = manager.getEntries().slice(session.entries.length);
    this.context = contextOf([...session.entries, ...this.entries]);
    this.userFirst = userFirst;
    this.anchors = anchors;
  }

  /** Raise unless every tool call pairs with a result, every payload reference finds its anchor, and, for edits of a conversation, a user message comes first. */
  check() {
    // Pi sends custom, Bash and summary messages as user messages, so judge the converted roles.
    const first = convertToLlm(this.context.messages).find(message => message.role !== 'system');
    const problems = [
      ...this.context.problems,
      ...(this.userFirst && first && first.role !== 'user' ? [`The context would start with an ${first.role} message; providers expect a user message first`] : []),
      ...this.anchors
        .filter(label => !this.context.items.some(item => item.text.includes(payloadAnchor(label))))
        .map(label => `A reference points at payload ${label}, which is not in the context`),
    ];
    demand(problems.length === 0, `The changed context is invalid:\n${problems.join('\n')}`);
    return this;
  }

  /** Write the original bytes plus these entries: in place after a verified backup, or to { to }, which must not exist. */
  apply({ to } = {}) {
    this.check();
    const { path, bytes } = this.session;
    const separator = bytes.length === 0 || bytes.at(-1) === 10 ? '' : '\n';
    const suffix = Buffer.from(separator + this.entries.map(entry => JSON.stringify(entry) + '\n').join(''));
    const target = to === undefined ? path : resolve(to);
    const backup = to === undefined ? backUp(path, bytes) : undefined;
    if (to === undefined) appendFileSync(path, suffix);
    else writeFileSync(target, Buffer.concat([bytes, suffix]), { flag: 'wx' });
    const written = readFileSync(target);
    demand(written.subarray(0, bytes.length).equals(bytes), `${target} lost original bytes`);
    demand(isDeepStrictEqual(new Session(target, written).context().messages, this.context.messages), `Pi would not reload ${target} as the checked context`);
    return { path: target, backup, appended: this.entries.length, sha256: sha256(written) };
  }
}

function backUp(path, bytes) {
  demand(readFileSync(path).equals(bytes), `${path} changed since it was opened; open it again`);
  let index = 0;
  while (existsSync(`${path}.backup-${index}`)) index++;
  const backup = `${path}.backup-${index}`;
  copyFileSync(path, backup);
  demand(readFileSync(backup).equals(bytes), `Backup ${backup} does not match ${path}`);
  return backup;
}

function clipped(text, clip) {
  return text.length <= clip ? text : `${text.slice(0, clip)}… [+${text.length - clip} chars]`;
}

function renderValue(value) {
  return typeof value === 'string' ? value : JSON.stringify(value, null, 1);
}

function renderBlock(block, clip = Infinity) {
  if (block.type === 'text') return clipped(block.text, clip);
  if (block.type === 'image') return `[image ${block.mimeType ?? ''} ${block.data?.length ?? 0} base64 chars]`;
  if (block.type === 'thinking') {
    const signature = block.thinkingSignature ? ` signature=${block.thinkingSignature.length} chars` : '';
    return block.thinking ? `<thinking${signature}>\n${clipped(block.thinking, clip)}\n</thinking>` : `[opaque thinking${signature}]`;
  }
  if (block.type === 'toolCall') {
    const fields = Object.entries(block.arguments ?? {}).map(([key, value]) => `  ${key}: ${clipped(renderValue(value), clip)}`);
    return [`→ toolCall ${block.name} id=${block.id}`, ...fields].join('\n');
  }
  return `[${block.type} block ${JSON.stringify(block).length} chars]`;
}

function renderMessage(message, clip = Infinity) {
  if (message.role === 'system') {
    const sections = Object.entries(message.sections ?? {}).filter(([, text]) => text);
    const tools = message.toolsAdded ? JSON.stringify(message.toolsAdded).length : 0;
    const characters = (message.content?.length ?? 0) + sections.reduce((total, [, text]) => total + text.length, 0) + tools;
    return `[system prompt: ${characters} chars${sections.length ? `; sections ${sections.map(([name]) => name).join(', ')}` : ''}${tools ? `; ${tools} chars of added tools` : ''}]`;
  }
  if (message.role === 'bashExecution') return clipped(`$ ${message.command}\n${message.output ?? ''}`, clip);
  if (message.summary !== undefined) return clipped(message.summary, clip);
  if (typeof message.content === 'string') return clipped(message.content, clip);
  return (message.content ?? []).map(block => renderBlock(block, clip)).join('\n');
}

const escapeAttribute = value => String(value).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

/** smart-compact's skeleton notation for a tool call and its result, folded into one line. */
export function skeleton({ name, command, purpose, outcome, meaning }) {
  const attributes = Object.entries({ name, command, purpose, outcome, meaning }).filter(([, value]) => value !== undefined);
  return `<tool-skeleton ${attributes.map(([key, value]) => `${key}="${escapeAttribute(value)}"`).join(' ')}/>`;
}

/** smart-compact's reference notation for a file operation. */
export function fileReference(operation, path, id) {
  return `<${operation} path="${escapeAttribute(path)}"${id === undefined ? '' : ` id="${escapeAttribute(id)}"`}/>`;
}
