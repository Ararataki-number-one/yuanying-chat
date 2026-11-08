#!/usr/bin/env python3
"""Real version-2 native navigation; no fixture-driven reveal or input replay."""
import hashlib,json,pathlib,re,subprocess,sys,time,uuid

ROOT=pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/gecko'))
from chrome_collapse_contract_v2 import NAMES,PHASES,INPUT_PATHS,reading_swipe_points,verify_case,verify_auto_collapse_v2
from integration_event_contract import EventTransfer,parse_receipt_line
from profile_invocation_contract import expected_build,verify_installed
from run_chrome_collapse import current_resumed,component_name,resume_transport
from ui_visual_capture import UiVisualCapture

def immutable_inputs(source):
    result={}
    for path in INPUT_PATHS:
        raw=(ROOT/path).read_bytes()
        selected=subprocess.check_output(['git','show',source+':'+path],cwd=ROOT)
        if raw!=selected:raise ValueError('Chrome v2 source changed: '+path)
        result[path]=hashlib.sha256(raw).hexdigest()
    return result

def home_resume(component,inputs,argv=None):
    """One HOME, an observed current HOME, then one return in 20 seconds."""
    started=time.monotonic();deadline=started+20;prefix=resume_transport(sys.argv[1:] if argv is None else argv)
    def adb(*parts):
        remaining=deadline-time.monotonic()
        if remaining<=0:raise TimeoutError('Chrome v2 HOME deadline expired')
        try:value=subprocess.run(prefix+list(parts),check=True,text=True,errors='replace',stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=min(90,remaining))
        except subprocess.TimeoutExpired as error:raise TimeoutError(('Chrome v2 HOME command timed out',parts,error.stdout,error.stderr)) from error
        if time.monotonic()>=deadline:raise TimeoutError('Chrome v2 HOME deadline expired during command')
        return value.stdout
    user=adb('shell','am','get-current-user').strip()
    if re.fullmatch('[0-9]+',user) is None:raise ValueError('Unrecognized current Android user')
    raw=adb('shell','cmd','package','resolve-activity','--brief','--user',user,'-a','android.intent.action.MAIN','-c','android.intent.category.HOME')
    homes=[component_name(x.strip()) for x in raw.splitlines() if re.fullmatch(r'[A-Za-z0-9_.]+/[A-Za-z0-9_.$]+',x.strip())]
    if len(homes)!=1 or homes[0]==component:raise ValueError('A distinct actual HOME is required')
    observations=[]
    def wait(target):
        while time.monotonic()<deadline:
            state=adb('shell','dumpsys','activity','activities')
            if current_resumed(state)=={(int(user),target)}:
                observations.append(dict(component=target,androidUser=int(user),activityState=state));return
            time.sleep(min(.2,max(0,deadline-time.monotonic())))
        raise TimeoutError(('Chrome v2 HOME barrier',target))
    adb('shell','input','keyevent','KEYCODE_HOME');inputs.append(dict(kind='key',label='home',key='KEYCODE_HOME',actualAndroidInput=True))
    wait(homes[0])
    adb('shell','am','start','-W','--activity-single-top','-n',component)
    inputs.append(dict(kind='activity-start',label='activityResume',component=component,actualAndroidInput=True))
    wait(component)
    return dict(home=homes[0],returned=component,androidUser=int(user),homeObservedBeforeStart=True,observations=observations,elapsedSeconds=time.monotonic()-started)

