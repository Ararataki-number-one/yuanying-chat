#!/usr/bin/env python3
"""Synthetic callback-accounting controls; no Android, core or route execution."""
import copy
import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    'network_settings_callback_contract', ROOT / 'tests/gecko/network_settings_callback_contract.py')
CONTRACT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CONTRACT)
ENV = '06309ee0-9d24-431e-a4ba-67f92cc98cb9'
JOBS = [
    'ebeea35b-09e2-4438-ba2b-34084b060299',
    '1b63d5d4-d2f7-4840-8081-9a19bc5f42e6',
    '77b27a5a-de66-4176-b84e-40a59344220d',
    '00a6b680-ea60-4e3e-8f11-f5b0ed3fb6ea',
]
CANDIDATES = [
    '31b5097461ae416a96945e64743a1837', '617278d47c5841ee841a1219ce3915b2',
    '155433c465aa48f788f49237d13a4b6a', '8065c0649616421599de86e7e3f21fbd',
]


def projection():
    """Self-contained projection of e21's five callback rows, not execution evidence."""
    results = []
    messages = ['配置已保存并由当前会话应用', '配置已保存并由当前会话应用',
                '应用失败，原线路恢复待确认', '配置已保存，实际应用回执尚未确认；当前网页保持打开']
    for index, (job, candidate, revision, state, ok) in enumerate(zip(
            JOBS, CANDIDATES, [4, 5, 5, 6],
            ['applied', 'applied', 'failed', 'saved-unconfirmed'], [True, True, False, False])):
        outcome = dict(environmentId=ENV, generation=0, candidateId=candidate,
                       savedRevision=revision, appliedRevision=revision if ok else 0,
                       saveState='saved', applicationState=state,
                       scope='core' if index == 2 else 'session', message=messages[index])
        if index == 2:
            outcome.update(rollbackState='unconfirmed', retryAvailable=True)
        results.append(dict(id=job, ok=ok, internal=False, operationResult=outcome))
    events = [dict(copy.deepcopy(row), sequence=index, targetDirect=True)
              for index, row in enumerate(results)]
    later = dict(environmentId=ENV, generation=0, candidateId=CANDIDATES[-1],
                 savedRevision=8, appliedRevision=6, saveState='saved',
                 applicationState='applied', scope='core', message='网络设置已应用',
                 networkAppliedRevision=8, browserAppliedRevision=6,
                 coreGeneration='6fa43757-12b0-489b-a95d-efaed8c0fae7', verifiedAt=1793805186820)
    events.append(dict(id='internal:4cb4a326-0645-432a-9ee2-8625cb084d9d',
                       ok=True, internal=True, operationResult=later,
                       sequence=4, targetDirect=False))
    return dict(applicationDirectJobs=list(JOBS), applicationResults=results,
                applicationCallbackEvents=events, applicationCallbackCount=len(events),
                actualAndroidExecution=False)


