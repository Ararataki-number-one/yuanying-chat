'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

// Runs the production isolated-world bridge with a small DOM/port harness. This
// verifies protocol boundaries, not Gecko isolation, CSP behavior or real pages.
const source = fs.readFileSync(path.join(__dirname, '../../app/src/main/assets/gecko/content.js'), 'utf8');
class Target {
  constructor() { this.listeners = new Map(); }
  addEventListener(type, receive) {
    if (!this.listeners.has(type)) this.listeners.set(type, new Set());
    this.listeners.get(type).add(receive);
  }
  removeEventListener(type, receive) { this.listeners.get(type)?.delete(receive); }
  dispatchEvent(event) {
    for (const receive of [...(this.listeners.get(event.type) || [])]) receive(event);
    return true;
  }
}
function harness() {
  const window = new Target(), document = new Target();
  const messages = [], scripts = [], fetched = [], timers = new Map();
  let nativeReceive, serial = 0, nonceSerial = 0, evaluated = 0;
  document.readyState = 'loading';
  document.body = null;
  document.documentElement = {clientWidth: 360, appendChild: script => scripts.push(script)};
  document.createElement = tag => ({tag, attributes: {},
    setAttribute(key, value) { this.attributes[key] = value; },
    remove() { this.removed = true; }});
  const context = vm.createContext({window, document,
    browser: {runtime: {connectNative(name) {
      assert.equal(name, 'pocketpage');
      return {postMessage: value => messages.push(value), onMessage: {addListener(receive) { nativeReceive = receive; }}};
    }, getURL: name => `moz-extension://test/${name}`}},
    crypto: {getRandomValues(values) { const sequence = ++nonceSerial; values.forEach((_, index) => { values[index] = sequence * 16 + index; }); return values; }},
    navigator: {userAgent: 'Mozilla/5.0 Firefox/157.0', appVersion: '5.0', platform: 'Linux armv8l', language: 'zh-CN', languages: ['zh-CN'], hardwareConcurrency: 8},
    location: {origin: 'https://chatgpt.com', href: 'https://chatgpt.com/'},
    visualViewport: {scale: 1, addEventListener() {}}, devicePixelRatio: 2,
    MutationObserver: class { observe() {} disconnect() {} },
    CustomEvent: class { constructor(type, options) { this.type = type; this.detail = options.detail; } },
    setTimeout(callback) { const id = ++serial; timers.set(id, callback); return id; },
    clearTimeout(id) { timers.delete(id); }, requestAnimationFrame() { return ++serial; }, cancelAnimationFrame() {},
    AbortController,
    fetch: async (url, options) => { fetched.push({url, options}); return {ok: true, text: async () => JSON.stringify({ip: '203.0.113.9'})}; },
    eval() { evaluated++; throw new Error('Unexpected privileged evaluation'); },
  });
  vm.runInContext(source, context, {filename: 'content.js'});
  return {window, messages, scripts, fetched,
    get evaluated() { return evaluated; },
    send: message => nativeReceive(message),
    event: detail => window.dispatchEvent({type: 'pocket-audit-observation', detail}),
    result: () => messages.filter(message => message.kind === 'auditResult'),
    nonce: () => JSON.parse(scripts.at(-1).attributes['data-pocket-audit']).nonce,
  };
}
async function flush() { for (let i = 0; i < 12; i++) await Promise.resolve(); }
function observed(nonce, extra = {}) {
  return JSON.stringify({nonce, provenance: 'page-main-world', parent: {ua: 'Mozilla/5.0 Firefox/157.0'},
    frame: {ua: 'Mozilla/5.0 Firefox/157.0'}, worker: {ua: 'Mozilla/5.0 Firefox/157.0'},
    coverage: {crossOriginFrame: false, sharedWorker: false, serviceWorker: false}, ...extra});
}

test('page events cannot evaluate code, request URLs or fabricate a native callback', async () => {
  const bridge = harness();
  bridge.event(JSON.stringify({kind: 'evaluate', id: 11, code: 'steal()', url: 'https://untrusted.test/'}));
  await flush();
  assert.equal(bridge.evaluated, 0);
  assert.equal(bridge.fetched.length, 0);
  assert.equal(bridge.result().length, 0);
});

