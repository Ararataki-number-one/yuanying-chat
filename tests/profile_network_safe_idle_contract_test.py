"""Synthetic contract inputs, never Android evidence; replay the actual verifier."""
import copy
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('safe_idle_contract', ROOT / 'tools/gecko/network_sources_contract.py')
C = importlib.util.module_from_spec(spec)
spec.loader.exec_module(C)
ENV = '11111111-1111-4111-8111-111111111111'


def deletion_proof():
    identity = dict(slot=0, generation=0, environmentId=ENV)
    before = dict(identity, created=True, deleting=False, resetting=False)
    return dict(schema=1, operation='ProfileCatalog.beginDelete', transitionIdentity=identity,
                pendingIdentity=copy.deepcopy(identity), candidateId='1' * 32, pendingState='ready',
                savedRevision=2, catalogBefore=before,
                catalogAfter=dict(before, generation=1, created=False, deleting=True),
                activeBeforeHash='a' * 64, pendingBeforeHash='b' * 64, transactionPresent=False)


def receipt():
    trust = dict(schema=1, method='NSS SQL public-root profile preload',
                 assetDirectory='network-safe-idle-trust/', hostname='chatgpt.com',
                 profilePath='/data/data/local.pocketchat.test/no_backup/gecko-browser',
                 preparedBeforeRuntime=True, databaseCopyShaVerified=True, serverChainShaVerified=True,
                 certificateValidityChecked=True, certificateHostnameSanMatches=True,
                 productionTrustChanged=False, certificateExceptionUsed=False, **C.SAFE_IDLE_TRUST_HASHES)
    security = dict(callback='GeckoSession.ProgressDelegate.onSecurityChange', host='chatgpt.com',
                    origin='https://chatgpt.com', isSecure=True, isException=False,
                    certificateSha256=C.SAFE_IDLE_TRUST_HASHES['testLeafSha256'],
                    testCaSha256=C.SAFE_IDLE_TRUST_HASHES['testCaSha256'],
                    certificateSignedByTestCa=True, certificateValidityChecked=True,
                    certificateHostnameSanMatches=True, certificateMatchesPackagedLeaf=True,
                    accepted=True, verificationError='')
    event = lambda kind, value: dict(kind=kind, value=copy.deepcopy(value))
    events = [event('testTrustPrepared', trust), event('security', security)]
    names = sorted(C.SAFE_IDLE_TRUST_CHECKS) + ['Packaged native ELF exposes its actual ABI, streamed SHA and controller version']
    names += ['Synthetic verifier check ' + str(i) for i in range(59 - len(names))]
    checks = [dict(name=name, **{'pass': True}) for name in names]
    rows, gestures, separations = [], [], []
    for name in C.SAFE_IDLE_CASES:
        sent = name.endswith('send')
        result = dict(environmentId=ENV, generation=0, candidateId='1' * 32, savedRevision=2,
                      appliedRevision=0, saveState='saved', applicationState='pending', scope='session',
                      message='环境已删除或尚未创建' if name == 'capture-delete' else 'saved pending')
        state = dict(connectionEpoch=0, navigationEpoch=0, replyId='reply-' + name if sent else '',
                     operation=False, configurationCapture=False, touchRestored=True,
                     fenced=name.startswith('complete'), confirmed=False,
                     job=dict(done=True, ok=name != 'capture-delete', message=result['message'],
                              operationResult=result, recoveryRequired=False),
                     generation=1 if name.endswith('delete') else 0)
        row = dict(name=name, outcome=state, activeBeforeHash='c' * 64 if name.startswith('complete') else 'a' * 64,
                   activeAfterHash='a' * 64, originalActiveHash='a' * 64,
                   pendingBeforeHash='b' * 64, pendingAfterHash='b' * 64,
                   actualTrustedGesture=sent, injectedState='none' if sent else name.split('-', 1)[1],
                   draft='' if sent else 'network fence prompt', actualInspectDelta=2, actualPageStateDelta=1,
                   reconnectAttempts=0, baselineLineage={})
        if name == 'capture-delete':
            row['deletionEvidence'] = deletion_proof()
        if name == 'complete-late-save':
            row['baselineLineage'] = dict(publishedBaseline='c' * 64, oldBaseline='a' * 64,
                latestBaselineAfter='a' * 64, actualBaselineAfter='a' * 64,
                latestConfigBeforeHash='d' * 64, latestConfigAfterHash='d' * 64,
                entrySnapshotRetained=True, exitSnapshotRetained=True,
                entryPayloadBeforeHash='e' * 64, entryPayloadAfterHash='e' * 64,
                exitPayloadBeforeHash='f' * 64, exitPayloadAfterHash='f' * 64,
                candidateChangedOnlyBaselineAndConsumedLineage=True, lineageConsumed=True, laterValidationPassed=True)
        if name != 'complete-delete':
            phase = 'prepare' if name.startswith('prepare') else 'commit' if name.startswith('capture') else 'complete'
            events.append(event('phase', dict(case=name, phase=phase, operation=phase != 'prepare',
                configurationCapture=phase != 'prepare', activeHash=row['activeBeforeHash'],
                pendingCandidateHash=row['pendingBeforeHash'], connectionEpoch=0)))
        if sent:
            tap = dict(case=name, css=dict(x=10, y=20, width=320, height=600),
                       native=dict(x=0, y=0, width=320, height=600))
            events += [event('tapNeeded', tap), event('gesture', dict(case=name, trusted=True, sent=1,
                replyId=state['replyId'], observedBy='Production Gecko extension → WebReplyObserver.receive'))]
            gestures.append(dict(case=name, oneAttempt=True, bounds=copy.deepcopy(tap), x=10, y=20,
                                 command=['shell', 'input', 'tap', '10', '20']))
        elif name == 'capture-delete':
            events.append(event('injection', dict(case=name, kind='delete', realCatalogGeneration=1,
                scope='controlled state injected at actual production phase', deletionEvidence=row['deletionEvidence'])))
        elif name == 'complete-delete':
            events.append(event('injection', dict(case=name, oldGeneration=0, newGeneration=1, commitPrecededDeletion=True)))
        elif name == 'complete-late-save':
            events.append(event('injection', dict(case=name, oldBaseline='a' * 64, publishedBaseline='c' * 64)))
        if len(rows) < 5:
            separation = dict(schema=1, case=name, activeBeforeHash=row['activeBeforeHash'],
                activeAfterHash=row['activeAfterHash'], pendingBeforeHash=row['pendingBeforeHash'],
                pendingAfterHash=row['pendingAfterHash'], activeUnchanged=True, pendingUnchanged=True)
            separations.append(separation)
            events.append(event('candidateSeparation', separation))
        rows.append(row)
        events.append(event('case', row))
    events.append(event('result', dict(status='passed', checkCount=59)))
    return dict(status='passed', sourceCommit='a' * 40, installedApkSha256='c' * 64,
        installedPackage='local.pocketchat.test', coreAbi='x86_64', coreSha256='d' * 64, coreVersion='synthetic',
        actualAndroidExecution=True, actualGeckoExecution=True, actualNativeParsing=True,
        actualNativeExecution=True, actualKeystoreEncryption=True, actualRouteApplication=False,
        actualPublicWebsite=False, actualTestCaTrust=True, certificateExceptions=0,
        fixtureProviderControl=dict(removeCallbacksCalled=True, automaticDrainSuspended=True,
            registeredProviderIdentity=1, controlledProviderIdentity=2, drainRevisionBefore=0, drainRevisionAfter=1),
        candidateSeparation=separations, runnerOneAttemptPerGesture=True, parseCount=2,
        actualTrustedGestures=2, actualAndroidGestures=gestures, proxyAccepted=1, proxyRejected=0,
        pageDocuments=1, controlledTlsPort=4443, proxyUpstreamConnections=['127.0.0.1:4443'],
        testCaTrust=trust, securityEvents=[security], phaseEvents=events, checkCount=59, checks=checks,
        cases=rows, **C.SAFE_IDLE_TRUST_HASHES)


