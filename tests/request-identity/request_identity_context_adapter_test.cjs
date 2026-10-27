'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs'),path=require('node:path');
// Actual isolated helper with a synthetic event harness; not browser trust/SOP acceptance.
const source=fs.readFileSync(path.join(__dirname,'../../app/src/main/assets/gecko/request-identity-audit.js'),'utf8');
const nonce='a'.repeat(32),endpoint='https://primary.example/pocketchat-identity/v1/',frameEndpoint='https://secondary.example/pocketchat-identity/v1/';
function harness({frame=false,url}={}){
 const listeners=new Map(),posted=[],timers=new Map();let serial=0;
 const window={addEventListener(type,run){if(!listeners.has(type))listeners.set(type,new Set());listeners.get(type).add(run);},removeEventListener(type,run){listeners.get(type)?.delete(run);},postMessage(value,origin){posted.push({value,origin});}};window.top=window;
 const context=vm.createContext({window,location:{href:url||endpoint+'document?nonce='+nonce+(frame?'&frame=1':'')},URL,Array,Object,Number,setTimeout(run){const id=++serial;timers.set(id,run);return id;},clearTimeout(id){timers.delete(id);}});vm.runInContext(source,context,{filename:'request-identity-audit.js'});
 return {window,posted,run:context.PocketRequestIdentityAudit.run,emit(value,extra={}){const event={source:window,origin:'https://primary.example',isTrusted:true,data:value,...extra};for(const run of [...(listeners.get('message')||[])])run(event);},listeners,timers};
}
function result(extra={}){return {schema:1,protocol:'pocketchat-request-identity-v1',pocketRequestIdentity:nonce,nonce,status:'complete',source:'controlled-top-level-document',document:{ua:'desktop',language:'en-US',languages:['en-US','ja-JP']},worker:{ua:'worker',language:'en-US',languages:['en-US','ja-JP']},...extra};}
function frame(extra={}){return {status:'complete',nonce,origin:'https://secondary.example',source:'controlled-cross-origin-iframe',apiChecks:{schema:1,requested:true,source:'controlled-cross-origin-iframe',probeVersion:1,protectionVerified:true,limits:{canvasPixels:99999999},durationMs:30,probes:{canvas:{state:'available',reason:'read',pixels:4096,hashAlgorithm:'sha256',hash:'b'.repeat(64),password:'never-copy'},audio:{state:'available',reason:'not-implemented',frames:2048},fonts:{state:'available',reason:'not-implemented',samples:[]},webgl:{state:'available',reason:'read',version:'WebGL 1.0',shadingLanguageVersion:'GLSL',vendor:'masked',renderer:'masked',maxTextureSize:4096,maxRenderbufferSize:4096,maxVertexAttribs:16,extensionCount:0,extensions:[],readbackPixels:256,readbackBytes:1024,readbackHash:'c'.repeat(64),readbackHashAlgorithm:'sha256',hash:'d'.repeat(64),hashAlgorithm:'sha256'}}},...extra};}
function config(extra={}){return {endpoint,nonce,...extra};}

