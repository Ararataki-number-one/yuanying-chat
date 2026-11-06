'use strict';

// Execute the complete current collector with explicit DOM/network boundaries.
// Date/Intl are real Node builtins under a process-only TZ, not Android proof.
const test=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const SOURCE=fs.readFileSync(path.join(__dirname,'../gecko/assets/gecko-cpu-ip-combo-page.js'),'utf8');
const FIXTURE={runNonce:'a'.repeat(32),sourceCommit:'b'.repeat(40),origins:['https://fp-a.pocketchat.test','https://fp-b.pocketchat.test']};
const plain=value=>JSON.parse(JSON.stringify(value));
const flush=async()=>{for(let n=0;n<12;n++)await Promise.resolve();};
function harness(options={}){
  const attributes=new Map(),timers=new Map(),requests=[];let sequence=0,resolve,reject;
  const response=new Promise((yes,no)=>{resolve=yes;reject=no;});
  const native=new Map(Array.from({length:options.cpu??1},(_,i)=>[i,i]));
  const nativeGetter=Object.getOwnPropertyDescriptor(Map.prototype,'size').get;
  Object.defineProperty(native,'hardwareConcurrency',{get:options.customGetter?function(){return 1;}:nativeGetter});
  const script={},document={currentScript:script,scripts:options.notFirst?[{},script]:[script],readyState:options.readyState??'loading',documentElement:{setAttribute(name,value){attributes.set(name,value);}}};
  const context={navigator:native,document,URL,URLSearchParams,Date,Intl,TextEncoder,crypto:{randomUUID:()=> '11111111-1111-4111-8111-111111111111'},
    location:{origin:FIXTURE.origins[0],href:FIXTURE.origins[0]+'/env-policy?phase=gecko-new-york'},isSecureContext:true,
    setTimeout(callback,delay){const id=++sequence;timers.set(id,{callback,delay});return id;},clearTimeout(id){timers.delete(id);},
    fetch(url,settings){requests.push({url,settings:plain(settings),before:attributes.get('data-gecko-cpu-ip-combo')});return response;}};
  context.window=context;if(options.frame)context.parent={};else context.parent=context;
  const previous=process.env.TZ;process.env.TZ=options.zone??'America/New_York';
  try{vm.runInNewContext((options.source??SOURCE).replace('__WORKER_POLICY_FIXTURE__',JSON.stringify(FIXTURE)),context,{filename:'actual-gecko-cpu-ip-combo-page.js'});}
  finally{if(previous===undefined)delete process.env.TZ;else process.env.TZ=previous;}
  return {native,attributes,timers,requests,resolve,reject,read(){return JSON.parse(attributes.get('data-gecko-cpu-ip-combo'));},
    reply(body='worker-network-synthetic-v1',ok=true){resolve({ok,text:async()=>body});},timeout(){for(const [id,row]of timers){assert.equal(row.delay,8000);timers.delete(id);row.callback();}}};
}

test('one first-inline document samples real CPU getter and January/July clocks before network work',async()=>{
  const h=harness(),first=h.read();assert.equal(first.hardwareConcurrency,1);assert.equal(first.nativeGetter,true);
  assert.equal(first.firstInline,true);assert.equal(first.nativeTimeZone.timeZone,'America/New_York');
  assert.equal(first.nativeTimeZone.january.offsetMinutes,300);assert.equal(first.nativeTimeZone.july.offsetMinutes,240);
  assert.equal(first.markerComplete,false);assert.equal(first.networkAllowed,false);
  assert.deepEqual(JSON.parse(h.requests[0].before),first);assert.equal(first.runNonce,FIXTURE.runNonce);assert.equal(first.sourceCommit,FIXTURE.sourceCommit);
  assert.equal(h.requests[0].url,'/worker-probe?phase=gecko-new-york&realm=document&documentId='+first.documentId);
  assert.deepEqual(h.requests[0].settings,{cache:'no-store',credentials:'omit',redirect:'error'});
  h.reply();await flush();assert.equal(h.read().networkAllowed,true);assert.equal(h.read().markerComplete,true);assert.equal(h.timers.size,0);
});
test('the final network receipt retains the original same-document getters',async()=>{
  const h=harness(),before=h.read();h.native.set('later',2);h.reply();await flush();const after=h.read();
  assert.equal(after.documentId,before.documentId);assert.equal(after.hardwareConcurrency,1);assert.deepEqual(after.nativeTimeZone,before.nativeTimeZone);
});
test('a different native count and timezone are reported honestly instead of repaired to the desired values',async()=>{
  const h=harness({cpu:2,zone:'UTC'});assert.equal(h.read().hardwareConcurrency,2);assert.equal(h.read().nativeTimeZone.timeZone,'UTC');
  assert.equal(h.read().nativeTimeZone.january.offsetMinutes,0);h.reply();await flush();assert.equal(h.read().hardwareConcurrency,2);
});
test('a JavaScript getter does not become a native descriptor proof',async()=>{
  const h=harness({customGetter:true});assert.equal(h.read().hardwareConcurrency,1);assert.equal(h.read().nativeGetter,false);h.reply();await flush();
});
test('frames do not claim a top-level first-inline combination',()=>{const h=harness({frame:true});assert.equal(h.attributes.size,0);assert.equal(h.requests.length,0);});
test('a late or secondary script is explicitly recorded as not first-inline',async()=>{
  for(const options of [{notFirst:true},{readyState:'complete'}]){const h=harness(options);assert.equal(h.read().firstInline,false);h.reply();await flush();}
});
test('network errors, wrong response bytes and timeout cannot become a successful marker',async()=>{
  for(const mode of ['error','wrong','status','timeout']){const h=harness();if(mode==='error')h.reject(Error('controlled'));else if(mode==='timeout')h.timeout();else h.reply(mode==='wrong'?'wrong':'worker-network-synthetic-v1',mode!=='status');await flush();assert.equal(h.read().markerComplete,true);assert.equal(h.read().networkAllowed,false);assert.equal(h.timers.size,0);}
});
test('compiled collector counterfeits fail the same honest CPU, clock and descriptor assertions',async()=>{
  for(const [needle,replacement,options,check]of [
    ['const hardwareConcurrency = navigator.hardwareConcurrency;','const hardwareConcurrency = 1;',{cpu:2},value=>assert.equal(value.hardwareConcurrency,2)],
    ['Intl.DateTimeFormat().resolvedOptions().timeZone',"'America/New_York'",{zone:'UTC'},value=>assert.equal(value.nativeTimeZone.timeZone,'UTC')],
    ['Function.prototype.toString.call(descriptor.get)',"'[native code]'",{customGetter:true},value=>assert.equal(value.nativeGetter,false)]]){
    assert.equal(SOURCE.split(needle).length,2);const pristine=harness(options);check(pristine.read());pristine.reply();await flush();
    const mutant=harness({...options,source:SOURCE.replace(needle,replacement)});assert.throws(()=>check(mutant.read()),assert.AssertionError);mutant.reply();await flush();
  }
});
