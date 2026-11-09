#!/usr/bin/env python3
"""Versioned real Android workload for address capsules and the current dock.

No product state is set to imitate a gesture or a dialog. New actions use adb
input and original accessibility bytes; the original eight 320 ms swipes,
first-tap/header readiness helpers, HOME budget and 30 s snapshot budget remain.
"""
import hashlib
import json
import pathlib
import re
import subprocess
import sys
import time
import uuid

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools/gecko'))
from integration_event_contract import EventTransfer, parse_receipt_line
from profile_invocation_contract import expected_build, verify_installed
from ui_visual_capture import UiVisualCapture
from chrome_collapse_contract_v2 import (ACTIVITY, ENVIRONMENT_ACTIVITY, PACKAGE, PHASES, NAMES,
                                         LEGACY_BEHAVIOR_MAP, inspect_ui, resumed, verify_case)
from run_chrome_collapse import resume_after_home, resume_transport


def run_v2(adb, adb_bytes, source, trace, out, focus):
    tree = subprocess.check_output(['git', 'rev-parse', 'HEAD^{tree}'], cwd=ROOT, text=True).strip()
    gradle = (ROOT/'app/build.gradle').read_text()
    identity = expected_build(out/'ui-current.apk', source, tree,
                              re.search(r"versionName '([^']+)'", gradle).group(1),
                              int(re.search(r'versionCode (\d+)', gradle).group(1)))
    verify_installed(json.loads(adb('exec-out', 'content', 'read', '--uri', 'content://'+PACKAGE+'.evidence/build-identity')), identity)
    prefix = resume_transport(sys.argv[1:])
    cases = []
    for width, scale in ((360, 1), (412, 1), (360, 2)):
        adb('shell', 'am', 'force-stop', PACKAGE); adb('logcat', '-c')
        adb('shell', 'wm', 'size', f'{width*3}x1920'); adb('shell', 'wm', 'density', '480')
        adb('shell', 'settings', 'put', 'system', 'font_scale', str(scale))
        user_text = adb('shell', 'am', 'get-current-user').strip()
        assert re.fullmatch('[0-9]+', user_text)
        user = int(user_text); nonce = uuid.uuid4().hex
        transfer = EventTransfer(identity=identity, nonce=nonce, slot=0, action='chromeCollapse',
                                 fetch=lambda uri: adb_bytes('exec-out', 'content', 'read', '--uri', uri))
        observations, inputs, native_ui = {}, [], {}
        capture = UiVisualCapture(adb=prefix[0], serial=prefix[2], source=source,
                                  diagnostics=out/('chrome-v2-ui-capture-'+nonce+'.json'))
        action = 'local.pocketchat.test.CHROME_COLLAPSE'

        def event(command):
            deadline = time.monotonic()+30
            while time.monotonic() < deadline:
                raw = adb('logcat', '-d', '-s', 'PocketGeckoIntegration:I', 'AndroidRuntime:E', '*:S')
                assert 'FATAL EXCEPTION' not in raw, raw[-5000:]
                for line in raw.splitlines():
                    receipt = parse_receipt_line(line)
                    if receipt is None or receipt.get('runNonce') != nonce: continue
                    assert receipt.get('kind') != 'eventTransportError', receipt
                    value = transfer.read(receipt)
                    assert value['kind'] != 'error', value
                    assert value['kind'] == 'collapseSnapshot', value
                    sample = value['result']; name = sample['command']
                    assert name in PHASES and (name not in observations or observations[name] == sample)
                    observations[name] = sample
                if command in observations: return observations[command]
                time.sleep(.1)
            raise TimeoutError(('No owned v2 collapse snapshot', command, raw[-5000:]))

        def send(command):
            adb('shell', 'am', 'broadcast', '-a', action, '-p', PACKAGE,
                '--es', 'eventNonce', nonce, '--es', 'collapseCommand', command)

        def snapshot(command):
            send(command)
            return event(command)

        def ui(phase):
            # Poll only observations; an input is never retried to make it pass.
            deadline = time.monotonic()+20
            wanted = ENVIRONMENT_ACTIVITY if phase in ('environment', 'drawer') else ACTIVITY
            while time.monotonic() < deadline:
                xml = capture.read(deadline=deadline)
                remaining = deadline-time.monotonic()
                if remaining <= 0: raise TimeoutError(('Native v2 observation deadline', phase))
                state = subprocess.check_output(prefix+['shell', 'dumpsys', 'activity', 'activities'], timeout=min(90, remaining)).decode('utf-8', 'strict')
                try:
                    assert resumed(state) == {(user, wanted)}
                    parsed = inspect_ui(xml, phase, observations['ready']['environmentName'])
                except AssertionError:
                    if time.monotonic() >= deadline: raise
                    time.sleep(min(.2, max(0, deadline-time.monotonic())))
                    continue
                raw, activity = xml.encode('utf-8'), state.encode('utf-8')
                native_ui[phase] = dict(phase=phase, sourceCommit=source, runNonce=nonce,
                    rawXml=xml, xmlBytes=len(raw), xmlSha256=hashlib.sha256(raw).hexdigest(),
                    activityState=state, activityBytes=len(activity), activitySha256=hashlib.sha256(activity).hexdigest())
                (out/('chrome-v2-'+nonce+'-'+phase+'.xml')).write_bytes(raw)
                return parsed
            raise TimeoutError(('Native v2 observation deadline', phase))

        def record(kind, label, before, **values):
            inputs.append(dict(kind=kind, label=label, before=before, actualAndroidInput=True, **values))

        def tap(before, label, key, *, point=None, bounds=None):
            point = observations[before][key] if point is None else point
            assert type(point) is list and len(point) == 2 and all(type(n) is int and n >= 0 for n in point)
            adb('shell', 'input', 'tap', *map(str, point))
            extra = dict(point=point)
            if bounds is not None: extra['bounds'] = bounds
            record('tap', label, before, **extra)

        def address(before, opened, returned, first=False):
            nonlocal first_readiness
            if first:
                from chrome_first_tap_readiness import first_tap_once
                first_readiness = first_tap_once(argv=sys.argv[1:], source=source, identity=identity,
                                                before=observations[before], nonce=nonce, out=out)
                record('tap', opened, before, point=first_readiness['point'])
            else: tap(before, opened, 'compactTap')
            dialog = ui(opened); snapshot(opened)
            cancel = dialog['controls'][0]
            assert cancel['label'] == '取消'
            tap(opened, returned, 'cancel', point=cancel['point'], bounds=cancel['bounds'])
            ui(returned)
            return snapshot(returned)

        def swipe(before, label, direction):
            send('clear'); s = observations[before]
            x = s['webX']+s['webWidth']//2; top = s['webY']+s['webHeight']//4; bottom = s['webY']+s['webHeight']*2//3
            start, end = ([x, bottom], [x, top]) if direction == 'up' else ([x, top], [x, bottom])
            if direction == 'horizontal': start, end = [s['webX']+s['webWidth']//4, (top+bottom)//2], [s['webX']+s['webWidth']*3//4, (top+bottom)//2]
            if direction == 'short': start, end = [x, bottom], [x, bottom-12]
            adb('shell', 'input', 'swipe', *map(str, start+end), '320')
            record('swipe', label, before, **{'from': start, 'to': end, 'durationMs': 320})
            return snapshot(label)

        def back(before, label):
            adb('shell', 'input', 'keyevent', 'KEYCODE_BACK'); record('back', label, before, key='KEYCODE_BACK')
            ui(label)
            return snapshot(label)

        adb('shell', 'am', 'start', '-W', '-n', ACTIVITY, '--es', 'compactAction', 'collapseStart',
            '--es', 'eventNonce', nonce, '--ei', 'chromeNavigationVersion', '2')
        event('ready'); first_readiness = None
        address('ready', 'initialAddress', 'initialChat', first=True)
        swipe('initialChat', 'up', 'up'); swipe('up', 'down', 'down')
        address('down', 'compactAddress', 'compactExpand')
        swipe('compactExpand', 'horizontal', 'horizontal'); swipe('horizontal', 'short', 'short')
        swipe('short', 'upBeforeChat', 'up')
        address('upBeforeChat', 'selectedAddress', 'selectedChat')
        swipe('selectedChat', 'upBeforeNative', 'up')
        tap('upBeforeNative', 'network', 'networkTap'); ui('network'); snapshot('network')
        back('network', 'nativeReturn')
        swipe('nativeReturn', 'upBeforeResume', 'up')
        resume_after_home(ACTIVITY)
        record('homeRoundtrip', 'activityResume', 'upBeforeResume', component=ACTIVITY, originalBudgetMs=20000)
        snapshot('activityResume')
        address('activityResume', 'resumeAddress', 'resumeChat')
        send('clear'); before = observations['resumeChat']
        from chrome_header_readiness import header_up_once
        header_readiness = header_up_once(argv=sys.argv[1:], source=source, identity=identity,
                                          start=before['headerSwipeFrom'], end=before['headerSwipeTo'], nonce=nonce, out=out)
        record('swipe', 'headerUp', 'resumeChat', **{'from': before['headerSwipeFrom'], 'to': before['headerSwipeTo'], 'durationMs': 320})
        snapshot('headerUp'); focus('local.pocketchat.CompactChromeIntegrationActivity')
        # Additional current-UI contracts occur after the original zero-menu,
        # zero-Activity header protection has already been observed.
        address('headerUp', 'extrasAddress', 'extrasExpanded')
        tap('extrasExpanded', 'environment', 'environmentTap'); ui('environment')
        back('environment', 'environmentReturn')
        tap('environmentReturn', 'downloads', 'downloadsTap'); ui('downloads'); snapshot('downloads')
        back('downloads', 'downloadsReturn')
        tap('downloadsReturn', 'reading', 'readingTap'); ui('reading'); snapshot('reading')
        tap('reading', 'readingExit', 'readingExitTap'); ui('readingExit'); snapshot('readingExit')
        tap('readingExit', 'readingBackMode', 'readingTap'); ui('readingBackMode'); snapshot('readingBackMode')
        back('readingBackMode', 'readingBack')
        point = observations['readingBack']['addressTap']
        adb('shell', 'input', 'swipe', *map(str, point+point), '700')
        record('longPress', 'environmentPicker', 'readingBack', point=point, durationMs=700)
        picker = ui('environmentPicker'); snapshot('environmentPicker')
        tap('environmentPicker', 'pickerReturn', 'closePicker', point=picker['closePoint'], bounds=picker['closeBounds'])
        ui('pickerReturn'); snapshot('pickerReturn')
        tap('pickerReturn', 'more', 'moreTap'); ui('more'); snapshot('more')
        back('more', 'moreReturn')
        tap('moreReturn', 'drawer', 'drawerTap'); ui('drawer')
        back('drawer', 'drawerReturn')
        initial = observations['initialChat']
        requests = [r for r in trace if r['kind'] == 'http' and r['path'] == '/c/reload-collapse' and r['documentMarker'] == initial['document']]
        case = dict(navigationContract=2, viewport=width, fontScale=scale, androidUser=user,
                    runNonce=nonce, sourceCommit=source, actualAndroidExecution=True,
                    actualGeckoExecution=True, actualAndroidTouchExecution=True,
                    checks=[{'name': name, 'pass': True} for name in NAMES],
                    legacyBehaviorMap=[list(row) for row in LEGACY_BEHAVIOR_MAP],
                    observations=observations, actualAndroidInputs=inputs, nativeUi=native_ui,
                    firstTapReadiness=first_readiness, headerReadiness=header_readiness,
                    eventTransfer=dict(runNonce=nonce, fixtureAction='chromeCollapse', processSlot=0, events=transfer.records),
                    fixtureRequests=requests)
        verify_case(case, identity)
        cases.append(case)
    return dict(navigationContract=2, status='passed', actualAndroidExecution=True,
                actualGeckoExecution=True, actualAndroidTouchExecution=True, sourceCommit=source,
                buildIdentity=identity, cases=cases,
                scope='Actual production chrome and protected local Gecko document with synthetic login/draft/task; no real ChatGPT acceptance or phone performance claim.')
