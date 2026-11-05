#!/usr/bin/env python3
"""Actual combined validators against synthetic device + real local TLS inputs."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import shlex
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'tests'), str(ROOT/'tools/gecko'), str(ROOT/'tools/browser')]
from tls_cpu_ip_combo_test_support import HostComboModelEvidence, model_identity_equal
from tls_product_test_support import model_identity, SOURCE, TREE, RUN
import tls_acceptance_contract as tls
import tls_cpu_ip_combo_contract as contract
import run_gecko_tls_cpu_ip_combo as runner
from native_tls_probe_server import Cursor, parse_client_hello

NEGATIVES = []
MUTANTS = []
REAL_TRANSPORT_EXECUTED = False
SOURCE_INPUTS = (
    'tests/tls_cpu_ip_combo_test_support.py', 'tests/gecko_tls_cpu_ip_combo_test.py',
    'tools/gecko/tls_cpu_ip_combo_contract.py', 'tools/gecko/tls_cpu_ip_combo_server.py',
    'tools/gecko/run_gecko_tls_cpu_ip_combo.py', 'tools/gecko/profile_invocation_contract.py',
    'tools/gecko/tls_acceptance_contract.py', 'tests/tls_product_test_support.py',
    'tools/browser/check_gecko_cpu_ip_combo_evidence.py', 'tools/browser/check_gecko_ip_timezone_evidence.py',
    'tools/browser/ip_timezone_fixture_server.py', 'tools/browser/newworker_fixture_server.py',
    'tools/browser/native_tls_probe_server.py', 'tools/browser/fingerprint_fixture_server.py',
    'tests/gecko_cpu_ip_combo_evidence_test.py', 'tests/gecko_ip_timezone_evidence_test.py',
    'tests/gecko_environment_policy_evidence_test.py', 'tests/browser_fingerprint_evidence_test.py',
    'tests/profile_sdk_identity_test.py', 'tests/gecko/assets/worker-policy-page.js',
    'tests/gecko/assets/tls-cpu-ip-combo-page.js', 'app/src/main/java/local/pocketchat/GeckoWebView.java')


def source_hashes():
    return {name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in SOURCE_INPUTS}


def mutate_hello(hello, *, extension=None, versions=None):
    """Counterfeit derived from original bytes, reparsed before testing guards."""
    raw = bytes.fromhex(hello['clientHelloHandshakeHex'])
    body = Cursor(raw[4:]); body.take(2+32); body.vector(1); body.vector(2); body.vector(1)
    prefix = body.raw[:body.at]; extensions = Cursor(body.vector(2)); body.done()
    output = bytearray()
    while extensions.at < len(extensions.raw):
        kind, value = extensions.number(2), extensions.vector(2)
        if kind == 43 and versions is not None:
            vector = b''.join(v.to_bytes(2,'big') for v in versions)
            value = len(vector).to_bytes(1,'big')+vector
        output.extend(kind.to_bytes(2,'big')+len(value).to_bytes(2,'big')+value)
    if extension is not None:
        kind, value = extension
        output.extend(kind.to_bytes(2,'big')+len(value).to_bytes(2,'big')+value)
    body = prefix+len(output).to_bytes(2,'big')+output
    handshake = b'\x01'+len(body).to_bytes(3,'big')+body
    records = b''.join(b'\x16\x03\x01'+len(part).to_bytes(2,'big')+part for part in (handshake[i:i+16384] for i in range(0,len(handshake),16384)))
    return parse_client_hello(records)


def corrupt_original_hello(hello):
    raw=bytearray.fromhex(hello['clientHelloHandshakeHex']);raw[-1]^=1
    hello['clientHelloHandshakeHex']=raw.hex()


class CombinedValidatorControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        global REAL_TRANSPORT_EXECUTED
        identity = model_identity(); identity.update(version='2.1.4', versionCode=106)
        cls.model = HostComboModelEvidence(identity, SOURCE, TREE, RUN)
        REAL_TRANSPORT_EXECUTED = True

    def packet(self):
        return copy.deepcopy(self.model.device), copy.deepcopy(self.model.envelope)

    def validate(self, device, envelope, module=contract, **changes):
        values = dict(source=SOURCE, expected=self.model.identity, run=RUN, engine=self.model.engine)
        values.update(changes)
        with patch.object(tls, 'verify_installed', side_effect=model_identity_equal):
            return module.validate_combo(device, envelope, **values)

    def reject(self, name, change, *, module=contract):
        device, envelope = self.packet(); change(device, envelope)
        with self.subTest(name=name):
            with self.assertRaises((ValueError, KeyError, TypeError, AssertionError)):
                self.validate(device, envelope, module)
            NEGATIVES.append(name)

    def test_real_wire_and_actual_validators_preserve_explicit_model_boundary(self):
        device, envelope = self.packet(); before = copy.deepcopy((device,envelope))
        finding = self.validate(device, envelope)
        self.assertEqual((device,envelope), before)
        self.assertEqual(finding, self.model.finding)
        self.assertEqual(finding['slot'],6); self.assertEqual(finding['pageHardwareConcurrency'],1)
        self.assertEqual(finding['pageTimeZone'],'America/New_York')
        self.assertEqual(finding['actualProtocol'],'TLSv1.3'); self.assertEqual(finding['freshWireConnections'],4)
        self.assertEqual(device['runtimeBinding']['documentSerial'],0) # Actual initial TimeZoneGate serial.
        self.assertFalse(self.model.actualAndroidExecution or self.model.actualGeckoExecution)
        for key in ('workerCoverageVerified','serviceWorkerCoverageVerified','fullTlsFingerprintEmulation','quicWireVerified','actualPublicIpGeolocationVerified'):
            self.assertFalse(finding[key])
        self.assertEqual(hashlib.sha256(self.model.original_bytes).hexdigest(), envelope['reportSha256'])
        self.assertEqual(json.loads(self.model.original_bytes), device)
        self.assertFalse(self.model.certificates.directory.exists())
        self.assertEqual([r['path'] for r in self.model.wire['records']], ['/env-policy','/worker-probe','/env-frame','/favicon.ico'])

    def test_fresh_missing_default_and_three_durable_cold_choices_are_required(self):
        cases = {
            'manual seed cannot stand in for missing IP':lambda d,e:e['prelaunchSetup'].update(manualSeedAppliedToIpScope=True),
            'preexisting timezone record':lambda d,e:e['prelaunchSetup'].update(timezoneSealedRecordMissing=False),
            'scope admitted after profile use':lambda d,e:e['prelaunchSetup'].update(scopeBeforeAnyProfileAccess=False),
            'scope reused old slot':lambda d,e:e['prelaunchSetup'].update(unusedSlotBeforeSetup=False),
            'setup loader ran early':lambda d,e:e['prelaunchSetup'].update(actualDefaultStoreLoadYet=True),
            'fake Profiles preparation':lambda d,e:e['prelaunchSetup'].update(actualProfilesPrepare=False),
            'custom timezone saved':lambda d,e:d['setup']['defaultSpec'].update(mode='system'),
            'old timezone revision':lambda d,e:d['setup'].update(defaultRevision=2),
            'wrong scope allocator':lambda d,e:d.update(scopeAllocationActivity=contract.ACTIVITY),
            'CPU record was not missing':lambda d,e:d['cpuSetup'].update(cpuSealedRecordMissingBefore=False),
            'CPU save after native session':lambda d,e:d['cpuSetup'].update(sessionAbsentBeforeSetup=False),
            'CPU desired was not cold saved':lambda d,e:d['cpuSetup'].update(actualColdStoreSave=False),
            'CPU durable revision old':lambda d,e:d['cpuStoredState'].update(revision=1),
            'CPU automatic desired':lambda d,e:d['cpuStoredState']['spec'].update(mode='automatic'),
            'TLS record was not missing':lambda d,e:d['tlsSetup'].update(tlsSealedRecordMissingBefore=False),
            'TLS saved after native session':lambda d,e:d['tlsSetup'].update(sessionAbsentBeforeSetup=False),
            'TLS hot save substituted':lambda d,e:d['tlsSetup'].update(actualColdStoreSave=False),
            'TLS durable revision old':lambda d,e:d['tlsStoredState'].update(revision=1),
            'TLS desired default':lambda d,e:d['tlsStoredState']['spec'].update(mode='default'),
        }
        for name, change in cases.items(): self.reject(name, change)

    def test_first_inline_cpu_date_and_marker_cannot_be_replaced_by_ack(self):
        cases = {
            'CPU page greater than one':lambda d,e:d['page'].update(hardwareConcurrency=2),
            'CPU Boolean one':lambda d,e:d['page'].update(hardwareConcurrency=True),
            'script overrides getter':lambda d,e:d['page'].update(nativeGetter=False),
            'late document observation':lambda d,e:d['page'].update(firstInline=False),
            'insecure document':lambda d,e:d['page'].update(secure=False),
            'wrong Intl zone':lambda d,e:d['page']['nativeTimeZone'].update(timeZone='UTC'),
            'January wrong local hour':lambda d,e:d['page']['nativeTimeZone']['january'].update(hour=12),
            'July missing DST':lambda d,e:d['page']['nativeTimeZone']['july'].update(offsetMinutes=300),
            'Date string offset':lambda d,e:d['page']['nativeTimeZone']['january'].update(offsetMinutes='300'),
            'foreign first-inline origin':lambda d,e:d['page'].update(origin='https://fp-b.pocketchat.test'),
            'malformed document ID':lambda d,e:d['page'].update(documentId='f'*36),
            'marker still pending':lambda d,e:d['page'].update(markerComplete=False),
            'network marker denied':lambda d,e:d['page'].update(networkAllowed=False),
            'JS TLS override invented':lambda d,e:d.update(javascriptTlsOverrideUsed=True),
        }
        for name, change in cases.items(): self.reject(name, change)

    def test_sdk_native_cpu_tls_and_no_user_readback_are_independent(self):
        cases = {
            'CPU fresh configured cap wrong':lambda d,e:d['freshCpuReadback'].update(configuredCap=2),
            'CPU fresh USER override':lambda d,e:d['freshCpuReadback'].update(hasUserValue=True),
            'CPU runtime changed':lambda d,e:d['runtimeCpuPolicy'].update(runtimeNonce='7'*32),
            'CPU boot desired differs':lambda d,e:d['cpuPolicy'].update(activeBootMode='automatic'),
            'CPU ACK is not ready':lambda d,e:d['cpuPolicy'].update(nativeSettingReadback=False),
            'TLS readback minimum admits12':lambda d,e:d['freshTlsReadback'].update(configuredMin=3),
            'TLS readback maximum string':lambda d,e:d['freshTlsReadback'].update(configuredMax='4'),
            'TLS fresh USER override':lambda d,e:d['freshTlsReadback'].update(hasUserMin=True),
            'TLS fresh RFP null':lambda d,e:d['freshTlsReadback'].update(rfpPriority=None),
            'TLS fresh H2 disabled':lambda d,e:d['freshTlsReadback'].update(h2Enabled=False),
            'TLS fresh H3 disabled':lambda d,e:d['freshTlsReadback'].update(h3Enabled=False),
            'TLS native ACK false':lambda d,e:d['tlsPolicy'].update(nativeSettingReadback=False),
            'TLS startup not reconciled':lambda d,e:d['tlsPolicy'].update(startupReconciled=False),
            'TLS native USER override':lambda d,e:d['tlsPolicy'].update(hasUserMax=True),
            'TLS boot mode default':lambda d,e:d['tlsPolicy'].update(activeBootMode='default'),
            'TLS queued cold save':lambda d,e:d['tlsPolicy'].update(pendingColdStart=True),
            'TLS old desired revision':lambda d,e:d['tlsPolicy'].update(desiredRevision=1),
            'TLS runtime changed':lambda d,e:d['runtimeTlsPolicy'].update(runtimeNonce='7'*32),
            'TLS parser changed nonowned prefs':lambda d,e:d['startupPreparation'].update(nonTlsPrefsAfterSha256='f'*64),
            'TLS removed CPU route prefix':lambda d,e:d['startupPreparation'].update(closedRouteConfigPrefixPreserved=False),
            'TLS runtime file masquerades as preboot':lambda d,e:d['startupPreparation'].update(scope='runtime-snapshot'),
        }
        for name, change in cases.items(): self.reject(name, change)

    def test_same_owner_pid_runtime_session_context_and_document_fences(self):
        cases = {
            'foreign UUID':lambda d,e:d['tlsStoredState']['identity'].update(environmentId='00000000-0000-0000-0000-000000000005'),
            'foreign generation':lambda d,e:d['cpuStoredState']['identity'].update(generation=2),
            'wrong slot process':lambda d,e:d['process'].update(name='local.pocketchat.test:profile1'),
            'shell substituted for app UID':lambda d,e:d['process'].update(uid=2000),
            'mixed shell PID':lambda d,e:e['processSample'].update(observedPid='7711 7712'),
            'shell ran as root':lambda d,e:e['processSample'].update(shellUid=0),
            'foreign runtime PID':lambda d,e:d['runtimeBinding'].update(pid=7712),
            'old captured Main session':lambda d,e:d['runtimeBinding'].update(currentSessionIsCaptured=False),
            'old displayed runtime':lambda d,e:d['runtimeBinding'].update(displayedRuntimeIsCaptured=False),
            'CPU ready for another runtime':lambda d,e:d['runtimeBinding'].update(cpuReadyForCapturedRuntime=False),
            'TLS ready for another runtime':lambda d,e:d['runtimeBinding'].update(tlsReadyForCapturedRuntime=False),
            'late native context callback':lambda d,e:d['runtimeBinding'].update(contextId='999'),
            'late SDK session callback':lambda d,e:d['runtimeBinding'].update(sessionId='old-session'),
            'old CPU boot incarnation':lambda d,e:d['runtimeBinding'].update(cpuRuntimeNonce='7'*32),
            'old TLS boot incarnation':lambda d,e:d['runtimeBinding'].update(tlsRuntimeNonce='7'*32),
            'negative document serial':lambda d,e:d['runtimeBinding'].update(documentSerial=-1),
            'Boolean document serial':lambda d,e:d['runtimeBinding'].update(documentSerial=True),
            'negative navigation epoch':lambda d,e:d['runtimeBinding'].update(navigationEpoch=-1),
            'late TZ context receipt':lambda d,e:d['native']['receipt']['binding'].update(contextId='999'),
            'fresh TZ read borrowed apply':lambda d,e:d['native']['freshReadback'].update(requestToken=d['native']['receipt']['requestToken']),
            'old route stamp':lambda d,e:d['native']['receipt']['ipObservation'].update(routeStamp='7'*64),
            'old native event session':lambda d,e:d['nativeEvents'][0].update(sessionId='foreign'),
            'stop pretends native target URI':lambda d,e:d['nativeEvents'][1].update(targetOwned=True),
            'no actual native start':lambda d,e:d['nativeEvents'][0].update(targetOwned=False),
        }
        for name, change in cases.items(): self.reject(name, change)

    def test_actual_runner_strict_original_parser_rejects_before_old_nonce_drop(self):
        original = self.model.original_bytes
        with patch.object(runner, 'verify_installed', side_effect=model_identity_equal):
            self.assertEqual(runner.read_activity(original,SOURCE,RUN,self.model.identity),self.model.device)
            old = copy.deepcopy(self.model.device); old['runNonce']='f'*32
            old_raw = json.dumps(old).encode()
            self.assertIsNone(runner.read_activity(old_raw,SOURCE,RUN,self.model.identity))
            for raw in (b'',b'  ',b'Error: unavailable',b'No result found.',b'Error while accessing provider: unavailable'):
                self.assertIsNone(runner.read_activity(raw,SOURCE,RUN,self.model.identity))
            cases = {
                'old nonce duplicate top key':b'{"runNonce":"'+b'f'*32+b'",'+old_raw[1:],
                'old nonce duplicate nested key':old_raw.replace(b'"buildIdentity": {',b'"buildIdentity": {"schema": 1,',1),
                'old nonce nonfinite':old_raw[:-1]+b',"invalid":NaN}',
                'oversized original':b' '*(262144+1),
                'non UTF8 original':b'\xff',
            }
            for name, value in (('typed nonce Boolean',True),('typed nonce number',12),('typed nonce null',None),('short nonce','f'*31),('nonce unknown alphabet','z'*32)):
                packet=copy.deepcopy(self.model.device);packet['runNonce']=value;cases[name]=json.dumps(packet).encode()
            for name, mutate in (
                ('runner wrong source',lambda d:d.update(sourceCommit='f'*40)),
                ('runner wrong tree',lambda d:d.update(sourceTree='f'*40)),
                ('runner wrong APK',lambda d:d['buildIdentity'].update(apkSha256='f'*64)),
                ('runner old version',lambda d:d['buildIdentity'].update(versionCode=105)),
                ('runner old SDK attempt',lambda d:d['buildIdentity']['sdkBuildIdentity'].update(runAttempt='2')),
                ('runner Boolean schema',lambda d:d.update(schema=True))):
                packet=copy.deepcopy(self.model.device);mutate(packet);cases[name]=json.dumps(packet).encode()
            for name, raw in cases.items():
                with self.subTest(name=name),self.assertRaises((ValueError,KeyError,TypeError,UnicodeError)):
                    runner.read_activity(raw,SOURCE,RUN,self.model.identity)
                NEGATIVES.append(name)

    def test_actual_runner_scope_commands_are_exact_and_shell_quoted(self):
        for action in ('prepare','clear'):
            command=runner.scope_command(action,SOURCE,RUN)
            self.assertEqual(command[0],'shell')
            self.assertEqual(shlex.split(command[1]),['content','call','--uri',
                'content://local.pocketchat.test.gecko-tls-cpu-ip-combo-evidence','--method',action,
                '--extra','sourceCommit:s:'+SOURCE,'--extra','runNonce:s:'+RUN])
            self.assertNotIn('slot',command[1]) # This provider's declared purpose is profile6 only.
        for name, args in (
            ('unknown scope method',('prepareManual',SOURCE,RUN)),
            ('scope source injection',('prepare',SOURCE+';echo BAD',RUN)),
            ('scope nonce injection',('clear',SOURCE,RUN+'$(echo BAD)')),
            ('scope short source',('prepare','a'*39,RUN))):
            with self.subTest(name=name),self.assertRaises((ValueError,TypeError)):
                runner.scope_command(*args)
            NEGATIVES.append(name)

    def test_actual_runner_early_adb_failure_runs_all_independent_cleanup_without_success(self):
        for failing_cleanup in (None,'appStopped','appDataCleared','shellUidRestored'):
            calls=[]
            def adb(*parts,**kwargs):
                calls.append(parts)
                if parts==('shell','getconf','_NPROCESSORS_ONLN'):
                    raise RuntimeError('Controlled prelaunch boundary, no Android execution')
                if parts==('shell','am','force-stop','local.pocketchat.test'):
                    if failing_cleanup=='appStopped':raise RuntimeError('Controlled app stop failure')
                    return types.SimpleNamespace(stdout=b'')
                if parts[:2]==('shell','pidof'):return types.SimpleNamespace(stdout=b'')
                if parts==('shell','pm','clear','local.pocketchat.test'):
                    return types.SimpleNamespace(stdout=b'Failure' if failing_cleanup=='appDataCleared' else b'Success')
                if parts==('shell','id','-u'):
                    return types.SimpleNamespace(stdout=b'0' if failing_cleanup=='shellUidRestored' and len(calls)>1 else b'2000')
                raise AssertionError('Unexpected early-boundary ADB call '+repr(parts))
            with self.subTest(failing_cleanup=failing_cleanup), tempfile.TemporaryDirectory() as name:
                with patch.object(runner,'IpFixtureCertificates',side_effect=AssertionError('No network/TLS setup after early boundary')):
                    with self.assertRaises(runner.ComboFailure) as failed:
                        runner.run_combo(adb,Path(name),SOURCE,TREE,self.model.identity,RUN)
                envelope=failed.exception.envelope
                self.assertEqual(envelope['status'],'failed')
                self.assertIsNone(envelope['reportSha256'])
                self.assertEqual(envelope['wire'],{});self.assertEqual(envelope['routeReceipts'],{})
                self.assertFalse((Path(name)/contract.CASE_FILE).exists())
                self.assertIn(('shell','am','force-stop','local.pocketchat.test'),calls)
                self.assertIn(('shell','pm','clear','local.pocketchat.test'),calls)
                self.assertEqual(calls[-1],('shell','id','-u'))
                for key in ('appStopped','appDataCleared','shellUidRestored'):
                    self.assertEqual(envelope['cleanup'][key],key!=failing_cleanup)
                for key in ('scopeCleared','caRemoved','privateMaterialRemoved','serverQuiesced'):
                    self.assertFalse(envelope['cleanup'][key])
                NEGATIVES.append('actual finally never passes prelaunch failure: '+str(failing_cleanup))

    def test_native_exact_uri_title_admission_and_certificate_required(self):
        cases = {
            'no target native start':lambda d,e:d['navigation'].update(targetStarted=False),
            'no exact native URI':lambda d,e:d['navigation'].update(targetLocation=False),
            'no source nonce title':lambda d,e:d['navigation'].update(titleMatched=False),
            'no actual native request':lambda d,e:d['navigation'].update(targetRequestObserved=False),
            'request bypassed production admission':lambda d,e:d['navigation'].update(productionAdmissionReady=False),
            'stop used as document oracle':lambda d,e:d['navigation'].update(stopUsedAsCompletionOracle=True),
            'native certificate exception':lambda d,e:d['tls'].update(isException=True),
            'native certificate leaf changed':lambda d,e:d['tls'].update(leafDerSha256='f'*64),
            'native roots not read back':lambda d,e:d['tls'].update(enterpriseRootsReadback=False),
            'native wrong TLS host':lambda d,e:d['tls'].update(host='fp-b.pocketchat.test'),
        }
        for name, change in cases.items(): self.reject(name, change)

    def test_source_apk_sdk_run_attempt_and_false_scope_flags_are_bound(self):
        cases = {
            'sourceCommit old':lambda d,e:d.update(sourceCommit='f'*40),
            'sourceTree old':lambda d,e:d.update(sourceTree='f'*40),
            'runNonce old':lambda d,e:d.update(runNonce='f'*32),
            'setup source old':lambda d,e:e['prelaunchSetup'].update(sourceCommit='f'*40),
            'setup APK old':lambda d,e:e['prelaunchSetup'].update(integrationApkSha256='f'*64),
            'installed APK old':lambda d,e:d['buildIdentity'].update(apkSha256='f'*64),
            'installed source old':lambda d,e:d['buildIdentity'].update(sourceCommit='f'*40),
            'installed SDK run old':lambda d,e:d['buildIdentity']['sdkBuildIdentity'].update(runId='99'),
            'installed SDK attempt old':lambda d,e:d['buildIdentity']['sdkBuildIdentity'].update(runAttempt='2'),
            'old version105':lambda d,e:d['buildIdentity'].update(version='2.1.3',versionCode=105),
            'not actual Android input':lambda d,e:d.update(actualAndroidExecution=False),
            'not actual Gecko input':lambda d,e:d.update(actualGeckoExecution=False),
            'not production ChatSession':lambda d,e:d.update(productionChatSession=False),
            'raw private field':lambda d,e:d.update(rawPrivateData='not-allowed'),
            'Boolean schema':lambda d,e:d.update(schema=True),
            'missing original checks':lambda d,e:d['checks'].pop(),
            'failed original check':lambda d,e:d['checks'][0].update(**{'pass':False}),
        }
        for field in ('actualPublicIpGeolocationVerified','workerCoverageVerified','serviceWorkerCoverageVerified','fingerprintProtectionVerified','fullTlsFingerprintEmulation','quicWireVerified','rawFatalAlertPacketDecoded','appIndependentTlsStacksCovered'):
            cases['unsupported coverage '+field] = lambda d,e,field=field:d.update({field:True})
        for name, change in cases.items(): self.reject(name, change)

    def test_independent_geo_route_trust_cleanup_and_document_marker(self):
        cases = {
            'geo not written':lambda d,e:e['routeReceipts']['events'][0].update(responseWritten=False),
            'geo credential leak':lambda d,e:e['routeReceipts']['events'][0].update(credentialsPresent=True),
            'geo redirected':lambda d,e:e['routeReceipts']['events'][0].update(behavior='redirect',status=302),
            'geo response body differs':lambda d,e:e['routeReceipts']['events'][0].update(responseSha256='f'*64),
            'geo response wrong IP':lambda d,e:e['routeReceipts']['events'][0].update(syntheticIp='1.1.1.1'),
            'native receipt wrong IP':lambda d,e:d['native']['receipt']['ipObservation'].update(ip='1.1.1.1'),
            'geo source override':lambda d,e:e['routeReceipts'].update(productionEndpointOverride=True),
            'upstream forwarded':lambda d,e:e['routeReceipts'].update(upstreamConnections=1),
            'route collector live':lambda d,e:e['routeReceipts'].update(closed=False),
            'route rejected connection':lambda d,e:e['routeReceipts']['errors'].update(socks=1),
            'marker for old document':lambda d,e:e['routeReceipts']['events'][2].update(documentId='00000000-0000-0000-0000-000000000999'),
            'marker not written':lambda d,e:e['routeReceipts']['events'][2].update(responseWritten=False),
            'page wrong origin':lambda d,e:e['routeReceipts']['events'][1].update(host='fp-b.pocketchat.test',targetSni='fp-b.pocketchat.test'),
            'wrong proxy protocol':lambda d,e:e['routeReceipts']['events'][0].update(protocol='http-connect'),
            'bad CA readback':lambda d,e:e['hostTls']['trustInstallation'].update(installedPublicCaBytesMatch=False),
            'CA not removed':lambda d,e:e['hostTls']['trustInstallation'].update(removedAfterExecution=False),
            'private material not removed':lambda d,e:e['hostTls'].update(privateMaterialRemoved=False),
            'changed Android system zone':lambda d,e:e['systemTimeZone'].update(after='America/New_York'),
        }
        for field in self.model.envelope['cleanup']:
            cases['cleanup incomplete '+field] = lambda d,e,field=field:e['cleanup'].update({field:False})
        for name, change in cases.items(): self.reject(name, change)

    def test_true_wire_raw_reparse_no_psk_and_same_document_requests(self):
        cases = {
            'missing original wire':lambda d,e:e['wire']['records'].clear(),
            'parsed fields without original':lambda d,e:e['wire']['records'][0]['clientHello'].pop('clientHelloHandshakeHex'),
            'raw bytes changed':lambda d,e:corrupt_original_hello(e['wire']['records'][0]['clientHello']),
            'native ACK without real TLS':lambda d,e:e['wire']['records'][0].update(tlsNegotiated=False),
            'wrong wire version':lambda d,e:e['wire']['records'][0].update(negotiatedVersion='TLSv1.2'),
            'wrong wire ALPN':lambda d,e:e['wire']['records'][0].update(negotiatedAlpn='h2'),
            'session resumed':lambda d,e:e['wire']['records'][0].update(sessionReused=True),
            'wire no request':lambda d,e:e['wire']['records'][0].update(requestObserved=False),
            'wire no response':lambda d,e:e['wire']['records'][0].update(responseObserved=False),
            'old wire document':lambda d,e:e['wire']['records'][1].update(documentId='00000000-0000-0000-0000-000000000999'),
            'frame borrowed for marker':lambda d,e:e['wire']['records'][1].update(path='/env-frame',realm='frame',documentId=''),
            'auxiliary borrowed for page':lambda d,e:e['wire']['records'][0].update(path='/favicon.ico',realm='auxiliary',phase='',documentId=''),
            'wire collector live':lambda d,e:e['wire'].update(serverClosed=False),
            'wire thread not joined':lambda d,e:e['wire'].update(serverThreadsJoined=False),
            'wire overflow':lambda d,e:e['wire'].update(recordsOverflow=True),
            'wire rejected unexpected handshake':lambda d,e:e['wire'].update(rejectedHandshakes=1),
            'wire no actual capture':lambda d,e:e['wire'].update(actualWireCapture=False),
            'wire tickets enabled':lambda d,e:e['wire'].update(ticketsDisabled=False),
            'wire source old':lambda d,e:e['wire']['binding'].update(sourceCommit='f'*40),
            'wire APK old':lambda d,e:e['wire']['binding'].update(integrationApkSha256='f'*64),
            'wire SDK attempt old':lambda d,e:e['wire']['binding'].update(sdkRunAttempt='2'),
        }
        def duplicate_random(d,e): e['wire']['records'][1]['clientHello'] = copy.deepcopy(e['wire']['records'][0]['clientHello'])
        def psk(d,e): e['wire']['records'][0]['clientHello'] = mutate_hello(e['wire']['records'][0]['clientHello'],extension=(41,b''))
        def tls12(d,e): e['wire']['records'][0]['clientHello'] = mutate_hello(e['wire']['records'][0]['clientHello'],versions=[772,771])
        cases.update({'fresh random replay':duplicate_random,'raw PSK extension':psk,'raw ClientHello admits TLS12':tls12})
        for name, change in cases.items(): self.reject(name, change)

    def test_counterfeits_only_pass_after_compiling_out_the_exact_guard(self):
        original = Path(contract.__file__).read_text()
        fresh_line = next(line for line in original.splitlines(True) if line.startswith("    equal(activity['freshTlsReadback'],"))
        cleanup_line = next(line for line in original.splitlines(True) if line.startswith("    equal(report['cleanup'],"))
        scenarios = (
            ("page['hardwareConcurrency']==1", 'True', lambda d,e:d['page'].update(hardwareConcurrency=2), 'first-inline CPU guard'),
            ("ip.clock(page['nativeTimeZone'],'America/New_York');", '', lambda d,e:d['page']['nativeTimeZone'].update(timeZone='UTC'), 'Date/Intl guard'),
            (fresh_line, '', lambda d,e:d['freshTlsReadback'].update(configuredMin=3), 'fresh SDK TLS read guard'),
            ("equal(rb['contextId'],native['contextId'],'same captured native context');", '', lambda d,e:d['runtimeBinding'].update(contextId='999'), 'late native context guard'),
            ("hello['preSharedKeyOffered'] is False and ", '', lambda d,e:e['wire']['records'][0].update(clientHello=mutate_hello(e['wire']['records'][0]['clientHello'],extension=(41,b''))), 'raw no-PSK guard'),
            ("negotiatedVersion='TLSv1.3',", '', lambda d,e:e['wire']['records'][0].update(negotiatedVersion='TLSv1.2'), 'actual negotiated protocol guard'),
            ("equal(parse_client_hello(records_bytes),hello,'independent immutable ClientHello reparse')", 'None', lambda d,e:corrupt_original_hello(e['wire']['records'][0]['clientHello']), 'original byte reparse guard'),
            (cleanup_line, '', lambda d,e:e['cleanup'].update(caRemoved=False), 'final cleanup guard'),
        )
        for before, after, change, name in scenarios:
            with self.subTest(guard=name):
                self.assertEqual(original.count(before),1)
                d,e = self.packet(); self.validate(d,e); change(d,e)
                with self.assertRaises(ValueError): self.validate(d,e)
                module = types.ModuleType('actual_compiled_combo_guard_mutant')
                module.__file__ = contract.__file__
                exec(compile(original.replace(before,after,1),'<compiled-combo-semantic-mutant>','exec'),module.__dict__)
                self.assertEqual(self.validate(d,e,module)['label'],'combined-cpu-ip-tls13')
                MUTANTS.append(name)


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--output',type=Path)
    args = parser.parse_args(); before = source_hashes()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(CombinedValidatorControls)
    result = unittest.TextTestRunner(stream=sys.stderr,verbosity=2).run(suite)
    after = source_hashes(); passed = result.wasSuccessful() and before == after
    report = dict(schema=1,status='passed' if passed else 'failed',testsRun=result.testsRun,
        failures=len(result.failures),errors=len(result.errors),negativeControls=NEGATIVES,
        compiledSemanticMutants=MUTANTS,actualHostOpenSslExecution=REAL_TRANSPORT_EXECUTED,
        actualAndroidExecution=False,actualGeckoExecution=False,
        scope='Actual current combo/native/cpu/wire validators; synthetic device/setup/process/Android trust metadata; only installed SDK identity boundary modeled; real local OpenSSL transport',
        sourceFiles=before,executionInputsUnchanged=before==after)
    raw=json.dumps(report,indent=2,sort_keys=True)+'\n'
    if args.output:args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(raw)
    print(raw,end='');raise SystemExit(0 if passed else 1)


if __name__=='__main__':main()
