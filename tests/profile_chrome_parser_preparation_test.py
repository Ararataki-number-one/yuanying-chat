"""Real host compiler/cache controls; no device input or Android acceptance."""
import ast
import contextlib
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'tools/gecko'), str(ROOT/'tests/gecko')]
import chrome_header_readiness as gate
import chrome_parser_preparation as preparation
import run_chrome_collapse_v2 as runner
from historical_source_inputs import historical_bytes

RUNNER = 'tests/gecko/run_chrome_collapse_v2.py'
OLD_TEST = 'tests/gecko_chrome_collapse_v2_test.py'
IMPORT = b'from chrome_parser_preparation import prepare_parser\n'
HOOK = b'    prepare_parser(root=ROOT, source=source, identity=identity)\n'
ANCHOR = (b"    verify_installed(json.loads(adb('exec-out', 'content', 'read', '--uri', 'content://'+PACKAGE+'.evidence/build-identity')), identity)\n"
          b'    prefix = resume_transport(sys.argv[1:])\n')
MOCK = b"                 patch.object(current_runner,'prepare_parser',return_value={'setupOnly':True,'hostOnly':True}),\\\n"
BEFORE = {
    RUNNER: (21427, 'd4661646b7e06d77875b0869b0871de07b2e273ff3333700e0fdcaad50c7690e', '333a702b0a705c7b716b921886abb5bbb013fa90'),
    OLD_TEST: (35374, 'f26ab2c43f758ab3fd33a21c8efdc2525d13174283cef4639b18293dd2603310', 'a0e4665b7e42e89ce77ab21ef30262e81a3c0109'),
}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def pin(raw):
    return len(raw), digest(raw), hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()


def before_image(raw, relative):
    """Only the two declared complete before images, never a broad normalizer."""
    if relative == RUNNER:
        installed, prefix = ANCHOR.splitlines(keepends=True)
        current = installed + HOOK + prefix
        if raw.count(IMPORT) != 1 or raw.count(HOOK) != 1 or raw.count(current) != 1:
            raise ValueError('Unreviewed runner preparation hook')
        restored = raw.replace(IMPORT, b'', 1).replace(current, ANCHOR, 1)
    elif relative == OLD_TEST:
        if raw.count(MOCK) != 1:
            raise ValueError('Unreviewed declared host-only dependency mock')
        restored = raw.replace(MOCK, b'', 1)
    else:
        raise ValueError('Unreviewed source path')
    if pin(restored) != BEFORE[relative]:
        raise ValueError('Whole original source or assertions changed')
    return restored


class ActualCompilerCacheTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base_directory = tempfile.TemporaryDirectory(prefix='chrome-parser-original-')
        cls.base = Path(cls.base_directory.name)
        (cls.base/'.gitignore').write_text('work/\n')
        for relative in (gate.HELPER, gate.CLI, gate.ADAPTER):
            target = cls.base/relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT/relative).read_bytes())
        env = dict(os.environ, GIT_NO_LAZY_FETCH='1', GIT_OPTIONAL_LOCKS='0')
        def git(*parts):
            return subprocess.check_output(['git', *parts], cwd=cls.base, env=env, stderr=subprocess.PIPE).decode().strip()
        git('init', '-q')
        git('add', '.gitignore', gate.HELPER, gate.CLI, gate.ADAPTER)
        git('-c', 'user.name=Host control', '-c', 'user.email=host-control@invalid.example',
            'commit', '-q', '-m', 'Synthetic host parser source only')
        cls.identity = dict(sourceCommit=git('rev-parse', 'HEAD'), sourceTree=git('rev-parse', 'HEAD^{tree}'))
        with contextlib.redirect_stdout(io.StringIO()):
            cls.original = preparation.prepare_parser(root=cls.base, source=cls.identity['sourceCommit'], identity=cls.identity)

    @classmethod
    def tearDownClass(cls):
        cls.base_directory.cleanup()

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='chrome-parser-control-')
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)/'source'
        shutil.copytree(self.base, self.root)
        self.cache = next((self.root/'work/chrome-header-parser').iterdir())
        self.manifest = self.cache/'manifest.json'
        self.classes = self.cache/'classes'

    def prepare(self, **kwargs):
        values = dict(root=self.root, source=self.identity['sourceCommit'], identity=self.identity)
        values.update(kwargs)
        with contextlib.redirect_stdout(io.StringIO()):
            return preparation.prepare_parser(**values)

    def test_real_cold_compile_then_warm_validation_use_the_same_bound_cache(self):
        shutil.rmtree(self.cache)
        with mock.patch.object(gate, '_bounded_run', wraps=gate._bounded_run) as commands:
            cold = self.prepare()
            cold_calls = [row.args[0] for row in commands.call_args_list]
            commands.reset_mock()
            warm = self.prepare()
            warm_calls = [row.args[0] for row in commands.call_args_list]
        self.assertEqual(sum(Path(row[0]).name == 'javac' for row in cold_calls), 1)
        self.assertFalse(any(Path(row[0]).name == 'javac' for row in warm_calls))
        self.assertEqual(sum(Path(row[0]).name == 'java' for row in warm_calls), 1)
        self.assertTrue(all(Path(row[0]).name in ('git', 'java', 'javac') for row in cold_calls + warm_calls))
        self.assertEqual(cold['parserClassesSha256'], warm['parserClassesSha256'])
        saved = json.loads(self.manifest.read_bytes())
        self.assertEqual(saved['classes'], gate._class_hashes(self.classes))
        self.assertEqual(len(saved['classes']), 7)
        self.assertEqual(saved['binding']['sourceCommit'], self.identity['sourceCommit'])
        self.assertEqual(saved['binding']['sourceTree'], self.identity['sourceTree'])
        home = os.environ.get('JAVA_HOME_17_X64') or os.environ.get('JAVA_HOME')
        java = (Path(home)/'bin/java').resolve() if home else Path(shutil.which('java')).resolve()
        self.assertEqual(saved['tool']['javaSha256'], digest(java.read_bytes()))
        self.assertEqual(saved['tool']['javacSha256'], digest(java.with_name('javac').read_bytes()))
        self.assertTrue(warm['setupOnly'])
        self.assertFalse(warm['actualAndroidExecution'])
        self.assertFalse(warm['applicationAcceptance'])
        self.assertFalse(warm['releaseAcceptance'])
        self.assertEqual(warm['setupBudgetMs'], 20000)

    def test_wrong_source_or_tree_is_rejected_before_cache_use(self):
        for field in ('sourceCommit', 'sourceTree'):
            identity = dict(self.identity, **{field: '0'*40})
            with self.subTest(field=field), mock.patch.object(gate, '_compile_parser', side_effect=AssertionError('Cache must not be used')), \
                 self.assertRaisesRegex(gate.HeaderReadinessFailure, 'source-unverified'):
                self.prepare(identity=identity)

    def test_dirty_selected_source_is_rejected(self):
        with (self.root/gate.CLI).open('ab') as stream:
            stream.write(b'\n// controlled unrelated mutation\n')
        with self.assertRaisesRegex(gate.HeaderReadinessFailure, 'source-unverified'):
            self.prepare()

    def test_wrong_cached_source_and_jdk_bindings_are_rejected(self):
        saved = json.loads(self.manifest.read_bytes())
        for owner, field in [('binding', 'sourceCommit'), ('binding', 'sourceTree'),
                             ('tool', 'javaSha256'), ('tool', 'javacSha256'), ('tool', 'versionSha256')]:
            changed = copy.deepcopy(saved)
            changed[owner][field] = '0'*len(changed[owner][field])
            self.manifest.write_text(json.dumps(changed))
            with self.subTest(owner=owner, field=field), self.assertRaisesRegex(gate.HeaderReadinessFailure, 'cache-unverified'):
                self.prepare()

    def test_modified_missing_extra_and_symlink_class_files_are_rejected(self):
        target = next(self.classes.rglob('NativePreEmitReadiness.class'))
        raw = target.read_bytes()
        for mutation in ('modified', 'missing', 'extra', 'symlink'):
            extra = target.with_name('Unexpected.class')
            if mutation == 'modified':
                target.write_bytes(raw + b'changed')
            elif mutation == 'missing':
                target.unlink()
            elif mutation == 'extra':
                extra.write_bytes(b'controlled unexpected class')
            else:
                target.unlink()
                target.symlink_to(self.base/target.relative_to(self.root))
            with self.subTest(mutation=mutation), self.assertRaisesRegex(gate.HeaderReadinessFailure, 'cache-unverified'):
                self.prepare()
            target.unlink(missing_ok=True)
            target.write_bytes(raw)
            extra.unlink(missing_ok=True)

    def test_missing_and_ambiguous_manifest_cannot_trigger_a_rebuild(self):
        original = self.manifest.read_bytes()
        for mutation in ('missing', 'duplicate'):
            if mutation == 'missing':
                self.manifest.unlink()
            else:
                self.manifest.write_bytes(b'{"binding":{},"binding":{}}')
            with self.subTest(mutation=mutation), mock.patch.object(gate, '_bounded_run', wraps=gate._bounded_run) as commands:
                with self.assertRaises(gate.HeaderReadinessFailure):
                    self.prepare()
                self.assertFalse(any(Path(row.args[0][0]).name == 'javac' for row in commands.call_args_list))
            self.manifest.write_bytes(original)

    def test_non_17_runtime_is_rejected_before_compilation(self):
        jdk = Path(self.directory.name)/'wrong-jdk/bin'
        jdk.mkdir(parents=True)
        (jdk/'java').write_text('#!/bin/sh\nprintf \'openjdk version "18.0.0"\\n\' >&2\n')
        (jdk/'javac').write_text('#!/bin/sh\nexit 99\n')
        (jdk/'java').chmod(0o700)
        (jdk/'javac').chmod(0o700)
        with mock.patch.dict(os.environ, {'JAVA_HOME_17_X64': str(jdk.parent)}), self.assertRaisesRegex(gate.HeaderReadinessFailure, 'cache-unverified'):
            self.prepare()


