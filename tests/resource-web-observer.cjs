/* Production JS in JSDOM with controlled timers/gesture adapters. No Android,
 * real website, timing benchmark, memory measurement, or capacity acceptance. */
'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {JSDOM} = require(process.env.JSDOM_MODULE || 'jsdom');
const source = fs.readFileSync(path.join(__dirname, '../app/src/main/assets/web-reply-observer.js'), 'utf8');

function fixture({url = 'https://chatgpt.com/c/resource-fixture', uploadApi = true, bridge = true} = {}) {
  const window = new JSDOM('<!doctype html><body><form><textarea id="prompt-textarea">original unsent draft</textarea><button type="button" data-testid="send-button" aria-label="Send">Send</button><div id="upload-zone"></div></form><main><article data-message-author-role="user" data-message-id="u0">earlier prompt</article></main><aside id="unrelated"></aside></body>',
    {url, runScripts:'outside-only'}).window;
  const posts = [], timers = new Map(), observers = [], handlers = new Map();
  const reads = {composer:0, busy:0, resourceBusy:0, uploadBusy:0};
  let timerId = 0, now = 1700000000000;
  window.Date.now = () => now;
  window.setTimeout = (fn, delay) => { const id = ++timerId; timers.set(id, {fn, delay}); return id; };
  window.clearTimeout = id => timers.delete(id);
  const NativeObserver = window.MutationObserver;
  window.MutationObserver = class extends NativeObserver {
    constructor(callback) { super(callback); observers.push(this); }
  };
  const add = window.document.addEventListener.bind(window.document);
  window.document.addEventListener = (kind, callback, ...rest) => {
    if (!handlers.has(kind)) handlers.set(kind, []);
    handlers.get(kind).push(callback);
    return add(kind, callback, ...rest);
  };
  window.document.cookie = 'fixtureSession=preserved;path=/';
  if (bridge) window.PocketWebReply = {postMessage:value => posts.push(JSON.parse(value))};
  const api = {
    composer:() => { reads.composer++; return window.document.querySelector('textarea'); },
    sendButton:() => window.document.querySelector('[data-testid="send-button"]'),
    draft:input => input.value,
    busy:() => { reads.busy++; return !!window.document.querySelector('[data-testid="stop-button"]'); },
    resourceBusy:() => { reads.resourceBusy++; return !!window.document.querySelector('[data-testid="stop-button"]'); },
    messages:role => [...window.document.querySelectorAll(`[data-message-author-role="${role}"]`)],
    key:node => 'id:' + node.getAttribute('data-message-id'),
    userText:node => node.textContent,
    hasMessages:() => !!window.document.querySelector('[data-message-author-role]'),
  };
  if (uploadApi) api.uploadBusy = () => { reads.uploadBusy++; return !!window.document.querySelector('[data-upload-state="uploading"]'); };
  window.eval(source);
  const settle = async () => { await Promise.resolve(); await Promise.resolve(); };
  const scheduled = delay => [...timers.values()].filter(task => task.delay === delay).length;
  const flush = delay => {
    const batch = [...timers].filter(([, task]) => task.delay === delay);
    assert.ok(batch.length <= 10, 'Timer flush is bounded and never waits real milliseconds');
    for (const [id, task] of batch) { timers.delete(id); task.fn(); }
    return batch.length;
  };
  const mutation = async () => { window.document.getElementById('unrelated').append(window.document.createElement('span')); await settle(); };
  const resources = () => posts.filter(row => row.type === 'resource-work');
  const busy = value => {
    const old = window.document.querySelector('[data-testid="stop-button"]');
    if (value && !old) { const node = window.document.createElement('button'); node.dataset.testid = 'stop-button'; window.document.body.append(node); }
    else if (!value && old) old.remove();
  };
  const uploading = value => {
    const zone = window.document.getElementById('upload-zone');
    if (value) zone.setAttribute('data-upload-state', 'uploading');
    else zone.removeAttribute('data-upload-state');
  };
  const close = () => { observers.forEach(observer => observer.disconnect()); timers.clear(); window.close(); };
  return {window, api, posts, timers, handlers, observers, reads, settle, scheduled, flush, mutation, resources, busy, uploading, close,
    install:binding => window.__pocketInstallWebReplyObserver(api,binding), advance:value => { now += value; }};
}

