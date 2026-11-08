"""Original IME regressions and explicit host geometry models, never UI acceptance.

Run42492339110/a1 API35 supplied the four unchanged controlled-document XMLs.
Its WM snapshots preceded the editor and contain no shown IME frame. The shown
WM frames below are deliberately synthetic host inputs; they establish neither
device rendering nor successful keyboard interaction on a new source.
"""
import ast
import copy
import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest import mock
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'tests/fixtures'
sys.path.insert(0, str(ROOT / 'tools/gecko'))
import glass_ui_validation as glass

METADATA_SHA = '808186fa4b907ff948b4da7c26242d56ccca28dd0b85a0c05ba27de0332fc7e6'
XML_SHAS = {
    'glass-keyboard-narrow-before.xml': 'b216dc3ef0c9d34185353b8c20468aa603dd2ee65be46b06149e898e841913d6',
    'glass-keyboard-narrow-after.xml': '59024e96a4ec25488f41e77bc4ff313421ccd47585ced440f36b1265110803f2',
    'glass-keyboard-landscape-before.xml': '286f81c5ece8ece84e7e0e75b2991bb92ff60a2e2d01c227f7f719efedc71b1e',
    'glass-keyboard-landscape-after.xml': '73d5592901f025e2be58cab444848e9711b122abf38a1b671fbc180c8f8006ec',
}


def xml(name, phase='after'):
    return (FIXTURES / ('glass-keyboard-' + name + '-' + phase + '.xml')).read_text()


def rectangles(value, *, text=None, view_class=None):
    return [tuple(map(int, re.findall(r'-?\d+', node.get('bounds', ''))))
            for node in ET.fromstring(value).iter('node')
            if (text is None or node.get('text') == text)
            and (view_class is None or node.get('class') == view_class)]


def mutate(value, select, change):
    tree = ET.fromstring(value)
    node = next(node for node in tree.iter('node') if select(node))
    change(node, tree)
    return ET.tostring(tree, encoding='unicode')


def shown_ime():
    """Exact original service/manager excerpts, with their original offsets."""
    data = json.loads((FIXTURES / 'glass-keyboard-observations.json').read_text())
    row = data['cases'][0]
    return ''.join(row[key]['text'] for key in
                   ('inputMethodShown', 'inputMethodWindow', 'inputMethodService'))


def synthetic_wm(width=960, height=2220, top=1371):
    """Explicit host WM model using the original Android InsetsSource syntax."""
    return ('        InsetsSource id=3 type=ime frame=[0,' + str(top) + ']['
            + str(width) + ',' + str(height)
            + '] visible=true flags= sideHint=BOTTOM boundingRects=null\n')


class Clock:
    def __init__(self):
        self.now = 100.0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class KeyboardTransportModel:
    """Host command ordering only; XML bytes are the actual old observations."""
    def __init__(self, values, *, ime=None, wm=None):
        self.values = list(values)
        self.ime = shown_ime() if ime is None else ime
        self.wm = synthetic_wm() if wm is None else wm
        self.clock = Clock()
        self.events, self.read_deadlines, self.adb_timeouts, self.taps = [], [], [], []

    def adb(self, *parts, **kwargs):
        self.events.append(('adb', parts))
        self.clock.now += .02
        self.adb_timeouts.append(kwargs.get('timeout'))
        if parts == ('shell', 'dumpsys', 'input_method'):
            return self.ime.encode()
        if parts == ('shell', 'dumpsys', 'window', 'displays'):
            return self.wm.encode()
        raise AssertionError('Unexpected command or input: ' + repr(parts))

    def read(self, deadline=None):
        self.events.append(('read', deadline))
        self.read_deadlines.append(deadline)
        self.clock.now += .02
        if len(self.values) > 1:
            return self.values.pop(0)
        return self.values[0]

    def tap(self, node, reason):
        self.events.append(('tap', node.get('bounds')))
        self.taps.append((node.attrib.copy(), reason))


