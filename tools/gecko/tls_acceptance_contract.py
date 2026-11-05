"""Strict production Gecko-web TLS evidence; preference ACK is never wire proof."""
import hashlib
import re
from urllib.parse import parse_qs,urlsplit
from tls_acceptance_server import CASE_SPECS,HOST
from native_tls_probe_server import parse_client_hello
from profile_invocation_contract import verify_installed

PACKAGE='local.pocketchat.test'
DEVICE_FIELDS=set('schema fixtureType status stage failure diagnosticOnly releaseAcceptance sourceCommit sourceTree runNonce caseNonce slot mode peerPort rfpRequested retainedProfile staleUserPrefSeeded serviceRequested expectedSuccess target buildIdentity process tlsPolicy cpuPolicy storagePathEvidence startupPreparation seed security navigation nativeEvents uiSaveInvoked uiSaveCompleted uiBefore uiAfter serviceObservation actualAndroidExecution actualGeckoExecution productionChatSession productionTlsBootstrap javascriptTlsOverrideUsed debuggingEndpointUsed nativeSettingReadbackIsWireProof workerCoverageVerified serviceWorkerCoverageVerified fullTlsFingerprintEmulation quicWireVerified'.split())
POLICY_FIELDS=set('schema engine desiredRevision desiredMode activeBootRevision activeBootMode state issue failureCode pendingColdStart defaultMin defaultMax configuredMin configuredMax hasUserMin hasUserMax rfpPriority h2Enabled h3Enabled nativeSettingReadback startupReconciled scope processNonce pid runtimeNonce environmentId environmentGeneration slot wireObservationVerified fullTlsFingerprintEmulation quicWireVerified persistentWorkerColdStartVerified connectionScope independentDownloaderTlsCovered connectionCheckTlsCovered proxyEntranceTlsCovered'.split())

def require(value,message):
    if not value:raise ValueError('Gecko product TLS evidence: '+message)

def equal(a,b):
    if type(a) is not type(b):return False
    if type(b) is dict:return set(a)==set(b) and all(equal(a[k],v) for k,v in b.items())
    if type(b) is list:return len(a)==len(b) and all(equal(x,y) for x,y in zip(a,b))
    return a==b

def integer(value,minimum=0,maximum=2**63-1):return type(value) is int and minimum<=value<=maximum

def token(value,size=32):return type(value) is str and re.fullmatch('[0-9a-f]{'+str(size)+'}',value) is not None

def native_policy(value,*,mode,rfp,slot,pid,pending):
    require(type(value) is dict and set(value)==POLICY_FIELDS,'exact native TLS status')
    require(type(value['schema']) is int and value['schema']==1 and value['engine']=='gecko' and value['state']=='ready' and value['scope']=='runtime-wide' and value['issue']=='' and value['failureCode']=='','ready native TLS policy')
    for key in ('nativeSettingReadback','startupReconciled','h2Enabled','h3Enabled'):require(value[key] is True,'fresh native flag '+key)
    require(value['connectionScope']=='gecko-web-connections','native policy covers Gecko web connections only')
    for key in ('hasUserMin','hasUserMax','wireObservationVerified','fullTlsFingerprintEmulation','quicWireVerified','persistentWorkerColdStartVerified','independentDownloaderTlsCovered','connectionCheckTlsCovered','proxyEntranceTlsCovered'):require(value[key] is False,'scope/residual USER '+key)
    require(value['rfpPriority'] is rfp,'fresh RFP readback must match requested independent policy')
    require(type(value['slot']) is int and value['slot']==slot and type(value['pid']) is int and value['pid']==pid,'native policy process/slot')
    require(integer(value['environmentGeneration'],0,2**31-1) and type(value['environmentId']) is str and re.fullmatch('[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}',value['environmentId']),'environment identity')
    require(token(value['processNonce']) and token(value['runtimeNonce']),'runtime invocation nonces')
    require(value['activeBootMode']==mode and value['desiredMode']==('default' if pending else mode) and integer(value['activeBootRevision'],1) and integer(value['desiredRevision'],1),'desired and immutable boot modes/revisions')
    require(value['pendingColdStart'] is pending and (value['desiredRevision']>value['activeBootRevision'] if pending else value['desiredRevision']==value['activeBootRevision']),'pending cold save cannot claim hot apply')
    require(all(integer(value[k],3,4) for k in ('defaultMin','defaultMax','configuredMin','configuredMax')) and value['defaultMin']<=value['defaultMax'] and value['configuredMin']==value['defaultMin'] and value['configuredMax']==value['defaultMax'],'actual modern DEFAULT/effective range')
    if mode=='tls13':require(value['defaultMin']==value['defaultMax']==4,'strict native DEFAULT4/4')
    return value

