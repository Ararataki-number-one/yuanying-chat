"""Exact13 diagnostic input controls; no new emulator or application acceptance."""
import ast
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import struct
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from zipfile import ZipFile

import native_setup11_workflow_contract as contract

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / '.github/workflows/gecko-integration.yml'
ADAPTER = ROOT / 'tests/native_setup11_workflow_contract.py'
OLD_TEST = ROOT / 'tests/profile_native_setup_diagnostic11_test.py'
VIEW_BINDING = b'''# This retained module observes exact historical S11 workflow bytes. New13
# controls and the real frontend read the actual Source13 Path directly.
from native_setup11_workflow_contract import Setup11WorkflowInput
WORKFLOW = Setup11WorkflowInput(WORKFLOW)
'''
sha = lambda raw: hashlib.sha256(raw).hexdigest()
spec = importlib.util.spec_from_file_location('editing_transport13_projector', ROOT / 'tests/gecko/print_editing_transport13_diagnostic.py')
emitter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(emitter)
SOURCE, TREE = 'a' * 40, 'b' * 40


def environment():
    return dict(CI='true', GITHUB_ACTIONS='true', GITHUB_SERVER_URL='https://github.com',
                GITHUB_REPOSITORY='Ararataki-number-one/yuanying-chat', GITHUB_JOB='android',
                GITHUB_SHA=SOURCE, GITHUB_RUN_ID='123', GITHUB_RUN_ATTEMPT='1',
                POCKET_EDITING_TRANSPORT_PHASE='editing', POCKET_EDITING_TRANSPORT_OUTCOME='failure')


def identity():
    return emitter.identity_from_environment(environment(), SOURCE, TREE, b'')


class Stream:
    """Declared smart-socket wire input; it never opens a real socket."""
    def __init__(self, raw):
        self.raw, self.sent, self.timeouts = raw, [], []

    def __enter__(self): return self
    def __exit__(self, *args): pass
    def settimeout(self, value): self.timeouts.append(value)
    def sendall(self, value): self.sent.append(value)
    def recv(self, length):
        value, self.raw = self.raw[:length], self.raw[length:]
        return value


class FakeAdb:
    """Explicit local command-result boundary; no Android execution implied."""
    calls = []
    def __init__(self, deadline): self.calls.append(('constructed', deadline))
    def online(self): self.calls.append(('online',))
    def read(self, parts):
        self.calls.append(parts)
        values = {emitter.COMMANDS['qemu']: '1\n', emitter.COMMANDS['user']: '0\n',
                  emitter.COMMANDS['package']: 'package:/data/app/controlled/base.apk\n',
                  ('sha256sum', '/data/app/controlled/base.apk'): 'c' * 64 + '  /data/app/controlled/base.apk\n',
                  emitter.COMMANDS['events']: '', emitter.COMMANDS['wifi']: 'Wi-Fi is enabled\n',
                  emitter.COMMANDS['connectivity']: 'Active default network: none\n'}
        if parts not in values: raise AssertionError(parts)
        return values[parts]


