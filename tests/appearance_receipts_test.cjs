// Controlled DOM/stylesheet faults. These tests do not represent the live ChatGPT website or Gecko pixels.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const {JSDOM} = require(process.env.JSDOM_MODULE || 'jsdom');
const script = fs.readFileSync('app/src/main/assets/gecko/appearance.js', 'utf8');
const documentId = 'controlled-document-123456';

function page(t, {url = 'https://chatgpt.com/c/synthetic', forcedWhite = false, transparent = false, noChat = false} = {}) {
  const base = transparent ? 'html,body,main,#prompt-textarea{background:transparent}' : 'html,body,main,#prompt-textarea{background:rgb(255,255,255);color:rgb(0,0,0)}html.dark,html.dark body,html.dark main,html.dark #prompt-textarea{background:rgb(33,33,33);color:rgb(236,236,236)}';
  const dom = new JSDOM(`<html class="light"><head><style>${base}${forcedWhite ? 'main{background:white!important}' : ''}</style></head><body>${noChat ? '<div>not a chat region</div>' : '<main>synthetic chat content<textarea id="prompt-textarea">synthetic draft</textarea></main>'}</body></html>`,
    {url, runScripts: 'outside-only', pretendToBeVisual: true});
  const w = dom.window;
  // jsdom has no layout. Supply visible rectangles only; computed CSS colors remain its own.
  w.HTMLElement.prototype.getBoundingClientRect = function() { return this.id === 'prompt-textarea'
    ? {width: 340, height: 60, top: 400, left: 10, right: 350, bottom: 460}
    : {width: 360, height: 500, top: 0, left: 0, right: 360, bottom: 500}; };
  w.document.elementFromPoint = (x, y) => y >= 400 ? w.document.querySelector('textarea') : w.document.querySelector('main');
  w.localStorage.setItem('theme', 'light'); w.localStorage.setItem('draft', 'unrelated saved draft'); w.document.cookie = 'session=synthetic';
  w.eval(script);
  t.after(() => { w.dispatchEvent(new w.Event('pagehide')); w.close(); });
  return w;
}
function command(version = 1, dark = true, document = documentId) {
  return {protocol: 1, documentId: document, version, dark};
}
function observed(w, request = command()) {
  const receipts = [];
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(Error('No bounded color observation')), 1400);
    const accepted = w.PocketAppearance.synchronize(request, value => {
      receipts.push(value);
      if (value.stage === 'observed') { clearTimeout(timer); resolve({value, receipts}); }
    });
    if (!accepted) { clearTimeout(timer); reject(Error('Request rejected')); }
  });
}

test('receipt stages separate delivery, settings and actual controlled region colors', async t => {
  const w = page(t), input = w.document.querySelector('textarea'); input.focus(); input.setSelectionRange(2, 5);
  const {value, receipts} = await observed(w);
  assert.deepEqual(receipts.slice(0, 2).map(row => row.stage), ['received', 'applied']);
  assert.equal(value.colorStatus, 'verified'); assert.equal(value.attributesApplied, true);
  assert.ok(['written', 'unchanged'].includes(value.storage));
  const chat = value.samples.filter(row => row.region === 'main' || row.region === 'composer');
  assert.equal(chat.length, 2); assert.ok(chat.every(row => row.visible && row.backgroundLuminance < .35));
  assert.ok(receipts.every(row => row.documentId === documentId && row.version === 1 && row.dark === true));
  assert.equal(w.document.querySelector('textarea'), input); assert.equal(w.document.activeElement, input);
  assert.equal(input.value, 'synthetic draft'); assert.equal(input.selectionStart, 2); assert.equal(input.selectionEnd, 5);
  assert.equal(w.localStorage.getItem('draft'), 'unrelated saved draft'); assert.equal(w.document.cookie, 'session=synthetic');
  const encoded = JSON.stringify(receipts); assert.ok(!encoded.includes('synthetic')); assert.ok(!encoded.includes('/c/'));
});

test('dark attributes cannot confirm a main region still forced white', async t => {
  const w = page(t, {forcedWhite: true}); const {value} = await observed(w);
  assert.equal(value.attributesApplied, true); assert.equal(value.colorStatus, 'mismatch');
  assert.equal(value.reason, 'color-mismatch');
  assert.equal(value.samples.find(row => row.region === 'main').backgroundLuminance, 1);
});

test('storage write failure reports incomplete persistence without hiding applied colors', async t => {
  const w = page(t); Object.defineProperty(w, 'localStorage', {value: {getItem: () => 'light', setItem() { throw Error('private exception text'); }}});
  const {value} = await observed(w);
  assert.equal(value.attributesApplied, true); assert.equal(value.storage, 'failed');
  assert.equal(value.colorStatus, 'verified'); assert.equal(value.reason, 'storage-write-failed');
  assert.ok(!JSON.stringify(value).includes('private exception')); assert.equal(w.PocketAppearance.apply(true), false);
});

test('blocked storage reads remain unavailable rather than successful', async t => {
  const w = page(t); Object.defineProperty(w, 'localStorage', {get() { throw Error('blocked'); }});
  const {value} = await observed(w); assert.equal(value.storage, 'unavailable'); assert.equal(value.reason, 'storage-unavailable');
});

