"""Synthetic parser/dispatch controls only; never Android acceptance artifacts."""
import ast
import copy
import hashlib
import json
import os
import shutil
import subprocess
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


def network_xml(width=360,scale=1):
    """Host-only current layout derived from the preserved native window shape."""
    tree=ET.fromstring((ROOT/'tests/fixtures/compact-network-dialog-c4.xml').read_text())
    parents={child:parent for parent in tree.iter() for child in parent}
    def get(identifier):return next(n for n in tree.iter('node') if n.get('resource-id')=='android:id/'+identifier)
    custom=get('customPanel');scroll=next(n for n in custom.iter('node') if n.get('class')=='android.widget.ScrollView')
    scroll.set('content-desc','当前环境网络详情');body=next(iter(scroll))
    # The real producer now reserves the native footer for Close; optional
    # actions belong to the body. These coordinates are a declared host model,
    # never a claim that the changed dialog has already run on Android.
    body.clear();body.attrib.update({'class':'android.widget.LinearLayout','package':previous.v2.PACKAGE,
        'enabled':'true','bounds':'[54,602][1026,1291]'})
    previous.node(body,'TextView','Controlled network details',rectangle=(54,602,1026,850))
    for identifier,description,top in (('button1','测一下网络延迟',850),('button3','查看当前网络连接详情',1000)):
        action=get(identifier);parents[action].remove(action);action.set('resource-id','');action.set('content-desc',description)
        action.set('bounds',f'[54,{top}][1026,{top+150}]');body.append(action)
    # Relative window containment and 48 dp remain checked for all cohorts.
    for node in tree.iter('node'):
        l,t,r,b=navigation.bounds(node)
        ys=1.15 if scale==2 else 1
        node.set('bounds',f'[{round(l*width/360)},{round(960+(t-960)*ys)}]'
                          f'[{round(r*width/360)},{round(960+(b-960)*ys)}]')
    return ET.tostring(tree,encoding='unicode')


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
        networkDetails=[modal(network_xml(width,scale)),modal(network_xml(width,scale))],networkDetailsFromHeader=True,
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


