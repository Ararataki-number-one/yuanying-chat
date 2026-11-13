"""Exact product-contract ports for browser entry; Android always runs current source.

The user requested direct browser entry. Original dashboard cohorts, screenshots,
identity/lifecycle observations, touch receipts and timeouts remain; dashboard
checks now explicitly choose Environment details. Direct browser observations
are additional assertions, not a substitute for the preserved details checks.
This inverse exists only so historical source-oracle tests can still verify
all unrelated accepted code. It is never used by a device runner.
"""
import hashlib

BEFORE = (14703, 'c6e2577110d22112722a25eb0f6a964d2558f8f7eb9cf1d2a794b4644cfa3849')
AFTER = (19155, '9a05109b387eaca468b074e4916ad644e160fbe3d7e29ca30df74f5b43e34494')
HUNKS = (('"""Real production launcher/list/MainActivity dashboards, using ADB touches.',
  '"""Real browser entry and explicit environment details, using ADB touches.',
  1),
 ("    prefix='打开环境：'+environment+'，'", "    prefix='打开浏览器：'+environment+'，'", 1),
 ('    """Observe the actual settings identity, current section and chat action."""',
  '    """Observe the actual settings identity, current section and browser action."""',
  1),
 ("    chats=[n for n in nodes if n.get('content-desc')==n.get('text')=='会话']",
  "    chats=[n for n in nodes if n.get('content-desc')==n.get('text')=='浏览器']",
  1),
 ("'settings chat action is not available'", "'settings browser action is not available'", 1),
 ("    def dashboard(xml):return any(n.get('content-desc')=='环境仪表盘' for n in tree(xml))\n",
  "    def dashboard(xml):return any(n.get('content-desc')=='环境仪表盘' for n in tree(xml))\n"
  '    def browser(xml):\n'
  "        assert not dashboard(xml),'Direct browser entry unexpectedly opened environment details'\n"
  "        return any(n.get('content-desc')=='进入专注阅读模式' for n in tree(xml)) and any('长按切换环境' in "
  "n.get('content-desc','') for n in tree(xml))\n",
  1),
 ('    def snapshot(name,xml,**metadata):\n',
  '    def open_details(environment):\n'
  "        adb('shell','am','start','-W','-n',PACKAGE+'/local.pocketchat.WindowHomeActivity')\n"
  "        xml=wait(lambda x:environment_action_description(x,environment) is not None,'details environment "
  "card')\n"
  "        click(xml,description='更多操作 '+environment)\n"
  '        scrolls=0;details_target=None\n'
  '        def details_ready(value):\n'
  '            nonlocal scrolls,details_target\n'
  '            progress=details_menu_progress(value,environment)\n'
  '            if progress is None:return False\n'
  "            if progress['ready']:\n"
  "                details_target=progress['bounds'];return True\n"
  "            assert scrolls<8,'environment details exceeded eight real menu scrolls'\n"
  "            l,t,r,b=progress['bounds'];x=(l+r)//2\n"
  '            start,end=t+(b-t)*4//5,t+(b-t)//5\n'
  "            adb('shell','input','swipe',str(x),str(start),str(x),str(end),'300')\n"
  '            scrolls+=1\n'
  "            events.append(dict(name='reveal-explicit-environment-details',environment=environment,\n"
  '                '
  "actualAndroidSwipe=dict(start=[x,start],end=[x,end],durationMillis=300,observedBounds=progress['bounds'])))\n"
  '            return False\n'
  "        xml=wait(details_ready,'explicit details menu')\n"
  '        l,t,r,b=details_target\n'
  "        adb('shell','input','tap',str((l+r)//2),str((t+b)//2))\n"
  "        taps.append(dict(label='环境详情',description=None,x=(l+r)//2,y=(t+b)//2))\n"
  "        return wait(lambda x:dashboard(x) and environment in x,'explicit environment details')\n"
  '    def snapshot(name,xml,**metadata):\n',
  1),
 ("            xml=wait(dashboard,name+' actual launcher dashboard')\n",
  "            wait(browser,name+' actual launcher browser')\n"
  "            events.append(dict(name=name+'-launcher-opens-browser-directly',passed=True))\n"
  "            xml=open_details('日常会话')\n",
  1),
 ("entry='production-brand-launcher'", "entry='production-environment-details'", 1),
 ("'进入聊天'", "'继续浏览'", 4),
 ("click(xml,'继续浏览');wait(lambda x:not dashboard(x) and '会话' in x,'explicit chat entry')",
  "click(xml,'继续浏览');wait(browser,'explicit return to browser')",
  1),
 ("wait(lambda x:not dashboard(x) and '会话' in x,'ordinary resume has no dashboard')",
  "wait(browser,'ordinary resume has no dashboard')",
  1),
 ("            click(xml,description=environment_action_description(xml,'日常会话'));xml=wait(dashboard,'warm "
  "list opens dashboard');snapshot('warm-list',xml)\n",
  "            click(xml,description=environment_action_description(xml,'日常会话'));wait(browser,'warm list "
  "opens browser directly')\n"
  "            events.append(dict(name='warm-list-opens-browser-without-dashboard',passed=True))\n"
  "            xml=open_details('日常会话');snapshot('warm-list',xml)\n",
  1),
 ("            click(xml,description=environment_action_description(xml,'资料整理'));xml=wait(lambda "
  "x:dashboard(x) and '资料整理' in x,'separate process second "
  "environment');snapshot('second-environment',xml,profileProcess='profile1',slot=1)\n",
  "            click(xml,description=environment_action_description(xml,'资料整理'));wait(lambda x:browser(x) "
  "and '资料整理' in x,'separate process second browser')\n"
  "            events.append(dict(name='second-process-opens-browser-without-dashboard',passed=True))\n"
  '            '
  "xml=open_details('资料整理');snapshot('second-environment',xml,profileProcess='profile1',slot=1)\n",
  1),
 ("            click(xml,'会话');xml=wait(dashboard,'workspace chat opens "
  "dashboard');snapshot('workspace-chat',xml)\n",
  "            click(xml,'浏览器');wait(browser,'workspace opens browser directly')\n"
  "            events.append(dict(name='settings-browser-tab-has-no-dashboard',passed=True))\n"
  "            xml=open_details('资料整理');snapshot('workspace-chat',xml)\n",
  1),
 ('def run(',
  'def details_menu_progress(xml,environment):\n'
  '    """Select only the named native sheet; reveal its existing offscreen action."""\n'
  '    root=ET.fromstring(xml);parents={c:p for p in root.iter() for c in p}\n'
  "    titles=[n for n in root.iter('node') if n.get('text')==n.get('content-desc')==environment]\n"
  "    closes=[n for n in root.iter('node') if n.get('content-desc')=='关闭'+environment]\n"
  '    if not titles and not closes:return None\n'
  "    assert len(titles)==len(closes)==1,'ambiguous environment menu'\n"
  '    title,close=titles[0],closes[0]\n'
  "    assert title.get('package')==close.get('package')==PACKAGE,'foreign environment menu'\n"
  "    assert title.get('class')=='android.widget.TextView' and close.get('class')=='android.widget.Button'\n"
  "    assert parents[title] is parents[close],'environment sheet header differs'\n"
  '    sheet=parents[parents[title]]\n'
  "    scrolls=[n for n in sheet if n.get('class')=='android.widget.ScrollView']\n"
  "    assert len(scrolls)==1 and scrolls[0].get('package')==PACKAGE,'one owned menu scroll surface "
  "required'\n"
  '    scroll=scrolls[0]\n'
  '    def rectangle(node):\n'
  "        match=re.fullmatch(r'\\[(\\d+),(\\d+)\\]\\[(\\d+),(\\d+)\\]',node.get('bounds',''))\n"
  "        assert match is not None,'menu bounds missing'\n"
  "        l,t,r,b=map(int,match.groups());assert l<r and t<b,'empty menu bounds'\n"
  '        return l,t,r,b\n'
  '    l,t,r,b=rectangle(scroll)\n'
  "    targets=[n for n in scroll.iter('node') if n.get('text')=='环境详情']\n"
  "    assert len(targets)<=1,'ambiguous environment details action'\n"
  '    if targets:\n'
  '        target=targets[0]\n'
  "        assert target.get('package')==PACKAGE and target.get('class')=='android.widget.Button'\n"
  "        assert target.get('enabled')==target.get('clickable')=='true','inactive environment details "
  "action'\n"
  '        al,at,ar,ab=rectangle(target)\n'
  "        if l<=al<ar<=r and t<=at<ab<=b and ab-at>=144 and target.get('visible-to-user')!='false':\n"
  '            return dict(ready=True,bounds=[al,at,ar,ab])\n'
  "    assert scroll.get('scrollable')=='true','environment details cannot be reached'\n"
  '    return dict(ready=False,bounds=[l,t,r,b])\n'
  '\n'
  'def run(',
  1),
 ('    def wait(predicate,label,timeout=35):\n'
  '        deadline=time.monotonic()+timeout\n'
  '        while True:\n'
  '            xml=dump(deadline=deadline)\n'
  "            crash=adb('logcat','-d','-s','AndroidRuntime:E','*:S')\n"
  "            assert 'FATAL EXCEPTION' not in crash,(label,crash[-4000:])\n"
  '            if predicate(xml):return xml\n'
  "            if time.monotonic()>=deadline:raise AssertionError((label,'not observed',xml[-5000:]))\n"
  '            time.sleep(.2)\n',
  '    def wait(predicate,label,timeout=35):\n'
  '        deadline=time.monotonic()+timeout\n'
  '        while True:\n'
  '            xml=dump(deadline=deadline)\n'
  "            crash=adb('logcat','-d','-s','AndroidRuntime:E','*:S')\n"
  "            assert 'FATAL EXCEPTION' not in crash,(label,crash[-4000:])\n"
  "            if time.monotonic()>=deadline:raise AssertionError((label,'wait budget "
  "expired',xml[-5000:]))\n"
  '            accepted=predicate(xml)\n'
  "            if time.monotonic()>=deadline:raise AssertionError((label,'wait budget "
  "expired',xml[-5000:]))\n"
  '            if accepted:return xml\n'
  '            time.sleep(.2)\n',
  1))

def historical_dashboard_source(value):
    if type(value) is not bytes:
        raise ValueError('Complete dashboard source bytes required')
    if (len(value),hashlib.sha256(value).hexdigest())!=AFTER:
        raise ValueError('Current direct-browser dashboard source differs')
    for old,new,count in reversed(HUNKS):
        old,new=old.encode(),new.encode()
        if value.count(new)!=count:
            raise ValueError('Browser interaction port is missing or duplicated')
        value=value.replace(new,old)
    if (len(value),hashlib.sha256(value).hexdigest())!=BEFORE:
        raise ValueError('Original complete dashboard flow changed')
    return value
