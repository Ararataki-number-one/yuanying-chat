"""Fail-closed public phase-two gates; fixtures here are never device evidence."""
import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import sys
import shutil
import unittest

ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec); spec.loader.exec_module(result)
    return result


C = module('phase2_contract', ROOT / 'tools/gecko/network_sources_contract.py')
SOURCE, APK = 'a' * 40, 'c' * 64


class HostWrapperTest(unittest.TestCase):
    def test_child_errors_missing_fields_and_wrong_identity_cannot_become_passed(self):
        sys.path.insert(0, str(ROOT / 'tools/gecko'))
        try:
            wrapper = module('settings_host_wrapper', ROOT / 'tools/gecko/run_network_settings_host_checks.py')
        finally:
            sys.path.pop(0)
        for kind in (*C.SETTINGS_HOST_MINIMUMS, 'ui'):
            value = dict(status='passed', actualAndroidExecution=False, sourceCommit=SOURCE)
            if kind == 'ui':
                value.pop('status')
                value['results'] = {'UiSnapshotTest': {'passed': 39, 'total': 39},
                                    'NetworkOptimizationPolicyTest': {'passed': 49, 'scope': 'Synthetic control of actual passed-only schema'}}
            else:
                count = C.SETTINGS_HOST_MINIMUMS[kind]
                value.update(passed=count, checks=[{'name': str(i), 'pass': True} for i in range(count)])
            args = (kind, SOURCE, 'desktop', C.SETTINGS_JSON_SHA256['desktop'])
            self.assertEqual(wrapper.bind_host_report(value, *args)['status'], 'passed')
            mutations = [lambda r: r.update(status='failed'), lambda r: r.update(sourceCommit='f' * 40),
                         lambda r: r.update(actualAndroidExecution=True), lambda r: r.pop('actualAndroidExecution'),
                         lambda r: r.update(diagnosticOnly=True), lambda r: r.update(sourceDirty=True),
                         lambda r: r.update(dirty=True)]
            if kind == 'ui':
                mutations += [lambda r: r.pop('results'), lambda r: r['results'].clear(),
                              lambda r: r['results']['UiSnapshotTest'].update(passed=0),
                              lambda r: r['results']['NetworkOptimizationPolicyTest'].pop('passed'),
                              lambda r: r['results']['NetworkOptimizationPolicyTest'].update(passed=48),
                              lambda r: r['results']['NetworkOptimizationPolicyTest'].update(total=48)]
            else:
                mutations += [lambda r: r.pop('checks'), lambda r: r['checks'].clear(),
                              lambda r: r['checks'][0].update({'pass': False})]
            for mutate in mutations:
                wrong = copy.deepcopy(value); mutate(wrong); before = copy.deepcopy(wrong)
                with self.subTest(kind=kind), self.assertRaises((AssertionError, KeyError)):
                    wrapper.bind_host_report(wrong, *args)
                self.assertEqual(wrong, before, 'A rejected child report must remain unmodified')


class SettingsReleaseGateTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='settings-public-gate-')
        self.addCleanup(temporary.cleanup); self.directory = Path(temporary.name)
        self.reports = {}
        for mode in ('retry', 'application', 'internal'):
            fixture = module('synthetic_' + mode, ROOT / ('tests/gecko_settings_' + mode + '_gate_test.py'))
            value = fixture.receipt()
            verifier, path = C._settings_verifier(mode)
            value.update(installedPackage='local.pocketchat.test', installedApkSha256=APK,
                         runnerOneAttempt=True, runnerSha256=hashlib.sha256(path.read_bytes()).hexdigest())
            value['buildIdentity']['apkSha256'] = APK
            self.reports['network-settings-' + mode + '-results.json'] = value
        internal = self.reports['network-settings-internal-results.json']
        self.core = {'recipe': {'version': internal['coreVersion']},
                     'binaries': {'x86_64': {'sha256': internal['coreSha256']}}}
        for implementation, digest in C.SETTINGS_JSON_SHA256.items():
            for kind, minimum in list(C.SETTINGS_HOST_MINIMUMS.items()) + [('ui', 0)]:
                value = dict(status='passed', sourceCommit=SOURCE, ciSourceDirty=False,
                             actualAndroidExecution=False,
                             ciHost={'jsonImplementation': implementation, 'jsonJarSha256': digest})
                if kind == 'ui':
                    value['results'] = {'UiSnapshotTest': {'passed': 39, 'total': 39},
                                        'NetworkOptimizationPolicyTest': {'passed': 49, 'scope': 'Synthetic control of actual passed-only schema'}}
                else:
                    value.update(passed=minimum, checks=[{'name': 'synthetic-' + str(i), 'pass': True} for i in range(minimum)])
                self.reports['network-settings-' + kind + '-' + implementation + '-host-results.json'] = value
        self.reports['network-settings-parser-negative-results.json'] = dict(
            status='passed', sourceCommit=SOURCE, ciSourceDirty=False, actualAndroidExecution=False,
            suites={name: dict(testsRun=count, successful=True, failures=0, errors=0, skipped=0,
                               sourceSha256='d' * 64) for name, count in C.SETTINGS_PARSER_SUITES.items()})

    def verify(self, reports=None):
        for path in self.directory.glob('*'): path.unlink()
        for name, value in (self.reports if reports is None else reports).items():
            (self.directory / name).write_text(json.dumps(value))
        return C.verify_network_settings(self.directory, SOURCE, self.core, APK)

    def test_all_required_reports_and_real_verifiers_accept_their_synthetic_controls(self):
        result = self.verify()
        self.assertEqual(set(result['actualAndroidChecks']), {'retry', 'application', 'internal'})
        self.assertEqual(len(result['productionHostChecks']), 8)

    def test_every_missing_or_failed_required_report_is_rejected(self):
        for name in C.SETTINGS_REPORTS:
            for mode in ('missing', 'failed', 'other-source'):
                reports = copy.deepcopy(self.reports)
                if mode == 'missing': reports.pop(name)
                elif mode == 'failed': reports[name]['status'] = 'failed'
                else: reports[name]['sourceCommit'] = 'f' * 40
                with self.subTest(name=name, mode=mode), self.assertRaises((AssertionError, FileNotFoundError)):
                    self.verify(reports)

    def test_android_build_runner_scope_and_real_case_guards_are_required(self):
        for mode in ('retry', 'application', 'internal'):
            key = 'network-settings-' + mode + '-results.json'
            for field, wrong in (('installedApkSha256', 'f' * 64), ('runnerSha256', 'f' * 64),
                                 ('runnerOneAttempt', False), ('actualAndroidExecution', False), ('runNonce', 'bad')):
                reports = copy.deepcopy(self.reports); reports[key][field] = wrong
                with self.subTest(mode=mode, field=field), self.assertRaises(AssertionError): self.verify(reports)
            reports = copy.deepcopy(self.reports)
            field = 'retryCases' if mode == 'retry' else 'applicationCases' if mode == 'application' else 'internalApplicationCases'
            # Use the exact fixture's case collection; deletion must reach its real verifier.
            if field not in reports[key]:
                field = 'cases'
            reports[key][field].pop()
            with self.subTest(mode=mode, field=field), self.assertRaises(AssertionError): self.verify(reports)
        reports = copy.deepcopy(self.reports); reports['network-settings-internal-results.json']['coreSha256'] = 'f' * 64
        with self.assertRaises(AssertionError): self.verify(reports)

    def test_each_host_and_parser_boundary_is_required(self):
        for implementation in C.SETTINGS_JSON_SHA256:
            for kind in (*C.SETTINGS_HOST_MINIMUMS, 'ui'):
                key = 'network-settings-' + kind + '-' + implementation + '-host-results.json'
                reports = copy.deepcopy(self.reports); reports[key]['actualAndroidExecution'] = True
                with self.assertRaises(AssertionError): self.verify(reports)
                reports = copy.deepcopy(self.reports)
                if kind == 'ui': reports[key]['results']['UiSnapshotTest']['passed'] = 38
                else: reports[key]['checks'][0]['pass'] = False
                with self.assertRaises(AssertionError): self.verify(reports)
        for name in C.SETTINGS_PARSER_SUITES:
            for field, wrong in (('testsRun', 0), ('successful', False), ('skipped', 1), ('errors', 1)):
                reports = copy.deepcopy(self.reports)
                reports['network-settings-parser-negative-results.json']['suites'][name][field] = wrong
                with self.assertRaises(AssertionError): self.verify(reports)


