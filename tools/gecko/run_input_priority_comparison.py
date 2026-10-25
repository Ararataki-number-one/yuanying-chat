#!/usr/bin/env python3
"""One original qualification flow per real source, on one emulator per AB/BA job.

This is a reversible driver-priority hypothesis experiment, never release or
application acceptance. No workload retry, event replay, or CI identity override.
"""
import argparse
import fnmatch
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

from caret_build_identity import digest, embedded_identity, require, strict_json
from native_input_contract import verify_qualification
from run_input_clock_diagnostic import validate_identity
import sdk_identity_contract as sdk_contract

ROOT = Path(__file__).resolve().parents[2]
BASELINE = '02f447ba873fd216c2fac063a7c92afb7422eb51'
SHELL = 'tests/native-input-driver/NativeInputShell.java'
ADDITIONS = ('.github/workflows/gecko-input-priority-comparison.yml',
             'tools/gecko/run_input_priority_comparison.py',
             'tests/gecko_input_priority_comparison_test.py')
PATTERNS = ('native-input-*.json', 'native-input-*.log', 'gecko-performance-*.json',
            'gecko-performance-*.txt', 'gecko-performance-*.png', 'gecko-performance-*.xml',
            'gecko-scroll-*.json', 'installed-apk-read-performance-*.json')
EXACT = ('caret-apk-build-receipt.json', 'sdk-build-receipt.json',
         'derived-sdk-verification.json', 'derived-sdk-input.json',
         'android-emulator-package-results.json', 'android-system-image-results.json',
         'android-platform-tools-results.json', 'emulator-bootstrap-results.json',
         'native-adb-setup-results.json', 'native-test.log', 'emulator.log', 'build.log')
GESTURES = ('baseline-scroll', 'current-scroll')


def git(root, *args):
    return subprocess.check_output(['git', *args], cwd=root)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False); stream.write('\n')


def identity():
    run, attempt, event = (os.environ[key] for key in ('GITHUB_RUN_ID', 'GITHUB_RUN_ATTEMPT', 'GITHUB_SHA'))
    require(run.isdigit() and attempt.isdigit() and re.fullmatch('[0-9a-f]{40}', event), 'Real CI identity required')
    return dict(runId=run, runAttempt=attempt, eventSourceCommit=event)


def validate_sources(root, candidate):
    require(candidate == identity()['eventSourceCommit'], 'Candidate must equal actual event source')
    require(git(root, 'rev-parse', 'HEAD').decode().strip() == candidate, 'Orchestration HEAD differs')
    require(not git(root, 'status', '--porcelain').strip(), 'Clean orchestration source required')
    names = git(root, 'diff', '--name-only', BASELINE, candidate).decode().splitlines()
    require(set(names) == {SHELL, *ADDITIONS}, 'Only the priority shell and three experiment files may differ')
    require(git(root, 'rev-parse', BASELINE + ':app') == git(root, 'rev-parse', candidate + ':app'), 'App tree changed')
    return {role: dict(sourceCommit=source,
                       sourceTree=git(root, 'rev-parse', source + '^{tree}').decode().strip(),
                       appTree=git(root, 'rev-parse', source + ':app').decode().strip())
            for role, source in (('A', BASELINE), ('B', candidate))}


def prepare(args):
    roles = validate_sources(args.root, identity()['eventSourceCommit'])
    require(not args.out.exists() and not args.roles.exists(), 'Refuse an existing comparison or worktree set')
    args.roles.mkdir(parents=True)
    for role, value in roles.items():
        path = args.roles / role
        subprocess.run(['git', 'worktree', 'add', '--detach', str(path), value['sourceCommit']], cwd=args.root, check=True)
        value['checkout'] = str(path)
    plan = dict(schema=1, diagnosticOnly=True, applicationAcceptance=False, releaseAcceptance=False,
                order=args.order, roles=roles, **identity(),
                criteria='Both AB and BA must pass both original flows; candidate each same-name gesture maximum lateness must be no worse, and the worst of the two gestures must strictly improve in each order. Otherwise do not retain.',
                scope='Driver-thread hypothesis only. Baseline/current gesture names are original fixture variants, not product A/B releases. All original timings and checks remain unchanged.')
    write(args.out / 'plan.json', plan)


