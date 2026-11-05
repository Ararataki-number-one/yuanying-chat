#!/usr/bin/env python3
"""Actual native header-policy methods; explicitly declared JVM SDK/app boundaries."""
import argparse,hashlib,json,pathlib,shutil,subprocess,tempfile,sys
ROOT=pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tests/gecko-navigation-host'))
from run import member_at
HERE=pathlib.Path(__file__).resolve().parent
PROD=ROOT/'app/src/main/java/local/pocketchat'
MEMBERS=['static final class HeaderPolicyRead','static boolean validRequestUserAgent(','void retireRequestHeaderPolicy(','boolean requestHeaderContextCurrent(','GeckoResult<Object> requestHeaderPolicy(']
MUTATIONS=[('revision','identityPolicyRevision!=read.revision||','', 'Late native UA cannot authorize changed revision'),('navigation','owner.navigationEpoch!=read.epoch||','', 'Late native UA cannot authorize changed navigation'),('token','nativeProtection.token()!=read.protection||','', 'Late native UA cannot authorize changed token'),('port','routePort!=read.port||','', 'Late native UA cannot authorize changed port'),('target','!identityRequestAllowed(target)||','false||', 'Every coalesced request rechecks its own target after readback'),('invalid','!validRequestUserAgent(value)','false','Invalid native UA cannot enter request headers'),('retired','headerPolicyRead!=selected||','', 'Late native UA cannot authorize changed retired'),('rfp','!metadata.rfpAcknowledged||','', 'Late native UA cannot authorize changed rfp'),('confirmed','!nativeProtection.confirmed()','false', 'Late native UA cannot authorize changed confirmed'),('private','if(!GeckoNavigationPolicy.publicWeb(target)){','if(false){','Explicit internal admission preserves its actual original SDK headers')]
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--java-home',type=pathlib.Path);p.add_argument('--json-jar',type=pathlib.Path,required=True);p.add_argument('--output',type=pathlib.Path,required=True);a=p.parse_args()
 java=lambda name:str(a.java_home/'bin'/name) if a.java_home else shutil.which(name)
 source=PROD/'GeckoWebView.java';template=HERE/'NativeHeadersHost.java.in';complete=[PROD/name for name in ['J.java','BrowserRuntimePolicy.java','BrowserAddressPolicy.java','GeckoNavigationPolicy.java']]
 files=[source,template,pathlib.Path(__file__).resolve(),ROOT/'tests/gecko-navigation-host/run.py']+complete
 hashes={str(f.relative_to(ROOT)):digest(f) for f in files};jar=digest(a.json_jar);text=source.read_text();members=[]
 for name in MEMBERS:
  if text.count(name)!=1:raise ValueError('Unique actual production method required: '+name)
  members.append(member_at(text,text.index(name)))
 body='\n'.join(members)
 def generate(value):return template.read_text().replace('@METHODS@',value.replace('WebExtension.Port','PortBoundary').replace('GeckoSession','SessionBoundary').replace('GeckoResult','ResultBoundary'))
 a.output.parent.mkdir(parents=True,exist_ok=True);artifacts=a.output.parent/(a.output.stem+'-artifacts');artifacts.mkdir(exist_ok=True);controls=[]
 with tempfile.TemporaryDirectory(prefix='gecko-native-headers-') as temporary:
  work=pathlib.Path(temporary)
  def execute(value,label,focus=None):
   out=artifacts/label;out.mkdir(exist_ok=True);host=out/'NativeHeadersHost.java';host.write_text(generate(value));classes=work/label
   command=[java('javac'),'-encoding','UTF-8','-cp',str(a.json_jar.resolve()),'-d',str(classes),str(host)]+[str(f) for f in complete]
   built=subprocess.run(command,text=True,capture_output=True,timeout=60);(out/'compile.command.json').write_text(json.dumps(command)+'\n');(out/'compile.stderr.log').write_text(built.stderr)
   if built.returncode:raise RuntimeError(built.stderr)
   command=[java('java'),'-cp',str(classes)+':'+str(a.json_jar.resolve()),'local.pocketchat.NativeHeadersHost']+([focus] if focus else [])
   run=subprocess.run(command,text=True,capture_output=True,timeout=30);(out/'run.command.json').write_text(json.dumps(command)+'\n');(out/'run.stdout.log').write_text(run.stdout);(out/'run.stderr.log').write_text(run.stderr);return run
  run=execute(body,'current')
  if run.returncode:raise RuntimeError(run.stdout+run.stderr)
  report=json.loads(run.stdout)
  for case,before,after,assertion in MUTATIONS:
   if body.count(before)!=1:raise ValueError('Exact mutation hunk required: '+case)
   pristine=execute(body,'pristine-'+case,case)
   if pristine.returncode:raise AssertionError('Pristine control failed: '+case+pristine.stderr)
   mutant=execute(body.replace(before,after,1),'mutant-'+case,case)
   if mutant.returncode==0 or 'AssertionError: '+assertion not in mutant.stderr:raise AssertionError('Precise mutation must fail: '+case+mutant.stderr)
   controls.append(dict(case=case,pristinePassed=True,mutantRejected=True,assertion=assertion))
 unchanged=all(digest(f)==hashes[str(f.relative_to(ROOT))] for f in files) and digest(a.json_jar)==jar
 report.update(sourceFiles=hashes,jsonJarSha256=jar,productionMembers=MEMBERS,negativeControls=controls,executionInputsUnchanged=unchanged,boundaries=['SDK GeckoSession/GeckoResult/WebExtension.Port type tokens replaced by explicitly controlled JVM session/result/port interfaces','Route result is an explicit native-route-admission boundary; actual proxy routing is not executed','Actual GeckoNavigationPolicy.publicWeb and real JSON serialization executed','Owner/metadata/protection counters are app state boundaries'],scope='Actual native UA readback, per-context coalescing and epoch/token/port/target rejection methods. No Android, Gecko SDK or network execution.')
 a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(dict(status=report['status'] if unchanged else 'source-changed',passed=report['passed'],negativeControls=len(controls),executionInputsUnchanged=unchanged,output=str(a.output))))
 if not unchanged:raise SystemExit(1)
if __name__=='__main__':main()
