"""Additional source-bound Android glass UI observations.

These cases use the unchanged loopback document and the existing test-only
MainActivity subclass. Production readiness still comes from the real Gecko
documentReady callback. Original PNG/XML/MP4 bytes are retained for review.
This is integration/test-signed evidence, never a physical-device or release-
signature claim, compositor benchmark, or automatic judgement of appearance.
"""
import ast
from contextlib import contextmanager
import hashlib
import http.server
import importlib.util
import json
from pathlib import Path
import re
import secrets
import shlex
import subprocess
import threading
import time
import uuid

from integration_event_contract import EventTransfer, parse_receipt_line


CONFIGURATIONS = (
    ('default-light', 412, 892, 1.0, 'no'),
    ('enlarged-light', 412, 892, 1.3, 'no'),
    ('narrow-light', 320, 740, 1.6, 'no'),
    ('landscape-light', 892, 412, 1.0, 'no'),
    ('default-dark', 412, 892, 1.0, 'yes'),
    ('enlarged-dark', 412, 892, 1.3, 'yes'),
    ('safearea-light', 412, 892, 1.0, 'no'),
)

SAFE_AREA_OVERLAYS = ('com.android.internal.display.cutout.emulation.tall',
                      'com.android.internal.systemui.navbar.threebutton')


def total_frames(raw):
    """Read cumulative HWUI counters; no FPS or animation-smoothness inference."""
    values = re.findall(r'^\s*Total frames rendered:\s*(\d+)\s*$', raw, re.M)
    if len(values) != 1:
        raise ValueError('Expected one actual HWUI cumulative frame counter')
    return int(values[0])


@contextmanager
def controlled_document(args, adb, result, sha):
    """Run the existing canonical fixture's exact server class, without its tests."""
    path = args.root / 'tests/gecko/run_ui_visuals.py'
    source = path.read_text()
    classes = [node for node in ast.walk(ast.parse(source))
               if isinstance(node, ast.ClassDef) and node.name == 'ReloadHttp']
    if len(classes) != 1:
        raise ValueError('The selected source has no unique canonical ReloadHttp fixture')
    spec = importlib.util.spec_from_file_location('glass_loopback', args.root / 'engine-probe/tests/run_device.py')
    loopback = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loopback)
    namespace = dict(reload_loopback=loopback, uuid=uuid)
    program = ast.fix_missing_locations(ast.Module(body=classes, type_ignores=[]))
    exec(compile(program, str(path), 'exec'), namespace)
    existing = adb('reverse', '--list').decode()
    if any('tcp:' + str(port) in existing for port in (8765, 1080)):
        raise ValueError('The isolated glass capture requires unowned loopback reverse ports')
    servers = []
    started_servers = []
    forwards = []
    try:
        servers.append(http.server.ThreadingHTTPServer(('127.0.0.1', 8765), namespace['ReloadHttp']))
        servers.append(loopback.ThreadedSocks(('127.0.0.1', 1080), loopback.Socks))
        for server in servers:
            threading.Thread(target=server.serve_forever, daemon=True).start()
            started_servers.append(server)
        for port in (8765, 1080):
            adb('reverse', 'tcp:' + str(port), 'tcp:' + str(port))
            forwards.append(port)
        result['controlledFixture'] = dict(
            path=str(path.relative_to(args.root)), sourceSha256=sha(path),
            classSha256=hashlib.sha256(ast.get_source_segment(source, classes[0]).encode()).hexdigest(),
            serverClass='ReloadHttp', actualLoopbackHttp=True, actualLoopbackSocks=True,
            productionReadinessCallbackPreserved=True, requests=[])
        yield loopback.TRACE
    finally:
        if 'controlledFixture' in result:
            result['controlledFixture']['requests'] = list(loopback.TRACE)
        for port in forwards:
            try:
                adb('reverse', '--remove', 'tcp:' + str(port), timeout=5)
            except Exception as error:
                result['errors'].append(dict(stage='remove-owned-reverse', port=port,
                    errorType=type(error).__name__, error=str(error)))
        for server in started_servers:
            try:
                server.shutdown()
            except Exception as error:
                result['errors'].append(dict(stage='shutdown-owned-server', errorType=type(error).__name__, error=str(error)))
        for server in servers:
            try:
                server.server_close()
            except Exception as error:
                result['errors'].append(dict(stage='close-owned-server', errorType=type(error).__name__, error=str(error)))


