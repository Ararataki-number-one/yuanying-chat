"""Synthetic rejection controls for actual cold-probe observation receipts."""
import copy
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from tools.gecko.check_connection_evidence import collect_cold_website_probe_event, verify_cold_website_probe_diagnostics


def fixture():
    token = 'a' * 32
    readings = [dict(entry='Entry|slow', at=1, firstMs=122, warmMs=2, code=200, status='ok'),
                dict(entry='Entry|fast', at=2, firstMs=40, warmMs=3, code=200, status='ok')]
    calls = [dict(case=i, entry=readings[i-1]['entry'], callBeganAtNs=i*1_000_000_000,
                  callEndedAtNs=i*1_000_000_000+400_000_000, reading=readings[i-1]) for i in (1, 2)]
    circuits = []
    for case, role, delay in ((1, 'slow', 100), (2, 'fast', 5)):
        base = case * 1_000_000_000
        entry = dict(circuit=len(circuits)+1, case=case, role=role, acceptedAtNs=base+1,
                     listenPort=10000+case, peerPort=20000+case, tls=False, handleBeganAtNs=base+2,
                     targetHost='127.0.0.1', targetPort=30000, requestedDelayMs=delay,
                     delayBeganAtNs=base+3, delayEndedAtNs=base+delay*1_000_000+3,
                     upstreamConnectBeganAtNs=base+delay*1_000_000+4,
                     upstreamConnectEndedAtNs=base+delay*1_000_000+5,
                     upstreamLocalPort=40000+case, upstreamRemotePort=30000,
                     socksReplyFlushedAtNs=base+delay*1_000_000+6)
        base += delay*1_000_000+5
        fixed = dict(circuit=len(circuits)+2, case=case, role='fixed', acceptedAtNs=base,
                     listenPort=30000, peerPort=40000+case, tls=False, handleBeganAtNs=base+1,
                     targetHost='127.0.0.1', targetPort=50000, requestedDelayMs=0,
                     delayBeganAtNs=base+2, delayEndedAtNs=base+3, upstreamConnectBeganAtNs=base+4,
                     upstreamConnectEndedAtNs=base+5, upstreamLocalPort=60000+case,
                     upstreamRemotePort=50000, socksReplyFlushedAtNs=base+6)
        site = dict(circuit=len(circuits)+3, case=case, role='site', acceptedAtNs=base+5,
                    listenPort=50000, peerPort=60000+case, tls=True, handleBeganAtNs=base+6,
                    firstReadBeganAtNs=base+7, tlsCompletionListenerAtNs=base+100,
                    requests=[dict(ordinal=i, method='HEAD', path='/website', responseCode=200,
                                   requestLineAtNs=base+i*10, headersReadAtNs=base+i*10+1,
                                   responseWriteBeganAtNs=base+i*10+2,
                                   responseFlushedAtNs=base+i*10+3) for i in (1, 2)])
        circuits.extend((entry, fixed, site))
    records = [('call', row) for row in calls] + [('circuit', row) for row in circuits]
    return dict(controlledWebsiteReadings=copy.deepcopy(readings),
                coldWebsiteProbeDiagnosticSummary=dict(schema=1, token=token, eventCount=len(records),
                    callCount=2, circuitCount=len(circuits), clock='Android elapsedRealtimeNanos',
                    frozen=True, overflow=False, timerUnchanged=True,
                    requestedConnectDelayMs=dict(slow=100, fast=5, fixed=0)),
                coldWebsiteProbeDiagnostics=[dict(token=token, order=i, recordKind=kind, payload=row)
                    for i, (kind, row) in enumerate(records, 1)])


