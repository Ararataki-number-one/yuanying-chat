"""Version 2: actual address dialogs and the four-action conversation dock.

This is a separate reader, not a projection into the historical six-tap report.
All fourteen original protections remain, with the removed Chat/Settings taps
replaced by explicit current-address and Network roundtrips. New destinations,
reading, environment long-press, More and Drawer have additional real inputs.
"""
import hashlib
import json
import math
import re
import xml.etree.ElementTree as ET

if __package__:
    from .integration_event_contract import EventTransfer, event_uri
    from .workspace_navigation_contract import navigation, bounds
    from .compact_chrome_layout_v2 import address_dialog, inside, rect
else:
    from integration_event_contract import EventTransfer, event_uri
    from workspace_navigation_contract import navigation, bounds
    from compact_chrome_layout_v2 import address_dialog, inside, rect

PACKAGE = 'local.pocketchat.test'
ACTIVITY = PACKAGE + '/local.pocketchat.CompactChromeIntegrationActivity'
ENVIRONMENT_ACTIVITY = PACKAGE + '/local.pocketchat.WindowHomeActivity'
TARGET = 'https://chatgpt.com/c/reload-collapse'
PHASES = (
    'ready', 'initialAddress', 'initialChat', 'up', 'down', 'compactAddress',
    'compactExpand', 'horizontal', 'short', 'upBeforeChat', 'selectedAddress',
    'selectedChat', 'upBeforeNative', 'network', 'nativeReturn', 'upBeforeResume',
    'activityResume', 'resumeAddress', 'resumeChat', 'headerUp', 'extrasAddress',
    'extrasExpanded', 'environmentReturn', 'downloads', 'downloadsReturn',
    'reading', 'readingExit', 'readingBackMode', 'readingBack',
    'environmentPicker', 'pickerReturn', 'more', 'moreReturn', 'drawerReturn',
)
ADDRESS_PHASES = ('initialAddress', 'compactAddress', 'selectedAddress', 'resumeAddress', 'extrasAddress')
NORMAL_UI_PHASES = ('initialChat', 'compactExpand', 'selectedChat', 'nativeReturn',
                    'resumeChat', 'extrasExpanded', 'environmentReturn', 'downloadsReturn',
                    'readingExit', 'readingBack', 'pickerReturn', 'moreReturn', 'drawerReturn')
UI_PHASES = set(ADDRESS_PHASES + NORMAL_UI_PHASES +
                ('network', 'environment', 'downloads', 'reading', 'readingBackMode',
                 'environmentPicker', 'more', 'drawer'))
STABLE = ('surface', 'sdkSession', 'attachedSession', 'document', 'draft', 'cookie',
          'sendCount', 'path', 'loads', 'stops', 'documents', 'pending', 'pendingStored')
