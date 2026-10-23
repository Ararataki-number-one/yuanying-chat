#!/usr/bin/env python3
"""Synthetic validator tests; passing these is never Android or release evidence."""
import copy
import json
import pathlib
import re
import subprocess
import sys
import unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from tools.gecko.check_connection_evidence import NETWORK_REPAIR_CHECKS, verify_network_repair_evidence, BUSY_BOOTSTRAP_CHECKS, verify_busy_bootstrap_evidence
from tools.gecko.network_sources_contract import verify_route_busy_bootstrap, verify_route_busy_phase_boundary


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


def phase_boundary_fixture():
    """Invented parser input only; never an Android execution receipt."""
    names = [
        'Legacy manual exit starts through the same production path',
        'A fresh manual core verifies its exit while the same real session remains navigation-busy',
        'Manual path keeps its ordinary SOCKS proxy and removes subscribed exit files',
        'The controlled busy phase ends after bootstrap without changing browser admission or the verified route',
        'Ending the controlled busy phase preserves the actual Gecko document and unsent draft',
    ]
    busy = dict(navigating=True, routeBusy=True, pending=False, fileWorkActive=False)
    before = dict(busy, submitting=False, operation=False, transferActive=False, stateBusy=False,
        networkReady=False, guardAllowed=False, guardBlocked=True, connecting=False, offline=False,
        coreReady=True, coreStarting=False, nativeReceiptCurrent=True,
        nativeReceiptObservation='pushed-service-state', defaultNetworkUsable=True,
        connectionEpoch=5, navigationEpoch=7, sessionDocumentId='', appliedIdentity='previous-browser-route',
        browserIdentity=100, geckoSessionIdentity=101, routeSerial=2,
        receipt=dict(fingerprint='a'*64, tokenHash='b'*64, configurationHash='c'*64,
            entry='Entry|a', generation='manual-core-generation', serial=2,
            controller=10000, proxy=10001, pid=200, servicePid=201))
    after = copy.deepcopy(before); after.update(navigating=False, routeBusy=False)
    document = dict(url='https://127.0.0.1:9879/pool', controlled=True,
                    timeOrigin=1700000000123.5, draft='unsent pool draft', sends=0)
    observed = dict(ok=True, url=document['url'], document=document)
    observations = [dict(phase=phase, scope='Gecko WebExtension isolated-world controlled document observation',
        expectedUrl=document['url'], beganAtNs=1001+i*2, endedAtNs=1002+i*2, validated=True,
        raw=json.dumps(observed), result=copy.deepcopy(observed)) for i, phase in enumerate(('before', 'after'))]
    return dict(checks=[{'name': name, 'pass': True} for name in names],
        legacyPhaseDocumentObservations=observations,
        legacyBusyBootstrap=dict(actualSession=True, busyClearedForStartup=False, receiptCurrent=True,
            exitRequests=1, before=copy.deepcopy(busy), after=copy.deepcopy(busy)),
        legacyBusyPhaseBoundary=dict(schema=1, method='test-only end of controlled navigation-busy phase',
            domReadyInferred=False, bootstrapCheckCount=3, beganAtNs=1000, endedAtNs=2000,
            before=before, after=after, documentBefore=copy.deepcopy(document), documentAfter=copy.deepcopy(document)),
        sessionRestorations=[dict(name='legacy-manual', beganAtNs=2001)])


