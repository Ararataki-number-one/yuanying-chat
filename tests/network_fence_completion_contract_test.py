#!/usr/bin/env python3
"""Synthetic owner-bound release controls; never Android acceptance evidence."""
import copy
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('safe_idle_synthetic', ROOT/'tests/profile_network_safe_idle_contract_test.py')
FIXTURE = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(FIXTURE)
C = FIXTURE.C


def sample():
    report = FIXTURE.receipt()
    return report, report['cases'][-1]


def synchronize(report, row):
    """Keep event copies coherent so a mutation tests its actual inner guard."""
    for event in report['phaseEvents']:
        if event['value'].get('case', event['value'].get('name')) != row['name']:
            continue
        if event['kind'] == 'case': event['value'] = copy.deepcopy(row)
        elif event['kind'] == 'caseCompletion': event['value'] = copy.deepcopy(row['completionProof'])
        elif event['kind'] == 'caseOwnershipObservation':
            event['value'] = dict(case=row['name'], jobId=row['completionProof']['jobId'],
                                 completionProof=copy.deepcopy(row['completionProof']),
                                 currentOwnership=copy.deepcopy(row['currentOwnership']))


def later(row, shared=False):
    row['currentOwnership'].update(ownerPresent=True,
        ownerId='internal:9496c6ac-b736-4665-a8dd-b99d569a8571',
        ownerToken=999, sameSession=True, internal=True,
        operation=True, configurationCapture=True, ownerCapture=True,
        ownerFenced=True, touchOwned=True, originalTouchRestored=not shared,
        touchFenceSharedWithCurrent=shared)


class CompletionOwnershipTests(unittest.TestCase):
    def reject(self, mutate):
        report, row = sample(); mutate(row); synchronize(report, row)
        with self.assertRaises((AssertionError, KeyError, TypeError)):
            C.verify_safe_idle(report)

    def test_original_closed_owner_report_still_passes(self):
        report, _ = sample(); before = copy.deepcopy(report)
        C.verify_safe_idle(report); self.assertEqual(report, before)

    def test_later_internal_capture_is_recorded_without_rewriting_old_release(self):
        for shared in (False, True):
            report, row = sample(); later(row, shared); synchronize(report, row)
            C.verify_safe_idle(report)
            self.assertTrue(row['currentOwnership']['operation'])
            self.assertFalse(row['outcome']['operation'])
            self.assertFalse(row['completionProof']['operation'])

    def test_missing_proof_and_missing_proof_fields_rejected(self):
        report, row = sample(); del row['completionProof']
        with self.assertRaises((AssertionError, KeyError)): C.verify_safe_idle(report)
        for field in list(sample()[1]['completionProof']):
            def mutate(row, field=field): del row['completionProof'][field]
            report, row = sample(); mutate(row)
            # Missing jobId cannot be synchronized, but direct helper still must reject.
            with self.assertRaises((AssertionError, KeyError, TypeError)):
                C._verify_safe_idle_completion(row, report['phaseEvents'])

    def test_original_touch_or_capture_leak_rejected_even_with_valid_new_owner(self):
        for field, value in [('operation', True), ('configurationCapture', True), ('touchRestored', False)]:
            def mutate(row, field=field, value=value):
                later(row, True)
                row['completionProof'][field] = row['outcome'][field] = value
            self.reject(mutate)
        self.reject(lambda row: row['completionProof'].update(ownerCapture=True))

    def test_original_owner_identity_boundary_and_retirement_are_required(self):
        for field, value in [('ownerId', 'wrong'), ('jobId', 'internal:wrong'),
                             ('ownerToken', True), ('ownerToken', 0),
                             ('boundary', 'later-global-snapshot'), ('cancelled', False),
                             ('activeTransitionIsOwner', True), ('activeTransitionPresent', True)]:
            self.reject(lambda row, field=field, value=value: row['completionProof'].update({field: value}))

    def test_completion_receipt_cannot_be_replaced_by_newer_internal_receipt(self):
        self.reject(lambda row: row['completionProof']['job'].update(ok=False))
        self.reject(lambda row: row['completionProof']['job'].update(done=False))

    def test_later_owner_must_be_different_internal_on_same_session(self):
        for field, value in [('ownerId', 'unregistered-direct'), ('ownerId', ''),
                             ('ownerToken', 0), ('ownerToken', 7), ('ownerToken', True),
                             ('internal', False), ('isOriginal', True), ('sameSession', False)]:
            def mutate(row, field=field, value=value):
                later(row); row['currentOwnership'][field] = value
            self.reject(mutate)

    def test_new_owner_capture_and_touch_must_match_actual_flags(self):
        for field in ('operation', 'configurationCapture', 'ownerCapture', 'ownerFenced', 'touchOwned'):
            def mutate(row, field=field):
                later(row); row['currentOwnership'][field] = False
            self.reject(mutate)

    def test_absent_owner_cannot_leave_global_capture_or_shared_touch(self):
        for field in ('operation', 'configurationCapture', 'ownerCapture', 'ownerFenced', 'touchOwned',
                      'touchFenceSharedWithCurrent', 'internal'):
            self.reject(lambda row, field=field: row['currentOwnership'].update({field: True}))
        self.reject(lambda row: row['currentOwnership'].update(originalTouchRestored=False))

    def test_listener_reuse_requires_current_real_fence_and_earlier_real_release(self):
        for field, value in [('touchFenceSharedWithCurrent', False), ('touchOwned', False),
                             ('ownerFenced', False), ('ownerPresent', False), ('originalTouchRestored', True)]:
            def mutate(row, field=field, value=value):
                later(row, True); row['currentOwnership'][field] = value
            self.reject(mutate)
        def unfenced_original(row):
            later(row, True); row['completionProof']['fenced'] = row['outcome']['fenced'] = False
        self.reject(unfenced_original)

    def test_boolean_fields_reject_missing_numbers_strings_and_null(self):
        _, sample_row = sample()
        for part in ('currentOwnership', 'completionProof'):
            for field, value in sample_row[part].items():
                if type(value) is not bool: continue
                for bad in (int(value), 'true', None):
                    self.reject(lambda row, part=part, field=field, bad=bad: row[part].update({field: bad}))

    def test_owner_completion_observation_events_are_unique_and_ordered(self):
        for kind in ('caseOwner', 'caseCompletion', 'caseOwnershipObservation'):
            report, row = sample()
            event = next(event for event in report['phaseEvents'] if event['kind'] == kind and event['value'].get('case') == row['name'])
            report['phaseEvents'].append(copy.deepcopy(event))
            with self.assertRaises(AssertionError): C.verify_safe_idle(report)
            report, row = sample()
            event = next(event for event in report['phaseEvents'] if event['kind'] == kind and event['value'].get('case') == row['name'])
            report['phaseEvents'].remove(event)
            with self.assertRaises(AssertionError): C.verify_safe_idle(report)
        report, row = sample()
        event = next(event for event in report['phaseEvents'] if event['kind'] == 'caseCompletion' and event['value']['case'] == row['name'])
        report['phaseEvents'].remove(event); report['phaseEvents'].insert(0, event)
        with self.assertRaises(AssertionError): C.verify_safe_idle(report)


if __name__ == '__main__': unittest.main()
