#!/usr/bin/env python3
"""Exercise actual production Worker guards in real desktop Chromium.

Loopback HTTP is a trustworthy local origin for the browser Service Worker API.
The test injects the exact asset before page scripts, not AndroidX document-start.
CDP is test-only; production does not enable remote debugging. Native Android
ServiceWorkerWebSettings and Worker fingerprint spoofing are not asserted here.
"""
import argparse
from collections import Counter
import hashlib
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import threading
import time
from urllib.parse import urlsplit,parse_qs

ROOT=Path(__file__).resolve().parents[2]
ASSET=ROOT/'app/src/main/assets/chromium-fingerprint.js'
PRELUDE="const existingWorker=new Worker('/worker.js?kind=prior&epoch='+location.pathname.slice(1));"
CASES=r'''
(async()=>{
 const epoch=location.pathname.slice(1),restricted=epoch==='restrict',checks=[];
 const check=(name,value)=>checks.push({name,pass:value===true});
 const timed=(promise)=>Promise.race([promise,new Promise((_,reject)=>setTimeout(()=>reject(Error('Worker fixture timeout')),5000))]);
 const ping=(worker)=>timed(new Promise((resolve,reject)=>{worker.onmessage=e=>resolve(e.data==='worker-alive');worker.onerror=()=>reject(Error('Worker native script failed'));worker.postMessage('ping')}));
 let created,denied=false;try{created=new Worker('/worker.js?kind=late&epoch='+epoch)}catch(error){denied=error.name==='SecurityError'}
 check('First page script sees the expected Dedicated Worker creation policy',restricted?denied:!!created);
 if(created){check('Allowed actual Dedicated Worker executes',await ping(created));created.terminate()}
 let moduleWorker,moduleDenied=false;try{moduleWorker=new Worker('/worker.js?kind=module&epoch='+epoch,{type:'module'})}catch(error){moduleDenied=error.name==='SecurityError'}
 check('Module Worker uses the same creation policy without a Blob wrapper',restricted?moduleDenied:!!moduleWorker);
 if(moduleWorker){check('Allowed actual module Worker executes',await ping(moduleWorker));moduleWorker.terminate()}
 check('Previously created Dedicated Worker remains executable',await ping(existingWorker));existingWorker.terminate();
 let shared,sharedDenied=false;try{shared=new SharedWorker('/shared.js?epoch='+epoch,{name:epoch})}catch(error){sharedDenied=error.name==='SecurityError'}
 check('Actual SharedWorker creation follows the requested policy',restricted?sharedDenied:!!shared);
 if(shared){check('Allowed actual SharedWorker executes',await timed(new Promise(resolve=>{shared.port.onmessage=e=>resolve(e.data==='shared-alive');shared.port.start();shared.port.postMessage('ping')})));shared.port.close()}
 let registration,registrationDenied=false;try{registration=await navigator.serviceWorker.register('/sw.js?epoch='+epoch,{scope:'/sw-scope/'})}catch(error){registrationDenied=error.name==='SecurityError'}
 check('Actual Service Worker registration follows the requested policy',restricted?registrationDenied:!!registration);
 const current=await navigator.serviceWorker.getRegistration('/sw-scope/');
 if(!current)throw Error('Existing native Service Worker registration missing');
 if(!current.active){const worker=current.installing||current.waiting;await timed(new Promise(resolve=>{worker.addEventListener('statechange',()=>{if(worker.state==='activated')resolve()});if(worker.state==='activated')resolve()}))}
 const active=current.active;if(!active)throw Error('Native Service Worker never activated');
 const channel=new MessageChannel();const alive=timed(new Promise(resolve=>{channel.port1.onmessage=e=>resolve(e.data==='service-worker-alive');channel.port1.start();active.postMessage('ping',[channel.port2])}));
 check('Existing Service Worker execution is explicitly not terminated',await alive);channel.port1.close();
 if(restricted){let escaped=false;try{new Worker.prototype.constructor('/worker.js?kind=escape&epoch='+epoch)}catch(error){escaped=error.name==='SecurityError'}check('Native constructor prototype does not bypass the page creation guard',escaped)}
 const frame=await timed(new Promise(resolve=>{addEventListener('message',function listener(event){if(event.source===child.contentWindow&&event.data?.epoch===epoch){removeEventListener('message',listener);resolve(event.data)}});const child=document.createElement('iframe');child.src='/frame?epoch='+epoch;document.body.append(child)}));
 check('Frame first script sees the same requested creation policy',frame.pass===true&&frame.mode===(restricted?'restrict':'allow'));
 await Promise.resolve();const observed=__pocketchatChromiumFingerprintObserve();
 check('Page observation reports exact Worker policy and scope',observed.workerCreation.mode===(restricted?'restrict':'allow')&&observed.workerCreation.scope==='page-frame-new-workers-only'&&observed.workerCreation.state===(restricted?'page-observed':'not-requested'));
 if(restricted)check('Page observation proves all available creation guards denied',observed.workerCreation.dedicatedCreationDenied===true&&observed.workerCreation.sharedCreationDenied===true&&observed.workerCreation.serviceRegistrationDenied===true);
 check('Observation refuses existing-execution and complete fingerprint coverage',observed.workerCreation.existingExecutionControlled===false&&observed.fingerprintProtectionVerified===false&&observed.unsupported.includes('worker')&&observed.unsupported.includes('serviceWorker'));
 finish({epoch,status:checks.every(v=>v.pass)?'passed':'failed',checks,passed:checks.filter(v=>v.pass).length,total:checks.length});
})().catch(error=>finish({epoch:location.pathname.slice(1),status:'failed',error:String(error)}));
'''
FRAME=r'''
(async()=>{const epoch=new URL(location).searchParams.get('epoch'),restricted=epoch==='restrict';let worker,denied=false;try{worker=new Worker('/worker.js?kind=frame&epoch='+epoch)}catch(error){denied=error.name==='SecurityError'}let pass=denied;if(worker){pass=await new Promise(resolve=>{worker.onmessage=e=>resolve(e.data==='worker-alive');worker.onerror=()=>resolve(false);worker.postMessage('ping')});worker.terminate()}parent.postMessage({epoch,pass:restricted?denied:pass,mode:__pocketchatChromiumFingerprintObserve().workerCreation.mode},location.origin)})()
'''
CONTROLLER=r'''
const [socketUrl,base]=process.argv.slice(1),socket=new WebSocket(socketUrl);
await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(Error('CDP socket timeout')),8000);socket.addEventListener('open',()=>{clearTimeout(timer);resolve()},{once:true});socket.addEventListener('error',reject,{once:true})});
let next=0;const pending=new Map();
socket.addEventListener('message',event=>{const value=JSON.parse(String(event.data)),wait=pending.get(value.id);if(wait){pending.delete(value.id);clearTimeout(wait.timer);value.error?wait.reject(Error(JSON.stringify(value.error))):wait.resolve(value.result)}});
function call(method,params={},sessionId){return new Promise((resolve,reject)=>{const id=++next,timer=setTimeout(()=>{pending.delete(id);reject(Error('CDP command timeout: '+method))},8000);pending.set(id,{resolve,reject,timer});socket.send(JSON.stringify({id,method,params,...(sessionId?{sessionId}:{})}))})}
try{
 const {targetId}=await call('Target.createTarget',{url:'about:blank'}),{sessionId}=await call('Target.attachToTarget',{targetId,flatten:true});await call('Page.enable',{},sessionId);
 const modes=[];
 for(const epoch of ['allow','restrict','restore']){
  await call('Page.navigate',{url:base+'/'+epoch},sessionId);const deadline=Date.now()+20000;let result;
  while(Date.now()<deadline){const value=await call('Runtime.evaluate',{expression:'document.getElementById("result")?.textContent',returnByValue:true},sessionId);if(typeof value.result?.value==='string'&&value.result.value!=='pending'){const candidate=JSON.parse(value.result.value);if(candidate.epoch===epoch){result=candidate;break}}await new Promise(resolve=>setTimeout(resolve,75))}
  if(!result)throw Error('Actual Worker '+epoch+' fixture did not complete within20s');modes.push(result);if(result.status!=='passed')break;
 }console.log(JSON.stringify({modes}));
}finally{socket.close()}
'''

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--chromium',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    paths=[ASSET,Path(__file__).resolve()];hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    source=ASSET.read_text();counts=Counter();lock=threading.Lock()
    def asset(epoch):
        config=dict(seed='1'*64,canvas=False,webgl=False,audio=False,webrtc=False,workers='restrict' if epoch=='restrict' else 'allow')
        return source.replace('__POCKETCHAT_CHROMIUM_FINGERPRINT_CONFIG__',json.dumps(config))
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*unused):pass
        def do_GET(self):
            parsed=urlsplit(self.path);query=parse_qs(parsed.query);epoch=query.get('epoch',[''])[0]
            if parsed.path in ('/allow','/restrict','/restore'):
                epoch=parsed.path[1:];kind='text/html';body='<!doctype html><meta charset="utf-8"><body><pre id="result">pending</pre><script>function finish(value){document.getElementById("result").textContent=JSON.stringify(value)}\n'+PRELUDE+'\n'+asset(epoch)+'\n'+CASES+'</script>'
            elif parsed.path=='/frame' and epoch in ('allow','restrict','restore'):
                kind='text/html';body='<!doctype html><script>'+asset(epoch)+'\n'+FRAME+'</script>'
            elif parsed.path=='/worker.js' and epoch in ('allow','restrict','restore'):
                kind='text/javascript';body='onmessage=()=>postMessage("worker-alive")';key=epoch+':worker:'+query.get('kind',[''])[0]
                with lock:counts[key]+=1
            elif parsed.path=='/shared.js' and epoch in ('allow','restrict','restore'):
                kind='text/javascript';body='onconnect=e=>{const p=e.ports[0];p.onmessage=()=>p.postMessage("shared-alive");p.start()}';
                with lock:counts[epoch+':shared']+=1
            elif parsed.path=='/sw.js' and epoch in ('allow','restrict','restore'):
                kind='text/javascript';body='// '+epoch+'\naddEventListener("install",()=>skipWaiting());addEventListener("activate",e=>e.waitUntil(clients.claim()));addEventListener("message",e=>e.ports[0]?.postMessage("service-worker-alive"));'
                with lock:counts[epoch+':service']+=1
            elif parsed.path=='/favicon.ico':self.send_response(204);self.end_headers();return
            else:self.send_error(404);return
            data=body.encode();self.send_response(200);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store');self.send_header('Service-Worker-Allowed','/');self.end_headers();self.wfile.write(data)
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    version=subprocess.check_output([str(args.chromium.resolve()),'--version'],text=True).strip()
    try:
        with tempfile.TemporaryDirectory(prefix='chromium-worker-browser-') as temporary:
            base=Path(temporary);(base/'config').mkdir();(base/'cache').mkdir()
            command=[str(args.chromium.resolve()),'--headless','--no-sandbox','--disable-dev-shm-usage','--disable-background-networking','--disable-component-update','--disable-sync','--no-first-run','--no-default-browser-check','--user-data-dir='+str(base/'profile'),'--remote-debugging-port=0','--remote-debugging-address=127.0.0.1','about:blank']
            process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=dict(os.environ,XDG_CONFIG_HOME=str(base/'config'),XDG_CACHE_HOME=str(base/'cache')),start_new_session=True)
            try:
                port_file=base/'profile/DevToolsActivePort';deadline=time.monotonic()+12
                while not port_file.is_file() and process.poll() is None and time.monotonic()<deadline:time.sleep(.1)
                if not port_file.is_file():raise RuntimeError('Actual Chromium endpoint did not start')
                port,path=port_file.read_text().splitlines()[:2]
                result=subprocess.run(['node','--input-type=module','-e',CONTROLLER,'ws://127.0.0.1:'+port+path,'http://127.0.0.1:'+str(server.server_port)],capture_output=True,text=True,timeout=75)
            finally:
                if process.poll() is None:os.killpg(process.pid,signal.SIGTERM)
                try:_,stderr=process.communicate(timeout=5)
                except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);_,stderr=process.communicate(timeout=5)
                (args.output/'chromium.stderr.log').write_text(stderr)
    finally:server.shutdown();server.server_close();thread.join(timeout=5)
    (args.output/'controller.stderr.log').write_text(result.stderr)
    if result.returncode:raise RuntimeError('Actual Chromium Worker fixture did not complete; see bounded local controller stderr')
    report=json.loads(result.stdout);modes=report['modes'];checks=[]
    def check(name,value):checks.append(dict(name=name,pass_=bool(value)))
    check('All allow/restrict/restore documents actually ran',len(modes)==3 and [m['epoch'] for m in modes]==['allow','restrict','restore'])
    for epoch in ('allow','restore'):
        for key in ('worker:prior','worker:late','worker:module','worker:frame','shared','service'):
            check('Host observed actual '+epoch+' '+key+' script request',counts[epoch+':'+key]>0)
    check('Restrict preserves previously created actual Worker',counts['restrict:worker:prior']>0)
    for key in ('worker:late','worker:module','worker:escape','worker:frame','shared','service'):
        check('Restricted '+key+' never reaches loopback host',counts['restrict:'+key]==0)
    report.update(checks=[dict(name=c['name'],**{'pass':c['pass_']}) for c in checks],requestCounts=dict(counts),version=version)
    passed=sum(m.get('passed',0) for m in modes)+sum(c['pass_'] for c in checks);total=sum(m.get('total',0) for m in modes)+len(checks)
    report.update(status='passed' if len(modes)==3 and all(m.get('status')=='passed' for m in modes) and all(c['pass_'] for c in checks) else 'failed',passed=passed,total=total,actualDesktopChromiumExecution=True,actualAndroidExecution=False,actualAndroidWebViewExecution=False,actualNativeServiceWorkerNetworkSettingExecution=False,workerFingerprintCoverageVerified=False,sourceFiles=hashes,executionInputsUnchanged=all(hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==sha for name,sha in hashes.items()),scope='Production asset before page/frame inline code in real desktop Chromium on a synthetic loopback trustworthy HTTP origin. Real Dedicated/module/Shared Worker execution and Service Worker registration, independently counted script requests, existing Worker execution and explicit allow restoration. Existing Service Worker execution is intentionally outside the page creation guard. No AndroidX document-start, Android native network-switch, server UA-CH or full Worker fingerprint-protection qualification.')
    (args.output/'results.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({key:report[key] for key in ('status','passed','total','version','executionInputsUnchanged')}))
    if report['status']!='passed' or not report['executionInputsUnchanged']:raise SystemExit(1)

if __name__=='__main__':main()
