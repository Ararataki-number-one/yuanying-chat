"""DDS preparation boundary controls; never Android/network acceptance.

The integration controls substitute host compilation/device I/O. Compiler
controls also execute real JDK17/D8 against a synthetic source selection; that
one Git response is explicitly controlled. Receipt, source/tool hashes, DEX,
deadline and original CM validators are never replaced.
"""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch
from zipfile import ZipFile

import gecko_cellular_bootstrap_test as fixture
from gecko_caret_build_identity_test import minimal_dex

adapter = fixture.setup.cellular_subscription
ROOT = Path(__file__).resolve().parents[1]
NONCE = 'e' * 32
REAL_RUN = subprocess.run


def receipt(initial=-1, before=-1):
    def row(default):
        return dict(activeSubscriptionIds=[1], defaultDataSubId=default, phoneId=0, slotSubscriptionId=1)
    return dict(schema=1, kind='synthetic-default-data-subscription', runNonce=NONCE, status='passed',
                uid=2000, androidSdk=35, qemu=True, abi='x86_64', hardware='ranchu',
                initial=row(initial), beforeWrite=row(before), after=row(1), setCalls=1 if before == -1 else 0,
                applicationAcceptance=False, physicalPhoneAcceptance=False, networkAcceptance=False)


class SubscriptionReceiptControls(unittest.TestCase):
    def test_only_once_initialization_and_natural_convergence_relations_pass(self):
        for initial, before, calls in ((-1, -1, 1), (-1, 1, 0), (1, 1, 0)):
            with self.subTest(initial=initial, before=before):
                value = receipt(initial, before)
                self.assertEqual(adapter.validate_receipt(json.dumps(value) + '\n', NONCE), value)
                self.assertEqual(value['setCalls'], calls)

    def test_identity_types_scope_unknown_fields_and_mapping_changes_fail(self):
        mutations = [lambda v: v.update(runNonce='f' * 32), lambda v: v.update(schema=True),
                     lambda v: v.update(status='failed'), lambda v: v.update(uid=True),
                     lambda v: v.update(uid=0), lambda v: v.update(androidSdk=36),
                     lambda v: v.update(qemu=1), lambda v: v.update(abi='arm64-v8a'),
                     lambda v: v.update(hardware='physical'), lambda v: v.update(extra='unknown'),
                     lambda v: v.pop('networkAcceptance'), lambda v: v.update(setCalls=True),
                     lambda v: v.update(setCalls=2), lambda v: v.update(setCalls=0)]
        for key in ('applicationAcceptance', 'physicalPhoneAcceptance', 'networkAcceptance'):
            mutations += [lambda v, key=key: v.update({key: True}), lambda v, key=key: v.update({key: 0})]
        for name in ('initial', 'beforeWrite', 'after'):
            for ids in ([], [1, 2], [0], [-1], [True], ['1'], [2147483647], '1'):
                mutations.append(lambda v, name=name, ids=ids: v[name].update(activeSubscriptionIds=ids))
            mutations += [lambda v, name=name: v[name].update(phoneId=True),
                          lambda v, name=name: v[name].update(slotSubscriptionId=2),
                          lambda v, name=name: v[name].update(defaultDataSubId=0),
                          lambda v, name=name: v[name].update(defaultDataSubId=True),
                          lambda v, name=name: v[name].update(extra=1)]
        for number, mutation in enumerate(mutations):
            with self.subTest(mutation=number):
                value = receipt(); mutation(value)
                with self.assertRaises(ValueError): adapter.validate_receipt(json.dumps(value), NONCE)
        value = receipt(1, -1)
        with self.assertRaisesRegex(ValueError, 'regressed'): adapter.validate_receipt(json.dumps(value), NONCE)
        value = receipt(); value['after']['defaultDataSubId'] = -1
        with self.assertRaises(ValueError): adapter.validate_receipt(json.dumps(value), NONCE)

    def test_duplicate_nonfinite_oversize_trailing_and_nonobject_json_fail(self):
        raw = json.dumps(receipt())
        bad = ['{"schema":1,' + raw[1:], raw.replace('"setCalls": 1', '"setCalls": NaN'),
               raw + raw, '[]', 'null', ' ' * 16385, '', None, b'{}']
        for number, value in enumerate(bad):
            with self.subTest(mutation=number), self.assertRaises(ValueError):
                adapter.validate_receipt(value, NONCE)


