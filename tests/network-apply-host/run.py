#!/usr/bin/env python3
"""Production retry/observer/job methods with explicit page/clock adapters and real threads."""
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

def method(signature,text=source):
    start=text.index(signature);brace=text.index('{',start);end=brace+1;depth=1
    while depth:
        if text[end]=='{':depth+=1
        elif text[end]=='}':depth-=1
        end+=1
    return text[start:end]

names=['static boolean internalJob(', 'void pruneJobs(', 'void recordResult(String id,boolean ok,String message){', 'void recordResult(String id,boolean ok,String message,JSONObject operationResult){', 'void observeSession(', 'void sessionChanged(']
methods=[method(name) for name in names]
constants=re.search(r'static final long JOB_RETENTION=\d+;static final int MAX_JOBS=\d+;',source).group(0)
generated=work/'generated/local/pocketchat/NetworkUiProvider.java';generated.parent.mkdir(parents=True,exist_ok=True)
generated.write_text('package local.pocketchat;\nimport java.util.*;import java.util.concurrent.*;import org.json.*;import android.os.SystemClock;\nfinal class NetworkUiProvider {\n'+constants+'''
final Map<String,JSONObject> jobs;
NetworkUiProvider(){this(new ConcurrentHashMap<>());}
NetworkUiProvider(Map<String,JSONObject> jobs){this.jobs=jobs;}
final NetworkApplyRetry retry=new NetworkApplyRetry();
ChatSession observedSession;final ChatSession.Observer sessionObserver=this::sessionChanged;
final Runnable pendingWake=this::drainPending;final PendingHandler main=new PendingHandler();
boolean maintenanceStopped;int drains;void drainPending(){drains++;}
'''+ '\n'.join(methods)+'\n}\n')
chat_source=(production/'ChatSession.java').read_text()
chat_methods=[method(signature,chat_source) for signature in ['void add(Observer o)', 'void remove(Observer o)']]
observation=work/'generated/local/pocketchat/ProviderObservation.java'
observation.write_text((pathlib.Path(__file__).parent/'ProviderObservation.java.in').read_text().replace('@CHAT_OBSERVER_METHODS@','\n'.join(chat_methods)))
files=[production/'NetworkApplyRetry.java',production/'J.java',generated,observation,*pathlib.Path(__file__).parent.rglob('*.java')]
subprocess.run([str(a.java_home/'bin/javac'),'-J-XX:ActiveProcessorCount=2','-encoding','UTF-8','-cp',str(a.json_jar),'-d',str(classes),*map(str,files)],check=True)
r=subprocess.run([str(a.java_home/'bin/java'),'-XX:ActiveProcessorCount=2','-cp',str(classes)+':'+str(a.json_jar),'local.pocketchat.NetworkApplyHostTest'],text=True,stdout=subprocess.PIPE,check=True)
result=json.loads(r.stdout);assert result['status']=='passed' and result['passed']==len(result['checks']) and all(c['pass'] is True for c in result['checks'])
result['methodSha256']={name:hashlib.sha256(value.encode()).hexdigest() for name,value in zip(names,methods)}
result['sourceSha256']=hashlib.sha256(source.encode()).hexdigest()
result['retrySourceSha256']=hashlib.sha256((production/'NetworkApplyRetry.java').read_bytes()).hexdigest()
result['fixtureSha256']={str(path.relative_to(root)):hashlib.sha256(path.read_bytes()).hexdigest() for path in [pathlib.Path(__file__),pathlib.Path(__file__).parent/'ProviderObservation.java.in',*pathlib.Path(__file__).parent.rglob('*.java')]}
result['chatObserverSourceSha256']=hashlib.sha256(chat_source.encode()).hexdigest()
result['chatObserverMethodsSha256']=[hashlib.sha256(value.encode()).hexdigest() for value in chat_methods]
result['scope']='Actual retry class and exact provider observer/retention/retirement methods plus ChatSession add/remove; explicit page/looper/clock adapters and two real threads. No Android provider lifecycle, Gecko or route application claim.'
out=a.output or work/'results.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'passed':result['passed'],'report':str(out)}))
