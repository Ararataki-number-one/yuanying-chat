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
from chrome_parser_preparation import prepare_parser
from chrome_collapse_contract_v2 import (ACTIVITY, ENVIRONMENT_ACTIVITY, PACKAGE, PHASES, BROWSER_NAMES, BROWSER_STARTUP_MAP,
                                         LEGACY_BEHAVIOR_MAP, address_cancel, inspect_ui, resumed, verify_case,
                                         make_short_target_proof, verify_short_target)
from run_chrome_collapse import resume_after_home, resume_transport


def cancel_address_once(*, observe, snapshot, tap, opened, returned):
    """Reobserve after the original snapshot within one original UI budget."""
    deadline = time.monotonic()+20
    observe(opened, deadline=deadline)
    sample = snapshot(opened)
    dialog = observe(opened, deadline=deadline, address_sample=sample)
    cancel = address_cancel(sample, dialog)
    if time.monotonic() >= deadline:
        raise TimeoutError(('Native v2 observation deadline before cancel input', opened))
    tap(opened, returned, 'cancel', point=cancel['point'], bounds=cancel['bounds'])


def short_swipe_once(*, capture, prefix, identity, nonce, android_user, before, diagnostic=None):
    """Choose a non-editable target from fresh bytes before one original input.

    Accessibility and Activity observations share the first twenty seconds of
    the original ninety-second adb action budget. No input is retried, and the
    unchanged caller owns the single subsequent thirty-second snapshot.
    """
    started_ns = time.monotonic_ns()
    diagnostic = {} if diagnostic is None else diagnostic
    diagnostic.update(schema=1, sourceCommit=identity['sourceCommit'], runNonce=nonce,
        diagnosticOnly=True, releaseAcceptance=False, status='preparing', inputInvocations=0,
        originalActionBudgetMs=90000, preparationBudgetMs=20000, actionStartedMonotonicNanos=started_ns)
    preparation_deadline = (started_ns + 20_000_000_000) / 1_000_000_000
    action_deadline = (started_ns + 90_000_000_000) / 1_000_000_000
    xml = capture.read(deadline=preparation_deadline)
    assert capture.diagnostics.is_file() and not capture.diagnostics.is_symlink()
    original = json.loads(capture.diagnostics.read_bytes())
    assert original['schema'] == 1 and original['sourceCommit'] == identity['sourceCommit']
    assert original['runNonce'] == capture.nonce and original['attemptCount'] == capture.count
    captured = original['attempts'][-1]
    assert captured['index'] == capture.count and captured['status'] == 'captured'
    remaining = preparation_deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError('Original short-swipe preparation budget expired before Activity observation')
    activity_started_ns = time.monotonic_ns()
    activity = subprocess.check_output(prefix + ['shell', 'dumpsys', 'activity', 'activities'],
                                       timeout=min(90, remaining)).decode('utf-8', 'strict')
    activity_completed_ns = time.monotonic_ns()
    proof = make_short_target_proof(raw_xml=xml, activity_state=activity, identity=identity,
        nonce=nonce, android_user=android_user, before=before, capture_nonce=capture.nonce,
        capture_record=captured, action_started_ns=started_ns,
        activity_started_ns=activity_started_ns, activity_completed_ns=activity_completed_ns,
        prepared_ns=time.monotonic_ns())
    geometry = verify_short_target(proof, identity=identity, nonce=nonce,
                                   android_user=android_user, before=before)
    diagnostic.update(status='prepared', targetProof=proof)
    if time.monotonic() >= preparation_deadline:
        raise TimeoutError('Original short-swipe preparation budget expired before input')
    remaining = action_deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError('Original short-swipe action budget expired before input')
    command = prefix + ['shell', 'input', 'swipe', *map(str, geometry['from'] + geometry['to']), '320']
    diagnostic.update(status='input-command-started', inputInvocations=1, command=command,
        inputStartedMonotonicNanos=time.monotonic_ns(), inputTimeoutSeconds=min(90, remaining))
    try:
        output = subprocess.check_output(command, timeout=min(90, remaining))
    except Exception as error:
        diagnostic.update(status='input-command-failed', errorType=type(error).__name__,
            deliveryStatus='not-established', inputCompletedMonotonicNanos=time.monotonic_ns())
        raise
    diagnostic.update(status='input-command-returned', returnCode=0,
        stdoutBytes=len(output), stdoutSha256=hashlib.sha256(output).hexdigest(),
        inputCompletedMonotonicNanos=time.monotonic_ns())
    if time.monotonic() >= action_deadline:
        raise TimeoutError('Original short-swipe action budget expired during input')
    return geometry, proof


