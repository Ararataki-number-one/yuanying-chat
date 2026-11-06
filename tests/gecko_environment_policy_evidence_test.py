"""Synthetic checker-schema/adversarial controls. No Android execution occurs here.

The fixture inputs contain actualAndroidExecution=True solely because that is
the production receipt schema being tested. These unit tests do not attest it.
"""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('gecko_environment_policy_evidence', ROOT / 'tools/browser/check_gecko_environment_policy_evidence.py')
gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)
import browser_fingerprint_evidence_test as historical

SOURCE, TREE, NONCE = 'a' * 40, 'b' * 40, 'c' * 32
SOURCE_BYTES = ('// Synthetic source oracle, never a device execution receipt.\n'
                'static final String VERSION="GeckoView 157.0.1 · 输入同步修正";\n').encode('utf-8')
SHA = hashlib.sha256(SOURCE_BYTES).hexdigest()
MOBILE = 'Mozilla/5.0 (Android 15; Mobile; rv:157.0) Gecko/157.0 Firefox/157.0'
DESKTOP = 'Mozilla/5.0 (X11; Linux x86_64; rv:157.0) Gecko/157.0 Firefox/157.0'


def raw_clock(selected):
    # Independent literal clock oracle for 2026-01-15/07-15T12:00:00Z. Do not
    # derive fixture expectations with the checker implementation under test.
    if selected == 'America/New_York':
        a, b = (300, 7, 0), (240, 8, 0)
    elif selected == 'Asia/Kathmandu':
        a = b = (-345, 17, 45)
    elif selected == 'Pacific/Kiritimati':
        a = b = (-840, 2, 0)
    else:
        assert selected == 'UTC'
        a = b = (0, 12, 0)
    def row(month, values):
        return dict(offsetMinutes=values[0], year=2026, month=month, day=16 if selected == 'Pacific/Kiritimati' else 15, hour=values[1], minute=values[2])
    return dict(timeZone=selected, january=row(1, a), july=row(7, b))


