#!/usr/bin/env python3
"""One fresh invocation of actual Gecko + production pending-network retries."""
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


def verify(report, source, nonce, apk_sha):
    assert report['status'] == 'passed', report
    assert report['sourceCommit'] == source and report['runNonce'] == nonce
    assert report['buildIdentity']['sourceCommit'] == source
    assert report['actualAndroidExecution'] is True and report['actualGeckoExecution'] is True
    assert report['actualKeystoreEncryption'] is True and report['productionDrainInvoked'] is True
    assert report['actualRouteApplication'] is False and report['actualPublicWebsite'] is False
    assert report['certificateExceptions'] == 0 and report['securityEvents']
    assert report['testTrust']['preparedBeforeRuntime'] is True
    assert report['testTrust']['certificateHostnameSanMatches'] is True
    checks = report['checks']
    assert report['checkCount'] == len(checks) and len(checks) >= 25
    assert len({c['name'] for c in checks}) == len(checks) and all(c['pass'] is True for c in checks)
    cases = report['retryCases']
    assert [c['fault'] for c in cases] == ['invalid', 'timeout']
    for case, expected in zip(cases, (5, 5)):
        assert case['requiredAttempts'] == expected
        assert case['faultHits'] >= expected and case['unavailableObservationHits'] > 0
        assert case['pendingStable'] is True and case['activeStable'] is True and case['draftStable'] is True
        assert case['heldBeforeCommit'] is True and case['routeApplied'] is False
        assert case['availabilityEventChanged'] is True
        assert case['priorRetryDeadline'] - case['recoveryObservedAt'] > 20000
        assert case['recoveryObservedAt'] <= case['recoveryAttemptAt'] < case['priorRetryDeadline']
        assert case['loadCallsBefore'] == case['loadCallsAfter']
        starts, finishes = case['attempts'], case['finishes']
        assert len(starts) == len(finishes) == expected
        assert starts[0]['internal'] is False and all(row['internal'] is True for row in starts[1:])
        assert len({row['id'] for row in starts}) == expected
        assert all(a['id'] == b['id'] and b['at'] >= a['at'] and b['jobCount'] == 1
                   for a, b in zip(starts, finishes))
        for index in range(1, expected):
            delay = starts[index]['at'] - finishes[index - 1]['at']
            bound = min(30000, 2000 << (index - 1))
            assert bound - 150 <= delay < bound + 7000, (case['fault'], index, delay)
        if case['fault'] == 'timeout':
            assert finishes[0]['at'] - starts[0]['at'] >= 2500
    ledger = report['retryLedger']
    assert ledger['schema'] == 1 and len(ledger['cases']) == 2
    owned = {}
    for case, owner in zip(cases, ledger['cases']):
        assert owner['case'] == case['case'] == 'retry-' + case['fault'] and owner['closed'] is True
        assert owner['externalId'] == case['attempts'][0]['id']
        assert isinstance(owner['environmentId'], str) and re.fullmatch(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', owner['environmentId'])
        assert type(owner['generation']) is int and owner['generation'] >= 0
        assert isinstance(owner['snapshotHash'], str) and re.fullmatch(r'[0-9a-f]{64}', owner['snapshotHash'])
        assert (owner['environmentId'], owner['generation']) == (ledger['cases'][0]['environmentId'], ledger['cases'][0]['generation'])
        attempts = owner['attempts']
        assert len(attempts) == case['requiredAttempts'] + 1
        assert attempts[-1]['id'] == case['recoveryId'] and attempts[-1]['id'].startswith('internal:')
        assert attempts[-1]['started'] == case['recoveryAttemptAt']
        for index, attempt in enumerate(attempts):
            assert attempt['id'] not in owned and 0 <= attempt['started'] <= attempt['retired']
            owned[attempt['id']] = (owner['case'], attempt)
            if index < case['requiredAttempts']:
                start, end = case['attempts'][index], case['finishes'][index]
                assert attempt['id'] == start['id'] == end['id']
                assert attempt['started'] == start['at'] and attempt['retired'] == end['at']
                assert attempt['jobCount'] == end['jobCount'] == 1
    assert ledger['cases'][0]['snapshotHash'] != ledger['cases'][1]['snapshotHash']
    retired = set()
    for callback in ledger['callbacks']:
        assert callback['id'] in owned, 'Unowned callbacks cannot be discarded'
        name, attempt = owned[callback['id']]
        assert callback['case'] == name and callback['isRetired'] is True
        if callback['wasActive'] is True:
            assert callback['id'] not in retired
            assert callback['at'] == attempt['retired'] and callback['jobCount'] == attempt['jobCount']
            retired.add(callback['id'])
        else:
            assert callback['wasActive'] is False and callback['id'] in retired
            assert callback['at'] >= attempt['retired']
    assert retired == set(owned), 'Every admitted job, including recovery, must actually retire'
    required = {
        'Internal completed and late callbacks leave no job records',
        'New external start retains the 32 still-readable completion receipts',
        'Full external receipt capacity rejects new work without deleting results',
    }
    assert required <= {c['name'] for c in checks}
    assert len(apk_sha) == 64


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
        adb('shell', 'am', 'start', '-W', '-n', ACTIVITY, '--ez', 'settingsRetry', 'true',
            '--es', 'sourceCommit', source, '--es', 'runNonce', nonce)
        deadline = time.monotonic() + 300
        report = None
        while time.monotonic() < deadline:
            try:
                raw = adb('exec-out', 'content', 'read', '--uri', 'content://' + PKG + '.evidence/network-settings-retry')
                value = json.loads(raw)
                if value.get('runNonce') == nonce:
                    report = value
                    break
            except (subprocess.CalledProcessError, json.JSONDecodeError):
                pass
            time.sleep(.8)
        if report is None:
            raise TimeoutError('One settings-retry invocation did not finish')
        report.update(installedPackage=PKG, installedApkSha256=apk_sha,
                      runnerOneAttempt=True, runnerSha256=hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest())
        (out / 'network-settings-retry-results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        verify(report, source, nonce, apk_sha)
        print(json.dumps({'status': 'passed', 'checks': report['checkCount'], 'source': source, 'nonce': nonce}))
    except BaseException as error:
        (out / 'network-settings-retry-runner-failure.json').write_text(json.dumps({
            'status': 'failed', 'sourceCommit': source, 'runNonce': nonce, 'error': str(error),
            'runnerOneAttempt': True}, ensure_ascii=False, indent=2) + '\n')
        raise
    finally:
        try:
            (out / 'network-settings-retry-log.txt').write_text(adb('logcat', '-d'))
            (out / 'network-settings-retry-final.png').write_bytes(adb('exec-out', 'screencap', '-p', binary=True))
        finally:
            adb('shell', 'am', 'force-stop', PKG)


if __name__ == '__main__':
    main()
