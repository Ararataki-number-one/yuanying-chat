const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs'),path=require('node:path');
const ROOT=path.resolve(__dirname,'../..'),SOURCE=fs.readFileSync(path.join(ROOT,'app/src/main/assets/gecko/native-photo-api.js'),'utf8');
function harness(){
  const state={now:1000000,rfp:true,records:new Map(),writes:[],timers:new Map(),windows:[],closed:[],next:0,afterWrite:null};
  const perms={ALLOW_ACTION:1,DENY_ACTION:2,EXPIRE_SESSION:1,
    getPermissionObject(p,type){assert.equal(type,'canvas');const v=state.records.get(p.origin);if(v?.expireTime&&v.expireTime<=state.now){state.records.delete(p.origin);return null;}return v??null;},
    testPermissionFromPrincipal(p,type){return this.getPermissionObject(p,type)?.capability??0;},
    addFromPrincipal(p,type,capability,expireType,expireTime){assert.equal(type,'canvas');state.writes.push({origin:p.origin,capability,expireType,expireTime});state.records.set(p.origin,{principal:p,capability,expireType,expireTime});state.afterWrite?.();},
    removeFromPrincipal(p,type){assert.equal(type,'canvas');state.writes.push({origin:p.origin,remove:true});state.records.delete(p.origin);}};
  const services={'@mozilla.org/permissionmanager;1':perms,'@mozilla.org/preferences-service;1':{getBoolPref(name){return name==='privacy.resistFingerprinting'&&state.rfp;}},
    '@mozilla.org/appshell/window-mediator;1':{getEnumerator(){let i=0;return {hasMoreElements:()=>i<state.windows.length,getNext:()=>state.windows[i++]};}}};
  const Ci={nsIPermissionManager:{},nsIPrefBranch:{},nsIWindowMediator:{},nsIWebProgressListener:{STATE_START:1,STATE_IS_DOCUMENT:2},nsIWebProgress:{NOTIFY_STATE_DOCUMENT:1,NOTIFY_LOCATION:2}};
  const context=vm.createContext({Cc:Object.fromEntries(Object.entries(services).map(([k,v])=>[k,{getService:()=>v}])),Ci,Date:class extends Date{static now(){return state.now;}},ChromeUtils:{generateQI:()=>()=>{},importESModule(url){
    if(url.endsWith('ExtensionCommon.sys.mjs'))return {ExtensionCommon:{ExtensionAPI:class{}}};
    if(url.endsWith('ExtensionUtils.sys.mjs'))return {ExtensionUtils:{ExtensionError:Error}};
    if(url.endsWith('Timer.sys.mjs'))return {setTimeout(action,ms){const id=++state.next;state.timers.set(id,{action,at:state.now+ms,ms});return id;},clearTimeout(id){state.timers.delete(id);}};
    throw Error(url);}}});
  vm.runInContext(SOURCE,context,{filename:'native-photo-api.js'});
  function window(id='session:one',origin='https://photos.example',attrs=''){
    const principal={isContentPrincipal:true,URI:{scheme:'https'},originNoSuffix:origin,origin:origin+attrs,originAttributes:{privateBrowsingId:attrs.includes('private')?1:0,userContextId:attrs.includes('userContextId=')?8:0},equals(other){return this.origin===other.origin;}};
    const listeners=new Set(),events=new Map(),global={innerWindowId:++state.next,documentPrincipal:principal};
    const top={currentWindowGlobal:global};top.top=top;
    const w={name:id,closed:false,document:{documentElement:{getAttribute:()=> 'navigator:geckoview'}},browser:{browsingContext:top,webProgress:{addProgressListener(v){listeners.add(v);},removeProgressListener(v){listeners.delete(v);}}},
      addEventListener(name,fn){events.set(name,fn);},removeEventListener(name,fn){if(events.get(name)===fn)events.delete(name);},principal,listeners,events};
    state.windows.push(w);return w;
  }
  const authorized={envType:'addon_parent',extension:{id:'browser@pocketchat.local',isPrivileged:true},callOnClose(v){state.closed.push(v);}};
  const parent=new context.pocketNativePhoto(),api=parent.getAPI(authorized).pocketNativePhoto;
  const capture=(w,token)=>api.captureSession(w.name,w.principal.originNoSuffix,token),grant=(w,token)=>api.grantSession(w.name,token),release=(w,token)=>api.releaseSession(w.name,token);
  const navigate=w=>{for(const l of [...w.listeners])l.onStateChange({isTopLevel:true},null,3);w.browser.browsingContext.currentWindowGlobal={innerWindowId:++state.next,documentPrincipal:w.principal};};
  const advance=ms=>{state.now+=ms;for(const [id,timer]of [...state.timers])if(timer.at<=state.now){state.timers.delete(id);timer.action();}};
  return {state,perms,parent,authorized,api,window,capture,grant,release,navigate,advance};
}
test('only the bundled privileged parent exposes a photo operation',()=>{
 const h=harness();for(const change of [{envType:'addon_child'},{extension:{id:'foreign',isPrivileged:true}},{extension:{id:'browser@pocketchat.local',isPrivileged:false}}])assert.throws(()=>h.parent.getAPI({...h.authorized,...change}),/app-bundled-photo/);assert.equal(h.state.writes.length,0);
});
test('capture is read-only and grant preserves RFP with a native session-expiring bound',async()=>{
 const h=harness(),w=h.window();await h.capture(w,'selected');assert.equal(h.state.writes.length,0);
 const receipt=await h.grant(w,'selected');assert.equal(receipt.status,'granted');assert.equal(receipt.expiresAt,h.state.now+120000);assert.equal(h.state.rfp,true);assert.equal(h.state.writes[0].expireType,h.perms.EXPIRE_SESSION);
 await h.release(w,'selected');assert.equal(h.perms.testPermissionFromPrincipal(w.principal,'canvas'),0);assert.equal(w.listeners.size,0);assert.equal(h.state.timers.size,0);
});
test('same-origin concurrent selections retain the other lease and shorten native expiry safely',async()=>{
 const h=harness(),a=h.window(),b=h.window('session:two');await h.capture(a,'a');await h.grant(a,'a');const original=h.state.now+120000;
 h.advance(10000);await h.capture(b,'b');await h.grant(b,'b');assert.equal(h.state.records.get(a.principal.origin).expireTime,h.state.now+120000);
 await h.release(b,'b');assert.equal(h.state.records.get(a.principal.origin).expireTime,original);assert.equal(h.perms.testPermissionFromPrincipal(a.principal,'canvas'),1);
 await h.release(a,'a');assert.equal(h.perms.testPermissionFromPrincipal(a.principal,'canvas'),0);
});
test('navigation of one same-origin tab cannot revoke another current selection',async()=>{
 const h=harness(),a=h.window(),b=h.window('session:two');await h.capture(a,'a');await h.grant(a,'a');await h.capture(b,'b');await h.grant(b,'b');h.navigate(a);assert.equal(h.perms.testPermissionFromPrincipal(b.principal,'canvas'),1);h.navigate(b);assert.equal(h.perms.testPermissionFromPrincipal(b.principal,'canvas'),0);
});
test('other origins and native origin-attributes namespaces are never borrowed',async()=>{
 const h=harness(),a=h.window(),b=h.window('session:two','https://photos.example','^privateBrowsingId=1'),c=h.window('session:three','https://other.example');await h.capture(a,'a');await h.grant(a,'a');
 assert.equal(h.perms.testPermissionFromPrincipal(b.principal,'canvas'),0);assert.equal(h.perms.testPermissionFromPrincipal(c.principal,'canvas'),0);
 await h.capture(b,'b');await h.grant(b,'b');await h.release(a,'a');assert.equal(h.perms.testPermissionFromPrincipal(b.principal,'canvas'),1);await h.release(b,'b');
});
test('pre-existing allow and explicit deny are neither overwritten nor removed',async()=>{
 for(const capability of [1,2]){const h=harness(),w=h.window();h.state.records.set(w.principal.origin,{principal:w.principal,capability,expireType:0,expireTime:0});await h.capture(w,'a');const r=await h.grant(w,'a');assert.equal(r.status,capability===1?'existing':'denied');await h.release(w,'a');assert.equal(h.state.writes.length,0);assert.equal(h.perms.testPermissionFromPrincipal(w.principal,'canvas'),capability);}
});
test('unsupported native containers are refused before any permission can escape their namespace',async()=>{
 const h=harness(),w=h.window('container','https://photos.example','^userContextId=8');await assert.rejects(h.capture(w,'a'),/container-permission-unavailable/);assert.equal(h.state.writes.length,0);
});
test('an external permission change is preserved on cancellation and cannot be erased by an older lease',async()=>{
 const h=harness(),a=h.window(),b=h.window('session:two');await h.capture(a,'a');await h.grant(a,'a');h.state.records.set(a.principal.origin,{principal:a.principal,capability:2,expireType:0,expireTime:0});await h.release(a,'a');assert.equal(h.perms.testPermissionFromPrincipal(a.principal,'canvas'),2);
 h.state.records.delete(a.principal.origin);await h.capture(a,'old');await h.grant(a,'old');h.state.records.delete(a.principal.origin);h.advance(1000);await h.capture(b,'new');await h.grant(b,'new');await h.release(a,'old');assert.equal(h.perms.testPermissionFromPrincipal(b.principal,'canvas'),1);await h.release(b,'new');assert.equal(h.perms.testPermissionFromPrincipal(b.principal,'canvas'),0);
});
test('same-URL replacement, wrong origin, ambiguous session, stale or reused token cannot grant',async()=>{
 const h=harness(),w=h.window();await assert.rejects(h.api.captureSession(w.name,'https://foreign.example','a'),/document-unavailable/);await assert.rejects(h.grant(w,'unknown'),/stale/);
 await h.capture(w,'a');w.browser.browsingContext.currentWindowGlobal={innerWindowId:999,documentPrincipal:w.principal};await assert.rejects(h.grant(w,'a'),/stale/);assert.equal(h.state.writes.length,0);
 await h.capture(w,'a');await h.grant(w,'a');await assert.rejects(h.grant(w,'a'),/stale/);assert.equal(h.perms.testPermissionFromPrincipal(w.principal,'canvas'),0);
 h.window(w.name);await assert.rejects(h.capture(w,'ambiguous'),/ambiguous/);
});
test('native expiry, document navigation, window close and extension teardown retire grants',async()=>{
 for(const end of ['expiry','navigation','close','disconnect','shutdown']){const h=harness(),w=h.window();await h.capture(w,'a');await h.grant(w,'a');
  if(end==='expiry')h.advance(120000);if(end==='navigation')h.navigate(w);if(end==='close')w.events.get('unload')();if(end==='disconnect')await h.api.releaseAll();if(end==='shutdown')h.parent.onShutdown();
  assert.equal(h.perms.testPermissionFromPrincipal(w.principal,'canvas'),0,end);assert.equal(h.state.timers.size,0,end);assert.equal(w.listeners.size,0,end);}
});
test('cancelled picker, expired capture and standard mode never create a grant',async()=>{
 const h=harness(),w=h.window();await h.capture(w,'cancel');await h.release(w,'cancel');await assert.rejects(h.grant(w,'cancel'),/stale/);
 await h.capture(w,'late');h.advance(900000);await assert.rejects(h.grant(w,'late'),/stale/);
 h.state.rfp=false;await h.capture(w,'standard');assert.equal((await h.grant(w,'standard')).status,'not-required');assert.equal(h.state.writes.length,0);
});
test('a native write that throws after mutation is still retired and never leaks a failed grant',async()=>{
 const h=harness(),w=h.window();await h.capture(w,'a');h.state.afterWrite=()=>{throw Error('uncertain setter completion');};await assert.rejects(h.grant(w,'a'),/uncertain/);assert.equal(h.perms.testPermissionFromPrincipal(w.principal,'canvas'),0);assert.equal(h.state.timers.size,0);
});

