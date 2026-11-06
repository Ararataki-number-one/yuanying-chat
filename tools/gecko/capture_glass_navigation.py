#!/usr/bin/env python3
"""Capture one real, source-bound Android navigation screen for design review.

This is a new screenshot diagnostic, not a replay or replacement of a frozen UI
acceptance workload. The ordinary integration APK starts its actual MainActivity
with the existing local, unconfigured visual fixture. No website, account, WAN
connection, physical phone or performance acceptance is claimed.
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

from ui_visual_capture import UiVisualCapture

PACKAGE = 'local.pocketchat.test'
COMPONENT = PACKAGE + '/local.pocketchat.UiVisualIntegrationActivity'
WIDTH, HEIGHT, DENSITY = 1236, 2676, 480
LABELS = ('环境', '网络', '下载', '阅读')


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def bounds(node):
    match = re.fullmatch(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', node.get('bounds', ''))
    if match is None:
        return None
    left, top, right, bottom = map(int, match.groups())
    if not (0 <= left < right <= WIDTH and 0 <= top < bottom <= HEIGHT):
        return None
    return left, top, right, bottom


def nodes(xml, predicate):
    return [node for node in ET.fromstring(xml).iter('node')
            if node.get('package') == PACKAGE and node.get('visible-to-user') != 'false'
            and bounds(node) is not None and predicate(node)]


def button(xml, label):
    found = nodes(xml, lambda node: node.get('text') == label
                  and node.get('class') == 'android.widget.Button'
                  and node.get('clickable') == 'true' and node.get('enabled') == 'true')
    return found[0] if len(found) == 1 else None


def navigation(xml):
    controls = [button(xml, label) for label in LABELS]
    if any(node is None for node in controls):
        return None
    boxes = [bounds(node) for node in controls]
    if any(node.get('selected') == 'true' for node in controls):
        return None  # The ordinary conversation is not one of the four actions.
    if any(right - left < 144 or bottom - top < 144 for left, top, right, bottom in boxes):
        return None
    if any(boxes[i][2] > boxes[i + 1][0] for i in range(3)) or boxes[2][2] >= boxes[3][0]:
        return None
    reading = boxes[-1]
    if abs((reading[2] - reading[0]) - (reading[3] - reading[1])) > 3:
        return None
    return {label: list(box) for label, box in zip(LABELS, boxes)}


def capsule(xml):
    found = nodes(xml, lambda node: node.get('content-desc', '').startswith('当前环境：')
                  and '点按输入网址，长按切换环境' in node.get('content-desc', '')
                  and node.get('clickable') == 'true' and node.get('enabled') == 'true')
    return found[0] if len(found) == 1 else None


def expanded(xml):
    return len(nodes(xml, lambda node: node.get('content-desc') == '管理环境'
                     and node.get('clickable') == 'true')) == 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--apk', type=Path, required=True)
    parser.add_argument('--build-work', type=Path, required=True)
    parser.add_argument('--adb', required=True)
    parser.add_argument('--serial', default='emulator-5554', choices=['emulator-5554'])
    parser.add_argument('--aapt2', required=True)
    parser.add_argument('--apksigner', required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    args.root, args.apk, args.build_work, args.out = (
        path.resolve() for path in (args.root, args.apk, args.build_work, args.out))
    args.out.mkdir(parents=True, exist_ok=True)
    report = dict(schema=1, status='started', startedAtUnixNs=time.time_ns(),
                  diagnostic='split-glass-navigation', scene='actual-main-activity',
                  actualAndroidExecution=False, applicationAcceptance=False,
                  physicalPhoneAcceptance=False, wanAcceptance=False,
                  performanceMeasurement=False, liveWebsiteContentClaimed=False,
                  scope=__doc__, commands=[], inputs=[], screenshots=[])

    def command(parts, timeout=45, check=True):
        row = dict(command=list(map(str, parts)), startedAtUnixNs=time.time_ns())
        report['commands'].append(row)
        try:
            result = subprocess.run(row['command'], stdin=subprocess.DEVNULL,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    timeout=timeout, check=False)
            row.update(exitCode=result.returncode, stdoutBytes=len(result.stdout),
                       stdoutSha256=hashlib.sha256(result.stdout).hexdigest(),
                       stderr=result.stderr.decode('utf-8', 'replace')[:8192])
            if check:
                result.check_returncode()
            return result.stdout
        except Exception as error:
            row.update(errorType=type(error).__name__, error=str(error))
            raise
        finally:
            row['completedAtUnixNs'] = time.time_ns()
            write(args.out / 'capture.json', report)

    def adb(*parts, **options):
        return command([args.adb, '-s', args.serial, *parts], **options)

    def screenshot(name):
        raw = adb('exec-out', 'screencap', '-p', timeout=30)
        if (len(raw) < 33 or raw[:8] != b'\x89PNG\r\n\x1a\n'
                or raw[12:16] != b'IHDR' or struct.unpack('>II', raw[16:24]) != (WIDTH, HEIGHT)):
            raise ValueError('Device did not return the requested complete PNG screenshot')
        (args.out / name).write_bytes(raw)
        report['screenshots'].append(dict(file=name, bytes=len(raw),
            sha256=hashlib.sha256(raw).hexdigest(), width=WIDTH, height=HEIGHT,
            acquiredBy='adb exec-out screencap -p', capturedAtUnixNs=time.time_ns()))

    def tap(node, reason):
        box = bounds(node)
        x, y = (box[0] + box[2]) // 2, (box[1] + box[3]) // 2
        report['inputs'].append(dict(action='tap', reason=reason, x=x, y=y,
                                     observedBounds=list(box), atUnixNs=time.time_ns()))
        adb('shell', 'input', 'tap', str(x), str(y))

    def wait_for(capture, predicate, name, seconds=45):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            xml = capture.read(deadline=deadline)
            (args.out / (name + '.xml')).write_text(xml)
            if predicate(xml):
                return xml
            time.sleep(.25)
        raise TimeoutError('Actual native screen did not become ready: ' + name)

    device_ready = False
    try:
        # Reuse the existing APK/source and reviewed SDK validators. This step
        # cannot turn a different APK or a source-only preview into app evidence.
        from profile_invocation_contract import expected_build
        from caret_build_identity import audit_apk, validate_sdk_receipt, embedded_identity
        git = lambda *parts: command(['git', '-C', str(args.root), *parts]).decode().strip()
        source, tree = git('rev-parse', 'HEAD'), git('rev-parse', 'HEAD^{tree}')
        if git('status', '--porcelain'):
            raise ValueError('A clean committed screenshot source is required')
        build = (args.root / 'app/build.gradle').read_text()
        version = re.search(r"versionName '([^']+)'", build).group(1)
        code = int(re.search(r'versionCode (\d+)', build).group(1))
        identity = expected_build(args.apk, source, tree, version, code)
        native = args.root / 'work/native-caret-sdk'
        sdk = validate_sdk_receipt(native / 'sdk-build-receipt.json', native / 'geckoview-caret.aar',
                                  args.root, args.build_work / 'geckoview.aar')
        if audit_apk(args.apk)['embeddedBuildIdentity'] != embedded_identity(sdk, native / 'sdk-build-receipt.json'):
            raise ValueError('Compiled APK and reviewed SDK receipts differ')
        command([args.apksigner, 'verify', '--verbose', str(args.apk)])
        badging = command([args.aapt2, 'dump', 'badging', str(args.apk)]).decode()
        if (not badging.startswith(f"package: name='{PACKAGE}' versionCode='{code}' versionName='{version}'")
                or 'application-debuggable' in badging or "native-code: 'x86_64'" not in badging):
            raise ValueError('Unexpected package, version, debuggability or ABI')
        report['buildIdentity'] = dict(identity, runnerSha256=sha(__file__),
            sdkReceiptSha256=sha(native / 'sdk-build-receipt.json'))

        if (adb('shell', 'getprop', 'ro.kernel.qemu').strip() != b'1'
                or adb('shell', 'getprop', 'ro.build.version.sdk').strip() != b'35'):
            raise ValueError('Only the disposable API 35 emulator is supported')
        device_ready = True
        report['actualAndroidExecution'] = True
        report['device'] = {key: adb('shell', 'getprop', key).decode().strip() for key in
            ('ro.build.fingerprint', 'ro.product.model', 'ro.product.cpu.abi', 'ro.build.version.sdk')}
        adb('shell', 'wm', 'size', f'{WIDTH}x{HEIGHT}')
        adb('shell', 'wm', 'density', str(DENSITY))
        adb('shell', 'settings', 'put', 'system', 'font_scale', '1.0')
        adb('shell', 'settings', 'put', 'system', 'accelerometer_rotation', '0')
        adb('shell', 'settings', 'put', 'system', 'user_rotation', '0')
        adb('shell', 'cmd', 'uimode', 'night', 'no')
        adb('shell', 'input', 'keyevent', '82')
        adb('install', '-r', str(args.apk), timeout=120)
        installed_path = adb('shell', 'pm', 'path', PACKAGE).decode().strip()
        if not re.fullmatch(r'package:/data/app/[A-Za-z0-9_./=+~-]+/base\.apk', installed_path):
            raise ValueError('Expected one installed synthetic APK')
        installed_path = installed_path.removeprefix('package:')
        installed_sha = adb('shell', 'sha256sum', installed_path).decode().split()[0]
        if installed_sha != identity['apkSha256']:
            raise ValueError('Installed APK bytes differ from the committed build')
        report['installedApk'] = dict(path=installed_path, sha256=installed_sha)
        if adb('shell', 'pm', 'clear', PACKAGE).strip() != b'Success':
            raise ValueError('Disposable visual fixture reset failed')
        adb('shell', 'am', 'start', '-W', '-n', COMPONENT, '--es', 'visualAction', 'chat')
        capture = UiVisualCapture(adb=args.adb, serial=args.serial, source=source,
                                  diagnostics=args.out / 'hierarchy-attempts.json')
        xml = wait_for(capture, lambda value: navigation(value) is not None and capsule(value) is not None,
                       'initial')
        if not expanded(xml):
            # Exercise the real tap interaction, then cancel without submitting.
            # Dismissing the editor leaves the real toolbar expanded for review.
            tap(capsule(xml), 'Open the address editor and expand the actual header')
            xml = wait_for(capture, lambda value: button(value, '取消') is not None
                           and bool(nodes(value, lambda node: node.get('text') == '打开网址')), 'address-editor')
            screenshot('address-editor.png')
            tap(button(xml, '取消'), 'Cancel URL input without navigating')
        xml = wait_for(capture, lambda value: navigation(value) is not None and expanded(value)
                       and capsule(value) is not None
                       and not nodes(value, lambda node: node.get('text') == '打开网址'), 'glass-navigation')
        activity = adb('shell', 'dumpsys', 'activity', 'activities').decode('utf-8', 'replace')
        (args.out / 'activity.txt').write_text(activity)
        resumed = [line.strip() for line in activity.splitlines()
                   if 'mResumedActivity' in line or 'topResumedActivity' in line]
        if not any(PACKAGE + '/local.pocketchat.MainActivity' in line for line in resumed):
            raise ValueError('The actual production MainActivity is not resumed')
        report['resumedActivity'] = resumed
        report['nativeControls'] = dict(navigation=navigation(xml),
            capsuleBounds=list(bounds(capsule(xml))), capsuleDescription=capsule(xml).get('content-desc'),
            expandedHeader=True, readingIsSeparateSquareControl=True,
            ordinaryConversationHasSelectedNavigation=False)
        report['display'] = dict(size=adb('shell', 'wm', 'size').decode().strip(),
            density=adb('shell', 'wm', 'density').decode().strip(),
            fontScale=adb('shell', 'settings', 'get', 'system', 'font_scale').decode().strip(),
            configuration=adb('shell', 'am', 'get-config').decode().strip())
        screenshot('glass-navigation.png')
        report['status'] = 'captured'
        print(json.dumps(dict(status='captured', sourceCommit=source,
            apkSha256=installed_sha, image='glass-navigation.png',
            scope='Actual Android MainActivity; local unconfigured environment, no live website'), ensure_ascii=False))
    except Exception as error:
        report.update(status='failed', errorType=type(error).__name__, error=str(error))
        if device_ready:
            try:
                screenshot('blocked-screen.png')
            except Exception as capture_error:
                report['failureScreenshotError'] = str(capture_error)
        raise
    finally:
        report['completedAtUnixNs'] = time.time_ns()
        write(args.out / 'capture.json', report)


if __name__ == '__main__':
    main()
