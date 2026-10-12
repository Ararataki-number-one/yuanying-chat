"""Require independent source libraries, actual Android dialogs and a pinned native chain."""
import hashlib
import json
import math
import pathlib
import re

PAYLOAD = 'pool-payload-' * 700
SUCCESS = {'subscribed-a', 'subscribed-b', 'after-probes', 'restored-subscription', 'legacy-manual'}
FAILURE = {'invalid-entry-snapshot-sha', 'invalid-exit-snapshot-sha', 'same-name-changed-exit', 'same-name-changed-entry'}
SAFE_IDLE_CASES = ['prepare-send', 'capture-send', 'prepare-transfer', 'capture-navigation',
                   'capture-delete', 'complete-delete', 'complete-late-save']


def _hash(value, length=64):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{' + str(length) + '}', value) is not None


def _core_matches(report, receipt):
    assert report['coreAbi'] == 'x86_64'
    assert report['coreVersion'] == receipt['recipe']['version']
    assert report['coreSha256'] == receipt['binaries']['x86_64']['sha256']


def verify_safe_idle(report):
    """Replay the actual report's gestures/events without runner-global state."""
    assert report['status'] == 'passed', report.get('error')
    assert not report.get('diagnosticOnly', False)
    assert _hash(report['sourceCommit'], 40) and _hash(report['installedApkSha256'])
    assert report['installedPackage'] == 'local.pocketchat.test'
    assert report['coreAbi'] == 'x86_64' and _hash(report['coreSha256'])
    assert isinstance(report['coreVersion'], str) and report['coreVersion']
    for key in ('actualAndroidExecution', 'actualGeckoExecution', 'actualNativeParsing', 'actualNativeExecution', 'actualKeystoreEncryption'):
        assert report[key] is True, key
    assert report['actualRouteApplication'] is False and report['actualPublicWebsite'] is False
    gestures, events = report['actualAndroidGestures'], report['phaseEvents']
    assert report['runnerOneAttemptPerGesture'] is True
    assert report['parseCount'] == 2 and report['actualTrustedGestures'] == 2 and len(gestures) == 2
    assert report['proxyAccepted'] > 0 and report['proxyRejected'] >= 0 and report['pageDocuments'] > 0
    assert 0 < report['controlledTlsPort'] <= 65535 and report['proxyUpstreamConnections']
    assert len(report['proxyUpstreamConnections']) == report['proxyAccepted']
    assert all(value == f"127.0.0.1:{report['controlledTlsPort']}" for value in report['proxyUpstreamConnections'])
    assert report['certificateExceptions'] == 1
    assert report['checkCount'] == len(report['checks']) >= 56
    assert all(row['pass'] is True for row in report['checks'])
    assert len({row['name'] for row in report['checks']}) == report['checkCount']
    assert 'Packaged native ELF exposes its actual ABI, streamed SHA and controller version' in {row['name'] for row in report['checks']}
    rows = report['cases']
    assert [row['name'] for row in rows] == SAFE_IDLE_CASES
    for row in rows:
        state = row['outcome']
        assert _hash(row['activeAfterHash']) and row['activeAfterHash'] == row['originalActiveHash']
        if row['name'] == 'complete-late-save':
            lineage = row['baselineLineage']
            assert lineage['publishedBaseline'] != lineage['oldBaseline']
            assert lineage['latestBaselineAfter'] == lineage['actualBaselineAfter'] == lineage['oldBaseline']
            assert lineage['latestConfigBeforeHash'] == lineage['latestConfigAfterHash']
            assert lineage['entrySnapshotRetained'] is True and lineage['exitSnapshotRetained'] is True
            assert lineage['entryPayloadBeforeHash'] == lineage['entryPayloadAfterHash']
            assert lineage['exitPayloadBeforeHash'] == lineage['exitPayloadAfterHash']
            for field in ('candidateChangedOnlyBaselineAndConsumedLineage', 'lineageConsumed', 'laterValidationPassed'):
                assert lineage[field] is True, field
        else:
            assert row['pendingBeforeHash'] == row['pendingAfterHash']
        assert state['job']['done'] is True and state['job']['ok'] is True
        assert state['confirmed'] is False and row['reconnectAttempts'] == 0
        assert not state['operation'] and not state['configurationCapture'] and state['touchRestored'] is True
        if row['name'].endswith('send'):
            assert row['actualTrustedGesture'] is True and row['injectedState'] == 'none' and state['replyId']
        else:
            assert row['actualTrustedGesture'] is False and row['injectedState'] in ('transfer', 'navigation', 'delete', 'late-save')
            assert not state['replyId']
        if not row['name'].startswith('prepare'):
            assert row['actualInspectDelta'] >= 2 and row['actualPageStateDelta'] == 1

    phase_rows = [event['value'] for event in events if event.get('kind') == 'phase']
    phases = {row['case']: row for row in phase_rows}
    assert len(phases) == len(phase_rows) == 6
    assert set(phases) == set(SAFE_IDLE_CASES) - {'complete-delete'}
    assert not phases['prepare-send']['operation'] and not phases['prepare-send']['configurationCapture']
    assert phases['capture-send']['operation'] is True and phases['capture-send']['configurationCapture'] is True
    for name, phase in phases.items():
        assert phase['phase'] == ('prepare' if name.startswith('prepare') else 'commit' if name.startswith('capture') else 'complete')
    trusted = [event['value'] for event in events if event.get('kind') == 'gesture']
    assert [row['case'] for row in trusted] == ['prepare-send', 'capture-send']
    assert all(row['trusted'] is True and row['sent'] == 1 for row in trusted)
    assert [row['case'] for row in gestures] == ['prepare-send', 'capture-send']
    taps = [event['value'] for event in events if event.get('kind') == 'tapNeeded']
    assert len(taps) == 2
    for gesture, observed, tap, case in zip(gestures, trusted, taps, rows[:2]):
        assert gesture['oneAttempt'] is True and gesture['bounds'] == tap
        assert observed['replyId'] == case['outcome']['replyId']
        assert observed['observedBy'] == 'Production Gecko extension → WebReplyObserver.receive'
        css, native = tap['css'], tap['native']
        assert all(isinstance(value, (int, float)) and math.isfinite(value) for value in (*css.values(), *native.values()))
        assert css['width'] > 0 and css['height'] > 0 and native['width'] > 0 and native['height'] > 0
        sx, sy = native['width'] / css['width'], native['height'] / css['height']
        assert abs(sx - sy) <= .12 * max(sx, sy)
        x, y = round(native['x'] + css['x'] * sx), round(native['y'] + css['y'] * sy)
        assert native['x'] <= x < native['x'] + native['width'] and native['y'] <= y < native['y'] + native['height']
        assert gesture['x'] == x and gesture['y'] == y
        assert gesture['command'] == ['shell', 'input', 'tap', str(x), str(y)]
    case_events = [event['value'] for event in events if event.get('kind') == 'case']
    assert case_events == rows
    late = [event['value'] for event in events if event.get('kind') == 'injection' and event['value']['case'] == 'complete-delete']
    assert len(late) == 1 and late[0]['newGeneration'] == late[0]['oldGeneration'] + 1
    assert late[0]['commitPrecededDeletion'] is True
    saved = [event['value'] for event in events if event.get('kind') == 'injection' and event['value']['case'] == 'complete-late-save']
    assert len(saved) == 1
    assert saved[0]['oldBaseline'] == rows[-1]['baselineLineage']['oldBaseline']
    assert saved[0]['publishedBaseline'] == rows[-1]['baselineLineage']['publishedBaseline']
    results = [event['value'] for event in events if event.get('kind') == 'result']
    assert len(results) == 1 and results[0]['status'] == 'passed' and results[0]['checkCount'] == report['checkCount']
    return {'actualAndroidExecution': True, 'actualGeckoExecution': True, 'actualNativeParsing': True,
            'safeIdleCases': len(rows), 'actualTrustedGestures': len(gestures), 'checks': report['checkCount'],
            'sourceBoundInstalledApkSha256': report['installedApkSha256'], 'wanSpeedClaim': False}

