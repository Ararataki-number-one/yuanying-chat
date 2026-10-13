"""Negative validators using counterfeit metadata only; no Android/Gecko execution."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'tools/gecko'/f'{name}.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
contract=load('template_invocation_contract');gate=load('check_template_evidence')


def metadata_only_report():
    identity=dict(schema=1,package='local.pocketchat.test',sourceCommit='a'*40,sourceTree='b'*40,dirtySource=False,version='1.7.0',versionCode=52,sdkCoordinate=contract.SDK,apkSha256='c'*64,apkBytes=100,buildStampSha256='d'*64)
    report=dict(schema=1,status='passed',synthetic=True,sourceCommit='a'*40,runNonce='e'*32,buildIdentity=identity,androidSdk=35,actualAndroidExecution=True,actualGeckoExecution=True,publicNetworkTraffic=False,fixtureType='production-template-controlled-contexts-v1',diagnosticOnly=False,controlledTemplateAcceptance=True,releaseAcceptance=False,fingerprintTemplateAcceptance=False,realAccountLogin=False,safeIdleApplicationAcceptance=False,sdkCoordinate=contract.SDK,sdkAarSha256=contract.AAR,engineVersion='GeckoView 157.0.1',templateIds=contract.TEMPLATES,uncovered=contract.UNCOVERED,independentTimezone='unsupported',origin='http://127.0.0.1:12345',cases=[],appliedCases=[],allRequestHeaders=[])
    names=contract.expected_check_names();report.update(passed=len(names),total=len(names),checks=[dict(name=name,pass_=True) for name in names])
    report['checks']=[{'name':name,'pass':True} for name in names]
    for index,template in enumerate(contract.TEMPLATES):
        desktop=index in [1,3];privacy='standard' if index<2 else 'compatibility';requested=dict(schema=1,templateId=template,display='desktop' if desktop else 'mobile',privacy=privacy,locales=contract.REQUESTS[index],timezoneStrategy='system')
        ua=('Mozilla/5.0 (X11; Linux x86_64; rv:157.0)' if desktop else 'Mozilla/5.0 (Android 14; Mobile; rv:157.0)')+' Gecko/157.0 Firefox/157.0'
        signal=dict(ua=ua,cpu=8,memory=None,language=contract.NORMALIZED[index],languages=[contract.NORMALIZED[index]],offset=-540,zone='Asia/Tokyo',intlLocale=contract.NORMALIZED[index])
        sessions=[]
        for name in ['primary']+(['secondary'] if index==3 else []):
            wire=[]
            for role in contract.ROLES:
                target={'page':'/page','frame':'/frame','worker-script':'/worker'}.get(role,'/echo');query='run='+report['runNonce']+'&case='+str(index+1)+'&session='+name+('&kind='+role if role.endswith('-fetch') else '')
                header=dict(sequence=len(report['allRequestHeaders'])+1,case=index+1,session=name,role=role,userAgent=ua,acceptLanguage=contract.NORMALIZED[index],method='GET',path=target+'?'+query)
                wire.append(header);report['allRequestHeaders'].append(header)
            raw=dict(run=report['runNonce'],case=index+1,session=name,provenance='controlled-page-main-world',**{context:copy.deepcopy(signal) for context in ['parent','frame','worker','blobWorker']})
            native=dict(userAgent=ua,requestedLocales=contract.REQUESTS[index],getterLocales=contract.REQUESTS[index],expectedSdkNormalizedLanguage=contract.NORMALIZED[index])
            sessions.append(dict(name=name,native=native,observed=raw,requestHeaders=wire))
        report['cases'].append(dict(index=index,serial=index+1,status='passed',sessions=sessions))
        coverage=dict(requiredFields=contract.FIELDS,**{context:dict(compared=contract.FIELDS,missingOrInvalid=[],different=[]) for context in ['frame','worker']})
        observation=dict(fresh=True,identityAppliedRevision=index+2,rows=[dict(key=key,state='verified') for key in ['ua','language','frame','worker','zone']],contextCoverage=coverage,controlledRequestHeaders=sessions[0]['requestHeaders'])
        native=dict(requested=requested,accepted=requested,requestedLocales=contract.REQUESTS[index],expectedSdkLocales=[contract.NORMALIZED[index]],getterScope='requested-descriptor-only',rfpAcknowledged=True,fingerprintingProtected=False,trackingProtection=index<2)
        report['appliedCases'].append(dict(index=index,templateId=template,privacy=privacy,nativePolicy=native,identity=dict(slot=0,generation=0,environmentId='00000000-0000-0000-0000-000000000001'),desiredRevision=index+2,appliedRevision=index+2,observedRevision=index+2,report=observation))
    return report


class TemplateContractTest(unittest.TestCase):
    def setUp(self):self.report=metadata_only_report()
    def rejects(self,edit):
        report=copy.deepcopy(self.report);edit(report)
        with self.assertRaises(ValueError):contract.verify_template_report(report)
    def test_well_formed_metadata_retains_limited_scope(self):
        result=contract.verify_template_report(self.report);self.assertTrue(result['controlledTemplateAcceptance']);self.assertFalse(result['fingerprintTemplateAcceptance']);self.assertFalse(result['realAccountLogin']);self.assertFalse(result['safeIdleApplicationAcceptance']);self.assertEqual(result['assertions'],181)
    def test_sdk_prototype_is_not_template_evidence(self):self.rejects(lambda r:r.update(diagnosticOnly=True,fixtureType='prototype'))
    def test_incomplete_context_cannot_pass(self):self.rejects(lambda r:r['cases'][0]['sessions'][0]['observed'].update(frame={'ua':'Firefox/157.0'}))
    def test_missing_main_language_type_cannot_pass(self):self.rejects(lambda r:r['cases'][0]['sessions'][0]['observed']['parent'].update(language=42))
    def test_script_request_is_not_actual_normalized_language(self):self.rejects(lambda r:r['cases'][2]['sessions'][0]['observed']['worker'].update(language='zh-Hant-TW'))
    def test_normalized_getter_cannot_replace_requested_descriptor(self):self.rejects(lambda r:r['cases'][2]['sessions'][0]['native'].update(getterLocales=['zh-TW']))
    def test_document_header_is_required(self):self.rejects(lambda r:r['cases'][0]['sessions'][0]['requestHeaders'].__delitem__(0))
    def test_wrong_http_ua_cannot_pass(self):self.rejects(lambda r:r['cases'][0]['sessions'][0]['requestHeaders'][0].update(userAgent='Java simulator'))
    def test_old_header_path_nonce_cannot_pass(self):self.rejects(lambda r:r['cases'][0]['sessions'][0]['requestHeaders'][0].update(path='/page?run='+('f'*32)+'&case=1&session=primary'))
    def test_duplicate_query_key_cannot_pass(self):self.rejects(lambda r:r['cases'][0]['sessions'][0]['requestHeaders'][0].update(path=r['cases'][0]['sessions'][0]['requestHeaders'][0]['path']+'&run='+r['runNonce']))
    def test_wrong_method_cannot_pass(self):self.rejects(lambda r:r['cases'][0]['sessions'][0]['requestHeaders'][0].update(method='POST'))
    def test_duplicate_sequence_cannot_pass(self):self.rejects(lambda r:r['cases'][0]['sessions'][0]['requestHeaders'][1].update(sequence=1))
    def test_zero_sequence_cannot_pass(self):self.rejects(lambda r:r['cases'][0]['sessions'][0]['requestHeaders'][0].update(sequence=0))
    def test_wrong_fetch_role_cannot_pass(self):self.rejects(lambda r:r['cases'][0]['sessions'][0]['requestHeaders'][3].update(path='/echo?run='+r['runNonce']+'&case=1&session=primary&kind=worker-fetch'))
    def test_other_origin_header_target_cannot_pass(self):self.rejects(lambda r:r['cases'][0]['sessions'][0]['requestHeaders'][0].update(path='https://other.example/page?run='+r['runNonce']+'&case=1&session=primary'))
    def test_unknown_schema_cannot_pass(self):self.rejects(lambda r:r.update(schema=2))
    def test_new_invocation_cannot_reuse_old_signals(self):self.rejects(lambda r:r['cases'][0]['sessions'][0]['observed'].update(run='f'*32))
    def test_unapplied_configuration_cannot_be_observed(self):self.rejects(lambda r:r['appliedCases'][0].update(appliedRevision=0))
    def test_slot_reuse_cannot_cross_observed_cases(self):self.rejects(lambda r:r['appliedCases'][3]['identity'].update(generation=1))
    def test_incomplete_audit_coverage_cannot_pass(self):self.rejects(lambda r:r['appliedCases'][0]['report']['contextCoverage']['frame'].update(missingOrInvalid=['memory']))
    def test_partial_checks_cannot_pass(self):self.rejects(lambda r:r['checks'].pop())
    def test_missing_template_case_cannot_pass(self):self.rejects(lambda r:r['appliedCases'].pop())
    def test_experimental_rfp_cannot_claim_verified_preset(self):self.rejects(lambda r:r.update(templateIds=['native-rfp-experimental']*4))
    def test_full_fingerprint_acceptance_cannot_be_invented(self):self.rejects(lambda r:r.update(fingerprintTemplateAcceptance=True))


class TemplateEvidenceGateTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.directory=Path(self.temp.name);self.report=metadata_only_report();self.write();self.write_host()
    def write_host(self):
        paths={'app/src/main/java/local/pocketchat/'+name+'.java' for name in ['BrowserIdentitySpec','AuditReport','IdentityTemplateController','FingerprintTemplateUi','BrowserEditIntent','DeferredBrowserSettings']}
        paths.update('app/src/main/assets/gecko/'+name for name in ['background.js','content.js','main-world-audit.js'])
        hashes={path:hashlib.sha256((ROOT/path).read_bytes()).hexdigest() for path in paths}
        base=dict(status='passed',actualAndroidExecution=False,sourceCommit='a'*40,sourceTree='b'*40,sourceDirty=False,sourceUnchangedDuringChecks=True,files=hashes)
        checks=[{'name':'Counterfeit metadata only '+str(i),'pass':True} for i in range(91)]
        template=dict(status='passed',actualAndroidExecution=False,passed=91,total=91,checks=checks)
        intent=dict(status='passed',actualAndroidExecution=False,passed=14,total=14,checks=checks[:14])
        host=dict(base,results=[dict(test='FingerprintTemplateTest',exitCode=0,output=json.dumps(template)),dict(test='BrowserEditIntentTest',exitCode=0,output=json.dumps(intent))])
        controller=dict(base,passed=74,total=74,checks=checks[:74])
        deferred=dict(base,passed=24,total=24,checks=checks[:24])
        bridge=dict(base,results=[dict(test='audit-bridge.test.cjs',passed=9,total=9),dict(test='protection-handshake.test.cjs',passed=3,total=3)])
        for name,value in [('profile-host-results.json',host),('identity-controller-host-results.json',controller),('deferred-browser-host-results.json',deferred),('identity-bridge-host-results.json',bridge)]:
            (self.directory/name).write_text(json.dumps(value))
    def write(self):
        raw=json.dumps(self.report).encode();(self.directory/'gecko-template-results.json').write_bytes(raw)
        log=dict(status='passed',sourceCommit='a'*40,buildIdentity=self.report['buildIdentity'],runNonce=self.report['runNonce'],installedBeforeAndAfterMatched=True,rawReportPreserved=True,reportSha256=hashlib.sha256(raw).hexdigest(),reportBytes=len(raw),diagnosticOnly=False,androidSdk=35)
        (self.directory/'gecko-template-runner-log.json').write_text(json.dumps(log))
    def verify(self):
        def source_bytes(source,path):return (ROOT/path).read_bytes() if path!='app/build.gradle' else b"versionCode 52; versionName '1.7.0'"
        with patch.object(gate,'selected_bytes',side_effect=source_bytes),patch.object(gate.subprocess,'check_output',return_value='b'*40):return gate.verify_template_evidence(self.directory,'a'*40)
    def test_complete_metadata_only_gate_preserves_scope(self):self.assertFalse(self.verify()['fingerprintTemplateAcceptance'])
    def test_raw_receipt_sha_change_is_rejected(self):
        (self.directory/'gecko-template-results.json').write_text(json.dumps(self.report)+' ')
        with self.assertRaises(ValueError):self.verify()
    def test_apk_source_mismatch_is_rejected(self):
        self.report['buildIdentity']['sourceCommit']='f'*40;self.write()
        with self.assertRaises(ValueError):self.verify()
    def test_apk_version_mismatch_is_rejected(self):
        self.report['buildIdentity']['versionCode']=51;self.write()
        with self.assertRaises(ValueError):self.verify()
    def test_host_source_hash_change_is_rejected(self):
        path=self.directory/'profile-host-results.json';host=json.loads(path.read_text());host['files']['app/src/main/assets/gecko/content.js']='0'*64;path.write_text(json.dumps(host))
        with self.assertRaises(ValueError):self.verify()
    def test_missing_controller_host_is_rejected(self):
        (self.directory/'identity-controller-host-results.json').unlink()
        with self.assertRaises(FileNotFoundError):self.verify()
    def test_native_failure_cannot_be_hidden_by_all_green_metadata(self):
        self.report['failureType']='NativeFailure';self.write()
        with self.assertRaises(ValueError):self.verify()


if __name__=='__main__':unittest.main()
