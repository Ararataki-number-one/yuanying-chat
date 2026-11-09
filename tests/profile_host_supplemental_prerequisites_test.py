"""Setup-only real Git controls; no replacement of historical test inputs."""
import ast
import copy
import json
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import profile_host_prerequisites_test as original

setup = original.setup
ROOT = original.ROOT


class SupplementalHistoryPrerequisitesTests(unittest.TestCase):
    def setUp(self):
        self.control = original.ProfileHostPrerequisitesTests('test_all_real_owner_tree_blob_bytes_verify_offline_without_ci')
        self.control.setUp()
        self.addCleanup(self.control.doCleanups)
        self.root, self.source = self.control.root, self.control.source
        self.environment = self.control.environment
        self.groups = [dict(commit=value['commit'], tree=value['tree'], files={name:
            {key: pin[key] for key in ('blob', 'bytes', 'sha256')} for name, pin in value['files'].items()})
            for value in self.control.groups[:2]]

    def prepare(self, environment=None):
        with patch.object(setup, 'supplemental_groups', return_value=(self.groups, [])):
            return setup.prepare_supplemental_history(self.root, source_commit=self.source,
                environment=self.environment if environment is None else environment)

    def object_path(self, identity):
        return self.root / '.git/objects' / identity[:2] / identity[2:]

    def remove_object(self, identity):
        path = self.object_path(identity)
        raw = path.read_bytes(); path.unlink()
        return path, raw

    def transport(self, expected, action):
        checked = setup.history.checked
        def intercept(root, *parts):
            if parts[0] == 'fetch':
                self.assertEqual(root, self.root)
                self.assertEqual(parts, ('fetch', '--no-tags', '--depth=1', '--no-write-fetch-head',
                    '--no-filter', 'origin', *expected))
                return action()
            return checked(root, *parts)
        return patch.object(setup.history, 'checked', side_effect=intercept)

    def test_real_supplemental_bytes_verify_offline_without_expanding_original_inventories(self):
        before = setup.history.checkout_state(ROOT)
        with patch.object(setup, 'authorize_fetch', side_effect=AssertionError('Original blobs must already be available offline')):
            result = setup.prepare_supplemental_history(ROOT, source_commit=before['sourceCommit'], environment={})
        self.assertEqual(result['status'], 'passed')
        self.assertEqual({group['commit']: len(group['files']) for group in result['groups']}, {
            '6ee06aced87581e52aa301431f8996ed46d666b8': 5,
            '4e99ab57a4d58a2ce7ab4d7d8d0c3362da41cd2e': 8})
        self.assertEqual(sum(row['declarationContentPinChecked'] for group in result['groups'] for row in group['files']), 13)
        self.assertEqual(result['fetchedCommits'], [])
        self.assertEqual(before, setup.history.checkout_state(ROOT))
        self.assertFalse(result['testsExecuted']); self.assertFalse(result['actualAndroidExecution'])
        self.assertEqual(len(setup.history.manifest(ROOT)), 21)
        compatibility, declarations = setup.compatibility_groups(ROOT)
        self.assertEqual({group['commit'] for group in compatibility}, {
            '7402ead321ca74b9fbefeab32a1aaffb32832011',
            '4363dbc04df80d5c82ba966248e47a3fd69cbcc8',
            '4e99ab57a4d58a2ce7ab4d7d8d0c3362da41cd2e'})
        self.assertEqual(sum(len(group['files']) for group in compatibility), 15)
        self.assertEqual(len(declarations), 5)

    def test_declaration_drift_unknown_owner_path_and_symlink_fail_before_fetch(self):
        path = self.root / setup.FIXTURE_ROOT_DECLARATION
        path.parent.mkdir(parents=True)
        raw = (ROOT / setup.FIXTURE_ROOT_DECLARATION).read_bytes()
        mutations = [raw+b'\n']
        value = json.loads(raw); value['baseCommit'] = 'a'*40
        mutations.append(json.dumps(value).encode())
        value = json.loads(raw); value['files']['tests/unreviewed.py'] = next(iter(value['files'].values()))
        mutations.append(json.dumps(value).encode())
        value = json.loads(raw); next(iter(value['files'].values()))['previousBytes'] += 1
        mutations.append(json.dumps(value).encode())
        with patch.object(setup, 'authorize_fetch', side_effect=AssertionError('Changed declaration authorized fetch')):
            for changed in mutations:
                path.write_bytes(changed)
                with self.subTest(bytes=len(changed)), self.assertRaisesRegex(RuntimeError, 'declaration bytes differ'):
                    setup.prepare_supplemental_history(self.root, source_commit=self.source, environment=self.environment)
            path.unlink(); path.symlink_to(ROOT / setup.FIXTURE_ROOT_DECLARATION)
            with self.assertRaisesRegex(RuntimeError, 'ordinary bounded fixture-root declaration'):
                setup.prepare_supplemental_history(self.root, source_commit=self.source, environment=self.environment)

    def test_only_missing_owner_is_fetched_and_complete_checkout_stays_unchanged(self):
        owner = self.groups[1]['commit']
        path, raw = self.remove_object(owner)
        before = setup.history.checkout_state(self.root)
        def restore():
            path.write_bytes(raw)
            return b''
        with self.transport([owner], restore):
            result = self.prepare()
        self.assertEqual(result['fetchedCommits'], [owner])
        self.assertEqual(before, setup.history.checkout_state(self.root))
        self.assertEqual(len(result['groups']), 2)

    def test_missing_blob_is_detected_when_both_owner_commits_are_already_present(self):
        blob = self.groups[0]['files']['proof.txt']['blob']
        path, raw = self.remove_object(blob)
        owners = [group['commit'] for group in self.groups]
        def restore():
            path.write_bytes(raw)
            return b''
        with self.transport(owners, restore):
            result = self.prepare()
        self.assertEqual(result['fetchedCommits'], owners)
        self.assertTrue(all(group['files'][0]['blob'] == blob for group in result['groups']))

    def test_wrong_object_type_tree_blob_identity_content_and_corruption_never_fetch(self):
        original_groups = copy.deepcopy(self.groups)
        blob = self.groups[0]['files']['proof.txt']['blob']
        for fault in ('type', 'tree', 'blob', 'bytes', 'hash', 'corrupt'):
            with self.subTest(fault=fault):
                self.groups = copy.deepcopy(original_groups)
                path = self.object_path(self.groups[0]['commit']); raw = path.read_bytes()
                if fault == 'type': self.groups[0]['commit'] = blob
                elif fault == 'tree': self.groups[0]['tree'] = 'a'*40
                elif fault == 'blob': self.groups[0]['files']['proof.txt']['blob'] = 'a'*40
                elif fault == 'bytes': self.groups[0]['files']['proof.txt']['bytes'] = 1
                elif fault == 'hash': self.groups[0]['files']['proof.txt']['sha256'] = 'a'*64
                else: path.unlink(); path.write_bytes(b'not a Git object')
                try:
                    with patch.object(setup, 'authorize_fetch', side_effect=AssertionError('Invalid object authorized fetch')):
                        with self.assertRaises(RuntimeError) as failure: self.prepare()
                        self.assertNotIsInstance(failure.exception, setup.history.MissingHistoricalObject)
                finally:
                    if fault == 'corrupt': path.unlink(); path.write_bytes(raw)

    def test_missing_payload_rejects_unauthorized_failed_or_empty_transport(self):
        owner = self.groups[0]['commit']; path, raw = self.remove_object(owner)
        with self.assertRaisesRegex(RuntimeError, 'fixed repository GitHub CI'):
            self.prepare(environment={})
        for failed in (False, True):
            def deliver():
                if failed: raise RuntimeError('Transport failed')
                return b''
            with self.subTest(transportFailed=failed), self.transport([owner], deliver):
                with self.assertRaises(RuntimeError): self.prepare()
        path.write_bytes(raw)

    def test_fetch_cannot_change_tracked_source_or_succeed_after_object_read_race(self):
        owner = self.groups[0]['commit']; path, raw = self.remove_object(owner)
        def mutate():
            path.write_bytes(raw)
            (self.root/'proof.txt').write_text('Changed during controlled transport\n')
            return b''
        with self.transport([owner], mutate):
            with self.assertRaisesRegex(RuntimeError, 'supplemental fetch changed HEAD, tree, index or tracked bytes'):
                self.prepare()
        with patch.object(setup.history, 'object_bytes', side_effect=setup.history.MissingHistoricalObject('Read race')):
            with patch.object(setup, 'authorize_fetch', side_effect=AssertionError('Read race authorized fetch')):
                with self.assertRaisesRegex(RuntimeError, 'unreadable after its type probe'): self.prepare()


