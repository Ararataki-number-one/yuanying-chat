"""Require independent source libraries, actual Android dialogs and a pinned native chain."""
import hashlib
import importlib.util
import json
import math
import pathlib
import re

PAYLOAD = 'pool-payload-' * 700
SUCCESS = {'subscribed-a', 'subscribed-b', 'after-probes', 'restored-subscription', 'legacy-manual'}
FAILURE = {'invalid-entry-snapshot-sha', 'invalid-exit-snapshot-sha', 'same-name-changed-exit', 'same-name-changed-entry'}
SAFE_IDLE_CASES = ['prepare-send', 'capture-send', 'prepare-transfer', 'capture-navigation',
                   'capture-delete', 'complete-delete', 'complete-late-save']
SAFE_IDLE_TRUST_HASHES = {
    'testCaSha256': '794f38936cb5ebc28b6d0f681f9d5b00a2431f48ced181137f4f3bf45fe67226',
    'testLeafSha256': '66c659c8f20a9ea7d132d66e4020897be19fab099aa3cc17fa870a967c16266c',
    'profileDbSha256': 'a3114642d39ee1f3bc23c4428b08035abeb101de367547dcfe32680af6286023',
}
SAFE_IDLE_TRUST_CHECKS = {
    'Public test CA database prepared in the isolated profile before Gecko runtime',
    'Controlled ChatGPT certificate has the exact valid CA signed SAN and server chain',
    'Official Gecko security callback trusts the controlled ChatGPT origin without an exception',
}
SAFE_IDLE_TRUST_MANIFEST_SHA256 = '077bb6aca51c2af07bc831cc4db3beabf9cbeb70c1fd793d1a7f61f25f54a621'
SAFE_IDLE_TRUST_FILES = {
    'root-ca.der': {'sha256': SAFE_IDLE_TRUST_HASHES['testCaSha256'], 'bytes': 959},
    'server-leaf.der': {'sha256': SAFE_IDLE_TRUST_HASHES['testLeafSha256'], 'bytes': 941},
    'cert9.db': {'sha256': SAFE_IDLE_TRUST_HASHES['profileDbSha256'], 'bytes': 28672},
    'server.p12': {'sha256': '5fe7edd5f9b89854977cc3f6181faf8b38386eb03f4829ec9d39bd3cbfb6acc3', 'bytes': 3814},
}
SAFE_IDLE_TRUST_ASSET_NAMES = sorted(set(SAFE_IDLE_TRUST_FILES) | {'manifest.json', 'README.md'})
SETTINGS_HOST_MINIMUMS = {'receipt': 22, 'provider': 41, 'retry': 43}
SETTINGS_JSON_SHA256 = {
    'desktop': '3cf6cd6892e32e2b4c1c39e0f52f5248a2f5b37646fdfbb79a66b46b618414ed',
    'android': 'dfb7bae2f404cfe0b72b4d23944698cb716b7665171812a0a4d0f5926c0fac79',
}
SETTINGS_PARSER_SUITES = {'gecko_settings_retry_gate_test.py': 5,
                          'gecko_settings_application_gate_test.py': 10,
                          'gecko_settings_internal_gate_test.py': 16}
SETTINGS_REPORTS = [
    'network-settings-' + mode + '-results.json' for mode in ('retry', 'application', 'internal')
] + ['network-settings-' + kind + '-' + implementation + '-host-results.json'
     for implementation in SETTINGS_JSON_SHA256 for kind in (*SETTINGS_HOST_MINIMUMS, 'ui')
] + ['network-settings-parser-negative-results.json']


def verify_settings_ui_host(results):
    assert set(results) == {'UiSnapshotTest', 'NetworkOptimizationPolicyTest'}
    ui, policy = results['UiSnapshotTest'], results['NetworkOptimizationPolicyTest']
    assert type(ui['passed']) is int and ui['passed'] == ui['total'] >= 39
    # The production policy test emits passed + scope, without a total field.
    # Keep that actual schema instead of adding a fabricated total to its receipt.
    assert type(policy['passed']) is int and policy['passed'] >= 49
    if 'total' in policy:
        assert policy['total'] == policy['passed']
    return ui['passed'] + policy['passed']


