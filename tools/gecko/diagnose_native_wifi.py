#!/usr/bin/env python3
"""Observe an experimental Wi-Fi endpoint adapter under a fault or normal control."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import uuid

from diagnose_native_readiness import (
    SOURCE, BUILD_RUN, BUILD_ATTEMPT, APK, SETUP, StateObserver,
    require, digest, write_json, observed_text, post_command, post_tcp_probe,
)

CASES = {'fault-1': 'mobile-data-disabled', 'fault-2': 'mobile-data-disabled',
         'control-1': 'unchanged'}


def export_transport_trace(source, target):
    """Retain packet header metadata, never the transport logger's payload prefix."""
    with Path(source).open(errors='replace') as incoming, Path(target).open('w') as outgoing:
        for line in incoming:
            outgoing.write(re.sub(r'(\[[A-Z]{4}\].*?\(len=\d+\))[^\n]*',
                                  r'\1 [payload omitted]', line))


def scenario_command(adb, parts):
    """Bounded, recorded command outside the unchanged original setup invocation."""
    command = [str(adb), '-s', 'emulator-5556', *parts]
    row = {'command': command, 'outsideOriginalSetup': True,
           'startedMonotonicNs': time.monotonic_ns()}
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=4)
        row.update(exitCode=result.returncode, stdout=observed_text(result.stdout),
                   stderr=observed_text(result.stderr), timedOut=False)
    except subprocess.TimeoutExpired as error:
        row.update(exitCode=None, stdout=observed_text(error.stdout),
                   stderr=observed_text(error.stderr), timedOut=True)
    except OSError as error:
        row.update(exitCode=None, errorType=type(error).__name__, error=str(error))
    row['elapsedMs'] = (time.monotonic_ns() - row['startedMonotonicNs']) / 1000000
    return row


def scenario_snapshot(adb):
    nonce = uuid.uuid4().hex
    commands = [
        ['shell', 'settings', 'get', 'global', 'mobile_data'],
        ['shell', 'settings', 'get', 'global', 'mobile_data1'],
        ['emu', 'gsm', 'status'],
        ['shell', 'ip', '-4', '-o', 'addr', 'show'],
        ['shell', 'ip', '-4', 'route', 'show', 'table', 'all'],
        ['exec-out', 'content', 'read', '--uri',
         'content://local.pocketchat.test.network-preflight/default-network?runNonce=' + nonce],
    ]
    return {'runNonce': nonce, 'observations': [scenario_command(adb, parts) for parts in commands]}


def apply_scenario(adb, case, record):
    require(case in CASES, 'Unknown predeclared fault/control case')
    qemu = scenario_command(adb, ['shell', 'getprop', 'ro.kernel.qemu'])
    record['syntheticTargetCheck'] = qemu
    require(qemu.get('exitCode') == 0 and qemu.get('stdout', '').strip() == '1',
            'Fault precondition requires a confirmed synthetic emulator')
    record['beforePrecondition'] = scenario_snapshot(adb)
    record['preconditionMutationAttempted'] = CASES[case] == 'mobile-data-disabled'
    record['externalPrecondition'] = CASES[case]
    record['externalStateChangeVerified'] = None if record['preconditionMutationAttempted'] else False
    if record['preconditionMutationAttempted']:
        # One intentional synthetic network fault, never a hidden helper repair.
        mutation = scenario_command(adb, ['shell', 'svc', 'data', 'disable'])
        record['preconditionMutation'] = mutation
        record['preconditionCommandSucceeded'] = mutation.get('exitCode') == 0
    else:
        record['preconditionCommandSucceeded'] = None
    record['afterPrecondition'] = scenario_snapshot(adb)
    # Do not retry a rejected command or add another intervention to induce a failure.
    require(not record['preconditionMutationAttempted'] or record['preconditionCommandSucceeded'],
            'Single mobile-data fault command failed; case is not covered')


