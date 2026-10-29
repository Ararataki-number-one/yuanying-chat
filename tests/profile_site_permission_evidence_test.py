"""Synthetic controls for the additional SDK-only evidence contract; no device run."""
import copy
import hashlib
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('site_permission_evidence', ROOT / 'tools/gecko/site_permission_evidence.py')
CONTRACT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CONTRACT)
NONCE = '3' * 32
ORIGIN = CONTRACT.ORIGIN


def data():
    requests, gestures = [], []
    for stage, before, result, start, end in [('initial', 'default', 'default', 0, 1), ('after-deny', 'denied', 'denied', 1, 1), ('after-default', 'default', 'default', 1, 2)]:
        requests.append(dict(realm='page-main-world', nonce=NONCE, stage=stage, url=ORIGIN + '/pool', secureContext=True,
                             isTrusted=True, userActivation=True, requestCalled=True, done=True, before=before, result=result,
                             after=result, callbacksBefore=start, callbacksAfter=end))
        bounds = dict(nonce=NONCE, stage=stage, css=dict(x=100, y=300, width=400, height=800), native=dict(x=0, y=30, width=800, height=1600))
        gestures.append(dict(nonce=NONCE, stage=stage, command=CONTRACT.permission_tap_command(bounds, CONTRACT.STAGES[:len(gestures)]), bounds=bounds, oneAttempt=True))
    callbacks = [dict(sequence=i + 1, type=1, role='content-permission-request', value=0, valueSemantics='native-request-unmapped', origin=ORIGIN, privateMode=False, contextMatches=True, thirdPartyAbsent=False, sameSession=True, thirdPartyOriginKind='controlled-origin', thirdPartyOriginLength=len(ORIGIN), thirdPartyOriginSha256=hashlib.sha256(ORIGIN.encode()).hexdigest(), thirdPartyOrigin=ORIGIN) for i in range(2)]
    snapshots = [dict(role='stored-permission-record', valueSemantics='stored-permission-value' if present else 'absent-record-sentinel', stage=stage, attempt=1, present=present, value=value, type=1, origin=ORIGIN, contextMatches=True, privateMode=False, thirdPartyAbsent=True)
                 for stage, present, value in [('baseline-default', False, 0), ('deny', True, 2), ('default', False, 0)]]
    return dict(schema=2, status='passed', scope='controlled-gecko-sdk-only', origin=ORIGIN, productionUiAdapter=False,
                actualAndroidExecution=True, actualGeckoExecution=True, physicalPhoneAcceptance=False, publicNetworkTraffic=False,
                testOnlyCertificateException=True, checks=[dict(name='synthetic contract check ' + str(i), **{'pass': True}) for i in range(12)],
                preflight=dict(realm='page-main-world', nonce=NONCE, url=ORIGIN + '/pool', secureContext=True, notificationApi=True),
                callbacks=callbacks, snapshots=snapshots, requests=requests,
                mutations=[dict(stage=stage, value=value, originalNativeObject=True, source=source, sourceValue=0 if stage == 'deny' else 2, sourceValueSemantics='native-request-unmapped' if stage == 'deny' else 'stored-permission-value') for stage, value, source in
                           [('deny', 2, 'content-permission-callback'), ('default', 3, 'getPermissions-readback')]],
                sameDocument=True, draftPreserved=True, sendCount=0), gestures


