"""Counterfeit metadata only for rejection tests; never actual resource/device proof."""
import copy, hashlib, importlib.util, json, os, re, shutil, subprocess, tempfile, unittest
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
    report['allocation']=dict(coldRuntimeCreates=0,recoveryRuntimeCreates=1,pressureSource='synthetic-pressure-control',physicalCapacityAcceptance=False,actualRuntimeObject=report['cases'][0]['sessions'][0]['native']['runtime'],oldEpoch=1,newEpoch=2,recoveredTarget=report['origin']+'/resource?run='+report['runNonce']+'&phase=parent')
    parent_url=report['allocation']['recoveredTarget']+'&spa=1';popup_url=report['origin']+'/resource?run='+report['runNonce']+'&phase=popup'
    bindings=['11111111-1111-1111-1111-111111111111','22222222-2222-2222-2222-222222222222','33333333-3333-3333-3333-333333333333']
    def event(url,binding,document,sequence,at,busy=True,uploading=True):return dict(type='resource-work',url=url,resourceBinding=binding,documentId=document,resourceSequence=sequence,capturedAt=at,busy=busy,uploading=uploading)
    rejection=dict(websiteEpoch=-1,sequence=0,observerBinding=bindings[2],observerPort=100,navigationEpoch=3)
    untouched=dict(draft='retained-resource-draft',cookie='resourceRetained=preserved',url=parent_url,sent=0)
    parent_session=report['cases'][0]['sessions'][0]['native']['session']
    report['resourcePortControls']=dict(sourceCommit=report['sourceCommit'],runNonce=report['runNonce'],phaseScope='controlled-production-delegate-sdk-open-load',syntheticPopupActivation=True,trustedPopupGesture=False,trustedUserGesture=False,realWebsiteExecution=False,observerDelivery='Actual SDK document observer bytes read through native evaluate; unchanged bytes passed to production resource admission',parentSession=parent_session,parentPort=100,popupSession=parent_session+2,popupPort=200,returnedSession=parent_session,returnedPort=100,parentEpochBefore=1,popupEpoch=2,returnEpoch=3,parentBeforeBinding=bindings[0],popupBinding=bindings[1],parentReturnedBinding=bindings[2],parentBefore=event(parent_url,bindings[0],'a'*32,1,1000),popup=event(popup_url,bindings[1],'b'*32,1,2000),parentReturned=event(parent_url,bindings[2],'a'*32,2,3000),parentIdle=event(parent_url,bindings[2],'a'*32,3,4000,False,False),stalePopupAfter=dict(rejection),staleParentAfter=dict(rejection),before=dict(untouched),after=dict(untouched))
    report['resourceRequests']=[]
    for sequence,phase in enumerate(('parent','popup'),1):
        target='/resource?run='+report['runNonce']+'&phase='+phase;line='GET '+target+' HTTP/1.1';document=contract.resource_bootstrap_document(phase)
        report['resourceRequests'].append(dict(sourceCommit=report['sourceCommit'],runNonce=report['runNonce'],sequence=sequence,connection=sequence,method='GET',path=target,phase=phase,userAgent='Observed Firefox/157.0',acceptLanguage='en-US',requestAt=sequence*100,responseAt=sequence*100+1,responseStatus=200,responseBytes=len(document),responseSha256=hashlib.sha256(document).hexdigest(),parsedRequestLine=line,parsedRequestLineBytes=len(line.encode('ascii')),parsedRequestLineSha256=hashlib.sha256(line.encode('ascii')).hexdigest(),requestLineScope='Parsed HTTP request line without CRLF; not a raw socket-byte capture'))
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
    def test_missing_retained_resource_raw_controls(self):self.rejects(lambda r:r.pop('resourcePortControls'))
    def test_retained_controls_source_is_owned(self):self.rejects(lambda r:r['resourcePortControls'].update(sourceCommit='f'*40))
    def test_retained_controls_invocation_is_owned(self):self.rejects(lambda r:r['resourcePortControls'].update(runNonce='f'*32))
    def test_direct_popup_delegate_cannot_claim_trusted_gesture(self):self.rejects(lambda r:r['resourcePortControls'].update(trustedPopupGesture=True))
    def test_loopback_controls_cannot_claim_real_website(self):self.rejects(lambda r:r['resourcePortControls'].update(realWebsiteExecution=True))
    def test_collected_observer_bytes_cannot_claim_original_transport(self):self.rejects(lambda r:r['resourcePortControls'].update(observerDelivery='Actual website native reply transport'))
    def test_retained_parent_sdk_identity(self):self.rejects(lambda r:r['resourcePortControls'].update(returnedSession=20))
    def test_retained_parent_matches_inherited_sdk_session(self):self.rejects(lambda r:r['resourcePortControls'].update(parentSession=30,returnedSession=30))
    def test_runtime_matches_inherited_sdk_runtime(self):self.rejects(lambda r:r['allocation'].update(actualRuntimeObject=999))
    def test_retained_parent_port_identity(self):self.rejects(lambda r:r['resourcePortControls'].update(returnedPort=200))
    def test_popup_has_distinct_native_port(self):self.rejects(lambda r:r['resourcePortControls'].update(popupPort=100))
    def test_return_epoch_advances(self):self.rejects(lambda r:r['resourcePortControls'].update(returnEpoch=2))
    def test_boolean_native_epoch_is_not_observation(self):self.rejects(lambda r:r['resourcePortControls'].update(parentEpochBefore=True))
    def test_parent_return_document_is_retained(self):self.rejects(lambda r:r['resourcePortControls']['parentReturned'].update(documentId='b'*32))
    def test_popup_document_is_distinct(self):self.rejects(lambda r:r['resourcePortControls']['popup'].update(documentId='a'*32))
    def test_parent_return_activation_binding_is_fresh(self):self.rejects(lambda r:r['resourcePortControls']['parentReturned'].update(resourceBinding=r['resourcePortControls']['parentBefore']['resourceBinding']))
    def test_actual_observer_binding_matches_native_activation(self):self.rejects(lambda r:r['resourcePortControls'].update(parentReturnedBinding=r['resourcePortControls']['parentBeforeBinding']))
    def test_idle_has_returned_parent_binding(self):self.rejects(lambda r:r['resourcePortControls']['parentIdle'].update(resourceBinding=r['resourcePortControls']['popup']['resourceBinding']))
    def test_parent_return_has_exact_owned_url(self):self.rejects(lambda r:r['resourcePortControls']['parentReturned'].update(url=r['resourcePortControls']['parentReturned']['url']+'&other=1'))
    def test_popup_has_exact_owned_nonce(self):self.rejects(lambda r:r['resourcePortControls']['popup'].update(url=r['resourcePortControls']['popup']['url'].replace(r['runNonce'],'f'*32)))
    def test_raw_observer_busy_state_must_be_boolean(self):self.rejects(lambda r:r['resourcePortControls']['parentReturned'].update(busy=1))
    def test_retained_parent_busy_to_idle_is_observed(self):self.rejects(lambda r:r['resourcePortControls']['parentIdle'].update(busy=True))
    def test_retained_parent_upload_ends_in_actual_idle(self):self.rejects(lambda r:r['resourcePortControls']['parentIdle'].update(uploading=True))
    def test_parent_return_sequence_is_fresh(self):self.rejects(lambda r:r['resourcePortControls']['parentReturned'].update(resourceSequence=1))
    def test_resource_capture_times_follow_actual_popup_order(self):self.rejects(lambda r:r['resourcePortControls']['popup'].update(capturedAt=5000))
    def test_stale_popup_cannot_authorize_website_epoch(self):self.rejects(lambda r:r['resourcePortControls']['stalePopupAfter'].update(websiteEpoch=3))
    def test_stale_parent_cannot_advance_sequence(self):self.rejects(lambda r:r['resourcePortControls']['staleParentAfter'].update(sequence=1))
    def test_stale_popup_cannot_rebind_parent_port(self):self.rejects(lambda r:r['resourcePortControls']['stalePopupAfter'].update(observerPort=200))
    def test_stale_parent_cannot_restore_previous_binding(self):self.rejects(lambda r:r['resourcePortControls']['staleParentAfter'].update(observerBinding=r['resourcePortControls']['parentBefore']['resourceBinding']))
    def test_retained_rebind_preserves_controlled_draft(self):self.rejects(lambda r:r['resourcePortControls']['after'].update(draft='lost draft'))
    def test_retained_rebind_preserves_controlled_cookie(self):self.rejects(lambda r:r['resourcePortControls']['after'].update(cookie=''))
    def test_retained_rebind_cannot_send_any_message(self):self.rejects(lambda r:r['resourcePortControls']['after'].update(sent=1))
    def test_resource_http_receipts_are_required(self):self.rejects(lambda r:r.pop('resourceRequests'))
    def test_resource_http_phase_count_is_exact(self):self.rejects(lambda r:r['resourceRequests'].append(dict(r['resourceRequests'][0])))
    def test_resource_http_source_is_owned(self):self.rejects(lambda r:r['resourceRequests'][0].update(sourceCommit='f'*40))
    def test_resource_http_nonce_is_owned(self):self.rejects(lambda r:r['resourceRequests'][1].update(runNonce='f'*32))
    def test_resource_http_get_is_required(self):self.rejects(lambda r:r['resourceRequests'][0].update(method='POST'))
    def test_resource_http_phase_is_exact(self):self.rejects(lambda r:r['resourceRequests'][1].update(phase='parent'))
    def test_resource_http_sequence_is_exact(self):self.rejects(lambda r:r['resourceRequests'][1].update(sequence=1))
    def test_resource_http_query_cannot_add_another_phase(self):self.rejects(lambda r:r['resourceRequests'][0].update(path=r['resourceRequests'][0]['path']+'&phase=popup'))
    def test_resource_http_target_cannot_be_absolute(self):self.rejects(lambda r:r['resourceRequests'][0].update(path=r['origin']+r['resourceRequests'][0]['path']))
    def test_resource_http_target_cannot_contain_fragment(self):self.rejects(lambda r:r['resourceRequests'][0].update(path=r['resourceRequests'][0]['path']+'#other'))
    def test_resource_http_receipt_cannot_claim_raw_socket_bytes(self):self.rejects(lambda r:r['resourceRequests'][0].update(requestLineScope='Raw socket bytes'))
    def test_resource_parsed_line_bytes_are_preserved(self):self.rejects(lambda r:r['resourceRequests'][0].update(parsedRequestLineBytes=0))
    def test_resource_parsed_line_hash_is_preserved(self):self.rejects(lambda r:r['resourceRequests'][0].update(parsedRequestLineSha256='0'*64))
    def test_resource_response_status_is_actual_success(self):self.rejects(lambda r:r['resourceRequests'][1].update(responseStatus=403))
    def test_resource_response_visible_body_bytes_are_exact(self):self.rejects(lambda r:r['resourceRequests'][0].update(responseBytes=0,responseSha256=hashlib.sha256(b'').hexdigest()))
    def test_resource_response_phase_body_cannot_be_swapped(self):self.rejects(lambda r:r['resourceRequests'][1].update(responseSha256=r['resourceRequests'][0]['responseSha256']))
    def test_resource_response_connection_is_distinct(self):self.rejects(lambda r:r['resourceRequests'][1].update(connection=1))
    def test_resource_response_times_follow_parent_then_popup(self):self.rejects(lambda r:r['resourceRequests'][1].update(requestAt=50))
    def test_resource_http_headers_are_observed(self):self.rejects(lambda r:r['resourceRequests'][0].update(userAgent=''))