test('ordinary controlled identity ignores unsolicited cross-origin API fields',async()=>{
 const h=harness(),pending=h.run(config(),[]);h.emit(result({crossOriginFrame:frame()}));const value=await pending;assert.equal(value.status,'complete');assert.equal(value.crossOriginFrame,undefined);
});
test('explicit trusted second origin keeps bounded API evidence separate and never attests protection',async()=>{
 const h=harness({frame:true}),pending=h.run(config({crossOriginFrame:true,frameEndpoint}),[]);h.emit(result({crossOriginFrame:frame()}));const value=await pending,c=value.crossOriginFrame;
 assert.equal(value.document.ua,'desktop');assert.equal(value.worker.ua,'worker');assert.equal(c.status,'complete');assert.equal(c.origin,'https://secondary.example');assert.equal(c.nonce,nonce);assert.equal(c.source,'controlled-cross-origin-iframe');assert.equal(c.protectionVerified,false);assert.equal(c.apiChecks.protectionVerified,false);
 assert.equal(c.apiChecks.probes.canvas.hash,'b'.repeat(64));assert.equal(c.apiChecks.probes.canvas.password,undefined);assert.equal(c.apiChecks.probes.webgl.readbackHash,'c'.repeat(64));assert.equal(c.apiChecks.probes.audio.state,'uncovered');assert.equal(c.apiChecks.probes.fonts.state,'uncovered');assert.deepEqual(JSON.parse(JSON.stringify(c.apiChecks.limits)),{canvasPixels:4096,audioFrames:0,fontCandidates:0,totalBudgetMs:1200});
});
test('cross-origin source origin and nonce must all match the explicit scope',async()=>{
 for(const bad of [{origin:'https://third.example'},{nonce:'b'.repeat(32)},{source:'page-main-world'}]){const h=harness({frame:true}),pending=h.run(config({crossOriginFrame:true,frameEndpoint}),[]);h.emit(result({crossOriginFrame:frame(bad)}));const value=await pending;assert.equal(value.status,'complete');assert.equal(value.crossOriginFrame.status,'uncovered');assert.equal(value.crossOriginFrame.reason,'invalid-frame-observation');assert.equal(value.crossOriginFrame.apiChecks,undefined);}
});
test('only a canonical separate HTTPS base can enable a controlled frame',async()=>{
 for(const bad of [endpoint,'http://secondary.example/pocketchat-identity/v1/','https://u:p@secondary.example/pocketchat-identity/v1/',frameEndpoint+'?x=1',frameEndpoint+'#fragment','https://secondary.example/other/','']){const h=harness({frame:true});const value=await h.run(config({crossOriginFrame:true,frameEndpoint:bad}),[]);assert.equal(value.status,'failed');assert.equal(value.error,'invalid-frame-endpoint');assert.equal(h.posted.length,0);}
});
test('cross-origin timeout remains uncovered without discarding independent document and Worker evidence',async()=>{
 const h=harness({frame:true}),pending=h.run(config({crossOriginFrame:true,frameEndpoint}),[]);h.emit(result({crossOriginFrame:frame({status:'uncovered',reason:'frame-timeout',apiChecks:undefined})}));const value=await pending;assert.equal(value.status,'complete');assert.equal(value.crossOriginFrame.status,'uncovered');assert.equal(value.crossOriginFrame.reason,'frame-timeout');assert.equal(value.crossOriginFrame.apiChecks,undefined);
});
test('wrong API source and incomplete available readbacks cannot claim cross-origin coverage',async()=>{
 for(const bad of ['source','readback']){const f=frame();if(bad==='source')f.apiChecks.source='page-main-world';else delete f.apiChecks.probes.webgl.readbackHash;
  const h=harness({frame:true}),pending=h.run(config({crossOriginFrame:true,frameEndpoint}),[]);h.emit(result({crossOriginFrame:f}));const value=await pending;
  if(bad==='source'){assert.equal(value.crossOriginFrame.status,'uncovered');assert.equal(value.crossOriginFrame.reason,'invalid-frame-api-observation');}else{assert.equal(value.crossOriginFrame.apiChecks.probes.webgl.state,'uncovered');assert.equal(value.crossOriginFrame.apiChecks.probes.webgl.reason,'incomplete-available-observation');}}
});
test('worker failure categories are whitelisted without copying arbitrary server text',async()=>{
 for(const [sent,want] of [['worker-response-too-large','worker-response-too-large'],['worker-response-invalid-json','worker-response-invalid-json'],['password=secret','controlled-page-or-worker-unavailable']]){const h=harness(),pending=h.run(config(),[]);h.emit(result({status:'failed',error:sent}));const value=await pending;assert.equal(value.status,'failed');assert.equal(value.error,want);assert.equal(value.document,undefined);}
});
test('wrong origin source trust and nonce messages do not satisfy the controlled page request',async()=>{
 const h=harness({frame:true}),pending=h.run(config({crossOriginFrame:true,frameEndpoint}),[]);h.emit(result({crossOriginFrame:frame()}),{origin:'https://third.example'});h.emit(result({crossOriginFrame:frame()}),{source:{}});h.emit(result({crossOriginFrame:frame()}),{isTrusted:false});h.emit(result({nonce:'b'.repeat(32),crossOriginFrame:frame()}));assert.equal(h.timers.size,1);h.emit(result({crossOriginFrame:frame()}));assert.equal((await pending).crossOriginFrame.status,'complete');
});
test('cancellation removes listeners and rejects a later frame observation',async()=>{
 const h=harness({frame:true}),stops=[],pending=h.run(config({crossOriginFrame:true,frameEndpoint}),stops);stops.forEach(stop=>stop());const value=await pending;h.emit(result({crossOriginFrame:frame()}));assert.equal(value.status,'failed');assert.equal(value.error,'cancelled');assert.equal(h.listeners.get('message').size,0);assert.equal(h.timers.size,0);
});
test('the ordinary configuration cannot adopt a frame-enabled document URL',async()=>{
 const h=harness({frame:true});const value=await h.run(config(),[]);assert.equal(value.status,'failed');assert.equal(value.error,'wrong-document');assert.equal(h.posted.length,0);
});

test('explicit waiting cancellation signals only the owned nonce and origin and remains idempotent',async()=>{
 const h=harness({frame:true}),stops=[],pending=h.run(config({crossOriginFrame:true,frameEndpoint}),stops);stops.forEach(stop=>stop());stops.forEach(stop=>stop());const value=await pending;
 const cancellations=h.posted.filter(x=>x.value.pocketRequestIdentityCancel!==undefined);assert.equal(cancellations.length,1);assert.deepEqual(JSON.parse(JSON.stringify(cancellations[0])),{value:{pocketRequestIdentityCancel:nonce},origin:'https://primary.example'});assert.equal(value.status,'failed');assert.equal(value.error,'cancelled');
 h.emit(result({crossOriginFrame:frame()}));assert.equal(h.listeners.get('message').size,0);assert.equal(h.timers.size,0);assert.equal(value.status,'failed');
});
test('completed observations never send a later page cancellation during cleanup',async()=>{
 const h=harness({frame:true}),stops=[],pending=h.run(config({crossOriginFrame:true,frameEndpoint}),stops);h.emit(result({crossOriginFrame:frame()}));const value=await pending;stops.forEach(stop=>stop());assert.equal(value.status,'complete');assert.equal(h.posted.length,1);assert.equal(h.posted[0].value.pocketRequestIdentityCollect,nonce);assert.equal(h.posted.some(x=>x.value.pocketRequestIdentityCancel!==undefined),false);
});
test('a page cancellation send failure still completes local cleanup',async()=>{
 const h=harness({frame:true}),stops=[],pending=h.run(config({crossOriginFrame:true,frameEndpoint}),stops);h.window.postMessage=()=>{throw new Error('labelled postMessage failure');};stops.forEach(stop=>stop());const value=await pending;assert.equal(value.status,'failed');assert.equal(value.error,'cancelled');assert.equal(h.listeners.get('message').size,0);assert.equal(h.timers.size,0);
});
