'use strict';
// Current diagnostic scripts; declared browser/fetch/native boundaries, no Android or network.
const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs'),path=require('node:path');
const ROOT=path.resolve(__dirname,'..'),base=path.join(ROOT,'tests/request-identity/ip_timezone_bootstrap_test.cjs');
const original=fs.readFileSync(base,'utf8'),prefix=original.slice(0,original.indexOf("test('fixed GET"));
const model={require,console,URL,Date,AbortController,TextDecoder,TextEncoder,Uint8Array,__dirname:path.dirname(base),module:{exports:{}}};
vm.runInNewContext(prefix+'\nmodule.exports={harness,details,lookup,response,held,flush,SOURCE,TOKEN,STAMP};',model,{filename:base});
const {harness,details,lookup,response,held,flush,SOURCE,TOKEN,STAMP}=model.module.exports;
const nonce='c'.repeat(32),plain=x=>JSON.parse(JSON.stringify(x));
const snapshot=h=>plain(h.context.PocketIpTimeZoneDiagnostic.snapshot(nonce));
test('positive actual script wrapper retains raw body and records create/fetch without native diagnostics until asked',async()=>{
 const h=harness();const raw=await h.bootstrap.lookup(lookup());assert.ok(JSON.parse(raw).body);const d=snapshot(h);assert.equal(d.diagnosticOnly,true);assert.equal(d.releaseAcceptance,false);assert.equal(d.events[0].stage,'bootstrap-loaded');for(const stage of ['create-enter','create-ready','lookup-received','lookup-start','fetch-start','before-request','fetch-response','finish-observed'])assert.ok(d.events.some(x=>x.stage===stage),stage);assert.equal(h.nativeCalls.length,0);assert.equal(h.timers.size,0);
});
test('actual private current host command returns only separate diagnostic native message',async()=>{
 const h=harness({full:true});h.browser.runtime.getManifest=()=>({version:'2.1.2.104',browser_specific_settings:{gecko:{id:'browser@pocketchat.local'}},background:{scripts:['ip-timezone-bootstrap.js','request-headers.js','request-identity-background.js','native-timezone-bridge.js','background.js']}});
 await h.host({kind:'timezoneIpDiagnosticSnapshot',requestNonce:nonce});assert.equal(h.nativeCalls.length,2);assert.ok(h.nativeCalls.every(call=>call.app==='pocketipdiagnostic'));assert.deepEqual(plain(h.nativeCalls.find(call=>call.message.kind==='hello').message),{schema:1,kind:'hello',diagnosticOnly:true,releaseAcceptance:false});const call=h.nativeCalls.find(call=>call.message.requestNonce===nonce);assert.equal(call.app,'pocketipdiagnostic');assert.equal(call.message.requestNonce,nonce);assert.equal(call.message.runtimeManifest.version,'2.1.2.104');assert.equal(call.message.runtimeManifest.scripts.length,5);assert.equal(call.message.bootstrapCreate,true);assert.equal(call.message.helperPresence.identity,'object');assert.equal(h.fetches.length,0);assert.equal(h.timers.size,0);
});
test('runtime manifest unknown values are enums, never arbitrary strings or paths',()=>{
 const h=harness();h.browser.runtime.getManifest=()=>({version:'secret-version',browser_specific_settings:{gecko:{id:'foreign-secret'}},background:{scripts:['/private/secret','https://secret.invalid/','ip-timezone-bootstrap.js']}});const d=snapshot(h);assert.equal(d.runtimeManifest.version,'other');assert.equal(d.runtimeManifest.id,'other');assert.deepEqual(d.runtimeManifest.scripts,['other','other','ip-timezone-bootstrap.js']);assert.ok(!JSON.stringify(d).includes('secret'));
});
test('same geo host query variants are observable but cannot borrow original exact authorization',async()=>{
 const variant=details({url:SOURCE.replaceAll(',','%2C')});const h=harness({fetch:(u,o,x)=>{x.hooks.onBeforeRequest.emit(variant);return response();}});const value=await h.bootstrap.lookup(lookup());assert.equal(value,null);assert.equal(h.bootstrap.authorization(variant),null);assert.ok(snapshot(h).events.some(x=>x.urlClass==='geo-host-variant'&&!x.exactGeo));assert.equal(h.nativeCalls.length,0);
});
test('browser supplied principal classifications distinguish own/foreign/absent without changing denial',async()=>{
 for(const [origin,wanted] of [['moz-extension://owned-background/bg','own'],['https://foreign.invalid/secret','foreign'],[undefined,'absent'],[17,'invalid']]){
  const h=harness({fetch:(u,o,x)=>{x.hooks.onBeforeRequest.emit(details({originUrl:origin,documentUrl:undefined}));return response();}});const value=await h.bootstrap.lookup(lookup());assert.equal(value!==null,wanted==='own');assert.ok(snapshot(h).events.some(x=>x.stage==='before-request'&&x.origin===wanted));
 }
});
test('raw URL/query/headers/request tokens/error message never enter observer payload',()=>{
 const h=harness(),secret='PRIVATE_KEY_AND_PASSWORD';h.context.PocketIpTimeZoneDiagnostic.record('proxy-event',{url:'https://foreign.invalid/'+secret,method:secret,originUrl:'https://foreign.invalid/'+secret,documentUrl:'https://foreign.invalid/'+secret,requestId:secret,headers:{Authorization:secret}},'none');h.context.PocketIpTimeZoneDiagnostic.record('fetch-rejected',null,'exception',{name:'foreign-'+secret,message:secret});const raw=JSON.stringify(snapshot(h));assert.ok(!raw.includes(secret));assert.ok(!raw.includes(TOKEN));assert.ok(!raw.includes(STAMP));assert.ok(!raw.includes('foreign.invalid'));assert.ok(snapshot(h).events.some(x=>x.errorName==='other'));
});
test('32 row bound and repeated semantic rows remain bounded with truthful omissions',()=>{
 const h=harness();for(let i=0;i<1000;i++)h.context.PocketIpTimeZoneDiagnostic.record('proxy-event',details(),'none');assert.ok(snapshot(h).events.length<10);assert.ok(snapshot(h).omitted>=999);const stages=['create-enter','create-ready','lookup-received','lookup-start','fetch-start','fetch-response','fetch-rejected','deadline','finish-null','finish-observed','before-request','authorization'];for(const stage of stages)for(const originUrl of [undefined,'https://foreign.invalid/','moz-extension://owned-background/'])h.context.PocketIpTimeZoneDiagnostic.record(stage,details({originUrl}),'none');const d=snapshot(h);assert.equal(d.events.length,32);assert.ok(d.omitted>999);assert.deepEqual(d.events.map(x=>x.sequence),Array.from({length:32},(_,i)=>i+1));
});
test('invalid stages/results and nonce drop without exporting arbitrary strings',async()=>{
 const h=harness({full:true});h.context.PocketIpTimeZoneDiagnostic.record('secret-stage',null,'none');h.context.PocketIpTimeZoneDiagnostic.record('proxy-event',null,'secret-result');assert.equal(snapshot(h).invalid,2);assert.equal(h.context.PocketIpTimeZoneDiagnostic.snapshot('wrong'),null);await h.host({kind:'timezoneIpDiagnosticSnapshot',requestNonce:'wrong'});assert.equal(h.nativeCalls.length,0);
});
test('foreign private port and public runtime message cannot request a diagnostic snapshot',async()=>{
 const h=harness({full:true});h.context.foreign={};h.context.command={kind:'timezoneIpDiagnosticSnapshot',requestNonce:nonce};await vm.runInContext('handleHostMessage(command,foreign)',h.context);h.runtimeMessage.emit(h.context.command);await flush();assert.equal(h.nativeCalls.length,0);assert.equal(h.fetches.length,0);
});
test('diagnostic observer exceptions never modify original successful route/header/body',async()=>{
 const h=harness();h.context.PocketIpTimeZoneDiagnostic={record(){throw Error('observer unavailable');}};const value=await h.bootstrap.lookup(lookup());assert.ok(JSON.parse(value).body);assert.equal(h.timers.size,0);
});
test('actual 8000 ms timeout and abort remain unchanged and observable',async()=>{
 const {h,result}=held();h.advance(8000);assert.equal(await result,null);assert.ok(snapshot(h).events.some(x=>x.stage==='deadline'));assert.equal(h.fetches[0].settings.signal.aborted,true);assert.equal(h.timers.size,0);
});
test('actual diagnostic hello replies require a primitive nonce and do not ask the original port',async()=>{
 const manifest={version:'2.1.2.104',browser_specific_settings:{gecko:{id:'browser@pocketchat.local'}},background:{scripts:['ip-timezone-bootstrap.js','request-headers.js','request-identity-background.js','native-timezone-bridge.js','background.js']}};
 const source=fs.readFileSync(path.join(ROOT,'app/src/main/assets/gecko/ip-timezone-bootstrap.js'),'utf8');
 for(const reply of [nonce,{nonce}]){
  const module='browser.runtime.getManifest=()=>('+JSON.stringify(manifest)+');globalThis.__ipConsole=[];console={info(value){__ipConsole.push(value);}};\n'+source;
  const h=harness({module,native:(app,message)=>{assert.equal(app,'pocketipdiagnostic');return Promise.resolve(message.kind==='hello'?reply:null);}});await flush();const calls=h.nativeCalls;assert.ok(calls.some(x=>x.message.kind==='hello'));assert.equal(calls.some(x=>x.message.requestNonce===nonce),typeof reply==='string');assert.equal(h.fetches.length,0);assert.equal(h.timers.size,0);assert.ok(plain(h.context.__ipConsole).every(x=>x.startsWith('POCKET_IP_TZ_DIAG4 ')));
  const raw=await h.bootstrap.lookup(lookup());assert.ok(JSON.parse(raw).body,'Observer cannot admit or deny actual body');await flush();assert.ok(plain(h.context.__ipConsole).length<=32);
 }
});
test('independent hello failure exposes only fixed error-name enum and never raw exception text',async()=>{
 const source=fs.readFileSync(path.join(ROOT,'app/src/main/assets/gecko/ip-timezone-bootstrap.js'),'utf8');
 const module="browser.runtime.getManifest=()=>({version:'2.1.2.104',browser_specific_settings:{gecko:{id:'browser@pocketchat.local'}}});globalThis.__ipConsole=[];console={info(value){__ipConsole.push(value);}};\n"+source;
 const h=harness({module,native:()=>Promise.reject(new Error('PRIVATE_PASSWORD'))});await flush();const d=snapshot(h);assert.ok(d.events.some(x=>x.stage==='hello-send-start'));assert.ok(d.events.some(x=>x.stage==='hello-failed'&&x.errorName==='other'));assert.ok(!JSON.stringify(d).includes('PRIVATE_PASSWORD'));assert.ok(!JSON.stringify(plain(h.context.__ipConsole)).includes('PRIVATE_PASSWORD'));assert.equal(h.timers.size,0);assert.equal(h.fetches.length,0);
});
test('callback entry observes exact kind/current/generation before original stale-host guard',async()=>{
 const h=harness({full:true});await h.host({kind:'timezoneIpDiagnosticSnapshot',requestNonce:nonce});let row=snapshot(h).events.find(x=>x.stage==='port-message-entry'&&x.kindClass==='snapshot');assert.ok(row);assert.equal(row.portCurrent,true);assert.equal(row.generation,1);assert.equal(row.hasKind,true);assert.equal(row.messageType,'object');const before=h.nativeCalls.length;vm.runInContext('host={}',h.context);await h.host(lookup());row=snapshot(h).events.find(x=>x.stage==='port-message-entry'&&x.kindClass==='lookup');assert.ok(row);assert.equal(row.portCurrent,false);assert.equal(h.nativeCalls.length,before);assert.equal(h.fetches.length,0);
});
test('port metadata never exports unknown values or prototype keys and classifies wrapped payload only',()=>{
 const h=harness();for(const kind of ['constructor','__proto__','PRIVATE_PASSWORD'])h.context.PocketIpTimeZoneDiagnostic.portEvent('port-message-entry',{kind,message:{kind:'timezoneIpLookup',secret:'PRIVATE_PASSWORD'},data:'PRIVATE_PASSWORD'},true,3);const rows=snapshot(h).events.filter(x=>x.stage==='port-message-entry');assert.ok(rows.length);for(const row of rows){assert.equal(row.kindClass,'other');assert.equal(row.nestedKindClass,'lookup');assert.equal(row.hasMessage,true);assert.equal(row.hasData,true);}assert.ok(!JSON.stringify(snapshot(h)).includes('PRIVATE_PASSWORD'));
});
