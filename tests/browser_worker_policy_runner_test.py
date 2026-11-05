"""Actual runner parsing/finalization with explicit fake adb/server boundaries.

These are deterministic transport controls, not Android, WebView, TLS or Worker
execution evidence. All simulated reports stay in this test's temporary path.
"""
import copy
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

import browser_worker_policy_evidence_test as synthetic_schema

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('worker_policy_runner', ROOT / 'tools/browser/run_worker_policy_integration.py')
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)
SOURCE, TREE, NONCE = 'a' * 40, 'b' * 40, 'c' * 32


class WorkerRunnerTests(unittest.TestCase):
    def document(self):
        return synthetic_schema.WorkerEvidenceTests().document()

    def read(self, value):
        identity = self.document()['expectedBuildIdentity']
        return runner.read_activity(json.dumps(value).encode(), NONCE, SOURCE, identity)

    def test_real_parser_accepts_current_and_ignores_pending_or_other_invocation(self):
        value = self.document()['results']['chromium']
        self.assertEqual(self.read(value), value)
        changed = copy.deepcopy(value)
        changed['runNonce'] = 'f' * 32
        self.assertIsNone(self.read(changed))
        for raw in (b'', b'not-json', b'null', b'[]', b'{}'):
            self.assertIsNone(runner.read_activity(raw, NONCE, SOURCE, {}))

    def test_original_device_bytes_reject_duplicate_fields_and_nonfinite_values(self):
        report = self.document()
        value, identity = report['results']['chromium'], report['expectedBuildIdentity']
        raw = json.dumps(value).encode()
        # Each would be silently folded/accepted by the old json.loads path and
        # then disappear from a strictly parsed, reserialized wrapper.
        for malformed in (raw[:-1] + b',"status":"passed"}',
                          raw[:-1] + b',"checks":[]}',
                          raw[:-1] + b',"nonFinite":NaN}',
                          raw[:-1] + b',"nonFinite":Infinity}'):
            with self.subTest(raw=malformed[-60:]), self.assertRaises(ValueError):
                runner.read_activity(malformed, NONCE, SOURCE, identity)

    def test_parser_keeps_bound_source_engine_apk_run_attempt_and_size_guards(self):
        changes = [lambda row: row.update(sourceCommit='f' * 40),
                   lambda row: row.update(engine='gecko'),
                   lambda row: row['buildIdentity'].update(sourceTree='f' * 40),
                   lambda row: row['buildIdentity'].update(apkSha256='f' * 64),
                   lambda row: row['buildIdentity']['sdkBuildIdentity'].update(runAttempt=2)]
        for change in changes:
            value = self.document()['results']['chromium']
            change(value)
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.read(value)
        with self.assertRaises(ValueError):
            runner.read_activity(b'x' * (1024 * 1024 + 1), NONCE, SOURCE, {})

    def execute_finalization(self, late_request):
        """Run the real main/finally; only process/TLS/adb boundaries are fakes."""
        schema = self.document()
        identity = schema['expectedBuildIdentity']
        activity = schema['results']['chromium']
        events = []
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'output'
            material = Path(directory) / 'host-private-material'
            material.mkdir()
            class Certificates:
                ca_sha = 'd' * 64
                leaf_sha = 'e' * 64
                public = {}
                directory = material
                def close(self):
                    events.append('material-removed')
                    self.directory.rmdir()
            class Server:
                port = 23456
                closed = False
                def __init__(self, *args, **kwargs):
                    self.requests = []
                def start(self):
                    return self
                def begin(self, engine):
                    events.append('begin-' + engine)
                def close(self):
                    events.append('server-close')
                    if late_request:
                        # Model a connection accepted before stop but recorded
                        # while its worker unwinds during native/server cleanup.
                        self.requests.append(dict(phase='restrict', realm='dedicated-classic', path='/worker-probe'))
                    self.closed = True
                def snapshot(self, engine):
                    events.append('snapshot')
                    return dict(serverClosed=self.closed, requests=copy.deepcopy(self.requests))
            class Ca:
                def __init__(self, *args):
                    self.receipt = dict(removedAfterExecution=False)
                def install(self):
                    events.append('ca-installed')
                def remove(self):
                    events.append('ca-removed')
                    self.receipt['removedAfterExecution'] = True
            started = False
            def adb(command, **kwargs):
                nonlocal started
                values = command[3:]
                data = b''
                if values == ['shell', 'getprop', 'ro.kernel.qemu']:
                    data = b'1\n'
                elif values[:3] == ['exec-out', 'content', 'read']:
                    data = json.dumps(identity if values[-1].endswith('/build-identity') else activity).encode()
                elif values == ['shell', 'pm', 'clear', 'local.pocketchat.test']:
                    data = b'Success\n'
                elif values == ['shell', 'id', '-u']:
                    data = b'2000\n'
                elif values == ['shell', 'am', 'force-stop', 'local.pocketchat.test']:
                    if started:
                        events.append('app-stop')
                elif values[:1] == ['shell'] and len(values) == 2 and values[1].startswith('am start '):
                    started = True
                elif values[:2] == ['reverse', '--remove']:
                    events.append('reverse-removed')
                return subprocess.CompletedProcess(command, 0, data, b'')
            def git(command, **kwargs):
                if command[:2] == ['git', 'show']:
                    # This unit fixture's deliberately synthetic aaaa commit
                    # does not ship a derived SDK manifest. Do not substitute
                    # any selected current production source into runtime tests.
                    raise subprocess.CalledProcessError(128, command, stderr=b'Synthetic source is not a Git commit')
                if command[:3] == ['git', 'status', '--porcelain']:
                    return ''
                return TREE + '\n' if command[-1] == 'HEAD^{tree}' else SOURCE + '\n'
            verified = []
            def verify(directory, source, expected):
                value = json.loads((Path(directory) / 'worker-policy-results.json').read_bytes())
                fixture = value['results']['chromium']['fixture']
                verified.append(fixture)
                if not fixture['serverClosed']:
                    raise ValueError('Snapshot taken before host connections were closed')
                if any(row['phase'] == 'restrict' for row in fixture['requests']):
                    raise ValueError('Late restricted Worker reached host')
                return {}
            patches = [mock.patch.object(runner.sys, 'argv', ['run_worker_policy_integration.py', '--output', str(output)]),
                       mock.patch.object(runner.subprocess, 'check_output', side_effect=git),
                       mock.patch.object(runner.subprocess, 'run', side_effect=adb),
                       mock.patch.object(runner, 'expected_build', return_value=identity),
                       mock.patch.object(runner, 'source_inputs', return_value=[Path(__file__).resolve()]),
                       mock.patch.object(runner.uuid, 'uuid4', return_value=mock.Mock(hex=NONCE)),
                       mock.patch.object(runner, 'EphemeralCertificates', Certificates),
                       mock.patch.object(runner, 'WorkerFixtureServer', Server),
                       mock.patch.object(runner, 'AndroidUserCa', Ca),
                       mock.patch.object(runner, 'verify_worker_policy_evidence', side_effect=verify),
                       mock.patch.object(runner.sys, 'stdout', io.StringIO())]
            from contextlib import ExitStack
            with ExitStack() as stack:
                for patch in patches:
                    stack.enter_context(patch)
                if late_request:
                    with self.assertRaisesRegex(ValueError, 'Late restricted Worker'):
                        runner.main()
                else:
                    runner.main()
            value = json.loads((output / 'worker-policy-results.json').read_bytes())
            self.assertEqual(events.count('snapshot'), 1)
            self.assertLess(events.index('app-stop'), events.index('server-close'))
            self.assertLess(events.index('server-close'), events.index('snapshot'))
            self.assertTrue(value['hostTls']['reverseRemoved'])
            self.assertTrue(value['hostTls']['privateMaterialRemoved'])
            self.assertTrue(value['hostTls']['trustInstallation']['removedAfterExecution'])
            self.assertFalse(material.exists())
            self.assertEqual(len(verified), 1)
            return value

    def test_real_main_final_snapshot_follows_native_stop_and_server_close(self):
        value = self.execute_finalization(False)
        self.assertEqual(value['status'], 'passed')
        self.assertEqual(value['results']['chromium']['fixture']['requests'], [])

    def test_real_main_late_restricted_request_remains_visible_and_rejects_pass(self):
        value = self.execute_finalization(True)
        self.assertEqual(value['status'], 'failed')
        self.assertEqual(value['results']['chromium']['fixture']['requests'][0]['phase'], 'restrict')
        self.assertIn('Late restricted Worker', value['validationError'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
