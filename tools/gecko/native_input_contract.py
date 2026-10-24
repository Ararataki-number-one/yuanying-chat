"""Strict evidence for the two declared test-only native-input protocols."""
import hashlib
import json
import math
import re
from pathlib import Path

SELF = 'local.pocketchat.inputdriver'
TARGET = 'local.pocketchat.test'
BACKEND = dict(executionBackend='shell-input-manager-global-v1',
               entryPoint=SELF+'.NativeInputShell', executionUid=2000, inputTargetUidEnforced=True)
SIGNATURE_VERIFIER = 'tools/gecko/VerifyNativeInputSignature.java'
SIGNATURE_API = 'native-input-driver-signature-api.json'
PROTOCOLS = {name: dict(durationMs=20 * interval, moveCount=19, intervalMs=interval, maxLateMs=2 * interval, upSynchronous=True)
             for name, interval in [('qualification', 15), ('formal-collapse', 16)]}
INPUTS = {'tests/native-input-driver/NativeGestureProtocol.java',
          'tests/native-input-driver/NativeInputShell.java',
          'tests/native-input-driver/NativeInputInstrumentation.java', 'tests/native-input-driver/AndroidManifest.xml'}


def require(value, message):
    if not value:
        raise ValueError('Native input: ' + message)


def decode(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate JSON field')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def integer(value):
    return type(value) is int and value >= 0


def verify_target_proof(proof, expected_sha, expected_bytes):
    require(proof['schema'] == 1 and proof['status'] == 'verified-bytes'
            and proof['actualInstalledApkRead'] is True and proof['compiledFileFallback'] is False
            and proof['retryPerformed'] is False and proof['returnCode'] == 0, 'actual target byte transfer')
    require(proof['transport'] == 'adb-shell-v2-no-pty-ranged' and proof['dataSource'] == 'binary-stdout-destination-file', 'target proof transport')
    require(proof['actualFileSha256'] == proof['stdoutSha256'] == proof['expectedSha256'] == expected_sha
            and proof['actualFileBytes'] == proof['stdoutBytes'] == proof['expectedBytes'] == expected_bytes, 'target proof bytes')
    require(proof['rangeBytes'] == 4194304 and len(proof['ranges']) == expected_bytes // 4194304 + 1, 'target read ranges')
    for i, row in enumerate(proof['ranges']):
        size = min(4194304, expected_bytes - i * 4194304)
        require(row['index'] == i and row['offset'] == i * 4194304 and row['actualBytes'] == row['expectedBytes'] == size
                and row['returnCode'] == 0 and row['status'] == 'verified-length'
                and re.fullmatch('[0-9a-f]{64}', row['sha256']), 'target range incomplete')
    require(re.fullmatch(r'/data/app/[A-Za-z0-9/._~+=-]+/base\.apk', proof['installedApkPath']) and '..' not in Path(proof['installedApkPath']).parts, 'target installed path')


def verify_build(build, source, source_reader):
    require(type(build['schema']) is int and build['schema'] == 1 and build['sourceCommit'] == source and re.fullmatch('[0-9a-f]{40}', build['sourceTree']), 'build source')
    require(build['status'] == 'built' and build['compileOnly'] is False and build['testOnly'] is True, 'strict build required')
    require(build['packageName'] == SELF and build['targetPackage'] == TARGET
            and build['instrumentationTargetPackage'] == SELF
            and build['instrumentation'] == SELF + '.NativeInputInstrumentation', 'self-target identity')
    require(build['protocols'] == PROTOCOLS, 'fixed protocol differs')
    require(all(type(build[key]) is type(expected) and build[key] == expected
                for key, expected in BACKEND.items()), 'fixed shell backend differs')
    for name, protocol in PROTOCOLS.items():
        require(all(type(build['protocols'][name][key]) is type(value) for key, value in protocol.items()), 'protocol field types')
    require(set(build['inputs']) == INPUTS, 'driver input set')
    for path in INPUTS:
        require(build['inputs'][path] == sha(source_reader(source, path)), 'driver source bytes: ' + path)
    require(re.fullmatch('[0-9a-f]{64}', build['apkSha256']) is not None and integer(build['apkBytes']) and build['apkBytes'] > 0, 'APK identity')
    require(str(build['runId']).isdigit() and str(build['runAttempt']).isdigit(), 'build run identity')
    require(re.fullmatch('[0-9a-f]{64}', build['signerCertificateSha256']) is not None, 'signing certificate identity')
    require(build['signatureVerifierSourceSha256'] == sha(source_reader(source, SIGNATURE_VERIFIER)), 'signature verifier source')
    require(build['toolchain']['buildTools'] == '37.0.0'
            and re.fullmatch('[0-9a-f]{64}', build['toolchain']['tools']['apksignerJar']['sha256']), 'actual pinned verifier JAR identity')



def verify_signature_logs(directory, build):
    directory = Path(directory)
    names = {'native-input-driver-signature-stdout.log', 'native-input-driver-signature-stderr.log'}
    api_names = {'native-input-driver-signature-api-stdout.log', 'native-input-driver-signature-api-stderr.log'}
    for field, required in (('signatureLogs', names), ('signatureApiLogs', api_names)):
        require(set(build[field]) == required, 'original signing outputs missing: ' + field)
        for name in required:
            require(sha((directory / name).read_bytes()) == build[field][name], 'signing output bytes: ' + name)
    for field in ('signatureCliReturnCode', 'signatureApiReturnCode'):
        require(type(build[field]) is int and build[field] == 0, 'actual signature command failed')
    raw = (directory / SIGNATURE_API).read_bytes()
    require(sha(raw) == build['signatureApiSha256']
            and raw == (directory / 'native-input-driver-signature-api-stdout.log').read_bytes(), 'original signature API bytes')
    value = decode(raw)
    require(type(value['schema']) is int and value['schema'] == 1 and value['status'] == 'passed'
            and value['verified'] is True and value['containsErrors'] is False and value['error'] == ''
            and value['inputsUnchangedDuringVerification'] is True, 'actual API verification failed')
    for field in ('sourceCommit', 'sourceTree', 'runId', 'runAttempt', 'apkSha256', 'apkBytes', 'signerCertificateSha256'):
        require(type(value[field]) is type(build[field]) and value[field] == build[field], 'signature API identity: ' + field)
    require(value['apksignerJarSha256'] == build['toolchain']['tools']['apksignerJar']['sha256']
            and value['verifierSourceSha256'] == build['signatureVerifierSourceSha256']
            and value['loadedApksignerJarPath'] == build['toolchain']['tools']['apksignerJar']['path'], 'actual API implementation identity')
    certificate = build['signerCertificateSha256']
    require(value['effectiveSignerCertificateSha256'] == [certificate], 'exactly one effective signing certificate')
    require(value['lineagePresent'] is False and value['lineageCertificateSha256'] == []
            and value['noRotation'] is True and value['v32Detected'] is False
            and value['ignoredV1SignerCertificateSha256'] == [], 'fresh unrotated signing identity')
    schemes = value['schemes']
    require([row['name'] for row in schemes] == ['v1', 'v2', 'v3', 'v31', 'v4'], 'signature scheme inventory')
    require(any(row['verified'] is True for row in schemes), 'no verified signature scheme')
    for row in schemes:
        require(type(row['verified']) is bool
                and row['signerCertificateSha256'] == ([certificate] if row['verified'] else []), 'single consistent scheme certificate')
        require(type(row['signers']) is list and len(row['signers']) == (1 if row['verified'] else 0), 'exact scheme signer inventory')
        for signer in row['signers']:
            require(signer['certificateSha256'] == certificate and signer['certificateChainSha256'] == [certificate]
                    and signer['containsErrors'] is False and signer['lineagePresent'] is False
                    and signer['lineageCertificateSha256'] == [] and signer['rotationTargetsDevRelease'] is False
                    and signer['signerTargetsDevRelease'] is False, 'fresh self-signed scheme certificate')
    return value


def verify_focus(value):
    require(type(value['displayId']) is int and value['displayId'] == 0
            and value['packageName'] == TARGET, 'AUT default display focus required')
    raw = value['raw']
    require(type(raw) is str and len(raw) < 8192, 'bounded actual focus observation')
    display = re.findall(r'^\s*mTopFocusedDisplayId=([0-9]+)\s*$', raw, re.M)
    focus = re.findall(r'^\s*mCurrentFocus=Window\{[^\n}]*\s([^\s}]+)\}\s*$', raw, re.M)
    require(display == ['0'] and focus == [value['component']]
            and value['component'].startswith(TARGET+'/'), 'actual focused window differs')


def verify_receipt(value, *, build, purpose, nonce, gesture, target_apk, request):
    require(purpose in PROTOCOLS, 'unknown purpose')
    p = PROTOCOLS[purpose]
    require(value['schema'] == 1 and value['status'] == 'passed' and not value.get('error'), 'failed injection')
    require(value['purpose'] == purpose and value['nonce'] == nonce and value['gesture'] == gesture, 'invocation identity')
    require(value['sourceCommit'] == build['sourceCommit'] and value['sourceTree'] == build['sourceTree'], 'source identity')
    require(value['packageName'] == SELF and value['targetPackage'] == TARGET, 'package identity')
    require(value['executionBackend'] == BACKEND['executionBackend']
            and type(value['executionUid']) is int and value['executionUid'] == 2000
            and value['tracePersistence'] == 'memory-until-terminal', 'actual shell backend required')
    require(integer(value['inputTargetUid']) and 10000 <= value['inputTargetUid'] < 100000
            and type(value['targetUidBefore']) is int and type(value['targetUidAfter']) is int
            and value['inputTargetUid'] == value['targetUidBefore'] == value['targetUidAfter'], 'target UID fence')
    require(type(value['displayId']) is int and value['displayId'] == 0, 'injected display changed')
    require(integer(value['driverPid']) and value['driverPid'] > 0
            and re.fullmatch('[1-9][0-9]*', value['driverStartTicks'])
            and re.fullmatch('[1-9][0-9]*', value['targetStartTicksBefore'])
            and value['targetStartTicksBefore'] == value['targetStartTicksAfter'], 'actual process generation fence')
    verify_focus(value['focusBefore']); verify_focus(value['focusAfter'])
    asset = value['buildIdentity']
    require(all(asset[key] == build[key] for key in ('schema', 'sourceCommit', 'sourceTree', 'runId', 'runAttempt', 'packageName', 'targetPackage', 'instrumentationTargetPackage', 'instrumentation', 'protocols', 'inputs')), 'embedded driver asset')
    require(all(type(asset[key]) is type(expected) and asset[key] == build[key] == expected
                for key, expected in BACKEND.items()), 'embedded shell backend identity')
    require(value['signerCertificateSha256'] == build['signerCertificateSha256'], 'actual driver signing certificate')
    require(value['driverApkSha256'] == build['apkSha256'] and value['targetApkSha256'] == target_apk, 'installed APK mismatch')
    target = value['targetBuildIdentity']
    require(target['sourceCommit'] == build['sourceCommit'] and target['sourceTree'] == build['sourceTree'] and target['dirtySource'] is False, 'measured APK source')
    require(value['targetApkHashSource'] == 'preflight-installed-byte-proof'
            and value['targetByteProofSha256'] == request['targetByteProofSha256'], 'target byte proof origin')
    require(value['targetApkPathBefore'] == value['targetApkPathAfter'] == request['targetApkPath']
            and value['targetApkBytesBefore'] == value['targetApkBytesAfter'] == request['targetApkBytes']
            and value['targetLastModifiedBefore'] == value['targetLastModifiedAfter']
            and value['targetLastUpdateBefore'] == value['targetLastUpdateAfter']
            and value['targetBuildIdentityAfter'] == target, 'target identity fence changed')
    require(value['targetPidBefore'] == value['targetPidAfter'] == request['targetPid'] and re.fullmatch('[1-9][0-9]*', request['targetPid']), 'measured process replaced')
    for key in ('createdUptimeMs', 'startedUptimeMs', 'connectStartUptimeMs', 'connectEndUptimeMs', 'readyUptimeMs', 'startupMs', 'finishedUptimeMs', 'expiresUptimeMs'):
        require(integer(value[key]), 'timestamp ' + key)
    require(value['createdUptimeMs'] <= value['startedUptimeMs'] <= value['connectStartUptimeMs']
            <= value['connectEndUptimeMs'] <= value['readyUptimeMs'] <= value['finishedUptimeMs']
            and value['startupMs'] == value['readyUptimeMs'] - value['startedUptimeMs'], 'startup chronology')
    t = value['trace']; start = t['startUptimeMs']
    require(all(t[key] == expected for key, expected in p.items()), 'trace schedule')
    require(all(type(t[key]) is type(expected) for key, expected in p.items()), 'trace schedule types')
    require(integer(start) and start >= value['readyUptimeMs'] and start + p['durationMs'] <= request['expiresUptimeMs'], 'original deadline')
    require(t['expiresUptimeMs'] == value['expiresUptimeMs'] == request['expiresUptimeMs'], 'deadline changed')
    require(t['error'] == '' and t['cleanup'] is None and len(t['events']) == 21, 'incomplete gesture or cleanup')
    prior = start
    for i, row in enumerate(t['events']):
        planned = start + i * p['intervalMs']
        require(row['action'] == (0 if i == 0 else 1 if i == 20 else 2)
                and row['sync'] is (i == 20) and row['downTime'] == start and row['plannedUptimeMs'] == planned, 'event order/downTime/plan')
        require(row['accepted'] is True and row['injected'] is True and row['cleanup'] is False and row['error'] == '', 'injection not accepted')
        event, begin, end = (row[k] for k in ('eventTime', 'callStartUptimeMs', 'callEndUptimeMs'))
        require(all(integer(v) for v in (event, begin, end)) and prior <= event <= begin <= end, 'actual event chronology')
        require(planned <= event <= planned + p['maxLateMs'] and begin <= planned + p['maxLateMs']
                and end <= request['expiresUptimeMs'], 'late injection')
        expected_y = request['startY'] + (request['endY'] - request['startY']) * i / 20
        require(all(type(row[k]) in (int, float) and math.isfinite(row[k]) for k in ('x', 'y'))
                and row['x'] == request['x'] and abs(row['y'] - expected_y) <= 0.001, 'trajectory changed')
        prior = end
    require(value['finishedUptimeMs'] >= prior, 'receipt predates injection return')


def verify_qualification(directory, report, source, source_reader, target_apk=None, expected_run=None):
    directory = Path(directory)
    evidence = report['nativeInputDriver']; build = decode((directory / 'native-input-driver-build.json').read_bytes())
    verify_build(build, source, source_reader)
    verify_signature_logs(directory, build)
    if expected_run is not None:
        require((build['runId'], build['runAttempt']) == tuple(expected_run), 'build run/attempt mismatch')
    require(evidence['buildSha256'] == sha((directory / 'native-input-driver-build.json').read_bytes()), 'build receipt bytes')
    require(evidence['purpose'] == 'qualification' and re.fullmatch('[0-9a-f]{32}', evidence['nonce']), 'qualification identity')
    proof_name = 'native-input-target-proof-' + evidence['nonce'] + '.json'
    require(evidence['targetByteProofFile'] == proof_name, 'target proof filename')
    proof_raw = (directory / proof_name).read_bytes(); proof = decode(proof_raw)
    require(evidence['targetByteProofSha256'] == sha(proof_raw), 'target proof original bytes')
    verify_target_proof(proof, target_apk or proof['actualFileSha256'], proof['actualFileBytes'])
    require(len(evidence['receipts']) == 2 and [r['gesture'] for r in evidence['receipts']] == ['baseline-scroll', 'current-scroll'], 'both single scroll invocations required')
    scroll = decode((directory / 'gecko-scroll-diagnostics.json').read_bytes())
    require(scroll['run'] == evidence['nonce'] and scroll['sourceCommit'] == source and scroll['actualAndroidFileRead'] is True, 'actual scroll identity')
    require([p['phase'] for p in scroll['phases']] == ['baseline', 'current'], 'actual scroll phases')
    gestures = {g['id']: g for g in report['actualAndroidGestures']}
    for receipt, phase in zip(evidence['receipts'], scroll['phases']):
        name = 'native-input-' + evidence['nonce'] + '-' + receipt['gesture'] + '.json'
        require(receipt['file'] == name, 'receipt path')
        raw = (directory / name).read_bytes(); value = decode(raw)
        require(receipt['sha256'] == sha(raw), 'raw receipt bytes')
        request = receipt['request']; gesture = gestures[receipt['gesture']]
        require(request['targetByteProofSha256'] == sha(proof_raw) and request['targetApkPath'] == proof['installedApkPath']
                and request['targetApkBytes'] == proof['actualFileBytes'], 'gesture must reuse exact target proof')
        require(all(request[key] == gesture[key] for key in ('x', 'startY', 'endY')), 'original requested endpoints')
        deadlines = [d for d in report['actualAndroidGestureDeadlines'] if d['id'] == receipt['gesture']]
        require(len(deadlines) == 1, 'one actual watchdog deadline')
        deadline = deadlines[0]
        require(deadline['expiresElapsedMs'] - deadline['sampledElapsedMs'] == 20000
                and deadline['expiresUptimeMs'] - deadline['sampledUptimeMs'] == 20000
                and request['expiresUptimeMs'] == deadline['expiresUptimeMs'], 'original 20s input window')
        verify_receipt(value, build=build, purpose='qualification', nonce=evidence['nonce'], gesture=receipt['gesture'], target_apk=target_apk or value['targetApkSha256'], request=request)
        samples = phase['samples']; require(samples and phase['outcome'] == 'passed', 'actual failed scroll')
        first = samples[0]
        for sample in samples:
            n = sample['native']; d = sample['dom']
            require(all(n[k] is True for k in ('sameNavigation', 'sameSession', 'sameSurface', 'sameUrl', 'windowFocused', 'webShown', 'surfaceShown', 'surfaceAttached')) and n['browserPaused'] is False, 'changed measured surface')
            require(d['document'] == first['dom']['document'] and d['url'] == first['dom']['url'], 'changed measured document')
        touches = phase['nativeTouches']
        require({0, 2} <= {t['action'] for t in touches if t['superHandled'] is True}, 'actual native MOVE missing')
        require(any(d['type'] == 'touchstart' and d['trusted'] is True for d in phase['domEvents']), 'trusted Gecko touch missing')
    return {'protocols': PROTOCOLS, 'receiptCount': 2, 'driverApkSha256': build['apkSha256']}