class ProfileRunnerSetupOrderTests(unittest.TestCase):
    def git_snapshot(self):
        return [subprocess.check_output(command, cwd=ROOT, text=True) for command in (
            ['git', 'rev-parse', 'HEAD'], ['git', 'rev-parse', 'HEAD^{tree}'],
            ['git', 'status', '--porcelain'])]

    def runner_prefix(self):
        source = (ROOT/'tools/gecko/run_profile_host_checks.py').read_text()
        module = ast.parse(source)
        main = next(node for node in module.body if isinstance(node, ast.FunctionDef) and node.name == 'main')
        snapshot = next(index for index, node in enumerate(main.body) if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == 'input_paths' for target in node.targets))
        prefix = ast.Module(body=main.body[:snapshot], type_ignores=[])
        self.assertEqual(sum(isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name) and node.func.value.id == 'subprocess'
            and node.func.attr == 'run' for node in ast.walk(prefix)), 1)
        return compile(ast.fix_missing_locations(prefix), '<actual profile setup prefix>', 'exec')

    def test_module_import_does_not_execute_setup_or_hosts(self):
        with patch.object(subprocess, 'run') as run, patch.object(subprocess, 'check_output') as output:
            runpy.run_path(str(ROOT/'tools/gecko/run_profile_host_checks.py'))
        run.assert_not_called(); output.assert_not_called()

    def test_unconditional_original_cli_finishes_before_input_snapshot(self):
        namespace = runpy.run_path(str(ROOT/'tools/gecko/run_profile_host_checks.py'))
        snapshot = self.git_snapshot(); source = snapshot[0].strip()
        with tempfile.TemporaryDirectory() as directory:
            jar = Path(directory)/'synthetic-argument-only.jar'; jar.write_bytes(b'Not executed')
            with patch.object(sys, 'argv', ['runner', '--json-jar', str(jar)]):
                with patch.object(subprocess, 'check_output', side_effect=snapshot*2), \
                        patch.object(subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)) as run:
                    exec(self.runner_prefix(), namespace)
            run.assert_called_once_with([sys.executable, str(ROOT/'tools/gecko/prepare_profile_host_prerequisites.py'),
                '--source-commit', source, '--root', str(ROOT),
                '--output', str(ROOT/'work/profile-host/prerequisites.json')], cwd=ROOT, check=True)
            self.assertNotIn('input_paths', namespace)

    def test_failed_setup_stops_actual_main_before_any_host_or_snapshot(self):
        namespace = runpy.run_path(str(ROOT/'tools/gecko/run_profile_host_checks.py'))
        snapshot = self.git_snapshot()
        with tempfile.TemporaryDirectory() as directory:
            jar = Path(directory)/'synthetic-argument-only.jar'; jar.write_bytes(b'Not executed')
            with patch.object(sys, 'argv', ['runner', '--json-jar', str(jar)]):
                with patch.object(subprocess, 'check_output', side_effect=snapshot), \
                        patch.object(subprocess, 'run', side_effect=subprocess.CalledProcessError(1, ['setup'])) as run:
                    with self.assertRaises(subprocess.CalledProcessError): namespace['main']()
            self.assertEqual(run.call_count, 1)
            self.assertIn('prepare_profile_host_prerequisites.py', run.call_args.args[0][1])

    def test_setup_change_to_head_tree_or_status_is_rejected_before_snapshot(self):
        for changed in ('HEAD', 'HEAD^{tree}', 'status'):
            namespace = runpy.run_path(str(ROOT/'tools/gecko/run_profile_host_checks.py'))
            calls = {}
            def git(command, **kwargs):
                key = command[-1] if command[1] == 'rev-parse' else 'status'
                calls[key] = calls.get(key, 0)+1
                return 'changed\n' if key == changed and calls[key] == 2 else {'HEAD': 'a'*40, 'HEAD^{tree}': 'b'*40, 'status': ''}[key]
            with tempfile.TemporaryDirectory() as directory:
                jar = Path(directory)/'synthetic-argument-only.jar'; jar.write_bytes(b'Not executed')
                with patch.object(sys, 'argv', ['runner', '--json-jar', str(jar)]):
                    with patch.object(subprocess, 'check_output', side_effect=git), patch.object(subprocess, 'run') as run:
                        with self.subTest(changed=changed), self.assertRaisesRegex(ValueError, 'setup changed source checkout'):
                            exec(self.runner_prefix(), namespace)
                self.assertEqual(run.call_count, 1)
                self.assertNotIn('input_paths', namespace)


if __name__ == '__main__':
    unittest.main(verbosity=2)
