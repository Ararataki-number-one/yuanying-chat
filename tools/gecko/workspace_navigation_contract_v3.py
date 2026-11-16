"""Version 3 reads the real bottom browser toolbar and retained workspaces.

Historical v1/v2 readers stay unchanged. No old dock or top address observation
is translated into this contract: all five targets must exist in native XML.
"""
import re
import hashlib
import time
import xml.etree.ElementTree as ET

if __package__:
    from .workspace_navigation_contract import bounds, navigation as workspace_navigation
else:
    from workspace_navigation_contract import bounds, navigation as workspace_navigation

VERSION = 3
MENU_ACTIONS = ('前进', '打开网址或搜索', '快速切换环境', '进入专注阅读',
                '当前环境网络', '管理全部环境', '下载管理')


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


def seek_menu_action(adb, read, package, label, *, deadline, scrolls):
    """Find a real menu action with bounded, recorded Android scroll inputs."""
    for attempt in range(9):
        assert time.monotonic() < deadline, 'Original menu observation budget expired'
        xml = read(deadline=deadline)
        assert time.monotonic() < deadline, 'Original menu observation budget expired'
        try:
            target = menu_action(xml, package, label)
            if target['bounds'][3]-target['bounds'][1] >= 144:
                return xml, target
        except AssertionError:
            pass
        tree = ET.fromstring(xml)
        assert any(n.get('package') == package and n.get('text') == n.get('content-desc') == '浏览器菜单'
                   for n in tree.iter('node')), 'Cannot scroll a window other than the actual browser menu'
        views = [n for n in tree.iter('node') if n.get('package') == package
                 and n.get('class') == 'android.widget.ScrollView' and n.get('scrollable') == 'true']
        assert len(views) == 1 and attempt < 8 and len(scrolls) < 8, ('Menu action is unavailable', label)
        left, top, right, bottom = bounds(views[0])
        start = [(left+right)//2, top+(bottom-top)*4//5]
        end = [start[0], top+(bottom-top)//5]
        raw = xml.encode('utf-8')
        scrolls.append(dict(label=label, rawXml=xml, xmlSha256=hashlib.sha256(raw).hexdigest(),
                            bounds=[left,top,right,bottom], **{'from':start, 'to':end},
                            durationMs=320, actualAndroidInput=True))
        adb('shell', 'input', 'swipe', *map(str, start+end), '320')
    raise AssertionError(('Menu action remained unavailable', label))


def verify_menu_scrolls(scrolls, package, label):
    assert type(scrolls) is list and len(scrolls) <= 8
    for value in scrolls:
        assert value['label'] == label and value['actualAndroidInput'] is True and value['durationMs'] == 320
        xml=value['rawXml']; assert type(xml) is str and 0 < len(xml.encode()) <= 1024*1024
        assert value['xmlSha256'] == hashlib.sha256(xml.encode()).hexdigest()
        nodes=list(ET.fromstring(xml).iter('node'))
        assert any(n.get('package') == package and n.get('text') == n.get('content-desc') == '浏览器菜单' for n in nodes)
        views=[n for n in nodes if n.get('package') == package and n.get('class') == 'android.widget.ScrollView' and n.get('scrollable') == 'true']
        assert len(views) == 1
        l,t,r,b=bounds(views[0]); assert value['bounds'] == [l,t,r,b]
        assert value['from'] == [(l+r)//2,t+(b-t)*4//5] and value['to'] == [(l+r)//2,t+(b-t)//5]
    return True


def navigation(xml, package, *, conversation, selected=None, browser=False):
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
    density = action_size / 48
    assert abs(density-3) < .01, 'Native browser action must retain the actual 48 dp target'
    assert address[2]-address[0] >= 48*density and address[3]-address[1] >= 48*density
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


def exercise_workspace_roundtrip(adb, initial_xml, save, package, *, browser=False):
    """Enter management through the actual menu, then return to the live browser."""
    assert browser is True, 'The v3 product uses direct browser entry'
    initial = navigation(initial_xml, package, conversation=True, browser=True)
    capsule = [n.get('content-desc') for n in ET.fromstring(initial_xml).iter('node')
               if n.get('package') == package and n.get('content-desc', '').startswith('当前环境：')]
    assert len(capsule) == 1
    receipts, observations = [], []

    def tap(target, label):
        point = center(target['bounds'])
        adb('shell', 'input', 'tap', *map(str, point))
        receipts.append(dict(label=label, point=point, bounds=target['bounds'], actualAndroidTap=True))

    menu_scrolls=[]

    def read_frame(*, deadline):
        remote='/sdcard/gecko-navigation-v3.xml'
        while time.monotonic() < deadline:
            output=adb('shell','rm -f '+remote+' && uiautomator dump '+remote+' 2>&1')
            print(output,end='',flush=True)
            assert time.monotonic() < deadline, 'Original native navigation budget expired'
            if output.strip() == 'ERROR: null root node returned by UiTestAutomationBridge.':
                time.sleep(min(.2,max(0,deadline-time.monotonic())))
                continue
            assert output.strip() == 'UI hierchary dumped to: '+remote
            xml=adb('shell','cat',remote)
            assert time.monotonic() < deadline, 'Original native navigation budget expired'
            return xml
        raise TimeoutError('Original native navigation budget expired')

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
    xml,target=seek_menu_action(adb,read_frame,package,'管理全部环境',deadline=deadline,scrolls=menu_scrolls)
    save('production-navigation-menu.xml',xml)
    assert time.monotonic() < deadline, 'Original native menu budget expired after save'
    tap(target, '管理全部环境')
    _, workspace = observe('environments', lambda xml: navigation(xml, package, conversation=False, selected='环境', browser=True))
    observations.append(workspace)
    target = next(row for row in workspace['controls'] if row['label'] == '浏览器')
    tap(target, '浏览器')
    xml, final = observe('chat', lambda xml: navigation(xml, package, conversation=True, browser=True))
    assert [n.get('content-desc') for n in ET.fromstring(xml).iter('node')
            if n.get('package') == package and n.get('content-desc', '').startswith('当前环境：')] == capsule
    observations.append(final)
    return dict(navigationContract=VERSION, actualAndroidTaps=3, inputs=receipts, browserWorkspace=True,
                initial=initial, observations=observations, menuScrolls=menu_scrolls, allFiveWorkspaceDestinationsVisible=True,
                returnedToSameEnvironment=True)
