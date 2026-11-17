/* Exact production observer with the established synthetic DOM/gesture fixture.
 * Tests finite work guards and disabled capture, not Android or phone timing. */
'use strict';
const fs=require('node:fs'),path=require('node:path'),test=require('node:test'),assert=require('node:assert/strict');
const fixtureSource=fs.readFileSync(path.join(__dirname,'resource-web-observer.cjs'),'utf8').split("test('Initial resource state")[0];
const fixture=new Function('require','__dirname',fixtureSource+'\nreturn fixture;')(require,__dirname);
const nonce='12345678-1234-1234-1234-123456789abc';
test('Finite guard returns fresh unchanged idle state without any response capture',t=>{
 const f=fixture();t.after(f.close);f.install('owned-binding');f.flush(250);const old=f.resources().at(-1),draft=f.window.document.querySelector('textarea').value,cookie=f.window.document.cookie;
 assert.equal(f.window.__pocketWebReplyObserver.requestResources(nonce),true);const current=f.resources().at(-1);
 assert.equal(current.guardRequestId,nonce);assert.equal(current.resourceBinding,'owned-binding');assert.equal(current.documentId,old.documentId);assert.equal(current.resourceSequence,old.resourceSequence+1);assert.equal(current.busy,false);assert.equal(current.uploading,false);
 assert.equal(Object.hasOwn(current,'prompt'),false);assert.equal(Object.hasOwn(current,'markdown'),false);assert.equal(f.window.document.querySelector('textarea').value,draft);assert.equal(f.window.document.cookie,cookie);
});
test('Disabled optional capture still permits finite busy and file guards',t=>{
 const f=fixture();t.after(f.close);f.window.__pocketReplyObservationAllowed=false;f.install('owned-binding');f.flush(250);f.busy(true);f.uploading(true);
 f.window.__pocketWebReplyObserver.requestResources(nonce);const current=f.resources().at(-1);assert.equal(current.busy,true);assert.equal(current.uploading,true);assert.equal(current.guardRequestId,nonce);assert.deepEqual(f.posts.filter(row=>['bound','intent','uncertain'].includes(row.type)),[]);
});
test('Trusted composer input keeps a short resource guard without a send-result task',t=>{
 const f=fixture();t.after(f.close);f.install('owned-binding');f.flush(250);
 f.api.messages=()=>{throw new Error('No send-result message scan');};f.api.draft=()=>{throw new Error('No native prompt capture');};
 const button=f.window.document.querySelector('[data-testid="send-button"]');
 for(const receive of f.handlers.get('click'))receive({isTrusted:true,target:button});
 f.window.__pocketWebReplyObserver.requestResources(nonce);assert.equal(f.resources().at(-1).busy,true);
 assert.equal(f.scheduled(1500),1);assert.equal(f.scheduled(45000),0);assert.equal(f.scheduled(30),0);
 f.advance(1501);f.flush(1500);f.flush(250);assert.equal(f.resources().at(-1).busy,false);
 assert.deepEqual(f.posts.filter(row=>['intent','bound','uncertain','stop'].includes(row.type)),[]);
 assert.equal(f.window.document.querySelector('textarea').value,'original unsent draft');
});
test('Resource busy and uploading stay independent after send-result detection removal',t=>{
 const f=fixture();t.after(f.close);f.install();f.flush(250);
 f.window.__pocketReplyObservationAllowed=false;f.busy(true);f.uploading(true);
 f.api.messages=()=>{throw new Error('Result detection is removed');};
 f.window.__pocketWebReplyObserver.requestResources(nonce);
 assert.equal(f.resources().at(-1).busy,true);assert.equal(f.resources().at(-1).uploading,true);
 assert.equal(f.window.__pocketWebReplyObserver.setObservationAllowed,undefined);
});
test('Malformed guard nonces cannot emit observations or alter files',t=>{
 const f=fixture();t.after(f.close);f.install();f.flush(250);const before=f.posts.length;
 for(const request of ['',null,'prefix/'+nonce+'/injected',{},'x'.repeat(81)])assert.equal(f.window.__pocketWebReplyObserver.requestResources(request),false);
 assert.equal(f.posts.length,before);
});


