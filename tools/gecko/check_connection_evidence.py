#!/usr/bin/env python3
"""Require current-source Android evidence for binding and proxy continuity fixes."""
import argparse
import json
import pathlib
import re
if __package__:
    from .network_client_binding_contract import verify_framework_binding_files
else:
    from network_client_binding_contract import verify_framework_binding_files


def collect_cold_website_probe_event(report, events, summary):
    kind = report.get('kind')
    if kind == 'coldWebsiteProbeDiagnosticSummary':
        value = report['value']
        assert re.fullmatch('[a-f0-9]{32}', value['token'])
        assert summary is None or summary == value, 'Conflicting cold website diagnostic summary'
        return True, value
    if kind == 'coldWebsiteProbeDiagnostic':
        value = report['value']; order = value['order']
        assert summary is not None and value['token'] == summary['token'], 'Mixed cold website invocation'
        assert type(order) is int and 1 <= order <= 18
        assert value['recordKind'] in ('call', 'circuit')
        assert order in events or order == len(events) + 1, 'Missing or reordered cold website event'
        assert order not in events or events[order] == value, 'Conflicting cold website diagnostic event'
        events[order] = value
        return True, summary
    return False, summary


def verify_cold_website_probe_diagnostics(network):
    """Source-bound wire observations supplement, never replace, the original timers."""
    summary = network['coldWebsiteProbeDiagnosticSummary']
    rows = network['coldWebsiteProbeDiagnostics']
    assert summary['schema'] == 1 and re.fullmatch('[a-f0-9]{32}', summary['token'])
    assert summary['clock'] == 'Android elapsedRealtimeNanos'
    assert summary['frozen'] is True and summary['overflow'] is False and summary['timerUnchanged'] is True
    assert summary['requestedConnectDelayMs'] == {'slow': 100, 'fast': 5, 'fixed': 0}
    assert summary['callCount'] == 2 and 6 <= summary['circuitCount'] <= 16
    assert summary['eventCount'] == len(rows) == summary['callCount'] + summary['circuitCount']
    assert [row['order'] for row in rows] == list(range(1, len(rows) + 1))
    assert all(row['token'] == summary['token'] for row in rows)
    assert [row['recordKind'] for row in rows] == ['call', 'call'] + ['circuit'] * summary['circuitCount']
    calls = [row['payload'] for row in rows[:2]]
    circuits = [row['payload'] for row in rows[2:]]
    assert [call['case'] for call in calls] == [1, 2]
    assert [call['entry'] for call in calls] == ['Entry|slow', 'Entry|fast']
    assert [call['reading'] for call in calls] == network['controlledWebsiteReadings']
    assert calls[1]['reading']['firstMs'] < calls[0]['reading']['firstMs'], 'The original cold ordering remains required'
    assert [row['circuit'] for row in circuits] == list(range(1, len(circuits) + 1))
    for call in calls:
        assert 0 < call['callBeganAtNs'] < call['callEndedAtNs'] and 'error' not in call
        assert call['reading']['entry'] == call['entry'] and call['reading']['status'] == 'ok'
        assert call['reading']['code'] == 200 and call['reading']['firstMs'] > 0 and call['reading']['warmMs'] > 0
    assert calls[0]['callEndedAtNs'] <= calls[1]['callBeganAtNs']
    for circuit in circuits:
        assert type(circuit['case']) is int and circuit['case'] in (1, 2)
        call = calls[circuit['case'] - 1]
        assert circuit['role'] in ('slow', 'fast', 'fixed', 'site')
        assert call['callBeganAtNs'] <= circuit['acceptedAtNs'] <= call['callEndedAtNs']
        assert all(type(circuit[key]) is int and 0 < circuit[key] <= 65535 for key in ('listenPort', 'peerPort'))
        assert circuit['tls'] is (circuit['role'] == 'site')
        assert circuit['handleBeganAtNs'] >= circuit['acceptedAtNs']
        if circuit['role'] != 'site':
            assert circuit['targetHost'] == '127.0.0.1'
            assert circuit['requestedDelayMs'] == summary['requestedConnectDelayMs'][circuit['role']]
            stamps = [circuit[key] for key in ('handleBeganAtNs', 'delayBeganAtNs', 'delayEndedAtNs', 'upstreamConnectBeganAtNs', 'upstreamConnectEndedAtNs', 'socksReplyFlushedAtNs')]
            assert all(a <= b for a, b in zip(stamps, stamps[1:]))
            assert circuit['delayEndedAtNs'] - circuit['delayBeganAtNs'] >= circuit['requestedDelayMs'] * 1_000_000
            assert circuit['upstreamRemotePort'] == circuit['targetPort']
            assert 0 < circuit['upstreamLocalPort'] <= 65535
        else:
            assert circuit['firstReadBeganAtNs'] >= circuit['handleBeganAtNs']
            requests = circuit['requests']
            assert 1 <= len(requests) <= 4
            assert [request['ordinal'] for request in requests] == list(range(1, len(requests) + 1))
            for request in requests:
                assert request['method'] == 'HEAD' and request['path'] == '/website' and request['responseCode'] == 200
                assert circuit['firstReadBeganAtNs'] <= request['requestLineAtNs'] <= request['headersReadAtNs'] <= request['responseWriteBeganAtNs']
                if 'responseFlushedAtNs' in request:
                    assert request['responseFlushedAtNs'] >= request['responseWriteBeganAtNs']
            # TLS completion listener delivery can lag the real handshake. It
            # is optional observational data, never a reconstructed TLS duration.
            if 'tlsCompletionListenerAtNs' in circuit:
                assert circuit['tlsCompletionListenerAtNs'] >= circuit['handleBeganAtNs']
    paths = []
    for case, role in ((1, 'slow'), (2, 'fast')):
        candidates = [row for row in circuits if row['case'] == case]
        matching = [(entry, fixed, site) for entry in candidates for fixed in candidates for site in candidates
                    if entry['role'] == role and fixed['role'] == 'fixed' and site['role'] == 'site'
                    and entry['targetPort'] == fixed['listenPort'] and entry['upstreamLocalPort'] == fixed['peerPort']
                    and fixed['targetPort'] == site['listenPort'] and fixed['upstreamLocalPort'] == site['peerPort']]
        assert matching, 'Missing actual entry to fixed-exit to HTTPS socket correlation'
        assert sum(len(site['requests']) for site in candidates if site['role'] == 'site') == 2
        paths.append({'case': case, 'entry': role, 'matchedPaths': len(matching)})
    return {'actualCorrelatedPaths': paths, 'originalColdOrderingRetained': True,
            'diagnosticOnly': True, 'productSpeedComparison': False}


