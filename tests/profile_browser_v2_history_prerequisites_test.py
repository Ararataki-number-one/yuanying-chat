"""Real Git controls for the separately declared released-browser-v2 inputs.

Only the fetch destination is redirected to the local repository. The fixed
owner, tree, paths, blob bytes, event admission and checkout checks remain real.
CI-shaped events here do not represent an actual GitHub or Android execution.
"""
import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zlib

import profile_host_prerequisites_test as original

ROOT, setup = original.ROOT, original.setup


class BrowserV2HistoryPrerequisitesTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='browser-v2-history-host-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.git('init', '-q')
        self.git('config', 'user.name', 'Browser v2 prerequisite control')
        self.git('config', 'user.email', 'browser-v2-control@example.invalid')
        self.git('remote', 'add', 'origin', setup.history.ORIGINS[1])
        (self.root/'anchor.txt').write_text('Independent checkout for actual Git-object checks\n')
        self.git('add', 'anchor.txt')
        self.git('commit', '-qm', 'Independent browser v2 prerequisite checkout')
        self.source = self.git('rev-parse', 'HEAD').decode().strip()
        self.group = setup.BROWSER_V2_GROUP
        self.event = dict(repository=dict(full_name=setup.history.REPOSITORY), number=9,
            pull_request=dict(head=dict(sha=self.source), base=dict(repo=dict(full_name=setup.history.REPOSITORY))))
        self.event_path = self.root/'event.json'
        self.write_event()
        self.environment = dict(CI='true', GITHUB_ACTIONS='true', GITHUB_SERVER_URL='https://github.com',
            GITHUB_REPOSITORY=setup.history.REPOSITORY, GITHUB_RUN_ID='123', GITHUB_RUN_ATTEMPT='1',
            GITHUB_SHA='f'*40, GITHUB_EVENT_NAME='pull_request', GITHUB_REF='refs/pull/9/merge',
            GITHUB_EVENT_PATH=str(self.event_path))
        self.real_git = setup.history.git
        self.fetches = []

    def git(self, *arguments):
        return subprocess.run(['git', '--no-replace-objects', *arguments], cwd=self.root,
            capture_output=True, check=True, env=dict(os.environ, GIT_NO_LAZY_FETCH='1')).stdout

    def write_event(self):
        self.event_path.write_text(json.dumps(self.event))

    def transport(self, root, *arguments):
        if arguments[:1] == ('fetch',):
            self.assertEqual(arguments, ('fetch', '--refetch', '--no-tags', '--depth=1',
                '--no-write-fetch-head', '--no-filter', 'origin', self.group['commit']))
            self.fetches.append(arguments)
            return self.real_git(root, *arguments[:6], str(ROOT), *arguments[7:])
        return self.real_git(root, *arguments)

    def prepare(self, *, source=None, environment=None, transport=None):
        with patch.object(setup.history, 'git', side_effect=transport or self.transport):
            return setup.prepare_browser_v2_history(self.root,
                source_commit=self.source if source is None else source,
                environment=self.environment if environment is None else environment)

    def seed(self):
        self.git('fetch', '--refetch', '--no-tags', '--depth=1', '--no-write-fetch-head',
                 '--no-filter', str(ROOT), self.group['commit'])

    def test_missing_real_owner_restores_exact_six_blobs_without_changing_checkout_or_refs(self):
        with self.assertRaises(setup.history.MissingHistoricalObject):
            setup.history.verify_group(self.root, self.group)
        before = setup.history.checkout_state(self.root)
        refs = self.git('for-each-ref', '--format=%(refname) %(objectname)')
        environment = dict(self.environment)
        report = self.prepare()
        observed = setup.history.verify_group(self.root, self.group)
        self.assertEqual(report['group'], observed)
        self.assertEqual(len(observed['files']), 6)
        self.assertEqual(report['fetchedCommits'], [self.group['commit']])
        self.assertEqual(len(self.fetches), 1)
        self.assertEqual(report['sourceCommit'], self.source)
        self.assertEqual(report['sourceTree'], before['sourceTree'])
        self.assertEqual(self.environment, environment)
        self.assertNotEqual(self.environment['GITHUB_SHA'], self.source)
        self.assertEqual(before, setup.history.checkout_state(self.root))
        self.assertEqual(refs, self.git('for-each-ref', '--format=%(refname) %(objectname)'))
        self.assertFalse((self.root/'.git/FETCH_HEAD').exists())
        self.assertTrue((self.root/'.git/shallow').is_file())
        self.assertTrue(report['historicalProofOnly'])
        self.assertFalse(report['currentSourceReplacement'])
        self.assertFalse(report['testsExecuted'])
        self.assertFalse(report['actualAndroidExecution'])

    def test_present_real_owner_verifies_offline_with_existing_local_edit(self):
        self.seed()
        (self.root/'anchor.txt').write_text('Existing tracked user edit\n')
        before = setup.history.checkout_state(self.root)
        with patch.object(setup, 'authorize_fetch', side_effect=AssertionError('Present history must remain offline')):
            report = self.prepare(environment={})
        self.assertEqual(report['fetchedCommits'], [])
        self.assertEqual(self.fetches, [])
        self.assertEqual(before, setup.history.checkout_state(self.root))

    def test_actual_corrupted_loose_blob_is_rejected_without_fetching_a_replacement(self):
        self.seed()
        pin = self.group['files']['tests/gecko/run_chrome_collapse.py']
        blob = pin['blob']
        original_bytes = self.git('cat-file', 'blob', blob)
        altered = original_bytes+b'\n# counterfeit historical bytes\n'
        # Git may prefer a packed copy over an identically named loose object.
        # Unpack this disposable repository first so the real corrupted object
        # below is the only candidate for the verifier's exact cat-file read.
        for packed in (self.root/'.git/objects/pack').glob('*.pack'):
            raw_pack = packed.read_bytes()
            packed.unlink()
            packed.with_suffix('.idx').unlink()
            subprocess.run(['git', '--no-replace-objects', 'unpack-objects', '-r'],
                cwd=self.root, input=raw_pack, capture_output=True, check=True,
                env=dict(os.environ, GIT_NO_LAZY_FETCH='1'))
        # Its object name is deliberately false; the existing SHA-1 byte check
        # must reject without treating the corrupted bytes as missing history.
        path = self.root/'.git/objects'/blob[:2]/blob[2:]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.unlink(missing_ok=True)
        path.write_bytes(zlib.compress(b'blob '+str(len(altered)).encode()+b'\0'+altered))
        before = setup.history.checkout_state(self.root)
        with self.assertRaisesRegex(RuntimeError, 'actual Git object identity differs'):
            self.prepare(environment={})
        self.assertEqual(self.fetches, [])
        self.assertEqual(before, setup.history.checkout_state(self.root))

    def test_checkout_change_during_real_fetch_cannot_report_prepared_history(self):
        def changed(root, *arguments):
            result = self.transport(root, *arguments)
            if arguments[:1] == ('fetch',):
                (self.root/'anchor.txt').write_text('Changed while actual objects arrived\n')
            return result
        with self.assertRaisesRegex(RuntimeError, 'v2 history fetch changed checkout'):
            self.prepare(transport=changed)
        self.assertEqual(len(self.fetches), 1)
        self.assertEqual(self.git('rev-parse', 'HEAD').decode().strip(), self.source)

    def test_wrong_source_event_origin_or_dirty_checkout_rejects_before_fetch(self):
        with self.assertRaisesRegex(RuntimeError, 'v2 history source differs'):
            self.prepare(source='a'*40)
        for environment in ({}, dict(self.environment, GITHUB_RUN_ID='0')):
            with self.subTest(environment=environment.get('GITHUB_RUN_ID')), self.assertRaises(RuntimeError):
                self.prepare(environment=environment)
        expected_event = copy.deepcopy(self.event)
        for kind in ('head', 'base'):
            self.event = copy.deepcopy(expected_event)
            if kind == 'head':
                self.event['pull_request']['head']['sha'] = 'a'*40
            else:
                self.event['pull_request']['base']['repo']['full_name'] = 'foreign/repository'
            self.write_event()
            with self.subTest(kind=kind), self.assertRaisesRegex(RuntimeError, 'head or base repository differs'):
                self.prepare()
        self.event = expected_event
        self.write_event()
        self.git('remote', 'set-url', 'origin', 'https://github.com/foreign/repository.git')
        with self.assertRaisesRegex(RuntimeError, 'fixed public GitHub origin'):
            self.prepare()
        self.git('remote', 'set-url', 'origin', setup.history.ORIGINS[1])
        (self.root/'anchor.txt').write_text('Dirty before fetch\n')
        with self.assertRaisesRegex(RuntimeError, 'tracked checkout must be clean'):
            self.prepare()
        self.assertEqual(self.fetches, [])

    def test_failed_or_incomplete_transport_never_reports_success(self):
        for returncode in (1, 0):
            def incomplete(root, *arguments):
                if arguments[:1] == ('fetch',):
                    return subprocess.CompletedProcess(arguments, returncode, b'', b'Controlled transport outcome')
                return self.real_git(root, *arguments)
            before = setup.history.checkout_state(self.root)
            with self.subTest(returncode=returncode), self.assertRaises(RuntimeError):
                self.prepare(transport=incomplete)
            self.assertEqual(before, setup.history.checkout_state(self.root))


if __name__ == '__main__':
    unittest.main(verbosity=2)
