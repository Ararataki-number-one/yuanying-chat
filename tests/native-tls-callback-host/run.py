#!/usr/bin/env python3
"""Actual current TLS fixture navigation helper and terminal dispatch, with opaque session ownership."""
import argparse,hashlib,json,os,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tests/gecko-navigation-host'))
from run import member_at
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--java-home',type=Path,required=True);p.add_argument('--json-jar',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 fixture=ROOT/'tests/gecko/NativeTlsProbeActivity.java';raw=fixture.read_text();parts={}
 for key,needle in [('NAVIGATION','static final class TrialNavigation {'),('DISPATCH','void callback(TrialNavigation actual,int index,int action)')]:
  if raw.count(needle)!=1:raise ValueError('Unique current actual callback source required: '+needle)
  parts[key]=member_at(raw,raw.index(needle))
 # The complete actual Activity is compiled separately against the real pinned SDK.
 # These exact call sites bind the tested helper to native delegates; no copied old helper is accepted.
 for call in ['actual.location(location)','actual.error(location,error.category,error.code)','actual.title(title)','actual.start(location)','actual.security(info.host,info.isSecure,info.isException,actualLeaf)','actual.stop(success)','navigation.owns(value,index,session,trial,value!=null&&value.isOpen(),done,closed,restoring)']:
  if raw.count(call)!=1:raise ValueError('Current native SDK callback/helper binding differs: '+call)
 files=[fixture,HERE/'Host.java.in',Path(__file__).resolve(),ROOT/'tests/gecko-navigation-host/run.py',ROOT/'app/src/main/java/local/pocketchat/J.java'];before={str(p.relative_to(ROOT)):sha(p)for p in files};jar=sha(a.json_jar)
 with tempfile.TemporaryDirectory(prefix='native-tls-callback-host-')as folder:
  base=Path(folder)
  def execute(label,chosen):
   out=base/label;out.mkdir();text=(HERE/'Host.java.in').read_text()
   for key,value in chosen.items():text=text.replace('@@'+key+'@@',value)
   source=out/'Host.java';source.write_text(text);classes=out/'classes'
   c=subprocess.run([str(a.java_home/'bin/javac'),'-encoding','UTF-8','-cp',str(a.json_jar),'-d',str(classes),str(source),str(ROOT/'app/src/main/java/local/pocketchat/J.java')],capture_output=True,text=True,timeout=30)
   if c.returncode:raise RuntimeError('Actual callback helper compile failed: '+c.stderr)
   return subprocess.run([str(a.java_home/'bin/java'),'-cp',str(classes)+os.pathsep+str(a.json_jar),'local.pocketchat.Host'],capture_output=True,text=True,timeout=30)
  current=execute('current',parts)
  if current.returncode:raise RuntimeError(current.stdout+current.stderr)
  report=json.loads(current.stdout);negative=[]
  mutants=[('borrowed-stop','NAVIGATION','row.put("stopCallbacks",stops).put("successfulStopCallbacks",successfulStops);return NONE;','row.put("stopCallbacks",stops).put("successfulStopCallbacks",successfulStops);return TLS_READY;'),('missing-title','NAVIGATION','&&row.optBoolean("titleMatched")',''),('foreign-session','NAVIGATION','supplied==owner','true'),('wrong-callback-trial','NAVIGATION','callbackIndex==index','true'),('foreign-error-uri','NAVIGATION','if(!target.equals(url))','if(false)'),('certificate-error-as-ssl','NAVIGATION','&&code==sslCode',''),('foreign-dispatch','DISPATCH','actual!=navigation||','')]
  for label,key,old,new in mutants:
   if parts[key].count(old)!=1:raise ValueError('Unique actual semantic counterexample required: '+label)
   selected=dict(parts);selected[key]=selected[key].replace(old,new,1);bad=execute(label,selected)
   if bad.returncode==0 or 'AssertionError:'not in bad.stderr:raise AssertionError('False callback proof escaped: '+label+' '+bad.stderr)
   negative.append(dict(name=label,compileSucceeded=True,runtimeRejected=True,assertion=bad.stderr.split('AssertionError:',1)[1].splitlines()[0].strip()))
 stable=all(sha(ROOT/k)==v for k,v in before.items())and sha(a.json_jar)==jar
 report.update(schema=1,sourceCommit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),sourceFiles=before,extractedMethodsSha256={k:hashlib.sha256(v.encode()).hexdigest()for k,v in parts.items()},jsonJarSha256=jar,executionInputsUnchanged=stable,negativeControls=negative,actualAndroidExecution=False,actualGeckoExecution=False,actualSdkApiCompile=False,actualNativeTlsExecution=False,actualNetworkRequestsSent=False,scope='Verbatim current TrialNavigation and actual terminal callback dispatch; exact native delegate call sites checked. Session objects/liveness and callback events are explicit host inputs. SDK stop callbacks have no URL and cannot establish target readiness. No Android/Gecko/TLS wire claim; independent real SDK compile and real four-peer Android/wire diagnostic remain required.')
 if not stable:report['status']='source-changed'
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:report[k]for k in ['status','passed','total','executionInputsUnchanged']}))
 if not stable:raise SystemExit(1)
if __name__=='__main__':main()
