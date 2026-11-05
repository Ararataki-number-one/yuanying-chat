'use strict';
// Controlled VM browser/Worker interfaces only. This is not Android/Gecko proof.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const ROOT = path.resolve(__dirname, '..');
const SOURCE = fs.readFileSync(path.join(ROOT, 'tests/gecko/assets/gecko-environment-policy-page.js'), 'utf8');
const SERVER = fs.readFileSync(path.join(ROOT, 'tools/browser/newworker_fixture_server.py'), 'utf8');
const TIMEZONE_SOURCE = JSON.parse(SERVER.match(/^TIMEZONE_SOURCE=(".*")$/m)[1]);
const CONFIG = {runNonce: 'a'.repeat(32), sourceCommit: 'b'.repeat(40),
  origins: ['https://fp-a.pocketchat.test', 'https://fp-b.pocketchat.test']};
const UUID = '11111111-1111-4111-8111-111111111111';
const clone = value => JSON.parse(JSON.stringify(value));
const replyZone = {timeZone: 'America/New_York',
  january: {offsetMinutes: 300, year: 2026, month: 1, day: 15, hour: 7, minute: 0},
  july: {offsetMinutes: 240, year: 2026, month: 7, day: 15, hour: 8, minute: 0}};
const settle = async () => { for (let i = 0; i < 5; i++) await new Promise(resolve => setImmediate(resolve)); };

function protectNativeReads(context) {
  // A script attempting to replace or rewrite these native VM values fails.
  vm.runInContext(`Object.freeze(Date.prototype);Object.freeze(Date);
    Object.freeze(Intl.DateTimeFormat.prototype);Object.freeze(Intl.DateTimeFormat);Object.freeze(Intl);
    Object.defineProperty(globalThis,'Date',{value:Date,writable:false,configurable:false});
    Object.defineProperty(globalThis,'Intl',{value:Intl,writable:false,configurable:false});`, context);
  return vm.runInContext('({Date,Intl,dateHours:Date.prototype.getHours,format:Intl.DateTimeFormat})', context);
}

