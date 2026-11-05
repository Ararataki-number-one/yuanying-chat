'use strict';

// Actual production scripts with declared browser, native, fetch-stream and
// deterministic timer boundaries. No Android, Gecko or HTTP executes here.
// Native policy also limits the entire envelope to 8192 bytes. Transport byte
// acceptance alone is not a claim that native accepts every near-cap body.
const test=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),crypto=require('node:crypto');
const ROOT=path.resolve(__dirname,'../..');
const FILES=['app/src/main/assets/gecko/ip-timezone-bootstrap.js','app/src/main/assets/gecko/request-headers.js','app/src/main/assets/gecko/request-identity-background.js','app/src/main/assets/gecko/native-timezone-bridge.js','app/src/main/assets/gecko/background.js','app/src/main/assets/gecko/manifest.json','tests/request-identity/ip_timezone_bootstrap_test.cjs'];
const hashes=Object.fromEntries(FILES.map(name=>[name,crypto.createHash('sha256').update(fs.readFileSync(path.join(ROOT,name))).digest('hex')]));
const SOURCE='https://ipwho.is/?fields=success,ip,timezone.id',OWN='moz-extension://owned-background/';
const TOKEN='a'.repeat(64),STAMP='b'.repeat(64),BODY=' {"success":true,"ip":"8.8.8.8","timezone":{"id":"Asia/Kathmandu"}}\n';
const MODULE=fs.readFileSync(path.join(ROOT,FILES[0]),'utf8');
const lookup=(extra={})=>({kind:'timezoneIpLookup',id:1,requestToken:TOKEN,routeStamp:STAMP,source:SOURCE,...extra});
const details=(extra={})=>({url:SOURCE,method:'GET',requestId:'owned-request-1',originUrl:OWN+'background.html',documentUrl:OWN+'background.html',type:'xmlhttprequest',tabId:-1,...extra});
const plain=value=>value===undefined?undefined:JSON.parse(JSON.stringify(value));
const deferred=()=>{let resolve,reject;const promise=new Promise((yes,no)=>{resolve=yes;reject=no;});return {promise,resolve,reject};};
const flush=async()=>{for(let i=0;i<12;i++)await Promise.resolve();};
function event(){return {listeners:[],addListener(callback,filter,extra){this.listeners.push({callback,filter,extra});},removeListener(callback){this.listeners=this.listeners.filter(row=>row.callback!==callback);},emit(value){return this.listeners.slice().map(row=>row.callback(value));}};}
function response(body=BODY,extra={}){
  const chunks=Array.isArray(body)?body:[typeof body==='string'?new TextEncoder().encode(body):body];let index=0;
  const reader={cancelled:0,released:0,async read(){return index<chunks.length?{done:false,value:chunks[index++]}:{done:true};},async cancel(){this.cancelled++;},releaseLock(){this.released++;}};
  return {ok:true,status:200,url:SOURCE,redirected:false,body:{getReader:()=>reader},reader,...extra};
}
function harness(options={}){
  let now=1000,sequence=0,fetcher=options.fetch;const timers=new Map(),fetches=[],nativeCalls=[],ports=[],proxyHooks=[];
  const hooks=Object.fromEntries(['onBeforeRequest','onBeforeRedirect','onBeforeSendHeaders','onHeadersReceived'].map(name=>[name,event()]));
  const runtimeMessage=event();
  const browser={webRequest:hooks,proxy:{onRequest:{addListener(callback,filter){proxyHooks.push({callback,filter});}}},
    runtime:{getURL:()=>options.ownURL??OWN,onMessage:runtimeMessage,connectNative(app){assert.equal(app,'pocketroute');const port={sent:[],onMessage:event(),onDisconnect:event(),postMessage(value){this.sent.push(plain(value));}};ports.push(port);return port;},
      sendNativeMessage(app,message){nativeCalls.push({app,message:plain(message)});if(options.native)return options.native(app,message);
        if(message.kind==='timezoneIpRoute')return Promise.resolve(JSON.stringify({type:'http',host:'127.0.0.1',port:6543}));
        if(message.kind==='timezoneIpHeaders')return Promise.resolve(JSON.stringify({allowed:true,revision:7,userAgent:'ActualSdk/157'}));
        return Promise.resolve(message.kind==='route'?JSON.stringify({type:'socks',host:'127.0.0.1',port:9,proxyDNS:true,failoverTimeout:1}):JSON.stringify({allowed:false}));}},
    cookies:{onChanged:event(),async getAll(){return [];},async set(){throw Error('Unexpected cookie restore');}},storage:{local:{async get(){return {};},async set(){}}},privacy:{websites:{resistFingerprinting:{onChange:event(),async set(){},async get(){return {value:false};}}}}};
  class Clock extends Date{static now(){return now;}}
  const h={browser,hooks,fetches,nativeCalls,ports,proxyHooks,runtimeMessage,timers,bootstrap:null,context:null,
    advance(amount){const until=now+amount;for(;;){const next=[...timers].filter(([,task])=>task.at<=until).sort((a,b)=>a[1].at-b[1].at)[0];if(!next)break;timers.delete(next[0]);now=next[1].at;next[1].callback();}now=until;},
    setFetch(value){fetcher=value;},
    async host(message,port=ports[0]){await Promise.all(port.onMessage.emit(message));},
    async headers(value){assert.equal(hooks.onBeforeSendHeaders.listeners.length,1);return plain(await hooks.onBeforeSendHeaders.listeners[0].callback(value));},
    async proxy(value){assert.equal(proxyHooks.length,1);return plain(await proxyHooks[0].callback(value));}
  };
  h.context=vm.createContext({browser,URL,Date:Clock,AbortController,TextDecoder,Uint8Array,console,
    setTimeout(callback,delay){const id=++sequence;timers.set(id,{at:now+delay,callback});return id;},clearTimeout(id){timers.delete(id);},
    fetch(url,settings){fetches.push({url,settings});if(fetcher)return fetcher(url,settings,h);hooks.onBeforeRequest.emit(details());return Promise.resolve(response());}});
  vm.runInContext(options.module??MODULE,h.context,{filename:FILES[0]});
  if(options.full){
    const manifest=JSON.parse(fs.readFileSync(path.join(ROOT,'app/src/main/assets/gecko/manifest.json'),'utf8'));
    assert.deepEqual(manifest.background.scripts,['ip-timezone-bootstrap.js','request-headers.js','request-identity-background.js','native-timezone-bridge.js','background.js']);
    for(const name of manifest.background.scripts.slice(1))vm.runInContext(fs.readFileSync(path.join(ROOT,'app/src/main/assets/gecko',name),'utf8'),h.context,{filename:name});
  }else h.bootstrap=h.context.PocketIpTimeZoneBootstrap.create({});
  return h;
}
function held(options={}){
  const transport=deferred(),h=harness({...options,fetch:(url,settings,owner)=>{owner.hooks.onBeforeRequest.emit(options.request??details());return transport.promise;}});
  return {h,transport,result:h.bootstrap.lookup(lookup())};
}
const cancel=h=>h.bootstrap.cancel({kind:'timezoneIpCancel',id:1,requestToken:TOKEN});