class SubscriptionIntegrationControls(unittest.TestCase):
    def run_device(self, device, value=None, **kwargs):
        value = fixture.record() if value is None else value
        with device.installed(): device.prepare(value, **kwargs)
        return value

    def test_no_helper_when_cellular_ready_or_only_verified_wifi_waits(self):
        for edits in ({}, {0: fixture.initial_wifi, 1: fixture.initial_wifi}):
            device = fixture.DeviceIO(edits=edits)
            value = self.run_device(device)
            self.assertNotIn('subscriptionInitialization', value['cellularPreparation'])
            self.assertFalse(device.subscription_invocations)
            self.assertFalse(any(c[3] == 'push' for c, unused in device.calls))

    def test_empty_causes_one_helper_then_original_two_cellular_proofs(self):
        for normal, budget in ((False, 45), (True, 33)):
            device = fixture.DeviceIO(edits={0: fixture.initial_wifi, 1: fixture.empty_default, 2: fixture.empty_default})
            device.subscription_initial_default = device.subscription_before_default = -1
            with self.subTest(normal=normal):
                value = self.run_device(device, normal=normal, budget=budget)
                stage, rows = value['cellularPreparation'], value['networkObservations']
                entry = stage['subscriptionInitialization']
                self.assertEqual(entry['status'], 'passed')
                self.assertEqual(entry['receipt']['setCalls'], 1)
                self.assertEqual(len(device.subscription_invocations), 1)
                self.assertEqual(entry['triggerObservationIndex'], 1)
                self.assertEqual(entry['deadlineMonotonic'], budget)
                self.assertEqual((entry['runId'], entry['runAttempt']), ('7', '1'))
                self.assertEqual(entry['integrationApkSha256'], fixture.identity()['apkSha256'])
                self.assertFalse(entry['networkAcceptance'] or entry['applicationAcceptance'])
                self.assertEqual((stage['firstCellularObservationIndex'], stage['confirmationCellularObservationIndex']), (3, 4))
                self.assertEqual(rows[3]['value']['activeNetwork'], rows[4]['value']['activeNetwork'])
                self.assertNotEqual(rows[3]['runNonce'], rows[4]['runNonce'])
                self.assertEqual(entry['rawReceipt'], value['commands'][entry['invocationCommandIndex']]['stdout'])
                self.assertTrue(entry['rawReceipt'].endswith('\n'))
                self.assertEqual(entry['rawReceiptSha256'], hashlib.sha256(entry['rawReceipt'].encode()).hexdigest())
                self.assertTrue(entry['deviceJarRemoved'])
                self.assertFalse(device.subscription_jars)
                self.assertLess(device.clock.now(), budget)

    def test_initialization_refuses_missing_run_and_source_identity_before_push(self):
        changes = [lambda r: r.pop('runId'), lambda r: r.update(runId='0'),
                   lambda r: r.update(runAttempt=1), lambda r: r.update(sourceCommit='f' * 40),
                   lambda r: r.update(sourceTree='f' * 40)]
        for number, change in enumerate(changes):
            with self.subTest(mutation=number):
                value, device = fixture.record(), fixture.DeviceIO(edits={1: fixture.empty_default})
                change(value)
                with device.installed(), self.assertRaises(ValueError): device.prepare(value)
                self.assertFalse(device.subscription_invocations or device.subscription_jars)
                self.assertEqual(device.observations, 2)

    def test_malformed_or_foreign_helper_receipt_never_causes_next_cm_observation(self):
        changes = [lambda v: v.update(runNonce='f' * 32), lambda v: v.update(networkAcceptance=True),
                   lambda v: v.update(setCalls=2), lambda v: v['after'].update(defaultDataSubId=-1),
                   lambda v: v['beforeWrite'].update(activeSubscriptionIds=[1, 2]),
                   lambda v: v.update(status='failed')]
        for number, change in enumerate(changes):
            with self.subTest(mutation=number):
                device, value = fixture.DeviceIO(edits={1: fixture.empty_default}), fixture.record()
                device.subscription_receipt_edit = change
                with device.installed(), self.assertRaises(ValueError): device.prepare(value)
                self.assertEqual(device.observations, 2)
                self.assertEqual(len(device.subscription_invocations), 1)
                self.assertEqual(value['cellularPreparation']['subscriptionInitialization']['status'], 'failed')
                self.assertFalse(device.subscription_jars)

    def test_uploaded_digest_and_size_fail_before_app_process(self):
        for attribute, wrong in (('subscription_hash_override', '0' * 64), ('subscription_size_override', '1')):
            with self.subTest(field=attribute):
                device, value = fixture.DeviceIO(edits={1: fixture.empty_default}), fixture.record()
                setattr(device, attribute, wrong)
                with device.installed(), self.assertRaises(ValueError): device.prepare(value)
                self.assertFalse(device.subscription_invocations or device.subscription_jars)
                self.assertEqual(device.observations, 2)

    def test_nonzero_or_timed_out_complete_helper_receipt_is_not_promoted(self):
        for timed_out in (False, True):
            with self.subTest(timed_out=timed_out):
                device, value = fixture.DeviceIO(edits={1: fixture.empty_default}), fixture.record()
                device.subscription_timeout = timed_out
                device.subscription_exit = 0 if timed_out else 1
                expected = subprocess.TimeoutExpired if timed_out else subprocess.CalledProcessError
                with device.installed(), self.assertRaises(expected): device.prepare(value)
                entry = value['cellularPreparation']['subscriptionInitialization']
                self.assertEqual(entry['status'], 'failed')
                self.assertNotIn('receipt', entry)
                self.assertEqual(device.observations, 2)
                self.assertEqual(len(device.subscription_invocations), 1)
                self.assertEqual(value['commands'][entry['invocationCommandIndex']]['timedOut'], timed_out)

    def test_helper_success_cannot_replace_persistent_empty_or_bad_final_cm(self):
        for mode in ('empty', 'foreign-final'):
            with self.subTest(mode=mode):
                edits = {i: fixture.empty_default for i in range(1, 100)} if mode == 'empty' else {
                    1: fixture.empty_default, 3: lambda v: v.update(activeNetwork='102', activeNetworkAfter='102')}
                device, value = fixture.DeviceIO(edits=edits), fixture.record()
                with device.installed(), self.assertRaises((ValueError, TimeoutError, subprocess.TimeoutExpired)):
                    device.prepare(value, budget=3)
                self.assertEqual(len(device.subscription_invocations), 1)
                self.assertEqual(value['cellularPreparation']['status'], 'failed')
                self.assertLessEqual(device.clock.now(), 3)
                self.assertNotIn('tcpipCommand', value)

    def test_cleanup_failure_never_masks_original_failure_or_yields_success(self):
        for original_error in (False, True):
            with self.subTest(original_error=original_error):
                device, value = fixture.DeviceIO(edits={1: fixture.empty_default}), fixture.record()
                device.subscription_cleanup_exit = 1
                device.subscription_timeout = original_error
                expected = subprocess.TimeoutExpired if original_error else subprocess.CalledProcessError
                with device.installed(), self.assertRaises(expected): device.prepare(value)
                entry = value['cellularPreparation']['subscriptionInitialization']
                self.assertEqual(entry['status'], 'failed')
                self.assertFalse(entry['deviceJarRemoved'])
                self.assertEqual(entry['failureType'], expected.__name__)
                self.assertEqual(entry['cleanupFailure']['failureType'], 'CalledProcessError')
        device, value = fixture.DeviceIO(edits={1: fixture.empty_default}), fixture.record()
        original = device.run
        def late_cleanup(command, **kwargs):
            result = original(command, **kwargs)
            if command[3:6] == ['shell', 'rm', '-f']: device.clock.value = 45.001
            return result
        device.run = late_cleanup
        with device.installed(), self.assertRaises(TimeoutError): device.prepare(value)
        self.assertEqual(value['cellularPreparation']['subscriptionInitialization']['status'], 'failed')

    def test_repeated_initialization_and_cm_nonce_collision_stop_without_second_io(self):
        device, value = fixture.DeviceIO(edits={1: fixture.empty_default}), fixture.record()
        with device.installed():
            device.prepare(value)
            count = len(device.calls)
            commands = fixture.setup.native.BootstrapCommands('adb', 'emulator-5556', value, 45)
            with self.assertRaisesRegex(ValueError, 'already attempted'):
                adapter.initialize(commands, value, fixture.identity())
            self.assertEqual(len(device.calls), count)
        device, value = fixture.DeviceIO(edits={1: fixture.empty_default}), fixture.record()
        with device.installed(), patch.object(adapter.secrets, 'token_hex', side_effect=lambda n: value['networkObservations'][-1]['runNonce']):
            with self.assertRaisesRegex(ValueError, 'fresh helper nonce'): device.prepare(value)
        self.assertFalse(device.subscription_invocations or device.subscription_jars)


