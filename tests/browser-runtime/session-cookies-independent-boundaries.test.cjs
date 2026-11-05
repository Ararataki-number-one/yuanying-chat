/* Current full background through explicit Cookie/header/system-timezone host
 * facades. No Android, native headers, native timezone or real Cookie API proof. */
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const {runtime,microtasks,cookie}=require('./session-cookies-coalescing.test.cjs');
let completed=false;const checks=[];
process.once('beforeExit',()=>{if(!completed){console.error('Cookie independent boundary checks did not complete');process.exitCode=1;}});
const check=(name,value)=>{assert.ok(value,name);checks.push({name,pass:true});};
async function main(){
  const initial=runtime();await initial.ready();
  check('Actual new header installation message has an independent observation channel',initial.sent.length===0&&initial.boundarySent.length===1&&initial.boundarySent[0].kind==='requestHeadersPrepared'&&initial.boundarySent[0].installed===true&&initial.independent.headerActivations===1);
  check('Cookie fixture never claims actual header, timezone or native readback execution',initial.independent.actualRequestHeaderPolicyExecution===false&&initial.independent.actualTimeZonePolicyExecution===false&&initial.independent.nativeSettingReadback===false);
  const unavailable=runtime({},[],'',{headersInstalled:false});await unavailable.ready();
  check('Declared failed header installation cannot be silently promoted to installed',unavailable.boundarySent.length===1&&unavailable.boundarySent[0].installed===false&&unavailable.sent.length===0);
  const held=runtime({sessionCookiesV1:[cookie('held-session')]});const gate=held.hold('read');let prepared=false,read=false;
  const preparation=held.prepare().then(()=>{prepared=true;}),reading=held.read().then(()=>{read=true;});await gate.started.promise;await microtasks();
  check('Independent header readiness cannot release held recovery or Cookie read barriers',held.boundarySent.length===1&&held.boundarySent[0].kind==='requestHeadersPrepared'&&!prepared&&!read&&held.sent.length===0&&held.counts.writes===0);
  gate.resume.resolve();await Promise.all([preparation,reading]);
  check('Actual Cookie readiness and read replies appear only after complete journal restoration',prepared&&read&&held.sets.length===1&&held.storage.sessionCookiesV1.length===1&&held.sent.some(value=>value.kind==='cookiePrepared')&&held.sent.some(value=>value.kind==='ready')&&held.sent.some(value=>value.kind==='cookies'&&value.error!==true));
  const before=initial.sent.length;await initial.send({kind:'timezoneRead',id:1,sessionId:'system-only-boundary',requestToken:'a'.repeat(64)});
  let value=JSON.parse(initial.boundarySent.at(-1).result);
  check('Default system timezone boundary remains explicitly unsupported without native ACK',initial.boundarySent.at(-1).kind==='timezoneReady'&&value.status==='unsupported'&&value.nativeSettingReadback===false&&initial.independent.timeZoneCalls.length===1&&initial.sent.length===before);
  await initial.send({kind:'timezoneApply',id:2,sessionId:'system-only-boundary',zoneId:'America/New_York',requestToken:'b'.repeat(64)});value=JSON.parse(initial.boundarySent.at(-1).result);
  check('Custom timezone request cannot acquire invented native confirmation',value.status==='unsupported'&&value.nativeSettingReadback===false&&initial.independent.timeZoneCalls.at(-1).zoneId==='America/New_York'&&initial.sent.length===before);
  await initial.send({kind:'requestHeaderPolicyChanged',revision:2});
  check('Independent header invalidation does not manufacture Cookie protocol output',initial.independent.headerInvalidations===1&&initial.sent.length===before);
  const boundaryCount=initial.boundarySent.length;
  // Synthetic host-side messages test the observer partition only. They are
  // never represented as messages emitted by the real production background.
  const kinds=['cookiePrepared','ready','cookies','checkpoint','cookieRecoveryError','protectionReady','unrecognized-control-probe'];
  for(const kind of kinds)initial.postNative({kind,syntheticObserverProbe:true});
  check('Cookie, checkpoint, RFP, error and unknown kinds cannot be swallowed by the independent observer',initial.boundarySent.length===boundaryCount&&initial.sent.slice(before).map(value=>value.kind).join(',')===kinds.join(','));
  check('Every independently observed message has exactly one of the two declared new kinds',initial.boundarySent.every(value=>value.kind==='requestHeadersPrepared'||value.kind==='timezoneReady'));
  const root=path.resolve(__dirname,'../..'),files=['tests/browser-runtime/session-cookies-coalescing.test.cjs','tests/browser-runtime/session-cookies-independent-boundaries.test.cjs','app/src/main/assets/gecko/background.js'];
  const report={schema:1,status:'passed',passed:checks.length,checks,actualAndroidExecution:false,actualGeckoExecution:false,actualRequestHeaderPolicyExecution:false,actualTimeZonePolicyExecution:false,realCookieApiExecution:false,nativeSettingReadback:false,sourceFiles:Object.fromEntries(files.map(name=>[name,crypto.createHash('sha256').update(fs.readFileSync(path.join(root,name))).digest('hex')])),scope:'Complete current production background with explicit Cookie/header-installed/system-timezone-unsupported facades. Held Cookie barriers and exact two-kind message separation only, not native/HTTP/timezone coverage.'};
  if(process.argv[2]==='--receipt'){assert.equal(process.argv.length,4);fs.mkdirSync(path.dirname(process.argv[3]),{recursive:true});fs.writeFileSync(process.argv[3],JSON.stringify(report,null,2)+'\n');}
  console.log(JSON.stringify({status:'passed',passed:checks.length,actualAndroidExecution:false}));completed=true;
}
main().catch(error=>{console.error(error);process.exitCode=1;});
