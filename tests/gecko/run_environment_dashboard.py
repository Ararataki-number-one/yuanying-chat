"""Real browser entry and explicit environment details, using ADB touches.

Only the existing integration package is seeded. No production display method
is called by the fixture. This verifies Android display/entry/lifecycle, not
physical-phone startup performance, public IP123, or ChatGPT compatibility.
"""
import hashlib,json,pathlib,re,struct,time,xml.etree.ElementTree as ET

PACKAGE='local.pocketchat.test'

def environment_action_description(xml,environment):
    """Find the real named environment card without rewriting captured XML."""
    nodes=list(ET.fromstring(xml).iter('node'))
    prefix='打开浏览器：'+environment+'，'
    cards=[n for n in nodes if n.get('package')==PACKAGE and n.get('content-desc','').startswith(prefix)]
    assert len(cards)<=1,('ambiguous environment card',environment)
    if not cards:return None
    card=cards[0]
    assert card.get('class')=='android.widget.LinearLayout' and card.get('enabled')==card.get('clickable')=='true',('inactive environment action',environment,card.attrib)
    assert card.get('visible-to-user')!='false',('hidden environment action',environment)
    match=re.fullmatch(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]',card.get('bounds',''))
    assert match is not None,('missing environment card bounds',environment)
    l,t,r,b=map(int,match.groups());assert r>l and b>t,('empty environment card bounds',environment)
    names=[n for n in card.iter('node') if n.get('text')==environment]
    assert len(names)==1,('environment name missing or ambiguous in its card',environment)
    name=names[0]
    assert name.get('class')=='android.widget.TextView' and name.get('package')==PACKAGE and name.get('enabled')=='true',('environment card title differs',environment)
    title_bounds=re.fullmatch(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]',name.get('bounds',''))
    assert title_bounds is not None and name.get('visible-to-user')!='false',('environment card title hidden',environment)
    nl,nt,nr,nb=map(int,title_bounds.groups())
    assert l<=nl<nr<=r and t<=nt<nb<=b,('environment card title outside its action',environment)
    return card.get('content-desc')

def settings_workspace(xml):
    """Observe the actual settings identity, current section and browser action."""
    nodes=[n for n in ET.fromstring(xml).iter('node') if n.get('package')==PACKAGE]
    titles=[n for n in nodes if n.get('content-desc')=='应用设置' and n.get('text')=='设置']
    sections=[n for n in nodes if n.get('text')=='启动与外观']
    chats=[n for n in nodes if n.get('content-desc')==n.get('text')=='浏览器']
    if not titles or not sections or not chats:return False
    assert len(titles)==len(sections)==len(chats)==1,'ambiguous settings workspace identity'
    assert titles[0].get('class')==sections[0].get('class')=='android.widget.TextView','settings identity is not native text'
    assert chats[0].get('class')=='android.widget.Button' and chats[0].get('enabled')==chats[0].get('clickable')=='true','settings browser action is not available'
    return True

def details_menu_progress(xml,environment):
    """Select only the named native sheet; reveal its existing offscreen action."""
    root=ET.fromstring(xml);parents={c:p for p in root.iter() for c in p}
    titles=[n for n in root.iter('node') if n.get('text')==n.get('content-desc')==environment]
    closes=[n for n in root.iter('node') if n.get('content-desc')=='关闭'+environment]
    if not titles and not closes:return None
    assert len(titles)==len(closes)==1,'ambiguous environment menu'
    title,close=titles[0],closes[0]
    assert title.get('package')==close.get('package')==PACKAGE,'foreign environment menu'
    assert title.get('class')=='android.widget.TextView' and close.get('class')=='android.widget.Button'
    assert parents[title] is parents[close],'environment sheet header differs'
    sheet=parents[parents[title]]
    scrolls=[n for n in sheet if n.get('class')=='android.widget.ScrollView']
    assert len(scrolls)==1 and scrolls[0].get('package')==PACKAGE,'one owned menu scroll surface required'
    scroll=scrolls[0]
    def rectangle(node):
        match=re.fullmatch(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]',node.get('bounds',''))
        assert match is not None,'menu bounds missing'
        l,t,r,b=map(int,match.groups());assert l<r and t<b,'empty menu bounds'
        return l,t,r,b
    l,t,r,b=rectangle(scroll)
    targets=[n for n in scroll.iter('node') if n.get('text')=='环境详情']
    assert len(targets)<=1,'ambiguous environment details action'
    if targets:
        target=targets[0]
        assert target.get('package')==PACKAGE and target.get('class')=='android.widget.Button'
        assert target.get('enabled')==target.get('clickable')=='true','inactive environment details action'
        al,at,ar,ab=rectangle(target)
        if l<=al<ar<=r and t<=at<ab<=b and ab-at>=144 and target.get('visible-to-user')!='false':
            return dict(ready=True,bounds=[al,at,ar,ab])
    assert scroll.get('scrollable')=='true','environment details cannot be reached'
    return dict(ready=False,bounds=[l,t,r,b])

