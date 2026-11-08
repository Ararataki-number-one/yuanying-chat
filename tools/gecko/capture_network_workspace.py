"""Original Android stills of the production network workspace.

Reuse the five local, unconfigured environments already verified by the
environment diagnostic. Navigation uses observed native buttons only. No source
is imported, network operation is requested, runtime is injected or connection
is claimed. These are visual-review images, not network or release acceptance.
"""
import json
import time

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
}


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


def complete(result):
    scenes = result.get('scenes', [])
    return (not result.get('errors') and result.get('restoredDefaultFont') is True
        and result.get('returnedToNetwork') is True and len(scenes) == len(SCENES)
        and {scene['name'] for scene in scenes} == set(SCENES)
        and all((scene['selectedTab'], scene['fontScale']) == SCENES[scene['name']] for scene in scenes))


def capture_network_workspace(args, report, capture, adb, screenshot, *, navigation_geometry):
    result = report['networkWorkspacePreview']
    identity = report['buildIdentity']
    result.update(status='started', startedAtUnixNs=time.time_ns(), actualAndroidExecution=True,
        actualProductionActivity=ACTIVITY, syntheticFixture=True,
        sourceCommit=identity['sourceCommit'], sourceTree=identity['sourceTree'],
        apkSha256=identity['apkSha256'], runNonce=report['runNonce'], runnerSha256=sha(__file__),
        scope=__doc__, viewport=dict(width=WIDTH, height=HEIGHT, densityDpi=DENSITY),
        observations=[], scenes=[], errors=[], feedbackDismissals=[], restoredDefaultFont=False,
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

    def network(tab, name):
        return observe(lambda xml: network_observation(xml, tab, navigation_geometry), name)

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

    def scene(name):
        tab, requested_scale = SCENES[name]
        scale = float(adb('shell', 'settings', 'get', 'system', 'font_scale', timeout=5).decode().strip())
        if abs(scale-requested_scale) > .001:
            raise ValueError('Actual network font scale differs from the requested scale')
        owner = activity(name)
        time.sleep(.45)
        xml, observation = network(tab, name)
        screenshot(name + '.png')
        image = dict(report['screenshots'][-1])
        if (image['width'], image['height']) != (WIDTH, HEIGHT):
            raise ValueError('Network PNG differs from the actual requested physical viewport')
        result['scenes'].append(dict(name=name, selectedTab=tab, fontScale=scale,
            hierarchy=observation, screenshot=image, activity=owner,
            textAppearanceReview='Manual PNG review; XML text is not glyph-fit evidence'))
        save()
        return xml, observation

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
