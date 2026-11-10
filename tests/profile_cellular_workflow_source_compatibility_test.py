"""Exact preparation input history; no host result is Android acceptance."""
import copy
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import yaml

import cellular_workflow_source_compatibility as cellular
import gradle_transport_source_compatibility as gradle
import ui_checkpoint_source_compatibility as checkpoint
import ui_job_budget_source_compatibility as ui_job_budget

ROOT = Path(__file__).resolve().parents[1]
CURRENT = (92783, 'e077be03328741ac49c8043d17af707287c8fff664c0486eb91dbeff6ce0f0e8')
PREVIOUS = (92383, '2629831d0afd9176b0ce4d92a4c03117b66a3f20c4912885b4c31b391160f83e')
HOST_NAME = 'Verify strict cellular emulator preparation controls'
PREPARATION_JOBS = ('chrome-diagnostic', 'android', 'editing-samples', 'browser', 'tls')
PORTS = {
    'tests/gradle_transport_source_compatibility.py',
    'tests/profile_gradle_transport_source_compatibility_test.py',
    'tests/profile_environment_workspace_workflow_source_compatibility_test.py',
    'tests/native_timezone_probe_test.py',
    'tests/gecko_cpu_acceptance_test.py',
}


def digest(raw):
    return len(raw), hashlib.sha256(raw).hexdigest()


def forward(previous, deltas):
    offsets = []
    shift = 0
    for owner, offset, before, after in deltas:
        offsets.append((offset - shift, before, after))
        shift += len(after) - len(before)
    result = previous
    for offset, before, after in reversed(offsets):
        assert result[offset:offset + len(before)] == before
        result = result[:offset] + after + result[offset + len(before):]
    return result


