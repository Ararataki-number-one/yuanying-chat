"""Explicit current native navigation contract, separate from retained v1 oracles.

All evidence comes from the installed test APK and actual ADB observations.
The four native labels are the centered three-item group plus its reading
button. This module never constructs Android evidence or changes app state
to make a layout pass.
"""
import hashlib
import json
import math
from pathlib import Path
import re
import struct
import time
import uuid
import xml.etree.ElementTree as ET

PACKAGE = 'local.pocketchat.test'
LABELS = ('环境', '网络', '下载', '阅读')


def protocol_for_variant(variant):
    if variant == 'before':
        return 1
    if variant == 'current':
        return 2
    raise ValueError('The native navigation protocol requires an explicit APK role')


def _native(xml):
    root = ET.fromstring(xml)
    if root.tag != 'hierarchy':
        raise ValueError('An actual native hierarchy is required')
    return [n for n in root.iter('node') if n.get('package') == PACKAGE
            and n.get('visible-to-user') != 'false']


def _bounds(node, width, height):
    found = re.fullmatch(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', node.get('bounds', ''))
    if found is None:
        raise ValueError('Complete native bounds are required')
    box = list(map(int, found.groups()))
    if not (0 <= box[0] < box[2] <= width and 0 <= box[1] < box[3] <= height):
        raise ValueError('The native control is clipped outside the actual display')
    return box


def validate_navigation(xml, width, height, density):
    if any(type(v) is not int or v <= 0 for v in (width, height, density)):
        raise ValueError('Explicit actual display geometry is required')
    nodes = _native(xml)
    boxes = {}
    for label in LABELS:
        found = [n for n in nodes if n.get('class') == 'android.widget.Button'
                 and n.get('text') == label and n.get('enabled') == 'true'
                 and n.get('clickable') == 'true']
        if len(found) != 1:
            raise ValueError('The complete current native navigation label is missing or ambiguous: ' + label)
        boxes[label] = _bounds(found[0], width, height)
    three = [boxes[label] for label in LABELS[:3]]
    group = [min(b[0] for b in three), min(b[1] for b in three),
             max(b[2] for b in three), max(b[3] for b in three)]
    reading = boxes['阅读']
    minimum = (48 * density + 159) // 160
    offset = (group[0] + group[2] - width) / 2
    same_row = group[2] < reading[0] and max(group[1], reading[1]) < min(group[3], reading[3])
    stacked = reading[1] > group[3] and reading[0] >= width / 2 and reading[2] > group[2]
    retired = []
    for node in nodes:
        if node.get('class') == 'android.widget.Button' and node.get('text') in ('会话', '设置'):
            try:
                box = _bounds(node, width, height)
            except ValueError:
                continue
            if max(box[1], group[1]) < min(box[3], group[3]):
                retired.append(node.get('text'))
    checks = dict(threeItemGroupCentered=abs(offset) <= 1,
        threeLabelsShareRow=all(abs(b[1] - three[0][1]) <= 1 and abs(b[3] - three[0][3]) <= 1 for b in three),
        threeLabelsOrdered=all(three[i][2] <= three[i + 1][0] for i in range(2)),
        independentReadingButton=same_row or stacked,
        readingSquare=abs(reading[2] - reading[0] - reading[3] + reading[1]) <= 3,
        minimum48DpTargets=all(b[2] - b[0] >= minimum and b[3] - b[1] >= minimum for b in boxes.values()),
        retiredFooterTabsAbsent=not retired)
    if not all(checks.values()):
        raise ValueError('The current native navigation geometry failed: ' + repr(checks))
    return dict(protocolVersion=2, labels=list(LABELS), bounds=boxes, groupBounds=group,
                centerOffsetPx=offset, allowedCenterOffsetPx=1, minimumTouchTargetDp=48,
                minimumTouchTargetPx=minimum, readingLayout='same-row' if same_row else 'stacked-right',
                checks=checks, valid=True)


def validate_chat(xml, width, height, density):
    navigation = validate_navigation(xml, width, height, density)
    nodes = _native(xml)
    capsules = [n for n in nodes if re.fullmatch(r'当前环境：.+，点按输入网址，长按切换环境', n.get('content-desc', ''))]
    networks = [n for n in nodes if n.get('content-desc', '').startswith('当前环境网络：')]
    if len(capsules) != 1 or len(networks) != 1:
        raise ValueError('The actual current environment and network header must be unique')
    capsule, network = capsules[0], networks[0]
    if capsule.get('clickable') != 'true' or capsule.get('enabled') != 'true' or network.get('clickable') != 'false':
        raise ValueError('The current URL/environment capsule and passive network row differ')
    top, status = _bounds(capsule, width, height), _bounds(network, width, height)
    if abs((top[0] + top[2] - width) / 2) > 1 or top[3] != status[1]:
        raise ValueError('The current short environment capsule is not centered above its status row')
    if any(n.get('text') in ('简洁', '原网页') for n in nodes):
        raise ValueError('Retired web-mode controls must remain absent')
    return dict(navigation=navigation, environmentDescription=capsule.get('content-desc'),
                capsuleBounds=top, networkBounds=status, source='actual-native-XML')


def chat_ready(xml, width, height, density):
    try:
        validate_chat(xml, width, height, density)
        return True
    except ValueError:
        return False


def environment_open_button(xml, name, width, height, density):
    found = [n for n in _native(xml) if n.get('class') == 'android.widget.Button'
             and n.get('content-desc') == '打开环境 ' + name
             and n.get('enabled') == 'true' and n.get('clickable') == 'true']
    if len(found) > 1:
        raise ValueError('The actual named environment entry is ambiguous')
    if not found:
        return None
    try:
        box = _bounds(found[0], width, height)
    except ValueError:
        return None
    minimum = (48 * density + 159) // 160
    return found[0] if box[2] - box[0] >= minimum and box[3] - box[1] >= minimum else None


def reveal_environment_entry(adb, dump, name, width, height, density, *, seconds=35):
    """Expose the retained real list button, rather than substituting a card tap."""
    deadline, swipes = time.monotonic() + seconds, 0
    while time.monotonic() < deadline:
        xml = dump(deadline=deadline)
        if environment_open_button(xml, name, width, height, density) is not None:
            return xml
        scrolls = [n for n in _native(xml) if n.get('class') == 'android.widget.ScrollView'
                   and n.get('scrollable') == 'true']
        if scrolls and swipes < 5:
            left, top, right, bottom = _bounds(scrolls[-1], width, height)
            x = (left + right) // 2
            adb('shell', 'input', 'swipe', str(x), str(top + (bottom - top) * 4 // 5),
                str(x), str(top + (bottom - top) // 5), '300')
            swipes += 1
        else:
            time.sleep(min(.2, max(0, deadline - time.monotonic())))
    raise TimeoutError('The complete real environment entry did not become visible: ' + name)


def validate_native_font_records(raw, nonce, identity, font_scale, density):
    if (type(nonce) is not str or re.fullmatch('[0-9a-f]{32}', nonce) is None
            or type(font_scale) not in (int, float) or not math.isfinite(font_scale) or font_scale <= 0
            or type(density) is not int or density <= 0):
        raise ValueError('Explicit source-bound native glyph observation inputs are required')
    rows = [json.loads(line[line.index('{'):]) for line in raw.splitlines() if '{' in line]
    rows = [r for r in rows if r.get('nonce') == nonce]
    summaries = [r for r in rows if r.get('kind') == 'summary']
    labels = [r for r in rows if r.get('kind') == 'label']
    if any(type(r.get('selectedIndex')) is not int or type(r.get('measurement', {}).get('buttonIndex')) is not int for r in labels):
        raise ValueError('Native navigation selection/label indices must be exact integers')
    keys = [(r.get('selectedIndex'), r.get('measurement', {}).get('buttonIndex')) for r in labels]
    if (len(summaries) != 1 or summaries[0].get('status') != 'verified'
            or summaries[0].get('observationCount') != 20 or len(labels) != 20
            or len(set(keys)) != 20 or set(keys) != {(s, i) for s in range(-1, 4) for i in range(4)}):
        raise ValueError('All twenty current native navigation glyph observations are required')
    checks = ('layoutFits', 'glyphFits', 'wholeLabel', 'widthFits', 'viewVisible',
              'horizontalLineFits', 'horizontalGlyphFits', 'verticalUnscrolled', 'selectionMatches')
    for row in rows:
        if (type(row.get('schema')) is not int or row['schema'] != 1 or row.get('actualAndroidLayout') is not True
                or any(row.get(k) != identity[k] for k in ('sourceCommit', 'sourceTree', 'apkSha256'))
                or type(row.get('fontScale')) not in (int, float) or not math.isfinite(row['fontScale'])
                or abs(row['fontScale'] - font_scale) > .001 or row.get('density') != density / 160):
            raise ValueError('The current native glyph source/APK/font/density identity differs')
    for row in labels:
        m = row['measurement']
        if (m.get('label') != LABELS[m['buttonIndex']] or m.get('valid') is not True
                or any(m.get('checks', {}).get(k) is not True for k in checks)
                or m.get('width', 0) < 48 * density / 160 or m.get('height', 0) < 48 * density / 160
                or m.get('selected') != (row['selectedIndex'] == m['buttonIndex'])):
            raise ValueError('A full native Chinese navigation label or touch region failed')
    return dict(protocolVersion=2, nonce=nonce, observationCount=20, records=rows,
                scope='Actual shared native navigation font/layout component; not a webpage screenshot')


def capture_native_fonts(adb_scene, *, identity, font_scale, density, out, stem):
    nonce, deadline = uuid.uuid4().hex, time.monotonic() + 25
    adb_scene(deadline, 'shell', 'am', 'start', '-W', '-n', PACKAGE + '/local.pocketchat.UiVisualIntegrationActivity',
        '--activity-clear-top', '--es', 'visualAction', 'navigation-typography', '--es', 'visualNonce', nonce,
        '--es', 'visualSourceCommit', identity['sourceCommit'], '--ef', 'visualFontScale', str(font_scale))
    path = Path(out) / (stem + '-navigation-fonts.log')
    while time.monotonic() < deadline:
        raw = adb_scene(deadline, 'logcat', '-d', '-v', 'raw', '-s', 'PocketNavType:I', '*:S')
        path.write_text(raw)
        rows = [json.loads(line) for line in raw.splitlines() if line.startswith('{')]
        if any(r.get('nonce') == nonce and r.get('kind') == 'summary' for r in rows):
            result = validate_native_font_records(raw, nonce, identity, font_scale, density)
            result.update(file=path.name, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            return result
        time.sleep(min(.2, max(0, deadline - time.monotonic())))
    raise TimeoutError('The current native navigation font observation did not complete')


def run_dashboard_v2(adb,binary,source,out,dump):
    records=[];events=[];taps=[];directory=out/'ui-visuals/environment-dashboard';directory.mkdir(parents=True,exist_ok=True)
    def tree(xml):return list(ET.fromstring(xml).iter('node'))
    def dashboard(xml):return any(n.get('content-desc')=='环境仪表盘' for n in tree(xml))
    def wait(predicate,label,timeout=35,*,deadline=None):
        deadline=time.monotonic()+timeout if deadline is None else deadline
        while True:
            xml=dump(deadline=deadline)
            crash=adb('logcat','-d','-s','AndroidRuntime:E','*:S')
            assert 'FATAL EXCEPTION' not in crash,(label,crash[-4000:])
            if predicate(xml):return xml
            if time.monotonic()>=deadline:raise AssertionError((label,'not observed',xml[-5000:]))
            time.sleep(.2)
    def click(xml,label=None,description=None):
        root=ET.fromstring(xml);parents={child:parent for parent in root.iter() for child in parent}
        found=[n for n in root.iter('node') if n.get('package')==PACKAGE and n.get('visible-to-user')!='false'
               and (label is not None and n.get('text')==label or description is not None and n.get('content-desc')==description)
               and n.get('enabled')=='true']
        assert len(found)==1,(label,description,'missing or ambiguous native target')
        node=found[0]
        while node.get('clickable')!='true' and node in parents:node=parents[node]
        assert node.get('clickable')=='true' and node.get('enabled')=='true',(label,node.attrib)
        l,t,r,b=_bounds(node,width*3,height*3);assert r-l>=144 and b-t>=144,(label,'native touch target below48dp',node.attrib)
        adb('shell','input','tap',str((l+r)//2),str((t+b)//2))
        taps.append(dict(label=label,description=description,x=(l+r)//2,y=(t+b)//2,bounds=[l,t,r,b]))
    def snapshot(name,xml,*,dashboard_required=True,**metadata):
        for text in ('跳过','停留查看'):
            assert not any(n.get('text')==text for n in tree(xml)),('retired action still visible',text)
        assert not any(re.search(r'\d+\s*秒后进入',n.get('text','')) for n in tree(xml)),('countdown still visible',name)
        if dashboard_required:assert dashboard(xml),('dashboard absent',name)
        else:validate_chat(xml,width*3,height*3,480)
        raw=binary('exec-out','screencap','-p');assert raw.startswith(b'\x89PNG\r\n\x1a\n')
        pixels=struct.unpack('>II',raw[16:24]);assert pixels==(width*3,height*3),(name,'actual screenshot viewport differs',pixels,[width*3,height*3])
        (directory/(name+'.xml')).write_text(xml);(directory/(name+'.png')).write_bytes(raw)
        # Flat original-byte companions are included by the existing phase transport.
        (out/'ui-visuals'/('environment-dashboard-v2-'+name+'.xml')).write_text(xml)
        (out/'ui-visuals'/('environment-dashboard-v2-'+name+'.png')).write_bytes(raw)
        records.append(dict(name=name,image='ui-visuals/environment-dashboard-v2-'+name+'.png',xml='ui-visuals/environment-dashboard-v2-'+name+'.xml',imageSha256=hashlib.sha256(raw).hexdigest(),actualPixelSize=list(pixels),navigationVersion=2,**metadata))
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
            xml=wait(dashboard,name+' actual launcher dashboard')
            node=next(n for n in tree(xml) if n.get('text')=='进入聊天' and n.get('enabled')=='true')
            l,t,r,b=map(int,re.findall(r'\d+',node.get('bounds')))
            assert 0<=l<r<=width*3 and 0<=t<b<=height*3 and b-t>=48*3,(name,'entry action clipped',node.attrib)
            snapshot(name,xml,entry='production-brand-launcher',viewport=[width,height],fontScale=scale,theme='dark' if night else 'light',observedAdbDisplay=observed,observationDelaySeconds=round(time.monotonic()-started,3))
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
            click(xml,'进入聊天');wait(lambda x:not dashboard(x) and chat_ready(x,width*3,height*3,480),'explicit chat entry')
            adb('shell','input','keyevent','KEYCODE_HOME')
            adb('shell','am','start','-W','-n',PACKAGE+'/local.pocketchat.MainActivity','--activity-reorder-to-front')
            wait(lambda x:not dashboard(x) and chat_ready(x,width*3,height*3,480),'ordinary resume has no dashboard')
            events.append(dict(name='home-retains-open-dashboard-and-chat-resume-does-not-reinsert',passed=True))
            # Real list button, same existing environment/Activity instance.
            entry_taps=len(taps)
            adb('shell','am','start','-W','-n',PACKAGE+'/local.pocketchat.WindowHomeActivity')
            xml=reveal_environment_entry(adb,dump,'日常会话',width*3,height*3,480)
            click(xml,description='打开环境 日常会话');xml=wait(dashboard,'warm list opens dashboard');snapshot('warm-list',xml)
            click(xml,'进入聊天');wait(lambda x:not dashboard(x),'warm explicit entry')
            # Match the reported second-environment case in its actual separate
            # Android profile process, using the real list's native button.
            adb('shell','am','start','-W','-n',PACKAGE+'/local.pocketchat.WindowHomeActivity')
            xml=reveal_environment_entry(adb,dump,'日常会话',width*3,height*3,480)
            xml=reveal_environment_entry(adb,dump,'资料整理',width*3,height*3,480)
            click(xml,description='打开环境 资料整理');xml=wait(lambda x:dashboard(x) and '资料整理' in x,'separate process second environment');snapshot('second-environment',xml,profileProcess='profile1',slot=1)
            click(xml,'进入聊天');wait(lambda x:not dashboard(x),'second environment explicit entry')
            # Settings workspace -> real bottom chat tab exercises the other
            # previously unmarked native navigation route.
            adb('shell','am','start','-W','-n',PACKAGE+'/local.pocketchat.WindowHomeActivity')
            command_deadline=time.monotonic()+35
            xml=wait(lambda x:'环境管理' in x and '搜索操作' in x,'manager command entry',deadline=command_deadline)
            click(xml,description='搜索操作')
            xml=wait(lambda x:'搜索应用操作' in x,'actual native command search',deadline=command_deadline)
            # The real palette focuses its EditText and exposes the command's
            # existing ASCII alias. Enter executes its one observed result;
            # no stale geometry is used while its IME changes the window.
            adb('shell','input','text','setting')
            xml=wait(lambda x:any(n.get('class')=='android.widget.EditText' and n.get('text')=='setting' for n in tree(x))
                     and '1 项操作' in x and '应用设置' in x,'unique actual settings command',deadline=command_deadline)
            adb('shell','input','keyevent','66')
            xml=wait(lambda x:'启动与界面' in x and '阅读' in x,'settings workspace',deadline=command_deadline)
            validate_navigation(xml,width*3,height*3,480)
            click(xml,'阅读')
            xml=wait(lambda x:not dashboard(x) and chat_ready(x,width*3,height*3,480),
                     'current reading entry returns to MainActivity')
            # The unconfigured page keeps its tools, per the production focus policy.
            # Actual focus-reading of a usable document remains separately mandatory.
            snapshot('workspace-chat',xml,dashboard_required=False,
                     entry='settings-native-book-button',documentScope='existing-unconfigured-production-page')
            events.append(dict(name='warm-list-second-process-and-settings-chat-entry',actualAndroidTaps=len(taps)-entry_taps,passed=True))
        result=dict(schema=1,status='passed',sourceCommit=source,actualAndroidExecution=True,navigationVersion=2,actualNativeDashboardRendering=True,physicalPhoneAcceptance=False,actualPublicSiteExecution=False,scope=__doc__.strip(),captures=records,events=events,actualAndroidTaps=taps)
        (out/'environment-dashboard-results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        (directory/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        return result
    except Exception as error:
        xml=dump();raw=binary('exec-out','screencap','-p')
        (directory/'failure.xml').write_text(xml);(directory/'failure.png').write_bytes(raw)
        (out/'ui-visuals/environment-dashboard-v2-failure.xml').write_text(xml)
        (out/'ui-visuals/environment-dashboard-v2-failure.png').write_bytes(raw)
        failure=dict(status='failed',sourceCommit=source,navigationVersion=2,error=repr(error),captures=records,events=events,actualAndroidTaps=taps,physicalPhoneAcceptance=False,
                     failureImage='ui-visuals/environment-dashboard-v2-failure.png',failureXml='ui-visuals/environment-dashboard-v2-failure.xml')
        (out/'environment-dashboard-results.json').write_text(json.dumps(failure,ensure_ascii=False,indent=2)+'\n');(directory/'results.json').write_text(json.dumps(failure,ensure_ascii=False,indent=2)+'\n');raise
    finally:
        adb('shell','cmd','uimode','night','no');adb('shell','settings','put','system','font_scale','1')
