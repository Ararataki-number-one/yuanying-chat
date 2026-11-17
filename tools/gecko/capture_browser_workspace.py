#!/usr/bin/env python3
"""Small native Chromium UI smoke on the source-bound disposable integration APK.

The existing visual fixture supplies an unconfigured route and a 23-character
environment name. These are actual Android native controls and menu taps, not a
loaded webpage, a login, WAN validation, or Chromium security acceptance.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import time
import uuid
import xml.etree.ElementTree as ET

import capture_glass_navigation as shared
from profile_invocation_contract import expected_build, verify_installed
from ui_visual_capture import UiVisualCapture
from browser_header_contract_v5 import verify_header, network_extension
from workspace_browser_header_v5 import native_observation

PACKAGE = 'local.pocketchat.test'
NAME = '长文阅读与文件整理和日常会话的完整环境名称测试'
URL = 'http://browser-fixture.example/native-ui-smoke'
WAITING = '请先在环境网络中配置浏览器线路'
ENVIRONMENT = '当前环境：'+NAME+'，点按切换环境'
BOTTOM_CONTROLS = ('打开当前环境主页', '网页窗口', '网址或搜索词', '网页工具', '浏览器菜单')
NETWORK_SUMMARY = '出口 IP 未核验 · 延迟未测 · 未连接'
NETWORK = '当前环境网络：'+NETWORK_SUMMARY


def only(xml, predicate, label):
    found = shared.nodes(xml, predicate)
    if len(found) != 1:
        raise ValueError('Expected one visible native ' + label)
    return found[0]


def control(xml, description, density):
    node = only(xml, lambda n: n.get('content-desc') == description
                and n.get('class') in ('android.widget.Button', 'android.widget.EditText'), description)
    box = shared.bounds(node)
    if box[2]-box[0] < 48*density or box[3]-box[1] < 48*density:
        raise ValueError('Native target is smaller than 48dp: ' + description)
    if node.get('clickable') != 'true':
        raise ValueError('Native action lost click semantics: ' + description)
    return node


def header_packet(log, nonce, source):
    """Read one nonce-owned native packet; a malformed or duplicate packet fails."""
    def pairs(values):
        result = {}
        for key, value in values:
            if key in result:
                raise ValueError('Duplicate native header field: '+key)
            result[key] = value
        return result
    selected = []
    for line in log.splitlines():
        if '{' not in line:
            continue
        raw = line[line.index('{'):]
        value = json.loads(raw, object_pairs_hook=pairs,
                           parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite header field')))
        if value.get('nonce') == nonce:
            selected.append(raw)
    if not selected:
        return None
    if len(selected) != 1:
        raise ValueError('Expected one owned native header observation')
    value = native_observation(selected[0], nonce, source)
    if value['engine'] != 'chromium' or value['activityClass'] != 'local.pocketchat.BrowserActivity':
        raise ValueError('Header observation is not from the actual Chromium activity')
    return selected[0], value


def network_control(xml, density, native_header=None):
    if native_header is None:
        # Historical XML-only observations retain their original visible 48dp rule.
        return control(xml, NETWORK, density)
    try:
        verify_header(native_header['layout'])
    except (AssertionError, KeyError, TypeError) as error:
        raise ValueError('Invalid live native header touch geometry') from error
    if (native_header['engine'] != 'chromium'
            or native_header['activityClass'] != 'local.pocketchat.BrowserActivity'
            or native_header['density'] != density):
        raise ValueError('Header owner or density differs from the current browser')
    node = only(xml, lambda n: n.get('content-desc') == NETWORK
                and n.get('class') == 'android.widget.Button', NETWORK)
    box = shared.bounds(node)
    if (node.get('clickable') != 'true' or node.get('enabled') != 'true'
            or box[2]-box[0] < 48*density or box[3]-box[1] < 28*density
            or list(box) != native_header['layout']['networkMetrics']['bounds']):
        raise ValueError('Visible network row differs from its native touch delegate')
    return node


def environment_ready(xml, density):
    """Match the capsule's action, not its repeated visual child label."""
    found = shared.nodes(xml, lambda n: n.get('class') == 'android.widget.Button'
                         and n.get('content-desc') == ENVIRONMENT)
    if len(found) != 1:
        return False
    node = found[0]
    box = shared.bounds(node)
    return (node.get('text') == NAME and node.get('enabled') == 'true'
            and node.get('clickable') == 'true' and node.get('long-clickable') != 'true'
            and box[2]-box[0] >= 48*density and box[3]-box[1] >= 48*density)


