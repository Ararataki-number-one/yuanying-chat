#!/usr/bin/env python3
"""One invocation of the real managed-core + trusted Gecko settings fixture."""
import argparse
import hashlib
import json
import pathlib
import re
import subprocess
import time
import uuid

ROOT = pathlib.Path(__file__).resolve().parents[2]
PKG = 'local.pocketchat.test'
ACTIVITY = PKG + '/local.pocketchat.NetworkSafeIdleIntegrationActivity'
PREFIX = 'network-settings-internal'
CA_SHA = '794f38936cb5ebc28b6d0f681f9d5b00a2431f48ced181137f4f3bf45fe67226'
LEAF_SHA = '66c659c8f20a9ea7d132d66e4020897be19fab099aa3cc17fa870a967c16266c'
CASE_NAMES = ['new-core-candidate-applied', 'stopped-core-receipt-rejected',
              'newer-desired-revision-rejected']


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


def digest(value, length=64):
    assert isinstance(value, str) and re.fullmatch('[0-9a-f]{%d}' % length, value)


def integer(value, minimum=0, maximum=None):
    assert type(value) is int and value >= minimum
    assert maximum is None or value <= maximum


def required_checks():
    names = {'Internal application begins with a genuinely acknowledged external session',
             'External setup has no running internal core to replace',
             'Changed candidate creates a new real core while preserving the fixed exit',
             'Internal entry change preserves the existing Gecko document without reload',
             'Production reconnect restores a newly verified core generation after the real stop',
             'Every mapped exit target stayed inside its explicit loopback allowlist'}
    for name in ['bootstrap-a', *CASE_NAMES]:
        names |= {name + ': result belongs to the exact environment and candidate',
                  name + ': saved and applied states remain distinct'}
    for name in ['bootstrap-a', CASE_NAMES[0]]:
        names |= {name + ': production model and real internal route identify the saved revision',
                  name + ': internal application preserves the unsent draft and conversation',
                  name + ': actual Gecko fetch dispatched',
                  name + ': fetch traverses the mapped fixed SOCKS exit without the external proxy'}
    for name in CASE_NAMES[1:]:
        names.add(name + ': original provider rejects stale application despite earlier ready state')
        names.add(name + ': negative precondition has the exact acknowledged saved model')
        names.add(name + ': original attempt and saved candidate remain current at injection')
    names.add(CASE_NAMES[1] + ': actual stopped service invalidates the captured core receipt')
    names.add(CASE_NAMES[2] + ': newer desired revision coexists with the genuinely verified old route')
    return names


def verify_trust(report):
    assert report['certificateExceptions'] == 0 and report['securityEvents']
    for field in ['preparedBeforeRuntime', 'databaseCopyShaVerified', 'serverChainShaVerified',
                  'certificateValidityChecked', 'certificateHostnameSanMatches']:
        assert report['testTrust'][field] is True, field
    for event in report['securityEvents']:
        assert event['callback'] == 'GeckoSession.ProgressDelegate.onSecurityChange'
        assert event['accepted'] is True and event['isSecure'] is True and event['isException'] is False
        assert event['host'] == 'chatgpt.com'
        assert event['certificateSha256'] == LEAF_SHA and event['testCaSha256'] == CA_SHA
        for field in ['certificateSignedByTestCa', 'certificateValidityChecked',
                      'certificateHostnameSanMatches', 'certificateMatchesPackagedLeaf']:
            assert event[field] is True, field


def verify_route(route, entry):
    assert route['observation'] == 'fresh-service-snapshot'
    assert route['alive'] is True and route['verified'] is True and route['receiptMatchesFreshState'] is True
    integer(route['pid'], 2); integer(route['servicePid'], 2)
    assert str(uuid.UUID(route['generation'])) == route['generation']
    assert route['receiptGeneration'] == route['generation'] and route['receiptPid'] == route['pid']
    assert route['receiptConfiguration'] == route['configuration']; digest(route['configuration'])
    digest(route['fixedIdentity']); digest(route['fixedNodeFingerprint'])
    integer(route['routeSerial'])
    assert route['currentEntry'] == entry and route['exitIp'] == '203.0.113.8'
    assert route['coreVersion']


