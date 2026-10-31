#!/usr/bin/env python3
"""Complete production Client bound metadata through explicit Android/Messenger adapters."""
import argparse,hashlib,json,pathlib,subprocess,tempfile
p=argparse.ArgumentParser();p.add_argument('--java-home',required=True,type=pathlib.Path);p.add_argument('--json-jar',required=True,type=pathlib.Path);p.add_argument('--output',required=True,type=pathlib.Path);a=p.parse_args();a.output.parent.mkdir(parents=True,exist_ok=True)
r=pathlib.Path(__file__).resolve().parents[2];d=r/'app/src/main/java/local/pocketchat';h=r/'tests/network-transport-client-host';here=pathlib.Path(__file__).parent
files=[d/x for x in ('NetworkTransportClient.java','EnvironmentSpec.java','J.java')]+[h/'NetworkTransportClientHost.java',here/'BoundClientHost.java',*sorted((h/'adapters').rglob('*.java'))]
input_hashes={str(x.relative_to(r)):hashlib.sha256(x.read_bytes()).hexdigest() for x in [*files,pathlib.Path(__file__)]}
with tempfile.TemporaryDirectory(prefix='bound-network-client-') as temp:
 subprocess.run([str(a.java_home/'bin/javac'),'-J-XX:ActiveProcessorCount=2','-encoding','UTF-8','-cp',str(a.json_jar),'-d',temp,*map(str,files)],check=True)
 run=subprocess.run([str(a.java_home/'bin/java'),'-XX:ActiveProcessorCount=2','-cp',temp+':'+str(a.json_jar),'local.pocketchat.BoundClientHost'],capture_output=True,text=True)
 a.output.with_suffix('.stdout.log').write_text(run.stdout);a.output.with_suffix('.stderr.log').write_text(run.stderr);run.check_returncode();result=json.loads(run.stdout);assert result['passed']==len(result['checks']) and all(x['pass'] for x in result['checks'])
assert all(hashlib.sha256((r/name).read_bytes()).hexdigest()==digest for name,digest in input_hashes.items()),'Executed client inputs changed during host run'
result.update(executionInputsUnchanged=True,sourceCommit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=r,text=True).strip(),sourceDirty=bool(subprocess.check_output(['git','status','--porcelain'],cwd=r,text=True)),filesSha256=input_hashes,scope='Full production NetworkTransportClient plus owner model and explicit Android Messenger/Looper adapters. No Android/Binder/service or real core execution claim.')
a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'status':result['status'],'passed':result['passed'],'report':str(a.output)}))
