"""Host controls for observed browser XML and exact current device-runner paths.

The XML files are unchanged observations from earlier Android CI runs. Mutated
XML and controlled ADB functions below test selectors, deadlines and gestures;
they do not claim a new device execution or physical-phone acceptance.
"""
import ast
import copy
from contextlib import redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import sys
import unittest
from unittest import mock
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools/gecko'))
import workspace_navigation_contract as CONTRACT
from profile_workspace_navigation_v2_test import (
    PACKAGE, NAVIGATION_DUMP_COMMAND, NAVIGATION_DUMP_SUCCESS,
    screen, dashboard_screen, xml)
from profile_environment_dashboard_presentation_test import RUN, environment_tree, node

FIXTURES = ROOT/'tests/fixtures'
HEADER = FIXTURES/'browser-workspace-header-api35.xml'
WIDE = FIXTURES/'browser-workspace-wide-header-api35.xml'
MENU = FIXTURES/'environment-details-menu-api35.xml'


class Clock:
    def __init__(self): self.now = 0.0
    def monotonic(self): return self.now
    def sleep(self, seconds): self.now += seconds


def header_value(tree=None, wide=False):
    source = (WIDE if wide else HEADER).read_text() if tree is None else xml(tree)
    return CONTRACT.conversation_header(source, PACKAGE, 892 if wide else 360,
                                        412 if wide else 640, 1,
                                        '默认环境' if wide else '日常会话', browser=True)


def described(tree, label):
    return next(n for n in tree.iter('node') if n.get('content-desc') == label)


def browser_workspace():
    tree = screen(False)
    old = described(tree, '会话')
    old.set('text', '浏览器'); old.set('content-desc', '浏览器')
    return xml(tree)


def exercise_roundtrip(final=None, management=None, late_read=False, late_save=False):
    clock = Clock(); calls = []; saved = []; taps = []
    initial = HEADER.read_text()
    final = initial if final is None else final
    management = browser_workspace() if management is None else management
    def adb(*parts):
        calls.append(parts)
        if parts[:3] == ('shell', 'input', 'tap'):
            taps.append(parts)
            return ''
        if parts == ('shell', NAVIGATION_DUMP_COMMAND):
            return NAVIGATION_DUMP_SUCCESS
        if parts == ('shell', 'cat', '/sdcard/gecko-navigation-v2.xml'):
            if len(taps) == 1: return management
            if late_read: clock.sleep(20)
            return final
        raise AssertionError(parts)
    def save(name, content):
        saved.append((name, content))
        if late_save and len(saved) == 2: clock.sleep(20)
    with mock.patch.object(CONTRACT, 'time', clock), redirect_stdout(io.StringIO()):
        result = CONTRACT.exercise_workspace_roundtrip(adb, initial, save, PACKAGE, browser=True)
    return result, calls, saved


