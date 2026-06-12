#!/usr/bin/env node
import fs from 'node:fs/promises';
import http from 'node:http';
import path from 'node:path';

const port = Number(process.env.PORT ?? 8765);
const rootDirectory = path.resolve(process.env.SERVE_DIR ?? '.');
const annotationsPath = path.resolve(process.env.ANNOTATIONS_FILE ?? 'annotations.json');
const maxBodyBytes = 1024 * 1024;
const contentTypes = {
  '.css': 'text/css; charset=utf-8',
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.txt': 'text/plain; charset=utf-8'
};

function isAllowedOrigin(origin, requestHost) {
  if (!origin || origin === 'null') {
    return true;
  }

  try {
    const url = new URL(origin);
    return url.host === requestHost || ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname);
  } catch {
    return false;
  }
}

function setCorsHeaders(request, response) {
  const origin = request.headers.origin;
  if (!isAllowedOrigin(origin, request.headers.host)) {
    return false;
  }

  response.setHeader('Access-Control-Allow-Origin', origin ?? '*');
  response.setHeader('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
  response.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  response.setHeader('Vary', 'Origin');
  return true;
}

async function readRequestJson(request) {
  let body = '';
  for await (const chunk of request) {
    body += chunk;
    if (body.length > maxBodyBytes) {
      throw new Error('Request body is too large.');
    }
  }
  return JSON.parse(body);
}

function assertPayloadStringFields(payload, fields) {
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
    throw new Error('Annotation payload must be an object.');
  }

  for (const key of fields) {
    if (typeof payload[key] !== 'string') {
      throw new Error(`Annotation payload field "${key}" must be a string.`);
    }
  }
}

function assertAnnotationPayload(payload) {
  assertPayloadStringFields(payload, ['selector', 'text', 'userInput', 'timestamp']);

  if (payload.specificallySelected !== undefined && typeof payload.specificallySelected !== 'string') {
    throw new Error('Annotation payload field "specificallySelected" must be a string.');
  }
}

function assertAnnotationsSnapshot(payload) {
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
    throw new Error('Annotations snapshot must be an object.');
  }

  for (const [selector, annotation] of Object.entries(payload)) {
    if (!annotation || typeof annotation !== 'object' || typeof annotation.text !== 'string' || !Array.isArray(annotation.userInputs)) {
      throw new Error(`Annotations snapshot entry "${selector}" must have a string "text" and an array "userInputs".`);
    }
  }
}

async function readAnnotations() {
  try {
    const text = await fs.readFile(annotationsPath, 'utf8');
    if (!text.trim()) {
      return {};
    }

    const parsed = JSON.parse(text);
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      throw new Error(`${annotationsPath} must contain a JSON object.`);
    }
    return parsed;
  } catch (error) {
    if (error.code === 'ENOENT') {
      return {};
    }
    throw error;
  }
}

async function writeAnnotations(annotations) {
  const temporaryPath = `${annotationsPath}.tmp`;
  await fs.mkdir(path.dirname(annotationsPath), {recursive: true});
  await fs.writeFile(temporaryPath, `${JSON.stringify(annotations, null, 2)}\n`);
  await fs.rename(temporaryPath, annotationsPath);
}

function sendJson(response, statusCode, payload) {
  response.writeHead(statusCode, {'Content-Type': 'application/json; charset=utf-8'});
  response.end(`${JSON.stringify(payload)}\n`);
}

function resolveStaticPath(pathname) {
  const decodedPathname = decodeURIComponent(pathname);
  const relativePath = decodedPathname === '/' ? 'index.html' : decodedPathname.replace(/^\/+/, '');
  const filePath = path.resolve(rootDirectory, relativePath);
  const isInsideRoot = filePath === rootDirectory || filePath.startsWith(`${rootDirectory}${path.sep}`);
  if (!isInsideRoot) {
    throw new Error('Static file path escapes the serve directory.');
  }
  return filePath;
}

async function sendStaticFile(request, response, requestUrl) {
  let filePath = resolveStaticPath(requestUrl.pathname);
  const fileStat = await fs.stat(filePath).catch(error => {
    if (error.code === 'ENOENT') {
      return null;
    }
    throw error;
  });

  if (!fileStat) {
    sendJson(response, 404, {ok: false, error: 'File not found.'});
    return;
  }

  if (fileStat.isDirectory()) {
    filePath = path.join(filePath, 'index.html');
  }

  const content = await fs.readFile(filePath);
  const contentType = contentTypes[path.extname(filePath)] ?? 'application/octet-stream';
  response.writeHead(200, {'Content-Type': contentType});
  if (request.method !== 'HEAD') {
    response.end(content);
    return;
  }
  response.end();
}

