"""Setup controls use real Git objects; synthetic transport is never release proof."""
import copy
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

from historical_source_inputs import COMMIT, TREE
import profile_host_prerequisites_test as original


setup = original.setup
ROOT = original.ROOT


class ReleasedHistoryPrerequisitesTests(unittest.TestCase):
    def setUp(self):
        self.control = original.ProfileHostPrerequisitesTests('test_all_real_owner_tree_blob_bytes_verify_offline_without_ci')
        self.control.setUp()
        self.addCleanup(self.control.doCleanups)
        self.root, self.source = self.control.root, self.control.source
        self.blob = subprocess.check_output(['git', 'hash-object', '-w', '--stdin'],
            input=b'Isolated retained payload for protocol controls, never a release oracle.\n', cwd=self.root).decode().strip()
        self.tree = subprocess.check_output(['git', 'mktree'],
            input=('100644 blob '+self.blob+'\tretained.txt\n').encode(), cwd=self.root).decode().strip()
        self.owner = self.control.git('commit-tree', self.tree, '-m', 'Isolated retained protocol owner').decode().strip()
        self.environment = self.control.environment

    def prepare(self, environment=None, source=None):
        # The synthetic owner is only a transport/protocol control. The first
        # test below independently checks the actual fixed released owner.
        with patch.object(setup, 'RELEASED_PROOF_COMMIT', self.owner), patch.object(setup, 'RELEASED_PROOF_TREE', self.tree):
            return setup.prepare_released_history(self.root, source_commit=self.source if source is None else source,
                environment=self.environment if environment is None else environment)

    def remove_object(self, identity):
        path = self.root/'.git/objects'/identity[:2]/identity[2:]
        raw = path.read_bytes()
        path.unlink()
        return path, raw

    def transport(self, action):
        original_checked = setup.history.checked
        def checked(root, *parts):
            if parts[0] == 'fetch':
                self.assertEqual(root, self.root)
                self.assertEqual(parts, ('fetch', '--refetch', '--no-tags', '--depth=1',
                    '--no-write-fetch-head', '--no-filter', 'origin', self.owner))
                return action()
            return original_checked(root, *parts)
        return patch.object(setup.history, 'checked', side_effect=checked)

    def test_actual_fixed_owner_tree_and_closure_verify_offline_without_expanding_original_groups(self):
        self.assertEqual(setup.RELEASED_PROOF_COMMIT, COMMIT)
        self.assertEqual(setup.RELEASED_PROOF_TREE, TREE)
        before = setup.history.checkout_state(ROOT)
        with patch.object(setup, 'authorize_fetch', side_effect=AssertionError('Present real objects must remain offline')):
            result = setup.prepare_released_history(ROOT, source_commit=before['sourceCommit'], environment={})
        self.assertEqual(result['status'], 'passed')
        self.assertEqual(result['fetchedCommits'], [])
        proof = result['releasedProof']
        self.assertEqual((proof['commit'], proof['tree']), (COMMIT, TREE))
        self.assertEqual(proof['reachableObjectsPresent'], 3394)
        self.assertTrue(proof['objectPresenceOnly'])
        self.assertTrue(proof['commitAndRootTreeSha1Verified'])
        self.assertEqual(proof['individualReadBytesVerifiedBy'], 'tests/historical_source_inputs.py')
        self.assertEqual(before, setup.history.checkout_state(ROOT))
        self.assertFalse(result['testsExecuted'])
        self.assertFalse(result['actualAndroidExecution'])
        self.assertEqual(len(setup.history.manifest(ROOT)), 21)
        self.assertEqual(len(setup.compatibility_groups(ROOT)[0]), 3)
        self.assertEqual(len(setup.supplemental_groups(ROOT)[0]), 2)

    def test_present_synthetic_closure_never_authorizes_network(self):
        before = setup.history.checkout_state(self.root)
        with patch.object(setup, 'authorize_fetch', side_effect=AssertionError('No missing objects')):
            result = self.prepare(environment={})
        self.assertEqual(result['releasedProof']['reachableObjectsPresent'], 2)
        self.assertEqual(result['fetchedCommits'], [])
        self.assertEqual(before, setup.history.checkout_state(self.root))

    def test_missing_commit_tree_or_blob_is_refetched_even_if_owner_is_already_present(self):
        for identity in (self.owner, self.tree, self.blob):
            with self.subTest(object=identity):
                path, raw = self.remove_object(identity)
                before = setup.history.checkout_state(self.root)
                environment_before = dict(self.environment)
                def restore():
                    path.write_bytes(raw)
                    return b''
                with self.transport(restore):
                    result = self.prepare()
                self.assertEqual(result['fetchedCommits'], [self.owner])
                self.assertEqual(result['releasedProof']['reachableObjectsPresent'], 2)
                self.assertEqual(before, setup.history.checkout_state(self.root))
                self.assertEqual(self.environment, environment_before)

    def test_real_local_shallow_fetch_obeys_the_same_exact_fixed_owner_command(self):
        # The source transport here is an isolated local bare repository; the
        # actual production command must still request only the fixed owner.
        remote = self.root/'source-control.git'
        subprocess.run(['git', 'clone', '--bare', '--no-hardlinks', str(self.root), str(remote)],
                       check=True, capture_output=True)
        subprocess.run(['git', '--git-dir='+str(remote), 'fetch', '--no-tags', str(self.root), self.owner],
                       check=True, capture_output=True)
        path, raw = self.remove_object(self.owner)
        before = setup.history.checkout_state(self.root)
        def actual_transport():
            return subprocess.check_output(['git', 'fetch', '--refetch', '--no-tags', '--depth=1',
                '--no-write-fetch-head', '--no-filter', str(remote), self.owner], cwd=self.root, stderr=subprocess.PIPE)
        try:
            with self.transport(actual_transport): result = self.prepare()
            self.assertEqual(result['fetchedCommits'], [self.owner])
            self.assertEqual(before, setup.history.checkout_state(self.root))
        finally:
            if not path.exists(): path.write_bytes(raw)

    def test_wrong_source_event_or_origin_rejects_before_transport(self):
        path, raw = self.remove_object(self.owner)
        try:
            with self.assertRaisesRegex(RuntimeError, 'source differs'):
                self.prepare(source='a'*40)
            with self.assertRaisesRegex(RuntimeError, 'fixed repository GitHub CI'):
                self.prepare(environment={})
            event = copy.deepcopy(self.control.event)
            self.control.event['pull_request']['head']['sha'] = 'a'*40
            self.control.write_event()
            with self.assertRaisesRegex(RuntimeError, 'head or base repository differs'):
                self.prepare()
            self.control.event = event
            self.control.write_event()
            self.control.git('remote', 'set-url', 'origin', 'https://github.com/foreign/repository.git')
            with self.assertRaisesRegex(RuntimeError, 'fixed public GitHub origin'):
                self.prepare()
        finally:
            path.write_bytes(raw)

    def test_wrong_tree_or_corrupt_owner_is_a_validation_error_not_a_fetch_request(self):
        with patch.object(setup, 'authorize_fetch', side_effect=AssertionError('Invalid ownership must not fetch')):
            with patch.object(setup, 'RELEASED_PROOF_COMMIT', self.owner), patch.object(setup, 'RELEASED_PROOF_TREE', 'a'*40):
                with self.assertRaisesRegex(RuntimeError, 'does not own the fixed tree'):
                    setup.prepare_released_history(self.root, source_commit=self.source, environment=self.environment)
            path, raw = self.remove_object(self.owner)
            try:
                path.write_bytes(b'corrupt Git commit')
                with self.assertRaises(RuntimeError) as failure: self.prepare()
                self.assertNotIsInstance(failure.exception, setup.history.MissingHistoricalObject)
            finally:
                path.unlink(); path.write_bytes(raw)

    def test_failed_or_incomplete_transport_never_reports_ready(self):
        path, raw = self.remove_object(self.blob)
        try:
            for failed in (False, True):
                def action():
                    if failed: raise RuntimeError('Transport failed')
                    return b''
                with self.subTest(failed=failed), self.transport(action):
                    with self.assertRaises(RuntimeError): self.prepare()
        finally:
            path.write_bytes(raw)

    def test_transport_source_change_is_rejected_after_fetch(self):
        path, raw = self.remove_object(self.owner)
        def change_source():
            path.write_bytes(raw)
            (self.root/'proof.txt').write_text('Changed checkout during transport\n')
            return b''
        with self.transport(change_source):
            with self.assertRaisesRegex(RuntimeError, 'fetch changed HEAD, tree, index or tracked bytes'):
                self.prepare()


if __name__ == '__main__':
    unittest.main(verbosity=2)
