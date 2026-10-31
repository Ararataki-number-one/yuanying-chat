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
test('Trusted send remains busy before the website adds a stop control',t=>{
 const f=fixture();t.after(f.close);f.install('owned-binding');f.flush(250);
 const button=f.window.document.querySelector('[data-testid="send-button"]');for(const receive of f.handlers.get('click'))receive({isTrusted:true,target:button});
 assert.equal(f.posts.filter(row=>row.type==='intent').length,1);assert.equal(f.window.document.querySelector('[data-testid="stop-button"]'),null);
 f.window.__pocketWebReplyObserver.requestResources(nonce);assert.equal(f.resources().at(-1).busy,true);
});
test('Backgrounding cancels heavy pending gesture confirmation while resource guard remains live',t=>{
 const f=fixture();t.after(f.close);f.install('owned-binding');f.flush(250);
 const button=f.window.document.querySelector('[data-testid="send-button"]');for(const receive of f.handlers.get('click'))receive({isTrusted:true,target:button});
 f.window.__pocketReplyObservationAllowed=false;f.api.messages=()=>{throw new Error('Optional message enumeration must stop');};f.flush(30);
 f.window.__pocketWebReplyObserver.requestResources(nonce);assert.equal(f.resources().at(-1).busy,true);assert.equal(f.posts.filter(row=>row.type==='bound').length,0);
});
test('Malformed guard nonces cannot emit observations or alter files',t=>{
 const f=fixture();t.after(f.close);f.install();f.flush(250);const before=f.posts.length;
 for(const request of ['',null,'prefix/'+nonce+'/injected',{},'x'.repeat(81)])assert.equal(f.window.__pocketWebReplyObserver.requestResources(request),false);
 assert.equal(f.posts.length,before);
});

// Native sets the flag before invoking this API; the observer must retain its own
// policy state. These fixtures never click/fill/submit on behalf of the website.
function allowed(f,value){f.window.__pocketReplyObservationAllowed=value;assert.equal(f.window.__pocketWebReplyObserver.setObservationAllowed(value),true);}
function gesture(f){const button=f.window.document.querySelector('[data-testid="send-button"]');for(const receive of f.handlers.get('click'))receive({isTrusted:true,target:button});return f.posts.filter(row=>row.type==='intent').at(-1);}
function appendUser(f,intent,{key='u1',text=intent.prompt}={}){const user=f.window.document.createElement('article');user.dataset.messageAuthorRole='user';user.dataset.messageId=key;user.textContent=text;f.window.document.querySelector('main').append(user);return user;}
function drop(f,type,when){const original=f.window.PocketWebReply.postMessage;f.window.PocketWebReply.postMessage=value=>{const row=JSON.parse(value);if(row.type!==type||!when())original(value);};}

test('Foreground resume after more than 45 seconds confirms one existing message without background scans',async t=>{
 const f=fixture();t.after(f.close);f.install('owned-binding');f.flush(50);f.flush(250);const intent=gesture(f),draft=f.window.document.querySelector('textarea').value,cookie=f.window.document.cookie;
 allowed(f,false);assert.equal(f.scheduled(30),0);assert.equal(f.scheduled(45000),0);
 const messages=f.api.messages;let reads=0;f.api.messages=role=>{reads++;if(f.window.__pocketReplyObservationAllowed===false)throw new Error('Background confirmation scanned messages');return messages(role);};
 f.advance(60000);appendUser(f,intent);await f.settle();assert.equal(f.scheduled(30),0);assert.equal(f.flush(45000),0);assert.equal(reads,0);
 allowed(f,true);const bound=f.posts.filter(row=>row.type==='bound');assert.equal(bound.length,1);assert.equal(bound[0].token,intent.token);assert.equal(bound[0].userKey,'id:u1');assert.equal(reads,1);assert.equal(f.scheduled(30),0);assert.equal(f.scheduled(45000),0);
 assert.equal(f.posts.filter(row=>row.type==='intent').length,1);assert.equal(f.window.document.querySelector('textarea').value,draft);assert.equal(f.window.document.cookie,cookie);
});

test('Resume before the original deadline restores only its remaining timer',t=>{
 const f=fixture();t.after(f.close);f.install();const intent=gesture(f);allowed(f,false);f.advance(15000);allowed(f,true);
 assert.equal(f.scheduled(30000),1);assert.equal(f.scheduled(45000),0);f.advance(30000);f.flush(30000);
 const uncertain=f.posts.filter(row=>row.type==='uncertain');assert.equal(uncertain.length,1);assert.equal(uncertain[0].token,intent.token);assert.match(uncertain[0].reason,/未能确认/);assert.equal(f.scheduled(30),0);assert.equal(f.posts.filter(row=>row.type==='intent').length,1);
});

