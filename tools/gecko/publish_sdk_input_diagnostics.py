#!/usr/bin/env python3
"""Publish all ten synthetic SDK transaction trials; never a release APK or account data."""
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / 'work/gecko-input-diagnostics'
BRANCH = 'apk/gecko-synthetic-caret-candidate'
PRODUCTION_SOURCE = 'e4a4a08202cf50ce60d36dd86a625366de9bb2f4'
TRIALS = tuple(range(1, 11))
ARTIFACTS = tuple((OUT, name) for name in (
    'build.log', 'input-test.log', 'emulator.log', 'input-diagnostic-screen.png',
    'sdk-instrumentation-receipt.json', 'hardware-candidate-receipt.json', 'observer-free-build.log',
    'observer-free/runner.log', 'observer-free/gecko-performance-results.json',
    'observer-free/gecko-performance-failure-log.txt', 'observer-free/gecko-performance-screen.png',
    'compatibility/runner.log', 'compatibility/gecko-caret-compat-results.json',
    'compatibility/gecko-caret-compat-failure-log.txt', 'compatibility/gecko-caret-compat-screen.png',
)) + tuple((OUT, f'attempt-{trial}/{name}') for trial in TRIALS for name in (
    'status.json', 'runner.log', 'gecko-performance-results.json',
    'gecko-performance-failure-log.txt', 'gecko-performance-screen.png', 'screen.png',
))


def git(*arguments, env=None):
    return subprocess.check_output(['git', *arguments], cwd=ROOT, env=env, text=True).strip()


