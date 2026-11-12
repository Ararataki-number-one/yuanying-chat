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

from integration_event_contract import EventTransfer, ReceiptJournalDiscovery, parse_receipt_line


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


def display_configuration_commands(width, height):
    """Use the portrait emulator's natural axes, then rotate the actual display.

    Android 12 clamps a forced natural width to twice the physical width. A
    swapped `wm size` therefore cannot represent this phone's full landscape.
    The subsequent viewport observation still requires the exact logical size.
    """
    return [('shell', 'wm', 'size', str(min(width, height)) + 'x' + str(max(width, height))),
            ('shell', 'wm', 'user-rotation', 'lock', '1' if width > height else '0')]


def prepare_display(args, owner, stem, adb, api, width, height, font_scale, night):
    """Apply emulator configuration while an ordinary app owns orientation.

    Android 15's NOSENSOR launcher saves the previous user rotation and restores
    it when the next app starts. A successful wm command on that launcher can
    therefore be undone. Reuse the existing native network fixture as a setup
    surface, leave that override first, then configure and observe the display.
    Retire the setup instance so the next scene executes its own onCreate.
    This setup is not a measured scene or a typography/application pass.
    """
    result = owner['displayPreparation'] = dict(status='started',
        scope='Disposable emulator configuration before observation; not UI acceptance',
        requested=dict(widthPx=width, heightPx=height, densityDpi=480,
                       fontScale=float(font_scale), night=night), observations=[],
        configurationSurfaceStopped=False)
    deadline = time.monotonic() + 15

    def read(*parts):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('Actual Android display configuration did not settle')
        raw = adb(*parts, timeout=min(6, remaining))
        if time.monotonic() >= deadline:
            raise TimeoutError('Actual Android display configuration did not settle')
        return raw

    try:
        read('shell', 'am', 'start', '-W', '-n', api['COMPONENT'], '--es', 'visualAction', 'network')
        activity = read('shell', 'dumpsys', 'activity', 'activities').decode('utf-8', 'strict')
        resumed = [line.strip() for line in activity.splitlines()
                   if 'mResumedActivity' in line or 'topResumedActivity' in line]
        result['resumedBeforeRotation'] = resumed
        if not any(api['COMPONENT'] in line for line in resumed):
            raise ValueError('The native configuration surface did not leave the NOSENSOR launcher')
        for command in display_configuration_commands(width, height):
            read(*command)
        previous = None
        while True:
            config = read('shell', 'am', 'get-config').decode('utf-8', 'strict').strip()
            font = float(read('shell', 'settings', 'get', 'system', 'font_scale').decode().strip())
            raw = read('shell', 'dumpsys', 'window', 'displays')
            path = args.out / (stem + '-preparation-' + str(len(result['observations']) + 1) + '.txt')
            path.write_bytes(raw)
            actual = api['window_display_viewport'](raw.decode('utf-8', 'strict'))
            parts = config.splitlines()[0].split('-')
            matches = (actual == dict(widthPx=width, heightPx=height, densityDpi=480)
                       and ('land' if width > height else 'port') in parts
                       and ('night' if night == 'yes' else 'notnight') in parts
                       and abs(font - float(font_scale)) <= .001)
            result['observations'].append(dict(configuration=config, fontScale=font,
                viewport=actual, matchesRequested=matches, file=path.name,
                sha256=hashlib.sha256(raw).hexdigest()))
            current = (config, font, actual)
            if time.monotonic() >= deadline:
                raise TimeoutError('Actual Android display configuration did not settle')
            if matches and previous == current:
                # The same fixture component dispatches scenes in onCreate.
                # Its live network setup must not consume the next scene's
                # intent. The launcher now saves the final configured rotation
                # and restores it on the next app launch, as between typography modes.
                read('shell', 'am', 'force-stop', api['PACKAGE'])
                result['configurationSurfaceStopped'] = True
                result['status'] = 'verified'
                return result
            previous = current if matches else None
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError('Actual Android display configuration did not settle')
            time.sleep(min(.5, remaining))
    except Exception as error:
        result.update(status='failed', errorType=type(error).__name__, error=str(error))
        raise


