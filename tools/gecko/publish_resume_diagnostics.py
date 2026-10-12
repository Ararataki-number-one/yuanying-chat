#!/usr/bin/env python3
"""Publish bounded synthetic resume diagnostics, never APKs or signing material."""
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / 'work/gecko-resume-diagnostics'
BRANCH = 'artifacts/gecko-resume-diagnostics'
MODES = {'reading': 'reading', 'transfers': 'update-transfers'}
# Keep this exact list shared with the workflow's capture/cleanup operation.
# Do not publish directories, arbitrary globs, APKs, keystores or environment dumps.
RUNNER_ARTIFACTS = {
    'reading': (
        'diagnostic-reading-results.json',
        'diagnostic-reading-last-device-log.txt',
        'diagnostic-reading-device-route-trace.json',
        'diagnostic-reading-device-native-events.txt',
        'reading-945x2100.png', 'reading-1024x2240.png',
        'reading-1128x2400.png', 'reading-1920x1080.png',
        'reading-shrunk-80.png', 'failure-screen.png', 'failure-ui.xml',
        'reading-fit-privacy-0.png', 'reading-fit-privacy-2.png',
        'reading-fit-landscape.png', 'reading-fit-portrait.png',
        'reading-fit-keyboard.png',
    ),
    'transfers': (
        'diagnostic-update-transfers-results.json',
        'diagnostic-update-device-results.json',
        'diagnostic-update-transfers-last-device-log.txt',
        'diagnostic-update-transfers-device-route-trace.json',
        'diagnostic-update-transfers-device-native-events.txt',
        'diagnostic-update-transfers-update-transfer-failure-log.txt',
        'update-transfer-job-before-pause.txt',
        'update-transfer-job-after-restart.txt',
        'failure-screen.png', 'failure-ui.xml',
    ),
}
ARTIFACTS = ('build.log', 'update-fixture-preparation.log') + tuple(
    f'{case}/{name}' for case in MODES for name in (
        'status.json', 'test.log', 'emulator.log', 'screen.png',
    ) + RUNNER_ARTIFACTS[case])
REPORTS = {
    'reading': ('diagnostic-reading-results.json',),
    'transfers': ('diagnostic-update-transfers-results.json',
                  'diagnostic-update-device-results.json'),
}


def git(*arguments, env=None):
    return subprocess.check_output(['git', *arguments], cwd=ROOT,
                                   env=env, text=True).strip()


def regular_artifact(path):
    """Even a whitelisted filename must not escape through a symlink."""
    return (path.is_file() and path.resolve().is_relative_to(OUT.resolve())
            and not any(item.is_symlink() for item in (path, *path.parents)
                        if item == OUT or OUT in item.parents))


def passed_report(case, name, report):
    if report.get('status') != 'passed' or report.get('actualAndroidExecution') is not True:
        return False
    if case == 'reading':
        bounds = report.get('nativeReadingBounds', {})
        cases = bounds.get('cases', [])
        return (report.get('androidSdk') == 35 and report.get('checkCount') == 14
                and len(report.get('responsiveReading', [])) == 4
                and len(report.get('nativeReadingZoom', [])) == 4
                and isinstance(report.get('scaledReadingInput'), dict)
                and bounds.get('schema') == 1
                and len(cases) == 2 and [item.get('privacyLevel') for item in cases] == [0, 2]
                and all(item.get('actualGeckoExecution') is True for item in cases)
                and len(bounds.get('rotation', [])) == 2
                and bounds.get('input', {}).get('imeVisible') is True
                and bounds.get('productionDelegateRestored') is True
                and bounds.get('privacyRestored') is True)
    if name == 'diagnostic-update-device-results.json':
        return report.get('androidSdk') == 35
    checks = report.get('checks', [])
    return (report.get('checkCount') == 28 and len(checks) == 28
            and len({item.get('name') for item in checks}) == 28
            and all(item.get('pass') is True for item in checks)
            and report.get('actualHttpTransfer') is True
            and report.get('actualJobSchedulerExecution') is True)


