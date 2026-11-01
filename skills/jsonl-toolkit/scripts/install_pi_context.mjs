// Shell access to Session.install in lib/pi.mjs: install prepared Pi messages as the active context of a new copy of a session.
import { readFileSync } from 'node:fs';
import { open } from '../lib/pi.mjs';

/** Install prepared messages as a new native context branch in outputPath, keeping the original session bytes intact. */
export function installPiContext(sessionPath, preparedContextPath, outputPath) {
  const messages = JSON.parse(readFileSync(preparedContextPath, 'utf8'));
  return open(sessionPath).install(messages).apply({ to: outputPath }).path;
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
