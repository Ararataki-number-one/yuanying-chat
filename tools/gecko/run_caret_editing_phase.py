#!/usr/bin/env python3
"""Run the two unchanged editing commands inside a restored emulator guard.

Exit 1 means a workload failed after verified cleanup. Any other failure exits
2 so the workflow must stop before its later real HOME/background checks.
"""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import uuid

from caret_build_identity import digest, embedded_identity, require, strict_json, validate_sdk_receipt
from caret_launcher_guard import LauncherGuard, SERIAL

ROOT = Path(__file__).resolve().parents[2]


def editing_commands(args):
    root, out = args.root.resolve(), args.out.resolve()
    performance = [sys.executable, str(root / 'tests/gecko/run_caret_bound_performance.py'),
        '--adb', args.adb, '--serial', args.serial, '--root', str(root), '--out', str(out),
        '--build-receipt', str(args.build_receipt), '--sdk-receipt', str(args.sdk_receipt),
        '--sdk-aar', str(args.sdk_aar), '--official-sdk-aar', str(args.official_sdk_aar),
        '--integration-apk', str(args.integration_apk)]
    caret = [sys.executable, str(root / 'tests/gecko/run_gecko_caret_compat.py'), '--normal-acceptance',
        '--adb', args.adb, '--serial', args.serial, '--root', str(root), '--out', str(out / 'caret-compat'),
        '--sdk-receipt', str(args.sdk_receipt), '--build-receipt', str(args.build_receipt),
        '--sdk-aar', str(args.sdk_aar), '--official-sdk-aar', str(args.official_sdk_aar),
        '--integration-apk', str(args.integration_apk), '--release-apk', str(args.release_apk)]
    return performance, caret


def run_workloads(args, record, verify_caret_environment=None):
    failed = False
    for index, (label, command) in enumerate(zip(('original-performance-wrapper', 'caret-compatibility'), editing_commands(args))):
        def invoke():
            row = dict(name=label, command=command, invocationCount=1, startedAtMonotonicNanos=time.monotonic_ns())
            record.setdefault('workloads', []).append(row)
            try:
                result = subprocess.run(command, cwd=args.root, check=False)
                row['exitCode'] = result.returncode
                require(result.returncode >= 0, 'Editing fixture process was terminated; do not launch another workload')
                return result.returncode
            finally:
                row['completedAtMonotonicNanos'] = time.monotonic_ns()
        code = invoke()
        if index == 1 and verify_caret_environment is not None:
            # The runner selects its IME after its final package reset and must
            # restore it before this phase permits the later real HOME suites.
            verify_caret_environment()
        failed |= code != 0
    return 1 if failed else 0


