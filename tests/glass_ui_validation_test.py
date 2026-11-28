#!/usr/bin/env python3
"""Focused checks for acceptance decisions made from Android hierarchy bounds.

The fixtures represent native button touch regions, including the two-row
layout used when a narrow window cannot fit an independently centered dock.
They do not stand in for Android capture or visual inspection.
"""
import ast
import copy
import hashlib
import inspect
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools' / 'gecko'))
import capture_glass_navigation as capture
import glass_ui_validation as validation
import gecko_event_transfer_test as event_controls
from profile_event_journal_discovery_test import discovery_class


class ReturnedControlledGeckoDocumentTest(unittest.TestCase):
    package = 'local.pocketchat.test'

    def frame(self, fault=None):
        root = ET.Element('hierarchy')
        attrs = {'package': self.package, 'visible-to-user': 'true', 'bounds': '[0,313][1236,2418]'}
        native = ET.SubElement(root, 'node', {**attrs, 'class': 'android.widget.FrameLayout'})
        ET.SubElement(native, 'node', {**attrs, 'class': 'android.widget.Button', 'content-desc': '网页工具'})
        if fault != 'toolbar-only':
            web = ET.SubElement(native, 'node', {**attrs, 'class': 'android.webkit.WebView'})
            if fault == 'foreign-web':
                web.set('package', 'some.other.package')
            if fault == 'duplicate-view':
                native.append(copy.deepcopy(web))
            parent = ET.SubElement(native if fault == 'outside' else web, 'node', attrs)
            if fault == 'hidden-ancestor':
                parent.set('visible-to-user', 'false')
            if fault == 'foreign-ancestor':
                parent.set('package', 'some.other.package')
            node = ET.SubElement(parent, 'node', {**attrs, 'class': 'android.view.View',
                'text': 'Controlled long reading document', 'bounds': '[24,584][838,649]'})
            if fault == 'hidden-mark':
                node.set('visible-to-user', 'false')
            if fault == 'clipped-mark':
                node.set('bounds', '[24,2400][838,2450]')
            if fault == 'other-document':
                node.set('text', 'Different document')
            if fault == 'duplicate-marker':
                parent.append(copy.deepcopy(node))
        return ET.tostring(root, encoding='unicode')

    def test_owned_visible_controlled_document_is_required(self):
        self.assertTrue(validation.returned_controlled_gecko_document(self.frame(), self.package, capture.bounds))
        for fault in ('toolbar-only', 'foreign-web', 'duplicate-view', 'outside', 'hidden-ancestor',
                      'foreign-ancestor', 'hidden-mark', 'clipped-mark', 'other-document', 'duplicate-marker'):
            with self.subTest(fault=fault):
                self.assertFalse(validation.returned_controlled_gecko_document(self.frame(fault), self.package, capture.bounds))


class GlassDocumentEventDiscoveryTest(unittest.TestCase):
    """Exercise the actual glass consumer with explicit synthetic native bytes."""

    def observer(self, out, *, journal_changes=None, log=None, payload=None, pending=False, delays=None, contract=4):
        result = dict(command='ready', document='controlled', navigationContract=contract, applicationAcceptance=False)
        receipt, raw = event_controls.packet(
            event_controls.event('collapseSnapshot', result), fixtureAction='chromeCollapse')
        transfer = event_controls.transfer
        if payload is not None:
            raw = payload(raw)
        self.calls = []
        self.read_timeouts = []
        self.clock = 0
        journal = dict(schema=1, status='committed', runNonce='e' * 32, processSlot=0,
                       fixtureAction='chromeCollapse', command=7, receipts=[json.dumps(receipt)])
        journal.update(journal_changes or {})
        if pending:
            journal = dict(schema=1, status='pending', runNonce='e' * 32, processSlot=0)
        journal_raw = json.dumps(journal).encode()
        # A stale log is a real transport condition: it cannot supply this
        # invocation's current receipt, even if native publication succeeded.
        stale = dict(receipt, runNonce='f' * 32)
        log = (json.dumps(stale) + '\n').encode() if log is None else log

        def adb(*parts, timeout=None):
            self.calls.append(parts)
            if parts[0] == 'logcat':
                self.read_timeouts.append(('log', timeout))
                self.clock += (delays or {}).get('log', 0)
                return log
            if parts[:3] == ('exec-out', 'content', 'read'):
                if '/gecko-event-receipts/' in parts[-1]:
                    self.read_timeouts.append(('journal', timeout))
                    self.clock += (delays or {}).get('journal', 0)
                    return journal_raw
                self.read_timeouts.append(('payload', timeout))
                self.clock += (delays or {}).get('payload', 0)
                self.assertEqual(parts[-1], transfer.event_uri(receipt))
                return raw
            self.assertEqual(parts[:3], ('shell', 'am', 'broadcast'))
            return b'Broadcast completed'

        reader = transfer.EventTransfer(identity=event_controls.identity(), nonce='e' * 32,
            slot=0, action='chromeCollapse', fetch=lambda uri: adb('exec-out', 'content', 'read', '--uri', uri))
        discovery = discovery_class()(reader)
        def sleep(seconds):
            self.clock += seconds
        bindings = dict(adb=adb, package='local.pocketchat.test', args=SimpleNamespace(out=out),
            observations={'e' * 32: reader}, journals={'e' * 32: discovery},
            time=SimpleNamespace(monotonic=lambda: self.clock, sleep=sleep),
            parse_receipt_line=transfer.parse_receipt_line)
        source = ast.parse(inspect.getsource(validation.capture_acceptance_suite))
        suite = next(node for node in source.body if isinstance(node, ast.FunctionDef))
        observer = next(node for node in suite.body
                        if isinstance(node, ast.FunctionDef) and node.name == 'observed_event')
        exec(compile(ast.Module(body=[observer], type_ignores=[]), validation.__file__, 'exec'), bindings)
        self.case = dict(name='controlled', runNonce='e' * 32)
        return bindings['observed_event'], reader, result

    def test_committed_native_journal_survives_missing_log_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            observer, reader, expected = self.observer(Path(directory))
            self.assertEqual(observer(self.case, 'ready', request=False), expected)
            self.assertEqual(self.case['documentObservations']['ready'], expected)
            self.assertEqual(len(reader.records), 1)
            self.assertFalse(any(call[:3] == ('shell', 'am', 'broadcast') for call in self.calls))
            self.assertTrue((Path(directory) / 'controlled-event-receipts.json').is_file())

    def test_valid_native_transport_cannot_substitute_a_previous_navigation_contract(self):
        for contract in (None, 2, 3, '4', True):
            with self.subTest(contract=contract), tempfile.TemporaryDirectory() as directory:
                observer, reader, _ = self.observer(Path(directory), contract=contract)
                with self.assertRaisesRegex(ValueError, 'navigation contract 4'):
                    observer(self.case, 'ready', request=False)
                self.assertNotIn('documentObservations', self.case)
                self.assertEqual(len(reader.records), 1, 'Keep the original valid native payload even when its contract is rejected')

    def test_malformed_pending_publication_never_claims_ready(self):
        with tempfile.TemporaryDirectory() as directory:
            observer, reader, _ = self.observer(Path(directory), journal_changes={
                'status': 'pending', 'fixtureAction': None, 'command': None, 'receipts': []})
            # This is a malformed pending marker; native pending has only its
            # owner fields. It must fail closed, rather than becoming readiness.
            with self.assertRaises(ValueError):
                observer(self.case, 'ready', request=False)
            self.assertEqual(reader.records, [])
            self.assertNotIn('documentObservations', self.case)

    def test_pending_publication_keeps_the_original_deadline(self):
        with tempfile.TemporaryDirectory() as directory:
            observer, reader, _ = self.observer(Path(directory), pending=True)
            with self.assertRaises(TimeoutError):
                observer(self.case, 'ready', request=False)
            self.assertGreaterEqual(self.clock, 40)
            self.assertLess(self.clock, 40.3)
            self.assertEqual(reader.records, [])
            self.assertNotIn('documentObservations', self.case)

    def test_late_journal_cannot_extend_the_original_ready_deadline(self):
        with tempfile.TemporaryDirectory() as directory:
            observer, reader, _ = self.observer(Path(directory), delays={'journal': 41})
            original_fetch = reader.fetch
            with self.assertRaises(TimeoutError):
                observer(self.case, 'ready', request=False)
            self.assertEqual(reader.records, [])
            self.assertNotIn('documentObservations', self.case)
            self.assertIs(reader.fetch, original_fetch)

    def test_late_payload_cannot_extend_the_original_ready_deadline(self):
        with tempfile.TemporaryDirectory() as directory:
            observer, reader, _ = self.observer(Path(directory), delays={'payload': 41})
            original_fetch = reader.fetch
            with self.assertRaises(TimeoutError):
                observer(self.case, 'ready', request=False)
            self.assertEqual(reader.records, [])
            self.assertNotIn('documentObservations', self.case)
            self.assertIs(reader.fetch, original_fetch)

    def test_all_native_reads_share_one_remaining_budget_and_restore_fetch(self):
        with tempfile.TemporaryDirectory() as directory:
            observer, reader, expected = self.observer(Path(directory),
                delays={'log': 7, 'journal': 9, 'payload': 11})
            original_fetch = reader.fetch
            self.assertEqual(observer(self.case, 'ready', request=False), expected)
            self.assertEqual(self.read_timeouts, [('log', 40), ('journal', 33), ('payload', 24)])
            self.assertEqual(self.clock, 27)
            self.assertIs(reader.fetch, original_fetch)

    def test_foreign_owner_command_and_digest_are_not_repaired_from_payload(self):
        for changes in ({'runNonce': 'f' * 32}, {'processSlot': 1},
                        {'fixtureAction': 'other'}, {'command': 8}):
            with self.subTest(changes=changes), tempfile.TemporaryDirectory() as directory:
                observer, reader, _ = self.observer(Path(directory), journal_changes=changes)
                with self.assertRaises(ValueError):
                    observer(self.case, 'ready', request=False)
                self.assertEqual(reader.records, [])
        with tempfile.TemporaryDirectory() as directory:
            observer, reader, _ = self.observer(Path(directory), payload=lambda raw: raw[:-1])
            with self.assertRaisesRegex(ValueError, 'payload length'):
                observer(self.case, 'ready', request=False)
            self.assertEqual(reader.records, [])

    def test_native_publication_error_and_android_crash_cannot_be_hidden_by_journal(self):
        error = dict(kind='eventTransportError', runNonce='e' * 32, processSlot=0)
        for log in ((json.dumps(error) + '\n').encode(), b'FATAL EXCEPTION: main\n'):
            with self.subTest(log=log), tempfile.TemporaryDirectory() as directory:
                observer, reader, _ = self.observer(Path(directory), log=log)
                with self.assertRaises(ValueError):
                    observer(self.case, 'ready', request=False)
                self.assertEqual(reader.records, [])


