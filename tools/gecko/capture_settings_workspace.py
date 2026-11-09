"""Original Android settings stills through the real environment navigation.

The owned disposable five-environment fixture opens production activities. Only
navigation and bounded native list gestures are issued: no settings row, search
action, preference value or feedback dismissal is invoked. XML proves observed
routes and bounds; the original PNGs still require manual typography review.
"""
import json
import re
import time
import xml.etree.ElementTree as ET

from capture_environment_workspace import (
    PACKAGE, COMPONENT, WIDTH, HEIGHT, DENSITY, LABELS, bounds, named, sha,
)
from capture_network_workspace import inherited_fixture

ACTIVITY = PACKAGE + '/local.pocketchat.AppSettingsActivity'
MAIN_ACTIVITY = PACKAGE + '/local.pocketchat.MainActivity'
ENVIRONMENT_ACTIVITY = PACKAGE + '/local.pocketchat.WindowHomeActivity'
TITLE = '应用设置'
SUMMARY = '启动、外观与应用偏好'
SEARCH = '搜索设置与操作'
ENTRY_TITLES = (
    '默认环境与启动入口', '白天与黑夜', '此环境的浏览器与启动', '后台回复检测',
    '后台完成提醒', '通知与电池设置', '环境配置备份', '问题与建议', '应用更新',
    '关于与使用帮助', '功能支持范围',
)
SCENES = {'settings-default': 1.0, 'settings-large-font-1.3': 1.3,
          'settings-large-font-scrolled': 1.3}
MAX_SCROLLS = 8
EDGE_GAP = 8 * DENSITY // 160
MIN_TARGET = 48 * DENSITY // 160


def activity_observation(raw, component):
    resumed = [line.strip() for line in raw.decode('utf-8', 'replace').splitlines()
               if 'mResumedActivity' in line or 'topResumedActivity' in line]
    if not any(re.search(r'(?<!\S)' + re.escape(component) + r'(?:\s|\})', line) for line in resumed):
        raise ValueError('The expected production settings route is not resumed: ' + component)
    return dict(actualProductionActivity=component, resumedActivity=resumed)


