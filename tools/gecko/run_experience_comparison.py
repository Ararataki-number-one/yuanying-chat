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
import uuid
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/gecko'))
import experience_scenarios as scenarios
import experience_process_identity as memory_identity
import experience_save_trace as save_trace
import native_input_contract as native_input
from native_input_driver import NativeInputDriver
from installed_apk_read import read_installed_apk
PACKAGE = 'local.pocketchat.test'
SERIAL = 'emulator-5554'
PHASE_TIMEOUT_SECONDS = 1200
REQUEST_PATH = '.github/experience-request.json'
APK = 'app/build/outputs/apk/integration/app-x86_64-integration.apk'
DRIVER_APK = 'work/gecko-integration/native-input-driver.apk'
DRIVER_BUILD = 'work/gecko-integration/native-input-driver-build.json'
DRIVER_OBSERVERS = (
    'tests/native-input-driver/NativeGestureProtocol.java',
    'tests/native-input-driver/NativeInputInstrumentation.java',
    'tests/native-input-driver/NativeInputShell.java',
    'tests/native-input-driver/AndroidManifest.xml',
    'tools/gecko/native_input_driver.py',
    'tools/gecko/native_input_contract.py',
)
HARNESS = (
    'tests/gecko/ExperienceBenchmarkActivity.java',
    'tests/gecko/ExperienceScenarios.java',
    'tests/gecko/ExperienceSaveSampling.java',
    'tools/gecko/experience_save_trace.py',
    'tools/gecko/run_experience_save_diagnostic.py',
    'tests/gecko/AndroidManifest.xml',
    'tools/gecko/experience_scenarios.py',
    'tools/gecko/experience_process_identity.py',
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
    'tests/native-input-driver/NativeGestureProtocol.java',
    'tests/native-input-driver/NativeInputInstrumentation.java',
    'tests/native-input-driver/NativeInputShell.java',
    'tests/native-input-driver/AndroidManifest.xml',
    'tools/gecko/native_input_driver.py',
    'tools/gecko/native_input_contract.py',
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
    'tools/gecko/build_native_input_driver.py',
    'tools/gecko/VerifyNativeInputSignature.java',
    'tools/gecko/installed_apk_read.py',
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


def verify_memory_observer(protocol):
    name='tools/gecko/experience_process_identity.py'
    require(sha(ROOT/name) == protocol[name] and sha(memory_identity.__file__) == protocol[name],
            'Workflow PSS identity observer differs from the selected protocol')


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


def declared_inputs(root, source, branch):
    """A dedicated push declares exact original builds; it never selects a run."""
    require(isinstance(source, str) and re.fullmatch('[0-9a-f]{40}', source),
            'Full orchestration source commit required')
    require(re.fullmatch(r'benchmark/experience-[A-Za-z0-9][A-Za-z0-9._-]{0,79}', branch),
            'Dedicated benchmark branch required')
    path = Path(root) / REQUEST_PATH
    require(path.is_file() and not path.is_symlink(), 'Regular fixed experiment request file required')
    require(path.stat().st_size <= 16384, 'Experiment request exceeds byte limit')
    raw = path.read_bytes()
    require(len(raw) <= 16384, 'Experiment request exceeds byte limit')

    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'Duplicate experiment request field: ' + key)
            result[key] = value
        return result

    value = json.loads(raw.decode('utf-8'), object_pairs_hook=unique_pairs)
    require(isinstance(value, dict) and type(value.get('schema')) is int and value['schema'] == 1,
            'Experiment request schema 1 required')
    require(value.get('mode') in ('baseline', 'compare'), 'Declared baseline or compare required')
    fields = {'schema', 'mode', 'baseline_source', 'baseline_run', 'baseline_attempt', 'scenario', 'repetitions'}
    if value['mode'] == 'compare':
        fields |= {'candidate_source', 'candidate_run', 'candidate_attempt'}
    require(set(value) == fields, 'Missing or unknown experiment request fields')
    require(all(isinstance(value[key], str) for key in fields - {'schema', 'repetitions'}),
            'Build references, mode and scenario must be strings')
    require(type(value['repetitions']) is int and 1 <= value['repetitions'] <= 10,
            'Declared repetitions must be an integer from 1 to 10')
    input_identity(value['baseline_source'], value['baseline_run'], value['baseline_attempt'])
    if value['mode'] == 'compare':
        input_identity(value['candidate_source'], value['candidate_run'], value['candidate_attempt'])
    scenario = scenarios.manifest(value['scenario'])
    require_phase_budget(scenario, value['repetitions'])
    selected = {key.upper(): str(item) for key, item in value.items() if key != 'schema'}
    return selected, dict(path=REQUEST_PATH, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(),
                          value=value, orchestrationSource=source, orchestrationBranch=branch,
                          selection='Explicit original build references; no run discovery or substitution')


