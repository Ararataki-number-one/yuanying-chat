#!/usr/bin/env python3
"""Synthetic verifier tests only; these receipts are never Android evidence."""
import copy
import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('settings_internal', ROOT / 'tests/gecko/run_network_settings_internal.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
SOURCE, NONCE, APK = 'a' * 40, 'b' * 32, 'c' * 64
ENV = '11111111-1111-4111-8111-111111111111'


def generation(index):
    return '00000000-0000-4000-8000-%012d' % index


def route(index, entry):
    configuration = ('a' if entry == 'Entry|a' else 'b') * 64
    return {'observation': 'fresh-service-snapshot', 'alive': True, 'verified': True,
            'receiptMatchesFreshState': True, 'pid': 200 + index, 'servicePid': 150,
            'generation': generation(index), 'receiptGeneration': generation(index),
            'receiptPid': 200 + index, 'configuration': configuration,
            'receiptConfiguration': configuration, 'fixedIdentity': 'e' * 64,
            'fixedNodeFingerprint': 'f' * 64, 'routeSerial': 1,
            'currentEntry': entry, 'exitIp': '203.0.113.8', 'coreVersion': 'synthetic version'}


def operation(name, revision, applied):
    wanted = {'environmentId': ENV, 'generation': 1,
              'candidateId': 'candidate-' + str(revision), 'savedRevision': revision}
    actual = dict(wanted, saveState='saved', scope='session',
                  applicationState='applied' if applied else 'saved-unconfirmed',
                  appliedRevision=revision if applied else 0)
    return {'name': name, 'expected': wanted, 'result': {'done': True, 'ok': applied, 'operationResult': actual}}


def positive(name, revision, index):
    row = operation(name, revision, True)
    entry = 'Entry|a' if index == 1 else 'Entry|b'
    request = {'name': name, 'ok': True, 'httpStatus': 200, 'bodyMatches': True,
               'bodySha256': 'd' * 64, 'expectedBodySha256': 'd' * 64,
               'nonce': str(index) * 32, 'echoedNonce': str(index) * 32, 'serverObservedNonce': True,
               'mappedBefore': index - 1, 'mappedAfter': index, 'externalBefore': 1, 'externalAfter': 1,
               'currentEntry': entry, 'entryAContacts': 1, 'entryBContacts': index - 1,
               'beganAtNs': index * 20, 'endedAtNs': index * 20 + 10}
    row.update(route=route(index, entry), actualModelDesiredRevision=revision,
               actualModelAppliedRevision=revision, actualConfigurationHash=str(index) * 64,
               modelDesiredHash=str(index) * 64, modelAppliedHash=str(index) * 64,
               modelEngineVersion='Gecko fixture version', runtimeEngineVersion='Gecko fixture version',
               draftRetained=True, acceptedPolicy=True, productionReconnect=True,
               documentBefore='doc-' + str(index), documentAfter='doc-' + str(index), loadsBefore=index, loadsAfter=index,
               connectionBefore=index, connectionAfter=index + 1, request=request)
    return row


def bootstrap_proof():
    identity = {'slot': 0, 'generation': 1, 'environmentId': ENV}
    common = dict(identity=identity, mode='external', browserMatchesAccepted=True, pendingIntent=False,
                  desiredRevision=1, appliedRevision=0, observedRevision=0, connection=0,
                  desiredHash='a' * 64, actualHash='b' * 64, appliedHash='',
                  networkMatchesActual=False, policyAcknowledged=True, networkReady=True,
                  guardAllowed=True, appliedIdentityCurrent=False, engineVersion='', runtimeEngineVersion='fixture Gecko')
    before = dict(common, phase='browser-only')
    aligned = dict(common, phase='reconciled', desiredRevision=2, desiredHash='b' * 64, networkMatchesActual=True)
    acknowledged = dict(aligned, phase='acknowledged', appliedRevision=2, appliedHash='b' * 64,
                        connection=1, appliedIdentityCurrent=True, engineVersion='fixture Gecko')
    return dict(schema=1, migrationIdentity=identity, migrationBeforeFixturePreferences=True,
                productionReconciliationInvoked=True, observations=[before, aligned, acknowledged])


def receipt():
    bootstrap = positive('bootstrap-a', 2, 1)
    changed = positive(m.CASE_NAMES[0], 3, 2)
    stopped = operation(m.CASE_NAMES[1], 4, False)
    stopped.update(before=route(3, 'Entry|b'), after={'alive': False, 'pid': 0, 'generation': generation(4)},
                   attemptCapturedBeforeInjection=True, originalAttemptCurrentAtPoll=True, realCoreStopped=True, capturedReceiptMatchesAfter=False,
                   stopConfirmed=True, pendingUnchangedAtPoll=True, modelDesiredRevisionBefore=4, modelAppliedRevisionBefore=4,
                   modelDesiredRevisionAtPoll=4, frozenConnection=4, observedConnection=4)
    stale = operation(m.CASE_NAMES[2], 5, False)
    stale.update(before=route(6, 'Entry|a'), after=route(6, 'Entry|a'),
                 attemptCapturedBeforeInjection=True, originalAttemptCurrentAtPoll=True, realCoreStopped=False, capturedReceiptMatchesAfter=True,
                 stopConfirmed=False, pendingUnchangedAtPoll=True, modelDesiredRevisionBefore=5, modelAppliedRevisionBefore=5,
                 modelDesiredRevisionAtPoll=6, frozenConnection=6, observedConnection=6)
    operations = [bootstrap, changed, stopped, stale]
    report = {'schema': 1, 'status': 'passed', 'sourceCommit': SOURCE, 'runNonce': NONCE,
              'buildIdentity': {'sourceCommit': SOURCE}, 'installedPackage': m.PKG,
              'installedApkSha256': APK, 'runnerOneAttempt': True,
              'actualAndroidExecution': True, 'actualGeckoExecution': True, 'actualMihomoExecution': True,
              'actualInternalCoreApplication': True, 'actualAuthenticatedSocksChain': True,
              'actualPublicWebsite': False, 'publicNetworkTraffic': False, 'actualTrustedGestures': False,
              'coreSha256': 'd' * 64, 'coreVersion': 'synthetic version', 'coreAbi': 'x86_64',
              'fixtureDiagnosticsIsolation': {'geoIpRetryClockHeld': True, 'heldUntilMillis': 1700000600000,
                    'originalGeoIpAttempted': 0, 'testGeoIpAttempted': 1700000600000,
                    'externalLatencyRetryClockHeld': True, 'originalLatencyAttempted': 0,
                    'originalLatencyRouteHash': 'e' * 64,
                    'latencyClockSamples': [{'attempted': 1000, 'routeHash': 'f' * 64}],
                    'admissionStateModified': False, 'scope': 'Synthetic diagnostic scheduling only; original admission runs'},
              'certificateExceptions': 0,
              'testTrust': {field: True for field in ['preparedBeforeRuntime', 'databaseCopyShaVerified',
                  'serverChainShaVerified', 'certificateValidityChecked', 'certificateHostnameSanMatches']},
              'securityEvents': [{'callback': 'GeckoSession.ProgressDelegate.onSecurityChange', 'accepted': True,
                  'isSecure': True, 'isException': False, 'host': 'chatgpt.com', 'certificateSha256': m.LEAF_SHA,
                  'testCaSha256': m.CA_SHA, 'certificateSignedByTestCa': True, 'certificateValidityChecked': True,
                  'certificateHostnameSanMatches': True, 'certificateMatchesPackagedLeaf': True}],
              'fixtureProviderControl': {'automaticDrainSuspended': True, 'removeCallbacksCalled': True,
                  'controlledProviderIdentity': 2, 'registeredProviderIdentity': 1,
                  'drainRevisionBefore': 1, 'drainRevisionAfter': 2},
              'bootstrap': bootstrap, 'cases': [changed, stopped, stale],
              'previousService': {'alive': False, 'pid': 0, 'servicePid': 150},
              'restoration': route(5, 'Entry|b'),
              'requests': [bootstrap['request'], changed['request']],
              'mapping': {'fromHost': 'chatgpt.com', 'fromPort': 443, 'toHost': '127.0.0.1', 'toPort': 18001,
                          'detectorTlsPort': 18002, 'detectorPlainPort': 18003, 'fixedPort': 18004,
                          'dnsOnlyLoopback': True},
              'dnsEvidence': [{'bootstrap': False, 'download': False, 'sinkPort': 18005,
                              **{key: ['127.0.0.1:18005'] for key in
                                 ['default-nameserver', 'nameserver', 'proxy-server-nameserver']}}],
              'fixedDenied': 0, 'entryADenied': 0, 'entryBDenied': 0,
              'fixedRejectedTargets': [], 'externalProxyDenied': 0, 'externalProxyRejectedTargets': [],
              'fixedWire': [{'authenticated': True, 'upstreamHost': '127.0.0.1', 'connectedAtNs': at,
                             'mappedOrigin': True, 'requestedHost': 'chatgpt.com', 'requestedPort': 443,
                             'upstreamPort': 18001} for at in [25, 45]]}
    for field in ['entryAWire', 'entryBWire']:
        report[field] = [{'connectAtNs': 4, 'authRejected': False, 'targetPort': 18004,
                          'acceptedAtNs': 1, 'methodAtNs': 2, 'authAtNs': 3}]
    report['checks'] = [{'name': name, 'pass': True} for name in sorted(m.required_checks())]
    report['checkCount'] = len(report['checks'])
    report['applicationResults'] = [{'id': 'job-' + str(i), 'internal': False,
                                    'ok': row['result']['ok'],
                                    'operationResult': copy.deepcopy(row['result']['operationResult'])}
                                   for i, row in enumerate(operations)]
    report['applicationBootstrap'] = bootstrap_proof()
    report['checks'].extend({'name': name, 'pass': True} for name in m.BOOTSTRAP_CHECKS)
    report['checkCount'] = len(report['checks'])
    return report


class GateTest(unittest.TestCase):
    def verify(self, report):
        m.verify(report, SOURCE, NONCE, APK)

    def rejected(self, report):
        with self.assertRaises((AssertionError, KeyError, ValueError, TypeError)):
            self.verify(report)

    def test_bootstrap_requires_observed_stale_migration_and_real_ack(self):
        for index, field, value in [(0, 'networkMatchesActual', True), (1, 'networkMatchesActual', False),
                                    (1, 'appliedRevision', 3), (1, 'actualHash', 'e' * 64),
                                    (2, 'appliedRevision', 1), (2, 'connection', 0),
                                    (2, 'policyAcknowledged', False), (2, 'guardAllowed', False),
                                    (2, 'appliedIdentityCurrent', False), (2, 'appliedHash', 'e' * 64)]:
            with self.subTest(index=index, field=field):
                report = receipt(); report['applicationBootstrap']['observations'][index][field] = value
                self.rejected(report)
        for field in ['migrationBeforeFixturePreferences', 'productionReconciliationInvoked']:
            report = receipt(); report['applicationBootstrap'][field] = False; self.rejected(report)
        report = receipt(); report['applicationBootstrap']['migrationIdentity']['generation'] += 1; self.rejected(report)
        report = receipt(); report['applicationBootstrap']['observations'].pop(); self.rejected(report)

    def test_complete_synthetic_control(self):
        self.verify(receipt())

    def test_build_nonce_package_and_scope_are_bound(self):
        for field, value in [('sourceCommit', '0' * 40), ('runNonce', '0' * 32),
                             ('installedApkSha256', '0' * 64), ('installedPackage', 'local.pocketchat'),
                             ('runnerOneAttempt', False), ('actualMihomoExecution', False),
                             ('actualInternalCoreApplication', False), ('actualAuthenticatedSocksChain', False),
                             ('publicNetworkTraffic', True), ('actualPublicWebsite', True),
                             ('actualTrustedGestures', True), ('coreAbi', ''), ('coreSha256', 'unverified')]:
            with self.subTest(field=field):
                report = receipt(); report[field] = value; self.rejected(report)
        report = receipt(); report['buildIdentity']['sourceCommit'] = 'old'; self.rejected(report)

    def test_tls_exception_wrong_leaf_or_missing_native_callback_rejected(self):
        for field, value in [('isException', True), ('isSecure', False), ('accepted', False),
                             ('certificateSha256', '0' * 64), ('testCaSha256', '0' * 64),
                             ('host', '127.0.0.1'), ('certificateSignedByTestCa', False)]:
            with self.subTest(field=field):
                report = receipt(); report['securityEvents'][0][field] = value; self.rejected(report)
        report = receipt(); report['securityEvents'] = []; self.rejected(report)
        report = receipt(); report['certificateExceptions'] = 1; self.rejected(report)
        report = receipt(); report['testTrust']['preparedBeforeRuntime'] = False; self.rejected(report)

    def test_diagnostic_isolation_must_not_modify_admission(self):
        report = receipt(); del report['fixtureDiagnosticsIsolation']; self.rejected(report)
        for field in ['geoIpRetryClockHeld', 'heldUntilMillis', 'admissionStateModified']:
            report = receipt(); del report['fixtureDiagnosticsIsolation'][field]; self.rejected(report)
        for field, value in [('geoIpRetryClockHeld', False), ('admissionStateModified', True),
                             ('heldUntilMillis', 0), ('heldUntilMillis', True), ('scope', '')]:
            with self.subTest(field=field, value=value):
                report = receipt(); report['fixtureDiagnosticsIsolation'][field] = value; self.rejected(report)

    def test_external_probe_clock_and_bounded_rejection_evidence_required(self):
        fields = ['originalGeoIpAttempted', 'testGeoIpAttempted', 'externalLatencyRetryClockHeld',
                  'originalLatencyAttempted', 'originalLatencyRouteHash', 'latencyClockSamples']
        for field in fields:
            report = receipt(); del report['fixtureDiagnosticsIsolation'][field]; self.rejected(report)
        for field, value in [('originalGeoIpAttempted', -1), ('testGeoIpAttempted', 1700000600001),
                             ('externalLatencyRetryClockHeld', False), ('originalLatencyAttempted', True),
                             ('originalLatencyAttempted', 1001), ('originalLatencyRouteHash', 'raw-route'),
                             ('latencyClockSamples', []), ('latencyClockSamples', [{}]),
                             ('latencyClockSamples', [{'attempted': True, 'routeHash': 'e' * 64}]),
                             ('latencyClockSamples', [{'attempted': 1000, 'routeHash': 'raw-route'}]),
                             ('latencyClockSamples', [{'attempted': 1000, 'routeHash': 'e' * 64, 'route': 'raw'}]),
                             ('latencyClockSamples', [{'attempted': at, 'routeHash': 'e' * 64} for at in [1000, 999]]),
                             ('latencyClockSamples', [{'attempted': 1000, 'routeHash': 'e' * 64}] * 25)]:
            with self.subTest(field=field, value=value):
                report = receipt(); report['fixtureDiagnosticsIsolation'][field] = value; self.rejected(report)
        for field in ['fixedRejectedTargets', 'externalProxyDenied', 'externalProxyRejectedTargets']:
            report = receipt(); del report[field]; self.rejected(report)
        for field, value in [('fixedRejectedTargets', [{'targetHash': 'd' * 64}]),
                             ('externalProxyDenied', -1), ('externalProxyDenied', True),
                             ('externalProxyDenied', 1), ('externalProxyRejectedTargets', None)]:
            report = receipt(); report[field] = value; self.rejected(report)
        rejection = {'requestHash': 'd' * 64, 'hostAllowlisted': False, 'reason': 'exact-origin-allowlist'}
        for count in [1, 33]:
            report = receipt(); report['externalProxyDenied'] = count
            report['externalProxyRejectedTargets'] = [copy.deepcopy(rejection) for _ in range(min(count, 32))]
            self.verify(report)
        for field, value in [('requestHash', 'raw request'), ('hostAllowlisted', True),
                             ('reason', 'unknown'), ('request', 'raw request')]:
            report = receipt(); report['externalProxyDenied'] = 1
            report['externalProxyRejectedTargets'] = [dict(rejection, **{field: value})]
            self.rejected(report)
        report = receipt(); report['externalProxyDenied'] = 33
        report['externalProxyRejectedTargets'] = [copy.deepcopy(rejection) for _ in range(33)]
        self.rejected(report)

    def test_exact_candidate_identity_revision_and_application_required(self):
        for field, value in [('candidateId', 'another'), ('generation', 2), ('savedRevision', 1),
                             ('appliedRevision', 1), ('applicationState', 'pending'), ('scope', 'next-session'),
                             ('saveState', 'failed'), ('environmentId', generation(99))]:
            with self.subTest(field=field):
                report = receipt(); report['cases'][0]['result']['operationResult'][field] = value
                self.rejected(report)
        report = receipt(); report['cases'][0]['expected']['candidateId'] = report['bootstrap']['expected']['candidateId']; self.rejected(report)

    def test_model_policy_draft_and_real_reconnect_must_match(self):
        for field, value in [('actualModelAppliedRevision', 1), ('modelAppliedHash', '0' * 64),
                             ('modelEngineVersion', 'old'), ('acceptedPolicy', False),
                             ('draftRetained', False), ('productionReconnect', False), ('connectionAfter', 1)]:
            with self.subTest(field=field):
                report = receipt(); report['cases'][0][field] = value; self.rejected(report)
        report = receipt(); report['cases'][0]['documentAfter'] = 'reloaded-document'; self.rejected(report)
        report = receipt(); report['cases'][0]['loadsAfter'] += 1; self.rejected(report)

    def test_fresh_core_receipt_pid_generation_config_and_fixed_exit_required(self):
        for field, value in [('observation', 'cached-ready'), ('alive', False), ('verified', False),
                             ('receiptMatchesFreshState', False), ('pid', 0), ('servicePid', 0),
                             ('receiptGeneration', generation(99)), ('receiptPid', 999),
                             ('receiptConfiguration', '0' * 64), ('currentEntry', 'Entry|a'),
                             ('fixedIdentity', '0' * 64), ('fixedNodeFingerprint', '0' * 64)]:
            with self.subTest(field=field):
                report = receipt(); report['cases'][0]['route'][field] = value; self.rejected(report)
        report = receipt(); report['cases'][0]['route'] = copy.deepcopy(report['bootstrap']['route']); self.rejected(report)

    def test_nonce_echo_server_observation_body_and_external_proxy_are_required(self):
        for field, value in [('nonce', ''), ('echoedNonce', '9' * 32), ('serverObservedNonce', False),
                             ('bodyMatches', False), ('bodySha256', '0' * 64), ('httpStatus', 204),
                             ('mappedAfter', 1), ('externalAfter', 2), ('entryBContacts', 0),
                             ('currentEntry', 'Entry|a'), ('beganAtNs', 100)]:
            with self.subTest(field=field):
                report = receipt(); report['cases'][0]['request'][field] = value; self.rejected(report)
        report = receipt(); row = report['cases'][0]['request']; row['nonce'] = row['echoedNonce'] = report['bootstrap']['request']['nonce']; self.rejected(report)
        report = receipt(); report['requests'][1] = copy.deepcopy(report['requests'][0]); self.rejected(report)

    def test_wire_mapping_cannot_contact_a_public_or_unlisted_target(self):
        for field, value in [('upstreamHost', '8.8.8.8'), ('requestedHost', 'other.invalid'),
                             ('requestedPort', 80), ('upstreamPort', 18099), ('authenticated', False),
                             ('mappedOrigin', False), ('connectedAtNs', 1)]:
            with self.subTest(field=field):
                report = receipt(); report['fixedWire'][1][field] = value; self.rejected(report)
        report = receipt(); report['fixedDenied'] = 1; self.rejected(report)
        report = receipt(); report['mapping']['toHost'] = '8.8.8.8'; self.rejected(report)
        report = receipt(); report['mapping']['toPort'] = report['mapping']['fixedPort']; self.rejected(report)

    def test_authenticated_entry_chain_cannot_be_omitted_or_point_elsewhere(self):
        for field in ['entryAWire', 'entryBWire']:
            report = receipt(); report[field] = []; self.rejected(report)
            report = receipt(); report[field][0]['targetPort'] = 18001; self.rejected(report)
            report = receipt(); report[field][0]['authRejected'] = True; self.rejected(report)
            report = receipt(); report[field][0]['authAtNs'] = 5; self.rejected(report)

    def test_dns_requires_observed_loopback_resolvers_and_no_source_download(self):
        for field in ['default-nameserver', 'nameserver', 'proxy-server-nameserver']:
            report = receipt(); report['dnsEvidence'][0][field] = ['https://1.1.1.1/dns-query']; self.rejected(report)
            report = receipt(); del report['dnsEvidence'][0][field]; self.rejected(report)
        report = receipt(); report['dnsEvidence'] = []; self.rejected(report)
        report = receipt(); report['dnsEvidence'][0]['download'] = True; self.rejected(report)
        report = receipt(); report['dnsEvidence'][0]['bootstrap'] = True; self.rejected(report)

    def test_stopped_core_must_be_really_stopped_and_old_attempt_rejected(self):
        for field, value in [('realCoreStopped', False), ('capturedReceiptMatchesAfter', True),
                             ('attemptCapturedBeforeInjection', False), ('modelDesiredRevisionAtPoll', 5),
                             ('stopConfirmed', False), ('pendingUnchangedAtPoll', False), ('modelAppliedRevisionBefore', 1),
                             ('originalAttemptCurrentAtPoll', False),
                             ('observedConnection', 5)]:
            with self.subTest(field=field):
                report = receipt(); report['cases'][1][field] = value; self.rejected(report)
        for field, value in [('alive', True), ('pid', 203), ('generation', generation(3))]:
            report = receipt(); report['cases'][1]['after'][field] = value; self.rejected(report)
        report = receipt(); report['cases'][1]['result']['ok'] = True; self.rejected(report)
        report = receipt(); report['cases'][1]['result']['operationResult']['appliedRevision'] = 4; self.rejected(report)

    def test_new_desired_revision_must_reject_while_old_route_remains_real(self):
        for field, value in [('modelDesiredRevisionAtPoll', 5), ('realCoreStopped', True),
                             ('capturedReceiptMatchesAfter', False), ('observedConnection', 7)]:
            report = receipt(); report['cases'][2][field] = value; self.rejected(report)
        report = receipt(); report['cases'][2]['after']['verified'] = False; self.rejected(report)
        report = receipt(); report['cases'][2]['after'] = route(7, 'Entry|a'); self.rejected(report)
        report = receipt(); report['cases'][2]['before'] = report['cases'][2]['after'] = route(3, 'Entry|a'); self.rejected(report)

    def test_restoration_is_a_new_verified_core_not_old_ready_state(self):
        for field, value in [('verified', False), ('receiptMatchesFreshState', False),
                             ('pid', 203), ('coreVersion', 'another binary'), ('currentEntry', 'Entry|a')]:
            report = receipt(); report['restoration'][field] = value; self.rejected(report)
        report = receipt(); report['restoration'] = copy.deepcopy(report['cases'][1]['before']); self.rejected(report)
        report = receipt(); report['previousService']['alive'] = True; self.rejected(report)
        report = receipt(); report['previousService']['pid'] = 999; self.rejected(report)

    def test_complete_cases_checks_and_exact_immutable_results_required(self):
        report = receipt(); report['cases'].pop(); self.rejected(report)
        report = receipt(); report['checks'][0]['pass'] = False; self.rejected(report)
        report = receipt(); report['checks'].pop(); report['checkCount'] -= 1; self.rejected(report)
        report = receipt(); report['applicationResults'].pop(); self.rejected(report)
        report = receipt(); report['applicationResults'][0]['internal'] = True; self.rejected(report)
        report = receipt(); report['applicationResults'][0]['operationResult']['candidateId'] = 'other'; self.rejected(report)
        report = receipt(); report['applicationResults'][1]['id'] = report['applicationResults'][0]['id']; self.rejected(report)


if __name__ == '__main__':
    unittest.main()