test('actual photo bridge rejects malformed requests and native receipts without creating a permission',async()=>{
 const h=harness(),w=h.window(),calls=[],listeners=[];
 const api=Object.fromEntries(['captureSession','grantSession','releaseSession','releaseAll'].map(name=>[name,(...args)=>{calls.push({name,args});return h.api[name](...args);}]))
 const context=vm.createContext({browser:{pocketNativePhoto:api,runtime:{onMessage:{addListener(fn){listeners.push(fn);}}}}});
 const bridgeSource=fs.readFileSync(path.join(ROOT,'app/src/main/assets/gecko/native-photo-bridge.js'),'utf8');
 vm.runInContext(bridgeSource,context,{filename:'native-photo-bridge.js'});const bridge=context.PocketNativePhotoBridge;
 const selected={kind:'photoCanvasCapture',id:1,sessionId:w.name,requestToken:'native-picker',origin:w.principal.originNoSuffix};
 const grant={kind:'photoCanvasGrant',id:2,sessionId:w.name,requestToken:'native-picker'};
 for(const bad of [null,[],{}, {...selected,kind:'from-page'},... [0,-1,1.5,2147483648,'1'].map(id=>({...selected,id})),
  {...selected,requestToken:'wrong\ntoken'},{...selected,sessionId:'https://private.example/'},{...selected,documentId:'page-supplied'},
  {...grant,origin:selected.origin},{...selected,origin:null}])assert.equal((await bridge.handle(bad)).status,'failed');
 assert.equal(calls.length,0);assert.equal(listeners.length,0);assert.equal(Object.isFrozen(bridge),true);
 const captured=await bridge.handle(selected);assert.equal(captured.status,'captured');assert.equal(h.state.writes.length,0);
 assert.deepEqual(calls,[{name:'captureSession',args:[w.name,w.principal.originNoSuffix,'native-picker']}]);
 for(const change of [{requestToken:'another-picker'},{sessionId:'another-session'},{documentId:'0'},{scope:'whole-runtime'},{origin:'https://foreign.example'},{expiresAt:1.5}]){
  api.captureSession=async()=>({...captured,...change});assert.equal((await bridge.handle(selected)).status,'failed');
 }
 assert.equal(h.state.writes.length,0);await bridge.clear();assert.equal(h.state.timers.size,0);
});

