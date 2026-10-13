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
    names=NAMES+contract.prototype_names();report.update(fixtureType='production-resource-pressure-controlled-v1',diagnosticOnly=True,capacityAcceptance=False,physicalDeviceAcceptance=False,resourceChecksCompleted=True,resourceChecks=[{'name':name,'pass':True} for name in NAMES],checks=[{'name':name,'pass':True} for name in names],passed=len(names),total=len(names),pid=123,nativeCustomCapabilities={name:'UNSUPPORTED' for name in contract.CUSTOM},resourceUncovered=['physical ARM capacity','Gecko child process PSS','real ChatGPT tasks','native file chooser gesture','real upload/download throughput','independent process restoration'])
    report['allocation']=dict(coldRuntimeCreates=0,recoveryRuntimeCreates=1,pressureSource='synthetic-pressure-control',physicalCapacityAcceptance=False,actualRuntimeObject=456,oldEpoch=1,newEpoch=2,recoveredTarget=report['origin']+'/frame?run='+report['runNonce']+'&case=4&session=secondary')
    report['platformMemory']=dict(source='android-ActivityManager.MemoryInfo',known=True,lowMemory=False,availableBytes=1024,totalBytes=2048,thresholdBytes=256,sampledAt=1000,observedAt=1001,process=dict(source='android-Debug.MemoryInfo',pid=123,totalPssKb=1024,javaUsedBytes=512,javaMaxBytes=4096,scope='Current fixture app PID only; Gecko child processes excluded'))
    for index,case in enumerate(report['cases']):
        for session in case['sessions']:
            desktop=index==1 or session['name']=='secondary'
            ua=('Mozilla/5.0 (X11; Linux x86_64; rv:157.0)' if desktop else 'Mozilla/5.0 (Android 14; Mobile; rv:157.0)')+' Gecko/157.0 Firefox/157.0'
            session['native']['userAgent']=ua
            for context in ['parent','frame','worker','blobWorker']:session['observed'][context].update(ua=ua,origin=report['origin'])
            for row in session['requestHeaders']:row['userAgent']=ua
    return report
class ResourceContractTest(unittest.TestCase):
    def setUp(self):self.report=metadata()
    def rejects(self,edit):
        value=copy.deepcopy(self.report);edit(value)
        with self.assertRaises(ValueError):contract.verify_resource_report(value,NAMES)
    def test_complete_metadata_retains_diagnostic_scope(self):
        value=contract.verify_resource_report(self.report,NAMES);self.assertTrue(value['diagnosticOnly']);self.assertFalse(value['capacityAcceptance']);self.assertFalse(value['physicalDeviceAcceptance']);self.assertEqual(value['controlledSdkChecks'],129)
    def test_failure_cannot_hide_behind_green_metadata(self):self.rejects(lambda r:r.update(failureType="NativeFailure"))
    def test_boolean_counters_are_not_runtime_counts(self):self.rejects(lambda r:r["allocation"].update(coldRuntimeCreates=False))
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
    def test_complete_metadata_preserves_scope(self):self.assertFalse(self.verify()['capacityAcceptance'])
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
