"""Fixed UI job history; no result is current workflow or Android acceptance."""
import copy
import hashlib
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import yaml
import ui_job_budget_source_compatibility as budget
from historical_source_inputs import historical_bytes

ROOT = Path(__file__).resolve().parents[1]


class UiJobBudgetSourceCompatibilityTests(unittest.TestCase):
    def setUp(self):
        # This whole class proves the old file reader and inverse. Current
        # workflow fields are checked separately by BrowserWorkflowTests.
        temporary = tempfile.TemporaryDirectory(prefix='released-ui-budget-proof-')
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        path = root / budget.PATH
        path.parent.mkdir(parents=True)
        path.write_bytes(historical_bytes(budget.PATH))
        selected = patch.object(budget, 'ROOT', root)
        selected.start()
        self.addCleanup(selected.stop)

    def workflow(self):
        return historical_bytes(budget.PATH)

    def test_actual_raw_workflow_changes_only_ui_job_resource_envelope(self):
        raw = self.workflow()
        self.assertEqual((len(raw), hashlib.sha256(raw).hexdigest()),
                         (92820, '6d61140b1f654c38b9a9b7cb030c4e4481aa521ca1a662a45abc79f80563e381'))
        previous = budget.source_input(raw, budget.PATH)
        self.assertEqual(previous, subprocess.check_output(['git', 'show', budget.BASE_COMMIT + ':' + budget.PATH], cwd=ROOT))
        actual, before = yaml.safe_load(raw), yaml.safe_load(previous)
        self.assertEqual(actual['jobs']['android']['timeout-minutes'], "${{ matrix.phase == 'ui' && 60 || 40 }}")
        self.assertEqual(actual['jobs']['android']['strategy']['matrix']['phase'],
                         ['ui', 'editing', 'files', 'connections', 'profiles'])
        restored = copy.deepcopy(actual)
        restored['jobs']['android']['timeout-minutes'] = 40
        self.assertEqual(restored, before)
        self.assertEqual(raw.count(b"timeout-minutes: ${{ matrix.phase == 'ui' && 60 || 40 }}"), 1)
        self.assertEqual(len(budget.DELTAS), 1)
        owner, offset, old, new = budget.DELTAS[0]
        self.assertEqual(owner, 'android/ui-job-container-budget')
        self.assertEqual(raw[:offset] + old + raw[offset + len(new):], previous)
        self.assertIn(b"python3 -m unittest discover -s tests -p 'profile_*_test.py'", raw)
        self.assertEqual(self.workflow(), raw)

    def test_missing_duplicate_moved_partial_and_unknown_workflows_reject(self):
        raw = self.workflow()
        _, offset, old, new = budget.DELTAS[0]
        missing = raw[:offset] + raw[offset + len(new):]
        candidates = [missing, missing + new, raw[:offset] + new + raw[offset:],
                      raw + b'\n', raw[:-1], raw[:1024], budget.source_input(raw, budget.PATH)]
        for candidate in candidates:
            with self.subTest(size=len(candidate)):
                with self.assertRaises(AssertionError): budget.source_input(candidate, budget.PATH)
                self.assertIs(budget.historical_workflow_input(candidate, budget.PATH), candidate)
        for candidate in (None, raw.decode(), bytearray(raw), memoryview(raw), True, b''):
            with self.assertRaises(AssertionError): budget.source_input(candidate, budget.PATH)
        for path in (None, Path(budget.PATH), '../' + budget.PATH, '/' + budget.PATH, 'unknown'):
            with self.assertRaises(AssertionError): budget.source_input(raw, path)

    def test_other_phases_action_budgets_hardware_readers_and_samples_cannot_change(self):
        raw = self.workflow()
        edits = ((b"matrix.phase == 'ui' && 60 || 40", b"matrix.phase == 'ui' && 61 || 40"),
                 (b"matrix.phase == 'ui' && 60 || 40", b"matrix.phase == 'ui' && 60 || 60"),
                 (b"matrix.phase == 'ui'", b"matrix.phase == 'files'"),
                 (b'-cores 4', b'-cores 5'), (b'timeout 300 bash', b'timeout 301 bash'),
                 (b'--serial emulator-5554', b'--serial emulator-5556'),
                 (b'python3 tools/browser/check_evidence.py', b'true # removed reader'),
                 (b'python3 tests/gecko/run_ui_visuals.py', b'true # removed UI workload'),
                 (b"sample: ['1', '2']", b"sample: ['1']"))
        for old, new in edits:
            with self.subTest(token=old):
                self.assertIn(old, raw)
                changed = raw.replace(old, new, 1)
                with self.assertRaises(AssertionError): budget.source_input(changed, budget.PATH)
                self.assertIs(budget.historical_workflow_input(changed, budget.PATH), changed)

    def test_historical_field_projection_is_exact_and_raw_yaml_stays_raw(self):
        raw = self.workflow(); actual = yaml.safe_load(raw); saved = copy.deepcopy(actual)
        self.assertEqual(budget.historical_yaml_input(actual), yaml.safe_load(budget.source_input(raw, budget.PATH)))
        self.assertEqual(budget.historical_job_field_input('android', 'timeout-minutes', budget.EXPRESSION), 40)
        for job, field, value in [('build', 'timeout-minutes', 60), ('tls', 'timeout-minutes', 40),
                                  ('android', 'timeout-minutes', 61), ('android', 'timeout-minutes', budget.EXPRESSION + ' '),
                                  ('android', 'steps', budget.EXPRESSION)]:
            self.assertIs(budget.historical_job_field_input(job, field, value), value)
        for mutant in [dict(actual, extra=True), dict(actual, jobs={})]:
            with self.assertRaises(AssertionError): budget.historical_yaml_input(mutant)
        self.assertEqual(actual, saved); self.assertEqual(self.workflow(), raw)

    def test_actual_file_must_be_ordinary_complete_and_reviewed(self):
        raw = self.workflow()
        with tempfile.TemporaryDirectory(prefix='ui-job-budget-') as directory:
            root = Path(directory); path = root / budget.PATH; path.parent.mkdir(parents=True)
            for candidate in (raw + b' ', raw.replace(b'-cores 4', b'-cores 5', 1), raw[:10]):
                path.write_bytes(candidate)
                with self.assertRaises(AssertionError): budget.workflow_read_input(path)
                with patch.object(budget, 'ROOT', root), self.assertRaises(AssertionError):
                    budget.historical_job_field_input('android', 'timeout-minutes', budget.EXPRESSION)
            path.write_bytes(raw)
            self.assertEqual(budget.workflow_read_input(path), budget.source_input(raw, budget.PATH))
            link = root / 'link.yml'; link.symlink_to(path)
            with self.assertRaises(AssertionError): budget.workflow_read_input(link)

    def test_exact_source_ports_restore_every_original_predicate_and_pin(self):
        self.assertTrue(budget.SOURCE_PORTS)
        for path, row in budget.SOURCE_PORTS.items():
            with self.subTest(path=path):
                raw = historical_bytes(path)
                previous = budget.source_port_input(raw, path)
                self.assertEqual(previous, subprocess.check_output(['git', 'show', budget.BASE_COMMIT + ':' + path], cwd=ROOT))
                self.assertEqual(budget.historical_source_input(raw, path), previous)
                for changed in (raw + b' ', raw[:-1], raw[:80], previous):
                    with self.assertRaises(AssertionError): budget.source_port_input(changed, path)
                    self.assertIs(budget.historical_source_input(changed, path), changed)
                for owner, offset, old, new in row['deltas']:
                    missing = raw[:offset] + raw[offset + len(new):]
                    moved = missing + new
                    if moved == raw: moved = new + missing
                    for changed in (missing, moved, raw[:offset] + new + raw[offset:]):
                        self.assertNotEqual(changed, raw)
                        with self.assertRaises(AssertionError): budget.source_port_input(changed, path)

    def test_unknown_images_stop_before_contexts_and_nonclosing_inverses_reject(self):
        raw = self.workflow()
        owner, offset, old, new = budget.DELTAS[0]
        with patch.object(budget, 'DELTAS', ((owner, offset, old + b'# foreign\n', new),)):
            with self.assertRaisesRegex(AssertionError, 'predecessor did not restore'):
                budget.source_input(raw, budget.PATH)
        with patch.object(budget, 'DELTAS', ((owner, offset, object(), object()),)):
            with self.assertRaisesRegex(AssertionError, 'Unknown complete'):
                budget.source_input(raw + b' ', budget.PATH)
        for path, row in budget.SOURCE_PORTS.items():
            changed = dict(row, previousSha256='0' * 64)
            with patch.dict(budget.SOURCE_PORTS, {path: changed}):
                with self.assertRaisesRegex(AssertionError, 'predecessor did not restore'):
                    budget.source_port_input(historical_bytes(path), path)


if __name__ == '__main__':
    unittest.main(verbosity=2)