class GlassKeyboardGeometryTest(unittest.TestCase):
    def check_geometry(self, value, *, ime_frame=(0, 1371, 960, 2220),
                       width=960, height=2220):
        return glass.url_editor_keyboard_geometry(value, list(ime_frame), width, height, 480)

    def run_cancel(self, transport, *, deadline=130.0, predicate=None,
                   width=960, height=2220):
        if predicate is None:
            predicate = lambda value: '打开网址' in value and '取消' in value
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.object(glass.time, 'monotonic', transport.clock.monotonic), \
                    mock.patch.object(glass.time, 'sleep', transport.clock.sleep):
                value = glass.cancel_keyboard_editor(capture=transport, adb=transport.adb,
                    tap=transport.tap, out=Path(directory), stem='host-url-keyboard',
                    width=width, height=height, density=480,
                    sha=lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest(),
                    predicate=predicate, deadline=deadline)
                return value, {path.name: path.read_bytes() for path in Path(directory).iterdir()}

    def test_original_xml_and_excerpt_provenance_is_bound_to_exact_failed_source(self):
        raw = (FIXTURES / 'glass-keyboard-observations.json').read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), METADATA_SHA)
        data = json.loads(raw)
        self.assertEqual((data['sourceCommit'], data['sourceTree'], data['runId'], data['api']),
            ('06a802663075664b75aa9d19184d9c02b6bab7c9',
             '23c64e1e3b592e58105e888c0223859959ea5279', '42492339110', 35))
        self.assertEqual(len(data['cases']), 2)
        for row in data['cases']:
            self.assertIs(row['originalPostImeWmAcquired'], False)
            self.assertIn('mInputShown=true', row['inputMethodShown']['text'])
            self.assertIn('mIsInputViewShown=true', row['inputMethodService']['text'])
            self.assertIn('visible=false', row['preEditorWindowIme']['text'])
            for name in ('inputMethodShown', 'inputMethodWindow', 'inputMethodService', 'preEditorWindowIme'):
                excerpt = row[name]
                self.assertEqual(hashlib.sha256(excerpt['text'].encode()).hexdigest(),
                                 excerpt['excerptSha256'])
            for item in row['xml']:
                raw_xml = (FIXTURES / item['fixture']).read_bytes()
                self.assertEqual(len(raw_xml), item['originalBytes'])
                self.assertEqual(hashlib.sha256(raw_xml).hexdigest(), item['originalSha256'])
                self.assertEqual(item['originalSha256'], XML_SHAS[item['fixture']])

    def test_actual_old_cancel_points_miss_the_post_ime_buttons_in_both_scenes(self):
        data = json.loads((FIXTURES / 'glass-keyboard-observations.json').read_text())
        for row, short in zip(data['cases'], ('narrow', 'landscape')):
            with self.subTest(case=short):
                before = rectangles(xml(short, 'before'), text='取消')[0]
                after = rectangles(xml(short), text='取消')[0]
                tap = row['originalCancelInput']
                self.assertEqual((tap['x'], tap['y']),
                                 ((before[0] + before[2]) // 2, (before[1] + before[3]) // 2))
                self.assertGreater(tap['y'], after[3])
                self.assertGreater(tap['atUnixNs'], row['oldObservationAtUnixNs'])
        self.assertEqual(rectangles(xml('landscape'), view_class='android.widget.EditText'), [])

    def test_original_narrow_post_ime_xml_fits_the_explicit_host_keyboard_model(self):
        value = self.check_geometry(xml('narrow'))
        self.assertEqual(list(value['editBounds']), [54, 666, 906, 843])
        self.assertEqual(list(value['cancelBounds']), [396, 964, 660, 1127])
        self.assertTrue(value['checks'])
        self.assertTrue(all(value['checks'].values()))

    def test_early_xml_coordinates_overlap_ime_and_are_rejected(self):
        for name, frame, width, height in (
                ('narrow', (0, 1371, 960, 2220), 960, 2220),
                ('landscape', (0, 453, 2676, 1236), 2676, 1236)):
            with self.subTest(case=name), self.assertRaises(ValueError):
                self.check_geometry(xml(name, 'before'), ime_frame=frame, width=width, height=height)

    def test_actual_landscape_compression_is_rejected_even_with_valid_cancel_target(self):
        value = xml('landscape')
        self.assertEqual(rectangles(value, text='取消'), [(1978, 297, 2242, 441)])
        self.assertEqual(rectangles(value, view_class='android.widget.EditText'), [])
        self.assertEqual(rectangles(value, text='网址或搜索'), [(188, 238, 2488, 249)])
        with self.assertRaises(ValueError):
            self.check_geometry(value, ime_frame=(0, 453, 2676, 1236), width=2676, height=1236)

    def test_hidden_disabled_missing_or_duplicate_editors_are_rejected(self):
        original = xml('narrow')
        select = lambda node: node.get('class') == 'android.widget.EditText'
        changes = [lambda node, tree: node.set('visible-to-user', 'false'),
                   lambda node, tree: node.set('enabled', 'false'),
                   lambda node, tree: node.set('focused', 'false'),
                   lambda node, tree: node.set('bounds', '[54,666][906,666]'),
                   lambda node, tree: node.set('package', 'another.package'),
                   lambda node, tree: node.set('class', 'android.widget.TextView'),
                   lambda node, tree: tree.append(copy.deepcopy(node))]
        for index, change in enumerate(changes):
            with self.subTest(mutation=index), self.assertRaises(ValueError):
                self.check_geometry(mutate(original, select, change))

    def test_all_three_buttons_retain_48dp_targets(self):
        for label in ('主页', '取消', '前往'):
            def shrink(node, tree):
                left, top, right, bottom = rectangles(ET.tostring(node, encoding='unicode'))[0]
                node.set('bounds', f'[{left},{top}][{right},{top + 143}]')
            with self.subTest(label=label), self.assertRaises(ValueError):
                self.check_geometry(mutate(xml('narrow'), lambda node: node.get('text') == label, shrink))

    def test_missing_disabled_or_duplicate_native_actions_are_rejected(self):
        changes = [lambda node, tree: node.set('text', '取'),
                   lambda node, tree: node.set('enabled', 'false'),
                   lambda node, tree: node.set('clickable', 'false'),
                   lambda node, tree: node.set('package', 'another.package'),
                   lambda node, tree: tree.append(copy.deepcopy(node))]
        for index, change in enumerate(changes):
            with self.subTest(mutation=index), self.assertRaises(ValueError):
                self.check_geometry(mutate(xml('narrow'), lambda node: node.get('text') == '取消', change))

    def test_editor_or_button_clipping_and_keyboard_occlusion_are_rejected(self):
        changes = [
            (lambda node: node.get('resource-id') == 'android:id/customPanel',
             lambda node, tree: node.set('bounds', '[0,479][960,700]')),
            (lambda node: node.get('text') == '取消',
             lambda node, tree: node.set('bounds', '[396,1352][660,1515]')),
            (lambda node: node.get('text') == '前往',
             lambda node, tree: node.set('visible-to-user', 'false')),
        ]
        for index, (select, change) in enumerate(changes):
            with self.subTest(mutation=index), self.assertRaises(ValueError):
                self.check_geometry(mutate(xml('narrow'), select, change))

    def test_only_one_positive_screen_ime_frame_is_accepted(self):
        self.assertEqual(list(glass.visible_ime_frame(synthetic_wm(), 960, 2220)), [0, 1371, 960, 2220])
        metadata = json.loads((FIXTURES / 'glass-keyboard-observations.json').read_text())
        for raw in (metadata['cases'][0]['preEditorWindowIme']['text'],
                    synthetic_wm().replace('visible=true', 'visible=false'),
                    synthetic_wm() + synthetic_wm(top=1400),
                    synthetic_wm(width=961), synthetic_wm(top=-1),
                    synthetic_wm(top=2220)):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                glass.visible_ime_frame(raw, 960, 2220)

    def test_fresh_stable_xml_after_shown_ime_drives_exactly_one_cancel_tap(self):
        model = KeyboardTransportModel([xml('narrow', 'before'), xml('narrow'), xml('narrow')])
        result, files = self.run_cancel(model)
        self.assertEqual(len(model.taps), 1)
        self.assertEqual(model.taps[0][0]['bounds'], '[396,964][660,1127]')
        self.assertEqual(result['xml'], xml('narrow'))
        self.assertEqual(list(result['geometry']['cancelBounds']), [396, 964, 660, 1127])
        self.assertGreaterEqual(len(model.read_deadlines), 3)
        self.assertEqual(set(model.read_deadlines), {130.0})
        self.assertTrue(all(value is not None and 0 < value <= 30 for value in model.adb_timeouts))
        self.assertEqual(model.events[-1][0], 'tap')
        for index, event in enumerate(model.events):
            if event[0] == 'read':
                self.assertEqual(model.events[index - 2:index], [
                    ('adb', ('shell', 'dumpsys', 'input_method')),
                    ('adb', ('shell', 'dumpsys', 'window', 'displays'))])
        self.assertTrue(any('mInputShown=true' in data.decode('utf-8', 'replace') for data in files.values()))

    def test_both_geometry_and_ime_frame_must_be_consecutively_stable(self):
        model = KeyboardTransportModel([xml('narrow'), xml('narrow', 'before'),
                                        xml('narrow'), xml('narrow')])
        self.run_cancel(model)
        self.assertEqual(len(model.read_deadlines), 4)
        self.assertEqual(len(model.taps), 1)

        class MovingImeModel(KeyboardTransportModel):
            def __init__(self):
                super().__init__([xml('narrow')])
                self.frames = [1371, 1400, 1400]

            def adb(self, *parts, **kwargs):
                if parts == ('shell', 'dumpsys', 'window', 'displays'):
                    self.wm = synthetic_wm(top=self.frames.pop(0))
                return super().adb(*parts, **kwargs)

        moving = MovingImeModel()
        result, unused_files = self.run_cancel(moving)
        self.assertEqual(len(moving.read_deadlines), 3)
        self.assertEqual(len(moving.taps), 1)
        self.assertEqual(result['geometry']['imeBounds'], [0, 1400, 960, 2220])

    def test_single_tap_uses_the_visible_cancel_checked_by_geometry(self):
        def add_hidden_cancel(node, tree):
            hidden = copy.deepcopy(node)
            hidden.set('visible-to-user', 'false')
            hidden.set('bounds', '[396,1352][660,1515]')
            tree.insert(0, hidden)
        value = mutate(xml('narrow'), lambda node: node.get('text') == '取消', add_hidden_cancel)
        self.assertEqual(self.check_geometry(value)['cancelBounds'], [396, 964, 660, 1127])
        model = KeyboardTransportModel([value])
        self.run_cancel(model)
        self.assertEqual(len(model.taps), 1)
        self.assertEqual(model.taps[0][0]['bounds'], '[396,964][660,1127]')

    def test_input_callback_failure_is_not_treated_as_read_only_not_ready(self):
        class InputFailureModel(KeyboardTransportModel):
            def tap(self, node, reason):
                super().tap(node, reason)
                raise ValueError('Synthetic failure after input injection')
        model = InputFailureModel([xml('narrow')])
        with self.assertRaisesRegex(ValueError, 'Synthetic failure after input injection'):
            self.run_cancel(model, deadline=101.0)
        self.assertEqual(len(model.taps), 1)

    def test_absent_keyboard_or_invalid_layout_never_injects_or_replays_input(self):
        models = [KeyboardTransportModel([xml('narrow')],
                      ime=shown_ime().replace('=true', '=false')),
                  KeyboardTransportModel([xml('narrow', 'before')]),
                  KeyboardTransportModel([xml('narrow')],
                      wm=synthetic_wm().replace('visible=true', 'visible=false'))]
        for index, model in enumerate(models):
            with self.subTest(model=index):
                with self.assertRaises((ValueError, TimeoutError)):
                    self.run_cancel(model, deadline=100.5)
                self.assertEqual(model.taps, [])
                self.assertLessEqual(model.clock.now, 100.75)
                self.assertTrue(all(deadline == 100.5 for deadline in model.read_deadlines))

    def test_rejected_route_predicate_cannot_become_a_cancel_input(self):
        model = KeyboardTransportModel([xml('narrow')])
        with self.assertRaises((ValueError, TimeoutError)):
            self.run_cancel(model, deadline=100.5, predicate=lambda value: False)
        self.assertEqual(model.taps, [])

    def test_expired_original_deadline_never_acquires_or_injects(self):
        model = KeyboardTransportModel([xml('narrow')])
        with self.assertRaises(TimeoutError):
            self.run_cancel(model, deadline=100.0)
        self.assertEqual(model.events, [])

    def test_actual_landscape_missing_input_never_reaches_the_single_tap(self):
        model = KeyboardTransportModel([xml('landscape')],
            wm=synthetic_wm(width=2676, height=1236, top=453))
        with self.assertRaises((ValueError, TimeoutError)):
            self.run_cancel(model, deadline=100.5, width=2676, height=1236)
        self.assertEqual(model.taps, [])

    def test_host_hidden_redundant_label_cannot_replace_a_visible_editor(self):
        def hide(node, tree):
            node.set('visible-to-user', 'false')
        value = mutate(xml('narrow'), lambda node: node.get('text') == '网址或搜索', hide)
        result = self.check_geometry(value)
        self.assertEqual(list(result['editBounds']), [54, 666, 906, 843])
        self.assertIsNone(result['labelBounds'])
        value = mutate(value, lambda node: node.get('class') == 'android.widget.EditText', hide)
        with self.assertRaises(ValueError):
            self.check_geometry(value)

    def test_actual_interaction_keeps_original_chat_predicate_and_shared_30_second_deadline(self):
        tree = ast.parse((ROOT / 'tools/gecko/glass_ui_validation.py').read_text())
        suite = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                     and node.name == 'capture_acceptance_suite')
        chat = next(node for node in ast.walk(suite) if isinstance(node, ast.FunctionDef) and node.name == 'chat')
        self.assertEqual(ast.unparse(chat.body[0]),
            "return nav(xml) is not None and capsule(xml) is not None and (not text(xml, '打开网址')) and (not text(xml, '快速切换环境'))")
        method = next(node for node in ast.walk(suite) if isinstance(node, ast.FunctionDef) and node.name == 'interactions')
        calls = [node for node in ast.walk(method) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name) and node.func.id == 'cancel_keyboard_editor']
        self.assertEqual(len(calls), 1)
        deadline = next(keyword.value for keyword in calls[0].keywords if keyword.arg == 'deadline')
        self.assertIsInstance(deadline, ast.Name)
        assignment = next(node for node in ast.walk(method) if isinstance(node, ast.Assign)
                          and any(isinstance(target, ast.Name) and target.id == deadline.id for target in node.targets))
        self.assertEqual(ast.unparse(assignment.value), 'time.monotonic() + 30')
        keyboard = next(node for node in ast.walk(method) if isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Name) and node.func.id == 'artifact'
                        and len(node.args) > 1 and isinstance(node.args[1], ast.Constant)
                        and node.args[1].value == 'url-keyboard')
        self.assertEqual(ast.unparse(next(keyword.value for keyword in keyboard.keywords if keyword.arg == 'deadline')), deadline.id)
        direct_cancel_taps = [node for node in ast.walk(method) if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name) and node.func.id == 'tap'
            and any(isinstance(child, ast.Constant) and child.value == '取消' for child in ast.walk(node))]
        self.assertEqual(direct_cancel_taps, [])


if __name__ == '__main__':
    unittest.main()
