#!/usr/bin/env python3
"""Focused source-bound production update notes/history/cache/HTTP checks."""
import argparse,hashlib,json,pathlib,subprocess,tempfile
p=argparse.ArgumentParser();p.add_argument('--java',default='java');p.add_argument('--json-jar',required=True,type=pathlib.Path);p.add_argument('--output',required=True,type=pathlib.Path);a=p.parse_args()
root=pathlib.Path(__file__).resolve().parents[2];here=pathlib.Path(__file__).resolve().parent;production=root/'app/src/main/java/local/pocketchat'
names=('ReleaseNotes','ReleaseHistoryPolicy','ReleaseHistory','AppUpdateInfo','AppUpdatePolicy','AppUpdateTransfer','Sha256')
inputs=[production/(name+'.java') for name in names]+list(here.rglob('*.java'))+[production/'AppUpdateRoute.java',here/'RouteHost.java.in',pathlib.Path(__file__).resolve()]
hashes={str(f.relative_to(root)):hashlib.sha256(f.read_bytes()).hexdigest() for f in inputs}
source=(production/'AppUpdateRoute.java').read_text();start=source.index('  static final class Factory ');brace=source.index('{',start);depth=1;end=brace+1
while depth:
 if source[end]=='{':depth+=1
 if source[end]=='}':depth-=1
 end+=1
factory=source[start:end]
with tempfile.TemporaryDirectory(prefix='update-experience-host-') as temp:
 target=pathlib.Path(temp);route=target/'AppUpdateRoute.java';route.write_text((here/'RouteHost.java.in').read_text().replace('@FACTORY@',factory))
 files=[production/(name+'.java') for name in names]+list(here.rglob('*.java'))+[route]
 compile_run=subprocess.run([a.java,'-m','jdk.compiler/com.sun.tools.javac.Main','--add-modules','jdk.httpserver','-encoding','UTF-8','-cp',str(a.json_jar),'-d',temp,*map(str,files)],text=True,capture_output=True,timeout=45)
 if compile_run.returncode:raise RuntimeError(compile_run.stdout+compile_run.stderr)
 result=subprocess.run([a.java,'--add-modules','jdk.httpserver','-cp',temp+':'+str(a.json_jar),'local.pocketchat.UpdateExperienceHost'],text=True,capture_output=True,timeout=45)
 if result.returncode:raise RuntimeError(result.stdout+result.stderr)
 report=json.loads(result.stdout)
report.update(sourceCommit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),sourceDirty=bool(subprocess.check_output(['git','status','--porcelain'],cwd=root,text=True).strip()),sourceSha256=hashes,routeFactorySha256=hashlib.sha256(factory.encode()).hexdigest(),jsonJarSha256=hashlib.sha256(a.json_jar.read_bytes()).hexdigest())
report['executionInputsUnchanged']=all(hashlib.sha256((root/f).read_bytes()).hexdigest()==sha for f,sha in hashes.items())
if report['status']!='passed' or not report['executionInputsUnchanged'] or not all(c['pass'] for c in report['checks']):raise AssertionError(report)
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'status':report['status'],'passed':report['passed'],'report':str(a.output)}))
