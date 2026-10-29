"""Counterfeit host controls only; these do not execute Android or qualify an APK."""
import contextlib
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/gecko'))
spec = importlib.util.spec_from_file_location('background_isolation', ROOT / 'tools/gecko/isolate_emulator_background.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
SOURCE, TREE = 'a' * 40, 'b' * 40
SENTINEL = 'PRIVATE_SENTINEL_ACCOUNT_OR_PATH_87123'


def identity():
    return dict(schema=1, package='local.pocketchat.test', sourceCommit=SOURCE,
        sourceTree=TREE, dirtySource=False, version='2.0.28', versionCode=81,
        sdkCoordinate='org.mozilla.geckoview:geckoview:157.0.20261005135250',
        apkSha256='c' * 64, apkBytes=100, buildStampSha256='d' * 64,
        sdkBuildIdentity=dict(runId='123', runAttempt='1'))


def observation(nonce):
    return dict(schema=1, runNonce=nonce, sourceCommit=SOURCE, buildIdentity=identity(),
        actualAndroidExecution=True, actualConnectivityManagerExecution=True,
        actualGeckoExecution=False, applicationAcceptance=False, physicalPhoneAcceptance=False,
        androidSdk=35, pid=123, observedAtElapsedRealtime=42, activeNetwork='101',
        activeNetworkAfter='101', capabilitiesPresent=True, internetCapability=True,
        stableDuringRead=True, usable=True)


def bootstrap():
    return dict(schema=2, status='passed', serial=module.SERIAL, sourceCommit=SOURCE,
        sourceTree=TREE, expectedBuildIdentity=identity(), confirmedQemu=True,
        actualAndroidCommands=True, actualIntegrationProviderExecution=True,
        actualConnectivityManagerExecution=True, applicationAcceptance=False,
        actualGeckoExecution=False, physicalPhoneAcceptance=False,
        applicationOrInputPolicyModified=False, gestureReplayed=False,
        networkObservations=[dict(runNonce='e' * 32, value=observation('e' * 32))],
        commands=[dict(stdout=SENTINEL)], unchangedLegacyField=SENTINEL)


def record():
    return dict(status='failed', operations=[], **module.FLAGS)


def public(output):
    prefix = 'EMULATOR_BACKGROUND_ISOLATION '
    assert output.startswith(prefix) and len(output.splitlines()) == 1
    return json.loads(output[len(prefix):])


@contextlib.contextmanager
def main_fixture(edit=None, dirty=False, identity_error=None):
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        (root / 'app').mkdir()
        (root / 'app/build.gradle').write_text("versionName '2.0.28'\nversionCode 81\n")
        apk = root / 'app/build/outputs/apk/integration/app-x86_64-integration.apk'
        apk.parent.mkdir(parents=True);apk.write_bytes(b'counterfeit-host-control-only')
        path = root / 'work/gecko-integration/emulator-bootstrap-results.json'
        path.parent.mkdir(parents=True)
        original = (json.dumps(bootstrap(), indent=2) + '\n').encode();path.write_bytes(original)
        commands = FakeCommands(edit)
        def git(command, **kwargs):
            if command[1:3] == ['rev-parse', 'HEAD']:
                return SOURCE + '\n'
            if command[1:3] == ['rev-parse', 'HEAD^{tree}']:
                return TREE + '\n'
            if command[1] == 'status':
                return ' M unexpected\n' if dirty else ''
            if command[1] == 'show':
                # The counterfeit aaaa source is a historical official identity,
                # not a real current derived-SDK build or acceptance receipt.
                raise subprocess.CalledProcessError(128, command, stderr=b'counterfeit missing source')
            raise AssertionError('Unexpected counterfeit git operation')
        env = dict(CI='true', GITHUB_ACTIONS='true', GITHUB_REPOSITORY=module.REPOSITORY,
                   GITHUB_SHA=SOURCE, GITHUB_EVENT_NAME='push', GITHUB_RUN_ID='123', GITHUB_RUN_ATTEMPT='1')
        with patch.object(module, 'ROOT', root), patch.object(module.subprocess, 'check_output', side_effect=git), \
                patch.object(module, 'expected_build', return_value=identity(), side_effect=identity_error), \
                patch.object(module, 'Commands', return_value=commands) as factory, patch.dict(os.environ, env, clear=True):
            yield root, apk, path, original, commands, factory


class FakeCommands:
    """Counterfeit responses, never an actual Android receipt."""
    def __init__(self, edit=None, before_mutation=None):
        self.calls = []
        self.edit, self.before_mutation = edit, before_mutation
        self.nonces = []

    def run(self, operation, *parts):
        self.calls.append((operation, parts))
        values = dict(qemu='1', sdk='35', abi='x86_64', hardware='ranchu',
            fingerprint='google/sdk_gphone64_x86_64/emu64xa:15/AE3A.240806.043/12960925:userdebug/dev-keys')
        if operation.startswith('device-'):
            output = values[operation.removeprefix('device-')]
        elif operation.endswith('-network'):
            nonce = parse_qs(urlsplit(parts[-1]).query)['runNonce'][0]
            self.nonces.append(nonce)
            value = observation(nonce)
            if self.edit:
                self.edit(operation, value)
            return json.dumps(value)
        elif operation in ('package-present', 'read-disabled'):
            output = 'package:' + module.PACKAGE
        elif operation == 'processes-before':
            output = 'NAME\ninit\nsystem_server\n' + module.PACKAGE + '.persistent\n'
        elif operation == 'processes-after':
            output = 'NAME\ninit\nsystem_server\n'
        else:
            output = ''
        if self.edit:
            changed = self.edit(operation, output)
            if changed is not None:
                output = changed
        return output

    def mutations(self):
        return [row for row in self.calls if row[0] in ('force-stop', 'disable-package')]


class IsolationControls(unittest.TestCase):
    def test_complete_control_changes_only_exact_background_package(self):
        commands, receipt = FakeCommands(), record()
        checks = []
        module.isolate(commands, receipt, identity(), lambda: checks.append('before-mutation'))
        self.assertEqual(checks, ['before-mutation'])
        self.assertEqual(commands.mutations(), [
            ('force-stop', ('shell', 'am', 'force-stop', '--user', '0', module.PACKAGE)),
            ('disable-package', ('shell', 'pm', 'disable-user', '--user', '0', module.PACKAGE))])
        self.assertEqual(receipt['status'], 'passed')
        self.assertTrue(receipt['networkBeforeUsable'] and receipt['networkAfterUsable'])
        self.assertEqual(len(set(commands.nonces)), 2)
        self.assertTrue(all(receipt[k] is False for k in module.FLAGS))

    def test_each_wrong_device_property_blocks_all_mutations(self):
        for field in ('qemu', 'sdk', 'abi', 'hardware', 'fingerprint'):
            with self.subTest(field=field):
                commands = FakeCommands(lambda op, value: 'not-the-fixed-image' if op == 'device-' + field else None)
                with self.assertRaises(module.IsolationFailure):
                    module.isolate(commands, record(), identity(), lambda: None)
                self.assertEqual(commands.mutations(), [])

    def test_before_network_requires_current_nonce_apk_api_and_usable_real_cm(self):
        edits = [lambda v: v.update(runNonce='f' * 32),
                 lambda v: v['buildIdentity'].update(apkSha256='f' * 64),
                 lambda v: v.update(androidSdk=34),
                 lambda v: v.update(actualConnectivityManagerExecution=False),
                 lambda v: v.update(applicationAcceptance=True),
                 lambda v: v.update(activeNetwork='', activeNetworkAfter='', capabilitiesPresent=False,
                                    internetCapability=False, stableDuringRead=False, usable=False)]
        for edit in edits:
            with self.subTest(edit=edit):
                def apply(op, value):
                    if op == 'before-network':
                        edit(value)
                commands = FakeCommands(apply)
                with self.assertRaises(module.IsolationFailure):
                    module.isolate(commands, record(), identity(), lambda: None)
                self.assertEqual(commands.mutations(), [])

    def test_changed_bootstrap_before_mutation_blocks_actions(self):
        commands = FakeCommands()
        def changed():
            raise module.IsolationFailure('bootstrap-changed')
        with self.assertRaises(module.IsolationFailure):
            module.isolate(commands, record(), identity(), changed)
        self.assertEqual(commands.mutations(), [])

    def test_similar_package_or_missing_readback_is_not_confirmation(self):
        for operation in ('package-present', 'read-disabled'):
            with self.subTest(operation=operation):
                commands = FakeCommands(lambda op, value: 'package:' + module.PACKAGE + '.other' if op == operation else None)
                receipt = record()
                with self.assertRaises(module.IsolationFailure):
                    module.isolate(commands, receipt, identity(), lambda: None)
                self.assertEqual(receipt['status'], 'failed')
                if operation == 'package-present':
                    self.assertEqual(commands.mutations(), [])

    def test_remaining_background_process_or_after_network_failure_is_not_passed(self):
        edits = [lambda op, value: 'NAME\ninit\n' + module.PACKAGE + ':leftover' if op == 'processes-after' else None,
                 lambda op, value: value.update(androidSdk=34) if op == 'after-network' else None]
        for edit in edits:
            with self.subTest(edit=edit):
                receipt = record()
                with self.assertRaises(module.IsolationFailure):
                    module.isolate(FakeCommands(edit), receipt, identity(), lambda: None)
                self.assertEqual(receipt['status'], 'failed')

    def test_process_snapshot_rejects_empty_header_only_wrong_header_and_truncation(self):
        for raw in ('', 'NAME', 'PID NAME\n1 init', 'NAME\nunknown', 'NAME\ninit\n', 'NAME\ninit\na b'):
            # NAME + init is a valid zero-match snapshot; it is not the header-only case.
            if raw == 'NAME\ninit\n':
                self.assertEqual(module.process_count(raw), 0)
            else:
                with self.subTest(raw=raw), self.assertRaises(module.IsolationFailure):
                    module.process_count(raw)
        self.assertEqual(module.process_count('NAME\ninit\ncom.google.android.gms\ncom.google.android.gms.persistent\ncom.google.android.gms:x\ncom.google.android.gmsfake'), 3)

    def test_valid_bootstrap_does_not_become_application_acceptance(self):
        module.validate_bootstrap(bootstrap(), identity(), '123', '1')
        for edit in (lambda v: v.update(status='failed'), lambda v: v.update(sourceCommit='f' * 40),
                     lambda v: v.update(actualGeckoExecution=True), lambda v: v.update(backgroundIsolation={}),
                     lambda v: v['expectedBuildIdentity'].update(apkBytes=100.0)):
            value = bootstrap();edit(value)
            with self.subTest(edit=edit), self.assertRaises(module.IsolationFailure):
                module.validate_bootstrap(value, identity(), '123', '1')
        with self.assertRaises(module.IsolationFailure):
            module.validate_bootstrap(bootstrap(), identity(), '999', '1')

    def test_ci_identity_is_required_before_actions(self):
        env = dict(CI='true', GITHUB_ACTIONS='true', GITHUB_REPOSITORY=module.REPOSITORY,
                   GITHUB_SHA=SOURCE, GITHUB_EVENT_NAME='push', GITHUB_RUN_ID='123', GITHUB_RUN_ATTEMPT='1')
        self.assertEqual(module.validate_ci(env, SOURCE), ('123', '1'))
        for key in env:
            changed = dict(env);changed[key] = SENTINEL
            with self.subTest(key=key), self.assertRaises(module.IsolationFailure):
                module.validate_ci(changed, SOURCE)

    def test_expired_budget_or_timed_out_process_even_with_success_stdout_fails(self):
        receipt = record();commands = module.Commands('adb', module.SERIAL, receipt, 5)
        with patch.object(module.time, 'monotonic', return_value=6), patch.object(module.subprocess, 'run') as run:
            with self.assertRaises(module.IsolationFailure):commands.run('read-disabled', 'shell', 'pm')
            run.assert_not_called()
        receipt = record();commands = module.Commands('adb', module.SERIAL, receipt, 5)
        timeout = subprocess.TimeoutExpired('adb', 1, output=b'package:com.google.android.gms', stderr=SENTINEL.encode())
        with patch.object(module.time, 'monotonic', return_value=0), patch.object(module.subprocess, 'run', side_effect=timeout):
            with self.assertRaises(module.IsolationFailure):commands.run('read-disabled', 'shell', 'pm')
        self.assertTrue(receipt['operations'][0]['timedOut'])
        self.assertNotIn(SENTINEL, json.dumps(receipt))
        receipt = record();commands = module.Commands('adb', module.SERIAL, receipt, 5)
        with patch.object(module.time, 'monotonic', side_effect=[0, 0, 6, 6]), patch.object(module.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, b'looks-successful', b'')):
            with self.assertRaises(module.IsolationFailure):commands.run('read-disabled', 'shell', 'pm')
        self.assertFalse(receipt['operations'][0]['succeeded'])

    def test_append_keeps_old_record_fields_and_rejects_changed_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'bootstrap.json';old = bootstrap()
            original = (json.dumps(old, indent=2) + '\n').encode();path.write_bytes(original)
            child = record();child['status'] = 'passed'
            module.append_result(path, original, old, child)
            result = json.loads(path.read_text());self.assertEqual(result.pop('backgroundIsolation'), child)
            self.assertEqual(result, old)
            path.write_bytes(original);path.write_text('{"different":true}')
            with self.assertRaises(module.IsolationFailure):module.append_result(path, original, old, child)
            self.assertEqual(path.read_text(), '{"different":true}')

    def test_failed_child_marks_overall_bootstrap_failed(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'bootstrap.json';old = bootstrap()
            raw = json.dumps(old).encode();path.write_bytes(raw)
            child = record();child['reason'] = 'after-network-unusable'
            module.append_result(path, raw, old, child)
            value = json.loads(path.read_text());self.assertEqual(value['status'], 'failed')
            self.assertEqual(value['commands'], old['commands'])
            self.assertEqual(value['backgroundIsolation']['status'], 'failed')

    def test_main_masks_arbitrary_exceptions_and_preserves_untrusted_old_file(self):
        output = io.StringIO()
        with patch.object(module, 'expected_build', side_effect=RuntimeError(SENTINEL)), contextlib.redirect_stdout(output):
            code = module.main(['--serial', 'physical-' + SENTINEL, '--adb', 'adb', '--apk', '/'+SENTINEL])
        self.assertNotEqual(code, 0);self.assertNotIn(SENTINEL, output.getvalue())
        self.assertEqual(public(output.getvalue())['reason'], 'invalid-arguments')

    def test_main_complete_control_appends_same_source_run_child(self):
        with main_fixture() as (_, apk, path, original, commands, factory):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = module.main(['--adb', 'adb', '--serial', module.SERIAL, '--apk', str(apk)])
            self.assertEqual(code, 0)
            value = json.loads(path.read_text());child = value.pop('backgroundIsolation')
            self.assertEqual(value, json.loads(original))
            self.assertEqual(child['originalBootstrapSha256'], module.digest(original))
            self.assertEqual((child['runId'], child['runAttempt']), ('123', '1'))
            self.assertEqual(child['status'], 'passed');self.assertNotIn(SENTINEL, json.dumps(child))
            summary = public(output.getvalue())
            self.assertEqual(summary['status'], 'passed')
            self.assertEqual((summary['sourceCommit'], summary['sourceTree'], summary['runId'], summary['runAttempt']),
                             (SOURCE, TREE, '123', '1'))

    def test_main_after_network_failure_marks_existing_bootstrap_failed(self):
        def edit(operation, value):
            if operation == 'after-network':
                value['activeNetworkAfter'] = '102';value['stableDuringRead'] = value['usable'] = False
        with main_fixture(edit) as (_, apk, path, original, commands, factory):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = module.main(['--adb', 'adb', '--serial', module.SERIAL, '--apk', str(apk)])
            self.assertNotEqual(code, 0)
            value = json.loads(path.read_text())
            self.assertEqual(value['status'], 'failed')
            self.assertEqual(value['commands'], json.loads(original)['commands'])
            self.assertEqual(value['backgroundIsolation']['status'], 'failed')
            self.assertEqual(value['backgroundIsolation']['reason'], 'after-network-unusable')

    def test_main_dirty_or_repeated_bootstrap_never_constructs_device_commands(self):
        for kind in ('dirty', 'repeated'):
            with self.subTest(kind=kind), main_fixture(dirty=kind == 'dirty') as (_, apk, path, original, commands, factory):
                if kind == 'repeated':
                    value = json.loads(path.read_text());value['backgroundIsolation'] = {'status':'passed'}
                    path.write_text(json.dumps(value));original = path.read_bytes()
                with contextlib.redirect_stdout(io.StringIO()):
                    code = module.main(['--adb', 'adb', '--serial', module.SERIAL, '--apk', str(apk)])
                self.assertNotEqual(code, 0);factory.assert_not_called()
                self.assertEqual(path.read_bytes(), original)

    def test_main_arbitrary_failure_never_prints_private_text(self):
        for failure in (RuntimeError(SENTINEL), module.IsolationFailure(SENTINEL)):
            with self.subTest(failure=type(failure).__name__), main_fixture(identity_error=failure) as (_, apk, path, original, commands, factory):
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    code = module.main(['--adb', 'adb', '--serial', module.SERIAL, '--apk', str(apk)])
                self.assertNotEqual(code, 0);self.assertNotIn(SENTINEL, output.getvalue())
                self.assertEqual(public(output.getvalue())['reason'], 'isolation-unavailable')
                self.assertEqual(path.read_bytes(), original);factory.assert_not_called()

    def test_main_save_race_is_nonzero_and_does_not_overwrite_changed_receipt(self):
        with main_fixture() as (_, apk, path, original, commands, factory):
            original_run = commands.run
            def change_after_network(operation, *parts):
                result = original_run(operation, *parts)
                if operation == 'after-network':
                    path.write_text('{"new-owner":true}')
                return result
            commands.run = change_after_network
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = module.main(['--adb', 'adb', '--serial', module.SERIAL, '--apk', str(apk)])
            self.assertNotEqual(code, 0);self.assertEqual(path.read_text(), '{"new-owner":true}')
            self.assertEqual(public(output.getvalue())['reason'], 'bootstrap-save-unconfirmed')

    def test_failure_after_provisional_success_cannot_save_passed_child(self):
        with main_fixture() as (_, apk, path, original, commands, factory):
            def fail_late(commands, receipt, identity, before_mutation):
                receipt['status'] = 'passed'
                raise module.IsolationFailure('deadline-expired')
            with patch.object(module, 'isolate', side_effect=fail_late), contextlib.redirect_stdout(io.StringIO()):
                code = module.main(['--adb', 'adb', '--serial', module.SERIAL, '--apk', str(apk)])
            self.assertNotEqual(code, 0)
            saved = json.loads(path.read_text())
            self.assertEqual((saved['status'], saved['backgroundIsolation']['status']), ('failed', 'failed'))


if __name__ == '__main__':
    unittest.main()
