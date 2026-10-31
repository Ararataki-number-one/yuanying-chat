#!/usr/bin/env python3
"""Run extracted production ChatSession guards with declared non-Android boundaries."""
import argparse,datetime,hashlib,json,pathlib,subprocess,uuid
p=argparse.ArgumentParser();p.add_argument('--json-jar',required=True,type=pathlib.Path);p.add_argument('--java-home',required=True,type=pathlib.Path);a=p.parse_args()
root=pathlib.Path(__file__).resolve().parents[2];prod=root/'app/src/main/java/local/pocketchat';work=root/'work/experience46-guards-host';attempt=work/(datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+uuid.uuid4().hex[:8]);classes=attempt/'classes';classes.mkdir(parents=True)
source=(prod/'ChatSession.java').read_text()
def member(start):
 at=source.index(start);brace=source.index('{',at);depth=1;i=brace+1;quote=None;escape=False;line=False;block=False
 while depth:
  c=source[i];n=source[i+1:i+2]
  if line:
   if c=='\n':line=False
  elif block:
   if c=='*' and n=='/':block=False;i+=1
  elif quote:
   if escape:escape=False
   elif c=='\\':escape=True
   elif c==quote:quote=None
  elif c=='/' and n=='/':line=True;i+=1
  elif c=='/' and n=='*':block=True;i+=1
  elif c in ['"',"'"]:quote=c
  elif c=='{':depth+=1
  elif c=='}':depth-=1
  i+=1
 return source[at:i]
needles=['boolean uploading(','boolean currentReplyActive(','boolean resourceFilesUncertain(','boolean fileWorkActive(','boolean resourceFilesActive(','void resourceObserverConnected(','void resourceObserverDisconnected(','boolean resourceBindingMatches(','void resourceObserverRouteReady(','void resourceWebsiteObservation(','boolean resourceObservationCurrent(','TaskGuardSnapshot taskGuardSnapshot(','TaskGuardSnapshot unknownTaskGuardSnapshot(','void requestTaskGuardStatus(','boolean replyObservationAllowed(','void replyObservationPolicyChanged(','long beginNetworkApplication(','boolean adoptNetworkApplication(','void wakePolling(','void evaluateDriver(']
observer=(prod/'WebReplyObserver.java').read_text();assert 'session.webWorkGeneration++;session.resourceObservedAt=0;' in observer,'Trusted intent boundary changed; review fixture instead of silently updating it'
body='\n'.join(member(n) for n in needles).replace('System.currentTimeMillis()','Clock.wallMillis()')
fixture=attempt/'GuardHost.java';fixture.write_text((pathlib.Path(__file__).parent/'GuardHost.java.in').read_text().replace('@PRODUCTION_MEMBERS@',body))
commands=[[str(a.java_home/'bin/javac'),'-encoding','UTF-8','-cp',str(a.json_jar),'-d',str(classes),str(prod/'J.java'),str(prod/'TaskGuardSnapshot.java'),str(prod/'BrowserSettingsPolicy.java'),str(fixture)],[str(a.java_home/'bin/java'),'-cp',str(classes)+':'+str(a.json_jar),'local.pocketchat.GuardHost']]
for i,cmd in enumerate(commands):
 result=subprocess.run(cmd,text=True,capture_output=True);(attempt/f'{i}.command.json').write_text(json.dumps(cmd,ensure_ascii=False)+'\n');(attempt/f'{i}.stdout.log').write_text(result.stdout);(attempt/f'{i}.stderr.log').write_text(result.stderr)
 if i==0 and result.returncode:print(result.stderr);raise SystemExit(result.returncode)
 if i==1:
  report=json.loads(result.stdout);report['productionSourceSha256']={n:hashlib.sha256((prod/n).read_bytes()).hexdigest() for n in ['ChatSession.java','TaskGuardSnapshot.java','BrowserSettingsPolicy.java','WebReplyObserver.java']};report['members']=needles;report['boundarySubstitutions']=['System.currentTimeMillis() → Clock.wallMillis()','SystemClock/Handler/Looper virtual clock and explicit callback queues','Gecko evaluation/document port/browser visibility/proof and activity-policy hooks are doubles','Trusted intent invalidation is a source-checked native-event boundary; WebReplyObserver.receive is not executed'];report['attempt']=str(attempt);(attempt/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');(work/'latest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'status':report['status'],'passed':report['passed'],'total':report['total'],'failed':[c['name'] for c in report['checks'] if not c['pass']],'attempt':str(attempt)},ensure_ascii=False));raise SystemExit(result.returncode)