def select_inputs(args):
    """First push can run without registering dispatch on the default branch."""
    values = {key: os.environ.get(key, '') for key in
              ('MODE', 'BASELINE_SOURCE', 'BASELINE_RUN', 'BASELINE_ATTEMPT',
               'CANDIDATE_SOURCE', 'CANDIDATE_RUN', 'CANDIDATE_ATTEMPT', 'REPETITIONS', 'SCENARIO')}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    receipt = dict(schema=1, status='in_progress', event=os.environ['GITHUB_EVENT_NAME'],
                   buildSelectionFrozen=False)
    json_write(args.report, receipt)
    try:
        if receipt['event'] == 'push' and os.environ.get('GITHUB_REF_NAME', '').startswith('benchmark/experience-'):
            values, request = declared_inputs(ROOT, os.environ.get('GITHUB_SHA', ''), os.environ['GITHUB_REF_NAME'])
            receipt.update(buildSelectionFrozen=True, request=request)
        elif receipt['event'] == 'push':
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
                                      BASELINE_ATTEMPT=str(frozen['run_attempt']), REPETITIONS='3', SCENARIO='core')
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
        values['SCENARIO'] = values['SCENARIO'] or 'core'
        scenario = scenarios.manifest(values['SCENARIO'])
        require_phase_budget(scenario, int(values['REPETITIONS']))
        with args.output.open('a') as output:
            for key, value in values.items():
                # Unused candidate fields are omitted, never copied to output unchecked.
                if key.startswith('CANDIDATE_') and values['MODE'] == 'baseline':
                    continue
                output.write(key.lower() + '=' + value + '\n')
        receipt.update(status='passed', selected=values, scenarioManifest=scenario,
                       scenarioManifestSha256=scenarios.digest(scenario))
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


def indexed_file(root, index, name):
    rows = [row for row in index['files'] if row.get('path') == name]
    require(len(rows) == 1, 'Exactly one original build input is required: ' + name)
    path = Path(root) / name
    require(path.is_file() and not path.is_symlink(), 'Missing regular build input: ' + name)
    require(type(rows[0].get('bytes')) is int and rows[0]['bytes'] == path.stat().st_size
            and rows[0].get('sha256') == sha(path), 'Original build input bytes differ: ' + name)
    return path


def driver_identity(root, index, source, run, attempt):
    """Bind each role's own signed helper; source equality is checked separately."""
    apk = indexed_file(root, index, DRIVER_APK)
    receipt = indexed_file(root, index, DRIVER_BUILD)
    build = native_input.decode(receipt.read_bytes())
    read_source = lambda commit, path: subprocess.check_output(
        ['git', 'show', commit + ':' + path], cwd=root, timeout=30)
    native_input.verify_build(build, source, read_source)
    native_input.verify_signature_logs(receipt.parent, build)
    for name in (*build['signatureLogs'], *build['signatureApiLogs'], native_input.SIGNATURE_API):
        indexed_file(root, index, 'work/gecko-integration/' + name)
    require(all(build.get(key) == value for key, value in
                dict(sourceCommit=source, sourceTree=index['sourceTree'], runId=run, runAttempt=attempt).items()),
            'Input driver belongs to another original build')
    require(build.get('status') == 'built' and build.get('compileOnly') is False
            and build.get('testOnly') is True, 'A real test-only driver build is required')
    require(build.get('apkSha256') == sha(apk) and build.get('apkBytes') == apk.stat().st_size,
            'Input driver APK differs from its build receipt')
    require(isinstance(build.get('signerCertificateSha256'), str)
            and re.fullmatch('[0-9a-f]{64}', build['signerCertificateSha256']),
            'Original driver signing certificate identity is required')
    with zipfile.ZipFile(apk) as archive:
        name = 'assets/native-input-driver-build.json'
        require(archive.namelist().count(name) == 1 and 'classes.dex' in archive.namelist(),
                'Input driver has no unique source asset or executable code')
        raw = archive.read(name)
    stamp = native_input.decode(raw)
    require(native_input.sha(raw) == build.get('assetSha256')
            and all(key in build and type(value) is type(build[key]) and value == build[key]
                    for key, value in stamp.items()), 'Embedded input driver identity differs')
    for key in ('schema', 'sourceCommit', 'sourceTree', 'runId', 'runAttempt', 'packageName',
                'targetPackage', 'instrumentationTargetPackage', 'instrumentation', 'protocols', 'inputs',
                'executionBackend', 'entryPoint', 'executionUid', 'inputTargetUidEnforced'):
        require(stamp.get(key) == build[key], 'Embedded input driver identity missing: ' + key)
    return dict(apk=str(apk), receipt=str(receipt), apkSha256=sha(apk), apkBytes=apk.stat().st_size,
                receiptSha256=sha(receipt), signerCertificateSha256=build['signerCertificateSha256'], build=build)


def prepare_target_proof(build, directory, adb):
    directory = Path(directory);directory.mkdir(parents=True, exist_ok=False)
    paths = subprocess.check_output([adb, '-s', SERIAL, 'shell', 'pm', 'path', PACKAGE],
                                    text=True, timeout=30).splitlines()
    require(len(paths) == 1 and paths[0].startswith('package:/data/app/'),
            'Exactly one installed role target APK is required')
    nonce = uuid.uuid4().hex
    # The full transferred APK is identical to the already indexed build and
    # stays in the role checkout's private cache. Preserve the original range
    # receipt in the raw artifact, without uploading four duplicate large APKs.
    cache = Path(build['root']) / 'work/experience-installed-readbacks'
    cache.mkdir(parents=True, exist_ok=True)
    proof = directory / 'installed-target-byte-proof.json'
    read_installed_apk(adb=adb, serial=SERIAL, installed_path=paths[0][len('package:'):],
        destination=cache / (nonce + '.apk'), expected_sha256=build['apkSha256'],
        expected_bytes=build['apkBytes'], diagnostics=proof, label='experience-phase-' + nonce)
    actual = native_input.decode(proof.read_bytes())
    require(actual.get('status') == 'verified-bytes' and actual.get('actualInstalledApkRead') is True
            and actual.get('actualFileSha256') == build['apkSha256']
            and actual.get('actualFileBytes') == build['apkBytes'], 'Actual installed target byte proof failed')
    return dict(path=str(proof), sha256=sha(proof), sourceCommit=build['sourceCommit'],
                sourceTree=build['sourceTree'], runId=build['runId'], runAttempt=build['runAttempt'],
                targetApkSha256=build['apkSha256'], preparationOutsideTimedWorkload=True)


