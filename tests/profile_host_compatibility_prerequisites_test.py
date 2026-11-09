"""Real Git-object controls for setup-only compatibility history preparation."""
import copy
import json
from pathlib import Path
import shutil
import unittest
from unittest.mock import patch

import profile_host_prerequisites_test as original

setup = original.setup
ROOT = original.ROOT


class CompatibilityHistoryPrerequisitesTests(unittest.TestCase):
    def setUp(self):
        # Reuse the established real-Git fixture; do not replace any of its
        # twenty-one-owner assertions or execute them a second time here.
        self.control = original.ProfileHostPrerequisitesTests('test_all_real_owner_tree_blob_bytes_verify_offline_without_ci')
        self.control.setUp()
        self.addCleanup(self.control.doCleanups)
        self.root, self.source = self.control.root, self.control.source
        self.environment = self.control.environment
        self.groups = [dict(commit=value['commit'], tree=value['tree'], files={name:
            {key: pin[key] for key in ('bytes', 'sha256')} for name, pin in value['files'].items()})
            for value in self.control.groups[:3]]

    def prepare(self, environment=None):
        with patch.object(setup, 'compatibility_groups', return_value=(self.groups, [])):
            return setup.prepare_compatibility_history(self.root, source_commit=self.source,
                environment=self.environment if environment is None else environment)

    def object_path(self, identity):
        return self.root / '.git/objects' / identity[:2] / identity[2:]

    def remove_objects(self, identities):
        values = {}
        for identity in identities:
            path = self.object_path(identity)
            values[path] = path.read_bytes()
            path.unlink()
        return values

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

    def test_existing_declarations_resolve_all_actual_fixed_owners_and_required_blobs_offline(self):
        before = setup.history.checkout_state(ROOT)
        with patch.object(setup, 'authorize_fetch', side_effect=AssertionError('Actual declared objects must verify offline')):
            result = setup.prepare_compatibility_history(ROOT, source_commit=before['sourceCommit'], environment={})
        self.assertEqual(result['status'], 'passed')
        self.assertEqual({group['commit'] for group in result['groups']}, {
            '7402ead321ca74b9fbefeab32a1aaffb32832011',
            '4363dbc04df80d5c82ba966248e47a3fd69cbcc8',
            '4e99ab57a4d58a2ce7ab4d7d8d0c3362da41cd2e'})
        self.assertEqual(len(result['declarations']), 5)
        self.assertEqual(sum(len(group['files']) for group in result['groups']), 15)
        self.assertEqual(sum(row['declarationContentPinChecked'] for group in result['groups'] for row in group['files']), 10)
        self.assertEqual(len(setup.history.manifest(ROOT)), 21)
        self.assertEqual(result['fetchedCommits'], [])
        self.assertEqual(before, setup.history.checkout_state(ROOT))
        self.assertFalse(result['testsExecuted'])
        self.assertFalse(result['actualAndroidExecution'])

    def test_changed_or_symlinked_declarations_fail_before_any_fetch(self):
        directory = self.root / 'tests/fixtures'; directory.mkdir(parents=True)
        for name, *_ in setup.COMPATIBILITY_DECLARATIONS:
            shutil.copy2(ROOT / 'tests/fixtures' / name, directory / name)
        for name, *_ in setup.COMPATIBILITY_DECLARATIONS:
            path = directory / name
            original_bytes = path.read_bytes()
            path.write_bytes(original_bytes+b'\n')
            with self.subTest(name=name), self.assertRaisesRegex(RuntimeError, 'declaration bytes differ'):
                setup.compatibility_groups(self.root)
            path.write_bytes(original_bytes)
        name = setup.COMPATIBILITY_DECLARATIONS[0][0]
        (directory / name).unlink(); (directory / name).symlink_to(ROOT / 'tests/fixtures' / name)
        with self.assertRaisesRegex(RuntimeError, 'ordinary bounded compatibility declaration'):
            setup.compatibility_groups(self.root)

    def test_missing_commit_batch_fetches_only_absent_owners_and_preserves_checkout(self):
        expected = [self.groups[index]['commit'] for index in (0, 2)]
        removed = self.remove_objects(expected)
        before = setup.history.checkout_state(self.root)
        def restore():
            for path, raw in removed.items():
                path.write_bytes(raw)
            return b''
        with self.transport(expected, restore):
            result = self.prepare()
        self.assertEqual(result['fetchedCommits'], expected)
        self.assertEqual(len(result['groups']), 3)
        self.assertEqual(before, setup.history.checkout_state(self.root))

    def test_missing_blob_also_fetches_its_exact_owner_and_verifies_payload(self):
        blob = self.control.groups[0]['files']['proof.txt']['blob']
        removed = self.remove_objects([blob])
        expected = [group['commit'] for group in self.groups]
        def restore():
            for path, raw in removed.items():
                path.write_bytes(raw)
            return b''
        with self.transport(expected, restore):
            result = self.prepare()
        self.assertEqual(result['fetchedCommits'], expected)
        self.assertTrue(all(group['files'][0]['blob'] == blob for group in result['groups']))

    def test_wrong_type_corrupt_object_tree_and_content_are_errors_without_fetch(self):
        original_groups = copy.deepcopy(self.groups)
        blob = self.control.groups[0]['files']['proof.txt']['blob']
        for fault in ('wrong-type', 'wrong-tree', 'wrong-bytes', 'wrong-hash', 'corrupt'):
            with self.subTest(fault=fault):
                self.groups = copy.deepcopy(original_groups)
                path = self.object_path(self.groups[0]['commit']); raw = path.read_bytes()
                if fault == 'wrong-type': self.groups[0]['commit'] = blob
                elif fault == 'wrong-tree': self.groups[0]['tree'] = 'a'*40
                elif fault == 'wrong-bytes': self.groups[0]['files']['proof.txt']['bytes'] = 1
                elif fault == 'wrong-hash': self.groups[0]['files']['proof.txt']['sha256'] = 'a'*64
                else:
                    path.unlink(); path.write_bytes(b'not a valid compressed Git object')
                try:
                    with patch.object(setup, 'authorize_fetch', side_effect=AssertionError('Wrong/corrupt object authorized fetch')):
                        with self.assertRaises(RuntimeError) as failure:
                            self.prepare()
                        self.assertNotIsInstance(failure.exception, setup.history.MissingHistoricalObject)
                finally:
                    if fault == 'corrupt':
                        path.unlink(); path.write_bytes(raw)

    def test_disappearing_after_successful_type_probe_is_not_a_missing_fetch_candidate(self):
        with patch.object(setup.history, 'object_bytes', side_effect=setup.history.MissingHistoricalObject('Read race')):
            with self.assertRaisesRegex(RuntimeError, 'unreadable after its type probe') as failure:
                setup.compatibility_object_bytes(self.root, 'commit', self.groups[0]['commit'])
        self.assertNotIsInstance(failure.exception, setup.history.MissingHistoricalObject)

    def test_successful_transport_without_payload_and_failed_transport_cannot_pass(self):
        owner = self.groups[0]['commit']; removed = self.remove_objects([owner])
        for fail_transport in (False, True):
            def deliver():
                if fail_transport:
                    raise RuntimeError('Declared transport failure')
                return b''
            with self.subTest(fail_transport=fail_transport), self.transport([owner], deliver):
                with self.assertRaises(RuntimeError): self.prepare()
        for path, raw in removed.items(): path.write_bytes(raw)

    def test_missing_owner_uses_existing_ci_authorization_and_rejects_checkout_mutation(self):
        owner = self.groups[0]['commit']; removed = self.remove_objects([owner])
        with self.assertRaisesRegex(RuntimeError, 'fixed repository GitHub CI'):
            self.prepare(environment={})
        def changing_fetch():
            for path, raw in removed.items(): path.write_bytes(raw)
            (self.root/'proof.txt').write_text('Mutation during synthetic transport\n')
            return b''
        with self.transport([owner], changing_fetch):
            with self.assertRaisesRegex(RuntimeError, 'compatibility fetch changed HEAD, tree, index or tracked bytes'):
                self.prepare()


if __name__ == '__main__':
    unittest.main(verbosity=2)
