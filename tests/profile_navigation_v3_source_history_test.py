"""Compare the current navigation producer with the actual retained release workload.

This source-history proof requires the fixed Git objects prepared by the full
profile/release workflow. Current-only maintenance uses the independent current
behavior controls without introducing a historical checkout dependency.
"""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class NavigationV3SourceHistory(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = ROOT/'tests/compact-chrome-capture-host/run.py'
        spec = importlib.util.spec_from_file_location('current_capture', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        cls.capture = module

    def test_current_v5_loop_is_selected_independently_of_bottom_contract_four(self):
        source = (ROOT/'tests/gecko/run_ui_visuals.py').read_text()
        members = self.capture.compact_ui_members(source, version=5)
        self.assertEqual(members['UI_NAVIGATION_CONTRACT'].value.value, 4)
        self.assertEqual(members['compactImport'].module, 'compact_chrome_v5')
        with self.assertRaises(AssertionError):
            self.capture.compact_ui_members(source, version=4)

    def test_current_capture_producer_retains_original_readiness_deadlines(self):
        module = self.capture
        source = (ROOT/'tests/gecko/run_ui_visuals.py').read_text()
        proof = module.verify_current_compact_ui_source(source)
        self.assertEqual(proof['currentNavigationContract'], 4)
        self.assertEqual(proof['currentCompactConsumerVersion'], 5)
        self.assertEqual(proof['currentHeaderConsumer']['headerContract'], 5)
        self.assertEqual(proof['currentHeaderConsumer']['navigationContract'], 4)
        self.assertEqual(proof['currentHeaderConsumer']['networkDialogTapCount'], 3)
        self.assertTrue(proof['currentHeaderConsumer']['originalV4ActionsAndDeadlinesPreserved'])
        self.assertFalse(proof['currentHeaderConsumer']['actualAndroidExecution'])
        bad = source.replace('def chrome_event(command,event):\n        deadline=time.monotonic()+20',
                             'def chrome_event(command,event):\n        deadline=time.monotonic()+21', 1)
        self.assertNotEqual(source, bad)
        with self.assertRaises(AssertionError):
            module.verify_current_compact_ui_source(bad)
        for changed in ('UiVisualCapture(', 'UiVisualCapture.unverified('):
            bad = source.replace('UiVisualCapture.for_device(', changed, 1)
            self.assertNotEqual(source, bad)
            with self.subTest(capture=changed), self.assertRaises(AssertionError):
                module.verify_current_compact_ui_source(bad)

    def test_consumer_and_bottom_navigation_bindings_cannot_be_mixed_or_unknown(self):
        source = (ROOT/'tests/gecko/run_ui_visuals.py').read_text()
        changes = (
            ('UI_NAVIGATION_CONTRACT=4', 'UI_NAVIGATION_CONTRACT=3'),
            ('from compact_chrome_v5 import run_case as capture_compact_v5',
             'from compact_chrome_v6 import run_case as capture_compact_v5'),
            ('from compact_chrome_v5 import run_case as capture_compact_v5',
             'from compact_chrome_v5 import unchecked_case as capture_compact_v5'),
            ('capture_compact_v5(adb,lambda', 'capture_compact_v4(adb,lambda'),
            ('capture_compact_v5(adb,lambda', 'capture_compact_v5(dump,lambda'),
        )
        for before, after in changes:
            self.assertEqual(source.count(before), 1)
            with self.subTest(change=after), self.assertRaises(AssertionError):
                self.capture.verify_current_compact_ui_source(source.replace(before, after, 1))

    def test_declared_v4_runner_binding_remains_distinct_from_header_five(self):
        source = (ROOT/'tests/gecko/run_ui_visuals.py').read_text()
        # Controlled runner binding only; this does not recreate historical UI
        # scenes or claim that the current v5 app has old geometry.
        previous = source.replace('compact_chrome_v5', 'compact_chrome_v4').replace('capture_compact_v5', 'capture_compact_v4')
        proof = self.capture.verify_current_compact_ui_source(previous)
        self.assertEqual((proof['currentNavigationContract'], proof['currentCompactConsumerVersion']), (4, 4))
        self.assertNotIn('currentHeaderConsumer', proof)
        self.assertTrue(proof['historicalProofOnly'])

    def test_v5_retains_old_actions_and_requires_real_extension_tap_and_modal_return(self):
        source = (ROOT/'tests/gecko/compact_chrome_v5.py').read_text()
        self.capture.verify_v5_header_consumer(source)
        changes = (
            (",('network-extension',extension['point'],extension['bounds'])", ''),
            ("('network-extension',extension['point'],extension['bounds'])",
             "('network-extension',status['networkTap'],status['bounds'])"),
            ("extension=network_extension(before_status)", "extension=network_extension(sample)"),
            ('tap(name,point,box); raw=observe_network_dialog(dump,package,True)',
             'raw=observe_network_dialog(dump,package,True)'),
            ("adb('shell','input','keyevent','KEYCODE_BACK'); observe_network_dialog(dump,package,False)",
             "adb('shell','input','keyevent','KEYCODE_BACK')"),
            ('headerContract=5,navigationContract=4', 'headerContract=4,navigationContract=4'),
            ('time.monotonic()+20', 'time.monotonic()+21'),
        )
        for before, after in changes:
            self.assertIn(before, source)
            with self.subTest(change=after), self.assertRaises(AssertionError):
                self.capture.verify_v5_header_consumer(source.replace(before, after, 1))


if __name__ == '__main__':
    unittest.main()
