"""Original Android stills of the production network workspace.

Reuse the five local, unconfigured environments already verified by the
environment diagnostic. Inputs use observed native buttons and bounded list
gestures. No source
is imported, network operation is requested, runtime is injected or connection
is claimed. These are visual-review images, not network or release acceptance.
"""
import json
import time
import xml.etree.ElementTree as ET

from capture_environment_workspace import (
    PACKAGE, COMPONENT, WIDTH, HEIGHT, DENSITY, LABELS, bounds, named, sha, visible_nodes,
)

ACTIVITY = PACKAGE + '/local.pocketchat.MainActivity'
TABS = ('环境网络', '入口', '出口')
SUMMARIES = {
    '环境网络': '5 个环境 · 0 个已连接',
    '入口': '0 个入口订阅',
    '出口': '0 个出口订阅 · 0 个固定出口',
}
SCENES = {
    'network-default': ('环境网络', 1.0),
    'network-entry': ('入口', 1.0),
    'network-exit': ('出口', 1.0),
    'network-large-font-1.3': ('环境网络', 1.3),
    'network-large-font-scrolled': ('环境网络', 1.3),
}
LAST_ENVIRONMENT = '翻译与写作'
MAX_SCROLLS = 3
EDGE_GAP = 8 * DENSITY // 160


def network_observation(xml, tab, navigation_geometry):
    """Require the real five-item route, unique selected tab and loaded counts."""
    if tab not in TABS:
        return None
    geometry = navigation_geometry(xml)
    if geometry is None or not geometry['valid'] or not all(
            geometry['selected'][label] == ('true' if label == '网络' else 'false') for label in LABELS):
        return None
    controls = {label: named(xml, label, button=True) for label in TABS}
    if any(node is None or node.get('selected') != ('true' if label == tab else 'false')
           for label, node in controls.items()):
        return None
    nodes = visible_nodes(xml)
    if (named(xml, SUMMARIES[tab]) is None
            or not any(node.get('class') == 'android.widget.ScrollView' for node in nodes)
            or any(node.get('text', '').startswith('正在读取窗口网络') for node in nodes)):
        return None
    statuses = [dict(label=node.get('content-desc'), bounds=list(bounds(node))) for node in nodes
                if node.get('content-desc', '').startswith('网络状态：')]
    # A screenshot with a connected badge cannot pass as this unconfigured
    # fixture, even if an unrelated count label still says zero.
    if (tab == TABS[0] and not statuses) or any(value['label'] == '网络状态：已连接' for value in statuses):
        return None
    return dict(geometry=geometry, selectedTab=tab, summary=SUMMARIES[tab],
        tabs={label: dict(bounds=list(bounds(node)), selected=node.get('selected'))
              for label, node in controls.items()}, visibleNetworkStatuses=statuses)


def inherited_fixture(report):
    """Do not launch a new or unrelated fixture when the prior capture failed."""
    value = report.get('environmentWorkspacePreview', {})
    identity = report['buildIdentity']
    if (value.get('status') != 'captured' or value.get('seededEnvironmentCount') != 5
            or value.get('restoredDefaultFont') is not True
            or value.get('runNonce') != report['runNonce']
            or any(value.get(key) != identity[key] for key in ('sourceCommit', 'sourceTree', 'apkSha256'))
            or not value.get('restoredHierarchy') or not value.get('restoredActivity')):
        raise ValueError('A completed source-bound five-environment capture must precede network stills')
    return dict(source='environmentWorkspacePreview', seededEnvironmentCount=5,
        sourceCommit=value['sourceCommit'], sourceTree=value['sourceTree'], apkSha256=value['apkSha256'],
        runNonce=value['runNonce'], restoredHierarchy=value['restoredHierarchy'],
        restoredActivity=value['restoredActivity'], resetPerformed=False,
        scope='Same five unconfigured local records; no added source or synthetic runtime')


