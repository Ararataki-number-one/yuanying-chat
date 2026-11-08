"""Host rejection controls over complete synthetic v2 packets; no device acceptance."""
import ast,copy,hashlib,importlib.util,json,os,pathlib,subprocess,sys,unittest
from unittest.mock import patch

ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tests/gecko'),str(ROOT/'tools/gecko')]
import chrome_collapse_contract as dispatch
import chrome_collapse_contract_v2 as contract
import run_chrome_collapse as legacy
import run_chrome_collapse_v2 as current
from gecko_event_transfer_test import identity

SOURCE='a'*40;COMPONENT='local.pocketchat.test/local.pocketchat.CompactChromeIntegrationActivity'

def activity(component):return 'topResumedActivity=ActivityRecord{abc u0 '+component+' t8}\n'

def native(labels,component=COMPONENT,*,ime=False):
    import xml.etree.ElementTree as ET
    tree=ET.Element('hierarchy')
    for label in labels:ET.SubElement(tree,'node',{'package':'local.pocketchat.test','text':label})
    xml=ET.tostring(tree,encoding='unicode')
    return dict(xml=xml,xmlSha256=hashlib.sha256(xml.encode()).hexdigest(),activityState=activity(component),androidUser=0,inputMethod='mInputShown='+str(ime).lower()+'\n',windowState='  Window #0 Window{abc u0 '+component+'}:\n    mOwnerUid=10001 package=local.pocketchat.test\n  mCurrentFocus=Window{abc u0 '+component+'}\n')

def bind_events(case):
    rows=[]
    for sequence,(phase,sample) in enumerate(case['observations'].items(),1):
        event=dict(kind='collapseSnapshot',result=copy.deepcopy(sample),nativeContext='environment-1',processSlot=0)
        envelope=dict(schema=1,sourceCommit=SOURCE,buildIdentity=identity(),runNonce=case['runNonce'],fixtureAction='chromeCollapse',command=1,sequence=sequence,nativeContext='environment-1',processSlot=0,event=event)
        raw=json.dumps(envelope,separators=(',',':'))+'\n'
        receipt={k:envelope[k] for k in ('schema','runNonce','fixtureAction','command','sequence','nativeContext','processSlot')}
        receipt.update(kind='eventReceipt',eventKind='collapseSnapshot',payloadBytes=len(raw.encode()),payloadSha256=hashlib.sha256(raw.encode()).hexdigest())
        rows.append(dict(receipt=receipt,rawUtf8=raw))
    case['eventTransfer']=dict(runNonce=case['runNonce'],fixtureAction='chromeCollapse',processSlot=0,events=rows)