class GlassReadyFailureDiagnosticsTest(unittest.TestCase):
    def setUp(self):
        path = Path(__file__).parent / 'fixtures/glass-ready-failure-api32.json'
        self.fixture = json.loads(path.read_text())
        self.identity = {key: self.fixture[key] for key in ('sourceCommit', 'sourceTree')}
        self.case = dict(self.fixture['case'])

    def trace(self, sequence=1):
        # Explicit synthetic native boundary; this is not a captured device success.
        result = dict(self.identity, schema=1, sequence=sequence, runNonce=self.case['runNonce'],
                      stage='waiting', diagnosticOnly=True)
        for key in ('checkpointReady', 'runtimePresent', 'extensionPresent', 'identityPrepared',
                    'routePrepared', 'privacyReady', 'ready', 'failed', 'destroyed', 'resourceDeferred',
                    'sessionPresent', 'surfacePresent', 'portPresent', 'usable', 'queuedTarget',
                    'routePortPresent', 'guardBlocked', 'networkReady', 'browserPaused', 'uiVisible', 'navigating',
                    'addonDisabled', 'metadataEnabled'):
            result[key] = False
        for key in ('elapsedMs', 'requestedProtection', 'protectionRequest', 'protectionLevel',
                    'documents', 'readyEvaluations', 'readyCallbacks', 'snapshotEvaluations',
                    'snapshotCallbacks', 'eventSequence', 'routeCalls', 'fixtureRoutes', 'blockedRoutes', 'otherRoutes',
                    'routeDelegateInstalls', 'routeConnectAttempts'):
            result[key] = 0
        return result

    def parse(self, rows):
        raw = ('\n'.join(json.dumps(row) for row in rows) + '\n').encode()
        return validation.collapse_start_trace(raw, self.identity, self.case['runNonce'])

    def test_original_api32_timeout_has_no_startup_evidence_to_promote(self):
        raw = self.fixture['originalEvents']['text'].encode()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), self.fixture['originalEvents']['sha256'])
        self.assertEqual(self.fixture['runId'], 43155512845)
        self.assertFalse(self.fixture['launchStdoutRetained'])
        self.assertEqual(self.fixture['fixtureRequestCount'], 0)
        self.assertEqual(self.case['errorType'], 'TimeoutError')
        self.assertEqual(validation.collapse_start_trace(raw, self.identity, self.case['runNonce']), ([], b''))

    def test_current_nonce_source_and_original_trace_lines_are_retained(self):
        first, second = self.trace(), self.trace(3)
        unrelated = dict(first, runNonce='f' * 32, draft='private data must not be retained')
        records, raw = self.parse([unrelated, first, second])
        self.assertEqual(records, [first, second])
        self.assertEqual(raw, (json.dumps(first) + '\n' + json.dumps(second) + '\n').encode())
        self.assertNotIn(b'private', raw)

    def test_wrong_identity_malformed_state_and_content_fields_are_rejected(self):
        changes = ({'sourceCommit': '0' * 40}, {'sourceTree': '0' * 40}, {'diagnosticOnly': False},
                   {'runtimePresent': 1}, {'routeCalls': '1'}, {'elapsedMs': 1.5}, {'sequence': True},
                   {'sequence': 81}, {'stage': 'unowned'}, {'stage': []}, {'pageUrl': 'https://private.invalid/'},
                   {'state': {'draft': 'private'}}, {'unlistedCounter': 1})
        for change in changes:
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.parse([dict(self.trace(), **change)])
        missing = self.trace(); del missing['runtimePresent']
        with self.assertRaises(ValueError):
            self.parse([missing])
        for raw in (b'\xff', b'x' * (1024 * 1024 + 1)):
            with self.assertRaises((ValueError, UnicodeError)):
                validation.collapse_start_trace(raw, self.identity, self.case['runNonce'])

    def test_duplicate_or_reversed_trace_sequences_cannot_be_combined(self):
        for rows in ([self.trace(), self.trace()], [self.trace(2), self.trace()]):
            with self.assertRaises(ValueError):
                self.parse(rows)

    def collect(self, path, raw_trace, activity, *, launch=b'Controlled synthetic am output\n'):
        calls = []
        def adb(*command, **kwargs):
            calls.append((command, kwargs))
            value = raw_trace if command[0] == 'logcat' else activity
            if isinstance(value, Exception):
                raise value
            return value
        result = validation.capture_ready_failure(path, self.case, self.identity, adb, launch)
        self.assertEqual(len(calls), 3)
        self.assertTrue(all(kwargs == {'timeout': 6} for _, kwargs in calls))
        self.assertTrue(all('start' not in command and 'broadcast' not in command for command, _ in calls))
        return result

    def test_post_failure_capture_keeps_only_native_counters_and_resumed_lines(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory); line = self.fixture['initialActivity']['resumedLines'][0]
            raw_trace = (json.dumps(self.trace()) + '\n').encode()
            activity = ('Intent { data=https://private.invalid/ }\n' + line + '\n').encode()
            result = self.collect(path, raw_trace, activity)
            self.assertEqual(result['status'], 'captured')
            self.assertTrue(result['readyGateAlreadyFailed'])
            self.assertFalse(result['applicationAcceptance'])
            self.assertEqual(self.case['status'], 'failed')
            self.assertEqual(self.case['error'], self.fixture['case']['error'])
            self.assertEqual((path / result['launchOutput']['file']).read_bytes(), b'Controlled synthetic am output\n')
            self.assertEqual((path / result['nativeTrace']['file']).read_bytes(), raw_trace)
            self.assertEqual((path / result['resumedActivity']['file']).read_text(), line + '\n')
            self.assertFalse(any(b'private.invalid' in p.read_bytes() for p in path.iterdir()))

    def test_absent_trace_or_resumed_component_remains_incomplete(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.collect(Path(directory), self.fixture['originalEvents']['text'].encode(), b'no resumed component\n')
            self.assertEqual(result['status'], 'incomplete')
            self.assertEqual(result['nativeTrace']['status'], 'missing')
            self.assertEqual(result['resumedActivity']['status'], 'missing')
            self.assertEqual(self.case['errorType'], 'TimeoutError')

    def test_diagnostic_transport_and_launch_boundary_failures_do_not_retry_or_clear_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.collect(Path(directory), TimeoutError('trace unavailable'),
                                  OSError('activity unavailable'), launch=b'x' * 16385)
            self.assertEqual(result['status'], 'incomplete')
            self.assertEqual([row['stage'] for row in result['errors']],
                             ['launch-output', 'native-trace', 'gecko-startup-log', 'resumed-activity'])
            self.assertEqual(self.case['status'], 'failed')
            self.assertEqual(self.case['error'], self.fixture['case']['error'])

    def ready_boundary(self):
        # Execute the actual call boundary in the suite, with only its transport
        # and observer substituted. This does not simulate an Android success.
        tree = ast.parse(inspect.getsource(validation.capture_acceptance_suite))
        matches = [node for node in ast.walk(tree) if isinstance(node, ast.Try)
                   and len(node.body) == 1 and isinstance(node.body[0], ast.Expr)
                   and isinstance(node.body[0].value, ast.Call)
                   and isinstance(node.body[0].value.func, ast.Name)
                   and node.body[0].value.func.id == 'observed_event'
                   and len(node.body[0].value.args) == 2
                   and isinstance(node.body[0].value.args[1], ast.Constant)
                   and node.body[0].value.args[1].value == 'ready']
        self.assertEqual(len(matches), 1)
        return compile(ast.Module(body=matches, type_ignores=[]),
                       validation.__file__, 'exec')

    def test_collector_top_level_failure_preserves_the_actual_ready_error(self):
        ready_error = TimeoutError(self.case['error'])
        observer = MagicMock(side_effect=ready_error)
        collector = MagicMock(side_effect=OSError('controlled collector failure'))
        namespace = dict(case=self.case, identity=self.identity, args=SimpleNamespace(out=Path('unused')),
                         adb=MagicMock(), start_output=b'started', observed_event=observer,
                         capture_ready_failure=collector)
        with self.assertRaises(TimeoutError) as caught:
            exec(self.ready_boundary(), namespace)
        self.assertIs(caught.exception, ready_error)
        observer.assert_called_once_with(self.case, 'ready', request=False)
        collector.assert_called_once_with(namespace['args'].out, self.case, self.identity,
                                          namespace['adb'], b'started')
        self.assertEqual(self.case['error'], self.fixture['case']['error'])
        self.assertEqual(self.case['status'], 'failed')
        self.assertEqual(self.case['readyFailureDiagnostics']['errors'], [dict(
            stage='diagnostic-collector', errorType='OSError', error='controlled collector failure')])
        namespace['adb'].assert_not_called()

    def test_successful_ready_observation_has_no_failure_diagnostic_side_effects(self):
        observer, collector = MagicMock(), MagicMock()
        namespace = dict(case=self.case, identity=self.identity, args=SimpleNamespace(out=Path('unused')),
                         adb=MagicMock(), start_output=b'started', observed_event=observer,
                         capture_ready_failure=collector)
        exec(self.ready_boundary(), namespace)
        observer.assert_called_once_with(self.case, 'ready', request=False)
        collector.assert_not_called()
        namespace['adb'].assert_not_called()
        self.assertNotIn('readyFailureDiagnostics', self.case)


def hierarchy(boxes, *, selected=None, extra=None, labels=None):
    root = ET.Element('hierarchy', rotation='0')
    frame = ET.SubElement(root, 'node', {
        'package': capture.PACKAGE,
        'class': 'android.widget.FrameLayout',
        'bounds': f'[0,0][{capture.WIDTH},{capture.HEIGHT}]',
    })
    for label, (left, top, right, bottom) in zip(capture.LABELS if labels is None else labels, boxes):
        ET.SubElement(frame, 'node', {
            'package': capture.PACKAGE,
            'class': 'android.widget.Button',
            'text': label,
            'clickable': 'true',
            'enabled': 'true',
            'visible-to-user': 'true',
            'selected': 'true' if label == selected else 'false',
            'bounds': f'[{left},{top}][{right},{bottom}]',
        })
    if extra:
        ET.SubElement(frame, 'node', extra)
    return ET.tostring(root, encoding='unicode')


class GlassNavigationGeometryTest(unittest.TestCase):
    def setUp(self):
        self.display = capture.WIDTH, capture.HEIGHT, capture.DENSITY
        capture.set_display(1236, 2676, 480)
        self.row = [(288, 2328, 508, 2520), (508, 2328, 728, 2520),
                    (728, 2328, 948, 2520), (984, 2328, 1176, 2520)]
        self.workspace = [(78 + index * 216, 2328, 78 + (index + 1) * 216, 2520)
                          for index in range(5)]

    def tearDown(self):
        capture.set_display(*self.display)

    def test_centered_three_item_group_has_its_own_axis(self):
        result = capture.navigation_geometry(hierarchy(self.row))
        self.assertTrue(result['valid'])
        self.assertEqual(result['threeItemGroupCenter'][0], 618)
        self.assertEqual(result['readingLayout'], 'same-row')
        self.assertEqual(result['minimumTouchTargetPx'], 144)
        self.assertIsNotNone(capture.navigation(hierarchy(self.row)))

    def test_narrow_window_allows_reading_below_and_to_the_right(self):
        capture.set_display(960, 1920, 480)
        stacked = [(150, 1452, 370, 1644), (370, 1452, 590, 1644),
                   (590, 1452, 810, 1644), (720, 1668, 912, 1860)]
        result = capture.navigation_geometry(hierarchy(stacked))
        self.assertTrue(result['valid'])
        self.assertEqual(result['readingLayout'], 'stacked-right')
        self.assertTrue(result['checks']['readingSeparateToRight'])
        self.assertLess(stacked[-1][0], stacked[-2][2])

    def test_reading_cannot_cover_a_destination(self):
        self.row[-1] = (816, 2328, 1008, 2520)
        result = capture.navigation_geometry(hierarchy(self.row))
        self.assertFalse(result['valid'])
        self.assertFalse(result['checks']['readingSeparateToRight'])

    def test_stacked_reading_cannot_overlap_vertically(self):
        capture.set_display(960, 1920, 480)
        stacked = [(150, 1452, 370, 1644), (370, 1452, 590, 1644),
                   (590, 1452, 810, 1644), (720, 1600, 912, 1792)]
        self.assertFalse(capture.navigation_geometry(hierarchy(stacked))['valid'])

    def test_stacked_reading_stays_on_the_right(self):
        capture.set_display(960, 1920, 480)
        stacked = [(150, 1452, 370, 1644), (370, 1452, 590, 1644),
                   (590, 1452, 810, 1644), (48, 1668, 240, 1860)]
        self.assertFalse(capture.navigation_geometry(hierarchy(stacked))['valid'])

    def test_centering_does_not_include_reading_button(self):
        shifted = [(left - 70, top, right - 70, bottom)
                   for left, top, right, bottom in self.row]
        result = capture.navigation_geometry(hierarchy(shifted))
        self.assertFalse(result['valid'])
        self.assertFalse(result['checks']['threeItemGroupCentered'])

    def test_three_destinations_cannot_form_a_staircase(self):
        self.row[1] = (508, 2160, 728, 2352)
        self.assertFalse(capture.navigation_geometry(hierarchy(self.row))['valid'])

    def test_reading_circle_keeps_a_square_touch_region(self):
        self.row[-1] = (984, 2328, 1176, 2490)
        result = capture.navigation_geometry(hierarchy(self.row))
        self.assertFalse(result['valid'])
        self.assertFalse(result['checks']['readingIsSquare'])

    def test_tiny_target_cannot_pass_from_other_geometry(self):
        self.row[0] = (288, 2328, 408, 2520)
        result = capture.navigation_geometry(hierarchy(self.row))
        self.assertFalse(result['valid'])
        self.assertFalse(result['checks']['minimumTouchTargets'])

    def test_duplicate_visible_action_is_ambiguous(self):
        duplicate = {'package': capture.PACKAGE, 'class': 'android.widget.Button',
                     'text': '网络', 'clickable': 'true', 'enabled': 'true',
                     'bounds': '[10,10][180,180]'}
        self.assertIsNone(capture.navigation_geometry(hierarchy(self.row, extra=duplicate)))

    def test_offscreen_action_cannot_become_a_successful_observation(self):
        self.row[-1] = (1100, 2328, 1292, 2520)
        self.assertIsNone(capture.navigation_geometry(hierarchy(self.row)))
        self.assertIsNone(capture.bounds(ET.Element('node', bounds='[0,0][1237,200]')))

    def test_navigation_selection_must_match_observed_route(self):
        for selected in ('环境', '下载', '网络', '设置'):
            xml = hierarchy(self.workspace, labels=capture.WORKSPACE_LABELS, selected=selected)
            with self.subTest(selected=selected):
                self.assertTrue(capture.selected_navigation(xml, selected))
                for wrong in capture.WORKSPACE_LABELS:
                    if wrong != selected:
                        self.assertFalse(capture.selected_navigation(xml, wrong))
                self.assertIsNone(capture.navigation(xml))
                result = capture.observed_navigation_geometry(xml)
                self.assertEqual(result['layout'], 'workspace-five')
                self.assertTrue(result['valid'])
                self.assertEqual(result['groupLabels'], ['浏览器', '环境', '下载', '网络', '设置'])
                self.assertNotIn('阅读', result['bounds'])

    def test_only_unselected_compact_actions_identify_the_conversation(self):
        xml = hierarchy(self.row)
        self.assertIsNotNone(capture.navigation(xml))
        result = capture.observed_navigation_geometry(xml)
        self.assertEqual(result['layout'], 'conversation-split')
        self.assertTrue(result['valid'])
        for selected in capture.LABELS:
            with self.subTest(selected=selected):
                wrong = hierarchy(self.row, selected=selected)
                self.assertIsNone(capture.navigation(wrong))
                self.assertFalse(capture.selected_navigation(wrong, selected))
                self.assertFalse(capture.selected_navigation(xml, selected))

    def test_workspace_requires_one_selected_destination(self):
        xml = hierarchy(self.workspace, labels=capture.WORKSPACE_LABELS)
        for label in capture.WORKSPACE_LABELS:
            self.assertFalse(capture.selected_navigation(xml, label))
        root = ET.fromstring(hierarchy(self.workspace, labels=capture.WORKSPACE_LABELS, selected='环境'))
        for node in root.iter('node'):
            if node.get('text') == '网络':
                node.set('selected', 'true')
        xml = ET.tostring(root, encoding='unicode')
        self.assertFalse(capture.selected_navigation(xml, '环境'))
        self.assertFalse(capture.selected_navigation(xml, '网络'))

    def test_native_workspace_cannot_retain_a_reading_action(self):
        reading = {'package': capture.PACKAGE, 'class': 'android.widget.Button',
                   'text': '阅读', 'clickable': 'true', 'enabled': 'true',
                   'bounds': '[984,2088][1176,2280]'}
        xml = hierarchy(self.workspace, labels=capture.WORKSPACE_LABELS, selected='网络', extra=reading)
        result = capture.workspace_navigation_geometry(xml)
        self.assertFalse(result['valid'])
        self.assertFalse(result['checks']['readingAbsent'])
        self.assertFalse(capture.selected_navigation(xml, '网络'))
        self.assertIsNone(capture.observed_navigation_geometry(xml))

    def test_unequal_native_columns_cannot_pass_route_admission(self):
        self.workspace[2] = (510, 2328, 700, 2520)
        xml = hierarchy(self.workspace, labels=capture.WORKSPACE_LABELS, selected='下载')
        result = capture.observed_navigation_geometry(xml)
        self.assertEqual(result['layout'], 'workspace-five')
        self.assertFalse(result['checks']['equalColumns'])
        self.assertFalse(capture.selected_navigation(xml, '下载'))


class GlassLoadingActionsGeometryTest(unittest.TestCase):
    """Synthetic hierarchy cases for short-window clipping decisions only."""

    def setUp(self):
        self.display = capture.WIDTH, capture.HEIGHT, capture.DENSITY
        capture.set_display(2676, 1236, 480)
        self.actions = [('检查网络', (720, 624, 1320, 792)),
                        ('重新加载', (1356, 624, 1956, 792))]
        self.nav = [(1008, 924, 1228, 1116), (1228, 924, 1448, 1116),
                    (1448, 924, 1668, 1116), (2424, 924, 2616, 1116)]

    def tearDown(self):
        capture.set_display(*self.display)

    def xml(self, *, actions=None, cover=(0, 276, 2676, 900),
            scroll=(84, 300, 2592, 864), capsule=(1050, 90, 1626, 246), nav=None):
        actions = self.actions if actions is None else actions
        nav = self.nav if nav is None else nav
        root = ET.Element('hierarchy', rotation='0')

        def view(parent, kind, box, **extra):
            left, top, right, bottom = box
            attrs = {'package': capture.PACKAGE, 'class': 'android.widget.' + kind,
                     'bounds': f'[{left},{top}][{right},{bottom}]',
                     'visible-to-user': 'true'}
            attrs.update(extra)
            return ET.SubElement(parent, 'node', attrs)

        frame = view(root, 'FrameLayout', (0, 0, capture.WIDTH, capture.HEIGHT))
        header = view(frame, 'LinearLayout', (0, 72, 2676, 276))
        view(header, 'Button', capsule, clickable='true', enabled='true',
             **{'content-desc': '当前环境：日常会话，点按切换环境', 'long-clickable': 'false'})
        loading = view(frame, 'LinearLayout', cover, clickable='true')
        overflow = view(loading, 'ScrollView', scroll, scrollable='true')
        content = view(overflow, 'LinearLayout', (636, 324, 2040, 840))
        view(content, 'TextView', (720, 324, 1956, 396), text='等待 VPN 连接')
        view(content, 'TextView', (636, 420, 2040, 516), text='网页联网已暂停。')
        boxes = [box for _, box in actions]
        row_box = (min(box[0] for box in boxes), min(box[1] for box in boxes),
                   max(box[2] for box in boxes), max(box[3] for box in boxes))
        row = view(content, 'LinearLayout', row_box)
        for label, box in actions:
            view(row, 'Button', box, text=label, clickable='true', enabled='true')
        view(content, 'TextView', (720, 810, 1956, 840), text='点按底部网址栏输入网址，点按顶部切换环境')
        for label, box in zip(capture.LABELS, nav):
            view(frame, 'Button', box, text=label, clickable='true', enabled='true', selected='false')
        return ET.tostring(root, encoding='unicode')

    def invalid(self, xml):
        result = validation.loading_actions_geometry(xml, capture.__dict__)
        self.assertIsNotNone(result)
        self.assertFalse(result['valid'])

    def test_horizontal_actions_fit_their_scroll_view_above_the_dock(self):
        result = validation.loading_actions_geometry(self.xml(), capture.__dict__)
        self.assertIsNotNone(result)
        self.assertTrue(result['valid'])
        self.assertIsInstance(result['checks'], dict)
        self.assertIsInstance(result['bounds'], dict)

    def test_full_screen_button_bounds_do_not_override_scroll_view_clipping(self):
        self.invalid(self.xml(scroll=(84, 300, 1800, 864)))

    def test_actions_must_fit_the_cover_as_well_as_the_scroll_view(self):
        self.invalid(self.xml(cover=(0, 276, 2676, 760)))

    def test_horizontal_actions_cannot_overlap(self):
        self.invalid(self.xml(actions=[self.actions[0], ('重新加载', (1290, 624, 1890, 792))]))

    def test_diagonally_crossing_buttons_cannot_pass_as_a_horizontal_row(self):
        self.invalid(self.xml(actions=[self.actions[0], ('重新加载', (1290, 650, 1890, 818))]))

    def test_stacked_buttons_are_rejected_even_when_both_fit_the_cover(self):
        self.invalid(self.xml(actions=[('检查网络', (1038, 480, 1638, 648)),
                                       ('重新加载', (1038, 672, 1638, 840))]))

    def test_portrait_requires_an_actual_tall_viewport_and_a_full_native_stack(self):
        stacked=self.xml(actions=[('检查网络', (1038, 480, 1638, 648)),
                                  ('重新加载', (1100, 672, 1576, 840))])
        self.assertFalse(validation.loading_actions_geometry(stacked,capture.__dict__,portrait=True)['valid'])
        capture.set_display(2676,5352,480)
        stacked=self.xml(actions=[('检查网络', (1038, 480, 1638, 648)),
                                  ('重新加载', (1100, 672, 1576, 840))])
        self.assertTrue(validation.loading_actions_geometry(stacked,capture.__dict__,portrait=True)['valid'])
        self.assertFalse(validation.loading_actions_geometry(self.xml(),capture.__dict__,portrait=True)['valid'])
        clipped=self.xml(scroll=(84,300,2592,790),actions=[('检查网络',(1038,480,1638,648)),
                                                         ('重新加载',(1100,672,1576,840))])
        self.assertFalse(validation.loading_actions_geometry(clipped,capture.__dict__,portrait=True)['valid'])

    def test_sideways_control_handoff_accepts_only_resumed_production_activity(self):
        from contextlib import nullcontext
        import portrait_orientation
        capture.set_display(2676,5352,480)
        xml=self.xml(actions=[('检查网络',(1038,480,1638,648)),('重新加载',(1100,672,1576,840))])
        pkg=capture.PACKAGE
        main=pkg+'/local.pocketchat.MainActivity'
        raw=(f'Display: mDisplayId=0\n  init=1236x2676 480dpi base=2676x5352 480dpi cur=2676x5352\n'
             ' InsetsSource type=statusBars frame=[0,0][2676,72] visible=true\n'
             ' InsetsSource type=navigationBars frame=[0,5260][2676,5352] visible=true\n').encode()
        def adb(*parts,**options):
            if parts[:1]==('shell',) and len(parts)==2 and 'wm help' in parts[1]:
                return b'Window manager commands:\n  user-rotation [-d DISPLAY_ID] [free|lock] [rotation]\n'
            if parts==('shell','dumpsys','activity','activities'):
                return ('topResumedActivity=ActivityRecord{token u0 '+main+' t72}').encode()
            if parts==('shell','dumpsys','window','displays'):return raw
            return b''
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder)
            def wait(capture_reader,predicate,stem,seconds):
                self.assertTrue(predicate(xml));(out/(stem+'.xml')).write_text(xml);return xml
            for owner,expected in [(main,'verified'),(pkg+'/local.pocketchat.UiVisualIntegrationActivity','failed')]:
                observed=dict(component=owner,orientation='portrait',userRotation='1',accelerometerRotation='0',
                              bounds=[0,0,2676,5352],activityConfig='mCurrentConfig={ port mBounds=Rect(0, 0 - 2676, 5352) }')
                report=dict(buildIdentity=dict(sourceCommit='source',sourceTree='tree'),installedApk={'sha256':'apk'},runNonce='run')
                with self.subTest(owner=owner), patch.object(portrait_orientation,'rotation_challenge',return_value=nullcontext({'controlLandscape':'fixture'})), patch.object(portrait_orientation,'observe',return_value=observed):
                    result=validation.capture_portrait_rotation(SimpleNamespace(out=out),report,None,adb,wait,
                        lambda name:(out/name).write_bytes(b'model screenshot'),capture.__dict__)
                    self.assertEqual(result['status'],expected,result)
                    if expected=='verified':
                        self.assertTrue(result['loadingActions']['checks']['portraitVerticalStack'])
                        self.assertTrue((out/result['png']['file']).is_file())
                    else:
                        self.assertIn('real MainActivity',result['error'])

    def test_valid_navigation_cannot_cover_loading_actions(self):
        nav = [(left, top - 204, right, bottom - 204) for left, top, right, bottom in self.nav]
        self.assertTrue(capture.navigation_geometry(self.xml(nav=nav))['valid'])
        self.invalid(self.xml(nav=nav))

    def test_short_buttons_cannot_pass_from_other_valid_geometry(self):
        actions = [(label, (left, top, right, top + 120))
                   for label, (left, top, right, _) in self.actions]
        self.invalid(self.xml(actions=actions))

    def test_observed_system_bar_cannot_cover_loading_actions(self):
        result = validation.loading_actions_geometry(self.xml(), capture.__dict__,
                                                      [(0, 750, 2676, 850)])
        self.assertIsNotNone(result)
        self.assertFalse(result['valid'])

    def test_exact_native_action_labels_are_required(self):
        changed = [('检查线路', self.actions[0][1]), self.actions[1]]
        self.assertIsNone(validation.loading_actions_geometry(self.xml(actions=changed), capture.__dict__))

    def test_duplicate_native_action_is_not_an_unambiguous_observation(self):
        duplicate = self.actions + [('检查网络', (720, 432, 1320, 600))]
        self.assertIsNone(validation.loading_actions_geometry(self.xml(actions=duplicate), capture.__dict__))

    def test_action_outside_the_logical_screen_cannot_be_accepted(self):
        outside = [self.actions[0], ('重新加载', (2400, 624, 2800, 792))]
        self.assertIsNone(validation.loading_actions_geometry(self.xml(actions=outside), capture.__dict__))

    def test_top_capsule_cannot_cover_the_actions(self):
        self.invalid(self.xml(capsule=(1050, 600, 1626, 756)))

    def test_capsule_and_navigation_must_keep_their_independent_centers(self):
        self.invalid(self.xml(capsule=(1110, 90, 1686, 246)))
        shifted = [(left + 30, top, right + 30, bottom) for left, top, right, bottom in self.nav]
        self.invalid(self.xml(nav=shifted))


