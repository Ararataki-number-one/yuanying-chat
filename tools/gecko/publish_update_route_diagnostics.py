#!/usr/bin/env python3
"""Source-matched update route diagnostics. Never publish APKs or signing material."""
import argparse, hashlib, json, os, pathlib, re, runpy, shutil, subprocess

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / 'work/gecko-integration'
BRANCH = 'apk/update-route-diagnostics'
BASE = 'e4a4a08202cf50ce60d36dd86a625366de9bb2f4'
REPORTS = {'transfers': 'diagnostic-update-transfers-results.json', 'route': 'update-route-results.json'}
ARTIFACTS = ('build.log', 'integration-badging.txt', 'update-fixture-preparation.log',
             'diagnostic-update-transfers-results.json', 'diagnostic-update-device-results.json',
             'diagnostic-update-transfers-last-device-log.txt', 'diagnostic-update-transfers-device-route-trace.json',
             'diagnostic-update-transfers-device-native-events.txt', 'diagnostic-update-transfers-update-transfer-failure-log.txt',
             'update-transfer-job-before-pause.txt', 'update-transfer-job-after-restart.txt',
             'update-route-results.json', 'update-route-log.txt', 'update-route-failure-log.txt',
             'update-route-host-wire.json', 'update-route-runner.log', 'update-transfers-runner.log',
             'update-route-transfers-status.json', 'update-route-route-status.json')
MUTATIONS = {'app/src/main/java/local/pocketchat/' + name + '.java' for name in
             ['AppUpdateActivity', 'AppUpdateManager', 'AppUpdateProvider', 'AppUpdateTransfer',
              'AppUpdates', 'AppUpdateRoute', 'NetworkUiProvider']}
PINNED_DEPENDENCIES = {
    'app/src/main/java/local/pocketchat/AppSettings.java': 'e82caf54bf6ca8e393c1e4e9abbf34f9d5a1c879cf6269516670b747a1835111',
    'app/src/main/java/local/pocketchat/QuietNotifications.java': '350c11c654744a478879fd3270f4f167bb642b5eee1826409e028f6766f9addf',
}


def git(*args, env=None):
    return subprocess.check_output(['git', *args], cwd=ROOT, env=env, text=True).strip()


def regular(path):
    return path.is_file() and path.resolve().is_relative_to(OUT.resolve()) and not any(p.is_symlink() for p in (path, *path.parents) if p == OUT or OUT in p.parents)


def stamp(case, exit_code, source, run, attempt):
    for name in ([REPORTS[case], 'diagnostic-update-device-results.json'] if case == 'transfers' else [REPORTS[case]]):
        p = OUT / name
        if regular(p):
            d = json.loads(p.read_text()); assert d['sourceCommit'] == source and d['actualAndroidExecution']
            d.update(diagnosticOnly=True, releaseAcceptance=False, runId=run, runAttempt=attempt)
            p.write_text(json.dumps(d, indent=2) + '\n')
    status = dict(case=case, sourceCommit=source, runId=run, runAttempt=attempt, exitCode=exit_code,
                  status='passed' if exit_code == 0 else 'failed', diagnosticOnly=True, releaseAcceptance=False)
    (OUT / ('update-route-' + case + '-status.json')).write_text(json.dumps(status, indent=2) + '\n')