class SitePermissionEvidenceTest(unittest.TestCase):
    def reject(self, mutate):
        report, gestures = data()
        mutate(report, gestures)
        with self.assertRaises(ValueError):
            CONTRACT.verify_site_permission_evidence(report, gestures)

    def test_passed_contract_is_sdk_only_and_not_phone_or_ui_acceptance(self):
        report, gestures = data()
        result = CONTRACT.verify_site_permission_evidence(report, gestures)
        self.assertEqual(result['status'], 'passed')
        self.assertTrue(result['actualNativePermissionChangeVerified'])
        self.assertFalse(result['productionUiAdapter'])
        self.assertFalse(result['physicalPhoneAcceptance'])
        report['snapshots'][-1].update(present=True, value=3, valueSemantics='stored-permission-value')
        self.assertEqual(CONTRACT.verify_site_permission_evidence(report, gestures)['status'], 'passed')

    def test_all_acceptance_flags_and_origin_are_strict(self):
        mutations = [lambda r, g: r.update(schema=True), lambda r, g: r.update(scope='production-ui'),
                     lambda r, g: r.update(origin='https://other.test'), lambda r, g: r['checks'][0].update({'pass': False})]
        for key in ['actualAndroidExecution', 'actualGeckoExecution', 'testOnlyCertificateException']:
            mutations.append(lambda r, g, key=key: r.update({key: 1}))
        for key in ['productionUiAdapter', 'physicalPhoneAcceptance', 'publicNetworkTraffic']:
            mutations.append(lambda r, g, key=key: r.update({key: True}))
        for mutation in mutations:
            with self.subTest(mutation=mutations.index(mutation)):
                self.reject(mutation)

    def test_each_page_request_must_be_activated_and_actual_main_world(self):
        for index in range(3):
            for key, bad in [('realm', 'extension-world'), ('url', 'http://127.0.0.1/pool'), ('nonce', '4' * 32),
                             ('isTrusted', False), ('userActivation', False), ('requestCalled', False), ('done', False),
                             ('secureContext', False), ('result', 'granted'), ('error', 'NotAllowedError')]:
                with self.subTest(index=index, key=key):
                    self.reject(lambda r, g, index=index, key=key, bad=bad: r['requests'][index].update({key: bad}))

    def test_actual_one_attempt_gesture_commands_and_mapping_are_bound(self):
        for mutation in [lambda r, g: g[0].update(oneAttempt=False), lambda r, g: g.append(copy.deepcopy(g[0])),
                         lambda r, g: g[1].update(nonce='4' * 32), lambda r, g: g[0]['command'].__setitem__(-1, '999'),
                         lambda r, g: g[0]['bounds']['css'].update(width=0), lambda r, g: g[0]['bounds']['css'].update(x=999),
                         lambda r, g: g[0]['bounds']['native'].update(height=800), lambda r, g: g[0]['bounds']['css'].update(x=float('nan'))]:
            with self.subTest(mutation=str(mutation)):
                self.reject(mutation)
        with self.assertRaises(ValueError):
            CONTRACT.permission_tap_command(data()[1][0]['bounds'], ['initial'])

    def test_native_origin_object_namespace_and_callback_counts_are_required(self):
        for key, bad in [('sequence', True), ('type', True), ('value', -1), ('origin', 'https://other.test'), ('privateMode', True),
                         ('contextMatches', False), ('thirdPartyAbsent', True), ('sameSession', False)]:
            self.reject(lambda r, g, key=key, bad=bad: r['callbacks'][0].update({key: bad}))
        for mutation in [lambda r, g: r.update(callbacks=[]), lambda r, g: r['requests'][1].update(callbacksAfter=2),
                         lambda r, g: r['requests'][2].update(callbacksAfter=1), lambda r, g: r['requests'][0].update(callbacksBefore=True)]:
            self.reject(mutation)

    def test_request_zero_is_explicitly_unmapped_and_never_a_stored_value(self):
        report, gestures = data()
        self.assertEqual(CONTRACT.verify_site_permission_evidence(report, gestures)['status'], 'passed')
        for value in (1, 2, 3):
            known, taps = data()
            known['callbacks'][0].update(value=value, valueSemantics='native-request-capability')
            known['mutations'][0].update(sourceValue=value, sourceValueSemantics='native-request-capability')
            self.assertEqual(CONTRACT.verify_site_permission_evidence(known, taps)['status'], 'passed')
        for mutate in [lambda r, g: r.update(schema=1),
                       lambda r, g: r['callbacks'][0].update(role='stored-permission-record'),
                       lambda r, g: r['callbacks'][0].update(valueSemantics='stored-permission-value'),
                       lambda r, g: r['callbacks'][0].update(value=3),
                       lambda r, g: r['callbacks'][0].update(value=4),
                       lambda r, g: r['snapshots'][1].update(value=0),
                       lambda r, g: r['snapshots'][1].update(role='content-permission-request'),
                       lambda r, g: r['snapshots'][1].update(valueSemantics='native-request-unmapped'),
                       lambda r, g: r['mutations'][0].update(sourceValue=3),
                       lambda r, g: r['mutations'][0].update(sourceValue=False),
                       lambda r, g: r['mutations'][0].update(sourceValue=0.0),
                       lambda r, g: r['mutations'][1].update(sourceValue=2.0),
                       lambda r, g: r['mutations'][0].update(sourceValueSemantics='stored-permission-value')]:
            self.reject(mutate)

    def test_request_principal_is_exact_controlled_origin_with_bounded_diagnostics(self):
        for key, bad in [('thirdPartyOriginKind', 'null'), ('thirdPartyOriginKind', 'empty'),
                         ('thirdPartyOriginKind', 'other'), ('thirdPartyOriginKind', 'oversize'),
                         ('thirdPartyOriginLength', 0), ('thirdPartyOriginLength', True),
                         ('thirdPartyOriginLength', 4096), ('thirdPartyOriginSha256', '0' * 64),
                         ('thirdPartyOrigin', None), ('thirdPartyOrigin', ''),
                         ('thirdPartyOrigin', ORIGIN + '/path'), ('thirdPartyOrigin', 'https://other.test')]:
            with self.subTest(key=key, bad=bad):
                self.reject(lambda r, g, key=key, bad=bad: r['callbacks'][0].update({key: bad}))
        for mutate in [lambda r, g: r['snapshots'][1].update(thirdPartyAbsent=False),
                       lambda r, g: r['callbacks'][0].update(contextMatches=False),
                       lambda r, g: r['callbacks'][0].update(privateMode=True),
                       lambda r, g: r['callbacks'][0].update(sameSession=False)]:
            self.reject(mutate)

    def test_native_readback_and_exactly_two_reduce_only_writes(self):
        for mutation in [lambda r, g: r['snapshots'][1].update(present=False, value=0), lambda r, g: r['snapshots'][-1].update(present=True, value=1),
                         lambda r, g: r['snapshots'][0].update(present=True, value=1), lambda r, g: r['snapshots'][1].update(contextMatches=False),
                         lambda r, g: r['snapshots'][1].update(privateMode=True), lambda r, g: r['snapshots'][1].update(attempt=4),
                         lambda r, g: r['mutations'][0].update(value=1), lambda r, g: r['mutations'][0].update(originalNativeObject=1),
                         lambda r, g: r['mutations'][1].update(source='fabricated-json'), lambda r, g: r['mutations'].append(copy.deepcopy(r['mutations'][0])),
                         lambda r, g: r.update(sameDocument=False), lambda r, g: r.update(draftPreserved=False), lambda r, g: r.update(sendCount=True)]:
            self.reject(mutation)

    def test_supported_uncovered_conditions_cannot_claim_a_native_change(self):
        for reason in ['secure-context-unavailable', 'notification-api-unavailable', 'content-callback-not-observed']:
            report, gestures = data()
            report.update(status='uncovered', reason=reason, callbacks=[], mutations=[])
            report['snapshots'] = report['snapshots'][:1] if reason == 'content-callback-not-observed' else []
            report['requests'] = report['requests'][:1] if reason == 'content-callback-not-observed' else []
            gestures = gestures[:len(report['requests'])]
            if report['requests']:
                report['requests'][0]['callbacksAfter'] = 0
            else:
                report['preflight']['secureContext' if reason == 'secure-context-unavailable' else 'notificationApi'] = False
            result = CONTRACT.verify_site_permission_evidence(report, gestures)
            self.assertEqual(result['status'], 'uncovered')
            self.assertFalse(result['actualNativePermissionChangeVerified'])
            report['mutations'] = data()[0]['mutations']
            with self.assertRaises(ValueError):
                CONTRACT.verify_site_permission_evidence(report, gestures)
        self.reject(lambda r, g: r.update(status='uncovered', reason='timeout'))
        self.reject(lambda r, g: r.update(status='failed'))


if __name__ == '__main__':
    unittest.main()
