'use strict';
// Actual scoped helper in a Node VM. These are API doubles, not Gecko acceptance.
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const SOURCE=fs.readFileSync(path.resolve(__dirname,'../../app/src/main/assets/gecko/request-identity-background.js'),'utf8');
const BASE='https://audit.example/pocketchat-identity/v1/',SECOND='https://frame.example/pocketchat-identity/v1/',NONCE='a'.repeat(32),OTHER='b'.repeat(32);
const plain=v=>JSON.parse(JSON.stringify(v));
function harness(fetcher){
 let now=1000,timerId=0;const timers=new Map(),calls=[],hooks={};
 const browser={webRequest:{}};
 for(const name of ['onBeforeRequest','onBeforeSendHeaders','onHeadersReceived']){const entries=[];hooks[name]=entries;browser.webRequest[name]={addListener(fn,filter){entries.push({fn,filter});},removeListener(fn){const i=entries.findIndex(v=>v.fn===fn);if(i>=0)entries.splice(i,1);}};}
 class Clock extends Date{static now(){return now;}}
 const context=vm.createContext({URL,Uint8Array,TextDecoder,AbortController,Date:Clock,browser,fetch:(url,options)=>{calls.push({url,options});if(!fetcher)throw new Error('No network in VM control');return fetcher(url,options);},setTimeout(fn,ms){const id=++timerId;timers.set(id,{at:now+ms,fn});return id;},clearTimeout(id){timers.delete(id);}});
 vm.runInContext(SOURCE,context,{filename:'request-identity-background.js'});
 return {api:context.PocketRequestIdentityBackground,calls,timers,
  advance(ms){const until=now+ms;for(;;){const next=[...timers].filter(([,v])=>v.at<=until).sort((a,b)=>a[1].at-b[1].at)[0];if(!next)break;now=next[1].at;timers.delete(next[0]);next[1].fn();}now=until;},
  hook(name,url,extra={}){let out={};for(const {fn,filter} of hooks[name]){if(!filter.urls.some(p=>new URL(url).hostname===new URL(p.replace('*','sentinel')).hostname))continue;out=plain(fn({url,method:'GET',...extra}));if(out.cancel)return out;}return out;},
  hooks:()=>Object.values(hooks).reduce((a,b)=>a+b.length,0)};
}
const register=(h,purpose='capabilities',nonce=NONCE,endpoint=BASE,extra={})=>plain(h.api.handle({action:'register',purpose,nonce,endpoint,...extra}));
const control=(h,nonce=NONCE,endpoint=BASE)=>h.api.handle({action:'capabilities',nonce,endpoint});
const target=(operation='capabilities',nonce=NONCE,base=BASE)=>base+operation+'?nonce='+nonce;
function streamed(value,status=200,chunk=2048){
 const raw=Buffer.isBuffer(value)?value:Buffer.from(JSON.stringify(value)),stats={cancelled:0,released:0,reads:0};let offset=0;
 return {status,stats,body:{getReader:()=>({async read(){stats.reads++;if(offset===raw.length)return {done:true};const value=raw.subarray(offset,Math.min(raw.length,offset+chunk));offset+=value.byteLength;return {done:false,value};},async cancel(){stats.cancelled++;},releaseLock(){stats.released++;}})}};
}
const ready=()=>({schema:1,protocol:'pocketchat-request-identity-v1',nonce:NONCE,source:'controlled-service-capabilities',status:'ready'});
const later=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};};
async function flush(){for(let i=0;i<12;i++)await Promise.resolve();}

