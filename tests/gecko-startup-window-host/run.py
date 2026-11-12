#!/usr/bin/env python3
"""Current Gecko startup-window admission and retirement; declared SDK boundary."""
import argparse,hashlib,importlib.util,json,os,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
SOURCE=ROOT/'app/src/main/java/local/pocketchat/GeckoWebView.java'
spec=importlib.util.spec_from_file_location('startup_java_member',ROOT/'tests/gecko-navigation-host/run.py')
reader=importlib.util.module_from_spec(spec);spec.loader.exec_module(reader)
NAMES=['private void maybeOpen(','private void open(','private void failure(','void destroy(',
       'boolean builtinAddonCurrent(','void acceptBuiltinAddon(','void addonStateChanged(','void applyAddonState(']
OPTIONAL=['private boolean prepareStartupWindow(','private void closeStartupWindow()','private void closeStartupWindow(GeckoSession window)']
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--java-home',type=Path,required=True);p.add_argument('--json-jar',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--red-baseline',action='store_true');a=p.parse_args()
 source=SOURCE.read_text();parts={}
 for name in NAMES+OPTIONAL:
  count=source.count(name)
  if count==0 and name in OPTIONAL and a.red_baseline:continue
  if count!=1:raise ValueError('Unique current member required: '+name)
  parts[name]=reader.member_at(source,source.index(name))
 files=[SOURCE,HERE/'StartupWindowHost.java.in',Path(__file__).resolve(),ROOT/'tests/gecko-navigation-host/run.py',ROOT/'app/src/main/java/local/pocketchat/J.java'];before={str(x.relative_to(ROOT)):sha(x) for x in files}
 deps={str(a.json_jar.resolve()):sha(a.json_jar),str((a.java_home/'bin/javac').resolve()):sha(a.java_home/'bin/javac'),str((a.java_home/'bin/java').resolve()):sha(a.java_home/'bin/java')}
 template=(HERE/'StartupWindowHost.java.in').read_text();a.output.parent.mkdir(parents=True,exist_ok=True)
 artifacts=a.output.parent/(a.output.stem+'-artifacts');artifacts.mkdir(exist_ok=True)
 with tempfile.TemporaryDirectory(prefix='gecko-startup-window-') as temporary:
  base=Path(temporary)
  def run(chosen,label):
   folder=base/label;folder.mkdir();java=folder/'StartupWindowHost.java';java.write_text(template.replace('@@MEMBERS@@','\n'.join(chosen.values())))
   compiled=subprocess.run([str(a.java_home/'bin/javac'),'-encoding','UTF-8','-cp',str(a.json_jar),'-d',str(folder/'classes'),str(java),str(ROOT/'app/src/main/java/local/pocketchat/J.java')],capture_output=True,text=True)
   (artifacts/(label+'-compile.log')).write_text(compiled.stdout+compiled.stderr)
   if compiled.returncode:raise RuntimeError('Actual current startup methods did not compile: '+compiled.stderr)
   result=subprocess.run([str(a.java_home/'bin/java'),'-cp',str(folder/'classes')+os.pathsep+str(a.json_jar),'local.pocketchat.StartupWindowHost'],capture_output=True,text=True)
   (artifacts/(label+'-run.log')).write_text(result.stdout+result.stderr)
   if not result.stdout.strip():raise RuntimeError('Startup host did not report behavior: '+result.stderr)
   return result,json.loads(result.stdout)
  result,report=run(parts,'current');negative=[]
  if a.red_baseline:
   if result.returncode==0:raise AssertionError('The requested original-source red reproduction unexpectedly passed')
   report['expectedRegressionReproduced']=any(x['name']=='Installed background receives an initial SDK window without waiting for its own bridge' and x['pass'] is False for x in report['checks'])
   if not report['expectedRegressionReproduced']:raise AssertionError('Original failure did not reproduce the installed background wait')
  else:
   if result.returncode:raise RuntimeError('Current startup behavior failed: '+result.stdout+result.stderr)
   mutations=[
    ('restore-startup-cycle','private void maybeOpen(','if(!routePrepared&&!prepareStartupWindow())return;','if(!routePrepared)return;'),
    ('skip-identity-admission','private void maybeOpen(','&&identityPrepared',''),
    ('skip-native-admission','private void maybeOpen(','&&protectionAllowsNetwork()',''),
    ('bootstrap-navigation-allow','private boolean prepareStartupWindow(','GeckoResult.fromValue(AllowOrDeny.DENY)','GeckoResult.fromValue(AllowOrDeny.ALLOW)'),
    ('failure-leaks-bootstrap','private void failure(','closeStartupWindow();',''),
    ('destroy-leaks-bootstrap','void destroy(','closeStartupWindow();',''),
    ('primary-leaks-bootstrap','private void open(','closeStartupWindow();',''),
    ('disabled-leaks-bootstrap','void applyAddonState(','closeStartupWindow();',''),
    ('deleted-owner-revived','private void maybeOpen(','&&!owner.deleted',''),
    ('late-open-leaks-retired-window','private boolean prepareStartupWindow(','if(startupWindow==window)startupWindow=null;closeStartupWindow(window);return false;','if(startupWindow==window)closeStartupWindow();return false;'),
    ('late-throw-leaks-retired-window','private boolean prepareStartupWindow(','\n      closeStartupWindow(window);\n      return false;','\n      return false;'),
   ]
   for label,name,old,new in mutations:
    if parts[name].count(old)!=1:raise ValueError('Unique startup semantic mutation required: '+label)
    changed=dict(parts);changed[name]=changed[name].replace(old,new,1);failed,value=run(changed,label)
    if failed.returncode==0 or value['status']!='failed':raise AssertionError('Compiled startup mutant escaped: '+label)
    negative.append(dict(name=label,compileSucceeded=True,runtimeRejected=True,failedChecks=[x['name'] for x in value['checks'] if not x['pass']]))
 stable=all(sha(ROOT/name)==digest for name,digest in before.items()) and all(sha(Path(name))==digest for name,digest in deps.items())
 report.update(schema=1,sourceCommit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),sourceFiles=before,dependencies=deps,executionInputsUnchanged=stable,productionMembers=list(parts),compileSucceeded=True,negativeControls=negative,actualAndroidExecution=False,actualGeckoExecution=False,actualNetworkExecution=False,
  scope='Verbatim current GeckoWebView maybeOpen/open/failure/destroy, authoritative addon event methods and startup-window helpers, complete J. SDK/Android objects and their window-created/extension-ready delivery are declared boundaries. Installed background waits for the first window; fresh installation can connect immediately. The pinned upstream source probe and actual API32/35 run remain separate evidence; this host does not attest native startup or networking.')
 if not stable:report['status']='source-changed'
 a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:report[k] for k in ['status','passed','total','compileSucceeded','executionInputsUnchanged','actualGeckoExecution']}))
 if not stable or not a.red_baseline and report['status']!='passed':raise SystemExit(1)
if __name__=='__main__':main()
