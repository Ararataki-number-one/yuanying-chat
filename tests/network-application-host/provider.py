#!/usr/bin/env python3
"""Exact production waiter; explicit model/transport/looper adapters, no Android claim."""
import argparse,hashlib,json,pathlib,subprocess
p=argparse.ArgumentParser();p.add_argument('--java-home',type=pathlib.Path,required=True);p.add_argument('--json-jar',type=pathlib.Path,required=True);p.add_argument('--output',type=pathlib.Path,required=True);p.add_argument('--before-ref');a=p.parse_args()
r=pathlib.Path(__file__).resolve().parents[2];prod=r/'app/src/main/java/local/pocketchat';work=r/'work/network-application-provider-host';work.mkdir(parents=True,exist_ok=True)
src=(prod/'NetworkUiProvider.java').read_text()
def extract(name,text=src):
 s=text.index(name);pos=text.index('{',s)+1;depth=1
 while depth:
  depth+=(text[pos]=='{')-(text[pos]=='}');pos+=1
 return text[s:pos]
names=['static final class RequestBinding {','static final class Choice {','void requireChoice(','void resolveChoice(','static JSONObject operationOutcome(RequestBinding binding,Transition transition,String id,String message)','static final class ApplicationAttempt {','boolean owns(Transition transition)','boolean applicationCurrent(ApplicationAttempt attempt)','boolean applicationRouteReady(ApplicationAttempt attempt)','void waitConnection(String id,ChatSession s,NativeNetwork n,boolean saved,long began)','void pollApplication(ApplicationAttempt attempt)','void completeSessionApplication(ApplicationAttempt attempt)']
methods=[extract(n) for n in names];before_source=None
if a.before_ref:
 before_source=subprocess.check_output(['git','show',a.before_ref+':app/src/main/java/local/pocketchat/NetworkUiProvider.java'],cwd=r,text=True);key='void waitConnection(String id,ChatSession s,NativeNetwork n,boolean saved,long began)';methods[names.index(key)]=extract(key,before_source)
generated=work/'ProviderApplication.java';template=pathlib.Path(__file__).with_name('ProviderApplication.java.in');window=(prod/'WindowNetworkState.java').read_text();running=extract('static JSONObject running(ChatSession s,NativeNetwork n)',window);generated.write_text(template.read_text().replace('@METHODS@','\n'.join(methods)).replace('@RUNNING@',running))
files=[prod/'EnvironmentSpec.java',prod/'NetworkApplicationReceipt.java',prod/'J.java',generated,pathlib.Path(__file__).parent/'local/pocketchat/NetworkApplicationProviderTest.java'];
if a.before_ref: files.append(pathlib.Path(__file__).parent/'local/pocketchat/NetworkApplicationLegacyTest.java')
classes=work/'classes';classes.mkdir(exist_ok=True)
subprocess.run([str(a.java_home/'bin/javac'),'-J-XX:ActiveProcessorCount=2','-encoding','UTF-8','-cp',str(a.json_jar),'-d',str(classes),*map(str,files)],check=True)
run=subprocess.check_output([str(a.java_home/'bin/java'),'-XX:ActiveProcessorCount=2','-cp',str(classes)+':'+str(a.json_jar),'local.pocketchat.'+('NetworkApplicationLegacyTest' if a.before_ref else 'NetworkApplicationProviderTest')],text=True)
result=json.loads(run)
if a.before_ref:
 assert result['status']=='expected-baseline-failure' and result['falseSuccessReproduced'] is True;result['baselineRef']=a.before_ref;result['baselineProviderSha256']=hashlib.sha256(before_source.encode()).hexdigest()
else: assert result['status']=='passed' and result['passed']==len(result['checks']) and all(c['pass'] for c in result['checks'])
result['sourceCommit']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=r,text=True).strip();result['dirty']=bool(subprocess.check_output(['git','status','--porcelain'],cwd=r,text=True));result['runningSummarySha256']=hashlib.sha256(running.encode()).hexdigest();result['windowSourceSha256']=hashlib.sha256(window.encode()).hexdigest();result['productionProviderSha256']=hashlib.sha256(src.encode()).hexdigest();result['methodsSha256']={n:hashlib.sha256(m.encode()).hexdigest() for n,m in zip(names,methods)};result['filesSha256']={str(f.relative_to(r)):hashlib.sha256(f.read_bytes()).hexdigest() for f in [*files[:-2],files[-1],template,pathlib.Path(__file__)]};result['scope']='Exact production application waiter and immutable EnvironmentSpec/receipt with explicit session/model/service/looper adapters. Simulated fresh IPC outcomes; no Android, actual core, real service, storage locks or Gecko execution claim.'
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'status':result['status'],'passed':result.get('passed'),'output':str(a.output)}))
