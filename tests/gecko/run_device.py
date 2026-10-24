#!/usr/bin/env python3
"""Release-mode SDK in the actual app: two live processes, distinct HTTP/SOCKS routes."""
import argparse, hashlib, importlib.util, json, pathlib, select, socket, socketserver
import re, subprocess, sys, threading, time, urllib.parse, uuid
import xml.etree.ElementTree as ET

ROOT=pathlib.Path(__file__).resolve().parents[2]
OUT=ROOT/'work/gecko-integration'
sys.path.insert(0,str(ROOT/'tools/gecko'))
from check_interaction_transfer_evidence import verify_paint_case, verify_saved_file_deletion
from integration_event_contract import EventTransfer, parse_receipt_line, read_with_sequence_failure_diagnostics
from profile_invocation_contract import expected_build, verify_installed
from page_continuity_contract import verify_page_continuity
from local_draft_contract import verify_local_draft_policy
from download_resume_contract import verify_download_resume
def collect_readiness(log,identity,invocations):
    """Diagnostic sidecar only. Never feeds a business decoder or acceptance gate."""
    owners={value['runNonce']:value for value in invocations};observations=[];counts={}
    def unique(pairs):
        value={}
        for key,item in pairs:
            if key in value:raise ValueError('duplicate diagnostic JSON key')
            value[key]=item
        return value
    for line in log.splitlines():
        if ' I PocketReadiness:' not in line:continue
        raw=line.split(' I PocketReadiness:',1)[1].strip();entry=dict(raw=raw)
        try:
            if len(raw.encode('utf-8'))>3500:raise ValueError('diagnostic byte bound')
            value=json.loads(raw,object_pairs_hook=unique)
            if value.get('kind')!='readinessObservation' or value.get('schema')!=1 or value.get('diagnosticOnly') is not True or value.get('acceptance') is not False:raise ValueError('diagnostic scope')
            for key in ('sourceCommit','sourceTree','apkSha256','buildStampSha256'):
                if value.get(key)!=identity.get(key):raise ValueError('diagnostic identity '+key)
            owner=owners.get(value.get('runNonce'))
            if owner is None or value.get('fixtureAction')!=owner['fixtureAction'] or value.get('processSlot')!=owner['processSlot']:raise ValueError('diagnostic invocation ownership')
            if type(value.get('command')) is not int or value['command']<1:raise ValueError('diagnostic native command')
            if 'diagnosticError' in value:raise ValueError(value['diagnosticError'])
            point=value['observation'];index=point['observation'];nonce=value['runNonce']
            if point.get('diagnosticOnly') is not True or point.get('acceptance') is not False or point.get('maxObservations')!=24 or type(index) is not int or not 1<=index<=24:raise ValueError('diagnostic observation bound')
            if index!=counts.get(nonce,0)+1:raise ValueError('missing or duplicate diagnostic observation')
            counts[nonce]=index;entry.update(valid=True,value=value)
        except Exception as error:entry.update(valid=False,error=f'{type(error).__name__}: {error}')
        observations.append(entry)
    return dict(diagnosticOnly=True,acceptance=False,buildIdentity=identity,observations=observations,
                scope='Original independent bounded log bytes; invalid or absent observations do not complete any device assertion')

def missing_update_job(return_code, output, package):
    """Only Android's exact not-yet-registered job response is transient."""
    if return_code!=23:return False
    lines=output.strip().splitlines()
    expected=f'Could not find job 4103 in package {package} / user 0'
    if lines==[expected]:return True
    return len(lines)==2 and re.fullmatch(r'unknown\(u0a[0-9]+/jid4103\)',lines[0]) is not None and lines[1]==expected
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
class PauseTransferBarrier:
    """Keep the first real response incomplete until a real pause is accepted."""
    def __init__(self,timeout=15):
        self.timeout=timeout;self.reached=threading.Event();self.ended=threading.Event()
        self._accepted=threading.Event();self._abort=threading.Event();self._lock=threading.Lock();self._state={}
    def snapshot(self):
        with self._lock:return dict(self._state)
    def hold(self,connection,trace,held,total):
        with self._lock:
            now=time.monotonic();self._state=dict(heldBytes=held,totalBytes=total,reachedAt=now,deadline=now+self.timeout,endedAt=0,reason='',actualPauseAccepted=False)
            trace['pauseBarrier']=self._state
        self.reached.set()
        reason=''
        try:
            while not reason:
                if self._accepted.is_set():reason='actual-pause-accepted';break
                if self._abort.is_set():reason='cleanup';break
                remaining=self._state['deadline']-time.monotonic()
                if remaining<=0:reason='deadline';break
                readable,_,_=select.select([connection],[],[],min(.05,remaining))
                if readable and not connection.recv(1,socket.MSG_PEEK):reason='client-disconnect'
        except OSError:reason='client-disconnect'
        finally:
            with self._lock:self._state.update(reason=reason,endedAt=time.monotonic())
            self.ended.set()
    def accept_pause(self,gesture,phase):
        if not (gesture.get('label')=='暂停下载' and all(gesture.get(key) is True for key in ['actualAndroidInput','actualNativeView','enabled','clickable','windowFocused']) and phase.get('state')=='paused' and phase.get('userPaused') is True):
            raise AssertionError('The HTTP barrier requires an actual Android pause gesture accepted by production')
        with self._lock:
            if not self.reached.is_set() or self._state['reason'] not in {'','client-disconnect'}:raise AssertionError('The first pause HTTP barrier is unavailable')
            self._state.update(actualPauseAccepted=True,pauseAcceptedAt=time.monotonic(),gestureToken=gesture.get('token'),pauseToken=phase.get('token'),runningAtAcceptance=phase.get('running'))
        self._accepted.set()
    def abort(self):self._abort.set()
