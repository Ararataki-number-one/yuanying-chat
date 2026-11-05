"""Explicit synthetic Android metadata + real host OpenSSL sockets. Never device evidence."""
import copy
import hashlib
import json
from pathlib import Path
import socket
import ssl
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/gecko'));sys.path.insert(0,str(ROOT/'tools/browser'))
from tls_acceptance_server import TlsAcceptanceServer,CASE_SPECS,HOST,GUEST_PORT
from fingerprint_fixture_server import EphemeralCertificates
import check_gecko_tls_evidence as checker
import tls_acceptance_contract as contract
SOURCE='a'*40;TREE='b'*40;RUN='c'*32

def host_context(mode,ca):
    c=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT);c.minimum_version=ssl.TLSVersion.TLSv1_3 if mode=='tls13' else ssl.TLSVersion.TLSv1_2;c.maximum_version=ssl.TLSVersion.TLSv1_3;c.options|=ssl.OP_NO_TICKET;c.set_alpn_protocols(['h2','http/1.1']);c.load_verify_locations(cafile=ca);return c

def request(server,certificates,binding,mode,path,method='GET',packet=None):
    port=binding['port'];peer=socket.create_connection(('127.0.0.1',server.port),timeout=5);peer.settimeout(5)
    try:
        peer.sendall(('CONNECT '+HOST+':'+str(port)+' HTTP/1.1\r\nHost: '+HOST+':'+str(port)+'\r\n\r\n').encode());head=b''
        while not head.endswith(b'\r\n\r\n'):head+=peer.recv(1)
        wrapped=host_context(mode,certificates.ca).wrap_socket(peer,server_hostname=HOST);peer=wrapped
        body=json.dumps(packet,separators=(',',':')).encode() if packet is not None else b''
        wrapped.sendall((method+' '+path+' HTTP/1.1\r\nHost: '+HOST+':'+str(port)+'\r\nContent-Length: '+str(len(body))+'\r\nConnection: close\r\n\r\n').encode()+body)
        raw=b''
        while True:
            value=wrapped.recv(8192)
            if not value:break
            raw+=value
            if len(raw)>65536:raise ValueError('Host response exceeded bound')
        return raw
    except ssl.SSLError:return None
    finally:peer.close()

def service_packet(spec,binding):
    slot=spec[1];prefix='/tls-product/slot'+str(slot)+'/'
    return dict(schema=1,runNonce=RUN,caseNonce=binding['caseNonce'],sourceCommit=SOURCE,slot=slot,existingRegistration=spec[0]=='persistent-after',controlledBeforeRegistration=spec[0]=='persistent-after',scriptPath=prefix+'service.js',scopePath=prefix,bootNonce=('e' if spec[0]=='persistent-before' else 'f')*32,fetchNonceMatched=True)

def model_identity():
    # These values deliberately cannot satisfy the real SDK verifier. Tests
    # replace only that boundary and compare every typed field exactly.
    value=dict(schema=1,package='local.pocketchat.test',sourceCommit=SOURCE,sourceTree=TREE,dirtySource=False,version='2.1.3',versionCode=105,apkSha256='d'*64,apkBytes=123,buildStampSha256='e'*64,sdkBuildIdentity=dict(runId='7',runAttempt='1'))
    value.update({key:'explicit-host-model-'+key for key in checker.SDK_FIELDS});return value

