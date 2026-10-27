#!/usr/bin/env python3
"""Actual loopback Chromium context probes, never Android/Gecko or RFP acceptance."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import threading
from http.server import ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('original_api_fixture',HERE/'browser_probe.py')
original=importlib.util.module_from_spec(spec);spec.loader.exec_module(original)
ROOT=HERE.parents[1]
ACTUAL=ROOT/'app/src/main/assets/gecko/main-world-audit.js'
WORKER_INSTRUMENT=r'''
const RealBlob=window.Blob;
window.Blob=class extends RealBlob{
  constructor(parts,options){
    const fault=window.probeFault;
    const prefix=`const fixtureCalls={canvasRead:0,webglRead:0};
      if(typeof OffscreenCanvasRenderingContext2D==='function'){
        const read=OffscreenCanvasRenderingContext2D.prototype.getImageData;
        OffscreenCanvasRenderingContext2D.prototype.getImageData=function(...args){fixtureCalls.canvasRead++;if(${JSON.stringify(fault)}==='worker-canvas-denied')throw new DOMException('controlled denial','SecurityError');return read.apply(this,args);};
      }
      if(typeof WebGLRenderingContext==='function'){
        const read=WebGLRenderingContext.prototype.readPixels;
        WebGLRenderingContext.prototype.readPixels=function(...args){fixtureCalls.webglRead++;return read.apply(this,args);};
      }
      if(${JSON.stringify(fault)}==='worker-no-offscreen')globalThis.OffscreenCanvas=undefined;
      if(${JSON.stringify(fault)}==='worker-no-webgl'&&typeof OffscreenCanvas==='function'){
        const get=OffscreenCanvas.prototype.getContext;OffscreenCanvas.prototype.getContext=function(kind,...args){return kind==='webgl'?null:get.call(this,kind,...args);};
      }
      if(${JSON.stringify(fault)}==='worker-pending-hash')crypto.subtle.digest=()=>new Promise(()=>{});
      const actualPost=globalThis.postMessage;
      globalThis.postMessage=value=>actualPost.call(globalThis,{...value,__fixtureWorkerCalls:fixtureCalls});
    `;
    super([prefix,...parts],options);
  }
};
'''

class Fixture(original.Fixture):
    def do_GET(self):
        path=urlsplit(self.path)
        if path.path!='/':
            return super().do_GET()
        query=parse_qs(path.query)
        cfg={'nonce':'context-browser-case','apiChecks':query.get('deep')==['1']}
        fault=query.get('fault',[''])[0]
        body=('<!doctype html><meta charset="utf-8"><title>Bounded context fixture</title>'
              '<script nonce="Y29udGV4dC1maXh0dXJl">window.probeFault='+json.dumps(fault)+';'+original.INSTRUMENT+WORKER_INSTRUMENT+'</script>'
              '<script src="/main-world-audit.js" data-pocket-audit="'+original.html.escape(json.dumps(cfg),quote=True)+'"></script>').encode()
        self.send_response(200)
        self.send_header('Content-Type','text/html; charset=utf-8')
        self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store')
        if fault=='frame-csp':self.send_header('Content-Security-Policy',"script-src 'self' 'nonce-Y29udGV4dC1maXh0dXJl' 'unsafe-eval'; frame-src 'self'; worker-src 'self' blob:")
        if fault=='worker-csp':self.send_header('Content-Security-Policy',"script-src 'self' 'unsafe-inline' 'unsafe-eval'; frame-src 'self'; worker-src 'none'")
        self.end_headers();self.wfile.write(body)


def run(chromium):
    from playwright.sync_api import sync_playwright
    server=ThreadingHTTPServer(('127.0.0.1',0),Fixture);threading.Thread(target=server.serve_forever,daemon=True).start()
    origin='http://127.0.0.1:'+str(server.server_port);cases=[]
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path=chromium,headless=True,args=['--no-sandbox','--disable-dev-shm-usage','--disable-background-networking','--use-angle=swiftshader','--enable-unsafe-swiftshader'])
            context=browser.new_context();context.route('**/*',lambda route:route.continue_() if route.request.url.startswith(origin+'/') else route.abort());page=context.new_page()
            try:
                for name,query in [('light',''),('real-context-operations','?deep=1'),('worker-offscreen-absent','?deep=1&fault=worker-no-offscreen'),('worker-webgl-absent','?deep=1&fault=worker-no-webgl'),('worker-canvas-denied','?deep=1&fault=worker-canvas-denied'),('frame-csp-blocked','?deep=1&fault=frame-csp'),('worker-csp-blocked','?deep=1&fault=worker-csp')]:
                    page.goto(origin+'/'+query);page.wait_for_function('probeResults.length===1',timeout=10000)
                    result=page.evaluate('probeResults[0]');calls=page.evaluate('probeCalls');assert calls['liveWorkers']==calls['liveBlobs']==0;assert page.locator('iframe').count()==0
                    worker_counts=result['worker'].get('__fixtureWorkerCalls',{})
                    if name=='light':
                        assert 'apiChecks' not in result and 'apiContexts' not in result
                        assert calls['readbacks']==calls['offlineRenders']==0
                        assert worker_counts=={'canvasRead':0,'webglRead':0}
                    else:
                        assert result['apiChecks']['source']=='page-main-world';assert result['apiChecks']['probeVersion']==1
                        contexts=result['apiContexts'];assert contexts['schema']==1 and contexts['requested'] is True
                        frame,worker=contexts['frame'],contexts['worker']
                        if name=='frame-csp-blocked':assert frame is None and 'blocked by CSP' in result['frame']['error']
                        else:
                            assert frame['source']=='same-origin-srcdoc' and frame['protectionVerified'] is False
                            assert frame['limits']==dict(canvasPixels=4096,audioFrames=2048,fontCandidates=5,totalBudgetMs=1200)
                            assert frame['probes']['canvas']['state']=='available';assert frame['probes']['audio']['state']=='available';assert len(frame['probes']['fonts']['samples'])==5
                        if name=='worker-csp-blocked':assert worker is None and result['worker']['error']
                        else:
                            assert worker['source']=='dedicated-worker' and worker['protectionVerified'] is False
                            assert worker['limits']==dict(canvasPixels=4096,audioFrames=0,fontCandidates=0,totalBudgetMs=1200)
                            for api in ['audio','fonts']:assert worker['probes'][api]=={'state':'uncovered','reason':'not-applicable-in-worker'}
                            canvas,webgl=worker['probes']['canvas'],worker['probes']['webgl']
                            if name=='worker-offscreen-absent':
                                assert canvas==webgl=={'state':'uncovered','reason':'offscreen-canvas-unavailable'};assert worker_counts=={'canvasRead':0,'webglRead':0}
                            else:
                                assert worker_counts['canvasRead']==1
                                if name=='worker-canvas-denied':assert canvas['state']=='restricted' and canvas['reason']=='SecurityError'
                                else:assert canvas['state']=='available' and re.fullmatch('[0-9a-f]{64}',canvas['hash'])
                                if name=='worker-webgl-absent':assert webgl=={'state':'uncovered','reason':'webgl-context-unavailable'} and worker_counts['webglRead']==0
                                else:
                                    assert worker_counts['webglRead']==1 and webgl['state'] in ['available','restricted']
                                    assert webgl['readbackPixels']==256 and webgl['readbackBytes']==1024 and re.fullmatch('[0-9a-f]{64}',webgl['readbackHash'])
                    cases.append(dict(name=name,status='passed',faultInjected=name not in ['light','real-context-operations'],observations=result,counters=calls))
                for event in ['pocket-audit-cancel','pagehide']:
                    page.goto(origin+'/?deep=1&fault=worker-pending-hash');page.wait_for_function('probeCalls.liveWorkers===1',timeout=5000)
                    if event=='pagehide':page.evaluate("dispatchEvent(new Event('pagehide'))")
                    else:page.evaluate("dispatchEvent(new CustomEvent('pocket-audit-cancel',{detail:'context-browser-case'}))")
                    page.wait_for_timeout(2800);calls=page.evaluate('probeCalls');assert page.evaluate('probeResults.length')==0;assert calls['liveWorkers']==calls['liveBlobs']==0;assert page.locator('iframe').count()==0
                    cases.append(dict(name='cancel-'+event,status='passed',faultInjected=True,counters=calls))
                return dict(schema=1,status='passed',actualChromiumExecution=True,actualGeckoExecution=False,actualAndroidExecution=False,physicalPhoneAcceptance=False,privacyProtectionAcceptance=False,publicNetworkTraffic=False,browserVersion=browser.version,productionAssetSha256=hashlib.sha256(ACTUAL.read_bytes()).hexdigest(),caseCount=len(cases),cases=cases,scope='Actual local Chromium page/frame/worker operations; explicit isolated failure/CSP/cancel controls. No cross-context hash equality or RFP effectiveness claim.')
            finally:context.close();browser.close()
    finally:server.shutdown();server.server_close()

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--chromium',default='/usr/bin/chromium');parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();result=run(args.chromium);args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:result[k] for k in ['status','caseCount','browserVersion','actualChromiumExecution','actualGeckoExecution']}))
