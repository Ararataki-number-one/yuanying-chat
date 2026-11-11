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
AFTER = (16002, 'a5bb9ed6386277f29a977c5545bd54071c904891bf23ffc69328bcba3f3e334a')
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
  "        xml=wait(lambda x:any(n.get('text')=='环境详情' for n in tree(x)),'explicit details menu')\n"
  "        click(xml,'环境详情')\n"
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
