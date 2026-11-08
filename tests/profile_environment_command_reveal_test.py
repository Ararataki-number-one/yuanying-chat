"""Retained real manager XML with host-only ADB/clock doubles.

These tests execute current reveal/click code. Replaying XML in this host does
not create Android observations or establish that a device run passed.
"""
import ast
import copy
import hashlib
import json
from pathlib import Path
import re
import sys
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/gecko'))
import native_navigation_v2 as nav

FIXTURES = ROOT / 'tests/fixtures/native-navigation-v2'
WIDTH, HEIGHT, DENSITY = 1080, 1920, 480
SHA = lambda raw: hashlib.sha256(raw).hexdigest()
SCROLLED = (FIXTURES / 'canonical-a9-manager-scrolled.xml').read_text()
TOP = (FIXTURES / 'canonical-a9-manager-top.xml').read_text()


def mutated(xml, action):
    root = ET.fromstring(xml)
    parents = {child: parent for parent in root.iter() for child in parent}
    action(root, parents)
    return ET.tostring(root, encoding='unicode')


def command_node(root):
    return next(node for node in root.iter('node')
                if node.get('class') == 'android.widget.Button' and node.get('content-desc') == '搜索操作')


class Clock:
    def __init__(self, now=100.):
        self.now = now

    def monotonic(self):
        return self.now


