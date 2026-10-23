const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const {JSDOM} = require(process.env.JSDOM_MODULE || 'jsdom');
const script = fs.readFileSync(process.env.APPEARANCE_SCRIPT || 'app/src/main/assets/gecko/appearance.js', 'utf8');
const settle = () => new Promise(resolve => setTimeout(resolve, 0));

function page(t, {url = 'https://chatgpt.com/c/test', dark = true, missingRoot = false} = {}) {
  const dom = new JSDOM(`<html class="light official-page"><head><style>
    html.light body { background: rgb(255, 255, 255); color: rgb(0, 0, 0); }
    html.dark body { background: rgb(33, 33, 33); color: rgb(236, 236, 236); }
    </style></head><body><textarea id="input">中文草稿</textarea><div id="reply">回复</div></body></html>`,
    {url, runScripts: 'outside-only'});
  t.after(() => dom.window.close());
  const w = dom.window, root = w.document.documentElement;
  w.localStorage.setItem('theme', 'light');
  w.localStorage.setItem('draft', '中文草稿');
  w.document.cookie = 'session=synthetic';
  const media = new w.EventTarget(); media.matches = dark;
  w.matchMedia = () => media;
  const registrations = [], NativeObserver = w.MutationObserver;
  let callbacks = 0;
  w.MutationObserver = class extends NativeObserver {
    constructor(callback) { super((...args) => { callbacks++; callback(...args); }); }
    observe(target, options) { registrations.push(options); super.observe(target, options); }
  };
  const input = w.document.getElementById('input'); input.focus(); input.setSelectionRange(2, 3);
  if (missingRoot) root.remove();
  w.eval(script);
  const mode = value => {
    media.matches = value; const event = new w.Event('change'); event.matches = value; media.dispatchEvent(event);
  };
  return {w, root, input, mode, registrations, callbacks: () => callbacks};
}

function darkPage(w) {
  assert.equal(w.getComputedStyle(w.document.body).backgroundColor, 'rgb(33, 33, 33)');
  assert.equal(w.getComputedStyle(w.document.body).color, 'rgb(236, 236, 236)');
  assert.equal(w.document.documentElement.style.colorScheme, 'dark');
}

test('startup uses Gecko preference before native handshake despite saved light theme', async t => {
  const {w} = page(t); await settle(); darkPage(w);
  assert.equal(w.localStorage.getItem('theme'), 'dark');
});

test('late hydration and SPA navigation cannot leave the official page white', async t => {
  const {w, root, input} = page(t); w.PocketAppearance.apply(true); await settle();
  for (const path of ['/c/first', '/c/second']) {
    w.history.pushState({}, '', path);
    w.localStorage.setItem('theme', 'light'); root.className = 'light official-page'; root.style.colorScheme = 'light';
    await settle(); darkPage(w);
    assert.ok(root.classList.contains('official-page'));
    assert.equal(w.document.getElementById('input'), input);
    assert.equal(w.document.activeElement, input);
    assert.equal(input.value, '中文草稿'); assert.equal(input.selectionStart, 2); assert.equal(input.selectionEnd, 3);
    assert.equal(w.localStorage.getItem('draft'), '中文草稿'); assert.equal(w.document.cookie, 'session=synthetic');
    assert.equal(w.location.pathname, path);
  }
});

test('root style reset is repaired and streaming replies do not trigger theme work', async t => {
  const p = page(t); p.w.PocketAppearance.apply(true); await settle();
  p.root.style.cssText = '--website-layout: 12px; color-scheme: light'; await settle(); darkPage(p.w);
  assert.equal(p.root.style.getPropertyValue('--website-layout'), '12px');
  const count = p.callbacks();
  for (let i = 0; i < 300; i++) p.w.document.getElementById('reply').textContent += '字';
  await settle(); assert.equal(p.callbacks(), count);
  assert.ok(p.registrations.every(options => !options.subtree));
  await settle(); assert.equal(p.callbacks(), count, 'no self-triggered theme loop');
});

test('system changes and explicit app choices switch both directions without replacing content', async t => {
  const {w, root, input, mode} = page(t); await settle(); mode(false); await settle();
  assert.equal(w.getComputedStyle(w.document.body).backgroundColor, 'rgb(255, 255, 255)');
  mode(true); await settle(); darkPage(w);
  w.PocketAppearance.apply(false); await settle(); assert.ok(root.classList.contains('light'));
  root.className = 'dark'; await settle(); assert.ok(root.classList.contains('light'));
  assert.equal(w.document.getElementById('input'), input); assert.equal(input.value, '中文草稿');
});

test('document_start without html, root replacement and page cache restore stay synchronized', async t => {
  const {w, root} = page(t, {missingRoot: true});
  w.document.append(root); await settle(); darkPage(w);
  const replacement = root.cloneNode(true); replacement.className = 'light'; root.replaceWith(replacement);
  await settle(); darkPage(w);
  w.dispatchEvent(new w.Event('pagehide')); replacement.className = 'light'; await settle();
  assert.ok(replacement.classList.contains('light'), 'suspended page observer is disconnected');
  w.PocketAppearance.apply(true); w.dispatchEvent(new w.Event('pageshow')); await settle(); darkPage(w);
});

test('native dark choice wins over later privacy media-query changes', async t => {
  const {w, root, input, mode} = page(t, {dark: false});
  w.PocketAppearance.apply(true); await settle(); darkPage(w);
  mode(false); root.style.colorScheme = 'light'; await settle(); darkPage(w);
  assert.equal(w.document.getElementById('input'), input);
  w.PocketAppearance.apply(false); mode(true); await settle();
  assert.ok(root.classList.contains('light'));
  assert.equal(w.localStorage.getItem('theme'), 'light');
});

test('login providers and lookalike origins are not modified or observed', async t => {
  for (const url of ['https://accounts.google.com/', 'https://auth.openai.com/', 'http://chatgpt.com/', 'https://chatgpt.com.example/']) {
    const p = page(t, {url}); await settle(); assert.equal(p.w.PocketAppearance.apply(true), false);
    assert.ok(p.root.classList.contains('light')); assert.equal(p.w.localStorage.getItem('theme'), 'light');
    assert.equal(p.registrations.length, 0);
  }
});
