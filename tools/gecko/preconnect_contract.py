"""Require real, source-bound Android preauthenticated SOCKS/H2 wire evidence."""
import hashlib

PAYLOAD = 'pool-payload-' * 700


def verify_preconnect(report, receipt):
    assert report['status'] == 'passed', report.get('error')
    assert not report.get('diagnosticOnly', False)
    assert report['actualAndroidExecution'] and report['actualGeckoExecution'] and report['actualMihomoExecution']
    assert report['actualAuthenticatedSocksChain'] and report['publicNetworkTraffic'] is False
    assert report['productionConfigOptIn'] is True
    assert report['coreAbi'] == 'x86_64' and report['coreVersion'] == receipt['recipe']['version']
    assert report['coreSha256'] == receipt['binaries']['x86_64']['sha256']
    assert report['protocol'] == report['server']['protocol'] == 'h2'
    assert len(report['checks']) >= 65 and all(row['pass'] for row in report['checks'])
    assert report['authStageDelayMs'] == 180
    requests = {row['id']: row for row in report['requests']}
    assert len(requests) == len(report['requests'])
    required = {'baseline-0', 'baseline-1', 'baseline-2', 'enabled-0', 'enabled-1', 'enabled-2',
                'route-b', 'returned-a', 'network-generation', 'network-return-a', 'blocked-epoch', 'epoch-restored',
                'expired', 'dead-idle', 'rejected-auth', 'auth-restored', 'guard-blocked', 'guard-restored',
                'inflight-trigger', 'refill-bounded-0', 'refill-bounded-1', 'refill-bounded-2'}
    assert set(requests) == required
    observed = [row for row in report['server']['requests'] if row['path'] == '/bytes']
    assert len(observed) == len(required) - 2
    assert {row['id'] for row in observed} == required - {'rejected-auth', 'guard-blocked'}
    assert not any(row.get('unexpectedHttp1') for row in report['server']['requests'])
    browser_ids = []
    for row in observed:
        actual = requests[row['id']]
        assert actual['ok'] and actual['expected'] and actual['protocol'] == row['protocol'] == 'h2'
        assert actual['connection'] == row['connection'] > 0 and actual['streamId'] == row['streamId'] > 0
        assert actual['bodyHash'] == hashlib.sha256(PAYLOAD.encode()).hexdigest()
        assert actual['fixedTargetContactsAfter'] == actual['fixedTargetContactsBefore'] + 1
        assert actual['fixedCircuit']['targetPort'] == 9878
        assert actual['beganAtNs'] <= actual['fixedCircuit']['connectAtNs'] <= actual['endedAtNs']
        browser_ids.append(actual['connection'])
    assert len(set(browser_ids)) == len(browser_ids), 'Cold browser requests reused TLS connections'
    for name in ['rejected-auth', 'guard-blocked']:
        row = requests[name]
        assert not row['ok'] and not row['expected'] and row['fixedCircuit'] is None
        assert row['fixedTargetContactsBefore'] == row['fixedTargetContactsAfter']
    assert len(report['pairedTrials']) == 3
    for index, pair in enumerate(report['pairedTrials']):
        assert pair['index'] == index and pair['baseline'] == requests[f'baseline-{index}']
        assert pair['enabled'] == requests[f'enabled-{index}']
        baseline, enabled = pair['baseline'], pair['enabled']
        cold, prepared = baseline['fixedCircuit'], enabled['fixedCircuit']
        assert baseline['beganAtNs'] <= cold['methodAtNs'] < cold['authAtNs'] < cold['connectAtNs']
        assert prepared['methodAtNs'] < prepared['authAtNs'] < enabled['beganAtNs'] <= prepared['connectAtNs']
        assert cold['authAtNs'] - cold['methodAtNs'] >= 2 * report['authStageDelayMs'] * 1_000_000
        assert prepared['authAtNs'] - prepared['methodAtNs'] >= 2 * report['authStageDelayMs'] * 1_000_000
        assert prepared['id'] != cold['id']
        assert pair['savedMs'] == baseline['durationMs'] - enabled['durationMs'] > report['authStageDelayMs']
    cases = {row['name']: row for row in report['cases']}
    assert set(cases) == {'route-a-b-a', 'network-generation', 'network-return-a', 'blocked-epoch', 'expiry', 'dead-idle',
                          'auth-rejection', 'native-probe-bypass', 'managed-stop-cancellation',
                          'inflight-refill-cancellation'}
    route = cases['route-a-b-a']
    assert route['before']['entry'] == route['after']['entry'] == 'Entry|a'
    assert route['after']['routeSerial'] >= route['before']['routeSerial'] + 2
    assert route['before']['pid'] == route['after']['pid'] > 1
    assert route['before']['generation'] == route['after']['generation']
    assert len({route['oldA']['id'], route['oldB']['id'], route['b']['fixedCircuit']['id'],
                route['returnedA']['fixedCircuit']['id']}) == 4
    for stale in [route['oldA'], route['oldB'], cases['network-generation']['stale'], cases['network-return-a']['stale'],
                  cases['blocked-epoch']['stale'], cases['expiry']['stale']]:
        assert stale['authAtNs'] > 0 and stale['connectAtNs'] == stale['targetPort'] == 0
        assert stale['eofAtNs'] > stale['authAtNs'] and stale['closedAtNs'] >= stale['eofAtNs']
        assert not stale['serverClosed']
    for name in ['network-generation', 'network-return-a']:
        case = cases[name]
        assert case['networkEventsInjected'] is True and case['epochBeforeHash'] != case['epochAfterHash']
        assert case['request']['fixedCircuit']['authAtNs'] >= case['changedAtNs']
    network_b, network_a = cases['network-generation'], cases['network-return-a']
    assert network_b['epochAfterHash'] == network_a['epochBeforeHash']
    assert network_b['epochBeforeHash'] != network_a['epochAfterHash']
    expiry = cases['expiry']['stale']
    assert 7_000_000_000 <= expiry['eofAtNs'] - expiry['authAtNs'] <= 10_000_000_000
    assert cases['dead-idle']['stale']['serverClosed']
    assert cases['auth-rejection']['deniedAfter'] > cases['auth-rejection']['deniedBefore']
    probe = cases['native-probe-bypass']
    assert probe['newFixedSockets'] == 1 and probe['idle']['connectAtNs'] == 0
    telemetry = probe['response']['probe']
    assert telemetry['secondConnectionReused'] and telemetry['warmSucceeded']
    assert telemetry['firstMs'] >= 2 * report['authStageDelayMs']
    assert telemetry['warmMs'] >= 0 and probe['response']['delay'] == telemetry['warmMs']
    assert telemetry['kind'] == 'warm' and telemetry['totalMs'] >= telemetry['firstMs'] + telemetry['warmMs']
    stopped = cases['managed-stop-cancellation']
    assert stopped['socket']['connectAtNs'] == 0 and not stopped['socket']['serverClosed']
    assert 0 <= stopped['socket']['eofAtNs'] - stopped['cancelledAtNs'] < 2_000_000_000
    pending = cases['inflight-refill-cancellation']
    assert pending['pendingRefillLimit'] == pending['idleSocketLimit'] == 1
    assert pending['socket']['holdingAuthAtNs'] > pending['socket']['methodAtNs'] > 0
    assert pending['socket']['authAtNs'] == pending['socket']['connectAtNs'] == pending['socket']['targetPort'] == 0
    assert not pending['socket']['serverClosed']
    assert 0 <= pending['socket']['eofAtNs'] - pending['cancelledAtNs'] < 2_000_000_000
    assert len(pending['requests']) == 3
    for i, row in enumerate(pending['requests']):
        assert row['request'] == requests[f'refill-bounded-{i}']
        assert row['pendingRefillCount'] == 1 and row['idleSocketCount'] == 0
        assert row['pendingRefillCircuit'] == pending['socket']['id']
    before, after = report['webSocketBefore'], report['webSocketAfter']
    assert before['connection'] == after['connection'] > 0
    assert after['echoes'] > before['echoes'] >= 5 and not before['closed'] and not after['closed']
    sockets = report['server']['webSockets']
    assert len(sockets) == 1 and sockets[0]['connection'] == before['connection']
    assert sockets[0]['frames'] >= after['echoes']
    assert all(row['route'].get('type') != 'direct' for row in report['routes'])
    blocked = [row for row in report['routes'] if '/bytes?id=guard-blocked' in row['url']]
    assert blocked and all(row['route'] == {'type': 'socks', 'host': '127.0.0.1', 'port': 9,
                                          'proxyDNS': True, 'failoverTimeout': 1} for row in blocked)
    assert report['entryAWire'] and report['entryBWire'] and report['fixedWire']
    for circuit in report['fixedWire']:
        assert circuit['connectAtNs'] == 0 or circuit['connectAtNs'] > circuit['authAtNs'] > 0
        assert circuit['connectAtNs'] != 0 or circuit['targetPort'] == 0
    return {'actualAndroidExecution': True, 'actualGeckoHttp2Execution': True,
            'actualAuthenticatedSocksChain': True, 'pairedColdRequests': 3,
            'targetContactsBeforeConnect': 0, 'nativeProbeSemanticsPreserved': True,
            'controlledSavingsMs': [row['savedMs'] for row in report['pairedTrials']],
            'wanSpeedClaim': False, 'checks': len(report['checks'])}
