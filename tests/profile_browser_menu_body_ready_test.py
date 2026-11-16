"""Replay original C10 incomplete-menu observations at host transport boundaries.

The original Android case remains failed. Subsequent complete frames below are
controlled inputs from an earlier observation, not a claim that C10 recovered.
"""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools/gecko'))
import capture_glass_navigation as capture
import workspace_navigation_contract_v3 as current

PACKAGE = 'local.pocketchat.test'
LABEL = '进入专注阅读'
FIXTURE = ROOT/'tests/fixtures/browser-menu-original-incomplete-body.json'


class OriginalMenuBodyReadinessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = json.loads(FIXTURE.read_text())
        cls.frames = {key:value['rawXml'] for key,value in cls.original['observations'].items()}

    def setUp(self):
        self.display = capture.WIDTH, capture.HEIGHT, capture.DENSITY
        capture.set_display(1236, 2676, 480)

    def tearDown(self):
        capture.set_display(*self.display)

    def test_original_artifact_and_failed_frames_remain_exact(self):
        self.assertEqual(hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),
                         'b460107f9fa81b96ea7b17d040d8a251a36183677dc57b79c90646d4053bf584')
        self.assertEqual(self.original['sourceCommit'], '668e1266c8412b8196cf169e475b8a8eccd5dd31')
        self.assertEqual(self.original['runId'], '43843598199')
        self.assertEqual(self.original['artifactSha256'],
                         '6e00d2a41808899974948a662992ef411d91bfd15a12176b932736ea41d27414')
        self.assertIs(self.original['recordedFailureOnly'], True)
        self.assertEqual(self.original['originalCaseStatus'], 'failed')
        self.assertEqual(self.original['originalCaseErrorType'], 'TimeoutExpired')
        for value in self.original['observations'].values():
            raw = value['rawXml'].encode()
            self.assertEqual(len(raw), value['bytes'])
            self.assertEqual(hashlib.sha256(raw).hexdigest(), value['sha256'])
        self.assertEqual(self.frames['incompleteOpened'], self.frames['incompleteBeforeScroll'])
        self.assertFalse(current.menu_body_ready(self.frames['incompleteOpened'], PACKAGE))
        self.assertTrue(current.menu_body_ready(self.frames['earlierCompleteSameCase'], PACKAGE))
        self.assertTrue(current.menu_body_ready(self.frames['afterFirstScroll'], PACKAGE))
        self.assertEqual(current.menu_action(self.frames['earlierCompleteSameCase'], PACKAGE, LABEL)['bounds'],
                         [78, 1145, 1158, 1316])
        self.assertIsNone(capture.button(self.frames['afterFirstScroll'], LABEL))

    def test_exact_original_producer_scrolls_the_incomplete_body(self):
        original = self.original['originalProducer']
        self.assertEqual(original['fileSha256'],
                         '442e368bd95a2c4d550a4fab37190f2ea93b237bcf2ae164fd2bacfc8bed6eb7')
        self.assertEqual(hashlib.sha256(original['rawFunction'].encode()).hexdigest(),
                         '5b1c010bbce6d5087312b03ee5331ffd734741c0f0ef3d236ba18ab0c8782d89')
        namespace = dict(capture.__dict__)
        exec(compile(original['rawFunction'], 'original-C10-menu_action', 'exec'), namespace)
        adb = mock.Mock(side_effect=RuntimeError('Stop host replay at the first real input boundary'))
        inputs = []
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(capture.time, 'monotonic', return_value=100):
            with self.assertRaisesRegex(RuntimeError, 'first real input boundary'):
                namespace['menu_action'](mock.Mock(), adb, self.frames['incompleteOpened'], LABEL,
                                         directory, 'original', 120, inputs)
        original_input = self.original['originalInputs'][0]
        self.assertEqual(inputs[0]['hierarchySha256'], original_input['hierarchySha256'])
        self.assertEqual(inputs[0]['start'], original_input['start'])
        self.assertEqual(inputs[0]['end'], original_input['end'])
        self.assertEqual(adb.call_args.args,
                         ('shell', 'input', 'touchscreen', 'swipe', '618', '2412', '618', '786', '300'))

    def test_current_producers_reread_without_scrolling_the_incomplete_body(self):
        incomplete, full = self.frames['incompleteOpened'], self.frames['earlierCompleteSameCase']
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(capture.time, 'monotonic', return_value=100):
            read = mock.Mock(side_effect=[incomplete, full]); adb = mock.Mock(); inputs = []
            raw, target = capture.menu_action(SimpleNamespace(read=read), adb, incomplete, LABEL,
                                              directory, 'current', 120, inputs)
            self.assertEqual(raw, full)
            self.assertEqual(capture.bounds(target), (78, 1145, 1158, 1316))
            self.assertEqual([call.kwargs for call in read.call_args_list], [{'deadline':120}]*2)
            self.assertEqual((Path(directory)/'current-menu-0.xml').read_text(), incomplete)
            self.assertEqual((Path(directory)/'current-menu-1.xml').read_text(), incomplete)
            self.assertEqual((Path(directory)/'current-menu-2.xml').read_text(), full)
            adb.assert_not_called(); self.assertEqual(inputs, [])
        with mock.patch.object(current.time, 'monotonic', return_value=100):
            read = mock.Mock(side_effect=[incomplete, incomplete, full]); adb = mock.Mock(); scrolls = []
            raw, target = current.seek_menu_action(adb, read, PACKAGE, LABEL, deadline=120, scrolls=scrolls)
            self.assertEqual(raw, full); self.assertEqual(target['bounds'], [78, 1145, 1158, 1316])
            self.assertEqual([call.kwargs for call in read.call_args_list], [{'deadline':120}]*3)
            adb.assert_not_called(); self.assertEqual(scrolls, [])

    def test_fake_hidden_foreign_or_external_actions_do_not_make_the_body_ready(self):
        source = ET.fromstring(self.frames['earlierCompleteSameCase'])
        original = next(n for n in source.iter('node') if n.get('text') == LABEL)
        for fault in ('foreign', 'hidden', 'disabled', 'outside', 'clipped-outside', 'webview-parent', 'hidden-parent'):
            tree = ET.fromstring(self.frames['incompleteOpened'])
            scroller = next(n for n in tree.iter('node') if n.get('class') == 'android.widget.ScrollView')
            target = copy.deepcopy(original)
            if fault == 'foreign': target.set('package', 'foreign.package')
            elif fault == 'hidden': target.set('visible-to-user', 'false')
            elif fault == 'disabled': target.set('enabled', 'false')
            elif fault == 'clipped-outside': target.set('bounds', '[78,600][1158,771]')
            parent = scroller
            if fault == 'outside': parent = tree
            elif fault in ('webview-parent', 'hidden-parent'):
                parent = ET.SubElement(scroller, 'node', {'package':PACKAGE,
                    'class':'android.webkit.WebView' if fault == 'webview-parent' else 'android.widget.LinearLayout',
                    'visible-to-user':'false' if fault == 'hidden-parent' else 'true'})
            parent.append(target)
            with self.subTest(fault=fault):
                self.assertFalse(current.menu_body_ready(ET.tostring(tree, encoding='unicode'), PACKAGE))

    def test_missing_or_ambiguous_real_modal_is_not_a_retryable_empty_body(self):
        for fault in ('missing-heading', 'missing-close', 'duplicate-close', 'foreign-scroller'):
            tree = ET.fromstring(self.frames['incompleteOpened'])
            parents = {child:parent for parent in tree.iter() for child in parent}
            title = next(n for n in tree.iter('node') if n.get('text') == '浏览器菜单')
            close = next(n for n in tree.iter('node') if n.get('content-desc') == '关闭浏览器菜单')
            if fault == 'missing-heading': parents[title].remove(title)
            elif fault == 'missing-close': parents[close].remove(close)
            elif fault == 'duplicate-close': parents[close].append(copy.deepcopy(close))
            else: next(n for n in tree.iter('node') if n.get('class') == 'android.widget.ScrollView').set('package', 'foreign.package')
            with self.subTest(fault=fault), self.assertRaises(AssertionError):
                current.menu_body_ready(ET.tostring(tree, encoding='unicode'), PACKAGE)

    def test_original_empty_body_cannot_authorize_a_replayed_scroll(self):
        raw = self.frames['incompleteBeforeScroll']
        scroll = dict(label=LABEL, rawXml=raw, xmlSha256=hashlib.sha256(raw.encode()).hexdigest(),
            bounds=[78,714,1158,2484], **{'from':[618,2130], 'to':[618,1068]},
            durationMs=320, actualAndroidInput=True)
        with self.assertRaisesRegex(AssertionError, 'incomplete menu body'):
            current.verify_menu_scrolls([scroll], PACKAGE, LABEL)

    def test_late_or_failed_reread_cannot_extend_the_same_twenty_seconds(self):
        incomplete, full = self.frames['incompleteOpened'], self.frames['earlierCompleteSameCase']
        for producer in ('glass', 'shared'):
            for failure in ('late', 'transport'):
                clock = [100.0]; adb = mock.Mock(); observations = []
                def read(*, deadline):
                    observations.append(deadline)
                    if failure == 'transport': raise RuntimeError('Original transport failure')
                    clock[0] = deadline+.001
                    return full
                with self.subTest(producer=producer,failure=failure), tempfile.TemporaryDirectory() as directory, \
                        mock.patch.object(current.time, 'monotonic', side_effect=lambda:clock[0]):
                    with self.assertRaises((TimeoutError, AssertionError, RuntimeError)):
                        if producer == 'glass':
                            capture.menu_action(SimpleNamespace(read=read), adb, incomplete, LABEL,
                                                directory, 'late', 120, [])
                        else:
                            frames = iter([incomplete])
                            def first_read(*, deadline):
                                try: return next(frames)
                                except StopIteration: return read(deadline=deadline)
                            current.seek_menu_action(adb, first_read, PACKAGE, LABEL, deadline=120, scrolls=[])
                    adb.assert_not_called(); self.assertEqual(observations, [120])

    def test_read_only_waits_preserve_the_original_eight_and_twelve_scroll_limits(self):
        incomplete, full_tail = self.frames['incompleteOpened'], self.frames['afterFirstScroll']
        for producer, limit in (('glass',12), ('shared',8)):
            frames = iter([incomplete, incomplete])
            deadlines = []
            def read(*, deadline):
                deadlines.append(deadline)
                return next(frames, full_tail)
            adb = mock.Mock(); inputs = []
            with self.subTest(producer=producer), tempfile.TemporaryDirectory() as directory, \
                    mock.patch.object(current.time, 'monotonic', return_value=100):
                with self.assertRaises((AssertionError, ValueError)):
                    if producer == 'glass':
                        capture.menu_action(SimpleNamespace(read=read), adb, incomplete, LABEL,
                                            directory, 'limit', 120, inputs)
                    else:
                        current.seek_menu_action(adb, read, PACKAGE, LABEL, deadline=120, scrolls=inputs)
            self.assertEqual(adb.call_count, limit); self.assertEqual(len(inputs), limit)
            self.assertTrue(all(value == 120 for value in deadlines))
            if producer == 'shared':
                self.assertTrue(current.verify_menu_scrolls(inputs, PACKAGE, LABEL))

    def test_glass_still_rejects_a_target_visible_only_after_the_twelfth_scroll(self):
        namespace = dict(capture.__dict__)
        exec(compile(self.original['originalProducer']['rawFunction'], 'original-C10-menu_action', 'exec'), namespace)
        tail, full = self.frames['afterFirstScroll'], self.frames['earlierCompleteSameCase']
        for name, producer in (('original',namespace['menu_action']), ('current',capture.menu_action)):
            for last_scroll in (11,12):
                read = mock.Mock(side_effect=[tail]*(last_scroll-1)+[full])
                adb = mock.Mock(); inputs = []
                with self.subTest(producer=name,last_scroll=last_scroll), tempfile.TemporaryDirectory() as directory, \
                        mock.patch.object(capture.time, 'monotonic', return_value=100):
                    def run():
                        return producer(SimpleNamespace(read=read), adb, tail, LABEL,
                                        directory, name, 120, inputs)
                    if last_scroll == 12:
                        with self.assertRaisesRegex(ValueError, 'not reachable in 12 observed scrolls'):
                            run()
                    else:
                        raw, target = run()
                        self.assertEqual(raw, full)
                        self.assertEqual(capture.bounds(target), (78,1145,1158,1316))
                self.assertEqual(adb.call_count, last_scroll)
                self.assertEqual(read.call_count, last_scroll)
                self.assertEqual(len(inputs), last_scroll)
                self.assertEqual([call.kwargs for call in read.call_args_list], [{'deadline':120}]*last_scroll)


if __name__ == '__main__':
    unittest.main(verbosity=2)
