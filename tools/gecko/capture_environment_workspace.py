"""A bounded visual diagnostic of the real environment workspace.

The existing test-only launcher seeds eight local, unconfigured environments and
then opens the production WindowHomeActivity. These records are synthetic visual
data, not live accounts, network receipts or release acceptance. PNGs and MP4s
are original Android captures; this module never draws or edits their pixels.
"""
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess
import time
import xml.etree.ElementTree as ET

PACKAGE = 'local.pocketchat.test'
COMPONENT = PACKAGE + '/local.pocketchat.UiVisualIntegrationActivity'
ACTIVITY = PACKAGE + '/local.pocketchat.WindowHomeActivity'
WIDTH, HEIGHT, DENSITY = 1236, 2676, 480
LABELS = ('环境', '网络', '下载', '阅读')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bounds(node):
    if node is None:
        return None
    match = re.fullmatch(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', node.get('bounds', ''))
    if match is None:
        return None
    left, top, right, bottom = map(int, match.groups())
    return (left, top, right, bottom) if 0 <= left < right <= WIDTH and 0 <= top < bottom <= HEIGHT else None


def visible_nodes(xml):
    return [node for node in ET.fromstring(xml).iter('node')
            if node.get('package') == PACKAGE and node.get('visible-to-user') != 'false'
            and bounds(node) is not None]


def named(xml, label, *, button=False):
    found = [node for node in visible_nodes(xml)
             if label in (node.get('text'), node.get('content-desc'))
             and (not button or (node.get('class') == 'android.widget.Button'
                                 and node.get('clickable') == 'true' and node.get('enabled') == 'true'))]
    return found[0] if len(found) == 1 else None


def row_positions(xml):
    # Each actual row keeps a uniquely named, accessible overflow control.
    # Comparing their observed bounds proves the scroll changed the row layout;
    # a clock changing in two PNGs is not treated as evidence of scrolling.
    return sorted((node.get('content-desc'), bounds(node)) for node in visible_nodes(xml)
                  if node.get('content-desc', '').startswith('更多操作 '))


def capture_environment_workspace(args, report, capture, adb, screenshot, *, navigation_geometry, mp4_metadata):
    result = report['environmentWorkspacePreview']
    identity = report['buildIdentity']
    result.update(status='started', startedAtUnixNs=time.time_ns(), actualAndroidExecution=True,
        actualProductionActivity=ACTIVITY, syntheticFixture=True, seededEnvironmentCount=8,
        sourceCommit=identity['sourceCommit'], sourceTree=identity['sourceTree'],
        apkSha256=identity['apkSha256'], runNonce=report['runNonce'], runnerSha256=sha(__file__),
        scope=__doc__, viewport=dict(width=WIDTH, height=HEIGHT, densityDpi=DENSITY),
        observations=[], scenes=[], errors=[], restoredDefaultFont=False,
        firstCommandIndex=len(report['commands']), firstInputIndex=len(report['inputs']),
        motion=dict(status='not-attempted', interactionsComplete=False,
                    performanceMeasurement=False, animationAppearanceVerified=False))
    motion = result['motion']
    process, log_stream, device_pid, recorder_row = None, None, None, None
    recording_started = None
    remote = '/data/local/tmp/pocketchat-environments-' + report['runNonce'] + '.mp4'
    pid_file = remote + '.pid'

    def save():
        (args.out / 'capture.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')

    def failure(error, phase):
        result['errors'].append(dict(phase=phase, errorType=type(error).__name__, error=str(error)))
        save()

    def selected(xml):
        geometry = navigation_geometry(xml)
        return geometry is not None and geometry['valid'] and all(
            geometry['selected'][label] == ('true' if label == '环境' else 'false') for label in LABELS)

    def ready(xml):
        # The visual heading can be “环境”; its explicit accessibility title is
        # still “环境管理”. Neither path relies on an off-screen text fragment.
        return (selected(xml) and named(xml, '环境管理') is not None
                and named(xml, '8 个环境') is not None and named(xml, '多选', button=True) is not None)

    def active():
        if process is None or process.poll() is not None or time.monotonic() - recording_started >= 59:
            raise TimeoutError('The owned environment recording ended before its actual inputs completed')
        return max(.1, 59 - (time.monotonic() - recording_started))

    def observe(predicate, name, *, recording=False, seconds=25):
        deadline = time.monotonic() + (min(seconds, active()) if recording else seconds)
        path = args.out / (name + '.xml')
        while time.monotonic() < deadline:
            xml = capture.read(deadline=deadline)
            path.write_text(xml)
            if predicate(xml):
                if recording:
                    active()
                observation = dict(file=path.name, sha256=sha(path), observedAtUnixNs=time.time_ns(),
                    geometry=navigation_geometry(xml), visibleRows=row_positions(xml),
                    observedWhileRecorderRunning=recording)
                result['observations'].append(observation)
                save()
                return xml, observation
            time.sleep(min(.2, max(0, deadline-time.monotonic())))
        raise TimeoutError('Actual environment workspace did not become ready: ' + name)

    def activity(name):
        raw = adb('shell', 'dumpsys', 'activity', 'activities', timeout=10)
        path = args.out / (name + '-activity.txt')
        path.write_bytes(raw)
        resumed = [line.strip() for line in raw.decode('utf-8', 'replace').splitlines()
                   if 'mResumedActivity' in line or 'topResumedActivity' in line]
        if not any(ACTIVITY in line for line in resumed):
            raise ValueError('The production WindowHomeActivity is not resumed')
        return dict(file=path.name, sha256=sha(path), resumedActivity=resumed)

    def scene(name, xml, observation, font_scale):
        actual_scale = float(adb('shell', 'settings', 'get', 'system', 'font_scale', timeout=5).decode().strip())
        if abs(actual_scale - font_scale) > .001:
            raise ValueError('Actual environment font scale differs from requested scale')
        owner = activity(name)
        time.sleep(.45)
        screenshot(name + '.png')
        image = dict(report['screenshots'][-1])
        if (image['width'], image['height']) != (WIDTH, HEIGHT):
            raise ValueError('Environment screenshot is not the actual requested physical viewport')
        value = dict(name=name, screenshot=image, hierarchy=observation, activity=owner,
                     fontScale=actual_scale, textAppearanceReview='Manual PNG review; XML text is not glyph-fit evidence')
        result['scenes'].append(value)
        save()
        return value

    def launch(scale):
        adb('shell', 'am', 'force-stop', PACKAGE)
        adb('shell', 'settings', 'put', 'system', 'font_scale', str(scale))
        adb('shell', 'am', 'start', '-W', '-n', COMPONENT, '--es', 'visualAction', 'environments')

    def input_event(parts, action, reason, observation, *, node=None, extra=None):
        active()
        event = dict(action=action, reason=reason, atUnixNs=time.time_ns(),
            hierarchy=observation['file'], hierarchySha256=observation['sha256'],
            diagnostic='environment-workspace', sourceCommit=identity['sourceCommit'],
            apkSha256=identity['apkSha256'])
        if node is not None:
            if bounds(node) is None:
                raise ValueError('Environment input target has no valid observed bounds')
            event['observedBounds'] = list(bounds(node))
        if extra:
            event.update(extra)
        report['inputs'].append(event)
        adb('shell', 'input', *parts, timeout=min(6, active()))
        active()
        event.update(completedAtUnixNs=time.time_ns(), completedWhileRecorderRunning=True)
        save()

    def tap(xml, label, observation):
        node = named(xml, label, button=True)
        box = bounds(node)
        if box is None:
            raise ValueError('Observed environment button is unavailable: ' + label)
        x, y = (box[0]+box[2])//2, (box[1]+box[3])//2
        input_event(('tap', str(x), str(y)), 'tap', label, observation, node=node,
                    extra=dict(x=x, y=y, label=label))

    def scroll(xml, observation, down):
        candidates = [node for node in visible_nodes(xml)
                      if node.get('class') == 'android.widget.ScrollView' and node.get('scrollable') == 'true']
        if not candidates:
            raise ValueError('No observed scrollable environment list')
        node = max(candidates, key=lambda n: (bounds(n)[2]-bounds(n)[0])*(bounds(n)[3]-bounds(n)[1]))
        left, top, right, bottom = bounds(node)
        geometry = navigation_geometry(xml)
        # Start and end inside actual content, above the floating dock's targets.
        bottom = min(bottom, min(geometry['bounds'][label][1] for label in LABELS) - 24*DENSITY//160)
        if bottom-top < 120*DENSITY//160:
            raise ValueError('Observed environment scroll region is too small for a safe gesture')
        x = (left+right)//2
        high, low = top+(bottom-top)//5, top+(bottom-top)*4//5
        start, end = (low, high) if down else (high, low)
        input_event(('touchscreen', 'swipe', str(x), str(start), str(x), str(end), '420'),
            'scroll-down' if down else 'scroll-up', 'Scroll the real environment list', observation,
            node=node, extra=dict(start=[x,start], end=[x,end], durationMillis=420))

    def signal_owned(signal):
        nonlocal device_pid
        if device_pid is None:
            value = adb('shell', 'cat', pid_file, timeout=3, check=False).decode().strip()
            if re.fullmatch(r'[1-9][0-9]{0,8}', value):
                device_pid = int(value)
        if device_pid is None:
            return False
        raw = adb('shell', 'cat', f'/proc/{device_pid}/cmdline', timeout=3, check=False)
        parts = raw.rstrip(b'\0').split(b'\0')
        if not parts or parts[0].rsplit(b'/', 1)[-1] != b'screenrecord' or remote.encode() not in parts:
            return False
        adb('shell', 'kill', '-' + signal, str(device_pid), timeout=3)
        motion.setdefault('signals', []).append(dict(signal=signal, pid=device_pid, atUnixNs=time.time_ns()))
        return True

    def stop_recording():
        if process is None:
            return
        if process.poll() is None:
            if not signal_owned('INT'):
                raise RuntimeError('Cannot match the owned environment screenrecord process')
            process.wait(timeout=8)
        recorder_row.update(exitCode=process.returncode, completedAtUnixNs=time.time_ns())
        motion['stoppedAtUnixNs'] = recorder_row['completedAtUnixNs']
        if process.returncode != 0:
            raise RuntimeError('Environment screenrecord exited with code ' + str(process.returncode))

    try:
        launch(1.0)
        xml, observation = observe(ready, 'environment-default')
        scene('environment-default', xml, observation, 1.0)
        try:
            motion.update(status='recording', startedAtUnixNs=time.time_ns(), timeLimitSeconds=60,
                requestedSize=[618,1338], minimumRecordingWallSeconds=16, firstInputIndex=len(report['inputs']),
                requestedReviewMinSeconds=6, requestedReviewMaxSeconds=60,
                sourceCommit=identity['sourceCommit'], sourceTree=identity['sourceTree'],
                apkSha256=identity['apkSha256'], runNonce=report['runNonce'],
                animationScales={key: adb('shell', 'settings', 'get', 'global', key, timeout=5).decode().strip()
                    for key in ('animator_duration_scale', 'window_animation_scale', 'transition_animation_scale')})
            shell = 'echo $$ > ' + shlex.quote(pid_file) + '; exec ' + shlex.join([
                'screenrecord', '--verbose', '--size', '618x1338', '--bit-rate', '3500000',
                '--time-limit', '60', remote])
            parts = [args.adb, '-s', args.serial, 'shell', shell]
            log_path = args.out / 'environment-screenrecord.log'
            recorder_row = dict(command=parts, startedAtUnixNs=time.time_ns(), asynchronous=True,
                                timeLimitSeconds=60, outputLog=log_path.name)
            report['commands'].append(recorder_row)
            log_stream = log_path.open('wb')
            process = subprocess.Popen(parts, stdin=subprocess.DEVNULL, stdout=log_stream, stderr=subprocess.STDOUT)
            recording_started = time.monotonic()
            time.sleep(.8)
            pid = adb('shell', 'cat', pid_file, timeout=3).decode().strip()
            if not re.fullmatch(r'[1-9][0-9]{0,8}', pid):
                raise ValueError('Environment screenrecord did not publish its owned PID')
            device_pid = int(pid)
            motion['recorderPid'] = device_pid
            before_rows = row_positions(xml)
            if not before_rows:
                raise ValueError('No actual environment rows were observed before scrolling')
            scroll(xml, observation, True)
            xml, observation = observe(lambda value: selected(value) and bool(row_positions(value))
                and row_positions(value) != before_rows, 'environment-scrolled', recording=True)
            result['scrollChangedObservedRows'] = True
            scene('environment-scrolled', xml, observation, 1.0)
            for index in range(3):
                scroll(xml, observation, False)
                xml, observation = observe(selected, 'environment-controls-' + str(index), recording=True)
                if ready(xml):
                    break
            if not ready(xml):
                raise ValueError('Environment selection controls did not return after actual scrolling')
            tap(xml, '多选', observation)
            xml, observation = observe(lambda value: selected(value)
                and named(value, '全选当前结果', button=True) is not None,
                'environment-selection-started', recording=True)
            tap(xml, '全选当前结果', observation)
            actions = ('取消当前结果选中', '批量分组', '收藏', '取消收藏')
            xml, observation = observe(lambda value: selected(value) and named(value, '已选 8 个') is not None
                and all(named(value, label, button=True) is not None for label in actions),
                'environment-selection-all', recording=True)
            for label in actions:
                left, top, right, bottom = bounds(named(xml, label, button=True))
                if right-left < 48*DENSITY//160 or bottom-top < 48*DENSITY//160:
                    raise ValueError('Actual environment selection target is smaller than 48 dp: ' + label)
            result['selection'] = dict(selectedCount=8, allFourActionsVisible=True,
                minimumTouchTargetDp=48, hierarchy=observation,
                actionBounds={label:list(bounds(named(xml, label, button=True))) for label in actions})
            scene('environment-selection-all', xml, observation, 1.0)
            input_event(('keyevent', '4'), 'keyevent', 'Exit multi-selection using actual Android Back',
                        observation, extra=dict(keyCode=4))
            xml, observation = observe(lambda value: ready(value) and named(value, '批量分组', button=True) is None,
                'environment-selection-exited', recording=True)
            result['selection']['backExitedSelection'] = True
            settle = max(.8, 16 - (time.monotonic()-recording_started))
            if settle > active():
                raise TimeoutError('No recording budget remains for the completed environment interaction tail')
            time.sleep(settle)
            active()
            motion.update(interactionsComplete=True, lastInputIndexExclusive=len(report['inputs']),
                postGestureWaitSeconds=settle, wallSecondsAtStopRequest=time.monotonic()-recording_started,
                stopReason='actual-scroll-selection-and-back-completed')
            stop_recording()
            xml, observation = observe(ready, 'environment-after-recording')
            motion['finalStateVerifiedAfterStop'] = True
        except Exception as error:
            motion['status'] = 'failed'
            failure(error, 'recording-and-selection')
        finally:
            if process is not None and process.poll() is None:
                try:
                    stop_recording()
                except Exception as error:
                    failure(error, 'stop-environment-recorder')
                    try:
                        signal_owned('KILL')
                    except Exception as stop_error:
                        failure(stop_error, 'kill-owned-environment-recorder')
                    if process.poll() is None:
                        process.terminate()
                        try:
                            process.wait(timeout=3)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait(timeout=3)
            if log_stream is not None:
                log_stream.close()
            if recorder_row is not None and process is not None:
                recorder_row.update(exitCode=process.poll(), completedAtUnixNs=time.time_ns())
            if process is not None:
                try:
                    video = args.out / 'environment-workspace-motion.mp4'
                    adb('pull', remote, str(video), timeout=20)
                    digest = adb('shell', 'sha256sum', remote, timeout=5).decode().split()[0]
                    if digest != sha(video):
                        raise ValueError('Environment recording bytes differ from the actual device file')
                    metadata = mp4_metadata(video)
                    if (metadata['width'], metadata['height']) != (618,1338):
                        raise ValueError('Environment recording has unexpected video dimensions')
                    motion['video'] = dict(file=video.name, bytes=video.stat().st_size,
                        sha256=digest, deviceSha256=digest, acquiredBy='Android screenrecord; original MP4 bytes',
                        **metadata)
                    if (motion['interactionsComplete'] and motion.get('finalStateVerifiedAfterStop')
                            and 6 <= metadata['durationSeconds'] <= 60 and not result['errors']):
                        motion['status'] = 'captured'
                    else:
                        raise ValueError('Environment recording did not retain a complete 6–60 second interaction sequence')
                except Exception as error:
                    motion['status'] = 'failed'
                    failure(error, 'retain-environment-recording')
        launch(1.3)
        xml, observation = observe(ready, 'environment-large-font-1.3')
        scene('environment-large-font-1.3', xml, observation, 1.3)
    except Exception as error:
        failure(error, 'environment-workspace')
    finally:
        try:
            launch(1.0)
            xml, observation = observe(ready, 'environment-restored')
            result['restoredHierarchy'] = observation
            result['restoredActivity'] = activity('environment-restored')
            scale = float(adb('shell', 'settings', 'get', 'system', 'font_scale', timeout=5).decode().strip())
            if abs(scale-1.0) > .001:
                raise ValueError('Environment diagnostic did not restore the default font scale')
            result['restoredDefaultFont'] = True
        except Exception as error:
            failure(error, 'restore-environment-default-font')
        expected = {'environment-default', 'environment-scrolled', 'environment-selection-all', 'environment-large-font-1.3'}
        result['status'] = ('captured' if not result['errors'] and result['restoredDefaultFont']
            and result.get('scrollChangedObservedRows') and result.get('selection', {}).get('backExitedSelection')
            and {value['name'] for value in result['scenes']} == expected and motion['status'] == 'captured' else 'failed')
        result.update(lastCommandIndexExclusive=len(report['commands']),
                      lastInputIndexExclusive=len(report['inputs']), completedAtUnixNs=time.time_ns())
        save()
