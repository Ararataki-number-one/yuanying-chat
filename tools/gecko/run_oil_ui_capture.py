#!/usr/bin/env python3
"""Draft: fixed native UI diagnostic captures; no publication or release verdict."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import sys
import time
import uuid
import xml.etree.ElementTree as ET

PACKAGE = 'local.pocketchat.test'
COMPONENT = PACKAGE + '/local.pocketchat.UiVisualIntegrationActivity'
LABELS = {
    'chat': '会话', 'environments': '环境管理', 'network': '固定测试出口',
    'downloads': '项目资料与界面设计说明.pdf', 'settings': '启动与界面',
    'network-menu': '导入网络', 'environment-picker': '切换环境',
    'appearance': '白天与黑夜', 'share-preview': '分享整条线路', 'delete-file': '删除文件',
    'subscription-form': '添加入口订阅', 'exit-form': '添加固定出口',
}


def matrix():
    core = ('chat', 'environments', 'network', 'downloads', 'settings')
    rows = [(theme, width, 640, 1, scene) for theme in ('light', 'dark')
            for width in (360, 412) for scene in core]
    rows += [('light', 360, 640, 2, scene) for scene in
             ('chat', 'settings', 'downloads', 'network-menu', 'environment-picker')]
    rows += [('light', 640, 360, 1, scene) for scene in
             ('chat', 'settings', 'environment-picker')]
    rows += [(theme, 360, 640, 1, scene) for theme in ('light', 'dark')
             for scene in ('appearance', 'share-preview', 'delete-file')]
    rows += [(theme, 360, 640, 1, scene) for theme in ('light', 'dark')
             for scene in ('subscription-form', 'exit-form')]
    rows += [('light', 360, 640, 2, scene) for scene in ('subscription-form', 'exit-form')]
    return rows


def sha(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def png_size(raw):
    if len(raw) < 33 or raw[:8] != b'\x89PNG\r\n\x1a\n' or raw[12:16] != b'IHDR':
        raise ValueError('screencap did not return a PNG')
    return struct.unpack('>II', raw[16:24])


def target_visible(xml, scene, width_pixels, height_pixels):
    for node in ET.fromstring(xml).iter('node'):
        if (node.get('package') != PACKAGE or node.get('text') != LABELS[scene]
                or node.get('visible-to-user') == 'false'):
            continue
        bounds = re.fullmatch(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', node.get('bounds', ''))
        if bounds:
            left, top, right, bottom = map(int, bounds.groups())
            if 0 <= left < right <= width_pixels and 0 <= top < bottom <= height_pixels:
                return True
    return False


def installed_path(raw):
    paths = raw.strip().splitlines()
    if len(paths) != 1 or not re.fullmatch(r'package:/data/app/[A-Za-z0-9_./=+~-]+/base\.apk', paths[0]):
        raise ValueError('Expected one installed test base APK')
    return paths[0].removeprefix('package:')


def verify_badging(raw, version, code):
    expected = f"package: name='{PACKAGE}' versionCode='{code}' versionName='{version}'"
    if not raw.startswith(expected) or 'application-debuggable' in raw:
        raise ValueError('Actual APK manifest package/version/debuggability differs')


def build_identity(args, command):
    # Reuse production source/SDK validators; do not invent a local CI receipt.
    sys.path.insert(0, str(args.root / 'tools/gecko'))
    from profile_invocation_contract import expected_build
    from caret_build_identity import audit_apk, validate_sdk_receipt, embedded_identity
    git = lambda *parts: command(['git', '-C', str(args.root), *parts]).decode().strip()
    source, tree = git('rev-parse', 'HEAD'), git('rev-parse', 'HEAD^{tree}')
    if git('status', '--porcelain'):
        raise ValueError('A clean committed UI source is required')
    text = (args.root / 'app/build.gradle').read_text()
    version = re.search(r"versionName '([^']+)'", text).group(1)
    code = int(re.search(r'versionCode (\d+)', text).group(1))
    identity = expected_build(args.apk, source, tree, version, code)
    native = args.root / 'work/native-caret-sdk'
    sdk = validate_sdk_receipt(native / 'sdk-build-receipt.json', native / 'geckoview-caret.aar',
                              args.root, args.root / 'work/gecko-integration/geckoview.aar')
    audit = audit_apk(args.apk)
    if audit['embeddedBuildIdentity'] != embedded_identity(sdk, native / 'sdk-build-receipt.json'):
        raise ValueError('APK and compiled SDK receipts differ')
    command([args.apksigner, 'verify', '--verbose', str(args.apk)])
    badging = command([args.aapt2, 'dump', 'badging', str(args.apk)]).decode()
    verify_badging(badging, version, code)
    return dict(identity, sdkReceiptSha256=sha(native / 'sdk-build-receipt.json'),
                runnerSha256=sha(__file__), uiCaptureHelperSha256=sha(args.root / 'tools/gecko/ui_visual_capture.py'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('verify-build', 'capture'))
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--apk', required=True, type=Path)
    parser.add_argument('--aapt2', required=True)
    parser.add_argument('--apksigner', required=True)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--adb')
    parser.add_argument('--serial', default='emulator-5554', choices=('emulator-5554',))
    parser.add_argument('--round', required=True, choices=('1', '2'))
    args = parser.parse_args()
    args.root, args.apk, args.out = args.root.resolve(), args.apk.resolve(), args.out.resolve()
    # A run has a new directory; never replace a failed/earlier round.
    args.out.mkdir(parents=True, exist_ok=False)
    report = dict(schema=1, mode=args.mode, round=int(args.round), status='in_progress',
                  actualAndroidExecution=False, releaseAcceptance=False, performanceMeasurement=False,
                  visualReview='pending', transport='ordinary-emulator-adb',
                  scope='Production native UI with existing synthetic fixture records. No real ChatGPT/WAN/upload/input-gate claim.',
                  plannedScreens=[dict(theme=t, widthDp=w, heightDp=h, fontScale=f, scene=s) for t,w,h,f,s in matrix()],
                  commands=[], screenshots=[])

    def command(parts, timeout=60, binary=False):
        row = dict(command=[str(x) for x in parts], startedAtUnixNs=time.time_ns())
        report['commands'].append(row)
        try:
            result = subprocess.run(parts, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, timeout=timeout, check=False)
            row.update(exitCode=result.returncode, stdoutBytes=len(result.stdout),
                       stdoutSha256=hashlib.sha256(result.stdout).hexdigest(),
                       stderr=result.stderr.decode('utf-8', 'replace'))
            if not binary:
                row['stdout'] = result.stdout.decode('utf-8', 'replace')
            result.check_returncode()
            return result.stdout
        except subprocess.TimeoutExpired as error:
            row.update(timedOut=True, stdout=(error.stdout or b'').decode('utf-8', 'replace'),
                       stderr=(error.stderr or b'').decode('utf-8', 'replace'))
            raise
        finally:
            row['completedAtUnixNs'] = time.time_ns()
            write(args.out / 'capture-results.json', report)

    adb = lambda *parts, **kw: command([args.adb, '-s', args.serial, *parts], **kw)
    try:
        report['buildIdentity'] = build_identity(args, command)
        if args.mode == 'verify-build':
            report['status'] = 'build-verified'
            return
        if not args.adb:
            raise ValueError('--adb is required for capture')
        # This runner clears only the test package on a disposable API35 emulator.
        if adb('shell', 'getprop', 'ro.kernel.qemu').strip() != b'1' or adb('shell', 'getprop', 'ro.build.version.sdk').strip() != b'35':
            raise ValueError('A disposable API35 emulator is required')
        report['actualAndroidExecution'] = True
        report['device'] = {key: adb('shell', 'getprop', key).decode().strip() for key in
                            ('ro.build.fingerprint', 'ro.product.model', 'ro.product.cpu.abi', 'ro.build.version.sdk')}
        for key in ('window_animation_scale', 'transition_animation_scale', 'animator_duration_scale'):
            adb('shell', 'settings', 'put', 'global', key, '1')
        adb('shell', 'settings', 'put', 'system', 'accelerometer_rotation', '0')
        adb('shell', 'settings', 'put', 'system', 'user_rotation', '0')
        report['device']['fixedSettings'] = {
            key: adb('shell', 'settings', 'get', namespace, key).decode().strip()
            for namespace, key in [('global', 'window_animation_scale'),
                                   ('global', 'transition_animation_scale'),
                                   ('global', 'animator_duration_scale'),
                                   ('system', 'accelerometer_rotation'), ('system', 'user_rotation')]}
        if any(float(value) != (0 if key in ('accelerometer_rotation', 'user_rotation') else 1)
               for key, value in report['device']['fixedSettings'].items()):
            raise ValueError('Actual animation/rotation settings differ')
        adb('install', '-r', str(args.apk), timeout=120)
        path = installed_path(adb('shell', 'pm', 'path', PACKAGE).decode())
        installed = adb('shell', 'sha256sum', path).decode().split()[0]
        if installed != report['buildIdentity']['apkSha256']:
            raise ValueError('Installed APK bytes differ from verified source APK')
        report['installedApk'] = dict(path=path, sha256=installed, method='pm path + device sha256sum')
        if adb('shell', 'pm', 'clear', PACKAGE).strip() != b'Success':
            raise ValueError('Synthetic test data reset failed')
        from ui_visual_capture import UiVisualCapture
        capture = UiVisualCapture(adb=args.adb, serial=args.serial,
                                  source=report['buildIdentity']['sourceCommit'],
                                  diagnostics=args.out / 'hierarchy-attempts.json')
        for index, (theme, width, height, font, scene) in enumerate(matrix(), 1):
            stem = f'{index:02d}-{theme}-{width}x{height}-font{font}-{scene}'
            report['currentScene'] = stem
            print(json.dumps(dict(event='capture-start', scene=stem)), flush=True)
            adb('shell', 'am', 'force-stop', PACKAGE)
            adb('shell', 'wm', 'size', f'{width * 3}x{height * 3}')
            adb('shell', 'wm', 'density', '480')
            adb('shell', 'settings', 'put', 'system', 'font_scale', str(font))
            adb('shell', 'cmd', 'uimode', 'night', 'yes' if theme == 'dark' else 'no')
            launch = ['shell', 'am', 'start', '-W', '-n', COMPONENT, '--es', 'visualAction', scene]
            # Existing download fixture emits owned native layout evidence.
            nonce = uuid.uuid4().hex
            launch += ['--es', 'visualNonce', nonce]
            adb(*launch, timeout=45)
            deadline = time.monotonic() + 35
            while True:
                xml = capture.read(deadline=deadline)
                (args.out / (stem + '.xml')).write_text(xml)
                if target_visible(xml, scene, width * 3, height * 3):
                    break
                if time.monotonic() >= deadline:
                    raise TimeoutError('Expected current scene label did not appear: ' + scene)
                time.sleep(.2)
            observed = dict(size=adb('shell', 'wm', 'size').decode(),
                            density=adb('shell', 'wm', 'density').decode(),
                            fontScale=adb('shell', 'settings', 'get', 'system', 'font_scale').decode(),
                            configuration=adb('shell', 'am', 'get-config').decode())
            if float(observed['fontScale']) != font or int(re.findall(r'density: (\d+)', observed['density'])[-1]) != 480:
                raise ValueError('Actual display/font settings differ')
            night = 'night' if theme == 'dark' else 'notnight'
            if not re.search(r'(?:^|[-\s])' + night + r'(?:[-\s]|$)', observed['configuration']):
                raise ValueError('Resolved device night configuration differs')
            raw = adb('exec-out', 'screencap', '-p', binary=True, timeout=30)
            (args.out / (stem + '.png')).write_bytes(raw)
            if png_size(raw) != (width * 3, height * 3):
                raise ValueError('Actual screenshot geometry differs')
            report['screenshots'].append(dict(index=index, scene=scene, themeRequested=theme,
                widthDp=width, heightDp=height, fontScale=font, observedDevice=observed,
                nativeAppearancePixelReview='pending', image=stem + '.png', xml=stem + '.xml',
                readinessScrolls=0, readinessTarget=LABELS[scene],
                imageSha256=sha(args.out / (stem + '.png')), xmlSha256=sha(args.out / (stem + '.xml')),
                fixtureNonce=nonce, capturedAtUnixNs=time.time_ns()))
        report['status'] = 'captured'
    except Exception as error:
        report.update(status='failed', errorType=type(error).__name__, error=str(error))
        # Read-only failure artifacts, never restart/replay a failed scene.
        if report['actualAndroidExecution'] and args.adb:
            try:
                raw = adb('exec-out', 'screencap', '-p', binary=True, timeout=15)
                (args.out / 'failure-state.png').write_bytes(raw)
                report['failureScreenshot'] = dict(path='failure-state.png', sha256=sha(args.out / 'failure-state.png'))
            except Exception as diagnostic:
                report['failureScreenshotError'] = str(diagnostic)
        raise
    finally:
        write(args.out / 'capture-results.json', report)


if __name__ == '__main__':
    main()