def load_plan(args):
    plan = strict_json((args.out / 'plan.json').read_bytes())
    require(all(plan.get(key) == value for key, value in identity().items()), 'Comparison CI identity differs')
    require(plan.get('order') == args.order and args.order in ('AB', 'BA'), 'Declared order differs')
    for role, value in plan['roles'].items():
        path = Path(value['checkout'])
        require(path == args.roles / role and git(path, 'rev-parse', 'HEAD').decode().strip() == value['sourceCommit'], 'Actual role HEAD differs')
        require(not git(path, 'status', '--porcelain').strip(), 'Actual role source dirty')
    return plan


def role_args(path, adb):
    out = path / 'work/gecko-integration'
    return argparse.Namespace(root=path, out=out, adb=adb, serial='emulator-5554',
        build_receipt=out / 'caret-apk-build-receipt.json',
        sdk_receipt=path / 'work/native-caret-sdk/sdk-build-receipt.json',
        sdk_aar=path / 'work/native-caret-sdk/geckoview-caret.aar',
        official_sdk_aar=out / 'geckoview.aar',
        integration_apk=path / 'app/build/outputs/apk/integration/app-x86_64-integration.apk',
        release_apk=path / 'app/build/outputs/apk/release/app-arm64-v8a-release-unsigned.apk')


def original_command(args):
    command = [sys.executable, str(args.root / 'tools/gecko/run_input_clock_diagnostic.py'),
               '--adb', args.adb, '--serial', args.serial, '--root', str(args.root), '--out', str(args.out)]
    for field in ('build_receipt', 'sdk_receipt', 'sdk_aar', 'official_sdk_aar', 'integration_apk', 'release_apk'):
        command += ['--' + field.replace('_', '-'), str(getattr(args, field))]
    return command


def adb_command(adb, record, *parts, check=True):
    command = [adb, '-s', 'emulator-5554', *parts]
    row = dict(command=command, startedAtMonotonicNanos=time.monotonic_ns())
    record.setdefault('commands', []).append(row)
    try:
        result = subprocess.run(command, capture_output=True, timeout=180 if parts[0] == 'install' else 30)
        row.update(exitCode=result.returncode, stdout=result.stdout.decode('utf-8', 'strict'), stderr=result.stderr.decode('utf-8', 'strict'))
        if check:
            require(result.returncode == 0, 'Device command failed: ' + ' '.join(parts[:3]))
        return result
    except subprocess.TimeoutExpired as error:
        row.update(timedOut=True, stdout=(error.stdout or b'').decode('utf-8', 'replace'), stderr=(error.stderr or b'').decode('utf-8', 'replace'))
        raise
    finally:
        row['completedAtMonotonicNanos'] = time.monotonic_ns()


def device(adb, record):
    commands = [('bootId', ('shell', 'cat', '/proc/sys/kernel/random/boot_id')),
                ('fingerprint', ('shell', 'getprop', 'ro.build.fingerprint')),
                ('qemu', ('shell', 'getprop', 'ro.kernel.qemu')),
                ('bootCompleted', ('shell', 'getprop', 'sys.boot_completed'))]
    value = {name: adb_command(adb, record, *parts).stdout.decode().strip() for name, parts in commands}
    require(re.fullmatch('[0-9a-f-]{36}', value['bootId']) and value['fingerprint']
            and value['qemu'] == '1' and value['bootCompleted'] == '1', 'Live pinned emulator identity unavailable')
    return value


def install_role(adb, record, apk):
    installed = adb_command(adb, record, 'shell', 'pm', 'path', 'local.pocketchat.test', check=False)
    require(installed.returncode in (0, 1) and not installed.stderr.strip(), 'Package query failed')
    if installed.stdout.strip():
        require(installed.returncode == 0 and all(line.startswith(b'package:/data/app/') for line in installed.stdout.splitlines()), 'Unexpected installed package path')
        adb_command(adb, record, 'uninstall', 'local.pocketchat.test')
    adb_command(adb, record, 'install', str(apk))


