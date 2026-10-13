#!/usr/bin/env python3
"""Publish only synthetic Gecko input diagnostics; no APK, profile or signing key."""
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / 'work/gecko-input-diagnostics'
BRANCH = 'apk/gecko-input-diagnostics'
# Exact filenames only. Never include a directory, arbitrary glob or environment dump.
ARTIFACTS = (
    (OUT, 'build.log'),
    (OUT, 'input-test.log'),
    (OUT, 'emulator.log'),
    (OUT, 'input-diagnostic-screen.png'),
) + tuple((OUT, f'attempt-{trial}/{name}') for trial in (1, 2, 3) for name in (
    'status.json', 'runner.log', 'gecko-performance-results.json',
    'gecko-performance-failure-log.txt', 'gecko-performance-screen.png', 'screen.png',
    'gecko-performance-failure-screen.png', 'gecko-performance-failure-ui.xml',
    'gecko-performance-failure-window.txt', 'gecko-performance-failure-activity.txt',
    'gecko-native-ime-snapshot.log', 'gecko-native-ime-snapshot.json',
    'gecko-scroll-diagnostics.json', 'gecko-scroll-diagnostic-log.json',
))


def git(*arguments, env=None):
    return subprocess.check_output(['git', *arguments], cwd=ROOT, env=env, text=True).strip()


def stage_evidence(source, run_id, run_attempt, outcomes):
    if not re.fullmatch(r'[0-9a-f]{40}', source):
        raise ValueError('Expected the exact checked-out source commit')
    if not re.fullmatch(r'[0-9]+', run_id) or not re.fullmatch(r'[0-9]+', run_attempt):
        raise ValueError('Expected GitHub run identity')
    if any(value not in ('success', 'failure', 'cancelled', 'skipped') for value in outcomes.values()):
        raise ValueError('Invalid diagnostic step outcome')
    stage = OUT / 'public'
    # A second publication must not carry files from a prior staging operation.
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    manifest = {
        'sourceCommit': source,
        'runId': run_id,
        'runAttempt': run_attempt,
        'diagnosticOnly': True,
        'releaseAcceptance': False,
        'stepOutcomes': outcomes,
        'artifacts': [],
        'warnings': [],
        'attempts': [],
        'reports': {},
    }
    for directory, name in ARTIFACTS:
        original = directory / name
        if original.is_symlink() or original.parent.is_symlink() or not original.is_file():
            continue
        data = original.read_bytes()
        if name.endswith('/status.json') or name.endswith('/gecko-performance-results.json'):
            try:
                report = json.loads(data)
                if report.get('sourceCommit') != source:
                    raise ValueError('Report belongs to another source commit')
                if name.endswith('/status.json'):
                    trial = int(name.split('/')[0].removeprefix('attempt-'))
                    if report.get('runId') != run_id or report.get('runAttempt') != run_attempt or report.get('trial') != trial:
                        raise ValueError('Attempt belongs to another run or trial')
                    manifest['attempts'].append(report)
                else:
                    if report.get('inputNativeDiagnosticsEnabled') is not True or report.get('inputDiagnosticsEnabled') is not False:
                        raise ValueError('Expected public-delegate/native-log diagnostics, without extra JS or evaluation tracing')
                    manifest['reports'][name.split('/')[0]] = {
                        'inputNativeDiagnosticsEnabled': True, 'inputDiagnosticsEnabled': False,
                        'sourceCommit': source, 'status': report.get('status', 'unknown'),
                        'checkCount': report.get('checkCount', 0),
                        'actualAndroidExecution': report.get('actualAndroidExecution', False),
                        'actualGeckoExecution': report.get('actualGeckoExecution', False),
                    }
            except (ValueError, TypeError, AttributeError) as error:
                manifest['warnings'].append(name + ': ' + str(error))
                continue
        target = stage / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        manifest['artifacts'].append({
            'file': name, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
        })
    manifest['allAttemptsPassed'] = (len(manifest['attempts']) == 3
        and all(item.get('exitCode') == 0 and item.get('status') == 'passed' for item in manifest['attempts'])
        and set(manifest['reports']) == {'attempt-1', 'attempt-2', 'attempt-3'}
        and all(item['status'] == 'passed' and item['actualAndroidExecution'] and item['actualGeckoExecution']
                for item in manifest['reports'].values())
        and outcomes['gecko'] == 'success' and not manifest['warnings'])
    (stage / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return stage, manifest


def main():
    source = git('rev-parse', 'HEAD')
    if os.environ.get('GITHUB_SHA') != source:
        raise ValueError('Checked-out source differs from the GitHub run source')
    outcomes = {name: os.environ['DIAGNOSTIC_' + name.upper() + '_OUTCOME']
                for name in ('setup', 'build', 'gecko')}
    stage, manifest = stage_evidence(source, os.environ['GITHUB_RUN_ID'],
                                     os.environ.get('GITHUB_RUN_ATTEMPT', '1'), outcomes)
    env = dict(os.environ,
               GIT_INDEX_FILE=str(OUT / 'public-index'), GIT_WORK_TREE=str(stage),
               GIT_AUTHOR_NAME='PocketChat diagnostics',
               GIT_AUTHOR_EMAIL='pocketchat@users.noreply.github.com',
               GIT_COMMITTER_NAME='PocketChat diagnostics',
               GIT_COMMITTER_EMAIL='pocketchat@users.noreply.github.com')
    parents = ['-p', source]
    previous = git('ls-remote', 'origin', 'refs/heads/' + BRANCH).split()
    if previous:
        git('fetch', 'origin', 'refs/heads/' + BRANCH)
        parents += ['-p', previous[0]]
    git('read-tree', '--empty', env=env)
    names = [artifact['file'] for artifact in manifest['artifacts']] + ['manifest.json']
    git('add', '-f', '--', *names, env=env)
    tree = git('write-tree', env=env)
    commit = git('commit-tree', tree, *parents, '-m', 'Publish synthetic Gecko input diagnostics', env=env)
    git('push', 'origin', commit + ':refs/heads/' + BRANCH)
    print(json.dumps({'sourceCommit': source, 'runId': manifest['runId'],
                      'branch': BRANCH, 'evidenceCommit': commit}, indent=2))


if __name__ == '__main__':
    main()
