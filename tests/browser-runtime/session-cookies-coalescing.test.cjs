/* Actual production extension in a VM. Cookie/storage boundaries are synthetic;
 * this measures API work and ordering, not Gecko/Android or phone performance.
 * --source <background.js> --measure-only replays the same burst on an old source.
 */
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),crypto=require('node:crypto');
const sourceIndex=process.argv.indexOf('--source');
const source=sourceIndex<0?'app/src/main/assets/gecko/background.js':process.argv[sourceIndex+1];
const code=fs.readFileSync(source,'utf8'),sourceSha256=crypto.createHash('sha256').update(code).digest('hex');
const copy=x=>JSON.parse(JSON.stringify(x)),checks=[],measurements=[],unhandled=[];
let completed=false;
process.once('beforeExit',()=>{if(!completed){console.error('Cookie host checks stopped with an unresolved persistence barrier');process.exitCode=1;}});
process.on('unhandledRejection',error=>unhandled.push(String(error)));
const cookie=(name,extra={})=>({name,value:'synthetic',domain:'example.test',path:'/',session:true,
  secure:true,httpOnly:true,hostOnly:true,sameSite:'lax',storeId:'firefox-default',...extra});
const deferred=()=>{let resolve,reject;const promise=new Promise((yes,no)=>{resolve=yes;reject=no;});return {promise,resolve,reject};};
const microtasks=async(n=12)=>{for(let i=0;i<n;i++)await Promise.resolve();};
function runtime(saved={},initial=[],failName=''){
  let cookies=copy(initial);const storage=copy(saved),sets=[],sent=[],warnings=[],trace=[],gates={read:[],write:[]};let changed,message;
  const counts={reads:0,urlReads:0,writes:0,enumerated:0,serialized:0,active:0,maxActive:0},failures={read:0,write:0};
  const enter=kind=>{counts.active++;counts.maxActive=Math.max(counts.maxActive,counts.active);trace.push(kind+':start');};
  const leave=kind=>{counts.active--;trace.push(kind+':end');};
  const waitGate=async(kind,payload)=>{const gate=gates[kind].shift();if(gate){gate.started.resolve(payload);await gate.resume.promise;}};
  let afterWrite=null;
  const browser={proxy:{onRequest:{addListener(){}}},runtime:{sendNativeMessage:async()=>' {"type":"direct"}',
    connectNative:()=>({onMessage:{addListener(fn){message=fn;}},postMessage(value){sent.push(value);}})},
    storage:{local:{get:async key=>({[key]:copy(storage[key]??null)}),set:async value=>{
      const snapshot=copy(value);counts.writes++;counts.serialized+=snapshot.sessionCookiesV1.length;enter('write');
      try{await waitGate('write',snapshot);if(failures.write>0){failures.write--;throw new Error('synthetic journal failure');}
        Object.assign(storage,snapshot);if(afterWrite){const fn=afterWrite;afterWrite=null;fn();}
      }finally{leave('write');}
    }}},
    cookies:{onChanged:{addListener(fn){changed=fn;}},getAll:async query=>{
      assert.equal(query.storeId,'firefox-default','Every Cookie API read remains scoped to the environment default store');
      const snapshot=copy(cookies.filter(c=>c.storeId===query.storeId));
      if(query.url){counts.urlReads++;return snapshot;}
      counts.reads++;counts.enumerated+=snapshot.length;enter('read');
      try{await waitGate('read',{query:copy(query),snapshot});if(failures.read>0){failures.read--;throw new Error('synthetic Cookie API read failure');}return snapshot;}
      finally{leave('read');}
    },set:async details=>{
      if(details.name===failName)throw new Error('synthetic Cookie API failure');sets.push(copy(details));
      const c=cookie(details.name,{...details,domain:details.domain??new URL(details.url).hostname,hostOnly:!details.domain});
      cookies.push(c);changed({cookie:c,removed:false});return c;
    }}};
  const context=vm.createContext({browser,console:{warn(...args){warnings.push(args.map(String).join(' '));}}});vm.runInContext(code,context);
  return {storage,sets,sent,warnings,trace,counts,ready:()=>vm.runInContext('cookieReady',context),
    prepare:()=>message({kind:'prepare'}),read:()=>message({kind:'cookies',id:1,url:'https://example.test/'}),
    checkpoint:()=>vm.runInContext('checkpoint()',context),flush:()=>vm.runInContext('cookieCommit',context),
    clearNative(){cookies=[];},
    emit(storeId='firefox-default'){changed({cookie:cookie('event',{storeId}),removed:true});},
    replace(list){cookies=copy(list);this.emit();},
    resetCounts(){assert.equal(counts.active,0);for(const key of Object.keys(counts))counts[key]=0;trace.length=0;},
    hold(kind){const gate={started:deferred(),resume:deferred()};gates[kind].push(gate);return gate;},
    failNext(kind){failures[kind]++;},afterWrite(fn){afterWrite=fn;}};
}
function check(name,value){assert.ok(value,name);checks.push({name,pass:true});}
const batch=generation=>Array.from({length:1000},(_,i)=>cookie('synthetic-'+i,{value:'generation-'+generation}));
async function measureBurst(){
  const burst=runtime();await burst.ready();burst.resetCounts();
  for(let i=1;i<=20;i++)burst.replace(batch(i));
  await burst.flush();
  const result={scenario:'20 synchronous change notifications, 1000 synthetic session cookies, drain original or coalesced queue',
    cookieChangeEvents:20,cookiesPerSnapshot:1000,getAllCalls:burst.counts.reads,enumeratedCookies:burst.counts.enumerated,
    journalWrites:burst.counts.writes,serializedSessionCookies:burst.counts.serialized,
    lastJournalGeneration:Number(burst.storage.sessionCookiesV1[0].value.split('-')[1]),maxConcurrentSnapshotWork:burst.counts.maxActive};
  measurements.push(result);return result;
}
(async()=>{
  const burst=await measureBurst();
  if(!process.argv.includes('--measure-only')){
    check('A synchronous 20-event burst reads and writes only the latest 1000-cookie snapshot',burst.getAllCalls===1&&burst.journalWrites===1&&burst.lastJournalGeneration===20&&burst.maxConcurrentSnapshotWork===1);
    const seed=runtime({},[cookie('session'),cookie('persistent',{session:false,expirationDate:1890000000})]);await seed.ready();
    check('Only session cookies enter the private journal',seed.storage.sessionCookiesV1.length===1&&seed.storage.sessionCookiesV1[0].name==='session');
    const restored=runtime(seed.storage);await restored.ready();await restored.prepare();
    const attributes=restored.sets[0];
    check('Native readiness waits for cookie restoration',restored.sent.at(-1).kind==='ready'&&restored.sets.length===1);
    check('Secure HttpOnly SameSite and host-only scope survive',attributes.secure&&attributes.httpOnly&&attributes.sameSite==='lax'&&!Object.hasOwn(attributes,'domain'));
    check('Session cookies do not receive an invented server expiry',!Object.hasOwn(attributes,'expirationDate'));
    restored.replace([]);await restored.flush();
    const logout=runtime(restored.storage);await logout.ready();
    check('Logout deletion cannot return after restart',logout.sets.length===0&&logout.storage.sessionCookiesV1.length===0);
    const cleared=runtime(seed.storage);await cleared.ready();cleared.clearNative();await cleared.read();
    const afterClear=runtime(cleared.storage);await afterClear.ready();
    check('Native bulk clear without cookie events cannot return after a completed read',afterClear.sets.length===0&&cleared.sent.at(-1).kind==='cookies'&&cleared.sent.at(-1).value==='');
    const existing=runtime(seed.storage,[cookie('session',{value:'newer-native-value'})]);await existing.ready();
    check('A newer native cookie is never overwritten by the journal',existing.sets.length===0&&existing.storage.sessionCookiesV1[0].value==='newer-native-value');
    const domain=runtime({sessionCookiesV1:[cookie('domain',{domain:'.example.test',hostOnly:false,sameSite:'strict',firstPartyDomain:'site.test',partitionKey:{topLevelSite:'https://site.test'}})]});await domain.ready();
    check('Domain and partition attributes remain scoped',domain.sets[0].domain==='.example.test'&&domain.sets[0].firstPartyDomain==='site.test'&&domain.sets[0].partitionKey.topLevelSite==='https://site.test');
    const original={sessionCookiesV1:[cookie('first'),cookie('failed')]};const failed=runtime(original,[],'failed');
    await assert.rejects(failed.ready());await failed.prepare();await failed.flush();failed.replace([]);await failed.read();
    check('A partial API failure keeps the complete recovery journal',JSON.stringify(failed.storage)===JSON.stringify(original));
    check('A failed restore never reports the browser ready or allows a native completed read',failed.sent.some(p=>p.kind==='cookieRecoveryError')&&failed.sent.at(-1).error===true&&failed.counts.writes===0);

    const recovering=runtime({sessionCookiesV1:[cookie('recover-a'),cookie('recover-b')]});const recoveryRead=recovering.hold('read');
    let prepared=false;const preparation=recovering.prepare().then(()=>{prepared=true;});await recoveryRead.started.promise;recovering.emit();await microtasks();
    check('Events during held recovery cannot checkpoint a partial store or report native ready',!prepared&&recovering.counts.writes===0&&recovering.sent.length===0);
    recoveryRead.resume.resolve();await preparation;
    check('Native prepare completes only after the full restored journal is checkpointed',prepared&&recovering.sets.length===2&&recovering.storage.sessionCookiesV1.length===2&&recovering.sent.at(-1).kind==='ready');

    const isolated=runtime({sessionCookiesV1:[cookie('foreign',{storeId:'firefox-container-1'}),cookie('persistent',{session:false})]},[cookie('own'),cookie('foreign',{storeId:'firefox-container-1'})]);
    await isolated.ready();isolated.resetCounts();isolated.emit('firefox-container-1');await isolated.flush();
    const other=runtime({},[cookie('other')]);await other.ready();
    check('Non-default-store events and saved cookies cannot enter the default-store journal',isolated.sets.length===0&&isolated.storage.sessionCookiesV1.length===1&&isolated.storage.sessionCookiesV1[0].name==='own'&&isolated.counts.reads===0&&isolated.counts.writes===0);
    isolated.replace([]);await isolated.flush();
    check('Separate environment runtimes never share cookie journal state',other.storage.sessionCookiesV1.length===1&&other.storage.sessionCookiesV1[0].name==='other');

    const readHeld=runtime();await readHeld.ready();readHeld.resetCounts();const reading=readHeld.hold('read');
    readHeld.replace(batch(0));await reading.started.promise;
    for(let i=1;i<=20;i++)readHeld.replace(batch(i));
    const readDrain=readHeld.flush();check('Held getAll keeps snapshot work serial and does not write early',readHeld.counts.reads===1&&readHeld.counts.writes===0&&readHeld.counts.maxActive===1);
    reading.resume.resolve();await readDrain;
    check('Events during held getAll collapse to one fresh read and discard its stale result',readHeld.counts.reads===2&&readHeld.counts.writes===1&&readHeld.storage.sessionCookiesV1[0].value==='generation-20'&&readHeld.counts.maxActive===1);
    measurements.push({scenario:'20 events during held getAll',...copy(readHeld.counts)});

    const writeHeld=runtime();await writeHeld.ready();writeHeld.resetCounts();const writing=writeHeld.hold('write');
    writeHeld.replace(batch(0));await writing.started.promise;
    for(let i=1;i<=20;i++)writeHeld.replace(batch(i));
    const writeDrain=writeHeld.flush();await microtasks();
    check('Held journal write prevents a concurrent read or second write',writeHeld.counts.reads===1&&writeHeld.counts.writes===1&&writeHeld.counts.active===1);
    writing.resume.resolve();await writeDrain;
    check('Events during held set collapse to one latest successor after the first write',writeHeld.counts.reads===2&&writeHeld.counts.writes===2&&writeHeld.storage.sessionCookiesV1[0].value==='generation-20'&&writeHeld.counts.maxActive===1);
    measurements.push({scenario:'20 events during held storage.set',...copy(writeHeld.counts)});

    for(const heldKind of ['read','write']){
      const active=runtime({},[cookie('before-clear')]);await active.ready();active.resetCounts();const gate=active.hold(heldKind);
      active.emit();await gate.started.promise;active.clearNative();let finished=false;const barrier=active.read().then(()=>{finished=true;});await microtasks();
      check('Native bulk-clear barrier waits while old '+heldKind+' is held',!finished&&active.sent.length===0);
      gate.resume.resolve();await barrier;const restart=runtime(active.storage);await restart.ready();
      check('Native bulk clear behind old '+heldKind+' commits an empty fresh snapshot before acknowledgment',finished&&active.storage.sessionCookiesV1.length===0&&restart.sets.length===0&&active.sent.at(-1).value===''&&active.counts.reads===2&&active.counts.maxActive===1);
    }
    const loggingOut=runtime({},[cookie('old-login')]);await loggingOut.ready();loggingOut.resetCounts();const logoutWrite=loggingOut.hold('write');
    loggingOut.emit();await logoutWrite.started.promise;loggingOut.replace([]);const logoutBarrier=loggingOut.flush();logoutWrite.resume.resolve();await logoutBarrier;
    check('An old held write cannot become the final journal after a logout event',loggingOut.storage.sessionCookiesV1.length===0&&loggingOut.counts.reads===2&&loggingOut.counts.writes===2&&loggingOut.counts.maxActive===1);

    for(const failedKind of ['read','write']){
      const broken=runtime({},[cookie('retained')]);await broken.ready();broken.resetCounts();broken.failNext(failedKind);broken.emit();
      await assert.rejects(broken.flush());await microtasks();
      check('Fire-and-forget '+failedKind+' failure is explicitly diagnosed and keeps the last journal',broken.warnings.length===1&&broken.storage.sessionCookiesV1[0].name==='retained');
      broken.clearNative();await broken.read();
      check('Native barrier retries successfully after an event '+failedKind+' failure',broken.sent.at(-1).error!==true&&broken.sent.at(-1).value===''&&broken.storage.sessionCookiesV1.length===0&&broken.counts.maxActive===1);

      const pending=runtime({},[cookie('obsolete')]);await pending.ready();const gate=pending.hold(failedKind);pending.emit();await gate.started.promise;
      pending.failNext(failedKind);pending.clearNative();let done=false;const clear=pending.read().then(()=>{done=true;});await microtasks();gate.resume.resolve();await clear;
      check('A failed old '+failedKind+' still consumes the pending fresh native-clear checkpoint',done&&pending.sent.at(-1).error!==true&&pending.storage.sessionCookiesV1.length===0&&pending.counts.maxActive===1);

      const nativeFailure=runtime({},[cookie('keep-until-confirmed')]);await nativeFailure.ready();nativeFailure.failNext(failedKind);nativeFailure.clearNative();await nativeFailure.read();
      check('Native '+failedKind+' persistence failure reports an error instead of completed clear',nativeFailure.sent.at(-1).error===true&&nativeFailure.storage.sessionCookiesV1[0].name==='keep-until-confirmed');
      await nativeFailure.read();
      check('A rejected native '+failedKind+' barrier does not poison a later successful retry',nativeFailure.sent.at(-1).error!==true&&nativeFailure.storage.sessionCookiesV1.length===0);
    }

    // Place a fresh request on successive microtask turns around the worker tail.
    // This catches active-promise cleanup that runs in a detached .finally().
    for(let depth=0;depth<10;depth++){
      const tail=runtime();await tail.ready();tail.resetCounts();let offered=false;
      tail.afterWrite(()=>{let turn=Promise.resolve();for(let i=0;i<depth;i++)turn=turn.then(()=>{});
        turn.then(()=>{offered=true;tail.replace([cookie('tail-'+depth)]);});});
      tail.replace([cookie('before-tail')]);await tail.flush();await microtasks(20);await tail.flush();
      check('A request at worker-tail microtask offset '+depth+' is consumed',offered&&tail.storage.sessionCookiesV1[0].name==='tail-'+depth&&tail.counts.active===0&&tail.counts.maxActive===1);
    }
    await new Promise(setImmediate);
    check('No event checkpoint creates an unhandled rejection',unhandled.length===0);
  }
  console.log(JSON.stringify({schema:1,source,sourceSha256,passed:checks.length,total:checks.length,
    scope:'Actual production background.js with synthetic host Cookie/storage API boundaries; API cardinality and persistence ordering only',
    actualAndroidExecution:false,realCookieApiExecution:false,realAccountUsed:false,phoneFrameOrCpuMeasurement:false,applicationSpeedupClaim:false,
    checks,measurements,unhandledRejections:unhandled}));
  completed=true;
})().catch(error=>{completed=true;console.error(error);process.exitCode=1;});
