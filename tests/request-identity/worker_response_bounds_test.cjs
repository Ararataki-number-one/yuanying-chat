'use strict';

// Real TLS retrieves the production-generated Worker. VM execution exercises its
// actual stream parser with controlled byte streams, not a browser/Gecko verdict.
const test = require('node:test'), assert = require('node:assert/strict');
const fs = require('node:fs'), path = require('node:path'), os = require('node:os');
const https = require('node:https'), vm = require('node:vm'), crypto = require('node:crypto');
const {execFileSync} = require('node:child_process');
const {createIdentityService, PROTOCOL, DEFAULT_BASE} = require('../../tools/fingerprint/request_identity_server.cjs');
const nonce = 'a'.repeat(32);
const valid = {schema: 1, protocol: PROTOCOL, nonce, source: 'worker-fetch', ok: true};
const bytes = value => new TextEncoder().encode(typeof value === 'string' ? value : JSON.stringify(value));

async function execute(script, options = {}) {
  const observations = {reads: 0, readBytes: 0, jsonCalls: 0, cancelled: 0, released: 0, aborted: false, requestedTimeouts: [], cleared: 0};
  const chunks = (options.chunks || [bytes(valid)]).slice();
  const total = Buffer.concat(chunks.filter(value => value instanceof Uint8Array).map(value => Buffer.from(value)));
  let done, signal;
  const result = new Promise(resolve => {done = resolve;});
  const fetch = async (_url, init) => {
    signal = init.signal;signal.addEventListener('abort', () => {observations.aborted = true;});
    if (options.fetchError) throw new TypeError('ControlledNetworkFailure');
    const reader = {async read() {
      observations.reads++;
      if (options.hang) return new Promise((_resolve, reject) => signal.addEventListener('abort', () => reject(new Error('Aborted')), {once: true}));
      if (!chunks.length) return {done: true};
      const value = chunks.shift();observations.readBytes += value?.byteLength || 0;return {done: false, value};
    }, async cancel() {observations.cancelled++;}, releaseLock() {observations.released++;}};
    return {ok: options.ok !== false, headers: {get: () => options.length ?? null},
      body: options.noStream ? null : {getReader: () => reader},
      async json() {observations.jsonCalls++;return JSON.parse(total.toString('utf8'));}};
  };
  const context = {navigator: {userAgent: 'VMWorker/1', language: 'en-US', languages: ['en-US']},
    URL, location: {href: 'https://controlled.example' + DEFAULT_BASE + 'worker.js?nonce=' + nonce},
    Uint8Array, TextDecoder, AbortController, fetch,
    setTimeout(fn, ms) {observations.requestedTimeouts.push(ms);return setTimeout(fn, options.fastTimeout && ms === 5000 ? 20 : ms);},
    clearTimeout(id) {observations.cleared++;clearTimeout(id);}, postMessage: value => done(JSON.parse(JSON.stringify(value)))};
  vm.runInNewContext(script, context, {filename: 'actual-generated-worker.js'});
  let timeout;
  const value = await Promise.race([result, new Promise((_resolve, reject) => {timeout = setTimeout(() => reject(Error('Controlled worker did not finish')), 6000);})]);
  clearTimeout(timeout);for (let i = 0; i < 5; i++) await Promise.resolve();
  return {value, observations};
}

