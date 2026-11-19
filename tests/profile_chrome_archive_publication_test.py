"""Exercise exact case transport and the actual publication reader boundaries.

All fixtures are explicitly host-only. Real Git indexes and the unchanged CI
pack/restore implementation carry the complete bytes. The consumer test uses
all 40 phases and 41 native inputs from the existing counterfeit v3 fixture;
only unrelated performance workloads are outside its selected AST boundary.
No result here is Android execution or release qualification.
"""
import ast
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'tools'), str(ROOT/'tools/gecko'), str(ROOT/'tests')]
import chrome_collapse_case_storage as storage
import profile_chrome_collapse_archive_test as archive_fixture
import profile_navigation_v3_test as complete_fixture
from gecko_ci_bundle_test import BUNDLE
from profile_photo_publication_test import calls, execute, one, step_python, working_directory
from profile_release_navigation_v2_test import stage_actual_reader_blocks
from gecko import check_performance_evidence as performance_reader

UNSIGNED = ROOT/'tools/gecko/publish_ci.py'
PUBLISHER = ROOT/'tools/publish-gecko-release.py'
READER = ROOT/'tools/gecko/check_performance_evidence.py'
FULL = ROOT/'.github/workflows/browser-2_1-acceptance.yml'
PUBLISH = ROOT/'.github/workflows/publish-gecko-release.yml'
HELPER = 'tools/gecko/chrome_collapse_case_storage.py'
FULL_STEP = 'Require every original release acceptance gate'
PUBLISH_STEP = 'Verify original regressions, derived SDK provenance and signed public APK'
NAMES = ('chrome-collapse-case-360-1.json', 'chrome-collapse-case-412-1.json',
         'chrome-collapse-case-360-2.json')


def git(directory, *arguments, environment=None, binary=False):
    return subprocess.check_output(['git', '-c', 'user.name=Archive host fixture', '-c',
        'user.email=fixture@example.invalid', *arguments], cwd=directory, env=environment,
        stderr=subprocess.PIPE, text=not binary)


def unsigned_copy(directory, stage, tree=None):
    tree = tree or ast.parse(UNSIGNED.read_text())
    block = one((node for node in tree.body if isinstance(node, ast.For)
                 and any(isinstance(value, ast.Constant) and value.value == NAMES[0]
                         for value in ast.walk(node))), 'actual unsigned case-copy loop')
    execute([block], dict(out=directory, stage=stage, shutil=shutil), UNSIGNED)
    assert all((stage/name).read_bytes() == (directory/name).read_bytes() for name in NAMES), \
        'All three complete case originals must survive unsigned publication'


def consumer_nodes(tree=None):
    tree = tree or ast.parse(READER.read_text())
    function = one((node for node in tree.body if isinstance(node, ast.FunctionDef)
                    and node.name == 'verify_performance_evidence'), 'performance reader')
    first = one((i for i, node in enumerate(function.body)
                 if isinstance(node, ast.Assign) and calls(node, 'load_auto_collapse_cases')),
                'actual hydration before the original oracle')
    nodes = function.body[first:first+3]
    assert len(nodes) == 3 and isinstance(nodes[1], ast.Assign)
    assert len(calls(nodes[1], 'verify_auto_collapse')) == 1
    assert isinstance(nodes[2], ast.Assert)
    assert ast.unparse(nodes[2].test) == "visual['autoCollapse'] == chrome['autoCollapse']"
    return nodes


def consume(directory, source, apk, tree=None):
    """Execute the unchanged oracle on the actual reader's hydrated variable."""
    namespace = dict(directory=Path(directory), source=source,
        chrome=json.loads((Path(directory)/'compact-chrome-results.json').read_bytes()),
        visual=json.loads((Path(directory)/'ui-visual-results.json').read_bytes()),
        build={'currentSha256': apk}, load_auto_collapse_cases=performance_reader.load_auto_collapse_cases,
        verify_auto_collapse=performance_reader.verify_auto_collapse)
    execute(consumer_nodes(tree), namespace, READER)
    return namespace['auto_collapse']


class ArchiveTransportPublicationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='chrome-archive-transport-')
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        environment = patch.dict(os.environ, GITHUB_RUN_ID='123456', GITHUB_RUN_ATTEMPT='1')
        environment.start(); self.addCleanup(environment.stop)
        self.root = self.base/'source'; self.root.mkdir()
        git(self.root, 'init', '-q')
        (self.root/'.gitignore').write_text('work/\napp/build/\n')
        git(self.root, 'add', '.gitignore'); git(self.root, 'commit', '-qm', 'Host-only transport source')
        source = git(self.root, 'rev-parse', 'HEAD').strip()
        tree = git(self.root, 'rev-parse', 'HEAD^{tree}').strip()
        for name in (BUNDLE.INTEGRATION, BUNDLE.RELEASE, *BUNDLE.INPUT_DRIVER_EVIDENCE,
                     BUNDLE.SDK/'sdk-build-receipt.json', BUNDLE.SDK/'geckoview-caret.aar'):
            target = self.root/name; target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b'Host-only exact transport bytes; not an APK or SDK.\r\n')
        self.build = self.base/'build.tar.gz'
        BUNDLE.pack(self.root, self.build, 'build')
        self.phase = self.clone('phase'); BUNDLE.restore(self.phase, self.build, 'build')
        self.directory = self.phase/BUNDLE.OUT
        # Rebind only this declared fixture's owners to the real disposable Git
        # source used by the transport. Keep every provider string as a string.
        value = json.dumps(archive_fixture.fixture(), ensure_ascii=False)
        self.inline = json.loads(value.replace(archive_fixture.SOURCE, source).replace(archive_fixture.TREE, tree))
        for case in self.inline['cases']:
            for row in case['eventTransfer']['events']:
                raw = row['rawUtf8'].encode('utf-8')
                row['receipt'].update(payloadBytes=len(raw), payloadSha256=hashlib.sha256(raw).hexdigest())
        self.source, self.apk = source, archive_fixture.APK
        self.manifest = storage.store_auto_collapse_cases(self.inline, self.directory, source, self.apk)
        for name in ('compact-chrome-results.json', 'ui-visual-results.json'):
            (self.directory/name).write_bytes(archive_fixture.encoded({'autoCollapse': self.manifest}))
        self.archive = self.base/'ui.tar.gz'
        self.packed = BUNDLE.pack(self.phase, self.archive, 'phase', 'ui')

    def clone(self, name):
        target = self.base/name
        subprocess.run(['git', 'clone', '-q', '--no-hardlinks', str(self.root), str(target)],
                       check=True, capture_output=True)
        return target

    def consumer(self, name):
        target = self.clone(name); BUNDLE.restore(target, self.build, 'build')
        return target

    def test_original_ci_bundle_unsigned_copy_and_signed_git_index_keep_every_byte(self):
        target = self.consumer('consumer')
        restored = BUNDLE.restore(target, self.archive, 'phase', 'ui')
        self.assertEqual(restored['buildIndexSha256'], BUNDLE.digest(target/BUNDLE.BUILD_INDEX))
        self.assertTrue({str(BUNDLE.OUT/name) for name in NAMES} <= {row['path'] for row in restored['files']})
        directory = target/BUNDLE.OUT
        self.assertEqual(storage.load_auto_collapse_cases(self.manifest, directory, self.source, self.apk), self.inline)
        unsigned = self.base/'unsigned'; unsigned.mkdir()
        unsigned_copy(directory, unsigned)
        tree = ast.parse(PUBLISHER.read_text())
        start = one((i for i, node in enumerate(tree.body) if isinstance(node, ast.Assign)
                     and any(isinstance(t, ast.Name) and t.id == 'performance_files' for t in node.targets)), 'staging file list')
        end = one((i for i, node in enumerate(tree.body) if isinstance(node, ast.For)
                   and isinstance(node.iter, ast.Name) and node.iter.id == 'performance_files'), 'real file-copy loop')
        stage = self.base/'signed'; stage.mkdir()
        namespace = dict(version_code=108, photo_upload=None, chrome={'autoCollapse': self.manifest},
            root=self.root, stage=stage, shutil=shutil, args=SimpleNamespace(evidence=directory),
            roadmap_release=False, sdk_build=None, caret=None, template_release=False,
            resource_release=False, browser_release=False, fingerprint_release=False,
            worker_timezone_release=False, chain_files=[])
        execute(tree.body[start:end], namespace, PUBLISHER)
        self.assertTrue(set(NAMES) <= set(namespace['performance_files']))
        for name in namespace['performance_files']:
            if not (directory/name).exists():
                self.assertNotIn(name, NAMES)
                (directory/name).write_bytes(b'Controlled unrelated release input.\n')
        execute([tree.body[end]], namespace, PUBLISHER)
        add = one((node for node in tree.body if isinstance(node, ast.Expr)
                   and isinstance(node.value, ast.Call) and ast.unparse(node.value.func) == 'subprocess.run'
                   and node.value.args and isinstance(node.value.args[0], ast.List)
                   and [getattr(v, 'value', None) for v in node.value.args[0].elts[:2]] == ['git', 'add']), 'real release git-add')
        environment = dict(os.environ, GIT_INDEX_FILE=str(self.base/'signed-index'), GIT_WORK_TREE=str(stage))
        # This legacy release does not stage optional Chromium assets.
        namespace.update(env=environment, subprocess=subprocess, manual_raw=None,
                         authorization_raw=None, chromium_release_files=[], manifest={'parts': []})
        arguments = eval(compile(ast.Expression(add.value.args[0]), str(PUBLISHER), 'eval'), namespace)
        for name in arguments[4:]:
            if not (stage/name).exists():
                self.assertNotIn(name, NAMES)
                (stage/name).parent.mkdir(parents=True, exist_ok=True)
                (stage/name).write_bytes(b'Controlled unrelated index input.\n')
        execute([add], namespace, PUBLISHER)
        indexed = git(self.root, 'ls-files', environment=environment).splitlines()
        self.assertTrue(set(NAMES) <= set(indexed))
        for name in NAMES:
            original = (self.directory/name).read_bytes()
            self.assertEqual((directory/name).read_bytes(), original)
            self.assertEqual((unsigned/name).read_bytes(), original)
            self.assertEqual(git(self.root, 'show', ':'+name, environment=environment, binary=True), original)
        self.assertEqual(git(self.root, 'status', '--porcelain'), '')

    def test_missing_tampered_or_mixed_run_and_build_phase_members_fail_before_restore(self):
        with tarfile.open(self.archive, 'r:gz') as archive:
            originals = {member.name: archive.extractfile(member).read() for member in archive.getmembers()}
        for mutation in ('missing', 'tampered', 'source', 'run', 'attempt', 'build'):
            files = dict(originals)
            manifest = json.loads(files['_ci_bundle.json'])
            first = str(BUNDLE.OUT/NAMES[0])
            if mutation == 'missing': files.pop(first)
            elif mutation == 'tampered': files[first] += b'\n'
            elif mutation == 'source': manifest['sourceCommit'] = 'f'*40
            elif mutation == 'run': manifest['runId'] = '654321'
            elif mutation == 'attempt': manifest['runAttempt'] = '2'
            else: manifest['buildIndexSha256'] = 'f'*64
            files['_ci_bundle.json'] = archive_fixture.encoded(manifest)
            archive_path = self.base/('mutant-'+mutation+'.tar.gz')
            with tarfile.open(archive_path, 'w:gz') as archive:
                for name, raw in files.items():
                    info = tarfile.TarInfo(name); info.size = len(raw)
                    archive.addfile(info, io.BytesIO(raw))
            target = self.consumer('rejected-'+mutation)
            with self.subTest(mutation=mutation), self.assertRaises(AssertionError):
                BUNDLE.restore(target, archive_path, 'phase', 'ui')
            self.assertTrue(all(not (target/BUNDLE.OUT/name).exists() for name in NAMES))

    def test_original_privacy_cap_and_nonregular_file_rejections_remain_in_transport(self):
        path = self.directory/NAMES[0]
        original = path.read_bytes(); path.unlink()
        outside = self.base/'outside.json'; outside.write_bytes(original)
        path.symlink_to(outside)
        stage = self.base/'unsafe-public'; stage.mkdir()
        with self.assertRaisesRegex(AssertionError, 'regular file'):
            unsigned_copy(self.directory, stage)
        with self.assertRaisesRegex(AssertionError, 'symbolic links'):
            BUNDLE.pack(self.phase, self.base/'unsafe.tar.gz', 'phase', 'ui')
        path.unlink(); path.write_bytes(b' '*(16*1024*1024+1))
        with self.assertRaisesRegex(ValueError, 'rejected bounded capture'):
            BUNDLE.pack(self.phase, self.base/'oversized.tar.gz', 'phase', 'ui')
        self.assertEqual(path.stat().st_size, 16*1024*1024+1, 'The gate must not truncate the rejected original')


class ArchiveReaderPublicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Cache only the existing fixture's actual missing Git-object read;
        # this never manufactures source bytes or replaces any SDK validator.
        complete_fixture.previous.ChromeCollapseV2Controls.setUpClass()
        cls.addClassCleanup(complete_fixture.previous.ChromeCollapseV2Controls.tearDownClass)

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='chrome-archive-reader-')
        self.addCleanup(temporary.cleanup); self.directory = Path(temporary.name)
        self.source, self.apk = 'a'*40, 'c'*64
        self.inline = complete_fixture.CollapseContractTests().fixture()
        self.inline['buildIdentity']['sdkBuildIdentity'] = dict(sourceCommit=self.source,
            sourceTree='b'*40, runId='123456', runAttempt='1')
        complete_fixture.previous.reseal(self.inline)
        self.expected = performance_reader.verify_auto_collapse(self.inline, self.source, self.apk)
        self.manifest = storage.store_auto_collapse_cases(self.inline, self.directory, self.source, self.apk)
        self.write_reports()

    def write_reports(self):
        for name in ('compact-chrome-results.json', 'ui-visual-results.json'):
            (self.directory/name).write_bytes(archive_fixture.encoded({'autoCollapse': self.manifest}))

    def test_actual_main_reader_hydrates_before_all_original_native_ui_and_event_checks(self):
        self.assertEqual(consume(self.directory, self.source, self.apk), self.expected)
        self.assertEqual((self.expected['cases'], self.expected['phasesPerCase'], self.expected['actualInputsPerCase']), (3, 40, 41))
        reference = self.manifest['caseFiles'][0]
        path = self.directory/reference['name']
        case = json.loads(path.read_bytes())
        # Fully rehash this hostile archive, so transport hashes alone cannot
        # satisfy the old actual-target predicate after hydration.
        case['actualAndroidInputs'][13]['point'] = [200, 1800]
        raw = archive_fixture.encoded(case); path.write_bytes(raw)
        reference.update(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
        self.write_reports()
        storage.load_auto_collapse_cases(self.manifest, self.directory, self.source, self.apk)
        with self.assertRaises(AssertionError): consume(self.directory, self.source, self.apk)

    def test_consumer_rejects_missing_original_and_mixed_identity_and_different_report_index(self):
        path = self.directory/NAMES[1]; raw = path.read_bytes(); path.unlink()
        with self.assertRaisesRegex(ValueError, 'missing or unsafe'):
            consume(self.directory, self.source, self.apk)
        path.write_bytes(raw)
        with self.assertRaisesRegex(ValueError, 'source or APK'):
            consume(self.directory, self.source, 'e'*64)
        visual = {'autoCollapse': copy.deepcopy(self.manifest)}
        visual['autoCollapse']['caseFiles'][0]['bytes'] += 1
        (self.directory/'ui-visual-results.json').write_bytes(archive_fixture.encoded(visual))
        with self.assertRaises(AssertionError): consume(self.directory, self.source, self.apk)
        tree = ast.parse(READER.read_text())
        function = one((n for n in tree.body if isinstance(n, ast.FunctionDef)
                        and n.name == 'verify_performance_evidence'), 'reader function')
        function.body = [n for n in function.body if not (isinstance(n, ast.Assign) and calls(n, 'verify_auto_collapse'))]
        with self.assertRaises(AssertionError): consumer_nodes(tree)

    def test_all_actual_mandatory_performance_entrypoints_resolve_the_original_cases(self):
        def selected(directory, source):
            self.assertEqual(Path(directory), self.directory); self.assertEqual(source, self.source)
            return consume(directory, source, self.apk)
        # Run the actual dispatch loop. Other original gates keep their own
        # independent suites; this test controls only those unrelated inputs.
        full = step_python(yaml.safe_load(FULL.read_text()), 'verify', FULL_STEP)
        loop = one((n for n in full.body if isinstance(n, ast.For)
                    and any(isinstance(v, ast.Name) and v.id == 'verify_performance_evidence'
                            for v in ast.walk(n.iter))), 'mandatory complete-acceptance reader dispatch')
        namespace = {v.id: (selected if v.id == 'verify_performance_evidence' else lambda *_: None)
                     for v in loop.iter.elts}
        namespace.update(directory=self.directory, source=self.source)
        execute([loop], namespace, FULL)
        actual_publisher = ast.parse(PUBLISHER.read_text())
        publisher_gate = one((n for n in actual_publisher.body if isinstance(n, ast.If)
                              and calls(n, 'verify_performance_evidence')), 'publisher original performance gate')
        published = step_python(yaml.safe_load(PUBLISH.read_text()), 'publish', PUBLISH_STEP)
        published_gate = one((n for n in published.body if isinstance(n, ast.If)
                              and calls(n, 'verify_performance_evidence')), 'published original performance gate')
        self.assertEqual(ast.unparse(publisher_gate.test), 'version_code >= 43')
        self.assertEqual(ast.unparse(published_gate.test), "m['versionCode'] >= 43")
        assignment = one((n for n in publisher_gate.body if isinstance(n, ast.Assign)), 'publisher performance assignment')
        assertion = one((n for n in published_gate.body if isinstance(n, ast.Assert)), 'published manifest comparison')
        execute([assignment], dict(args=SimpleNamespace(evidence=self.directory, source=self.source),
                                  verify_performance_evidence=selected), PUBLISHER)
        namespace = dict(pathlib=__import__('pathlib'), verify_performance_evidence=lambda directory, source:
            selected(self.directory if directory == Path('.') else directory, source),
            m={'sourceCommit': self.source, 'performanceRegression': self.expected})
        execute([assertion], namespace, PUBLISH)
        namespace['m']['performanceRegression'] = dict(self.expected, cases=2)
        with self.assertRaises(AssertionError): execute([assertion], namespace, PUBLISH)
        (self.directory/NAMES[2]).unlink()
        with self.assertRaises(ValueError): execute([loop], {**namespace, **{v.id: selected if v.id == 'verify_performance_evidence' else lambda *_: None for v in loop.iter.elts}, 'directory': self.directory, 'source': self.source}, FULL)
        with self.assertRaises(ValueError): execute([assertion], namespace, PUBLISH)

    def test_actual_stage_has_lazy_guard_and_final_workflow_pins_exact_helper_source(self):
        stage = self.directory/'stage'; stage.mkdir()
        stage_actual_reader_blocks(stage)
        tree = ast.parse(PUBLISHER.read_text())
        guard = one((n for n in tree.body if isinstance(n, ast.If)
                     and ast.unparse(n.test) == 'sdk_build is not None'
                     and any(isinstance(v, ast.Call) and ast.unparse(v.func) == 'shutil.copy2' for v in ast.walk(n))), 'actual SDK reader copy block')
        execute([guard], dict(root=ROOT, stage=stage, sdk_build={}, caret={'controlledImeEnvironment': True}, shutil=shutil), PUBLISHER)
        for name in (*NAMES, 'compact-chrome-results.json', 'ui-visual-results.json'):
            shutil.copy2(self.directory/name, stage/name)
        script = """import importlib,json,pathlib,sys
stage=pathlib.Path.cwd()
for path in (stage,stage/'tools',stage/'tools/gecko'):sys.path.insert(0,str(path))
report=json.loads((stage/'compact-chrome-results.json').read_bytes())['autoCollapse']
for prefix in ('tools.gecko.','gecko.',''):
 module=importlib.import_module(prefix+'chrome_collapse_case_storage')
 reader=importlib.import_module(prefix+'check_performance_evidence')
 assert pathlib.Path(module.__file__).is_relative_to(stage)
 assert reader.load_auto_collapse_cases is module.load_auto_collapse_cases
 value=module.load_auto_collapse_cases(report,stage,'a'*40,'c'*64)
 assert len(value['cases'])==3 and len(value['cases'][0]['observations'])==40
print('all complete originals loaded using only actual staged dependencies')
"""
        environment = dict(os.environ); environment.pop('PYTHONPATH', None)
        def probe():
            return subprocess.run([sys.executable, '-I', '-c', script], cwd=stage,
                                  env=environment, text=True, capture_output=True, timeout=30)
        result = probe(); self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        (stage/'tools/gecko/caret_ime_guard.py').unlink()
        result = probe(); self.assertNotEqual(result.returncode, 0); self.assertIn('caret_ime_guard', result.stderr)
        workflow = step_python(yaml.safe_load(PUBLISH.read_text()), 'publish', PUBLISH_STEP)
        pinned = one((n for n in workflow.body if isinstance(n, ast.If)
                      and any(isinstance(v, ast.Constant) and v.value == HELPER for v in ast.walk(n))), 'source-bound archive helper gate')
        self.assertEqual(ast.unparse(pinned.test), "m['versionCode'] >= 108")
        names = one((n for n in pinned.body if isinstance(n, ast.For)), 'actual source-byte comparison loop').iter
        repository = self.directory/'source'; repository.mkdir(); git(repository, 'init', '-q')
        for value in names.elts:
            name = value.value
            target = repository/name; target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT/name).read_bytes())
        git(repository, 'add', '.'); git(repository, 'commit', '-qm', 'Real current checker source bytes')
        source = git(repository, 'rev-parse', 'HEAD').strip()
        namespace = dict(m={'versionCode': 108, 'sourceCommit': source}, pathlib=__import__('pathlib'), subprocess=subprocess)
        with working_directory(repository): execute([pinned], namespace, PUBLISH)
        (repository/HELPER).write_bytes((repository/HELPER).read_bytes()+b'\n# unreviewed\n')
        with working_directory(repository), self.assertRaisesRegex(AssertionError, 'differs from tested source'):
            execute([pinned], namespace, PUBLISH)


if __name__ == '__main__':
    unittest.main()
