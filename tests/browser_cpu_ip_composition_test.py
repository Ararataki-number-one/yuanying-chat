"""Additional IP composition controls for the retained CPU publication oracle.

CPU packets and prior-gate metadata remain synthetic. No fixture result here is
eligible as Android/IP evidence; the real missing-IP checker is also exercised.
"""
import importlib
import ast
import hashlib
import json
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import browser_cpu_publish_gate_test as original


class CpuIpPublicationComposition(unittest.TestCase):
    def test_all_original_cpu_publication_test_bodies_remain_identical(self):
        # Independently verified real public 0111cec70b5df1b957cfaaef684f5141be8234b4,
        # tree6058deb8280eb72d96d6a656b561931d733feffc; original complete file
        # blob45996b680539728cf14076418db9bddcccbd7fd8 / SHA256c0343a899fd8049728bbeeb43603da7b652c502f169802885aa9ca66caf42a79.
        # Raw source segments avoid Python-version-dependent AST serialization.
        source=(original.ROOT/'tests/browser_cpu_publish_gate_test.py').read_text()
        def bodies(raw):return {node.name:ast.get_source_segment(raw,node) for node in ast.walk(ast.parse(raw)) if isinstance(node,ast.FunctionDef) and node.name.startswith('test_')}
        def digest(raw):return hashlib.sha256(json.dumps(bodies(raw),sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        expected='8304bd6a9a4acf95aeb64a2f5caa1a97491dfed46b76b02c4e1816414a75e8cb'
        self.assertEqual(digest(source),expected);self.assertEqual(len(bodies(source)),9)
        self.assertNotEqual(digest(source.replace("self.assertEqual(len(dependencies),1,", "self.assertEqual(len(dependencies),2,",1)),expected)

    def test_current_combined_cpu_and_ip_paths_keep_the_old_three_gate_observations(self):
        factory=original.CpuPublicationTests();factory.setUp()
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);factory.fixture(root)
            with factory.prior_evidence_boundaries() as old:
                value=factory.gate.verify_browser_evidence(root,original.SOURCE,reader=factory.reader)
                self.assertIn('geckoCpuRegression',value);self.assertIn('geckoIpTimeZoneRegression',value)
                self.assertEqual(len(old),3);self.assertEqual(len(factory.ip_calls),1)
                self.assertIn('geckoCpuIpComboRegression',value);self.assertEqual(len(factory.combo_calls),1)
                actual=factory.ip_calls[0];self.assertEqual(actual[0:2],(root,original.SOURCE));self.assertIs(actual[3].__self__,factory)
                self.assertFalse(value['geckoIpTimeZoneRegression'].get('actualAndroidExecution',False))

    def test_ip_failure_or_missing_entrypoint_cannot_be_swallowed_by_complete_cpu_evidence(self):
        factory=original.CpuPublicationTests();factory.setUp()
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);factory.fixture(root)
            with factory.prior_evidence_boundaries():
                module=sys.modules['browser.check_gecko_ip_timezone_evidence']
                with patch.object(module,'verify_gecko_ip_timezone_evidence',side_effect=ValueError('exact IP rejection')):
                    with self.assertRaisesRegex(ValueError,'exact IP rejection'):factory.gate.verify_browser_evidence(root,original.SOURCE,reader=factory.reader)
                function=module.verify_gecko_ip_timezone_evidence;del module.verify_gecko_ip_timezone_evidence
                try:
                    with self.assertRaises(ImportError):factory.gate.verify_browser_evidence(root,original.SOURCE,reader=factory.reader)
                finally:module.verify_gecko_ip_timezone_evidence=function

    def test_actual_combined_gate_propagates_combo_failure_and_does_not_require_it_for_212(self):
        factory=original.CpuPublicationTests();factory.setUp()
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);_,expected=factory.fixture(root)
            with factory.prior_evidence_boundaries():
                module=sys.modules['browser.check_gecko_cpu_ip_combo_evidence']
                with patch.object(module,'verify_gecko_cpu_ip_combo_evidence',side_effect=ValueError('exact combination rejection')):
                    with self.assertRaisesRegex(ValueError,'exact combination rejection'):
                        factory.gate.verify_browser_evidence(root,original.SOURCE,reader=factory.reader)
                expected['version']='2.1.2';factory.device(root,expected)
                with patch.object(module,'verify_gecko_cpu_ip_combo_evidence',side_effect=AssertionError('Not a 212 requirement')) as invoked:
                    value=factory.gate.verify_browser_evidence(root,original.SOURCE,reader=factory.reader)
                    self.assertNotIn('geckoCpuIpComboRegression',value);invoked.assert_not_called()

    def test_ip_boundary_rejects_changed_source_and_real_missing_report_is_fail_closed(self):
        factory=original.CpuPublicationTests();factory.setUp()
        actual=importlib.import_module('browser.check_gecko_ip_timezone_evidence')
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);_,expected=factory.fixture(root)
            with factory.prior_evidence_boundaries():
                module=sys.modules['browser.check_gecko_ip_timezone_evidence']
                with self.assertRaises(AssertionError):module.verify_gecko_ip_timezone_evidence(root,'0'*40,expected,factory.reader)
                with patch.dict(sys.modules,{'browser.check_gecko_ip_timezone_evidence':actual}):
                    with self.assertRaisesRegex(ValueError,'IP timezone evidence: exact real raw directory required'):
                        factory.gate.verify_browser_evidence(root,original.SOURCE,reader=factory.reader)


if __name__=='__main__':unittest.main(verbosity=2)