test('A JS-bound receipt dropped while native is off is strictly revalidated once on foreground',async t=>{
 const f=fixture();t.after(f.close);f.install();const intent=gesture(f);let suppress=true;drop(f,'bound',()=>suppress);appendUser(f,intent);await f.settle();f.flush(30);assert.equal(f.posts.filter(row=>row.type==='bound').length,0);assert.equal(f.scheduled(45000),0);
 allowed(f,false);f.advance(60000);suppress=false;allowed(f,true);const bound=f.posts.filter(row=>row.type==='bound');assert.equal(bound.length,1);assert.equal(bound[0].token,intent.token);assert.equal(bound[0].userKey,'id:u1');assert.equal(bound[0].prompt,intent.prompt);assert.equal(f.scheduled(30),0);assert.equal(f.scheduled(45000),0);assert.equal(f.posts.filter(row=>row.type==='intent').length,1);
});

test('A bound receipt can recover even if the off setter itself was never delivered',async t=>{
 const f=fixture();t.after(f.close);f.install();const intent=gesture(f);let suppress=true;drop(f,'bound',()=>suppress);appendUser(f,intent);await f.settle();f.flush(30);f.window.__pocketReplyObservationAllowed=false;f.advance(60000);suppress=false;allowed(f,true);
 const bound=f.posts.filter(row=>row.type==='bound');assert.equal(bound.length,1);assert.equal(bound[0].token,intent.token);assert.equal(bound[0].userKey,'id:u1');assert.equal(f.posts.filter(row=>row.type==='intent').length,1);
});

test('Bound foreground replay rejects changed text, key, or additional last-user evidence',async t=>{
 for(const change of ['text','additional','before','unstable']){const f=fixture();t.after(f.close);f.install();const intent=gesture(f);let suppress=true;drop(f,'bound',()=>suppress);const user=appendUser(f,intent);await f.settle();f.flush(30);allowed(f,false);
  if(change==='text')user.textContent='a different prompt';else if(change==='additional')appendUser(f,intent,{key:'u2',text:'another question'});else if(change==='before')user.dataset.messageId='u0';else f.api.key=()=> 'position:1';
  await f.settle();suppress=false;allowed(f,true);assert.equal(f.posts.filter(row=>row.type==='bound').length,0);const uncertain=f.posts.filter(row=>row.type==='uncertain');assert.equal(uncertain.length,1);assert.equal(uncertain[0].token,intent.token);assert.equal(f.scheduled(30),0);assert.equal(f.scheduled(45000),0);
 }
});

test('A changed document or conversation cannot be rebound during foreground resume',async t=>{
 for(const change of ['document','route']){const f=fixture();t.after(f.close);f.install();const intent=gesture(f);allowed(f,false);appendUser(f,intent);
  if(change==='document')f.window.__pocketAttachmentDocumentId='replacement-document-123456789';else f.window.history.replaceState({},'','/c/a-different-conversation');
  await f.settle();let reads=0;const original=f.api.messages;f.api.messages=role=>{reads++;return original(role);};allowed(f,true);
  assert.equal(f.posts.filter(row=>row.type==='bound').length,0);assert.equal(reads,0);const uncertain=f.posts.filter(row=>row.type==='uncertain');assert.equal(uncertain.length,1);assert.equal(uncertain[0].token,intent.token);assert.equal(uncertain[0].documentId,intent.documentId);assert.equal(f.scheduled(30),0);assert.equal(f.scheduled(45000),0);
 }
});

test('Expired background attempt without a fresh message emits safe uncertain without replaying input',t=>{
 const f=fixture();t.after(f.close);f.install();const intent=gesture(f),draft=f.window.document.querySelector('textarea').value;allowed(f,false);f.advance(60000);allowed(f,true);
 const uncertain=f.posts.filter(row=>row.type==='uncertain');assert.equal(uncertain.length,1);assert.equal(uncertain[0].token,intent.token);assert.equal(uncertain[0].documentId,intent.documentId);assert.match(uncertain[0].reason,/未能确认/);assert.equal(f.posts.filter(row=>row.type==='bound').length,0);assert.equal(f.posts.filter(row=>row.type==='intent').length,1);assert.equal(f.window.document.querySelector('textarea').value,draft);assert.equal(f.scheduled(30),0);assert.equal(f.scheduled(45000),0);
});

