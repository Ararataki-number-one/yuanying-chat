"""Counterfeit state controls; no actual adb, Android, APK or IME is exercised."""
import json
from pathlib import Path
import shlex
import unittest

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools/gecko'))

from caret_ime_guard import (ControlledImeGuard, COMPONENT, SERIAL, KEYS, METHOD_DUMP_COMMAND,
                            canonical_component, current_method, active_method, enabled_entries)

STOCK = 'org.stock/.LatinIme'
OTHER = 'org.other/third.party.IME'
ENABLED = STOCK + ';17;-3:' + OTHER + ';29'
HISTORY = OTHER + ';29:' + STOCK + ';17'


def identity():
    return dict(sourceCommit='a'*40, sourceTree='b'*40, runId='1234', runAttempt='1',
                integrationApkSha256='c'*64, sdkReceiptSha256='d'*64)


class SyntheticError(RuntimeError):
    def __init__(self, message):
        super().__init__(message)
        self.stdout = b'Partial synthetic command result\n'
        self.stderr = 'Synthetic stderr with unicode\u4f60\u597d\n'.encode('utf-8')


class FakeAdb:
    """Finite adapter. Only explicit fixture/User 0 mutations and captured key repair are accepted."""
    def __init__(self, *, initial_fixture_enabled=False, missing_fixture=False, qemu='1', user='0',
                 fail_enable=False, fail_set=False, fail_restore=False, absent_subtype=False,
                 absent_history=False, bad_enabled=None, active='current', safe_selected=STOCK,
                 sdk='35', dump_user='0', dump_override=None, bound='current', have_connection='true',
                 bound_to_method='true', visible_bound='true'):
        self.settings = dict(default_input_method=safe_selected,
                             enabled_input_methods=bad_enabled or (ENABLED + (':' + COMPONENT if initial_fixture_enabled else '')),
                             selected_input_method_subtype='null' if absent_subtype else '17',
                             input_methods_subtype_history='null' if absent_history else HISTORY)
        self.before = dict(self.settings)
        self.registered = (STOCK, OTHER) + (() if missing_fixture else (COMPONENT,))
        self.qemu, self.user, self.active, self.sdk, self.dump_user = qemu, user, active, sdk, dump_user
        self.dump_override, self.dump_count = dump_override, 0
        self.bound, self.have_connection, self.bound_to_method, self.visible_bound = bound, have_connection, bound_to_method, visible_bound
        self.fail_enable, self.fail_set, self.fail_restore = fail_enable, fail_set, fail_restore
        self.calls, self.mutations = [], []

    def __call__(self, *parts):
        self.calls.append(parts)
        if parts == ('shell', 'getprop', 'ro.kernel.qemu'):
            return self.qemu + '\n'
        if parts == ('shell', 'am', 'get-current-user'):
            return self.user + '\n'
        if parts == ('shell', 'getprop', 'ro.build.version.sdk'):
            return self.sdk + '\n'
        if len(parts) == 7 and parts[:6] == ('shell', 'settings', '--user', '0', 'get', 'secure'):
            if parts[6] not in KEYS:
                raise AssertionError('Foreign key read')
            return self.settings[parts[6]] + '\n'
        if parts == ('shell', 'ime', 'list', '-a', '-s', '--user', '0'):
            return '\n'.join(self.registered) + '\n'
        if parts == ('shell', 'ime', 'list', '-s', '--user', '0'):
            return '\n'.join(entry.split(';')[0] for entry in self.settings['enabled_input_methods'].split(':')) + '\n'
        if parts == METHOD_DUMP_COMMAND:
            self.dump_count += 1
            if self.dump_override is not None:
                return self.dump_override
            method = self.settings['default_input_method'] if self.active == 'current' else self.active
            bound = method if self.bound == 'current' else self.bound
            # Source-shaped counterfeit fields from AOSP android-15.0.0_r1:
            # services/core/java/com/android/server/inputmethod/InputMethodManagerService.java
            # SHA256 3657ba927c0316c53ea39f5090f5c115dce1adeed136595d31e745c36f413264.
            # There is no claim that this host string is an observed Android dump.
            return ('Current Input Method Manager state:\n  Input Methods:\n'
                    '    mCurMethodId=ignored.nested/.IME\n'
                    '  mCurrentUserId=' + self.dump_user + '\n  mCurMethodId=' + method +
                    '\n  mCurClient=synthetic-changing-handle-' + str(self.dump_count) +
                    '\n  mCurId=' + bound + ' mHaveConnection=' + self.have_connection +
                    ' mBoundToMethod=' + self.bound_to_method + ' mVisibleBound=' + self.visible_bound + '\n')
        if len(parts) == 6 and parts[:2] == ('shell', 'ime') and parts[3:5] == ('--user', '0'):
            operation = parts[2]
            quoted = shlex.split(parts[5])
            if len(quoted) != 1:
                raise AssertionError('Exactly one remote-shell component required')
            component = quoted[0]
            if operation in ('enable', 'disable'):
                if component != COMPONENT:
                    raise AssertionError('Foreign IME enabled-state mutation')
                items = self.settings['enabled_input_methods'].split(':')
                if operation == 'enable' and COMPONENT not in items:
                    items.append(COMPONENT)
                if operation == 'disable' and COMPONENT in items:
                    items.remove(COMPONENT)
                self.settings['enabled_input_methods'] = ':'.join(items)
                self.mutations.append(parts)
                if operation == 'enable' and self.fail_enable:
                    self.fail_enable = False
                    raise SyntheticError('Failure after adding owned IME')
                return 'Owned IME ' + operation + '\n'
            if operation == 'set' and component in (COMPONENT, self.before['default_input_method']):
                if component == self.before['default_input_method'] and self.fail_restore:
                    raise SyntheticError('Stock IME restoration failure')
                previous = self.settings['default_input_method']
                previous_subtype = self.settings['selected_input_method_subtype']
                self.settings['default_input_method'] = component
                self.settings['selected_input_method_subtype'] = '-1'
                self.settings['input_methods_subtype_history'] = previous + ';' + ('-1' if previous_subtype == 'null' else previous_subtype)
                self.mutations.append(parts)
                if component == COMPONENT and self.fail_set:
                    self.fail_set = False
                    raise SyntheticError('Failure after selecting owned IME')
                return 'Owned IME selected\n'
        if len(parts) in (7, 8) and parts[:4] == ('shell', 'settings', '--user', '0'):
            operation, secure, key = parts[4:7]
            if secure != 'secure' or key not in ('selected_input_method_subtype', 'input_methods_subtype_history'):
                raise AssertionError('Foreign secure setting mutation')
            if operation == 'delete' and len(parts) == 7:
                if self.before[key] != 'null':
                    raise AssertionError('Cannot delete a present original key')
                self.settings[key] = 'null'
            elif operation == 'put' and len(parts) == 8:
                value = shlex.split(parts[7])
                if value != [self.before[key]]:
                    raise AssertionError('Restoration must use exact original data')
                self.settings[key] = value[0]
            else:
                raise AssertionError('Unexpected setting operation')
            self.mutations.append(parts)
            return ''
        raise AssertionError('Unexpected prototype command: ' + repr(parts))


