"""Version 3: retained environment capsule and actual bottom browser menu.

Every menu destination has its own native XML, actual tap and owned device
snapshot. The historical v2 reader is unchanged. Shared helpers retain the same
single-input and original-budget readiness/document protections.
"""
import hashlib
import re
import xml.etree.ElementTree as ET

if __package__:
    from .integration_event_contract import EventTransfer, event_uri
    from .workspace_navigation_contract_v3 import navigation, bounds, menu_action, verify_menu_scrolls
    from .compact_chrome_layout_v2 import address_dialog, inside, rect
    from .chrome_collapse_contract_v2 import (PACKAGE, ACTIVITY, ENVIRONMENT_ACTIVITY, TARGET,
        STABLE, LEGACY_BEHAVIOR_MAP, BROWSER_STARTUP_MAP, center, resumed, gesture,
        address_cancel, make_short_target_proof, verify_short_target, modal as legacy_modal)
else:
    from integration_event_contract import EventTransfer, event_uri
    from workspace_navigation_contract_v3 import navigation, bounds, menu_action, verify_menu_scrolls
    from compact_chrome_layout_v2 import address_dialog, inside, rect
    from chrome_collapse_contract_v2 import (PACKAGE, ACTIVITY, ENVIRONMENT_ACTIVITY, TARGET,
        STABLE, LEGACY_BEHAVIOR_MAP, BROWSER_STARTUP_MAP, center, resumed, gesture,
        address_cancel, make_short_target_proof, verify_short_target, modal as legacy_modal)

PHASES = (
    'ready','initialAddress','initialChat','up','down','compactAddress','compactExpand',
    'horizontal','short','upBeforeChat','selectedAddress','selectedChat','upBeforeNative',
    'networkMenu','network','nativeReturn','upBeforeResume','activityResume','resumeAddress',
    'resumeChat','headerUp','extrasAddress','extrasExpanded','environmentMenu','environmentReturn',
    'downloadsMenu','downloads','downloadsReturn','readingMenu','reading','readingExit',
    'readingBackMenu','readingBackMode','readingBack','environmentPicker','pickerReturn',
    'more','moreReturn','drawerMenu','drawerReturn',
)
ADDRESS_PHASES = ('initialAddress','compactAddress','selectedAddress','resumeAddress','extrasAddress')
NORMAL_UI_PHASES = ('initialChat','compactExpand','selectedChat','nativeReturn','resumeChat',
    'extrasExpanded','environmentReturn','downloadsReturn','readingExit','readingBack','pickerReturn','moreReturn','drawerReturn')
MENU_TARGETS = {'networkMenu':'当前环境网络','environmentMenu':'管理全部环境',
    'downloadsMenu':'下载管理','readingMenu':'进入专注阅读','readingBackMenu':'进入专注阅读','drawerMenu':'管理全部环境'}
MENU_PHASES = ('networkMenu','environmentMenu','downloadsMenu','readingMenu','readingBackMenu','more','drawerMenu')
UI_PHASES = set(ADDRESS_PHASES + NORMAL_UI_PHASES + MENU_PHASES +
    ('network','environment','downloads','reading','readingBackMode','environmentPicker','drawer'))
