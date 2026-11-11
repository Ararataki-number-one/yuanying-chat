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
import xml.etree.ElementTree as ET

import capture_glass_navigation as shared
from profile_invocation_contract import expected_build, verify_installed
from ui_visual_capture import UiVisualCapture

PACKAGE = 'local.pocketchat.test'
NAME = '长文阅读与文件整理和日常会话的完整环境名称测试'
URL = 'http://browser-fixture.example/native-ui-smoke'
WAITING = '请先在环境网络中配置浏览器线路'


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


def browser_geometry(xml, density):
    address = control(xml, '网址或搜索词', density)
    if address.get('text') != URL:
        raise ValueError('Controlled HTTP address differs')
    name = only(xml, lambda n: n.get('text') == NAME and n.get('class') == 'android.widget.TextView', 'complete environment name')
    caption = only(xml, lambda n: n.get('text') == 'Chromium · HTTP · 不安全', 'HTTP caption')
    notice = only(xml, lambda n: n.get('text') == WAITING, 'unconfigured-route notice')
    descriptions = ['当前环境：'+NAME+'；打开环境管理', '刷新网页', '后退', '前进',
                    '打开主页', '1 个标签页，点击管理', '浏览器菜单']
    controls = [control(xml, value, density) for value in descriptions]
    name_box, caption_box = shared.bounds(name), shared.bounds(caption)
    if name_box[3] > caption_box[1] or shared.bounds(address)[3] > name_box[1]:
        raise ValueError('Environment, caption and address rows overlap')
    bottom = [shared.bounds(n) for n in controls[2:]]
    for before, after in zip(bottom, bottom[1:]):
        if before[2] > after[0]:
            raise ValueError('Bottom browser controls overlap or change order')
    if shared.bounds(notice)[3] >= min(box[1] for box in bottom):
        raise ValueError('Native chrome leaves no visible content area')
    # The production root directly owns its empty FrameLayout content slot.
    # Some accessibility implementations omit empty views: retain that limit.
    tree = ET.fromstring(xml)
    parents = {child: parent for parent in tree.iter() for child in parent}
    raw_address = next(n for n in tree.iter('node') if n.get('content-desc') == '网址或搜索词')
    root = parents.get(parents.get(raw_address))
    slots = [] if root is None else [n for n in root if n.get('class') == 'android.widget.FrameLayout']
    slot = None
    if slots:
        if len(slots) != 1 or shared.bounds(slots[0]) is None:
            raise ValueError('Native browser content slot is missing positive visible bounds')
        slot = shared.bounds(slots[0])
        if slot[1] < shared.bounds(notice)[3] or slot[3] > min(box[1] for box in bottom):
            raise ValueError('Native content slot overlaps browser controls')
    return dict(environmentName=NAME, environmentBounds=name_box, captionBounds=caption_box,
                addressBounds=shared.bounds(address), contentBounds=slot,
                contentSlotObserved=slot is not None, nativeGlyphMetricsMeasured=False,
                controls=[dict(description=n.get('content-desc'), bounds=shared.bounds(n),
                               enabled=n.get('enabled')) for n in controls])


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

    def wait_for(predicate, name, seconds=35):
        deadline = time.monotonic()+seconds
        while time.monotonic() < deadline:
            xml = capture.read(deadline=deadline)
            (args.out/(name+'.xml')).write_text(xml)
            if predicate(xml):
                return xml
            time.sleep(.2)
        raise TimeoutError('Native Chromium UI not ready: '+name)

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
                      installedApkSha256=installed_sha, runnerSha256=shared.sha(__file__), actualAndroidExecution=True)
        original['size'] = adb('shell', 'wm', 'size').decode().strip()
        original['density'] = adb('shell', 'wm', 'density').decode().strip()
        for key in ('font_scale', 'accelerometer_rotation', 'user_rotation'):
            original[key] = adb('shell', 'settings', 'get', 'system', key).decode().strip()
        report['originalDisplay'] = original.copy()
        capture = UiVisualCapture(adb=args.adb, serial=args.serial, source=source, diagnostics=args.out/'hierarchy-attempts.json')
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
            adb('shell', 'am', 'start', '-W', '-n', PACKAGE+'/local.pocketchat.BrowserActivity', '--es', 'url', URL)
            xml = wait_for(lambda value: present(value, lambda n: n.get('text') == WAITING)
                           and present(value, lambda n: n.get('text') == NAME), label+'-browser')
            case['geometry'] = browser_geometry(xml, 3)
            case['screenshots'].append(screenshot(label+'-browser.png'))
            tap(control(xml, '浏览器菜单', 3), 'Open actual Chromium menu')
            xml = wait_for(lambda value: shared.button(value, '环境管理') is not None
                           and shared.button(value, '新标签页') is not None, label+'-menu')
            case['screenshots'].append(screenshot(label+'-menu.png'))
            for attempt in range(10):
                tail = shared.button(xml, '内核信息')
                if tail is not None:
                    break
                scroll = only(xml, lambda n: n.get('class') == 'android.widget.ScrollView', 'menu scroller')
                box = shared.bounds(scroll)
                x, start, end = (box[0]+box[2])//2, box[3]-48, box[1]+48
                if start <= end:
                    raise ValueError('Menu has no scrollable viewport')
                report['inputs'].append(dict(kind='swipe', reason='Reach existing menu tail', bounds=box,
                                             start=[x, start], end=[x, end]))
                adb('shell', 'input', 'swipe', str(x), str(start), str(x), str(end), '300')
                xml = capture.read(deadline=time.monotonic()+15)
                (args.out/(label+'-menu-tail.xml')).write_text(xml)
            else:
                raise ValueError('Original engine-information action is not reachable')
            (args.out/(label+'-menu-tail.xml')).write_text(xml)
            case['screenshots'].append(screenshot(label+'-menu-tail.png'))
            tap(tail, 'Open original engine-information action')
            wait_for(lambda value: present(value, lambda n: n.get('text') == 'Chromium 内核'), label+'-engine-info')
            case['screenshots'].append(screenshot(label+'-engine-info.png'))
            case.update(status='passed', actualMenuAndTailTaps=True, noRouteNoticeObserved=True)
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
