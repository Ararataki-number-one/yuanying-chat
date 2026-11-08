"""Contract 2: native address/menu/dock navigation over one retained SDK document.

The legacy 14-check/16-snapshot oracle remains in chrome_collapse_contract.py.
This verifier reopens every complete provider event and recomputes the v2 claims.
"""
import hashlib
import math
import pathlib
import re
import subprocess
import xml.etree.ElementTree as ET
if __package__:
    from .integration_event_contract import EventTransfer,event_uri
else:
    from integration_event_contract import EventTransfer,event_uri

PHASES=('ready','addressOpen','initial','up','down','compactAddressOpen','compactReturn',
        'horizontal','short','upBeforeLongPress','environmentMenu','environmentMenuReturn',
        'longPressAddressOpen','longPressReturn','moreMenu','moreReturn','environmentReturn',
        'upBeforeNetwork','network','networkReturn','downloads','downloadsReturn','reading',
        'readingReturn','upBeforeResume','activityResume','resumeAddressOpen','resumeReturn','headerUp')
INPUT_PATHS=('tests/gecko/run_chrome_collapse.py','tests/gecko/run_chrome_collapse_v2.py',
    'tests/gecko/ChromeCollapseIntegration.java','tests/gecko/run_ui_visuals.py',
    'tests/gecko/run_chrome_collapse_diagnostic.py','tools/gecko/ui_visual_capture.py',
    'tools/gecko/integration_event_contract.py','tools/gecko/profile_invocation_contract.py',
    'tools/gecko/chrome_collapse_contract.py','tools/gecko/chrome_collapse_contract_v2.py',
    'tools/gecko/chrome_first_tap_readiness.py','tools/gecko/chrome_header_readiness.py')
INPUTS=(('tap','addressOpen'),('tap','addressCancel'),('swipe','up'),('swipe','down'),
        ('tap','compactAddressOpen'),('tap','compactAddressCancel'),('swipe','horizontal'),
        ('swipe','short'),('swipe','upBeforeLongPress'),('longpress','environmentMenu'),
        ('key','environmentMenuReturn'),('tap','longPressAddressOpen'),('tap','longPressAddressCancel'),
        ('tap','moreMenu'),('key','moreReturn'),('tap','environmentActivity'),('key','environmentReturn'),
        ('swipe','upBeforeNetwork'),('tap','network'),('key','networkReturn'),('tap','downloads'),
        ('key','downloadsReturn'),('tap','reading'),('tap','readingReturn'),('swipe','upBeforeResume'),
        ('key','home'),('activity-start','activityResume'),('tap','resumeAddressOpen'),
        ('tap','resumeAddressCancel'),('swipe','headerUp'))
STABLE=('surface','sdkSession','attachedSession','document','draft','cookie','sendCount','path',
        'loads','stops','documents','pending','pendingStored','activityRef','activityClass','pid','uid')
NAMES={
    'Contract 2 starts with a real collapsed Gecko document',
    'A capsule tap opens the native address dialog and Cancel preserves the page',
    'Trusted upward reading collapses only after release',
    'Downward reading keeps the compact address capsule',
    'The compact capsule opens the address dialog after a webpage swipe',
    'Horizontal and short gestures keep expanded controls',
    'A capsule long press opens the real environment menu without opening an address dialog',
    'The visible More button opens and dismisses the real session menu',
    'Environment management returns to the same SDK document',
    'Network and downloads are actual native pages with Back retention',
    'Reading mode hides chrome and its real exit control restores it',
    'HOME is observed before one explicit return to the original Activity',
    'The resumed compact capsule still opens and cancels the native address dialog',
    'The native header swipe starts inside its actual button touch region',
    'The native header collapses only after the released gesture',
    'Every v2 action preserves the document draft cookie pending task and network request count',
}

def need(value,reason):
    if not value:raise AssertionError('Chrome navigation v2: '+reason)

def point(value):
    need(isinstance(value,list) and len(value)==2 and all(type(x) is int for x in value),'actual native point')
    return value

def _reading_rect(value,name):
    need(type(value) is list and len(value)==4,'observed CSS rectangle '+name)
    need(all(type(v) in (int,float) and math.isfinite(v) for v in value),'finite CSS rectangle '+name)
    need(value[0]<value[2] and value[1]<value[3],'positive CSS rectangle '+name)
    return value

