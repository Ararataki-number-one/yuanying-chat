"""Host-only copy and local Git publication controls; no Android acceptance."""
import ast
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('ci_git_publish', ROOT/'tools/gecko/ci_git_publish.py')
P = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(P)


# Actual 33/1 public Git stderr, with only runner timestamps removed.
ACTUAL_REMOTE_CAS_STDERR = (
    'remote: warning: See https://gh.io/lfs for more information.        \n'
    "remote: warning: File PocketChat-2.0.33-arm64-v8a.apk.part01 is 56.58 MB; this is larger than GitHub's recommended maximum file size of 50.00 MB        \n"
    "remote: warning: File PocketChat-2.0.33-arm64-v8a.apk.part00 is 57.22 MB; this is larger than GitHub's recommended maximum file size of 50.00 MB        \n"
    'remote: warning: GH001: Large files detected. You may want to try Git Large File Storage - https://git-lfs.github.com.        \n'
    'To https://github.com/Ararataki-number-one/yuanying-chat\n'
    " ! [remote rejected] 0de4d5cecfdb4a8d64919368b1925a2404616ffa -> apk/gecko-integration-build-20261003 (cannot lock ref 'refs/heads/apk/gecko-integration-build-20261003': is at 8cfcdab8ee95ad623f58a5d477daced01f9e0f22 but expected b0c4c0ae7f8de409273e8af1c7a8cf49ca2e78b9)\n"
    "error: failed to push some refs to 'https://github.com/Ararataki-number-one/yuanying-chat'\n"
)


