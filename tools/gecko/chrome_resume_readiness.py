"""Observe resumed native focus inside the caller's original HOME budget.

This helper emits no Android input and no authoritative collapse snapshot. The
caller keeps its one HOME/return sequence and its one activityResume snapshot;
this diagnostic observes the existing read-only native readiness provider first.
"""
import json
import math
from pathlib import Path
import re
import time

import chrome_header_readiness as gate
from chrome_first_tap_readiness import SNAPSHOT_FIELDS, TAG, TARGET, _focus, _rect

ROOT = Path(__file__).resolve().parents[2]
ADAPTER = 'tools/gecko/chrome_resume_readiness.py'
DEPENDENCIES = (ADAPTER, 'tools/gecko/chrome_first_tap_readiness.py',
                'tests/gecko/ChromeCollapseIntegration.java')


def _sources(root, source, identity, deadline):
    binding = gate._source_bindings(root, source, identity, deadline)
    additional = {}
    for name in DEPENDENCIES:
        path = root/name
        gate.need(path.is_file() and not path.is_symlink() and path.stat().st_size <= gate.MAX_OUTPUT,
                  'source-unverified')
        actual = path.read_bytes()
        original = gate._checked(['git', 'show', source+':'+name], deadline, cwd=root)
        gate.need(actual == original, 'source-unverified')
        additional[name] = gate.digest(actual)
    return binding, additional


def _original(first, *, source, identity, nonce, before, binding, additional, compiled):
    gate.need(isinstance(first, dict) and first.get('status') == 'passed' and first.get('reason') == 'clear'
              and first.get('scope') == 'chrome-initial-compact-tap-only' and first.get('tapInvocations') == 1
              and first.get('diagnosticOnly') is True and first.get('releaseAcceptance') is False
              and first.get('sourceCommit') == source and first.get('sourceTree') == identity['sourceTree']
              and first.get('runNonce') == nonce, 'identity-changed')
    expected_sources = dict(binding['sourceSha256'], **{k: v for k, v in additional.items() if k != ADAPTER})
    gate.need(first.get('sourceSha256') == expected_sources
              and first.get('parserClassesSha256') == compiled['parserClassesSha256'], 'source-unverified')
    owner = first.get('processIdentity')
    gate.need(isinstance(owner, dict) and set(owner) == {'pid', 'uid', 'startTicks', 'systemUiUid'}
              and isinstance(owner['pid'], str) and re.fullmatch('[1-9][0-9]*', owner['pid']) is not None
              and isinstance(owner['startTicks'], str) and re.fullmatch('[1-9][0-9]*', owner['startTicks']) is not None
              and type(owner['uid']) is int and 10000 <= owner['uid'] < 100000
              and type(owner['systemUiUid']) is int and 10000 <= owner['systemUiUid'] < 100000
              and owner['uid'] != owner['systemUiUid'], 'identity-changed')
    samples = first.get('nativeSnapshots')
    gate.need(isinstance(samples, list) and 2 <= len(samples) <= 4, 'invalid-observation')
    initial = samples[-1]
    gate.need(isinstance(initial, dict) and set(initial) == SNAPSHOT_FIELDS
              and initial.get('sourceCommit') == source and initial.get('sourceTree') == identity['sourceTree']
              and initial.get('apkSha256') == identity['apkSha256'] and initial.get('runNonce') == nonce
              and type(initial.get('sequence')) is int and 1 < initial['sequence'] < 128
              and type(initial.get('observedAtElapsedRealtime')) is int and initial['observedAtElapsedRealtime'] > 0
              and type(initial.get('activityRef')) is int and initial['activityRef'] > 0
              and initial.get('windowFocus') is True and initial.get('decorFocus') is True,
              'identity-changed')
    windows = first.get('windowObservations')
    gate.need(isinstance(windows, list) and windows and windows[-1].get('parserState') == 'CLEAR', 'invalid-observation')
    focused = windows[-1].get('currentFocus')
    match = re.fullmatch(r'Window\{([0-9a-f]+) u0 '+re.escape(gate.COMPONENT)+r'\}', focused or '')
    gate.need(match is not None, 'identity-changed')
    gate.need(isinstance(before, dict) and before.get('command') == 'upBeforeResume'
              and before.get('expanded') is False and before.get('keyboard') is False
              and before.get('toolbarVisibility') == before.get('compactVisibility') == before.get('page') == 0
              and isinstance(before.get('nativeTouches'), list) and 3 <= len(before['nativeTouches']) <= 256,
              'invalid-request')
    return dict(owner), initial, focused, match[1]