class PreparationBoundaryTests(unittest.TestCase):
    def test_original_host_calls_share_one_fixed_deadline(self):
        binding = dict(sourceCommit='a'*40, sourceTree='b'*40, sourceSha256={})
        with mock.patch.object(gate, '_source_bindings', return_value=binding) as sources, \
             mock.patch.object(gate, '_compile_parser', return_value=([], {'parserClassesSha256': 'c'*64})) as compiler, \
             contextlib.redirect_stdout(io.StringIO()):
            result = preparation.prepare_parser(root=ROOT, source='a'*40, identity=binding, clock=iter((100., 119.999)).__next__)
        self.assertEqual(sources.call_args.args[-1], 120.)
        self.assertEqual(compiler.call_args.args[-1], 120.)
        self.assertEqual(result['setupBudgetMs'], 20000)
        self.assertLess(result['elapsedMs'], 20000)

    def test_host_preparation_finishing_at_its_deadline_is_rejected(self):
        binding = dict(sourceTree='b'*40, sourceSha256={})
        with mock.patch.object(gate, '_source_bindings', return_value=binding), \
             mock.patch.object(gate, '_compile_parser', return_value=([], {'parserClassesSha256': 'c'*64})), \
             self.assertRaisesRegex(gate.HeaderReadinessFailure, 'deadline'):
            preparation.prepare_parser(root=ROOT, source='a'*40, identity=binding, clock=iter((100., 120.)).__next__)

    def test_preparation_error_stops_real_runner_before_any_cohort_or_input(self):
        build = dict(sourceCommit='a'*40, sourceTree='b'*40)
        observed = []
        def adb(*parts):
            self.assertEqual(parts, ('exec-out', 'content', 'read', '--uri', 'content://'+runner.PACKAGE+'.evidence/build-identity'))
            observed.append('installed-read')
            return json.dumps(build)
        def verify(actual, expected):
            self.assertEqual(actual, expected)
            observed.append('installed-verified')
        def failed_preparation(**kwargs):
            self.assertEqual(kwargs, dict(root=runner.ROOT, source=build['sourceCommit'], identity=build))
            observed.append('host-preparation-failed')
            raise gate.HeaderReadinessFailure('cache-unverified')
        with mock.patch.object(runner.subprocess, 'check_output', return_value=build['sourceTree']+'\n'), \
             mock.patch.object(runner, 'expected_build', return_value=build), \
             mock.patch.object(runner, 'verify_installed', side_effect=verify), \
             mock.patch.object(runner, 'prepare_parser', side_effect=failed_preparation), \
             mock.patch.object(runner, 'resume_transport', side_effect=AssertionError('Cohort must not begin')), \
             self.assertRaisesRegex(gate.HeaderReadinessFailure, 'cache-unverified'):
            runner.run_v2(adb, lambda *parts: self.fail('No device payload'), build['sourceCommit'], [], ROOT, lambda *parts: self.fail('No focus action'))
        self.assertEqual(observed, ['installed-read', 'installed-verified', 'host-preparation-failed'])

    def test_all_original_timed_helpers_and_v1_runner_are_byte_unchanged(self):
        original = {
            'tools/gecko/chrome_first_tap_readiness.py': '27628987c416146274fc37bcc48a0537e5906b1d25e28def8d43dafe6be92216',
            'tools/gecko/chrome_header_readiness.py': '77590576542e0e5faeb88beaab59ae6950361dee88cb6c974260f611a92b26be',
            'tools/gecko/chrome_resume_readiness.py': 'cf02ea759b87e02781da02354c6930fcb6778ac62680c8ac5dbd2b18ee14bea6',
            'tests/gecko/run_chrome_collapse.py': 'edaa810f470717a45092cce966d451506d2817f9a41def33d62a1d83ed200acf',
        }
        for relative, sha256 in original.items():
            with self.subTest(relative=relative):
                self.assertEqual(digest(historical_bytes(relative)), sha256)

    def test_only_the_explicit_runner_hook_and_old_fake_edge_are_added(self):
        for relative in (RUNNER, OLD_TEST):
            raw = historical_bytes(relative)
            restored = before_image(raw, relative)
            self.assertEqual(pin(restored), BEFORE[relative])
            if relative == OLD_TEST:
                assertions = lambda value: [ast.dump(n, include_attributes=False) for n in ast.walk(ast.parse(value))
                    if isinstance(n, ast.Assert) or isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr.startswith('assert')]
                self.assertEqual(assertions(raw), assertions(restored))

    def test_finite_delta_check_rejects_relocated_duplicate_missing_or_other_changes(self):
        raw = historical_bytes(RUNNER)
        installed, prefix = ANCHOR.splitlines(keepends=True)
        changed = [raw.replace(HOOK, b'', 1), raw.replace(HOOK, HOOK+HOOK, 1),
            raw.replace(installed+HOOK, HOOK+installed, 1), raw+b'\n',
            raw.replace(b'first=True', b'first=False', 1)]
        for item in changed:
            with self.subTest(sha256=digest(item)), self.assertRaises(ValueError):
                before_image(item, RUNNER)
        old = historical_bytes(OLD_TEST)
        for item in (old.replace(MOCK, b'', 1), old.replace(MOCK, MOCK+MOCK, 1),
                     old.replace(b'self.assertFalse(partial[', b'self.assertTrue(partial[', 1)):
            with self.subTest(sha256=digest(item)), self.assertRaises(ValueError):
                before_image(item, OLD_TEST)


if __name__ == '__main__':
    unittest.main()
