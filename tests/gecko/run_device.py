#!/usr/bin/env python3
"""Release-mode SDK in the actual app: two live processes, distinct HTTP/SOCKS routes."""
import argparse, hashlib, importlib.util, json, pathlib, select, socket, socketserver
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
    def do_POST(self):
        body=self.rfile.read(int(self.headers.get('Content-Length','0')))
        ok=self.path=='/image-received' and b'filename="photo-123.png"' in body and b'Content-Type: image/png' in body and b'\x89PNG\r\n\x1a\n' in body
        self.send_response(200 if ok else 400);self.send_header('Content-Length','0');self.end_headers()
    def do_GET(self):
        address=urllib.parse.urlparse(self.path);query=urllib.parse.parse_qs(address.query)
        if address.path.startswith('/update-'):
            source=OUT/('update-wrong-signer.apk' if address.path=='/update-wrong-signer' else 'update-fixture.apk')
            body=bytearray(source.read_bytes())
            if address.path=='/update-corrupt':body[len(body)//2]^=1
            self.send_response(200);self.send_header('Content-Type','application/octet-stream');self.send_header('Content-Length',str(len(body)));self.end_headers()
            if address.path=='/update-wait':time.sleep(10)
            try:self.wfile.write(body)
            except (BrokenPipeError,ConnectionResetError):pass
            return
        if address.path=='/native-csv':
            body=b'name,value\nsynthetic,42\n'
            self.send_response(200);self.send_header('Content-Type','text/csv');self.send_header('Content-Disposition','attachment; filename="generated.csv"');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body);return
        if address.path=='/browser-image':
            body=b'''<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><h1>Desktop image fixture</h1><input id="upload" type="file" accept="image/*" multiple><p id="upload-result"></p><script>upload.onchange=async e=>{try{const f=e.target.files[0],image=await createImageBitmap(f),bytes=new Uint8Array(await f.arrayBuffer());if(f.type!=='image/png'||image.width!==4||image.height!==3||bytes[0]!==137||bytes[1]!==80)throw Error('image bytes or MIME lost');const form=new FormData();form.append('file',f);const response=await fetch('/image-received',{method:'POST',body:form});if(!response.ok)throw Error('upload rejected');document.getElementById('upload-result').textContent='ok:'+f.name+':'+f.type+':4x3';}catch(error){document.getElementById('upload-result').textContent='error:'+error.message;}};</script>'''
        elif address.path=='/browser-usability':
            body=b'''<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><h1>Mobile browser capability fixture</h1><input id="upload" type="file" accept="text/plain"><p id="upload-result"></p><a id="csv" href="/native-csv">Download generated CSV</a><button id="blob" onclick="const a=document.createElement('a');a.href=window.URL.createObjectURL(new window.Blob(['name,value\\nsynthetic,42\\n'],{type:'text/csv'}));a.download='generated.csv';document.body.appendChild(a);a.click();a.remove();">Download page blob</button><script>document.getElementById('upload').onchange=async e=>{const f=e.target.files[0];document.getElementById('upload-result').textContent=f.name+':'+await f.text();};</script>'''
        elif address.path=='/browser-window':
            step=query.get('step',['one'])[0];command=query.get('command',['0'])[0]
            assert step in ['one','two','three','four'] and command.isdigit()
            body=(f'<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Controlled window {step}</title>'
                  f'<h1 id="window-step">{step}</h1><button id="popup" '
                  f'onclick="window.open(\'/browser-window?step=three&command={command}\',\'_blank\')">Open controlled popup</button>').encode()
        elif address.path=='/browser-loading':
            body=b'<!doctype html><meta charset="utf-8"><h1>Visible before slow resource</h1><img src="/slow-resource">'
        elif address.path=='/browser-reading':
            body=b'''<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
            <title>Controlled responsive reading fixture</title><style>body{margin:0;font:18px sans-serif}main{padding:16px;box-sizing:border-box}#sidebar{width:260px;float:left}textarea{width:100%;box-sizing:border-box;font:inherit}pre{overflow:auto}@media(max-width:760px){#sidebar{display:none}}</style>
            <aside id="sidebar">Controlled sidebar</aside><main><h1>Controlled readable content</h1><p>This fixture checks native viewport settings; it does not replace ChatGPT.</p><pre>Long code remains horizontally scrollable.........................................................................................</pre><textarea id="composer">Unsent draft stays here</textarea></main>'''
        elif address.path=='/browser-session':
            token='none'
            for cookie in self.headers.get('Cookie','').split(';'):
                if cookie.strip().startswith('sessionOnly='):token=cookie.strip().split('=',1)[1]
            if query.get('action')==['sessionSeed']:token='synthetic-session-'+query.get('context',['0'])[0]
            if query.get('action')==['sessionLogout']:token='none'
            body=(f'<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
                f'<h1>Controlled session continuity</h1><p id="session-result">{token}</p><textarea id="session-draft"></textarea>').encode()
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
        if address.path=='/browser-session' and query.get('action')==['sessionSeed']:
            self.send_header('Set-Cookie','sessionOnly=synthetic-session-'+query.get('context',['0'])[0]+'; Path=/browser-session; HttpOnly; SameSite=Lax')
        if address.path=='/browser-session' and query.get('action')==['sessionLogout']:
            self.send_header('Set-Cookie','sessionOnly=; Path=/browser-session; HttpOnly; SameSite=Lax; Max-Age=0')
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
    for setting in ['window_animation_scale','transition_animation_scale','animator_duration_scale']:
        adb('shell','settings','put','global',setting,'0')
    launcher='com.google.android.apps.nexuslauncher'
    has_pixel_launcher=launcher in adb('shell','pm','list','packages',launcher)
    steps=[];logs=[]
    def run(context,action,kind='fixture'):
        adb('logcat','-c')
        tapped=set()
        activity='GeckoIntegrationTestActivity' if context==1 else 'ProfileGeckoIntegrationActivity1'
        # This emulator image's Pixel Launcher can ANR during first-boot package
        # optimization and intercept otherwise correct trusted taps. Stop only
        # that unrelated package before returning to the test Activity; never
        # dismiss an app ANR. The Home step still exercises real backgrounding.
        if has_pixel_launcher:adb('shell','am','force-stop',launcher)
        adb('shell','am','start','-W','-n',package+'/local.pocketchat.'+activity,'--es','fixtureAction',action)
        deadline=time.monotonic()+120
        while time.monotonic()<deadline:
            output=adb('logcat','-d','-s','PocketGeckoIntegration:I','*:S')
            for line in output.splitlines():
                if '{' not in line:continue
                try:event=json.loads(line[line.index('{'):])
                except json.JSONDecodeError:continue
                if event.get('nativeContext')!=f'environment-{context}':continue
                if event.get('kind')=='homeNeeded':
                    marker=event['result']['id']
                    if marker not in tapped:tapped.add(marker);adb('shell','input','keyevent','KEYCODE_HOME')
                    continue
                if event.get('kind')=='tapNeeded':
                    tap=event['result']
                    if tap['id'] not in tapped:
                        tapped.add(tap['id']);time.sleep(.4);print(json.dumps(event),flush=True)
                        adb('shell','input','tap',str(tap['x']),str(tap['y']))
                        if tap['id'].startswith('composer-'):
                            # adb input text emits a word's hardware key events
                            # as fast as possible. Give the real browser/IME on
                            # this CPU-limited emulator human typing intervals;
                            # keep asserting the exact ordered text below.
                            time.sleep(.5)
                            for character in 'native-input-ok':
                                adb('shell','input','text',character);time.sleep(.15)
                    continue
                if event.get('kind')=='error':logs.append(output);raise AssertionError(event)
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
    def update(action):
        adb('logcat','-c')
        source=OUT/('update-wrong-signer.apk' if action=='badSigner' else 'update-fixture.apk')
        data=source.read_bytes()
        adb('shell','am','start','-W','-n',package+'/local.pocketchat.AppUpdateIntegrationActivity','--es','updateAction',action,'--es','updateHash',hashlib.sha256(data).hexdigest(),'--el','updateBytes',str(len(data)))
        deadline=time.monotonic()+90
        while time.monotonic()<deadline:
            output=adb('logcat','-d','-s','PocketAppUpdateIntegration:I','*:S')
            for line in output.splitlines():
                if '{' not in line:continue
                result=json.loads(line[line.index('{'):]);assert 'error' not in result,result
                event=dict(kind='appUpdate',action=action,result=result)
                steps.append(event);logs.append(output);print(json.dumps(event),flush=True);return result
            time.sleep(.5)
        raise TimeoutError('No native update result: '+action)
    def management(action):
        adb('logcat','-c')
        adb('shell','am','start','-W','-n',package+'/local.pocketchat.EnvironmentManagementIntegrationActivity','--es','managementAction',action)
        deadline=time.monotonic()+90
        while time.monotonic()<deadline:
            output=adb('logcat','-d','-s','PocketEnvironmentManagement:I','*:S')
            for line in output.splitlines():
                if '{' not in line:continue
                try:result=json.loads(line[line.index('{'):])
                except json.JSONDecodeError:continue
                if result.get('action')!=action:continue
                assert 'error' not in result,result
                assert all(value is True for key,value in result.items() if key!='action'),result
                steps.append(dict(kind='environmentManagement',result=result));print(json.dumps(result),flush=True);return result
            time.sleep(1)
        raise TimeoutError('Environment management: '+action)
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
        usability=run(1,'usability','usability');assert usability['documentPreserved'] and usability['mobileVisible'] and usability['upload']=='sample.txt:synthetic-upload' and usability['csv']=='name,value\nsynthetic,42\n' and usability['blob']==usability['csv'],usability
        report['browserUsability']=usability
        image=run(1,'desktopImage','desktopImage');assert all(image[k] for k in ['productionChooserOpened','imageMimeAndMultiple','pendingPreserved','noPhantomUpload','desktop']) and image['upload']=='ok:photo-123.png:image/png:4x3',image
        report['desktopImageUpload']=image
        check(run(1,'seed'),1,True);check(run(2,'read'),2,False)
        check(run(2,'seed'),2,True);check(run(1,'read'),1,True)
        for context in [1,2]:
            network=run(context,'network')
            assert network['remoteDns']=='synthetic-ok' and network['webSocket']=='synthetic-probe',network
            assert network['downloadBytes']==1152 and network['dedicatedWorker']=='synthetic-ok',network
        for context in [1,2]:
            windows=run(context,'windows','windowFlow');assert windows['realPopup'] and windows['parentHistoryRestored'] and windows['popups']==0,windows
            recovery=run(context,'closedSession');check(recovery,context,True)
            assert recovery['closedSessionRecovery'] and recovery['blockedRecoveryPreservesClosed'] and recovery['pendingFailureRetained'],recovery
        lost=run(1,'lostParent','windowFlow');assert lost['lostParentRecovery'] and lost['popups']==0,lost
        check(run(2,'read'),2,True)
        sessions=[]
        for context in [1,2]:
            seed=run(context,'sessionSeed','session');assert seed['token']==f'synthetic-session-{context}' and seed['checkpoint'],seed
            recovered=run(context,'killRestore','session')
            assert recovered['token']==f'synthetic-session-{context}' and recovered['draft']==f'session-draft-{context}' and recovered['automaticRecovery'] and recovered['profileForeground'],recovered
            sessions.append(dict(context=context,**recovered))
        # Keep both processes live and repeatedly move the surface between foreground tasks.
        for _ in range(6):
            for context in [1,2]:
                result=run(context,'sessionLive','session');assert result['token']==f'synthetic-session-{context}' and result['profileForeground'] and result['draft']==f'session-draft-{context}',result
        adb('shell','input','keyevent','KEYCODE_HOME');time.sleep(2)
        for context in [1,2]:
            resumed=run(context,'sessionLive','session');assert resumed['token']==f'synthetic-session-{context}' and resumed['profileForeground'] and resumed['draft']==f'session-draft-{context}',resumed
            saved=run(context,'sessionCheckpoint','checkpoint');assert saved['saved'],saved
        adb('shell','am','force-stop',package)
        for context in [1,2]:
            restored=run(context,'resumeSaved','session');assert restored['token']==f'synthetic-session-{context}' and restored['profileForeground'] and restored['draft']==f'session-draft-{context}',restored
        assert run(1,'sessionLogout','session')['token']=='none'
        # Wait for the official cookie removal event to reach the private journal.
        run(1,'sessionCheckpoint','checkpoint');adb('shell','am','force-stop',package)
        assert run(1,'sessionRead','session')['token']=='none'
        assert run(2,'sessionRead','session')['token']=='synthetic-session-2'
        report['sessionContinuity']=sessions
        paint=run(1,'earlyPaint','paint');assert paint['firstPaintBeforeComplete'],paint
        reading=[]
        for size in ['945x2100','1024x2240','1128x2400','1920x1080']:
            adb('shell','wm','size',size)
            result=run(1,'reading','reading');reading.append(dict(size=size,**result))
            assert result['mobileViewport'] and result['desktopIdentity'] and 'Android' not in result['userAgent'],result
            assert abs(result['viewport']*result['density']-result['nativeWidth'])<5 and abs(result['scale']-1)<.02,result
            assert result['sidebarHidden'] and result['composerWidth']>=result['viewport']-34 and result['draft']=='Unsent draft stays here',result
            (OUT/f'reading-{size}.png').write_bytes(subprocess.check_output([args.adb,'-s',args.serial,'exec-out','screencap','-p'],timeout=30))
        report['responsiveReading']=reading
        adb('shell','wm','size','1080x2400')
        run(1,'reading','reading')
        zoom=run(1,'readingZoom','readingZoom')['checks'];report['nativeReadingZoom']=zoom
        assert len(zoom)==4 and len({x['document'] for x in zoom})==1 and all(x['draft']=='Unsent draft stays here' for x in zoom),zoom
        for x in zoom:
            assert abs(x['shownFontPixels']/(18*x['density'])-x['choice'])<.06,x
        assert zoom[1]['shownFontPixels']<zoom[0]['shownFontPixels']<zoom[2]['shownFontPixels'],zoom
        (OUT/'reading-shrunk-80.png').write_bytes(subprocess.check_output([args.adb,'-s',args.serial,'exec-out','screencap','-p'],timeout=30))
        typed=run(1,'readingInput','readingInput');assert typed['focused']=='composer' and 'native-input-ok' in typed['draft'] and abs(typed['choice']-.8)<.02,typed
        adb('shell','input','keyevent','KEYCODE_BACK')
        cancelled=run(1,'cancelLoad','cancelledLoad');assert not cancelled['reportedFailure'] and not cancelled['pageError'] and cancelled['visibleDocumentRetained'] and cancelled['documentReadyBeforeStop'],cancelled
        assert any(x['kind']=='socks' and x.get('route')=='environment-1-socks' for x in fixture.TRACE)
        assert any(x['kind']=='httpProxy' and x.get('route')=='environment-2-http' for x in fixture.TRACE)
        assert any(x['kind']=='socks' and x['host']=='remote-probe.invalid' and x['addressType']==3 for x in fixture.TRACE)
        blocked=run(1,'block','blocked');assert blocked['guard'] is False and blocked['route']['port']==9 and blocked['newFetchBlocked'],blocked
        # Background service-worker updates already admitted before blocking may
        # finish. Assert a uniquely identified new request, not global traffic.
        assert not any(x.get('kind')=='http' and x.get('path','').startswith('/guard-blocked') for x in fixture.TRACE),'A new blocked request reached the fixture'
        check(run(2,'read'),2,True)
        adb('shell','am','force-stop',package)
        check(run(1,'read'),1,True);check(run(2,'read'),2,True)
        # Switching engines restarts the environment; native runtimes never coexist.
        adb('shell','am','force-stop',package)
        switch=run(1,'systemProbe','engineSwitch');assert switch['gecko'] is False
        adb('shell','am','force-stop',package)
        check(run(1,'read'),1,True);check(run(2,'read'),2,True)
        assert run(1,'sessionSeed','session')['token']=='synthetic-session-1'
        check(run(1,'clear'),1,False);check(run(2,'read'),2,True)
        adb('shell','am','force-stop',package)
        assert run(1,'sessionRead','session')['token']=='none','Explicit profile clear restored a deleted session cookie'
        assert run(2,'sessionRead','session')['token']=='synthetic-session-2'
        privacy=run(1,'privacy','privacy');assert privacy['nativeFingerprintingEnabled'] is True,privacy
        completion=run(1,'completion','completion');assert completion['guestActionsRecognized'] and completion['priorActionsCannotComplete'] and completion['nestedMessageIdRecognized'],completion
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
        update_checks=[]
        for action in ['badHash','badSigner','cancel']:
            result=update(action);update_checks.append(result)
            assert result['state']=='available' and not result['uri'] and result['downloadId']==-1,result
            if action=='badHash':assert '不完整' in result['message'],result
            if action=='badSigner':assert '签名' in result['message'],result
            if action=='cancel':assert '取消' in result['message'],result
        good=update('good');assert good['state']=='ready' and good['uri'].startswith('content://'+package+'.app-updates/'),good
        access=update('verifyAccess');assert access['readOnly'] and access['traversalRejected'] and access['sameSigner'],access
        update('showUi');time.sleep(1)
        adb('shell','uiautomator','dump','/sdcard/update-ui.xml');update_ui=adb('shell','cat','/sdcard/update-ui.xml');(OUT/'update-ui.xml').write_text(update_ui)
        for label in ['应用更新','当前版本','安装更新','自动检查更新','Wi-Fi 下自动下载新版']:assert label in update_ui,(label,update_ui)
        (OUT/'update-ui.png').write_bytes(subprocess.check_output([args.adb,'-s',args.serial,'exec-out','screencap','-p'],timeout=30))
        adb('shell','appops','set',package,'REQUEST_INSTALL_PACKAGES','allow')
        import xml.etree.ElementTree as ET,re
        button=next(node for node in ET.fromstring(update_ui).iter('node') if node.attrib.get('text')=='安装更新')
        x1,y1,x2,y2=map(int,re.findall(r'\d+',button.attrib['bounds']))
        adb('shell','input','tap',str((x1+x2)//2),str((y1+y2)//2));time.sleep(3)
        adb('shell','uiautomator','dump','/sdcard/update-installer-ui.xml');installer_ui=adb('shell','cat','/sdcard/update-installer-ui.xml');(OUT/'update-installer-ui.xml').write_text(installer_ui)
        assert 'packageinstaller' in installer_ui and ('Update' in installer_ui or '更新' in installer_ui),installer_ui
        adb('shell','input','keyevent','KEYCODE_BACK') # Never install the synthetic replacement.
        report['appUpdates']=dict(downloadManager='passed (real system HTTP transfer)',good=good,failures=update_checks,provider=access,settingsUi='passed',androidInstaller='passed (opened; synthetic APK not installed)')
        queued=run(2,'queuedChanges','queuedChanges');assert all(queued[key] for key in ['savedWhileReplying','oldRouteKept','browserSavedWithoutApplying','replyCleared','appliedWhenIdle','vpnGuardBlocksWithoutVpn']),queued
        foreign_before=run(1,'foreignPreferences','foreignPreferences');assert foreign_before['marker']=='prime-target',foreign_before
        deletion=management('deleteOne')
        foreign_after=run(1,'foreignPreferences','foreignPreferences');assert not foreign_after['marker'],foreign_after
        check(run(2,'read'),2,False)
        background_settings=run(2,'backgroundSettings','backgroundSettings');assert all(background_settings.values()),background_settings
        deletion_zero=management('deleteZero')
        report['environmentManagement']=dict(queued=queued,backgroundSettings=background_settings,deleteOne=deletion,deleteZero=deletion_zero,foreignPreferenceCache='passed (live parent sees cleared preferences)',slotReuseLogin='passed (old controlled cookie absent)',privacy=privacy,completion=completion)
        report.update(status='passed',liveEnvironmentProcesses='passed',storageIsolation='passed',restartPersistence='passed',
            distinctHttpSocksRoutes='passed',workersAndWebSocket='passed',remoteDns='passed',guardBlocksRequests='passed',
            nativeContextClear='passed',systemEngineFallback='passed',closedBootstrapWithoutExtension='passed',productionActivityShell='passed',
            popupParentHistory='passed',closedSessionRecovery='passed (injected SDK onKill contract, real close/open/render)',
            closedParentRecovery='passed',firstPaintBeforeSlowResource='passed',cancelledLoadNotReportedAsFailure='passed',responsiveDesktopViewport='passed (controlled responsive fixture, portrait and landscape)')
        report.update(sessionCookieRestartAndLogout='passed (synthetic HttpOnly session cookie)',automaticContentRecovery='passed (injected SDK onKill, native restoreState)',profileProcessLifecycle='passed (both RESUMED)',continuousEnvironmentSwitching='passed (12 foreground changes and Home return)',realShrinkAndMagnify='passed (80%, 60%, 130%, 80%; same document and draft)',scaledKeyboardInput='passed (trusted Android tap and keyboard text)')
    except Exception as error:
        report.update(status='failed',error=f'{type(error).__name__}: {error}')
        (OUT/'failure-screen.png').write_bytes(subprocess.check_output([args.adb,'-s',args.serial,'exec-out','screencap','-p'],timeout=30))
        adb('shell','uiautomator','dump','/sdcard/gecko-failure.xml')
        (OUT/'failure-ui.xml').write_text(adb('shell','cat','/sdcard/gecko-failure.xml'))
        raise
    finally:
        if report.get('status')!='passed':(OUT/'last-device-log.txt').write_text(adb('logcat','-d'))
        report['steps']=steps
        (OUT/'device-results.json').write_text(json.dumps(report,indent=2)+'\n')
        (OUT/'device-route-trace.json').write_text(json.dumps(fixture.TRACE,indent=2)+'\n')
        (OUT/'device-native-events.txt').write_text('\n'.join(logs))
        for server in servers:server.shutdown();server.server_close()

if __name__=='__main__':main()