function fixture(options = {}) {
  const origin = options.origin || CONFIG.origins[0], phase = options.phase || 'gecko-system';
  const calls = {dedicated: [], shared: [], service: [], fetches: [], terminated: 0,
    sharedClosed: 0, channelClosed: 0, revoked: [], blobSources: [], pending: [],
    readyReads: 0, unregisters: 0, framePosts: [], snapshots: []};
  const timers = new Map(), events = new Map(), documentEvents = new Map(), blobUrls = new Map(), attributes = new Map();
  let timerSequence = 0, blobSequence = 0;
  const dispatch = callback => options.holdResponses ? calls.pending.push(callback) : queueMicrotask(callback);
  const mode = realm => (options.modes || {})[realm];
  const response = realm => ({executed: true, networkAllowed: options.networkAllowed !== false,
    nativeUserAgent: 'native-worker/' + realm, nativeTimeZone: clone(replyZone), sourceRole: realm});
  class BlobBoundary { constructor(parts, settings) { this.text = parts.join(''); this.type = settings.type; } }
  class UrlBoundary extends URL {
    static createObjectURL(blob) { const url = 'blob:' + origin + '/controlled-' + (++blobSequence); blobUrls.set(url, blob.text); calls.blobSources.push(blob.text); return url; }
    static revokeObjectURL(url) { calls.revoked.push(url); blobUrls.delete(url); }
  }
  class WorkerBoundary {
    constructor(url, settings) {
      this.url = url; this.settings = settings;
      this.realm = String(url).startsWith('blob:') ? 'dedicated-blob' : new URL(url, origin).searchParams.get('realm');
      calls.dedicated.push(this);
      if (mode(this.realm) === 'constructor') { const error = Error('Controlled constructor failure'); error.name = 'SecurityError'; throw error; }
      if (this.realm === 'dedicated-blob') {
        this.scope = vm.createContext({navigator: Object.freeze({userAgent: 'native-blob-UA'}),
          fetch: async (address, settings) => { calls.fetches.push({address, settings}); return {ok: true, text: async () => 'worker-network-synthetic-v1'}; }});
        this.scope.self = this.scope;
        this.scope.postMessage = value => dispatch(() => this.onmessage({data: value}));
        this.before = protectNativeReads(this.scope);
        vm.runInContext(blobUrls.get(url), this.scope);
      }
    }
    postMessage() {
      if (mode(this.realm) === 'silent') return;
      dispatch(() => {
        if (mode(this.realm) === 'error') { this.onerror({message: 'controlled native worker error'}); return; }
        if (this.scope) { Promise.resolve(this.scope.onmessage()).catch(error => this.onerror(error)); return; }
        const value = response(this.realm);
        if (mode(this.realm) === 'wrong-role') value.sourceRole = 'unrelated-worker';
        this.onmessage({data: value});
      });
    }
    terminate() { this.terminated = true; calls.terminated++; }
  }
  class SharedBoundary {
    constructor(url, settings) {
      calls.shared.push({url, settings});
      if (mode('shared-worker') === 'constructor') throw Error('Controlled shared constructor failure');
      const owner = this;
      this.port = {started: false, start() { this.started = true; },
        postMessage() { if (mode('shared-worker') === 'silent') return; dispatch(() => {
          if (mode('shared-worker') === 'error') owner.onerror({message: 'controlled shared failure'});
          else this.onmessage({data: response('shared-worker')});
        }); }, close() { calls.sharedClosed++; }};
    }
  }
  class PortBoundary {
    constructor() { this.closed = false; }
    start() { this.started = true; }
    postMessage(value) { dispatch(() => { if (!this.peer.closed && this.peer.onmessage) this.peer.onmessage({data: value}); }); }
    close() { this.closed = true; calls.channelClosed++; }
  }
  class ChannelBoundary {
    constructor() { this.port1 = new PortBoundary(); this.port2 = new PortBoundary(); this.port1.peer = this.port2; this.port2.peer = this.port1; }
  }
  const active = {state: options.serviceInstalling ? 'installing' : 'activated', listeners: new Set(),
    addEventListener(type, listener) { assert.equal(type, 'statechange'); this.listeners.add(listener); },
    removeEventListener(type, listener) { this.listeners.delete(listener); },
    postMessage(value, ports) { calls.service.push({action: 'message', value, ports});
      if (mode('service-worker') === 'error') throw Error('Controlled service message failure');
      if (mode('service-worker') !== 'silent') ports[0].postMessage(response('service-worker')); }};
  const registration = {active: options.serviceInstalling ? null : active,
    installing: options.serviceInstalling ? active : null, waiting: null,
    unregister() { calls.unregisters++; throw Error('Unexpected unregister boundary'); }};
  const manager = {register(address, settings) { calls.service.push({action: 'register', address, settings});
    if (mode('service-worker') === 'constructor') return Promise.reject(Error('Controlled register failure'));
    return Promise.resolve(registration); }};
  Object.defineProperty(manager, 'ready', {get() { calls.readyReads++; throw Error('Outside-scope document must not await serviceWorker.ready'); }});
  const navigator = {userAgent: options.userAgent || 'native-document-UA'};
  if (options.serviceAvailable !== false) navigator.serviceWorker = manager;
  Object.freeze(navigator);
  const firstScript = {};
  const frames = CONFIG.origins.map(value => ({src: value + '/env-frame?phase=' + phase, contentWindow: {origin: value}}));
  const document = {currentScript: options.notFirst ? {} : firstScript, scripts: [firstScript],
    readyState: options.readyState || 'loading', referrer: options.referrer || CONFIG.origins[0] + '/env-policy?phase=' + phase,
    documentElement: {setAttribute(name, value) { assert.equal(name, 'data-gecko-environment-policy');
      attributes.set(name, value); calls.snapshots.push({value, fetches: calls.fetches.length, workers: calls.dedicated.length}); },
    getAttribute(name) { return attributes.get(name) || null; }},
    addEventListener(type, listener) { if (!documentEvents.has(type)) documentEvents.set(type, []); documentEvents.get(type).push(listener); },
    dispatchEvent(event) { for (const listener of documentEvents.get(event.type) || []) listener(event); return true; },
    querySelectorAll(selector) { assert.equal(selector, 'iframe'); return frames; }};
  const context = vm.createContext({document, location: {href: origin + (options.frame ? '/env-frame' : '/env-policy') + '?phase=' + phase, origin},
    isSecureContext: options.secure !== false, crypto: {randomUUID: () => UUID}, navigator,
    URL: UrlBoundary, URLSearchParams, Blob: BlobBoundary, MessageChannel: ChannelBoundary, TextEncoder,
    fetch: async (address, settings) => { calls.fetches.push({address, settings, origin});
      if (options.markerFailure) throw Error('Controlled native document fetch failure');
      return {ok: options.markerAllowed !== false, text: async () => 'worker-network-synthetic-v1'}; },
    setTimeout(callback, delay) { assert.equal(delay, 8000); const id = ++timerSequence; timers.set(id, callback); return id; },
    clearTimeout(id) { timers.delete(id); },
    addEventListener(type, listener) { if (!events.has(type)) events.set(type, []); events.get(type).push(listener); }});
  if (options.workerAvailable !== false) context.Worker = WorkerBoundary;
  if (options.sharedAvailable !== false) context.SharedWorker = SharedBoundary;
  context.window = context;
  context.parent = options.frame ? {postMessage(value, targetOrigin) { calls.framePosts.push({value, targetOrigin}); }} : context;
  const natives = protectNativeReads(context);
  const nativeZone = vm.runInContext(TIMEZONE_SOURCE + ';JSON.stringify(nativeZone())', context);
  Object.defineProperty(context, 'navigator', {value: navigator, writable: false, configurable: false});
  vm.runInContext(SOURCE.replace('__WORKER_POLICY_FIXTURE__', JSON.stringify(CONFIG)), context,
    {filename: 'actual-gecko-environment-policy-page.js'});
  function emit(value, source, eventOrigin) {
    for (const listener of events.get('message') || []) listener({data: value, source, origin: eventOrigin});
  }
  function frameValue(index, changes = {}) {
    return {...clone(context.__geckoEnvironmentPolicy.page),
      documentId: '22222222-2222-4222-8222-' + String(index + 1).padStart(12, '0'),
      origin: CONFIG.origins[index], nativeUserAgent: 'native-frame/' + index,
      markerComplete: true, networkAllowed: true, ...changes};
  }
  function acceptFrames() { for (let index = 0; index < 2; index++) emit(frameValue(index), frames[index].contentWindow, CONFIG.origins[index]); }
  return {context, calls, timers, frames, active, registration, natives, nativeZone,
    emit, frameValue, acceptFrames,
    releaseResponses() { options.holdResponses = false; for (const action of calls.pending.splice(0)) queueMicrotask(action); },
    expireTimers() { for (const [id, callback] of Array.from(timers)) { timers.delete(id); callback(); } }};
}

