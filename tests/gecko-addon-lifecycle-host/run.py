#!/usr/bin/env python3
"""Current addon authority/native navigation methods, explicit SDK/UI boundaries."""
import argparse,hashlib,json,os,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
import sys
sys.path.insert(0,str(ROOT/'tests/gecko-navigation-host'))
from run import member_at
SOURCE=ROOT/'app/src/main/java/local/pocketchat/GeckoWebView.java'
NAMES=['boolean builtinAddonCurrent(','void acceptBuiltinAddon(','void addonStateChanged(','void applyAddonState(','boolean rejectDisabledNavigation(','GeckoResult<String> nativeNavigationFailure(','private void maybeOpen(','boolean protectionAllowsNetwork(','public void loadUrl(','void loadSessionUri(','void restoreCheckpoint(','static String stateUrl(','public GeckoResult<AllowOrDeny> onLoadRequest(','public GeckoResult<GeckoSession> onNewSession(','public void onLocationChange(','public void onPageStart(','public void onPageStop(','private void pageVisible(']
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--java-home',required=True,type=Path);p.add_argument('--json-jar',required=True,type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args();text=SOURCE.read_text();parts={}
 for name in NAMES:
  if text.count(name)!=1:raise ValueError('Unique current method required: '+name)
  parts[name]=member_at(text,text.index(name))
 start=text.index('private final WebExtension.MessageDelegate routeMessages=');at=text.index('public void onDisconnect(WebExtension.Port incoming)',start);parts['route-port-onDisconnect']=member_at(text,at)
 files=[SOURCE,HERE/'AddonHost.java.in',Path(__file__).resolve(),ROOT/'app/src/main/java/local/pocketchat/J.java',ROOT/'app/src/main/java/local/pocketchat/NativeProtectionState.java'];before={str(x.relative_to(ROOT)):sha(x) for x in files};template=(HERE/'AddonHost.java.in').read_text()
 def generated(chosen):return template.replace('@@MEMBERS@@','\n'.join(chosen.values()))
 with tempfile.TemporaryDirectory(prefix='gecko-addon-host-') as tmp:
  base=Path(tmp)
  def run(chosen,label,focus='all'):
   folder=base/label;folder.mkdir();java=folder/'AddonHost.java';java.write_text(generated(chosen));classes=folder/'classes';compiled=subprocess.run([str(a.java_home/'bin/javac'),'-encoding','UTF-8','-cp',str(a.json_jar),'-d',str(classes),str(java),str(ROOT/'app/src/main/java/local/pocketchat/J.java'),str(ROOT/'app/src/main/java/local/pocketchat/NativeProtectionState.java')],capture_output=True,text=True)
   if compiled.returncode:raise RuntimeError('Actual addon host compile failed: '+compiled.stderr)
   return subprocess.run([str(a.java_home/'bin/java'),'-cp',str(classes)+os.pathsep+str(a.json_jar),'local.pocketchat.AddonHost',focus],capture_output=True,text=True)
  result=run(parts,'current')
  if result.returncode:raise RuntimeError(result.stdout+result.stderr)
  report=json.loads(result.stdout);negative=[]
  boundary=run(parts,'manual-ip-boundary','manual-ip-boundary')
  if boundary.returncode:raise AssertionError('Manual-system addon boundary controls failed: '+boundary.stderr)
  boundary_report=json.loads(boundary.stdout)
  cpu_boundary=run(parts,'cpu-boundary','cpu-boundary')
  if cpu_boundary.returncode:raise AssertionError('Default CPU prerequisite boundary controls failed: '+cpu_boundary.stderr)
  cpu_boundary_report=json.loads(cpu_boundary.stdout)
  mutations=[('runtime-authority','boolean builtinAddonCurrent(','runtime==expected&&','','authority'),('stale-commit','void applyAddonState(','addonStateSerial!=serial||','','authority'),('failure-notification','GeckoResult<String> nativeNavigationFailure(','owner.finishNavigation(owner.pageError,false);','owner.setStatus(owner.pageError);','entries'),('forged-enable','void applyAddonState(','if(!disabled){extension.setMessageDelegate','if(!disabled){privacyReady=true;extension.setMessageDelegate','enable'),('disabled-open','private void maybeOpen(','&&!addonDisabled','','entries'),('late-stop','public void onPageStop(','||addonDisabled','','progress'),('late-visible','private void pageVisible(','||addonDisabled','','progress'),('late-start','public void onPageStart(','||addonDisabled','','progress'),('late-location','public void onLocationChange(','||addonDisabled','','progress')]
  for label,name,old,new,focus in mutations:
   if parts[name].count(old)!=1:raise ValueError('Unique semantic mutation required: '+label)
   changed=dict(parts);changed[name]=changed[name].replace(old,new,1);failed=run(changed,label,focus)
   if failed.returncode==0 or 'AssertionError:' not in failed.stderr:raise AssertionError('Actual addon semantic mutant escaped: '+label+failed.stderr)
   negative.append({'name':label,'currentMethod':name,'compileSucceeded':True,'runtimeRejected':True,'assertion':failed.stderr.split('AssertionError: ',1)[1].splitlines()[0]})
  cpu_negative=[]
  cpu_mutations=[('cpu-conjunction-removed','boolean protectionAllowsNetwork(','owner.cpu.readyFor(runtime)&&',''),('cpu-result-forced-ready','boolean protectionAllowsNetwork(','owner.cpu.readyFor(runtime)&&','(owner.cpu.readyFor(runtime)||true)&&')]
  for label,name,old,new in cpu_mutations:
   if parts[name].count(old)!=1:raise ValueError('Unique CPU prerequisite semantic mutation required: '+label)
   changed=dict(parts);changed[name]=changed[name].replace(old,new,1);failed=run(changed,label,'cpu-boundary')
   expected='CPU unconfirmed prerequisite denies actual native guard'
   if failed.returncode==0 or 'AssertionError: '+expected not in failed.stderr:raise AssertionError('CPU prerequisite mutant was not rejected by actual guard denial: '+label+failed.stderr)
   cpu_negative.append({'name':label,'currentMethod':name,'compileSucceeded':True,'runtimeRejected':True,'assertion':expected})
 stable=all(sha(ROOT/name)==value for name,value in before.items());report.update(schema=1,sourceCommit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),sourceFiles=before,executionInputsUnchanged=stable,jsonJarSha256=sha(a.json_jar),productionMembers=list(parts),selectedMethodsSha256={name:hashlib.sha256(value.encode()).hexdigest() for name,value in parts.items()},negativeControls=negative,manualSystemBoundaryControls=boundary_report,actualIpLookupExecution=False,actualPopupUiExecution=False,manualSystemBoundaryScope='All legacy cases explicitly choose manual-system mode; counted IP failure/retry and popup entry/invalidation collaborators throw for automatic IP scope. No IP success, UI rendering or native opening is simulated.',actualAndroidExecution=False,actualGeckoExecution=False,actualSdkAddonEventExecution=False,actualUiSpinnerExecution=False,scope='Verbatim current GeckoWebView addon authority, reject/native error, real load/nativeURI/checkpoint/popup entry methods and exact route port disconnect; complete actual NativeProtectionState and J. Explicit immutable SDK event/session/port, retired policy collaborators, owner audit/error notification, storage/writer and main-queue boundaries. No SDK/native addon operation, Android UI, network or page completion is invented. Existing native admission algorithms are declared boundaries, tested by their separate suites.')
 if not stable:report['status']='source-changed'
 report.update(cpuPrerequisiteBoundaryControls=cpu_boundary_report,cpuPrerequisiteNegativeControls=cpu_negative,cpuPrerequisiteBoundaryScope='Legacy addon cases explicitly confirm only the default CPU prerequisite for their exact opaque View.runtime. Unconfirmed, custom-mode, retired, foreign and null runtime inputs deny. Separate current-method guard/load dispatch controls execute; neither CPU controller/native preference execution nor runtime CPU readback is simulated. Two compiled conjunction mutants fail the actual unconfirmed guard-denial assertion; original 44 checks and 9 mutants remain independent.')
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:report[k] for k in ['status','passed','total','executionInputsUnchanged','actualAndroidExecution']}))
 if not stable:raise SystemExit(1)
if __name__=='__main__':main()
