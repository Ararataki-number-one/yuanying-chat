#!/usr/bin/env python3
"""Local stdin/start-failure contracts for the real diagnostic collector."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    'scheduler_trace_input_under_test', ROOT / 'tools/gecko/trace_input_scheduler.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SchedulerTraceInputTest(unittest.TestCase):
    SOURCE = '1' * 40
    TREE = '2' * 40
    NONCE = '3' * 32
    KEY = 'pc-input-' + NONCE
    COMMAND = b'set -euo pipefail\n: original-workload-fixture\n'

    def exercise(self, *, start_code=0, start_timeout=False, workload_code=0):
        temporary = tempfile.TemporaryDirectory(prefix='scheduler-trace-input-')
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        out = root / 'work/input-scheduler-diagnostic'
        out.mkdir(parents=True)
        command = out / 'original-editing.sh'
        command.write_bytes(self.COMMAND)
        identity = dict(sourceCommit=self.SOURCE, sourceTree=self.TREE,
                        runId='123456', runAttempt='1')
        build = dict(identity)
        for field, relative, content in (
                ('integrationApkSha256', 'app/build/outputs/apk/integration/app-x86_64-integration.apk', b'integration-fixture'),
                ('releaseApkSha256', 'app/build/outputs/apk/release/app-arm64-v8a-release-unsigned.apk', b'release-fixture')):
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
            build[field] = hashlib.sha256(content).hexdigest()
        for relative, value in (
                ('work/gecko-integration/ci-build-index.json', identity),
                ('work/gecko-integration/caret-apk-build-receipt.json', build),
                ('work/native-caret-sdk/sdk-build-receipt.json', identity)):
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(value))

        def git_output(argv, **kwargs):
            if argv == ['git', 'rev-parse', 'HEAD']:
                return self.SOURCE + '\n'
            if argv == ['git', 'rev-parse', 'HEAD^{tree}']:
                return self.TREE + '\n'
            if argv == ['git', 'status', '--porcelain']:
                return '' if kwargs.get('text') else b''
            if argv == ['git', 'diff', '--name-status', MODULE.BASE, self.SOURCE]:
                return 'A\ttools/gecko/trace_input_scheduler.py\n'
            raise AssertionError('Unexpected git request: ' + repr(argv))

        calls = []
        start_stdout = b'start-stdout\x00\xff'
        start_stderr = b'start-stderr\x00\xfe'

        def process(argv, **kwargs):
            calls.append((list(argv), dict(kwargs)))
            if argv[0] == 'bash':
                return subprocess.CompletedProcess(argv, workload_code)
            self.assertEqual(argv[:3], ['test-adb', '-s', 'emulator-5554'])
            tail = argv[3:]
            if tail[:2] == ['shell', 'perfetto'] and '--detach=' + self.KEY in tail:
                if start_timeout:
                    raise subprocess.TimeoutExpired(argv, kwargs['timeout'],
                                                    output=start_stdout, stderr=start_stderr)
                return subprocess.CompletedProcess(argv, start_code, start_stdout, start_stderr)
            if tail and tail[0] == 'pull':
                Path(tail[-1]).write_bytes(b'bounded-fake-trace')
            return subprocess.CompletedProcess(argv, 0, b'fixture-output\n', b'')

        args = argparse.Namespace(out=out, command_file=command, sample='1',
                                  adb='test-adb', serial='emulator-5554')
        with mock.patch.object(MODULE, 'ROOT', root), \
                mock.patch.object(MODULE.subprocess, 'check_output', side_effect=git_output), \
                mock.patch.object(MODULE.subprocess, 'run', side_effect=process), \
                mock.patch.object(MODULE, 'host_snapshot'), \
                mock.patch.object(MODULE, 'original_command', return_value=self.COMMAND), \
                mock.patch.object(MODULE.uuid, 'uuid4', return_value=SimpleNamespace(hex=self.NONCE)), \
                mock.patch.dict(os.environ, GITHUB_SHA=self.SOURCE,
                                GITHUB_RUN_ID=identity['runId'], GITHUB_RUN_ATTEMPT=identity['runAttempt']):
            code = MODULE.run(args)
        record = json.loads((out / 'diagnostic-run.json').read_bytes())
        return SimpleNamespace(code=code, record=record, calls=calls, root=root,
                               out=out, command=command, start_stdout=start_stdout,
                               start_stderr=start_stderr)

    def assert_stdin_and_own_cleanup(self, result):
        starts = [(argv, kwargs) for argv, kwargs in result.calls
                  if '--detach=' + self.KEY in argv]
        self.assertEqual(len(starts), 1)
        expected_remote = '/data/misc/perfetto-traces/' + self.KEY + '.perfetto-trace'
        self.assertEqual(starts[0][0], [
            'test-adb', '-s', 'emulator-5554', 'shell', 'perfetto', '--txt',
            '--config', '-', '--out', expected_remote, '--detach=' + self.KEY])
        config = (result.out / 'perfetto-config.pbtxt').read_bytes()
        self.assertEqual(starts[0][1]['input'], config)
        self.assertTrue(starts[0][1]['capture_output'])
        self.assertGreater(starts[0][1]['timeout'], 0)
        self.assertEqual(config, MODULE.config_text(self.KEY).encode())
        self.assertFalse(any(argv[3:4] == ['push'] for argv, _ in result.calls))
        stops = [argv for argv, _ in result.calls if '--stop' in argv]
        self.assertEqual(stops, [[
            'test-adb', '-s', 'emulator-5554', 'shell', 'perfetto',
            '--attach=' + self.KEY, '--stop']])
        pulls = [argv for argv, _ in result.calls if argv[3:4] == ['pull']]
        self.assertEqual(pulls, [[
            'test-adb', '-s', 'emulator-5554', 'pull', expected_remote,
            str(result.out / 'android.perfetto-trace')]])
        self.assertFalse(any(any(word in ('kill', 'killall', 'pkill') for word in argv)
                             for argv, _ in result.calls))
        self.assertEqual((result.out / 'start-own-session.stdout.log').read_bytes(), result.start_stdout)
        self.assertEqual((result.out / 'start-own-session.stderr.log').read_bytes(), result.start_stderr)
        self.assertIs(result.record['diagnosticOnly'], True)
        self.assertIs(result.record['applicationAcceptance'], False)
        self.assertLessEqual(sum(argv[0] == 'bash' for argv, _ in result.calls), 1)
        return config

    def test_success_uses_exact_local_config_stdin_once(self):
        result = self.exercise()
        config = self.assert_stdin_and_own_cleanup(result)
        self.assertEqual(result.code, 0)
        self.assertIs(result.record['traceStartSucceeded'], True)
        self.assertEqual(result.record['workloadInvocationCount'], 1)
        bash = [(argv, kwargs) for argv, kwargs in result.calls if argv[0] == 'bash']
        self.assertEqual(len(bash), 1)
        self.assertEqual(bash[0][0], ['bash', '--noprofile', '--norc', '-e', '-o',
                                     'pipefail', str(result.command)])
        self.assertEqual(bash[0][1], dict(cwd=result.root))
        self.assertEqual(result.record['configSource'], 'stdin')
        self.assertEqual(result.record['configFile'], 'perfetto-config.pbtxt')
        self.assertEqual(result.record['configBytes'], len(config))
        self.assertEqual(result.record['configSha256'], hashlib.sha256(config).hexdigest())

    def test_nonzero_start_never_launches_original_workload(self):
        result = self.exercise(start_code=13)
        self.assert_stdin_and_own_cleanup(result)
        self.assertNotEqual(result.code, 0)
        self.assertIs(result.record['traceStartSucceeded'], False)
        self.assertEqual(result.record['workloadInvocationCount'], 0)
        self.assertFalse(any(argv[0] == 'bash' for argv, _ in result.calls))
        self.assertEqual(result.record['status'], 'incomplete')
        start = [row for row in result.record['collectorCalls'] if row['label'] == 'start-own-session']
        self.assertEqual(start[0]['returnCode'], 13)

    def test_timed_out_start_preserves_error_bytes_and_cleans_only_own_key(self):
        result = self.exercise(start_timeout=True)
        self.assert_stdin_and_own_cleanup(result)
        self.assertNotEqual(result.code, 0)
        self.assertIs(result.record['traceStartSucceeded'], False)
        self.assertEqual(result.record['workloadInvocationCount'], 0)
        self.assertFalse(any(argv[0] == 'bash' for argv, _ in result.calls))
        self.assertEqual(result.record['status'], 'incomplete')
        start = [row for row in result.record['collectorCalls'] if row['label'] == 'start-own-session']
        self.assertIsNone(start[0]['returnCode'])

    def test_original_workload_failure_does_not_replay(self):
        result = self.exercise(workload_code=1)
        self.assert_stdin_and_own_cleanup(result)
        self.assertEqual(result.code, 1)
        self.assertEqual(result.record['workloadInvocationCount'], 1)
        self.assertEqual(result.record['workloadExitCode'], 1)
        self.assertEqual(sum(argv[0] == 'bash' for argv, _ in result.calls), 1)


if __name__ == '__main__':
    unittest.main()
