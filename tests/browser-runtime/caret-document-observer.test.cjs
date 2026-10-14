'use strict';

// Host protocol regression only. Two VM realms model separate page/extension
// globals sharing DOM adapters; they do not establish Gecko isolation or trusted
// Android input. Plain event objects below explicitly model browser callbacks.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const root = path.resolve(__dirname, '../..');
const bridgeSource = fs.readFileSync(path.join(root, 'app/src/main/assets/gecko/content.js'), 'utf8');
const observerPath = path.join(root, 'tests/gecko/assets/caret-document-observer.js');

class Target {
  constructor() { this.listeners = new Map(); }
  addEventListener(type, callback, options) {
    if (!this.listeners.has(type)) this.listeners.set(type, []);
    const listeners = this.listeners.get(type);
    const capture = options === true || !!options?.capture;
    if (!listeners.some(item => item.callback === callback && item.capture === capture))
      listeners.push({callback, capture});
  }
  removeEventListener(type, callback, options) {
    const capture = options === true || !!options?.capture;
    this.listeners.set(type, (this.listeners.get(type) || [])
      .filter(item => item.callback !== callback || item.capture !== capture));
  }
  dispatchEvent(event) {
    for (const {callback} of [...(this.listeners.get(event.type) || [])]) callback(event);
    return !event.defaultPrevented;
  }
  listenerCount() { return [...this.listeners.values()].reduce((sum, rows) => sum + rows.length, 0); }
}

function harness(caseNumber = 0) {
  const url = `http://127.0.0.1:8771/caret?case=${caseNumber}`;
  const state = {caseNumber, draft:'abcdefghij', otherDraft:'untouched independent draft',
    start:5, end:5, direction:'none', focused:false, cookie:'session=synthetic-caret', timeOrigin:123456};
  const writes = [], messages = [], window = new Target(), pageWindow = new Target();
  const document = new Target();
  let clock = 0, nativeReceive, requestId = 0, node;
  const makeNode = (id, tagName = 'TEXTAREA') => {
    const result = new Target();
    Object.assign(result, {id, tagName, ownerDocument:document, isConnected:true, scrollLeft:0,
      getBoundingClientRect:() => ({x:12,y:40,left:12,right:372,top:40,bottom:136,width:360,height:96}),
      contains:other => other === result,
      getAttribute:name => name === 'id' ? id : null,
      closest:selector => selector.includes('button') && tagName === 'BUTTON' ? result : null,
      focus:() => { writes.push('focus'); },
      setSelectionRange:() => { writes.push('setSelectionRange'); },
      setAttribute:name => { writes.push(`attribute:${name}`); },
    });
    for (const [property, key] of [['value',id === 'other-draft' ? 'otherDraft' : 'draft'],
      ['selectionStart','start'],['selectionEnd','end'],['selectionDirection','direction']])
      Object.defineProperty(result, property, {get:() => state[key], set:() => writes.push(property)});
    return result;
  };
  node = makeNode('prompt-textarea');
  const other = makeNode('other-draft'), send = makeNode('send', 'BUTTON');
  document.documentElement = {clientWidth:384, dataset:{caretCase:String(caseNumber)},
    getAttribute:name => name === 'data-caret-case' ? String(state.caseNumber) : null};
  document.body = {innerText:'Controlled original input semantics'};
  document.readyState = 'complete';
  document.fonts = {status:'loaded'};
  document.URL = url;
  document.defaultView = pageWindow;
  Object.defineProperty(document, 'cookie', {get:() => state.cookie, set:() => writes.push('cookie')});
  Object.defineProperty(document, 'activeElement', {get:() => state.focused ? node : document.body,
    set:() => writes.push('activeElement')});
  document.getElementById = id => id === 'prompt-textarea' ? node : id === 'other-draft' ? other : id === 'send' ? send : null;
  document.querySelector = selector => selector.includes('prompt-textarea') || selector.includes('textarea')
    ? node : selector.includes('button') || selector === '#send' ? send : null;
  document.createElement = tag => {
    assert.equal(tag, 'canvas', 'The observer may create only a detached measurement canvas');
    return {getContext:kind => { assert.equal(kind, '2d'); return {font:'',measureText:text => ({width:text.length * 15})}; }};
  };
  document.createRange = () => { writes.push('createRange'); throw Error('Unexpected selection operation'); };
  const location = {href:url, origin:'http://127.0.0.1:8771', pathname:'/caret', search:`?case=${caseNumber}`};
  const performance = {get timeOrigin() { return state.timeOrigin; }, now:() => ++clock};
  const computedStyle = () => ({font:'26px monospace',fontSize:'26px',borderLeftWidth:'1px',
    borderTopWidth:'1px',paddingLeft:'10px',paddingTop:'10px'});
  for (const realmWindow of [window, pageWindow]) Object.assign(realmWindow, {
    document, location, performance, innerWidth:384, innerHeight:720, getComputedStyle:computedStyle,
  });
  window.top = window; pageWindow.top = pageWindow;
  const viewport = {width:384,height:720,scale:1,offsetLeft:0,offsetTop:0,pageLeft:0,pageTop:0,
    addEventListener() {}};
  Object.assign(window, {visualViewport:viewport,devicePixelRatio:1,scrollX:0,scrollY:0});
  const common = {document,location,performance,innerWidth:384,innerHeight:720,scrollX:0,scrollY:0,
    getComputedStyle:computedStyle,URL,URLSearchParams,console};
  const page = vm.createContext({...common, window:pageWindow});
  const extension = vm.createContext({...common, window,
    browser:{runtime:{connectNative(name) {
      assert.equal(name, 'pocketpage');
      return {postMessage:value => messages.push(value),onMessage:{addListener:callback => { nativeReceive = callback; }}};
    }}},
    visualViewport:viewport,devicePixelRatio:1,
    MutationObserver:class { observe() {} disconnect() {} },
    requestAnimationFrame:() => 1,cancelAnimationFrame() {},
    setTimeout:() => 1,clearTimeout() {},
  });
  vm.runInContext(bridgeSource, extension, {filename:'production-gecko-content.js'});
  const configuration = {case:caseNumber,documentUrl:url,sourceCommit:'a'.repeat(40),
    runId:'12345',runAttempt:'1',runNonce:'c'.repeat(32)};
  const evaluate = code => {
    const id = ++requestId;
    nativeReceive({kind:'evaluate',id,code});
    const result = messages.find(item => item.kind === 'result' && item.id === id);
    assert.ok(result, 'Actual production bridge must return this evaluation result');
    return JSON.parse(result.result);
  };
  const observe = (options = configuration) => evaluate(`(${fs.readFileSync(observerPath, 'utf8')})(${JSON.stringify(options)})`);
  const emit = (type, options = {}) => {
    const event = {type,target:node,isTrusted:true,hostEventAdapter:true,key:'',data:null,
      inputType:'',defaultPrevented:false,preventDefault() { this.defaultPrevented = true; },...options};
    // Capture/document listeners and target listeners see the same shared DOM
    // callback object. No Event.isTrusted is fabricated by a browser or SDK.
    document.dispatchEvent(event);
    if (type !== 'selectionchange') event.target.dispatchEvent(event);
    return event;
  };
  const count = () => document.listenerCount() + node.listenerCount() + send.listenerCount();
  return {state,writes,document,window,pageWindow,page,extension,configuration,location,
    get node() { return node; },send,viewport,evaluate,observe,emit,count,
    replaceComposer() { node.isConnected = false; node = makeNode('prompt-textarea'); },
  };
}

