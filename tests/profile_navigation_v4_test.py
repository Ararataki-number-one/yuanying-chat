"""Synthetic parser/dispatch controls only; never Android acceptance artifacts."""
import ast
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'tools/gecko'),str(ROOT/'tests/gecko')]
import compact_chrome_layout_v4 as compact
import workspace_navigation_contract_v4 as navigation
import chrome_collapse_contract_v4 as collapse
import chrome_collapse_contract as dispatch
import compact_chrome_v4 as producer
import gecko_chrome_collapse_v2_test as previous
from profile_release_navigation_v2_test import load_actual_gate


def metrics(text,box,role=14,scale=1,lines=1):
    return dict(text=text,bounds=box,fontHeight=role*3*scale,contentHeight=role*3*scale+6,
        inkWidth=60,contentWidth=box[2]-box[0]-12,ellipsized=scale==2,lineCount=1,
        maxLines=lines,layoutHeight=role*3*scale+6,textSizePx=role*3*scale,expectedTextSizePx=role*3*scale)


def layout(width=360,scale=1):
    w=width*3; capsule_height=max(36,30*scale+8)*3; top_height=max(48*3,capsule_height+12)
    top=[0,72,w,72+top_height]; capsule=[(w-576)//2,78,(w+576)//2,78+capsule_height]
    address_height=max(144,14*3*scale+60); bar_height=address_height+42; y=1896-bar_height
    at=y+18; action_y=at+(address_height-144)//2
    boxes=[[12,action_y,156,action_y+144],[156,action_y,300,action_y+144],
           [312,at,w-312,at+address_height],[w-300,action_y,w-156,action_y+144],[w-156,action_y,w-12,action_y+144]]
    descriptions=('打开当前环境主页','网页窗口','当前网址 https://example.test/photo，点击输入网址或搜索','网页工具','浏览器菜单')
    controls=[]
    for name,box,description in zip(('home','windows','address','tools','menu'),boxes,descriptions):
        value=dict(name=name,bounds=box,shown=True,enabled=True,clickable=True,description=description,tap=navigation.center(box))
        if name=='address':value['text']=metrics('example.test/photo',box,14,scale)
        controls.append(value)
    status_y=top[3]; status_bounds=[0,status_y,w,status_y+144]
    text_y=status_y+24
    texts=[metrics('日本 · 203.0.113.25',[36,text_y,w-450,text_y+12*3*scale+6],12,scale,2),
           metrics('42 ms（02:00）',[w-450,text_y,w-180,text_y+12*3*scale+6],12,scale,2),
           metrics('已连接',[w-180,text_y,w-18,text_y+11*3*scale+6],11,scale,1)]
    for item in texts[1:]: item['ellipsized']=False
    status=dict(bounds=status_bounds,networkTap=navigation.center(status_bounds),stateTap=navigation.center(texts[2]['bounds']),
        clickable=True,focusable=True,background='android.graphics.drawable.RippleDrawable',description='当前环境网络：日本 · 已连接',texts=texts,
        dot=dict(textSizeDp=9,inkWidth=12,contentWidth=36,fontHeight=28,contentHeight=60,height=60))
    touch=[capsule[0],top[1],capsule[2],top[3]]
    toolbar=[0,72,w,status_bounds[3]+1]
    return dict(navigationContract=4,browserChrome=True,geckoOnly=True,pageMode=True,noNativeChat=True,
        systemWebViews=0,viewportDp=width,fontScale=scale,syntheticPresentation=True,actualLatencyMeasurement=False,
        latency='42 ms（02:00）',expectedLatency='42 ms（02:00）',networkInHeader=True,networkShown=True,networkMetrics=status,
        topChildren=1,toolbar=toolbar,topBounds=top,toolbarHeightDp=(toolbar[3]-toolbar[1])/3,topHeightDp=top_height/3,
        windowBounds=[0,0,w,1920],webBounds=[0,toolbar[3],w,y],
        controls=[dict(name='environment',visible=capsule,touch=touch,widthDp=192,heightDp=top_height/3,tap=navigation.center(touch))],
        capsuleText=metrics('Controlled environment',capsule,15,scale),
        browserAddressRow=dict(bounds=[0,y,w,1896],padding=[12,18,12,24],stacked=False,shown=True,parentIsConversationBar=True,controls=controls))


def browser_xml(width=360,scale=1):
    value=layout(width,scale); root=ET.Element('hierarchy')
    host=previous.node(root,'FrameLayout',rectangle=value['windowBounds'])
    capsule_host=previous.node(host,'FrameLayout',rectangle=value['topBounds'])
    previous.node(capsule_host,'Button','Controlled environment','当前环境：Controlled environment，点按切换环境',
                  value['controls'][0]['visible'],**{'long-clickable':'false'})
    previous.node(host,'Button',description=value['networkMetrics']['description'],rectangle=value['networkMetrics']['bounds'])
    row=previous.node(host,'LinearLayout',rectangle=value['browserAddressRow']['bounds']);row.set('class','android.view.ViewGroup')
    for v in value['browserAddressRow']['controls']:
        previous.node(row,'Button',description=v['description'],rectangle=v['bounds'],enabled='true' if v['enabled'] else 'false')
    return ET.tostring(root,encoding='unicode')


def menu_xml(width=360, title='浏览器菜单'):
    root=ET.Element('hierarchy')
    right=width*3-78
    panel=previous.node(root,'LinearLayout',rectangle=(30,356,width*3-30,1812))
    header=previous.node(panel,'LinearLayout',rectangle=(78,434,right,578))
    previous.node(header,'TextView',title,title,rectangle=(78,434,right-144,578))
    previous.node(header,'Button',description='关闭'+title,rectangle=(right-144,434,right,578))
    scroll=previous.node(panel,'ScrollView',rectangle=(78,578,right,1728),scrollable='true')
    body=previous.node(scroll,'LinearLayout',rectangle=(78,578,right,1728))
    # Current first screen; the address editor has its own five real phases.
    labels=('后退','前进','刷新网页','复制当前网址','进入专注阅读') if title=='网页工具' else ('下载管理','快速切换环境','当前环境网络','管理全部环境','应用设置')
    for i,label in enumerate(labels):
        top=600+i*163
        previous.node(body,'Button',label,rectangle=(78,top,right,min(top+162,1728)),
                      enabled='false' if label=='前进' else 'true')
    return ET.tostring(root,encoding='unicode')


def window_xml(width=360):
    root=ET.Element('hierarchy'); panel=previous.node(root,'LinearLayout',rectangle=(30,356,width*3-30,1812))
    header=previous.node(panel,'LinearLayout',rectangle=(78,434,width*3-78,578))
    previous.node(header,'TextView','网页窗口','网页窗口',rectangle=(78,434,width*3-222,578))
    previous.node(header,'Button',description='关闭网页窗口',rectangle=(width*3-222,434,width*3-78,578))
    label='主页面 · 当前\nhttps://chatgpt.com/c/reload-collapse'
    previous.node(panel,'Button',label,'网页窗口：'+label,rectangle=(78,600,width*3-78,780),selected='true')
    return ET.tostring(root,encoding='unicode')


def case(width=360,scale=1):
    value=layout(width,scale); raw=menu_xml(width); target=navigation.menu_action(raw,previous.v2.PACKAGE,'管理全部环境')
    dialog_xml=previous.xml_for('initialAddress'); dialog=compact.address_dialog(dialog_xml,previous.v2.PACKAGE)
    dialog.update(rawXml=dialog_xml,rawXmlSha256=hashlib.sha256(dialog_xml.encode()).hexdigest(),cancelled=True,actionsBefore=2,actionsAfter=2)
    status=copy.deepcopy(value); status.update(actions=5,page=0)
    taps=[]
    for label,item,key,box_key in [
        ('menu-management',value['browserAddressRow']['controls'][4],'tap','bounds'),
        ('management',target,'point','bounds'),
        ('address',value['browserAddressRow']['controls'][2],'tap','bounds'),
        ('cancel-address',dialog['controls'][0],'point','bounds'),
        ('environment',value['controls'][0],'tap','touch'),
        ('windows',value['browserAddressRow']['controls'][1],'tap','bounds'),
        ('tools',value['browserAddressRow']['controls'][3],'tap','bounds')]:
        taps.append(dict(control=label,point=item[key],bounds=item[box_key],actualAndroidTap=True))
    network=status['networkMetrics']
    taps.extend([dict(control='network-status',point=network['networkTap'],bounds=network['bounds'],actualAndroidTap=True),
                 dict(control='network-state',point=network['stateTap'],bounds=network['texts'][2]['bounds'],actualAndroidTap=True)])
    def modal(raw):
        return dict(rawXml=raw,rawXmlSha256=hashlib.sha256(raw.encode()).hexdigest(),dismissedByBack=True)
    return dict(navigationContract=4,viewport=width,fontScale=scale,layout=value,
        actualAndroidTaps=taps,managementMenuXml=raw,menuScrolls=[],
        managementNavigation=dict(activity='local.pocketchat.WindowHomeActivity',actualMenuAction=True,resumedThenReturned=True),addressDialog=dialog,
        environmentSelection=dict(action='environment',inputKind='tap',addressDialogOpened=False,actionsBefore=2,actionsAfter=3),
        environmentSheet=dict(title='快速切换环境',currentSlot=0,searchDescription='搜索要切换的环境',closeDescription='关闭快速切换环境'),
        windowSheet=modal(window_xml(width)),toolsSheet=modal(menu_xml(width,'网页工具')),
        networkDetails=[modal(menu_xml(width,'网络情况')),modal(menu_xml(width,'网络情况'))],networkDetailsFromHeader=True,
        statusObservation=dict(before=status,after=copy.deepcopy(status)),environmentDismissedByBack=True)



def collapse_case(width,scale,nonce):
    """New counterfeit v4 record assembled only inside this host test."""
    old=previous.case_fixture(width,scale,nonce); original=old['observations']; observed={}
    menu_before={'networkMenu':'upBeforeNative','environmentMenu':'extrasExpanded','downloadsMenu':'environmentReturn',
                 'readingMenu':'downloadsReturn','readingBackMenu':'readingExit','drawerMenu':'moreReturn'}
    current=layout(width,scale); row=current['browserAddressRow']; header=current['controls'][0]['touch']
    toolbar_height=current['toolbar'][3]-current['toolbar'][1]
    sources={'compactPicker':'environmentPicker','compactPickerReturn':'pickerReturn','windowPicker':'more','windowReturn':'moreReturn'}
    for index,phase in enumerate(collapse.PHASES):
        value=copy.deepcopy(original[menu_before.get(phase,sources.get(phase,phase))])
        if phase=='ready':value=copy.deepcopy(original['initialChat'])
        if phase in collapse.PICKER_PHASES:
            value.update(expanded=True,compactVisibility=8,topVisibility=0)
        if phase in collapse.MENU_PHASES+collapse.PICKER_PHASES:value['windowFocus']=False
        expanded=value['expanded']
        height=toolbar_height if expanded else 144
        value.update(command=phase,navigationContract=4,navigationLayout='workspace-five' if phase in ('network','downloads') else 'browser-bottom',
            networkInHeader=True,networkVisibility=0 if expanded else 8,
            networkShown=expanded and phase not in ('network','downloads','reading','readingBackMode'),
            menuOpens=sum(index>=collapse.PHASES.index(p) for p in collapse.MENU_PHASES if p not in collapse.TOOLS_PHASES),
            toolsOpens=sum(index>=collapse.PHASES.index(p) for p in collapse.TOOLS_PHASES),
            windowsOpens=int(index>=collapse.PHASES.index('windowPicker')),
            environmentPickerOpens=sum(index>=collapse.PHASES.index(p) for p in ('compactPicker','environmentPicker')),
            activityStarts=2 if index>=collapse.PHASES.index('drawerReturn') else 1 if index>=collapse.PHASES.index('environmentReturn') else 0,
            browserToolbarBounds=row['bounds'],browserToolbarShown=phase not in ('network','downloads','reading','readingBackMode'),
            toolbarHeight=height,webHeight=1400+toolbar_height-height,webY=72+height,
            toolbarBounds=[0,72,width*3,72+height],headerButtonTouch=header,
            headerSwipeFrom=[width*3//2,header[3]-2],headerSwipeTo=[width*3//2,header[1]+3])
        value['compactTap']=None if expanded else [width*3//2,144]
        value['addressTap']=row['controls'][2]['tap']
        value['environmentCapsuleTap']=navigation.center(header) if expanded else value['compactTap']
        value['browserAddressTap']=row['controls'][2]['tap'];value['moreTap']=row['controls'][4]['tap']
        value['toolsTap']=row['controls'][3]['tap'];value['windowsTap']=row['controls'][1]['tap']
        if phase in ('reading','readingBackMode'):value['webHeight']=1400+toolbar_height+180
        observed[phase]=value
    for before,after in (('initialChat','up'),('up','down'),('compactExpand','horizontal')):
        a=observed[before];observed[after]['touches']=[dict(action=n,pointers=1,width=a['webWidth'],height=a['webHeight'],expanded=a['expanded']) for n in (0,2,1)]
    native={}
    for phase in collapse.UI_PHASES:
        if phase in collapse.NORMAL_UI_PHASES:xml=browser_xml(width,scale)
        elif phase in collapse.MENU_PHASES:xml=menu_xml(width,'网页工具' if phase in collapse.TOOLS_PHASES else '浏览器菜单')
        elif phase=='windowPicker':xml=window_xml(width)
        elif phase=='compactPicker':xml=previous.xml_for('environmentPicker',width,scale)
        else:
            xml=previous.xml_for(phase,width,scale)
            if phase in ('network','downloads','environment','drawer'):xml=xml.replace('会话','浏览器')
        component=collapse.ENVIRONMENT_ACTIVITY if phase in ('environment','drawer') else collapse.ACTIVITY
        activity='topResumedActivity=ActivityRecord{abc u0 '+component+' t8}\n'
        native[phase]=dict(phase=phase,runNonce=nonce,sourceCommit='a'*40,rawXml=xml,xmlBytes=len(xml.encode()),xmlSha256=hashlib.sha256(xml.encode()).hexdigest(),
            activityState=activity,activityBytes=len(activity.encode()),activitySha256=hashlib.sha256(activity.encode()).hexdigest())
    inputs=[]
    for label,kind,before,target in collapse.INPUTS:
        row_input=dict(label=label,kind=kind,before=before,actualAndroidInput=True); sample=observed.get(before)
        if kind=='tap':
            if target.startswith('menu:'):
                found=navigation.menu_action(native[before]['rawXml'],collapse.PACKAGE,target[5:]);row_input.update(point=found['point'],bounds=found['bounds'])
            elif target=='cancel':row_input.update(point=[200,665],bounds=[100,600,300,730])
            elif target=='closePicker':row_input.update(point=[875,175],bounds=[800,100,950,250])
            else:row_input['point']=sample[target]
        elif kind=='swipe':
            x=sample['webWidth']//2;top=sample['webY']+sample['webHeight']//4;bottom=sample['webY']+sample['webHeight']*2//3
            start,end=([x,bottom],[x,top]) if target=='up' else ([x,top],[x,bottom])
            if target=='short':start,end=[x,bottom],[x,bottom-12]
            if target=='horizontal':start,end=[sample['webWidth']//4,(top+bottom)//2],[sample['webWidth']*3//4,(top+bottom)//2]
            if target=='header':start,end=sample['headerSwipeFrom'],sample['headerSwipeTo']
            row_input.update({'from':start,'to':end,'durationMs':320})
        elif kind=='longPress':row_input.update(point=sample[target],durationMs=700)
        elif kind=='back':row_input['key']='KEYCODE_BACK'
        else:row_input.update(component=collapse.ACTIVITY,originalBudgetMs=20000)
        inputs.append(row_input)
    old.update(navigationContract=4,browserChrome=True,observations=observed,nativeUi=native,actualAndroidInputs=inputs,
        menuScrolls={p:[] for p in collapse.MENU_TARGETS},checks=[dict(name=n,pass_=True) for n in ()],
        legacyBehaviorMap=[list(v) for v in collapse.LEGACY_BEHAVIOR_MAP[2:]],browserStartupMap=[list(v) for v in collapse.BROWSER_STARTUP_MAP])
    old['checks']=[{'name':n,'pass':True} for n in collapse.BROWSER_NAMES]
    old['firstTapReadiness'].update(target='address',scope='chrome-initial-address-tap-only')
    previous.seal(old,previous.identity())
    return old


class BottomContractTests(unittest.TestCase):
    def test_actual_compact_geometry_and_receipts_for_all_declared_cohorts(self):
        for width,scale in ((360,1),(412,1),(360,2)):
            self.assertTrue(compact.verify_case(case(width,scale)))
            self.assertEqual(navigation.conversation_header(browser_xml(width,scale),previous.v2.PACKAGE,width,640,scale,'Controlled environment',browser=True)['navigationContract'],4)

    def test_current_layout_cannot_claim_old_header_or_overlap_hidden_targets(self):
        mutations=(lambda c:c['layout'].update(networkInHeader=False),lambda c:c['layout'].update(topChildren=3),
            lambda c:c['layout']['browserAddressRow'].update(parentIsConversationBar=False),
            lambda c:c['layout']['browserAddressRow']['controls'][4].update(shown=False),
            lambda c:c['layout']['browserAddressRow']['controls'][2]['bounds'].__setitem__(0,150),
            lambda c:c['layout']['browserAddressRow']['controls'][2]['text'].update(lineCount=2),
            lambda c:c['actualAndroidTaps'][2].update(bounds=c['layout']['controls'][0]['touch'],point=c['layout']['controls'][0]['tap']),
            lambda c:c['addressDialog'].update(rawXml=c['addressDialog']['rawXml']+' '),
            lambda c:c['statusObservation']['after'].update(actions=6))
        for change in mutations:
            value=case();change(value)
            with self.assertRaises((AssertionError,KeyError,ValueError)):compact.verify_case(value)

    def test_release_gate_accepts_current_and_rejects_mixed_or_downgraded_versions(self):
        report=dict(status='passed',actualAndroidExecution=True,sourceCommit='a'*40,cases=[case(w,s) for w,s in ((360,1),(412,1),(360,2))])
        self.assertTrue(load_actual_gate()(report,'a'*40))
        report['cases'][1]['navigationContract']=3
        with self.assertRaises(AssertionError):load_actual_gate()(report,'a'*40)

    def test_capsule_address_or_old_long_press_claim_cannot_qualify_v4(self):
        for change in ('old-description','long-press','missing-network','short-host'):
            tree=ET.fromstring(browser_xml());parents={child:parent for parent in tree.iter() for child in parent}
            cap=next(n for n in tree.iter('node') if n.get('content-desc','').startswith('当前环境：'))
            if change=='old-description':cap.set('content-desc','当前环境：Controlled environment，点按输入网址，长按切换环境')
            elif change=='long-press':cap.set('long-clickable','true')
            elif change=='short-host':parents[cap].set('bounds','[0,72][1080,215]')
            else:
                network=next(n for n in tree.iter('node') if n.get('content-desc','').startswith('当前环境网络：'))
                parents[network].remove(network)
            with self.subTest(change=change),self.assertRaises(AssertionError):
                navigation.conversation_header(ET.tostring(tree,encoding='unicode'),previous.v2.PACKAGE,360,640,1,'Controlled environment',browser=True)

    def test_tools_and_windows_keep_independent_native_modal_owners(self):
        for title,opened in (('网页工具',menu_xml(title='网页工具')),('网页窗口',window_xml())):
            self.assertTrue(producer.browser_panel_visible(opened,previous.v2.PACKAGE,title))
            self.assertFalse(producer.browser_panel_visible(browser_xml(),previous.v2.PACKAGE,title))
            tree=ET.fromstring(opened)
            next(n for n in tree.iter('node') if n.get('content-desc')=='关闭'+title).set('enabled','false')
            with self.subTest(panel=title),self.assertRaises(AssertionError):
                producer.browser_panel_visible(ET.tostring(tree,encoding='unicode'),previous.v2.PACKAGE,title)
        value=case();value['environmentSelection']['inputKind']='longPress'
        with self.assertRaises(AssertionError):compact.verify_case(value)
        value=case();raw=menu_xml(title='浏览器菜单')
        value['toolsSheet'].update(rawXml=raw,rawXmlSha256=hashlib.sha256(raw.encode()).hexdigest())
        with self.assertRaises(AssertionError):compact.verify_case(value)

    def test_actual_panel_observer_rejects_a_frame_arriving_after_original_deadline(self):
        for title in ('网页工具','网页窗口'):
            clock=[10.0];deadlines=[]
            def read(*,deadline):
                deadlines.append(deadline);clock[0]=deadline+.01
                return menu_xml(title=title)
            with patch.object(producer.time,'monotonic',side_effect=lambda:clock[0]),self.assertRaises(TimeoutError):
                producer.observe_browser_panel(read,previous.v2.PACKAGE,title,True)
            self.assertEqual(deadlines,[30])

    def test_a_fully_visible_tools_grid_needs_no_scroll_but_cannot_invent_one(self):
        tree=ET.fromstring(menu_xml(title='网页工具'))
        next(n for n in tree.iter('node') if n.get('class')=='android.widget.ScrollView').set('scrollable','false')
        raw=ET.tostring(tree,encoding='unicode');inputs=[];scrolls=[]
        def adb(*parts):inputs.append(parts)
        with patch.object(navigation.time,'monotonic',return_value=10):
            observed,target=navigation.seek_menu_action(adb,lambda **options:raw,previous.v2.PACKAGE,
                '进入专注阅读',deadline=30,scrolls=scrolls)
            self.assertEqual(observed,raw);self.assertEqual(target['label'],'进入专注阅读')
            parents={child:parent for parent in tree.iter() for child in parent}
            reading=next(n for n in tree.iter('node') if n.get('text')=='进入专注阅读');parents[reading].remove(reading)
            raw=ET.tostring(tree,encoding='unicode')
            with self.assertRaises(AssertionError):navigation.seek_menu_action(adb,lambda **options:raw,
                previous.v2.PACKAGE,'进入专注阅读',deadline=30,scrolls=scrolls)
        self.assertEqual(inputs,[]);self.assertEqual(scrolls,[])

class CollapseContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):previous.ChromeCollapseV2Controls.setUpClass()
    @classmethod
    def tearDownClass(cls):previous.ChromeCollapseV2Controls.tearDownClass()
    def fixture(self):
        return dict(navigationContract=4,browserChrome=True,status='passed',sourceCommit='a'*40,actualAndroidExecution=True,
            actualGeckoExecution=True,actualAndroidTouchExecution=True,buildIdentity=previous.identity(),
            cases=[collapse_case(w,s,str(i)*32) for i,(w,s) in enumerate(((360,1),(412,1),(360,2)),1)])
    def test_all_original_gestures_and_new_actual_menu_inputs_are_required(self):
        result=dispatch.verify_auto_collapse(self.fixture(),'a'*40,'c'*64)
        self.assertEqual(result['navigationContract'],4);self.assertEqual(result['retainedLegacyProtections'],12)
        self.assertEqual(sum(v[1]=='swipe' for v in collapse.INPUTS),8)
        self.assertEqual(result['actualInputsPerCase'],45)
    def test_menu_receipts_cannot_be_omitted_forged_or_use_old_dock_points(self):
        for change in (lambda r:r['cases'][0]['actualAndroidInputs'].pop(12),
            lambda r:r['cases'][0]['nativeUi'].pop('networkMenu'),
            lambda r:next(i for i in r['cases'][0]['actualAndroidInputs'] if i['label']=='network').update(point=[200,1800]),
            lambda r:r['cases'][0]['observations']['networkMenu'].update(menuOpens=0),
            lambda r:r['cases'][0].update(navigationContract=3)):
            report=self.fixture();change(report)
            with self.assertRaises((AssertionError,KeyError,ValueError)):dispatch.verify_auto_collapse(report,'a'*40,'c'*64)

    def test_complete_current_fixture_requires_more_controls_and_independent_address_editor(self):
        for phase,target in (('more','heading'),('more','close'),('more','download'),('initialAddress','editor')):
            report=self.fixture();observation=report['cases'][0]['nativeUi'][phase]
            tree=ET.fromstring(observation['rawXml']);parents={c:p for p in tree.iter() for c in p}
            if target=='heading':matches=[n for n in tree.iter('node') if n.get('text')=='浏览器菜单']
            elif target=='close':matches=[n for n in tree.iter('node') if n.get('content-desc')=='关闭浏览器菜单']
            elif target=='download':matches=[n for n in tree.iter('node') if n.get('text')=='下载管理']
            else:matches=[n for n in tree.iter('node') if n.get('class')=='android.widget.EditText']
            self.assertEqual(len(matches),1);parents[matches[0]].remove(matches[0])
            raw=ET.tostring(tree,encoding='unicode');encoded=raw.encode('utf-8')
            observation.update(rawXml=raw,xmlBytes=len(encoded),xmlSha256=hashlib.sha256(encoded).hexdigest())
            with self.subTest(phase=phase,target=target),self.assertRaises((AssertionError,KeyError,ValueError)):
                dispatch.verify_auto_collapse(report,'a'*40,'c'*64)


if __name__=='__main__':unittest.main()