def run_v2(adb, adb_bytes, source, trace, out, focus):
    tree = subprocess.check_output(['git', 'rev-parse', 'HEAD^{tree}'], cwd=ROOT, text=True).strip()
    gradle = (ROOT/'app/build.gradle').read_text()
    identity = expected_build(out/'ui-current.apk', source, tree,
                              re.search(r"versionName '([^']+)'", gradle).group(1),
                              int(re.search(r'versionCode (\d+)', gradle).group(1)))
    verify_installed(json.loads(adb('exec-out', 'content', 'read', '--uri', 'content://'+PACKAGE+'.evidence/build-identity')), identity)
    prepare_parser(root=ROOT, source=source, identity=identity)
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
        observations, inputs, native_ui, ui_attempts, raw_files, short_attempts = {}, [], {}, [], [], []
        first_readiness = None; header_readiness = None; resume_readiness = None
        capture = UiVisualCapture(adb=prefix[0], serial=prefix[2], source=source,
                                  diagnostics=out/('chrome-v2-ui-capture-'+nonce+'.json'))
        action = 'local.pocketchat.test.CHROME_COLLAPSE'

        def raw_file(name, raw):
            path = out/name
            with path.open('xb') as stream: stream.write(raw)
            value = dict(name=name, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
            raw_files.append(value)
            return value

        def partial(completed, failure):
            # These are original observed bytes and validated event payloads,
            # never a replacement passing case or a replay of device input.
            capture_file = None; capture_error = None
            try:
                raw = capture.diagnostics.read_bytes()
                capture_file = dict(name=capture.diagnostics.name, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
                capture_status = 'available'
            except FileNotFoundError as error:
                capture_status = 'not-started' if capture.count == 0 else 'missing'
                capture_error = repr(error)
            value = dict(schema=1, navigationContract=2, diagnosticOnly=True, releaseAcceptance=False,
                caseCompleted=completed, sourceCommit=source, sourceTree=tree, buildIdentity=identity,
                runNonce=nonce, viewport=width, fontScale=scale, androidUser=user,
                captureRunNonce=capture.nonce, captureFile=capture_file,
                captureStatus=capture_status, captureAttemptCount=capture.count,
                observations=observations, actualAndroidInputs=inputs, nativeUi=native_ui,
                firstTapReadiness=first_readiness, headerReadiness=header_readiness,
                resumeReadiness=resume_readiness,
                uiAttempts=ui_attempts, rawFiles=raw_files, shortAttempts=short_attempts,
                eventTransfer=dict(runNonce=nonce, fixtureAction='chromeCollapse', processSlot=0, events=transfer.records))
            if capture_error is not None: value['captureError'] = capture_error
            if failure is not None: value['error'] = repr(failure)
            with (out/('chrome-v2-'+nonce+'-partial.json')).open('x', encoding='utf-8') as stream:
                stream.write(json.dumps(value, ensure_ascii=False, indent=2)+'\n')

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

        def ui(phase, *, deadline=None, address_sample=None):
            # Poll only observations; an input is never retried to make it pass.
            if deadline is None: deadline = time.monotonic()+20
            wanted = ENVIRONMENT_ACTIVITY if phase in ('environment', 'drawer') else ACTIVITY
            while time.monotonic() < deadline:
                xml = capture.read(deadline=deadline)
                raw = xml.encode('utf-8')
                attempt = dict(phase=phase, index=len(ui_attempts)+1, existingSceneDeadline=deadline,
                    xml=raw_file('chrome-v2-'+nonce+'-'+phase+'-attempt-'+str(len(ui_attempts)+1)+'.xml', raw))
                ui_attempts.append(attempt)
                remaining = deadline-time.monotonic()
                if remaining <= 0: raise TimeoutError(('Native v2 observation deadline', phase))
                state = subprocess.check_output(prefix+['shell', 'dumpsys', 'activity', 'activities'], timeout=min(90, remaining)).decode('utf-8', 'strict')
                activity = state.encode('utf-8')
                attempt['activity'] = raw_file('chrome-v2-'+nonce+'-'+phase+'-attempt-'+str(attempt['index'])+'.activity.txt', activity)
                try:
                    assert resumed(state) == {(user, wanted)}
                    parsed = inspect_ui(xml, phase, observations['ready']['environmentName'], browser=True)
                    if address_sample is not None: address_cancel(address_sample, parsed)
                except AssertionError as error:
                    attempt.update(status='not-ready', error=repr(error))
                    if time.monotonic() >= deadline: raise
                    time.sleep(min(.2, max(0, deadline-time.monotonic())))
                    continue
                attempt['status'] = 'observed'
                native_ui[phase] = dict(phase=phase, sourceCommit=source, runNonce=nonce,
                    rawXml=xml, xmlBytes=len(raw), xmlSha256=hashlib.sha256(raw).hexdigest(),
                    activityState=state, activityBytes=len(activity), activitySha256=hashlib.sha256(activity).hexdigest())
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
                                                before=observations[before], nonce=nonce, out=out, target='address')
                record('tap', opened, before, point=first_readiness['point'])
            else: tap(before, opened, 'compactTap')
            cancel_address_once(observe=ui, snapshot=snapshot, tap=tap, opened=opened, returned=returned)
            ui(returned)
            return snapshot(returned)

        def swipe(before, label, direction):
            send('clear'); s = observations[before]
            x = s['webX']+s['webWidth']//2; top = s['webY']+s['webHeight']//4; bottom = s['webY']+s['webHeight']*2//3
            start, end = ([x, bottom], [x, top]) if direction == 'up' else ([x, top], [x, bottom])
            if direction == 'horizontal': start, end = [s['webX']+s['webWidth']//4, (top+bottom)//2], [s['webX']+s['webWidth']*3//4, (top+bottom)//2]
            extra = {}
            if direction == 'short':
                attempt = {}; short_attempts.append(attempt)
                geometry, proof = short_swipe_once(capture=capture, prefix=prefix, identity=identity,
                    nonce=nonce, android_user=user, before=s, diagnostic=attempt)
                start, end = geometry['from'], geometry['to']
                extra['shortTargetProof'] = proof
            else:
                adb('shell', 'input', 'swipe', *map(str, start+end), '320')
            record('swipe', label, before, **{'from': start, 'to': end, 'durationMs': 320}, **extra)
            return snapshot(label)

        def back(before, label):
            adb('shell', 'input', 'keyevent', 'KEYCODE_BACK'); record('back', label, before, key='KEYCODE_BACK')
            ui(label)
            return snapshot(label)

        completed = False; failure = None
        try:
            adb('shell', 'am', 'start', '-W', '-n', ACTIVITY, '--es', 'compactAction', 'collapseStart',
                '--es', 'eventNonce', nonce, '--ei', 'chromeNavigationVersion', '2')
            event('ready')
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
            resume_deadline = time.monotonic()+20
            resume_after_home(ACTIVITY)
            from chrome_resume_readiness import wait_resume_focus
            resume_readiness = wait_resume_focus(argv=sys.argv[1:], source=source, identity=identity,
                before=observations['upBeforeResume'], nonce=nonce, first_readiness=first_readiness,
                deadline=resume_deadline, out=out)
            if time.monotonic() >= resume_deadline:
                raise TimeoutError('Original HOME roundtrip budget expired after focus observation')
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
            case = dict(navigationContract=2, browserChrome=True, viewport=width, fontScale=scale, androidUser=user,
                        runNonce=nonce, sourceCommit=source, actualAndroidExecution=True,
                        actualGeckoExecution=True, actualAndroidTouchExecution=True,
                        checks=[{'name': name, 'pass': True} for name in BROWSER_NAMES],
                        legacyBehaviorMap=[list(row) for row in LEGACY_BEHAVIOR_MAP[2:]],
                        browserStartupMap=[list(row) for row in BROWSER_STARTUP_MAP],
                        observations=observations, actualAndroidInputs=inputs, nativeUi=native_ui,
                        firstTapReadiness=first_readiness, headerReadiness=header_readiness,
                        resumeReadiness=resume_readiness,
                        eventTransfer=dict(runNonce=nonce, fixtureAction='chromeCollapse', processSlot=0, events=transfer.records),
                        fixtureRequests=requests)
            verify_case(case, identity)
            cases.append(case)
            completed = True
        except Exception as error:
            failure = error
            raise
        finally:
            try: partial(completed, failure)
            except Exception as error:
                if failure is None: raise
                print('V2 diagnostic collection failed: '+repr(error), file=sys.stderr)
    return dict(navigationContract=2, browserChrome=True, status='passed', actualAndroidExecution=True,
                actualGeckoExecution=True, actualAndroidTouchExecution=True, sourceCommit=source,
                buildIdentity=identity, cases=cases,
                scope='Actual production chrome and protected local Gecko document with synthetic login/draft/task; no real ChatGPT acceptance or phone performance claim.')
