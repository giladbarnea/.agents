import { readFileSync } from 'node:fs';
import { buildSessionContext } from '/opt/homebrew/lib/node_modules/@earendil-works/pi-coding-agent/dist/core/session-manager.js';
import { convertToLlm } from '/opt/homebrew/lib/node_modules/@earendil-works/pi-coding-agent/dist/core/messages.js';

const entries = JSON.parse(readFileSync(0, 'utf8'));
console.log(JSON.stringify(convertToLlm(buildSessionContext(entries).messages)));
