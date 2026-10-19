"""Host-only transfer integrity controls; no Android or application acceptance."""
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('ci_bundle', ROOT / 'tools/gecko/ci_bundle.py')
BUNDLE = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(BUNDLE)


class CiBundleTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='pocket-ci-bundle-')
        self.addCleanup(temporary.cleanup); self.base = Path(temporary.name)
        self.env = patch.dict(os.environ, GITHUB_RUN_ID='123456', GITHUB_RUN_ATTEMPT='1')
        self.env.start(); self.addCleanup(self.env.stop)
        self.root = self.base / 'source'; self.root.mkdir()
        self.git(self.root, 'init', '-q')
        (self.root / '.gitignore').write_text('work/\napp/build/\n')
        self.git(self.root, 'add', '.gitignore'); self.git(self.root, 'commit', '-qm', 'Fixture source')
        for name, data in {
            BUNDLE.INTEGRATION:b'exact synthetic integration bytes',
            BUNDLE.RELEASE:b'exact synthetic release bytes',
            BUNDLE.SDK/'geckoview-caret.aar':b'exact synthetic SDK bytes',
            BUNDLE.SDK/'sdk-build-receipt.json':b'{"scope":"transport fixture only"}',
            BUNDLE.OUT/'host-results.json':b'{"synthetic":true}',
            BUNDLE.OUT/'integration-test.jks':b'must never transfer this key',
            BUNDLE.OUT/'network-fixture.p12':b'must never transfer this key either',
        }.items():
            path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
        self.build = self.base / 'build.tar.gz'
        BUNDLE.pack(self.root,self.build,'build')

    def git(self, root, *args):
        return subprocess.check_output(['git','-c','user.name=CI fixture','-c','user.email=fixture@example.invalid',*args],cwd=root,stderr=subprocess.DEVNULL,text=True)

    def clone(self, name):
        target=self.base/name
        subprocess.run(['git','clone','-q','--no-hardlinks',str(self.root),str(target)],check=True,stderr=subprocess.DEVNULL)
        return target

    def phase(self, name, files):
        target=self.clone('phase-'+name);BUNDLE.restore(target,self.build,'build')
        for file,data in files.items():
            path=target/BUNDLE.OUT/file;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
        archive=self.base/(name+'.tar.gz');BUNDLE.pack(target,archive,'phase',name)
        return archive

    def test_exact_build_roundtrip_excludes_keys_and_restores_same_ui_bytes(self):
        target=self.clone('consumer');manifest=BUNDLE.restore(target,self.build,'build')
        self.assertEqual((target/BUNDLE.INTEGRATION).read_bytes(),(self.root/BUNDLE.INTEGRATION).read_bytes())
        self.assertEqual((target/BUNDLE.OUT/'ui-current.apk').read_bytes(),(self.root/BUNDLE.INTEGRATION).read_bytes())
        self.assertFalse((target/BUNDLE.OUT/'integration-test.jks').exists())
        self.assertFalse((target/BUNDLE.OUT/'network-fixture.p12').exists())
        self.assertEqual(manifest['runId'],'123456')

    def test_other_ci_attempt_is_rejected_before_writing_apks(self):
        target=self.clone('other-attempt')
        with patch.dict(os.environ,GITHUB_RUN_ATTEMPT='2'),self.assertRaises(AssertionError):
            BUNDLE.restore(target,self.build,'build')
        self.assertFalse((target/BUNDLE.INTEGRATION).exists())

    def test_other_source_is_rejected_before_writing_apks(self):
        target=self.clone('other-source');(target/'changed.txt').write_text('another source')
        self.git(target,'add','changed.txt');self.git(target,'commit','-qm','Different source')
        with self.assertRaises(AssertionError):BUNDLE.restore(target,self.build,'build')
        self.assertFalse((target/BUNDLE.INTEGRATION).exists())

    def test_changed_archive_bytes_are_rejected_before_any_extraction(self):
        corrupt=self.base/'corrupt.tar.gz'
        with tarfile.open(self.build,'r:gz') as original,tarfile.open(corrupt,'w:gz') as output:
            for item in original.getmembers():
                raw=original.extractfile(item).read()
                if item.name==str(BUNDLE.INTEGRATION):raw=b'X'+raw[1:]
                output.addfile(item,io.BytesIO(raw))
        target=self.clone('corrupt-consumer')
        with self.assertRaises(AssertionError):BUNDLE.restore(target,corrupt,'build')
        self.assertFalse((target/BUNDLE.INTEGRATION).exists())

    def test_phase_requires_the_same_compiled_build_index(self):
        phase=self.phase('ui',{'ui-visual-results.json':b'{"synthetic":true}'})
        target=self.clone('different-build');BUNDLE.restore(target,self.build,'build')
        path=target/BUNDLE.BUILD_INDEX;path.write_bytes(path.read_bytes()+b' ')
        with self.assertRaises(AssertionError):BUNDLE.restore(target,phase,'phase','ui')
        self.assertFalse((target/BUNDLE.OUT/'ui-visual-results.json').exists())

    def test_distinct_phase_reports_merge_and_device_preflight_remains_canonical(self):
        ui=self.phase('ui',{'ui-visual-results.json':b'{"ui":true}','emulator-bootstrap-results.json':b'{"vm":"ui"}'})
        files=self.phase('files',{'device-results.json':b'{"device":true}','emulator-bootstrap-results.json':b'{"vm":"files"}'})
        target=self.clone('collector');BUNDLE.restore(target,self.build,'build')
        BUNDLE.restore(target,ui,'phase','ui');BUNDLE.restore(target,files,'phase','files')
        self.assertTrue((target/BUNDLE.OUT/'ui-visual-results.json').exists())
        self.assertTrue((target/BUNDLE.OUT/'device-results.json').exists())
        self.assertEqual(json.loads((target/BUNDLE.OUT/'emulator-bootstrap-results.json').read_text())['vm'],'files')
        self.assertEqual(json.loads((target/BUNDLE.OUT/'ci-phases/ui/emulator-bootstrap-results.json').read_text())['vm'],'ui')

    def test_phases_cannot_replace_another_phase_evidence(self):
        ui=self.phase('ui',{'shared-results.json':b'first'})
        other=self.phase('connections',{'shared-results.json':b'second'})
        target=self.clone('collision');BUNDLE.restore(target,self.build,'build');BUNDLE.restore(target,ui,'phase','ui')
        with self.assertRaises(AssertionError):BUNDLE.restore(target,other,'phase','connections')
        self.assertEqual((target/BUNDLE.OUT/'shared-results.json').read_bytes(),b'first')

    def test_traversal_and_symbolic_link_entries_are_rejected(self):
        for name, link in (('../escape',False),('work/gecko-integration/link.json',True)):
            archive=self.base/('link.tar.gz' if link else 'traversal.tar.gz')
            with tarfile.open(self.build,'r:gz') as original,tarfile.open(archive,'w:gz') as output:
                for item in original.getmembers():output.addfile(item,original.extractfile(item))
                item=tarfile.TarInfo(name)
                if link:item.type=tarfile.SYMTYPE;item.linkname='/tmp/outside'
                else:item.size=1
                output.addfile(item,None if link else io.BytesIO(b'x'))
            target=self.clone('link-consumer' if link else 'traversal-consumer')
            with self.assertRaises(AssertionError):BUNDLE.restore(target,archive,'build')
            self.assertFalse((target/BUNDLE.INTEGRATION).exists())


if __name__=='__main__':unittest.main()