def reading_swipe_points(sample,direction):
    """Map the current unobscured main document to actual native input pixels.

    Client rectangles and visualViewport offsets share layout-viewport CSS
    coordinates. The measured web size supplies both scale factors; neither
    density nor visualViewport.scale is multiplied into the mapping again.
    """
    need(direction in ('up','down','horizontal','short'),'declared reading direction')
    need(sample['keyboard'] is False and sample['visibleDocument'] is True
         and sample['loadingCoverVisibility']==8 and sample['page']==0,'uncovered reading document without IME')
    region=sample['readingViewport']
    need(type(region['schema']) is int and region['schema']==1
         and region['coordinateSpace']=='layout-viewport-css'
         and region['document']==sample['document']
         and region['composerTag']=='FORM' and region['composerId']=='composer','current complete composer observation')
    need(all(type(region[k]) in (int,float) and math.isfinite(region[k]) and region[k]>0
             for k in ('layoutWidth','layoutHeight')),'positive actual layout viewport')
    need(region['layoutWidth']==sample['innerWidth'] and region['layoutHeight']==sample['innerHeight'],'same snapshot layout viewport')
    visual=_reading_rect(region['visualBounds'],'visualViewport')
    main=_reading_rect(region['mainBounds'],'main')
    composer=_reading_rect(region['composerBounds'],'complete composer form')
    need(all(type(sample[k]) is int for k in ('webX','webY','webWidth','webHeight','nativeDensityDpi'))
         and sample['webWidth']>0 and sample['webHeight']>0 and sample['nativeDensityDpi']>0,'actual native web viewport')
    sx=sample['webWidth']/(visual[2]-visual[0]);sy=sample['webHeight']/(visual[3]-visual[1])
    need(math.isfinite(sx) and math.isfinite(sy) and sx>0 and sy>0
         and abs((visual[2]-visual[0])*sy-sample['webWidth'])<=2
         and abs((visual[3]-visual[1])*sx-sample['webHeight'])<=2,'CSS/native viewport proportions')
    left,top=max(visual[0],main[0]),max(visual[1],main[1])
    right,bottom=min(visual[2],main[2]),min(visual[3],main[3])
    # Exclude the whole form across its occupied row, never use its side gutter.
    if max(left,composer[0])<min(right,composer[2]) and max(top,composer[1])<min(bottom,composer[3]):
        bottom=min(bottom,composer[1])
    need(left<right and top<bottom,'visible main reading strip above the complete composer')
    native_x=lambda x:sample['webX']+(x-visual[0])*sx
    native_y=lambda y:sample['webY']+(y-visual[1])*sy
    nl,nr=math.ceil(native_x(left))+1,math.floor(native_x(right))-1
    nt,nb=math.ceil(native_y(top))+1,math.floor(native_y(bottom))-1
    need(nl<nr and nt<nb,'positive reading strip after native rounding')
    x=(nl+nr)//2;margin=max(1,(nb-nt)//8)
    upper,lower=nt+margin,nb-margin
    if direction in ('up','down'):
        need(lower-upper>=40*sample['nativeDensityDpi']/160,'safe native reading swipe still reaches the original 40dp threshold')
        start,end=([x,lower],[x,upper]) if direction=='up' else ([x,upper],[x,lower])
    elif direction=='horizontal':
        y=(upper+lower)//2;start,end=[nl+(nr-nl)//4,y],[nl+(nr-nl)*3//4,y]
        need(start[0]<end[0],'positive native horizontal reading swipe')
    else:
        start,end=[x,lower],[x,lower-12]
    need(all(nl<=p[0]<=nr and nt<=p[1]<=nb and sample['webX']<=p[0]<sample['webX']+sample['webWidth']
             and sample['webY']<=p[1]<sample['webY']+sample['webHeight'] for p in (start,end)),'rounded endpoints remain inside the actual safe reading strip')
    cl,ct,cr,cb=native_x(composer[0]),native_y(composer[1]),native_x(composer[2]),native_y(composer[3])
    collision=(cl<=start[0]<=cr and max(min(start[1],end[1]),ct)<=min(max(start[1],end[1]),cb)) if start[0]==end[0] else (
        ct<=start[1]<=cb and max(min(start[0],end[0]),cl)<=min(max(start[0],end[0]),cr))
    need(not collision,'entire native swipe excludes the complete composer form')
    return start,end