def model_device(spec,binding,identity,leaf):
    label,slot,mode,rfp,retain,stale,resample,version,success,service=spec;pending=label=='pending-default-tls12'
    boot_index={'strict-tls13':2,'pending-default-tls12':2,'concurrent-strict-resample-tls12':9}.get(label,binding['epoch'])
    revision=1 if label=='default-tls12' or slot==2 else 2 if boot_index==2 else 3 if label=='restored-default-tls12' else 4
    pid=1200+boot_index;environment='00000000-0000-0000-0000-00000000000'+str(slot)
    policy=dict(schema=1,engine='gecko',desiredRevision=3 if pending else revision,desiredMode='default' if pending else mode,activeBootRevision=revision,activeBootMode=mode,state='ready',issue='',failureCode='',pendingColdStart=pending,defaultMin=4 if mode=='tls13' else 3,defaultMax=4,configuredMin=4 if mode=='tls13' else 3,configuredMax=4,hasUserMin=False,hasUserMax=False,rfpPriority=rfp,h2Enabled=True,h3Enabled=True,nativeSettingReadback=True,startupReconciled=True,scope='runtime-wide',processNonce=format(boot_index,'032x'),pid=pid,runtimeNonce=format(boot_index+100,'032x'),environmentId=environment,environmentGeneration=1,slot=slot,wireObservationVerified=False,fullTlsFingerprintEmulation=False,quicWireVerified=False,persistentWorkerColdStartVerified=False,connectionScope='gecko-web-connections',independentDownloaderTlsCovered=False,connectionCheckTlsCovered=False,proxyEntranceTlsCovered=False)
    prep=dict(schema=1,status='verified',scope='offline-two-owned-tls-preferences',mode=mode,profileBytesBefore=100,profileBytesAfter=80,removedOwnedBytes=20,nonTlsPrefsBeforeSha256='a'*64,nonTlsPrefsAfterSha256='a'*64,nonTlsPrefsBytePreserved=True,closedRouteConfigPrefixPreserved=True,configBeforeSha256='b'*64,configAfterSha256=('b' if mode=='default' else 'c')*64)
    before=dict(pid=pid,runtimeNonce=policy['runtimeNonce'],processNonce=policy['processNonce'],navigationEpoch=3,connectionEpoch=2,loadCalls=5,urlSha256='a'*64,pendingSha256='b'*64,submitting=False,operation=False,transferActive=False,resourceChoosers=0,resourceFilePreparations=0,fileWorkActive=False)
    target='https://'+HOST+':'+str(binding['port'])+'/tls-product/slot'+str(slot)+'/page?run='+RUN+'&case='+binding['caseNonce']+'&source='+SOURCE
    seed=dict(performed=True,min=4,max=4,otherBytesPreserved=True,originalBytes=100,seededBytes=180,originalSha256='a'*64,otherSha256='b'*64,testSetupOnly=True) if stale else {}
    return dict(schema=1,fixtureType='gecko-production-tls-v1',status='passed',stage='complete',failure='',diagnosticOnly=True,releaseAcceptance=False,sourceCommit=SOURCE,sourceTree=TREE,runNonce=RUN,caseNonce=binding['caseNonce'],slot=slot,mode=mode,peerPort=binding['port'],rfpRequested=rfp,retainedProfile=retain,staleUserPrefSeeded=stale,serviceRequested=service,expectedSuccess=success,target=target,buildIdentity=copy.deepcopy(identity),process=dict(pid=pid,uid=10234,name='local.pocketchat.test:profile'+str(slot)),tlsPolicy=policy,cpuPolicy=dict(state='ready',nativeSettingReadback=True,startupReconciled=True,scope='runtime-wide',slot=slot,pid=pid,environmentId=environment,environmentGeneration=1,workerCoverageVerified=False,serviceWorkerCoverageVerified=False),storagePathEvidence=dict(schema=1,status='verified',slot=slot,frameworkDataAncestorAlias=False,globalNoBackupAncestorAlias=True,environmentRootAncestorAlias=True,noBackupWithinDataAnchor=True,rootMatchesSlot=True,privateComponentsNoSymlinks=True,validatedPrivateComponents=3,runtimePathsCanonical=True),startupPreparation=prep,seed=seed,security=dict(isSecure=True,isException=False,host=HOST,leafSha256=leaf,enterpriseRootsReadback=True,nativeUrlAvailable=False) if success else {},navigation=dict(targetStarted=True,targetLocation=success,titleMatched=success,targetRequestObserved=True,productionAdmissionReady=True,targetError=not success,errorCategory=-1 if success else 2,errorCode=-1 if success else 34,nativeErrorUrlMatched=not success,nativeStopOwnershipVerified=False,nativeSecurityUrlOwnershipVerified=False,stopCallbacks=0,successfulStopCallbacks=0),nativeEvents=[dict(event='request',targetOwned=True,error=None,admissionReady=True,nativeUrlAvailable=True),dict(event='start',targetOwned=True,error=None,admissionReady=None,nativeUrlAvailable=True),dict(event='location' if success else 'error',targetOwned=True,error=None if success else '2:34',admissionReady=None,nativeUrlAvailable=True)],uiSaveInvoked=pending,uiSaveCompleted=pending,uiBefore=before if pending else {},uiAfter=copy.deepcopy(before) if pending else {},serviceObservation=service_packet(spec,binding) if service else None,actualAndroidExecution=True,actualGeckoExecution=True,productionChatSession=True,productionTlsBootstrap=True,javascriptTlsOverrideUsed=False,debuggingEndpointUsed=False,nativeSettingReadbackIsWireProof=False,workerCoverageVerified=False,serviceWorkerCoverageVerified=False,fullTlsFingerprintEmulation=False,quicWireVerified=False)

