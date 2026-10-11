#!/usr/bin/env python3
"""Actual Android screenshots of production UI; never touches the formal app."""
import argparse,json,pathlib,re,struct,subprocess,time,xml.etree.ElementTree as ET

root=pathlib.Path(__file__).resolve().parents[2];out=root/'work/gecko-integration';shots=out/'ui-visuals';shots.mkdir(exist_ok=True)
p=argparse.ArgumentParser();p.add_argument('--adb',required=True);p.add_argument('--serial',required=True);args=p.parse_args()
package='local.pocketchat.test';scenes=['chat','environments','network','proxy','entries','browser','preferences'];records=[]
def adb(*values):return subprocess.check_output([args.adb,'-s',args.serial,*values],timeout=90).decode(errors='replace')
def dump():
    adb('shell','uiautomator','dump','/sdcard/ui-visual.xml')
    return adb('shell','cat','/sdcard/ui-visual.xml')
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
def capture(variant,width,height,scale,scene):
    adb('shell','am','force-stop',package);adb('logcat','-c')
    if 'com.google.android.apps.nexuslauncher' in adb('shell','pm','list','packages','com.google.android.apps.nexuslauncher'):adb('shell','am','force-stop','com.google.android.apps.nexuslauncher')
    adb('shell','wm','size',f'{width*3}x{height*3}');adb('shell','wm','density','480');adb('shell','settings','put','system','font_scale',str(scale))
    adb('shell','am','start','-W','-n',package+'/local.pocketchat.UiVisualIntegrationActivity','--es','visualAction',scene)
    required={'chat':'原网页','environments':'环境管理','network':'窗口网络','proxy':'代理地址','entries':'选择入口','browser':'基本信息','preferences':'基本信息'}[scene]
    deadline=time.monotonic()+35
    while True:
        xml=dump()
        runtime=adb('logcat','-d','-s','AndroidRuntime:E','*:S')
        if 'FATAL EXCEPTION' in runtime:raise AssertionError((variant,scene,'Android UI crashed',runtime[-5000:]))
        if required in xml:break
        if time.monotonic()>deadline:raise AssertionError((variant,scene,'screen did not appear',xml[-2000:]))
        time.sleep(.5)
    if scene=='browser':click_editor_tab(xml,'浏览器');time.sleep(2.5);xml=dump();assert '网页显示方式' in xml
    if scene=='preferences':
        tab_scrolls=click_editor_tab(xml,'使用偏好');time.sleep(.5)
        expected={'自动同步可见历史会话','保存本机输入草稿','恢复网页滚动位置','后台检测回复','回复完成通知','仅在 Wi-Fi 下载文件','自动清理 30 天以上的无引用中间文件'}
        seen=set();collected=[]
        for attempt in range(8):
            xml=dump();collected.append(xml)
            seen.update(n.attrib.get('text','') for n in ET.fromstring(xml).iter('node') if n.attrib.get('class')=='android.widget.CheckBox')
            assert not any(label in xml for label in ['文件保存完成通知','网络中断提醒','后台等待回复']),(variant,scene,xml)
            if seen==expected:break
            scroll=next(n for n in ET.fromstring(xml).iter('node') if n.attrib.get('class')=='android.widget.ScrollView')
            left,top,right,bottom=map(int,re.findall(r'\d+',scroll.attrib['bounds']));x=(left+right)//2
            adb('shell','input','swipe',str(x),str(top+(bottom-top)*4//5),str(x),str(top+(bottom-top)//5),'350')
        assert seen==expected,(variant,scene,'Preference controls missing or unexpected',sorted(seen))
        preference_check={'preferenceControls':sorted(seen),'removedNoticeControlsAbsent':True,'scrollFrames':len(collected),'tabScrolls':tab_scrolls}
    if scene=='chat':time.sleep(2.5);xml=dump();assert all(label in xml for label in ['会话','环境','下载','网络','设置','原网页'])
    assert 'FATAL EXCEPTION' not in adb('logcat','-d','-s','AndroidRuntime:E','*:S')
    if variant=='current' and scene=='entries':
        choices=[n for n in ET.fromstring(xml).iter('node') if n.attrib.get('class') in ['android.widget.CheckBox','android.widget.RadioButton']]
        assert choices,(variant,scene,'Missing entry choices')
        heights=[int(re.findall(r'\d+',n.attrib['bounds'])[3])-int(re.findall(r'\d+',n.attrib['bounds'])[1]) for n in choices]
        assert max(heights)>=144,(variant,scene,'Entry touch area below 48 dp',heights)
    stem=f'{variant}-{width}x{height}-font{scale:g}-{scene}'
    (shots/(stem+'.xml')).write_text(xml)
    raw=subprocess.check_output([args.adb,'-s',args.serial,'exec-out','screencap','-p'],timeout=30)
    pixels=struct.unpack('>II',raw[16:24]);assert pixels==(width*3,height*3),(variant,scene,'Unexpected actual viewport',pixels)
    density=int(re.findall(r'density: (\d+)',adb('shell','wm','density'))[-1]);assert density==480,density
    (shots/(stem+'.png')).write_bytes(raw)
    record={'variant':variant,'logicalViewport':f'{width}x{height}','actualPixels':list(pixels),'densityDpi':density,'fontScale':scale,'scene':scene,'image':stem+'.png','xml':stem+'.xml'}
    if scene=='preferences':record.update(preference_check)
    records.append(record)
try:
    for variant in ['baseline','current']:
        adb('shell','am','force-stop',package)
        adb('install','-r',str(out/('ui-'+variant+'.apk')))
        adb('shell','pm','clear',package)
        if int(adb('shell','getprop','ro.build.version.sdk').strip())>=33:adb('shell','pm','grant',package,'android.permission.POST_NOTIFICATIONS')
        for width,height in [(360,640),(412,640)]:
            for scene in scenes:capture(variant,width,height,1,scene)
        for scene in ['proxy','entries','browser','preferences']+(['chat'] if variant=='current' else []):capture(variant,360,640,2,scene)
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
        assert '低延迟优先' in xml and '重新随机' not in xml
        choices=[n for n in ET.fromstring(xml).iter('node') if n.attrib.get('class')=='android.widget.CheckBox'];assert choices
        stem=f'network-latency-{width}-font{scale}'
        (out/(stem+'.xml')).write_text(xml);(out/(stem+'.png')).write_bytes(subprocess.check_output([args.adb,'-s',args.serial,'exec-out','screencap','-p'],timeout=30))
        if scale==1:
            click(xml,'自动随机');xml=dump();assert '重新随机' in xml
            click(xml,'手动指定');xml=dump();assert any(n.attrib.get('class')=='android.widget.RadioButton' for n in ET.fromstring(xml).iter('node'))
            click(xml,'低延迟优先');xml=dump();assert '勾选允许使用的入口' in xml and '重新随机' not in xml
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
        assert sample['latency']==sample['expectedLatency']=='42 ms',sample
        assert not sample['networkClickable'] and not sample['networkFocusable'] and sample['networkBackground']=='none' and '点击' not in sample['networkDescription'],sample
        assert sample['toolbarHeightDp']<= (59 if scale==1 else 100),sample
        assert sample['topHeightDp']>=40 and sample['networkHeightDp']>=18,sample
        dot=sample['decorativeDot']
        assert abs(dot['textSizeDp']-9)<.01 and dot['inkWidth']<=dot['contentWidth']+1 and dot['fontHeight']<=dot['contentHeight']+1,(sample,dot)
        for text in sample['texts']:
            assert text['fontHeight']<=text['contentHeight']+1,(sample,text)
            if text['text'] in ['简洁','原网页','42 ms','已连接']:assert not text['ellipsized'] and text['inkWidth']<=text['contentWidth']+1,(sample,text)
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
            expected='activity:local.pocketchat.WindowHomeActivity' if control['name']=='environment' else control['name']
            assert action['action']==expected and action['actions']==before['actions']+1 and action['page']==0,(control,action)
            if control['name']=='environment':
                focus('local.pocketchat.WindowHomeActivity')
                adb('shell','input','keyevent','KEYCODE_BACK')
                focus('local.pocketchat.CompactChromeIntegrationActivity')
            elif control['name'] in ['drawer','more']:
                label='最近聊天' if control['name']=='drawer' else '会话选项'
                visible(label)
                adb('shell','input','keyevent','KEYCODE_BACK')
                visible(label,False)
            taps.append({'control':control['name'],'expandedRegion':True,'action':action['action']})
        compact.append({'viewport':width,'fontScale':scale,'image':stem+'.png','xml':stem+'.xml','readOnlyStatus':True,'actualAndroidTaps':taps,'layout':sample})
    source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
    (out/'compact-chrome-results.json').write_text(json.dumps({'status':'passed','actualAndroidExecution':True,'sourceCommit':source,'cases':compact},ensure_ascii=False,indent=2)+'\n')
    report={'status':'passed','actualAndroidExecution':True,'sourceCommit':source,'screenshots':records,'networkOptimizationScreens':optimization,'compactChromeScreens':compact,'scope':'Production native UI and original widgets with local synthetic records; webpage, login and network core not replaced.'}
except Exception as error:
    (out/'ui-visual-log.txt').write_text(adb('logcat','-d'))
    (out/'ui-visual-failure.png').write_bytes(subprocess.check_output([args.adb,'-s',args.serial,'exec-out','screencap','-p'],timeout=30))
    (out/'ui-visual-failure.xml').write_text(dump())
    report={'status':'failed','error':repr(error),'screenshots':records};raise
finally:
    (out/'ui-visual-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    adb('shell','settings','put','system','font_scale','1');adb('shell','wm','size','reset');adb('shell','wm','density','reset')
