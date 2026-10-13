#!/usr/bin/env python3
"""Reject stale APK/source evidence and polluted exports using synthetic fixtures only."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name,path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


exporter = module('profile_exporter',ROOT / 'tools/export-profile-upgrades.py')


class ExportContractTest(unittest.TestCase):
    def test_export_refuses_nonempty_and_source_parent(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'repo';root.mkdir();out=Path(temp)/'output';out.mkdir()
            stale=out/'stale-review.json';stale.write_text('{"synthetic":true}')
            with self.assertRaises(ValueError):exporter.validate_output(root,out)
            self.assertEqual(stale.read_text(),'{"synthetic":true}')
            with self.assertRaises(ValueError):exporter.validate_output(root,Path(temp))

    def test_clean_export_has_exact_hashed_files_and_bound_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'repo';root.mkdir()
            def git(*args):
                return subprocess.check_output(['git','-c','user.name=Fixture','-c','user.email=fixture@example.invalid',*args],cwd=root).decode().strip()
            git('init','-q');(root/'base.txt').write_text('baseline');(root/'app').mkdir();(root/'app/build.gradle').write_text("versionCode 49; versionName '1.5.23'");git('add','.');git('commit','-qm','baseline');base=git('rev-parse','HEAD')
            releases=[]
            for code,version in enumerate(['1.6.0','1.7.0','2.0.0'],50):
                (root/'change.txt').write_text(version);(root/'app/build.gradle').write_text(f"versionCode {code}; versionName '{version}'");git('add','.');git('commit','-qm',version)
                releases.append((version,git('rev-parse','HEAD')))
            evidence=Path(temp)/'evidence';evidence.mkdir()
            (evidence/'profile-host-results.json').write_text(json.dumps(dict(sourceCommit=releases[-1][1],sourceTree=git('rev-parse','HEAD^{tree}'),sourceDirty=False,actualAndroidExecution=False,status='passed')))
            (evidence/'unrelated.json').write_text('{"synthetic":true}')
            output=Path(temp)/'out';exporter.export(root,output,base,releases,evidence)
            manifest=json.loads((output/'manifest.json').read_text())
            with ZipFile(output/'PocketChat-1.6-1.7-2.0-review.zip') as zipped:
                names={n.removeprefix('PocketChat-profile-upgrades/') for n in zipped.namelist()}
                self.assertEqual(names,set(manifest['files'])|{'manifest.json'})
                self.assertNotIn('verification/unrelated.json',names)
                for name,sha in manifest['files'].items():
                    self.assertEqual(hashlib.sha256(zipped.read('PocketChat-profile-upgrades/'+name)).hexdigest(),sha)
            bad=evidence/'profile-host-results.json';bad.write_text(json.dumps(dict(sourceCommit='0'*40,actualAndroidExecution=False)))
            with self.assertRaises(ValueError):exporter.export(root,Path(temp)/'bad',base,releases,evidence)
            self.assertFalse((Path(temp)/'bad').exists())


if __name__=='__main__':
    unittest.main()
