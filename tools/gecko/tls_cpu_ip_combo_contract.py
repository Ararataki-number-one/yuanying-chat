"""Mandatory twelfth production cold CPU/default-IP/TLS13 combination.
The first eleven TLS oracles remain separate. Pref ACK is never wire proof.
"""
import hashlib
import re
import check_gecko_ip_timezone_evidence as ip
import check_gecko_cpu_ip_combo_evidence as cpu
import tls_acceptance_contract as tls
from native_tls_probe_server import parse_client_hello
FIXTURE_TYPE='gecko-production-tls-cpu-ip-combo-v1'
ACTIVITY='local.pocketchat.GeckoTlsCpuIpComboIntegrationActivity'
CASE_FILE='case-combined-cpu-ip-tls13.json'
CHECKS=cpu.CHECKS+('production.tls-desired-durable','production.fresh-tls-native','production.native-url-title-admission')
ACTIVITY_FIELDS=set('schema fixtureType status stage failure sourceCommit sourceTree runNonce buildIdentity activityClass scopeAllocationActivity setup cpuSetup tlsSetup tlsStoredState freshTlsReadback runtimeBinding tlsPolicy runtimeTlsPolicy startupPreparation navigation cpuStoredState process page native cpuPolicy runtimeCpuPolicy freshCpuReadback tls checks nativeEvents actualAndroidExecution actualGeckoExecution productionChatSession syntheticGeoService actualPublicIpGeolocationVerified workerCoverageVerified serviceWorkerCoverageVerified fingerprintProtectionVerified fullTlsFingerprintEmulation quicWireVerified rawFatalAlertPacketDecoded appIndependentTlsStacksCovered'.split())
ENVELOPE_FIELDS=set('schema label status report reportSha256 prelaunchSetup processSample routeReceipts hostTls systemTimeZone cleanup wire'.split())

def require(value,message):
    if not value:raise ValueError('TLS CPU IP evidence: '+message)
def equal(actual,wanted,message):require(tls.equal(actual,wanted),message)

