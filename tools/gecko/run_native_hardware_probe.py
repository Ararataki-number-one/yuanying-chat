#!/usr/bin/env python3
"""Diagnostic-only actual Gecko CPU preference and untouched navigator observations."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
import uuid

from profile_invocation_contract import expected_build, verify_installed

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = 'local.pocketchat.test'
PROCESS = PACKAGE + ':native_hardware_probe'
COMPONENT = PACKAGE + '/local.pocketchat.NativeHardwareProbeActivity'
AUTHORITY = PACKAGE + '.nativehardware'
ROLES = ('page', 'dedicated', 'blob', 'shared', 'service')
PHASES = ('baseline', 'cap2', 'cap1', 'reset')
MODES = ('standard', 'rfp')
MAX_REPORT_BYTES = 262144
MAX_HARDWARE_COUNT = 65536
OBSERVATION_ERRORS = ('Unavailable', 'TimeoutError', 'WorkerError', 'InvalidReply')


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(65536), b''):
            digest.update(block)
    return digest.hexdigest()


def strict_json(raw):
    require(type(raw) is bytes and len(raw) <= MAX_REPORT_BYTES, 'Bounded native report required')
    def pairs(rows):
        value = {}
        for key, item in rows:
            require(key not in value, 'Duplicate native field')
            value[key] = item
        return value
    value = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite native value')))
    require(type(value) is dict, 'Native report object required')
    return value


def typed_equal(actual, expected):
    if type(actual) is not type(expected):
        return False
    if type(expected) is dict:
        return set(actual) == set(expected) and all(typed_equal(actual[k], v) for k, v in expected.items())
    if type(expected) is list:
        return len(actual) == len(expected) and all(typed_equal(a, b) for a, b in zip(actual, expected))
    return actual == expected


def installed_identity(actual, expected):
    require(type(actual) is dict and type(expected) is dict, 'Installed APK identity required')
    verify_installed(actual, expected)
    require(all(key in actual and typed_equal(actual[key], value) for key, value in expected.items()),
        'Installed APK identity types differ')


def native_ack(packet, *, phase, nonce, mode, readback, baseline):
    fields = {'kind', 'schema', 'status', 'operation', 'requestToken', 'requestedCap', 'configuredCap',
        'hasUserValue', 'rfpEnabled', 'nativePreferenceReadback', 'scope', 'workerCoverageVerified',
        'fingerprintProtectionVerified'}
    require(type(packet) is dict and set(packet) == fields, 'Native acknowledgement schema differs')
    require(type(packet['schema']) is int and packet['schema'] == 1 and packet['kind'] == 'hardwareProbeResult',
        'Native acknowledgement kind differs')
    cap = {'cap2': 2, 'cap1': 1}.get(phase)
    operation = 'read' if readback or phase == 'baseline' else ('reset' if phase == 'reset' else 'set')
    status = {'read': 'read', 'set': 'applied', 'reset': 'reset'}[operation]
    suffix = '-read' if readback else '-apply'
    require(packet['operation'] == operation and packet['status'] == status
        and packet['requestToken'] == nonce + '-' + phase + suffix, 'Native operation or token differs')
    requested = None if operation != 'set' else cap
    require(typed_equal(packet['requestedCap'], requested), 'Native requested cap differs')
    expected = cap if cap is not None else baseline
    require(type(packet['configuredCap']) is int and packet['configuredCap'] == expected
        and packet['hasUserValue'] is (phase in ('cap2', 'cap1')), 'Native preference readback differs')
    require(packet['rfpEnabled'] is (mode == 'rfp') and packet['nativePreferenceReadback'] is True
        and packet['scope'] == 'runtime-native-pref' and packet['workerCoverageVerified'] is False
        and packet['fingerprintProtectionVerified'] is False, 'Native scope or RFP fence differs')


def observation(value, role, phase, nonce, source, expected):
    require(type(value) is dict and set(value) == {'schema', 'nonce', 'sourceCommit', 'role', 'phase', 'status', 'observation', 'error'},
        'Observation schema differs')
    require(type(value['schema']) is int and value['schema'] == 1 and value['nonce'] == nonce
        and value['sourceCommit'] == source and value['role'] == role and value['phase'] == phase,
        'Observation binding differs')
    status = value['status']
    require(status in ('observed', 'unsupported', 'failed'), 'Unknown observation status')
    if status != 'observed':
        require(value['observation'] is None and type(value['error']) is str
            and value['error'] in OBSERVATION_ERRORS, 'Invalid failure metadata')
        return dict(role=role, status=status, actualExecution=False, hardwareConcurrency=None, nativeGetter=None,
            capObeyed=None, error=value['error'])
    row = value['observation']
    require(type(row) is dict and set(row) == {'hardwareConcurrency', 'nativeGetter'} and type(row['nativeGetter']) is bool
        and value['error'] is None,
        'Navigator observation schema differs')
    count = row['hardwareConcurrency']
    require(type(count) is int and 1 <= count <= MAX_HARDWARE_COUNT, 'Positive typed hardware count required')
    return dict(role=role, status=status, actualExecution=True, hardwareConcurrency=count, nativeGetter=row['nativeGetter'],
        capObeyed=count <= expected, error=None)


def navigation_proof(value, phase):
    booleans = ('bootstrapStarted', 'bootstrapDocumentReady', 'bootstrapStoppedSuccessfully', 'probeRequested',
        'probeStarted', 'probeDocumentReady', 'probeStoppedSuccessfully', 'targetOwnedCompletion')
    fields = {'schema', 'targetPath', 'activePath', 'locationPath', 'generation',
        'failedStopsWithoutNativeUrl', 'targetLoadError', *booleans}
    require(type(value) is dict and set(value) == fields, 'Bounded native navigation proof required')
    target = phase + '/probe'
    require(type(value['schema']) is int and value['schema'] == 1 and value['targetPath'] == target
        and value['activePath'] == target and value['locationPath'] == target
        and all(value[name] is True for name in booleans) and value['targetLoadError'] is False,
        'Owned target document did not complete')
    require(type(value['generation']) is int and 2 <= value['generation'] <= 512
        and type(value['failedStopsWithoutNativeUrl']) is int
        and 0 <= value['failedStopsWithoutNativeUrl'] <= 512, 'Invalid bounded navigation counters')
    return dict(targetPath=target, generation=value['generation'], targetOwnedCompletion=True,
        failedStopsWithoutNativeUrl=value['failedStopsWithoutNativeUrl'])


def event_proof(report):
    events = report.get('nativeEvents')
    require(type(events) is list and 1 <= len(events) <= 256, 'Bounded native events required')
    paths = ('initial', 'bootstrap', 'other', *(phase + '/probe' for phase in PHASES))
    for event in events:
        require(type(event) is dict and set(event) == {'event', 'stage', 'phase', 'path', 'generation',
            'success', 'errorCategory', 'errorCode', 'nativeUrlAvailable', 'elapsedMs'}, 'Native event shape differs')
        require(event['event'] in ('page-start', 'page-stop', 'page-failed', 'location', 'load-error', 'private-document-ready')
            and event['phase'] in ('initial', *PHASES) and event['path'] in paths
            and event['stage'] in ('extension', 'bootstrap', 'native-apply', 'observing', 'native-readback')
            and type(event['generation']) is int and 0 <= event['generation'] <= 512
            and type(event['elapsedMs']) is int and 0 <= event['elapsedMs'] <= 240000, 'Native event binding differs')
        stop = event['event'] in ('page-stop', 'page-failed')
        require(event['nativeUrlAvailable'] is (not stop)
            and (type(event['success']) is bool if stop else event['success'] is None),
            'Native stop URL ownership must remain explicit')
        error = event['event'] == 'load-error'
        require(all(type(event[name]) is int if error else event[name] is None for name in ('errorCategory', 'errorCode')),
            'Typed native error codes required')
    for row in report['phases']:
        phase = row['phase']; target = phase + '/probe'; generation = row['navigation']['generation']
        owned = [event for event in events if event['phase'] == phase and event['path'] == target
            and event['generation'] == generation]
        names = {event['event'] for event in owned if event['event'] != 'page-stop' or event['success'] is True}
        require({'page-start', 'location', 'private-document-ready', 'page-stop'} <= names,
            'Actual owned native phase event quartet missing')
        require(not any(event['event'] == 'load-error' for event in owned), 'Owned target native load error')
    server = report.get('server')
    require(type(server) is dict and set(server) == {'schema', 'requests', 'responses', 'rejectedRequests',
        'transportErrors', 'events', 'eventsTruncated'} and type(server['schema']) is int and server['schema'] == 1
        and all(type(server[name]) is int and 0 <= server[name] <= 512
            for name in ('requests', 'responses', 'rejectedRequests', 'transportErrors'))
        and server['eventsTruncated'] is False, 'Complete bounded server counters required')
    rows = server['events']
    require(type(rows) is list and len(rows) <= 256, 'Bounded synthetic server events required')
    allowed_paths = ('bootstrap', 'other', *(phase + '/' + name for phase in PHASES
        for name in ('probe', 'probe.js', 'worker.js', 'report')))
    served = set()
    for event in rows:
        require(type(event) is dict and set(event) == {'event', 'method', 'path', 'status', 'error'}
            and event['event'] in ('request', 'response', 'rejected', 'error')
            and event['method'] in ('GET', 'POST', 'other') and event['path'] in allowed_paths,
            'Synthetic server event shape differs')
        require((type(event['status']) is int and 100 <= event['status'] <= 599) if event['event'] == 'response'
            else event['status'] is None, 'Server response status differs')
        require(event['error'] in (None, 'request-line', 'origin-or-nonce', 'timeout', 'short-read',
            'json-shape', 'uri-shape', 'bounded-io', 'request-shape'), 'Unknown server error metadata')
        if event['event'] == 'response' and event['method'] == 'GET' and event['status'] == 200:
            served.add(event['path'])
    require({phase + '/probe' for phase in PHASES} <= served, 'Actual controlled phase HTTP200 response missing')


def validate_case(report, *, mode, nonce, source, tree, identity):
    require(mode in MODES and re.fullmatch('[0-9a-f]{32}', nonce) is not None, 'Invalid selected case')
    fields = {'schema', 'status', 'stage', 'failure', 'diagnosticOnly', 'releaseAcceptance', 'actualAndroidExecution',
        'actualGeckoExecution', 'sourceCommit', 'sourceTree', 'buildIdentity', 'runNonce', 'mode', 'process',
        'nativePreferenceOnly', 'navigatorGetterOverrideUsed', 'debuggingEndpointUsed', 'javaTimezoneOverrideUsed',
        'processTimezoneEnvironmentChangedByProbe', 'workerCoverageVerified', 'fingerprintProtectionVerified',
        'phases', 'server', 'nativeEvents'}
    require(type(report) is dict and set(report) == fields, 'Native report schema differs')
    require(type(report['schema']) is int and report['schema'] == 1 and report['status'] == 'observed'
        and report['stage'] == 'complete' and report['failure'] == '', 'Actual completed native observation required')
    require(report['runNonce'] == nonce and report['mode'] == mode and report['sourceCommit'] == source
        and report['sourceTree'] == tree, 'Native case source/nonce/mode differs')
    require(report['diagnosticOnly'] is True and report['releaseAcceptance'] is False
        and report['actualAndroidExecution'] is True and report['actualGeckoExecution'] is True
        and report['nativePreferenceOnly'] is True, 'Actual diagnostic Gecko execution required')
    installed_identity(report['buildIdentity'], identity)
    for name in ('navigatorGetterOverrideUsed', 'debuggingEndpointUsed', 'javaTimezoneOverrideUsed',
        'processTimezoneEnvironmentChangedByProbe', 'workerCoverageVerified', 'fingerprintProtectionVerified'):
        require(report[name] is False, 'Probe must preserve diagnostic scope: ' + name)
    process = report['process']
    require(type(process) is dict and set(process) == {'pid', 'uid', 'javaTimezoneBefore', 'javaTimezoneAfter',
        'icuTimezoneBefore', 'icuTimezoneAfter', 'tzEnvironmentBefore', 'tzEnvironmentAfter'}
        and type(process['pid']) is int and process['pid'] > 0 and type(process['uid']) is int
        and 10000 <= process['uid'] < 100000, 'Actual process identity required')
    for before, after in (('javaTimezoneBefore', 'javaTimezoneAfter'), ('icuTimezoneBefore', 'icuTimezoneAfter'),
        ('tzEnvironmentBefore', 'tzEnvironmentAfter')):
        require(typed_equal(process[before], process[after]) and (process[before] is None
            or (type(process[before]) is str and len(process[before]) <= 100)), 'Process timezone baseline changed')
    rows = report['phases']
    require(type(rows) is list and len(rows) == len(PHASES), 'Every ordered phase is required')
    first = rows[0]
    require(type(first) is dict and type(first.get('nativeApply')) is dict, 'Baseline native receipt required')
    baseline = first['nativeApply'].get('configuredCap')
    require(type(baseline) is int and 1 <= baseline <= MAX_HARDWARE_COUNT, 'Bounded native default cap required')
    findings = []
    previous_generation = 0
    for phase, row in zip(PHASES, rows):
        require(type(row) is dict and set(row) == {'phase', 'nativeApply', 'nativeRead', 'navigation', 'observations'}
            and row['phase'] == phase, 'Native phase order or schema differs')
        native_ack(row['nativeApply'], phase=phase, nonce=nonce, mode=mode, readback=False, baseline=baseline)
        native_ack(row['nativeRead'], phase=phase, nonce=nonce, mode=mode, readback=True, baseline=baseline)
        navigation = navigation_proof(row['navigation'], phase)
        require(navigation['generation'] > previous_generation, 'Each phase requires a fresh owned document')
        previous_generation = navigation['generation']
        packets = row['observations']
        require(type(packets) is list and len(packets) == len(ROLES), 'Every context must report an actual outcome')
        by_role = {}
        for packet in packets:
            require(type(packet) is dict and packet.get('role') in ROLES and packet['role'] not in by_role,
                'Duplicate/unknown context')
            by_role[packet['role']] = packet
        expected = {'cap2': 2, 'cap1': 1}.get(phase, 4)
        configured = {'cap2': 2, 'cap1': 1}.get(phase, baseline)
        contexts = [observation(by_role[role], role, phase, nonce, source, expected) for role in ROLES]
        require(contexts[0]['actualExecution'], 'Actual main-document navigator observation missing')
        require(mode != 'standard' or contexts[0]['nativeGetter'] is True, 'Actual standard page native getter required')
        findings.append(dict(phase=phase, configuredCap=configured, rfpEnabled=mode == 'rfp',
            navigationProof=navigation, contexts=contexts))
    event_proof(report)
    page_counts = [phase['contexts'][0]['hardwareConcurrency'] for phase in findings]
    sequence = page_counts == [4, 2, 1, 4]
    return dict(mode=mode, nativeDefaultCap=baseline, phases=findings, pageHardwareCounts=page_counts,
        standardPageSequenceVerified=sequence if mode == 'standard' else None,
        rfpRemainedEnabled=mode == 'rfp', workerCoverageVerified=False, fingerprintProtectionVerified=False)


def snapshot():
    names = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard',
        'app', 'tests', 'tools', '.github/workflows/native-hardware-probe.yml'], cwd=ROOT, text=True).splitlines()
    return {name: sha(ROOT / name) for name in sorted(set(names)) if (ROOT / name).is_file()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adb', default='adb')
    parser.add_argument('--serial', default='emulator-5554')
    parser.add_argument('--apk', type=Path, required=True)
    parser.add_argument('--source', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    require(args.serial == 'emulator-5554', 'Controlled emulator target required')
    require(re.fullmatch('[0-9a-f]{40}', args.source) is not None, 'Exact selected source required')
    source = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    tree = subprocess.check_output(['git', 'rev-parse', 'HEAD^{tree}'], cwd=ROOT, text=True).strip()
    require(source == args.source and re.fullmatch('[0-9a-f]{40}', tree) is not None, 'Selected source differs')
    require(not subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True).strip(),
        'Clean selected diagnostic source required')
    output = args.output.absolute()
    require(not output.exists() and all(not p.is_symlink() for p in (output, *output.parents)),
        'Fresh ordinary report directory required')
    require(args.apk.is_file() and not args.apk.is_symlink(), 'Actual ordinary integration APK required')
    before = snapshot()
    settings = (ROOT / 'app/build.gradle').read_text()
    identity = expected_build(args.apk, source, tree, re.search(r"versionName '([^']+)'", settings)[1],
        int(re.search(r'versionCode ([0-9]+)', settings)[1]))
    output.mkdir(parents=True)
    def adb(*parts, check=True, timeout=20):
        return subprocess.run([args.adb, '-s', args.serial, *parts], capture_output=True, check=check, timeout=timeout)
    def system_state():
        zone = adb('shell', 'getprop', 'persist.sys.timezone').stdout.decode('utf-8').strip()
        auto = adb('shell', 'settings', 'get', 'global', 'auto_time_zone').stdout.decode('ascii').strip()
        require(len(zone) <= 100 and auto in ('0', '1', 'null'), 'Invalid system timezone metadata')
        return dict(timezoneProperty=zone, automaticTimezone=auto)
    records = []; findings = []; errors = []
    system_before = None; system_after = None; guest_cpus = None; used_nonces = set(); used_pids = set()
    try:
        require(adb('shell', 'getprop', 'ro.kernel.qemu').stdout.strip() == b'1', 'Actual emulator required')
        require(adb('shell', 'getprop', 'ro.build.version.sdk').stdout.strip() == b'35', 'Selected actual API35 runtime required')
        require(adb('shell', 'id', '-u').stdout.strip() == b'2000', 'Evidence must be read as shell UID2000')
        guest_raw = adb('shell', 'getconf', '_NPROCESSORS_ONLN').stdout.strip()
        require(guest_raw == b'4', 'Actual native-ADB guest online CPU count must be four')
        guest_cpus = 4
        installed_identity(strict_json(adb('exec-out', 'content', 'read', '--uri',
            'content://' + PACKAGE + '.evidence/build-identity').stdout), identity)
        system_before = system_state()
        for mode in MODES:
            nonce = uuid.uuid4().hex
            require(nonce not in used_nonces, 'Fresh mode nonce required')
            used_nonces.add(nonce)
            stage = 'fresh-process'; entry = dict(mode=mode, runNonce=nonce, status='failed')
            try:
                adb('shell', 'am', 'force-stop', PACKAGE)
                require(not adb('shell', 'pidof', PROCESS, check=False).stdout.strip(), 'Prior probe process remained alive')
                stage = 'launch'
                adb('shell', 'am', 'start', '-W', '-n', COMPONENT, '--es', 'runNonce', nonce,
                    '--es', 'sourceCommit', source, '--es', 'mode', mode)
                stage = 'observe'; deadline = time.monotonic() + 240; report = None
                while time.monotonic() < deadline:
                    response = adb('exec-out', 'content', 'read', '--uri', 'content://' + AUTHORITY + '/report/' + nonce,
                        check=False)
                    raw = response.stdout
                    try:
                        value = strict_json(raw)
                    except (ValueError, UnicodeError):
                        time.sleep(.25); continue
                    if value.get('status') in ('observed', 'failed'):
                        # Preserve the provider's bounded original bytes even when source,
                        # phase, native ACK or independent observation validation fails.
                        report = value
                        path = output / ('case-' + mode + '.json')
                        path.write_bytes(raw)
                        entry.update(report=path.name, reportSha256=hashlib.sha256(raw).hexdigest(), reportBytes=len(raw))
                    require(value.get('runNonce') == nonce, 'Stale invocation report')
                    require(value.get('sourceCommit') == source and value.get('sourceTree') == tree, 'Stale source report')
                    if report is not None:
                        break
                    require(value.get('status') == 'running', 'Unknown report status')
                    time.sleep(.25)
                require(report is not None, 'Diagnostic did not terminate')
                current = validate_case(report, mode=mode, nonce=nonce, source=source, tree=tree, identity=identity)
                pid = adb('shell', 'pidof', PROCESS).stdout.decode('ascii').strip()
                require(pid == str(report['process']['pid']), 'Observed process owner differs')
                require(pid not in used_pids, 'Each mode requires a fresh actual process')
                used_pids.add(pid)
                current['systemTimezoneUnchanged'] = system_state() == system_before
                require(current['systemTimezoneUnchanged'], 'Android system timezone changed')
                entry.update(status='observed', finding=current); findings.append(current)
            except Exception as error:
                entry.update(errorType=type(error).__name__, failureStage=stage)
                errors.append(dict(mode=mode, errorType=type(error).__name__, stage=stage))
            finally:
                try:
                    adb('shell', 'am', 'force-stop', PACKAGE)
                except Exception:
                    pass
                records.append(entry)
        system_after = system_state()
    except Exception as error:
        errors.append(dict(stage='device-preflight-or-final-state', errorType=type(error).__name__))
    stable = snapshot() == before
    completed = len(records) == len(MODES) and all(row['status'] == 'observed' for row in records)
    page_verified = completed and findings[0]['standardPageSequenceVerified'] is True
    passed = completed and page_verified and system_before is not None and system_before == system_after and stable and not errors
    result = dict(schema=1, status='observed' if passed else 'failed', diagnosticOnly=True, releaseAcceptance=False,
        sourceCommit=source, sourceTree=tree, runId=os.environ.get('GITHUB_RUN_ID'), runAttempt=os.environ.get('GITHUB_RUN_ATTEMPT'),
        expectedBuildIdentity=identity, guestOnlineCpus=guest_cpus, actualAndroidExecution=bool(findings),
        actualGeckoExecution=bool(findings), standardPageSequenceVerified=bool(page_verified),
        workerCoverageVerified=False, fingerprintProtectionVerified=False, caseRecords=records, errors=errors,
        systemBefore=system_before, systemAfter=system_after,
        systemTimezoneUnchanged=system_before is not None and system_before == system_after,
        sourceFiles=before, executionInputsUnchanged=stable, debuggingEndpointUsed=False,
        navigatorGetterOverrideUsed=False, systemTimezoneModifiedByProbe=False,
        scope='Diagnostic-only native runtime preference read/set/reset on one actual Gecko runtime per mode. '
            'Untouched navigator.hardwareConcurrency is sampled independently in page/dedicated/blob/shared/service contexts '
            'at every phase. STANDARD page sequence must be 4,2,1,4 on the fixed four-CPU guest. RFP stays enabled and '
            'all raw RFP counts, unsupported outcomes and cap mismatches remain explicit. Native ACK is not worker or protection acceptance.')
    (output / 'results.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({name: result[name] for name in ('status', 'diagnosticOnly', 'releaseAcceptance', 'sourceCommit',
        'standardPageSequenceVerified', 'systemTimezoneUnchanged', 'executionInputsUnchanged')}))
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