test('capability action is unavailable without an acknowledged purpose-bound scope',async()=>{
 const h=harness();assert.equal(h.hooks(),0);assert.equal(plain(await control(h)).error,'diagnostic-scope-expired');assert.equal(h.calls.length,0);
 assert.equal(register(h,'identity').ok,true);assert.equal(plain(await control(h)).error,'diagnostic-purpose-mismatch');assert.equal(h.calls.length,0);
});
test('capability registration echoes its purpose and admits only its fixed GET endpoint',()=>{
 const h=harness(),ack=register(h);assert.equal(ack.purpose,'capabilities');assert.equal(ack.credentialFilter,true);assert.equal(ack.redirectsBlocked,true);
 assert.deepEqual(h.hook('onBeforeRequest',target()),{});
 for(const operation of ['document','worker.js','observe','result','frame'])assert.equal(h.hook('onBeforeRequest',target(operation)).cancel,true,operation);
 for(const url of [target()+'&source=worker',target()+'&frame=1',target()+'&nonce='+OTHER,target()+'#fragment',target('capabilities',OTHER),target().replace('https://','https://user:pass@'),target().replace('audit.example','audit.example:9443')])assert.equal(h.hook('onBeforeRequest',url).cancel,true,url);
 assert.equal(h.hook('onBeforeRequest',target(),{method:'POST'}).cancel,true);
});
test('registered capability headers strip sensitive values but preserve UA and full languages',()=>{
 const h=harness();register(h);const headers=[{name:'Cookie',value:'private'},{name:'Authorization',value:'private'},{name:'Proxy-Authorization',value:'private'},{name:'Referer',value:'https://chatgpt.com/c/private'},{name:'Origin',value:'moz-extension://private'},{name:'User-Agent',value:'Actual/157'},{name:'Accept-Language',value:'ja-JP,en-US;q=0.8,en;q=0.5'}];
 assert.deepEqual(h.hook('onBeforeSendHeaders',target(),{requestHeaders:headers}).requestHeaders,headers.slice(5));assert.equal(headers.length,7);
 for(const code of [300,301,302,307,308,399])assert.equal(h.hook('onHeadersReceived',target(),{statusCode:code}).cancel,true);
});
test('invalid scope purposes and frame flags do not install hooks',()=>{
 for(const config of [{purpose:'all'},{purpose:null},{purpose:3},{purpose:'capabilities',crossOriginFrame:true},{purpose:'frame',crossOriginFrame:true},{purpose:'identity',crossOriginFrame:'true'}]){const h=harness();assert.equal(plain(h.api.handle({action:'register',endpoint:BASE,nonce:NONCE,...config})).ok,false);assert.equal(h.hooks(),0);}
});
test('a registered nonce cannot change purpose or expand an identity frame flag',()=>{
 const h=harness();assert.equal(register(h,'identity').ok,true);assert.equal(register(h,'capabilities').error,'nonce-purpose-rebind');assert.equal(register(h,'identity',NONCE,BASE,{crossOriginFrame:true,frameEndpoint:SECOND}).error,'nonce-purpose-rebind');assert.equal(h.hook('onBeforeRequest',target('document')+'&frame=1').cancel,true);
});
test('explicit primary cross-frame scope admits only frame=1 on the document',()=>{
 const h=harness(),ack=register(h,'identity',NONCE,BASE,{crossOriginFrame:true,frameEndpoint:SECOND});assert.equal(ack.crossOriginFrame,true);assert.deepEqual(h.hook('onBeforeRequest',target('document')+'&frame=1'),{});assert.deepEqual(h.hook('onBeforeRequest',target('document')),{});
 for(const url of [target('worker.js')+'&frame=1',target('document')+'&frame=0',target('document')+'&frame=1&frame=1',target('document')+'&frame=1&source=worker'])assert.equal(h.hook('onBeforeRequest',url).cancel,true,url);
 assert.equal(h.hook('onBeforeRequest',target('frame')).cancel,true);
});
test('the separate frame purpose admits only the exact secondary frame URL',()=>{
 const h=harness();assert.equal(register(h,'frame',NONCE,SECOND,{parentEndpoint:BASE}).error,'frame-parent-unconfirmed');assert.equal(register(h,'identity',NONCE,BASE,{crossOriginFrame:true,frameEndpoint:SECOND}).ok,true);const ack=register(h,'frame',NONCE,SECOND,{parentEndpoint:BASE});assert.equal(ack.purpose,'frame');assert.deepEqual(h.hook('onBeforeRequest',target('frame',NONCE,SECOND)),{});
 for(const operation of ['document','worker.js','observe','result','capabilities'])assert.equal(h.hook('onBeforeRequest',target(operation,NONCE,SECOND)).cancel,true,operation);
 assert.equal(h.hook('onBeforeRequest',target('frame',NONCE,SECOND)+'&frame=1').cancel,true);
 assert.equal(register(h,'capabilities',OTHER,BASE).error,'diagnostic-scope-limit','Primary and child count as two actual scopes');
});
test('capability transport uses protected anonymous options and returns actual streamed bytes',async()=>{
 const response=streamed(ready(),200,5),h=harness(async()=>response);register(h);const out=plain(await control(h));assert.equal(out.ok,true);assert.equal(out.source,'extension-background-control');assert.equal(out.responseBytes,Buffer.byteLength(JSON.stringify(ready())));assert.deepEqual(out.service,ready());assert.equal(h.calls[0].url,target());
 const opts=h.calls[0].options;assert.equal(opts.credentials,'omit');assert.equal(opts.referrerPolicy,'no-referrer');assert.equal(opts.redirect,'error');assert.equal(opts.cache,'no-store');assert.ok(opts.signal instanceof AbortSignal);assert.equal(response.stats.released,1);assert.equal(h.timers.size,0);
});
test('exact 16KB succeeds while one extra streamed byte cancels rather than parsing',async()=>{
 const value={padding:''};value.padding='x'.repeat(16384-Buffer.byteLength(JSON.stringify(value)));const exact=streamed(value,200,3000),h=harness(async()=>exact);register(h);assert.equal(plain(await control(h)).ok,true);
 const overflow=streamed(Buffer.concat([Buffer.from(JSON.stringify(value)),Buffer.from(' ')]),200,3000),bad=harness(async()=>overflow);register(bad);const out=plain(await control(bad));assert.equal(out.error,'service-response-too-large');assert.equal(out.service,undefined);assert.equal(overflow.stats.cancelled,1);assert.equal(overflow.stats.released,1);
});
test('no stream, invalid UTF8, malformed JSON and scalar JSON never use unbounded helpers',async()=>{
 let unbounded=0;const missing=harness(async()=>({status:200,body:null,json(){unbounded++;},text(){unbounded++;}}));register(missing);assert.equal(plain(await control(missing)).error,'bounded-stream-unavailable');assert.equal(unbounded,0);
 for(const bytes of [Buffer.from([255]),Buffer.from('{'),Buffer.from('1'),Buffer.from('[]'),Buffer.from('null')]){const h=harness(async()=>streamed(bytes));register(h);assert.equal(plain(await control(h)).error,'service-json-invalid');}
});
test('status codes and protocol error payloads stay separate from successful capabilities',async()=>{
 for(const status of [403,404,409,429,503]){const service={status:'unavailable',reason:'test-only'},h=harness(async()=>streamed(service,status));register(h);const out=plain(await control(h));assert.equal(out.ok,true);assert.equal(out.httpStatus,status);assert.deepEqual(out.service,service);}
});
test('timeouts abort before headers and during streamed reads, releasing the body lock',async()=>{
 const h=harness((_,opts)=>new Promise((resolve,reject)=>opts.signal.addEventListener('abort',()=>reject(Error('transport aborted')),{once:true})));register(h);const p=control(h);h.advance(2999);await flush();assert.equal(h.calls[0].options.signal.aborted,false);h.advance(1);assert.equal(plain(await p).error,'service-timeout');assert.equal(h.timers.size,0);
 let reads=0,releases=0;const body=harness(async(_,opts)=>({status:200,body:{getReader:()=>({read(){reads++;return new Promise((resolve,reject)=>opts.signal.addEventListener('abort',()=>reject(Error('body aborted')),{once:true}));},releaseLock(){releases++;}})}}));register(body);const pending=control(body);await flush();assert.equal(reads,1);body.advance(3000);assert.equal(plain(await pending).error,'service-timeout');assert.equal(releases,1);assert.equal(body.timers.size,0);
});
test('manual cancellation and clear abort the active fetch and close future requests',async()=>{
 for(const clear of [false,true]){const h=harness((_,opts)=>new Promise((resolve,reject)=>opts.signal.addEventListener('abort',()=>reject(Error('stopped')),{once:true})));register(h);const p=control(h);if(clear)h.api.clear();else h.api.handle({action:'cancel',nonce:NONCE});assert.equal(plain(await p).error,'service-cancelled');assert.equal(h.hook('onBeforeRequest',target()).cancel,true);assert.equal(h.timers.size,0);}
});
test('late old replies do not unlock a replacement scope or become current evidence',async()=>{
 const a=later(),b=later();let count=0;const h=harness(()=>++count===1?a.promise:b.promise);register(h);const old=control(h);h.api.handle({action:'cancel',nonce:NONCE});register(h);const current=control(h);a.resolve(streamed(ready()));assert.equal(plain(await old).ok,false);assert.equal(plain(await control(h)).error,'capabilities-already-in-flight');assert.equal(h.calls.length,2);b.resolve(streamed(ready()));assert.equal(plain(await current).ok,true);assert.equal(h.timers.size,0);
});
test('re-registration cannot bypass the single in-flight capability request lock',async()=>{
 const deferred=later(),h=harness(()=>deferred.promise);register(h);const p=control(h);assert.equal(register(h).ok,true);assert.equal(plain(await control(h)).error,'capabilities-already-in-flight');assert.equal(h.calls.length,1);deferred.resolve(streamed(ready()));assert.equal(plain(await p).ok,true);
});
test('generic transport errors do not invent certificate certainty or expose error contents',async()=>{
 const h=harness(async()=>{throw new TypeError('secret provider certificate body');});register(h);const out=plain(await control(h));assert.equal(out.error,'service-connection-or-certificate-unavailable');assert.equal(JSON.stringify(out).includes('secret'),false);
});
test('purpose-bound scope expiry keeps the diagnostic namespace closed',()=>{
 const h=harness();register(h);h.advance(30000);assert.equal(h.hook('onBeforeRequest',target()).cancel,true);assert.equal(h.hook('onBeforeSendHeaders',target(),{requestHeaders:[{name:'Cookie',value:'private'}]}).cancel,true);assert.equal(h.hooks(),3);
});

