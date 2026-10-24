#!/usr/bin/env python3
"""Reject stale builds, changed protocols and incomplete benchmark samples."""
import copy
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest

SPEC = importlib.util.spec_from_file_location(
    'experience_comparison', Path(__file__).resolve().parents[1] / 'tools/gecko/run_experience_comparison.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ComparisonTests(unittest.TestCase):
    def test_impossible_idle_budget_is_rejected_before_any_build_or_device_access(self):
        for repetitions in range(5, 11):
            with self.subTest(repetitions=repetitions), self.assertRaisesRegex(ValueError, 'entire 1200-second phase budget'):
                MODULE.prepare(SimpleNamespace(repetitions=repetitions, scenario='idle-120'))
        MODULE.require_phase_budget(MODULE.scenarios.manifest('idle-120'), 3)
        MODULE.require_phase_budget(MODULE.scenarios.manifest('core'), 10)

    def setUp(self):
        self.build = dict(sourceCommit='a' * 40, sourceTree='b' * 40, version='2.0.16',
                          versionCode=69, apkSha256='c' * 64, apkBytes=100)
        self.protocol = {name: 'd' * 64 for name in MODULE.HARNESS + MODULE.SETUP}
        iteration = dict(
            index=1, status='passed', startup={'activityCreateToReadyMs': 100},
            actions=[dict(name=name, responseToDrawMs=20) for name in MODULE.ACTIONS],
            cpu=dict(available=False), memoryReady=dict(available=False), memoryFinal=dict(available=False),
            frames={'allNativeHwuiFrames': [], 'allChoreographerGapsMs': []}, scenarioWindows=[],
            seed={'scenario': {'manifest': MODULE.scenarios.manifest('core'),
                               'manifestSha256': MODULE.scenarios.digest(MODULE.scenarios.manifest('core'))}})
        self.report = dict(
            schema=1, status='passed', label='baseline-1', sourceCommit=self.build['sourceCommit'],
            buildIdentity=dict(self.build, package=MODULE.PACKAGE, dirtySource=False),
            runnerSha256='d' * 64, activitySha256='d' * 64,
            scenarioManifest=MODULE.scenarios.manifest('core'),
            scenarioManifestSha256=MODULE.scenarios.digest(MODULE.scenarios.manifest('core')),
            observerFiles={name: 'd' * 64 for name in MODULE.HARNESS}, executionInputsUnchanged=True,
            physicalDeviceAcceptance=False, realChatGptAcceptance=False, releaseAcceptance=False,
            predeclaredRepetitions=1, iterations=[iteration],
            environment=dict(serial=MODULE.SERIAL, androidSdk='35', abi='x86_64',
                             viewport='1080x1920', density='480', fontScale='1.0',
                             animationScales={name: '1.0' for name in MODULE.ANIMATIONS},
                             cpuCount=2, clockTicksPerSecond=100))

    def verify(self, report):
        return MODULE.verify_report(report, self.build, 'baseline-1', 1, self.protocol)

    def test_exact_installed_identity_is_required(self):
        self.verify(self.report)
        for field, value in [('sourceCommit', 'e' * 40), ('sourceTree', 'f' * 40),
                             ('apkSha256', 'e' * 64), ('apkBytes', 99), ('versionCode', 70),
                             ('package', 'local.pocketchat'), ('dirtySource', True)]:
            with self.subTest(field=field):
                report = copy.deepcopy(self.report)
                report['buildIdentity'][field] = value
                with self.assertRaises(ValueError):
                    self.verify(report)

    def test_missing_and_reordered_work_cannot_be_replaced(self):
        mutations = [
            lambda r: r.update(predeclaredRepetitions=2),
            lambda r: r.update(iterations=[]),
            lambda r: r['iterations'][0].update(index=True),
            lambda r: r['iterations'][0].update(status='failed'),
            lambda r: r['iterations'][0]['actions'].pop(),
            lambda r: r['iterations'][0]['actions'].reverse(),
        ]
        for mutate in mutations:
            report = copy.deepcopy(self.report)
            mutate(report)
            with self.assertRaises(ValueError):
                self.verify(report)

    def test_changed_observer_and_promoted_acceptance_fail(self):
        for field, value in [('runnerSha256', 'e' * 64), ('activitySha256', 'e' * 64),
                             ('releaseAcceptance', True), ('physicalDeviceAcceptance', True),
                             ('realChatGptAcceptance', True), ('label', 'replacement')]:
            report = copy.deepcopy(self.report)
            report[field] = value
            with self.assertRaises(ValueError):
                self.verify(report)

    def test_scenario_input_observer_and_device_seed_are_required(self):
        for mutate in (
                lambda r: r['scenarioManifest']['fixture'].update(replyRepeats=1),
                lambda r: r.update(scenarioManifestSha256='f' * 64),
                lambda r: r.update(executionInputsUnchanged=False),
                lambda r: r['observerFiles'].pop('tests/gecko/ExperienceScenarios.java'),
                lambda r: r['iterations'][0]['seed']['scenario'].update(manifestSha256='f' * 64),
                lambda r: r['iterations'][0].update(scenarioWindows=[{'name': 'undeclared'}])):
            report = copy.deepcopy(self.report)
            mutate(report)
            with self.assertRaises(ValueError):
                self.verify(report)

    def test_normal_animation_settings_required(self):
        for value in ('0', '0.5', '2', 'nan'):
            report = copy.deepcopy(self.report)
            report['environment']['animationScales']['window_animation_scale'] = value
            with self.assertRaises(ValueError):
                self.verify(report)

    def test_protocol_must_cover_all_fixed_sources(self):
        MODULE.matching_protocol(self.protocol, self.protocol)
        missing = dict(self.protocol)
        missing.pop('app/src/main/java/local/pocketchat/NormalCaretSdkReceipt.java')
        changed = dict(self.protocol)
        changed['tests/gecko/run_experience_benchmark.py'] = 'f' * 64
        with self.assertRaises(ValueError):
            MODULE.matching_protocol(missing, missing)
        with self.assertRaises(ValueError):
            MODULE.matching_protocol(self.protocol, changed)

    def test_activity_process_and_lifecycle_manifest_is_frozen(self):
        name = 'tests/gecko/AndroidManifest.xml'
        self.assertIn(name, MODULE.HARNESS)
        changed = dict(self.protocol)
        changed[name] = 'f' * 64
        with self.assertRaisesRegex(ValueError, 'Benchmark or environment setup changed between builds'):
            MODULE.matching_protocol(self.protocol, changed)
        missing = dict(self.protocol)
        missing.pop(name)
        with self.assertRaisesRegex(ValueError, 'Incomplete benchmark protocol'):
            MODULE.matching_protocol(missing, missing)

    def test_missing_cpu_memory_and_frames_never_become_zero(self):
        self.report['iterations'][0]['startup']['productionPageUsableFromActivityCreateMs'] = None
        result = MODULE.summarize([self.report])
        for key in ('cpuSecondsObserved', 'cpuPercentOfOneCoreObserved',
                    'memoryReadyPssKb', 'memoryFinalPssKb', 'observedNativeHwuiFrameMs'):
            self.assertEqual(result[key]['count'], 0)
            self.assertTrue(result[key]['unavailable'])
            self.assertEqual(result[key]['missingIterations'], 1)
            self.assertNotIn('median', result[key])
        changes = MODULE.deltas(result, result)
        self.assertNotIn('cpuSecondsObserved', changes)
        self.assertEqual(changes['activityCreateToFixtureReadyMs']['percentChange'], 0)

    def test_all_observations_include_slow_tail(self):
        second = copy.deepcopy(self.report)
        second['iterations'][0]['startup']['activityCreateToReadyMs'] = 900
        result = MODULE.summarize([self.report, second])
        self.assertEqual(result['activityCreateToFixtureReadyMs']['raw'], [100, 900])
        self.assertEqual(result['activityCreateToFixtureReadyMs']['median'], 500)
        self.assertEqual(result['activityCreateToFixtureReadyMs']['p95'], 900)
        for invalid in ([], [float('nan')], [float('inf')], [-1], [True], [None]):
            with self.assertRaises(ValueError):
                MODULE.values_summary(invalid)

    def test_incomplete_cpu_coverage_is_disclosed(self):
        self.report['iterations'][0]['cpu'] = dict(available=True, cpuSecondsObserved=2,
                                                  percentOfOneCore=20, completeProcessLifetimeCoverage=False)
        result = MODULE.summarize([self.report])
        self.assertEqual(result['cpuSecondsObserved']['median'], 2)
        self.assertFalse(result['cpuSecondsObserved']['allLifetimesCovered'])

    def test_identifiers_reject_unbound_refs_and_output_injection(self):
        MODULE.input_identity('a' * 40, '123', '1')
        for source, run, attempt in [('main', '123', '1'), ('a' * 40, '0', '1'),
                                     ('a' * 40, '123', '1\nother=bad')]:
            with self.assertRaises(ValueError):
                MODULE.input_identity(source, run, attempt)

    def test_push_build_selection_does_not_switch_run_or_attempt(self):
        row = dict(id=123, run_attempt=1, head_sha='a' * 40,
                   head_branch='release/gecko-2.0.16-experience', event='push')
        self.assertEqual(MODULE.select_push_run([row], row['head_sha'], row['head_branch']), row)
        self.assertIsNone(MODULE.select_push_run([row], 'f' * 40, row['head_branch']))
        with self.assertRaises(ValueError):
            MODULE.select_push_run([row, dict(row, id=124)], row['head_sha'], row['head_branch'])
        with self.assertRaises(ValueError):
            MODULE.select_push_run([dict(row, run_attempt=2)], row['head_sha'], row['head_branch'])


if __name__ == '__main__':
    unittest.main()
