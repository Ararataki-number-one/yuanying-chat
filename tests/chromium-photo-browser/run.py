#!/usr/bin/env python3
"""Actual browser file selection and independent PNG receiver for the production canvas guard."""
import argparse
import hashlib
import http.server
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/browser'))
sys.path.insert(0,str(ROOT/'tools/gecko'))
from chromium_process import chromium_endpoint
from photo_upload_contract import WIDTH,HEIGHT,expected_rgba,decode_png
ASSET=ROOT/'app/src/main/assets/chromium-fingerprint.js'
CASES={'original':True,**{f'{kind}-{encoding}':kind in ('bitmap','object-url','file-reader','canvas-chain')
  for kind in ('bitmap','object-url','file-reader','canvas-chain','synthetic-file','mixed-drawing','fingerprint') for encoding in ('blob','url')}}
PAGE=r'''
const nativeRead=CanvasRenderingContext2D.prototype.getImageData;
__GUARD__
const selected=document.getElementById('photo'),checks=[];
const check=(name,pass)=>{checks.push({name,pass:pass===true});if(!pass)throw Error(name)};
const equal=(a,b)=>a.length===b.length&&a.every((value,i)=>value===b[i]);
const asData=blob=>new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=reject;reader.readAsDataURL(blob)});
const image=url=>new Promise((resolve,reject)=>{const value=new Image();value.onload=()=>resolve(value);value.onerror=reject;value.src=url});
const canvas=source=>{const value=document.createElement('canvas');value.width=64;value.height=48;value.getContext('2d').drawImage(source,0,0);return value};
const send=async(name,blob)=>{const response=await fetch('/received?name='+encodeURIComponent(name),{method:'POST',body:blob});if(!response.ok)throw Error('independent receiver rejected '+name);};
const exports=async(name,value,photo)=>{
 const ctx=value.getContext('2d'),raw=nativeRead.call(ctx,0,0,64,48).data,read=ctx.getImageData(0,0,64,48).data;
 check(name+' readback policy',equal(raw,read)===photo);
 await send(name+'-blob',await new Promise(resolve=>value.toBlob(resolve,'image/png')));
 await send(name+'-url',await (await fetch(value.toDataURL('image/png'))).blob());
};
selected.addEventListener('change',async event=>{
 if(!event.isTrusted)return;
 try{
  check('browser-originated file selection',event.isTrusted&&selected.files.length===1);
  const file=selected.files[0];await send('original',file);
  const bitmap=await createImageBitmap(file),first=canvas(bitmap);await exports('bitmap',first,true);
  const url=URL.createObjectURL(file),objectImage=await image(url);URL.revokeObjectURL(url);await exports('object-url',canvas(objectImage),true);
  await exports('file-reader',canvas(await image(await asData(file))),true);
  await exports('canvas-chain',canvas(first),true);
  const synthetic=new File([await file.arrayBuffer()],'synthetic.png',{type:'image/png'}),transfer=new DataTransfer();transfer.items.add(synthetic);selected.files=transfer.files;selected.dispatchEvent(new Event('change',{bubbles:true}));
  await exports('synthetic-file',canvas(await createImageBitmap(synthetic)),false);
  const mixed=canvas(bitmap);mixed.getContext('2d').fillStyle='red';mixed.getContext('2d').fillText('probe',2,20);await exports('mixed-drawing',mixed,false);
  const probe=document.createElement('canvas');probe.width=64;probe.height=48;const ctx=probe.getContext('2d');ctx.fillStyle='#517399';ctx.fillRect(0,0,64,48);await exports('fingerprint',probe,false);
  check('all targeted image workflows and protection controls completed',checks.length===8);
  document.getElementById('result').textContent=JSON.stringify({status:'passed',checks});
 }catch(error){document.getElementById('result').textContent=JSON.stringify({status:'failed',error:String(error),checks});}
});
'''
CONTROLLER=r'''
const [endpoint,url,file]=process.argv.slice(1),socket=new WebSocket(endpoint),pending=new Map();let next=0;
await new Promise((resolve,reject)=>{socket.addEventListener('open',resolve,{once:true});socket.addEventListener('error',reject,{once:true})});
socket.addEventListener('message',event=>{const value=JSON.parse(String(event.data)),entry=pending.get(value.id);if(entry){pending.delete(value.id);clearTimeout(entry.timer);value.error?entry.reject(Error(JSON.stringify(value.error))):entry.resolve(value.result)}});
function call(method,params={},sessionId){return new Promise((resolve,reject)=>{const id=++next,timer=setTimeout(()=>reject(Error('CDP deadline '+method)),8000);pending.set(id,{resolve,reject,timer});socket.send(JSON.stringify({id,method,params,...(sessionId?{sessionId}:{})}))})}
try{
 const {targetId}=await call('Target.createTarget',{url:'about:blank'}),{sessionId}=await call('Target.attachToTarget',{targetId,flatten:true});
 await call('Page.enable',{},sessionId);await call('Page.navigate',{url},sessionId);
 const until=Date.now()+20000;let ready=false;
 while(Date.now()<until){const v=await call('Runtime.evaluate',{expression:'!!document.getElementById("photo")&&typeof selected!=="undefined"',returnByValue:true},sessionId);if(v.result?.value===true){ready=true;break}await new Promise(r=>setTimeout(r,50))}
 if(!ready)throw Error('Photo fixture failed to load');
 const {root}=await call('DOM.getDocument',{},sessionId),{nodeId}=await call('DOM.querySelector',{nodeId:root.nodeId,selector:'#photo'},sessionId);
 await call('DOM.setFileInputFiles',{nodeId,files:[file]},sessionId);let result;
 while(Date.now()<until){const v=await call('Runtime.evaluate',{expression:'document.getElementById("result").textContent',returnByValue:true},sessionId);if(v.result?.value&&v.result.value!=='pending'){result=JSON.parse(v.result.value);break}await new Promise(r=>setTimeout(r,50))}
 if(!result)throw Error('Photo fixture failed to complete');console.log(JSON.stringify(result));
}finally{socket.close()}
'''