def last_card_layout(xml, navigation_geometry):
    """Measure current content and overlays without treating an inline notice as a bottom overlay."""
    root = ET.fromstring(xml)
    nodes = [n for n in root.iter('node') if n.get('package') == PACKAGE
             and n.get('visible-to-user') != 'false' and bounds(n) is not None]
    parents = {child: parent for parent in root.iter() for child in parent}
    scrolls = [n for n in nodes if n.get('class') == 'android.widget.ScrollView']
    if len(scrolls) != 1:
        raise ValueError('A unique observed native network ScrollView is required')
    scroll = scrolls[0]
    scroll_box = bounds(scroll)
    geometry = navigation_geometry(xml)
    if geometry is None or not geometry['valid']:
        raise ValueError('The real five-destination navigation is required for scroll bounds')
    navigation = [n for n in nodes if n.get('class') == 'android.widget.Button'
                  and n.get('text') in LABELS and n.get('clickable') == n.get('enabled') == 'true']
    if len(navigation) != len(LABELS):
        raise ValueError('Ambiguous observed network navigation')
    common = navigation[0]
    while common in parents and not all(n in common.iter() for n in navigation):
        common = parents[common]
    nav_box = bounds(common)
    if nav_box is None:
        raise ValueError('Native navigation has no measured container')
    left, top, right, bottom = scroll_box
    bottom = min(bottom, nav_box[1])
    notices = [n for n in nodes if n.get('content-desc') == '网络连接提示']
    if len(notices) > 1:
        raise ValueError('Ambiguous current network feedback container')
    feedback = None
    if notices:
        notice = notices[0]
        notice_box = bounds(notice)
        # A real inline notice occupies layout before the ScrollView. It must
        # not incorrectly turn the entire scrollable area into an unsafe zone.
        placement = 'above-scroll' if notice_box[3] <= top else 'below-scroll'
        if notice_box[1] < bottom and notice_box[3] > top:
            if notice_box[1] <= top:
                top = max(top, notice_box[3]); placement = 'overlaps-scroll-top'
            else:
                bottom = min(bottom, notice_box[1]); placement = 'overlaps-scroll-bottom'
        feedback = dict(bounds=list(notice_box), placement=placement,
            texts=[n.get('text') for n in notice.iter('node') if n in nodes and n.get('text')])
    safe = [left+EDGE_GAP, top+EDGE_GAP, right-EDGE_GAP, bottom-EDGE_GAP]
    rows = sorted([n.get('content-desc'), list(bounds(n))] for n in nodes
        if n.get('class') == 'android.widget.Button' and n.get('content-desc', '').endswith('的更多网络操作'))
    cards = [n for n in nodes if n.get('content-desc', '').startswith(LAST_ENVIRONMENT+'，')
             and n.get('content-desc', '').endswith('，查看窗口详情')]
    if len(cards) > 1:
        raise ValueError('Ambiguous final environment card')
    card, complete = None, False
    if cards:
        node = cards[0]
        descendants = [n for n in node.iter('node') if n in nodes]
        title = [n for n in descendants if n.get('class') == 'android.widget.TextView' and n.get('text') == LAST_ENVIRONMENT]
        status = [n for n in descendants if n.get('class') == 'android.widget.TextView'
                  and n.get('content-desc', '').startswith('网络状态：')]
        details = [n for n in descendants if n.get('class') == 'android.widget.TextView' and n.get('text')
                   and n not in title and n not in status]
        actions = {label: [n for n in descendants if n.get('content-desc') == description
                   and n.get('class') == 'android.widget.Button' and n.get('clickable') == n.get('enabled') == 'true']
                   for label, description in (('edit','编辑网络 · '+LAST_ENVIRONMENT), ('more',LAST_ENVIRONMENT+'的更多网络操作'))}
        describe = lambda n: dict(text=n.get('text',''), description=n.get('content-desc',''), bounds=list(bounds(n)))
        card = dict(name=LAST_ENVIRONMENT, bounds=list(bounds(node)), description=node.get('content-desc'),
            title=[describe(n) for n in title], status=[describe(n) for n in status],
            details=[describe(n) for n in details], actions={label:[describe(n) for n in values] for label,values in actions.items()})
        targets = [node, *title, *status, *details, *actions['edit'], *actions['more']]
        inside = lambda b: safe[0] <= b[0] < b[2] <= safe[2] and safe[1] <= b[1] < b[3] <= safe[3]
        complete = (len(title) == 1 and len(status) == 1 and bool(details)
            and all(len(values) == 1 for values in actions.values()) and all(inside(bounds(n)) for n in targets)
            and all(bounds(n)[2]-bounds(n)[0] >= 48*DENSITY//160 and bounds(n)[3]-bounds(n)[1] >= 48*DENSITY//160
                    for values in actions.values() for n in values))
    return dict(environmentName=LAST_ENVIRONMENT, scrollBounds=list(scroll_box), scrollable=scroll.get('scrollable') == 'true',
        navigationBounds=list(nav_box), feedback=feedback, safeViewportBounds=safe, edgeGapPx=EDGE_GAP,
        visibleRows=rows, lastCard=card, fullyVisible=complete, glyphFitVerified=False)


