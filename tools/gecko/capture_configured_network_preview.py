"""Source-bound native component screenshots with explicitly synthetic network data.

This is a separate integration-only Activity, never MainActivity or real network
evidence. Existing unconfigured production screenshots and gates are untouched.
"""
import json
import time

from capture_environment_workspace import (
    PACKAGE, COMPONENT as RESTORE_COMPONENT, WIDTH, HEIGHT, LABELS, named, sha, visible_nodes,
)
from capture_network_workspace import last_card_layout, scroll_plan, rows_moved_up

COMPONENT = PACKAGE + '/local.pocketchat.ConfiguredNetworkVisualActivity'
BANNER = '示例配置 · 非真实连接'
EXPLANATION = 'IP、延迟与连接状态均为演示数据'
SUMMARY = '3 个环境 · 2 个已连接'
TAB_PREVIEWS = (
    (1, 'network-configured-synthetic-entry', '2 个入口订阅',
     ('日本入口（示例）', '多地区入口（示例）')),
    (2, 'network-configured-synthetic-exit', '2 个出口订阅 · 2 个固定出口',
     ('新加坡出口订阅（示例）', '香港出口订阅（示例）', '新加坡固定出口（示例）', '未标注地区出口（示例）')),
)


def preview_observation(xml, navigation_geometry, *, tab=0, summary=SUMMARY, required=()):
    geometry = navigation_geometry(xml)
    selected_tab = named(xml, ('环境网络', '入口', '出口')[tab], button=True)
    if (geometry is None or not geometry['valid'] or not all(
            geometry['selected'][label] == ('true' if label == '网络' else 'false') for label in LABELS)
            or named(xml, BANNER) is None or named(xml, EXPLANATION) is None
            or named(xml, summary) is None or selected_tab is None or selected_tab.get('selected') != 'true'
            or any(named(xml, label) is None for label in required)):
        return None
    return dict(geometry=geometry, syntheticNoticeVisible=True,
                networkTab=tab, expectedLabelsVisible=list(required),
                visibleStatuses=[node.get('content-desc') for node in visible_nodes(xml)
                                 if node.get('content-desc', '').startswith('网络状态：')])


