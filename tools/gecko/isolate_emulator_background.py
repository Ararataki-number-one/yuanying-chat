#!/usr/bin/env python3
"""Isolate one observed background competitor in a fresh synthetic CI emulator.

This is an emulator prerequisite, not application or phone acceptance. No input
workload, timing, IME, viewport, hardware allocation or app setting is changed.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
import uuid

try:
    from .profile_invocation_contract import expected_build
    from .prepare_emulator import validate_observation, AUTHORITY
except ImportError:
    from profile_invocation_contract import expected_build
    from prepare_emulator import validate_observation, AUTHORITY

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = 'com.google.android.gms'
SERIAL = 'emulator-5554'
REPOSITORY = 'Ararataki-number-one/yuanying-chat'
MAX_OUTPUT = 1024 * 1024
MAX_BOOTSTRAP = 4 * MAX_OUTPUT
FLAGS = dict(applicationAcceptance=False, actualGeckoExecution=False,
             physicalPhoneAcceptance=False, gestureReplayed=False,
             applicationOrInputPolicyModified=False)
REASONS = frozenset(('invalid-json', 'synthetic-ci-required', 'invalid-ci-identity',
    'bootstrap-not-ready', 'bootstrap-scope-invalid', 'bootstrap-build-mismatch',
    'bootstrap-run-mismatch', 'bootstrap-network-missing', 'bootstrap-network-invalid',
    'synthetic-target-required', 'deadline-expired', 'deadline-unavailable',
    'command-failed', 'command-output-too-large', 'command-timed-out', 'command-unavailable',
    'before-network-invalid', 'before-network-unusable', 'after-network-invalid',
    'after-network-unusable', 'process-observation-invalid', 'bootstrap-changed',
    'synthetic-image-required', 'background-package-not-present',
    'background-disable-unconfirmed', 'background-processes-still-running',
    'bootstrap-output-not-fresh', 'invalid-arguments', 'invalid-timeout', 'invalid-source',
    'dirty-source', 'synthetic-apk-required', 'isolation-unavailable',
    'bootstrap-save-unconfirmed'))


class IsolationFailure(Exception):
    """Only fixed reason codes are allowed to reach the public report."""


def need(condition, reason):
    if not condition:
        raise IsolationFailure(reason)


def expired(signum, frame):
    raise IsolationFailure('deadline-expired')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def strict_json(raw):
    def pairs(rows):
        result = {}
        for key, value in rows:
            need(key not in result, 'invalid-json')
            result[key] = value
        return result
    try:
        return json.loads(raw, object_pairs_hook=pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(IsolationFailure('invalid-json')))
    except (UnicodeError, json.JSONDecodeError):
        raise IsolationFailure('invalid-json') from None


def validate_ci(environment, source):
    need(environment.get('CI') == environment.get('GITHUB_ACTIONS') == 'true'
         and environment.get('GITHUB_REPOSITORY') == REPOSITORY
         and environment.get('GITHUB_SHA') == source
         and environment.get('GITHUB_EVENT_NAME') in ('push', 'workflow_dispatch'), 'synthetic-ci-required')
    for key in ('GITHUB_RUN_ID', 'GITHUB_RUN_ATTEMPT'):
        need(re.fullmatch('[1-9][0-9]*', environment.get(key, '')) is not None, 'invalid-ci-identity')
    return environment['GITHUB_RUN_ID'], environment['GITHUB_RUN_ATTEMPT']


def validate_bootstrap(value, identity, run, attempt):
    need(isinstance(value, dict) and value.get('schema') == 2
         and value.get('status') == 'passed' and value.get('serial') == SERIAL
         and value.get('sourceCommit') == identity['sourceCommit']
         and value.get('sourceTree') == identity['sourceTree']
         and 'backgroundIsolation' not in value, 'bootstrap-not-ready')
    for key in ('confirmedQemu', 'actualAndroidCommands', 'actualIntegrationProviderExecution',
                'actualConnectivityManagerExecution'):
        need(value.get(key) is True, 'bootstrap-not-ready')
    for key in ('applicationAcceptance', 'actualGeckoExecution', 'physicalPhoneAcceptance',
                'applicationOrInputPolicyModified', 'gestureReplayed'):
        need(value.get(key) is False, 'bootstrap-scope-invalid')
    need(json.dumps(value.get('expectedBuildIdentity'), sort_keys=True, separators=(',', ':')) ==
         json.dumps(identity, sort_keys=True, separators=(',', ':')), 'bootstrap-build-mismatch')
    sdk = identity.get('sdkBuildIdentity')
    need(isinstance(sdk, dict) and str(sdk.get('runId')) == run
         and str(sdk.get('runAttempt')) == attempt, 'bootstrap-run-mismatch')
    observations = value.get('networkObservations')
    need(isinstance(observations, list) and observations, 'bootstrap-network-missing')
    row = observations[-1]
    try:
        valid = validate_observation(row['value'], identity, row['runNonce'])
    except (KeyError, TypeError, ValueError):
        raise IsolationFailure('bootstrap-network-invalid') from None
    need(valid and row['value'].get('androidSdk') == 35, 'bootstrap-network-invalid')


class Commands:
    def __init__(self, executable, serial, record, deadline):
        need(serial == SERIAL, 'synthetic-target-required')
        self.executable, self.serial, self.record, self.deadline = executable, serial, record, deadline

    def run(self, operation, *parts):
        remaining = self.deadline - time.monotonic()
        need(remaining > 0, 'deadline-expired')
        started = time.monotonic()
        row = dict(operation=operation, succeeded=False, timedOut=False)
        self.record['operations'].append(row)
        try:
            result = subprocess.run([self.executable, '-s', self.serial, *parts],
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    timeout=min(8, remaining), check=False)
            row['exitCode'] = result.returncode
            need(result.returncode == 0, 'command-failed')
            need(len(result.stdout) <= MAX_OUTPUT and len(result.stderr) <= MAX_OUTPUT,
                 'command-output-too-large')
            text = result.stdout.decode('utf-8', errors='strict').replace('\r', '').strip()
            need(time.monotonic() < self.deadline, 'deadline-expired')
            row['succeeded'] = True
            return text
        except subprocess.TimeoutExpired:
            row['timedOut'] = True
            raise IsolationFailure('command-timed-out') from None
        except (OSError, UnicodeError):
            raise IsolationFailure('command-unavailable') from None
        finally:
            row['elapsedMs'] = max(0, round((time.monotonic() - started) * 1000))


def network(commands, identity, stage):
    nonce = uuid.uuid4().hex
    raw = commands.run(stage + '-network', 'exec-out', 'content', 'read', '--uri',
                       'content://' + AUTHORITY + '/default-network?runNonce=' + nonce)
    value = strict_json(raw)
    try:
        valid = validate_observation(value, identity, nonce)
    except (TypeError, ValueError):
        raise IsolationFailure(stage + '-network-invalid') from None
    need(valid and value.get('androidSdk') == 35, stage + '-network-unusable')
    return True


def process_count(raw):
    rows = raw.splitlines()
    need(rows and rows[0].strip() == 'NAME' and 1 < len(rows) <= 4097, 'process-observation-invalid')
    names = [row.strip() for row in rows[1:]]
    need(all(name and len(name) <= 512 and not re.search(r'\s|\x00', name) for name in names)
         and any(name in ('init', 'system_server') for name in names), 'process-observation-invalid')
    return sum(name == PACKAGE or name.startswith(PACKAGE + '.') or name.startswith(PACKAGE + ':')
               for name in names)


def unchanged(path, original):
    need(not path.is_symlink() and path.is_file() and path.stat().st_size == len(original)
         and path.read_bytes() == original,
         'bootstrap-changed')


def isolate(commands, record, identity, before_mutation):
    properties = {
        'qemu': ('ro.kernel.qemu', lambda value: value == '1'),
        'sdk': ('ro.build.version.sdk', lambda value: value == '35'),
        'abi': ('ro.product.cpu.abi', lambda value: value == 'x86_64'),
        'hardware': ('ro.hardware', lambda value: value == 'ranchu'),
        'fingerprint': ('ro.build.fingerprint', lambda value: re.fullmatch(
            r'google/sdk_gphone64_x86_64/emu64xa:15/[^\s]+:userdebug/dev-keys', value) is not None),
    }
    for label, (key, valid) in properties.items():
        need(valid(commands.run('device-' + label, 'shell', 'getprop', key)), 'synthetic-image-required')
    record['syntheticImageConfirmed'] = True
    record['networkBeforeUsable'] = network(commands, identity, 'before')
    present = commands.run('package-present', 'shell', 'pm', 'list', 'packages', '--user', '0', PACKAGE)
    need('package:' + PACKAGE in present.splitlines(), 'background-package-not-present')
    record['packagePresent'] = True
    record['processesBefore'] = process_count(commands.run('processes-before', 'shell', 'ps', '-A', '-o', 'NAME'))
    before_mutation()
    commands.run('force-stop', 'shell', 'am', 'force-stop', '--user', '0', PACKAGE)
    commands.run('disable-package', 'shell', 'pm', 'disable-user', '--user', '0', PACKAGE)
    disabled = commands.run('read-disabled', 'shell', 'pm', 'list', 'packages', '-d', '--user', '0', PACKAGE)
    need('package:' + PACKAGE in disabled.splitlines(), 'background-disable-unconfirmed')
    record['disabledStateConfirmed'] = True
    record['processesAfter'] = process_count(commands.run('processes-after', 'shell', 'ps', '-A', '-o', 'NAME'))
    need(record['processesAfter'] == 0, 'background-processes-still-running')
    record['processStopConfirmed'] = True
    record['networkAfterUsable'] = network(commands, identity, 'after')
    record['status'] = 'passed'


def append_result(path, original, bootstrap, record):
    unchanged(path, original)
    value = dict(bootstrap)
    value['backgroundIsolation'] = record
    if record['status'] != 'passed':
        value['status'] = 'failed'
    temporary = path.with_suffix('.background-partial')
    need(not temporary.exists() and not temporary.is_symlink(), 'bootstrap-output-not-fresh')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    unchanged(path, original)
    temporary.replace(path)


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise IsolationFailure('invalid-arguments')


def main(argv=None):
    record = dict(schema=1, status='failed', exactPackage=PACKAGE, operations=[],
                  syntheticImageConfirmed=False, packagePresent=False,
                  disabledStateConfirmed=False, processStopConfirmed=False,
                  networkBeforeUsable=False, networkAfterUsable=False, **FLAGS)
    original = bootstrap = path = old_handler = None
    alarm_installed = False
    started = time.monotonic()
    code = 1
    try:
        parser = Parser(description=__doc__)
        parser.add_argument('--adb', required=True)
        parser.add_argument('--serial', required=True, choices=[SERIAL])
        parser.add_argument('--apk', required=True, type=Path)
        parser.add_argument('--timeout', type=int, default=20)
        args = parser.parse_args(argv)
        need(10 <= args.timeout <= 30, 'invalid-timeout')
        need(signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0), 'deadline-unavailable')
        old_handler = signal.signal(signal.SIGALRM, expired)
        signal.setitimer(signal.ITIMER_REAL, max(0.001, started + args.timeout - time.monotonic()))
        alarm_installed = True
        source = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT,
                                         stderr=subprocess.PIPE, text=True, timeout=5).strip()
        tree = subprocess.check_output(['git', 'rev-parse', 'HEAD^{tree}'], cwd=ROOT,
                                       stderr=subprocess.PIPE, text=True, timeout=5).strip()
        need(re.fullmatch('[0-9a-f]{40}', source) is not None and
             re.fullmatch('[0-9a-f]{40}', tree) is not None, 'invalid-source')
        run, attempt = validate_ci(os.environ, source)
        need(not subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=normal'],
                                        cwd=ROOT, stderr=subprocess.PIPE, text=True, timeout=5).strip(),
             'dirty-source')
        need(args.apk.resolve() == ROOT / 'app/build/outputs/apk/integration/app-x86_64-integration.apk',
             'synthetic-apk-required')
        settings = (ROOT / 'app/build.gradle').read_text()
        version = re.search(r"versionName '([^']+)'", settings).group(1)
        version_code = int(re.search(r'versionCode ([0-9]+)', settings).group(1))
        identity = expected_build(args.apk.resolve(), source, tree, version, version_code)
        need(identity.get('package') == 'local.pocketchat.test', 'synthetic-apk-required')
        path = ROOT / 'work/gecko-integration/emulator-bootstrap-results.json'
        need(path.is_file() and not path.is_symlink() and 0 < path.stat().st_size <= MAX_BOOTSTRAP,
             'bootstrap-not-ready')
        original = path.read_bytes()
        bootstrap = strict_json(original)
        validate_bootstrap(bootstrap, identity, run, attempt)
        record.update(sourceCommit=source, sourceTree=tree, runId=run, runAttempt=attempt,
                      originalBootstrapSha256=digest(original), originalBootstrapBytes=len(original),
                      timeoutSeconds=args.timeout)
        commands = Commands(args.adb, args.serial, record, started + args.timeout)
        isolate(commands, record, identity, lambda: unchanged(path, original))
        code = 0
    except IsolationFailure as error:
        record.update(status='failed', reason=str(error) if str(error) in REASONS else 'isolation-unavailable')
    except BaseException:
        record.update(status='failed', reason='isolation-unavailable')
    finally:
        # The action budget includes local source/APK checks as well as adb.
        # Cancel only our timer before the bounded-size local receipt update.
        if alarm_installed:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, old_handler)
    record['elapsedMs'] = max(0, round((time.monotonic() - started) * 1000))
    if original is not None and bootstrap is not None and 'sourceCommit' in record:
        try:
            append_result(path, original, bootstrap, record)
        except BaseException:
            record.update(status='failed', reason='bootstrap-save-unconfirmed')
            code = 1
    # This deliberately excludes command output, process names/IDs, paths and
    # arbitrary exception text. The existing bootstrap's old fields stay intact.
    summary = {key: record[key] for key in ('schema', 'status', 'exactPackage',
               'syntheticImageConfirmed', 'disabledStateConfirmed', 'processStopConfirmed',
               'networkBeforeUsable', 'networkAfterUsable', 'elapsedMs', *FLAGS)}
    if 'reason' in record:
        summary['reason'] = record['reason']
    for key in ('sourceCommit', 'sourceTree', 'runId', 'runAttempt'):
        if key in record:
            summary[key] = record[key]
    print('EMULATOR_BACKGROUND_ISOLATION ' + json.dumps(summary, separators=(',', ':')))
    return code


if __name__ == '__main__':
    sys.exit(main())
