"""Read and exercise the native navigation introduced by the five-page UI.

Conversation has three destinations and a separate reading control. Management
screens have five destinations. All observations use the unmodified Android XML.
"""
import re
import time
import xml.etree.ElementTree as ET

VERSION = 2
WORKSPACE_LABELS = ('会话', '环境', '下载', '网络', '设置')
CONVERSATION_LABELS = ('环境', '网络', '下载', '阅读')


def bounds(node):
    match = re.fullmatch(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', node.attrib.get('bounds', ''))
    assert match is not None, ('Missing native bounds', node.attrib)
    left, top, right, bottom = map(int, match.groups())
    assert left < right and top < bottom, ('Invisible native control', node.attrib)
    return [left, top, right, bottom]


def navigation(xml, package, *, conversation, selected=None):
    assert type(conversation) is bool and type(package) is str and package.endswith('.test')
    tree = ET.fromstring(xml)
    labels = CONVERSATION_LABELS if conversation else WORKSPACE_LABELS
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
                       and n.attrib.get('text') in ('会话', '设置') for n in tree.iter('node'))
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


def conversation_header(xml, package, width, height, scale, environment):
    result = navigation(xml, package, conversation=True)
    nodes = list(ET.fromstring(xml).iter('node'))
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
    assert not any(n.attrib.get('content-desc') in ('管理环境', '更多') for n in nodes)
    assert not any(n.attrib.get('text') in ('简洁', '原网页') for n in nodes)
    left, top, right, bottom = bounds(capsule)
    nl, nt, nr, nb = bounds(status)
    assert 0 <= left < right <= width * 3 and 0 <= nl < nr <= width * 3
    assert 0 <= top < bottom == nt < nb <= height * 3
    # The redesigned capsule includes a full 48 dp native touch target; the old
    # 28 dp visual-only bound no longer describes this accessibility control.
    assert 48 * 3 <= bottom - top <= max(56, 40 * scale) * 3
    for row in result['controls']:
        l, t, r, b = row['bounds']
        assert r-l >= 48*3 and b-t >= 48*3
        assert 0 <= l < r <= width*3 and nb <= t < b <= height*3
    result.update(environment=environment, capsuleBounds=[left, top, right, bottom],
                  networkBounds=[nl, nt, nr, nb], addressTapAndEnvironmentLongPressDescribed=True)
    return result


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


def exercise_workspace_roundtrip(adb, initial_xml, save, package):
    """Open management, its chat dashboard, then enter the same conversation."""
    initial = navigation(initial_xml, package, conversation=True)
    original_capsule = [n.attrib['content-desc'] for n in ET.fromstring(initial_xml).iter('node')
                        if n.attrib.get('content-desc', '').startswith('当前环境：')]
    assert len(original_capsule) == 1
    capsule = re.fullmatch(r'当前环境：(.+)，点按输入网址，长按切换环境', original_capsule[0])
    assert capsule is not None, 'Current environment identity is required'
    environment = capsule.group(1)
    observed = []
    for label, conversation, selected in (('环境', False, '环境'), ('会话', True, None)):
        before = initial if not observed else observed[-1]
        target = next(row for row in before['controls'] if row['label'] == label)
        l, t, r, b = target['bounds']
        point = [(l+r)//2, (t+b)//2]
        adb('shell', 'input', 'tap', *map(str, point))
        deadline = time.monotonic()+20

        def read_frame():
            assert time.monotonic() < deadline, 'Native navigation exceeded its original 20 second budget'
            adb('shell', 'uiautomator', 'dump', '/sdcard/gecko-navigation-v2.xml')
            xml = adb('shell', 'cat', '/sdcard/gecko-navigation-v2.xml')
            assert time.monotonic() < deadline, 'Native navigation exceeded its original 20 second budget'
            return xml

        entry = None
        if conversation:
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
                value = navigation(xml, package, conversation=conversation, selected=selected)
                break
            except AssertionError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(.2)
        save('production-navigation-' + ('chat' if conversation else 'environments') + '.xml', xml)
        if conversation:
            assert [n.attrib['content-desc'] for n in ET.fromstring(xml).iter('node')
                    if n.attrib.get('content-desc', '').startswith('当前环境：')] == original_capsule
        value.update(actualAndroidTap=dict(label=label, point=point, bounds=target['bounds']))
        if entry is not None:
            value['dashboardEntry'] = entry
        observed.append(value)
    return dict(navigationContract=VERSION, actualAndroidTaps=3, initial=initial,
                observations=observed, allFiveWorkspaceDestinationsVisible=True,
                returnedToSameEnvironment=True)
