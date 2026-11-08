"""Strict diagnostic comparison inputs; actual workflow dictionaries stay raw."""
import copy
from pathlib import Path
import unittest
from unittest.mock import patch

import yaml
import browser_acceptance_workflow_test as browser
import gecko_cpu_acceptance_test as cpu
import native_timezone_probe_test as timezone
import gradle_transport_source_compatibility as transport

ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / '.github/workflows/browser-2_1-acceptance.yml'
CASES = (
    (cpu, cpu.ProductionCpuControls,
     'test_workflow_exact_source_same_run_restore_fixed_four_cpu_and_readonly_permissions',
     ROOT / '.github/workflows/gecko-cpu-acceptance.yml'),
    (timezone, timezone.ProbeControls,
     'test_workflow_uses_actual_full_sdk_and_original_capacity_fences',
     ROOT / '.github/workflows/native-timezone-probe.yml'),
)


class GradleDiagnosticWorkflowInputTests(unittest.TestCase):
    def invoke(self, selected, diagnostic, canonical):
        module, case_type, method, path = selected
        case = case_type(method)
        with patch.object(module.yaml, 'safe_load', side_effect=[diagnostic, canonical]):
            getattr(case, method)()

    def test_original_full_cases_keep_actual_yaml_and_both_parsed_dictionaries_unchanged(self):
        raw = CANONICAL.read_bytes()
        for selected in CASES:
            diagnostic_raw = selected[3].read_bytes()
            diagnostic, canonical = yaml.safe_load(diagnostic_raw), yaml.safe_load(raw)
            before_diagnostic, before_canonical = copy.deepcopy(diagnostic), copy.deepcopy(canonical)
            self.invoke(selected, diagnostic, canonical)
            self.assertEqual(diagnostic, before_diagnostic)
            self.assertEqual(canonical, before_canonical)
            self.assertEqual(selected[3].read_bytes(), diagnostic_raw)
            self.assertEqual(CANONICAL.read_bytes(), raw)
            step = next(step for step in canonical['jobs']['build']['steps'] if step.get('name') == 'Prepare locked toolchain')
            self.assertIn('/releases/assets/586068844', step['run'])
            historical = transport.historical_toolchain_step(step)
            self.assertIsNot(historical, step)
            self.assertNotIn('/releases/assets/586068844', historical['run'])
            self.assertEqual(canonical, before_canonical)

    def test_current_transport_other_step_fields_and_source_environment_mutations_are_rejected(self):
        canonical = yaml.safe_load(CANONICAL.read_bytes())
        checksum = 'bafd5ce9cfaea0fbccfdc8439a1ac42fbd4cd9c89dc9a988228d8a2639a58e6c'
        for selected in CASES:
            diagnostic = yaml.safe_load(selected[3].read_bytes())
            for before, after in (('/releases/assets/586068844', '/releases/assets/586068845'),
                                  ('151611662', '151611663'), (checksum, '0' * 64),
                                  ('unzip -q ', 'unzip -v ')):
                changed = copy.deepcopy(canonical)
                step = next(step for step in changed['jobs']['build']['steps'] if step.get('name') == 'Prepare locked toolchain')
                self.assertEqual(step['run'].count(before), 1)
                step['run'] = step['run'].replace(before, after, 1)
                self.assertIs(transport.historical_toolchain_step(step), step)
                with self.subTest(case=selected[2], before=before), self.assertRaises(AssertionError):
                    self.invoke(selected, copy.deepcopy(diagnostic), changed)
            for change in ('extra-step-field', 'other-step', 'source-environment'):
                changed = copy.deepcopy(canonical)
                if change == 'extra-step-field':
                    next(step for step in changed['jobs']['build']['steps'] if step.get('name') == 'Prepare locked toolchain')['continue-on-error'] = True
                elif change == 'other-step':
                    changed['jobs']['build']['steps'][0]['uses'] += '-unreviewed'
                else:
                    changed['env']['GIT_NO_LAZY_FETCH'] = '0'
                with self.subTest(case=selected[2], change=change), self.assertRaises(AssertionError):
                    self.invoke(selected, copy.deepcopy(diagnostic), changed)

    def test_original_canonical_budget_guards_remain_strict_with_the_transport_view(self):
        case_type = browser.BrowserWorkflowTests
        case_type.setUpClass()
        original = copy.deepcopy(case_type.new)
        self.assertEqual(original, yaml.safe_load(CANONICAL.read_bytes()))
        case = case_type('test_original_checks_retained_in_order')
        case.test_original_checks_retained_in_order()
        for budget in (61, 0, True):
            changed = copy.deepcopy(original)
            changed['jobs']['build']['timeout-minutes'] = budget
            with self.subTest(budget=budget), patch.object(case_type, 'new', changed), self.assertRaises(AssertionError):
                case.test_original_checks_retained_in_order()
        self.assertEqual(case_type.new, original)
        self.assertEqual(case_type.new, yaml.safe_load(CANONICAL.read_bytes()))


if __name__ == '__main__':
    unittest.main(verbosity=2)