def gesture_metrics(raw, role):
    clock = raw['ownedClockObservation']
    require(clock['diagnosticOnly'] is True and clock['timingPerturbationPossible'] is True
            and all(type(clock[key]) is int for key in ('dropped', 'capacity', 'cpuObservationErrors', 'uptimeObservationErrors'))
            and clock['dropped'] == 0 and clock['capacity'] == 21
            and len(clock['slots']) == 21 and clock['cpuObservationErrors'] == 0
            and clock['uptimeObservationErrors'] == 0, 'Incomplete owned-clock observation')
    wanted = 0 if role == 'A' else -4
    require(all(type(clock[phase]['priority']) is int and clock[phase]['priority'] == wanted
                and clock[phase]['tid'] == raw['driverPid'] for phase in ('before', 'after')), 'Actual owned-thread priority differs')
    if role == 'B':
        priority = raw['ownedPriorityExperiment']
        require(all(priority.get(key) is True for key in ('experimentalOnly', 'attempted', 'applied', 'restoreAttempted', 'restoreVerified')),
                'Owned priority application/restoration incomplete')
        for key, value in dict(originalPriority=0, requestedPriority=-4, actualAppliedPriority=-4,
                               actualRestoredPriority=0, tid=raw['driverPid'], pid=raw['driverPid'], uid=2000).items():
            require(type(priority.get(key)) is int and priority[key] == value, 'Owned priority identity/value differs: ' + key)
        require(type(priority['applyUptimeMs']) is int and type(priority['restoreUptimeMs']) is int
                and priority['applyUptimeMs'] <= raw['readyUptimeMs'] <= raw['trace']['startUptimeMs']
                and clock['after']['uptimeMs'] <= priority['restoreUptimeMs'] <= raw['finishedUptimeMs'], 'Priority scope was not outside the fixed trace')
    trace = raw['trace']['events']
    require(len(trace) == 21, 'Exactly 21 original events required')
    lateness = []
    for index, (slot, event) in enumerate(zip(clock['slots'], trace)):
        fields = ('index', 'plannedUptimeMs', 'untilEnteredUptimeMs', 'requestedSleepMs',
                  'threadCpuBeforeNs', 'untilReturnedUptimeMs', 'threadCpuAfterNs', 'nextNowUptimeMs')
        require(all(type(slot.get(key)) is int for key in fields) and slot['index'] == index,
                'Actual typed slot evidence required')
        require(slot['plannedUptimeMs'] == event['plannedUptimeMs']
                and slot['requestedSleepMs'] == slot['plannedUptimeMs'] - slot['untilEnteredUptimeMs']
                and slot['untilEnteredUptimeMs'] <= slot['untilReturnedUptimeMs'] <= slot['nextNowUptimeMs'] <= event['eventTime'] <= event['callStartUptimeMs']
                and 0 <= slot['threadCpuBeforeNs'] <= slot['threadCpuAfterNs'], 'Owned wait/clock/event chain differs')
        late = event['callStartUptimeMs'] - event['plannedUptimeMs']
        require(type(late) is int and 0 <= late <= 30, 'Original fixed input slot exceeded')
        lateness.append(late)
    return dict(maxLatenessMs=max(lateness), latenessMs=lateness, ownedPriority=wanted,
                definition='Actual original injection callStartUptimeMs minus plannedUptimeMs; terminal synchronous UP completion is not slot lateness.')