BROWSER_NAMES = (
    'Actual Gecko document starts with visible environment capsule and bottom browser controls',
    'Tapping the environment capsule opens the address dialog without navigation',
    'Trusted upward reading swipe compacts chrome only after the gesture',
    'Downward reading preserves the compact environment bar',
    'Compact environment remains tappable after a webpage swipe',
    'Horizontal scrolling does not collapse environment controls',
    'Short gestures do not collapse environment controls',
    'Explicit current-environment address tap reveals controls on the same conversation',
    'Returning from native network reveals chrome without reloading chat',
    'Activity resume preserves the collapsed controls and live SDK page',
    'Explicit current-environment address tap reveals controls after resume',
    'Upward swipe on native environment controls collapses only after release',
    'Native header swipe starts inside an actual expanded button touch region',
    'All chrome interactions use one controlled actual document without navigation or send',
    'Every address dialog is production-owned and cancelled by one actual native button tap',
    'Browser menu opens the actual environment Activity and Back preserves the SDK document',
    'Browser menu opens native downloads and Back restores bottom browser controls',
    'Reading hides native chrome and its actual exit button restores the same document',
    'Back exits reading without leaving the conversation or navigating the document',
    'Long-pressing the environment capsule opens and closes the actual environment picker',
    'Bottom menu opens the native browser menu and Back dismisses it without an action',
    'Repeated environment management from the browser menu preserves the SDK document',
)
NAMES = BROWSER_NAMES
INPUTS = (
    ('initialAddress','tap','ready','addressTap'),('initialChat','tap','initialAddress','cancel'),
    ('up','swipe','initialChat','up'),('down','swipe','up','down'),
    ('compactAddress','tap','down','compactTap'),('compactExpand','tap','compactAddress','cancel'),
    ('horizontal','swipe','compactExpand','horizontal'),('short','swipe','horizontal','short'),
    ('upBeforeChat','swipe','short','up'),('selectedAddress','tap','upBeforeChat','compactTap'),
    ('selectedChat','tap','selectedAddress','cancel'),('upBeforeNative','swipe','selectedChat','up'),
    ('networkMenu','tap','upBeforeNative','moreTap'),('network','tap','networkMenu','menu:当前环境网络'),
    ('nativeReturn','back','network',''),('upBeforeResume','swipe','nativeReturn','up'),
    ('activityResume','homeRoundtrip','upBeforeResume',''),('resumeAddress','tap','activityResume','compactTap'),
    ('resumeChat','tap','resumeAddress','cancel'),('headerUp','swipe','resumeChat','header'),
    ('extrasAddress','tap','headerUp','compactTap'),('extrasExpanded','tap','extrasAddress','cancel'),
    ('environmentMenu','tap','extrasExpanded','moreTap'),('environment','tap','environmentMenu','menu:管理全部环境'),
    ('environmentReturn','back','environment',''),('downloadsMenu','tap','environmentReturn','moreTap'),
    ('downloads','tap','downloadsMenu','menu:下载管理'),('downloadsReturn','back','downloads',''),
    ('readingMenu','tap','downloadsReturn','moreTap'),('reading','tap','readingMenu','menu:进入专注阅读'),
    ('readingExit','tap','reading','readingExitTap'),('readingBackMenu','tap','readingExit','moreTap'),
    ('readingBackMode','tap','readingBackMenu','menu:进入专注阅读'),('readingBack','back','readingBackMode',''),
    ('environmentPicker','longPress','readingBack','addressTap'),('pickerReturn','tap','environmentPicker','closePicker'),
    ('more','tap','pickerReturn','moreTap'),('moreReturn','back','more',''),
    ('drawerMenu','tap','moreReturn','moreTap'),('drawer','tap','drawerMenu','menu:管理全部环境'),
    ('drawerReturn','back','drawer',''),
)