def total_frames(raw):
    """Read cumulative HWUI counters; no FPS or animation-smoothness inference."""
    values = re.findall(r'^\s*Total frames rendered:\s*(\d+)\s*$', raw, re.M)
    if len(values) != 1:
        raise ValueError('Expected one actual HWUI cumulative frame counter')
    return int(values[0])


def collapse_start_trace(raw, identity, nonce):
    """Keep only this case's existing native counters, never page/user content."""
    if len(raw) > 1024 * 1024:
        raise ValueError('Collapse startup trace exceeds its bounded buffer')
    stages = {'waiting', 'route-return', 'document-ready-before', 'document-ready-after',
              'start-before', 'page-finished-before', 'page-finished-after', 'load-before',
              'load-return', 'ready-evaluate', 'ready-callback', 'snapshot-evaluate',
              'snapshot-callback', 'emit-before', 'emit-queued'}
    strings = {'runNonce', 'sourceCommit', 'sourceTree', 'stage'}
    flags = {'diagnosticOnly', 'checkpointReady', 'runtimePresent', 'extensionPresent',
             'identityPrepared', 'routePrepared', 'privacyReady', 'ready', 'failed', 'destroyed',
             'resourceDeferred', 'sessionPresent', 'surfacePresent', 'portPresent', 'usable',
             'queuedTarget', 'routePortPresent', 'guardBlocked', 'networkReady', 'browserPaused',
             'uiVisible', 'navigating', 'addonDisabled', 'metadataEnabled'}
    counters = {'schema', 'sequence', 'elapsedMs', 'requestedProtection', 'protectionRequest',
                'protectionLevel', 'documents', 'readyEvaluations', 'readyCallbacks',
                'snapshotEvaluations', 'snapshotCallbacks', 'eventSequence', 'routeCalls',
                'fixtureRoutes', 'blockedRoutes', 'otherRoutes', 'routeDelegateInstalls', 'routeConnectAttempts'}
    records, lines = [], []
    for line in raw.decode('utf-8', 'strict').splitlines():
        if not line.startswith('{'):
            continue
        value = json.loads(line)
        if type(value) is not dict or value.get('runNonce') != nonce:
            continue
        if (set(value) != strings | flags | counters
                or any(type(value[key]) is not str for key in strings)
                or any(type(value[key]) is not bool for key in flags)
                or any(type(value[key]) is not int or not -1 <= value[key] < 2**63 for key in counters)
                or value['schema'] != 1
                or value.get('diagnosticOnly') is not True
                or any(value.get(key) != identity[key] for key in ('sourceCommit', 'sourceTree'))
                or value.get('stage') not in stages
                or type(value.get('sequence')) is not int or not 1 <= value['sequence'] <= 80
                or records and value['sequence'] <= records[-1]['sequence']):
            raise ValueError('Collapse startup diagnostic identity, sequence or scalar boundary differs')
        records.append(value)
        lines.append(line)
    return records, ('\n'.join(lines) + ('\n' if lines else '')).encode('utf-8')


