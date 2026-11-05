/* Independent current-background protocol facades only; no real header, timezone,
 * Gecko, privacy API, Cookie database or network execution is established. */
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const {runtime,flush,deferred}=require('./native-protection-handshake.test.cjs');
const checks=[];const check=(name,value)=>{assert.ok(value,name);checks.push({name,pass:true});};
let completed=false;
process.once('beforeExit',()=>{if(!completed){console.error('Independent policy boundary controls did not complete');process.exitCode=1;}});
async function main(){
  const ordinary=runtime();await ordinary.ready();
  check('Actual startup header message is observed on the declared independent channel',ordinary.current().sent.length===0&&ordinary.current().boundarySent.length===1&&ordinary.current().boundarySent[0].kind==='requestHeadersPrepared'&&ordinary.current().boundarySent[0].installed===true&&ordinary.independent.headerActivations[0]===ordinary.current());
  check('Default independent facades never manufacture native/header/timezone coverage',ordinary.independent.actualRequestHeaderPolicyExecution===false&&ordinary.independent.actualTimeZonePolicyExecution===false&&ordinary.independent.nativeSettingReadback===false&&ordinary.sets.length===0&&ordinary.reads.length===0);
  const unavailable=runtime({headersInstalled:false});await unavailable.ready();
  check('A failed declared header installation remains false in the actual background reply',unavailable.current().boundarySent[0].installed===false&&unavailable.current().sent.length===0&&unavailable.sets.length===0);

  const gate=deferred();let held=true;const cookies=runtime({cookies:async()=>{if(held)await gate.promise;}});const preparing=cookies.protect(2,1,1,'prepare');await flush();
  check('Independent header readiness cannot bypass held Cookie recovery or start native RFP',cookies.current().boundarySent.length===1&&cookies.current().boundarySent[0].kind==='requestHeadersPrepared'&&cookies.current().sent.length===0&&cookies.sets.length===0);
  held=false;gate.resolve();await preparing;
  check('Released Cookie preparation retains every original real-background RFP barrier in order',cookies.current().sent.map(row=>row.kind).join(',')==='cookiePrepared,protectionReady,ready'&&cookies.replies()[0].acknowledged===true&&cookies.replies()[0].token===1&&cookies.replies()[0].generation===1);

  const before=ordinary.current().sent.length;await ordinary.send({kind:'timezoneRead',id:1,sessionId:'declared-system-session',requestToken:'a'.repeat(64)});
  let response=ordinary.current().boundarySent.at(-1),value=JSON.parse(response.result);
  check('Default system timezone boundary returns explicit unsupported without native ACK',response.kind==='timezoneReady'&&response.id===1&&value.status==='unsupported'&&value.nativeSettingReadback===false&&ordinary.current().sent.length===before&&ordinary.independent.timeZoneCalls.length===1&&ordinary.sets.length===0);
  await ordinary.send({kind:'timezoneApply',id:2,sessionId:'declared-system-session',zoneId:'America/New_York',requestToken:'b'.repeat(64)});response=ordinary.current().boundarySent.at(-1);value=JSON.parse(response.result);
  check('A custom timezone request cannot gain a fake default-system native confirmation',response.kind==='timezoneReady'&&response.id===2&&value.status==='unsupported'&&value.nativeSettingReadback===false&&ordinary.independent.timeZoneCalls.at(-1).zoneId==='America/New_York'&&ordinary.current().sent.length===before&&ordinary.sets.length===0);
  const calls=ordinary.independent.timeZoneCalls.length;await ordinary.send({kind:'timezoneRead',id:0});
  check('Malformed independent timezone IPC is rejected by the actual background before the facade',ordinary.independent.timeZoneCalls.length===calls);
  await ordinary.send({kind:'requestHeaderPolicyChanged',revision:7});
  check('Header invalidation records the actual current port and revision without changing RFP',ordinary.independent.headerInvalidations.length===1&&ordinary.independent.headerInvalidations[0].port===ordinary.current()&&ordinary.independent.headerInvalidations[0].revision===7&&ordinary.sets.length===0&&ordinary.replies().length===0);
  const old=ordinary.current();ordinary.disconnect(old);await ordinary.advance(500);const replacement=ordinary.current(),prior=ordinary.independent.timeZoneCalls.length,invalidations=ordinary.independent.headerInvalidations.length;
  await ordinary.send({kind:'timezoneRead',id:3},old);await ordinary.send({kind:'requestHeaderPolicyChanged',revision:8},old);
  check('Retired native ports cannot call either independent policy facade',old!==replacement&&ordinary.independent.timeZoneCalls.length===prior&&ordinary.independent.headerInvalidations.length===invalidations&&ordinary.independent.headerClears.length===1&&ordinary.independent.headerClears[0]===old);
  check('Replacement startup header observation remains independent and exact-port owned',ordinary.independent.headerActivations.length===2&&ordinary.independent.headerActivations[1]===replacement&&replacement.boundarySent.length===1&&replacement.boundarySent[0].kind==='requestHeadersPrepared'&&replacement.sent.length===0);
  const boundaryBefore=replacement.boundarySent.length;replacement.postMessage({kind:'unrecognized-control-probe'});
  check('Only the two declared new kinds leave the original port observation stream',replacement.boundarySent.length===boundaryBefore&&replacement.sent.at(-1).kind==='unrecognized-control-probe'&&ordinary.independent.messages.every(row=>row.kind==='requestHeadersPrepared'||row.kind==='timezoneReady'));
  const files=['tests/browser-runtime/native-protection-handshake.test.cjs','tests/browser-runtime/native-protection-independent-boundaries.test.cjs','app/src/main/assets/gecko/background.js'];const root=path.resolve(__dirname,'../..');
  const report={schema:1,status:'passed',passed:checks.length,checks,actualAndroidExecution:false,actualGeckoExecution:false,actualRequestHeaderPolicyExecution:false,actualTimeZonePolicyExecution:false,realSettingApiExecution:false,fullFingerprintProtectionAccepted:false,sourceFiles:Object.fromEntries(files.map(name=>[name,crypto.createHash('sha256').update(fs.readFileSync(path.join(root,name))).digest('hex')])),scope:'Full current production background and original 60-check RFP adapter; only explicit independent header-installed/system-timezone-unsupported facades and fake native/Cookie APIs execute. No real header, native timezone or browser coverage claim.'};
  if(process.argv[2]==='--receipt'){assert.equal(process.argv.length,4);fs.mkdirSync(path.dirname(process.argv[3]),{recursive:true});fs.writeFileSync(process.argv[3],JSON.stringify(report,null,2)+'\n');}
  console.log(JSON.stringify({status:report.status,passed:report.passed,actualAndroidExecution:false}));completed=true;
}
main().catch(error=>{console.error(error);process.exitCode=1;});
