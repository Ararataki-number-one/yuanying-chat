#!/usr/bin/env python3
import hashlib,importlib.util,json,pathlib,time,traceback
p=pathlib.Path(__file__).resolve().parent;root=p.parent
spec=importlib.util.spec_from_file_location('whole_core_bench',root/'run.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
originalCore=m.CORE;m.OUT=p;m.CORE=p/'launch.py';(p/'fixtures').mkdir(exist_ok=True);
for name in ['serve.py','benchmark.py']:(p/'fixtures'/name).write_bytes((root/'fixtures'/name).read_bytes())
fixture=m.Fixture();core=None;out={'schema':1,'focusedActualUnifiedDelay':True,'fullLinuxProcess':True,'passed':False,'coreSha256':m.sha(originalCore),'patchSha256':m.PATCH,'wanOrAndroidClaim':False}
try:
 core=m.Core(fixture,'production-true',True);assert pathlib.Path('/proc/'+str(core.proc.pid)+'/exe').resolve()==originalCore.resolve();assert json.loads((core.root/'config.json').read_text())['unified-delay'];out['configSha256']=m.sha(core.root/'config.json');seedbefore=fixture.snapshot();seed=core.request(fixture);out['seed']=m.bind_wire(fixture,seedbefore,fixture.snapshot(),seed)
 def ready():
  rows=fixture.snapshot();slots=m.ready_sockets(rows)
  if slots:time.sleep(.03);return fixture.snapshot()
 before=m.until(ready);ids=set(m.ready_sockets(before));assert len(ids)==1
 response=core.api('/proxies/FixedExit/delay?url='+m.urllib.parse.quote(fixture.ready['target']['url'],safe='')+'&timeout=5000');after=fixture.snapshot();out['response']=response;out['readySocketsBefore']=sorted(ids);out['readySocketsAfter']=sorted(m.ready_sockets(after));out['newWireEvents']=after[len(before):]
 assert ids==set(m.ready_sockets(after));trace=response['probe'];assert trace['firstMs']>=180 and trace['warmAttempted'] and trace['warmSucceeded'] and trace['dialCount']==2 and trace['attempts']==2 and not trace['secondConnectionReused'] and trace['kind']=='cold-retest'
 newexits={r['socket'] for r in out['newWireEvents'] if r['socket'].startswith('exit-') and r['phase']=='accepted'};auth={r['socket'] for r in out['newWireEvents'] if r['socket'].startswith('exit-') and r['phase']=='auth-sent'};connect={r['socket'] for r in out['newWireEvents'] if r['socket'].startswith('exit-') and r['phase']=='connect-received'};assert len(newexits)==2 and newexits==auth==connect and not newexits&ids
 out['newProbeExitSockets']=sorted(newexits);out['passed']=True
except Exception:
 out['failure']=traceback.format_exc();raise
finally:
 out['allWireEvents']=fixture.snapshot()
 if core:core.stop()
 fixture.stop();(p/'results.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({'passed':out['passed'],'response':out['response'],'readySocketPreserved':out['readySocketsBefore']}))