class CallbackCohortTests(unittest.TestCase):
    def rejected(self, report):
        with self.assertRaises((AssertionError, ValueError)):
            CONTRACT.verify_callback_cohort(report)

    def test_exact_e21_projection_preserves_four_direct_results_and_later_internal(self):
        report = projection(); before = copy.deepcopy(report)
        self.assertIsNone(CONTRACT.verify_callback_cohort(report))
        self.assertEqual(report, before)
        self.assertEqual(len(report['applicationCallbackEvents']), 5)
        self.assertFalse(report['actualAndroidExecution'])
        self.assertEqual(report['applicationResults'][-1]['operationResult']['savedRevision'], 6)

    def test_no_internal_callback_is_required(self):
        report = projection(); report['applicationCallbackEvents'].pop()
        report['applicationCallbackCount'] = 4
        CONTRACT.verify_callback_cohort(report)

    def test_internal_null_outcome_retained(self):
        report = projection(); report['applicationCallbackEvents'][-1]['operationResult'] = None
        CONTRACT.verify_callback_cohort(report)

    def test_internal_callbacks_may_precede_direct_and_canonical_order_is_by_id(self):
        report = projection(); events = report['applicationCallbackEvents']
        events.insert(0, events.pop())
        for index, event in enumerate(events): event['sequence'] = index
        report['applicationResults'].reverse()
        CONTRACT.verify_callback_cohort(report)

    def test_later_internal_revision_never_backfills_direct(self):
        report = projection(); report['applicationCallbackEvents'][-1]['operationResult']['savedRevision'] = 100
        CONTRACT.verify_callback_cohort(report)
        self.assertEqual(report['applicationResults'][-1]['operationResult']['savedRevision'], 6)

    def test_multiple_internal_events_remain_unfiltered_even_same_internal_id(self):
        report = projection(); extra = copy.deepcopy(report['applicationCallbackEvents'][-1])
        extra['sequence'] = 5; report['applicationCallbackEvents'].append(extra)
        report['applicationCallbackCount'] = 6
        CONTRACT.verify_callback_cohort(report)

    def test_direct_admission_requires_exactly_four_unique_noninternal_ids(self):
        for value in (None, {}, JOBS[:-1], JOBS + ['extra'], JOBS[:-1] + [JOBS[0]],
                      JOBS[:-1] + ['internal:forged'], JOBS[:-1] + [''], JOBS[:-1] + [True]):
            with self.subTest(value=value):
                report = projection(); report['applicationDirectJobs'] = value; self.rejected(report)

    def test_missing_required_arrays_rejected(self):
        for field in ('applicationDirectJobs', 'applicationCallbackEvents',
                      'applicationCallbackCount', 'applicationResults'):
            report = projection(); del report[field]; self.rejected(report)

    def test_independent_callback_count_is_a_strict_integer_and_matches_raw(self):
        for value in (None, True, False, 5.0, '5', -1, 4, 6):
            with self.subTest(value=value):
                report = projection(); report['applicationCallbackCount'] = value
                self.rejected(report)

    def test_omitted_terminal_internal_event_cannot_hide_behind_contiguous_sequence(self):
        report = projection(); report['applicationCallbackEvents'].pop()
        self.assertEqual([row['sequence'] for row in report['applicationCallbackEvents']], list(range(4)))
        self.rejected(report)

    def test_unknown_direct_callback_rejected_even_when_not_targeted(self):
        report = projection(); event = report['applicationCallbackEvents'][-1]
        event.update(id='unknown-direct', internal=False, targetDirect=False); self.rejected(report)

    def test_unknown_direct_cannot_claim_target_membership(self):
        report = projection(); report['applicationCallbackEvents'][0]['id'] = 'unknown-direct'
        self.rejected(report)

    def test_repeated_target_callback_rejected_without_dedup(self):
        report = projection(); event = copy.deepcopy(report['applicationCallbackEvents'][0])
        event['sequence'] = 5; report['applicationCallbackEvents'].append(event)
        report['applicationCallbackCount'] = 6; self.rejected(report)

    def test_missing_target_raw_event_cannot_be_replaced_by_internal_same_candidate(self):
        report = projection(); del report['applicationCallbackEvents'][3]
        report['applicationCallbackEvents'][-1]['sequence'] = 3
        report['applicationCallbackCount'] = 4; self.rejected(report)

    def test_null_or_nonobject_direct_outcome_rejected(self):
        for value in (None, [], '', 0, True):
            report = projection(); report['applicationCallbackEvents'][0]['operationResult'] = value
            self.rejected(report)

    def test_sequence_gap_reorder_duplicate_and_boolean_rejected(self):
        for value in (-1, 0, 3, True, '1', 1.0):
            report = projection(); report['applicationCallbackEvents'][1]['sequence'] = value
            self.rejected(report)
        report = projection(); report['applicationCallbackEvents'].reverse(); self.rejected(report)

    def test_raw_event_loss_retains_gap_and_is_rejected(self):
        report = projection(); del report['applicationCallbackEvents'][1]; self.rejected(report)

    def test_internal_marker_is_exactly_the_id_prefix(self):
        for index, value in ((0, True), (4, False), (0, 0), (4, 1)):
            report = projection(); report['applicationCallbackEvents'][index]['internal'] = value
            self.rejected(report)

    def test_target_marker_is_exactly_admission_membership(self):
        for index, value in ((0, False), (4, True), (0, 1), (4, 0)):
            report = projection(); report['applicationCallbackEvents'][index]['targetDirect'] = value
            self.rejected(report)

    def test_raw_ok_requires_boolean(self):
        for index in (0, 4):
            for value in (1, 0, None, 'true'):
                report = projection(); report['applicationCallbackEvents'][index]['ok'] = value
                self.rejected(report)

    def test_canonical_missing_duplicate_extra_unknown_internal_results_rejected(self):
        report = projection(); report['applicationResults'].pop(); self.rejected(report)
        report = projection(); report['applicationResults'].append(copy.deepcopy(report['applicationResults'][0]))
        self.rejected(report)
        report = projection(); report['applicationResults'][1] = copy.deepcopy(report['applicationResults'][0])
        self.rejected(report)
        for field, value in (('id', 'unknown'), ('id', 'internal:forged'), ('internal', True), ('ok', False)):
            report = projection(); report['applicationResults'][0][field] = value; self.rejected(report)

    def test_canonical_internal_result_cannot_replace_original_stale_direct(self):
        report = projection(); row = report['applicationResults'][-1]
        row.update(ok=True, operationResult=copy.deepcopy(report['applicationCallbackEvents'][-1]['operationResult']))
        self.rejected(report)

    def test_canonical_revision_or_state_backfill_rejected(self):
        for field, value in (('savedRevision', 8), ('appliedRevision', 6),
                             ('applicationState', 'applied'), ('scope', 'core'), ('candidateId', CANDIDATES[0])):
            report = projection(); report['applicationResults'][-1]['operationResult'][field] = value
            self.rejected(report)

    def test_canonical_equality_is_type_strict_and_compares_optional_fields(self):
        report = projection(); report['applicationResults'][0]['ok'] = 1; self.rejected(report)
        report = projection(); report['applicationResults'][0]['operationResult']['generation'] = False
        self.rejected(report)
        report = projection(); report['applicationResults'][2]['operationResult']['retryAvailable'] = 1
        self.rejected(report)
        report = projection(); report['applicationResults'][0]['operationResult']['added'] = True
        self.rejected(report)

    def test_callback_and_canonical_field_shapes_are_exact(self):
        for field in ('sequence', 'targetDirect', 'operationResult'):
            report = projection(); del report['applicationCallbackEvents'][0][field]; self.rejected(report)
        report = projection(); report['applicationCallbackEvents'][0]['unexpected'] = 1; self.rejected(report)
        report = projection(); report['applicationResults'][0]['sequence'] = 0; self.rejected(report)

    def test_internal_receipt_requires_common_production_fields(self):
        for field in CONTRACT._RECEIPT_FIELDS:
            report = projection(); del report['applicationCallbackEvents'][-1]['operationResult'][field]
            self.rejected(report)

    def test_internal_generation_and_revisions_are_nonnegative_integers(self):
        for field in ('generation', 'savedRevision', 'appliedRevision', 'networkAppliedRevision',
                      'browserAppliedRevision', 'verifiedAt'):
            for value in (-1, True, 1.0, '8', None):
                report = projection(); report['applicationCallbackEvents'][-1]['operationResult'][field] = value
                self.rejected(report)

    def test_internal_receipt_strings_states_and_booleans_are_valid(self):
        for field, value in (('environmentId', 'unknown'), ('environmentId', 1),
                             ('candidateId', 'UPPER'), ('candidateId', ''), ('saveState', 'invented'),
                             ('applicationState', 'ready'), ('scope', 'browser'), ('message', None),
                             ('coreGeneration', ''), ('retryAvailable', 1), ('recoveryRequired', 'true'),
                             ('rollbackState', 'unknown')):
            report = projection(); report['applicationCallbackEvents'][-1]['operationResult'][field] = value
            self.rejected(report)

    def test_known_internal_unknown_save_receipts_remain_legal(self):
        for save, state in (('superseded', 'superseded'), ('uncertain', 'unconfirmed'),
                            ('failed', 'saved-unconfirmed')):
            report = projection(); outcome = report['applicationCallbackEvents'][-1]['operationResult']
            for field in CONTRACT._OPTIONAL_RECEIPT_FIELDS: outcome.pop(field, None)
            outcome.update(saveState=save, applicationState=state, candidateId='',
                           savedRevision=0, appliedRevision=0, scope='session')
            CONTRACT.verify_callback_cohort(report)

    def test_nonobject_internal_outcome_and_foreign_receipt_fields_rejected(self):
        for value in ([], True, '', 8):
            report = projection(); report['applicationCallbackEvents'][-1]['operationResult'] = value
            self.rejected(report)
        report = projection(); report['applicationCallbackEvents'][-1]['operationResult']['unrelated'] = 1
        self.rejected(report)


if __name__ == '__main__':
    unittest.main()
