"""Version 3 reads the real bottom browser toolbar and retained workspaces.

Historical v1/v2 readers stay unchanged. No old dock or top address observation
is translated into this contract: all five targets must exist in native XML.
"""
import re
import hashlib
import json
import math
import time
import xml.etree.ElementTree as ET

if __package__:
    from .workspace_navigation_contract import bounds, navigation as workspace_navigation
else:
    from workspace_navigation_contract import bounds, navigation as workspace_navigation

VERSION = 3
MENU_ACTIONS = ('前进', '打开网址或搜索', '快速切换环境', '进入专注阅读',
                '当前环境网络', '管理全部环境', '下载管理')


def display_density_evidence(raw):
    """Keep Android's independent density readback, never infer it from a target."""
    assert type(raw) is str and 0 < len(raw.encode('utf-8')) <= 1024
    match = re.fullmatch(r'Physical density: ([1-9][0-9]*)(?:\r?\nOverride density: ([1-9][0-9]*))?\r?\n?', raw)
    assert match is not None, 'Expected one complete Android wm density readback'
    physical = int(match.group(1))
    override = int(match.group(2)) if match.group(2) is not None else None
    assert 72 <= physical <= 10000 and (override is None or 72 <= override <= 10000)
    encoded = raw.encode('utf-8')
    return dict(schema=1, command=['shell', 'wm', 'density'], rawStdout=raw,
                stdoutBytes=len(encoded), stdoutSha256=hashlib.sha256(encoded).hexdigest(),
                physicalDpi=physical, overrideDpi=override, effectiveDpi=override or physical)


def display_density(evidence=None):
    # Existing chrome cohorts independently configure 480 dpi and keep their
    # original contract. The general file runner supplies a device readback.
    if evidence is None:
        return 3.0
    assert type(evidence) is dict and type(evidence.get('schema')) is int
    assert type(evidence.get('stdoutBytes')) is int and type(evidence.get('physicalDpi')) is int
    assert type(evidence.get('effectiveDpi')) is int
    assert evidence.get('overrideDpi') is None or type(evidence['overrideDpi']) is int
    assert evidence == display_density_evidence(evidence['rawStdout']), 'Android density evidence changed'
    return evidence['effectiveDpi']/160


def minimum_touch_pixels(evidence=None):
    return int(48*display_density(evidence)+.5)


