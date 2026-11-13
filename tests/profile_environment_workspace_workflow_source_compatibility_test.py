"""Fixed 2.1.4 environment-workflow history; never current CI execution evidence."""
import hashlib
import json
import os
from pathlib import Path
from historical_source_inputs import historical_bytes
import subprocess
import unittest

import yaml

import environment_workspace_workflow_source_compatibility as workspace
import profile_display_sampling_gate_test as display
import gradle_transport_source_compatibility as transport
from cellular_workflow_source_compatibility import source_port_input as cellular_source_port_input

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
        working_path=ROOT/workspace.PATH;working_bytes=working_path.read_bytes()
        value = workspace.manifest()
        tree = subprocess.check_output(['git', '--no-replace-objects', 'rev-parse', workspace.PREVIOUS_COMMIT + '^{tree}'],
                                       cwd=ROOT, env=dict(os.environ, GIT_NO_LAZY_FETCH='1')).decode().strip()
        self.assertEqual(tree, workspace.PREVIOUS_TREE)
        before = previous_blob(workspace.PATH)
        current = historical_bytes(workspace.PATH)
        self.assertEqual(workspace.source_input(current, workspace.PATH), before)
        self.assertEqual(workspace.historical_workflow_text(current.decode()).encode(), before)
        restored = before
        for delta in value['deltas']:
            previous, after = delta['previous'].encode(), delta['current'].encode()
            self.assertEqual(restored.count(previous), 1)
            restored = restored.replace(previous, after, 1)
        self.assertEqual(restored, current)
        self.assertEqual(historical_bytes(workspace.PATH), current)
        self.assertEqual(working_path.read_bytes(),working_bytes)

    def assert_rejected_by_both_guards(self, changed, original):
        self.assertNotEqual(changed, original)
        with self.assertRaises(AssertionError):
            workspace.source_input(changed, workspace.PATH)
        text = changed.decode()
        self.assertEqual(workspace.historical_workflow_text(text), text)
        with self.assertRaises(AssertionError):
            display.reverse_reviewed_glass_host_workflow_additions(workspace.historical_workflow_text(text))

    def test_missing_duplicated_moved_and_changed_reviewed_hunks_fail_closed(self):
        raw = historical_bytes(workspace.PATH)
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
        raw = historical_bytes(workspace.PATH)
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

    def test_environment_push_and_branch_concurrency_preserve_paths_and_event_identity(self):
        raw = historical_bytes(workspace.PATH)
        current = yaml.load(raw, Loader=yaml.BaseLoader)
        previous = yaml.load(previous_blob(workspace.PATH), Loader=yaml.BaseLoader)
        self.assertEqual(current['on']['push']['branches'], previous['on']['push']['branches'] + ['codex/environment-workspace-polish'])
        self.assertEqual(current['on']['push']['paths'], previous['on']['push']['paths'])
        self.assertEqual(current['on']['pull_request'], previous['on']['pull_request'])
        self.assertEqual(current['on']['workflow_dispatch'], previous['on']['workflow_dispatch'])
        self.assertEqual(current['permissions'], previous['permissions'])
        self.assertEqual(current['concurrency'], {'group': 'profile-upgrade-checks-${{ github.head_ref || github.ref_name }}', 'cancel-in-progress': 'true'})
        for job in ('host-contracts', 'official-sdk-build'):
            self.assertEqual(current['jobs'][job]['steps'][0], previous['jobs'][job]['steps'][0])

    def test_push_scope_concurrency_and_checkout_identity_mutations_are_rejected(self):
        raw = historical_bytes(workspace.PATH)
        mutations = (
            (b"'release/gecko-*', 'codex/environment-workspace-polish']", b"'release/gecko-*', '*']"),
            (b"'release/gecko-*', 'codex/environment-workspace-polish']", b"'release/gecko-*']"),
            (b'group: profile-upgrade-checks-${{ github.head_ref || github.ref_name }}', b'group: profile-upgrade-checks-${{ github.ref }}'),
            (b'group: profile-upgrade-checks-${{ github.head_ref || github.ref_name }}', b'group: profile-upgrade-checks-all-branches'),
            (b'  cancel-in-progress: true', b'  cancel-in-progress: false'),
            (b"    paths: ['app/**', 'tests/**'", b"    paths: ['**', 'tests/**'"),
            (b'ref: ${{ github.event.pull_request.head.sha || github.sha }}', b'ref: ${{ github.sha }}'),
            (b'permissions:\n  contents: read', b'permissions:\n  contents: write'),
        )
        for before, after in mutations:
            self.assertIn(before, raw)
            with self.subTest(anchor=before):
                self.assert_rejected_by_both_guards(raw.replace(before, after, 1), raw)

    def test_extra_history_owner_is_exact_and_keeps_the_original_twenty_one(self):
        source = historical_bytes(workspace.PATH).decode('utf-8')
        prepare = "          python3 tools/gecko/prepare_profile_host_prerequisites.py --source-commit '${{ github.event.pull_request.head.sha || github.sha }}' --output work/profile-host/prerequisites.json\n"
        fetch = '          git fetch --no-tags --depth=1 --no-write-fetch-head --no-filter origin 6ee06aced87581e52aa301431f8996ed46d666b8\n'
        following = '          npm install --prefix work/resource-observer --ignore-scripts --no-audit --no-fund jsdom@26.1.0\n'
        self.assertEqual(source.count(prepare + fetch + following), 1)
        path = 'tests/baselines/public-source-history.json'
        raw = (ROOT / path).read_bytes()
        self.assertEqual(raw, previous_blob(path))
        self.assertNotIn(b'6ee06aced87581e52aa301431f8996ed46d666b8', raw)
        target = 'tests/profile_gradle_workflow_test_source_compatibility_test.py'
        self.assertIn(b"git('show', '6ee06aced87581e52aa301431f8996ed46d666b8:' + inputs.FINAL)", previous_blob(target))
        for changed in (fetch.replace('6ee06aced87581e52aa301431f8996ed46d666b8', 'unreviewed-ref'),
                        fetch.replace('--no-filter ', ''), fetch.replace('--no-write-fetch-head ', ''),
                        fetch.replace('--depth=1', '--depth=0')):
            with self.subTest(command=changed):
                self.assert_rejected_by_both_guards(source.replace(fetch, changed, 1).encode(), source.encode())

    def test_unrelated_steps_action_pins_and_existing_validation_cannot_change(self):
        raw = historical_bytes(workspace.PATH)
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

    def test_environment_inverse_preserves_the_exact_upstream_gradle_transport(self):
        raw = historical_bytes(workspace.PATH)
        previous = previous_blob(workspace.PATH)
        restored = workspace.source_input(raw, workspace.PATH)
        self.assertEqual(restored, previous)
        row = transport.manifest()['files'][workspace.PATH]
        self.assertEqual(len(row['deltas']), 1)
        current = row['deltas'][0]['current'].encode()
        self.assertEqual(raw.count(current), 1)
        self.assertEqual(previous.count(current), 1)
        historical = subprocess.check_output(['git', '--no-replace-objects', 'show',
            transport.manifest()['baseCommit'] + ':' + workspace.PATH], cwd=ROOT,
            env=dict(os.environ, GIT_NO_LAZY_FETCH='1'))
        self.assertEqual(transport.source_input(restored, workspace.PATH), historical)
        for path in ('tests/fixtures/gradle-transport-source-deltas.json',
                     'tests/fixtures/gradle-workflow-test-source-deltas.json'):
            self.assertEqual((ROOT / path).read_bytes(), previous_blob(path))

    def test_environment_adapter_cannot_hide_upstream_asset_size_or_checksum_changes(self):
        raw = historical_bytes(workspace.PATH)
        mutations = (
            (b'https://api.github.com/repos/gradle/gradle-distributions/releases/assets/586068844', b'https://api.github.com/repos/gradle/gradle-distributions/releases/assets/586068845'),
            (b'151611662', b'151611663'),
            (b'bafd5ce9cfaea0fbccfdc8439a1ac42fbd4cd9c89dc9a988228d8a2639a58e6c', b'0' * 64),
            (b"-H 'Accept: application/octet-stream' ", b''),
            (b"-H 'X-GitHub-Api-Version: 2022-11-28' ", b''),
            (b'--max-time 240', b'--max-time 241'),
            (b'https://services.gradle.org/', b'https://unreviewed.invalid/'),
            (b"work/profile-build/gradle.zip' | sha256sum -c -\n", b"work/profile-build/gradle.zip' | sha256sum -c - || true\n"),
        )
        for before, after in mutations:
            self.assertEqual(raw.count(before), 1)
            changed = raw.replace(before, after, 1)
            with self.subTest(anchor=before):
                self.assert_rejected_by_both_guards(changed, raw)
                with self.assertRaises(AssertionError):
                    transport.source_input(workspace.historical_workflow_text(changed.decode()).encode(), workspace.PATH)

    def test_types_paths_partial_and_unknown_sources_cannot_gain_acceptance(self):
        raw = historical_bytes(workspace.PATH)
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
        raw = historical_bytes(DISPLAY).decode('utf-8')
        self.assertEqual(raw.count(PORT_IMPORT), 1)
        self.assertEqual(raw.count(CURRENT_READ), 2)
        restored = raw.replace(PORT_IMPORT, '', 1).replace(CURRENT_READ, PREVIOUS_READ)
        self.assertEqual(restored.encode(), previous_blob(DISPLAY))

    def test_gradle_transport_controls_only_add_two_owned_read_ports(self):
        path = 'tests/profile_gradle_transport_source_compatibility_test.py'
        source = cellular_source_port_input(historical_bytes(path), path).decode()
        imported = 'from environment_workspace_workflow_source_compatibility import PATH as ENVIRONMENT_WORKFLOW_PATH, source_input as environment_workflow_source_input\n'
        current = 'raw = environment_workflow_source_input((ROOT / path).read_bytes(), path) if path == ENVIRONMENT_WORKFLOW_PATH else (ROOT / path).read_bytes()'
        previous = 'raw = (ROOT / path).read_bytes()'
        self.assertEqual(source.count(imported), 1)
        self.assertEqual(source.count(current), 2)
        self.assertEqual(source.replace(imported, '', 1).replace(current, previous).encode(), previous_blob(path))

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
