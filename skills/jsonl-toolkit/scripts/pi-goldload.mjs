import { loadEntriesFromFile, buildContextEntries, buildSessionContext } from
  '/opt/homebrew/lib/node_modules/@earendil-works/pi-coding-agent/dist/core/session-manager.js';

const usage = () => console.log(
  'usage: pi-goldload.mjs <session.jsonl> [session.jsonl ...]\n' +
  'Load native Pi sessions through Pi’s session manager and verify their active paths.'
);

const files = process.argv.slice(2);
if (files.length === 0) {
  usage();
  process.exitCode = 2;
} else if (files.length === 1 && ['-h', '--help'].includes(files[0])) {
  usage();
} else if (files.some(file => file.startsWith('-'))) {
  console.error(`pi-goldload.mjs: unknown option: ${files.find(file => file.startsWith('-'))}`);
  usage();
  process.exitCode = 2;
} else {
  for (const file of files) {
    try {
      const entries = loadEntriesFromFile(file);
      const byId = new Map(entries.map(entry => [entry.id, entry]));
      const reached = buildContextEntries(entries, undefined, byId).length;
      const context = buildSessionContext(entries, undefined, byId);
      const passed = reached === entries.length - 1;
      console.log(`${file.split('/').pop()}`);
      console.log(`  entries=${entries.length} reached=${reached} expected=${entries.length - 1} PASS=${passed} contextMessages=${context.messages?.length ?? 'n/a'}`);
    } catch (error) {
      console.error(`${file}: ${error.message}`);
      process.exitCode = 1;
    }
  }
}
