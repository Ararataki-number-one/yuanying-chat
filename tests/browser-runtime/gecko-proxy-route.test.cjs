'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const crypto = require('node:crypto');
const {execFileSync} = require('node:child_process');

const root = path.resolve(__dirname, '../..');
const assetPath = 'app/src/main/assets/gecko/background.js';
const testPath = 'tests/browser-runtime/gecko-proxy-route.test.cjs';
const code = fs.readFileSync(path.join(root, assetPath), 'utf8');
const blocked = {type: 'socks', host: '127.0.0.1', port: 9, proxyDNS: true, failoverTimeout: 1};
const CHECK_NAMES = Object.freeze([
  "Registers exactly one production listener for every URL",
  "Explicitly authorized direct returns strict null",
  "Native guard denial after direct stays closed",
  "Verified internal HTTP route preserves every field",
  "Explicit external SOCKS route preserves every field",
  "Explicit HTTPS route preserves every field",
  "Authorized direct does not retain the preceding proxy route",
  "Missing native response stays closed",
  "Empty native response stays closed",
  "Malformed native JSON stays closed",
  "Native JSON null stays closed",
  "Native response without type stays closed",
  "Native response with null type stays closed",
  "Native response with numeric type stays closed",
  "Native response with boolean type stays closed",
  "Native JSON string stays closed",
  "Native JSON boolean stays closed",
  "Native JSON number stays closed",
  "Native JSON array stays closed",
  "Native JSON cannot inherit direct from __proto__",
  "Unserialized native object stays closed",
  "Other string-valued proxy types are not converted to null",
  "An empty string type is not converted to null",
  "Native bridge synchronous failure stays closed",
  "Native bridge promise rejection stays closed",
  "Pending native authorization never opens a request early",
  "Pending request uses the final native denial",
  "A later explicit direct authorization still returns strict null"
]);
const checks = [];
const nativeRequests = [];
const registrations = [];
let nativeReply = async () => {throw new Error('Native bridge not connected');};
let callback;

// Run the complete production extension module. The cookie/native-port stubs
// permit its ordinary startup; only the per-request native reply varies.
const browser = {
  proxy: {
    onRequest: {addListener(listener, filter) {registrations.push(filter); callback = listener;}},
    get settings() {throw new Error('This test forbids changing the global proxy settings');},
  },
  runtime: {
    sendNativeMessage(app, message) {
      nativeRequests.push({app, message: {...message}});
      return nativeReply(app, message);
    },
    connectNative() {return {postMessage() {}, onMessage: {addListener() {}}};},
  },
  cookies: {getAll: async () => [], onChanged: {addListener() {}}},
  storage: {local: {get: async () => ({}), set: async () => {}}},
};

vm.runInNewContext(code, {browser}, {filename: assetPath, timeout: 1000});
const request = {url: 'https://chatgpt.com/c/proxy-route-regression'};
const plain = value => value === undefined ? undefined : JSON.parse(JSON.stringify(value));
const check = (name, action) => {
  assert.equal(name, CHECK_NAMES[checks.length], 'Check name and order must match the source-owned contract');
  action();
  checks.push({name, pass: true});
};

async function replyCase(name, reply, expected) {
  nativeReply = async () => reply;
  const before = nativeRequests.length;
  const value = await callback(request);
  check(name, () => {
    assert.deepStrictEqual(plain(value), expected);
    assert.equal(nativeRequests.length, before + 1);
    assert.deepStrictEqual(nativeRequests.at(-1), {app: 'pocketroute', message: {kind: 'route', url: request.url}});
  });
}