def center(rectangle):
    left, top, right, bottom = rectangle
    return [(left + right)//2, (top + bottom)//2]


def native_button(xml, package, label, *, field='content-desc', enabled=True):
    nodes = list(ET.fromstring(xml).iter('node'))
    matches = [n for n in nodes if n.get('package') == package
               and n.get('class') == 'android.widget.Button' and n.get(field) == label]
    assert len(matches) == 1, ('Missing or ambiguous native action', label)
    node = matches[0]
    assert node.get('clickable') == 'true' and node.get('visible-to-user') != 'false'
    assert node.get('enabled') == ('true' if enabled else 'false')
    box = bounds(node)
    return dict(label=label, bounds=box, point=center(box))


def menu_action(xml, package, label):
    tree = ET.fromstring(xml)
    headings = [n for n in tree.iter('node') if n.get('package') == package
                and n.get('class') == 'android.widget.TextView'
                and n.get('text') == n.get('content-desc') == '浏览器菜单']
    assert len(headings) == 1, 'Actual browser menu must be open'
    return native_button(xml, package, label, field='text')


def menu_body_ready(xml, package):
    """A newly shown native sheet may expose its header before its actions.

    An empty action subtree is an incomplete observation, not evidence that the
    requested action is below the viewport. Only a real visible button within
    the owned scroll body can authorize searching that body with a gesture.
    """
    tree = ET.fromstring(xml)
    nodes = list(tree.iter('node'))
    parents = {child: parent for parent in tree.iter() for child in parent}
    headings = [n for n in nodes if n.get('package') == package
                and n.get('class') == 'android.widget.TextView'
                and n.get('text') == n.get('content-desc') == '浏览器菜单'
                and n.get('visible-to-user') != 'false']
    close = [n for n in nodes if n.get('package') == package
             and n.get('class') == 'android.widget.Button'
             and n.get('content-desc') == '关闭浏览器菜单'
             and n.get('clickable') == n.get('enabled') == 'true'
             and n.get('visible-to-user') != 'false']
    scrollers = [n for n in nodes if n.get('package') == package
                 and n.get('class') == 'android.widget.ScrollView'
                 and n.get('scrollable') == n.get('enabled') == 'true'
                 and n.get('visible-to-user') != 'false']
    assert len(headings) == len(close) == len(scrollers) == 1, 'Expected the actual native browser menu'
    scroller = scrollers[0]
    left, top, right, bottom = bounds(scroller)
    assert 0 <= left < right and 0 <= top < bottom, 'Native menu scroller has no visible bounds'
    for node in scroller.iter('node'):
        if not (node.get('package') == package and node.get('class') == 'android.widget.Button'
                and node.get('text') and node.get('clickable') == node.get('enabled') == 'true'
                and node.get('visible-to-user') != 'false'):
            continue
        l, t, r, b = bounds(node)
        if not (left <= l < r <= right and top <= t < b <= bottom):
            continue
        ancestor = parents.get(node)
        while ancestor is not scroller:
            if (ancestor is None or ancestor.get('package') != package
                    or ancestor.get('visible-to-user') == 'false'
                    or ancestor.get('class') == 'android.webkit.WebView'):
                break
            ancestor = parents.get(ancestor)
        if ancestor is scroller:
            return True
    return False


def menu_scroll_points(viewport, target_bounds, *, coarse_start, coarse_end, minimum_target):
    """Keep a partially visible target in view while revealing its clipped edge.

    Android exposes clipped accessibility bounds. A full upward swipe can move
    a bottom-clipped row straight past the top, so an observed partial row needs
    a short correction in the direction of its missing edge. This only chooses
    a real gesture; a fresh hierarchy must still prove the original touch size.
    """
    assert isinstance(viewport, (list, tuple)) and len(viewport) == 4
    assert all(type(v) is int for v in viewport)
    left, top, right, bottom = viewport
    assert 0 <= left < right and 0 <= top < bottom
    assert type(minimum_target) is int and minimum_target > 0
    for point in (coarse_start, coarse_end):
        assert isinstance(point, (list, tuple)) and len(point) == 2
        assert all(type(v) is int for v in point)
        assert point[0] == (left+right)//2 and top < point[1] < bottom
    assert coarse_start[1] > coarse_end[1]
    start, end = list(coarse_start), list(coarse_end)
    if target_bounds is None:
        return start, end
    assert isinstance(target_bounds, (list, tuple)) and len(target_bounds) == 4
    assert all(type(v) is int for v in target_bounds)
    l, t, r, b = target_bounds
    assert left <= l < r <= right and top <= t < b <= bottom
    if b-t < minimum_target:
        clipped_top, clipped_bottom = t <= top+1, b >= bottom-1
        if clipped_top != clipped_bottom:
            distance = min(start[1]-end[1], minimum_target, max(1, (bottom-top)//3))
            if clipped_top:
                start, end = list(coarse_end), [start[0], coarse_end[1]+distance]
            else:
                end = [start[0], start[1]-distance]
    return start, end


def seek_menu_action(adb, read, package, label, *, deadline, scrolls, density_evidence=None):
    """Find a real menu action with bounded, recorded Android scroll inputs."""
    minimum = minimum_touch_pixels(density_evidence)
    while True:
        assert time.monotonic() < deadline, 'Original menu observation budget expired'
        xml = read(deadline=deadline)
        assert time.monotonic() < deadline, 'Original menu observation budget expired'
        if not menu_body_ready(xml, package):
            continue
        target = None
        try:
            target = menu_action(xml, package, label)
            box = target['bounds']
            if min(box[2]-box[0], box[3]-box[1]) >= minimum:
                return xml, target
        except AssertionError:
            pass
        tree = ET.fromstring(xml)
        assert any(n.get('package') == package and n.get('text') == n.get('content-desc') == '浏览器菜单'
                   for n in tree.iter('node')), 'Cannot scroll a window other than the actual browser menu'
        views = [n for n in tree.iter('node') if n.get('package') == package
                 and n.get('class') == 'android.widget.ScrollView' and n.get('scrollable') == 'true']
        assert len(views) == 1 and len(scrolls) < 8, ('Menu action is unavailable', label)
        left, top, right, bottom = bounds(views[0])
        start, end = menu_scroll_points([left, top, right, bottom],
            target['bounds'] if target is not None else None,
            coarse_start=[(left+right)//2, top+(bottom-top)*4//5],
            coarse_end=[(left+right)//2, top+(bottom-top)//5], minimum_target=minimum)
        raw = xml.encode('utf-8')
        observation = dict(label=label, rawXml=xml, xmlSha256=hashlib.sha256(raw).hexdigest(),
                            bounds=[left,top,right,bottom], **{'from':start, 'to':end},
                            durationMs=320, actualAndroidInput=True)
        assert time.monotonic() < deadline, 'Original menu observation budget expired before scroll'
        scrolls.append(observation)
        adb('shell', 'input', 'swipe', *map(str, start+end), '320')


def verify_menu_scrolls(scrolls, package, label, *, density_evidence=None):
    minimum = minimum_touch_pixels(density_evidence)
    assert type(scrolls) is list and len(scrolls) <= 8
    for value in scrolls:
        assert value['label'] == label and value['actualAndroidInput'] is True and value['durationMs'] == 320
        xml=value['rawXml']; assert type(xml) is str and 0 < len(xml.encode()) <= 1024*1024
        assert value['xmlSha256'] == hashlib.sha256(xml.encode()).hexdigest()
        assert menu_body_ready(xml, package), 'An incomplete menu body cannot authorize a scroll'
        nodes=list(ET.fromstring(xml).iter('node'))
        assert any(n.get('package') == package and n.get('text') == n.get('content-desc') == '浏览器菜单' for n in nodes)
        views=[n for n in nodes if n.get('package') == package and n.get('class') == 'android.widget.ScrollView' and n.get('scrollable') == 'true']
        assert len(views) == 1
        l,t,r,b=bounds(views[0]); assert value['bounds'] == [l,t,r,b]
        target = None
        try:
            target = menu_action(xml, package, label)
        except AssertionError:
            pass
        if target is not None:
            box = target['bounds']
            assert min(box[2]-box[0], box[3]-box[1]) < minimum, 'A fully tappable menu target needs no seek gesture'
        start, end = menu_scroll_points([l,t,r,b], target['bounds'] if target is not None else None,
            coarse_start=[(l+r)//2,t+(b-t)*4//5], coarse_end=[(l+r)//2,t+(b-t)//5], minimum_target=minimum)
        for field in ('from', 'to'):
            assert type(value[field]) is list and len(value[field]) == 2
            assert all(type(v) is int for v in value[field])
        assert value['from'] == start and value['to'] == end
    return True


def navigation(xml, package, *, conversation, selected=None, browser=False, density_evidence=None):
    assert type(conversation) is bool and type(browser) is bool
    assert type(package) is str and package.endswith('.test')
    if not conversation:
        # The five management destinations retain their own v2 native layout.
        return workspace_navigation(xml, package, conversation=False, selected=selected, browser=browser)
    assert selected is None
    tree = ET.fromstring(xml)
    nodes = list(tree.iter('node'))
    parents = {child: parent for parent in tree.iter() for child in parent}
    descriptions = ('后退', '打开当前环境主页', None, ('刷新网页', '停止加载'), '浏览器菜单')
    names = ('back', 'home', 'address', 'reload', 'menu')
    controls, actual = [], []
    for name, description in zip(names, descriptions):
        matches = [n for n in nodes if n.get('package') == package
                   and n.get('class') == 'android.widget.Button'
                   and (n.get('content-desc', '').startswith('当前网址 ') if name == 'address'
                        else n.get('content-desc') in description if isinstance(description, tuple)
                        else n.get('content-desc') == description)]
        assert len(matches) == 1, ('Missing or ambiguous native browser control', name)
        node = matches[0]
        assert node.get('clickable') == 'true' and node.get('visible-to-user') != 'false'
        assert node.get('enabled') in (('true', 'false') if name == 'back' else ('true',))
        if name == 'address':
            assert re.fullmatch(r'当前网址 .+，点击输入网址或搜索', node.get('content-desc', ''))
        box = bounds(node)
        actual.append(node)
        controls.append(dict(name=name, label=name, description=node.get('content-desc'),
                             bounds=box, point=center(box), enabled=node.get('enabled') == 'true'))
    row = parents[actual[0]]
    assert row.get('package') == package and row.get('class') == 'android.view.ViewGroup'
    assert all(parents[n] is row for n in actual) and list(row) == actual, 'Browser controls must share their actual five-child toolbar'
    rl, rt, rr, rb = bounds(row)
    for child in actual:
        l, t, r, b = bounds(child)
        assert rl <= l < r <= rr and rt <= t < b <= rb, 'Browser target is outside its native toolbar'
    ancestor = row
    while parents.get(ancestor) is not None and parents[ancestor].tag == 'node':
        ancestor = parents[ancestor]
        assert ancestor.get('package') == package and ancestor.get('visible-to-user') != 'false'
        al, at, ar, ab = bounds(ancestor)
        assert al <= rl < rr <= ar and at <= rt < rb <= ab, 'Browser toolbar is clipped by its native window'
    back, home, address, reload, menu = [c['bounds'] for c in controls]
    action_boxes = (back, home, reload, menu)
    assert len({(b[1], b[3]) for b in action_boxes}) == 1
    assert len({(b[2]-b[0], b[3]-b[1]) for b in action_boxes}) == 1
    action_size = back[2]-back[0]
    assert action_size == back[3]-back[1]
    density = display_density(density_evidence)
    minimum = minimum_touch_pixels(density_evidence)
    assert action_size == minimum, 'Native browser action must retain the actual 48 dp target'
    assert address[2]-address[0] >= minimum and address[3]-address[1] >= minimum
    assert all(a[2] <= b[0] for a, b in zip(action_boxes, action_boxes[1:])), 'Browser actions overlap or reorder'
    if address[3] <= back[1]:
        layout = 'stacked'
        assert address[0] == back[0] and address[2] == menu[2]
        assert rr-rl < (4*48+2*4+72+8)*density, 'An ordinary-width browser must not stack its address'
    else:
        layout = 'inline'
        assert home[2] < address[0] < address[2] < reload[0]
        assert abs(address[1]+address[3]-back[1]-back[3]) <= 1
    assert not any(n.get('package') == package and n.get('class') == 'android.widget.Button'
                   and n.get('text') == n.get('content-desc') and n.get('text') in ('环境', '网络', '下载', '阅读')
                   and bounds(n)[1] >= rt for n in parents[row].iter('node')), 'Retired management dock is still visible in the native browser footer'
    return dict(navigationContract=VERSION, conversation=True, controls=controls,
                toolbarBounds=[rl, rt, rr, rb], addressLayout=layout, density=density)


def conversation_header(xml, package, width, height, scale, environment, *, browser=False):
    result = navigation(xml, package, conversation=True, browser=browser)
    nodes = list(ET.fromstring(xml).iter('node'))
    capsules = [n for n in nodes if n.get('package') == package and n.get('content-desc', '').startswith('当前环境：')]
    assert len(capsules) == 1
    capsule = capsules[0]
    assert capsule.get('content-desc') == f'当前环境：{environment}，点按输入网址，长按切换环境'
    assert capsule.get('class') == 'android.widget.Button'
    assert capsule.get('clickable') == capsule.get('long-clickable') == 'true'
    assert not any(n.get('package') == package and n.get('content-desc', '').startswith('当前环境网络：') for n in nodes)
    assert not any(n.get('package') == package and n.get('content-desc') in ('管理环境', '更多') for n in nodes)
    l, t, r, b = bounds(capsule)
    assert 0 <= l < r <= width*3 and 0 <= t < b < result['toolbarBounds'][1] < height*3
    assert b-t >= 48*3 and abs(result['density']-3) < .01
    for control in result['controls']:
        cl, ct, cr, cb = control['bounds']
        assert 0 <= cl < cr <= width*3 and b < ct < cb <= height*3
        assert cr-cl >= 48*3 and cb-ct >= 48*3
    result.update(environment=environment, capsuleBounds=[l,t,r,b],
                  addressTapAndEnvironmentLongPressDescribed=True, networkStatusInMenu=True)
    return result


def captured_observation(xml, capture):
    encoded = xml.encode('utf-8')
    row = capture.report['attempts'][-1]
    assert row['status'] == 'captured' and row['xmlBytes'] == len(encoded)
    assert row['xmlSha256'] == hashlib.sha256(encoded).hexdigest()
    return dict(rawXml=xml, xmlBytes=len(encoded), xmlSha256=row['xmlSha256'], captureIndex=row['index'])


def verify_workspace_roundtrip(record, package, *, source=None, root=None):
    """Re-read actual XML, Android density and the original observer receipts."""
    if __package__:
        from . import ui_hierarchy_driver as driver
    else:
        import ui_hierarchy_driver as driver
    assert type(record['schema']) is int and record['schema'] == 1
    assert type(record['navigationContract']) is int and record['navigationContract'] == VERSION
    source = record['sourceCommit'] if source is None else source
    assert record['sourceCommit'] == source
    capture = record['hierarchyCapture']
    assert capture['sourceCommit'] == source
    evidence = capture['acquisitionDriver']
    driver.verify_evidence(evidence, source, root=root)
    assert record['sourceTree'] == evidence['sourceTree']
    assert capture['serial'] == evidence['serial']
    nonce = capture['runNonce']
    assert type(nonce) is str and re.fullmatch('[0-9a-f]{32}', nonce)
    attempts = capture['attempts']
    assert type(attempts) is list and 0 < len(attempts) <= 256
    for field in ('attemptCount', 'droppedAttempts'):
        assert type(capture[field]) is int and capture[field] >= 0
    assert capture['attemptCount'] == len(attempts)+capture['droppedAttempts']
    assert [a['index'] for a in attempts] == list(range(capture['droppedAttempts']+1, capture['attemptCount']+1))
    rows = {a['index']: a for a in attempts}

    def raw_observation(value, *, budget=20):
        xml = value['rawXml']
        assert type(xml) is str and 0 < len(xml.encode('utf-8')) <= 1024*1024
        raw = xml.encode('utf-8'); digest = hashlib.sha256(raw).hexdigest()
        assert type(value['xmlBytes']) is int and value['xmlBytes'] == len(raw)
        assert value['xmlSha256'] == digest and type(value['captureIndex']) is int
        row = rows[value['captureIndex']]
        assert row['status'] == 'captured' and row['xmlBytes'] == len(raw) and row['xmlSha256'] == digest
        remote = '/sdcard/pocketchat-ui-visual-'+nonce+'-'+str(row['index'])+'.xml'
        assert row['remotePath'] == remote
        start, end = row['startedAtMonotonicNanos'], row['completedAtMonotonicNanos']
        deadline = row['existingSceneDeadline']
        assert type(start) is type(end) is int and 0 < start < end
        assert type(deadline) in (int, float) and math.isfinite(deadline)
        assert start/1e9 < end/1e9 < deadline and deadline-start/1e9 <= budget
        commands = row['commands']; assert type(commands) is list and len(commands) == 2
        previous = start
        for index, command in enumerate(commands):
            cs, ce = command['startedAtMonotonicNanos'], command['completedAtMonotonicNanos']
            assert type(cs) is type(ce) is int and previous <= cs < ce <= end
            previous = ce
            timeout = command['timeoutSeconds']
            assert type(timeout) in (int, float) and math.isfinite(timeout) and 0 < timeout <= min(90, deadline-start/1e9)
            assert type(command['exitCode']) is int and command['exitCode'] == 0
            parts = command['parts']
            if index == 0:
                assert len(parts) == 13 and type(parts[6]) is str and re.fullmatch('[1-9][0-9]*', parts[6])
                millis = int(parts[6]); assert 0 < millis <= min(90000, math.ceil((deadline-start/1e9)*1000))
                assert parts == ['shell', 'CLASSPATH='+evidence['installedJar']['remotePath']+':'+driver.SYSTEM_JAR,
                    'app_process', '/system/bin', driver.ENTRY_POINT, remote, str(millis),
                    evidence['installedJar']['sha256'], source, evidence['sourceTree'], evidence['runId'],
                    evidence['runAttempt'], evidence['device']['systemJarSha256']]
                stdout = ('UI hierchary dumped to: '+remote+'\n').encode()
            else:
                assert parts == ['shell', 'cat', remote]
                stdout = raw
            for field, data in (('stdout', stdout), ('stderr', b'')):
                expected = dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest(),
                                text=data[:8192].decode('utf-8', 'replace'), truncated=len(data)>8192)
                actual = command[field]
                assert type(actual['bytes']) is int and type(actual['truncated']) is bool
                assert actual == expected, 'Native observation output differs from its original command'
        return xml

    native = record['nativeUi']
    assert set(native) == {'initial', 'menu', 'environments', 'chat'}
    xml = {name: raw_observation(native[name], budget=30 if name == 'initial' else 20)
           for name in ('initial', 'menu', 'environments', 'chat')}
    indexes = [native[name]['captureIndex'] for name in ('initial', 'menu', 'environments', 'chat')]
    assert all(a < b for a, b in zip(indexes, indexes[1:])), 'Roundtrip observations must keep their real acquisition order'
    density = record['densityEvidence']
    minimum = minimum_touch_pixels(density)
    initial = navigation(xml['initial'], package, conversation=True, browser=True, density_evidence=density)
    final = navigation(xml['chat'], package, conversation=True, browser=True, density_evidence=density)
    workspace = navigation(xml['environments'], package, conversation=False, selected='环境', browser=True)
    assert record['initial'] == initial and record['observations'] == [workspace, final]
    def capsule(raw):
        nodes = [n for n in ET.fromstring(raw).iter('node') if n.get('package') == package
                 and n.get('content-desc', '').startswith('当前环境：')]
        assert len(nodes) == 1 and nodes[0].get('class') == 'android.widget.Button'
        assert nodes[0].get('clickable') == nodes[0].get('long-clickable') == 'true'
        return nodes[0].get('content-desc')
    assert capsule(xml['initial']) == capsule(xml['chat'])
    management = menu_action(xml['menu'], package, '管理全部环境')
    assert min(management['bounds'][2]-management['bounds'][0], management['bounds'][3]-management['bounds'][1]) >= minimum
    menu_tree = ET.fromstring(xml['menu'])
    parents = {child: parent for parent in menu_tree.iter() for child in parent}
    target = next(n for n in menu_tree.iter('node') if n.get('package') == package
                  and n.get('class') == 'android.widget.Button' and n.get('text') == '管理全部环境')
    l, t, r, b = bounds(target)
    scroll_ancestors = 0
    while parents.get(target) is not None and parents[target].tag == 'node':
        target = parents[target]
        assert target.get('package') == package and target.get('visible-to-user') != 'false'
        al, at, ar, ab = bounds(target)
        assert al <= l < r <= ar and at <= t < b <= ab, 'Management action is clipped by its native menu'
        if target.get('class') == 'android.widget.ScrollView':
            assert target.get('scrollable') == 'true'
            scroll_ancestors += 1
    assert scroll_ancestors == 1, 'Management action must belong to the actual browser menu scroller'
    verify_menu_scrolls(record['menuScrolls'], package, '管理全部环境', density_evidence=density)
    for scroll in record['menuScrolls']:
        matching = [row for row in attempts if row.get('status') == 'captured' and row.get('xmlSha256') == scroll['xmlSha256']
                    and indexes[0] < row['index'] < indexes[1]]
        assert matching, 'Menu scroll must refer to an original native hierarchy in this phase'
        raw_observation(dict(rawXml=scroll['rawXml'], xmlBytes=len(scroll['rawXml'].encode('utf-8')),
                             xmlSha256=scroll['xmlSha256'], captureIndex=matching[-1]['index']))
    targets = [initial['controls'][-1], management, next(row for row in workspace['controls'] if row['label'] == '浏览器')]
    inputs = record['inputs']; assert type(inputs) is list and len(inputs) == 3
    for index, (item, target, label) in enumerate(zip(inputs, targets, ('浏览器菜单', '管理全部环境', '浏览器'))):
        assert item['label'] == label and item['actualAndroidTap'] is True
        assert item['bounds'] == target['bounds'] and item['point'] == center(target['bounds'])
        assert item['captureIndex'] == indexes[index]
        started = item['startedAtMonotonicNanos']; assert type(started) is int
        assert rows[indexes[index]]['completedAtMonotonicNanos'] <= started < rows[indexes[index+1]]['startedAtMonotonicNanos']
    assert type(record['actualAndroidTaps']) is int and record['actualAndroidTaps'] == 3
    for field in ('browserWorkspace', 'allFiveWorkspaceDestinationsVisible', 'returnedToSameEnvironment'):
        assert record[field] is True
    return dict(schema=1, navigationContract=VERSION, sourceCommit=source, sourceTree=evidence['sourceTree'],
                runId=evidence['runId'], runAttempt=evidence['runAttempt'],
                densityDpi=density['effectiveDpi'], minimumActionTouchDp=48, minimumActionTouchPx=minimum,
                actualAndroidTaps=3)


def exercise_workspace_roundtrip(adb, initial_xml, save, package, *, browser=False, capture):
    """Enter management through the actual menu, then return to the live browser."""
    assert browser is True, 'The v3 product uses direct browser entry'
    density = display_density_evidence(adb('shell', 'wm', 'density'))
    initial = navigation(initial_xml, package, conversation=True, browser=True, density_evidence=density)
    native = dict(initial=captured_observation(initial_xml, capture))
    capsule = [n.get('content-desc') for n in ET.fromstring(initial_xml).iter('node')
               if n.get('package') == package and n.get('content-desc', '').startswith('当前环境：')]
    assert len(capsule) == 1
    receipts, observations = [], []

    def tap(target, label):
        point = center(target['bounds'])
        started = time.monotonic_ns()
        adb('shell', 'input', 'tap', *map(str, point))
        receipts.append(dict(label=label, point=point, bounds=target['bounds'], actualAndroidTap=True,
                             captureIndex=capture.report['attempts'][-1]['index'], startedAtMonotonicNanos=started))

    menu_scrolls=[]

    def read_frame(*, deadline):
        xml = capture.read(deadline=deadline)
        assert time.monotonic() < deadline, 'Original native navigation budget expired'
        return xml

    def observe(name, reader):
        deadline=time.monotonic()+20
        while time.monotonic() < deadline:
            xml=read_frame(deadline=deadline)
            try:
                value=reader(xml)
            except AssertionError:
                if time.monotonic() >= deadline: raise
                time.sleep(min(.2,max(0,deadline-time.monotonic())))
                continue
            save('production-navigation-'+name+'.xml',xml)
            assert time.monotonic() < deadline, 'Original native navigation budget expired after save'
            return xml,value
        raise TimeoutError(('Native navigation observation expired',name))

    tap(initial['controls'][-1], '浏览器菜单')
    deadline=time.monotonic()+20
    xml,target=seek_menu_action(adb,read_frame,package,'管理全部环境',deadline=deadline,scrolls=menu_scrolls,density_evidence=density)
    save('production-navigation-menu.xml',xml)
    assert time.monotonic() < deadline, 'Original native menu budget expired after save'
    native['menu'] = captured_observation(xml, capture)
    assert time.monotonic() < deadline, 'Original native menu budget expired before input'
    tap(target, '管理全部环境')
    xml, workspace = observe('environments', lambda xml: navigation(xml, package, conversation=False, selected='环境', browser=True))
    native['environments'] = captured_observation(xml, capture)
    observations.append(workspace)
    target = next(row for row in workspace['controls'] if row['label'] == '浏览器')
    tap(target, '浏览器')
    xml, final = observe('chat', lambda xml: navigation(xml, package, conversation=True, browser=True,density_evidence=density))
    native['chat'] = captured_observation(xml, capture)
    assert [n.get('content-desc') for n in ET.fromstring(xml).iter('node')
            if n.get('package') == package and n.get('content-desc', '').startswith('当前环境：')] == capsule
    observations.append(final)
    result = dict(schema=1, navigationContract=VERSION, actualAndroidTaps=3, inputs=receipts, browserWorkspace=True,
                initial=initial, observations=observations, menuScrolls=menu_scrolls, allFiveWorkspaceDestinationsVisible=True,
                returnedToSameEnvironment=True, densityEvidence=density, nativeUi=native,
                sourceCommit=capture.report['sourceCommit'], sourceTree=capture.report['acquisitionDriver']['sourceTree'],
                hierarchyCapture=json.loads(json.dumps(capture.report)))
    return result
