"""Source-independent contract for the real Android update-route evidence."""
import re
ETAG = '"route-fixture-v1"'


def verify_update_route(report, source, core_sha256):
    assert report['status'] == 'passed', report.get('error')
    assert report['actualAndroidExecution'] and report['actualManagedCoreExecution'] and report['actualProfileProcesses']
    assert report['productionLeaseEndpoints'] and report['testOnlySingletonFixtures'] and not report['productionProviderTestHooks']
    assert report['publicNetworkTraffic'] is False and report['internalDirectFallbackCalls'] == 0 and report['directFactoryCalls'] == 2
    assert report['cleanupRestoredProfiles']
    assert len(report['checks']) >= 32 and all(c['pass'] for c in report['checks'])
    zero, seven = report['initialProfiles']
    assert [zero['slot'], seven['slot']] == [0, 7]
    assert zero['processPid'] != seven['processPid'] and zero['corePid'] != seven['corePid']
    assert zero['proxyPort'] != seven['proxyPort'] and zero['verified'] and seven['verified']
    for row in [zero, seven]:
        assert row['corePid'] > 1 and row['servicePid'] > 1
        assert row['coreSha256'] == core_sha256
        assert row['entryDenied'] == row['fixedExitDenied'] == 0
    initial, restored = report['initialLease'], report['restoredLease']
    assert initial['slot'] == restored['slot'] == 7 and initial['sourceType'] == restored['sourceType'] == 'internal'
    assert initial['environmentGeneration'] == restored['environmentGeneration']
    assert re.fullmatch('[a-f0-9]{64}', initial['lease']) and re.fullmatch('[a-f0-9]{64}', restored['lease'])
    assert initial['lease'] != restored['lease'] and initial['proxyPort'] == seven['proxyPort']
    restarted = report['restoredProfile7']
    assert restarted['corePid'] != seven['corePid'] and restored['proxyPort'] == restarted['proxyPort']
    assert report['profileAfterNetworkInvalidation']['corePid'] == seven['corePid']
    assert report['profileAfterNetworkInvalidation']['ready'] and report['injectedDefaultNetwork']['injectedEvent']
    assert report['injectedDefaultNetwork']['afterRevision'] > report['injectedDefaultNetwork']['beforeRevision']
    assert report['partialBeforeInvalidation'] == report['partialAfterInvalidation'] == report['partialWhileDefaultIsDirect']
    partial = report['partialBeforeInvalidation']
    assert partial['bytes'] == 262144 and partial['etag'] == ETAG and re.fullmatch('[a-f0-9]{64}', partial['sha256'])
    modes = {row['name']: row for row in report['invalidations']}
    assert set(modes) == {'default-network-revision', 'core-lifetime', 'wrong-slot', 'wrong-environment-generation', 'deleted-environment', 'recreated-generation', 'direct-source-change', 'direct-deleted-generation'}
    assert len(modes) == len(report['invalidations']) and all(row['rejected'] for row in modes.values())
    active_zero, active_seven = report['activeProfiles']
    assert active_zero['entryCircuits'] == zero['entryCircuits'] and active_zero['fixedExitCircuits'] == zero['fixedExitCircuits']
    assert active_seven['entryCircuits'] > seven['entryCircuits'] and active_seven['fixedExitCircuits'] > seven['fixedExitCircuits']
    assert active_seven['entryAuthenticated'] == active_seven['entryCircuits'] and active_seven['fixedExitAuthenticated'] == active_seven['fixedExitCircuits']
    assert active_seven['corePid'] == seven['corePid'] and active_seven['coreGeneration'] == seven['coreGeneration'] and active_seven['routeSerial'] == seven['routeSerial'] and active_seven['verified']
    assert len(report['opens']) == 3 and report['opens'][0]['officialUrl'].endswith('/latest.json')
    for row in report['opens']:
        assert row['type'] == 'HTTP' and row['host'] == '127.0.0.1' and row['port'] in {initial['proxyPort'], restored['proxyPort']}
    archive = report['verifiedArchive']
    assert archive['bytes'] > 1024 * 1024 and archive['sameInstalledSigner'] and not archive['installed']
    assert re.fullmatch('[a-f0-9]{64}', archive['sha256']) and archive['sha256'] == report['fixtureApkSha256']
    wire = report['serverTrace']
    requests = [row for row in wire if row['path'] == '/update-route.apk']
    assert len(requests) == 2 and requests[0]['connection'] != requests[1]['connection']
    first, resumed = requests
    assert first['status'] == 200 and first['range'] == '' and first['bytesSent'] == 262144
    assert first['peerClosed'] and first['serverClosedBeforePeerEof'] is False and first['nextByte'] == -1
    assert first['stalledAfterBytes'] == 262144 and first['declaredBytes'] == archive['bytes']
    assert resumed['status'] == 206 and resumed['range'] == 'bytes=262144-' and resumed['ifRange'] == ETAG
    assert resumed['contentRange'] == f"bytes 262144-{archive['bytes'] - 1}/{archive['bytes']}"
    assert resumed['bytesSent'] == archive['bytes'] - 262144 and resumed['completed']
    assert all(not row['personalCredentialsSeen'] for row in wire)
    assert all(row['etag'] == ETAG for row in requests)
    assert report['directScope']['sourceType'] == 'direct' and report['directScope']['slot'] == 0
    assert report['directPartialBeforeSourceChange'] == report['directPartialAfterSourceChange']
    assert report['directPartialBeforeSourceChange']['bytes'] == 262144
    assert report['directPartialBeforeGenerationChange'] == report['directPartialAfterGenerationChange']
    assert report['directPartialBeforeGenerationChange']['bytes'] == 327680
    direct_wire = [r for r in wire if r['path'] == '/direct-route.apk']
    assert len(direct_wire) == 2
    for row, status, count in [(direct_wire[0], 200, 262144), (direct_wire[1], 206, 65536)]:
        assert row['status'] == status and row['bytesSent'] == count and row['peerClosed'] and row['nextByte'] == -1
        assert not row['serverClosedBeforePeerEof'] and not row['completed']
    assert direct_wire[0]['range'] == '' and direct_wire[1]['range'] == 'bytes=262144-' and direct_wire[1]['ifRange'] == ETAG
    assert report['sourceCommit'] == source

    return {"actualAndroidExecution": True, "actualManagedCoreExecution": True, "checks": len(report["checks"]), "selectedSlot": initial["slot"], "invalidations": len(modes), "internalDirectFallbackCalls": 0, "resumedBytes": resumed["bytesSent"], "signedArchiveBytes": archive["bytes"]}