def preparation(value,mode,stale_user):
    fields=set('schema status scope mode profileBytesBefore profileBytesAfter removedOwnedBytes nonTlsPrefsBeforeSha256 nonTlsPrefsAfterSha256 nonTlsPrefsBytePreserved closedRouteConfigPrefixPreserved configBeforeSha256 configAfterSha256'.split())
    require(type(value) is dict and set(value)==fields and type(value['schema']) is int and value['schema']==1 and value['status']=='verified' and value['scope']=='offline-two-owned-tls-preferences' and value['mode']==mode,'actual pre-runtime preparation receipt')
    require(all(integer(value[k],0,4*1024*1024) for k in ('profileBytesBefore','profileBytesAfter','removedOwnedBytes')) and value['profileBytesBefore']-value['profileBytesAfter']==value['removedOwnedBytes'],'owned-byte removal accounting')
    require(all(token(value[k],64) for k in ('nonTlsPrefsBeforeSha256','nonTlsPrefsAfterSha256','configBeforeSha256','configAfterSha256')) and value['nonTlsPrefsBeforeSha256']==value['nonTlsPrefsAfterSha256'],'all original non-TLS profile bytes preserved before native runtime')
    require(value['nonTlsPrefsBytePreserved'] is True and value['closedRouteConfigPrefixPreserved'] is True,'original CPU/closed-route prefix preserved')
    require((value['configBeforeSha256']==value['configAfterSha256']) is (mode=='default'),'default is unmodified config, strict appends only actual range')
    if stale_user:require(value['removedOwnedBytes']>0,'actual nonempty old USER lines reconciled')

