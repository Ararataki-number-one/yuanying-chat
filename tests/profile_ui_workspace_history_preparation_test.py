"""Real shallow Git controls for the fixed UI history setup supplement.

CI-shaped dictionaries below are controlled authorization inputs only. Fetch
transport is redirected to this local repository; no actual CI identity, public
network request, original oracle substitution, Android or signing is claimed.
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zlib


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/browser'))
import prepare_ui_workspace_history as workspace

history = workspace.history


class UiWorkspaceHistoryPreparationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='ui-history-setup-')
        self.addCleanup(self.temporary.cleanup)
        self.repo = Path(self.temporary.name) / 'repo'
        self.repo.mkdir()
        self.real = history.git
        self.fetches = []
        self.git_run('init', '-q')
        self.git_run('config', 'user.name', 'UI history source control')
        self.git_run('config', 'user.email', 'ui-history-control@example.invalid')
        (self.repo / 'anchor.txt').write_text('current source remains unchanged\n')
        self.git_run('add', 'anchor.txt')
        self.git_run('commit', '-qm', 'Independent current source fixture')
        self.git_run('remote', 'add', 'origin', history.ORIGINS[0])
        target = self.repo / workspace.MANIFEST
        target.parent.mkdir(parents=True)
        target.write_bytes((ROOT / workspace.MANIFEST).read_bytes())
        self.head = self.git_run('rev-parse', 'HEAD').decode().strip()
        self.controlled_environment = dict(
            CI='true', GITHUB_ACTIONS='true', GITHUB_SERVER_URL='https://github.com',
            GITHUB_REPOSITORY=history.REPOSITORY, GITHUB_RUN_ID='123',
            GITHUB_RUN_ATTEMPT='1', GITHUB_SHA=self.head)

    def git_run(self, *args, input=None):
        return subprocess.run(['git', '--no-replace-objects', *args], cwd=self.repo,
                              capture_output=True, check=True, input=input,
                              env=dict(os.environ, GIT_NO_LAZY_FETCH='1')).stdout

    def seed(self, commit):
        self.git_run('fetch', '--no-tags', '--depth=1', '--no-write-fetch-head', str(ROOT), commit)

    def transport(self, root, *args):
        if args[:1] == ('fetch',):
            self.assertEqual(args[:5], ('fetch', '--no-tags', '--depth=1', '--no-write-fetch-head', 'origin'))
            self.assertEqual(len(args), 6)
            self.assertIn(args[5], {group['commit'] for group in workspace.manifest(root)})
            self.fetches.append(args)
            # Only the fetch destination changes. The unchanged verifier reads
            # actual Git commit/tree/blob bytes after the local transport.
            return self.real(root, *args[:4], str(ROOT), args[5])
        return self.real(root, *args)

    def prepare(self, environment=None, transport=None):
        with patch.object(history, 'git', side_effect=transport or self.transport):
            return workspace.prepare_ui_workspace_history(
                self.repo, self.controlled_environment if environment is None else environment)

    def test_both_missing_owners_restore_real_shallow_objects_and_preserve_checkout(self):
        groups = workspace.manifest(self.repo)
        for group in groups:
            self.assertNotEqual(history.git(self.repo, 'cat-file', '-e', group['commit']).returncode, 0)
        before = history.checkout_state(self.repo)
        report = self.prepare()
        self.assertEqual(report['status'], 'passed')
        self.assertTrue(report['checkoutUnchanged'])
        self.assertEqual(history.checkout_state(self.repo), before)
        self.assertEqual(self.git_run('rev-parse', 'HEAD').decode().strip(), self.head)
        self.assertTrue((self.repo / '.git/shallow').is_file())
        self.assertFalse((self.repo / '.git/FETCH_HEAD').exists())
        self.assertEqual(report['fetchedCommits'], [group['commit'] for group in groups])
        self.assertEqual(len(self.fetches), 2)
        self.assertEqual([len(group['files']) for group in report['groups']], [13, 10])
        for expected, actual in zip(groups, report['groups']):
            self.assertEqual(history.verify_group(self.repo, expected), actual)
        self.assertFalse(report['testsExecuted'])
        self.assertFalse(report['actualAndroidExecution'])

    def test_ready_objects_are_readonly_without_ci_identity_even_with_local_changes(self):
        for group in workspace.manifest(self.repo):
            self.seed(group['commit'])
        (self.repo / 'anchor.txt').write_text('Unrelated existing local change\n')
        before = history.checkout_state(self.repo)
        report = self.prepare({})
        self.assertEqual(report['fetchedCommits'], [])
        self.assertEqual(self.fetches, [])
        self.assertEqual(history.checkout_state(self.repo), before)

    def test_missing_objects_require_original_repository_source_and_ci_authorization(self):
        cases = [('CI', 'false'), ('GITHUB_ACTIONS', 'false'),
                 ('GITHUB_SERVER_URL', 'https://example.invalid'),
                 ('GITHUB_REPOSITORY', 'foreign/repository'), ('GITHUB_SHA', 'f' * 40),
                 ('GITHUB_RUN_ID', '0'), ('GITHUB_RUN_ATTEMPT', 'not-a-number')]
        for key, value in cases:
            environment = dict(self.controlled_environment)
            environment[key] = value
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                self.prepare(environment)
        with self.assertRaises(RuntimeError):
            self.prepare({})
        self.git_run('remote', 'set-url', 'origin', 'https://example.invalid/foreign/repository')
        with self.assertRaises(RuntimeError):
            self.prepare()
        self.assertEqual(self.fetches, [])

    def test_missing_objects_cannot_fetch_with_dirty_tracked_source(self):
        (self.repo / 'anchor.txt').write_text('Existing unrelated source edit\n')
        with self.assertRaises(RuntimeError):
            self.prepare()
        self.assertEqual(self.fetches, [])

    def test_changed_missing_and_symlink_manifests_fail_before_fetch(self):
        path = self.repo / workspace.MANIFEST
        raw = path.read_bytes()
        path.write_bytes(raw + b'\n')
        with self.assertRaises(RuntimeError):
            self.prepare()
        path.unlink()
        with self.assertRaises(RuntimeError):
            self.prepare()
        target = self.repo / 'different.json'
        target.write_bytes(raw)
        path.symlink_to(target)
        with self.assertRaises(RuntimeError):
            self.prepare()
        self.assertEqual(self.fetches, [])

    def test_successful_transport_without_actual_objects_is_rejected(self):
        def incomplete(root, *args):
            if args[:1] == ('fetch',):
                return subprocess.CompletedProcess(args, 0, b'', b'')
            return self.real(root, *args)
        with self.assertRaises(history.MissingHistoricalObject):
            self.prepare(transport=incomplete)

    def assert_mutation_rejected(self, mutate):
        def mutation(root, *args):
            result = self.transport(root, *args)
            if args[:1] == ('fetch',):
                mutate()
            return result
        with self.assertRaisesRegex(RuntimeError, 'changed HEAD, index or tracked bytes'):
            self.prepare(transport=mutation)
        self.assertEqual(len(self.fetches), 1)

    def test_actual_tracked_bytes_mutation_during_fetch_is_rejected(self):
        self.assert_mutation_rejected(lambda: (self.repo / 'anchor.txt').write_text('changed source\n'))

    def test_actual_index_mutation_during_fetch_is_rejected(self):
        blob = self.git_run('hash-object', '-w', '--stdin', input=b'index-only change\n').decode().strip()
        self.assert_mutation_rejected(
            lambda: self.git_run('update-index', '--cacheinfo', '100644,' + blob + ',anchor.txt'))

    def test_actual_head_mutation_during_fetch_is_rejected(self):
        tree = self.git_run('rev-parse', 'HEAD^{tree}').decode().strip()
        other = self.git_run('commit-tree', tree, '-p', self.head, input=b'Changed HEAD control\n').decode().strip()
        self.assert_mutation_rejected(lambda: self.git_run('update-ref', 'HEAD', other))

    def test_actual_counterfeit_blob_bytes_are_rejected_without_fetch_fallback(self):
        group = workspace.manifest(self.repo)[0]
        objects = {('commit', group['commit']), ('tree', group['tree'])}
        for name, pin in group['files'].items():
            objects.add(('blob', pin['blob']))
            parts = name.split('/')
            for length in range(1, len(parts)):
                identity = history.checked(
                    ROOT, 'rev-parse', group['commit'] + ':' + '/'.join(parts[:length])).decode().strip()
                objects.add(('tree', identity))
        # Start with canonical loose objects in the independent empty fixture.
        # An existing pack must not hide the intentionally corrupted loose blob.
        for kind, identity in sorted(objects):
            raw = history.object_bytes(ROOT, kind, identity)
            written = self.git_run('hash-object', '-t', kind, '-w', '--stdin', input=raw).decode().strip()
            self.assertEqual(written, identity)
        self.assertEqual(history.verify_group(self.repo, group)['commit'], group['commit'])
        self.assertEqual(list((self.repo / '.git/objects/pack').glob('*.pack')), [])
        blob = next(iter(group['files'].values()))['blob']
        changed = self.git_run('cat-file', 'blob', blob) + b'counterfeit control bytes\n'
        target = self.repo / '.git/objects' / blob[:2] / blob[2:]
        target.parent.mkdir(parents=True, exist_ok=True)
        # Git writes canonical loose objects read-only; remove only this owned
        # temporary fault target so the same control also runs as a non-root user.
        target.unlink()
        target.write_bytes(zlib.compress(b'blob ' + str(len(changed)).encode() + b'\0' + changed))
        self.assertEqual(self.git_run('cat-file', 'blob', blob), changed)
        with self.assertRaisesRegex(RuntimeError, 'actual Git object identity differs'):
            self.prepare()
        self.assertEqual(self.fetches, [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
