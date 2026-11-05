#!/usr/bin/env python3
"""Actual authorized audit navigation, full timezone lifecycle and exact proof predicate."""
import argparse, hashlib, importlib.util, json, shutil, subprocess, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
PROD=ROOT/'app/src/main/java/local/pocketchat'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
spec=importlib.util.spec_from_file_location('timezone_flow_extraction',ROOT/'tests/gecko-timezone-flow-host/run.py')
extract=importlib.util.module_from_spec(spec);spec.loader.exec_module(extract)
block=extract.block
AUDIT=['static String hash(', 'static String packageVersion(', 'String routeStamp(', 'String policyStamp(', 'String requestIdentityPolicyStamp(', 'JSONObject expected(', 'boolean observationCurrent(']
WEB=['static final class TimeZoneGate {', 'boolean timeZoneSessionAlive(', 'boolean timeZoneAllows(', 'JSONObject timeZoneStatus(', 'void finishTimeZone(', 'void releaseIpRoute(', 'void completeTimeZoneRequests(', 'void completeTimeZoneProofs(', 'Object identityAuditNativeOpen(', 'void awaitIdentityAuditDocumentProof(']
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--java-home',type=Path);p.add_argument('--json-jar',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 def tool(n):return str(a.java_home/'bin'/n) if a.java_home else shutil.which(n)
 names=['RequestIdentityAuditSession.java','RequestIdentityAudit.java','RequestIdentityLanguages.java','AuditReport.java','GeckoTimeZoneController.java','GeckoTimeZoneSpec.java','GeckoTimeZoneStore.java','GeckoTimeZonePolicy.java','GeckoIpTimeZonePolicy.java','ChromiumRouteLease.java','EnvironmentSpec.java','NetworkShareJson.java','J.java']
 sources=[PROD/n for n in names];audit=PROD/'EnvironmentAudit.java';web=PROD/'GeckoWebView.java';network=PROD/'BrowserNetworkGuard.java'
 am={m:block(audit.read_text(),m) for m in AUDIT};wm={m:block(web.read_text(),m) for m in WEB}
 fields=[line.strip() for line in web.read_text().splitlines() if line.strip().startswith('final Map<TimeZoneGate,ChromiumRouteLease.Handle> ipRouteLeases=')]
 if len(fields)!=1 or not fields[0].endswith(';'):raise ValueError('Unique complete current IP route-lease field required')
 nm={m:block(network.read_text(),m) for m in ['static boolean localHost(', 'static boolean privateV4(']}
 host=HERE/'RequestIdentityTimezoneHost.java.in';core=ROOT/'tests/gecko-timezone-host/GeckoTimeZoneHost.java'
 comparison=ROOT/'tests/request-identity/RequestIdentityAuditHost.java'
 inputs=sources+[audit,web,network,host,core,comparison,Path(__file__).resolve(),ROOT/'tests/gecko-timezone-flow-host/run.py'];hashes={str(x.relative_to(ROOT)):sha(x) for x in inputs}
 with tempfile.TemporaryDirectory(prefix='request-identity-timezone-') as temp:
  folder=Path(temp);context=folder/'android/content/Context.java';context.parent.mkdir(parents=True);context.write_text('package android.content;public abstract class Context{public abstract Context getApplicationContext();public abstract java.io.File getNoBackupFilesDir();}\n')
  clock=folder/'android/os/SystemClock.java';clock.parent.mkdir(parents=True);clock.write_text('package android.os;public final class SystemClock{public static long now=1000;public static long elapsedRealtime(){return now;}}\n')
  template=host.read_text();generated=folder/'RequestIdentityTimezoneHost.java'
  def generated_text(methods):return template.replace('/*@@AUDIT@@*/','\n'.join(am.values())).replace('/*@@WEB@@*/','\n'.join(methods.values())).replace('/*@@IP_ROUTE_FIELDS@@*/',fields[0]).replace('/*@@NETWORK@@*/','\n'.join(nm.values()))
  generated.write_text(generated_text(wm));request=PROD/'RequestIdentityAuditSession.java'
  def execute(label,request_source,methods):
   sub=folder/label;sub.mkdir();classes=sub/'classes';selected=sources
   if request_source is not None:
    altered=sub/'RequestIdentityAuditSession.java';altered.write_text(request_source);selected=[altered if x==request else x for x in sources]
   wrapper=sub/'RequestIdentityTimezoneHost.java';wrapper.write_text(generated_text(methods))
   c=subprocess.run([tool('javac'),'-encoding','UTF-8','-source','8','-target','8','-cp',str(a.json_jar.resolve()),'-d',str(classes),*map(str,selected),str(core),str(comparison),str(context),str(clock),str(wrapper)],capture_output=True,text=True)
   if c.returncode:raise RuntimeError(label+' actual source compilation failed:\n'+c.stderr)
   r=subprocess.run([tool('java'),'-cp',str(classes)+':'+str(a.json_jar.resolve()),'local.pocketchat.RequestIdentityTimezoneHost',str(sub/'state')],capture_output=True,text=True,timeout=60)
   return r
  result=execute('current',None,wm)
  if result.returncode:raise RuntimeError(result.stdout+'\n'+result.stderr)
  report=json.loads(result.stdout);current=request.read_text();mutants=[]
  mutations=[('original-full-stamp-opening','!documentUrl.equals(target)||!configurationFresh()','!documentUrl.equals(target)||!routeFresh()','Authorized own navigation survives full-stamp document invalidation'),('configuration-fence','&&configurationPolicy.equals(audit.requestIdentityPolicyStamp())','','Changed configuration cannot rebind detector proof: configuration'),('open-incarnation-fence','&&nativeOpen==session.web.identityAuditNativeOpen()','','Original open incarnation remains part of configuration fence'),('full-stamp-after-binding','&&policy.equals(audit.policyStamp())','','Pending native proof cannot collect or issue detector subrequests'),('proof-required','if(!ready||!requestNonce.equals(nonce)','if(!requestNonce.equals(nonce)','Unconfirmed actual proof cannot rebind the audit')]
  for label,before,after,assertion in mutations:
   if current.count(before)!=1:raise RuntimeError('Unique current semantic mutation required '+label)
   r=execute(label,current.replace(before,after,1),wm)
   if r.returncode!=1 or 'java.lang.AssertionError: '+assertion not in r.stderr:raise RuntimeError(label+' did not fail exact assertion:\n'+r.stdout+'\n'+r.stderr)
   mutants.append(dict(name=label,compiled=True,runtimeExitCode=r.returncode,assertion=assertion))
  # Removing expected-open from the actual native proof predicate must also fail.
  marker='void awaitIdentityAuditDocumentProof(';before='expectedOpen!=gate||';body=wm[marker]
  if body.count(before)!=1:raise RuntimeError('Unique actual native open guard required')
  changed=dict(wm);changed[marker]=body.replace(before,'',1);r=execute('native-open-proof',None,changed)
  assertion='Actual proof rejects the same SDK object with a different open gate'
  if r.returncode!=1 or 'java.lang.AssertionError: '+assertion not in r.stderr:raise RuntimeError('Native open proof counterfeit not rejected:\n'+r.stdout+'\n'+r.stderr)
  mutants.append(dict(name='native-open-proof',compiled=True,runtimeExitCode=r.returncode,assertion=assertion))
  for label,before,after,assertion in [('ip-lease-close','lease.close();',';','Actual IP lease release closes its owned real registry handle'),('ip-lease-remove','ipRouteLeases.remove(gate)','ipRouteLeases.get(gate)','Actual IP lease release removes only its owned gate entry')]:
   marker='void releaseIpRoute(';body=wm[marker]
   if body.count(before)!=1:raise RuntimeError('Unique current IP lease mutation required: '+label)
   changed=dict(wm);changed[marker]=body.replace(before,after,1);r=execute(label,None,changed)
   if r.returncode!=1 or 'java.lang.AssertionError: '+assertion not in r.stderr:raise RuntimeError(label+' did not fail exact lease assertion:\n'+r.stdout+'\n'+r.stderr)
   mutants.append(dict(name=label,compiled=True,runtimeExitCode=r.returncode,assertion=assertion))
 stable=all(sha(x)==hashes[str(x.relative_to(ROOT))] for x in inputs)
 report.update(schema=1,status='passed' if stable else 'source-changed',compiledSemanticMutants=mutants,executionInputsUnchanged=stable,sourceCommit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),sourceFiles=hashes,methodSha256={**{'EnvironmentAudit:'+k:hashlib.sha256(v.encode()).hexdigest() for k,v in am.items()},**{'GeckoWebView:'+k:hashlib.sha256(v.encode()).hexdigest() for k,v in wm.items()}},fieldSha256={'GeckoWebView:ipRouteLeases':hashlib.sha256(fields[0].encode()).hexdigest()},jsonJarSha256=sha(a.json_jar),actualIpLookupExecution=False,actualJavaIpLeaseReleaseExecution=True,manualSelectionBoundary='Retained request-identity cases explicitly save manual New York. Verbatim current lease map/release and complete real Java registry are exercised separately; no native IP lookup, route admission, transport or Worker proof is simulated.',actualAndroidExecution=False,actualGeckoExecution=False,actualNativeTimezoneExecution=False,actualAesKeystoreExecution=False,scope='Entire current RequestIdentityAuditSession, comparison/report, full timezone Controller/Store/Policy and verbatim current audit stamps/expected/observation freshness plus Gecko live-open/proof/finish predicates. Real filesystem and locks, explicit catalog/atomic-vault adapters; synthetic native ACK input must pass actual strict parser, writer publication and current proof fences. Manual SDK document commit, SDK objects/port, handler/clock, preferences, page/draft/driver and report persistence boundaries are declared; no Android, native setter, HTTP or page/Worker semantics inferred.')
 report['total']+=len(mutants);report['passed']+=len(mutants)
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:report[k] for k in ['status','passed','total','executionInputsUnchanged','actualAndroidExecution','actualNativeTimezoneExecution']}))
 if not stable:raise SystemExit(1)
if __name__=='__main__':main()