def stage(source, run, attempt, outcomes):
    assert re.fullmatch('[a-f0-9]{40}', source) and run.isdecimal() and attempt.isdecimal()
    try: base = git('rev-parse', '--verify', BASE + '^{commit}')
    except subprocess.CalledProcessError:
        git('fetch', '--no-tags', '--depth=1', 'origin', BASE); base = git('rev-parse', '--verify', BASE + '^{commit}')
    changed = git('diff', '--name-only', base, source, '--', 'app', 'libs', 'third-party', 'build.gradle', 'settings.gradle', 'gradle.properties').splitlines()
    assert set(changed) <= MUTATIONS | set(PINNED_DEPENDENCIES), 'Unexpected production/SDK/core change'
    mutations = []
    for name in changed:
        current = subprocess.check_output(['git', 'show', source + ':' + name], cwd=ROOT)
        digest = hashlib.sha256(current).hexdigest()
        if name in PINNED_DEPENDENCIES:
            assert digest == PINNED_DEPENDENCIES[name], 'Quiet dependency differs from the authorized pinned helper'
        mutations.append(dict(file=name, sourceSha256=digest, pinnedDependency=name in PINNED_DEPENDENCIES))
    public = OUT / 'update-route-public'
    if public.exists(): shutil.rmtree(public)
    public.mkdir(parents=True)
    core = json.loads((ROOT / 'third-party/patches/mihomo-v1.19.31-probe-build.json').read_text()); core['sourceCommit'] = source
    (public / 'network-core-build.json').write_text(json.dumps(core, indent=2) + '\n')
    manifest = dict(sourceCommit=source, productionBaseCommit=base, runId=run, runAttempt=attempt,
                    diagnosticOnly=True, releaseAcceptance=False, officialSdkAndNativeCoreUnchanged=True,
                    productionMutations=mutations, stepOutcomes=outcomes, reports={}, cases={}, artifacts=[], warnings=[])
    complete = {}
    for name in ARTIFACTS:
        path = OUT / name
        if not regular(path): continue
        data = path.read_bytes()
        if name in REPORTS.values() or name == 'diagnostic-update-device-results.json' or name.endswith('-status.json'):
            report = json.loads(data)
            assert report['sourceCommit'] == source and report['diagnosticOnly'] and report['releaseAcceptance'] is False, name
            assert report['runId'] == run and report['runAttempt'] == attempt, name
            if name.endswith('-status.json'): manifest['cases'][report['case']] = report
            elif name in REPORTS.values():
                case = next(k for k, v in REPORTS.items() if v == name); passed = False
                if report.get('status') == 'passed':
                    try:
                        assert report['actualAndroidExecution']
                        if case == 'route': runpy.run_path(str(ROOT / 'tests/gecko/run_update_route.py'))['verify'](report)
                        else:
                            assert report['checkCount'] == len(report['checks']) == 28
                            assert len({v['name'] for v in report['checks']}) == 28 and all(v['pass'] for v in report['checks'])
                            assert report['actualHttpTransfer'] and report['actualJobSchedulerExecution']
                        passed = True
                    except Exception as error: manifest['warnings'].append(name + ': ' + str(error))
                complete[case] = passed
                manifest['reports'][name] = dict(sourceCommit=source, status=report.get('status'),
                    actualAndroidExecution=report.get('actualAndroidExecution'), checkCount=len(report.get('checks', [])), completeDiagnosticPassed=passed)
        (public / name).write_bytes(data)
    for path in sorted(public.iterdir()):
        data = path.read_bytes(); manifest['artifacts'].append(dict(file=path.name, bytes=len(data), sha256=hashlib.sha256(data).hexdigest()))
    badging = (public / 'integration-badging.txt').read_text() if (public / 'integration-badging.txt').is_file() else ''
    manifest['compiledIntegrationNonDebuggable'] = "package: name='local.pocketchat.test'" in badging and 'application-debuggable' not in badging
    manifest['allDiagnosticsPassed'] = (manifest['compiledIntegrationNonDebuggable'] and set(complete) == set(REPORTS)
        and all(complete.values()) and set(manifest['cases']) == set(REPORTS)
        and all(v['exitCode'] == 0 for v in manifest['cases'].values()) and not manifest['warnings']
        and outcomes.get('android') not in ('failure', 'cancelled', 'skipped'))
    (public / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return public, manifest


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--case', choices=REPORTS); p.add_argument('--exit-code', type=int); args = p.parse_args()
    source = git('rev-parse', 'HEAD'); assert source == os.environ['GITHUB_SHA']
    run, attempt = os.environ['GITHUB_RUN_ID'], os.environ.get('GITHUB_RUN_ATTEMPT', '1')
    if args.case: assert args.exit_code is not None; stamp(args.case, args.exit_code, source, run, attempt)
    directory, manifest = stage(source, run, attempt, {k: os.environ.get('UPDATE_ROUTE_' + k.upper() + '_OUTCOME', 'pending') for k in ['setup', 'build', 'fixtures', 'android']})
    env = dict(os.environ, GIT_INDEX_FILE=str(OUT / 'update-route-public-index'), GIT_WORK_TREE=str(directory),
               GIT_AUTHOR_NAME='PocketChat diagnostics', GIT_AUTHOR_EMAIL='pocketchat@users.noreply.github.com',
               GIT_COMMITTER_NAME='PocketChat diagnostics', GIT_COMMITTER_EMAIL='pocketchat@users.noreply.github.com')
    parents = ['-p', source]; previous = git('ls-remote', 'origin', 'refs/heads/' + BRANCH).split()
    if previous: git('fetch', 'origin', 'refs/heads/' + BRANCH); parents += ['-p', previous[0]]
    git('read-tree', '--empty', env=env); git('add', '-f', '--', 'manifest.json', *(v['file'] for v in manifest['artifacts']), env=env)
    tree = git('write-tree', env=env); commit = git('commit-tree', tree, *parents, '-m', 'Publish bounded synthetic update route evidence', env=env)
    git('push', 'origin', commit + ':refs/heads/' + BRANCH)
    print(json.dumps(dict(sourceCommit=source, evidenceCommit=commit, runId=run, allDiagnosticsPassed=manifest['allDiagnosticsPassed']), indent=2))


if __name__ == '__main__': main()
