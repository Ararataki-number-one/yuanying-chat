#!/usr/bin/env python3
"""Focused checks for acceptance decisions made from Android hierarchy bounds.

The fixtures represent native button touch regions, including the two-row
layout used when a narrow window cannot fit an independently centered dock.
They do not stand in for Android capture or visual inspection.
"""
import ast
import hashlib
import inspect
import json
from pathlib import Path
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


class GlassDocumentEventDiscoveryTest(unittest.TestCase):
    """Exercise the actual glass consumer with explicit synthetic native bytes."""

    def observer(self, out, *, journal_changes=None, log=None, payload=None, pending=False, delays=None):
        result = dict(command='ready', document='controlled', applicationAcceptance=False)
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
        view(header, 'TextView', capsule, clickable='true', enabled='true',
             **{'content-desc': '当前环境：日常会话，点按输入网址，长按切换环境'})
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
        view(content, 'TextView', (720, 810, 1956, 840), text='点按顶部输入网址，长按切换环境')
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

    def run_setup(self, target=None, width=1236, height=2676):
        target = target or validation.prepare_display
        self.owner = {}
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(validation.time, 'monotonic', side_effect=lambda: self.clock), \
                patch.object(validation.time, 'sleep', side_effect=lambda seconds: setattr(self, 'clock', self.clock + seconds)):
            return target(SimpleNamespace(out=Path(directory)), self.owner, 'controlled', self.adb,
                          capture.__dict__, width, height, 1.0, 'no')

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


if __name__ == '__main__':
    unittest.main()