async function main() {
  check('Registers exactly one production listener for every URL', () => {
    assert.equal(registrations.length, 1);
    assert.equal(typeof callback, 'function');
    assert.deepStrictEqual(plain(registrations[0]), {urls: ['<all_urls>']});
  });

  await replyCase('Explicitly authorized direct returns strict null', '{"type":"direct"}', null);
  await replyCase('Native guard denial after direct stays closed', JSON.stringify(blocked), blocked);
  const http = {type: 'http', host: '127.0.0.1', port: 8080, failoverTimeout: 1, connectionIsolationKey: 'synthetic-environment-2'};
  await replyCase('Verified internal HTTP route preserves every field', JSON.stringify(http), http);
  const socks = {type: 'socks', host: '127.0.0.1', port: 1080, proxyDNS: true, failoverTimeout: 1, connectionIsolationKey: 'synthetic-external-2'};
  await replyCase('Explicit external SOCKS route preserves every field', JSON.stringify(socks), socks);
  const https = {type: 'https', host: 'proxy.synthetic.invalid', port: 443, connectionIsolationKey: 'synthetic-external-3'};
  await replyCase('Explicit HTTPS route preserves every field', JSON.stringify(https), https);
  await replyCase('Authorized direct does not retain the preceding proxy route', '{"type":"direct"}', null);

  for (const [name, reply] of [
    ['Missing native response stays closed', undefined],
    ['Empty native response stays closed', ''],
    ['Malformed native JSON stays closed', '{"type":"direct"'],
    ['Native JSON null stays closed', 'null'],
    ['Native response without type stays closed', '{}'],
    ['Native response with null type stays closed', '{"type":null}'],
    ['Native response with numeric type stays closed', '{"type":0}'],
    ['Native response with boolean type stays closed', '{"type":true}'],
    ['Native JSON string stays closed', '"direct"'],
    ['Native JSON boolean stays closed', 'false'],
    ['Native JSON number stays closed', '1'],
    ['Native JSON array stays closed', '[{"type":"direct"}]'],
    ['Native JSON cannot inherit direct from __proto__', '{"__proto__":{"type":"direct"}}'],
    ['Unserialized native object stays closed', {type: 'direct'}],
  ]) await replyCase(name, reply, blocked);

  // Existing string-valued proxy replies keep the original callback semantics;
  // only exact "direct" is translated. SDK validation remains SDK-owned.
  await replyCase('Other string-valued proxy types are not converted to null', '{"type":"DIRECT"}', {type: 'DIRECT'});
  await replyCase('An empty string type is not converted to null', '{"type":""}', {type: ''});

  for (const [name, fail] of [
    ['Native bridge synchronous failure stays closed', () => {throw new Error('Disconnected native host');}],
    ['Native bridge promise rejection stays closed', () => Promise.reject(new Error('Disconnected native host'))],
  ]) {
    nativeReply = fail;
    const before = nativeRequests.length;
    const value = await callback(request);
    check(name, () => {
      assert.deepStrictEqual(plain(value), blocked);
      assert.equal(nativeRequests.length, before + 1);
    });
  }

  let resolveNative;
  nativeReply = () => new Promise(resolve => {resolveNative = resolve;});
  let settled = false;
  const held = callback(request).then(value => {settled = true; return value;});
  await Promise.resolve();
  check('Pending native authorization never opens a request early', () => assert.equal(settled, false));
  resolveNative(JSON.stringify(blocked));
  const heldValue = await held;
  check('Pending request uses the final native denial', () => assert.deepStrictEqual(plain(heldValue), blocked));
  await replyCase('A later explicit direct authorization still returns strict null', '{"type":"direct"}', null);
  assert.equal(CHECK_NAMES.length, 28, 'The source-owned contract must retain all 28 checks');
  assert.equal(checks.length, 28, 'All 28 checks must execute before a passed receipt is emitted');

  const sourceCommit = execFileSync('git', ['rev-parse', 'HEAD'], {cwd: root, encoding: 'utf8'}).trim();
  const sourceTree = execFileSync('git', ['rev-parse', 'HEAD^{tree}'], {cwd: root, encoding: 'utf8'}).trim();
  const sourceDirty = execFileSync('git', ['status', '--porcelain'], {cwd: root, encoding: 'utf8'}).trim().length > 0;
  const files = Object.fromEntries([assetPath, testPath].map(file => [file,
    crypto.createHash('sha256').update(fs.readFileSync(path.join(root, file))).digest('hex'),
  ]));
  const report = {
    schema: 1,
    status: 'passed',
    passed: checks.length,
    total: checks.length,
    executed: checks.length,
    sourceCommit,
    sourceTree,
    sourceDirty,
    files,
    actualAndroidExecution: false,
    actualGeckoExecution: false,
    actualProductionScriptExecution: true,
    scope: 'Node VM executing the complete production extension module with synthetic native bridge replies; no browser, VPN, sockets, or real network execution.',
    checks,
    nativeRequestCount: nativeRequests.length,
  };
  const args = process.argv.slice(2);
  if (args.length) {
    if (args.length !== 2 || args[0] !== '--receipt') throw new Error('Usage: node gecko-proxy-route.test.cjs [--receipt path]');
    const target = path.resolve(args[1]);
    fs.mkdirSync(path.dirname(target), {recursive: true});
    fs.writeFileSync(target, JSON.stringify(report, null, 2) + '\n');
  }
  process.stdout.write(JSON.stringify(report, null, 2) + '\n');
}

main().catch(error => {process.stderr.write(error.stack + '\n'); process.exitCode = 1;});