def verify_receipt(case, state):
    wanted, output = case['expected'], case['result']
    actual = output['operationResult']
    assert str(uuid.UUID(wanted['environmentId'])) == wanted['environmentId']
    integer(wanted['generation']); integer(wanted['savedRevision'], 1)
    assert re.fullmatch('[a-z0-9:-]{1,96}', wanted['candidateId'])
    for field in ['environmentId', 'generation', 'candidateId', 'savedRevision']:
        assert actual[field] == wanted[field], field
    assert output['done'] is True and output['ok'] is (state == 'applied')
    assert actual['saveState'] == 'saved' and actual['scope'] == 'session'
    assert actual['applicationState'] == state
    assert actual['appliedRevision'] == (wanted['savedRevision'] if state == 'applied' else 0)


def verify(report, source, nonce, apk_sha):
    digest(source, 40); digest(nonce, 32); digest(apk_sha)
    assert report['schema'] == 1 and report['status'] == 'passed'
    assert report['sourceCommit'] == report['buildIdentity']['sourceCommit'] == source
    assert report['runNonce'] == nonce and report['installedPackage'] == PKG
    assert report['installedApkSha256'] == apk_sha and report['runnerOneAttempt'] is True
    for field in ['actualAndroidExecution', 'actualGeckoExecution', 'actualMihomoExecution',
                  'actualInternalCoreApplication', 'actualAuthenticatedSocksChain']:
        assert report[field] is True, field
    for field in ['actualPublicWebsite', 'publicNetworkTraffic', 'actualTrustedGestures']:
        assert report[field] is False, field
    digest(report['coreSha256']); assert report['coreVersion']
    assert report['coreAbi'] in ['x86_64', 'arm64-v8a']
    verify_trust(report)
    isolation = report['fixtureDiagnosticsIsolation']
    assert isolation['geoIpRetryClockHeld'] is True and isolation['admissionStateModified'] is False
    integer(isolation['heldUntilMillis'], 1_000_000_000_000)
    integer(isolation['originalGeoIpAttempted'])
    integer(isolation['testGeoIpAttempted'], 1_000_000_000_000)
    assert isolation['testGeoIpAttempted'] == isolation['heldUntilMillis']
    assert isolation['externalLatencyRetryClockHeld'] is True
    integer(isolation['originalLatencyAttempted'])
    digest(isolation['originalLatencyRouteHash'])
    clock_samples = isolation['latencyClockSamples']
    assert isinstance(clock_samples, list) and 1 <= len(clock_samples) <= 24
    previous_attempt = isolation['originalLatencyAttempted']
    for sample in clock_samples:
        assert set(sample) == {'attempted', 'routeHash'}
        integer(sample['attempted'], max(1, previous_attempt))
        digest(sample['routeHash'])
        previous_attempt = sample['attempted']
    assert isinstance(isolation['scope'], str) and isolation['scope']
    control = report['fixtureProviderControl']
    assert control['automaticDrainSuspended'] is True and control['removeCallbacksCalled'] is True
    assert control['controlledProviderIdentity'] != control['registeredProviderIdentity']
    assert control['drainRevisionAfter'] > control['drainRevisionBefore']
    checks = report['checks']
    assert checks and report['checkCount'] == len(checks) and all(row['pass'] is True for row in checks)
    names = {row['name'] for row in checks}
    assert required_checks() <= names, required_checks() - names
    assert report['previousService']['alive'] is False and report['previousService']['pid'] == 0
    integer(report['previousService']['servicePid'], 2)

    bootstrap, cases = report['bootstrap'], report['cases']
    verify_application_bootstrap(report, bootstrap['expected'])
    assert bootstrap['name'] == 'bootstrap-a' and [row['name'] for row in cases] == CASE_NAMES
    operations = [bootstrap, *cases]
    assert len({row['expected']['candidateId'] for row in operations}) == len(operations)
    identity = (bootstrap['expected']['environmentId'], bootstrap['expected']['generation'])
    for row in operations:
        assert (row['expected']['environmentId'], row['expected']['generation']) == identity
        verify_receipt(row, 'applied' if row in [bootstrap, cases[0]] else 'saved-unconfirmed')

    mapping = report['mapping']
    assert mapping['fromHost'] == 'chatgpt.com' and mapping['fromPort'] == 443
    assert mapping['toHost'] == '127.0.0.1' and mapping['dnsOnlyLoopback'] is True
    for field in ['toPort', 'detectorTlsPort', 'detectorPlainPort', 'fixedPort']:
        integer(mapping[field], 1, 65535)
    assert len({mapping[field] for field in ['toPort', 'detectorTlsPort', 'detectorPlainPort', 'fixedPort']}) == 4
    assert report['dnsEvidence']
    for configuration in report['dnsEvidence']:
        assert type(configuration['bootstrap']) is bool and configuration['download'] is False
        integer(configuration['sinkPort'], 1, 65535)
        for field in ['default-nameserver', 'nameserver', 'proxy-server-nameserver']:
            assert configuration[field] == ['127.0.0.1:' + str(configuration['sinkPort'])]
    assert any(row['bootstrap'] is False for row in report['dnsEvidence'])

    fixed = report['fixedWire']
    assert fixed and report['fixedDenied'] == report['entryADenied'] == report['entryBDenied'] == 0
    assert report['fixedRejectedTargets'] == []
    integer(report['externalProxyDenied'])
    external_rejections = report['externalProxyRejectedTargets']
    assert isinstance(external_rejections, list) and len(external_rejections) == min(report['externalProxyDenied'], 32)
    for rejection in external_rejections:
        assert set(rejection) == {'requestHash', 'hostAllowlisted', 'reason'}
        digest(rejection['requestHash'])
        assert rejection['hostAllowlisted'] is False and rejection['reason'] == 'exact-origin-allowlist'
    mapped = []
    for wire in fixed:
        assert wire['authenticated'] is True and wire['upstreamHost'] == '127.0.0.1'
        integer(wire['connectedAtNs'], 1)
        if wire['mappedOrigin'] is True:
            assert wire['requestedHost'] == 'chatgpt.com' and wire['requestedPort'] == 443
            assert wire['upstreamPort'] == mapping['toPort']; mapped.append(wire)
        else:
            assert wire['mappedOrigin'] is False and wire['requestedHost'] == '127.0.0.1'
            assert wire['requestedPort'] == wire['upstreamPort']
            assert wire['upstreamPort'] in [mapping['detectorTlsPort'], mapping['detectorPlainPort']]
    assert mapped
    for field in ['entryAWire', 'entryBWire']:
        connected = [wire for wire in report[field] if wire['connectAtNs'] > 0]
        assert connected
        for wire in connected:
            assert wire['authRejected'] is False and wire['targetPort'] == mapping['fixedPort']
            assert 0 < wire['acceptedAtNs'] <= wire['methodAtNs'] <= wire['authAtNs'] <= wire['connectAtNs']

    assert [row['name'] for row in report['requests']] == ['bootstrap-a', CASE_NAMES[0]]
    request_nonces = set()
    for index, case in enumerate([bootstrap, cases[0]]):
        route, request = case['route'], case['request']
        entry = 'Entry|a' if index == 0 else 'Entry|b'
        verify_route(route, entry)
        assert route['coreVersion'] == report['coreVersion']
        assert case['actualModelDesiredRevision'] == case['actualModelAppliedRevision'] == case['expected']['savedRevision']
        assert case['actualConfigurationHash'] == case['modelDesiredHash'] == case['modelAppliedHash']
        digest(case['actualConfigurationHash'])
        assert case['modelEngineVersion'] == case['runtimeEngineVersion'] and case['runtimeEngineVersion']
        for field in ['draftRetained', 'acceptedPolicy', 'productionReconnect']:
            assert case[field] is True, field
        integer(case['connectionBefore'], 1); assert case['connectionAfter'] > case['connectionBefore']
        assert case['documentBefore'] and case['documentAfter']
        integer(case['loadsBefore'], 1); integer(case['loadsAfter'], case['loadsBefore'])
        if index == 1:
            assert case['documentBefore'] == case['documentAfter'] and case['loadsBefore'] == case['loadsAfter']
        assert request == report['requests'][index] and request['name'] == case['name']
        assert request['ok'] is True and request['httpStatus'] == 200 and request['bodyMatches'] is True
        digest(request['bodySha256']); assert request['bodySha256'] == request['expectedBodySha256']
        digest(request['nonce'], 32); assert request['nonce'] == request['echoedNonce']
        assert request['serverObservedNonce'] is True and request['nonce'] not in request_nonces
        request_nonces.add(request['nonce'])
        integer(request['mappedBefore']); integer(request['externalBefore'])
        assert request['mappedAfter'] > request['mappedBefore'] and request['mappedAfter'] <= len(mapped)
        assert request['externalAfter'] == request['externalBefore'] and request['currentEntry'] == entry
        assert request['entryAContacts' if index == 0 else 'entryBContacts'] > 0
        assert 0 < request['beganAtNs'] < request['endedAtNs']
        assert any(request['beganAtNs'] <= wire['connectedAtNs'] <= request['endedAtNs'] for wire in mapped)
    old, new = bootstrap['route'], cases[0]['route']
    assert old['generation'] != new['generation'] and old['pid'] != new['pid']
    assert old['configuration'] != new['configuration']
    assert old['fixedIdentity'] == new['fixedIdentity'] and old['fixedNodeFingerprint'] == new['fixedNodeFingerprint']
    assert cases[0]['expected']['savedRevision'] > bootstrap['expected']['savedRevision']

    for case, entry in zip(cases[1:], ['Entry|b', 'Entry|a']):
        verify_route(case['before'], entry)
        assert case['before']['fixedIdentity'] == old['fixedIdentity']
        assert case['before']['fixedNodeFingerprint'] == old['fixedNodeFingerprint']
        assert case['attemptCapturedBeforeInjection'] is True
        assert case['originalAttemptCurrentAtPoll'] is True
        assert case['pendingUnchangedAtPoll'] is True
        assert case['modelDesiredRevisionBefore'] == case['modelAppliedRevisionBefore'] == case['expected']['savedRevision']
        assert case['before']['coreVersion'] == report['coreVersion']
        integer(case['frozenConnection'], 1)
        assert case['observedConnection'] == case['frozenConnection']
    stopped, stale = cases[1:]
    assert stopped['realCoreStopped'] is True and stopped['capturedReceiptMatchesAfter'] is False
    assert stopped['stopConfirmed'] is True
    assert stopped['after']['alive'] is False and stopped['after']['pid'] == 0
    assert stopped['after']['generation'] != stopped['before']['generation']
    assert stopped['modelDesiredRevisionAtPoll'] == stopped['expected']['savedRevision']
    assert stale['realCoreStopped'] is False and stale['capturedReceiptMatchesAfter'] is True
    assert stale['stopConfirmed'] is False
    verify_route(stale['after'], 'Entry|a')
    for field in ['generation', 'pid', 'configuration', 'fixedIdentity', 'fixedNodeFingerprint']:
        assert stale['before'][field] == stale['after'][field]
    assert stale['modelDesiredRevisionAtPoll'] > stale['expected']['savedRevision']
    assert stale['before']['generation'] not in [stopped['before']['generation'], stopped['after']['generation']]
    restoration = report['restoration']
    verify_route(restoration, 'Entry|b')
    assert restoration['coreVersion'] == report['coreVersion']
    assert restoration['generation'] not in [stopped['before']['generation'], stopped['after']['generation']]
    assert restoration['pid'] != stopped['before']['pid']
    assert restoration['fixedIdentity'] == old['fixedIdentity']
    assert restoration['fixedNodeFingerprint'] == old['fixedNodeFingerprint']
    assert stale['before']['generation'] != restoration['generation']

    observations = report['applicationResults']
    assert len(observations) == len(operations)
    for case in operations:
        matches = [row for row in observations if row['operationResult']['candidateId'] == case['expected']['candidateId']]
        assert len(matches) == 1
        row = matches[0]
        assert row['internal'] is False  # Direct user job; the route itself is internal.
        assert row['ok'] is case['result']['ok'] and row['operationResult'] == case['result']['operationResult']
    assert len({row['id'] for row in observations}) == len(observations)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--adb', required=True)
    parser.add_argument('--serial', default='emulator-5554')
    parser.add_argument('--expected-apk-sha', required=True)
    args = parser.parse_args()
    out = ROOT / 'work/gecko-integration'; out.mkdir(parents=True, exist_ok=True)
    source = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    nonce = uuid.uuid4().hex

    def adb(*values, binary=False):
        return subprocess.check_output([args.adb, '-s', args.serial, *values], text=not binary, timeout=35)

    try:
        digest(args.expected_apk_sha)
        adb('shell', 'am', 'force-stop', PKG); adb('shell', 'pm', 'clear', PKG); adb('logcat', '-c')
        installed = adb('shell', 'pm', 'path', PKG).strip().removeprefix('package:')
        apk_sha = adb('shell', 'sha256sum', installed).split()[0]
        assert apk_sha == args.expected_apk_sha
        adb('shell', 'am', 'start', '-W', '-n', ACTIVITY, '--ez', 'settingsInternal', 'true',
            '--es', 'sourceCommit', source, '--es', 'runNonce', nonce)
        deadline, report = time.monotonic() + 540, None
        while time.monotonic() < deadline:
            try:
                value = json.loads(adb('exec-out', 'content', 'read', '--uri', 'content://' + PKG + '.evidence/' + PREFIX))
                if value.get('runNonce') == nonce:
                    report = value; break
            except (subprocess.CalledProcessError, json.JSONDecodeError):
                pass
            time.sleep(.8)
        if report is None:
            raise TimeoutError('One settings-internal invocation did not finish')
        report.update(installedPackage=PKG, installedApkSha256=apk_sha, runnerOneAttempt=True,
                      runnerSha256=hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest())
        (out / (PREFIX + '-results.json')).write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        verify(report, source, nonce, apk_sha)
        print(json.dumps({'status': 'passed', 'checks': report['checkCount'], 'source': source, 'nonce': nonce}))
    except BaseException as error:
        (out / (PREFIX + '-runner-failure.json')).write_text(json.dumps({
            'status': 'failed', 'sourceCommit': source, 'runNonce': nonce, 'error': str(error),
            'runnerOneAttempt': True}, ensure_ascii=False, indent=2) + '\n')
        raise
    finally:
        errors = []
        for suffix, command, binary in [('-log.txt', ('logcat', '-d'), False),
                                        ('-final.png', ('exec-out', 'screencap', '-p'), True)]:
            try:
                value = adb(*command, binary=binary)
                destination = out / (PREFIX + suffix)
                destination.write_bytes(value) if binary else destination.write_text(value)
            except Exception as error:
                errors.append({'stage': suffix, 'error': str(error)})
        try:
            adb('shell', 'am', 'force-stop', PKG)
        except Exception as error:
            errors.append({'stage': 'force-stop', 'error': str(error)})
        if errors:
            (out / (PREFIX + '-diagnostic-errors.json')).write_text(json.dumps(errors, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    main()
