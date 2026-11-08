#!/usr/bin/env python3
"""Capture a real, source-bound Android navigation screen and optional motion clip.

This is a new screenshot diagnostic, not a replay or replacement of a frozen UI
acceptance workload. The ordinary integration APK starts its actual MainActivity
with the existing local, unconfigured visual fixture. No website, account, WAN
connection, physical phone or performance acceptance is claimed.
The optional recording is a visual-review artifact, not animation acceptance.
An additional native-network screenshot runs after recording, with its own status.
Navigation typography is measured separately at default and enlarged font scales;
its component fixture is never presented as the actual MainActivity screenshot.
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
MOTION_WIDTH, MOTION_HEIGHT, MOTION_BIT_RATE, MOTION_SECONDS = 618, 1338, 3500000, 60
MOTION_MIN_WALL_SECONDS, MOTION_OBSERVATION_SECONDS, MOTION_RELEASE_SETTLE_SECONDS = 20, 20, 1.2
MOTION_REVIEW_MIN_SECONDS = 12


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


def navigation_geometry(xml):
    """Measure the actual default-screen touch views, independent of selection.

    The first three buttons have symmetric padding within their shared capsule.
    Their union therefore measures that group's horizontal screen alignment;
    reading is deliberately excluded from the centered group.
    """
    controls = [button(xml, label) for label in LABELS]
    if any(node is None for node in controls):
        return None
    boxes = [bounds(node) for node in controls]
    group = (min(box[0] for box in boxes[:3]), min(box[1] for box in boxes[:3]),
             max(box[2] for box in boxes[:3]), max(box[3] for box in boxes[:3]))
    reading = boxes[-1]
    group_center = [(group[0] + group[2]) / 2, (group[1] + group[3]) / 2]
    offset = group_center[0] - WIDTH / 2
    minimum_touch_px = (48 * DENSITY + 159) // 160
    checks = dict(
        threeItemGroupCentered=abs(offset) <= 1,
        leftToRightOrder=all(boxes[i][2] <= boxes[i + 1][0] for i in range(3)),
        readingSeparateToRight=group[2] < reading[0],
        readingIsSquare=abs((reading[2] - reading[0]) - (reading[3] - reading[1])) <= 3,
        minimumTouchTargets=all(right - left >= minimum_touch_px and bottom - top >= minimum_touch_px
                                for left, top, right, bottom in boxes))
    return dict(coordinateSpace='native XML screen pixels', screenWidthPx=WIDTH,
                configuredDensityDpi=DENSITY, screenCenterX=WIDTH / 2,
                groupLabels=list(LABELS[:3]), threeItemGroupBounds=list(group),
                threeItemGroupCenter=group_center, horizontalCenterOffsetPx=offset,
                allowedCenterOffsetPx=1, readingBounds=list(reading),
                readingGapPx=reading[0] - group[2],
                leftToRightLabels=[label for label, box in sorted(zip(LABELS, boxes), key=lambda item: item[1][0])],
                minimumTouchTargetDp=48, minimumTouchTargetPx=minimum_touch_px,
                bounds={label: list(box) for label, box in zip(LABELS, boxes)},
                selected={label: node.get('selected') for label, node in zip(LABELS, controls)},
                checks=checks, valid=all(checks.values()))


def navigation(xml):
    geometry = navigation_geometry(xml)
    if geometry is None or not geometry['valid']:
        return None
    if any(value == 'true' for value in geometry['selected'].values()):
        return None  # The ordinary conversation is not one of the four actions.
    return geometry['bounds']


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
    geometry = navigation_geometry(xml)
    if geometry is None or not geometry['valid']:
        return False
    return all(geometry['selected'][label] == ('true' if label == expected else 'false')
               for label in LABELS)


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

    The 60-second hard cap allows bounded hierarchy acquisition. A successful
    clip stops after all four inputs and their release tail, with a 20-second
    wall-time floor. The encoded MP4 duration is reported independently.

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
                  minimumRecordingWallSeconds=MOTION_MIN_WALL_SECONDS,
                  requestedReviewMinSeconds=MOTION_REVIEW_MIN_SECONDS,
                  requestedReviewMaxSeconds=MOTION_SECONDS,
                  observationTimeoutSeconds=MOTION_OBSERVATION_SECONDS,
                  releaseSettleMillis=round(MOTION_RELEASE_SETTLE_SECONDS * 1000),
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
    recording_started = None
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
                       seconds=min(MOTION_OBSERVATION_SECONDS, active_seconds())
                       if during_recording else MOTION_OBSERVATION_SECONDS)
        if during_recording:
            active_seconds()
        motion['observations'].append(dict(file=name + '.xml', sha256=sha(args.out / (name + '.xml')),
            observedAtUnixNs=time.time_ns(),
            recorderStillRunning=process.poll() is None,
            selectedNavigation=[label for label in LABELS
                                if button(xml, label) is not None and button(xml, label).get('selected') == 'true'],
            bounds={label: list(bounds(button(xml, label))) for label in LABELS
                    if button(xml, label) is not None}, geometry=navigation_geometry(xml)))
        save()
        return xml

    def swipe(node, reason, *, cancel=False):
        nonlocal gesture_in_flight
        if node is None:
            raise ValueError('The observed motion target is missing')
        box = bounds(node)
        x, y = (box[0] + box[2]) // 2, (box[1] + box[3]) // 2
        end_x, end_y, duration = x, y, 140
        if cancel:
            # Trace the material hotspot from 25% to 80% of the observed width,
            # releasing 16 dp above the button to cancel its reading action.
            width = box[2] - box[0]
            x, end_x = box[0] + width // 4, box[0] + width * 4 // 5
            end_y, duration = max(0, box[1] - DENSITY // 10), 400
        if cancel and end_y >= box[1]:
            raise ValueError('No safe point outside the observed reading button')
        action = dict(action='swipe-to-cancel' if cancel else 'short-press', reason=reason,
                      start=[x, y], end=[end_x, end_y], durationMillis=duration,
                      observedBounds=list(box), atUnixNs=time.time_ns())
        report['inputs'].append(action)
        gesture_in_flight = True
        adb('shell', 'input', 'touchscreen', 'swipe', str(x), str(y), str(end_x), str(end_y),
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
        # The pinned API 35 image rejects --help. A no-argument input command
        # requests usage without injecting events; retain either output stream.
        help_text = adb('shell', 'input 2>&1', timeout=5).decode('utf-8', 'replace')
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
                       and capsule(value) is not None, 'motion-initial', seconds=MOTION_OBSERVATION_SECONDS)
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
        recording_started = time.monotonic()
        stop_deadline = recording_started + MOTION_SECONDS
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
        # its bounds across Back. The final hierarchy verifies the actual chat
        # after the reading gesture without a third acquisition before input.
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
        swipe(reading, 'Move the reading material hotspot diagonally, releasing outside to cancel the action', cancel=True)
        sequence = report['inputs'][motion['firstInputIndex']:]
        if ([item['action'] for item in sequence] !=
                ['short-press', 'short-press', 'keyevent', 'swipe-to-cancel']
                or not all(item.get('completedWhileRecorderRunning') for item in sequence)):
            raise ValueError('The four actual inputs did not all complete inside the recording')
        motion['lastGestureCompletedAtUnixNs'] = sequence[-1]['completedAtUnixNs']
        # Uiautomator needs time to observe the real route transitions. Give it
        # bounded headroom, but do not fill a successful movie with idle time.
        # Keep the old 20-second wall-time floor and a visible release tail.
        settle = max(MOTION_RELEASE_SETTLE_SECONDS,
                     recording_started + MOTION_MIN_WALL_SECONDS - time.monotonic())
        if settle > active_seconds():
            raise TimeoutError('Recording has no remaining budget for the complete release tail')
        motion['postGestureWaitSeconds'] = settle
        time.sleep(settle)
        active_seconds()
        motion['recorderStopReason'] = 'four-input-sequence-and-release-tail-completed'
        motion['recordingWallSecondsAtStopRequest'] = time.monotonic() - recording_started
        if not signal_owned('INT'):
            raise RuntimeError('The completed recording no longer has its verified owned recorder')
        process.wait(timeout=8)
        recorder_row.update(completedAtUnixNs=time.time_ns(), exitCode=process.returncode)
        motion['recorderStoppedAtUnixNs'] = recorder_row['completedAtUnixNs']
        if process.returncode != 0:
            raise RuntimeError('Screenrecord exited with code ' + str(process.returncode))
        # Only this final state check runs after muxer finalization. All four
        # inputs and the release tail were checked while the recorder was live.
        # This remains a real hierarchy assertion, not video-frame inspection.
        observe(chat, 'motion-reading-cancelled', during_recording=False)
        motion['interactionsComplete'] = True
        motion['lastInputIndexExclusive'] = len(report['inputs'])
        motion['readingGestureReleasedOutsideObservedButton'] = True
        motion['returnedToOrdinaryChat'] = True
        motion['finalStateVerifiedAfterRecorderStop'] = True
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
            recorder_row.setdefault('completedAtUnixNs', time.time_ns())
            recorder_row['exitCode'] = process.poll() if process is not None else None
            if log.is_file():
                recorder_row.update(outputLogBytes=log.stat().st_size, outputLogSha256=sha(log))
        if 'firstInputIndex' in motion:
            motion['lastInputIndexExclusive'] = len(report['inputs'])

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
            duration = motion['video']['durationSeconds']
            motion['video']['meetsRequestedReviewLength'] = (
                motion['requestedReviewMinSeconds'] <= duration <= motion['requestedReviewMaxSeconds'])
            motion['video']['meetsLegacy12To21SecondLength'] = 12 <= duration <= 21
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


def capture_native_backdrop_preview(args, report, capture, adb, wait_for, tap, screenshot):
    """Photograph the actual native workspace after the bounded movie has ended."""
    preview = report['nativeBackdropPreview']
    preview.update(status='started', startedAtUnixNs=time.time_ns(),
        runNonce=report['runNonce'], sourceCommit=report['buildIdentity']['sourceCommit'],
        apkSha256=report['installedApk']['sha256'], firstInputIndex=len(report['inputs']),
        scene='actual-main-activity-native-network', imageCaptured=False,
        returnedToOrdinaryChat=False, errors=[],
        scope='Real native workspace and original device PNG; no website, WAN or GPU acceptance.')
    network_tapped = False
    network_observed = False

    def chat(xml):
        return (navigation(xml) is not None and expanded(xml) and capsule(xml) is not None
                and not nodes(xml, lambda node: node.get('text') in ('打开网址', '退出阅读')))

    def known_screen(xml):
        return chat(xml) or selected_navigation(xml, '网络') or selected_navigation(xml, '下载')

    def back_to_chat(reason, name):
        action = dict(action='keyevent', keyCode=4, reason=reason,
                      phase='native-backdrop-preview', atUnixNs=time.time_ns())
        report['inputs'].append(action)
        adb('shell', 'input', 'keyevent', '4', timeout=6)
        action['completedAtUnixNs'] = time.time_ns()
        return wait_for(capture, chat, name, seconds=15)

    def failure(error, stage):
        preview['errors'].append(dict(stage=stage, errorType=type(error).__name__, error=str(error)))

    try:
        xml = wait_for(capture, known_screen, 'native-backdrop-initial', seconds=15)
        initial_name = 'native-backdrop-initial.xml'
        if not chat(xml):
            # An optional movie failure may leave one of these observed native
            # pages open. Recover only from a recognized page, never a dialog.
            xml = back_to_chat('Restore the observed native workspace before the separate still preview',
                               'native-backdrop-chat-before')
            initial_name = 'native-backdrop-chat-before.xml'
            preview['restoredChatBeforePreview'] = True
        preview['initialChatHierarchy'] = dict(file=initial_name, sha256=sha(args.out / initial_name))
        tap(button(xml, '网络'), 'Open the actual native network workspace for a separate backdrop screenshot')
        network_tapped = True
        xml = wait_for(capture, lambda value: selected_navigation(value, '网络'),
                       'native-backdrop-network-selected', seconds=15)
        network_observed = True
        # Wait for the existing native content, without inserting fixture rows
        # or pressing any connect, verification, import or network-test control.
        ready = lambda value: (selected_navigation(value, '网络')
            and bool(nodes(value, lambda node: node.get('class') == 'android.widget.ScrollView'))
            and not nodes(value, lambda node: node.get('text', '').startswith('正在读取窗口网络')))
        xml = wait_for(capture, ready, 'native-backdrop-network-before-scroll', seconds=20)
        scrolls = nodes(xml, lambda node: node.get('class') == 'android.widget.ScrollView'
                        and node.get('scrollable') == 'true')
        preview['scroll'] = dict(inputIssued=False, observedScrollableViews=len(scrolls))
        if len(scrolls) == 1:
            box = bounds(scrolls[0])
            nav_top = min(bounds(button(xml, label))[1] for label in LABELS)
            safe_top = box[1] + DENSITY // 10
            safe_bottom = min(box[3], nav_top) - DENSITY // 10
            if box[2] - box[0] >= 144 and safe_bottom - safe_top >= 288:
                x = (box[0] + box[2]) // 2
                height = safe_bottom - safe_top
                start_y = safe_top + height * 3 // 4
                # A modest real scroll keeps the denser grouped list in view,
                # instead of jumping to its final padded end in one gesture.
                end_y = max(safe_top, start_y - min(height // 4, DENSITY * 5 // 8))
                action = dict(action='swipe', phase='native-backdrop-preview',
                    reason='Scroll the observed native content once above the floating navigation',
                    start=[x, start_y], end=[x, end_y], durationMillis=400,
                    observedScrollViewBounds=list(box), observedNavigationTop=nav_top,
                    hierarchySource='native-backdrop-network-before-scroll.xml', atUnixNs=time.time_ns())
                report['inputs'].append(action)
                adb('shell', 'input', 'touchscreen', 'swipe', str(x), str(start_y), str(x), str(end_y),
                    '400', timeout=6)
                action['completedAtUnixNs'] = time.time_ns()
                preview['scroll'].update(inputIssued=True, input=action)
            else:
                preview['scroll']['skipReason'] = 'No sufficiently large gesture area above the actual navigation'
        else:
            preview['scroll']['skipReason'] = 'No unique scrollable native ScrollView'
        activity = adb('shell', 'dumpsys', 'activity', 'activities', timeout=10).decode('utf-8', 'replace')
        (args.out / 'native-network-activity.txt').write_text(activity)
        resumed = [line.strip() for line in activity.splitlines()
                   if 'mResumedActivity' in line or 'topResumedActivity' in line]
        if not any(PACKAGE + '/local.pocketchat.MainActivity' in line for line in resumed):
            raise ValueError('The native backdrop preview is not in the actual MainActivity')
        preview['resumedActivity'] = resumed
        preview['stillSettleMillis'] = 600
        time.sleep(.6)
        # Observe the final settled UI immediately before the still. A notice
        # can arrive after the scroll, so dismiss at most this one observed UI.
        xml = wait_for(capture, ready, 'native-network-glass', seconds=15)
        feedback_close = lambda node: (node.get('class') == 'android.widget.Button'
            and node.get('content-desc') == '关闭提示' and node.get('text') == '×'
            and node.get('clickable') == 'true' and node.get('enabled') == 'true')
        feedback = nodes(xml, feedback_close)
        preview['feedbackDismissal'] = dict(observedMatchingControls=len(feedback), tapIssued=False)
        if len(feedback) == 1:
            before = args.out / 'native-backdrop-feedback-before-dismiss.xml'
            before.write_text(xml)
            preview['feedbackDismissal'].update(hierarchySource=before.name, hierarchySha256=sha(before),
                observedBounds=list(bounds(feedback[0])), inputIndex=len(report['inputs']))
            tap(feedback[0], 'Dismiss the single observed × / 关闭提示 feedback notice once for the native screenshot')
            report['inputs'][-1].update(phase='native-backdrop-preview', hierarchySource=before.name)
            preview['feedbackDismissal']['tapIssued'] = True
            # Refresh actual geometry after the notice closes. A recurring
            # notice is left alone; this is one UI dismissal, not suppression.
            xml = wait_for(capture, ready, 'native-network-glass', seconds=15)
            preview['feedbackDismissal'].update(matchingControlsAfterTap=len(nodes(xml, feedback_close)),
                refreshedHierarchySource='native-network-glass.xml',
                refreshedHierarchySha256=sha(args.out / 'native-network-glass.xml'))
        preview['hierarchy'] = dict(file='native-network-glass.xml', sha256=sha(args.out / 'native-network-glass.xml'),
            selectedNavigation='网络', bounds={label: list(bounds(button(xml, label))) for label in LABELS},
            geometry=navigation_geometry(xml))
        screenshot('native-network-glass.png')
        preview['screenshot'] = dict(report['screenshots'][-1])
        if (preview['screenshot']['width'], preview['screenshot']['height']) != (WIDTH, HEIGHT):
            raise ValueError('Native preview PNG dimensions differ from the configured physical screen')
        preview['imageCaptured'] = True
    except Exception as error:
        failure(error, 'native-network-capture')
    finally:
        try:
            if network_tapped:
                if not network_observed:
                    recovery = wait_for(capture, known_screen, 'native-backdrop-recovery', seconds=10)
                    network_observed = not chat(recovery)
                if network_observed:
                    back_to_chat('Return from the separate native backdrop preview to the existing chat',
                                 'native-backdrop-returned-chat')
                else:
                    wait_for(capture, chat, 'native-backdrop-returned-chat', seconds=10)
                preview['returnedToOrdinaryChat'] = True
                preview['returnedChatHierarchy'] = dict(file='native-backdrop-returned-chat.xml',
                    sha256=sha(args.out / 'native-backdrop-returned-chat.xml'))
        except Exception as error:
            failure(error, 'return-to-chat')
        preview['status'] = ('captured' if preview['imageCaptured'] and preview['returnedToOrdinaryChat']
                             and not preview['errors'] else 'failed')
        preview['lastInputIndexExclusive'] = len(report['inputs'])
        preview['completedAtUnixNs'] = time.time_ns()
        write(args.out / 'capture.json', report)


def collect_glass_lens_logs(args, report, adb):
    """Keep observed runtime messages as diagnostics, never as image/GPU proof."""
    diagnostic = report['glassLensDiagnostics']
    diagnostic.update(status='collecting', runNonce=report['runNonce'],
        startedAtUnixNs=time.time_ns(), gpuRenderingVerified=False,
        scope='Logcat history for the observed application PID; review PNG/MP4 independently. Missing errors do not establish success.')
    try:
        raw_pids = adb('shell', 'pidof', PACKAGE, timeout=5, check=False).decode().strip()
        pids = raw_pids.split() if re.fullmatch(r'[1-9][0-9]*(?:\s+[1-9][0-9]*)*', raw_pids) else []
        raw = adb('logcat', '-d', '-v', 'threadtime', '-s', 'GlassLens:V', '*:S', timeout=10)
        path = args.out / 'glass-lens-logcat.txt'
        path.write_bytes(raw)
        observed = []
        for line in raw.decode('utf-8', 'replace').splitlines():
            match = re.match(r'^\d\d-\d\d\s+\d\d:\d\d:\d\d\.\d+\s+(\d+)\s+\d+\s+([VDIWEFAS])\s+GlassLens\s*:\s?(.*)$', line)
            if match and match.group(1) in pids:
                observed.append((match.group(2), match.group(3), line))
        notices = [line for priority, message, line in observed
                   if priority in 'WEFA' or 'fallback' in message.lower()]
        diagnostic.update(status='collected', file=path.name, bytes=len(raw), sha256=sha(path),
            observedAppPids=pids, currentAppMessageCount=len(observed),
            observedAgslMaterialReady=any('AGSL material ready' in message for _, message, _ in observed),
            observedNativeBackdropRecorded=any('native backdrop recorded' in message for _, message, _ in observed),
            fallbackOrErrorCount=len(notices), fallbackOrErrorLines=notices[:40],
            fallbackOrErrorLinesTruncated=len(notices) > 40)
    except Exception as error:
        diagnostic.update(status='failed', errorType=type(error).__name__, error=str(error))
    finally:
        diagnostic['completedAtUnixNs'] = time.time_ns()


def capture_navigation_typography(args, report, capture, adb, wait_for, screenshot):
    """Bounded component measurements after the original screenshots and movie."""
    result = report['navigationTypography']
    result.update(status='started', startedAtUnixNs=time.time_ns(), runNonce=report['runNonce'],
        sourceCommit=report['buildIdentity']['sourceCommit'], apkSha256=report['buildIdentity']['apkSha256'],
        scope='Actual ReferenceUi.nav component fixture at font scales 1.0 and 1.3; MainActivity PNG is separate.',
        cases=[], errors=[], restoredDefaultFont=False, returnedToOrdinaryChat=False,
        firstCommandIndex=len(report['commands']))
    identity = report['buildIdentity']

    def failure(error, phase):
        result['errors'].append(dict(phase=phase, errorType=type(error).__name__, error=str(error)))

    def main_activity(name):
        adb('shell', 'am', 'force-stop', PACKAGE)
        adb('shell', 'am', 'start', '-W', '-n', COMPONENT, '--es', 'visualAction', 'chat')
        xml = wait_for(capture, lambda value: navigation(value) is not None and capsule(value) is not None,
                       name, seconds=30)
        raw = adb('shell', 'dumpsys', 'activity', 'activities').decode('utf-8', 'replace')
        (args.out / (name + '-activity.txt')).write_text(raw)
        resumed = [line.strip() for line in raw.splitlines()
                   if 'mResumedActivity' in line or 'topResumedActivity' in line]
        if not any(PACKAGE + '/local.pocketchat.MainActivity' in line for line in resumed):
            raise ValueError('The production MainActivity is not resumed after typography observation')
        return dict(file=name + '.xml', sha256=sha(args.out / (name + '.xml')),
                    geometry=navigation_geometry(xml), resumedActivity=resumed)

    try:
        for scale in (1.0, 1.3):
            nonce = secrets.token_hex(16)
            case = dict(requestedFontScale=scale, nonce=nonce, status='started', startedAtUnixNs=time.time_ns())
            result['cases'].append(case)
            adb('shell', 'am', 'force-stop', PACKAGE)
            adb('shell', 'settings', 'put', 'system', 'font_scale', str(scale))
            adb('shell', 'am', 'start', '-W', '-n', COMPONENT,
                '--es', 'visualAction', 'navigation-typography', '--es', 'visualNonce', nonce,
                '--es', 'visualSourceCommit', identity['sourceCommit'], '--ef', 'visualFontScale', str(scale))
            deadline = time.monotonic() + 25
            path = args.out / ('navigation-typography-font-' + str(scale) + '.log')
            records, summaries = [], []
            while time.monotonic() < deadline:
                raw = adb('logcat', '-d', '-v', 'raw', '-s', 'PocketNavType:I', '*:S',
                          timeout=min(10, max(.1, deadline-time.monotonic())))
                path.write_bytes(raw)
                records = []
                for line in raw.decode('utf-8', 'replace').splitlines():
                    if not line.startswith('{'):
                        continue
                    value = json.loads(line)
                    if value.get('nonce') == nonce:
                        records.append(value)
                summaries = [row for row in records if row.get('kind') == 'summary']
                if summaries:
                    break
                time.sleep(min(.2, max(0, deadline-time.monotonic())))
            case.update(logFile=path.name, logSha256=sha(path), observedRecords=records)
            if len(summaries) != 1 or summaries[0].get('status') != 'verified':
                raise ValueError('Native typography fixture did not verify: ' + str(summaries))
            labels = [row for row in records if row.get('kind') == 'label']
            expected = {(selected, index) for selected in range(-1, 4) for index in range(4)}
            keys = [(row.get('selectedIndex'), row.get('measurement', {}).get('buttonIndex')) for row in labels]
            if len(labels) != 20 or len(set(keys)) != 20 or set(keys) != expected or summaries[0].get('observationCount') != 20:
                raise ValueError('Typography observation phases or labels are incomplete')
            for row in records:
                if (row.get('schema') != 1 or not row.get('actualAndroidLayout')
                        or any(row.get(key) != identity[key] for key in ('sourceCommit', 'sourceTree', 'apkSha256'))
                        or abs(row.get('fontScale', -1) - scale) > .001):
                    raise ValueError('Typography record identity or actual font scale differs')
            for row in labels:
                measured = row['measurement']
                top = measured['compoundPaddingTop']
                bottom = measured['height'] - measured['compoundPaddingBottom']
                glyph = measured['glyphBounds']
                glyph_top = measured['baseline'] + glyph[1] - measured['scrollY']
                glyph_bottom = measured['baseline'] + glyph[3] - measured['scrollY']
                if (measured['label'] != LABELS[measured['buttonIndex']]
                        or not measured['valid'] or not all(measured['checks'].values())
                        or measured['contentHeight'] != bottom-top or measured['layoutHeight'] > bottom-top
                        or measured['glyphTop'] != glyph_top or measured['glyphBottom'] != glyph_bottom
                        or glyph_top < top or glyph_bottom > bottom):
                    raise ValueError('Actual navigation label does not fit its native text region')
            case.update(status='verified', labelObservationCount=len(labels), completedAtUnixNs=time.time_ns())
            case_path = args.out / ('navigation-typography-font-' + str(scale) + '.json')
            write(case_path, case)
            case.update(file=case_path.name, sha256=sha(case_path))

        # This is a separate screenshot of the real MainActivity, not the empty
        # component fixture above, and never replaces the original 1.0 capture.
        hierarchy = main_activity('large-font-navigation')
        scale = float(adb('shell', 'settings', 'get', 'system', 'font_scale').decode().strip())
        if abs(scale-1.3) > .001:
            raise ValueError('Enlarged-font MainActivity is not at the requested system scale')
        screenshot('large-font-navigation.png')
        result['largeFontMainActivity'] = dict(status='captured', fontScale=scale,
            actualProductionMainActivity=True, hierarchy=hierarchy, screenshot=dict(report['screenshots'][-1]),
            scope='Actual MainActivity at enlarged system font; local unconfigured environment, no live website')
    except Exception as error:
        failure(error, 'typography-observation')
    finally:
        try:
            adb('shell', 'settings', 'put', 'system', 'font_scale', '1.0')
            result['restoredChatHierarchy'] = main_activity('typography-returned-chat')
            scale = float(adb('shell', 'settings', 'get', 'system', 'font_scale').decode().strip())
            result['restoredFontScale'] = scale
            if abs(scale-1.0) > .001:
                raise ValueError('Default font scale was not restored')
            result.update(restoredDefaultFont=True, returnedToOrdinaryChat=True)
        except Exception as error:
            failure(error, 'restore-default-font-and-chat')
        result['status'] = ('verified' if len(result['cases']) == 2
            and all(case['status'] == 'verified' for case in result['cases'])
            and result['restoredDefaultFont'] and result['returnedToOrdinaryChat'] and not result['errors'] else 'failed')
        result.update(lastCommandIndexExclusive=len(report['commands']), completedAtUnixNs=time.time_ns())
        write(args.out / 'capture.json', report)


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
                                    wanAcceptance=False, performanceMeasurement=False),
                  nativeBackdropPreview=dict(status='not-attempted', optional=True,
                                             applicationAcceptance=False, physicalPhoneAcceptance=False,
                                             wanAcceptance=False, gpuRenderingVerified=False),
                  navigationTypography=dict(status='not-attempted', optional=True,
                                            applicationAcceptance=False, physicalPhoneAcceptance=False),
                  glassLensDiagnostics=dict(status='not-attempted', gpuRenderingVerified=False))

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
            geometry = navigation_geometry(xml)
            # Keep the latest real geometry, including a failing/incomplete
            # layout, without accepting its route predicate. Null geometry also
            # prevents an earlier observation from referring to a replaced XML.
            report.setdefault('navigationGeometryObservations', {})[name] = dict(
                file=name + '.xml', sha256=sha(args.out / (name + '.xml')),
                observedAtUnixNs=time.time_ns(), geometry=geometry)
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
            geometry=navigation_geometry(xml),
            capsuleBounds=list(bounds(capsule(xml))), capsuleDescription=capsule(xml).get('content-desc'),
            rootBounds=native_root_bounds(xml),
            expandedHeader=True, readingIsSeparateSquareControl=True,
            ordinaryConversationHasSelectedNavigation=False)
        report['display'] = dict(size=adb('shell', 'wm', 'size').decode().strip(),
            density=adb('shell', 'wm', 'density').decode().strip(),
            fontScale=adb('shell', 'settings', 'get', 'system', 'font_scale').decode().strip(),
            configuration=adb('shell', 'am', 'get-config').decode().strip())
        report['stillSettleMillis'] = 600
        time.sleep(.6)
        screenshot('glass-navigation.png')
        report['status'] = 'captured'
        report['staticScreenshotStatus'] = 'captured'
        # A failed optional clip must never discard the original successful PNG.
        try:
            capture_motion(args, report, capture, adb, wait_for)
        except Exception as error:
            report['motionReport'].update(status='failed', errorType=type(error).__name__, error=str(error))
        # This separate still must not spend any of the bounded movie's
        # budget or turn a failed movie into a passed motion observation.
        try:
            capture_native_backdrop_preview(args, report, capture, adb, wait_for, tap, screenshot)
        except Exception as error:
            report['nativeBackdropPreview'].update(status='failed', errorType=type(error).__name__, error=str(error))
        # Preserve messages from the same process as the original still/movie
        # before the separate font diagnostic deliberately starts fresh views.
        collect_glass_lens_logs(args, report, adb)
        try:
            capture_navigation_typography(args, report, capture, adb, wait_for, screenshot)
        except Exception as error:
            report['navigationTypography'].update(status='failed', errorType=type(error).__name__, error=str(error))
        print(json.dumps(dict(status='captured', sourceCommit=source,
            apkSha256=installed_sha, image='glass-navigation.png',
            motionStatus=report['motionReport']['status'],
            nativeBackdropStatus=report['nativeBackdropPreview']['status'],
            typographyStatus=report['navigationTypography']['status'],
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
        if device_ready and report['glassLensDiagnostics']['status'] == 'not-attempted':
            collect_glass_lens_logs(args, report, adb)
        report['completedAtUnixNs'] = time.time_ns()
        write(args.out / 'capture.json', report)


if __name__ == '__main__':
    main()
