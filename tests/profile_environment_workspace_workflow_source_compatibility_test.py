"""Exact environment-capture workflow history; never device execution evidence."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import unittest

import environment_workspace_workflow_source_compatibility as workspace
import profile_display_sampling_gate_test as display

ROOT = Path(__file__).resolve().parents[1]
DISPLAY = 'tests/profile_display_sampling_gate_test.py'
PORT_IMPORT = 'from environment_workspace_workflow_source_compatibility import historical_workflow_text as environment_workspace_workflow_input\n'
PREVIOUS_READ = "source=(root/'.github/workflows/profile-upgrade-checks.yml').read_text()"
CURRENT_READ = "source=environment_workspace_workflow_input((root/'.github/workflows/profile-upgrade-checks.yml').read_text())"


def previous_blob(path):
    return subprocess.check_output(['git', '--no-replace-objects', 'show', workspace.PREVIOUS_COMMIT + ':' + path],
                                   cwd=ROOT, env=dict(os.environ, GIT_NO_LAZY_FETCH='1'))


class EnvironmentWorkspaceWorkflowSourceTests(unittest.TestCase):
    def test_inverse_and_forward_match_the_actual_upstream_git_blob(self):
        value = workspace.manifest()
        tree = subprocess.check_output(['git', '--no-replace-objects', 'rev-parse', workspace.PREVIOUS_COMMIT + '^{tree}'],
                                       cwd=ROOT, env=dict(os.environ, GIT_NO_LAZY_FETCH='1')).decode().strip()
        self.assertEqual(tree, workspace.PREVIOUS_TREE)
        before = previous_blob(workspace.PATH)
        current = (ROOT / workspace.PATH).read_bytes()
        self.assertEqual(workspace.source_input(current, workspace.PATH), before)
        self.assertEqual(workspace.historical_workflow_text(current.decode()).encode(), before)
        restored = before
        for delta in value['deltas']:
            previous, after = delta['previous'].encode(), delta['current'].encode()
            self.assertEqual(restored.count(previous), 1)
            restored = restored.replace(previous, after, 1)
        self.assertEqual(restored, current)
        self.assertEqual((ROOT / workspace.PATH).read_bytes(), current)

    def assert_rejected_by_both_guards(self, changed, original):
        self.assertNotEqual(changed, original)
        with self.assertRaises(AssertionError):
            workspace.source_input(changed, workspace.PATH)
        text = changed.decode()
        self.assertEqual(workspace.historical_workflow_text(text), text)
        with self.assertRaises(AssertionError):
            display.reverse_reviewed_glass_host_workflow_additions(workspace.historical_workflow_text(text))

    def test_missing_duplicated_moved_and_changed_reviewed_hunks_fail_closed(self):
        raw = (ROOT / workspace.PATH).read_bytes()
        for delta in workspace.manifest()['deltas']:
            current = delta['current'].encode()
            self.assertEqual(raw.count(current), 1)
            remaining = raw.replace(current, b'', 1)
            moved = current + remaining
            if moved == raw:
                moved = remaining + current
            for changed in (remaining, raw.replace(current, current * 2, 1), moved,
                            raw.replace(current, current + b' ', 1)):
                with self.subTest(sha256=workspace.sha(changed)):
                    self.assert_rejected_by_both_guards(changed, raw)

    def test_branch_timeout_environment_and_capture_arguments_are_exact(self):
        raw = (ROOT / workspace.PATH).read_bytes()
        mutations = (
            (b'"codex/environment-workspace-polish"', b'"codex/unreviewed-workspace"'),
            (b'        timeout-minutes: 9\n', b'        timeout-minutes: 10\n'),
            (b'          TASK_CAPTURE_BRANCH: ${{ github.head_ref || github.ref_name }}\n', b'          TASK_CAPTURE_BRANCH: unreviewed\n'),
            (b'if [ "$TASK_CAPTURE_BRANCH" = \'codex/environment-workspace-polish\' ]; then', b'if true; then'),
            (b'task_environment_capture_args=(--environment-workspace)', b'task_environment_capture_args=()'),
            (b'--out work/glass-navigation "${task_environment_capture_args[@]}"', b'--out work/glass-navigation'),
        )
        for before, after in mutations:
            self.assertIn(before, raw)
            with self.subTest(anchor=before):
                self.assert_rejected_by_both_guards(raw.replace(before, after, 1), raw)

    def test_unrelated_steps_action_pins_and_existing_validation_cannot_change(self):
        raw = (ROOT / workspace.PATH).read_bytes()
        mutations = (
            (b'checkout@11d5960a326750d5838078e36cf38b85af677262', b'checkout@unreviewed'),
            (b'    timeout-minutes: 15\n', b'    timeout-minutes: 16\n'),
            (b'--source-commit ', b'--source-commit-changed '),
            (b'python3 tools/gecko/run_profile_host_checks.py --json-jar work/profile-host/json.jar', b'python3 -c "pass"'),
            (b'-no-snapshot -no-boot-anim', b'-snapshot -no-boot-anim'),
            (b'3cf6cd6892e32e2b4c1c39e0f52f5248a2f5b37646fdfbb79a66b46b618414ed', b'0' * 64),
        )
        for before, after in mutations:
            self.assertIn(before, raw)
            with self.subTest(anchor=before):
                self.assert_rejected_by_both_guards(raw.replace(before, after, 1), raw)

    def test_types_paths_partial_and_unknown_sources_cannot_gain_acceptance(self):
        raw = (ROOT / workspace.PATH).read_bytes()
        for changed in (None, raw.decode(), bytearray(raw), memoryview(raw), True, b'', raw[:1024], raw + b'\n'):
            with self.assertRaises(AssertionError):
                workspace.source_input(changed, workspace.PATH)
        for path in (None, Path(workspace.PATH), '/' + workspace.PATH, '../' + workspace.PATH,
                     'tools/gecko/capture_glass_navigation.py'):
            with self.assertRaises(AssertionError):
                workspace.source_input(raw, path)
        for changed in (None, raw, bytearray(raw), True):
            with self.assertRaises(AssertionError):
                workspace.historical_workflow_text(changed)

    def test_known_predecessor_retains_the_original_guard_and_original_manifest(self):
        before = previous_blob(workspace.PATH)
        with self.assertRaises(AssertionError):
            workspace.source_input(before, workspace.PATH)
        self.assertEqual(workspace.historical_workflow_text(before.decode()), before.decode())
        original = display.reverse_reviewed_glass_host_workflow_additions(before.decode())
        self.assertEqual(hashlib.sha256(original.encode()).hexdigest(), display.profile_workflow_history_manifest()['previousSha256'])
        path = 'tests/fixtures/profile-glass-host-workflow-deltas.json'
        self.assertEqual((ROOT / path).read_bytes(), previous_blob(path))

    def test_only_the_declared_display_test_read_ports_change(self):
        raw = (ROOT / DISPLAY).read_text()
        self.assertEqual(raw.count(PORT_IMPORT), 1)
        self.assertEqual(raw.count(CURRENT_READ), 2)
        restored = raw.replace(PORT_IMPORT, '', 1).replace(CURRENT_READ, PREVIOUS_READ)
        self.assertEqual(restored.encode(), previous_blob(DISPLAY))

    def test_diagnostic_previous_bytes_and_all_original_delta_sides_stay_locked(self):
        path = 'tests/fixtures/glass-diagnostic-source-deltas.json'
        before = json.loads(previous_blob(path))
        current = json.loads((ROOT / path).read_bytes())
        self.assertEqual(set(before), set(current))
        for key in ('schema', 'baseCommit', 'baseTree'):
            self.assertEqual(current[key], before[key])
        self.assertEqual(set(before['files']), set(current['files']))
        for name, row in before['files'].items():
            changed = current['files'][name]
            self.assertEqual(changed['previousBytes'], row['previousBytes'])
            self.assertEqual(changed['previousSha256'], row['previousSha256'])
            self.assertEqual(len(changed['deltas']), len(row['deltas']))
            for after, previous in zip(changed['deltas'], row['deltas']):
                for key in ('previous', 'previousBytes', 'previousSha256'):
                    self.assertEqual(after[key], previous[key])
            if name != DISPLAY:
                self.assertEqual(changed, row)


if __name__ == '__main__':
    unittest.main(verbosity=2)
