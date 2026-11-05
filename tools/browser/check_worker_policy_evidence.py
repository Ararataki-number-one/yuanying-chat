#!/usr/bin/env python3
"""Validate source-bound real Android Worker policy evidence, without whole-Worker claims."""
import argparse
import hashlib
import json
from pathlib import Path,PurePosixPath
import re
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from gecko.profile_invocation_contract import verify_installed
from gecko.sdk_identity_contract import source_bytes,strict_json,_typed_equal,SDK_FIELDS

ORIGINS={'https://fp-a.pocketchat.test','https://fp-b.pocketchat.test'}
PHASES=('allow','restrict','restrict-route','restore')
CASE_REALMS={'dedicated':'dedicated-classic','module':'dedicated-module','blob':'dedicated-blob','shared':'shared-worker','sharedBlob':'shared-blob'}
SCRIPT_PATHS={'dedicated':'/dedicated.js','module':'/module.js','shared':'/shared.js'}
REQUIRED={'chromium.production-ui','default.allow-policy','stale.actual-js-dispatched','restrict.save-revision-rebuild','stale.policy-token-rejected','stale.actual-js-callback-rejected','stale.receipt-rejected','restrict.current-page-selftest','route.actual-new-ticket','restore.save-revision-rebuild','coverage.honest-boundaries'}
for phase in PHASES:REQUIRED.update(phase+'.'+suffix for suffix in ('first-inline','actual-workers','frames-first-inline','native-tls','native-switch','service-existing-cache','service-network','service-registration'))
SOURCE_INPUTS={'tools/browser/check_worker_policy_evidence.py','tools/browser/run_worker_policy_integration.py','tools/browser/newworker_fixture_server.py','tools/browser/fingerprint_fixture_server.py','tests/gecko/WorkerPolicyIntegrationActivity.java','tests/gecko/WorkerPolicyEvidenceProvider.java','tests/gecko/BrowserFingerprintFixture.java','tests/gecko/BrowserFingerprintIntegrationActivity.java','tests/gecko/IntegrationBuildIdentity.java','tests/gecko/assets/worker-policy-page.js','tests/gecko/AndroidManifest.xml','tests/gecko/res/xml/network_security.xml','app/build.gradle','app/src/main/AndroidManifest.xml','app/src/main/res/xml/network_security.xml','.github/workflows/browser-2_1-acceptance.yml','app/src/main/java/local/pocketchat/NormalCaretSdkReceipt.java','app/src/main/java/local/pocketchat/BrowserActivity.java','app/src/main/java/local/pocketchat/ChromiumRuntime.java','app/src/main/java/local/pocketchat/ChromiumFingerprintSpec.java','app/src/main/java/local/pocketchat/ChromiumFingerprintRuntime.java','app/src/main/java/local/pocketchat/ChromiumFingerprintStore.java','app/src/main/java/local/pocketchat/ChromiumFingerprintUi.java','app/src/main/java/local/pocketchat/PocketApplication.java','app/src/main/assets/chromium-fingerprint.js'}


def require(value,message):
    if not value:raise ValueError('Android Worker policy acceptance: '+message)

def no_full_claim(value):
    require(all(value.get(key) is False for key in ('fingerprintProtectionVerified','workerCoverageVerified','serviceWorkerCoverageVerified','existingExecutionControlled')),'whole Worker protection/execution control must not be claimed')

def native(value,restrict,revision):
    require(type(value) is dict and value.get('scope')=='service-worker-network-only' and value.get('mode')==('restrict' if restrict else 'allow'),'native Worker setting scope/mode differs')
    require(all(value.get(key) is True for key in ('confirmed','identityBound','routeAdmitted','nativeReadbackObserved','nativeSettingMatches')),'native Worker setting confirmation missing')
    require(type(value.get('desiredRevision')) is int and value['desiredRevision']==revision and value.get('nativeBlockNetworkLoads') is restrict,'actual native setting/revision differs')
    require(value.get('workerCoverageVerified') is False and value.get('existingOrCachedExecutionControlled') is False,'native setting must not claim existing Worker termination')

def observation(value,restrict,shared):
    require(type(value) is dict and value.get('scope')=='page-frame-new-workers-only' and value.get('mode')==('restrict' if restrict else 'allow') and value.get('state')==('page-observed' if restrict else 'not-requested'),'current document Worker guard observation differs')
    require(value.get('existingExecutionControlled') is False,'existing Worker execution falsely claimed')
    require(value.get('dedicatedAvailable') is True and value.get('sharedAvailable') is shared and value.get('serviceRegistrationAvailable') is True,'actual Worker capability observation differs')
    for key,expected in [('dedicatedCreationDenied',restrict),('sharedCreationDenied',restrict and shared),('serviceRegistrationGuardInstalled',restrict),('serviceRegistrationDenied',restrict)]:require(value.get(key) is expected,'actual page guard outcome missing: '+key)

