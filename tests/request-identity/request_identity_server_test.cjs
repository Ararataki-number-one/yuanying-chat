'use strict';

// Real TLS transport/protocol test. The clients below are Node HTTPS clients;
// no browser, real Dedicated Worker, account, phone or leak-free verdict is implied.
const test = require('node:test');
const assert = require('node:assert/strict');
const https = require('node:https');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {execFileSync} = require('node:child_process');
const crypto = require('node:crypto');
const {createIdentityService, PROTOCOL, DEFAULT_BASE} = require('../../tools/fingerprint/request_identity_server.cjs');

const nonce = () => crypto.randomBytes(16).toString('hex');

test('controlled HTTPS identity server retains independent, bounded request evidence', async t => {
  const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'pocketchat-request-identity-tls-'));
  const key = path.join(temporary, 'key.pem'), cert = path.join(temporary, 'cert.pem');
  execFileSync('openssl', ['req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-sha256', '-days', '1',
    '-subj', '/CN=localhost', '-addext', 'subjectAltName=DNS:localhost,IP:127.0.0.1', '-keyout', key, '-out', cert], {stdio: 'ignore'});
  const output = path.join(temporary, 'server.json'), rawLog = path.join(temporary, 'server.jsonl');
  const service = createIdentityService({key: fs.readFileSync(key), cert: fs.readFileSync(cert),
    ttlMs: 1000, maxChecks: 64, maxLogEvents: 24, output, rawLog});
  await new Promise(resolve => service.server.listen(0, '127.0.0.1', resolve));
  const port = service.server.address().port;
  function request(operation, id, headers = {}, extra = '', activePort = port, rawPath = '') {
    return new Promise((resolve, reject) => {
      const request = https.request({hostname: '127.0.0.1', port: activePort, path: rawPath || DEFAULT_BASE + operation + '?nonce=' + id + extra,
        method: 'GET', ca: fs.readFileSync(cert), headers, agent: false}, response => {
        let text = ''; response.setEncoding('utf8'); response.on('data', chunk => {text += chunk;});
        response.on('end', () => {let body; try {body = JSON.parse(text);} catch (_) {}
          resolve({status: response.statusCode, headers: response.headers, body, text});});
      });
      request.on('error', reject); request.end();
    });
  }
  try {
    await t.test('unknown nonce is pending and cannot manufacture document evidence', async () => {
      const id = nonce(), value = await request('result', id);
      assert.equal(value.status, 202); assert.equal(value.body.status, 'pending');
      assert.deepEqual(value.body.events, []); assert.equal(value.body.createdAt, 0);
      assert.equal((await request('observe', id, {}, '&source=worker')).status, 409);
    });
    await t.test('actual TLS request headers stay separate from browser-side JavaScript', async () => {
      const id = nonce();
      const document = await request('document', id, {'User-Agent': 'DocumentUA/157', 'Accept-Language': 'zh-CN,en;q=0.5', 'Sec-Fetch-Dest': 'document', 'X-Forwarded-For': '198.51.100.10'});
      assert.equal(document.status, 200); assert.match(document.text, /new Worker/);
      assert.equal(document.headers['referrer-policy'], 'no-referrer');
      assert.match(document.headers['content-security-policy'], /worker-src 'self'/);
      assert.match(document.text, /controlled-top-level-document/);
      assert.match(document.text, /pocketRequestIdentityCollect/);
      assert.equal((await request('result', id, {'User-Agent': 'ControlClient/1'})).status, 202);
      const script = await request('worker.js', id, {'User-Agent': 'WorkerUA/157', 'Accept-Language': 'en-US', 'Sec-Fetch-Dest': 'worker'});
      assert.equal(script.status, 200); assert.match(script.text, /credentials: 'omit'/);
      const observe = await request('observe', id, {'User-Agent': 'WorkerUA/157', 'Accept-Language': 'en-US', 'Sec-Fetch-Dest': 'empty'}, '&source=worker');
      assert.equal(observe.body.nonce, id); assert.equal(observe.body.protocol, PROTOCOL);
      const result = await request('result', id);
      assert.equal(result.status, 200); assert.equal(result.body.status, 'ready'); assert.equal(result.body.source, 'independent-https-server-records');
      assert.deepEqual(result.body.events.map(e => e.source), ['document', 'control-result', 'worker-script', 'worker-fetch']);
      const rows = Object.fromEntries(result.body.events.map(e => [e.source, e]));
      assert.equal(rows.document.headers.userAgent, 'DocumentUA/157');
      assert.equal(rows['worker-fetch'].headers.userAgent, 'WorkerUA/157');
      assert.equal(rows.document.headers.acceptLanguage, 'zh-CN,en;q=0.5');
      assert.equal(rows.document.peer.address, '127.0.0.1'); assert.equal(rows.document.peer.source, 'socket-peer');
      assert.notEqual(rows.document.peer.address, '198.51.100.10');
      assert.equal(result.body.credentialObserved, false); assert.equal(result.body.events.length, 4);
      for (let i = 0; i < 12; i++) await request('result', id);
      assert.equal((await request('result', id)).body.events.length, 4);
    });
    await t.test('document and Worker script provenance cannot be replaced with one fetch tag', async () => {
      const id = nonce(); await request('document', id);
      await request('observe', id, {}, '&source=worker');
      const result = await request('result', id);
      assert.equal(result.status, 202); assert.equal(result.body.status, 'pending');
      assert.equal(result.body.events.some(e => e.source === 'worker-script'), false);
    });
    await t.test('credential-bearing arrivals reject and never store credential values', async () => {
      for (const name of ['Cookie', 'Authorization', 'Proxy-Authorization', 'Referer', 'Origin']) {
        const id = nonce(); const value = await request('document', id, {[name]: 'fixture-secret-must-not-be-recorded'});
        assert.equal(value.status, 403); assert.equal(value.body.status, 'rejected');
        assert.equal(value.body.credentialObserved, true); assert.equal(value.body.reason, 'credential-header-observed');
        assert.equal((await request('result', id)).body.status, 'rejected');
      }
      const persisted = fs.readFileSync(output, 'utf8') + fs.readFileSync(rawLog, 'utf8');
      assert.equal(persisted.includes('fixture-secret-must-not-be-recorded'), false);
    });
    await t.test('late credential-bearing result cannot pass a prior clean check', async () => {
      const id = nonce(); await request('document', id);
      await request('worker.js', id); await request('observe', id, {}, '&source=worker');
      assert.equal((await request('result', id)).status, 200);
      const value = await request('result', id, {Cookie: 'fixture-secret-must-not-be-recorded'});
      assert.equal(value.status, 403); assert.equal(value.body.credentialObserved, true);
      assert.equal((await request('result', id)).body.status, 'rejected');
    });
    await t.test('concurrent check capacity rejects rather than evicts live evidence', async () => {
      const limited = createIdentityService({key: fs.readFileSync(key), cert: fs.readFileSync(cert), maxChecks: 1});
      await new Promise(resolve => limited.server.listen(0, '127.0.0.1', resolve));
      const activePort = limited.server.address().port, id = nonce();
      try {
        assert.equal((await request('document', id, {}, '', activePort)).status, 200);
        const value = await request('document', nonce(), {}, '', activePort);
        assert.equal(value.status, 429); assert.equal(value.body.error, 'detector-capacity');
        const kept = await request('result', id, {}, '', activePort);
        assert.equal(kept.body.events[0].source, 'document');
      } finally {await limited.close();}
    });
    await t.test('host wrapper only owns unhandled routes and cannot bypass detector validation', async () => {
      const handled = [];
      const extra = createIdentityService({key: fs.readFileSync(key), cert: fs.readFileSync(cert), extraHandler: (request, response) => {
        handled.push(request.url);
        if (request.url !== '/chat') return false;
        response.writeHead(200, {'Content-Type': 'text/plain'}); response.end('test-only-chat'); return true;
      }});
      await new Promise(resolve => extra.server.listen(0, '127.0.0.1', resolve));
      const activePort = extra.server.address().port;
      try {
        assert.equal((await request('', '', {}, '', activePort, '/chat')).text, 'test-only-chat');
        assert.equal((await request('document', nonce(), {}, '', activePort)).status, 200);
        assert.equal((await request('document', 'invalid', {}, '', activePort)).status, 400);
        assert.deepEqual(handled, ['/chat']);
        assert.equal(extra.log.events.length, 1); assert.equal(extra.log.events[0].source, 'document');
      } finally {await extra.close();}
    });
    await t.test('existing files and conflicting evidence paths cannot be overwritten', () => {
      const material = {key: fs.readFileSync(key), cert: fs.readFileSync(cert)};
      const before = fs.readFileSync(cert);
      assert.throws(() => createIdentityService({...material, output: cert}), /Output already exists/);
      assert.deepEqual(fs.readFileSync(cert), before);
      assert.throws(() => createIdentityService({...material, output: path.join(temporary, 'same'), rawLog: path.join(temporary, 'same')}), /Distinct output paths/);
    });
    await t.test('TTL expiry releases records and old nonce cannot read stale headers', async () => {
      await new Promise(resolve => setTimeout(resolve, 1100));
      const id = nonce(); await request('document', id);
      await new Promise(resolve => setTimeout(resolve, 1100));
      const value = await request('result', id);
      assert.equal(value.status, 202); assert.equal(value.body.createdAt, 0); assert.deepEqual(value.body.events, []);
    });
    await t.test('duplicate probes are explicit ambiguity and never overwrite earlier headers', async () => {
      const id = nonce(); await request('document', id, {'User-Agent': 'Original/1'});
      const value = await request('document', id, {'User-Agent': 'Replacement/2'});
      assert.equal(value.status, 409); assert.equal(value.body.reason, 'duplicate-probe-source');
      assert.deepEqual(value.body.events.map(e => e.headers.userAgent), ['Original/1', 'Replacement/2']);
    });
    await t.test('nonce identity and protocol query pollution fail closed', async () => {
      assert.equal((await request('document', 'not-a-nonce')).status, 400);
      assert.equal((await request('document', nonce(), {}, '&nonce=' + nonce())).status, 400);
      assert.equal((await request('document', nonce(), {}, '&source=worker')).status, 400);
      assert.equal((await request('observe', nonce(), {}, '&source=document')).status, 400);
      assert.equal((await request('unexpected', nonce())).status, 404);
    });
    await t.test('oversized compared HTTP headers are rejected rather than silently clipped', async () => {
      const limitOutput = path.join(temporary, 'too-long.json'), limitLog = path.join(temporary, 'too-long.jsonl');
      const bounded = createIdentityService({key: fs.readFileSync(key), cert: fs.readFileSync(cert), output: limitOutput, rawLog: limitLog});
      await new Promise(resolve => bounded.server.listen(0, '127.0.0.1', resolve)); const activePort = bounded.server.address().port;
      try {
        for (const [name, maximum] of [['User-Agent', 2048], ['Accept-Language', 1024], ['Sec-Fetch-Dest', 64], ['Sec-Fetch-Site', 64]]) {
          const id = nonce(), sentinel = 'oversized-value-must-not-save-' + 'x'.repeat(maximum);
          const value = await request('document', id, {[name]: sentinel}, '', activePort);
          assert.equal(value.status, 409); assert.equal(value.body.status, 'rejected'); assert.equal(value.body.reason, 'header-value-too-long');
          assert.equal(value.body.events[0].headerValueTooLong, true);
          assert.deepEqual(value.body.events[0].rejectedHeaderFields, [name.toLowerCase()]);
          assert.equal(JSON.stringify(value.body).includes(sentinel), false);
          assert.equal(value.body.events[0].headers.userAgent, '');
          assert.equal((await request('result', id, {}, '', activePort)).body.status, 'rejected');
        }
        const recorded = JSON.parse(fs.readFileSync(limitOutput, 'utf8'));
        const arrivals = fs.readFileSync(limitLog, 'utf8').trim().split('\n').map(line => JSON.parse(line));
        assert.deepEqual(recorded.events, arrivals); assert.equal(recorded.dropped, 0);
        assert.equal(arrivals.filter(event => event.headerValueTooLong).length, 4);
        assert.equal(JSON.stringify(recorded).includes('oversized-value-must-not-save'), false);
      } finally {await bounded.close();}
    });
    await t.test('per-check events and global retained arrivals remain bounded', async () => {
      const id = nonce(); await request('document', id);
      for (let i = 0; i < 16; i++) await request('worker.js', id);
      const value = await request('result', id);
      assert.equal(value.body.status, 'rejected'); assert.equal(value.body.reason, 'event-limit');
      assert.equal(value.body.events.length, 12);
    });
    await t.test('output and independent JSONL have consecutive matching arrivals with a bounded log', async () => {
      const report = JSON.parse(fs.readFileSync(output, 'utf8'));
      const rows = fs.readFileSync(rawLog, 'utf8').trim().split('\n').map(line => JSON.parse(line));
      assert.deepEqual(report.events, rows);
      assert.deepEqual(rows.map(e => e.sequence), rows.map((_, i) => i + 1));
      assert.equal(rows.length, 24); assert.ok(report.dropped > 0); assert.equal(report.scope.includes('not browser'), true);
      assert.equal(report.events.some(e => e.headers && Object.keys(e.headers).some(k => /cookie|authorization|referer/i.test(k))), false);
    });
  } finally {await service.close(); fs.rmSync(temporary, {recursive: true, force: true});}
});