test('production extension eval cannot read a page-world snapshot global', () => {
  const f = harness();
  vm.runInContext("window.__caretSnapshot=()=>({ready:true,draft:document.getElementById('prompt-textarea').value});", f.page);
  assert.equal(vm.runInContext('window.__caretSnapshot().ready', f.page), true);
  assert.deepEqual(f.evaluate('window.__caretSnapshot?window.__caretSnapshot():({ready:false})'), {ready:false});
  assert.equal(f.window.__caretSnapshot, undefined);
  assert.deepEqual(f.writes, []);
});

test('isolated observer reads immutable DOM readiness without modifying editor state', () => {
  const f = harness();
  const before = {...f.state};
  const value = f.observe();
  assert.equal(value.ready, true);
  assert.equal(value.case, 0);
  assert.equal(value.draft, before.draft);
  assert.equal(value.otherDraft, before.otherDraft);
  assert.equal(value.start, before.start);
  assert.equal(value.end, before.end);
  assert.equal(value.direction, before.direction);
  assert.equal(value.focused, false);
  assert.equal(value.cookie, before.cookie);
  assert.equal(value.sendCount, 0);
  assert.equal(value.eventCount, 0);
  assert.equal(value.points.length, before.draft.length + 1);
  assert.deepEqual(f.state, before);
  assert.deepEqual(f.writes, []);
  assert.equal(f.pageWindow.__pocketCaretObservation, undefined);
});

test('isolated measured targets include every UTF16 boundary without editing the draft', () => {
  const f = harness(12);
  f.state.draft = 'A😀B'; f.state.start = f.state.end = 3;
  const before = {...f.state};
  const value = f.observe();
  assert.equal(value.ready, true);
  assert.equal(value.points.length, 5);
  assert.deepEqual(value.points.map(point => point.x), [23,38,53,68,83]);
  assert.ok(value.points.every(point => Number.isFinite(point.x) && Number.isFinite(point.y)));
  assert.deepEqual(f.state, before);
  assert.deepEqual(f.writes, []);
});

