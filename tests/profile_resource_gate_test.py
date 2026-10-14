"""Counterfeit metadata only for rejection tests; never actual resource/device proof."""
import copy, hashlib, importlib.util, json, re, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from profile_template_gate_test import metadata_only_report
ROOT=Path(__file__).resolve().parents[1]
def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'tools/gecko'/f'{name}.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
contract=load('resource_invocation_contract');gate=load('check_resource_evidence');invocation=load('profile_invocation_contract')
NAMES=re.findall(r'resourceCheck\("([^"\n]+)"',(ROOT/'tests/gecko/ResourcePressureIntegrationActivity.java').read_text())
def metadata():
    report=metadata_only_report();report['buildIdentity'].update(version='2.0.0',versionCode=53)
    names=NAMES+contract.prototype_names();report.update(fixtureType='production-resource-pressure-controlled-v1',diagnosticOnly=True,capacityAcceptance=False,physicalDeviceAcceptance=False,fullDesktopUaConsistency=False,fingerprintTemplateAcceptance=False,fullTemplateAcceptance=False,resourceChecksCompleted=True,resourceChecks=[{'name':name,'pass':True} for name in NAMES],checks=[{'name':name,'pass':True} for name in names],passed=len(names),total=len(names),pid=123,nativeCustomCapabilities={name:'UNSUPPORTED' for name in contract.CUSTOM},resourceUncovered=['physical ARM capacity','Gecko child process PSS','real ChatGPT tasks','native file chooser gesture','real upload/download throughput','independent process restoration','desktop Worker fetch UA consistency'])
    report['allocation']=dict(coldRuntimeCreates=0,recoveryRuntimeCreates=1,pressureSource='synthetic-pressure-control',physicalCapacityAcceptance=False,actualRuntimeObject=456,oldEpoch=1,newEpoch=2,recoveredTarget=report['origin']+'/frame?run='+report['runNonce']+'&case=4&session=secondary')
    report['platformMemory']=dict(source='android-ActivityManager.MemoryInfo',known=True,lowMemory=False,availableBytes=1024,totalBytes=2048,thresholdBytes=256,sampledAt=1000,observedAt=1001,process=dict(source='android-Debug.MemoryInfo',pid=123,totalPssKb=1024,javaUsedBytes=512,javaMaxBytes=4096,scope='Current fixture app PID only; Gecko child processes excluded'))
    for index,case in enumerate(report['cases']):
        for session in case['sessions']:
            desktop=index==1 or session['name']=='secondary'
            ua='Mozilla/5.0 (X11; Linux x86_64; rv:157.0) Gecko/20100101 Firefox/157.0' if desktop else report['sdkUserAgentBaseline']['userAgent']
            session['native']['userAgent']=ua
            for context in ['parent','frame','worker','blobWorker']:session['observed'][context].update(ua=ua,origin=report['origin'])
            for row in session['requestHeaders']:row['userAgent']=report['sdkUserAgentBaseline']['userAgent'] if row['role'] in ['worker-fetch','blob-worker-fetch'] else ua
            session['userAgentScope']=dict(documentHeadersMatchSession=True,workerFetchHeadersMatchSdkDefault=True,workerFetchHeadersMatchSession=not desktop,workerFetchHeaderMismatch=desktop,observedUserAgentUniform=not desktop,fullTemplateAcceptance=False)
        case['workerFetchMismatchSessions']=[row['name'] for row in case['sessions'] if row['userAgentScope']['workerFetchHeaderMismatch']]
        case['fullTemplateAcceptance']=False
    return report
