"""One fixed UI owner, fetched explicitly before historical Activity assertions."""
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import profile_glass_history_prerequisites_test as legacy

ROOT = Path(__file__).resolve().parents[1]
setup = legacy.setup
UI_MANIFEST = 'tests/baselines/ui-preparation-source-history.json'
ACTIVITY = 'tests/gecko/UiVisualIntegrationActivity.java'
OWNER = '4363dbc04df80d5c82ba966248e47a3fd69cbcc8'
TREE = '08189ae748eb1045ff21af4253369ef17d6bdad3'
BLOB = 'be0704e74cc2f106dc1c765c909cf17c33e6f0dc'
SHA256 = '04f629d6053d1fc62bdddd590c4b405ddff2d564fd4dc3211332c849da0a4366'


class UiPreparationHistoryPrerequisitesTests(unittest.TestCase):
    git_at = legacy.GlassHistoryPrerequisitesTests.git_at
    git = legacy.GlassHistoryPrerequisitesTests.git
    fetch_local = legacy.GlassHistoryPrerequisitesTests.fetch_local
    with_transport = legacy.GlassHistoryPrerequisitesTests.with_transport

    def setUp(self):
        # Reuse the real bare/depth-one transport controls, without inheriting
        # the old two-group tests or altering their inventory and assertions.
        legacy.GlassHistoryPrerequisitesTests.setUp(self)
        self.groups = self.groups[:1]

    def prepare(self, *, environment=None, source_commit=None):
        with patch.object(setup, 'ui_manifest', return_value=self.groups):
            return setup.prepare_ui_history(self.root,
                source_commit=self.source if source_commit is None else source_commit,
                environment=self.environment if environment is None else environment)

    def test_single_public_group_matches_actual_git_tree_blob_and_all_bytes(self):
        groups = setup.ui_manifest(ROOT)
        self.assertEqual(setup.UI_MANIFEST, UI_MANIFEST)
        self.assertEqual(groups, json.loads((ROOT / UI_MANIFEST).read_bytes())['groups'])
        self.assertEqual(len(groups), 1)
        group = groups[0]
        self.assertEqual((group['commit'], group['tree'], set(group['files'])), (OWNER, TREE, {ACTIVITY}))
        self.assertEqual(group['files'][ACTIVITY], dict(mode='100644', blob=BLOB, bytes=13373, sha256=SHA256))
        observed = setup.history.verify_group(ROOT, group)
        self.assertEqual(len(observed['files']), 1)
        before = self.git_at(ROOT, 'show', OWNER + ':' + ACTIVITY)
        self.assertEqual((len(before), hashlib.sha256(before).hexdigest()), (13373, SHA256))
        self.assertEqual(hashlib.sha256((ROOT / setup.history.MANIFEST).read_bytes()).hexdigest(),
                         '52831c72831c3d1ed43ae040efeef9436fb9b71ba78aa5a8ec6f0b4e3be6e745')
        self.assertEqual(len(setup.history.manifest(ROOT)), 21)
        self.assertEqual(len(setup.additional_manifest(ROOT)), 2)

    def test_existing_objects_verify_offline_without_fetch_or_ci(self):
        self.fetch_local([self.groups[0]['commit']])
        before = setup.history.checkout_state(self.root)
        with patch.object(setup, 'authorize_fetch', side_effect=AssertionError('Offline UI history requested network')):
            value = self.prepare(environment={})
        self.assertEqual(len(value['groups']), 1)
        self.assertEqual(value['fetchedCommits'], [])
        self.assertTrue(value['checkoutUnchanged'])
        self.assertFalse(value['testsExecuted'])
        self.assertEqual(setup.history.checkout_state(self.root), before)

    def test_real_depth_one_fetch_has_only_exact_missing_owner_and_keeps_checkout(self):
        self.assertEqual(self.git('rev-parse', '--is-shallow-repository').strip(), b'true')
        group = self.groups[0]
        with self.assertRaises(setup.history.MissingHistoricalObject):setup.history.verify_group(self.root, group)
        before = setup.history.checkout_state(self.root)
        tracked = (self.root / 'proof.txt').read_bytes()
        owners = [group['commit']]
        value = self.with_transport(owners, self.fetch_local)
        self.assertEqual(value['fetchedCommits'], owners)
        self.assertEqual(len(value['groups']), 1)
        self.assertEqual(setup.history.checkout_state(self.root), before)
        self.assertEqual((self.root / 'proof.txt').read_bytes(), tracked)
        setup.history.verify_group(self.root, group)
        raw = self.git('show', group['commit'] + ':proof.txt')
        self.assertEqual(hashlib.sha256(raw).hexdigest(), group['files']['proof.txt']['sha256'])

    def test_missing_objects_cannot_fetch_from_unauthorized_or_dirty_checkout(self):
        for environment in ({}, dict(self.environment, GITHUB_REPOSITORY='foreign/repository')):
            with self.subTest(environment=environment.get('GITHUB_REPOSITORY')), self.assertRaises(RuntimeError):
                self.prepare(environment=environment)
        with self.assertRaisesRegex(RuntimeError, 'requested source differs'):
            self.prepare(source_commit='a' * 40)
        self.git('remote', 'set-url', 'origin', 'https://github.com/foreign/repository.git')
        with self.assertRaisesRegex(RuntimeError, 'fixed public GitHub origin'):
            self.prepare()
        self.git('remote', 'set-url', 'origin', setup.history.ORIGINS[1])
        (self.root / 'proof.txt').write_bytes(b'Unapproved existing tracked modification\n')
        with self.assertRaisesRegex(RuntimeError, 'tracked checkout must be clean'):
            self.prepare()

    def test_failed_or_empty_transport_cannot_report_ui_history_ready(self):
        missing = [self.groups[0]['commit']]
        before = setup.history.checkout_state(self.root)
        def failure(owners):
            raise RuntimeError('Declared UI-history transport failure')
        with self.assertRaisesRegex(RuntimeError, 'Declared UI-history transport failure'):
            self.with_transport(missing, failure)
        self.assertEqual(setup.history.checkout_state(self.root), before)
        with self.assertRaises(setup.history.MissingHistoricalObject):
            self.with_transport(missing, lambda owners: b'')
        self.assertEqual(setup.history.checkout_state(self.root), before)

    def test_fetch_that_changes_actual_tracked_bytes_is_rejected(self):
        def polluted(owners):
            self.fetch_local(owners)
            (self.root / 'proof.txt').write_bytes(b'Changed tracked bytes during UI-history fetch\n')
            return b''
        with self.assertRaisesRegex(RuntimeError, 'changed HEAD|checkout|tracked'):
            self.with_transport([self.groups[0]['commit']], polluted)

    def test_altered_foreign_duplicate_or_symlink_manifest_rejects(self):
        original = (ROOT / UI_MANIFEST).read_bytes()
        path = self.root / UI_MANIFEST
        path.parent.mkdir(parents=True)
        path.write_bytes(original)
        self.assertEqual(setup.ui_manifest(self.root), setup.ui_manifest(ROOT))
        value = json.loads(original)
        duplicate = copy.deepcopy(value)
        duplicate['groups'].append(copy.deepcopy(duplicate['groups'][0]))
        foreign = copy.deepcopy(value)
        foreign['groups'][0]['commit'] = 'a' * 40
        for candidate in (original + b'\n', b'{"schema":1,"schema":1}',
                          json.dumps(duplicate).encode(), json.dumps(foreign).encode(), b'x' * 16385):
            path.write_bytes(candidate)
            with self.assertRaises(RuntimeError):setup.ui_manifest(self.root)
        path.unlink()
        actual = self.root / 'actual-ui-manifest.json'
        actual.write_bytes(original)
        path.symlink_to(actual)
        with self.assertRaises(RuntimeError):setup.ui_manifest(self.root)

    def test_actual_main_wires_original_then_additional_then_independent_ui_stage(self):
        old = dict(schema=1, status='passed', sourceCommit=self.source,
            sourceTree=self.git('rev-parse', 'HEAD^{tree}').decode().strip(),
            manifestSha256=setup.history.MANIFEST_SHA256, groups=setup.history.manifest(ROOT),
            fetchedCommits=[], checkoutUnchanged=True, testsExecuted=False, actualAndroidExecution=False)
        original = copy.deepcopy(old)
        additional = dict(schema=1, groups=setup.additional_manifest(ROOT), marker='exact unchanged additional stage receipt')
        ui = dict(schema=1, groups=setup.ui_manifest(ROOT), manifestSha256=setup.UI_MANIFEST_SHA256,
                  fetchedCommits=[OWNER], checkoutUnchanged=True, testsExecuted=False, actualAndroidExecution=False)
        calls = []
        def stage(label, value):
            def prepare(root, *, source_commit):
                self.assertEqual((root, source_commit), (self.root, self.source))
                calls.append(label)
                return value
            return prepare
        output = self.base / 'three-stage-main.json'
        argv = ['prepare_profile_host_prerequisites.py', '--source-commit', self.source,
                '--root', str(self.root), '--output', str(output)]
        with patch.object(setup, 'prepare_history', side_effect=stage('original21', old)), \
                patch.object(setup, 'prepare_additional_history', side_effect=stage('additional2', additional)), \
                patch.object(setup, 'prepare_ui_history', side_effect=stage('ui1', ui)), patch.object(sys, 'argv', argv):
            setup.main()
        value = json.loads(output.read_bytes())
        self.assertEqual(calls, ['original21', 'additional2', 'ui1'])
        self.assertEqual({key: item for key, item in value.items() if key not in ('additionalHistory', 'uiActivityHistory')}, original)
        self.assertEqual(value['additionalHistory'], additional)
        self.assertEqual(value['uiActivityHistory'], ui)
        self.assertEqual(len(value['groups']), 21)
        self.assertEqual(len(value['additionalHistory']['groups']), 2)
        self.assertEqual(len(value['uiActivityHistory']['groups']), 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