class ColdWebsiteDiagnosticTest(unittest.TestCase):
    def test_complete_synthetic_shape_with_late_tls_listener(self):
        result = verify_cold_website_probe_diagnostics(fixture())
        self.assertTrue(result['originalColdOrderingRetained'])
        self.assertFalse(result['productSpeedComparison'])

    def test_current_122_150_failure_cannot_be_relabelled_passing(self):
        report = fixture()
        report['controlledWebsiteReadings'][1]['firstMs'] = 150
        report['coldWebsiteProbeDiagnostics'][1]['payload']['reading']['firstMs'] = 150
        with self.assertRaises(AssertionError): verify_cold_website_probe_diagnostics(report)

    def test_missing_or_mixed_observations_fail(self):
        mutations = [lambda r: r.pop('coldWebsiteProbeDiagnosticSummary'),
                     lambda r: r['coldWebsiteProbeDiagnostics'].pop(),
                     lambda r: r['coldWebsiteProbeDiagnosticSummary'].update(overflow=True),
                     lambda r: r['coldWebsiteProbeDiagnosticSummary'].update(timerUnchanged=False),
                     lambda r: r['coldWebsiteProbeDiagnosticSummary']['requestedConnectDelayMs'].update(slow=200),
                     lambda r: r['coldWebsiteProbeDiagnostics'][2].update(token='b'*32),
                     lambda r: r['coldWebsiteProbeDiagnostics'][3].update(order=3),
                     lambda r: r['coldWebsiteProbeDiagnostics'][0]['payload'].update(entry='Entry|fast'),
                     lambda r: r['coldWebsiteProbeDiagnostics'][0]['payload'].update(callEndedAtNs=0),
                     lambda r: r['coldWebsiteProbeDiagnostics'][2]['payload'].update(case=2),
                     lambda r: r['coldWebsiteProbeDiagnostics'][3]['payload'].update(peerPort=12345),
                     lambda r: r['coldWebsiteProbeDiagnostics'][4]['payload'].update(peerPort=12345),
                     lambda r: r['coldWebsiteProbeDiagnostics'][2]['payload'].update(targetHost='outside.invalid'),
                     lambda r: r['coldWebsiteProbeDiagnostics'][2]['payload'].update(delayEndedAtNs=1),
                     lambda r: r['coldWebsiteProbeDiagnostics'][2]['payload'].update(delayEndedAtNs=1_050_000_000),
                     lambda r: r['coldWebsiteProbeDiagnostics'][4]['payload']['requests'].pop(),
                     lambda r: r['coldWebsiteProbeDiagnostics'][4]['payload']['requests'][0].update(method='GET'),
                     lambda r: r['coldWebsiteProbeDiagnostics'][4]['payload']['requests'][0].update(responseCode=503),
                     lambda r: r['coldWebsiteProbeDiagnostics'][4]['payload']['requests'][0].update(responseWriteBeganAtNs=1),
                     lambda r: r['controlledWebsiteReadings'][0].update(firstMs=99)]
        for index, mutate in enumerate(mutations):
            with self.subTest(index=index):
                report = fixture(); mutate(report)
                with self.assertRaises((AssertionError, KeyError)): verify_cold_website_probe_diagnostics(report)

    def test_optional_late_flush_and_tls_listener_are_not_fabricated(self):
        report = fixture()
        for event in report['coldWebsiteProbeDiagnostics']:
            row = event['payload']
            if row.get('role') == 'site':
                row.pop('tlsCompletionListenerAtNs')
                row['requests'][1].pop('responseFlushedAtNs')
        verify_cold_website_probe_diagnostics(report)

    def test_collector_requires_one_invocation_and_retains_exact_duplicate_reads(self):
        report = fixture(); events = {}; summary = None
        handled, summary = collect_cold_website_probe_event(dict(kind='coldWebsiteProbeDiagnosticSummary', value=report['coldWebsiteProbeDiagnosticSummary']), events, summary)
        self.assertTrue(handled)
        for row in report['coldWebsiteProbeDiagnostics']:
            event = dict(kind='coldWebsiteProbeDiagnostic', value=row)
            for _ in range(2):
                handled, summary = collect_cold_website_probe_event(event, events, summary)
                self.assertTrue(handled)
        self.assertEqual(list(events.values()), report['coldWebsiteProbeDiagnostics'])
        self.assertEqual(collect_cold_website_probe_event(dict(kind='check'), events, summary), (False, summary))

    def test_collector_rejects_reorder_conflict_missing_summary_and_mixed_token(self):
        report = fixture(); summary = report['coldWebsiteProbeDiagnosticSummary']; row = report['coldWebsiteProbeDiagnostics'][0]
        cases = [(dict(kind='coldWebsiteProbeDiagnostic', value=row), {}, None),
                 (dict(kind='coldWebsiteProbeDiagnostic', value=report['coldWebsiteProbeDiagnostics'][1]), {}, summary),
                 (dict(kind='coldWebsiteProbeDiagnostic', value=dict(row, token='b'*32)), {}, summary),
                 (dict(kind='coldWebsiteProbeDiagnostic', value=dict(row, order=True)), {}, summary),
                 (dict(kind='coldWebsiteProbeDiagnostic', value=row), {1: dict(row, payload={})}, summary),
                 (dict(kind='coldWebsiteProbeDiagnosticSummary', value=dict(summary, token='b'*32)), {}, summary)]
        for event, events, saved in cases:
            with self.subTest(event=event['kind']):
                with self.assertRaises(AssertionError): collect_cold_website_probe_event(event, events, saved)


if __name__ == '__main__': unittest.main()