class HostModelEvidence:
    def __init__(self):
        self.certificates=EphemeralCertificates();self.server=None;self.identity=model_identity();self.entries=[];self.host=None;self.leaf=self.certificates.leaf_sha
        try:
            self.server=TlsAcceptanceServer(self.certificates,RUN,SOURCE,(ROOT/'tests/gecko/assets/tls-acceptance-page.js').read_text(),(ROOT/'tests/gecko/assets/tls-acceptance-worker.js').read_text()).start()
            for i,spec in enumerate(CASE_SPECS,1):
                binding=self.server.begin(spec[0],format(i+1000,'032x'));prefix='/tls-product/slot'+str(spec[1])+'/';query='?run='+RUN+'&case='+binding['caseNonce']+'&source='+SOURCE
                raw=request(self.server,self.certificates,binding,spec[2],prefix+'page'+query)
                if spec[8] and (raw is None or ('TLS product:'+binding['caseNonce']).encode() not in raw):raise AssertionError('Real host success page missing')
                if not spec[8] and raw is not None:raise AssertionError('Real host protocol restriction did not reject')
                if spec[9]:
                    if spec[0]=='persistent-before':request(self.server,self.certificates,binding,spec[2],prefix+'service.js')
                    packet=service_packet(spec,binding);request(self.server,self.certificates,binding,spec[2],prefix+'sw-fetch'+query+'&boot='+packet['bootNonce']);request(self.server,self.certificates,binding,spec[2],prefix+'service-report'+query,method='POST',packet=packet)
                device=model_device(spec,binding,self.identity,self.leaf)
                # Explicit synthetic identity boundary; production verification remains unchanged.
                old=contract.verify_installed;contract.verify_installed=lambda actual,expected:None if actual==expected else (_ for _ in ()).throw(ValueError('Model identity differs'))
                try:finding=contract.validate_device(device,spec=spec,binding=binding,run=RUN,source=SOURCE,tree=TREE,identity=self.identity,leaf=self.leaf)
                finally:contract.verify_installed=old
                self.entries.append(dict(label=spec[0],binding=binding,status='passed',device=device,finding=finding))
            deadline=time.monotonic()+5
            while time.monotonic()<deadline:
                if all(any(r.get('epoch')==e['binding']['epoch'] and r.get('destinationPort')==e['binding']['port'] for r in self.server.snapshot()['records']) for e in self.entries):break
                time.sleep(.01)
            self.server.close();self.host=self.server.snapshot()
            self.process_checks=[]
            for stage in ('both-resident','after-resample'):
                for label in ('concurrent-strict-tls13','concurrent-default-tls12'):
                    f=next(e['finding'] for e in self.entries if e['label']==label);self.process_checks.append(dict(stage=stage,slot=f['slot'],expectedPid=f['pid'],observedPid=str(f['pid']),shellUid=2000))
            self.wire=contract.validate_wire(self.host,self.entries,run=RUN,source=SOURCE);contract.validate_cross(self.entries,self.process_checks)
        finally:
            if self.server is not None and not self.server.closed:self.server.close()
            self.public=copy.deepcopy(self.certificates.public);self.certificates.close()
    def write(self,directory):
        directory=Path(directory);directory.mkdir(parents=True,exist_ok=True);records=[]
        for e in self.entries:
            name='case-'+e['label']+'.json';raw=(json.dumps(e['device'],sort_keys=True)+'\n').encode();(directory/name).write_bytes(raw);records.append({k:copy.deepcopy(e[k]) for k in ('label','binding','status','finding')}|dict(report=name,reportSha256=hashlib.sha256(raw).hexdigest()))
        install=dict(method='domain-scoped-user-ca',androidUser=0,ownerAndMode='644:1000:1000',selinuxContext='u:object_r:keystore_data_file:s0',subjectHashOld=self.public['subjectHashOld'],storePath='/data/misc/user/0/cacerts-added/'+self.public['subjectHashOld']+'.0',publicCaPemSha256=self.public['caPemSha256'],expectedLeafDerSha256=self.leaf,evidenceShellUid=2000,cleanupRootUid=0,cleanupShellUid=2000)
        install.update({k:True for k in ('adbRoot','selinuxEnforcing','installedPublicCaBytesMatch','appForceStoppedAfterInstall','removedAfterExecution','shellRestoredAfterInstall','shellRestoredAfterCleanup')})
        tls=dict(self.public,trustInstallation=install,guestPort=GUEST_PORT,privateMaterialRemoved=True,reverseRemoved=True,binding=dict(sourceCommit=SOURCE,sourceTree=TREE,runNonce=RUN,integrationApkSha256=self.identity['apkSha256'],sdkRunId='7',sdkRunAttempt='1'))
        result=dict(schema=1,kind='gecko-production-tls-v1',status='passed',diagnosticOnly=True,releaseAcceptance=False,sourceCommit=SOURCE,sourceTree=TREE,runId='7',runAttempt='1',runNonce=RUN,expectedBuildIdentity=self.identity,guest=dict(actualEmulator=True,api=35,onlineCpus=4,evidenceShellUid=2000),caseRecords=records,processChecks=self.process_checks,hostTls=tls,host=self.host,cleanup={k:True for k in ('appStopped','appDataCleared','reverseRemoved','serverClosed','serverThreadsJoined','caRemoved','privateMaterialRemoved','shellUidRestored')},errors=[],checked=self.wire,sourceFiles={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in checker.SOURCE_INPUTS},executionInputsUnchanged=True,actualAndroidExecution=True,actualGeckoExecution=True,productionGeckoWebTlsWorkloadPassed=True,persistentServiceWorkerTlsMeasured=True,workerCoverageVerified=False,serviceWorkerCoverageVerified=False,fullTlsFingerprintEmulation=False,quicWireVerified=False,rawFatalAlertPacketDecoded=False,appIndependentTlsStacksCovered=False,scope='SYNTHETIC ANDROID METADATA FOR HOST VALIDATOR CONTROLS ONLY; real sockets use host OpenSSL, not Gecko or Service Workers.')
        (directory/'results.json').write_text(json.dumps(result,sort_keys=True)+'\n');return copy.deepcopy(result)
