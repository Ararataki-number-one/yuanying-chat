"""Exact source-oracle controls only; never Android, rendering or tap acceptance."""
import ast
import hashlib
from pathlib import Path
import unittest

import ui_observer_source_compatibility as source_input
import ui_visual_preservation_contract as original_ui

ROOT = Path(__file__).resolve().parents[1]
PREVIOUS = {
    'tests/gecko/run_ui_visuals.py': 'e955b67f4e1afefe6a5253875ca527a54b8a72c789e17c0903bc2c395bd3c99d',
    'tests/gecko/UiVisualIntegrationActivity.java': '2f51f18edd70c63ee0b10e5020b21574a6c030e8c248e7900297a252f0318949',
    'tests/gecko/DownloadLocationLayoutEvidence.java': '61cadf4de2e0926d21e874e59c4bdb321587c184cbd1eb5998acd4f54de84556',
    'tests/ui_visual_preservation_contract.py': '4b6aff72ee501af4c1d4d7eab96e36c44de1a2cc9102522b569011b9ccadb99e',
    'tests/ui_runner14_source_contract.py': '07b478fb52a3e0200d0b30a201e4ecb128ae15b452a3d4b87e338b92043e1a87',
    'tests/profile_ui_settings_services11_test.py': '5abed3062f56ade2e93f09cf7ca765baf6e6a89632f54ba560bd6527e48ae65e',
}