def host_trust(report,result):
    host=report.get('hostTls');require(type(host) is dict,'ephemeral host TLS receipt missing')
    require(host.get('ephemeral') is True and host.get('privateMaterialLocation')=='host-tmp-only' and host.get('privateMaterialExported') is False and host.get('privateMaterialRemoved') is True,'TLS private material must stay ephemeral host /tmp only')
    require(host.get('opensslChainVerified') is True and host.get('hostnameVerified')==['fp-a.pocketchat.test','fp-b.pocketchat.test'] and host.get('certificateExceptionUsed') is False,'native-valid exact-host chain required')
    require(host.get('guestPort')==18765 and host.get('reverseRemoved') is True,'controlled reverse mapping/cleanup missing')
    for key in ('caPemSha256','leafDerSha256'):require(type(host.get(key)) is str and re.fullmatch('[0-9a-f]{64}',host[key]),'public trust hash invalid')
    identity=report.get('expectedBuildIdentity',{});sdk=identity.get('sdkBuildIdentity',{})
    binding=dict(sourceCommit=report.get('sourceCommit'),sourceTree=report.get('sourceTree'),runNonce=report.get('runNonce'),integrationApkSha256=identity.get('apkSha256'),sdkRunId=sdk.get('runId'),sdkRunAttempt=sdk.get('runAttempt'))
    require(_typed_equal(host.get('binding'),binding),'host source/tree/APK/run/nonce binding differs')
    installation=host.get('trustInstallation',{});subject=host.get('subjectHashOld')
    require(type(subject) is str and re.fullmatch('[0-9a-f]{8}',subject),'public CA subject hash invalid')
    require(installation.get('method')=='domain-scoped-user-ca' and type(installation.get('androidUser')) is int and installation['androidUser']==0,'exact two-domain user CA method required')
    require(all(installation.get(key) is True for key in ('adbRoot','selinuxEnforcing','installedPublicCaBytesMatch','appForceStoppedAfterInstall','removedAfterExecution','shellRestoredAfterInstall','shellRestoredAfterCleanup')),'public CA actual installation/readback/cleanup missing')
    for key,expected in [('evidenceShellUid',2000),('cleanupRootUid',0),('cleanupShellUid',2000)]:require(type(installation.get(key)) is int and installation[key]==expected,'root/shell UID lifecycle differs')
    require(installation.get('ownerAndMode')=='644:1000:1000' and type(installation.get('selinuxContext')) is str and re.fullmatch(r'u:object_r:(?!unlabeled)[a-zA-Z0-9_]+:s0',installation['selinuxContext']),'public CA owner/mode/SELinux proof missing')
    require(installation.get('subjectHashOld')==subject and installation.get('storePath')=='/data/misc/user/0/cacerts-added/'+subject+'.0' and installation.get('publicCaPemSha256')==host['caPemSha256'] and installation.get('expectedLeafDerSha256')==host['leafDerSha256'],'public CA PEM/native leaf DER hash differs')
    fixture=result.get('fixture',{})
    require(type(fixture) is dict and fixture.get('engine')=='chromium' and _typed_equal(fixture.get('binding'),binding),'fresh engine host binding missing')
    require(fixture.get('caPemSha256')==host['caPemSha256'] and fixture.get('leafDerSha256')==host['leafDerSha256'] and fixture.get('trustMethod')=='domain-scoped-user-ca','engine native trust differs')
    require(type(fixture.get('upstreamConnections')) is int and fixture['upstreamConnections']==0 and fixture.get('forwardingImplemented') is False and fixture.get('certificateExceptionUsed') is False,'fixture must not forward external traffic or bypass TLS')
    require(type(fixture.get('tlsConnections')) is int and fixture['tlsConnections']>0,'actual native TLS connections missing')
    requests=fixture.get('requests');require(type(requests) is list and 0<len(requests)<=200 and type(fixture.get('accepted')) is int and fixture['accepted']==len(requests),'bounded actual server requests missing')
    paths={'/worker-document','/worker-frame','/dedicated.js','/module.js','/shared.js','/service.js','/worker-probe','/sw-cached'}
    for row in requests:
        require(type(row) is dict and row.get('origin') in ORIGINS and row.get('method')=='GET' and row.get('tls') is True and row.get('phase') in PHASES and row.get('path') in paths,'request escapes actual HTTPS Worker fixture')
        require(set(row)<= {'origin','method','tls','phase','path','realm','documentId','user-agent','sec-ch-ua','sec-ch-ua-mobile','sec-ch-ua-platform','sec-ch-ua-platform-version','sec-ch-ua-model','sec-ch-ua-arch','sec-ch-ua-bitness','sec-ch-ua-full-version-list'},'non-allowlisted HTTP metadata exported')
        require(type(row.get('user-agent')) is str and 0<len(row['user-agent'])<=512,'actual server UA missing')
    return host,requests

