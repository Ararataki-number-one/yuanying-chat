"""Pure JSON contracts shared by Android runners and the public release gate."""
import hashlib
import re

PAYLOAD = 'pool-payload-' * 700


def verify_native_probe(report, receipt):
    assert report['status'] == 'passed', report
    assert report['actualAndroidExecution'] and report['actualMihomoExecution'], report
    assert report['actualAuthenticatedSocksChain'] and report['probeSchema'] == 1, report
    assert re.fullmatch(r'[0-9a-f]{64}', report['coreSha256']), report
    assert report['coreAbi'] == 'x86_64' and report['coreVersion'] == receipt['recipe']['version'], report
    assert report['coreSha256'] == receipt['binaries'][report['coreAbi']]['sha256'], 'Android executed another native binary'
    assert len(report['checks']) >= 57 and all(row['pass'] for row in report['checks']), report
    assert report['originalRoute'] == report['finalRoute'], report
    assert report['originalRoute']['verified'] and report['originalRoute']['pid'] > 1, report
    assert report['webSocketConnections'] == 1 and report['webSocketEchoes'] >= 5, report
    assert report['entryCircuits'] == report['fixedExitCircuits'] > 5, report
    readings = {row['name']: row for row in report['measurements']}
    warm = readings['keep-alive warm']
    cold = readings['connection-close cold retest']
    fallback = readings['second-response reset fallback']
    for row, kind, reused in [(warm, 'warm', True), (cold, 'cold-retest', False),
                               (fallback, 'cold-fallback', None)]:
        response = row['response']
        p = response['probe']
        assert row['httpStatus'] == 200 and p['schema'] == 1 and p['kind'] == kind, row
        assert p['warmAttempted'] and isinstance(p['secondConnectionReused'], bool), row
        assert p['firstMs'] > 0 and p['warmMs'] >= 0, row
        assert p['totalMs'] >= p['firstMs'] + p['warmMs'], row
        ids = row['wireConnectionIds']
        assert p['dialCount'] == row['entryCircuits'] == row['fixedExitCircuits'], row
        assert p['attempts'] == len(ids), row
        if reused is not None:
            assert p['secondConnectionReused'] is reused and len(ids) == 2, row
            assert (ids[0] == ids[1]) is reused, row
            assert row['entryCircuits'] == row['fixedExitCircuits'] == (1 if reused else 2), row
        else:
            assert 2 <= len(ids) <= 3 and ids[0] == ids[1], row
            assert row['entryCircuits'] == row['fixedExitCircuits'] and 1 <= row['entryCircuits'] <= 2, row
        assert response['delay'] == p['firstMs' if kind == 'cold-fallback' else 'warmMs'], row
    assert warm['response']['probe']['warmSucceeded'], warm
    assert cold['response']['probe']['warmSucceeded'], cold
    p = fallback['response']['probe']
    assert not p['warmSucceeded'] and p['warmError'] == 'transport' and p['warmMs'] >= 200, fallback
    assert p['totalMs'] - fallback['response']['delay'] > 150, fallback
    cases = {row['path']: row for row in report['cancellations']}
    assert set(cases) == {'/cancel-first', '/cancel-second', '/cancel-java-first', '/cancel-java-second'}, cases
    for path, count in [('/cancel-first', 1), ('/cancel-second', 2),
                        ('/cancel-java-first', 1), ('/cancel-java-second', 2)]:
        c = cases[path]
        assert c['expectedHeads'] == c['actualHeads'] == count, c
        assert 0 <= c['nativeCloseMs'] < 1500 < c['nativeTimeoutMs'], c
        assert c['targetObservedNativeEofAt'] - c['controllerClosedAt'] == c['nativeCloseMs'], c
        assert not c['serverClosedSocketBeforeEof'] and not c['javaFutureCancelled'], c
        if path.startswith('/cancel-java-'):
            assert c['mechanism'] == 'production-maintenance' and c['javaProbeDelay'] < 0, c
        else:
            assert c['mechanism'] == 'raw-controller-client', c
        heads = [r for r in report['nativeWire'] if r['kind'] == 'head' and r['path'] == path]
        eof = [r for r in report['nativeWire'] if r['kind'] == 'blocked-read-ended' and r['path'] == path]
        assert len(heads) == count and len(eof) == 1 and eof[0]['next'] == -1, (heads, eof)
    bad = readings['bad-first-status']['response']['probe']
    assert bad['error'] == 'unexpected-status' and bad['firstStatus'] == 403, bad
    tls = readings['untrusted-tls']
    assert tls['httpStatus'] >= 400 and 'delay' not in tls['response'], tls
    assert tls['response']['probe']['firstMs'] == -1 and not report['untrustedTlsWire'], tls


