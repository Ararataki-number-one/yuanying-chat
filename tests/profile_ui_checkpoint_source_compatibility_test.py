"""Finite checkpoint source-oracle controls, never Android/UI acceptance."""
import ast
import hashlib
from pathlib import Path
import unittest

import ui_checkpoint_source_compatibility as checkpoint
import ui_quick_sheet_source_compatibility as quick
import ui_visual_preservation_contract as original_ui

ROOT = Path(__file__).resolve().parents[1]
PREPARATION = ("from ui_test_device import prepare_workflow as prepare_ui_test_device\n"
               "(out/'ui-test-device-isolation.json').write_text(json.dumps(prepare_ui_test_device(adb,serial=args.serial,environment=os.environ),sort_keys=True,indent=2)+'\\n')\n")


class UiCheckpointSourceCompatibilityTests(unittest.TestCase):
    def test_actual_current_runner_and_entire_two_snippet_inverse(self):
        raw = (ROOT / checkpoint.RUNNER).read_bytes()
        old = checkpoint.require_current_runner(raw)
        self.assertEqual(checkpoint.sha(raw), checkpoint.RUNNER_CURRENT_SHA256)
        self.assertEqual(checkpoint.sha(old), '65fb205cbb7a466858a0a1869cd4b5388f70026d4e09da078318827e92432f4f')
        self.assertEqual(raw.count(checkpoint.FLAG_DECLARATION.encode()), 1)
        self.assertEqual(raw.count(checkpoint.FLAG_RETURN.encode()), 1)
        self.assertEqual(checkpoint.checkpoint_runner_input(raw).replace(checkpoint.FLAG_DECLARATION.encode(), b'', 1).replace(checkpoint.FLAG_RETURN.encode(), b'', 1), old)
        with self.assertRaises(AssertionError):checkpoint.require_current_runner(old)
        self.assertNotIn('ui_checkpoint_source_compatibility', (ROOT / checkpoint.RUNNER).read_text())
        path = 'tests/gecko_ui_checkpoint_publication_test.py'
        actual = (ROOT / path).read_bytes()
        previous = checkpoint.source_input(actual, path)
        def runtime_functions(raw):
            return {node.name: ast.dump(node, include_attributes=False)
                    for node in ast.walk(ast.parse(raw)) if isinstance(node, ast.FunctionDef)
                    and node.name != 'test_two_opt_in_insertions_inverse_entire_actual_runner_to_exact_before'}
        self.assertEqual(runtime_functions(actual), runtime_functions(previous))
        self.assertEqual(checkpoint.sha(checkpoint.checkpoint_runner_input(raw)), checkpoint.PREFERENCE_PREVIOUS_SHA256)

    def test_four_source_rows_keep_fixed_before_pins_and_forward_roundtrip(self):
        manifest = checkpoint.manifest()
        host = quick.manifest()['host']
        actual = (ROOT / host['path']).read_text()
        classes = {n.name:n for n in ast.parse(actual).body if isinstance(n,ast.ClassDef)}
        for name,methods in host['previousMethods'].items():
            current={n.name:hashlib.sha256(ast.get_source_segment(actual,n).encode()).hexdigest() for n in classes[name].body if isinstance(n,ast.FunctionDef)}
            self.assertEqual(current,methods)
        self.assertEqual(set(manifest['files']), set(checkpoint.PREVIOUS))
        for path, row in manifest['files'].items():
            raw = (ROOT / path).read_bytes()
            old = checkpoint.source_input(raw, path)
            self.assertEqual(checkpoint.sha(old), checkpoint.PREVIOUS[path])
            for delta in row['deltas']:
                self.assertEqual(old.count(delta['previous'].encode()), 1)
                old = old.replace(delta['previous'].encode(), delta['current'].encode(), 1)
            self.assertEqual(old, raw)
            for unknown in (raw + b' ', b'', raw[:64]):
                with self.assertRaises(AssertionError):checkpoint.source_input(unknown, path)
        self.assertEqual(hashlib.sha256((ROOT / 'tests/fixtures/ui-quick-sheet-source-deltas.json').read_bytes()).hexdigest(),
                         'c0588f2e30e6250bb446ecf472ffe3c2d7f3bf77c471d3cc16cdf845deb385e4')
        self.assertEqual(hashlib.sha256((ROOT / 'tests/fixtures/ui-observer-source-deltas.json').read_bytes()).hexdigest(),
                         '998637d381722c943cb32517cb1c72e092d0d0db7581e0f7c9103d74303b42c8')

    def test_complete_formatted_and_no_old_preparation_ast_inputs_still_pass(self):
        current = (ROOT / checkpoint.RUNNER).read_bytes()
        before = checkpoint.require_current_runner(current)
        for raw, old in ((current.decode(), before.decode()),
                         (current.decode().replace(PREPARATION, '', 1), before.decode().replace(PREPARATION, '', 1))):
            for value in (raw, '# coding: utf-8\n# Formatting only\n' + ast.unparse(ast.parse(raw)) + '\n'):
                self.assertEqual(checkpoint.tree_sha(checkpoint.original_runner_tree(ast.parse(value.encode()))),
                                 checkpoint.tree_sha(ast.parse(old.encode())))
                receipt = original_ui.verify_shared_ui_source(value)
                self.assertEqual(receipt['normalizedModuleAstSha256'], original_ui.ORIGINAL_MODULE_AST)
                self.assertEqual(receipt['normalizedCaptureAstSha256'], original_ui.ORIGINAL_CAPTURE_AST)
                self.assertFalse(receipt['actualAndroidExecution'])

    def test_missing_duplicate_moved_default_and_original_timeout_changes_are_rejected(self):
        source = (ROOT / checkpoint.RUNNER).read_text()
        declaration, returned = checkpoint.FLAG_DECLARATION, checkpoint.FLAG_RETURN
        changed = [source.replace(declaration, '', 1), source.replace(returned, '', 1),
                   source.replace(declaration, declaration * 2, 1), source.replace(returned, returned * 2, 1),
                   source.replace(returned, '', 1).replace('    partial=', returned + '    partial=', 1),
                   source.replace(declaration, '', 1) + '\n' + declaration + '\n',
                   source.replace("action='store_true',help='Disable checkpoint", "action='store_true',default=True,help='Disable checkpoint", 1),
                   source.replace("timeout=90).decode(errors='replace')", "timeout=91).decode(errors='replace')", 1),
                   source.replace('deadline=time.monotonic()+35;readiness_scrolls=0', 'deadline=time.monotonic()+36;readiness_scrolls=0', 1),
                   source.replace("assert '已选 8 个' in xml", 'assert True', 1),
                   source.replace(checkpoint.PREFERENCE_CURRENT, checkpoint.PREFERENCE_PREVIOUS, 1),
                   source.replace("'自动检测外部网络响应'", "'unexpected-control'", 1),
                   source.replace(checkpoint.PREFERENCE_CURRENT, checkpoint.PREFERENCE_CURRENT + ';' + checkpoint.PREFERENCE_CURRENT, 1)]
        for value in changed:
            with self.subTest(sha=checkpoint.sha(value.encode())):
                self.assertNotEqual(value, source)
                with self.assertRaises(AssertionError):checkpoint.require_current_runner(value.encode())
                with self.assertRaises(AssertionError):checkpoint.checkpoint_runner_input(value.encode())
                with self.assertRaises(AssertionError):checkpoint.original_runner_tree(ast.parse(value.encode()))
                with self.assertRaises(AssertionError):original_ui.verify_shared_ui_source(value)
        # A complete valid predecessor remains a historical input, never a
        # substitute for the mandatory current raw-source check above.
        old = checkpoint.require_current_runner(source.encode())
        self.assertEqual(checkpoint.history_input(old, checkpoint.RUNNER), old)
        unknown = source.encode() + b' '
        self.assertEqual(checkpoint.history_input(unknown, checkpoint.RUNNER), unknown)
        with self.assertRaises(AssertionError):quick.source_input(unknown, checkpoint.RUNNER)

    def test_types_paths_and_ast_excerpts_cannot_gain_acceptance(self):
        raw = (ROOT / checkpoint.RUNNER).read_bytes()
        for value in (None, raw.decode(), bytearray(raw), memoryview(raw), True):
            with self.assertRaises(AssertionError):checkpoint.source_input(value, checkpoint.RUNNER)
        for path in (None, Path(checkpoint.RUNNER), '../' + checkpoint.RUNNER, '/' + checkpoint.RUNNER, 'unknown.py'):
            with self.assertRaises(AssertionError):checkpoint.source_input(raw, path)
        capture = next(n for n in ast.parse(raw).body if isinstance(n, ast.FunctionDef) and n.name == 'capture')
        for tree in (None, ast.Module(body=[], type_ignores=[]), ast.Module(body=[capture], type_ignores=[])):
            with self.assertRaises(AssertionError):checkpoint.original_runner_tree(tree)


if __name__ == '__main__':
    unittest.main(verbosity=2)
