/* Real production JS, synthetic DOM/timers and explicit trusted-event adapter.
 * No Android, Gecko, real upload, or physical gesture acceptance. */
'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path');
const {JSDOM}=require(process.env.JSDOM_MODULE||'jsdom');
const assets=path.join(__dirname,'../../app/src/main/assets');
const observer=fs.readFileSync(path.join(assets,'web-reply-observer.js'),'utf8');
const driver=fs.readFileSync(path.join(assets,'attachment-driver.js'),'utf8');
function fixture(t){
  const window=new JSDOM('<form><textarea id="prompt-textarea">keep this draft</textarea><button type="button" data-testid="send-button" aria-label="Send">Send</button><section id="files"></section></form><main><article data-message-author-role="user" data-message-id="u0">old</article></main>',{url:'https://chatgpt.com/c/attachments',runScripts:'outside-only',pretendToBeVisual:true}).window;
  let now=1700000000000,next=0;const timers=new Map(),handlers=new Map(),posts=[];
  window.Date.now=()=>now;window.setTimeout=(fn,delay)=>{const id=++next;timers.set(id,{fn,delay});return id;};window.clearTimeout=id=>timers.delete(id);
  Object.defineProperty(window.HTMLElement.prototype,'innerText',{get(){return this.textContent;}});
  window.HTMLElement.prototype.getClientRects=function(){return this.isConnected&&!this.closest('[hidden]')?[{}]:[];};
  const add=window.document.addEventListener.bind(window.document);
  window.document.addEventListener=(kind,fn,...args)=>{if(!handlers.has(kind))handlers.set(kind,[]);handlers.get(kind).push(fn);add(kind,fn,...args);};
  window.document.cookie='attachmentSession=preserved;path=/';window.PocketWebReply={postMessage:raw=>posts.push(JSON.parse(raw))};
  const editor=window.document.querySelector('textarea');
  const api={composer:()=>editor.isConnected?editor:null,sendButton:()=>window.document.querySelector('[data-testid="send-button"]'),draft:node=>node.value,busy:()=>false,resourceBusy:()=>false,uploadBusy:()=>!!window.document.querySelector('[data-upload-state="uploading"]'),messages:role=>[...window.document.querySelectorAll(`[data-message-author-role="${role}"]`)],key:node=>'id:'+node.dataset.messageId,userText:node=>node.textContent,hasMessages:()=>true};
  window.eval(observer);assert.equal(window.__pocketInstallWebReplyObserver(api),true);
  const documentId=window.__pocketWebReplyObserver.documentId;
  const batch=(id='batch-1',name='report.txt',selectedAt=now-1)=>({batchId:id,documentId,selectedAt,names:[name]});
  const poll=async batches=>JSON.parse(JSON.stringify(await window.eval(driver.replace('__ACTION__',JSON.stringify('attachment-state')).replace('__ARG__',JSON.stringify({url:window.location.href,documentId,names:batches.flatMap(b=>b.names),batches})))));
  const card=(name='report.txt',state='ready')=>{const node=window.document.createElement('div');node.dataset.fileName=name;node.dataset.uploadState=state;const button=window.document.createElement('button');button.type='button';button.setAttribute('aria-label','Remove file');button.textContent='Remove';node.append(button);window.document.getElementById('files').append(node);return node;};
  const gesture=(node,trusted=true)=>handlers.get('click').forEach(fn=>fn({isTrusted:trusted,target:node}));
  const settle=async()=>{await Promise.resolve();await Promise.resolve();};
  const flush=delay=>{const work=[...timers].filter(([,task])=>task.delay===delay);assert.ok(work.length<10);for(const[id,task]of work){timers.delete(id);task.fn();}};
  t.after(()=>{assert.equal(editor.value,'keep this draft');assert.match(window.document.cookie,/attachmentSession=preserved/);timers.clear();window.close();});
  return {window,editor,documentId,batch,poll,card,gesture,settle,flush,posts,advance:ms=>now+=ms,now:()=>now};
}
const state=value=>value.batches[0].files[0].state;