def role_evidence(directory, expected, role, root):
    """Verify original bytes without requiring or downloading the large APK."""
    outcome = strict_json((directory / 'native-input-clock-outcome.json').read_bytes())
    require(outcome.get('status') == 'passed' and outcome.get('exitCode') == 0
            and outcome.get('diagnosticOnly') is True and outcome.get('applicationAcceptance') is False
            and outcome.get('releaseAcceptance') is False, 'Original focused flow failed or has wrong scope')
    for key in ('sourceCommit', 'sourceTree', 'runId', 'runAttempt'):
        require(outcome.get(key) == expected[key], 'Original outcome identity differs: ' + key)
    require(outcome['launcherEnvironment'].get('restorationVerified') is True
            and len(outcome['workloads']) == 1 and outcome['workloads'][0]['invocationCount'] == 1
            and outcome['workloads'][0]['exitCode'] == 0, 'Original workload/launcher evidence incomplete')
    report = strict_json((directory / 'gecko-performance-results.json').read_bytes())
    side = strict_json((directory / 'gecko-performance-build-identity.json').read_bytes())
    require(report.get('status') == 'passed' and side['runnerExitCode'] == 0
            and side['invocationCount'] == 1 and side['before'] == side['after']
            and side['rawReportUnmodified'] is True and side['actualInstalledApkRead'] is True
            and side['rawReportSha256'] == digest(directory / 'gecko-performance-results.json'), 'Original performance/installed evidence failed')
    for key in ('sourceCommit', 'sourceTree', 'runId', 'runAttempt', 'integrationApkSha256'):
        require(side[key] == outcome[key], 'Sidecar identity differs')
    reader = lambda source, path: git(root, 'show', source + ':' + path)
    sdk_path = directory / 'sdk-build-receipt.json'
    build_path = directory / 'caret-apk-build-receipt.json'
    require(digest(build_path) == outcome['buildReceiptSha256'] == side['buildReceiptSha256']
            and digest(sdk_path) == outcome['sdkReceiptSha256'] == side['sdkReceiptSha256'], 'Original SDK/build receipt bytes differ')
    manifest, manifest_hash = sdk_contract.selected_manifest(expected['sourceCommit'], reader)
    sdk = sdk_contract.validate_receipt(sdk_path.read_bytes(), manifest, manifest_hash,
                                        expected['sourceCommit'], expected['sourceTree'])
    require(all(sdk[key] == expected[key] for key in ('runId', 'runAttempt')), 'SDK built by another CI invocation')
    build = strict_json(build_path.read_bytes())
    embedded = embedded_identity(sdk, sdk_path)
    require(all(type(build.get(key)) is type(value) and build[key] == value for key, value in embedded.items())
            and build['integrationApkSha256'] == outcome['integrationApkSha256'], 'Build/SDK/AUT identity differs')
    installed = side['before']['commonInstalledIdentity']
    sdk_installed = sdk_contract.identity_from_receipt(sdk_path.read_bytes(), manifest, manifest_hash,
                                                      expected['sourceCommit'], expected['sourceTree'])
    require(installed['sdkBuildIdentity'] == sdk_installed
            and installed['apkSha256'] == outcome['integrationApkSha256']
            and installed['sourceCommit'] == expected['sourceCommit'] and installed['sourceTree'] == expected['sourceTree'],
            'Actual installed common SDK/source differs')
    verified = verify_qualification(directory, report, expected['sourceCommit'], reader,
        target_apk=outcome['integrationApkSha256'], expected_run=(expected['runId'], expected['runAttempt']))
    metrics = {}
    for row in report['nativeInputDriver']['receipts']:
        raw = strict_json((directory / row['file']).read_bytes())
        metrics[row['gesture']] = dict(gesture_metrics(raw, role), receiptSha256=digest(directory / row['file']))
    require(set(metrics) == set(GESTURES), 'Both original gestures required')
    return dict(status='passed', **expected, integrationApkSha256=outcome['integrationApkSha256'],
                driverApkSha256=verified['driverApkSha256'], metrics=metrics, originalDevice=report['device'],
                originalGestures=report['actualAndroidGestures'])