async function handleAnnotations(request, response) {
  if (!setCorsHeaders(request, response)) {
    sendJson(response, 403, {ok: false, error: 'Origin is not allowed.'});
    return;
  }

  if (request.method === 'OPTIONS') {
    response.writeHead(204);
    response.end();
    return;
  }

  if (request.method === 'GET') {
    sendJson(response, 200, await readAnnotations());
    return;
  }

  // PUT edits one existing note in place, identified by its selector and
  // unique-per-submit timestamp; the timestamp stays as the note's identity.
  if (request.method === 'PUT') {
    const payload = await readRequestJson(request);
    assertPayloadStringFields(payload, ['selector', 'timestamp', 'userInput']);

    const annotations = await readAnnotations();
    const userInputs = annotations[payload.selector]?.userInputs;
    const note = Array.isArray(userInputs)
      ? userInputs.find(item => item?.timestamp === payload.timestamp)
      : undefined;
    if (!note) {
      sendJson(response, 404, {ok: false, error: 'No annotation note matches that selector and timestamp.'});
      return;
    }
    note.userInput = payload.userInput;
    await writeAnnotations(annotations);

    sendJson(response, 200, {ok: true, path: annotationsPath});
    return;
  }

  // DELETE removes one note, again keyed by selector + timestamp; the whole
  // selector entry goes with its last note.
  if (request.method === 'DELETE') {
    const payload = await readRequestJson(request);
    assertPayloadStringFields(payload, ['selector', 'timestamp']);

    const annotations = await readAnnotations();
    const userInputs = annotations[payload.selector]?.userInputs;
    const remaining = Array.isArray(userInputs)
      ? userInputs.filter(item => item?.timestamp !== payload.timestamp)
      : [];
    if (!Array.isArray(userInputs) || remaining.length === userInputs.length) {
      sendJson(response, 404, {ok: false, error: 'No annotation note matches that selector and timestamp.'});
      return;
    }
    if (remaining.length === 0) {
      delete annotations[payload.selector];
    } else {
      annotations[payload.selector].userInputs = remaining;
    }
    await writeAnnotations(annotations);

    sendJson(response, 200, {ok: true, path: annotationsPath});
    return;
  }

  if (request.method !== 'POST') {
    sendJson(response, 405, {ok: false, error: 'Use GET, POST, PUT, or DELETE /annotations.'});
    return;
  }

  const payload = await readRequestJson(request);
  assertAnnotationPayload(payload);

  const annotations = await readAnnotations();
  const existing = annotations[payload.selector];
  const userInputs = Array.isArray(existing?.userInputs) ? existing.userInputs : [];
  const item = {userInput: payload.userInput};
  if (payload.specificallySelected) {
    item.specificallySelected = payload.specificallySelected;
  }
  item.timestamp = payload.timestamp;
  userInputs.push(item);
  annotations[payload.selector] = {
    text: payload.text,
    userInputs
  };
  await writeAnnotations(annotations);

  sendJson(response, 200, {ok: true, path: annotationsPath});
}

// Replaces the entire annotations file with a client-held snapshot — the undo
// path for a deletion: the client snapshots the file just before deleting and
// writes it back verbatim on revert.
async function handleAnnotationsRestore(request, response) {
  if (!setCorsHeaders(request, response)) {
    sendJson(response, 403, {ok: false, error: 'Origin is not allowed.'});
    return;
  }

  if (request.method === 'OPTIONS') {
    response.writeHead(204);
    response.end();
    return;
  }

  if (request.method !== 'POST') {
    sendJson(response, 405, {ok: false, error: 'Use POST /annotations/restore.'});
    return;
  }

  const payload = await readRequestJson(request);
  assertAnnotationsSnapshot(payload);
  await writeAnnotations(payload);

  sendJson(response, 200, {ok: true, path: annotationsPath});
}

const server = http.createServer(async (request, response) => {
  try {
    const requestUrl = new URL(request.url, `http://${request.headers.host}`);

    if (requestUrl.pathname === '/annotations') {
      await handleAnnotations(request, response);
      return;
    }

    if (requestUrl.pathname === '/annotations/restore') {
      await handleAnnotationsRestore(request, response);
      return;
    }

    if (!['GET', 'HEAD'].includes(request.method)) {
      sendJson(response, 405, {ok: false, error: 'Use GET, HEAD, or /annotations.'});
      return;
    }

    await sendStaticFile(request, response, requestUrl);
  } catch (error) {
    sendJson(response, 500, {ok: false, error: error.message});
  }
});

server.listen(port, '0.0.0.0', () => {
  console.log(`in-html server listening on http://0.0.0.0:${port}`);
  console.log(`Serving ${rootDirectory}`);
  console.log(`Writing ${annotationsPath}`);
});