class BrowserWorkspaceContracts(unittest.TestCase):
    def test_unmodified_artifact_provenance_and_bytes(self):
        provenance = json.loads((FIXTURES/'browser-workspace-observations.json').read_text())
        expected = {
            HEADER.name: (16909, 'c1425f6afd23c7aa7041ee0f4905c4c609d2550273b423e1786dd8f6b4b81d5b', 13942776491),
            WIDE.name: (17842, '4d7ac1388fb3133e509e678b318725426bf949bb4e2ced2f4ffb06e6c2164fc9', 13942564984),
            MENU.name: (9092, 'e6bc5570a5c63583c3c24252d1d79a914a1c2a595c5b6e8731a08893ad8486f4', 13942776491),
        }
        self.assertEqual(provenance['schema'], 1)
        self.assertEqual({n['file'] for n in provenance['observations']}, set(expected))
        for observation in provenance['observations']:
            raw = (FIXTURES/observation['file']).read_bytes()
            self.assertEqual((len(raw), hashlib.sha256(raw).hexdigest(), observation['artifactId']), expected[observation['file']])
            self.assertEqual((observation['bytes'], observation['sha256']), expected[observation['file']][:2])
            self.assertEqual(observation['runAttempt'], 1)
            self.assertEqual(observation['sourceCommit'],
                '1178ce488bc1532d71460845b2b7131724416df6' if observation['file'] == WIDE.name
                else '09e3db4e9eaf9b2ca353e35479b2d1022487329b')

    def test_actual_stacked_and_inline_headers_require_explicit_browser_contract(self):
        for wide, layout in ((False, 'stacked'), (True, 'inline')):
            with self.subTest(layout=layout):
                result = header_value(wide=wide)
                self.assertEqual(result['addressLayout'], layout)
                self.assertTrue(result['browserWorkspace'])
                self.assertEqual(len(result['browserActionBounds']), 6)
        with self.assertRaises(AssertionError):
            CONTRACT.conversation_header(HEADER.read_text(), PACKAGE, 360, 640, 1, '日常会话')
        self.assertFalse(any(n.get('enabled') == 'true' for n in ET.parse(HEADER).iter('node')
                             if n.get('content-desc') in ('后退', '前进')))

    def test_missing_duplicate_foreign_disabled_or_hidden_native_controls_reject(self):
        for label in ('后退', '前进', '刷新网页', '打开当前环境主页', '管理环境', '更多'):
            for operation in ('missing', 'duplicate', 'foreign', 'class', 'hidden', 'unclickable', 'clipped'):
                tree = ET.parse(HEADER).getroot(); target = described(tree, label)
                parent = next(n for n in tree.iter() if target in list(n))
                if operation == 'missing': parent.remove(target)
                elif operation == 'duplicate': parent.append(copy.deepcopy(target))
                elif operation == 'foreign': target.set('package', 'foreign.package')
                elif operation == 'class': target.set('class', 'android.widget.TextView')
                elif operation == 'hidden': target.set('visible-to-user', 'false')
                elif operation == 'unclickable': target.set('clickable', 'false')
                else: target.set('bounds', '[0,0][144,144]')
                with self.subTest(label=label, operation=operation), self.assertRaises(AssertionError): header_value(tree)
            if label not in ('后退', '前进'):
                tree = ET.parse(HEADER).getroot(); described(tree, label).set('enabled', 'false')
                with self.subTest(label=label), self.assertRaises(AssertionError): header_value(tree)
        tree = ET.parse(HEADER).getroot(); described(tree, '刷新网页').set('content-desc', '停止加载')
        self.assertIn('停止加载', header_value(tree)['browserActionBounds'])

    def test_header_geometry_environment_identity_and_native_ancestors_remain_required(self):
        for wide in (False, True):
            for operation in ('address', 'ancestor', 'viewport', 'order', 'name', 'capsule-center'):
                tree = ET.parse(WIDE if wide else HEADER).getroot()
                address = next(n for n in tree.iter('node') if n.get('content-desc', '').startswith('当前网址 '))
                parents = {c: p for p in tree.iter() for c in p}
                capsule = next(n for n in tree.iter('node') if n.get('content-desc', '').startswith('当前环境：'))
                if operation == 'address': address.set('bounds', '[49,249][1032,393]')
                elif operation == 'ancestor': parents[parents[address]].set('package', 'foreign.package')
                elif operation == 'viewport': address.set('bounds', '[48,249][3000,393]')
                elif operation == 'order':
                    row = parents[address]; child = row[0]; row.remove(child); row.append(child)
                elif operation == 'name': capsule.set('text', '截断…')
                else:
                    l,t,r,b = CONTRACT.bounds(capsule); capsule.set('bounds', f'[{l+3},{t}][{r+3},{b}]')
                with self.subTest(wide=wide, operation=operation), self.assertRaises(AssertionError): header_value(tree, wide)

    def test_current_device_consumers_explicitly_select_browser_contract(self):
        for path, function in (('tests/gecko/run_device.py', 'exercise_workspace_roundtrip'),
                               ('tests/gecko/run_ui_visuals.py', 'conversation_header')):
            calls = [n for n in ast.walk(ast.parse((ROOT/path).read_text()))
                     if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == function]
            self.assertEqual(len(calls), 1)
            self.assertEqual([(k.arg, k.value.value) for k in calls[0].keywords
                              if k.arg == 'browser' and isinstance(k.value, ast.Constant)], [('browser', True)])
        with self.assertRaises(AssertionError):
            CONTRACT.navigation(browser_workspace(), PACKAGE, conversation=False, selected='环境')
        with self.assertRaises(AssertionError):
            CONTRACT.navigation(xml(screen(False)), PACKAGE, conversation=False, selected='环境', browser=True)
        with self.assertRaises(AssertionError):
            CONTRACT.navigation(browser_workspace(), PACKAGE, conversation=False, selected='环境', browser='true')

    def test_current_roundtrip_uses_two_real_taps_and_returns_to_same_environment(self):
        result, calls, saved = exercise_roundtrip()
        taps = [n for n in calls if n[:3] == ('shell', 'input', 'tap')]
        self.assertEqual(len(taps), result['actualAndroidTaps'])
        self.assertEqual(result['actualAndroidTaps'], 2)
        self.assertTrue(result['returnedToSameEnvironment'])
        self.assertEqual([n['actualAndroidTap']['label'] for n in result['observations']], ['环境', '浏览器'])
        self.assertEqual([n[0] for n in saved], ['production-navigation-environments.xml', 'production-navigation-chat.xml'])
        self.assertEqual(saved[-1][1], HEADER.read_text())
        self.assertFalse(any('dashboardEntry' in n for n in result['observations']))

    def test_wrong_environment_legacy_workspace_or_dashboard_cannot_pass_roundtrip(self):
        for final, management in ((HEADER.read_text().replace('日常会话', '另一环境'), None),
                                  (xml(dashboard_screen()), None), (None, xml(screen(False)))):
            with self.subTest(management=management is not None), self.assertRaises(AssertionError):
                exercise_roundtrip(final, management)

    def test_original_twenty_second_budget_covers_acquisition_and_final_save(self):
        for late_read, late_save in ((True, False), (False, True)):
            with self.subTest(late_read=late_read), self.assertRaisesRegex(AssertionError, '20 second budget'):
                exercise_roundtrip(late_read=late_read, late_save=late_save)