test('Initial resource state is sampled once after a controlled 250ms throttle', async t => {
  const f = fixture(); t.after(f.close);
  const before = f.window.document.body.innerHTML;
  assert.equal(f.install(), true);
  assert.equal(f.scheduled(250), 1);
  assert.equal(f.resources().length, 0);
  assert.equal(f.flush(250), 1);
  assert.equal(f.resources().length, 1);
  const first = f.resources()[0];
  assert.equal(first.busy, false); assert.equal(first.uploading, false);
  assert.equal(first.resourceSequence, 1);
  assert.equal(first.capturedAt, 1700000000000);
  assert.equal(f.reads.resourceBusy, 1); assert.equal(f.reads.uploadBusy, 1);
  assert.equal(f.reads.busy, 0, 'Resource observation must not run the legacy page-wide busy API');
  assert.equal(first.url, f.window.location.href);
  assert.match(first.documentId, /^[a-zA-Z0-9-]{16,80}$/);
  assert.equal(f.window.document.body.innerHTML, before);
  assert.equal(f.window.document.querySelector('textarea').value, 'original unsent draft');
  assert.match(f.window.document.cookie, /fixtureSession=preserved/);
});

test('Installing the observer twice retains one identity observer and initial resource timer', t => {
  const f = fixture(); t.after(f.close);
  assert.equal(f.install(), true);
  const identity = f.window.__pocketWebReplyObserver.documentId;
  assert.equal(f.install(), true);
  assert.equal(f.window.__pocketWebReplyObserver.documentId, identity);
  assert.equal(f.observers.length, 1);
  assert.equal(f.scheduled(250), 1);
  f.flush(250);
  assert.equal(f.resources().length, 1);
});

test('Mutation bursts schedule one resource sample that reads the final busy and upload state', async t => {
  const f = fixture(); t.after(f.close); f.install(); f.flush(250);
  for (let i = 0; i < 80; i++) f.window.document.getElementById('unrelated').setAttribute('data-pulse', String(i));
  f.busy(true); f.uploading(true); await f.settle();
  await f.mutation(); await f.mutation();
  assert.equal(f.scheduled(250), 1);
  assert.equal(f.resources().length, 1);
  f.flush(250);
  assert.deepEqual(f.resources().map(row => [row.busy, row.uploading, row.resourceSequence]), [[false,false,1],[true,true,2]]);
});

test('Repeated unrelated DOM mutations never rescan or repost unchanged resource state', async t => {
  const f = fixture(); t.after(f.close); f.install(); f.flush(250);
  f.flush(50); const before = {...f.reads};
  for (let i = 0; i < 8; i++) { await f.mutation(); assert.equal(f.scheduled(250), 0); f.flush(250); }
  assert.equal(f.resources().length, 1);
  assert.deepEqual(f.reads, before);
  f.busy(true); await f.settle(); f.flush(250);
  assert.equal(f.resources().at(-1).resourceSequence, 2);
});

test('Starting and ending a website reply each publish an observed busy transition', async t => {
  const f = fixture(); t.after(f.close); f.install(); f.flush(250);
  f.busy(true); await f.settle(); f.flush(250);
  f.busy(false); await f.settle(); f.flush(250);
  assert.deepEqual(f.resources().map(row => row.busy), [false,true,false]);
  assert.ok(f.resources().every(row => row.uploading === false));
  assert.deepEqual(f.resources().map(row => row.resourceSequence), [1,2,3]);
});

test('Starting and ending an upload each publish independently of reply busy state', async t => {
  const f = fixture(); t.after(f.close); f.install(); f.flush(250);
  f.uploading(true); await f.settle(); f.flush(250);
  f.uploading(false); await f.settle(); f.flush(250);
  assert.deepEqual(f.resources().map(row => row.uploading), [false,true,false]);
  assert.ok(f.resources().every(row => row.busy === false));
  assert.deepEqual(f.resources().map(row => row.resourceSequence), [1,2,3]);
});

test('Initial already busy upload and reply state is preserved rather than guessed idle', t => {
  const f = fixture(); t.after(f.close); f.busy(true); f.uploading(true);
  f.install(); f.flush(250);
  assert.equal(f.resources().length, 1);
  assert.equal(f.resources()[0].busy, true); assert.equal(f.resources()[0].uploading, true);
});

