#!/usr/bin/env python3
"""Focused-clock orchestration controls; no Android execution."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/gecko'))
import run_input_clock_diagnostic as runner
from run_caret_editing_phase import editing_commands


class FocusedClockControls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.out = self.root / 'work/gecko-integration'
        self.out.mkdir(parents=True)
        self.args = argparse.Namespace(root=self.root, out=self.out, adb='/fixed/adb', serial='emulator-5554')
        for name in ('build_receipt', 'sdk_receipt', 'sdk_aar', 'official_sdk_aar', 'integration_apk', 'release_apk'):
            path = self.root / name
            path.write_bytes(name.encode())
            setattr(self.args, name, path)

    def argv(self):
        result = ['--root', str(self.root), '--out', str(self.out), '--adb', self.args.adb, '--serial', self.args.serial]
        for name in ('build_receipt', 'sdk_receipt', 'sdk_aar', 'official_sdk_aar', 'integration_apk', 'release_apk'):
            result += ['--' + name.replace('_', '-'), str(getattr(self.args, name))]
        return result

    def test_exact_original_command_once_and_no_extra_flags(self):
        record = {}
        with patch.object(runner.subprocess, 'run', return_value=argparse.Namespace(returncode=0)) as called:
            self.assertEqual(runner.run_once(self.args, record), 0)
        called.assert_called_once_with(editing_commands(self.args)[0], cwd=self.root, check=False)
        self.assertEqual(record['workloads'][0]['invocationCount'], 1)
        self.assertNotIn('--native-input-diagnostics', called.call_args.args[0])
        self.assertNotIn('--input-diagnostics', called.call_args.args[0])

    def test_failure_is_recorded_and_never_replayed(self):
        record = {}
        with patch.object(runner.subprocess, 'run', return_value=argparse.Namespace(returncode=7)) as called:
            self.assertEqual(runner.run_once(self.args, record), 1)
            with self.assertRaisesRegex(ValueError, 'cannot replay'):
                runner.run_once(self.args, record)
        self.assertEqual(called.call_count, 1)
        self.assertEqual(record['workloads'][0]['exitCode'], 7)

    def test_terminated_process_does_not_become_success(self):
        record = {}
        with patch.object(runner.subprocess, 'run', return_value=argparse.Namespace(returncode=-15)) as called:
            with self.assertRaisesRegex(ValueError, 'terminated'):
                runner.run_once(self.args, record)
        self.assertEqual(called.call_count, 1)
        self.assertGreater(record['workloads'][0]['completedAtMonotonicNanos'], 0)

    def test_guard_wraps_one_workload_without_mutating_original_bytes(self):
        events = []
        raw = b'{"status":"failed","original":"unchanged"}\n'
        def actual_child(*args, **kwargs):
            events.append('workload')
            (self.out / 'gecko-performance-results.json').write_bytes(raw)
            return argparse.Namespace(returncode=1)
        class Guard:
            def __init__(self, **kwargs):
                self.record = kwargs['record']
            def run(self, call):
                events.append('prepare')
                value = call()
                events.append('restore')
                self.record['restorationVerified'] = True
                return value
        with patch.object(runner, 'validate_identity', return_value={'schema': 1}), \
             patch.object(runner, 'LauncherGuard', Guard), patch.object(runner.subprocess, 'run', side_effect=actual_child):
            self.assertEqual(runner.main(self.argv()), 1)
        self.assertEqual(events, ['prepare', 'workload', 'restore'])
        self.assertEqual((self.out / 'gecko-performance-results.json').read_bytes(), raw)
        value = json.loads((self.out / runner.OUTCOME).read_bytes())
        self.assertTrue(value['diagnosticOnly'])
        self.assertFalse(value['releaseAcceptance'])
        self.assertFalse(value['applicationAcceptance'])
        self.assertEqual(value['phaseStatus'], 'workload-failed-restored')

    def test_restore_failure_cannot_pass_after_successful_workload(self):
        class Guard:
            def __init__(self, **kwargs): pass
            def run(self, call):
                self.assertion = call()
                raise RuntimeError('restore failed')
        with patch.object(runner, 'validate_identity', return_value={'schema': 1}), \
             patch.object(runner, 'LauncherGuard', Guard), \
             patch.object(runner.subprocess, 'run', return_value=argparse.Namespace(returncode=0)) as called:
            self.assertEqual(runner.main(self.argv()), 2)
        self.assertEqual(called.call_count, 1)
        value = json.loads((self.out / runner.OUTCOME).read_bytes())
        self.assertEqual(value['status'], 'failed')
        self.assertEqual(value['error'], 'restore failed')
        self.assertFalse(value['releaseAcceptance'])

    def test_stale_outcome_and_raw_reports_rejected_without_device_calls(self):
        for name in (runner.OUTCOME, 'gecko-performance-results.json', 'gecko-performance-build-identity.json'):
            path = self.out / name
            path.write_bytes(b'old')
            with patch.object(runner, 'validate_identity') as validate:
                with self.assertRaises(ValueError): runner.main(self.argv())
                validate.assert_not_called()
            self.assertEqual(path.read_bytes(), b'old')
            path.unlink()

    def test_identity_rejects_foreign_run_and_changed_apk(self):
        source, tree = '1' * 40, '2' * 40
        expected = dict(schema=1, sourceCommit=source, runId='101', runAttempt='1')
        build = dict(expected, integrationApkSha256=runner.digest(self.args.integration_apk),
                     releaseApkSha256=runner.digest(self.args.release_apk))
        self.args.build_receipt.write_text(json.dumps(build))
        def check(environment):
            with patch.object(runner.subprocess, 'check_output', side_effect=[source, tree, '']), \
                 patch.object(runner, 'validate_sdk_receipt', return_value=dict(sourceCommit=source, sourceTree=tree)), \
                 patch.object(runner, 'embedded_identity', return_value=expected), patch.dict(os.environ, environment):
                return runner.validate_identity(self.args, {})
        self.assertEqual(check({'GITHUB_RUN_ID': '101', 'GITHUB_RUN_ATTEMPT': '1'})['sourceTree'], tree)
        with self.assertRaisesRegex(ValueError, 'CI invocation'):
            check({'GITHUB_RUN_ID': '102', 'GITHUB_RUN_ATTEMPT': '1'})
        self.args.integration_apk.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'APK bytes'):
            check({'GITHUB_RUN_ID': '101', 'GITHUB_RUN_ATTEMPT': '1'})

    def test_workflow_has_one_focused_call_and_read_only_artifacts(self):
        raw = (ROOT / '.github/workflows/gecko-input-clock-diagnostic.yml').read_text()
        self.assertIn("branches: ['debug/gecko-input-clock-*']", raw)
        self.assertIn('contents: read', raw)
        self.assertNotIn('contents: write', raw)
        self.assertEqual(raw.count('python3 tools/gecko/run_input_clock_diagnostic.py '), 1)
        self.assertNotIn('publish_ci', raw)
        self.assertNotIn('publish_input', raw)
        self.assertNotIn('for trial', raw)
        self.assertNotIn('--native-input-diagnostics', raw)
        artifact = raw.split('        path: |\n', 1)[1].split('        if-no-files-found:', 1)[0]
        self.assertIn('native-input-*.json', artifact)
        self.assertIn('native-input-*.log', artifact)
        self.assertIn('installed-apk-read-performance-*.json', artifact)
        self.assertNotIn('.jks', artifact)
        self.assertNotIn('.apk', artifact)
        self.assertNotIn('commands.json', artifact)
        self.assertIn('      if: always()', raw)

    def test_original_setup_commands_and_shell_syntax(self):
        raw = (ROOT / '.github/workflows/gecko-input-clock-diagnostic.yml').read_text()
        original = (ROOT / '.github/workflows/gecko-integration.yml').read_text()
        # The concrete bootstrap/setup commands must come from the original
        # qualified path, including its pinned network and display identity.
        markers = ('"$ANDROID_HOME/emulator/emulator" -avd', 'python3 tools/gecko/prepare_native_adb.py ',
                   'python3 tools/gecko/prepare_emulator.py ', 'python3 tools/gecko/prepare_platform_tools.py ',
                   'python3 tools/gecko/prepare_android_image.py ', 'python3 tools/gecko/build_native_input_driver.py ',
                   'python3 tools/gecko/caret_workflow.py ', 'work/gecko-integration/gradle/gradle-9.8.0/bin/gradle :app:')
        for line in raw.splitlines():
            if any(line.strip().startswith(x) for x in markers):
                self.assertIn(line.strip(), original)
        blocks = raw.split('      run: |\n')[1:]
        for block in blocks:
            lines = []
            for line in block.splitlines():
                if line and not line.startswith('        '): break
                lines.append(line[8:])
            subprocess.run(['bash', '-n'], input='\n'.join(lines), text=True, check=True)


if __name__ == '__main__':
    unittest.main()