class UiObserverSourceCompatibilityTests(unittest.TestCase):
    def test_whole_sources_restore_fixed_real_e21_bytes_and_roundtrip(self):
        manifest = source_input.manifest()
        self.assertEqual(set(PREVIOUS), set(manifest['files']))
        for path, expected in PREVIOUS.items():
            current = (ROOT / path).read_bytes()
            original = source_input.source_input(current, path)
            self.assertEqual(hashlib.sha256(original).hexdigest(), expected)
            for delta in manifest['files'][path]['deltas']:
                self.assertEqual(original.count(delta['previous'].encode()), 1)
                original = original.replace(delta['previous'].encode(), delta['current'].encode(), 1)
            self.assertEqual(original, current)

    def test_unknown_missing_duplicate_relocated_and_changed_context_are_rejected(self):
        for path, row in source_input.manifest()['files'].items():
            raw = (ROOT / path).read_bytes()
            changes = [raw + b'\n', b'unknown', b'']
            for delta in row['deltas']:
                current = delta['current'].encode()
                changes.extend([raw.replace(current, b'', 1), raw.replace(current, current * 2, 1),
                                current + raw.replace(current, b'', 1),
                                raw.replace(current, current + b' ', 1)])
            for changed in changes:
                self.assertNotEqual(changed, raw)
                with self.subTest(path=path, sha256=hashlib.sha256(changed).hexdigest()), self.assertRaises(AssertionError):
                    source_input.source_input(changed, path)

    def test_raw_types_relative_paths_and_incomplete_excerpts_fail_closed(self):
        raw = (ROOT / source_input.RUNNER).read_bytes()
        for value in (None, raw.decode(), bytearray(raw), raw[:1024]):
            with self.assertRaises(AssertionError):source_input.source_input(value, source_input.RUNNER)
        for path in (None, Path(source_input.RUNNER), '/'+source_input.RUNNER, '../'+source_input.RUNNER,
                     'tests/gecko/other.py', 'tests/gecko/../gecko/run_ui_visuals.py'):
            with self.assertRaises(AssertionError):source_input.source_input(raw, path)
        capture = next(node for node in ast.parse(raw).body if isinstance(node, ast.FunctionDef) and node.name == 'capture')
        for tree in (capture, ast.Module(body=[capture], type_ignores=[]), ast.Module(body=[], type_ignores=[])):
            with self.assertRaises(AssertionError):source_input.original_runner_tree(tree)

    def test_formatted_and_no_preparation_ast_inputs_keep_all_original_goldens(self):
        raw = (ROOT / source_input.RUNNER).read_bytes()
        old = source_input.source_input(raw, source_input.RUNNER)
        block = ("from ui_test_device import prepare_workflow as prepare_ui_test_device\n"
                 "(out/'ui-test-device-isolation.json').write_text(json.dumps(prepare_ui_test_device(adb,serial=args.serial,environment=os.environ),sort_keys=True,indent=2)+'\\n')\n")
        for current, previous in ((raw.decode(), old.decode()), (raw.decode().replace(block, '', 1), old.decode().replace(block, '', 1))):
            for value in (current, '# coding: utf-8\n# Formatting only\n' + ast.unparse(ast.parse(current)) + '\n'):
                restored = source_input.original_runner_tree(ast.parse(value.encode()))
                self.assertEqual(source_input.tree_sha(restored), source_input.tree_sha(ast.parse(previous.encode())))
                report = original_ui.verify_shared_ui_source(value)
                self.assertEqual(report['normalizedModuleAstSha256'], '5c528802063ccba23d6cc0c36726c8ad3fee41efa44aef29c9f498f8b8e331f1')
                self.assertEqual(report['normalizedCaptureAstSha256'], '7bfb8cf6cabcce321ba9841a216dbb035f97ceee76384191d55543c80ebaf4d5')
                self.assertIs(report['actualAndroidExecution'], False)

    def test_old_predicates_and_fresh_scope_mutations_never_normalize_away(self):
        source = (ROOT / source_input.RUNNER).read_text()
        changes = [("assert '已选 8 个' in xml", 'assert True'),
                   ('deadline=time.monotonic()+35;readiness_scrolls=0', 'deadline=time.monotonic()+36;readiness_scrolls=0'),
                   ('readiness_scrolls<8', 'readiness_scrolls<9'),
                   ("if value.get('nonce')==label_nonce:payloads.append(raw)", 'payloads.append(raw)'),
                   (".decode('utf-8')", ".decode('utf-8',errors='replace')"),
                   ('verify_download_location(record,source)', 'verify_download_location(record)'),
                   ('verify_captures(records,source)', 'verify_captures(records)'),
                   ("'visualParentNonce',invocation_nonce", "'visualParentNonce',nonce")]
        for before, after in changes:
            self.assertEqual(source.count(before), 1)
            changed = source.replace(before, after, 1)
            with self.subTest(before=before):
                with self.assertRaises(AssertionError):source_input.source_input(changed.encode(), source_input.RUNNER)
                with self.assertRaises(AssertionError):original_ui.verify_shared_ui_source(changed)
        tree = ast.parse(source)
        selected = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'observe_scrolled_download')
        tree.body.remove(selected);tree.body.append(selected)
        with self.assertRaises(AssertionError):source_input.original_runner_tree(tree)

    def test_only_explicit_historical_source_calls_change_guard_inputs(self):
        path = 'tests/ui_runner14_source_contract.py'
        actual = (ROOT / path).read_bytes()
        previous = source_input.source_input(actual, path)
        def functions(raw):
            text = raw.decode()
            return {node.name: ast.get_source_segment(text, node) for node in ast.parse(text).body if isinstance(node, ast.FunctionDef)}
        before, after = functions(previous), functions(actual)
        self.assertEqual(before, {key: after[key] for key in before})
        guard = 'tests/ui_visual_preservation_contract.py'
        receipt = original_ui.verify_download_visual_fixture_source((ROOT / 'tests/gecko/UiVisualIntegrationActivity.java').read_bytes())
        self.assertEqual(receipt['originalFixtureSha256'], '0e6b5e11649a0a7a9e6e2badf1cd2c6194b4b0cecd632dc9094fb97d09a37b0e')
        self.assertEqual(receipt['selectedFixtureSha256'], hashlib.sha256((ROOT / 'tests/gecko/UiVisualIntegrationActivity.java').read_bytes()).hexdigest())
        previous_guard = source_input.source_input((ROOT / guard).read_bytes(), guard).decode()
        fixture_guard = next(node for node in ast.parse(previous_guard).body if isinstance(node, ast.FunctionDef) and node.name == 'verify_download_visual_fixture_source')
        self.assertEqual(ast.get_source_segment(previous_guard, fixture_guard).count("text=raw.decode('utf-8')"), 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
