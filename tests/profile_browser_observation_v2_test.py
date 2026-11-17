"""Synthetic parser rejection controls; never device or production result evidence."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/gecko'))
from browser_observation_contract_v2 import (
    ANDROID_CHECKS, NOTIFICATION_CHECKS, verify_browser_observation,
    verify_browser_notifications, verify_lifecycle_host, INTERACTION_HOST_CHECKS, verify_interaction_host)


def android_report():
    stats = dict(derivedBuilt=12, messageListsBuilt=2)
    def metric(variant, action, size):
        return dict(variant=variant, action=action, samples=12,
                    bridgeResponseBytes=size, domReadChars=size,
                    observationBefore=stats.copy(), observationAfter=stats.copy())
    return dict(browserObservationContract=2, status='passed', actualAndroidExecution=True,
                actualGeckoExecution=True, actualAndroidTouchExecution=True,
                actualGeckoBrowserLifecycleExecution=True, actualAppearanceRoundtrip=True,
                actualInputImeSettled=True, actualSingleInputBurst=True,
                checkCount=len(ANDROID_CHECKS), checks=[],
                measurements=[metric('baseline', 'historical-poll', 100000), metric('current', 'web-inspect', 1000)])


def checked_report():
    result = android_report()
    result['checks'] = [{'name': n, 'pass': True} for n in sorted(ANDROID_CHECKS)]
    return result


def notification_report():
    def visible(count):
        return dict(known=True, foreground=count > 0, actualActivityStartedCount=count,
                    visibilitySource='activity-start-stop', processes=[
                        dict(process='local.pocketchat.test', pid=100, known=True, visible=False, actualActivityStartedCount=0),
                        dict(process='local.pocketchat.test:profile7', pid=101, known=True, visible=count > 0, actualActivityStartedCount=count)])
    running = dict(alive=True, generation='first', slot=7, pid=103, servicePid=102, state='running')
    return dict(notificationContract=2, status='passed', actualAndroidExecution=True,
                checks=[{'name': n, 'pass': True} for n in sorted(NOTIFICATION_CHECKS)], checkCount=len(NOTIFICATION_CHECKS),
                replyRetirementEvidence=dict(legacyPolicyMigratedOff=True, legacyPendingArchived=True, serviceStopped=True,
                                             requestedService='local.pocketchat.test/.Profile7Service'),
                proxyEvidence=dict(controllerReady=True, loopbackListenersConfigured=True, denyAllConfigured=True,
                                   fixtureRemoteRequests=False, started=running.copy(), ready=running.copy(),
                                   stopped=dict(alive=False, generation='stopped', pid=0)),
                foregroundEvidence=visible(1), homeEvidence=visible(0))


class BrowserObservationV2Tests(unittest.TestCase):
    def rejected(self, mutation, builder=checked_report, verifier=verify_browser_observation):
        value = builder(); mutation(value)
        with self.assertRaises((AssertionError, KeyError, StopIteration)):
            verifier(value)

    def test_current_browser_contract_has_explicit_distinct_workloads(self):
        result = verify_browser_observation(checked_report())
        self.assertEqual((result['historicalWorkload'], result['currentWorkload']), ('poll', 'web-inspect'))
        self.assertTrue(result['replyDetectionRetired'])

    def test_rejects_old_or_missing_contract(self):
        self.rejected(lambda v: v.pop('browserObservationContract'))
        self.rejected(lambda v: v.update(browserObservationContract=1))

    def test_requires_actual_browser_lifecycle_and_original_native_input(self):
        for key in ('actualGeckoBrowserLifecycleExecution', 'actualAndroidTouchExecution', 'actualSingleInputBurst', 'actualInputImeSettled'):
            with self.subTest(key=key): self.rejected(lambda v: v.update({key: False}))

    def test_old_completion_claim_cannot_replace_new_absence_check(self):
        self.rejected(lambda v: v['checks'][0].update(name='Production stable lightweight samples finish and persist the actual reply task'))

    def test_missing_and_duplicate_checks_are_rejected(self):
        self.rejected(lambda v: v['checks'].pop())
        self.rejected(lambda v: v['checks'].__setitem__(1, v['checks'][0]))

    def test_current_workload_cannot_be_silently_labelled_poll(self):
        self.rejected(lambda v: v['measurements'][1].update(action='poll'))

    def test_original_performance_ratio_and_cache_oracles_remain_required(self):
        self.rejected(lambda v: v['measurements'][1].update(bridgeResponseBytes=6000))
        self.rejected(lambda v: v['measurements'][1].update(domReadChars=6000))
        self.rejected(lambda v: v['measurements'][1]['observationAfter'].update(derivedBuilt=13))

    def test_pure_browser_notification_contract(self):
        result = verify_browser_notifications(notification_report())
        self.assertTrue(result['actualFileNotifications'] and result['actualProxyForeground'])

    def test_legacy_policy_or_service_cannot_remain_live(self):
        for key in ('legacyPolicyMigratedOff', 'legacyPendingArchived', 'serviceStopped'):
            with self.subTest(key=key):
                self.rejected(lambda v: v['replyRetirementEvidence'].update({key: False}), notification_report, verify_browser_notifications)

    def test_proxy_and_real_home_evidence_are_mandatory(self):
        self.rejected(lambda v: v['proxyEvidence']['ready'].update(alive=False), notification_report, verify_browser_notifications)
        self.rejected(lambda v: v['homeEvidence'].update(foreground=True), notification_report, verify_browser_notifications)
        self.rejected(lambda v: v['homeEvidence'].update(actualActivityStartedCount=1), notification_report, verify_browser_notifications)

    def test_file_route_and_readable_file_checks_cannot_be_omitted(self):
        for name in ('Independent environments retain distinct file notification routes', 'The notified local file is fully published and readable'):
            with self.subTest(name=name):
                self.rejected(lambda v: v.update(checks=[row for row in v['checks'] if row['name'] != name]), notification_report, verify_browser_notifications)

    def test_old_binding_host_report_cannot_qualify_current_lifecycle(self):
        with self.assertRaises(AssertionError): verify_lifecycle_host(dict(contract='reply-binding-v1', passed=100, total=100))


    def test_interaction_contract_rejects_automatic_result_work(self):
        cases = ('unchanged', 'later-user', 'bound-user-removed', 'earlier-history-user', 'other-route', 'detached-body', 'body-changed', 'sidebar-class')
        value = dict(contract='browser-result-removal-v1', passed=len(INTERACTION_HOST_CHECKS), total=len(INTERACTION_HOST_CHECKS),
                     checks=[{'name': name, 'pass': True} for name in sorted(INTERACTION_HOST_CHECKS)],
                     retiredSemantics=['queued reply prewarm', 'native completion during interaction', 'send intent snapshots'],
                     retiredResults=dict(contract='browser-result-removal-v1', actualAndroidExecution=False, rows=[
                         dict(kind=kind, noResultWork=True, zeroSend=True, zeroFetch=True, cookieAndDraftPreserved=True,
                              snapshotUrl='https://chatgpt.com/c/'+('other' if kind == 'other-route' else 'interaction-fixture')) for kind in cases]))
        self.assertEqual(verify_interaction_host(value), 42)
        value['retiredResults']['rows'][1]['noResultWork'] = False
        with self.assertRaises(AssertionError): verify_interaction_host(value)


if __name__ == '__main__': unittest.main()