def make_case(width,scale,nonce):
    virtual='https://chatgpt.com/c/reload-collapse';actual='http://127.0.0.1:8765/c/reload-collapse'
    ready=dict(rawMessage=dict(kind='documentReady',url=actual),senderUrl=actual,actualUrl=actual,visibleUrl=virtual,topLevel=True,contentScript=True,acceptedByProduction=True,nativeSession=12,currentSession=12)
    ready['normalizedMessage']=dict(ready['rawMessage'],url=virtual)
    pending=dict(id='owned-task',kind='web',engine='gecko',userKey='id:reload-user',prompt='already sent fixture question',expectedUrl=virtual,confirmed=True,webSuspended=True,confirmedUrl=virtual)
    base=dict(navigationContract=2,androidSdk=35,activityClass=COMPONENT.split('/')[1],activityRef=23,surface=11,sdkSession=12,attachedSession=12,document='d'*32,draft='unsent controlled browser draft',cookie='session=synthetic-reload',sendCount=0,path='/c/reload-collapse',loads=0,stops=0,documents=1,pending=pending,pendingStored=json.dumps(pending),visibleDocument=True,loadingCoverVisibility=8,documentReadyEvidence=ready,compactName='Owned environment',environmentName='Owned environment',compactHeight=80,networkVisibility=0,page=0,keyboard=False,windowFocus=True,webWidth=width*3,webHeight=1000,webX=0,webY=180,toolbarHeight=130,toolbarVisibility=0,expanded=True,compactVisibility=8,topVisibility=0,compactTap=[300,100],addressTap=[400,100],moreTap=[width*3-50,100],environmentTap=[100,1600],networkTap=[250,1600],downloadsTap=[400,1600],readingTap=[550,1600],exitTap=[width*3-80,80],readingRequested=False,readingActive=False,navigationVisibility=0,exitVisibility=8,addressDialog={'visible':False},scrollY=0,touches=[],nativeTouches=[],headerSwipeFrom=[400,126],headerSwipeTo=[400,81],headerButtonTouch=[300,80,500,128])
    compact={'ready','up','down','upBeforeLongPress','environmentMenu','environmentMenuReturn','upBeforeNetwork','network','upBeforeResume','activityResume','headerUp'}
    observations={}
    for phase in contract.PHASES:
        value=copy.deepcopy(base);value['command']=phase
        value.update(nativeFontScale=scale,nativeScreenWidthDp=width,nativeDensityDpi=480,nativeDisplayWidth=width*3,pid=1234,uid=10001)
        if phase in compact:value.update(expanded=False,compactVisibility=0,topVisibility=8,toolbarHeight=80,webHeight=1050)
        value['activityStarts']=int(contract.PHASES.index(phase)>=contract.PHASES.index('environmentReturn'))
        value['menuOpens']=int(contract.PHASES.index(phase)>=contract.PHASES.index('moreMenu'))
        if phase in ('addressOpen','compactAddressOpen','longPressAddressOpen','resumeAddressOpen'):
            value['addressDialog']=dict(visible=True,windowFocus=True,editorFocused=True,editorText=virtual,editorTap=[350,550],cancelTap=[700,700],cancelBounds=[600,650,800,750],cancelText='取消')
        if phase=='network':value.update(page=4,toolbarVisibility=8)
        if phase=='downloads':value.update(page=1,toolbarVisibility=8)
        if phase=='reading':value.update(readingRequested=True,readingActive=True,toolbarVisibility=8,navigationVisibility=8,exitVisibility=0,webHeight=1200)
        events=[dict(type='touchend',trusted=True)] if phase=='up' else []
        value['trusted']=events;value['telemetryReady']=True;value['fixtureInputTelemetry']=dict(schema=1,realm='page-main-world',document=value['document'],listenerTypes=['touchend'],events=events,count=len(events),dropped=0)
        if phase=='up':value['scrollY']=200
        observations[phase]=value
    for before,after in [('initial','up'),('up','down'),('compactReturn','horizontal'),('horizontal','short'),('short','upBeforeLongPress'),('environmentReturn','upBeforeNetwork'),('readingReturn','upBeforeResume')]:
        b=observations[before];observations[after]['touches']=[dict(action=a,pointers=1,width=b['webWidth'],height=b['webHeight'],expanded=b['expanded']) for a in (0,2,1)]
    observations['headerUp']['nativeTouches']=[dict(action=a,pointers=1,height=1000,expanded=True) for a in (0,2,1)]
    windows={phase:native(labels,ime=phase in ('addressOpen','compactAddressOpen','longPressAddressOpen','resumeAddressOpen')) for phase,labels in [('addressOpen',('打开网址','取消')),('compactAddressOpen',('打开网址','取消')),('longPressAddressOpen',('打开网址','取消')),('resumeAddressOpen',('打开网址','取消')),('environmentMenu',('快速切换环境','搜索要切换的环境')),('moreMenu',('会话选项','打开网址或搜索')),('network',('网络','窗口网络')),('downloads',('下载中心',))]}
    windows.update({phase:native(()) for phase in ('initial','compactReturn','longPressReturn','resumeReturn')})
    windows['environmentActivity']=native(('环境管理',),'local.pocketchat.test/local.pocketchat.WindowHomeActivity')
    targets={'addressOpen':('ready','compactTap'),'compactAddressOpen':('down','compactTap'),'longPressAddressOpen':('environmentMenuReturn','compactTap'),'moreMenu':('longPressReturn','moreTap'),'environmentActivity':('moreReturn','environmentTap'),'network':('upBeforeNetwork','networkTap'),'downloads':('networkReturn','downloadsTap'),'reading':('downloadsReturn','readingTap'),'readingReturn':('reading','exitTap'),'resumeAddressOpen':('activityResume','compactTap')}
    cancels={'addressCancel':'addressOpen','compactAddressCancel':'compactAddressOpen','longPressAddressCancel':'longPressAddressOpen','resumeAddressCancel':'resumeAddressOpen'}
    gestures={'up':('initial','up'),'down':('up','down'),'horizontal':('compactReturn','horizontal'),'short':('horizontal','short'),'upBeforeLongPress':('short','up'),'upBeforeNetwork':('environmentReturn','up'),'upBeforeResume':('readingReturn','up')}
    inputs=[]
    for kind,label in contract.INPUTS:
        item=dict(kind=kind,label=label,actualAndroidInput=True)
        if kind=='tap':
            item['point']=observations[cancels[label]]['addressDialog']['cancelTap'] if label in cancels else observations[targets[label][0]][targets[label][1]]
        elif kind=='swipe':
            if label=='headerUp':start,end=base['headerSwipeFrom'],base['headerSwipeTo']
            else:
                phase,direction=gestures[label];v=observations[phase];x=v['webX']+v['webWidth']//2;top=v['webY']+v['webHeight']//4;bottom=v['webY']+v['webHeight']*2//3;start,end=([x,bottom],[x,top]) if direction=='up' else ([x,top],[x,bottom])
                if direction=='horizontal':start=[v['webX']+v['webWidth']//4,(top+bottom)//2];end=[v['webX']+v['webWidth']*3//4,(top+bottom)//2]
                if direction=='short':start=[x,bottom];end=[x,bottom-12]
            item.update({'from':start,'to':end,'durationMs':320})
        elif kind=='longpress':item.update(point=observations['upBeforeLongPress']['compactTap'],durationMs=750)
        elif kind=='key':item['key']='KEYCODE_HOME' if label=='home' else 'KEYCODE_BACK'
        elif kind=='activity-start':item['component']=COMPONENT
        inputs.append(item)
    case=dict(navigationContract=2,sourceCommit=SOURCE,androidSdk=35,viewport=width,fontScale=scale,runNonce=nonce,actualAndroidExecution=True,actualGeckoExecution=True,actualAndroidTouchExecution=True,observations=observations,checks=[{'name':n,'pass':True} for n in contract.NAMES],nativeUiObservations=windows,actualAndroidInputs=inputs,fixtureRequests=[dict(kind='http',path='/c/reload-collapse',documentMarker='d'*32)],homeResume=dict(home='launcher/launcher.Home',returned=COMPONENT,homeObservedBeforeStart=True,elapsedSeconds=1.2,observations=[dict(component='launcher/launcher.Home',androidUser=0,activityState=activity('launcher/launcher.Home')),dict(component=COMPONENT,androidUser=0,activityState=activity(COMPONENT))]))
    bind_events(case);return case

def source_material(path):return b'getIntExtra("chromeNavigationVersion",1)!=2' if path=='tests/gecko/ChromeCollapseIntegration.java' else path.encode()

def report():
    return dict(navigationContract=2,status='passed',sourceCommit=SOURCE,sourceTree='b'*40,androidSdk=35,buildIdentity=identity(),actualAndroidExecution=True,actualGeckoExecution=True,actualAndroidTouchExecution=True,sourceInputsUnchanged=True,sourceFiles={p:hashlib.sha256(source_material(p)).hexdigest() for p in contract.INPUT_PATHS},cases=[make_case(w,f,str(i)*32) for i,(w,f) in enumerate(((360,1),(412,1),(360,2)),1)])

class ChromeV2EvidenceTests(unittest.TestCase):
    def verify(self,value):
        with patch.dict(os.environ,{'GIT_NO_LAZY_FETCH':'1'}):return contract.verify_auto_collapse_v2(value,SOURCE,'c'*64,source_reader=lambda s,p:source_material(p))

    def test_full_three_case_provider_packets_and_native_navigation_are_required(self):
        result=self.verify(report());self.assertEqual(result['navigationContract'],2);self.assertEqual(result['cases'],3);self.assertEqual(result['checks'],48)

    def test_version_dispatch_rejects_unknown_and_never_maps_legacy_to_v2(self):
        for v in (0,3,True,None,'2'):
            with self.subTest(version=v),self.assertRaises((ValueError,AssertionError)):
                dispatch.verify_auto_collapse(dict(navigationContract=v),'a'*40,'c'*64)
            with self.assertRaises(ValueError):legacy.run_current(None,None,None,None,None,None,navigation_version=v)
        with patch.object(legacy,'run',return_value='legacy') as old:
            self.assertEqual(legacy.run_current(1,2,3,4,5,6,navigation_version=1),'legacy');old.assert_called_once_with(1,2,3,4,5,6)
        for value in ({},{'navigationContract':1}):
            with self.assertRaisesRegex(ValueError,'Selected source requires'):
                dispatch.verify_auto_collapse(value,'06a802663075664b75aa9d19184d9c02b6bab7c9','c'*64)
        self.assertEqual(contract.selected_contract_version(SOURCE,source_reader=lambda s,p:b'original v1 fixture'),1)
        with self.assertRaisesRegex(ValueError,'Unknown selected-source'):
            contract.selected_contract_version(SOURCE,source_reader=lambda s,p:b'getIntExtra("chromeNavigationVersion",1)!=3')

    def test_forged_pass_flags_cannot_mask_real_snapshot_regressions(self):
        changes=[('up','cookie','different'),('up','pendingStored','lost'),('up','loads',1),('up','stops',1),('up','sendCount',1),('up','document','x'*32),('up','sdkSession',999),('up','webHeight',999),('network','page',3),('reading','navigationVisibility',0),('readingReturn','readingActive',True),('environmentReturn','activityStarts',0),('moreMenu','menuOpens',0),('headerUp','expanded',True),('addressOpen','addressDialog',{'visible':False})]
        for phase,key,value in changes:
            candidate=report();candidate['cases'][0]['observations'][phase][key]=value;bind_events(candidate['cases'][0])
            with self.subTest(phase=phase,key=key),self.assertRaises((AssertionError,KeyError,ValueError)):self.verify(candidate)

    def test_missing_up_trust_realm_or_release_is_rejected(self):
        for change in ('untrusted','realm','no-up','resize-live','native-no-up'):
            candidate=report();s=candidate['cases'][0]['observations']
            if change=='untrusted':s['up']['trusted'][0]['trusted']=False
            if change=='realm':s['up']['fixtureInputTelemetry']['realm']='extension-isolated-world'
            if change=='no-up':s['up']['touches'][-1]['action']=3
            if change=='resize-live':s['up']['touches'][1]['height']=42
            if change=='native-no-up':s['headerUp']['nativeTouches'][-1]['action']=3
            bind_events(candidate['cases'][0])
            with self.subTest(change=change),self.assertRaises(AssertionError):self.verify(candidate)

    def test_actual_inputs_native_windows_nonce_digest_and_source_cannot_be_swapped(self):
        for change in ('point','missing-action','longpress','native-label','native-activity','home','source','nonce','payload','request','case-size'):
            candidate=report();case=candidate['cases'][0]
            if change=='point':case['actualAndroidInputs'][0]['point']=[0,0]
            if change=='missing-action':case['actualAndroidInputs'].pop()
            if change=='longpress':next(x for x in case['actualAndroidInputs'] if x['kind']=='longpress')['durationMs']=1
            if change=='native-label':case['nativeUiObservations']['environmentMenu']=native(('unrelated',))
            if change=='native-activity':case['nativeUiObservations']['environmentActivity']['activityState']=activity(COMPONENT)
            if change=='home':case['homeResume']['homeObservedBeforeStart']=False
            if change=='source':candidate['sourceFiles'][contract.INPUT_PATHS[0]]='0'*64
            if change=='nonce':case['runNonce']='f'*32
            if change=='payload':case['eventTransfer']['events'][0]['rawUtf8']+=' '
            if change=='request':case['fixtureRequests'].append(copy.deepcopy(case['fixtureRequests'][0]))
            if change=='case-size':candidate['cases'][1]['viewport']=360
            with self.subTest(change=change),self.assertRaises((AssertionError,ValueError,KeyError)):self.verify(candidate)

    def test_relabelling_one_actual_size_font_or_density_as_three_cases_is_rejected(self):
        for field,value in [('nativeFontScale',1),('nativeScreenWidthDp',360),('nativeDensityDpi',420),('nativeDisplayWidth',1080),('webWidth',1080)]:
            candidate=report();case=candidate['cases'][2 if field=='nativeFontScale' else 1]
            for sample in case['observations'].values():sample[field]=value
            bind_events(case)
            with self.subTest(field=field),self.assertRaises(AssertionError):self.verify(candidate)

    def test_saved_real_ime_and_window_owner_are_recomputed_not_claimed(self):
        for phase,field,before,after in [('addressOpen','inputMethod','true','false'),('initial','inputMethod','false','true'),('addressOpen','windowState','mOwnerUid=10001','mOwnerUid=10002'),('addressOpen','windowState','mCurrentFocus=Window{abc','mCurrentFocus=Window{def')]:
            candidate=report();row=candidate['cases'][0]['nativeUiObservations'][phase];row[field]=row[field].replace(before,after)
            with self.subTest(phase=phase,field=field),self.assertRaises(AssertionError):self.verify(candidate)

    def test_legacy_run_and_full_oracle_function_bytes_and_ast_are_preserved(self):
        for path,name,sha in [('tests/gecko/run_chrome_collapse.py','run','fbd56ad879413151e5032b10b713f23fc17cf0f3a5d496451aa9ca8a55b647e4'),('tools/gecko/chrome_collapse_contract.py','verify_auto_collapse','834df0776ce08dcafd13fbe73acc2b129cf350dc1f45d7d01cded3e328937bc6')]:
            raw=(ROOT/path).read_text();node=next(n for n in ast.parse(raw).body if isinstance(n,ast.FunctionDef) and n.name==name);body=ast.get_source_segment(raw,node)
            self.assertEqual(hashlib.sha256(body.encode()).hexdigest(),sha)
            original=subprocess.check_output(['git','show','06a802663075664b75aa9d19184d9c02b6bab7c9:'+path],cwd=ROOT).decode();old=next(n for n in ast.parse(original).body if isinstance(n,ast.FunctionDef) and n.name==name)
            self.assertEqual(ast.dump(node,include_attributes=False),ast.dump(old,include_attributes=False))


class CurrentHomeBarrierTests(unittest.TestCase):
    def invoke(self,transport,inputs):
        from profile_chrome_home_resume_test import CLI,TARGET
        with patch.object(current.time,'monotonic',transport.clock),patch.object(current.time,'sleep',transport.sleep),patch.object(current.subprocess,'run',transport.run):
            return current.home_resume(TARGET,inputs,CLI)

    def test_actual_new_helper_observes_home_before_one_return_and_records_both_states(self):
        from profile_chrome_home_resume_test import Transport,TARGET,HOME
        transport=Transport();inputs=[];result=self.invoke(transport,inputs)
        self.assertEqual((transport.keys,transport.starts),(1,1));self.assertLessEqual(transport.now,20)
        self.assertEqual([r['component'] for r in result['observations']],[HOME,TARGET])
        self.assertEqual([(i['kind'],i['label']) for i in inputs],[('key','home'),('activity-start','activityResume')])
        self.assertLess(next(t for n,t in transport.events if n=='home-applied'),next(t for n,t in transport.events if n=='app-start'))

    def test_unobserved_home_or_history_only_never_starts_the_app(self):
        from profile_chrome_home_resume_test import Transport
        for flag in ('never_home','history_only','wrong_home','wrong_user'):
            transport=Transport();setattr(transport,flag,True)
            with self.subTest(flag=flag),self.assertRaises(TimeoutError):self.invoke(transport,[])
            self.assertEqual((transport.keys,transport.starts),(1,0));self.assertLessEqual(transport.now,20.000001)

    def test_missing_return_and_stalled_real_command_do_not_retry_or_extend_deadline(self):
        from profile_chrome_home_resume_test import Transport
        transport=Transport();transport.never_app=True
        with self.assertRaises(TimeoutError):self.invoke(transport,[])
        self.assertEqual((transport.keys,transport.starts),(1,1));self.assertLessEqual(transport.now,20.000001)
        transport=Transport();transport.stall=('shell','am','get-current-user')
        with self.assertRaises(TimeoutError) as caught:self.invoke(transport,[])
        self.assertIsInstance(caught.exception.__cause__,subprocess.TimeoutExpired)
        self.assertEqual((transport.keys,transport.starts),(0,0));self.assertLessEqual(transport.now,20.000001)

if __name__=='__main__':unittest.main(verbosity=2)
