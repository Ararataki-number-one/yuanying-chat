'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const root=path.resolve(__dirname,'../..');
const fixture=fs.readFileSync(path.join(root,'tests/gecko/run_ui_visuals.py'),'utf8');
const java=fs.readFileSync(path.join(root,'tests/gecko/ChromeCollapseIntegration.java'),'utf8');
const script=fixture.match(/body=body\.replace\(b'<\/html>',b'''<script>([\s\S]*?)<\/script><\/html>'''\)/)?.[1];
assert.ok(script,'The actual controlled HTTP fixture must supply its page-world observer');
function constant(name){
  const match=java.match(new RegExp('static final String '+name+'=("(?:[^"\\\\]|\\\\.)*");'));
  assert.ok(match,'Actual Android snapshot constant '+name);return JSON.parse(match[1]);
}
const read=constant('TELEMETRY'),ready=constant('TELEMETRY_READY');
function setup(){
  const document={documentElement:{dataset:{reloadDocument:'controlled-document'}}};
  const listeners=new Map();let time=0;
  const page={document,navigator:{maxTouchPoints:1},TouchEvent:function(){},PointerEvent:function(){},
    matchMedia:()=>({matches:false}),performance:{now:()=>++time},scrollY:0,
    addEventListener:(type,listener,options)=>listeners.set(type,{listener,options})};
  page.window=page;const main=vm.createContext(page);
  const isolated=vm.createContext({document,window:{}});
  vm.runInContext(script,main);
  const snapshot=()=>vm.runInContext('(()=>{const t='+read+';return {ready:'+ready+',trace:t};})()',isolated);
  // Host callbacks are explicitly synthetic and untrusted. No Android input or browser trust is claimed.
  const emit=(type,extra={})=>listeners.get(type).listener(Object.freeze({type,isTrusted:false,clientX:10,clientY:20,...extra}));
  return {document,page,main,isolated,listeners,snapshot,emit};
}
test('The old page-window global is absent from the separate extension global',()=>{
  const f=setup();vm.runInContext('window.__chromeTouches=[{type:"touchend",trusted:false}]',f.main);
  assert.equal(vm.runInContext('(window.__chromeTouches||[]).length',f.isolated),0);
});
test('The actual shared-DOM expression reads registered page-world telemetry',()=>{
  const f=setup(),value=f.snapshot();assert.equal(value.ready,true);assert.equal(value.trace.realm,'page-main-world');
  assert.equal(value.trace.document,'controlled-document');assert.equal(value.trace.events.length,0);
});
test('The fixture retains the required touchend listener and diagnostic input families',()=>{
  const f=setup();for(const type of ['touchstart','touchmove','touchend','touchcancel','pointerdown','pointerup','pointercancel','mousedown','mouseup','scroll'])assert.ok(f.listeners.has(type));
});
test('All page observers are passive capture listeners',()=>{
  const f=setup();for(const value of f.listeners.values()){assert.equal(value.options.passive,true);assert.equal(value.options.capture,true);}
});
test('A synthetic callback produces a visible record without fabricating trust',()=>{
  const f=setup();f.emit('touchend');const events=f.snapshot().trace.events;
  assert.equal(events.length,1);assert.equal(events[0].type,'touchend');assert.equal(events[0].trusted,false);
});
test('Touch end coordinates come from changedTouches',()=>{
  const f=setup();f.emit('touchend',{changedTouches:[{clientX:31,clientY:47}]});const event=f.snapshot().trace.events[0];
  assert.equal(event.x,31);assert.equal(event.y,47);
});
test('Diagnostic pointer and scroll values are observed rather than synthesized',()=>{
  const f=setup();f.page.scrollY=93;f.emit('pointercancel',{pointerType:'touch'});const event=f.snapshot().trace.events[0];
  assert.equal(event.pointerType,'touch');assert.equal(event.scrollY,93);assert.equal(event.trusted,false);
});
test('Capabilities are reported by the page execution context',()=>{
  const f=setup(),caps=f.snapshot().trace.capabilities;assert.equal(caps.touchEvent,true);assert.equal(caps.pointerEvent,true);assert.equal(caps.maxTouchPoints,1);
});
test('Bounded telemetry retains monotonic sequences and an honest dropped count',()=>{
  const f=setup();for(let i=0;i<270;i++)f.emit('mousemove');const trace=f.snapshot().trace;
  assert.equal(trace.count,270);assert.equal(trace.events.length,256);assert.equal(trace.dropped,14);
  assert.equal(trace.events[0].sequence,15);assert.equal(trace.events.at(-1).sequence,270);assert.ok(trace.events.every(event=>event.trusted===false));
});
test('An isolated-world decoy global cannot replace the shared-DOM observations',()=>{
  const f=setup();vm.runInContext('window.__chromeTouches=[{type:"decoy"}]',f.isolated);f.emit('touchend');
  assert.equal(f.snapshot().trace.events[0].type,'touchend');
});
test('A different document marker fails the actual readiness expression',()=>{
  const f=setup();f.document.documentElement.dataset.reloadDocument='different-document';assert.equal(f.snapshot().ready,false);
});
test('Malformed shared evidence fails instead of becoming an empty accepted trace',()=>{
  const f=setup();f.document.documentElement.dataset.chromeInputEvidence='{broken';assert.throws(f.snapshot);
});
