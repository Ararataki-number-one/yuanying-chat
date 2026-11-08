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
import xml.etree.ElementTree as ET

from integration_event_contract import EventTransfer, parse_receipt_line
from glass_display import GlassDisplay, verify_png
from glass_document_viewport import require_document_viewport


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


def gfxinfo_owner(raw, package):
    """Bind a cumulative counter to its actual Android process and reset epoch."""
    pids = re.findall(r'^\*\* Graphics info for pid (\d+) \[' + re.escape(package) + r'\] \*\*\s*$', raw, re.M)
    epochs = re.findall(r'^Stats since:\s*(\d+)ns\s*$', raw, re.M)
    clocks = re.findall(r'^Uptime:\s*\d+\s+Realtime:\s*(\d+)\s*$', raw, re.M)
    if len(pids) != 1 or len(epochs) != 1 or len(clocks) != 1:
        raise ValueError('One actual process/epoch/clock is required for the HWUI observation')
    return dict(pid=int(pids[0]), statsSinceNs=int(epochs[0]), realtimeMillis=int(clocks[0]))


def validate_glass_owner_window(before, after, samples, identity, nonce, commands):
    """Validate read-only attribution; never substitute it for the HWUI limit."""
    if len(samples) != 2 or samples[0]['pid'] != samples[1]['pid'] or samples[0]['statsSinceNs'] != samples[1]['statsSinceNs']:
        raise ValueError('HWUI observation changed process or reset epoch')
    counts = []
    for observation, command in zip((before, after), commands):
        if (type(observation.get('schema')) is not int or observation['schema'] != 1 or observation.get('status') != 'observed'
                or observation.get('command') != command or observation.get('runNonce') != nonce
                or observation.get('readOnly') is not True or observation.get('pausesObservers') is not False
                or any(observation.get(key) != identity[key] for key in ('sourceCommit', 'sourceTree', 'apkSha256'))
                or observation.get('pid') != samples[0]['pid']
                or observation.get('activityClass') != 'local.pocketchat.CompactChromeIntegrationActivity'):
            raise ValueError('Native glass-owner observation identity or read-only scope differs')
        if any(type(observation.get(key)) is not int for key in ('pid', 'uid', 'activityRef', 'decorRef')):
            raise ValueError('Native glass-owner process and Activity identities must be integers')
        owners = observation['owners']
        if len(owners.get('roots', [])) != 2 or not owners.get('materials') or not owners.get('docks'):
            raise ValueError('Native glass-owner observation is incomplete')

        def require_host(host):
            if (type(host.get('rootIdentity')) is not int or host['rootIdentity'] != observation['decorRef']
                    or any(type(host.get(flag)) is not bool for flag in ('shown', 'attached'))
                    or any(type(host.get(flag)) is not int or host[flag] not in (0, 4, 8)
                           for flag in ('visibility', 'windowVisibility'))):
                raise ValueError('Native host visibility or current Activity root is not an observed typed value')

        for host in owners['roots']:
            require_host(host)
        backdrop = owners.get('backdrop', {})
        if any(type(backdrop.get(flag)) is not bool for flag in ('configuredActive', 'isGlassActive')):
            raise ValueError('Native backdrop activity state is missing')
        require_host(backdrop.get('host', {}))
        hidden_active = 0
        for owner, key in [(item, 'animation') for item in owners['materials']] + [(item, 'transition') for item in owners['docks']]:
            host, animator = owner['host'], owner[key]
            require_host(host)
            if key == 'animation' and type(owner.get('drawableVisible')) is not bool:
                raise ValueError('Native material visibility is not an observed boolean')
            if any(type(animator.get(flag)) is not bool for flag in ('present', 'started', 'running')):
                raise ValueError('Native animator state is missing, not an observed idle value')
            if not animator['present'] and (animator['started'] or animator['running']):
                raise ValueError('Absent native animator has an inconsistent live state')
            hidden = not host['attached'] or not host['shown'] or host['windowVisibility'] != 0 or not owner.get('drawableVisible', True)
            if hidden and (animator['started'] or animator['running']):
                hidden_active += 1
        counts.append(hidden_active)
    if (before['activityRef'] != after['activityRef'] or before['decorRef'] != after['decorRef']
            or before['uid'] != after['uid']):
        raise ValueError('Native glass observation changed Activity/decor/UID')
    start, end = before['capturedAtElapsedRealtimeNanos'], after['capturedAtElapsedRealtimeNanos']
    if not (type(start) is int and type(end) is int and 0 <= start <= end
            and start <= (samples[0]['realtimeMillis'] + 1) * 1_000_000
            and end >= samples[1]['realtimeMillis'] * 1_000_000):
        raise ValueError('Read-only native observations do not bracket the original HWUI window')
    return dict(status='bound', before=before, after=after, hiddenActiveAnimatorCounts=counts,
        scope='Current native glass owners; raw process HWUI threshold remains independently required')


