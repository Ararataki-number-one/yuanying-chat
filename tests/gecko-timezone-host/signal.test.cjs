'use strict';
// Execute verbatim current/baseline public signal functions in explicit JS
// environment boundaries. This does not execute Gecko, a webpage or a Worker.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),crypto=require('node:crypto'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'../..'),asset='app/src/main/assets/gecko/main-world-audit.js',current=fs.readFileSync(path.join(root,asset),'utf8');
const fixture=fs.readFileSync(path.join(__dirname,'fixtures/baseline-signal.json'),'utf8'),baseline=JSON.parse(fixture),checks=[];
const sha=v=>crypto.createHash('sha256').update(v).digest('hex');
function extract(source){const start=source.indexOf('  async function signal(){'),end=source.indexOf('\n  // These finite probes',start);assert(start>=0&&end>start&&source.indexOf('  async function signal(){',start+1)<0);return source.slice(start,end).trim();}
assert.equal(baseline.sourceCommit,'8a0a487002993f5dacc02ed313fab00648ccb79a');assert.equal(baseline.sourcePath,asset);assert.equal(baseline.sourceSha256,'698773af650d3cf20627a25e985bcf3b200c4222d01dd9e4c42a484d29e96110');assert.equal(sha(baseline.method),'8aa4b016fa091e234105dac05ef7f6b4c5ed30b76d2bf00c36c06861d005c3de');assert.equal(baseline.methodSha256,sha(baseline.method));
const actual=extract(current),prior=baseline.method;
function check(name,pass){assert(pass,name);checks.push(name);}
async function execute(source,{at=1772953199999,offset=300}={}){
  let constructed=0,timeReads=0,offsetReads=0;
  class ObservedDate {constructor(){this.sequence=++constructed;}getTime(){timeReads++;return at+(this.sequence-1)*2000;}getTimezoneOffset(){offsetReads++;return offset+(this.sequence-1)*60;}static now(){return at+999999;}}
  const context={navigator:{userAgent:'Firefox/157.0',appVersion:'5.0 test',platform:'Linux aarch64',language:'en-US',languages:['en-US','ja-JP'],hardwareConcurrency:8,deviceMemory:undefined},Date:ObservedDate,Intl:{DateTimeFormat:()=>({resolvedOptions:()=>({timeZone:'America/New_York'})})},OffscreenCanvas:class{getContext(){return null;}}};
  const value=await vm.runInNewContext('const bounded=value=>typeof value===\'string\'?value.slice(0,2048):value;('+source+')()',context,{timeout:1000});
  return {value:JSON.parse(JSON.stringify(value)),constructed,timeReads,offsetReads};
}
(async()=>{
  const before=await execute(prior),after=await execute(actual);
  check('Production captures timestamp and offset from exactly one Date instance',after.constructed===1&&after.timeReads===1&&after.offsetReads===1&&after.value.observedAt===1772953199999&&after.value.offset===300);
  const original={...after.value};delete original.observedAt;check('Every original public signal remains byte-equivalent to hash-pinned prechange signal output',JSON.stringify(original)===JSON.stringify(before.value));
  check('Timestamp is a page-observed numeric epoch, not a host completion timestamp',typeof after.value.observedAt==='number'&&after.value.observedAt!==1772953199999+999999);
  const switched=await execute(actual,{at:1772953200001,offset:240});check('A later sample keeps its own post-DST observation',switched.value.observedAt===1772953200001&&switched.value.offset===240&&switched.constructed===1);
  const missing=await execute(actual.replace('observedAt:sampled.getTime(),',''));check('Negative control detects missing actual sample timestamp',missing.value.observedAt===undefined);
  const detached=await execute(actual.replace('observedAt:sampled.getTime()','observedAt:Date.now()'));check('Negative control detects unrelated timestamp clock read',detached.value.observedAt!==after.value.observedAt||detached.timeReads!==1);
  const duplicated=await execute(actual.replace('offset:sampled.getTimezoneOffset()','offset:new Date().getTimezoneOffset()'));check('Negative control detects offset from another Date across transition',duplicated.constructed!==1&&duplicated.value.offset!==after.value.offset);
  const report={schema:1,status:'passed',passed:checks.length,total:checks.length,checks,sourceFile:asset,sourceSha256:sha(current),methodSha256:sha(actual),baselineCommit:baseline.sourceCommit,baselineSourceSha256:baseline.sourceSha256,baselineMethodSha256:sha(prior),baselineFixtureSha256:sha(fixture),executionInputsUnchanged:sha(fs.readFileSync(path.join(root,asset)))===sha(current),actualAndroidExecution:false,actualGeckoExecution:false,scope:'Verbatim current and hash-pinned actual prechange main-world signal functions executed in Node VM with explicit navigator/Date/Intl/canvas boundaries. Date-instance and mutation controls, not webpage or native execution.'};
  assert(report.executionInputsUnchanged);const index=process.argv.indexOf('--output');if(index>=0){const output=path.resolve(process.argv[index+1]);fs.mkdirSync(path.dirname(output),{recursive:true});fs.writeFileSync(output,JSON.stringify(report,null,2)+'\n');}console.log(JSON.stringify(report));
})().catch(error=>{console.error(error);process.exitCode=1;});