def verify_caret_ime_environment(path, identity):
    from caret_ime_guard import COMPONENT, IDENTITY_FIELDS
    require(path.is_file(), 'Missing actual controlled IME restoration receipt; later HOME suites must not run')
    value = strict_json(path.read_text())
    require(type(value.get('schema')) is int and value['schema'] == 1
            and value.get('exactFixtureComponent') == COMPONENT
            and value.get('serial') == SERIAL and type(value.get('user')) is int and value['user'] == 0,
            'Controlled IME receipt component/device differs')
    bound = value.get('identity')
    require(isinstance(bound, dict) and all(bound.get(key) == identity.get(key) for key in IDENTITY_FIELDS),
            'Controlled IME restoration receipt source/run/APK/SDK differs')
    require(value.get('restorationVerified') is True and not value.get('restoreError')
            and not value.get('fatal') and all(isinstance(value.get(key), dict) and value[key]
                for key in ('initial', 'during', 'restored')),
            'Exact IME restoration was not proved; later HOME suites must not run')
    require(value.get('failureStage') in (None, 'workload')
            and value.get('errorType') not in ('KeyboardInterrupt', 'SystemExit'),
            'Controlled IME preflight, exit status, or interruption failed; later HOME suites must not run')
    state_keys = ('settings', 'selectedComponent', 'enabledComponents', 'actualEnabledComponents',
                  'registeredComponents', 'actualSelectedComponent')
    require(all(key in value['initial'] and key in value['restored']
                and value['initial'][key] == value['restored'][key] for key in state_keys),
            'Actual selected/enabled IME and raw secure settings were not exactly restored')
    phases = [value.get(key) for key in ('prepareStartedAtMonotonicNanos', 'preparedAtMonotonicNanos',
              'workloadStartedAtMonotonicNanos', 'workloadCompletedAtMonotonicNanos',
              'restoreStartedAtMonotonicNanos', 'restoredAtMonotonicNanos')]
    require(all(type(stamp) is int and stamp > 0 for stamp in phases) and phases == sorted(phases)
            and value.get('mutationAttempted') is True
            and type(value.get('workloadInvocationCount')) is int and value['workloadInvocationCount'] == 1,
            'Controlled IME phase/workload receipt incomplete')
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adb', required=True)
    parser.add_argument('--serial', required=True, choices=[SERIAL])
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--out', type=Path, required=True)
    for name in ('build-receipt', 'sdk-receipt', 'sdk-aar', 'official-sdk-aar', 'integration-apk', 'release-apk'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    args.root, args.out = args.root.resolve(), args.out.resolve()
    args.out.mkdir(parents=True, exist_ok=True)
    nonce = uuid.uuid4().hex
    record = dict(schema=1, status='failed', phaseStatus='failed', runNonce=nonce,
                  runId=os.environ.get('GITHUB_RUN_ID'), runAttempt=os.environ.get('GITHUB_RUN_ATTEMPT', '1'),
                  applicationAcceptance=False,
                  physicalPhoneAcceptance=False, scope='Temporary launcher-only environment guard; no input oracles changed.')
    exit_code = 2
    handlers = {}
    def interrupted(signum, unused):
        raise KeyboardInterrupt('Editing phase interrupted by signal ' + str(signum))
    for signum in (signal.SIGTERM, signal.SIGINT):
        handlers[signum] = signal.signal(signum, interrupted)
    try:
        source = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=args.root, text=True).strip()
        tree = subprocess.check_output(['git', 'rev-parse', 'HEAD^{tree}'], cwd=args.root, text=True).strip()
        record.update(sourceCommit=source, sourceTree=tree)
        require(not subprocess.check_output(['git', 'status', '--porcelain'], cwd=args.root, text=True).strip(),
                'Editing phase requires clean committed source')
        sdk = validate_sdk_receipt(args.sdk_receipt, args.sdk_aar, args.root, args.official_sdk_aar)
        expected = embedded_identity(sdk, args.sdk_receipt)
        build = strict_json(args.build_receipt.read_text())
        require(all(build.get(key) == value for key, value in expected.items())
                and sdk['sourceCommit'] == source and sdk['sourceTree'] == tree,
                'Editing phase source/run/SDK identity differs')
        require(build['integrationApkSha256'] == digest(args.integration_apk)
                and build['releaseApkSha256'] == digest(args.release_apk), 'Editing phase actual compiled APK bytes differ')
        require(build['runId'] == os.environ['GITHUB_RUN_ID']
                and build['runAttempt'] == os.environ.get('GITHUB_RUN_ATTEMPT', '1'), 'Editing phase CI invocation differs')
        identity = dict(expected, sourceTree=tree, integrationApkSha256=build['integrationApkSha256'])
        def adb(*parts):
            return subprocess.run([args.adb, '-s', args.serial, *parts], check=True,
                                  text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=8).stdout.strip()
        guard = LauncherGuard(adb=adb, identity=identity, record=record, nonce=nonce, serial=args.serial)
        ime_path = args.out / 'caret-compat/caret-ime-environment.json'
        require(not ime_path.exists(), 'Refuse stale IME guard receipt before the once-only fixture')
        def verify_ime_environment():
            ime = verify_caret_ime_environment(ime_path, identity)
            record['imeEnvironmentReceipt'] = str(ime_path.relative_to(args.out))
            record['imeEnvironmentReceiptSha256'] = digest(ime_path)
            record['imeRestorationVerified'] = ime['restorationVerified']
        exit_code = guard.run(lambda: run_workloads(args, record, verify_ime_environment))
        record['phaseStatus'] = 'passed' if exit_code == 0 else 'workload-failed-restored'
    except BaseException as error:
        record.update(phaseStatus='fatal-environment-failure', phaseErrorType=type(error).__name__, phaseError=str(error))
        exit_code = 2
    finally:
        for signum, handler in handlers.items():
            signal.signal(signum, handler)
        target = args.out / 'editing-phase-environment.json'
        temporary = target.with_suffix('.partial')
        temporary.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
        temporary.replace(target)
    print(json.dumps(dict(phaseStatus=record['phaseStatus'], restorationVerified=record.get('restorationVerified', False),
                          applicationAcceptance=False)))
    return exit_code


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as error:
        # An archival/programming failure is never an ordinary workload rc1.
        print('Fatal editing-phase coordinator error: ' + str(error), file=sys.stderr)
        sys.exit(2)