def ready_menu(decoy=False):
    tree = ET.parse(MENU).getroot()
    scroll = next(n for n in tree.iter('node') if n.get('class') == 'android.widget.ScrollView')
    for child in list(scroll): scroll.remove(child)
    target = node(scroll, 'android.widget.Button', text='环境详情', bounds='[78,1500][1002,1662]', clickable='true')
    if decoy:
        fake = ET.Element('node', dict(target.attrib)); fake.set('bounds', '[1,1][145,145]')
        tree.insert(0, fake)
    return tree, target, scroll


class MenuHarness:
    """Compile the real nested functions, controlling only ADB and the clock."""
    def __init__(self, reveal_after=2, decoy=False, late_logcat=False, late_predicate=False):
        self.clock = Clock(); self.calls = []; self.taps = []; self.events = []
        self.state = 'list'; self.swipes = 0
        initial, card = environment_tree()
        node(card, 'android.widget.Button', description='更多操作 日常会话',
             bounds='[840,404][984,548]', clickable='true')
        list_xml = xml(initial); menu_xml = MENU.read_text(); visible_xml = xml(ready_menu(decoy)[0])
        details_xml = xml(dashboard_screen())
        def adb(*parts):
            self.calls.append(parts)
            if parts[:3] == ('shell', 'input', 'swipe'):
                self.swipes += 1
                self.assert_state('menu')
            elif parts[:3] == ('shell', 'input', 'tap'):
                if self.state == 'list': self.state = 'menu'
                else:
                    assert parts[3:] == ('540', '1581'), ('not the validated native details target', parts)
                    self.state = 'details'
            elif parts[:1] == ('logcat',) and late_logcat and self.state == 'menu': self.clock.sleep(35)
            return ''
        def dump(**kwargs):
            assert self.clock.now < kwargs['deadline']
            if self.state == 'list': return list_xml
            if self.state == 'details': return details_xml
            return visible_xml if self.swipes >= reveal_after else menu_xml
        def progress(value, environment):
            result = RUN.details_menu_progress(value, environment)
            if late_predicate and result is not None and result['ready']: self.clock.sleep(35)
            return result
        module = ast.parse((ROOT/'tests/gecko/run_environment_dashboard.py').read_text())
        run = next(n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == 'run')
        names = ('tree', 'dashboard', 'wait', 'click', 'open_details')
        body = [n for n in run.body if isinstance(n, ast.FunctionDef) and n.name in names]
        assert {n.name for n in body} == set(names)
        namespace = dict(vars(RUN), adb=adb, dump=dump, time=self.clock,
                         taps=self.taps, events=self.events, details_menu_progress=progress)
        exec(compile(ast.Module(body=body, type_ignores=[]), '<actual dashboard runner functions>', 'exec'), namespace)
        self.open = namespace['open_details']

    def assert_state(self, state): assert self.state == state


