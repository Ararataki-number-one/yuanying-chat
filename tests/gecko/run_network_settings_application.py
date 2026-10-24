#!/usr/bin/env python3
"""One fresh invocation of actual Gecko + production settings application receipts."""
import argparse
import hashlib
import json
import pathlib
import subprocess
import time
import uuid

ROOT = pathlib.Path(__file__).resolve().parents[2]
PKG = 'local.pocketchat.test'
ACTIVITY = PKG + '/local.pocketchat.NetworkSafeIdleIntegrationActivity'


CA_SHA = '794f38936cb5ebc28b6d0f681f9d5b00a2431f48ced181137f4f3bf45fe67226'
LEAF_SHA = '66c659c8f20a9ea7d132d66e4020897be19fab099aa3cc17fa870a967c16266c'
CASE_NAMES = ['pending-while-web-busy', 'applied-after-safe-idle', 'saved-receipt-read-failure',
              'newer-desired-revision', 'newer-candidate', 'old-connection-epoch', 'retired-session',
              'old-environment-generation', 'wrong-environment-uuid', 'no-session']
STALE = CASE_NAMES[3:7]


BOOTSTRAP_CHECKS = ['Fixture browser-only update preserves the migrated stale network', 'Fixture reconciliation aligns desired network without acknowledging application', 'Fixture bootstrap is acknowledged only by the production reconnect']


def verify_application_bootstrap(report, expected):
    proof = report['applicationBootstrap']
    assert proof['schema'] == 1 and proof['migrationBeforeFixturePreferences'] is True
    assert proof['productionReconciliationInvoked'] is True
    identity = proof['migrationIdentity']
    assert identity['environmentId'] == expected['environmentId'] and identity['generation'] == expected['generation']
    assert str(uuid.UUID(identity['environmentId'])) == identity['environmentId']
    assert type(identity['generation']) is int and identity['generation'] >= 0
    assert type(identity['slot']) is int and 0 <= identity['slot'] < 8
    rows = proof['observations']
    assert [row['phase'] for row in rows] == ['browser-only', 'reconciled', 'acknowledged']
    before, aligned, acknowledged = rows
    for row in rows:
        assert row['identity'] == identity and row['mode'] == 'external'
        assert row['browserMatchesAccepted'] is True and row['pendingIntent'] is False
        for field in ['desiredRevision', 'appliedRevision', 'observedRevision', 'connection']:
            assert type(row[field]) is int and row[field] >= 0
        for field in ['desiredHash', 'actualHash']:
            assert isinstance(row[field], str) and len(row[field]) == 64 and all(c in '0123456789abcdef' for c in row[field])
    assert before['networkMatchesActual'] is False and before['desiredHash'] != before['actualHash']
    assert before['appliedRevision'] == aligned['appliedRevision'] == 0
    assert before['appliedHash'] == aligned['appliedHash'] == ''
    assert before['observedRevision'] == aligned['observedRevision'] == 0
    assert before['desiredRevision'] > 0 and aligned['desiredRevision'] > before['desiredRevision']
    assert aligned['networkMatchesActual'] is True and aligned['desiredHash'] == aligned['actualHash']
    assert before['actualHash'] == aligned['actualHash'] == acknowledged['actualHash']
    assert before['connection'] == aligned['connection'] < acknowledged['connection']
    assert acknowledged['desiredRevision'] == acknowledged['appliedRevision'] == aligned['desiredRevision']
    assert expected['savedRevision'] >= acknowledged['appliedRevision']
    assert acknowledged['networkMatchesActual'] is True
    assert acknowledged['desiredHash'] == acknowledged['appliedHash'] == acknowledged['actualHash']
    assert acknowledged['engineVersion'] == acknowledged['runtimeEngineVersion'] and acknowledged['engineVersion']
    assert all(acknowledged[field] is True for field in ['policyAcknowledged', 'networkReady', 'guardAllowed', 'appliedIdentityCurrent'])
    assert set(BOOTSTRAP_CHECKS) <= {row['name'] for row in report['checks']}