def capture_configured_network_preview(args, report, capture, adb, screenshot, *, navigation_geometry):
    identity = report['buildIdentity']
    result = report['configuredNetworkSyntheticPreview'] = dict(
        status='started', syntheticPresentationOnly=True, actualNetworkEvidence=False,
        actualProductionActivity=False, component=COMPONENT, productionComponent='NetworkWorkspaceUi',
        actualAndroidExecution=False, sourceCommit=identity['sourceCommit'], sourceTree=identity['sourceTree'],
        apkSha256=identity['apkSha256'], runNonce=report['runNonce'], runnerSha256=sha(__file__),
        scope=__doc__, networkOperationsRequested=False, configurationPersisted=False,
        businessActionsInert=True, scenes=[], errors=[], inputs=[], observations=[],
        restoredDefaultFont=False, returnedToEnvironment=False,
        firstCommandIndex=len(report['commands']), firstInputIndex=len(report['inputs']))
    fixture_owned = False

    def save():
        (args.out/'capture.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')

    def observe(name, *, last=False, tab=0, summary=SUMMARY, required=()):
        deadline = time.monotonic()+20
        path = args.out/(name+'.xml')
        while time.monotonic()<deadline:
            xml = capture.read(deadline=deadline);path.write_text(xml)
            value = preview_observation(xml, navigation_geometry, tab=tab, summary=summary, required=required)
            if value:
                if last:
                    value['lastCardLayout'] = last_card_layout(xml, navigation_geometry)
                value.update(file=path.name, sha256=sha(path), observedAtUnixNs=time.time_ns())
                result['observations'].append(value);save()
                return xml, value
            time.sleep(.15)
        raise TimeoutError('Explicit synthetic component did not become ready: '+name)

    def scene(name, scale, *, last=False, tab=0, summary=SUMMARY, required=()):
        actual_scale = float(adb('shell', 'settings', 'get', 'system', 'font_scale', timeout=5).decode().strip())
        if abs(actual_scale-scale)>.001:
            raise ValueError('Synthetic preview font scale differs')
        raw = adb('shell', 'dumpsys', 'activity', 'activities', timeout=10)
        owner = args.out/(name+'-activity.txt');owner.write_bytes(raw)
        resumed = [line.strip() for line in raw.decode('utf-8', 'replace').splitlines()
                   if 'mResumedActivity' in line or 'topResumedActivity' in line]
        if not any(COMPONENT in line for line in resumed):
            raise ValueError('The separate synthetic Activity must own this image')
        result['actualAndroidExecution'] = True
        xml, evidence = observe(name, last=last, tab=tab, summary=summary, required=required)
        if last and not evidence['lastCardLayout']['fullyVisible']:
            raise ValueError('Final configured example is clipped')
        screenshot(name+'.png');image = dict(report['screenshots'][-1])
        if (image['width'],image['height'])!=(WIDTH,HEIGHT):
            raise ValueError('Unexpected actual screenshot dimensions')
        result['scenes'].append(dict(name=name, fontScale=scale, networkTab=tab, syntheticPresentationOnly=True,
            actualNetworkEvidence=False, hierarchy=evidence, screenshot=image,
            activity=dict(file=owner.name, sha256=sha(owner), resumedActivity=resumed)))
        save()

    try:
        if (report.get('networkWorkspacePreview', {}).get('status')!='captured'
                or adb('shell', 'getprop', 'ro.kernel.qemu', timeout=5).strip()!=b'1'
                or adb('shell', 'pm', 'path', PACKAGE, timeout=5).decode().strip()!='package:'+report['installedApk']['path']
                or adb('shell', 'sha256sum', report['installedApk']['path'], timeout=10).decode().split()[0]!=identity['apkSha256']):
            raise ValueError('The completed disposable source-bound network capture is required')
        fixture_owned = True
        for name, scale in (('network-configured-synthetic-default',1.0),('network-configured-synthetic-large-font-1.3',1.3)):
            adb('shell','am','force-stop',PACKAGE)
            adb('shell','settings','put','system','font_scale',str(scale))
            adb('shell','am','start','-W','-n',COMPONENT,'--es','visualNonce',report['runNonce'],
                '--es','visualSourceCommit',identity['sourceCommit'])
            xml, _ = observe(name+'-ready')
            if not any('192.0.2.18' in node.get('text','') for node in visible_nodes(xml)):
                raise ValueError('The documentation-address example was not rendered')
            scene(name,scale)
        xml, evidence = observe('network-configured-synthetic-scroll-before',last=True)
        layout = evidence['lastCardLayout'];scrolls = 0
        for attempt in range(4):
            plan = scroll_plan(layout)
            if plan is None:
                break
            event = dict(plan,action='scroll-down',diagnostic='configured-network-synthetic-preview',
                hierarchy=evidence['file'],hierarchySha256=evidence['sha256'],atUnixNs=time.time_ns())
            report['inputs'].append(event);result['inputs'].append(event)
            adb('shell','input','touchscreen','swipe',*map(str,plan['start']),*map(str,plan['end']),str(plan['durationMillis']),timeout=6)
            event['completedAtUnixNs']=time.time_ns();scrolls+=1
            time.sleep(.35)
            xml, evidence = observe('network-configured-synthetic-scroll-'+str(attempt+1),last=True)
            after = evidence['lastCardLayout']
            if not rows_moved_up(layout,after):
                raise ValueError('Synthetic preview swipe did not move observed rows')
            layout=after
        scene('network-configured-synthetic-large-font-scrolled',1.3,last=True)
        result['lastCardPreview']=dict(fullyVisible=True,inputCount=scrolls,
            skipReason='Final card already fits' if scrolls==0 else '')
        # Each list is an inert, in-memory component fixture, not a request to
        # import a subscription, select a route or perform a network lookup.
        for tab, name, summary, required in TAB_PREVIEWS:
            adb('shell','am','force-stop',PACKAGE)
            adb('shell','settings','put','system','font_scale','1.0')
            adb('shell','am','start','-W','-n',COMPONENT,'--es','visualNonce',report['runNonce'],
                '--es','visualSourceCommit',identity['sourceCommit'],'--ei','visualNetworkTab',str(tab))
            scene(name,1.0,tab=tab,summary=summary,required=required)
    except Exception as error:
        result['errors'].append(dict(errorType=type(error).__name__,error=str(error)))
    finally:
        if fixture_owned:
            try:
                adb('shell','am','force-stop',PACKAGE)
                adb('shell','settings','put','system','font_scale','1.0')
                result['restoredDefaultFont']=abs(float(adb('shell','settings','get','system','font_scale',timeout=5).decode().strip())-1.0)<.001
                adb('shell','am','start','-W','-n',RESTORE_COMPONENT)
                deadline=time.monotonic()+20
                while time.monotonic()<deadline:
                    xml=capture.read(deadline=deadline)
                    if named(xml,'环境管理') is not None and named(xml,'5 个环境') is not None and named(xml,BANNER) is None:
                        result['returnedToEnvironment']=True;break
                    time.sleep(.15)
            except Exception as error:
                result['errors'].append(dict(phase='restore',errorType=type(error).__name__,error=str(error)))
        result['status']='captured' if (not result['errors'] and len(result['scenes'])==3+len(TAB_PREVIEWS)
            and result.get('lastCardPreview',{}).get('fullyVisible') is True
            and result['restoredDefaultFont'] and result['returnedToEnvironment']) else 'failed'
        result.update(lastCommandIndexExclusive=len(report['commands']),
            lastInputIndexExclusive=len(report['inputs']),completedAtUnixNs=time.time_ns())
        save()