class EnvironmentDetailsScrolling(unittest.TestCase):
    def test_actual_offscreen_menu_and_owned_visible_target_validation(self):
        self.assertEqual(RUN.details_menu_progress(MENU.read_text(), '日常会话'),
                         dict(ready=False, bounds=[78,578,1002,1728]))
        self.assertIsNone(RUN.details_menu_progress(xml(ET.Element('hierarchy')), '日常会话'))
        tree, target, scroll = ready_menu()
        self.assertEqual(RUN.details_menu_progress(xml(tree), '日常会话'), dict(ready=True, bounds=[78,1500,1002,1662]))
        for operation in ('foreign', 'class', 'disabled', 'duplicate', 'unscrollable', 'title-owner', 'close-owner'):
            tree, target, scroll = ready_menu()
            if operation == 'foreign': target.set('package', 'foreign.package')
            elif operation == 'class': target.set('class', 'android.widget.TextView')
            elif operation == 'disabled': target.set('enabled', 'false')
            elif operation == 'duplicate': scroll.append(copy.deepcopy(target))
            elif operation == 'unscrollable':
                target.set('bounds', '[78,1719][1002,1728]'); scroll.set('scrollable', 'false')
            elif operation == 'title-owner': described(tree, '日常会话').set('package', 'foreign.package')
            else: described(tree, '关闭日常会话').set('package', 'foreign.package')
            with self.subTest(operation=operation), self.assertRaises(AssertionError): RUN.details_menu_progress(xml(tree), '日常会话')
        for key, value in (('bounds','[78,1719][1002,1728]'), ('bounds','[0,1500][1002,1662]'), ('visible-to-user','false')):
            tree, target, scroll = ready_menu(); target.set(key, value)
            self.assertFalse(RUN.details_menu_progress(xml(tree), '日常会话')['ready'])

    def test_actual_nested_path_scrolls_native_menu_then_taps_validated_target(self):
        harness = MenuHarness(); result = harness.open('日常会话')
        self.assertIn('环境仪表盘', result)
        swipes = [c for c in harness.calls if c[:3] == ('shell','input','swipe')]
        self.assertEqual(swipes, [('shell','input','swipe','540','1498','540','808','300')]*2)
        self.assertEqual(len(harness.taps), 2)
        self.assertEqual(harness.taps[-1], dict(label='环境详情', description=None, x=540, y=1581))
        self.assertEqual(len(harness.events), 2)
        self.assertTrue(all(e['actualAndroidSwipe']['observedBounds'] == [78,578,1002,1728] for e in harness.events))

    def test_unreachable_details_stops_at_eight_real_scrolls(self):
        harness = MenuHarness(reveal_after=9)
        with self.assertRaisesRegex(AssertionError, 'eight real menu scrolls'): harness.open('日常会话')
        self.assertEqual(harness.swipes, 8)
        self.assertEqual(len(harness.taps), 1)

    def test_whole_xml_text_decoy_cannot_replace_validated_menu_target(self):
        harness = MenuHarness(reveal_after=1, decoy=True)
        self.assertIn('环境仪表盘', harness.open('日常会话'))
        self.assertEqual(harness.taps[-1]['x'], 540)
        self.assertEqual(harness.taps[-1]['y'], 1581)

    def test_original_thirty_five_second_budget_covers_logcat_and_predicate(self):
        for logcat, predicate in ((True, False), (False, True)):
            harness = MenuHarness(reveal_after=0, late_logcat=logcat, late_predicate=predicate)
            with self.subTest(logcat=logcat), self.assertRaisesRegex(AssertionError, 'wait budget expired'):
                harness.open('日常会话')
            self.assertEqual(len(harness.taps), 1)
            self.assertEqual(harness.swipes, 0)


if __name__ == '__main__': unittest.main()