class NativeNetworkDialogTests(unittest.TestCase):
    def test_original_failed_capture_has_native_title_without_redundant_description(self):
        record=json.loads((ROOT/'tests/fixtures/compact-network-dialog-c4-provenance.json').read_text())
        self.assertIs(record['recordedFailureOnly'],True)
        self.assertEqual(record['originalStatus'],'failed')
        self.assertEqual(record['sourceCommit'],'b0f0ffb5758b943ccafa082569e7c767438d4d2a')
        self.assertEqual(record['checkpointCommit'],'efa7d88f8270d61329f05a20ab90c03697d4f03e')
        for row in record['files']:
            raw=(ROOT/'tests/fixtures'/row['fixture']).read_bytes()
            self.assertEqual(len(raw),row['bytes'])
            self.assertEqual(hashlib.sha256(raw).hexdigest(),row['sha256'])
            self.assertEqual(hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest(),row['gitBlob'])
        self.assertEqual(record['secondNetworkEntryGitBlob'],record['files'][0]['gitBlob'])
        raw=(ROOT/'tests/fixtures/compact-network-dialog-c4.xml').read_text();nodes=list(ET.fromstring(raw).iter('node'))
        title=[n for n in nodes if n.get('resource-id')=='android:id/alertTitle']
        self.assertEqual(len(title),1);self.assertEqual(title[0].get('content-desc'),'')
        old=[n for n in nodes if n.get('package')==previous.v2.PACKAGE and n.get('class')=='android.widget.TextView'
             and n.get('text')==n.get('content-desc')=='网络情况']
        self.assertEqual(old,[], 'The former custom-sheet predicate rejects this actual native title')
        self.assertEqual(next(n for n in nodes if n.get('resource-id')=='android:id/button1').get('enabled'),'false')
        with self.assertRaises(AssertionError):
            compact.network_dialog_visible(raw,previous.v2.PACKAGE)
        self.assertTrue(compact.network_dialog_visible(network_xml(),previous.v2.PACKAGE))
        closed=(ROOT/'tests/fixtures/compact-network-dialog-c4-closed.xml').read_text()
        self.assertFalse(compact.network_dialog_visible(closed,previous.v2.PACKAGE))

    def test_native_identity_geometry_and_half_modal_cannot_be_forged(self):
        changes=('duplicate-title','foreign-title','foreign-panel','hidden-title','hidden-panel','wrong-role',
                 'wrong-id','missing-close','disabled-close','unclickable-close','short-close','title-outside',
                 'close-outside','foreign-window','detached-close','panel-outside-window',
                 'missing-body','duplicate-body','foreign-body','body-outside','wrong-body-role',
                 'connection-in-footer','measure-in-footer','duplicate-measure','wrong-measure','disabled-connection',
                 'extra-footer-button','title-only','close-only')
        for change in changes:
            tree=ET.fromstring(network_xml());parents={child:parent for parent in tree.iter() for child in parent}
            def get(identifier):return next(n for n in tree.iter('node') if n.get('resource-id')=='android:id/'+identifier)
            title=get('alertTitle');close=get('button2');panel=get('parentPanel')
            if change=='duplicate-title':parents[title].append(copy.deepcopy(title))
            elif change=='foreign-title':title.set('package','foreign.app')
            elif change=='foreign-panel':panel.set('package','foreign.app')
            elif change=='hidden-title':title.set('visible-to-user','false')
            elif change=='hidden-panel':panel.set('visible-to-user','false')
            elif change=='wrong-role':title.set('class','android.widget.Button')
            elif change=='wrong-id':title.set('resource-id','foreign:id/alertTitle')
            elif change=='missing-close':parents[close].remove(close)
            elif change=='disabled-close':close.set('enabled','false')
            elif change=='unclickable-close':close.set('clickable','false')
            elif change=='short-close':close.set('bounds','[417,1303][560,1447]')
            elif change=='title-outside':title.set('bounds','[126,459][954,547]')
            elif change=='close-outside':close.set('bounds','[417,1459][681,1603]')
            elif change=='foreign-window':next(iter(tree)).set('package','foreign.app')
            elif change=='detached-close':
                parents[close].remove(close)
                other=previous.node(tree,'FrameLayout',rectangle=(0,0,1080,1920));other.append(close)
            elif change=='panel-outside-window':parents[panel].set('bounds','[54,461][1026,1459]')
            elif change in ('missing-body','duplicate-body','foreign-body','body-outside','wrong-body-role'):
                node=next(n for n in tree.iter('node') if n.get('content-desc')=='当前环境网络详情')
                if change=='missing-body':node.set('content-desc','')
                elif change=='duplicate-body':parents[node].append(copy.deepcopy(node))
                elif change=='foreign-body':node.set('package','foreign.app')
                elif change=='body-outside':node.set('bounds','[54,602][1026,1292]')
                else:node.set('class','android.widget.LinearLayout')
            elif change in ('connection-in-footer','measure-in-footer','duplicate-measure','wrong-measure','disabled-connection'):
                desc='查看当前网络连接详情' if 'connection' in change else '测一下网络延迟'
                node=next(n for n in tree.iter('node') if n.get('content-desc')==desc)
                if change.endswith('in-footer'):
                    parents[node].remove(node);get('buttonPanel').append(node)
                elif change=='duplicate-measure':parents[node].append(copy.deepcopy(node))
                elif change=='wrong-measure':node.set('class','android.widget.TextView')
                else:node.set('enabled','false')
            elif change=='extra-footer-button':
                duplicate=copy.deepcopy(close);duplicate.set('resource-id','');get('buttonPanel').append(duplicate)
            else:
                only=copy.deepcopy(title if change=='title-only' else close);tree=ET.Element('hierarchy');tree.append(only)
            with self.subTest(change=change),self.assertRaises((AssertionError,ValueError)):
                compact.network_dialog_visible(ET.tostring(tree,encoding='unicode'),previous.v2.PACKAGE)
        with self.assertRaises(AssertionError):
            compact.network_dialog_visible(menu_xml(title='网络情况'),previous.v2.PACKAGE)

    def test_scroll_body_actions_may_be_outside_first_viewport_but_footer_cannot_be(self):
        tree=ET.fromstring(network_xml());parents={child:parent for parent in tree.iter() for child in parent}
        for node in list(tree.iter('node')):
            if node.get('content-desc') in ('测一下网络延迟','查看当前网络连接详情'):
                parents[node].remove(node)
        self.assertTrue(compact.network_dialog_visible(ET.tostring(tree,encoding='unicode'),previous.v2.PACKAGE))
        close=next(n for n in tree.iter('node') if n.get('resource-id')=='android:id/button2')
        close.set('bounds','[417,1303][681,1381]')
        with self.assertRaisesRegex(AssertionError,'48 dp'):
            compact.network_dialog_visible(ET.tostring(tree,encoding='unicode'),previous.v2.PACKAGE)

    def test_original_c6_clipped_close_remains_failed_and_does_not_lower_target(self):
        record=json.loads((ROOT/'tests/fixtures/compact-network-dialog-c6-clipped-provenance.json').read_text())
        raw=(ROOT/'tests/fixtures'/record['fixture']).read_bytes()
        self.assertIs(record['recordedFailureOnly'],True);self.assertEqual(record['originalStatus'],'failed')
        self.assertEqual(record['sourceCommit'],'bdd3b3adffcc6e726fd7fe35872519063adc06ad')
        self.assertEqual(record['checkpointCommit'],'db44a3cb6d853ead46ef015926c6a8a502cd0b6d')
        self.assertEqual(len(raw),record['bytes']);self.assertEqual(hashlib.sha256(raw).hexdigest(),record['sha256'])
        self.assertEqual(hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest(),record['gitBlob'])
        node=next(n for n in ET.fromstring(raw).iter('node') if n.get('resource-id')=='android:id/button2')
        box=list(navigation.bounds(node));self.assertEqual(box,record['observedCloseBounds'])
        self.assertEqual(box[3]-box[1],78);self.assertLess(box[3]-box[1],144)
        with self.assertRaises(AssertionError):compact.network_dialog_visible(raw.decode(),previous.v2.PACKAGE)
        # The same observed 78 px target also fails in the current, otherwise
        # valid host layout; the failure is not hidden by the schema change.
        tree=ET.fromstring(network_xml());close=next(n for n in tree.iter('node') if n.get('resource-id')=='android:id/button2')
        close.set('bounds','[417,1303][681,1381]')
        with self.assertRaisesRegex(AssertionError,'48 dp'):
            compact.network_dialog_visible(ET.tostring(tree,encoding='unicode'),previous.v2.PACKAGE)

    def test_report_still_requires_both_original_raw_hashes_and_back_results(self):
        for change in ('hash','back','one-entry','custom-sheet'):
            value=case()
            if change=='hash':value['networkDetails'][0]['rawXml']+=' '
            elif change=='back':value['networkDetails'][1]['dismissedByBack']=False
            elif change=='one-entry':value['networkDetails'].pop()
            else:
                raw=menu_xml(title='网络情况')
                value['networkDetails'][0].update(rawXml=raw,rawXmlSha256=hashlib.sha256(raw.encode()).hexdigest())
            with self.subTest(change=change),self.assertRaises(AssertionError):compact.verify_case(value)

    def test_observer_rejects_late_open_and_closed_frames_at_original_deadline(self):
        closed=(ROOT/'tests/fixtures/compact-network-dialog-c4-closed.xml').read_text()
        for shown,raw in ((True,network_xml()),(False,closed)):
            clock=[10.];deadlines=[]
            def read(*,deadline):
                deadlines.append(deadline);clock[0]=deadline+.001;return raw
            with patch.object(producer.time,'monotonic',side_effect=lambda:clock[0]),self.assertRaises(TimeoutError):
                producer.observe_network_dialog(read,previous.v2.PACKAGE,shown)
            self.assertEqual(deadlines,[30.])
            original=producer.network_dialog_visible
            for completed in (30.,30.001):
                clock[0]=10.;deadlines.clear()
                def timely_read(*,deadline):deadlines.append(deadline);return raw
                def parsed_at_deadline(xml,package):
                    result=original(xml,package);clock[0]=completed;return result
                with patch.object(producer.time,'monotonic',side_effect=lambda:clock[0]),patch.object(producer,'network_dialog_visible',side_effect=parsed_at_deadline),self.assertRaises(TimeoutError):
                    producer.observe_network_dialog(timely_read,previous.v2.PACKAGE,shown)
                self.assertEqual(deadlines,[30.])

    def run_actual_network_segment(self, *, ignore_back=False):
        source=(ROOT/'tests/gecko/compact_chrome_v4.py').read_text();tree=ast.parse(source)
        run=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='run_case')
        index=next(i for i,n in enumerate(run.body) if isinstance(n,ast.For) and ast.unparse(n.target)=='(name, point, box)')
        fragment=ast.Module(body=run.body[index-1:index+1],type_ignores=[])
        self.assertEqual(ast.unparse(fragment.body[0]),'details = []')
        clock=[10.];opened=[False];commands=[];deadlines=[]
        raw=network_xml();closed=(ROOT/'tests/fixtures/compact-network-dialog-c4-closed.xml').read_text()
        def tap(*args):commands.append(('tap',)+args);opened[0]=True
        def adb(*args):
            self.assertEqual(args,('shell','input','keyevent','KEYCODE_BACK'));commands.append(('adb',)+args)
            if not ignore_back:opened[0]=False
        def dump(*,deadline):deadlines.append(deadline);return raw if opened[0] else closed
        def sleep(seconds):clock[0]+=seconds
        with tempfile.TemporaryDirectory() as d,patch.object(producer.time,'monotonic',side_effect=lambda:clock[0]),patch.object(producer.time,'sleep',side_effect=sleep):
            scope=dict(status=layout()['networkMetrics'],tap=tap,adb=adb,dump=dump,package=previous.v2.PACKAGE,
                       observe_network_dialog=producer.observe_network_dialog,hashlib=hashlib,shots=Path(d),stem='controlled')
            if ignore_back:
                with self.assertRaises(TimeoutError):exec(compile(fragment,'<actual-network-transitions>','exec'),scope)
                self.assertEqual(len(commands),2);self.assertEqual(scope['details'],[])
                self.assertTrue(all(deadline==30. for deadline in deadlines))
                self.assertEqual(clock[0],30.)
            else:
                exec(compile(fragment,'<actual-network-transitions>','exec'),scope)
                self.assertEqual([v[0:2] for v in commands],[('tap','network-status'),('adb','shell'),('tap','network-state'),('adb','shell')])
                self.assertEqual(deadlines,[30.]*4)
                self.assertEqual(len(scope['details']),2)
                for name,value in zip(('network-status','network-state'),scope['details']):
                    self.assertEqual((Path(d)/('controlled-'+name+'.xml')).read_text(),raw)
                    self.assertEqual(value,dict(rawXml=raw,rawXmlSha256=hashlib.sha256(raw.encode()).hexdigest(),dismissedByBack=True))

    def test_actual_two_network_inputs_keep_separate_open_one_back_and_closed_observations(self):
        self.run_actual_network_segment()

    def test_a_back_that_leaves_the_modal_open_cannot_qualify_or_retry_input(self):
        self.run_actual_network_segment(ignore_back=True)


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

    def test_header_xml_checks_visible_row_not_native_touch_delegate(self):
        for height,accepted in ((144,True),(96,True),(95,False)):
            tree=ET.fromstring(browser_xml())
            network=next(n for n in tree.iter('node') if n.get('content-desc','').startswith('当前环境网络：'))
            l,t,r,b=navigation.bounds(network)
            network.set('bounds',f'[{l},{t}][{r},{t+height}]')
            xml=ET.tostring(tree,encoding='unicode')
            if accepted:
                self.assertEqual(navigation.conversation_header(xml,previous.v2.PACKAGE,360,640,1,'Controlled environment',browser=True)['navigationContract'],4)
            else:
                with self.assertRaises(AssertionError):
                    navigation.conversation_header(xml,previous.v2.PACKAGE,360,640,1,'Controlled environment',browser=True)

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


