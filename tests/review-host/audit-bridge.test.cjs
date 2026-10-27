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
function harness(options = {}) {
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
    AbortController, TextDecoder, Uint8Array,
    fetch: async (url, requestOptions) => { fetched.push({url, options: requestOptions});const chunks=options.chunks||[new TextEncoder().encode(JSON.stringify({ip:'203.0.113.9'}))];let index=0;return {ok:true,body:options.noReader?null:{getReader(){return {read:async()=>index<chunks.length?{value:chunks[index++],done:false}:{done:true},cancel:async()=>{options.cancelled=(options.cancelled||0)+1;},releaseLock(){options.released=(options.released||0)+1;}};}},text:async()=>{throw Error('Unbounded response.text must not run');}}; },
    PocketRequestIdentityAudit: options.identityHelper,
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
async function flush() { await new Promise(resolve=>setImmediate(resolve)); }
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
  assert.equal(result.parent.languages, undefined);
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


test('oversized network bodies are cancelled while streaming and never accepted', async () => {
  const options={chunks:[new Uint8Array(8000).fill(32),new Uint8Array(8000).fill(32)]};const bridge=harness(options);
  bridge.send({kind:'audit',id:40,configuration:{id:'large-body',network:true}});bridge.event(observed(bridge.nonce()));await flush();await flush();
  assert.equal(bridge.result().length,1);const result=JSON.parse(bridge.result()[0].result);
  assert.equal(result.network.ipv4.ip,undefined);assert.equal(options.cancelled,3);assert.equal(options.released,3);
});

test('a missing body reader remains uncovered without unbounded text fallback', async () => {
  const bridge=harness({noReader:true});bridge.send({kind:'audit',id:41,configuration:{id:'missing-reader',network:true}});bridge.event(observed(bridge.nonce()));await flush();
  assert.equal(bridge.result().length,1);assert.equal(JSON.parse(bridge.result()[0].result).network.ipv4.ip,undefined);
});

test('malformed language arrays stay absent instead of silently becoming complete',async()=>{
  const bridge=harness();bridge.send({kind:'audit',id:42,configuration:{id:'language-coverage',network:false}});bridge.event(observed(bridge.nonce(),{parent:{ua:'Firefox/157.0',languages:['en-US',null]}}));await flush();
  assert.equal(JSON.parse(bridge.result()[0].result).parent.languages,undefined);
});

function apiObservation(extra = {}) {
  return {schema:1,probeVersion:1,requested:true,source:'page-main-world',durationMs:7,
    limits:{canvasPixels:999999999},protectionVerified:true,
    probes:{canvas:{state:'available',reason:'draw-and-pixel-readback-completed',pixels:4096,hash:'a'.repeat(64),hashAlgorithm:'sha256'},
      audio:{state:'restricted',reason:'NotAllowedError'},fonts:{state:'uncovered',reason:'font-measurement-unavailable'},
      webgl:{state:'failed',reason:'OperationError'}},...extra};
}

test('normal audit does not request or accept expensive API probes', async()=>{
  const bridge=harness();bridge.send({kind:'audit',id:43,configuration:{id:'light',network:false}});
  assert.equal(JSON.parse(bridge.scripts.at(-1).attributes['data-pocket-audit']).apiChecks,false);
  bridge.event(observed(bridge.nonce(),{apiChecks:apiObservation()}));await flush();
  assert.equal(JSON.parse(bridge.result()[0].result).apiChecks,undefined);
});

test('explicit API request preserves bounded operation observations without protection attestation', async()=>{
  const bridge=harness();bridge.send({kind:'audit',id:44,configuration:{id:'api',network:false,apiChecks:true}});
  assert.equal(JSON.parse(bridge.scripts.at(-1).attributes['data-pocket-audit']).apiChecks,true);
  bridge.event(observed(bridge.nonce(),{apiChecks:apiObservation()}));await flush();
  const checks=JSON.parse(bridge.result()[0].result).apiChecks;
  assert.equal(checks.source,'page-main-world');assert.equal(checks.protectionVerified,false);
  assert.deepEqual(checks.limits,{canvasPixels:4096,audioFrames:2048,fontCandidates:5,totalBudgetMs:1200});
  assert.equal(checks.probes.canvas.hash,'a'.repeat(64));assert.equal(checks.probes.audio.state,'restricted');
  assert.equal(bridge.fetched.length,0);
});

test('CSP-blocked deep audit reports uncovered APIs instead of isolated-world API values', async()=>{
  const bridge=harness();bridge.send({kind:'audit',id:45,configuration:{id:'blocked-api',network:false,apiChecks:true}});
  bridge.scripts.at(-1).onerror();await flush();const result=JSON.parse(bridge.result()[0].result);
  assert.equal(result.mainWorld.observed,false);assert.equal(result.apiChecks.source,'unavailable');
  assert.ok(Object.values(result.apiChecks.probes).every(probe=>probe.state==='uncovered'));
  assert.equal(result.apiChecks.protectionVerified,false);
  assert.deepEqual(JSON.parse(bridge.scripts.at(-1).attributes['data-pocket-audit']),{});
});

test('API payloads strip unbounded or invalid fields and cannot enable more contexts', async()=>{
  const bridge=harness();bridge.send({kind:'audit',id:46,configuration:{id:'bounded-api',network:false,apiChecks:true}});
  const api=apiObservation({probes:{canvas:{state:'available',reason:'x'.repeat(9000),hash:'not-a-hash',hashAlgorithm:'sha256',pixels:Infinity,secret:{cookie:'no'}},
    audio:{state:'verified',reason:'invented'},fonts:{state:'available',reason:'font-values',samples:[{name:'bad',faceCheck:{bad:true},monospaceWidth:1,sansSerifWidth:1}]},
    webgl:{state:'restricted',reason:'masked',renderer:{bad:true},extensions:Array(8).fill('extension')}}});
  bridge.event(observed(bridge.nonce(),{apiChecks:api}));await flush();const checks=JSON.parse(bridge.result()[0].result).apiChecks;
  assert.equal(checks.probes.canvas.state,'uncovered');assert.equal(checks.probes.canvas.reason,'incomplete-available-observation');assert.equal(checks.probes.canvas.hash,undefined);
  assert.equal(checks.probes.canvas.pixels,undefined);assert.equal(checks.probes.canvas.secret,undefined);
  assert.equal(checks.probes.audio.state,'uncovered');assert.equal(checks.probes.fonts.state,'uncovered');assert.deepEqual(checks.probes.fonts.samples,[]);
  assert.equal(checks.probes.webgl.renderer,undefined);assert.equal(checks.probes.webgl.extensions,undefined);
  assert.match(checks.coverage,/frame and Worker API operations not sampled/);
});

test('cancelled API audit ignores later operation results', async()=>{
  const bridge=harness();bridge.send({kind:'audit',id:47,configuration:{id:'cancel-api',network:false,apiChecks:true}});
  const nonce=bridge.nonce();bridge.send({kind:'auditCancel'});bridge.event(observed(nonce,{apiChecks:apiObservation()}));await flush();
  assert.equal(bridge.result().length,0);
  assert.deepEqual(JSON.parse(bridge.scripts.at(-1).attributes['data-pocket-audit']),{});
});

test('request-identity helper is never invoked by an ordinary audit',async()=>{
  let calls=0;const bridge=harness({identityHelper:{run(){calls++;return Promise.resolve({});}}});
  bridge.send({kind:'audit',id:48,configuration:{id:'no-request-check',network:false}});
  bridge.event(observed(bridge.nonce()));await flush();
  assert.equal(calls,0);assert.equal(JSON.parse(bridge.result()[0].result).requestIdentity,undefined);
});

test('only explicit native request configuration reaches the isolated request helper',async()=>{
  let received;const observation={schema:1,nonce:'a'.repeat(32),status:'complete',source:'controlled-top-level-document',document:{ua:'main',language:'en-US',languages:['en-US']},worker:{ua:'worker',language:'en-US',languages:['en-US']}};
  const bridge=harness({identityHelper:{run(configuration,stops){received=configuration;assert.ok(Array.isArray(stops));return Promise.resolve(observation);}}});
  const configuration={nonce:'a'.repeat(32),endpoint:'https://controlled.test/pocketchat-identity/v1/'};
  bridge.send({kind:'audit',id:49,configuration:{id:'request-check',network:false,requestIdentity:configuration}});
  bridge.event(observed(bridge.nonce()));await flush();
  assert.equal(received,configuration);assert.deepEqual(JSON.parse(bridge.result()[0].result).requestIdentity,observation);
  assert.equal(bridge.fetched.length,0);assert.equal(bridge.evaluated,0);
});

test('missing request helper fails explicitly without falling back to content fetch',async()=>{
  const bridge=harness();bridge.send({kind:'audit',id:50,configuration:{id:'missing-request-helper',network:false,requestIdentity:{nonce:'b'.repeat(32)}}});
  bridge.event(observed(bridge.nonce()));await flush();const identity=JSON.parse(bridge.result()[0].result).requestIdentity;
  assert.equal(identity.status,'failed');assert.equal(identity.error,'request-identity-helper-unavailable');
  assert.equal(identity.document,undefined);assert.equal(bridge.fetched.length,0);
});

test('cancelled request helper cannot deliver a late audit result',async()=>{
  let complete;const bridge=harness({identityHelper:{run(configuration,stops){return new Promise(resolve=>{complete=resolve;stops.push(()=>resolve({schema:1,status:'failed',error:'cancelled'}));});}}});
  bridge.send({kind:'audit',id:51,configuration:{id:'cancel-request-helper',network:false,requestIdentity:{nonce:'c'.repeat(32)}}});
  const nonce=bridge.nonce();await flush();bridge.send({kind:'auditCancel'});complete({schema:1,status:'complete'});bridge.event(observed(nonce));await flush();
  assert.equal(bridge.result().length,0);
});

test('immediate cancellation prevents even starting a deferred request helper',async()=>{
  let calls=0;const bridge=harness({identityHelper:{run(){calls++;return Promise.resolve({schema:1,status:'complete'});}}});
  bridge.send({kind:'audit',id:52,configuration:{id:'cancel-before-helper',network:false,requestIdentity:{nonce:'d'.repeat(32)}}});
  bridge.send({kind:'auditCancel'});await flush();assert.equal(calls,0);assert.equal(bridge.result().length,0);
});