def browser_geometry(xml, density, native_header=None):
    address = control(xml, '网址或搜索词', density)
    if address.get('text') != URL:
        raise ValueError('Controlled HTTP address differs')
    name = control(xml, ENVIRONMENT, density)
    if name.get('text') != NAME or name.get('enabled') != 'true' or name.get('long-clickable') == 'true':
        raise ValueError('The retained environment capsule lost its complete name or switch action')
    network = network_control(xml, density, native_header)
    if network.get('text') != '●  '+NETWORK_SUMMARY or network.get('enabled') != 'true':
        raise ValueError('The unconfigured Chromium header must report its own unverified network state')
    notice = only(xml, lambda n: n.get('text') == WAITING, 'unconfigured-route notice')
    controls = [control(xml, value, density) for value in BOTTOM_CONTROLS]
    if any(n.get('enabled') != 'true' for n in controls):
        raise ValueError('Every current bottom browser destination must remain enabled')
    name_box = shared.bounds(name)
    network_box = shared.bounds(network)
    if native_header is not None and list(name_box) != native_header['capsuleAccessibilityBounds']:
        raise ValueError('Native header capsule differs from the visible current activity')
    bottom = [shared.bounds(n) for n in controls]
    if name_box[3] > network_box[1] or network_box[3] > shared.bounds(notice)[1]:
        raise ValueError('The capsule, network row and page notice are not separate ordered header controls')
    if shared.nodes(xml, lambda n: n.get('text') == 'Chromium · HTTP · 不安全'
                    or n.get('content-desc') in ('前进', '打开主页', '1 个标签页，点击管理')
                    or n.get('text') in ('环境', '网络', '下载', '阅读')):
        raise ValueError('The browser still exposes a retired top row or management dock')
    for before, after in zip(bottom, bottom[1:]):
        if before[2] > after[0]:
            raise ValueError('Bottom browser controls overlap or change order')
    if shared.bounds(address)[2]-shared.bounds(address)[0] < 72*density:
        raise ValueError('The bottom address has no usable editing width')
    if any(abs((box[1]+box[3])-(bottom[0][1]+bottom[0][3])) > 1 for box in bottom):
        raise ValueError('Current browser actions and address must share one row')
    for box in (bottom[0], bottom[1], bottom[3], bottom[4]):
        if box[2]-box[0] != 48*density or box[3]-box[1] != 48*density:
            raise ValueError('Browser action geometry differs from the fixed 48dp targets')
    if shared.bounds(notice)[3] >= min(box[1] for box in bottom):
        raise ValueError('Native chrome leaves no visible content area')
    # The production root directly owns its empty FrameLayout content slot.
    # Some accessibility implementations omit empty views: retain that limit.
    tree = ET.fromstring(xml)
    parents = {child: parent for parent in tree.iter() for child in parent}
    raw_address = next(n for n in tree.iter('node') if n.get('content-desc') == '网址或搜索词')
    raw_name = next(n for n in tree.iter('node') if n.get('content-desc') == ENVIRONMENT)
    root = parents.get(raw_address)
    while root is not None and not any(n is raw_name for n in root.iter()):
        root = parents.get(root)
    if root is None or shared.bounds(root) is None:
        raise ValueError('The address and environment have no visible shared native root')
    root_box = shared.bounds(root)
    if abs(name_box[0]+name_box[2]-root_box[0]-root_box[2]) > 1:
        raise ValueError('The retained environment capsule is not horizontally centered')
    # The new top capsule has its own FrameLayout. Only the other direct
    # FrameLayout is the actual content slot; do not mistake the header for it.
    slots = [n for n in root if n.get('class') == 'android.widget.FrameLayout'
             and not any(child is raw_name for child in n.iter())]
    slot = None
    if slots:
        if len(slots) != 1 or shared.bounds(slots[0]) is None:
            raise ValueError('Native browser content slot is missing positive visible bounds')
        slot = shared.bounds(slots[0])
        if slot[1] < shared.bounds(notice)[3] or slot[3] > min(box[1] for box in bottom):
            raise ValueError('Native content slot overlaps browser controls')
        if native_header is not None and list(slot) != native_header['layout']['webBounds']:
            raise ValueError('Current content slot differs from the native header observation')
    return dict(navigationContract=4, headerContract=5 if native_header is not None else 4,
                environmentName=NAME, environmentBounds=name_box,
                networkBounds=network_box, networkText=network.get('text'),
                networkTouchBounds=native_header['layout']['networkMetrics']['touchBounds'] if native_header is not None else network_box,
                unverifiedNetworkStateObserved=True,
                addressBounds=shared.bounds(address), contentBounds=slot,
                addressAtBottom=True, topAddressAbsent=True, environmentCapsuleRetained=True,
                contentSlotObserved=slot is not None, nativeGlyphMetricsMeasured=False,
                controls=[dict(description=n.get('content-desc'), bounds=shared.bounds(n),
                               enabled=n.get('enabled')) for n in controls])


