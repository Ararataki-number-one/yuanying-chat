#!/usr/bin/env python3
"""Capture a real, source-bound Android navigation screen and optional motion clip.

This is a new screenshot diagnostic, not a replay or replacement of a frozen UI
acceptance workload. The ordinary integration APK starts its actual MainActivity
with the existing local, unconfigured visual fixture. No website, account, WAN
connection, physical phone or performance acceptance is claimed.
The optional recording is a visual-review artifact, not animation acceptance.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import secrets
import shlex
import struct
import subprocess
import time
import xml.etree.ElementTree as ET

from ui_visual_capture import UiVisualCapture

PACKAGE = 'local.pocketchat.test'
COMPONENT = PACKAGE + '/local.pocketchat.UiVisualIntegrationActivity'
WIDTH, HEIGHT, DENSITY = 1236, 2676, 480
LABELS = ('环境', '网络', '下载', '阅读')
MOTION_WIDTH, MOTION_HEIGHT, MOTION_BIT_RATE, MOTION_SECONDS = 618, 1338, 3500000, 20


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


def native_root_bounds(xml):
    return [node.get('bounds') for node in ET.fromstring(xml)
            if node.get('package') == PACKAGE]


def selected_navigation(xml, expected):
    """A separate diagnostic observation; the static chat assertions stay intact."""
    controls = [button(xml, label) for label in LABELS]
    if any(node is None for node in controls):
        return False
    boxes = [bounds(node) for node in controls]
    return (all(node.get('selected') == ('true' if label == expected else 'false')
                for label, node in zip(LABELS, controls))
            and all(right - left >= 144 and bottom - top >= 144
                    for left, top, right, bottom in boxes)
            and all(boxes[i][2] <= boxes[i + 1][0] for i in range(3))
            and boxes[2][2] < boxes[3][0])


def mp4_metadata(path):
    """Read finalized ISO BMFF track metadata, without rewriting device pixels.

    This detects missing/truncated boxes and a missing video track, not decoder
    correctness or frame pacing. The original MP4 remains available for review.
    """
    data = Path(path).read_bytes()

    def boxes(start, end):
        while start < end:
            if end - start < 8:
                raise ValueError('Truncated MP4 box header')
            length, kind = struct.unpack_from('>I4s', data, start)
            header = 8
            if length == 1:
                if end - start < 16:
                    raise ValueError('Truncated extended MP4 box header')
                length, header = struct.unpack_from('>Q', data, start + 8)[0], 16
            elif length == 0:
                length = end - start
            if length < header or start + length > end:
                raise ValueError('Incomplete MP4 box: ' + repr(kind))
            yield kind, start + header, start + length
            start += length

    top = list(boxes(0, len(data)))
    if (not top or top[0][0] != b'ftyp'
            or not any(kind == b'mdat' and end > start for kind, start, end in top)
            or sum(kind == b'moov' for kind, _, _ in top) != 1):
        raise ValueError('Recording lacks a finalized MP4 header, media or movie box')
    movie = next((start, end) for kind, start, end in top if kind == b'moov')
    videos = []
    for kind, start, end in boxes(*movie):
        if kind != b'trak':
            continue
        track = {name: (left, right) for name, left, right in boxes(start, end)}
        if b'mdia' not in track or b'tkhd' not in track:
            continue
        media = {name: (left, right) for name, left, right in boxes(*track[b'mdia'])}
        if b'hdlr' not in media or b'mdhd' not in media:
            continue
        handler, handler_end = media[b'hdlr']
        if handler_end - handler < 12 or data[handler + 8:handler + 12] != b'vide':
            continue
        track_start, track_end = track[b'tkhd']
        if track_end - track_start < 84:
            raise ValueError('Video track header is incomplete')
        width, height = struct.unpack_from('>II', data, track_end - 8)
        if width & 0xffff or height & 0xffff:
            raise ValueError('Video dimensions are not integral pixels')
        media_start, media_end = media[b'mdhd']
        version = data[media_start] if media_end > media_start else -1
        if version == 0 and media_end - media_start >= 24:
            scale, duration = struct.unpack_from('>II', data, media_start + 12)
        elif version == 1 and media_end - media_start >= 36:
            scale, duration = struct.unpack_from('>IQ', data, media_start + 20)
        else:
            raise ValueError('Video media duration is missing or unsupported')
        if not scale or not duration:
            raise ValueError('Video track has no positive duration')
        videos.append(dict(width=width >> 16, height=height >> 16,
                           durationSeconds=duration / scale))
    if len(videos) != 1:
        raise ValueError('Expected one recorded video track')
    return dict(videos[0], container='MP4', finalizedContainer=True,
                decoderValidation=False, framePacingMeasurement=False)


def capture_motion(args, report, capture, adb, wait_for):
    """Optional, bounded recording of actual controls after the original PNG.

    Official screenrecord options: https://developer.android.com/tools/adb#screenrecord
    AOSP InputShellCommand.sendSwipe emits DOWN/MOVE/UP within one input command:
    https://android.googlesource.com/platform/frameworks/base/+/master/services/core/java/com/android/server/input/InputShellCommand.java
    """
    motion = report['motionReport']
    motion.update(status='started', startedAtUnixNs=time.time_ns(),
                  runNonce=report['runNonce'], sourceCommit=report['buildIdentity']['sourceCommit'],
                  apkSha256=report['installedApk']['sha256'],
                  requestedWidth=MOTION_WIDTH, requestedHeight=MOTION_HEIGHT,
                  requestedBitRate=MOTION_BIT_RATE, timeLimitSeconds=MOTION_SECONDS,
                  acquiredBy='Android screenrecord; adb pull; original MP4 bytes',
                  animationAppearanceVerified=False, animationTimingMeasurement=False,
                  interactionsComplete=False, observations=[], errors=[])
    prefix = '/data/local/tmp/pocketchat-glass-motion-' + report['runNonce']
    remote, pid_file = prefix + '.mp4', prefix + '.pid'
    local = args.out / 'glass-navigation-motion.mp4'
    log = args.out / 'motion-screenrecord.log'
    process = None
    log_stream = None
    recorder_row = None
    device_pid = None
    stop_deadline = None
    gesture_in_flight = False
    cancel_supported = False
    pulled = False

    def save():
        write(args.out / 'capture.json', report)

    def failed(error, stage):
        motion['status'] = 'failed'
        motion['errors'].append(dict(stage=stage, errorType=type(error).__name__, error=str(error)))

    def active_seconds():
        remaining = stop_deadline - time.monotonic() - .4
        if process.poll() is not None or remaining <= 0:
            raise TimeoutError('Recording ended before the observed interaction sequence completed')
        return remaining

    def observe(predicate, name, *, during_recording=True):
        xml = wait_for(capture, predicate, name,
                       seconds=min(8, active_seconds()) if during_recording else 10)
        if during_recording:
            active_seconds()
        motion['observations'].append(dict(file=name + '.xml', sha256=sha(args.out / (name + '.xml')),
            observedAtUnixNs=time.time_ns(),
            recorderStillRunning=process.poll() is None,
            selectedNavigation=[label for label in LABELS
                                if button(xml, label) is not None and button(xml, label).get('selected') == 'true'],
            bounds={label: list(bounds(button(xml, label))) for label in LABELS
                    if button(xml, label) is not None}))
        save()
        return xml

    def swipe(node, reason, *, cancel=False):
        nonlocal gesture_in_flight
        if node is None:
            raise ValueError('The observed motion target is missing')
        box = bounds(node)
        x, y = (box[0] + box[2]) // 2, (box[1] + box[3]) // 2
        # Move 16 dp beyond the actual button's top before releasing. Android
        # cancels its pressed/click state; this never clicks the reading action.
        end_y, duration = (max(0, box[1] - DENSITY // 10), 350) if cancel else (y, 140)
        if cancel and end_y >= box[1]:
            raise ValueError('No safe point outside the observed reading button')
        action = dict(action='swipe-to-cancel' if cancel else 'short-press', reason=reason,
                      start=[x, y], end=[x, end_y], durationMillis=duration,
                      observedBounds=list(box), atUnixNs=time.time_ns())
        report['inputs'].append(action)
        gesture_in_flight = True
        adb('shell', 'input', 'touchscreen', 'swipe', str(x), str(y), str(x), str(end_y),
            str(duration), timeout=min(6, active_seconds()))
        gesture_in_flight = False
        action['completedAtUnixNs'] = time.time_ns()
        active_seconds()
        action['completedWhileRecorderRunning'] = True

    def signal_owned(signal):
        if device_pid is None:
            return False
        cmdline = adb('shell', 'cat', f'/proc/{device_pid}/cmdline', timeout=3, check=False)
        parts = cmdline.rstrip(b'\0').split(b'\0')
        # Never signal an arbitrary recorder or a reused PID: match our exact
        # nonce-owned output path and the screenrecord executable immediately.
        if not parts or parts[0].rsplit(b'/', 1)[-1] != b'screenrecord' or remote.encode() not in parts:
            return False
        adb('shell', 'kill', '-' + signal, str(device_pid), timeout=3)
        motion.setdefault('recorderSignals', []).append(dict(signal=signal, pid=device_pid,
                                                            atUnixNs=time.time_ns()))
        return True

    try:
        help_text = adb('shell', 'input', '--help', timeout=5).decode('utf-8', 'replace')
        (args.out / 'motion-input-help.txt').write_text(help_text)
        cancel_supported = 'motionevent' in help_text and 'CANCEL' in help_text
        # AOSP screenrecord writes its usage text to stderr, including --help.
        record_help = adb('shell', 'screenrecord --help 2>&1', timeout=5).decode('utf-8', 'replace')
        (args.out / 'motion-screenrecord-help.txt').write_text(record_help)
        if 'swipe' not in help_text or any(option not in record_help for option in
                                             ('--size', '--bit-rate', '--time-limit')):
            raise ValueError('The actual device lacks the required documented capture/input options')
        motion['animationScales'] = {key: adb('shell', 'settings', 'get', 'global', key,
            timeout=5).decode().strip() for key in
            ('animator_duration_scale', 'window_animation_scale', 'transition_animation_scale')}
        motion['zeroAnimationScales'] = []
        for key, value in motion['animationScales'].items():
            try:
                if float(value) == 0:
                    motion['zeroAnimationScales'].append(key)
            except ValueError:
                pass  # Preserve unset/non-numeric values without guessing a runtime default.
        motion['animationEvidenceScope'] = ('System animation scale is zero; no visible-animation validation claimed'
            if motion['zeroAnimationScales'] else 'Recorded for visual review; settings unchanged; animation not automatically verified')
        xml = wait_for(capture, lambda value: navigation(value) is not None and expanded(value)
                       and capsule(value) is not None, 'motion-initial', seconds=10)
        motion['initialHierarchySha256'] = sha(args.out / 'motion-initial.xml')
        initial_reading_bounds = bounds(button(xml, '阅读'))
        # The remote shell becomes screenrecord, preserving the exact owned PID.
        shell = ('echo $$ > ' + shlex.quote(pid_file) + '; exec ' + shlex.join([
            'screenrecord', '--verbose', '--size', f'{MOTION_WIDTH}x{MOTION_HEIGHT}',
            '--bit-rate', str(MOTION_BIT_RATE), '--time-limit', str(MOTION_SECONDS), remote]))
        parts = [args.adb, '-s', args.serial, 'shell', shell]
        recorder_row = dict(command=parts, startedAtUnixNs=time.time_ns(), asynchronous=True,
                            timeLimitSeconds=MOTION_SECONDS, finalizationGraceSeconds=8,
                            outputLog=log.name)
        report['commands'].append(recorder_row)
        log_stream = log.open('wb')
        process = subprocess.Popen(parts, stdin=subprocess.DEVNULL, stdout=log_stream,
                                   stderr=subprocess.STDOUT)
        stop_deadline = time.monotonic() + MOTION_SECONDS
        motion['status'] = 'recording'
        save()
        time.sleep(.8)
        raw_pid = adb('shell', 'cat', pid_file, timeout=3).decode().strip()
        if not re.fullmatch(r'[1-9][0-9]{0,8}', raw_pid):
            raise ValueError('Screenrecord did not publish its owned device PID')
        device_pid = int(raw_pid)
        motion['recorderPid'] = device_pid
        motion['firstInputIndex'] = len(report['inputs'])
        active_seconds()
        swipe(button(xml, '下载'), 'Open downloads with an actual 140 ms native short press')
        xml = observe(lambda value: selected_navigation(value, '下载'), 'motion-downloads')
        time.sleep(.55)
        swipe(button(xml, '网络'), 'Move the shared selected background from downloads to network')
        xml = observe(lambda value: selected_navigation(value, '网络'), 'motion-network')
        time.sleep(.55)
        reading = button(xml, '阅读')
        # AppHub retains this same bottom bar while showing its native pages.
        # Require two independently observed layouts to agree before reusing
        # its bounds across Back. A third slow hierarchy read here would spend
        # most of the 20-second clip waiting rather than showing interactions.
        if bounds(reading) != initial_reading_bounds:
            raise ValueError('Reading control moved between the actual chat and network layouts')
        motion['readingBoundsSource'] = dict(hierarchy='motion-network.xml',
            matchesInitialChatHierarchy=True, observedBounds=list(initial_reading_bounds))
        back_input = dict(action='keyevent', keyCode=4,
            reason='Return from the actual native network workspace to the existing chat',
            atUnixNs=time.time_ns())
        report['inputs'].append(back_input)
        adb('shell', 'input', 'keyevent', '4', timeout=min(6, active_seconds()))
        active_seconds()
        back_input.update(completedAtUnixNs=time.time_ns(), completedWhileRecorderRunning=True)
        time.sleep(.55)
        chat = lambda value: (navigation(value) is not None and expanded(value)
                              and capsule(value) is not None
                              and not nodes(value, lambda node: node.get('text') == '退出阅读'))
        swipe(reading, 'Show reading press/release feedback, sliding outside to cancel the action', cancel=True)
        time.sleep(.35)
        # The final read may finish after the recorder's time limit. All inputs
        # must have completed while it was running; this read checks the final
        # real UI state and does not claim to inspect individual video frames.
        observe(chat, 'motion-reading-cancelled', during_recording=False)
        motion['interactionsComplete'] = True
        motion['lastInputIndexExclusive'] = len(report['inputs'])
        motion['readingGestureReleasedOutsideObservedButton'] = True
        motion['returnedToOrdinaryChat'] = True
        # Let the device's documented time limit finalize the MP4 naturally.
        process.wait(timeout=max(1, stop_deadline - time.monotonic() + 8))
        if process.returncode != 0:
            raise RuntimeError('Screenrecord exited with code ' + str(process.returncode))
    except Exception as error:
        failed(error, 'recording-or-interactions')
    finally:
        if gesture_in_flight and cancel_supported:
            try:
                adb('shell', 'input', 'touchscreen', 'motionevent', 'CANCEL', '0', '0', timeout=3)
            except Exception as error:
                failed(error, 'cancel-incomplete-input')
        if process is not None and process.poll() is None:
            try:
                signal_owned('INT')  # AOSP screenrecord handles SIGINT and closes the muxer.
                process.wait(timeout=5)
            except Exception as error:
                failed(error, 'stop-recorder')
                try:
                    signal_owned('KILL')
                except Exception as stop_error:
                    failed(stop_error, 'kill-owned-recorder')
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=3)
        if log_stream is not None:
            log_stream.close()
        if recorder_row is not None:
            recorder_row.update(completedAtUnixNs=time.time_ns(),
                exitCode=process.poll() if process is not None else None)
            if log.is_file():
                recorder_row.update(outputLogBytes=log.stat().st_size, outputLogSha256=sha(log))

    if process is not None:
        try:
            remote_sha = adb('shell', 'sha256sum', remote, timeout=5).decode().split()[0]
            if not re.fullmatch('[0-9a-f]{64}', remote_sha):
                raise ValueError('Recorded MP4 has no valid device checksum')
            adb('pull', remote, str(local), timeout=30)
            pulled = True
            motion['video'] = dict(file=local.name, bytes=local.stat().st_size, sha256=sha(local),
                                   deviceSha256=remote_sha, capturedAtUnixNs=time.time_ns())
            if motion['video']['sha256'] != remote_sha:
                raise ValueError('Pulled video differs from the device recording')
            motion['video'].update(mp4_metadata(local))
            if (motion['video']['width'], motion['video']['height']) != (MOTION_WIDTH, MOTION_HEIGHT):
                raise ValueError('The encoder did not use the requested half-size dimensions')
            if not 0 < motion['video']['durationSeconds'] <= MOTION_SECONDS + 3:
                raise ValueError('Unexpected recorded video duration')
            motion['video']['meetsRequestedReviewLength'] = 12 <= motion['video']['durationSeconds'] <= 21
            if motion['interactionsComplete'] and not motion['errors']:
                motion['status'] = 'captured'
        except Exception as error:
            failed(error, 'retrieve-or-validate-video')
        finally:
            try:
                # Only remove this invocation's temporary files, never app data.
                adb('shell', 'rm', '-f', pid_file, *([remote] if pulled else []), timeout=3)
            except Exception as error:
                failed(error, 'remove-owned-temporary-files')
    motion['completedAtUnixNs'] = time.time_ns()
    save()


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
    report = dict(schema=1, status='started', startedAtUnixNs=time.time_ns(), runNonce=secrets.token_hex(16),
                  diagnostic='split-glass-navigation', scene='actual-main-activity',
                  actualAndroidExecution=False, applicationAcceptance=False,
                  physicalPhoneAcceptance=False, wanAcceptance=False,
                  performanceMeasurement=False, liveWebsiteContentClaimed=False,
                  scope=__doc__, commands=[], inputs=[], screenshots=[],
                  staticScreenshotStatus='pending',
                  motionReport=dict(status='not-attempted', optional=True,
                                    applicationAcceptance=False, physicalPhoneAcceptance=False,
                                    wanAcceptance=False, performanceMeasurement=False))

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
        if len(raw) < 33 or raw[:8] != b'\x89PNG\r\n\x1a\n' or raw[12:16] != b'IHDR':
            diagnostic = Path(name).stem + '.raw'
            (args.out / diagnostic).write_bytes(raw)
            report.setdefault('screenshotErrors', []).append(dict(file=diagnostic,
                bytes=len(raw), prefixHex=raw[:64].hex(), reason='PNG signature/header missing'))
            raise ValueError('Device returned a non-PNG screenshot; raw bytes retained in ' + diagnostic)
        # Preserve the device's original pixels before checking metadata. A wm
        # logical-size override need not change the physical capture dimensions.
        (args.out / name).write_bytes(raw)
        actual_width, actual_height = struct.unpack('>II', raw[16:24])
        report['screenshots'].append(dict(file=name, bytes=len(raw),
            sha256=hashlib.sha256(raw).hexdigest(), width=actual_width, height=actual_height,
            requestedLogicalWidth=WIDTH, requestedLogicalHeight=HEIGHT,
            matchesRequestedLogicalSize=(actual_width, actual_height) == (WIDTH, HEIGHT),
            acquiredBy='adb exec-out screencap -p', capturedAtUnixNs=time.time_ns()))
        if raw[-12:] != b'\x00\x00\x00\x00IEND\xaeB`\x82':
            raise ValueError('Device PNG is incomplete; original bytes retained in ' + name)

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
        report['initialNativeRootBounds'] = native_root_bounds(xml)
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
            rootBounds=native_root_bounds(xml),
            expandedHeader=True, readingIsSeparateSquareControl=True,
            ordinaryConversationHasSelectedNavigation=False)
        report['display'] = dict(size=adb('shell', 'wm', 'size').decode().strip(),
            density=adb('shell', 'wm', 'density').decode().strip(),
            fontScale=adb('shell', 'settings', 'get', 'system', 'font_scale').decode().strip(),
            configuration=adb('shell', 'am', 'get-config').decode().strip())
        report['stillSettleMillis'] = 350
        time.sleep(.35)
        screenshot('glass-navigation.png')
        report['status'] = 'captured'
        report['staticScreenshotStatus'] = 'captured'
        # A failed optional clip must never discard the original successful PNG.
        try:
            capture_motion(args, report, capture, adb, wait_for)
        except Exception as error:
            report['motionReport'].update(status='failed', errorType=type(error).__name__, error=str(error))
        print(json.dumps(dict(status='captured', sourceCommit=source,
            apkSha256=installed_sha, image='glass-navigation.png',
            motionStatus=report['motionReport']['status'],
            scope='Actual Android MainActivity; local unconfigured environment, no live website'), ensure_ascii=False))
    except Exception as error:
        report.update(status='failed', staticScreenshotStatus='failed', errorType=type(error).__name__, error=str(error))
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
