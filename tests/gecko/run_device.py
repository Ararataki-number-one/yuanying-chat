#!/usr/bin/env python3
"""Release-mode SDK in the actual app: two live processes, distinct HTTP/SOCKS routes."""
import argparse, importlib.util, json, pathlib, select, socket, socketserver
import subprocess, threading, time, urllib.parse

ROOT=pathlib.Path(__file__).resolve().parents[2]
OUT=ROOT/'work/gecko-integration'
spec=importlib.util.spec_from_file_location('sdk_fixture',ROOT/'engine-probe/tests/run_device.py')
fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
thread_context=threading.local()
class Trace(list):
    def append(self,event):
        if hasattr(thread_context,'route'):event['route']=thread_context.route
        super().append(event)
fixture.TRACE=Trace()
class Socks(fixture.Socks):
    def handle(self):thread_context.route='environment-1-socks';super().handle()
class HttpProxy(socketserver.BaseRequestHandler):
    def handle(self):
        thread_context.route='environment-2-http'
        client=self.request
        with fixture.CONNECTION_LOCK:fixture.CONNECTIONS.add(client)
        try:
            raw=b''
            while b'\r\n\r\n' not in raw and len(raw)<16384:
                data=client.recv(4096)
                if not data:return
                raw+=data
            header,remaining=raw.split(b'\r\n\r\n',1)
            lines=header.decode('iso-8859-1').split('\r\n');method,target,version=lines[0].split(' ',2)
            address=urllib.parse.urlparse('//'+target if method=='CONNECT' else target)
            accepted=method in ['GET','CONNECT'] and address.hostname in ['127.0.0.1','remote-probe.invalid'] and address.port==8765
            fixture.TRACE.append({'kind':'httpProxy','route':'environment-2-http','method':method,'host':address.hostname,'port':address.port,'accepted':accepted})
            if not accepted:client.sendall(b'HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\n\r\n');return
            with socket.create_connection(('127.0.0.1',8765),timeout=10) as upstream:
                if method=='CONNECT':
                    # Firefox tunnels WebSocket through an HTTP proxy, as it does HTTPS.
                    client.sendall(b'HTTP/1.1 200 Connection established\r\n\r\n')
                    if remaining:upstream.sendall(remaining)
                else:
                    path=(address.path or '/')+('?' + address.query if address.query else '')
                    forwarded=[f'{method} {path} {version}']+[line for line in lines[1:] if not line.lower().startswith(('proxy-connection:','proxy-authorization:'))]
                    upstream.sendall(('\r\n'.join(forwarded)+'\r\n\r\n').encode('iso-8859-1')+remaining)
                while True:
                    ready,_,_=select.select([client,upstream],[],[],20)
                    if not ready:return
                    for source in ready:
                        data=source.recv(65536)
                        if not data:return
                        (upstream if source is client else client).sendall(data)
        except OSError:return
        finally:
            with fixture.CONNECTION_LOCK:fixture.CONNECTIONS.discard(client)
