"""Finite source-input metadata controls; actual capture execution stays raw."""
import ast
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import ui_capture_dependency_source_compatibility as layer
import ui_checkpoint_source_compatibility as checkpoint
import ui_quick_sheet_source_compatibility as quick

ROOT = Path(__file__).resolve().parents[1]
sha = lambda raw: hashlib.sha256(raw).hexdigest()


class CaptureDependencySourceControls(unittest.TestCase):
    def test_actual_inverse_and_all_original_class_bodies_are_exact(self):
        raw = (ROOT / layer.PATH).read_bytes()
        before = layer.source_input(raw)
        self.assertEqual((len(raw), sha(raw)), layer.AFTER)
        self.assertEqual((len(before), sha(before)), layer.BEFORE)
        self.assertIs(layer.source_input(before), before)
        def classes(source):
            return {n.name: ast.get_source_segment(source.decode(), n)
                    for n in ast.parse(source).body if isinstance(n, ast.ClassDef)}
        self.assertEqual(classes(raw), classes(before))
        self.assertEqual(sum(n.name.startswith('test_') for n in ast.walk(ast.parse(before))
                             if isinstance(n, ast.FunctionDef)), 45)

    def test_original_json_and_all_other_rows_are_unchanged_without_input_mutation(self):
        raw = layer.CHECKPOINT.read_bytes()
        self.assertEqual(sha(raw), layer.CHECKPOINT_SHA256)
        original = json.loads(raw)
        saved = copy.deepcopy(original)
        current = layer.wrap_checkpoint_manifest(lambda: original)()
        self.assertEqual(original, saved)
        self.assertEqual(set(current), set(original))
        for key in original:
            if key != 'files': self.assertEqual(current[key], original[key])
        for path, row in original['files'].items():
            if path != layer.PATH: self.assertEqual(current['files'][path], row)
        self.assertEqual(current['files'][layer.PATH]['deltas'][:2], original['files'][layer.PATH]['deltas'])
        self.assertEqual(layer.CHECKPOINT.read_bytes(), raw)
        self.assertEqual(sha((ROOT / 'tests/fixtures/ui-quick-sheet-source-deltas.json').read_bytes()),
                         'c0588f2e30e6250bb446ecf472ffe3c2d7f3bf77c471d3cc16cdf845deb385e4')
        original['files'][layer.PATH]['reviewedBytes'] += 1
        with self.assertRaises(AssertionError): layer.wrap_checkpoint_manifest(lambda: original)()

    def test_actual_checkpoint_and_quick_history_forward_inverse_keep_old_goldens(self):
        raw = (ROOT / layer.PATH).read_bytes()
        saved = bytes(raw)
        before = checkpoint.source_input(raw, layer.PATH)
        self.assertEqual(sha(before), '8ab2a6335b9f313e38cb52deb4b7265ee1be3e8fefc4009d5ef5c3825c40d0c6')
        self.assertEqual(checkpoint.history_input(raw, layer.PATH), before)
        self.assertEqual(quick.manifest()['host']['reviewedSha256'], sha(before))
        for delta in checkpoint.manifest()['files'][layer.PATH]['deltas']:
            old, new = delta['previous'].encode(), delta['current'].encode()
            self.assertEqual(before.count(old), 1)
            before = before.replace(old, new, 1)
        self.assertEqual(before, raw)
        self.assertEqual(raw, saved)
        self.assertIn(b'protocol_for_variant = _capture_dependency.protocol_for_variant', raw)

    def test_missing_duplicate_changed_moved_and_other_body_mutations_reject(self):
        raw = (ROOT / layer.PATH).read_bytes()
        chunk = layer.manifest()['delta']['current'].encode()
        removed = raw.replace(chunk, b'', 1)
        for value in (removed, raw.replace(chunk, chunk * 2, 1), raw.replace(chunk, chunk + b' ', 1),
                      chunk + removed, raw + b' ', raw[:100],
                      raw.replace(b'len(gestures), 8', b'len(gestures), 9', 1)):
            self.assertNotEqual(value, raw)
            with self.assertRaises(AssertionError): layer.source_input(value)
            with self.assertRaises(AssertionError): checkpoint.source_input(value, layer.PATH)
        for value in (None, raw.decode(), bytearray(raw), memoryview(raw)):
            with self.assertRaises(AssertionError): layer.source_input(value)

    def test_unreviewed_fixture_redirects_or_bytes_cannot_expand_the_view(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'changed.json'
            path.write_bytes(layer.FIXTURE.read_bytes() + b' ')
            with patch.object(layer, 'FIXTURE', path), self.assertRaises(AssertionError): layer.manifest()
        for path in ('tests/gecko/run_ui_visuals.py', 'tools/gecko/ui_visual_capture.py',
                     'tools/gecko/native_navigation_v2.py', layer.PATH):
            self.assertNotIn('ui_capture_dependency_source_compatibility', (ROOT / path).read_text())


if __name__ == '__main__': unittest.main()
