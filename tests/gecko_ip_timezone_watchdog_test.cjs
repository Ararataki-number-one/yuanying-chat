'use strict';

// Execute the actual extension scripts on declared native/browser/timer boundaries.
// No Android, Gecko process, HTTP, timezone application or gate acceptance runs here.
const test=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),crypto=require('node:crypto');
const ROOT=path.resolve(__dirname,'..');
const BOOTSTRAP=path.join(ROOT,'app/src/main/assets/gecko/ip-timezone-bootstrap.js');
const SCRIPT=fs.readFileSync(BOOTSTRAP,'utf8');
const MANIFEST=JSON.parse(fs.readFileSync(path.join(ROOT,'app/src/main/assets/gecko/manifest.json'),'utf8'));
const BASE=path.join(ROOT,'tests/request-identity/ip_timezone_bootstrap_test.cjs');
const original=fs.readFileSync(BASE,'utf8'),boundary=original.indexOf("test('fixed GET");
assert.ok(boundary>0,'Reuse only declared VM boundaries, not existing test executions');
const adapter={require,console,URL,Date,AbortController,TextDecoder,TextEncoder,Uint8Array,__dirname:path.dirname(BASE),module:{exports:{}}};
vm.runInNewContext(original.slice(0,boundary)+'\nmodule.exports={harness,flush};',adapter,{filename:BASE});
const {harness,flush}=adapter.module.exports;
const plain=value=>JSON.parse(JSON.stringify(value));
const NONCE='d'.repeat(32);
const snapshot=h=>plain(h.context.PocketIpTimeZoneDiagnostic.snapshot(NONCE));
const events=(h,stage)=>snapshot(h).events.filter(row=>row.stage===stage);
const prepare=(token=1,generation=1)=>({kind:'prepare',level:1,token,generation,timeoutMs:8000});
function actual(options={}){
  const control={issued:[],failure:null,reply:options.reply};
  const manifest=options.manifest===undefined?MANIFEST:options.manifest;
  const install=options.missingManifest?'':options.manifestThrows
    ?"browser.runtime.getManifest=()=>{throw Error('PRIVATE_MANIFEST_FAILURE');};\n"
    :'browser.runtime.getManifest=()=>('+JSON.stringify(manifest)+');\n';
  const prefix=install+"globalThis.__watchdogLogs=[];console={info(value){__watchdogLogs.push(value);}};\n";
  const h=harness({full:true,module:prefix+(options.script??SCRIPT),native(app,message){
    assert.equal(app,'pocketipdiagnostic','The diagnostic timer must not call a business native host');
    assert.equal(message.diagnosticOnly,true);assert.equal(message.releaseAcceptance,false);
    if(message.kind==='hello'){
      assert.deepEqual(plain(message),{schema:1,kind:'hello',diagnosticOnly:true,releaseAcceptance:false});
      if(control.failure==='sync')throw Object.assign(Error('PRIVATE_WATCHDOG_ERROR'),{name:'TypeError'});
      if(control.failure==='async')return Promise.reject(Object.assign(Error('PRIVATE_WATCHDOG_ERROR'),{name:'UNKNOWN_PRIVATE_NAME'}));
      const nonce=crypto.randomBytes(16).toString('hex');control.issued.push(nonce);
      return Promise.resolve(control.reply===undefined?nonce:control.reply);
    }
    assert.equal(message.requestNonce?.length,32,'Only a native challenge-bound snapshot may follow hello');
    return Promise.resolve(null);
  }});
  return {h,control};
}
async function admitted(value){
  await flush();await value.h.host(prepare());await flush();
  assert.ok(value.h.ports[0].sent.some(row=>row.kind==='protectionReady'&&row.acknowledged===true));
  assert.equal(value.h.ports[0].sent.at(-1).kind,'ready');
  return value;
}
function originalBusiness(h){return plain(h.ports.map(port=>port.sent));}
function noExternalWork(h){
  assert.equal(h.fetches.length,0,'The observer must not run an IP/Geo/HTTP lookup');
  assert.ok(h.nativeCalls.every(row=>row.app==='pocketipdiagnostic'));
}