def settings_observation(xml, navigation_geometry):
    """Read actual actionable rows and a viewport above the floating navigation."""
    geometry = navigation_geometry(xml)
    if geometry is None or not geometry['valid'] or not all(
            geometry['selected'][label] == ('true' if label == '设置' else 'false') for label in LABELS):
        return None
    title, summary, search = named(xml, TITLE), named(xml, SUMMARY), named(xml, SEARCH, button=True)
    if (title is None or title.get('text') != '设置' or summary is None or search is None
            or min(bounds(search)[2]-bounds(search)[0], bounds(search)[3]-bounds(search)[1]) < MIN_TARGET):
        return None
    root = ET.fromstring(xml)
    nodes = [n for n in root.iter('node') if n.get('package') == PACKAGE
             and n.get('visible-to-user') != 'false' and bounds(n) is not None]
    parents = {child: parent for parent in root.iter() for child in parent}
    scrolls = [n for n in nodes if n.get('class') == 'android.widget.ScrollView']
    navigation = [n for n in nodes if n.get('class') == 'android.widget.Button'
                  and n.get('text') in LABELS and n.get('clickable') == n.get('enabled') == 'true']
    if len(scrolls) != 1 or len(navigation) != len(LABELS):
        return None
    scroll = scrolls[0]
    common = navigation[0]
    while common in parents and not all(n in common.iter() for n in navigation):
        common = parents[common]
    nav_box = bounds(common)
    if nav_box is None:
        return None
    scroll_box = bounds(scroll)
    left, top, right, bottom = scroll_box
    bottom = min(bottom, nav_box[1])
    # A live hub notice belongs above the list. If any actual notice overlaps
    # it, shrink the safe viewport; never dismiss it to obtain a passing image.
    closes = [n for n in nodes if n.get('class') == 'android.widget.Button'
              and n.get('content-desc') == '关闭提示' and n.get('clickable') == n.get('enabled') == 'true']
    if len(closes) > 1:
        return None
    feedback = None
    if closes:
        notice = parents.get(closes[0])
        notice_box = bounds(notice) if notice is not None else None
        if notice_box is None:
            return None
        placement = 'above-scroll' if notice_box[3] <= top else 'below-scroll'
        if notice_box[1] < bottom and notice_box[3] > top:
            if notice_box[1] <= top:
                top = max(top, notice_box[3]); placement = 'overlaps-scroll-top'
            else:
                bottom = min(bottom, notice_box[1]); placement = 'overlaps-scroll-bottom'
        feedback = dict(bounds=list(notice_box), placement=placement,
            texts=[n.get('text') for n in notice.iter('node') if n in nodes and n.get('text')])
    safe = [left+EDGE_GAP, top+EDGE_GAP, right-EDGE_GAP, bottom-EDGE_GAP]
    if safe[2]-safe[0] < MIN_TARGET or safe[3]-safe[1] < MIN_TARGET:
        return None
    inside = lambda box: safe[0] <= box[0] < box[2] <= safe[2] and safe[1] <= box[1] < box[3] <= safe[3]
    describe = lambda n: dict(text=n.get('text', ''), description=n.get('content-desc', ''), bounds=list(bounds(n)))
    rows = []
    for label in ENTRY_TITLES:
        matches = [n for n in nodes if n.get('class') == 'android.widget.TextView' and n.get('text') == label]
        if len(matches) > 1:
            return None
        if not matches:
            continue
        text = matches[0]
        row = parents.get(text)
        while row is not None and row is not scroll and row.get('clickable') != 'true':
            row = parents.get(row)
        if (row is None or row is scroll or row not in nodes or row.get('enabled') != 'true'
                or row not in scroll.iter('node')):
            return None
        details = [n for n in row.iter('node') if n in nodes and n is not text
                   and n.get('class') == 'android.widget.TextView' and n.get('text')]
        box = bounds(row)
        target_ok = box[2]-box[0] >= MIN_TARGET and box[3]-box[1] >= MIN_TARGET
        fully_visible = bool(details) and target_ok and all(inside(bounds(n)) for n in [row, text, *details])
        rows.append(dict(title=label, bounds=list(box), titleNode=describe(text),
            details=[describe(n) for n in details], minimumTouchTarget=target_ok, fullyVisible=fully_visible))
    if not rows:
        return None
    last = next((row for row in rows if row['title'] == ENTRY_TITLES[-1]), None)
    return dict(geometry=geometry, selectedNavigation='设置',
        header=dict(title=describe(title), summary=describe(summary), search=describe(search)),
        scrollBounds=list(scroll_box), scrollable=scroll.get('scrollable') == 'true',
        navigationBounds=list(nav_box), feedback=feedback, safeViewportBounds=safe,
        edgeGapPx=EDGE_GAP, visibleRows=rows,
        fullyVisibleEntries=[row['title'] for row in rows if row['fullyVisible']],
        lastEntry=last, lastEntryFullyVisible=last is not None and last['fullyVisible'], glyphFitVerified=False)


def rows_moved_up(before, after):
    previous = {row['title']: row['bounds'] for row in before['visibleRows']}
    current = {row['title']: row['bounds'] for row in after['visibleRows']}
    return any(current[name][1] < box[1] for name, box in previous.items() if name in current)


def rows_stationary(before, after):
    previous = {row['title']: row['bounds'] for row in before['visibleRows']}
    current = {row['title']: row['bounds'] for row in after['visibleRows']}
    return bool(previous) and previous == current