def validate_device(value,*,spec,binding,run,source,tree,identity,leaf):
    label,slot,mode,rfp,retain,stale_user,resample,protocol,success,service=spec;pending=label=='pending-default-tls12'
    require(type(value) is dict and set(value)==DEVICE_FIELDS and type(value['schema']) is int and value['schema']==1 and value['fixtureType']=='gecko-production-tls-v1' and value['status']=='passed' and value['stage']=='complete' and value['failure']=='','complete exact production packet')
    for key,wanted in dict(runNonce=run,caseNonce=binding['caseNonce'],sourceCommit=source,sourceTree=tree,slot=slot,mode=mode,peerPort=binding['port'],rfpRequested=rfp,retainedProfile=retain,staleUserPrefSeeded=stale_user,serviceRequested=service,expectedSuccess=success).items():require(equal(value.get(key),wanted),'original packet tuple '+key)
    verify_installed(value['buildIdentity'],identity);require(all(k in value['buildIdentity'] and equal(value['buildIdentity'][k],v) for k,v in identity.items()),'typed full installed tuple')
    for key in ('diagnosticOnly','actualAndroidExecution','actualGeckoExecution','productionChatSession','productionTlsBootstrap'):require(value[key] is True,'actual production scope '+key)
    for key in ('releaseAcceptance','javascriptTlsOverrideUsed','debuggingEndpointUsed','nativeSettingReadbackIsWireProof','workerCoverageVerified','serviceWorkerCoverageVerified','fullTlsFingerprintEmulation','quicWireVerified'):require(value[key] is False,'unverified scope '+key)
    process=value['process'];require(type(process) is dict and set(process)=={'pid','uid','name'} and integer(process['pid'],1,2**31-1) and integer(process['uid'],10000,99999) and process['name']==PACKAGE+':profile'+str(slot),'actual environment process')
    policy=native_policy(value['tlsPolicy'],mode=mode,rfp=rfp,slot=slot,pid=process['pid'],pending=pending)
    cpu=value['cpuPolicy'];require(type(cpu) is dict and cpu.get('state')=='ready' and cpu.get('nativeSettingReadback') is True and cpu.get('startupReconciled') is True and cpu.get('scope')=='runtime-wide' and equal(cpu.get('slot'),slot) and equal(cpu.get('pid'),process['pid']) and cpu.get('environmentId')==policy['environmentId'] and equal(cpu.get('environmentGeneration'),policy['environmentGeneration']),'independent actual CPU bootstrap remains admitted')
    require(cpu.get('workerCoverageVerified') is False and cpu.get('serviceWorkerCoverageVerified') is False,'CPU scope remains independent')
    storage=value['storagePathEvidence'];fields=set('schema status slot frameworkDataAncestorAlias globalNoBackupAncestorAlias environmentRootAncestorAlias noBackupWithinDataAnchor rootMatchesSlot privateComponentsNoSymlinks validatedPrivateComponents runtimePathsCanonical'.split())
    require(type(storage) is dict and set(storage)==fields and equal(storage['schema'],1) and storage['status']=='verified' and equal(storage['slot'],slot) and equal(storage['validatedPrivateComponents'],3),'actual framework storage anchoring')
    for key in ('frameworkDataAncestorAlias','globalNoBackupAncestorAlias','environmentRootAncestorAlias'):require(type(storage[key]) is bool,'storage alias Boolean')
    for key in ('noBackupWithinDataAnchor','rootMatchesSlot','privateComponentsNoSymlinks','runtimePathsCanonical'):require(storage[key] is True,'owned private path '+key)
    preparation(value['startupPreparation'],mode,stale_user)
    target='https://'+HOST+':'+str(binding['port'])+'/tls-product/slot'+str(slot)+'/page?run='+run+'&case='+binding['caseNonce']+'&source='+source
    require(value['target']==target,'exact target URL')
    nav=value['navigation'];fields=set('targetStarted targetLocation titleMatched targetRequestObserved productionAdmissionReady targetError errorCategory errorCode nativeErrorUrlMatched nativeStopOwnershipVerified nativeSecurityUrlOwnershipVerified stopCallbacks successfulStopCallbacks'.split())
    require(type(nav) is dict and set(nav)==fields,'native navigation schema')
    for key in ('targetStarted','targetLocation','titleMatched','targetRequestObserved','productionAdmissionReady','targetError','nativeErrorUrlMatched'):require(type(nav[key]) is bool,'native Boolean '+key)
    require(nav['targetRequestObserved'] is True and nav['productionAdmissionReady'] is True and nav['nativeStopOwnershipVerified'] is False and nav['nativeSecurityUrlOwnershipVerified'] is False,'real request after admission; URL-less callbacks remain diagnostic')
    require(integer(nav['stopCallbacks'],0,128) and integer(nav['successfulStopCallbacks'],0,nav['stopCallbacks']),'bounded URL-less native stops')
    events=value['nativeEvents'];require(type(events) is list and 1<=len(events)<=128,'bounded native events')
    for event in events:
        require(type(event) is dict and set(event)=={'event','targetOwned','error','admissionReady','nativeUrlAvailable'} and event['event'] in ('start','stop','request','location','error') and type(event['targetOwned']) is bool and event['nativeUrlAvailable'] is (event['event']!='stop') and (event['error'] is None or type(event['error']) is str and re.fullmatch('[0-9]{1,3}:[0-9]{1,3}',event['error'])) and (event['admissionReady'] is None or type(event['admissionReady']) is bool),'strict synthetic-free native event')
    require(any(e['event']=='request' and e['targetOwned'] and e['admissionReady'] is True for e in events),'owned native request sees actual production gates ready')
    sec=value['security']
    if sec:
        require(type(sec) is dict and set(sec)=={'isSecure','isException','host','leafSha256','enterpriseRootsReadback','nativeUrlAvailable'} and all(type(sec[k]) is bool for k in ('isSecure','isException','enterpriseRootsReadback','nativeUrlAvailable')) and sec['host']==HOST and (sec['leafSha256']=='' or token(sec['leafSha256'],64)) and sec['nativeUrlAvailable'] is False,'bounded native security metadata only')
    else:require(type(sec) is dict,'native security object')
    require(integer(nav['errorCategory'],-1,999) and integer(nav['errorCode'],-1,999),'typed native error codes')
    if success:
        require(all(nav[k] is True for k in ('targetStarted','targetLocation','titleMatched')) and nav['targetError'] is False and nav['errorCategory']==nav['errorCode']==-1,'exact start/location/nonce-title, not stop-derived completion')
        sec=value['security'];require(type(sec) is dict and set(sec)=={'isSecure','isException','host','leafSha256','enterpriseRootsReadback','nativeUrlAvailable'} and sec['isSecure'] is True and sec['isException'] is False and sec['host']==HOST and sec['leafSha256']==leaf and sec['enterpriseRootsReadback'] is True and sec['nativeUrlAvailable'] is False,'actual native trusted leaf, independently bound with target and wire')
    else:
        require(nav['targetError'] is True and nav['nativeErrorUrlMatched'] is True and nav['titleMatched'] is False and equal(nav['errorCategory'],2) and equal(nav['errorCode'],34),'exact native security2/SSL34 URI error, never timeout')
        require(any(e['event']=='error' and e['targetOwned'] and e['error']=='2:34' for e in events),'original owned error event')
    require(value['uiSaveInvoked'] is pending and value['uiSaveCompleted'] is pending,'real pending UI save scope')
    if pending:
        before,after=value['uiBefore'],value['uiAfter'];keys=set('pid runtimeNonce processNonce navigationEpoch connectionEpoch loadCalls urlSha256 pendingSha256 submitting operation transferActive resourceChoosers resourceFilePreparations fileWorkActive'.split())
        require(type(before) is dict and set(before)==keys and equal(before,after),'save itself must not navigate, restart or mutate live task state')
        require(equal(before['pid'],process['pid']) and before['runtimeNonce']==policy['runtimeNonce'] and before['processNonce']==policy['processNonce'] and token(before['urlSha256'],64) and token(before['pendingSha256'],64),'live save invocation ownership')
        for k in ('navigationEpoch','connectionEpoch','loadCalls','resourceChoosers','resourceFilePreparations'):require(integer(before[k]),'typed live state counter')
        for k in ('submitting','operation','transferActive','fileWorkActive'):require(type(before[k]) is bool,'typed live work flag')
    else:require(value['uiBefore']==value['uiAfter']=={},'no fabricated UI operation')
    if stale_user:
        seed=value['seed'];require(type(seed) is dict and set(seed)==set('performed min max otherBytesPreserved originalBytes seededBytes originalSha256 otherSha256 testSetupOnly'.split()) and seed['performed'] is True and equal(seed['min'],4) and equal(seed['max'],4) and seed['otherBytesPreserved'] is True and seed['testSetupOnly'] is True and integer(seed['originalBytes'],0,4*1024*1024) and integer(seed['seededBytes'],1,4*1024*1024) and token(seed['originalSha256'],64) and token(seed['otherSha256'],64),'nonempty USER test seed and untouched other bytes, not a native ACK')
    else:require(value['seed']=={},'unexpected USER seed')
    observation=value['serviceObservation']
    if service:
        prefix='/tls-product/slot'+str(slot)+'/'
        require(type(observation) is dict and set(observation)==set('schema runNonce caseNonce sourceCommit slot existingRegistration controlledBeforeRegistration scriptPath scopePath bootNonce fetchNonceMatched'.split()),'actual persistent worker packet')
        for k,v in dict(schema=1,runNonce=run,caseNonce=binding['caseNonce'],sourceCommit=source,slot=slot,scriptPath=prefix+'service.js',scopePath=prefix,fetchNonceMatched=True).items():require(equal(observation[k],v),'service identity '+k)
        require(type(observation['existingRegistration']) is bool and type(observation['controlledBeforeRegistration']) is bool and token(observation['bootNonce']),'actual worker registration/instance metadata')
    else:require(observation is None,'unexpected worker claim')
    return dict(label=label,slot=slot,mode=mode,pid=process['pid'],environmentId=policy['environmentId'],environmentGeneration=policy['environmentGeneration'],processNonce=policy['processNonce'],runtimeNonce=policy['runtimeNonce'],activeBootRevision=policy['activeBootRevision'],desiredRevision=policy['desiredRevision'],nativeMin=policy['configuredMin'],nativeMax=policy['configuredMax'],serviceBootNonce=observation['bootNonce'] if service else None)

