"""Actual retained host prerequisites; no CPU/TLS native or handshake proof."""
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest

import profile_native_protection_test as protection
import profile_native_runtime_capabilities_test as capability

ROOT=Path(__file__).resolve().parents[1]
FILES=(Path(__file__),ROOT/'tests/native-protection-host/NativeProtectionControllerHost.java.in',ROOT/'tests/native-runtime-capabilities-host/NativeRuntimeCapabilitiesHost.java',ROOT/'tests/profile_native_protection_test.py',ROOT/'tests/profile_native_runtime_capabilities_test.py',ROOT/'app/src/main/java/local/pocketchat/GeckoWebView.java')
SHA=lambda raw:hashlib.sha256(raw).hexdigest()

class ColdPolicyCollaboratorBoundaries(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.before={str(p.relative_to(ROOT)):SHA(p.read_bytes()) for p in FILES};cls.outcomes=[];cls.counterfeits=[]
        (ROOT/'work').mkdir(exist_ok=True)
    @classmethod
    def tearDownClass(cls):
        stable=cls.before=={str(p.relative_to(ROOT)):SHA(p.read_bytes()) for p in FILES}
        if not stable:raise AssertionError('Current host boundary source changed during controls')
        out=ROOT/'work/cpu-tls-host-boundary';out.mkdir(exist_ok=True)
        (out/'results.json').write_text(json.dumps(dict(schema=1,status='passed' if len(cls.outcomes)==2 and len(cls.counterfeits)==5 else 'failed',sourceFiles=cls.before,executionInputsUnchanged=True,outcomes=cls.outcomes,compiledSemanticCounterfeits=cls.counterfeits,actualCpuNativeExecution=False,actualTlsNativeExecution=False,actualNetworkExecution=False,scope='Verbatim current Gv extraction through the retained original protection/capability runners, explicit default opaque-runtime and unobserved metadata collaborators. Original98+60/51 checks retain their own budgets. Declared missing/foreign/retired prerequisites cannot grant native confirmation; no real CPU/TLS bootstrap or wire runs here.'),indent=2)+'\n')
    def test_original_protection_budget_and_new_cold_conjunction_reject_semantic_counterfeits(self):
        result=protection.execute()
        self.assertEqual(result['passed'],98);self.assertEqual(result['addonBoundaryPassed'],8)
        self.assertEqual(result['coldPolicyBoundaryPassed'],20)
        self.assertEqual(len(result['coldPolicyBoundaryChecks']),20)
        self.assertTrue(all(row['pass'] is True for row in result['coldPolicyBoundaryChecks']))
        self.assertIs(result['actualAndroidExecution'],False);self.assertIs(result['actualGeckoExecution'],False)
        self.outcomes.append(dict(scope='actual-protection-methods',original=98,addon=8,coldPrerequisites=20))
        source=protection.VIEW.read_text()
        for name,needle,reason in [('CPU-conjunction','owner.cpu.readyFor(runtime)&&','CPU unconfirmed prerequisite denies actual protection conjunction'),('TLS-conjunction','owner.tls.readyFor(runtime)&&','TLS unconfirmed prerequisite denies actual protection conjunction')]:
            self.assertEqual(source.count(needle),1)
            with self.assertRaisesRegex(AssertionError,reason):protection.execute(source.replace(needle,'('+needle[:-2]+'||true)&&',1))
            self.counterfeits.append(dict(name=name,compiledAndRejectedByOriginalRunner=True))
        template=protection.TEMPLATE;raw=template.read_text()
        for name,needle,reason in [('opaque-runtime-borrow','&&runtime==expectedRuntime','foreign opaque runtime cannot borrow readiness'),('retired-prerequisite','&&!retired','retired prerequisite denies unchanged runtime')]:
            self.assertEqual(raw.count(needle),1)
            with tempfile.TemporaryDirectory(prefix='cold-boundary-mutant-',dir=ROOT/'work') as folder:
                path=Path(folder)/'NativeProtectionControllerHost.java.in';path.write_text(raw.replace(needle,'',1))
                try:
                    protection.TEMPLATE=path
                    with self.assertRaisesRegex(AssertionError,reason):protection.execute()
                finally:protection.TEMPLATE=template
            self.counterfeits.append(dict(name=name,compiledAndRejectedByOriginalRunner=True))
    def test_actual_capability_reader_keeps_unobserved_policy_metadata_unproven(self):
        case=capability.NativeRuntimeCapabilitiesTest('test_exact_sdk_readers_owner_lifecycle_and_existing_audit_freshness')
        case.test_exact_sdk_readers_owner_lifecycle_and_existing_audit_freshness()
        receipt=json.loads((ROOT/'work/native-runtime-capabilities/host-results.json').read_text())
        for run in receipt['runs']:
            report=run['report'];self.assertEqual(report['checks'],51);self.assertEqual(report['coldPolicyBoundaryPassed'],6)
            self.assertTrue(all(v['pass'] is True for v in report['coldPolicyBoundaryChecks']))
            self.assertIs(report['actualCpuPolicyExecution'],False);self.assertIs(report['actualTlsNativeExecution'],False)
        self.outcomes.append(dict(scope='actual-capability-reader',originalPerJson=51,coldMetadataPerJson=6,jsonRuntimes=[v['runtime'] for v in receipt['runs']]))
        template=capability.HOST;raw=template.read_text();needle='"synthetic-unobserved-cold-policy","nativeSettingReadback",false';self.assertEqual(raw.count(needle),1)
        with tempfile.TemporaryDirectory(prefix='cold-metadata-mutant-',dir=ROOT/'work') as folder:
            path=Path(folder)/'NativeRuntimeCapabilitiesHost.java';path.write_text(raw.replace(needle,needle[:-5]+'true',1))
            try:
                capability.HOST=path
                with self.assertRaisesRegex(AssertionError,'CPU metadata is an explicit unobserved default prerequisite'):
                    case.test_exact_sdk_readers_owner_lifecycle_and_existing_audit_freshness()
            finally:capability.HOST=template
        self.counterfeits.append(dict(name='modeled-prerequisite-forges-native-receipt',compiledAndRejectedByOriginalRunner=True))

if __name__=='__main__':unittest.main(verbosity=2)
