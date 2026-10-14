"""Adversarial host controls of recorded controlled-IME evidence.

Every passing base is produced by executing the real ControlledImeGuard and
LauncherGuard with their finite fake command adapters, plus the real editing
coordinator with synthetic child-process results. No adb, APK, Gecko, input,
keyboard UI, ARM device or release acceptance is exercised or claimed.
"""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'tests'), str(ROOT/'tools/gecko')]

import gecko_caret_ime_guard_test as IME_HOST
import gecko_caret_launcher_guard_test as LAUNCHER_HOST
import run_caret_editing_phase as PHASE
from caret_ime_guard import ControlledImeGuard, COMPONENT, KEYS, METHOD_DUMP_COMMAND
from caret_launcher_guard import LauncherGuard
from caret_ime_contract import verify_ime_environment

NONCE = 'e'*32


class HostClock:
    """Deterministic positive host timestamps; not device or performance data."""
    def __init__(self):
        self.value = 1_000_000_000

    def __call__(self):
        self.value += 10_000
        return self.value


def encode(value):
    return (json.dumps(value, ensure_ascii=False, indent=2)+'\n').encode('utf-8')


def raw_hash(value):
    return hashlib.sha256(encode(value)).hexdigest()


def recorded_base(*, fixture_previously_enabled=False, absent_subtype=False, absent_history=False,
                  relative_artifacts=False, method_dump_padding=''):
    """Execute the checked-in guards/coordinator; only child process results are doubled.

    The parent coordinator actually records both commands, once-only counts,
    timestamps, IME restoration verification and a hash of the real temporary
    JSON file. No second handwritten implementation creates a passing ledger.
    """
    clock = HostClock()
    identity = IME_HOST.identity()
    value = {}
    phase = dict(sourceCommit=identity['sourceCommit'], sourceTree=identity['sourceTree'],
                 runId=identity['runId'], runAttempt=identity['runAttempt'], phaseStatus='failed')
    fake_ime = IME_HOST.FakeAdb(initial_fixture_enabled=fixture_previously_enabled,
                              absent_subtype=absent_subtype, absent_history=absent_history)
    def ime_command(*parts):
        raw=fake_ime(*parts)
        return raw+method_dump_padding if parts==METHOD_DUMP_COMMAND else raw
    calls = []
    with tempfile.TemporaryDirectory(prefix='ime-contract-host-only-') as temporary:
        output = Path(temporary)
        target = output/'caret-ime-environment.json'
        args = SimpleNamespace(root=ROOT, out=output, adb='SYNTHETIC-ADB-NOT-EXECUTABLE',
                               serial=IME_HOST.SERIAL)
        artifact_names = ('build_receipt', 'sdk_receipt', 'sdk_aar', 'official_sdk_aar', 'integration_apk', 'release_apk')
        relative_paths = (
            'work/gecko-integration/caret-apk-build-receipt.json',
            'work/native-caret-sdk/sdk-build-receipt.json',
            'work/native-caret-sdk/geckoview-caret.aar',
            'work/gecko-integration/geckoview.aar',
            'app/build/outputs/apk/integration/app-x86_64-integration.apk',
            'app/build/outputs/apk/release/app-arm64-v8a-release-unsigned.apk',
        )
        for name, relative_path in zip(artifact_names, relative_paths):
            setattr(args, name, Path(relative_path) if relative_artifacts else output/('counterfeit-not-read-'+name))

        def process(command, **unused):
            calls.append(list(command))
            if command[1].endswith('/run_caret_bound_performance.py'):
                if fake_ime.mutations or fake_ime.settings != fake_ime.before:
                    raise AssertionError('Real coordinator switched IME before stock workload')
            elif command[1].endswith('/run_gecko_caret_compat.py'):
                guard = ControlledImeGuard(adb=ime_command, identity=identity, record=value,
                                           nonce=NONCE, clock=clock)
                guard.run(lambda: 0)
                target.write_bytes(encode(value))
            else:
                raise AssertionError('Unexpected synthetic child command')
            return SimpleNamespace(returncode=0)

        def verify_child():
            # Execute the actual coordinator's restoration parser before the
            # outer guard can restore its launcher or permit later HOME suites.
            PHASE.verify_caret_ime_environment(target, identity)
            phase['imeEnvironmentReceipt'] = 'caret-compat/caret-ime-environment.json'
            phase['imeEnvironmentReceiptSha256'] = hashlib.sha256(target.read_bytes()).hexdigest()
            phase['imeRestorationVerified'] = True

        def workloads():
            result = PHASE.run_workloads(args, phase, verify_child)
            phase['phaseStatus'] = 'passed' if result == 0 else 'workload-failed-restored'
            return result

        with mock.patch.object(PHASE.subprocess, 'run', side_effect=process), \
             mock.patch.object(PHASE.time, 'monotonic_ns', side_effect=clock):
            launcher = LauncherGuard(adb=LAUNCHER_HOST.FakeAdb(), identity=dict(schema=1, **identity),
                                     record=phase, nonce='f'*32)
            if launcher.run(workloads) != 0:
                raise AssertionError('Synthetic guard/coordinator base failed')
        if len(calls) != 2 or fake_ime.settings != fake_ime.before:
            raise AssertionError('Base did not execute both workloads and restore exact fake state')
    return value, phase, identity, NONCE, raw_hash(value)


