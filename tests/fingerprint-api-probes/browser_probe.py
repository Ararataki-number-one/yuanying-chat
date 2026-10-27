#!/usr/bin/env python3
"""Exercise production API probes in real local Chromium, with explicit fault cases.

This optional developer check requires Playwright and a local Chromium binary.
It does not test Gecko, Android, RFP effectiveness, or ChatGPT. No public endpoint
is contacted; only the loopback fixture is served. Injected failures are labelled.
"""
import argparse
import hashlib
import html
import json
from pathlib import Path
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[2]
ASSET = ROOT / 'app/src/main/assets/gecko/main-world-audit.js'
INSTRUMENT = r'''
window.probeCalls={readbacks:0,offlineRenders:0,audioRetired:0,audioContextsRetired:0,liveWorkers:0,liveBlobs:0};
window.probeResults=[];
window.addEventListener('pocket-audit-observation',event=>{window.probeResults.push(JSON.parse(event.detail));});
const actualRead=CanvasRenderingContext2D.prototype.getImageData;
CanvasRenderingContext2D.prototype.getImageData=function(...args){
  probeCalls.readbacks++;
  if(window.probeFault==='canvas-security')throw new DOMException('controlled denial','SecurityError');
  return actualRead.apply(this,args);
};
const ActualOffline=window.OfflineAudioContext;
if(window.probeFault==='audio-missing')window.OfflineAudioContext=undefined;
else if(['audio-pending','audio-setup-failure'].includes(window.probeFault))window.OfflineAudioContext=class{
  constructor(){this.destination={};}
  createOscillator(){return {frequency:{value:0},connect(){},start(){},stop(){},disconnect(){probeCalls.audioRetired++;}};}
  createDynamicsCompressor(){if(window.probeFault==='audio-setup-failure')throw new DOMException('controlled graph setup denial','NotAllowedError');return {threshold:{},knee:{},ratio:{},attack:{},release:{},connect(){},disconnect(){probeCalls.audioRetired++;}};}
  startRendering(){probeCalls.offlineRenders++;return new Promise(()=>{});}
  close(){probeCalls.audioContextsRetired++;return Promise.resolve();}
};
else window.OfflineAudioContext=class extends ActualOffline{
  startRendering(){probeCalls.offlineRenders++;return super.startRendering();}
};
const ActualWorker=window.Worker;
window.Worker=class extends ActualWorker{
  constructor(...args){super(...args);probeCalls.liveWorkers++;this.retired=false;}
  terminate(){if(!this.retired){this.retired=true;probeCalls.liveWorkers--;}return super.terminate();}
};
const actualCreate=URL.createObjectURL,actualRevoke=URL.revokeObjectURL;
const liveUrls=new Set();
URL.createObjectURL=function(...args){const url=actualCreate.apply(this,args);liveUrls.add(url);probeCalls.liveBlobs=liveUrls.size;return url;};
URL.revokeObjectURL=function(url){liveUrls.delete(url);probeCalls.liveBlobs=liveUrls.size;return actualRevoke.call(this,url);};
'''


class Fixture(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_GET(self):
        target = urlsplit(self.path)
        if target.path == '/main-world-audit.js':
            body = ASSET.read_bytes()
            mime = 'application/javascript'
        elif target.path == '/':
            query = parse_qs(target.query)
            cfg = {'nonce': 'api-probe-browser-case', 'apiChecks': query.get('deep') == ['1']}
            fault = query.get('fault', [''])[0]
            body = ('<!doctype html><meta charset="utf-8"><title>Local API probe fixture</title>'
                    '<script>window.probeFault=' + json.dumps(fault) + ';' + INSTRUMENT + '</script>'
                    '<script src="/main-world-audit.js" data-pocket-audit="' +
                    html.escape(json.dumps(cfg), quote=True) + '"></script>').encode()
            mime = 'text/html; charset=utf-8'
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)


