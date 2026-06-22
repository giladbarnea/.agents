#!/usr/bin/env node
import fsSync from 'node:fs';
import fs from 'node:fs/promises';
import http from 'node:http';
import net from 'node:net';
import os from 'node:os';
import path from 'node:path';
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';

const scriptPath = fileURLToPath(import.meta.url);
const scriptsDirectory = path.dirname(scriptPath);
const skillDirectory = path.dirname(scriptsDirectory);
const templatesDirectory = path.join(skillDirectory, 'templates');
const iCloudDirectory = path.join(os.homedir(), 'Library/Mobile Documents/com~apple~CloudDocs');
const contentMarkerPattern = /\s*<!-- CONTENT START[\s\S]*?CONTENT END -->/;
const stylesheetLinkPattern = cssBasename => new RegExp(`<link\\b[^>]*?href\\s*=\\s*['"][^'"]*${escapeRegExp(cssBasename)}['"][^>]*?>\\s*`, 'gi');

function usage() {
  return `Usage:
  inhtml build CONTENT.html --title "Page title" --layer 3 --out /tmp/page [options]
  build.mjs [build] CONTENT.html --title "Page title" --layer 3 --out /tmp/page [options]

Options:
  --layer 1|2|3                 Build style-only, interactive, or annotated page. Default: 3.
  --title TEXT                  HTML <title>. Default: Interactive Brief.
  --out DIR                     Output directory. Default: a new /tmp/inhtml-<title>-* dir.
  --also-layer1 FILE            Also write a self-contained layer-1 HTML file.
  --also-layer1-icloud FILE     Also write a self-contained layer-1 file into iCloud Drive.
  --port PORT                   Port for the layer-3 annotation server. Default: first free 8765-8799.
  --no-serve                    Build layer 3 without starting annotation-writer.mjs.
  --allow-missing-links         Warn instead of failing on broken internal #links.
  -h, --help                    Show this help.

CONTENT.html is an HTML body fragment. If it is a full HTML document, only <body> is used.
The builder mirrors data-annotation-id values into id attributes before link validation.`;
}

function parseArgs(argv) {
  const queue = argv[0] === 'build' ? argv.slice(1) : argv.slice();
  const options = {
    layer: 3,
    title: 'Interactive Brief',
    outputDirectory: null,
    contentPath: null,
    alsoLayer1Outputs: [],
    port: null,
    serve: true,
    allowMissingLinks: false,
  };

  for (let index = 0; index < queue.length; index += 1) {
    const arg = queue[index];
    if (arg === '-h' || arg === '--help') {
      console.log(usage());
      process.exit(0);
    }
    if (arg === '--layer') {
      options.layer = Number(readValue(queue, index += 1, arg));
      continue;
    }
    if (arg === '--title') {
      options.title = readValue(queue, index += 1, arg);
      continue;
    }
    if (arg === '--out') {
      options.outputDirectory = expandHome(readValue(queue, index += 1, arg));
      continue;
    }
    if (arg === '--also-layer1') {
      options.alsoLayer1Outputs.push(expandHome(readValue(queue, index += 1, arg)));
      continue;
    }
    if (arg === '--also-layer1-icloud' || arg === '--icloud') {
      options.alsoLayer1Outputs.push(resolveICloudOutput(readValue(queue, index += 1, arg)));
      continue;
    }
    if (arg === '--port') {
      options.port = Number(readValue(queue, index += 1, arg));
      continue;
    }
    if (arg === '--no-serve') {
      options.serve = false;
      continue;
    }
    if (arg === '--allow-missing-links') {
      options.allowMissingLinks = true;
      continue;
    }
    if (arg.startsWith('-')) {
      throw new Error(`Unknown option: ${arg}`);
    }
    if (options.contentPath) {
      throw new Error(`Unexpected extra positional argument: ${arg}`);
    }
    options.contentPath = expandHome(arg);
  }

  assertOptions(options);
  return options;
}

function readValue(argv, index, flag) {
  const value = argv[index];
  if (!value || value.startsWith('--')) {
    throw new Error(`${flag} requires a value.`);
  }
  return value;
}

function assertOptions(options) {
  if (!options.contentPath) {
    throw new Error('Missing CONTENT.html path.');
  }
  if (![1, 2, 3].includes(options.layer)) {
    throw new Error('--layer must be 1, 2, or 3.');
  }
  if (options.port !== null && (!Number.isInteger(options.port) || options.port < 1 || options.port > 65535)) {
    throw new Error('--port must be an integer between 1 and 65535.');
  }
}

function expandHome(value) {
  if (value === '~') {
    return os.homedir();
  }
  if (value.startsWith('~/')) {
    return path.join(os.homedir(), value.slice(2));
  }
  return value;
}

function resolveICloudOutput(value) {
  const expanded = expandHome(value);
  if (path.isAbsolute(expanded)) {
    return ensureHtmlExtension(expanded);
  }
  return path.join(iCloudDirectory, ensureHtmlExtension(expanded));
}

function ensureHtmlExtension(value) {
  return value.toLowerCase().endsWith('.html') ? value : `${value}.html`;
}

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function escapeHtml(value) {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;');
}

