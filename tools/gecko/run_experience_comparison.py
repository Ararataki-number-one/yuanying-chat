#!/usr/bin/env python3
"""Run a predeclared ABBA workload on one synthetic emulator.

This is an experience experiment, separate from the original release gates.
It never rebuilds an APK, retries a workload, or turns missing observations into
zeroes. Both builds must use the same benchmark and environment setup sources.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import statistics
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = 'local.pocketchat.test'
SERIAL = 'emulator-5554'
APK = 'app/build/outputs/apk/integration/app-x86_64-integration.apk'
HARNESS = (
    'tests/gecko/ExperienceBenchmarkActivity.java',
    'tests/gecko/run_experience_benchmark.py',
    'tests/gecko/ChromeCollapseIntegration.java',
    'tests/gecko/CompactChromeIntegrationActivity.java',
    'tests/gecko/ChromeCollapseDocumentReadyAdapter.java',
    'tests/gecko/IntegrationBuildIdentity.java',
    'tests/gecko/IntegrationEventStore.java',
    'tests/gecko/IntegrationEvidenceProvider.java',
    'app/src/main/java/local/pocketchat/NormalCaretSdkReceipt.java',
    'engine-probe/tests/run_device.py',
    'tools/gecko/integration_event_contract.py',
    'tools/gecko/profile_invocation_contract.py',
    'tools/gecko/sdk_identity_contract.py',
)
SETUP = (
    'tools/gecko/android-emulator.json',
    'tools/gecko/android-system-image.json',
    'tools/gecko/android-platform-tools.json',
    'tools/gecko/android-35-google-apis-x86_64-package.xml',
    'tools/gecko/android-emulator-package.xml',
    'tools/gecko/prepare_android_image.py',
    'tools/gecko/prepare_platform_tools.py',
    'tools/gecko/prepare_native_adb.py',
    'tools/gecko/prepare_emulator.py',
    'tools/gecko/ci_bundle.py',
)
ACTIONS = (
    'open-network', 'return-network', 'open-downloads', 'return-downloads',
    'open-settings', 'return-settings', 'collapse', 'expand', 'theme-settings',
    'theme-dark', 'theme-light', 'theme-return', 'warm-resume',
)
ENVIRONMENT = (
    'serial', 'androidSdk', 'abi', 'viewport', 'density', 'fontScale',
    'animationScales', 'cpuCount', 'clockTicksPerSecond',
)
ANIMATIONS = ('window_animation_scale', 'transition_animation_scale',
              'animator_duration_scale')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def json_write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def git(root, *args):
    return subprocess.check_output(['git', *args], cwd=root, text=True,
                                   timeout=30).strip()


def input_identity(source, run, attempt):
    require(isinstance(source, str) and re.fullmatch('[0-9a-f]{40}', source),
            'A full source commit is required')
    require(isinstance(run, str) and re.fullmatch('[1-9][0-9]{0,19}', run),
            'A positive original build run is required')
    require(isinstance(attempt, str) and re.fullmatch('[1-9][0-9]{0,3}', attempt),
            'A positive original build attempt is required')
    return dict(sourceCommit=source, runId=run, runAttempt=attempt)


def select_push_run(rows, source, branch):
    matches = [row for row in rows if row.get('head_sha') == source
               and row.get('head_branch') == branch and row.get('event') == 'push']
    require(len(matches) <= 1, 'Ambiguous original push builds; use explicit workflow_dispatch inputs')
    if not matches:
        return None
    row = matches[0]
    require(row.get('run_attempt') == 1, 'Original push build was rerun; select its attempt explicitly')
    input_identity(source, str(row['id']), str(row['run_attempt']))
    return row


def select_inputs(args):
    """First push can run without registering dispatch on the default branch."""
    values = {key: os.environ.get(key, '') for key in
              ('MODE', 'BASELINE_SOURCE', 'BASELINE_RUN', 'BASELINE_ATTEMPT',
               'CANDIDATE_SOURCE', 'CANDIDATE_RUN', 'CANDIDATE_ATTEMPT', 'REPETITIONS')}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    receipt = dict(schema=1, status='in_progress', event=os.environ['GITHUB_EVENT_NAME'],
                   buildSelectionFrozen=False)
    json_write(args.report, receipt)
    try:
        if receipt['event'] == 'push':
            source = os.environ['GITHUB_SHA']
            branch = os.environ['GITHUB_REF_NAME']
            require(branch == 'release/gecko-2.0.16-experience', 'Automatic baseline branch differs')
            repository = os.environ['GITHUB_REPOSITORY']
            require(re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository), 'Invalid repository')
            base = 'https://api.github.com/repos/' + repository + '/actions/'

            def read(route):
                request = urllib.request.Request(base + route, headers={
                    'Authorization': 'Bearer ' + os.environ['GH_TOKEN'],
                    'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28'})
                with urllib.request.urlopen(request, timeout=30) as response:
                    return json.load(response)

            deadline, frozen = time.monotonic() + 2400, None
            while time.monotonic() < deadline:
                if frozen is None:
                    listing = read('workflows/gecko-integration.yml/runs?' + urllib.parse.urlencode(
                        dict(head_sha=source, event='push', per_page=100)))
                    frozen = select_push_run(listing['workflow_runs'], source, branch)
                    if frozen:
                        receipt.update(buildSelectionFrozen=True, sourceCommit=source,
                                       runId=str(frozen['id']), runAttempt=str(frozen['run_attempt']))
                        json_write(args.report, receipt)
                if frozen:
                    current = read('runs/' + str(frozen['id']))
                    require(current['head_sha'] == source and current['run_attempt'] == frozen['run_attempt'],
                            'Selected build attempt changed; no replacement build is allowed')
                    artifact_name = 'gecko-%s-%s-build' % (frozen['id'], frozen['run_attempt'])
                    artifacts = read('runs/%s/artifacts?per_page=100' % frozen['id'])['artifacts']
                    matches = [item for item in artifacts if item['name'] == artifact_name and not item['expired']]
                    require(len(matches) <= 1, 'Ambiguous build artifact')
                    if matches:
                        receipt['artifactId'] = matches[0]['id']
                        values.update(MODE='baseline', BASELINE_SOURCE=source, BASELINE_RUN=str(frozen['id']),
                                      BASELINE_ATTEMPT=str(frozen['run_attempt']), REPETITIONS='3')
                        break
                    require(current['status'] != 'completed', 'Selected original build completed without its exact artifact')
                time.sleep(20)
            else:
                raise TimeoutError('Original push build did not publish its exact artifact in 40 minutes')
        else:
            require(receipt['event'] == 'workflow_dispatch', 'Unsupported experiment trigger')
        require(values['MODE'] in ('baseline', 'compare'), 'Select baseline or compare')
        input_identity(values['BASELINE_SOURCE'], values['BASELINE_RUN'], values['BASELINE_ATTEMPT'])
        if values['MODE'] == 'compare':
            input_identity(values['CANDIDATE_SOURCE'], values['CANDIDATE_RUN'], values['CANDIDATE_ATTEMPT'])
        require(re.fullmatch(r'[1-9]|10', values['REPETITIONS']), 'Require 1..10 fixed repetitions')
        with args.output.open('a') as output:
            for key, value in values.items():
                # Unused candidate fields are omitted, never copied to output unchecked.
                if key.startswith('CANDIDATE_') and values['MODE'] == 'baseline':
                    continue
                output.write(key.lower() + '=' + value + '\n')
        receipt.update(status='passed', selected=values)
        json_write(args.report, receipt)
    except BaseException as error:
        receipt.update(status='failed', errorType=type(error).__name__, error=str(error))
        json_write(args.report, receipt)
        raise


def source_hashes(root, names):
    result = {}
    for name in names:
        path = Path(root) / name
        require(path.is_file() and not path.is_symlink(), 'Missing protocol file: ' + name)
        result[name] = sha(path)
    return result


def matching_protocol(baseline, candidate):
    require(set(baseline) == set(HARNESS + SETUP), 'Incomplete benchmark protocol')
    require(baseline == candidate, 'Benchmark or environment setup changed between builds')
    return baseline


def restore_build(root, bundle, source, run, attempt):
    root, bundle = Path(root).resolve(), Path(bundle).resolve()
    identity = input_identity(source, run, attempt)
    require(git(root, 'rev-parse', 'HEAD') == source, 'Checkout differs from selected source')
    require(not git(root, 'status', '--porcelain'), 'Benchmark checkout must be clean')
    # The original build identity is supplied only to the original bundle
    # validator; the benchmark workflow retains its own run identity elsewhere.
    env = dict(os.environ, GITHUB_RUN_ID=run, GITHUB_RUN_ATTEMPT=attempt,
               PYTHONDONTWRITEBYTECODE='1')
    subprocess.run([sys.executable, str(root / 'tools/gecko/ci_bundle.py'),
                    'restore', '--kind', 'build', '--bundle', str(bundle)],
                   cwd=root, env=env, check=True, timeout=300)
    index_path = root / 'work/gecko-integration/ci-build-index.json'
    index = json.loads(index_path.read_text())
    require(all(index.get(k) == value for k, value in identity.items()),
            'Restored build index identity mismatch')
    rows = [row for row in index['files'] if row['path'] == APK]
    require(len(rows) == 1, 'Exactly one integration APK is required')
    apk = root / APK
    digest = sha(apk)
    require(digest == rows[0]['sha256'] and apk.stat().st_size == rows[0]['bytes'],
            'Restored integration APK bytes differ')
    with zipfile.ZipFile(apk) as archive:
        stamp = json.loads(archive.read('assets/pocketchat-integration-build.json'))
    require(stamp['sourceCommit'] == source and stamp['sourceTree'] == index['sourceTree']
            and stamp['dirtySource'] is False, 'APK source stamp differs')
    return dict(identity, root=str(root), apk=str(apk), apkSha256=digest,
                apkBytes=apk.stat().st_size, sourceTree=index['sourceTree'],
                version=stamp['version'], versionCode=stamp['versionCode'],
                buildIndexSha256=sha(index_path), bundleSha256=sha(bundle),
                protocol=source_hashes(root, HARNESS + SETUP))


def product_inventory(root):
    return {str(path.relative_to(root)): sha(path)
            for path in sorted((root / 'app/src/main').rglob('*'))
            if path.is_file() and not path.is_symlink()}


def prepare(args):
    require(1 <= args.repetitions <= 10, 'Require 1..10 predeclared repetitions')
    require(not args.plan.exists(), 'The experiment plan is immutable; choose a new output')
    baseline = restore_build(args.baseline_root, args.baseline_bundle,
                             args.baseline_source, args.baseline_run, args.baseline_attempt)
    if args.mode == 'baseline':
        candidate = baseline
    else:
        require(all(getattr(args, 'candidate_' + key) for key in
                    ('root', 'bundle', 'source', 'run', 'attempt')),
                'Comparison requires both complete build identities')
        candidate = restore_build(args.candidate_root, args.candidate_bundle,
                                  args.candidate_source, args.candidate_run, args.candidate_attempt)
        require(candidate['sourceCommit'] != baseline['sourceCommit'],
                'Use baseline mode to measure repeatability of one source')
    protocol = matching_protocol(baseline['protocol'], candidate['protocol'])
    require(source_hashes(ROOT, SETUP) == {name: protocol[name] for name in SETUP},
            'Workflow runtime setup differs from selected builds')
    inventory_a = product_inventory(Path(baseline['root']))
    inventory_b = product_inventory(Path(candidate['root']))
    changed = [name for name in sorted(set(inventory_a) | set(inventory_b))
               if inventory_a.get(name) != inventory_b.get(name)]
    plan = dict(schema=1, mode=args.mode, order=['A', 'B', 'B', 'A'],
                repetitionsPerPhase=args.repetitions, cooldownSeconds=15,
                inputs={'A': baseline, 'B': candidate}, protocol=protocol,
                changedProductFiles=changed,
                comparisonToolSha256=sha(__file__),
                originalWorkloadRerun=False, physicalDeviceAcceptance=False,
                realChatGptAcceptance=False, releaseAcceptance=False)
    args.plan.parent.mkdir(parents=True, exist_ok=True)
    json_write(args.plan, plan)
    print(json.dumps(dict(status='prepared', mode=args.mode, order=plan['order'],
                          repetitionsPerPhase=args.repetitions,
                          changedProductFiles=changed)))


def finite(value):
    require(type(value) in (int, float) and math.isfinite(value) and value >= 0,
            'Missing, negative, or non-finite observed metric')
    return value


def values_summary(values):
    require(bool(values), 'An empty metric is not a zero')
    values = [finite(value) for value in values]
    ordered = sorted(values)
    return dict(count=len(values), raw=values, median=statistics.median(values),
                p95=ordered[math.ceil(.95 * len(ordered)) - 1],
                minimum=min(values), maximum=max(values))


def verify_report(report, build, label, repetitions, protocol):
    require(report.get('schema') == 1 and report.get('status') == 'passed',
            'Benchmark workload did not pass')
    require(report.get('label') == label and report.get('sourceCommit') == build['sourceCommit'],
            'Benchmark label/source differs')
    installed = report.get('buildIdentity', {})
    for key in ('sourceCommit', 'sourceTree', 'version', 'versionCode', 'apkSha256', 'apkBytes'):
        require(installed.get(key) == build[key], 'Installed benchmark identity differs: ' + key)
    require(installed.get('package') == PACKAGE and installed.get('dirtySource') is False,
            'Synthetic installed source identity required')
    require(report.get('runnerSha256') == protocol['tests/gecko/run_experience_benchmark.py']
            and report.get('activitySha256') == protocol['tests/gecko/ExperienceBenchmarkActivity.java'],
            'Actual benchmark observer differs')
    require(all(report.get(k) is False for k in
                ('releaseAcceptance', 'physicalDeviceAcceptance', 'realChatGptAcceptance')),
            'Benchmark scope was promoted to unrelated acceptance')
    require(type(report.get('predeclaredRepetitions')) is int
            and report.get('predeclaredRepetitions') == repetitions
            and len(report.get('iterations', [])) == repetitions,
            'A predeclared iteration is missing')
    for number, row in enumerate(report['iterations'], 1):
        require(type(row.get('index')) is int and row.get('index') == number and row.get('status') == 'passed',
                'A predeclared iteration failed or was replaced')
        require(tuple(action.get('name') for action in row.get('actions', [])) == ACTIONS,
                'The fixed action sequence differs')
        finite(row['startup']['activityCreateToReadyMs'])
        for action in row['actions']:
            finite(action['responseToDrawMs'])
    environment = report.get('environment', {})
    require(all(key in environment for key in ENVIRONMENT if key != 'cpuCount'), 'Missing device environment')
    require(environment['serial'] == SERIAL, 'Only the synthetic emulator is supported')
    require(set(environment['animationScales']) == set(ANIMATIONS)
            and all(float(value) == 1 for value in environment['animationScales'].values()),
            'Performance workload requires normal animation scales')
    return {key: environment.get(key) for key in ENVIRONMENT}


def summarize(reports):
    rows = [row for report in reports for row in report['iterations']]
    result = {
        'activityCreateToFixtureReadyMs': values_summary([r['startup']['activityCreateToReadyMs'] for r in rows]),
        'actionToNativeDrawMs': {
            name: values_summary([a['responseToDrawMs'] for r in rows for a in r['actions'] if a['name'] == name])
            for name in ACTIONS},
    }
    for key, field in (('cpuSecondsObserved', 'cpuSecondsObserved'),
                       ('cpuPercentOfOneCoreObserved', 'percentOfOneCore')):
        available = [r['cpu'][field] for r in rows if r.get('cpu', {}).get('available')]
        result[key] = (values_summary(available) if available else {'count': 0, 'unavailable': True})
        result[key]['missingIterations'] = len(rows) - len(available)
        result[key]['allLifetimesCovered'] = all(r.get('cpu', {}).get('completeProcessLifetimeCoverage') is True for r in rows)
    for stage in ('memoryReady', 'memoryFinal'):
        available = [r[stage]['totalPssKb'] for r in rows if r.get(stage, {}).get('available')]
        result[stage + 'PssKb'] = (values_summary(available) if available else {'count': 0, 'unavailable': True})
        result[stage + 'PssKb']['missingIterations'] = len(rows) - len(available)
    for field in ('productionPageUsableFromActivityCreateMs',):
        available = [r['startup'][field] for r in rows if r['startup'].get(field) is not None]
        result[field] = values_summary(available) if available else {'count': 0, 'unavailable': True}
        result[field]['missingIterations'] = len(rows) - len(available)
    for key, observations in (
            ('observedNativeHwuiFrameMs', [[f['durationMs'] for f in r.get('frames', {}).get('allNativeHwuiFrames', [])] for r in rows]),
            ('observedChoreographerGapMs', [r.get('frames', {}).get('allChoreographerGapsMs', []) for r in rows])):
        available = [value for iteration in observations for value in iteration]
        result[key] = values_summary(available) if available else {'count': 0, 'unavailable': True}
        result[key]['missingIterations'] = sum(not values for values in observations)
    result['measurementScope'] = 'Observed fixture startup and Android View draw, CPU observations and process-family PSS; no WAN, real-account, keyboard or physical compositor acceptance.'
    return result


def deltas(before, after):
    """Descriptive paired-condition statistics, never an automatic speed claim."""
    pairs = {'activityCreateToFixtureReadyMs':
             (before['activityCreateToFixtureReadyMs'], after['activityCreateToFixtureReadyMs'])}
    pairs.update({'actionToNativeDrawMs.' + name: (before['actionToNativeDrawMs'][name], after['actionToNativeDrawMs'][name])
                  for name in ACTIONS})
    for key in ('cpuSecondsObserved', 'cpuPercentOfOneCoreObserved', 'memoryReadyPssKb', 'memoryFinalPssKb',
                'productionPageUsableFromActivityCreateMs', 'observedNativeHwuiFrameMs', 'observedChoreographerGapMs'):
        if before[key].get('count') and after[key].get('count'):
            pairs[key] = (before[key], after[key])
    return {name: dict(baselineMedian=a['median'], candidateMedian=b['median'],
                       candidateMinusBaseline=b['median'] - a['median'],
                       percentChange=100 * (b['median'] - a['median']) / a['median'] if a['median'] else None)
            for name, (a, b) in pairs.items()}


def execute(args):
    plan = json.loads(args.plan.read_text())
    require(plan.get('schema') == 1 and plan.get('order') == ['A', 'B', 'B', 'A'],
            'A predeclared ABBA plan is required')
    require(plan['comparisonToolSha256'] == sha(__file__), 'Comparison tool changed after planning')
    require(not args.out.exists(), 'Keep every experiment; choose a new output directory')
    args.out.mkdir(parents=True)
    shutil.copy2(args.plan, args.out / 'plan.json')
    record = dict(schema=1, status='in_progress', mode=plan['mode'], order=plan['order'],
                  comparisonRunId=os.environ.get('GITHUB_RUN_ID', ''),
                  comparisonRunAttempt=os.environ.get('GITHUB_RUN_ATTEMPT', ''),
                  sameEmulatorRequired=True, phases=[], workloadReplayed=False,
                  physicalDeviceAcceptance=False, realChatGptAcceptance=False, releaseAcceptance=False)

    def persist():
        json_write(args.out / 'comparison-results.json', record)

    def adb(*parts, timeout=30):
        return subprocess.check_output([args.adb, '-s', SERIAL, *parts],
                                       text=True, timeout=timeout).strip()

    def device():
        return dict(bootId=adb('exec-out', 'cat', '/proc/sys/kernel/random/boot_id'),
                    fingerprint=adb('shell', 'getprop', 'ro.build.fingerprint'),
                    qemu=adb('shell', 'getprop', 'ro.kernel.qemu'),
                    sdk=adb('shell', 'getprop', 'ro.build.version.sdk'))

    counts = {'A': 0, 'B': 0}
    observed_environment = None
    reports = {'A': [], 'B': []}
    persist()
    try:
        original_device = device()
        require(original_device['qemu'] == '1' and original_device['sdk'] == '35'
                and re.fullmatch('[0-9a-f-]{36}', original_device['bootId']),
                'Actual pinned synthetic emulator is required')
        record['device'] = original_device
        persist()
        for position, condition in enumerate(plan['order'], 1):
            counts[condition] += 1
            label = ('baseline' if condition == 'A' else 'candidate' if plan['mode'] == 'compare' else 'baseline-repeat') + '-' + str(counts[condition])
            build = plan['inputs'][condition]
            root = Path(build['root'])
            require(git(root, 'rev-parse', 'HEAD') == build['sourceCommit']
                    and not git(root, 'status', '--porcelain'), 'Selected source checkout changed')
            require(source_hashes(root, HARNESS + SETUP) == plan['protocol'],
                    'Fixed benchmark/setup protocol changed')
            require(sha(build['apk']) == build['apkSha256'], 'Selected APK changed after planning')
            require(device() == original_device, 'The emulator rebooted or changed between conditions')
            phase = dict(position=position, condition=condition, label=label,
                         sourceCommit=build['sourceCommit'], apkSha256=build['apkSha256'],
                         status='in_progress', hostLoadAverage=Path('/proc/loadavg').read_text().strip())
            record['phases'].append(phase);persist()
            phase_dir = args.out / ('%02d-' % position + label)
            phase_dir.mkdir()
            # The formal package is never uninstalled or cleared. Separate CI
            # builds use different synthetic keys, so each condition starts from
            # an equally empty integration package, outside the timed workload.
            installed_path = subprocess.run([args.adb, '-s', SERIAL, 'shell', 'pm', 'path', PACKAGE],
                                            capture_output=True, text=True, timeout=30)
            json_write(phase_dir / 'package-before-install.json', dict(
                exitCode=installed_path.returncode, stdout=installed_path.stdout, stderr=installed_path.stderr))
            current = installed_path.stdout.strip()
            require(installed_path.returncode in (0, 1) and not installed_path.stderr.strip()
                    and (not current or (installed_path.returncode == 0 and current.startswith('package:'))),
                    'Cannot determine the installed synthetic package')
            if current:
                require(adb('uninstall', PACKAGE) == 'Success', 'Synthetic APK uninstall failed')
            require('Success' in adb('install', build['apk'], timeout=120), 'Synthetic APK install failed')
            setup_log = phase_dir / 'preflight.log'
            setup = root / 'work/gecko-integration/emulator-bootstrap-results.json'
            setup.unlink(missing_ok=True)
            try:
                with setup_log.open('w') as output:
                    subprocess.run([sys.executable, str(root / 'tools/gecko/prepare_emulator.py'),
                                    '--adb', args.adb, '--serial', SERIAL, '--apk', build['apk']],
                                   cwd=root, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'),
                                   stdout=output, stderr=subprocess.STDOUT, check=True, timeout=90)
            finally:
                if setup.is_file():
                    shutil.copy2(setup, phase_dir / setup.name)
            setup_value = json.loads(setup.read_text())
            require(setup_value['status'] == 'passed'
                    and setup_value['expectedBuildIdentity']['apkSha256'] == build['apkSha256'],
                    'Normal source/installed APK preflight failed')
            for name in ANIMATIONS:
                require(float(adb('shell', 'settings', 'get', 'global', name)) == 1,
                        'Normal animations changed before measurement')
            time.sleep(plan['cooldownSeconds'])
            destination = phase_dir / 'workload'
            command = [sys.executable, str(root / 'tests/gecko/run_experience_benchmark.py'),
                       '--adb', args.adb, '--serial', SERIAL, '--apk', build['apk'],
                       '--source', build['sourceCommit'], '--label', label, '--out', str(destination),
                       '--repetitions', str(plan['repetitionsPerPhase'])]
            phase['command'] = command;persist()
            with (phase_dir / 'workload.log').open('w') as output:
                subprocess.run(command, cwd=root, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'),
                               stdout=output, stderr=subprocess.STDOUT, check=True, timeout=1200)
            report_path = destination / 'experience-results.json'
            report = json.loads(report_path.read_text())
            observed = verify_report(report, build, label, plan['repetitionsPerPhase'], plan['protocol'])
            if observed_environment is None:
                observed_environment = observed
            require(observed_environment == observed, 'Device measurement settings changed between conditions')
            require(device() == original_device, 'Device identity changed during measurement')
            phase.update(status='passed', reportSha256=sha(report_path),
                         environment=observed, iterations=len(report['iterations']))
            reports[condition].append(report);persist()
        if plan['mode'] == 'baseline':
            record['baselineRepeatability'] = summarize(reports['A'] + reports['B'])
            record['interpretation'] = 'One unchanged build, all %d predeclared iterations retained. Baseline variability only; no optimization or improvement claim.' % (4 * plan['repetitionsPerPhase'])
        else:
            before, after = summarize(reports['A']), summarize(reports['B'])
            record.update(baseline=before, candidate=after,
                          descriptiveMedianChanges=deltas(before, after),
                          interpretation='ABBA condition medians are descriptive. Review raw distributions, observation availability and preservation checks before retaining any single product change; this tool makes no automatic improvement claim.')
        record.update(status='passed', changedProductFiles=plan['changedProductFiles'])
        persist()
    except BaseException as error:
        record.update(status='failed', errorType=type(error).__name__, error=str(error))
        if record['phases'] and record['phases'][-1]['status'] == 'in_progress':
            record['phases'][-1]['status'] = 'failed'
        persist()
        raise
    finally:
        record['rawEvidence'] = [dict(path=str(path.relative_to(args.out)), bytes=path.stat().st_size,
                                      sha256=sha(path))
                                 for path in sorted(args.out.rglob('*'))
                                 if path.is_file() and path.name != 'comparison-results.json']
        persist()
    print(json.dumps(dict(status=record['status'], mode=plan['mode'], phases=len(record['phases']),
                          sameDevice=True, workloadReplayed=False)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    select = commands.add_parser('select-inputs')
    select.add_argument('--output', type=Path, required=True)
    select.add_argument('--report', type=Path, required=True)
    stage = commands.add_parser('prepare')
    stage.add_argument('--mode', choices=('baseline', 'compare'), required=True)
    for condition in ('baseline', 'candidate'):
        for field in ('root', 'bundle', 'source', 'run', 'attempt'):
            stage.add_argument('--' + condition + '-' + field,
                               type=Path if field in ('root', 'bundle') else str,
                               required=condition == 'baseline')
    stage.add_argument('--repetitions', type=int, default=3)
    stage.add_argument('--plan', type=Path, required=True)
    run = commands.add_parser('run')
    run.add_argument('--plan', type=Path, required=True)
    run.add_argument('--adb', required=True)
    run.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    {'select-inputs': select_inputs, 'prepare': prepare, 'run': execute}[args.command](args)


if __name__ == '__main__':
    main()
