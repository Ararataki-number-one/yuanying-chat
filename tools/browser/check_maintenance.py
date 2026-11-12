#!/usr/bin/env python3
"""Run current-source browser and network regressions without historical source views.

This is a focused maintenance check, not the full release or device acceptance.
Each child retains its original behavioral assertions and negative controls.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
INPUT_PATHS = ('app/src', 'app/build.gradle', 'tests', 'tools', 'third-party',
               '.github/workflows', 'build.gradle', 'settings.gradle', 'gradle.properties')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_inputs(root=ROOT):
    """Include sibling fixtures, imported runners and assets, not only argv files."""
    raw = subprocess.check_output(['git', 'ls-files', '-z', '--cached', '--others',
                                   '--exclude-standard', '--', *INPUT_PATHS], cwd=root)
    return sorted({root / os.fsdecode(name) for name in raw.split(b'\0') if name})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--java-home', required=True, type=Path)
    parser.add_argument('--json-jar', required=True, type=Path)
    parser.add_argument('--output', type=Path, default=ROOT/'work/browser-maintenance')
    parser.add_argument('--android-jar', type=Path, help='Optional actual Android API compile; requires both dependency jars below.')
    parser.add_argument('--webkit-jar', type=Path)
    parser.add_argument('--snakeyaml-jar', type=Path)
    args = parser.parse_args()
    native = [args.android_jar, args.webkit_jar, args.snakeyaml_jar]
    if any(native) and not all(native):
        parser.error('Native compilation requires --android-jar, --webkit-jar and --snakeyaml-jar together')
    java_home, jar, out = args.java_home.resolve(), args.json_jar.resolve(), args.output.resolve()
    for path in [java_home/'bin/java', java_home/'bin/javac', jar, *[p for p in native if p]]:
        if not path.is_file():
            parser.error('Missing dependency: '+str(path))
    compiler = subprocess.check_output([str(java_home/'bin/javac'), '-version'], stderr=subprocess.STDOUT, text=True).strip()
    if not compiler.startswith('javac 17.'):
        parser.error('The maintenance checks require JDK 17')
    runtime = subprocess.check_output([str(java_home/'bin/java'), '-version'], stderr=subprocess.STDOUT, text=True).strip()
    out.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, JAVA_HOME=str(java_home), PROFILE_JAVA=str(java_home/'bin/java'),
               PROFILE_JSON_JAR=str(jar), BROWSER_ENTRY_REPORT=str(out/'environment-entry.json'))
    env['PATH'] = str(java_home/'bin')+os.pathsep+env.get('PATH', '')
    jobs = []
    java = ['--java-home', str(java_home)]

    def host(name, script, arguments=(), report=True):
        target = out/(name+'.json') if report else None
        command = [sys.executable, script, *map(str, arguments)]
        if target:
            command += ['--output', str(target)]
        jobs.append((name, [command], target))

    host('address-policy', 'tests/browser-address-host/run.py', java)
    host('browser-permissions', 'tests/browser-permissions-host/run.py', java)
    host('native-attachment-chooser', 'tests/native-attachment-chooser-host/run.py', [*java, '--json-jar', jar])
    for name, script in [
        ('session-navigation', 'tests/gecko-navigation-host/session_navigation.py'),
        ('driver-ownership', 'tests/gecko-navigation-host/run.py'),
        ('gecko-activation', 'tests/gecko-activation-host/run.py'),
        ('gecko-ui-lifecycle', 'tests/gecko-ui-host-lifecycle/run.py'),
        ('resource-client', 'tests/gecko-navigation-host/client_ready.py'),
        ('addon-lifecycle', 'tests/gecko-addon-lifecycle-host/run.py'),
        ('gecko-startup-window', 'tests/gecko-startup-window-host/run.py'),
        ('gecko-texture-surface', 'tests/gecko-texture-surface-host/run.py'),
        ('ip-transport', 'tests/gecko-ip-transport-host/run.py'),
        ('resource-recovery', 'tests/resource-recovery-host/run.py'),
        ('page-lifecycle', 'tests/browser-navigation-lifecycle-host/run.py'),
        ('reply-task-persistence', 'tests/reply-task-persistence-host/run.py'),
        ('download-cancellation', 'tests/download-resume-host/run.py'),
        ('download-persistence', 'tests/download-persistence-host/run.py'),
        ('download-recovery', 'tests/download-recovery-host/run.py'),
        ('saved-file-copy', 'tests/saved-copy-host/run.py'),
        ('draft-policy', 'tests/local-draft-policy-host/run.py'),
        ('chromium-navigation', 'tests/chromium-fingerprint-activity-host/run.py'),
        ('chromium-fingerprint-jobs', 'tests/chromium-fingerprint-jobs-host/run.py'),
        ('route-start', 'tests/source-route-start-host/run.py'),
        ('route-terminal', 'tests/source-route-start-host/terminal_join.py'),
        ('route-lease', 'tests/chromium-route-host/lease_boundaries.py'),
    ]:
        host(name, script, [*java, '--json-jar', jar])
        if name == 'saved-file-copy':
            jobs[-1][1].append([sys.executable, 'tests/profile_saved_copy_host_retirement_test.py'])
    host('page-recovery', 'tests/page-recovery-host/run.py', ['--json-jar', jar], report=False)
    host('persistent-profile', 'tests/browser-profile-path-host/run.py', java)
    host('profile-maintenance', 'tests/profile_current_runtime_raw_binding_test.py', [
        'CurrentRuntimeRawBindings.test_every_other_original_raw_pin_remains_exact_and_unknown_is_rejected',
        'CurrentRuntimeRawBindings.test_current_profile_behavior_accepts_an_unrelated_browser_method',
        'CurrentRuntimeRawBindings.test_default_embedded_dependency_and_reject_unknown_explicit_jar'], report=False)
    host('environment-entry', 'tests/profile_browser_environment_entry_test.py', report=False)
    host('browser-startup', 'tests/profile_environment_dashboard_startup_test.py', report=False)
    jobs.append(('display-acceptance', [
        [sys.executable, 'tests/gecko_glass_navigation_capture_test.py'],
        [sys.executable, 'tests/glass_ui_validation_test.py'],
        [sys.executable, 'tests/browser_workspace_device_configuration_test.py'],
        [sys.executable, 'tests/profile_ui_device_preparation_test.py']], None))
    jobs.append(('event-transport', [
        [sys.executable, 'tests/gecko_event_transfer_test.py'],
        [sys.executable, 'tests/profile_event_journal_discovery_test.py']], None))
    host('address-ui', 'tests/browser_fingerprint_fixture_test.py', [
        'BrowserFingerprintFixtureTests.test_actual_browser_address_navigation_and_history_controls',
        'BrowserFingerprintFixtureTests.test_actual_browser_address_row_reflows_without_recreating_controls'], report=False)
    for name, source, test, arguments in [
        ('bridge-ownership', 'BrowserBridgeRequests', 'BrowserBridgeRequestsTest', []),
        ('browser-runtime', 'BrowserRuntimePolicy', 'BrowserRuntimePolicyTest', [str(ROOT)]),
    ]:
        classes = out/(name+'-classes')
        jobs.append((name, [
            [str(java_home/'bin/javac'), '-encoding', 'UTF-8', '--release', '17', '-d', str(classes),
             str(ROOT/'app/src/main/java/local/pocketchat'/(source+'.java')),
             str(ROOT/'tests/browser-runtime'/(test+'.java'))],
            [str(java_home/'bin/java'), '-cp', str(classes), 'local.pocketchat.'+test, *arguments]], None))
    if all(native):
        target = out/'native-compile'
        jobs.append(('native-compile', [[sys.executable, 'tests/ux-native-compile/run.py', *java,
            '--android-jar', str(args.android_jar.resolve()), '--classpath-jar', str(args.webkit_jar.resolve()),
            '--classpath-jar', str(args.snakeyaml_jar.resolve()), '--output', str(target)]], target/'receipt.json'))

    hashes = {str(path.relative_to(ROOT)): digest(path) for path in source_inputs()}
    dependencies = {str(path.resolve()): digest(path) for path in [jar, *[p for p in native if p]]}
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    tree = subprocess.check_output(['git', 'rev-parse', 'HEAD^{tree}'], cwd=ROOT, text=True).strip()
    dirty = bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True).strip())
    started_at, started = datetime.now(timezone.utc).isoformat(), time.monotonic()
    rows = []
    for name, commands, report in jobs:
        print(json.dumps(dict(suite=name, status='running')), flush=True)
        suite_started = time.monotonic()
        log, codes = [], []
        if report and report.exists():
            report.unlink()
        for command in commands:
            try:
                result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, timeout=300)
                log.extend([result.stdout, result.stderr]);codes.append(result.returncode)
            except subprocess.TimeoutExpired as failure:
                log.append('Suite exceeded 300 seconds: '+str(failure));codes.append(124)
            if codes[-1]:
                break
        log_path = out/(name+'.log');log_path.write_text(''.join(log))
        passed = all(code == 0 for code in codes)
        row = dict(suite=name, status='passed' if passed else 'failed', commands=commands,
                   exitCodes=codes, log=str(log_path), logSha256=digest(log_path),
                   durationSeconds=round(time.monotonic()-suite_started, 3))
        if report:
            if report.is_file():
                data = json.loads(report.read_text())
                row.update(report=str(report), reportSha256=digest(report))
                if data.get('status', 'passed') != 'passed' or not data.get('executionInputsUnchanged', True):
                    row['status'] = 'failed'
            else:
                row.update(status='failed', reason='Required report was not produced')
        rows.append(row)
        print(json.dumps(dict(suite=name, status=row['status'], log=str(log_path))), flush=True)
    changed = [name for name, value in hashes.items() if not (ROOT/name).is_file() or digest(ROOT/name) != value]
    changed += sorted({str(path.relative_to(ROOT)) for path in source_inputs()} - hashes.keys())
    changed += [name for name, value in dependencies.items() if not Path(name).is_file() or digest(Path(name)) != value]
    stable = not changed and subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip() == commit
    passed = stable and all(row['status'] == 'passed' for row in rows)
    result = dict(status='passed' if passed else 'failed', sourceCommit=commit, sourceTree=tree,
                  dirtySource=dirty, sourceFiles=hashes, javaVersion=runtime, compilerVersion=compiler,
                  executionInputsUnchanged=stable, changedInputs=changed, dependencies=dependencies, suites=rows,
                  startedAt=started_at, completedAt=datetime.now(timezone.utc).isoformat(),
                  durationSeconds=round(time.monotonic()-started, 3),
                  actualAndroidExecution=False, fullAppBuild=False, fullReleaseQualification=False,
                  scope='Current production navigation, UI host and permission ownership, task/file persistence and cancellation, fingerprint transactions, route-change leases, address UI, browser entry and persistent profile behavior on declared host boundaries. Optional native Java API compilation. No device, website, network or full release acceptance.')
    (out/'results.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(dict(status=result['status'], suites=len(rows), executionInputsUnchanged=stable)), flush=True)
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
