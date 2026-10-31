"""Strict46 stopped-core failure contract; all report samples here are synthetic.

Native Android reports remain untouched and require their complete fresh runner.
"""
import ast
import copy
import hashlib
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
import network_settings_internal46_contract as contract


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


fixture = load('internal46_synthetic_fixtures', ROOT / 'tests/gecko_settings_internal_gate_test.py')
runner = fixture.m


def mutate_stopped(report, key, value, remove=False):
    case = report['cases'][1]
    candidate = case['expected']['candidateId']
    rows = [case['result']['operationResult']]
    rows += [row['operationResult'] for row in report['applicationResults']
             if row['operationResult']['candidateId'] == candidate]
    for row in rows:
        if remove:
            row.pop(key, None)
        else:
            row[key] = value


class Internal46ContractTests(unittest.TestCase):
    def verify(self, report):
        runner.verify(report, fixture.SOURCE, fixture.NONCE, fixture.APK)

    def rejected(self, report):
        with self.assertRaises((AssertionError, KeyError, TypeError, ValueError)):
            self.verify(report)

    def test_entire_reviewed_files_invert_to_exact_original_whole_sources(self):
        for path, (previous, reviewed, _) in contract.REVIEWED.items():
            raw = (ROOT / path).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), reviewed)
            self.assertEqual(hashlib.sha256(contract.previous_source_bytes(raw, path)).hexdigest(), previous)
        self.assertEqual(contract.REVIEWED['tests/gecko/run_network_settings_internal.py'][0],
                         '07ff8880b514fa313c634ba21c4adc78938390758e84f7742de774fa722b24e6')
        self.assertEqual(contract.REVIEWED['tests/gecko/NetworkSettingsInternalApplication.java'][0],
                         'b36d166f7e22496fc9341c4fcaa5ec7dd240a314b48790d3db7ad9f0d3d6b136')

    def test_missing_duplicate_altered_relocated_and_unknown_source_deltas_rejected(self):
        for path, (_, _, deltas) in contract.REVIEWED.items():
            raw = (ROOT / path).read_bytes()
            for _, addition in deltas:
                for changed in [raw.replace(addition, b'', 1),
                                raw.replace(addition, addition + addition, 1),
                                raw.replace(addition, addition + b' ', 1),
                                raw.replace(addition, b'', 1) + addition]:
                    with self.assertRaises(ValueError):
                        contract.previous_source_bytes(changed, path)
            for changed in [raw + b' ', b'unknown', b'']:
                with self.assertRaises(ValueError):
                    contract.previous_source_bytes(changed, path)
        with self.assertRaises(ValueError):
            contract.previous_source_bytes(b'', 'unknown/path')

    def test_original_wire_owner_nonce_source_and_timeout_predicates_cannot_be_edited(self):
        path = 'tests/gecko/run_network_settings_internal.py'
        raw = (ROOT / path).read_bytes()
        for old, changed in [(b"wire['authenticated'] is True", b"wire['authenticated'] is False"),
                             (b"deadline, report = time.monotonic() + 540, None", b"deadline, report = time.monotonic() + 541, None"),
                             (b"actual[field] == wanted[field]", b"actual[field] != wanted[field]"),
                             (b"request['nonce'] == request['echoedNonce']", b"request['nonce'] != request['echoedNonce']"),
                             (b"report['sourceCommit'] == report['buildIdentity']['sourceCommit'] == source", b"True")]:
            self.assertEqual(raw.count(old), 1)
            with self.assertRaises(ValueError):
                contract.previous_source_bytes(raw.replace(old, changed, 1), path)

    def test_every_original_gate_test_method_is_byte_identical(self):
        path = 'tests/gecko_settings_internal_gate_test.py'
        current = (ROOT / path).read_text()
        prior = contract.previous_source_bytes(current.encode(), path).decode()
        def methods(text):
            tree = ast.parse(text)
            case = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'GateTest')
            return {node.name: ast.get_source_segment(text, node) for node in case.body
                    if isinstance(node, ast.FunctionDef)}
        self.assertEqual(methods(prior), methods(current))
        self.assertEqual(len([name for name in methods(current) if name.startswith('test_')]), 19)

    def test_complete_explicit_failed_core_control_is_accepted_without_rewriting_it(self):
        report = fixture.receipt()
        original = copy.deepcopy(report)
        self.verify(report)
        self.assertEqual(report, original)
        actual = report['cases'][1]['result']['operationResult']
        self.assertEqual((actual['applicationState'], actual['scope'], actual['appliedRevision']), ('failed', 'core', 0))
        self.assertEqual(actual['rollbackState'], 'unconfirmed')
        self.assertIs(actual['retryAvailable'], True)
        self.assertEqual(len(report['cases']), 3)

    def test_old_unknown_or_false_success_stopped_core_results_are_rejected(self):
        for key, value in [('applicationState', 'saved-unconfirmed'), ('applicationState', 'applied'),
                           ('scope', 'session'), ('scope', 'next-session'), ('appliedRevision', 1),
                           ('appliedRevision', False), ('appliedRevision', 0.0),
                           ('generation', True), ('savedRevision', 4.0), ('saveState', 'superseded'),
                           ('rollbackState', 'verified'), ('rollbackState', 'unchanged'),
                           ('rollbackState', ''), ('rollbackState', None),
                           ('retryAvailable', False), ('retryAvailable', 1),
                           ('retryAvailable', 'true'), ('retryAvailable', None)]:
            with self.subTest(key=key, value=value):
                report = fixture.receipt()
                mutate_stopped(report, key, value)
                self.rejected(report)
        for key in ['rollbackState', 'retryAvailable']:
            report = fixture.receipt()
            mutate_stopped(report, key, None, remove=True)
            self.rejected(report)

    def test_new_failed_semantics_cannot_spread_to_other_cases(self):
        for index in [0, 2]:
            report = fixture.receipt()
            report['cases'][index]['result']['operationResult'].update(
                applicationState='failed', scope='core', rollbackState='unconfirmed', retryAvailable=True,
                appliedRevision=0)
            self.rejected(report)
        report = fixture.receipt()
        row = report['cases'][2]
        row['result']['operationResult'].update(applicationState='failed', scope='core',
                                              rollbackState='unconfirmed', retryAvailable=True)
        with self.assertRaises(AssertionError):
            runner.verify_receipt(row, 'failed')

    def test_actual_stop_owner_zero_applied_and_strict_new_check_cannot_be_omitted(self):
        for field, value in [('stopConfirmed', False), ('realCoreStopped', False),
                             ('capturedReceiptMatchesAfter', True), ('originalAttemptCurrentAtPoll', False),
                             ('pendingUnchangedAtPoll', False)]:
            report = fixture.receipt()
            report['cases'][1][field] = value
            self.rejected(report)
        report = fixture.receipt()
        name = runner.CASE_NAMES[1] + ': stopped core keeps rollback unconfirmed and retry available'
        report['checks'] = [row for row in report['checks'] if row['name'] != name]
        report['checkCount'] = len(report['checks'])
        self.rejected(report)

    def test_failed_or_incomplete_native_status_is_never_promoted(self):
        report = fixture.receipt()
        report.update(status='failed', error='retained failed native invocation')
        original = copy.deepcopy(report)
        self.rejected(report)
        self.assertEqual(report, original)
        report = fixture.receipt()
        report['cases'] = report['cases'][:1]
        self.rejected(report)

    def test_actual_injection_capture_and_original_assertion_counts_are_preserved(self):
        path = 'tests/gecko/NetworkSettingsInternalApplication.java'
        current = (ROOT / path).read_bytes()
        prior = current
        for before, after in reversed(contract.REVIEWED[path][2][-3:]):
            self.assertEqual(prior.count(after), 1)
            prior = prior.replace(after, before, 1)
        self.assertEqual(hashlib.sha256(prior).hexdigest(),
                         'c0bf0a5fe3375435f79d99fed11e5f87a7dfa58bdadb7d5ca783c5815194f629')
        self.assertEqual(current.count(b'a.check('), prior.count(b'a.check('))
        capture = b'JSONObject injection=a.ui(()->J.obj("connection",a.session.connectionEpoch,"attemptCurrent",a.provider.applicationCurrent(attempt)));'
        self.assertEqual(current.count(capture), 1)
        self.assertEqual(current.count(b'"connectionAtInjection",connectionAtInjection'), 1)
        self.assertLess(current.index(capture), current.index(b'a.provider.pollApplication(attempt)'))
        self.assertIn(b'originalAttemptCurrent&&pendingUnchangedAtPoll&&connectionAtInjection==attempt.connection', current)
        path = 'tests/gecko/run_network_settings_internal.py'
        current = (ROOT / path).read_bytes()
        before, after = contract.REVIEWED[path][2][-1]
        prior = current.replace(after, before, 1)
        self.assertEqual(hashlib.sha256(prior).hexdigest(),
                         '4eb7010fad67836ee0673af7c6481a35c4dc539c3eb9c23dd17b05b2843116cf')
        self.assertEqual(sum(isinstance(n, ast.Assert) for n in ast.walk(ast.parse(current))),
                         sum(isinstance(n, ast.Assert) for n in ast.walk(ast.parse(prior))))
        # The original runner requires 31 distinct names; the actual native
        # cohort emits 44 checks including repeated bootstrap/receipt phases.
        self.assertEqual(len(runner.required_checks()), 31)

    def test_injection_and_post_result_leases_are_exact_typed_and_required(self):
        baseline = fixture.receipt()
        self.assertEqual([(row['connectionAtInjection'], row['frozenConnection'], row['observedConnection'])
                          for row in baseline['cases'][1:]], [(5, 5, 6), (6, 6, 6)])
        for index in (1, 2):
            for field in ('connectionAtInjection', 'observedConnection', 'frozenConnection'):
                expected = baseline['cases'][index][field]
                for value in (expected - 1, expected + 1, expected + 2, True,
                              float(expected), str(expected), None):
                    with self.subTest(case=index, field=field, value=value):
                        report = fixture.receipt()
                        report['cases'][index][field] = value
                        self.rejected(report)
                report = fixture.receipt()
                report['cases'][index].pop(field)
                self.rejected(report)
        # Old reports have no separate injection observation. Missing fields
        # stay rejected; they are never filled from a later connection value.
        report = fixture.receipt()
        for row in report['cases'][1:]:
            row.pop('connectionAtInjection')
        original = copy.deepcopy(report)
        self.rejected(report)
        self.assertEqual(report, original)


if __name__ == '__main__':
    unittest.main(verbosity=2)