NAMES = (
    'Actual Gecko document starts with collapsed environment controls',
    'Tapping compact environment name opens the address dialog and preserves the document',
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
    'Environment dock opens the actual environment Activity and Back preserves the SDK document',
    'Downloads dock opens the native download page and Back restores conversation controls',
    'Reading hides native chrome and its actual exit button restores the same document',
    'Back exits reading without leaving the conversation or navigating the document',
    'Long-pressing the environment capsule opens and closes the actual environment picker',
    'More opens the native conversation menu and Back dismisses it without an action',
    'Drawer opens the actual environment Activity and Back preserves the SDK document',
)
LEGACY_BEHAVIOR_MAP = (
    ('cold-collapsed', 'ready'), ('compact-tap-reveal', 'initialAddress/initialChat'),
    ('up-after-release', 'up'), ('down-keeps-compact', 'down'),
    ('compact-tappable-after-swipe', 'compactAddress/compactExpand'),
    ('horizontal-preserves-expanded', 'horizontal'), ('short-preserves-expanded', 'short'),
    ('selected-chat-reveal', 'selectedAddress/selectedChat'),
    ('native-settings-return', 'network/nativeReturn'), ('resume-keeps-compact', 'activityResume'),
    ('explicit-chat-after-resume', 'resumeAddress/resumeChat'),
    ('header-after-release', 'headerUp'), ('header-real-button-region', 'resumeChat/headerUp'),
    ('one-document-no-send', 'all-phases'),
)
# label, kind, preceding source snapshot, native target (or direction)
INPUTS = (
    ('initialAddress', 'tap', 'ready', 'compactTap'), ('initialChat', 'tap', 'initialAddress', 'cancel'),
    ('up', 'swipe', 'initialChat', 'up'), ('down', 'swipe', 'up', 'down'),
    ('compactAddress', 'tap', 'down', 'compactTap'), ('compactExpand', 'tap', 'compactAddress', 'cancel'),
    ('horizontal', 'swipe', 'compactExpand', 'horizontal'), ('short', 'swipe', 'horizontal', 'short'),
    ('upBeforeChat', 'swipe', 'short', 'up'), ('selectedAddress', 'tap', 'upBeforeChat', 'compactTap'),
    ('selectedChat', 'tap', 'selectedAddress', 'cancel'), ('upBeforeNative', 'swipe', 'selectedChat', 'up'),
    ('network', 'tap', 'upBeforeNative', 'networkTap'), ('nativeReturn', 'back', 'network', ''),
    ('upBeforeResume', 'swipe', 'nativeReturn', 'up'), ('activityResume', 'homeRoundtrip', 'upBeforeResume', ''),
    ('resumeAddress', 'tap', 'activityResume', 'compactTap'), ('resumeChat', 'tap', 'resumeAddress', 'cancel'),
    ('headerUp', 'swipe', 'resumeChat', 'header'),
    ('extrasAddress', 'tap', 'headerUp', 'compactTap'), ('extrasExpanded', 'tap', 'extrasAddress', 'cancel'),
    ('environment', 'tap', 'extrasExpanded', 'environmentTap'), ('environmentReturn', 'back', 'environment', ''),
    ('downloads', 'tap', 'environmentReturn', 'downloadsTap'), ('downloadsReturn', 'back', 'downloads', ''),
    ('reading', 'tap', 'downloadsReturn', 'readingTap'), ('readingExit', 'tap', 'reading', 'readingExitTap'),
    ('readingBackMode', 'tap', 'readingExit', 'readingTap'), ('readingBack', 'back', 'readingBackMode', ''),
    ('environmentPicker', 'longPress', 'readingBack', 'addressTap'), ('pickerReturn', 'tap', 'environmentPicker', 'closePicker'),
    ('more', 'tap', 'pickerReturn', 'moreTap'), ('moreReturn', 'back', 'more', ''),
    ('drawer', 'tap', 'moreReturn', 'drawerTap'), ('drawerReturn', 'back', 'drawer', ''),
)