test('An uploading card stays uploading; missing unobserved files stay unknown',async t=>{
  const f=fixture(t),b=f.batch(),card=f.card('report.txt','uploading');
  assert.equal(state(await f.poll([b])),'uploading');card.remove();
  const missing=f.batch('never-observed','missing.txt');
  assert.equal(state(await f.poll([missing])),'unknown');f.advance(24*60*60*1000);
  assert.equal(state(await f.poll([missing])),'unknown','Elapsed time alone never releases unknown files');
});
test('An observed card disappearing yields fresh terminal samples without changing the draft',async t=>{
  const f=fixture(t),b=f.batch(),card=f.card();assert.equal(state(await f.poll([b])),'ready');card.remove();
  const first=await f.poll([b]),second=await f.poll([b]);assert.equal(state(first),'removed');assert.equal(state(second),'removed');assert.equal(second.batches[0].sequence,first.batches[0].sequence+1);
});
test('A trusted remove captured before the first attachment poll is recognized only after disappearance',async t=>{
  const f=fixture(t),b=f.batch(),card=f.card('report.txt','uploading');f.gesture(card.querySelector('button'));
  assert.equal(state(await f.poll([b])),'uploading','Remove intent cannot declare a still visible upload complete');card.remove();assert.equal(state(await f.poll([b])),'removed');
});
test('A quick send is terminal only after the production observer confirms the new user message',async t=>{
  const f=fixture(t),b=f.batch(),card=f.card();f.gesture(f.window.document.querySelector('[data-testid="send-button"]'));card.remove();
  assert.equal(state(await f.poll([b])),'unknown','Trusted intent alone is not successful sending');
  const user=f.window.document.createElement('article');user.dataset.messageAuthorRole='user';user.dataset.messageId='u1';user.textContent=f.editor.value;f.window.document.querySelector('main').append(user);await f.settle();f.flush(30);
  assert.ok(f.posts.some(row=>row.type==='bound'));assert.equal(state(await f.poll([b])),'sent');
});
test('Untrusted remove and an unconfirmed send never supply terminal evidence',async t=>{
  const f=fixture(t),b=f.batch(),card=f.card();f.gesture(card.querySelector('button'),false);card.remove();
  assert.equal(state(await f.poll([b])),'unknown');f.flush(30);assert.equal(state(await f.poll([b])),'unknown');
});
test('Old and equal-millisecond remove facts cannot release a newer same-name selection',async t=>{
  const f=fixture(t),card=f.card();f.gesture(card.querySelector('button'));card.remove();
  const equal=f.batch('equal-time','report.txt',f.now());assert.equal(state(await f.poll([equal])),'unknown');
  f.advance(1);const newer=f.batch('newer','report.txt',f.now());assert.equal(state(await f.poll([newer])),'unknown');
});
test('Overlapping batches with the same filename remain ambiguous even when one card looks ready',async t=>{
  const f=fixture(t),first=f.batch('first'),second=f.batch('second');f.card();
  const value=await f.poll([first,second]);assert.deepEqual(value.batches.map(b=>b.files[0].state),['unknown','unknown']);
});
test('Legacy polling cannot erase batch sequence or evidence of a previously seen card',async t=>{
  const f=fixture(t),b=f.batch(),card=f.card();const first=await f.poll([b]);card.remove();
  await f.window.eval(driver.replace('__ACTION__',JSON.stringify('attachment-state')).replace('__ARG__',JSON.stringify({names:['report.txt'],url:f.window.location.href})));
  const next=await f.poll([b]);assert.equal(state(next),'removed');assert.equal(next.batches[0].sequence,first.batches[0].sequence+1);
});
test('Hidden document or hidden composer never supplies terminal evidence and recovers on visibility',async t=>{
  const f=fixture(t),b=f.batch(),card=f.card();assert.equal(state(await f.poll([b])),'ready');
  Object.defineProperty(f.window.document,'visibilityState',{configurable:true,value:'hidden'});card.remove();assert.equal(state(await f.poll([b])),'unknown');
  Object.defineProperty(f.window.document,'visibilityState',{configurable:true,value:'visible'});f.editor.closest('form').hidden=true;assert.equal(state(await f.poll([b])),'unknown');
  f.editor.closest('form').hidden=false;assert.equal(state(await f.poll([b])),'removed');
});
test('A hidden attachment and a separate active upload block removal inference',async t=>{
  const f=fixture(t),b=f.batch(),card=f.card();card.hidden=true;assert.equal(state(await f.poll([b])),'unknown');card.hidden=false;assert.equal(state(await f.poll([b])),'ready');card.remove();
  const other=f.card('other.txt','uploading');assert.equal(state(await f.poll([b])),'unknown');other.remove();assert.equal(state(await f.poll([b])),'removed');
});
test('A wrong document or batch document cannot contribute attachment observations',async t=>{
  const f=fixture(t),b=f.batch();f.card();b.documentId='another-document';const value=await f.poll([b]);assert.equal(value.batches[0].sequence,0);assert.deepEqual(value.batches[0].files,[]);
  const wrong=await f.window.eval(driver.replace('__ACTION__',JSON.stringify('attachment-state')).replace('__ARG__',JSON.stringify({documentId:'another-document',batches:[b]})));assert.equal(wrong.ok,false);
});
test('Facts from a different conversation do not release a missing file',async t=>{
  const f=fixture(t),b=f.batch(),card=f.card();f.gesture(card.querySelector('button'));card.remove();f.window.history.pushState({},'','/c/another');
  assert.equal(state(await f.poll([b])),'unknown');
});