@contextmanager
def record_case(args, report, adb, case, sha, mp4_metadata):
    """Retain one bounded device recording, with exact nonce-owned PID cleanup."""
    remote = '/data/local/tmp/glass-suite-' + case['runNonce'] + '.mp4'
    pid_file = remote + '.pid'
    path = args.out / (case['name'] + '-motion.mp4')
    log = args.out / (case['name'] + '-screenrecord.log')
    shell = 'echo $$ > ' + shlex.quote(pid_file) + '; exec ' + shlex.join([
        'screenrecord', '--size', '618x1338', '--bit-rate', '3500000', '--time-limit', '180', remote])
    recording = case['motion'] = dict(status='started', hardLimitSeconds=180,
        startedAtUnixNs=time.time_ns(), acquiredBy='Android screenrecord; original device MP4',
        firstInputIndex=len(report['inputs']), appearanceVerified=False,
        framePacingMeasurement=False, highRefreshRateAcceptance=False, errors=[])
    recorder_command = [args.adb, '-s', args.serial, 'shell', shell]
    command_row = dict(command=recorder_command, startedAtUnixNs=time.time_ns(),
                       asynchronous=True, outputLog=log.name, phase=case['name'])
    report['commands'].append(command_row)
    with log.open('wb') as stream:
        process = subprocess.Popen(recorder_command,
            stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT)
        device_pid = None
        primary_error = None

        def cleanup_error(stage, error):
            recording['errors'].append(dict(stage=stage, errorType=type(error).__name__, error=str(error)))

        def signal_owned(signal):
            nonlocal device_pid
            if device_pid is None:
                raw_pid = adb('shell', 'cat', pid_file, timeout=3, check=False).decode().strip()
                if re.fullmatch('[1-9][0-9]{0,8}', raw_pid):
                    device_pid = int(raw_pid)
            if device_pid is None:
                return False
            parts = adb('shell', 'cat', '/proc/' + str(device_pid) + '/cmdline',
                        timeout=3, check=False).rstrip(b'\0').split(b'\0')
            if parts and parts[0].rsplit(b'/', 1)[-1] == b'screenrecord' and remote.encode() in parts:
                adb('shell', 'kill', '-' + signal, str(device_pid), timeout=3)
                return True
            return False

        try:
            time.sleep(.8)
            raw = adb('shell', 'cat', pid_file, timeout=3).decode().strip()
            if not re.fullmatch('[1-9][0-9]{0,8}', raw) or process.poll() is not None:
                raise ValueError('The owned suite recorder did not start')
            device_pid = int(raw)
            yield
            if process.poll() is not None:
                raise ValueError('The suite recorder ended before the input sequence completed')
            time.sleep(1)
            recording['allInputsCompletedBeforeStop'] = True
        except BaseException as error:
            primary_error = error
            raise
        finally:
            if process.poll() is None:
                try:
                    signal_owned('INT')
                except Exception as error:
                    cleanup_error('stop-recorder', error)
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                try:
                    signal_owned('KILL')
                except Exception as error:
                    cleanup_error('kill-owned-recorder', error)
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=4)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=3)
            recording.update(exitCode=process.returncode, completedAtUnixNs=time.time_ns(),
                lastInputIndexExclusive=len(report['inputs']), logFile=log.name)
            command_row.update(exitCode=process.returncode, completedAtUnixNs=time.time_ns(),
                               outputLogBytes=log.stat().st_size, outputLogSha256=sha(log))
            pulled = False
            try:
                device_sha = adb('shell', 'sha256sum', remote, timeout=5).decode().split()[0]
                adb('pull', remote, str(path), timeout=30)
                pulled = True
                recording.update(file=path.name, sha256=sha(path), deviceSha256=device_sha,
                                 bytes=path.stat().st_size, **mp4_metadata(path))
                if device_sha != recording['sha256']:
                    raise ValueError('Suite MP4 changed during transfer')
                if process.returncode != 0 or not recording.get('allInputsCompletedBeforeStop'):
                    raise ValueError('Suite recording did not cover the complete input sequence')
                recording['status'] = 'captured'
            except Exception as error:
                cleanup_error('retrieve-or-validate-video', error)
                recording['status'] = 'failed'
            finally:
                try:
                    adb('shell', 'rm', '-f', pid_file, *([remote] if pulled else []), check=False, timeout=3)
                except Exception as error:
                    cleanup_error('remove-owned-temporary-files', error)
            if recording['errors']:
                recording['status'] = 'failed'
                if primary_error is None:
                    raise RuntimeError('Suite recording failed; original diagnostics are retained')