def telemetry(sample):
    t=sample['fixtureInputTelemetry']
    need(sample['telemetryReady'] is True and t['schema']==1 and t['realm']=='page-main-world','main-world telemetry')
    need(t['document']==sample['document'] and 'touchend' in t['listenerTypes'],'current telemetry document')
    need(t['events']==sample['trusted'] and len(t['events'])<=256 and t['count']==len(t['events'])+t['dropped'],'complete bounded telemetry')
    need(all(type(row['trusted']) is bool and row['type'] in t['listenerTypes'] for row in t['events']),'typed trusted events')

def gesture(before,after):
    touches=after['touches']
    need(len(touches)>=3 and touches[0]['action']==0 and touches[-1]['action']==1 and any(t['action']==2 for t in touches),'complete DOWN MOVE UP')
    need(all(t['pointers']==1 and t['width']==before['webWidth'] and t['height']==before['webHeight'] and t['expanded']==before['expanded'] for t in touches),'layout unchanged beneath finger')

def current_components(raw):
    # Current AMS fields only; historical task/window mentions are insufficient.
    resumed=set()
    for line in raw.splitlines():
        m=re.fullmatch(r'\s*(?:mResumedActivity|topResumedActivity)\s*[:=]\s*ActivityRecord\{[^{}]*?\bu([0-9]+)\s+([A-Za-z0-9_.]+/[A-Za-z0-9_.$]+)(?:\s+[^{}]*)?\}',line)
        if m:
            package,activity=m[2].split('/');resumed.add((int(m[1]),package+'/'+(package+activity if activity.startswith('.') else activity)))
    return resumed

def native_window(value,labels,component,uid,*,ime=None):
    raw=value['xml'];need(hashlib.sha256(raw.encode()).hexdigest()==value['xmlSha256'],'native hierarchy digest')
    nodes=list(ET.fromstring(raw).iter('node'))
    for label in labels:
        need(any(n.get('package')=='local.pocketchat.test' and label in (n.get('text',''),n.get('content-desc','')) for n in nodes),'actual native label '+label)
    need(current_components(value['activityState'])=={(value['androidUser'],component)},'actual current native Activity')
    state=value['windowState'];focus=re.findall(r'^\s*mCurrentFocus=Window\{([0-9a-f]+)\s+u[0-9]+\s+[^\r\n{}]+\}',state,re.MULTILINE)
    need(len(focus)==1,'one actual focused window')
    blocks=re.split(r'(?=^\s*Window #[0-9]+ Window\{)',state,flags=re.MULTILINE)
    owned=[b for b in blocks if re.match(r'\s*Window #[0-9]+ Window\{'+re.escape(focus[0])+r'\s',b)]
    need(len(owned)==1 and re.findall(r'\bmOwnerUid=([0-9]+)\b',owned[0])==[str(uid)]
         and re.search(r'\bpackage=local\.pocketchat\.test\b',owned[0]) is not None,'actual focus belongs to the tested UID/package')
    if ime is not None:need(re.findall(r'\bmInputShown=(true|false)\b',value['inputMethod'])==['true' if ime else 'false'],'actual IME state')