class BusyPhaseBoundaryEvidenceTests(unittest.TestCase):
    def test_synthetic_input_records_only_phase_end_not_admission(self):
        result = verify_route_busy_phase_boundary(phase_boundary_fixture())
        self.assertTrue(result['browserAdmissionAndReceiptUnchanged'])
        self.assertTrue(result['requiresSubsequentProductionReconnect'])

    def test_old_missing_or_early_boundary_is_rejected(self):
        report = phase_boundary_fixture(); del report['legacyBusyPhaseBoundary']
        with self.assertRaises(KeyError): verify_route_busy_phase_boundary(report)
        for count in (0, 1, 2, 4, 100, True, 3.0):
            report = phase_boundary_fixture(); report['legacyBusyPhaseBoundary']['bootstrapCheckCount'] = count
            with self.subTest(count=count), self.assertRaises(AssertionError): verify_route_busy_phase_boundary(report)
        for index in range(5):
            for remove in (False, True):
                report = phase_boundary_fixture()
                if remove: report['checks'].pop(index)
                else: report['checks'][index]['pass'] = False
                with self.subTest(index=index, remove=remove), self.assertRaises(AssertionError): verify_route_busy_phase_boundary(report)

    def test_cannot_clear_original_bootstrap_busy_or_declare_dom_ready(self):
        for group, field in (('legacyBusyBootstrap', 'busyClearedForStartup'), ('legacyBusyPhaseBoundary', 'domReadyInferred')):
            report = phase_boundary_fixture(); report[group][field] = True
            with self.subTest(field=field), self.assertRaises(AssertionError): verify_route_busy_phase_boundary(report)
        for side in ('before', 'after'):
            report = phase_boundary_fixture(); report['legacyBusyBootstrap'][side]['navigating'] = False
            with self.subTest(side=side), self.assertRaises(AssertionError): verify_route_busy_phase_boundary(report)
        for key in ('pending', 'fileWorkActive'):
            report = phase_boundary_fixture()
            for side in ('before', 'after'): report['legacyBusyBootstrap'][side][key] = True
            with self.subTest(splicedWork=key), self.assertRaises(AssertionError): verify_route_busy_phase_boundary(report)

    def test_admission_route_epochs_or_other_work_cannot_change(self):
        alterations = dict(networkReady=True, guardAllowed=True, guardBlocked=False, nativeReceiptCurrent=False,
            coreReady=False, connecting=True, offline=True, connectionEpoch=6, navigationEpoch=8,
            browserIdentity=102, geckoSessionIdentity=103, routeSerial=3,
            sessionDocumentId='replacement-document', appliedIdentity='replacement-browser-route',
            pending=True, fileWorkActive=True, submitting=True, operation=True, transferActive=True, stateBusy=True)
        for key, value in alterations.items():
            report = phase_boundary_fixture(); report['legacyBusyPhaseBoundary']['after'][key] = value
            with self.subTest(key=key), self.assertRaises(AssertionError): verify_route_busy_phase_boundary(report)
        for key in ('pid', 'servicePid', 'serial', 'controller', 'proxy', 'generation', 'entry', 'fingerprint', 'tokenHash', 'configurationHash'):
            report = phase_boundary_fixture(); receipt = report['legacyBusyPhaseBoundary']['after']['receipt']
            receipt[key] = receipt[key] + 1 if type(receipt[key]) is int else receipt[key] + '-changed'
            with self.subTest(receipt=key), self.assertRaises(AssertionError): verify_route_busy_phase_boundary(report)
        for key in ('pending', 'fileWorkActive', 'submitting', 'operation', 'transferActive', 'stateBusy'):
            report = phase_boundary_fixture()
            for side in ('before', 'after'): report['legacyBusyPhaseBoundary'][side][key] = True
            with self.subTest(unchangedRealWork=key), self.assertRaises(AssertionError): verify_route_busy_phase_boundary(report)

    def test_actual_document_and_draft_must_survive(self):
        for key, value in dict(timeOrigin=1700000000999.5, url='https://chatgpt.com/', controlled=False, draft='', sends=1).items():
            report = phase_boundary_fixture(); report['legacyBusyPhaseBoundary']['documentAfter'][key] = value
            with self.subTest(key=key), self.assertRaises(AssertionError): verify_route_busy_phase_boundary(report)
        for origin in (0, -1, True, '1700000000123.5', float('nan'), float('inf')):
            report = phase_boundary_fixture()
            for side in ('documentBefore', 'documentAfter'): report['legacyBusyPhaseBoundary'][side]['timeOrigin'] = origin
            with self.subTest(origin=origin), self.assertRaises(AssertionError): verify_route_busy_phase_boundary(report)

    def test_real_reconnect_must_follow_completed_boundary(self):
        for began, ended, reconnect in ((0, 2000, 2001), (2000, 1000, 2001), (1000, 2000, 1999), (True, 2000, 2001)):
            report = phase_boundary_fixture(); report['legacyBusyPhaseBoundary'].update(beganAtNs=began, endedAtNs=ended)
            report['sessionRestorations'][0]['beganAtNs'] = reconnect
            with self.subTest(times=(began, ended, reconnect)), self.assertRaises(AssertionError): verify_route_busy_phase_boundary(report)
        report = phase_boundary_fixture(); report['sessionRestorations'] = []
        with self.assertRaises(AssertionError): verify_route_busy_phase_boundary(report)