test('Resource sequence strictly increases across state and committed route mutations', async t => {
  const f = fixture(); t.after(f.close); f.install(); f.flush(250);
  f.busy(true); await f.settle(); f.advance(20); f.flush(250);
  f.uploading(true); await f.settle(); f.advance(20); f.flush(250);
  f.window.history.pushState({}, '', '/c/next-resource-route'); f.window.dispatchEvent(new f.window.PopStateEvent('popstate')); await f.mutation(); f.advance(20); f.flush(250);
  f.busy(false); f.uploading(false); await f.settle(); f.advance(20); f.flush(250);
  const rows = f.resources();
  assert.deepEqual(rows.map(row => row.resourceSequence), [1,2,3,4,5]);
  assert.equal(new Set(rows.map(row => row.documentId)).size, 1);
  assert.ok(rows.every((row, index) => index === 0 || row.capturedAt > rows[index - 1].capturedAt));
  assert.equal(rows[3].url, 'https://chatgpt.com/c/next-resource-route');
  assert.equal(rows[3].busy, true); assert.equal(rows[3].uploading, true);
});

test('Same document query and hash changes emit a bound route and refresh resource state', async t => {
  const f = fixture(); t.after(f.close); f.install(); f.flush(50); f.flush(250);
  const original=f.resources()[0];
  f.window.history.replaceState({}, '', '/c/resource-fixture?view=changed#section');
  f.window.dispatchEvent(new f.window.PopStateEvent('popstate')); await f.mutation(); f.flush(250);
  const route=f.posts.find(row=>row.type==='resource-route');
  assert.ok(route);assert.equal(route.documentId,original.documentId);assert.equal(route.url,'https://chatgpt.com/c/resource-fixture?view=changed#section');
  assert.equal(f.resources().length,2);assert.equal(f.resources()[1].resourceSequence,2);assert.equal(f.resources()[1].url,route.url);
  f.window.history.replaceState({}, '', '/c/a-different-route'); f.window.dispatchEvent(new f.window.PopStateEvent('popstate')); await f.mutation(); f.flush(50); f.flush(250);
  assert.equal(f.resources().length,3);assert.equal(f.resources()[2].resourceSequence,3);
});

test('Retained document reinstall refreshes one bounded snapshot without duplicate listeners or draft writes', async t => {
  const f = fixture(); t.after(f.close);
  const firstBinding='primary-before-popup'; f.install(firstBinding); f.flush(50); f.flush(250);
  const first=f.resources()[0], listeners=[...f.handlers].map(([kind,callbacks])=>[kind,callbacks.length]);
  const draft=f.window.document.querySelector('textarea').value, cookie=f.window.document.cookie;
  f.busy(true);f.uploading(true);await f.settle();f.flush(250);
  const before=f.resources().at(-1), reads={...f.reads};
  f.advance(400);f.install('primary-after-popup');f.install('primary-after-popup');
  assert.equal(f.scheduled(250),1);assert.deepEqual(f.reads,reads);
  f.flush(250);const fresh=f.resources().at(-1);
  assert.equal(fresh.resourceBinding,'primary-after-popup');assert.equal(first.resourceBinding,firstBinding);
  assert.equal(fresh.documentId,first.documentId);assert.equal(fresh.resourceSequence,before.resourceSequence+1);
  assert.equal(fresh.busy,true);assert.equal(fresh.uploading,true);assert.ok(fresh.capturedAt>before.capturedAt);
  assert.equal(f.observers.length,1);assert.deepEqual([...f.handlers].map(([kind,callbacks])=>[kind,callbacks.length]),listeners);
  assert.equal(f.window.document.querySelector('textarea').value,draft);assert.equal(f.window.document.cookie,cookie);
  assert.equal(f.posts.filter(row=>row.type==='intent').length,0);
});

test('A queued resource sample adopts only the newest native activation binding', async t => {
  const f=fixture();t.after(f.close);f.install('old-primary');
  f.install('popup');f.install('returned-primary');assert.equal(f.scheduled(250),1);f.flush(250);
  assert.equal(f.resources().length,1);assert.equal(f.resources()[0].resourceBinding,'returned-primary');
  f.window.__pocketWebReplyObserver.refreshResources('x'.repeat(81));assert.equal(f.scheduled(250),0);
});