test('a child scope requires the same nonce, exact declared endpoint and exact parent endpoint',()=>{
 const h=harness();register(h,'identity',NONCE,BASE,{crossOriginFrame:true,frameEndpoint:SECOND});
 for(const config of [{purpose:'frame',nonce:OTHER,endpoint:SECOND,parentEndpoint:BASE},{purpose:'frame',nonce:NONCE,endpoint:SECOND},{purpose:'frame',nonce:NONCE,endpoint:SECOND,parentEndpoint:'https://wrong.example/pocketchat-identity/v1/'},{purpose:'frame',nonce:NONCE,endpoint:'https://third.example/pocketchat-identity/v1/',parentEndpoint:BASE}])assert.equal(plain(h.api.handle({action:'register',...config})).error,'frame-parent-unconfirmed');
 assert.equal(register(h,'identity',NONCE,SECOND).error,'nonce-endpoint-rebind','The old arbitrary nonce rebind denial is preserved');
 assert.equal(register(h,'frame',NONCE,SECOND,{parentEndpoint:BASE}).ok,true);
 assert.equal(register(h,'identity',NONCE,BASE,{crossOriginFrame:true,frameEndpoint:'https://third.example/pocketchat-identity/v1/'}).error,'nonce-purpose-rebind');
});
test('cancelling a secondary scope leaves its primary but primary cancellation closes the child too',()=>{
 const h=harness();register(h,'identity',NONCE,BASE,{crossOriginFrame:true,frameEndpoint:SECOND});register(h,'frame',NONCE,SECOND,{parentEndpoint:BASE});
 assert.equal(plain(h.api.handle({action:'cancel',nonce:NONCE,endpoint:SECOND})).ok,true);assert.equal(h.hook('onBeforeRequest',target('frame',NONCE,SECOND)).cancel,true);assert.deepEqual(h.hook('onBeforeRequest',target('document')+'&frame=1'),{});
 assert.equal(register(h,'frame',NONCE,SECOND,{parentEndpoint:BASE}).ok,true);assert.equal(plain(h.api.handle({action:'cancel',nonce:NONCE,endpoint:BASE})).ok,true);assert.equal(h.hook('onBeforeRequest',target('document')).cancel,true);assert.equal(h.hook('onBeforeRequest',target('frame',NONCE,SECOND)).cancel,true);assert.equal(register(h,'frame',NONCE,SECOND,{parentEndpoint:BASE}).error,'frame-parent-unconfirmed');
 assert.equal(plain(h.api.handle({action:'cancel',nonce:NONCE,endpoint:SECOND})).ok,true,'Late child cleanup is idempotent');
});
test('scope cancellation cannot cancel another bound endpoint or rebound child origin',()=>{
 const h=harness();register(h,'identity',NONCE,BASE,{crossOriginFrame:true,frameEndpoint:SECOND});register(h,'frame',NONCE,SECOND,{parentEndpoint:BASE});
 assert.equal(plain(h.api.handle({action:'cancel',nonce:NONCE,endpoint:'https://wrong.example/pocketchat-identity/v1/'})).error,'scope-endpoint-mismatch');assert.deepEqual(h.hook('onBeforeRequest',target('frame',NONCE,SECOND)),{});h.advance(30000);assert.equal(h.hook('onBeforeRequest',target('frame',NONCE,SECOND)).cancel,true);assert.equal(h.hook('onBeforeRequest',target('document')).cancel,true);
});
test('only valid different-origin explicit frame endpoints can extend an identity registration',()=>{
 for(const frameEndpoint of [undefined,BASE,'https://audit.example/pocketchat-identity/v1/','https://user:pass@frame.example/pocketchat-identity/v1/','https://FRAME.example/pocketchat-identity/v1/']){const h=harness();assert.equal(register(h,'identity',NONCE,BASE,{crossOriginFrame:true,frameEndpoint}).error,'invalid-frame-endpoint');assert.equal(h.hooks(),0);}
});