def png_fixture():
 def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
 pixels=expected_rgba();rows=b''.join(b'\0'+pixels[y*WIDTH*4:(y+1)*WIDTH*4] for y in range(HEIGHT))
 return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',WIDTH,HEIGHT,8,6,0,0,0))+chunk(b'IDAT',zlib.compress(rows))+chunk(b'IEND',b'')

def firefox_run(args,url,photo,output):
 with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
 with (output/'geckodriver.log').open('w') as log:
  process=subprocess.Popen([str(args.geckodriver),'--port',str(port)],stdout=log,stderr=log)
  def command(method,path,data=None):
   request=urllib.request.Request(f'http://127.0.0.1:{port}'+path,data=None if data is None else json.dumps(data).encode(),headers={'Content-Type':'application/json'},method=method)
   try:
    with urllib.request.urlopen(request,timeout=30) as response:return json.load(response)['value']
   except urllib.error.HTTPError as error:raise RuntimeError(error.read().decode())
  sid=None
  try:
   until=time.monotonic()+10
   while True:
    try:command('GET','/status');break
    except OSError:
     if time.monotonic()>until:raise
     time.sleep(.05)
   created=command('POST','/session',{'capabilities':{'alwaysMatch':{'browserName':'firefox','moz:firefoxOptions':{'binary':str(args.firefox.resolve()),'args':['-headless'],'prefs':{'privacy.resistFingerprinting':False,'network.proxy.type':0}}}}})
   sid=created['sessionId'];prefix='/session/'+sid
   command('POST',prefix+'/url',{'url':url})
   element=command('POST',prefix+'/element',{'using':'css selector','value':'#photo'})['element-6066-11e4-a52e-4f735466cecf']
   command('POST',prefix+'/element/'+element+'/value',{'text':str(photo)})
   until=time.monotonic()+20
   while time.monotonic()<until:
    raw=command('POST',prefix+'/execute/sync',{'script':'return document.getElementById("result").textContent','args':[]})
    if raw!='pending':return json.loads(raw),created['capabilities']['browserVersion']
    time.sleep(.05)
   raise RuntimeError('Firefox script fixture deadline')
  finally:
   if sid:
    try:command('DELETE','/session/'+sid)
    except Exception:pass
   process.terminate();process.wait(timeout=5)