def verify_gecko_pool(report, server):
    assert report['status'] == 'passed', report.get('error')
    assert report['actualAndroidExecution'] and report['actualGeckoExecution'] and report['actualMihomoExecution']
    assert report['protocol'] == server['protocol'] == 'h2'
    assert len(report['checks']) >= 55 and all(c['pass'] for c in report['checks'])
    expected = ['initial', 'warm', 'healthy-recovery', 'legacy-before', 'legacy-after', 'route-a', 'route-b',
                'returned-a', 'core-restarted', 'network-b', 'network-return-a', 'alternate-pool',
                'guard-blocked', 'receipt-blocked', 'unknown-network-blocked', 'guard-restored']
    by_id = {row['id']: row for row in report['requests']}
    assert list(by_id) == expected and len(report['requests']) == len(expected)
    blocked = {'guard-blocked', 'receipt-blocked', 'unknown-network-blocked'}
    observed = [r for r in server['requests'] if r['path'] == '/bytes']
    assert len(observed) == len(expected) - len(blocked), observed
    assert {r['id'] for r in observed} == set(expected) - blocked
    assert not any(r.get('unexpectedHttp1') for r in server['requests']), server
    for row in observed:
        native = by_id[row['id']]
        assert native['ok'] and native['protocol'] == row['protocol'] == 'h2'
        assert native['connection'] == row['connection'] > 0 and native['streamId'] == row['streamId'] > 0
        assert native['bodyBytes'] == len(PAYLOAD) and native['bodyHash'] == hashlib.sha256(PAYLOAD.encode()).hexdigest()
        assert native['durationMs'] >= 0
        assert row['closed'] and row['responseBytes'] > len(PAYLOAD) and row['responseSha256']
    assert by_id['initial']['connection'] == by_id['warm']['connection'] == by_id['healthy-recovery']['connection']
    for a, b in [('legacy-before', 'legacy-after'), ('route-a', 'route-b'), ('route-a', 'returned-a'),
                 ('returned-a', 'core-restarted'), ('core-restarted', 'network-b'),
                 ('core-restarted', 'network-return-a'), ('network-return-a', 'alternate-pool'),
                 ('network-return-a', 'guard-restored')]:
        assert by_id[a]['connection'] != by_id[b]['connection'], (a, b)
    transitions = {row['name']: row for row in report['transitions']}
    healthy = transitions['healthy-managed-recovery']
    assert healthy['before']['poolKey'] == healthy['after']['poolKey']
    assert healthy['after']['epoch'] == healthy['before']['epoch'] + 1
    for field in ['pid', 'servicePid', 'generation', 'configuration', 'proxyPort', 'controllerPort', 'entry', 'routeSerial', 'fixedExitHash']:
        assert healthy['before'][field] == healthy['after'][field], field
    assert healthy['before']['verified'] and healthy['after']['verified']
    legacy = transitions['legacy-counterfactual-healthy-recovery']
    assert legacy['before']['poolKey'] == legacy['after']['poolKey']
    assert legacy['after']['epoch'] == legacy['before']['epoch'] + 1
    for field in ['pid', 'servicePid', 'generation', 'configuration', 'proxyPort', 'controllerPort', 'entry', 'routeSerial', 'fixedExitHash']:
        assert legacy['before'][field] == legacy['after'][field], field
    a = transitions['real-entry-a-to-b']['before']
    b = transitions['real-entry-a-to-b']['after']
    returned = transitions['real-entry-b-to-a']['after']
    assert a['entry'] == returned['entry'] == 'Entry|a' and b['entry'] == 'Entry|b'
    assert a['routeSerial'] < b['routeSerial'] < returned['routeSerial']
    assert len({a['poolKey'], b['poolKey'], returned['poolKey']}) == 3
    assert a['fixedExitHash'] == b['fixedExitHash'] == returned['fixedExitHash']
    changed = by_id['route-b']
    assert changed['entry'] == 'Entry|b' and changed['entryBConnectionsAfter'] > changed['entryBConnectionsBefore']
    assert changed['fixedConnectionsAfter'] > changed['fixedConnectionsBefore']
    assert len(server['webSockets']) == 1 and server['webSockets'][0]['frames'] >= report['webSocketAfter']['echoes']
    before, after = report['webSocketBefore'], report['webSocketAfter']
    assert before['connection'] == after['connection'] == server['webSockets'][0]['connection'] > 0
    assert after['echoes'] > before['echoes'] >= 5 and not before['closed'] and not after['closed']
    assert all(row['route'].get('type') != 'direct' for row in report['routes'])
    for id_value in blocked:
        candidates = [r for r in report['routes'] if '/bytes?id=' + id_value in r['url']]
        assert candidates and all(r['route'] == {'type': 'socks', 'host': '127.0.0.1', 'port': 9,
                                                'proxyDNS': True, 'failoverTimeout': 1} for r in candidates), id_value
    assert report['fixedExitConnections'] > 0 and report['entryAConnections'] > 0 and report['entryBConnections'] > 0
    assert report['publicNetworkTraffic'] is False