class CellularWorkflowSourceCompatibilityTests(unittest.TestCase):
    def workflow(self):
        return ui_job_budget.historical_workflow_input((ROOT / cellular.PATH).read_bytes(), cellular.PATH)

    def reject_workflow(self, candidate, actual):
        self.assertNotEqual(candidate, actual)
        with self.assertRaises(AssertionError):
            cellular.source_input(candidate, cellular.PATH)
        self.assertIs(cellular.historical_input(candidate, cellular.PATH), candidate)
        with self.assertRaises(AssertionError):
            gradle.source_input(candidate, cellular.PATH)
        with self.assertRaises(AssertionError):
            checkpoint.checkpoint_workflow_input(candidate)

    def test_complete_current_image_reverses_exactly_eight_calls_and_one_host_step(self):
        raw = self.workflow()
        self.assertEqual(digest(raw), CURRENT)
        self.assertEqual((cellular.CURRENT_BYTES, cellular.CURRENT_SHA256), CURRENT)
        self.assertEqual((cellular.PREVIOUS_BYTES, cellular.PREVIOUS_SHA256), PREVIOUS)
        self.assertEqual(cellular.BASE_COMMIT, 'b55eee51d143170b46a5363aa5c6e120f07b982c')
        self.assertEqual(cellular.BASE_TREE, 'cbb6692ea39577f5a15930a3953746027082972f')
        expected = ('build/strict-cellular-host-controls', 'chrome-diagnostic/native',
                    'chrome-diagnostic/normal', 'android/native', 'android/normal',
                    'editing-samples/native', 'editing-samples/normal', 'browser/normal', 'tls/normal')
        self.assertEqual(tuple(row[0] for row in cellular.DELTAS), expected)
        self.assertEqual(tuple(row[1] for row in cellular.DELTAS),
                         (7217, 46838, 47117, 53783, 54062, 69280, 69559, 83431, 90848))
        before = cellular.source_input(raw, cellular.PATH)
        self.assertEqual(digest(before), PREVIOUS)
        self.assertEqual(forward(before, cellular.DELTAS), raw)
        self.assertEqual(cellular.historical_workflow_text(raw.decode()).encode(), before)
        self.assertEqual(raw.count(b'prepare_cellular_adb.py --phase native'), 3)
        self.assertEqual(raw.count(b'prepare_cellular_adb.py --phase normal'), 5)
        self.assertEqual(before.count(b'python3 tools/gecko/prepare_native_adb.py'), 3)
        self.assertEqual(before.count(b'python3 tools/gecko/prepare_emulator.py'), 5)
        self.assertNotIn(b'python3 tools/gecko/prepare_native_adb.py', raw)
        self.assertNotIn(b'python3 tools/gecko/prepare_emulator.py', raw)
        self.assertEqual(self.workflow(), raw)

    def test_raw_yaml_keeps_all_jobs_workloads_inputs_budgets_and_mandatory_host_controls(self):
        raw = self.workflow()
        actual = yaml.safe_load(raw)
        previous = yaml.safe_load(cellular.source_input(raw, cellular.PATH))
        restored = copy.deepcopy(actual)
        build = restored['jobs']['build']['steps']
        selected = [step for step in build if step.get('name') == HOST_NAME]
        self.assertEqual(selected, [dict(name=HOST_NAME, shell='bash', run=(
            'set -euo pipefail\n'
            'python3 tests/gecko_cellular_bootstrap_test.py\n'
            'python3 tests/profile_cellular_workflow_source_compatibility_test.py\n'))])
        position = build.index(selected[0])
        self.assertEqual(build[position - 1]['name'], 'Verify pinned network core and source patch')
        self.assertEqual(build[position + 1]['name'], 'Prepare locked toolchain')
        build.pop(position)
        calls = {'native': 0, 'normal': 0}
        for owner in PREPARATION_JOBS:
            selected = [step for step in restored['jobs'][owner]['steps']
                        if 'python3 tools/gecko/prepare_cellular_adb.py' in step.get('run', '')]
            self.assertEqual(len(selected), 1)
            step = selected[0]
            for phase, predecessor in (('native', 'prepare_native_adb.py'), ('normal', 'prepare_emulator.py')):
                current = 'python3 tools/gecko/prepare_cellular_adb.py --phase ' + phase
                count = step['run'].count(current)
                self.assertEqual(count, int(phase == 'normal' or owner in PREPARATION_JOBS[:3]))
                calls[phase] += count
                step['run'] = step['run'].replace(current, 'python3 tools/gecko/' + predecessor)
            if owner in ('browser', 'tls'):
                self.assertIn('-port 5554', step['run'])
                self.assertNotIn('prepare_native_adb.py', step['run'])
        self.assertEqual(calls, {'native': 3, 'normal': 5})
        # A complete object comparison includes all original shell lines, job
        # order, workloads, permissions, runner, matrix, SDK and deadlines.
        self.assertEqual(restored, previous)
        self.assertEqual(yaml.safe_load(self.workflow()), actual)

    def test_every_missing_duplicated_moved_or_changed_delta_is_rejected(self):
        raw = self.workflow()
        for owner, offset, before, after in cellular.DELTAS:
            remainder = raw[:offset] + raw[offset + len(after):]
            candidates = (remainder, raw[:offset] + after + raw[offset:],
                          remainder + after, raw[:offset] + after + b' ' + raw[offset + len(after):])
            for index, candidate in enumerate(candidates):
                with self.subTest(owner=owner, mutation=index):
                    self.reject_workflow(candidate, raw)

    def test_unowned_budget_hardware_serial_reader_and_source_changes_are_rejected(self):
        raw = self.workflow()
        replacements = (
            (b'timeout-minutes: 60', b'timeout-minutes: 61'),
            (b'-cores 4', b'-cores 5'),
            (b'--serial emulator-5554', b'--serial emulator-5556'),
            (b'--monitor "$PWD/work/gecko-integration/qemu-monitor.sock"', b'--monitor /tmp/unowned.sock'),
            (b'--apk app/build/outputs/apk/integration/app-x86_64-integration.apk', b'--apk /tmp/unverified.apk'),
            (b'timeout 300 bash', b'timeout 301 bash'),
            (b'python3 tools/browser/check_evidence.py', b'true # reader removed'),
            (b'python3 tests/gecko/run_ui_visuals.py', b'true # workload removed'),
            (b'        set -euo pipefail\n        python3 tests/gecko_cellular_bootstrap_test.py',
             b'        set +e\n        python3 tests/gecko_cellular_bootstrap_test.py'),
        )
        for before, after in replacements:
            with self.subTest(token=before):
                self.assertTrue(before in raw, 'Mutation must select an actual original workflow token')
                self.reject_workflow(raw.replace(before, after, 1), raw)
        for changed in (raw + b'\n', raw[:-1], raw[:1024]):
            self.reject_workflow(changed, raw)

    def test_types_paths_excerpts_and_predecessor_cannot_replace_current_raw_input(self):
        raw = self.workflow()
        for candidate in (None, raw.decode(), bytearray(raw), memoryview(raw), True, b''):
            with self.assertRaises(AssertionError):
                cellular.source_input(candidate, cellular.PATH)
        for path in (None, Path(cellular.PATH), '../' + cellular.PATH, '/' + cellular.PATH, 'unknown'):
            with self.assertRaises(AssertionError):
                cellular.source_input(raw, path)
        before = cellular.source_input(raw, cellular.PATH)
        with self.assertRaises(AssertionError):
            cellular.source_input(before, cellular.PATH)
        self.assertIs(cellular.historical_input(before, cellular.PATH), before)
        for value in (None, raw, bytearray(raw), True):
            with self.assertRaises(AssertionError):
                cellular.historical_workflow_text(value)

    def test_five_exact_source_ports_restore_the_original_whole_source_and_old_predicates(self):
        self.assertEqual(set(cellular.SOURCE_PORTS), PORTS)
        self.assertEqual([len(row['deltas']) for row in cellular.SOURCE_PORTS.values()], [1, 3, 2, 2, 2])
        for path, row in cellular.SOURCE_PORTS.items():
            with self.subTest(path=path):
                raw = (ROOT / path).read_bytes()
                before = cellular.source_port_input(raw, path)
                self.assertEqual(digest(raw), (row['reviewedBytes'], row['reviewedSha256']))
                self.assertEqual(digest(before), (row['previousBytes'], row['previousSha256']))
                self.assertEqual(forward(before, row['deltas']), raw)
                for candidate in (raw + b' ', raw[:-1], raw[:64], before):
                    with self.assertRaises(AssertionError):
                        cellular.source_port_input(candidate, path)
                for owner, offset, old, current in row['deltas']:
                    missing = raw[:offset] + raw[offset + len(current):]
                    moved = missing + current
                    if moved == raw:
                        moved = current + missing
                    for candidate in (missing, moved, raw[:offset] + current + raw[offset:]):
                        self.assertNotEqual(candidate, raw)
                        with self.assertRaises(AssertionError):
                            cellular.source_port_input(candidate, path)
        for path in ('tests/browser_acceptance_workflow_test.py', '../tests/native_timezone_probe_test.py', None):
            with self.assertRaises(AssertionError):
                cellular.source_port_input(b'not-an-owned-source', path)

    def test_old_gradle_and_checkpoint_pins_and_raw_browser_oracles_still_execute(self):
        import browser_acceptance_workflow_test as workflow
        raw = self.workflow()
        previous = gradle.canonical_history_input(raw)
        self.assertEqual(hashlib.sha256(previous).hexdigest(), checkpoint.WORKFLOW_CURRENT_SHA256)
        self.assertEqual(hashlib.sha256(checkpoint.checkpoint_workflow_input(raw)).hexdigest(),
                         'a0fdfae87d0b32ee1ab9479aacdbff81755e9e5fe45cfcaf92a8bce3e11a0069')
        self.assertEqual(gradle.FIXTURE_SHA256, '0e34228b10f4ecb511c584f5fc071e06ffd87e6981caddd80b0510897fbcc793')
        cls = workflow.BrowserWorkflowTests
        cls.setUpClass()
        self.assertEqual(ui_job_budget.historical_yaml_input(cls.new), yaml.safe_load(raw))
        cls('test_original_checks_retained_in_order').test_original_checks_retained_in_order()
        cls('test_single_pipeline_shares_actual_apk_and_gates_browser').test_single_pipeline_shares_actual_apk_and_gates_browser()
        self.assertEqual(ui_job_budget.historical_yaml_input(cls.new), yaml.safe_load(raw))

    def test_only_complete_reviewed_preparation_steps_are_projected_without_mutation(self):
        raw = self.workflow()
        current = yaml.safe_load(raw)
        previous = yaml.safe_load(cellular.source_input(raw, cellular.PATH))
        for owner in PREPARATION_JOBS:
            step = next(step for step in current['jobs'][owner]['steps']
                        if 'python3 tools/gecko/prepare_cellular_adb.py' in step.get('run', ''))
            original = copy.deepcopy(step)
            expected = next(row for row in previous['jobs'][owner]['steps'] if row.get('name') == step['name'])
            self.assertEqual(cellular.historical_step_input(step), expected)
            self.assertEqual(step, original)
            mutants = (dict(step, run=step['run'] + '\n'), dict(step, shell='sh'),
                       dict(step, **{'continue-on-error': True}), dict(step, **{'timeout-minutes': 99}),
                       dict(step, run=step['run'].replace('--phase normal', '--phase native', 1)))
            for mutant in mutants:
                self.assertNotEqual(mutant, step)
                self.assertIs(cellular.historical_step_input(mutant), mutant)
        with tempfile.TemporaryDirectory(prefix='cellular-raw-workflow-') as directory:
            root = Path(directory)
            path = root / cellular.PATH
            path.parent.mkdir(parents=True)
            path.write_bytes(raw.replace(b'-cores 4', b'-cores 5', 1))
            with patch.object(cellular, 'ROOT', root), self.assertRaises(AssertionError):
                cellular.historical_step_input(step)
        self.assertEqual(self.workflow(), raw)


if __name__ == '__main__':
    unittest.main(verbosity=2)