test('natural owned native prepare-result schedules one timer at exactly 7000ms',async()=>{
  const value=actual();await flush();assert.equal(value.h.timers.size,0,'Script load and connection alone do not start a watchdog');
  await admitted(value);const {h}=value;
  assert.equal(events(h,'native-prepare-result').length,1);assert.equal(events(h,'native-prepare-result')[0].result,'accepted');
  assert.equal(events(h,'watchdog-scheduled').length,1);assert.equal(h.timers.size,1);
  const now=vm.runInContext('Date.now()',h.context);assert.equal([...h.timers.values()][0].at-now,7000);
  const calls=h.nativeCalls.length,business=originalBusiness(h);
  h.advance(6999);await flush();assert.equal(events(h,'watchdog-fired').length,0);assert.equal(h.nativeCalls.length,calls);assert.equal(h.timers.size,1);
  h.advance(1);await flush();assert.equal(events(h,'watchdog-fired').length,1);assert.equal(h.timers.size,0);
  assert.equal(h.nativeCalls.length-calls,2);assert.deepEqual(originalBusiness(h),business);noExternalWork(h);
});

test('watchdog independently negotiates a new primitive 32-hex nonce and exports only its challenge snapshot',async()=>{
  const value=await admitted(actual()),{h,control}=value;
  const prior=control.issued.slice(),calls=h.nativeCalls.length;
  h.advance(7000);await flush();const sent=h.nativeCalls.slice(calls);
  assert.equal(sent.length,2);assert.equal(sent[0].message.kind,'hello');
  assert.match(sent[1].message.requestNonce,/^[0-9a-f]{32}$/);assert.ok(!prior.includes(sent[1].message.requestNonce));
  assert.equal(sent[1].message.requestNonce,control.issued.at(-1));
  assert.equal(sent[1].message.schema,1);assert.equal(sent[1].message.diagnosticOnly,true);assert.equal(sent[1].message.releaseAcceptance,false);
  assert.ok(sent[1].message.events.some(row=>row.stage==='watchdog-fired'));
  assert.ok(!h.ports[0].sent.some(row=>row.kind==='timezoneIpLookup'||row.kind==='timezoneIpDiagnosticSnapshot'));
  noExternalWork(h);
});

test('duplicate prepare, duplicate prepare-result and later result never schedule another diagnostic timer',async()=>{
  const value=await admitted(actual()),{h}=value;
  await h.host(prepare());await flush();await h.host(prepare(2,2));await flush();
  h.context.PocketIpTimeZoneDiagnostic.record('native-prepare-result',null,'accepted');
  assert.equal(events(h,'watchdog-scheduled').length,1);assert.equal(h.timers.size,1);
  h.advance(7000);await flush();assert.equal(events(h,'watchdog-fired').length,1);assert.equal(h.timers.size,0);
  await h.host(prepare(3,3));await flush();
  assert.equal(h.context.PocketIpTimeZoneDiagnostic.watchdog(()=>true,99),false);
  h.advance(14000);await flush();assert.equal(events(h,'watchdog-fired').length,1);assert.equal(h.timers.size,0);noExternalWork(h);
});

test('foreign, missing or unreadable extension identity cannot schedule or send diagnostic messages',async()=>{
  const foreign=plain(MANIFEST);foreign.browser_specific_settings.gecko.id='foreign@private.invalid';
  for(const options of [{manifest:foreign},{manifest:{}},{missingManifest:true},{manifestThrows:true}]){
    const value=actual(options),{h}=value;await flush();await h.host(prepare());await flush();h.advance(10000);await flush();
    assert.equal(events(h,'native-prepare-result').length,1,'Original prepare still reaches its natural result');
    assert.equal(events(h,'watchdog-scheduled').length,0);assert.equal(events(h,'watchdog-fired').length,0);
    assert.equal(h.timers.size,0);assert.equal(h.nativeCalls.length,0);assert.equal(h.ports[0].sent.at(-1).kind,'ready');noExternalWork(h);
  }
});

test('watchdog observes an original rejected prepare without turning it into protection acknowledgement',async()=>{
  const {h}=actual();await flush();await h.host({kind:'prepare',level:99,token:1,generation:1});await flush();
  const result=h.ports[0].sent.find(row=>row.kind==='protectionReady');assert.equal(result.acknowledged,false);assert.equal(result.reason,'invalid-setting-request');
  assert.equal(events(h,'native-prepare-result')[0].result,'rejected');assert.equal(h.timers.size,1);
  const business=originalBusiness(h);h.advance(7000);await flush();assert.deepEqual(originalBusiness(h),business);noExternalWork(h);
});

test('nonprimitive, malformed or noncanonical hello replies cannot produce a watchdog snapshot',async()=>{
  for(const reply of [{nonce:NONCE},new String(NONCE),'D'.repeat(32),'d'.repeat(31),'d'.repeat(33),null,17]){
    const {h}=await admitted(actual({reply})),calls=h.nativeCalls.length,business=originalBusiness(h);
    h.advance(7000);await flush();const later=h.nativeCalls.slice(calls);
    assert.equal(later.length,1);assert.equal(later[0].message.kind,'hello');
    assert.equal(events(h,'watchdog-hello-result')[0].result,'invalid');assert.equal(events(h,'watchdog-snapshot-result').length,0);
    assert.deepEqual(originalBusiness(h),business);noExternalWork(h);
  }
});