function escapeAttribute(value) {
  return value.replaceAll('&', '&amp;').replaceAll('"', '&quot;');
}

function slugify(value) {
  const slug = value.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
  return slug || 'page';
}

async function readContentFragment(contentPath) {
  const content = await fs.readFile(contentPath, 'utf8');
  const bodyMatch = content.match(/<body\b[^>]*>([\s\S]*?)<\/body>/i);
  const fragment = bodyMatch ? bodyMatch[1] : content;
  return mirrorAnnotationIds(fragment.trim());
}

function mirrorAnnotationIds(html) {
  return html.replace(/<([a-zA-Z][\w:-]*)(\s[^<>]*?\bdata-annotation-id\s*=\s*(['"])([^'"]+)\3[^<>]*?)>/g, (match, tag, attributes, _quote, annotationId) => {
    if (/\sid\s*=/.test(attributes)) {
      return match;
    }
    return `<${tag} id="${escapeAttribute(annotationId)}"${attributes}>`;
  });
}

async function buildLayer({layer, title, outputDirectory, content, allowMissingLinks}) {
  await fs.mkdir(outputDirectory, {recursive: true});
  const templateName = layer === 1 ? 'template-style.html' : layer === 2 ? 'template-interactive.html' : 'template.html';
  const templatePath = path.join(templatesDirectory, templateName);
  const indexPath = path.join(outputDirectory, 'index.html');
  await copyLayerAssets(layer, outputDirectory);
  await writeInjectedTemplate(templatePath, indexPath, title, content);

  if (layer !== 1) {
    await validateLinks(indexPath, allowMissingLinks);
    return {indexPath};
  }

  const pagePath = path.join(outputDirectory, 'page.html');
  await inlineCss(indexPath, path.join(outputDirectory, 'style.css'), pagePath);
  await validateLinks(pagePath, allowMissingLinks);
  return {indexPath, pagePath};
}

async function copyLayerAssets(layer, outputDirectory) {
  await copyFromScripts('style.css', outputDirectory);
  if (layer >= 2) {
    await copyFromScripts('interactions.js', outputDirectory);
  }
  if (layer >= 3) {
    await copyFromScripts('annotations.css', outputDirectory);
    await copyFromScripts('annotations.js', outputDirectory);
    await copyFromScripts('annotation-writer.mjs', outputDirectory);
    await writeIfMissing(path.join(outputDirectory, 'annotations.json'), '{}\n');
  }
}

async function copyFromScripts(filename, outputDirectory) {
  await fs.copyFile(path.join(scriptsDirectory, filename), path.join(outputDirectory, filename));
}

async function writeInjectedTemplate(templatePath, outputPath, title, content) {
  const template = await fs.readFile(templatePath, 'utf8');
  const titled = template.replace(/<title>[\s\S]*?<\/title>/i, `<title>${escapeHtml(title)}</title>`);
  if (!contentMarkerPattern.test(titled)) {
    throw new Error(`Template has no CONTENT START/END block: ${templatePath}`);
  }
  await fs.writeFile(outputPath, titled.replace(contentMarkerPattern, `\n${content}\n`));
}

async function writeIfMissing(filePath, content) {
  try {
    await fs.access(filePath);
  } catch (error) {
    if (error.code !== 'ENOENT') {
      throw error;
    }
    await fs.writeFile(filePath, content);
  }
}

async function inlineCss(htmlPath, cssPath, outputPath) {
  const html = await fs.readFile(htmlPath, 'utf8');
  const css = await fs.readFile(cssPath, 'utf8');
  const withoutLink = html.replace(stylesheetLinkPattern(path.basename(cssPath)), '');
  const styleBlock = `<style>\n${css}\n</style>`;
  if (!/<\/head>/i.test(withoutLink)) {
    throw new Error(`No </head> found in ${htmlPath}; cannot inline CSS.`);
  }
  const result = withoutLink.replace(/<\/head>/i, `${styleBlock}</head>`);
  await fs.mkdir(path.dirname(outputPath), {recursive: true});
  await fs.writeFile(outputPath, result);
}

async function buildLayer1Output({title, content, outputPath, allowMissingLinks}) {
  const tempDirectory = await fs.mkdtemp(path.join(os.tmpdir(), 'inhtml-layer1-'));
  const {pagePath} = await buildLayer({layer: 1, title, content, outputDirectory: tempDirectory, allowMissingLinks});
  await fs.mkdir(path.dirname(outputPath), {recursive: true});
  await fs.copyFile(pagePath, outputPath);
  await fs.rm(tempDirectory, {recursive: true, force: true});
  await validateLinks(outputPath, allowMissingLinks);
}

function collectAttributes(html, attribute) {
  const values = new Set();
  const pattern = new RegExp(`\\b${attribute}\\s*=\\s*(['"])(.*?)\\1`, 'gi');
  for (const match of html.matchAll(pattern)) {
    values.add(match[2]);
  }
  return values;
}

async function validateLinks(filePath, allowMissingLinks) {
  const missing = await findMissingInternalLinks(filePath);
  if (missing.length === 0) {
    return;
  }
  const message = `${filePath} has missing internal links: ${missing.map(id => `#${id}`).join(', ')}`;
  if (allowMissingLinks) {
    console.warn(`warning: ${message}`);
    return;
  }
  throw new Error(message);
}

async function findMissingInternalLinks(filePath) {
  const html = await fs.readFile(filePath, 'utf8');
  const ids = collectAttributes(html, 'id');
  for (const annotationId of collectAttributes(html, 'data-annotation-id')) {
    ids.add(annotationId);
  }

  const missing = new Set();
  const hrefPattern = /\bhref\s*=\s*(['"])#([^'"]*)\1/gi;
  for (const match of html.matchAll(hrefPattern)) {
    const target = decodeURIComponent(match[2]);
    if (target && !ids.has(target)) {
      missing.add(target);
    }
  }
  return [...missing].sort();
}

async function canListen(port) {
  return new Promise(resolve => {
    const server = net.createServer();
    server.once('error', () => resolve(false));
    server.once('listening', () => server.close(() => resolve(true)));
    server.listen(port, '0.0.0.0');
  });
}

async function choosePort(requestedPort) {
  if (requestedPort !== null) {
    if (await canListen(requestedPort)) {
      return requestedPort;
    }
    throw new Error(`Port ${requestedPort} is already in use.`);
  }
  for (let port = 8765; port <= 8799; port += 1) {
    if (await canListen(port)) {
      return port;
    }
  }
  throw new Error('No free port found in 8765-8799. Use --port.');
}

async function waitForHttp(port) {
  const deadline = Date.now() + 1800;
  while (Date.now() < deadline) {
    if (await httpResponds(port)) {
      return;
    }
    await new Promise(resolve => setTimeout(resolve, 120));
  }
  throw new Error(`Annotation server did not respond on port ${port}. Check server.log.`);
}

async function httpResponds(port) {
  return new Promise(resolve => {
    const request = http.get({hostname: '127.0.0.1', port, path: '/index.html', timeout: 400}, response => {
      response.resume();
      resolve(response.statusCode === 200);
    });
    request.on('error', () => resolve(false));
    request.on('timeout', () => {
      request.destroy();
      resolve(false);
    });
  });
}

async function startAnnotationServer(outputDirectory, requestedPort) {
  const port = await choosePort(requestedPort);
  const logPath = path.join(outputDirectory, 'server.log');
  const stdout = fsSync.openSync(logPath, 'a');
  const child = spawn(process.execPath, ['annotation-writer.mjs'], {
    cwd: outputDirectory,
    detached: true,
    stdio: ['ignore', stdout, stdout],
    env: {
      ...process.env,
      PORT: String(port),
      SERVE_DIR: outputDirectory,
      ANNOTATIONS_FILE: path.join(outputDirectory, 'annotations.json'),
    },
  });

  child.unref();
  await fs.writeFile(path.join(outputDirectory, 'server.pid'), `${child.pid}\n`);
  try {
    await waitForHttp(port);
  } catch (error) {
    try {
      process.kill(child.pid, 'SIGTERM');
    } catch {}
    throw error;
  }
  return {port, pid: child.pid, logPath};
}

async function defaultOutputDirectory(title) {
  return fs.mkdtemp(path.join(os.tmpdir(), `inhtml-${slugify(title)}-`));
}

function printSummary(summary) {
  const lines = ['in-html build complete'];
  lines.push(`Layer ${summary.layer}: ${summary.primaryPath}`);
  if (summary.annotationsPath) {
    lines.push(`Annotations: ${summary.annotationsPath}`);
  }
  if (summary.server) {
    lines.push(`URL: http://127.0.0.1:${summary.server.port}/index.html`);
    lines.push(`Server PID: ${summary.server.pid}`);
    lines.push(`Server log: ${summary.server.logPath}`);
  }
  for (const outputPath of summary.layer1Outputs) {
    lines.push(`Layer 1 copy: ${outputPath}`);
  }
  console.log(lines.join('\n'));
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  const content = await readContentFragment(options.contentPath);
  const outputDirectory = options.outputDirectory ?? await defaultOutputDirectory(options.title);
  const buildResult = await buildLayer({
    layer: options.layer,
    title: options.title,
    content,
    outputDirectory,
    allowMissingLinks: options.allowMissingLinks,
  });

  for (const outputPath of options.alsoLayer1Outputs) {
    await buildLayer1Output({
      title: options.title,
      content,
      outputPath,
      allowMissingLinks: options.allowMissingLinks,
    });
  }

  const server = options.layer === 3 && options.serve
    ? await startAnnotationServer(outputDirectory, options.port)
    : null;

  printSummary({
    layer: options.layer,
    primaryPath: buildResult.pagePath ?? buildResult.indexPath,
    annotationsPath: options.layer === 3 ? path.join(outputDirectory, 'annotations.json') : null,
    server,
    layer1Outputs: options.alsoLayer1Outputs,
  });
}

main().catch(error => {
  console.error(`error: ${error.message}`);
  process.exit(1);
});
