// Shell access to lib/pi.mjs: read a Pi session's live context, or apply saved context-edit decisions.
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { open } from '../lib/pi.mjs';

const USAGE = `usage:
  node pi_context_edit.mjs dump SESSION OUT_DIR
  node pi_context_edit.mjs apply SESSION DECISIONS.json [--dry-run] [--to COPY.jsonl] [--marker JSON]

SESSION is a path or a unique session-ID prefix.
dump   writes OUT_DIR/context.md (readable, with entry IDs) and OUT_DIR/outline.txt (one line per entry).
apply  applies Draft decisions, [{targetId, replacement}], where replacement null omits the entry.
       In place after a verified backup, or to a new --to file.`;

function dump(reference, directory) {
  const context = open(reference).context();
  mkdirSync(directory, { recursive: true });
  writeFileSync(join(directory, 'context.md'), context.render());
  writeFileSync(join(directory, 'outline.txt'), context.outline() + '\n');
  return { items: context.length, estimatedTokens: context.tokens, directory };
}

function apply(reference, decisionsPath, options) {
  const valueOf = flag => options.includes(flag) ? options[options.indexOf(flag) + 1] : undefined;
  const draft = open(reference).edit(JSON.parse(readFileSync(decisionsPath, 'utf8')));
  const report = draft.check().report();
  if (options.includes('--dry-run')) return { dryRun: true, ...report };
  return { ...report, ...draft.apply({ to: valueOf('--to'), marker: JSON.parse(valueOf('--marker') ?? '{}') }) };
}

if (import.meta.main) {
  const [command, reference, target, ...options] = process.argv.slice(2);
  const commands = { dump: () => dump(reference, target), apply: () => apply(reference, target, options) };
  if (!commands[command] || !reference || !target) {
    console.error(USAGE);
    process.exitCode = 2;
  } else {
    try {
      console.log(JSON.stringify(commands[command](), null, 1));
    } catch (error) {
      console.error(error.message);
      process.exitCode = 1;
    }
  }
}