def quiet_window_check(samples, allowed_delta, owner_window):
    delta = samples[1]['frames'] - samples[0]['frames']
    process_valid = 0 <= delta <= allowed_delta
    owner_bound = owner_window.get('status') == 'bound'
    hidden_failure = owner_bound and any(count != 0 for count in owner_window['hiddenActiveAnimatorCounts'])
    return dict(observations=samples, deltaFrames=delta, allowedDeltaFrames=allowed_delta,
        windowSeconds=(samples[1]['atUnixNs'] - samples[0]['atUnixNs']) / 1e9,
        requestedObservationSeconds=1.5, glassOwnerWindow=owner_window,
        scope='Bounded HWUI process counter; owner attribution cannot override this threshold',
        processDrawFailure=not process_valid, ownerBindingFailure=not owner_bound,
        hiddenAnimatorFailure=hidden_failure,
        valid=process_valid and owner_bound and not hidden_failure)


def system_bar_sources(raw):
    """Read observed InsetsSource rectangles from API 32/35 window dumps."""
    sources = {'statusBars': [], 'navigationBars': []}
    aliases = {'statusBars': 'statusBars', 'navigationBars': 'navigationBars',
               'ITYPE_STATUS_BAR': 'statusBars', 'ITYPE_NAVIGATION_BAR': 'navigationBars'}
    for line in raw.splitlines():
        if re.search(r'\bInsetsSource\b', line) is None:
            continue  # InsetsSourceControl is a leash, not a visible bar frame.
        kind = re.search(r'\b(?:mType|type)=(statusBars|navigationBars|ITYPE_STATUS_BAR|ITYPE_NAVIGATION_BAR)\b', line)
        if kind is None:
            continue
        frame = re.search(r'\b(?:mFrame|frame)=\[\s*(-?\d+),\s*(-?\d+)\]\[\s*(-?\d+),\s*(-?\d+)\]', line)
        visible = re.search(r'\b(?:mVisible|visible)=(true|false)\b', line)
        if frame is None or visible is None:
            raise ValueError('Observed system-bar InsetsSource lacks bounds or visibility')
        rectangle = list(map(int, frame.groups()))
        if rectangle[0] > rectangle[2] or rectangle[1] > rectangle[3]:
            raise ValueError('Observed system-bar InsetsSource has reversed bounds')
        source = dict(bounds=rectangle, visible=visible[1] == 'true')
        values = sources[aliases[kind[1]]]
        if source not in values:
            values.append(source)
    if not all(sources.values()):
        raise ValueError('Both actual status-bar and navigation-bar InsetsSources are required')
    return sources