class GeckoEnvironmentEvidenceTests(unittest.TestCase):
    def document(self, shared=True, service=True, realm_differences=True):
        previous = historical.FingerprintEvidenceTests().document()
        identity = previous['expectedBuildIdentity']
        owner = dict(slot=0, generation=1, environmentId='00000000-0000-0000-0000-000000000001')
        requests, samples = [], []
        sequence = 0

        def document_id():
            nonlocal sequence
            sequence += 1
            return '00000000-0000-0000-0000-' + str(sequence).zfill(12)

        def request(page, realm, path, ua, initial=False):
            requests.append(dict(origin=page['origin'], path=path, tls=True, method='GET', phase=page['phase'], realm=realm, documentId='' if initial else page['documentId'], **{'user-agent': ua}))
            if path == '/env-policy' and page['phase'] == 'gecko-coop':
                requests[-1]['responseCoop'] = 'same-origin'

        labels = list(gate.LABELS[:7]) + ['desktop-applied', 'desktop', 'mobile-restored-applied', 'mobile-restored', 'rfp-system-reset', 'rfp-applied']
        phases = ['gecko-system-mobile', 'gecko-ny-mobile', 'gecko-coop', 'gecko-kathmandu-mobile', 'gecko-kathmandu-mobile', 'gecko-kathmandu-mobile', 'gecko-kathmandu-mobile', 'gecko-kathmandu-mobile', 'gecko-desktop', 'gecko-desktop', 'gecko-mobile-restored', 'gecko-mobile-restored', 'gecko-mobile-restored']
        contexts = ['100', '101', '102', '103', '103', '104', '105', '106', '106', '107', '107', '108', '109']
        for index, label in enumerate(labels):
            desired = '' if label in {'system', 'rfp-system-reset', 'rfp-applied'} else 'America/New_York' if label in {'new-york', 'coop'} else 'Asia/Kathmandu'
            desired_clock = desired or 'UTC'
            revision = 1 if label == 'system' else 2 if label in {'new-york', 'coop'} else 4 if label in {'rfp-system-reset', 'rfp-applied'} else 3
            native_ua = DESKTOP if label in {'desktop', 'desktop-applied'} else MOBILE
            context = contexts[index]
            session_id, epoch, token = 'sdk-session-' + context, 'open-epoch-' + context, format(int(context), '064x')
            actual = dict(schema=1, status='applied', requestToken=token, sessionId=session_id, requestedZoneId=desired, nativeZoneId=desired, contextId=context, nativeSettingReadback=True, scope='top-browsing-context', workerCoverageVerified=False, serviceWorkerCoverageVerified=False)
            receipt = dict(schema=1, identity=copy.deepcopy(owner), desiredRevision=revision, processNonce='f'*64, requestToken=token, binding=dict(engineVersion='GeckoView 157.0.1 · 输入同步修正', sessionId=session_id, sessionEpoch=epoch, contextId=context), nativeSettingReadback=True, pageObservationVerified=False, workerCoverageVerified=False, serviceWorkerCoverageVerified=False, nativeReceipt=actual, recordedAt=1793836800000 + index)
            policy = dict(schema=1, engine='gecko', loaded=True, desiredZone=desired, desiredRevision=revision, state='native-readback', nativeSettingReadback=True, scope='top-browsing-context', appliedScope='top-browsing-context', pageObservationVerified=False, workerCoverageVerified=False, serviceWorkerCoverageVerified=False, issue='', currentSessionPrepared=True, popupScope='custom-zone-popups-blocked')
            fresh = dict(actual, status='read', requestToken=format(5000+index, '064x'))
            native = dict(sessionId=session_id, sessionEpoch=epoch, contextId=context, desiredRevision=revision, desiredZone=desired, receipt=receipt, freshReadback=fresh, contextCurrent=True, timeZonePolicy=policy, userAgent=native_ua, desktop=label in {'desktop', 'desktop-applied'}, headerPolicy=dict(installed=True, nativeReadback=True, revision=index + 1, userAgent=native_ua, scope='public-http-request-ua-only', privateAdmission='unchanged-original-headers', sharedWorkerWireVerified=False, serviceWorkerWireVerified=False))
            page = dict(schema=1, firstInline=True, secure=True, runNonce=NONCE, sourceCommit=SOURCE, documentId=document_id(), phase=phases[index], origin='https://fp-b.pocketchat.test' if label == 'coop' else 'https://fp-a.pocketchat.test', nativeUserAgent=native_ua, nativeTimeZone=raw_clock(desired_clock), markerComplete=True, networkAllowed=True)
            request(page, 'document', '/env-policy', native_ua, True)
            request(page, 'document', '/worker-probe', native_ua)
            frames = []
            for origin in sorted(gate.ORIGINS):
                frame = dict(schema=1, firstInline=True, secure=True, runNonce=NONCE, sourceCommit=SOURCE, documentId=document_id(), phase=page['phase'], origin=origin, nativeUserAgent=native_ua, nativeTimeZone=raw_clock('UTC' if realm_differences else desired_clock), markerComplete=True, networkAllowed=True)
                frames.append(frame)
                request(frame, 'frame', '/env-frame', native_ua, True)
                request(frame, 'document', '/worker-probe', native_ua)
            workers = dict(started=label in gate.FULL_WORKER_LABELS, complete=label in gate.FULL_WORKER_LABELS, cases={})
            if workers['started']:
                for name, realm in gate.WORKER_ROLES.items():
                    available = shared if name == 'shared' else service if name == 'service' else True
                    row = dict(available=available, created=available, executed=available, networkAllowed=available)
                    if available:
                        row.update(nativeUserAgent=native_ua, nativeTimeZone=raw_clock('UTC' if realm_differences else desired_clock), sourceRole='service-worker' if name == 'service' else realm)
                        request(page, realm, '/worker-probe', native_ua)
                        if name in gate.SCRIPT_PATHS:
                            request(page, 'service-worker' if name == 'service' else realm, gate.SCRIPT_PATHS[name], native_ua)
                        if name == 'service':
                            request(page, 'service-worker-install', '/sw-cached', native_ua)
                    else:
                        row['reason'] = 'Native API unavailable'
                    workers['cases'][name] = row
            samples.append(dict(label=label, url=page['origin'] + '/env-policy?phase=' + page['phase'], page=page, frames=frames, workers=workers, native=native, security=dict(isSecure=True, isException=False, host=page['origin'].split('//')[1], leafDerSha256=previous['hostTls']['leafDerSha256'], enterpriseRootsReadback=True)))

        by_label = {sample['label']: sample for sample in samples}
        def native(label):
            return by_label[label]['native']
        lifecycle = dict(
            reload=dict(beforeDocumentId=by_label['kathmandu']['page']['documentId'], afterDocumentId=by_label['reload']['page']['documentId'], beforeContextId=native('kathmandu')['contextId'], afterContextId=native('reload')['contextId']),
            reopen=dict(beforeDocumentId=by_label['reload']['page']['documentId'], afterDocumentId=by_label['reopen']['page']['documentId'], beforeContextId=native('reload')['contextId'], afterContextId=native('reopen')['contextId']),
            restore=dict(beforeContextId=native('reopen')['contextId'], afterContextId=native('restore')['contextId'], sdkCheckpointAvailable=True, formValueRestored=True, actualRestoreRequests=1),
            coop=dict(fromOrigin=by_label['new-york']['page']['origin'], toOrigin=by_label['coop']['page']['origin'], oldContextId=native('new-york')['contextId'], newContextId=native('coop')['contextId'], contextChanged=True, firstInlineZoneCorrect=True, responseHeaderObserved=True),
        )
        fixture = copy.deepcopy(previous['results']['gecko']['fixture'])
        fixture.update(requests=requests, accepted=len(requests), tlsConnections=len(requests))
        activity = dict(schema=1, engine='gecko', status='passed', stage='complete', sourceCommit=SOURCE, sourceTree=TREE, runNonce=NONCE, buildIdentity=dict(copy.deepcopy(identity), scope='Installed synthetic integration APK bytes and embedded source stamp only'), checks=[dict(id=name, **{'pass': True}) for name in sorted(gate.REQUIRED)], samples=[sample for sample in samples if sample['label'] in gate.LABELS], transitionSamples=[by_label['desktop-applied'], by_label['mobile-restored-applied']], rfpResetBaseline=by_label['rfp-system-reset'], rfpFinalObservation=by_label['rfp-applied'],
            staleTicketProof=dict(actualStoreRecordAttempt=True, oldRecordRejected=True, oldReceiptEmpty=True, oldContextId=native('reload')['contextId'], newContextId=native('reopen')['contextId'], oldToken=native('reload')['receipt']['requestToken'], newToken=native('reopen')['receipt']['requestToken']),
            staleRevisionProof=dict(actualStoreRecordAttempt=True, actualStoreReceiptAttempt=True, currentReceiptRead=True, oldRecordRejected=True, oldReceiptRejected=True, currentReceiptPreserved=True, oldRevision=native('new-york')['desiredRevision'], newRevision=native('kathmandu')['desiredRevision'], oldContextId=native('new-york')['contextId'], newContextId=native('kathmandu')['contextId'], oldToken=native('new-york')['receipt']['requestToken'], newToken=native('kathmandu')['receipt']['requestToken']),
            popupProof=dict(actualNavigationDelegate=True, customRejected=True, sessionCountBefore=1, sessionCountAfter=1, oldNativeSessionUnchanged=True),
            rfpConflictProof=dict(actualUiAttempt=True, levelBefore=2, levelAfter=2, rfpConfirmed=True, desiredRevisionBefore=4, desiredRevisionAfter=4, savedZoneBefore='', savedZoneAfter='', customSaveRejected=True), lifecycle=lifecycle, fixture=fixture, actualAndroidExecution=True, actualGeckoExecution=True, actualPublicWebsiteExecution=False, workerCoverageVerified=False, serviceWorkerCoverageVerified=False)
        return dict(schema=1, fixtureType=gate.FIXTURE_TYPE, status='passed', sourceCommit=SOURCE, sourceTree=TREE, runNonce=NONCE, expectedBuildIdentity=copy.deepcopy(identity), activity=activity, hostTls=copy.deepcopy(previous['hostTls']), systemTimeZone=dict(zoneId='UTC', source='android-getprop-persist.sys.timezone', januaryOffsetMinutes=0, julyOffsetMinutes=0), sourceFiles={path: SHA for path in gate.SOURCE_INPUTS}, executionInputsUnchanged=True, cleanup=dict(appStopped=True, reverseRemoved=True, caRemoved=True, privateMaterialRemoved=True))

    def validate(self, value):
        return gate.validate_behavior(value, SOURCE, lambda source, path: SOURCE_BYTES)

    def reject_changes(self, changes):
        for index, change in enumerate(changes):
            with self.subTest(index=index):
                value = self.document()
                change(value)
                with self.assertRaises(ValueError):
                    self.validate(value)

    def test_consistent_synthetic_schema_and_honest_realm_differences(self):
        for shared in (False, True):
            for service in (False, True):
                with self.subTest(shared=shared, service=service):
                    report = self.document(shared, service)
                    original = copy.deepcopy(report)
                    result = self.validate(report)
                    self.assertEqual(report, original, 'Checker must not mutate its raw observations')
                    self.assertEqual(len(result['samples']), 9)
                    self.assertEqual(len(result['_derivedWorkerTimeZoneDifferences']), 4 * (3 + shared + service))
                    self.assertEqual(len(result['_derivedFrameTimeZoneDifferences']), 20)
                    self.assertFalse(result['workerCoverageVerified'])
                    self.assertFalse(result['serviceWorkerCoverageVerified'])
        self.assertEqual(self.validate(self.document(realm_differences=False))['_derivedWorkerTimeZoneDifferences'], [])
        empty_popups = self.document()
        empty_popups['activity']['popupProof'].update(sessionCountBefore=0, sessionCountAfter=0)
        self.validate(empty_popups)
        rfp_managed = self.document()
        rfp_managed['activity']['rfpFinalObservation']['page']['nativeTimeZone'] = raw_clock('America/New_York')
        self.assertEqual(self.validate(rfp_managed)['_derivedRfpTimeZoneObservation'], raw_clock('America/New_York'))

    def test_fixed_epoch_oracle_includes_dst_and_forty_five_minute_zone(self):
        for selected in ('UTC', 'America/New_York', 'Asia/Kathmandu', 'Pacific/Kiritimati'):
            self.assertTrue(gate.clock_matches(raw_clock(selected), selected), selected)
        wrong = raw_clock('America/New_York')
        wrong['july']['offsetMinutes'] = 300
        self.assertFalse(gate.clock_matches(wrong, 'America/New_York'))
        alias = raw_clock('Asia/Kathmandu')
        alias['timeZone'] = 'Asia/Katmandu'
        self.assertTrue(gate.clock_matches(alias, 'Asia/Kathmandu'))
        alias['timeZone'] = 'Asia/Kolkata'
        self.assertFalse(gate.clock_matches(alias, 'Asia/Kathmandu'))

    def test_wrapper_invocation_typed_flags_and_cleanup_fail_closed(self):
        self.reject_changes([
            lambda r: r.update(schema=True), lambda r: r.update(fixtureType='other'), lambda r: r.update(status='failed'), lambda r: r.update(sourceCommit='f'*40), lambda r: r.update(sourceTree='old'), lambda r: r.update(runNonce='old'), lambda r: r.update(executionInputsUnchanged=False), lambda r: r.update(actualAndroidExecution=False), lambda r: r.update(workerCoverageVerified=True),
            *[lambda r, key=key: r['cleanup'].update({key: False}) for key in ('appStopped', 'reverseRemoved', 'caRemoved', 'privateMaterialRemoved')],
            lambda r: r['activity'].update(schema=True), lambda r: r['activity'].update(engine='chromium'), lambda r: r['activity'].update(status='running'), lambda r: r['activity'].update(stage='running'), lambda r: r['activity'].update(runNonce='d'*32), lambda r: r['activity'].update(sourceTree='d'*40), lambda r: r['activity'].update(actualAndroidExecution=False), lambda r: r['activity'].update(actualGeckoExecution=False), lambda r: r['activity'].update(actualPublicWebsiteExecution=True), lambda r: r['activity'].update(actualAndroidWebViewExecution=True), lambda r: r['activity'].update(fingerprintProtectionVerified=True), lambda r: r['activity'].update(workerCoverageVerified=True), lambda r: r['activity'].update(serviceWorkerCoverageVerified=True), lambda r: r['activity']['checks'][0].update({'pass': 1}), lambda r: r['activity']['checks'].append(copy.deepcopy(r['activity']['checks'][0])), lambda r: r['activity']['checks'].pop(),
            lambda r: r['systemTimeZone'].update(source='page-js'), lambda r: r['systemTimeZone'].update(januaryOffsetMinutes=True), lambda r: r['systemTimeZone'].update(julyOffsetMinutes=15), lambda r: r['systemTimeZone'].update(zoneId='../UTC'),
        ])

    def test_raw_first_inline_clock_identity_and_native_tls_must_match(self):
        self.reject_changes([
            lambda r: r['activity']['samples'].pop(), lambda r: r['activity']['samples'].reverse(),
            lambda r: r['activity']['samples'][1]['page'].update(schema=True), lambda r: r['activity']['samples'][1]['page'].update(schema=2), lambda r: r['activity']['samples'][1]['page'].pop('schema'), lambda r: r['activity']['samples'][1]['page'].update(firstInline=False), lambda r: r['activity']['samples'][1]['page'].update(secure=False), lambda r: r['activity']['samples'][1]['page'].update(sourceCommit='d'*40), lambda r: r['activity']['samples'][1]['page'].update(runNonce='d'*32), lambda r: r['activity']['samples'][1]['page'].update(markerComplete=False), lambda r: r['activity']['samples'][1]['page'].update(networkAllowed=False),
            lambda r: r['activity']['samples'][1]['page']['nativeTimeZone']['july'].update(offsetMinutes=300), lambda r: r['activity']['samples'][1]['page']['nativeTimeZone']['january'].update(hour=8), lambda r: r['activity']['samples'][3]['page']['nativeTimeZone']['january'].update(minute=0), lambda r: r['activity']['samples'][3]['page']['nativeTimeZone']['july'].update(offsetMinutes=345), lambda r: r['activity']['samples'][3]['page']['nativeTimeZone']['july'].update(offsetMinutes=-345.0),
            lambda r: r['activity']['samples'][0]['page']['nativeTimeZone'].update(timeZone='Not/AZone'), lambda r: r['activity']['samples'][4]['page'].update(documentId=r['activity']['samples'][3]['page']['documentId']), lambda r: r['activity']['samples'][1]['frames'].pop(), lambda r: r['activity']['samples'][1]['frames'][0].update(firstInline=False), lambda r: r['activity']['samples'][1]['frames'][0].update(runNonce='d'*32),
            lambda r: r['activity']['samples'][0].update(url='https://127.0.0.1/env-policy?phase=gecko-system-mobile'), lambda r: r['activity']['samples'][0].update(url='http://fp-a.pocketchat.test/env-policy?phase=gecko-system-mobile'), lambda r: r['activity']['samples'][0].update(url='https://fp-a.pocketchat.test/env-policy?phase=gecko-system-mobile&phase=gecko-system-mobile'),
            lambda r: r['activity']['samples'][1]['security'].update(isException=True), lambda r: r['activity']['samples'][1]['security'].update(leafDerSha256='d'*64), lambda r: r['activity']['samples'][1]['security'].update(host='localhost'), lambda r: r['activity']['samples'][1]['security'].update(enterpriseRootsReadback=False),
        ])

    def test_full_sidecar_and_native_policy_are_bound_to_exact_current_context(self):
        changes = []
        for key, bad in [('sessionId', 'wrong-session'), ('sessionEpoch', 'wrong-epoch'), ('contextId', '999'), ('desiredRevision', True), ('desiredZone', 'Asia/Tokyo'), ('desktop', True)]:
            changes.append(lambda r, key=key, bad=bad: r['activity']['samples'][3]['native'].update({key: bad}))
        for key, bad in [('schema', True), ('desiredRevision', 99), ('processNonce', 'old'), ('requestToken', 'old'), ('nativeSettingReadback', False), ('pageObservationVerified', True), ('workerCoverageVerified', True), ('recordedAt', False)]:
            changes.append(lambda r, key=key, bad=bad: r['activity']['samples'][3]['native']['receipt'].update({key: bad}))
        for key, bad in [('requestToken', 'd'*64), ('sessionId', 'different'), ('contextId', '999'), ('status', 'read'), ('requestedZoneId', ''), ('nativeZoneId', 'UTC'), ('scope', 'all-workers'), ('workerCoverageVerified', True), ('extra', 'forged')]:
            changes.append(lambda r, key=key, bad=bad: r['activity']['samples'][3]['native']['receipt']['nativeReceipt'].update({key: bad}))
        for key, bad in [('state', 'saved'), ('nativeSettingReadback', False), ('currentSessionPrepared', False), ('desiredZone', 'Asia/Tokyo'), ('desiredRevision', 1), ('appliedScope', ''), ('pageObservationVerified', True), ('issue', 'old receipt')]:
            changes.append(lambda r, key=key, bad=bad: r['activity']['samples'][3]['native']['timeZonePolicy'].update({key: bad}))
        for key, bad in [('installed', False), ('nativeReadback', False), ('userAgent', DESKTOP), ('scope', 'private-admission-unchanged'), ('revision', True), ('sharedWorkerWireVerified', True)]:
            changes.append(lambda r, key=key, bad=bad: r['activity']['samples'][3]['native']['headerPolicy'].update({key: bad}))
        for key, bad in [('schema', True), ('status', 'applied'), ('sessionId', 'old-session'), ('contextId', '999'), ('nativeZoneId', 'Asia/Tokyo'), ('scope', 'all-workers'), ('workerCoverageVerified', True), ('extra', 'forged')]:
            changes.append(lambda r, key=key, bad=bad: r['activity']['samples'][3]['native']['freshReadback'].update({key: bad}))
        changes.extend([lambda r: r['activity']['samples'][3]['native'].update(contextCurrent=False), lambda r: r['activity']['samples'][3]['native']['freshReadback'].update(requestToken=r['activity']['samples'][3]['native']['receipt']['requestToken']), lambda r: r['activity']['samples'][3]['native']['receipt'].update(extra='forged'), lambda r: r['activity']['samples'][3]['native']['receipt']['binding'].update(sessionEpoch='old'), lambda r: r['activity']['samples'][3]['native']['receipt']['binding'].update(engineVersion='different SDK'), lambda r: r['activity']['samples'][3]['native']['receipt']['identity'].update(generation=2)])
        self.reject_changes(changes)

    def test_every_required_worker_execution_and_actual_wire_ua_is_checked(self):
        changes = []
        for name in gate.WORKER_ROLES:
            for key, bad in [('created', False), ('executed', False), ('networkAllowed', False), ('available', False), ('sourceRole', 'wrong-worker'), ('workerCoverageVerified', True)]:
                changes.append(lambda r, name=name, key=key, bad=bad: r['activity']['samples'][1]['workers']['cases'][name].update({key: bad}))
        changes.extend([lambda r: r['activity']['samples'][0]['workers'].update(complete=False), lambda r: r['activity']['samples'][1]['workers']['cases'].pop('module'), lambda r: r['activity']['samples'][1]['workers']['cases']['blob']['nativeTimeZone']['january'].update(hour=True)])
        self.reject_changes(changes)
        for name, realm in gate.WORKER_ROLES.items():
            report = self.document()
            page = report['activity']['samples'][1]['page']
            for request in report['activity']['fixture']['requests']:
                if request['documentId'] == page['documentId'] and request['realm'] == realm:
                    request['user-agent'] = 'wrong-wire-UA'
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.validate(report)
        # The JS navigator value is an honest independent observation. HTTP UA
        # alignment does not assert that the implementation rewrites Worker JS.
        report = self.document()
        report['activity']['samples'][1]['workers']['cases']['classic']['nativeUserAgent'] = 'independent-worker-JS-UA'
        self.assertIn(dict(label='new-york', role='classic'), self.validate(report)['_derivedJavascriptUaDifferences'])

    def test_one_extra_bad_wire_row_cannot_hide_behind_an_existing_good_request(self):
        for changes in ({'user-agent': 'wrong-wire-UA'}, {'authorization': 'must-not-export'}, {'origin': 'https://public.example'}, {'tls': False}, {'phase': 'gecko-stale'}, {'documentId': '00000000-0000-0000-0000-999999999999'}, {'path': '/module.js', 'realm': 'shared-worker'}):
            report = self.document()
            row = copy.deepcopy(report['activity']['fixture']['requests'][1])
            row.update(changes)
            report['activity']['fixture']['requests'].append(row)
            report['activity']['fixture']['accepted'] += 1
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.validate(report)

    def test_missing_scripts_and_unavailable_shared_service_cannot_claim_success(self):
        for path in ('/module.js', '/shared.js', '/service.js', '/sw-cached'):
            report = self.document()
            fixture = report['activity']['fixture']
            fixture['requests'] = [row for row in fixture['requests'] if row['path'] != path]
            fixture['accepted'] = len(fixture['requests'])
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.validate(report)
        for role in ('shared', 'service'):
            report = self.document(shared=False, service=False)
            report['activity']['samples'][0]['workers']['cases'][role]['executed'] = True
            with self.subTest(role=role), self.assertRaises(ValueError):
                self.validate(report)

    def test_lifecycle_stale_ticket_popup_and_rfp_proofs_are_cross_bound(self):
        self.reject_changes([
            lambda r: r['activity']['staleTicketProof'].update(actualStoreRecordAttempt=False), lambda r: r['activity']['staleTicketProof'].update(oldRecordRejected=False), lambda r: r['activity']['staleTicketProof'].update(oldReceiptEmpty=False), lambda r: r['activity']['staleTicketProof'].update(oldToken='d'*64), lambda r: r['activity']['staleTicketProof'].update(newContextId='999'),
            lambda r: r['activity']['lifecycle']['reload'].update(afterDocumentId=r['activity']['lifecycle']['reload']['beforeDocumentId']), lambda r: r['activity']['lifecycle']['reopen'].update(afterContextId=r['activity']['lifecycle']['reopen']['beforeContextId']), lambda r: r['activity']['lifecycle']['restore'].update(sdkCheckpointAvailable=False), lambda r: r['activity']['lifecycle']['restore'].update(formValueRestored=False), lambda r: r['activity']['lifecycle']['coop'].update(responseHeaderObserved=False), lambda r: r['activity']['lifecycle']['coop'].update(oldContextId='999'),
            lambda r: r['activity']['popupProof'].update(actualNavigationDelegate=False), lambda r: r['activity']['popupProof'].update(sessionCountAfter=2), lambda r: r['activity']['popupProof'].update(oldNativeSessionUnchanged=False),
            lambda r: r['activity']['rfpConflictProof'].update(actualUiAttempt=False), lambda r: r['activity']['rfpConflictProof'].update(levelAfter=1), lambda r: r['activity']['rfpConflictProof'].update(rfpConfirmed=False), lambda r: r['activity']['rfpConflictProof'].update(desiredRevisionAfter=5), lambda r: r['activity']['rfpConflictProof'].update(savedZoneAfter='Asia/Kathmandu'),
        ])

    def test_old_revision_proof_requires_both_actual_rejections_and_current_receipt(self):
        changes = []
        for key in ('actualStoreRecordAttempt', 'actualStoreReceiptAttempt', 'currentReceiptRead',
                    'oldRecordRejected', 'oldReceiptRejected', 'currentReceiptPreserved'):
            changes.append(lambda r, key=key: r['activity']['staleRevisionProof'].update({key: False}))
        changes.extend([
            lambda r: r['activity'].pop('staleRevisionProof'),
            lambda r: r['activity']['staleRevisionProof'].update(oldRevision=3),
            lambda r: r['activity']['staleRevisionProof'].update(newRevision=2),
            lambda r: r['activity']['staleRevisionProof'].update(oldRevision=True),
            lambda r: r['activity']['staleRevisionProof'].update(oldToken='d' * 64),
            lambda r: r['activity']['staleRevisionProof'].update(newContextId='999'),
        ])
        self.reject_changes(changes)

    def test_coop_current_context_and_actual_header_trace_cannot_be_assumed(self):
        def without_header(report):
            for row in report['activity']['fixture']['requests']:
                row.pop('responseCoop', None)
        self.reject_changes([
            without_header,
            lambda r: r['activity']['lifecycle']['coop'].update(contextChanged=False),
            lambda r: r['activity']['lifecycle']['coop'].update(contextChanged=1),
            lambda r: r['activity']['lifecycle']['restore'].update(actualRestoreRequests=0),
            lambda r: r['activity']['lifecycle']['restore'].update(actualRestoreRequests=True),
            lambda r: r['activity']['samples'][2]['native']['freshReadback'].update(contextId=r['activity']['samples'][1]['native']['contextId']),
            lambda r: r['activity']['samples'][2]['native']['receipt']['binding'].update(contextId=r['activity']['samples'][1]['native']['contextId']),
            lambda r: r['activity']['samples'][2]['page'].update(nativeTimeZone=raw_clock('UTC')),
            lambda r: r['activity']['fixture']['requests'][0].update(responseCoop='same-origin'),
        ])
        # COOP does not promise that a particular engine changes its top BC id.
        # A retained BC still needs a fresh private read and correct first-inline
        # clock; do not turn it into a claim that replacement was exercised.
        value = self.document()
        before, after = value['activity']['samples'][1:3]
        native, old = after['native'], before['native']
        native.update(sessionId=old['sessionId'], sessionEpoch=old['sessionEpoch'], contextId=old['contextId'])
        for binding in (native['receipt']['binding'],):
            binding.update(sessionId=old['sessionId'], sessionEpoch=old['sessionEpoch'], contextId=old['contextId'])
        for ack in (native['receipt']['nativeReceipt'], native['freshReadback']):
            ack.update(sessionId=old['sessionId'], contextId=old['contextId'])
        value['activity']['lifecycle']['coop'].update(newContextId=old['contextId'], contextChanged=False)
        self.validate(value)

    def test_host_native_leaf_and_source_hashes_cannot_be_replaced(self):
        self.reject_changes([
            lambda r: r['hostTls'].update(privateMaterialExported=True), lambda r: r['hostTls'].update(privateMaterialRemoved=False), lambda r: r['hostTls'].update(certificateExceptionUsed=True), lambda r: r['hostTls'].update(reverseRemoved=False), lambda r: r['hostTls'].update(hostnameVerified=['localhost']), lambda r: r['hostTls']['binding'].update(runNonce='d'*32), lambda r: r['hostTls']['trustInstallation'].update(evidenceShellUid=0), lambda r: r['hostTls']['trustInstallation'].update(installedPublicCaBytesMatch=False),
            lambda r: r['activity']['fixture'].update(upstreamConnections=1), lambda r: r['activity']['fixture'].update(upstreamConnections=False), lambda r: r['activity']['fixture'].update(forwardingImplemented=True), lambda r: r['activity']['fixture'].update(accepted=0), lambda r: r['activity']['fixture'].update(leafDerSha256='d'*64),
            lambda r: r['sourceFiles'].clear(), lambda r: r['sourceFiles'].update({'../escape': SHA}), lambda r: r['sourceFiles'].update({'/absolute': SHA}), lambda r: r['sourceFiles'].update({next(iter(r['sourceFiles'])): 'd'*64}),
        ])

    def test_transition_and_rfp_reset_are_full_attributed_native_observations(self):
        self.reject_changes([
            lambda r: r['activity']['transitionSamples'].pop(), lambda r: r['activity']['transitionSamples'].reverse(), lambda r: r['activity']['transitionSamples'][0]['page']['nativeTimeZone']['january'].update(minute=0), lambda r: r['activity']['transitionSamples'][1]['page'].update(markerComplete=False),
            lambda r: r['activity']['rfpResetBaseline']['page'].update(nativeTimeZone=raw_clock('Asia/Kathmandu')), lambda r: r['activity']['rfpResetBaseline']['native'].update(contextCurrent=False), lambda r: r['activity']['rfpResetBaseline']['native']['freshReadback'].update(requestToken=r['activity']['samples'][0]['native']['freshReadback']['requestToken']), lambda r: r['activity']['rfpFinalObservation']['native']['freshReadback'].update(nativeZoneId='America/New_York'), lambda r: r['activity']['rfpFinalObservation']['page'].update(networkAllowed=False),
        ])
        # A different independently read RFP UA is allowed, and must be applied
        # to every attributed wire row. It is not forced to the earlier mobile
        # JS value or treated as a complete Worker identity guarantee.
        report = self.document()
        final = report['activity']['rfpFinalObservation']
        final['native']['userAgent'] = 'actual-independent-RFP-native-UA'
        final['native']['headerPolicy']['userAgent'] = final['native']['userAgent']
        documents = {raw['documentId'] for raw in [final['page']] + final['frames']}
        for row in report['activity']['fixture']['requests']:
            if row['documentId'] in documents:
                row['user-agent'] = final['native']['userAgent']
        # The initial request has no document UUID. Add the separate actual
        # native-UA request rows that this later RFP document must have made.
        for raw in [final['page']] + final['frames']:
            path, realm = ('/env-policy', 'document') if raw is final['page'] else ('/env-frame', 'frame')
            report['activity']['fixture']['requests'].append(dict(origin=raw['origin'], path=path, realm=realm, phase=raw['phase'], documentId='', tls=True, method='GET', **{'user-agent': final['native']['userAgent']}))
        report['activity']['fixture']['accepted'] = len(report['activity']['fixture']['requests'])
        self.validate(report)

        changed_revision = self.document()
        for snapshot in (changed_revision['activity']['rfpResetBaseline'], changed_revision['activity']['rfpFinalObservation']):
            native = snapshot['native']
            native['desiredRevision'] = native['receipt']['desiredRevision'] = native['timeZonePolicy']['desiredRevision'] = 5
        changed_revision['activity']['rfpConflictProof'].update(desiredRevisionBefore=5, desiredRevisionAfter=5)
        with self.assertRaises(ValueError):
            self.validate(changed_revision)

    def test_full_file_verifier_binds_independent_apk_sdk_reference(self):
        with tempfile.TemporaryDirectory() as folder:
            report = self.document()
            path = Path(folder, gate.REPORT_NAME)
            path.write_text(json.dumps(report))
            result = gate.verify_gecko_environment_policy_evidence(folder, SOURCE, copy.deepcopy(report['expectedBuildIdentity']), lambda source, path: SOURCE_BYTES)
            self.assertEqual(result['sampleCount'], 9)
            self.assertEqual(result['reportSha256'], hashlib.sha256(path.read_bytes()).hexdigest())
            self.assertFalse(result['workerCoverageVerified'])
            self.assertEqual(len(result['workerTimeZoneDifferences']), 20)
            self.assertNotIn('receipt', result)
            for location, key, bad in [('wrapper', 'apkSha256', 'd'*63+'a'), ('activity', 'versionCode', 999), ('sdk', 'runAttempt', 2)]:
                value = self.document()
                expected = copy.deepcopy(value['expectedBuildIdentity'])
                selected = value['expectedBuildIdentity'] if location == 'wrapper' else value['activity']['buildIdentity'] if location == 'activity' else value['activity']['buildIdentity']['sdkBuildIdentity']
                selected[key] = bad
                path.write_text(json.dumps(value))
                with self.subTest(location=location), self.assertRaises(ValueError):
                    gate.verify_gecko_environment_policy_evidence(folder, SOURCE, expected, lambda source, path: SOURCE_BYTES)

    def test_duplicate_json_nonfinite_missing_and_oversized_reports_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(FileNotFoundError):
                gate.verify_gecko_environment_policy_evidence(folder, SOURCE, {})
            for raw in (b'{"status":"passed","status":"passed"}', b'{"number":NaN}', b'{"number":Infinity}', b'[]', b' ' * (4*1024*1024+1)):
                Path(folder, gate.REPORT_NAME).write_bytes(raw)
                with self.subTest(raw=raw[:50]), self.assertRaises(ValueError):
                    gate.verify_gecko_environment_policy_evidence(folder, SOURCE, {})


if __name__ == '__main__':
    unittest.main(verbosity=2)