test('actual bundled background routes photos only from the current native port and clears leases on disconnect',async()=>{
 const h=harness(),w=h.window(),plain=value=>JSON.parse(JSON.stringify(value));
 const event=()=>({listeners:[],addListener(fn){this.listeners.push(fn);},async emit(...args){return Promise.all(this.listeners.map(fn=>fn(...args)));}});
 const ports=[],publicMessages=event(),timers=new Map();let timerId=0;
 const browser={pocketNativePhoto:h.api,runtime:{getURL:()=> 'moz-extension://own-runtime/',onMessage:publicMessages,connectNative(app){assert.equal(app,'pocketroute');const port={sent:[],onMessage:event(),onDisconnect:event(),postMessage(value){this.sent.push(plain(value));}};ports.push(port);return port;},sendNativeMessage(){throw Error('No network in photo host-route controls');}},webRequest:{},proxy:{onRequest:{addListener(){}}},cookies:{onChanged:event(),async getAll(){return [];},async set(){throw Error('No cookie restore in photo fixture');}},storage:{local:{async get(){return {};},async set(){}}},privacy:{websites:{resistFingerprinting:{onChange:event(),async set(){},async get(){return {value:false};}}}}};
 for(const name of ['onBeforeRequest','onBeforeSendHeaders','onHeadersReceived'])browser.webRequest[name]={addListener(){},removeListener(){}};
 const context=vm.createContext({browser,URL,Intl,Date,AbortController,TextDecoder,Uint8Array,setTimeout(fn,delay){const id=++timerId;timers.set(id,{fn,delay});return id;},clearTimeout(id){timers.delete(id);},fetch(){throw Error('No network in photo host-route controls');}});
 const manifest=JSON.parse(fs.readFileSync(path.join(ROOT,'app/src/main/assets/gecko/manifest.json'),'utf8'));
 for(const name of manifest.background.scripts)vm.runInContext(fs.readFileSync(path.join(ROOT,'app/src/main/assets/gecko',name),'utf8'),context,{filename:name});
 assert.equal(ports.length,1);assert.equal(publicMessages.listeners.length,0);const first=ports[0];
 const capture={kind:'photoCanvasCapture',id:31,sessionId:w.name,requestToken:'selected-file',origin:w.principal.originNoSuffix};
 const grant={kind:'photoCanvasGrant',id:32,sessionId:w.name,requestToken:'selected-file'};
 await publicMessages.emit(capture,{id:'browser@pocketchat.local',url:'https://photos.example'});assert.equal(w.listeners.size,0);
 await first.onMessage.emit(capture);assert.equal(first.sent.at(-1).kind,'photoCanvasReady');assert.equal(first.sent.at(-1).id,31);
 assert.equal(JSON.parse(first.sent.at(-1).result).status,'captured');assert.equal(h.state.writes.length,0);
 await first.onMessage.emit({...grant,origin:w.principal.originNoSuffix});assert.equal(JSON.parse(first.sent.at(-1).result).status,'failed');assert.equal(h.state.writes.length,0);
 await first.onMessage.emit(grant);assert.equal(first.sent.at(-1).id,32);assert.equal(JSON.parse(first.sent.at(-1).result).status,'granted');assert.equal(h.perms.testPermissionFromPrincipal(w.principal,'canvas'),1);
 await first.onDisconnect.emit();assert.equal(h.perms.testPermissionFromPrincipal(w.principal,'canvas'),0);assert.equal(h.state.timers.size,0);assert.equal(w.listeners.size,0);
 const reconnect=[...timers].find(([,timer])=>timer.delay===500);assert.ok(reconnect);timers.delete(reconnect[0]);reconnect[1].fn();assert.equal(ports.length,2);
 const previous=first.sent.length;await first.onMessage.emit(capture);assert.equal(first.sent.length,previous);assert.equal(w.listeners.size,0);
 const second=ports[1];await second.onMessage.emit(capture);await second.onMessage.emit(grant);assert.equal(JSON.parse(second.sent.at(-1).result).status,'granted');
 await second.onMessage.emit({...grant,kind:'photoCanvasRelease',id:33});assert.equal(JSON.parse(second.sent.at(-1).result).status,'released');assert.equal(h.perms.testPermissionFromPrincipal(w.principal,'canvas'),0);assert.equal(publicMessages.listeners.length,0);
});
