"""Actual old 80dp report regression plus explicit host component observations.

The a9 assertion value is retained unchanged. New component owner/bounds data
below is a host model for the new read-only fixture, never new Android evidence.
"""
import ast
import copy
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/gecko'))
from native_navigation_v2 import validate_compact_toolbar_v2


def actual_old_sample():
    return json.loads((ROOT / 'tests/fixtures/native-navigation-v2/canonical-a9-compact-360-1.json').read_text())


def component(identity, parent, bounds, minimum=0):
    return dict(identity=identity, rootIdentity=99, parentIdentity=parent, bounds=list(bounds),
                shown=True, visibility=0, padding=[0, 0, 0, 0], minimumHeight=minimum)


def host_observation(*, top_dp=56, scale=1, stacked=False):
    sample = actual_old_sample()
    start = 72 + top_dp * 3
    row_height = 94 if scale == 2 else 60
    end = start + (row_height * 2 if stacked else row_height) + 12
    toolbar = component(1, 98, [0, 72, 1080, end]);toolbar['padding'] = [48, 0, 48, 0]
    top = component(2, 1, [48, 72, 1032, start])
    network = component(3, 1, [48, start, 1032, end]);network['padding'] = [18, 0, 18, 12]
    network['orientation'] = int(stacked)
    boxes = ([66, start, 1014, start + row_height], [66, start + row_height, 1014, end - 12]) if stacked else (
             [66, start, 619, end - 12], [619, start, 1014, end - 12])
    network['rows'] = [dict(component(i + 4, 3, box, row_height), naturalContentHeight=row_height)
                       for i, box in enumerate(boxes)]
    sample.update(fontScale=scale, toolbar=toolbar['bounds'], toolbarHeightDp=(end - 72) / 3,
                  topHeightDp=top_dp, networkHeightDp=(end - start) / 3, networkBounds=network['bounds'])
    sample['nativeToolbarLayout'] = dict(schema=1, package='local.pocketchat.test',
        activityClass='local.pocketchat.CompactChromeIntegrationActivity', pid=2026,
        uid=10209, applicationUid=10209, density=3, toolbar=toolbar, top=top, network=network,
        visibleToolbarChildren=[copy.deepcopy(top), copy.deepcopy(network)])
    return sample