def verify_detector_transport_evidence(network):
    """Wire failures and the exact protected service identity, rather than check labels alone."""
    evidence = network['exitTransportContinuity']
    assert len(evidence) == 6
    cases = {(item['kind'], item['fault']): item for item in evidence}
    assert set(cases) == {(kind, fault) for kind in ('verified', 'changed-route', 'first-route')
                          for fault in ('reset', 'eof')}
    for (kind, fault), item in cases.items():
        assert item['classification'] == 'transport-reset-or-eof', (kind, fault)
        assert item['detectorRequests'] == item['wireFaultRequests'] > 0
        if kind == 'verified':
            before, after = item['before'], item['after']
            assert item['serviceProcess'] and before == after and before['alive']
            assert before['pid'] > 1 and before['servicePid'] > 1
            assert before['controllerPort'] > 0 and before['proxyPort'] > 0
            assert before['generation'] and before['configuration'] and before['entry'] and before['exitIp']
            assert len(before['tokenHash']) == 64
            assert item['receiptCurrent'] and item['sendAccepted'] and item['lastVerified'] == 0
            assert item['retryInMs'] > 0 and item['backoffNoRequests']
            assert item['webSocketConnections'] == 1 and item['echoesAfter'] > item['echoesBefore']
        else:
            assert not item['ready'] and not item['coreAlive'] and not item['receiptCurrent']
            if kind == 'changed-route':
                assert not item['sendAccepted'] and item['entryChanged']
                assert item['webSocketClosed'] and item['webSocketConnections'] == 1
            else:
                assert not item['startAccepted'] and item['startupBeganAt'] > 0 and item['controllerPort'] > 0
    return {'actualDetectorReset': True, 'actualDetectorEof': True,
            'sameVerifiedServiceWebSocket': True, 'unknownRouteFailClosed': True}