def validate_behavior(report,source,reader=source_bytes):
    require(type(report) is dict and type(report.get('schema')) is int and report['schema']==1 and report.get('status')=='passed' and report.get('sourceCommit')==source,'successful exact-source Worker report required')
    require(type(report.get('sourceTree')) is str and re.fullmatch('[0-9a-f]{40}',report['sourceTree']) and type(report.get('runNonce')) is str and re.fullmatch('[0-9a-f]{32}',report['runNonce']),'source tree/fresh invocation missing')
    require(report.get('executionInputsUnchanged') is True,'execution inputs changed')
    require(all(report.get(key) is True for key in ('actualAndroidExecution','actualAndroidWebViewExecution','actualNativeServiceWorkerSettingExecution')),'actual Android/native Service Worker setting execution required')
    require(all(report.get(key) is False for key in ('actualGeckoExecution','actualDesktopChromiumExecution','actualPublicWebsiteExecution','actualDevicePerformanceMeasurement')),'execution scope differs');no_full_claim(report)
    results=report.get('results');require(type(results) is dict and set(results)=={'chromium'},'current Chromium actual engine result required');result=results['chromium']
    require(type(result) is dict and result.get('status')=='passed' and result.get('phase')=='complete' and not result.get('failure') and result.get('engine')=='chromium' and result.get('sourceCommit')==source and result.get('runNonce')==report['runNonce'],'engine result incomplete/stale')
    require(result.get('actualAndroidExecution') is True and result.get('actualAndroidWebViewExecution') is True and result.get('actualGeckoExecution') is False and result.get('actualPublicWebsiteExecution') is False,'engine execution scope differs');no_full_claim(result)
    checks=result.get('checks');require(type(checks) is list and all(type(c) is dict and c.get('pass') is True and type(c.get('id')) is str for c in checks),'check failed/malformed')
    names=[c['id'] for c in checks];require(len(names)==len(set(names)) and REQUIRED<=set(names),'required checks missing/duplicated')
    host,requests=host_trust(report,result)
    samples=result.get('samples');setups=result.get('nativeSetups');require(type(samples) is list and len(samples)==4 and [s.get('phase') for s in samples]==list(PHASES) and type(setups) is list and len(setups)==4 and [s.get('phase') for s in setups]==list(PHASES),'four actual policy/route phases missing')
    documents=set();revisions=[];environment=None
    def matches(phase,realm,path,document=None,ua=None):return [r for r in requests if r['phase']==phase and r['realm']==realm and r['path']==path and (document is None or r['documentId']==document) and (ua is None or r['user-agent']==ua)]
    for sample,setup,phase in zip(samples,setups,PHASES):
        restrict=phase in ('restrict','restrict-route');revision=sample.get('desiredRevision');require(type(revision) is int and revision>0,'desired policy revision missing');revisions.append(revision)
        owner=sample.get('environmentIdentity');require(type(owner) is dict and set(owner)=={'slot','generation','environmentId'} and type(owner['slot']) is int and owner['slot']==0 and type(owner['generation']) is int and owner['generation']>=0 and type(owner['environmentId']) is str and re.fullmatch('[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',owner['environmentId']),'actual environment identity missing')
        if environment is None:environment=owner
        require(_typed_equal(owner,environment),'environment owner/generation changed during policy proof')
        native(sample.get('nativeWorkerPolicy'),restrict,revision);native(setup.get('workerNetwork'),restrict,revision)
        require(setup.get('observedLeafDerSha256')==host['leafDerSha256'] and setup.get('desiredRevision')==revision,'actual native peer leaf/revision differs')
        require(setup.get('documentStartRegistered') is True and setup.get('features',{}).get('documentStart') is True and int(str(setup.get('chromiumVersion','0')).split('.')[0])>=124,'actual provider/document-start support required')
        require(setup.get('requested',{}).get('workers')==('restrict' if restrict else 'allow') and setup.get('workerCoverageVerified') is False and setup.get('fingerprintProtectionVerified') is False,'native requested policy or coverage differs')
        page=sample.get('page');require(type(page) is dict and page.get('phase')==phase and page.get('mode')==('restrict' if restrict else 'allow') and page.get('firstInline') is True and page.get('complete') is True and page.get('secure') is True and page.get('documentGuard') is True and page.get('frame') is False and not page.get('error') and page.get('runNonce')==report['runNonce'] and page.get('sourceCommit')==source,'actual first-inline page observation missing')
        require(page.get('workerCoverageVerified') is False and page.get('existingExecutionControlled') is False,'page overclaims Worker scope')
        document=page.get('documentId');require(type(document) is str and re.fullmatch('[0-9a-f-]{36}',document) and document not in documents,'fresh document identity required');documents.add(document)
        require(page.get('origin')=='https://fp-a.pocketchat.test' and page.get('nativeUserAgent')==setup.get('nativeUserAgent') and matches(phase,'document','/worker-probe',document,page['nativeUserAgent']),'server/native/current-document UA binding missing')
        cases=page.get('cases');require(type(cases) is dict and set(cases)==set(CASE_REALMS),'all Worker creation variants required')
        for name,realm in CASE_REALMS.items():
            row=cases[name];available=row.get('available');require(type(available) is bool and (available or name.startswith('shared')),'Dedicated/module/blob actual capability required')
            if not available:
                require(all(row.get(key) is False for key in ('created','executed','denied','networkAllowed')),'unavailable API cannot be marked denied/protected');continue
            require(row.get('denied') is restrict and row.get('created') is (not restrict) and row.get('executed') is (not restrict) and row.get('networkAllowed') is (not restrict),'actual Worker create/execute/network outcome differs: '+name)
            if not restrict:
                require(row.get('documentGuard') is False and row.get('auditAvailable') is False and type(row.get('nativeUserAgent')) is str,'Worker fingerprint scope must remain explicitly unprotected')
                require(matches(phase,realm,'/worker-probe',document,row['nativeUserAgent']),'actual Worker fetch UA not observed at HTTPS host')
                if name in SCRIPT_PATHS:require(matches(phase,realm,SCRIPT_PATHS[name],document),'actual Worker script never requested')
        shared=cases['shared']['available'];require(cases['sharedBlob']['available'] is shared,'SharedWorker capability inconsistency');observation(page.get('observation'),restrict,shared)
        sw=page.get('serviceWorker');require(type(sw) is dict and sw.get('available') is True and sw.get('registered') is (not restrict) and sw.get('registrationDenied') is restrict and sw.get('existingExecution') is True and sw.get('cacheRead') is True and sw.get('networkAllowed') is (not restrict) and sw.get('workerFingerprintProtected') is False,'actual existing Service Worker cache/network boundary differs')
        if not restrict:
            require(matches(phase,'service-worker','/service.js',document) and matches(phase,'service-worker-install','/sw-cached',document) and matches(phase,'service-worker-fetch','/worker-probe',document,sw.get('nativeUserAgent')),'actual Service Worker registration/cache/network requests missing')
        frames=sample.get('frames');require(type(frames) is list and len(frames)==2 and {f.get('origin') for f in frames}==ORIGINS,'same/cross-origin early frames required')
        for frame in frames:
            require(frame.get('phase')==phase and frame.get('mode')==page['mode'] and frame.get('firstInline') is True and frame.get('complete') is True and frame.get('secure') is True and frame.get('documentGuard') is True and frame.get('frame') is True and frame.get('runNonce')==report['runNonce'] and frame.get('sourceCommit')==source and not frame.get('error'),'frame first script did not see current policy')
            case=frame.get('cases',{}).get('dedicated',{});require(case.get('available') is True and case.get('created') is (not restrict) and case.get('executed') is (not restrict) and case.get('denied') is restrict and case.get('networkAllowed') is (not restrict),'frame actual Worker guard outcome differs')
            frame_id=frame.get('documentId');require(type(frame_id) is str and re.fullmatch('[0-9a-f-]{36}',frame_id) and frame_id not in documents,'fresh frame document identity missing');documents.add(frame_id)
            require(any(row.get('origin')==frame['origin'] for row in matches(phase,'document','/worker-probe',frame_id,frame.get('nativeUserAgent'))),'actual early frame document marker absent at HTTPS host')
            if not restrict:require(matches(phase,'frame-dedicated','/dedicated.js',frame.get('documentId')) and matches(phase,'frame-dedicated','/worker-probe',frame.get('documentId'),case.get('nativeUserAgent')),'frame actual Worker script/fetch not observed')
        if restrict:
            require(not any(r['phase']==phase and (r['path'] in ('/dedicated.js','/module.js','/shared.js','/service.js','/sw-cached') or r['realm'] not in ('document','frame')) for r in requests),'restricted Worker traffic reached HTTPS host')
    require(revisions==[revisions[0],revisions[0]+1,revisions[0]+1,revisions[0]+2],'actual saved revisions/route retention differ')
    stale=result.get('staleCallbackProof',{});require(all(stale.get(k) is True for k in ('actualJavaScriptResult','bindingRejected','receiptUnchanged','nativeRemainedBlocked')) and type(stale.get('callbacks')) is int and stale['callbacks']==1,'actual stale JavaScript callback rejection missing')
    route=result.get('routeReadmissionProof',{});require(all(route.get(k) is True for k in ('actualRouteRefresh','newTicketIdentity','newNativeSurface','samePolicyRevision')),'fresh production route readmission proof missing');native(route.get('nativeWorkerPolicy'),True,revisions[1])
    receipt=result.get('currentRestrictReceipt',{});require(receipt.get('desiredRevision')==revisions[1] and receipt.get('fingerprintProtectionVerified') is False,'current policy receipt missing')
    require(_typed_equal(receipt.get('identity'),environment),'current page receipt belongs to a different environment')
    binding=samples[1].get('binding');require(type(binding) is dict and set(binding)=={'providerPackage','providerVersion','runtimeEpoch','surfaceGeneration','navigationGeneration'},'actual current document binding missing')
    for key in binding:require(_typed_equal(receipt.get(key),binding[key]),'current page receipt provider/runtime/surface/navigation binding differs')
    row=receipt.get('fields',{}).get('workerCreation',{});require(row.get('state')=='page-observed' and row.get('value',{}).get('mode')=='restrict','actual current document receipt missing');observation(row['value'],True,samples[1]['page']['cases']['shared']['available'])
    hashes=report.get('sourceFiles');require(type(hashes) is dict and SOURCE_INPUTS<=set(hashes),'required source/resource hashes missing')
    for path,sha in hashes.items():
        require(type(path) is str and str(PurePosixPath(path))==path and not PurePosixPath(path).is_absolute() and '..' not in PurePosixPath(path).parts and '\\' not in path and '\x00' not in path and type(sha) is str and re.fullmatch('[0-9a-f]{64}',sha),'unsafe source hash record')
        require(hashlib.sha256(reader(source,path)).hexdigest()==sha,'selected-source bytes differ: '+path)
    return result

