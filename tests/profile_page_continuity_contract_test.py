"""Counterfeit continuity metadata controls only; never Android execution evidence."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('page_continuity_contract', ROOT / 'tools/gecko/page_continuity_contract.py')
contract = importlib.util.module_from_spec(spec)
spec.loader.exec_module(contract)


def metadata():
    pending = json.dumps(dict(id='continuity-5', kind='web', engine='gecko',
                             expectedUrl='https://chatgpt.com/', confirmedUrl='https://chatgpt.com/',
                             prompt='controlled task', attempted=True), separators=(',', ':'))
    before = dict(url='about:blank', nativeUrl='about:blank', session=123,
                  visible=False, navigating=False, navigationFailed=True,
                  pageError='previous page observation', status='previous page observation',
                  manualAttention=False, networkReady=True, guardAllowed=True,
                  connecting=False, recoveryScheduled=False, recoveryToken=7,
                  recoveryAttempt=0, networkIssue='', connectionEpoch=2,
                  navigationEpoch=8, loads=0, stops=0, pending=pending, persistedPending=pending)
    after = dict(before, pageError=contract.PAGE_ERROR, status=contract.PAGE_ERROR, navigationEpoch=9)
    evidence = dict(before=before, after=after, requestedNavigationEpoch=9, uiScope=contract.UI_SCOPE)
    evidence.update({key: True for key in contract.EMPTY_CONDITIONS})
    report = dict(schema=1, status='passed', actualAndroidExecution=True, actualGeckoExecution=True,
                  checks=[dict(name=name, **{'pass': True}) for name in contract.CHECK_NAMES],
                  checkCount=13, emptyConditionInputs=evidence,
                  snapshots=[dict(phase='after-head-failure', session=123, connectionEpoch=2,
                                  document=dict(url='http://127.0.0.1:8765/browser-continuity?command=5'))])
    report.update({key: True for key in contract.FLAGS})
    return report


class PageContinuityContractTest(unittest.TestCase):
    def setUp(self):
        self.report = metadata()

    def reject(self, edit):
        value = copy.deepcopy(self.report)
        edit(value)
        with self.assertRaises(ValueError):
            contract.verify_page_continuity(value)

    def state_reject(self, stage, edit):
        self.reject(lambda value: edit(value['emptyConditionInputs'][stage]))

    def test_complete_metadata_preserves_original_13_and_eight_conditions(self):
        self.assertEqual(contract.verify_page_continuity(self.report), dict(checks=13, emptyConditions=8))

    def test_old_report_without_raw_empty_evidence_is_rejected(self):
        self.reject(lambda report: report.pop('emptyConditionInputs'))

    def test_failed_execution_cannot_hide_behind_passing_checks(self):
        self.reject(lambda report: report.update(status='failed'))
        self.reject(lambda report: report.update(error='fixture error'))

    def test_schema_and_count_must_be_exact_integers(self):
        for key in ('schema', 'checkCount'):
            for value in (True, False, 1.0, '13', None):
                with self.subTest(key=key, value=value):
                    self.reject(lambda report: report.update({key: value}))

    def test_original_flags_require_strict_true(self):
        for key in contract.FLAGS + ('actualAndroidExecution', 'actualGeckoExecution'):
            for value in (False, 1, 'true', None):
                with self.subTest(key=key, value=value):
                    self.reject(lambda report: report.update({key: value}))

    def test_every_original_check_is_required(self):
        for index in range(13):
            with self.subTest(index=index):
                self.reject(lambda report: report['checks'].pop(index))

    def test_original_check_names_order_and_results_are_preserved(self):
        self.reject(lambda report: report['checks'].reverse())
        for index in range(13):
            for mutation in ({'name': 'substituted'}, {'pass': False}, {'pass': 1}):
                with self.subTest(index=index, mutation=mutation):
                    self.reject(lambda report: report['checks'][index].update(mutation))

    def test_every_empty_condition_requires_strict_true(self):
        for key in contract.EMPTY_CONDITIONS:
            for value in (False, 1, 'true', None):
                with self.subTest(key=key, value=value):
                    self.reject(lambda report: report['emptyConditionInputs'].update({key: value}))

    def test_raw_states_are_both_required(self):
        for stage in ('before', 'after'):
            self.reject(lambda report: report['emptyConditionInputs'].pop(stage))

    def test_every_raw_boolean_has_boolean_type(self):
        for stage in ('before', 'after'):
            for key in contract.STATE_BOOLEANS:
                for value in (1, 'false', None):
                    with self.subTest(stage=stage, key=key, value=value):
                        self.state_reject(stage, lambda state: state.update({key: value}))

    def test_raw_numeric_values_cannot_be_booleans_floats_or_invalid_counters(self):
        for stage in ('before', 'after'):
            for key in contract.STATE_INTEGERS:
                for value in (True, 0.0, -1, 2**63, None):
                    with self.subTest(stage=stage, key=key, value=value):
                        self.state_reject(stage, lambda state: state.update({key: value}))

    def test_every_raw_text_field_is_required(self):
        for stage in ('before', 'after'):
            for key in contract.STATE_STRINGS:
                with self.subTest(stage=stage, key=key):
                    self.state_reject(stage, lambda state: state.pop(key))

    def test_green_page_failure_summary_cannot_hide_navigating_or_success(self):
        self.state_reject('after', lambda state: state.update(navigationFailed=False))
        self.state_reject('after', lambda state: state.update(navigating=True))

    def test_recovery_error_and_visible_status_must_match_actual_timeout(self):
        for mutation in (dict(pageError=''), dict(status='已连接'), dict(pageError='other', status='other')):
            self.state_reject('after', lambda state: state.update(mutation))

    def test_green_admission_cannot_hide_lost_route_or_guard(self):
        for stage in ('before', 'after'):
            for key in ('networkReady', 'guardAllowed'):
                self.state_reject(stage, lambda state: state.update({key: False}))

    def test_page_timeout_cannot_create_or_hide_network_manual_block(self):
        for stage in ('before', 'after'):
            self.state_reject(stage, lambda state: state.update(manualAttention=True))

    def test_each_network_retry_field_must_remain_unchanged(self):
        for key in ('recoveryToken', 'recoveryAttempt', 'connectionEpoch'):
            with self.subTest(key=key):
                self.state_reject('after', lambda state: state.update({key: state[key] + 1}))
        self.state_reject('after', lambda state: state.update(networkIssue='replacement diagnostic'))

    def test_no_reconnect_summary_cannot_hide_scheduled_or_active_work(self):
        for stage in ('before', 'after'):
            for key in ('recoveryScheduled', 'connecting'):
                self.state_reject(stage, lambda state: state.update({key: True}))

    def test_empty_state_must_retain_actual_sdk_session(self):
        self.state_reject('after', lambda state: state.update(session=456))
        self.state_reject('before', lambda state: state.update(session=456))

    def test_original_retained_anchor_is_required_and_bound(self):
        self.reject(lambda report: report.update(snapshots=[]))
        self.reject(lambda report: report['snapshots'].append(copy.deepcopy(report['snapshots'][0])))
        for key in ('session', 'connectionEpoch'):
            self.reject(lambda report: report['snapshots'][0].update({key: 999}))
            self.reject(lambda report: report['snapshots'][0].update({key: True}))

    def test_empty_page_cannot_be_a_visible_or_different_native_document(self):
        for stage in ('before', 'after'):
            self.state_reject(stage, lambda state: state.update(visible=True))
            for key in ('url', 'nativeUrl'):
                self.state_reject(stage, lambda state: state.update({key: 'https://chatgpt.com/'}))

    def test_exact_single_requested_navigation_epoch_is_required(self):
        for value in (True, 9.0, 8, 10, None):
            self.reject(lambda report: report['emptyConditionInputs'].update(requestedNavigationEpoch=value))
        self.state_reject('after', lambda state: state.update(navigationEpoch=10))
        self.reject(lambda report: (report['emptyConditionInputs'].update(requestedNavigationEpoch=10),
                                    report['emptyConditionInputs']['after'].update(navigationEpoch=10)))

    def test_no_reload_summary_cannot_hide_loads_or_stops(self):
        for key in ('loads', 'stops'):
            self.state_reject('after', lambda state: state.update({key: state[key] + 1}))

    def test_pending_summary_requires_all_four_exact_raw_copies(self):
        for stage in ('before', 'after'):
            for key in ('pending', 'persistedPending'):
                self.state_reject(stage, lambda state: state.update({key: ''}))

    def test_equal_pending_copies_cannot_substitute_another_task(self):
        for replacement in ('{}', 'invalid JSON', json.dumps(dict(id='different-task')), self.report['emptyConditionInputs']['before']['pending'].replace('continuity-5', 'continuity-6')):
            self.reject(lambda report: [report['emptyConditionInputs'][stage].update(pending=replacement, persistedPending=replacement)
                                        for stage in ('before', 'after')])

    def test_pending_attempt_flag_cannot_be_numeric(self):
        pending = json.loads(self.report['emptyConditionInputs']['before']['pending'])
        pending['attempted'] = 1
        replacement = json.dumps(pending)
        self.reject(lambda report: [report['emptyConditionInputs'][stage].update(pending=replacement, persistedPending=replacement)
                                    for stage in ('before', 'after')])

    def test_task_invocation_is_bound_to_original_controlled_url(self):
        for url in ('http://127.0.0.1:8765/browser-continuity?command=6',
                    'http://127.0.0.1:8765/browser-continuity?command=5&command=5',
                    'https://example.invalid/browser-continuity?command=5'):
            self.reject(lambda report: report['snapshots'][0]['document'].update(url=url))

    def test_host_action_scope_cannot_claim_actual_android_gesture(self):
        self.reject(lambda report: report['emptyConditionInputs'].update(uiScope='Actual Android recovery button clicked'))


if __name__ == '__main__':
    unittest.main()
