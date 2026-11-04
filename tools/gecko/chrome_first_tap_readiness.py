"""One original compact-name tap after read-only, source-bound receiver checks.

The first tap's existing 90-second command budget includes at most 20 seconds of
preparation. No focus, window, package or page mutation is used for preparation.
The original 30-second result observation and complete collapse oracle are owned
by run_chrome_collapse.py and remain separate from these diagnostic snapshots.
"""
import json
from pathlib import Path
import re
import time

import chrome_header_readiness as gate

ROOT = Path(__file__).resolve().parents[2]
ADAPTER = 'tools/gecko/chrome_first_tap_readiness.py'
FIXTURE = 'tests/gecko/ChromeCollapseIntegration.java'
TAG = 'PocketChromeInputReady'
TARGET = 'https://chatgpt.com/c/reload-collapse'
SNAPSHOT_FIELDS = set(('schema kind diagnosticOnly releaseAcceptance sourceCommit sourceTree apkSha256 runNonce request fixtureAction sequence '
    'observedAtElapsedRealtime pid uid activityRef surface sdkSession attachedSession appearanceDocument documentBinding documentPort currentPort url visibleDocument pendingId pendingConfirmed '
    'windowFocus decorFocus attached shown enabled clickable laidOut layoutRequested globallyVisible expanded toolbarVisibility compactVisibility page '
    'activityStarts menuOpens nativeTouchCount hostBounds toolbarBounds compactBounds visibleBounds webBounds point').split())


def need(value, reason):
    gate.need(value, reason)


def _sources(root, source, identity, deadline):
    binding = gate._source_bindings(root, source, identity, deadline)
    additional = {}
    for name in (ADAPTER, FIXTURE):
        path = root/name
        need(path.is_file() and not path.is_symlink() and path.stat().st_size <= gate.MAX_OUTPUT, 'source-unverified')
        actual = path.read_bytes()
        original = gate._checked(['git', 'show', source+':'+name], deadline, cwd=root)
        need(actual == original, 'source-unverified')
        additional[name] = gate.digest(actual)
    return binding, additional


def _focus(raw):
    """Record the actual bounded owner even when it is not the tested window."""
    fields = re.findall(r'^\s*mCurrentFocus=([^\r\n]*)$', raw.decode('utf-8'), re.MULTILINE)
    need(len(fields) == 1 and len(fields[0]) <= 512, 'invalid-observation')
    value = fields[0].strip()
    need(value == 'null' or re.fullmatch(r'Window\{[0-9a-f]+ u[0-9]+ [A-Za-z0-9_.$/: -]{1,300}\}', value) is not None,
         'invalid-observation')
    return value


def _rect(value):
    need(isinstance(value, list) and len(value) == 4 and all(type(x) is int for x in value), 'invalid-observation')
    return value


