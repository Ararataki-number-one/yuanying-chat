#!/usr/bin/env python3
"""Verifier-only synthetic receipts; none are Android/device evidence."""
import copy
import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('settings_application', ROOT / 'tests/gecko/run_network_settings_application.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
SOURCE, NONCE, APK = 'a' * 40, 'b' * 32, 'c' * 64
ENV, OTHER = '11111111-1111-4111-8111-111111111111', '22222222-2222-4222-8222-222222222222'


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
    wanted = {'environmentId': ENV, 'generation': 1, 'candidateId': 'candidate-1', 'savedRevision': 2}
    names = ['Application fixture starts with production external route and model acknowledgement',
             'Busy save retains the exact pending intent and current document',
             'Applied result matches the actual accepted browser and external route',
             'Same-proxy application preserves the document draft and unsent question',
             'Completed internal application leaves the original pending receipt immutable',
             'Receipt-read fault preserves the genuinely saved ready intent',
             'Newer candidate survives the old completion cleanup',
             'No session can report a setting as actually applied']
    cases = []
    for name in m.CASE_NAMES:
        if name in m.CASE_NAMES[7:9]:
            submitted = {'slot': 0, 'generation': 2 if name == 'old-environment-generation' else 1,
                         'environmentId': OTHER if name == 'wrong-environment-uuid' else ENV}
            cases.append({'name': name, 'result': {'done': True, 'ok': False},
                          'directRequestResult': {'done': True, 'ok': False}, 'directRequestRejected': True,
                          'expectedIdentity': {'slot': 0, 'generation': 1, 'environmentId': ENV},
                          'submittedIdentity': submitted, 'rejectedBeforeSave': True,
                          'encryptedStorageBefore': 'e' * 64, 'encryptedStorageAfter': 'e' * 64})
            names.extend([name + ': stale environment request is rejected before saving',
                          name + ': direct queued request also preserves encrypted model pending and active state'])
            continue
        actual = dict(wanted, saveState='saved', applicationState='saved-unconfirmed', scope='session', appliedRevision=0)
        if name == 'pending-while-web-busy':
            actual['applicationState'] = 'pending'
        if name == 'applied-after-safe-idle':
            actual.update(applicationState='applied', appliedRevision=2)
        if name == 'saved-receipt-read-failure':
            actual['savedRevision'] = 0
        if name == 'no-session':
            actual['scope'] = 'next-session'
        case = {'name': name, 'expected': copy.deepcopy(wanted),
                'result': {'done': True, 'ok': name not in m.STALE and name != 'saved-receipt-read-failure', 'operationResult': actual}}
        if name == 'pending-while-web-busy':
            case.update(actualDomBusy=True, pendingSnapshotHash='d' * 64)
        if name == 'applied-after-safe-idle':
            case.update(sameCandidateAsPending=True, actualModelDesiredRevision=2, actualModelAppliedRevision=2,
                        modelEngineVersion='GeckoView controlled', runtimeEngineVersion='GeckoView controlled',
                        actualConfigurationHash='f' * 64, modelDesiredHash='f' * 64, modelAppliedHash='f' * 64,
                        documentBefore='doc-1', documentAfter='doc-1', loadsBefore=1, loadsAfter=1,
                        actualConfigurationMatches=True, acceptedPolicy=True, draftRetained=True,
                        documentRetained=True, reconnectObserved=True)
        if name == 'saved-receipt-read-failure':
            case.update(faultHits=1, actualReadyIntentRetained=True)
        if name in m.STALE:
            case.update(attemptCapturedBeforeInjection=True, capturedConnection=5, observedConnection=6,
                        modelDesiredRevisionAtPoll=3, sessionAbsentAtPoll=name == 'retired-session',
                        newerPendingRetained=name == 'newer-candidate', injection=name)
            names.append(name + ': an old application callback cannot claim success')
        if name == 'no-session':
            case['sessionAbsent'] = True
        names.extend([name + ': result belongs to the exact environment and candidate',
                      name + ': saved and applied states remain distinct'])
        cases.append(case)
    report = {'status': 'passed', 'sourceCommit': SOURCE, 'runNonce': NONCE,
              'buildIdentity': {'sourceCommit': SOURCE}, 'installedPackage': m.PKG,
              'installedApkSha256': APK, 'runnerOneAttempt': True,
              'actualAndroidExecution': True, 'actualGeckoExecution': True, 'actualKeystoreEncryption': True,
              'actualExternalRouteApplication': True, 'actualInternalCoreApplication': False,
              'actualPublicWebsite': False, 'actualTrustedGestures': False,
              'productionRequestInvoked': True, 'productionDrainInvoked': True, 'productionModelAcknowledgement': True,
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
              'checks': [{'name': name, 'pass': True} for name in names], 'checkCount': len(names),
              'applicationCases': cases}
    report['applicationResults'] = [{'id': 'internal:positive', 'internal': True, 'ok': True,
                                    'operationResult': copy.deepcopy(cases[1]['result']['operationResult'])}]
    report['applicationBootstrap'] = bootstrap_proof()
    report['checks'].extend({'name': name, 'pass': True} for name in m.BOOTSTRAP_CHECKS)
    report['checkCount'] = len(report['checks'])
    return report


class GateTest(unittest.TestCase):
    def verify(self, report):
        m.verify(report, SOURCE, NONCE, APK)

    def rejected(self, report):
        with self.assertRaises((AssertionError, KeyError, ValueError)):
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

    def test_stale_build_nonce_and_scope_rejected(self):
        for field, value in [('sourceCommit', 'old'), ('runNonce', 'old'), ('installedApkSha256', 'old'),
                             ('actualInternalCoreApplication', True), ('actualPublicWebsite', True),
                             ('actualExternalRouteApplication', False), ('productionModelAcknowledgement', False),
                             ('runnerOneAttempt', False)]:
            with self.subTest(field=field):
                report = receipt(); report[field] = value; self.rejected(report)

    def test_pending_or_old_revision_cannot_impersonate_applied(self):
        for field, value in [('applicationState', 'pending'), ('appliedRevision', 1), ('savedRevision', 1),
                             ('candidateId', 'another'), ('generation', 2), ('environmentId', OTHER), ('scope', 'next-session')]:
            with self.subTest(field=field):
                report = receipt(); report['applicationCases'][1]['result']['operationResult'][field] = value
                self.rejected(report)

    def test_model_policy_or_document_mismatch_rejected(self):
        for field, value in [('actualModelAppliedRevision', 1), ('modelAppliedHash', '0' * 64),
                             ('acceptedPolicy', False), ('modelEngineVersion', 'old'),
                             ('documentAfter', 'replacement'), ('loadsAfter', 2), ('draftRetained', False)]:
            with self.subTest(field=field):
                report = receipt(); report['applicationCases'][1][field] = value; self.rejected(report)

    def test_snapshot_and_saved_receipt_read_failure_are_required(self):
        report = receipt(); report['applicationCases'][1]['expected']['candidateId'] = 'different'; self.rejected(report)
        report = receipt(); report['applicationCases'][2]['result']['operationResult']['saveState'] = 'failed'; self.rejected(report)
        report = receipt(); report['applicationCases'][2]['actualReadyIntentRetained'] = False; self.rejected(report)
        report = receipt(); report['applicationCases'][2]['result']['operationResult']['savedRevision'] = 2; self.rejected(report)

    def test_stale_attempt_has_to_be_captured_before_real_difference(self):
        for index, field, value in [(3, 'modelDesiredRevisionAtPoll', 2), (4, 'newerPendingRetained', False),
                                    (5, 'observedConnection', 5), (6, 'sessionAbsentAtPoll', False),
                                    (3, 'attemptCapturedBeforeInjection', False)]:
            with self.subTest(index=index, field=field):
                report = receipt(); report['applicationCases'][index][field] = value; self.rejected(report)
        report = receipt(); report['applicationCases'][5]['result']['ok'] = True; self.rejected(report)

    def test_stale_environment_must_preserve_storage_and_reject_direct_request(self):
        for index in (7, 8):
            report = receipt(); report['applicationCases'][index]['encryptedStorageAfter'] = '0' * 64; self.rejected(report)
            report = receipt(); report['applicationCases'][index]['directRequestResult']['ok'] = True; self.rejected(report)
        report = receipt(); report['applicationCases'][7]['submittedIdentity']['generation'] = 1; self.rejected(report)
        report = receipt(); report['applicationCases'][8]['submittedIdentity']['environmentId'] = ENV; self.rejected(report)

    def test_no_session_cannot_be_applied_or_have_known_applied_revision(self):
        for field, value in [('applicationState', 'applied'), ('appliedRevision', 2), ('scope', 'session')]:
            with self.subTest(field=field):
                report = receipt(); report['applicationCases'][9]['result']['operationResult'][field] = value; self.rejected(report)
        report = receipt(); report['applicationCases'][9]['sessionAbsent'] = False; self.rejected(report)

    def test_tls_bypass_missing_case_or_failed_check_rejected(self):
        report = receipt(); report['securityEvents'][0]['isException'] = True; self.rejected(report)
        report = receipt(); report['securityEvents'][0]['certificateSha256'] = '0' * 64; self.rejected(report)
        report = receipt(); report['testTrust']['preparedBeforeRuntime'] = False; self.rejected(report)
        report = receipt(); report['applicationCases'].pop(); self.rejected(report)
        report = receipt(); report['checks'][0]['pass'] = False; self.rejected(report)
        report = receipt(); report['checks'].pop(); report['checkCount'] -= 1; self.rejected(report)

    def test_internal_observation_must_match_one_applied_operation(self):
        report = receipt(); report['applicationResults'][0]['internal'] = False; self.rejected(report)
        report = receipt(); report['applicationResults'].append(copy.deepcopy(report['applicationResults'][0])); self.rejected(report)
        report = receipt(); report['applicationResults'][0]['operationResult']['candidateId'] = 'other'; self.rejected(report)


if __name__ == '__main__':
    unittest.main()
