"""Host setup authorization and real Git-object invariants; never device evidence."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('tested_profile_host_prerequisites',
    ROOT / 'tools/gecko/prepare_profile_host_prerequisites.py')
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


class ProfileHostPrerequisitesTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(prefix='profile-history-controls-')
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.git('init', '-q')
        self.git('config', 'user.email', 'synthetic@example.invalid')
        self.git('config', 'user.name', 'Synthetic host setup control')
        self.git('remote', 'add', 'origin', setup.history.ORIGINS[1])
        raw = b'Fixed test payload, never an application oracle.\n'
        (self.root / 'proof.txt').write_bytes(raw)
        self.git('add', 'proof.txt')
        self.git('commit', '-q', '-m', 'Synthetic host setup checkout')
        self.source = self.git('rev-parse', 'HEAD').strip().decode()
        tree = self.git('rev-parse', 'HEAD^{tree}').strip().decode()
        blob = self.git('rev-parse', 'HEAD:proof.txt').strip().decode()
        self.groups = []
        for index in range(21):
            owner = self.git('commit-tree', tree, '-m', 'Immutable setup owner ' + str(index)).strip().decode()
            self.groups.append(dict(commit=owner, tree=tree, files={'proof.txt':
                dict(mode='100644', blob=blob, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())}))
        self.event = dict(repository=dict(full_name=setup.history.REPOSITORY), number=5,
            pull_request=dict(head=dict(sha=self.source), base=dict(repo=dict(full_name=setup.history.REPOSITORY))))
        self.event_path = self.root / 'event.json'
        self.write_event()
        self.environment = dict(CI='true', GITHUB_ACTIONS='true', GITHUB_SERVER_URL='https://github.com',
            GITHUB_REPOSITORY=setup.history.REPOSITORY, GITHUB_RUN_ID='123', GITHUB_RUN_ATTEMPT='1',
            GITHUB_SHA='f' * 40, GITHUB_EVENT_NAME='pull_request', GITHUB_REF='refs/pull/5/merge',
            GITHUB_EVENT_PATH=str(self.event_path))

    def git(self, *parts):
        return subprocess.check_output(['git', *parts], cwd=self.root, stderr=subprocess.PIPE)

    def write_event(self):
        self.event_path.write_text(json.dumps(self.event))

    def prepare(self, **kwargs):
        with patch.object(setup.history, 'manifest', return_value=self.groups):
            return setup.prepare_history(self.root, source_commit=kwargs.pop('source_commit', self.source),
                environment=kwargs.pop('environment', self.environment), **kwargs)

    def test_all_real_owner_tree_blob_bytes_verify_offline_without_ci(self):
        before = setup.history.checkout_state(self.root)
        with patch.object(setup, 'authorize_fetch', side_effect=AssertionError('offline verification contacted CI')):
            result = self.prepare(environment={})
        self.assertEqual(len(result['groups']), 21)
        self.assertEqual(result['fetchedCommits'], [])
        self.assertEqual(before, setup.history.checkout_state(self.root))
        self.assertFalse(result['testsExecuted'])

    def test_pr_head_is_authorized_while_workflow_merge_sha_stays_unchanged(self):
        original = dict(self.environment)
        setup.authorize_fetch(self.root, self.source, self.environment)
        self.assertNotEqual(self.source, self.environment['GITHUB_SHA'])
        self.assertEqual(self.environment, original)

    def test_wrong_ci_repository_run_or_event_kind_is_rejected(self):
        for key, value in [('GITHUB_REPOSITORY', 'foreign/repository'), ('CI', 'false'),
                ('GITHUB_RUN_ID', '0'), ('GITHUB_RUN_ATTEMPT', '1;command'),
                ('GITHUB_SERVER_URL', 'https://foreign.invalid'), ('GITHUB_EVENT_NAME', 'pull_request_target')]:
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                setup.authorize_fetch(self.root, self.source, dict(self.environment, **{key: value}))

    def test_wrong_event_repository_head_base_or_number_is_rejected(self):
        original = copy.deepcopy(self.event)
        changes = [('repo', lambda e: e['repository'].update(full_name='foreign/repository')),
            ('head', lambda e: e['pull_request']['head'].update(sha='a' * 40)),
            ('base', lambda e: e['pull_request']['base']['repo'].update(full_name='foreign/repository')),
            ('number', lambda e: e.update(number=6))]
        for name, change in changes:
            self.event = copy.deepcopy(original)
            change(self.event)
            self.write_event()
            with self.subTest(name=name), self.assertRaises(RuntimeError):
                setup.authorize_fetch(self.root, self.source, self.environment)

    def test_wrong_source_or_foreign_origin_cannot_fetch(self):
        with self.assertRaisesRegex(RuntimeError, 'requested source differs'):
            self.prepare(source_commit='a' * 40)
        self.git('remote', 'set-url', 'origin', 'https://github.com/foreign/repository.git')
        with self.assertRaisesRegex(RuntimeError, 'fixed public GitHub origin'):
            setup.authorize_fetch(self.root, self.source, self.environment)

    def test_event_symlink_or_incomplete_pr_metadata_is_rejected(self):
        link = self.root / 'linked-event.json'
        link.symlink_to(self.event_path)
        with self.assertRaisesRegex(RuntimeError, 'bounded actual GitHub event'):
            setup.authorize_fetch(self.root, self.source, dict(self.environment, GITHUB_EVENT_PATH=str(link)))
        self.event.pop('pull_request')
        self.write_event()
        with self.assertRaisesRegex(RuntimeError, 'actual pull request event'):
            setup.authorize_fetch(self.root, self.source, self.environment)

    def test_push_and_dispatch_bind_source_and_ref(self):
        self.event = dict(repository=dict(full_name=setup.history.REPOSITORY),
            after=self.source, ref='refs/heads/reviewed')
        self.write_event()
        environment = dict(self.environment, GITHUB_SHA=self.source, GITHUB_EVENT_NAME='push', GITHUB_REF=self.event['ref'])
        setup.authorize_fetch(self.root, self.source, environment)
        self.event['after'] = 'a' * 40
        self.write_event()
        with self.assertRaisesRegex(RuntimeError, 'push source or ref'):
            setup.authorize_fetch(self.root, self.source, environment)
        for ref in ('reviewed', 'refs/heads/reviewed'):
            self.event['ref'] = ref
            self.write_event()
            setup.authorize_fetch(self.root, self.source, dict(environment, GITHUB_EVENT_NAME='workflow_dispatch'))
        with self.assertRaisesRegex(RuntimeError, 'dispatch source or ref'):
            setup.authorize_fetch(self.root, self.source, dict(environment,
                GITHUB_EVENT_NAME='workflow_dispatch', GITHUB_SHA='a' * 40))

    def test_real_wrong_owner_tree_blob_and_bytes_fail_closed(self):
        for key, value in [('tree', 'a' * 40), ('blob', 'a' * 40), ('bytes', 1), ('sha256', 'a' * 64)]:
            group = copy.deepcopy(self.groups[0])
            (group if key == 'tree' else group['files']['proof.txt'])[key] = value
            with self.subTest(pin=key), self.assertRaises(RuntimeError):
                setup.history.verify_group(self.root, group)
        # A real foreign owner with another tree cannot borrow this group's pins.
        self.git('add', 'event.json')
        foreign_tree = self.git('write-tree').strip().decode()
        group = copy.deepcopy(self.groups[0])
        group['commit'] = self.git('commit-tree', foreign_tree, '-m', 'Foreign owner control').strip().decode()
        with self.assertRaisesRegex(RuntimeError, 'fixed commit does not own the fixed tree'):
            setup.history.verify_group(self.root, group)

    def test_changed_fixed_inventory_bytes_are_rejected(self):
        path = self.root / setup.history.MANIFEST
        path.parent.mkdir(parents=True)
        path.write_bytes((ROOT / setup.history.MANIFEST).read_bytes() + b'\n')
        with self.assertRaisesRegex(RuntimeError, 'fixed dependency manifest bytes differ'):
            setup.history.manifest(self.root)

    def run_missing(self, fetch):
        real_verify, real_checked = setup.history.verify_group, setup.history.checked
        self.missing = True
        def verify(root, group):
            if self.missing and group['commit'] == self.groups[0]['commit']:
                raise setup.history.MissingHistoricalObject('Declared missing control')
            return real_verify(root, group)
        def checked(root, *parts):
            if parts[0] == 'fetch':
                self.assertEqual(parts, ('fetch', '--no-tags', '--depth=1', '--no-write-fetch-head',
                    '--no-filter', 'origin', self.groups[0]['commit']))
                return fetch()
            return real_checked(root, *parts)
        with patch.object(setup.history, 'verify_group', side_effect=verify), patch.object(setup.history, 'checked', side_effect=checked):
            return self.prepare()

    def test_exact_missing_owner_fetch_is_verified_after_transport(self):
        def fetch():
            self.missing = False
            return b''
        result = self.run_missing(fetch)
        self.assertEqual(result['fetchedCommits'], [self.groups[0]['commit']])
        self.assertEqual(len(result['groups']), 21)

    def test_successful_transport_with_missing_payload_is_rejected(self):
        with self.assertRaises(setup.history.MissingHistoricalObject):
            self.run_missing(lambda: b'')

    def test_failed_transport_cannot_report_prepared_history(self):
        def fetch():
            raise RuntimeError('Declared Git transport failure')
        with self.assertRaisesRegex(RuntimeError, 'Declared Git transport failure'):
            self.run_missing(fetch)

    def test_fetch_that_changes_tracked_bytes_is_rejected(self):
        def fetch():
            self.missing = False
            (self.root / 'proof.txt').write_text('Changed tracked bytes during fetch\n')
            return b''
        with self.assertRaisesRegex(RuntimeError, 'history fetch changed HEAD, tree, index or tracked bytes'):
            self.run_missing(fetch)

    def test_dirty_checkout_cannot_authorize_a_network_fetch(self):
        (self.root / 'proof.txt').write_text('Local tracked modification\n')
        with self.assertRaisesRegex(RuntimeError, 'tracked checkout must be clean'):
            setup.authorize_fetch(self.root, self.source, self.environment)


if __name__ == '__main__':
    unittest.main(verbosity=2)
