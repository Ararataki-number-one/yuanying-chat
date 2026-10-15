#!/usr/bin/env python3
"""Actual native swipes and navigation; source/APK/SDK/nonce-bound full snapshots."""
import json,pathlib,re,subprocess,sys,time,uuid

ROOT=pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/gecko'))
from integration_event_contract import EventTransfer,parse_receipt_line
from profile_invocation_contract import expected_build,verify_installed


def run(adb,adb_bytes,source,trace,out,focus):
    package='local.pocketchat.test'
    component=package+'/local.pocketchat.CompactChromeIntegrationActivity'
    action='local.pocketchat.test.CHROME_COLLAPSE'
    tree=subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=ROOT,text=True).strip()
    gradle=(ROOT/'app/build.gradle').read_text()
    identity=expected_build(out/'ui-current.apk',source,tree,re.search(r"versionName '([^']+)'",gradle).group(1),int(re.search(r'versionCode (\d+)',gradle).group(1)))
    verify_installed(json.loads(adb('exec-out','content','read','--uri','content://'+package+'.evidence/build-identity')),identity)
    cases=[]
    for width,scale in [(360,1),(412,1),(360,2)]:
        adb('shell','am','force-stop',package);adb('logcat','-c')
        adb('shell','wm','size',f'{width*3}x1920');adb('shell','wm','density','480');adb('shell','settings','put','system','font_scale',str(scale))
        nonce=uuid.uuid4().hex
        transfer=EventTransfer(identity=identity,nonce=nonce,slot=0,action='chromeCollapse',fetch=lambda uri:adb_bytes('exec-out','content','read','--uri',uri))
        observations={};checks=[];inputs=[]
        def check(name,value):
            checks.append({'name':name,'pass':bool(value)})
            assert value,('Chrome auto-collapse regression',width,scale,name,observations)
        def event(command):
            deadline=time.monotonic()+30
            while time.monotonic()<deadline:
                raw=adb('logcat','-d','-s','PocketGeckoIntegration:I','AndroidRuntime:E','*:S')
                assert 'FATAL EXCEPTION' not in raw,raw[-5000:]
                for line in raw.splitlines():
                    receipt=parse_receipt_line(line)
                    if receipt is None or receipt.get('runNonce')!=nonce:continue
                    assert receipt.get('kind')!='eventTransportError',receipt
                    value=transfer.read(receipt)
                    assert value['kind']!='error',value
                    if value['kind']=='collapseSnapshot':observations[value['result']['command']]=value['result']
                if command in observations:return observations[command]
                time.sleep(.1)
            raise TimeoutError(('No owned collapse snapshot',command,raw[-5000:]))
        def send(command):
            adb('shell','am','broadcast','-a',action,'-p',package,'--es','eventNonce',nonce,'--es','collapseCommand',command)
        def snapshot(command):send(command);return event(command)
        def swipe(before,label,direction):
            send('clear')
            x=before['webX']+before['webWidth']//2
            top=before['webY']+before['webHeight']//4
            bottom=before['webY']+before['webHeight']*2//3
            x1=x2=x;y1,y2=(bottom,top) if direction=='up' else (top,bottom)
            if direction=='horizontal':x1=before['webX']+before['webWidth']//4;x2=before['webX']+before['webWidth']*3//4;y1=y2=(top+bottom)//2
            if direction=='short':y1=bottom;y2=bottom-12
            adb('shell','input','swipe',str(x1),str(y1),str(x2),str(y2),'320')
            inputs.append({'kind':'swipe','label':label,'actualAndroidInput':True,'from':[x1,y1],'to':[x2,y2],'durationMs':320})
            return snapshot(label)
        def tap(before,label,key):
            point=before[key];adb('shell','input','tap',str(point[0]),str(point[1]))
            inputs.append({'kind':'tap','label':label,'actualAndroidInput':True,'point':point})
            return snapshot(label)
        def unchanged(before,after):
            return all(after[k]==before[k] for k in ['surface','sdkSession','attachedSession','document','draft','cookie','sendCount','path','loads','stops','documents','pending','pendingStored','activityStarts','menuOpens'])
        def gesture_geometry(before,after):
            touches=after['touches']
            return len(touches)>=3 and touches[0]['action']==0 and touches[-1]['action']==1 and any(t['action']==2 for t in touches) and all(t['pointers']==1 and t['height']==before['webHeight'] and t['width']==before['webWidth'] and t['expanded']==before['expanded'] for t in touches)
        adb('shell','am','start','-W','-n',component,'--es','compactAction','collapseStart','--es','eventNonce',nonce)
        cold=event('ready')
        check('Actual Gecko document starts with collapsed environment controls',not cold['expanded'] and cold['toolbarVisibility']==8 and cold['visibleDocument'] and cold['loadingCoverVisibility']==8)
        initial=tap(cold,'initialChat','chatTap')
        check('Explicit Chat tap reveals controls without replacing the initial document',unchanged(cold,initial) and cold['webHeight']==initial['webHeight']+initial['toolbarHeight'] and initial['visibleDocument'] and initial['loadingCoverVisibility']==8 and initial['expanded'] and initial['toolbarVisibility']==0 and initial['toolbarHeight']>0 and initial['webHeight']>0 and initial['documents']==1 and initial['loads']==initial['stops']==initial['sendCount']==0 and initial['path']=='/c/reload-collapse' and len(initial['document'])==32 and initial['draft']=='unsent controlled browser draft' and 'session=synthetic-reload' in initial['cookie'] and initial['pending']['confirmed'] and initial['sdkSession']==initial['attachedSession'])
        hidden=swipe(initial,'up','up')
        check('Trusted upward reading swipe hides chrome only after the gesture',not hidden['expanded'] and hidden['toolbarVisibility']==8 and hidden['webHeight']==initial['webHeight']+initial['toolbarHeight'] and gesture_geometry(initial,hidden) and unchanged(initial,hidden) and hidden['scrollY']>initial['scrollY'] and any(t['trusted'] and t['type']=='touchend' for t in hidden['trusted']))
        shown=swipe(hidden,'down','down')
        check('Trusted downward reading swipe reveals chrome after the gesture',shown['expanded'] and shown['toolbarVisibility']==0 and shown['webHeight']==initial['webHeight'] and gesture_geometry(hidden,shown) and unchanged(initial,shown))
        horizontal=swipe(shown,'horizontal','horizontal')
        check('Horizontal scrolling does not collapse environment controls',horizontal['expanded'] and horizontal['webHeight']==initial['webHeight'] and gesture_geometry(shown,horizontal) and unchanged(initial,horizontal))
        short=swipe(horizontal,'short','short')
        check('Short gestures do not collapse environment controls',short['expanded'] and short['webHeight']==initial['webHeight'] and unchanged(initial,short))
        hidden_again=swipe(short,'upBeforeChat','up')
        chat=tap(hidden_again,'selectedChat','chatTap')
        check('Tapping the already selected Chat tab reveals environment controls',not hidden_again['expanded'] and chat['expanded'] and chat['page']==0 and chat['webHeight']==initial['webHeight'] and unchanged(initial,chat))
        hidden_native=swipe(chat,'upBeforeNative','up')
        native=tap(hidden_native,'settings','settingsTap')
        returned=tap(native,'nativeReturn','chatTap')
        check('Returning from native settings reveals chrome without reloading chat',not hidden_native['expanded'] and native['page']==3 and returned['page']==0 and returned['expanded'] and returned['webHeight']==initial['webHeight'] and unchanged(initial,native) and unchanged(initial,returned))
        hidden_resume=swipe(returned,'upBeforeResume','up')
        adb('shell','input','keyevent','KEYCODE_HOME')
        adb('shell','am','start','-W','--activity-single-top','-n',component)
        focus('local.pocketchat.CompactChromeIntegrationActivity')
        resumed=snapshot('activityResume')
        check('Activity resume preserves the collapsed controls and live SDK page',not hidden_resume['expanded'] and not resumed['expanded'] and resumed['webHeight']==hidden_resume['webHeight'] and unchanged(initial,resumed))
        resume_chat=tap(resumed,'resumeChat','chatTap')
        check('Explicit Chat tap reveals controls after resume',resume_chat['expanded'] and resume_chat['webHeight']==initial['webHeight'] and unchanged(initial,resume_chat))
        send('clear');start=resume_chat['headerSwipeFrom'];end=resume_chat['headerSwipeTo'];left,top,right,bottom=resume_chat['headerButtonTouch']
        check('Native header swipe starts inside an actual expanded button touch region',left<=start[0]<right and top<=start[1]<bottom)
        adb('shell','input','swipe',str(start[0]),str(start[1]),str(end[0]),str(end[1]),'320')
        inputs.append({'kind':'swipe','label':'headerUp','actualAndroidInput':True,'from':start,'to':end,'durationMs':320})
        header=snapshot('headerUp');native_touches=header['nativeTouches']
        focus('local.pocketchat.CompactChromeIntegrationActivity')
        check('Upward swipe on native environment controls collapses only after release',not header['expanded'] and header['toolbarVisibility']==8 and header['windowFocus'] and header['activityStarts']==header['menuOpens']==0 and header['webHeight']==cold['webHeight'] and unchanged(initial,header) and len(native_touches)>=3 and native_touches[0]['action']==0 and native_touches[-1]['action']==1 and any(t['action']==2 for t in native_touches) and all(t['pointers']==1 and t['height']==initial['webHeight'] and t['expanded'] for t in native_touches))
        requests=[row for row in trace if row['kind']=='http' and row['path']=='/c/reload-collapse' and row['documentMarker']==initial['document']]
        check('All chrome interactions use one controlled actual document without navigation or send',len(requests)==1 and all(unchanged(initial,sample) for sample in observations.values()) and all(sample['sendCount']==0 for sample in observations.values()))
        cases.append({'viewport':width,'fontScale':scale,'runNonce':nonce,'sourceCommit':source,'actualAndroidExecution':True,'actualGeckoExecution':True,'actualAndroidTouchExecution':True,'checks':checks,'observations':observations,'actualAndroidInputs':inputs,'eventTransfer':{'runNonce':nonce,'fixtureAction':'chromeCollapse','processSlot':0,'events':transfer.records},'fixtureRequests':requests})
    return {'status':'passed','actualAndroidExecution':True,'actualGeckoExecution':True,'actualAndroidTouchExecution':True,'sourceCommit':source,'buildIdentity':identity,'cases':cases,'scope':'Actual production chrome and protected local Gecko document with synthetic login/draft/task; no real ChatGPT acceptance or phone performance claim.'}