def run(chromium):
    from playwright.sync_api import sync_playwright
    server = ThreadingHTTPServer(('127.0.0.1', 0), Fixture)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = 'http://127.0.0.1:' + str(server.server_port)
    cases = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=chromium, headless=True, args=[
                '--no-sandbox', '--disable-dev-shm-usage', '--disable-background-networking',
                '--use-angle=swiftshader', '--enable-unsafe-swiftshader'])
            context = browser.new_context()
            context.route('**/*', lambda route: route.continue_() if route.request.url.startswith(origin + '/') else route.abort())
            page = context.new_page()
            try:
                for name, query in [('light', ''), ('real-api-operations', '?deep=1'),
                                    ('canvas-denied', '?deep=1&fault=canvas-security'),
                                    ('audio-absent', '?deep=1&fault=audio-missing'),
                                    ('audio-timeout', '?deep=1&fault=audio-pending'),
                                    ('audio-setup-failure', '?deep=1&fault=audio-setup-failure')]:
                    page.goto(origin + '/' + query)
                    page.wait_for_function('probeResults.length===1', timeout=10000)
                    result = page.evaluate('probeResults[0]')
                    calls = page.evaluate('probeCalls')
                    assert calls['liveWorkers'] == calls['liveBlobs'] == 0
                    assert page.locator('iframe').count() == 0
                    if name == 'light':
                        assert 'apiChecks' not in result
                        assert calls['readbacks'] == calls['offlineRenders'] == 0
                    else:
                        api = result['apiChecks']
                        assert api['source'] == 'page-main-world' and api['protectionVerified'] is False
                        assert api['limits'] == dict(canvasPixels=4096, audioFrames=2048, fontCandidates=5, totalBudgetMs=1200)
                        probes = api['probes']
                        assert set(probes) == {'canvas', 'audio', 'fonts', 'webgl'}
                        if name == 'canvas-denied':
                            assert probes['canvas']['state'] == 'restricted' and probes['canvas']['reason'] == 'SecurityError'
                        else:
                            assert probes['canvas']['state'] == 'available'
                            assert probes['canvas']['pixels'] == 4096
                            assert re.fullmatch('[0-9a-f]{64}', probes['canvas']['hash'])
                        if name == 'audio-absent':
                            assert probes['audio']['state'] == 'uncovered' and probes['audio']['reason'] == 'offline-audio-unavailable'
                        elif name == 'audio-timeout':
                            assert probes['audio']['state'] == 'uncovered' and probes['audio']['reason'] == 'time-budget-exhausted'
                            assert calls['audioRetired'] == 2 and calls['audioContextsRetired'] == 1
                        elif name == 'audio-setup-failure':
                            assert probes['audio']['state'] == 'restricted' and probes['audio']['reason'] == 'NotAllowedError'
                            assert calls['audioRetired'] == calls['audioContextsRetired'] == 1
                            assert calls['offlineRenders'] == 0
                        else:
                            assert probes['audio']['state'] == 'available' and probes['audio']['frames'] == 2048
                            assert re.fullmatch('[0-9a-f]{64}', probes['audio']['hash'])
                        assert probes['fonts']['state'] == 'available' and len(probes['fonts']['samples']) == 5
                        assert probes['webgl']['state'] in ['available', 'restricted']
                    cases.append(dict(name=name, status='passed', faultInjected=name not in ['light', 'real-api-operations'], observations=result, counters=calls))
                for event in ['pocket-audit-cancel', 'pagehide']:
                    page.goto(origin + '/?deep=1&fault=audio-pending')
                    page.wait_for_function('probeCalls.offlineRenders===1', timeout=10000)
                    if event == 'pagehide':
                        page.evaluate("dispatchEvent(new Event('pagehide'))")
                    else:
                        page.evaluate("dispatchEvent(new CustomEvent('pocket-audit-cancel',{detail:'api-probe-browser-case'}))")
                    page.wait_for_timeout(100)
                    assert page.evaluate('probeResults.length') == 0
                    calls = page.evaluate('probeCalls')
                    assert calls['audioRetired'] == 2 and calls['audioContextsRetired'] == 1
                    assert calls['liveWorkers'] == calls['liveBlobs'] == 0
                    assert page.locator('iframe').count() == 0
                    cases.append(dict(name='cancel-' + event, status='passed', faultInjected=True, counters=calls))
                return dict(schema=1, status='passed', actualChromiumExecution=True,
                            actualGeckoExecution=False, actualAndroidExecution=False,
                            physicalPhoneAcceptance=False, privacyProtectionAcceptance=False,
                            publicNetworkTraffic=False, browserVersion=browser.version,
                            productionAssetSha256=hashlib.sha256(ASSET.read_bytes()).hexdigest(),
                            caseCount=len(cases), cases=cases,
                            budgetScope='Cooperative elapsed-time guard and fixed operation count; a synchronous native browser call cannot be preempted by JavaScript.',
                            scope='Real local Chromium API operations with labelled denial/absence/timeout/cancel injection. Not Gecko/RFP, Android or ChatGPT acceptance.')
            finally:
                context.close()
                browser.close()
    finally:
        server.shutdown()
        server.server_close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--chromium', default='/usr/bin/chromium')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = run(args.chromium)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({key: report[key] for key in ['status', 'browserVersion', 'caseCount', 'actualChromiumExecution', 'actualGeckoExecution']}))
