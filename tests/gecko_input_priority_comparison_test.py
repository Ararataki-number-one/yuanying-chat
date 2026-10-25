#!/usr/bin/env python3
"""Host controls for exact-source, no-replay priority experiments; no Android."""
import argparse
import copy
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
import run_input_priority_comparison as comparison
from run_caret_editing_phase import editing_commands


def raw_gesture(priority=0):
    events, slots = [], []
    for index in range(21):
        planned = 1000 + index * 15
        events.append(dict(plannedUptimeMs=planned, eventTime=planned + 1, callStartUptimeMs=planned + 1))
        slots.append(dict(index=index, plannedUptimeMs=planned, untilEnteredUptimeMs=planned - 5,
                          requestedSleepMs=5, untilReturnedUptimeMs=planned, nextNowUptimeMs=planned,
                          threadCpuBeforeNs=index * 10, threadCpuAfterNs=index * 10 + 2))
    return dict(driverPid=123, readyUptimeMs=990, finishedUptimeMs=1320,
                trace=dict(events=events, startUptimeMs=1000),
                ownedClockObservation=dict(diagnosticOnly=True, timingPerturbationPossible=True,
                    dropped=0, capacity=21, cpuObservationErrors=0, uptimeObservationErrors=0,
                    slots=slots, before=dict(priority=priority, tid=123, uptimeMs=995),
                    after=dict(priority=priority, tid=123, uptimeMs=1310)),
                ownedPriorityExperiment=dict(experimentalOnly=True, originalPriority=0, requestedPriority=-4,
                    actualAppliedPriority=-4, actualRestoredPriority=0, attempted=True, applied=True,
                    restoreAttempted=True, restoreVerified=True, tid=123, pid=123, uid=2000,
                    applyUptimeMs=985, restoreUptimeMs=1315))


