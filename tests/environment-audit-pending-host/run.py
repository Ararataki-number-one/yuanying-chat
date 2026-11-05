#!/usr/bin/env python3
"""Execute current ordinary audit and exact document-fence methods at declared boundaries."""
import argparse,hashlib,json,os,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tests/gecko-navigation-host'))
from run import member_at
AUDIT=['static final class PendingPageAudit {','boolean start(boolean network,Runnable done)','boolean start(boolean network,boolean apiChecks,Runnable done)','boolean pendingPageCurrent(','void abortOrdinaryStart(','void beginOrdinaryAudit(','boolean current(','String routeStamp(','String policyStamp(','String requestIdentityPolicyStamp(','boolean fresh(','void finishIfReady(','void cancel()','void nativeDocumentProofChanged(','void retirePageCheck(','void cleanup()']
WEB=['static final class AuditDocumentFence {','Object environmentAuditDocumentFence(','boolean environmentAuditDocumentCurrent(','void awaitEnvironmentAuditDocumentProof(','boolean environmentAuditDocumentOwns(','void awaitIdentityAuditDocumentProof(','void completeTimeZoneProofs(','void runEnvironmentAudit(']
TIMEZONE=['String auditStamp(','private void boundaryChanged(']
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--java-home',required=True,type=Path);p.add_argument('--json-jar',required=True,type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args();production=ROOT/'app/src/main/java/local/pocketchat';parts={}
 for source,needles in [('EnvironmentAudit.java',AUDIT),('GeckoWebView.java',WEB),('GeckoTimeZoneController.java',TIMEZONE)]:
  raw=(production/source).read_text()
  for needle in needles:
   if raw.count(needle)!=1:raise ValueError('Unique current method required: '+source+':'+needle)
   parts[source+':'+needle]=member_at(raw,raw.index(needle))
 files=[production/name for name in ['EnvironmentAudit.java','GeckoWebView.java','GeckoTimeZoneController.java','BrowserBridgeRequests.java','J.java']]+[HERE/'Host.java.in',Path(__file__).resolve(),ROOT/'tests/gecko-navigation-host/run.py'];before={str(p.relative_to(ROOT)):sha(p)for p in files};jarHash=sha(a.json_jar);template=(HERE/'Host.java.in').read_text()
 def generate(selected):
  text=template
  for marker,source in [('AUDIT','EnvironmentAudit.java'),('WEB','GeckoWebView.java'),('TIMEZONE','GeckoTimeZoneController.java')]:
   text=text.replace('@@'+marker+'@@','\n'.join(value for key,value in selected.items()if key.startswith(source+':')))
  return text
 with tempfile.TemporaryDirectory(prefix='ordinary-audit-pending-')as folder:
  base=Path(folder)
  def execute(selected,label):
   output=base/label;output.mkdir();source=output/'Host.java';source.write_text(generate(selected));classes=output/'classes'
   compiled=subprocess.run([str(a.java_home/'bin/javac'),'-encoding','UTF-8','-cp',str(a.json_jar),'-d',str(classes),str(source),str(production/'J.java'),str(production/'BrowserBridgeRequests.java')],capture_output=True,text=True,timeout=40)
   if compiled.returncode:raise RuntimeError('Current-method host compile failed: '+compiled.stderr)
   return subprocess.run([str(a.java_home/'bin/java'),'-cp',str(classes)+os.pathsep+str(a.json_jar),'local.pocketchat.Host'],capture_output=True,text=True,timeout=40)
  current=execute(parts,'current')
  if current.returncode:raise RuntimeError(current.stdout+current.stderr)
  report=json.loads(current.stdout);negative=[]
  mutants=[('unconfirmed-ack','EnvironmentAudit.java:boolean start(boolean network,boolean apiChecks,Runnable done)','if(!ready||!pendingPageCurrent(pending))','if(!pendingPageCurrent(pending))'),('premature-dispatch','EnvironmentAudit.java:boolean start(boolean network,boolean apiChecks,Runnable done)','if(!gecko){beginOrdinaryAudit(id,false,network,apiChecks);return true;}','if(true){beginOrdinaryAudit(id,gecko,network,apiChecks);return true;}'),('config-while-pending','EnvironmentAudit.java:boolean pendingPageCurrent(','pending.configuration.equals(requestIdentityPolicyStamp())','true'),('retire-before-epoch','EnvironmentAudit.java:void retirePageCheck(','(geckoRun||pendingPageAudit!=null)','geckoRun'),('forged-native-transition','EnvironmentAudit.java:void nativeDocumentProofChanged(','pending!=null&&pendingPageCurrent(pending)&&session.web.environmentAuditDocumentOwns(pending.document,nativeSession,epoch)','pending!=null'),('restarted-budget','EnvironmentAudit.java:void beginOrdinaryAudit(','"budgetMillis",remaining','"budgetMillis",14000'),('foreign-page-port','GeckoWebView.java:boolean environmentAuditDocumentCurrent(','fence.page==ports.get(current)','true'),('replaced-document','GeckoWebView.java:boolean environmentAuditDocumentCurrent(','fence.document==fence.open.documentSerial','true'),('foreign-native-proof','GeckoWebView.java:boolean environmentAuditDocumentOwns(','fence.session==nativeSession','true'),('old-open-proof','GeckoWebView.java:boolean environmentAuditDocumentOwns(','Objects.equals(fence.open.epoch,epoch)','true')]
  for label,key,old,new in mutants:
   if parts[key].count(old)!=1:raise ValueError('Exact current semantic mutation required: '+label)
   chosen=dict(parts);chosen[key]=chosen[key].replace(old,new,1);failed=execute(chosen,label)
   if failed.returncode==0 or 'AssertionError:'not in failed.stderr:raise AssertionError('Current semantic mutant escaped: '+label+' '+failed.stderr)
   negative.append(dict(name=label,compileSucceeded=True,runtimeRejected=True,assertion=failed.stderr.split('AssertionError:',1)[1].splitlines()[0].strip()))
 stable=all(sha(ROOT/name)==digest for name,digest in before.items())and sha(a.json_jar)==jarHash;report.update(schema=1,sourceCommit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),sourceFiles=before,executionInputsUnchanged=stable,jsonJarSha256=sha(a.json_jar),extractedMethodsSha256={name:hashlib.sha256(value.encode()).hexdigest()for name,value in parts.items()},negativeControls=negative,actualAndroidExecution=False,actualGeckoExecution=False,actualNativeTimezoneReadback=False,actualSdkApiCompile=False,actualNetworkRequestsSent=False,scope='Verbatim current ordinary audit admission, pending lifecycle, complete freshness/retirement/completion, exact native document-fence/wait helpers, native boundary notification and remaining-budget dispatch. Complete actual BrowserBridgeRequests/J. SDK session/runtime/ports/native ACK states, main clock/handler, executor/native query, policy settings, report builder and persistence are explicit synthetic collaborators; no engine/timezone/getter/network or Android claim.')
 if not stable:report['status']='source-changed'
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:report[k]for k in ['status','passed','total','executionInputsUnchanged','actualAndroidExecution']}))
 if not stable:raise SystemExit(1)
if __name__=='__main__':main()