test('generated Worker limits decoded response by actual bytes before JSON parsing', async t => {
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'pocketchat-worker-stream-'));
  const key = path.join(temp, 'key.pem'), cert = path.join(temp, 'cert.pem');
  execFileSync('openssl', ['req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-sha256', '-days', '1', '-subj', '/CN=localhost',
    '-addext', 'subjectAltName=DNS:localhost,IP:127.0.0.1', '-keyout', key, '-out', cert], {stdio: 'ignore'});
  const service = createIdentityService({key: fs.readFileSync(key), cert: fs.readFileSync(cert)});
  await new Promise(resolve => service.server.listen(0, '127.0.0.1', resolve));
  const get = operation => new Promise((resolve, reject) => https.get({hostname: '127.0.0.1', port: service.server.address().port,
    path: DEFAULT_BASE + operation + '?nonce=' + nonce, ca: fs.readFileSync(cert), agent: false}, response => {
      let text = '';response.setEncoding('utf8');response.on('data', value => {text += value;});response.on('end', () => resolve({text, status: response.statusCode}));
    }).on('error', reject));
  try {
    assert.equal((await get('document')).status, 200);const generated = await get('worker.js');assert.equal(generated.status, 200);
    const script = generated.text;assert.equal(script.includes('response.json()'), false);
    await t.test('normal bounded response retains Worker result and original five-second deadline', async () => {
      const result = await execute(script);assert.equal(result.value.status, 'complete');assert.equal(result.observations.jsonCalls, 0);
      assert.equal(result.observations.cancelled, 1);assert.equal(result.observations.released, 1);assert.deepEqual(result.observations.requestedTimeouts, [5000]);assert.equal(result.observations.cleared, 1);
    });
    await t.test('exact 8192 bytes succeeds, one additional streamed byte fails and aborts', async () => {
      const exact = bytes(JSON.stringify(valid) + ' '.repeat(8192 - bytes(valid).length));assert.equal(exact.length, 8192);
      assert.equal((await execute(script, {chunks: [exact.slice(0, 4096), exact.slice(4096)]})).value.status, 'complete');
      const over = await execute(script, {chunks: [exact.slice(0, 4096), exact.slice(4096), bytes(' ')]});
      assert.equal(over.value.error, 'worker-response-too-large');assert.equal(over.value.status, 'failed');assert.equal(over.observations.readBytes, 8193);assert.equal(over.observations.jsonCalls, 0);assert.equal(over.observations.aborted, true);assert.equal(over.observations.cancelled, 1);
    });
    await t.test('multibyte body is bounded by byte count and reproduces the old unbounded acceptance', async () => {
      const body = bytes({...valid, padding: '中'.repeat(3000)});assert.ok(body.length > 8192);
      const fixture = fs.readFileSync(path.join(__dirname, 'fixtures/worker-script-before-d0d648cc.js'));
      assert.equal(crypto.createHash('sha256').update(fixture).digest('hex'), 'd0265e5f2f6f63745cf50eabbb87b5bbd082ccf855232b5466519c6d6e20f1a9');
      const before = fixture.toString() + '\nworkerScript(' + JSON.stringify(nonce) + ',' + JSON.stringify(PROTOCOL) + ');';
      const old = await execute(before, {chunks: [body]});assert.equal(old.value.status, 'complete');assert.equal(old.observations.jsonCalls, 1);assert.equal(old.observations.reads, 0);
      const current = await execute(script, {chunks: [body]});assert.equal(current.value.error, 'worker-response-too-large');assert.equal(current.observations.jsonCalls, 0);assert.equal(current.observations.aborted, true);
    });
    await t.test('declared large or malformed length is rejected before any stream read', async () => {
      for (const [length, reason] of [['8193', 'worker-response-too-large'], ['invalid', 'worker-response-invalid-length']]) {
        const result = await execute(script, {length});assert.equal(result.value.error, reason);assert.equal(result.observations.reads, 0);assert.equal(result.observations.aborted, true);
      }
    });
    await t.test('no bounded stream never falls back to json', async () => {
      const result = await execute(script, {noStream: true});assert.equal(result.value.error, 'worker-response-stream-unavailable');assert.equal(result.observations.jsonCalls, 0);
    });
    await t.test('invalid UTF8, JSON and protocol retain distinct bounded categories', async () => {
      for (const [body, reason] of [[new Uint8Array([255]), 'worker-response-invalid-utf8'], [bytes('{'), 'worker-response-invalid-json'], [bytes(null), 'worker-response-protocol-mismatch'], [bytes({...valid, nonce: 'b'.repeat(32)}), 'worker-response-protocol-mismatch']]) {
        const result = await execute(script, {chunks: [body]});assert.equal(result.value.error, reason);assert.equal(result.value.status, 'failed');assert.equal(result.observations.cancelled, 1);
      }
    });
    await t.test('HTTP failure and transport failure remain separate without reading a body', async () => {
      const response = await execute(script, {ok: false});assert.equal(response.value.error, 'worker-response-http-failed');assert.equal(response.observations.reads, 0);
      const transport = await execute(script, {fetchError: true});assert.equal(transport.value.error, 'worker-response-transport-failed');assert.equal(transport.observations.reads, 0);
    });
    await t.test('deadline abort releases a pending reader, using a controlled shorter clock only in this VM case', async () => {
      const result = await execute(script, {hang: true, fastTimeout: true});assert.equal(result.value.error, 'worker-response-timeout');assert.equal(result.observations.aborted, true);assert.equal(result.observations.cancelled, 1);assert.equal(result.observations.released, 1);assert.deepEqual(result.observations.requestedTimeouts, [5000]);
    });
    await t.test('malformed stream chunk is rejected and releases reader ownership', async () => {
      const result = await execute(script, {chunks: [new DataView(new ArrayBuffer(8))]});assert.equal(result.value.error, 'worker-response-invalid-stream');assert.equal(result.observations.cancelled, 1);assert.equal(result.observations.released, 1);
    });
  } finally {await service.close();fs.rmSync(temp, {recursive: true, force: true});}
});
