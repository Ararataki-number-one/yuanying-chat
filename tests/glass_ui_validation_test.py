#!/usr/bin/env python3
"""Focused checks for acceptance decisions made from Android hierarchy bounds.

The fixtures represent native button touch regions, including the two-row
layout used when a narrow window cannot fit an independently centered dock.
They do not stand in for Android capture or visual inspection.
"""
import sys
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools' / 'gecko'))
import capture_glass_navigation as capture
import glass_ui_validation as validation


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


class GlassCaptureFailureCleanupTest(unittest.TestCase):
    """Host-side cleanup checks with fake transports; no Android claim."""

    def test_clamped_loading_viewport_fails_before_input_or_geometry_wait_and_restores_display(self):
        previous = capture.WIDTH, capture.HEIGHT, capture.DENSITY
        request = capture.DISPLAY_REQUEST
        capture.set_display(1236, 2676, 480)
        forced = False

        def adb(*parts, **options):
            nonlocal forced
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
                result = validation.capture_loading_landscape(args, report, MagicMock(), transport,
                    wait_for, screenshot, capture.__dict__)
                self.assertEqual(result['status'], 'failed')
                self.assertEqual(result['displayViewport']['requested']['widthPx'], 2676)
                self.assertEqual(result['displayViewport']['actual']['widthPx'], 2472)
                self.assertFalse(result['displayViewport']['matchesRequested'])
                self.assertIn('Actual Android viewport differs', result['errors'][0]['error'])
                wait_for.assert_not_called()
                self.assertFalse(report['inputs'])
                self.assertFalse(any('input' in call.args for call in transport.call_args_list))
                screenshot.assert_called_once_with('landscape-loading-native-failed.png')
                self.assertTrue(result['restoredDisplayBeforeControlledDocument'])
                self.assertEqual(result['restoredDisplay']['displayViewport']['status'], 'verified')
                self.assertEqual((capture.WIDTH, capture.HEIGHT, capture.DENSITY), (1236, 2676, 480))
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
