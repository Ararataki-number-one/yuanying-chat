"""Strict history view controls; actual dashboard transport runs unprojected."""
import ast
from pathlib import Path
import unittest
from unittest.mock import patch

import dashboard_capture_source_compatibility as view
import profile_diagnostic_capture_privacy_test as privacy


ROOT = Path(__file__).resolve().parents[1]


class DashboardCaptureHistoricalView(unittest.TestCase):
    def setUp(self):
        self.current = (ROOT/view.PATH).read_text()

    def test_complete_current_bytes_restore_the_fixed_original_and_all_old_privacy_pins(self):
        self.assertEqual(view.AFTER, (15719, '1c232eeb787787895c99e20a8e5f4b36f309b3828fd9e8b14866655d06a4c01f'))
        self.assertEqual(view.BEFORE, (14358, '7efcea13daac3874bbf8bf945bca3e213d9b3224020738fe5398582e4ecd3e5a'))
        self.assertEqual(view.pin(self.current.encode()), view.AFTER)
        original = view.historical_bundle_source(self.current)
        self.assertEqual(view.pin(original.encode()), view.BEFORE)
        self.assertEqual(view.historical_bundle_source(original), original)
        privacy.verify_accepted_bundle_source(self.current)
        privacy.verify_accepted_bundle_source(original)

    def test_each_missing_duplicate_moved_and_changed_hunk_is_rejected(self):
        for original, current in view.HUNKS:
            mutations = (self.current.replace(current, original, 1),
                         self.current.replace(current, current+current, 1),
                         self.current.replace(current, '', 1)+current,
                         self.current.replace(current, current.replace('\n', '\n# changed\n', 1), 1))
            for value in mutations:
                with self.subTest(hunk=current[:60]), self.assertRaises(AssertionError):
                    view.historical_bundle_source(value)

    def test_new_pin_alone_cannot_hide_changed_context_or_original_functional_code(self):
        mutations = (
            self.current.replace("return kind == 'phase' and path.name in DASHBOARD_CAPTURE_FILES", 'return True', 1),
            self.current.replace("'.png', '.xml'", "'.png', '.xml', '.json'", 1),
            self.current.replace("directory = root / DASHBOARD_CAPTURE_DIR", "directory = root / OUT", 1),
            self.current.replace("assert path.is_file() and not path.is_symlink()", "assert path.is_file()", 1),
            self.current.replace("if target.exists():", "if False:", 1),
            self.current.replace('        scan_diagnostic_capture(path)\n', '', 1),
        )
        for value in mutations:
            self.assertNotEqual(value, self.current)
            with self.subTest(pin=view.pin(value.encode())), patch.object(view, 'AFTER', view.pin(value.encode())), self.assertRaises(AssertionError):
                view.historical_bundle_source(value)

    def test_only_old_oracle_projects_and_actual_pack_restore_still_use_current_source(self):
        original = view.historical_bundle_source(self.current)
        self.assertNotEqual(privacy.functions(self.current)['pack'], privacy.functions(original)['pack'])
        module = privacy.load_bundle()
        self.assertEqual(module.DASHBOARD_CAPTURE_FILES, {
            name+suffix for name in ('light','light-fingerprint','home-return','warm-list','second-environment',
                'workspace-chat','large-font','large-font-fingerprint','landscape','landscape-fingerprint',
                'dark','dark-fingerprint','failure') for suffix in ('.png','.xml')})
        self.assertNotIn('dashboard_capture_source_compatibility', self.current)
        self.assertNotIn('historical_bundle_source', self.current)
        source = (ROOT/'tests/profile_diagnostic_capture_privacy_test.py').read_text()
        uses = [node for node in ast.walk(ast.parse(source)) if isinstance(node,ast.Call)
                and isinstance(node.func,ast.Name) and node.func.id=='historical_bundle_source']
        self.assertEqual(len(uses),1)
        body = privacy.functions(source)['verify_accepted_bundle_source']
        self.assertIn('source=historical_bundle_source(source)', body)
        for text in ('Accepted094 bundle source bytes differ:', 'Exact route diagnostic URL publication addition missing or repeated',
                     'Exact additive pack capture hook missing or repeated', 'Accepted094 pack source bytes differ after exact inverse'):
            self.assertIn(text, body)

    def test_unknown_text_and_nontext_inputs_have_no_projection_fallback(self):
        for value in (None, b'', bytearray(), self.current+'\n', self.current[:-1], 'unknown source'):
            with self.subTest(value_type=type(value).__name__), self.assertRaises(AssertionError):
                view.historical_bundle_source(value)


if __name__ == '__main__': unittest.main()
