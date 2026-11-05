#!/usr/bin/env python3
"""Actual Java IP bootstrap, real callbacks/leases and complete native-setting store path."""
import argparse
import hashlib
import importlib.util
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent;PROD=ROOT/'app/src/main/java/local/pocketchat'
EXTRACTOR=ROOT/'tests/gecko-timezone-flow-host/run.py'
spec=importlib.util.spec_from_file_location('ip_transport_verbatim_members',EXTRACTOR);extract=importlib.util.module_from_spec(spec);spec.loader.exec_module(extract)
MEMBERS=('static final class IpLookup {','static final class TimeZoneGate {','static final class IpNavigationFailure {','boolean autoIpMode(',
 'void queueIpRouteCheck(', 'void checkIpRoute(', '  String ipRouteStamp(', 'boolean ipLookupCurrent(',
 'void lookupIpTimeZone(', 'void tryStartIpLookup(', 'void cancelIpLookup(', 'void releaseIpRoute(',
 'boolean ipBootstrapRequest(', 'GeckoResult<Object> ipBootstrapHeaders(', 'boolean timeZoneSessionAlive(',
 'boolean timeZoneAllows(', 'JSONObject timeZoneStatus(', 'void retireTimeZone(', 'void retireTimeZones(',
 'boolean ipNavigationFailed(', 'boolean retryFailedIpNavigation(', 'private boolean reopenIpCurrent(', 'void finishIpNavigationFailure(', 'GeckoResult<String> nativeNavigationFailure(',
 'public void onPageStart(', 'public void onPageStop(', 'private void pageVisible(', 'public void onLocationChange(',
 'public void loadUrl(', 'Object claimTimeZoneIntent(', 'void clearTimeZoneIntent(',
 'void finishTimeZone(', 'void sendTimeZone(', 'void prepareTimeZone(', 'void revalidateTimeZone(',
 'private void startTimeZone(', 'void completeTimeZoneRequests(', 'void completeTimeZoneProofs(',
 'JSONObject blocked(', 'JSONObject route(', 'JSONObject protectedNetworkRoute(', 'String internalPoolKey(',
 'static boolean validRequestUserAgent(', 'public GeckoResult<Object> onMessage(String app,')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def replace(value,before,after,label):
 if value.count(before)!=1:raise ValueError('One exact semantic mutation required: '+label)
 return value.replace(before,after,1)
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--java-home',type=Path);p.add_argument('--json-jar',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 def tool(name):
  found=str(a.java_home/'bin'/name) if a.java_home else shutil.which(name)
  if not found:p.error('Provide JDK17 --java-home')
  return found
 source=PROD/'GeckoWebView.java';watch=PROD/'GeckoIpRouteWatch.java';identity=ROOT/'app/src/main/java/org/mozilla/geckoview/AppSessionIdentity.java';main_activity=PROD/'MainActivity.java';network=PROD/'NativeNetwork.java'
 full=[PROD/name for name in ['GeckoTimeZoneController.java','GeckoTimeZoneSpec.java','GeckoTimeZoneStore.java','GeckoTimeZonePolicy.java','GeckoIpTimeZonePolicy.java','EnvironmentSpec.java','NetworkShareJson.java','J.java','ChromiumRouteLease.java','BrowserBridgeRequests.java','NetworkPoolIdentity.java','Sha256.java','BrowserAddressPolicy.java','GeckoNavigationPolicy.java']]
 adapters=ROOT/'tests/gecko-timezone-host/GeckoTimeZoneHost.java';template_path=HERE/'IpTransportHost.java.in'
 files=[source,watch,identity,main_activity,network,adapters,template_path,EXTRACTOR,Path(__file__).resolve(),HERE/'README.md',*full];hashes={str(path.relative_to(ROOT)):sha(path) for path in files};jar=sha(a.json_jar)
 text=source.read_text();selected={marker:extract.block(text,marker) for marker in MEMBERS}
 scoped=text[text.index('private final WebExtension.MessageDelegate routeMessages='):text.index('final WebExtension.MessageDelegate pageMessages=')]
 selected['nativePort.onPortMessage']=extract.block(scoped,'public void onPortMessage(Object message,WebExtension.Port incoming)')
 watch_methods={marker:extract.block(watch.read_text(),marker) for marker in ['static final class Snapshot {','private void update(', 'private void updateLinks(', 'Snapshot snapshot(']}
 extras={'@IDENTITY@':extract.block(identity.read_text(),'public static String id('),'@VALID_PROXY@':extract.block(main_activity.read_text(),'static boolean validProxy('),'@HASH@':extract.block(network.read_text(),'static String hash(String s)')}
 template=template_path.read_text();renames=(('WebExtension.MessageSender','SenderBoundary'),('WebExtension.Port','PortBoundary'),('GeckoSession','SessionBoundary'),('GeckoRuntime','RuntimeBoundary'),('GeckoResult','ResultBoundary'),('GeckoWebView','WebBoundary'),('GeckoIpRouteWatch','RouteWatchBoundary'),('NativeNetwork','NetworkBoundary'),('AppSessionIdentity','IdentityBoundary'),('SystemClock','ClockBoundary'),('Looper.','LooperBoundary.'),('Uri.','UriBoundary.'))
 def generate(members,watching):
  value=template.replace('@METHODS@','\n'.join(members.values())).replace('@WATCH@','\n'.join(watching.values()))
  for marker,body in extras.items():value=value.replace(marker,body)
  # Only SDK/OS/app boundary type names change; selected method bodies and
  # real controller/store/callback/lease production sources otherwise execute.
  for before,after in renames:value=value.replace(before,after)
  value=re.sub(r'\bUri\b','UriBoundary',value)
  # The complete controller's static version reference needs its explicitly
  # declared app facade, distinct from the actual extracted WebBoundary.
  value=value.replace('final class WebBoundary {static final String VERSION=WebBoundary.VERSION;}','final class GeckoWebView {static final String VERSION=WebBoundary.VERSION;}')
  return value
 a.output.parent.mkdir(parents=True,exist_ok=True);artifacts=a.output.parent/(a.output.stem+'-artifacts');artifacts.mkdir(exist_ok=True);controls=[]
 with tempfile.TemporaryDirectory(prefix='gecko-ip-transport-') as temporary:
  temp=Path(temporary)
  def execute(members,watching,label,focus='full'):
   out=artifacts/label;out.mkdir(exist_ok=True);host=out/'IpTransportHost.java';host.write_text(generate(members,watching));context=out/'android/content/Context.java';context.parent.mkdir(parents=True,exist_ok=True);context.write_text('package android.content;public abstract class Context {public abstract Context getApplicationContext();public abstract java.io.File getNoBackupFilesDir();}\n')
   cmd=[tool('javac'),'--release','17','-encoding','UTF-8','-cp',str(a.json_jar.resolve()),'-d',str(temp/label/'classes'),*map(str,full),str(adapters),str(context),str(host)]
   built=subprocess.run(cmd,text=True,capture_output=True,timeout=60);(out/'compile.command.json').write_text(json.dumps(cmd)+'\n');(out/'compile.stdout.log').write_text(built.stdout);(out/'compile.stderr.log').write_text(built.stderr)
   if built.returncode:raise RuntimeError(label+' compilation failed:\n'+built.stderr)
   cmd=[tool('java'),'-cp',str(temp/label/'classes')+os.pathsep+str(a.json_jar.resolve()),'local.pocketchat.IpTransportHost',str(temp/label/'state'),focus]
   ran=subprocess.run(cmd,text=True,capture_output=True,timeout=60);(out/'run.command.json').write_text(json.dumps(cmd)+'\n');(out/'run.stdout.log').write_text(ran.stdout);(out/'run.stderr.log').write_text(ran.stderr);return ran
  current=execute(selected,watch_methods,'current')
  if current.returncode:raise RuntimeError(current.stdout+current.stderr)
  result=json.loads(current.stdout)
  mutations=[
   ('native-sender','public GeckoResult<Object> onMessage(String app,','||sender.environmentType!=WebExtension.MessageSender.ENV_TYPE_EXTENSION','','protocol','Content native-message caller cannot borrow IP bootstrap'),
   ('lookup-token','boolean ipBootstrapRequest(','claim.token.equals(token)&&','','protocol','Wrong native lookup token is denied even for exact source'),
   ('native-response-id','nativePort.onPortMessage','&&claim.id==data.optInt("id")','','protocol','Wrong native response request id cannot finish the lookup'),
   ('native-open-gate','boolean ipLookupCurrent(','timeZoneGates.get(claim.session)==claim.gate&&','','gate','Changed gate authority cannot use old bootstrap'),
   ('native-document','boolean ipLookupCurrent(','claim.gate.documentSerial==claim.document','true','document','Changed document authority cannot use old bootstrap'),
   ('lease-until-store','void lookupIpTimeZone(','ChromiumRouteLease.Handle old=ipRouteLeases.put(gate,claim.lease);','claim.lease.close();ChromiumRouteLease.Handle old=ipRouteLeases.put(gate,claim.lease);','commit','Geo response transfers rather than releases its actual route lease'),
   ('retire-handoff-lease','void retireTimeZone(','releaseIpRoute(gate);','','cancel','Retiring native gate releases handoff route lease'),
   ('header-claim-owner','GeckoResult<Object> ipBootstrapHeaders(','ipLookup==claim&&','','headers','Old SDK UA callback cannot borrow a replacement lookup'),
   ('diagnostic-header-guard','boolean ipBootstrapRequest(','&&identityRequestAllowed(target)','','protocol','Changed diagnostic admission denies bootstrap before SDK UA read'),
   ('timeout-cancel','void finishTimeZone(','if(!gate.ready&&ipLookup!=null&&ipLookup.session==session&&ipLookup.gate==gate)cancelIpLookup();','','cancel','Controller timeout immediately cancels the native lookup and releases its lease'),
   ('spinner-failure-dispatch','void finishTimeZone(','finishIpNavigationFailure(session,gate,issue);','','spinner','Eight-second initial IP failure stops spinner and preserves its exact queued target'),
   ('spinner-task-owner','void finishIpNavigationFailure(','owner.pending!=null||','','spinner','Initial IP failure preserves protected state: pending'),
   ('spinner-late-progress','public void onPageStop(','||ipNavigationFailed(s)','','spinner','Late native errors and progress cannot overwrite exact failed initial IP state'),
   ('spinner-retry-gate','boolean retryFailedIpNavigation(','return reopenIpCurrent();','return true;','spinner','Explicit retry uses actual loadUrl and retires the failed native window before a fresh SDK barrier'),
   ('spinner-retry-task','boolean retryFailedIpNavigation(','owner.pending!=null||','','spinner','Explicit IP retry does not replace a protected live task: pending'),
   ('watch-link-owner','private void updateLinks(','!state.network.equals(network)||','','watch','Old default-network link callback cannot replace the current network'),
  ]
  for label,member,before,after,focus,assertion in mutations:
   pristine=execute(selected,watch_methods,'pristine-'+label,focus)
   if pristine.returncode:raise AssertionError('Pristine focus failed: '+label+pristine.stderr)
   modified=dict(selected);modified_watch=dict(watch_methods);target=modified if member in modified else modified_watch;target[member]=replace(target[member],before,after,label);failed=execute(modified,modified_watch,'mutant-'+label,focus)
   if failed.returncode!=1 or 'java.lang.AssertionError: '+assertion not in failed.stderr:raise AssertionError('Compiled mutant must fail its exact assertion: '+label+'\n'+failed.stdout+failed.stderr)
   controls.append(dict(name=label,compiled=True,pristinePassed=True,runtimeExitCode=failed.returncode,assertion=assertion,producerMethod=member,mutantBodySha256=hashlib.sha256(target[member].encode()).hexdigest()));result['checks'].append('Compiled actual semantic mutant rejected: '+label)
  result['passed']+=len(controls);result['total']+=len(controls)
 stable=all(sha(path)==hashes[str(path.relative_to(ROOT))] for path in files) and sha(a.json_jar)==jar
 result.update(schema=1,status='passed' if stable else 'source-changed',sourceFiles=hashes,sourceCommit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),executionInputsUnchanged=stable,jsonJarSha256=jar,productionMethodSha256={key:hashlib.sha256(value.encode()).hexdigest() for key,value in selected.items()},watchMethodSha256={key:hashlib.sha256(value.encode()).hexdigest() for key,value in watch_methods.items()},compiledSemanticMutants=controls,actualAndroidExecution=False,actualGeckoExecution=False,actualNetworkExecution=False,actualPublicGeoExecution=False,actualDateIntlExecution=False,actualWorkerExecution=False,actualSqliteExecution=False,actualAesKeystoreExecution=False,httpOriginPrincipalVerifiedByThisJavaHost=False,httpRequestIdVerifiedByThisJavaHost=False,scope='Actual current Java native bootstrap/native-message and port callbacks, full real Controller/Spec/Store/Policy/parser, real ChromiumRouteLease/BrowserBridgeRequests/NetworkPoolIdentity and pure address/hash policies. Actual initial-IP failure, late progress delegates, explicit loadUrl retry, full native-session replacement and route-watch lifecycle execute. Real filesystem/FileLock/atomic replacement via declared existing core IO adapters. Named SDK session/result/runtime/port, UA read, Handler clock, native route admission/default-network/link snapshot and native read/apply inputs are controlled JVM boundaries. Actual extension HTTP principal/requestId and credential stripping are independently exercised by unchanged Node producer suites, never inferred from Java endpoint matching. This host executes native-message sender environment and request-id/port ownership, not native network/BC/page/Worker effects.')
 result.update(actualPublicIpGeolocationVerified=False,syntheticGeoService=True,syntheticGeoInputs=True)
 a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({key:result[key] for key in ['schema','status','passed','total','executionInputsUnchanged','actualAndroidExecution']}))
 if not stable:raise SystemExit(1)
if __name__=='__main__':main()
