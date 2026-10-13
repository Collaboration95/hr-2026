#!/usr/bin/env node
import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { isDeepStrictEqual } from 'node:util';
import { validateArtifact } from '../tests/contract-check.mjs';

// No package additions. Run from repo root; use only the announced local endpoint.
const args = process.argv.slice(2);
const value = flag => { const i = args.indexOf(flag); return i < 0 ? undefined : args[i + 1]; };
if (args.includes('--help')) {
  console.log('node app/scripts/browser-check.mjs [--file artifacts/demo-v1.json] [--url http://127.0.0.1:5173] [--expected-plots 17]\nValidates the real v1 artifact. With --url, checks app HTML and /data/demo-v1.json and compares it with --file when supplied. This is HTTP/contract QA, not a browser interaction pass.');
  process.exit(0);
}
const allowed = new Set(['--file', '--url', '--expected-plots']);
for (let i = 0; i < args.length; i += 2) {
  if (!allowed.has(args[i]) || args[i + 1] === undefined || args[i + 1].startsWith('--')) {
    console.error(`Invalid arguments near ${args[i] ?? '(empty)'}. Use --help.`); process.exit(2);
  }
}
const expectedPlots = Number(value('--expected-plots') ?? 17);
if (!Number.isSafeInteger(expectedPlots) || expectedPlots < 1) { console.error('--expected-plots must be a positive integer'); process.exit(2); }
const file = value('--file') ?? (value('--url') ? undefined : 'artifacts/demo-v1.json');
const base = value('--url');
const failures = [];
let canonical;
let served;
async function check(label, operation) {
  try { const result = await operation(); console.log(`PASS ${label}`); return result; }
  catch (error) { failures.push(`${label}: ${error.message}`); console.error(`FAIL ${label}: ${error.message}`); }
}
function validate(data) {
  const { errors, warnings } = validateArtifact(data, { expectedPlots });
  warnings.forEach(warning => console.log(`NOTE ${warning}`));
  if (errors.length) throw new Error(errors.join('\n'));
  return data;
}
async function get(url, kind) {
  const response = await fetch(url, { signal: AbortSignal.timeout(10000), redirect: 'error' });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  if (!(response.headers.get('content-type') ?? '').includes(kind)) throw new Error(`expected ${kind} Content-Type`);
  return response;
}
if (file) canonical = await check(`artifact ${file}`, async () => validate(JSON.parse(await readFile(resolve(file), 'utf8'))));
if (base) {
  await check('local endpoint URL', async () => {
    const url = new URL(base);
    if (url.protocol !== 'http:' || !['127.0.0.1', 'localhost', '[::1]'].includes(url.hostname)) throw new Error('only HTTP loopback endpoints are allowed');
    if (url.username || url.password) throw new Error('endpoint must not contain credentials');
  });
  if (!failures.some(f => f.startsWith('local endpoint URL:'))) {
    await check('frontend HTML', async () => {
      const html = await (await get(new URL('/', base), 'text/html')).text();
      if (!/<(?:div|main)\b[^>]*\bid=["']root["']/i.test(html)) throw new Error('React root missing');
      if (!/<script\b/i.test(html)) throw new Error('application script missing');
    });
    served = await check('served artifact /data/demo-v1.json', async () => validate(await (await get(new URL('/data/demo-v1.json', base), 'application/json')).json()));
    if (canonical && served) await check('served data matches canonical artifact', async () => {
      if (!isDeepStrictEqual(canonical, served)) throw new Error('served JSON differs from canonical artifact; sync app data before reviewing');
    });
  }
}
console.log(JSON.stringify({ kind: 'http-contract-check', browserJourneyTested: false, expectedPlots, failures: failures.length }));
process.exitCode = failures.length ? 1 : 0;
