#!/usr/bin/env python3
"""Synthetic validator tests; passing these is never Android or release evidence."""
import copy
import pathlib
import sys
import unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from tools.gecko.check_connection_evidence import NETWORK_REPAIR_CHECKS, verify_network_repair_evidence


def fixture():
    return {'checks': [{'name': name, 'pass': True} for name in sorted(NETWORK_REPAIR_CHECKS)],
            'networkRepairEvidence': {
                'schema': 1, 'serviceGenerationStopGuard': True, 'exitDiagnostics': True,
                'retainedOutcome': True, 'busyBeforeMutation': True,
                'candidateFailure': dict(accepted=False, sameReceipt=True, sameCore=True,
                    sameEntry=True, verified=True, optimizationBackoff=True),
                'rollback': dict(exitRequests=2, newReceipt=True, sameEntry=True, verified=True, sameCore=True),
                'backoffRecovery': dict(exitRequests=1, entryChanged=True, verified=True,
                    sameCore=True, sameWebSocket=True, detectorRetryReset=True),
                'failedRollback': dict(ready=False, coreAlive=False, receiptCurrent=False, webSocketClosed=True)}}


class NetworkRepairEvidenceTests(unittest.TestCase):
    def test_complete_synthetic_validator_input(self):
        self.assertTrue(verify_network_repair_evidence(fixture())['retainedIsNotRecovered'])

    def test_every_required_case_must_exist_and_pass(self):
        for name in NETWORK_REPAIR_CHECKS:
            for missing in (True, False):
                with self.subTest(name=name, missing=missing):
                    report = fixture()
                    if missing:
                        report['checks'] = [row for row in report['checks'] if row['name'] != name]
                    else:
                        next(row for row in report['checks'] if row['name'] == name)['pass'] = False
                    with self.assertRaises(AssertionError):
                        verify_network_repair_evidence(report)

    def test_every_observed_boolean_is_required(self):
        complete = fixture()
        evidence = complete['networkRepairEvidence']
        paths = [(key,) for key, value in evidence.items() if type(value) is bool]
        paths += [(key, field) for key, value in evidence.items() if isinstance(value, dict)
                  for field, observed in value.items() if type(observed) is bool]
        for path in paths:
            with self.subTest(path=path):
                report = copy.deepcopy(complete)
                value = report['networkRepairEvidence']
                for key in path[:-1]:
                    value = value[key]
                value[path[-1]] = not value[path[-1]]
                with self.assertRaises(AssertionError):
                    verify_network_repair_evidence(report)

    def test_rollback_requires_two_real_exit_requests_and_recovery_one(self):
        for group, counts in [('rollback', [0, 1, 3, True, 2.0, '2']), ('backoffRecovery', [0, 2, 3, True, 1.0, '1'])]:
            for count in counts:
                with self.subTest(group=group, count=count):
                    report = fixture()
                    report['networkRepairEvidence'][group]['exitRequests'] = count
                    with self.assertRaises(AssertionError):
                        verify_network_repair_evidence(report)

    def test_old_report_without_new_observations_is_not_accepted(self):
        report = fixture()
        del report['networkRepairEvidence']
        with self.assertRaises(KeyError):
            verify_network_repair_evidence(report)


if __name__ == '__main__':
    unittest.main()