def validate_combo(activity,report,*,source,expected,run,engine):
    require(type(report) is dict and set(report)==ENVELOPE_FIELDS and report['schema']==1 and type(report['schema']) is int and report['label']=='combined-cpu-ip-tls13' and report['status']=='passed' and report['report']==CASE_FILE and tls.token(report['reportSha256'],64),'exact independent twelfth envelope')
    require(type(activity) is dict and set(activity)==ACTIVITY_FIELDS,'exact independent actual combined packet')
    for key,value in dict(schema=1,fixtureType=FIXTURE_TYPE,status='passed',stage='complete',failure='',sourceCommit=source,sourceTree=expected['sourceTree'],runNonce=run,activityClass=ACTIVITY,scopeAllocationActivity='local.pocketchat.GeckoIpTimeZoneIntegrationActivity',actualAndroidExecution=True,actualGeckoExecution=True,productionChatSession=True,syntheticGeoService=True).items():equal(activity.get(key),value,'actual combined packet '+key)
    tls.verify_installed(activity['buildIdentity'],expected)
    for key,value in expected.items():equal(activity['buildIdentity'].get(key),value,'actual combined installed tuple '+key)
    for key in ('actualPublicIpGeolocationVerified','workerCoverageVerified','serviceWorkerCoverageVerified','fingerprintProtectionVerified','fullTlsFingerprintEmulation','quicWireVerified','rawFatalAlertPacketDecoded','appIndependentTlsStacksCovered'):require(activity.get(key) is False,'unsupported coverage '+key)
    expected_build=expected
    before=report['prelaunchSetup'];after=activity['setup'];ip.keys(before,('schema','status','sourceCommit','sourceTree','runNonce','integrationApkSha256','slot','identity','unusedSlotBeforeSetup','scopeBeforeAnyProfileAccess','timezoneSealedRecordMissing','actualProfilesPrepare','actualDefaultStoreLoadYet','manualSeedAppliedToIpScope'));ip.keys(after,(*before,'defaultSpec','defaultRevision','loadedIdentity'));require(type(before['schema']) is int and before['schema']==1 and type(before['slot']) is int and before['slot']==6 and before['actualProfilesPrepare'] is True,'actual profile preparation missing');ip.environment(after['loadedIdentity']);owner=after['loadedIdentity']
    require(owner['slot']==6 and before.get('status')=='armed' and before.get('sourceCommit')==source and before.get('sourceTree')==expected_build['sourceTree'] and before.get('runNonce')==run and before.get('integrationApkSha256')==expected_build['apkSha256'] and before.get('unusedSlotBeforeSetup') is True and before.get('scopeBeforeAnyProfileAccess') is True and before.get('timezoneSealedRecordMissing') is True and before.get('actualDefaultStoreLoadYet') is False and before.get('manualSeedAppliedToIpScope') is False,'fresh unused default-IP scope absent')
    for key in before:equal(after.get(key),True if key=='actualDefaultStoreLoadYet' else before[key],'scope changed during actual default load: '+key)
    equal(after['loadedIdentity'],before['identity'],'missing-store environment owner differs');equal(after['defaultSpec'],dict(schema=2,engine='gecko',mode='ip',zoneId=''),'actual missing store is not IP');equal(after['defaultRevision'],1,'default timezone revision differs')
    setup=activity['cpuSetup'];ip.keys(setup,('cpuSealedRecordMissingBefore','actualColdStoreSave','loadedMode','loadedRevision','savedMode','savedRevision','identity','sessionAbsentBeforeSetup'))
    equal(setup,dict(cpuSealedRecordMissingBefore=True,actualColdStoreSave=True,loadedMode='automatic',loadedRevision=1,savedMode='1',savedRevision=2,identity=owner,sessionAbsentBeforeSetup=True),'CPU choice was not durably saved before the real session')
    page=activity['page'];ip.keys(page,('schema','firstInline','secure','sourceCommit','runNonce','documentId','origin','phase','hardwareConcurrency','nativeGetter','nativeTimeZone','markerComplete','networkAllowed'))
    require(type(page['schema']) is int and page['schema']==1 and all(page[k] is True for k in ('firstInline','secure','nativeGetter','markerComplete','networkAllowed')) and type(page['hardwareConcurrency']) is int and page['hardwareConcurrency']==1 and page['sourceCommit']==source and page['runNonce']==run and page['origin']=='https://fp-a.pocketchat.test' and page['phase']=='gecko-new-york' and type(page['documentId']) is str and re.fullmatch('[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}',page['documentId']),'same first-inline native CPU getter absent')
    ip.clock(page['nativeTimeZone'],'America/New_York');native=activity['native'];ip.native(native,'ip','America/New_York',engine);equal(native['identity'],owner,'CPU/timezone environment differs');equal(native['desiredRevision'],1,'default IP was replaced by a manual revision');require(native['privacyLevel']==1 and type(native['privacyLevel']) is int and native['nativeRfpConfirmed'] is False,'standard protection/native RFP scope differs')
    require(native['receipt']['ipObservation']['ip']=='8.8.8.8' and native['receipt']['ipObservation']['source']==ip.GEO_SOURCE,'controlled geo observation differs');cpu.cpu_proof(activity,owner)
    sdk=expected_build['sdkBuildIdentity'];binding=dict(sourceCommit=source,sourceTree=expected_build['sourceTree'],runNonce=run,integrationApkSha256=expected_build['apkSha256'],sdkRunId=sdk['runId'],sdkRunAttempt=sdk['runAttempt'])
    host=report['routeReceipts'];ip.route_snapshot(host,binding)
    require(host['closed'] is True and all(value==0 and type(value) is int for value in host['errors'].values()),'fixture route errors or unquiesced collector')
    events=host['events'];require(all(row['route']=='socks' and row['case']=='default-socks' for row in events),'combination crossed a different proxy/case')
    geos=[row for row in events if row['kind']=='geo'];require(len(geos)==1 and geos[0]['behavior']=='normal' and geos[0]['responseWritten'] is True and geos[0]['status']==200 and geos[0]['syntheticIp']=='8.8.8.8' and geos[0]['syntheticZoneId']=='America/New_York','exact single private synthetic geo response absent')
    targets=[row for row in events if row['kind']=='content' and row['path']=='/env-policy'];markers=[row for row in events if row['kind']=='content' and row['path']=='/worker-probe']
    require(len(targets)==1 and len(markers)==1 and all(row['host']=='fp-a.pocketchat.test' and row['phase']=='gecko-new-york' and row['responseWritten'] is True for row in (*targets,*markers)) and markers[0]['realm']=='document' and markers[0]['documentId']==page['documentId'] and geos[0]['sequence']<targets[0]['sequence'] and geos[0]['sequence']<markers[0]['sequence'],'same first-inline document lacks independent same-document wire marker after geo admission')
    security=activity['tls'];equal(security,dict(host='fp-a.pocketchat.test',isSecure=True,isException=False,leafDerSha256=host['leafDerSha256'],enterpriseRootsReadback=True),'actual native document TLS proof differs')
    cpu.trust(report['hostTls'],host,binding);system=report['systemTimeZone'];ip.keys(system,('before','after'));equal(system['before'],system['after'],'Android system timezone changed');ip.expected_clock(system['before'])
    cpu.process_sample(report['processSample'],activity['process'],source,expected_build['sourceTree'],run)

    tls_policy=tls.native_policy(activity['tlsPolicy'],mode='tls13',rfp=False,slot=6,pid=activity['process']['pid'],pending=False)
    equal(activity['tlsPolicy'],activity['runtimeTlsPolicy'],'same actual TLS runtime snapshot')
    equal(tls_policy['environmentId'],owner['environmentId'],'CPU/TLS/IP UUID differs');equal(tls_policy['environmentGeneration'],owner['generation'],'CPU/TLS/IP generation differs')
    equal(tls_policy['activeBootRevision'],2,'cold saved strict TLS revision');equal(tls_policy['desiredRevision'],2,'durable strict TLS revision')
    equal(activity['tlsSetup'],dict(tlsSealedRecordMissingBefore=True,actualColdStoreSave=True,loadedMode='default',loadedRevision=1,savedMode='tls13',savedRevision=2,identity=owner,sessionAbsentBeforeSetup=True),'actual missing TLS store cold save')
    equal(activity['tlsStoredState'],dict(identity=owner,revision=2,spec=dict(schema=1,engine='gecko',mode='tls13')),'actual durable strict TLS store')
    equal(activity['freshTlsReadback'],dict(configuredMin=4,configuredMax=4,defaultMin=4,defaultMax=4,hasUserMin=False,hasUserMax=False,rfpPriority=False,h2Enabled=True,h3Enabled=True),'fresh SDK native TLS readback')
    tls.preparation(activity['startupPreparation'],'tls13',False)
    rb=activity['runtimeBinding'];ip.keys(rb,('pid','currentSessionIsCaptured','displayedRuntimeIsCaptured','cpuReadyForCapturedRuntime','tlsReadyForCapturedRuntime','navigationEpoch','documentSerial','contextId','sessionId','cpuRuntimeNonce','tlsRuntimeNonce'))
    for key in ('currentSessionIsCaptured','displayedRuntimeIsCaptured','cpuReadyForCapturedRuntime','tlsReadyForCapturedRuntime'):require(rb[key] is True,'same captured actual runtime '+key)
    equal(rb['pid'],activity['process']['pid'],'same captured PID');equal(rb['contextId'],native['contextId'],'same captured native context');equal(rb['sessionId'],native['sessionId'],'same captured SDK session')
    equal(rb['cpuRuntimeNonce'],activity['cpuPolicy']['runtimeNonce'],'same CPU boot incarnation');equal(rb['tlsRuntimeNonce'],tls_policy['runtimeNonce'],'same TLS boot incarnation');require(ip.integer(rb['navigationEpoch']) and ip.integer(rb['documentSerial']),'same document navigation fence')
    equal(activity['navigation'],dict(targetStarted=True,targetLocation=True,titleMatched=True,targetRequestObserved=True,productionAdmissionReady=True,stopUsedAsCompletionOracle=False),'native exact URI/title/admission without stop inference')
    equal(activity['checks'],[dict(id=name,**{'pass':True}) for name in CHECKS],'original eight CPU/IP and three new TLS checks')
    events=activity['nativeEvents'];require(type(events) is list and 1<=len(events)<=80,'bounded native event ring')
    for i,event in enumerate(events,1):
        ip.keys(event,('sequence','kind','targetOwned','sessionId','navigation'));require(type(event['sequence']) is int and event['sequence']==i and event['kind'] in ('page-start','page-stop-true','page-stop-false') and type(event['targetOwned']) is bool and event['sessionId']==native['sessionId'] and ip.integer(event['navigation']),'native same session events')
        if event['kind']!='page-start':require(event['targetOwned'] is False,'URL-less stop cannot establish target ownership')
    require(any(e['kind']=='page-start' and e['targetOwned'] for e in events),'actual target native start')
    equal(report['cleanup'],dict(appStopped=True,scopeCleared=True,reverseRemoved=True,caRemoved=True,privateMaterialRemoved=True,serverQuiesced=True,appDataCleared=True,shellUidRestored=True),'independent combined cleanup')
    wire=validate_combo_wire(report['wire'],binding,page['documentId'])
    return dict(label='combined-cpu-ip-tls13',slot=6,pid=activity['process']['pid'],environmentId=owner['environmentId'],environmentGeneration=owner['generation'],cpuRuntimeNonce=activity['cpuPolicy']['runtimeNonce'],tlsRuntimeNonce=tls_policy['runtimeNonce'],sessionId=native['sessionId'],contextId=native['contextId'],pageHardwareConcurrency=1,pageTimeZone='America/New_York',actualProtocol='TLSv1.3',freshWireConnections=wire['connections'],syntheticGeoService=True,actualPublicIpGeolocationVerified=False,workerCoverageVerified=False,serviceWorkerCoverageVerified=False,fullTlsFingerprintEmulation=False,quicWireVerified=False)

