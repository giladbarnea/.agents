#!/usr/bin/env node
import fs from 'node:fs/promises';
import http from 'node:http';
import path from 'node:path';

const port = Number(process.env.PORT ?? 8765);
const annotationsPath = path.resolve(process.env.ANNOTATIONS_FILE ?? 'm2-abstraction-gap.annotations.json');
const maxBodyBytes = 1024 * 1024;

function isAllowedOrigin(origin) {
  if (!origin || origin === 'null') {
    return true;
  }

  const url = new URL(origin);
  return ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname);
}

function setCorsHeaders(request, response) {
  const origin = request.headers.origin;
  if (!isAllowedOrigin(origin)) {
    return false;
  }

  response.setHeader('Access-Control-Allow-Origin', origin ?? '*');
  response.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
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

function assertAnnotationPayload(payload) {
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
    throw new Error('Annotation payload must be an object.');
  }

  for (const key of ['selector', 'text', 'userInput']) {
    if (typeof payload[key] !== 'string') {
      throw new Error(`Annotation payload field "${key}" must be a string.`);
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

const server = http.createServer(async (request, response) => {
  try {
    if (!setCorsHeaders(request, response)) {
      sendJson(response, 403, {ok: false, error: 'Origin is not allowed.'});
      return;
    }

    if (request.method === 'OPTIONS') {
      response.writeHead(204);
      response.end();
      return;
    }

    const requestUrl = new URL(request.url, `http://${request.headers.host}`);
    if (request.method !== 'POST' || requestUrl.pathname !== '/annotations') {
      sendJson(response, 404, {ok: false, error: 'Use POST /annotations.'});
      return;
    }

    const payload = await readRequestJson(request);
    assertAnnotationPayload(payload);

    const annotations = await readAnnotations();
    annotations[payload.selector] = {
      text: payload.text,
      userInput: payload.userInput
    };
    await writeAnnotations(annotations);

    sendJson(response, 200, {ok: true, path: annotationsPath});
  } catch (error) {
    sendJson(response, 500, {ok: false, error: error.message});
  }
});

server.listen(port, '127.0.0.1', () => {
  console.log(`Annotation writer listening on http://127.0.0.1:${port}`);
  console.log(`Writing ${annotationsPath}`);
});