class ResourceBootstrapPolicyTest(unittest.TestCase):
    def test_actual_java_bootstrap_policy_rejects_wrong_authority_and_renders_visible_body(self):
        def method(path,signature):
            source=(ROOT/path).read_text();start=source.index(signature);end=source.index('\n  }',start)+4;return source[start:end]
        policy=method('tests/gecko/ResourcePressureIntegrationActivity.java','static String bootstrapDocument(')
        default=method('tests/gecko/GeckoIdentityPrototypeIntegrationActivity.java','String resourceFixtureDocument(').split('\n',1)[0]
        java=os.environ.get('PROFILE_JAVA') or shutil.which('java')
        self.assertTrue(java,'JDK 17 is required to execute the actual extracted Java fixture policy')
        harness='''import java.util.*;
public final class ResourceBootstrapPolicyControl {
POLICY
DEFAULT
static void check(boolean value){if(!value)throw new AssertionError("Actual resource bootstrap policy failed");}
public static void main(String[] args){String nonce="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";Map<String,String> query=new HashMap<>();query.put("run",nonce);query.put("phase","parent");String parent=bootstrapDocument("GET",query,nonce);check(parent!=null&&parent.contains("<p>")&&parent.contains("<input ")&&!parent.contains("<script"));check(parent.equals(PARENT));query.put("phase","popup");check(bootstrapDocument("GET",query,nonce).equals(POPUP));check(new ResourceBootstrapPolicyControl().resourceFixtureDocument("GET",query)==null);for(String invalid:new String[]{"POST","HEAD","get"})check(bootstrapDocument(invalid,query,nonce)==null);check(bootstrapDocument("GET",query,"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb")==null);check(bootstrapDocument("GET",query,"wrong")==null);check(bootstrapDocument("GET",query,null)==null);check(bootstrapDocument("GET",null,nonce)==null);query.put("phase","other");check(bootstrapDocument("GET",query,nonce)==null);query.put("phase","parent");query.put("unexpected","1");check(bootstrapDocument("GET",query,nonce)==null);query.remove("unexpected");query.remove("run");check(bootstrapDocument("GET",query,nonce)==null);}
}'''.replace('POLICY',policy).replace('DEFAULT',default).replace('PARENT',json.dumps(contract.resource_bootstrap_document('parent').decode())).replace('POPUP',json.dumps(contract.resource_bootstrap_document('popup').decode()))
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'ResourceBootstrapPolicyControl.java';path.write_text(harness)
            compile=subprocess.run([java,'-m','jdk.compiler/com.sun.tools.javac.Main',str(path)],text=True,capture_output=True,timeout=30);self.assertEqual(compile.returncode,0,compile.stderr)
            run=subprocess.run([java,'-cp',temp,'ResourceBootstrapPolicyControl'],text=True,capture_output=True,timeout=30);self.assertEqual(run.returncode,0,run.stderr)
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