class PublicationArtifactCopyTests(unittest.TestCase):
    def network_scope_copy(self):
        helper = ROOT/'tools/gecko/network_scope_artifacts.py'
        spec = importlib.util.spec_from_file_location('actual_network_scope_artifacts', helper)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        return module.copy_network_scope_evidence

    def network_scope_files(self):
        values = {'network-client-binding-results.json': b'{"status":"failed"}\r\n',
                  'network-client-binding-native-event.raw.json': b'{"original":true}\r\n',
                  'network-client-binding-adb-0001-stdout.raw.log': b'\x00\xfforiginal provider bytes\r\n',
                  'network-client-binding-adb-0001-stderr.raw.log': b'',
                  'network-client-binding-adb-10000-stdout.raw.log': b'original final error\xc2\n'}
        for implementation in ('desktop', 'android'):
            stem = 'window-network-identity-' + implementation + '-host-results'
            values[stem + '.json'] = b'{"status":"failed","hostOnly":true}\n'
            for name in ('manifest.json', 'compile.stdout.raw', 'compile.stderr.raw',
                         'execute.stdout.raw', 'execute.stderr.raw',
                         'device-projection.stdout.raw', 'device-projection.stderr.raw'):
                values[stem + '-raw/' + name] = (b'' if name.endswith('stderr.raw')
                                                else (implementation + '/' + name).encode() + b'\r\n\x00\xff')
        return values

    def test_actual_network_scope_copy_preserves_exact_owned_binary_and_empty_streams(self):
        copy = self.network_scope_copy(); evidence = self.network_scope_files()
        excluded = {'network-client-binding-private.json': b'excluded',
                    'network-client-binding-private.log': b'excluded',
                    'network-client-binding-adb-0000-stdout.raw.log': b'excluded',
                    'network-client-binding-adb-1-stdout.raw.log': b'excluded',
                    'network-client-binding-adb-00001-stdout.raw.log': b'excluded',
                    'network-client-binding-adb-0001-password.raw.log': b'excluded',
                    'network-client-binding-adb-0001-stdout.raw.log.jks': b'excluded',
                    'window-network-identity-private-host-results.json': b'excluded',
                    'window-network-identity-desktop-host-results-raw/private.txt': b'excluded',
                    'window-network-identity-desktop-host-results-raw/private.jks': b'excluded',
                    'window-network-identity-desktop-host-results-raw/classes/Fixture.class': b'excluded',
                    'window-network-identity-desktop-host-results-raw/src/Fixture.java': b'excluded'}
        with tempfile.TemporaryDirectory() as temporary:
            out, stage = Path(temporary)/'out', Path(temporary)/'stage'; out.mkdir(); stage.mkdir()
            for name, data in {**evidence, **excluded}.items():
                path = out/name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(data)
            self.assertEqual(set(copy(out, stage)), set(evidence))
            self.assertEqual({path.relative_to(stage).as_posix() for path in stage.rglob('*')
                              if path.is_file()}, set(evidence))
            for name, data in evidence.items():self.assertEqual((stage/name).read_bytes(), data)
            for name, data in excluded.items():self.assertEqual((out/name).read_bytes(), data)

    def test_network_scope_copy_refuses_source_and_destination_symlinks(self):
        copy = self.network_scope_copy()
        for location in ('source-file', 'source-directory', 'destination-file', 'destination-directory',
                         'source-root', 'destination-root'):
            with self.subTest(location=location), tempfile.TemporaryDirectory() as temporary:
                base = Path(temporary); out, stage = base/'out', base/'stage'; out.mkdir(); stage.mkdir()
                outside = base/'outside'; outside.mkdir(); (outside/'sentinel').write_bytes(b'unchanged')
                name = 'window-network-identity-desktop-host-results-raw'
                if location == 'source-file':(out/'network-client-binding-results.json').symlink_to(outside/'sentinel')
                elif location == 'source-directory':(out/name).symlink_to(outside, target_is_directory=True)
                elif location == 'destination-file':
                    (out/'network-client-binding-results.json').write_bytes(b'{}')
                    (stage/'network-client-binding-results.json').symlink_to(outside/'sentinel')
                elif location == 'destination-directory':
                    (out/name).mkdir(); (out/name/'manifest.json').write_bytes(b'{}')
                    (stage/name).symlink_to(outside, target_is_directory=True)
                elif location == 'source-root':out.rmdir(); out.symlink_to(outside, target_is_directory=True)
                else:stage.rmdir(); stage.symlink_to(outside, target_is_directory=True)
                with self.assertRaisesRegex(AssertionError, 'symlink'):copy(out, stage)
                self.assertEqual((outside/'sentinel').read_bytes(), b'unchanged')
                self.assertEqual({path.name for path in outside.iterdir()}, {'sentinel'})

    def test_network_scope_copy_refuses_symlink_ancestors_of_both_roots(self):
        copy = self.network_scope_copy()
        for side in ('source', 'destination'):
            with self.subTest(side=side), tempfile.TemporaryDirectory() as temporary:
                base = Path(temporary); outside = base/'outside'; outside.mkdir()
                link = base/'linked-parent'; link.symlink_to(outside, target_is_directory=True)
                out = (link if side == 'source' else base/'source')/'gecko-integration'
                stage = (link if side == 'destination' else base/'output')/'public'
                out.mkdir(parents=True); stage.mkdir(parents=True)
                (out/'network-client-binding-results.json').write_bytes(b'original synthetic report\n')
                before = {path.relative_to(outside).as_posix(): path.read_bytes()
                          for path in outside.rglob('*') if path.is_file()}
                self.assertFalse(out.is_symlink()); self.assertFalse(stage.is_symlink())
                with self.assertRaisesRegex(AssertionError, 'ancestor symlink'):copy(out, stage)
                self.assertEqual({path.relative_to(outside).as_posix(): path.read_bytes()
                                  for path in outside.rglob('*') if path.is_file()}, before)
                self.assertEqual(list(stage.iterdir()), [])

    def test_network_scope_copy_refuses_nonregular_and_over_one_gib_files(self):
        copy = self.network_scope_copy()
        for invalid in ('directory', 'over-limit'):
            with self.subTest(invalid=invalid), tempfile.TemporaryDirectory() as temporary:
                out, stage = Path(temporary)/'out', Path(temporary)/'stage'; out.mkdir(); stage.mkdir()
                target = out/'network-client-binding-results.json'
                if invalid == 'directory':target.mkdir()
                else:
                    with target.open('wb') as stream:stream.truncate(1024 ** 3 + 1)
                with self.assertRaisesRegex(AssertionError, 'Invalid network evidence file'):copy(out, stage)
                self.assertEqual(list(stage.iterdir()), [])

    def test_network_scope_copy_is_called_by_real_publisher_and_missing_files_stay_missing(self):
        tree = ast.parse((ROOT/'tools/gecko/publish_ci.py').read_bytes())
        calls = [node for node in tree.body if isinstance(node, ast.Expr)
                 and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name)
                 and node.value.func.id == 'copy_network_scope_evidence']
        self.assertEqual(len(calls), 1)
        self.assertEqual(ast.unparse(calls[0]), 'copy_network_scope_evidence(out, stage)')
        with tempfile.TemporaryDirectory() as temporary:
            out, stage = Path(temporary)/'out', Path(temporary)/'stage'; out.mkdir(); stage.mkdir()
            self.assertEqual(self.network_scope_copy()(out, stage), [])
            self.assertEqual(list(stage.iterdir()), [])

    def test_network_scope_helper_import_is_isolated_and_has_no_publisher_side_effects(self):
        helper = ROOT/'tools/gecko/network_scope_artifacts.py'
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary); copied = base/helper.name; copied.write_bytes(helper.read_bytes())
            spec = importlib.util.spec_from_file_location('standalone_network_scope_artifacts', copied)
            module = importlib.util.module_from_spec(spec)
            with patch.object(subprocess, 'run', side_effect=AssertionError('Import must not run commands')), \
                 patch.object(subprocess, 'check_output', side_effect=AssertionError('Import must not read Git')), \
                 patch('sys.dont_write_bytecode', True):
                spec.loader.exec_module(module)
            self.assertEqual({p.name for p in base.iterdir()}, {helper.name})
            self.assertEqual(module.NETWORK_IDENTITY_RAW_DIRS, frozenset(
                'window-network-identity-' + platform + '-host-results-raw'
                for platform in ('desktop', 'android')))
            self.assertEqual(len(module.NETWORK_IDENTITY_RAW_FILES), 7)
            self.assertEqual(len(module.NETWORK_SCOPE_REPORT_FILES), 4)

    def test_both_publishers_import_same_helper_and_signed_staging_keeps_raw_git_paths(self):
        paths = (ROOT/'tools/gecko/publish_ci.py', ROOT/'tools/publish-gecko-release.py')
        for path, module in zip(paths, ('network_scope_artifacts', 'gecko.network_scope_artifacts')):
            tree = ast.parse(path.read_bytes())
            imports = [node for node in tree.body if isinstance(node, ast.ImportFrom)
                       and node.module == module]
            self.assertEqual(len(imports), 1)
            self.assertEqual([(row.name, row.asname) for row in imports[0].names],
                             [('copy_network_scope_evidence', None)])
            self.assertFalse(any(isinstance(node, ast.FunctionDef) and node.name == 'copy_network_scope_evidence'
                                 for node in tree.body))
        signed = paths[1]; tree = ast.parse(signed.read_bytes())
        staging = [node for node in tree.body if isinstance(node, ast.Expr)
                   and isinstance(node.value, ast.Call) and ast.unparse(node.value.func) == 'performance_files.extend'
                   and any(isinstance(child, ast.Call) and isinstance(child.func, ast.Name)
                           and child.func.id == 'copy_network_scope_evidence' for child in ast.walk(node))]
        self.assertEqual(len(staging), 1)
        self.assertEqual(ast.unparse(staging[0]),
                         'performance_files.extend(copy_network_scope_evidence(args.evidence, stage))')
        helper_copy = [node for node in tree.body if isinstance(node, ast.Expr)
                       and isinstance(node.value, ast.Call) and ast.unparse(node.value.func) == 'shutil.copy2'
                       and any(isinstance(child, ast.Constant) and child.value == 'tools/gecko/network_scope_artifacts.py'
                               for child in ast.walk(node))]
        self.assertEqual(len(helper_copy), 1)
        git_add = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                   and ast.unparse(node.func) == 'subprocess.run' and node.args
                   and isinstance(node.args[0], ast.List)
                   and any(isinstance(child, ast.Constant) and child.value == 'add' for child in node.args[0].elts)]
        self.assertEqual(len(git_add), 1)
        self.assertTrue(any(isinstance(child, ast.Starred) and isinstance(child.value, ast.Name)
                            and child.value.id == 'performance_files' for child in git_add[0].args[0].elts))
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary); out, stage = base/'out', base/'signed'; out.mkdir(); stage.mkdir()
            evidence = self.network_scope_files()
            for name, data in evidence.items():
                path = out/name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(data)
            namespace = dict(args=type('Args', (), {'evidence': out})(), stage=stage,
                             performance_files=['original-required-file.json'],
                             copy_network_scope_evidence=self.network_scope_copy())
            exec(compile(ast.Module(body=staging, type_ignores=[]), str(signed), 'exec'), namespace)
            self.assertEqual(set(namespace['performance_files']), {'original-required-file.json'} | set(evidence))
            for name, data in evidence.items():self.assertEqual((stage/name).read_bytes(), data)
            # Execute the actual module-copy statement; importing the staged
            # standalone helper must not depend on the repository checkout.
            (stage/'tools/gecko').mkdir(parents=True)
            exec(compile(ast.Module(body=helper_copy, type_ignores=[]), str(signed), 'exec'),
                 dict(root=ROOT, stage=stage, shutil=shutil))
            self.assertEqual((stage/'tools/gecko/network_scope_artifacts.py').read_bytes(),
                             (ROOT/'tools/gecko/network_scope_artifacts.py').read_bytes())

    def test_actual_event_sequence_copy_loop_retains_only_six_original_files(self):
        publisher = ROOT/'tools/gecko/publish_ci.py'
        loops = [node for node in ast.parse(publisher.read_text()).body if isinstance(node, ast.For)
                 and any(isinstance(value, ast.Constant) and isinstance(value.value, str)
                         and value.value.startswith('device-event-sequence') for value in ast.walk(node.iter))]
        self.assertEqual(len(loops), 1)
        evidence = {
            'device-event-sequence-failure.json': b'{"status":"failed","diagnosticOnly":true}\r\n',
            'device-event-sequence-filtered.log': 'original filtered snapshot\r\n原始\n'.encode(),
            'device-event-sequence-expected.stdout.log': b'\x00\xffunparsed original provider bytes\r\n',
            'device-event-sequence-expected.stderr.log': b'',
            'device-event-sequence-current.stdout.log': b'{"sequence":2}\n',
            'device-event-sequence-current.stderr.log': b'original error \xc2\n',
        }
        self.assertEqual(ast.literal_eval(loops[0].iter), list(evidence))
        excluded = {'device-event-sequence-private.txt': b'not declared',
                    'device-event-sequence-private.log': b'not declared',
                    'device-event-sequence-private.json': b'not declared',
                    'device-event-sequence-filtered.txt': b'not declared',
                    'device-event-sequence.json': b'not declared',
                    'device-event-sequence-fixture.apk': b'synthetic executable excluded',
                    'device-event-sequence-fixture.jks': b'synthetic key excluded',
                    'device-event-sequence-fixture.p12': b'synthetic key excluded'}
        with tempfile.TemporaryDirectory() as temporary:
            out, stage = Path(temporary)/'out', Path(temporary)/'stage'
            out.mkdir(); stage.mkdir()
            for name, data in {**evidence, **excluded}.items():(out/name).write_bytes(data)
            exec(compile(ast.Module(body=loops, type_ignores=[]), str(publisher), 'exec'),
                 {'out': out, 'stage': stage, 'shutil': shutil})
            self.assertEqual({path.name for path in stage.iterdir()}, set(evidence))
            for name, data in evidence.items():self.assertEqual((stage/name).read_bytes(), data)
            for name, data in excluded.items():self.assertEqual((out/name).read_bytes(), data)

    def test_failed_driver_build_has_only_the_declared_diagnostic_upload(self):
        source = (ROOT / '.github/workflows/gecko-integration.yml').read_text()
        part = source.split('    - name: Preserve native input build signature diagnostics\n', 1)[1].split('\n    - ', 1)[0]
        self.assertIn('      if: always()\n', part)
        paths = part.split('        path: |\n', 1)[1].split('        if-no-files-found:', 1)[0]
        self.assertEqual({line.strip() for line in paths.splitlines() if line.strip()}, {
            'work/gecko-integration/native-input-driver-signature-stdout.log',
            'work/gecko-integration/native-input-driver-signature-stderr.log',
            'work/gecko-integration/native-input-driver-signature-api.json',
            'work/gecko-integration/native-input-driver-signature-api-stdout.log',
            'work/gecko-integration/native-input-driver-signature-api-stderr.log',
            'work/native-input-driver-build/strict/signed.apk'})
        for name in ('Publish unsigned build for local original signing',
                     'Seal one source/run-bound build for every Android phase',
                     'Transfer exact compiled APKs and SDK inputs'):
            step = source.split('    - name: ' + name + '\n', 1)[1].split('\n    - ', 1)[0]
            self.assertNotIn('if: always()', step)

    def test_signature_host_failure_upload_uses_only_the_explicit_public_logs(self):
        source = (ROOT / '.github/workflows/gecko-integration.yml').read_text()
        part = source.split('    - name: Preserve native input signature host diagnostics\n', 1)[1].split('\n    - ', 1)[0]
        self.assertIn('      if: always()\n', part)
        paths = part.split('        path: |\n', 1)[1].split('        if-no-files-found:', 1)[0]
        expected = {'work/gecko-integration/native-input-signature-api-host-results.json'}
        expected.update('work/gecko-integration/native-input-signature-api-host-' + label + '-' + stream + '.log'
                        for label in ('compile', 'policy', 'signed', 'unsigned', 'tampered')
                        for stream in ('stdout', 'stderr'))
        self.assertEqual({line.strip() for line in paths.splitlines() if line.strip()}, expected)

    def test_actual_input_driver_copy_loops_preserve_failure_bytes_but_exclude_apk_and_keys(self):
        publisher=ROOT/'tools/gecko/publish_ci.py'
        loops=[node for node in ast.parse(publisher.read_text()).body if isinstance(node,ast.For)
               and any(isinstance(value,ast.Constant) and isinstance(value.value,str)
                       and value.value.startswith('native-input-') for value in ast.walk(node.iter))]
        self.assertEqual(len(loops),1)
        evidence={'native-input-driver-build.json':b'{"testOnly":true}\r\n',
                  'native-input-driver-signature-api.json':b'{"status":"failed"}\r\n',
                  'native-input-driver-signature-api-stdout.log':b'{"status":"failed"}\r\n',
                  'native-input-driver-signature-api-stderr.log':b'original API diagnostics \xc2\n',
                  'native-input-baseline-scroll-results.json':b'{"status":"failed"}',
                  'native-input-baseline-scroll-stdout.log':b'original \xc2\n',
                  'native-input-current-scroll-failure.txt':b'timeout\n'}
        excluded={'native-input-driver.apk':b'private test executable',
                  'native-input-driver.jks':b'private synthetic key',
                  'native-input-driver.p12':b'private synthetic key'}
        with tempfile.TemporaryDirectory() as temporary:
            out=Path(temporary)/'out';stage=Path(temporary)/'stage';out.mkdir();stage.mkdir()
            for name,data in {**evidence,**excluded}.items():(out/name).write_bytes(data)
            exec(compile(ast.Module(body=loops,type_ignores=[]),str(publisher),'exec'),
                 {'out':out,'stage':stage,'shutil':shutil})
            self.assertEqual({p.name for p in stage.iterdir()},set(evidence))
            for name,data in evidence.items():self.assertEqual((stage/name).read_bytes(),data)

    def test_actual_network_settings_copy_loops_publish_evidence_without_keys(self):
        publisher = ROOT/'tools/gecko/publish_ci.py'
        tree = ast.parse(publisher.read_text(), filename=str(publisher))
        loops = [node for node in tree.body if isinstance(node, ast.For)
                 and any(isinstance(value, ast.Constant) and isinstance(value.value, str)
                         and value.value.startswith('network-settings-')
                         for value in ast.walk(node.iter))]
        self.assertTrue(loops, 'Publisher has no network settings evidence copy loop')
        # Execute only the source-owned copy loops, without publisher setup or Git.
        for loop in loops:
            for call in (node for node in ast.walk(loop) if isinstance(node, ast.Call)):
                self.assertIsInstance(call.func, ast.Attribute)
                self.assertIsInstance(call.func.value, ast.Name)
                self.assertIn((call.func.value.id, call.func.attr), (('out', 'glob'), ('shutil', 'copy2')))

        names = [f'network-settings-{kind}-{suffix}'
                 for kind in ('application', 'internal', 'retry')
                 for suffix in ('results.json', 'log.txt', 'final.png')]
        names += [f'network-settings-{kind}-{platform}-host-results.json'
                  for kind in ('receipt', 'provider', 'retry', 'ui')
                  for platform in ('desktop', 'android')]
        names += ['network-settings-parser-negative-results.json', 'network-settings-application-failure.xml']
        evidence = {name: ('Host-only copy fixture: ' + name + '\n').encode() for name in names}
        private = {'network-settings-fixture.jks': b'private synthetic JKS fixture',
                   'network-settings-fixture.p12': b'private synthetic PKCS12 fixture'}
        with tempfile.TemporaryDirectory(prefix='ci-copy-controls-') as directory:
            out, stage = Path(directory)/'out', Path(directory)/'stage'
            out.mkdir();stage.mkdir()
            for name, data in {**evidence, **private}.items():
                (out/name).write_bytes(data)
            code = compile(ast.Module(body=loops, type_ignores=[]), str(publisher), 'exec')
            exec(code, {'out': out, 'stage': stage, 'shutil': shutil})
            self.assertEqual({path.name for path in stage.iterdir()}, set(evidence))
            for name, data in evidence.items():
                with self.subTest(file=name):
                    self.assertEqual((stage/name).read_bytes(), data)
            for name in private:
                self.assertFalse((stage/name).exists())
                self.assertEqual((out/name).read_bytes(), private[name])


class PublicationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='ci-ref-controls-')
        self.addCleanup(temporary.cleanup)
        base = Path(temporary.name)
        self.root, self.remote = base/'writer', base/'origin.git'
        subprocess.run(['git','init','--quiet','--bare',str(self.remote)],check=True)
        subprocess.run(['git','init','--quiet',str(self.root)],check=True)
        self.git('config','user.name','Synthetic CI ref fixture')
        self.git('config','user.email','fixture@example.invalid')
        self.git('remote','add','origin',str(self.remote))
        (self.root/'artifact.txt').write_text('source only\n')
        self.git('add','artifact.txt');self.git('commit','-qm','source')
        self.source = self.git('rev-parse','HEAD')
        (self.root/'artifact.txt').write_text('exact verified artifact bytes\n')
        self.git('add','artifact.txt');self.tree = self.git('write-tree')
        self.branch = 'apk/controlled-ci-artifacts';self.ref = 'refs/heads/'+self.branch
        self.env = dict(os.environ)
        self.pushes = [];self.competitors = []

    def git(self,*args):
        return subprocess.check_output(['git',*args],cwd=self.root,stderr=subprocess.PIPE,text=True).strip()

    def publish(self,**kwargs):
        return P.push_tree(root=self.root,source=self.source,tree=self.tree,branch=self.branch,
                           env=self.env,message='unchanged verified tree',**kwargs)

    def collide(self,number):
        original = subprocess.run
        def run(command,**kwargs):
            if 'push' in command and 'http.postBuffer=524288000' in command:
                self.pushes.append(list(command))
                if len(self.pushes) <= number:
                    tip=self.git('ls-remote','origin',self.ref).split()[0]
                    competitor=self.git('commit-tree',self.tree,'-p',tip,'-m','other writer '+str(len(self.pushes)))
                    original(['git','push','origin',competitor+':'+self.ref],cwd=self.root,
                             capture_output=True,text=True,check=True)
                    self.competitors.append(competitor)
            return original(command,**kwargs)
        return patch.object(P.subprocess,'run',side_effect=run)

    def assert_tree(self,commit):
        self.assertEqual(self.git('rev-parse',commit+'^{tree}'),self.tree)
        self.assertEqual(self.git('show',commit+':artifact.txt'),'exact verified artifact bytes')
        self.assertEqual(self.git('ls-remote','origin',self.ref).split()[0],commit)

    def test_new_ref_publishes_exact_tree_and_source_parent(self):
        commit=self.publish();self.assert_tree(commit)
        self.assertEqual(self.git('show','-s','--format=%P',commit),self.source)

    def test_real_concurrent_writer_is_retained_without_force_or_changed_tree(self):
        first=self.publish()
        with self.collide(1),contextlib.redirect_stderr(io.StringIO()):commit=self.publish()
        self.assert_tree(commit);self.assertEqual(len(self.pushes),2)
        parents=self.git('show','-s','--format=%P',commit).split()
        self.assertIn(self.source,parents);self.assertIn(self.competitors[0],parents)
        self.assertIn('parent '+first,self.git('cat-file','-p',self.competitors[0]).splitlines())
        self.assertTrue(all(not any(x.startswith('--force') or x.startswith('+') for x in row) for row in self.pushes))

    def test_repeated_conflicts_fail_at_declared_bound_and_preserve_other_writer(self):
        self.publish()
        with self.collide(2),contextlib.redirect_stderr(io.StringIO()),self.assertRaises(subprocess.CalledProcessError):
            self.publish(attempts=2)
        self.assertEqual(len(self.pushes),2)
        self.assertEqual(self.git('ls-remote','origin',self.ref).split()[0],self.competitors[-1])

    def test_non_conflict_failure_is_never_retried(self):
        original=subprocess.run;calls=[]
        def deny(command,**kwargs):
            if 'push' in command:
                calls.append(command)
                return subprocess.CompletedProcess(command,128,stdout='',stderr='permission denied')
            return original(command,**kwargs)
        with patch.object(P.subprocess,'run',side_effect=deny),contextlib.redirect_stderr(io.StringIO()),self.assertRaises(subprocess.CalledProcessError):
            self.publish()
        self.assertEqual(len(calls),1);self.assertEqual(self.git('ls-remote','origin',self.ref),'')

    def advance_before_fetch(self, number):
        original = subprocess.run
        self.fetches = []
        def run(command, **kwargs):
            if command[:2] == ['git', 'fetch']:
                self.fetches.append(list(command))
                if len(self.fetches) <= number:
                    tip = self.git('ls-remote', 'origin', self.ref).split()[0]
                    competitor = self.git('commit-tree', self.tree, '-p', tip,
                                          '-m', 'writer before fetch ' + str(len(self.fetches)))
                    original(['git', 'push', 'origin', competitor + ':' + self.ref],
                             cwd=self.root, capture_output=True, text=True, check=True)
                    self.competitors.append(competitor)
            if 'push' in command and 'http.postBuffer=524288000' in command:
                self.pushes.append(list(command))
            return original(command, **kwargs)
        return patch.object(P.subprocess, 'run', side_effect=run)

    def test_real_ref_advance_before_fetch_keeps_original_snapshot_and_retries_push(self):
        first = self.publish()
        with self.advance_before_fetch(1), contextlib.redirect_stderr(io.StringIO()):
            commit = self.publish()
        self.assert_tree(commit)
        self.assertEqual(len(self.fetches), 2)
        self.assertEqual(self.fetches[0][-1], first)
        self.assertEqual(self.fetches[1][-1], self.competitors[0])
        self.assertEqual(len(self.pushes), 2)
        self.assertIn(self.competitors[0], self.git('show', '-s', '--format=%P', commit).split())
        self.assertTrue(all(not any(value.startswith('--force') or value.startswith('+')
                                    for value in command) for command in self.pushes))

    def test_ref_advances_before_fetch_exhaust_original_bound_without_overwriting_writer(self):
        self.publish()
        with self.advance_before_fetch(2), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(subprocess.CalledProcessError):
            self.publish(attempts=2)
        self.assertEqual(len(self.fetches), 2)
        self.assertEqual(len(self.pushes), 2)
        self.assertEqual(self.git('ls-remote', 'origin', self.ref).split()[0], self.competitors[-1])

    def test_unexpected_fetched_identity_still_fails_before_push(self):
        self.publish()
        original = subprocess.check_output
        def output(command, **kwargs):
            if command == ['git', 'rev-parse', 'FETCH_HEAD']:
                return 'f' * 40 + '\n'
            return original(command, **kwargs)
        with patch.object(P.subprocess, 'check_output', side_effect=output), self.assertRaisesRegex(RuntimeError, 'immutable identity'):
            self.publish()
        self.assertEqual(self.git('ls-remote', 'origin', self.ref).split()[0], self.git('rev-parse', 'FETCH_HEAD'))

    def test_malformed_observed_ref_is_rejected_before_fetch(self):
        original = subprocess.check_output
        for observed in ('invalid ' + self.ref, 'a' * 40 + ' refs/heads/apk/other',
                         'a' * 40, 'a' * 40 + ' ' + self.ref + ' extra'):
            def output(command, **kwargs):
                if command == ['git', 'ls-remote', 'origin', self.ref]:
                    return observed + '\n'
                return original(command, **kwargs)
            with self.subTest(observed=observed), patch.object(P.subprocess, 'check_output', side_effect=output), self.assertRaisesRegex(ValueError, 'observed artifact ref'):
                self.publish()

    def remote_cas_stderr(self, candidate, current, expected, standard=False):
        if standard:
            return (f"remote: error: cannot lock ref '{self.ref}': is at {current} but expected {expected}\n"
                    f' ! [remote rejected] {candidate} -> {self.branch} (failed to update ref)\n'
                    f"error: failed to push some refs to '{self.remote}'\n")
        return (ACTUAL_REMOTE_CAS_STDERR
                .replace('0de4d5cecfdb4a8d64919368b1925a2404616ffa', candidate)
                .replace('8cfcdab8ee95ad623f58a5d477daced01f9e0f22', current)
                .replace('b0c4c0ae7f8de409273e8af1c7a8cf49ca2e78b9', expected)
                .replace('apk/gecko-integration-build-20261003', self.branch))

    def remote_cas_collisions(self, number, standard=False):
        original = subprocess.run
        self.pushes = [];self.fetches = [];self.competitors = [];self.handshakes = []
        def run(command, **kwargs):
            if command[:2] == ['git', 'fetch']:
                self.fetches.append(list(command))
            if 'push' in command and 'http.postBuffer=524288000' in command:
                self.pushes.append(list(command))
                if len(self.pushes) <= number:
                    tip = self.git('ls-remote', 'origin', self.ref).split()[0]
                    # Real local remote advances twice: Git's handshake expectation
                    # need not equal this publisher's earlier ls-remote snapshot.
                    previous = tip
                    for label in ('handshake', 'competing writer'):
                        changed = self.git('commit-tree', self.source + '^{tree}', '-p', previous,
                                           '-m', label + ' ' + str(len(self.pushes)))
                        original(['git', 'push', 'origin', changed + ':' + self.ref], cwd=self.root,
                                 capture_output=True, text=True, check=True)
                        if label == 'handshake':self.handshakes.append(changed)
                        previous = changed
                    self.competitors.append(changed)
                    candidate = command[-1].split(':', 1)[0]
                    return subprocess.CompletedProcess(command, 1, stdout='', stderr=self.remote_cas_stderr(
                        candidate, changed, self.handshakes[-1], standard))
            return original(command, **kwargs)
        return patch.object(P.subprocess, 'run', side_effect=run)

    def assert_frozen_pushes(self):
        for command in self.pushes:
            self.assertFalse(any(value.startswith('--force') or value.startswith('+') for value in command))
            self.assertEqual(command[-1].split(':', 1)[1], self.ref)
            candidate = command[-1].split(':', 1)[0]
            self.assertEqual(self.git('rev-parse', candidate + '^{tree}'), self.tree)
            self.assertEqual(self.git('show', '-s', '--format=%P', candidate).split()[0], self.source)

    def test_literal_actual_remote_cas_stderr_is_recognized(self):
        self.assertTrue(P._remote_ref_conflict(ACTUAL_REMOTE_CAS_STDERR,
            'refs/heads/apk/gecko-integration-build-20261003',
            '0de4d5cecfdb4a8d64919368b1925a2404616ffa'))

    def test_remote_cas_race_retries_same_tree_and_preserves_actual_competing_writer(self):
        for standard in (False, True):
            with self.subTest(standard=standard):
                first = self.publish()
                with self.remote_cas_collisions(1, standard), contextlib.redirect_stderr(io.StringIO()):
                    commit = self.publish()
                self.assert_tree(commit)
                self.assertEqual(len(self.pushes), 2)
                self.assertEqual([command[-1] for command in self.fetches], [first, self.competitors[0]])
                self.assertNotEqual(self.handshakes[0], first)
                self.assertEqual(self.git('show', '-s', '--format=%P', commit).split(),
                                 [self.source, self.competitors[0]])
                self.assertIn('parent ' + self.handshakes[0],
                              self.git('cat-file', '-p', self.competitors[0]).splitlines())
                self.assert_frozen_pushes()

    def test_three_remote_cas_races_exhaust_original_budget_without_overwrite(self):
        first = self.publish()
        with self.remote_cas_collisions(3), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(subprocess.CalledProcessError):
            self.publish()
        self.assertEqual(len(self.pushes), 3)
        self.assertEqual([command[-1] for command in self.fetches], [first, *self.competitors[:2]])
        self.assertEqual(self.git('ls-remote', 'origin', self.ref).split()[0], self.competitors[-1])
        self.assert_frozen_pushes()

    def test_remote_cas_lookalikes_are_never_retried(self):
        first = self.publish();original = subprocess.run
        mutations = {
            'authentication': lambda text: "remote: Permission denied\nfatal: Authentication failed\n",
            'network': lambda text: "fatal: unable to access remote: Could not resolve host\n",
            'permission': lambda text: text.replace("cannot lock ref '" + self.ref + "': is at " + 'a' * 40 + ' but expected ' + 'b' * 40, 'permission denied'),
            'disk': lambda text: text.replace("cannot lock ref '" + self.ref + "': is at " + 'a' * 40 + ' but expected ' + 'b' * 40, 'No space left on device'),
            'hook': lambda text: text.replace("cannot lock ref '" + self.ref + "': is at " + 'a' * 40 + ' but expected ' + 'b' * 40, 'pre-receive hook declined'),
            'wrong-cas-ref': lambda text: text.replace("cannot lock ref '" + self.ref, "cannot lock ref 'refs/heads/apk/other"),
            'wrong-destination': lambda text: text.replace(' -> ' + self.branch + ' ', ' -> apk/other '),
            'wrong-candidate': lambda text: re.sub(r'(\[remote rejected\] )[0-9a-f]{40}(?= ->)', r'\g<1>' + 'c' * 40, text),
            'bad-current-hex': lambda text: text.replace('is at ' + 'a' * 40, 'is at ' + 'g' * 40),
            'short-expected': lambda text: text.replace('expected ' + 'b' * 40, 'expected ' + 'b' * 39),
            'same-hashes': lambda text: text.replace('expected ' + 'b' * 40, 'expected ' + 'a' * 40),
            'no-remote-prefix': lambda text: text.replace('[remote rejected]', '[rejected]'),
            'not-a-status-line': lambda text: text.replace(' ! [remote rejected]', 'lookalike ! [remote rejected]'),
            'missing-failed-push': lambda text: '\n'.join(line for line in text.splitlines() if not line.startswith('error:')) + '\n',
            'no-cas-detail': lambda text: text.replace("cannot lock ref '" + self.ref + "': is at " + 'a' * 40 + ' but expected ' + 'b' * 40, 'failed to update ref'),
            'filesystem-lock': lambda text: text.replace("is at " + 'a' * 40 + ' but expected ' + 'b' * 40, 'Unable to create ref.lock: File exists'),
        }
        for name, mutate in mutations.items():
            pushes = []
            def deny(command, **kwargs):
                if 'push' in command and 'http.postBuffer=524288000' in command:
                    pushes.append(list(command))
                    candidate = command[-1].split(':', 1)[0]
                    return subprocess.CompletedProcess(command, 1, stdout='', stderr=mutate(
                        self.remote_cas_stderr(candidate, 'a' * 40, 'b' * 40)))
                return original(command, **kwargs)
            with self.subTest(name=name), patch.object(P.subprocess, 'run', side_effect=deny), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(subprocess.CalledProcessError):
                self.publish()
            self.assertEqual(len(pushes), 1, name)
            self.assertEqual(self.git('ls-remote', 'origin', self.ref).split()[0], first)

    def test_standard_remote_cas_requires_exact_remote_error_detail(self):
        for detail in ("error: cannot lock ref '" + self.ref + "': is at ",
                       "remote: error: cannot lock ref 'refs/heads/apk/other': is at "):
            text = (detail + 'a' * 40 + ' but expected ' + 'b' * 40 + '\n'
                    + ' ! [remote rejected] ' + self.source + ' -> ' + self.branch + ' (failed to update ref)\n'
                    + "error: failed to push some refs to 'local-test-origin'\n")
            with self.subTest(detail=detail):
                self.assertFalse(P._remote_ref_conflict(text, self.ref, self.source))


if __name__ == '__main__':
    unittest.main()
