"""Guards for explicit synthetic faults and evidence-only path classification."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/gecko'))
SPEC = importlib.util.spec_from_file_location('cellular_diagnostic', ROOT / 'tools/gecko/diagnose_native_cellular.py')
DIAG = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DIAG)


def result(stdout='', code=0):
    return {'exitCode': code, 'stdout': stdout, 'stderr': '', 'timedOut': False}


def receipt(initial=True, missing=True, recovery=True):
    return {'status': 'failed', 'postSetupNetworkRecoveryRequired': recovery,
            'networkObservations': [
                {'phase': 'before-network-configuration', 'raw': json.dumps({
                    'usable': initial, 'transports': ['wifi'] if initial else []})},
                {'phase': 'after-setup-package-handling', 'raw': json.dumps({
                    'usable': not missing, 'transports': [] if missing else ['cellular'],
                    'activeNetwork': '' if missing else '101',
                    'activeNetworkAfter': '' if missing else '101'})}]}


class CellularDiagnosticTest(unittest.TestCase):
    def test_export_keeps_auth_header_but_discards_auth_payload_prefix(self):
        with tempfile.TemporaryDirectory() as folder:
            source, target = Path(folder) / 'raw.log', Path(folder) / 'export.log'
            source.write_text('from remote: [AUTH] arg0=0x1 arg1=0x0 (len=20) secret-auth-prefix\nregistered\n')
            DIAG.export_transport_trace(source, target)
            self.assertEqual(target.read_text(), 'from remote: [AUTH] arg0=0x1 arg1=0x0 (len=20) [payload omitted]\nregistered\n')

    def test_fault_uses_one_explicit_command_only_after_confirmed_qemu(self):
        record = {}
        with patch.object(DIAG, 'scenario_command', side_effect=[result('1\n'), result()]) as command, \
                patch.object(DIAG, 'scenario_snapshot', return_value={'observations': []}) as snapshot:
            DIAG.apply_scenario('adb', 'fault-1', record)
        self.assertEqual(command.call_args_list[0].args, ('adb', ['shell', 'getprop', 'ro.kernel.qemu']))
        self.assertEqual(command.call_args_list[1].args, ('adb', ['shell', 'svc', 'data', 'disable']))
        self.assertEqual(command.call_count, 2)
        self.assertEqual(snapshot.call_count, 2)
        self.assertTrue(record['preconditionMutationAttempted'])
        self.assertEqual(record['preconditionMutation']['exitCode'], 0)

    def test_control_does_not_change_or_enable_mobile_data(self):
        record = {}
        with patch.object(DIAG, 'scenario_command', return_value=result('1')) as command, \
                patch.object(DIAG, 'scenario_snapshot', return_value={}):
            DIAG.apply_scenario('adb', 'control-1', record)
        self.assertEqual(command.call_count, 1)
        self.assertNotIn('preconditionMutation', record)
        self.assertFalse(record['preconditionMutationAttempted'])
        self.assertFalse(record['externalStateChangeVerified'])

    def test_non_emulator_is_never_mutated(self):
        with patch.object(DIAG, 'scenario_command', return_value=result('0')) as command, \
                patch.object(DIAG, 'scenario_snapshot') as snapshot:
            with self.assertRaises(ValueError):
                DIAG.apply_scenario('adb', 'fault-2', {})
        self.assertEqual(command.call_count, 1)
        snapshot.assert_not_called()

    def test_rejected_mutation_is_preserved_without_retry(self):
        record = {}
        with patch.object(DIAG, 'scenario_command', side_effect=[result('1'), result('denied', 1)]) as command, \
                patch.object(DIAG, 'scenario_snapshot', return_value={}):
            with self.assertRaises(ValueError):
                DIAG.apply_scenario('adb', 'fault-1', record)
        self.assertEqual(command.call_count, 2)
        self.assertEqual(record['preconditionMutation']['exitCode'], 1)
        self.assertFalse(record['preconditionCommandSucceeded'])

    def test_timeout_keeps_exact_command_and_does_not_retry(self):
        failure = subprocess.TimeoutExpired(['adb'], 4, output='partial', stderr='timeout')
        with patch.object(DIAG.subprocess, 'run', side_effect=failure) as run:
            row = DIAG.scenario_command('/pinned/adb', ['shell', 'svc', 'data', 'disable'])
        run.assert_called_once_with(['/pinned/adb', '-s', 'emulator-5556', 'shell', 'svc', 'data', 'disable'],
                                    capture_output=True, text=True, timeout=4)
        self.assertTrue(row['timedOut'])
        self.assertIsNone(row['exitCode'])
        self.assertEqual(row['stdout'], 'partial')

    def test_coverage_requires_all_three_observed_conditions(self):
        self.assertTrue(DIAG.target_coverage(receipt())['targetPathCovered'])
        for args in ((False, True, True), (True, False, True), (True, True, False)):
            self.assertFalse(DIAG.target_coverage(receipt(*args))['targetPathCovered'])
        self.assertFalse(DIAG.target_coverage({})['targetPathCovered'])

    def test_coverage_never_promotes_failure_or_claims_equivalence(self):
        original = receipt()
        frozen = json.dumps(original, sort_keys=True)
        coverage = DIAG.target_coverage(original)
        self.assertEqual(json.dumps(original, sort_keys=True), frozen)
        self.assertEqual(original['status'], 'failed')
        self.assertFalse(coverage['equivalentToOriginalFailure'])
        self.assertNotIn('applicationAcceptance', coverage)

    def test_snapshot_is_read_only_and_records_eth0_wlan0_routes(self):
        with patch.object(DIAG, 'scenario_command', return_value={}) as command:
            DIAG.scenario_snapshot('adb')
        parts = [call.args[1] for call in command.call_args_list]
        self.assertEqual(len(parts), 6)
        self.assertIn(['shell', 'ip', '-4', '-o', 'addr', 'show'], parts)
        self.assertIn(['shell', 'ip', '-4', 'route', 'show', 'table', 'all'], parts)
        self.assertTrue(all('disable' not in part and 'enable' not in part for part in parts))


if __name__ == '__main__':
    unittest.main()