class GlassSystemBarSourcesTest(unittest.TestCase):
    """Parse retained Android inset-source text without inventing absent bars."""

    def test_reads_api32_itype_sources(self):
        raw = ('  InsetsSourceControl: {mType=ITYPE_STATUS_BAR mLeash=Surface(name=StatusBar)}\n'
               '  InsetsSource: {mType=ITYPE_STATUS_BAR mFrame=[0,0][2676,72] mVisible=true}\n'
               '  InsetsSource: {mType=ITYPE_NAVIGATION_BAR mFrame=[0,1164][2676,1236] mVisible=true}\n')
        result = validation.system_bar_sources(raw)
        self.assertEqual(result['statusBars'], [{'bounds': [0, 0, 2676, 72], 'visible': True}])
        self.assertEqual(result['navigationBars'], [{'bounds': [0, 1164, 2676, 1236], 'visible': True}])

    def test_reads_api35_named_sources_and_preserves_hidden_bar_observation(self):
        raw = ('  InsetsSource: {47d00001 type=statusBars frame=[0,0][2676,72] visible=true}\n'
               '  InsetsSource: {47d00002 type=navigationBars frame=[0,1164][2676,1236] visible=false}\n')
        result = validation.system_bar_sources(raw)
        self.assertEqual(result['statusBars'], [{'bounds': [0, 0, 2676, 72], 'visible': True}])
        self.assertEqual(result['navigationBars'], [{'bounds': [0, 1164, 2676, 1236], 'visible': False}])

    def test_missing_source_type_frame_or_visibility_cannot_prove_safe_area(self):
        status = 'InsetsSource: {type=statusBars frame=[0,0][2676,72] visible=true}\n'
        incomplete = (
            '',
            status,
            status + 'InsetsSource: {type=navigationBars frame=[0,1164][2676,1236]}\n',
            status + 'InsetsSource: {type=navigationBars visible=true}\n',
            'InsetsSource: {type=unrecognized frame=[0,0][2676,72] visible=true}\n',
        )
        for raw in incomplete:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                validation.system_bar_sources(raw)


