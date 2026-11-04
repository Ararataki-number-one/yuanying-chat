"""Historical source-input controls, discovered by the existing profile suite."""
import ast
import hashlib
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import network_settings_callback_source_compatibility as compat

ROOT = Path(__file__).resolve().parents[1]


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def historical(path):
    return subprocess.check_output(
        ['git', '--no-replace-objects', 'show', compat.BASE_COMMIT + ':' + path], cwd=ROOT)


def assertions(raw):
    return [ast.dump(node, include_attributes=False) for node in ast.walk(ast.parse(raw))
            if isinstance(node, ast.Assert)]


def gate_methods(raw):
    text = raw.decode('utf-8')
    case = next(node for node in ast.parse(text).body
                if isinstance(node, ast.ClassDef) and node.name == 'GateTest')
    return {node.name: ast.get_source_segment(text, node) for node in case.body
            if isinstance(node, ast.FunctionDef)}


class CallbackSourceCompatibilityTests(unittest.TestCase):
    rejected_counterfeits = 0

    def rejected(self, raw, path):
        with self.assertRaises(ValueError):
            compat.source_input(raw, path)
        type(self).rejected_counterfeits += 1

    def test_exact_real_e21_identity_whole_files_and_forward_hunks(self):
        tree = subprocess.check_output(
            ['git', '--no-replace-objects', 'rev-parse', compat.BASE_COMMIT + '^{tree}'], cwd=ROOT)
        self.assertEqual(tree.decode().strip(), compat.BASE_TREE)
        for path, row in compat.manifest()['files'].items():
            with self.subTest(path=path):
                previous, current = historical(path), (ROOT / path).read_bytes()
                self.assertEqual(digest(previous), compat.BASE_SOURCES[path])
                self.assertEqual(digest(previous), row['previousSha256'])
                self.assertEqual(digest(current), row['reviewedSha256'])
                self.assertEqual(compat.source_input(current, path), previous)
                forward = previous
                for delta in row['deltas']:
                    before, after = delta['previous'].encode(), delta['current'].encode()
                    self.assertTrue(before and after)
                    self.assertEqual(forward.count(before), 1)
                    forward = forward.replace(before, after, 1)
                self.assertEqual(forward, current)

    def test_missing_duplicate_changed_moved_and_unknown_sources_fail_closed(self):
        for path, row in compat.manifest()['files'].items():
            current = (ROOT / path).read_bytes()
            for delta in row['deltas']:
                addition = delta['current'].encode()
                remaining = current.replace(addition, b'', 1)
                moved = remaining + addition
                if moved == current:
                    moved = addition + remaining
                self.assertNotEqual(moved, current)
                for invalid in (remaining, current.replace(addition, addition * 2, 1),
                                current.replace(addition, addition + b' ', 1), moved):
                    with self.subTest(path=path, mutation=digest(invalid)):
                        self.rejected(invalid, path)
            for invalid in (current + b' ', b'unknown source', b'', historical(path)):
                self.rejected(invalid, path)

    def test_original_owner_nonce_source_timeout_and_gate_predicate_drift_rejected(self):
        path = 'tests/gecko/run_network_settings_internal.py'
        current = (ROOT / path).read_bytes()
        for before, after in ((b"wire['authenticated'] is True", b"wire['authenticated'] is False"),
                              (b"deadline, report = time.monotonic() + 540, None", b"deadline, report = time.monotonic() + 541, None"),
                              (b"actual[field] == wanted[field]", b"actual[field] != wanted[field]"),
                              (b"request['nonce'] == request['echoedNonce']", b"request['nonce'] != request['echoedNonce']"),
                              (b"report['sourceCommit'] == report['buildIdentity']['sourceCommit'] == source", b'True')):
            self.assertEqual(current.count(before), 1)
            self.rejected(current.replace(before, after, 1), path)
        for path, predicate in (
                ('tests/gecko/NetworkSettingsInternalApplication.java',
                 b'originalAttemptCurrent&&pendingUnchangedAtPoll&&connectionAtInjection==attempt.connection'),
                ('tests/gecko_settings_internal_gate_test.py',
                 b'with self.assertRaises((AssertionError, KeyError, ValueError, TypeError)):')):
            current = (ROOT / path).read_bytes()
            self.assertEqual(current.count(predicate), 1)
            self.rejected(current.replace(predicate, predicate + b' ', 1), path)

    def test_wrong_input_types_paths_and_oversized_sources_rejected(self):
        path = 'tests/gecko/run_network_settings_internal.py'
        current = (ROOT / path).read_bytes()
        for raw in (None, current.decode(), bytearray(current), memoryview(current), 1, True):
            self.rejected(raw, path)
        for wrong in (None, Path(path), path.encode(), '', '../' + path,
                      path + ' ', 'tests/gecko/NetworkSafeIdleIntegrationActivity.java'):
            self.rejected(current, wrong)
        self.rejected(b'x' * (compat.MAX_SOURCE_BYTES + 1), path)

    def test_altered_missing_or_oversized_sidecar_is_never_trusted(self):
        path = 'tests/gecko/run_network_settings_internal.py'
        current = (ROOT / path).read_bytes()
        fixture = compat.DELTA_PATH.read_bytes()
        with tempfile.TemporaryDirectory(prefix='callback-source-fixture-') as directory:
            changed = Path(directory) / 'changed.json'
            for raw in (fixture + b' ', b'', b'{}', b'x' * (compat.MAX_DELTA_BYTES + 1)):
                changed.write_bytes(raw)
                with patch.object(compat, 'DELTA_PATH', changed):
                    self.rejected(current, path)

    def test_old_contract_pins_assertions_and_all_nineteen_gate_methods_remain(self):
        path = 'tests/network_settings_internal46_contract.py'
        self.assertEqual((ROOT / path).read_bytes(), historical(path))
        path = 'tests/gecko_settings_internal_gate_test.py'
        previous, current = historical(path), (ROOT / path).read_bytes()
        self.assertEqual(gate_methods(current), gate_methods(previous))
        self.assertEqual(len([name for name in gate_methods(current) if name.startswith('test_')]), 19)
        for path in ('tests/gecko/run_network_settings_internal.py',
                     'tests/profile_network_settings_internal46_contract_test.py',
                     'tests/profile_diagnostic_producer_capture_privacy_test.py'):
            self.assertEqual(assertions((ROOT / path).read_bytes()), assertions(historical(path)), path)
        path = 'tests/profile_diagnostic_producer_capture_privacy_test.py'
        def pins(raw):
            return {node.targets[0].id: ast.dump(node.value, include_attributes=False)
                    for node in ast.parse(raw).body if isinstance(node, ast.Assign)
                    and isinstance(node.targets[0], ast.Name)
                    and node.targets[0].id in {'PREVIOUS_RUNNER_SHA256', 'CHANGES', 'PRODUCER_PINS', 'PRODUCER_HUNKS'}}
        self.assertEqual(pins((ROOT / path).read_bytes()), pins(historical(path)))

    def test_internal46_consumer_changes_only_its_explicit_source_inputs(self):
        path = 'tests/profile_network_settings_internal46_contract_test.py'
        current = (ROOT / path).read_bytes()
        hook = b'from network_settings_callback_source_compatibility import source_input as network_source_input\n'
        self.assertEqual(current.count(hook), 1)
        restored = current.replace(hook, b'', 1)
        text_read = b'network_source_input((ROOT / path).read_bytes(), path).decode()'
        self.assertEqual(restored.count(text_read), 1)
        restored = restored.replace(text_read, b'(ROOT / path).read_text()', 1)
        source_read = b'network_source_input((ROOT / path).read_bytes(), path)'
        self.assertEqual(restored.count(source_read), 5)
        restored = restored.replace(source_read, b'(ROOT / path).read_bytes()')
        self.assertEqual(restored, historical(path))

    def test_runtime_keeps_current_verifier_and_evidence_instead_of_inverted_code(self):
        path = 'tests/gecko/run_network_settings_internal.py'
        current = (ROOT / path).read_bytes()
        original = compat.source_input(current, path)
        self.assertEqual(current.count(b'    verify_callback_cohort(report)\n'), 1)
        self.assertNotIn(b'verify_callback_cohort', original)
        guard = b"require_runner_source(source_input(pathlib.Path(__file__).read_bytes(), 'tests/gecko/run_network_settings_internal.py'))"
        self.assertEqual(current.count(guard), 1)
        self.assertIn(b"runnerSha256=hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest()", current)
        self.assertNotIn(b'network_source_input', current)
        path = 'tests/gecko/NetworkSettingsInternalApplication.java'
        current = (ROOT / path).read_bytes()
        self.assertIn(b'JSONObject callbackEvidence=a.ui(', current)
        self.assertIn(b'"applicationCallbackEvents",callbackEvidence.getJSONArray("applicationCallbackEvents")', current)
        self.assertNotIn(b'callbackEvidence', compat.source_input(current, path))


if __name__ == '__main__':
    unittest.main(verbosity=2)