class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address=True;daemon_threads=True
class Fixture(fixture.Fixture):
    def do_GET(self):
        address=urllib.parse.urlparse(self.path);query=urllib.parse.parse_qs(address.query)
        if address.path=='/browser-window':
            step=query.get('step',['one'])[0];command=query.get('command',['0'])[0]
            assert step in ['one','two','three','four'] and command.isdigit()
            body=(f'<!doctype html><meta charset="utf-8"><title>Controlled window {step}</title>'
                  f'<h1 id="window-step">{step}</h1><a id="popup" target="_blank" '
                  f'href="/browser-window?step=three&command={command}">Open controlled popup</a>').encode()
        elif address.path=='/browser-loading':
            body=b'<!doctype html><meta charset="utf-8"><h1>Visible before slow resource</h1><img src="/slow-resource">'
        elif address.path=='/slow-resource':
            time.sleep(5);body=b'synthetic-slow-resource'
        else:return super().do_GET()
        self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8')
        self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store')
        self.end_headers();self.wfile.write(body)
    def end_headers(self):
        address=urllib.parse.urlparse(self.path);query=urllib.parse.parse_qs(address.query)
        if address.path=='/fixture' and query.get('action')==['seed']:
            context=query.get('context',['0'])[0]
            self.send_header('Set-Cookie',f'nativeOnly=synthetic-environment-{context}; Path=/; Max-Age=3600; HttpOnly; SameSite=Strict')
        super().end_headers()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--adb',required=True);parser.add_argument('--serial',default='emulator-5554');args=parser.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    def adb(*parts):return subprocess.check_output([args.adb,'-s',args.serial,*parts],text=True,timeout=30)
    package='local.pocketchat.test'
    servers=[fixture.http.server.ThreadingHTTPServer(('127.0.0.1',8765),Fixture),Server(('127.0.0.1',1080),Socks),Server(('127.0.0.1',1081),HttpProxy)]
    for server in servers:threading.Thread(target=server.serve_forever,daemon=True).start()
    for port in [8765,1080,1081]:adb('reverse',f'tcp:{port}',f'tcp:{port}')
    adb('shell','pm','clear',package)
    sdk=int(adb('shell','getprop','ro.build.version.sdk').strip())
    if sdk>=33:adb('shell','pm','grant',package,'android.permission.POST_NOTIFICATIONS')
    # A fresh test phone needs an explicit permission response before checking app UI.
    adb('shell','wm','size','1080x2400');adb('shell','wm','density','420')
    steps=[];logs=[]
    def run(context,action,kind='fixture'):
        adb('logcat','-c')
        activity='GeckoIntegrationTestActivity' if context==1 else 'ProfileGeckoIntegrationActivity1'
        adb('shell','am','start','-n',package+'/local.pocketchat.'+activity,'--es','fixtureAction',action)
        deadline=time.monotonic()+120
        while time.monotonic()<deadline:
            output=adb('logcat','-d','-s','PocketGeckoIntegration:I','*:S')
            for line in output.splitlines():
                if '{' not in line:continue
                try:event=json.loads(line[line.index('{'):])
                except json.JSONDecodeError:continue
                if event.get('nativeContext')!=f'environment-{context}':continue
                if event.get('kind')=='error':raise AssertionError(event)
                if event.get('kind')==kind:
                    result=event['result']
                    assert 'error' not in result,event
                    if kind=='fixture' and (result.get('context')!=str(context) or result.get('action')!=action):continue
                    logs.append(output);steps.append(event);print(json.dumps(event),flush=True)
                    assert 'error' not in result,result
                    return result
                if kind=='fixture' and event.get('kind')=='loadError':raise AssertionError(event)
            time.sleep(1)
        (OUT/'last-device-log.txt').write_text(adb('logcat','-d'))
        raise TimeoutError(f'No integration result: {context}, {action}, {kind}')
    def check(result,context,populated):
        expected=f'synthetic-environment-{context}' if populated else None
        for key in ['localStorage','indexedDB','cache','workerToken']:assert result[key]==expected,(key,result)
        assert result['cookie']==(f'probe={expected}' if populated else ''),result
        assert result['serviceWorkers']==int(populated),result
        assert result.get('nativeCookies') is not None,result
        cookies=dict(part.split('=',1) for part in result['nativeCookies'].split('; ') if part)
        assert cookies==({'probe':expected,'nativeOnly':expected} if populated else {}),result
    report={'actualAndroidExecution':True,'releaseMode':True,'androidSdk':sdk,'androidAbi':adb('shell','getprop','ro.product.cpu.abi').strip(),'viewport':'1080x2400 / 420 dpi','sourceCommit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'googleLogin':'not-tested','internalMihomoRoute':'reuses production API; no live subscription provided'}
    try:
        check(run(1,'seed'),1,True);check(run(2,'read'),2,False)
        check(run(2,'seed'),2,True);check(run(1,'read'),1,True)
        for context in [1,2]:
            network=run(context,'network')
            assert network['remoteDns']=='synthetic-ok' and network['webSocket']=='synthetic-probe',network
            assert network['downloadBytes']==1152 and network['dedicatedWorker']=='synthetic-ok',network
        for context in [1,2]:
            windows=run(context,'windows','windowFlow');assert windows['realPopup'] and windows['parentHistoryRestored'] and windows['popups']==0,windows
            recovery=run(context,'closedSession');check(recovery,context,True)
            assert recovery['closedSessionRecovery'] and recovery['blockedRecoveryPreservesClosed'],recovery
        lost=run(1,'lostParent','windowFlow');assert lost['lostParentRecovery'] and lost['popups']==0,lost
        check(run(2,'read'),2,True)
        paint=run(1,'earlyPaint','paint');assert paint['firstPaintBeforeComplete'],paint
        assert any(x['kind']=='socks' and x.get('route')=='environment-1-socks' for x in fixture.TRACE)
        assert any(x['kind']=='httpProxy' and x.get('route')=='environment-2-http' for x in fixture.TRACE)
        assert any(x['kind']=='socks' and x['host']=='remote-probe.invalid' and x['addressType']==3 for x in fixture.TRACE)
        before=len(fixture.TRACE);blocked=run(1,'block','blocked');assert blocked['guard'] is False and blocked['route']['port']==9,blocked
        assert len(fixture.TRACE)==before,'blocked browser still requested fixture traffic'
        check(run(2,'read'),2,True)
        adb('shell','am','force-stop',package)
        check(run(1,'read'),1,True);check(run(2,'read'),2,True)
        # Switching engines restarts the environment; native runtimes never coexist.
        adb('shell','am','force-stop',package)
        switch=run(1,'systemProbe','engineSwitch');assert switch['gecko'] is False
        adb('shell','am','force-stop',package)
        check(run(1,'read'),1,True);check(run(2,'read'),2,True)
        check(run(1,'clear'),1,False);check(run(2,'read'),2,True)
        bootstrap=run(1,'disableExtension','bootstrapCheck');assert bootstrap['navigationFailed'] is True,bootstrap
        check(run(2,'read'),2,True)
        # Exercise the real outer Activity after moving its retained Gecko surface.
        adb('logcat','-c')
        adb('shell','am','start','-n',package+'/local.pocketchat.MainActivity','--es','openWindowAction','native-smoke')
        time.sleep(4)
        assert adb('shell','pidof',package).strip(),'Production Activity exited'
        adb('shell','uiautomator','dump','/sdcard/gecko-production.xml')
        hierarchy=adb('shell','cat','/sdcard/gecko-production.xml')
        (OUT/'production-ui.xml').write_text(hierarchy)
        for label in ['会话','环境','下载','网络','设置','原网页']:assert label in hierarchy,(label,hierarchy)
        assert 'FATAL EXCEPTION' not in adb('logcat','-d','-s','AndroidRuntime:E','*:S')
        report.update(status='passed',liveEnvironmentProcesses='passed',storageIsolation='passed',restartPersistence='passed',
            distinctHttpSocksRoutes='passed',workersAndWebSocket='passed',remoteDns='passed',guardBlocksRequests='passed',
            nativeContextClear='passed',systemEngineFallback='passed',closedBootstrapWithoutExtension='passed',productionActivityShell='passed',
            popupParentHistory='passed',closedSessionRecovery='passed (injected SDK onKill contract, real close/open/render)',
            closedParentRecovery='passed',firstPaintBeforeSlowResource='passed')
    except Exception as error:
        report.update(status='failed',error=f'{type(error).__name__}: {error}');raise
    finally:
        if report.get('status')!='passed':(OUT/'last-device-log.txt').write_text(adb('logcat','-d'))
        report['steps']=steps
        (OUT/'device-results.json').write_text(json.dumps(report,indent=2)+'\n')
        (OUT/'device-route-trace.json').write_text(json.dumps(fixture.TRACE,indent=2)+'\n')
        (OUT/'device-native-events.txt').write_text('\n'.join(logs))
        for server in servers:server.shutdown();server.server_close()

if __name__=='__main__':main()