def validate_wire(host,entries,*,run,source):
    require(type(host) is dict and set(host)==set('schema runNonce sourceCommit records cases recordsOverflow controls rejectedRequests upstreamConnections forwardingImplemented actualWireCapture ticketsDisabled privateMaterialExported certificateExceptionUsed serverClosed serverThreadsJoined'.split()) and equal(host.get('schema'),1) and host.get('runNonce')==run and host.get('sourceCommit')==source,'host source/run')
    for key in ('actualWireCapture','ticketsDisabled','serverClosed','serverThreadsJoined'):require(host.get(key) is True,'actual socket/cleanup '+key)
    for key in ('recordsOverflow','forwardingImplemented','privateMaterialExported','certificateExceptionUsed'):require(host.get(key) is False,'closed/bounded fixture '+key)
    require(equal(host.get('upstreamConnections'),0),'no upstream network')
    records=host.get('records');require(type(records) is list and 11<=len(records)<=96 and all(integer(r.get('sequence'),1,96) for r in records) and [r.get('sequence') for r in records]==list(range(1,len(records)+1)),'all final bounded ordered socket records')
    require(type(host.get('cases')) is dict and set(host['cases'])=={e['binding']['caseNonce'] for e in entries},'all fixed registered cases')
    randoms=set();offered={};peer_rfp={e['binding']['port']:spec[3] for spec,e in zip(CASE_SPECS,entries)}
    for row in records:
        required={'schema','epoch','destinationPort','slot','serverOnlyVersion','clientHello','tlsNegotiated','httpReceived','sequence'}
        optional={'negotiatedVersion','negotiatedAlpn','sessionReused','caseNonce','requestRole','serviceBootNonce','errorType','tlsErrorReason'}
        require(type(row) is dict and required<=set(row) and set(row)<=required|optional,'fixed raw socket metadata; no arbitrary log fields')
        require(type(row) is dict and equal(row.get('schema'),1) and integer(row.get('epoch'),1,len(CASE_SPECS)) and integer(row.get('destinationPort'),42000,61999),'bounded controlled socket record')
        hello=row.get('clientHello')
        if hello is None:continue # An app-stop may close a speculative socket; it cannot prove any case.
        raw=hello.get('clientHelloHandshakeHex');require(type(raw) is str and 76<=len(raw)<=131072 and len(raw)%2==0 and re.fullmatch('[0-9a-f]+',raw),'original ClientHello bytes')
        original=bytes.fromhex(raw);packets=b''.join(b'\x16\x03\x01'+len(p).to_bytes(2,'big')+p for p in (original[i:i+16384] for i in range(0,len(original),16384)))
        require(equal(parse_client_hello(packets),hello),'actual ClientHello independent reparse')
        require(hello['clientRandomHex'] not in randoms and hello['preSharedKeyOffered'] is False,'fresh non-PSK handshake');randoms.add(hello['clientRandomHex'])
        require(hello['serverNames']==[HOST] and not ({0x0301,0x0302}&set(hello['supportedVersions'])) and 0x0304 in hello['supportedVersions'],'modern actual SNI/version vector')
        alpn=hello['offeredAlpn'];require('h2' in alpn and 'http/1.1' in alpn,'H2/HTTP1 ALPN retained')
        require(row['destinationPort'] in peer_rfp,'original record uses a registered actual peer')
        group=str(peer_rfp[row['destinationPort']]).lower()
        if group not in offered:offered[group]=alpn
        require(equal(offered[group],alpn),'TLS cap cannot mutate ALPN within the same independent RFP policy')
    results={}
    for spec,entry in zip(CASE_SPECS,entries):
        label,slot,mode,rfp,retain,stale,resample,version,success,service=spec;binding=entry['binding'];case=binding['caseNonce']
        stored=host['cases'][case];require(type(stored) is dict and set(stored)==set(binding)|{'serviceObservation'} and all(equal(stored.get(k),v) for k,v in binding.items()),'host original case registration')
        rows=[r for r in records if r['epoch']==binding['epoch'] and r['destinationPort']==binding['port'] and r['clientHello'] is not None]
        require(1<=len(rows)<=12,'actual independent selected peer attempts '+label)
        completed=[]
        for row in rows:
            hello=row['clientHello'];versions=hello['supportedVersions'];require(equal(row['slot'],slot) and row['serverOnlyVersion']==version and ((0x0303 not in versions) if mode=='tls13' else (0x0303 in versions)),'actual selected range on wire '+label)
            if success:
                require(row.get('tlsNegotiated') is True and row.get('negotiatedVersion')==version and row.get('negotiatedAlpn')=='http/1.1' and row.get('sessionReused') is False,'actual negotiated protocol/ALPN '+label)
                if row.get('caseNonce')==case and row.get('httpReceived') is True and row.get('requestRole')=='page' and 'errorType' not in row:completed.append(row)
            else:require(row.get('tlsNegotiated') is False and row.get('httpReceived') is False and row.get('errorType')=='SSLError' and row.get('tlsErrorReason')=='UNSUPPORTED_PROTOCOL','actual peer protocol rejection, not timeout/certificate failure '+label)
        require(bool(completed) if success else not completed,'nonce-bound HTTP success/rejection '+label)
        if service:
            packet=entry['device']['serviceObservation'];require(equal(stored.get('serviceObservation'),packet),'device worker packet equals independent host packet')
            worker=[r for r in rows if r.get('caseNonce')==case and r.get('requestRole')=='service-fetch' and r.get('serviceBootNonce')==packet['bootNonce'] and r.get('httpReceived') is True and 'errorType' not in r]
            require(worker,'actual TLS request issued by source-pinned persistent Service Worker, not script download/page HTTP')
        results[label]=dict(connections=len(rows),actualProtocol=version if success else None,protocolRejected=not success,workerFetchProven=service)
    return dict(cases=results,uniqueClientRandoms=len(randoms),offeredAlpnByRfp=offered,rawFatalAlertPacketDecoded=False,fullTlsFingerprintEmulation=False,quicWireVerified=False)