class PhaseDocumentScriptTests(unittest.TestCase):
    """Execute the Java fixture's exact JS in a host vm, never Android/Gecko evidence."""
    @classmethod
    def setUpClass(cls):
        source = (pathlib.Path(__file__).resolve().parents[1] / 'gecko/NetworkSourcesRouteIntegrationActivity.java').read_text()
        literal = re.search(r'  static final String PHASE_DOCUMENT_SCRIPT=("(?:[^"\\]|\\.)*");', source)
        assert literal, 'Read the actual Java fixture script, not a duplicate host script'
        cls.script = json.loads(literal.group(1))
        runner = r'''
const vm=require('node:vm'),fs=require('node:fs'),script=JSON.parse(fs.readFileSync(0,'utf8')).script;
const output={};
for(const mode of ['normal','content-performance-unavailable','performance-throws','performance-missing','time-origin-missing','time-origin-nan','textarea-missing','empty-document']){
  const context={location:{href:'https://127.0.0.1:9879/pool'},performance:{timeOrigin:1700000000123.5},
    document:{getElementById:id=>mode==='empty-document'?null:id==='pool-ready'?{}:id==='prompt-textarea'?(mode==='textarea-missing'?null:{value:'unsent pool draft'}):id==='send-count'?{textContent:'0'}:null}};
  if(mode==='content-performance-unavailable')context.content={get performance(){throw new Error('content alias unavailable');}};
  if(mode==='performance-throws')Object.defineProperty(context,'performance',{get(){throw new TypeError('host controlled performance failure');}});
  if(mode==='performance-missing')delete context.performance;
  if(mode==='time-origin-missing')context.performance={};
  if(mode==='time-origin-nan')context.performance.timeOrigin=NaN;
  output[mode]=vm.runInNewContext(script,context,{timeout:1000});
}
process.stdout.write(JSON.stringify({scope:'Host vm controls of actual Java fixture JS; no Android/Gecko execution',output}));
'''
        result = subprocess.run(['node', '-e', runner], input=json.dumps({'script': cls.script}),
                                text=True, capture_output=True, check=True, timeout=15)
        cls.values = json.loads(result.stdout)['output']

    def report_for(self, observed):
        report = phase_boundary_fixture()
        for row in report['legacyPhaseDocumentObservations']:
            row.update(raw=json.dumps(observed), result=copy.deepcopy(observed))
        return report

    def test_actual_java_script_observes_global_performance_without_content_alias(self):
        for mode in ('normal', 'content-performance-unavailable'):
            value = self.values[mode]
            self.assertTrue(value['ok']);self.assertEqual(value['document']['timeOrigin'], 1700000000123.5)
            self.assertTrue(verify_route_busy_phase_boundary(self.report_for(value))['actualDocumentPreserved'])

    def test_actual_js_exceptions_and_missing_fields_remain_explicit_and_rejected(self):
        for mode in ('performance-throws', 'performance-missing', 'time-origin-missing', 'time-origin-nan', 'textarea-missing', 'empty-document'):
            value = self.values[mode]
            with self.subTest(mode=mode):
                self.assertFalse(value['ok']);self.assertEqual(value['url'], 'https://127.0.0.1:9879/pool')
                self.assertTrue(value['error']['name']);self.assertTrue(value['error']['message'])
                with self.assertRaises(AssertionError): verify_route_busy_phase_boundary(self.report_for(value))

    def test_empty_null_invalid_and_replaced_raw_observations_cannot_pass(self):
        for raw in ('', 'null', '{}', '[]', 'not-json', '{', json.dumps({'ok': True})):
            report = phase_boundary_fixture();report['legacyPhaseDocumentObservations'][0]['raw'] = raw
            with self.subTest(raw=raw), self.assertRaises((AssertionError, ValueError, KeyError)):
                verify_route_busy_phase_boundary(report)
        for field, value in [('validated', False), ('scope', 'invented fallback'), ('expectedUrl', 'https://chatgpt.com/'),
                             ('beganAtNs', 999), ('endedAtNs', 3000), ('error', {'type': 'java.io.IOException'})]:
            report = phase_boundary_fixture();report['legacyPhaseDocumentObservations'][0][field] = value
            with self.subTest(field=field), self.assertRaises(AssertionError): verify_route_busy_phase_boundary(report)
        report = phase_boundary_fixture();report['legacyPhaseDocumentObservations'].reverse()
        with self.assertRaises(AssertionError): verify_route_busy_phase_boundary(report)


if __name__ == '__main__':
    unittest.main()
