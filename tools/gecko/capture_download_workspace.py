"""Real DownloadCenterActivity captures with bounded, local synthetic records.

The integration-only launcher creates readable PDF/PNG/TXT files plus explicit
paused/failed fixture metadata. No active transfer, account, WAN, or performance
claim is made. All displayed pixels and movies come unchanged from Android.
"""
import hashlib
import json
from pathlib import Path
import re
import secrets
import shlex
import subprocess
import time
from urllib.parse import unquote, urlsplit

from capture_environment_workspace import bounds, named, scrollable_region, visible_nodes
from profile_invocation_contract import bind_report
from sdk_identity_contract import strict_json

PACKAGE = 'local.pocketchat.test'
COMPONENT = PACKAGE + '/local.pocketchat.DownloadsWorkspaceVisualActivity'
ACTIVITY = PACKAGE + '/local.pocketchat.DownloadCenterActivity'
WIDTH, HEIGHT, DENSITY = 1236, 2676, 480
LABELS = ('会话', '环境', '下载', '网络', '设置')
PAUSED, FAILED = '界面素材与图标资源.zip', '会议纪要补充资料.pdf'
SAVED = ('产品设计说明.pdf', '界面参考与配色.png', '阅读摘录与笔记.txt')
FILENAMES = (PAUSED, FAILED) + SAVED


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify_fixture(payload_raw, journal_raw, *, identity, nonce, run_nonce, command, mode):
    """Validate original native bytes and their independently published receipt."""
    require(isinstance(payload_raw, bytes) and 0 < len(payload_raw) <= 2*1024*1024,
            'A bounded original fixture payload is required')
    require(isinstance(journal_raw, bytes) and 0 < len(journal_raw) <= 32768,
            'A bounded original fixture receipt journal is required')
    payload, journal = strict_json(payload_raw), strict_json(journal_raw)
    require(type(payload) is dict and type(journal) is dict, 'Native fixture objects are required')
    bind_report(payload, identity)
    expected = dict(schema=1, runNonce=nonce, processSlot=0, fixtureAction='download-workspace', command=command)
    for key, value in expected.items():
        require(type(payload.get(key)) is type(value) and payload.get(key) == value,
                'Fixture invocation differs: ' + key)
        require(type(journal.get(key)) is type(value) and journal.get(key) == value,
                'Fixture receipt invocation differs: ' + key)
    require(payload.get('sequence') == 1 and type(payload.get('sequence')) is int
            and journal.get('status') == 'committed' and payload.get('nativeContext') == 'environment-1'
            and type(payload.get('observedAtElapsedRealtime')) is int and payload['observedAtElapsedRealtime'] > 0,
            'One committed fixture event is required')
    receipts = journal.get('receipts')
    require(type(receipts) is list and len(receipts) == 1 and type(receipts[0]) is str,
            'Exactly one original native receipt is required')
    receipt = strict_json(receipts[0].encode())
    for key, value in expected.items():
        require(type(receipt.get(key)) is type(value) and receipt.get(key) == value,
                'Fixture event receipt differs: ' + key)
    require(receipt.get('kind') == 'eventReceipt' and receipt.get('eventKind') == 'downloadWorkspaceFixture'
            and receipt.get('sequence') == 1 and type(receipt.get('sequence')) is int
            and receipt.get('nativeContext') == 'environment-1',
            'The committed event receipt is not a download fixture receipt')
    require(type(receipt.get('payloadBytes')) is int and receipt['payloadBytes'] == len(payload_raw)
            and receipt.get('payloadSha256') == hashlib.sha256(payload_raw).hexdigest(),
            'Native fixture payload bytes differ from their committed receipt')
    event = payload.get('event', {})
    require(event.get('kind') == 'downloadWorkspaceFixture' and event.get('processSlot') == 0
            and type(event.get('processSlot')) is int and event.get('nativeContext') == 'environment-1',
            'The native event is not a download workspace fixture')
    value = event.get('result', {})
    require(value.get('status') == 'ready' and value.get('mode') == mode
            and value.get('parentRunNonce') == run_nonce and value.get('actualProductionActivity') == ACTIVITY,
            'The local fixture belongs to a different capture or screen')
    require(value.get('syntheticFixture') is True and value.get('syntheticTaskMetadata') is True
            and value.get('actualNetworkTransfer') is False,
            'Synthetic local state must not be reported as an actual transfer')
    require(mode in ('populated', 'empty'), 'Unsupported fixture mode')
    counts = dict(recordCount=5 if mode == 'populated' else 0,
                  savedCount=3 if mode == 'populated' else 0,
                  pausedCount=1 if mode == 'populated' else 0,
                  failedCount=1 if mode == 'populated' else 0, activeTransferCount=0)
    for key, count in counts.items():
        require(type(value.get(key)) is int and value[key] == count, 'Unexpected fixture count: ' + key)
    rows, files, partials = value.get('rows'), value.get('savedFiles'), value.get('partialFiles')
    require(type(rows) is list and len(rows) == counts['recordCount']
            and type(files) is list and len(files) == counts['savedCount']
            and type(partials) is list and len(partials) == counts['pausedCount'],
            'The native fixture record lists are incomplete')
    expected_names = set(FILENAMES) if mode == 'populated' else set()
    require(all(type(row) is dict for row in rows)
            and {row.get('name') for row in rows} == expected_names,
            'Unexpected or duplicate native fixture names')
    require(len({(row.get('slot'), row.get('id')) for row in rows}) == len(rows),
            'Duplicate native download identity')
    by_name = {row['name']: row for row in rows}
    for row in rows:
        name = row['name']
        expected_state = 'paused' if name == PAUSED else 'failed' if name == FAILED else 'saved'
        require(row.get('state') == expected_state, 'The fixture contains unexpected active or saved state')
        require(type(row.get('slot')) is int and 0 <= row['slot'] < 5
                and type(row.get('id')) is str and re.fullmatch(r'[a-f0-9-]{36}', row['id'])
                and type(row.get('environmentId')) is str and re.fullmatch(r'[a-f0-9-]{36}', row['environmentId'])
                and type(row.get('environmentGeneration')) is int and row['environmentGeneration'] >= 0,
                'The fixture lacks its real environment/publication identity')
    require({proof.get('name') for proof in files} == (set(SAVED) if mode == 'populated' else set()),
            'Readable file proofs do not match the saved records')
    for proof in files:
        row = by_name[proof['name']]
        uri = urlsplit(proof.get('uri', ''))
        parts = unquote(uri.path).split('/')
        require(uri.scheme == 'content' and uri.netloc == PACKAGE + '.saved-downloads'
                and not uri.query and not uri.fragment
                and parts == ['', str(row['slot']), row['id'], row['name']],
                'A saved fixture file is not under its exact owned content URI')
        require(proof.get('readable') is True and proof.get('id') == row['id']
                and proof.get('uri') == row.get('uri') and proof.get('slot') == row['slot']
                and type(proof.get('bytes')) is int and 0 < proof['bytes'] <= 1024*1024
                and proof['bytes'] == row.get('savedBytes') and type(proof.get('sha256')) is str
                and re.fullmatch(r'[0-9a-f]{64}', proof['sha256']),
                'The readable file proof differs from its real indexed publication')
    for proof in partials:
        row = by_name[PAUSED]
        require(proof.get('name') == PAUSED and proof.get('id') == row['id'] and proof.get('slot') == row['slot']
                and type(proof.get('bytes')) is int and 0 < proof['bytes'] == row.get('received') < row.get('total', -1)
                and type(proof.get('sha256')) is str and re.fullmatch(r'[0-9a-f]{64}', proof['sha256']),
                'Paused progress differs from its actual partial file')
    return value