def verify_case(case,identity,android_sdk,*,verify_claims=True):
    need(type(case['navigationContract']) is int and case['navigationContract']==2 and case['sourceCommit']==identity['sourceCommit'],'case version/source')
    need(case['androidSdk']==android_sdk and all(case[k] is True for k in ('actualAndroidExecution','actualGeckoExecution','actualAndroidTouchExecution')),'case runtime')
    if verify_claims:need(NAMES<={c['name'] for c in case['checks']} and all(c['pass'] is True for c in case['checks']),'all explicit v2 checks')
    owned=case['eventTransfer'];need(owned['runNonce']==case['runNonce'] and owned['fixtureAction']=='chromeCollapse' and owned['processSlot']==0,'case invocation')
    rows=owned['events'];payloads={event_uri(r['receipt']):r['rawUtf8'].encode() for r in rows}
    need(len(rows)==len(payloads)==len(PHASES),'all v2 snapshots')
    transfer=EventTransfer(identity=identity,nonce=case['runNonce'],slot=0,action='chromeCollapse',fetch=lambda uri:payloads[uri])
    observed={}
    for row in rows:
        event=transfer.read(row['receipt']);need(event['kind']=='collapseSnapshot','original snapshot event')
        s=event['result'];need(type(s['navigationContract']) is int and s['navigationContract']==2 and s['command'] not in observed,'snapshot version/uniqueness');observed[s['command']]=s
    need(tuple(observed)==PHASES and observed==case['observations'],'exact ordered provider snapshots')
    s=observed;cold=s['ready'];initial=s['initial']
    need(not cold['expanded'] and cold['toolbarVisibility']==0 and cold['compactVisibility']==0 and cold['topVisibility']==8 and cold['networkVisibility']==0,'initial collapsed controls')
    need(cold['compactName']==cold['environmentName'] and cold['compactHeight']>0 and cold['visibleDocument'] and cold['loadingCoverVisibility']==8,'real initial document')
    need(initial['expanded'] and initial['compactVisibility']==8 and initial['topVisibility']==0 and initial['toolbarVisibility']==0 and initial['toolbarHeight']>cold['toolbarHeight'],'production address click reveals chrome')
    need(cold['webHeight']==initial['webHeight']+initial['toolbarHeight']-cold['toolbarHeight'],'real collapse geometry')
    need(initial['loads']==initial['stops']==initial['sendCount']==0 and initial['documents']==1 and initial['sdkSession']==initial['attachedSession'],'original live SDK')
    need(type(initial['pid']) is int and initial['pid']>0 and type(initial['uid']) is int and initial['uid']>0,'actual native process owner')
    need(len(initial['document'])==32 and initial['draft']=='unsent controlled browser draft' and 'session=synthetic-reload' in initial['cookie'] and initial['path']=='/c/reload-collapse','controlled draft/login/document')
    need(initial['pending']['confirmed'] is True and initial['pending']['webSuspended'] is True and initial['pending']['confirmedUrl']=='https://chatgpt.com/c/reload-collapse','confirmed retained task')
    task=initial['pending'];need(isinstance(task['id'],str) and bool(task['id']) and task['kind']=='web' and task['engine']=='gecko' and task['userKey']=='id:reload-user' and task['prompt']=='already sent fixture question' and task['expectedUrl']=='https://chatgpt.com/c/reload-collapse','same owned pending task')
    import json
    need(json.loads(initial['pendingStored'])==task,'pending persistence equals the owned task')
    r=initial['documentReadyEvidence'];actual='http://127.0.0.1:8765/c/reload-collapse';virtual='https://chatgpt.com/c/reload-collapse'
    need(r['rawMessage']['kind']=='documentReady' and r['rawMessage']['url']==r['senderUrl']==r['actualUrl']==actual and r['visibleUrl']==virtual,'actual controlled ready port')
    need(r['normalizedMessage']==dict(r['rawMessage'],url=virtual) and all(r[k] is True for k in ('topLevel','contentScript','acceptedByProduction')) and r['nativeSession']==r['currentSession']==initial['sdkSession'],'production readiness authority')
    for phase,sample in s.items():
        need(all(sample[k]==initial[k] for k in STABLE),'retention at '+phase);telemetry(sample)
        need(sample['androidSdk']==android_sdk,'snapshot Android API')
        need(type(sample['nativeFontScale']) in (int,float) and sample['nativeFontScale']==case['fontScale']
             and type(sample['nativeScreenWidthDp']) is int and sample['nativeScreenWidthDp']==case['viewport']
             and type(sample['nativeDensityDpi']) is int and sample['nativeDensityDpi']==480
             and type(sample['nativeDisplayWidth']) is int and sample['nativeDisplayWidth']==case['viewport']*3
             and sample['webWidth']==case['viewport']*3,'actual native size/font configuration at '+phase)
        need(sample['activityStarts']==(1 if PHASES.index(phase)>=PHASES.index('environmentReturn') else 0),'exact Activity starts at '+phase)
        need(sample['menuOpens']==(1 if PHASES.index(phase)>=PHASES.index('moreMenu') else 0),'exact More opens at '+phase)
        if phase not in ('network','downloads','reading'):need(sample['networkVisibility']==0,'network line retained at '+phase)
    for opened,closed in [('addressOpen','initial'),('compactAddressOpen','compactReturn'),('longPressAddressOpen','longPressReturn'),('resumeAddressOpen','resumeReturn')]:
        d=s[opened]['addressDialog'];need(d['visible'] is True and d['windowFocus'] is True and d['editorFocused'] is True and d['editorText']==virtual and d['cancelText']=='取消','real native address editor')
        point(d['editorTap']);point(d['cancelTap']);need(s[closed]['addressDialog']=={'visible':False} and s[closed]['expanded'] and not s[closed]['keyboard'],'address Cancel without IME residue')
    for before,after in [('initial','up'),('up','down'),('compactReturn','horizontal'),('horizontal','short'),('short','upBeforeLongPress'),('environmentReturn','upBeforeNetwork'),('readingReturn','upBeforeResume')]:gesture(s[before],s[after])
    for phase in ('up','down','upBeforeLongPress','upBeforeNetwork','upBeforeResume','activityResume','headerUp'):
        need(s[phase]['expanded'] is False and s[phase]['toolbarVisibility']==0 and s[phase]['compactVisibility']==0 and s[phase]['webHeight']==cold['webHeight'],'compact geometry '+phase)
    need(s['up']['scrollY']>initial['scrollY'] and any(t['trusted'] is True and t['type']=='touchend' for t in s['up']['trusted']),'real trusted upward scroll')
    need(s['horizontal']['expanded'] and s['short']['expanded'] and s['horizontal']['webHeight']==s['short']['webHeight']==initial['webHeight'],'non-collapse directions')
    need(s['environmentMenu']['addressDialog']=={'visible':False} and not s['environmentMenu']['expanded'] and not s['environmentMenuReturn']['expanded'],'consumed real long press')
    for phase,page in [('network',4),('downloads',1)]:need(s[phase]['page']==page and s[phase]['toolbarVisibility']==8,'actual native page '+phase)
    for phase in ('environmentReturn','networkReturn','downloadsReturn','readingReturn','resumeReturn'):
        need(s[phase]['page']==0 and s[phase]['expanded'] and s[phase]['webHeight']==initial['webHeight'],'real return '+phase)
    need(s['reading']['readingRequested'] is True and s['reading']['readingActive'] is True and s['reading']['toolbarVisibility']==s['reading']['navigationVisibility']==8 and s['reading']['exitVisibility']==0,'actual reading mode')
    need(s['readingReturn']['readingRequested'] is False and s['readingReturn']['readingActive'] is False and s['readingReturn']['navigationVisibility']==0 and s['readingReturn']['exitVisibility']==8,'actual reading exit')
    header=s['headerUp'];touches=header['nativeTouches'];left,top,right,bottom=s['resumeReturn']['headerButtonTouch'];start=s['resumeReturn']['headerSwipeFrom']
    need(left<=start[0]<right and top<=start[1]<bottom,'actual native header touch bounds')
    need(header['windowFocus'] and len(touches)>=3 and touches[0]['action']==0 and touches[-1]['action']==1 and any(t['action']==2 for t in touches) and all(t['pointers']==1 and t['height']==initial['webHeight'] and t['expanded'] for t in touches),'native release before collapse')
    windows=case['nativeUiObservations'];component='local.pocketchat.test/local.pocketchat.CompactChromeIntegrationActivity'
    for phase,labels in [('addressOpen',('打开网址','取消')),('compactAddressOpen',('打开网址','取消')),('longPressAddressOpen',('打开网址','取消')),('resumeAddressOpen',('打开网址','取消')),('environmentMenu',('快速切换环境','搜索要切换的环境')),('moreMenu',('会话选项','打开网址或搜索')),('network',('网络','窗口网络')),('downloads',('下载中心',))]:native_window(windows[phase],labels,component,initial['uid'],ime=True if phase.endswith('AddressOpen') or phase=='addressOpen' else None)
    for phase in ('initial','compactReturn','longPressReturn','resumeReturn'):native_window(windows[phase],(),component,initial['uid'],ime=False)
    native_window(windows['environmentActivity'],('环境管理',),'local.pocketchat.test/local.pocketchat.WindowHomeActivity',initial['uid'])
    home=case['homeResume'];need(home['homeObservedBeforeStart'] is True and home['home']!=component and home['returned']==component and len(home['observations'])==2 and 0<home['elapsedSeconds']<=20,'HOME observation barrier')
    need(home['observations'][0]['component']==home['home'] and home['observations'][-1]['component']==component,'actual HOME then original Activity')
    for row in home['observations']:need(current_components(row['activityState'])=={(row['androidUser'],row['component'])},'actual current HOME/return observation')
    inputs=case['actualAndroidInputs'];need([(g['kind'],g['label']) for g in inputs]==list(INPUTS) and all(g['actualAndroidInput'] is True for g in inputs),'complete ordered v2 inputs')
    taps={g['label']:g for g in inputs if g['kind']=='tap'}
    for label,phase,key in [('addressOpen','ready','compactTap'),('compactAddressOpen','down','compactTap'),
            ('longPressAddressOpen','environmentMenuReturn','compactTap'),('moreMenu','longPressReturn','moreTap'),
            ('environmentActivity','moreReturn','environmentTap'),('network','upBeforeNetwork','networkTap'),
            ('downloads','networkReturn','downloadsTap'),('reading','downloadsReturn','readingTap'),
            ('readingReturn','reading','exitTap'),('resumeAddressOpen','activityResume','compactTap')]:
        need(point(taps[label]['point'])==point(s[phase][key]),'actual native tap target '+label)
    for label,phase in [('addressCancel','addressOpen'),('compactAddressCancel','compactAddressOpen'),('longPressAddressCancel','longPressAddressOpen'),('resumeAddressCancel','resumeAddressOpen')]:
        need(point(taps[label]['point'])==point(s[phase]['addressDialog']['cancelTap']),'actual dialog Cancel target')
    swipes={g['label']:g for g in inputs if g['kind']=='swipe'}
    for label,phase,direction in [('up','initial','up'),('down','up','down'),('horizontal','compactReturn','horizontal'),
            ('short','horizontal','short'),('upBeforeLongPress','short','up'),('upBeforeNetwork','environmentReturn','up'),('upBeforeResume','readingReturn','up')]:
        start,end=reading_swipe_points(s[phase],direction)
        need(swipes[label]['from']==start and swipes[label]['to']==end,'original swipe coordinates '+label)
    need(swipes['headerUp']['from']==s['resumeReturn']['headerSwipeFrom'] and swipes['headerUp']['to']==s['resumeReturn']['headerSwipeTo'],'actual header coordinates')
    need(len([g for g in inputs if g['kind']=='swipe'])==8 and all(g['durationMs']==320 for g in inputs if g['kind']=='swipe'),'original eight real swipes')
    press=next(g for g in inputs if g['label']=='environmentMenu');need(press['durationMs']==750 and point(press['point'])==point(s['upBeforeLongPress']['compactTap']),'real consumed long press')
    need(all(g['key']==('KEYCODE_HOME' if g['label']=='home' else 'KEYCODE_BACK') for g in inputs if g['kind']=='key'),'actual HOME/Back keys')
    need(next(g for g in inputs if g['kind']=='activity-start')['component']==component,'one original Activity start')
    requests=case['fixtureRequests'];need(len(requests)==1 and requests[0]['kind']=='http' and requests[0]['path']=='/c/reload-collapse' and requests[0]['documentMarker']==initial['document'],'one actual document request')
    return len(case['checks']) if verify_claims else len(NAMES)