class PriorityControls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.args = argparse.Namespace(root=self.root, roles=self.root / 'roles', out=self.root / 'out',
                                      order='AB', adb='/actual/adb')
        self.ci = dict(runId='12', runAttempt='1', eventSourceCommit='b' * 40)

    def orders(self, a=(5, 0), b=(4, 0)):
        return {order: {role: dict(metrics={name: dict(maxLatenessMs=value)
                    for name, value in zip(comparison.GESTURES, values)})
                    for role, values in (('A', a), ('B', b))} for order in ('AB', 'BA')}

    def test_predeclared_worst_improves_with_zero_floor(self):
        result = comparison.decision(self.orders())
        self.assertTrue(result['retainRecommended'])
        self.assertEqual(len(result['comparisons']), 4)
        self.assertEqual(len(result['orderAggregates']), 2)

    def test_tie_single_regression_or_missing_order_never_support_retention(self):
        self.assertFalse(comparison.decision(self.orders(a=(5, 0), b=(5, 0)))['retainRecommended'])
        self.assertFalse(comparison.decision(self.orders(a=(5, 0), b=(4, 1)))['retainRecommended'])
        values = self.orders(); values['BA'] = self.orders(a=(5, 0), b=(5, 0))['BA']
        self.assertFalse(comparison.decision(values)['retainRecommended'])
        for values in ({'AB': self.orders()['AB']}, self.orders(b=(True, 0)), self.orders(b=(31, 0))):
            with self.assertRaises(ValueError): comparison.decision(values)

    def test_actual_clock_chain_and_reversible_priority(self):
        self.assertEqual(comparison.gesture_metrics(raw_gesture(), 'A')['maxLatenessMs'], 1)
        self.assertEqual(comparison.gesture_metrics(raw_gesture(-4), 'B')['maxLatenessMs'], 1)
        mutations = [lambda v: v['ownedPriorityExperiment'].update(restoreVerified=False),
                     lambda v: v['ownedPriorityExperiment'].update(actualRestoredPriority=-4),
                     lambda v: v['ownedPriorityExperiment'].update(originalPriority=False),
                     lambda v: v['ownedPriorityExperiment'].update(tid=124),
                     lambda v: v['ownedPriorityExperiment'].update(applyUptimeMs=1001),
                     lambda v: v['ownedClockObservation']['before'].update(priority=0),
                     lambda v: v['ownedClockObservation']['slots'][2].update(nextNowUptimeMs=9999),
                     lambda v: v['ownedClockObservation']['slots'][2].update(requestedSleepMs=15),
                     lambda v: v['ownedClockObservation'].update(dropped=1),
                     lambda v: v['trace']['events'][2].update(callStartUptimeMs=1061)]
        for mutate in mutations:
            value = raw_gesture(-4); mutate(value)
            with self.assertRaises(ValueError): comparison.gesture_metrics(value, 'B')

    def test_signed_package_switch_uninstalls_before_install_and_rejects_query_failure(self):
        rows = []
        def call(adb, record, *parts, **kwargs):
            rows.append(parts)
            return argparse.Namespace(returncode=0, stdout=b'package:/data/app/old/base.apk\n', stderr=b'')
        with patch.object(comparison, 'adb_command', side_effect=call):
            comparison.install_role('/adb', {}, Path('/role.apk'))
        self.assertEqual(rows, [('shell', 'pm', 'path', 'local.pocketchat.test'),
                                ('uninstall', 'local.pocketchat.test'), ('install', '/role.apk')])
        with patch.object(comparison, 'adb_command', return_value=argparse.Namespace(returncode=1, stdout=b'', stderr=b'')) as call:
            comparison.install_role('/adb', {}, Path('/role.apk'))
            self.assertEqual(call.call_count, 2)
        with patch.object(comparison, 'adb_command', return_value=argparse.Namespace(returncode=1, stdout=b'', stderr=b'offline')) as call:
            with self.assertRaises(ValueError): comparison.install_role('/adb', {}, Path('/role.apk'))
            self.assertEqual(call.call_count, 1)

    def run_pair(self, codes=(0, 0), restoration=True, devices=None):
        plan = dict(roles={role: dict(checkout=str(self.args.roles / role), sourceCommit=role.lower() * 40,
                                    sourceTree='c' * 40, appTree='d' * 40) for role in 'AB'})
        calls = []
        for role in 'AB': (self.args.roles / role / 'work/gecko-integration').mkdir(parents=True)
        self.args.out.mkdir()
        def validated(a, row): row.update(runId='12', runAttempt='1')
        def child(command, **kwargs):
            if 'prepare_emulator.py' in command[1]: return argparse.Namespace(returncode=0)
            self.assertEqual(Path(command[1]).name, 'run_input_clock_diagnostic.py')
            calls.append(command)
            role = Path(command[1]).parents[2].name
            out = self.args.roles / role / 'work/gecko-integration'
            code = codes[len(calls) - 1]
            (out / 'native-input-clock-outcome.json').write_text(json.dumps(dict(
                launcherEnvironment=dict(restorationVerified=restoration), exitCode=code)))
            return argparse.Namespace(returncode=code)
        device = dict(bootId='one-device')
        with patch.object(comparison, 'identity', return_value=self.ci), \
             patch.object(comparison, 'load_plan', return_value=plan), \
             patch.object(comparison, 'validate_identity', side_effect=validated), \
             patch.object(comparison, 'device', side_effect=devices or [device] * 5), \
             patch.object(comparison, 'install_role'), patch.object(comparison, 'adb_command'), \
             patch.object(comparison, 'role_evidence', return_value={'status': 'passed'}), \
             patch.object(comparison.subprocess, 'run', side_effect=child):
            code = comparison.run(self.args)
        return code, calls, json.loads((self.args.out / 'comparison.json').read_text())

    def test_both_roles_once_and_failed_flow_retained_without_retry(self):
        code, calls, record = self.run_pair((1, 0))
        self.assertEqual(code, 1)
        self.assertEqual(len(calls), 2)
        self.assertEqual([row['role'] for row in record['roles']], ['A', 'B'])
        self.assertEqual([row['status'] for row in record['roles']], ['failed', 'passed'])
        with patch.object(comparison, 'load_plan', return_value={}):
            with self.assertRaisesRegex(ValueError, 'repeated'): comparison.run(self.args)

    def test_fatal_restore_failure_stops_next_role(self):
        code, calls, record = self.run_pair((2, 0), restoration=False)
        self.assertEqual(code, 1); self.assertEqual(len(calls), 1)
        self.assertIn('Environment/restoration failed', record['error'])

    def test_emulator_reboot_stops_without_running_role(self):
        code, calls, record = self.run_pair(devices=[dict(bootId='one'), dict(bootId='two')])
        self.assertEqual(code, 1); self.assertEqual(calls, [])
        self.assertIn('reboot', record['error'])

    def test_original_wrapper_argv_is_unchanged(self):
        a = comparison.role_args(self.root, '/actual/adb')
        command = comparison.original_command(a)
        self.assertNotIn('--native-input-diagnostics', command)
        self.assertNotIn('--timeout', command)
        self.assertEqual(command.count(str(a.root / 'tools/gecko/run_input_clock_diagnostic.py')), 1)
        # That existing wrapper is source-frozen and calls this exact original command.
        self.assertIn('run_once(args, record)', (ROOT / 'tools/gecko/run_input_clock_diagnostic.py').read_text())
        self.assertEqual(editing_commands(a)[0][1], str(self.root / 'tests/gecko/run_caret_bound_performance.py'))

    def test_retention_exact_original_bytes_excludes_keys_apks_and_replacement(self):
        path = self.args.roles / 'A/work/gecko-integration'; path.mkdir(parents=True)
        samples = {'native-input-test.json': b'{"status":"failed"}\n', 'native-input-test.log': b'raw\x00stderr',
                   'integration-test.jks': b'key', 'native-input-driver.apk': b'apk', 'arbitrary.txt': b'other'}
        for name, raw in samples.items(): (path / name).write_bytes(raw)
        with patch.object(comparison, 'identity', return_value=self.ci): comparison.retain(self.args)
        manifest = json.loads((self.args.out / 'raw-manifest.json').read_text())
        self.assertEqual({row['path'] for row in manifest['files']}, {'A/native-input-test.json', 'A/native-input-test.log'})
        self.assertEqual((self.args.out / 'A/native-input-test.log').read_bytes(), samples['native-input-test.log'])
        with patch.object(comparison, 'identity', return_value=self.ci):
            with self.assertRaises(ValueError): comparison.retain(self.args)

    def test_symlink_raw_is_rejected(self):
        path = self.args.roles / 'A/work/gecko-integration'; path.mkdir(parents=True)
        (self.root / 'secret').write_text('private')
        (path / 'native-input-test.log').symlink_to(self.root / 'secret')
        with patch.object(comparison, 'identity', return_value=self.ci):
            with self.assertRaisesRegex(ValueError, 'Unsafe'): comparison.retain(self.args)

    def test_missing_evidence_writes_failed_decision_without_fallback(self):
        self.args.inputs = self.root / 'absent'
        with patch.object(comparison, 'identity', return_value=self.ci), patch.object(comparison, 'validate_sources', return_value={}):
            self.assertEqual(comparison.decide(self.args), 1)
        result = json.loads((self.args.out / 'priority-decision.json').read_text())
        self.assertFalse(result['retainRecommended']); self.assertFalse(result['releaseAcceptance'])

    def test_aggregate_roundtrip_rejects_raw_tamper_foreign_run_role_failure_and_device_change(self):
        self.args.inputs = self.root / 'inputs'
        device = dict(bootId='same')
        for order in ('AB', 'BA'):
            folder = self.args.inputs / order; folder.mkdir(parents=True)
            entries, bootstrap = [], []
            for role in 'AB':
                path = folder / role / 'native-input-receipt.json'
                path.parent.mkdir(); path.write_bytes(b'{"original":"bytes"}\n')
                entries.append(dict(path=str(path.relative_to(folder)), bytes=path.stat().st_size, sha256=comparison.digest(path)))
            for name in ('android-emulator-package-results.json', 'android-system-image-results.json', 'android-platform-tools-results.json'):
                path = folder / 'bootstrap' / name; path.parent.mkdir(exist_ok=True); path.write_text('{}')
                bootstrap.append(dict(path=str(path.relative_to(folder)), bytes=2, sha256=comparison.digest(path)))
            (folder / 'raw-manifest.json').write_text(json.dumps(dict(**self.ci, files=entries, bootstrapFiles=bootstrap)))
            (folder / 'comparison.json').write_text(json.dumps(dict(**self.ci, order=order, status='passed', device=device,
                roles=[dict(role=role, status='passed', invocationCount=1, deviceBefore=device, deviceAfter=device) for role in order])))
        roles = {role: dict(sourceCommit=role.lower() * 40, sourceTree='c' * 40) for role in 'AB'}
        def verify(folder, expected, role, root):
            return dict(self.orders()[folder.parent.name][role], originalDevice={'actual': 'same'}, originalGestures=['same'])
        def decide():
            with patch.object(comparison, 'identity', return_value=self.ci), \
                 patch.object(comparison, 'validate_sources', return_value=roles), \
                 patch.object(comparison, 'role_evidence', side_effect=verify):
                code = comparison.decide(self.args)
            result = json.loads((self.args.out / 'priority-decision.json').read_text())
            (self.args.out / 'priority-decision.json').unlink()
            return code, result
        code, result = decide(); self.assertEqual(code, 0); self.assertTrue(result['retainRecommended'])
        target = self.args.inputs / 'AB/A/native-input-receipt.json'; original = target.read_bytes()
        target.write_bytes(original + b'changed')
        code, result = decide(); self.assertEqual(code, 1); self.assertFalse(result['retainRecommended'])
        target.write_bytes(original)
        record_path = self.args.inputs / 'BA/comparison.json'; original = record_path.read_bytes()
        for change in (lambda v: v.update(runId='foreign'),
                       lambda v: v['roles'][0].update(status='failed'),
                       lambda v: v['roles'][0].update(deviceAfter={'bootId': 'reboot'}),
                       lambda v: v['roles'][0].update(invocationCount=2)):
            value = json.loads(original); change(value); record_path.write_text(json.dumps(value))
            code, result = decide(); self.assertEqual(code, 1); self.assertFalse(result['retainRecommended'])
        record_path.write_bytes(original)

    def test_real_git_source_closure_rejects_other_changes_and_spoofed_event(self):
        def git(*words): return subprocess.check_output(['git', *words], cwd=self.root, stderr=subprocess.PIPE).decode().strip()
        git('init', '-q'); git('config', 'user.name', 'synthetic'); git('config', 'user.email', 'synthetic@invalid')
        for name in ('app/untouched', comparison.SHELL):
            path = self.root / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_text('original')
        git('add', '.'); git('commit', '-qm', 'control'); base = git('rev-parse', 'HEAD')
        for name in (comparison.SHELL, *comparison.ADDITIONS):
            path = self.root / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_text('candidate')
        git('add', '.'); git('commit', '-qm', 'experiment'); candidate = git('rev-parse', 'HEAD')
        with patch.object(comparison, 'BASELINE', base), patch.object(comparison, 'identity', return_value={'eventSourceCommit': candidate}):
            self.assertEqual(comparison.validate_sources(self.root, candidate)['A']['sourceCommit'], base)
            with self.assertRaisesRegex(ValueError, 'actual event'): comparison.validate_sources(self.root, base)
        (self.root / 'app/untouched').write_text('modified'); git('add', '.'); git('commit', '-qm', 'illegal change')
        candidate = git('rev-parse', 'HEAD')
        with patch.object(comparison, 'BASELINE', base), patch.object(comparison, 'identity', return_value={'eventSourceCommit': candidate}):
            with self.assertRaises(ValueError): comparison.validate_sources(self.root, candidate)

    def test_workflow_scope_and_original_source_builds(self):
        raw = (ROOT / comparison.ADDITIONS[0]).read_text()
        self.assertIn("branches: ['debug/gecko-owned-priority-*']", raw)
        self.assertIn('order: [AB, BA]', raw); self.assertIn('fail-fast: false', raw)
        self.assertIn('contents: read', raw); self.assertNotIn('contents: write', raw)
        self.assertNotIn('GITHUB_SHA=', raw); self.assertNotIn('publish_ci', raw)
        self.assertIn('for role in A B', raw)
        for command in ('caret_workflow.py prepare', 'caret_workflow.py record', 'build_native_input_driver.py',
                        'prepare_native_adb.py', 'prepare_android_image.py', 'prepare_platform_tools.py'):
            self.assertIn(command, raw)
        self.assertEqual(raw.count('run_input_priority_comparison.py run '), 1)
        self.assertIn('if: always()', raw)
        self.assertNotIn('run_caret_editing_phase.py', raw)
        self.assertNotIn('rerun', raw)


if __name__ == '__main__':
    unittest.main()
