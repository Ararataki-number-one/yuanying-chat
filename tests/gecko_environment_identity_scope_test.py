"""Synthetic identity-schema controls; no device, APK or native execution claim."""
import ast
import copy
import inspect
import json
from pathlib import Path
import re
import tempfile
import unittest

import gecko_environment_policy_evidence_test as modeled

gate = modeled.gate
ROOT = Path(__file__).resolve().parents[1]


class InstalledIdentityScopeTests(unittest.TestCase):
    def identities(self):
        report = modeled.GeckoEnvironmentEvidenceTests().document()
        expected = report['expectedBuildIdentity']
        # Independent synthetic derived-SDK identity for schema comparison only.
        # Full-file tests below still execute the original official-SDK fixture
        # and the real selected-source verifier; this is not an APK receipt.
        for key in gate.SDK_FIELDS:
            expected.setdefault(key, 'f' * 64)
        expected['sdkBuildKind'] = 'source-derived-java'
        expected['sdkBuildIdentity']['sdkBuildKind'] = 'source-derived-java'
        return dict(copy.deepcopy(expected), scope=gate.INSTALLED_IDENTITY_SCOPE), expected

    def test_native_scope_is_the_exact_existing_producer_declaration(self):
        producer = (ROOT / 'tests/gecko/IntegrationBuildIdentity.java').read_text()
        declarations = re.findall(r'value\.put\("scope","([^"\n]+)"\)', producer)
        self.assertEqual(declarations, [gate.INSTALLED_IDENTITY_SCOPE])
        actual, expected = self.identities()
        self.assertEqual(len(expected), 22)
        self.assertEqual(set(actual), set(expected) | {'scope'})
        before = copy.deepcopy((actual, expected))
        gate.installed_identity(actual, expected)
        self.assertEqual((actual, expected), before)

    def test_all_security_fields_keep_exact_value_and_type_comparison(self):
        for key in sorted(gate.INSTALLED_IDENTITY_KEYS):
            for side in ('actual', 'expected'):
                actual, expected = self.identities()
                selected = actual if side == 'actual' else expected
                original = selected[key]
                selected[key] = dict(original, unexpected=True) if type(original) is dict else ('wrong-' + original if type(original) is str else original + 1 if type(original) is int else not original)
                with self.subTest(key=key, side=side), self.assertRaises(ValueError):
                    gate.installed_identity(actual, expected)
                actual, expected = self.identities()
                (actual if side == 'actual' else expected)[key] = str(original) if type(original) is not str else [original]
                with self.subTest(key=key, side=side, changed_type=True), self.assertRaises(ValueError):
                    gate.installed_identity(actual, expected)

    def test_missing_unknown_and_wrong_scope_are_rejected_on_exact_sides(self):
        actual, expected = self.identities()
        cases = []
        for key in actual:
            value = copy.deepcopy(actual); value.pop(key)
            cases.append((value, expected))
        for key in expected:
            value = copy.deepcopy(expected); value.pop(key)
            cases.append((actual, value))
        for bad in ('', gate.INSTALLED_IDENTITY_SCOPE + ' ', 'Complete fingerprint protection', True, None, []):
            cases.append((dict(actual, scope=bad), expected))
        cases.extend([(dict(actual, unknown=True), expected), (actual, dict(expected, unknown=True)), (actual, dict(expected, scope=gate.INSTALLED_IDENTITY_SCOPE)), (None, expected), (actual, None)])
        for index, (observed, reference) in enumerate(cases):
            with self.subTest(index=index), self.assertRaises(ValueError):
                gate.installed_identity(observed, reference)

    def test_complete_original_checks_still_run_and_independent_reference_rejects_matching_forgery(self):
        report = modeled.GeckoEnvironmentEvidenceTests().document()
        result = modeled.GeckoEnvironmentEvidenceTests().validate(report)
        self.assertEqual({row['id'] for row in result['checks']}, gate.REQUIRED)
        with tempfile.TemporaryDirectory() as folder:
            reference = copy.deepcopy(report['expectedBuildIdentity'])
            for key, bad in (('apkSha256', 'f' * 64), ('versionCode', 999), ('sdkBuildIdentity', dict(reference['sdkBuildIdentity'], runAttempt=2))):
                value = copy.deepcopy(report)
                value['expectedBuildIdentity'][key] = copy.deepcopy(bad)
                value['activity']['buildIdentity'][key] = copy.deepcopy(bad)
                # Matching local dictionaries do not replace the independent
                # APK/source/SDK reference used by the full file verifier.
                gate.installed_identity(value['activity']['buildIdentity'], value['expectedBuildIdentity'])
                Path(folder, gate.REPORT_NAME).write_text(json.dumps(value))
                with self.subTest(key=key), self.assertRaises(ValueError):
                    gate.verify_gecko_environment_policy_evidence(folder, modeled.SOURCE, reference, lambda source, path: modeled.SOURCE_BYTES)

    def test_failed_original_reports_cannot_be_promoted_by_identity_alignment(self):
        report = modeled.GeckoEnvironmentEvidenceTests().document()
        report['status'] = 'failed'
        with self.assertRaisesRegex(ValueError, 'successful exact-source'):
            modeled.GeckoEnvironmentEvidenceTests().validate(report)

    def test_each_compiled_production_guard_is_necessary(self):
        body = inspect.getsource(gate.installed_identity)
        controls = (
            ('exact expected installed identity fields required', lambda a, e: e.update(unknown=True)),
            ('exact native installed identity fields required', lambda a, e: a.update(unknown=True)),
            ('native installed identity scope differs', lambda a, e: a.update(scope='Complete fingerprint protection')),
            ('wrapper and installed build identity fields differ', lambda a, e: a['sdkBuildIdentity'].update(runAttempt=999)),
        )
        for message, change in controls:
            actual, expected = self.identities(); change(actual, expected)
            with self.subTest(message=message), self.assertRaises(ValueError):
                gate.installed_identity(actual, expected)
            tree = ast.parse(body)
            selected = [node for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'require' and len(node.args) == 2 and isinstance(node.args[1], ast.Constant) and node.args[1].value == message]
            self.assertIn(len(selected), (1, 2))
            for node in selected:
                node.args[0] = ast.Constant(True)
            namespace = dict(vars(gate)); exec(compile(ast.fix_missing_locations(tree), '<actual-identity-guard-mutant>', 'exec'), namespace)
            # Removing any one real guard accepts its corresponding counterfeit.
            # All four mutants compile and execute; none is a source-text check.
            namespace['installed_identity'](actual, expected)


if __name__ == '__main__':
    unittest.main(verbosity=2)