def _validate_snapshot(value, *, source, identity, nonce, request, owner, initial, before):
    gate.need(isinstance(value, dict) and set(value) == SNAPSHOT_FIELDS
              and type(value.get('schema')) is int and value['schema'] == 1
              and value.get('kind') == 'nativeInputReadiness' and value.get('diagnosticOnly') is True
              and value.get('releaseAcceptance') is False, 'invalid-observation')
    gate.need(value.get('runNonce') == nonce and value.get('request') == request
              and value.get('sourceCommit') == source and value.get('sourceTree') == identity['sourceTree']
              and value.get('apkSha256') == identity['apkSha256'] and value.get('fixtureAction') == 'chromeCollapse',
              'identity-changed')
    gate.need(type(value.get('pid')) is int and str(value['pid']) == owner['pid']
              and type(value.get('uid')) is int and value['uid'] == owner['uid'], 'identity-changed')
    for key in ('sequence', 'observedAtElapsedRealtime', 'activityRef', 'surface', 'sdkSession', 'attachedSession'):
        gate.need(type(value.get(key)) is int and value[key] > 0, 'invalid-observation')
    gate.need(value['sequence'] <= 128 and value['activityRef'] == initial['activityRef'], 'identity-changed')
    gate.need(all(type(before.get(key)) is int and before[key] > 0
                  and value[key] == before[key] == initial[key]
                  for key in ('surface', 'sdkSession', 'attachedSession'))
              and value['sdkSession'] == value['attachedSession'], 'identity-changed')
    document = before['documentReadyEvidence']['rawMessage']['appearanceDocument']
    pending = before['pending']['id']
    gate.need(isinstance(document, str) and re.fullmatch('[a-zA-Z0-9-]{16,80}', document) is not None
              and isinstance(pending, str) and re.fullmatch('[a-zA-Z0-9_-]{1,80}', pending) is not None
              and value.get('appearanceDocument') == document == initial['appearanceDocument']
              and value.get('documentBinding') == 'fixture-admitted-current-port'
              and type(value.get('documentPort')) is int and value['documentPort'] > 0
              and type(value.get('currentPort')) is int
              and value['documentPort'] == value['currentPort'] == initial['documentPort'] == initial['currentPort']
              and value.get('url') == TARGET and value.get('pendingId') == pending
              and value.get('pendingConfirmed') is True, 'identity-changed')
    for key in ('windowFocus', 'decorFocus', 'attached', 'shown', 'enabled', 'clickable', 'laidOut',
                'layoutRequested', 'globallyVisible', 'visibleDocument', 'expanded'):
        gate.need(type(value.get(key)) is bool, 'invalid-observation')
    for key in ('toolbarVisibility', 'compactVisibility', 'page', 'activityStarts', 'menuOpens', 'nativeTouchCount'):
        gate.need(type(value.get(key)) is int, 'invalid-observation')
    gate.need(value['expanded'] is False and value['toolbarVisibility'] == value['compactVisibility'] == value['page'] == 0
              and value['activityStarts'] == before['activityStarts'] and value['menuOpens'] == before['menuOpens']
              and value['nativeTouchCount'] == len(before['nativeTouches']) and value['visibleDocument'] is True,
              'identity-changed')
    geometry = {key: _rect(value.get(key)) for key in ('hostBounds', 'toolbarBounds', 'compactBounds', 'visibleBounds', 'webBounds')}
    point = value.get('point')
    gate.need(isinstance(point, list) and len(point) == 2 and all(type(n) is int and n >= 0 for n in point), 'invalid-observation')
    gate.need(point == before['compactTap'] and geometry['webBounds'] == [before['webX'], before['webY'],
              before['webX']+before['webWidth'], before['webY']+before['webHeight']], 'identity-changed')
    geometry['point'] = point
    left, top, right, bottom = geometry['compactBounds']; vl, vt, vr, vb = geometry['visibleBounds']
    ready = all(value[key] for key in ('windowFocus', 'decorFocus', 'attached', 'shown', 'enabled', 'clickable',
                                      'laidOut', 'globallyVisible')) and not value['layoutRequested']
    ready = ready and all(rect[0] < rect[2] and rect[1] < rect[3] for key, rect in geometry.items() if key != 'point')
    ready = ready and left <= vl < vr <= right and top <= vt < vb <= bottom
    ready = ready and point == [(left+right)//2, (top+bottom)//2]
    ready = ready and all(rect[0] <= point[0] < rect[2] and rect[1] <= point[1] < rect[3]
                          for key, rect in geometry.items() if key not in ('point', 'webBounds'))
    return geometry if ready else None


def _save_record(path, record):
    try:
        temporary = path.with_suffix('.partial')
        with temporary.open('x') as target: json.dump(record, target, sort_keys=True)
        temporary.replace(path)
    except OSError:
        raise gate.HeaderReadinessFailure('receipt-unavailable') from None


def wait_resume_focus(*, argv, source, identity, before, nonce, first_readiness, deadline, out,
                      root=ROOT, clock=time.monotonic, sleep=time.sleep):
    """No action retries and no new budget: deadline precedes the HOME command."""
    started = clock(); path = None; owned = False
    record = dict(schema=1, status='failed', reason='invalid-request', scope='chrome-home-resume-focus-only',
        sourceCommit=source, runNonce=nonce, diagnosticOnly=True, releaseAcceptance=False, applicationAcceptance=False,
        inputInvocations=0, authoritativeSnapshotInvocations=0, originalRoundtripBudgetMs=20000,
        deadlineMonotonic=deadline, observerStartedMonotonic=started, nativeSnapshots=[], windowObservations=[])
    try:
        gate.need(type(deadline) in (int, float) and math.isfinite(deadline) and 0 < deadline-started <= 20,
                  'deadline')
        record['originalRoundtripStartedMonotonic'] = deadline-20
        parser = gate.Parser(add_help=False, allow_abbrev=False)
        parser.add_argument('--adb', required=True); parser.add_argument('--serial', required=True)
        parser.add_argument('--out', type=Path)
        args, _ = parser.parse_known_args(argv)
        gate.need(isinstance(source, str) and re.fullmatch('[0-9a-f]{40}', source) is not None
                  and args.adb and args.serial == 'emulator-5554' and isinstance(nonce, str)
                  and re.fullmatch('[0-9a-f]{32}', nonce) is not None, 'invalid-request')
        root = Path(root).resolve(); out = Path(out); prefix = [args.adb, '-s', args.serial]
        gate.need(out.is_dir() and not out.is_symlink(), 'invalid-request')
        report_out = args.out if args.out is not None else out
        if not report_out.is_absolute(): report_out = root/report_out
        gate.need(report_out.is_dir() and not report_out.is_symlink(), 'invalid-request')
        path = report_out/('chrome-resume-readiness-'+nonce+'.json')
        gate.need(not path.exists() and not path.is_symlink(), 'already-invoked')
        with path.open('x') as target: json.dump(record, target, sort_keys=True)
        owned = True
        binding, additional = _sources(root, source, identity, deadline)
        parser_command, compiled = gate._compile_parser(root, binding, deadline)
        owner, initial, initial_focus, token = _original(first_readiness, source=source, identity=identity, nonce=nonce,
            before=before, binding=binding, additional=additional, compiled=compiled)
        record.update(sourceTree=identity['sourceTree'], sourceSha256=dict(binding['sourceSha256'], **additional),
            parserClassesSha256=compiled['parserClassesSha256'], processIdentity=owner,
            originalActivityRef=initial['activityRef'], originalNativeTouchCount=len(before['nativeTouches']))
        for parts, expected in [(['shell', 'getprop', 'ro.kernel.qemu'], b'1'),
                                (['shell', 'getprop', 'ro.build.version.sdk'], b'35'),
                                (['shell', 'am', 'get-current-user'], b'0')]:
            gate.need(gate._checked(prefix+parts, deadline, stdout_limit=128).strip() == expected, 'identity-changed')
        gate.need(gate._checked(prefix+['shell', 'getprop', 'ro.hardware'], deadline, stdout_limit=128).strip()
                  in (b'ranchu', b'goldfish'), 'identity-changed')
        sequence = initial['sequence']; observed_at = initial['observedAtElapsedRealtime']; previous = None; queries = 0
        for _ in range(101):
            gate.need(clock() < deadline, 'deadline')
            gate.need(gate._identity(prefix, identity, deadline) == owner, 'identity-changed')
            raw = gate._checked(prefix+['shell', 'dumpsys', 'window'], deadline)
            focused = _focus(raw)
            observation = dict(currentFocus=focused, bytes=len(raw), sha256=gate.digest(raw))
            record['windowObservations'] = (record['windowObservations']+[observation])[-8:]
            if focused != initial_focus:
                previous = None; sleep(min(.2, max(0, deadline-clock()))); continue
            gate.need(gate._class_hashes(compiled['cache']/'classes') == compiled['classes'], 'cache-unverified')
            state = gate._checked(parser_command+[str(owner['uid']), str(owner['systemUiUid']), gate.COMPONENT, token],
                                  deadline, input_bytes=raw, stdout_limit=64, stderr_limit=64)
            gate.need(state in (b'CLEAR\n', b'SHADE_VISIBLE\n'), 'invalid-observation')
            observation['parserState'] = state.decode('ascii').strip()
            if state != b'CLEAR\n':
                previous = None; sleep(min(.2, max(0, deadline-clock()))); continue
            queries += 1; request = nonce+'-'+str(800+queries)
            gate._checked(prefix+['shell', 'am', 'broadcast', '-a', 'local.pocketchat.test.CHROME_COLLAPSE', '-p', gate.PACKAGE,
                          '--es', 'eventNonce', nonce, '--es', 'collapseReadiness', request], deadline)
            value = None
            while clock() < deadline:
                log = gate._checked(prefix+['logcat', '-d', '-v', 'threadtime', '-s', TAG+':I', 'AndroidRuntime:E', '*:S'], deadline)
                gate.need(b'FATAL EXCEPTION' not in log, 'observation-failed')
                matches = []
                for line in log.splitlines():
                    marker = (TAG+': ').encode()
                    if marker not in line: continue
                    header, payload = line.split(marker, 1)
                    gate.need(len(payload) <= 3500, 'output-too-large')
                    packet = gate.decode(payload)
                    if packet.get('runNonce') == nonce and packet.get('request') == request:
                        transport = re.fullmatch(rb'[0-9]{2}-[0-9]{2} [0-9:.]+\s+([0-9]+)\s+([0-9]+) I ', header)
                        gate.need(transport is not None and transport[1].decode('ascii') == owner['pid']
                                  and transport[2].decode('ascii') == owner['pid'], 'identity-changed')
                        matches.append(packet)
                gate.need(len(matches) <= 1, 'invalid-observation')
                if matches: value = matches[0]; break
                sleep(min(.1, max(0, deadline-clock())))
            gate.need(value is not None, 'deadline')
            geometry = _validate_snapshot(value, source=source, identity=identity, nonce=nonce, request=request,
                                           owner=owner, initial=initial, before=before)
            gate.need(value['sequence'] > sequence and value['observedAtElapsedRealtime'] > observed_at, 'invalid-observation')
            sequence = value['sequence']; observed_at = value['observedAtElapsedRealtime']
            record['nativeSnapshots'] = (record['nativeSnapshots']+[value])[-4:]
            if geometry is None:
                previous = None; sleep(min(.2, max(0, deadline-clock()))); continue
            if geometry != previous:
                previous = geometry; continue
            gate.need(gate._identity(prefix, identity, deadline) == owner, 'identity-changed')
            last = gate._checked(prefix+['shell', 'dumpsys', 'window'], deadline)
            final = dict(currentFocus=_focus(last), bytes=len(last), sha256=gate.digest(last))
            record['windowObservations'] = (record['windowObservations']+[final])[-8:]
            if final['currentFocus'] != initial_focus:
                previous = None; continue
            gate.need(gate._class_hashes(compiled['cache']/'classes') == compiled['classes'], 'cache-unverified')
            state = gate._checked(parser_command+[str(owner['uid']), str(owner['systemUiUid']), gate.COMPONENT, token],
                                  deadline, input_bytes=last, stdout_limit=64, stderr_limit=64)
            gate.need(state in (b'CLEAR\n', b'SHADE_VISIBLE\n'), 'invalid-observation')
            final['parserState'] = state.decode('ascii').strip()
            if state != b'CLEAR\n': previous = None; continue
            gate.need(_sources(root, source, identity, deadline) == (binding, additional)
                      and gate._identity(prefix, identity, deadline) == owner, 'identity-changed')
            gate.need(clock() < deadline, 'deadline')
            record.update(status='passed', reason='clear', preparationQueries=queries)
            return record
        raise gate.HeaderReadinessFailure('deadline')
    except gate.HeaderReadinessFailure as error:
        record['reason'] = error.reason; raise
    except (OSError, ValueError, KeyError, TypeError, IndexError):
        record['reason'] = 'observation-failed'; raise gate.HeaderReadinessFailure('observation-failed') from None
    finally:
        finished = clock(); record['observerFinishedMonotonic'] = finished
        record['observerElapsedMs'] = max(0, round((finished-started)*1000))
        if type(deadline) in (int, float) and math.isfinite(deadline):
            record['originalRoundtripElapsedMs'] = max(0, round((finished-(deadline-20))*1000))
        if owned and path is not None and path.is_file(): _save_record(path, record)
        if record['status'] == 'passed' and clock() >= deadline:
            # A late receipt is still a failed original roundtrip. Preserve its
            # actual observations rather than leaving a misleading passed file.
            finished = clock()
            record.update(status='failed', reason='deadline', observerFinishedMonotonic=finished,
                observerElapsedMs=max(0, round((finished-started)*1000)),
                originalRoundtripElapsedMs=max(0, round((finished-(deadline-20))*1000)))
            if owned and path is not None and path.is_file(): _save_record(path, record)
            raise gate.HeaderReadinessFailure('deadline')
