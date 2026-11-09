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
    for a, b in zip(controls, controls[1:]):
        assert a['bounds'][2] <= b['bounds'][0], 'Native navigation touch areas overlap or reorder'
        assert max(a['bounds'][1], b['bounds'][1]) < min(a['bounds'][3], b['bounds'][3]), 'Native navigation labels do not share a row'
    return dict(navigationContract=VERSION, conversation=conversation, controls=controls)


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


def exercise_workspace_roundtrip(adb, initial_xml, save, package):
    """Two genuine taps expose all five destinations, then return to conversation."""
    initial = navigation(initial_xml, package, conversation=True)
    original_capsule = [n.attrib['content-desc'] for n in ET.fromstring(initial_xml).iter('node')
                        if n.attrib.get('content-desc', '').startswith('当前环境：')]
    assert len(original_capsule) == 1
    observed = []
    for label, conversation, selected in (('环境', False, '环境'), ('会话', True, None)):
        before = initial if not observed else observed[-1]
        target = next(row for row in before['controls'] if row['label'] == label)
        l, t, r, b = target['bounds']
        point = [(l+r)//2, (t+b)//2]
        adb('shell', 'input', 'tap', *map(str, point))
        deadline = time.monotonic()+20
        while True:
            adb('shell', 'uiautomator', 'dump', '/sdcard/gecko-navigation-v2.xml')
            xml = adb('shell', 'cat', '/sdcard/gecko-navigation-v2.xml')
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
        observed.append(value)
    return dict(navigationContract=VERSION, actualAndroidTaps=2, initial=initial,
                observations=observed, allFiveWorkspaceDestinationsVisible=True,
                returnedToSameEnvironment=True)
