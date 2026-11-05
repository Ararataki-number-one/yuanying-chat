'use strict';

// Actual bridge and optional actual parent-API source run against declared VM
// browser/window/BrowsingContext doubles. No native Gecko or timezone effect is
// established by these controls; Date/Intl/Worker observations remain separate.
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const ROOT=path.resolve(__dirname,'../..');
const SOURCE=fs.readFileSync(path.join(ROOT,'app/src/main/assets/gecko/native-timezone-bridge.js'),'utf8');
const NATIVE=fs.readFileSync(path.join(ROOT,'app/src/main/assets/gecko/native-timezone-api.js'),'utf8');
const MANIFEST=JSON.parse(fs.readFileSync(path.join(ROOT,'app/src/main/assets/gecko/manifest.json'),'utf8'));
const plain=value=>JSON.parse(JSON.stringify(value));
const apply=(zoneId='Asia/Shanghai')=>({kind:'timezoneApply',id:1,sessionId:'session:one',requestToken:'request-1',zoneId});
const read=()=>({kind:'timezoneRead',id:2,sessionId:'session:one',requestToken:'request-2'});
const ack=(selected,status=selected.kind==='timezoneApply'?'applied':'read',zoneId=selected.zoneId??'Asia/Shanghai')=>({schema:1,status,requestToken:selected.requestToken,sessionId:selected.sessionId,requestedZoneId:zoneId,nativeZoneId:zoneId,contextId:'8589934593',nativeSettingReadback:true,scope:'top-browsing-context',workerCoverageVerified:false,serviceWorkerCoverageVerified:false});
function harness(api){
  const runtimeListeners=[],context=vm.createContext({browser:{pocketNativeTimezone:api,runtime:{onMessage:{addListener(value){runtimeListeners.push(value);}}}},Intl,Date});
  vm.runInContext(SOURCE,context,{filename:'native-timezone-bridge.js'});
  return {context,api:context.PocketNativeTimezoneBridge,runtimeListeners,async handle(value){return plain(await this.api.handle(value));}};
}
test('bridge is frozen, registers no content/runtime listener and leaves Date/Intl unchanged',()=>{
  const h=harness({});assert.equal(Object.isFrozen(h.api),true);assert.equal(h.runtimeListeners.length,0);assert.equal(h.context.Date,Date);assert.equal(h.context.Intl,Intl);assert.equal(typeof h.api.handle,'function');assert.deepEqual(Object.keys(h.api),['handle']);
});
test('valid apply calls exact API with original IANA token and returns only native typed receipt',async()=>{
  const selected=apply('US/Eastern'),calls=[],h=harness({async applySession(...args){calls.push(args);return ack(selected);}});const value=await h.handle(selected);assert.deepEqual(calls,[[selected.sessionId,'US/Eastern',selected.requestToken]]);assert.deepEqual(value,ack(selected));assert.equal(value.requestedZoneId,'US/Eastern');assert.equal('id' in value,false);
});
test('system reset remains the empty native override, never a guessed system IANA name',async()=>{
  const selected=apply(''),h=harness({async applySession(sessionId,zoneId,requestToken){assert.equal(zoneId,'');return ack(selected);}});assert.deepEqual(await h.handle(selected),ack(selected));
});
test('read calls exact API, validates its setting and never asks Intl for a native acknowledgement',async()=>{
  const selected=read(),calls=[],h=harness({async readSession(...args){calls.push(args);return ack(selected,'read','Europe/Paris');}});assert.deepEqual(await h.handle(selected),ack(selected,'read','Europe/Paris'));assert.deepEqual(calls,[[selected.sessionId,selected.requestToken]]);
  const system=harness({async readSession(){return ack(selected,'read','');}});assert.equal((await system.handle(selected)).nativeZoneId,'');
});
test('bad kind/id/session/token/zone or extra fields never invoke native API',async()=>{
  let calls=0;const h=harness({async applySession(){calls++;},async readSession(){calls++;}});
  const cases=[null,[],{}, {...apply(),kind:'from-page'},... [0,-1,1.5,2147483648,'1',NaN].map(id=>({...apply(),id})),... ['', 'a'.repeat(161),'session/one','https://private.example/'].map(sessionId=>({...apply(),sessionId})),... ['', 'a'.repeat(161),'request\n1'].map(requestToken=>({...apply(),requestToken})),... ['Not/A_Real_Zone','Asia/Shanghai\n','Europe/Paris?x=1','a'.repeat(81),null,42].map(zoneId=>({...apply(),zoneId})),{...apply(),url:'https://private.example/'},{...read(),zoneId:'Asia/Shanghai'}];
  for(const value of cases){const result=await h.handle(value);assert.equal(result.status,'failed');assert.equal(result.nativeSettingReadback,false);assert.equal(result.reason,'invalid-timezone-request');assert.equal(JSON.stringify(result).includes('private.example'),false);}assert.equal(calls,0);
});
test('missing namespace or required method returns explicit unsupported without native confirmation',async()=>{
  for(const api of [undefined,null,{}, {readSession(){throw Error('wrong method');}}]){const result=await harness(api).handle(apply());assert.equal(result.status,'unsupported');assert.equal(result.nativeSettingReadback,false);assert.equal(result.reason,'native-timezone-api-unavailable');assert.equal(result.workerCoverageVerified,false);assert.equal(result.serviceWorkerCoverageVerified,false);assert.equal(result.contextId,'');}
});
test('native API failure reasons are bounded and never leak exception text',async()=>{
  for(const reason of ['native-timezone-property-unavailable','native-timezone-readback-unavailable','timezone-window-enumeration-unavailable','https://sensitive.example/private?token=secret']){const result=await harness({async applySession(){throw Error(reason);}}).handle(apply());assert.equal(result.nativeSettingReadback,false);assert.equal(result.status,reason.startsWith('https:')?'failed':'unsupported');assert.equal(result.reason,reason.startsWith('https:')?'native-timezone-call-failed':reason);assert.equal(JSON.stringify(result).includes('sensitive.example'),false);}
});
test('wrong identities/types/status/scope/context/worker claims or extra receipt fields cannot confirm',async()=>{
  const selected=apply(),good=ack(selected),changes=[{schema:'1'},{schema:2},{status:'read'},{requestToken:'another-token'},{sessionId:'another-session'},{requestedZoneId:'Asia/Tokyo'},{nativeZoneId:'Asia/Tokyo'},{nativeZoneId:'invalid-zone'},{contextId:8589934593},{contextId:'0'},{contextId:'01'},{contextId:'1'.repeat(25)},{nativeSettingReadback:'true'},{nativeSettingReadback:false},{scope:'whole-runtime'},{workerCoverageVerified:true},{serviceWorkerCoverageVerified:true},{pageObservationVerified:true}];
  for(const change of changes){const result=await harness({async applySession(){return {...good,...change};}}).handle(selected);assert.equal(result.status,'failed');assert.equal(result.reason,'native-timezone-receipt-invalid');assert.equal(result.nativeSettingReadback,false);}
  for(const raw of [null,[],JSON.stringify(good),{status:'unsupported'}])assert.equal((await harness({async applySession(){return raw;}}).handle(selected)).nativeSettingReadback,false);
});
test('native read must agree on its own requested/native setting and still match original identity',async()=>{
  const selected=read(),bad={...ack(selected,'read','Europe/Paris'),nativeZoneId:'Asia/Shanghai'},h=harness({async readSession(){return bad;}});assert.equal((await h.handle(selected)).nativeSettingReadback,false);
});
test('input mutation while native call is pending cannot rebind the request or confirm a later identity',async()=>{
  let resolve;const held=new Promise(yes=>{resolve=yes;}),selected=apply(),original=plain(selected),h=harness({applySession(){return held;}});const waiting=h.handle(selected);selected.sessionId='later-session';selected.requestToken='later-token';selected.zoneId='Europe/Paris';resolve(ack(original));assert.deepEqual(await waiting,ack(original));
});
test('actual bundled parent API matches only one named session and preserves separate context settings',async()=>{
  const one={id:8589934593,timezoneOverride:''},two={id:8589934594,timezoneOverride:''};
  const window=(name,top)=>({name,closed:false,document:{documentElement:{getAttribute:key=>key==='windowtype'?'navigator:geckoview':''}},browser:{browsingContext:{top}}});
  const windows=[window('session:one',one),window('session:two',two)],components={classes:{'@mozilla.org/appshell/window-mediator;1':{getService(){return {getEnumerator(){let index=0;return {hasMoreElements:()=>index<windows.length,getNext:()=>windows[index++]};}};}}},interfaces:{nsIWindowMediator:{}}};
  const context=vm.createContext({Intl,Cc:components.classes,Ci:components.interfaces,ChromeUtils:{importESModule(url){if(url==='resource://gre/modules/ExtensionCommon.sys.mjs')return {ExtensionCommon:{ExtensionAPI:class {}}};if(url==='resource://gre/modules/ExtensionUtils.sys.mjs')return {ExtensionUtils:{ExtensionError:class extends Error {}}};throw Error('Unexpected parent module');}}});vm.runInContext(NATIVE,context,{filename:'native-timezone-api.js'});
  const parent=new context.pocketNativeTimezone(),authorized={envType:'addon_parent',extension:{id:'browser@pocketchat.local',isPrivileged:true}};
  // These are declared privileged-extension VM context fields, not privilege
  // obtained in Gecko. The actual production API must reject each missing or
  // foreign scope before exposing an operation to any window double.
  for(const denied of [{extension:authorized.extension},{...authorized,envType:'addon_child'},{...authorized,extension:{...authorized.extension,id:'foreign@example.invalid'}},{...authorized,extension:{...authorized.extension,isPrivileged:false}}])assert.throws(()=>parent.getAPI(denied),/app-bundled-timezone-api-only/);
  const native=parent.getAPI(authorized).pocketNativeTimezone,h=harness(native);
  const first=await h.handle(apply('Asia/Shanghai'));assert.equal(first.nativeSettingReadback,true);assert.equal(first.contextId,'8589934593');assert.equal(one.timezoneOverride,'Asia/Shanghai');assert.equal(two.timezoneOverride,'');
  const other=apply('Europe/Paris');other.sessionId='session:two';other.requestToken='other-request';const second=await h.handle(other);assert.equal(second.contextId,'8589934594');assert.equal(one.timezoneOverride,'Asia/Shanghai');assert.equal(two.timezoneOverride,'Europe/Paris');
  assert.equal((await h.handle(read())).nativeZoneId,'Asia/Shanghai');assert.equal((await h.handle(apply(''))).nativeZoneId,'');assert.equal(two.timezoneOverride,'Europe/Paris');
  windows.push(window('session:one',{id:33,timezoneOverride:''}));assert.equal((await h.handle(apply())).nativeSettingReadback,false);
});
test('actual manifest host-only glue correlates ACKs and cannot publish a disconnected or content-origin operation',async()=>{
  assert.deepEqual(MANIFEST.background.scripts,['request-headers.js','request-identity-background.js','native-timezone-bridge.js','background.js']);
  const event=()=>({listeners:[],addListener(callback){this.listeners.push(callback);},async emit(...args){return Promise.all(this.listeners.map(callback=>callback(...args)));}});
  const ports=[],nativeCalls=[],timers=new Map(),publicMessages=event();let timerId=0,heldResolve,hold=false;
  const api={async applySession(sessionId,zoneId,requestToken){nativeCalls.push({method:'applySession',sessionId,zoneId,requestToken});const result=ack({kind:'timezoneApply',sessionId,zoneId,requestToken});return hold?new Promise(resolve=>{heldResolve=()=>resolve(result);}):result;},async readSession(sessionId,requestToken){nativeCalls.push({method:'readSession',sessionId,requestToken});return ack({kind:'timezoneRead',sessionId,requestToken},'read','Asia/Shanghai');}};
  const browser={pocketNativeTimezone:api,runtime:{getURL:()=> 'moz-extension://own-runtime/',onMessage:publicMessages,connectNative(app){assert.equal(app,'pocketroute');const port={sent:[],onMessage:event(),onDisconnect:event(),postMessage(message){this.sent.push(plain(message));}};ports.push(port);return port;},sendNativeMessage(){throw Error('No HTTP request in timezone host-glue controls');}},webRequest:{},proxy:{onRequest:{addListener(){}}},cookies:{onChanged:event(),async getAll(){return [];},async set(){throw Error('No restored cookies in fixture');}},storage:{local:{async get(){return {};},async set(){}}},privacy:{websites:{resistFingerprinting:{onChange:event(),async set(){},async get(){return {value:false};}}}}};
  for(const name of ['onBeforeRequest','onBeforeSendHeaders','onHeadersReceived'])browser.webRequest[name]={addListener(){},removeListener(){}};
  const context=vm.createContext({browser,URL,Intl,Date,AbortController,TextDecoder,Uint8Array,setTimeout(callback,delay){const id=++timerId;timers.set(id,{callback,delay});return id;},clearTimeout(id){timers.delete(id);},fetch(){throw Error('No network in timezone host-glue controls');}});
  for(const name of MANIFEST.background.scripts)vm.runInContext(fs.readFileSync(path.join(ROOT,'app/src/main/assets/gecko',name),'utf8'),context,{filename:name});
  assert.equal(ports.length,1);const first=ports[0];assert.deepEqual(first.sent,[{kind:'requestHeadersPrepared',installed:true}]);assert.equal(publicMessages.listeners.length,0);
  await publicMessages.emit(apply(),{id:'browser@pocketchat.local',url:'https://chatgpt.com/c/page'});assert.equal(nativeCalls.length,0,'No page/content message listener forwards native timezone operations');
  await first.onMessage.emit(apply());assert.deepEqual(nativeCalls,[{method:'applySession',sessionId:'session:one',zoneId:'Asia/Shanghai',requestToken:'request-1'}]);const applied=first.sent.at(-1);assert.equal(applied.kind,'timezoneReady');assert.equal(applied.id,1);assert.deepEqual(JSON.parse(applied.result),ack(apply()));
  await first.onMessage.emit(read());assert.equal(first.sent.at(-1).id,2);assert.equal(JSON.parse(first.sent.at(-1).result).status,'read');
  hold=true;const pending=apply('Europe/Paris');pending.id=3;pending.requestToken='pending-token';const waiting=first.onMessage.emit(pending);await first.onDisconnect.emit();const before=first.sent.length;heldResolve();await waiting;assert.equal(first.sent.length,before,'Late native ACK cannot be posted by a disconnected owner');
  const reconnect=[...timers].find(([,value])=>value.delay===500);assert.ok(reconnect);timers.delete(reconnect[0]);reconnect[1].callback();assert.equal(ports.length,2);const second=ports[1];assert.deepEqual(second.sent,[{kind:'requestHeadersPrepared',installed:true}]);
  const callsBefore=nativeCalls.length;await first.onMessage.emit(apply());assert.equal(nativeCalls.length,callsBefore,'Old host cannot invoke API after replacement');
  hold=false;const fresh=apply('Asia/Tokyo');fresh.id=4;fresh.requestToken='new-owner-token';await second.onMessage.emit(fresh);assert.equal(second.sent.at(-1).id,4);assert.deepEqual(JSON.parse(second.sent.at(-1).result),ack(fresh));assert.equal(publicMessages.listeners.length,0);
});