def selected_source_bytes(source,path):
    root=pathlib.Path(__file__).resolve().parents[2]
    return subprocess.check_output(['git','show',source+':'+path],cwd=root)

def selected_contract_version(source,*,source_reader=selected_source_bytes):
    raw=source_reader(source,'tests/gecko/ChromeCollapseIntegration.java')
    if b'chromeNavigationVersion' not in raw:return 1
    if re.search(rb'getIntExtra\("chromeNavigationVersion",1\)!=2',raw):return 2
    raise ValueError('Unknown selected-source Chrome navigation contract')

def verify_auto_collapse_v2(report,source,apk_sha,*,source_reader=selected_source_bytes):
    need(type(report['navigationContract']) is int and report['navigationContract']==2 and report['status']=='passed' and report['sourceCommit']==source,'report version/source/status')
    need(all(report[k] is True for k in ('actualAndroidExecution','actualGeckoExecution','actualAndroidTouchExecution','sourceInputsUnchanged')),'real runtime and immutable inputs')
    identity=report['buildIdentity'];need(identity['sourceCommit']==source and identity['apkSha256']==apk_sha and report['sourceTree']==identity['sourceTree'],'source/APK/tree identity')
    need(type(report['androidSdk']) is int and report['androidSdk']>=26,'actual Android API')
    need(set(report['sourceFiles'])==set(INPUT_PATHS),'complete selected source inputs')
    for path in INPUT_PATHS:need(report['sourceFiles'][path]==hashlib.sha256(source_reader(source,path)).hexdigest(),'selected source input '+path)
    need(selected_contract_version(source,source_reader=source_reader)==2,'selected source declares v2')
    cases=report['cases'];need(len(cases)==3 and {(c['viewport'],c['fontScale']) for c in cases}=={(360,1),(412,1),(360,2)} and len({c['runNonce'] for c in cases})==3,'three independent size/font invocations')
    count=sum(verify_case(case,identity,report['androidSdk']) for case in cases)
    return dict(navigationContract=2,cases=3,checks=count,actualAndroidExecution=True,actualGeckoExecution=True)