test('A dropped old timeout receipt is replayed on resume even when off setter was delayed',t=>{
 const f=fixture();t.after(f.close);f.install();const intent=gesture(f);drop(f,'uncertain',()=>f.window.__pocketReplyObservationAllowed===false);f.window.__pocketReplyObservationAllowed=false;f.advance(45001);f.flush(45000);assert.equal(f.posts.filter(row=>row.type==='uncertain').length,0);
 allowed(f,true);const uncertain=f.posts.filter(row=>row.type==='uncertain');assert.equal(uncertain.length,1);assert.equal(uncertain[0].token,intent.token);assert.equal(uncertain[0].documentId,intent.documentId);assert.match(uncertain[0].reason,/未能确认/);assert.equal(f.posts.filter(row=>row.type==='bound').length,0);assert.equal(f.posts.filter(row=>row.type==='intent').length,1);assert.equal(f.scheduled(30),0);assert.equal(f.scheduled(45000),0);
});

test('A stopped or page-hidden attempt keeps its original end semantics on foreground',async t=>{
 const stopped=fixture();t.after(stopped.close);stopped.install();const intent=gesture(stopped);allowed(stopped,false);stopped.busy(true);let suppress=true;drop(stopped,'stop',()=>suppress);const button=stopped.window.document.querySelector('[data-testid="stop-button"]');for(const receive of stopped.handlers.get('click'))receive({isTrusted:true,target:button});suppress=false;allowed(stopped,true);assert.equal(stopped.posts.filter(row=>row.type==='bound').length,0);assert.equal(stopped.posts.filter(row=>row.type==='uncertain').length,0);assert.equal(stopped.posts.filter(row=>row.type==='stop').at(-1).token,intent.token);
 const hidden=fixture();t.after(hidden.close);hidden.install();const pending=gesture(hidden);allowed(hidden,false);drop(hidden,'uncertain',()=>hidden.window.__pocketReplyObservationAllowed===false);hidden.window.dispatchEvent(new hidden.window.Event('pagehide'));appendUser(hidden,pending);await hidden.settle();allowed(hidden,true);assert.equal(hidden.posts.filter(row=>row.type==='bound').length,0);const uncertain=hidden.posts.filter(row=>row.type==='uncertain');assert.equal(uncertain.length,1);assert.match(uncertain[0].reason,/页面已离开/);
});


test('An attachment-only bound receipt can be recovered after the website reply finishes',async t=>{
 const f=fixture();t.after(f.close);f.install();f.window.document.querySelector('textarea').value='';const intent=gesture(f);let suppress=true;drop(f,'bound',()=>suppress);appendUser(f,intent,{text:''});f.busy(true);await f.settle();f.flush(30);assert.equal(f.scheduled(45000),0);allowed(f,false);f.busy(false);await f.settle();f.advance(60000);suppress=false;allowed(f,true);const bound=f.posts.filter(row=>row.type==='bound');assert.equal(bound.length,1);assert.equal(bound[0].token,intent.token);assert.equal(bound[0].userKey,'id:u1');assert.equal(bound[0].prompt,'');assert.equal(f.window.document.querySelector('textarea').value,'');assert.equal(f.posts.filter(row=>row.type==='intent').length,1);
});

test('Repeated explicit activations preserve the original deadline and reject malformed policy values',t=>{
 const f=fixture();t.after(f.close);f.install();const intent=gesture(f);allowed(f,false);assert.equal(f.window.__pocketWebReplyObserver.setObservationAllowed('true'),false);assert.equal(f.window.__pocketReplyObservationAllowed,false);f.advance(10000);allowed(f,true);assert.equal(f.scheduled(35000),1);f.advance(5000);allowed(f,true);assert.equal(f.scheduled(35000),0);assert.equal(f.scheduled(30000),1);assert.equal(f.scheduled(45000),0);allowed(f,false);f.advance(30001);allowed(f,true);const uncertain=f.posts.filter(row=>row.type==='uncertain');assert.equal(uncertain.length,1);assert.equal(uncertain[0].token,intent.token);assert.equal(f.scheduled(30),0);assert.equal(f.scheduled(45000),0);assert.equal(f.posts.filter(row=>row.type==='intent').length,1);
});