class GlassFrameObservationTest(unittest.TestCase):
    def test_reads_actual_cumulative_counter_without_fps_inference(self):
        raw = ('Applications Graphics Acceleration Info:\n'
               '** Graphics info for pid 741 [local.pocketchat.test] **\n'
               'Stats since: 53118741ns\n'
               'Total frames rendered: 432\n'
               'Janky frames: 0 (0.00%)\n')
        self.assertEqual(validation.total_frames(raw), 432)

    def test_zero_frames_is_a_valid_idle_counter(self):
        self.assertEqual(validation.total_frames('  Total frames rendered: 0\r\n'), 0)

    def test_missing_malformed_or_multiple_counters_cannot_pass_idle_check(self):
        for raw in ('Janky frames: 0\n',
                    'Total frames rendered: -1\n',
                    'Total frames rendered: 43 (approximate)\n',
                    'Total frames rendered: 11\nTotal frames rendered: 7\n'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                validation.total_frames(raw)


class GlassCaptureCoverageTest(unittest.TestCase):
    def test_portrait_contract_keeps_every_supported_upright_configuration(self):
        self.assertEqual({c[0] for c in validation.PORTRAIT_CONFIGURATIONS},
                         {'default-light','enlarged-light','narrow-light','default-dark','enlarged-dark','safearea-light'})
        self.assertEqual(validation.PORTRAIT_CONFIGURATIONS,tuple(c for c in validation.CONFIGURATIONS if c[1]<c[2]))

    def test_configurations_cover_required_layout_and_appearance_conditions(self):
        configurations = validation.CONFIGURATIONS
        names = [row[0] for row in configurations]
        self.assertEqual(len(names), len(set(names)), 'Artifact stems must identify one case')
        for night in ('no', 'yes'):
            cases = [row for row in configurations if row[4] == night]
            with self.subTest(night=night):
                self.assertTrue(any(width < height and scale == 1.0
                                    for _, width, height, scale, _ in cases))
                self.assertTrue(any(scale >= 1.3 for _, _, _, scale, _ in cases))
        self.assertTrue(any(width < 360 and scale >= 1.4
                            for _, width, _, scale, _ in configurations),
                        'A narrow enlarged-text case must exercise the stacked layout')
        self.assertTrue(any(width > height for _, width, height, _, _ in configurations),
                        'A real landscape configuration is required')


class GlassUrlKeyboardInteractionTest(unittest.TestCase):
    """Actual interaction functions with a model of the observed API32 IME move."""

    # Original API32 run 43732281389: url-keyboard XML and the nine succeeding
    # dumps disagree because the IME moved the dialog before the old tap.
    BEFORE_IME = (1978, 408, 2242, 552)
    AFTER_IME = (1978, 297, 2242, 441)

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.out = Path(directory.name)
        display = patch.multiple(capture, WIDTH=2676, HEIGHT=1236)
        display.start()
        self.addCleanup(display.stop)

    def editor(self, box=AFTER_IME, *, missing=False, duplicate=False, title='打开网址', **attributes):
        root = ET.Element('hierarchy', screen='editor')
        common = {'package': capture.PACKAGE, 'visible-to-user': 'true'}
        ET.SubElement(root, 'node', dict(common, text=title, bounds='[140,180][550,260]'))
        if not missing:
            left, top, right, bottom = box
            values = dict(common, text='取消', bounds=f'[{left},{top}][{right},{bottom}]',
                          enabled='true', clickable='true')
            values['class'] = 'android.widget.Button'
            values.update(attributes)
            ET.SubElement(root, 'node', values)
            if duplicate:
                ET.SubElement(root, 'node', values)
        return ET.tostring(root, encoding='unicode')

    def run_interaction(self, *, current=None, shown=True, ime_seconds=2, read_error=None,
                        late_return=False):
        class BoundaryReached(Exception):
            pass

        clock = SimpleNamespace(value=0)
        report = dict(inputs=[])
        case = dict(name='landscape-light', observations={},
                    documentObservations={'ready': dict(visibleDocument=True, loadingCoverVisibility=8)})
        state = dict(editor=False, ime=False, currentReads=0, deadlines=[], events=[], cancelled=False)
        chat_xml = ('<hierarchy screen="chat"><node package="' + capture.PACKAGE
                    + '" content-desc="environment" bounds="[1098,78][1578,234]" />'
                    + '<node package="'+capture.PACKAGE+'" content-desc="bottom-address" '
                    + 'bounds="[300,900][2376,1044]" /></hierarchy>')
        old_xml = self.editor(self.BEFORE_IME)
        current = self.editor() if current is None else current

        def sleep(seconds):
            state['events'].append(('sleep', seconds))
            clock.value += seconds

        def read(*, deadline):
            state['deadlines'].append(deadline)
            if clock.value >= deadline:
                raise TimeoutError('Existing model scene deadline expired')
            clock.value += 1
            if not state['editor']:
                return chat_xml
            if not state['ime']:
                state['editorDeadline'] = deadline
                return old_xml
            state['currentReads'] += 1
            state['events'].append(('current', clock.value))
            if read_error is not None:
                raise read_error
            if late_return:
                clock.value = deadline
            return current

        def adb(*parts):
            if parts == ('shell', 'dumpsys', 'input_method'):
                clock.value += ime_seconds
                state['ime'] = True
                state['events'].append(('ime', shown))
                return b'mInputShown=true\n' if shown else b'mInputShown=false\n'
            self.assertEqual(parts[:3], ('shell', 'input', 'tap'))
            point = tuple(map(int, parts[3:]))
            state['events'].append(('tap', point, clock.value))
            if not state['editor']:
                state['editor'] = True
            else:
                left, top, right, bottom = self.AFTER_IME
                if left <= point[0] < right and top <= point[1] < bottom:
                    state['editor'] = False
                    state['cancelled'] = True
            return b''

        def screenshot(name):
            state['events'].append(('screenshot', name))
            (self.out / name).write_bytes(b'original model screenshot')

        def geometry(xml):
            return dict(layout='browser-bottom') if ET.fromstring(xml).get('screen') == 'chat' else None

        def capsule(xml):
            found = capture.nodes(xml, lambda node: node.get('content-desc') == 'environment')
            return found[0] if found else None

        def address(xml):
            found=capture.nodes(xml,lambda node:node.get('content-desc')=='bottom-address')
            return found[0] if len(found)==1 else None

        bindings = dict(args=SimpleNamespace(out=self.out), report=report,
            capture=SimpleNamespace(read=read), adb=adb, screenshot=screenshot,
            time=SimpleNamespace(monotonic=lambda: clock.value, sleep=sleep,
                                 time_ns=lambda: int(clock.value * 1_000_000_000)),
            re=validation.re, sha=capture.sha, write=capture.write,
            bounds=capture.bounds, nodes=capture.nodes, button=capture.button,
            geometry=geometry, observed_navigation_geometry=geometry,
            current_observed_navigation_geometry=geometry,
            capsule=capsule, nav=lambda xml: capsule(xml), api={'WIDTH': 2676,'browser_address_node':address})
        functions = []
        for owner, names in ((validation.capture_acceptance_suite,
                              {'save', 'artifact', 'text', 'chat', 'interactions'}),
                             (capture.main, {'tap', 'wait_for'})):
            body = ast.parse(inspect.getsource(owner)).body[0].body
            selected = [node for node in body if isinstance(node, ast.FunctionDef) and node.name in names]
            self.assertEqual({node.name for node in selected}, names)
            functions.extend(selected)
        exec(compile(ast.Module(body=functions, type_ignores=[]), validation.__file__, 'exec'), bindings)
        artifact = bindings['artifact']

        def until_toolbar(case, suffix, predicate, **options):
            if suffix == 'browser-toolbar':
                raise BoundaryReached()
            return artifact(case, suffix, predicate, **options)

        bindings['artifact'] = until_toolbar
        failure = None
        try:
            bindings['interactions'](case)
        except BoundaryReached:
            pass
        except Exception as error:
            failure = error
        return failure, state, report, case, old_xml, current

    def test_ime_moved_cancel_uses_current_bounds_and_retains_original_evidence(self):
        failure, state, report, case, old_xml, current = self.run_interaction()
        self.assertIsNone(failure)
        self.assertTrue(state['cancelled'])
        self.assertEqual(report['inputs'][0]['observedBounds'],[300,900,2376,1044],
                         'Current editor entry must come from the bottom address, not the environment capsule')
        self.assertEqual(report['inputs'][-1]['observedBounds'], list(self.AFTER_IME))
        self.assertEqual((report['inputs'][-1]['x'], report['inputs'][-1]['y']), (2110, 369))
        self.assertGreater(480, self.AFTER_IME[3], 'The old tap must miss the observed current control')
        self.assertEqual((self.out / 'landscape-light-url-keyboard.xml').read_text(), old_xml)
        self.assertEqual((self.out / 'landscape-light-url-keyboard.png').read_bytes(), b'original model screenshot')
        observed = case['observations']['url-keyboard-current']
        self.assertEqual((self.out / observed['xml']).read_text(), current)
        self.assertEqual(observed['xmlSha256'], hashlib.sha256(current.encode()).hexdigest())
        self.assertIn('url-cancelled', case['observations'])
        self.assertTrue(case['keyboard']['shown'])

    def test_current_read_shares_original_editor_deadline_without_an_extra_pause(self):
        failure, state, report, _, _, _ = self.run_interaction(ime_seconds=8)
        self.assertIsNone(failure)
        self.assertEqual(state['currentReads'], 1)
        self.assertEqual(state['deadlines'][1:3], [state['editorDeadline']] * 2)
        event = next(index for index, item in enumerate(state['events']) if item[0] == 'current')
        self.assertEqual(state['events'][event + 1], ('tap', (2110, 369), state['events'][event][1]))
        self.assertEqual(len(report['inputs']), 2)

    def test_missing_disabled_hidden_unclickable_or_ambiguous_cancel_fails_closed(self):
        for options in (dict(missing=True), dict(enabled='false'), {'visible-to-user': 'false'},
                        dict(clickable='false'), dict(duplicate=True), dict(bounds='[0,0][0,0]')):
            with self.subTest(options=options):
                failure, state, report, case, _, _ = self.run_interaction(current=self.editor(**options))
                self.assertIsInstance(failure, ValueError)
                self.assertEqual(state['currentReads'], 1)
                self.assertEqual(len(report['inputs']), 1, 'Only opening the editor is permitted')
                self.assertIn('url-keyboard-current', case['observations'])

    def test_cancel_without_the_url_editor_or_inside_environment_picker_fails_closed(self):
        for title in ('', '快速切换环境'):
            with self.subTest(title=title):
                failure, _, report, _, _, _ = self.run_interaction(current=self.editor(title=title))
                self.assertIsInstance(failure, ValueError)
                self.assertEqual(len(report['inputs']), 1)

    def test_keyboard_not_observed_cannot_refresh_or_cancel(self):
        failure, state, report, case, _, _ = self.run_interaction(shown=False)
        self.assertIsInstance(failure, ValueError)
        self.assertIn('keyboard was not observed', str(failure))
        self.assertFalse(case['keyboard']['shown'])
        self.assertEqual(state['currentReads'], 0)
        self.assertEqual(len(report['inputs']), 1)

    def test_expired_or_late_current_observation_cannot_extend_the_scene_or_tap(self):
        for options in (dict(ime_seconds=30), dict(late_return=True)):
            with self.subTest(options=options):
                failure, state, report, _, _, _ = self.run_interaction(**options)
                self.assertIsInstance(failure, TimeoutError)
                self.assertLessEqual(state['currentReads'], 1)
                self.assertEqual(len(report['inputs']), 1)
                if state['currentReads']:
                    self.assertEqual(state['deadlines'][-1], state['editorDeadline'])

    def test_current_capture_failure_is_not_retried_and_cannot_use_old_bounds(self):
        for error in (RuntimeError('capture failed'), subprocess.TimeoutExpired('uiautomator', 2)):
            with self.subTest(error=error):
                failure, state, report, _, _, _ = self.run_interaction(read_error=error)
                self.assertIs(failure, error)
                self.assertEqual(state['currentReads'], 1)
                self.assertEqual(len(report['inputs']), 1)


class GlassDisplayPreparationTest(unittest.TestCase):
    """Real setup helper with explicit AOSP launcher/rotation transport boundaries."""

    def setUp(self):
        self.clock = 0.0
        self.calls = []
        self.base = (1236, 2676)
        self.rotation = 0
        self.saved_launcher_rotation = 1
        self.foreground = False
        self.launch_succeeds = True
        self.ignore_rotation = False
        self.read_delay = 0.0
        self.night = 'notnight'
        self.scale = 1.0

    def adb(self, *parts, timeout):
        self.calls.append((parts, timeout))
        self.clock += self.read_delay
        if parts[:4] == ('shell', 'am', 'start', '-W'):
            self.foreground = self.launch_succeeds
            if self.foreground and self.saved_launcher_rotation is not None:
                # DisplayRotationReversionController.revertOverride restores
                # the rotation saved when the NOSENSOR launcher came forward.
                self.rotation = self.saved_launcher_rotation
                self.saved_launcher_rotation = None
            return b'Status: ok\n'
        if parts == ('shell', 'dumpsys', 'activity', 'activities'):
            activity = capture.COMPONENT if self.foreground else 'launcher/NOSENSOR'
            return ('topResumedActivity=ActivityRecord{' + activity + '}\n').encode()
        if parts == ('shell', 'am', 'force-stop', capture.PACKAGE):
            self.foreground = False
            return b''
        if parts[:3] == ('shell', 'wm', 'size'):
            requested = tuple(map(int, parts[3].split('x')))
            self.base = min(requested[0], 2472), min(requested[1], 5352)
            return b''
        if parts[:4] == ('shell', 'wm', 'user-rotation', 'lock'):
            if not self.ignore_rotation:
                self.rotation = int(parts[4])
            return b''
        logical = self.base[::-1] if self.rotation % 2 else self.base
        if parts == ('shell', 'am', 'get-config'):
            orientation = 'land' if logical[0] > logical[1] else 'port'
            return ('config: mcc310-' + orientation + '-' + self.night + '\n').encode()
        if parts == ('shell', 'settings', 'get', 'system', 'font_scale'):
            return str(self.scale).encode()
        if parts == ('shell', 'dumpsys', 'window', 'displays'):
            return (f'Display: mDisplayId=0 rootTasks=3\n  init=1236x2676 480dpi '
                    f'base={self.base[0]}x{self.base[1]} 480dpi '
                    f'cur={logical[0]}x{logical[1]} app={logical[0]}x{logical[1]}\n').encode()
        self.fail('Unexpected setup command: ' + repr(parts))

    def run_setup(self, target=None, width=1236, height=2676, *, retire_surface=True):
        target = target or validation.prepare_display
        self.owner = {}
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(validation.time, 'monotonic', side_effect=lambda: self.clock), \
                patch.object(validation.time, 'sleep', side_effect=lambda seconds: setattr(self, 'clock', self.clock + seconds)):
            return target(SimpleNamespace(out=Path(directory)), self.owner, 'controlled', self.adb,
                          capture.__dict__, width, height, 1.0, 'no', retire_surface=retire_surface)

    def test_portrait_applies_after_launcher_override_reversion(self):
        result = self.run_setup()
        self.assertEqual(result['status'], 'verified')
        self.assertIsNone(self.saved_launcher_rotation)
        self.assertEqual(self.rotation, 0)
        self.assertEqual(len(result['observations']), 2)
        self.assertTrue(all(row['matchesRequested'] for row in result['observations']))
        self.assertTrue(all(row['viewport'] == dict(widthPx=1236, heightPx=2676, densityDpi=480)
                            for row in result['observations']))
        self.assertGreaterEqual(self.clock, .5)

    def test_old_launcher_first_order_still_fails_on_real_helper_negative_control(self):
        source = inspect.getsource(validation.prepare_display)
        move = '        for command in display_configuration_commands(width, height):\n            read(*command)\n'
        self.assertEqual(source.count(move), 1)
        source = source.replace(move, '').replace(
            "        read('shell', 'am', 'start', '-W', '-n', api['COMPONENT']",
            move + "        read('shell', 'am', 'start', '-W', '-n', api['COMPONENT']", 1)
        namespace = dict(validation.__dict__)
        exec(compile(source, '<launcher-order-negative-control>', 'exec'), namespace)
        with self.assertRaises(TimeoutError):
            self.run_setup(namespace['prepare_display'])
        self.assertEqual(self.rotation, 1)
        self.assertEqual(self.owner['displayPreparation']['status'], 'failed')
        self.assertTrue(all(not row['matchesRequested'] for row in self.owner['displayPreparation']['observations']))

    def test_natural_axes_keep_complete_landscape_under_android12_width_clamp(self):
        result = self.run_setup(width=2676, height=1236)
        self.assertEqual(self.base, (1236, 2676))
        self.assertEqual(result['observations'][-1]['viewport'],
                         dict(widthPx=2676, heightPx=1236, densityDpi=480))

    def test_failed_foreground_launch_cannot_apply_or_accept_rotation(self):
        self.launch_succeeds = False
        with self.assertRaisesRegex(ValueError, 'did not leave the NOSENSOR launcher'):
            self.run_setup()
        self.assertFalse(any(parts[:2] == ('shell', 'wm') for parts, _ in self.calls))
        self.assertEqual(self.owner['displayPreparation']['observations'], [])

    def test_successful_shell_exit_cannot_hide_wrong_actual_configuration(self):
        self.ignore_rotation = True
        with self.assertRaisesRegex(TimeoutError, 'did not settle'):
            self.run_setup()
        self.assertLessEqual(self.clock, 15)
        self.assertEqual(self.owner['displayPreparation']['status'], 'failed')

    def test_theme_and_font_are_independent_actual_requirements(self):
        for field, value in (('night', 'night'), ('scale', 1.3)):
            with self.subTest(field=field):
                self.setUp()
                setattr(self, field, value)
                with self.assertRaises(TimeoutError):
                    self.run_setup()
                self.assertTrue(all(not row['matchesRequested'] for row in self.owner['displayPreparation']['observations']))

    def test_all_reads_share_one_deadline_and_expired_result_cannot_pass(self):
        self.read_delay = 4
        with self.assertRaises(TimeoutError):
            self.run_setup()
        self.assertEqual([timeout for _, timeout in self.calls], [6, 6, 6, 3])
        self.assertEqual(self.owner['displayPreparation']['status'], 'failed')
        self.assertEqual(self.owner['displayPreparation']['observations'], [])

    def test_late_final_processing_cannot_accept_an_otherwise_matching_display(self):
        original = capture.window_display_viewport
        observed = []
        def slow_last_parse(raw):
            result = original(raw)
            observed.append(result)
            if len(observed) == 2:
                self.clock += 16
            return result
        with patch.object(capture, 'window_display_viewport', side_effect=slow_last_parse), \
                self.assertRaises(TimeoutError):
            self.run_setup()
        self.assertEqual(len(self.owner['displayPreparation']['observations']), 2)
        self.assertTrue(all(row['matchesRequested'] for row in self.owner['displayPreparation']['observations']))
        self.assertEqual(self.owner['displayPreparation']['status'], 'failed')

    def setup_then_start_scene(self, action, *, target=None, width=1236, height=2676,
                               stop_error=False, stop_delay=0):
        """Actual setup helper; explicit observed task and NOSENSOR boundaries.

        The b6 Android 35 stdout hashes confirm START_DELIVERED_TO_TOP for
        the same live setup component. UiVisual's onNewIntent only observes
        downloads; its typography/chat dispatch belongs to onCreate. This is
        a controlled framework/fixture boundary, not another Android run.
        """
        original_adb = self.adb
        state = self.task_boundary = dict(live=None, created=[], delivered=[],
                                         nonces=[], viewports=[], stoppedAfter=[])

        def task_adb(*parts, timeout):
            starting = parts[:4] == ('shell', 'am', 'start', '-W')
            if starting and state['live'] is not None:
                self.calls.append((parts, timeout))
                self.clock += self.read_delay
                state['delivered'].append(parts[parts.index('visualAction') + 1])
                return (b'Warning: Activity not started, intent has been delivered '
                        b'to currently running top-most instance.\nStatus: ok\n')
            raw = original_adb(*parts, timeout=timeout)
            if starting:
                next_action = parts[parts.index('visualAction') + 1]
                state['live'] = next_action
                state['created'].append(next_action)
                state['viewports'].append(self.base[::-1] if self.rotation % 2 else self.base)
                if next_action == 'navigation-typography':
                    state['nonces'].append(parts[parts.index('visualNonce') + 1])
            if parts == ('shell', 'am', 'force-stop', capture.PACKAGE):
                state['stoppedAfter'].append(len(self.owner['displayPreparation']['observations']))
                if stop_error:
                    raise subprocess.CalledProcessError(1, parts, stderr=b'controlled stop failure')
                self.clock += stop_delay
                state['live'] = None
                # Entering the NOSENSOR launcher saves the final configured
                # rotation; the next app launch restores that same value.
                self.saved_launcher_rotation = self.rotation
                self.rotation = 0
            return raw

        with patch.object(self, 'adb', side_effect=task_adb):
            state['setup'] = self.run_setup(target, width, height)
            state['savedBeforeNextLaunch'] = self.saved_launcher_rotation
            self.adb('shell', 'am', 'start', '-W', '-n', capture.COMPONENT,
                     '--es', 'visualAction', action, '--es', 'visualNonce', 'fresh-scene', timeout=6)
        return state

    def test_first_typography_has_a_fresh_instance_nonce_and_final_rotation(self):
        for width, height, rotation in ((1236, 2676, 0), (2676, 1236, 1)):
            with self.subTest(rotation=rotation):
                self.setUp()
                state = self.setup_then_start_scene('navigation-typography', width=width, height=height)
                self.assertEqual(state['nonces'], ['fresh-scene'], 'Fresh typography must execute onCreate')
                self.assertEqual(state['created'], ['network', 'navigation-typography'])
                self.assertEqual(state['delivered'], [])
                self.assertEqual(state['savedBeforeNextLaunch'], rotation)
                self.assertEqual(state['viewports'][-1], (width, height))
                self.assertEqual(state['stoppedAfter'], [2])
                self.assertIs(state['setup']['configurationSurfaceStopped'], True)

    def test_first_loading_chat_cannot_be_delivered_to_the_network_setup_instance(self):
        state = self.setup_then_start_scene('chat', width=2676, height=1236)
        self.assertEqual(state['live'], 'chat', 'Chat must execute its onCreate dispatch')
        self.assertEqual(state['created'], ['network', 'chat'])
        self.assertEqual(state['delivered'], [])
        self.assertEqual(state['savedBeforeNextLaunch'], 1)
        self.assertEqual(state['viewports'][-1], (2676, 1236))

    def test_missing_retirement_negative_control_reuses_network_and_emits_no_new_nonce(self):
        source = inspect.getsource(validation.prepare_display)
        stop = "                    read('shell', 'am', 'force-stop', api['PACKAGE'])\n"
        self.assertLessEqual(source.count(stop), 1)
        namespace = dict(validation.__dict__)
        exec(compile(source.replace(stop, ''), '<unretired-configuration-surface>', 'exec'), namespace)
        for action in ('navigation-typography', 'chat'):
            with self.subTest(action=action):
                self.setUp()
                state = self.setup_then_start_scene(action, target=namespace['prepare_display'])
                self.assertEqual(state['created'], ['network'])
                self.assertEqual(state['delivered'], [action])
                self.assertEqual(state['live'], 'network')
                self.assertEqual(state['nonces'], [])

    def test_stop_failure_cannot_verify_an_otherwise_matching_display(self):
        with self.assertRaises(subprocess.CalledProcessError):
            self.setup_then_start_scene('chat', stop_error=True)
        self.assertEqual(self.owner['displayPreparation']['status'], 'failed')
        self.assertFalse(self.owner['displayPreparation'].get('configurationSurfaceStopped', False))
        self.assertEqual(self.task_boundary['created'], ['network'])

    def test_stop_uses_remaining_setup_budget_without_a_new_deadline(self):
        self.read_delay = 1
        state = self.setup_then_start_scene('chat')
        timeouts = [timeout for parts, timeout in self.calls
                    if parts == ('shell', 'am', 'force-stop', capture.PACKAGE)]
        self.assertEqual(timeouts, [4.5])
        self.assertEqual(state['setup']['status'], 'verified')
        self.assertLess(self.clock, 15)

    def test_late_stop_cannot_verify_or_start_the_next_scene(self):
        self.read_delay = 1
        with self.assertRaises(TimeoutError):
            self.setup_then_start_scene('chat', stop_delay=5)
        self.assertEqual(self.owner['displayPreparation']['status'], 'failed')
        self.assertFalse(self.owner['displayPreparation'].get('configurationSurfaceStopped', False))
        self.assertEqual(self.task_boundary['created'], ['network'])

    def test_retained_surface_keeps_observed_landscape_without_launcher(self):
        value=self.run_setup(width=2676,height=1236,retire_surface=False)
        self.assertTrue(self.foreground);self.assertEqual(self.rotation,1)
        self.assertTrue(value['configurationSurfaceRetained']);self.assertFalse(value['configurationSurfaceStopped'])
        self.assertEqual(len(value['observations']),2)
        self.assertFalse(any(parts==('shell','am','force-stop',capture.PACKAGE) for parts,_ in self.calls))

    def test_scene_and_typography_handoffs_create_fresh_activities_without_launcher(self):
        for function in (validation.capture_loading_landscape,validation.capture_acceptance_suite):
            tree=ast.parse(inspect.getsource(function))
            setup=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='prepare_display']
            retained=[n for n in setup if any(k.arg=='retire_surface' and ast.literal_eval(k.value) is False for k in n.keywords)]
            self.assertEqual(len(retained),1)
        source=inspect.getsource(validation.capture_acceptance_suite)
        typography=next(n for n in ast.walk(ast.parse(source)) if isinstance(n,ast.FunctionDef) and n.name=='typography')
        self.assertIn('--activity-clear-task',ast.unparse(typography));self.assertNotIn('force-stop',ast.unparse(typography))
        self.assertIn("start_output = adb('shell', 'am', 'start', '-W', '--activity-clear-task'",source)