def main():
 parser=argparse.ArgumentParser(description=__doc__);engines=parser.add_mutually_exclusive_group(required=True)
 engines.add_argument('--chromium',type=Path);engines.add_argument('--firefox',type=Path)
 parser.add_argument('--geckodriver',type=Path);parser.add_argument('--output',required=True,type=Path)
 args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
 policy=dict(seed='1'*64,canvas=True,webgl=False,audio=False,webrtc=False)
 page=('<!doctype html><meta charset="utf-8"><input type="file" id="photo"><pre id="result">pending</pre><script>'+PAGE.replace('__GUARD__',ASSET.read_text().replace('__POCKETCHAT_CHROMIUM_FINGERPRINT_CONFIG__',json.dumps(policy)))+'</script>').encode()
 receipts={};errors=[]
 class Handler(http.server.BaseHTTPRequestHandler):
  def log_message(self,*args):pass
  def do_GET(self):
   self.send_response(200);self.send_header('Content-Type','text/html;charset=utf-8');self.send_header('Content-Length',str(len(page)));self.end_headers();self.wfile.write(page)
  def do_POST(self):
   try:
    name=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)['name'][0]
    if name not in CASES or name in receipts:raise AssertionError('unknown/duplicate image')
    count=int(self.headers.get('Content-Length','0'))
    if not 0<count<=131072:raise AssertionError('PNG bound')
    raw=self.rfile.read(count);pixels=decode_png(raw)
    equal=pixels==expected_rgba()
    if equal is not CASES[name]:raise AssertionError(name+' pixel policy mismatch')
    (args.output/(name+'.png')).write_bytes(raw)
    receipts[name]={'matchesSelectedPhoto':equal,'pngSha256':hashlib.sha256(raw).hexdigest(),'rgbaSha256':hashlib.sha256(pixels).hexdigest()}
    self.send_response(200);self.end_headers();self.wfile.write(b'ok')
   except Exception as error:
    errors.append(str(error));self.send_response(400);self.end_headers();self.wfile.write(b'rejected')
 server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
 url=f'http://127.0.0.1:{server.server_address[1]}/fixture';photo=(args.output/'selected-photo.png').resolve();photo.write_bytes(png_fixture())
 sources=[ASSET,Path(__file__).resolve(),ROOT/'tools/gecko/photo_upload_contract.py'];hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
 try:
  if args.firefox:
   if not args.geckodriver:raise ValueError('--geckodriver is required with Firefox')
   result,version=firefox_run(args,url,photo,args.output)
  else:
   version=subprocess.check_output([str(args.chromium),'--version'],text=True).strip()
   with tempfile.TemporaryDirectory(prefix='chromium-photo-native-') as temporary:
    base=Path(temporary);(base/'config').mkdir();(base/'cache').mkdir()
    command=[str(args.chromium.resolve()),'--headless','--no-sandbox','--disable-dev-shm-usage','--disable-background-networking','--disable-component-update','--disable-sync','--no-first-run','--no-default-browser-check','--user-data-dir='+str(base/'profile'),'--remote-debugging-port=0','--remote-debugging-address=127.0.0.1','about:blank']
    with chromium_endpoint(command=command,environment=dict(os.environ,XDG_CONFIG_HOME=str(base/'config'),XDG_CACHE_HOME=str(base/'cache')),profile=base/'profile',output=args.output,version=version,source_files=hashes) as endpoint:
     run=subprocess.run(['node','--input-type=module','-e',CONTROLLER,endpoint,url,str(photo)],capture_output=True,text=True,timeout=40)
    (args.output/'controller.stderr.log').write_text(run.stderr)
    if run.returncode:raise RuntimeError('Chromium controller failed; see local log')
    result=json.loads(run.stdout)
 finally:server.shutdown()
 unchanged=all(hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest for name,digest in hashes.items())
 report={'status':'passed' if result.get('status')=='passed' and set(receipts)==set(CASES) and not errors and unchanged else 'failed',
  'actualDesktopChromiumExecution':bool(args.chromium),'actualDesktopFirefoxExecution':bool(args.firefox),'actualAndroidExecution':False,
  'browserVersion':version,'page':result,'receiverErrors':errors,'receipts':receipts,'sourceFiles':hashes,'executionInputsUnchanged':unchanged,
  'sourceCommit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
  'sourceTree':subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=ROOT,text=True).strip(),
  'scope':'Actual browser File selection, production document guard, bitmap/object-URL/FileReader/canvas-chain exports, independent HTTP PNG decoding and negative fingerprint controls. No Android or real-account acceptance.'}
 (args.output/'results.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps({'status':report['status'],'images':len(receipts),'receiverErrors':errors,'page':result}))
 if report['status']!='passed':raise SystemExit(1)

if __name__=='__main__':main()
