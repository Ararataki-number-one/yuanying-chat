"""Driver scheduler and fail-closed evidence controls. No device execution."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/gecko'))
import native_input_contract as C
import native_input_driver as D
from native_input_signature_fixture import signature_files


def receipt(purpose='qualification'):
    source, tree, nonce = 'a' * 40, 'b' * 40, 'c' * 32
    build = dict(schema=1, status='built', compileOnly=False, testOnly=True, sourceCommit=source, sourceTree=tree, runId='123', runAttempt='1',
                 packageName=C.SELF, targetPackage=C.TARGET, instrumentationTargetPackage=C.SELF,
                 instrumentation=C.SELF + '.NativeInputInstrumentation', protocols=C.PROTOCOLS,
                 inputs={name: C.sha((ROOT / name).read_bytes()) for name in C.INPUTS},
                 apkSha256='d' * 64, apkBytes=10, signerCertificateSha256='e' * 64)
    signature_files(build, C.sha((ROOT / C.SIGNATURE_VERIFIER).read_bytes()))
    request = dict(x=540, startY=1469, endY=567, targetPid='1234', expiresUptimeMs=21000,
                   targetByteProofSha256='f' * 64, targetApkPath='/data/app/test/base.apk', targetApkBytes=100)
    p = C.PROTOCOLS[purpose]; rows = []
    for i in range(21):
        at = 1000 + i * p['intervalMs']
        rows.append(dict(action=0 if i == 0 else 1 if i == 20 else 2, downTime=1000, plannedUptimeMs=at,
                         eventTime=at, callStartUptimeMs=at, callEndUptimeMs=at, x=540,
                         y=1469 + (567 - 1469) * i / 20, injected=True, accepted=True, cleanup=False, sync=i == 20, error=''))
    target = dict(sourceCommit=source, sourceTree=tree, dirtySource=False)
    value = dict(schema=1, status='passed', sourceCommit=source, sourceTree=tree, nonce=nonce,
                 gesture='baseline-scroll' if purpose == 'qualification' else 'formal-collapse', purpose=purpose,
                 packageName=C.SELF, targetPackage=C.TARGET, buildIdentity=copy.deepcopy(build),
                 driverApkSha256=build['apkSha256'], targetApkSha256='1' * 64,
                 signerCertificateSha256=build['signerCertificateSha256'], targetBuildIdentity=target,
                 targetBuildIdentityAfter=copy.deepcopy(target), targetPidBefore='1234', targetPidAfter='1234',
                 targetApkHashSource='preflight-installed-byte-proof', targetByteProofSha256='f' * 64,
                 targetApkPathBefore=request['targetApkPath'], targetApkPathAfter=request['targetApkPath'],
                 targetApkBytesBefore=100, targetApkBytesAfter=100, targetLastModifiedBefore=50,
                 targetLastModifiedAfter=50, targetLastUpdateBefore=40, targetLastUpdateAfter=40,
                 createdUptimeMs=480, startedUptimeMs=500, connectStartUptimeMs=700, connectEndUptimeMs=850, readyUptimeMs=900, startupMs=400, finishedUptimeMs=1400, expiresUptimeMs=21000,
                 trace=dict(startUptimeMs=1000, expiresUptimeMs=21000, **p, events=rows, error='', cleanup=None))
    kwargs = dict(build=build, purpose=purpose, nonce=nonce, gesture=value['gesture'], target_apk='1' * 64, request=request)
    return value, kwargs


class ContractControls(unittest.TestCase):
    def qualification(self, directory):
        value, kwargs = receipt(); build = kwargs['build']; nonce = value['nonce']
        for name, raw in signature_files(build, C.sha((ROOT / C.SIGNATURE_VERIFIER).read_bytes())).items():
            (directory / name).write_bytes(raw)
        (directory / 'native-input-driver-build.json').write_text(json.dumps(build))
        proof = dict(schema=1, status='verified-bytes', actualInstalledApkRead=True, compiledFileFallback=False,
                     retryPerformed=False, returnCode=0, transport='adb-shell-v2-no-pty-ranged',
                     dataSource='binary-stdout-destination-file', actualFileSha256='1' * 64, stdoutSha256='1' * 64,
                     expectedSha256='1' * 64, actualFileBytes=100, stdoutBytes=100, expectedBytes=100,
                     rangeBytes=4194304, installedApkPath='/data/app/test/base.apk',
                     ranges=[dict(index=0, offset=0, actualBytes=100, expectedBytes=100, returnCode=0,
                                  status='verified-length', sha256='2' * 64)])
        proof_raw = json.dumps(proof).encode(); proof_name = 'native-input-target-proof-' + nonce + '.json'
        (directory / proof_name).write_bytes(proof_raw)
        report = dict(actualAndroidGestures=[], actualAndroidGestureDeadlines=[], nativeInputDriver=dict(
            purpose='qualification', nonce=nonce, buildSha256=C.sha((directory / 'native-input-driver-build.json').read_bytes()),
            targetByteProofFile=proof_name, targetByteProofSha256=C.sha(proof_raw), receipts=[]))
        phases = []
        for phase in ('baseline', 'current'):
            item = copy.deepcopy(value); item['gesture'] = phase + '-scroll'; item['targetByteProofSha256'] = C.sha(proof_raw)
            request = copy.deepcopy(kwargs['request']); request['targetByteProofSha256'] = C.sha(proof_raw)
            name = 'native-input-' + nonce + '-' + item['gesture'] + '.json'
            raw = json.dumps(item).encode(); (directory / name).write_bytes(raw)
            report['nativeInputDriver']['receipts'].append(dict(file=name, sha256=C.sha(raw), gesture=item['gesture'], request=request))
            report['actualAndroidGestures'].append(dict(id=item['gesture'], x=540, startY=1469, endY=567))
            report['actualAndroidGestureDeadlines'].append(dict(id=item['gesture'], sampledElapsedMs=1000,
                sampledUptimeMs=1000, expiresElapsedMs=21000, expiresUptimeMs=21000))
            native = {key: True for key in ('sameNavigation', 'sameSession', 'sameSurface', 'sameUrl', 'windowFocused', 'webShown', 'surfaceShown', 'surfaceAttached')}
            native['browserPaused'] = False
            sample = dict(native=native, dom=dict(document=100 if phase == 'baseline' else 200, url='fixture/' + phase))
            phases.append(dict(phase=phase, outcome='passed', samples=[sample, copy.deepcopy(sample)],
                               nativeTouches=[dict(action=0, superHandled=True), dict(action=2, superHandled=True)],
                               domEvents=[dict(type='touchstart', trusted=True)]))
        scroll = dict(run=nonce, sourceCommit=build['sourceCommit'], actualAndroidFileRead=True, phases=phases)
        (directory / 'gecko-scroll-diagnostics.json').write_text(json.dumps(scroll))
        return report, scroll, build

    def test_complete_raw_qualification_and_legal_coalescing(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary); report, _, build = self.qualification(directory)
            result = C.verify_qualification(directory, report, build['sourceCommit'], lambda s, p: (ROOT / p).read_bytes(), '1' * 64, ('123', '1'))
            self.assertEqual(result['receiptCount'], 2)
            # The passive receiver may stop after its first real MOVE; no
            # requirement for nineteen individual deliveries or captured UP.

    def test_missing_raw_move_document_and_run_cannot_qualify(self):
        for scenario in ('missing-receipt', 'missing-proof', 'missing-move', 'changed-document', 'wrong-run', 'forged-signature'):
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary); report, scroll, build = self.qualification(directory)
                if scenario == 'missing-receipt': (directory / report['nativeInputDriver']['receipts'][0]['file']).unlink()
                if scenario == 'missing-proof': (directory / report['nativeInputDriver']['targetByteProofFile']).unlink()
                if scenario == 'missing-move': scroll['phases'][0]['nativeTouches'].pop()
                if scenario == 'changed-document': scroll['phases'][0]['samples'][1]['dom']['document'] += 1
                if scenario == 'forged-signature': (directory / 'native-input-driver-signature-stdout.log').write_text('not an actual signer')
                (directory / 'gecko-scroll-diagnostics.json').write_text(json.dumps(scroll))
                with self.assertRaises((ValueError, FileNotFoundError)):
                    C.verify_qualification(directory, report, build['sourceCommit'], lambda s, p: (ROOT / p).read_bytes(), '1' * 64,
                                           ('999', '1') if scenario == 'wrong-run' else ('123', '1'))

    def test_two_exact_protocols(self):
        for purpose in C.PROTOCOLS:
            value, kwargs = receipt(purpose); C.verify_receipt(value, **kwargs)
        self.assertEqual(C.PROTOCOLS['qualification']['durationMs'], 300)
        self.assertEqual(C.PROTOCOLS['formal-collapse']['durationMs'], 320)

    def test_reject_incomplete_replayed_late_and_unbound_receipts(self):
        changes = [lambda v: v.update(status='failed'), lambda v: v.update(nonce='0' * 32),
                   lambda v: v.update(targetPidAfter='999'), lambda v: v.update(targetLastUpdateAfter=41),
                   lambda v: v.update(signerCertificateSha256='0' * 64),
                   lambda v: v['trace']['events'].pop(1), lambda v: v['trace']['events'].append(copy.deepcopy(v['trace']['events'][-1])),
                   lambda v: v['trace']['events'][1].update(eventTime=1046, callStartUptimeMs=1046, callEndUptimeMs=1046),
                   lambda v: v['trace']['events'][1].update(callStartUptimeMs=1046, callEndUptimeMs=1046),
                   lambda v: v['trace']['events'][1].update(accepted=False),
                   lambda v: v['trace']['events'][1].update(downTime=1015),
                   lambda v: v['trace']['events'][1].update(plannedUptimeMs=1016),
                   lambda v: v['trace']['events'][20].update(sync=False),
                   lambda v: v['trace']['events'][1].update(sync=True),
                   lambda v: v['trace']['events'][20].update(callEndUptimeMs=22000),
                   lambda v: v['trace'].update(cleanup={'action': 3}),
                   lambda v: v['trace'].update(durationMs=1000),
                   lambda v: v['trace']['events'][1].update(y=100),
                   lambda v: v.update(targetApkHashSource='guessed')]
        for change in changes:
            value, kwargs = receipt(); change(value)
            with self.subTest(change=changes.index(change)), self.assertRaises((ValueError, KeyError)):
                C.verify_receipt(value, **kwargs)

    def test_build_uses_exact_selected_java_and_self_target(self):
        _, kwargs = receipt(); build = kwargs['build']
        reader = lambda source, name: (ROOT / name).read_bytes()
        C.verify_build(build, build['sourceCommit'], reader)
        bad = copy.deepcopy(build); bad['instrumentationTargetPackage'] = C.TARGET
        with self.assertRaises(ValueError): C.verify_build(bad, build['sourceCommit'], reader)
        bad = copy.deepcopy(build); bad['inputs'][next(iter(C.INPUTS))] = '0' * 64
        with self.assertRaises(ValueError): C.verify_build(bad, build['sourceCommit'], reader)
        bad = copy.deepcopy(build); bad['signatureVerifierSourceSha256'] = '0' * 64
        with self.assertRaises(ValueError): C.verify_build(bad, build['sourceCommit'], reader)

    def test_signature_api_rejects_semantic_substitution_even_with_rebound_file_hashes(self):
        changes = [lambda v: v.update(verified=False), lambda v: v.update(containsErrors=True),
                   lambda v: v.update(inputsUnchangedDuringVerification=False),
                   lambda v: v.pop('inputsUnchangedDuringVerification'),
                   lambda v: v.update(sourceCommit='0' * 40), lambda v: v.update(runId='999'),
                   lambda v: v.update(apkSha256='0' * 64), lambda v: v.update(apkBytes=11),
                   lambda v: v.update(apksignerJarSha256='0' * 64),
                   lambda v: v.update(loadedApksignerJarPath='shadow/apksigner.jar'),
                   lambda v: v.update(verifierSourceSha256='0' * 64),
                   lambda v: v.update(effectiveSignerCertificateSha256=['e' * 64, 'e' * 64]),
                   lambda v: v.update(lineagePresent=True, lineageCertificateSha256=['e' * 64]),
                   lambda v: v.update(ignoredV1SignerCertificateSha256=['e' * 64]),
                   lambda v: v.update(v32Detected=True),
                   lambda v: v['schemes'][0].update(signerCertificateSha256=['e' * 64]),
                   lambda v: v['schemes'][2].update(signerCertificateSha256=['f' * 64]),
                   lambda v: v['schemes'][2]['signers'][0].update(certificateChainSha256=['e' * 64, 'e' * 64]),
                   lambda v: v['schemes'][2]['signers'][0].update(containsErrors=True),
                   lambda v: v['schemes'][2]['signers'][0].update(lineagePresent=True),
                   lambda v: v['schemes'][2]['signers'][0].update(signerTargetsDevRelease=True),
                   lambda v: v['schemes'][2]['signers'][0].update(rotationTargetsDevRelease=True)]
        for change in changes:
            with self.subTest(case=changes.index(change)), tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary); _, _, build = self.qualification(directory)
                value = C.decode((directory / C.SIGNATURE_API).read_bytes()); change(value)
                raw = json.dumps(value).encode()
                (directory / C.SIGNATURE_API).write_bytes(raw)
                (directory / 'native-input-driver-signature-api-stdout.log').write_bytes(raw)
                build['signatureApiSha256'] = C.sha(raw)
                build['signatureApiLogs']['native-input-driver-signature-api-stdout.log'] = C.sha(raw)
                with self.assertRaises((ValueError, KeyError)):
                    C.verify_signature_logs(directory, build)

    def test_signature_api_original_files_and_exit_codes_are_required(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary); _, _, build = self.qualification(directory)
            C.verify_signature_logs(directory, build)
            for name in (*build['signatureLogs'], *build['signatureApiLogs'], C.SIGNATURE_API):
                path = directory / name; raw = path.read_bytes(); path.unlink()
                with self.subTest(missing=name), self.assertRaises(FileNotFoundError):
                    C.verify_signature_logs(directory, build)
                path.write_bytes(raw)
                path.write_bytes(raw + b' ')
                with self.subTest(changed=name), self.assertRaises(ValueError):
                    C.verify_signature_logs(directory, build)
                path.write_bytes(raw)
            for field in ('signatureCliReturnCode', 'signatureApiReturnCode'):
                for bad in (1, False, '0'):
                    changed = copy.deepcopy(build); changed[field] = bad
                    with self.subTest(field=field, bad=bad), self.assertRaises(ValueError):
                        C.verify_signature_logs(directory, changed)

    def test_strict_json_duplicate_and_nonfinite(self):
        for raw in [b'{"x":1,"x":2}', b'{"x":NaN}']:
            with self.assertRaises(ValueError): C.decode(raw)

    def test_failed_native_command_retains_raw_and_never_replays(self):
        with tempfile.TemporaryDirectory() as temporary:
            d = object.__new__(D.NativeInputDriver); d.out = Path(temporary); d.nonce = 'a' * 32
            d.invoked = set(); d.receipts = []; d.source = 'b' * 40; d.build = dict(sourceTree='c' * 40, apkSha256='d' * 64)
            d.target_hash = 'e' * 64; d.target_proof_raw = b'actual proof'; d.target_proof = dict(installedApkPath='/data/app/test/base.apk', actualFileBytes=100)
            commands = []
            def command(*parts, **kwargs):
                commands.append(parts)
                if parts[:2] == ('shell', 'pidof'): return subprocess.CompletedProcess([], 0, b'1234\n', b'')
                if parts[:3] == ('shell', 'am', 'instrument'):
                    raise subprocess.TimeoutExpired(parts, 20, output=b'original partial stdout\xc2', stderr=b'original stderr')
                return subprocess.CompletedProcess([], 1, b'', b'no device receipt')
            d.command = command
            gesture = dict(id='baseline-scroll', x=540, startY=1469, endY=567)
            with self.assertRaises(subprocess.TimeoutExpired): d.inject(gesture, expires_uptime_ms=21000)
            with self.assertRaisesRegex(ValueError, 'replay'): d.inject(gesture, expires_uptime_ms=21000)
            self.assertEqual(sum(p[:3] == ('shell', 'am', 'instrument') for p in commands), 1)
            self.assertIn(('shell', 'am', 'force-stop', C.SELF), commands)
            self.assertNotIn(('shell', 'am', 'force-stop', C.TARGET), commands)
            self.assertEqual(next(d.out.glob('*-stdout.log')).read_bytes(), b'original partial stdout\xc2')
            self.assertIsNone(d.receipts[0]['sha256'])

    def test_real_scheduler_compiled_and_executed(self):
        java_home = os.environ.get('JAVA_HOME')
        java = Path(java_home) / 'bin/java' if java_home else Path(shutil.which('java'))
        javac = java.with_name('javac')
        with tempfile.TemporaryDirectory() as temporary:
            subprocess.run([str(javac), '-encoding', 'UTF-8', '-d', temporary,
                            str(ROOT / 'tests/native-input-driver/NativeGestureProtocol.java'),
                            str(ROOT / 'tests/native-input-driver-host/NativeGestureProtocolHostTest.java')], check=True, capture_output=True)
            result = subprocess.check_output([str(java), '-cp', temporary, 'local.pocketchat.inputdriver.NativeGestureProtocolHostTest'])
            observed = json.loads(result); self.assertEqual(observed['status'], 'passed'); self.assertGreaterEqual(observed['checks'], 20)
            type(self).scheduler_result = observed


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ContractControls))
    out = ROOT / 'work/gecko-integration/native-input-driver-host-results.json'; out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(dict(status='passed' if result.wasSuccessful() else 'failed', tests=result.testsRun,
        scheduler=getattr(ContractControls, 'scheduler_result', None),
        actualAndroidExecution=False, scope='Production test-driver scheduler and strict parser negative controls only'), indent=2) + '\n')
    raise SystemExit(0 if result.wasSuccessful() else 1)