def file_positions(xml):
    return sorted((node.get('text'), bounds(node)) for node in visible_nodes(xml)
                  if node.get('class') == 'android.widget.TextView' and node.get('text') in FILENAMES)


def file_names(xml):
    return {name for name, _ in file_positions(xml)}


def checked_file(xml, name):
    nodes = [node for node in visible_nodes(xml) if node.get('class') == 'android.widget.CheckBox'
             and node.get('content-desc') == '收集文件 ' + name and node.get('checked') == 'true']
    return len(nodes) == 1


def capture_download_workspace(args, report, capture, adb, screenshot, *, navigation_geometry, mp4_metadata):
    result, identity = report['downloadsWorkspacePreview'], report['buildIdentity']
    result.update(status='started', startedAtUnixNs=time.time_ns(), actualAndroidExecution=True,
        actualProductionActivity=ACTIVITY, sourceCommit=identity['sourceCommit'], sourceTree=identity['sourceTree'],
        apkSha256=identity['apkSha256'], runNonce=report['runNonce'], runnerSha256=sha(__file__),
        syntheticFixture=True, syntheticTaskMetadata=True, actualNetworkTransfer=False,
        scope=__doc__, observations=[], scenes=[], fixtures=[], resets=[], errors=[],
        firstCommandIndex=len(report['commands']), firstInputIndex=len(report['inputs']), restoredDefaultFont=False,
        motion=dict(status='not-attempted', performanceMeasurement=False, animationAppearanceVerified=False,
                    interactionsComplete=False))
    motion = result['motion']
    process, log_stream, device_pid, recorder_row, recording_started = None, None, None, None, None
    remote = '/data/local/tmp/pocketchat-downloads-' + report['runNonce'] + '.mp4'
    pid_file = remote + '.pid'
    launch_count, last_mode = 0, 'populated'

    def save():
        (args.out / 'capture.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')

    def failure(error, phase):
        result['errors'].append(dict(phase=phase, errorType=type(error).__name__, error=str(error)))
        save()

    def selected(xml):
        geometry = navigation_geometry(xml)
        return geometry is not None and geometry['valid'] and all(
            geometry['selected'][label] == ('true' if label == '下载' else 'false') for label in LABELS)

    def ready(xml, mode='populated'):
        return (selected(xml) and named(xml, '下载中心') is not None
                and all(named(xml, label, button=True) is not None for label in ('全部', '进行中', '已完成', '失败'))
                and (PAUSED in file_names(xml) if mode == 'populated' else named(xml, '还没有下载文件') is not None))

    def active():
        require(process is not None and process.poll() is None and time.monotonic() - recording_started < 59,
                'The owned download recording ended before its actual inputs completed')
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
                observed = dict(file=path.name, sha256=sha(path), observedAtUnixNs=time.time_ns(),
                    geometry=navigation_geometry(xml), visibleFiles=file_positions(xml),
                    observedWhileRecorderRunning=recording)
                result['observations'].append(observed)
                save()
                return xml, observed
            time.sleep(min(.2, max(0, deadline-time.monotonic())))
        raise TimeoutError('Actual download workspace did not become ready: ' + name)

    def activity(name):
        raw = adb('shell', 'dumpsys', 'activity', 'activities', timeout=10)
        path = args.out / (name + '-activity.txt');path.write_bytes(raw)
        resumed = [line.strip() for line in raw.decode('utf-8', 'replace').splitlines()
                   if 'mResumedActivity' in line or 'topResumedActivity' in line]
        require(any(ACTIVITY in line for line in resumed), 'The real DownloadCenterActivity is not resumed')
        return dict(file=path.name, sha256=sha(path), resumedActivity=resumed)

    def scene(name, observation, scale):
        actual = float(adb('shell', 'settings', 'get', 'system', 'font_scale', timeout=5).decode().strip())
        require(abs(actual-scale) <= .001, 'Actual download font scale differs from the requested scale')
        owner = activity(name);time.sleep(.4);screenshot(name + '.png')
        value = dict(report['screenshots'][-1])
        require((value['width'], value['height']) == (WIDTH, HEIGHT), 'Unexpected download capture viewport')
        result['scenes'].append(dict(name=name, screenshot=value, hierarchy=observation, activity=owner,
            fontScale=actual, textAppearanceReview='Manual PNG review; XML text is not glyph-fit evidence'))
        save()

    def reset(mode):
        require(report.get('actualAndroidExecution') is True and report['installedApk']['sha256'] == identity['apkSha256']
                and adb('shell', 'getprop', 'ro.kernel.qemu', timeout=5).strip() == b'1',
                'Only the verified installed disposable test package can be reset')
        installed = adb('shell', 'pm', 'path', PACKAGE, timeout=5).decode().strip()
        require(re.fullmatch(r'package:/data/app/[A-Za-z0-9_./=+~-]+/base\.apk', installed) is not None,
                'The disposable download fixture must still have exactly one installed APK')
        installed = installed.removeprefix('package:')
        require(installed == report['installedApk']['path'], 'The installed test APK changed before fixture reset')
        checksum = adb('shell', 'sha256sum', installed, timeout=15).decode().split()
        require(len(checksum) == 2 and checksum[0] == identity['apkSha256'] and checksum[1] == installed,
                'The current installed test APK bytes differ from the reviewed build before fixture reset')
        require(adb('shell', 'pm', 'clear', PACKAGE, timeout=15).strip() == b'Success', 'Disposable download fixture reset failed')
        result['resets'].append(dict(package=PACKAGE, mode=mode, atUnixNs=time.time_ns(),
                                    installedApkPath=installed, verifiedApkSha256=checksum[0]))

    def launch(scale, mode, name):
        nonlocal launch_count, last_mode
        launch_count += 1;last_mode = mode;nonce = secrets.token_hex(16)
        adb('shell', 'am', 'force-stop', PACKAGE)
        adb('shell', 'settings', 'put', 'system', 'font_scale', str(scale))
        adb('shell', 'am', 'start', '-W', '-n', COMPONENT,
            '--es', 'visualNonce', nonce, '--es', 'visualRunNonce', report['runNonce'],
            '--es', 'visualMode', mode, '--el', 'visualCommand', str(launch_count),
            '--es', 'visualSourceCommit', identity['sourceCommit'], '--es', 'visualSourceTree', identity['sourceTree'],
            '--es', 'visualApkSha256', identity['apkSha256'])
        base = 'content://' + PACKAGE + '.evidence/'
        deadline = time.monotonic() + 25
        raw = journal = b''
        while time.monotonic() < deadline:
            raw = adb('shell', 'content', 'read', '--uri', base + 'gecko-events/0/' + nonce + '/1', timeout=5, check=False)
            journal = adb('shell', 'content', 'read', '--uri', base + 'gecko-event-receipts/0/' + nonce, timeout=5, check=False)
            try:
                parsed_payload, parsed_journal = strict_json(raw), strict_json(journal)
            except (ValueError, UnicodeDecodeError):
                time.sleep(.2);continue
            if isinstance(parsed_payload, dict) and isinstance(parsed_journal, dict) and parsed_journal.get('status') == 'committed':
                break
            time.sleep(.2)
        payload_path, journal_path = args.out / (name + '-fixture.json'), args.out / (name + '-receipts.json')
        payload_path.write_bytes(raw);journal_path.write_bytes(journal)
        fixture = verify_fixture(raw, journal, identity=identity, nonce=nonce, run_nonce=report['runNonce'],
                                 command=launch_count, mode=mode)
        result['fixtures'].append(dict(file=payload_path.name, sha256=sha(payload_path),
            receiptFile=journal_path.name, receiptSha256=sha(journal_path), mode=mode, nonce=nonce,
            command=launch_count, recordCount=fixture['recordCount'], savedFileCount=fixture['savedCount'],
            sourceCommit=identity['sourceCommit'], sourceTree=identity['sourceTree'], apkSha256=identity['apkSha256']))
        save()

    def input_event(parts, action, label, observation, *, node, extra=None):
        active();box = bounds(node)
        require(box is not None, 'Actual download input target has no observed bounds')
        event = dict(action=action, label=label, atUnixNs=time.time_ns(), diagnostic='download-workspace',
            hierarchy=observation['file'], hierarchySha256=observation['sha256'], observedBounds=list(box),
            sourceCommit=identity['sourceCommit'], apkSha256=identity['apkSha256'])
        if extra:
            event.update(extra)
        report['inputs'].append(event)
        adb('shell', 'input', *parts, timeout=min(6, active()));active()
        event.update(completedAtUnixNs=time.time_ns(), completedWhileRecorderRunning=True);save()

    def tap(xml, label, observation, *, checkbox=False):
        node = named(xml, label, button=not checkbox)
        require(node is not None and node.get('clickable') == 'true' and node.get('enabled') == 'true'
                and (not checkbox or node.get('class') == 'android.widget.CheckBox'),
                'Actual download control is unavailable: ' + label)
        left, top, right, bottom = bounds(node);x, y = (left+right)//2, (top+bottom)//2
        require(bottom <= min(navigation_geometry(xml)['bounds'][item][1] for item in LABELS),
                'Download content input would be covered by the floating navigation')
        input_event(('tap', str(x), str(y)), 'tap', label, observation, node=node, extra=dict(x=x, y=y))

    def scroll(xml, observation, down):
        node = scrollable_region(xml);require(node is not None, 'No actual scrollable download content')
        left, top, right, bottom = bounds(node);geometry = navigation_geometry(xml)
        bottom = min(bottom, min(geometry['bounds'][label][1] for label in LABELS)-24*DENSITY//160)
        require(bottom-top >= 120*DENSITY//160, 'Actual download content is too short for a safe scroll gesture')
        x = (left+right)//2;high, low = top+(bottom-top)//5, top+(bottom-top)*4//5
        start, end = (low, high) if down else (high, low)
        input_event(('touchscreen', 'swipe', str(x), str(start), str(x), str(end), '420'),
            'scroll-down' if down else 'scroll-up', 'Scroll actual download records', observation, node=node,
            extra=dict(start=[x,start], end=[x,end], durationMillis=420))

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
            require(signal_owned('INT'), 'Cannot match the owned download screenrecord process')
            process.wait(timeout=8)
        recorder_row.update(exitCode=process.returncode, completedAtUnixNs=time.time_ns())
        motion['stoppedAtUnixNs'] = recorder_row['completedAtUnixNs']
        require(process.returncode == 0, 'Download screenrecord exited with code ' + str(process.returncode))

    try:
        reset('populated')
        launch(1.0, 'populated', 'downloads-default')
        xml, observation = observe(ready, 'downloads-default');scene('downloads-default', observation, 1.0)
        launch(1.3, 'populated', 'downloads-large-font-1.3')
        xml, observation = observe(ready, 'downloads-large-font-1.3');scene('downloads-large-font-1.3', observation, 1.3)
        can_scroll = scrollable_region(xml) is not None
        result['scrollInteractionAvailable'] = can_scroll
        try:
            motion.update(status='recording', startedAtUnixNs=time.time_ns(), timeLimitSeconds=60,
                requestedSize=[618,1338], minimumRecordingWallSeconds=16, firstInputIndex=len(report['inputs']),
                fontScale=1.3, sourceCommit=identity['sourceCommit'], sourceTree=identity['sourceTree'],
                apkSha256=identity['apkSha256'], runNonce=report['runNonce'])
            shell = 'echo $$ > ' + shlex.quote(pid_file) + '; exec ' + shlex.join([
                'screenrecord', '--verbose', '--size', '618x1338', '--bit-rate', '3500000', '--time-limit', '60', remote])
            parts = [args.adb, '-s', args.serial, 'shell', shell]
            log_path = args.out / 'downloads-screenrecord.log'
            recorder_row = dict(command=parts, startedAtUnixNs=time.time_ns(), asynchronous=True,
                                timeLimitSeconds=60, outputLog=log_path.name)
            report['commands'].append(recorder_row);log_stream = log_path.open('wb')
            process = subprocess.Popen(parts, stdin=subprocess.DEVNULL, stdout=log_stream, stderr=subprocess.STDOUT)
            recording_started = time.monotonic();time.sleep(.8)
            pid = adb('shell', 'cat', pid_file, timeout=3).decode().strip()
            require(re.fullmatch(r'[1-9][0-9]{0,8}', pid), 'Download screenrecord did not publish its owned PID')
            device_pid = int(pid);motion['recorderPid'] = device_pid
            before = file_positions(xml)
            if can_scroll:
                scroll(xml, observation, True)
                xml, observation = observe(lambda value: selected(value) and bool(file_positions(value))
                    and file_positions(value) != before, 'downloads-scrolled', recording=True)
                result['scrollChangedObservedRows'] = True;scene('downloads-scrolled', observation, 1.3)
                for index in range(3):
                    scroll(xml, observation, False)
                    xml, observation = observe(selected, 'downloads-controls-' + str(index), recording=True)
                    if ready(xml) and file_positions(xml) == before:
                        break
                require(ready(xml) and file_positions(xml) == before, 'Download rows did not return after actual scrolling')
            else:
                result.update(scrollChangedObservedRows=False, scrollSkipReason='All real fixture content fits at observed 1.3 font scale')
            tap(xml, '失败', observation)
            xml, observation = observe(lambda value: selected(value) and file_names(value) == {FAILED},
                'downloads-failed-filter', recording=True)
            result['failedFilterVerified'] = True
            tap(xml, '进行中', observation)
            xml, observation = observe(lambda value: selected(value) and not file_names(value)
                and named(value, '没有进行中的下载') is not None, 'downloads-active-empty', recording=True)
            result['activeFilterVerifiedEmpty'] = True
            tap(xml, '已完成', observation)
            xml, observation = observe(lambda value: selected(value) and file_names(value) == set(SAVED),
                'downloads-completed-filter', recording=True)
            result['completedFilterVerified'] = True
            tap(xml, '收集文件', observation)
            xml, observation = observe(lambda value: selected(value) and named(value, '完成选择', button=True) is not None
                and named(value, '收集文件 ' + SAVED[0]) is not None, 'downloads-selection-started', recording=True)
            tap(xml, '收集文件 ' + SAVED[0], observation, checkbox=True)
            xml, observation = observe(lambda value: selected(value) and checked_file(value, SAVED[0])
                and named(value, '收集篮 · 1', button=True) is not None, 'downloads-selection', recording=True)
            scene('downloads-selection', observation, 1.3)
            result['collection'] = dict(selectedCount=1, selectedFilename=SAVED[0], checkboxVerified=True, hierarchy=observation)
            tap(xml, '完成选择', observation)
            xml, observation = observe(lambda value: selected(value) and named(value, '收集文件', button=True) is not None
                and named(value, '收集文件 ' + SAVED[0]) is None, 'downloads-selection-exited', recording=True)
            result['collection']['doneExitedSelection'] = True
            tap(xml, '全部', observation)
            xml, observation = observe(ready, 'downloads-all-restored', recording=True)
            settle = max(.8, 16-(time.monotonic()-recording_started));require(settle < active(), 'No download recording tail budget remains')
            time.sleep(settle);active()
            motion.update(interactionsComplete=True, lastInputIndexExclusive=len(report['inputs']), postGestureWaitSeconds=settle,
                wallSecondsAtStopRequest=time.monotonic()-recording_started, stopReason='actual-filter-and-collection-inputs-completed')
            stop_recording();xml, observation = observe(ready, 'downloads-after-recording')
            motion['finalStateVerifiedAfterStop'] = True
        except Exception as error:
            motion['status'] = 'failed';failure(error, 'download-recording-and-inputs')
        finally:
            if process is not None and process.poll() is None:
                try:
                    stop_recording()
                except Exception as error:
                    failure(error, 'stop-download-recorder')
                    try:
                        signal_owned('KILL')
                    except Exception as stop_error:
                        failure(stop_error, 'kill-owned-download-recorder')
                    if process.poll() is None:
                        process.terminate()
                        try:
                            process.wait(timeout=3)
                        except subprocess.TimeoutExpired:
                            process.kill();process.wait(timeout=3)
            if log_stream is not None:
                log_stream.close()
            if recorder_row is not None and process is not None:
                recorder_row.update(exitCode=process.poll(), completedAtUnixNs=time.time_ns())
            if process is not None:
                try:
                    video = args.out / 'downloads-workspace-motion.mp4';adb('pull', remote, str(video), timeout=20)
                    digest = adb('shell', 'sha256sum', remote, timeout=5).decode().split()[0]
                    require(digest == sha(video), 'Download video bytes differ from the original device file')
                    metadata = mp4_metadata(video)
                    require((metadata['width'], metadata['height']) == (618,1338), 'Unexpected download video dimensions')
                    motion['video'] = dict(file=video.name, bytes=video.stat().st_size, sha256=digest, deviceSha256=digest,
                        acquiredBy='Android screenrecord; original MP4 bytes', **metadata)
                    require(motion['interactionsComplete'] and motion.get('finalStateVerifiedAfterStop')
                        and 6 <= metadata['durationSeconds'] <= 60 and not result['errors'], 'Download video lacks its complete input sequence')
                    motion['status'] = 'captured'
                except Exception as error:
                    motion['status'] = 'failed';failure(error, 'retain-download-recording')
        reset('empty');launch(1.0, 'empty', 'downloads-empty')
        xml, observation = observe(lambda value: ready(value, 'empty') and not file_names(value), 'downloads-empty')
        scene('downloads-empty', observation, 1.0)
    except Exception as error:
        failure(error, 'download-workspace')
    finally:
        try:
            launch(1.0, last_mode, 'downloads-restored')
            xml, observation = observe(lambda value: ready(value, last_mode), 'downloads-restored')
            result['restoredHierarchy'] = observation;result['restoredActivity'] = activity('downloads-restored')
            scale = float(adb('shell', 'settings', 'get', 'system', 'font_scale', timeout=5).decode().strip())
            require(abs(scale-1.0) <= .001, 'Download capture did not restore the default font scale')
            result['restoredDefaultFont'] = True
        except Exception as error:
            failure(error, 'restore-download-default-font')
        expected = {'downloads-default', 'downloads-large-font-1.3', 'downloads-selection', 'downloads-empty'}
        if result.get('scrollInteractionAvailable'):
            expected.add('downloads-scrolled')
        result['status'] = ('captured' if not result['errors'] and result['restoredDefaultFont']
            and {scene['name'] for scene in result['scenes']} == expected
            and result.get('failedFilterVerified') and result.get('activeFilterVerifiedEmpty') and result.get('completedFilterVerified')
            and result.get('collection', {}).get('doneExitedSelection') and motion['status'] == 'captured' else 'failed')
        result.update(lastCommandIndexExclusive=len(report['commands']), lastInputIndexExclusive=len(report['inputs']), completedAtUnixNs=time.time_ns())
        save()
