"""Synthetic validator adversarial controls; no Android/public geo execution."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
os.environ.setdefault('GIT_NO_LAZY_FETCH','1')

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('ip_timezone_checker',ROOT/'tools/browser/check_gecko_ip_timezone_evidence.py')
gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)
import gecko_environment_policy_evidence_test as old
import profile_sdk_identity_test as sdk_fixture

SOURCE,TREE,NONCE='a'*40,'b'*40,'c'*32
SOURCE_BYTES=old.SOURCE_BYTES
SOURCE_SHA=hashlib.sha256(SOURCE_BYTES).hexdigest()
_BASE=None
_SDK=sdk_fixture.fixture()
def source_reader(source,path):
    if source!=SOURCE:raise ValueError('foreign synthetic source')
    return _SDK[1].get(path,SOURCE_BYTES) if path!='app/src/main/java/local/pocketchat/GeckoWebView.java' else SOURCE_BYTES


class IpEvidenceTests(unittest.TestCase):
    def fixture(self):
        global _BASE
        if _BASE is None:_BASE=old.GeckoEnvironmentEvidenceTests().document(realm_differences=True)
        prior=copy.deepcopy(_BASE)
        expected=copy.deepcopy(_SDK[6]);expected.update(version='2.1.2',versionCode=104)
        sdk=expected['sdkBuildIdentity']
        binding=dict(sourceCommit=SOURCE,sourceTree=TREE,runNonce=NONCE,integrationApkSha256=expected['apkSha256'],sdkRunId=sdk['runId'],sdkRunAttempt=sdk['runAttempt'])
        owner=dict(slot=6,generation=1,environmentId='00000000-0000-0000-0000-000000000006')
        cases={};
        for index,(name,mode,wanted,privacy) in enumerate((
            ('default-socks','ip','America/New_York',1),('route-switch-http','ip','Asia/Kathmandu',1),
            ('https-proxy','ip','UTC',1),('manual-system','system','UTC',1),
            ('manual-iana','iana','Asia/Kathmandu',1),('rfp-priority','ip',gate.RFP_STANDARD_ZONE,2))):
            original=copy.deepcopy(prior['activity']['samples'][0]);value={key:original[key] for key in ('page','frames','workers','security')}
            # The older modeled helper only supports its original UTC/NY/KTM
            # inputs. Keep it unchanged; current157 RFP has UTC numeric parts
            # and its own exact standardized Intl identifier.
            modeled_clock=old.raw_clock('UTC' if name=='rfp-priority' else wanted)
            if name=='rfp-priority':modeled_clock['timeZone']=gate.RFP_STANDARD_ZONE
            value['case']=name;value['page'].update(nativeTimeZone=modeled_clock,documentId='00000000-0000-0000-0000-'+str(index+1).zfill(12))
            actual=original['native'];receipt=copy.deepcopy(actual['receipt']);receipt.update(identity=copy.deepcopy(owner),desiredRevision=index+1,requestToken=format(100+index,'064x'))
            receipt['binding'].update(sessionId='session-'+str(index),sessionEpoch='epoch-'+str(index),contextId=str(100+index))
            effective='' if mode=='system' or privacy==2 else wanted
            receipt['nativeReceipt'].update(requestToken=receipt['requestToken'],sessionId=receipt['binding']['sessionId'],contextId=receipt['binding']['contextId'],requestedZoneId=effective,nativeZoneId=effective)
            route=format(index+1000,'064x');status=copy.deepcopy(actual['timeZonePolicy']);status.update(desiredMode=mode,desiredZone='' if mode in ('ip','system') else wanted,desiredRevision=index+1,ipMatched=mode=='ip' and privacy==1,ipRouteStamp=route if mode=='ip' and privacy==1 else '',effectiveZone=effective,rfpPriority=privacy==2,effectiveMode='rfp-priority' if privacy==2 else 'native-override',ipSource=gate.GEO_SOURCE,observedIp='',ipObservedAt=0)
            if mode=='ip':
                route_name=('socks','http','https')[index] if index<3 else None
                observation=None if privacy==2 else dict(schema=1,source=gate.GEO_SOURCE,ip=gate.ROUTES[route_name][3],zoneId=wanted,routeStamp=route,observedAt=1793836800000+index)
                receipt.update(schema=2,effectiveZoneId=effective,ipObservation=observation,rfpManaged=privacy==2)
                if observation:status.update(observedIp=observation['ip'],ipObservedAt=observation['observedAt'])
            fresh=dict(receipt['nativeReceipt'],status='read',requestToken=format(index+5000,'064x'))
            native=dict(sessionId=receipt['binding']['sessionId'],sessionEpoch=receipt['binding']['sessionEpoch'],contextId=receipt['binding']['contextId'],freshReadback=fresh,receipt=receipt,desiredSpec=dict(schema=2,engine='gecko',mode=mode,zoneId='' if mode!='iana' else wanted),desiredRevision=index+1,identity=copy.deepcopy(owner),status=status,routeStamp=route,nativeRfpConfirmed=privacy==2,privacyLevel=privacy)
            value['native']=native
            if name=='route-switch-http':value.update(oldTicketReadAttempted=True,oldTicketRejected=True)
            if name in ('manual-system','manual-iana','rfp-priority'):value.update(geoCountBefore=4,geoCountAfter=4)
            cases[name]=value
        events=[]
        def geo(route,case,behavior='normal',written=True):
            sequence=len(events)+1
            value=dict(sequence=sequence,route=route,protocol=gate.ROUTES[route][0],case=case,kind='geo',host='ipwho.is',path='/?fields=success,ip,timezone.id',method='GET',tls=True,proxyTls=route=='https',targetSni='ipwho.is',credentialsPresent=False,responseWritten=written,behavior=behavior,responseNonce=NONCE+'-'+route+'-'+str(sequence))
            if written:
                ip=gate.ROUTES[route][3];zone='Invalid/ControlledFixtureZone' if behavior=='invalid' else gate.ROUTES[route][2]
                digest=hashlib.sha256(json.dumps(dict(success=True,ip=ip,timezone={'id':zone}),separators=(',',':')).encode()).hexdigest()
                value.update(responseAttempted=True,status=302 if behavior=='redirect' else 200,responseSha256=digest,syntheticIp=ip,syntheticZoneId=zone)
            events.append(value);return value
        def content(route,case):
            events.append(dict(sequence=len(events)+1,route=route,protocol=gate.ROUTES[route][0],case=case,kind='content',host='fp-a.pocketchat.test',path='/env-policy',phase='gecko-new-york',realm='document',documentId='',responseSha256='d'*64,tls=True,proxyTls=route=='https',targetSni='fp-a.pocketchat.test',responseWritten=True))
        def snapshot():return dict(schema=1,binding=copy.deepcopy(binding),syntheticGeoService=True,actualPublicIpGeolocationVerified=False,productionEndpointOverride=False,geoSource=gate.GEO_SOURCE,routes={name:dict(protocol=row[0],guestPort=row[1]) for name,row in gate.ROUTES.items()},events=copy.deepcopy(events),errors={k:0 for k in gate.ROUTES},controlRequests=10,upstreamConnections=0,forwardingImplemented=False,certificateExceptionUsed=False,caPemSha256=prior['hostTls']['caPemSha256'],leafDerSha256=prior['hostTls']['leafDerSha256'],closed=False)
        for route,name in (('socks','default-socks'),('http','route-switch-http'),('https','https-proxy')):geo(route,name);content(route,name)
        geo('https','cancel-late','hold',False);pending=snapshot()
        failed_status=copy.deepcopy(cases['https-proxy']['native']['status']);failed_status.update(state='failed',nativeSettingReadback=False,ipMatched=False,currentSessionPrepared=False)
        cases['cancel-late']=dict(explicitProductionMethodBoundary=True,actualUserGesture=False,oldDocumentId=cases['https-proxy']['page']['documentId'],pending=pending,after=copy.deepcopy(failed_status),lateResultAdmitted=False)
        events[-1].update(responseAttempted=True,responseWriteFailed=True)
        geo('https','bootstrap-isolation','hold',False);pending=snapshot()
        cases['bootstrap-isolation']=dict(schema=1,runNonce=NONCE,sourceCommit=SOURCE,documentId=cases['https-proxy']['page']['documentId'],source=gate.GEO_SOURCE,started=True,complete=True,roles={key:dict(available=True,created=True,executed=True,networkAllowed=False) for key in ('page','dedicated','shared','service')},pending=pending,afterAttempts=copy.deepcopy(pending),explicitProductionMethodBoundary=True,actualUserGesture=False)
        cases['bootstrap-isolation'].update(livePrivateCapabilityDuringAttempts=True,nativeAfter=copy.deepcopy(cases['https-proxy']['native']),nativeApplyLease=dict(actualNativeAck=True,leaseHeldBeforeNativeAckPublication=True,controllerPreparedBeforePublication=False,leaseReleasedAfterNativeAndStoreAck=True,ack=copy.deepcopy(cases['https-proxy']['native']['receipt']['nativeReceipt'])))
        events[-1].update(responseWritten=True,responseAttempted=True,status=200,responseSha256=hashlib.sha256(b'{"success":true,"ip":"9.9.9.9","timezone":{"id":"UTC"}}').hexdigest(),syntheticIp='9.9.9.9',syntheticZoneId='UTC')
        cases['manual-rfp-denied']=dict(actualUiAttempt=True,revisionBefore=6,revisionAfter=6,manualSaveRejected=True,status=copy.deepcopy(cases['rfp-priority']['native']['status']),privacyLevel=2)
        for name,behavior in (('redirect-rejected','redirect'),('invalid-geo-rejected','invalid')):
            geo('https',name,behavior)
            cases[name]=dict(oldDocumentId=cases['https-proxy']['page']['documentId'],remainingDocumentId=cases['https-proxy']['page']['documentId'],status=copy.deepcopy(failed_status),host=snapshot(),actualAddressUiAttempt=True,fallbackApplied=False)
        recovery=copy.deepcopy(cases['manual-system']);recovery['case']='invalid-geo-recovery'
        cases['invalid-geo-rejected'].update(newNativeSession=True,oldSessionId='old-session',failedSessionId='new-session',oldNativeRequestToken='1'*64,actualSpontaneousLateCallbackObserved=False,blankBeforeRecovery=True,navigationStopped=True,navigationFailed=True,errorDisplayed=True,spinnerStopped=True,actualTimeZoneRetryUi=True,queuedTargetRetained=True,actualManualUiRecovery=True,geoCountBeforeRecovery=6,geoCountAfterRecovery=6,manualRecovery=recovery)
        cases['invalid-geo-rejected'].pop('remainingDocumentId');cases['invalid-geo-rejected'].pop('actualAddressUiAttempt')
        host=snapshot();host['closed']=True
        setup=dict(schema=1,status='armed',sourceCommit=SOURCE,sourceTree=TREE,runNonce=NONCE,integrationApkSha256=expected['apkSha256'],slot=6,identity=copy.deepcopy(owner),unusedSlotBeforeSetup=True,scopeBeforeAnyProfileAccess=True,timezoneSealedRecordMissing=True,actualProfilesPrepare=True,actualDefaultStoreLoadYet=True,manualSeedAppliedToIpScope=False,defaultSpec=dict(schema=2,engine='gecko',mode='ip',zoneId=''),defaultRevision=1,loadedIdentity=copy.deepcopy(owner))
        activity=dict(schema=1,fixtureType=gate.FIXTURE_TYPE,engine='gecko',status='passed',stage='complete',failedAtStage='',failure='',sourceCommit=SOURCE,sourceTree=TREE,runNonce=NONCE,buildIdentity=copy.deepcopy(expected),checks=[dict(id=name,**{'pass':True}) for name in sorted(gate.REQUIRED)],cases=cases,setup=setup,nativeEvents=[],lastPage={},currentTimeZonePolicy={},actualAndroidExecution=True,actualGeckoExecution=True,syntheticGeoService=True,actualPublicIpGeolocationVerified=False,workerCoverageVerified=False,serviceWorkerCoverageVerified=False,fingerprintProtectionVerified=False,scope='Synthetic validator input, not execution evidence')
        tls=copy.deepcopy(prior['hostTls']);tls.update(binding=binding,hostnameVerified=['fp-a.pocketchat.test','fp-b.pocketchat.test','ipwho.is'],proxyIpSanVerified='127.0.0.1',privateMaterialRemoved=True)
        tls.pop('guestPort',None);tls.pop('reverseRemoved',None);tls['trustInstallation'].pop('storePath',None)
        report=dict(schema=1,fixtureType=gate.FIXTURE_TYPE,status='passed',sourceCommit=SOURCE,sourceTree=TREE,runNonce=NONCE,expectedBuildIdentity=copy.deepcopy(expected),actualAndroidExecution=True,actualGeckoExecution=True,syntheticGeoService=True,actualPublicIpGeolocationVerified=False,workerCoverageVerified=False,serviceWorkerCoverageVerified=False,executionInputsUnchanged=True,sourceFiles={name:SOURCE_SHA for name in gate.SOURCE_INPUTS},activity=activity,hostTls=tls,routeReceipts=host,systemTimeZone=dict(before='UTC',after='UTC'),cleanup={name:True for name in ('appStopped','scopeCleared','reverseRemoved','caRemoved','privateMaterialRemoved','serverQuiesced')})
        return report,expected

    def values(self,report):
        binding=report['hostTls']['binding']
        result={name+'.json':dict(schema=1,case=name,binding=copy.deepcopy(binding),evidence=copy.deepcopy(value)) for name,value in report['activity']['cases'].items()}
        for name,value in (('route-receipts',report['routeReceipts']),('setup-scope',report['activity']['setup'])):result[name+'.json']=dict(schema=1,case=name,binding=copy.deepcopy(binding),evidence=copy.deepcopy(value))
        return result
    def validate(self,report,expected=None):
        return gate.validate_behavior(report,SOURCE,expected or self.fixture()[1],self.values(report),source_reader)
    def rejects(self,changes):
        for index,change in enumerate(changes):
            with self.subTest(index=index):
                report,expected=self.fixture();change(report)
                with self.assertRaises((ValueError,KeyError,TypeError)):self.validate(report,expected)

    def test_consistent_synthetic_schema_never_claims_public_geo_or_worker_coverage(self):
        report,expected=self.fixture();original=copy.deepcopy(report);value=self.validate(report,expected)
        self.assertEqual(report,original);self.assertEqual(value['caseCount'],13)
        self.assertFalse(value['actualPublicIpGeolocationVerified']);self.assertFalse(value['workerCoverageVerified'])
        self.assertEqual(value['routeProtocols'],['socks5','http-connect','https-connect'])

    def test_source_installed_sdk_run_attempt_and_default_scope_controls(self):
        self.rejects([
            lambda r:r.update(sourceCommit='f'*40),lambda r:r.update(sourceTree='f'*40),
            lambda r:r.update(runNonce='f'*32),lambda r:r['expectedBuildIdentity'].update(apkSha256='f'*64),
            lambda r:r['activity']['buildIdentity']['sdkBuildIdentity'].update(runAttempt='2'),
            lambda r:r['sourceFiles'].pop(next(iter(gate.SOURCE_INPUTS))),
            lambda r:r['sourceFiles'].update({'../secret':'a'*64}),
            lambda r:r['activity']['setup'].update(timezoneSealedRecordMissing=False),
            lambda r:r['activity']['setup'].update(manualSeedAppliedToIpScope=True),
            lambda r:r['activity']['setup']['defaultSpec'].update(mode='system'),
            lambda r:r['activity']['setup'].update(slot=5),
            lambda r:r['activity']['setup']['loadedIdentity'].update(environmentId='00000000-0000-0000-0000-000000000007'),
        ])

    def test_actual_first_inline_january_july_quarter_offset_and_stale_native_binding(self):
        self.rejects([
            lambda r:r['activity']['cases']['default-socks']['page'].update(firstInline=False),
            lambda r:r['activity']['cases']['default-socks']['page']['nativeTimeZone']['july'].update(offsetMinutes=300),
            lambda r:r['activity']['cases']['route-switch-http']['page']['nativeTimeZone']['january'].update(minute=0),
            lambda r:r['activity']['cases']['default-socks']['native']['freshReadback'].update(contextId='999'),
            lambda r:r['activity']['cases']['default-socks']['native']['receipt']['binding'].update(sessionId='other'),
            lambda r:r['activity']['cases']['default-socks']['native']['receipt'].update(requestToken='1'*64),
            lambda r:r['activity']['cases']['default-socks']['native']['receipt']['ipObservation'].update(routeStamp='9'*64),
            lambda r:r['activity']['cases']['route-switch-http'].update(oldTicketRejected=False),
            lambda r:r['activity']['cases']['default-socks']['native']['receipt'].update(pageObservationVerified=True),
        ])

    def test_three_real_transports_no_redirect_credential_or_default_route_fallback(self):
        self.rejects([
            lambda r:r['routeReceipts']['events'][0].update(protocol='http-connect'),
            lambda r:r['routeReceipts']['events'][4].update(proxyTls=False),
            lambda r:r['routeReceipts']['events'][0].update(credentialsPresent=True),
            lambda r:r['routeReceipts']['events'][0].update(targetSni='other.example'),
            lambda r:r['routeReceipts']['events'][0].update(path='/?secret=1'),
            lambda r:r['routeReceipts'].update(upstreamConnections=1),
            lambda r:r['routeReceipts'].update(productionEndpointOverride=True),
            lambda r:r['routeReceipts']['events'][0].update(responseWritten=False),
            lambda r:r['routeReceipts']['events'][0].update(sequence=100),
            lambda r:r['activity']['cases']['https-proxy']['native']['receipt']['ipObservation'].update(ip='8.8.8.8'),
        ])

    def test_cancel_capability_isolation_actual_roles_and_server_extra_request_rejected(self):
        def extra_request(r):
            value=r['activity']['cases']['bootstrap-isolation']['afterAttempts'];row=copy.deepcopy(value['events'][-1]);row.update(sequence=len(value['events'])+1,responseNonce=NONCE+'-https-'+str(len(value['events'])+1));value['events'].append(row)
        self.rejects([
            lambda r:r['activity']['cases']['cancel-late'].update(lateResultAdmitted=True),
            lambda r:r['activity']['cases']['cancel-late']['after'].update(nativeSettingReadback=True),
            lambda r:r['activity']['cases']['bootstrap-isolation'].update(explicitProductionMethodBoundary=False),
            lambda r:r['activity']['cases']['bootstrap-isolation'].update(livePrivateCapabilityDuringAttempts=False),
            lambda r:r['activity']['cases']['bootstrap-isolation']['nativeApplyLease'].update(leaseHeldBeforeNativeAckPublication=False),
            lambda r:r['activity']['cases']['bootstrap-isolation']['nativeApplyLease'].update(leaseReleasedAfterNativeAndStoreAck=False),
            lambda r:r['activity']['cases']['bootstrap-isolation']['roles']['service'].update(executed=False),
            lambda r:r['activity']['cases']['bootstrap-isolation']['roles']['page'].update(networkAllowed=True),
            lambda r:r['activity']['cases']['bootstrap-isolation']['pending']['events'][-1].update(responseWritten=True),
            extra_request,
        ])

    def test_manual_rfp_failures_do_not_masquerade_as_ip_match(self):
        self.rejects([
            lambda r:r['activity']['cases']['manual-system'].update(geoCountAfter=5),
            lambda r:r['activity']['cases']['manual-iana']['native']['status'].update(ipMatched=True),
            lambda r:r['activity']['cases']['rfp-priority']['native']['receipt'].update(rfpManaged=False),
            lambda r:r['activity']['cases']['rfp-priority']['native']['status'].update(ipMatched=True),
            lambda r:r['activity']['cases']['manual-rfp-denied'].update(revisionAfter=99),
            lambda r:r['activity']['cases']['redirect-rejected'].update(fallbackApplied=True),
            lambda r:r['activity']['cases']['invalid-geo-rejected'].update(remainingDocumentId='other'),
            lambda r:r['activity']['cases']['invalid-geo-rejected'].update(spinnerStopped=False),
            lambda r:r['activity']['cases']['invalid-geo-rejected'].update(errorDisplayed=False),
            lambda r:r['activity']['cases']['invalid-geo-rejected'].update(actualManualUiRecovery=False),
            lambda r:r['systemTimeZone'].update(after='Asia/Tokyo'),
            lambda r:r['cleanup'].update(caRemoved=False),
            lambda r:r.update(workerCoverageVerified=True),
            lambda r:r.update(actualPublicIpGeolocationVerified=True),
        ])

    def write(self,directory,report):
        rawdir=directory/gate.RAW_DIRECTORY;rawdir.mkdir();pins={}
        for name,value in self.values(report).items():
            raw=(json.dumps(value,separators=(',',':'))+'\n').encode();(rawdir/name).write_bytes(raw);pins[name]=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
        report['casePins']=pins;(directory/gate.REPORT_NAME).write_text(json.dumps(report,separators=(',',':'))+'\n')
    def test_exact_raw_bytes_paths_unknown_keys_symlink_fifo_and_oversize(self):
        for bad in ('missing','extra','changed','symlink','directory-symlink','fifo','oversize','duplicate','secret'):
            with self.subTest(bad=bad),tempfile.TemporaryDirectory() as temp:
                directory=Path(temp);report,expected=self.fixture();self.write(directory,report);path=directory/gate.RAW_DIRECTORY/'default-socks.json'
                if bad=='missing':path.unlink()
                elif bad=='extra':(path.parent/'extra.json').write_text('{}')
                elif bad=='changed':path.write_bytes(path.read_bytes()+b' ')
                elif bad=='symlink':path.unlink();path.symlink_to(directory/gate.REPORT_NAME)
                elif bad=='directory-symlink':path.parent.rename(directory/'old');(directory/gate.RAW_DIRECTORY).symlink_to(directory/'old',target_is_directory=True)
                elif bad=='fifo':import os;path.unlink();os.mkfifo(path)
                elif bad=='oversize':path.write_bytes(b' '*262145)
                elif bad=='duplicate':path.write_text('{"x":1,"x":2}')
                else:
                    value=json.loads(path.read_text());value['evidence']['page']['secret']='secret';path.write_text(json.dumps(value));report['activity']['cases']['default-socks']['page']['secret']='secret';raw=path.read_bytes();report['casePins'][path.name]=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest());(directory/gate.REPORT_NAME).write_text(json.dumps(report))
                with self.assertRaises((ValueError,OSError,KeyError,TypeError)):gate.verify_gecko_ip_timezone_evidence(directory,SOURCE,expected,reader=source_reader)
        with tempfile.TemporaryDirectory() as temp:
            directory=Path(temp);report,expected=self.fixture();self.write(directory,report)
            self.assertEqual(gate.verify_gecko_ip_timezone_evidence(directory,SOURCE,expected,reader=source_reader)['caseCount'],13)

if __name__=='__main__':unittest.main()
