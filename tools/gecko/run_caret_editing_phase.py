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


def run_workloads(args, record):
    failed = False
    for label, command in zip(('original-performance-wrapper', 'caret-compatibility'), editing_commands(args)):
        row = dict(name=label, command=command, invocationCount=1, startedAtMonotonicNanos=time.monotonic_ns())
        record.setdefault('workloads', []).append(row)
        try:
            result = subprocess.run(command, cwd=args.root, check=False)
            row['exitCode'] = result.returncode
            require(result.returncode >= 0, 'Editing fixture process was terminated; do not launch another workload')
            failed |= result.returncode != 0
        finally:
            row['completedAtMonotonicNanos'] = time.monotonic_ns()
    return 1 if failed else 0


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
        exit_code = guard.run(lambda: run_workloads(args, record))
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
