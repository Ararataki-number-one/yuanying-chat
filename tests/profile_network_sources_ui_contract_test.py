"""Exercise the actual runner contract without starting Android or parsing CLI flags."""
import ast
import copy
import hashlib
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / 'tests/gecko/run_network_sources_ui.py'


def contract():
    source = ast.parse(RUNNER.read_text())
    names = {'LEGACY_ANDROID_CHECKS', 'SAVED_ONLY_ROUTE_CHECK', 'EXPECTED_ANDROID_CHECKS'}
    members = [node for node in source.body
               if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id in names for target in node.targets)
               or isinstance(node, ast.FunctionDef) and node.name == 'verify_android_checks']
    namespace = {}
    exec(compile(ast.Module(body=members, type_ignores=[]), str(RUNNER), 'exec'), namespace)
    return namespace


class NetworkSourcesUiContractTest(unittest.TestCase):
    def setUp(self):
        self.contract = contract()
        self.names = self.contract['EXPECTED_ANDROID_CHECKS']
        self.verify = self.contract['verify_android_checks']
        self.report = dict(status='passed', checkCount=86,
                           checks=[dict(name=name, **{'pass': True}) for name in self.names])

    def test_original_85_names_and_order_are_preserved(self):
        legacy = self.contract['LEGACY_ANDROID_CHECKS']
        self.assertEqual(len(legacy), 85)
        self.assertEqual(hashlib.sha256('\n'.join(legacy).encode()).hexdigest(),
                         '1fbb5b492da30920acc0aa499e2a1095f49e6925c1b3964172ff40b1ae3d2465')
        self.assertEqual(self.names[:7] + self.names[8:], legacy)
        self.assertEqual(self.names[7], 'Saved source settings alone do not create a running route summary')
        self.assertEqual(len(set(self.names)), 86)

    def test_complete_contract_passes(self):
        self.verify(self.report)

    def test_missing_original_or_new_check_fails(self):
        for index in range(86):
            with self.subTest(index=index), self.assertRaises(AssertionError):
                value = copy.deepcopy(self.report)
                value['checks'].pop(index)
                value['checkCount'] -= 1
                self.verify(value)

    def test_same_count_duplicate_replacement_fails(self):
        value = copy.deepcopy(self.report)
        value['checks'][7] = value['checks'][6]
        with self.assertRaises(AssertionError):
            self.verify(value)

    def test_reordered_original_checks_fail(self):
        value = copy.deepcopy(self.report)
        value['checks'][8], value['checks'][9] = value['checks'][9], value['checks'][8]
        with self.assertRaises(AssertionError):
            self.verify(value)

    def test_unexpected_extra_check_fails(self):
        self.report['checks'].append(dict(name='not part of this workload', **{'pass': True}))
        self.report['checkCount'] += 1
        with self.assertRaises(AssertionError):
            self.verify(self.report)

    def test_failed_or_non_boolean_results_fail(self):
        for index in (0, 7, 85):
            for passed in (False, 1, 'true', None):
                with self.subTest(index=index, passed=passed), self.assertRaises(AssertionError):
                    value = copy.deepcopy(self.report)
                    value['checks'][index]['pass'] = passed
                    self.verify(value)

    def test_missing_pass_field_fails(self):
        del self.report['checks'][7]['pass']
        with self.assertRaises(AssertionError):
            self.verify(self.report)

    def test_count_requires_exact_integer(self):
        for count in (85, 87, True, 86.0, '86', None):
            with self.subTest(count=count), self.assertRaises(AssertionError):
                self.verify(dict(self.report, checkCount=count))

    def test_missing_or_malformed_rows_fail(self):
        for rows in (None, {}, tuple(self.report['checks']), [None] * 86):
            with self.subTest(rows=type(rows)), self.assertRaises(AssertionError):
                self.verify(dict(self.report, checks=rows))

    def test_failed_android_status_cannot_pass(self):
        for status in ('failed', 'in_progress', 'no-result', None):
            with self.subTest(status=status), self.assertRaises(AssertionError):
                self.verify(dict(self.report, status=status))


if __name__ == '__main__':
    unittest.main()
