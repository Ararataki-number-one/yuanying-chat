"""Read and exercise the native navigation introduced by the five-page UI.

Conversation has three destinations and a separate reading control. Management
screens have five destinations. All observations use the unmodified Android XML.
"""
import re
import time
import xml.etree.ElementTree as ET

VERSION = 2
WORKSPACE_LABELS = ('会话', '环境', '下载', '网络', '设置')
BROWSER_WORKSPACE_LABELS = ('浏览器', '环境', '下载', '网络', '设置')
CONVERSATION_LABELS = ('环境', '网络', '下载', '阅读')


def bounds(node):
    match = re.fullmatch(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', node.attrib.get('bounds', ''))
    assert match is not None, ('Missing native bounds', node.attrib)
    left, top, right, bottom = map(int, match.groups())
    assert left < right and top < bottom, ('Invisible native control', node.attrib)
    return [left, top, right, bottom]


def navigation(xml, package, *, conversation, selected=None, browser=False):
    assert type(browser) is bool
    assert type(conversation) is bool and type(package) is str and package.endswith('.test')
    tree = ET.fromstring(xml)
    labels = CONVERSATION_LABELS if conversation else (BROWSER_WORKSPACE_LABELS if browser else WORKSPACE_LABELS)
    parents = {child: parent for parent in tree.iter() for child in parent}
    controls = []
    for label in labels:
        description = '进入专注阅读模式' if conversation and label == '阅读' else label
        matches = [n for n in tree.iter('node')
                   if n.attrib.get('package') == package
                   and n.attrib.get('class') == 'android.widget.Button'
                   and n.attrib.get('text') == label
                   and n.attrib.get('content-desc') == description]
        assert len(matches) == 1, ('Missing or ambiguous native navigation', label)
        node = matches[0]
        assert node.attrib.get('enabled') == node.attrib.get('clickable') == 'true', node.attrib
        rectangle = bounds(node)
        assert node.attrib.get('selected') == ('true' if label == selected else 'false'), node.attrib
        controls.append(dict(label=label, description=description, bounds=rectangle,
                             selected=node.attrib['selected'] == 'true'))
    nodes = [next(n for n in tree.iter('node') if n.attrib.get('package') == package
                  and n.attrib.get('class') == 'android.widget.Button'
                  and n.attrib.get('text') == row['label']
                  and n.attrib.get('content-desc') == row['description']) for row in controls]
    destinations = nodes[:-1] if conversation else nodes
    assert len({parents[n] for n in destinations}) == 1, 'Destinations must share the actual native dock'
    if conversation:
        assert parents[nodes[-1]] is not parents[nodes[0]], 'Reading must remain a separate mode control'
        assert not any(n.attrib.get('package') == package
                       and n.attrib.get('class') == 'android.widget.Button'
                       and n.attrib.get('text') == n.attrib.get('content-desc')
                       and n.attrib.get('text') in ('会话', '浏览器', '设置') for n in tree.iter('node'))
    ordered = controls[:-1] if conversation else controls
    for a, b in zip(ordered, ordered[1:]):
        assert a['bounds'][2] <= b['bounds'][0], 'Native navigation touch areas overlap or reorder'
        assert max(a['bounds'][1], b['bounds'][1]) < min(a['bounds'][3], b['bounds'][3]), 'Native navigation labels do not share a row'
    if conversation:
        conversation_layout(nodes, parents, package)
    return dict(navigationContract=VERSION, conversation=conversation, controls=controls)


def conversation_layout(nodes, parents, package):
    """Read the two exact layouts produced by native GlassNavigationRow.

    Its three destinations stay on one centered dock. The independent square
    reading control either shares that row or occupies the trailing position
    below it when the native labels cannot fit beside that control.
    """
    dock, reading = parents[nodes[0]], parents[nodes[-1]]
    row = parents.get(dock)
    assert row is not None and parents.get(reading) is row, 'Reading and dock must share their actual native row'
    assert list(row) == [dock, reading] and list(dock) == nodes[:-1] and list(reading) == nodes[-1:], 'Unexpected native navigation children'
    for element, kind in ((row, 'android.view.ViewGroup'), (dock, 'android.widget.LinearLayout'),
                          (reading, 'android.widget.FrameLayout')):
        assert element.attrib.get('package') == package and element.attrib.get('class') == kind, 'Navigation container belongs to another native view'
    rl, rt, rr, rb = bounds(row)
    dl, dt, dr, db = bounds(dock)
    left, top, right, bottom = bounds(reading)
    assert bounds(nodes[-1]) == [left, top, right, bottom], 'Reading must fill its own native mode surface'
    assert 0 <= rl + rr - dl - dr <= 1, 'Destination dock must remain centered on its native row'
    assert dt == rt and right == rr, 'Native dock or reading alignment differs'
    height = db - dt
    assert right - left == bottom - top == height, 'Reading must retain the native square touch surface'
    for node in nodes[:-1]:
        l, t, r, b = bounds(node)
        assert dl <= l < r <= dr and dt <= t < b <= db, 'Destination is clipped by its native dock'
    assert len({(bounds(node)[1], bounds(node)[3]) for node in nodes[:-1]}) == 1, 'Destination labels must keep the same native row'
    # Check real ancestor bounds as well as the explicit viewport/48 dp checks
    # kept by the caller; a second row cannot authorize an offscreen control.
    for child in (dock, reading):
        cl, ct, cr, cb = bounds(child)
        assert rl <= cl < cr <= rr and rt <= ct < cb <= rb, 'Navigation surface is clipped by its native row'
    ancestor = row
    while parents.get(ancestor) is not None and parents[ancestor].tag == 'node':
        ancestor = parents[ancestor]
        assert ancestor.attrib.get('package') == package, 'Navigation row has a foreign owner'
        al, at, ar, ab = bounds(ancestor)
        assert al <= rl < rr <= ar and at <= rt < rb <= ab, 'Navigation row is outside the actual window'
    if top == dt:
        assert left > dr and bottom == db == rb, 'Inline reading must be separate and share the destination row'
        return 'inline'
    gap = top - db
    assert gap > 0 and bottom == rb and rb - rt == 2 * height + gap, 'Stacked reading must be the distinct second native row'
    assert dr - dl > rr - rl - 2 * (height + gap), 'Reading cannot be stacked while the destination dock fits inline'
    return 'stacked'


def conversation_header(xml, package, width, height, scale, environment, *, browser=False):
    result = navigation(xml, package, conversation=True, browser=browser)
    tree = ET.fromstring(xml)
    nodes = list(tree.iter('node'))
    capsule = [n for n in nodes if n.attrib.get('package') == package
               and n.attrib.get('content-desc', '').startswith('当前环境：')]
    status = [n for n in nodes if n.attrib.get('package') == package
              and n.attrib.get('content-desc', '').startswith('当前环境网络：')]
    assert len(capsule) == len(status) == 1, 'One current environment and one network status are required'
    capsule, status = capsule[0], status[0]
    assert capsule.attrib.get('content-desc') == f'当前环境：{environment}，点按输入网址，长按切换环境'
    assert capsule.attrib.get('class') == 'android.widget.Button'
    assert capsule.attrib.get('clickable') == capsule.attrib.get('long-clickable') == 'true'
    assert status.attrib.get('clickable') == status.attrib.get('focusable') == 'false'
    if not browser:
        assert not any(n.attrib.get('content-desc') in ('管理环境', '更多') for n in nodes)
    assert not any(n.attrib.get('text') in ('简洁', '原网页') for n in nodes)
    left, top, right, bottom = bounds(capsule)
    nl, nt, nr, nb = bounds(status)
    assert 0 <= left < right <= width * 3 and 0 <= nl < nr <= width * 3
    if browser:
        assert capsule.get('text') == environment, 'Current environment name must remain complete'
        result.update(browser_header_controls(tree, package, capsule, status, width, height))
        assert 0 <= top < bottom < nt < nb <= height * 3
    else:
        assert 0 <= top < bottom == nt < nb <= height * 3
    # The redesigned capsule includes a full 48 dp native touch target; the old
    # 28 dp visual-only bound no longer describes this accessibility control.
    assert 48 * 3 <= bottom - top
    if not browser:
        assert bottom - top <= max(56, 40 * scale) * 3
    for row in result['controls']:
        l, t, r, b = row['bounds']
        assert r-l >= 48*3 and b-t >= 48*3
        assert 0 <= l < r <= width*3 and nb <= t < b <= height*3
    result.update(environment=environment, capsuleBounds=[left, top, right, bottom],
                  networkBounds=[nl, nt, nr, nb], addressTapAndEnvironmentLongPressDescribed=True)
    return result


def browser_header_controls(tree, package, capsule, status, width, height):
    """Observe the native browser header; the legacy contract stays the default.

    BrowserAddressRow has two layouts, both read from their actual Android
    children and bounds. History actions may be disabled when no entry exists.
    Other actions must be enabled; all touch surfaces remain at least 48 dp.
    """
    nodes = list(tree.iter('node'))
    parents = {child: parent for parent in tree.iter() for child in parent}

    def owned(node, kind, action=False, history=False):
        assert node.get('package') == package and node.get('class') == kind, 'Foreign browser header control'
        assert node.get('visible-to-user') != 'false', 'Hidden browser header control'
        l, t, r, b = bounds(node)
        assert 0 <= l < r <= width * 3 and 0 <= t < b <= height * 3, 'Browser header outside viewport'
        if action:
            assert node.get('clickable') == 'true', 'Browser action is not clickable'
            assert node.get('enabled') in (('true', 'false') if history else ('true',)), 'Browser action is inactive'
            assert r-l >= 144 and b-t >= 144, 'Browser action is smaller than 48 dp'
        ancestor = node
        while parents.get(ancestor) is not None and parents[ancestor].tag == 'node':
            ancestor = parents[ancestor]
            assert ancestor.get('package') == package and ancestor.get('visible-to-user') != 'false', 'Foreign or hidden browser ancestor'
            al, at, ar, ab = bounds(ancestor)
            assert al <= l < r <= ar and at <= t < b <= ab, 'Browser control is clipped by its native ancestor'
        return node

    def action(descriptions, history=False):
        matches = [n for n in nodes if n.get('content-desc') in descriptions]
        assert len(matches) == 1, ('Missing or ambiguous browser action', descriptions)
        return owned(matches[0], 'android.widget.Button', True, history)

    address = [n for n in nodes if n.get('content-desc', '').startswith('当前网址 ')]
    assert len(address) == 1, 'One native current address is required'
    address = owned(address[0], 'android.widget.Button', True)
    assert re.fullmatch(r'当前网址 .+，点击输入网址或搜索', address.get('content-desc', '')), 'Address editing semantics missing'
    assert address.get('long-clickable') == 'true', 'Address must retain environment long press'
    back, forward = action(('后退',), True), action(('前进',), True)
    reload = action(('刷新网页', '停止加载'))
    home = action(('打开当前环境主页',))
    manage, more = action(('管理环境',)), action(('更多',))
    owned(capsule, 'android.widget.Button', True)
    owned(status, 'android.widget.LinearLayout')
    actions = [back, forward, reload, home]
    row = owned(parents[address], 'android.view.ViewGroup')
    assert all(parents[n] is row for n in actions), 'Browser address actions have different native parents'
    rl, rt, rr, rb = bounds(row)
    al, at, ar, ab = bounds(address)
    action_bounds = [bounds(n) for n in actions]
    assert all(r-l == b-t == 144 for l, t, r, b in action_bounds), 'Browser history and load actions must retain their square surfaces'
    assert len({(t, b) for l, t, r, b in action_bounds}) == 1, 'Browser actions must share a row'
    for a, b in zip(action_bounds, action_bounds[1:]):
        assert a[2] <= b[0], 'Browser actions overlap or reorder'
    assert action_bounds[0][0] == rl and action_bounds[0][2] == action_bounds[1][0]
    assert action_bounds[2][2] == action_bounds[3][0] and action_bounds[3][2] == rr
    if list(row) == [address, back, forward, reload, home]:
        layout = 'stacked'
        assert (al, ar) == (rl, rr) and at == rt+9, 'Stacked address must fill its native first row'
        assert action_bounds[0][1] == ab+12 and action_bounds[0][3]+21 == rb, 'Stacked browser actions must occupy the native second row'
    else:
        layout = 'inline'
        assert list(row) == [back, forward, address, reload, home], 'Unexpected browser address children'
        assert action_bounds[1][2] == al and ar == action_bounds[2][0], 'Inline address overlaps its actions'
        assert abs(at+ab-action_bounds[0][1]-action_bounds[0][3]) <= 1, 'Inline address must share the action center'
        assert min(at, action_bounds[0][1]) == rt+9 and max(ab, action_bounds[0][3])+21 == rb
    hosts = [parents[n] for n in (manage, capsule, more)]
    for host, child in zip(hosts, (manage, capsule, more)):
        owned(host, 'android.widget.FrameLayout')
        assert list(host) == [child], 'Unexpected browser header action host'
    header = owned(parents[hosts[0]], 'android.widget.LinearLayout')
    assert list(header) == hosts and all(parents[h] is header for h in hosts), 'Browser header must retain its native three surfaces'
    hl, ht, hr, hb = bounds(header)
    cl, ct, cr, cb = bounds(capsule)
    ml, mt, mr, mb = bounds(manage)
    ol, ot, ore, ob = bounds(more)
    assert ml < mr <= cl < cr <= ol < ore, 'Browser header surfaces overlap or reorder'
    assert abs(cl+cr-hl-hr) <= 1, 'Environment capsule is not centered'
    assert abs(ct+cb-mt-mb) <= 1 and abs(ct+cb-ot-ob) <= 1, 'Browser header actions must share a vertical center'
    assert parents[header] is parents[row] is parents[status], 'Browser header, address and status must share their native toolbar'
    assert hl == rl == bounds(status)[0] and hr == rr == bounds(status)[2]
    assert hb == rt and rb == bounds(status)[1], 'Browser toolbar sections must keep their native order'
    return dict(browserWorkspace=True, addressLayout=layout, addressBounds=bounds(address),
                browserActionBounds={n.get('content-desc'): bounds(n) for n in actions+[manage, more]})


def dashboard_entry(xml, package, environment):
    """Read the actual dashboard header and its sole native entry button."""
    assert type(package) is str and package.endswith('.test')
    assert type(environment) is str and environment
    tree = ET.fromstring(xml)
    dashboards = [n for n in tree.iter('node')
                  if n.attrib.get('content-desc') == '环境仪表盘']
    assert len(dashboards) == 1, 'One native environment dashboard is required'

    def owner(node, kind):
        assert node.attrib.get('package') == package, 'Dashboard belongs to another package'
        assert node.attrib.get('class') == 'android.widget.' + kind, node.attrib
        return node

    dashboard = owner(dashboards[0], 'LinearLayout')
    children = list(dashboard)
    assert len(children) == 2, 'Dashboard must retain its scroll body and entry footer'
    scroll, footer = owner(children[0], 'ScrollView'), owner(children[1], 'LinearLayout')
    assert len(scroll) == 1
    centered = owner(scroll[0], 'FrameLayout')
    assert len(centered) == 1
    body = owner(centered[0], 'LinearLayout')
    assert len(body) > 0
    header = owner(body[0], 'LinearLayout')
    assert len(header) == 2, 'Dashboard header must contain its slot badge and name'
    badge, title = owner(header[0], 'TextView'), owner(header[1], 'TextView')
    assert re.fullmatch(r'[0-9]{2,}', badge.attrib.get('text', ''))
    assert int(badge.attrib['text']) > 0
    assert title.attrib.get('text') == environment, 'Dashboard opened another environment'
    entries = [n for n in tree.iter('node') if n.attrib.get('text') == '进入聊天']
    assert len(entries) == len(footer) == 1 and entries[0] is footer[0], 'One actual footer entry is required'
    button = owner(entries[0], 'Button')
    assert button.attrib.get('content-desc', '') == ''
    assert button.attrib.get('enabled') == button.attrib.get('clickable') == 'true', button.attrib
    dl, dt, dr, db = bounds(dashboard)
    for node in (header, title, footer, button):
        l, t, r, b = bounds(node)
        assert dl <= l < r <= dr and dt <= t < b <= db, 'Dashboard control is clipped'
    l, t, r, b = bounds(button)
    fl, ft, fr, fb = bounds(footer)
    assert fl <= l < r <= fr and ft <= t < b <= fb, 'Entry must remain inside its native footer'
    return dict(environment=environment, environmentBadge=badge.attrib['text'],
                dashboardBounds=[dl, dt, dr, db], headerBounds=bounds(title),
                buttonBounds=[l, t, r, b], point=[(l+r)//2, (t+b)//2])


def exercise_workspace_roundtrip(adb, initial_xml, save, package, *, browser=False):
    """Exercise the explicitly selected legacy or direct-browser entry contract."""
    initial = navigation(initial_xml, package, conversation=True, browser=browser)
    original_capsule = [n.attrib['content-desc'] for n in ET.fromstring(initial_xml).iter('node')
                        if n.attrib.get('content-desc', '').startswith('当前环境：')]
    assert len(original_capsule) == 1
    capsule = re.fullmatch(r'当前环境：(.+)，点按输入网址，长按切换环境', original_capsule[0])
    assert capsule is not None, 'Current environment identity is required'
    environment = capsule.group(1)
    observed = []
    for label, conversation, selected in (('环境', False, '环境'), ('浏览器' if browser else '会话', True, None)):
        before = initial if not observed else observed[-1]
        target = next(row for row in before['controls'] if row['label'] == label)
        l, t, r, b = target['bounds']
        point = [(l+r)//2, (t+b)//2]
        adb('shell', 'input', 'tap', *map(str, point))
        deadline = time.monotonic()+20

        def read_frame():
            remote = '/sdcard/gecko-navigation-v2.xml'
            while True:
                assert time.monotonic() < deadline, 'Native navigation exceeded its original 20 second budget'
                # One remote shell command preserves stderr and removes the old
                # file before this attempt; never read a previous hierarchy.
                dumped = adb('shell', 'rm -f ' + remote + ' && uiautomator dump ' + remote + ' 2>&1')
                print(dumped, end='', flush=True)  # Preserve actual acquisition output in the CI log.
                assert time.monotonic() < deadline, 'Native navigation exceeded its original 20 second budget'
                if dumped.strip() == 'ERROR: null root node returned by UiTestAutomationBridge.':
                    remaining = deadline - time.monotonic()
                    assert remaining > 0, 'Native navigation exceeded its original 20 second budget'
                    time.sleep(min(.2, remaining))
                    continue
                assert dumped.strip() == 'UI hierchary dumped to: ' + remote, ('Unexpected native hierarchy dump output', dumped)
                break
            xml = adb('shell', 'cat', '/sdcard/gecko-navigation-v2.xml')
            assert time.monotonic() < deadline, 'Native navigation exceeded its original 20 second budget'
            return xml

        entry = None
        if conversation and not browser:
            while True:
                xml = read_frame()
                if any(n.attrib.get('content-desc') == '环境仪表盘'
                       for n in ET.fromstring(xml).iter('node')):
                    entry = dashboard_entry(xml, package, environment)
                    break
                time.sleep(.2)
            save('production-navigation-dashboard.xml', xml)
            assert time.monotonic() < deadline, 'Dashboard entry exceeded its original 20 second budget'
            adb('shell', 'input', 'tap', *map(str, entry['point']))
            entry['actualAndroidTap'] = dict(label='进入聊天', point=entry['point'], bounds=entry['buttonBounds'])
            # The dashboard and final conversation share the original chat deadline.
        while True:
            xml = read_frame()
            try:
                if browser and conversation:
                    assert not any(n.get('content-desc') == '环境仪表盘' for n in ET.fromstring(xml).iter('node')), 'Direct browser entry opened an environment dashboard'
                value = navigation(xml, package, conversation=conversation, selected=selected, browser=browser)
                break
            except AssertionError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(.2)
        save('production-navigation-' + ('chat' if conversation else 'environments') + '.xml', xml)
        if conversation:
            assert [n.attrib['content-desc'] for n in ET.fromstring(xml).iter('node')
                    if n.attrib.get('content-desc', '').startswith('当前环境：')] == original_capsule
        assert time.monotonic() < deadline, 'Native navigation exceeded its original 20 second budget'
        value.update(actualAndroidTap=dict(label=label, point=point, bounds=target['bounds']))
        if entry is not None:
            value['dashboardEntry'] = entry
        observed.append(value)
    return dict(navigationContract=VERSION, actualAndroidTaps=2 if browser else 3, browserWorkspace=browser, initial=initial,
                observations=observed, allFiveWorkspaceDestinationsVisible=True,
                returnedToSameEnvironment=True)
