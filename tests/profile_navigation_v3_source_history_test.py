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
    def test_current_capture_producer_retains_original_readiness_deadlines(self):
        path = ROOT/'tests/compact-chrome-capture-host/run.py'
        spec = importlib.util.spec_from_file_location('current_capture', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        source = (ROOT/'tests/gecko/run_ui_visuals.py').read_text()
        proof = module.verify_current_compact_ui_source(source)
        self.assertEqual(proof['currentNavigationContract'], 4)
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


if __name__ == '__main__':
    unittest.main()