NETWORK_REPAIR_CHECKS = frozenset({
    'A stale generation stop is rejected by the real service without interrupting its WSS',
    'Unexpected real core exit retains its exact generation and nonzero exit code',
    'A replacement core preserves the old generation exit history',
    'Requested stop is distinguished from an unexpected real core exit',
    'Incomplete recovery provides a separate exact-route retention outcome',
    'Candidate control failure reports failure without stopping the exact verified WSS route',
    'Candidate control failures back off optimization without changing detector retry state',
    'Automatic candidate verification failure reselects and really reverifies the previous entry',
    'Rollback does not publish the failed candidate as the selected quality route',
    'Busy reply or attachment work prevents the manual route transaction before mutation',
    'Reply or upload beginning during fresh identity lookup prevents selection',
    'Exit detector backoff does not suppress corroborated failed-chain recovery',
    'All network repair faults preserve one live WSS and fixed exit',
    'A failed rollback verification stops admission instead of reusing the old receipt',
})

def verify_network_repair_evidence(network):
    checks = {item['name']: item['pass'] for item in network['checks']}
    assert NETWORK_REPAIR_CHECKS <= checks.keys(), 'Network repair regression cases are required.'
    assert all(checks[name] is True for name in NETWORK_REPAIR_CHECKS)
    evidence = network['networkRepairEvidence']
    assert type(evidence['schema']) is int and evidence['schema'] == 1 and evidence['serviceGenerationStopGuard'] is True
    assert evidence['exitDiagnostics'] is True and evidence['retainedOutcome'] is True
    candidate = evidence['candidateFailure']
    assert candidate['accepted'] is False
    assert all(candidate[key] is True for key in ('sameReceipt', 'sameCore', 'sameEntry', 'verified', 'optimizationBackoff'))
    rollback = evidence['rollback']
    assert type(rollback['exitRequests']) is int and rollback['exitRequests'] == 2
    assert all(rollback[key] is True for key in ('newReceipt', 'sameEntry', 'verified', 'sameCore'))
    assert evidence['busyBeforeMutation'] is True
    recovery = evidence['backoffRecovery']
    assert type(recovery['exitRequests']) is int and recovery['exitRequests'] == 1
    assert all(recovery[key] is True for key in ('entryChanged', 'verified', 'sameCore', 'sameWebSocket', 'detectorRetryReset'))
    failed = evidence['failedRollback']
    assert all(failed[key] is False for key in ('ready', 'coreAlive', 'receiptCurrent'))
    assert failed['webSocketClosed'] is True
    return {'boundedExitDiagnostics': True, 'retainedIsNotRecovered': True,
            'candidateFailureKeepsVerifiedRoute': True, 'rollbackRequiresNewVerification': True}


BUSY_BOOTSTRAP_CHECKS = frozenset(
    prefix + path for path in ('remembered', 'first-verified') for prefix in (
        'Busy fresh service startup verifies its fixed exit through ',
        'Busy admitted service route cannot borrow startup permission in ',
        'Direct rebuild retires stale ready state and verifies a new busy core in '))