def run(args):
    plan = load_plan(args)
    target = args.out / 'comparison.json'
    require(not target.exists(), 'Refuse repeated comparison')
    record = dict(schema=1, status='failed', diagnosticOnly=True, applicationAcceptance=False,
                  releaseAcceptance=False, order=args.order, roles=[], **identity())
    failed = False
    try:
        original_device = device(args.adb, record)
        record['device'] = original_device
        for role in args.order:
            source = plan['roles'][role]
            a = role_args(Path(source['checkout']), args.adb)
            row = dict(role=role, **source, status='failed', invocationCount=0)
            record['roles'].append(row)
            validate_identity(a, row)
            row['deviceBefore'] = device(args.adb, row)
            require(row['deviceBefore'] == original_device, 'Device reboot/replacement before role')
            install_role(args.adb, row, a.integration_apk)
            preflight = [sys.executable, str(a.root / 'tools/gecko/prepare_emulator.py'), '--adb', args.adb,
                         '--serial', a.serial, '--apk', str(a.integration_apk)]
            with (args.out / (role + '-preflight.log')).open('xb') as log:
                pre = subprocess.run(preflight, cwd=a.root, stdout=log, stderr=subprocess.STDOUT)
            row['preflightExitCode'] = pre.returncode
            require(pre.returncode == 0, 'Original role preflight failed')
            adb_command(args.adb, row, 'shell', 'am', 'force-stop', 'local.pocketchat.test')
            adb_command(args.adb, row, 'shell', 'pm', 'clear', 'local.pocketchat.test')
            adb_command(args.adb, row, 'shell', 'pm', 'grant', 'local.pocketchat.test', 'android.permission.POST_NOTIFICATIONS')
            command = original_command(a)
            row.update(command=command, invocationCount=1, startedAtMonotonicNanos=time.monotonic_ns())
            with (args.out / (role + '-original-flow.log')).open('xb') as log:
                result = subprocess.run(command, cwd=a.root, stdout=log, stderr=subprocess.STDOUT)
            row.update(exitCode=result.returncode, completedAtMonotonicNanos=time.monotonic_ns())
            outcome = strict_json((a.out / 'native-input-clock-outcome.json').read_bytes())
            require(result.returncode in (0, 1) and outcome['launcherEnvironment'].get('restorationVerified') is True,
                    'Environment/restoration failed; do not proceed to another role')
            row['deviceAfter'] = device(args.adb, row)
            require(row['deviceAfter'] == original_device, 'Device reboot/replacement during role')
            if result.returncode == 0:
                expected = {key: row[key] for key in ('sourceCommit', 'sourceTree', 'runId', 'runAttempt')}
                try:
                    row['verified'] = role_evidence(a.out, expected, role, args.root)
                    row['status'] = 'passed'
                except Exception as error:
                    row.update(evidenceErrorType=type(error).__name__, evidenceError=str(error))
                    failed = True
            else:
                failed = True
        record['status'] = 'failed' if failed else 'passed'
    except BaseException as error:
        record.update(errorType=type(error).__name__, error=str(error))
    finally:
        write(target, record)
    return 0 if record['status'] == 'passed' else 1


def retain(args):
    """Only exact synthetic diagnostic files; never APKs, keys, or broad trees."""
    args.out.mkdir(parents=True, exist_ok=True)
    entries = []
    for role in 'AB':
        source = args.roles / role / 'work/gecko-integration'
        destination = args.out / role
        destination.mkdir(exist_ok=True)
        for path in sorted(source.glob('*')):
            if path.name not in EXACT and not any(fnmatch.fnmatchcase(path.name, pattern) for pattern in PATTERNS):
                continue
            require(path.is_file() and not path.is_symlink(), 'Unsafe diagnostic artifact')
            target = destination / path.name
            require(not target.exists(), 'Refuse replacement of retained raw bytes')
            shutil.copyfile(path, target)
            entries.append(dict(path=role + '/' + path.name, bytes=target.stat().st_size, sha256=digest(target)))
    bootstrap = []
    for name in EXACT:
        path = args.root / 'work/gecko-integration' / name
        if not path.exists():
            continue
        require(path.is_file() and not path.is_symlink(), 'Unsafe bootstrap artifact')
        target = args.out / 'bootstrap' / name
        require(not target.exists(), 'Refuse bootstrap evidence replacement')
        target.parent.mkdir(exist_ok=True)
        shutil.copyfile(path, target)
        bootstrap.append(dict(path='bootstrap/' + name, bytes=target.stat().st_size, sha256=digest(target)))
    write(args.out / 'raw-manifest.json', dict(schema=1, **identity(), files=entries, bootstrapFiles=bootstrap))


def decision(orders):
    require(set(orders) == {'AB', 'BA'}, 'Both predeclared orders required')
    rows, aggregates, eligible = [], [], True
    for order in ('AB', 'BA'):
        values = orders[order]
        require(set(values) == {'A', 'B'}, 'Both roles required without replacement')
        order_a, order_b = [], []
        for gesture in GESTURES:
            a, b = (values[role]['metrics'][gesture]['maxLatenessMs'] for role in 'AB')
            require(type(a) is int and type(b) is int and 0 <= a <= 30 and 0 <= b <= 30, 'Valid original slot lateness required')
            improved = b < a
            rows.append(dict(order=order, gesture=gesture, normalMaxLatenessMs=a, displayMaxLatenessMs=b,
                             noWorse=b <= a, strictlyImproved=improved))
            eligible &= b <= a
            order_a.append(a); order_b.append(b)
        strict = max(order_b) < max(order_a)
        eligible &= strict
        aggregates.append(dict(order=order, normalWorstMs=max(order_a), displayWorstMs=max(order_b), strictlyImproved=strict))
    return dict(eligibleForHumanConsideration=eligible, retainRecommended=eligible, comparisons=rows, orderAggregates=aggregates)


