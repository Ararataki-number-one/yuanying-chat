#!/usr/bin/env python3
"""Actual Android screenshots of production UI; never touches the formal app."""
import argparse,json,pathlib,re,struct,subprocess,time,xml.etree.ElementTree as ET
import http.server,importlib.util,threading,uuid,os
import sys

root=pathlib.Path(__file__).resolve().parents[2];out=root/'work/gecko-integration';shots=out/'ui-visuals';shots.mkdir(exist_ok=True)
p=argparse.ArgumentParser();p.add_argument('--adb',required=True);p.add_argument('--serial',required=True);args=p.parse_args()
source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
package='local.pocketchat.test';records=[]
sys.path.insert(0,str(root/'tools/gecko'))
from ui_visual_capture import UiVisualCapture
from diagnostic_capture_privacy import checked_text
from ui_visual_contract import LIGHT_SCENES, LARGE_SCENES, DARK_SCENES, LANDSCAPE_SCENES, required_captures, verify_captures, verify_download_location
scenes=LIGHT_SCENES
last_geometry=None
ui_capture=UiVisualCapture(adb=args.adb,serial=args.serial,source=source,diagnostics=out/'ui-visual-capture-attempts.json')
def adb(*values):return subprocess.check_output([args.adb,'-s',args.serial,*values],timeout=90).decode(errors='replace')
from ui_test_device import prepare_workflow as prepare_ui_test_device
(out/'ui-test-device-isolation.json').write_text(json.dumps(prepare_ui_test_device(adb,serial=args.serial,environment=os.environ),sort_keys=True,indent=2)+'\n')
def dump(deadline=None):
    return ui_capture.read(deadline=deadline)