def menu_swipe_plan(xml):
    """Start on an observed empty divider, never an actionable menu row."""
    if not shared.browser_menu_open(xml):
        raise ValueError('The actual browser menu must be open before scrolling')
    tree = ET.fromstring(xml)
    parents = {child: parent for parent in tree.iter() for child in parent}
    def visible(node):
        while node is not None:
            if node.get('visible-to-user') == 'false':
                return False
            node = parents.get(node)
        return True
    shown = [node for node in tree.iter('node') if visible(node)]
    scrolls = [node for node in shown if node.get('package') == PACKAGE
               and node.get('class') == 'android.widget.ScrollView']
    if len(scrolls) != 1:
        raise ValueError('Expected one visible native menu scroller')
    scroll = scrolls[0]
    box = shared.bounds(scroll)
    if (box is None or scroll.get('enabled') != 'true' or scroll.get('scrollable') != 'true'
            or scroll.get('clickable') != 'false' or scroll.get('long-clickable') != 'false'):
        raise ValueError('Menu scroller cannot safely own the gesture')
    blocked = []
    for node in shown:
        if node.get('clickable') == 'true' or node.get('long-clickable') == 'true':
            rectangle = shared.bounds(node)
            if rectangle is None:
                raise ValueError('An actionable native node has unproven bounds')
            blocked.append(rectangle)
    candidates = []
    for node in scroll.iter('node'):
        if (not visible(node) or node.get('package') != PACKAGE or list(node)
                or node.get('class') != 'android.view.View' or node.get('text') or node.get('content-desc')
                or node.get('enabled') != 'true' or node.get('clickable') != 'false'
                or node.get('long-clickable') != 'false' or node.get('focusable') == 'true'):
            continue
        rectangle = shared.bounds(node)
        if (rectangle is None or not (box[0] <= rectangle[0] < rectangle[2] <= box[2]
                                      and box[1] <= rectangle[1] < rectangle[3] <= box[3])):
            continue
        x, y = (rectangle[0]+rectangle[2])//2, (rectangle[1]+rectangle[3])//2
        if not (box[0]+48 <= x < box[2]-48 and box[1]+96 <= y <= box[3]-48):
            continue
        if any(left <= x < right and top <= y < bottom for left, top, right, bottom in blocked):
            continue
        candidates.append((y, x, rectangle))
    if not candidates:
        raise ValueError('No observed noninteractive menu divider can start a safe swipe')
    y, x, rectangle = max(candidates)
    return dict(bounds=list(box), start=[x, y], end=[x, box[1]+48],
                noninteractiveStartBounds=list(rectangle))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--apk', type=Path, required=True)
    parser.add_argument('--adb', default='adb')
    parser.add_argument('--serial', default='emulator-5554')
    parser.add_argument('--device-api', type=int, choices=(32, 35), required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.serial != 'emulator-5554':
        parser.error('Only the disposable CI emulator is supported')
    args.root, args.apk, args.out = args.root.resolve(), args.apk.resolve(), args.out.resolve()
    args.out.mkdir(parents=True, exist_ok=True)
    report = dict(schema=1, status='running', scope=__doc__.strip(), cases=[], inputs=[], commands=[],
                  actualAndroidExecution=False, actualAndroidWebViewExecution=False,
                  actualPublicWebsiteExecution=False, fingerprintProtectionVerified=False)
    original = {}
    capture = None
    verified = False
    failure = None

    def command(parts, timeout=30):
        row = dict(command=list(map(str, parts)), startedAtUnixNs=time.time_ns())
        report['commands'].append(row)
        result = subprocess.run(row['command'], stdin=subprocess.DEVNULL, capture_output=True, timeout=timeout)
        row.update(exitCode=result.returncode, stdoutSha256=hashlib.sha256(result.stdout).hexdigest(),
                   stderr=result.stderr.decode('utf-8', 'replace')[:2048])
        result.check_returncode()
        return result.stdout

    def adb(*parts, **options):
        return command([args.adb, '-s', args.serial, *parts], **options)

    def screenshot(name):
        raw = adb('exec-out', 'screencap', '-p')
        if len(raw) < 33 or raw[:8] != b'\x89PNG\r\n\x1a\n' or raw[-12:] != b'\x00\x00\x00\x00IEND\xaeB`\x82':
            raise ValueError('Original device screenshot is not a complete PNG')
        (args.out/name).write_bytes(raw)
        return dict(file=name, sha256=hashlib.sha256(raw).hexdigest(),
                    actualPixelSize=list(struct.unpack('>II', raw[16:24])))

    def wait_for(predicate, name, seconds=35, *, deadline=None):
        deadline = time.monotonic()+seconds if deadline is None else deadline
        while time.monotonic() < deadline:
            xml = capture.read(deadline=deadline)
            (args.out/(name+'.xml')).write_text(xml)
            if predicate(xml):
                return xml
            time.sleep(.2)
        raise TimeoutError('Native Chromium UI not ready: '+name)

    def observe_header(nonce, source, deadline):
        while time.monotonic() < deadline:
            remaining = deadline-time.monotonic()
            if remaining <= 0:
                break
            raw = adb('logcat', '-d', '-s', 'PocketBrowserHeader:I', '*:S', timeout=min(30, remaining))
            packet = header_packet(raw.decode('utf-8'), nonce, source)
            if packet is not None:
                return packet
            time.sleep(min(.2, max(0, deadline-time.monotonic())))
        raise TimeoutError('Native Chromium header did not report within the original readiness deadline')

    def present(xml, predicate):
        return len(shared.nodes(xml, predicate)) == 1

    def tap(node, reason):
        box = shared.bounds(node)
        if box is None or node.get('enabled') != 'true' or node.get('clickable') != 'true':
            raise ValueError('Action must come from one enabled visible native control')
        point = [(box[0]+box[2])//2, (box[1]+box[3])//2]
        report['inputs'].append(dict(kind='tap', reason=reason, bounds=box, point=point))
        adb('shell', 'input', 'tap', *map(str, point))

    try:
        git = lambda *parts: command(['git', '-C', args.root, *parts]).decode().strip()
        source, tree = git('rev-parse', 'HEAD'), git('rev-parse', 'HEAD^{tree}')
        if git('status', '--porcelain'):
            raise ValueError('A clean committed source tree is required')
        gradle = (args.root/'app/build.gradle').read_text()
        identity = expected_build(args.apk, source, tree, re.search(r"versionName '([^']+)'", gradle).group(1),
                                  int(re.search(r'versionCode (\d+)', gradle).group(1)))
        if adb('shell', 'getprop', 'ro.kernel.qemu').strip() != b'1' or adb('shell', 'getprop', 'ro.build.version.sdk').strip() != str(args.device_api).encode():
            raise ValueError('Expected disposable Android emulator API')
        installed = json.loads(adb('exec-out', 'content', 'read', '--uri', 'content://local.pocketchat.test.evidence/build-identity'))
        verify_installed(installed, identity)
        path = adb('shell', 'pm', 'path', PACKAGE).decode().strip()
        if not re.fullmatch(r'package:/data/app/[A-Za-z0-9_./=+~-]+/base\.apk', path):
            raise ValueError('Expected one installed test APK')
        installed_sha = adb('shell', 'sha256sum', path.removeprefix('package:')).decode().split()[0]
        if installed_sha != identity['apkSha256']:
            raise ValueError('Installed bytes differ from the exact current-source APK')
        verified = True
        report.update(sourceCommit=source, sourceTree=tree, buildIdentity=identity,
                      installedApkSha256=installed_sha, runnerSha256=shared.sha(__file__), actualAndroidExecution=True,
                      headerContract=5, headerReaderInputs={name:shared.sha(args.root/name) for name in (
                          'tools/gecko/browser_header_contract_v5.py', 'tools/gecko/workspace_browser_header_v5.py',
                          'tests/gecko/BrowserHeaderVisualEvidence.java')})
        original['size'] = adb('shell', 'wm', 'size').decode().strip()
        original['density'] = adb('shell', 'wm', 'density').decode().strip()
        for key in ('font_scale', 'accelerometer_rotation', 'user_rotation'):
            original[key] = adb('shell', 'settings', 'get', 'system', key).decode().strip()
        report['originalDisplay'] = original.copy()
        capture = UiVisualCapture.for_device(adb=args.adb, serial=args.serial, source=source, diagnostics=args.out/'hierarchy-attempts.json')
        for label, width, height, scale in [('default', 412, 892, 1.0), ('narrow-large-font', 320, 640, 2.0)]:
            shared.set_display(width*3, height*3, 480)
            adb('shell', 'am', 'force-stop', PACKAGE)
            if adb('shell', 'pm', 'clear', PACKAGE).strip() != b'Success':
                raise ValueError('Disposable fixture reset failed')
            adb('shell', 'wm', 'size', f'{width*3}x{height*3}')
            adb('shell', 'wm', 'density', '480')
            for key, value in [('font_scale', str(scale)), ('accelerometer_rotation', '0'), ('user_rotation', '0')]:
                adb('shell', 'settings', 'put', 'system', key, value)
            actual_scale = float(adb('shell', 'settings', 'get', 'system', 'font_scale').strip())
            if actual_scale != scale:
                raise ValueError('Android did not apply the requested font scale')
            case = dict(name=label, widthDp=width, heightDp=height, fontScale=scale, screenshots=[], status='running')
            report['cases'].append(case)
            adb('shell', 'am', 'start', '-W', '-n', shared.COMPONENT, '--es', 'visualAction', 'browser')
            wait_for(lambda xml: any(NAME in n.get('text', '') or NAME in n.get('content-desc', '')
                                    for n in ET.fromstring(xml).iter('node')), label+'-seed')
            # The seed opens an editor after MainActivity's first frame. End that
            # synthetic task before opening the unchanged production browser.
            adb('shell', 'am', 'force-stop', PACKAGE)
            nonce = uuid.uuid4().hex
            adb('shell', 'am', 'start', '-W', '-n', shared.COMPONENT,
                '--es', 'visualAction', 'browser-header', '--es', 'visualHeaderNonce', nonce, '--es', 'url', URL)
            browser_deadline = time.monotonic()+35
            xml = wait_for(lambda value: present(value, lambda n: n.get('text') == WAITING)
                           and environment_ready(value, 3)
                           and present(value, lambda n: n.get('content-desc') == NETWORK), label+'-browser', deadline=browser_deadline)
            header_raw, native_header = observe_header(nonce, source, browser_deadline)
            if native_header['fontScale'] != scale or native_header['windowBounds'] != [0, 0, width*3, height*3]:
                raise ValueError('Native header font scale or window differs from the requested actual display')
            case.update(headerContract=5, browserHeaderNonce=nonce, browserHeaderRaw=header_raw, browserHeaderRawXml=xml)
            (args.out/(label+'-header.json')).write_text(header_raw+'\n')
            case['geometry'] = browser_geometry(xml, 3, native_header)
            case['screenshots'].append(screenshot(label+'-browser.png'))
            tap(control(xml, ENVIRONMENT, 3), 'Tap the small environment capsule to open only the environment picker')
            xml = wait_for(lambda value: present(value, lambda n: n.get('text') == '快速切换环境')
                           and present(value, lambda n: n.get('content-desc') == '关闭快速切换环境')
                           and not present(value, lambda n: n.get('text') == '打开网址'), label+'-environment')
            case['screenshots'].append(screenshot(label+'-environment.png'))
            tap(control(xml, '关闭快速切换环境', 3), 'Close the environment picker without switching the current page')
            xml = wait_for(lambda value: present(value, lambda n: n.get('text') == WAITING)
                           and present(value, lambda n: n.get('content-desc') == NETWORK), label+'-environment-returned')
            case['environmentReturnedGeometry'] = browser_geometry(xml, 3, native_header)
            tap(network_control(xml, 3, native_header), 'Open the actual Chromium network details from the header row')
            xml = wait_for(lambda value: present(value, lambda n: n.get('text') == '网络情况')
                           and present(value, lambda n: n.get('content-desc') == '关闭网络情况')
                           and present(value, lambda n: n.get('text', '').startswith(NETWORK_SUMMARY+'\n\n')),
                           label+'-network')
            case['screenshots'].append(screenshot(label+'-network.png'))
            tap(control(xml, '关闭网络情况', 3), 'Close network details without changing route configuration')
            xml = wait_for(lambda value: present(value, lambda n: n.get('text') == WAITING)
                           and present(value, lambda n: n.get('content-desc') == NETWORK), label+'-network-returned')
            case['networkReturnedGeometry'] = browser_geometry(xml, 3, native_header)
            target = network_extension(native_header['layout'])
            point, visible = target['point'], native_header['layout']['networkMetrics']['bounds']
            outside = not (visible[0] <= point[0] < visible[2] and visible[1] <= point[1] < visible[3])
            if visible[3]-visible[1] < 48*3 and not outside:
                raise ValueError('Compact header tap must exercise the actual extension outside the visible strip')
            report['inputs'].append(dict(kind='tap', reason='Exercise the actual native 48dp network target',
                                        bounds=target['bounds'], point=point, headerNonce=nonce, outsideVisibleRow=outside))
            adb('shell', 'input', 'tap', *map(str, point))
            xml = wait_for(lambda value: present(value, lambda n: n.get('text') == '网络情况')
                           and present(value, lambda n: n.get('content-desc') == '关闭网络情况')
                           and present(value, lambda n: n.get('text', '').startswith(NETWORK_SUMMARY+'\n\n')),
                           label+'-network-touch-target')
            case['screenshots'].append(screenshot(label+'-network-touch-target.png'))
            tap(control(xml, '关闭网络情况', 3), 'Close the network sheet opened from the native touch target')
            xml = wait_for(lambda value: present(value, lambda n: n.get('text') == WAITING)
                           and present(value, lambda n: n.get('content-desc') == NETWORK), label+'-network-touch-returned')
            case['networkTouchReturnedGeometry'] = browser_geometry(xml, 3, native_header)
            case.update(actualNativeNetworkTargetRoundtrip=True, nativeNetworkTarget=target,
                        nativeNetworkTapOutsideVisibleRow=outside)
            tap(control(xml, '网页工具', 3), 'Open actual Chromium webpage tools')
            xml = wait_for(lambda value: shared.browser_tools_open(value)
                           and present(value, lambda n: n.get('text') == 'Chromium · HTTP · 不安全')
                           and present(value, lambda n: n.get('text') == '前进'
                                       and n.get('class') == 'android.widget.Button'), label+'-tools')
            forward = only(xml, lambda n: n.get('text') == '前进' and n.get('class') == 'android.widget.Button', 'forward menu action')
            if forward.get('enabled') != 'false':
                raise ValueError('Forward must remain disabled without actual history')
            case['screenshots'].append(screenshot(label+'-tools.png'))
            tap(control(xml, '关闭网页工具', 3), 'Close actual webpage tools without navigating')
            xml = wait_for(lambda value: present(value, lambda n: n.get('text') == WAITING)
                           and not shared.browser_tools_open(value), label+'-tools-returned')
            case['toolsReturnedGeometry'] = browser_geometry(xml, 3, native_header)
            tap(control(xml, '网页窗口', 3), 'Open actual tabs from the second browser button')
            xml = wait_for(lambda value: present(value, lambda n: n.get('text') == '网页窗口')
                           and present(value, lambda n: n.get('text') == NAME+' · 1/8 个标签页')
                           and shared.button(value, '返回') is not None
                           and shared.button(value, '新标签页') is not None, label+'-tabs')
            case['screenshots'].append(screenshot(label+'-tabs.png'))
            tap(shared.button(xml, '返回'), 'Return from actual tab management without changing tabs')
            xml = wait_for(lambda value: present(value, lambda n: n.get('text') == WAITING)
                           and present(value, lambda n: n.get('content-desc') == '浏览器菜单')
                           and not present(value, lambda n: n.get('text') == NAME+' · 1/8 个标签页'), label+'-tabs-returned')
            case['returnedGeometry'] = browser_geometry(xml, 3, native_header)
            tap(control(xml, '浏览器菜单', 3), 'Reopen the browser menu after the tab sheet')
            xml = wait_for(lambda value: shared.browser_menu_open(value)
                           and shared.menu_body_ready(value, PACKAGE), label+'-menu-reopened')
            observed_actions = set()
            for attempt in range(10):
                observed_actions.update(value for value in ('环境管理',) if shared.button(xml, value) is not None)
                tail = shared.button(xml, '内核信息')
                if tail is not None:
                    break
                plan = menu_swipe_plan(xml)
                box = plan['bounds']
                x, start = plan['start']
                end = plan['end'][1]
                report['inputs'].append(dict(kind='swipe', reason='Reach existing menu tail', bounds=box,
                                             start=[x, start], end=[x, end],
                                             noninteractiveStartBounds=plan['noninteractiveStartBounds'],
                                             sourceHierarchySha256=hashlib.sha256(xml.encode('utf-8')).hexdigest()))
                adb('shell', 'input', 'swipe', str(x), str(start), str(x), str(end), '300')
                xml = capture.read(deadline=time.monotonic()+15)
                (args.out/(label+'-menu-tail.xml')).write_text(xml)
            else:
                raise ValueError('Original engine-information action is not reachable')
            if observed_actions != {'环境管理'}:
                raise ValueError('Original environment management menu action is not reachable')
            (args.out/(label+'-menu-tail.xml')).write_text(xml)
            case['screenshots'].append(screenshot(label+'-menu-tail.png'))
            tap(tail, 'Open original engine-information action')
            wait_for(lambda value: present(value, lambda n: n.get('text') == 'Chromium 内核'), label+'-engine-info')
            case['screenshots'].append(screenshot(label+'-engine-info.png'))
            case.update(status='passed', actualMenuAndTailTaps=True, actualTabSheetRoundtrip=True,
                        actualEnvironmentCapsuleTapRoundtrip=True, actualHeaderNetworkRoundtrip=True,
                        actualWebpageToolsRoundtrip=True,
                        forwardDisabledWithoutHistory=True, httpCaptionObservedInTools=True,
                        environmentManagementActionReachable=True, newTabActionInWindowsReachable=True,
                        noRouteNoticeObserved=True)
        if git('rev-parse', 'HEAD') != source or git('status', '--porcelain') or shared.sha(args.apk) != identity['apkSha256']:
            raise ValueError('Source or APK changed during capture')
        report['status'] = 'passed'
    except Exception as error:
        failure = error
        report.update(status='failed', errorType=type(error).__name__, error=str(error))
        if verified:
            try:
                report['failureScreenshot'] = screenshot('failure.png')
            except Exception as capture_error:
                report['failureCaptureError'] = str(capture_error)
    finally:
        if verified:
            restores = [('shell', 'am', 'force-stop', PACKAGE)]
            for key in ('size', 'density'):
                if key in original:
                    override = re.search(r'Override '+key+r':\s*([^\s]+)', original[key])
                    restores.append(('shell', 'wm', key, override.group(1) if override else 'reset'))
            for key in ('font_scale', 'accelerometer_rotation', 'user_rotation'):
                if key in original:
                    restores.append(('shell', 'settings', 'delete', 'system', key) if original[key] == 'null'
                                    else ('shell', 'settings', 'put', 'system', key, original[key]))
            for parts in restores:
                try:
                    adb(*parts)
                except Exception as restore_error:
                    report.setdefault('restoreErrors', []).append(str(restore_error))
                    report['status'] = 'failed'
        report['completedAtUnixNs'] = time.time_ns()
        (args.out/'capture.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(dict(status=report['status'], sourceCommit=report.get('sourceCommit'),
                         actualAndroidExecution=report['actualAndroidExecution'], output=str(args.out/'capture.json'))))
    if failure is not None or report['status'] != 'passed':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