test('API without uploadBusy preserves readiness and trusted reply intent binding', async t => {
  const f = fixture({uploadApi:false}); t.after(f.close);
  assert.equal(f.install(), true); assert.equal(f.scheduled(250), 0);
  f.flush(50); assert.equal(f.posts.filter(row => row.type === 'ready').length, 1);
  const send = f.window.document.querySelector('[data-testid="send-button"]');
  // Explicit trusted-gesture host adapter; JSDOM does not manufacture trusted user input.
  f.handlers.get('click')[0]({isTrusted:true, target:send});
  const intent = f.posts.find(row => row.type === 'intent');
  assert.ok(intent); assert.equal(intent.prompt, 'original unsent draft');
  assert.deepEqual(intent.beforeKeys, ['id:u0']);
  const user = f.window.document.createElement('article'); user.dataset.messageAuthorRole = 'user';
  user.dataset.messageId = 'u1'; user.textContent = intent.prompt; f.window.document.querySelector('main').append(user);
  await f.settle(); f.flush(30);
  const bound = f.posts.find(row => row.type === 'bound');
  assert.ok(bound); assert.equal(bound.token, intent.token); assert.equal(bound.userKey, 'id:u1');
  assert.equal(f.resources().length, 0); assert.equal(f.scheduled(250), 0);
  assert.equal(f.scheduled(45000), 0);
});

test('Non ChatGPT origin never installs listeners resource timers or observer state', async t => {
  const f = fixture({url:'https://accounts.example/c/resource-fixture'}); t.after(f.close);
  assert.equal(f.install(), false);
  assert.equal(f.window.__pocketWebReplyObserver, undefined);
  assert.equal(f.observers.length, 0); assert.equal(f.scheduled(250), 0);
  await f.mutation(); f.flush(250);
  assert.equal(f.posts.length, 0);
});

test('Missing native bridge never installs resource observation', t => {
  const f = fixture({bridge:false}); t.after(f.close);
  assert.equal(f.install(), false); assert.equal(f.observers.length, 0);
  assert.equal(f.scheduled(250), 0); assert.equal(f.window.__pocketWebReplyObserver, undefined);
});

test('Synthetic untrusted clicks cannot acquire a reply intent while resource observation works', async t => {
  const f = fixture(); t.after(f.close); f.install(); f.flush(250);
  f.window.document.querySelector('[data-testid="send-button"]').click();
  await f.settle(); f.flush(30); f.flush(250);
  assert.equal(f.posts.filter(row => row.type === 'intent').length, 0);
  assert.equal(f.resources().length, 1);
  assert.equal(f.window.document.querySelector('textarea').value, 'original unsent draft');
});

test('A thousand long reply text mutations never rescan busy upload or composer state', async t => {
  const f = fixture(); t.after(f.close);
  const body = f.window.document.createElement('div'); body.className = 'markdown';
  body.setAttribute('data-message-author-role', 'assistant');
  const text = f.window.document.createTextNode('long reply '.repeat(10000));
  body.append(text); f.window.document.querySelector('main').append(body);
  f.install(); f.flush(250); f.flush(50); await f.settle(); f.flush(250);
  const before = {...f.reads}, posts = f.resources().length;
  for (let i = 0; i < 1000; i++) text.nodeValue += ' token' + i;
  await f.settle();
  assert.equal(f.scheduled(250), 0); f.flush(250);
  assert.deepEqual(f.reads, before); assert.equal(f.resources().length, posts);
  assert.ok(text.nodeValue.endsWith(' token999'));
});

test('Unrelated child lists beside a long reply do not trigger resource API scans', async t => {
  const f = fixture(); t.after(f.close);
  const body = f.window.document.createElement('div'); body.className = 'markdown';
  body.setAttribute('data-message-author-role', 'assistant'); body.textContent = 'long reply '.repeat(10000);
  f.window.document.querySelector('main').append(body);
  f.install(); f.flush(250); f.flush(50); await f.settle(); f.flush(250);
  const before = {...f.reads}, posts = f.resources().length;
  for (let i = 0; i < 1000; i++) { const item = f.window.document.createElement('span'); item.textContent = 'unrelated ' + i; body.append(item); }
  await f.settle(); assert.equal(f.scheduled(250), 0); f.flush(250);
  assert.deepEqual(f.reads, before); assert.equal(f.resources().length, posts);
});
