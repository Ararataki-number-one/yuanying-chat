'use strict';

// Actual extension modules in a Node VM with declared browser/native/timer
// boundaries. These controls do not execute Gecko, Android or a network request.
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const ROOT=path.resolve(__dirname,'../..');
const HELPER=fs.readFileSync(path.join(ROOT,'app/src/main/assets/gecko/request-identity-background.js'),'utf8');
const SOURCE=fs.readFileSync(path.join(ROOT,'app/src/main/assets/gecko/request-headers.js'),'utf8');
const BACKGROUND=fs.readFileSync(path.join(ROOT,'app/src/main/assets/gecko/background.js'),'utf8');
const IP_BOOTSTRAP=fs.readFileSync(path.join(ROOT,'app/src/main/assets/gecko/ip-timezone-bootstrap.js'),'utf8');
const TIMEZONE_BRIDGE=fs.readFileSync(path.join(ROOT,'app/src/main/assets/gecko/native-timezone-bridge.js'),'utf8');
const MANIFEST=JSON.parse(fs.readFileSync(path.join(ROOT,'app/src/main/assets/gecko/manifest.json'),'utf8'));
const BASE='https://audit.example/pocketchat-identity/v1/',NONCE='a'.repeat(32);
const OWN='moz-extension://own-runtime/',SITE='https://chatgpt.com/c/controlled';
const plain=value=>JSON.parse(JSON.stringify(value));
const deferred=()=>{let resolve,reject;const promise=new Promise((yes,no)=>{resolve=yes;reject=no;});return {promise,resolve,reject};};
const accepted=(userAgent='NativeDesktop/157',revision=1)=>JSON.stringify({allowed:true,userAgent,revision});
const privateAdmission=(revision=1)=>JSON.stringify({allowed:true,scope:'private-admission-unchanged',revision});
const response=value=>({status:200,body:{getReader(){let done=false;return {async read(){if(done)return {done:true};done=true;return {done:false,value:new TextEncoder().encode(JSON.stringify(value))};},async cancel(){},releaseLock(){}};}}});
const ordinary=(extra={})=>({url:SITE,method:'GET',type:'xmlhttprequest',tabId:-1,requestHeaders:[{name:'User-Agent',value:'WorkerMobile/157'}],...extra});
const diagnostic=(operation='observe',extra={})=>ordinary({url:BASE+operation+'?nonce='+NONCE+(operation==='observe'?'&source=worker':''),...extra});
const COMPLETE_SCRIPTS=['ip-timezone-bootstrap.js','request-headers.js','request-identity-background.js','native-timezone-bridge.js','background.js'];
function completeScripts(manifest){assert.deepEqual(manifest.background.scripts,COMPLETE_SCRIPTS);return manifest.background.scripts;}

