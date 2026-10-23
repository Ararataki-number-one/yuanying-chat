"""Counterfeit derived metadata tests; no device execution or caret repair proof."""
from contextlib import ExitStack
import copy
import functools
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from profile_sdk_identity_test import fixture, SOURCE, TREE

ROOT=Path(__file__).resolve().parents[1]
OUT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
import profile_resource_gate_test as metadata_fixture

spec=importlib.util.spec_from_file_location('derived_resource_contract',OUT/'tools/gecko/resource_invocation_contract.py')
contract=importlib.util.module_from_spec(spec);spec.loader.exec_module(contract)

# Frozen ordered catalog before the six upload controls were added (33c8d6c):
# 36 resource assertions followed by 138 SDK/context assertions. The digest
# covers the ASCII JSON name list with separators=(',', ':'), not just its size.
ORIGINAL_ORDERED_NAMES_SHA256='f5d8a1d2151db4ef600c40120261da4b52c2947e0162a743d41d54716a3084c6'
ADDED_UPLOAD_NAMES=(
    'Open file chooser blocks maintenance and profile changes',
    'File preparation blocks maintenance and profile changes',
    'Unknown handed off selections protect maintenance without claiming uploading',
    'Actual selected uploading card keeps unified file work active',
    'One actual removal observation retains selection protection',
    'Two actual removal observations release the selected batch',
)


class DerivedResourceCatalogControls(unittest.TestCase):
    def setUp(self):
        self.manifest,self.materials,self.reader,self.receipt,self.raw,self.asset,self.installed,_=fixture()
        self.report=metadata_fixture.metadata()
        self.report['buildIdentity']['sdkBuildIdentity']=copy.deepcopy(self.asset)
        self.report['engineVersion']='GeckoView 157.0.1 (source-derived Java editable-selection)'
        for key in contract._sdk.SDK_FIELDS:
            self.report[key]=self.asset[key]
            self.report['sdkUserAgentBaseline'][key]=self.asset[key]

    def verify(self):
        # Only source I/O is replaced. SDK expectations still come from selected
        # synthetic source records, and every original resource assertion runs.
        with ExitStack() as stack:
            for helper in (contract._sdk,contract._guard._sdk):
                stack.enter_context(patch.object(helper,'verify_sdk_identity',functools.partial(helper.verify_sdk_identity,reader=self.reader)))
                stack.enter_context(patch.object(helper,'verify_report_sdk',functools.partial(helper.verify_report_sdk,reader=self.reader)))
            contract._sdk.verify_sdk_identity(self.report['buildIdentity'],SOURCE,TREE,self.raw)
            return contract.verify_resource_report(self.report,metadata_fixture.NAMES)

    def test_derived_identity_retains_all_174_ordered_assertions(self):
        original=[row for row in self.report['checks'] if row['name'] not in ADDED_UPLOAD_NAMES]
        self.assertEqual(len(original),174)
        names=json.dumps([row['name'] for row in original],ensure_ascii=True,separators=(',',':')).encode('ascii')
        self.assertEqual(hashlib.sha256(names).hexdigest(),ORIGINAL_ORDERED_NAMES_SHA256)
        for row in original:
            with self.subTest(original=row['name']):self.assertIs(row['pass'],True)
        self.assertEqual(len(self.report['checks']),180)
        self.assertEqual(len(self.report['resourceChecks']),42)
        for field in ('checks','resourceChecks'):
            added=[row for row in self.report[field] if row['name'] in ADDED_UPLOAD_NAMES]
            self.assertEqual(added,[{'name':name,'pass':True} for name in ADDED_UPLOAD_NAMES])
        result=self.verify()
        self.assertFalse(result['capacityAcceptance'])
        self.assertFalse(self.report['physicalDeviceAcceptance'])
        self.assertFalse(self.report['fingerprintTemplateAcceptance'])
        self.assertTrue(all(value=='UNSUPPORTED' for value in self.report['nativeCustomCapabilities'].values()))

    def test_original_resource_order_remains_required(self):
        for field in ('checks','resourceChecks'):
            self.report[field][0],self.report[field][1]=self.report[field][1],self.report[field][0]
        with self.assertRaises(ValueError):self.verify()

    def test_each_added_upload_assertion_remains_required(self):
        original=copy.deepcopy(self.report)
        for name in ADDED_UPLOAD_NAMES:
            with self.subTest(name=name):
                self.report=copy.deepcopy(original)
                for field in ('checks','resourceChecks'):
                    self.report[field]=[row for row in self.report[field] if row['name']!=name]
                self.report['passed']-=1;self.report['total']-=1
                with self.assertRaises(ValueError):self.verify()

    def test_each_added_upload_assertion_must_pass(self):
        original=copy.deepcopy(self.report)
        for name in ADDED_UPLOAD_NAMES:
            with self.subTest(name=name):
                self.report=copy.deepcopy(original)
                for field in ('checks','resourceChecks'):
                    for row in self.report[field]:
                        if row['name']==name:row['pass']=False
                with self.assertRaises(ValueError):self.verify()

    def test_missing_original_resource_assertion_remains_rejected(self):
        self.report['resourceChecks'].pop()
        with self.assertRaises(ValueError):self.verify()

    def test_missing_original_sdk_context_assertion_remains_rejected(self):
        self.report['checks'].pop()
        with self.assertRaises(ValueError):self.verify()

    def test_native_controls_remain_unsupported(self):
        self.report['nativeCustomCapabilities']['INDEPENDENT_TIMEZONE']='SUPPORTED'
        with self.assertRaises(ValueError):self.verify()

    def test_derived_ua_baseline_cannot_claim_the_official_input_checksum(self):
        self.report['sdkUserAgentBaseline']['sdkAarSha256']=contract._sdk.SDK_AAR_SHA256
        with self.assertRaises(ValueError):self.verify()


if __name__=='__main__':unittest.main()