test('single injected token and synchronous native snapshot match the shared server schema', () => {
  assert.equal(SOURCE.split('__WORKER_POLICY_FIXTURE__').length - 1, 1);
  assert.ok(Buffer.byteLength(SOURCE) <= 32768);
  assert.ok(!SOURCE.toLowerCase().includes('</script'));
  const f = fixture();
  const page = f.context.__geckoEnvironmentPolicy.page;
  assert.equal(page.schema, 1); assert.equal(page.firstInline, true); assert.equal(page.secure, true);
  assert.equal(page.runNonce, CONFIG.runNonce); assert.equal(page.sourceCommit, CONFIG.sourceCommit);
  assert.equal(page.phase, 'gecko-system'); assert.equal(page.documentId, UUID);
  assert.equal(page.nativeUserAgent, 'native-document-UA');
  assert.deepEqual(clone(page.nativeTimeZone), JSON.parse(f.nativeZone));
  assert.equal(f.context.__geckoEnvironmentPolicy.workers.started, false);
  assert.equal(f.context.__geckoEnvironmentPolicy.workers.complete, false);
  assert.equal(f.calls.dedicated.length + f.calls.shared.length + f.calls.service.length, 0);
  assert.equal(page.markerComplete, false); assert.equal(f.calls.fetches.length, 1);
  assert.equal(f.timers.size, 1);
  assert.equal(vm.runInContext('Date', f.context), f.natives.Date);
  assert.equal(vm.runInContext('Intl.DateTimeFormat', f.context), f.natives.format);
  assert.equal(vm.runInContext('Date.prototype.getHours', f.context), f.natives.dateHours);
});

test('first-inline and secure observations preserve false native conditions', () => {
  for (const options of [{notFirst: true}, {readyState: 'complete'}, {secure: false}]) {
    const f = fixture(options), page = f.context.__geckoEnvironmentPolicy.page;
    assert.equal(page.firstInline, !options.notFirst && options.readyState !== 'complete');
    assert.equal(page.secure, options.secure !== false);
  }
});