test('watchdog failures retain fixed error-name enums without leaking error text or changing business results',async()=>{
  for(const [mode,name] of [['sync','TypeError'],['async','other']]){
    const value=await admitted(actual()),{h,control}=value;control.failure=mode;const business=originalBusiness(h);
    h.advance(7000);await flush();const failed=events(h,'watchdog-hello-failed');assert.equal(failed.length,1);assert.equal(failed[0].errorName,name);
    assert.equal(failed[0].generation,1);assert.equal(failed[0].portCurrent,true);
    assert.ok(!JSON.stringify(snapshot(h)).includes('PRIVATE_WATCHDOG_ERROR'));assert.ok(!JSON.stringify(plain(h.context.__watchdogLogs)).includes('PRIVATE_WATCHDOG_ERROR'));
    assert.ok(!JSON.stringify(snapshot(h)).includes('UNKNOWN_PRIVATE_NAME'));assert.deepEqual(originalBusiness(h),business);noExternalWork(h);
  }
});

test('scheduled watchdog retains the original port generation and truthfully observes later retirement',async()=>{
  const {h}=await admitted(actual());const scheduled=events(h,'watchdog-scheduled')[0];assert.equal(scheduled.generation,1);assert.equal(scheduled.portCurrent,true);
  // Run the actual reconnection function. A later native port is not a new
  // timeout owner; the first scheduled callback still owns its original closure.
  vm.runInContext('connectHost()',h.context);await flush();assert.equal(h.ports.length,2);
  await h.host(prepare(1,2),h.ports[1]);await flush();assert.equal(h.timers.size,1);
  const business=originalBusiness(h);h.advance(7000);await flush();const fired=events(h,'watchdog-fired')[0];
  assert.equal(fired.generation,1);assert.equal(fired.portCurrent,false);assert.equal(events(h,'watchdog-scheduled').length,1);
  assert.ok(snapshot(h).events.some(row=>row.stage==='port-connected'&&row.generation===2));
  assert.ok(snapshot(h).events.some(row=>row.stage==='port-message-entry'&&row.kindClass==='prepare'&&row.generation===2));
  assert.deepEqual(originalBusiness(h),business);noExternalWork(h);
});

test('diagnostic timer leaves the exact original natural prepare business messages unchanged',async()=>{
  const marker='/* Private native IP-timezone bootstrap; no webpage or JavaScript clock changes. */';
  assert.equal(SCRIPT.split(marker).length,2);const businessModule=SCRIPT.slice(SCRIPT.indexOf(marker));
  const observed=await admitted(actual()),baseline=await admitted(actual({script:businessModule}));
  assert.deepEqual(originalBusiness(observed.h),originalBusiness(baseline.h));assert.equal(baseline.h.timers.size,0);
  const before=originalBusiness(observed.h);observed.h.advance(7000);baseline.h.advance(7000);await flush();
  assert.deepEqual(originalBusiness(observed.h),before);assert.deepEqual(originalBusiness(observed.h),originalBusiness(baseline.h));
  noExternalWork(observed.h);assert.equal(baseline.h.fetches.length,0);assert.equal(baseline.h.nativeCalls.length,0);
});

