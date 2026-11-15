"""Real historical mappings retain strict checks on actual parsed workflow data."""
import ast
import copy
from pathlib import Path
import unittest
from unittest.mock import patch

import yaml

import browser_acceptance_workflow_test as acceptance
from historical_source_inputs import historical_bytes, historical_identity
import released_workflow_comparison as comparison


ROOT = Path(__file__).resolve().parents[1]


class ReleasedWorkflowComparisonTests(unittest.TestCase):
    def setUp(self):
        comparison._reviewed_comparisons.cache_clear()
        self.addCleanup(comparison._reviewed_comparisons.cache_clear)
        self.released = yaml.safe_load(historical_bytes(comparison.budget.PATH))
        self.current = yaml.safe_load((ROOT/comparison.budget.PATH).read_bytes())

    def selected(self, workflow, owner, name):
        steps = [step for step in workflow['jobs'][owner]['steps'] if step.get('name') == name]
        self.assertEqual(len(steps), 1)
        return steps[0]

    def run_current_guard(self, changed):
        acceptance.BrowserWorkflowTests.setUpClass()
        case = acceptance.BrowserWorkflowTests('test_original_checks_retained_in_order')
        case.new = changed
        case.test_original_checks_retained_in_order()

    def test_fixed_release_whole_inverse_chain_and_six_exact_current_steps(self):
        identity = historical_identity(comparison.budget.PATH)
        self.assertEqual(identity['commit'], '7383bb1dd82c5d2155ba7c8dcc11b541478f6cfe')
        self.assertEqual(identity['tree'], '56be467a913681f60dac48cefeedfce119b0a361')
        self.assertTrue(identity['historicalProofOnly'])
        self.assertFalse(identity['currentSourceReplacement'])
        raw = historical_bytes(comparison.budget.PATH)
        before = comparison.transport.source_input(comparison.cellular.source_input(
            comparison.budget.source_input(raw, comparison.budget.PATH), comparison.budget.PATH), comparison.budget.PATH)
        previous = yaml.safe_load(before)
        self.assertEqual(len(comparison.STEPS), 6)
        for owner, name in comparison.STEPS:
            with self.subTest(owner=owner):
                current = self.selected(self.current, owner, name)
                snapshot = copy.deepcopy(current)
                self.assertEqual(current, self.selected(self.released, owner, name))
                result = comparison.released_toolchain_step(current)
                self.assertEqual(result, self.selected(previous, owner, name))
                self.assertEqual(current, snapshot)
                result['run'] = 'changed caller copy'
                self.assertEqual(comparison.released_toolchain_step(current), self.selected(previous, owner, name))

    def test_each_owned_step_rejects_command_metadata_type_and_predecessor_drift(self):
        negative = 0
        for owner, name in comparison.STEPS:
            current = self.selected(self.current, owner, name)
            mutants = [dict(current, run=current['run']+'\ntrue'), dict(current, run=True),
                dict(current, **{'continue-on-error': True}), dict(current, **{'if': 'always()'}),
                dict(current, timeout=1), comparison.released_toolchain_step(current)]
            for changed in mutants:
                with self.subTest(owner=owner, changed=sorted(changed)), self.assertRaises(AssertionError):
                    comparison.released_toolchain_step(changed)
                negative += 1
        self.assertEqual(negative, 36)

    def test_actual_ordered_guard_rejects_changed_renamed_missing_and_rolled_back_steps(self):
        self.run_current_guard(copy.deepcopy(self.current))
        negative = 0
        for owner, name in comparison.STEPS[:4]:
            for fault in ('command', 'name', 'missing', 'rollback'):
                changed = copy.deepcopy(self.current)
                selected = self.selected(changed, owner, name)
                if fault == 'command': selected['run'] += '\ntrue'
                elif fault == 'name': selected['name'] += ' unreviewed'
                elif fault == 'missing': changed['jobs'][owner]['steps'].remove(selected)
                else:
                    position = changed['jobs'][owner]['steps'].index(selected)
                    changed['jobs'][owner]['steps'][position] = comparison.released_toolchain_step(selected)
                with self.subTest(owner=owner, fault=fault), self.assertRaises(AssertionError):
                    self.run_current_guard(changed)
                negative += 1
        self.assertEqual(negative, 16)

    def test_only_exact_android_timeout_can_use_its_former_comparison_value(self):
        reviewed = self.current['jobs']['android']['timeout-minutes']
        self.assertEqual(comparison.released_job_field_input('android', 'timeout-minutes', reviewed), 40)
        for changed in (40, 60, 40.0, True, None, '40', reviewed+' ', reviewed.replace('60', '61')):
            with self.subTest(value=changed), self.assertRaises(AssertionError):
                comparison.released_job_field_input('android', 'timeout-minutes', changed)
            actual = copy.deepcopy(self.current)
            actual['jobs']['android']['timeout-minutes'] = changed
            with self.assertRaises(AssertionError): self.run_current_guard(actual)
        sentinel = object()
        for owner, field in (('build', 'timeout-minutes'), ('android', 'runs-on'), ('unknown', 'permissions')):
            self.assertIs(comparison.released_job_field_input(owner, field, sentinel), sentinel)

    def test_unowned_steps_are_not_projected_and_invalid_owned_values_fail(self):
        for step in (None, True, {}, {'name': 'A new independent step', 'run': 'false'}):
            self.assertIs(comparison.released_toolchain_step(step), step)
        for value in (object(), float('nan'), float('inf')):
            changed = dict(self.selected(self.current, *comparison.STEPS[0]), value=value)
            with self.assertRaises(AssertionError): comparison.released_toolchain_step(changed)

    def test_missing_or_unknown_historical_bytes_cannot_become_a_mapping(self):
        current = self.selected(self.current, *comparison.STEPS[0])
        raw = historical_bytes(comparison.budget.PATH)
        for changed in (raw+b'\n', (ROOT/comparison.budget.PATH).read_bytes(), b''):
            comparison._reviewed_comparisons.cache_clear()
            with patch.object(comparison, 'historical_bytes', return_value=changed):
                with self.assertRaises(AssertionError): comparison.released_toolchain_step(current)
        comparison._reviewed_comparisons.cache_clear()
        with patch.object(comparison, 'historical_bytes', side_effect=RuntimeError('Missing actual owner')):
            with self.assertRaisesRegex(RuntimeError, 'Missing actual owner'):
                comparison.released_toolchain_step(current)

    def test_original_whole_source_strict_helpers_and_their_controls_are_unchanged(self):
        for name in ('gradle_transport_source_compatibility.py', 'cellular_workflow_source_compatibility.py',
                     'ui_job_budget_source_compatibility.py'):
            with self.subTest(name=name):
                self.assertEqual((ROOT/'tests'/name).read_bytes(), historical_bytes('tests/'+name))
        module = ast.parse((ROOT/'tests/released_workflow_comparison.py').read_bytes())
        self.assertFalse(any(isinstance(n, ast.Attribute) and n.attr in ('read_text', 'read_bytes') for n in ast.walk(module)))


if __name__ == '__main__':
    unittest.main(verbosity=2)