test('repeat reads install one recorder and retain exact host callback events', () => {
  const f = harness();
  assert.equal(f.observe().ready, true);
  const listenerCount = f.count();
  for (let i = 0; i < 5; i++) assert.equal(f.observe().ready, true);
  assert.equal(f.count(), listenerCount);
  f.state.focused = true;
  f.emit('focus');
  f.emit('keydown', {key:'Q'});
  f.emit('beforeinput', {data:'Q',inputType:'insertText'});
  f.state.draft = 'abcdeQfghij'; f.state.start = f.state.end = 6;
  f.emit('input', {data:'Q',inputType:'insertText'});
  f.emit('compositionstart', {data:''});
  f.emit('compositionupdate', {data:'中',isComposing:true});
  f.emit('compositionend', {data:'中'});
  f.emit('select');
  f.emit('selectionchange');
  const value = f.observe();
  assert.equal(value.eventCount, 9);
  assert.equal(value.keyCount, 1);
  assert.equal(value.characterKeyCount, 1);
  assert.equal(value.qKeyCount, 1);
  assert.equal(value.beforeCount, 1);
  assert.equal(value.inputCount, 1);
  assert.equal(value.compositionCount, 1);
  assert.equal(value.compositionEndCount, 1);
  assert.deepEqual(value.events.map(event => event.index), Array.from({length:9}, (_, index) => index));
  assert.equal(value.events[1].draft, 'abcdefghij');
  assert.equal(value.events[3].draft, 'abcdeQfghij');
  assert.equal(value.events[3].start, 6);
  assert.equal(value.allTrusted, true, 'Only explicit host callback adapter flags are counted');
  assert.equal(value.focused, true);
  assert.deepEqual(f.observe().events, value.events);
  assert.equal(f.count(), listenerCount);
  assert.deepEqual(f.writes, []);
});

test('layout viewport changes remain separate from passive visual geometry', () => {
  const f = harness();
  const original = f.observe();
  assert.equal(original.ready, true);
  f.extension.innerHeight = f.window.innerHeight = 989;
  f.viewport.height = 667;
  f.viewport.offsetTop = 7;
  f.viewport.pageTop = 12;
  f.extension.scrollY = f.window.scrollY = 5;
  const value = f.observe();
  assert.equal(value.height, 989);
  assert.deepEqual(value.viewport, {width:384,height:667,scale:1,
    offsetLeft:0,offsetTop:7,pageLeft:0,pageTop:12});
  assert.equal(value.devicePixelRatio, 1);
  assert.equal(value.scrollX, 0);
  assert.equal(value.scrollY, 5);
  assert.equal(value.readyState, 'complete');
  assert.equal(value.documentFontsLoaded, true);
  assert.deepEqual(value.points, original.points,
    'Text measurement must not scale CSS points by layout viewport height');
  assert.deepEqual(f.writes, []);
});

test('rejected-input fixture records cancellation and isolated send count', () => {
  const f = harness(10); f.state.draft = 'rejected draft'; f.state.start = f.state.end = 4;
  assert.equal(f.observe().ready, true);
  f.emit('keydown', {key:'Q'});
  const rejected = f.emit('beforeinput', {data:'Q',inputType:'insertText'});
  assert.equal(rejected.defaultPrevented, true);
  f.emit('keyup', {key:'Q'});
  f.emit('click', {target:f.send});
  const value = f.observe();
  assert.equal(value.draft, 'rejected draft');
  assert.equal(value.start, 4);
  assert.equal(value.end, 4);
  assert.equal(value.inputCount, 0);
  assert.equal(value.beforeCount, 1);
  assert.equal(value.qKeyCount, 1);
  assert.equal(value.events.find(event => event.type === 'beforeinput').prevented, true);
  assert.equal(value.sendCount, 1);
  assert.deepEqual(f.writes, []);
});

test('raw callback storage is bounded and signals lost evidence', () => {
  const f = harness(); assert.equal(f.observe().ready, true);
  for (let i = 0; i < 513; i++) f.emit('keydown', {key:'Q'});
  const value = f.observe();
  assert.equal(value.events.length, 512);
  assert.equal(value.eventCount, 512);
  assert.equal(value.overflow, true);
  assert.equal(value.events.at(-1).index, 511);
});

for (const [name, field, value] of [['source','sourceCommit','b'.repeat(40)],['run','runId','12346'],
  ['attempt','runAttempt','2'],['nonce','runNonce','d'.repeat(32)],['case','case',1],
  ['URL','documentUrl','http://127.0.0.1:8771/caret?case=1']]) {
  test(`foreign ${name} cannot reuse an existing isolated observer`, () => {
    const f = harness(); assert.equal(f.observe().ready, true); const listeners = f.count();
    assert.equal(f.observe({...f.configuration,[field]:value}).ready, false);
    assert.equal(f.count(), listeners);
    assert.deepEqual(f.writes, []);
  });
}

test('changed document object, time origin, node, URL, and case cannot revive old observation', () => {
  for (const mutate of [f => { f.state.timeOrigin++; },f => f.replaceComposer(),
    f => { f.extension.document = Object.create(f.document); },
    f => { f.location.href += '#foreign-document'; },f => { f.state.caseNumber = 1; }]) {
    const f = harness(); assert.equal(f.observe().ready, true); const listeners = f.count();
    mutate(f);
    assert.equal(f.observe().ready, false);
    assert.ok(f.count() <= listeners, 'A stale observation cannot install replacement listeners');
    assert.deepEqual(f.writes, []);
  }
});