def validate_cross(entries,process_checks):
    by={entry['label']:entry for entry in entries};get=lambda label:by[label]['finding']
    a,b=get('strict-tls12'),get('strict-tls13')
    for label in ('strict-tls13','pending-default-tls12'):
        actual=get(label)
        for k in ('pid','environmentId','environmentGeneration','processNonce','runtimeNonce','activeBootRevision'):require(equal(actual[k],a[k]),'same strict runtime resample '+k)
    pending,restored=get('pending-default-tls12'),get('restored-default-tls12')
    require(restored['environmentId']==pending['environmentId'] and restored['environmentGeneration']==pending['environmentGeneration'] and restored['activeBootRevision']==pending['desiredRevision'] and restored['processNonce']!=pending['processNonce'] and restored['runtimeNonce']!=pending['runtimeNonce'],'same desired UI save actually applied only after true cold bootstrap')
    before,after=get('persistent-before'),get('persistent-after')
    require(before['environmentId']==after['environmentId'] and before['environmentGeneration']==after['environmentGeneration'] and before['activeBootRevision']==after['activeBootRevision'] and before['processNonce']!=after['processNonce'] and before['runtimeNonce']!=after['runtimeNonce'] and before['serviceBootNonce']!=after['serviceBootNonce'],'same registration and desired policy survive real process cold start with a new worker instance')
    require(by['persistent-before']['device']['serviceObservation']['existingRegistration'] is False and by['persistent-after']['device']['serviceObservation']['existingRegistration'] is True,'persistent registration cannot be replaced by a new worker')
    require(by['persistent-before']['binding']['port']==by['persistent-after']['binding']['port'],'persistent worker exact HTTPS origin retained')
    one,two,again=get('concurrent-strict-tls13'),get('concurrent-default-tls12'),get('concurrent-strict-resample-tls12')
    for k in ('pid','environmentId','processNonce','runtimeNonce'):require(one[k]!=two[k],'concurrent environment separation '+k)
    for k in ('pid','environmentId','environmentGeneration','processNonce','runtimeNonce','activeBootRevision'):require(equal(one[k],again[k]),'strict environment remains unchanged after default peer '+k)
    require(type(process_checks) is list and len(process_checks)==4,'both actual concurrent processes checked before and after resample')
    expected=[('both-resident',one),('both-resident',two),('after-resample',one),('after-resample',two)]
    for row,(stage,finding) in zip(process_checks,expected):require(type(row) is dict and set(row)=={'stage','slot','expectedPid','observedPid','shellUid'} and row['stage']==stage and equal(row['slot'],finding['slot']) and equal(row['expectedPid'],finding['pid']) and row['observedPid']==str(finding['pid']) and equal(row['shellUid'],2000),'actual shell PID residency')
