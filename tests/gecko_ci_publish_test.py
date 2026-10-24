"""Host-only copy and local Git publication controls; no Android acceptance."""
import ast
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('ci_git_publish', ROOT/'tools/gecko/ci_git_publish.py')
P = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(P)


class PublicationArtifactCopyTests(unittest.TestCase):
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


if __name__ == '__main__':
    unittest.main()
