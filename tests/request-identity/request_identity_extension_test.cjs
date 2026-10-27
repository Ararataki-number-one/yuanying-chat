'use strict';

// Adversarial extension-boundary controls in Node VM. Browser/WebRequest/window
// are fakes here; this does not establish actual Gecko or network protection.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const ROOT = path.resolve(__dirname, '../..');
const BACKGROUND = fs.readFileSync(path.join(ROOT, 'app/src/main/assets/gecko/request-identity-background.js'), 'utf8');
const AUDIT = fs.readFileSync(path.join(ROOT, 'app/src/main/assets/gecko/request-identity-audit.js'), 'utf8');
const BASE = 'https://audit.example/pocketchat-identity/v1/';
const NONCE = 'a'.repeat(32), OTHER = 'b'.repeat(32), THIRD = 'c'.repeat(32);
const PROTOCOL = 'pocketchat-request-identity-v1';
const plain = value => JSON.parse(JSON.stringify(value));

function matches(pattern, target) {
  const parts = /^(https?):\/\/([^/]+)(\/.*)$/.exec(pattern);
  assert.ok(parts, 'A browser URL pattern must be a scoped HTTPS host/path');
  assert.equal(parts[1], 'https'); assert.equal(parts[2].includes('*'), false, 'No wildcard/global host is needed');
  const url = new URL(target);
  const expression = '^' + parts[3].split('*').map(s => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('.*') + '$';
  return url.protocol === parts[1] + ':' && url.hostname === parts[2] && new RegExp(expression).test(url.pathname + url.search);
}

function background(failAt, fetchImpl) {
  let now = 1000, calls = 0, timerId = 0;
  const timers = new Map(), fetchCalls = [];
  const points = ['onBeforeRequest', 'onBeforeSendHeaders', 'onHeadersReceived'];
  const listeners = Object.fromEntries(points.map(name => [name, new Map()]));
  const browser = {webRequest: {}};
  for (const name of points) browser.webRequest[name] = {
    addListener(callback, filter, extra) {
      if (name === failAt) throw Error('Controlled listener registration failure');
      listeners[name].set(callback, {filter: plain(filter), extra: plain(extra)});
    },
    removeListener(callback) {listeners[name].delete(callback);},
    hasListener(callback) {return listeners[name].has(callback);}
  };
  class ClockDate extends Date {static now() {return now;}}
  const context = vm.createContext({browser, URL, Date: ClockDate, AbortController, TextDecoder, Uint8Array,
    setTimeout(callback, delay) {const id = ++timerId; timers.set(id, {at: now + delay, callback}); return id;},
    clearTimeout(id) {timers.delete(id);},
    fetch(url, options) {fetchCalls.push({url, options}); if (!fetchImpl) throw Error('No network in VM controls'); return fetchImpl(url, options);}});
  vm.runInContext(BACKGROUND, context, {filename: 'request-identity-background.js'});
  return {
    api: context.PocketRequestIdentityBackground,
    advance(value) {
      const until = now + value;
      for (;;) {
        const next = [...timers].sort((a, b) => a[1].at - b[1].at).find(([, timer]) => timer.at <= until);
        if (!next) break;
        timers.delete(next[0]); now = next[1].at; next[1].callback();
      }
      now = until;
    },
    timers: () => timers.size,
    fetchCalls,
    count: () => points.reduce((sum, name) => sum + listeners[name].size, 0),
    rules: () => points.flatMap(name => [...listeners[name].values()].map(value => ({name, ...value}))),
    calls: () => calls,
    request(name, details) {
      let result = {};
      for (const [callback, {filter}] of listeners[name]) {
        if (!filter.urls.some(pattern => matches(pattern, details.url))) continue;
        calls++; const value = plain(callback(details));
        if (value.cancel) return value;
        result = {...result, ...value};
      }
      return result;
    }
  };
}

function diagnostic(kind = 'document', nonce = NONCE, base = BASE) {
  return {url: base + kind + '?nonce=' + nonce + (kind === 'observe' ? '&source=worker' : ''), method: 'GET'};
}
function register(h, nonce = NONCE, base = BASE) {
  return plain(h.api.handle({action: 'register', nonce, endpoint: base}));
}

test('background defaults to zero hooks and leaves ordinary browser traffic alone', () => {
  const h = background(); assert.equal(h.count(), 0);
  assert.deepEqual(h.request('onBeforeRequest', {url: 'https://chatgpt.com/c/fixture', method: 'GET'}), {});
  assert.equal(h.calls(), 0);
  assert.equal(register(h).ok, true); assert.equal(h.count(), 3);
  assert.equal(h.rules().every(rule => rule.filter.urls.every(pattern => !matches(pattern, 'https://chatgpt.com/c/fixture'))), true);
  const calls = h.calls();
  assert.deepEqual(h.request('onBeforeSendHeaders', {url: 'https://chatgpt.com/c/fixture', method: 'GET', requestHeaders: [{name: 'Cookie', value: 'chat-session'}]}), {});
  assert.equal(h.calls(), calls, 'The browser URL filter, not a per-request JavaScript check, excludes ChatGPT');
});

test('an exact diagnostic registration strips credentials and preserves actual UA/language headers', () => {
  const h = background(), ack = register(h);
  assert.equal(ack.credentialFilter, true); assert.equal(ack.redirectsBlocked, true);
  const original = [{name: 'Cookie', value: 'not-for-detector'}, {name: 'AUTHORIZATION', value: 'not-for-detector'},
    {name: 'Proxy-Authorization', value: 'not-for-origin'}, {name: 'Referer', value: 'https://chatgpt.com/c/private'},
    {name: 'User-Agent', value: 'ObservedBrowser/157'}, {name: 'Accept-Language', value: 'ja-JP,en;q=0.5'}, {name: 'Accept', value: 'text/html'}];
  const kept = h.request('onBeforeSendHeaders', {...diagnostic(), requestHeaders: original});
  assert.deepEqual(kept.requestHeaders, original.slice(4)); assert.equal(original.length, 7);
  for (const kind of ['document', 'worker.js', 'observe', 'result'])
    assert.deepEqual(h.request('onBeforeRequest', diagnostic(kind)), {});
});

test('known diagnostic scope rejects absent/stale nonce, wrong methods, credentials and query pollution', () => {
  const h = background(); register(h);
  const invalid = [diagnostic('document', OTHER), {...diagnostic(), method: 'POST'},
    {...diagnostic(), url: BASE + 'document'}, {...diagnostic(), url: diagnostic().url + '&nonce=' + OTHER},
    {...diagnostic(), url: diagnostic().url + '&unexpected=yes'}, {...diagnostic(), url: diagnostic().url + '#fragment'},
    {...diagnostic(), url: diagnostic().url.replace('https://', 'https://name:password@')},
    {...diagnostic(), url: BASE + 'observe?nonce=' + NONCE},
    {...diagnostic(), url: BASE + 'observe?nonce=' + NONCE + '&source=document'},
    {...diagnostic(), url: diagnostic().url + '&source=worker'}];
  for (const details of invalid) {
    assert.equal(h.request('onBeforeRequest', details).cancel, true, details.url);
    assert.equal(h.request('onBeforeSendHeaders', {...details, requestHeaders: [{name: 'Cookie', value: 'sentinel'}]}).cancel, true);
  }
});

test('invalid endpoint registrations install no hooks and never claim a filter acknowledgement', () => {
  const h = background();
  for (const endpoint of ['http://audit.example/pocketchat-identity/v1/', 'https://name:password@audit.example/pocketchat-identity/v1/',
    'https://audit.example/pocketchat-identity/v1/?secret=value', 'https://audit.example/pocketchat-identity/v1/#fragment',
    'https://audit.example/other/', 'not a URL']) assert.equal(register(h, NONCE, endpoint).ok, false);
  assert.equal(plain(h.api.handle({action: 'register', nonce: 'invalid', endpoint: BASE})).ok, false);
  assert.equal(h.count(), 0);
});

test('nonce bindings cannot be moved between detector origins or ports', () => {
  const h = background(), base2 = 'https://second.example/pocketchat-identity/v1/';
  assert.equal(register(h).ok, true); assert.equal(register(h, OTHER, base2).ok, true);
  assert.equal(register(h, NONCE, base2).ok, false, 'An existing nonce retains its original origin binding');
  assert.equal(h.request('onBeforeRequest', diagnostic('document', NONCE, base2)).cancel, true);
  assert.deepEqual(h.request('onBeforeRequest', diagnostic()), {});
  const p = background(), portBase = 'https://audit.example:9443/pocketchat-identity/v1/';
  assert.equal(register(p, NONCE, portBase).ok, true);
  assert.equal(p.request('onBeforeRequest', diagnostic()).cancel, true, 'The host-level browser match must still enforce the exact registered port');
});

test('all 3xx responses are stopped at the registered origin before a redirect can follow', () => {
  const h = background(); register(h);
  for (const statusCode of [300, 301, 302, 303, 304, 305, 306, 307, 308, 399])
    assert.equal(h.request('onHeadersReceived', {...diagnostic(), statusCode, responseHeaders: [{name: 'Location', value: 'https://other.example/'}]}).cancel, true);
  for (const statusCode of [200, 204, 400, 403, 500]) assert.deepEqual(h.request('onHeadersReceived', {...diagnostic(), statusCode}), {});
});

test('cancel, clear and expiry retain closed diagnostic tombstones without touching ordinary URLs', () => {
  const h = background(); register(h);
  assert.equal(plain(h.api.handle({action: 'cancel', nonce: NONCE})).ok, true);
  for (const kind of ['document', 'worker.js', 'observe', 'result']) assert.equal(h.request('onBeforeRequest', diagnostic(kind)).cancel, true);
  assert.equal(register(h, OTHER).ok, true); assert.equal(h.count(), 3, 'Reuse one host/path hook group');
  h.advance(30000); assert.equal(h.request('onBeforeRequest', diagnostic('result', OTHER)).cancel, true);
  assert.equal(register(h, THIRD).ok, true); h.api.clear();
  assert.equal(h.request('onBeforeRequest', diagnostic('worker.js', THIRD)).cancel, true); assert.equal(h.count(), 3);
  const before = h.calls(); h.request('onBeforeRequest', {url: 'https://audit.example/ordinary', method: 'GET'});
  assert.equal(h.calls(), before);
});

test('partial WebRequest installation is rolled back and cannot acknowledge protection', () => {
  for (const point of ['onBeforeRequest', 'onBeforeSendHeaders', 'onHeadersReceived']) {
    const h = background(point); assert.equal(h.count(), 0);
    assert.equal(register(h).ok, false); assert.equal(h.count(), 0, point);
  }
});

test('diagnostic scopes and host groups stay bounded', () => {
  const h = background(); register(h); register(h, OTHER);
  assert.equal(register(h, THIRD).ok, false);
  h.api.handle({action: 'cancel', nonce: NONCE}); assert.equal(register(h, THIRD).ok, true);
  const bases = background();
  for (let index = 0; index < 4; index++) {
    const nonce = String(index + 1).repeat(32), base = `https://audit${index}.example/pocketchat-identity/v1/`;
    assert.equal(register(bases, nonce, base).ok, true); bases.api.handle({action: 'cancel', nonce});
  }
  assert.equal(register(bases, NONCE, 'https://fifth.example/pocketchat-identity/v1/').ok, false);
  assert.equal(bases.count(), 12);
});

const deferred = () => {let resolve, reject; const promise = new Promise((yes, no) => {resolve = yes; reject = no;}); return {promise, resolve, reject};};
function streamed(status, value, split) {
  const bytes = Buffer.isBuffer(value) ? value : Buffer.from(JSON.stringify(value));
  const chunks = split ? [bytes.subarray(0, split), bytes.subarray(split)] : [bytes];
  const stats = {reads: 0, cancelled: 0, released: 0}; let index = 0;
  return {status, stats, body: {getReader: () => ({
    async read() {stats.reads++; return index < chunks.length ? {done: false, value: chunks[index++]} : {done: true};},
    async cancel() {stats.cancelled++;}, releaseLock() {stats.released++;}
  })}};
}
const control = (h, nonce = NONCE, endpoint = BASE) => h.api.handle({action: 'evidence', nonce, endpoint});

test('independent evidence fetch uses only the exact credentialless protected control URL', async () => {
  const value = {schema: 1, nonce: NONCE, protocol: PROTOCOL, status: 'ready'};
  const response = streamed(200, value, 5), h = background(null, async () => response); register(h);
  const result = plain(await control(h));
  assert.equal(result.ok, true); assert.equal(result.source, 'extension-background-control'); assert.equal(result.httpStatus, 200);
  assert.deepEqual(result.server, value); assert.equal(h.fetchCalls.length, 1);
  const {url, options} = h.fetchCalls[0]; assert.equal(url, BASE + 'result?nonce=' + NONCE);
  assert.equal(options.credentials, 'omit'); assert.equal(options.referrerPolicy, 'no-referrer');
  assert.equal(options.redirect, 'error'); assert.equal(options.cache, 'no-store');
  assert.ok(options.signal instanceof AbortSignal); assert.equal(h.timers(), 0); assert.equal(response.stats.released, 1);
  const cleaned = h.request('onBeforeSendHeaders', {...diagnostic('result'), requestHeaders: [{name: 'Origin', value: 'moz-extension://private-origin'}, {name: 'User-Agent', value: 'Observed/157'}]});
  assert.deepEqual(cleaned.requestHeaders, [{name: 'User-Agent', value: 'Observed/157'}]);
});

test('control evidence is bounded by actual streamed bytes rather than unbounded text or Content-Length', async () => {
  const exact = {status: 'ready', padding: ''}; exact.padding = 'x'.repeat(32000 - Buffer.byteLength(JSON.stringify(exact)));
  const accepted = streamed(200, exact, 16000), pass = background(null, async () => accepted); register(pass);
  assert.equal(plain(await control(pass)).ok, true); assert.equal(accepted.stats.cancelled, 0);
  const tooLarge = streamed(200, Buffer.concat([Buffer.from(JSON.stringify(exact)), Buffer.from(' ')]), 16000);
  const reject = background(null, async () => tooLarge); register(reject);
  const result = plain(await control(reject)); assert.equal(result.ok, false); assert.equal(result.server, undefined);
  assert.equal(tooLarge.stats.cancelled, 1); assert.equal(tooLarge.stats.released, 1); assert.equal(reject.timers(), 0);
  let unboundedReads = 0;
  const absent = background(null, async () => ({status: 200, body: null, async text() {unboundedReads++; return '{}';}})); register(absent);
  assert.equal(plain(await control(absent)).ok, false); assert.equal(unboundedReads, 0);
  for (const bytes of [Buffer.from([0xff]), Buffer.from('not JSON')]) {
    const malformed = background(null, async () => streamed(200, bytes)); register(malformed);
    assert.equal(plain(await control(malformed)).ok, false);
  }
});

test('control evidence cancels after three seconds both before headers and while reading a body', async () => {
  const pendingFetch = background(null, (_, options) => new Promise((resolve, reject) => options.signal.addEventListener('abort', () => reject(Error('aborted')), {once: true}))); register(pendingFetch);
  const first = control(pendingFetch); pendingFetch.advance(2999); await pending(first); pendingFetch.advance(1);
  assert.equal(plain(await first).error, 'evidence-cancelled'); assert.equal(pendingFetch.timers(), 0);
  let bodyReads = 0, released = 0;
  const pendingBody = background(null, async (_, options) => ({status: 200, body: {getReader: () => ({
    read() {bodyReads++; return new Promise((resolve, reject) => options.signal.addEventListener('abort', () => reject(Error('aborted')), {once: true}));},
    releaseLock() {released++;}
  })}})); register(pendingBody);
  const second = control(pendingBody);
  for (let i = 0; i < 8 && !bodyReads; i++) await Promise.resolve();
  assert.equal(bodyReads, 1); pendingBody.advance(3000);
  assert.equal(plain(await second).error, 'evidence-cancelled'); assert.equal(released, 1); assert.equal(pendingBody.timers(), 0);
});

test('one nonce has one in-flight control request and re-registration cannot unlock it', async () => {
  const later = deferred(); let calls = 0;
  const h = background(null, () => ++calls === 1 ? later.promise : Promise.resolve(streamed(200, {nonce: NONCE, status: 'ready'}))); register(h);
  const first = control(h); assert.equal(register(h).ok, true);
  assert.equal(plain(await control(h)).error, 'evidence-already-in-flight'); assert.equal(h.fetchCalls.length, 1);
  later.resolve(streamed(200, {nonce: NONCE, status: 'ready'})); assert.equal(plain(await first).ok, true);
  assert.equal(plain(await control(h)).ok, true); assert.equal(h.fetchCalls.length, 2);
});

test('cancel and clear reject late transport responses without clearing the next scope lock', async () => {
  for (const clear of [false, true]) {
    const old = deferred(), next = deferred(); let call = 0;
    const h = background(null, () => (++call === 1 ? old.promise : next.promise)); register(h);
    const previous = control(h);
    if (clear) h.api.clear(); else h.api.handle({action: 'cancel', nonce: NONCE});
    assert.equal(h.fetchCalls[0].options.signal.aborted, true);
    register(h); const current = control(h);
    old.resolve(streamed(200, {nonce: NONCE, status: 'ready'})); assert.equal(plain(await previous).ok, false);
    assert.equal(plain(await control(h)).error, 'evidence-already-in-flight'); assert.equal(h.fetchCalls.length, 2);
    next.resolve(streamed(200, {nonce: NONCE, status: 'ready'})); assert.equal(plain(await current).ok, true);
    assert.equal(h.timers(), 0);
  }
});

test('a 202 server response keeps the same scope usable for a later completed record', async () => {
  const responses = [streamed(202, {nonce: NONCE, status: 'pending'}), streamed(200, {nonce: NONCE, status: 'ready'})];
  const h = background(null, async () => responses.shift()); register(h);
  const first = plain(await control(h)); assert.equal(first.ok, true); assert.equal(first.httpStatus, 202); assert.equal(first.server.status, 'pending');
  assert.deepEqual(h.request('onBeforeRequest', diagnostic('worker.js')), {});
  const second = plain(await control(h)); assert.equal(second.ok, true); assert.equal(second.server.status, 'ready'); assert.equal(h.fetchCalls.length, 2);
});

test('unregistered, cancelled, expired and wrong-origin evidence actions cannot start a fetch', async () => {
  const h = background(null, async () => streamed(200, {}));
  assert.equal(plain(await control(h)).ok, false); register(h);
  assert.equal(plain(await control(h, NONCE, 'https://other.example/pocketchat-identity/v1/')).ok, false);
  h.api.handle({action: 'cancel', nonce: NONCE}); assert.equal(plain(await control(h)).ok, false);
  register(h); h.advance(30000); assert.equal(plain(await control(h)).ok, false); assert.equal(h.fetchCalls.length, 0);
});

test('control response failures stay explicit and do not silently follow redirects', async () => {
  for (const status of [200, 202, 403, 409]) {
    const h = background(null, async () => streamed(status, {nonce: NONCE, status: status === 403 ? 'rejected' : 'pending'})); register(h);
    const value = plain(await control(h)); assert.equal(value.ok, true); assert.equal(value.httpStatus, status);
  }
  for (const status of [301, 302, 307, 308, 401, 500]) {
    const h = background(null, async () => streamed(status, {})); register(h);
    assert.equal(plain(await control(h)).ok, false); assert.equal(h.fetchCalls.length, 1); assert.equal(h.fetchCalls[0].options.redirect, 'error');
  }
});

function page({href = BASE + 'document?nonce=' + NONCE, framed = false} = {}) {
  let time = 0, serial = 0;
  const timers = new Map(), listeners = new Set(), posted = [];
  const location = new URL(href);
  const window = {addEventListener(name, callback) {assert.equal(name, 'message'); listeners.add(callback);},
    removeEventListener(name, callback) {assert.equal(name, 'message'); listeners.delete(callback);},
    postMessage(value, target) {posted.push({value: plain(value), target});}};
  window.top = framed ? {} : window;
  const context = vm.createContext({window, location, URL, setTimeout(callback, delay) {const id = ++serial; timers.set(id, {at: time + delay, callback}); return id;}, clearTimeout(id) {timers.delete(id);}});
  vm.runInContext(AUDIT, context, {filename: 'request-identity-audit.js'});
  return {api: context.PocketRequestIdentityAudit, window, location, posted,
    listeners: () => listeners.size, timers: () => timers.size,
    emit(value, override = {}) {for (const callback of [...listeners]) callback({source: window, origin: location.origin, isTrusted: true, data: value, ...override});},
    advance(ms) {time += ms; for (const [id, timer] of [...timers]) if (timer.at <= time) {timers.delete(id); timer.callback();}}};
}
const signal = () => ({ua: 'ObservedBrowser/157', language: 'ja-JP', languages: ['ja-JP', 'en-US']});
const complete = (nonce = NONCE) => ({pocketRequestIdentity: nonce, schema: 1, protocol: PROTOCOL, nonce,
  status: 'complete', source: 'controlled-top-level-document', document: signal(), worker: signal()});
async function pending(promise) {let settled = false; promise.then(() => {settled = true;}); await Promise.resolve(); assert.equal(settled, false);}

test('page collection requires the exact top-level document and a valid endpoint', async () => {
  for (const [options, configuration] of [[{}, {endpoint: BASE, nonce: 'invalid'}],
    [{href: BASE + 'document?nonce=' + OTHER}, {endpoint: BASE, nonce: NONCE}],
    [{framed: true}, {endpoint: BASE, nonce: NONCE}],
    [{}, {endpoint: BASE.replace('https://', 'https://user:password@'), nonce: NONCE}],
    [{}, {endpoint: 'https://audit.example/other/', nonce: NONCE}]]) {
    const h = page(options), value = plain(await h.api.run(configuration, []));
    assert.equal(value.status, 'failed'); assert.equal(h.posted.length, 0); assert.equal(h.listeners(), 0); assert.equal(h.timers(), 0);
  }
});

test('late page collection requests its existing result and rejects wrong provenance messages', async () => {
  const h = page(), stops = [], promise = h.api.run({endpoint: BASE, nonce: NONCE}, stops);
  assert.deepEqual(h.posted, [{value: {pocketRequestIdentityCollect: NONCE}, target: 'https://audit.example'}]);
  assert.equal(h.listeners(), 1); assert.equal(h.timers(), 1); assert.equal(stops.length, 1);
  for (const override of [{source: {}}, {origin: 'https://other.example'}, {isTrusted: false}]) {h.emit(complete(), override); await pending(promise);}
  for (const value of [complete(OTHER), {...complete(), protocol: 'different-protocol'}, {...complete(), source: 'content-script'}, {...complete(), schema: 2}]) {
    h.emit(value); await pending(promise);
  }
  const value = complete(); value.document.cookie = 'must-not-copy'; value.server = {headers: {Cookie: 'must-not-copy'}};
  h.emit(value); value.document.languages[0] = 'changed-after-message';
  const result = plain(await promise);
  assert.equal(result.status, 'complete'); assert.equal(result.source, 'controlled-top-level-document');
  assert.deepEqual(result.document.languages, ['ja-JP', 'en-US']); assert.equal(result.document.cookie, undefined); assert.equal(result.server, undefined);
  assert.equal(h.listeners(), 0); assert.equal(h.timers(), 0);
});

test('incomplete or oversized JS samples fail without propagating arbitrary page data', async () => {
  const invalid = [{...signal(), ua: ''}, {...signal(), ua: 'x'.repeat(2049)}, {...signal(), language: 42},
    {...signal(), languages: []}, {...signal(), languages: ['x'.repeat(129)]}, {...signal(), languages: Array(9).fill('en-US')}];
  for (const worker of invalid) {
    const h = page(), promise = h.api.run({endpoint: BASE, nonce: NONCE}, []);
    h.emit({...complete(), worker}); const result = plain(await promise);
    assert.equal(result.status, 'failed'); assert.equal(result.error, 'incomplete-javascript-observation');
    assert.equal(h.listeners(), 0); assert.equal(h.timers(), 0);
  }
  const h = page(), promise = h.api.run({endpoint: BASE, nonce: NONCE}, []);
  h.emit({...complete(), status: 'failed', error: 'untrusted-page-secret'});
  assert.equal(plain(await promise).error, 'controlled-page-or-worker-unavailable');
});

test('collection has a six-second bound, cancellation cleanup, and accepts at most one result', async () => {
  const timeout = page(), waiting = timeout.api.run({endpoint: BASE, nonce: NONCE}, []);
  timeout.advance(5999); await pending(waiting); timeout.advance(1);
  assert.equal(plain(await waiting).error, 'controlled-page-observation-timeout'); assert.equal(timeout.listeners(), 0); assert.equal(timeout.timers(), 0);
  const cancelled = page(), stops = [], promise = cancelled.api.run({endpoint: BASE, nonce: NONCE}, stops);
  let completions = 0; promise.then(() => completions++); stops[0](); cancelled.emit(complete()); cancelled.advance(6000);
  assert.equal(plain(await promise).error, 'cancelled'); await Promise.resolve(); assert.equal(completions, 1);
  assert.equal(cancelled.listeners(), 0); assert.equal(cancelled.timers(), 0);
  const done = page(), stop = [], success = done.api.run({endpoint: BASE, nonce: NONCE}, stop);
  done.emit(complete()); done.emit({...complete(), status: 'failed'}); stop[0](); done.advance(6000);
  assert.equal(plain(await success).status, 'complete'); assert.equal(done.listeners(), 0); assert.equal(done.timers(), 0);
});

test('a previous cancelled nonce cannot satisfy the next document collection', async () => {
  const h = page(), stops = [], first = h.api.run({endpoint: BASE, nonce: NONCE}, stops);
  stops[0](); assert.equal(plain(await first).error, 'cancelled');
  h.location.href = BASE + 'document?nonce=' + OTHER;
  const second = h.api.run({endpoint: BASE, nonce: OTHER}, []); h.emit(complete()); await pending(second);
  h.emit(complete(OTHER)); assert.equal(plain(await second).nonce, OTHER); assert.equal(h.listeners(), 0);
});
