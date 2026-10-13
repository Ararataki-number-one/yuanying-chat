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


runner = module('profile_runner',ROOT / 'tests/gecko/run_profile_features.py')


class FixtureProvenanceTest(unittest.TestCase):
    def stamp(self):
        return dict(schema=1,sourceCommit='a'*40,sourceTree='b'*40,dirtySource=False,
                    version='1.6.0',versionCode=50,
                    sdkCoordinate='org.mozilla.geckoview:geckoview:157.0.20261005135250')

    def test_expected_apk_rejects_stale_dirty_or_wrong_version(self):
        with tempfile.TemporaryDirectory() as temp:
            apk=Path(temp) / 'fixture.apk'
            def write(stamp):
                with ZipFile(apk,'w') as zipped:
                    zipped.writestr(runner.STAMP,json.dumps(stamp)+'\n')
            stamp=self.stamp();write(stamp)
            value=runner.expected_build(apk,'a'*40,'b'*40,'1.6.0',50)
            self.assertEqual(value['apkSha256'],hashlib.sha256(apk.read_bytes()).hexdigest())
            for key,other in [('sourceCommit','c'*40),('sourceTree','d'*40),('dirtySource',True),
                              ('versionCode',49),('version','1.5.23'),('sdkCoordinate','unbound')]:
                with self.subTest(key=key):
                    write(dict(stamp,**{key:other}))
                    with self.assertRaises(ValueError):
                        runner.expected_build(apk,'a'*40,'b'*40,'1.6.0',50)

    def test_installed_bytes_and_report_source_cannot_be_relabelled(self):
        identity=dict(self.stamp(),package=runner.PACKAGE,apkSha256='e'*64,apkBytes=123,buildStampSha256='f'*64)
        runner.verify_installed(dict(identity),identity)
        for key,other in [('apkSha256','0'*64),('apkBytes',124),('package','local.pocketchat'),
                          ('sourceCommit','c'*40),('buildStampSha256','1'*64),('versionCode',49)]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                runner.verify_installed(dict(identity,**{key:other}),identity)
        report={};runner.bind_report(report,identity)
        self.assertEqual(report['sourceCommit'],identity['sourceCommit'])
        with self.assertRaises(ValueError):
            runner.bind_report({'sourceCommit':'c'*40},identity)

    def test_fixture_result_requires_complete_success(self):
        valid=dict(status='passed',actualAndroidExecution=True,synthetic=True,passed=20)
        runner.verify(valid,20)
        for mutation in [dict(valid,passed=19),dict(valid,error='failure'),dict(valid,actualAndroidExecution=False)]:
            with self.assertRaises(ValueError):runner.verify(mutation,20)
        runner.verify(dict(valid,total=20,checks=[{'pass':True} for _ in range(20)]),20,True)
        with self.assertRaises(ValueError):
            runner.verify(dict(valid,total=20,checks=[{'pass':True} for _ in range(19)]),20,True)



if __name__=='__main__':
    unittest.main()