function matches(pattern,target){
  const url=new URL(target),parts=/^(https?):\/\/([^/]+)(\/.*)$/.exec(pattern);if(!parts||url.protocol!==parts[1]+':')return false;
  if(parts[2]!=='*'&&url.hostname!==parts[2])return false;
  return new RegExp('^'+parts[3].split('*').map(value=>value.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')).join('.*')+'$').test(url.pathname+url.search);
}
function harness(options={}){
  let now=1000,id=0,fetcher=options.fetch??(()=>{throw Error('No network in VM');});
  const timers=new Map(),calls=[],hooks={onBeforeRequest:[],onBeforeSendHeaders:[],onHeadersReceived:[]};
  const browser={runtime:{getURL:()=>OWN,sendNativeMessage(app,message){calls.push({app,message:plain(message)});return options.native?options.native(app,message):Promise.resolve(accepted(options.userAgent,options.revision));}},webRequest:{}};
  for(const [name,rows] of Object.entries(hooks))browser.webRequest[name]={
    addListener(callback,filter,extra){if(options.failGlobal&&filter.urls.includes('http://*/*'))throw Error('Controlled global registration failure');rows.push({callback,filter:plain(filter),extra:plain(extra)});},
    removeListener(callback){const index=rows.findIndex(row=>row.callback===callback);if(index>=0)rows.splice(index,1);}
  };
  if(options.missing==='sendNativeMessage')delete browser.runtime.sendNativeMessage;
  if(options.missing==='getURL')delete browser.runtime.getURL;
  if(options.missing==='headersEvent')delete browser.webRequest.onBeforeSendHeaders;
  if(options.missing==='removeListener')delete browser.webRequest.onBeforeSendHeaders.removeListener;
  class Clock extends Date{static now(){return now;}}
  const context=vm.createContext({browser,URL,Date:Clock,AbortController,TextDecoder,Uint8Array,
    setTimeout(callback,delay){const key=++id;timers.set(key,{at:now+delay,callback});return key;},clearTimeout(key){timers.delete(key);},
    fetch:(url,settings)=>fetcher(url,settings)});
  vm.runInContext(HELPER,context,{filename:'request-identity-background.js'});
  vm.runInContext(SOURCE,context,{filename:'request-headers.js'});
  const api=context.PocketGeckoRequestHeaders,helper=context.PocketRequestIdentityBackground,port={};
  if(!options.inactive)api.activate(port);
  return {api,helper,port,calls,hooks,context,
    setFetch(value){fetcher=value;},
    advance(ms){const until=now+ms;for(;;){const next=[...timers].filter(([,value])=>value.at<=until).sort((a,b)=>a[1].at-b[1].at)[0];if(!next)break;timers.delete(next[0]);now=next[1].at;next[1].callback();}now=until;},
    timers:()=>timers.size,
    register(purpose='identity'){const value=plain(helper.handle({action:'register',endpoint:BASE,nonce:NONCE,purpose}));assert.equal(value.ok,true);return value;},
    listeners(details){return hooks.onBeforeSendHeaders.filter(row=>row.filter.urls.some(pattern=>matches(pattern,details.url)));},
    async decisions(details,reverse=false){const rows=this.listeners(details);if(reverse)rows.reverse();return Promise.all(rows.map(row=>Promise.resolve(row.callback(details)).then(plain)));},
    async filter(details,sanitized){return plain(await api.filter(details,sanitized));}
  };
}
const ua=result=>result.requestHeaders?.filter(value=>value.name.toLowerCase()==='user-agent').map(value=>value.value);

test('installs one actual global blocking header listener and freezes its API',()=>{
  const h=harness();assert.equal(Object.isFrozen(h.api),true);assert.deepEqual(plain(h.api.status()),{installed:true});
  assert.equal(h.hooks.onBeforeSendHeaders.length,1);assert.deepEqual(h.hooks.onBeforeSendHeaders[0].filter,{urls:['http://*/*','https://*/*']});assert.deepEqual(h.hooks.onBeforeSendHeaders[0].extra,['blocking','requestHeaders']);
  h.api.activate(h.port);h.api.activate({});assert.equal(h.hooks.onBeforeSendHeaders.length,1);
});
test('unowned or cleared runtime cancels rather than falling back to the worker UA',async()=>{
  const h=harness({inactive:true});assert.deepEqual(await h.filter(ordinary()),{cancel:true});assert.equal(h.calls.length,0);
  h.api.activate(h.port);h.api.clear(h.port);assert.deepEqual(await h.filter(ordinary()),{cancel:true});
});
test('all website resource types and absent/negative tab IDs receive the actual native UA',async()=>{
  const h=harness();
  for(const [type,tabId] of [['main_frame',3],['sub_frame',3],['script',-1],['xmlhttprequest',-1],['other',-1],['websocket',undefined]]){
    const value=await h.filter(ordinary({type,tabId}));assert.deepEqual(ua(value),['NativeDesktop/157']);
  }
  assert.equal(h.calls.length,6);for(const call of h.calls)assert.deepEqual(call,{app:'pocketroute',message:{kind:'requestHeaderPolicy',url:SITE}});
});
test('only User-Agent is deduplicated and replaced; sensitive ordinary-site headers and input bytes remain',async()=>{
  const h=harness(),input=[{name:'Cookie',value:'site-cookie'},{name:'uSeR-aGeNt',value:'old',binaryValue:[1]},{name:'Authorization',value:'Bearer secret'},{name:'User-Agent',value:'duplicate'},{name:'Accept-Language',value:'zh-CN,en;q=0.8'},{name:'X-Binary',binaryValue:[0,1,255]}],before=plain(input);
  const value=await h.filter(ordinary({requestHeaders:input}));assert.deepEqual(input,before);assert.deepEqual(value.requestHeaders,[before[0],{name:'uSeR-aGeNt',value:'NativeDesktop/157'},before[2],before[4],before[5]]);
});
test('absent User-Agent is supplied without inventing unrelated headers',async()=>{
  const h=harness();assert.deepEqual((await h.filter(ordinary({requestHeaders:[{name:'Accept',value:'*/*'}]}))).requestHeaders,[{name:'Accept',value:'*/*'},{name:'User-Agent',value:'NativeDesktop/157'}]);
});
test('malformed, unbounded, non-ASCII or untyped native proofs always cancel',async()=>{
  const invalid=[null,{allowed:true,userAgent:'object',revision:1},'not-json','[]','null',JSON.stringify({allowed:false}),JSON.stringify({allowed:true,userAgent:'UA',revision:1,extra:true}),JSON.stringify({allowed:true,scope:'other',revision:1}),JSON.stringify({allowed:true,scope:'private-admission-unchanged',revision:1,userAgent:'UA'}),privateAdmission(0),accepted('',1),accepted('bad\rUA',1),accepted('bad\nUA',1),accepted('非ASCII',1),accepted('a'.repeat(1025),1),accepted('UA',0),accepted('UA',1.5),accepted('UA',Number.MAX_SAFE_INTEGER+1),' '.repeat(4097)];
  for(const raw of invalid){const h=harness({native:()=>Promise.resolve(raw)});assert.deepEqual(await h.filter(ordinary()),{cancel:true});assert.equal(h.timers(),0);}
});
test('native rejection and synchronous native failures cancel without leaking timers',async()=>{
  for(const native of [()=>Promise.reject(Error('native disconnected')),()=>{throw Error('native unavailable');}]){const h=harness({native});assert.deepEqual(await h.filter(ordinary()),{cancel:true});assert.equal(h.timers(),0);}
});
test('non-HTTP schemes, embedded credentials and sanitizer cancellation never invoke native',async()=>{
  const h=harness();for(const url of ['file:///private','moz-extension://own-runtime/page','data:text/plain,no','https://user:pass@example.com/','not a URL'])assert.deepEqual(await h.filter(ordinary({url})),{cancel:true});
  assert.deepEqual(await h.filter(ordinary(),{cancel:true}),{cancel:true});assert.equal(h.calls.length,0);
});
test('five second deadline cancels; a late old proof cannot establish the next revision',async()=>{
  const held=deferred(),h=harness({native:()=>held.promise}),waiting=h.filter(ordinary());h.advance(4999);assert.equal(h.timers(),1);h.advance(1);assert.deepEqual(await waiting,{cancel:true});assert.equal(h.timers(),0);
  h.api.invalidate(h.port,2);held.resolve(accepted('Old/157',1));await Promise.resolve();assert.deepEqual(await h.filter(ordinary()),{cancel:true});
});
test('invalidation immediately cancels pending proof and rejects stale revision on subsequent work',async()=>{
  const held=deferred();let count=0;const h=harness({native:()=>++count===1?held.promise:Promise.resolve(accepted('Current/157',2))});
  const waiting=h.filter(ordinary());assert.equal(h.api.invalidate(h.port,2),true);assert.deepEqual(await waiting,{cancel:true});held.resolve(accepted('Old/157',1));await Promise.resolve();
  assert.deepEqual(ua(await h.filter(ordinary())),['Current/157']);assert.equal(h.timers(),0);
});
test('same revision invalidation also fences old protection-token work',async()=>{
  const held=deferred(),h=harness({native:()=>held.promise});h.api.invalidate(h.port,7);const waiting=h.filter(ordinary());assert.equal(h.api.invalidate(h.port,7),true);assert.deepEqual(await waiting,{cancel:true});held.resolve(accepted('Old/157',7));await Promise.resolve();assert.equal(h.timers(),0);
});
test('clear and reactivation fence old owner; old disconnect cannot clear new owner',async()=>{
  const held=deferred();let count=0;const h=harness({native:()=>++count===1?held.promise:Promise.resolve(accepted('NewOwner/157',9))}),waiting=h.filter(ordinary());
  const replacement={};h.api.activate(replacement);assert.deepEqual(await waiting,{cancel:true});assert.equal(h.api.clear(h.port),false);held.resolve(accepted('OldOwner/157',1));assert.deepEqual(ua(await h.filter(ordinary())),['NewOwner/157']);
  assert.equal(h.api.clear(replacement),true);assert.deepEqual(await h.filter(ordinary()),{cancel:true});
});
test('lower/invalid revision cannot replace a newer policy, and exact equality is required',async()=>{
  const h=harness({native:()=>accepted('UA/157',4)});h.api.invalidate(h.port,5);for(const value of [0,-1,4,5.5,NaN,Number.MAX_SAFE_INTEGER+1])assert.equal(h.api.invalidate(h.port,value),false);assert.deepEqual(await h.filter(ordinary()),{cancel:true});
});
test('two environment VMs keep native UA and known revision independently',async()=>{
  const one=harness({userAgent:'EnvironmentOne/157',revision:1}),two=harness({userAgent:'EnvironmentTwo/157',revision:2});assert.deepEqual(ua(await one.filter(ordinary())),['EnvironmentOne/157']);assert.deepEqual(ua(await two.filter(ordinary())),['EnvironmentTwo/157']);one.api.clear(one.port);assert.deepEqual(ua(await two.filter(ordinary())),['EnvironmentTwo/157']);
});
test('both actual header hooks return the same credential-stripped aligned result in either order',async()=>{
  const h=harness();h.register();const original=[{name:'Cookie',value:'cookie'},{name:'Authorization',value:'secret'},{name:'Proxy-Authorization',value:'proxy'},{name:'Origin',value:'origin'},{name:'Referer',value:'referrer'},{name:'User-Agent',value:'WorkerMobile/157'},{name:'Accept',value:'*/*'}],details=diagnostic('observe',{originUrl:'https://audit.example/worker.js',requestHeaders:original});
  for(const reverse of [false,true]){const results=await h.decisions(details,reverse);assert.equal(results.length,2);assert.deepEqual(results[0],results[1]);assert.deepEqual(results[0].requestHeaders,[{name:'User-Agent',value:'NativeDesktop/157'},{name:'Accept',value:'*/*'}]);}assert.equal(original.length,7);
});
test('actual invalid/expired diagnostic scope wins before any header policy proof',async()=>{
  const h=harness();h.register();for(const details of [diagnostic('observe',{url:BASE+'observe?nonce='+'b'.repeat(32)+'&source=worker'}),diagnostic('observe',{method:'POST'})])for(const result of await h.decisions(details))assert.deepEqual(result,{cancel:true});
  h.advance(30000);for(const result of await h.decisions(diagnostic()))assert.deepEqual(result,{cancel:true});assert.equal(h.calls.length,0);
});
test('scope cancellation or expiry during pending native proof cancels at completion',async()=>{
  for(const expire of [false,true]){const held=deferred(),h=harness({native:()=>held.promise});h.register();if(expire)h.advance(29999);const waiting=h.decisions(diagnostic());if(expire)h.advance(1);else h.helper.handle({action:'cancel',endpoint:BASE,nonce:NONCE});held.resolve(accepted());for(const result of await waiting)assert.deepEqual(result,{cancel:true});assert.equal(h.timers(),0);}
});
test('fresh sanitizer may only remove more; it cannot restore a previously removed header',async()=>{
  const h=harness(),details=ordinary({requestHeaders:[{name:'Cookie',value:'site-cookie'},{name:'User-Agent',value:'old'}]});const value=await h.filter(details,{requestHeaders:[{name:'User-Agent',value:'old'}]});assert.deepEqual(value.requestHeaders,[{name:'User-Agent',value:'NativeDesktop/157'}]);
});
test('actual registered inflight extension evidence keeps its original HTTP UA and strips credentials',async()=>{
  const h=harness();h.register();let observed;
  h.setFetch(async(url,options)=>{assert.equal(options.credentials,'omit');assert.equal(options.redirect,'error');observed=await h.decisions(diagnostic('result',{url,originUrl:OWN+'_generated_background_page.html',documentUrl:OWN+'_generated_background_page.html',requestHeaders:[{name:'User-Agent',value:'IndependentControl/157'},{name:'Origin',value:OWN},{name:'Cookie',value:'must-remove'}]}));return response({status:'ready'});});
  const value=plain(await h.helper.handle({action:'evidence',endpoint:BASE,nonce:NONCE}));assert.equal(value.ok,true);assert.equal(value.source,'extension-background-control');assert.equal(observed.length,2);for(const result of observed)assert.deepEqual(result.requestHeaders,[{name:'User-Agent',value:'IndependentControl/157'}]);assert.equal(h.calls.length,0);assert.equal(h.timers(),0);
});
test('actual registered inflight capability control also stays independent',async()=>{
  const h=harness();h.register('capabilities');let observed;
  h.setFetch(async url=>{observed=await h.decisions(diagnostic('capabilities',{url,documentUrl:OWN+'_generated_background_page.html',requestHeaders:[{name:'User-Agent',value:'CapabilityControl/157'}]}));return response({protocol:'capabilities'});});
  const value=plain(await h.helper.handle({action:'capabilities',endpoint:BASE,nonce:NONCE}));assert.equal(value.ok,true);for(const result of observed)assert.deepEqual(ua(result),['CapabilityControl/157']);assert.equal(h.calls.length,0);
});
test('tab id, control path, missing initiator and another extension never grant control exemption',async()=>{
  const fetchHold=deferred(),h=harness();h.register();h.setFetch(()=>fetchHold.promise);const control=h.helper.handle({action:'evidence',endpoint:BASE,nonce:NONCE});
  const origins=[{}, {originUrl:'https://audit.example/worker.js'}, {originUrl:'moz-extension://other-runtime/background.html'}, {originUrl:'moz-extension://own-runtime.evil/background.html'}, {originUrl:OWN+'background.html',documentUrl:'https://audit.example/page'}, {originUrl:'null'}, {originUrl:'moz-extension://own-runtime@other-runtime/background.html'}];
  for(const extra of origins)for(const result of await h.decisions(diagnostic('result',{tabId:-1,...extra})))assert.deepEqual(ua(result),['NativeDesktop/157']);
  fetchHold.resolve(response({status:'ready'}));await control;
});
test('same-extension origin without an actual inflight control is aligned normally',async()=>{
  const h=harness();h.register();for(const result of await h.decisions(diagnostic('result',{originUrl:OWN+'background.html'})))assert.deepEqual(ua(result),['NativeDesktop/157']);assert.equal(h.calls.length,2);
});
test('listener registration/API failures remain explicitly unavailable, with no original-UA fallback',async()=>{
  for(const options of [{failGlobal:true},{missing:'sendNativeMessage'},{missing:'getURL'},{missing:'headersEvent'},{missing:'removeListener'}]){const h=harness(options);assert.deepEqual(plain(h.api.status()),{installed:false});assert.deepEqual(plain(h.api.activate(h.port)),{installed:false});assert.deepEqual(await h.filter(ordinary()),{cancel:true});assert.equal(h.calls.length,0);assert.equal(h.hooks.onBeforeSendHeaders.length,0);}
});
test('only explicit positive native private admission preserves the already sanitized original headers',async()=>{
  const original=[{name:'Cookie',value:'private-cookie'},{name:'User-Agent',value:'FixtureOriginal/157'},{name:'USER-AGENT',value:'existing-duplicate'},{name:'Accept',value:'*/*'}],h=harness({native:()=>privateAdmission()});
  assert.deepEqual((await h.filter(ordinary({url:'https://127.0.0.1:9877/pool',requestHeaders:original}))).requestHeaders,original);
  assert.deepEqual((await h.filter(ordinary({requestHeaders:original}),{requestHeaders:original.slice(1)})).requestHeaders,original.slice(1));
  assert.equal(h.calls.length,2);assert.equal(h.calls[0].message.url,'https://127.0.0.1:9877/pool');
  const denied=harness({native:()=>JSON.stringify({allowed:false})});assert.deepEqual(await denied.filter(ordinary({url:'https://127.0.0.1:9877/pool'})),{cancel:true});
});
test('private admission still obeys revision, disconnect and five second proof fences',async()=>{
  for(const action of ['revision','disconnect','timeout']){const held=deferred(),h=harness({native:()=>held.promise}),waiting=h.filter(ordinary({url:'https://127.0.0.1:9877/pool'}));if(action==='revision')h.api.invalidate(h.port,2);else if(action==='disconnect')h.api.clear(h.port);else h.advance(5000);held.resolve(privateAdmission());assert.deepEqual(await waiting,{cancel:true});assert.equal(h.timers(),0);}
});
test('private positive proof cannot undo actual diagnostic filtering or scope cancellation',async()=>{
  const h=harness({native:()=>privateAdmission()});h.register();for(const result of await h.decisions(diagnostic('observe',{requestHeaders:[{name:'Cookie',value:'secret'},{name:'Origin',value:'private'},{name:'User-Agent',value:'Original/157'}]})))assert.deepEqual(result.requestHeaders,[{name:'User-Agent',value:'Original/157'}]);
  const held=deferred(),pending=harness({native:()=>held.promise});pending.register();const waiting=pending.decisions(diagnostic());pending.helper.handle({action:'cancel',endpoint:BASE,nonce:NONCE});held.resolve(privateAdmission());for(const result of await waiting)assert.deepEqual(result,{cancel:true});
});
test('actual complete manifest startup advertises listener readiness before prepare and fences reconnection',async()=>{
  assert.deepEqual(MANIFEST.background.scripts,['ip-timezone-bootstrap.js','request-headers.js','request-identity-background.js','native-timezone-bridge.js','background.js']);
  let now=1000,timerId=0,rfp=false,mode='ready',nativeUa='FirstNative/157',nativeRevision=1;
  const timers=new Map(),ports=[],nativeCalls=[],headerHooks=[],proxyHooks=[],privacyCalls=[];let pendingProof;
  const event=()=>({listeners:[],addListener(callback){this.listeners.push(callback);},emit(value){return Promise.all(this.listeners.map(callback=>callback(value)));}});
  const browser={runtime:{getURL:()=>OWN,connectNative(app){assert.equal(app,'pocketroute');const port={sent:[],onMessage:event(),onDisconnect:event(),postMessage(message){this.sent.push(plain(message));}};ports.push(port);return port;},sendNativeMessage(app,message){nativeCalls.push({app,message:plain(message)});if(message.kind==='route')return Promise.resolve(JSON.stringify({type:'socks',host:'127.0.0.1',port:9,proxyDNS:true,failoverTimeout:1}));assert.equal(message.kind,'requestHeaderPolicy');return mode==='pending'?pendingProof.promise:Promise.resolve(accepted(nativeUa,nativeRevision));}},webRequest:{},proxy:{onRequest:{addListener(callback,filter){proxyHooks.push({callback,filter:plain(filter)});}}},cookies:{onChanged:event(),async getAll(){return [];},async set(){throw Error('No restored cookies expected');}},storage:{local:{async get(){return {};},async set(){}}},privacy:{websites:{resistFingerprinting:{onChange:event(),async set(value){privacyCalls.push(plain(value));rfp=value.value;},async get(){return {value:rfp};}}}}};
  for(const name of ['onBeforeRequest','onBeforeSendHeaders','onHeadersReceived'])browser.webRequest[name]={addListener(callback,filter,extra){if(name==='onBeforeSendHeaders')headerHooks.push({callback,filter:plain(filter),extra:plain(extra)});},removeListener(callback){const index=headerHooks.findIndex(value=>value.callback===callback);if(index>=0)headerHooks.splice(index,1);}};
  class Clock extends Date{static now(){return now;}}
  const context=vm.createContext({browser,URL,Date:Clock,AbortController,TextDecoder,Uint8Array,setTimeout(callback,delay){const id=++timerId;timers.set(id,{at:now+delay,callback});return id;},clearTimeout(id){timers.delete(id);},fetch(){throw Error('No network in startup controls');}});
  const sources={'ip-timezone-bootstrap.js':IP_BOOTSTRAP,'request-headers.js':SOURCE,'request-identity-background.js':HELPER,'native-timezone-bridge.js':TIMEZONE_BRIDGE,'background.js':BACKGROUND};for(const name of completeScripts(MANIFEST))vm.runInContext(sources[name],context,{filename:name});
  const first=ports[0];assert.equal(ports.length,1);assert.deepEqual(first.sent,[{kind:'requestHeadersPrepared',installed:true}]);assert.equal(nativeCalls.length,0);assert.equal(headerHooks.length,1);assert.equal(proxyHooks.length,1);assert.deepEqual(proxyHooks[0].filter,{urls:['<all_urls>']});
  await first.onMessage.emit({kind:'prepare',level:1,token:1,generation:1,timeoutMs:8000});assert.deepEqual(first.sent.map(value=>value.kind),['requestHeadersPrepared','cookiePrepared','protectionReady','ready']);assert.equal(first.sent[2].acknowledged,true);assert.deepEqual(privacyCalls,[{value:false}]);assert.equal(nativeCalls.length,0,'Cookie/RFP preparation needs no session UA query');
  await first.onMessage.emit({kind:'requestHeaderPolicyChanged',revision:1});const header=headerHooks[0].callback;assert.deepEqual(ua(plain(await header(ordinary()))),['FirstNative/157']);assert.deepEqual(nativeCalls,[{app:'pocketroute',message:{kind:'requestHeaderPolicy',url:SITE}}]);
  const route=plain(await proxyHooks[0].callback({url:SITE}));assert.deepEqual(route,{type:'socks',host:'127.0.0.1',port:9,proxyDNS:true,failoverTimeout:1});
  mode='pending';pendingProof=deferred();const waiting=header(ordinary());await first.onDisconnect.emit();assert.deepEqual(plain(await waiting),{cancel:true});pendingProof.resolve(accepted('DisconnectedOld/157',1));assert.deepEqual(plain(await header(ordinary())),{cancel:true});
  const advance=ms=>{const until=now+ms;for(;;){const next=[...timers].filter(([,value])=>value.at<=until).sort((a,b)=>a[1].at-b[1].at)[0];if(!next)break;timers.delete(next[0]);now=next[1].at;next[1].callback();}now=until;};
  advance(499);assert.equal(ports.length,1);advance(1);assert.equal(ports.length,2);const second=ports[1];assert.deepEqual(second.sent,[{kind:'requestHeadersPrepared',installed:true}]);assert.equal(headerHooks.length,1,'Reconnect reuses the one installed listener');
  await first.onMessage.emit({kind:'requestHeaderPolicyChanged',revision:999});await first.onDisconnect.emit();await second.onMessage.emit({kind:'prepare',level:1,token:2,generation:2,timeoutMs:8000});await second.onMessage.emit({kind:'requestHeaderPolicyChanged',revision:2});mode='ready';nativeUa='ReconnectedNative/157';nativeRevision=2;
  assert.deepEqual(ua(plain(await header(ordinary()))),['ReconnectedNative/157']);assert.equal(second.sent.some(value=>value.kind==='protectionReady'&&value.acknowledged===true),true);assert.equal(timers.size,0);
});
test('complete current manifest rejects extra, duplicate, missing or reordered background modules',()=>{
  assert.deepEqual(completeScripts(MANIFEST),COMPLETE_SCRIPTS);
  for(const scripts of [[...COMPLETE_SCRIPTS,'unknown.js'],[...COMPLETE_SCRIPTS,COMPLETE_SCRIPTS[0]],COMPLETE_SCRIPTS.slice(1),[COMPLETE_SCRIPTS[1],COMPLETE_SCRIPTS[0],...COMPLETE_SCRIPTS.slice(2)]])assert.throws(()=>completeScripts({background:{scripts}}),assert.AssertionError);
});