def validate_combo_wire(wire,binding,document):
    fields=set('schema binding records recordsOverflow rejectedHandshakes actualWireCapture serverOnlyVersion ticketsDisabled observerIsReadOnly serverClosed serverThreadsJoined upstreamConnections forwardingImplemented privateMaterialExported certificateExceptionUsed rawFatalAlertPacketDecoded fullTlsFingerprintEmulation quicWireVerified'.split())
    require(type(wire) is dict and set(wire)==fields,'exact independent TLS13 wire capture');equal(wire['binding'],binding,'exact combined wire source/APK/SDK/run')
    for key,value in dict(schema=1,recordsOverflow=False,rejectedHandshakes=0,actualWireCapture=True,serverOnlyVersion='TLSv1.3',ticketsDisabled=True,observerIsReadOnly=True,serverClosed=True,serverThreadsJoined=True,upstreamConnections=0,forwardingImplemented=False,privateMaterialExported=False,certificateExceptionUsed=False,rawFatalAlertPacketDecoded=False,fullTlsFingerprintEmulation=False,quicWireVerified=False).items():equal(wire.get(key),value,'wire capture scope '+key)
    records=wire['records'];require(type(records) is list and 2<=len(records)<=32,'real page/marker fresh TLS connections')
    randoms=set();proved={}
    for i,row in enumerate(records,1):
        base=set('schema host clientHello tlsNegotiated requestObserved responseObserved sequence negotiatedVersion negotiatedAlpn sessionReused path phase realm documentId'.split())
        require(type(row) is dict and set(row)==base and row['schema']==1 and type(row['schema']) is int and row['sequence']==i and type(row['sequence']) is int and row['host']=='fp-a.pocketchat.test','exact actual successful wire row')
        hello=row['clientHello'];raw=hello.get('clientHelloHandshakeHex');require(type(raw) is str and 76<=len(raw)<=131072 and len(raw)%2==0 and re.fullmatch('[0-9a-f]+',raw),'original raw ClientHello')
        data=bytes.fromhex(raw);records_bytes=b''.join(b'\x16\x03\x01'+len(p).to_bytes(2,'big')+p for p in (data[j:j+16384] for j in range(0,len(data),16384)))
        equal(parse_client_hello(records_bytes),hello,'independent immutable ClientHello reparse')
        require(hello['serverNames']==['fp-a.pocketchat.test'] and hello['supportedVersions']==[772] and hello['preSharedKeyOffered'] is False and hello['clientRandomHex'] not in randoms,'fresh exact strict TLS13 hello');randoms.add(hello['clientRandomHex'])
        require('h2' in hello['offeredAlpn'] and 'http/1.1' in hello['offeredAlpn'],'original ALPN is retained')
        for key,value in dict(tlsNegotiated=True,requestObserved=True,responseObserved=True,negotiatedVersion='TLSv1.3',negotiatedAlpn='http/1.1',sessionReused=False).items():equal(row.get(key),value,'actual handshake HTTP '+key)
        if row['path']=='/env-policy':equal((row['phase'],row['realm'],row['documentId']),('gecko-new-york','document',''),'actual same origin document request');proved['page']=True
        elif row['path']=='/worker-probe':equal((row['phase'],row['realm'],row['documentId']),('gecko-new-york','document',document),'actual same document independent marker');proved['marker']=True
        elif row['path']=='/env-frame':require(row['phase']=='gecko-new-york' and row['realm']=='frame' and row['documentId']=='','bounded same origin frame diagnostic')
        else:require(row['path']=='/favicon.ico' and row['phase']=='' and row['realm']=='auxiliary' and row['documentId']=='','only bounded auxiliary icon')
    require(proved==dict(page=True,marker=True),'separate actual TLS page and same document marker');return dict(connections=len(records))