def capture_ready_failure(out, case, identity, adb, start_output):
    """Observe an already failed ready gate; never retry it or change its result."""
    result = case['readyFailureDiagnostics'] = dict(status='incomplete', diagnosticOnly=True,
        applicationAcceptance=False, readyGateAlreadyFailed=True, runNonce=case['runNonce'],
        sourceCommit=identity['sourceCommit'], sourceTree=identity['sourceTree'],
        scope='Post-failure existing native startup counters and resumed component; not a new readiness gate',
        errors=[])

    def save(suffix, raw):
        path = out / (case['name'] + '-' + suffix)
        path.write_bytes(raw)
        return dict(file=path.name, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())

    try:
        if not isinstance(start_output, bytes) or len(start_output) > 16384:
            raise ValueError('Controlled activity launch output exceeds its boundary')
        result['launchOutput'] = save('launch-output.txt', start_output)
    except Exception as error:
        result['errors'].append(dict(stage='launch-output', errorType=type(error).__name__, error=str(error)))
    try:
        raw = adb('logcat', '-d', '-v', 'raw', '-s', 'PocketCollapseTrace:I', '*:S', timeout=6)
        records, selected = collapse_start_trace(raw, identity, case['runNonce'])
        result['nativeTrace'] = dict(save('collapse-start-trace.log', selected), records=records,
            rawBufferBytes=len(raw), rawBufferSha256=hashlib.sha256(raw).hexdigest(),
            currentCaseOnly=True, status='captured' if records else 'missing')
    except Exception as error:
        result['errors'].append(dict(stage='native-trace', errorType=type(error).__name__, error=str(error)))
    try:
        raw = adb('logcat', '-d', '-v', 'threadtime', '-t', '300', '-s', 'WebExtension:D',
                  'GeckoRuntime:D', 'GeckoProcessManager:W', 'ServiceAllocator:W',
                  'GeckoConsole:W', 'Gecko:W', 'AndroidRuntime:E', '*:S', timeout=6)
        if len(raw) > 256 * 1024:
            raise ValueError('Gecko startup diagnostic exceeds its bounded buffer')
        result['geckoStartupLog'] = dict(save('gecko-startup.log', raw),
            currentCaseOnly=False, diagnosticOnly=True, applicationAcceptance=False,
            scope='Last 300 selected SDK log lines; not nonce-filtered or attributed to the current process')
    except Exception as error:
        result['errors'].append(dict(stage='gecko-startup-log', errorType=type(error).__name__, error=str(error)))
    try:
        raw = adb('shell', 'dumpsys', 'activity', 'activities', timeout=6)
        if len(raw) > 2 * 1024 * 1024:
            raise ValueError('Activity diagnostic exceeds its bounded buffer')
        # Retain only resumed records; the remaining task/Intent dump can contain URLs.
        lines = [line for line in raw.decode('utf-8', 'strict').splitlines()
                 if re.match(r'^\s*(?:mResumedActivity|topResumedActivity)[:=]\s*ActivityRecord\{'
                             r'[0-9a-f]+ u[0-9]+ [A-Za-z0-9_.$]+/[A-Za-z0-9_.$]+ t[0-9]+\}\s*$', line)]
        result['resumedActivity'] = dict(save('ready-failed-activity.txt',
            ('\n'.join(lines) + ('\n' if lines else '')).encode('utf-8')), records=lines,
            status='captured' if lines else 'missing')
    except Exception as error:
        result['errors'].append(dict(stage='resumed-activity', errorType=type(error).__name__, error=str(error)))
    if (not result['errors'] and result['nativeTrace']['status'] == 'captured'
            and result['resumedActivity']['status'] == 'captured'):
        result['status'] = 'captured'
    return result


