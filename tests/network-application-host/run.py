#!/usr/bin/env python3
"""Run immutable production model/operation-receipt checks, without Android doubles."""
import argparse, hashlib, json, pathlib, subprocess
p=argparse.ArgumentParser();p.add_argument('--java-home',required=True,type=pathlib.Path);p.add_argument('--json-jar',required=True,type=pathlib.Path);p.add_argument('--output',type=pathlib.Path);a=p.parse_args()
root=pathlib.Path(__file__).resolve().parents[2];work=root/'work/network-application-host';classes=work/'classes';classes.mkdir(parents=True,exist_ok=True)
production=root/'app/src/main/java/local/pocketchat';files=[production/name for name in ('EnvironmentSpec.java','NetworkApplicationReceipt.java','J.java')]+[pathlib.Path(__file__).parent/'local/pocketchat/NetworkApplicationHostTest.java']
hashes={str(f.relative_to(root)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
subprocess.run([str(a.java_home/'bin/javac'),'-J-XX:ActiveProcessorCount=2','-encoding','UTF-8','-cp',str(a.json_jar),'-d',str(classes),*map(str,files)],check=True)
r=subprocess.run([str(a.java_home/'bin/java'),'-XX:ActiveProcessorCount=2','-cp',str(classes)+':'+str(a.json_jar),'local.pocketchat.NetworkApplicationHostTest'],text=True,capture_output=True,check=True)
result=json.loads(r.stdout);assert result['passed']==len(result['checks']) and all(row['pass'] is True for row in result['checks'])
result.update(sourceCommit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),sourceDirty=bool(subprocess.check_output(['git','status','--porcelain'],cwd=root,text=True)),files=hashes,scope='Actual EnvironmentSpec and NetworkApplicationReceipt methods. Runtime admission, Android lifecycle and real core verification are not exercised.')
assert all(hashlib.sha256((root/f).read_bytes()).hexdigest()==h for f,h in hashes.items())
out=a.output or work/'results.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'passed':result['passed'],'report':str(out)}))