test('unknown phases fail before starting a Worker or publishing a fabricated report', () => {
  assert.throws(() => fixture({phase: 'gecko-unregistered-phase'}), /Unknown Gecko fixture phase/);
});

test('every current closed Gecko server phase retains a raw native clock instead of deriving one from its label', () => {
  const phaseLine = SERVER.match(/^PHASES=(.*)$/m)[1];
  const phases = Array.from(phaseLine.matchAll(/'(gecko-[a-z-]+)'/g), row => row[1]);
  assert.equal(phases.length, 17);
  for (const phase of phases) {
    const f = fixture({phase}), page = f.context.__geckoEnvironmentPolicy.page;
    assert.equal(page.phase, phase);
    assert.deepEqual(clone(page.nativeTimeZone), JSON.parse(f.nativeZone));
    assert.equal(page.nativeUserAgent, 'native-document-UA');
  }
});

test('frames post only their original synchronous native snapshot to an allowed top origin', async () => {
  const f = fixture({frame: true, origin: CONFIG.origins[1]});
  assert.equal(f.calls.framePosts.length, 0);
  await settle();
  assert.equal(f.calls.framePosts.length, 1);
  assert.equal(f.calls.framePosts[0].targetOrigin, CONFIG.origins[0]);
  assert.equal(f.calls.framePosts[0].value, f.context.__geckoEnvironmentPolicy.page);
  assert.equal(f.calls.framePosts[0].value.origin, CONFIG.origins[1]);
  assert.equal(f.calls.framePosts[0].value.firstInline, true);
  assert.equal(f.calls.framePosts[0].value.markerComplete, true);
  assert.equal(f.calls.framePosts[0].value.networkAllowed, true);
  const marker = new URL(f.calls.fetches[0].address, CONFIG.origins[1]);
  assert.equal(marker.pathname, '/worker-probe'); assert.equal(marker.searchParams.get('realm'), 'document');
  assert.equal(marker.searchParams.get('documentId'), UUID);
  assert.equal(typeof f.context.__runGeckoEnvironmentWorkers, 'undefined');
  assert.equal(f.calls.dedicated.length, 0);
  const second = fixture({frame: true, origin: CONFIG.origins[0], referrer: CONFIG.origins[1] + '/env-policy?phase=gecko-system'});
  await settle();
  assert.equal(second.calls.framePosts[0].targetOrigin, CONFIG.origins[1]);
});

test('frame admission checks nonce, commit, phase, origin, UUID and actual iframe source', () => {
  const f = fixture(), report = f.context.__geckoEnvironmentPolicy;
  const bad = [
    {runNonce: '0'.repeat(32)}, {sourceCommit: '0'.repeat(40)}, {phase: 'gecko-new-york'},
    {origin: CONFIG.origins[1]}, {documentId: 'not-a-document'}, {documentId: UUID},
    {schema: 2}, {firstInline: 'true'}, {secure: 'true'},
    {markerComplete: false}, {markerComplete: 'true'}, {networkAllowed: 'true'},
  ];
  for (const changes of bad) f.emit(f.frameValue(0, changes), f.frames[0].contentWindow, CONFIG.origins[0]);
  f.emit(f.frameValue(0), {}, CONFIG.origins[0]);
  f.emit(f.frameValue(0), f.context, CONFIG.origins[0]);
  f.emit(f.frameValue(0), f.frames[0].contentWindow, 'https://untrusted.example');
  assert.equal(report.frames.length, 0);
  const original = f.frames[0].src;
  for (const invalid of [CONFIG.origins[0] + '/wrong?phase=gecko-system',
    CONFIG.origins[0] + '/env-frame?phase=gecko-new-york',
    CONFIG.origins[0] + '/env-frame?phase=gecko-system&phase=gecko-system',
    CONFIG.origins[0] + '/env-frame?phase=gecko-system&extra=1']) {
    f.frames[0].src = invalid; f.emit(f.frameValue(0), f.frames[0].contentWindow, CONFIG.origins[0]);
  }
  f.frames[0].src = original;
  assert.equal(report.frames.length, 0);
  const raw = f.frameValue(0, {nativeTimeZone: clone(replyZone)});
  f.emit(raw, f.frames[0].contentWindow, CONFIG.origins[0]);
  f.emit(raw, f.frames[0].contentWindow, CONFIG.origins[0]);
  assert.equal(report.frames.length, 1);
  assert.deepEqual(clone(report.frames[0]), raw);
  f.emit(f.frameValue(1), f.frames[1].contentWindow, CONFIG.origins[1]);
  assert.equal(report.frames.length, 2);
});

