"""Real shallow Git prerequisites for the two fixed glass source-history groups."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('tested_glass_history_prerequisites',
    ROOT / 'tools/gecko/prepare_profile_host_prerequisites.py')
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)
EXTRA_MANIFEST = 'tests/baselines/glass-source-history.json'
FINAL = 'tests/final_browser_source_compatibility.py'
PUBLIC_FILES = {
    '.github/workflows/browser-2_1-acceptance.yml',
    '.github/workflows/profile-upgrade-checks.yml',
    '.github/workflows/glass-release-validation.yml',
    FINAL,
    'tests/profile_fixture_root_source_compatibility.py',
    'tests/profile_final_browser_source_compatibility_test.py',
    'tests/fixtures/profile-fixture-root-source-deltas.json',
    'tests/fixtures/resource-startup-source-deltas.json',
    'tests/fixtures/final-browser-source-deltas.json',
    'app/src/main/java/local/pocketchat/ProfileContext.java',
    'app/src/main/java/local/pocketchat/GeckoWebView.java',
}


class GlassHistoryPrerequisitesTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(prefix='glass-shallow-history-')
        self.addCleanup(self.folder.cleanup)
        self.base = Path(self.folder.name)
        self.upstream = self.base / 'upstream'
        self.upstream.mkdir()
        self.git_at(self.upstream, 'init', '-q', '-b', 'main')
        self.git_at(self.upstream, 'config', 'user.email', 'synthetic@example.invalid')
        self.git_at(self.upstream, 'config', 'user.name', 'Synthetic glass prerequisite control')
        self.groups = []
        for index in range(2):
            raw = ('Immutable declared historical payload ' + str(index) + '\n').encode()
            (self.upstream / 'proof.txt').write_bytes(raw)
            self.git_at(self.upstream, 'add', 'proof.txt')
            self.git_at(self.upstream, 'commit', '-q', '-m', 'Historical owner ' + str(index))
            owner = self.git_at(self.upstream, 'rev-parse', 'HEAD').decode().strip()
            tree = self.git_at(self.upstream, 'rev-parse', 'HEAD^{tree}').decode().strip()
            blob = self.git_at(self.upstream, 'rev-parse', 'HEAD:proof.txt').decode().strip()
            self.groups.append(dict(commit=owner, tree=tree, files={'proof.txt': dict(
                mode='100644', blob=blob, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())}))
        (self.upstream / 'proof.txt').write_bytes(b'Actual shallow checkout payload\n')
        self.git_at(self.upstream, 'add', 'proof.txt')
        self.git_at(self.upstream, 'commit', '-q', '-m', 'Current shallow checkout')
        self.remote = self.base / 'remote.git'
        self.git_at(self.base, 'clone', '-q', '--bare', str(self.upstream), str(self.remote))
        self.root = self.base / 'checkout'
        self.git_at(self.base, 'clone', '-q', '--depth=1', self.remote.as_uri(), str(self.root))
        self.git('remote', 'set-url', 'origin', setup.history.ORIGINS[1])
        self.source = self.git('rev-parse', 'HEAD').decode().strip()
        self.event_path = self.root / 'event.json'
        self.event_path.write_text(json.dumps(dict(repository=dict(full_name=setup.history.REPOSITORY),
            number=5, pull_request=dict(head=dict(sha=self.source),
                base=dict(repo=dict(full_name=setup.history.REPOSITORY))))))
        self.environment = dict(CI='true', GITHUB_ACTIONS='true', GITHUB_SERVER_URL='https://github.com',
            GITHUB_REPOSITORY=setup.history.REPOSITORY, GITHUB_RUN_ID='123', GITHUB_RUN_ATTEMPT='1',
            GITHUB_SHA='f' * 40, GITHUB_EVENT_NAME='pull_request', GITHUB_REF='refs/pull/5/merge',
            GITHUB_EVENT_PATH=str(self.event_path))

    def git_at(self, root, *parts):
        return subprocess.check_output(['git', '--no-replace-objects', *parts], cwd=root,
            stderr=subprocess.PIPE, env=dict(os.environ, GIT_NO_LAZY_FETCH='1', GIT_TERMINAL_PROMPT='0'))

    def git(self, *parts):
        return self.git_at(self.root, *parts)

    def fetch_local(self, owners):
        return self.git('fetch', '--no-tags', '--depth=1', '--no-write-fetch-head', '--no-filter',
                        self.remote.as_uri(), *owners)

    def prepare(self, *, environment=None):
        with patch.object(setup, 'additional_manifest', return_value=self.groups):
            return setup.prepare_additional_history(self.root, source_commit=self.source,
                environment=self.environment if environment is None else environment)

    def with_transport(self, missing, transport):
        real_checked = setup.history.checked
        calls = []
        def checked(root, *parts):
            if parts[0] == 'fetch':
                self.assertEqual(Path(root), self.root)
                self.assertEqual(parts, ('fetch', '--no-tags', '--depth=1', '--no-write-fetch-head',
                    '--no-filter', 'origin', *missing))
                calls.append(parts)
                return transport(missing)
            return real_checked(root, *parts)
        with patch.object(setup.history, 'checked', side_effect=checked):
            result = self.prepare()
        self.assertEqual(len(calls), 1)
        return result

    def test_fixed_two_group_inventory_and_all_real_object_pins(self):
        groups = setup.additional_manifest(ROOT)
        self.assertEqual(groups, json.loads((ROOT / EXTRA_MANIFEST).read_bytes())['groups'])
        self.assertEqual(len(groups), 2)
        expected = {
            '6ee06aced87581e52aa301431f8996ed46d666b8': ('19b74a878d2c238cdb209dd51d2fb66076057963', {FINAL}),
            '7402ead321ca74b9fbefeab32a1aaffb32832011': ('2aaec06687b65d9511ace499528b6946dc1b8d53', PUBLIC_FILES),
        }
        self.assertEqual({group['commit'] for group in groups}, set(expected))
        for group in groups:
            tree, paths = expected[group['commit']]
            self.assertEqual((group['tree'], set(group['files'])), (tree, paths))
            observed = setup.history.verify_group(ROOT, group)
            self.assertEqual(len(observed['files']), len(paths))
        self.assertEqual(sum(len(group['files']) for group in groups), 12)
        legacy = ROOT / setup.history.MANIFEST
        self.assertEqual(hashlib.sha256(legacy.read_bytes()).hexdigest(),
                         '52831c72831c3d1ed43ae040efeef9436fb9b71ba78aa5a8ec6f0b4e3be6e745')
        self.assertEqual(len(setup.history.manifest(ROOT)), 21)

    def test_exact_groups_verify_offline_without_fetch_or_ci(self):
        self.fetch_local([group['commit'] for group in self.groups])
        before = setup.history.checkout_state(self.root)
        with patch.object(setup, 'authorize_fetch', side_effect=AssertionError('Offline objects requested network')):
            result = self.prepare(environment={})
        self.assertEqual(result['fetchedCommits'], [])
        self.assertEqual(len(result['groups']), 2)
        self.assertTrue(result['checkoutUnchanged'])
        self.assertFalse(result['testsExecuted'])
        self.assertEqual(setup.history.checkout_state(self.root), before)

    def test_real_depth_one_checkout_fetches_only_the_missing_exact_owner(self):
        self.assertEqual(self.git('rev-parse', '--is-shallow-repository').strip(), b'true')
        self.fetch_local([self.groups[0]['commit']])
        setup.history.verify_group(self.root, self.groups[0])
        with self.assertRaises(setup.history.MissingHistoricalObject):
            setup.history.verify_group(self.root, self.groups[1])
        before = setup.history.checkout_state(self.root)
        missing = [self.groups[1]['commit']]
        result = self.with_transport(missing, self.fetch_local)
        self.assertEqual(result['fetchedCommits'], missing)
        self.assertEqual(len(result['groups']), 2)
        self.assertEqual(setup.history.checkout_state(self.root), before)
        for group in self.groups:
            setup.history.verify_group(self.root, group)
            raw = self.git('show', group['commit'] + ':proof.txt')
            self.assertEqual(hashlib.sha256(raw).hexdigest(), group['files']['proof.txt']['sha256'])

    def test_transport_success_without_objects_is_rejected(self):
        missing = [group['commit'] for group in self.groups]
        with self.assertRaises(setup.history.MissingHistoricalObject):
            self.with_transport(missing, lambda owners: b'')

    def test_transport_failure_cannot_report_prepared_history(self):
        def failure(owners):
            raise RuntimeError('Declared additional-history transport failure')
        missing = [group['commit'] for group in self.groups]
        with self.assertRaisesRegex(RuntimeError, 'Declared additional-history transport failure'):
            self.with_transport(missing, failure)

    def test_fetch_that_changes_tracked_bytes_is_rejected(self):
        def polluted(owners):
            self.fetch_local(owners)
            (self.root / 'proof.txt').write_bytes(b'Changed tracked checkout during transport\n')
            return b''
        missing = [group['commit'] for group in self.groups]
        with self.assertRaisesRegex(RuntimeError, 'changed HEAD|checkout|tracked'):
            self.with_transport(missing, polluted)

    def test_dirty_checkout_cannot_authorize_additional_history_fetch(self):
        (self.root / 'proof.txt').write_bytes(b'Existing tracked modification\n')
        with self.assertRaisesRegex(RuntimeError, 'tracked checkout must be clean'):
            self.prepare()

    def test_altered_duplicate_foreign_or_symlink_inventory_is_rejected(self):
        original = (ROOT / EXTRA_MANIFEST).read_bytes()
        path = self.root / EXTRA_MANIFEST
        path.parent.mkdir(parents=True)
        path.write_bytes(original)
        self.assertEqual(setup.additional_manifest(self.root), setup.additional_manifest(ROOT))
        value = json.loads(original)
        duplicate = copy.deepcopy(value)
        duplicate['groups'].append(copy.deepcopy(duplicate['groups'][0]))
        foreign = copy.deepcopy(value)
        foreign['groups'][0]['commit'] = 'a' * 40
        for candidate in (original + b'\n', b'{"schema":1,"schema":1}',
                          json.dumps(duplicate).encode(), json.dumps(foreign).encode(), b'x' * (256 * 1024 + 1)):
            path.write_bytes(candidate)
            with self.assertRaises(RuntimeError):setup.additional_manifest(self.root)
        path.unlink()
        actual = self.root / 'actual-manifest.json'
        actual.write_bytes(original)
        path.symlink_to(actual)
        with self.assertRaises(RuntimeError):setup.additional_manifest(self.root)

    def test_main_preserves_original_receipt_and_prepares_additional_history_in_order(self):
        legacy = dict(schema=1, status='passed', sourceCommit=self.source,
            sourceTree=self.git('rev-parse', 'HEAD^{tree}').decode().strip(),
            manifestSha256=setup.history.MANIFEST_SHA256,
            groups=[dict(commit=group['commit']) for group in setup.history.manifest(ROOT)],
            fetchedCommits=[], checkoutUnchanged=True, testsExecuted=False, actualAndroidExecution=False)
        original = copy.deepcopy(legacy)
        additional = dict(schema=1, status='passed', sourceCommit=self.source,
            sourceTree=legacy['sourceTree'], manifestSha256=setup.ADDITIONAL_MANIFEST_SHA256,
            groups=copy.deepcopy(self.groups), fetchedCommits=[self.groups[1]['commit']],
            checkoutUnchanged=True, testsExecuted=False, actualAndroidExecution=False)
        calls = []
        def prepare_original(root, *, source_commit):
            self.assertEqual((root, source_commit), (self.root, self.source))
            calls.append('original21')
            return legacy
        def prepare_additional(root, *, source_commit):
            self.assertEqual((root, source_commit), (self.root, self.source))
            calls.append('additional2')
            return additional
        output = self.base / 'main-output' / 'prerequisites.json'
        argv = ['prepare_profile_host_prerequisites.py', '--source-commit', self.source,
                '--root', str(self.root), '--output', str(output)]
        with patch.object(setup, 'prepare_history', side_effect=prepare_original), \
                patch.object(setup, 'prepare_additional_history', side_effect=prepare_additional), \
                patch.object(setup, 'prepare_ui_history', return_value=dict(
                    schema=1, status='passed', groups=[dict(commit='4363dbc04df80d5c82ba966248e47a3fd69cbcc8')],
                    fetchedCommits=[], checkoutUnchanged=True, testsExecuted=False, actualAndroidExecution=False)), \
                patch.object(sys, 'argv', argv):
            setup.main()
        value = json.loads(output.read_bytes())
        self.assertEqual(calls, ['original21', 'additional2'])
        self.assertEqual(value['additionalHistory'], additional)
        self.assertEqual({key: item for key, item in value.items() if key not in ('additionalHistory', 'uiActivityHistory')}, original)
        self.assertEqual(len(value['groups']), 21)
        self.assertEqual(len(value['additionalHistory']['groups']), 2)


if __name__ == '__main__':
    unittest.main(verbosity=2)