class EnvironmentCommandRevealTests(unittest.TestCase):
    def driver(self, sequence, *, clock=None, deadline=135.):
        clock = clock or Clock()
        calls, dumps = [], []
        pending = iter(sequence)

        def dump(*, deadline):
            dumps.append(deadline)
            clock.now += .1
            return next(pending)

        def adb(*parts):
            calls.append(parts)
            clock.now += .3
            return ''

        return clock, adb, dump, calls, dumps

    def test_exact_actual_fixtures_and_provenance_reproduce_fifteen_old_predicate_misses(self):
        provenance_raw = (FIXTURES / 'canonical-a9-provenance.json').read_bytes()
        self.assertEqual(SHA(provenance_raw), '1c964638618da9fbe701824dcfc56704a1e240253b418a7c11a87ae3bf889025')
        provenance = json.loads(provenance_raw)
        self.assertEqual(provenance['sourceCommit'], 'a9daefb514a4e47126cc51c79813a0daedae779a')
        self.assertEqual((provenance['runId'], provenance['runAttempt'], provenance['artifactId']),
                         (42509705450, 1, 13631855036))
        pins = {'canonical-a9-manager-scrolled.xml': (21143, 'ddf07643bcb836bf28f3928be1624f95a8815801e978765e88f6410824e2d4db'),
                'canonical-a9-manager-top.xml': (17413, '733e365fa7e23a653448367777386ef437ac4f9d2e86c3c64d22d5155bc8c978')}
        for name, (size, digest) in pins.items():
            raw = (FIXTURES / name).read_bytes()
            self.assertEqual((len(raw), SHA(raw)), (size, digest))
            record = next(row for row in provenance['files'] if row['fixture'] == name)
            self.assertEqual((record['bytes'], record['sha256']), (size, digest))
        # Fifteen host replays of the exact retained, successfully captured XML
        # reproduce the old predicate. The original device timeline remains in
        # the canonical artifact; these repetitions are not new device dumps.
        for _ in range(15):
            self.assertIn('环境管理', SCROLLED)
            self.assertNotIn('搜索操作', SCROLLED)
            self.assertFalse('环境管理' in SCROLLED and '搜索操作' in SCROLLED)
            self.assertIsNone(nav.manager_command_entry(SCROLLED, WIDTH, HEIGHT, DENSITY))

    def test_scrolled_manager_uses_observed_downward_swipe_and_returns_fresh_real_top_xml(self):
        clock, adb, dump, calls, dumps = self.driver([SCROLLED, TOP])
        with patch.object(nav.time, 'monotonic', clock.monotonic):
            value = nav.reveal_manager_command_entry(adb, dump, WIDTH, HEIGHT, DENSITY, deadline=135.)
        self.assertEqual(value, TOP)
        self.assertEqual(dumps, [135., 135.])
        self.assertEqual(calls, [('shell', 'input', 'swipe', '540', '493', '540', '1297', '300')])
        target = nav.manager_command_entry(value, WIDTH, HEIGHT, DENSITY)
        self.assertEqual(target.get('bounds'), '[342,225][486,369]')
        self.assertEqual(target.get('class'), 'android.widget.Button')
        self.assertEqual(target.get('enabled'), 'true')
        self.assertEqual(target.get('clickable'), 'true')
        self.assertEqual(nav._bounds(target, WIDTH, HEIGHT), [342, 225, 486, 369])
        self.assertFalse(any('tap' in call for call in calls), 'The reveal helper must not click a target')

    def test_already_visible_action_returns_same_observation_without_input(self):
        clock, adb, dump, calls, dumps = self.driver([TOP])
        with patch.object(nav.time, 'monotonic', clock.monotonic):
            self.assertEqual(nav.reveal_manager_command_entry(adb, dump, WIDTH, HEIGHT, DENSITY, deadline=135.), TOP)
        self.assertEqual(calls, [])
        self.assertEqual(dumps, [135.])

    def test_original_dashboard_hook_clicks_only_once_after_reveal_using_fresh_target(self):
        tree = ast.parse((ROOT / 'tools/gecko/native_navigation_v2.py').read_text())
        method = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'run_dashboard_v2')
        click = copy.deepcopy(next(node for node in method.body if isinstance(node, ast.FunctionDef) and node.name == 'click'))
        loop = next(node for node in method.body if isinstance(node, ast.Try)).body[0]
        start = next(index for index, node in enumerate(loop.body) if isinstance(node, ast.Assign)
                     and any(isinstance(target, ast.Name) and target.id == 'command_deadline' for target in node.targets))
        block = copy.deepcopy(loop.body[start:start + 3])
        self.assertEqual(len(block), 3)
        self.assertIn('reveal_manager_command_entry', ast.unparse(block[1]))
        self.assertEqual(ast.unparse(block[2]), "click(xml, description='搜索操作')")
        clock, adb, dump, calls, dumps = self.driver([SCROLLED, TOP])
        taps = []
        environment = dict(time=nav.time, ET=ET, re=re, PACKAGE=nav.PACKAGE, _bounds=nav._bounds,
                           reveal_manager_command_entry=nav.reveal_manager_command_entry,
                           width=360, height=640, adb=adb, dump=dump, taps=taps)
        with patch.object(nav.time, 'monotonic', clock.monotonic):
            exec(compile(ast.fix_missing_locations(ast.Module(body=[click, *block], type_ignores=[])),
                         '<actual dashboard manager reveal and original click>', 'exec'), environment)
        self.assertEqual(dumps, [135., 135.])
        self.assertEqual(calls, [('shell', 'input', 'swipe', '540', '493', '540', '1297', '300'),
                                 ('shell', 'input', 'tap', '414', '297')])
        self.assertEqual(taps, [dict(label=None, description='搜索操作', x=414, y=297, bounds=[342, 225, 486, 369])])

    def test_expired_deadline_never_dumps_or_issues_input(self):
        for deadline in (99., 100.):
            with self.subTest(deadline=deadline), patch.object(nav.time, 'monotonic', return_value=100.), \
                    self.assertRaises(TimeoutError):
                nav.reveal_manager_command_entry(lambda *args: self.fail('Expired input'),
                    lambda **kwargs: self.fail('Expired dump'), WIDTH, HEIGHT, DENSITY, deadline=deadline)

    def test_dump_that_exhausts_original_deadline_cannot_approve_target_or_issue_swipe(self):
        for value in (SCROLLED, TOP):
            clock = Clock()
            calls, dumps = [], []
            def dump(*, deadline):
                dumps.append(deadline);clock.now = deadline
                return value
            with self.subTest(targetVisible=value == TOP), patch.object(nav.time, 'monotonic', clock.monotonic), \
                    self.assertRaises(TimeoutError):
                nav.reveal_manager_command_entry(lambda *args: calls.append(args), dump,
                    WIDTH, HEIGHT, DENSITY, deadline=135.)
            self.assertEqual(dumps, [135.])
            self.assertEqual(calls, [])

    def test_finite_deadline_is_mandatory(self):
        for value in (None, '135', True, float('nan'), float('inf'), float('-inf')):
            with self.subTest(deadline=value), self.assertRaises(ValueError):
                nav.reveal_manager_command_entry(lambda *args: self.fail('Invalid input'),
                    lambda **kwargs: self.fail('Invalid dump'), WIDTH, HEIGHT, DENSITY, deadline=value)

    def test_missing_action_is_bounded_to_five_swipes_under_the_same_deadline(self):
        clock, adb, dump, calls, dumps = self.driver([SCROLLED] * 6)
        with patch.object(nav.time, 'monotonic', clock.monotonic), self.assertRaises(ValueError):
            nav.reveal_manager_command_entry(adb, dump, WIDTH, HEIGHT, DENSITY, deadline=135.)
        self.assertEqual(dumps, [135.] * 6)
        self.assertEqual(calls, [('shell', 'input', 'swipe', '540', '493', '540', '1297', '300')] * 5)

    def test_wrong_manager_or_duplicate_action_rejects_before_any_input(self):
        wrong = mutated(TOP, lambda root, parents: next(node for node in root.iter('node')
                        if node.get('text') == '环境管理').set('text', '其他页面'))
        def duplicate(root, parents):
            node = command_node(root);parents[node].append(copy.deepcopy(node))
        for value in (wrong, mutated(TOP, duplicate)):
            clock, adb, dump, calls, dumps = self.driver([value])
            with self.subTest(xmlSha256=SHA(value.encode())), patch.object(nav.time, 'monotonic', clock.monotonic), \
                    self.assertRaises(ValueError):
                nav.reveal_manager_command_entry(adb, dump, WIDTH, HEIGHT, DENSITY, deadline=135.)
            self.assertEqual(calls, [])

    def test_hidden_or_clipped_ancestor_does_not_approve_an_otherwise_complete_target(self):
        def hidden(root, parents):
            parents[command_node(root)].set('visible-to-user', 'false')
        def clipped(root, parents):
            parents[command_node(root)].set('bounds', '[342,225][486,300]')
        for action in (hidden, clipped):
            value = mutated(TOP, action)
            with self.subTest(mutation=action.__name__), self.assertRaises(ValueError):
                nav.manager_command_entry(value, WIDTH, HEIGHT, DENSITY)

    def test_disabled_unclickable_small_or_outside_target_is_rejected(self):
        changes = (('enabled', 'false'), ('clickable', 'false'),
                   ('bounds', '[342,225][485,369]'), ('bounds', '[342,225][486,368]'),
                   ('bounds', '[-1,225][143,369]'), ('bounds', '[1000,225][1144,369]'))
        for key, value in changes:
            current = mutated(TOP, lambda root, parents: command_node(root).set(key, value))
            with self.subTest(field=key, value=value), self.assertRaises(ValueError):
                nav.manager_command_entry(current, WIDTH, HEIGHT, DENSITY)
        hidden = mutated(TOP, lambda root, parents: command_node(root).set('visible-to-user', 'false'))
        self.assertIsNone(nav.manager_command_entry(hidden, WIDTH, HEIGHT, DENSITY))

    def test_absent_or_ambiguous_scrollview_cannot_trigger_a_gesture(self):
        def no_scroll(root, parents):
            node = next(node for node in root.iter('node') if node.get('class') == 'android.widget.ScrollView')
            parents[node].remove(node)
        def double_scroll(root, parents):
            node = next(node for node in root.iter('node') if node.get('class') == 'android.widget.ScrollView')
            parents[node].append(copy.deepcopy(node))
        for action in (no_scroll, double_scroll):
            value = mutated(SCROLLED, action)
            clock, adb, dump, calls, dumps = self.driver([value])
            with self.subTest(mutation=action.__name__), patch.object(nav.time, 'monotonic', clock.monotonic), \
                    self.assertRaises(ValueError):
                nav.reveal_manager_command_entry(adb, dump, WIDTH, HEIGHT, DENSITY, deadline=135.)
            self.assertEqual(calls, [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