def stage_evidence(source, run_id, run_attempt, outcomes):
    if not re.fullmatch(r'[0-9a-f]{40}', source):
        raise ValueError('Expected exact checked-out diagnostic source')
    if not re.fullmatch(r'[0-9]+', run_id) or not re.fullmatch(r'[0-9]+', run_attempt):
        raise ValueError('Expected GitHub run identity')
    if any(value not in ('success', 'failure', 'cancelled', 'skipped') for value in outcomes.values()):
        raise ValueError('Invalid diagnostic step outcome')
    stage = OUT / 'public-sdk'
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    manifest = {
        'sourceCommit': source, 'productionSourceCommit': PRODUCTION_SOURCE,
        'runId': run_id, 'runAttempt': run_attempt,
        'diagnosticOnly': True, 'releaseAcceptance': False, 'partial': os.environ.get('SDK_DIAGNOSTIC_PARTIAL') == '1',
        'observation': 'Per-action synthesized insertion candidate: ten identical single-burst diagnostics with actual input/output predicate and native writer activation, followed by original observer-free gate and actual soft-input compatibility.',
        'oldSdkComparison': {'sourceCommit': '8f61060f7968b6798060947009310fc1f14e69f1', 'evidenceCommit': '6eb6d06655bbda116db20975f7fcf70d874c7b70', 'trials': 10, 'failedTrials': [1]},
        'infrastructure': {'gradleDaemonStoppedBeforeEmulator': True, 'gradleDaemonStoppedAfterBareBuild': True,
                           'fixedTrials':10, 'automaticTrialRetries':0, 'originalInputBurstUnchanged':True},
        'firstScopedCandidate': {'sourceCommit': '860a6777ab4dd09d110f603de8754f2e76fefc50', 'evidenceCommit': '5768483fc256edad73491e024e0e7328bb9a1f17', 'trials':10, 'failedTrials':[2], 'failure':'ADB logcat exited255; no SDK report in trial2', 'activated':False},
        'observerFreeOriginalGate': {}, 'compatibility': {},
        'stepOutcomes': outcomes, 'expectedTrials': list(TRIALS),
        'artifacts': [], 'warnings': [], 'attempts': [], 'reports': {},
    }
    for directory, name in ARTIFACTS:
        original = directory / name
        if original.is_symlink() or original.parent.is_symlink() or not original.is_file():
            continue
        data = original.read_bytes()
        if name in ('observer-free/gecko-performance-results.json', 'compatibility/gecko-caret-compat-results.json'):
            try:
                report = json.loads(data)
                if report.get('sourceCommit') != source:
                    raise ValueError('Observer-free or compatibility report belongs to another source')
                if name.startswith('observer-free/'):
                    if any(report.get(key) is not False for key in ('diagnosticOnly', 'inputSdkDiagnosticsEnabled', 'inputNativeDiagnosticsEnabled', 'inputDiagnosticsEnabled')):
                        raise ValueError('Original gate unexpectedly used diagnostic instrumentation')
                    if report.get('actualSdkInputTrace') or report.get('actualNativeInputTrace') or report.get('actualInputEvaluationTrace'):
                        raise ValueError('Original gate contains observer events')
                    manifest['observerFreeOriginalGate'] = {'sourceCommit': source, 'status': report.get('status'), 'checkCount': report.get('checkCount'), 'actualAndroidExecution': report.get('actualAndroidExecution'), 'actualGeckoExecution': report.get('actualGeckoExecution'), 'diagnosticOnly': False}
                else:
                    manifest['compatibility'] = {'sourceCommit': source, 'status': report.get('status'), 'checkCount': report.get('checkCount'), 'actualAndroidExecution': report.get('actualAndroidExecution'), 'actualGeckoExecution': report.get('actualGeckoExecution')}
            except (ValueError, TypeError, AttributeError) as error:
                manifest['warnings'].append(name + ': ' + str(error))
                continue
        elif name.endswith('/status.json') or name.endswith('/gecko-performance-results.json'):
            try:
                report = json.loads(data)
                if report.get('sourceCommit') != source:
                    raise ValueError('Report belongs to another source')
                if name.endswith('/status.json'):
                    trial = int(name.split('/')[0].removeprefix('attempt-'))
                    if report.get('runId') != run_id or report.get('runAttempt') != run_attempt or report.get('trial') != trial or report.get('diagnosticOnly') is not True:
                        raise ValueError('Attempt belongs to another run or trial')
                    manifest['attempts'].append(report)
                else:
                    if report.get('diagnosticOnly') is not True or report.get('inputSdkDiagnosticsEnabled') is not True or report.get('inputNativeDiagnosticsEnabled') is not False or report.get('inputDiagnosticsEnabled') is not False:
                        raise ValueError('Expected same-class SDK instrumentation only; no native proxies or added JS instrumentation')
                    rows = report.get('actualSdkInputTrace', [])
                    summary = report.get('actualSdkInputSummary') or {}
                    complete = (bool(rows) and summary.get('overflow') == 0
                                and summary.get('reserved') == summary.get('published') == summary.get('rowCount') == len(rows)
                                and all(isinstance(row, list) and len(row) == 14 for row in rows)
                                and [row[13] for row in rows] == list(range(len(rows))))
                    manifest['reports'][name.split('/')[0]] = {
                        'sourceCommit': source, 'status': report.get('status', 'unknown'),
                        'checkCount': report.get('checkCount', 0),
                        'actualAndroidExecution': report.get('actualAndroidExecution', False),
                        'actualGeckoExecution': report.get('actualGeckoExecution', False),
                        'sameClassTraceComplete': complete, 'sdkTraceRows': len(rows),
                        'candidateActivationRequired': report.get('actualCandidateActivation',{}).get('required') is True,
                        'actualNativeCaretWriters': report.get('actualCandidateActivation',{}).get('nativeCaretWriterCount',0),
                        'expectedTypedCharacters': report.get('actualCandidateActivation',{}).get('expectedCharacters',0),
                        'error': report.get('error', ''),
                    }
            except (ValueError, TypeError, AttributeError, KeyError) as error:
                manifest['warnings'].append(name + ': ' + str(error))
                continue
        target = stage / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        manifest['artifacts'].append({'file': name, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
    manifest['allAttemptsRecorded'] = ({item.get('trial') for item in manifest['attempts']} == set(TRIALS)
                                       and len(manifest['attempts']) == len(TRIALS))
    manifest['passedTrials'] = [item['trial'] for item in manifest['attempts'] if item.get('exitCode') == 0 and item.get('status') == 'passed']
    manifest['failedTrials'] = [item['trial'] for item in manifest['attempts'] if item.get('exitCode') != 0 or item.get('status') != 'passed']
    manifest['allSdkTracesComplete'] = (set(manifest['reports']) == {f'attempt-{trial}' for trial in TRIALS}
                                       and all(item['sameClassTraceComplete'] for item in manifest['reports'].values()))
    (stage / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return stage, manifest


def main():
    source = git('rev-parse', 'HEAD')
    if os.environ.get('GITHUB_SHA') != source:
        raise ValueError('Checked-out diagnostic source differs from run source')
    outcomes = {name: os.environ['DIAGNOSTIC_' + name.upper() + '_OUTCOME'] for name in ('setup', 'build', 'gecko')}
    outcomes.update({name: os.environ.get('DIAGNOSTIC_' + name.upper() + '_OUTCOME', 'skipped')
                     for name in ('plain_build', 'original_gate', 'compatibility')})
    stage, manifest = stage_evidence(source, os.environ['GITHUB_RUN_ID'], os.environ.get('GITHUB_RUN_ATTEMPT', '1'), outcomes)
    env = dict(os.environ, GIT_INDEX_FILE=str(OUT / 'public-sdk-index'), GIT_WORK_TREE=str(stage),
               GIT_AUTHOR_NAME='PocketChat SDK diagnostics', GIT_AUTHOR_EMAIL='pocketchat@users.noreply.github.com',
               GIT_COMMITTER_NAME='PocketChat SDK diagnostics', GIT_COMMITTER_EMAIL='pocketchat@users.noreply.github.com')
    parents = ['-p', source]
    previous = git('ls-remote', 'origin', 'refs/heads/' + BRANCH).split()
    if previous:
        git('fetch', 'origin', 'refs/heads/' + BRANCH)
        parents += ['-p', previous[0]]
    git('read-tree', '--empty', env=env)
    names = [artifact['file'] for artifact in manifest['artifacts']] + ['manifest.json']
    git('add', '-f', '--', *names, env=env)
    tree = git('write-tree', env=env)
    commit = git('commit-tree', tree, *parents, '-m', 'Record every synthetic SDK transaction input diagnostic trial', env=env)
    git('push', 'origin', commit + ':refs/heads/' + BRANCH)
    print(json.dumps({'sourceCommit': source, 'productionSourceCommit': PRODUCTION_SOURCE, 'runId': manifest['runId'],
                      'branch': BRANCH, 'evidenceCommit': commit, 'allAttemptsRecorded': manifest['allAttemptsRecorded'],
                      'passedTrials': manifest['passedTrials'], 'failedTrials': manifest['failedTrials']}, indent=2))


if __name__ == '__main__':
    main()