def verify(report, source, nonce, apk_sha):
    assert report['status'] == 'passed', report
    assert report['sourceCommit'] == report['buildIdentity']['sourceCommit'] == source
    assert report['runNonce'] == nonce and len(nonce) == 32
    assert report['installedPackage'] == PKG and report['installedApkSha256'] == apk_sha and len(apk_sha) == 64
    assert report['runnerOneAttempt'] is True
    for field in ['actualAndroidExecution', 'actualGeckoExecution', 'actualKeystoreEncryption',
                  'actualExternalRouteApplication', 'productionRequestInvoked', 'productionDrainInvoked',
                  'productionModelAcknowledgement']:
        assert report[field] is True, field
    for field in ['actualInternalCoreApplication', 'actualPublicWebsite', 'actualTrustedGestures']:
        assert report[field] is False, field
    assert report['certificateExceptions'] == 0 and report['securityEvents']
    trust = report['testTrust']
    for field in ['preparedBeforeRuntime', 'databaseCopyShaVerified', 'serverChainShaVerified',
                  'certificateValidityChecked', 'certificateHostnameSanMatches']:
        assert trust[field] is True, field
    for event in report['securityEvents']:
        assert event['callback'] == 'GeckoSession.ProgressDelegate.onSecurityChange'
        assert event['accepted'] is True and event['isSecure'] is True and event['isException'] is False
        assert event['host'] == 'chatgpt.com' and event['certificateSha256'] == LEAF_SHA and event['testCaSha256'] == CA_SHA
        for field in ['certificateSignedByTestCa', 'certificateValidityChecked',
                      'certificateHostnameSanMatches', 'certificateMatchesPackagedLeaf']:
            assert event[field] is True, field
    control = report['fixtureProviderControl']
    assert control['automaticDrainSuspended'] is True and control['removeCallbacksCalled'] is True
    assert control['controlledProviderIdentity'] != control['registeredProviderIdentity']
    assert control['drainRevisionAfter'] > control['drainRevisionBefore']
    checks = report['checks']
    assert report['checkCount'] == len(checks) and all(c['pass'] is True for c in checks)
    names = {c['name'] for c in checks}
    assert len(names) == len(checks)
    required = {'Application fixture starts with production external route and model acknowledgement',
                'Busy save retains the exact pending intent and current document',
                'Applied result matches the actual accepted browser and external route',
                'Same-proxy application preserves the document draft and unsent question',
                'Completed internal application leaves the original pending receipt immutable',
                'Receipt-read fault preserves the genuinely saved ready intent',
                'Newer candidate survives the old completion cleanup',
                'No session can report a setting as actually applied'}
    receipt_names = CASE_NAMES[:7] + ['no-session']
    for name in receipt_names:
        required |= {name + ': result belongs to the exact environment and candidate',
                     name + ': saved and applied states remain distinct'}
    required |= {name + ': an old application callback cannot claim success' for name in STALE}
    required |= {name + ': stale environment request is rejected before saving' for name in CASE_NAMES[7:9]}
    required |= {name + ': direct queued request also preserves encrypted model pending and active state' for name in CASE_NAMES[7:9]}
    assert required <= names, required - names
    cases = report['applicationCases']
    assert [case['name'] for case in cases] == CASE_NAMES
    by_name = {case['name']: case for case in cases}
    for name in receipt_names:
        case = by_name[name]
        actual, wanted = case['result']['operationResult'], case['expected']
        assert case['result']['done'] is True
        assert actual['environmentId'] == wanted['environmentId'] and str(uuid.UUID(actual['environmentId'])) == actual['environmentId']
        assert actual['generation'] == wanted['generation'] and isinstance(actual['generation'], int) and actual['generation'] >= 0
        assert actual['candidateId'] == wanted['candidateId'] and actual['candidateId']
        assert actual['saveState'] == 'saved'
        assert actual['scope'] == ('next-session' if name == 'no-session' else 'session')
        expected_state = 'applied' if name == 'applied-after-safe-idle' else 'pending' if name == 'pending-while-web-busy' else 'saved-unconfirmed'
        assert actual['applicationState'] == expected_state
        assert wanted['savedRevision'] >= 1
        assert actual['savedRevision'] == (0 if name == 'saved-receipt-read-failure' else wanted['savedRevision'])
        assert actual['appliedRevision'] == (wanted['savedRevision'] if name == 'applied-after-safe-idle' else 0)
    pending, applied = by_name['pending-while-web-busy'], by_name['applied-after-safe-idle']
    verify_application_bootstrap(report, pending['expected'])
    assert pending['actualDomBusy'] is True and len(pending['pendingSnapshotHash']) == 64
    assert pending['expected'] == applied['expected'] and applied['sameCandidateAsPending'] is True
    assert pending['result']['ok'] is True and applied['result']['ok'] is True
    assert applied['actualModelDesiredRevision'] == applied['actualModelAppliedRevision'] == applied['expected']['savedRevision']
    assert applied['modelEngineVersion'] == applied['runtimeEngineVersion'] and applied['runtimeEngineVersion']
    assert applied['actualConfigurationHash'] == applied['modelDesiredHash'] == applied['modelAppliedHash'] and len(applied['actualConfigurationHash']) == 64
    assert applied['documentBefore'] == applied['documentAfter'] and applied['documentBefore']
    assert applied['loadsBefore'] == applied['loadsAfter'] and applied['loadsBefore'] > 0
    for field in ['actualConfigurationMatches', 'acceptedPolicy', 'draftRetained', 'documentRetained', 'reconnectObserved']:
        assert applied[field] is True, field
    read_failure = by_name['saved-receipt-read-failure']
    assert read_failure['faultHits'] == 1 and read_failure['actualReadyIntentRetained'] is True
    for name in STALE:
        case = by_name[name]
        assert case['attemptCapturedBeforeInjection'] is True and case['result']['ok'] is False
        assert case['capturedConnection'] > 0 and case['injection'] == name
    assert by_name['newer-desired-revision']['modelDesiredRevisionAtPoll'] > by_name['newer-desired-revision']['expected']['savedRevision']
    assert by_name['newer-candidate']['newerPendingRetained'] is True
    assert by_name['old-connection-epoch']['observedConnection'] > by_name['old-connection-epoch']['capturedConnection']
    assert by_name['retired-session']['sessionAbsentAtPoll'] is True
    for name in CASE_NAMES[7:9]:
        case = by_name[name]
        assert case['rejectedBeforeSave'] is True and case['result']['done'] is True and case['result']['ok'] is False
        assert case['directRequestRejected'] is True and case['directRequestResult']['done'] is True and case['directRequestResult']['ok'] is False
        assert case['encryptedStorageBefore'] == case['encryptedStorageAfter'] and len(case['encryptedStorageBefore']) == 64
        expected, submitted = case['expectedIdentity'], case['submittedIdentity']
        assert expected['slot'] == submitted['slot']
        if name == 'old-environment-generation':
            assert expected['environmentId'] == submitted['environmentId'] and expected['generation'] != submitted['generation']
        else:
            assert expected['generation'] == submitted['generation'] and expected['environmentId'] != submitted['environmentId']
    assert by_name['no-session']['sessionAbsent'] is True
    matches = [row for row in report['applicationResults'] if row['operationResult'].get('applicationState') == 'applied']
    assert len(matches) == 1 and matches[0]['internal'] is True and matches[0]['ok'] is True
    assert matches[0]['operationResult'] == applied['result']['operationResult']


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--adb', required=True)
    parser.add_argument('--serial', default='emulator-5554')
    parser.add_argument('--expected-apk-sha', required=True)
    args = parser.parse_args()
    out = ROOT / 'work/gecko-integration'
    out.mkdir(parents=True, exist_ok=True)
    source = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    nonce = uuid.uuid4().hex

    def adb(*values, binary=False):
        return subprocess.check_output([args.adb, '-s', args.serial, *values], text=not binary, timeout=35)

    try:
        adb('shell', 'am', 'force-stop', PKG)
        adb('shell', 'pm', 'clear', PKG)
        adb('logcat', '-c')
        installed = adb('shell', 'pm', 'path', PKG).strip().removeprefix('package:')
        apk_sha = adb('shell', 'sha256sum', installed).split()[0]
        assert apk_sha == args.expected_apk_sha
        adb('shell', 'am', 'start', '-W', '-n', ACTIVITY, '--ez', 'settingsApplication', 'true',
            '--es', 'sourceCommit', source, '--es', 'runNonce', nonce)
        deadline = time.monotonic() + 360
        report = None
        while time.monotonic() < deadline:
            try:
                raw = adb('exec-out', 'content', 'read', '--uri', 'content://' + PKG + '.evidence/network-settings-application')
                value = json.loads(raw)
                if value.get('runNonce') == nonce:
                    report = value
                    break
            except (subprocess.CalledProcessError, json.JSONDecodeError):
                pass
            time.sleep(.8)
        if report is None:
            raise TimeoutError('One settings-application invocation did not finish')
        report.update(installedPackage=PKG, installedApkSha256=apk_sha,
                      runnerOneAttempt=True, runnerSha256=hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest())
        (out / 'network-settings-application-results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        verify(report, source, nonce, apk_sha)
        print(json.dumps({'status': 'passed', 'checks': report['checkCount'], 'source': source, 'nonce': nonce}))
    except BaseException as error:
        (out / 'network-settings-application-runner-failure.json').write_text(json.dumps({
            'status': 'failed', 'sourceCommit': source, 'runNonce': nonce, 'error': str(error),
            'runnerOneAttempt': True}, ensure_ascii=False, indent=2) + '\n')
        raise
    finally:
        try:
            (out / 'network-settings-application-log.txt').write_text(adb('logcat', '-d'))
            (out / 'network-settings-application-final.png').write_bytes(adb('exec-out', 'screencap', '-p', binary=True))
        finally:
            adb('shell', 'am', 'force-stop', PKG)


if __name__ == '__main__':
    main()