class ResourceContractTest(unittest.TestCase):
    def setUp(self):self.report=metadata()
    def rejects(self,edit):
        value=copy.deepcopy(self.report);edit(value)
        with self.assertRaises(ValueError):contract.verify_resource_report(value,NAMES)
    def test_complete_metadata_retains_diagnostic_scope(self):
        value=contract.verify_resource_report(self.report,NAMES);self.assertTrue(value['diagnosticOnly']);self.assertFalse(value['capacityAcceptance']);self.assertFalse(value['physicalDeviceAcceptance']);self.assertEqual(value['controlledSdkChecks'],138)
    def test_failure_cannot_hide_behind_green_metadata(self):self.rejects(lambda r:r.update(failureType="NativeFailure"))
    def test_boolean_counters_are_not_runtime_counts(self):self.rejects(lambda r:r["allocation"].update(coldRuntimeCreates=False))
    def test_guard_assertions_are_appended_after_original_sdk_checks(self):
        names=contract.prototype_names();self.assertEqual(len(names[:-9]),129);self.assertEqual(names[-9:],list(contract._guard.GUARD_CHECK_NAMES))
    def test_missing_actual_guard_evidence(self):self.rejects(lambda r:r.pop("guardEvidence"))
    def test_guard_tcp_cannot_hide_a_new_connection(self):self.rejects(lambda r:r["guardEvidence"]["afterServer"].update(acceptedConnections=r["guardEvidence"]["beforeServer"]["acceptedConnections"]+1))
    def test_guard_native_sender_is_bound(self):self.rejects(lambda r:r["guardEvidence"]["nativePort"].update(nativeSession=999))
    def test_actual_sdk_worker_mismatch_remains_visible(self):
        result=contract.verify_resource_report(self.report,NAMES);self.assertFalse(result['fullDesktopUaConsistency']);self.assertFalse(result['fingerprintTemplateAcceptance']);self.assertFalse(result['fullTemplateAcceptance']);self.assertEqual(result['workerFetchMismatchSessions'],[{'case':0,'sessions':[]},{'case':1,'sessions':['primary']},{'case':2,'sessions':[]},{'case':3,'sessions':['secondary']}])
    def test_missing_independent_sdk_default(self):self.rejects(lambda r:r.pop('sdkUserAgentBaseline'))
    def test_static_default_is_not_runtime_ack(self):self.rejects(lambda r:r['sdkUserAgentBaseline'].update(runtimeAcknowledgement=True))
    def test_desktop_worker_headers_cannot_be_rewritten_to_session(self):self.rejects(lambda r:r['cases'][1]['sessions'][0]['requestHeaders'][4].update(userAgent=r['cases'][1]['sessions'][0]['native']['userAgent']))
    def test_raw_worker_mismatch_cannot_be_hidden(self):self.rejects(lambda r:r['cases'][1]['sessions'][0]['userAgentScope'].update(workerFetchHeaderMismatch=False))
    def test_case_worker_mismatch_cannot_be_hidden(self):self.rejects(lambda r:r['cases'][3].update(workerFetchMismatchSessions=[]))
    def test_full_desktop_ua_claim_rejected(self):self.rejects(lambda r:r.update(fullDesktopUaConsistency=True))
    def test_fingerprint_claim_rejected(self):self.rejects(lambda r:r.update(fingerprintTemplateAcceptance=True))
    def test_wrong_schema(self):self.rejects(lambda r:r.update(schema=2))
    def test_wrong_sdk(self):self.rejects(lambda r:r.update(sdkAarSha256='f'*64))
    def test_physical_capacity_claim(self):self.rejects(lambda r:r.update(capacityAcceptance=True))
    def test_fake_native_claim(self):self.rejects(lambda r:r['nativeCustomCapabilities'].update(INDEPENDENT_TIMEZONE='VERIFIED'))
    def test_missing_resource_assertion(self):self.rejects(lambda r:r['resourceChecks'].pop())
    def test_duplicate_resource_assertion(self):self.rejects(lambda r:r['resourceChecks'].__setitem__(1,r['resourceChecks'][0]))
    def test_missing_parent_assertion(self):self.rejects(lambda r:r['checks'].pop())
    def test_false_resource_assertion(self):self.rejects(lambda r:r['resourceChecks'][0].update(**{'pass':False}))
    def test_runtime_created_while_deferred(self):self.rejects(lambda r:r['allocation'].update(coldRuntimeCreates=1))
    def test_old_deadline(self):self.rejects(lambda r:r['allocation'].update(newEpoch=1))
    def test_unbound_candidate(self):self.rejects(lambda r:r['allocation'].update(recoveredTarget='https://chatgpt.com/'))
    def test_fake_platform_source(self):self.rejects(lambda r:r['platformMemory'].update(source='synthetic-pressure-control'))
    def test_invalid_platform_bytes(self):self.rejects(lambda r:r['platformMemory'].update(availableBytes=-1))
    def test_stale_platform_snapshot(self):self.rejects(lambda r:r['platformMemory'].update(observedAt=10000))
    def test_pid_scope(self):self.rejects(lambda r:r['platformMemory']['process'].update(pid=999))
    def test_missing_limits(self):self.rejects(lambda r:r.update(resourceUncovered=[]))
    def test_actual_context_incomplete(self):self.rejects(lambda r:r['cases'][0]['sessions'][0]['observed'].update(worker={}))
    def test_actual_language_mismatch(self):self.rejects(lambda r:r['cases'][2]['sessions'][0]['observed']['worker'].update(language='zh-Hant-TW'))
    def test_other_origin_header(self):self.rejects(lambda r:r['cases'][0]['sessions'][0]['requestHeaders'][0].update(path='https://other.test'+r['cases'][0]['sessions'][0]['requestHeaders'][0]['path']))
    def test_fragment_header(self):self.rejects(lambda r:r['cases'][0]['sessions'][0]['requestHeaders'][0].update(path=r['cases'][0]['sessions'][0]['requestHeaders'][0]['path']+'#fake'))
    def test_duplicate_header_query(self):self.rejects(lambda r:r['cases'][0]['sessions'][0]['requestHeaders'][0].update(path=r['cases'][0]['sessions'][0]['requestHeaders'][0]['path']+'&run='+r['runNonce']))
    def test_wrong_method(self):self.rejects(lambda r:r['cases'][0]['sessions'][0]['requestHeaders'][0].update(method='POST'))
    def test_duplicate_role(self):self.rejects(lambda r:r['cases'][0]['sessions'][0]['requestHeaders'][1].update(role='page'))
    def test_wrong_document_nonce(self):self.rejects(lambda r:r['cases'][0]['sessions'][0]['observed'].update(run='f'*32))
    def test_header_sequence(self):self.rejects(lambda r:r['cases'][0]['sessions'][0]['requestHeaders'][1].update(sequence=1))
class ResourceGateTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.directory=Path(self.temp.name);self.report=metadata();self.write()
        # Explicit counterfeit baseline/template receipts exercise the cross-
        # phase byte-identity gate; they are never exported as device proof.
        identity=copy.deepcopy(self.report['buildIdentity'])
        device=dict(status='passed',sourceCommit='a'*40,actualAndroidExecution=True,releaseMode=True,diagnosticOnly=False,androidSdk=35,eventTransport=dict(buildIdentity=identity),artifactErrors=[])
        (self.directory/'device-results.json').write_text(json.dumps(device))
        template=metadata_only_report();template.update(buildIdentity=copy.deepcopy(identity),runNonce='f'*32)
        template_raw=json.dumps(template).encode();(self.directory/'gecko-template-results.json').write_bytes(template_raw)
        template_log=dict(status='passed',sourceCommit='a'*40,buildIdentity=copy.deepcopy(identity),runNonce=template['runNonce'],installedBeforeAndAfterMatched=True,rawReportPreserved=True,reportSha256=hashlib.sha256(template_raw).hexdigest(),reportBytes=len(template_raw),diagnosticOnly=False,androidSdk=35)
        (self.directory/'gecko-template-runner-log.json').write_text(json.dumps(template_log))
        names=re.findall(r'check\("([^"\n]+)"',(ROOT/'tests/resource-pressure-host/local/pocketchat/ResourcePressureHostTest.java').read_text())
        paths=['app/src/main/java/local/pocketchat/ResourcePressureController.java','tools/gecko/run_resource_host_checks.py','tests/resource-pressure-host/local/pocketchat/ResourcePressureHostTest.java','tests/resource-pressure-host/android/app/ActivityManager.java','tests/resource-pressure-host/android/content/Context.java','tests/resource-pressure-host/android/os/SystemClock.java']
        host=dict(status='passed',actualAndroidExecution=False,synthetic=True,capacityAcceptance=False,actualPlatformMemoryObservation=False,sourceCommit='a'*40,sourceTree='b'*40,sourceDirty=False,sourceUnchangedDuringChecks=True,passed=len(names),total=len(names),executed=len(names),checks=[{'name':n,'pass':True} for n in names],expectedCheckNames=names,files={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths})
        (self.directory/'resource-pressure-host-results.json').write_text(json.dumps(host))
        observer_names=re.findall(r"test\('([^'\n]+)'",(ROOT/'tests/resource-web-observer.cjs').read_text())
        observer_paths=['app/src/main/assets/web-reply-observer.js','app/src/main/assets/page-driver.js','tests/resource-web-observer.cjs','tools/gecko/run_resource_observer_host.py']
        observer=dict(host,expectedCheckNames=observer_names,passed=len(observer_names),total=len(observer_names),executed=len(observer_names),failed=0,exitCode=0,checks=[{'name':n,'pass':True,'index':i+1} for i,n in enumerate(observer_names)],actualPerformanceMeasurement=False,realWebsiteExecution=False,pageDriverExecuted=False,files={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in observer_paths})
        (self.directory/'resource-observer-host-results.json').write_text(json.dumps(observer))
    def write(self):
        raw=json.dumps(self.report).encode();(self.directory/'resource-pressure-results.json').write_bytes(raw)
        log=dict(status='passed',sourceCommit='a'*40,buildIdentity=self.report['buildIdentity'],runNonce=self.report['runNonce'],installedBeforeAndAfterMatched=True,rawReportPreserved=True,reportSha256=hashlib.sha256(raw).hexdigest(),reportBytes=len(raw),diagnosticOnly=True,androidSdk=35)
        (self.directory/'resource-pressure-runner-log.json').write_text(json.dumps(log))
    def verify(self):
        def selected(source,path):return b"versionCode 53; versionName '2.0.0'" if path=='app/build.gradle' else (ROOT/path).read_bytes()
        with patch.object(gate,'selected_bytes',side_effect=selected),patch.object(gate,'selected_contract',side_effect=lambda source,name:contract if name=='resource_invocation_contract' else invocation),patch.object(gate.subprocess,'check_output',return_value='b'*40):return gate.verify_resource_evidence(self.directory,'a'*40)
    def test_complete_metadata_preserves_scope(self):
        value=self.verify();self.assertFalse(value['capacityAcceptance']);self.assertTrue(value['sameInstalledApkAcrossRegressions']);self.assertEqual(value['androidSdk'],35)
    def reject_linked_edit(self,name,edit,message):
        path=self.directory/name;original=path.read_bytes();value=json.loads(original);edit(value)
        path.write_text(json.dumps(value))
        if name=='gecko-template-results.json':
            log_path=self.directory/'gecko-template-runner-log.json';original_log=log_path.read_bytes();log=json.loads(original_log);raw=path.read_bytes();log.update(reportSha256=hashlib.sha256(raw).hexdigest(),reportBytes=len(raw));log_path.write_text(json.dumps(log))
        try:
            with self.assertRaisesRegex(ValueError,message):self.verify()
        finally:
            path.write_bytes(original)
            if name=='gecko-template-results.json':log_path.write_bytes(original_log)
    def linked_identity_edits(self,key,value):
        for name in ['device-results.json','gecko-template-results.json','gecko-template-runner-log.json']:
            with self.subTest(file=name,field=key):
                def edit(report):
                    identity=report['eventTransport']['buildIdentity'] if name=='device-results.json' else report['buildIdentity']
                    self.assertEqual(identity['sourceCommit'],'a'*40);self.assertEqual(identity['sourceTree'],'b'*40);identity[key]=value
                self.reject_linked_edit(name,edit,'Installed test APK differs.*'+key)
    def test_same_source_different_installed_apk_sha(self):self.linked_identity_edits('apkSha256','0'*64)
    def test_same_source_different_installed_apk_size(self):self.linked_identity_edits('apkBytes',101)
    def test_same_source_different_installed_build_stamp(self):self.linked_identity_edits('buildStampSha256','0'*64)
    def test_same_installed_apk_different_android_sdk(self):
        for name in ['device-results.json','gecko-template-results.json','gecko-template-runner-log.json']:
            with self.subTest(file=name):self.reject_linked_edit(name,lambda report:report.update(androidSdk=36),'same actual Android SDK')
    def test_missing_baseline_installed_identity(self):self.reject_linked_edit('device-results.json',lambda report:report.pop('eventTransport'),'Installed test APK differs')
    def test_diagnostic_subset_is_not_full_device_baseline(self):self.reject_linked_edit('device-results.json',lambda report:report.update(diagnosticOnly=True),'full same-source device baseline')
    def test_template_diagnostic_is_not_template_acceptance(self):self.reject_linked_edit('gecko-template-results.json',lambda report:report.update(diagnosticOnly=True),'raw installed/invocation-bound template evidence')
    def test_template_raw_report_is_preserved(self):
        path=self.directory/'gecko-template-results.json';path.write_bytes(path.read_bytes()+b' ')
        with self.assertRaisesRegex(ValueError,'raw installed/invocation-bound template evidence'):self.verify()
    def test_template_invocation_nonce_is_bound(self):self.reject_linked_edit('gecko-template-runner-log.json',lambda report:report.update(runNonce='0'*32),'another fixture invocation')
    def test_changed_raw_bytes(self):
        p=self.directory/'resource-pressure-results.json';p.write_bytes(p.read_bytes()+b' ')
        with self.assertRaises(ValueError):self.verify()
    def test_apk_source_mismatch(self):
        self.report['buildIdentity']['sourceCommit']='f'*40;self.write()
        with self.assertRaises(ValueError):self.verify()
    def test_apk_nonce_mismatch(self):
        self.report['runNonce']='f'*32;self.write();p=self.directory/'resource-pressure-runner-log.json';v=json.loads(p.read_text());v['runNonce']='e'*32;p.write_text(json.dumps(v))
        with self.assertRaises(ValueError):self.verify()
    def test_changed_host_source(self):
        p=self.directory/'resource-pressure-host-results.json';v=json.loads(p.read_text());v['files']['app/src/main/java/local/pocketchat/ResourcePressureController.java']='0'*64;p.write_text(json.dumps(v))
        with self.assertRaises(ValueError):self.verify()
    def test_changed_observer_source(self):
        p=self.directory/'resource-observer-host-results.json';v=json.loads(p.read_text());v['files']['app/src/main/assets/web-reply-observer.js']='0'*64;p.write_text(json.dumps(v))
        with self.assertRaises(ValueError):self.verify()
    def test_observer_false_check(self):
        p=self.directory/'resource-observer-host-results.json';v=json.loads(p.read_text());v['checks'][0]['pass']=False;p.write_text(json.dumps(v))
        with self.assertRaises(ValueError):self.verify()
    def test_observer_dirty_source(self):
        p=self.directory/'resource-observer-host-results.json';v=json.loads(p.read_text());v['sourceDirty']=True;p.write_text(json.dumps(v))
        with self.assertRaises(ValueError):self.verify()
    def test_host_scope_mismatch(self):
        p=self.directory/'resource-pressure-host-results.json';v=json.loads(p.read_text());v['actualAndroidExecution']=True;p.write_text(json.dumps(v))
        with self.assertRaises(ValueError):self.verify()
if __name__=='__main__':unittest.main()
