"""Real Git inputs for historical proofs remain separate from current behavior."""
from pathlib import Path
import os
import subprocess
import unittest
from unittest.mock import patch

import historical_source_inputs as inputs

SOURCE = 'app/src/main/java/local/pocketchat/GeckoWebView.java'


class HistoricalSourceInputsTests(unittest.TestCase):
    def setUp(self):
        inputs._verified_source.cache_clear()

    def tearDown(self):
        inputs._verified_source.cache_clear()

    def test_actual_published_commit_tree_path_blob_and_bytes(self):
        raw = inputs.historical_bytes(SOURCE)
        self.assertEqual(inputs.historical_identity(SOURCE), dict(
            commit='7383bb1dd82c5d2155ba7c8dcc11b541478f6cfe',
            tree='56be467a913681f60dac48cefeedfce119b0a361', path=SOURCE,
            blob='bbf8242a8b7d1d3cb8a6dbe17e64b076b8eea412', bytes=128874,
            sha256='55225a8da3ba67b3be724e243c9b442e635dbc5aa282a2ef0257653e8fb2b364',
            historicalProofOnly=True, currentSourceReplacement=False))
        actual = subprocess.check_output(['git', '--no-replace-objects', 'show',
            inputs.COMMIT + ':' + SOURCE], cwd=inputs.ROOT,
            env=os.environ | {'GIT_NO_LAZY_FETCH': '1'})
        self.assertEqual(raw, actual)

    def test_no_current_source_read_or_fallback(self):
        with patch.object(Path, 'read_bytes', side_effect=AssertionError('Current file read forbidden')):
            self.assertEqual(len(inputs.historical_bytes(SOURCE)), 128874)
        inputs._verified_source.cache_clear()
        with patch.object(inputs._objects, 'object_bytes', side_effect=inputs._objects.MissingHistoricalObject('Missing actual Git input')):
            with self.assertRaises(inputs._objects.MissingHistoricalObject):
                inputs.historical_bytes(SOURCE)

    def test_each_actual_git_object_kind_is_verified_before_use(self):
        original = inputs._objects.git
        for selected in ('commit', 'tree', 'blob'):
            inputs._verified_source.cache_clear()
            hits = []
            def corrupted(root, *parts):
                result = original(root, *parts)
                if parts[:2] == ('cat-file', selected) and result.returncode == 0:
                    hits.append(parts[-1])
                    return subprocess.CompletedProcess(result.args, 0, result.stdout + b'\n', result.stderr)
                return result
            with self.subTest(object=selected), patch.object(inputs._objects, 'git', side_effect=corrupted), self.assertRaises(RuntimeError):
                inputs.historical_bytes(SOURCE)
            self.assertTrue(hits)

    def test_fixed_commit_must_own_fixed_tree(self):
        with patch.object(inputs, 'TREE', '0'*40), self.assertRaisesRegex(ValueError, 'does not own'):
            inputs.historical_bytes(SOURCE)

    def test_noncanonical_or_unowned_paths_are_rejected_before_git(self):
        invalid = (None, b'app/x', Path('app/x'), '', 'app', '/app/x', '../app/x',
                   'app/../tests/x', 'app//x', './app/x', 'app/./x', 'app/x/',
                   '.git/config', 'unknown/x', 'app/x\0tail', 'app/' + 'x'*241)
        with patch.object(inputs._objects, 'object_bytes', side_effect=AssertionError('Git must not be read')):
            for relative in invalid:
                with self.subTest(path=relative), self.assertRaises(ValueError):
                    inputs.historical_bytes(relative)

    def test_path_modes_reject_links_directories_and_non_tree_parents(self):
        original = inputs._objects.entry
        for component, changed_mode in (('GeckoWebView.java', '120000'),
                                        ('GeckoWebView.java', '40000'), ('app', '100644')):
            inputs._verified_source.cache_clear()
            def changed(raw, part):
                mode, identity = original(raw, part)
                return (changed_mode if part == component else mode), identity
            with self.subTest(component=component, mode=changed_mode), patch.object(inputs._objects, 'entry', side_effect=changed), self.assertRaises(ValueError):
                inputs.historical_bytes(SOURCE)

    def test_exact_source_size_bound_is_enforced(self):
        with patch.object(inputs, 'MAX_BYTES', 1), self.assertRaisesRegex(ValueError, 'bound'):
            inputs.historical_bytes(SOURCE)

    def test_verified_cache_has_immutable_bytes_and_copied_provenance(self):
        raw = inputs.historical_bytes(SOURCE)
        identity = inputs.historical_identity(SOURCE)
        identity.update(commit='0'*40, historicalProofOnly=False)
        with patch.object(inputs._objects, 'object_bytes', side_effect=AssertionError('Verified immutable cache expected')):
            self.assertIs(inputs.historical_bytes(SOURCE), raw)
            self.assertEqual(inputs.historical_identity(SOURCE)['commit'], inputs.COMMIT)
            self.assertTrue(inputs.historical_identity(SOURCE)['historicalProofOnly'])


if __name__ == '__main__':
    unittest.main()