class ProductionNetworkDialogTests(unittest.TestCase):
    def execute_show(self, method):
        from profile_gecko_window_selection_test import member
        java_home=os.environ.get('JAVA_HOME')
        java=Path(os.environ.get('PROFILE_JAVA') or (str(Path(java_home)/'bin/java') if java_home else '') or shutil.which('java') or '')
        javac=java.with_name('javac.exe' if os.name=='nt' else 'javac')
        self.assertTrue(java.is_file() and javac.is_file(),'A complete JDK with javac is required')
        template=(ROOT/'tests/network-metrics-dialog-host/NetworkMetricsDialogHost.java.in').read_text()
        self.assertEqual(template.count('/* ACTUAL_SHOW */'),1)
        with tempfile.TemporaryDirectory(prefix='network-dialog-host-') as directory:
            work=Path(directory);source=work/'NetworkMetricsDialogHost.java'
            source.write_text(template.replace('/* ACTUAL_SHOW */',method))
            compiled=subprocess.run([str(javac),'-encoding','UTF-8','-d',str(work),str(source)],capture_output=True,text=True,timeout=45)
            self.assertEqual(compiled.returncode,0,compiled.stdout+compiled.stderr)
            return subprocess.run([str(java),'-cp',str(work),'local.pocketchat.NetworkMetricsDialogHost'],capture_output=True,text=True,timeout=20)

    def production_show(self):
        from profile_gecko_window_selection_test import member
        return member((ROOT/'app/src/main/java/local/pocketchat/NetworkMetricsUi.java').read_text(),' static void show(MainActivity a){')

    def test_actual_single_footer_and_original_network_callbacks_tick_and_cleanup(self):
        result=self.execute_show(self.production_show())
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        report=json.loads(result.stdout)
        self.assertEqual(report['status'],'passed');self.assertGreaterEqual(report['checks'],55)
        self.assertIs(report['actualAndroidExecution'],False)

    def test_actual_host_rejects_footer_regression_cooldown_and_owner_cleanup_changes(self):
        actual=self.production_show()
        changes=(
            ('.setNegativeButton("关闭",null)', '.setPositiveButton("测一下延迟",null).setNegativeButton("关闭",null)'),
            ('SystemClock.elapsedRealtime()-n.lastManualProbe>=5000','SystemClock.elapsedRealtime()-n.lastManualProbe>=0'),
            ('a.handler.removeCallbacks(tick);',''),
            ('if(a.networkDialog==dialog)a.networkDialog=null;','a.networkDialog=null;'),
            ('dialog.dismiss();NetworkStatusUi.show(a);','NetworkStatusUi.show(a);dialog.dismiss();'),
            ('measure.setEnabled(false);',''),
        )
        for before,after in changes:
            self.assertEqual(actual.count(before),1)
            with self.subTest(mutation=before):
                result=self.execute_show(actual.replace(before,after))
                self.assertNotEqual(result.returncode,0,'Actual host did not reject '+before)
                self.assertIn('AssertionError',result.stderr)


class CompactNetworkTargetTests(unittest.TestCase):
    def test_compact_status_keeps_disjoint_48dp_target(self):
        value=layout(412,1);status=value['networkMetrics'];box=status['bounds']
        box[3]=box[1]+96
        value['toolbar'][3]=box[3]
        status['networkTap']=navigation.center(box)
        status['expandedTouch']=[box[2]-144,box[3]-144,box[2],box[3]]
        status['expandedTap']=[box[2]-72,box[3]-143]
        compact.verify_status(value)
        for kind in ('short','webpage','capsule','point','missing'):
            bad=copy.deepcopy(value);target=bad['networkMetrics']['expandedTouch']
            if kind=='short':target[1]+=1
            elif kind=='webpage':target[3]+=1
            elif kind=='capsule':target[0]=bad['controls'][0]['touch'][0]
            elif kind=='point':bad['networkMetrics']['expandedTap']=[-1,-1]
            else:del bad['networkMetrics']['expandedTouch']
            with self.subTest(kind=kind),self.assertRaises(AssertionError):compact.verify_status(bad)

if __name__=='__main__':unittest.main()