class NativeToolbarV2Test(unittest.TestCase):
    def test_actual_old_report_is_80dp_with_a_separate_56dp_top_and_24dp_network_row(self):
        sample = actual_old_sample()
        self.assertEqual((sample['command'], sample['toolbarHeightDp'], sample['topHeightDp'], sample['networkHeightDp']),
                         ('compact-360-1', 80, 56, 24))
        self.assertEqual([c['heightDp'] for c in sample['controls']], [52, 52, 52])
        with self.assertRaises(AssertionError):
            assert sample['toolbarHeightDp'] <= 59
        with self.assertRaises(KeyError):
            validate_compact_toolbar_v2(sample, 360, 1)
        # Old raw dimensions cannot masquerade as the newly measured owners.

    def test_new_host_component_observation_keeps_raw_80_and_applies_59_to_actual_top(self):
        sample = host_observation()
        result = validate_compact_toolbar_v2(sample, 360, 1)
        self.assertEqual((sample['toolbarHeightDp'], result['actualToolbarHeightDp']), (80, 80))
        self.assertEqual((result['actualTopHeightDp'], result['actualNetworkHeightDp'], result['topControlLimitDp']), (56, 24, 59))
        self.assertIs(result['nativeOwnerAndCompositionVerified'], True)

    def test_original_59_and_100_top_budgets_reject_coherent_taller_component_models(self):
        for scale, height in ((1, 60), (2, 101)):
            with self.subTest(scale=scale), self.assertRaisesRegex(ValueError, 'top-control budget'):
                validate_compact_toolbar_v2(host_observation(top_dp=height, scale=scale), 360, scale)
        self.assertEqual(validate_compact_toolbar_v2(host_observation(top_dp=100, scale=2, stacked=True),
                                                   360, 2)['topControlLimitDp'], 100)

    def test_raw_parent_height_cannot_be_changed_to_the_top_height(self):
        sample = host_observation();sample['toolbarHeightDp'] = sample['topHeightDp']
        with self.assertRaises(ValueError):
            validate_compact_toolbar_v2(sample, 360, 1)

    def test_package_uid_root_parent_and_exact_types_are_bound(self):
        variants = []
        for key, value in [('package', 'foreign.test'), ('uid', 1), ('pid', True), ('schema', True), ('density', float('nan'))]:
            sample = host_observation();sample['nativeToolbarLayout'][key] = value;variants.append(sample)
        for key, value in [('parentIdentity', 8), ('parentIdentity', True), ('rootIdentity', 100), ('shown', 1), ('visibility', False)]:
            sample = host_observation();sample['nativeToolbarLayout']['top'][key] = value;variants.append(sample)
        for sample in variants:
            with self.subTest(sample=sample['nativeToolbarLayout']), self.assertRaises(ValueError):
                validate_compact_toolbar_v2(sample, 360, 1)

    def test_missing_reordered_or_extra_visible_toolbar_child_is_rejected(self):
        for action in ('drop', 'reverse', 'extra'):
            sample = host_observation();children = sample['nativeToolbarLayout']['visibleToolbarChildren']
            if action == 'drop':children.pop()
            elif action == 'reverse':children.reverse()
            else:children.append(component(10, 1, [48, 312, 1032, 330]))
            with self.subTest(action=action), self.assertRaises(ValueError):
                validate_compact_toolbar_v2(sample, 360, 1)

    def test_native_control_touches_must_fit_the_actual_top_row_and_48dp(self):
        for kind in ('cross-network', 'small'):
            sample = host_observation()
            if kind == 'cross-network':sample['controls'][0]['touch'][3] = 250
            else:sample['controls'][0]['touch'][2] = sample['controls'][0]['touch'][0] + 143
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                validate_compact_toolbar_v2(sample, 360, 1)

    def test_network_stays_passive_and_cannot_hide_unmeasured_vertical_space(self):
        for kind in ('click', 'focus', 'background', 'extra-space', 'inflated-natural-row'):
            sample = host_observation();layout = sample['nativeToolbarLayout']
            if kind == 'click':sample['networkClickable'] = True
            elif kind == 'focus':sample['networkFocusable'] = True
            elif kind == 'background':sample['networkBackground'] = 'RippleDrawable'
            elif kind == 'extra-space':
                sample['toolbarHeightDp'] += 10;sample['networkHeightDp'] += 10
                sample['toolbar'][3] += 30;sample['networkBounds'][3] += 30
                layout['visibleToolbarChildren'][1]['bounds'][3] += 30
            else:layout['network']['rows'][0]['naturalContentHeight'] += 1
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                validate_compact_toolbar_v2(sample, 360, 1)

    def test_overlapping_or_nonjoining_network_subrows_are_rejected(self):
        for stacked in (False, True):
            sample = host_observation(stacked=stacked)
            row = sample['nativeToolbarLayout']['network']['rows'][1]
            row['bounds'][0 if not stacked else 1] -= 1
            with self.subTest(stacked=stacked), self.assertRaises(ValueError):
                validate_compact_toolbar_v2(sample, 360, 1)

    def test_actual_runner_retains_v1_whole_container_assertion_and_explicit_current_v2(self):
        tree = ast.parse((ROOT / 'tests/gecko/run_ui_visuals.py').read_text())
        branch = next(n for n in ast.walk(tree) if isinstance(n, ast.If)
                      and ast.unparse(n.test) == 'compact_navigation_protocol == 1')
        self.assertEqual(ast.unparse(branch.body[0]),
                         "assert sample['toolbarHeightDp'] <= (59 if scale == 1 else 100), sample")
        for protocol in (1, 2):
            sample = host_observation()
            env = dict(compact_navigation_protocol=protocol, sample=sample, width=360, scale=1,
                       validate_compact_toolbar_v2=validate_compact_toolbar_v2)
            code = compile(ast.fix_missing_locations(ast.Module(body=[copy.deepcopy(branch)], type_ignores=[])), '<actual runner branch>', 'exec')
            if protocol == 1:
                with self.assertRaises(AssertionError):exec(code, env)
            else:
                exec(code, env);self.assertEqual(sample['nativeToolbarValidation']['actualToolbarHeightDp'], 80)


if __name__ == '__main__':
    unittest.main()
