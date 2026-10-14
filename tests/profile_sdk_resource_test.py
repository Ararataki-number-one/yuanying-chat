"""Counterfeit derived metadata tests; no device execution or caret repair proof."""
from contextlib import ExitStack
import copy
import functools
import importlib.util
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
        self.assertEqual(len(self.report['checks']),174)
        result=self.verify()
        self.assertFalse(result['capacityAcceptance'])
        self.assertFalse(self.report['physicalDeviceAcceptance'])
        self.assertFalse(self.report['fingerprintTemplateAcceptance'])
        self.assertTrue(all(value=='UNSUPPORTED' for value in self.report['nativeCustomCapabilities'].values()))

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
