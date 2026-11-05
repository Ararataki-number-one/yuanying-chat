"""Synthetic checker-schema controls; these reports do not attest Android execution."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/browser'))
import check_worker_policy_evidence as gate
import browser_fingerprint_evidence_test as historical_fingerprint_schema

class WorkerEvidenceTests(unittest.TestCase):
    def document(self,shared=True):
        previous=historical_fingerprint_schema.FingerprintEvidenceTests().document();source='a'*40;nonce='c'*32;identity=previous['expectedBuildIdentity'];sha=hashlib.sha256(b'controlled source').hexdigest();requests=[];samples=[];setups=[];next_id=0
        def document_id():
            nonlocal next_id;next_id+=1;return '00000000-0000-0000-0000-'+str(next_id).zfill(12)
        def request(phase,realm,path,document,origin='https://fp-a.pocketchat.test'):requests.append(dict(origin=origin,path=path,tls=True,method='GET',phase=phase,realm=realm,documentId=document,**{'user-agent':'synthetic-native-UA'}))
        def observation(restrict):return dict(scope='page-frame-new-workers-only',mode='restrict' if restrict else 'allow',state='page-observed' if restrict else 'not-requested',existingExecutionControlled=False,dedicatedAvailable=True,sharedAvailable=shared,serviceRegistrationAvailable=True,dedicatedCreationDenied=restrict,sharedCreationDenied=restrict and shared,serviceRegistrationGuardInstalled=restrict,serviceRegistrationDenied=restrict)
        def native(restrict,revision):return dict(scope='service-worker-network-only',mode='restrict' if restrict else 'allow',desiredRevision=revision,confirmed=True,identityBound=True,routeAdmitted=True,nativeReadbackObserved=True,nativeSettingMatches=True,nativeBlockNetworkLoads=restrict,workerCoverageVerified=False,existingOrCachedExecutionControlled=False)
        for index,phase in enumerate(gate.PHASES):
            restrict=phase in ('restrict','restrict-route');revision=[1,2,2,3][index];document=document_id();cases={}
            for name,realm in gate.CASE_REALMS.items():
                available=shared or not name.startswith('shared');row=dict(available=available,created=available and not restrict,executed=available and not restrict,denied=available and restrict,networkAllowed=available and not restrict)
                if available and not restrict:
                    row.update(documentGuard=False,auditAvailable=False,nativeUserAgent='synthetic-native-UA');request(phase,realm,'/worker-probe',document)
                    if name in gate.SCRIPT_PATHS:request(phase,realm,gate.SCRIPT_PATHS[name],document)
                cases[name]=row
            page=dict(schema=1,runNonce=nonce,sourceCommit=source,phase=phase,mode='restrict' if restrict else 'allow',firstInline=True,complete=True,secure=True,documentGuard=True,frame=False,documentId=document,origin='https://fp-a.pocketchat.test',nativeUserAgent='synthetic-native-UA',workerCoverageVerified=False,existingExecutionControlled=False,cases=cases,observation=observation(restrict),serviceWorker=dict(available=True,registered=not restrict,registrationDenied=restrict,existingExecution=True,cacheRead=True,networkAllowed=not restrict,nativeUserAgent='synthetic-native-UA',workerFingerprintProtected=False));request(phase,'document','/worker-probe',document)
            if not restrict:
                for realm,path in [('service-worker','/service.js'),('service-worker-install','/sw-cached'),('service-worker-fetch','/worker-probe')]:request(phase,realm,path,document)
            frames=[]
            for origin in sorted(gate.ORIGINS):
                frame_id=document_id();row=dict(available=True,created=not restrict,executed=not restrict,denied=restrict,networkAllowed=not restrict)
                if not restrict:
                    row.update(documentGuard=False,auditAvailable=False,nativeUserAgent='synthetic-native-UA');request(phase,'frame-dedicated','/dedicated.js',frame_id,origin);request(phase,'frame-dedicated','/worker-probe',frame_id,origin)
                frames.append(dict(schema=1,runNonce=nonce,sourceCommit=source,phase=phase,mode=page['mode'],firstInline=True,complete=True,secure=True,documentGuard=True,frame=True,documentId=frame_id,origin=origin,nativeUserAgent='synthetic-native-UA',cases=dict(dedicated=row)));request(phase,'document','/worker-probe',frame_id,origin)
            samples.append(dict(phase=phase,desiredRevision=revision,page=page,frames=frames,nativeWorkerPolicy=native(restrict,revision),environmentIdentity=dict(slot=0,generation=1,environmentId='00000000-0000-0000-0000-000000000001'),binding=dict(providerPackage='synthetic.provider',providerVersion='124',runtimeEpoch='synthetic-current-runtime',surfaceGeneration=index+1,navigationGeneration=index+1)))
            setups.append(dict(phase=phase,desiredRevision=revision,observedLeafDerSha256=sha,workerNetwork=native(restrict,revision),documentStartRegistered=True,features=dict(documentStart=True),chromiumVersion='124.0.6367.219',requested=dict(workers=page['mode']),nativeUserAgent='synthetic-native-UA',workerCoverageVerified=False,fingerprintProtectionVerified=False))
        fixture=copy.deepcopy(previous['results']['chromium']['fixture']);fixture.update(requests=requests,accepted=len(requests))
        result=dict(schema=1,engine='chromium',status='passed',phase='complete',failure='',sourceCommit=source,runNonce=nonce,buildIdentity=copy.deepcopy(identity),checks=[dict(id=name,**{'pass':True}) for name in sorted(gate.REQUIRED)],samples=samples,nativeSetups=setups,fixture=fixture,actualAndroidExecution=True,actualAndroidWebViewExecution=True,actualGeckoExecution=False,actualPublicWebsiteExecution=False,fingerprintProtectionVerified=False,workerCoverageVerified=False,serviceWorkerCoverageVerified=False,existingExecutionControlled=False,staleCallbackProof=dict(actualJavaScriptResult=True,bindingRejected=True,receiptUnchanged=True,nativeRemainedBlocked=True,callbacks=1),routeReadmissionProof=dict(actualRouteRefresh=True,newTicketIdentity=True,newNativeSurface=True,samePolicyRevision=True,nativeWorkerPolicy=native(True,2)),currentRestrictReceipt=dict(desiredRevision=2,fingerprintProtectionVerified=False,fields=dict(workerCreation=dict(state='page-observed',value=observation(True)))))
        report={key:copy.deepcopy(previous[key]) for key in ('hostTls','schema','status','sourceCommit','sourceTree','runNonce','expectedBuildIdentity','executionInputsUnchanged')}
        result['currentRestrictReceipt'].update(identity=copy.deepcopy(samples[1]['environmentIdentity']),**samples[1]['binding'])
        report.update(results=dict(chromium=result),actualAndroidExecution=True,actualAndroidWebViewExecution=True,actualNativeServiceWorkerSettingExecution=True,actualGeckoExecution=False,actualDesktopChromiumExecution=False,actualPublicWebsiteExecution=False,actualDevicePerformanceMeasurement=False,fingerprintProtectionVerified=False,workerCoverageVerified=False,serviceWorkerCoverageVerified=False,existingExecutionControlled=False,sourceFiles={path:sha for path in gate.SOURCE_INPUTS});return report
    def validate(self,value):return gate.validate_behavior(value,'a'*40,lambda source,path:b'controlled source')
    def test_complete_schema_with_and_without_native_shared_worker_api(self):
        for shared in (True,False):
            with self.subTest(shared=shared):self.assertEqual(len(self.validate(self.document(shared))['checks']),43)
    def test_full_checker_returns_only_source_bound_qualification_metadata(self):
        with tempfile.TemporaryDirectory() as folder:
            value=self.document();Path(folder,'worker-policy-results.json').write_text(json.dumps(value));result=gate.verify_worker_policy_evidence(folder,'a'*40,value['expectedBuildIdentity'],lambda source,path:b'controlled source')
            self.assertEqual(result['checkCount'],43);self.assertEqual(result['runId'],'123');self.assertFalse(result['workerCoverageVerified']);self.assertNotIn('seed',result)
    def test_current_receipt_owner_and_navigation_must_match_the_real_current_sample(self):
        for key,value in [('providerPackage','other.provider'),('runtimeEpoch','old-runtime'),('surfaceGeneration',1),('navigationGeneration',1)]:
            with self.subTest(key=key):
                report=self.document();report['results']['chromium']['currentRestrictReceipt'][key]=value
                with self.assertRaises(ValueError):self.validate(report)
        report=self.document();report['results']['chromium']['samples'][3]['environmentIdentity']['generation']=2
        with self.assertRaises(ValueError):self.validate(report)
    def test_reject_wrong_scope_identity_policy_outcome_or_traffic(self):
        changes=[lambda r:r.update(status='failed'),lambda r:r.update(schema=True),lambda r:r.update(sourceCommit='f'*40),lambda r:r.update(runNonce='old'),lambda r:r.update(executionInputsUnchanged=False),lambda r:r.update(actualAndroidExecution=False),lambda r:r.update(actualNativeServiceWorkerSettingExecution=False),lambda r:r.update(actualDesktopChromiumExecution=True),lambda r:r.update(workerCoverageVerified=True),lambda r:r.update(existingExecutionControlled=True),lambda r:r['results']['chromium']['checks'].pop(),lambda r:r['results']['chromium']['checks'].append(r['results']['chromium']['checks'][0]),lambda r:r['results']['chromium']['checks'][0].update({'pass':False}),lambda r:r['results']['chromium']['samples'].pop(),lambda r:r['results']['chromium']['nativeSetups'][0].update(observedLeafDerSha256='f'*64),lambda r:r['results']['chromium']['nativeSetups'][0].update(documentStartRegistered=False),lambda r:r['results']['chromium']['samples'][0]['page'].update(firstInline=False),lambda r:r['results']['chromium']['samples'][0]['page'].update(documentGuard=False),lambda r:r['results']['chromium']['samples'][1]['page']['cases']['module'].update(denied=False),lambda r:r['results']['chromium']['samples'][1]['page']['cases']['blob'].update(executed=True),lambda r:r['results']['chromium']['samples'][0]['page']['cases']['shared'].update(available=False),lambda r:r['results']['chromium']['samples'][0]['page']['cases']['blob'].update(documentGuard=True),lambda r:r['results']['chromium']['samples'][1]['page']['serviceWorker'].update(cacheRead=False),lambda r:r['results']['chromium']['samples'][1]['page']['serviceWorker'].update(networkAllowed=True),lambda r:r['results']['chromium']['samples'][3]['page']['serviceWorker'].update(networkAllowed=False),lambda r:r['results']['chromium']['samples'][1]['page']['observation'].update(dedicatedCreationDenied=False),lambda r:r['results']['chromium']['samples'][0]['page']['observation'].update(dedicatedAvailable=False),lambda r:r['results']['chromium']['samples'][2]['nativeWorkerPolicy'].update(nativeBlockNetworkLoads=False),lambda r:r['results']['chromium']['samples'][2]['nativeWorkerPolicy'].update(nativeReadbackObserved=False),lambda r:r['results']['chromium']['samples'][2]['nativeWorkerPolicy'].update(identityBound=False),lambda r:r['results']['chromium']['samples'][2].update(desiredRevision=3),lambda r:r['results']['chromium']['samples'][2]['page'].update(documentId=r['results']['chromium']['samples'][1]['page']['documentId']),lambda r:r['results']['chromium']['samples'][1]['frames'].pop(),lambda r:r['results']['chromium']['samples'][1]['frames'][1].update(documentGuard=False),lambda r:r['results']['chromium']['staleCallbackProof'].update(actualJavaScriptResult=False),lambda r:r['results']['chromium']['staleCallbackProof'].update(bindingRejected=False),lambda r:r['results']['chromium']['staleCallbackProof'].update(nativeRemainedBlocked=False),lambda r:r['results']['chromium']['routeReadmissionProof'].update(newTicketIdentity=False),lambda r:r['results']['chromium']['currentRestrictReceipt']['fields']['workerCreation'].update(state='requested'),lambda r:r['hostTls'].update(privateMaterialExported=True),lambda r:r['hostTls'].update(privateMaterialRemoved=False),lambda r:r['hostTls'].update(certificateExceptionUsed=True),lambda r:r['hostTls']['trustInstallation'].update(evidenceShellUid=0),lambda r:r['hostTls']['binding'].update(sdkRunAttempt=2),lambda r:r['results']['chromium']['fixture'].update(upstreamConnections=1),lambda r:r['results']['chromium']['fixture']['requests'][0].update(origin='https://outside.test'),lambda r:r['results']['chromium']['fixture']['requests'][0].update(tls=False),lambda r:r['results']['chromium']['fixture']['requests'][0].update({'authorization':'secret'}),lambda r:r['sourceFiles'].clear(),lambda r:r['sourceFiles'].update({'../escape':'f'*64})]
        for index,change in enumerate(changes):
            with self.subTest(index=index):
                value=self.document();change(value)
                with self.assertRaises(ValueError):self.validate(value)
    def test_a_single_restricted_worker_network_request_cannot_be_hidden_by_passing_ui_checks(self):
        for phase in ('restrict','restrict-route'):
            for realm,path in [('dedicated-classic','/dedicated.js'),('dedicated-blob','/worker-probe'),('service-worker','/service.js'),('service-worker-fetch','/worker-probe')]:
                with self.subTest(phase=phase,realm=realm):
                    value=self.document();fixture=value['results']['chromium']['fixture'];row=copy.deepcopy(fixture['requests'][0]);row.update(phase=phase,realm=realm,path=path);fixture['requests'].append(row);fixture['accepted']+=1
                    with self.assertRaises(ValueError):self.validate(value)
    def test_missing_positive_request_or_wrong_worker_ua_is_rejected(self):
        for path in ('/module.js','/service.js','/sw-cached'):
            value=self.document();fixture=value['results']['chromium']['fixture'];fixture['requests']=[r for r in fixture['requests'] if r['path']!=path];fixture['accepted']=len(fixture['requests'])
            with self.subTest(path=path),self.assertRaises(ValueError):self.validate(value)
        value=self.document();value['results']['chromium']['samples'][0]['page']['cases']['dedicated']['nativeUserAgent']='different-UA'
        with self.assertRaises(ValueError):self.validate(value)
    def test_report_missing_duplicate_json_and_typed_apk_run_binding_fail_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(FileNotFoundError):gate.verify_worker_policy_evidence(folder,'a'*40,{})
            for raw in [b'{"status":"passed","status":"passed"}',b'{"value":NaN}']:
                Path(folder,'worker-policy-results.json').write_bytes(raw)
                with self.assertRaises(ValueError):gate.verify_worker_policy_evidence(folder,'a'*40,{})
            for change in (lambda r:r['expectedBuildIdentity'].update(apkSha256='f'*64),lambda r:r['results']['chromium']['buildIdentity'].update(apkSha256='f'*64),lambda r:r['results']['chromium']['buildIdentity']['sdkBuildIdentity'].update(runAttempt=2)):
                report=self.document();expected=copy.deepcopy(report['expectedBuildIdentity']);change(report);Path(folder,'worker-policy-results.json').write_text(json.dumps(report))
                with self.assertRaises(ValueError):gate.verify_worker_policy_evidence(folder,'a'*40,expected,lambda source,path:b'controlled source')

if __name__=='__main__':unittest.main(verbosity=2)