def verify_busy_bootstrap_evidence(network):
    checks = {row['name']: row['pass'] for row in network['checks']}
    assert BUSY_BOOTSTRAP_CHECKS <= checks.keys()
    assert all(checks[name] is True for name in BUSY_BOOTSTRAP_CHECKS)
    rows = network['busyBootstrap']
    assert len(rows) == 2 and [row['path'] for row in rows] == ['remembered', 'first-verified']
    for row in rows:
        for field in ('busyBefore', 'busyAfter', 'callbackAccepted', 'receiptCurrent', 'busyLiveSwitchBlocked'):
            assert row[field] is True, field
        assert type(row['exitRequests']) is int and row['exitRequests'] > 0
        first, rebuilt = row['first'], row['directRebuild']
        assert rebuilt['verified'] is True and rebuilt['busyAfter'] is True
        assert type(rebuilt['exitRequests']) is int and rebuilt['exitRequests'] > 0
        second = rebuilt['replacement']
        for state in (first, second):
            assert state['alive'] is True
            for field in ('pid', 'servicePid', 'controllerPort', 'proxyPort'):
                assert type(state[field]) is int and state[field] > 1
            for field in ('generation', 'configuration', 'entry', 'exitIp'):
                assert isinstance(state[field], str) and state[field]
            assert isinstance(state['tokenHash'], str) and len(state['tokenHash']) == 64
        assert first['generation'] != second['generation'] and first['pid'] != second['pid']
        assert first['configuration'] == second['configuration'] and first['exitIp'] == second['exitIp']
    return {'busyInitialRouteVerified': True, 'liveSwitchStillFenced': True,
            'directRebuildUsesNewVerifiedCore': True}