def capture_acceptance_suite(args, report, capture, adb, wait_for, tap, screenshot, api):
    """Fail closed on route/configuration failures; save every original observation."""
    result = report['glassUiAcceptance'] = dict(schema=1, status='started',
        sourceCommit=report['buildIdentity']['sourceCommit'],
        sourceTree=report['buildIdentity']['sourceTree'],
        apkSha256=report['installedApk']['sha256'], runNonce=report['runNonce'],
        sdkBuildIdentity=report['buildIdentity'].get('sdkBuildIdentity'),
        integrationPackage=api['PACKAGE'], testSignedIntegrationEvidence=True,
        releaseSignatureAcceptance=False, actualAndroidExecution=True,
        physicalPhoneAcceptance=False, highRefreshRateAcceptance=False,
        appearanceVerified=False, expectedMaterialPath='CPU cached raster (API <33)'
            if args.device_api < 33 else 'AGSL on hardware-accelerated Android Canvas',
        cases=[], errors=[], startedAtUnixNs=time.time_ns())
    package = api['PACKAGE']
    component = package + '/local.pocketchat.CompactChromeIntegrationActivity'
    sha, write, bounds, nodes, button = [api[key] for key in ('sha', 'write', 'bounds', 'nodes', 'button')]
    nav, capsule, geometry = [api[key] for key in ('navigation', 'capsule', 'observed_navigation_geometry')]
    identity = report['buildIdentity']
    observations = {}
    previous_overlays = {}

    def save():
        write(args.out / 'capture.json', report)

    def artifact(case, suffix, predicate, *, photograph=True):
        stem = case['name'] + '-' + suffix
        xml = wait_for(capture, predicate, stem, seconds=30)
        item = dict(xml=stem + '.xml', xmlSha256=sha(args.out / (stem + '.xml')),
                    geometry=geometry(xml), observedAtUnixNs=time.time_ns())
        title = capsule(xml)
        if title is not None:
            box = bounds(title)
            offset = (box[0] + box[2] - api['WIDTH']) / 2
            item['topCapsule'] = dict(bounds=list(box), horizontalCenterOffsetPx=offset,
                                     description=title.get('content-desc'))
            if abs(offset) > 1:
                raise ValueError('The actual top environment capsule is not centered')
        if photograph:
            time.sleep(.6)
            screenshot(stem + '.png')
            item.update(png=stem + '.png', pngSha256=sha(args.out / (stem + '.png')))
        case['observations'][suffix] = item
        save()
        return xml

    def text(xml, value):
        return bool(nodes(xml, lambda node: node.get('text') == value))

    def chat(xml):
        observed = geometry(xml)
        return (observed is not None and observed['layout'] == 'conversation-split'
                and nav(xml) is not None and capsule(xml) is not None
                and not text(xml, '打开网址') and not text(xml, '快速切换环境'))

    def key(case, code, reason):
        report['inputs'].append(dict(action='keyevent', keyCode=code, phase=case['name'],
                                     reason=reason, atUnixNs=time.time_ns()))
        adb('shell', 'input', 'keyevent', str(code))

    def observed_event(case, command, *, request=True):
        if request:
            adb('shell', 'am', 'broadcast', '-a', package + '.CHROME_COLLAPSE', '-p', package,
                '--es', 'eventNonce', case['runNonce'], '--es', 'collapseCommand', command)
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline:
            raw = adb('logcat', '-d', '-v', 'brief', '-s', 'PocketGeckoIntegration:I', 'AndroidRuntime:E', '*:S')
            (args.out / (case['name'] + '-events.log')).write_bytes(raw)
            if b'FATAL EXCEPTION' in raw:
                raise ValueError('Android crashed during the real UI sequence')
            for line in raw.decode('utf-8', 'replace').splitlines():
                receipt = parse_receipt_line(line)
                if receipt is None or receipt.get('runNonce') != case['runNonce']:
                    continue
                value = observations[case['runNonce']].read(receipt)
                if value['kind'] == 'error':
                    raise ValueError('Controlled document fixture failed: ' + str(value))
                if value['kind'] == 'collapseSnapshot' and value['result'].get('command') == command:
                    case.setdefault('documentObservations', {})[command] = value['result']
                    return value['result']
            time.sleep(.2)
        raise TimeoutError('No current, source/APK/SDK/nonce-bound document observation: ' + command)

    def quiet(case, name, allowed_delta):
        time.sleep(1.1)  # Longer than every glass press/selection release.
        values = []
        for index in range(2):
            raw = adb('shell', 'dumpsys', 'gfxinfo', package).decode('utf-8', 'replace')
            path = args.out / (case['name'] + '-' + name + '-gfxinfo-' + str(index) + '.txt')
            path.write_text(raw)
            values.append(dict(file=path.name, sha256=sha(path), frames=total_frames(raw),
                               atUnixNs=time.time_ns()))
            if index == 0:
                time.sleep(1.5)
        delta = values[1]['frames'] - values[0]['frames']
        check = dict(observations=values, deltaFrames=delta, allowedDeltaFrames=allowed_delta,
                     windowSeconds=(values[1]['atUnixNs'] - values[0]['atUnixNs']) / 1e9,
                     scope='Bounded HWUI process counter; not per-drawable attribution or FPS',
                     valid=0 <= delta <= allowed_delta)
        case.setdefault('idleObservations', {})[name] = check
        if not check['valid']:
            raise ValueError('UI continued drawing during bounded ' + name + ' observation: ' + str(delta))

    def renderer_observation(case):
        pids = adb('shell', 'pidof', package, timeout=5).decode().strip().split()
        raw = adb('logcat', '-d', '-v', 'threadtime', '-s', 'GlassLens:V', '*:S', timeout=10)
        path = args.out / (case['name'] + '-glass-lens.txt'); path.write_bytes(raw)
        messages = []
        for line in raw.decode('utf-8', 'replace').splitlines():
            match = re.match(r'^\d\d-\d\d\s+\d\d:\d\d:\d\d\.\d+\s+(\d+)\s+\d+\s+([VDIWEFAS])\s+GlassLens\s*:\s?(.*)$', line)
            if match and match[1] in pids:
                messages.append(dict(priority=match[2], text=match[3]))
        observation = case['materialPath'] = dict(deviceApi=args.device_api,
            file=path.name, sha256=sha(path), currentAppPids=pids, messages=messages,
            agslReady=any('AGSL material ready' in row['text'] for row in messages),
            nativeBackdropRecorded=any('native backdrop recorded' in row['text'] for row in messages),
            sourceBoundCpuBranch=args.device_api < 33, appearanceVerified=False)
        if args.device_api >= 33 and (not observation['agslReady'] or not observation['nativeBackdropRecorded']
                or any(row['priority'] in 'WEFA' for row in messages)):
            raise ValueError('The expected actual AGSL/native-backdrop path was not observed in the current app PID')
        if args.device_api < 33 and observation['agslReady']:
            raise ValueError('API <33 unexpectedly reported AGSL; CPU fallback evidence is inconsistent')

    def safe_area(case):
        raw = adb('shell', 'dumpsys', 'window', 'displays').decode('utf-8', 'replace')
        path = args.out / (case['name'] + '-window-insets.txt'); path.write_text(raw)
        overlays = adb('shell', 'cmd', 'overlay', 'list', '--user', '0').decode()
        overlay_path = args.out / (case['name'] + '-overlays.txt'); overlay_path.write_text(overlays)
        case['safeArea'] = dict(windowInsetsFile=path.name, windowInsetsSha256=sha(path),
            overlayFile=overlay_path.name, overlaySha256=sha(overlay_path),
            statusAndNavigationBarsCaptured=True, visualReviewRequired=True)
        if case['name'] == 'safearea-light':
            enabled = {match[1] for match in re.finditer(r'^\[x\]\s+(\S+)\s*$', overlays, re.M)}
            if not all(name in enabled for name in SAFE_AREA_OVERLAYS):
                raise ValueError('Requested cutout and three-button safe-area overlays were not actually enabled')
            case['safeArea']['observedEnabledOverlays'] = sorted(enabled.intersection(SAFE_AREA_OVERLAYS))

    def typography(case, mode):
        """Measure native Chinese glyphs in this exact size/theme/font configuration."""
        nonce = secrets.token_hex(16)
        expected_labels = api['LABELS'] if mode == 'conversation' else api['WORKSPACE_LABELS']
        count = len(expected_labels)
        observation_count = count * (count + 1)
        field = 'typography' if mode == 'conversation' else 'workspaceTypography'
        adb('shell', 'am', 'start', '-W', '-n', api['COMPONENT'],
            '--es', 'visualAction', 'navigation-typography', '--es', 'visualNonce', nonce,
            '--es', 'visualNavigationMode', mode,
            '--es', 'visualSourceCommit', identity['sourceCommit'], '--ef', 'visualFontScale', str(case['fontScale']))
        suffix = '-typography.log' if mode == 'conversation' else '-workspace-typography.log'
        path = args.out / (case['name'] + suffix)
        deadline = time.monotonic() + 25
        records = []
        summaries = []
        while time.monotonic() < deadline:
            raw = adb('logcat', '-d', '-v', 'raw', '-s', 'PocketNavType:I', '*:S', timeout=10)
            path.write_bytes(raw)
            records = [json.loads(line) for line in raw.decode('utf-8', 'replace').splitlines() if line.startswith('{')]
            records = [row for row in records if row.get('nonce') == nonce]
            summaries = [row for row in records if row.get('kind') == 'summary']
            if summaries:
                break
            time.sleep(.2)
        component = 'ReferenceUi.nav' if mode == 'conversation' else 'ReferenceUi.workspaceNav'
        case[field] = dict(file=path.name, sha256=sha(path), nonce=nonce, records=records,
            navigationMode=mode,
            scope='Separate actual ' + component + ' component; same Android size/theme/font, not MainActivity')
        labels = [row for row in records if row.get('kind') == 'label']
        expected = {(selected, index) for selected in range(-1, count) for index in range(count)}
        keys = [(row.get('selectedIndex'), row.get('measurement', {}).get('buttonIndex')) for row in labels]
        if (len(summaries) != 1 or summaries[0].get('status') != 'verified'
                or summaries[0].get('observationCount') != observation_count or len(labels) != observation_count
                or len(set(keys)) != observation_count or set(keys) != expected):
            raise ValueError('The native Chinese navigation typography observation is incomplete or failed')
        for row in records:
            if (row.get('schema') != 1 or row.get('actualAndroidLayout') is not True
                    or row.get('navigationMode') != mode
                    or any(row.get(key) != identity[key] for key in ('sourceCommit', 'sourceTree', 'apkSha256'))
                    or abs(row.get('fontScale', -1) - case['fontScale']) > .001):
                raise ValueError('Typography source/APK/font identity differs from the current case')
        for row in labels:
            measured = row['measurement']
            if (measured.get('label') != expected_labels[measured['buttonIndex']]
                    or measured.get('valid') is not True or not measured.get('checks')
                    or not all(value is True for value in measured['checks'].values())):
                raise ValueError('A complete Chinese navigation label did not fit its native text region')
        case[field]['status'] = 'verified'
        adb('shell', 'am', 'force-stop', package)

    def interactions(case):
        xml = artifact(case, 'chat', chat)
        initial = case['documentObservations']['ready']
        if initial.get('visibleDocument') is not True or initial.get('loadingCoverVisibility') != 8:
            raise ValueError('The actual production callback did not reveal the controlled Gecko document')
        tap(capsule(xml), 'Tap the observed environment capsule to open only the native URL editor')
        xml = artifact(case, 'url-keyboard', lambda value: text(value, '打开网址')
                       and button(value, '取消') is not None and not text(value, '快速切换环境'))
        ime = adb('shell', 'dumpsys', 'input_method').decode('utf-8', 'replace')
        path = args.out / (case['name'] + '-keyboard.txt')
        path.write_text(ime)
        case['keyboard'] = dict(file=path.name, sha256=sha(path),
            shown=bool(re.search(r'(?:mInputShown|mIsInputViewShown|isInputViewShown)=true\b', ime)))
        if not case['keyboard']['shown']:
            raise ValueError('The actual native URL keyboard was not observed')
        tap(button(xml, '取消'), 'Cancel native URL editing without navigating')
        xml = artifact(case, 'url-cancelled', chat, photograph=False)
        box = bounds(capsule(xml)); x, y = (box[0] + box[2]) // 2, (box[1] + box[3]) // 2
        report['inputs'].append(dict(action='long-press', phase=case['name'], observedBounds=list(box),
            point=[x, y], durationMillis=850, atUnixNs=time.time_ns()))
        adb('shell', 'input', 'touchscreen', 'swipe', str(x), str(y), str(x), str(y), '850')
        xml = artifact(case, 'environment-sheet', lambda value: text(value, '快速切换环境')
                       and not text(value, '打开网址'))
        closes = nodes(xml, lambda node: node.get('content-desc') == '关闭快速切换环境'
                       and node.get('clickable') == 'true')
        if len(closes) != 1:
            raise ValueError('Expected one observed environment sheet close control')
        tap(closes[0], 'Dismiss the environment picker without changing environment')
        xml = artifact(case, 'environment-cancelled', chat, photograph=False)
        for label in ('下载', '网络'):
            tap(button(xml, label), 'Open the actual native ' + label + ' workspace')
            xml = artifact(case, label, lambda value: api['selected_navigation'](value, label))
            key(case, 4, 'Return from the native workspace to the retained Gecko document')
            xml = artifact(case, label + '-returned', chat, photograph=False)
        tap(button(xml, '环境'), 'Open the actual environment management destination')
        artifact(case, 'environments', lambda value: api['selected_navigation'](value, '环境'))
        key(case, 4, 'Return from environment management to the retained conversation')
        xml = artifact(case, 'environments-returned', chat, photograph=False)
        for exit_method in ('button', 'back'):
            tap(button(xml, '阅读'), 'Enter actual focus reading with a usable Gecko document')
            xml = artifact(case, 'reading-entered-' + exit_method,
                lambda value: button(value, '退出阅读') is not None and capsule(value) is None
                and all(button(value, label) is None for label in api['LABELS']))
            if exit_method == 'button':
                quiet(case, 'glass-hidden-reading', 2)
                tap(button(xml, '退出阅读'), 'Exit focus reading through its actual native exit control')
            else:
                key(case, 4, 'Exit actual focus reading with Android Back')
            xml = artifact(case, 'reading-exited-' + exit_method, chat)
        after = observed_event(case, 'after-interactions')
        retained = ('draft', 'cookie', 'sendCount', 'document', 'surface', 'sdkSession', 'documents', 'loads', 'stops')
        case['documentRetained'] = {key: initial.get(key) == after.get(key) for key in retained}
        if not all(case['documentRetained'].values()) or after.get('sendCount') != 0:
            raise ValueError('Native UI interaction changed the controlled document, draft, login or send count')

    try:
        overlay_list = adb('shell', 'cmd', 'overlay', 'list', '--user', '0').decode()
        previous_overlays = {match[2]: match[1] == 'x' for match in
            re.finditer(r'^\[([ x])\]\s+(com\.android\.internal\.(?:display\.cutout\.emulation|systemui\.navbar)\.\S+)\s*$',
                        overlay_list, re.M)}
        for name in SAFE_AREA_OVERLAYS:
            if name not in previous_overlays:
                raise ValueError('The disposable emulator lacks required safe-area overlay: ' + name)
        with controlled_document(args, adb, result, sha):
            for name, width, height, scale, night in CONFIGURATIONS:
                case = dict(name=name, runNonce=secrets.token_hex(16), status='started',
                    widthDp=width, heightDp=height, fontScale=scale, requestedNight=night,
                    observations={}, startedAtUnixNs=time.time_ns())
                result['cases'].append(case)
                try:
                    api['set_display'](width * 3, height * 3, 480)
                    adb('shell', 'am', 'force-stop', package)
                    adb('shell', 'wm', 'size', str(width * 3) + 'x' + str(height * 3))
                    adb('shell', 'settings', 'put', 'system', 'font_scale', str(scale))
                    adb('shell', 'cmd', 'uimode', 'night', night)
                    for overlay in SAFE_AREA_OVERLAYS:
                        if name == 'safearea-light':
                            adb('shell', 'cmd', 'overlay', 'enable-exclusive', '--category', '--user', '0', overlay)
                        else:
                            adb('shell', 'cmd', 'overlay', 'disable', '--user', '0', overlay)
                    adb('shell', 'settings', 'put', 'secure', 'show_ime_with_hard_keyboard', '1')
                    typography(case, 'conversation')
                    typography(case, 'workspace')
                    observations[case['runNonce']] = EventTransfer(identity=identity, nonce=case['runNonce'],
                        slot=0, action='chromeCollapse', fetch=lambda uri: adb('exec-out', 'content', 'read', '--uri', uri))
                    adb('shell', 'am', 'start', '-W', '-n', component,
                        '--es', 'compactAction', 'collapseStart', '--ei', 'chromeNavigationVersion', '2',
                        '--es', 'eventNonce', case['runNonce'], '--ez', 'longName', 'false')
                    observed_event(case, 'ready', request=False)
                    case['actualConfiguration'] = adb('shell', 'am', 'get-config').decode().strip()
                    case['observedFontSetting'] = adb('shell', 'settings', 'get', 'system', 'font_scale').decode().strip()
                    if abs(float(case['observedFontSetting']) - scale) > .001:
                        raise ValueError('Observed Android font setting differs from the requested case')
                    config_parts = case['actualConfiguration'].splitlines()[0].split('-')
                    if ('night' not in config_parts if night == 'yes' else 'notnight' not in config_parts):
                        raise ValueError('The actual Android configuration did not apply the requested light/dark mode')
                    orientation = 'land' if width > height else 'port'
                    if orientation not in config_parts:
                        raise ValueError('The actual Android configuration did not apply the requested orientation')
                    safe_area(case)
                    if name in ('default-light', 'default-dark'):
                        with record_case(args, report, adb, case, sha, api['mp4_metadata']):
                            interactions(case)
                    else:
                        interactions(case)
                    renderer_observation(case)
                    quiet(case, 'foreground-settled', 2)
                    key(case, 3, 'Background the application after every glass release has settled')
                    activity = adb('shell', 'dumpsys', 'activity', 'activities').decode()
                    path = args.out / (name + '-background-activity.txt'); path.write_text(activity)
                    resumed = [line for line in activity.splitlines() if 'mResumedActivity' in line or 'topResumedActivity' in line]
                    if not resumed or any(package + '/' in line for line in resumed):
                        raise ValueError('The application did not actually leave the resumed state')
                    quiet(case, 'background', 0)
                    case['status'] = 'verified'
                except Exception as error:
                    case.update(status='failed', errorType=type(error).__name__, error=str(error))
                    result['errors'].append(dict(case=name, errorType=type(error).__name__, error=str(error)))
                    try:
                        screenshot(name + '-failed.png')
                    except Exception:
                        pass
                finally:
                    case['events'] = observations[case['runNonce']].records if case['runNonce'] in observations else []
                    case['completedAtUnixNs'] = time.time_ns()
                    save()
        result['status'] = 'verified' if len(result['cases']) == len(CONFIGURATIONS) and not result['errors'] else 'failed'
    except Exception as error:
        result['status'] = 'failed'
        result['errors'].append(dict(stage='suite-setup-or-server', errorType=type(error).__name__, error=str(error)))
    finally:
        api['set_display'](1236, 2676, 480)
        cleanup = [('shell', 'am', 'force-stop', package), ('shell', 'wm', 'size', '1236x2676'),
                   ('shell', 'settings', 'put', 'system', 'font_scale', '1.0'),
                   ('shell', 'cmd', 'uimode', 'night', 'no')]
        cleanup.extend(('shell', 'cmd', 'overlay', 'enable' if enabled else 'disable', '--user', '0', name)
                       for name, enabled in previous_overlays.items())
        for command in cleanup:
            try:
                adb(*command, timeout=6)
            except Exception as error:
                result['status'] = 'failed'
                result['errors'].append(dict(stage='restore-disposable-emulator', command=list(command),
                    errorType=type(error).__name__, error=str(error)))
        result['completedAtUnixNs'] = time.time_ns()
        save()
    if result['status'] != 'verified':
        raise RuntimeError('Required real glass UI observations failed; review capture.json and original artifacts')