def scroll_plan(observation):
    if not observation['scrollable']:
        raise ValueError('The observed settings list cannot perform a real bottom-scroll probe')
    left, top, right, bottom = observation['safeViewportBounds']
    if right-left < MIN_TARGET or bottom-top < 120*DENSITY//160:
        raise ValueError('The observed settings viewport is too small for a safe gesture')
    x, height = (left+right)//2, bottom-top
    return dict(start=[x, top+height*4//5], end=[x, top+height*2//5], durationMillis=420,
                observedBounds=observation['scrollBounds'], safeViewportBounds=observation['safeViewportBounds'])


def complete(result):
    scenes = result.get('scenes', [])
    scroll = result.get('bottomScrollPreview', {})
    embedded = result.get('embeddedMainActivityObservation', {})
    embedded_settings = embedded.get('settingsObservation') or {}
    return (not result.get('errors') and result.get('restoredDefaultFont') is True
        and result.get('returnedToEnvironment') is True
        and embedded.get('activity', {}).get('actualProductionActivity') == MAIN_ACTIVITY
        and embedded_settings.get('selectedNavigation') == '设置'
        and len(scenes) == len(SCENES) and {scene.get('name') for scene in scenes} == set(SCENES)
        and all(scene.get('fontScale') == SCENES[scene['name']]
                and scene.get('activity', {}).get('actualProductionActivity') == ACTIVITY for scene in scenes)
        and set(result.get('largeFontFullyVisibleEntries', [])) == set(ENTRY_TITLES)
        and scroll.get('status') == 'captured' and scroll.get('fullyVisible') is True
        and scroll.get('observedRowsMovedUp') is True and scroll.get('additionalSwipeStationary') is True
        and type(scroll.get('inputCount')) is int and 2 <= scroll['inputCount'] <= MAX_SCROLLS
        and scroll.get('feedbackDismissalsDuringScroll') == 0)


def capture_settings_workspace(args, report, capture, adb, screenshot, *, navigation_geometry):
    result = report['settingsWorkspacePreview']
    identity = report['buildIdentity']
    result.update(status='started', startedAtUnixNs=time.time_ns(), actualAndroidExecution=True,
        actualProductionActivity=ACTIVITY, sourceCommit=identity['sourceCommit'], sourceTree=identity['sourceTree'],
        apkSha256=identity['apkSha256'], runNonce=report['runNonce'], runnerSha256=sha(__file__), scope=__doc__,
        syntheticEnvironmentRecords=True, injectedSettingsPresentation=False,
        settingsActionsInvoked=False, settingsValuesWrittenByRunner=False, networkOperationsRequested=False,
        viewport=dict(width=WIDTH, height=HEIGHT, densityDpi=DENSITY), observations=[], scenes=[], errors=[],
        embeddedMainActivityObservation=report.get('nativeBackdropPreview', {}).get('settingsNavigation', {}),
        expectedEntries=list(ENTRY_TITLES), largeFontFullyVisibleEntries=[],
        bottomScrollPreview=dict(status='not-attempted', maxScrolls=MAX_SCROLLS, feedbackDismissalsDuringScroll=0),
        restoredDefaultFont=False, returnedToEnvironment=False,
        firstCommandIndex=len(report['commands']), firstInputIndex=len(report['inputs']))
    fixture_owned = False
    seen = set()

    def save():
        (args.out / 'capture.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')

    def failure(error, phase):
        result['errors'].append(dict(phase=phase, errorType=type(error).__name__, error=str(error)))
        save()

    def observe(predicate, name, seconds=20):
        deadline = time.monotonic() + seconds
        path = args.out / (name + '.xml')
        while time.monotonic() < deadline:
            xml = capture.read(deadline=deadline)
            path.write_text(xml)
            evidence = predicate(xml)
            if evidence:
                value = dict(file=path.name, sha256=sha(path), observedAtUnixNs=time.time_ns(),
                    **(evidence if isinstance(evidence, dict) else {}))
                result['observations'].append(value)
                save()
                return xml, value
            time.sleep(min(.2, max(0, deadline-time.monotonic())))
        raise TimeoutError('Actual settings workspace did not become ready: ' + name)

    def settings(name):
        return observe(lambda xml: settings_observation(xml, navigation_geometry), name)

    def activity(name, component=ACTIVITY):
        raw = adb('shell', 'dumpsys', 'activity', 'activities', timeout=10)
        path = args.out / (name + '-activity.txt')
        path.write_bytes(raw)
        return dict(file=path.name, sha256=sha(path), **activity_observation(raw, component))

    def environment_ready(xml):
        geometry = navigation_geometry(xml)
        return (geometry is not None and geometry['valid'] and all(
            geometry['selected'][label] == ('true' if label == '环境' else 'false') for label in LABELS)
            and named(xml, '环境管理') is not None and named(xml, '5 个环境') is not None)

    def environment(name, scale):
        adb('shell', 'am', 'force-stop', PACKAGE)
        adb('shell', 'settings', 'put', 'system', 'font_scale', str(scale))
        # An already-owned seed returns before any fixture writes, then opens
        # production WindowHomeActivity. AppSettingsActivity is not exported.
        adb('shell', 'am', 'start', '-W', '-n', COMPONENT)
        xml, observation = observe(environment_ready, name + '-environment')
        return xml, observation, activity(name + '-environment', ENVIRONMENT_ACTIVITY)

    def open_settings(name, scale):
        xml, observation, owner = environment(name, scale)
        node = named(xml, '设置', button=True)
        if node is None:
            raise ValueError('No unique actual settings navigation target')
        box = bounds(node)
        x, y = (box[0]+box[2])//2, (box[1]+box[3])//2
        event = dict(action='tap', label='设置', reason='Open production AppSettingsActivity from environment navigation',
            observedBounds=list(box), x=x, y=y, hierarchy=observation['file'], hierarchySha256=observation['sha256'],
            activity=owner, diagnostic='settings-workspace', sourceCommit=identity['sourceCommit'],
            apkSha256=identity['apkSha256'], atUnixNs=time.time_ns())
        report['inputs'].append(event)
        adb('shell', 'input', 'tap', str(x), str(y), timeout=6)
        event['completedAtUnixNs'] = time.time_ns()
        xml, observation = settings(name + '-opened')
        activity(name + '-opened')
        return xml, observation

    def remember(observation):
        seen.update(observation['fullyVisibleEntries'])
        result['largeFontFullyVisibleEntries'] = [label for label in ENTRY_TITLES if label in seen]

    def scene(name):
        scale = float(adb('shell', 'settings', 'get', 'system', 'font_scale', timeout=5).decode().strip())
        if abs(scale-SCENES[name]) > .001:
            raise ValueError('Actual settings font scale differs from the requested scale')
        owner = activity(name)
        time.sleep(.45)
        xml, observation = settings(name)
        if scale == 1.3:
            remember(observation)
        screenshot(name + '.png')
        image = dict(report['screenshots'][-1])
        if (image['width'], image['height']) != (WIDTH, HEIGHT):
            raise ValueError('Settings PNG differs from the actual requested physical viewport')
        result['scenes'].append(dict(name=name, fontScale=scale, hierarchy=observation, screenshot=image,
            activity=owner, textAppearanceReview='Manual original PNG review; XML is not glyph-fit evidence'))
        save()
        return xml, observation

    def scroll_to_bottom():
        preview = result['bottomScrollPreview']
        preview.update(status='started', inputCount=0, observedRowsMovedUp=False, additionalSwipeStationary=False,
            probes=[], firstInputIndex=len(report['inputs']), startedAtUnixNs=time.time_ns())
        xml, observation = settings('settings-large-scroll-before')
        remember(observation)
        preview.update(beforeHierarchy=observation)
        preview['probes'].append(observation)
        for attempt in range(MAX_SCROLLS):
            plan = scroll_plan(observation)
            event = dict(plan, action='scroll-down', label='Reach the actual settings list bottom',
                reason='Reveal every retained setting and independently probe the native scroll boundary',
                hierarchy=observation['file'], hierarchySha256=observation['sha256'], diagnostic='settings-workspace',
                sourceCommit=identity['sourceCommit'], apkSha256=identity['apkSha256'], atUnixNs=time.time_ns())
            report['inputs'].append(event)
            adb('shell', 'input', 'touchscreen', 'swipe', *map(str, plan['start']), *map(str, plan['end']),
                str(plan['durationMillis']), timeout=6)
            event['completedAtUnixNs'] = time.time_ns()
            preview['inputCount'] += 1
            time.sleep(.45)
            xml, after = settings('settings-large-scroll-' + str(attempt+1))
            remember(after)
            moved = rows_moved_up(observation, after)
            stationary = rows_stationary(observation, after)
            preview['observedRowsMovedUp'] = preview['observedRowsMovedUp'] or moved
            preview['probes'].append(after)
            event.update(observedRowsMovedUp=moved, observedRowsStationary=stationary,
                afterHierarchy=after['file'], afterHierarchySha256=after['sha256'])
            if (observation['lastEntryFullyVisible'] and after['lastEntryFullyVisible']
                    and preview['observedRowsMovedUp'] and stationary):
                preview['additionalSwipeStationary'] = True
                observation = after
                break
            if not moved:
                raise ValueError('The native settings swipe neither advanced known rows nor confirmed a visible bottom')
            observation = after
            save()
        if (not preview['additionalSwipeStationary'] or not observation['lastEntryFullyVisible']
                or seen != set(ENTRY_TITLES)):
            raise ValueError('The bounded native settings scroll did not expose all entries and prove the real bottom')
        xml, final = scene('settings-large-font-scrolled')
        if not final['lastEntryFullyVisible'] or not rows_stationary(observation, final):
            raise ValueError('The final settings scene moved or clipped the last entry after its bottom probe')
        preview.update(status='captured', fullyVisible=True, finalHierarchy=final,
            feedbackPresent=final['feedback'] is not None, lastInputIndexExclusive=len(report['inputs']),
            completedAtUnixNs=time.time_ns())
        save()

    try:
        result['inheritedFixture'] = inherited_fixture(report)
        installed = adb('shell', 'pm', 'path', PACKAGE, timeout=5).decode().strip()
        if (not report.get('actualAndroidExecution')
                or adb('shell', 'getprop', 'ro.kernel.qemu', timeout=5).strip() != b'1'
                or installed != 'package:' + report['installedApk']['path']
                or adb('shell', 'sha256sum', report['installedApk']['path'], timeout=10).decode().split()[0]
                    != identity['apkSha256']):
            raise ValueError('The same installed disposable integration APK is required')
        fixture_owned = True
        open_settings('settings-initial', 1.0)
        scene('settings-default')
        open_settings('settings-large', 1.3)
        scene('settings-large-font-1.3')
        scroll_to_bottom()
    except Exception as error:
        failure(error, 'settings-workspace')
    finally:
        if fixture_owned:
            try:
                xml, observation, owner = environment('settings-restored', 1.0)
                scale = float(adb('shell', 'settings', 'get', 'system', 'font_scale', timeout=5).decode().strip())
                if abs(scale-1.0) > .001:
                    raise ValueError('Settings diagnostic did not restore default font scale')
                result.update(restoredDefaultFont=True, returnedToEnvironment=True,
                    restoredHierarchy=observation, restoredActivity=owner)
            except Exception as error:
                failure(error, 'restore-settings-default-font')
        result['status'] = 'captured' if complete(result) else 'failed'
        result.update(lastCommandIndexExclusive=len(report['commands']), lastInputIndexExclusive=len(report['inputs']),
            completedAtUnixNs=time.time_ns())
        save()