def verify_source_route(report,server,receipt,source):
    assert report['schema']==1 and report['sourceCommit']==source and report['status']=='passed',report.get('error')
    for key in ['actualAndroidExecution','actualMihomoExecution','actualGeckoExecution','actualAuthenticatedSocksChain','actualKeystoreEncryption','actualRouteApplication']:
        assert report[key] is True,key
    assert report['publicNetworkTraffic'] is False and report['coreAbi']=='x86_64'
    assert report['coreVersion']==receipt['recipe']['version']
    assert report['coreSha256']==receipt['binaries']['x86_64']['sha256']
    assert len(report['checks'])>=69 and all(row['pass'] is True for row in report['checks'])
    refs=report['sourceRefs'];assert refs['subscriptionUrl']==refs['exitSubscriptionUrl']
    assert refs['entrySubscriptionId']!=refs['exitSubscriptionId'] and refs['exitSource']=='subscription'
    assert len(refs['exitNodeKey'])==64 and len(refs['entryPoolKeys'])==2
    for seal in report['sealedSnapshots'].values():
        assert seal['ivBytes']==12 and seal['sealedBytes']==seal['plainBytes']+29
        assert seal['matchesPlaintext'] is False and seal['decryptedMatches'] is True and seal['nonExportableKeystoreKey'] is True
    assert set(report['sealedSnapshots'])=={'entry','exit'}
    providers=report['generatedConfig']['proxy-providers']
    assert providers['Subscription']['type']==providers['ExitSource']['type']=='file'
    assert providers['Subscription']['path']=='./subscription.yaml' and providers['ExitSource']['path']=='./exit-subscription.yaml'
    assert providers['ExitSource']['override']['pocket-config-fingerprint']==refs['exitNodeKey']
    assert providers['ExitSource']['override']['dialer-proxy']=='EntryChoice'
    assert report['generatedConfig']['rules']==['MATCH,REJECT']
    initial,switched,probed=(report[key] for key in ['initial','switched','afterProbes'])
    assert all(row['verified'] for row in [initial,switched,probed])
    assert initial['currentEntry']=='Entry|a' and switched['currentEntry']==probed['currentEntry']=='Entry|b'
    assert initial['pid']==switched['pid']==probed['pid']>1 and initial['generation']==switched['generation']==probed['generation']
    assert initial['fixedIdentity']==switched['fixedIdentity']==probed['fixedIdentity']
    assert initial['fixedNodeFingerprint']==switched['fixedNodeFingerprint']==probed['fixedNodeFingerprint']==refs['exitNodeKey']
    assert initial['fixedNodeName']==switched['fixedNodeName']==probed['fixedNodeName']=='FixedExit'
    assert switched['routeSerial']>initial['routeSerial'] and probed['routeSerial']==switched['routeSerial']
    requests={row['id']:row for row in report['requests']};assert len(requests)==len(report['requests'])==9
    assert set(requests)==SUCCESS|FAILURE
    observed={row['id']:row for row in server['requests'] if row['path']=='/bytes'}
    assert set(observed)==SUCCESS and len([row for row in server['requests'] if row['path']=='/bytes'])==5
    assert server['protocol']=='h2' and not any(row.get('unexpectedHttp1') for row in server['requests'])
    for name in SUCCESS:
        row,actual=requests[name],observed[name]
        assert row['ok'] is row['expected'] is True and row['protocol']==actual['protocol']=='h2'
        assert row['connection']==actual['connection']>0 and row['streamId']==actual['streamId']>0
        assert row['bodyHash']==hashlib.sha256(PAYLOAD.encode()).hexdigest()
        assert row['after']['decoyTarget']==0 and row['after']['fixedTarget']>0
    assert requests['subscribed-a']['connection']!=requests['subscribed-b']['connection']
    assert requests['after-probes']['connection']==requests['subscribed-b']['connection']
    assert report['probe']['delay']>0 and report['websiteProbe']['status']=='ok' and report['websiteProbe']['firstMs']>0
    before,candidate,website=(report['probeWire'][key] for key in ['before','afterCandidate','afterWebsite'])
    assert before['entryA']<candidate['entryA']<website['entryA']
    assert before['fixedPlain']<candidate['fixedPlain'] and candidate['fixedSite']<website['fixedSite']
    assert before['fixedBrowser']==candidate['fixedBrowser']==website['fixedBrowser'] and before['decoy']==candidate['decoy']==website['decoy']==0
    negatives={row['name']:row for row in report['negativeCases']};assert set(negatives)==FAILURE
    for name in FAILURE:
        row=negatives[name];req=requests[name]
        assert not row['started'] and not row['readyAfter'] and not row['coreAliveAfter']
        assert row['before']==row['after'] and row['request']==req
        assert req['ok'] is req['expected'] is False
        assert req['before']['fixedTarget']==req['after']['fixedTarget'] and req['before']['decoyTarget']==req['after']['decoyTarget']
    assert not negatives['invalid-entry-snapshot-sha']['entrySnapshotHashValid']
    assert not negatives['invalid-exit-snapshot-sha']['exitSnapshotHashValid']
    for name in ['same-name-changed-exit','same-name-changed-entry']:
        assert negatives[name]['entrySnapshotHashValid'] and negatives[name]['exitSnapshotHashValid']
    assert not report['decoyWire'] and not report['replacementEntryWire']
    assert report['entryAWire'] and report['entryBWire'] and report['fixedWire']
    for key in ['entryAWire','entryBWire','fixedWire']:
        assert all(row['connectAtNs']==0 or row['connectAtNs']>row['authAtNs']>row['methodAtNs']>0 for row in report[key])
    assert 'ExitSource' not in report['legacyConfig']['proxy-providers']
    legacy=[row for row in report['legacyConfig']['proxies'] if row['name']=='FixedExit'];assert len(legacy)==1
    assert legacy[0]['type']=='socks5' and legacy[0]['dialer-proxy']=='EntryChoice'
    assert all(row['route'].get('type')!='direct' for row in report['routes'])
    for name in FAILURE:
        blocked=[row for row in report['routes'] if '/bytes?id='+name in row['url']]
        assert blocked and all(row['route']['type']=='socks' and row['route']['host']=='127.0.0.1' and row['route']['port']==9 for row in blocked)
    return {'actualAndroidExecution':True,'actualGeckoHttp2Execution':True,'actualAuthenticatedSocksChain':True,
            'sameSourceFixedExitAcrossEntrySwitch':True,'independentProbesPreserveBusinessConnection':True,
            'snapshotAndNodeMismatchRejections':4,'legacyManualPathPreserved':True,'checks':len(report['checks']),
            'publicNetworkTraffic':False,'wanSpeedClaim':False}


