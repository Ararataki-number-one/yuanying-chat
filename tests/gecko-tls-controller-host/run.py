#!/usr/bin/env python3
"""Whole TLS controller/profile/store against real filesystem and explicit callback inputs."""
import argparse,hashlib,json,os,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--java-home',type=Path,required=True);p.add_argument('--json-jar',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 names=['GeckoTlsController.java','GeckoTlsProfile.java','GeckoTlsStore.java','GeckoTlsSpec.java','GeckoCpuProfile.java','GeckoCpuSpec.java','EnvironmentSpec.java','NetworkShareJson.java','J.java'];sources=[ROOT/'app/src/main/java/local/pocketchat'/n for n in names]+[HERE/'ControllerHost.java',HERE/'Collaborators.java'];before={str(q.relative_to(ROOT)):sha(q)for q in sources+[Path(__file__).resolve()]};jar=sha(a.json_jar);reports=[];negative=[]
 with tempfile.TemporaryDirectory(prefix='gecko-tls-controller-')as temp:
  folder=Path(temp);stubs={
   'android/content/Context.java':'package android.content;public abstract class Context{public abstract Context getApplicationContext();public abstract java.io.File getNoBackupFilesDir();public abstract android.content.pm.ApplicationInfo getApplicationInfo();}',
   'android/content/pm/ApplicationInfo.java':'package android.content.pm;public final class ApplicationInfo{public String dataDir;}',
   'android/os/Process.java':'package android.os;public final class Process{public static int myPid(){return 111;}}'}
  for name,text in stubs.items():q=folder/name;q.parent.mkdir(parents=True,exist_ok=True);q.write_text(text)
  def compile_java(label,change=None):
   out=folder/label;out.mkdir();selected=list(sources)
   if change:
    filename,old,new=change;original=next(q for q in sources if q.name==filename);raw=original.read_text()
    if raw.count(old)!=1:raise ValueError('Unique current native counterexample required: '+label)
    replacement=out/filename;replacement.write_text(raw.replace(old,new,1));selected=[replacement if q==original else q for q in selected]
   classes=out/'classes';c=subprocess.run([str(a.java_home/'bin/javac'),'-encoding','UTF-8','-cp',str(a.json_jar),'-d',str(classes),*map(str,selected),*map(str,[folder/n for n in stubs])],text=True,capture_output=True,timeout=40)
   if c.returncode:raise RuntimeError(c.stderr)
   return out,classes
  def execute(out,classes,scenario):return subprocess.run([str(a.java_home/'bin/java'),'-cp',str(classes)+os.pathsep+str(a.json_jar),'local.pocketchat.ControllerHost',str(out/scenario),scenario],text=True,capture_output=True,timeout=30)
  out,classes=compile_java('current')
  for scenario in ['positive','strict','default-alternate','strict-mismatch','user','old-protocol','timeout','deleted','catalog-changed']:
   r=execute(out,classes,scenario)
   if r.returncode:raise RuntimeError(scenario+'\n'+r.stdout+r.stderr)
   reports.append(json.loads(r.stdout))
  mutants=[
   ('user-override-admitted','user','GeckoTlsController.java','&&!value.hasUserMin&&!value.hasUserMax',''),
   ('pending-revision-replaces-frozen-boot','positive','GeckoTlsController.java','expected.desired.spec.isDefault()','desired.spec.isDefault()'),
   ('unclaimed-native-runtime','positive','GeckoTlsController.java','!expected.claimed||',''),
   ('profile-io-on-ui','positive','GeckoTlsController.java','    session.environmentIo.execute(()->{\n      Boot prepared','    ((java.util.concurrent.Executor)Runnable::run).execute(()->{\n      Boot prepared'),
   ('foreign-runtime-borrows-ack','positive','GeckoTlsController.java','boolean readyFor(Object actual){return ready&&readback!=null&&!retired&&runtime==actual&&boot!=null','boolean readyFor(Object actual){return ready&&readback!=null&&!retired&&boot!=null'),
   ('unrelated-profile-erasure','positive','GeckoTlsProfile.java','result.append(bytes);',''),
  ]
  for label,scenario,name,old,new in mutants:
   mutant,classes=compile_java(label,(name,old,new));r=execute(mutant,classes,scenario)
   if r.returncode==0 or 'AssertionError:'not in r.stderr:raise AssertionError('False native policy escaped: '+label+' '+r.stderr)
   negative.append({'name':label,'compileSucceeded':True,'runtimeRejected':True,'assertion':r.stderr.split('AssertionError:',1)[1].splitlines()[0].strip()})
 stable=all(sha(ROOT/k)==v for k,v in before.items())and sha(a.json_jar)==jar;checks=[name for report in reports for name in report['checks']];value=dict(schema=1,status='passed'if stable else'source-changed',passed=len(checks),total=len(checks),checks=checks,negativeControls=negative,sourceCommit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),sourceFiles=before,jsonJarSha256=jar,executionInputsUnchanged=stable,actualAndroidExecution=False,actualGeckoExecution=False,actualNativeTlsExecution=False,actualNetworkRequestsSent=False,actualSdkApiCompile=False,scope='Complete current TLS controller/profile/store/spec plus unchanged CPU storage resolver/spec and EnvironmentSpec/strictJSON/J; real filesystem, file locks/atomic moves; separate JVM cold scenarios and six separately compiled semantic false-policy mutants. Context/catalog/plain-file vault/main+IO queues and native callbacks are explicit models. No SDK or engine/native handshake proof. The controlled Android product gate remains mandatory.')
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:value[k]for k in ['status','passed','total','executionInputsUnchanged']}))
 if not stable:raise SystemExit(1)
if __name__=='__main__':main()