test('fixed GET omits credentials and referrer, refuses redirects and carries original raw bytes',async()=>{
  const h=harness(),raw=await h.bootstrap.lookup(lookup()),value=JSON.parse(raw),call=h.fetches[0];
  assert.deepEqual(Object.keys(value).sort(),['body','requestToken','routeStamp','schema','source','status']);assert.deepEqual(value,{schema:1,status:'observed',requestToken:TOKEN,routeStamp:STAMP,source:SOURCE,body:BODY});
  assert.equal(call.url,SOURCE);assert.deepEqual(Object.keys(call.settings).sort(),['cache','credentials','method','redirect','referrer','referrerPolicy','signal']);
  assert.equal(call.settings.method,'GET');assert.equal(call.settings.credentials,'omit');assert.equal(call.settings.cache,'no-store');assert.equal(call.settings.redirect,'error');assert.equal(call.settings.referrer,'');assert.equal(call.settings.referrerPolicy,'no-referrer');assert.equal(call.settings.signal.aborted,false);assert.equal(h.timers.size,0);
});
test('duplicate JSON keys, whitespace and UTF-8 BOM are never normalized by transport',async()=>{
  for(const body of ['\ufeff'+BODY,' {"success":true,"success":false,"ip":"8.8.8.8","timezone":{"id":"UTC"}}\r\n','invalid JSON remains native policy input']){
    const h=harness({fetch:(url,settings,owner)=>{owner.hooks.onBeforeRequest.emit(details());return response(body);}});assert.equal(JSON.parse(await h.bootstrap.lookup(lookup())).body,body);
  }
});
test('exact byte cap accepts 8192 bytes and rejects the next byte without reserialization',async()=>{
  for(const count of [8192,8193]){const h=harness({fetch:(url,settings,owner)=>{owner.hooks.onBeforeRequest.emit(details());return response(' '.repeat(count));}}),raw=await h.bootstrap.lookup(lookup());if(count===8192)assert.equal(JSON.parse(raw).body.length,8192);else assert.equal(raw,null);assert.equal(h.timers.size,0);}
});
test('fatal UTF-8 decoding rejects replacement sequences, truncated code points and byte rather than character overflow',async()=>{
  for(const body of [new Uint8Array([0xc3,0x28]),new Uint8Array([0xe2,0x82]),'字'.repeat(2731)]){const h=harness({fetch:(url,settings,owner)=>{owner.hooks.onBeforeRequest.emit(details());return response(body);}});assert.equal(await h.bootstrap.lookup(lookup()),null);assert.equal(h.timers.size,0);}
});
test('malformed native claims never issue a fetch',async()=>{
  const invalid=[null,[],{},lookup({kind:'other'}),lookup({id:0}),lookup({id:true}),lookup({id:2147483648}),lookup({requestToken:'a'.repeat(63)}),lookup({routeStamp:'B'.repeat(64)}),lookup({source:SOURCE+'&other=1'}),{...lookup(),extra:true}];
  for(const message of invalid){const h=harness();assert.equal(await h.bootstrap.lookup(message),null);assert.equal(h.fetches.length,0);assert.equal(h.timers.size,0);}
});
test('only one native lookup may own a pending transport',async()=>{
  const {h,transport,result}=held();assert.equal(await h.bootstrap.lookup(lookup({id:2,requestToken:'c'.repeat(64)})),null);assert.equal(h.fetches.length,1);transport.resolve(response());assert.ok(await result);assert.equal(h.timers.size,0);
});
test('browser-supplied exact own principal and request id are both mandatory',async()=>{
  const bad=[{originUrl:undefined,documentUrl:undefined},{originUrl:'null',documentUrl:undefined},{originUrl:'moz-extension://foreign/background.html',documentUrl:undefined},{originUrl:OWN,documentUrl:'https://site.example/'},{originUrl:'https://site.example/',documentUrl:OWN},{originUrl:'moz-extension://user:pass@owned-background/',documentUrl:undefined},{requestId:undefined},{requestId:1},{requestId:''},{method:'POST'},{url:SOURCE+'#fragment'}];
  for(const extra of bad){const {h,transport,result}=held({request:details(extra)});assert.equal(h.bootstrap.authorization(details(extra)),null);transport.resolve(response());assert.equal(await result,null);}
  const valid=held({request:details({originUrl:undefined,documentUrl:OWN})});assert.deepEqual(plain(valid.h.bootstrap.authorization(details({originUrl:undefined,documentUrl:OWN}))),{requestToken:TOKEN,routeStamp:STAMP});valid.transport.resolve(response());assert.ok(await valid.result);
});
test('public page, dedicated Worker, Shared Worker and Service Worker cannot borrow the pending URL',async()=>{
  const {h,transport,result}=held();
  for(const realm of ['document','dedicated','shared','service'])for(const origin of [undefined,'https://site.example/'+realm+'.js','moz-extension://foreign/'+realm+'.js'])assert.equal(h.bootstrap.authorization(details({requestId:'other-'+realm,originUrl:origin,documentUrl:origin})),null);
  assert.equal(h.bootstrap.authorization(details({requestId:'unrelated-id'})),null);assert.equal(h.bootstrap.authorization(details({url:'https://ipwho.is/other'})),null);transport.resolve(response());assert.ok(await result);assert.equal(h.bootstrap.authorization(details()),null);
});
test('a missing onBeforeRequest observation never turns a successful fetch stub into proof',async()=>{
  const h=harness({fetch:()=>response()});assert.equal(await h.bootstrap.lookup(lookup()),null);assert.equal(h.timers.size,0);
});
test('redirect and repeated request-id events revoke the claim immediately',async()=>{
  for(const kind of ['redirect','restart']){const {h,transport,result}=held();assert.ok(h.bootstrap.authorization(details()));if(kind==='redirect')h.hooks.onBeforeRedirect.emit(details({redirectUrl:'https://elsewhere.example/'}));else h.hooks.onBeforeRequest.emit(details());assert.equal(h.bootstrap.authorization(details()),null);assert.equal(h.fetches[0].settings.signal.aborted,true);assert.equal(await result,null);transport.resolve(response());await flush();assert.equal(h.timers.size,0);}
});
test('status, final URL, redirected response, missing stream and fetch failures all fail closed',async()=>{
  for(const value of [response(BODY,{ok:false,status:503}),response(BODY,{url:'https://elsewhere.example/'}),response(BODY,{redirected:true}),response(BODY,{body:null}),response('')]){const h=harness({fetch:(url,settings,owner)=>{owner.hooks.onBeforeRequest.emit(details());return value;}});assert.equal(await h.bootstrap.lookup(lookup()),null);}
  for(const fetch of [()=>{throw Error('controlled fetch error');},()=>Promise.reject(Error('controlled rejection'))]){const h=harness({fetch});assert.equal(await h.bootstrap.lookup(lookup()),null);assert.equal(h.timers.size,0);}
});
test('eight-second deterministic deadline aborts fetch and refuses every late response',async()=>{
  const {h,transport,result}=held();h.advance(7999);assert.ok(h.bootstrap.authorization(details()));h.advance(1);assert.equal(await result,null);assert.equal(h.bootstrap.authorization(details()),null);assert.equal(h.fetches[0].settings.signal.aborted,true);assert.equal(h.timers.size,0);transport.resolve(response());await flush();assert.equal(h.timers.size,0);
});
test('matching cancellation is required and transport retirement serializes a later native claim',async()=>{
  const {h,transport,result}=held();for(const message of [{kind:'timezoneIpCancel',id:2,requestToken:TOKEN},{kind:'timezoneIpCancel',id:1,requestToken:'c'.repeat(64)},{kind:'timezoneIpCancel',id:1,requestToken:TOKEN,extra:true}])assert.equal(h.bootstrap.cancel(message),false);
  assert.ok(h.bootstrap.authorization(details()));assert.equal(cancel(h),true);assert.equal(cancel(h),false);assert.equal(await result,null);assert.equal(await h.bootstrap.lookup(lookup({id:2})),null);assert.equal(h.fetches.length,1);transport.resolve(response());await flush();h.setFetch((url,settings,owner)=>{owner.hooks.onBeforeRequest.emit(details({requestId:'new-id'}));return response();});assert.ok(await h.bootstrap.lookup(lookup({id:2})));assert.equal(h.fetches.length,2);
});
test('close removes observers, revokes authorization and cannot lend a late transport to a new port',async()=>{
  const {h,transport,result}=held();h.bootstrap.close();h.bootstrap.close();assert.equal(await result,null);assert.equal(h.hooks.onBeforeRequest.listeners.length,0);assert.equal(h.hooks.onBeforeRedirect.listeners.length,0);assert.equal(await h.bootstrap.lookup(lookup()),null);
  const next=h.context.PocketIpTimeZoneBootstrap.create({});assert.equal(await next.lookup(lookup({id:2})),null);assert.equal(h.fetches.length,1);transport.resolve(response());await flush();next.close();assert.equal(h.timers.size,0);
});
test('actual five-script startup adds no native message, lookup, content listener or timer',async()=>{
  const h=harness({full:true});await flush();assert.equal(h.fetches.length,0);assert.equal(h.nativeCalls.length,0);assert.deepEqual(h.ports[0].sent,[{kind:'requestHeadersPrepared',installed:true}]);assert.equal(h.runtimeMessage.listeners.length,0);assert.equal(h.timers.size,0);assert.equal(h.proxyHooks.length,1);assert.equal(h.hooks.onBeforeSendHeaders.listeners.length,1);
  await Promise.all(h.runtimeMessage.emit(lookup()));assert.equal(h.fetches.length,0);
});
test('actual private host lookup uses protected route and native UA while stripping sensitive headers',async()=>{
  const rawHeaders=[{name:'Cookie',value:'synthetic cookie'},{name:'Authorization',value:'synthetic auth'},{name:'Proxy-Authorization',value:'synthetic proxy'},{name:'Origin',value:'https://source.example'},{name:'Referer',value:'https://source.example/'},{name:'User-Agent',value:'stale'},{name:'Accept',value:'application/json'}];let aligned;
  const h=harness({full:true,fetch:async(url,settings,owner)=>{const request=details({requestHeaders:rawHeaders});owner.hooks.onBeforeRequest.emit(request);assert.deepEqual(await owner.proxy(request),{type:'http',host:'127.0.0.1',port:6543});aligned=await owner.headers(request);return response();}});await h.host(lookup());
  assert.deepEqual(h.nativeCalls.map(value=>value.message),[{kind:'timezoneIpRoute',url:SOURCE,method:'GET',requestToken:TOKEN,routeStamp:STAMP},{kind:'timezoneIpHeaders',url:SOURCE,method:'GET',requestToken:TOKEN,routeStamp:STAMP}]);assert.deepEqual(aligned.requestHeaders,[{name:'User-Agent',value:'ActualSdk/157'},{name:'Accept',value:'application/json'}]);assert.equal(rawHeaders.length,7);assert.equal(JSON.parse(h.ports[0].sent.at(-1).result).body,BODY);assert.equal(h.ports[0].sent.at(-1).kind,'timezoneIpReady');assert.equal(h.timers.size,0);
});
async function eventOrder(code,order,observeBefore=true){
  let routed,aligned;const h=harness({module:code,full:true,fetch:async(url,settings,owner)=>{
    const request=details({requestHeaders:[{name:'Cookie',value:'never send'},{name:'User-Agent',value:'old'}]});
    if(order==='before-first')owner.hooks.onBeforeRequest.emit(request);
    routed=await owner.proxy(request);
    assert.equal(routed.type,'http','Proxy-first owned lookup must receive its current protected route');
    if(order==='proxy-first'&&observeBefore)owner.hooks.onBeforeRequest.emit(request);
    aligned=await owner.headers(request);assert.deepEqual(aligned.requestHeaders,[{name:'User-Agent',value:'ActualSdk/157'}]);
    return response();
  }});await h.host(lookup());return {h,routed,aligned,result:h.ports[0].sent.at(-1).result};
}
test('both browser event orders use the same exact owned native route and header authorization',async()=>{
  for(const order of ['before-first','proxy-first']){const result=await eventOrder(MODULE,order);assert.equal(JSON.parse(result.result).body,BODY);assert.deepEqual(result.h.nativeCalls.map(row=>row.message.kind),['timezoneIpRoute','timezoneIpHeaders']);assert.equal(result.h.timers.size,0);}
});
test('proxy and headers may claim an owned request but final body still requires actual onBeforeRequest',async()=>{
  const result=await eventOrder(MODULE,'proxy-first',false);assert.equal(result.result,'null','A proxy claim without actual before-request observation must not become IP evidence');assert.equal(result.h.fetches.length,1);assert.equal(result.h.fetches[0].settings.signal.aborted,true);
});
test('ordinary and counterfeit IP requests retain the original route and header native messages',async()=>{
  const hold=deferred(),h=harness({full:true,fetch:(url,settings,owner)=>{owner.hooks.onBeforeRequest.emit(details());return hold.promise;}}),waiting=h.host(lookup());
  for(const request of [details({originUrl:'https://site.example/',documentUrl:undefined,requestId:'page'}),details({url:'https://site.example/',requestId:'ordinary'})]){await h.proxy(request);assert.deepEqual(await h.headers(request),{cancel:true});}
  assert.deepEqual(h.nativeCalls.map(value=>value.message.kind),['route','requestHeaderPolicy','route','requestHeaderPolicy']);await h.host({kind:'timezoneIpCancel',id:1,requestToken:TOKEN});hold.resolve(response());await waiting;assert.equal(h.ports[0].sent.at(-1).result,'null');
});
test('existing headerDecision runs first and its cancellation cannot be bypassed by bootstrap authorization',async()=>{
  const hold=deferred(),h=harness({full:true,fetch:(url,settings,owner)=>{owner.hooks.onBeforeRequest.emit(details());return hold.promise;}}),waiting=h.host(lookup());
  h.context.PocketRequestIdentityBackground={headerDecision(){return {cancel:true};},controlRequest(){throw Error('Sanitizer cancellation must win first');}};assert.deepEqual(await h.headers(details()),{cancel:true});assert.equal(h.nativeCalls.length,0);await h.host({kind:'timezoneIpCancel',id:1,requestToken:TOKEN});hold.resolve(response());await waiting;
});
test('a later sanitizer never restores removed headers or supplies a private-scope proof for IP bootstrap',async()=>{
  for(const privateScope of [false,true]){
    const hold=deferred(),h=harness({full:true,native:()=>JSON.stringify(privateScope?{allowed:true,revision:7,scope:'private-admission-unchanged'}:{allowed:true,revision:7,userAgent:'Native/157'}),fetch:(url,settings,owner)=>{owner.hooks.onBeforeRequest.emit(details());return hold.promise;}}),waiting=h.host(lookup());let calls=0;
    h.context.PocketRequestIdentityBackground={headerDecision(value){calls++;return calls===1?{requestHeaders:value.requestHeaders.filter(row=>row.name!=='X-Removed')}:{requestHeaders:[...value.requestHeaders,{name:'Cookie',value:'must stay removed'}]};},controlRequest:()=>false};
    const result=await h.headers(details({requestHeaders:[{name:'X-Removed',value:'remove'},{name:'Cookie',value:'secret'},{name:'Accept',value:'*/*'}]}));if(privateScope)assert.deepEqual(result,{cancel:true});else assert.deepEqual(result.requestHeaders,[{name:'Accept',value:'*/*'},{name:'User-Agent',value:'Native/157'}]);await h.host({kind:'timezoneIpCancel',id:1,requestToken:TOKEN});hold.resolve(response());await waiting;
  }
});
test('native route reply arriving after private cancellation cannot open the request',async()=>{
  const transport=deferred(),native=deferred(),h=harness({full:true,native:()=>native.promise,fetch:(url,settings,owner)=>{owner.hooks.onBeforeRequest.emit(details());return transport.promise;}}),lookupDone=h.host(lookup()),route=h.proxy(details());await h.host({kind:'timezoneIpCancel',id:1,requestToken:TOKEN});native.resolve(JSON.stringify({type:'direct'}));assert.equal((await route).port,9);transport.resolve(response());await lookupDone;
});
test('native header reply arriving after cancellation, revision change or disconnect is denied',async()=>{
  for(const kind of ['cancel','revision','disconnect']){
    const transport=deferred(),native=deferred(),h=harness({full:true,native:()=>native.promise,fetch:(url,settings,owner)=>{owner.hooks.onBeforeRequest.emit(details());return transport.promise;}}),lookupDone=h.host(lookup()),header=h.headers(details());
    if(kind==='cancel')await h.host({kind:'timezoneIpCancel',id:1,requestToken:TOKEN});if(kind==='revision')await h.host({kind:'requestHeaderPolicyChanged',revision:8});if(kind==='disconnect')await Promise.all(h.ports[0].onDisconnect.emit());native.resolve(JSON.stringify({allowed:true,revision:7,userAgent:'Old/157'}));assert.deepEqual(await header,{cancel:true});transport.resolve(response());await lookupDone;if(kind==='disconnect')assert.equal(h.ports[0].sent.some(value=>value.kind==='timezoneIpReady'),false);
  }
});
test('old native port cannot launch or cancel work belonging to a reconnected port',async()=>{
  const h=harness({full:true});await Promise.all(h.ports[0].onDisconnect.emit());h.advance(500);assert.equal(h.ports.length,2);await h.host(lookup(),h.ports[0]);assert.equal(h.fetches.length,0);
  const transport=deferred();h.setFetch((url,settings,owner)=>{owner.hooks.onBeforeRequest.emit(details({requestId:'reconnected'}));return transport.promise;});const current=h.host(lookup({id:2}),h.ports[1]);await h.host({kind:'timezoneIpCancel',id:2,requestToken:TOKEN},h.ports[0]);assert.equal(h.fetches.length,1);assert.equal(h.fetches[0].settings.signal.aborted,false);transport.resolve(response());await current;assert.equal(h.ports[1].sent.at(-1).kind,'timezoneIpReady');assert.equal(h.ports[1].sent.at(-1).id,2);assert.notEqual(h.ports[1].sent.at(-1).result,'null');
});
test('focused missing-authority mutation is rejected by the same actual-module ownership assertion',async()=>{
  const marker="url.protocol+'//'+url.host!==own";assert.equal(MODULE.split(marker).length,2);const mutant=MODULE.replace(marker,'false');
  for(const [code,reject] of [[MODULE,false],[mutant,true]]){
    const {h,transport,result}=held({module:code,request:details({originUrl:'moz-extension://foreign/bg',documentUrl:undefined})});
    const assertion=()=>assert.equal(h.bootstrap.authorization(details({originUrl:'moz-extension://foreign/bg',documentUrl:undefined})),null,'Foreign extension must not receive native bootstrap authorization');if(reject)assert.throws(assertion,error=>error instanceof assert.AssertionError&&error.message.includes('Foreign extension'));else assertion();transport.resolve(response());await result;
  }
});
test('focused raw-body normalization mutation is rejected by the unchanged raw-byte assertion',async()=>{
  const marker='source:SOURCE,body}';assert.equal(MODULE.split(marker).length,2);const raw=' {"success":true,"success":false} \n';
  for(const [code,reject] of [[MODULE,false],[MODULE.replace(marker,'source:SOURCE,body:JSON.stringify(JSON.parse(body))}'),true]]){
    const h=harness({module:code,fetch:(url,settings,owner)=>{owner.hooks.onBeforeRequest.emit(details());return response(raw);}}),observed=JSON.parse(await h.bootstrap.lookup(lookup()));const assertion=()=>assert.equal(observed.body,raw,'Original duplicate JSON bytes must reach native unchanged');if(reject)assert.throws(assertion,error=>error instanceof assert.AssertionError&&error.message.includes('Original duplicate'));else assertion();
  }
});
test('focused removed-byte-cap mutation is rejected by the actual oversized-body contract',async()=>{
  const marker='bytes+part.value.byteLength>MAX_BYTES';assert.equal(MODULE.split(marker).length,2);
  for(const [code,reject] of [[MODULE,false],[MODULE.replace(marker,'false'),true]]){
    const h=harness({module:code,fetch:(url,settings,owner)=>{owner.hooks.onBeforeRequest.emit(details());return response('x'.repeat(8193));}}),observed=await h.bootstrap.lookup(lookup());const assertion=()=>assert.equal(observed,null,'8193 raw bytes must be refused');if(reject)assert.throws(assertion,error=>error instanceof assert.AssertionError&&error.message.includes('8193 raw bytes'));else assertion();
  }
});
test('focused restored-before-first dependency mutation fails the actual proxy-first workload',async()=>{
  const marker='if(!job||!current(job)||!request(details))return null;';assert.equal(MODULE.split(marker).length,2);const mutant=MODULE.replace(marker,'if(!job||!current(job)||!job.beforeSeen||!request(details))return null;');
  // Fetch boundaries surface callback assertions as transport failures, so
  // assert the unchanged workload result instead of accepting any exception.
  const pristine=await eventOrder(MODULE,'proxy-first');assert.notEqual(pristine.result,'null');
  const denied=await eventOrder(mutant,'proxy-first');assert.equal(denied.result,'null');assert.equal(denied.routed.port,9);assert.deepEqual(denied.h.nativeCalls.map(row=>row.message.kind),['route']);
});
test('focused removed-before-observation fence is rejected by the actual final evidence assertion',async()=>{
  const marker='||!job.beforeSeen||';assert.equal(MODULE.split(marker).length,2);const mutant=MODULE.replace(marker,'||');
  const pristine=await eventOrder(MODULE,'proxy-first',false);assert.equal(pristine.result,'null');
  const accepted=await eventOrder(mutant,'proxy-first',false);const assertion=()=>assert.equal(accepted.result,'null','Unobserved before-request must not become native IP evidence');assert.throws(assertion,error=>error instanceof assert.AssertionError&&error.message.includes('Unobserved before-request'));
});
test.after(()=>{
  for(const [name,expected] of Object.entries(hashes))assert.equal(crypto.createHash('sha256').update(fs.readFileSync(path.join(ROOT,name))).digest('hex'),expected,'Actual source remained fixed: '+name);
  console.log('IP_TIMEZONE_JS_HOST_SOURCE '+JSON.stringify({sourceFiles:hashes,executionInputsUnchanged:true,actualAndroidExecution:false,actualGeckoExecution:false,actualNetworkExecution:false,scope:'Actual production modules in Node VM; explicit fetch stream, browser principal/request-id, private native-port and deterministic timer boundaries; no external endpoint or native browser executes.'}));
});
