"""Additive original-history preparation and declared transport fault controls.

Full discovery imports every profile module before executing any case, so this
module prepares immutable inputs before the untouched historical tests run.
Standalone old modules in a shallow checkout require the helper CLI first.
"""
import json
import hashlib
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from gecko import prepare_bridge42_history12 as history

ROOT = Path(__file__).resolve().parents[1]
PREPARATION = history.prepare_original_history(ROOT)
print('ORIGINAL_HISTORY12_INPUTS ' + json.dumps(PREPARATION, sort_keys=True), flush=True)

SOURCE = 'a' * 40
ENV = dict(CI='true', GITHUB_ACTIONS='true', GITHUB_SERVER_URL='https://github.com',
           GITHUB_REPOSITORY=history.REPOSITORY, GITHUB_RUN_ID='123', GITHUB_RUN_ATTEMPT='1', GITHUB_SHA=SOURCE)


class FakeGit:
    """The fetch boundary copies actual pinned Git bytes into a declared store.

    It does not execute a remote fetch, rewrite original git-show calls or run
    original assertions. Unrecognized commands fail rather than returning OK.
    """
    def __init__(self, objects, groups, *, missing=(), fail_fetch=False, incomplete=False):
        self.objects, self.groups = objects, groups
        self.present = set(objects) - set(missing)
        self.fail_fetch, self.incomplete = fail_fetch, incomplete
        self.calls, self.metadata = [], {}
        self.after_fetch = {}

    def __call__(self, root, *parts):
        self.calls.append(parts)
        result = subprocess.CompletedProcess(parts, 0, stdout=b'', stderr=b'')
        if parts[:1] == ('cat-file',):
            key = parts[1:]
            result.returncode = 0 if key in self.present else 128
            result.stdout = self.objects[key] if key in self.present else b''
            return result
        values = {('rev-parse', '--show-toplevel'): str(ROOT).encode() + b'\n',
                  ('rev-parse', 'HEAD'): SOURCE.encode() + b'\n',
                  ('rev-parse', 'HEAD^{tree}'): b'b' * 40 + b'\n',
                  ('ls-files', '--stage', '-z'): b'controlled exact index metadata\0',
                  ('status', '--porcelain', '--untracked-files=no'): b'',
                  ('remote', 'get-url', 'origin'): history.ORIGINS[0].encode() + b'\n'}
        values.update(self.metadata)
        if parts in values:
            result.stdout = values[parts]
            return result
        if parts[:1] == ('fetch',):
            assert parts[:6] == ('fetch', '--no-tags', '--depth=1', '--no-write-fetch-head', 'origin', parts[5])
            assert len(parts) == 6 and parts[5] in self.groups
            result.returncode = 1 if self.fail_fetch else 0
            if not self.fail_fetch and not self.incomplete:
                self.present.update(self.groups[parts[5]])
            self.metadata.update(self.after_fetch)
            return result
        raise AssertionError(('Unexpected Git command', parts))

    def fetches(self):
        return [row for row in self.calls if row[:1] == ('fetch',)]


class OriginalHistoryPreparationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Actual local immutable objects form the fault-control payloads. No
        # synthetic replacement bytes can stand in for the original oracles.
        cls.objects, cls.groups = {}, {}
        original = history.git
        for group in history.GROUPS:
            keys = set()
            def record(root, *parts):
                result = original(root, *parts)
                if parts[:1] == ('cat-file',) and result.returncode == 0:
                    keys.add(parts[1:])
                    cls.objects[parts[1:]] = result.stdout
                return result
            with patch.object(history, 'git', record):
                history.verify_group(ROOT, group)
            cls.groups[group[0]] = keys

    def fake(self, **kwargs):
        return FakeGit(dict(self.objects), dict(self.groups), **kwargs)

    def run_prepare(self, fake, env=ENV):
        with patch.object(history, 'git', fake):
            return history.prepare_original_history(ROOT, environment=env)

    def test_actual_current_objects_verify_both_owners_and_all_twelve_inputs(self):
        value = history.prepare_original_history(ROOT, environment={})
        self.assertEqual(value['status'], 'verified-original-historical-inputs')
        self.assertEqual(value['fetchedOwnerCommits'], [])
        self.assertEqual([len(row['files']) for row in value['groups']], [3, 9])
        self.assertFalse(value['originalAssertionsExecuted'])
        self.assertFalse(value['actualAndroidExecution'])

    def test_already_present_inputs_need_no_ci_origin_or_mutation(self):
        fake = self.fake()
        value = self.run_prepare(fake, {})
        self.assertEqual(value['fetchedOwnerCommits'], [])
        self.assertTrue(fake.calls)
        self.assertTrue(all(row[0] == 'cat-file' for row in fake.calls))

    def test_missing_history_outside_actual_ci_is_a_hard_failure(self):
        missing = [('commit', history.GROUPS[0][0])]
        changes = [{}, dict(ENV, CI='false'), dict(ENV, GITHUB_ACTIONS='false'),
                   dict(ENV, GITHUB_SERVER_URL='https://elsewhere.invalid'), dict(ENV, GITHUB_REPOSITORY='someone/other')]
        for env in changes:
            fake = self.fake(missing=missing)
            with self.subTest(environment=env), self.assertRaisesRegex(RuntimeError, 'actual GitHub CI repository'):
                self.run_prepare(fake, env)
            self.assertEqual(fake.fetches(), [])

    def test_actual_positive_workflow_and_source_identity_are_required(self):
        for key, values in [('GITHUB_RUN_ID', ('', '0', '1\n', True)),
                            ('GITHUB_RUN_ATTEMPT', ('', '0', '1;anything', 1)),
                            ('GITHUB_SHA', ('', 'b' * 40, 'a' * 40 + '\n', True))]:
            for value in values:
                fake = self.fake(missing=[('commit', history.GROUPS[0][0])])
                with self.subTest(key=key, value=value), self.assertRaises(RuntimeError):
                    self.run_prepare(fake, dict(ENV, **{key: value}))
                self.assertEqual(fake.fetches(), [])

    def test_actual_checkout_root_clean_source_and_fixed_origin_are_required(self):
        for key, value in [(('rev-parse', '--show-toplevel'), b'/elsewhere\n'),
                           (('status', '--porcelain', '--untracked-files=no'), b' M changed\n'),
                           (('remote', 'get-url', 'origin'), b'https://elsewhere.invalid/repo\n')]:
            fake = self.fake(missing=[('commit', history.GROUPS[0][0])])
            fake.metadata[key] = value
            with self.subTest(field=key), self.assertRaises(RuntimeError):
                self.run_prepare(fake)
            self.assertEqual(fake.fetches(), [])

    def test_only_missing_exact_owner_is_fetched_once_without_fetch_head(self):
        for group in history.GROUPS:
            fake = self.fake(missing=[('commit', group[0])])
            value = self.run_prepare(fake)
            self.assertEqual(value['fetchedOwnerCommits'], [group[0]])
            self.assertEqual(fake.fetches(), [('fetch', '--no-tags', '--depth=1', '--no-write-fetch-head', 'origin', group[0])])
            self.assertEqual([len(row['files']) for row in value['groups']], [3, 9])

    def test_both_missing_groups_fetch_only_two_fixed_commits(self):
        fake = self.fake(missing=[('commit', row[0]) for row in history.GROUPS])
        value = self.run_prepare(fake)
        self.assertEqual(value['fetchedOwnerCommits'], [row[0] for row in history.GROUPS])
        self.assertEqual(len(fake.fetches()), 2)

    def test_missing_root_tree_subtree_or_blob_is_not_mistaken_for_verified(self):
        group = history.GROUPS[0]
        subtree = next(key for key in self.groups[group[0]] if key[0] == 'tree' and key[1] != group[1])
        blob = ('blob', next(iter(group[2].values()))[0])
        for key in [('tree', group[1]), subtree, blob]:
            fake = self.fake(missing=[key])
            value = self.run_prepare(fake)
            self.assertEqual(value['fetchedOwnerCommits'], [group[0]])

    def test_command_failure_or_incomplete_fetch_never_runs_a_retry_or_reports_ready(self):
        for kwargs in (dict(fail_fetch=True), dict(incomplete=True)):
            fake = self.fake(missing=[('commit', history.GROUPS[0][0])], **kwargs)
            with self.subTest(kwargs=kwargs), self.assertRaises(RuntimeError):
                self.run_prepare(fake)
            self.assertEqual(len(fake.fetches()), 1)

    def test_actual_head_tree_index_or_worktree_changes_after_fetch_are_rejected(self):
        for key, value in [(('rev-parse', 'HEAD'), b'd' * 40 + b'\n'),
                           (('rev-parse', 'HEAD^{tree}'), b'd' * 40 + b'\n'),
                           (('ls-files', '--stage', '-z'), b'changed exact index metadata\0'),
                           (('status', '--porcelain', '--untracked-files=no'), b' M changed\n')]:
            fake = self.fake(missing=[('commit', history.GROUPS[0][0])])
            fake.after_fetch[key] = value
            with self.subTest(field=key), self.assertRaises(RuntimeError):
                self.run_prepare(fake)
            self.assertEqual(len(fake.fetches()), 1)

    def test_corrupt_existing_owner_tree_and_blob_fail_without_fetch(self):
        group = history.GROUPS[0]
        for key in [('commit', group[0]), ('tree', group[1]), ('blob', next(iter(group[2].values()))[0])]:
            fake = self.fake()
            fake.objects[key] += b' '
            with self.subTest(object=key), self.assertRaisesRegex(RuntimeError, 'object bytes differ'):
                self.run_prepare(fake)
            self.assertEqual(fake.fetches(), [])

    def test_wrong_owner_tree_or_path_blob_pin_is_rejected(self):
        owner, tree, files = history.GROUPS[0]
        for replacement in [(owner, '0' * 40, files),
                            (owner, tree, dict(files, **{'tests/fingerprint_source_compatibility.py': ('0' * 40, 10225, '0' * 64)}))]:
            fake = self.fake()
            with patch.object(history, 'GROUPS', (replacement, history.GROUPS[1])), self.assertRaises(RuntimeError):
                self.run_prepare(fake)
            self.assertEqual(fake.fetches(), [])

    def test_wrong_whole_file_size_or_sha_pin_is_not_softened(self):
        owner, tree, files = history.GROUPS[0]
        path = 'tests/fingerprint_source_compatibility.py'
        blob, size, sha = files[path]
        for altered in ((blob, size + 1, sha), (blob, size, '0' * 64)):
            fake = self.fake()
            with patch.object(history, 'GROUPS', ((owner, tree, dict(files, **{path: altered})), history.GROUPS[1])), self.assertRaisesRegex(RuntimeError, 'whole historical source differs'):
                self.run_prepare(fake)
            self.assertEqual(fake.fetches(), [])

    def test_git_transport_has_a_fixed_deadline_and_never_checks_out_or_writes_refs(self):
        completed = subprocess.CompletedProcess([], 0, stdout=b'ok', stderr=b'')
        with patch.object(history.subprocess, 'run', return_value=completed) as run:
            self.assertEqual(history.git(ROOT, 'cat-file', 'commit', history.GROUPS[0][0]), completed)
        args, kwargs = run.call_args
        self.assertEqual(args, (['git', '--no-replace-objects', 'cat-file', 'commit', history.GROUPS[0][0]],))
        self.assertEqual({key: kwargs[key] for key in ('cwd', 'stdout', 'stderr', 'timeout')},
                         dict(cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120))
        for key in ('GIT_NO_LAZY_FETCH', 'GIT_OPTIONAL_LOCKS', 'GIT_TERMINAL_PROMPT'):
            self.assertEqual(kwargs['env'][key], '1' if key == 'GIT_NO_LAZY_FETCH' else '0')
        with patch.object(history.subprocess, 'run', side_effect=subprocess.TimeoutExpired('git', 120)), self.assertRaises(subprocess.TimeoutExpired):
            history.git(ROOT, 'fetch', '--no-tags', '--depth=1', '--no-write-fetch-head', 'origin', history.GROUPS[0][0])

    def test_full_discovery_imports_preparation_before_original_old_cases_execute(self):
        # A separate process performs real full discovery (imports only), then
        # runs just the two original formerly failing methods. Their own real
        # git-show calls and assertions are not intercepted or normalized.
        script = '''import json,pathlib,sys,unittest
root=pathlib.Path(sys.argv[1]);sys.path.insert(0,str(root/'tests'))
loader=unittest.TestLoader();all_cases=loader.discover(str(root/'tests'),pattern='profile_*_test.py')
assert 'profile_original_history12_test' in sys.modules
proof=sys.modules['profile_original_history12_test'].PREPARATION
assert [len(row['files']) for row in proof['groups']]==[3,9]
names=['profile_page_bridge42_source_compatibility_test.SequentialBridge42CompatibilityTests.test_exact_four_line_inverse_matches_whole_actual_prior41_tree','profile_page_bridge42_source_compatibility_test.SequentialBridge42CompatibilityTests.test_compatibility_changes_invert_to_entire_prior41_test_bytes']
result=unittest.TextTestRunner().run(loader.loadTestsFromNames(names));assert result.wasSuccessful() and result.testsRun==2
print('HISTORY12_DISCOVERY_ORDER '+json.dumps({'allModulesImportedBeforeOriginalMethods':True,'originalMethodsRun':2,'realHistoricalInputsVerified':True,'actualRemoteFetch':False,'actualAndroidExecution':False}))
'''
        result = subprocess.run([sys.executable, '-c', script, str(ROOT)], cwd=ROOT,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertIn(b'HISTORY12_DISCOVERY_ORDER ', result.stdout)
        self.assertIn(b'Ran 2 tests', result.stderr)

    def test_two_original_consumer_modules_and_every_method_remain_byte_exact(self):
        for path, sha in {
            'tests/profile_page_bridge42_source_compatibility_test.py': '41420eaa7e9b63ab584d922de2f6a663c2fdfbfe3228bf039f59f034b589ab72',
            'tests/profile_native43_source_compatibility_test.py': 'bba86851f8ccca9f33a64398925f2eb1648947fc7ee628bd9404269c235f3f39',
        }.items():
            self.assertEqual(hashlib.sha256((ROOT / path).read_bytes()).hexdigest(), sha)


if __name__ == '__main__':
    unittest.main(verbosity=2)
