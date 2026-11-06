"""Synthetic hostile combo packets; checker behavior, never Android proof."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import types
import unittest
os.environ.setdefault('GIT_NO_LAZY_FETCH','1')
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('combo_current_checker',ROOT/'tools/browser/check_gecko_cpu_ip_combo_evidence.py');gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)
import gecko_ip_timezone_evidence_test as modeled
SOURCE,TREE,NONCE=modeled.SOURCE,modeled.TREE,modeled.NONCE


def fixture():
    previous,expected=modeled.IpEvidenceTests().fixture();sample=previous['activity']['cases']['default-socks'];identity=sample['native']['identity'];setup=copy.deepcopy(previous['activity']['setup']);before=copy.deepcopy(setup)
    for key in ('defaultSpec','defaultRevision','loadedIdentity'):before.pop(key)
    before['actualDefaultStoreLoadYet']=False
    page=copy.deepcopy(sample['page']);page.pop('nativeUserAgent');page.update(hardwareConcurrency=1,nativeGetter=True,phase='gecko-new-york',origin='https://fp-a.pocketchat.test')
    process=dict(pid=7711,uid=10123,name=gate.PROCESS)
    cpu=dict(schema=1,engine='gecko',desiredRevision=2,desiredMode='1',activeBootRevision=2,activeBootMode='1',state='ready',issue='',failureCode='',pendingColdStart=False,configuredCap=1,defaultCap=1,hasUserValue=False,rfpPriority=False,nativeSettingReadback=True,startupReconciled=True,scope='runtime-wide',processNonce='e'*32,pid=7711,runtimeNonce='f'*32,environmentId=identity['environmentId'],environmentGeneration=identity['generation'],slot=6,pageObservationVerified=False,workerCoverageVerified=False,serviceWorkerCoverageVerified=False,persistentWorkerColdStartVerified=False)
    activity=dict(schema=1,fixtureType=gate.FIXTURE_TYPE,status='passed',stage='complete',failure='',sourceCommit=SOURCE,sourceTree=TREE,runNonce=NONCE,buildIdentity=copy.deepcopy(expected),activityClass=gate.ACTIVITY,scopeAllocationActivity=gate.SCOPE_ACTIVITY,setup=setup,cpuSetup=dict(cpuSealedRecordMissingBefore=True,actualColdStoreSave=True,loadedMode='automatic',loadedRevision=1,savedMode='1',savedRevision=2,identity=copy.deepcopy(identity),sessionAbsentBeforeSetup=True),cpuStoredState=dict(identity=copy.deepcopy(identity),revision=2,spec=dict(schema=1,engine='gecko',mode='1')),process=process,page=page,native=copy.deepcopy(sample['native']),cpuPolicy=cpu,runtimeCpuPolicy=copy.deepcopy(cpu),freshCpuReadback=dict(configuredCap=1,defaultCap=1,hasUserValue=False,rfpPriority=False),tls=copy.deepcopy(sample['security']),checks=[dict(id=name,**{'pass':True}) for name in gate.CHECKS],nativeEvents=[dict(sequence=1,kind='page-start',targetOwned=True,sessionId=sample['native']['sessionId'],navigation=1),dict(sequence=2,kind='page-stop-true',targetOwned=True,sessionId=sample['native']['sessionId'],navigation=1)],actualAndroidExecution=True,actualGeckoExecution=True,productionChatSession=True,syntheticGeoService=True,actualPublicIpGeolocationVerified=False,workerCoverageVerified=False,serviceWorkerCoverageVerified=False,fingerprintProtectionVerified=False)
    host=copy.deepcopy(previous['routeReceipts']);host['events']=host['events'][:2];marker=copy.deepcopy(host['events'][1]);marker.update(sequence=3,path='/worker-probe',documentId=page['documentId'],realm='document',phase='gecko-new-york');host['events'].append(marker)
    process_sample=dict(schema=1,sourceCommit=SOURCE,sourceTree=TREE,runNonce=NONCE,slot=6,processName=gate.PROCESS,expectedPid=7711,observedPid='7711',shellUid=2000)
    report=dict(schema=1,fixtureType=gate.FIXTURE_TYPE,status='passed',sourceCommit=SOURCE,sourceTree=TREE,runNonce=NONCE,expectedBuildIdentity=copy.deepcopy(expected),activity=activity,prelaunchSetup=before,routeReceipts=host,processSample=process_sample,hostTls=copy.deepcopy(previous['hostTls']),systemTimeZone=dict(before='UTC',after='UTC'),sourceFiles={name:modeled.SOURCE_SHA for name in gate.SOURCE_INPUTS},executionInputsUnchanged=True,cleanup=dict(appStopped=True,scopeCleared=True,reverseRemoved=True,caRemoved=True,privateMaterialRemoved=True,serverQuiesced=True),actualAndroidExecution=True,actualGeckoExecution=True,syntheticGeoService=True,actualPublicIpGeolocationVerified=False,workerCoverageVerified=False,serviceWorkerCoverageVerified=False,fingerprintProtectionVerified=False)
    return report,expected


def values(report):
    activity=report['activity'];binding=report['routeReceipts']['binding']
    payload={'route-receipts.json':report['routeReceipts'],'setup-scope.json':dict(beforeLaunch=report['prelaunchSetup'],afterLoad=activity['setup'],cpuSetup=activity['cpuSetup'],cpuStoredState=activity['cpuStoredState']),'process-sample.json':report['processSample']}
    return {'combo.json':copy.deepcopy(activity),**{name:dict(schema=1,case=name[:-5],binding=copy.deepcopy(binding),evidence=copy.deepcopy(value)) for name,value in payload.items()}}

def validate(report,expected=None,module=gate):return module.validate_behavior(report,SOURCE,expected or fixture()[1],values(report),modeled.source_reader)

def write(directory,report):
    rawdir=directory/gate.RAW_DIRECTORY;rawdir.mkdir();pins={}
    for name,value in values(report).items():
        # Deliberate visible whitespace proves original device bytes survive.
        raw=(json.dumps(value,indent=1)+'\n').encode();(rawdir/name).write_bytes(raw);pins[name]=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
    report['casePins']=pins;report['deviceReportReceivedSha256']=pins['combo.json']['sha256'];(directory/gate.REPORT_NAME).write_text(json.dumps(report))


class ComboEvidenceTests(unittest.TestCase):
    def reject(self,changes):
        for index,change in enumerate(changes):
            report,expected=fixture();change(report)
            with self.subTest(index=index),self.assertRaises((ValueError,KeyError,TypeError)):validate(report,expected)
    def test_same_document_native_getters_and_readbacks_bind_all_layers(self):
        report,expected=fixture();original=copy.deepcopy(report);result=validate(report,expected);self.assertEqual(report,original);self.assertEqual(result['caseCount'],1);self.assertEqual(result['checkCount'],8);self.assertEqual(result['pageHardwareConcurrency'],1);self.assertEqual(result['pageTimeZone'],'America/New_York');self.assertFalse(result['workerCoverageVerified']);self.assertFalse(result['actualPublicIpGeolocationVerified'])
    def test_pref_success_cannot_substitute_for_first_inline_cpu_or_time_zone(self):
        self.reject([lambda r:r['activity']['page'].update(hardwareConcurrency=2),lambda r:r['activity']['page'].update(hardwareConcurrency=True),lambda r:r['activity']['page'].update(nativeGetter=False),lambda r:r['activity']['page'].update(firstInline=False),lambda r:r['activity']['page'].update(nativeTimeZone=modeled.old.raw_clock('UTC')),lambda r:r['activity']['page']['nativeTimeZone']['july'].update(offsetMinutes=300),lambda r:r['activity']['page'].update(origin='https://fp-b.pocketchat.test'),lambda r:r['activity']['page'].update(documentId='f'*36),lambda r:r['activity']['page'].update(markerComplete=False)])
    def test_current_native_ack_context_rev_and_environment_still_strict(self):
        self.reject([lambda r:r['activity']['native'].update(contextId='999'),lambda r:r['activity']['native']['freshReadback'].update(contextId='999'),lambda r:r['activity']['native']['receipt']['binding'].update(sessionEpoch='old'),lambda r:r['activity']['native']['receipt'].update(desiredRevision=2),lambda r:r['activity']['native']['status'].update(nativeSettingReadback=False),lambda r:r['activity']['native']['status'].update(ipMatched=False),lambda r:r['activity']['native'].update(privacyLevel=2,nativeRfpConfirmed=True),lambda r:r['activity']['native']['receipt']['ipObservation'].update(ip='1.1.1.1'),lambda r:r['activity']['native']['identity'].update(generation=2)])
    def test_cpu_boot_runtime_actual_sdk_read_and_durable_store_are_separate(self):
        self.reject([lambda r:r['activity']['cpuPolicy'].update(desiredRevision=3),lambda r:r['activity']['cpuPolicy'].update(activeBootMode='2'),lambda r:r['activity']['runtimeCpuPolicy'].update(runtimeNonce='1'*32),lambda r:r['activity']['cpuPolicy'].update(configuredCap=True),lambda r:r['activity']['freshCpuReadback'].update(defaultCap=2),lambda r:r['activity']['freshCpuReadback'].update(hasUserValue=True),lambda r:r['activity']['cpuStoredState'].update(revision=3),lambda r:r['activity']['cpuStoredState']['identity'].update(generation=2),lambda r:r['activity']['cpuStoredState']['spec'].update(mode='2'),lambda r:r['activity']['cpuSetup'].update(sessionAbsentBeforeSetup=False),lambda r:r['activity']['cpuSetup'].update(cpuSealedRecordMissingBefore=False)])
    def test_shell_pid_and_profile_process_cannot_be_mixed(self):
        self.reject([lambda r:r['processSample'].update(observedPid='7711 7712'),lambda r:r['processSample'].update(expectedPid=7712),lambda r:r['processSample'].update(shellUid=0),lambda r:r['processSample'].update(slot=5),lambda r:r['activity']['process'].update(name='local.pocketchat.test:profile1'),lambda r:r['activity']['process'].update(uid=2000),lambda r:r['activity']['cpuPolicy'].update(pid=7712)])
    def test_provider_allocator_scope_is_original_and_fresh_before_main(self):
        self.reject([lambda r:r['activity'].update(scopeAllocationActivity=gate.ACTIVITY),lambda r:r['activity'].update(activityClass=gate.SCOPE_ACTIVITY),lambda r:r['prelaunchSetup'].update(actualDefaultStoreLoadYet=True),lambda r:r['prelaunchSetup'].update(manualSeedAppliedToIpScope=True),lambda r:r['prelaunchSetup'].update(unusedSlotBeforeSetup=False),lambda r:r['prelaunchSetup'].update(actualProfilesPrepare=False),lambda r:r['activity']['setup']['defaultSpec'].update(mode='system'),lambda r:r['activity']['setup'].update(defaultRevision=2)])
    def test_independent_geo_marker_route_tls_sequence_and_upstream_are_required(self):
        self.reject([lambda r:r['routeReceipts'].update(upstreamConnections=1),lambda r:r['routeReceipts']['events'][0].update(credentialsPresent=True),lambda r:r['routeReceipts']['events'][0].update(protocol='http-connect'),lambda r:r['routeReceipts']['events'][0].update(targetSni='fp-a.pocketchat.test'),lambda r:r['routeReceipts']['events'][0].update(responseWritten=False),lambda r:r['routeReceipts']['events'][0].update(behavior='redirect',status=302),lambda r:r['routeReceipts']['events'][2].update(documentId='00000000-0000-0000-0000-000000000999'),lambda r:r['routeReceipts']['events'][1].update(host='fp-b.pocketchat.test',targetSni='fp-b.pocketchat.test'),lambda r:r['routeReceipts']['events'][1].update(phase='gecko-system'),lambda r:r['routeReceipts']['events'][2].update(host='fp-b.pocketchat.test',targetSni='fp-b.pocketchat.test'),lambda r:r['routeReceipts']['events'][2].update(sequence=4),lambda r:r['routeReceipts']['events'].pop(),lambda r:r['activity']['tls'].update(isException=True),lambda r:r['hostTls']['trustInstallation'].update(removedAfterExecution=False),lambda r:r['routeReceipts'].update(closed=False)])
    def test_an_extra_marker_cannot_be_ignored_as_an_unrelated_document(self):
        report,expected=fixture();row=copy.deepcopy(report['routeReceipts']['events'][-1]);row.update(sequence=4,documentId='00000000-0000-0000-0000-000000000999');report['routeReceipts']['events'].append(row)
        with self.assertRaisesRegex(ValueError,'independent same-document wire marker'):validate(report,expected)
    def test_content_log_completion_can_follow_the_same_document_marker(self):
        report,expected=fixture();events=report['routeReceipts']['events'];events[1],events[2]=events[2],events[1]
        for sequence,event in enumerate(events,1):event['sequence']=sequence
        self.assertTrue(validate(report,expected)['productionColdCpuDefaultIpCombinationPassed'])
        # Moving geo admission after a content record still violates the native
        # query-first gate, unlike concurrent completion-log arrival ordering.
        events[0],events[1]=events[1],events[0]
        for sequence,event in enumerate(events,1):event['sequence']=sequence
        with self.assertRaises(ValueError):validate(report,expected)
    def test_source_apk_sdk_attempt_and_no_coverage_overclaim(self):
        self.reject([lambda r:r['activity']['buildIdentity'].update(apkSha256='f'*64),lambda r:r['activity']['buildIdentity']['sdkBuildIdentity'].update(runAttempt='2'),lambda r:r.update(runNonce='f'*32),lambda r:r.update(sourceCommit='f'*40),lambda r:r['sourceFiles'].update({next(iter(gate.SOURCE_INPUTS)):'f'*64}),lambda r:r['sourceFiles'].pop(next(iter(gate.SOURCE_INPUTS))),lambda r:r.update(workerCoverageVerified=True),lambda r:r.update(actualPublicIpGeolocationVerified=True),lambda r:r['activity']['checks'].pop(),lambda r:r['activity']['checks'][0].update(**{'pass':False}),lambda r:r['activity']['nativeEvents'][0].update(sessionId='foreign'),lambda r:r['activity']['nativeEvents'][1].update(kind='page-stop-false'),lambda r:r['cleanup'].update(caRemoved=False)])
    def test_original_raw_bytes_and_safe_fixed_sets_are_bound_without_normalizing(self):
        report,expected=fixture()
        with tempfile.TemporaryDirectory() as name:
            d=Path(name);write(d,report);result=gate.verify_gecko_cpu_ip_combo_evidence(d,SOURCE,expected,modeled.source_reader);self.assertEqual(result['caseCount'],1)
            raw=d/gate.RAW_DIRECTORY/'combo.json';original=raw.read_bytes();raw.write_bytes(json.dumps(json.loads(original)).encode())
            with self.assertRaisesRegex(ValueError,'original raw file bytes/SHA'):gate.verify_gecko_cpu_ip_combo_evidence(d,SOURCE,expected,modeled.source_reader)
        for kind in ('missing','extra','symlink','duplicate','nonfinite','oversize'):
            with self.subTest(kind=kind),tempfile.TemporaryDirectory() as name:
                d=Path(name);write(d,copy.deepcopy(report));path=d/gate.RAW_DIRECTORY/'process-sample.json'
                if kind=='missing':path.unlink()
                if kind=='extra':(path.parent/'extra.json').write_text('{}')
                if kind=='symlink':path.unlink();path.symlink_to(d/gate.REPORT_NAME)
                if kind=='duplicate':path.write_bytes(b'{"x":1,"x":2}')
                if kind=='nonfinite':path.write_bytes(b'{"x":NaN}')
                if kind=='oversize':path.write_bytes(b' '*262145)
                with self.assertRaises((ValueError,OSError)):gate.verify_gecko_cpu_ip_combo_evidence(d,SOURCE,expected,modeled.source_reader)
    def test_semantic_guard_mutants_accept_exact_counterfeits_only_after_real_guards_removed(self):
        original=Path(gate.__file__).read_text()
        scenarios=[("page['hardwareConcurrency']==1","True",lambda r:r['activity']['page'].update(hardwareConcurrency=2)),("ip.clock(page['nativeTimeZone'],'America/New_York');","",lambda r:r['activity']['page'].update(nativeTimeZone=modeled.old.raw_clock('UTC'))),("ip.native(native,'ip','America/New_York',engine);","",lambda r:r['activity']['native'].update(contextId='999')),("equal(stored['identity'],identity,'durable CPU owner differs');","",lambda r:r['activity']['cpuStoredState']['identity'].update(generation=2))]
        for before,after,change in scenarios:
            with self.subTest(guard=before):
                report,expected=fixture();validate(report,expected);change(report)
                with self.assertRaises(ValueError):validate(report,expected)
                self.assertEqual(original.count(before),1);module=types.ModuleType('compiled_combo_mutant');module.__file__=gate.__file__;exec(compile(original.replace(before,after,1),'<compiled-semantic-mutant>','exec'),module.__dict__);self.assertTrue(validate(report,expected,module)['productionColdCpuDefaultIpCombinationPassed'])

if __name__=='__main__':unittest.main()