def check(value, phase, identity, nonce, digest):
    return verify_ime_environment(value, phase, identity=identity, nonce=nonce, raw_sha256=digest)


def setting_read_positions(value, snapshot):
    """Locate a snapshot's actual seven-read group for explicit negative tampering."""
    rows = value['commands']
    expected = [('shell', 'settings', '--user', '0', 'get', 'secure', key) for key in KEYS]
    expected += [('shell', 'ime', 'list', '-a', '-s', '--user', '0'),
                 ('shell', 'ime', 'list', '-s', '--user', '0'), METHOD_DUMP_COMMAND]
    for index in range(len(rows)-6):
        group = rows[index:index+7]
        if [tuple(row['parts']) for row in group] == expected and group[6]['stdout'] == snapshot['inputMethodDumpRaw']:
            return range(index, index+7)
    raise AssertionError('Executed guard snapshot read group unavailable')


class EnvironmentContractTest(unittest.TestCase):
    def test_large_complete_method_dump_is_accepted_with_actual_utf8_size_and_hash(self):
        padding='  synthetic_readonly_history='+('界'*140000)+'\n'
        value,phase,identity,nonce,digest=recorded_base(method_dump_padding=padding)
        self.assertEqual(check(value,phase,identity,nonce,digest)['status'],'passed')
        for row in value['commands']:
            if tuple(row['parts'])==METHOD_DUMP_COMMAND:
                raw=row['stdout'].encode('utf-8')
                self.assertGreater(len(raw),131072)
                self.assertEqual(row['stdoutChars'],len(row['stdout']))
                self.assertEqual(row['stdoutBytes'],len(raw))
                self.assertEqual(row['stdoutSha256'],hashlib.sha256(raw).hexdigest())
                self.assertTrue(row['stdout'].endswith(padding))

    def test_complete_method_dump_metadata_cannot_be_forged_or_claim_truncation(self):
        for field,wrong in (('stdoutType','bytes'),('stdoutChars',True),('stdoutBytes',1),
                            ('stdoutSha256','0'*64),('stdoutTruncated',True)):
            def mutate(value,field=field,wrong=wrong):
                row=next(row for row in value['commands'] if tuple(row['parts'])==METHOD_DUMP_COMMAND)
                row[field]=wrong
            with self.subTest(field=field):
                self.assert_rejected(mutate)

    def assert_rejected(self, mutate_value=None, mutate_phase=None, *, mutate_args=None):
        value, phase, identity, nonce, digest = recorded_base()
        # Each negative begins with a passing executed base, so an unrelated
        # contract defect cannot make all adversarial cases appear successful.
        self.assertEqual(check(value, phase, identity, nonce, digest)['status'], 'passed')
        if mutate_value:
            mutate_value(value)
            digest = raw_hash(value)
            phase['imeEnvironmentReceiptSha256'] = digest
        if mutate_phase:
            mutate_phase(phase)
        arguments = dict(identity=identity, nonce=nonce, raw_sha256=digest)
        if mutate_args:
            mutate_args(arguments)
        with self.assertRaises(ValueError):
            verify_ime_environment(value, phase, **arguments)

    def test_executed_guard_and_coordinator_base_with_actual_preflight_order_and_read_groups(self):
        value, phase, identity, nonce, digest = recorded_base()
        result = check(value, phase, identity, nonce, digest)
        self.assertEqual(result['status'], 'passed')
        self.assertTrue(result['originalStockWorkloadFirst'] and result['restorationVerified'])
        self.assertEqual([row['parts'] for row in value['commands'][:3]], [
            ['shell', 'getprop', 'ro.kernel.qemu'], ['shell', 'am', 'get-current-user'],
            ['shell', 'getprop', 'ro.build.version.sdk']])
        for name in ('initial', 'during', 'restored'):
            self.assertEqual(len(setting_read_positions(value, value[name])), 7)
        self.assertFalse(result['applicationAcceptance'])
        self.assertFalse(result['physicalPhoneAcceptance'])
        self.assertFalse(result['vendorKeyboardUiAcceptance'])

    def test_previously_enabled_fixture_is_preserved_without_enable_disable_writes(self):
        value, phase, identity, nonce, digest = recorded_base(fixture_previously_enabled=True)
        self.assertEqual(check(value, phase, identity, nonce, digest)['status'], 'passed')
        self.assertIn(COMPONENT, value['initial']['enabledComponents'])
        self.assertEqual(value['initial']['settings'], value['restored']['settings'])
        operations = [row['parts'][2] for row in value['commands']
                      if row['parts'][:2] == ['shell', 'ime'] and row['parts'][2] in ('enable', 'set', 'disable')]
        self.assertEqual(operations, ['set', 'set'])

    def test_real_coordinator_keeps_workflow_shaped_relative_artifact_paths(self):
        value, phase, identity, nonce, digest = recorded_base(relative_artifacts=True)
        self.assertEqual(check(value, phase, identity, nonce, digest)['status'], 'passed')
        for workload in phase['workloads']:
            command = workload['command']
            for flag in ('--build-receipt', '--sdk-receipt', '--sdk-aar', '--official-sdk-aar', '--integration-apk'):
                argument = command[command.index(flag)+1]
                self.assertFalse(Path(argument).is_absolute())
                self.assertNotIn('..', Path(argument).parts)
            self.assertTrue(Path(command[command.index('--root')+1]).is_absolute())
            self.assertTrue(Path(command[command.index('--out')+1]).is_absolute())

    def test_absent_subtype_history_keys_are_restored_by_actual_delete_commands(self):
        value, phase, identity, nonce, digest = recorded_base(absent_subtype=True, absent_history=True)
        self.assertEqual(check(value, phase, identity, nonce, digest)['status'], 'passed')
        deletes = [row['parts'][-1] for row in value['commands'] if row['parts'][:5] == ['shell', 'settings', '--user', '0', 'delete']]
        self.assertEqual(deletes, ['selected_input_method_subtype', 'input_methods_subtype_history'])

    def test_each_identity_field_must_match_the_selected_source_run_apk_sdk(self):
        for field in ('sourceCommit', 'sourceTree', 'runId', 'runAttempt', 'integrationApkSha256', 'sdkReceiptSha256'):
            def mutate(value, field=field):
                value['identity'][field] = '7'*len(value['identity'][field])
                value[field] = value['identity'][field]
            with self.subTest(field=field):
                self.assert_rejected(mutate)

    def test_flat_identity_cannot_conflict_with_nested_identity(self):
        self.assert_rejected(lambda value: value.update(sourceTree='9'*40))

    def test_nonce_and_exact_component_serial_user_are_bound(self):
        for field, wrong in (('runNonce', 'f'*32), ('exactFixtureComponent', 'other.app/.IME'),
                             ('serial', 'physical-phone'), ('user', 10), ('user', False)):
            with self.subTest(field=field, wrong=wrong):
                self.assert_rejected(lambda value, field=field, wrong=wrong: value.update({field: wrong}))

    def test_preflight_truth_and_actual_values_are_required(self):
        for field, wrong in (('confirmedQemu', False), ('confirmedUser0', False), ('confirmedAndroidSdk', 36),
                             ('confirmedAndroidSdk', True)):
            with self.subTest(field=field):
                self.assert_rejected(lambda value, field=field, wrong=wrong: value.update({field: wrong}))
        for index, wrong in ((0, '0\n'), (1, '10\n'), (2, '36\n')):
            with self.subTest(index=index):
                self.assert_rejected(lambda value, index=index, wrong=wrong: value['commands'][index].update(stdout=wrong))

    def test_preflight_command_order_cannot_be_changed(self):
        def mutate(value):
            value['commands'][1]['parts'], value['commands'][2]['parts'] = value['commands'][2]['parts'], value['commands'][1]['parts']
        self.assert_rejected(mutate)

    def test_restored_raw_subtype_history_and_enabled_order_must_match_initial(self):
        changes = dict(selected_input_method_subtype='18', input_methods_subtype_history=IME_HOST.STOCK+';18',
                       enabled_input_methods=IME_HOST.OTHER+';29:'+IME_HOST.STOCK+';17;-3',
                       default_input_method='org.stock/org.stock.LatinIme')
        for key, wrong in changes.items():
            with self.subTest(key=key):
                self.assert_rejected(lambda value, key=key, wrong=wrong: value['restored']['settings'].update({key: wrong}))

    def test_secure_settings_cannot_add_unknown_keys_or_newlines(self):
        self.assert_rejected(lambda value: value['initial']['settings'].update(other_secure_key='unexpected'))
        self.assert_rejected(lambda value: value['initial']['settings'].update(default_input_method=IME_HOST.STOCK+'\n'))

    def test_raw_actual_ime_lists_are_not_display_only_labels(self):
        for field, wrong in (('allImeListRaw', IME_HOST.STOCK+'\n'+IME_HOST.OTHER+'\n'),
                             ('enabledImeListRaw', IME_HOST.STOCK+'\n'),
                             ('enabledImeListRaw', IME_HOST.STOCK+'\n'+IME_HOST.STOCK+'\n')):
            with self.subTest(field=field, wrong=wrong):
                self.assert_rejected(lambda value, field=field, wrong=wrong: value['during'].update({field: wrong}))

    def test_raw_dump_must_be_the_same_top_level_user_selected_component(self):
        for change in ('wrong-user', 'wrong-method', 'duplicate-method', 'unknown-field'):
            def mutate(value, change=change):
                raw = value['during']['inputMethodDumpRaw']
                if change == 'wrong-user':
                    raw = raw.replace('  mCurrentUserId=0', '  mCurrentUserId=10')
                elif change == 'wrong-method':
                    raw = raw.replace('  mCurMethodId='+COMPONENT, '  mCurMethodId='+IME_HOST.STOCK)
                elif change == 'duplicate-method':
                    raw += '  mCurMethodId='+COMPONENT+'\n'
                else:
                    raw = raw.replace('  mCurMethodId=', '  mSelectedMethodId=')
                value['during']['inputMethodDumpRaw'] = raw
            with self.subTest(change=change):
                self.assert_rejected(mutate)

    def test_snapshot_labels_cannot_diverge_from_raw_settings_and_lists(self):
        for field, wrong in (('selectedComponent', IME_HOST.STOCK), ('actualSelectedComponent', IME_HOST.STOCK),
                             ('enabledComponents', []), ('actualEnabledComponents', []), ('registeredComponents', [])):
            with self.subTest(field=field):
                self.assert_rejected(lambda value, field=field, wrong=wrong: value['during'].update({field: wrong}))

    def test_raw_snapshot_must_match_its_complete_actual_command_read_group(self):
        def mutate(value):
            row = list(setting_read_positions(value, value['during']))[4]
            value['commands'][row]['stdout'] = IME_HOST.STOCK+'\n'
        self.assert_rejected(mutate)

    def test_incomplete_seven_read_group_is_rejected(self):
        def mutate(value):
            row = list(setting_read_positions(value, value['during']))[2]
            value['commands'][row]['parts'] = ['shell', 'settings', '--user', '0', 'get', 'secure', 'default_input_method']
        self.assert_rejected(mutate)

    def test_foreign_ime_mutation_is_rejected(self):
        def mutate(value):
            row = next(row for row in value['commands'] if row['parts'][:3] == ['shell', 'ime', 'enable'])
            row['parts'][-1] = IME_HOST.OTHER
        self.assert_rejected(mutate)

    def test_reset_and_force_stop_commands_are_not_allowed_in_ime_guard(self):
        for parts in (['shell', 'ime', 'reset', '--user', '0'],
                      ['shell', 'am', 'force-stop', '--user', '0', 'com.google.android.inputmethod.latin']):
            def mutate(value, parts=parts):
                next(row for row in value['commands'] if row['parts'][:3] == ['shell', 'ime', 'enable'])['parts'] = parts
            with self.subTest(parts=parts):
                self.assert_rejected(mutate)

    def test_unowned_secure_setting_repair_is_rejected(self):
        def mutate(value):
            row = next(row for row in value['commands'] if row['parts'][:5] == ['shell', 'settings', '--user', '0', 'put'])
            row['parts'][6] = 'enabled_input_methods'
        self.assert_rejected(mutate)

    def test_restore_setting_values_must_be_captured_literal_values(self):
        def mutate(value):
            row = next(row for row in value['commands'] if row['parts'][:7] == ['shell', 'settings', '--user', '0', 'put', 'secure', 'input_methods_subtype_history'])
            row['parts'][7] = "'other.app/.IME;-1'"
        self.assert_rejected(mutate)

    def test_duplicate_owned_switch_is_rejected_even_with_valid_command_timing(self):
        def mutate(value):
            index = next(i for i, row in enumerate(value['commands']) if row['parts'][:3] == ['shell', 'ime', 'enable'])
            row = copy.deepcopy(value['commands'][index])
            row['startedAtMonotonicNanos'] = row['completedAtMonotonicNanos']+1
            row['completedAtMonotonicNanos'] = row['startedAtMonotonicNanos']+1
            value['commands'].insert(index+1, row)
        self.assert_rejected(mutate)

    def test_fixture_selection_cannot_occur_during_workload(self):
        def mutate(value):
            index = next(i for i, row in enumerate(value['commands']) if row['parts'][:3] == ['shell', 'ime', 'set'] and row['parts'][-1] == COMPONENT)
            row = value['commands'].pop(index)
            row['startedAtMonotonicNanos'] = value['workloadStartedAtMonotonicNanos']+1
            row['completedAtMonotonicNanos'] = row['startedAtMonotonicNanos']+1
            at = next(i for i, entry in enumerate(value['commands']) if entry['startedAtMonotonicNanos'] > row['startedAtMonotonicNanos'])
            value['commands'].insert(at, row)
        self.assert_rejected(mutate)

    def test_missing_or_boolean_or_overflow_and_out_of_order_timestamps_are_rejected(self):
        for field, wrong in (('preparedAtMonotonicNanos', True), ('restoredAtMonotonicNanos', 2**63),
                             ('workloadStartedAtMonotonicNanos', 0), ('restoreStartedAtMonotonicNanos', 1)):
            with self.subTest(field=field):
                self.assert_rejected(lambda value, field=field, wrong=wrong: value.update({field: wrong}))
        self.assert_rejected(lambda value: value.pop('workloadCompletedAtMonotonicNanos'))

    def test_command_times_and_status_must_be_valid(self):
        self.assert_rejected(lambda value: value['commands'][0].update(status='failed'))
        self.assert_rejected(lambda value: value['commands'][0].update(startedAtMonotonicNanos=True))
        self.assert_rejected(lambda value: value['commands'][0].update(completedAtMonotonicNanos=1))

    def test_failed_partial_or_replayed_workloads_are_rejected(self):
        for field, wrong in (('status', 'failed'), ('restorationVerified', False), ('mutationAttempted', False),
                             ('workloadInvocationCount', 2), ('workloadInvocationCount', True),
                             ('workloadExitCode', 1), ('workloadExitCode', False), ('workloadStatus', 'failed'),
                             ('failureStage', 'workload'), ('fatal', True)):
            with self.subTest(field=field):
                self.assert_rejected(lambda value, field=field, wrong=wrong: value.update({field: wrong}))

    def test_environment_ledger_cannot_claim_vendor_phone_or_application_acceptance(self):
        for field in ('applicationAcceptance', 'physicalPhoneAcceptance', 'vendorKeyboardUiAcceptance'):
            with self.subTest(field=field):
                self.assert_rejected(lambda value, field=field: value.update({field: True}))

    def test_parent_must_bind_the_exact_child_raw_receipt_hash_and_path(self):
        self.assert_rejected(mutate_phase=lambda phase: phase.update(imeEnvironmentReceiptSha256='9'*64))
        self.assert_rejected(mutate_phase=lambda phase: phase.update(imeEnvironmentReceipt='../stale/caret-ime-environment.json'))

    def test_parent_source_run_binding_and_restoration_are_required(self):
        for field, wrong in (('sourceCommit', '9'*40), ('sourceTree', '9'*40), ('runId', '9'),
                             ('runAttempt', '9'), ('restorationVerified', False), ('imeRestorationVerified', False),
                             ('status', 'failed'), ('phaseStatus', 'workload-failed-restored')):
            with self.subTest(field=field):
                self.assert_rejected(mutate_phase=lambda phase, field=field, wrong=wrong: phase.update({field: wrong}))
        self.assert_rejected(mutate_phase=lambda phase: phase['identity'].update(sdkReceiptSha256='9'*64))

    def test_parent_original_stock_workload_must_finish_first_once(self):
        self.assert_rejected(mutate_phase=lambda phase: phase['workloads'].reverse())
        self.assert_rejected(mutate_phase=lambda phase: phase['workloads'][0].update(invocationCount=2))
        self.assert_rejected(mutate_phase=lambda phase: phase['workloads'][0].update(exitCode=1))
        self.assert_rejected(mutate_phase=lambda phase: phase['workloads'][0].update(completedAtMonotonicNanos=phase['workloads'][1]['completedAtMonotonicNanos']))

    def test_parent_new_workload_must_exit_after_exact_ime_restore(self):
        def mutate(phase):
            phase['workloads'][1]['completedAtMonotonicNanos'] = phase['workloads'][1]['startedAtMonotonicNanos']+1
        self.assert_rejected(mutate_phase=mutate)
        self.assert_rejected(mutate_phase=lambda phase: phase['workloads'].append(copy.deepcopy(phase['workloads'][1])))

    def test_parent_commands_must_be_exact_original_runners_with_shared_artifact_paths(self):
        changes = ('replace-both', 'drop-normal-mode', 'append-flag', 'different-sdk-receipt',
                   'different-sdk-aar', 'different-integration-apk', 'different-root', 'different-child-output')
        for change in changes:
            def mutate(phase, change=change):
                if change == 'replace-both':
                    for workload in phase['workloads']:
                        workload['command'] = ['/bin/true']
                    return
                command = phase['workloads'][1]['command']
                if change == 'drop-normal-mode':
                    command.remove('--normal-acceptance')
                elif change == 'append-flag':
                    command.append('--native-input-diagnostics')
                else:
                    flag = {'different-sdk-receipt': '--sdk-receipt', 'different-sdk-aar': '--sdk-aar',
                            'different-integration-apk': '--integration-apk', 'different-root': '--root',
                            'different-child-output': '--out'}[change]
                    command[command.index(flag)+1] = '/tmp/forged-unshared-host-control-path'
            with self.subTest(change=change):
                self.assert_rejected(mutate_phase=mutate)

    def test_malformed_receipt_hash_is_rejected_even_if_parent_field_matches(self):
        value, phase, identity, nonce, digest = recorded_base()
        self.assertEqual(check(value, phase, identity, nonce, digest)['status'], 'passed')
        for wrong in ('same-but-not-a-hash', '0'*63, True):
            parent = copy.deepcopy(phase)
            parent['imeEnvironmentReceiptSha256'] = wrong
            with self.subTest(wrong=wrong), self.assertRaises(ValueError):
                check(value, parent, identity, nonce, wrong)

    def test_executed_post_callback_active_binding_observation_matches_command(self):
        value, phase, identity, nonce, digest = recorded_base()
        self.assertEqual(check(value, phase, identity, nonce, digest)['status'], 'passed')
        active = value['activeInputMethod']
        self.assertEqual(active['selectedComponent'], COMPONENT)
        self.assertEqual(active['boundComponent'], COMPONENT)
        self.assertTrue(active['haveConnection'] and active['boundToMethod'])
        self.assertLessEqual(value['workloadStartedAtMonotonicNanos'], active['startedAtMonotonicNanos'])
        self.assertLessEqual(active['completedAtMonotonicNanos'], value['workloadCompletedAtMonotonicNanos'])
        rows = [row for row in value['commands'] if tuple(row['parts']) == METHOD_DUMP_COMMAND
                and row['stdout'] == active['inputMethodDumpRaw']]
        self.assertEqual(len(rows), 1)

    def test_active_binding_observation_must_exist_and_be_successful(self):
        self.assert_rejected(lambda value: value.pop('activeInputMethod'))
        self.assert_rejected(lambda value: value['activeInputMethod'].update(status='failed'))

    def test_selected_alone_does_not_prove_the_fixture_was_bound(self):
        def mutate(value):
            active = value['activeInputMethod']
            active['boundComponent'] = 'org.stock/org.stock.LatinIme'
            active['inputMethodDumpRaw'] = active['inputMethodDumpRaw'].replace(
                '  mCurId='+COMPONENT, '  mCurId='+IME_HOST.STOCK)
            row = next(row for row in value['commands'] if tuple(row['parts']) == METHOD_DUMP_COMMAND
                       and row['startedAtMonotonicNanos'] >= active['startedAtMonotonicNanos'])
            row['stdout'] = active['inputMethodDumpRaw']
        self.assert_rejected(mutate)

    def test_bound_name_without_live_connection_or_binding_is_rejected(self):
        for field, raw_field in (('haveConnection', 'mHaveConnection'), ('boundToMethod', 'mBoundToMethod')):
            def mutate(value, field=field, raw_field=raw_field):
                active = value['activeInputMethod']
                active[field] = False
                active['inputMethodDumpRaw'] = active['inputMethodDumpRaw'].replace(raw_field+'=true', raw_field+'=false')
                row = next(row for row in value['commands'] if tuple(row['parts']) == METHOD_DUMP_COMMAND
                           and row['startedAtMonotonicNanos'] >= active['startedAtMonotonicNanos'])
                row['stdout'] = active['inputMethodDumpRaw']
            with self.subTest(field=field):
                self.assert_rejected(mutate)

    def test_active_raw_dump_and_labels_must_match_one_actual_read(self):
        self.assert_rejected(lambda value: value['activeInputMethod'].update(selectedComponent='org.stock/org.stock.LatinIme'))
        def mutate(value):
            active = value['activeInputMethod']
            row = next(row for row in value['commands'] if tuple(row['parts']) == METHOD_DUMP_COMMAND
                       and row['stdout'] == active['inputMethodDumpRaw'])
            row['stdout'] += '  injected_nonobserved_field=true\n'
        self.assert_rejected(mutate)

    def test_active_capture_must_be_inside_the_workload_and_before_restore(self):
        for change in ('boolean-start', 'before-workload', 'after-restore', 'inverted'):
            def mutate(value, change=change):
                active = value['activeInputMethod']
                if change == 'boolean-start':
                    active['startedAtMonotonicNanos'] = True
                elif change == 'before-workload':
                    active['startedAtMonotonicNanos'] = value['prepareStartedAtMonotonicNanos']
                    active['completedAtMonotonicNanos'] = value['preparedAtMonotonicNanos']
                elif change == 'after-restore':
                    active['startedAtMonotonicNanos'] = value['restoredAtMonotonicNanos']+1
                    active['completedAtMonotonicNanos'] = value['restoredAtMonotonicNanos']+2
                else:
                    active['completedAtMonotonicNanos'] = active['startedAtMonotonicNanos']-1
            with self.subTest(change=change):
                self.assert_rejected(mutate)

    def test_active_capture_cannot_claim_one_observation_with_duplicate_read_commands(self):
        def mutate(value):
            active = value['activeInputMethod']
            index = next(i for i, row in enumerate(value['commands']) if tuple(row['parts']) == METHOD_DUMP_COMMAND
                         and row['stdout'] == active['inputMethodDumpRaw'])
            row = copy.deepcopy(value['commands'][index])
            row['startedAtMonotonicNanos'] = row['completedAtMonotonicNanos']+1
            row['completedAtMonotonicNanos'] = row['startedAtMonotonicNanos']+1
            value['commands'].insert(index+1, row)
        self.assert_rejected(mutate)


if __name__ == '__main__':
    unittest.main(verbosity=2)
