#!/usr/bin/env python3
"""Run the original performance wrapper once, under its normal launcher guard.

This focused diagnostic never supplies release qualification or replaces any
input sample. Raw original workload files are retained without rewriting.
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
from run_caret_editing_phase import editing_commands

ROOT = Path(__file__).resolve().parents[2]
OUTCOME = 'native-input-clock-outcome.json'


def run_once(args, record):
    require(not record.get('workloads'), 'Focused diagnostic cannot replay its workload')
    command = editing_commands(args)[0]
    row = dict(name='original-performance-wrapper', command=command, invocationCount=1,
               startedAtMonotonicNanos=time.monotonic_ns())
    record['workloads'] = [row]
    try:
        result = subprocess.run(command, cwd=args.root, check=False)
        row['exitCode'] = result.returncode
        require(result.returncode >= 0, 'Original performance process was terminated')
        return 0 if result.returncode == 0 else 1
    finally:
        row['completedAtMonotonicNanos'] = time.monotonic_ns()


def validate_identity(args, record):
    source = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=args.root, text=True).strip()
    tree = subprocess.check_output(['git', 'rev-parse', 'HEAD^{tree}'], cwd=args.root, text=True).strip()
    require(not subprocess.check_output(['git', 'status', '--porcelain'], cwd=args.root, text=True).strip(),
            'Focused diagnostic requires clean committed source')
    sdk = validate_sdk_receipt(args.sdk_receipt, args.sdk_aar, args.root, args.official_sdk_aar)
    expected = embedded_identity(sdk, args.sdk_receipt)
    build = strict_json(args.build_receipt.read_bytes())
    require(all(build.get(key) == value for key, value in expected.items())
            and sdk['sourceCommit'] == source and sdk['sourceTree'] == tree,
            'Focused diagnostic source/run/SDK differs')
    require(build['integrationApkSha256'] == digest(args.integration_apk)
            and build['releaseApkSha256'] == digest(args.release_apk), 'Actual compiled APK bytes differ')
    require(build['runId'] == os.environ['GITHUB_RUN_ID']
            and build['runAttempt'] == os.environ.get('GITHUB_RUN_ATTEMPT', '1'), 'CI invocation differs')
    record.update(sourceCommit=source, sourceTree=tree, runId=build['runId'], runAttempt=build['runAttempt'],
                  buildReceiptSha256=digest(args.build_receipt), sdkReceiptSha256=digest(args.sdk_receipt),
                  integrationApkSha256=build['integrationApkSha256'], releaseApkSha256=build['releaseApkSha256'])
    return dict(expected, sourceTree=tree, integrationApkSha256=build['integrationApkSha256'])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adb', required=True)
    parser.add_argument('--serial', required=True, choices=[SERIAL])
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--out', type=Path, required=True)
    for name in ('build-receipt', 'sdk-receipt', 'sdk-aar', 'official-sdk-aar', 'integration-apk', 'release-apk'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args(argv)
    args.root, args.out = args.root.resolve(), args.out.resolve()
    require(args.out == args.root / 'work/gecko-integration', 'Original output directory required')
    args.out.mkdir(parents=True, exist_ok=True)
    target = args.out / OUTCOME
    require(not target.exists() and not target.is_symlink(), 'Refuse a repeated diagnostic invocation')
    for name in ('gecko-performance-results.json', 'gecko-performance-build-identity.json'):
        path = args.out / name
        require(not path.exists() and not path.is_symlink(), 'Refuse retained original workload evidence')
    record = dict(schema=1, status='failed', phaseStatus='not-started', diagnosticOnly=True,
                  applicationAcceptance=False, releaseAcceptance=False, physicalPhoneAcceptance=False,
                  scope='One original performance invocation with owned driver-clock observation; no caret workload, release gates, or retry. Observation may affect scheduling.')
    code, handlers = 2, {}
    def interrupted(signum, unused):
        raise KeyboardInterrupt('Focused diagnostic interrupted by signal ' + str(signum))
    for signum in (signal.SIGTERM, signal.SIGINT):
        handlers[signum] = signal.signal(signum, interrupted)
    try:
        identity = validate_identity(args, record)
        def adb(*parts):
            return subprocess.run([args.adb, '-s', args.serial, *parts], check=True, text=True,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=8).stdout.strip()
        guard_record = {}
        record['launcherEnvironment'] = guard_record
        guard = LauncherGuard(adb=adb, identity=identity, record=guard_record,
                              nonce=uuid.uuid4().hex, serial=args.serial)
        code = guard.run(lambda: run_once(args, record))
        record.update(status='passed' if code == 0 else 'failed',
                      phaseStatus='workload-completed-restored' if code == 0 else 'workload-failed-restored')
    except BaseException as error:
        record.update(status='failed', phaseStatus='fatal-environment-or-invocation-failure',
                      errorType=type(error).__name__, error=str(error))
        code = 2
    finally:
        for signum, handler in handlers.items():
            signal.signal(signum, handler)
        record['exitCode'] = code
        # Exclusive outcome creation never modifies original workload receipts.
        with target.open('x') as stream:
            json.dump(record, stream, indent=2); stream.write('\n')
    print(json.dumps(dict(diagnosticOnly=True, applicationAcceptance=False, releaseAcceptance=False,
                          phaseStatus=record['phaseStatus'], exitCode=code)))
    return code


if __name__ == '__main__':
    sys.exit(main())
