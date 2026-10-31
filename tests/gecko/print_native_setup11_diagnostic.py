#!/usr/bin/env python3
"""Print a bounded projection of this job's existing setup record; never repair it.

No application, device or acceptance command runs here. The original JSON and
artifact remain unchanged. Missing evidence is unavailable, never a pass.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import subprocess

ROOT = Path(__file__).resolve().parents[2]
SETUP_FILE = ROOT / 'work/gecko-integration/native-adb-setup-results.json'
PREFIX = 'NATIVE_ADB_SETUP_DIAGNOSTIC '
MAX_INPUT_BYTES = 8 * 1024 * 1024
MAX_OUTPUT_BYTES = 16 * 1024
MAX_PROBES = 16
PHASES = frozenset(('ui', 'editing', 'files', 'connections', 'profiles'))
OUTCOMES = frozenset(('success', 'failure', 'cancelled', 'skipped'))
ERROR_TYPES = frozenset(('TimeoutError', 'TimeoutExpired', 'ValueError', 'AssertionError',
    'CalledProcessError', 'FileNotFoundError', 'PermissionError', 'OSError', 'EOFError',
    'ConnectionRefusedError', 'ConnectionResetError', 'ConnectionAbortedError',
    'BrokenPipeError', 'RuntimeError', 'UnicodeDecodeError', 'JSONDecodeError',
    'IsADirectoryError', 'NotADirectoryError'))
BOOL_FIELDS = ('confirmedQemu', 'actualAndroidCommands', 'actualIntegrationProviderExecution',
    'actualConnectivityManagerExecution', 'endpointProtocolReachable', 'nativeReady',
    'announcementSent', 'announcementIsNotificationOnly', 'disabledStateConfirmed',
    'normalPreflightStillRequired', 'originalWorkloadInvoked', 'applicationOrInputPolicyModified')


def unavailable(code, identity=None, input_meta=None):
    return dict(schema=1, diagnosticOnly=True, releaseAcceptance=False,
                applicationAcceptance=False, actualGeckoExecution=False,
                physicalPhoneAcceptance=False, status='unavailable', reasonCode=code,
                identity=identity, input=input_meta)


def identity_from_environment(env, head, tree):
    if (not re.fullmatch('[0-9a-f]{40}', head or '')
            or not re.fullmatch('[0-9a-f]{40}', tree or '')
            or env.get('GITHUB_SHA') != head or env.get('GITHUB_JOB') != 'android'
            or env.get('POCKET_NATIVE_SETUP_PHASE') not in PHASES
            or env.get('POCKET_NATIVE_SETUP_BOOT_OUTCOME') not in OUTCOMES):
        return None
    run, attempt = env.get('GITHUB_RUN_ID', ''), env.get('GITHUB_RUN_ATTEMPT', '')
    if not all(type(v) is str and re.fullmatch('[1-9][0-9]{0,19}', v) for v in (run, attempt)):
        return None
    return dict(sourceCommit=head, sourceTree=tree, runId=run, runAttempt=attempt,
                job='android', phase=env['POCKET_NATIVE_SETUP_PHASE'],
                bootOutcome=env['POCKET_NATIVE_SETUP_BOOT_OUTCOME'])


def read_setup(path):
    """Read one bounded ordinary file without following symlink ancestors."""
    if any(p.is_symlink() for p in (path, *path.parents)):
        return None, None, 'unsafe-input'
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, 'rb') as stream:
            before = os.fstat(stream.fileno())
            if not stat.S_ISREG(before.st_mode):
                return None, None, 'unsafe-input'
            if before.st_size > MAX_INPUT_BYTES:
                return None, dict(bytes=before.st_size, sha256=None), 'input-bound'
            raw = stream.read(MAX_INPUT_BYTES + 1)
            after = os.fstat(stream.fileno())
        current = path.lstat()
        if (len(raw) > MAX_INPUT_BYTES or len(raw) != before.st_size
                or (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
                != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
                or (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
                != (current.st_dev, current.st_ino, current.st_size, current.st_mtime_ns)
                or not stat.S_ISREG(current.st_mode)):
            return None, None, 'input-changed'
        return raw, dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()), None
    except FileNotFoundError:
        return None, None, 'missing-input'
    except OSError:
        return None, None, 'input-unavailable'


def unique(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('Duplicate JSON key')
        value[key] = item
    return value


def project(raw, identity):
    if len(raw) > MAX_INPUT_BYTES:
        return unavailable('input-bound', identity, dict(bytes=len(raw), sha256=None))
    meta = dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    if identity is None:
        return unavailable('identity-unavailable', input_meta=meta)
    try:
        record = json.loads(raw, object_pairs_hook=unique,
                            parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (ValueError, UnicodeError, RecursionError):
        return unavailable('invalid-json', identity, meta)
    if (type(record) is not dict or type(record.get('schema')) is not int
            or record['schema'] != 1 or record.get('status') not in ('passed', 'failed')):
        return unavailable('invalid-record', identity, meta)
    if any(type(record.get(key)) is not str or record[key] != identity[key]
           for key in ('sourceCommit', 'sourceTree', 'runId', 'runAttempt')):
        return unavailable('source-run-mismatch', identity, meta)
    result = unavailable('observed', identity, meta)
    result['status'] = 'available'
    setup = dict(status=record['status'])
    invalid = set()

    def boolean(target, source, key, prefix=''):
        if key not in source:
            return
        if type(source[key]) is bool:
            target[key] = source[key]
        else:
            invalid.add(prefix + key)

    def number(target, source, key, minimum=0, maximum=3_600_000, integer=False, prefix=''):
        if key not in source:
            return
        value = source[key]
        if (type(value) in ((int,) if integer else (int, float))
                and (type(value) is int or math.isfinite(value)) and minimum <= value <= maximum):
            target[key] = value
        else:
            invalid.add(prefix + key)

    def error_type(target, source, key, prefix=''):
        if key in source:
            target[key] = source[key] if type(source[key]) is str and source[key] in ERROR_TYPES else 'other'
            if target[key] == 'other':
                invalid.add(prefix + key)

    for key in BOOL_FIELDS:
        boolean(setup, record, key)
    for key in ('preparationBudgetSeconds', 'endpointDeadlineSeconds'):
        number(setup, record, key, maximum=3600)
    error_type(setup, record, 'failureType')
    tcp = record.get('tcpipCommand')
    if type(tcp) is dict:
        row = {}
        number(row, tcp, 'invocations', maximum=64, integer=True, prefix='tcpipCommand.')
        number(row, tcp, 'exitCode', minimum=-255, maximum=255, integer=True, prefix='tcpipCommand.')
        number(row, tcp, 'elapsedMs', prefix='tcpipCommand.')
        boolean(row, tcp, 'timedOut', 'tcpipCommand.')
        setup['tcpipCommand'] = row
    wifi = record.get('nativeWifiPathPreparation')
    if type(wifi) is dict:
        row = {}
        if wifi.get('status') in ('passed', 'failed'):
            row['status'] = wifi['status']
        boolean(row, wifi, 'repairAttempted', 'nativeWifiPathPreparation.')
        number(row, wifi, 'repairAttempts', maximum=64, integer=True, prefix='nativeWifiPathPreparation.')
        if type(wifi.get('observations')) is list:
            row['sampleCount'] = len(wifi['observations'])
        setup['nativeWifiPathPreparation'] = row
    result['setup'] = setup
    probes = record.get('endpointProbeAttempts')
    if type(probes) is list:
        indexes = list(range(len(probes))) if len(probes) <= MAX_PROBES else list(range(MAX_PROBES // 2)) + list(range(len(probes) - MAX_PROBES // 2, len(probes)))
        samples = []
        for index in indexes:
            row, item = dict(index=index), probes[index]
            if type(item) is not dict:
                row['unavailable'] = True
                samples.append(row)
                continue
            for key in ('tcpAccepted', 'payloadRead', 'authResponseSent', 'applicationCommandsSent'):
                boolean(row, item, key, 'endpointProbeAttempts.')
            if 'responseCommand' in item:
                if item['responseCommand'] in ('CNXN', 'AUTH', 'CLSE'):
                    row['responseCommand'] = item['responseCommand']
                else:
                    invalid.add('endpointProbeAttempts.responseCommand')
            number(row, item, 'elapsedMs', prefix='endpointProbeAttempts.')
            number(row, item, 'payloadBytesAdvertised', maximum=1024 * 1024, integer=True, prefix='endpointProbeAttempts.')
            error_type(row, item, 'errorType', 'endpointProbeAttempts.')
            samples.append(row)
        result['protocolProbe'] = dict(status='recorded', totalCount=len(probes),
                                      selectedCount=len(samples), omittedCount=len(probes) - len(samples), samples=samples)
    else:
        result['protocolProbe'] = dict(status='unavailable', reasonCode='not-recorded')
    result['invalidFields'] = sorted(invalid)
    return result


def render(value):
    line = PREFIX + json.dumps(value, ensure_ascii=True, separators=(',', ':'), allow_nan=False)
    if len(line.encode()) > MAX_OUTPUT_BYTES:
        line = PREFIX + json.dumps(unavailable('output-bound', value.get('identity'), value.get('input')),
                                   ensure_ascii=True, separators=(',', ':'))
    return line


def main():
    identity = None
    try:
        def git(revision):
            return subprocess.check_output(['git', 'rev-parse', revision], cwd=ROOT,
                                           stderr=subprocess.DEVNULL, text=True, timeout=3,
                                           env=dict(os.environ, GIT_NO_LAZY_FETCH='1', GIT_OPTIONAL_LOCKS='0')).strip()
        identity = identity_from_environment(os.environ, git('HEAD'), git('HEAD^{tree}'))
        raw, meta, error = read_setup(SETUP_FILE)
        value = unavailable(error, identity, meta) if error else project(raw, identity)
    except Exception:
        value = unavailable('diagnostic-unavailable', identity)
    print(render(value), flush=True)


if __name__ == '__main__':
    main()
