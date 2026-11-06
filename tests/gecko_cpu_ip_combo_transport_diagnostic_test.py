"""Strict diagnostic sidecar controls at explicit modeled collector boundaries."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

import gecko_cpu_ip_combo_runner_test as previous
import gecko_cpu_ip_combo_evidence_test as modeled

runner = previous.runner


class ComboTransportDiagnosticTests(unittest.TestCase):
    def fixture(self, failures=0, closed=True):
        report, _ = modeled.fixture()
        binding = report['routeReceipts']['binding']
        counts = {name: {stage: {} for stage in runner.TRANSPORT_STAGES} for name in runner.ROUTES}
        events = []
        if failures:
            counts['socks']['command']['ValueError'] = failures
            events = [dict(sequence=index, route='socks', protocol='socks5', stage='command', exceptionClass='ValueError', guardCode='other-guard', collectorClosed=False) for index in range(1, min(failures, 128) + 1)]
        value = dict(schema=1, kind='ip-timezone-transport-diagnostics-v1', binding=copy.deepcopy(binding),
                     collectorClosed=closed, quiescent=closed, eventLimit=128, totalFailures=failures,
                     recordedEvents=len(events), droppedEvents=failures-len(events), counts=counts, events=events)
        routes = copy.deepcopy(report['routeReceipts']); routes['errors']['socks'] = failures; routes['closed'] = closed
        return value, binding, routes

    def export(self, directory, value, binding, routes):
        class Collector:
            def diagnostic_snapshot(self):
                return copy.deepcopy(value)
        return runner.write_transport_diagnostic(directory, Collector(), binding, routes)

    def test_separate_bounded_sidecar_preserves_original_errors_and_has_no_qualification_claim(self):
        for failures in (0, 38, 128, 145):
            value, binding, routes = self.fixture(failures)
            original = copy.deepcopy((value, binding, routes))
            with self.subTest(failures=failures), tempfile.TemporaryDirectory() as folder:
                pin = self.export(folder, value, binding, routes)
                raw = Path(folder, runner.TRANSPORT_DIAGNOSTIC_NAME).read_bytes()
                exported = json.loads(raw)
                self.assertEqual(pin['bytes'], len(raw))
                self.assertTrue(exported['diagnosticOnly'])
                self.assertFalse(exported['qualificationEvidence'])
                self.assertEqual(exported['snapshot'], value)
                self.assertEqual(routes['errors']['socks'], failures)
                self.assertLess(len(raw), 262144)
            self.assertEqual((value, binding, routes), original)

    def test_unknown_raw_values_binding_changes_and_missing_fields_never_export(self):
        changes = [lambda v: v.update(rawError='PRIVATE DATA'),
                   lambda v: v['binding'].update(runNonce='f'*32),
                   lambda v: v.update(schema=True),
                   lambda v: v.update(quiescent=1),
                   lambda v: v.update(eventLimit=129),
                   lambda v: v['events'][0].update(host='private.example'),
                   lambda v: v['events'][0].update(exceptionClass='PRIVATE ERROR MESSAGE'),
                   lambda v: v['events'][0].update(guardCode='PRIVATE ERROR MESSAGE'),
                   lambda v: v['events'][0].update(stage='PRIVATE URL'),
                   lambda v: v['events'][0].update(sequence=True),
                   lambda v: v['counts']['socks']['command'].update(SecretException=1)]
        for index, change in enumerate(changes):
            value, binding, routes = self.fixture(1); change(value)
            with self.subTest(index=index), tempfile.TemporaryDirectory() as folder:
                with self.assertRaises(ValueError): self.export(folder, value, binding, routes)
                self.assertFalse(Path(folder, runner.TRANSPORT_DIAGNOSTIC_NAME).exists())
        value, binding, routes = self.fixture()
        for key in value:
            broken = copy.deepcopy(value); broken.pop(key)
            with self.subTest(missing=key), tempfile.TemporaryDirectory() as folder, self.assertRaises(ValueError):
                self.export(folder, broken, binding, routes)

    def test_nonquiescent_snapshot_is_explicit_and_bucket_or_error_counter_rewrites_are_rejected(self):
        value, binding, routes = self.fixture(1, closed=False)
        with tempfile.TemporaryDirectory() as folder:
            self.export(folder, value, binding, routes)
            self.assertFalse(json.loads(Path(folder, runner.TRANSPORT_DIAGNOSTIC_NAME).read_bytes())['snapshot']['quiescent'])
        for change in (lambda v, r: r['errors'].update(socks=0),
                       lambda v, r: r['binding'].update(runNonce='f'*32),
                       lambda v, r: r.update(closed=False),
                       lambda v, r: v['events'][0].update(stage='host'),
                       lambda v, r: v.update(totalFailures=0),
                       lambda v, r: v.update(droppedEvents=1),
                       lambda v, r: v.update(collectorClosed=False)):
            value, binding, routes = self.fixture(1); change(value, routes)
            with tempfile.TemporaryDirectory() as folder, self.assertRaises(ValueError):
                self.export(folder, value, binding, routes)
        value, binding, routes = self.fixture(1, closed=False)
        value['events'][0]['collectorClosed'] = True
        with tempfile.TemporaryDirectory() as folder, self.assertRaises(ValueError):
            self.export(folder, value, binding, routes)

    def test_actual_runner_exports_after_close_and_original_checker_failure_remains_a_failure(self):
        for condition in ('passed', 'checker'):
            boundary = previous.ComboRunnerTests(); self.addCleanup(boundary.doCleanups)
            report, actions, out, original, status, verify = boundary.execute_main(condition)
            self.assertEqual(len(verify), 1)
            self.assertEqual(status['status'], 'passed' if condition == 'passed' else 'failed')
            self.assertEqual(report['status'], 'passed', 'The actual device outcome remains original')
            value = json.loads((out/runner.TRANSPORT_DIAGNOSTIC_NAME).read_bytes())
            self.assertTrue(value['snapshot']['quiescent'])
            self.assertEqual(set(report['casePins']), set(runner.RAW_FILES))
            self.assertEqual((out/runner.RAW_DIRECTORY/'combo.json').read_bytes(), original)
            self.assertTrue(all(report['cleanup'].values()))

    def test_original_combo_zero_error_gate_still_rejects_every_route_error(self):
        report, expected = modeled.fixture()
        for route in runner.ROUTES:
            changed = copy.deepcopy(report); changed['routeReceipts']['errors'][route] = 1
            values = modeled.values(changed)
            with self.subTest(route=route), self.assertRaisesRegex(ValueError, 'fixture route errors'):
                modeled.gate.validate_behavior(changed, modeled.SOURCE, expected, values, modeled.modeled.source_reader)

    def test_actual_close_failure_exports_unquiesced_diagnostic_and_remains_failed(self):
        boundary = previous.ComboRunnerTests(); self.addCleanup(boundary.doCleanups)
        report, actions, out, original, status, verify = boundary.execute_main('server-close')
        diagnostic = json.loads((out/runner.TRANSPORT_DIAGNOSTIC_NAME).read_bytes())
        self.assertTrue(diagnostic['snapshot']['collectorClosed'])
        self.assertFalse(diagnostic['snapshot']['quiescent'])
        self.assertFalse(report['cleanup']['serverQuiesced'])
        self.assertEqual((report['status'], status['status'], verify), ('failed', 'failed', []))
        self.assertEqual((out/runner.RAW_DIRECTORY/'combo.json').read_bytes(), original)

    def test_independent_diagnostic_failure_fails_command_without_rewriting_device_outcome(self):
        boundary = previous.ComboRunnerTests(); self.addCleanup(boundary.doCleanups)
        report, actions, out, original, status, verify = boundary.execute_main('diagnostic')
        self.assertEqual((report['status'], status['status'], verify), ('passed', 'failed', []))
        self.assertEqual(status['errorType'], 'ValueError')
        self.assertTrue(all(report['cleanup'].values()))
        self.assertFalse((out/runner.TRANSPORT_DIAGNOSTIC_NAME).exists())
        self.assertEqual((out/runner.RAW_DIRECTORY/'combo.json').read_bytes(), original)


if __name__ == '__main__':
    unittest.main(verbosity=2)
