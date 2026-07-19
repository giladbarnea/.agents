import { loadEntriesFromFile, buildContextEntries, buildSessionContext } from
  '/opt/homebrew/lib/node_modules/@earendil-works/pi-coding-agent/dist/core/session-manager.js';
for (const file of process.argv.slice(2)) {
  const entries = loadEntriesFromFile(file);
  const byId = new Map(entries.map(e => [e.id, e]));
  const reached = buildContextEntries(entries, undefined, byId).length;
  const ctx = buildSessionContext(entries, undefined, byId);
  const ok = reached === entries.length - 1;
  console.log(`${file.split('/').pop()}`);
  console.log(`  entries=${entries.length} reached=${reached} expected=${entries.length-1} PASS=${ok} contextMessages=${ctx.messages?.length ?? 'n/a'}`);
}
