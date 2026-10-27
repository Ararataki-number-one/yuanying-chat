/* Full production background module; setting/Cookie/native-port boundaries are synthetic. */
'use strict';
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict'),crypto=require('node:crypto');
const root=path.resolve(__dirname,'../..'),asset=path.join(root,'app/src/main/assets/gecko/background.js'),code=fs.readFileSync(asset,'utf8');
const checks=[];let completed=false;
process.once('beforeExit',()=>{if(!completed){console.error('Native protection host controls did not complete');process.exitCode=1;}});
const copy=x=>JSON.parse(JSON.stringify(x));
const deferred=()=>{let resolve,reject;const promise=new Promise((yes,no)=>{resolve=yes;reject=no;});return {promise,resolve,reject};};
const flush=async()=>{for(let i=0;i<30;i++)await Promise.resolve();};
const check=(name,value)=>{assert.ok(value,name);checks.push({name,pass:true});};
function runtime(options={}){
  const state={value:false,now:0,active:0,maxActive:0,connects:0,clearCount:0};
  const ports=[],timers=[],trace=[],sets=[],reads=[];let changed,failConnect=false;
  const control={
    async set({value}){sets.push(value);trace.push('set-start:'+value);state.maxActive=Math.max(state.maxActive,++state.active);
      try{if(options.set)await options.set(value,state);state.value=value;trace.push('set-end:'+value);}finally{state.active--;}
    },
    async get(){reads.push(state.value);trace.push('get-start:'+state.value);state.maxActive=Math.max(state.maxActive,++state.active);
      try{if(options.get)return await options.get(state);return {value:state.value};}finally{trace.push('get-end:'+state.value);state.active--;}
    },onChange:{addListener(fn){changed=fn;}}
  };
  const browser={proxy:{onRequest:{addListener(){}}},runtime:{sendNativeMessage:async()=>'{"type":"socks","host":"127.0.0.1","port":9}',
    connectNative(){state.connects++;if(failConnect)throw new Error('synthetic connect failure');
      const port={sent:[],closed:false,onMessage:{addListener(fn){port.message=fn;}},onDisconnect:{addListener(fn){port.disconnected=fn;}},postMessage(value){if(port.closed)throw new Error('closed');trace.push('message:'+value.kind+':'+value.token+':'+value.acknowledged);port.sent.push(copy(value));}};
      ports.push(port);return port;
    }},
    cookies:{onChanged:{addListener(){}},getAll:async()=>{if(options.cookies)await options.cookies();return [];},set:async()=>{}},
    storage:{local:{get:async()=>({}),set:async()=>{}}}
  };
  if(!options.missing)browser.privacy={websites:{resistFingerprinting:control}};
  const scope=options.scope??{handle:cfg=>({ok:true,nonce:cfg.nonce}),clear(){state.clearCount++;}};
  const context=vm.createContext({browser,console,Date:class extends Date{static now(){return state.now;}},
    PocketRequestIdentityBackground:options.noScope?undefined:scope,
    setTimeout(fn,delay){const timer={fn,at:state.now+delay};timers.push(timer);return timer;},clearTimeout(timer){const index=timers.indexOf(timer);if(index>=0)timers.splice(index,1);}});
  vm.runInContext(code,context,{filename:'production-background.js'});
  return {state,ports,timers,trace,sets,reads,ready:()=>vm.runInContext('cookieReady',context),
    current:()=>ports.at(-1),send(message,port=ports.at(-1)){return port.message(message);},
    protect(level,token,generation,kind='protection',port=ports.at(-1)){return this.send({kind,level,token,generation,timeoutMs:8000},port);},
    change(value){changed?.(value);},disconnect(port=ports.at(-1)){port.closed=true;port.disconnected();},
    failConnections(){failConnect=true;},
    async advance(delta){const end=state.now+delta;for(;;){timers.sort((a,b)=>a.at-b.at);const timer=timers[0];if(!timer||timer.at>end)break;timers.shift();state.now=timer.at;timer.fn();await flush();}state.now=end;await flush();},
    replies(port=ports.at(-1)){return port.sent.filter(x=>x.kind==='protectionReady');}
  };
}
async function main(){
  const normal=runtime();await normal.ready();await normal.protect(2,1,1,'prepare');
  check('Prepare preserves separate cookie and RFP barriers',normal.current().sent.map(x=>x.kind).join(',')==='cookiePrepared,protectionReady,ready');
  check('Strong acknowledgment carries the exact token and generation',normal.replies()[0].level===2&&normal.replies()[0].token===1&&normal.replies()[0].generation===1&&normal.replies()[0].acknowledged===true&&normal.replies()[0].fingerprinting===true);
  check('Strong API applies and reads the actual desired value',normal.sets.join(',')==='true'&&normal.reads.join(',')==='true'&&normal.state.value===true);
  await normal.protect(1,2,2);check('A user-selected standard request confirms a real false readback',normal.replies().at(-1).acknowledged===true&&normal.replies().at(-1).fingerprinting===false&&normal.state.value===false);
  const missing=runtime({missing:true});await missing.ready();await missing.protect(2,1,1);
  check('Missing setting API returns an explicit failure',missing.replies()[0].acknowledged===false&&missing.replies()[0].reason==='setting-unavailable');
  const failed=runtime({set:async()=>{throw new Error('synthetic private error details');}});await failed.ready();await failed.protect(2,1,1);
  check('Native-setting exception is contained and redacted',failed.replies()[0].acknowledged===false&&failed.replies()[0].reason==='setting-error'&&!JSON.stringify(failed.replies()).includes('private error'));
  const badRead=runtime({get:async()=>({value:false})});await badRead.ready();await badRead.protect(2,1,1);
  check('Set completion without a matching readback cannot confirm',badRead.replies()[0].acknowledged===false&&badRead.replies()[0].reason==='setting-mismatch');
  const badType=runtime({get:async()=>({value:'true'})});await badType.ready();await badType.protect(2,1,1);
  check('String-valued readback cannot be coerced into confirmation',badType.replies()[0].acknowledged===false&&badType.replies()[0].fingerprinting===false);

  const cookieGate=deferred();let cookieHeld=true;const cookies=runtime({cookies:async()=>{if(cookieHeld)await cookieGate.promise;}});
  const preparing=cookies.protect(2,1,1,'prepare');await flush();check('No Cookie readiness or setting acknowledgment escapes held recovery',cookies.current().sent.length===0&&cookies.sets.length===0);
  cookieHeld=false;cookieGate.resolve();await preparing;check('Full cookie restoration precedes the early cookie barrier',cookies.current().sent[0].kind==='cookiePrepared'&&cookies.replies()[0].acknowledged===true);

  for(const [oldLevel,newLevel,label] of [[1,2,'standard to strong'],[2,1,'strong to standard']]){
    const delayedCookies=deferred();let held=true;
    const transition=runtime({cookies:async()=>{if(held)await delayedCookies.promise;}});
    const delayedPrepare=transition.protect(oldLevel,1,1,'prepare');await flush();await transition.protect(newLevel,2,2);
    check('New '+label+' setting can confirm while the old Cookie prepare is still pending',transition.replies().some(x=>x.token===2&&x.acknowledged)&&transition.current().sent.every(x=>x.kind!=='cookiePrepared'));
    held=false;delayedCookies.resolve();await delayedPrepare;
    check('Late Cookie prepare cannot overwrite the newer '+label+' confirmation',transition.sets.length===1&&transition.sets[0]===(newLevel>=2)&&transition.state.value===(newLevel>=2)&&transition.replies().filter(x=>x.acknowledged).every(x=>x.token===2));
  }
  const replay=runtime();await replay.ready();await replay.protect(2,8,8);await replay.protect(1,7,7);
  check('Replayed lower counters cannot enqueue a stale mode after confirmation',replay.sets.join(',')==='true'&&replay.state.value===true&&replay.replies().at(-1).reason==='superseded');
  replay.change({value:false});check('A rejected stale request cannot detach the current change observer',replay.current().sent.at(-1).kind==='protectionChanged'&&replay.current().sent.at(-1).token===8);
  for(const field of ['level','token','generation']){
    const malformed=runtime();await malformed.ready();const request={kind:'protection',level:2,token:1,generation:1};request[field]=String(request[field]);await malformed.send(request);
    check('Malformed string '+field+' is rejected before any setting side effect',malformed.sets.length===0&&malformed.replies()[0].reason==='invalid-setting-request');
  }
  const nullLevel=runtime();await nullLevel.ready();await nullLevel.send({kind:'protection',level:null,token:1,generation:1});
  check('Missing or null mode cannot silently choose a standard setting',nullLevel.sets.length===0&&nullLevel.replies()[0].reason==='invalid-setting-request');

  const lateGate=deferred();let holdOld=true;const late=runtime({set:async value=>{if(value===false&&holdOld){holdOld=false;await lateGate.promise;}}});await late.ready();
  const old=late.protect(1,1,1);await flush();late.state.now=8100;
  const superseded=late.protect(2,2,2),current=late.protect(2,3,2);await flush();
  check('A timed-out old set holds the API lock until it really settles',late.sets.join(',')==='false'&&late.state.active===1);
  check('Only the latest queued request is retained',late.replies().some(x=>x.token===2&&x.reason==='superseded')&&!late.sets.includes(true));
  lateGate.resolve();await Promise.all([old,superseded,current]);
  check('Late old disable settles before the new enable starts',late.trace.indexOf('set-end:false')<late.trace.indexOf('set-start:true'));
  check('Late old work can never report successful current confirmation',late.replies().find(x=>x.token===1).acknowledged===false&&late.replies().find(x=>x.token===3).acknowledged===true);
  check('A newer confirmed setting cannot be overwritten by an older set',late.state.value===true&&late.sets.join(',')==='false,true'&&late.state.maxActive===1);

  const readGate=deferred();let firstRead=true;const readLate=runtime({get:async state=>{if(firstRead){firstRead=false;await readGate.promise;}return {value:state.value};}});await readLate.ready();
  const oldRead=readLate.protect(2,1,1);await flush();readLate.state.now=8100;const standard=readLate.protect(1,2,2);await flush();
  check('A hanging get also retains the serial lock',readLate.sets.join(',')==='true'&&readLate.state.active===1);
  readGate.resolve();await Promise.all([oldRead,standard]);check('Late old get cannot confirm a different user-selected mode',readLate.replies().find(x=>x.token===1).acknowledged===false&&readLate.replies().find(x=>x.token===2).acknowledged===true&&readLate.state.value===false&&readLate.state.maxActive===1);

  let failures=1;const retry=runtime({set:async()=>{if(failures-->0)throw new Error('synthetic failure');}});await retry.ready();await retry.protect(2,1,4);await retry.protect(2,2,4);
  check('A same-level retry can recover after an actual API failure',retry.replies()[0].acknowledged===false&&retry.replies()[1].acknowledged===true&&retry.replies()[1].generation===4);
  const expiringGate=deferred();let hold=true;const expired=runtime({set:async()=>{if(hold){hold=false;await expiringGate.promise;}}});await expired.ready();const oldExpired=expired.protect(1,1,1);await flush();const waiting=expired.protect(2,2,2);expired.state.now=9000;expiringGate.resolve();await Promise.all([oldExpired,waiting]);
  check('An expired queued request never performs a late unowned set',expired.sets.length===1&&expired.replies().find(x=>x.token===2).reason==='setting-timeout'&&!expired.replies().find(x=>x.token===2).acknowledged);

  const busyGate=deferred();let initial=true;const busy=runtime({set:async()=>{if(initial){initial=false;await busyGate.promise;}}});await busy.ready();const firstBusy=busy.protect(1,1,1);await flush();const pending=[];
  for(let token=2;token<=51;token++)pending.push(busy.protect(2,token,2));await flush();check('Fifty superseding requests cause no concurrent or growing API work',busy.sets.length===1&&busy.replies().length===49);
  busyGate.resolve();await Promise.all([firstBusy,...pending]);check('A superseding burst executes only the latest native setting',busy.sets.join(',')==='false,true'&&busy.replies().find(x=>x.token===51).acknowledged&&busy.state.maxActive===1);

  const observer=runtime();await observer.ready();await observer.protect(2,7,8);const before=observer.current().sent.length;observer.change({value:true});observer.change({});
  check('Matching or malformed setting events cannot create a new acknowledgment',observer.current().sent.length===before);
  observer.change({value:false});const invalidation=observer.current().sent.at(-1);
  check('An actual setting change invalidates only the current confirmed token',invalidation.kind==='protectionChanged'&&invalidation.token===7&&invalidation.generation===8&&invalidation.level===2);
  check('A setting-change event never directly retries or confirms',observer.sets.length===1&&observer.replies().length===1);

  const reconnectGate=deferred();let oldHeld=true;const reconnect=runtime({set:async()=>{if(oldHeld){oldHeld=false;await reconnectGate.promise;}}});await reconnect.ready();const oldPort=reconnect.current();const oldWork=reconnect.protect(1,1,1);await flush();reconnect.disconnect(oldPort);
  check('Disconnect clears the temporary request-identity registration',reconnect.state.clearCount===1);
  await reconnect.advance(499);check('Bridge reconnection respects a finite backoff',reconnect.state.connects===1);await reconnect.advance(1);const newPort=reconnect.current();const newWork=reconnect.protect(2,2,2,'prepare',newPort);await flush();
  reconnectGate.resolve();await Promise.all([oldWork,newWork]);check('Old port callbacks are never posted to the replacement host',newPort!==oldPort&&newPort.sent.filter(x=>x.kind==='protectionReady').every(x=>x.token===2&&x.generation===2));
  check('Replacement host confirms only after older setting work settles',reconnect.state.value===true&&reconnect.state.maxActive===1&&reconnect.replies(newPort)[0].acknowledged===true);
  oldPort.disconnected();check('A late old disconnect cannot clear the new host scope',reconnect.state.clearCount===1&&reconnect.timers.length===0);
  reconnect.disconnect(newPort);await reconnect.advance(500);check('A confirmed connection starts a fresh bounded recovery after a later failure',reconnect.state.connects===3);

  const bounded=runtime();await bounded.ready();bounded.failConnections();bounded.disconnect();await bounded.advance(3500);
  check('A broken native host is retried at most three times',bounded.state.connects===4&&bounded.timers.length===0);
  const cleanupFails=runtime({scope:{handle:()=>({ok:true}),clear(){throw new Error('synthetic cleanup failure');}}});await cleanupFails.ready();cleanupFails.disconnect();await cleanupFails.advance(500);
  check('Scope cleanup failure cannot prevent bounded native reconnect',cleanupFails.state.connects===2);
  const scope=runtime();await scope.ready();await scope.send({kind:'requestIdentityScope',id:9,configuration:{nonce:'controlled-nonce'}});
  const scopeReply=scope.current().sent.at(-1);check('Identity scope IPC retains its request id and explicit helper result',scopeReply.kind==='requestIdentityScopeResult'&&scopeReply.id===9&&JSON.parse(scopeReply.result).nonce==='controlled-nonce');
  const noScope=runtime({noScope:true});await noScope.ready();await noScope.send({kind:'requestIdentityScope',id:10,configuration:{}});check('Missing identity-scope helper is an explicit failure',JSON.parse(noScope.current().sent.at(-1).result).error==='scope-helper-unavailable');
  const scopeGate=deferred(),asyncScope=runtime({scope:{handle:()=>scopeGate.promise,clear(){}}});await asyncScope.ready();
  const scoped=asyncScope.send({kind:'requestIdentityScope',id:11,configuration:{action:'evidence'}});await flush();check('Asynchronous evidence IPC is not serialized as an empty Promise object',asyncScope.current().sent.length===0);
  scopeGate.resolve({ok:true,nonce:'async-controlled-nonce'});await scoped;check('Asynchronous evidence returns the actual resolved result',JSON.parse(asyncScope.current().sent.at(-1).result).nonce==='async-controlled-nonce');

  // Synthetic event ordering only: these controls do not establish that Gecko
  // emits this order or that another setting writer is reachable on a phone.
  const snapshotGate=deferred(),snapshotReceived=deferred();let firstSnapshot=true;
  const changedDuringRead=runtime({get:async state=>{
    if(!firstSnapshot)return {value:state.value};
    firstSnapshot=false;const snapshot={value:state.value};snapshotReceived.resolve(snapshot);await snapshotGate.promise;return snapshot;
  }});await changedDuringRead.ready();const changedTask=changedDuringRead.protect(2,19,20);await snapshotReceived.promise;
  changedDuringRead.state.value=false;changedDuringRead.change({value:false});snapshotGate.resolve();await changedTask;
  check('A setting event while a true snapshot awaits confirmation forces a new read',changedDuringRead.reads.join(',')==='true,false');
  check('A stable disabled reread rejects the old successful strong snapshot',changedDuringRead.replies()[0].acknowledged===false&&changedDuringRead.replies()[0].fingerprinting===false&&changedDuringRead.replies()[0].reason==='setting-mismatch');
  check('Conflicting readback never rewrites the setting and retains the exact request identity',changedDuringRead.sets.join(',')==='true'&&changedDuringRead.state.value===false&&changedDuringRead.state.maxActive===1&&changedDuringRead.replies()[0].token===19&&changedDuringRead.replies()[0].generation===20);

  const standardGate=deferred(),standardReceived=deferred();let firstStandard=true;
  const changedStandard=runtime({get:async state=>{
    if(!firstStandard)return {value:state.value};
    firstStandard=false;const snapshot={value:state.value};standardReceived.resolve(snapshot);await standardGate.promise;return snapshot;
  }});await changedStandard.ready();const standardTask=changedStandard.protect(1,21,22);await standardReceived.promise;
  changedStandard.state.value=true;changedStandard.change({value:true});standardGate.resolve();await standardTask;
  check('A pending standard request also rejects a stale disabled snapshot after an enable event',changedStandard.reads.join(',')==='false,true'&&changedStandard.replies()[0].acknowledged===false&&changedStandard.replies()[0].fingerprinting===true&&changedStandard.replies()[0].reason==='setting-mismatch');

  let firstMatching=true;const matchingDuringRead=runtime({get:async state=>{if(firstMatching){firstMatching=false;matchingDuringRead.change({value:state.value});}return {value:state.value};}});
  await matchingDuringRead.ready();await matchingDuringRead.protect(2,1,1);
  check('An own matching event during get can confirm after one stable reread',matchingDuringRead.reads.join(',')==='true,true'&&matchingDuringRead.replies()[0].acknowledged===true&&matchingDuringRead.sets.length===1&&matchingDuringRead.state.maxActive===1);
  const ownSetEvent=runtime({set:async value=>ownSetEvent.change({value})});await ownSetEvent.ready();await ownSetEvent.protect(2,1,1);
  check('An own set event before get does not trigger unnecessary repeated reads',ownSetEvent.reads.join(',')==='true'&&ownSetEvent.replies()[0].acknowledged===true);

  let keepChanging=true;const unstable=runtime({get:async state=>{const snapshot={value:state.value};if(keepChanging){state.value=!state.value;unstable.change({value:state.value});}return snapshot;}});
  await unstable.ready();await unstable.protect(2,1,1);
  check('Repeated changes have exactly three bounded readbacks and no successful acknowledgment',unstable.reads.length===3&&unstable.replies().length===1&&unstable.replies()[0].acknowledged===false&&unstable.replies()[0].fingerprinting===false&&unstable.replies()[0].reason==='setting-changed-during-confirmation');
  check('Change conflicts keep one actual write and never create event-driven retry work',unstable.sets.length===1&&unstable.state.maxActive===1&&unstable.timers.length===0);
  keepChanging=false;await unstable.protect(2,2,1);
  check('A later explicit request can confirm after changes stop',unstable.sets.join(',')==='true,true'&&unstable.reads.length===4&&unstable.replies().at(-1).acknowledged===true&&unstable.replies().at(-1).token===2&&unstable.replies().at(-1).generation===1);

  const malformedDuringRead=runtime({get:async state=>{malformedDuringRead.change({value:'false'});return {value:state.value};}});
  await malformedDuringRead.ready();await malformedDuringRead.protect(2,1,1);
  check('Malformed change payloads cannot create false conflicts or new acknowledgments',malformedDuringRead.reads.length===1&&malformedDuringRead.replies().length===1&&malformedDuringRead.replies()[0].acknowledged===true);

  const deadlineDuringRead=runtime({get:async state=>{const snapshot={value:state.value};state.now=8100;state.value=false;deadlineDuringRead.change({value:false});return snapshot;}});
  await deadlineDuringRead.ready();await deadlineDuringRead.protect(2,1,1);
  check('A conflicting snapshot after the original deadline never starts another get',deadlineDuringRead.reads.length===1&&deadlineDuringRead.sets.length===1);
  check('Readback conflict cannot extend the original setting deadline',deadlineDuringRead.replies()[0].acknowledged===false&&deadlineDuringRead.replies()[0].reason==='setting-timeout');

  const supersedingGate=deferred(),supersedingReceived=deferred();let firstSuperseding=true;
  const supersedingRead=runtime({get:async state=>{if(!firstSuperseding)return {value:state.value};firstSuperseding=false;const snapshot={value:state.value};supersedingReceived.resolve(snapshot);await supersedingGate.promise;return snapshot;}});
  await supersedingRead.ready();const oldSnapshotTask=supersedingRead.protect(2,1,1);await supersedingReceived.promise;
  supersedingRead.state.value=false;supersedingRead.change({value:false});const newerSnapshotTask=supersedingRead.protect(1,2,2);await flush();supersedingGate.resolve();await Promise.all([oldSnapshotTask,newerSnapshotTask]);
  check('A superseded read conflict cannot consume another old readback or confirm',supersedingRead.reads.length===2&&supersedingRead.replies().find(x=>x.token===1).acknowledged===false&&supersedingRead.replies().find(x=>x.token===1).reason==='setting-timeout');
  check('The latest mode retains serial API ownership after an older read conflict',supersedingRead.sets.join(',')==='true,false'&&supersedingRead.state.maxActive===1&&supersedingRead.state.value===false&&supersedingRead.replies().find(x=>x.token===2).acknowledged===true);

  assert.equal(crypto.createHash('sha256').update(fs.readFileSync(asset)).digest('hex'),crypto.createHash('sha256').update(code).digest('hex'),'Production source changed during controls');
  const snapshot=run=>({sets:run.sets,readStarts:run.reads,replies:run.replies(),currentValue:run.state.value,maxConcurrentApiCalls:run.state.maxActive,trace:run.trace});
  const changeOrderControls={scope:'Synthetic Promise/onChange order only; real Gecko order and other reachable setting writers remain unverified',oldTrueSnapshot:snapshot(changedDuringRead),oldFalseSnapshot:snapshot(changedStandard),ownMatchingEvent:snapshot(matchingDuringRead),boundedConflictsThenExplicitRetry:snapshot(unstable),originalDeadline:snapshot(deadlineDuringRead),supersededSnapshot:snapshot(supersedingRead)};
  const report={schema:1,status:'passed',passed:checks.length,checks,changeOrderControls,scope:'Complete production extension with synthetic native port, setting API, Cookie API and monotonic test scheduling boundaries; no Android, real privacy API, or network attestation',actualAndroidExecution:false,actualGeckoExecution:false,realSettingApiExecution:false,fullFingerprintProtectionAccepted:false,sourceSha256:crypto.createHash('sha256').update(code).digest('hex')};
  if(process.argv[2]==='--receipt'){assert.equal(process.argv.length,4);fs.mkdirSync(path.dirname(process.argv[3]),{recursive:true});fs.writeFileSync(process.argv[3],JSON.stringify(report,null,2)+'\n');}
  console.log(JSON.stringify({status:report.status,passed:report.passed,actualAndroidExecution:false}));completed=true;
}
main().catch(error=>{console.error(error);process.exitCode=1;});