def decide(args):
    record = dict(schema=1, status='insufficient-or-failed-evidence', diagnosticOnly=True,
                  applicationAcceptance=False, releaseAcceptance=False, retainRecommended=False, **identity())
    try:
        roles = validate_sources(args.root, identity()['eventSourceCommit'])
        orders = {}
        for order in ('AB', 'BA'):
            folder = args.inputs / order
            result = strict_json((folder / 'comparison.json').read_bytes())
            require(result['order'] == order and result['status'] == 'passed'
                    and [row['role'] for row in result['roles']] == list(order), 'An order failed, was skipped or changed')
            require(all(result[key] == value for key, value in identity().items()), 'Foreign comparison run')
            manifest = strict_json((folder / 'raw-manifest.json').read_bytes())
            require(all(manifest[key] == value for key, value in identity().items()), 'Foreign raw archive')
            paths = set()
            bootstrap_paths = set()
            for entry in manifest['files'] + manifest['bootstrapFiles']:
                name = entry['path']
                require(re.fullmatch('(A|B|bootstrap)/[A-Za-z0-9_.-]+', name)
                        and name not in paths | bootstrap_paths, 'Unsafe or duplicate raw path')
                (bootstrap_paths if name.startswith('bootstrap/') else paths).add(name)
                path = folder / name
                require(path.is_file() and not path.is_symlink() and path.stat().st_size == entry['bytes']
                        and digest(path) == entry['sha256'], 'Original raw archive bytes differ')
            require(paths == {str(path.relative_to(folder)) for role in 'AB' for path in (folder / role).iterdir()}, 'Unindexed role evidence')
            require(bootstrap_paths == {str(path.relative_to(folder)) for path in (folder / 'bootstrap').iterdir()}
                    and {'bootstrap/' + name for name in ('android-emulator-package-results.json',
                         'android-system-image-results.json', 'android-platform-tools-results.json')} <= bootstrap_paths,
                    'Missing or unindexed pinned bootstrap evidence')
            orders[order] = {}
            for role in 'AB':
                row = next(row for row in result['roles'] if row['role'] == role)
                require(row['invocationCount'] == 1 and row['status'] == 'passed'
                        and row['deviceBefore'] == row['deviceAfter'] == result['device'], 'Role replay or device continuity missing')
                expected = dict(sourceCommit=roles[role]['sourceCommit'], sourceTree=roles[role]['sourceTree'],
                                runId=identity()['runId'], runAttempt=identity()['runAttempt'])
                orders[order][role] = role_evidence(folder / role, expected, role, args.root)
            require(orders[order]['A']['originalDevice'] == orders[order]['B']['originalDevice']
                    and orders[order]['A']['originalGestures'] == orders[order]['B']['originalGestures'],
                    'Actual original device geometry or requested gestures differ within pair')
        record.update(decision(orders), status='compared', orders=orders,
                      scope='Two opposite-order same-emulator pairs; N=2 orders on distinct cloud VMs, not statistical proof. Driver timing only. Even favorable results do not establish the previous miss cause or application speed.')
    except BaseException as error:
        record.update(errorType=type(error).__name__, error=str(error))
    write(args.out / 'priority-decision.json', record)
    return 0 if record['status'] == 'compared' else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('prepare', 'run', 'retain', 'decide'))
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--roles', type=Path)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--inputs', type=Path)
    parser.add_argument('--order', choices=('AB', 'BA'))
    parser.add_argument('--adb')
    args = parser.parse_args()
    args.root = args.root.resolve()
    args.roles = (args.roles or args.root / 'work/priority-roles').resolve()
    args.out = (args.out or args.root / 'work/priority-comparison').resolve()
    return {'prepare': prepare, 'run': run, 'retain': retain, 'decide': decide}[args.mode](args) or 0


if __name__ == '__main__':
    sys.exit(main())
