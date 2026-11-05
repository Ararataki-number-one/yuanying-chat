#!/usr/bin/env python3
"""Exercise the production document script in actual desktop Chromium.

This supplies extra native Web API semantics coverage, never Android, UA-CH
network identity, complete fingerprint protection or performance acceptance.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import tempfile
import time

ROOT=Path(__file__).resolve().parents[2]
ASSET=ROOT/'app/src/main/assets/chromium-fingerprint.js'
PRELUDE=r'''
const nativeRead=CanvasRenderingContext2D.prototype.getImageData;
const nativeURL=HTMLCanvasElement.prototype.toDataURL;
let encoderCalls=0;
HTMLCanvasElement.prototype.toDataURL=function(){encoderCalls++;return Reflect.apply(nativeURL,this,arguments)};
'''
CASES=r'''
(async()=>{
  const checks=[];const check=(name,value)=>checks.push({name,pass:value===true});
  const equal=(a,b)=>a.length===b.length&&a.every((v,i)=>v===b[i]);
  const c=document.createElement('canvas');c.width=32;c.height=32;const x=c.getContext('2d');x.fillStyle='#517399';x.fillRect(0,0,32,32);
  const raw=nativeRead.call(x,0,0,32,32).data;
  const observed=x.getImageData(0,0,32,32).data;
  check('Actual Canvas2D readout changes without changing native pixels',!equal(raw,observed)&&equal(raw,nativeRead.call(x,0,0,32,32).data));
  check('Repeated actual readouts remain stable',equal(observed,x.getImageData(0,0,32,32).data));
  let mimeCalls=0;const mime={toString(){mimeCalls++;return'image/png'}};
  const encoded=c.toDataURL(mime);
  check('Protected PNG export invokes one actual native encoder and coerces MIME once',encoderCalls===1&&mimeCalls===1&&encoded.startsWith('data:image/png;base64,'));
  let beforeReturn=true,callbackAsync=false,callbackCount=0;
  const blob=await new Promise(resolve=>{c.toBlob(value=>{callbackAsync=!beforeReturn;callbackCount++;resolve(value)});beforeReturn=false;x.clearRect(0,0,32,32)});
  const bitmap=await createImageBitmap(blob);const decoded=document.createElement('canvas');decoded.width=32;decoded.height=32;const context=decoded.getContext('2d');context.drawImage(bitmap,0,0);bitmap.close();
  check('Actual toBlob snapshots before later drawing and preserves asynchronous callback',callbackAsync&&callbackCount===1&&equal(observed,nativeRead.call(context,0,0,32,32).data));
  let missingThrows=false,receiverThrows=false;
  try{c.getContext()}catch(error){missingThrows=error instanceof TypeError}
  try{HTMLCanvasElement.prototype.getContext.call({},'2d')}catch(error){receiverThrows=error instanceof TypeError}
  check('Actual native required argument and receiver errors remain TypeError',missingThrows&&receiverThrows);
  let coercions=0;const coordinate={valueOf(){coercions++;return 0}};x.getImageData(coordinate,0,32,32);
  check('Actual getImageData coerces a coordinate object once',coercions===1);
  c.width=16;c.height=16;x.fillStyle='#517399';x.fillRect(0,0,16,16);
  check('Actual canvas resize keeps stable readouts',equal(x.getImageData(0,0,16,16).data,x.getImageData(0,0,16,16).data));
  const blank=document.createElement('canvas');blank.toDataURL();const gl=blank.getContext('webgl');
  check('Exporting an untouched canvas leaves its context available',blank.getContext('2d')!==null||gl!==null);
  if(gl)check('Actual WebGL debug renderer extension is hidden',gl.getExtension('WEBGL_debug_renderer_info')===null&&!gl.getSupportedExtensions().includes('WEBGL_debug_renderer_info'));
  const buffer=new AudioBuffer({length:64,numberOfChannels:1,sampleRate:48000});const live=buffer.getChannelData(0);live.fill(.125);
  const copy=new Float32Array(64),again=new Float32Array(64);buffer.copyFromChannel(copy,0);buffer.copyFromChannel(again,0);
  check('Actual audio copied readouts change stably while the writable live buffer stays intact',!copy.every(v=>v===.125)&&equal(copy,again)&&buffer.getChannelData(0)===live&&live.every(v=>v===.125));
  let rtcDenied=false;try{new RTCPeerConnection()}catch(error){rtcDenied=error.name==='NotAllowedError'}
  check('Actual window WebRTC construction is denied',rtcDenied);
  const observation=__pocketchatChromiumFingerprintObserve();
  check('Actual page observation explicitly excludes complete fingerprint and Worker coverage',observation.fingerprintProtectionVerified===false&&observation.unsupported.includes('worker')&&observation.unsupported.includes('serviceWorker'));
  finish({status:checks.every(v=>v.pass)?'passed':'failed',checks,passed:checks.filter(v=>v.pass).length,total:checks.length,webglContextAvailable:!!gl});
})().catch(error=>finish({status:'failed',error:String(error)}));
'''
CONTROLLER=r'''
import {readFile} from 'node:fs/promises';
const [socketUrl,pagePath]=process.argv.slice(1),socket=new WebSocket(socketUrl);
await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(Error('CDP socket timeout')),8000);socket.addEventListener('open',()=>{clearTimeout(timer);resolve()},{once:true});socket.addEventListener('error',reject,{once:true})});
let next=0;const pending=new Map();
socket.addEventListener('message',event=>{const value=JSON.parse(String(event.data)),wait=pending.get(value.id);if(wait){pending.delete(value.id);clearTimeout(wait.timer);value.error?wait.reject(Error(JSON.stringify(value.error))):wait.resolve(value.result)}});
function call(method,params={},sessionId){return new Promise((resolve,reject)=>{const id=++next,timer=setTimeout(()=>{pending.delete(id);reject(Error('CDP command timeout: '+method))},8000);pending.set(id,{resolve,reject,timer});socket.send(JSON.stringify({id,method,params,...(sessionId?{sessionId}:{})}))})}
try{
 const {targetId}=await call('Target.createTarget',{url:'about:blank'}),{sessionId}=await call('Target.attachToTarget',{targetId,flatten:true});
 await call('Page.enable',{},sessionId);const {frameTree}=await call('Page.getFrameTree',{},sessionId);
 await call('Page.setDocumentContent',{frameId:frameTree.frame.id,html:await readFile(pagePath,'utf8')},sessionId);
 const deadline=Date.now()+20000;let result;
 while(Date.now()<deadline){const value=await call('Runtime.evaluate',{expression:'document.getElementById("result")?.textContent',returnByValue:true},sessionId);if(typeof value.result?.value==='string'&&value.result.value!=='pending'){result=JSON.parse(value.result.value);break}await new Promise(resolve=>setTimeout(resolve,100))}
 if(!result)throw Error('Native API fixture did not complete within its wall-clock budget');console.log(JSON.stringify(result));
}finally{socket.close()}
'''

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--chromium',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    sources=[ASSET,Path(__file__).resolve()];hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    policy=dict(seed='1'*64,canvas=True,webgl=True,audio=True,webrtc=True)
    script=ASSET.read_text().replace('__POCKETCHAT_CHROMIUM_FINGERPRINT_CONFIG__',json.dumps(policy))
    page='<!doctype html><meta charset="utf-8"><pre id="result">pending</pre><script>function finish(value){document.getElementById("result").textContent=JSON.stringify(value)}\n'+PRELUDE+'\n'+script+'\n'+CASES+'</script>'
    version=subprocess.check_output([str(args.chromium.resolve()),'--version'],text=True).strip()
    with tempfile.TemporaryDirectory(prefix='chromium-fingerprint-native-') as temporary:
        base=Path(temporary);source=base/'fixture.html';source.write_text(page)
        command=[str(args.chromium.resolve()),'--headless','--no-sandbox','--disable-dev-shm-usage','--disable-background-networking','--disable-component-update','--disable-sync','--no-first-run','--no-default-browser-check','--enable-unsafe-swiftshader','--user-data-dir='+str(base/'profile'),'--remote-debugging-port=0','--remote-debugging-address=127.0.0.1','about:blank']
        environment=dict(os.environ,XDG_CONFIG_HOME=str(base/'config'),XDG_CACHE_HOME=str(base/'cache'))
        (base/'config').mkdir();(base/'cache').mkdir()
        process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=environment,start_new_session=True)
        try:
            port_file=base/'profile/DevToolsActivePort';deadline=time.monotonic()+12
            while not port_file.is_file() and process.poll() is None and time.monotonic()<deadline:time.sleep(.1)
            if not port_file.is_file():raise RuntimeError('Actual Chromium debugging endpoint did not start')
            port,path=port_file.read_text().splitlines()[:2]
            result=subprocess.run(['node','--input-type=module','-e',CONTROLLER,'ws://127.0.0.1:'+port+path,str(source)],capture_output=True,text=True,timeout=40)
        finally:
            if process.poll() is None:os.killpg(process.pid,signal.SIGTERM)
            try:stdout,stderr=process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid,signal.SIGKILL);stdout,stderr=process.communicate(timeout=5)
            (args.output/'chromium.stderr.log').write_text(stderr)
    (args.output/'controller.stderr.log').write_text(result.stderr)
    if result.returncode:raise RuntimeError('Actual Chromium fixture did not complete; inspect local controller stderr log')
    report=json.loads(result.stdout)
    report.setdefault('passed',0);report.setdefault('total',0)
    report.update(sourceCommit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),sourceTree=subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=ROOT,text=True).strip())
    report.update(actualDesktopChromiumExecution=True,actualAndroidExecution=False,actualAndroidWebViewExecution=False,actualDevicePerformanceMeasurement=False,actualNetworkIdentityVerification=False,version=version,sourceFiles=hashes,executionInputsUnchanged=all(hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==sha for name,sha in hashes.items()),scope='Production document script executed against actual desktop Chromium Canvas2D/PNG/Blob/AudioBuffer/WebGL/window WebRTC APIs. CDP supplies a synthetic opaque-origin document with a fixed test seed, without network navigation; no Android document-start feature, native UA metadata, controlled HTTPS or full fingerprint guarantee.')
    (args.output/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({key:report[key] for key in ('status','passed','total','version','executionInputsUnchanged')}))
    if report['status']!='passed' or not report['executionInputsUnchanged']:raise SystemExit(1)

if __name__=='__main__':main()