def center(value):
    left, top, right, bottom = rect(value)
    return [(left + right) // 2, (top + bottom) // 2]


def resumed(raw):
    result = set()
    for line in raw.splitlines():
        field = re.fullmatch(r'\s*(?:mResumedActivity|topResumedActivity)\s*[:=]\s*(.*)', line)
        if field is None or field[1] == 'null':
            continue
        match = re.fullmatch(r'ActivityRecord\{[^{}]*?\bu([0-9]+)\s+([A-Za-z0-9_.]+)/([A-Za-z0-9_.$]+)(?:\s+[^{}]*)?\}', field[1])
        assert match is not None, 'Unrecognized current native Activity'
        user, package, activity = match.groups()
        result.add((int(user), package + '/' + (package + activity if activity.startswith('.') else activity)))
    return result


def short_target_geometry(raw_xml, before):
    """Select one original 12 px short gesture outside actual editable controls.

    Only the short gesture may use this explicit target contract. The original
    center point wins whenever its complete segment has 24 px clearance. If it
    intersects an actionable descendant, use the center of the largest
    full-width blank vertical band in the same owned WebView. A narrow gutter
    beside a control is not a replacement target: Gecko can adjust a short
    touch into the nearby editor even when the native coordinates miss it.
    """
    assert type(raw_xml) is str and 0 < len(raw_xml.encode('utf-8')) <= 1024*1024
    assert before['command'] == 'horizontal' and before['expanded'] is True
    assert before['keyboard'] is False and before['windowFocus'] is True
    assert type(before['page']) is int and before['page'] == 0 and before['addressDialog']['showing'] is False
    for key in ('webX', 'webY', 'webWidth', 'webHeight'):
        assert type(before[key]) is int and before[key] >= 0
    expected = [before['webX'], before['webY'], before['webX']+before['webWidth'],
                before['webY']+before['webHeight']]
    left, top, right, bottom = rect(expected)
    tree = ET.fromstring(raw_xml)
    assert tree.tag == 'hierarchy'
    nodes = list(tree.iter('node')); assert 0 < len(nodes) <= 4096
    webs = [n for n in nodes if n.attrib.get('class') == 'android.webkit.WebView']
    assert len(webs) == 1, 'Short target needs one unambiguous native WebView'
    web = webs[0]
    assert web.attrib.get('package') == PACKAGE and web.attrib.get('enabled') == 'true'
    assert bounds(web) == expected, 'Short target WebView moved after horizontal snapshot'
    parents = {child: parent for parent in tree.iter() for child in parent}
    ancestor = web
    while parents.get(ancestor) is not None and parents[ancestor].tag == 'node':
        ancestor = parents[ancestor]
        assert ancestor.attrib.get('package') == PACKAGE, 'Short target has a foreign native ancestor'
        al, at, ar, ab = bounds(ancestor)
        assert al <= left < right <= ar and at <= top < bottom <= ab
    descendants = list(web.iter('node'))[1:]
    controls = []
    for node in descendants:
        assert node.attrib.get('package') == PACKAGE, 'Short target has a foreign WebView descendant'
        flags = ('clickable', 'long-clickable', 'focusable', 'checkable')
        assert all(node.attrib.get(key) in ('true', 'false') for key in flags)
        actionable = node.attrib.get('class') == 'android.widget.EditText' or any(node.attrib[key] == 'true' for key in flags)
        if actionable:
            rectangle = bounds(node)
            if max(left, rectangle[0]) < min(right, rectangle[2]) and max(top, rectangle[1]) < min(bottom, rectangle[3]):
                controls.append(rectangle)
    # An overlapping native control or foreign window cannot become a blank
    # area merely because it is outside the WebView's accessibility subtree.
    descendants_set = set(descendants)
    ancestors = set(); ancestor = web
    while parents.get(ancestor) is not None:
        ancestor = parents[ancestor]; ancestors.add(ancestor)
    for node in nodes:
        if node is web or node in descendants_set or node in ancestors: continue
        rectangle = bounds(node)
        if max(left, rectangle[0]) >= min(right, rectangle[2]) or max(top, rectangle[1]) >= min(bottom, rectangle[3]): continue
        assert node.attrib.get('package') == PACKAGE, 'Short target overlaps a foreign native window'
        if node.attrib.get('class') == 'android.widget.EditText' or any(node.attrib.get(key) == 'true' for key in ('clickable', 'long-clickable', 'focusable', 'checkable')):
            controls.append(rectangle)
    controls = [list(value) for value in sorted(set(map(tuple, controls)))]
    assert len(controls) <= 512
    margin, distance = 24, 12
    original = [left+(right-left)//2, top+(bottom-top)*2//3]
    xl, xr, yt, yb = left+margin, right-margin, top+margin+distance, bottom-margin
    assert xl < xr and yt < yb, 'No sufficiently inset WebView short target'
    blocked = [(max(xl, l-margin), max(yt, t-margin), min(xr, r+margin), min(yb, b+margin+distance))
               for l, t, r, b in controls]
    blocked = [row for row in blocked if row[0] < row[2] and row[1] < row[3]]
    def safe(point):
        x, y = point
        return xl <= x < xr and yt <= y < yb and not any(l <= x < r and t <= y < b for l, t, r, b in blocked)
    selected = original
    if not safe(selected):
        # Project every actionable rectangle across the WebView width. Sweep
        # only its vertical boundaries, then use a gap's middle rather than a
        # control-adjacent edge. This changes only pre-emission preparation.
        intervals = sorted((t, b) for l, t, r, b in blocked)
        gaps = []
        edge = yt
        for t, b in intervals + [(yb, yb)]:
            if edge < t:
                gaps.append((edge, t))
            edge = max(edge, b)
        assert gaps, 'No full-width editable-safe short gesture segment remains'
        start, end = min(gaps, key=lambda gap: (-(gap[1]-gap[0]),
            abs((gap[0]+gap[1]-1)//2-original[1]), gap[0]))
        selected = [original[0], (start+end-1)//2]
    assert safe(selected)
    return dict(targetContract=1, webBounds=expected, excludedBounds=controls, marginPx=margin,
                originalFrom=original, originalTo=[original[0], original[1]-distance],
                **{'from': selected, 'to': [selected[0], selected[1]-distance], 'durationMs': 320})


def make_short_target_proof(*, raw_xml, activity_state, identity, nonce, android_user, before,
                            capture_nonce, capture_record, action_started_ns, activity_started_ns,
                            activity_completed_ns, prepared_ns):
    """Bind a fresh read-only capture to one pre-emission short target.

    Host monotonic times describe the real acquisition order, not Android event
    timestamps. This is input preparation inside the original 90 s command
    budget; it is never a replacement snapshot or a passing application result.
    """
    assert type(raw_xml) is str and 0 < len(raw_xml.encode('utf-8')) <= 1024*1024
    assert re.fullmatch('[0-9a-f]{40}', identity['sourceCommit']) and re.fullmatch('[0-9a-f]{40}', identity['sourceTree'])
    assert re.fullmatch('[0-9a-f]{64}', identity['apkSha256'])
    assert re.fullmatch('[0-9a-f]{32}', nonce) and re.fullmatch('[0-9a-f]{32}', capture_nonce)
    assert type(android_user) is int and android_user >= 0
    assert type(activity_state) is str and 0 < len(activity_state.encode('utf-8')) <= 1024*1024
    assert resumed(activity_state) == {(android_user, ACTIVITY)}
    for value in (action_started_ns, activity_started_ns, activity_completed_ns, prepared_ns):
        assert type(value) is int and value > 0
    preparation_deadline = action_started_ns+20_000_000_000
    assert action_started_ns <= activity_started_ns <= activity_completed_ns <= prepared_ns < preparation_deadline
    record = json.loads(json.dumps(capture_record, ensure_ascii=False, allow_nan=False))
    assert set(record) == set(('index remotePath commands startedAtMonotonicNanos existingSceneDeadline status xmlBytes xmlSha256 completedAtMonotonicNanos').split())
    assert type(record['index']) is int and record['index'] > 0 and record['status'] == 'captured'
    remote = '/sdcard/pocketchat-ui-visual-'+capture_nonce+'-'+str(record['index'])+'.xml'
    assert record['remotePath'] == remote
    deadline = record['existingSceneDeadline']
    assert type(deadline) in (int, float) and math.isfinite(deadline) and abs(deadline*1_000_000_000-preparation_deadline) <= 1024
    for key in ('startedAtMonotonicNanos', 'completedAtMonotonicNanos'):
        assert type(record[key]) is int
    assert action_started_ns <= record['startedAtMonotonicNanos'] <= record['completedAtMonotonicNanos'] <= activity_started_ns
    raw = raw_xml.encode('utf-8'); digest = hashlib.sha256(raw).hexdigest()
    assert type(record['xmlBytes']) is int and record['xmlBytes'] == len(raw) and record['xmlSha256'] == digest
    commands = record['commands']; assert type(commands) is list and len(commands) == 2
    previous = record['startedAtMonotonicNanos']
    for index, command in enumerate(commands):
        assert set(command) == set(('parts startedAtWallTimeMillis startedAtMonotonicNanos timeoutSeconds exitCode stdout stderr completedAtMonotonicNanos completedAtWallTimeMillis').split())
        assert command['parts'] == (['shell', 'uiautomator', 'dump', remote] if index == 0 else ['shell', 'cat', remote])
        assert type(command['exitCode']) is int and command['exitCode'] == 0
        for key in ('startedAtWallTimeMillis', 'completedAtWallTimeMillis', 'startedAtMonotonicNanos', 'completedAtMonotonicNanos'):
            assert type(command[key]) is int and command[key] > 0
        assert previous <= command['startedAtMonotonicNanos'] <= command['completedAtMonotonicNanos'] <= record['completedAtMonotonicNanos']
        assert command['startedAtWallTimeMillis'] <= command['completedAtWallTimeMillis']
        remaining = (preparation_deadline-command['startedAtMonotonicNanos'])/1_000_000_000
        timeout = command['timeoutSeconds']
        assert type(timeout) in (int, float) and math.isfinite(timeout) and 0 < timeout <= 20 and timeout <= remaining+.002
        previous = command['completedAtMonotonicNanos']
        def output(value, expected):
            assert set(value) == {'bytes', 'sha256', 'text', 'truncated'}
            assert type(value['bytes']) is int and value['bytes'] == len(expected)
            assert value['sha256'] == hashlib.sha256(expected).hexdigest()
            assert value['text'] == expected[:8192].decode('utf-8', 'replace')
            assert value['truncated'] is (len(expected) > 8192)
        output(command['stderr'], b'')
        if index == 0:
            stdout = command['stdout']['text'].encode('utf-8')
            assert stdout.decode().strip() in ('', 'UI hierchary dumped to: '+remote, 'UI hierarchy dumped to: '+remote)
            output(command['stdout'], stdout)
        else: output(command['stdout'], raw)
    geometry = short_target_geometry(raw_xml, before)
    activity = activity_state.encode('utf-8')
    return dict(schema=1, kind='shortSwipeTarget', phase='horizontal', preEmitOnly=True,
        applicationAcceptance=False, sourceCommit=identity['sourceCommit'], sourceTree=identity['sourceTree'],
        apkSha256=identity['apkSha256'], runNonce=nonce, androidUser=android_user,
        beforeSnapshotSha256=hashlib.sha256(json.dumps(before, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest(),
        rawXml=raw_xml, xmlBytes=len(raw), xmlSha256=digest,
        activityState=activity_state, activityBytes=len(activity), activitySha256=hashlib.sha256(activity).hexdigest(),
        captureRunNonce=capture_nonce, captureRecord=record, actionStartedAtMonotonicNanos=action_started_ns,
        activityStartedAtMonotonicNanos=activity_started_ns, activityCompletedAtMonotonicNanos=activity_completed_ns,
        preparedAtMonotonicNanos=prepared_ns, originalActionBudgetMs=90000, preparationBudgetMs=20000, geometry=geometry)


def verify_short_target(proof, *, identity, nonce, android_user, before):
    """Recompute every target field from the original bytes; never trust a point."""
    expected = make_short_target_proof(raw_xml=proof['rawXml'], activity_state=proof['activityState'],
        identity=identity, nonce=nonce, android_user=android_user, before=before,
        capture_nonce=proof['captureRunNonce'], capture_record=proof['captureRecord'],
        action_started_ns=proof['actionStartedAtMonotonicNanos'], activity_started_ns=proof['activityStartedAtMonotonicNanos'],
        activity_completed_ns=proof['activityCompletedAtMonotonicNanos'], prepared_ns=proof['preparedAtMonotonicNanos'])
    assert json.dumps(proof, sort_keys=True, allow_nan=False) == json.dumps(expected, sort_keys=True, allow_nan=False), 'Short target proof differs from its original read-only observations'
    assert type(proof['schema']) is int and type(proof['geometry']['targetContract']) is int
    assert type(proof['androidUser']) is int and type(proof['xmlBytes']) is type(proof['activityBytes']) is int
    assert type(proof['originalActionBudgetMs']) is type(proof['preparationBudgetMs']) is int
    return expected['geometry']


def modal(xml, kind, environment):
    nodes = list(ET.fromstring(xml).iter('node'))
    title = '快速切换环境' if kind == 'environmentPicker' else '会话选项'
    def one(widget, field, value):
        rows = [n for n in nodes if n.attrib.get('package') == PACKAGE and
                n.attrib.get('class') == 'android.widget.' + widget and n.attrib.get(field) == value]
        assert len(rows) == 1, ('Missing or ambiguous native modal control', kind, value)
        bounds(rows[0])
        return rows[0]
    heading = one('TextView', 'text', title)
    assert heading.attrib.get('content-desc') == title
    close = one('Button', 'content-desc', '关闭' + title)
    assert close.attrib.get('enabled') == close.attrib.get('clickable') == 'true'
    if kind == 'environmentPicker':
        search = one('EditText', 'content-desc', '搜索要切换的环境')
        assert search.attrib.get('enabled') == search.attrib.get('clickable') == 'true'
        selected = [n for n in nodes if n.attrib.get('package') == PACKAGE and
                    n.attrib.get('class') == 'android.widget.Button' and n.attrib.get('selected') == 'true']
        assert len(selected) == 1
        current = selected[0]
        assert current.attrib.get('text', '').startswith('01  ') and ' · 当前\n' in current.attrib.get('text', '')
        assert current.attrib.get('content-desc', '').startswith('切换到 ' + environment + '，')
        assert current.attrib.get('enabled') == current.attrib.get('clickable') == 'true'
        bounds(current)
    else:
        address = one('Button', 'text', '打开网址或搜索')
        assert address.attrib.get('enabled') == address.attrib.get('clickable') == 'true'
    return dict(title=title, closeBounds=bounds(close), closePoint=center(bounds(close)))


def inspect_ui(raw, phase, environment):
    """Pure reader of original, unmodified Android XML; used before real input."""
    if phase in ADDRESS_PHASES:
        result = address_dialog(raw, PACKAGE)
        fields = [n for n in ET.fromstring(raw).iter('node') if n.attrib.get('package') == PACKAGE and n.attrib.get('class') == 'android.widget.EditText']
        assert len(fields) == 1 and fields[0].attrib.get('content-desc') == '网址或搜索'
        assert fields[0].attrib.get('text') == TARGET and fields[0].attrib.get('focused') == 'true'
        return result
    if phase in ('environmentPicker', 'more'):
        return modal(raw, phase, environment)
    if phase in ('reading', 'readingBackMode'):
        nodes = list(ET.fromstring(raw).iter('node'))
        exits = [n for n in nodes if n.attrib.get('package') == PACKAGE and n.attrib.get('class') == 'android.widget.Button'
                 and n.attrib.get('text') == '退出阅读' and n.attrib.get('content-desc') == '退出专注阅读，恢复应用工具栏和导航']
        assert len(exits) == 1 and exits[0].attrib.get('enabled') == exits[0].attrib.get('clickable') == 'true'
        assert not any(n.attrib.get('package') == PACKAGE and n.attrib.get('content-desc') in
                       ('管理环境', '更多', '进入专注阅读模式', '环境', '网络', '下载') for n in nodes)
        return dict(exitBounds=bounds(exits[0]), exitPoint=center(bounds(exits[0])))
    if phase in ('environment', 'drawer', 'network', 'downloads'):
        return navigation(raw, PACKAGE, conversation=False,
                          selected={'environment': '环境', 'drawer': '环境', 'network': '网络', 'downloads': '下载'}[phase])
    assert phase in NORMAL_UI_PHASES
    value = navigation(raw, PACKAGE, conversation=True)
    assert not any(n.attrib.get('package') == PACKAGE and n.attrib.get('text') in
                   ('打开网址', '快速切换环境', '会话选项') for n in ET.fromstring(raw).iter('node'))
    return value


def gesture(before, after):
    touches = after['touches']
    assert len(touches) >= 3 and touches[0]['action'] == 0 and touches[-1]['action'] == 1 and any(t['action'] == 2 for t in touches)
    assert all(t['pointers'] == 1 and t['width'] == before['webWidth'] and t['height'] == before['webHeight'] and
               t['expanded'] is before['expanded'] for t in touches)


def address_cancel(sample, interpreted):
    """Bind the real owned dialog's cancel geometry to a fresh native XML read.

    The workload uses this same full reader before emitting a cancel input, not
    only after the complete case. A keyboard relocation can never authorize a
    tap using the preceding, pre-IME XML bounds.
    """
    d = sample['addressDialog']
    assert sample['expanded'] is True and sample['windowFocus'] is False
    assert type(d['schema']) is int and d['schema'] == 1 and d['ownerActivity'] is d['showing'] is True
    assert type(d['dialogRef']) is int and d['dialogRef'] > 0 and type(d['editorRef']) is int and d['editorRef'] > 0
    assert d['dialogClass'] == 'android.app.AlertDialog' and d['editorClass'] == 'android.widget.EditText'
    assert all(d[k] is True for k in ('decorAttached', 'decorShown', 'decorFocus', 'editorShown', 'editorFocused', 'editorWindowFocus', 'sameWindow', 'cancelShown', 'cancelEnabled', 'cancelClickable'))
    assert d['editorDescription'] == '网址或搜索' and d['editorText'] == TARGET and d['editorInputType'] == 17 and d['editorMaxLines'] == 1 and d['cancelText'] == '取消'
    for key in ('decorBounds', 'editorBounds', 'cancelBounds'): rect(d[key])
    cancel = interpreted['controls'][0]
    assert cancel['label'] == '取消' and d['cancelBounds'] == cancel['bounds'], 'Native address cancel geometry moved before input'
    assert cancel['point'] == center(cancel['bounds'])
    inside(cancel['point'], cancel['bounds'])
    return cancel


def verify_case(case, identity):
    source = identity['sourceCommit']
    assert type(case.get('navigationContract')) is int and case['navigationContract'] == 2
    assert case['sourceCommit'] == source and re.fullmatch('[0-9a-f]{32}', case['runNonce'])
    assert all(case[k] is True for k in ('actualAndroidExecution', 'actualGeckoExecution', 'actualAndroidTouchExecution'))
    assert [c['name'] for c in case['checks']] == list(NAMES) and all(c['pass'] is True for c in case['checks'])
    assert case['legacyBehaviorMap'] == [list(row) for row in LEGACY_BEHAVIOR_MAP]
    owned = case['eventTransfer']
    assert owned['runNonce'] == case['runNonce'] and owned['fixtureAction'] == 'chromeCollapse' and type(owned['processSlot']) is int and owned['processSlot'] == 0
    rows = owned['events']; payloads = {event_uri(row['receipt']): row['rawUtf8'].encode('utf-8') for row in rows}
    assert len(rows) == len(payloads) == len(PHASES)
    transfer = EventTransfer(identity=identity, nonce=case['runNonce'], slot=0, action='chromeCollapse', fetch=lambda uri: payloads[uri])
    samples = {}
    for expected, row in zip(PHASES, rows):
        event = transfer.read(row['receipt']); assert event['kind'] == 'collapseSnapshot'
        sample = event['result']; assert sample['command'] == expected and expected not in samples
        assert type(sample.get('navigationContract')) is int and sample['navigationContract'] == 2
        samples[expected] = sample
    assert samples == case['observations'] and list(samples) == list(PHASES)
    cold, initial = samples['ready'], samples['initialChat']
    assert cold['expanded'] is False and cold['toolbarVisibility'] == cold['compactVisibility'] == cold['networkVisibility'] == 0 and cold['topVisibility'] == 8
    assert cold['compactName'] == cold['environmentName'] and cold['compactHeight'] > 0
    assert cold['webHeight'] == initial['webHeight'] + initial['toolbarHeight'] - cold['toolbarHeight']
    assert initial['toolbarHeight'] > cold['toolbarHeight'] and initial['webHeight'] > 0
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
        assert sample['visibleDocument'] is True and sample['loadingCoverVisibility'] == 8
        assert sample['navigationLayout'] == ('workspace-five' if phase in ('network', 'downloads') else 'conversation-compact')
        index = PHASES.index(phase)
        assert sample['activityStarts'] == (2 if phase == 'drawerReturn' else 1 if index >= PHASES.index('environmentReturn') else 0)
        assert sample['menuOpens'] == (1 if index >= PHASES.index('more') else 0)
        assert sample['readingActive'] is (phase in ('reading', 'readingBackMode'))
        assert sample['readingRequested'] is sample['readingActive']
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
        if phase not in ADDRESS_PHASES + ('environmentPicker', 'more'):
            assert sample['windowFocus'] is True, ('Native collapse window focus', phase)
    # Same complete gesture geometry and trusted document input as v1.
    for before_key, after_key, expanded in (('initialChat', 'up', False), ('up', 'down', False), ('compactExpand', 'horizontal', True)):
        gesture(samples[before_key], samples[after_key]); assert samples[after_key]['expanded'] is expanded
    assert samples['up']['scrollY'] > initial['scrollY'] and any(t['trusted'] is True and t['type'] == 'touchend' for t in samples['up']['trusted'])
    collapsed = ('ready', 'up', 'down', 'upBeforeChat', 'upBeforeNative', 'upBeforeResume', 'activityResume', 'headerUp')
    for phase in collapsed:
        s = samples[phase]
        assert s['expanded'] is False and s['toolbarVisibility'] == s['compactVisibility'] == 0 and s['topVisibility'] == 8
        assert s['webHeight'] == cold['webHeight'] and s['navigationVisibility'] == 0
    expanded = ('initialChat', 'compactExpand', 'horizontal', 'short', 'selectedChat', 'nativeReturn', 'resumeChat') + NORMAL_UI_PHASES[5:]
    for phase in expanded:
        s = samples[phase]
        assert s['expanded'] is True and s['compactVisibility'] == 8 and s['topVisibility'] == s['toolbarVisibility'] == 0
        assert s['webHeight'] == initial['webHeight'] and s['navigationVisibility'] == 0
    header = samples['headerUp']; touches = header['nativeTouches']; before = samples['resumeChat']
    assert header['activityStarts'] == header['menuOpens'] == 0 and header['windowFocus'] is True
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
        interpreted[phase] = inspect_ui(value['rawXml'], phase, initial['environmentName'])
        if phase in ADDRESS_PHASES:
            address_cancel(samples[phase], interpreted[phase])
        elif phase in ('environmentPicker', 'more'):
            assert samples[phase]['windowFocus'] is False and samples[phase]['addressDialog']['showing'] is False
        elif phase in ('reading', 'readingBackMode'):
            assert samples[phase]['readingExitTap'] == interpreted[phase]['exitPoint']
    # Exact ordered emissions: no claimed destination with its real input missing.
    inputs = case['actualAndroidInputs']; assert len(inputs) == len(INPUTS)
    for row, (label, kind, previous, target) in zip(inputs, INPUTS):
        assert row['label'] == label and row['kind'] == kind and row['before'] == previous and row['actualAndroidInput'] is True
        assert 'shortTargetProof' not in row or (kind == 'swipe' and target == 'short' and previous == 'horizontal')
        if kind == 'tap':
            if target == 'cancel':
                wanted = interpreted[previous]['controls'][0]; assert row['bounds'] == wanted['bounds']
                point = wanted['point']; inside(point, wanted['bounds'])
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
    requests = case['fixtureRequests']
    assert len(requests) == 1 and requests[0]['kind'] == 'http' and requests[0]['path'] == '/c/reload-collapse' and requests[0]['documentMarker'] == initial['document']
    return len(NAMES)


def verify_auto_collapse_v2(report, source, apk_sha):
    assert type(report.get('navigationContract')) is int and report['navigationContract'] == 2
    assert report['status'] == 'passed' and report['sourceCommit'] == source
    assert all(report[k] is True for k in ('actualAndroidExecution', 'actualGeckoExecution', 'actualAndroidTouchExecution'))
    identity = report['buildIdentity']; assert identity['sourceCommit'] == source and identity['apkSha256'] == apk_sha
    cases = report['cases']
    assert len(cases) == 3 and {(c['viewport'], c['fontScale']) for c in cases} == {(360, 1), (412, 1), (360, 2)}
    assert len({case['runNonce'] for case in cases}) == 3
    total = sum(verify_case(case, identity) for case in cases)
    return dict(navigationContract=2, cases=3, actualAndroidExecution=True, actualGeckoExecution=True,
                checks=total, retainedLegacyProtections=14, phasesPerCase=len(PHASES), actualInputsPerCase=len(INPUTS))