test('wrong nonce and oversized events are ignored; current public signals remain untrusted evidence', async () => {
  const bridge = harness();
  bridge.send({kind: 'audit', id: 1, configuration: {id: 'run-1', network: false}});
  bridge.event(observed('incorrect'));
  bridge.event('x'.repeat(60001));
  await flush();
  assert.equal(bridge.result().length, 0);
  bridge.event(observed(bridge.nonce(), {kind: 'evaluate', code: 'steal()', url: 'https://untrusted.test/'}));
  await flush();
  assert.equal(bridge.result().length, 1);
  const result = JSON.parse(bridge.result()[0].result);
  assert.equal(result.id, 'run-1');
  assert.equal(result.provenance, 'page-main-world');
  assert.match(result.mainWorld.authenticity, /forged/);
  assert.equal(result.code, undefined);
  assert.equal(bridge.evaluated, 0);
  assert.equal(bridge.fetched.length, 0);
});

test('old observations cannot complete a new audit, and cancellation prevents late completion', async () => {
  const bridge = harness();
  bridge.send({kind: 'audit', id: 1, configuration: {id: 'old', network: false}});
  const old = bridge.nonce();
  bridge.send({kind: 'audit', id: 2, configuration: {id: 'new', network: false}});
  bridge.event(observed(old));
  await flush();
  assert.equal(bridge.result().length, 0);
  const current = bridge.nonce();
  bridge.send({kind: 'auditCancel'});
  bridge.event(observed(current));
  await flush();
  assert.equal(bridge.result().length, 0);
});

test('deep attacker fields and non-scalar signals never cross the native JSON boundary', async () => {
  const bridge = harness();
  bridge.send({kind: 'audit', id: 5, configuration: {id: 'bounded', network: false}});
  const deep = '['.repeat(8000) + '0' + ']'.repeat(8000);
  bridge.event('{"nonce":' + JSON.stringify(bridge.nonce()) + ',"provenance":"page-main-world",' +
    '"parent":{"ua":"Mozilla/5.0 Firefox/157.0","extra":' + deep +
    ',"cpu":{"untrusted":true},"language":{"untrusted":true},"languages":["zh-CN",{"bad":true}],' +
    '"screen":{"width":360,"height":{"untrusted":true}},"renderer":' + deep + '},' +
    '"coverage":{"crossOriginFrame":true,"serviceWorker":true}}');
  await flush();
  assert.equal(bridge.result().length, 1);
  const result = JSON.parse(bridge.result()[0].result);
  assert.equal(result.parent.extra, undefined);
  assert.equal(result.parent.cpu, undefined);
  assert.equal(result.parent.language, undefined);
  assert.equal(result.parent.renderer, undefined);
  assert.deepEqual(result.parent.languages, ['zh-CN']);
  assert.deepEqual(result.parent.screen, {width: 360});
  assert.equal(result.coverage.crossOriginFrame, false);
  assert.equal(result.coverage.serviceWorker, false);
  assert.ok(bridge.result()[0].result.length < 3000);
});

test('script rejection is reported as isolated-world fallback with no main-world coverage', async () => {
  const bridge = harness();
  bridge.send({kind: 'audit', id: 3, configuration: {id: 'blocked', network: false}});
  bridge.scripts.at(-1).onerror();
  await flush();
  const result = JSON.parse(bridge.result()[0].result);
  assert.equal(result.provenance, 'extension-isolated-world-fallback');
  assert.equal(result.mainWorld.observed, false);
  assert.match(result.frame.error, /No page-main-world/);
  assert.equal(result.coverage.crossOriginFrame, false);
});

test('network audit uses only static endpoints and strips credentials and referrer', async () => {
  const bridge = harness();
  bridge.send({kind: 'audit', id: 4, configuration: {id: 'network', network: true,
    ipv4: 'https://untrusted.test/', headers: 'http://127.0.0.1/'}});
  bridge.event(observed(bridge.nonce(), {url: 'https://untrusted.test/'}));
  await flush();
  assert.deepEqual(bridge.fetched.map(request => request.url), [
    'https://api.ipify.org/?format=json', 'https://api6.ipify.org/?format=json', 'https://httpbin.org/headers']);
  for (const {options} of bridge.fetched) {
    assert.equal(options.credentials, 'omit');
    assert.equal(options.referrerPolicy, 'no-referrer');
  }
  assert.equal(bridge.result().length, 1);
  assert.equal(bridge.evaluated, 0);
});