def browser_menu_modal(raw):
    """Observe the current menu before Back dismisses it without an action."""
    tree=ET.fromstring(raw); nodes=list(tree.iter('node'))
    parents={child:parent for parent in tree.iter() for child in parent}
    def one(widget,field,value):
        matches=[n for n in nodes if n.get('package')==PACKAGE
                 and n.get('class')=='android.widget.'+widget and n.get(field)==value]
        assert len(matches)==1, ('Missing or ambiguous current browser menu control',value)
        node=matches[0]
        assert node.get('visible-to-user')!='false' and node.get('enabled')=='true'
        bounds(node)
        return node
    heading=one('TextView','text','浏览器菜单')
    assert heading.get('content-desc')=='浏览器菜单'
    close=one('Button','content-desc','关闭浏览器菜单')
    action=one('Button','text','下载管理')
    scroll=one('ScrollView','scrollable','true')
    header=parents[heading]; panel=parents[header]
    assert parents[close] is header and parents[scroll] is panel
    assert all(n.get('package')==PACKAGE and n.get('class')=='android.widget.LinearLayout'
               and n.get('visible-to-user')!='false' for n in (header,panel))
    ancestor=action
    while ancestor in parents and ancestor is not scroll:ancestor=parents[ancestor]
    assert ancestor is scroll, 'Current browser action must belong to the actual menu scroller'
    for node in (close,action):
        box=bounds(node)
        assert node.get('clickable')=='true' and min(box[2]-box[0],box[3]-box[1])>=144
    left,top,right,bottom=bounds(scroll); al,at,ar,ab=bounds(action)
    assert left<=al<ar<=right and top<=at<ab<=bottom
    assert bounds(heading)[3]<=top and bounds(close)[3]<=top
    pl,pt,pr,pb=bounds(panel)
    for node in (header,scroll):
        l,t,r,b=bounds(node)
        assert pl<=l<r<=pr and pt<=t<b<=pb
    return dict(title='浏览器菜单',closeBounds=bounds(close),closePoint=center(bounds(close)))


def inspect_ui(raw, phase, environment, *, browser=False):
    assert browser is True
    if phase in ADDRESS_PHASES:
        result=address_dialog(raw,PACKAGE)
        fields=[n for n in ET.fromstring(raw).iter('node') if n.get('package')==PACKAGE and n.get('class')=='android.widget.EditText']
        assert len(fields)==1 and fields[0].get('content-desc')=='网址或搜索'
        assert fields[0].get('text')==TARGET and fields[0].get('focused')=='true'
        return result
    if phase == 'environmentPicker': return legacy_modal(raw,phase,environment,browser=True)
    if phase in MENU_PHASES:
        title=[n for n in ET.fromstring(raw).iter('node') if n.get('package')==PACKAGE
               and n.get('class')=='android.widget.TextView' and n.get('text')==n.get('content-desc')=='浏览器菜单']
        assert len(title)==1
        if phase in MENU_TARGETS: return menu_action(raw,PACKAGE,MENU_TARGETS[phase])
        assert phase=='more'
        return browser_menu_modal(raw)
    if phase in ('reading','readingBackMode'):
        nodes=list(ET.fromstring(raw).iter('node'))
        exits=[n for n in nodes if n.get('package')==PACKAGE and n.get('class')=='android.widget.Button'
               and n.get('text')=='退出阅读' and n.get('content-desc')=='退出专注阅读，恢复应用工具栏和导航']
        assert len(exits)==1 and exits[0].get('enabled')==exits[0].get('clickable')=='true'
        assert not any(n.get('package')==PACKAGE and (n.get('content-desc') in ('浏览器菜单','后退','打开当前环境主页')
                       or n.get('content-desc','').startswith(('当前环境：','当前网址 '))) for n in nodes)
        return dict(exitBounds=bounds(exits[0]),exitPoint=center(bounds(exits[0])))
    if phase in ('environment','drawer','network','downloads'):
        return navigation(raw,PACKAGE,conversation=False,
            selected={'environment':'环境','drawer':'环境','network':'网络','downloads':'下载'}[phase],browser=True)
    assert phase in NORMAL_UI_PHASES
    result=navigation(raw,PACKAGE,conversation=True,browser=True)
    assert not any(n.get('package')==PACKAGE and n.get('text') in ('打开网址','快速切换环境','浏览器菜单')
                   and n.get('class')=='android.widget.TextView' for n in ET.fromstring(raw).iter('node'))
    return result


