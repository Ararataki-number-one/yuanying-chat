#!/usr/bin/env python3
"""Production retry class and verbatim provider job methods with a clock adapter."""
import argparse, hashlib, json, pathlib, re, subprocess
p=argparse.ArgumentParser()
p.add_argument('--java-home',required=True,type=pathlib.Path)
p.add_argument('--json-jar',required=True,type=pathlib.Path)
p.add_argument('--output',type=pathlib.Path)
a=p.parse_args()
root=pathlib.Path(__file__).resolve().parents[2]
work=root/'work/network-apply-host';classes=work/'classes';classes.mkdir(parents=True,exist_ok=True)
production=root/'app/src/main/java/local/pocketchat'
source=(production/'NetworkUiProvider.java').read_text()

def method(signature):
    start=source.index(signature);brace=source.index('{',start);end=brace+1;depth=1
    while depth:
        if source[end]=='{':depth+=1
        elif source[end]=='}':depth-=1
        end+=1
    return source[start:end]

names=['static boolean internalJob(', 'void pruneJobs(', 'void recordResult(']
methods=[method(name) for name in names]
constants=re.search(r'static final long JOB_RETENTION=\d+;static final int MAX_JOBS=\d+;',source).group(0)
generated=work/'generated/local/pocketchat/NetworkUiProvider.java';generated.parent.mkdir(parents=True,exist_ok=True)
generated.write_text('package local.pocketchat;\nimport java.util.*;import java.util.concurrent.*;import org.json.*;import android.os.SystemClock;\nfinal class NetworkUiProvider {\n'+constants+'\nfinal Map<String,JSONObject> jobs=new ConcurrentHashMap<>();\n'+'\n'.join(methods)+'\n}\n')
files=[production/'NetworkApplyRetry.java',production/'J.java',generated,*pathlib.Path(__file__).parent.rglob('*.java')]
subprocess.run([str(a.java_home/'bin/javac'),'-J-XX:ActiveProcessorCount=2','-encoding','UTF-8','-cp',str(a.json_jar),'-d',str(classes),*map(str,files)],check=True)
r=subprocess.run([str(a.java_home/'bin/java'),'-XX:ActiveProcessorCount=2','-cp',str(classes)+':'+str(a.json_jar),'local.pocketchat.NetworkApplyHostTest'],text=True,stdout=subprocess.PIPE,check=True)
result=json.loads(r.stdout);assert result['status']=='passed' and result['passed']==len(result['checks']) and all(c['pass'] is True for c in result['checks'])
result['methodSha256']={name:hashlib.sha256(value.encode()).hexdigest() for name,value in zip(names,methods)}
result['sourceSha256']=hashlib.sha256(source.encode()).hexdigest()
result['scope']='Actual retry state class and exact provider retention/retirement methods; clock adapter. No Android provider lifecycle, Gecko or route application claim.'
out=a.output or work/'results.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'passed':result['passed'],'report':str(out)}))