def sync_case(report):
    """Do not let duplicate-event mismatch mask an inner-field negative control."""
    row = report['cases'][4]
    for event in report['phaseEvents']:
        if event['kind'] == 'case' and event['value']['name'] == row['name']:
            event['value'] = copy.deepcopy(row)
        if event['kind'] == 'injection' and event['value']['case'] == row['name'] and 'deletionEvidence' in row:
            event['value']['deletionEvidence'] = copy.deepcopy(row['deletionEvidence'])


class SafeIdleContractTest(unittest.TestCase):
    def reject(self, mutate, sync=True):
        value = receipt()
        mutate(value)
        if sync:
            sync_case(value)
        with self.assertRaises((AssertionError, KeyError, TypeError)):
            C.verify_safe_idle(value)

    def test_full_synthetic_contract_passes_without_mutation(self):
        value = receipt()
        before = copy.deepcopy(value)
        result = C.verify_safe_idle(value)
        self.assertEqual(result['safeIdleCases'], 7)
        self.assertEqual(value, before)

    def test_only_capture_delete_requires_failure(self):
        for index in range(7):
            self.reject(lambda r, i=index: r['cases'][i]['outcome']['job'].update(ok=i == 4))

    def test_done_and_ok_require_actual_booleans(self):
        for field in ('done', 'ok'):
            for value in (0, 1, 'false', None):
                self.reject(lambda r, f=field, v=value: r['cases'][4]['outcome']['job'].update({f: v}))

    def test_message_alone_or_missing_original_identity_never_passes(self):
        self.reject(lambda r: r['cases'][4].pop('deletionEvidence'))
        for field in ('transitionIdentity', 'pendingIdentity', 'catalogBefore', 'catalogAfter'):
            self.reject(lambda r, f=field: r['cases'][4]['deletionEvidence'].pop(f))

    def test_catalog_must_be_same_uuid_and_exact_deletion_generation(self):
        for field in ('catalogBefore', 'catalogAfter'):
            for key, value in (('environmentId', '22222222-2222-4222-8222-222222222222'),
                               ('slot', 1), ('generation', 7), ('resetting', True)):
                self.reject(lambda r, f=field, k=key, v=value: r['cases'][4]['deletionEvidence'][f].update({k: v}))
        for field, key, value in [('catalogBefore', 'created', False), ('catalogBefore', 'deleting', True),
                                  ('catalogAfter', 'created', True), ('catalogAfter', 'deleting', False)]:
            self.reject(lambda r, f=field, k=key, v=value: r['cases'][4]['deletionEvidence'][f].update({k: v}))

    def test_pending_and_operation_receipt_are_bound_to_captured_identity(self):
        for field in ('pendingIdentity', 'transitionIdentity'):
            self.reject(lambda r, f=field: r['cases'][4]['deletionEvidence'][f].update(generation=9))
        for key, value in [('environmentId', '22222222-2222-4222-8222-222222222222'),
                           ('generation', 1), ('candidateId', '2' * 32), ('savedRevision', 3)]:
            self.reject(lambda r, k=key, v=value: r['cases'][4]['outcome']['job']['operationResult'].update({k: v}))

    def test_numbers_reject_booleans_floats_strings_and_missing(self):
        paths = [('deletionEvidence', 'schema'), ('deletionEvidence', 'savedRevision'),
                 ('deletionEvidence', 'catalogAfter', 'generation'), ('deletionEvidence', 'transitionIdentity', 'slot'),
                 ('outcome', 'generation'), ('outcome', 'job', 'operationResult', 'appliedRevision'),
                 ('outcome', 'job', 'operationResult', 'generation'), ('outcome', 'job', 'operationResult', 'savedRevision')]
        for path in paths:
            for value in (True, False, 0.0, 1.0, '1', None):
                def mutate(r, path=path, value=value):
                    target = r['cases'][4]
                    for key in path[:-1]:
                        target = target[key]
                    target[path[-1]] = value
                self.reject(mutate)

    def test_saved_never_means_applied_or_uncertain(self):
        for key, value in [('applicationState', 'applied'), ('applicationState', 'saved-unconfirmed'),
                           ('saveState', 'failed'), ('appliedRevision', 2), ('scope', 'core')]:
            self.reject(lambda r, k=key, v=value: r['cases'][4]['outcome']['job']['operationResult'].update({k: v}))
        self.reject(lambda r: r['cases'][4]['outcome']['job'].update(recoveryRequired=True))
        for key, value in [('transactionPresent', True), ('pendingState', 'staged'), ('operation', 'fake-delete')]:
            self.reject(lambda r, k=key, v=value: r['cases'][4]['deletionEvidence'].update({k: v}))

    def test_no_reconnect_write_fence_or_pending_reply_can_hide_as_deletion(self):
        for key in ('operation', 'configurationCapture', 'confirmed', 'fenced'):
            self.reject(lambda r, k=key: r['cases'][4]['outcome'].update({k: True}))
        self.reject(lambda r: r['cases'][4].update(reconnectAttempts=1))
        self.reject(lambda r: r['cases'][4]['outcome'].update(connectionEpoch=1))
        self.reject(lambda r: r['cases'][4]['outcome'].update(replyId='new-reply'))
        self.reject(lambda r: r['cases'][4].update(draft=''))

    def test_original_active_and_pending_hashes_must_stay_exact(self):
        for key in ('activeBeforeHash', 'activeAfterHash', 'originalActiveHash', 'pendingBeforeHash', 'pendingAfterHash'):
            self.reject(lambda r, k=key: r['cases'][4].update({k: 'f' * 64}))
        for key in ('activeBeforeHash', 'pendingBeforeHash'):
            self.reject(lambda r, k=key: r['cases'][4]['deletionEvidence'].update({k: 'f' * 64}))

    def test_deletion_event_is_unique_bound_and_ordered(self):
        def event(report, kind):
            return next(e for e in report['phaseEvents'] if e['kind'] == kind and e['value'].get('case') == 'capture-delete')
        self.reject(lambda r: r['phaseEvents'].append(copy.deepcopy(event(r, 'injection'))))
        self.reject(lambda r: r['phaseEvents'].remove(event(r, 'injection')))
        self.reject(lambda r: event(r, 'injection')['value'].update(kind='navigation'))
        self.reject(lambda r: event(r, 'injection')['value'].update(realCatalogGeneration=2))
        self.reject(lambda r: event(r, 'phase')['value'].update(phase='complete'))
        self.reject(lambda r: event(r, 'phase')['value'].update(connectionEpoch=1))
        self.reject(lambda r: event(r, 'candidateSeparation')['value'].update(activeUnchanged=False))
        def reorder(r):
            value = event(r, 'injection')
            r['phaseEvents'].remove(value)
            r['phaseEvents'].insert(0, value)
        self.reject(reorder)

    def test_raw_case_event_must_match_report_without_synthesis(self):
        self.reject(lambda r: next(e for e in r['phaseEvents'] if e['kind'] == 'case' and e['value']['name'] == 'capture-delete')['value']['outcome']['job'].update(ok=True), sync=False)

    def test_complete_delete_keeps_original_success_and_rollback_contract(self):
        self.reject(lambda r: r['cases'][5]['outcome']['job'].update(ok=False))
        self.reject(lambda r: r['cases'][5].update(activeAfterHash='f' * 64))


if __name__ == '__main__':
    unittest.main()