def verify_network_sources(directory, source, receipt):
    directory = pathlib.Path(directory)

    def report(name):
        value = json.loads((directory / name).read_text())
        assert value['sourceCommit'] == source and value['status'] == 'passed', name
        assert not value.get('diagnosticOnly', False), name
        return value

    for name, minimum in [('network-catalog-host-results.json', 51), ('network-source-host-results.json', 94)]:
        host = json.loads((directory / name).read_text())
        assert host['sourceCommit'] == source and host['actualAndroidExecution'] is False, name
        assert host['passed'] == host['total'] == len(host['checks']) >= minimum, name
        assert all(row['pass'] for row in host['checks']), name
    catalog = json.loads((directory / 'network-catalog-host-results.json').read_text())
    assert catalog['actualCrossProcessFileLocks'] is True
    snapshots = json.loads((directory / 'network-source-host-results.json').read_text())
    assert snapshots['actualCrossProcessSourceLease'] is True and snapshots['actualCrossProcessActiveSnapshotLease'] is True
    lineage = json.loads((directory / 'network-lineage-host-results.json').read_text())
    assert lineage['sourceCommit'] == source and lineage['actualAndroidExecution'] is False
    assert lineage['actualGeckoExecution'] is False and lineage['actualNativeExecution'] is False
    assert not lineage.get('diagnosticOnly', False)
    assert lineage['passed'] == lineage['total'] == len(lineage['checks']) >= 26
    assert all(row['pass'] is True for row in lineage['checks'])
    lineage_names = {row['name'] for row in lineage['checks']}
    assert len(lineage_names) == lineage['total']
    assert {'Exact A rollback rebases its validated B descendant',
            "Lineage rebase preserves B's chosen configuration",
            'Lineage rebase preserves both raw provider payloads',
            'A consumed lineage cannot be replayed',
            'A newer independent candidate remains unchanged by A rollback',
            'Failed rebase publication preserves the latest candidate record',
            'Older completed apply cannot clear the newer candidate pointer',
            'Failed pointer cleanup retains the latest candidate and both payloads',
            'Current exact pointer can cancel its desired configuration',
            'Exact pointer cleanup removes the desired record and both owned payloads',
            'Canceling desired configuration keeps the active baseline unchanged',
            'An already canceled pointer cannot be replayed'} <= lineage_names
    model = report('network-source-results.json')
    for field in ['actualAndroidExecution', 'actualNativeExecution', 'actualMihomoExecution', 'actualKeystoreEncryption']:
        assert model[field] is True, field
    assert model['actualRouteApplication'] is False
    assert model['coreAbi'] == 'x86_64'
    assert model['coreVersion'] == receipt['recipe']['version']
    assert model['coreSha256'] == receipt['binaries']['x86_64']['sha256']
    assert model['checkCount'] == len(model['checks']) >= 46 and all(row['pass'] for row in model['checks'])
    assert len({row['name'] for row in model['checks']}) == model['checkCount']
    required = {
        'Identical subscription URLs have separate stable source IDs',
        'Native fixed-exit fingerprint survives a provider-name change',
        'Same-name changed endpoint cannot replace a fixed exit',
        'Library refresh does not rewrite an active environment\'s snapshot',
        'Creating an environment copies both private provider payloads',
        'Creating an environment excludes pending network operations',
        'Creating an environment excludes the source chat draft',
        'Creating an environment rejects a provider receipt with the wrong SHA',
        'Identified provider receipts require their own role and source URL',
        'Identified provider receipts reject a changed private generation',
    }
    assert required <= {row['name'] for row in model['checks']}
    ui = report('network-source-ui-results.json')
    assert ui['actualAndroidExecution'] and ui['actualNativeExecution'] and ui['actualKeystoreEncryption']
    assert ui['actualAdbTouchExecution'] is True and ui['actualRouteApplication'] is False
    assert ui['installedPackage'] == 'local.pocketchat.test' and len(ui['installedApkSha256']) == 64
    assert ui['checkCount'] == len(ui['checks']) >= 77 and all(row['pass'] for row in ui['checks'])
    assert len({row['name'] for row in ui['checks']}) == ui['checkCount']
    assert ui['touchUiCheckCount'] == len(ui['touchUiChecks']) >= 24 and all(row['pass'] for row in ui['touchUiChecks'])
    assert {'Cancelling a supported exit choice leaves the parent draft unchanged',
            'Unsupported exit cannot change the parent draft',
            'Opening legacy editor reparses existing raw cache without a download',
            'Cached migration binds the real native entrance identity',
            'No native global default exit is introduced'} <= {row['name'] for row in ui['checks']}
    route = report('network-source-route-results.json')
    route_result = verify_source_route(route, route['server'], receipt, source)
    idle = report('network-safe-idle-results.json')
    _core_matches(idle, receipt)
    assert idle['installedApkSha256'] == ui['installedApkSha256'], 'Safe-idle and touch UI must run the same integration APK'
    idle_result = verify_safe_idle(idle)
    return {'separateEntryAndExitLibraries': True, 'sourceModelAndroidChecks': model['checkCount'],
            'sourceUiAndroidChecks': ui['checkCount'], 'actualTouchChecks': ui['touchUiCheckCount'],
            'privateEnvironmentSnapshots': True, 'fixedExitRoute': route_result,
            'pendingBaselineLineageHostChecks': lineage['total'], 'actualSafeIdleFences': idle_result}
