"""Actual viewport regressions; readiness and idle counters cannot establish pixels."""
import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('glass_document_viewport',
    ROOT / 'tools/gecko/glass_document_viewport.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
CHECK = MODULE.require_document_viewport
FIXTURE = ROOT / 'tests/fixtures/glass-document-viewports.json'


class GlassDocumentViewport(unittest.TestCase):
    def samples(self):
        raw = FIXTURE.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),
            '68806256e3b038ea349aa2c09ac26615454f74973416e65357ba3405026d9b2e')
        return json.loads(raw)['samples']

    def valid(self):
        return copy.deepcopy(next(row['observation'] for row in self.samples()
                                  if row['expectedLayout'] == 'nonempty-layout'))

    def test_real_nonempty_texture_layout_samples_are_accepted_without_claiming_pixels(self):
        rows = [row for row in self.samples() if row['expectedLayout'] == 'nonempty-layout']
        self.assertEqual(len(rows), 4)
        self.assertEqual({row['api'] for row in rows}, {'32', '35'})
        for row in rows:
            with self.subTest(api=row['api'], case=row['case']):
                result = CHECK(row['observation'])
                self.assertEqual(result['status'], 'verified')
                self.assertIn('original PNG/MP4 visual inspection remains required', result['scope'])
                for name in ('innerWidth', 'innerHeight', 'webWidth', 'webHeight'):
                    self.assertEqual(result[name], row['observation'][name])

    def test_actual_default_surface_callback_regression_is_rejected_on_both_apis(self):
        rows = [row for row in self.samples() if row['expectedLayout'] == 'reject-empty-layout']
        self.assertEqual(len(rows), 2)
        self.assertEqual({row['api'] for row in rows}, {'32', '35'})
        for row in rows:
            with self.subTest(api=row['api']):
                value = row['observation']
                self.assertIs(value['visibleDocument'], True)
                self.assertEqual(value['loadingCoverVisibility'], 8)
                self.assertGreater(value['webWidth'], 0)
                self.assertGreater(value['webHeight'], 0)
                self.assertEqual((value['innerWidth'], value['innerHeight']), (0, 0))
                with self.assertRaises(ValueError):
                    CHECK(value)

    def test_any_missing_empty_or_invalid_page_or_native_dimension_is_rejected(self):
        for name in ('innerWidth', 'innerHeight', 'webWidth', 'webHeight'):
            for bad in (None, 0, -1, True, '412', float('nan'), float('inf'), -float('inf')):
                with self.subTest(name=name, bad=repr(bad)):
                    value = self.valid()
                    value[name] = bad
                    with self.assertRaises(ValueError):
                        CHECK(value)
            value = self.valid()
            del value[name]
            with self.assertRaises(ValueError):
                CHECK(value)

    def test_obscured_or_unconfirmed_production_document_is_rejected(self):
        for name, bad in (('visibleDocument', False), ('visibleDocument', 1),
                          ('loadingCoverVisibility', 0), ('loadingCoverVisibility', 4),
                          ('loadingCoverVisibility', 8.0), ('loadingCoverVisibility', '8')):
            with self.subTest(name=name, bad=bad):
                value = self.valid()
                value[name] = bad
                with self.assertRaises(ValueError):
                    CHECK(value)

    def test_missing_visibility_and_non_object_observations_are_rejected(self):
        for value in (None, [], 'ready', True):
            with self.assertRaises(ValueError):
                CHECK(value)
        for name in ('visibleDocument', 'loadingCoverVisibility'):
            value = self.valid()
            del value[name]
            with self.assertRaises(ValueError):
                CHECK(value)

    def test_every_actual_snapshot_checks_viewport_before_it_is_accepted(self):
        path = ROOT / 'tools/gecko/glass_ui_validation.py'
        tree = ast.parse(path.read_text())
        functions = [node for node in ast.walk(tree)
                     if isinstance(node, ast.FunctionDef) and node.name == 'observed_event']
        self.assertEqual(len(functions), 1)
        function = functions[0]
        calls = [node for node in ast.walk(function) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name) and node.func.id == 'require_document_viewport']
        self.assertEqual(len(calls), 1)
        self.assertEqual(ast.unparse(calls[0].args[0]), "value['result']")
        returns = [node for node in ast.walk(function) if isinstance(node, ast.Return)]
        self.assertEqual(len(returns), 1)
        self.assertLess(calls[0].lineno, returns[0].lineno)
        self.assertFalse(any(isinstance(node, ast.Try) for node in ast.walk(function)))


if __name__ == '__main__':
    unittest.main()
