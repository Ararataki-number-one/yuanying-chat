"""Exact source views for native geometry; no device or runtime acceptance."""
import ast
import copy
import hashlib
from pathlib import Path
import unittest

import ui_native_geometry_source_compatibility as geometry

ROOT = Path(__file__).resolve().parents[1]
SHA = lambda raw: hashlib.sha256(raw).hexdigest()
REJECTED = (AssertionError, ValueError)
PINS = {
    'tests/gecko/run_ui_visuals.py': (
        47025, '12d0f61c0f53efd5766f37cf34ae5526acadfa287a387eb81855dd2e5943783f',
        47272, '6e1ace5e7fb823c650e2084f717e81aba75934c41f9db3df2e0a12188ba90989'),
}
NATIVE = 'tools/gecko/native_navigation_v2.py'
NATIVE_CURRENT = (33225, '0bec5f0ffe463826ba3fa522a18bfa4b779b38b52a0ab5392b3a5afe0bf30a18')
PREPARATION = ("from ui_test_device import prepare_workflow as prepare_ui_test_device\n"
               "(out/'ui-test-device-isolation.json').write_text(json.dumps(prepare_ui_test_device(adb,serial=args.serial,environment=os.environ),sort_keys=True,indent=2)+'\\n')\n")


def tree_identity(tree):
    return ast.dump(tree, include_attributes=False)


