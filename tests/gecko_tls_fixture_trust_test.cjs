'use strict';
// Host fault injection executes the actual privileged integration API. It does
// not pretend that the counterfeit NSS/observer objects are a Gecko execution.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const directory = path.join(__dirname, 'gecko/assets/tls-fixture-trust');
const code = fs.readFileSync(path.join(directory, 'parent.js'), 'utf8');
let checks = 0;
const check = (value, label) => { checks++; assert.ok(value, label); };
const reject = async (task, reason) => { await assert.rejects(task, reason); checks++; };
const base = () => ({sourceCommit:'a'.repeat(40),sourceTree:'b'.repeat(40),runNonce:'c'.repeat(32),
  caseNonce:'d'.repeat(32),bootCaseNonce:'d'.repeat(32),runtimeNonce:'e'.repeat(32),processNonce:'f'.repeat(32),
  challengeNonce:'1'.repeat(32),expectedCaDerSha256:'2'.repeat(64),pid:12345,slot:1});
function fixture(options = {}) {
  const events = new Set(), callbacks = [];
  const state = {enabled:false,user:false,roots:[],reads:0,now:1800000000000};
  const sandbox = {ChromeUtils:{importESModule(url) { return url.includes('ExtensionCommon')
    ? {ExtensionCommon:{ExtensionAPI:class {}}} : {ExtensionUtils:{ExtensionError:Error}}; }},
    Services:{prefs:{getBoolPref(){return state.enabled;},prefHasUserValue(){return state.user;}},
      obs:{addObserver(fn, topic){assert.equal(topic,'psm:enterprise-certs-imported');events.add(fn);},
        removeObserver(fn, topic){assert.equal(topic,'psm:enterprise-certs-imported');events.delete(fn);}}},
    Cc:{'@mozilla.org/psm;1':{getService(){return options.missingApi ? {} : {getEnterpriseRoots(){state.reads++;return state.roots;}};}},
      '@mozilla.org/security/x509certdb;1':{getService(){return {constructX509(der){return {
        sha256Fingerprint:(der[0]===2?'2':'9').repeat(64),validity:{notBefore:(state.now-10000)*1000,notAfter:(state.now+10000)*1000}};}};}}},
    Ci:{nsINSSComponent:{},nsIX509CertDB:{}},Date:{now:()=>state.now}};
  vm.createContext(sandbox);vm.runInContext(code,sandbox,{filename:'actual-tls-fixture-trust-parent.js'});
  const api = new sandbox.pocketFixtureTrust().getAPI({extension:{id:options.id||'tls-fixture-trust@pocketchat.local',isPrivileged:options.privileged!==false},callOnClose(value){callbacks.push(value);}}).pocketFixtureTrust;
  return {api,state,events,emit(topic='psm:enterprise-certs-imported'){for(const fn of [...events])fn(null,topic);},close(){callbacks.forEach(value=>value.close());}};
}
async function complete(f, binding=base(), beforeWait=false) {
  const armed = await f.api.arm(binding);check(armed.observerRegistered && !armed.nativeEffective && f.events.size===1,'listener actually registered before native enable');
  let done=false;const pending=beforeWait?null:f.api.waitImported(binding).then(value=>{done=true;return value;});
  f.state.enabled=true;f.state.roots=[[2,1,3]];
  await Promise.resolve();check(!done&&f.state.reads===0,'root presence and preference true alone cannot ACK');
  f.emit();const actual = await (pending||f.api.waitImported(binding));
  check(actual.importedEventObserved&&actual.importEventCount===1&&actual.rootMatches===1&&actual.caDerSha256===binding.expectedCaDerSha256,'native completion then exact root');
  check(f.events.size===0,'native observer released after original completion');return actual;
}
(async () => {
  const manifest=JSON.parse(fs.readFileSync(path.join(directory,'manifest.json')));
  assert.deepEqual(manifest.permissions,['nativeMessaging','geckoViewAddons']);check(!manifest.content_scripts&&!manifest.host_permissions&&!manifest.externally_connectable,'no page or network permissions');
  for(const file of ['parent.js','background.js'])check(!/\b(fetch|XMLHttpRequest|WebSocket|importCertificates|addCert|setCertTrust|setBoolPref)\b/.test(fs.readFileSync(path.join(directory,file),'utf8')),'no added trust or traffic '+file);
  assert.throws(()=>fixture({id:'browser@pocketchat.local'}),/builtin-only/);checks++;
  assert.throws(()=>fixture({privileged:false}),/builtin-only/);checks++;
  const ordinary=fixture();const original=await complete(ordinary);await reject(()=>ordinary.api.arm(base()),/duplicate-arm/);
  const fresh={...base(),caseNonce:'5'.repeat(32),challengeNonce:'6'.repeat(32)};
  const resample=await ordinary.api.read(fresh);check(resample.importedAtUtcMs===original.importedAtUtcMs&&resample.binding.caseNonce===fresh.caseNonce&&ordinary.events.size===0,'same-runtime fresh read has no new import');
  await reject(()=>ordinary.api.read(fresh),/resample-binding/);
  await reject(()=>ordinary.api.read({...fresh,caseNonce:'7'.repeat(32)}),/resample-binding/);
  for(const key of ['sourceCommit','sourceTree','runNonce','bootCaseNonce','runtimeNonce','processNonce','expectedCaDerSha256','pid','slot']){
    const binding={...base(),caseNonce:'7'.repeat(32),challengeNonce:'8'.repeat(32)};
    binding[key]=key==='pid'?12346:key==='slot'?2:'0'.repeat(binding[key].length);
    await reject(()=>ordinary.api.read(binding),/resample-binding/);
  }
  ordinary.state.roots=[[9,1,3]];await reject(()=>ordinary.api.read({...fresh,caseNonce:'a'.repeat(32),challengeNonce:'b'.repeat(32)}),/exact-root-missing/);
  const early=fixture();await complete(early,base(),true);check(early.events.size===0,'native event before waiter is retained');
  for(const property of ['enabled','user']){const f=fixture();f.state[property]=true;await reject(()=>f.api.arm(base()),/native-pref/);check(f.events.size===0,'unexpected initial preference cannot arm');}
  const missing=fixture({missingApi:true});await reject(()=>missing.api.arm(base()),/native-api/);
  for(const [label,change,pattern] of [
    ['wrong root',f=>{f.state.enabled=true;f.state.roots=[[9,1,3]];},/exact-root-missing/],
    ['no roots',f=>{f.state.enabled=true;},/native-roots/],
    ['duplicate root',f=>{f.state.enabled=true;f.state.roots=[[2],[2]];},/exact-root-missing/],
    ['unexpected USER override',f=>{f.state.enabled=true;f.state.user=true;f.state.roots=[[2]];},/native-pref/],
    ['event without enable',f=>{f.state.roots=[[2]];},/native-pref/]]){
    const f=fixture();await f.api.arm(base());const p=f.api.waitImported(base());change(f);f.emit();await reject(()=>p,pattern);check(f.events.size===0,'failed observer retired '+label);
  }
  const closed=fixture();await closed.api.arm(base());const waiting=closed.api.waitImported(base());closed.close();await reject(()=>waiting,/retired/);closed.emit();check(closed.events.size===0,'destroyed parent cannot receive a late import');await reject(()=>closed.api.read(fresh),/retired/);
  // Execute the original background bridge with a controlled native-event wait.
  const native=[], listeners=[], disconnect=[];let resolve;
  const receipt={binding:base()};const fake={runtime:{connectNative(name){assert.equal(name,'pockettlsfixturetrust');return {postMessage:value=>native.push(value),onMessage:{addListener:fn=>listeners.push(fn)},onDisconnect:{addListener:fn=>disconnect.push(fn)}};}},pocketFixtureTrust:{async arm(){return receipt;},waitImported(){return new Promise(done=>{resolve=done;});},async read(){return receipt;},async close(){}}};
  vm.runInNewContext(fs.readFileSync(path.join(directory,'background.js'),'utf8'),{browser:fake});
  listeners[0]({kind:'arm',binding:base()});await new Promise(done=>setImmediate(done));
  assert.deepEqual(native.map(v=>v.kind),['connected','armed']);checks++;resolve(receipt);await new Promise(done=>setImmediate(done));assert.deepEqual(native.map(v=>v.kind),['connected','armed','ready']);checks++;
  disconnect[0]();listeners[0]({kind:'read',binding:fresh});await new Promise(done=>setImmediate(done));check(native.length===3,'closed native port sends no late ACK');
  console.log(JSON.stringify({status:'passed',checks,actualAndroidExecution:false,actualGeckoExecution:false,
    scope:'Actual integration parent/background code with counterfeit native observer/certificates and private port only'}));
})().catch(error=>{console.error(error);process.exitCode=1;});