def click(xml,label):
    node=next(n for n in ET.fromstring(xml).iter('node') if n.attrib.get('text')==label)
    x1,y1,x2,y2=map(int,re.findall(r'\d+',node.attrib['bounds']));adb('shell','input','tap',str((x1+x2)//2),str((y1+y2)//2))
def click_editor_tab(xml,label):
    deadline=time.monotonic()+20;swipes=0
    while time.monotonic()<deadline:
        tree=ET.fromstring(xml)
        target=next((n for n in tree.iter('node') if n.attrib.get('text')==label and n.attrib.get('clickable')=='true' and n.attrib.get('enabled')=='true'),None)
        if target is not None:
            click(xml,label);return swipes
        scroll=next((n for n in tree.iter('node') if n.attrib.get('class')=='android.widget.HorizontalScrollView' and any(child.attrib.get('text') in ['基本信息','网络配置','浏览器','使用偏好'] for child in n.iter('node'))),None)
        if scroll is not None and swipes<6:
            left,top,right,bottom=map(int,re.findall(r'\d+',scroll.attrib['bounds']));y=(top+bottom)//2
            adb('shell','input','swipe',str(left+(right-left)*4//5),str(y),str(left+(right-left)//5),str(y),'350');swipes+=1
        else:time.sleep(.2)
        xml=dump()
    raise TimeoutError(('Editor tab did not appear after horizontal scrolling',label,swipes,xml[-3000:]))
def checkpoint():
    partial={'status':'in_progress','actualAndroidExecution':True,'sourceCommit':source,'comparisonMode':'current-only','historicalUIRebuilt':False,'screenshots':records,'expectedCaptures':len(required_captures()),'scope':'Incomplete capture checkpoint for review; never release acceptance.'}
    (out/'ui-visual-results.json').write_text(json.dumps(partial,ensure_ascii=False,indent=2)+'\n')
    if os.environ.get('GITHUB_ACTIONS')=='true':
        result=subprocess.run([sys.executable,str(root/'tools/gecko/publish_ci.py')],cwd=root)
        print(json.dumps({'event':'ui-capture-checkpoint','count':len(records),'publishExitCode':result.returncode}),flush=True)
def capture(variant,width,height,scale,scene,theme='light'):
    global last_geometry
    started=time.monotonic();print(json.dumps({'event':'ui-capture-start','scene':scene,'viewport':f'{width}x{height}','fontScale':scale,'theme':theme,'completed':len(records)}),flush=True)
    adb('shell','am','force-stop',package);adb('logcat','-c')
    geometry=(width,height,scale)
    if geometry!=last_geometry:
        if 'com.google.android.apps.nexuslauncher' in adb('shell','pm','list','packages','com.google.android.apps.nexuslauncher'):adb('shell','am','force-stop','com.google.android.apps.nexuslauncher')
        adb('shell','wm','size',f'{width*3}x{height*3}');adb('shell','wm','density','480');adb('shell','settings','put','system','font_scale',str(scale));last_geometry=geometry
    label_nonce=uuid.uuid4().hex if scene=='downloads' else None
    launch=['shell','am','start','-W','-n',package+'/local.pocketchat.UiVisualIntegrationActivity','--es','visualAction',scene]
    if label_nonce:launch.extend(['--es','visualNonce',label_nonce])
    adb(*launch)
    required={'chat':'会话','environments':'环境管理','network':'固定测试出口','proxy':'代理地址','entries':'选择入口','browser':'基本信息','preferences':'基本信息','settings':'启动与界面','network-menu':'导入网络',
      'environment-picker':'切换环境','downloads':'项目资料与界面设计说明.pdf','feedback':'一句话说明','appearance':'白天与黑夜','default-entry':'默认环境与启动入口',
      'subscription-form':'订阅名称','exit-form':'SOCKS5 服务器','route-editor':'保存并应用','import':'选择分享文件','brand':'元婴期院士','templates':'选择模板','zoom':'网页缩放','update':'当前安装版本','audit':'环境自检与变更','file-preview':'双指缩放 · 拖动查看','delete-file':'删除文件','share-preview':'分享整条线路'}[scene]
    deadline=time.monotonic()+35;readiness_scrolls=0
    while True:
        xml=dump(deadline=deadline)
        runtime=adb('logcat','-d','-s','AndroidRuntime:E','*:S')
        if 'FATAL EXCEPTION' in runtime:raise AssertionError((variant,scene,'Android UI crashed',runtime[-5000:]))
        if required in xml:break
        if scene in ('exit-form','templates') and readiness_scrolls<8:
            candidates=[n for n in ET.fromstring(xml).iter('node') if n.attrib.get('class')=='android.widget.ScrollView' and n.attrib.get('scrollable')=='true']
            if candidates:
                left,top,right,bottom=map(int,re.findall(r'\d+',candidates[-1].attrib['bounds']));x=(left+right)//2
                adb('shell','input','swipe',str(x),str(top+(bottom-top)*4//5),str(x),str(top+(bottom-top)//5),'350');readiness_scrolls+=1
        if time.monotonic()>deadline:raise AssertionError((variant,scene,'screen did not appear',xml[-2000:]))
        time.sleep(.5)
    if scene=='templates':
        # Both fixed footer actions must fit without scrolling or clipping.
        for label in ('关闭','保存模板'):
            action=next((n for n in ET.fromstring(xml).iter('node') if n.attrib.get('text')==label and n.attrib.get('clickable')=='true'),None)
            assert action is not None,(variant,scene,'Template footer action missing',label)
            bounds=list(map(int,re.findall(r'\d+',action.attrib['bounds'])))
            assert bounds[3]-bounds[1]>=48*3 and 0<=bounds[1]<bounds[3]<=height*3,(variant,scene,'Template footer action clipped',label,bounds)
    if scene=='browser':
        headings=[n for n in ET.fromstring(xml).iter('node') if n.attrib.get('text','').startswith('编辑 · ')]
        assert headings,(variant,scene,'Missing long environment editor heading')
        bounds=list(map(int,re.findall(r'\d+',headings[0].attrib['bounds'])))
        assert bounds[3]-bounds[1]<=130*3,(variant,scene,'Environment title crowds out the editor',bounds)
        click_editor_tab(xml,'浏览器');time.sleep(2.5);xml=dump();assert '网页显示方式' in xml
    if scene=='preferences':
        tab_scrolls=click_editor_tab(xml,'使用偏好');time.sleep(.5)
        expected={'保存本机输入草稿','恢复网页滚动位置','允许此环境的后台回复提醒','仅在 Wi-Fi 下载文件','自动清理 30 天以上的无引用中间文件'}
        seen=set();collected=[]
        for attempt in range(8):
            xml=dump();collected.append(xml)
            seen.update(n.attrib.get('text','') for n in ET.fromstring(xml).iter('node') if n.attrib.get('class')=='android.widget.CheckBox')
            assert not any(label in xml for label in ['自动同步可见历史会话','文件保存完成通知','网络中断提醒','后台等待回复']),(variant,scene,xml)
            if seen==expected:break
            scroll=next(n for n in ET.fromstring(xml).iter('node') if n.attrib.get('class')=='android.widget.ScrollView')
            left,top,right,bottom=map(int,re.findall(r'\d+',scroll.attrib['bounds']));x=(left+right)//2
            adb('shell','input','swipe',str(x),str(top+(bottom-top)*4//5),str(x),str(top+(bottom-top)//5),'350')
        assert seen==expected,(variant,scene,'Preference controls missing or unexpected',sorted(seen))
        preference_check={'preferenceControls':sorted(seen),'removedNoticeControlsAbsent':True,'scrollFrames':len(collected),'tabScrolls':tab_scrolls}
    if scene=='chat':
        time.sleep(2.5);xml=dump();assert all(label in xml for label in ['会话','环境','下载','网络','设置'])
        assert not any(n.attrib.get('text') in ['简洁','原网页'] for n in ET.fromstring(xml).iter('node')),xml
        nodes=list(ET.fromstring(xml).iter('node'))
        environment=[n for n in nodes if n.attrib.get('content-desc','').startswith('当前环境：')]
        network=[n for n in nodes if n.attrib.get('content-desc','').startswith('当前环境网络：')]
        assert len(environment)==len(network)==1,xml
        assert environment[0].attrib.get('content-desc')=='当前环境：日常会话，点击展开环境工具栏' and environment[0].attrib.get('clickable')=='true',xml
        assert network[0].attrib.get('clickable')=='false',xml
        assert not any(n.attrib.get('content-desc') in ['管理环境','更多'] for n in nodes),xml
        left,top,right,bottom=map(int,re.findall(r'\d+',environment[0].attrib['bounds']))
        nl,nt,nr,nb=map(int,re.findall(r'\d+',network[0].attrib['bounds']))
        assert 0<=left<right<=width*3 and 0<=nl<nr<=width*3 and top<bottom==nt<nb,xml
        assert bottom-top<=(28 if scale==1 else 48)*3,xml
    assert 'FATAL EXCEPTION' not in adb('logcat','-d','-s','AndroidRuntime:E','*:S')
    if variant=='current' and scene=='entries':
        choices=[n for n in ET.fromstring(xml).iter('node') if n.attrib.get('class') in ['android.widget.CheckBox','android.widget.RadioButton']]
        assert choices,(variant,scene,'Missing entry choices')
        heights=[int(re.findall(r'\d+',n.attrib['bounds'])[3])-int(re.findall(r'\d+',n.attrib['bounds'])[1]) for n in choices]
        assert max(heights)>=144,(variant,scene,'Entry touch area below 48 dp',heights)
    stem=f'{variant}-'+('dark-' if theme=='dark' else '')+f'{width}x{height}-font{scale:g}-{scene}'
    (shots/(stem+'.xml')).write_text(xml)
    raw=subprocess.check_output([args.adb,'-s',args.serial,'exec-out','screencap','-p'],timeout=30)
    pixels=struct.unpack('>II',raw[16:24]);assert pixels==(width*3,height*3),(variant,scene,'Unexpected actual viewport',pixels)
    density=int(re.findall(r'density: (\d+)',adb('shell','wm','density'))[-1]);assert density==480,density
    (shots/(stem+'.png')).write_bytes(raw)
    record={'variant':variant,'theme':theme,'logicalViewport':f'{width}x{height}','actualPixels':list(pixels),'densityDpi':density,'fontScale':scale,'scene':scene,'image':stem+'.png','xml':stem+'.xml','readinessScrolls':readiness_scrolls}
    if scene=='downloads':
        # Small native payload from this exact Activity invocation; never infer
        # drawn text completeness from accessibility XML's full text attribute.
        label_log=subprocess.check_output([args.adb,'-s',args.serial,'logcat','-d','-s','PocketDownloadLabel:I','*:S'],timeout=30).decode('utf-8')
        payloads=[]
        for line in label_log.splitlines():
            if '{' not in line:continue
            raw=line[line.index('{'):]
            value=json.loads(raw)
            if value.get('nonce')==label_nonce:payloads.append(raw)
        assert len(payloads)==1,(variant,scene,'Missing or duplicate owned native label observation',payloads)
        record.update(downloadLocationNonce=label_nonce,downloadLocationRaw=payloads[0])
        (shots/(stem+'-download-location.json')).write_text(payloads[0]+'\n')
        verify_download_location(record,source)
    if scene=='preferences':record.update(preference_check)
    if scene=='environments':
        # Exercise the real multi-select footer, including doubled accessibility text.
        count=next(n for n in ET.fromstring(xml).iter('node') if n.attrib.get('text')=='8 个环境')
        bounds=list(map(int,re.findall(r'\d+',count.attrib['bounds'])))
        assert bounds[3]-bounds[1]<=48*3,(variant,scene,'Environment count wraps awkwardly',bounds)
        click(xml,'多选');xml=dump();click(xml,'全选当前结果');xml=dump()
        assert '已选 8 个' in xml,(variant,scene,'Actual select-all did not select the visible environments')
        for label in ('取消当前结果选中','批量分组','收藏','取消收藏'):
            action=next((n for n in ET.fromstring(xml).iter('node') if n.attrib.get('text')==label and n.attrib.get('class')=='android.widget.Button'),None)
            assert action is not None and action.attrib.get('enabled')=='true',(variant,scene,'Selection action unavailable',label)
            left,top,right,bottom=map(int,re.findall(r'\d+',action.attrib['bounds']))
            assert bottom-top>=48*3 and 0<=left<right<=width*3 and 0<=top<bottom<=height*3,(variant,scene,'Selection action clipped',label,action.attrib['bounds'])
        selected_stem=stem+'-selection';(shots/(selected_stem+'.xml')).write_text(xml)
        (shots/(selected_stem+'.png')).write_bytes(subprocess.check_output([args.adb,'-s',args.serial,'exec-out','screencap','-p'],timeout=30))
        record['selectionCheck']={'actualAndroidTaps':2,'actualAndroidBack':True,'selectedCount':8,'allFourFooterActionsVisible':True,'image':selected_stem+'.png'}
        adb('shell','input','keyevent','4');assert '批量分组' not in dump()
    records.append(record)
    print(json.dumps({'event':'ui-capture-complete','scene':scene,'count':len(records),'seconds':round(time.monotonic()-started,2)}),flush=True)
    if len(records)%10==0 or len(records)==len(required_captures()):checkpoint()
try:
    for variant in ['current']:
        adb('shell','am','force-stop',package)
        adb('install','-r',str(out/('ui-'+variant+'.apk')))
        adb('shell','pm','clear',package)
        if int(adb('shell','getprop','ro.build.version.sdk').strip())>=33:adb('shell','pm','grant',package,'android.permission.POST_NOTIFICATIONS')
        for width,height in [(360,640),(412,640)]:
            for scene in scenes:capture(variant,width,height,1,scene)
        for scene in LARGE_SCENES:capture(variant,360,640,2,scene)
        for scene in LANDSCAPE_SCENES:capture(variant,640,360,1,scene)
    adb('shell','cmd','uimode','night','yes')
    try:
        for scene in DARK_SCENES:capture('current',360,640,1,scene,theme='dark')
    finally:adb('shell','cmd','uimode','night','no')
    # Exercise the actual exit form with synthetic credentials and Android taps.
    exit_password=[]
    for width,scale in [(360,1),(360,2)]:
        adb('shell','am','force-stop',package);adb('shell','wm','size',f'{width*3}x1920');adb('shell','wm','density','480');adb('shell','settings','put','system','font_scale',str(scale))
        adb('shell','am','start','-W','-n',package+'/local.pocketchat.UiVisualIntegrationActivity','--es','visualAction','exit-password')
        deadline=time.monotonic()+35
        while True:
            xml=dump(deadline=deadline)
            if '隐藏密码' in xml and 'Synthetic-exit-7!' in xml:break
            if time.monotonic()>deadline:raise AssertionError(('Exit password is not visible by default',xml))
            scroll=next((n for n in ET.fromstring(xml).iter('node') if n.attrib.get('class')=='android.widget.ScrollView' and n.attrib.get('scrollable')=='true'),None)
            if scroll is not None:
                left,top,right,bottom=map(int,re.findall(r'\d+',scroll.attrib['bounds']));x=(left+right)//2
                adb('shell','input','swipe',str(x),str(top+(bottom-top)*4//5),str(x),str(top+(bottom-top)//5),'350')
            else:time.sleep(.3)
        click(xml,'隐藏');xml=dump();assert '显示密码' in xml and 'Synthetic-exit-7!' not in xml,xml
        click(xml,'显示');xml=dump();assert '隐藏密码' in xml and 'Synthetic-exit-7!' in xml,xml
        stem=f'exit-password-{width}-font{scale}'
        (out/(stem+'.xml')).write_text(xml)
        (out/(stem+'.png')).write_bytes(subprocess.check_output([args.adb,'-s',args.serial,'exec-out','screencap','-p'],timeout=30))
        exit_password.append(dict(viewport=width,fontScale=scale,defaultVisible=True,hideShowPreservesValue=True,actualAndroidTaps=2,image=stem+'.png'))
    # Supplementary native screens for the new mode, with trusted Android taps.
    optimization=[]
    for width,scale in [(360,1),(412,1),(360,2)]:
        adb('shell','am','force-stop',package);adb('shell','wm','size',f'{width*3}x1920');adb('shell','wm','density','480');adb('shell','settings','put','system','font_scale',str(scale))
        adb('shell','am','start','-W','-n',package+'/local.pocketchat.UiVisualIntegrationActivity','--es','visualAction','entries','--es','entryMode','latency')
        deadline=time.monotonic()+30
        while True:
            xml=dump()
            if '勾选允许使用的入口' in xml:break
            if time.monotonic()>deadline:raise AssertionError(('low latency modal missing',xml))
            time.sleep(.5)
        assert '自动优选' in xml and '重新随机' not in xml
        choices=[n for n in ET.fromstring(xml).iter('node') if n.attrib.get('class')=='android.widget.CheckBox'];assert choices
        stem=f'network-latency-{width}-font{scale}'
        (out/(stem+'.xml')).write_text(xml);(out/(stem+'.png')).write_bytes(subprocess.check_output([args.adb,'-s',args.serial,'exec-out','screencap','-p'],timeout=30))
        if scale==1:
            click(xml,'自动随机');xml=dump();assert '重新随机' in xml
            click(xml,'手动指定');xml=dump();assert any(n.attrib.get('class')=='android.widget.RadioButton' for n in ET.fromstring(xml).iter('node'))
            click(xml,'自动优选');xml=dump();assert '勾选允许使用的入口' in xml and '重新随机' not in xml
        optimization.append({'viewport':width,'fontScale':scale,'image':stem+'.png','xml':stem+'.xml','poolCheckboxes':len(choices)})
    # Production chrome at narrow/large-font sizes, including real taps in the
    # expanded touch regions rather than only calling performClick().
    compact=[]
    component=package+'/local.pocketchat.CompactChromeIntegrationActivity'
    def chrome_event(command,event):
        deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            raw=adb('logcat','-d','-s','PocketCompactChrome:I','AndroidRuntime:E','*:S')
            assert 'FATAL EXCEPTION' not in raw,raw[-5000:]
            for line in raw.splitlines():
                if 'PocketCompactChrome' not in line or '{' not in line:continue
                value=json.loads(line[line.index('{'):])
                if value.get('command')==command and value.get('event')==event:
                    assert not value.get('error'),value
                    return value
            time.sleep(.2)
        raise TimeoutError(('No compact chrome event',command,event,raw[-5000:]))
    def focus(activity):
        deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            state=adb('shell','dumpsys','activity','activities')
            if any(activity in line for line in state.splitlines() if 'mResumedActivity' in line or 'topResumedActivity' in line):return
            time.sleep(.2)
        raise TimeoutError(('Activity did not resume',activity,state[-3000:]))
    def visible(label,present=True):
        deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            xml=dump();found=any(n.attrib.get('text')==label or n.attrib.get('content-desc')==label for n in ET.fromstring(xml).iter('node'))
            if found==present:return
            time.sleep(.2)
        raise TimeoutError(('Dialog visibility did not settle',label,present,xml[-3000:]))
    for width,scale in [(360,1),(412,1),(360,2)]:
        adb('shell','am','force-stop',package);adb('logcat','-c')
        adb('shell','wm','size',f'{width*3}x1920');adb('shell','wm','density','480');adb('shell','settings','put','system','font_scale',str(scale))
        command=f'compact-{width}-{scale}'
        adb('shell','am','start','-W','-n',component,'--es','compactCommand',command)
        sample=chrome_event(command,'ready')
        assert sample['geckoOnly'] and sample['pageMode'] and sample['noNativeChat'] and sample['systemWebViews']==0,sample
        assert [control['name'] for control in sample['controls']]==['drawer','environment','more'],sample
        assert sample['latency']==sample['expectedLatency']=='42 ms（02:00）',sample
        assert not sample['networkClickable'] and not sample['networkFocusable'] and sample['networkBackground']=='none' and '点击' not in sample['networkDescription'],sample
        assert sample['toolbarHeightDp']<= (59 if scale==1 else 100),sample
        assert sample['topHeightDp']>=40 and sample['networkHeightDp']>=18,sample
        dot=sample['decorativeDot']
        assert abs(dot['textSizeDp']-9)<.01 and dot['inkWidth']<=dot['contentWidth']+1 and dot['fontHeight']<=dot['contentHeight']+1,(sample,dot)
        for text in sample['texts']:
            assert text['fontHeight']<=text['contentHeight']+1,(sample,text)
            assert text['text'] not in ['简洁','原网页'],(sample,text)
            if text['text'] in ['42 ms（02:00）','已连接']:assert not text['ellipsized'] and text['inkWidth']<=text['contentWidth']+1,(sample,text)
        if scale==2:assert sample['texts'][0]['ellipsized'],sample
        for control in sample['controls']:
            assert control['widthDp']>=47.9 and control['heightDp']>=47.9,(sample,control)
            l,t,r,b=control['touch'];tl,tt,tr,tb=sample['toolbar'];assert tl<=l<r<=tr and tt<=t<b<=tb,(sample,control)
            vl,vt,vr,vb=control['visible'];assert l<=(vl+vr)//2<r and t<=(vt+vb)//2<b,(sample,control,'Touch target misses visible view center')
            assert l<=vl<vr<=r and t<=vt<vb<=b,(sample,control,'Touch target does not cover visible view frame')
            assert b<=sample['networkTap'][1],(sample,control,'Touch target overlaps read-only network center')
        for left_control,right_control in zip(sample['controls'],sample['controls'][1:]):
            assert left_control['touch'][2]<=right_control['touch'][0],(sample,left_control,right_control,'Neighboring touch targets overlap')
        stem=f'compact-chrome-{width}-font{scale}'
        (shots/(stem+'.xml')).write_text(dump());(shots/(stem+'.png')).write_bytes(subprocess.check_output([args.adb,'-s',args.serial,'exec-out','screencap','-p'],timeout=30))
        for point in [sample['networkTap'],sample['stateTap']]:adb('shell','input','tap',str(point[0]),str(point[1]))
        command+='-status'
        adb('shell','am','start','-W','--activity-single-top','-n',component,'--es','compactAction','snapshot','--es','compactCommand',command)
        after=chrome_event(command,'snapshot');assert after['actions']==sample['actions']==0 and after['page']==0,after
        taps=[]
        for control in sample['controls']:
            command+= '-'+control['name']
            adb('shell','am','start','-W','--activity-single-top','-n',component,'--es','compactAction','snapshot','--es','compactCommand',command)
            before=chrome_event(command,'snapshot')
            adb('shell','input','tap',str(control['tap'][0]),str(control['tap'][1]))
            action=chrome_event(command,'action')
            expected='activity:local.pocketchat.WindowHomeActivity' if control['name']=='drawer' else control['name']
            assert action['action']==expected and action['actions']==before['actions']+1 and action['page']==0,(control,action)
            if control['name']=='drawer':
                focus('local.pocketchat.WindowHomeActivity')
                adb('shell','input','keyevent','KEYCODE_BACK')
                focus('local.pocketchat.CompactChromeIntegrationActivity')
            elif control['name']=='environment':
                visible('切换环境');visible('管理全部环境')
                adb('shell','input','keyevent','KEYCODE_BACK');visible('切换环境',False)
            elif control['name']=='more':
                label='会话选项'
                visible(label)
                adb('shell','input','keyevent','KEYCODE_BACK')
                visible(label,False)
            taps.append({'control':control['name'],'expandedRegion':True,'action':action['action']})
        command+='-performance'
        adb('shell','am','start','-W','--activity-single-top','-n',component,'--es','compactAction','performance','--es','compactCommand',command)
        performance=chrome_event(command,'performance')
        assert performance['status']=='passed',performance
        compact.append({'viewport':width,'fontScale':scale,'image':stem+'.png','xml':stem+'.xml','readOnlyStatus':True,'actualAndroidTaps':taps,'layout':sample,'performance':performance['performance']})
    # Real Gecko document + real protected loopback SOCKS, isolated synthetic login.
    # The ordinary three chrome cases and their trusted touch assertions remain intact.
    spec=importlib.util.spec_from_file_location('reload_loopback',root/'engine-probe/tests/run_device.py')
    reload_loopback=importlib.util.module_from_spec(spec);spec.loader.exec_module(reload_loopback)
    class ReloadHttp(reload_loopback.Fixture):
        def do_GET(self):
            if not self.path.startswith('/c/reload-'):self.send_error(404);return
            document_marker=uuid.uuid4().hex
            reload_loopback.TRACE.append({'kind':'http','path':self.path,'documentMarker':document_marker})
            body=b'''<!doctype html><html data-reload-document="__RELOAD_DOCUMENT__"><meta name="viewport" content="width=device-width,initial-scale=1"><style>body{font:18px sans-serif}#composer{position:fixed;bottom:0;background:white;width:90%}textarea{width:95%;height:70px}</style><main><article data-message-author-role="user" data-message-id="reload-user"><div data-user-message-bubble>already sent fixture question</div></article><section><div data-message-author-role="assistant" data-message-id="reload-reply"><div class="markdown"><p>Preserved controlled reply body.</p></div></div></section></main><form id="composer"><textarea id="prompt-textarea">unsent controlled browser draft</textarea><button type="button" data-testid="send-button" aria-label="Send" onclick="document.getElementById('send-count').textContent=Number(document.getElementById('send-count').textContent)+1">Send</button></form><span id="send-count">0</span><script>document.cookie='session=synthetic-reload; Path=/';</script></html>'''.replace(b'__RELOAD_DOCUMENT__',document_marker.encode('ascii'))
            if self.path=='/c/reload-collapse':
                body=body.replace(b'</main>',b'<div style="height:12000px;overflow:hidden">Controlled long reading document</div></main>')
                body=body.replace(b'</form>',b'<button type="button" data-testid="stop-button" aria-label="Stop">Stop</button></form>')
                body=body.replace(b'</html>',b'''<script>
                (()=>{
                  const root=document.documentElement;
                  const types=['touchstart','touchmove','touchend','touchcancel','pointerdown','pointermove','pointerup','pointercancel','mousedown','mousemove','mouseup','scroll'];
                  const trace={schema:1,realm:'page-main-world',document:root.dataset.reloadDocument,listenerTypes:types,
                    capabilities:{touchEvent:typeof TouchEvent==='function',pointerEvent:typeof PointerEvent==='function',maxTouchPoints:navigator.maxTouchPoints,
                      coarsePointer:matchMedia('(pointer:coarse)').matches,hover:matchMedia('(hover:hover)').matches},
                    count:0,dropped:0,events:[]};
                  const publish=()=>{root.dataset.chromeInputEvidence=JSON.stringify(trace);};
                  for(const type of types)addEventListener(type,e=>{
                    const p=e.changedTouches?.[0]||e.touches?.[0]||e;
                    const record={sequence:++trace.count,type:e.type,trusted:e.isTrusted,time:performance.now(),
                      pointerType:e.pointerType||'',x:Number.isFinite(p.clientX)?p.clientX:null,y:Number.isFinite(p.clientY)?p.clientY:null,scrollY:scrollY};
                    if(trace.events.length===256){trace.events.shift();trace.dropped++;}
                    trace.events.push(record);publish();
                  },{passive:true,capture:true});
                  publish();
                })();
                </script></html>''')
            self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(body)
    reload_http=http.server.ThreadingHTTPServer(('127.0.0.1',8765),ReloadHttp)
    reload_socks=reload_loopback.ThreadedSocks(('127.0.0.1',1080),reload_loopback.Socks)
    for server in [reload_http,reload_socks]:threading.Thread(target=server.serve_forever,daemon=True).start()
    adb('reverse','tcp:8765','tcp:8765');adb('reverse','tcp:1080','tcp:1080')
    reload_checks=[];reload_taps=[]
    def reload_check(name,value):
        reload_checks.append({'name':name,'pass':bool(value)})
        assert value,('Reload confirmation regression',name)
    def reload_command(action,event):
        global command
        command='reload-'+action+'-'+str(time.monotonic_ns())
        adb('shell','am','start','-W','--activity-single-top','-n',component,'--es','compactAction',action,'--es','compactCommand',command)
        return chrome_event(command,event)['reload']
    def reload_tap(modal,label):
        control=next(c for c in modal['controls'] if c['label']==label);left,top,right,bottom=control['bounds']
        assert control['enabled'] and control['clickable'] and left<=control['x']<right and top<=control['y']<bottom,control
        adb('shell','input','tap',str(control['x']),str(control['y']));reload_taps.append({'actualAndroidTap':True,**control})
    def reload_ready(value,ready_path,run):
        evidence=value.get('documentReadyEvidence',{})
        if not isinstance(evidence,dict):return False
        raw=evidence.get('rawMessage',{})
        if not isinstance(raw,dict):return False
        actual='http://127.0.0.1:8765'+ready_path;virtual='https://chatgpt.com'+ready_path
        return (value.get('visibleDocument') is True and evidence.get('acceptedByProduction') is True
            and isinstance(run,str) and re.fullmatch(r'reload-reloadStart-[0-9]+',run) is not None
            and evidence.get('fixtureRun')==evidence.get('registeredRun')==run
            and evidence.get('topLevel') is True and evidence.get('contentScript') is True
            and all(type(item) is int for item in (value.get('nativeSession'),evidence.get('nativeSession'),evidence.get('currentSession')))
            and value['nativeSession']==evidence.get('nativeSession')==evidence.get('currentSession')
            and raw.get('kind')=='documentReady' and raw.get('url')==evidence.get('senderUrl')==evidence.get('actualUrl')==actual
            and evidence.get('visibleUrl')==virtual and evidence.get('normalizedMessage')==dict(raw,url=virtual)
            and isinstance(value.get('document'),str) and re.fullmatch('[0-9a-f]{32}',value['document']) is not None
            and evidence.get('documentMarker')==value['document']
            and value.get('nativeUrl')=='http://127.0.0.1:8765'+value.get('path','')
            and value.get('currentUrl')=='https://chatgpt.com'+value.get('path',''))
    try:
        adb('shell','am','force-stop',package);adb('logcat','-c');adb('shell','wm','size','1080x1920');adb('shell','wm','density','480');adb('shell','settings','put','system','font_scale','1')
        initial=reload_command('reloadStart','reloadReady')
        reload_run=command
        reload_check('Controlled current SPA route and synthetic draft login are ready',reload_ready(initial,'/c/reload-A',reload_run) and len(initial.get('document',''))==32 and initial['path']=='/c/reload-B' and initial['cachedResumeUrl']=='https://chatgpt.com/c/reload-A' and initial['draft']=='unsent controlled browser draft' and 'session=synthetic-reload' in initial['cookie'] and initial['sendCount']==0 and initial['loads']==initial['stops']==0)
        modal=reload_command('requestReload','reloadModal');reload_check('Actual website reply requires a centered native reload confirmation',modal['centered'] and [control['label'] for control in modal['controls']]==['取消','重新加载'])
        reload_tap(modal,'取消');cancelled=reload_command('reloadSnapshot','reloadSnapshot')
        reload_check('Actual cancel preserves the document body draft login and native load counters',all(cancelled[k]==initial[k] for k in ['body','draft','cookie','sendCount','document','path','stops','loads']) and not cancelled['modal'])
        modal=reload_command('requestReload','reloadModal');changed=reload_command('changeRoute','routeChanged');reload_tap(modal,'重新加载');stale=reload_command('reloadSnapshot','reloadSnapshot')
        reload_check('Changing the actual current route makes an old confirmation harmless',stale['path']=='/c/reload-C' and stale['stops']==stale['loads']==0 and all(stale[k]==initial[k] for k in ['body','draft','cookie','sendCount','document']))
        reload_command('restoreRoute','routeRestored');modal=reload_command('requestReload','reloadModal');reload_tap(modal,'重新加载');confirmed=chrome_event(command,'reloaded')['reload']
        reload_check('Only explicit confirmation reloads the captured current conversation',reload_ready(confirmed,'/c/reload-B',reload_run) and confirmed['documents']==2 and confirmed['loads']==1 and confirmed['requested']=='https://chatgpt.com/c/reload-B' and confirmed['path']=='/c/reload-B' and confirmed['document']!=initial['document'])
        reload_check('Confirmed reload durably archives the draft without resubmission or login loss',confirmed['draftArchived'] and confirmed['sendCount']==0 and confirmed['cookie']==initial['cookie'])
        idle=reload_command('idleReload','reloaded')
        reload_check('An idle empty current page reloads directly without a confirmation',reload_ready(idle,'/c/reload-B',reload_run) and idle['documents']==3 and idle['loads']==2 and not idle['modal'] and idle['requested']=='https://chatgpt.com/c/reload-B' and idle['sendCount']==0)
        requests=[r for r in reload_loopback.TRACE if r['kind']=='http'];routes=[r for r in reload_loopback.TRACE if r['kind']=='socks' and r['accepted']];blocked=[r for r in reload_loopback.TRACE if r['kind']=='socks' and not r['accepted']]
        reload_check('All reload documents use the actual controlled SOCKS route without extra loads',len(requests)==3 and [r['documentMarker'] for r in requests]==[initial['document'],confirmed['document'],idle['document']] and len({r['documentMarker'] for r in requests})==3 and [r['path'] for r in requests]==['/c/reload-A','/c/reload-B','/c/reload-B'] and routes and all(r['port']==8765 and r['host']=='127.0.0.1' for r in routes))
        reload_confirmation={'actualAndroidExecution':True,'actualGeckoExecution':True,'sourceCommit':source,'checks':reload_checks,'actualAndroidTaps':reload_taps,'cancelMatched':all(cancelled[k]==initial[k] for k in ['body','draft','cookie','document']),'noStopNoLoad':cancelled['stops']==cancelled['loads']==0,'noSend':confirmed['sendCount']==idle['sendCount']==0,'fullDraftCookieUnchanged':cancelled['draft']==initial['draft'] and cancelled['cookie']==initial['cookie'],'explicitConfirmCurrentURI':confirmed['requested']==initial['currentUrl'],'notOldURI':confirmed['requested']!=initial['cachedResumeUrl'],'idleNoModal':not idle['modal'],'initial':initial,'cancelled':cancelled,'stale':stale,'confirmed':confirmed,'idle':idle,'fixtureRequests':requests,'controlledProxyRoutes':routes,'blockedRequests':blocked}
        # Preserve this exact completed object before the next scenario clears logcat.
        # This partial file cannot replace compact-chrome-results or full UI acceptance.
        (out/'ui-reload-confirmation.json').write_text(json.dumps(reload_confirmation,ensure_ascii=False,indent=2)+'\n')
        (out/'ui-reload-log.txt').write_text(checked_text(adb('logcat','-d'))[0])
        from run_chrome_collapse import run as run_chrome_collapse
        auto_collapse=run_chrome_collapse(adb,lambda *parts:subprocess.check_output([args.adb,'-s',args.serial,*parts],timeout=90),source,reload_loopback.TRACE,out,focus)
    finally:
        (out/'ui-collapse-server-trace.json').write_text(json.dumps({'sourceCommit':source,'diagnosticOnly':True,'releaseAcceptance':False,'events':reload_loopback.TRACE},ensure_ascii=False,indent=2)+'\n')
        reload_http.shutdown();reload_socks.shutdown()
    (out/'compact-chrome-results.json').write_text(json.dumps({'status':'passed','actualAndroidExecution':True,'sourceCommit':source,'cases':compact,'reloadConfirmation':reload_confirmation,'autoCollapse':auto_collapse},ensure_ascii=False,indent=2)+'\n')
    verify_captures(records,source)
    build=json.loads((out/'ui-build-comparison.json').read_text())
    assert build['comparisonMode']=='current-only' and not build['historicalUIRebuilt'] and build['coreSourceCommit']==source,build
    report={'status':'passed','actualAndroidExecution':True,'sourceCommit':source,'comparisonMode':'current-only','historicalUIRebuilt':False,'screenshots':records,'networkOptimizationScreens':optimization,'compactChromeScreens':compact,'reloadConfirmation':reload_confirmation,'autoCollapse':auto_collapse,'exitPassword':exit_password,'scope':'Current GeckoView-only production UI with local synthetic records, 111 current-source captures including workspaces, secondary forms, light, dark and double-font layouts, plus exit password checks; historical UI is not rebuilt. Website content, login and network core are not replaced.'}
except Exception as error:
    report={'status':'failed','actualAndroidExecution':True,'sourceCommit':source,'diagnosticOnly':False,'error':repr(error),'screenshots':records}
    (out/'ui-visual-log.txt').write_text(checked_text(adb('logcat','-d'))[0])
    (out/'ui-visual-failure.png').write_bytes(subprocess.check_output([args.adb,'-s',args.serial,'exec-out','screencap','-p'],timeout=30))
    (out/'ui-visual-failure.xml').write_text(dump())
    raise
finally:
    (out/'ui-visual-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    adb('shell','settings','put','system','font_scale','1');adb('shell','wm','size','reset');adb('shell','wm','density','reset')
