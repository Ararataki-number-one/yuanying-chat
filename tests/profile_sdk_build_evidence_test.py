"""Counterfeit input/runtime SDK evidence rejection controls, never device proof."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from profile_sdk_identity_test import fixture, encoded, SOURCE, TREE, sdk

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/gecko'))
spec=importlib.util.spec_from_file_location('sdk_build_evidence_controls',ROOT/'tools/gecko/check_sdk_build_evidence.py')
gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)


class SdkBuildEvidenceTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.directory=Path(self.temp.name)
        self.manifest,self.materials,self.reader,self.receipt,self.raw,self.asset,self.installed,_=fixture()
        self.base_raw=(ROOT/'third-party/sdk/geckoview-157.0.1-official.json').read_bytes();self.base=json.loads(self.base_raw)
        self.official=dict(status='passed',sourceCommit=SOURCE,coordinate=sdk.SDK_COORDINATE,firefoxVersion='157.0.1',
            receiptSha256=sdk.digest(self.base_raw),aarSha256=sdk.SDK_AAR_SHA256,classesJarSha256=sdk.SDK_CLASSES_SHA256,
            actualAndroidExecution=False,sdkAarModified=False,sdkClassTransformApplied=False,gradleResolvedAarVerified=False,resolvedArtifacts=[])
        actual=dict(status='passed',sourceCommit=SOURCE,sourceTree=TREE,runId=self.asset['runId'],runAttempt=self.asset['runAttempt'],
            actualAndroidExecution=False,releaseAcceptance=False,gradleResolvedAarVerified=True,
            resolvedArtifacts=[dict(coordinate=sdk.SDK_RUNTIME_COORDINATE,sha256=self.manifest['sdkAarSha256'],bytes=self.manifest['sdkAarBytes'],configuration=name) for name in ('releaseCompileClasspath','integrationCompileClasspath')],
            archiveDelta=dict(actualArchiveComparison=True,changedClassEntries=[sdk.EDITABLE_ENTRY],allOtherClassEntriesUnchanged=True,allNativeAndResourceEntriesUnchanged=True,sdkInputAarSha256=sdk.SDK_AAR_SHA256,sdkAarSha256=self.manifest['sdkAarSha256'],unchangedClassEntries=100,unchangedAarEntries=20),
            **{key:self.asset[key] for key in ('sdkBuildKind','sdkRuntimeCoordinate','sdkAarSha256','sdkClassesJarSha256','sdkGeckoEditableClassSha256','sdkManifestSha256','sdkBuildReceiptSha256')})
        self.records={'official-sdk-input.json':self.base,'official-sdk-verification.json':self.official,
            'derived-sdk-input.json':self.manifest,sdk.SDK_RECEIPT_FILE:self.receipt,
            'device-results.json':dict(status='passed',sourceCommit=SOURCE,actualAndroidExecution=True,eventTransport=dict(buildIdentity=self.installed)),
            'derived-sdk-verification.json':actual}
        self.write(self.records)

    def write(self,records):
        for name,value in records.items():
            raw=self.base_raw if name=='official-sdk-input.json' else self.raw if name==sdk.SDK_RECEIPT_FILE else self.materials[sdk.DERIVED_MANIFEST] if name=='derived-sdk-input.json' else encoded(value)
            (self.directory/name).write_bytes(raw)

    def test_complete_distinct_input_and_runtime_metadata(self):
        result=gate.verify_sdk_build_evidence(self.directory,SOURCE,self.reader)
        self.assertEqual(result['sdkAarSha256'],self.manifest['sdkAarSha256'])
        self.assertNotEqual(result['sdkAarSha256'],sdk.SDK_AAR_SHA256)

    def test_bound_verification_fields_reject_counterfeit_changes(self):
        actual='derived-sdk-verification.json';upstream='official-sdk-verification.json'
        edits=[
            (actual,lambda v:v.update(sdkAarSha256=sdk.SDK_AAR_SHA256)),
            (actual,lambda v:v.update(sdkBuildReceiptSha256='0'*64)),
            (actual,lambda v:v.update(runAttempt='2')),
            (actual,lambda v:v.update(sourceTree='0'*40)),
            (actual,lambda v:v['resolvedArtifacts'].pop()),
            (actual,lambda v:v['resolvedArtifacts'][0].update(coordinate=sdk.SDK_COORDINATE)),
            (actual,lambda v:v['resolvedArtifacts'][0].update(sha256=sdk.SDK_AAR_SHA256)),
            (actual,lambda v:v['resolvedArtifacts'][0].update(bytes=1)),
            (actual,lambda v:v['archiveDelta'].update(actualArchiveComparison=False)),
            (actual,lambda v:v['archiveDelta']['changedClassEntries'].append('org/mozilla/geckoview/GeckoEditable$1.class')),
            (actual,lambda v:v['archiveDelta'].update(allNativeAndResourceEntriesUnchanged=False)),
            (actual,lambda v:v['archiveDelta'].update(unchangedClassEntries=0)),
            (upstream,lambda v:v.update(aarSha256=self.manifest['sdkAarSha256'])),
            (upstream,lambda v:v.update(sdkAarModified=True)),
            (upstream,lambda v:v.update(gradleResolvedAarVerified=True)),
            ('device-results.json',lambda v:v['eventTransport']['buildIdentity'].pop('sdkBuildIdentity')),
        ]
        for index,(name,edit) in enumerate(edits):
            with self.subTest(control=index,file=name):
                values=copy.deepcopy(self.records);edit(values[name]);self.write(values)
                with self.assertRaises((AssertionError,ValueError,KeyError)):gate.verify_sdk_build_evidence(self.directory,SOURCE,self.reader)

    def test_raw_runtime_receipt_bytes_remain_bound(self):
        (self.directory/sdk.SDK_RECEIPT_FILE).write_bytes(self.raw+b' ')
        with self.assertRaises((ValueError,AssertionError)):gate.verify_sdk_build_evidence(self.directory,SOURCE,self.reader)

    def test_historical_official_mode_keeps_resolved_artifact_checks(self):
        value=copy.deepcopy(self.official);value.update(gradleResolvedAarVerified=True,resolvedArtifacts=[dict(sha256=sdk.SDK_AAR_SHA256,bytes=self.base['aar']['bytes'])])
        (self.directory/'official-sdk-verification.json').write_bytes(encoded(value))
        def historical(source,path):raise subprocess.CalledProcessError(128,['git','show',source+':'+path])
        self.assertIsNone(gate.verify_sdk_build_evidence(self.directory,SOURCE,historical))
        value['resolvedArtifacts'][0]['sha256']=self.manifest['sdkAarSha256']
        (self.directory/'official-sdk-verification.json').write_bytes(encoded(value))
        with self.assertRaises(AssertionError):gate.verify_sdk_build_evidence(self.directory,SOURCE,historical)


if __name__=='__main__':unittest.main()