def target_coverage(native):
    """Classify observed coverage, never change any setup/acceptance outcome."""
    phases = {}
    for row in native.get('networkObservations', []):
        value = json.loads(row['raw'])
        phases.setdefault(row['phase'], []).append(value)
    initial = phases.get('before-network-configuration', [{}])[0]
    after = phases.get('after-setup-package-handling', [{}])[0]
    initial_wifi = initial.get('usable') is True and initial.get('transports') == ['wifi']
    no_default = (after.get('activeNetwork') == '' and after.get('activeNetworkAfter') == ''
                  and after.get('usable') is False and after.get('transports') == [])
    recovery = native.get('postSetupNetworkRecoveryRequired') is True
    return {'initialWifiUsable': initial_wifi, 'afterSetupHasNoDefaultNetwork': no_default,
            'originalNetworkRecoveryRequired': recovery,
            'targetPathCovered': initial_wifi and no_default and recovery,
            'equivalentToOriginalFailure': False,
            'scope': 'Observed network-state path only; external data disabling may also remove eth0/.15.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-root', type=Path, required=True)
    parser.add_argument('--adb', type=Path, required=True)
    parser.add_argument('--monitor', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--case', choices=list(CASES), required=True)
    args = parser.parse_args()
    root, out, adb = args.baseline_root.resolve(), args.out.resolve(), args.adb.resolve()
    out.mkdir(parents=True, exist_ok=True)
    require(not (out / 'readiness-results.json').exists(), 'Never replace an existing diagnostic')
    record = {'schema': 1, 'status': 'in_progress', 'case': args.case, 'scenario': CASES[args.case],
              'predeclaredCases': list(CASES), 'sourceCommit': SOURCE,
              'originalBuildRunId': BUILD_RUN, 'originalBuildRunAttempt': BUILD_ATTEMPT,
              'diagnosticRunId': os.environ.get('GITHUB_RUN_ID', ''),
              'diagnosticRunAttempt': os.environ.get('GITHUB_RUN_ATTEMPT', ''),
              'originalWorkloadInvoked': False, 'actualGeckoExecution': False,
              'applicationAcceptance': False, 'releaseAcceptance': False,
              'setupInvocations': 0, 'setupReplayed': False,
              'coverageClassification': 'not_evaluated',
              'targetPathCoverage': {'targetPathCovered': False, 'notEvaluated': True},
              'equivalentToOriginalFailure': False,
              'experimentalEnvironmentAdapter': True,
              'scope': 'Experimental Wi-Fi endpoint with synthetic fault/control; no original setup or application acceptance.'}
    write_json(out / 'readiness-results.json', record)
    try:
        def git(*parts):
            return subprocess.check_output(['git', *parts], cwd=root, text=True, timeout=15).strip()
        require(git('rev-parse', 'HEAD') == SOURCE and not git('status', '--porcelain'),
                'Exact clean frozen baseline checkout required')
        index_path = root / 'work/gecko-integration/ci-build-index.json'
        index = json.loads(index_path.read_text())
        require(index['sourceCommit'] == SOURCE and index['sourceTree'] == git('rev-parse', 'HEAD^{tree}')
                and index['runId'] == BUILD_RUN and index['runAttempt'] == BUILD_ATTEMPT,
                'Restored original build identity differs')
        rows = [row for row in index['files'] if row['path'] == APK]
        require(len(rows) == 1, 'Exactly one original integration APK required')
        apk = root / APK
        require(apk.stat().st_size == rows[0]['bytes'] and digest(apk) == rows[0]['sha256'],
                'Original compiled integration APK bytes differ')
        setup = root / SETUP
        original_bytes = subprocess.check_output(['git', 'show', SOURCE + ':' + SETUP], cwd=root, timeout=15)
        require(setup.read_bytes() == original_bytes, 'Original setup script was changed')
        native_report = root / 'work/gecko-integration/native-adb-setup-results.json'
        require(not native_report.exists(), 'Original setup has already been invoked')
        record.update(sourceTree=index['sourceTree'], apkSha256=rows[0]['sha256'],
                      apkBytes=rows[0]['bytes'], originalSetupSha256=digest(setup),
                      buildIndexSha256=digest(index_path), diagnosticToolSha256=digest(__file__))
        apply_scenario(adb, args.case, record)
        adapter_path = Path(__file__).with_name('prepare_native_wifi.py')
        record['experimentalHelperSha256'] = digest(adapter_path)
        record['experimentalHelperSourceCommit'] = os.environ.get('GITHUB_SHA', '')
        spec = importlib.util.spec_from_file_location('experimental_wifi_native_setup', adapter_path)
        original = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(original)
        saved_run, saved_argv = subprocess.run, sys.argv
        observer = StateObserver(saved_run, str(adb))
        try:
            subprocess.run = observer
            sys.argv = [str(adapter_path), '--baseline-root', str(root), '--adb', str(adb), '--apk', str(apk), '--monitor', str(args.monitor.resolve())]
            record['setupInvocations'] = 1
            original.main()
            record['experimentalSetupOutcome'] = 'passed'
        except Exception as error:
            record.update(experimentalSetupOutcome='failed', experimentalErrorType=type(error).__name__,
                          experimentalError=str(error))
        finally:
            subprocess.run, sys.argv = saved_run, saved_argv
            record['nativeGetStateObservations'] = observer.rows
        require(native_report.is_file(), 'Original setup did not write its required receipt')
        native = json.loads(native_report.read_text())
        require(native['sourceCommit'] == SOURCE and native['originalWorkloadInvoked'] is False
                and native['actualGeckoExecution'] is False and native['applicationAcceptance'] is False,
                'Original receipt identity or diagnostic-only scope differs')
        require(native.get('experimentalEnvironmentAdapter') is True
                and native.get('adapterSha256') == record['experimentalHelperSha256']
                and native.get('adapterSourceCommit') == record['experimentalHelperSourceCommit'],
                'Experimental adapter identity differs')
        require(native['status'] == record['experimentalSetupOutcome'], 'Experimental outcome was not preserved')
        shutil.copyfile(native_report, out / native_report.name)
        record['experimentalSetupReceiptSha256'] = digest(native_report)
        record['targetPathCoverage'] = target_coverage(native)
        record['coverageClassification'] = ('covered' if record['targetPathCoverage']['targetPathCovered'] else 'not_covered')
        # These commands follow the frozen original outcome. None can qualify,
        # retry or repair that outcome; they inspect only this empty CI emulator.
        commands = [('devices', '-l'), ('-s', 'emulator-5556', 'get-state'),
                    ('-s', 'emulator-5556', 'shell', 'getprop', 'init.svc.adbd'),
                    ('-s', 'emulator-5556', 'shell', 'getprop', 'service.adb.tcp.port'),
                    ('-s', 'emulator-5556', 'shell', 'ss', '-ltn'),
                    ('-s', 'emulator-5556', 'shell', 'ip', '-4', '-o', 'addr', 'show'),
                    ('-s', 'emulator-5556', 'shell', 'ip', '-4', 'route'),
                    ('-s', 'emulator-5554', 'get-state')]
        if native.get('confirmedQemu') is True:
            record['postSetupObservations'] = [post_command(adb, list(parts)) for parts in commands]
            try:
                # Do not send an ADB header to an unrelated local listener if
                # setup stopped before establishing this exact QEMU forward.
                original.verify_forward(native.get('afterUsernet', ''))
            except ValueError:
                record['postSetupTcpProbeSkipped'] = 'Experimental adapter did not prove the exact Wi-Fi forwarding rule'
            else:
                record['postSetupTcpProbe'] = post_tcp_probe()
            record['postProbeDevices'] = post_command(adb, ['devices', '-l'])
            record['afterOriginalOutcome'] = scenario_snapshot(adb)
        else:
            record['postSetupObservationSkipped'] = 'Experimental adapter did not confirm the synthetic emulator'
        record['status'] = 'observed'
    except Exception as error:
        record.update(status='diagnostic_failed', errorType=type(error).__name__, error=str(error))
        raise
    finally:
        write_json(out / 'readiness-results.json', record)
    print(json.dumps({'status': record['status'], 'case': args.case, 'scenario': CASES[args.case],
                      'experimentalSetupOutcome': record['experimentalSetupOutcome'],
                      'nativeGetStateObservations': len(record['nativeGetStateObservations']),
                      'applicationAcceptance': False, 'originalWorkloadInvoked': False}))
    # The complete diagnostic retains setup failure as a failed CI step, even
    # if a later raw TCP connection or state observation happens to succeed.
    return 0 if record['experimentalSetupOutcome'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
