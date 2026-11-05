"""Synthetic device/setup metadata plus real local OpenSSL/IP-fixture receipts.

The model packet's Android flags are only input to the actual strict validators.
They never constitute Android/Gecko execution evidence. Only the installed SDK
verification boundary is replaced with an exact typed model-identity comparison.
"""
import copy
import hashlib
import json
from pathlib import Path
import re
import socket
import ssl
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
sys.path.insert(0, str(ROOT / 'tools/browser'))
sys.path.insert(0, str(ROOT / 'tools/gecko'))
import gecko_cpu_ip_combo_evidence_test as old_model
import tls_cpu_ip_combo_contract as contract
import tls_acceptance_contract as tls
from ip_timezone_fixture_server import IpFixtureCertificates, IpTimeZoneFleet, GEO_HOST, GEO_TARGET, exact_bytes
from tls_cpu_ip_combo_server import TlsCpuIpCapture


def model_identity_equal(actual, expected):
    if not tls.equal(actual, expected):
        raise ValueError('Explicit synthetic installed identity differs')


class HostComboModelEvidence:
    """No emulator/ADB is invoked; process/native/CA-install metadata is modeled."""
    def __init__(self, identity, source, tree, run):
        if identity.get('sourceCommit') != source or identity.get('sourceTree') != tree:
            raise ValueError('Explicit model source tuple differs')
        self.identity = copy.deepcopy(identity)
        self.source, self.tree, self.run = source, tree, run
        self.actualAndroidExecution = self.actualGeckoExecution = False
        self.scope = 'SYNTHETIC DEVICE/SETUP/PROCESS/TRUST METADATA; real host localhost OpenSSL only'
        previous, _ = old_model.fixture()
        self.device = copy.deepcopy(previous['activity'])
        self.device.update(fixtureType=contract.FIXTURE_TYPE, activityClass=contract.ACTIVITY,
            sourceCommit=source, sourceTree=tree, runNonce=run, buildIdentity=copy.deepcopy(identity))
        self.device['page'].update(sourceCommit=source, runNonce=run)
        engine_source = (ROOT / 'app/src/main/java/local/pocketchat/GeckoWebView.java').read_text()
        engines = re.findall(r'^\s*static final String VERSION=("(?:[^"\\]|\\.)*");', engine_source, re.M)
        if len(engines) != 1:
            raise ValueError('Unique current modeled engine tuple required')
        self.engine = json.loads(engines[0])
        self.device['native']['receipt']['binding']['engineVersion'] = self.engine
        owner = self.device['native']['identity']; pid = self.device['process']['pid']
        setup = copy.deepcopy(previous['prelaunchSetup'])
        setup.update(sourceCommit=source, sourceTree=tree, runNonce=run,
            integrationApkSha256=identity['apkSha256'])
        self.device['setup'] = dict(copy.deepcopy(setup), actualDefaultStoreLoadYet=True,
            defaultSpec=dict(schema=2, engine='gecko', mode='ip', zoneId=''),
            defaultRevision=1, loadedIdentity=copy.deepcopy(owner))
        self.device['tlsSetup'] = dict(tlsSealedRecordMissingBefore=True,
            actualColdStoreSave=True, loadedMode='default', loadedRevision=1,
            savedMode='tls13', savedRevision=2, identity=copy.deepcopy(owner), sessionAbsentBeforeSetup=True)
        self.device['tlsStoredState'] = dict(identity=copy.deepcopy(owner), revision=2,
            spec=dict(schema=1, engine='gecko', mode='tls13'))
        policy = dict(schema=1, engine='gecko', desiredRevision=2, desiredMode='tls13',
            activeBootRevision=2, activeBootMode='tls13', state='ready', issue='',
            failureCode='', pendingColdStart=False, defaultMin=4, defaultMax=4,
            configuredMin=4, configuredMax=4, hasUserMin=False, hasUserMax=False,
            rfpPriority=False, h2Enabled=True, h3Enabled=True, nativeSettingReadback=True,
            startupReconciled=True, scope='runtime-wide', processNonce='9'*32,
            pid=pid, runtimeNonce='8'*32, environmentId=owner['environmentId'],
            environmentGeneration=owner['generation'], slot=6, wireObservationVerified=False,
            fullTlsFingerprintEmulation=False, quicWireVerified=False,
            persistentWorkerColdStartVerified=False, connectionScope='gecko-web-connections',
            independentDownloaderTlsCovered=False, connectionCheckTlsCovered=False, proxyEntranceTlsCovered=False)
        self.device['tlsPolicy'] = policy
        self.device['runtimeTlsPolicy'] = copy.deepcopy(policy)
        self.device['freshTlsReadback'] = dict(configuredMin=4, configuredMax=4,
            defaultMin=4, defaultMax=4, hasUserMin=False, hasUserMax=False,
            rfpPriority=False, h2Enabled=True, h3Enabled=True)
        self.device['startupPreparation'] = dict(schema=1, status='verified',
            scope='offline-two-owned-tls-preferences', mode='tls13', profileBytesBefore=100,
            profileBytesAfter=100, removedOwnedBytes=0, nonTlsPrefsBeforeSha256='a'*64,
            nonTlsPrefsAfterSha256='a'*64, nonTlsPrefsBytePreserved=True,
            closedRouteConfigPrefixPreserved=True, configBeforeSha256='b'*64, configAfterSha256='c'*64)
        self.device['runtimeBinding'] = dict(pid=pid, currentSessionIsCaptured=True,
            displayedRuntimeIsCaptured=True, cpuReadyForCapturedRuntime=True,
            tlsReadyForCapturedRuntime=True, navigationEpoch=1, documentSerial=0,
            contextId=self.device['native']['contextId'], sessionId=self.device['native']['sessionId'],
            cpuRuntimeNonce=self.device['cpuPolicy']['runtimeNonce'], tlsRuntimeNonce=policy['runtimeNonce'])
        self.device['navigation'] = dict(targetStarted=True, targetLocation=True,
            titleMatched=True, targetRequestObserved=True, productionAdmissionReady=True,
            stopUsedAsCompletionOracle=False)
        self.device['nativeEvents'][1]['targetOwned'] = False # Native stop carries no URI.
        self.device['checks'] = [dict(id=name, **{'pass':True}) for name in contract.CHECKS]
        self.device.update(fullTlsFingerprintEmulation=False, quicWireVerified=False,
            rawFatalAlertPacketDecoded=False, appIndependentTlsStacksCovered=False)
        sdk = identity['sdkBuildIdentity']
        self.binding = dict(sourceCommit=source, sourceTree=tree, runNonce=run,
            integrationApkSha256=identity['apkSha256'], sdkRunId=sdk['runId'], sdkRunAttempt=sdk['runAttempt'])
        self.certificates = IpFixtureCertificates()
        fleet = None
        try:
            capture = TlsCpuIpCapture(self.certificates, self.binding)
            fleet = IpTimeZoneFleet(self.certificates,
                (ROOT / 'tests/gecko/assets/worker-policy-page.js').read_text(),
                (ROOT / 'tests/gecko/assets/tls-cpu-ip-combo-page.js').read_text(), self.binding).start()
            fleet.control(dict(sourceCommit=source, runNonce=run, action='stage', case='default-socks'))
            context = ssl.create_default_context(cafile=str(self.certificates.ca))
            context.minimum_version = context.maximum_version = ssl.TLSVersion.TLSv1_3
            context.set_alpn_protocols(['h2', 'http/1.1'])
            def request(host, path):
                raw = socket.create_connection(('127.0.0.1', fleet.proxies['socks'].port), timeout=5)
                try:
                    raw.sendall(b'\x05\x01\x00')
                    if exact_bytes(raw, 2) != b'\x05\x00': raise ValueError('Actual model SOCKS greeting failed')
                    name = host.encode('ascii')
                    raw.sendall(bytes([5,1,0,3,len(name)])+name+b'\x01\xbb')
                    if exact_bytes(raw, 10)[:2] != b'\x05\x00': raise ValueError('Actual model SOCKS connect failed')
                    channel = context.wrap_socket(raw, server_hostname=host); raw = channel
                    if channel.version() != 'TLSv1.3' or channel.selected_alpn_protocol() != 'http/1.1' or channel.session_reused:
                        raise ValueError('Actual model TLS peer failed')
                    channel.sendall(('GET '+path+' HTTP/1.1\r\nHost: '+host+'\r\n\r\n').encode('ascii'))
                    response = bytearray()
                    while True:
                        block = channel.recv(65536)
                        if not block: break
                        response.extend(block)
                        if len(response) > 131072: raise ValueError('Actual model response exceeded bound')
                    head, separator, body = bytes(response).partition(b'\r\n\r\n')
                    if not head.startswith(b'HTTP/1.1 200 OK') or not separator: raise ValueError('Actual model HTTP failed')
                    return body
                finally:
                    raw.close()
            expected_geo = dict(success=True, ip='8.8.8.8', timezone={'id':'America/New_York'})
            if json.loads(request(GEO_HOST, GEO_TARGET)) != expected_geo: raise ValueError('Actual synthetic geo body differs')
            if b'data-gecko-cpu-ip-combo' not in request('fp-a.pocketchat.test', '/env-policy?phase=gecko-new-york'):
                raise ValueError('Actual combined source page absent')
            marker = '/worker-probe?phase=gecko-new-york&realm=document&documentId='+self.device['page']['documentId']
            if request('fp-a.pocketchat.test', marker) != b'worker-network-synthetic-v1':
                raise ValueError('Actual same-document marker response differs')
            request('fp-a.pocketchat.test', '/env-frame?phase=gecko-new-york')
            request('fp-b.pocketchat.test', '/env-frame?phase=gecko-new-york')
            request('fp-a.pocketchat.test', '/favicon.ico')
            fleet.close()
            self.wire = capture.snapshot(fleet)
            routes = fleet.snapshot()
            self.public = copy.deepcopy(self.certificates.public)
        finally:
            if fleet is not None and not fleet.closed:
                fleet.close()
            self.certificates.close()
        if self.certificates.directory.exists(): raise ValueError('Actual private material cleanup failed')
        self.device['tls'] = dict(host='fp-a.pocketchat.test', isSecure=True, isException=False,
            leafDerSha256=routes['leafDerSha256'], enterpriseRootsReadback=True)
        install = dict(method='domain-scoped-user-ca', androidUser=0, adbRoot=True,
            selinuxEnforcing=True, installedPublicCaBytesMatch=True, ownerAndMode='644:1000:1000',
            selinuxContext='u:object_r:keystore_data_file:s0', subjectHashOld=self.public['subjectHashOld'],
            appForceStoppedAfterInstall=True, publicCaPemSha256=self.public['caPemSha256'],
            expectedLeafDerSha256=self.public['leafDerSha256'], evidenceShellUid=2000,
            shellRestoredAfterInstall=True, removedAfterExecution=True, cleanupRootUid=0,
            cleanupShellUid=2000, shellRestoredAfterCleanup=True)
        trust = dict(self.public, binding=copy.deepcopy(self.binding), privateMaterialRemoved=True,
            trustInstallation=install)
        sample = dict(schema=1, sourceCommit=source, sourceTree=tree, runNonce=run, slot=6,
            processName=self.device['process']['name'], expectedPid=pid, observedPid=str(pid), shellUid=2000)
        self.original_bytes = (json.dumps(self.device, indent=1, sort_keys=True)+'\n').encode()
        self.envelope = dict(schema=1, label='combined-cpu-ip-tls13', status='passed',
            report=contract.CASE_FILE, reportSha256=hashlib.sha256(self.original_bytes).hexdigest(),
            prelaunchSetup=setup, processSample=sample, routeReceipts=routes, hostTls=trust,
            systemTimeZone=dict(before='UTC', after='UTC'), wire=copy.deepcopy(self.wire),
            cleanup=dict(appStopped=True, scopeCleared=True, reverseRemoved=True, caRemoved=True,
                privateMaterialRemoved=True, serverQuiesced=True, appDataCleared=True, shellUidRestored=True))
        with patch.object(tls, 'verify_installed', side_effect=model_identity_equal):
            self.finding = contract.validate_combo(self.device, self.envelope, source=source,
                expected=self.identity, run=run, engine=self.engine)
