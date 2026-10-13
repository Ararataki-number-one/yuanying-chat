"""Negative controls for source/APK/invocation proof; no Android execution."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import warnings
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('profile_runner', ROOT / 'tests/gecko/run_profile_features.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class FixtureProvenanceTest(unittest.TestCase):
    def stamp(self):
        return dict(schema=1, sourceCommit='a'*40, sourceTree='b'*40, dirtySource=False,
                    version='1.6.0', versionCode=51,
                    sdkCoordinate='org.mozilla.geckoview:geckoview:157.0.20261005135250')

    def identity(self):
        return dict(self.stamp(), package='local.pocketchat.test', apkSha256='c'*64,
                    apkBytes=100, buildStampSha256='d'*64)

    def test_expected_apk_rejects_stale_dirty_and_wrong_sdk(self):
        with tempfile.TemporaryDirectory() as directory:
            apk=Path(directory)/'fixture.apk'
            def write(stamp):
                with ZipFile(apk,'w') as archive:
                    archive.writestr(runner.STAMP,json.dumps(stamp)+'\n')
            stamp=self.stamp();write(stamp)
            value=runner.expected_build(apk,'a'*40,'b'*40,'1.6.0',51)
            self.assertEqual(value['apkSha256'],hashlib.sha256(apk.read_bytes()).hexdigest())
            for key, other in [('sourceCommit','e'*40),('sourceTree','f'*40),('dirtySource',True),
                               ('version','1.5.24'),('versionCode',50),('sdkCoordinate','unbound')]:
                with self.subTest(key=key):
                    write(dict(stamp,**{key:other}))
                    with self.assertRaises(ValueError):
                        runner.expected_build(apk,'a'*40,'b'*40,'1.6.0',51)

    def test_duplicate_stamp_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            apk=Path(directory)/'duplicate.apk'
            with ZipFile(apk,'w') as archive:
                archive.writestr(runner.STAMP,json.dumps(self.stamp()))
                with warnings.catch_warnings():
                    warnings.simplefilter('ignore',UserWarning)
                    archive.writestr(runner.STAMP,json.dumps(self.stamp()))
            with self.assertRaises(ValueError):
                runner.expected_build(apk,'a'*40,'b'*40,'1.6.0',51)

    def test_each_installed_identity_field_is_required_and_matched(self):
        expected=self.identity()
        runner.verify_installed(expected,expected)
        for key in expected:
            with self.subTest(key=key):
                changed=dict(expected);changed.pop(key)
                with self.assertRaises(ValueError):runner.verify_installed(changed,expected)

    def test_host_cannot_fill_missing_device_source_or_identity(self):
        identity=self.identity(); report=dict(sourceCommit='a'*40,buildIdentity=identity,runNonce='e'*32)
        runner.verify_invocation(report,identity,'e'*32)
        for key in ['sourceCommit','buildIdentity','runNonce']:
            with self.subTest(key=key):
                changed=dict(report);changed.pop(key)
                with self.assertRaises(ValueError):runner.verify_invocation(changed,identity,'e'*32)
        with self.assertRaises(ValueError):runner.verify_invocation(report,identity,'f'*32)
        with self.assertRaises(ValueError):runner.verify_invocation(report,identity,'invalid')

    def test_partial_or_failed_device_assertions_are_rejected(self):
        valid=dict(status='passed',actualAndroidExecution=True,synthetic=True,passed=1,total=1,
                   checks=[{'name':'controlled check','pass':True}])
        runner.verify(valid,1,True)
        for edit in [dict(status='failed'),dict(actualAndroidExecution=False),dict(synthetic=False),
                     dict(passed=0),dict(total=2),dict(checks=[]),dict(error='fixture failed'),
                     dict(checks=[{'name':'controlled check','pass':False}])]:
            with self.subTest(edit=edit):
                with self.assertRaises(ValueError):runner.verify(dict(valid,**edit),1,True)

    def test_prototype_cannot_be_promoted_to_template_acceptance(self):
        report=dict(diagnosticOnly=True,releaseAcceptance=False,actualGeckoExecution=True,
                    publicNetworkTraffic=False,uncovered=['Service Worker'],
                    independentTimezone='unsupported',cases=[
                        dict(index=i,status='passed',sessions=[{}]* (2 if i==3 else 1)) for i in range(4)])
        runner.verify_diagnostic(report)
        for edit in [dict(diagnosticOnly=False),dict(releaseAcceptance=True),dict(actualGeckoExecution=False),
                     dict(publicNetworkTraffic=True),dict(cases=report['cases'][:3]),dict(uncovered=[]),
                     dict(independentTimezone='enabled')]:
            with self.subTest(edit=edit):
                with self.assertRaises(ValueError):runner.verify_diagnostic(dict(report,**edit))


if __name__=='__main__':
    unittest.main()