def stage_evidence(source, run_id, run_attempt, outcomes):
    if not re.fullmatch(r'[0-9a-f]{40}', source):
        raise ValueError('Expected the exact checked-out source commit')
    if not re.fullmatch(r'[0-9]+', run_id) or not re.fullmatch(r'[0-9]+', run_attempt):
        raise ValueError('Expected GitHub run identity')
    if set(outcomes) != {'setup', 'build', 'fixtures', 'reading', 'transfers'}:
        raise ValueError('Expected both diagnostic and preparation outcomes')
    if any(value not in ('success', 'failure', 'cancelled', 'skipped')
           for value in outcomes.values()):
        raise ValueError('Invalid diagnostic step outcome')
    stage = OUT / 'public'
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    manifest = {
        'sourceCommit': source, 'runId': run_id, 'runAttempt': run_attempt,
        'diagnosticOnly': True, 'releaseAcceptance': False,
        'stepOutcomes': outcomes, 'artifacts': [], 'warnings': [],
        'diagnostics': {}, 'reports': {},
    }
    report_passes = {}
    for name in ARTIFACTS:
        original = OUT / name
        if not regular_artifact(original):
            continue
        data = original.read_bytes()
        case, _, filename = name.partition('/')
        if filename == 'status.json' or filename in REPORTS.get(case, ()):
            try:
                report = json.loads(data)
                if report.get('sourceCommit') != source:
                    raise ValueError('Report belongs to another source commit')
                if report.get('diagnosticOnly') is not True:
                    raise ValueError('Report is not explicitly diagnostic-only')
                if filename == 'status.json':
                    if (report.get('runId') != run_id or report.get('runAttempt') != run_attempt
                            or report.get('mode') != MODES[case]):
                        raise ValueError('Diagnostic belongs to another run or mode')
                    manifest['diagnostics'][case] = report
                else:
                    # Runner reports are bound to this run by the clean per-case
                    # output directory, matching status, and manifest content hash.
                    if 'runId' in report and str(report['runId']) != run_id:
                        raise ValueError('Report belongs to another GitHub run')
                    report_passes[name] = passed_report(case, filename, report)
                    manifest['reports'][name] = {
                        'sourceCommit': source, 'status': report.get('status', 'unknown'),
                        'checkCount': report.get('checkCount', 0),
                        'actualAndroidExecution': report.get('actualAndroidExecution', False),
                        'completeDiagnosticPassed': report_passes[name],
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
    required = {f'{case}/{name}' for case, names in REPORTS.items() for name in names}
    manifest['allDiagnosticsPassed'] = (
        set(manifest['diagnostics']) == set(MODES)
        and all(item.get('exitCode') == 0 and item.get('status') == 'passed'
                for item in manifest['diagnostics'].values())
        and set(report_passes) == required and all(report_passes.values())
        and all(value == 'success' for value in outcomes.values())
        and not manifest['warnings'])
    (stage / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return stage, manifest


def main():
    source = git('rev-parse', 'HEAD')
    if os.environ.get('GITHUB_SHA') != source:
        raise ValueError('Checked-out source differs from the GitHub run source')
    outcomes = {name: os.environ['DIAGNOSTIC_' + name.upper() + '_OUTCOME']
                for name in ('setup', 'build', 'fixtures', 'reading', 'transfers')}
    stage, manifest = stage_evidence(source, os.environ['GITHUB_RUN_ID'],
                                     os.environ.get('GITHUB_RUN_ATTEMPT', '1'), outcomes)
    env = dict(os.environ, GIT_INDEX_FILE=str(OUT / 'public-index'),
               GIT_WORK_TREE=str(stage), GIT_AUTHOR_NAME='PocketChat diagnostics',
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
    commit = git('commit-tree', tree, *parents, '-m',
                 'Publish synthetic reading and update resume diagnostics', env=env)
    git('push', 'origin', commit + ':refs/heads/' + BRANCH)
    print(json.dumps({'sourceCommit': source, 'runId': manifest['runId'],
                      'branch': BRANCH, 'evidenceCommit': commit,
                      'allDiagnosticsPassed': manifest['allDiagnosticsPassed']}, indent=2))


if __name__ == '__main__':
    main()