def _validate_snapshot(value, *, source, identity, nonce, request, owner, before):
    need(isinstance(value, dict) and value.get('schema') == 1 and type(value.get('schema')) is int
         and value.get('diagnosticOnly') is True and value.get('releaseAcceptance') is False
         and value.get('kind') == 'nativeInputReadiness' and set(value) == SNAPSHOT_FIELDS, 'invalid-observation')
    need(value.get('runNonce') == nonce and value.get('request') == request
         and value.get('sourceCommit') == source and value.get('sourceTree') == identity['sourceTree']
         and value.get('apkSha256') == identity['apkSha256'] and value.get('fixtureAction') == 'chromeCollapse', 'identity-changed')
    need(type(value.get('pid')) is int and str(value['pid']) == owner['pid']
         and type(value.get('uid')) is int and value['uid'] == owner['uid'], 'identity-changed')
    for key in ('sequence', 'observedAtElapsedRealtime', 'activityRef', 'surface', 'sdkSession', 'attachedSession'):
        need(type(value.get(key)) is int and value[key] > 0, 'invalid-observation')
    need(value['sequence'] <= 128, 'invalid-observation')
    need(all(type(before.get(key)) is int and before[key] > 0 and value.get(key) == before[key] for key in ('surface', 'sdkSession', 'attachedSession'))
         and value['sdkSession'] == value['attachedSession'], 'identity-changed')
    document = before['documentReadyEvidence']['rawMessage']['appearanceDocument']
    pending = before['pending']['id']
    need(value.get('documentBinding') == 'fixture-admitted-current-port'
         and type(value.get('documentPort')) is int and value['documentPort'] > 0
         and type(value.get('currentPort')) is int and value['documentPort'] == value['currentPort'], 'identity-changed')
    need(isinstance(pending, str) and re.fullmatch('[a-zA-Z0-9_-]{1,80}', pending) is not None
         and isinstance(document, str) and re.fullmatch('[a-zA-Z0-9-]{16,80}', document) is not None
         and value.get('appearanceDocument') == document and value.get('url') == TARGET
         and value.get('pendingId') == pending and value.get('pendingConfirmed') is True, 'identity-changed')
    for key in ('windowFocus', 'decorFocus', 'attached', 'shown', 'enabled', 'clickable', 'laidOut', 'layoutRequested', 'globallyVisible', 'visibleDocument', 'expanded'):
        need(type(value.get(key)) is bool, 'invalid-observation')
    for key in ('toolbarVisibility', 'compactVisibility', 'page', 'activityStarts', 'menuOpens', 'nativeTouchCount'):
        need(type(value.get(key)) is int, 'invalid-observation')
    need(value['expanded'] is False and value['toolbarVisibility'] == value['compactVisibility'] == value['page'] == 0
         and value['activityStarts'] == before['activityStarts'] and value['menuOpens'] == before['menuOpens']
         and value['nativeTouchCount'] == 0 and value['visibleDocument'] is True, 'identity-changed')
    geometry = {key: _rect(value.get(key)) for key in ('hostBounds', 'toolbarBounds', 'compactBounds', 'visibleBounds', 'webBounds')}
    point = value.get('point')
    need(isinstance(point, list) and len(point) == 2 and all(type(x) is int and x >= 0 for x in point), 'invalid-observation')
    original = before.get('compactTap')
    need(isinstance(original, list) and len(original) == 2 and all(type(x) is int and x >= 0 for x in original), 'invalid-request')
    geometry['point'] = point
    ready = all(value[key] for key in ('windowFocus', 'decorFocus', 'attached', 'shown', 'enabled', 'clickable', 'laidOut', 'globallyVisible')) and not value['layoutRequested']
    ready = ready and all(rect[0] < rect[2] and rect[1] < rect[3] for key, rect in geometry.items() if key != 'point')
    left, top, right, bottom = geometry['compactBounds']
    vl, vt, vr, vb = geometry['visibleBounds']
    ready = ready and left <= vl < vr <= right and top <= vt < vb <= bottom
    ready = ready and point == [(left+right)//2, (top+bottom)//2] and point == original
    ready = ready and all(rect[0] <= point[0] < rect[2] and rect[1] <= point[1] < rect[3]
                          for key, rect in geometry.items() if key not in ('point', 'webBounds'))
    return geometry if ready else None


def first_tap_once(*, argv, source, identity, before, nonce, out, root=ROOT, clock=time.monotonic, sleep=time.sleep):
    started = clock(); action_deadline = started+90; preparation_deadline = started+20
    safe_source = source if isinstance(source, str) and re.fullmatch('[0-9a-f]{40}', source) else None
    safe_nonce = nonce if isinstance(nonce, str) and re.fullmatch('[0-9a-f]{32}', nonce) else None
    record = dict(schema=1, status='failed', reason='invalid-request', scope='chrome-initial-compact-tap-only',
        sourceCommit=safe_source, runNonce=safe_nonce, diagnosticOnly=True, releaseAcceptance=False, applicationAcceptance=False,
        preEmitOnly=True, preparationBudgetMs=20000, originalActionBudgetMs=90000, tapInvocations=0,
        nativeSnapshots=[], windowObservations=[], elapsedMs=0)
    path = None; owned = False
    try:
        parser = gate.Parser(add_help=False, allow_abbrev=False)
        parser.add_argument('--adb', required=True); parser.add_argument('--serial', required=True)
        parser.add_argument('--out', type=Path)
        args, _ = parser.parse_known_args(argv)
        need(isinstance(source, str) and re.fullmatch('[0-9a-f]{40}', source) is not None
             and args.adb and args.serial == 'emulator-5554' and isinstance(nonce, str)
             and re.fullmatch('[0-9a-f]{32}', nonce) is not None, 'invalid-request')
        prefix = [args.adb, '-s', args.serial]; root = Path(root).resolve(); out = Path(out)
        need(out.is_dir() and not out.is_symlink(), 'invalid-request')
        # The focused diagnostic already declares its archived output directory;
        # keep this proof there instead of leaving it beside the immutable APK.
        report_out = args.out if args.out is not None else out
        if not report_out.is_absolute():report_out = root/report_out
        need(report_out.is_dir() and not report_out.is_symlink(), 'invalid-request')
        path = report_out/('chrome-first-tap-readiness-'+nonce+'.json')
        need(not path.exists() and not path.is_symlink(), 'already-invoked')
        with path.open('x') as target:json.dump(record, target, sort_keys=True)
        owned = True
        binding, additional = _sources(root, source, identity, preparation_deadline)
        parser_command, compiled = gate._compile_parser(root, binding, preparation_deadline)
        record.update(sourceTree=binding['sourceTree'], sourceSha256=dict(binding['sourceSha256'], **additional),
                      parserClassesSha256=compiled['parserClassesSha256'])
        for parts, expected in [(['shell', 'getprop', 'ro.kernel.qemu'], b'1'),
                                (['shell', 'getprop', 'ro.build.version.sdk'], b'35'),
                                (['shell', 'am', 'get-current-user'], b'0')]:
            need(gate._checked(prefix+parts, preparation_deadline, stdout_limit=128).strip() == expected, 'identity-changed')
        need(gate._checked(prefix+['shell', 'getprop', 'ro.hardware'], preparation_deadline, stdout_limit=128).strip()
             in (b'ranchu', b'goldfish'), 'identity-changed')
        owner = gate._identity(prefix, identity, preparation_deadline); record['processIdentity'] = owner
        token = None; previous = None; previous_ref = None; activity_ref = None; sequence = 0; queries = 0
        for _ in range(101):
            need(clock() < preparation_deadline, 'deadline')
            need(gate._identity(prefix, identity, preparation_deadline) == owner, 'identity-changed')
            raw = gate._checked(prefix+['shell', 'dumpsys', 'window'], preparation_deadline)
            focused = _focus(raw)
            observation = dict(currentFocus=focused, bytes=len(raw), sha256=gate.digest(raw))
            record['windowObservations'] = (record['windowObservations']+[observation])[-8:]
            expected = re.fullmatch(r'Window\{([0-9a-f]+) u0 '+re.escape(gate.COMPONENT)+r'\}', focused)
            if expected is None:
                previous = None; sleep(min(.2, max(0, preparation_deadline-clock()))); continue
            need(token is None or token == expected[1], 'identity-changed'); token = expected[1]
            need(gate._class_hashes(compiled['cache']/'classes') == compiled['classes'], 'cache-unverified')
            state = gate._checked(parser_command+[str(owner['uid']), str(owner['systemUiUid']), gate.COMPONENT, token],
                                  preparation_deadline, input_bytes=raw, stdout_limit=64, stderr_limit=64)
            need(state in (b'CLEAR\n', b'SHADE_VISIBLE\n'), 'invalid-observation')
            observation['parserState'] = state.decode('ascii').strip()
            if state != b'CLEAR\n':
                previous = None; sleep(min(.2, max(0, preparation_deadline-clock()))); continue
            queries += 1; request = nonce+'-'+str(queries)
            gate._checked(prefix+['shell', 'am', 'broadcast', '-a', 'local.pocketchat.test.CHROME_COLLAPSE', '-p', gate.PACKAGE,
                '--es', 'eventNonce', nonce, '--es', 'collapseReadiness', request], preparation_deadline)
            value = None
            while clock() < preparation_deadline:
                log = gate._checked(prefix+['logcat', '-d', '-v', 'threadtime', '-s', TAG+':I', 'AndroidRuntime:E', '*:S'], preparation_deadline)
                need(b'FATAL EXCEPTION' not in log, 'observation-failed')
                matches = []
                for line in log.splitlines():
                    marker = (TAG+': ').encode()
                    if marker not in line:continue
                    header, payload = line.split(marker, 1)
                    need(len(payload) <= 3500, 'output-too-large')
                    packet = gate.decode(payload)
                    if packet.get('runNonce') == nonce and packet.get('request') == request:
                        transport = re.fullmatch(rb'[0-9]{2}-[0-9]{2} [0-9:.]+\s+([0-9]+)\s+([0-9]+) I ', header)
                        need(transport is not None and transport[1].decode('ascii') == owner['pid']
                             and transport[2].decode('ascii') == owner['pid'], 'identity-changed')
                        matches.append(packet)
                need(len(matches) <= 1, 'invalid-observation')
                if matches:value = matches[0];break
                sleep(min(.1, max(0, preparation_deadline-clock())))
            need(value is not None, 'deadline')
            geometry = _validate_snapshot(value, source=source, identity=identity, nonce=nonce, request=request, owner=owner, before=before)
            need(value['sequence'] > sequence, 'invalid-observation'); sequence = value['sequence']
            need(activity_ref is None or activity_ref == value['activityRef'], 'identity-changed'); activity_ref = value['activityRef']
            record['nativeSnapshots'] = (record['nativeSnapshots']+[value])[-4:]
            stable_ref = [value[key] for key in ('activityRef', 'surface', 'sdkSession', 'attachedSession', 'appearanceDocument', 'documentPort', 'currentPort')]
            if geometry is None:
                previous = None; sleep(min(.2, max(0, preparation_deadline-clock()))); continue
            if previous != geometry or previous_ref != stable_ref:
                previous = geometry; previous_ref = stable_ref; continue
            # The parser preceding each fresh native snapshot must be CLEAR; a
            # final read fences the single emission without changing focus.
            need(gate._identity(prefix, identity, preparation_deadline) == owner, 'identity-changed')
            last = gate._checked(prefix+['shell', 'dumpsys', 'window'], preparation_deadline)
            last_focus = _focus(last)
            final = dict(currentFocus=last_focus, bytes=len(last), sha256=gate.digest(last))
            record['windowObservations'] = (record['windowObservations']+[final])[-8:]
            if last_focus != focused:
                previous = None; continue
            need(gate._class_hashes(compiled['cache']/'classes') == compiled['classes'], 'cache-unverified')
            state = gate._checked(parser_command+[str(owner['uid']), str(owner['systemUiUid']), gate.COMPONENT, token],
                                  preparation_deadline, input_bytes=last, stdout_limit=64, stderr_limit=64)
            need(state in (b'CLEAR\n', b'SHADE_VISIBLE\n'), 'invalid-observation'); final['parserState'] = state.decode('ascii').strip()
            if state != b'CLEAR\n':previous = None;continue
            need(_sources(root, source, identity, preparation_deadline) == (binding, additional)
                 and gate._identity(prefix, identity, preparation_deadline) == owner, 'identity-changed')
            need(clock() < preparation_deadline and clock() < action_deadline, 'deadline')
            point = before['compactTap']; record.update(point=point, tapInvocations=1)
            outcome = gate._bounded_run(prefix+['shell', 'input', 'tap', str(point[0]), str(point[1])], action_deadline)
            need(outcome.returncode == 0, 'action-failed');need(clock() < action_deadline, 'deadline')
            record.update(status='passed', reason='clear', preparationQueries=queries)
            return record
        raise gate.HeaderReadinessFailure('deadline')
    except gate.HeaderReadinessFailure as error:
        record['reason'] = error.reason;raise
    except (OSError, ValueError, KeyError, TypeError, IndexError):
        record['reason'] = 'observation-failed';raise gate.HeaderReadinessFailure('observation-failed') from None
    finally:
        record['elapsedMs'] = max(0, round((clock()-started)*1000))
        if owned and path is not None and path.is_file():
            try:
                temporary = path.with_suffix('.partial')
                with temporary.open('x') as target:json.dump(record, target, sort_keys=True)
                temporary.replace(path)
            except OSError:raise gate.HeaderReadinessFailure('receipt-unavailable') from None
        print('CHROME_FIRST_TAP_READINESS '+json.dumps(record, sort_keys=True, separators=(',', ':')), flush=True)