class Fixture(fixture.Fixture):
    update_transfer_trace=[]
    update_transfer_counts={}
    update_transfer_lock=threading.Lock()
    pause_barrier=None
    def update_transfer(self,scenario):
        if scenario not in {'cut','pause','ignore-range','bad-range','changed-etag','short-length','oversize','bad-hash','bad-signer','queued-cancel','cancel-restart'}:
            self.send_error(404);return
        source=OUT/('update-wrong-signer.apk' if scenario=='bad-signer' else 'update-fixture.apk')
        original=source.read_bytes();body=bytearray(original)
        if scenario=='bad-hash':body[len(body)//2]^=1
        if scenario=='oversize':body.extend(b'oversized-fixture')
        if scenario=='short-length':body=body[:-1]
        incoming_range=self.headers.get('Range','');incoming_validator=self.headers.get('If-Range','')
        with self.update_transfer_lock:
            index=self.update_transfer_counts.get(scenario,0)+1;self.update_transfer_counts[scenario]=index
            trace={'scenario':scenario,'request':index,'range':incoming_range,'ifRange':incoming_validator,'sourceBytes':len(original),'sentBytes':0}
            self.update_transfer_trace.append(trace)
        offset=0
        if incoming_range:
            if not incoming_range.startswith('bytes=') or not incoming_range.endswith('-'):
                self.send_error(416);return
            try:offset=int(incoming_range[6:-1])
            except ValueError:self.send_error(416);return
            if offset<0 or offset>=len(body):self.send_error(416);return
        ignores_range=bool(incoming_range) and scenario=='ignore-range'
        status=206 if incoming_range and not ignores_range else 200
        if ignores_range:offset=0
        etag='"synthetic-update-v2"' if incoming_range and scenario=='changed-etag' else '"synthetic-update-v1"'
        response=body[offset:];content_range=''
        if status==206:
            first=offset+1 if scenario=='bad-range' else offset
            content_range=f'bytes {first}-{len(body)-1}/{len(body)}'
        self.send_response(status);self.send_header('Content-Type','application/octet-stream');self.send_header('Content-Length',str(len(response)))
        self.send_header('Accept-Ranges','bytes');self.send_header('ETag',etag);self.send_header('Cache-Control','no-store')
        if content_range:self.send_header('Content-Range',content_range)
        self.end_headers();trace.update(status=status,etag=etag,contentRange=content_range,responseBytes=len(response))
        cut=index==1 and not incoming_range and scenario in {'cut','ignore-range','bad-range','changed-etag','queued-cancel','cancel-restart'}
        send_length=len(body)//2 if cut else len(response)
        barrier_at=(send_length-1)//16384*16384 if scenario=='pause' and index==1 and not incoming_range else -1
        try:
            for at in range(0,send_length,16384):
                if at==barrier_at:
                    if self.pause_barrier is None:raise AssertionError('First pause response requires an armed HTTP barrier')
                    self.pause_barrier.hold(self.connection,trace,trace['sentBytes'],len(body));self.close_connection=True;return
                chunk=response[at:min(at+16384,send_length)];self.wfile.write(chunk);self.wfile.flush();trace['sentBytes']+=len(chunk)
                if scenario=='pause':time.sleep(.5)
            if cut:
                trace['forcedDisconnect']=True;self.close_connection=True
                self.connection.shutdown(socket.SHUT_RDWR)
        except (BrokenPipeError,ConnectionResetError,OSError):trace['clientDisconnected']=True
        finally:trace['returnedBytes']=trace['sentBytes']
        return
    def do_POST(self):
        body=self.rfile.read(int(self.headers.get('Content-Length','0')))
        ok=self.path=='/image-received' and b'filename="photo-123.png"' in body and b'Content-Type: image/png' in body and b'\x89PNG\r\n\x1a\n' in body
        self.send_response(200 if ok else 400);self.send_header('Content-Length','0');self.end_headers()
    def do_GET(self):
        address=urllib.parse.urlparse(self.path);query=urllib.parse.parse_qs(address.query)
        if address.path.startswith('/update-transfer/'):
            return self.update_transfer(address.path.removeprefix('/update-transfer/'))
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
        elif address.path=='/browser-continuity':
            body=b'''<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><h1>Controlled page continuity</h1><textarea id="prompt-textarea"></textarea><button id="stop" data-testid="stop-button">Stop</button><script>window.__continuitySends=0;</script>'''
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
        elif address.path=='/reading-cookie-retirement':
            body=b'<!doctype html><meta charset="utf-8"><title>Owned reading cookie retirement</title>'
        elif address.path=='/browser-reading':
            body=b'''<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
            <title>Controlled responsive reading fixture</title><style>body{margin:0;font:18px sans-serif}main{padding:16px;box-sizing:border-box}#sidebar{width:260px;float:left}textarea{width:100%;height:72px;box-sizing:border-box;font:inherit}pre{overflow:auto}@media(max-width:760px){#sidebar{display:none}}</style>
            <aside id="sidebar">Controlled sidebar</aside><main id="reading-main"><h1>Controlled readable content</h1><p id="reading-paragraph">This fixture checks native viewport settings; it does not replace ChatGPT. Both left and right edges must remain readable at fit.</p><pre id="reading-code">Long code remains horizontally scrollable.........................................................................................</pre><textarea id="composer">Unsent draft stays here</textarea><div id="reading-long"></div></main><output id="reading-send-count" hidden>0</output><script>document.cookie='readingBounds=controlled-fixture; Path=/';if(new URL(location.href).searchParams.has('bounds'))for(let i=0;i<50;i++){const p=document.createElement('p');p.textContent='Controlled long reply paragraph '+i+' remains readable across fit, rotation and Android keyboard changes.';document.getElementById('reading-long').appendChild(p);}</script>'''
        elif address.path=='/f04-restore-blank':
            if (set(query)!={'nonce','command','phase'}
                    or len(query['nonce'])!=1 or re.fullmatch('[0-9a-f]{32}',query['nonce'][0]) is None
                    or len(query['command'])!=1 or re.fullmatch('[1-9][0-9]{0,18}',query['command'][0]) is None
                    or query['phase'] not in (['off'],['stale-on'],['fresh-on'])):
                self.send_error(400,'Invalid F04 blank owner');return
            body=b'<!doctype html><meta charset="utf-8"><title>Owned F04 restore preparation</title>'
        elif address.path=='/browser-session':
            token='none'
            for cookie in self.headers.get('Cookie','').split(';'):
                if cookie.strip().startswith('sessionOnly='):token=cookie.strip().split('=',1)[1]
            if query.get('action')==['sessionSeed']:token='synthetic-session-'+query.get('context',['0'])[0]
            if query.get('action')==['sessionLogout']:token='none'
            body=(f'<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
                f'<h1>Controlled session continuity</h1><p id="session-result">{token}</p><textarea id="session-draft"></textarea>').encode()
            if 'localDraft' in query:
                body+=b'''<button type="button" id="f04-send" onclick="document.getElementById('f04-sends').textContent=Number(document.getElementById('f04-sends').textContent)+1">Send controlled fixture</button><output id="f04-sends">0</output><div style="height:5000px">Controlled SDK scroll restoration</div>'''
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
    parser=argparse.ArgumentParser();parser.add_argument('--adb',required=True);parser.add_argument('--serial',default='emulator-5554');parser.add_argument('--apk',type=pathlib.Path,default=ROOT/'app/build/outputs/apk/integration/app-x86_64-integration.apk')
    modes=parser.add_mutually_exclusive_group();modes.add_argument('--reading-only',action='store_true',help='Diagnostic reading/zoom/input subset; cannot replace full device acceptance');modes.add_argument('--update-transfers-only',action='store_true',help='Diagnostic real 28-case transfer subset; cannot replace full device acceptance');args=parser.parse_args()
    diagnostic='reading' if args.reading_only else 'update-transfers' if args.update_transfers_only else ''
    device_report_name='diagnostic-reading-results.json' if args.reading_only else 'diagnostic-update-device-results.json' if args.update_transfers_only else 'device-results.json'
    update_report_name='diagnostic-update-transfers-results.json' if diagnostic else 'update-transfer-results.json'
    OUT.mkdir(parents=True,exist_ok=True)
    def adb(*parts):return subprocess.check_output([args.adb,'-s',args.serial,*parts],text=True,timeout=30)
    def adb_bytes(*parts):return subprocess.check_output([args.adb,'-s',args.serial,*parts],timeout=30)
    source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    tree=subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=ROOT,text=True).strip()
    if subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True):raise ValueError('Device evidence requires clean committed APK/source')
    gradle=(ROOT/'app/build.gradle').read_text();version=re.search(r"versionName '([^']+)'",gradle).group(1);code=int(re.search(r'versionCode (\d+)',gradle).group(1))
    identity=expected_build(args.apk.resolve(),source,tree,version,code)
    event_transfers=[]
    package='local.pocketchat.test'
    servers=[fixture.http.server.ThreadingHTTPServer(('127.0.0.1',8765),Fixture),Server(('127.0.0.1',1080),Socks),Server(('127.0.0.1',1081),HttpProxy)]
    for server in servers:threading.Thread(target=server.serve_forever,daemon=True).start()
    for port in [8765,1080,1081]:adb('reverse',f'tcp:{port}',f'tcp:{port}')
    adb('shell','pm','clear',package)
    verify_installed(json.loads(adb('exec-out','content','read','--uri','content://local.pocketchat.test.evidence/build-identity')),identity)
    sdk=int(adb('shell','getprop','ro.build.version.sdk').strip())
    if sdk>=33:adb('shell','pm','grant',package,'android.permission.POST_NOTIFICATIONS')
    # A fresh test phone needs an explicit permission response before checking app UI.
    adb('shell','wm','size','1080x2400');adb('shell','wm','density','420')
    for setting in ['window_animation_scale','transition_animation_scale','animator_duration_scale']:
        adb('shell','settings','put','global',setting,'0')
    launcher='com.google.android.apps.nexuslauncher'
    has_pixel_launcher=launcher in adb('shell','pm','list','packages',launcher)
    if diagnostic and has_pixel_launcher:adb('shell','am','force-stop',launcher) # First-boot workaround only once for a diagnostic subset.
    steps=[];logs=[];update_report=None;surface_gestures={}
    def run(context,action,kind='fixture',extra=()):
        adb('logcat','-c')
        nonce=uuid.uuid4().hex
        transfer_record=dict(runNonce=nonce,fixtureAction=action,processSlot=context-1,events=[],scope='Complete owned synthetic event bytes; no replacement of original device assertions')
        event_transfers.append(transfer_record)
        def fetch_event(uri):
            raw=adb_bytes('exec-out','content','read','--uri',uri)
            return raw
        transfer=EventTransfer(identity=identity,nonce=nonce,slot=context-1,action=action,fetch=fetch_event)
        tapped=set()
        reading_events=set();reading_trace=[];reading_lifecycle=[];reading_geometry=[];reading_readiness=None;bounds_before=None;bounds_pan=None
        surface_gestures[(context,action)]=[]
        activity='GeckoIntegrationTestActivity' if context==1 else 'ProfileGeckoIntegrationActivity1'
        if action=='downloadResume':
            assert context==8
            activity='DownloadResumeIntegrationActivity'
        # This emulator image's Pixel Launcher can ANR during first-boot package
        # optimization and intercept otherwise correct trusted taps. Stop only
        # that unrelated package before returning to the test Activity; never
        # dismiss an app ANR. The Home step still exercises real backgrounding.
        # Killing the Launcher again during stationary geometry measurement
        # makes Android recreate its taskbar/navigation mode and resize the
        # already visible browser. Keep the first-boot workaround elsewhere.
        if has_pixel_launcher and action not in {'reading','readingZoom','readingInput','readingBounds','readingBoundsProtected','readingBoundsGeometry','readingBoundsInput','readingBoundsEnd','nativeSurface','nativeCheckpoint'}:adb('shell','am','force-stop',launcher)
        adb('shell','am','start','-W','-n',package+'/local.pocketchat.'+activity,'--es','fixtureAction',action,'--es','eventNonce',nonce,*extra)
        deadline=time.monotonic()+120
        while time.monotonic()<deadline:
            output=adb('logcat','-d','-s','PocketGeckoIntegration:I','*:S')
            for line in output.splitlines():
                receipt=parse_receipt_line(line)
                if receipt is None:continue
                if receipt.get('runNonce')!=nonce or receipt.get('processSlot')!=context-1:continue
                if receipt.get('kind')=='eventTransportError':raise ValueError('Native complete event publication failed: '+str(receipt))
                event=read_with_sequence_failure_diagnostics(transfer,receipt,filtered_log=output,out=OUT,adb=args.adb,serial=args.serial)
                transfer_record['events']=transfer.records
                if action in {'readingBounds','readingBoundsProtected'} and event.get('kind') in {'readingBoundsBefore','readingBoundsPan'}:
                    if event['kind']=='readingBoundsBefore':bounds_before=event['result']
                    else:bounds_pan=event['result']
                    continue
                if action=='readingZoom' and event.get('kind') in {'readingZoomTrace','readingZoomLifecycle','readingZoomGeometry','readingZoomReadiness'}:
                    event_identity=json.dumps(event,sort_keys=True,separators=(',',':'))
                    if event_identity not in reading_events:
                        reading_events.add(event_identity);payload=event['result'];event_kind=event['kind']
                        if event_kind=='readingZoomTrace' and len(reading_trace)<96:reading_trace.append(payload)
                        elif event_kind=='readingZoomLifecycle' and len(reading_lifecycle)<16:reading_lifecycle.append(payload)
                        elif event_kind=='readingZoomGeometry' and len(reading_geometry)<16:reading_geometry.append(payload)
                        elif event_kind=='readingZoomReadiness':reading_readiness=payload
                        report.update(readingZoomTrace=reading_trace,readingZoomLifecycle=reading_lifecycle,readingZoomGeometry=reading_geometry,readingZoomReadiness=reading_readiness)
                    continue
                if event.get('kind')=='swipeNeeded':
                    point=event['result'];gesture_identity=point['id']
                    if gesture_identity not in tapped:
                        tapped.add(gesture_identity)
                        adb('shell','input','swipe',str(point['x']),str(point['fromY']),str(point['x']),str(point['toY']),str(point.get('duration',500)))
                        surface_gestures[(context,action)].append(dict(point,context=context,action=action,actualAndroidInput=True))
                    continue
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
                if event.get('kind')=='error':
                    if action=='readingZoom':
                        report['readingZoomFailure']=event['result']
                    logs.append(output);raise AssertionError(event)
                if event.get('kind')==kind:
                    result=event['result']
                    if action=='downloadResume':
                        report.setdefault('savedFileDeletion',{})['downloadResume']=result
                    assert 'error' not in result,event
                    if kind=='fixture' and (result.get('context')!=str(context) or result.get('action')!=action):continue
                    if action=='readingZoom':result.update(trace=reading_trace,lifecycle=reading_lifecycle,geometryTransitions=reading_geometry,readiness=reading_readiness)
                    if action in {'readingBounds','readingBoundsProtected'}:
                        assert bounds_before is not None and bounds_pan is not None,event
                        result.update(before=bounds_before,pan=bounds_pan)
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
    def transfer(scenario,action='transferStart',target='ready'):
        adb('logcat','-c');token=str(time.monotonic_ns());source=OUT/('update-wrong-signer.apk' if scenario=='bad-signer' else 'update-fixture.apk');data=source.read_bytes()
        adb('shell','am','start','-W','-n',package+'/local.pocketchat.AppUpdateIntegrationActivity','--es','updateAction',action,'--es','transferScenario',scenario,'--es','transferToken',token,'--es','transferTarget',target,'--es','updateHash',hashlib.sha256(data).hexdigest(),'--el','updateBytes',str(len(data)))
        expires=time.monotonic()+100
        while time.monotonic()<expires:
            raw=adb('logcat','-d','-s','PocketUpdateTransfer:I','AndroidRuntime:E','*:S');assert 'FATAL EXCEPTION' not in raw,raw
            for line in raw.splitlines():
                if 'PocketUpdateTransfer' not in line or '{' not in line:continue
                result=json.loads(line[line.index('{'):])
                if result.get('token')!=token:continue
                assert 'error' not in result,result
                update_report['cases'].append(result);print(json.dumps(dict(kind='updateTransfer',result=result)),flush=True);return result
            time.sleep(.25)
        raise TimeoutError(f'Controlled transfer {scenario}/{action}/{target} timed out')
    def transfer_check(name,passed):
        item={'name':name,'pass':bool(passed)};update_report['checks'].append(item);assert passed,item
    def update_touch(label):
        action={'暂停下载':'transferLocatePause','继续下载':'transferLocateResume'}[label]
        point=transfer('pause',action,'inspect');bounds=point['bounds']
        assert point['label']==label and all(point[key] for key in ['actualNativeView','enabled','clickable','windowFocused']),point
        assert bounds['left']<point['x']<bounds['right'] and bounds['top']<point['y']<bounds['bottom'],point
        adb('shell','input','tap',str(point['x']),str(point['y']))
        update_report['actualAndroidGestures'].append(dict(point,actualAndroidInput=True));return point
    def active_update_job(stage):
        started=time.monotonic();expires=started+6;raw='';attempts=[]
        command=[args.adb,'-s',args.serial,'shell','cmd','jobscheduler','get-job-state',package,'4103']
        while time.monotonic()<expires:
            # A trusted resume tap queues metadata preparation before Android
            # registers its Job. The shell reports that brief absence as 23;
            # it must still become an actually active Job within this deadline.
            result=subprocess.run(command,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=30);raw=result.stdout
            sample=dict(stage=stage,elapsedMs=round((time.monotonic()-started)*1000),returnCode=result.returncode,output=raw.strip());attempts.append(sample)
            update_report.setdefault('jobReadinessTrace',[]).append(sample)
            missing=missing_update_job(result.returncode,raw,package)
            if result.returncode!=0 and not missing:raise subprocess.CalledProcessError(result.returncode,command,output=raw)
            if result.returncode==0 and 'active' in raw.split():break
            time.sleep(.1)
        assert result.returncode==0 and 'active' in raw.split(),(stage,attempts)
        detail=adb('shell','dumpsys','jobscheduler');assert 'local.pocketchat.AppUpdateJob' in detail,detail
        (OUT/('update-transfer-job-'+stage+'.txt')).write_text(detail);event=dict(stage=stage,jobId=4103,state=raw.strip(),service='local.pocketchat.AppUpdateJob',readinessTrace=attempts);update_report['actualJobExecutions'].append(event);return event
    def update_transfers():
        nonlocal update_report
        Fixture.pause_barrier=PauseTransferBarrier()
        update_report=dict(status='running',sourceCommit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),diagnosticOnly=bool(diagnostic),validationScope='Diagnostic update-transfers subset; cannot replace full acceptance' if diagnostic else 'Full device acceptance',actualAndroidExecution=True,actualHttpTransfer=True,actualJobSchedulerExecution=False,checks=[],cases=[],httpTransfers=Fixture.update_transfer_trace,actualAndroidGestures=[],actualJobExecutions=[],scope='Real signed synthetic APK over controlled HTTP through the production transfer and Android JobScheduler; no synthetic APK installed.')
        original=(OUT/'update-fixture.apk').read_bytes();expected=hashlib.sha256(original).hexdigest();size=len(original)
        cut=transfer('cut',target='waiting');transfer_check('disconnectPreservesPartial',cut['partialBytes']==size//2 and cut['partialSha']==hashlib.sha256(original[:size//2]).hexdigest() and cut['partialIdentity'] and not cut['uri'])
        ready=transfer('cut','transferResume');trace=[x for x in Fixture.update_transfer_trace if x['scenario']=='cut']
        transfer_check('rangeOnlyRemaining',len(trace)==2 and trace[0]['sentBytes']==size//2 and trace[1]['range']==f'bytes={size//2}-' and trace[1]['status']==206 and trace[1]['sentBytes']==size-size//2)
        transfer_check('ifRangeValidator',trace[1]['ifRange']=='"synthetic-update-v1"')
        transfer_check('resumedShaSigner',ready['state']=='ready' and ready['finalSha']==expected and ready['finalBytes']==size and ready['sameSigner'])
        transfer_check('singleFinalApk',ready['finalApks']==1 and ready['partialBytes']==0)
        run(2,'reading','reading')
        live=transfer('pause',target='downloading');active_update_job('before-pause')
        interaction=run(2,'nativeSurface','nativeSurface');assert all(interaction[k] for k in ['stationaryGeometryDeduplicated','movedSurfaceAcceptsRealInput','documentAndDraftPreserved']),interaction
        update_report['transferNativeSurfaceGestures']=surface_gestures[(2,'nativeSurface')]
        assert len(update_report['transferNativeSurfaceGestures'])==3 and interaction['actualGestureCount']==3,interaction
        streaming=transfer('pause','transferInspect','downloading');transfer_check('chatResponsiveDuringTransfer',streaming['running'] and streaming['state']=='downloading' and streaming['partialBytes']>live['partialBytes'] and all(interaction[k] for k in ['movedSurfaceAcceptsRealInput','documentAndDraftPreserved']))
        time.sleep(2.2);progress=transfer('pause','transferInspect','downloading')
        speed=progress['bytesPerSecond'];remaining=progress['remainingSeconds']
        transfer_check('streamingStatusReadable',progress['statusReads']>=2 and 0<progress['received']<size and progress['total']==size and isinstance(progress['message'],str) and speed>0 and remaining>=0 and remaining==(progress['total']-progress['received']+speed-1)//speed and progress['speedSamplePairs']>0 and progress['speedSampleDeltaBytes']>0 and progress['speedSampleDurationMillis']>0 and progress['speedLastReceived']-progress['speedFirstReceived']==progress['speedSampleDeltaBytes'] and progress['speedLastSampleNanos']>progress['speedFirstSampleNanos'] and '/s' in progress['downloadDetailsText'] and '约剩' in progress['downloadDetailsText'])
        transfer_check('mainThreadStatusNoIo',progress['statusMainThreadIo']==0)
        transfer_check('progressKeepsViewIdentity',progress['progressIdentityPairs']>=1)
        assert Fixture.pause_barrier.reached.wait(35),'First pause HTTP barrier was not reached'
        barrier=Fixture.pause_barrier.snapshot();update_report['pauseBarrierBeforeGesture']=barrier
        assert 0<barrier['heldBytes']<size and not barrier['reason'],barrier
        update_touch('暂停下载')
        # A pause first records the user's choice, then cancels its blocked read.
        # Release only after observing that real gesture's production state;
        # the original paused/not-running oracle still follows below.
        accepted=transfer('pause','transferInspect','inspect')
        Fixture.pause_barrier.accept_pause(update_report['actualAndroidGestures'][-1],accepted)
        paused=transfer('pause','transferWaitPaused','paused')
        transfer_check('actualPauseTouch',paused['state']=='paused' and paused['userPaused'] and not paused['running'])
        transfer_check('pauseKeepsPartial',0<paused['partialBytes']<size and paused['partialIdentity'] and not paused['uri'])
        assert Fixture.pause_barrier.ended.wait(1),'Accepted pause did not release its HTTP barrier'
        barrier=Fixture.pause_barrier.snapshot();update_report['pauseBarrierAfterPause']=barrier
        assert barrier['actualPauseAccepted'] and barrier['reason'] in {'actual-pause-accepted','client-disconnect'} and 0<paused['partialBytes']<=barrier['heldBytes']<size,barrier
        before_race=len(Fixture.update_transfer_trace)
        queued_pause=transfer('pause','transferQueuedPause','paused')
        transfer_check('queuedResumeCannotOverridePause',queued_pause['commandQueueDrained'] and queued_pause['state']=='paused' and queued_pause['userPaused'] and queued_pause['partialBytes']==paused['partialBytes'] and queued_pause['partialSha']==paused['partialSha'] and queued_pause['partialIdentity'] and not queued_pause['running'] and not queued_pause['pendingTransferJob'] and len(Fixture.update_transfer_trace)==before_race)
        delayed_pause=transfer('pause','transferDelayedPause','paused')
        transfer_check('delayedPreparationKeepsPause',delayed_pause['preparationGuardReached'] and delayed_pause['commandQueueDrained'] and delayed_pause['state']=='paused' and delayed_pause['userPaused'] and delayed_pause['partialBytes']==paused['partialBytes'] and delayed_pause['partialSha']==paused['partialSha'] and delayed_pause['partialIdentity'] and not delayed_pause['running'] and not delayed_pause['pendingTransferJob'] and len(Fixture.update_transfer_trace)==before_race)
        recreated=transfer('pause','transferRecreate','inspect');transfer_check('activityRecreationKeepsPartial',recreated['pid']==paused['pid'] and recreated['partialBytes']==paused['partialBytes'] and recreated['partialSha']==paused['partialSha'] and recreated['state']=='paused')
        adb('shell','am','force-stop',package)
        restarted=transfer('pause','transferInspect','inspect');transfer_check('processRestartKeepsPartial',restarted['pid']!=paused['pid'] and restarted['partialBytes']==paused['partialBytes'] and restarted['partialSha']==paused['partialSha'] and restarted['partialIdentity'] and restarted['state']=='paused')
        update_touch('继续下载');active_update_job('after-restart');finished=transfer('pause','transferWaitReady','ready')
        transfer_check('actualResumeTouch',finished['state']=='ready' and not finished['userPaused'])
        ranges=[x for x in Fixture.update_transfer_trace if x['scenario']=='pause' and x['range']]
        transfer_check('restartResumeRange',len(ranges)==1 and ranges[0]['range']==f"bytes={paused['partialBytes']}-" and ranges[0]['ifRange']=='"synthetic-update-v1"')
        transfer_check('restartResumeComplete',finished['sameSigner'] and finished['finalSha']==expected and finished['finalBytes']==size and finished['finalApks']==1 and finished['partialBytes']==0)
        ignored=transfer('ignore-range',target='waiting');again=transfer('ignore-range','transferResume');ranges=[x for x in Fixture.update_transfer_trace if x['scenario']=='ignore-range']
        transfer_check('ignoredRangeRestartsCleanly',ignored['partialBytes']==size//2 and len(ranges)==2 and ranges[1]['status']==200 and ranges[1]['range']==f'bytes={size//2}-' and ranges[1]['sentBytes']==size and again['finalSha']==expected and again['finalBytes']==size and again['finalApks']==1)
        for scenario,name in [('bad-range','invalidContentRangeRejected'),('changed-etag','changedETagRejected')]:
            interrupted=transfer(scenario,target='waiting');invalid=transfer(scenario,'transferResume','available');requests=[x for x in Fixture.update_transfer_trace if x['scenario']==scenario]
            bad_header=len(requests)==2 and requests[1]['range']==f"bytes={interrupted['partialBytes']}-" and requests[1]['status']==206
            if bad_header:bad_header=requests[1]['contentRange'].startswith(f"bytes {interrupted['partialBytes']+1}-") if scenario=='bad-range' else requests[1]['etag']=='"synthetic-update-v2"'
            transfer_check(name,bad_header and not invalid['uri'] and invalid['partialBytes']==0 and invalid['finalApks']==0 and not invalid['downloadRequested'])
        for scenario,name in [('short-length','shortLengthRejected'),('oversize','oversizeRejected'),('bad-hash','badHashRejected'),('bad-signer','badSignerRejected')]:
            invalid=transfer(scenario,target='available');requests=[x for x in Fixture.update_transfer_trace if x['scenario']==scenario]
            reached_fixture=len(requests)==1 and requests[0]['status']==200
            if reached_fixture:
                reached_fixture=requests[0]['responseBytes']<size if scenario=='short-length' else requests[0]['responseBytes']>size if scenario=='oversize' else requests[0]['sentBytes']==requests[0]['sourceBytes']
            transfer_check(name,reached_fixture and not invalid['uri'] and invalid['partialBytes']==0 and invalid['finalApks']==0 and not invalid['downloadRequested'])
        cancel_partial=transfer('queued-cancel',target='waiting');before_cancel=len(Fixture.update_transfer_trace)
        cancelled=transfer('queued-cancel','transferQueuedCancel','available')
        transfer_check('queuedResumeCannotOverrideCancel',cancel_partial['partialBytes']==size//2 and cancelled['commandQueueDrained'] and cancelled['state']=='available' and not cancelled['downloadRequested'] and not cancelled['userPaused'] and cancelled['partialBytes']==0 and not cancelled['partialIdentity'] and not cancelled['uri'] and cancelled['finalApks']==0 and not cancelled['running'] and not cancelled['pendingTransferJob'] and len(Fixture.update_transfer_trace)==before_cancel)
        killed_partial=transfer('cancel-restart',target='waiting');killed_paused=transfer('cancel-restart','transferPause','paused')
        before_death=transfer('cancel-restart','transferCancelBeforeCleanup','inspect')
        assert before_death['cleanupWorkerBlocked'] and before_death['durableDiscardPending'] and before_death['discardPending'] and not before_death['writerWasActive'],before_death
        adb('shell','am','force-stop',package)
        after_death=transfer('cancel-restart','transferInspect','inspect')
        transfer_check('cancelledPartialClearedAfterProcessDeath',killed_partial['partialBytes']==size//2 and killed_paused['partialSha']==hashlib.sha256(original[:size//2]).hexdigest() and before_death['partialBytes']==killed_paused['partialBytes'] and before_death['partialSha']==killed_paused['partialSha'] and before_death['partialIdentity'] and after_death['pid']!=before_death['pid'] and after_death['state']=='available' and not after_death['downloadRequested'] and not after_death['discardPending'] and after_death['partialBytes']==0 and not after_death['partialIdentity'] and not after_death['pendingTransferJob'] and not after_death['uri'])
        after_cancel=transfer('cancel-restart','transferResume');requests=[x for x in Fixture.update_transfer_trace if x['scenario']=='cancel-restart']
        transfer_check('freshDownloadAfterKilledCancellation',len(requests)==2 and requests[0]['forcedDisconnect'] and requests[0]['sentBytes']==size//2 and requests[1]['range']=='' and requests[1]['ifRange']=='' and requests[1]['status']==200 and requests[1]['sentBytes']==size and after_cancel['state']=='ready' and after_cancel['finalSha']==expected and after_cancel['sameSigner'] and after_cancel['finalBytes']==size and after_cancel['finalApks']==1 and after_cancel['partialBytes']==0 and not after_cancel['discardPending'])
        update_report['cancellationProcessDeath']=dict(scope='Actual cancelled paused HTTP partial; real cleanup worker held until durable marker, then Android force-stop kills the process. No active-writer timing claim.',before=before_death,after=after_death)
        assert len(update_report['checks'])==28,update_report
        kept=transfer('cancel-restart','transferKeepPackage');keep=kept['packageDeletion']
        transfer_check('readyDeletionConfirmationRetainsPackage',keep['actualProductionDialog'] and keep['nativeButtonClicked'] and keep['dialogDismissed'] and keep['dialogLabel']=='保留安装包' and not keep['actualAndroidGesture'] and keep['phaseAfterDialog']=='ready' and keep['beforeBytes']==keep['afterBytes']==keep['beforeStoredBytes']==keep['afterStoredBytes']==size and keep['beforeSha']==keep['afterSha']==expected and keep['generationBefore']==keep['generationAfter'] and kept['state']=='ready' and kept['sameSigner'])
        stale=transfer('cancel-restart','transferStaleDelete');stale_delete=stale['packageDeletion']
        transfer_check('staleReadyDeletionRejected',stale_delete['wrongCodeRejected'] and stale_delete['wrongUriRejected'] and stale_delete['generationBefore']==stale_delete['generationAfter'] and stale_delete['beforeBytes']==stale_delete['afterBytes']==size and stale_delete['afterSha']==expected and stale['state']=='ready' and stale['finalApks']==1)
        deleted=transfer('cancel-restart','transferDeleteReady','available');delete=deleted['packageDeletion']
        transfer_check('confirmedReadyPackageRemoved',delete['actualProductionDialog'] and delete['nativeButtonClicked'] and delete['dialogDismissed'] and delete['dialogLabel']=='删除安装包' and not delete['actualAndroidGesture'] and delete['phaseAfterDialog']=='deleting' and delete['beforeBytes']==delete['beforeStoredBytes']==size and delete['beforeSha']==expected and delete['afterBytes']==delete['afterStoredBytes']==delete['ownedFiles']==0 and delete['oldUriRejected'] and delete['generationAfter']>delete['generationBefore'] and deleted['state']=='available' and not deleted['uri'] and not deleted['discardPending'] and not deleted['downloadRequested'] and not deleted['pendingTransferJob'] and deleted['received']==deleted['partialBytes']==deleted['finalApks']==0)
        transfer_check('deletionCancelsQueuedVerification',delete['queuedVerifyRequest']>0 and delete['verifyRequestedSerial']>delete['queuedVerifyRequest'] and delete['verifiedSerial']==0 and delete['pendingInstallCleared'] and deleted['state']=='available')
        transfer_check('readyDeletionPreservesPreferences',delete['sameMetadata'] and delete['sameSettings'] and not delete['packageDeleteRetry'] and delete['cancelledCode']==delete['releaseCode'])
        requests_before_auto=len(Fixture.update_transfer_trace);suppressed=transfer('cancel-restart','transferAutomaticSuppression','available');automatic=suppressed['packageDeletion']
        transfer_check('deletedReleaseDoesNotAutoDownload',automatic['automaticAdmissionAttempted'] and len(Fixture.update_transfer_trace)==requests_before_auto and automatic['beforeBytes']==automatic['afterBytes']==automatic['afterStoredBytes']==0 and automatic['cancelledCode']==automatic['releaseCode'] and automatic['sameMetadata'] and automatic['sameSettings'] and suppressed['state']=='available' and not suppressed['downloadRequested'] and not suppressed['pendingTransferJob'] and not suppressed['uri'])
        transfer_check('packageDeletionStatusNoIo',deleted['statusMainThreadIo']==suppressed['statusMainThreadIo']==0)
        redownloaded=transfer('cancel-restart','transferResume');requests=[x for x in Fixture.update_transfer_trace if x['scenario']=='cancel-restart']
        transfer_check('explicitRedownloadAfterPackageDeletion',len(requests)==3 and requests[-1]['range']==requests[-1]['ifRange']=='' and requests[-1]['status']==200 and requests[-1]['sentBytes']==size and redownloaded['state']=='ready' and redownloaded['finalSha']==expected and redownloaded['sameSigner'] and redownloaded['finalBytes']==size and redownloaded['finalApks']==1 and redownloaded['partialBytes']==0 and not redownloaded['discardPending'])
        update_report['readyPackageDeletion']=dict(scope='Real signed ready APK and actual production confirmation buttons via native performClick; no Android input-gesture claim. Existing worker holds queued verification until confirmation, then actual owned byte/URI cleanup and automatic/manual admission are measured.',kept=kept,stale=stale,deleted=deleted,suppressed=suppressed,redownloaded=redownloaded)
        assert len(update_report['checks'])==36,update_report
        update_report.update(status='passed',checkCount=len(update_report['checks']),actualJobSchedulerExecution=len(update_report['actualJobExecutions'])==2,chatInteraction=interaction)
        (OUT/update_report_name).write_text(json.dumps(update_report,indent=2)+'\n')
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
    report={'actualAndroidExecution':True,'releaseMode':True,'diagnosticOnly':bool(diagnostic),'validationScope':f'Diagnostic {diagnostic} subset; cannot replace full acceptance' if diagnostic else 'Full device acceptance','androidSdk':sdk,'androidAbi':adb('shell','getprop','ro.product.cpu.abi').strip(),'viewport':'1080x2400 / 420 dpi','sourceCommit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'googleLogin':'not-tested','internalMihomoRoute':'reuses production API; no live subscription provided'}
    def reading_checks():
        reading=[]
        for size in ['945x2100','1024x2240','1128x2400','1920x1080']:
            adb('shell','wm','size',size)
            result=run(1,'reading','reading');reading.append(dict(size=size,**result))
            assert result['mobileViewport'] and result['desktopIdentity'] and 'Android' not in result['userAgent'],result
            assert result['compositorMeasured'] and result['nativeScale']>0 and abs(result['viewport']*result['nativeScale']-result['nativeWidth'])<5 and abs(result['scale']-1)<.02,result
            assert result['sidebarHidden'] and result['composerWidth']>=result['viewport']-34 and result['draft']=='Unsent draft stays here',result
            (OUT/f'reading-{size}.png').write_bytes(subprocess.check_output([args.adb,'-s',args.serial,'exec-out','screencap','-p'],timeout=30))
        report['responsiveReading']=reading
        adb('shell','wm','size','1080x2400');run(1,'reading','reading')
        observed=run(1,'readingZoom','readingZoom');zoom=observed['checks'];report['nativeReadingZoom']=zoom;report['readingZoomTrace']=observed['trace'];report['readingZoomReadiness']=observed['readiness']
        assert len(zoom)==4 and len({x['document'] for x in zoom})==1 and all(x['draft']=='Unsent draft stays here' for x in zoom),zoom
        for x in zoom:assert abs(x['shownFontPixels']/(18*x['density'])-x['choice'])<.06,x
        assert zoom[1]['shownFontPixels']<zoom[0]['shownFontPixels']<zoom[2]['shownFontPixels'],zoom
        (OUT/'reading-shrunk-80.png').write_bytes(subprocess.check_output([args.adb,'-s',args.serial,'exec-out','screencap','-p'],timeout=30))
        typed=run(1,'readingInput','readingInput');assert typed['focused']=='composer' and 'native-input-ok' in typed['draft'] and abs(typed['choice']-.8)<.02,typed
        report['scaledReadingInput']=typed;adb('shell','input','keyevent','KEYCODE_BACK')
        cases=[]
        for action,level in [('readingBounds',0),('readingBoundsProtected',2)]:
            result=run(1,action,'readingBounds');assert result['schema']==1 and result['privacyLevel']==level and result['actualGeckoExecution'] and result['protectionAcknowledged'] and result['fitUsedProductionController'],result
            before,pan,after=(result[key] for key in ('before','pan','after'))
            assert abs(before['choice']-4.2)<.001 and abs(before['matrixScale']*before['layout']*before['viewport']/before['nativeWidth']-4.2)<.05,before
            assert abs(pan['nativeScrollX']-48)<=1 and abs(pan['pageLeft']-48)<=1 and abs(pan['nativeScrollY']-320)<=1,pan
            assert abs(after['nativeScrollY']-pan['nativeScrollY'])<=1 and result['stableSamples']>=5 and result['stableMillis']>=500,result
            assert after['codeScrollWidth']>after['codeWidth'] and after['codeLeft']>0,after
            assert result['fingerprintingProtected']==(level==2),result
            assert len({item['document'] for item in (before,pan,after)})==1 and len({item['sessionIdentity'] for item in (before,pan,after)})==1 and len({item['surfaceIdentity'] for item in (before,pan,after)})==1,result
            assert all(item['draft']=='Unsent draft stays here' and item['cookie']==before['cookie'] and item['bodyHash']==before['bodyHash'] and item['sends']==0 for item in (pan,after)),result
            assert 'readingBounds=controlled-fixture' in before['cookie'],before
            cases.append(result)
            (OUT/f'reading-fit-privacy-{level}.png').write_bytes(subprocess.check_output([args.adb,'-s',args.serial,'exec-out','screencap','-p'],timeout=30))
        report['nativeReadingBounds']=dict(schema=1,cases=cases)
        prior_accelerometer=adb('shell','settings','get','system','accelerometer_rotation').strip();prior_rotation=adb('shell','settings','get','system','user_rotation').strip()
        try:
            adb('shell','settings','put','system','accelerometer_rotation','0')
            geometry=[]
            for phase,rotation in [('landscape','1'),('portrait','0')]:
                adb('shell','settings','put','system','user_rotation',rotation)
                value=run(1,'readingBoundsGeometry','readingBoundsGeometry',('--es','geometryPhase',phase));geometry.append(value)
                assert value['phase']==phase and value['measurement']['document']==cases[-1]['after']['document'] and value['measurement']['activityIdentity']==cases[-1]['after']['activityIdentity'],value
                (OUT/f'reading-fit-{phase}.png').write_bytes(subprocess.check_output([args.adb,'-s',args.serial,'exec-out','screencap','-p'],timeout=30))
            report['nativeReadingBounds']['rotation']=geometry
            input_result=run(1,'readingBoundsInput','readingBoundsInput');assert input_result['imeVisible'] and input_result['imeBottom']>0 and all(input_result[key] for key in ('sameDocument','sameCookie','draftPreserved')),input_result
            measured=input_result['measurement'];composer=measured['blocks'][2];physical=measured['composerPhysicalRect'];visible=measured['visibleSurfaceRect']
            assert composer['top']>=measured['offsetTop']-1 and composer['bottom']<=measured['offsetTop']+measured['visualHeight']+1,measured
            assert physical['bottom']>physical['top'] and physical['top']>=visible['top']-2 and physical['bottom']<=min(visible['bottom'],measured['imeTopPixels'])+2 and physical['left']>=visible['left']-2 and physical['right']<=visible['right']+2,measured
            assert measured['nativeComposerFits'] and measured['productionKeyboardController'] and measured['nativeFocusRequests']>0 and measured['nativeFocusMeasurements']>0 and len(measured['pageToSurfaceMatrix'])==9,measured
            assert measured['imeTopPixels']==measured['windowBounds']['bottom']-input_result['imeBottom'] and (not measured['nativeFocusWasClipped'] or measured['nativeFocusScrolls']>0 and abs(measured['nativeFocusScrollDeltaCss'])>0),measured
            report['nativeReadingBounds']['input']=input_result
            (OUT/'reading-fit-keyboard.png').write_bytes(subprocess.check_output([args.adb,'-s',args.serial,'exec-out','screencap','-p'],timeout=30))
            adb('shell','input','keyevent','KEYCODE_BACK');ended=run(1,'readingBoundsEnd','readingBoundsEnd');assert ended['productionDelegateRestored'] and ended['privacyRestored'],ended
            report['nativeReadingBounds']['productionDelegateRestored']=True
            report['nativeReadingBounds']['privacyRestored']=True
        finally:
            for key,value in [('user_rotation',prior_rotation),('accelerometer_rotation',prior_accelerometer)]:
                if value=='null':adb('shell','settings','delete','system',key)
                else:adb('shell','settings','put','system',key,value)
        # The completed new cases retain their own same-document evidence.
        # Return to the original short fixture for its independent stationary
        # surface benchmark; its three swipes must not move the composer away.
        run(1,'reading','reading')
    try:
        if args.reading_only:
            reading_checks();report.update(status='passed',checkCount=14,scope='Diagnostic subset only: four responsive widths, four exact zoom choices, actual Android input, two native fit cases, two actual rotations and an IME fit case. Not full release evidence.');return
        if args.update_transfers_only:
            update_transfers();report.update(status='passed',scope='Diagnostic subset only: all 28 real transfer checks. Not full release evidence.');return
        usability=run(1,'usability','usability');assert usability['documentPreserved'] and usability['mobileVisible'] and usability['upload']=='sample.txt:synthetic-upload' and usability['csv']=='name,value\nsynthetic,42\n' and usability['blob']==usability['csv'],usability
        report['browserUsability']=usability
        image=run(1,'desktopImage','desktopImage');assert all(image[k] for k in ['productionChooserOpened','imageMimeAndMultiple','pendingPreserved','noPhantomUpload','desktop']) and image['upload']=='ok:photo-123.png:image/png:4x3',image
        report['desktopImageUpload']=image
        own_image=run(1,'desktopOwnImage','desktopImage');assert all(own_image[k] for k in ['productionChooserOpened','imageMimeAndMultiple','pendingPreserved','noPhantomUpload','desktop']) and own_image['upload']=='ok:photo-123.png:image/png:4x3',own_image
        report['ownProviderImageUpload']=own_image
        upload_lifecycle=run(1,'uploadLifecycle','uploadLifecycle')
        assert all(upload_lifecycle[k] is True for k in ['atomicHandoff','dismissedOnce','closedPromptResultIgnored','preparationCleanup']),upload_lifecycle
        report['uploadPromptLifecycle']=upload_lifecycle
        continuity=run(1,'pageContinuity','pageContinuity')
        assert continuity['status']=='passed' and all(continuity[k] is True for k in ['readinessNoReload','busyRecoveryPreserved','failedProbePreserved','emptyTimeoutManualOnly','ownedCookieCleaned','resourcesRestored','persistedPendingRestored']),continuity
        assert continuity['checkCount']==len(continuity['checks']) and all(item['pass'] is True for item in continuity['checks']),continuity
        verify_page_continuity(continuity)
        report['pageContinuity']=continuity
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
        # F04 uses a separate private fixture store. Each next invocation reads
        # after Android has killed the previous process, then restores through
        # the real SDK; it does not replace the original automatic-startup cases.
        draft_policy=[];draft_stops=[]
        for phase in ['seed','off','stale-on','fresh-on']:
            value=run(2,'localDraftPolicy','localDraftPolicy',('--es','draftPhase',phase))
            draft_policy.append(value)
            if phase!='fresh-on':
                command=['shell','am','force-stop',package]
                draft_stops.append(dict(afterPhase=phase,beforePid=value['pid'],command=command,
                    stdout=adb(*command),returnCode=0))
        report['localDraftPolicy']=dict(schema=1,phases=draft_policy,forceStopBetweenPhases=True,
            forceStops=draft_stops,automaticStartupSelectionAcceptance=False)
        verify_local_draft_policy(report['localDraftPolicy'])
        paint=run(1,'earlyPaint','paint');assert paint['firstPaintBeforeComplete'],paint
        first_paint_case=verify_paint_case(paint)
        reading_checks()
        surface=run(1,'nativeSurface','nativeSurface');assert all(surface[k] for k in ['stationaryGeometryDeduplicated','movedSurfaceAcceptsRealInput','documentAndDraftPreserved']),surface
        report['nativeSurfacePerformance']=surface;report['nativeSurfaceGestures']=surface_gestures[(1,'nativeSurface')]
        assert len(report['nativeSurfaceGestures'])==3 and surface['actualGestureCount']==3,surface
        adb('shell','input','keyevent','KEYCODE_BACK')
        checkpoint=run(1,'nativeCheckpoint','nativeCheckpoint')
        assert all(checkpoint[k] for k in ['readingFixtureCookieRemovedFromDom','readingFixtureCookieRemovedFromNative','otherDomCookiesPreserved','otherNativeCookiesPreserved']),checkpoint
        assert all(checkpoint[k] for k in ['mainSerializationZero','pendingBounded','latestWinsDuringSerialization','oversizeKeepsPrevious','independentStore','validAfterNullCandidate','validAfterThrowingCandidate','validAfterUtf8Oversize','invalidNewerKeepsValid','continuousOffersPersisted','sdkSnapshotRestorable']),checkpoint
        assert checkpoint['mainSerialized']==0 and checkpoint['firstBurstSerialized']==1 and checkpoint['firstBurstCoalesced']==999 and checkpoint['lastCandidate']==1199 and checkpoint['lastValidCandidate']==2002 and checkpoint['continuousLastCandidate']==4199 and checkpoint['continuousOffered']==200 and checkpoint['continuousWritesDuringOffers']>=1,checkpoint
        report['nativeCheckpointPerformance']=checkpoint
        cancelled=run(1,'cancelLoad','cancelledLoad');assert not cancelled['reportedFailure'] and not cancelled['pageError'] and cancelled['visibleDocumentRetained'] and cancelled['documentReadyBeforeStop'],cancelled
        cancelled_paint_case=verify_paint_case(cancelled,cancelled=True)
        assert cancelled_paint_case['serial']>first_paint_case['serial'] and cancelled_paint_case['target']!=first_paint_case['target'],cancelled
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
        # Historical system/simple preferences must open the existing official
        # Gecko profiles without changing their stored environment data.
        adb('shell','am','force-stop',package)
        legacy=[]
        for context in [1,2]:
            result=run(context,'legacyEnginePreference');check(result,context,True)
            proof=result['legacyEngineCompatibility']
            assert all(proof[key] for key in ['actualGecko','oldPreferencesPreserved','systemEngineRefused','sameSdkSession','sameSurface','sameDocument','sameProtectedRoute']),proof
            assert proof['systemWebViews']==0,proof
            legacy.append(dict(context=context,**proof))
        assert run(1,'sessionRead','session')['token']=='none'
        assert run(2,'sessionRead','session')['token']=='synthetic-session-2'
        report['legacyEngineCompatibility']=legacy
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
        assert bootstrap['extensionId']=='browser@pocketchat.local' and bootstrap['enabledAfterDisable'] is False and bootstrap['disabledFlags']&2,bootstrap
        restored_bootstrap=run(1,'restoreExtension','bootstrapRestore')
        before=restored_bootstrap['ensureBefore'];enabled=restored_bootstrap['enableResult'];after=restored_bootstrap['ensureAfter']
        assert before['id']==enabled['id']==after['id']=='browser@pocketchat.local' and before['version']==enabled['version']==after['version'],restored_bootstrap
        assert before['enabled'] is False and before['disabledFlags']&2 and enabled['enabled'] is True and after['enabled'] is True and not after['disabledFlags']&2,restored_bootstrap
        assert restored_bootstrap['enableSource']=='USER' and all(restored_bootstrap[key] for key in ['newNativeRoutePort','privacyReady','nativeProtectionAcknowledged']),restored_bootstrap
        assert restored_bootstrap['protectionLevel']==restored_bootstrap['expectedProtectionLevel'] and restored_bootstrap['guardBefore']==restored_bootstrap['guardAfter'] and restored_bootstrap['networkReadyBefore']==restored_bootstrap['networkReadyAfter'],restored_bootstrap
        report['closedBootstrapCleanup']=restored_bootstrap
        check(run(2,'read'),2,True)
        # Exercise the real outer Activity after moving its retained Gecko surface.
        adb('logcat','-c')
        adb('shell','am','start','-n',package+'/local.pocketchat.MainActivity','--es','openWindowAction','native-smoke')
        time.sleep(4)
        assert adb('shell','pidof',package).strip(),'Production Activity exited'
        adb('shell','uiautomator','dump','/sdcard/gecko-production.xml')
        hierarchy=adb('shell','cat','/sdcard/gecko-production.xml')
        (OUT/'production-ui.xml').write_text(hierarchy)
        for label in ['会话','环境','下载','网络','设置']:assert label in hierarchy,(label,hierarchy)
        assert not any(node.attrib.get('text') in ['简洁','原网页'] for node in ET.fromstring(hierarchy).iter('node')),hierarchy
        assert 'FATAL EXCEPTION' not in adb('logcat','-d','-s','AndroidRuntime:E','*:S')
        update_checks=[]
        for action in ['badHash','badSigner','cancel']:
            result=update(action);update_checks.append(result)
            assert result['state']=='available' and not result['uri'] and result['downloadId']==-1,result
            if action=='badHash':assert '不完整' in result['message'],result
            if action=='badSigner':assert '签名' in result['message'],result
            if action=='cancel':assert '取消' in result['message'],result
        held_cancel=update('cancelDuringQuery')
        assert all(held_cancel[key] for key in ['actualSystemQuery','queryHeldAfterReturn','queryReturnedAfterCancel','productionProviderCancel','productionPollDrained','cleanupWorkerDrained','systemRecordRemoved','sameRelease']),held_cancel
        assert held_cancel['ownedDownloadId']>0 and held_cancel['generationAfterCancel']>held_cancel['generationBeforeCancel'] and held_cancel['cancelledDownloadId']==-1,held_cancel
        assert held_cancel['queriedUri']=='http://127.0.0.1:8765/update-wait' and held_cancel['systemRowId']==held_cancel['ownedDownloadId'] and held_cancel['cursorClass'] and held_cancel['cursorStatusBeforeCancel'] in [1,2,4],held_cancel
        assert held_cancel['cancelState']=='available' and held_cancel['state']=='available' and '取消' in held_cancel['message'] and held_cancel['downloadId']==-1 and not held_cancel['uri'],held_cancel
        assert held_cancel['received']==0 and not held_cancel['downloadRequested'] and not held_cancel['pendingTransferJob'] and not held_cancel['finalFilePresent'] and held_cancel['pid']==held_cancel['finalPid'],held_cancel
        report['legacyDownloadCancelDuringQuery']=held_cancel
        good=update('good');assert good['state']=='ready' and good['uri'].startswith('content://'+package+'.app-updates/'),good
        access=update('verifyAccess');assert access['readOnly'] and access['traversalRejected'] and access['sameSigner'],access
        update('showUi');time.sleep(1)
        adb('shell','uiautomator','dump','/sdcard/update-ui.xml');update_ui=adb('shell','cat','/sdcard/update-ui.xml');(OUT/'update-ui.xml').write_text(update_ui)
        for label in ['应用更新','当前版本','安装更新','删除安装包','自动检查更新','Wi-Fi 下自动下载新版']:assert label in update_ui,(label,update_ui)
        (OUT/'update-ui.png').write_bytes(subprocess.check_output([args.adb,'-s',args.serial,'exec-out','screencap','-p'],timeout=30))
        adb('shell','appops','set',package,'REQUEST_INSTALL_PACKAGES','allow')
        button=next(node for node in ET.fromstring(update_ui).iter('node') if node.attrib.get('text')=='安装更新')
        x1,y1,x2,y2=map(int,re.findall(r'\d+',button.attrib['bounds']))
        adb('shell','input','tap',str((x1+x2)//2),str((y1+y2)//2));time.sleep(3)
        adb('shell','uiautomator','dump','/sdcard/update-installer-ui.xml');installer_ui=adb('shell','cat','/sdcard/update-installer-ui.xml');(OUT/'update-installer-ui.xml').write_text(installer_ui)
        assert 'packageinstaller' in installer_ui and ('Update' in installer_ui or '更新' in installer_ui),installer_ui
        adb('shell','input','keyevent','KEYCODE_BACK') # Never install the synthetic replacement.
        report['appUpdates']=dict(downloadManager='passed (real system HTTP transfer)',good=good,failures=update_checks,cancelDuringQuery=held_cancel,provider=access,settingsUi='passed',androidInstaller='passed (opened; synthetic APK not installed)')
        deleted_files=run(1,'deleteDownloads','downloadDeletion')
        verify_saved_file_deletion(deleted_files)
        report['savedFileDeletion']=dict(deleted_files)
        resumed_files=run(8,'downloadResume','downloadResume')
        report['savedFileDeletion']['downloadResume']=resumed_files
        verify_download_resume(resumed_files,identity)
        update_transfers()
        report['appUpdateTransfer']='passed (real HTTP interruption, durable Range resume, Android JobScheduler, pause/resume touch and concurrent controlled browser input)'
        cleanup=run(2,'readingFixtureCookieCleanup','readingFixtureCookieCleanup')
        assert cleanup['schema']==1 and cleanup['processSlot']==1 and cleanup['cookie']=='readingBounds=controlled-fixture' and cleanup['cookiePath']=='/' and all(cleanup[key] is True for key in ('sameSession','sameDocument','sameUrl','readingFixtureCookieRemovedFromDom','readingFixtureCookieRemovedFromNative','otherDomCookiesPreserved','otherNativeCookiesPreserved')),cleanup
        report['readingFixtureCookieCleanup']=cleanup
        check(run(1,'seed'),1,True);check(run(2,'seed'),2,True)
        lifecycle=management('copyAndReset')
        check(run(2,'read'),2,False);check(run(1,'read'),1,True)
        check(run(2,'seed'),2,True)
        reset_zero=management('resetZero')
        check(run(1,'read'),1,False);check(run(2,'read'),2,True)
        queued=run(2,'queuedChanges','queuedChanges');assert all(queued[key] for key in ['savedWhileReplying','oldRouteKept','browserSavedWithoutApplying','replyCleared','appliedWhenIdle','vpnGuardBlocksWithoutVpn']),queued
        foreign_before=run(1,'foreignPreferences','foreignPreferences');assert foreign_before['marker']=='prime-target',foreign_before
        deletion=management('deleteOne')
        foreign_after=run(1,'foreignPreferences','foreignPreferences');assert not foreign_after['marker'],foreign_after
        check(run(2,'read'),2,False)
        background_settings=run(2,'backgroundSettings','backgroundSettings');assert all(background_settings.values()),background_settings
        deletion_zero=management('deleteZero')
        report['environmentManagement']=dict(queued=queued,backgroundSettings=background_settings,copyAndReset=lifecycle,resetZero=reset_zero,resetLoginData='passed (actual production maintenance, synthetic Gecko cookie/storage and another environment retained)',deleteOne=deletion,deleteZero=deletion_zero,foreignPreferenceCache='passed (live parent sees cleared preferences)',slotReuseLogin='passed (old controlled cookie absent)',privacy=privacy,completion=completion)
        report.update(status='passed',liveEnvironmentProcesses='passed',storageIsolation='passed',restartPersistence='passed',
            distinctHttpSocksRoutes='passed',workersAndWebSocket='passed',remoteDns='passed',guardBlocksRequests='passed',
            nativeContextClear='passed',legacyEnginePreferenceCompatibility='passed (official Gecko, stored preferences and isolated data retained; system engine refused)',closedBootstrapWithoutExtension='passed',productionActivityShell='passed',
            popupParentHistory='passed',closedSessionRecovery='passed (injected SDK onKill contract, real close/open/render)',
            closedParentRecovery='passed',firstPaintBeforeSlowResource='passed',cancelledLoadNotReportedAsFailure='passed',responsiveDesktopViewport='passed (controlled responsive fixture, portrait and landscape)')
        report.update(sessionCookieRestartAndLogout='passed (synthetic HttpOnly session cookie)',automaticContentRecovery='passed (injected SDK onKill, native restoreState)',profileProcessLifecycle='passed (both RESUMED)',continuousEnvironmentSwitching='passed (12 foreground changes and Home return)',realShrinkAndMagnify='passed (80%, 60%, 130%, 80%; same document and draft)',scaledKeyboardInput='passed (trusted Android tap and keyboard text)')
    except Exception as error:
        report.update(status='failed',error=f'{type(error).__name__}: {error}')
        if update_report is not None and update_report.get('status')!='passed':
            update_report.update(status='failed',error=f'{type(error).__name__}: {error}',checkCount=len(update_report['checks']))
        raise
    finally:
        import sys
        primary_error=sys.exc_info()[1]
        if Fixture.pause_barrier is not None:
            Fixture.pause_barrier.abort()
            if Fixture.pause_barrier.reached.is_set():Fixture.pause_barrier.ended.wait(1)
        prefix=f'diagnostic-{diagnostic}-' if diagnostic else ''
        report['steps']=steps
        report['eventTransport']=dict(schema=1,buildIdentity=identity,invocations=event_transfers,scope='Source/APK/nonce/slot/action/sequence and exact UTF-8 size/SHA-bound file handoff; original full event results and assertions remain unchanged')
        artifact_errors=report.setdefault('artifactErrors',[]);persistence_errors=[]
        def artifact(name,save,required=False):
            try:save()
            except Exception as error:
                artifact_errors.append(dict(artifact=name,error=f'{type(error).__name__}: {error}'))
                if required:persistence_errors.append(error)
        def write_reports():
            artifact(device_report_name,lambda:(OUT/device_report_name).write_text(json.dumps(report,indent=2)+'\n'),True)
            if update_report is not None:
                update_report['artifactErrors']=artifact_errors
                artifact(update_report_name,lambda:(OUT/update_report_name).write_text(json.dumps(update_report,indent=2)+'\n'),True)
        # Preserve the source, original failure and completed steps before any
        # optional ADB evidence: an unavailable phone must not hide an assertion.
        write_reports()
        if report.get('status')!='passed':
            artifact('failure-screen.png',lambda:(OUT/'failure-screen.png').write_bytes(subprocess.check_output([args.adb,'-s',args.serial,'exec-out','screencap','-p'],timeout=30)))
            def failure_ui():
                adb('shell','uiautomator','dump','/sdcard/gecko-failure.xml')
                (OUT/'failure-ui.xml').write_text(adb('shell','cat','/sdcard/gecko-failure.xml'))
            artifact('failure-ui.xml',failure_ui)
            artifact(prefix+'last-device-log.txt',lambda:(OUT/(prefix+'last-device-log.txt')).write_text(adb('logcat','-d')))
            artifact(prefix+'device-readiness-observations.json',lambda:(OUT/(prefix+'device-readiness-observations.json')).write_text(json.dumps(collect_readiness((OUT/(prefix+'last-device-log.txt')).read_text(),identity,event_transfers),indent=2)+'\n'))
            # Read-only post-failure evidence. These commands do not run inside
            # the original result deadline and cannot turn its error into pass.
            def failure_runtime():
                observations=[]
                for command in [('dumpsys','activity','activities'),('dumpsys','window','windows'),('ps','-A'),('cat','/proc/meminfo')]:
                    try:
                        value=subprocess.run([args.adb,'-s',args.serial,'shell',*command],capture_output=True,text=True,timeout=5)
                        observations.append(dict(command=list(command),returnCode=value.returncode,stdout=value.stdout[:131072],stderr=value.stderr[:4096],truncated=len(value.stdout)>131072 or len(value.stderr)>4096))
                    except Exception as error:observations.append(dict(command=list(command),error=f'{type(error).__name__}: {error}'))
                (OUT/(prefix+'device-failure-runtime.json')).write_text(json.dumps(dict(diagnosticOnly=True,acceptance=False,sourceCommit=identity['sourceCommit'],buildIdentity=identity,originalError=report.get('error'),observations=observations),indent=2)+'\n')
            artifact(prefix+'device-failure-runtime.json',failure_runtime)
        if update_report is not None and update_report.get('status')!='passed':
            artifact(prefix+'update-transfer-failure-log.txt',lambda:(OUT/(prefix+'update-transfer-failure-log.txt')).write_text(adb('logcat','-d')))
        artifact(prefix+'device-route-trace.json',lambda:(OUT/(prefix+'device-route-trace.json')).write_text(json.dumps(fixture.TRACE,indent=2)+'\n'))
        artifact(prefix+'device-native-events.txt',lambda:(OUT/(prefix+'device-native-events.txt')).write_text('\n'.join(logs)))
        for index,server in enumerate(servers):
            artifact(f'fixture-server-{index}-shutdown',server.shutdown)
            artifact(f'fixture-server-{index}-close',server.server_close)
        # Record evidence-collection failures while re-raising the original
        # exception. Missing required JSON still fails an otherwise passing run.
        if persistence_errors and primary_error is None:
            error=persistence_errors[0];report.update(status='failed',error=f'{type(error).__name__}: {error}')
        write_reports()
        if persistence_errors and primary_error is None:raise persistence_errors[0]

if __name__=='__main__':main()
