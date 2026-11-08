"""Finite historical source inputs only; no v2 producer uses an old image."""
import ast
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import chrome_first_tap_source_compatibility as first
import ui_checkpoint_source_compatibility as checkpoint
import ui_visual_preservation_contract as original

ROOT = Path(__file__).resolve().parents[1]
SHA = lambda value: hashlib.sha256(value).hexdigest()
CHROME = 'tests/gecko/run_chrome_collapse.py'
UI = 'tests/gecko/run_ui_visuals.py'
PREPARATION = ("from ui_test_device import prepare_workflow as prepare_ui_test_device\n"
    "(out/'ui-test-device-isolation.json').write_text(json.dumps(prepare_ui_test_device(adb,serial=args.serial,environment=os.environ),sort_keys=True,indent=2)+'\\n')\n")


class ChromeNavigationV2HistoricalControls(unittest.TestCase):
    def test_runner_append_is_exact_and_the_original_fourteen_controls_stay_fourteen(self):
        raw = (ROOT / CHROME).read_bytes()
        self.assertEqual((len(raw), SHA(raw)), (16331, 'a64eb97979edbf10f392cc74ca018d33a6b9ac8e05266c4d3f4382a876b280b3'))
        preserved = raw[:15834]
        self.assertEqual(SHA(preserved), '630b6ac6be99f47316f4d6a49bf646ed43f5d064309b03588e09a01bb423fe67')
        manifest = first.manifest()
        self.assertEqual(len(manifest['files'][CHROME]['deltas']), 1)
        self.assertEqual(sum(4 * len(row['deltas']) + 3 for path, row in manifest['files'].items()
                             if path != 'tools/gecko/chrome_header_readiness.py'), 14)
        before = first.source_input(raw, CHROME)
        self.assertEqual(SHA(before), 'c2b30b11c52fbca41abfd2df289dcc1f5221194222edb1b6e5170ef0f5a36ac5')
        with self.assertRaises(ValueError):
            first.source_input(preserved, CHROME)

    def test_dispatcher_changes_removal_duplication_or_other_runtime_drift_reject(self):
        raw = (ROOT / CHROME).read_bytes()
        append = raw[15834:]
        mutants = [raw[:15834], raw + append, append + raw[:15834], raw + b' ',
            raw.replace(b'navigation_version=2', b'navigation_version=1', 1),
            raw.replace(b'if navigation_version==1:return run(', b'if navigation_version==2:return run(', 1),
            raw.replace(b'from run_chrome_collapse_v2 import run as run_v2', b'from other import run as run_v2', 1),
            raw.replace(b'return snapshot(label)', b'return before', 1)]
        for mutant in mutants:
            with self.subTest(sha=SHA(mutant)), self.assertRaises(ValueError):
                first.source_input(mutant, CHROME)

    def test_current_whole_ui_inverse_keeps_the_original_checkpoint_golden(self):
        raw = (ROOT / UI).read_bytes()
        self.assertEqual((len(raw), SHA(raw)), (47025, '12d0f61c0f53efd5766f37cf34ae5526acadfa287a387eb81855dd2e5943783f'))
        before = checkpoint.navigation_v2_runner_input(raw)
        self.assertEqual((len(before), SHA(before)), (46016, 'b85896aa5b94e33fb40bbada323d239a66f75c12a39bf9adb2a4ff3e3483e14d'))
        self.assertEqual(SHA(checkpoint.require_current_runner(raw)), '65fb205cbb7a466858a0a1869cd4b5388f70026d4e09da078318827e92432f4f')
        forward = before
        for delta in checkpoint.navigation_v2_manifest()['deltas']:
            previous, current = delta['previous'].encode(), delta['current'].encode()
            self.assertEqual(forward.count(previous), 1)
            self.assertLessEqual(max(len(previous), len(current)), 32768)
            forward = forward.replace(previous, current, 1)
        self.assertEqual(forward, raw)
        with self.assertRaises(AssertionError):
            checkpoint.require_current_runner(before)

    def test_each_new_whole_source_hunk_rejects_missing_duplicate_moved_or_changed_bytes(self):
        raw = (ROOT / UI).read_bytes()
        count = 0
        for delta in checkpoint.navigation_v2_manifest()['deltas']:
            chunk = delta['current'].encode()
            self.assertEqual(raw.count(chunk), 1)
            removed = raw.replace(chunk, b'', 1)
            moved = removed + chunk
            if moved == raw:
                moved = chunk + removed
            for mutant in (removed, raw.replace(chunk, chunk * 2, 1),
                           raw.replace(chunk, chunk + b' ', 1), moved):
                self.assertNotEqual(mutant, raw)
                with self.assertRaises(AssertionError):
                    checkpoint.navigation_v2_runner_input(mutant)
                with self.assertRaises(AssertionError):
                    checkpoint.source_input(mutant, UI)
                count += 1
        self.assertEqual(count, 28)

    def test_complete_ast_variants_restore_only_the_two_original_allowed_modules(self):
        raw = (ROOT / UI).read_text()
        manifest = checkpoint.navigation_v2_manifest()
        old_pairs = checkpoint.manifest()['runnerAst']['allowedModulePairs']
        self.assertEqual(len(old_pairs), 2)
        self.assertEqual(len(manifest['astPairs']), 2)
        for source in (raw, raw.replace(PREPARATION, '', 1)):
            for variant in (source, '# coding: utf-8\n' + ast.unparse(ast.parse(source)) + '\n'):
                tree = ast.parse(variant.encode())
                value = manifest['astPairs'][checkpoint.tree_sha(tree)]
                self.assertEqual(len(value['operations']), 7)
                returned = checkpoint.navigation_v2_tree_input(tree)
                self.assertIs(returned, tree)
                self.assertEqual(checkpoint.tree_sha(tree), value['previousAstSha256'])
                self.assertIn(value['previousAstSha256'], old_pairs)
                self.assertEqual(checkpoint.tree_sha(checkpoint.original_runner_tree(ast.parse(variant.encode()))),
                                 old_pairs[value['previousAstSha256']])
                self.assertTrue(original.verify_shared_ui_source(variant)['originalWorkloadSemanticsPreserved'])

    def test_unknown_v2_ast_and_changes_to_original_budgets_or_v1_body_reject(self):
        raw = (ROOT / UI).read_text()
        for before, after in (
                ('navigation_protocol==2', 'navigation_protocol==1'),
                ('native_navigation=validate_chat(', 'native_navigation=chat_ready('),
                ('from run_chrome_collapse import run_current as', 'from run_chrome_collapse import run as'),
                ('identity=identity,font_scale=scale', 'identity={},font_scale=scale'),
                ('deadline=time.monotonic()+35;readiness_scrolls=0', 'deadline=time.monotonic()+36;readiness_scrolls=0'),
                ("['会话','环境','下载','网络','设置']", "['会话','环境','下载','网络']")):
            self.assertIn(before, raw)
            changed = raw.replace(before, after, 1)
            with self.subTest(change=before):
                with self.assertRaises(AssertionError):
                    checkpoint.navigation_v2_tree_input(ast.parse(changed.encode()))
                with self.assertRaises(AssertionError):
                    original.verify_shared_ui_source(changed)

    def test_unknown_byte_inputs_cannot_gain_an_ast_fallback(self):
        raw = (ROOT / UI).read_bytes()
        for mutant in (raw + b' ', raw[:100], b'', raw.decode(), bytearray(raw)):
            with self.assertRaises(AssertionError):
                checkpoint.navigation_v2_runner_input(mutant)
        with self.assertRaises(AssertionError):
            checkpoint.navigation_v2_tree_input(ast.Module(body=[], type_ignores=[]))

    def test_metadata_corruption_and_all_current_producer_imports_remain_separate(self):
        for layer in (first, checkpoint):
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'changed.json'
                path.write_bytes(layer.FIXTURE.read_bytes() + b' ')
                with patch.object(layer, 'FIXTURE', path), self.assertRaises((AssertionError, ValueError)):
                    layer.manifest()
        for name in (CHROME, UI, 'tests/gecko/run_chrome_collapse_v2.py',
                     'tools/gecko/chrome_collapse_contract_v2.py'):
            source = (ROOT / name).read_text()
            self.assertNotIn('ui_checkpoint_source_compatibility', source)
            self.assertNotIn('chrome_first_tap_source_compatibility', source)
        self.assertIn('from run_chrome_collapse import run_current as run_chrome_collapse', (ROOT / UI).read_text())


if __name__ == '__main__':
    unittest.main()