def harness(**options):
    fake = FakeAdb(**options)
    record = {}
    guard = ControlledImeGuard(adb=fake, identity=identity(), record=record, nonce='e'*32)
    return fake, record, guard


class ParserTest(unittest.TestCase):
    def test_expands_only_safe_short_component(self):
        self.assertEqual(canonical_component(STOCK), 'org.stock/org.stock.LatinIme')
        for value in ('null', 'org.stock', 'org.stock/.IME;reboot', 'org.stock/.IME$(x)', 'org.stock/.IME\n'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                canonical_component(value)

    def test_enabled_subtype_suffixes_retained_and_duplicates_rejected(self):
        self.assertEqual(enabled_entries(ENABLED), ('org.stock/org.stock.LatinIme', OTHER))
        for value in ('', STOCK + ':org.stock/org.stock.LatinIme', STOCK + ';2147483648', STOCK + ';;17'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                enabled_entries(value)

    def test_source_shaped_actual35_current_selected_field_not_bound_alias(self):
        raw = ('Current Input Method Manager state:\n  mCurrentUserId=0\n  mCurMethodId=' + STOCK +
               '\n  mCurId=null mHaveConnection=false mBoundToMethod=false\n')
        self.assertEqual(current_method(raw), 'org.stock/org.stock.LatinIme')
        self.assertEqual(METHOD_DUMP_COMMAND, ('shell', 'dumpsys', '--priority', 'CRITICAL', 'input_method'))

    def test_missing_duplicate_foreign_user_and_unknown_format_fail(self):
        prefix = 'Current Input Method Manager state:\n  mCurrentUserId=0\n'
        for raw in ('', prefix + '  mCurMethodId=null\n', prefix + '  mSelectedMethodId=' + STOCK + '\n',
                    prefix + '  mCurMethodId=' + STOCK + '\n  mCurMethodId=' + OTHER + '\n',
                    prefix.replace('mCurrentUserId=0', 'mCurrentUserId=10') + '  mCurMethodId=' + STOCK + '\n',
                    prefix + '  mCurMethodId=' + STOCK + '\n' + prefix + '  mCurMethodId=' + STOCK + '\n'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                current_method(raw)

    def test_nested_or_unrelated_user_fields_cannot_authorize_top_level_state(self):
        selected = 'Current Input Method Manager state:\n  mCurrentUserId=0\n  mCurMethodId=' + STOCK + '\n'
        raw = ('Other service:\n  mCurrentUserId=10\n  mCurMethodId=' + OTHER + '\n' + selected +
               '    mCurrentUserId=10\n    mCurMethodId=' + OTHER + '\n'
               'Remote client dump:\n  mCurrentUserId=10\n  mCurMethodId=' + OTHER + '\n')
        self.assertEqual(current_method(raw), 'org.stock/org.stock.LatinIme')
        with self.assertRaises(ValueError):
            current_method('Current Input Method Manager state:\n    mCurrentUserId=0\n    mCurMethodId=' + STOCK + '\n')

    def test_legitimate_google_full_and_short_and_nested_class_names_supported(self):
        values = ('com.google.android.inputmethod.latin/com.android.inputmethod.latin.LatinIME',
                  'com.android.inputmethod.latin/.LatinIME', 'org.stock/.Outer$InnerIme')
        expected = ('com.google.android.inputmethod.latin/com.android.inputmethod.latin.LatinIME',
                    'com.android.inputmethod.latin/com.android.inputmethod.latin.LatinIME',
                    'org.stock/org.stock.Outer$InnerIme')
        for value, want in zip(values, expected):
            self.assertEqual(canonical_component(value), want)
        for value in ('org..stock/.IME', '.org.stock/.IME', 'org.stock//IME', 'org.stock/.IME.$(x)'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                canonical_component(value)

    def test_actual35_bound_line_preserves_null_and_real_flags(self):
        prefix = 'Current Input Method Manager state:\n  mCurrentUserId=0\n  mCurMethodId=' + STOCK + '\n'
        observed = active_method(prefix + '  mCurId=null mHaveConnection=false mBoundToMethod=false mVisibleBound=false\n')
        self.assertIsNone(observed['boundComponent'])
        self.assertFalse(observed['haveConnection'] or observed['boundToMethod'] or observed['visibleBound'])
        observed = active_method(prefix + '  mCurId=' + STOCK + ' mHaveConnection=true mBoundToMethod=true mVisibleBound=true\n')
        self.assertEqual(observed['selectedComponent'], observed['boundComponent'])
        self.assertTrue(observed['haveConnection'] and observed['boundToMethod'] and observed['visibleBound'])
        for suffix in ('', '    mCurId=' + STOCK + ' mHaveConnection=true mBoundToMethod=true mVisibleBound=true\n',
                       '  mCurId=' + STOCK + ' mHaveConnection=1 mBoundToMethod=true mVisibleBound=true\n',
                       ('  mCurId=' + STOCK + ' mHaveConnection=true mBoundToMethod=true mVisibleBound=true\n')*2):
            with self.subTest(suffix=suffix), self.assertRaises(ValueError):
                active_method(prefix+suffix)


class GuardTest(unittest.TestCase):
    def test_success_only_changes_owned_component_and_restores_raw_subtypes_order(self):
        fake, record, guard = harness()
        called = []
        def workload():
            called.append(1)
            self.assertEqual(fake.settings['default_input_method'], COMPONENT)
            self.assertEqual(fake.settings['enabled_input_methods'], ENABLED + ':' + COMPONENT)
            return 0
        self.assertEqual(guard.run(workload), 0)
        self.assertEqual(called, [1])
        self.assertEqual(fake.settings, fake.before)
        self.assertTrue(record['restorationVerified'])
        self.assertNotIn('failureStage', record)
        for flag in ('applicationAcceptance', 'physicalPhoneAcceptance', 'vendorKeyboardUiAcceptance'):
            self.assertFalse(record[flag])
        for command in fake.mutations:
            self.assertIn('--user', command)
            self.assertIn('0', command)

    def test_previously_enabled_fixture_is_retained(self):
        fake, record, guard = harness(initial_fixture_enabled=True)
        guard.run(lambda: 0)
        self.assertEqual(fake.settings, fake.before)
        self.assertFalse(any(row[:3] == ('shell', 'ime', 'disable') for row in fake.mutations))

    def test_absent_subtype_history_settings_are_deleted_after_selection_side_effects(self):
        fake, record, guard = harness(absent_subtype=True, absent_history=True)
        guard.run(lambda: 0)
        self.assertEqual(fake.settings, fake.before)
        deleted = {row[-1] for row in fake.mutations if row[:5] == ('shell', 'settings', '--user', '0', 'delete')}
        self.assertEqual(deleted, {'selected_input_method_subtype', 'input_methods_subtype_history'})

    def test_history_semicolons_are_remote_shell_quoted_data(self):
        fake, record, guard = harness()
        guard.run(lambda: 0)
        rows = [row for row in fake.mutations if row[:7] == ('shell', 'settings', '--user', '0', 'put', 'secure', 'input_methods_subtype_history')]
        self.assertEqual(len(rows), 1)
        self.assertEqual(shlex.split(rows[0][-1]), [HISTORY])
        self.assertTrue(rows[0][-1].startswith("'"))

    def test_prepare_error_after_enable_restores_all_state_without_running_input(self):
        fake, record, guard = harness(fail_enable=True)
        called = []
        with self.assertRaises(SyntheticError):
            guard.run(lambda: called.append(1))
        self.assertEqual(called, [])
        self.assertEqual(fake.settings, fake.before)
        self.assertTrue(record['restorationVerified'])
        self.assertEqual(record['failureStage'], 'prepare')
        failed = [row for row in record['commands'] if row['status'] == 'failed']
        self.assertEqual(len(failed), 1)
        self.assertEqual(failed[0]['stdout'], 'Partial synthetic command result\n')
        self.assertEqual(failed[0]['stderr'], 'Synthetic stderr with unicode\u4f60\u597d\n')

    def test_prepare_error_after_select_restores_all_state_without_running_input(self):
        fake, record, guard = harness(fail_set=True)
        called = []
        with self.assertRaises(SyntheticError):
            guard.run(lambda: called.append(1))
        self.assertEqual(called, [])
        self.assertEqual(fake.settings, fake.before)

    def test_failure_and_interrupt_preserved_after_verified_cleanup(self):
        for error in (SyntheticError('Fixture failed'), KeyboardInterrupt('Interrupted')):
            with self.subTest(error=type(error).__name__):
                fake, record, guard = harness()
                def workload():
                    raise error
                with self.assertRaises(type(error)) as caught:
                    guard.run(workload)
                self.assertIs(caught.exception, error)
                self.assertEqual(fake.settings, fake.before)
                self.assertTrue(record['restorationVerified'])
                self.assertEqual(record['failureStage'], 'workload')

    def test_command_and_phase_times_bound_one_workload_and_exact_state_restore(self):
        fake, record, guard = harness()
        guard.run(lambda: 0)
        fields = ('prepareStartedAtMonotonicNanos', 'preparedAtMonotonicNanos',
                  'workloadStartedAtMonotonicNanos', 'workloadCompletedAtMonotonicNanos',
                  'restoreStartedAtMonotonicNanos', 'restoredAtMonotonicNanos')
        values = [record[key] for key in fields]
        self.assertEqual(values, sorted(values))
        self.assertTrue(all(type(value) is int and value > 0 for value in values))
        self.assertEqual(record['initial']['settings'], record['restored']['settings'])
        self.assertNotEqual(record['initial']['inputMethodDumpRaw'], record['restored']['inputMethodDumpRaw'])
        self.assertEqual(record['during']['actualSelectedComponent'], COMPONENT)
        self.assertEqual(record['confirmedAndroidSdk'], 35)
        self.assertTrue(record['confirmedQemu'] and record['confirmedUser0'])
        self.assertEqual(record['workloadInvocationCount'], 1)
        self.assertEqual(record['workloadExitCode'], 0)
        active = record['activeInputMethod']
        self.assertEqual(active['status'], 'passed')
        self.assertEqual(active['selectedComponent'], COMPONENT)
        self.assertEqual(active['boundComponent'], COMPONENT)
        self.assertLessEqual(record['workloadStartedAtMonotonicNanos'], active['startedAtMonotonicNanos'])
        self.assertLessEqual(active['completedAtMonotonicNanos'], record['workloadCompletedAtMonotonicNanos'])
        for key, value in identity().items():
            self.assertEqual(record[key], value)
        for command in record['commands']:
            self.assertLessEqual(command['startedAtMonotonicNanos'], command['completedAtMonotonicNanos'])
            self.assertGreaterEqual(command['startedAtMonotonicNanos'], values[0])
            self.assertLessEqual(command['completedAtMonotonicNanos'], values[-1])

    def test_nested_class_component_is_remote_shell_quoted_during_exact_restore(self):
        fake, record, guard = harness(safe_selected='org.stock/.Outer$InnerIme')
        # Keep the synthetic registered/enabled state consistent with that valid method.
        fake.settings['enabled_input_methods'] = fake.settings['enabled_input_methods'].replace(STOCK, fake.settings['default_input_method'])
        fake.settings['input_methods_subtype_history'] = fake.settings['input_methods_subtype_history'].replace(STOCK, fake.settings['default_input_method'])
        fake.registered = (fake.settings['default_input_method'], OTHER, COMPONENT)
        fake.before = dict(fake.settings)
        guard.run(lambda: 0)
        self.assertEqual(fake.settings, fake.before)
        restore = [row for row in fake.mutations if row[:3] == ('shell', 'ime', 'set')][-1]
        self.assertEqual(shlex.split(restore[-1]), [fake.before['default_input_method']])
        self.assertTrue(restore[-1].startswith("'"))

    def test_positive_fixture_failure_not_replayed(self):
        fake, record, guard = harness()
        self.assertEqual(guard.run(lambda: 1), 1)
        self.assertEqual(record['workloadInvocationCount'], 1)
        self.assertEqual(record['workloadStatus'], 'failed')
        self.assertNotIn('activeInputMethod', record)
        with self.assertRaises(ValueError):
            guard.run(lambda: 0)

    def test_restore_failure_is_fatal_and_keeps_evidence(self):
        fake, record, guard = harness(fail_restore=True)
        with self.assertRaises(RuntimeError):
            guard.run(lambda: 0)
        self.assertTrue(record['fatal'])
        self.assertFalse(record['restorationVerified'])
        self.assertEqual(record['restoreErrorType'], 'SyntheticError')
        self.assertEqual(record['failureStage'], 'restore')

    def test_foreign_enabled_state_drift_is_not_silently_repaired(self):
        fake, record, guard = harness()
        def workload():
            fake.settings['enabled_input_methods'] = STOCK + ';17;-3:' + COMPONENT
            return 0
        with self.assertRaises(RuntimeError):
            guard.run(workload)
        self.assertFalse(record['restorationVerified'])
        self.assertFalse(any(row[:3] == ('shell', 'ime', 'enable') and row[-1] == OTHER for row in fake.mutations))

    def test_wrong_device_user_missing_fixture_and_unrecovered_selected_fixture_fail_before_mutation(self):
        options = [dict(qemu='0'), dict(user='10'), dict(sdk='36'), dict(dump_user='10'),
                   dict(missing_fixture=True), dict(active=OTHER),
                   dict(safe_selected=COMPONENT, initial_fixture_enabled=True), dict(bad_enabled=STOCK + ';bad')]
        for option in options:
            with self.subTest(option=option):
                fake, record, guard = harness(**option)
                called = []
                with self.assertRaises(ValueError):
                    guard.run(lambda: called.append(1))
                self.assertEqual(fake.mutations, [])
                self.assertEqual(called, [])

    def test_rejects_other_serial_and_counterfeit_identity(self):
        for value in ('phone-serial', 'emulator-5556'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                ControlledImeGuard(adb=FakeAdb(), identity=identity(), record={}, nonce='e'*32, serial=value)
        bad = identity()
        bad['runAttempt'] = '0'
        with self.assertRaises(ValueError):
            ControlledImeGuard(adb=FakeAdb(), identity=bad, record={}, nonce='e'*32)

    def test_invalid_six_field_identities_and_nonce_never_issue_commands(self):
        for field, value in (('sourceCommit', 'a'*39), ('sourceTree', True), ('runId', '0'),
                             ('runAttempt', 1), ('integrationApkSha256', 'c'*63), ('sdkReceiptSha256', 'd'*65)):
            fake = FakeAdb()
            bad = identity()
            bad[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                ControlledImeGuard(adb=fake, identity=bad, record={}, nonce='e'*32)
            self.assertEqual(fake.calls, [])
        with self.assertRaises(ValueError):
            ControlledImeGuard(adb=FakeAdb(), identity=identity(), record={}, nonce='e'*31)

    def test_terminated_new_workload_is_fatal_after_cleanup_and_never_replayed(self):
        fake, record, guard = harness()
        with self.assertRaises(ValueError):
            guard.run(lambda: -15)
        self.assertEqual(fake.settings, fake.before)
        self.assertEqual(record['workloadInvocationCount'], 1)
        self.assertTrue(record['restorationVerified'])
        self.assertEqual(record['failureStage'], 'workload-exit')

    def test_unchanged_focus_oracle_failure_is_preserved_after_cleanup(self):
        fake, record, guard = harness()
        error = SyntheticError('Real focus/caret failed: IME visible=false')
        def workload():
            raise error
        with self.assertRaises(SyntheticError) as caught:
            guard.run(workload)
        self.assertIs(caught.exception, error)
        self.assertEqual(fake.settings, fake.before)
        self.assertTrue(record['restorationVerified'])
        self.assertEqual(record['failureStage'], 'workload')
        for field in ('prepareStartedAtMonotonicNanos', 'preparedAtMonotonicNanos',
                      'workloadStartedAtMonotonicNanos', 'workloadCompletedAtMonotonicNanos',
                      'restoreStartedAtMonotonicNanos', 'restoredAtMonotonicNanos'):
            self.assertGreater(record[field], 0)
        for key in ('initial', 'during', 'restored'):
            self.assertIn('settings', record[key])
        self.assertNotIn('activeInputMethod', record)

    def test_successful_callback_without_actual_bound_controlled_method_is_fatal_but_restored(self):
        for options in (dict(bound='null'), dict(bound=OTHER), dict(have_connection='false'), dict(bound_to_method='false')):
            with self.subTest(options=options):
                fake, record, guard = harness(**options)
                with self.assertRaises(ValueError):
                    guard.run(lambda: 0)
                self.assertEqual(record['failureStage'], 'active-input-method')
                self.assertEqual(record['activeInputMethod']['status'], 'failed')
                self.assertEqual(fake.settings, fake.before)
                self.assertTrue(record['restorationVerified'])
                self.assertEqual(record['workloadInvocationCount'], 1)



if __name__ == '__main__':
    unittest.main(verbosity=2)
