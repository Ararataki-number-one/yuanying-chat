"""CI device preparation is narrow; the original UI gestures remain unchanged."""
import hashlib
import importlib.util
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('ui_test_device', ROOT / 'tools/gecko/ui_test_device.py')
device = importlib.util.module_from_spec(spec)
spec.loader.exec_module(device)


class FakeAdb:
    def __init__(self, *, qemu='1', present=True, disabled=False, accept=True, similarly_named=False):
        self.qemu, self.present, self.disabled = qemu, present, disabled
        self.accept, self.similarly_named = accept, similarly_named
        self.calls = []

    def __call__(self, *args):
        self.calls.append(args)
        if args == ('shell', 'getprop', 'ro.kernel.qemu'):
            return self.qemu + '\n'
        if args[:4] == ('shell', 'pm', 'list', 'packages'):
            visible = self.present and ('-d' not in args or self.disabled)
            return ('package:' + device.SYSTEM_PACKAGE + '\n' if visible else '') + (
                'package:' + device.SYSTEM_PACKAGE + '.other\n' if self.similarly_named else '')
        if args == ('shell', 'am', 'force-stop', '--user', '0', device.SYSTEM_PACKAGE):
            return ''
        if args == ('shell', 'pm', 'disable-user', '--user', '0', device.SYSTEM_PACKAGE):
            if self.accept:
                self.disabled = True
            return 'package state changed\n'
        raise AssertionError(('Unexpected device command', args))


class UiTestDeviceTests(unittest.TestCase):
    def test_checkpoint_publisher_override_does_not_change_device_preparation(self):
        recorded = []
        for publisher in ('true', 'false'):
            adb = FakeAdb()
            value = device.prepare_workflow(adb, serial='emulator-5554',
                environment={'CI': 'true', 'GITHUB_RUN_ID': '123456', 'GITHUB_ACTIONS': publisher})
            self.assertEqual(value['status'], 'foreign-package-disabled')
            recorded.append(adb.calls)
        self.assertEqual(recorded[0], recorded[1])

    def test_workflow_identity_is_required_before_device_inspection(self):
        for env in ({}, {'CI': 'true'}, {'GITHUB_RUN_ID': '123'},
                    {'CI': 'false', 'GITHUB_RUN_ID': '123'},
                    *({'CI': 'true', 'GITHUB_RUN_ID': run} for run in ('0', '-1', '1;anything', '1\n', '1' * 21, 123, True))):
            with self.subTest(environment=env):
                adb = FakeAdb()
                self.assertEqual(device.prepare_workflow(adb, serial='physical-device', environment=env)['status'], 'not-ci-unchanged')
                self.assertEqual(adb.calls, [])

    def test_non_ci_does_not_even_inspect_or_mutate_any_device(self):
        for ci in (False, None, 'true', 1):
            with self.subTest(ci=ci):
                adb = FakeAdb()
                self.assertEqual(device.prepare(adb, ci=ci, serial='physical-device')['status'], 'not-ci-unchanged')
                self.assertEqual(adb.calls, [])

    def test_physical_or_malformed_serial_fails_before_any_command(self):
        for serial in ('physical-device', 'emulator-5554;anything', 'emulator-5554\n', '', None):
            with self.subTest(serial=serial):
                adb = FakeAdb()
                with self.assertRaisesRegex(RuntimeError, 'explicit CI emulator'):
                    device.prepare(adb, ci=True, serial=serial)
                self.assertEqual(adb.calls, [])

    def test_emulator_serial_alone_is_not_a_device_confirmation(self):
        for flag in ('0', '', 'true'):
            with self.subTest(flag=flag):
                adb = FakeAdb(qemu=flag)
                with self.assertRaisesRegex(RuntimeError, 'confirmed emulator'):
                    device.prepare(adb, ci=True, serial='emulator-5554')
                self.assertEqual(adb.calls, [('shell', 'getprop', 'ro.kernel.qemu')])

    def test_absent_and_similarly_named_packages_are_not_mutated(self):
        for similarly_named in (False, True):
            adb = FakeAdb(present=False, similarly_named=similarly_named)
            self.assertEqual(device.prepare(adb, ci=True, serial='emulator-5554')['status'], 'foreign-package-absent')
            self.assertFalse(any('force-stop' in c or 'disable-user' in c for c in adb.calls))

    def test_only_the_exact_foreign_package_is_disabled_and_read_back(self):
        self.assertEqual(device.SYSTEM_PACKAGE, 'com.google.android.apps.wellbeing')
        adb = FakeAdb(similarly_named=True)
        value = device.prepare(adb, ci=True, serial='emulator-5554')
        self.assertEqual(value['status'], 'foreign-package-disabled')
        self.assertFalse(value['previouslyDisabled'])
        mutations = [c for c in adb.calls if 'force-stop' in c or 'disable-user' in c]
        self.assertEqual(mutations, [('shell', 'am', 'force-stop', '--user', '0', device.SYSTEM_PACKAGE),
                                     ('shell', 'pm', 'disable-user', '--user', '0', device.SYSTEM_PACKAGE)])
        self.assertTrue(adb.disabled)
        self.assertIs(value['applicationNotificationsChanged'], False)
        self.assertIs(value['workloadChanged'], False)
        self.assertIs(value['previousFailureCauseProven'], False)

    def test_previously_disabled_package_is_not_reenabled_or_reconfigured(self):
        adb = FakeAdb(disabled=True)
        self.assertTrue(device.prepare(adb, ci=True, serial='emulator-5554')['previouslyDisabled'])
        self.assertFalse(any('disable-user' in c or 'enable' in c for c in adb.calls))

    def test_unconfirmed_disable_is_a_failure_not_a_success_or_retry(self):
        adb = FakeAdb(accept=False)
        with self.assertRaisesRegex(RuntimeError, 'not confirmed'):
            device.prepare(adb, ci=True, serial='emulator-5554')
        self.assertEqual(sum('disable-user' in c for c in adb.calls), 1)

    def test_command_failure_propagates_without_running_the_workload(self):
        def unavailable(*args):
            raise subprocess.CalledProcessError(1, args)
        with self.assertRaises(subprocess.CalledProcessError):
            device.prepare(unavailable, ci=True, serial='emulator-5554')

    def test_runner_preserves_every_original_byte_except_one_preparation_block(self):
        raw = (ROOT / 'tests/gecko/run_ui_visuals.py').read_bytes()
        added = (b'from ui_test_device import prepare_workflow as prepare_ui_test_device\n'
                 b"(out/'ui-test-device-isolation.json').write_text(json.dumps(prepare_ui_test_device(adb,serial=args.serial,environment=os.environ),sort_keys=True,indent=2)+'\\n')\n")
        self.assertEqual(raw.count(added), 1)
        # Pin the complete original bytes without requiring history in CI's shallow checkout.
        self.assertEqual(hashlib.sha256(raw.replace(added, b'', 1)).hexdigest(),
                         '269408189e39006eeed0b50ebf15cd46cc611b76b78a40d159111e127e02973d')
        self.assertLess(raw.index(added), raw.index(b'def capture('))


if __name__ == '__main__':
    unittest.main()