def idle_draw_records(raw, identity, nonce, request, phase):
    """Parse bounded post-failure observations; these never establish acceptance."""
    rows = []
    for line in raw.splitlines():
        if not line.startswith('{'):
            continue
        row = json.loads(line)
        if row.get('request') != request or row.get('runNonce') != nonce:
            continue
        if (type(row.get('schema')) is not int or row.get('schema') != 1 or row.get('phase') != phase
                or row.get('diagnosticOnly') is not True or row.get('applicationAcceptance') is not False
                or any(row.get(key) != identity[key] for key in ('sourceCommit', 'sourceTree', 'apkSha256'))
                or row.get('kind') not in ('start', 'frame', 'stack', 'count', 'end')
                or not isinstance(row.get('data'), dict)
                or type(row.get('sequence')) is not int or row['sequence'] != len(rows) + 1):
            raise ValueError('Idle draw diagnostic identity, sequence or bounded schema mismatch')
        rows.append(row)
    if (not rows or len(rows) > 128 or rows[0]['kind'] != 'start' or rows[-1]['kind'] != 'end'
            or sum(row['kind'] == 'start' for row in rows) != 1
            or sum(row['kind'] == 'end' for row in rows) != 1
            or sum(row['kind'] == 'frame' for row in rows) > 16
            or sum(row['kind'] == 'stack' for row in rows) > 12
            or sum(row['kind'] == 'count' for row in rows) > 96):
        raise ValueError('Complete bounded idle draw diagnostic start/end required')
    end = rows[-1]['data']
    counts = [end.get(key) for key in ('callbacksInstalled', 'callbacksRestored', 'callbacksChangedByOwner', 'callbackRestoreErrors')]
    if (any(type(value) is not int or value < 0 for value in counts)
            or counts[0] > 160 or counts[0] != counts[1] + counts[2]
            or counts[3] != 0 or end.get('perfEnabledRestored') is not True):
        raise ValueError('Idle draw observer callback/performance-state restoration was incomplete')
    return rows


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
    package = api['PACKAGE']
    stem = 'landscape-loading-native'
    previous_font = '1.0'
    previous_night = 'no'

    def save():
        api['write'](args.out / 'capture.json', report)

    try:
        previous_font = adb('shell', 'settings', 'get', 'system', 'font_scale').decode().strip()
        if abs(float(previous_font) - 1.0) > .001:
            raise ValueError('The required landscape observation must start after default-font restoration')
        previous_config = adb('shell', 'am', 'get-config').decode().strip()
        previous_night = 'yes' if 'night' in previous_config.splitlines()[0].split('-') else 'no'
        api['set_display'](2676, 1236, 480)
        adb('shell', 'am', 'force-stop', package)
        adb('shell', 'settings', 'put', 'system', 'font_scale', '1.0')
        adb('shell', 'cmd', 'uimode', 'night', 'no')
        prepare_display(args, result, stem, adb, api, 2676, 1236, 1.0, 'no')
        adb('shell', 'am', 'start', '-W', '-n', api['COMPONENT'], '--es', 'visualAction', 'chat')
        result['actualDisplay'] = dict(size=adb('shell', 'wm', 'size').decode().strip(),
            density=adb('shell', 'wm', 'density').decode().strip(),
            fontScale=adb('shell', 'settings', 'get', 'system', 'font_scale').decode().strip(),
            configuration=adb('shell', 'am', 'get-config').decode().strip())
        api['observe_display_viewport'](adb, args.out, result, stem, 2676, 1236, 480)
        config_parts = result['actualDisplay']['configuration'].splitlines()[0].split('-')
        if ('land' not in config_parts or 'notnight' not in config_parts
                or abs(float(result['actualDisplay']['fontScale']) - 1.0) > .001):
            raise ValueError('Actual Android configuration did not apply landscape/default-font/light')

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
        initial_geometry = loading_actions_geometry(xml, api)
        result['initialObservation'] = dict(xml=initial_stem + '.xml',
            xmlSha256=api['sha'](args.out / (initial_stem + '.xml')),
            png=initial_stem + '.png', pngSha256=api['sha'](args.out / (initial_stem + '.png')),
            geometry=initial_geometry)
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
        result['errors'].append(dict(stage='actual-loading-page', errorType=type(error).__name__, error=str(error)))
        if 'png' not in result:
            try:
                screenshot(stem + '-failed.png')
            except Exception as capture_error:
                result['errors'].append(dict(stage='failure-screenshot', errorType=type(capture_error).__name__, error=str(capture_error)))
    finally:
        api['set_display'](*previous_display)
        cleanup = [('shell', 'am', 'force-stop', package)]
        cleanup.extend([('shell', 'settings', 'put', 'system', 'font_scale', previous_font),
                        ('shell', 'cmd', 'uimode', 'night', previous_night)])
        cleanup_errors = []
        for command in cleanup:
            try:
                adb(*command, timeout=6)
            except Exception as error:
                cleanup_errors.append(dict(stage='restore-before-controlled-document', command=list(command),
                    errorType=type(error).__name__, error=str(error)))
        try:
            preparation = result['restorationPreparation'] = {}
            try:
                prepare_display(args, preparation, stem + '-restore', adb, api,
                                *previous_display[:2], previous_font, previous_night)
            finally:
                try:
                    adb('shell', 'am', 'force-stop', package, timeout=6)
                except Exception as error:
                    cleanup_errors.append(dict(stage='stop-loading-configuration-surface',
                        errorType=type(error).__name__, error=str(error)))
            restored = result['restoredDisplay'] = dict(
                size=adb('shell', 'wm', 'size').decode().strip(),
                fontScale=adb('shell', 'settings', 'get', 'system', 'font_scale').decode().strip(),
                configuration=adb('shell', 'am', 'get-config').decode().strip())
            sizes = re.findall(r'(?:Physical|Override) size:\s*(\d+)x(\d+)', restored['size'])
            config_parts = restored['configuration'].splitlines()[0].split('-')
            expected_orientation = 'land' if previous_display[0] > previous_display[1] else 'port'
            expected_night = 'night' if previous_night == 'yes' else 'notnight'
            if (not sizes or tuple(map(int, sizes[-1])) != tuple(sorted(previous_display[:2]))
                    or abs(float(restored['fontScale']) - float(previous_font)) > .001
                    or expected_orientation not in config_parts or expected_night not in config_parts):
                raise ValueError('Actual Android display/font/theme was not restored before controlled documents')
            api['observe_display_viewport'](adb, args.out, restored, stem + '-restored', *previous_display)
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
    nav, capsule, geometry = [api[key] for key in ('navigation', 'capsule', 'observed_navigation_geometry')]
    identity = report['buildIdentity']
    observations = {}
    journals = {}
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
        timeout_message = 'No current, source/APK/SDK/nonce-bound document observation: ' + command

        def remaining():
            budget = deadline - time.monotonic()
            if budget <= 0:
                raise TimeoutError(timeout_message)
            return budget

        def bounded_read(*parts):
            raw = adb(*parts, timeout=remaining())
            remaining()
            return raw

        reader = observations[case['runNonce']]
        previous_fetch = reader.fetch
        reader.fetch = lambda uri: bounded_read('exec-out', 'content', 'read', '--uri', uri)
        try:
            while time.monotonic() < deadline:
                raw = bounded_read('logcat', '-d', '-v', 'brief', '-s', 'PocketGeckoIntegration:I', 'AndroidRuntime:E', '*:S')
                (args.out / (case['name'] + '-events.log')).write_bytes(raw)
                if b'FATAL EXCEPTION' in raw:
                    raise ValueError('Android crashed during the real UI sequence')
                for line in raw.decode('utf-8', 'replace').splitlines():
                    receipt = parse_receipt_line(line)
                    if receipt is None or receipt.get('runNonce') != case['runNonce']:
                        continue
                    if receipt.get('kind') == 'eventTransportError':
                        raise ValueError('Native complete event publication failed: ' + str(receipt))
                discovery = journals[case['runNonce']]
                journal = bounded_read('exec-out', 'content', 'read', '--uri', discovery.uri())
                (args.out / (case['name'] + '-event-receipts.json')).write_bytes(journal)
                for receipt in discovery.snapshot(journal):
                    value = reader.read(receipt)
                    remaining()
                    if value['kind'] == 'error':
                        raise ValueError('Controlled document fixture failed: ' + str(value))
                    if value['kind'] == 'collapseSnapshot' and value['result'].get('command') == command:
                        case.setdefault('documentObservations', {})[command] = value['result']
                        return value['result']
                time.sleep(min(.2, remaining()))
            raise TimeoutError(timeout_message)
        finally:
            reader.fetch = previous_fetch

    def idle_diagnostic(case, name):
        # This is a separate observation after the unchanged counter gate failed.
        # It never pauses production observers, navigates, retries the gate or
        # turns its failure into a pass. The fixture has its own cleanup deadline.
        request = secrets.token_hex(16)
        result = case.setdefault('idleDrawDiagnostics', {}).setdefault(name, dict(
            status='started', request=request, diagnosticOnly=True, applicationAcceptance=False,
            measuredGateAlreadyFailed=True,
            scope='Separate post-failure root/view/drawable observations; not the original HWUI measurement'))
        errors = []
        command = ('shell', 'am', 'broadcast', '-a', 'local.pocketchat.test.CHROME_COLLAPSE', '-p', package,
                   '--es', 'eventNonce', case['runNonce'], '--es', 'idleDrawRequest', request,
                   '--es', 'idleDrawPhase', name, '--es', 'idleDrawDiagnostic')
        try:
            adb(*command, 'start', timeout=6)
            time.sleep(1.5)
        except Exception as failure:
            errors.append(dict(stage='start', errorType=type(failure).__name__, error=str(failure)))
        finally:
            try:
                adb(*command, 'stop', timeout=6)
            except Exception as failure:
                errors.append(dict(stage='stop', errorType=type(failure).__name__, error=str(failure)))
        try:
            raw = adb('logcat', '-d', '-v', 'raw', '-s', 'PocketIdleDraw:I', '*:S', timeout=10)
            path = args.out / (case['name'] + '-' + name + '-idle-diagnostic.log')
            path.write_bytes(raw)
            result.update(file=path.name, sha256=sha(path))
            rows = idle_draw_records(raw.decode('utf-8', 'strict'), identity, case['runNonce'], request, name)
            result['records'] = rows
        except Exception as failure:
            errors.append(dict(stage='collect', errorType=type(failure).__name__, error=str(failure)))
        result.update(status='incomplete' if errors else 'captured', errors=errors)

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
            idle_diagnostic(case, name)
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
            api['verify_navigation_text'](measured, expected_labels[measured['buttonIndex']], mode, row['density'])
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
        # The same controls must remain available on the actual controlled
        # ChatGPT document, including narrow/large-font and legacy Android cases.
        # Keep every original draft, document and lifecycle check below intact.
        xml = artifact(case, 'browser-toolbar', lambda value: chat(value)
                       and api['browser_toolbar_geometry'](value) is not None)
        case['browserToolbar'] = api['browser_toolbar_geometry'](xml)
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
                    adb('shell', 'settings', 'put', 'system', 'font_scale', str(scale))
                    adb('shell', 'cmd', 'uimode', 'night', night)
                    for overlay in SAFE_AREA_OVERLAYS:
                        if name == 'safearea-light':
                            adb('shell', 'cmd', 'overlay', 'enable-exclusive', '--category', '--user', '0', overlay)
                        else:
                            adb('shell', 'cmd', 'overlay', 'disable', '--user', '0', overlay)
                    adb('shell', 'settings', 'put', 'secure', 'show_ime_with_hard_keyboard', '1')
                    prepare_display(args, case, name, adb, api, width * 3, height * 3, scale, night)
                    typography(case, 'conversation')
                    typography(case, 'workspace')
                    observations[case['runNonce']] = EventTransfer(identity=identity, nonce=case['runNonce'],
                        slot=0, action='chromeCollapse', fetch=lambda uri: adb('exec-out', 'content', 'read', '--uri', uri))
                    journals[case['runNonce']] = ReceiptJournalDiscovery(observations[case['runNonce']])
                    start_output = adb('shell', 'am', 'start', '-W', '-n', component,
                        '--es', 'compactAction', 'collapseStart', '--ei', 'chromeNavigationVersion', '2',
                        '--es', 'eventNonce', case['runNonce'], '--ez', 'longName', 'false')
                    try:
                        observed_event(case, 'ready', request=False)
                    except Exception:
                        try:
                            capture_ready_failure(args.out, case, identity, adb, start_output)
                        except Exception as diagnostic_error:
                            case.setdefault('readyFailureDiagnostics', {}).setdefault('errors', []).append(
                                dict(stage='diagnostic-collector', errorType=type(diagnostic_error).__name__,
                                     error=str(diagnostic_error)))
                        raise
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
                    api['observe_display_viewport'](adb, args.out, case, name, width * 3, height * 3, 480)
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
        cleanup = [('shell', 'am', 'force-stop', package)]
        cleanup.extend([('shell', 'settings', 'put', 'system', 'font_scale', '1.0'),
                        ('shell', 'cmd', 'uimode', 'night', 'no')])
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
            preparation = result['restorationPreparation'] = {}
            prepare_display(args, preparation, 'suite-restore', adb, api, 1236, 2676, 1.0, 'no')
        except Exception as error:
            result['status'] = 'failed'
            result['errors'].append(dict(stage='observe-disposable-emulator-restoration',
                errorType=type(error).__name__, error=str(error)))
        finally:
            try:
                adb('shell', 'am', 'force-stop', package, timeout=6)
            except Exception as error:
                result['status'] = 'failed'
                result['errors'].append(dict(stage='stop-configuration-surface',
                    errorType=type(error).__name__, error=str(error)))
        result['completedAtUnixNs'] = time.time_ns()
        save()
    if result['status'] != 'verified':
        raise RuntimeError('Required real glass UI observations failed; review capture.json and original artifacts')