class SharingReleaseGateTest(unittest.TestCase):
    def fixture(self):
        cases = json.loads((ROOT / 'tests/gecko/assets/sharing-schema-matrix.json').read_text())['cases']
        evidence = [dict(case=row['id'], sourceHash=hashlib.sha256(row['source'].encode()).hexdigest(),
                         exportHash='d' * 64, originalFingerprint='e' * 64, exportFingerprint='e' * 64,
                         actualNativeFingerprintVerified=True, actualEncryptedCatalogCandidate=True,
                         activeSnapshotPreserved=True, temporarySourceDeleted=True) for row in cases]
        return dict(status='passed', actualAndroidExecution=True, actualNativeExecution=True,
                    buildIdentity={'sourceCommit': SOURCE, 'apkSha256': APK}, runToken='b' * 32,
                    checkCount=66, checks=[{'name': 'synthetic-' + str(i), 'pass': True} for i in range(66)],
                    schemaFingerprintCount=31, schemaFingerprintEvidence=evidence)

    def test_real_shared_matrix_verifier_accepts_exact_synthetic_control(self):
        self.assertEqual(C.verify_network_sharing(self.fixture(), SOURCE, APK)['nativeSchemaFingerprints'], 31)

    def test_matrix_order_native_equivalence_cache_readback_and_identity_fail_closed(self):
        mutations = [lambda r: r['schemaFingerprintEvidence'].pop(),
                     lambda r: r['schemaFingerprintEvidence'].reverse(),
                     lambda r: r['buildIdentity'].update(sourceCommit='f' * 40),
                     lambda r: r['buildIdentity'].update(apkSha256='f' * 64)]
        for field, wrong in [('sourceHash', 'f' * 64), ('originalFingerprint', ''),
                             ('exportFingerprint', 'f' * 64), ('actualNativeFingerprintVerified', False),
                             ('actualEncryptedCatalogCandidate', False), ('activeSnapshotPreserved', False),
                             ('temporarySourceDeleted', False)]:
            mutations.append(lambda r, f=field, w=wrong: r['schemaFingerprintEvidence'][0].update({f: w}))
        for mutate in mutations:
            value = self.fixture(); mutate(value)
            with self.assertRaises(AssertionError): C.verify_network_sharing(value, SOURCE, APK)

    def test_existing_android_runner_uses_the_same_public_verifier_at_both_boundaries(self):
        tree = ast.parse((ROOT / 'tests/gecko/run_network_sharing.py').read_text())
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name) and node.func.id == 'verify_network_sharing']
        self.assertEqual(len(calls), 2)
        self.assertTrue(any(any(k.arg == 'complete' and isinstance(k.value, ast.Constant) and k.value.value is True
                                for k in call.keywords) for call in calls))


class SignedInventoryTest(unittest.TestCase):
    def test_actual_version70_staging_retains_required_reports_and_standalone_verifiers(self):
        source = ROOT / 'tools/publish-gecko-release.py'
        tree = ast.parse(source.read_text())
        additions = [node for node in tree.body if isinstance(node, ast.If)
                     and isinstance(node.test, ast.Compare) and isinstance(node.test.left, ast.Name)
                     and node.test.left.id == 'version_code' and len(node.test.comparators) == 1
                     and isinstance(node.test.comparators[0], ast.Constant) and node.test.comparators[0].value == 70]
        self.assertEqual(len(additions), 2)
        with tempfile.TemporaryDirectory(prefix='signed-settings-inventory-') as temporary:
            stage = Path(temporary); (stage / 'tools/gecko').mkdir(parents=True)
            namespace = dict(version_code=70, root=ROOT, stage=stage, shutil=shutil,
                             performance_files=['original-required-result.json'])
            sys.path.insert(0, str(ROOT / 'tools'))
            try:
                exec(compile(ast.Module(body=additions, type_ignores=[]), str(source), 'exec'), namespace)
            finally:
                sys.path.pop(0)
            self.assertEqual(namespace['performance_files'], ['original-required-result.json'] + C.SETTINGS_REPORTS)
            shutil.copy2(ROOT / 'tools/gecko/network_sources_contract.py', stage / 'tools/gecko/network_sources_contract.py')
            staged = module('standalone_public_settings', stage / 'tools/gecko/network_sources_contract.py')
            for mode in ('retry', 'application', 'internal'):
                verifier, path = staged._settings_verifier(mode)
                original = ROOT / ('tests/gecko/run_network_settings_' + mode + '.py')
                self.assertEqual(path.read_bytes(), original.read_bytes())
                self.assertTrue(callable(verifier.verify))
            fixture = SharingReleaseGateTest().fixture()
            self.assertEqual(staged.verify_network_sharing(fixture, SOURCE, APK)['nativeSchemaFingerprints'], 31)


if __name__ == '__main__': unittest.main()