def verify_cold_start(cold, *, browser=False):
    """Read real startup geometry; old reports keep the collapsed default."""
    assert browser is True
    assert cold['toolbarVisibility'] == cold['networkVisibility'] == 0
    assert cold['networkInHeader'] is cold['networkShown'] is False
    assert cold['browserToolbarShown'] is True
    inside(cold['browserAddressTap'],cold['browserToolbarBounds'])
    assert cold['compactName'] == cold['environmentName']
    if browser:
        assert cold['expanded'] is True and cold['compactVisibility'] == 8 and cold['topVisibility'] == 0
        assert cold['compactTap'] is None
        point = cold['addressTap']
        assert type(point) is list and len(point) == 2 and all(type(n) is int and n >= 0 for n in point)
        inside(point, cold['headerButtonTouch'])
    else:
        assert cold['expanded'] is False and cold['compactVisibility'] == 0 and cold['topVisibility'] == 8
        assert cold['compactHeight'] > 0


def verify_case(case, identity):
    source = identity['sourceCommit']
    browser = case.get('browserChrome', False)
    assert browser is True
    names = BROWSER_NAMES if browser else NAMES
    assert type(case.get('navigationContract')) is int and case['navigationContract'] == 3
    assert case['sourceCommit'] == source and re.fullmatch('[0-9a-f]{32}', case['runNonce'])
    assert all(case[k] is True for k in ('actualAndroidExecution', 'actualGeckoExecution', 'actualAndroidTouchExecution'))
    assert [c['name'] for c in case['checks']] == list(names) and all(c['pass'] is True for c in case['checks'])
    assert case['legacyBehaviorMap'] == [list(row) for row in (LEGACY_BEHAVIOR_MAP[2:] if browser else LEGACY_BEHAVIOR_MAP)]
    if browser:
        assert case['browserStartupMap'] == [list(row) for row in BROWSER_STARTUP_MAP]
    owned = case['eventTransfer']
    assert owned['runNonce'] == case['runNonce'] and owned['fixtureAction'] == 'chromeCollapse' and type(owned['processSlot']) is int and owned['processSlot'] == 0
    rows = owned['events']; payloads = {event_uri(row['receipt']): row['rawUtf8'].encode('utf-8') for row in rows}
    assert len(rows) == len(payloads) == len(PHASES)
    transfer = EventTransfer(identity=identity, nonce=case['runNonce'], slot=0, action='chromeCollapse', fetch=lambda uri: payloads[uri])
    samples = {}
    for expected, row in zip(PHASES, rows):
        event = transfer.read(row['receipt']); assert event['kind'] == 'collapseSnapshot'
        sample = event['result']; assert sample['command'] == expected and expected not in samples
        assert type(sample.get('navigationContract')) is int and sample['navigationContract'] == 3
        samples[expected] = sample
    assert samples == case['observations'] and list(samples) == list(PHASES)
    cold, initial = samples['ready'], samples['initialChat']
    verify_cold_start(cold, browser=browser)
    compact = samples['up'] if browser else cold
    assert compact['webHeight'] == initial['webHeight'] + initial['toolbarHeight'] - compact['toolbarHeight']
    assert initial['toolbarHeight'] > compact['toolbarHeight'] and initial['webHeight'] > 0
    if browser:
        assert all(cold[key] == initial[key] for key in ('webHeight', 'toolbarHeight', 'addressTap'))
    assert initial['loads'] == initial['stops'] == initial['sendCount'] == 0 and initial['documents'] == 1
    assert initial['sdkSession'] == initial['attachedSession'] and all(type(initial[k]) is int and initial[k] > 0 for k in ('sdkSession', 'surface'))
    assert re.fullmatch('[0-9a-f]{32}', initial['document']) and initial['path'] == '/c/reload-collapse'
    assert initial['draft'] == 'unsent controlled browser draft' and 'session=synthetic-reload' in initial['cookie']
    assert initial['pending']['confirmed'] is True
    ready = initial['documentReadyEvidence']; actual = 'http://127.0.0.1:8765/c/reload-collapse'
    assert ready['rawMessage']['kind'] == 'documentReady' and ready['rawMessage']['url'] == actual
    assert ready['senderUrl'] == ready['actualUrl'] == actual and ready['visibleUrl'] == TARGET
    assert ready['normalizedMessage'] == dict(ready['rawMessage'], url=TARGET)
    assert ready['topLevel'] is ready['contentScript'] is ready['acceptedByProduction'] is True
    assert ready['nativeSession'] == ready['currentSession'] == initial['sdkSession']
    for phase, sample in samples.items():
        assert all(sample[k] == initial[k] for k in STABLE), phase
        assert sample['documentReadyEvidence'] == ready and sample['networkVisibility'] == 0
        assert sample['networkInHeader'] is False and sample['networkShown'] is (phase in MENU_PHASES)
        assert sample['visibleDocument'] is True and sample['loadingCoverVisibility'] == 8
        assert sample['navigationLayout'] == ('workspace-five' if phase in ('network', 'downloads') else 'browser-bottom')
        index = PHASES.index(phase)
        assert sample['activityStarts'] == (2 if phase == 'drawerReturn' else 1 if index >= PHASES.index('environmentReturn') else 0)
        assert sample['menuOpens'] == sum(index >= PHASES.index(name) for name in MENU_PHASES)
        assert sample['readingActive'] is (phase in ('reading', 'readingBackMode'))
        assert sample['readingRequested'] is sample['readingActive']
        if phase not in ADDRESS_PHASES:
            assert sample['browserToolbarShown'] is (phase not in ('network','downloads','reading','readingBackMode'))
        assert sample['page'] == {'network': 4, 'downloads': 1}.get(phase, 0)
        telemetry = sample['fixtureInputTelemetry']
        assert sample['telemetryReady'] is True and type(telemetry['schema']) is int and telemetry['schema'] == 1 and telemetry['realm'] == 'page-main-world'
        assert telemetry['document'] == sample['document'] and 'touchend' in telemetry['listenerTypes']
        assert telemetry['events'] == sample['trusted'] and len(telemetry['events']) <= 256
        assert telemetry['count'] == len(telemetry['events']) + telemetry['dropped']
        assert all(type(row['trusted']) is bool and row['type'] in telemetry['listenerTypes'] for row in telemetry['events'])
        dialog = sample['addressDialog']
        assert type(dialog['schema']) is int and dialog['schema'] == 1 and dialog['ownerActivity'] is True
        assert dialog['showing'] is (phase in ADDRESS_PHASES)
        if phase not in ADDRESS_PHASES:
            assert dialog['dialogRef'] == dialog['editorRef'] == 0
        if phase not in ADDRESS_PHASES + ('environmentPicker',) + MENU_PHASES:
            assert sample['windowFocus'] is True, ('Native collapse window focus', phase)
    # Same complete gesture geometry and trusted document input as v1.
    for before_key, after_key, expanded in (('initialChat', 'up', False), ('up', 'down', False), ('compactExpand', 'horizontal', True)):
        gesture(samples[before_key], samples[after_key]); assert samples[after_key]['expanded'] is expanded
    assert samples['up']['scrollY'] > initial['scrollY'] and any(t['trusted'] is True and t['type'] == 'touchend' for t in samples['up']['trusted'])
    collapsed = (() if browser else ('ready',)) + ('up', 'down', 'upBeforeChat', 'upBeforeNative', 'upBeforeResume', 'activityResume', 'headerUp')
    for phase in collapsed:
        s = samples[phase]
        assert s['expanded'] is False and s['toolbarVisibility'] == s['compactVisibility'] == 0 and s['topVisibility'] == 8
        assert s['webHeight'] == compact['webHeight'] and s['navigationVisibility'] == 0
    expanded = (('ready',) if browser else ()) + ('initialChat', 'compactExpand', 'horizontal', 'short', 'selectedChat', 'nativeReturn', 'resumeChat') + NORMAL_UI_PHASES[5:]
    for phase in expanded:
        s = samples[phase]
        assert s['expanded'] is True and s['compactVisibility'] == 8 and s['topVisibility'] == s['toolbarVisibility'] == 0
        assert s['webHeight'] == initial['webHeight'] and s['navigationVisibility'] == 0
    header = samples['headerUp']; touches = header['nativeTouches']; before = samples['resumeChat']
    assert header['activityStarts'] == before['activityStarts'] == 0 and header['menuOpens'] == before['menuOpens'] == 1 and header['windowFocus'] is True
    inside(before['headerSwipeFrom'], before['headerButtonTouch'])
    assert len(touches) >= 3 and touches[0]['action'] == 0 and touches[-1]['action'] == 1 and any(t['action'] == 2 for t in touches)
    assert all(t['pointers'] == 1 and t['height'] == initial['webHeight'] and t['expanded'] is True for t in touches)
    for phase in ('network', 'downloads'):
        assert samples[phase]['toolbarVisibility'] == 8 and samples[phase]['navigationVisibility'] == 0
    for phase in ('reading', 'readingBackMode'):
        s = samples[phase]
        assert s['toolbarVisibility'] == s['navigationVisibility'] == 8 and s['readingExitVisibility'] == 0
        assert s['webHeight'] == initial['webHeight'] + initial['toolbarHeight'] + initial['workspaceHeight'] - s['workspaceHeight']
        assert s['webHeight'] > initial['webHeight']
    ui = case['nativeUi']; assert set(ui) == UI_PHASES
    assert type(case['androidUser']) is int and case['androidUser'] >= 0
    interpreted = {}
    for phase, value in ui.items():
        assert value['phase'] == phase and value['runNonce'] == case['runNonce'] and value['sourceCommit'] == source
        for raw_key, size_key, hash_key in (('rawXml', 'xmlBytes', 'xmlSha256'), ('activityState', 'activityBytes', 'activitySha256')):
            raw = value[raw_key].encode('utf-8')
            assert 0 < len(raw) <= 1024*1024 and value[size_key] == len(raw) and value[hash_key] == hashlib.sha256(raw).hexdigest()
        expected_activity = ENVIRONMENT_ACTIVITY if phase in ('environment', 'drawer') else ACTIVITY
        assert resumed(value['activityState']) == {(case['androidUser'], expected_activity)}
        interpreted[phase] = inspect_ui(value['rawXml'], phase, initial['environmentName'], browser=browser)
        if phase in ADDRESS_PHASES:
            address_cancel(samples[phase], interpreted[phase])
        elif phase in ('environmentPicker',) + MENU_PHASES:
            assert samples[phase]['windowFocus'] is False and samples[phase]['addressDialog']['showing'] is False
        elif phase in ('reading', 'readingBackMode'):
            assert samples[phase]['readingExitTap'] == interpreted[phase]['exitPoint']
    # Exact ordered emissions: no claimed destination with its real input missing.
    inputs = case['actualAndroidInputs']; assert len(inputs) == len(INPUTS)
    for row, (label, kind, previous, target) in zip(inputs, INPUTS):
        if browser and label == 'initialAddress': target = 'addressTap'
        assert row['label'] == label and row['kind'] == kind and row['before'] == previous and row['actualAndroidInput'] is True
        assert 'shortTargetProof' not in row or (kind == 'swipe' and target == 'short' and previous == 'horizontal')
        if kind == 'tap':
            if target == 'cancel':
                wanted = interpreted[previous]['controls'][0]; assert row['bounds'] == wanted['bounds']
                point = wanted['point']; inside(point, wanted['bounds'])
            elif target.startswith('menu:'):
                wanted=menu_action(ui[previous]['rawXml'],PACKAGE,target[5:])
                assert row['bounds'] == wanted['bounds']; point=wanted['point']
            elif target == 'closePicker':
                wanted = interpreted[previous]; point = wanted['closePoint']; assert row['bounds'] == wanted['closeBounds']
            else:
                point = samples[previous][target]
            assert type(point) is list and len(point) == 2 and all(type(n) is int and n >= 0 for n in point)
            assert row['point'] == point
        elif kind == 'swipe':
            assert row['durationMs'] == 320
            s = samples[previous]; x = s['webX'] + s['webWidth']//2; top = s['webY'] + s['webHeight']//4; bottom = s['webY'] + s['webHeight']*2//3
            start, end = ([x, bottom], [x, top]) if target == 'up' else ([x, top], [x, bottom])
            if target == 'horizontal': start, end = [s['webX']+s['webWidth']//4, (top+bottom)//2], [s['webX']+s['webWidth']*3//4, (top+bottom)//2]
            if target == 'short': start, end = [x, bottom], [x, bottom-12]
            if target == 'short' and 'shortTargetProof' in row:
                geometry = verify_short_target(row['shortTargetProof'], identity=identity,
                    nonce=case['runNonce'], android_user=case['androidUser'], before=s)
                start, end = geometry['from'], geometry['to']
            if target == 'header': start, end = s['headerSwipeFrom'], s['headerSwipeTo']
            assert row['from'] == start and row['to'] == end
        elif kind == 'longPress':
            assert row['durationMs'] == 700 and row['point'] == samples[previous][target]
        elif kind == 'back': assert row['key'] == 'KEYCODE_BACK'
        else: assert kind == 'homeRoundtrip' and row['component'] == ACTIVITY and row['originalBudgetMs'] == 20000
    assert sum(row['kind'] == 'swipe' for row in inputs) == 8 and sum(row['kind'] == 'tap' for row in inputs) >= 6
    for key, counter in (('firstTapReadiness', 'tapInvocations'), ('headerReadiness', 'gestureInvocations')):
        value = case[key]
        assert value['status'] == 'passed' and value['sourceCommit'] == source and value[counter] == 1
        assert value['preEmitOnly'] is True and value['releaseAcceptance'] is False and value['applicationAcceptance'] is False
        assert value['originalActionBudgetMs'] == 90000 and value['preparationBudgetMs'] == 20000
    if browser:
        assert case['firstTapReadiness']['target'] == 'address'
        assert case['firstTapReadiness']['scope'] == 'chrome-initial-address-tap-only'
    assert set(case['menuScrolls']) == set(MENU_TARGETS)
    for phase, scrolls in case['menuScrolls'].items():
        verify_menu_scrolls(scrolls, PACKAGE, MENU_TARGETS[phase])
    requests = case['fixtureRequests']
    assert len(requests) == 1 and requests[0]['kind'] == 'http' and requests[0]['path'] == '/c/reload-collapse' and requests[0]['documentMarker'] == initial['document']
    return len(names)


def verify_auto_collapse_v3(report, source, apk_sha):
    browser = report.get('browserChrome', False)
    assert browser is True
    assert type(report.get('navigationContract')) is int and report['navigationContract'] == 3
    assert report['status'] == 'passed' and report['sourceCommit'] == source
    assert all(report[k] is True for k in ('actualAndroidExecution', 'actualGeckoExecution', 'actualAndroidTouchExecution'))
    identity = report['buildIdentity']; assert identity['sourceCommit'] == source and identity['apkSha256'] == apk_sha
    cases = report['cases']
    assert all(type(c.get('browserChrome', False)) is bool and c.get('browserChrome', False) is browser for c in cases)
    assert len(cases) == 3 and {(c['viewport'], c['fontScale']) for c in cases} == {(360, 1), (412, 1), (360, 2)}
    assert len({case['runNonce'] for case in cases}) == 3
    total = sum(verify_case(case, identity) for case in cases)
    return dict(navigationContract=3, cases=3, actualAndroidExecution=True, actualGeckoExecution=True,
                checks=total, retainedLegacyProtections=12 if browser else 14, browserStartupProtections=2 if browser else 0,
                phasesPerCase=len(PHASES), actualInputsPerCase=len(INPUTS))