class NativeGeometrySourceCompatibilityTests(unittest.TestCase):
    def test_actual_whole_sources_inverse_and_forward_restore_only_fixed_images(self):
        manifest = geometry.manifest()
        self.assertEqual(set(manifest['files']), set(PINS))
        for path, pins in PINS.items():
            with self.subTest(path=path):
                raw = (ROOT / path).read_bytes()
                self.assertEqual((len(raw), SHA(raw)), pins[2:])
                row = manifest['files'][path]
                self.assertEqual((row['previousBytes'], row['previousSha256'],
                                  row['currentBytes'], row['currentSha256']), pins)
                before = geometry.source_input(raw, path)
                self.assertEqual((len(before), SHA(before)), pins[:2])
                self.assertEqual(geometry.source_input(before, path), before)
                forward = before
                for delta in row['deltas']:
                    previous, current = delta['previous'].encode(), delta['current'].encode()
                    self.assertTrue(previous and current and previous != current)
                    for name, literal in (('previous', previous), ('current', current)):
                        self.assertLessEqual(len(literal), 32768)
                        self.assertEqual((len(literal), SHA(literal)),
                                         (delta[name + 'Bytes'], delta[name + 'Sha256']))
                    self.assertEqual(forward.count(previous), 1)
                    forward = forward.replace(previous, current, 1)
                self.assertEqual(forward, raw)
                self.assertEqual((ROOT / path).read_bytes(), raw)

    def test_every_new_hunk_rejects_missing_duplicate_moved_and_changed_bytes(self):
        for path, row in geometry.manifest()['files'].items():
            raw = (ROOT / path).read_bytes()
            for index, delta in enumerate(row['deltas']):
                current = delta['current'].encode()
                self.assertEqual(raw.count(current), 1)
                removed = raw.replace(current, b'', 1)
                moved = removed + current
                if moved == raw:
                    moved = current + removed
                mutants = (removed, raw.replace(current, current * 2, 1), moved,
                           raw.replace(current, current + b' ', 1))
                for mutant in mutants:
                    with self.subTest(path=path, hunk=index, mutant=SHA(mutant)):
                        self.assertNotEqual(mutant, raw)
                        with self.assertRaises(REJECTED):
                            geometry.source_input(mutant, path)
                        with self.assertRaises(REJECTED):
                            geometry.historical_input(mutant, path)

    def test_source_types_paths_excerpts_and_unowned_original_changes_reject(self):
        for path in PINS:
            raw = (ROOT / path).read_bytes()
            for mutant in (raw + b' ', raw[:100], b'', b'unknown complete source',
                           b'# changed original source\n' + raw):
                with self.subTest(path=path, mutant=SHA(mutant)), self.assertRaises(REJECTED):
                    geometry.source_input(mutant, path)
            for value in (None, raw.decode(), bytearray(raw), memoryview(raw), True):
                with self.assertRaises(REJECTED):
                    geometry.source_input(value, path)
            for value in (None, Path(path), '/' + path, '../' + path, path + '.other'):
                with self.assertRaises(REJECTED):
                    geometry.source_input(raw, value)

    def test_complete_current_formatted_and_two_preparation_ast_variants_restore(self):
        raw = (ROOT / geometry.RUNNER).read_bytes()
        before = geometry.source_input(raw, geometry.RUNNER).decode()
        self.assertEqual(raw.decode().count(PREPARATION), 1)
        self.assertEqual(before.count(PREPARATION), 1)
        for current, previous in (
                (raw.decode(), before),
                (raw.decode().replace(PREPARATION, '', 1), before.replace(PREPARATION, '', 1))):
            for source in (current, '# Formatting only\n' + ast.unparse(ast.parse(current)) + '\n'):
                tree = ast.parse(source)
                result = geometry.runner_tree_input(tree)
                self.assertIs(result, tree)
                self.assertEqual(tree_identity(tree), tree_identity(ast.parse(previous)))
            old_tree = ast.parse(previous)
            saved = copy.deepcopy(old_tree)
            self.assertIs(geometry.runner_tree_input(old_tree), old_tree)
            self.assertEqual(tree_identity(old_tree), tree_identity(saved))

    def test_ast_excerpts_extra_workload_and_original_deadline_drift_reject(self):
        source = (ROOT / geometry.RUNNER).read_text()
        self.assertIn('deadline=time.monotonic()+35;readiness_scrolls=0', source)
        drift = source.replace('deadline=time.monotonic()+35;readiness_scrolls=0',
                               'deadline=time.monotonic()+36;readiness_scrolls=0', 1)
        tree = ast.parse(source)
        partial = ast.Module(body=[copy.deepcopy(next(node for node in tree.body
                                if isinstance(node, ast.FunctionDef) and node.name == 'capture'))], type_ignores=[])
        for value in (None, ast.Module(body=[], type_ignores=[]), partial,
                      ast.parse(source + '\nunreviewed_extra_action = True\n'),
                      ast.parse(drift)):
            with self.assertRaises(REJECTED):
                geometry.runner_tree_input(value)

    def test_immutable_original_json_files_and_actual_producers_remain_raw(self):
        pins = {
            'tests/fixtures/ui-checkpoint-source-deltas.json': 'efaa8da45f2697d95a0d514be8cd404260eed1f59595dd4c08b5c2ee8f37d22e',
            'tests/fixtures/ui-quick-sheet-source-deltas.json': 'c0588f2e30e6250bb446ecf472ffe3c2d7f3bf77c471d3cc16cdf845deb385e4',
            'tests/fixtures/ui-observer-source-deltas.json': '998637d381722c943cb32517cb1c72e092d0d0db7581e0f7c9103d74303b42c8',
            'tests/fixtures/ui-navigation-source-deltas.json': '98c2c894fc4eda4adc28d06064943af7b68a99e9c4270b2ed32dafc21bf80775',
        }
        before = {path: (ROOT / path).read_bytes() for path in (*PINS, *pins, NATIVE)}
        geometry.manifest()
        for path, raw in before.items():
            self.assertEqual((ROOT / path).read_bytes(), raw)
            if path in pins:
                self.assertEqual(SHA(raw), pins[path])
            else:
                self.assertNotIn('ui_native_geometry_source_compatibility', raw.decode())
        self.assertEqual((len(before[NATIVE]), SHA(before[NATIVE])), NATIVE_CURRENT)

    def test_explicit_history_port_is_pure_and_grants_no_unknown_owned_acceptance(self):
        for path in PINS:
            raw = (ROOT / path).read_bytes()
            saved = bytes(raw)
            self.assertEqual(geometry.historical_input(raw, path), geometry.source_input(raw, path))
            self.assertEqual(raw, saved)
            self.assertEqual((ROOT / path).read_bytes(), saved)
            with self.assertRaises(REJECTED):
                geometry.historical_input(raw + b' ', path)
        unrelated = b'Unowned inputs still face their existing strict guard.'
        self.assertIs(geometry.historical_input(unrelated, 'tests/unowned-source.py'), unrelated)
        native = (ROOT / NATIVE).read_bytes()
        with self.assertRaises(REJECTED):
            geometry.source_input(native, NATIVE)
        self.assertIs(geometry.historical_input(native, NATIVE), native)
        self.assertEqual((ROOT / NATIVE).read_bytes(), native)


if __name__ == '__main__':
    unittest.main(verbosity=2)
