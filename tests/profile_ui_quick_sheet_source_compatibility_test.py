"""QuickSheet historical source controls; never Android or trusted-tap evidence."""
import ast
import hashlib
from pathlib import Path
import unittest

import ui_observer_source_compatibility as observer
import ui_quick_sheet_source_compatibility as quick
import ui_visual_preservation_contract as original_ui
import ui_runner14_source_contract as runner14

ROOT = Path(__file__).resolve().parents[1]


class QuickSheetSourceCompatibilityTests(unittest.TestCase):
    rejected_counterfeits = 0

    def reject(self, raw, path):
        with self.assertRaises(AssertionError):
            quick.source_input(raw, path)
        type(self).rejected_counterfeits += 1

    def test_exact_source7_whole_bytes_and_forward_roundtrip(self):
        self.assertEqual(quick.BASE_COMMIT, '03d0c4ace70942a3f6899daffac086cc6682885e')
        self.assertEqual(quick.BASE_TREE, 'bfd7bbcdf89ef947dd466dab795e94e83fc992c3')
        for path, row in quick.manifest()['files'].items():
            current = (ROOT / path).read_bytes()
            previous = quick.source_input(current, path)
            self.assertEqual(hashlib.sha256(previous).hexdigest(), quick.PREVIOUS[path])
            self.assertEqual(len(previous), row['previousBytes'])
            for delta in row['deltas']:
                before, after = delta['previous'].encode(), delta['current'].encode()
                self.assertTrue(before and after)
                self.assertEqual(previous.count(before), 1)
                previous = previous.replace(before, after, 1)
            self.assertEqual(previous, current)

    def test_unknown_missing_duplicate_moved_or_altered_hunks_rejected(self):
        for path, row in quick.manifest()['files'].items():
            raw = (ROOT / path).read_bytes()
            for delta in row['deltas']:
                addition = delta['current'].encode()
                remaining = raw.replace(addition, b'', 1)
                moved = remaining + addition
                if moved == raw:
                    moved = addition + remaining
                for changed in (remaining, raw.replace(addition, addition * 2, 1),
                                raw.replace(addition, addition + b' ', 1), moved):
                    self.assertNotEqual(changed, raw)
                    self.reject(changed, path)
            for changed in (b'', b'unknown source', raw + b' ', quick.source_input(raw, path)):
                self.reject(changed, path)

    def test_exact_types_paths_and_complete_ast_required(self):
        raw = (ROOT / quick.RUNNER).read_bytes()
        for changed in (None, raw.decode(), bytearray(raw), memoryview(raw), True, raw[:1024]):
            self.reject(changed, quick.RUNNER)
        for path in (None, Path(quick.RUNNER), '', '../' + quick.RUNNER, '/' + quick.RUNNER,
                     quick.RUNNER.encode(), 'tests/gecko_ui_visual_capture_test.py'):
            self.reject(raw, path)
        for value in (None, b'', ast.Module(body=[], type_ignores=[])):
            with self.assertRaises(AssertionError):
                quick.original_runner_tree(value)
        for value in (None, raw.decode(), bytearray(raw)):
            with self.assertRaises(AssertionError):quick.history_input(value, quick.RUNNER)
        with self.assertRaises(AssertionError):quick.history_input(raw, 'unknown/path')

    def test_complete_current_formatted_and_independent_preparation_ast_variants(self):
        current = (ROOT / quick.RUNNER).read_bytes()
        previous = quick.source_input(current, quick.RUNNER)
        block = ("from ui_test_device import prepare_workflow as prepare_ui_test_device\n"
                 "(out/'ui-test-device-isolation.json').write_text(json.dumps(prepare_ui_test_device(adb,serial=args.serial,environment=os.environ),sort_keys=True,indent=2)+'\\n')\n")
        self.assertEqual(current.decode().count(block), 1)
        for new, old in ((current.decode(), previous.decode()),
                         (current.decode().replace(block, '', 1), previous.decode().replace(block, '', 1))):
            for value in (new, '# coding: utf-8\n' + ast.unparse(ast.parse(new)) + '\n'):
                restored = quick.original_runner_tree(ast.parse(value.encode()))
                self.assertEqual(quick.tree_sha(restored), quick.tree_sha(ast.parse(old.encode())))
                receipt = original_ui.verify_shared_ui_source(value)
                self.assertEqual(receipt['normalizedModuleAstSha256'], '5c528802063ccba23d6cc0c36726c8ad3fee41efa44aef29c9f498f8b8e331f1')
                self.assertEqual(receipt['normalizedCaptureAstSha256'], '7bfb8cf6cabcce321ba9841a216dbb035f97ceee76384191d55543c80ebaf4d5')
                self.assertFalse(receipt['actualAndroidExecution'])

    def test_current_and_old_predicates_cannot_normalize_away(self):
        raw = (ROOT / quick.RUNNER).read_bytes()
        text = raw.decode()
        for before, after in (("quick_environment_sheet(dump(),0,package)", "quick_environment_sheet(dump(),1,package)"),
                              ("deadline=time.monotonic()+20\n        while time.monotonic()<deadline:\n            xml=dump()", "deadline=time.monotonic()+21\n        while time.monotonic()<deadline:\n            xml=dump()"),
                              ("assert '已选 8 个' in xml", 'assert True'),
                              ("if value.get('nonce')==label_nonce:payloads.append(raw)", 'payloads.append(raw)'),
                              ("verify_captures(records,source)", 'verify_captures(records)'),
                              ("'actualDrawerTap':True", "'actualDrawerTap':False")):
            self.assertGreaterEqual(text.count(before), 1)
            changed = text.replace(before, after, 1)
            self.reject(changed.encode(), quick.RUNNER)
            with self.assertRaises(AssertionError):quick.original_runner_tree(ast.parse(changed.encode()))
            with self.assertRaises(AssertionError):original_ui.verify_shared_ui_source(changed)
        tree = ast.parse(raw)
        outer = next(node for node in tree.body if isinstance(node, ast.Try) and node.finalbody)
        helper = next(node for node in outer.body if isinstance(node, ast.FunctionDef) and node.name == 'quick_environment_sheet')
        outer.body.remove(helper);outer.body.append(helper)
        with self.assertRaises(AssertionError):quick.original_runner_tree(tree)

    def test_source6_fixture_goldens_and_original_assertions_unchanged(self):
        fixture = ROOT / 'tests/fixtures/ui-observer-source-deltas.json'
        self.assertEqual(hashlib.sha256(fixture.read_bytes()).hexdigest(), '998637d381722c943cb32517cb1c72e092d0d0db7581e0f7c9103d74303b42c8')
        self.assertEqual(observer.FIXTURE_SHA256, '998637d381722c943cb32517cb1c72e092d0d0db7581e0f7c9103d74303b42c8')
        for path in ('tests/ui_observer_source_compatibility.py', 'tests/profile_ui_observer_source_compatibility_test.py'):
            current = (ROOT / path).read_bytes()
            previous = quick.source_input(current, path)
            def assertions(raw):
                return [ast.dump(node, include_attributes=False) for node in ast.walk(ast.parse(raw)) if isinstance(node, ast.Assert)]
            self.assertEqual(assertions(current), assertions(previous))
        self.assertEqual(observer.source_input((ROOT / quick.RUNNER).read_bytes(), quick.RUNNER),
                         observer.source_input(quick.source_input((ROOT / quick.RUNNER).read_bytes(), quick.RUNNER), quick.RUNNER))

    def test_forwarding_port_still_requires_original_guards_for_unknown_input(self):
        raw = (ROOT / quick.RUNNER).read_bytes()
        self.assertEqual(quick.history_input(raw, quick.RUNNER), quick.source_input(raw, quick.RUNNER))
        predicate_drift = raw.replace("assert '已选 8 个' in xml".encode(), b'assert True', 1)
        for changed in (raw + b' ', b'', predicate_drift):
            self.assertEqual(quick.history_input(changed, quick.RUNNER), changed)
            with self.assertRaises(AssertionError):observer.source_input(changed, quick.RUNNER)
            with self.assertRaises(AssertionError):runner14.require_current_ui14(changed)
        for changed in (b'', predicate_drift):
            with self.assertRaises(AssertionError):original_ui.verify_shared_ui_source(changed.decode())

    def test_actual_host_keeps_current_runner_and_all_thirty_seven_old_methods(self):
        manifest = quick.manifest()
        host = manifest['host']
        raw = (ROOT / host['path']).read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), host['reviewedSha256'])
        self.assertEqual(hashlib.sha256((ROOT / quick.RUNNER).read_bytes()).hexdigest(), '65fb205cbb7a466858a0a1869cd4b5388f70026d4e09da078318827e92432f4f')
        text = raw.decode()
        classes = {node.name: node for node in ast.parse(text).body if isinstance(node, ast.ClassDef)}
        for name, methods in host['previousMethods'].items():
            current = {node.name: hashlib.sha256(ast.get_source_segment(text, node).encode()).hexdigest()
                       for node in classes[name].body if isinstance(node, ast.FunctionDef)}
            self.assertEqual(current, methods)
        self.assertEqual(host['previousTests'], 37)
        self.assertNotIn('ui_quick_sheet_source_compatibility', text)
        self.assertIn('tree = ast.parse(RUNNER.read_text())', text)
        actual = ast.parse((ROOT / quick.RUNNER).read_bytes())
        old = ast.parse(quick.source_input((ROOT / quick.RUNNER).read_bytes(), quick.RUNNER))
        self.assertEqual(len([node for node in ast.walk(actual) if isinstance(node, ast.FunctionDef) and node.name == 'quick_environment_sheet']), 1)
        self.assertFalse(any(isinstance(node, ast.FunctionDef) and node.name == 'quick_environment_sheet' for node in ast.walk(old)))


if __name__ == '__main__':
    unittest.main(verbosity=2)