def run(adb,binary,source,out,dump):
    records=[];events=[];taps=[];directory=out/'ui-visuals/environment-dashboard';directory.mkdir(parents=True,exist_ok=True)
    def tree(xml):return list(ET.fromstring(xml).iter('node'))
    def dashboard(xml):return any(n.get('content-desc')=='环境仪表盘' for n in tree(xml))
    def browser(xml):
        assert not dashboard(xml),'Direct browser entry unexpectedly opened environment details'
        return any(n.get('content-desc')=='进入专注阅读模式' for n in tree(xml)) and any('长按切换环境' in n.get('content-desc','') for n in tree(xml))
    def wait(predicate,label,timeout=35):
        deadline=time.monotonic()+timeout
        while True:
            xml=dump(deadline=deadline)
            crash=adb('logcat','-d','-s','AndroidRuntime:E','*:S')
            assert 'FATAL EXCEPTION' not in crash,(label,crash[-4000:])
            if time.monotonic()>=deadline:raise AssertionError((label,'wait budget expired',xml[-5000:]))
            accepted=predicate(xml)
            if time.monotonic()>=deadline:raise AssertionError((label,'wait budget expired',xml[-5000:]))
            if accepted:return xml
            time.sleep(.2)
    def click(xml,label=None,description=None):
        node=next(n for n in tree(xml) if (label is not None and n.get('text')==label or description is not None and n.get('content-desc')==description) and n.get('enabled')=='true')
        l,t,r,b=map(int,re.findall(r'\d+',node.get('bounds')));assert r>l and b>t,(label,node.attrib)
        adb('shell','input','tap',str((l+r)//2),str((t+b)//2))
        taps.append(dict(label=label,description=description,x=(l+r)//2,y=(t+b)//2))
    def open_details(environment):
        adb('shell','am','start','-W','-n',PACKAGE+'/local.pocketchat.WindowHomeActivity')
        xml=wait(lambda x:environment_action_description(x,environment) is not None,'details environment card')
        click(xml,description='更多操作 '+environment)
        scrolls=0;details_target=None
        def details_ready(value):
            nonlocal scrolls,details_target
            progress=details_menu_progress(value,environment)
            if progress is None:return False
            if progress['ready']:
                details_target=progress['bounds'];return True
            assert scrolls<8,'environment details exceeded eight real menu scrolls'
            l,t,r,b=progress['bounds'];x=(l+r)//2
            start,end=t+(b-t)*4//5,t+(b-t)//5
            adb('shell','input','swipe',str(x),str(start),str(x),str(end),'300')
            scrolls+=1
            events.append(dict(name='reveal-explicit-environment-details',environment=environment,
                actualAndroidSwipe=dict(start=[x,start],end=[x,end],durationMillis=300,observedBounds=progress['bounds'])))
            return False
        xml=wait(details_ready,'explicit details menu')
        l,t,r,b=details_target
        adb('shell','input','tap',str((l+r)//2),str((t+b)//2))
        taps.append(dict(label='环境详情',description=None,x=(l+r)//2,y=(t+b)//2))
        return wait(lambda x:dashboard(x) and environment in x,'explicit environment details')
    def snapshot(name,xml,**metadata):
        for text in ('跳过','停留查看'):
            assert not any(n.get('text')==text for n in tree(xml)),('retired action still visible',text)
        assert not any(re.search(r'\d+\s*秒后进入',n.get('text','')) for n in tree(xml)),('countdown still visible',name)
        assert dashboard(xml),('dashboard absent',name)
        raw=binary('exec-out','screencap','-p');assert raw.startswith(b'\x89PNG\r\n\x1a\n')
        pixels=struct.unpack('>II',raw[16:24]);assert pixels==(width*3,height*3),(name,'actual screenshot viewport differs',pixels,[width*3,height*3])
        (directory/(name+'.xml')).write_text(xml);(directory/(name+'.png')).write_bytes(raw)
        records.append(dict(name=name,image='ui-visuals/environment-dashboard/'+name+'.png',xml='ui-visuals/environment-dashboard/'+name+'.xml',imageSha256=hashlib.sha256(raw).hexdigest(),actualPixelSize=list(pixels),**metadata))
    try:
        for name,width,height,scale,night in [('light',360,640,1,False),('large-font',360,640,2,False),('landscape',640,360,1,False),('dark',360,640,1,True)]:
            adb('shell','am','force-stop',PACKAGE);adb('logcat','-c')
            adb('shell','cmd','uimode','night','yes' if night else 'no')
            adb('shell','wm','size',f'{width*3}x{height*3}');adb('shell','wm','density','480');adb('shell','settings','put','system','font_scale',str(scale))
            observed=dict(size=adb('shell','wm','size').strip(),density=adb('shell','wm','density').strip(),fontScale=adb('shell','settings','get','system','font_scale').strip())
            assert float(observed['fontScale'])==scale,('Requested font scale not applied',observed)
            started=time.monotonic()
            # The unchanged fixture seeds local synthetic environments. Enter
            # through the real exported launcher, without a tall introduction
            # page whose button is offscreen at large text/landscape sizes.
            adb('shell','am','start','-W','-n',PACKAGE+'/local.pocketchat.UiVisualIntegrationActivity','--es','visualAction','environments')
            wait(lambda x:'环境管理' in x,name+' existing environment seed')
            adb('shell','am','start','-W','-n',PACKAGE+'/local.pocketchat.BrandLaunchActivity')
            wait(browser,name+' actual launcher browser')
            events.append(dict(name=name+'-launcher-opens-browser-directly',passed=True))
            xml=open_details('日常会话')
            node=next(n for n in tree(xml) if n.get('text')=='继续浏览' and n.get('enabled')=='true')
            l,t,r,b=map(int,re.findall(r'\d+',node.get('bounds')))
            assert 0<=l<r<=width*3 and 0<=t<b<=height*3 and b-t>=48*3,(name,'entry action clipped',node.attrib)
            snapshot(name,xml,entry='production-environment-details',viewport=[width,height],fontScale=scale,theme='dark' if night else 'light',observedAdbDisplay=observed,observationDelaySeconds=round(time.monotonic()-started,3))
            # Scroll the real native content to expose fingerprint rows on small
            # screens; the fixed entry button remains reachable.
            scroll=next(n for n in tree(xml) if n.get('class')=='android.widget.ScrollView')
            l,t,r,b=map(int,re.findall(r'\d+',scroll.get('bounds')));x=(l+r)//2
            heading_seen='指纹信息' in xml
            for _ in range(8):
                if 'User Agent' in xml:break
                adb('shell','input','swipe',str(x),str(t+(b-t)*4//5),str(x),str(t+(b-t)//5),'300');xml=dump();heading_seen=heading_seen or '指纹信息' in xml
            assert heading_seen and 'User Agent' in xml,(name,'fingerprint card not reachable',xml[-3000:])
            snapshot(name+'-fingerprint',xml)
            if name!='light':continue
            # A wait beyond the removed five-second deadline must never leave.
            until=time.monotonic()+7
            while time.monotonic()<until:
                xml=dump();assert dashboard(xml),'dashboard auto-dismissed before explicit entry';time.sleep(.5)
            events.append(dict(name='persists-beyond-five-seconds',seconds=7,passed=True))
            # Home/return must preserve the same open display; ordinary resume
            # after explicit entry must not insert a new dashboard.
            adb('shell','input','keyevent','KEYCODE_HOME')
            adb('shell','am','start','-W','-n',PACKAGE+'/local.pocketchat.MainActivity','--activity-reorder-to-front')
            xml=wait(dashboard,'dashboard retained over Home');snapshot('home-return',xml)
            click(xml,'继续浏览');wait(browser,'explicit return to browser')
            adb('shell','input','keyevent','KEYCODE_HOME')
            adb('shell','am','start','-W','-n',PACKAGE+'/local.pocketchat.MainActivity','--activity-reorder-to-front')
            wait(browser,'ordinary resume has no dashboard')
            events.append(dict(name='home-retains-open-dashboard-and-chat-resume-does-not-reinsert',passed=True))
            # Real list button, same existing environment/Activity instance.
            entry_taps=len(taps)
            adb('shell','am','start','-W','-n',PACKAGE+'/local.pocketchat.WindowHomeActivity')
            xml=wait(lambda x:environment_action_description(x,'日常会话') is not None,'environment list button')
            click(xml,description=environment_action_description(xml,'日常会话'));wait(browser,'warm list opens browser directly')
            events.append(dict(name='warm-list-opens-browser-without-dashboard',passed=True))
            xml=open_details('日常会话');snapshot('warm-list',xml)
            click(xml,'继续浏览');wait(lambda x:not dashboard(x),'warm explicit entry')
            # Match the reported second-environment case in its actual separate
            # Android profile process, using the real list's native button.
            adb('shell','am','start','-W','-n',PACKAGE+'/local.pocketchat.WindowHomeActivity')
            xml=wait(lambda x:environment_action_description(x,'日常会话') is not None,'list for second environment')
            for _ in range(5):
                if environment_action_description(xml,'资料整理') is not None:break
                scroll=next(n for n in tree(xml) if n.get('class')=='android.widget.ScrollView' and n.get('scrollable')=='true')
                l,t,r,b=map(int,re.findall(r'\d+',scroll.get('bounds')));x=(l+r)//2
                adb('shell','input','swipe',str(x),str(t+(b-t)*4//5),str(x),str(t+(b-t)//5),'300');xml=dump()
            click(xml,description=environment_action_description(xml,'资料整理'));wait(lambda x:browser(x) and '资料整理' in x,'separate process second browser')
            events.append(dict(name='second-process-opens-browser-without-dashboard',passed=True))
            xml=open_details('资料整理');snapshot('second-environment',xml,profileProcess='profile1',slot=1)
            click(xml,'继续浏览');wait(lambda x:not dashboard(x),'second environment explicit entry')
            # Settings workspace -> real bottom chat tab exercises the other
            # previously unmarked native navigation route.
            adb('shell','am','start','-W','-n',PACKAGE+'/local.pocketchat.WindowHomeActivity')
            xml=wait(lambda x:'环境管理' in x and '设置' in x,'manager settings entry')
            click(xml,'设置')
            xml=wait(settings_workspace,'settings workspace')
            click(xml,'浏览器');wait(browser,'workspace opens browser directly')
            events.append(dict(name='settings-browser-tab-has-no-dashboard',passed=True))
            xml=open_details('资料整理');snapshot('workspace-chat',xml)
            events.append(dict(name='warm-list-second-process-and-settings-chat-entry',actualAndroidTaps=len(taps)-entry_taps,passed=True))
        result=dict(schema=1,status='passed',sourceCommit=source,actualAndroidExecution=True,actualNativeDashboardRendering=True,physicalPhoneAcceptance=False,actualPublicSiteExecution=False,scope=__doc__.strip(),captures=records,events=events,actualAndroidTaps=taps)
        (out/'environment-dashboard-results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        (directory/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        return result
    except Exception as error:
        xml=dump();(directory/'failure.xml').write_text(xml);(directory/'failure.png').write_bytes(binary('exec-out','screencap','-p'))
        failure=dict(status='failed',sourceCommit=source,error=repr(error),captures=records,events=events,actualAndroidTaps=taps,physicalPhoneAcceptance=False)
        (out/'environment-dashboard-results.json').write_text(json.dumps(failure,ensure_ascii=False,indent=2)+'\n');(directory/'results.json').write_text(json.dumps(failure,ensure_ascii=False,indent=2)+'\n');raise
    finally:
        adb('shell','cmd','uimode','night','no');adb('shell','settings','put','system','font_scale','1')

def main():
    import argparse,subprocess,sys,os
    root=pathlib.Path(__file__).resolve().parents[2];out=root/'work/gecko-integration'
    parser=argparse.ArgumentParser();parser.add_argument('--adb',required=True);parser.add_argument('--serial',required=True);args=parser.parse_args()
    source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
    def binary(*parts):return subprocess.check_output([args.adb,'-s',args.serial,*parts],timeout=90)
    def adb(*parts):return binary(*parts).decode(errors='replace')
    # Only our integration package is replaced/cleared. The next original UI
    # runner independently reinstalls and clears this same test package.
    adb('shell','am','force-stop',PACKAGE)
    adb('install','-r',str(out/'ui-current.apk'))
    adb('shell','pm','clear',PACKAGE)
    if int(adb('shell','getprop','ro.build.version.sdk').strip())>=33:adb('shell','pm','grant',PACKAGE,'android.permission.POST_NOTIFICATIONS')
    sys.path.insert(0,str(root/'tools/gecko'))
    from ui_visual_capture import UiVisualCapture
    from ui_settings_services_device11 import prepare_workflow,finish_workflow
    capture=UiVisualCapture(adb=args.adb,serial=args.serial,source=source,diagnostics=out/'dashboard-capture-attempts.json')
    lease=prepare_workflow(adb,serial=args.serial,environment=os.environ,root=root,source=source,record_path=out/'dashboard-settings-services-isolation.json')
    report={'status':'failed','sourceCommit':source,'physicalPhoneAcceptance':False}
    try:
        report=run(adb,binary,source,out,capture.read)
        print(json.dumps({'status':report['status'],'sourceCommit':source,'actualAndroidExecution':True,'dashboardCaptures':len(report['captures']),'physicalPhoneAcceptance':False}))
    finally:
        finish_workflow(lease,report)
        adb('shell','wm','size','reset');adb('shell','wm','density','reset')

if __name__=='__main__':main()
