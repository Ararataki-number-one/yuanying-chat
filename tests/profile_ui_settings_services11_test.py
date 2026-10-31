"""Declared ADB/filesystem boundaries, not Android or notification acceptance."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import ui_settings_services11_contract as contract
import ui_visual_preservation_contract as original_ui

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/gecko'))
spec = importlib.util.spec_from_file_location('settings_services_device11', ROOT / 'tests/gecko/ui_settings_services_device11.py')
device = importlib.util.module_from_spec(spec)
spec.loader.exec_module(device)
SOURCE, TREE, APK_SHA = 'a' * 40, 'b' * 40, 'c' * 64
ENV = dict(CI='true', GITHUB_RUN_ID='123', GITHUB_RUN_ATTEMPT='1', GITHUB_SHA=SOURCE)
IDENTITY = dict(schema=1, package='local.pocketchat.test', sourceCommit=SOURCE, sourceTree=TREE,
                dirtySource=False, apkSha256=APK_SHA, version='2.0.46', versionCode=99)
INSTALLED = '/data/app/~~current=/local.pocketchat.test-xyz==/base.apk'


def package_dump(state, *, package=device.PACKAGE, user='0', installed='true'):
    return ('Packages:\n  Package [' + package + '] (a):\n'
            '    codePath=/product/priv-app/SettingsIntelligence\n'
            '    User ' + user + ': installed=' + installed + ' hidden=false enabled=' + str(state) + '\n'
            'Queries:\n  User 0: installed=true enabled=0\n')


class FakeAdb:
    """Only exact commands in the new lease are implemented; unknown calls fail."""
    def __init__(self, *, state=0, present=True, qemu='1', user='0', digest=APK_SHA,
                 paths=None, package_rows=None, disable_error=False,
                 confirm_disable=True, confirm_restore=True):
        self.state, self.present, self.qemu, self.user = state, present, qemu, user
        self.digest, self.paths, self.package_rows = digest, paths, package_rows
        self.disable_error, self.confirm_disable, self.confirm_restore = disable_error, confirm_disable, confirm_restore
        self.calls = []

    def __call__(self, *parts):
        self.calls.append(parts)
        if parts == ('shell', 'getprop', 'ro.kernel.qemu'):
            return self.qemu + '\n'
        if parts == ('shell', 'am', 'get-current-user'):
            return self.user + '\n'
        if parts == ('shell', 'pm', 'path', device.TEST_PACKAGE):
            return self.paths if self.paths is not None else 'package:' + INSTALLED + '\n'
        if parts == ('shell', 'sha256sum', INSTALLED):
            return self.digest + '  ' + INSTALLED + '\n'
        if parts == ('shell', 'pm', 'list', 'packages', '--user', '0', device.PACKAGE):
            return self.package_rows if self.package_rows is not None else ('package:' + device.PACKAGE + '\n' if self.present else '')
        if parts == ('shell', 'dumpsys', 'package', device.PACKAGE):
            return package_dump(self.state)
        if parts == ('shell', 'am', 'force-stop', '--user', '0', device.PACKAGE):
            return ''
        if parts == ('shell', 'pm', 'disable-user', '--user', '0', device.PACKAGE):
            if self.confirm_disable:
                self.state = 3
            if self.disable_error:
                raise subprocess.CalledProcessError(1, parts)
            return 'Package state changed\n'
        if parts in [('shell', 'pm', command, '--user', '0', device.PACKAGE) for command in ('default-state', 'enable')]:
            if self.confirm_restore:
                self.state = 0 if parts[2] == 'default-state' else 1
            return 'Package state restored\n'
        raise AssertionError(('Unexpected device boundary call', parts))

    def mutations(self):
        return [row for row in self.calls if 'disable-user' in row or 'force-stop' in row or 'default-state' in row or 'enable' in row]


class SettingsServicesLeaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.record_path = self.root / 'lease.json'

    def prepare(self, adb, **changes):
        # The device cases isolate the ADB boundary; the selected-source/APK
        # delegation is tested separately below, never called actual APK proof.
        args = dict(serial=device.SERIAL, environment=ENV, root=self.root, source=SOURCE, record_path=self.record_path)
        args.update(changes)
        with patch.object(device, 'expected_apk', return_value=copy.deepcopy(IDENTITY)) as expected:
            value = device.prepare_workflow(adb, **args)
        return value, expected

    def test_non_ci_never_inspects_a_device_or_build(self):
        for env in ({}, dict(ENV, CI='false'), dict(ENV, GITHUB_RUN_ID='0'), dict(ENV, GITHUB_RUN_ID='123\n')):
            with self.subTest(environment=env):
                adb = FakeAdb()
                lease, expected = self.prepare(adb, serial='physical-device', environment=env)
                expected.assert_not_called()
                self.assertEqual(adb.calls, [])
                self.assertEqual(lease.record['status'], 'not-ci-unchanged')

    def test_exact_run_attempt_and_ui_endpoint_required_before_build_or_device(self):
        for changes in [dict(serial=s) for s in ('emulator-5556', 'physical-device', 'emulator-5554\n', None)]:
            with self.subTest(changes=changes), self.assertRaisesRegex(RuntimeError, 'fixed UI synthetic endpoint'):
                self.prepare(FakeAdb(), **changes)
        for value in ('', '0', '1\n', '1;anything', True, 1):
            adb = FakeAdb()
            with self.subTest(attempt=value), self.assertRaisesRegex(RuntimeError, 'run attempt'):
                self.prepare(adb, environment=dict(ENV, GITHUB_RUN_ATTEMPT=value))
            self.assertEqual(adb.calls, [])

    def test_both_checkpoint_publisher_modes_use_identical_isolation(self):
        calls = []
        for publisher in ('true', 'false'):
            adb = FakeAdb()
            lease, _ = self.prepare(adb, environment=dict(ENV, GITHUB_ACTIONS=publisher))
            lease.restore()
            calls.append(adb.calls)
        self.assertEqual(calls[0], calls[1])

    def test_actual_qemu_user_and_installed_digest_required_before_any_mutation(self):
        for kwargs in (dict(qemu='0'), dict(qemu=''), dict(user='10'), dict(digest='d' * 64)):
            adb = FakeAdb(**kwargs)
            with self.subTest(kwargs=kwargs), self.assertRaises(RuntimeError):
                self.prepare(adb)
            self.assertEqual(adb.mutations(), [])

    def test_only_single_actual_data_app_test_apk_path_is_accepted(self):
        for value in ('', 'package:/sdcard/base.apk\n', 'package:' + INSTALLED + '\npackage:' + INSTALLED + '\n',
                      'package:/data/app/a/base.apk;anything\n', 'package:/data/app/a/split_config.apk\n'):
            adb = FakeAdb(paths=value)
            with self.subTest(path=value), self.assertRaises(RuntimeError):
                self.prepare(adb)
            self.assertEqual(adb.mutations(), [])

    def test_exact_package_is_required_and_absent_package_is_unchanged(self):
        adb = FakeAdb(present=False)
        lease, _ = self.prepare(adb)
        self.assertEqual(lease.record['status'], 'foreign-package-absent')
        lease.restore()
        self.assertEqual(adb.mutations(), [])
        for value in ('package:' + device.PACKAGE + '.other\n', 'package:' + device.PACKAGE + '\npackage:' + device.PACKAGE + '.other\n'):
            adb = FakeAdb(package_rows=value)
            with self.subTest(rows=value), self.assertRaisesRegex(RuntimeError, 'exact foreign package'):
                self.prepare(adb)
            self.assertEqual(adb.mutations(), [])

    def test_default_and_explicit_enabled_states_restore_exactly_once(self):
        for original, command in ((0, 'default-state'), (1, 'enable')):
            adb = FakeAdb(state=original)
            lease, expected = self.prepare(adb)
            expected.assert_called_once_with(self.root, SOURCE, ENV)
            self.assertEqual(adb.state, 3)
            self.assertEqual(lease.record['initialEnabledState'], original)
            self.assertEqual(lease.record['status'], 'foreign-package-disabled')
            lease.restore()
            lease.restore()
            self.assertEqual(adb.state, original)
            self.assertTrue(lease.record['restorationVerified'])
            self.assertEqual(adb.mutations(), [
                ('shell', 'pm', 'disable-user', '--user', '0', device.PACKAGE),
                ('shell', 'am', 'force-stop', '--user', '0', device.PACKAGE),
                ('shell', 'pm', command, '--user', '0', device.PACKAGE)])

    def test_preexisting_disabled_states_are_never_reenabled_or_reconfigured(self):
        for original in (2, 3, 4):
            adb = FakeAdb(state=original)
            lease, _ = self.prepare(adb)
            lease.restore()
            self.assertEqual(lease.record['status'], 'already-disabled-unchanged')
            self.assertEqual(adb.state, original)
            self.assertEqual(adb.mutations(), [])

    def test_uncertain_disable_failure_still_restores_the_owned_initial_state(self):
        adb = FakeAdb(state=1, disable_error=True)
        with self.assertRaises(subprocess.CalledProcessError):
            self.prepare(adb)
        self.assertEqual(adb.state, 1)
        record = json.loads(self.record_path.read_text())
        self.assertEqual(record['status'], 'failed')
        self.assertTrue(record['mutationAttempted'])
        self.assertTrue(record['restorationVerified'])

    def test_unconfirmed_disable_fails_without_workload_and_restores(self):
        adb = FakeAdb(confirm_disable=False)
        with self.assertRaisesRegex(RuntimeError, 'disabled-user state was not confirmed'):
            self.prepare(adb)
        self.assertEqual(adb.state, 0)
        self.assertTrue(json.loads(self.record_path.read_text())['restorationVerified'])

    def test_failed_preparation_record_write_still_restores(self):
        adb = FakeAdb()
        real_save = device.Lease.save
        calls = []
        def once_unwritable(lease):
            calls.append(1)
            if len(calls) == 1:
                raise OSError('declared record write failure')
            return real_save(lease)
        with patch.object(device.Lease, 'save', once_unwritable), self.assertRaises(OSError):
            self.prepare(adb)
        self.assertEqual(adb.state, 0)
        self.assertTrue(json.loads(self.record_path.read_text())['restorationVerified'])

    def test_failed_restore_makes_a_passed_workload_fail_and_keeps_diagnostics(self):
        adb = FakeAdb(confirm_restore=False)
        lease, _ = self.prepare(adb)
        report = dict(status='passed')
        with self.assertRaisesRegex(RuntimeError, 'not restored'):
            device.finish_workflow(lease, report)
        self.assertEqual(report['status'], 'failed')
        self.assertIn('deviceRestorationError', report)
        record = json.loads(self.record_path.read_text())
        self.assertFalse(record['restorationVerified'])
        self.assertEqual(record['restoreErrorType'], 'RuntimeError')

    def test_setup_and_restoration_failure_are_both_recorded(self):
        adb = FakeAdb(state=1, disable_error=True, confirm_restore=False)
        with self.assertRaisesRegex(RuntimeError, 'setup and exact restoration failed'):
            self.prepare(adb)
        record = json.loads(self.record_path.read_text())
        self.assertEqual(record['errorType'], 'CalledProcessError')
        self.assertEqual(record['restoreErrorType'], 'RuntimeError')
        self.assertFalse(record['restorationVerified'])

    def test_changed_device_or_apk_is_not_mutated_during_restore(self):
        for field, value in (('qemu', '0'), ('user', '10'), ('digest', 'd' * 64)):
            adb = FakeAdb()
            lease, _ = self.prepare(adb)
            setattr(adb, field, value)
            before = len(adb.mutations())
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                device.finish_workflow(lease, dict(status='passed'))
            self.assertEqual(len(adb.mutations()), before)
            self.assertFalse(lease.record['restorationVerified'])

    def test_failed_workload_keeps_its_original_error_after_successful_restore(self):
        adb = FakeAdb()
        lease, _ = self.prepare(adb)
        report = dict(status='failed', error='original workload failure')
        device.finish_workflow(lease, report)
        self.assertEqual(report, dict(status='failed', error='original workload failure'))
        self.assertEqual(adb.state, 0)
        self.assertFalse(lease.record['applicationNotificationsChanged'])
        self.assertFalse(lease.record['workloadChanged'])
        self.assertFalse(lease.record['releaseAcceptance'])


class EnabledStateBoundaryTests(unittest.TestCase):
    def test_real_structure_accepts_only_the_requested_package_user_member(self):
        for value in range(5):
            self.assertEqual(device.enabled_state(package_dump(value)), value)
        valid = package_dump(0)
        for changed in (package_dump(0, package=device.PACKAGE + '.other'), package_dump(0, user='10'),
                        package_dump(0, installed='false'), package_dump(True), package_dump(-1), package_dump(5),
                        valid.replace('enabled=0', 'enabled=0 enabled=1', 1),
                        valid.replace('    User 0:', '      User 0:', 1),
                        valid.replace('Queries:', '    User 0: installed=true enabled=0\nQueries:'),
                        valid + '  Package [' + device.PACKAGE + '] (b):\n    User 0: installed=true enabled=0\n'):
            with self.subTest(dump=changed), self.assertRaises(RuntimeError):
                device.enabled_state(changed)


class SourceBuildBindingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'app').mkdir()
        (self.root / 'app/build.gradle').write_text("versionName '2.0.46'; versionCode 99\n")

    def test_current_clean_source_and_version_delegate_to_original_apk_validator(self):
        with patch.object(device.subprocess, 'check_output', side_effect=[SOURCE, '', TREE]) as git, patch('profile_invocation_contract.expected_build', return_value=IDENTITY) as original:
            self.assertEqual(device.expected_apk(self.root, SOURCE, ENV), IDENTITY)
        original.assert_called_once_with(self.root / 'work/gecko-integration/ui-current.apk', SOURCE, TREE, '2.0.46', 99)
        self.assertEqual([call.args[0] for call in git.call_args_list], [
            ['git', 'rev-parse', 'HEAD'], ['git', 'status', '--porcelain', '--untracked-files=no'], ['git', 'rev-parse', 'HEAD^{tree}']])

    def test_source_workflow_dirty_tree_and_ambiguous_version_fail_before_apk_or_adb(self):
        cases = [(SOURCE, dict(ENV, GITHUB_SHA='d' * 40), [], None),
                 ('not-source', ENV, [], None),
                 (SOURCE, ENV, ['d' * 40], None),
                 (SOURCE, ENV, [SOURCE, ' M changed'], None),
                 (SOURCE, ENV, [SOURCE, '', 'not-tree'], None),
                 (SOURCE, ENV, [SOURCE, '', TREE], "versionName 'one'; versionName 'two'; versionCode 99")]
        for source, env, outputs, gradle in cases:
            with self.subTest(source=source, env=env, outputs=outputs):
                if gradle is not None:
                    (self.root / 'app/build.gradle').write_text(gradle)
                with patch.object(device.subprocess, 'check_output', side_effect=outputs), patch('profile_invocation_contract.expected_build') as original, self.assertRaises(RuntimeError):
                    device.expected_apk(self.root, source, env)
                original.assert_not_called()

    def test_original_sdk_apk_validation_failure_cannot_be_overridden(self):
        with patch.object(device.subprocess, 'check_output', side_effect=[SOURCE, '', TREE]), patch('profile_invocation_contract.expected_build', side_effect=ValueError('original invalid source or SDK identity')), self.assertRaisesRegex(ValueError, 'original invalid'):
            device.expected_apk(self.root, SOURCE, ENV)


class SourcePreservationTests(unittest.TestCase):
    def test_complete_actual_runner_inverse_recovers_all_original_bytes(self):
        raw = (ROOT / 'tests/gecko/run_ui_visuals.py').read_bytes()
        old = contract.require_runner_source(raw)
        self.assertEqual(hashlib.sha256(old).hexdigest(), contract.PREVIOUS_SHA256)
        self.assertEqual(old.count(b"timeout=90).decode(errors='replace')"), 1)
        self.assertTrue(original_ui.verify_shared_ui_source(raw.decode())['originalWorkloadSemanticsPreserved'])

    def test_unknown_bytes_and_partial_moved_or_changed_lease_are_rejected(self):
        raw = (ROOT / 'tests/gecko/run_ui_visuals.py').read_bytes()
        text = raw.decode()
        changed = [text + '\n# unreviewed change\n', text.replace(contract.PREPARATION, '', 1),
                   text.replace(contract.PREPARATION, contract.PREPARATION * 2, 1),
                   text.replace('finish_settings_services_device11(settings_services_device11,report)', 'pass', 1),
                   text.replace("record_path=out/'ui-settings-services-isolation.json'", "record_path=out/'other.json'", 1),
                   text.replace('environment=os.environ,root=root,source=source', 'environment={},root=root,source=source', 1),
                   text.replace('        finish_settings_services_device11(settings_services_device11,report)\n', "        pass\n", 1),
                   text.replace("timeout=90).decode(errors='replace')", "timeout=91).decode(errors='replace')", 1)]
        for source in changed:
            with self.subTest(sha=hashlib.sha256(source.encode()).hexdigest()), self.assertRaises(AssertionError):
                contract.require_runner_source(source.encode())
        for source in changed[1:]:
            with self.subTest(ast_sha=hashlib.sha256(source.encode()).hexdigest()), self.assertRaises(AssertionError):
                original_ui.verify_shared_ui_source(source)

    def test_shared_consumer_only_adds_two_precise_hooks_before_old_bodies(self):
        raw = (ROOT / 'tests/ui_visual_preservation_contract.py').read_bytes()
        for added in (b"import importlib.util\nfrom pathlib import Path\n\n_lease_spec = importlib.util.spec_from_file_location('selected_ui_settings_services11_contract', Path(__file__).with_name('ui_settings_services11_contract.py'))\n_lease = importlib.util.module_from_spec(_lease_spec)\n_lease_spec.loader.exec_module(_lease)\n",
                      b'    raw=_lease.original_runner_bytes(raw)\n',
                      b'    _lease.remove_reviewed_lease(tree)\n'):
            self.assertEqual(raw.count(added), 1)
            raw = raw.replace(added, b'', 1)
        self.assertEqual(hashlib.sha256(raw).hexdigest(), 'f828f323527565200e28dc1e87262c340767550cd5810228111a49e6c7dac09f')


if __name__ == '__main__':
    unittest.main(verbosity=2)
