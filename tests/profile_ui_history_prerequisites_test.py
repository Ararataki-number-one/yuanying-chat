"""Real missing UI Git objects through the current profile setup entry point.

CI-shaped inputs and the redirected local fetch are protocol controls, not an
actual GitHub run or a replacement for any historical UI behavior assertion.
"""
from contextlib import ExitStack
import copy
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import profile_host_prerequisites_test as original
import profile_host_supplemental_prerequisites_test as supplemental

ROOT, setup = original.ROOT, original.setup
sys.path.insert(0, str(ROOT / 'tools/browser'))
import prepare_ui_workspace_history as ui_history


class ProfileUiHistoryPrerequisitesTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(prefix='profile-ui-history-')
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.git('init', '-q')
        self.git('config', 'user.name', 'Profile UI setup control')
        self.git('config', 'user.email', 'profile-ui-control@example.invalid')
        self.git('remote', 'add', 'origin', setup.history.ORIGINS[1])
        (self.root / 'anchor.txt').write_text('Independent source checkout\n')
        manifest = self.root / ui_history.MANIFEST
        manifest.parent.mkdir(parents=True)
        manifest.write_bytes((ROOT / ui_history.MANIFEST).read_bytes())
        self.git('add', 'anchor.txt', ui_history.MANIFEST)
        self.git('commit', '-qm', 'Independent profile prerequisite control')
        self.source = self.git('rev-parse', 'HEAD').decode().strip()
        self.groups = ui_history.manifest(self.root)
        self.expected_missing = [group['commit'] for group in self.groups]
        self.event = dict(repository=dict(full_name=setup.history.REPOSITORY), number=7,
            pull_request=dict(head=dict(sha=self.source), base=dict(repo=dict(full_name=setup.history.REPOSITORY))))
        self.event_path = self.root / 'event.json'
        self.write_event()
        self.environment = dict(CI='true', GITHUB_ACTIONS='true', GITHUB_SERVER_URL='https://github.com',
            GITHUB_REPOSITORY=setup.history.REPOSITORY, GITHUB_RUN_ID='123', GITHUB_RUN_ATTEMPT='1',
            GITHUB_SHA='f' * 40, GITHUB_EVENT_NAME='pull_request', GITHUB_REF='refs/pull/7/merge',
            GITHUB_EVENT_PATH=str(self.event_path))
        self.real_git = setup.history.git
        self.fetches = []

    def git(self, *args):
        return subprocess.run(['git', '--no-replace-objects', *args], cwd=self.root,
            capture_output=True, check=True, env=dict(os.environ, GIT_NO_LAZY_FETCH='1')).stdout

    def write_event(self):
        self.event_path.write_text(json.dumps(self.event))

    def transport(self, root, *args):
        if args[:1] == ('fetch',):
            self.assertEqual(args, ('fetch', '--no-tags', '--depth=1', '--no-write-fetch-head',
                '--no-filter', 'origin', *self.expected_missing))
            self.fetches.append(args)
            # Only the destination changes. All owner/tree/blob validation
            # still executes against the actual fetched Git object bytes.
            return self.real_git(root, *args[:5], str(ROOT), *args[6:])
        return self.real_git(root, *args)

    def prepare(self, *, source=None, environment=None, transport=None):
        with patch.object(setup.history, 'git', side_effect=transport or self.transport):
            return setup.prepare_ui_history(self.root, source_commit=self.source if source is None else source,
                environment=self.environment if environment is None else environment)

    def seed(self, group):
        self.git('fetch', '--no-tags', '--depth=1', '--no-write-fetch-head', str(ROOT), group['commit'])

    def cli(self, output, calls, *, transport=None, earlier_failure=None):
        def stage(name):
            def invoke(root, *, source_commit):
                self.assertEqual((root, source_commit), (self.root, self.source))
                calls.append(name)
                if name == earlier_failure:
                    raise RuntimeError('Earlier setup failed')
                return dict(status='passed', controlledBoundary=name)
            return invoke
        real_verify = setup.history.verify_group
        def verify(root, group):
            if group['commit'] in self.expected_missing and 'ui' not in calls:
                calls.append('ui')
            return real_verify(root, group)
        with ExitStack() as stack:
            # The other four prerequisite families have their own real-object
            # tests. This entry-point control isolates the formerly omitted UI
            # family without manufacturing or substituting its source objects.
            for function, name in (('prepare_history', 'original'),
                    ('prepare_compatibility_history', 'compatibility'),
                    ('prepare_supplemental_history', 'supplemental'),
                    ('prepare_released_history', 'released')):
                stack.enter_context(patch.object(setup, function, side_effect=stage(name)))
            stack.enter_context(patch.object(setup.history, 'verify_group', side_effect=verify))
            stack.enter_context(patch.object(setup.history, 'git', side_effect=transport or self.transport))
            stack.enter_context(patch.dict(os.environ, self.environment))
            stack.enter_context(patch.object(sys, 'argv', ['prepare', '--root', str(self.root),
                '--source-commit', self.source, '--output', str(output)]))
            setup.main()
            self.assertEqual(os.environ['GITHUB_SHA'], self.environment['GITHUB_SHA'])

    def test_actual_default_cli_restores_missing_ui_owners_after_existing_setup(self):
        for group in self.groups:
            with self.assertRaises(setup.history.MissingHistoricalObject):
                setup.history.verify_group(self.root, group)
        before = setup.history.checkout_state(self.root)
        calls, output = [], self.root / 'report.json'
        self.cli(output, calls)
        # This fails against the original CLI: it reports success yet leaves
        # the two actual owners unavailable to the following UI tests.
        observed = [setup.history.verify_group(self.root, group) for group in self.groups]
        report = json.loads(output.read_bytes())
        self.assertEqual(calls, ['original', 'compatibility', 'supplemental', 'released', 'ui'])
        self.assertEqual(report['uiHistory']['groups'], observed)
        self.assertEqual(report['uiHistory']['fetchedCommits'], self.expected_missing)
        self.assertEqual([len(group['files']) for group in observed], [13, 10])
        self.assertEqual(before, setup.history.checkout_state(self.root))
        self.assertTrue((self.root / '.git/shallow').is_file())
        self.assertFalse((self.root / '.git/FETCH_HEAD').exists())

    def test_real_missing_owners_use_pr_head_without_changing_workflow_merge_sha(self):
        environment = dict(self.environment)
        before = setup.history.checkout_state(self.root)
        # Calling the old strict helper would reject this valid PR checkout.
        with patch.object(ui_history.history, 'authorize_fetch',
                side_effect=AssertionError('Legacy SHA-equals-HEAD authorization must not run')):
            report = self.prepare()
        self.assertNotEqual(self.source, self.environment['GITHUB_SHA'])
        self.assertEqual(self.environment, environment)
        self.assertEqual(report['sourceCommit'], self.source)
        self.assertEqual(report['manifestSha256'], ui_history.MANIFEST_SHA256)
        self.assertEqual(report['fetchedCommits'], self.expected_missing)
        self.assertEqual(len(self.fetches), 1)
        self.assertEqual(before, setup.history.checkout_state(self.root))
        self.assertFalse(report['testsExecuted'])
        self.assertFalse(report['actualAndroidExecution'])

    def test_only_actual_missing_owner_is_fetched(self):
        self.seed(self.groups[0])
        self.expected_missing = [self.groups[1]['commit']]
        report = self.prepare()
        self.assertEqual(report['fetchedCommits'], self.expected_missing)
        self.assertEqual(len(report['groups']), 2)
        self.assertEqual(len(self.fetches), 1)

    def test_present_owners_verify_offline_even_with_existing_local_change(self):
        for group in self.groups:
            self.seed(group)
        (self.root / 'anchor.txt').write_text('Existing local edit\n')
        before = setup.history.checkout_state(self.root)
        with patch.object(setup, 'authorize_fetch', side_effect=AssertionError('Present objects must stay offline')):
            report = self.prepare(environment={})
        self.assertEqual(report['fetchedCommits'], [])
        self.assertEqual(self.fetches, [])
        self.assertEqual(before, setup.history.checkout_state(self.root))

    def test_wrong_source_event_origin_or_dirty_checkout_rejects_before_transport(self):
        with self.assertRaisesRegex(RuntimeError, 'source differs'):
            self.prepare(source='a' * 40)
        with self.assertRaisesRegex(RuntimeError, 'fixed repository GitHub CI'):
            self.prepare(environment={})
        original_event = copy.deepcopy(self.event)
        for kind in ('head', 'base'):
            self.event = copy.deepcopy(original_event)
            if kind == 'head': self.event['pull_request']['head']['sha'] = 'a' * 40
            else: self.event['pull_request']['base']['repo']['full_name'] = 'foreign/repository'
            self.write_event()
            with self.subTest(kind=kind), self.assertRaisesRegex(RuntimeError, 'head or base repository differs'):
                self.prepare()
        self.event = original_event
        self.write_event()
        self.git('remote', 'set-url', 'origin', 'https://github.com/foreign/repository.git')
        with self.assertRaisesRegex(RuntimeError, 'fixed public GitHub origin'):
            self.prepare()
        self.git('remote', 'set-url', 'origin', setup.history.ORIGINS[1])
        (self.root / 'anchor.txt').write_text('Dirty before fetch\n')
        with self.assertRaisesRegex(RuntimeError, 'tracked checkout must be clean'):
            self.prepare()
        self.assertEqual(self.fetches, [])

    def test_changed_original_ui_manifest_is_rejected_before_transport(self):
        manifest = self.root / ui_history.MANIFEST
        manifest.write_bytes(manifest.read_bytes() + b'\n')
        with self.assertRaisesRegex(RuntimeError, 'fixed UI history manifest bytes differ'):
            self.prepare()
        self.assertEqual(self.fetches, [])

    def test_failed_or_incomplete_transport_cannot_report_prepared_objects(self):
        def transport(root, *args):
            if args[:1] == ('fetch',):
                return subprocess.CompletedProcess(args, returncode, b'', b'Controlled transport failure')
            return self.real_git(root, *args)
        for returncode in (1, 0):
            with self.subTest(returncode=returncode), self.assertRaises(RuntimeError):
                self.prepare(transport=transport)

    def test_source_change_during_actual_fetch_is_rejected(self):
        def transport(root, *args):
            result = self.transport(root, *args)
            if args[:1] == ('fetch',):
                (self.root / 'anchor.txt').write_text('Changed during fetch\n')
            return result
        with self.assertRaisesRegex(RuntimeError, 'fetch changed HEAD, tree, index or tracked bytes'):
            self.prepare(transport=transport)

    def test_cli_ui_setup_failure_propagates_without_success_report(self):
        def incomplete(root, *args):
            if args[:1] == ('fetch',):
                return subprocess.CompletedProcess(args, 0, b'', b'')
            return self.real_git(root, *args)
        calls, output = [], self.root / 'report.json'
        with self.assertRaises(setup.history.MissingHistoricalObject):
            self.cli(output, calls, transport=incomplete)
        self.assertEqual(calls, ['original', 'compatibility', 'supplemental', 'released', 'ui'])
        self.assertFalse(output.exists())

    def test_cli_earlier_setup_failure_stops_before_ui_preparation(self):
        calls, output = [], self.root / 'report.json'
        with self.assertRaisesRegex(RuntimeError, 'Earlier setup failed'):
            self.cli(output, calls, earlier_failure='supplemental')
        self.assertEqual(calls, ['original', 'compatibility', 'supplemental'])
        self.assertEqual(self.fetches, [])
        self.assertFalse(output.exists())

    def test_actual_runner_tracks_ui_setup_inputs_before_host_snapshot(self):
        control = supplemental.ProfileRunnerSetupOrderTests(
            'test_unconditional_original_cli_finishes_before_input_snapshot')
        namespace = runpy.run_path(str(ROOT / 'tools/gecko/run_profile_host_checks.py'))
        snapshot = control.git_snapshot()
        jar = self.root / 'argument-only.jar'
        jar.write_bytes(b'Not executed')
        with patch.object(sys, 'argv', ['runner', '--json-jar', str(jar)]), \
                patch.object(subprocess, 'check_output', side_effect=snapshot * 2), \
                patch.object(subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)) as run:
            exec(control.runner_prefix(), namespace)
        run.assert_called_once()
        self.assertEqual(namespace['prerequisite_inputs'], {ROOT / path for path in (
            'tools/gecko/prepare_profile_host_prerequisites.py', 'tools/browser/source_history.py',
            'tests/baselines/public-source-history.json', 'tests/fixtures/profile-fixture-root-source-deltas.json',
            'tools/browser/prepare_ui_workspace_history.py', ui_history.MANIFEST)})
        self.assertNotIn('input_paths', namespace)


if __name__ == '__main__':
    unittest.main(verbosity=2)