def loading_actions_geometry(xml, api, system_bar_frames=()):
    """Check native loading actions and their visible ancestor/chrome bounds.

    Accessibility preserves the complete labels and exposes touch rectangles;
    the original PNG remains necessary to review actual glyph appearance.
    """
    root = ET.fromstring(xml)
    parents = {child: parent for parent in root.iter() for child in parent}
    labels = ('检查网络', '重新加载')
    controls = []
    for label in labels:
        found = [node for node in root.iter('node') if node.get('package') == api['PACKAGE']
                 and node.get('text') == label and node.get('class') == 'android.widget.Button'
                 and node.get('clickable') == 'true' and node.get('enabled') == 'true'
                 and node.get('visible-to-user') != 'false']
        if len(found) != 1 or api['bounds'](found[0]) is None:
            return None
        controls.append(found[0])
    boxes = [api['bounds'](node) for node in controls]
    navigation = api['navigation_geometry'](xml)
    capsule = api['capsule'](xml)
    capsule_box = api['bounds'](capsule) if capsule is not None else None

    def contains(outer, inner):
        return outer[0] <= inner[0] < inner[2] <= outer[2] and outer[1] <= inner[1] < inner[3] <= outer[3]

    def overlaps(left, right):
        return max(left[0], right[0]) < min(left[2], right[2]) and max(left[1], right[1]) < min(left[3], right[3])

    ancestor_rows = []
    scrolls = []
    ancestors_fit = True
    for control, box in zip(controls, boxes):
        rows, scrolling = [], set()
        current = parents.get(control)
        while current is not None and current.tag == 'node':
            match = re.fullmatch(r'\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]', current.get('bounds', ''))
            if match is None:
                ancestors_fit = False
            else:
                frame = list(map(int, match.groups()))
                visible = current.get('visible-to-user') != 'false'
                rows.append(dict(viewClass=current.get('class'), bounds=frame, visible=visible))
                ancestors_fit &= visible and contains(frame, box)
                if current.get('class') == 'android.widget.ScrollView':
                    scrolling.add(current)
            current = parents.get(current)
        ancestor_rows.append(rows)
        scrolls.append(scrolling)
    minimum_touch = (48 * api['DENSITY'] + 159) // 160
    same_row = abs(boxes[0][1] - boxes[1][1]) <= 1 and abs(boxes[0][3] - boxes[1][3]) <= 1
    top_offset = None if capsule_box is None else (capsule_box[0] + capsule_box[2] - api['WIDTH']) / 2
    nav_top = min(box[1] for box in navigation['bounds'].values()) if navigation is not None else None
    checks = dict(
        completeAccessibleLabels=all(control.get('text') == label for control, label in zip(controls, labels)),
        minimumTouchTargets=all(box[2] - box[0] >= minimum_touch and box[3] - box[1] >= minimum_touch for box in boxes),
        sameHorizontalRow=same_row,
        actionsDoNotOverlap=not overlaps(*boxes),
        visibleAncestorsContainActions=bool(ancestor_rows[0] and ancestor_rows[1]) and ancestors_fit,
        sharedLoadingScroller=bool(scrolls[0].intersection(scrolls[1])),
        navigationValid=navigation is not None and navigation['valid'],
        topCapsuleCentered=top_offset is not None and abs(top_offset) <= 1,
        belowTopCapsule=capsule_box is not None and all(box[1] >= capsule_box[3] for box in boxes),
        aboveDock=nav_top is not None and all(box[3] <= nav_top for box in boxes),
        systemBarsDoNotOverlap=all(not overlaps(box, bar) for box in boxes for bar in system_bar_frames))
    return dict(coordinateSpace='native XML screen pixels', screenWidthPx=api['WIDTH'],
        screenHeightPx=api['HEIGHT'], configuredDensityDpi=api['DENSITY'],
        minimumTouchTargetDp=48, minimumTouchTargetPx=minimum_touch,
        bounds={label: list(box) for label, box in zip(labels, boxes)},
        leftToRightLabels=[label for label, box in sorted(zip(labels, boxes), key=lambda item: item[1][0])],
        ancestors={label: rows for label, rows in zip(labels, ancestor_rows)},
        topCapsuleBounds=list(capsule_box) if capsule_box is not None else None,
        topCapsuleCenterOffsetPx=top_offset, navigation=navigation,
        observedVisibleSystemBarFrames=[list(box) for box in system_bar_frames],
        glyphAppearanceVerified=False, checks=checks, valid=all(checks.values()))