def _settings_verifier(mode):
    name = 'run_network_settings_' + mode + '.py'
    source = pathlib.Path(__file__).resolve().parents[2] / 'tests/gecko' / name
    # Signed public evidence retains these exact verification sources beside this
    # contract. Importing them never invokes their guarded Android main functions.
    if not source.is_file():
        source = pathlib.Path(__file__).resolve().parent / name
    spec = importlib.util.spec_from_file_location('required_settings_' + mode, source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, source


def verify_network_sharing(report, source, apk_sha256, complete=False, run_token=None):
    assert report['status'] == 'passed'
    assert report['actualAndroidExecution'] is True and report['actualNativeExecution'] is True
    assert report['buildIdentity']['sourceCommit'] == source
    assert report['buildIdentity']['apkSha256'] == apk_sha256 and _hash(apk_sha256)
    assert _hash(report['runToken'], 32)
    if run_token is not None:
        assert report['runToken'] == run_token
    checks = report['checks']
    assert report['checkCount'] == len(checks) >= 30
    assert all(row['pass'] is True for row in checks)
    assert len({row['name'] for row in checks}) == len(checks)
    matrix = pathlib.Path(__file__).resolve().parents[2] / 'tests/gecko/assets/sharing-schema-matrix.json'
    if not matrix.is_file():
        matrix = pathlib.Path(__file__).resolve().parent / 'sharing-schema-matrix.json'
    cases = json.loads(matrix.read_text())['cases']
    expected = [case['id'] for case in cases]
    evidence = report['schemaFingerprintEvidence']
    assert len(expected) == len(set(expected)) == report['schemaFingerprintCount'] == len(evidence) == 31
    assert [row['case'] for row in evidence] == expected
    for row, case in zip(evidence, cases):
        for field in ('actualNativeFingerprintVerified', 'actualEncryptedCatalogCandidate',
                      'activeSnapshotPreserved', 'temporarySourceDeleted'):
            assert row[field] is True, (row['case'], field)
        assert _hash(row['originalFingerprint']) and row['originalFingerprint'] == row['exportFingerprint']
        assert row['sourceHash'] == hashlib.sha256(case['source'].encode()).hexdigest()
        assert _hash(row['exportHash'])
    if complete:
        assert report['sharePreparationPreservesActiveSnapshot'] is True
        assert report['partialSharePreservesActiveSnapshot'] is True
        assert report['cancelledBeforeRouteApplication'] is True
        expected_taps = ['仅分享入口', '复制配置', '测试订阅整条线路', '仅分享出口', '复制配置',
                         '测试入口分享', '复制配置', '测试出口分享', '复制配置', '测试固定出口分享', '复制配置',
                         '检查分享未改动线路', '测试入口失败后仅分享出口', '复制配置', '恢复分享测试线路',
                         '导入并选择环境', 'Sharing Window', '取消']
        assert report['uiChecks'] == expected_taps
        assert report['actualAndroidTaps'] == len(expected_taps)
    return {'nativeSchemaFingerprints': len(evidence), 'encryptedCatalogRoundTrip': True,
            'actualShareDialogsAndExplicitImport': complete}


def verify_network_settings(directory, source, receipt, apk_sha256):
    directory = pathlib.Path(directory)
    reports = {}
    for name in SETTINGS_REPORTS:
        value = json.loads((directory / name).read_text())
        assert value['sourceCommit'] == source and value['status'] == 'passed', name
        assert not value.get('diagnosticOnly', False), name
        reports[name] = value
    android = {}
    for mode in ('retry', 'application', 'internal'):
        value = reports['network-settings-' + mode + '-results.json']
        assert _hash(value['runNonce'], 32)
        assert value['installedPackage'] == 'local.pocketchat.test'
        assert value['installedApkSha256'] == value['buildIdentity']['apkSha256'] == apk_sha256
        assert value['runnerOneAttempt'] is True
        verifier, path = _settings_verifier(mode)
        assert value['runnerSha256'] == hashlib.sha256(path.read_bytes()).hexdigest()
        verifier.verify(value, source, value['runNonce'], apk_sha256)
        android[mode] = value['checkCount']
    _core_matches(reports['network-settings-internal-results.json'], receipt)
    host_counts = {}
    for implementation, jar_sha in SETTINGS_JSON_SHA256.items():
        for kind in (*SETTINGS_HOST_MINIMUMS, 'ui'):
            name = 'network-settings-' + kind + '-' + implementation + '-host-results.json'
            value = reports[name]
            assert value['actualAndroidExecution'] is False and value['ciSourceDirty'] is False
            assert value['ciHost'] == {'jsonImplementation': implementation, 'jsonJarSha256': jar_sha}
            if kind == 'ui':
                host_counts[implementation + '-' + kind] = verify_settings_ui_host(value['results'])
            else:
                checks = value['checks']
                assert value['passed'] == len(checks) >= SETTINGS_HOST_MINIMUMS[kind]
                assert all(row['pass'] is True for row in checks)
                assert len({row['name'] for row in checks}) == len(checks)
                host_counts[implementation + '-' + kind] = len(checks)
    parsers = reports['network-settings-parser-negative-results.json']
    assert parsers['actualAndroidExecution'] is False and parsers['ciSourceDirty'] is False
    assert set(parsers['suites']) == set(SETTINGS_PARSER_SUITES)
    for name, minimum in SETTINGS_PARSER_SUITES.items():
        result = parsers['suites'][name]
        assert result['testsRun'] >= minimum and result['successful'] is True
        assert result['failures'] == result['errors'] == result['skipped'] == 0
        assert _hash(result['sourceSha256'])
    return {'actualAndroidChecks': android, 'productionHostChecks': host_counts,
            'requiredParserNegativeSuites': len(parsers['suites']), 'sameIntegrationApk': True}
MODEL_STORAGE_CHECKS = {
    'Original encrypted record layout and slot AAD remain readable',
    'Unprotected Android AtomicFile creates an actual pending .new',
    "Unprotected Android recovery deletes another writer's .new",
    'Unprotected Android finishWrite returns without publishing the new value',
    'Formal encrypted writer reaches Android startWrite before publication',
    "Formal encrypted reader waits instead of deleting the writer's .new",
    'Formal encrypted reader decrypts the whole newly published value',
    'Successful formal publication leaves no pending .new',
    "Formal storage reports Android's quiet rename failure as IOException",
    'Rejected encrypted publication keeps the previously committed value',
    'Rejected encrypted publication leaves no pending staging file',
    'Formal encrypted removal waits for an active publication',
    'Formal encrypted removal clears both committed and pending files',
    'Different physical files on one stripe support safe nested leases',
    'Dynamic storage slots keep at most 64 stable lock inodes',
    'Removing dynamic slots leaves no committed or pending payloads',
    "Storage race fixtures preserve the environment's encrypted route",
}
SEALED_STORAGE_HOST_CHECKS = {
    'Unprotected baseline creates a pending .new file',
    "Unprotected openRead removes a different writer's .new file",
    'Unprotected finishWrite can return normally without publishing',
    'Formal publication turns quiet rename failure into IOException',
    'Rejected rename publication retains the last committed bytes',
    'Formal writer reaches an actual startWrite barrier',
    'Formal reader waits instead of deleting an active .new',
    'Formal reader receives the complete newly published value',
    'Formal remove waits for publication before removing the record',
    'Formal remove clears base and pending publication',
    'A separate JVM reader cannot destroy a pending publication',
    'Cross-JVM writer commits successfully',
    'Cross-JVM reader observes the complete committed value',
    'Fixture finds two different physical files sharing one stable stripe',
    'Nested access to a different file on the same stripe is reentrant',
    'Dynamic cache slot churn creates at most 64 persistent lock inodes',
    'Removed dynamic slots leave no committed or pending payload files',
    'Missing records return null without treating .lock files as data',
    'Legacy backup recovery remains readable under the formal lease',
    'Rejected rename publication clears its pending .new file',
    'A separate JVM actually attempts and observes the held OS stripe lock',
    'Payload removal never replaces or unlinks a stable stripe inode',
    'Publication verifies prefix and complete multi-chunk payload',
    'Publication verification rejects same-length prefix corruption',
    'Publication verification rejects same-length payload-tail corruption',
    'Publication verification rejects shortened and extra payload bytes',
    'Canonical file aliases share the same stable stripe gate',
    'Publication through an alias preserves the physical file and symlink',
    'Removal through an alias clears the physical payload under its lease',
    'A queued JVM waiter retains the same live canonical gate',
    'Interrupted stripe acquisition exits without entering protected I/O',
    'Completed and interrupted leases release all JVM gate references',
}


def _hash(value, length=64):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{' + str(length) + '}', value) is not None


def _core_matches(report, receipt):
    assert report['coreAbi'] == 'x86_64'
    assert report['coreVersion'] == receipt['recipe']['version']
    assert report['coreSha256'] == receipt['binaries']['x86_64']['sha256']


def verify_route_busy_bootstrap(report):
    required = 'A fresh manual core verifies its exit while the same real session remains navigation-busy'
    assert any(row['name'] == required and row['pass'] is True for row in report['checks'])
    evidence = report['legacyBusyBootstrap']
    assert evidence['actualSession'] is True and evidence['busyClearedForStartup'] is False
    assert evidence['receiptCurrent'] is True
    assert type(evidence['exitRequests']) is int and evidence['exitRequests'] > 0
    before, after = evidence['before'], evidence['after']
    for value in (before, after):
        assert value['navigating'] is True and value['routeBusy'] is True
        assert type(value['pending']) is bool and type(value['fileWorkActive']) is bool
    assert before['pending'] == after['pending'] and before['fileWorkActive'] == after['fileWorkActive']
    return {'realSessionBusyPreserved': True, 'freshCoreExitVerified': True}


def verify_route_busy_phase_boundary(report):
    """The test ends its busy phase; only a later real reconnect may admit traffic."""
    verify_route_busy_bootstrap(report)
    boundary = report['legacyBusyPhaseBoundary']
    assert boundary['schema'] == 1
    assert boundary['method'] == 'test-only end of controlled navigation-busy phase'
    assert boundary['domReadyInferred'] is False
    count = boundary['bootstrapCheckCount']
    assert type(count) is int and count >= 3
    checks = report['checks']
    expected = [
        'Legacy manual exit starts through the same production path',
        'A fresh manual core verifies its exit while the same real session remains navigation-busy',
        'Manual path keeps its ordinary SOCKS proxy and removes subscribed exit files',
        'The controlled busy phase ends after bootstrap without changing browser admission or the verified route',
        'Ending the controlled busy phase preserves the actual Gecko document and unsent draft',
    ]
    observed = checks[count - 3:count + 2]
    assert [row['name'] for row in observed] == expected
    assert all(row['pass'] is True for row in observed)
    before, after = boundary['before'], boundary['after']
    for key in ('navigating', 'routeBusy', 'pending', 'fileWorkActive'):
        assert before[key] is report['legacyBusyBootstrap']['after'][key], key
    assert before['navigating'] is True and before['routeBusy'] is True
    assert after['navigating'] is False and after['routeBusy'] is False
    changed = {'navigating', 'routeBusy'}
    assert {key: value for key, value in before.items() if key not in changed} == {
        key: value for key, value in after.items() if key not in changed}
    for value in (before, after):
        for key in ('pending', 'fileWorkActive', 'submitting', 'operation', 'transferActive', 'stateBusy'):
            assert value[key] is False, key
        for key in ('networkReady', 'guardAllowed', 'guardBlocked', 'connecting', 'offline',
                    'coreStarting', 'defaultNetworkUsable'):
            assert type(value[key]) is bool, key
        assert value['coreReady'] is True and value['nativeReceiptCurrent'] is True
        assert value['nativeReceiptObservation'] == 'pushed-service-state'
        for key in ('connectionEpoch', 'navigationEpoch', 'routeSerial'):
            assert type(value[key]) is int and value[key] >= 0, key
        for key in ('browserIdentity', 'geckoSessionIdentity'):
            assert type(value[key]) is int and value[key] > 0, key
        assert isinstance(value['sessionDocumentId'], str)
        assert isinstance(value['appliedIdentity'], str) and value['appliedIdentity']
        receipt = value['receipt']
        for key in ('fingerprint', 'tokenHash', 'configurationHash'):
            assert _hash(receipt[key]), key
        for key in ('entry', 'generation'):
            assert isinstance(receipt[key], str) and receipt[key], key
        assert type(receipt['serial']) is int and receipt['serial'] == value['routeSerial']
        for key in ('controller', 'proxy', 'pid', 'servicePid'):
            assert type(receipt[key]) is int and receipt[key] > 1, key
    assert boundary['documentBefore'] == boundary['documentAfter']
    document = boundary['documentAfter']
    assert document['url'] == 'https://127.0.0.1:9879/pool' and document['controlled'] is True
    assert type(document['timeOrigin']) in (int, float) and math.isfinite(document['timeOrigin']) and document['timeOrigin'] > 0
    assert document['draft'] == 'unsent pool draft' and type(document['sends']) is int and document['sends'] == 0
    began, ended = boundary['beganAtNs'], boundary['endedAtNs']
    assert type(began) is int and type(ended) is int and 0 < began <= ended
    manual = [row for row in report['sessionRestorations'] if row['name'] == 'legacy-manual']
    assert len(manual) == 1 and type(manual[0]['beganAtNs']) is int and ended <= manual[0]['beganAtNs']
    return {'syntheticBusyPhaseEndedAfterBootstrap': True, 'browserAdmissionAndReceiptUnchanged': True,
            'actualDocumentPreserved': True, 'requiresSubsequentProductionReconnect': True}


def _verify_route_session_restorations(report):
    assert len(report['checks']) >= 71
    required = {name + ' releases the browser guard through the production reconnect callback'
                for name in ('restored-subscription', 'legacy-manual')}
    assert required <= {row['name'] for row in report['checks']}
    restorations = report['sessionRestorations']
    assert [row['name'] for row in restorations] == ['restored-subscription', 'legacy-manual']
    for row in restorations:
        assert row['method'] == 'ChatSession.reconnect → NativeNetwork.recover → ChatSession.applyProxy'
        before, after = row['before'], row['after']
        assert before['nativeReceiptObservation'] == after['nativeReceiptObservation'] == 'fresh-service-snapshot'
        assert before['coreReady'] is True and before['nativeReceiptCurrent'] is True
        for key in ('networkReady', 'guardAllowed', 'coreReady', 'nativeReceiptCurrent', 'defaultNetworkUsable'):
            assert after[key] is True, key
        for key in ('guardBlocked', 'connecting', 'offline', 'coreStarting'):
            assert after[key] is False, key
        assert row['document'] == {'url': 'https://127.0.0.1:9879/pool', 'controlled': True}
    for name in SUCCESS | FAILURE:
        actual = [row for row in report['routes'] if '/bytes?id=' + name in row['url']]
        assert actual, name
        for row in actual:
            state = row['session']
            assert state['nativeReceiptObservation'] == 'pushed-service-state'
            if name in SUCCESS:
                for key in ('networkReady', 'guardAllowed', 'coreReady', 'nativeReceiptCurrent', 'defaultNetworkUsable'):
                    assert state[key] is True, (name, key)
                assert state['guardBlocked'] is False and state['offline'] is False
            else:
                assert state['coreReady'] is False and state['nativeReceiptCurrent'] is False


def _verify_safe_idle_tls(report):
    assert report['actualTestCaTrust'] is True and report['certificateExceptions'] == 0
    preparation = report['testCaTrust']
    assert preparation['schema'] == 1 and preparation['method'] == 'NSS SQL public-root profile preload'
    assert preparation['assetDirectory'] == 'network-safe-idle-trust/' and preparation['hostname'] == 'chatgpt.com'
    assert isinstance(preparation['profilePath'], str)
    assert preparation['profilePath'].endswith('/local.pocketchat.test/no_backup/gecko-browser')
    for key, expected in SAFE_IDLE_TRUST_HASHES.items():
        assert report[key] == preparation[key] == expected, key
    for key in ('preparedBeforeRuntime', 'databaseCopyShaVerified', 'serverChainShaVerified',
                'certificateValidityChecked', 'certificateHostnameSanMatches'):
        assert preparation[key] is True, key
    assert preparation['productionTrustChanged'] is False and preparation['certificateExceptionUsed'] is False
    security = report['securityEvents']
    assert security
    for event in security:
        assert event['callback'] == 'GeckoSession.ProgressDelegate.onSecurityChange'
        assert event['host'] == 'chatgpt.com' and isinstance(event['origin'], str)
        assert event['isSecure'] is True and event['isException'] is False
        assert event['certificateSha256'] == SAFE_IDLE_TRUST_HASHES['testLeafSha256']
        assert event['testCaSha256'] == SAFE_IDLE_TRUST_HASHES['testCaSha256']
        for key in ('certificateSignedByTestCa', 'certificateValidityChecked', 'certificateHostnameSanMatches',
                    'certificateMatchesPackagedLeaf', 'accepted'):
            assert event[key] is True, key
        assert event['verificationError'] == ''
    events = report['phaseEvents']
    prepared = [event['value'] for event in events if event.get('kind') == 'testTrustPrepared']
    observed = [event['value'] for event in events if event.get('kind') == 'security']
    assert prepared == [preparation] and observed == security
    preparation_index = next(i for i, event in enumerate(events) if event.get('kind') == 'testTrustPrepared')
    first_security = next(i for i, event in enumerate(events) if event.get('kind') == 'security')
    first_tap = next(i for i, event in enumerate(events) if event.get('kind') == 'tapNeeded')
    assert preparation_index < first_security < first_tap


def _verify_safe_idle_trust_host(report, source, apk_sha256):
    assert report['schema'] == 1 and report['sourceCommit'] == source and report['status'] == 'passed'
    assert report['actualAndroidExecution'] is False and not report.get('diagnosticOnly', False)
    assert report['assetDirectory'] == 'network-safe-idle-trust/' and report['hostname'] == 'chatgpt.com'
    assert report['manifestSha256'] == SAFE_IDLE_TRUST_MANIFEST_SHA256
    assert report['files'] == SAFE_IDLE_TRUST_FILES
    assert report['integrationApkAssetNames'] == SAFE_IDLE_TRUST_ASSET_NAMES
    assert report['integrationApkAssetCount'] == len(SAFE_IDLE_TRUST_ASSET_NAMES)
    for key in ('publicOnlyNssDatabase', 'nssServerCaTrustVerified', 'validCaSignedServerHostname',
                'pkcs12LeafMatchesSource', 'integrationApkAssetsVerified'):
        assert report[key] is True, key
    assert _hash(apk_sha256) and report['integrationApkSha256'] == apk_sha256


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
    control = report['fixtureProviderControl']
    assert control['removeCallbacksCalled'] is True and control['automaticDrainSuspended'] is True
    assert control['registeredProviderIdentity'] != control['controlledProviderIdentity']
    assert control['drainRevisionAfter'] == control['drainRevisionBefore'] + 1
    separation = report['candidateSeparation']
    assert [row['case'] for row in separation] == SAFE_IDLE_CASES[:5]
    for row in separation:
        assert row['schema'] == 1 and row['activeUnchanged'] is True and row['pendingUnchanged'] is True
        assert row['activeBeforeHash'] == row['activeAfterHash'] and _hash(row['activeBeforeHash'])
        assert row['pendingBeforeHash'] == row['pendingAfterHash'] and _hash(row['pendingBeforeHash'])
    gestures, events = report['actualAndroidGestures'], report['phaseEvents']
    assert report['runnerOneAttemptPerGesture'] is True
    assert report['parseCount'] == 2 and report['actualTrustedGestures'] == 2 and len(gestures) == 2
    assert report['proxyAccepted'] > 0 and report['proxyRejected'] >= 0 and report['pageDocuments'] > 0
    assert 0 < report['controlledTlsPort'] <= 65535 and report['proxyUpstreamConnections']
    assert len(report['proxyUpstreamConnections']) == report['proxyAccepted']
    assert all(value == f"127.0.0.1:{report['controlledTlsPort']}" for value in report['proxyUpstreamConnections'])
    _verify_safe_idle_tls(report)
    assert report['checkCount'] == len(report['checks']) >= 59
    assert all(row['pass'] is True for row in report['checks'])
    assert len({row['name'] for row in report['checks']}) == report['checkCount']
    assert 'Packaged native ELF exposes its actual ABI, streamed SHA and controller version' in {row['name'] for row in report['checks']}
    assert SAFE_IDLE_TRUST_CHECKS <= {row['name'] for row in report['checks']}
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
    _verify_route_session_restorations(report)
    verify_route_busy_bootstrap(report)
    verify_route_busy_phase_boundary(report)
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
    storage = json.loads((directory / 'sealed-file-host-results.json').read_text())
    assert storage['sourceCommit'] == source and not storage.get('diagnosticOnly', False)
    assert storage['status'] == 'passed' and storage['failure'] == ''
    assert storage['actualAndroidExecution'] is False and storage['actualKeystoreEncryption'] is False
    assert storage['actualAtomicFileBehaviorStub'] is True and storage['actualCrossJvmStorageLease'] is True
    assert storage['executed'] == storage['passed'] == storage['total'] == len(storage['checks']) >= 32
    assert all(row['pass'] is True for row in storage['checks'])
    storage_names = {row['name'] for row in storage['checks']}
    assert len(storage_names) == storage['total'] and SEALED_STORAGE_HOST_CHECKS <= storage_names
    model = report('network-source-results.json')
    for field in ['actualAndroidExecution', 'actualNativeExecution', 'actualMihomoExecution', 'actualKeystoreEncryption']:
        assert model[field] is True, field
    assert model['actualRouteApplication'] is False
    assert model['coreAbi'] == 'x86_64'
    assert model['coreVersion'] == receipt['recipe']['version']
    assert model['coreSha256'] == receipt['binaries']['x86_64']['sha256']
    assert model['checkCount'] == len(model['checks']) >= 63 and all(row['pass'] for row in model['checks'])
    assert len({row['name'] for row in model['checks']}) == model['checkCount']
    assert model['actualAtomicFilePublicationRace'] is True and model['actualSealedFileIoLease'] is True
    assert MODEL_STORAGE_CHECKS <= {row['name'] for row in model['checks']}
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
    trust_host = report('network-safe-idle-trust-host-results.json')
    _verify_safe_idle_trust_host(trust_host, source, idle['installedApkSha256'])
    idle_result = verify_safe_idle(idle)
    sharing = json.loads((directory / 'network-source-sharing-results.json').read_text())
    sharing_result = verify_network_sharing(sharing, source, ui['installedApkSha256'], complete=True)
    settings_result = verify_network_settings(directory, source, receipt, ui['installedApkSha256'])
    return {'separateEntryAndExitLibraries': True, 'sourceModelAndroidChecks': model['checkCount'],
            'sourceUiAndroidChecks': ui['checkCount'], 'actualTouchChecks': ui['touchUiCheckCount'],
            'privateEnvironmentSnapshots': True, 'fixedExitRoute': route_result,
            'pendingBaselineLineageHostChecks': lineage['total'], 'actualSafeIdleFences': idle_result,
            'integrationTestCaAssetsVerified': True, 'integrationTestCaAssetFiles': trust_host['integrationApkAssetCount'],
            'crossJvmStorageLeaseHostChecks': storage['total'], 'actualAndroidStoragePublicationBarrier': True,
            'singleNodeSharing': sharing_result, 'versionedNetworkSettings': settings_result}