def scroll_plan(layout):
    if layout['fullyVisible']:
        return None
    if not layout['scrollable']:
        raise ValueError('The final card is obscured but the real native list cannot scroll')
    left, top, right, bottom = layout['safeViewportBounds']
    if right-left < 48*DENSITY//160 or bottom-top < 120*DENSITY//160:
        raise ValueError('The observed network viewport is too small for a safe scroll')
    card = layout['lastCard']
    needed = card['bounds'][3]-bottom if card is not None else (bottom-top)//3
    if needed <= 0:
        raise ValueError('The final card lacks complete visible semantics; upward scrolling cannot repair it')
    x, start = (left+right)//2, top+(bottom-top)*4//5
    distance = min(max(48*DENSITY//160, needed+16*DENSITY//160), (bottom-top)*3//5)
    return dict(start=[x,start], end=[x,start-distance], durationMillis=420,
        observedBounds=layout['scrollBounds'], safeViewportBounds=layout['safeViewportBounds'])


def rows_moved_up(before, after):
    previous, current = dict(before['visibleRows']), dict(after['visibleRows'])
    return any(current[name][1] < box[1] for name,box in previous.items() if name in current)


def complete(result):
    scenes = result.get('scenes', [])
    scroll = result.get('lastCardPreview', {})
    return (not result.get('errors') and result.get('restoredDefaultFont') is True
        and result.get('returnedToNetwork') is True and len(scenes) == len(SCENES)
        and {scene['name'] for scene in scenes} == set(SCENES)
        and all((scene['selectedTab'], scene['fontScale']) == SCENES[scene['name']] for scene in scenes)
        and scroll.get('status') == 'captured' and scroll.get('fullyVisible') is True
        and scroll.get('feedbackDismissalsDuringScroll') == 0
        and type(scroll.get('inputCount')) is int
        and ((scroll.get('inputCount') == 0 and scroll.get('scrollRequired') is False and bool(scroll.get('skipReason')))
             or (type(scroll.get('inputCount')) is int and 1 <= scroll['inputCount'] <= MAX_SCROLLS
                 and scroll.get('scrollRequired') is True and scroll.get('observedRowsMovedUp') is True)))


def capture_network_workspace(args, report, capture, adb, screenshot, *, navigation_geometry):
    result = report['networkWorkspacePreview']
    identity = report['buildIdentity']
    result.update(status='started', startedAtUnixNs=time.time_ns(), actualAndroidExecution=True,
        actualProductionActivity=ACTIVITY, syntheticFixture=True,
        sourceCommit=identity['sourceCommit'], sourceTree=identity['sourceTree'],
        apkSha256=identity['apkSha256'], runNonce=report['runNonce'], runnerSha256=sha(__file__),
        scope=__doc__, viewport=dict(width=WIDTH, height=HEIGHT, densityDpi=DENSITY),
        observations=[], scenes=[], errors=[], feedbackDismissals=[], restoredDefaultFont=False,
        lastCardPreview=dict(status='not-attempted', maxScrolls=MAX_SCROLLS, feedbackDismissalsDuringScroll=0),
        returnedToNetwork=False, networkOperationsRequested=False, runtimeInjected=False,
        firstCommandIndex=len(report['commands']), firstInputIndex=len(report['inputs']))
    fixture_owned = False

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
                observation = dict(file=path.name, sha256=sha(path), observedAtUnixNs=time.time_ns(),
                    **(evidence if isinstance(evidence, dict) else {}))
                result['observations'].append(observation)
                save()
                return xml, observation
            time.sleep(min(.2, max(0, deadline-time.monotonic())))
        raise TimeoutError('Actual network workspace did not become ready: ' + name)

    def network(tab, name, *, last_card=False, fully_visible=False):
        def ready(xml):
            evidence = network_observation(xml, tab, navigation_geometry)
            if evidence and last_card:
                evidence['lastCardLayout'] = last_card_layout(xml, navigation_geometry)
                if fully_visible and not evidence['lastCardLayout']['fullyVisible']:
                    return None
            return evidence
        return observe(ready, name)

    def tap(xml, label, observation):
        if label not in ('网络', *TABS, '关闭提示'):
            raise ValueError('Network stills only navigate tabs or dismiss one observed notice')
        node = named(xml, label, button=True)
        if node is None or (label == '关闭提示' and node.get('text') != '×'):
            raise ValueError('No unique observed native control: ' + label)
        box = bounds(node)
        x, y = (box[0]+box[2])//2, (box[1]+box[3])//2
        event = dict(action='tap', label=label, reason='Native network visual review: ' + label,
            observedBounds=list(box), x=x, y=y, hierarchy=observation['file'],
            hierarchySha256=observation['sha256'], diagnostic='network-workspace',
            sourceCommit=identity['sourceCommit'], apkSha256=identity['apkSha256'], atUnixNs=time.time_ns())
        report['inputs'].append(event)
        adb('shell', 'input', 'tap', str(x), str(y), timeout=6)
        event['completedAtUnixNs'] = time.time_ns()
        save()

    def activity(name):
        raw = adb('shell', 'dumpsys', 'activity', 'activities', timeout=10)
        path = args.out / (name + '-activity.txt')
        path.write_bytes(raw)
        resumed = [line.strip() for line in raw.decode('utf-8', 'replace').splitlines()
                   if 'mResumedActivity' in line or 'topResumedActivity' in line]
        if not any(ACTIVITY in line for line in resumed):
            raise ValueError('The production MainActivity is not resumed for network review')
        return dict(file=path.name, sha256=sha(path), resumedActivity=resumed)

    def environment_ready(xml):
        geometry = navigation_geometry(xml)
        return (geometry is not None and geometry['valid'] and all(
            geometry['selected'][label] == ('true' if label == '环境' else 'false') for label in LABELS)
            and named(xml, '环境管理') is not None and named(xml, '5 个环境') is not None)

    def open_network(name, *, scale=None):
        if scale is not None:
            adb('shell', 'am', 'force-stop', PACKAGE)
            adb('shell', 'settings', 'put', 'system', 'font_scale', str(scale))
            # This existing launcher returns early from seedFive once its
            # fixture is seeded; it never injects a network presentation.
            adb('shell', 'am', 'start', '-W', '-n', COMPONENT)
        xml, observation = observe(environment_ready, name + '-environment')
        tap(xml, '网络', observation)
        xml, observation = network(TABS[0], name + '-opened')
        time.sleep(.45)
        xml, observation = network(TABS[0], name + '-settled')
        # One observed dismissal per launch. A recurring notice is left visible.
        close = named(xml, '关闭提示', button=True)
        notice = dict(launch=name, observed=close is not None, tapIssued=False,
            hierarchy=observation['file'], hierarchySha256=observation['sha256'])
        result['feedbackDismissals'].append(notice)
        if close is not None and close.get('text') == '×':
            tap(xml, '关闭提示', observation)
            notice['tapIssued'] = True
            xml, observation = network(TABS[0], name + '-notice-dismissed')
        return xml, observation

    def scene(name, *, last_card=False):
        tab, requested_scale = SCENES[name]
        scale = float(adb('shell', 'settings', 'get', 'system', 'font_scale', timeout=5).decode().strip())
        if abs(scale-requested_scale) > .001:
            raise ValueError('Actual network font scale differs from the requested scale')
        owner = activity(name)
        time.sleep(.45)
        xml, observation = network(tab, name, last_card=last_card, fully_visible=last_card)
        screenshot(name + '.png')
        image = dict(report['screenshots'][-1])
        if (image['width'], image['height']) != (WIDTH, HEIGHT):
            raise ValueError('Network PNG differs from the actual requested physical viewport')
        result['scenes'].append(dict(name=name, selectedTab=tab, fontScale=scale,
            hierarchy=observation, screenshot=image, activity=owner,
            textAppearanceReview='Manual PNG review; XML text is not glyph-fit evidence'))
        save()
        return xml, observation

    def capture_last_card():
        preview = result['lastCardPreview']
        preview.update(status='started', inputCount=0, probes=[], observedRowsMovedUp=False,
            firstInputIndex=len(report['inputs']), startedAtUnixNs=time.time_ns())
        xml, observation = network(TABS[0], 'network-large-scroll-before', last_card=True)
        layout = observation['lastCardLayout']
        preview.update(beforeHierarchy=observation, scrollRequired=not layout['fullyVisible'])
        preview['probes'].append(observation)
        for attempt in range(MAX_SCROLLS):
            plan = scroll_plan(layout)
            if plan is None:
                break
            event = dict(plan, action='scroll-down', label='Reveal final network environment',
                reason='Move the last actual environment card above the observed viewport boundaries',
                hierarchy=observation['file'], hierarchySha256=observation['sha256'],
                diagnostic='network-workspace', sourceCommit=identity['sourceCommit'],
                apkSha256=identity['apkSha256'], atUnixNs=time.time_ns())
            report['inputs'].append(event)
            adb('shell', 'input', 'touchscreen', 'swipe', *map(str, plan['start']), *map(str, plan['end']),
                str(plan['durationMillis']), timeout=6)
            event['completedAtUnixNs'] = time.time_ns()
            preview['inputCount'] += 1
            time.sleep(.45)
            xml, observation = network(TABS[0], 'network-large-scroll-'+str(attempt+1), last_card=True)
            after = observation['lastCardLayout']
            if not rows_moved_up(layout, after):
                raise ValueError('The bounded native swipe did not move any observed environment upward')
            preview['observedRowsMovedUp'] = True
            preview['probes'].append(observation)
            layout = after
            save()
        if not layout['fullyVisible']:
            raise ValueError('The final environment remains clipped after the bounded scroll budget')
        if preview['inputCount'] == 0:
            preview['skipReason'] = 'All final-card text and actions already fit above the actual viewport boundaries'
        # Reobserve after normal scene settling. Never hide a live notice to
        # make the final card pass; the screenshot must match these fresh bounds.
        xml, observation = scene('network-large-font-scrolled', last_card=True)
        preview.update(status='captured', fullyVisible=True, finalHierarchy=observation,
            feedbackPresent=observation['lastCardLayout']['feedback'] is not None,
            lastInputIndexExclusive=len(report['inputs']), completedAtUnixNs=time.time_ns())
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
        open_network('network-initial')
        xml, observation = scene('network-default')
        tap(xml, '入口', observation)
        xml, observation = scene('network-entry')
        tap(xml, '出口', observation)
        scene('network-exit')
        open_network('network-large', scale=1.3)
        scene('network-large-font-1.3')
        capture_last_card()
    except Exception as error:
        failure(error, 'network-workspace')
    finally:
        if fixture_owned:
            try:
                xml, observation = open_network('network-restored', scale=1.0)
                scale = float(adb('shell', 'settings', 'get', 'system', 'font_scale', timeout=5).decode().strip())
                if abs(scale-1.0) > .001:
                    raise ValueError('Network diagnostic did not restore default font scale')
                result.update(restoredDefaultFont=True, returnedToNetwork=True,
                    restoredHierarchy=observation, restoredActivity=activity('network-restored'))
            except Exception as error:
                failure(error, 'restore-network-default-font')
        result['status'] = 'captured' if complete(result) else 'failed'
        result.update(lastCommandIndexExclusive=len(report['commands']),
            lastInputIndexExclusive=len(report['inputs']), completedAtUnixNs=time.time_ns())
        save()