def prepare_driver(build, directory, adb, target_proof):
    """Install only this role's self-target driver, outside the timed workload."""
    selected = build['nativeInputDriver']
    nonce = uuid.uuid4().hex
    directory = Path(directory)
    started = time.monotonic_ns()
    NativeInputDriver(root=Path(build['root']), out=directory, adb=adb, serial=SERIAL, nonce=nonce,
        target_apk=Path(build['apk']), expected_source=build['sourceCommit'],
        driver_apk=Path(selected['apk']), build_receipt=Path(selected['receipt']),
        target_byte_proof=Path(target_proof), install=True)
    path = directory / ('native-input-setup-' + nonce + '.json')
    actual = native_input.decode(path.read_bytes())
    require(actual.get('sourceCommit') == build['sourceCommit'] and actual.get('nonce') == nonce
            and actual.get('installationRequested') is True and actual.get('actualInstalledApkRead') is True,
            'Input driver preparation did not read the installed role APK')
    for key in ('apkSha256', 'apkBytes', 'signerCertificateSha256'):
        require(actual.get(key) == selected[key], 'Installed prepared driver identity differs: ' + key)
    return dict(sourceCommit=build['sourceCommit'], runId=build['runId'], runAttempt=build['runAttempt'],
                driverApkSha256=selected['apkSha256'], buildReceiptSha256=selected['receiptSha256'],
                rawSetup=path.name, rawSetupSha256=sha(path), hostStartedMonotonicNs=started,
                hostCompletedMonotonicNs=time.monotonic_ns(), preparationOutsideTimedWorkload=True)


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
    driver = driver_identity(root, index, source, run, attempt)
    return dict(identity, root=str(root), apk=str(apk), apkSha256=digest,
                apkBytes=apk.stat().st_size, sourceTree=index['sourceTree'],
                version=stamp['version'], versionCode=stamp['versionCode'],
                buildIndexSha256=sha(index_path), bundleSha256=sha(bundle),
                protocol=source_hashes(root, HARNESS + SETUP), nativeInputDriver=driver)


def product_inventory(root):
    return {str(path.relative_to(root)): sha(path)
            for path in sorted((root / 'app/src/main').rglob('*'))
            if path.is_file() and not path.is_symlink()}


def require_phase_budget(scenario, repetitions):
    require(type(repetitions) is int and 1 <= repetitions <= 10, 'Require 1..10 predeclared repetitions')
    idle = scenario.get('idle', {})
    minimum = repetitions * (idle.get('foregroundMs', 0) + idle.get('backgroundMs', 0))
    require(minimum < PHASE_TIMEOUT_SECONDS * 1000,
            'Fixed idle intervals already consume the entire 1200-second phase budget; reduce repetitions before planning')