def run(adb,adb_bytes,source,trace,out,focus):
    package='local.pocketchat.test';component=package+'/local.pocketchat.CompactChromeIntegrationActivity'
    action=package+'.CHROME_COLLAPSE';tree=subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=ROOT,text=True).strip()
    gradle=(ROOT/'app/build.gradle').read_text();inputs_before=immutable_inputs(source)
    identity=expected_build(out/'ui-current.apk',source,tree,re.search(r"versionName '([^']+)'",gradle).group(1),int(re.search(r'versionCode (\d+)',gradle).group(1)))
    verify_installed(json.loads(adb('exec-out','content','read','--uri','content://'+package+'.evidence/build-identity')),identity)
    android_sdk=int(adb('shell','getprop','ro.build.version.sdk').strip())
    if android_sdk<26:raise ValueError('Chrome v2 requires the real supported Android API')
    prefix=resume_transport(sys.argv[1:]);cases=[]
    for width,scale in ((360,1),(412,1),(360,2)):
        adb('shell','am','force-stop',package);adb('logcat','-c')
        adb('shell','wm','size',f'{width*3}x1920');adb('shell','wm','density','480');adb('shell','settings','put','system','font_scale',str(scale))
        nonce=uuid.uuid4().hex;observations={};inputs=[];windows={};checks=[]
        capture=UiVisualCapture(adb=prefix[0],serial=prefix[2],source=source,diagnostics=out/('chrome-v2-native-capture-'+nonce+'.json'))
        transfer=EventTransfer(identity=identity,nonce=nonce,slot=0,action='chromeCollapse',fetch=lambda uri:adb_bytes('exec-out','content','read','--uri',uri))
        def event(command):
            deadline=time.monotonic()+30
            while time.monotonic()<deadline:
                raw=adb('logcat','-d','-s','PocketGeckoIntegration:I','AndroidRuntime:E','*:S')
                assert 'FATAL EXCEPTION' not in raw,raw[-5000:]
                for line in raw.splitlines():
                    receipt=parse_receipt_line(line)
                    if receipt is None or receipt.get('runNonce')!=nonce:continue
                    assert receipt.get('kind')!='eventTransportError',receipt
                    value=transfer.read(receipt);assert value['kind']!='error',value
                    if value['kind']=='collapseSnapshot':
                        sample=value['result'];assert sample['navigationContract']==2,sample
                        observations[sample['command']]=sample
                if command in observations:return observations[command]
                time.sleep(.1)
            raise TimeoutError(('No owned v2 collapse snapshot',command,raw[-5000:]))
        def send(command):adb('shell','am','broadcast','-a',action,'-p',package,'--es','eventNonce',nonce,'--es','collapseCommand',command)
        def snapshot(command):send(command);return event(command)
        def native(phase,labels=(),target=component,ime=None):
            deadline=time.monotonic()+30;last={}
            while time.monotonic()<deadline:
                state=adb('shell','dumpsys','activity','activities');user=adb('shell','am','get-current-user').strip()
                if not user.isdigit():raise ValueError('Unrecognized native current user')
                xml=capture.read(deadline=deadline)
                import xml.etree.ElementTree as ET
                nodes=list(ET.fromstring(xml).iter('node'))
                method=adb('shell','dumpsys','input_method');shown=re.findall(r'\bmInputShown=(true|false)\b',method)
                last=dict(xml=xml,xmlSha256=hashlib.sha256(xml.encode()).hexdigest(),activityState=state,androidUser=int(user),
                    windowState=adb('shell','dumpsys','window'),inputMethod=method)
                if current_resumed(state)=={(int(user),target)} and all(any(n.get('package')==package and label in (n.get('text',''),n.get('content-desc','')) for n in nodes) for label in labels) and (ime is None or shown==['true' if ime else 'false']):
                    windows[phase]=last;return last
                time.sleep(min(.1,max(0,deadline-time.monotonic())))
            raise TimeoutError(('Chrome v2 actual native window',phase,last))
        def tap(before,label,key,first=False):
            point=before[key]
            if first:
                from chrome_first_tap_readiness import first_tap_once
                point=first_tap_once(argv=sys.argv[1:],source=source,identity=identity,before=before,nonce=nonce,out=out)['point']
            else:adb('shell','input','tap',str(point[0]),str(point[1]))
            inputs.append(dict(kind='tap',label=label,point=point,actualAndroidInput=True))
        def address(before,opened,closed,cancel_label,first=False):
            tap(before,opened,'compactTap' if not before['expanded'] else 'addressTap',first)
            native(opened,('打开网址','取消'),ime=True);dialog=snapshot(opened)
            field=dialog['addressDialog'];assert field['visible'] and field['editorFocused'] and field['windowFocus'],dialog
            point=field['cancelTap'];adb('shell','input','tap',str(point[0]),str(point[1]))
            inputs.append(dict(kind='tap',label=cancel_label,point=point,actualAndroidInput=True))
            native(closed,ime=False);returned=snapshot(closed)
            assert returned['addressDialog']=={'visible':False} and not returned['keyboard'],returned
            return returned
        def swipe(before,label,direction):
            start,end=reading_swipe_points(before,direction);x1,y1=start;x2,y2=end
            send('clear')
            adb('shell','input','swipe',str(x1),str(y1),str(x2),str(y2),'320')
            inputs.append(dict(kind='swipe',label=label,actualAndroidInput=True,**{'from':[x1,y1],'to':[x2,y2]},durationMs=320))
            return snapshot(label)
        def back(label,**kw):
            adb('shell','input','keyevent','KEYCODE_BACK');inputs.append(dict(kind='key',label=label,key='KEYCODE_BACK',actualAndroidInput=True))
            native(label,ime=False,**kw);return snapshot(label)
        adb('shell','am','start','-W','-n',component,'--es','compactAction','collapseStart','--es','eventNonce',nonce,'--ei','chromeNavigationVersion','2')
        cold=event('ready')
        initial=address(cold,'addressOpen','initial','addressCancel',True)
        up=swipe(initial,'up','up');down=swipe(up,'down','down')
        expanded=address(down,'compactAddressOpen','compactReturn','compactAddressCancel')
        horizontal=swipe(expanded,'horizontal','horizontal');short=swipe(horizontal,'short','short')
        collapsed=swipe(short,'upBeforeLongPress','up');point=collapsed['compactTap']
        if collapsed['expanded'] is not False or type(point) is not list or len(point)!=2 or any(type(v) is not int for v in point):
            raise AssertionError('Released reading swipe did not expose an actual compact capsule; no long press emitted')
        adb('shell','input','swipe',str(point[0]),str(point[1]),str(point[0]),str(point[1]),'750')
        inputs.append(dict(kind='longpress',label='environmentMenu',point=point,durationMs=750,actualAndroidInput=True))
        native('environmentMenu',('快速切换环境','搜索要切换的环境'));snapshot('environmentMenu')
        returned=back('environmentMenuReturn')
        expanded=address(returned,'longPressAddressOpen','longPressReturn','longPressAddressCancel')
        tap(expanded,'moreMenu','moreTap');native('moreMenu',('会话选项','打开网址或搜索'));snapshot('moreMenu')
        returned=back('moreReturn');tap(returned,'environmentActivity','environmentTap')
        native('environmentActivity',('环境管理',),target=package+'/local.pocketchat.WindowHomeActivity')
        returned=back('environmentReturn')
        collapsed=swipe(returned,'upBeforeNetwork','up');tap(collapsed,'network','networkTap')
        native('network',('网络','窗口网络'));snapshot('network');returned=back('networkReturn')
        tap(returned,'downloads','downloadsTap');native('downloads',('下载中心',));snapshot('downloads');returned=back('downloadsReturn')
        tap(returned,'reading','readingTap');reading=snapshot('reading')
        tap(reading,'readingReturn','exitTap');returned=snapshot('readingReturn')
        swipe(returned,'upBeforeResume','up');home=home_resume(component,inputs);native('activityResume',ime=False);resumed=snapshot('activityResume')
        expanded=address(resumed,'resumeAddressOpen','resumeReturn','resumeAddressCancel')
        send('clear');start=expanded['headerSwipeFrom'];end=expanded['headerSwipeTo']
        from chrome_header_readiness import header_up_once
        header_up_once(argv=sys.argv[1:],source=source,identity=identity,start=start,end=end,nonce=nonce,out=out)
        inputs.append(dict(kind='swipe',label='headerUp',actualAndroidInput=True,**{'from':start,'to':end},durationMs=320));snapshot('headerUp')
        focus('local.pocketchat.CompactChromeIntegrationActivity')
        assert tuple(observations)==PHASES,tuple(observations)
        requests=[row for row in trace if row['kind']=='http' and row['path']=='/c/reload-collapse' and row['documentMarker']==initial['document']]
        case=dict(navigationContract=2,viewport=width,fontScale=scale,runNonce=nonce,sourceCommit=source,androidSdk=android_sdk,
            actualAndroidExecution=True,actualGeckoExecution=True,actualAndroidTouchExecution=True,observations=observations,
            actualAndroidInputs=inputs,nativeUiObservations=windows,homeResume=home,
            eventTransfer=dict(runNonce=nonce,fixtureAction='chromeCollapse',processSlot=0,events=transfer.records),fixtureRequests=requests)
        # Earn each check only after reopening the complete original events and
        # validating every v2 action. No prefilled success may bypass this call.
        verify_case(case,identity,android_sdk,verify_claims=False)
        case['checks']=[{'name':name,'pass':True} for name in sorted(NAMES)];cases.append(case)
    inputs_after=immutable_inputs(source)
    report=dict(navigationContract=2,status='passed',sourceCommit=source,sourceTree=tree,androidSdk=android_sdk,buildIdentity=identity,
        actualAndroidExecution=True,actualGeckoExecution=True,actualAndroidTouchExecution=True,sourceFiles=inputs_before,
        sourceInputsUnchanged=inputs_before==inputs_after,cases=cases,
        scope='Actual v2 production address/menu/workspace/reading navigation and trusted gestures over one synthetic protected Gecko document per case; no live ChatGPT or phone performance claim.')
    verify_auto_collapse_v2(report,source,identity['apkSha256'])
    return report
