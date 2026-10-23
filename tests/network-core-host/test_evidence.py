#!/usr/bin/env python3
"""Synthetic validator tests; passing these is never Android or release evidence."""
import copy
import pathlib
import sys
import unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from tools.gecko.check_connection_evidence import NETWORK_REPAIR_CHECKS, verify_network_repair_evidence, BUSY_BOOTSTRAP_CHECKS, verify_busy_bootstrap_evidence
from tools.gecko.network_sources_contract import verify_route_busy_bootstrap


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


def bootstrap_fixture():
    rows = []
    for path in ('remembered', 'first-verified'):
        first = dict(alive=True, pid=200, servicePid=201, controllerPort=10000, proxyPort=10001,
                     generation='first', configuration='fixed-config', entry='entry-a', exitIp='203.0.113.8', tokenHash='a'*64)
        second = dict(first, generation='replacement', pid=202)
        rows.append(dict(path=path, busyBefore=True, busyAfter=True, callbackAccepted=True,
                         receiptCurrent=True, busyLiveSwitchBlocked=True, exitRequests=1, first=first,
                         directRebuild=dict(verified=True, busyAfter=True, exitRequests=1, replacement=second)))
    return dict(checks=[], busyBootstrap=rows)


class BootstrapEvidenceTests(unittest.TestCase):
    def good(self):
        value = bootstrap_fixture()
        value['checks'] = [{'name': name, 'pass': True} for name in BUSY_BOOTSTRAP_CHECKS]
        return value

    def test_valid_synthetic_receipt(self):
        self.assertTrue(verify_busy_bootstrap_evidence(self.good())['busyInitialRouteVerified'])

    def test_every_bootstrap_case_is_required(self):
        for name in BUSY_BOOTSTRAP_CHECKS:
            value = self.good(); value['checks'] = [r for r in value['checks'] if r['name'] != name]
            with self.assertRaises(AssertionError): verify_busy_bootstrap_evidence(value)

    def test_no_boolean_or_identity_can_be_invented(self):
        for field in ('busyBefore', 'busyAfter', 'callbackAccepted', 'receiptCurrent', 'busyLiveSwitchBlocked'):
            value = self.good(); value['busyBootstrap'][0][field] = False
            with self.assertRaises(AssertionError): verify_busy_bootstrap_evidence(value)
        for count in (0, -1, True, '1', 1.0):
            value = self.good(); value['busyBootstrap'][0]['exitRequests'] = count
            with self.assertRaises(AssertionError): verify_busy_bootstrap_evidence(value)
        for field in ('pid', 'generation'):
            value = self.good(); row = value['busyBootstrap'][0]; row['directRebuild']['replacement'][field] = row['first'][field]
            with self.assertRaises(AssertionError): verify_busy_bootstrap_evidence(value)
        for field in ('configuration', 'exitIp'):
            value = self.good(); value['busyBootstrap'][0]['directRebuild']['replacement'][field] = 'changed'
            with self.assertRaises(AssertionError): verify_busy_bootstrap_evidence(value)

    def test_actual_session_witness_cannot_clear_busy(self):
        value = {'checks': [{'name': 'A fresh manual core verifies its exit while the same real session remains navigation-busy', 'pass': True}],
                 'legacyBusyBootstrap': dict(actualSession=True, busyClearedForStartup=False, receiptCurrent=True, exitRequests=1,
                     before=dict(navigating=True, routeBusy=True, pending=False, fileWorkActive=False),
                     after=dict(navigating=True, routeBusy=True, pending=False, fileWorkActive=False))}
        self.assertTrue(verify_route_busy_bootstrap(value)['realSessionBusyPreserved'])
        for field in ('navigating', 'routeBusy'):
            bad = copy.deepcopy(value); bad['legacyBusyBootstrap']['after'][field] = False
            with self.assertRaises(AssertionError): verify_route_busy_bootstrap(bad)
        bad = copy.deepcopy(value); bad['legacyBusyBootstrap']['busyClearedForStartup'] = True
        with self.assertRaises(AssertionError): verify_route_busy_bootstrap(bad)


if __name__ == '__main__':
    unittest.main()