test('on-demand factories launch in parallel once and preserve native worker observations', async () => {
  const f = fixture({holdResponses: true}); f.acceptFrames();
  const first = f.context.__runGeckoEnvironmentWorkers();
  const second = f.context.__runGeckoEnvironmentWorkers();
  assert.equal(first, second);
  assert.equal(f.calls.dedicated.length, 3); assert.equal(f.calls.shared.length, 1);
  assert.equal(f.calls.service.filter(row => row.action === 'register').length, 1);
  await settle();
  assert.equal(f.context.__geckoEnvironmentPolicy.workers.complete, false);
  f.releaseResponses(); await first;
  const report = f.context.__geckoEnvironmentPolicy;
  assert.equal(report.workers.complete, true);
  assert.deepEqual(Object.keys(report.workers.cases).sort(), ['blob', 'classic', 'module', 'service', 'shared']);
  for (const row of Object.values(report.workers.cases)) {
    assert.equal(row.available, true); assert.equal(row.created, true);
    assert.equal(row.executed, true); assert.equal(row.networkAllowed, true);
    assert.equal(typeof row.sourceRole, 'string');
  }
  assert.deepEqual(clone(report.workers.cases.classic.nativeTimeZone), replyZone);
  assert.deepEqual(clone(report.workers.cases.service.nativeTimeZone), replyZone);
  assert.equal(report.workers.cases.classic.nativeUserAgent, 'native-worker/dedicated-classic');
  assert.equal(f.calls.dedicated[1].settings.type, 'module');
  assert.equal(f.calls.terminated, 3); assert.equal(f.calls.sharedClosed, 1);
  assert.equal(f.calls.channelClosed, 1); assert.equal(f.calls.revoked.length, 1);
  assert.equal(f.calls.readyReads, 0); assert.equal(f.calls.unregisters, 0); assert.equal(f.timers.size, 0);
  for (const address of [...f.calls.dedicated.filter(row => !row.scope).map(row => row.url),
    f.calls.shared[0].url, f.calls.service.find(row => row.action === 'register').address]) {
    const url = new URL(address, CONFIG.origins[0]);
    assert.deepEqual([...url.searchParams.keys()].sort(), ['documentId', 'phase', 'realm']);
    assert.equal(url.searchParams.get('phase'), 'gecko-system'); assert.equal(url.searchParams.get('documentId'), UUID);
  }
  const service = f.calls.service.find(row => row.action === 'register');
  assert.equal(service.settings.scope, '/sw-scope/');
  const message = f.calls.service.find(row => row.action === 'message').value;
  assert.deepEqual(clone(message), {action: 'network', phase: 'gecko-system', documentId: UUID});
});

test('actual blob source executes its native zone and bound fetch without fingerprint writes', async () => {
  const f = fixture(); f.acceptFrames(); await f.context.__runGeckoEnvironmentWorkers();
  assert.equal(f.calls.blobSources.length, 1); assert.equal(f.calls.fetches.length, 2);
  const probe = new URL(f.calls.fetches.find(row => row.address.startsWith(CONFIG.origins[0])).address);
  assert.equal(probe.origin, CONFIG.origins[0]); assert.equal(probe.pathname, '/worker-probe');
  assert.equal(probe.searchParams.get('realm'), 'dedicated-blob');
  assert.equal(probe.searchParams.get('documentId'), UUID); assert.equal(probe.searchParams.get('phase'), 'gecko-system');
  const row = f.context.__geckoEnvironmentPolicy.workers.cases.blob;
  assert.equal(row.nativeUserAgent, 'native-blob-UA');
  assert.equal(row.sourceRole, 'dedicated-blob');
  const worker = f.calls.dedicated.find(value => value.scope);
  assert.equal(vm.runInContext('Date', worker.scope), worker.before.Date);
  assert.equal(vm.runInContext('Intl.DateTimeFormat', worker.scope), worker.before.format);
  assert.deepEqual(clone(row.nativeTimeZone), JSON.parse(vm.runInContext(TIMEZONE_SOURCE + ';JSON.stringify(nativeZone())', worker.scope)));
});

