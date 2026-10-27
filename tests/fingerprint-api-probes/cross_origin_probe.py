#!/usr/bin/env python3
"""Real Chromium cross-origin graphics function, not deployed protocol/Gecko acceptance."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer

ROOT=Path(__file__).resolve().parents[2]
HELPER=ROOT/'tools/fingerprint/context_graphics_probe.cjs'
NONCE='d'*32

class Fixture(BaseHTTPRequestHandler):
    def log_message(self,*_):pass
    def do_GET(self):
        if self.server.role=='primary':
            body=('<!doctype html><title>Cross-origin graphics parent</title><iframe id="sample" src="'+self.server.other+'/frame"></iframe><script>'
                  'window.result=null;addEventListener("message",event=>{const frame=document.getElementById("sample");if(!frame||event.source!==frame.contentWindow||event.origin!=='+json.dumps(self.server.other)+'||event.data?.nonce!=='+json.dumps(NONCE)+')return;'
                  'let isolated=false;try{void frame.contentWindow.document.body}catch(error){isolated=error.name==="SecurityError"}'
                  'window.result={...event.data,independentEventOrigin:event.origin,actualFrameSopRestricted:isolated};frame.remove();});</script>').encode()
        else:
            counters='const calls={canvasRead:0,webglRead:0};const canvasRead=CanvasRenderingContext2D.prototype.getImageData;CanvasRenderingContext2D.prototype.getImageData=function(...args){calls.canvasRead++;return canvasRead.apply(this,args);};const glRead=WebGLRenderingContext.prototype.readPixels;WebGLRenderingContext.prototype.readPixels=function(...args){calls.webglRead++;return glRead.apply(this,args);};'
            body=('<!doctype html><title>Cross-origin graphics child</title><script>'+counters+'('+self.server.probe+')().then(apiChecks=>parent.postMessage({nonce:'+json.dumps(NONCE)+',actualOrigin:location.origin,secureContext:isSecureContext,apiChecks,counters:calls},'+json.dumps(self.server.other)+'));</script>').encode()
        self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(body)


def run(chromium):
    from playwright.sync_api import sync_playwright
    probe=subprocess.check_output(['node','-e','process.stdout.write(require("./tools/fingerprint/context_graphics_probe.cjs").controlledFrameGraphics.toString())'],cwd=ROOT,text=True)
    primary=ThreadingHTTPServer(('127.0.0.1',0),Fixture);secondary=ThreadingHTTPServer(('127.0.0.1',0),Fixture)
    first='http://127.0.0.1:'+str(primary.server_port);second='http://127.0.0.1:'+str(secondary.server_port)
    for server,role,other in [(primary,'primary',second),(secondary,'secondary',first)]:server.role=role;server.other=other;server.probe=probe;threading.Thread(target=server.serve_forever,daemon=True).start()
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path=chromium,headless=True,args=['--no-sandbox','--disable-dev-shm-usage','--disable-background-networking','--use-angle=swiftshader','--enable-unsafe-swiftshader']);context=browser.new_context();context.route('**/*',lambda route:route.continue_() if any(route.request.url.startswith(origin+'/') for origin in [first,second]) else route.abort());page=context.new_page()
            try:
                page.goto(first+'/');page.wait_for_function('window.result!==null',timeout=8000);result=page.evaluate('result');api=result['apiChecks'];assert result['actualFrameSopRestricted'] is True and result['secureContext'] is True;assert result['actualOrigin']==result['independentEventOrigin']==second;assert result['counters']==dict(canvasRead=1,webglRead=1);assert page.locator('iframe').count()==0
                assert api['source']=='controlled-cross-origin-iframe' and api['probeVersion']==1 and api['protectionVerified'] is False
                assert api['limits']==dict(canvasPixels=4096,audioFrames=0,fontCandidates=0,totalBudgetMs=1200)
                assert api['probes']['canvas']['state']=='available' and api['probes']['canvas']['pixels']==4096 and re.fullmatch('[0-9a-f]{64}',api['probes']['canvas']['hash'])
                gl=api['probes']['webgl'];assert gl['state'] in ['available','restricted'] and gl['readbackPixels']==256 and gl['readbackBytes']==1024 and re.fullmatch('[0-9a-f]{64}',gl['readbackHash'])
                for name in ['audio','fonts']:assert api['probes'][name]==dict(state='uncovered',reason='not-covered-by-controlled-frame-graphics')
                return dict(schema=1,status='passed',actualChromiumExecution=True,actualGeckoExecution=False,actualAndroidExecution=False,actualProductionProtocolExecution=False,physicalPhoneAcceptance=False,privacyProtectionAcceptance=False,publicNetworkTraffic=False,browserVersion=browser.version,helperSha256=hashlib.sha256(HELPER.read_bytes()).hexdigest(),observations=result,scope='Actual serialized production graphics function in a distinct loopback HTTP origin iframe with real SOP restriction and API call counters. Not the production HTTPS detector protocol, Gecko, Android, RFP or a physical-phone test.')
            finally:context.close();browser.close()
    finally:
        for server in [primary,secondary]:server.shutdown();server.server_close()

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--chromium',default='/usr/bin/chromium');parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();value=run(args.chromium);args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(value,indent=2)+'\n');print(json.dumps({k:value[k] for k in ['status','actualChromiumExecution','actualGeckoExecution','actualProductionProtocolExecution']}))
