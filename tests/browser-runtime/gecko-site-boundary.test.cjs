/* Actual production scripts with synthetic DOM/native-port boundaries.
 * This checks site admission and retained audit/evaluation behavior, not Android,
 * Gecko fingerprint coverage, trusted user gestures or public website operation.
 */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const {JSDOM} = require(process.env.JSDOM_MODULE || 'jsdom');
const root = path.resolve(__dirname, '../..');
const asset = name => fs.readFileSync(path.join(root, 'app/src/main/assets', name), 'utf8');
const content = asset('gecko/content.js');
const driver = asset('page-driver.js');
const attachments = asset('attachment-driver.js');
const observer = asset('web-reply-observer.js');
const flush = () => new Promise(resolve => setImmediate(resolve));
const interactionEvents = new Set(['pointerdown', 'pointermove', 'pointerup', 'pointercancel',
  'touchstart', 'touchmove', 'touchend', 'touchcancel', 'wheel', 'keydown', 'beforeinput',
  'input', 'compositionstart', 'compositionupdate', 'compositionend']);
const html = '<!doctype html><body><form><textarea id="prompt-textarea">private unsent draft</textarea>' +
  '<button data-testid="send-button" aria-label="Send">Send</button>' +
  '<div data-file-name="keep.txt" data-upload-state="ready"><span>keep.txt</span>' +
  '<button aria-label="Remove file keep.txt">Remove</button></div></form></body>';

function fixture(url, framed = false) {
  const dom = new JSDOM(html, {url: framed ? 'https://parent.example/' : url,
    runScripts: 'outside-only', pretendToBeVisual: true});
  let w = dom.window;
  if (framed) {
    const frame = w.document.createElement('iframe');
    frame.src = url;w.document.body.append(frame);w = frame.contentWindow;
    w.document.open();w.document.write(html);w.document.close();
  }
  const editor = w.document.getElementById('prompt-textarea');
  const messages = [], scripts = [], events = [], reads = {selectors: 0, text: 0, fetches: 0};
  let receive;
  for (const name of ['querySelector', 'querySelectorAll', 'getElementById', 'getElementsByTagName', 'getElementsByClassName']) {
    const original = w.document[name].bind(w.document);
    w.document[name] = (...args) => {reads.selectors++;return original(...args);};
  }
  Object.defineProperty(w.HTMLElement.prototype, 'innerText', {
    configurable: true, get() {reads.text++;return this.textContent;},
  });
  const listen = w.document.addEventListener.bind(w.document);
  w.document.addEventListener = (name, callback, options) => {
    if (interactionEvents.has(name)) events.push(name);
    return listen(name, callback, options);
  };
  const create = w.document.createElement.bind(w.document);
  w.document.createElement = (...args) => {
    const element = create(...args);if (args[0] === 'script') scripts.push(element);return element;
  };
  w.Element.prototype.getClientRects = () => [{}];
  w.visualViewport = {scale: 1, addEventListener() {}};
  w.requestAnimationFrame = () => 1;w.cancelAnimationFrame = () => {};
  w.fetch = () => {reads.fetches++;throw new Error('Unrequested fixture network');};
  w.browser = {runtime: {
    connectNative(name) {
      assert.equal(name, 'pocketpage');
      return {postMessage: value => messages.push(value),
        onMessage: {addListener: callback => {receive = callback;}}};
    }, getURL: name => 'moz-extension://controlled/' + name,
  }};
  return {w, editor, reads, events, messages, scripts,
    install() {w.eval(content);}, send(message) {assert.ok(receive);receive(message);},
    call(action, args = {}, source = driver) {
      return w.eval(source.replace('__ACTION__', JSON.stringify(action)).replace('__ARG__', JSON.stringify(args)));
    }, close() {dom.window.close();},
  };
}

function noChatSurface(f) {
  for (const name of ['PocketWebReply', '__pocketReadingInteraction', '__pocketComposerInteraction',
    '__pocketWebReplyObserver', '__pocketReadDriver', '__pocketCheckAttachments',
    '__pocketAttachmentDocumentId', '__pocketAttachmentBatches']) {
    assert.equal(Object.hasOwn(f.w, name), false, 'Unrelated page acquired ' + name);
  }
  assert.deepEqual(f.events, [], 'Unrelated page acquired ChatGPT interaction listeners');
  assert.equal(f.reads.selectors, 0, 'Unrelated page DOM was queried');
  assert.equal(f.reads.text, 0, 'Unrelated page text was read');
  assert.equal(f.reads.fetches, 0, 'Unrelated page caused an unrequested request');
  assert.equal(f.editor.value, 'private unsent draft');
}

const denied = [
  ['public HTTPS', 'https://example.org/website', false],
  ['public HTTP', 'http://example.org/website', false],
  ['HTTP ChatGPT', 'http://chatgpt.com/c/route', false],
  ['ChatGPT nondefault port', 'https://chatgpt.com:8443/c/route', false],
  ['ChatGPT subdomain', 'https://other.chatgpt.com/c/route', false],
  ['ChatGPT framed document', 'https://chatgpt.com/c/route', true],
];