class EditingTransport13WorkflowTests(unittest.TestCase):
    def test_actual_source13_whole_workflow_has_only_the_one_reviewed_editing_diagnostic(self):
        raw = WORKFLOW.read_bytes()
        self.assertEqual(sha(raw), contract.EDITING13_SHA256)
        self.assertEqual(raw.count(contract.EDITING13_STEP), 1)
        source11 = contract.restore_setup11_workflow(raw)
        self.assertEqual(sha(source11), contract.CURRENT_SHA256)
        self.assertEqual(source11.replace(contract.EDITING13_BEFORE + contract.EDITING13_AFTER,
                                         contract.EDITING13_BEFORE + contract.EDITING13_STEP + contract.EDITING13_AFTER, 1), raw)
        source10 = contract.restore_previous_workflow(raw)
        self.assertEqual(sha(source10), contract.PREVIOUS_SHA256)
        self.assertEqual(contract.restore_previous_workflow(source11), source10)
        self.assertEqual(contract.restore_previous_workflow(source10), source10)
        self.assertIn(b"if: ${{ always() && matrix.phase == 'editing' }}", contract.EDITING13_STEP)

    def test_unknown_relocated_duplicate_steps_and_any_original_workload_change_are_rejected(self):
        raw = WORKFLOW.read_bytes()
        removed = raw.replace(contract.EDITING13_STEP, b'', 1)
        # The exact old11 input remains an explicit supported historical input.
        self.assertEqual(contract.restore_setup11_workflow(removed), removed)
        invalid = [b'unknown workflow', raw + b'\n', removed + b' ', removed + contract.EDITING13_STEP,
                   raw.replace(contract.EDITING13_STEP, contract.EDITING13_STEP * 2, 1),
                   raw.replace(b'always() &&', b'success() &&', 1),
                   raw.replace(b'print_editing_transport13_diagnostic.py', b'print_unreviewed_diagnostic.py', 1)]
        for before, after in [(b'timeout 180 adb', b'timeout 181 adb'),
                              (b' -cores 4 ', b' -cores 2 '),
                              (b'checks_failed=1', b'checks_failed=0'),
                              (b"sample: ['1', '2']", b"sample: ['1', '2', '3']")]:
            self.assertIn(before, raw)
            invalid.append(raw.replace(before, after, 1))
        for value in invalid:
            with self.subTest(sha256=sha(value)), self.assertRaises(AssertionError):
                contract.restore_previous_workflow(value)
        for value in (None, raw.decode(), bytearray(raw)):
            with self.assertRaises(AssertionError):
                contract.restore_previous_workflow(value)

    def test_previous_adapter_and_all_eleven_old_test_methods_and_goldens_are_whole_byte_exact(self):
        adapter = ADAPTER.read_bytes()
        marker = b'\n\n# Source13 adds only a diagnostic after the unchanged editing command.'
        self.assertEqual(adapter.count(marker), 1)
        previous_adapter = adapter.split(marker, 1)[0]
        self.assertEqual(sha(previous_adapter), 'f7c31b6d5bad40140978f8f14347769b738583feea2226d0c11c2c90b015d3d8')
        current = OLD_TEST.read_bytes()
        self.assertEqual(current.count(VIEW_BINDING), 1)
        previous = current.replace(VIEW_BINDING, b'', 1)
        self.assertEqual(sha(previous), '6d1831300cdda830c6bf2366731818320634ae7cebc635f2dc3f6d0f28384e44')
        def methods(raw):
            text = raw.decode()
            return {n.name: ast.get_source_segment(text, n) for n in ast.walk(ast.parse(text))
                    if isinstance(n, ast.FunctionDef)}
        self.assertEqual(methods(current), methods(previous))
        self.assertEqual(sum(name.startswith('test_') for name in methods(previous)), 11)
        self.assertEqual(sorted(methods(previous_adapter).items()),
                         sorted((k, v) for k, v in methods(adapter).items() if k in methods(previous_adapter)))

    def test_historical_view_is_one_ordinary_bounded_reader_and_keeps_real_path_unmodified(self):
        raw = WORKFLOW.read_bytes()
        with tempfile.TemporaryDirectory(prefix='editing13-workflow-view-') as directory:
            folder = Path(directory); path = folder / 'workflow.yml'; path.write_bytes(raw)
            view = contract.Setup11WorkflowInput(path)
            self.assertEqual(sha(view.read_bytes()), contract.CURRENT_SHA256)
            self.assertEqual(path.read_bytes(), raw)
            link = folder / 'link.yml'; link.symlink_to(path)
            with self.assertRaises(AssertionError):
                contract.Setup11WorkflowInput(link).read_bytes()
            path.write_bytes(raw + b'\n')
            with self.assertRaises(AssertionError):
                view.read_bytes()
            path.write_bytes(b'x' * (128 * 1024 + 1))
            with self.assertRaises(AssertionError):
                view.read_bytes()

    def test_real_frontend_reads_actual_source13_and_retains_diagnostic_only_scope(self):
        generator = ROOT / 'tools/gecko/generate_experience_targeted_workflow.py'
        target = ROOT / '.github/workflows/gecko-experience-targeted.yml'
        before = {p: p.read_bytes() for p in (WORKFLOW, generator, target)}
        self.assertEqual(sha(before[generator]), '1274bafdf4b9557b60800618ec90ea3f63a312405d321693e406c58c5f630f00')
        command = [sys.executable, str(ROOT / 'tests/gecko/source11_targeted_generator_compat.py'), '--check']
        result = subprocess.run(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        proof = json.loads(result.stdout)
        self.assertEqual(proof['mainInputSha256'], contract.EDITING13_SHA256)
        self.assertEqual(proof['status'], 'checked-historical-diagnostic-graph-only')
        for key in ('workflowWritten', 'ciTriggered', 'formalFourteenQualification',
                    'applicationAcceptance', 'physicalPhoneAcceptance', 'originalCliSupportsChangedMain'):
            self.assertIs(proof[key], False)
        self.assertEqual(before, {p: p.read_bytes() for p in before})


class EditingTransport13ObservationTests(unittest.TestCase):
    def test_strict_editing_source_run_identity_and_absent_owner_do_not_probe(self):
        self.assertEqual(identity()['sourceTree'], TREE)
        for key, value in [('CI', 'false'), ('GITHUB_ACTIONS', 'false'),
                           ('GITHUB_SERVER_URL', 'https://elsewhere.invalid'),
                           ('GITHUB_REPOSITORY', 'other/project'), ('GITHUB_JOB', 'build'),
                           ('GITHUB_SHA', 'c' * 40), ('GITHUB_RUN_ID', '0'),
                           ('GITHUB_RUN_ATTEMPT', True), ('POCKET_EDITING_TRANSPORT_PHASE', 'connections'),
                           ('POCKET_EDITING_TRANSPORT_OUTCOME', 'unknown')]:
            env = environment(); env[key] = value
            self.assertIsNone(emitter.identity_from_environment(env, SOURCE, TREE, b''))
        self.assertIsNone(emitter.identity_from_environment(environment(), SOURCE, TREE, b' M changed'))
        with patch.object(emitter.subprocess, 'run', side_effect=AssertionError('No Git/ADB process for absent owner')), \
                patch.object(emitter, 'ExistingAdb', side_effect=AssertionError('No ADB probe')):
            value = emitter.collect(ROOT, {}, emitter.SERIAL)
        self.assertEqual(value['reasonCode'], 'identity-unavailable')
        self.assertFalse(value['actualCommands'])

    def test_serial_and_local_apk_mismatch_stop_before_any_existing_adb_probe(self):
        with patch.object(emitter, 'source_identity', return_value=identity()), \
                patch.object(emitter, 'apk_identity', side_effect=AssertionError('Wrong serial stops earlier')), \
                patch.object(emitter, 'ExistingAdb', side_effect=AssertionError('No ADB probe')):
            value = emitter.collect(ROOT, environment(), 'another-device')
        self.assertEqual(value['reasonCode'], 'serial-unavailable')
        with patch.object(emitter, 'source_identity', return_value=identity()), \
                patch.object(emitter, 'apk_identity', side_effect=emitter.Unavailable('local-apk-digest-mismatch')), \
                patch.object(emitter, 'ExistingAdb', side_effect=AssertionError('No ADB probe')):
            value = emitter.collect(ROOT, environment(), emitter.SERIAL)
        self.assertEqual(value['reasonCode'], 'local-apk-digest-mismatch')
        self.assertFalse(value['actualCommands'])

    def test_declared_read_only_device_observations_never_change_original_acceptance(self):
        FakeAdb.calls = []
        with patch.object(emitter, 'source_identity', return_value=identity()), \
                patch.object(emitter, 'apk_identity', return_value=dict(apkSha256='c' * 64, apkBytes=100)), \
                patch.object(emitter, 'ExistingAdb', FakeAdb), \
                patch.object(emitter, 'host_health', return_value=dict(memory={}, qemu={'status': 'unavailable'})):
            value = emitter.collect(ROOT, environment(), emitter.SERIAL)
        self.assertEqual(value['status'], 'available')
        self.assertTrue(value['deviceIdentityConfirmed'])
        self.assertEqual([x['name'] for x in value['commands']], ['events', 'wifi', 'connectivity'])
        self.assertEqual(FakeAdb.calls[1:], [('online',), emitter.COMMANDS['qemu'], emitter.COMMANDS['user'],
                         emitter.COMMANDS['package'], ('sha256sum', '/data/app/controlled/base.apk'),
                         emitter.COMMANDS['events'], emitter.COMMANDS['wifi'], emitter.COMMANDS['connectivity']])
        self.assertTrue(value['diagnosticOnly'])
        for key in ('releaseAcceptance', 'applicationAcceptance', 'originalEditingAcceptance', 'physicalPhoneAcceptance'):
            self.assertIs(value[key], False)

    def test_privacy_projection_retains_only_typed_events_and_bounded_latest_rows(self):
        secret = 'PRIVATE_SENTINEL_CREDENTIAL_SSID_ADDRESS'
        self.assertEqual(emitter.project_wifi('Wi-Fi is enabled\nSSID: ' + secret), dict(status='observed', enabled=True))
        self.assertEqual(emitter.project_wifi('Wifi is enabled\nSSID: ' + secret), dict(status='observed', enabled=True))
        self.assertEqual(emitter.project_wifi('Wifi is disabled\n'), dict(status='observed', enabled=False))
        self.assertEqual(emitter.project_wifi(secret)['status'], 'unavailable')
        connectivity = emitter.project_connectivity('Active default network: 102\nWIFI VPN ' + secret)
        self.assertEqual(connectivity['activeDefaultNetworkId'], 102)
        lines = ['10-31 01:02:03.004  123  456 I wpa_supplicant: CTRL-EVENT-DISCONNECTED reason=3 locally_generated=1 ' + secret
                 for _ in range(emitter.MAX_EVENTS + 5)]
        projected = emitter.project_events('\n'.join(lines))
        self.assertEqual(projected['totalMatched'], emitter.MAX_EVENTS + 5)
        self.assertEqual(len(projected['events']), emitter.MAX_EVENTS)
        self.assertEqual(projected['omitted'], 5)
        self.assertIs(projected['events'][0]['locallyGenerated'], True)
        self.assertNotIn(secret, json.dumps([projected, connectivity]))

    def test_existing_server_socket_uses_only_read_services_and_framed_bounded_output(self):
        deadline = time.monotonic() + emitter.MAX_TOTAL_SECONDS
        body = b'emulator-5554\tdevice product:controlled\n'
        stream = Stream(b'OKAY' + ('%04x' % len(body)).encode() + body)
        with patch.object(emitter.socket, 'create_connection', return_value=stream) as connect, \
                patch.object(emitter.subprocess, 'run', side_effect=AssertionError('Never execute adb CLI')):
            emitter.ExistingAdb(deadline).online()
        self.assertEqual(connect.call_args.args, (('127.0.0.1', 5037),))
        self.assertEqual(stream.sent, [b'000ehost:devices-l'])
        self.assertTrue(all(0 < x <= emitter.MAX_COMMAND_SECONDS for x in stream.timeouts))
        output = b'1\n'
        stream = Stream(b'OKAYOKAY' + struct.pack('<BI', 1, len(output)) + output + struct.pack('<BI', 3, 1) + b'\0')
        with patch.object(emitter.socket, 'create_connection', return_value=stream):
            self.assertEqual(emitter.ExistingAdb(deadline).read(emitter.COMMANDS['qemu']), '1\n')
        self.assertEqual(len(stream.sent), 2)
        self.assertIn(b'host:transport:emulator-5554', stream.sent[0])
        self.assertIn(b'shell,v2,raw:getprop ro.kernel.qemu', stream.sent[1])
        for parts in [('tcpip', '5555'), ('connect', '127.0.0.1:5556'), ('settings', 'put', 'global', 'wifi_on', '1'),
                      ('logcat', '-c'), ('am', 'force-stop', emitter.PACKAGE)]:
            with patch.object(emitter.socket, 'create_connection', side_effect=AssertionError('No mutating service')):
                with self.assertRaises(emitter.Unavailable):
                    emitter.ExistingAdb(deadline).read(parts)

    def test_truncated_oversize_bad_exit_and_offline_wire_inputs_never_become_observed(self):
        deadline = time.monotonic() + emitter.MAX_TOTAL_SECONDS
        frames = [b'OKAYOKAY', b'OKAYOKAY' + struct.pack('<BI', 1, emitter.MAX_STDOUT_BYTES + 1),
                  b'OKAYOKAY' + struct.pack('<BI', 9, 0),
                  b'OKAYOKAY' + struct.pack('<BI', 3, 1) + b'\x01']
        for raw in frames:
            with patch.object(emitter.socket, 'create_connection', return_value=Stream(raw)), self.assertRaises(emitter.Unavailable):
                emitter.ExistingAdb(deadline).read(emitter.COMMANDS['qemu'])
        for body in (b'emulator-5554\toffline\n', b'emulator-5554\tdevice\nemulator-5554\tdevice\n'):
            raw = b'OKAY' + ('%04x' % len(body)).encode() + body
            with patch.object(emitter.socket, 'create_connection', return_value=Stream(raw)), self.assertRaises(emitter.Unavailable):
                emitter.ExistingAdb(deadline).online()

    def test_actual_build_receipt_shape_without_tree_uses_bound_apk_stamp_and_rejects_mismatch(self):
        with tempfile.TemporaryDirectory(prefix='editing13-apk-control-') as directory:
            root = Path(directory)
            apk = root / 'app/build/outputs/apk/integration/app-x86_64-integration.apk'; apk.parent.mkdir(parents=True)
            receipt = root / 'work/gecko-integration/caret-apk-build-receipt.json'; receipt.parent.mkdir(parents=True)
            def create(tree=TREE):
                with ZipFile(apk, 'w') as archive:
                    archive.writestr('assets/pocketchat-integration-build.json', json.dumps(dict(schema=1, dirtySource=False, sourceCommit=SOURCE, sourceTree=tree)))
                # The actual caret_workflow/embedded_identity producer has no sourceTree field here.
                value = dict(sourceCommit=SOURCE, runId='123', runAttempt='1', integrationApkSha256=sha(apk.read_bytes()))
                receipt.write_text(json.dumps(value)); return value
            expected = create()
            result = emitter.apk_identity(root, identity(), time.monotonic() + 60)
            self.assertEqual(result['apkSha256'], expected['integrationApkSha256'])
            receipt.write_text(json.dumps(dict(expected, runAttempt='2')))
            with self.assertRaises(emitter.Unavailable): emitter.apk_identity(root, identity(), time.monotonic() + 60)
            create('c' * 40)
            with self.assertRaises(emitter.Unavailable): emitter.apk_identity(root, identity(), time.monotonic() + 60)
            create(); apk.write_bytes(apk.read_bytes() + b'changed')
            with self.assertRaises(emitter.Unavailable): emitter.apk_identity(root, identity(), time.monotonic() + 60)

    def test_expired_budget_is_unavailable_and_main_never_overrides_original_failure(self):
        self.assertEqual((emitter.MAX_TOTAL_SECONDS, emitter.MAX_COMMAND_SECONDS), (60, 4))
        with patch.object(emitter.time, 'monotonic', return_value=61), self.assertRaises(emitter.Unavailable):
            emitter.remaining(60)
        with tempfile.TemporaryDirectory(prefix='editing13-main-control-') as directory:
            root = Path(directory); (root / 'work/gecko-integration').mkdir(parents=True)
            stdout = io.StringIO()
            with patch.object(emitter, 'ROOT', root), patch.dict(emitter.os.environ, {}, clear=True), \
                    patch.object(sys, 'argv', ['diagnostic', '--adb', 'unused-never-executed', '--serial', emitter.SERIAL]), \
                    patch.object(emitter.socket, 'create_connection', side_effect=AssertionError('No owner no socket')), \
                    contextlib.redirect_stdout(stdout):
                self.assertEqual(emitter.main(), 0)
            self.assertTrue(stdout.getvalue().startswith(emitter.PREFIX))
            value = json.loads(stdout.getvalue()[len(emitter.PREFIX):])
            self.assertEqual(value['status'], 'unavailable')
            self.assertIs(value['originalEditingAcceptance'], False)
            self.assertLessEqual(len(stdout.getvalue().encode()), emitter.MAX_REPORT_BYTES + len(emitter.PREFIX) + 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