class GlassCaptureFailureCleanupTest(unittest.TestCase):
    """Host-side cleanup checks with fake transports; no Android claim."""

    def test_loading_rotates_portrait_base_instead_of_exceeding_android12_width_limit(self):
        previous = capture.WIDTH, capture.HEIGHT, capture.DENSITY
        request = capture.DISPLAY_REQUEST
        capture.set_display(1236, 2676, 480)
        base, rotation = (1236, 2676), 0
        def adb(*parts, **options):
            nonlocal base, rotation
            if parts == ('shell', 'dumpsys', 'activity', 'activities'):
                return ('topResumedActivity=ActivityRecord{' + capture.COMPONENT + '}\n').encode()
            if parts[:3] == ('shell', 'wm', 'size'):
                if len(parts) == 4:
                    width, height = map(int, parts[3].split('x'))
                    # AOSP Android 12 DisplayContent.setForcedSize clamps each
                    # natural-orientation axis to twice its physical size.
                    base = min(width, 1236 * 2), min(height, 2676 * 2)
                    return b''
                return f'Physical size: 1236x2676\nOverride size: {base[0]}x{base[1]}\n'.encode()
            if parts[:4] == ('shell', 'wm', 'user-rotation', 'lock'):
                rotation = int(parts[4]); return b''
            logical = base[::-1] if rotation % 2 else base
            if parts == ('shell', 'wm', 'density'):
                return b'Physical density: 480\n'
            if parts == ('shell', 'settings', 'get', 'system', 'font_scale'):
                return b'1.0\n'
            if parts == ('shell', 'am', 'get-config'):
                return b'config: mcc310-land-notnight\n' if logical[0] > logical[1] else b'config: mcc310-port-notnight\n'
            if parts == ('shell', 'dumpsys', 'window', 'displays'):
                return (f'Display: mDisplayId=0 rootTasks=5\n  init=1236x2676 480dpi '
                        f'base={base[0]}x{base[1]} 480dpi cur={logical[0]}x{logical[1]} '
                        f'app={logical[0]}x{logical[1]}\n').encode()
            return b''
        try:
            with tempfile.TemporaryDirectory() as directory:
                args = SimpleNamespace(root=Path(__file__).resolve().parents[1], out=Path(directory))
                report = dict(buildIdentity=dict(sourceCommit='source', sourceTree='tree',
                    sdkReceiptSha256='sdk', integrationSigningCertificateSha256='signer'),
                    installedApk={'sha256': 'apk'}, runNonce='nonce', inputs=[], commands=[])
                boundary = MagicMock(side_effect=RuntimeError('viewport boundary completed'))
                result = validation.capture_loading_landscape(args, report, MagicMock(), adb,
                    boundary, MagicMock(), capture.__dict__)
                self.assertEqual(result['displayViewport']['status'], 'verified')
                self.assertEqual(result['displayViewport']['actual']['widthPx'], 2676)
                self.assertEqual(result['displayViewport']['actual']['heightPx'], 1236)
                self.assertEqual(result['errors'][0]['error'], 'viewport boundary completed')
                boundary.assert_called_once()
                self.assertTrue(result['restoredDisplayBeforeControlledDocument'])
                self.assertEqual((base, rotation), ((1236, 2676), 0))
                self.assertFalse(report['inputs'])
        finally:
            capture.set_display(*previous, requested=request)

    def test_clamped_loading_viewport_fails_before_input_or_geometry_wait_and_restores_display(self):
        previous = capture.WIDTH, capture.HEIGHT, capture.DENSITY
        request = capture.DISPLAY_REQUEST
        capture.set_display(1236, 2676, 480)
        forced = False

        def adb(*parts, **options):
            nonlocal forced
            if parts == ('shell', 'dumpsys', 'activity', 'activities'):
                return ('topResumedActivity=ActivityRecord{' + capture.COMPONENT + '}\n').encode()
            if parts[:4] == ('shell', 'wm', 'user-rotation', 'lock'):
                forced = parts[4] == '1'
                return b''
            if parts[:3] == ('shell', 'wm', 'size'):
                if len(parts) == 4:
                    forced = parts[3] == '2676x1236'
                    return b''
                return b'Physical size: 1236x2676\n' + (b'Override size: 2472x1236\n' if forced else b'')
            if parts == ('shell', 'wm', 'density'):
                return b'Physical density: 480\n'
            if parts == ('shell', 'settings', 'get', 'system', 'font_scale'):
                return b'1.0\n'
            if parts == ('shell', 'am', 'get-config'):
                return b'config: mcc310-land-notnight\n' if forced else b'config: mcc310-port-notnight\n'
            if parts == ('shell', 'dumpsys', 'window', 'displays'):
                return (b'Display: mDisplayId=0 rootTasks=5\n'
                        + (b'  init=1236x2676 480dpi base=2472x1236 480dpi cur=2472x1236 app=2472x1236\n'
                           if forced else b'  init=1236x2676 480dpi cur=1236x2676 app=1236x2676\n'))
            return b''

        try:
            with tempfile.TemporaryDirectory() as directory:
                args = SimpleNamespace(root=Path(__file__).resolve().parents[1], out=Path(directory))
                report = dict(buildIdentity=dict(sourceCommit='source', sourceTree='tree',
                    sdkReceiptSha256='sdk', integrationSigningCertificateSha256='signer'),
                    installedApk={'sha256': 'apk'}, runNonce='nonce', inputs=[], commands=[])
                transport = MagicMock(side_effect=adb)
                wait_for, screenshot = MagicMock(), MagicMock()
                clock = [0.0]
                with patch.object(validation.time, 'monotonic', side_effect=lambda: clock[0]), \
                        patch.object(validation.time, 'sleep', side_effect=lambda seconds: clock.__setitem__(0, clock[0] + seconds)):
                    result = validation.capture_loading_landscape(args, report, MagicMock(), transport,
                        wait_for, screenshot, capture.__dict__)
                self.assertEqual(result['status'], 'failed')
                preparation = result['displayPreparation']
                self.assertEqual(preparation['status'], 'failed')
                self.assertEqual(preparation['requested']['widthPx'], 2676)
                self.assertTrue(preparation['observations'])
                self.assertTrue(all(row['viewport']['widthPx'] == 2472
                                    and not row['matchesRequested'] for row in preparation['observations']))
                self.assertIn('Actual Android display configuration did not settle', result['errors'][0]['error'])
                wait_for.assert_not_called()
                self.assertFalse(report['inputs'])
                self.assertFalse(any('input' in call.args for call in transport.call_args_list))
                screenshot.assert_called_once_with('landscape-loading-native-failed.png')
                self.assertTrue(result['restoredDisplayBeforeControlledDocument'])
                self.assertEqual(result['restoredDisplay']['displayViewport']['status'], 'verified')
                self.assertEqual((capture.WIDTH, capture.HEIGHT, capture.DENSITY), (1236, 2676, 480))
        finally:
            capture.set_display(*previous, requested=request)

    def test_failed_loading_restoration_still_stops_the_configuration_activity(self):
        previous = capture.WIDTH, capture.HEIGHT, capture.DENSITY
        request = capture.DISPLAY_REQUEST
        capture.set_display(1236, 2676, 480)
        calls = []
        def adb(*parts, **options):
            calls.append(parts)
            if parts == ('shell', 'settings', 'get', 'system', 'font_scale'):
                return b'1.0\n'
            if parts == ('shell', 'am', 'get-config'):
                return b'config: mcc310-port-notnight\n'
            return b''
        def fail_setup(*args, **options):
            calls.append(('prepare', args[2]))
            raise TimeoutError('configuration failed')
        try:
            with tempfile.TemporaryDirectory() as directory, \
                    patch.object(validation, 'prepare_display', side_effect=fail_setup):
                args = SimpleNamespace(root=Path(__file__).resolve().parents[1], out=Path(directory))
                report = dict(buildIdentity=dict(sourceCommit='source', sourceTree='tree',
                    sdkReceiptSha256='sdk', integrationSigningCertificateSha256='signer'),
                    installedApk={'sha256': 'apk'}, runNonce='nonce', inputs=[], commands=[])
                result = validation.capture_loading_landscape(args, report, MagicMock(), adb,
                    MagicMock(), MagicMock(), capture.__dict__)
                self.assertEqual(result['status'], 'failed')
                self.assertFalse(result['restoredDisplayBeforeControlledDocument'])
                self.assertEqual(calls[-2:], [('prepare', 'landscape-loading-native-restore'),
                                             ('shell', 'am', 'force-stop', capture.PACKAGE)])
                self.assertEqual([row['error'] for row in result['errors']],
                                 ['configuration failed', 'configuration failed'])
        finally:
            capture.set_display(*previous, requested=request)

    def test_second_server_constructor_failure_does_not_shutdown_unstarted_server(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'tests' / 'gecko' / 'run_ui_visuals.py'
            source.parent.mkdir(parents=True)
            source.write_text('class ReloadHttp(reload_loopback.Fixture):\n    pass\n')
            first_server = MagicMock()
            failure = OSError('controlled SOCKS port already in use')
            loopback = SimpleNamespace(Fixture=object, Socks=object, TRACE=[],
                                       ThreadedSocks=MagicMock(side_effect=failure))
            spec = SimpleNamespace(loader=SimpleNamespace(exec_module=MagicMock()))
            with patch.object(validation.importlib.util, 'spec_from_file_location', return_value=spec), \
                    patch.object(validation.importlib.util, 'module_from_spec', return_value=loopback), \
                    patch.object(validation.http.server, 'ThreadingHTTPServer', return_value=first_server), \
                    patch.object(validation.threading, 'Thread') as thread:
                with self.assertRaises(OSError) as caught:
                    with validation.controlled_document(SimpleNamespace(root=root),
                                                        MagicMock(return_value=b''), {}, MagicMock()):
                        self.fail('The body must not start after a fixture bind failure')
            self.assertIs(caught.exception, failure)
            thread.assert_not_called()
            first_server.shutdown.assert_not_called()
            first_server.server_close.assert_called_once_with()

    def test_ui_failure_survives_video_retrieval_failure_and_owned_recorder_is_stopped(self):
        with tempfile.TemporaryDirectory() as directory:
            nonce = 'a' * 32
            remote = '/data/local/tmp/glass-suite-' + nonce + '.mp4'
            pid_file = remote + '.pid'
            process = MagicMock()
            process.returncode = None
            process.poll.side_effect = lambda: process.returncode

            def finish(**kwargs):
                process.returncode = 0
                return 0

            process.wait.side_effect = finish

            def adb(*parts, **kwargs):
                if parts == ('shell', 'cat', pid_file):
                    return b'123\n'
                if parts == ('shell', 'cat', '/proc/123/cmdline'):
                    return b'/system/bin/screenrecord\0--size\0' + b'618x1338\0' + remote.encode() + b'\0'
                if parts == ('shell', 'sha256sum', remote):
                    raise OSError('controlled video transfer failure')
                return b''

            transport = MagicMock(side_effect=adb)
            case = {'name': 'failed-ui', 'runNonce': nonce}
            primary = RuntimeError('Actual UI did not enter reading')
            args = SimpleNamespace(out=Path(directory), adb='fake-adb', serial='fake-device')
            with patch.object(validation.subprocess, 'Popen', return_value=process), \
                    patch.object(validation.time, 'sleep'):
                with self.assertRaises(RuntimeError) as caught:
                    with validation.record_case(args, {'inputs': [], 'commands': []}, transport, case,
                                                MagicMock(), MagicMock()):
                        raise primary
            self.assertIs(caught.exception, primary)
            self.assertEqual(case['motion']['status'], 'failed')
            self.assertIn('retrieve-or-validate-video',
                          [row['stage'] for row in case['motion']['errors']])
            self.assertTrue(any(call.args == ('shell', 'kill', '-INT', '123')
                                for call in transport.call_args_list))
            self.assertTrue(any(call.args[:4] == ('shell', 'rm', '-f', pid_file)
                                for call in transport.call_args_list))




class GlassRendererAttributionTest(unittest.TestCase):
    """Host controls for actual renderer consumers, not Android observations."""
    def setUp(self):
        fixture=GlassReadyFailureDiagnosticsTest();fixture.setUp()
        self.identity=fixture.identity;self.nonce=fixture.case['runNonce']
        self.start=fixture.trace();self.start['stage']='start-before'

    def line(self,text,tag='GlassLens',pid='4321',priority='I'):
        return f'11-15 12:00:00.123  {pid}  4321 {priority} {tag}: {text}\n'

    def log(self,*,old=False,warning=False):
        marks=self.line('AGSL material ready')+self.line('native backdrop recorded')
        boundary=self.line(json.dumps(self.start),'PocketCollapseTrace')
        return ((marks+boundary if old else boundary+marks)+(self.line('AGSL unavailable',priority='W') if warning else '')).encode()

    def native(self,api=35,*,recorded=True):
        rows=[]
        for index,role in enumerate(('workspace',)):
            present=api>=33
            rows.append(dict(role=role,dockRef=100+index,drawableRef=200+index,
                attached=True,currentActivityRoot=True,ownerBound=True,backdropBound=True,gpuBroken=False,
                rendererRef=300+index if present else 0,
                rendererClass='local.pocketchat.GlassLensRenderer' if present else '',agslReady=present,
                nativeBackdropRecorded=present and recorded,hadBackdrop=present,
                lastSourcePresent=present,lastSourceCurrent=present))
        return dict(schema=1,navigationContract=4,deviceApi=api,pid=4321,mainThread=True,
            activityClass='local.pocketchat.CompactChromeIntegrationActivity',activityRef=1234,docks=rows)

    def observe(self,raw,before=None,after=None,api=35):
        tree=ast.parse(inspect.getsource(validation.capture_acceptance_suite))
        function=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='renderer_observation')
        case=dict(name='host-renderer-boundary',runNonce=self.nonce,documentObservations=dict(
            ready=dict(glassRenderer=before if before is not None else self.native(api)),
            **{'after-interactions':dict(glassRenderer=after if after is not None else self.native(api))}))
        def adb(*parts,**kwargs):
            if parts==('shell','pidof','local.pocketchat.test'):return b'4321\n'
            if parts[:2]==('logcat','-d'):return raw
            raise AssertionError(parts)
        with tempfile.TemporaryDirectory() as directory:
            namespace=dict(adb=adb,package='local.pocketchat.test',identity=self.identity,
                args=SimpleNamespace(out=Path(directory),device_api=api),
                renderer_scene_messages=validation.renderer_scene_messages,
                verify_scene_renderers=validation.verify_scene_renderers,
                sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest())
            exec(compile(ast.Module(body=[function],type_ignores=[]),'<actual-renderer-consumer>','exec'),namespace)
            namespace['renderer_observation'](case)
        return case['materialPath']

    def test_same_pid_preparation_lines_cannot_satisfy_current_scene(self):
        raw=self.log(old=True)
        messages,boundary=validation.renderer_scene_messages(raw,self.identity,self.nonce,['4321'])
        self.assertEqual(messages,[]);self.assertEqual(boundary['lineIndex'],2)
        with self.assertRaises(ValueError):self.observe(raw)

    def test_current_lines_and_current_materials_keep_original_log_claims(self):
        value=self.observe(self.log())
        self.assertTrue(value['agslReady']);self.assertTrue(value['nativeBackdropRecorded'])
        self.assertTrue(value['sceneRenderers']['verified'])
        self.assertEqual(value['sceneRenderers']['navigationContract'], 4)

    def test_historical_renderer_readers_do_not_authorize_current_capture(self):
        for contract in (2, 3):
            before = self.native()
            before['navigationContract'] = contract
            if contract == 2:
                conversation = dict(before['docks'][0], role='conversation', dockRef=101,
                                    drawableRef=201, rendererRef=301)
                before['docks'].insert(0, conversation)
            after = copy.deepcopy(before)
            observed = validation.verify_scene_renderers(before, after, 35, ['4321'])
            self.assertTrue(observed['verified'])
            self.assertEqual(observed['navigationContract'], contract)
            with self.subTest(contract=contract), self.assertRaises(ValueError):
                self.observe(self.log(), before, after)

    def test_late_old_same_pid_logs_cannot_replace_unrendered_current_material(self):
        before=self.native(recorded=False);after=self.native(recorded=False)
        with self.assertRaisesRegex(ValueError,'did not actually render'):self.observe(self.log(),before,after)

    def test_warning_foreign_source_and_missing_current_nonce_are_rejected(self):
        with self.assertRaises(ValueError):self.observe(self.log(warning=True))
        self.start['sourceCommit']='f'*40
        with self.assertRaises(ValueError):self.observe(self.log())
        self.start['sourceCommit']=self.identity['sourceCommit'];self.start['runNonce']='f'*32
        with self.assertRaises(ValueError):self.observe(self.log())

    def test_native_foreign_objects_failed_materials_and_missing_receipts_are_rejected(self):
        changes=(lambda v:v.update(activityRef=9),lambda v:v.update(pid=1),
            lambda v:v['docks'][0].update(drawableRef=9),lambda v:v['docks'][0].update(ownerBound=False),
            lambda v:v['docks'][0].update(backdropBound=False),lambda v:v['docks'][0].update(currentActivityRoot=False),
            lambda v:v['docks'][0].update(gpuBroken=True),lambda v:v['docks'][0].update(lastSourceCurrent=False),
            lambda v:v['docks'].pop())
        for index,change in enumerate(changes):
            after=self.native();change(after)
            with self.subTest(index=index),self.assertRaises(ValueError):self.observe(self.log(),after=after)
        with self.assertRaises(ValueError):self.observe(self.log(),before={})

    def test_already_rendered_ready_and_legitimate_hidden_dock_discard_are_allowed(self):
        after=self.native()
        for row in after['docks']:row.update(hadBackdrop=False,lastSourcePresent=False,lastSourceCurrent=False)
        self.assertTrue(self.observe(self.log(),after=after)['sceneRenderers']['verified'])

    def test_api32_retains_cpu_branch_and_rejects_any_agsl_claim(self):
        raw=self.line(json.dumps(self.start),'PocketCollapseTrace').encode()
        self.assertTrue(self.observe(raw,api=32)['sourceBoundCpuBranch'])
        with self.assertRaises(ValueError):self.observe(self.log(),api=32)
        with self.assertRaises(ValueError):self.observe(raw,after=self.native(),api=32)

    def test_preparation_is_saved_before_opted_in_launch_without_clearing_journal(self):
        source=inspect.getsource(validation.capture_acceptance_suite)
        self.assertLess(source.index("case['rendererPreparationLog']"),source.index('start_output = adb('))
        self.assertIn("'observeGlassRenderer', 'true'",source)
        prefix=source[source.index('preparation_log='):source.index('start_output = adb(')]
        self.assertNotIn("'-c'",prefix);self.assertNotIn('force-stop',prefix)



    def test_actual_native_observer_reads_owned_materials_and_skips_api33_fields_on_api32(self):
        root=Path(__file__).resolve().parents[1]
        java_home=Path(os.environ['JAVA_HOME'])
        jar=Path(os.environ.get('PROFILE_JSON_JAR',str(root/'work/profile-host/json.jar')))
        self.assertTrue((java_home/'bin/javac').is_file() and jar.is_file(),'Actual JDK17 and JSON dependency required')
        source=(root/'tests/gecko/ChromeCollapseIntegration.java').read_text()
        methods=source[source.index('  JSONObject glassRendererObservation()'):source.index('  void emit(',source.index('  JSONObject glassRendererObservation()'))]
        java=r"""package local.pocketchat;
import org.json.*;
import android.graphics.drawable.*;
class Build {static class VERSION {static int SDK_INT=SDK_VALUE;}}
class Looper {static final Looper MAIN=new Looper();static Looper myLooper(){return MAIN;}static Looper getMainLooper(){return MAIN;}}
class View {Object context;View parent,root;Drawable background;boolean attached=true;
 View(Object context,View root){this.context=context;this.root=root==null?this:root;}
 View getParent(){return parent;}View getRootView(){return root;}Object getContext(){return context;}
 Drawable getBackground(){return background;}boolean isAttachedToWindow(){return attached;}}
class GlassDock extends View {GlassDock(Object context,View root){super(context,root);}}
class GlassLensRenderer {private boolean reportedBackdrop=true,hadBackdrop=true;private Object lastSource;
 GlassLensRenderer(Object source){lastSource=source;}}
class LiquidGlassDrawable extends Drawable {
 private java.lang.ref.WeakReference<Object> owner,backdrop;private boolean gpuBroken;
 RENDERER_FIELD
 LiquidGlassDrawable(Object host,Object source){owner=new java.lang.ref.WeakReference<>(host);backdrop=new java.lang.ref.WeakReference<>(source);RENDERER_INIT}
 void owner(Object value){owner=new java.lang.ref.WeakReference<>(value);}
}
class ChildMaterial extends LiquidGlassDrawable {ChildMaterial(Object h,Object s){super(h,s);}}
class Hub {CompactChromeIntegrationActivity a;Object panel=new Object();View[] tabs,workspaceTabs;}
class Window {View root;Window(View root){this.root=root;}View getDecorView(){return root;}}
class CompactChromeIntegrationActivity {Hub hub=new Hub();Window window;Window getWindow(){return window;}}
public class RendererHost {
 final CompactChromeIntegrationActivity a=new CompactChromeIntegrationActivity();
 final ChildMaterial first,second;
 RendererHost(){
  View root=new View(a,null);a.window=new Window(root);a.hub.a=a;
  GlassDock conversation=new GlassDock(a,root),workspace=new GlassDock(a,root);
  first=new ChildMaterial(conversation,a.hub.panel);second=new ChildMaterial(workspace,a.hub.panel);
  conversation.background=new InsetDrawable(new LayerDrawable(new Drawable[]{new Drawable(),first}));
  workspace.background=new LayerDrawable(new Drawable[]{new InsetDrawable(second)});
  View tab=new View(a,root),workspaceTab=new View(a,root);tab.parent=conversation;workspaceTab.parent=workspace;
  a.hub.tabs=new View[]{tab};a.hub.workspaceTabs=new View[]{workspaceTab};
 }
 METHODS
 static void require(boolean value,String message){if(!value)throw new AssertionError(message);}
 public static void main(String[] args)throws Exception {
  RendererHost host=new RendererHost();JSONObject report=host.glassRendererObservation();
  require(report.getInt("navigationContract")==4,"current native navigation contract");
  require(report.getBoolean("mainThread"),"actual main thread boundary");
  require(report.getString("activityClass").equals("local.pocketchat.CompactChromeIntegrationActivity"),"actual activity class");
  JSONArray docks=report.getJSONArray("docks");require(docks.length()==1,"the actual workspace dock; browser bar is not a dock");
  for(int i=0;i<1;i++){
   JSONObject row=docks.getJSONObject(i);
   for(String key:new String[]{"attached","currentActivityRoot","ownerBound","backdropBound"})require(row.getBoolean(key),key);
   require(row.getBoolean("agslReady")== (Build.VERSION.SDK_INT>=33),"actual guarded renderer branch");
   require(row.getBoolean("nativeBackdropRecorded")== (Build.VERSION.SDK_INT>=33),"actual recording flag");
   require(row.getBoolean("lastSourceCurrent")== (Build.VERSION.SDK_INT>=33),"actual source identity");
  }
  host.second.owner(new Object());require(!host.glassRendererObservation().getJSONArray("docks").getJSONObject(0).getBoolean("ownerBound"),"foreign owner rejected");
  try {glassMaterial(new LayerDrawable(new Drawable[]{host.first,host.second}));throw new AssertionError("ambiguous material accepted");}
  catch(IllegalStateException expected){}
  require(glassMaterial(new InsetDrawable(new LayerDrawable(new Drawable[]{host.second})))==host.second,"layered actual object identity");
  System.out.println("{\"passed\":true,\"api\":"+Build.VERSION.SDK_INT+"}");
 }
}
"""
        with tempfile.TemporaryDirectory() as directory:
            work=Path(directory)
            stubs={
                'android/graphics/drawable/Drawable.java':'package android.graphics.drawable;public class Drawable {}',
                'android/graphics/drawable/InsetDrawable.java':'package android.graphics.drawable;public class InsetDrawable extends Drawable {final Drawable value;public InsetDrawable(Drawable v){value=v;}public Drawable getDrawable(){return value;}}',
                'android/graphics/drawable/LayerDrawable.java':'package android.graphics.drawable;public class LayerDrawable extends Drawable {final Drawable[] values;public LayerDrawable(Drawable[] v){values=v;}public int getNumberOfLayers(){return values.length;}public Drawable getDrawable(int i){return values[i];}}',
                'android/os/Process.java':'package android.os;public class Process {public static int myPid(){return 4321;}}'}
            for name,text in stubs.items():
                path=work/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
            for api in (32,35):
                code=java.replace('SDK_VALUE',str(api)).replace('METHODS',methods)
                code=code.replace('RENDERER_FIELD','private GlassLensRenderer renderer;' if api>=33 else '')
                code=code.replace('RENDERER_INIT','renderer=new GlassLensRenderer(source);' if api>=33 else '')
                target=work/'RendererHost.java';target.write_text(code);classes=work/str(api);classes.mkdir()
                compiled=subprocess.run([str(java_home/'bin/javac'),'-encoding','UTF-8','-cp',str(jar),'-d',str(classes),
                    *[str(work/name) for name in stubs],str(root/'app/src/main/java/local/pocketchat/J.java'),str(target)],capture_output=True,text=True,timeout=30)
                self.assertEqual(compiled.returncode,0,compiled.stdout+compiled.stderr)
                ran=subprocess.run([str(java_home/'bin/java'),'-cp',str(classes)+os.pathsep+str(jar),'local.pocketchat.RendererHost'],capture_output=True,text=True,timeout=10)
                self.assertEqual(ran.returncode,0,ran.stdout+ran.stderr);self.assertEqual(json.loads(ran.stdout),dict(passed=True,api=api))


if __name__ == '__main__':
    unittest.main()