def prepare(args):
    require(1 <= args.repetitions <= 10, 'Require 1..10 predeclared repetitions')
    scenario = scenarios.manifest(args.scenario)
    require_phase_budget(scenario, args.repetitions)
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
    verify_memory_observer(protocol)
    require(sha(ROOT / 'tools/gecko/experience_scenarios.py') == protocol['tools/gecko/experience_scenarios.py'],
            'Planner scenario inputs differ from selected builds')
    require(source_hashes(ROOT, SETUP) == {name: protocol[name] for name in SETUP},
            'Workflow runtime setup differs from selected builds')
    require(source_hashes(ROOT, DRIVER_OBSERVERS) == {name: protocol[name] for name in DRIVER_OBSERVERS},
            'Workflow input driver differs from selected builds')
    inventory_a = product_inventory(Path(baseline['root']))
    inventory_b = product_inventory(Path(candidate['root']))
    changed = [name for name in sorted(set(inventory_a) | set(inventory_b))
               if inventory_a.get(name) != inventory_b.get(name)]
    plan = dict(schema=1, mode=args.mode, order=['A', 'B', 'B', 'A'],
                scenarioManifest=scenario, scenarioManifestSha256=scenarios.digest(scenario),
                repetitionsPerPhase=args.repetitions, cooldownSeconds=15,
                inputs={'A': baseline, 'B': candidate}, protocol=protocol,
                changedProductFiles=changed,
                comparisonToolSha256=sha(__file__),
                originalWorkloadRerun=False, physicalDeviceAcceptance=False,
                realChatGptAcceptance=False, releaseAcceptance=False)
    args.plan.parent.mkdir(parents=True, exist_ok=True)
    json_write(args.plan, plan)
    print(json.dumps(dict(status='prepared', mode=args.mode, order=plan['order'],
                          scenarioManifest=scenario, scenarioManifestSha256=scenarios.digest(scenario),
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


def retained_raw(report, root, name):
    require(root is not None, 'Original benchmark raw evidence is required')
    path = Path(root) / name
    require(path.is_file() and not path.is_symlink()
            and Path(root).resolve() in path.resolve().parents, 'Missing original benchmark input evidence: ' + name)
    rows = [item for item in report.get('rawEvidence', []) if item.get('path') == name]
    require(len(rows) == 1, 'Missing or duplicate raw evidence index: ' + name)
    raw = path.read_bytes()
    require(type(rows[0].get('bytes')) is int and rows[0]['bytes'] == len(raw)
            and rows[0].get('sha256') == native_input.sha(raw), 'Raw benchmark evidence bytes differ: ' + name)
    return raw


def verify_driver_iteration(report, row, build, protocol, raw_root):
    selected = build['nativeInputDriver']
    driver_build = selected['build']
    require(all(driver_build['inputs'][name] == protocol[name] for name in native_input.INPUTS),
            'Compiled input driver differs from the fixed protocol')
    require(driver_build['signatureVerifierSourceSha256'] == protocol[native_input.SIGNATURE_VERIFIER],
            'Input signature verifier differs from the fixed setup')
    for key in ('sourceCommit', 'sourceTree', 'runId', 'runAttempt'):
        require(driver_build[key] == build[key], 'Driver role identity differs: ' + key)
    prefix = 'iteration-%02d/' % row['index']
    build_raw = retained_raw(report, raw_root, prefix + 'native-input-driver-build.json')
    require(native_input.sha(build_raw) == selected['receiptSha256']
            and native_input.decode(build_raw) == driver_build, 'Retained role driver build receipt differs')
    for name in (*driver_build['signatureLogs'], *driver_build['signatureApiLogs'], native_input.SIGNATURE_API):
        retained_raw(report, raw_root, prefix + name)
    native_input.verify_signature_logs(Path(raw_root) / prefix, driver_build)
    evidence = row['nativeInputDriver']
    require(evidence.get('purpose') == 'formal-collapse'
            and isinstance(evidence.get('nonce'), str) and re.fullmatch('[0-9a-f]{32}', evidence['nonce'])
            and evidence.get('buildSha256') == selected['receiptSha256'], 'Formal input evidence identity differs')
    setup = native_input.decode(retained_raw(report, raw_root,
        prefix + 'native-input-setup-' + evidence['nonce'] + '.json'))
    require(setup.get('sourceCommit') == build['sourceCommit'] and setup.get('nonce') == evidence['nonce']
            and setup.get('installationRequested') is False and setup.get('actualInstalledApkRead') is True
            and all(setup.get(key) == selected[key] for key in ('apkSha256', 'apkBytes', 'signerCertificateSha256')),
            'Iteration must verify the already prepared role driver without reinstalling')
    proof_raw = retained_raw(report, raw_root, prefix + 'native-input-target-proof-' + evidence['nonce'] + '.json')
    require(native_input.sha(proof_raw) == report['targetByteProofSha256'], 'Original target byte proof changed')
    proof = native_input.decode(proof_raw)
    native_input.verify_target_proof(proof, build['apkSha256'], build['apkBytes'])
    receipts = evidence.get('receipts')
    require(isinstance(receipts, list) and len(receipts) == 1
            and receipts[0].get('gesture') == 'formal-collapse', 'Exactly one formal collapse invocation is required')
    receipt = receipts[0]
    name = 'native-input-' + evidence['nonce'] + '-formal-collapse.json'
    require(receipt.get('file') == name, 'Unexpected formal input receipt path')
    raw = retained_raw(report, raw_root, prefix + name)
    require(receipt.get('sha256') == native_input.sha(raw), 'Actual formal input receipt hash differs')
    for suffix in ('-stdout.log', '-stderr.log'):
        retained_raw(report, raw_root, prefix + name[:-5] + suffix)
    actual = native_input.decode(raw)
    request = receipt['request']
    require(request['targetByteProofSha256'] == report['targetByteProofSha256']
            and request['targetApkPath'] == proof['installedApkPath']
            and request['targetApkBytes'] == build['apkBytes'], 'Gesture did not use the original role byte proof')
    observed = row['collapseInput']
    armed = observed['armed']
    require(armed.get('name') == 'collapse' and armed.get('target') == 'collapsed'
            and type(armed.get('armedUptimeMs')) is int and armed['armedUptimeMs'] > 0
            and type(armed.get('expiresUptimeMs')) is int
            and armed['expiresUptimeMs'] == armed['armedUptimeMs'] + 15000
            and request['expiresUptimeMs'] == armed['expiresUptimeMs'], 'Original 15-second action deadline changed')
    first, last = observed['from'], observed['to']
    require(len(first) == len(last) == 2 and all(type(n) is int and n >= 0 for n in first + last)
            and first[0] == last[0] == request['x'] and request['startY'] == first[1]
            and request['endY'] == last[1], 'Original collapse endpoints changed')
    native_input.verify_receipt(actual, build=driver_build, purpose='formal-collapse', nonce=evidence['nonce'],
                                gesture='formal-collapse', target_apk=build['apkSha256'], request=request)
    require(actual['signerCertificateSha256'] == selected['signerCertificateSha256'],
            'Installed role driver certificate differs')
    require(actual['startedUptimeMs'] >= armed['armedUptimeMs'], 'One-shot driver started outside the armed action')
    require(observed['startupMs'] == actual['startupMs'] and observed['readyUptimeMs'] == actual['readyUptimeMs'],
            'Automation startup observation differs from its raw receipt')
    require(type(receipt.get('hostStartedMonotonicNs')) is int
            and type(receipt.get('hostCompletedMonotonicNs')) is int
            and 0 < receipt['hostStartedMonotonicNs'] <= receipt['hostCompletedMonotonicNs'],
            'Driver host invocation interval missing')
    require(observed.get('armedActionToReadyMs') == actual['readyUptimeMs'] - armed['armedUptimeMs']
            and observed.get('hostInvocationMs') == (receipt['hostCompletedMonotonicNs'] - receipt['hostStartedMonotonicNs']) / 1000000,
            'Whole armed/host automation intervals differ from original clocks')
    action = next(item for item in row['actions'] if item['name'] == 'collapse')
    touches = actual['trace']['events']
    require(action['inputUpUptimeMs'] == touches[-1]['eventTime']
            and action['inputDurationMs'] == touches[-1]['eventTime'] - touches[0]['eventTime']
            and action['drawUptimeMs'] >= action['inputUpUptimeMs'],
            'Target ACTION_UP measurement differs from actual driver events')
    transfers = native_input.decode(retained_raw(report, raw_root, prefix + 'experienceBenchmark-transport.json'))
    owned = []
    for transfer in transfers:
        raw = transfer['rawUtf8'].encode('utf-8')
        pointer = transfer['receipt']
        require(pointer['payloadBytes'] == len(raw) and pointer['payloadSha256'] == native_input.sha(raw),
                'Original app event transport bytes differ')
        envelope = native_input.decode(raw)
        require(envelope['runNonce'] == pointer['runNonce'] == evidence['nonce']
                and envelope['sourceCommit'] == build['sourceCommit']
                and envelope['buildIdentity']['apkSha256'] == build['apkSha256'],
                'App observation belongs to another driver invocation or role')
        owned.append(envelope['event'])
    require(any(event.get('kind') == 'armed' and event.get('result') == armed for event in owned),
            'Original owned armed event is missing')
    require(any(event.get('kind') == 'measurement' and event.get('result') == action for event in owned),
            'Original target collapse measurement is missing')
    return tuple(actual[key] for key in ('targetApkPathBefore', 'targetApkBytesBefore',
                                        'targetLastModifiedBefore', 'targetLastUpdateBefore'))


def verify_report(report, build, label, repetitions, protocol, scenario=None, *, raw_root=None,
                  target_proof_sha256=None):
    require(report.get('schema') == 1 and report.get('status') == 'passed',
            'Benchmark workload did not pass')
    require(report.get('label') == label and report.get('sourceCommit') == build['sourceCommit'],
            'Benchmark label/source differs')
    scenario = scenarios.manifest('core') if scenario is None else scenario
    require(report.get('scenarioManifest') == scenario and report.get('scenarioManifestSha256') == scenarios.digest(scenario),
            'Fixed scenario input manifest differs')
    require(report.get('executionInputsUnchanged') is True, 'Measurement sources changed during execution')
    require(isinstance(target_proof_sha256, str) and re.fullmatch('[0-9a-f]{64}', target_proof_sha256)
            and report.get('targetByteProofSha256') == target_proof_sha256,
            'Benchmark target byte proof is not bound to this phase')
    for name in ('tests/gecko/run_experience_benchmark.py', 'tests/gecko/ExperienceBenchmarkActivity.java',
                 'tests/gecko/ExperienceScenarios.java', 'tools/gecko/experience_scenarios.py',
                 'tools/gecko/experience_process_identity.py', *DRIVER_OBSERVERS):
        require(report.get('observerFiles', {}).get(name) == protocol[name], 'Actual scenario observer differs: ' + name)
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
    original_target_fence = None
    input_nonces = set()
    for number, row in enumerate(report['iterations'], 1):
        require(type(row.get('index')) is int and row.get('index') == number and row.get('status') == 'passed',
                'A predeclared iteration failed or was replaced')
        require(tuple(action.get('name') for action in row.get('actions', [])) == ACTIONS,
                'The fixed action sequence differs')
        target_fence = verify_driver_iteration(report, row, build, protocol, raw_root)
        nonce = row['nativeInputDriver']['nonce']
        require(nonce not in input_nonces, 'An input-driver invocation was reused across iterations')
        input_nonces.add(nonce)
        if original_target_fence is None:
            original_target_fence = target_fence
        require(target_fence == original_target_fence, 'Measured APK metadata changed while reusing the phase byte proof')
        verify_scenario(row, scenario)
        snapshots = [row['memoryReady'], row['memoryFinal']]
        snapshots += [snapshot for window in row['scenarioWindows']
                      for snapshot in (window['memoryBefore'], window['memoryAfter'])]
        for snapshot in snapshots:
            memory_identity.verify(snapshot, PACKAGE, memory_identity.parse_stat, scenarios.pss_value)
        finite(row['startup']['activityCreateToReadyMs'])
        for action in row['actions']:
            finite(action['responseToDrawMs'])
    controls = report.get('pssIdentityNegativeControls', {})
    require(controls == dict(path='pss-identity-negative-controls.json', count=6,
            afterTimedIterations=True, extraDeviceReads=0, originalSnapshot='iteration-01.memoryReady'),
            'New original-raw PSS identity negative controls missing or scope changed')
    control_payload = native_input.decode(retained_raw(report, raw_root, controls['path']))
    original_snapshot = report['iterations'][0]['memoryReady']
    require(control_payload.get('schema') == 1 and control_payload.get('originalSnapshot') == original_snapshot,
            'PSS negative controls are not bound to this phase actual original snapshot')
    expected_controls = memory_identity.negative_controls(original_snapshot['rawEvidence'], PACKAGE,
                                                         memory_identity.parse_stat, scenarios.pss_value)
    require(control_payload.get('cases') == expected_controls,
            'Retained original-raw PSS negative controls differ from strict replay')
    environment = report.get('environment', {})
    require(all(key in environment for key in ENVIRONMENT if key != 'cpuCount'), 'Missing device environment')
    require(environment['serial'] == SERIAL, 'Only the synthetic emulator is supported')
    require(set(environment['animationScales']) == set(ANIMATIONS)
            and all(float(value) == 1 for value in environment['animationScales'].values()),
            'Performance workload requires normal animation scales')
    return {key: environment.get(key) for key in ENVIRONMENT}


def verify_scenario(row, scenario):
    name = scenario['name']
    seed = row.get('seed', {}).get('scenario', {})
    require(seed.get('manifest') == scenario and seed.get('manifestSha256') == scenarios.digest(scenario),
            'Actual device seed differs from frozen input')
    windows = row.get('scenarioWindows', [])
    expected = ['history-save'] if name.startswith('download-history-') else ['idle-foreground', 'idle-background'] if name == 'idle-120' else []
    require([w.get('name') for w in windows] == expected, 'Scenario windows missing/reordered/replayed')
    for window in windows:
        start, end = window['start'], window['end']
        elapsed = finite(end['elapsedRealtimeMs'] - start['elapsedRealtimeMs'])
        require(elapsed == window['elapsedDurationMs'], 'Scenario boundary clocks differ')
        require(window.get('frameLimitReached') is False and window.get('lifecycleChanges') == 0,
                'Frame capture truncated or lifecycle changed within fixed window')
        if name == 'idle-120':
            require(elapsed >= 120000, 'Idle observation shorter than fixed input')
        else:
            saves = window.get('saves', [])
            require([s.get('step') for s in saves] == list(range(1, 9)), 'Actual save sequence incomplete')
            for step, save in enumerate(saves, 1):
                finite(save['durationMs'])
                require(save.get('received') == step * 65536 and save.get('method') == 'DownloadTasks.save'
                        and save.get('httpTransferMeasured') is False, 'Persistence workload/scope differs')
            verify = window.get('verification', {})
            count = scenario['downloadHistory']['savedRows']
            require(verify.get('savedRows') == count and verify.get('taskRows') == count + 1
                    and verify.get('verifiedProgressBytes') == 8 * 65536
                    and verify.get('actualAndroidSQLite') is True and verify.get('actualAndroidSharedPreferences') is True,
                    'Actual final persistence verification incomplete')


def summarize(reports):
    rows = [row for report in reports for row in report['iterations']]
    result = {
        'activityCreateToFixtureReadyMs': values_summary([r['startup']['activityCreateToReadyMs'] for r in rows]),
        'actionToNativeDrawMs': {
            name: values_summary([a['responseToDrawMs'] for r in rows for a in r['actions'] if a['name'] == name])
            for name in ACTIONS},
    }
    startups = [r['collapseInput']['startupMs'] for r in rows if 'startupMs' in r.get('collapseInput', {})]
    result['automation'] = dict(
        driverOnStartToReadyMs=values_summary(startups) if startups else {'count': 0, 'unavailable': True},
        missingIterations=len(rows) - len(startups),
        scope='The retained driverOnStartToReadyMs field now measures shell entry-to-READY and excludes process creation. Armed-action-to-READY additionally retains event handoff and process launch; host invocation includes transport, the gesture and receipt collection. These are automation intervals, not user app startup or an app bottleneck; no subtraction from original action or whole-flow metrics.')
    for name in ('armedActionToReadyMs', 'hostInvocationMs'):
        values = [r['collapseInput'][name] for r in rows if name in r.get('collapseInput', {})]
        result['automation'][name] = values_summary(values) if values else {'count': 0, 'unavailable': True}
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
    result['scenarioWindows'] = {}
    names = sorted({w['name'] for r in rows for w in r.get('scenarioWindows', [])})
    for name in names:
        windows = [w for r in rows for w in r.get('scenarioWindows', []) if w['name'] == name]
        measured = {'elapsedDurationMs': values_summary([w['elapsedDurationMs'] for w in windows]),
                    'cpuScope': 'Observed process-family lower bound over contained sample envelopes; inspect missing/lifetime/attribution coverage in raw windows.',
                    'frameScope': 'Delivered native HWUI only, not full Gecko or display presentation. Empty reports mean unobserved.'}
        for metric, available in (
            ('cpuSecondsObserved', [w['cpu']['cpuSecondsObserved'] for w in windows if w.get('cpu', {}).get('available')]),
            ('memoryBeforePssKb', [w['memoryBefore']['totalPssKb'] for w in windows if w.get('memoryBefore', {}).get('available')]),
            ('memoryAfterPssKb', [w['memoryAfter']['totalPssKb'] for w in windows if w.get('memoryAfter', {}).get('available')])):
            measured[metric] = values_summary(available) if available else {'count': 0, 'unavailable': True}
            measured[metric]['missingWindows'] = len(windows)-len(available)
        saves = [s['durationMs'] for w in windows for s in w.get('saves', [])]
        if saves:
            measured['productionSaveDurationMs'] = values_summary(saves)
            measured['saveScope'] = 'Actual main-thread DownloadTasks.save with controlled paused-record changes; no HTTP transfer.'
        frames = [f['durationMs'] for w in windows for f in w.get('nativeHwuiFrames', [])]
        measured['nativeHwuiDurationMs'] = values_summary(frames) if frames else {'count': 0, 'unavailable': True}
        if frames:
            measured['nativeHwuiDurationMs'].update(over32MsCount=sum(v > 32 for v in frames), over100MsCount=sum(v > 100 for v in frames),
                droppedFrameReports=sum(f.get('droppedReports', 0) for w in windows for f in w.get('nativeHwuiFrames', [])))
        gaps = [f['durationMs'] for w in windows for f in w.get('choreographerFrames', [])]
        measured['choreographerGapMs'] = values_summary(gaps) if gaps else {'count': 0, 'unavailable': True}
        if gaps:
            measured['choreographerGapMs'].update(over32MsCount=sum(v > 32 for v in gaps), over100MsCount=sum(v > 100 for v in gaps))
        result['scenarioWindows'][name] = measured
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
    for name in sorted(set(before.get('scenarioWindows', {})) & set(after.get('scenarioWindows', {}))):
        a, b = before['scenarioWindows'][name], after['scenarioWindows'][name]
        for field in ('elapsedDurationMs', 'cpuSecondsObserved', 'memoryBeforePssKb', 'memoryAfterPssKb', 'productionSaveDurationMs', 'nativeHwuiDurationMs'):
            if a.get(field, {}).get('count') and b.get(field, {}).get('count'):
                pairs['scenario.' + name + '.' + field] = (a[field], b[field])
    return {name: dict(baselineMedian=a['median'], candidateMedian=b['median'],
                       candidateMinusBaseline=b['median'] - a['median'],
                       percentChange=100 * (b['median'] - a['median']) / a['median'] if a['median'] else None)
            for name, (a, b) in pairs.items()}


def execute(args):
    plan = json.loads(args.plan.read_text())
    require(plan.get('schema') == 1 and plan.get('order') == ['A', 'B', 'B', 'A'],
            'A predeclared ABBA plan is required')
    require(plan.get('scenarioManifest') == scenarios.manifest(plan.get('scenarioManifest', {}).get('name'))
            and plan.get('scenarioManifestSha256') == scenarios.digest(plan['scenarioManifest']), 'Scenario plan differs')
    require_phase_budget(plan['scenarioManifest'], plan['repetitionsPerPhase'])
    verify_memory_observer(plan['protocol'])
    require(sha(ROOT / 'tools/gecko/experience_scenarios.py') == plan['protocol']['tools/gecko/experience_scenarios.py'],
            'Scenario inputs changed after planning')
    require(plan['comparisonToolSha256'] == sha(__file__), 'Comparison tool changed after planning')
    require(source_hashes(ROOT, SETUP + DRIVER_OBSERVERS)
            == {name: plan['protocol'][name] for name in SETUP + DRIVER_OBSERVERS},
            'Workflow input driver/setup changed after planning')
    require(not args.out.exists(), 'Keep every experiment; choose a new output directory')
    args.out.mkdir(parents=True)
    shutil.copy2(args.plan, args.out / 'plan.json')
    record = dict(schema=1, status='in_progress', mode=plan['mode'], order=plan['order'],
                  comparisonRunId=os.environ.get('GITHUB_RUN_ID', ''),
                  comparisonRunAttempt=os.environ.get('GITHUB_RUN_ATTEMPT', ''),
                  scenarioManifest=plan['scenarioManifest'], scenarioManifestSha256=plan['scenarioManifestSha256'],
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
            index_path = root / 'work/gecko-integration/ci-build-index.json'
            require(sha(index_path) == build['buildIndexSha256'], 'Original build index changed after planning')
            require(driver_identity(root, native_input.decode(index_path.read_bytes()), build['sourceCommit'],
                        build['runId'], build['runAttempt']) == build['nativeInputDriver'],
                    'Selected role input driver changed after planning')
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
            phase['targetByteProof'] = prepare_target_proof(build, phase_dir / 'target-byte-read', args.adb)
            phase['nativeInputPreparation'] = prepare_driver(build, phase_dir / 'input-driver-setup', args.adb,
                                                            phase['targetByteProof']['path'])
            persist()
            time.sleep(plan['cooldownSeconds'])
            destination = phase_dir / 'workload'
            command = [sys.executable, str(root / 'tests/gecko/run_experience_benchmark.py'),
                       '--adb', args.adb, '--serial', SERIAL, '--apk', build['apk'],
                       '--source', build['sourceCommit'], '--label', label, '--out', str(destination),
                       '--driver-apk', build['nativeInputDriver']['apk'],
                       '--driver-build', build['nativeInputDriver']['receipt'],
                       '--target-byte-proof', phase['targetByteProof']['path'],
                       '--repetitions', str(plan['repetitionsPerPhase']), '--scenario', plan['scenarioManifest']['name']]
            phase['command'] = command;persist()
            with (phase_dir / 'workload.log').open('w') as output:
                subprocess.run(command, cwd=root, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'),
                               stdout=output, stderr=subprocess.STDOUT, check=True, timeout=PHASE_TIMEOUT_SECONDS)
            report_path = destination / 'experience-results.json'
            report = json.loads(report_path.read_text())
            observed = verify_report(report, build, label, plan['repetitionsPerPhase'], plan['protocol'],
                                     plan['scenarioManifest'], raw_root=destination,
                                     target_proof_sha256=phase['targetByteProof']['sha256'])
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
        # Persist the complete original summaries before any profiling starts.
        persist()
        run_post_baseline_diagnostic(args, plan, record, reports)
        require(device() == original_device, 'Device identity changed during the extra diagnostic')
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


def diagnostic_preconditions(plan, record, reports):
    """No extra tracing before every original timed sample was strictly accepted."""
    if plan['mode'] != 'baseline' or not plan['scenarioManifest']['name'].startswith('download-history-'):
        return False
    require(plan['order'] == ['A', 'B', 'B', 'A'] and len(record['phases']) == 4
            and [phase['condition'] for phase in record['phases']] == plan['order']
            and all(phase['status'] == 'passed' and phase['iterations'] == plan['repetitionsPerPhase'] for phase in record['phases']),
            'All original four phases must pass before the extra diagnostic')
    require(len(reports['A']) == len(reports['B']) == 2
            and all(len(report['iterations']) == plan['repetitionsPerPhase']
                    and report['status'] == 'passed'
                    and all(row['status'] == 'passed' and tuple(action['name'] for action in row['actions']) == ACTIONS for row in report['iterations'])
                    for report in reports['A'] + reports['B']),
            'All original timed iterations/actions must complete before the extra diagnostic')
    require(record.get('baselineRepeatability') == summarize(reports['A'] + reports['B']),
            'Original timed summary must finish unchanged before extra profiling')
    require('historySaveSampling' not in record.get('diagnostics', {}), 'Never replay an extra diagnostic')
    for name in save_trace.OBSERVERS:
        require(sha(ROOT / name) == plan['protocol'][name], 'Actual workflow diagnostic observer differs: ' + name)
    require(Path(save_trace.__file__).resolve() == (ROOT / 'tools/gecko/experience_save_trace.py').resolve(), 'Imported diagnostic decoder is outside the verified source')
    return True


def run_post_baseline_diagnostic(args, plan, record, reports):
    if not diagnostic_preconditions(plan, record, reports):
        return
    build = plan['inputs']['A']
    directory = args.out / 'diagnostics' / 'history-save-sampling'
    directory.mkdir(parents=True, exist_ok=False)
    destination = directory / 'capture'
    entry = dict(status='in_progress', selectedRole='A', sourceCommit=build['sourceCommit'],
                 sourceTree=build['sourceTree'], runId=build['runId'], runAttempt=build['runAttempt'],
                 apkSha256=build['apkSha256'], diagnosticOnly=True,
                 performanceComparisonAllowed=False, priorTimedIterations=4 * plan['repetitionsPerPhase'])
    record.setdefault('diagnostics', {})['historySaveSampling'] = entry
    original_error = None
    try:
        require(git(Path(build['root']), 'rev-parse', 'HEAD') == build['sourceCommit']
                and source_hashes(Path(build['root']), HARNESS + SETUP) == plan['protocol'], 'Selected diagnostic source changed after the timed samples')
        entry['targetByteProofBefore'] = prepare_target_proof(build, directory / 'installed-byte-read-before', args.adb)
        command = [sys.executable, str(Path(build['root']) / 'tools/gecko/run_experience_save_diagnostic.py'),
                   '--plan', str(args.plan.resolve()), '--adb', args.adb, '--serial', SERIAL, '--out', str(destination)]
        entry['command'] = command
        with (directory / 'diagnostic-runner.log').open('w') as output:
            result = subprocess.run(command, cwd=build['root'], env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'),
                                    stdout=output, stderr=subprocess.STDOUT, timeout=420, check=False)
        require(result.returncode == 0, 'Extra sampling diagnostic failed; its original trace and failure evidence are retained')
    except BaseException as error:
        original_error = error
    finally:
        path = destination / save_trace.RESULT_FILE
        if path.is_file():
            entry.update(reportPath=str(path.relative_to(args.out)), reportSha256=sha(path))
            try: entry['captureStatus'] = json.loads(path.read_text()).get('status')
            except BaseException as error:
                entry['captureReportParseError'] = type(error).__name__ + ': ' + str(error)
                if original_error is None: original_error = error
        if 'targetByteProofBefore' in entry:
            try: entry['targetByteProofAfter'] = prepare_target_proof(build, directory / 'installed-byte-read-after', args.adb)
            except BaseException as error:
                entry['postCaptureByteProofError'] = type(error).__name__ + ': ' + str(error)
                if original_error is None: original_error = error
        if original_error is not None:
            entry.update(status='failed', errorType=type(original_error).__name__, error=str(original_error))
    if original_error is not None:
        raise original_error
    try:
        require(path.is_file(), 'Original extra diagnostic report missing')
        # Re-audit the APK's actual embedded source/SDK identity, independent of
        # report labels, and replay both app envelopes and the original trace.
        from profile_invocation_contract import expected_build
        expected = expected_build(Path(build['apk']), build['sourceCommit'], build['sourceTree'], build['version'], build['versionCode'])
        value = json.loads(path.read_text())
        save_trace.verify_diagnostic(value, expected, plan['protocol'], plan['scenarioManifest'], destination, build)
        entry.update(status='passed', additionalRealSaveCalls=8, excludedFromAllTimedStatistics=True)
    except BaseException as error:
        entry.update(status='failed', errorType=type(error).__name__, error=str(error)); raise


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
    stage.add_argument('--scenario', choices=scenarios.NAMES, default='core')
    stage.add_argument('--plan', type=Path, required=True)
    run = commands.add_parser('run')
    run.add_argument('--plan', type=Path, required=True)
    run.add_argument('--adb', required=True)
    run.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    {'select-inputs': select_inputs, 'prepare': prepare, 'run': execute}[args.command](args)


if __name__ == '__main__':
    main()