def verify_worker_policy_evidence(directory,source,expected,reader=source_bytes):
    raw=(Path(directory)/'worker-policy-results.json').read_bytes();require(0<len(raw)<=2*1024*1024,'bounded Worker report required');report=strict_json(raw);result=validate_behavior(report,source,reader)
    require(expected.get('sourceCommit')==source and expected.get('sourceTree')==report.get('sourceTree'),'reference source/tree differs')
    for installed in (report.get('expectedBuildIdentity',{}),result.get('buildIdentity',{})):
        require(type(installed) is dict,'actual installed identity missing')
        for key in ('schema','package','sourceCommit','sourceTree','dirtySource','version','versionCode','sdkCoordinate','apkSha256','apkBytes','buildStampSha256','sdkBuildIdentity')+SDK_FIELDS:require(_typed_equal(installed.get(key),expected.get(key)),'typed source/APK/SDK identity differs: '+key)
        verify_installed(installed,expected)
    sdk=expected['sdkBuildIdentity'];return dict(sourceCommit=source,sourceTree=expected['sourceTree'],integrationApkSha256=expected['apkSha256'],runId=sdk['runId'],runAttempt=sdk['runAttempt'],reportSha256=hashlib.sha256(raw).hexdigest(),actualAndroidExecution=True,actualAndroidWebViewExecution=True,actualNativeServiceWorkerSettingExecution=True,checkCount=len(result['checks']),fingerprintProtectionVerified=False,workerCoverageVerified=False,existingExecutionControlled=False,scope='Actual page/frame new Worker creation restriction, native ServiceWorker subsequent network block/readback and actual HTTPS request absence through policy save and route readmission; allow restoration and existing cache execution. No Worker realm spoofing, full Worker termination or in-flight cancellation claim.')

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--directory',required=True,type=Path);p.add_argument('--source',required=True);p.add_argument('--reference',required=True,type=Path);p.add_argument('--output',type=Path);a=p.parse_args();expected=json.loads(a.reference.read_text())['eventTransport']['buildIdentity'];result=verify_worker_policy_evidence(a.directory,a.source,expected)
    if a.output:a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))

if __name__=='__main__':main()