def verify_connection_evidence(directory, source):
    directory = pathlib.Path(directory)

    def android(name):
        report = json.loads((directory / name).read_text())
        assert report['sourceCommit'] == source and report['status'] == 'passed'
        assert report['actualAndroidExecution'], name
        assert all(check['pass'] for check in report['checks']), name
        return report

    gecko = android('gecko-performance-results.json')
    assert gecko['actualGeckoExecution'] and gecko['actualGeckoBindingRegressionExecution']
    inputs = gecko['actualAndroidTextInputs']
    assert len(inputs) == 1 and inputs[0]['id'] == 'current-input'
    assert inputs[0]['composerFocused'] and inputs[0]['nativeFocused'] and inputs[0]['acceptingText']
    assert inputs[0]['stableFocusSamples'] >= 2
    assert gecko['checkCount'] == len(gecko['checks']) >= 125
    names = {check['name'] for check in gecko['checks']}
    assert {
        'Same-route empty DOM waits without losing the confirmed task or accumulating terminal samples',
        'Virtualizing only the bound user waits even while other historical messages remain',
        'Homepage allocation rejects the same user ID when its prompt no longer matches',
        'Homepage conversation allocation preserves the exact user identity and persists the new route',
        'A genuine different conversation is rejected even if its visible message IDs match',
        'A neutral homepage shell during restoration waits without declaring another conversation',
        'SPA restoration and websocket faults never resubmit and preserve the typed draft and synthetic login',
        'Actual native inspection recognizes the website socket fault before polling and resets terminal stability',
        'A rendered historical reply socket alert and retry control do not invalidate the current task',
        'Website errors clear native stable samples and never finish or clear the persisted task',
        'A restored bound reply completes only after three fresh actual samples and two seconds',
        'Manual website recovery durably archives its captured draft before checking newer typing',
        'Typing while manual recovery saves aborts reload and preserves the newer draft and original pending task',
        'Manual website recovery durably archives its captured draft even when the pending task changes',
        'Changing the pending task while manual recovery saves aborts stale reload and preserves the new task',
        'Connection invalidation resets native terminal samples without submitting or clearing browser data',
    } <= names, 'Actual Gecko loading and route binding regression is required.'

    network = android('network-performance-results.json')
    assert network['actualMihomoExecution']
    assert len(network['checks']) >= 143
    names = {check['name'] for check in network['checks']}
    assert {
        'The live core and selected route have a successful exit verification receipt',
        'A real WSS connection carries continuous frames through both Mihomo SOCKS hops',
        'A temporary exit HTTP failure preserves the same WSS core and fixed route',
        'A real exit read timeout leaves the existing WSS tunnel responsive',
        'An invalid exit service response preserves only the previously verified route',
        'Exit verification failure schedules bounded retry without claiming fresh success',
        'Exit verification backoff makes no repeated IP requests or WebSocket replacement',
        'Send preflight admits the exact retained route with degraded verification',
        'Same-route recovery reports incomplete verification while retaining admission during detector outage',
        'Primary detector outage with target HTTP 200 preserves verified route',
        'Primary detector outage with target HTTP 403 preserves verified route',
        'Primary detector outage with target HTTP 429 preserves verified route',
        'Primary detector outage with target HTTP 503 preserves verified route',
        'Busy health does not issue either primary or secondary request',
        'Injected target SSLProtocolException never replaces or stops the actual WSS route',
        'Injected target SSLException never replaces or stops the actual WSS route',
        'Injected target SSLHandshakeException never replaces or stops the actual WSS route',
        'One paired transport failure keeps the route suspect',
        'Reachable target clears paired-failure suspicion despite continued primary outage',
        'A recovered exit service renews proof and resets the retry state',
        'All temporary verification faults retain one WebSocket and one core generation',
        "An actual entry change invalidates the previous route's verification receipt",
        'An unverified changed route fails closed when the exit service is unavailable',
        'A new core has no inherited in-memory verification receipt',
        'First connection requires actual exit verification and never accepts an outage',
        'A confirmed exit IP mismatch still blocks recovery and closes the real WebSocket',
        'Independent network service retains the same WSS and core during exit HTTP failure',
        'Independent network service retains the same WSS and core during a real exit timeout',
        'Independent network service retains the same WSS and core during invalid exit response',
        'Independent network service renews exit proof without replacing the original WebSocket',
        'Cancelled maintenance fails closed after an actual unverified entry change',
        'A confirmed service exit mismatch still stops the core when maintenance is concurrently cancelled',
        'Independent network service retains the same WSS and core during detector reset',
        'Independent network service retains the same WSS and core during detector eof',
        'Detector reset preflight admits only the retained verified WSS route',
        'Detector eof preflight admits only the retained verified WSS route',
        'An unverified changed route rejects detector reset and closes its WSS',
        'An unverified changed route rejects detector eof and closes its WSS',
        'First connection rejects detector reset without inheriting a route receipt',
        'First connection rejects detector eof without inheriting a route receipt',
        'Detector transport classification excludes cancellation TLS identity and configuration failures',
    } <= names, 'Real protected WebSocket continuity and unknown-route rejection are required.'
    transport = verify_detector_transport_evidence(network)
    repairs = verify_network_repair_evidence(network)
    bootstrap = verify_busy_bootstrap_evidence(network)
    cold_probe = verify_cold_website_probe_diagnostics(network)

    host = json.loads((directory / 'reply-binding-host-results.json').read_text())
    assert host['passed'] == host['total'] >= 41 and all(check['pass'] for check in host['checks'])
    names = {check['name'] for check in host['checks']}
    assert {
        'A visible historical assistant alert cannot interrupt the current healthy reply',
        'A user-quoted alert cannot become an active website failure during inspection',
        'A real current-turn alert beside its reply body remains recoverable',
        'Read-only waiting, recovery and assignment never resend the question',
    } <= names, 'Current website errors must remain distinct from historical or quoted content.'
    framework_binding = verify_framework_binding_files(directory, source)
    return {'actualAndroidExecution': True, 'actualGeckoExecution': True,
            'actualMihomoExecution': True, 'geckoChecks': gecko['checkCount'],
            'networkChecks': len(network['checks']), 'bindingHostChecks': host['total'],
            'detectorTransport': transport, 'networkRepairs': repairs, 'busyBootstrap': bootstrap,
            'coldWebsiteProbeDiagnostic': cold_probe, 'frameworkClientBinding': framework_binding}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('directory', type=pathlib.Path)
    parser.add_argument('--source', required=True)
    args = parser.parse_args()
    print(json.dumps(verify_connection_evidence(args.directory, args.source), indent=2))