def capture_loading_landscape(args, report, capture, adb, wait_for, screenshot, api):
    """Photograph the unconfigured production loading page before local documents."""
    identity = report['buildIdentity']
    result = report['landscapeLoadingUi'] = dict(schema=1, status='started', required=True,
        sourceCommit=identity['sourceCommit'], sourceTree=identity['sourceTree'],
        apkSha256=report['installedApk']['sha256'], runNonce=report['runNonce'],
        sdkReceiptSha256=identity['sdkReceiptSha256'],
        integrationSigningCertificateSha256=identity['integrationSigningCertificateSha256'],
        helperSha256=api['sha'](__file__),
        observationNonce=secrets.token_hex(16), actualAndroidExecution=True,
        testSignedIntegrationEvidence=True, releaseSignatureAcceptance=False,
        physicalPhoneAcceptance=False, glyphAppearanceVerified=False,
        requestedDisplay=dict(widthDp=892, heightDp=412, densityDpi=480, fontScale=1.0, night='no'),
        scene='actual-MainActivity-unconfigured-loading-landscape',
        fixture='existing UiVisualIntegrationActivity visualAction=chat',
        sourceLoadingUiSha256=api['sha'](args.root / 'app/src/main/java/local/pocketchat/LoadingUi.java'),
        fixtureSourceSha256=api['sha'](args.root / 'tests/gecko/UiVisualIntegrationActivity.java'),
        firstInputIndex=len(report['inputs']), firstCommandIndex=len(report['commands']),
        startedAtUnixNs=time.time_ns(), errors=[])
    previous_display = (api['WIDTH'], api['HEIGHT'], api['DENSITY'])
    display = GlassDisplay(adb, args.out, api['sha'])
    previous_state = None
    result['displayHelperSha256'] = api['sha'](Path(__file__).with_name('glass_display.py'))
    package = api['PACKAGE']
    stem = 'landscape-loading-native'

    def save():
        api['write'](args.out / 'capture.json', report)

    try:
        previous_state = display.observe(stem + '-previous')
        result['previousDisplay'] = previous_state
        if abs(float(previous_state['fontScale']) - 1.0) > .001:
            raise ValueError('The required landscape observation must start after default-font restoration')
        api['set_display'](2676, 1236, 480)
        adb('shell', 'am', 'force-stop', package)
        result['displayPreparation'] = display.prepare(api['COMPONENT'], stem + '-preparation')
        display.configure(2676, 1236, 480, 1.0, 'no')
        result['displayPreparation']['configuredDisplay'] = display.require(
            2676, 1236, 480, 1.0, 'no', stem + '-prepared')
        # CLEAR_TOP recreates this standard Activity instead of delivering the
        # scene intent to the existing empty display-preparation instance.
        adb('shell', 'am', 'start', '-W', '-n', api['COMPONENT'],
            '--activity-clear-top', '--es', 'visualAction', 'chat')
        result['actualDisplay'] = display.require(2676, 1236, 480, 1.0, 'no', stem)

        def loading_scroller(xml):
            root = ET.fromstring(xml)
            parents = {child: parent for parent in root.iter() for child in parent}
            found = set()
            for node in root.iter('node'):
                if (node.get('package') != package or node.get('visible-to-user') == 'false'
                        or node.get('text') not in ('等待 VPN 连接', '网页暂时无法打开')):
                    continue
                current = parents.get(node)
                while current is not None:
                    if current.get('class') == 'android.widget.ScrollView' and api['bounds'](current) is not None:
                        found.add(current)
                        break
                    current = parents.get(current)
            return next(iter(found)) if len(found) == 1 else None

        def native_loading(xml):
            return api['navigation'](xml) is not None and api['capsule'](xml) is not None and loading_scroller(xml) is not None

        initial_stem = stem + '-before-scroll'
        xml = wait_for(capture, native_loading, initial_stem, seconds=30)
        screenshot(initial_stem + '.png')
        initial_png = verify_png(args.out / (initial_stem + '.png'), 2676, 1236)
        initial_geometry = loading_actions_geometry(xml, api)
        result['initialObservation'] = dict(xml=initial_stem + '.xml',
            xmlSha256=api['sha'](args.out / (initial_stem + '.xml')),
            png=initial_stem + '.png', pngSha256=api['sha'](args.out / (initial_stem + '.png')),
            geometry=initial_geometry, pngDimensions=initial_png)
        # LoadingUi deliberately scrolls short windows. Reveal its real actions
        # once if the initial viewport clips them; never press a network/reload
        # action, change visibility, or relax the final complete-target checks.
        need_scroll = initial_geometry is None or any(not initial_geometry['checks'][key]
            for key in ('minimumTouchTargets', 'visibleAncestorsContainActions', 'aboveDock'))
        result['scrollToRevealActions'] = dict(inputIssued=False)
        if need_scroll:
            box = api['bounds'](loading_scroller(xml))
            nav_top = min(frame[1] for frame in api['navigation_geometry'](xml)['bounds'].values())
            title_bottom = api['bounds'](api['capsule'](xml))[3]
            edge = 8 * api['DENSITY'] // 160
            top, bottom = max(box[1], title_bottom) + edge, min(box[3], nav_top) - edge
            if bottom - top < 48 * api['DENSITY'] // 160:
                raise ValueError('The observed loading scroller has no safe native swipe region')
            x = (box[0] + box[2]) // 2
            action = dict(action='swipe', phase='required-landscape-loading',
                reason='Reveal original loading actions within the observed short-window ScrollView',
                observedBounds=list(box), start=[x, bottom], end=[x, top], durationMillis=350,
                hierarchySource=initial_stem + '.xml', atUnixNs=time.time_ns())
            report['inputs'].append(action)
            adb('shell', 'input', 'touchscreen', 'swipe', str(x), str(bottom), str(x), str(top), '350')
            action['completedAtUnixNs'] = time.time_ns()
            result['scrollToRevealActions'] = dict(inputIssued=True, input=action)

        def actions_visible(value):
            return (api['navigation'](value) is not None and api['capsule'](value) is not None
                and all(api['button'](value, label) is not None for label in ('检查网络', '重新加载')))

        xml = wait_for(capture, actions_visible, stem, seconds=30)
        result['xml'] = dict(file=stem + '.xml', sha256=api['sha'](args.out / (stem + '.xml')))
        # Capture before geometry assertions so a real regression retains its
        # original screen rather than only a timeout or a host-side assertion.
        time.sleep(.6)
        screenshot(stem + '.png')
        result['png'] = dict(file=stem + '.png', sha256=api['sha'](args.out / (stem + '.png')))
        result['pngDimensions'] = verify_png(args.out / (stem + '.png'), 2676, 1236)
        activity = adb('shell', 'dumpsys', 'activity', 'activities').decode('utf-8', 'replace')
        path = args.out / (stem + '-activity.txt'); path.write_text(activity)
        resumed = [line.strip() for line in activity.splitlines() if 'mResumedActivity' in line or 'topResumedActivity' in line]
        result['activity'] = dict(file=path.name, sha256=api['sha'](path), resumed=resumed)
        if not any(package + '/local.pocketchat.MainActivity' in line for line in resumed):
            raise ValueError('The actual production MainActivity is not resumed on the loading page')
        raw = adb('shell', 'dumpsys', 'window', 'displays').decode('utf-8', 'replace')
        path = args.out / (stem + '-window-insets.txt'); path.write_text(raw)
        sources = system_bar_sources(raw)
        result['systemBars'] = dict(file=path.name, sha256=api['sha'](path), sources=sources)
        visible_frames = [source['bounds'] for values in sources.values() for source in values
                          if source['visible'] and source['bounds'][0] < source['bounds'][2]
                          and source['bounds'][1] < source['bounds'][3]]
        result['geometry'] = loading_actions_geometry(xml, api, visible_frames)
        if result['geometry'] is None or not result['geometry']['valid']:
            raise ValueError('Actual landscape loading actions are clipped, overlapping, or not in one horizontal row')
        result['status'] = 'verified'
    except Exception as error:
        result['status'] = 'failed'
        if hasattr(error, 'observedDisplay'):
            result['actualDisplay'] = error.observedDisplay
        result['errors'].append(dict(stage='actual-loading-page', errorType=type(error).__name__, error=str(error)))
        if 'png' not in result:
            try:
                screenshot(stem + '-failed.png')
            except Exception as capture_error:
                result['errors'].append(dict(stage='failure-screenshot', errorType=type(capture_error).__name__, error=str(capture_error)))
    finally:
        api['set_display'](*previous_display)
        cleanup_errors = []
        try:
            adb('shell', 'am', 'force-stop', package, timeout=6)
        except Exception as error:
            cleanup_errors.append(dict(stage='stop-loading-fixture', errorType=type(error).__name__, error=str(error)))
        try:
            if previous_state is None:
                raise ValueError('Original display state was not acquired for exact restoration')
            result['restoredDisplay'] = display.restore(previous_state, stem + '-restored')
        except Exception as error:
            cleanup_errors.append(dict(stage='observe-restored-display', errorType=type(error).__name__, error=str(error)))
        result['errors'].extend(cleanup_errors)
        result['restoredDisplayBeforeControlledDocument'] = not cleanup_errors
        if cleanup_errors:
            result['status'] = 'failed'
        result.update(lastInputIndexExclusive=len(report['inputs']),
                      lastCommandIndexExclusive=len(report['commands']), completedAtUnixNs=time.time_ns())
        save()
    return result


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
    nav, capsule, geometry = [api[key] for key in ('navigation', 'capsule', 'navigation_geometry')]
    identity = report['buildIdentity']
    observations = {}
    previous_overlays = {}
    display = GlassDisplay(adb, args.out, sha)
    previous_display = None
    previous_api_display = (api['WIDTH'], api['HEIGHT'], api['DENSITY'])
    result['displayHelperSha256'] = sha(Path(__file__).with_name('glass_display.py'))

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
            item['pngDimensions'] = verify_png(args.out / (stem + '.png'), api['WIDTH'], api['HEIGHT'])
        case['observations'][suffix] = item
        save()
        return xml

    def text(xml, value):
        return bool(nodes(xml, lambda node: node.get('text') == value))

    def chat(xml):
        return nav(xml) is not None and capsule(xml) is not None and not text(xml, '打开网址') and not text(xml, '快速切换环境')

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
                    case.setdefault('documentViewportObservations', {})[command] = require_document_viewport(value['result'])
                    case.setdefault('documentObservations', {})[command] = value['result']
                    return value['result']
            time.sleep(.2)
        raise TimeoutError('No current, source/APK/SDK/nonce-bound document observation: ' + command)

    def observed_glass_pair(case, commands):
        deadline = time.monotonic() + 40
        found = {}
        while time.monotonic() < deadline:
            raw = adb('logcat', '-d', '-v', 'brief', '-s', 'PocketGeckoIntegration:I', 'AndroidRuntime:E', '*:S')
            (args.out / (case['name'] + '-events.log')).write_bytes(raw)
            if b'FATAL EXCEPTION' in raw:
                raise ValueError('Android crashed during native glass-owner observation')
            for line in raw.decode('utf-8', 'replace').splitlines():
                receipt = parse_receipt_line(line)
                if receipt is None or receipt.get('runNonce') != case['runNonce']:
                    continue
                event = observations[case['runNonce']].read(receipt)
                if event['kind'] == 'error':
                    raise ValueError('Controlled document fixture failed during native owner observation')
                if event['kind'] == 'glassOwnerObservation' and event['result'].get('command') in commands:
                    found[event['result']['command']] = event['result']
            if all(command in found for command in commands):
                return [found[command] for command in commands]
            time.sleep(.2)
        raise TimeoutError('No source/SDK/APK/nonce-bound native glass-owner observation pair')

    def quiet(case, name, allowed_delta):
        time.sleep(1.1)  # Longer than every glass press/selection release.
        values = []
        commands = [name + '-before', name + '-after']
        for index in range(2):
            # Synchronous registered receiver reads only native state; the first
            # read precedes the counter and the second follows it. No DOM or
            # snapshot/pauseObservers call occurs inside this observation.
            broadcast = shlex.join(['am', 'broadcast', '-a', package + '.CHROME_COLLAPSE', '-p', package,
                '--es', 'eventNonce', case['runNonce'], '--es', 'glassObserveCommand', commands[index]])
            counter = shlex.join(['dumpsys', 'gfxinfo', package])
            sequence = broadcast + ' && ' + counter if index == 0 else counter + ' && ' + broadcast
            raw = adb('shell', sequence).decode('utf-8', 'replace')
            path = args.out / (case['name'] + '-' + name + '-gfxinfo-' + str(index) + '.txt')
            path.write_text(raw)
            values.append(dict(file=path.name, sha256=sha(path), frames=total_frames(raw),
                               atUnixNs=time.time_ns(), **gfxinfo_owner(raw, package)))
            if index == 0:
                time.sleep(1.5)
        owner_window = dict(status='failed')
        try:
            before, after = observed_glass_pair(case, commands)
            owner_window.update(before=before, after=after)
            owner_window = validate_glass_owner_window(before, after, values, identity, case['runNonce'], commands)
        except Exception as error:
            owner_window.update(errorType=type(error).__name__, error=str(error))
        check = quiet_window_check(values, allowed_delta, owner_window)
        case.setdefault('idleObservations', {})[name] = check
        if check['processDrawFailure']:
            raise ValueError('UI continued drawing during bounded ' + name + ' observation: ' + str(check['deltaFrames']))
        if check['ownerBindingFailure']:
            raise ValueError('Native glass-owner attribution could not be bound to the required HWUI window')
        if check['hiddenAnimatorFailure']:
            raise ValueError('A hidden native glass owner retained a started or running animator')

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

    def typography(case):
        """Measure native Chinese glyphs in this exact size/theme/font configuration."""
        nonce = secrets.token_hex(16)
        adb('shell', 'am', 'start', '-W', '-n', api['COMPONENT'],
            '--activity-clear-top', '--es', 'visualAction', 'navigation-typography', '--es', 'visualNonce', nonce,
            '--es', 'visualSourceCommit', identity['sourceCommit'], '--ef', 'visualFontScale', str(case['fontScale']))
        path = args.out / (case['name'] + '-typography.log')
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
        case['typography'] = dict(file=path.name, sha256=sha(path), nonce=nonce, records=records,
            scope='Separate actual ReferenceUi.nav component; same Android size/theme/font, not MainActivity')
        labels = [row for row in records if row.get('kind') == 'label']
        expected = {(selected, index) for selected in range(-1, 4) for index in range(4)}
        keys = [(row.get('selectedIndex'), row.get('measurement', {}).get('buttonIndex')) for row in labels]
        if (len(summaries) != 1 or summaries[0].get('status') != 'verified'
                or summaries[0].get('observationCount') != 20 or len(labels) != 20
                or len(set(keys)) != 20 or set(keys) != expected):
            raise ValueError('The native Chinese navigation typography observation is incomplete or failed')
        for row in records:
            if (row.get('schema') != 1 or row.get('actualAndroidLayout') is not True
                    or any(row.get(key) != identity[key] for key in ('sourceCommit', 'sourceTree', 'apkSha256'))
                    or abs(row.get('fontScale', -1) - case['fontScale']) > .001):
                raise ValueError('Typography source/APK/font identity differs from the current case')
        for row in labels:
            measured = row['measurement']
            if (measured.get('label') != api['LABELS'][measured['buttonIndex']]
                    or measured.get('valid') is not True or not measured.get('checks')
                    or not all(value is True for value in measured['checks'].values())):
                raise ValueError('A complete Chinese navigation label did not fit its native text region')
        case['typography']['status'] = 'verified'
        case['typography']['display'] = display.require(case['widthDp'] * 3, case['heightDp'] * 3,
            480, case['fontScale'], case['requestedNight'], case['name'] + '-typography')
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
        previous_display = display.observe('glass-suite-previous')
        result['previousDisplay'] = previous_display
        loading = capture_loading_landscape(args, report, capture, adb, wait_for, screenshot, api)
        if loading['status'] != 'verified':
            result['errors'].append(dict(stage='required-landscape-loading',
                error='The required actual unconfigured landscape loading observation failed',
                reportKey='landscapeLoadingUi'))
        with controlled_document(args, adb, result, sha):
            for name, width, height, scale, night in CONFIGURATIONS:
                case = dict(name=name, runNonce=secrets.token_hex(16), status='started',
                    widthDp=width, heightDp=height, fontScale=scale, requestedNight=night,
                    observations={}, startedAtUnixNs=time.time_ns())
                result['cases'].append(case)
                try:
                    api['set_display'](width * 3, height * 3, 480)
                    adb('shell', 'am', 'force-stop', package)
                    case['displayPreparation'] = display.prepare(api['COMPONENT'], name + '-preparation')
                    display.configure(width * 3, height * 3, 480, scale, night)
                    for overlay in SAFE_AREA_OVERLAYS:
                        if name == 'safearea-light':
                            adb('shell', 'cmd', 'overlay', 'enable-exclusive', '--category', '--user', '0', overlay)
                        else:
                            adb('shell', 'cmd', 'overlay', 'disable', '--user', '0', overlay)
                    adb('shell', 'settings', 'put', 'secure', 'show_ime_with_hard_keyboard', '1')
                    case['displayPreparation']['configuredDisplay'] = display.require(
                        width * 3, height * 3, 480, scale, night, name + '-prepared')
                    typography(case)
                    observations[case['runNonce']] = EventTransfer(identity=identity, nonce=case['runNonce'],
                        slot=0, action='chromeCollapse', fetch=lambda uri: adb('exec-out', 'content', 'read', '--uri', uri))
                    adb('shell', 'am', 'start', '-W', '-n', component,
                        '--es', 'compactAction', 'collapseStart', '--ei', 'chromeNavigationVersion', '2',
                        '--es', 'eventNonce', case['runNonce'], '--ez', 'longName', 'false')
                    observed_event(case, 'ready', request=False)
                    case['display'] = display.require(width * 3, height * 3, 480, scale, night, name)
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
                    if hasattr(error, 'observedDisplay'):
                        case['display'] = error.observedDisplay
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
        api['set_display'](*previous_api_display)
        cleanup = [('shell', 'am', 'force-stop', package)]
        cleanup.extend(('shell', 'cmd', 'overlay', 'enable' if enabled else 'disable', '--user', '0', name)
                       for name, enabled in previous_overlays.items())
        for command in cleanup:
            try:
                adb(*command, timeout=6)
            except Exception as error:
                result['status'] = 'failed'
                result['errors'].append(dict(stage='restore-disposable-emulator', command=list(command),
                    errorType=type(error).__name__, error=str(error)))
        try:
            if previous_display is None:
                raise ValueError('Original display state was not acquired for exact restoration')
            result['restoredDisplay'] = display.restore(previous_display, 'glass-suite-restored')
        except Exception as error:
            result['status'] = 'failed'
            result['errors'].append(dict(stage='restore-disposable-display',
                errorType=type(error).__name__, error=str(error)))
        result['completedAtUnixNs'] = time.time_ns()
        save()
    if result['status'] != 'verified':
        raise RuntimeError('Required real glass UI observations failed; review capture.json and original artifacts')