class SubscriptionHostCommandControls(unittest.TestCase):
    def test_failed_and_non_utf8_output_is_retained_exactly(self):
        for code in (0, 1):
            entry = dict(hostCommands=[])
            result = subprocess.CompletedProcess(['synthetic'], code, b'actual stdout\n', b'\xfferror\n')
            with patch.object(adapter.subprocess, 'run', return_value=result):
                if code:
                    with self.assertRaises(subprocess.CalledProcessError): adapter.host_run(['synthetic'], entry, time.monotonic() + 8)
                else: adapter.host_run(['synthetic'], entry, time.monotonic() + 8)
            row = entry['hostCommands'][0]
            self.assertEqual(row['stdoutUtf8'], 'actual stdout\n')
            self.assertEqual(row['stderrSha256'], hashlib.sha256(b'\xfferror\n').hexdigest())
            self.assertEqual(row['stderrBase64'], '/2Vycm9yCg==')

    def test_timeout_partial_and_oversize_bytes_are_not_success(self):
        entry = dict(hostCommands=[])
        error = subprocess.TimeoutExpired(['synthetic'], .5, output=b'complete-looking success\n', stderr=b'partial error')
        with patch.object(adapter.subprocess, 'run', side_effect=error), self.assertRaises(subprocess.TimeoutExpired):
            adapter.host_run(['synthetic'], entry, time.monotonic() + .5)
        self.assertTrue(entry['hostCommands'][0]['timedOut'])
        self.assertEqual(entry['hostCommands'][0]['stdoutUtf8'], 'complete-looking success\n')
        entry = dict(hostCommands=[]); raw = b'x' * (adapter.MAX_OUTPUT + 1)
        result = subprocess.CompletedProcess(['synthetic'], 0, raw, b'')
        with patch.object(adapter.subprocess, 'run', return_value=result), self.assertRaises(ValueError):
            adapter.host_run(['synthetic'], entry, time.monotonic() + 8)
        row = entry['hostCommands'][0]
        self.assertTrue(row['stdoutOmittedOversize'])
        self.assertNotIn('stdoutUtf8', row)
        self.assertEqual(row['stdoutSha256'], hashlib.sha256(raw).hexdigest())

    def test_original_deadline_limits_command_and_late_exit_zero_fails(self):
        clock, entry = fixture.Clock(), dict(hostCommands=[])
        def late(command, **kwargs):
            self.assertEqual(kwargs['timeout'], .25)
            clock.value = .251
            return subprocess.CompletedProcess(command, 0, b'completed too late', b'')
        with patch.object(adapter.time, 'monotonic', side_effect=clock.now), patch.object(adapter.subprocess, 'run', side_effect=late):
            with self.assertRaises(TimeoutError): adapter.host_run(['synthetic'], entry, .25)
        self.assertEqual(entry['hostCommands'][0]['deadlineMonotonic'], .25)


class SubscriptionCompilerControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        home = os.environ.get('JAVA_HOME_17_X64') or os.environ.get('JAVA_HOME')
        sdk = os.environ.get('ANDROID_HOME')
        if not home or not sdk:
            raise AssertionError('Original JDK17 and Android SDK environment are required at the full host gate')
        cls.home, cls.sdk = Path(home), Path(sdk)
        cls.d8 = cls.sdk / 'build-tools/37.0.0/lib/d8.jar'
        if hashlib.sha256(cls.d8.read_bytes()).hexdigest() != adapter.D8_SHA256:
            raise AssertionError('Original build-tools 37 D8 bytes required')
        cls.source = (ROOT / adapter.SOURCE).read_bytes()

    @contextmanager
    def compiler(self, *, synthetic=False, selected=None, output_change=None):
        with tempfile.TemporaryDirectory(prefix='cellular-compiler-controls-') as name:
            work = Path(name); source = work / adapter.SOURCE
            source.parent.mkdir(parents=True); source.write_bytes(self.source)
            out = work / 'output'; out.mkdir()
            def run(command, **kwargs):
                if command == ['git', '--no-replace-objects', 'show', 'a' * 40 + ':' + adapter.SOURCE]:
                    return subprocess.CompletedProcess(command, 0, self.source if selected is None else selected, b'')
                if not synthetic: return REAL_RUN(command, **kwargs)
                if command[1:] == ['-version']:
                    return subprocess.CompletedProcess(command, 0, b'', b'openjdk version "17.0.21"\n')
                if Path(command[0]).name == 'javac':
                    target = Path(command[command.index('-d') + 1]) / (adapter.CLASS.replace('.', '/') + '.class')
                    target.parent.mkdir(parents=True); target.write_bytes(b'\xca\xfe\xba\xbe\x00\x00\x00\x34synthetic class')
                elif 'com.android.tools.r8.D8' in command:
                    jar = Path(command[command.index('--output') + 1])
                    with ZipFile(jar, 'w') as archive:
                        archive.writestr('classes.dex', minimal_dex(['L' + adapter.CLASS.replace('.', '/') + ';']))
                    if output_change: output_change(jar, source)
                else: raise AssertionError('Unexpected compiler command')
                return subprocess.CompletedProcess(command, 0, b'', b'')
            with patch.object(adapter, 'ROOT', work), patch.object(adapter.subprocess, 'run', side_effect=run):
                yield work, out

    def test_real_jdk_d8_compile_preserves_source_tool_class_and_dex_evidence(self):
        entry = dict(sourceCommit='a' * 40, hostCommands=[])
        deadline = time.monotonic() + 30
        with self.compiler() as (work, out):
            jar = adapter.compile_helper(out, entry, deadline)
            self.assertEqual(entry['jar']['sha256'], hashlib.sha256(jar.read_bytes()).hexdigest())
            self.assertEqual(entry['sourceFile']['sha256'], hashlib.sha256(self.source).hexdigest())
            self.assertEqual(entry['toolchain']['d8']['sha256'], adapter.D8_SHA256)
            self.assertFalse(entry['compilerCacheUsed'])
            self.assertEqual(len(entry['classes']), 3)
            self.assertEqual(len(entry['dex']['definitions']), 3)
            self.assertEqual(len(entry['hostCommands']), 4)
            self.assertTrue(all(row['exitCode'] == 0 and not row['timedOut'] and row['timeoutSeconds'] <= 8
                                and row['deadlineMonotonic'] == deadline for row in entry['hostCommands']))
            self.assertEqual(entry['hostCommands'][0]['stdoutUtf8'].encode(), self.source)

    def test_foreign_selected_source_is_rejected_before_any_compilation(self):
        entry = dict(sourceCommit='a' * 40, hostCommands=[])
        with self.compiler(synthetic=True, selected=self.source + b'\n') as (work, out):
            with self.assertRaisesRegex(ValueError, 'source differs'):
                adapter.compile_helper(out, entry, time.monotonic() + 8)
        self.assertEqual(len(entry['hostCommands']), 1)

    def test_wrong_d8_bytes_or_revision_fail_before_javac(self):
        for wrong_revision in (False, True):
            with self.subTest(wrong_revision=wrong_revision), self.compiler(synthetic=True) as (work, out):
                sdk = work / 'sdk'; build = sdk / 'build-tools/37.0.0'
                (build / 'lib').mkdir(parents=True)
                (build / 'source.properties').write_bytes(b'Pkg.Revision=36.0.0\n' if wrong_revision else b'Pkg.Revision=37.0.0\n')
                if wrong_revision: shutil.copyfile(self.d8, build / 'lib/d8.jar')
                else: (build / 'lib/d8.jar').write_bytes(b'foreign D8')
                entry = dict(sourceCommit='a' * 40, hostCommands=[])
                with patch.dict(os.environ, {'ANDROID_HOME': str(sdk)}), self.assertRaises(ValueError):
                    adapter.compile_helper(out, entry, time.monotonic() + 8)
                self.assertEqual(len(entry['hostCommands']), 1)

    def test_wrong_dex_extra_archive_member_and_source_race_are_rejected(self):
        def wrong_definition(jar, source):
            with ZipFile(jar, 'w') as archive: archive.writestr('classes.dex', minimal_dex(['Lforeign/Helper;']))
        def extra(jar, source):
            with ZipFile(jar, 'a') as archive: archive.writestr('unexpected', b'x')
        def source_race(jar, source): source.write_bytes(self.source + b'\n')
        for change in (wrong_definition, extra, source_race):
            with self.subTest(change=change.__name__), self.compiler(synthetic=True, output_change=change) as (work, out):
                entry = dict(sourceCommit='a' * 40, hostCommands=[])
                with self.assertRaises(ValueError): adapter.compile_helper(out, entry, time.monotonic() + 8)


if __name__ == '__main__':
    unittest.main()