test('genuinely absent optional APIs are explicit unavailable outcomes', async () => {
  const f = fixture({sharedAvailable: false, serviceAvailable: false}); f.acceptFrames();
  await f.context.__runGeckoEnvironmentWorkers();
  const workers = f.context.__geckoEnvironmentPolicy.workers;
  assert.equal(workers.complete, true);
  for (const name of ['shared', 'service']) {
    const row = workers.cases[name];
    assert.equal(row.available, false); assert.equal(row.created, false); assert.equal(row.executed, false);
    assert.match(row.reason, /API unavailable/); assert.equal(row.error, undefined);
  }
});

test('existing constructors that throw remain available failed observations', async () => {
  const f = fixture({modes: {'dedicated-classic': 'constructor', 'shared-worker': 'constructor', 'service-worker': 'constructor'}});
  f.acceptFrames(); await f.context.__runGeckoEnvironmentWorkers();
  const workers = f.context.__geckoEnvironmentPolicy.workers;
  assert.equal(workers.complete, false); assert.match(workers.error, /incomplete/);
  for (const name of ['classic', 'shared', 'service']) {
    const row = workers.cases[name];
    assert.equal(row.available, true); assert.equal(row.created, false); assert.equal(row.executed, false);
    assert.ok(row.error); assert.equal(row.reason, undefined);
  }
});

test('missing required worker support cannot complete as a successful native observation', async () => {
  const f = fixture({workerAvailable: false}); f.acceptFrames(); await f.context.__runGeckoEnvironmentWorkers();
  const workers = f.context.__geckoEnvironmentPolicy.workers;
  assert.equal(workers.complete, false); assert.match(workers.error, /incomplete/);
  for (const name of ['classic', 'module', 'blob']) assert.equal(workers.cases[name].available, false);
});

test('worker deadline and wrong source role remain errors with cleanup', async () => {
  const f = fixture({modes: {'dedicated-classic': 'silent', 'dedicated-module': 'wrong-role'}}); f.acceptFrames();
  const run = f.context.__runGeckoEnvironmentWorkers(); await settle(); f.expireTimers(); await run;
  const workers = f.context.__geckoEnvironmentPolicy.workers;
  assert.equal(workers.complete, false); assert.match(workers.cases.classic.error, /8-second/);
  assert.match(workers.cases.module.error, /response incomplete/);
  assert.equal(workers.cases.classic.available, true); assert.equal(workers.cases.classic.created, true);
  assert.equal(workers.cases.classic.executed, false); assert.equal(f.calls.terminated, 3);
  assert.equal(f.timers.size, 0);
});

test('service activation waits the actual registration worker and never serviceWorker.ready', async () => {
  const f = fixture({serviceInstalling: true}); f.acceptFrames();
  const run = f.context.__runGeckoEnvironmentWorkers(); await settle();
  assert.equal(f.calls.service.filter(row => row.action === 'message').length, 0);
  f.active.state = 'activated'; for (const listener of Array.from(f.active.listeners)) listener();
  await run;
  assert.equal(f.context.__geckoEnvironmentPolicy.workers.complete, true);
  assert.equal(f.calls.readyReads, 0); assert.equal(f.active.listeners.size, 0);
});

test('two authenticated frame observations are required before collection is complete', async () => {
  const f = fixture();
  f.emit(f.frameValue(0), f.frames[0].contentWindow, CONFIG.origins[0]);
  const run = f.context.__runGeckoEnvironmentWorkers(); await settle();
  assert.equal(f.context.__geckoEnvironmentPolicy.workers.complete, false);
  assert.equal(Object.keys(f.context.__geckoEnvironmentPolicy.workers.cases).length, 5);
  f.expireTimers(); await run;
  const report = f.context.__geckoEnvironmentPolicy;
  assert.equal(report.workers.complete, false); assert.match(report.framesError, /two native frame observations/);
  assert.ok(report.workers.error);
});

test('native network refusal is retained as raw data rather than rewritten into an expected outcome', async () => {
  const f = fixture({networkAllowed: false}); f.acceptFrames(); await f.context.__runGeckoEnvironmentWorkers();
  const cases = f.context.__geckoEnvironmentPolicy.workers.cases;
  for (const name of ['classic', 'module', 'shared', 'service']) {
    assert.equal(cases[name].executed, true); assert.equal(cases[name].networkAllowed, false);
    assert.deepEqual(clone(cases[name].nativeTimeZone), replyZone);
  }
  assert.equal(f.context.__geckoEnvironmentPolicy.workers.complete, true);
});

