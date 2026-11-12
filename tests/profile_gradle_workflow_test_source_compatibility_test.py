"""Exact public metadata closure controls; no workflow or producer projection."""
import ast
import json
import os
from pathlib import Path
import subprocess
import unittest

import final_browser_source_compatibility as final
import gradle_workflow_test_source_compatibility as inputs
from workspace_runner_source_compatibility import historical_input as workspace_source_input
from ui_job_budget_source_compatibility import historical_source_input as ui_job_budget_source_input
import profile_fixture_root_source_compatibility_test as root_controls
import profile_resource_startup_source_compatibility_test as resource_controls
from historical_source_inputs import historical_bytes

# Exercise composition through the retained source-control test interfaces.
# Their fixed metadata-consumer boundary remains unchanged for runtime code.
root_inputs = root_controls.layer
resource = resource_controls.layer

ROOT = Path(__file__).resolve().parents[1]


def git(*parts):
    return subprocess.check_output(['git', '--no-replace-objects', *parts], cwd=ROOT,
                                   env=dict(os.environ, GIT_NO_LAZY_FETCH='1'))


class GradleWorkflowTestSourceCompatibilityTests(unittest.TestCase):
    def test_public_before_whole_bytes_and_forward_roundtrips(self):
        value = inputs.manifest()
        self.assertEqual(git('rev-parse', value['baseCommit'] + '^{tree}').decode().strip(), value['baseTree'])
        for path, row in value['files'].items():
            raw = workspace_source_input(historical_bytes(path), path)
            before = git('show', value['baseCommit'] + ':' + path)
            self.assertEqual(inputs.source_input(raw, path), before)
            self.assertEqual((inputs.sha(before), len(before)), (row['previousSha256'], row['previousBytes']))
            self.assertEqual(inputs.historical_input(before, path), before)
            with self.assertRaises(ValueError):inputs.source_input(before, path)
            for delta in row['deltas']:
                previous, current = delta['previous'].encode(), delta['current'].encode()
                self.assertTrue(0 < len(previous) <= 32768 and 0 < len(current) <= 32768)
                self.assertEqual(before.count(previous), 1)
                before = before.replace(previous, current, 1)
            self.assertEqual(before, raw)

    def test_actual_after_context_mutations_still_face_original_guards(self):
        for path, row in inputs.manifest()['files'].items():
            raw = workspace_source_input(historical_bytes(path), path)
            candidates = [raw + b' ', raw[:1000], b'unknown source']
            for delta in row['deltas']:
                current = delta['current'].encode()
                self.assertEqual(raw.count(current), 1)
                remaining = raw.replace(current, b'', 1)
                moved = remaining + current
                if moved == raw:moved = current + remaining
                candidates.extend((remaining, raw.replace(current, current * 2, 1), moved,
                                   raw.replace(current, current + b' ', 1)))
            for candidate in candidates:
                self.assertNotEqual(candidate, raw)
                with self.subTest(path=path, sha256=inputs.sha(candidate)):
                    with self.assertRaises(ValueError):inputs.source_input(candidate, path)
                    self.assertEqual(inputs.historical_input(candidate, path), candidate)
                    with self.assertRaises(ValueError):resource.source_input(candidate, path)
                    if path == inputs.FINAL:
                        with self.assertRaises(ValueError):root_inputs.source_input(candidate, path)
        raw = ui_job_budget_source_input(historical_bytes(final.BUILD_BUDGET_PATH), final.BUILD_BUDGET_PATH)
        self.assertEqual(raw.count(final.BUILD_BUDGET_CURRENT), 1)
        changed = raw.replace(b'historical_toolchain_step(current[\'steps\'][at])==step', b'True', 1)
        self.assertNotEqual(changed, raw)
        with self.assertRaises(ValueError):final.build_budget_input(changed, final.BUILD_BUDGET_PATH)

    def test_root_and_resource_views_keep_real_before_hashes_counts_and_old_fixtures(self):
        value = inputs.manifest()
        root_view = root_inputs.manifest()
        self.assertEqual(sum(len(row['deltas']) for row in root_view['files'].values()), 7)
        row = root_view['files'][inputs.FINAL]
        before = git('show', '6ee06aced87581e52aa301431f8996ed46d666b8:' + inputs.FINAL)
        self.assertEqual((inputs.sha(before), len(before)), (row['previousSha256'], row['previousBytes']))
        for delta in row['deltas']:
            self.assertLessEqual(max(len(delta['previous'].encode()), len(delta['current'].encode())), 32768)
            self.assertEqual(before.count(delta['previous'].encode()), 1)
            before = before.replace(delta['previous'].encode(), delta['current'].encode(), 1)
        self.assertEqual(before, ui_job_budget_source_input(historical_bytes(inputs.FINAL), inputs.FINAL))
        old_config = json.loads(resource.CONFIG.read_bytes())
        current_config = resource.config()
        self.assertEqual(set(current_config['sources']), set(old_config['sources']))
        self.assertEqual(current_config['rootAfterRow'], old_config['rootAfterRow'])
        for path, old in old_config['sources'].items():
            current = current_config['sources'][path]
            self.assertEqual((current['previousSha256'], current['previousBytes']), (old['previousSha256'], old['previousBytes']))
            self.assertEqual(current['edits'][:len(old['edits'])], old['edits'])
            if path not in inputs.PREVIOUS:self.assertEqual(current, old)
        for fixture in ('profile-fixture-root-source-deltas.json', 'resource-startup-source-deltas.json', 'final-browser-source-deltas.json'):
            path = 'tests/fixtures/' + fixture
            self.assertEqual((ROOT / path).read_bytes(), git('show', value['baseCommit'] + ':' + path))

    def test_old_function_bodies_and_literal_oracles_stay_complete(self):
        value = inputs.manifest()
        def bodies(raw):
            text = raw.decode()
            return [ast.get_source_segment(text, node) for node in ast.walk(ast.parse(raw))
                    if isinstance(node, (ast.ClassDef, ast.FunctionDef))]
        for path in ('tests/profile_final_browser_source_compatibility_test.py',
                     'tests/profile_fixture_root_source_compatibility.py',
                     'tests/resource_startup_source_compatibility.py'):
            self.assertEqual(bodies(ui_job_budget_source_input(historical_bytes(path), path)), bodies(git('show', value['baseCommit'] + ':' + path)))
        for path in inputs.PREVIOUS:
            for raw in (None, bytearray(b'unknown'), b'', memoryview(b'unknown')):
                with self.assertRaises(ValueError):inputs.source_input(raw, path)
        for path in (None, Path(inputs.FINAL), '/' + inputs.FINAL, '../' + inputs.FINAL, 'tests/unowned.py'):
            with self.assertRaises(ValueError):inputs.source_input(b'unknown', path)


if __name__ == '__main__':
    unittest.main(verbosity=2)