test('sampling rereads a preference changed after applying rather than reusing an old success', async t => {
  const w = page(t), pending = observed(w);
  await new Promise(resolve => setTimeout(resolve, 120));
  w.localStorage.setItem('theme', 'light');
  const {value} = await pending;
  assert.equal(value.colorStatus, 'verified'); assert.equal(value.storage, 'failed');
  assert.equal(value.reason, 'storage-preference-mismatch'); assert.equal(w.localStorage.getItem('theme'), 'light');
});

test('a transparent ancestor cannot confirm an unpainted dark chat region', async t => {
  const w = page(t); w.document.body.style.opacity = '0';
  const {value} = await observed(w); assert.equal(value.colorStatus, 'unavailable');
  assert.ok(value.samples.filter(row => ['main', 'composer'].includes(row.region)).every(row => !row.visible));
});

test('a white overlay outside the chat region prevents color confirmation', async t => {
  const w = page(t), overlay = w.document.createElement('div'); overlay.style.background = 'white'; w.document.body.append(overlay);
  w.document.elementFromPoint = () => overlay;
  const {value} = await observed(w); assert.equal(value.colorStatus, 'unavailable');
});

test('the measured painted descendant can expose a white chat surface inside a dark main', async t => {
  const w = page(t), surface = w.document.createElement('div'); surface.style.background = 'white'; w.document.querySelector('main').append(surface);
  w.document.elementFromPoint = (x, y) => y >= 400 ? w.document.querySelector('textarea') : surface;
  const {value} = await observed(w); assert.equal(value.colorStatus, 'mismatch');
  assert.equal(value.samples.find(row => row.region === 'main').backgroundLuminance, 1);
});

test('a transparent dark hit descendant cannot conceal its white parent', async t => {
  const w = page(t, {forcedWhite: true}), hit = w.document.createElement('div');
  hit.style.background = 'rgb(33,33,33)'; hit.style.opacity = '0'; w.document.querySelector('main').append(hit);
  w.document.elementFromPoint = (x, y) => y >= 400 ? w.document.querySelector('textarea') : hit;
  const {value} = await observed(w); assert.equal(value.colorStatus, 'unavailable');
  assert.equal(value.samples.find(row => row.region === 'main').visible, false);
});

test('an unrelated root and absent chat regions never confirm webpage colors', async t => {
  const w = page(t, {noChat: true}); const {value} = await observed(w);
  assert.equal(value.colorStatus, 'unavailable'); assert.equal(value.reason, 'chat-region-unavailable');
});

test('a transparent unknown canvas is not assumed to match the native preference', async t => {
  const w = page(t, {transparent: true}); const {value} = await observed(w);
  assert.equal(value.colorStatus, 'unavailable'); assert.equal(value.reason, 'color-unavailable');
  assert.ok(value.samples.filter(row => ['main', 'composer'].includes(row.region)).every(row => row.backgroundLuminance === null));
});

test('a hidden document reports unavailable without waiting for a suspended animation frame', async t => {
  const w = page(t); Object.defineProperty(w.document, 'visibilityState', {value: 'hidden', configurable: true});
  w.requestAnimationFrame = () => assert.fail('hidden document must not depend on RAF');
  const {value} = await observed(w); assert.equal(value.colorStatus, 'unavailable');
  assert.equal(value.reason, 'page-hidden'); assert.equal(value.samples.length, 0);
});

test('old versions and another document cannot overwrite a newer native choice', async t => {
  const w = page(t), rows = [];
  assert.equal(w.PocketAppearance.synchronize(command(10, true), row => rows.push(row)), true);
  const current = observed(w, command(11, false));
  assert.equal(w.PocketAppearance.synchronize(command(10, true), () => assert.fail('stale receipt')), false);
  assert.equal(w.PocketAppearance.synchronize(command(12, true, 'another-document-1234'), () => assert.fail('wrong document')), false);
  const {value} = await current; assert.equal(value.version, 11); assert.equal(value.dark, false); assert.equal(value.colorStatus, 'verified');
  assert.ok(!rows.some(row => row.stage === 'observed')); assert.ok(w.document.documentElement.classList.contains('light'));
});

test('repeating the same chosen theme starts a fresh measured native version', async t => {
  const w = page(t); await observed(w, command(1)); const {value} = await observed(w, command(2));
  assert.equal(value.version, 2); assert.equal(value.colorStatus, 'verified'); assert.equal(value.dark, true);
});

test('page suspension cancels a pending measurement and resumes without replacement', async t => {
  const w = page(t), rows = [], input = w.document.querySelector('textarea');
  w.PocketAppearance.synchronize(command(1), row => rows.push(row));
  w.dispatchEvent(new w.Event('pagehide')); await new Promise(resolve => setTimeout(resolve, 450));
  assert.ok(!rows.some(row => row.stage === 'observed'));
  assert.equal(w.PocketAppearance.synchronize(command(2), () => {}), false);
  w.dispatchEvent(new w.Event('pageshow')); const {value} = await observed(w, command(2));
  assert.equal(value.colorStatus, 'verified'); assert.equal(w.document.querySelector('textarea'), input);
});

test('login/lookalike origins reject synchronization and do not touch their theme', t => {
  for (const url of ['https://auth.openai.com/', 'https://accounts.google.com/', 'http://chatgpt.com/', 'https://chatgpt.com.example/']) {
    const w = page(t, {url}); assert.equal(w.PocketAppearance.synchronize(command(), () => assert.fail('foreign receipt')), false);
    assert.equal(w.localStorage.getItem('theme'), 'light');
  }
});