test('a full32 diagnostic ring cannot suppress the one natural seven-second watchdog; omitted events remain explicit',async()=>{
  const {h}=actual();await flush();
  // Valid bounded observations only. These calls do not create requests, touch
  // native preparation or borrow its admission; all fetch/native edges remain
  // the same declared VM adapters as the ordinary cases above.
  for(const stage of ['proxy-event','proxy-authorization','header-event','header-authorization','header-listener','authorization','before-request','before-redirect']){
    for(const originUrl of [undefined,'https://unrelated.example/','moz-extension://owned-background/observe']){
      for(const result of ['none','ready'])h.context.PocketIpTimeZoneDiagnostic.record(stage,{url:'https://ipwho.is/?fields=success,ip,timezone.id',method:'GET',originUrl,requestId:'bounded-cap-observation'},result);
    }
  }
  await flush();const full=snapshot(h);assert.equal(full.events.length,32);assert.ok(full.omitted>0);assert.equal(h.timers.size,0);
  await h.host(prepare());await flush();const prepared=snapshot(h);
  assert.deepEqual(prepared.events,full.events);assert.ok(prepared.omitted>full.omitted);
  assert.equal(h.ports[0].sent.at(-1).kind,'ready');assert.ok(h.ports[0].sent.some(row=>row.kind==='protectionReady'&&row.acknowledged===true));
  assert.equal(h.timers.size,1);assert.equal([...h.timers.values()][0].at-vm.runInContext('Date.now()',h.context),7000);
  await h.host(prepare());await flush();assert.equal(h.timers.size,1,'Duplicate prepare cannot create a second timer after the ring fills');
  const calls=h.nativeCalls.length,business=originalBusiness(h),beforeTick=snapshot(h).omitted;
  h.advance(6999);await flush();assert.equal(h.nativeCalls.length,calls);assert.equal(h.timers.size,1);
  h.advance(1);await flush();assert.equal(h.timers.size,0);const sent=h.nativeCalls.slice(calls);
  assert.equal(sent.length,2);assert.equal(sent[0].message.kind,'hello');assert.match(sent[1].message.requestNonce,/^[0-9a-f]{32}$/);
  assert.equal(sent[1].message.events.length,32);assert.ok(sent[1].message.omitted>beforeTick);
  // Capacity intentionally omits watchdog rows. The fresh native handshake and
  // exact timer boundary establish execution here; absence of a row is never
  // advertised as proof that the watchdog did not fire.
  assert.ok(!sent[1].message.events.some(row=>row.stage.startsWith('watchdog-')));
  assert.deepEqual(snapshot(h).events,full.events);assert.ok(snapshot(h).omitted>beforeTick);
  assert.deepEqual(originalBusiness(h),business);noExternalWork(h);
  await h.host(prepare(2,2));await flush();h.advance(14000);await flush();
  assert.equal(h.timers.size,0);assert.equal(h.nativeCalls.length,calls+2);assert.equal(snapshot(h).events.length,32);noExternalWork(h);
});

test('natural prepare snapshots retain unique contiguous sequences and pass the real strict Python extension parser',async()=>{
  const {h}=await admitted(actual());
  const prepared=snapshot(h);assert.deepEqual(prepared.events.map(row=>row.sequence),Array.from({length:prepared.events.length},(_,index)=>index+1));
  const armed=prepared.events.findIndex(row=>row.stage==='watchdog-scheduled'),completed=prepared.events.findIndex(row=>row.stage==='native-prepare-result');
  assert.ok(armed>=0&&completed>armed,'Recursive scheduled observation must precede construction of the prepare-result row');
  h.advance(7000);await flush();const observed=snapshot(h);
  assert.deepEqual(observed.events.map(row=>row.sequence),Array.from({length:observed.events.length},(_,index)=>index+1));
  assert.ok(observed.events.some(row=>row.stage==='watchdog-fired'));noExternalWork(h);
  // Registered/counter fields below are declared parser-envelope boundaries,
  // not a claim of Android registration. The latest payload is the untouched
  // actual extension snapshot; the Python verifier and its predicates are real.
  const python=String.raw`import copy,importlib.util,json,pathlib,sys
root=pathlib.Path(sys.argv[1]);sys.path.insert(0,str(root/'tools/browser'))
file=root/'tools/browser/run_gecko_ip_timezone_integration.py'
spec=importlib.util.spec_from_file_location('actual_watchdog_extension_verifier',file)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
latest=json.load(sys.stdin);envelope=dict(registered=True,accepted=1,rejected=0,latest=latest)
original=copy.deepcopy(envelope)
assert module.extension_debug(envelope,'d'*32) is envelope and envelope==original
counterfeit=copy.deepcopy(envelope);counterfeit['latest']['events'][1]['sequence']=counterfeit['latest']['events'][0]['sequence']
refused=False
try:module.extension_debug(counterfeit,'d'*32)
except ValueError:refused=True
assert refused,'The real parser must still reject a duplicate observer sequence'
print(json.dumps(dict(status='passed',acceptedEvents=len(latest['events']),duplicateSequenceRejected=refused,actualAndroidExecution=False)))`;
  const result=JSON.parse(require('node:child_process').execFileSync('python3',['-c',python,ROOT],{input:JSON.stringify(observed),encoding:'utf8',timeout:20000,env:{...process.env,PYTHONDONTWRITEBYTECODE:'1'}}));
  assert.equal(result.status,'passed');assert.equal(result.acceptedEvents,observed.events.length);
  assert.equal(result.duplicateSequenceRejected,true);assert.equal(result.actualAndroidExecution,false);
});