test('document marker binds native inline UUID before workers and preserves a failed native fetch', async () => {
  const success = fixture();
  assert.equal(success.context.__geckoEnvironmentPolicy.page.markerComplete, false);
  assert.equal(success.calls.dedicated.length, 0); await settle();
  const page = success.context.__geckoEnvironmentPolicy.page;
  assert.equal(page.markerComplete, true); assert.equal(page.networkAllowed, true);
  const marker = new URL(success.calls.fetches[0].address, CONFIG.origins[0]);
  assert.deepEqual([...marker.searchParams.keys()].sort(), ['documentId', 'phase', 'realm']);
  assert.equal(marker.searchParams.get('documentId'), UUID); assert.equal(marker.searchParams.get('phase'), 'gecko-system');
  assert.equal(marker.searchParams.get('realm'), 'document');
  assert.equal(success.calls.fetches[0].settings.cache, 'no-store');
  const failed = fixture({markerFailure: true}); failed.acceptFrames();
  await failed.context.__runGeckoEnvironmentWorkers();
  const report = failed.context.__geckoEnvironmentPolicy;
  assert.equal(report.page.firstInline, true); assert.equal(report.page.markerComplete, true);
  assert.equal(report.page.networkAllowed, false); assert.match(report.page.markerError, /document fetch failure/);
  assert.equal(report.workers.complete, false); assert.match(report.workers.error, /document network marker/);
});

test('DOM snapshots bridge isolated readers before the first marker fetch and after every completed observation', async () => {
  const f = fixture();
  assert.ok(f.calls.snapshots.length >= 1); assert.equal(f.calls.snapshots[0].fetches, 0);
  const first = JSON.parse(f.calls.snapshots[0].value);
  assert.equal(first.page.firstInline, true); assert.equal(first.page.documentId, UUID);
  assert.equal(first.page.markerComplete, false); assert.equal(first.workers.started, false);
  assert.deepEqual(first.page.nativeTimeZone, JSON.parse(f.nativeZone));
  f.acceptFrames();
  f.context.document.dispatchEvent({type: 'pocketchat-gecko-env-run-workers', detail: 'wrong-run'});
  f.context.document.dispatchEvent({type: 'pocketchat-gecko-env-run-workers', detail: new String(CONFIG.runNonce)});
  assert.equal(f.context.__geckoEnvironmentPolicy.workers.started, false);
  // Primitive nonce detail is accessible from a separate isolated VM world.
  vm.runInNewContext(`document.dispatchEvent({type:'pocketchat-gecko-env-run-workers',detail:${JSON.stringify(CONFIG.runNonce)}})`,
    {document: f.context.document});
  await f.context.__runGeckoEnvironmentWorkers();
  const isolated = vm.runInNewContext(`JSON.parse(document.documentElement.getAttribute('data-gecko-environment-policy'))`,
    {document: f.context.document});
  assert.equal(isolated.page.markerComplete, true); assert.equal(isolated.page.networkAllowed, true);
  assert.equal(isolated.frames.length, 2); assert.equal(isolated.workers.complete, true);
  assert.equal(Object.keys(isolated.workers.cases).length, 5);
  assert.equal(isolated.workers.cases.classic.sourceRole, 'dedicated-classic');
  assert.ok(f.calls.snapshots.some(row => JSON.parse(row.value).workers.started && row.workers === 0));
  assert.ok(f.calls.snapshots.length > 10);
  assert.equal(isolated.__geckoEnvironmentPolicy, undefined);
});

test('oversized native observations publish a bounded explicit failure rather than truncated native success', async () => {
  const userAgent = '文'.repeat(100000), f = fixture({userAgent}); await settle();
  const encoded = f.context.document.documentElement.getAttribute('data-gecko-environment-policy');
  assert.ok(Buffer.byteLength(encoded) <= 100000);
  const report = JSON.parse(encoded);
  assert.equal(report.publicationError, 'oversized-native-observation');
  assert.equal(report.workers.complete, false); assert.ok(report.workers.error);
  assert.equal(f.context.__geckoEnvironmentPolicy.page.nativeUserAgent, userAgent);
  assert.equal(report.page.nativeUserAgent, undefined);
});