test('Enter, modified Enter and IME gestures never capture a prompt or enumerate messages',t=>{
 const f=fixture();t.after(f.close);f.install();f.flush(250);const input=f.window.document.querySelector('textarea');
 f.api.messages=()=>{throw new Error('No message scan');};f.api.draft=()=>{throw new Error('No prompt capture');};
 for(const details of [{key:'Enter'},{key:'Enter',shiftKey:true},{key:'Enter',isComposing:true,keyCode:229}])
  for(const receive of f.handlers.get('keydown'))receive({isTrusted:true,target:input,...details});
 assert.deepEqual(f.posts.filter(row=>['intent','bound','uncertain','stop'].includes(row.type)),[]);
 assert.equal(f.scheduled(1500),1);assert.equal(f.scheduled(45000),0);assert.equal(input.value,'original unsent draft');
});
test('A minute without a response cannot create an uncertain-send receipt',t=>{
 const f=fixture();t.after(f.close);f.install();f.flush(250);const input=f.window.document.querySelector('textarea');
 for(const receive of f.handlers.get('keydown'))receive({isTrusted:true,target:input,key:'Enter'});
 f.advance(60000);f.flush(1500);f.flush(250);f.flush(45000);
 assert.deepEqual(f.posts.filter(row=>['intent','bound','uncertain','stop'].includes(row.type)),[]);assert.equal(f.scheduled(45000),0);
});
test('Conversation navigation carries resources but no send-result binding',async t=>{
 const f=fixture();t.after(f.close);f.install();f.flush(50);f.flush(250);
 f.window.history.pushState({},'','/c/another-conversation');f.window.dispatchEvent(new f.window.PopStateEvent('popstate'));
 await f.settle();f.flush(50);f.flush(250);
 assert.equal(f.resources().at(-1).url,'https://chatgpt.com/c/another-conversation');
 assert.deepEqual(f.posts.filter(row=>['intent','bound','uncertain','stop'].includes(row.type)),[]);
});
test('Old background-policy flags cannot reactivate removed confirmation timers',t=>{
 const f=fixture();t.after(f.close);f.window.__pocketReplyObservationAllowed=false;f.install();f.flush(250);
 f.window.__pocketReplyObservationAllowed=true;f.install();f.advance(60000);f.flush(45000);f.flush(30);
 assert.equal(f.window.__pocketWebReplyObserver.setObservationAllowed,undefined);assert.equal(f.scheduled(45000),0);
 assert.deepEqual(f.posts.filter(row=>['intent','bound','uncertain','stop'].includes(row.type)),[]);
});
test('Website stop controls never become native stopped-result receipts',async t=>{
 const f=fixture();t.after(f.close);f.install();f.flush(250);f.busy(true);await f.settle();f.flush(250);
 const stop=f.window.document.querySelector('[data-testid="stop-button"]');for(const receive of f.handlers.get('click'))receive({isTrusted:true,target:stop});
 f.busy(false);await f.settle();f.flush(250);
 assert.equal(f.resources().at(-1).busy,false);assert.equal(f.posts.filter(row=>row.type==='stop').length,0);
});
test('Repeated composer interactions keep only one bounded guard release timer',t=>{
 const f=fixture();t.after(f.close);f.install();f.flush(250);const input=f.window.document.querySelector('textarea');
 for(let i=0;i<100;i++){f.advance(1);for(const receive of f.handlers.get('keydown'))receive({isTrusted:true,target:input,key:'a'});}
 assert.equal(f.scheduled(1500),1);assert.equal(f.scheduled(250),1);assert.equal(f.scheduled(45000),0);
 f.advance(1501);f.flush(1500);f.flush(250);assert.equal(f.resources().at(-1).busy,false);
});
test('Explicit attachment removal evidence stays name and route scoped',async t=>{
 const f=fixture();t.after(f.close);f.install();f.flush(250);const zone=f.window.document.getElementById('upload-zone');
 zone.innerHTML='<div data-file-name="photo.png"><button type="button" aria-label="Remove file">Remove</button></div>';
 await f.settle();f.flush(250);const since=f.window.Date.now();f.advance(1);
 const remove=zone.querySelector('button');for(const receive of f.handlers.get('click'))receive({isTrusted:true,target:remove});
 const api=f.window.__pocketWebReplyObserver;assert.equal(api.attachmentEvidence('photo.png',since).removed,true);
 assert.equal(api.attachmentEvidence('other.png',since).removed,false);assert.equal(api.attachmentEvidence('photo.png',since).sent,undefined);
 f.window.history.replaceState({},'','/c/other');assert.equal(api.attachmentEvidence('photo.png',since).removed,false);
});
test('A finite busy guard is followed by idle after the actual interaction window expires',t=>{
 const f=fixture();t.after(f.close);f.install();f.flush(250);const input=f.window.document.querySelector('textarea');
 for(const receive of f.handlers.get('keydown'))receive({isTrusted:true,target:input,key:'x'});
 f.window.__pocketWebReplyObserver.requestResources(nonce);const busy=f.resources().at(-1);assert.equal(busy.busy,true);
 f.advance(1501);f.flush(1500);f.flush(250);const idle=f.resources().at(-1);
 assert.equal(idle.busy,false);assert.equal(idle.resourceSequence,busy.resourceSequence+1);
});
test('Unrelated trusted page clicks do not mark a composer interaction',t=>{
 const f=fixture();t.after(f.close);f.install();f.flush(250);
 for(const receive of f.handlers.get('click'))receive({isTrusted:true,target:f.window.document.getElementById('unrelated')});
 assert.equal(f.window.__pocketWebReplyObserver.lastGestureAt(),0);assert.equal(f.scheduled(1500),0);
});
test('Untrusted input cannot take a resource guard or alter the restoration timestamp',t=>{
 const f=fixture();t.after(f.close);f.install();f.flush(250);const input=f.window.document.querySelector('textarea');
 for(const receive of f.handlers.get('keydown'))receive({isTrusted:false,target:input,key:'Enter'});
 assert.equal(f.window.__pocketWebReplyObserver.lastGestureAt(),0);assert.equal(f.scheduled(1500),0);
 f.window.__pocketWebReplyObserver.requestResources(nonce);assert.equal(f.resources().at(-1).busy,false);
});
test('The public page driver rejects removed result commands before reading any DOM',()=>{
 const vm=require('node:vm'),driver=fs.readFileSync(path.join(__dirname,'../app/src/main/assets/page-driver.js'),'utf8');
 for(const action of ['poll','latest','submit','message-regenerate-submit']){
  const context={__ACTION__:action,__ARG__:{}};Object.defineProperty(context,'document',{get(){throw new Error('Rejected command touched DOM');}});
  const result=vm.runInNewContext(driver,context);assert.equal(result.ok,false);assert.equal(result.reason,'请在 ChatGPT 原网页中操作');
 }
});