for (const [name, url, framed] of denied) {
  test(name + ' retains generic bridge without ChatGPT globals, listeners or content reads', async () => {
    const f = fixture(url, framed);
    try {
      f.install();await flush();noChatSurface(f);
      assert.ok(f.messages.some(value => value.kind === 'documentReady' && value.url === url));
      f.send({kind: 'evaluate', id: 41, code: '({answer:6*7,url:location.href})'});
      const evaluated = f.messages.find(value => value.kind === 'result' && value.id === 41);
      assert.deepEqual(JSON.parse(evaluated.result), {answer: 42, url});
      noChatSurface(f);
      for (const action of ['inspect', 'web-inspect', 'observe-install', 'page-state', 'page-restore',
        'web-transcript', 'transcript', 'poll', 'file-prepare', 'file-point', 'file-followup']) {
        const result = f.call(action, {expectedUrl: url, state: {draft: 'must never be written'}});
        assert.equal(result.ok, false, action + ' must reject this document');
      }
      const result = await f.call('attachment-state', {url, names: ['keep.txt']}, attachments);
      assert.equal(result.ok, false);noChatSurface(f);
    } finally {f.close();}
  });
}

for (const url of ['https://example.org/audit', 'http://example.org/audit']) {
  test(url + ' still executes an explicitly requested fingerprint audit through the actual native bridge', async () => {
    const f = fixture(url);
    try {
      f.install();await flush();noChatSurface(f);
      f.send({kind: 'audit', id: 51, configuration: {id: 'explicit-audit', network: false}});
      assert.equal(f.scripts.length, 1);
      const nonce = JSON.parse(f.scripts[0].getAttribute('data-pocket-audit')).nonce;
      const signal = {ua: 'Controlled Firefox', language: 'zh-CN', languages: ['zh-CN']};
      f.w.dispatchEvent(new f.w.CustomEvent('pocket-audit-observation', {
        detail: JSON.stringify({nonce, provenance: 'page-main-world', parent: signal,
          frame: signal, worker: signal}),
      }));
      await flush();
      const reply = f.messages.find(value => value.kind === 'auditResult' && value.id === 51);
      assert.ok(reply, 'Generic fingerprint audit callback must be preserved');
      const result = JSON.parse(reply.result);
      assert.equal(result.id, 'explicit-audit');assert.equal(result.parent.ua, signal.ua);
      assert.equal(result.provenance, 'page-main-world');assert.equal(result.mainWorld.observed, true);
      assert.equal(f.scripts[0].isConnected, false);noChatSurface(f);
    } finally {f.close();}
  });
}

for (const url of ['https://chatgpt.com/c/route', 'https://chatgpt.com:443/c/route']) {
  test(url + ' retains ChatGPT reading, draft observation and attachment inspection without submission', async () => {
    const f = fixture(url);
    try {
      f.install();await flush();
      assert.equal(typeof f.w.PocketWebReply.postMessage, 'function');
      assert.equal(typeof f.w.__pocketReadingInteraction.revision, 'function');
      assert.equal(typeof f.w.__pocketComposerInteraction.snapshot, 'function');
      assert.ok(f.events.includes('beforeinput') && f.events.includes('pointerdown'));
      f.w.eval(observer);
      assert.equal(f.call('observe-install', {resourceBinding: 'controlled-binding'}).ok, true);
      const inspected = f.call('inspect');
      assert.equal(inspected.composer, true);assert.equal(inspected.draft, 'private unsent draft');
      const file = await f.call('attachment-state', {url, names: ['keep.txt']}, attachments);
      assert.equal(file.ok, true);assert.equal(file.files[0].state, 'ready');
      assert.equal(f.call('submit', {text: 'must not send'}).ok, false);
      assert.equal(f.editor.value, 'private unsent draft');
      f.w.PocketWebReply.postMessage('controlled-reply');
      assert.ok(f.messages.some(value => value.kind === 'reply' && value.text === 'controlled-reply'));
    } finally {f.close();}
  });
}

test('reverting only the exact-origin or top-frame driver admission exposes the controlled negative fixture', async () => {
  const oldDriver = driver.replace("window !== window.top || location.origin !== 'https://chatgpt.com'",
    "location.protocol !== 'https:' || location.hostname !== 'chatgpt.com'");
  const oldAttachments = attachments.replace("window!==window.top||location.origin!=='https://chatgpt.com'",
    "location.protocol!=='https:'||location.hostname!=='chatgpt.com'");
  assert.notEqual(oldDriver, driver);assert.notEqual(oldAttachments, attachments);
  for (const framed of [false, true]) {
    const f = fixture(framed ? 'https://chatgpt.com/c/route' : 'https://chatgpt.com:8443/c/route', framed);
    try {
      assert.equal(f.call('inspect', {}, oldDriver).composer, true);
      assert.equal((await f.call('attachment-state', {names: ['keep.txt']}, oldAttachments)).ok, true);
      assert.ok(f.reads.selectors > 0, 'The denied fixture must exercise a real query when the guard regresses');
    } finally {f.close();}
  }
});
