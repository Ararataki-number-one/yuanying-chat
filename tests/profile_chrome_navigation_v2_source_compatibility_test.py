"""Exact finite historical ports; current Chrome v2 still executes unprojected."""
import ast
import hashlib
from pathlib import Path
import unittest

import chrome_navigation_v2_source_compatibility as view
import chrome_first_tap_source_compatibility as first

ROOT = Path(__file__).resolve().parents[1]


class ChromeNavigationHistoricalPorts(unittest.TestCase):
    def test_only_fixed_complete_inputs_restore_the_unmodified_old_pins(self):
        old = first.manifest()['files']
        for relative in (view.RUNNER, view.GUARD, view.HEADER):
            raw = (ROOT/relative).read_bytes()
            restored = view.source_input(raw, relative)
            self.assertEqual(view.pin(restored), view.LEGACY[relative][0])
            self.assertEqual((len(restored), hashlib.sha256(restored).hexdigest()),
                             (old[relative]['reviewedBytes'], old[relative]['reviewedSha256']))
            self.assertEqual(view.source_input(restored, relative), restored)
        self.assertEqual(hashlib.sha256(first.FIXTURE.read_bytes()).hexdigest(),
                         '2c31cb3286d88a91079fb33cef1f27b9c81f7cefda6fbb1c7bc6537e6ca79795')

    def test_the_entire_original_runner_is_one_unchanged_prefix(self):
        raw=(ROOT/view.RUNNER).read_bytes(); old=view.source_input(raw,view.RUNNER)
        self.assertEqual(raw,old+view.APPEND)
        self.assertEqual(view.pin(view.APPEND),(516,view.APPEND_SHA256))
        self.assertNotIn('chrome_navigation_v2_source_compatibility',raw.decode())
        self.assertEqual([n.name for n in ast.parse(view.APPEND).body],['run_versioned'])

    def test_home_test_methods_and_assertions_are_byte_for_byte_unchanged(self):
        raw=(ROOT/view.GUARD).read_text(); old=view.source_input(raw.encode(),view.GUARD).decode()
        def methods(source):
            return [ast.get_source_segment(source,n) for n in ast.walk(ast.parse(source))
                    if isinstance(n,ast.FunctionDef) and n.name.startswith('test_')]
        def assertions(source):
            return [ast.dump(n,include_attributes=False) for n in ast.walk(ast.parse(source))
                    if isinstance(n,ast.Assert) or isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr.startswith('assert')]
        self.assertEqual(methods(raw),methods(old));self.assertEqual(assertions(raw),assertions(old))

    def test_append_deleted_duplicated_moved_edited_and_prefix_changes_reject(self):
        raw=(ROOT/view.RUNNER).read_bytes();old=view.source_input(raw,view.RUNNER)
        # The exact old whole file remains valid for original historical tests.
        self.assertEqual(view.source_input(old,view.RUNNER),old)
        mutations=(old+view.APPEND+view.APPEND,view.APPEND+old,raw+b' ',raw[:-1],
                   raw.replace(b'navigation_contract==1',b'navigation_contract==2',1),
                   raw.replace(b'deadline=time.monotonic()+30',b'deadline=time.monotonic()+31',1),
                   raw.replace(b'assert value,',b'assert True,',1),old+view.APPEND[:-1])
        for value in mutations:
            with self.subTest(digest=hashlib.sha256(value).hexdigest()),self.assertRaisesRegex(ValueError,'Unreviewed header readiness change'):
                view.source_input(value,view.RUNNER)

    def test_read_port_cannot_hide_changed_old_tests_or_wrong_source(self):
        raw=(ROOT/view.GUARD).read_bytes()
        for value in (raw.replace(view.PORT_IMPORT,b'',1),raw.replace(view.PORT_IMPORT,view.PORT_IMPORT*2,1),
                      raw.replace(view.NEW_SHARED,view.OLD_SHARED,1),raw.replace(b'self.assertTrue(',b'self.assertFalse(',1),
                      raw.replace(b'if not 0<amount<=.2',b'if not 0<amount<=.3',1),raw+b' '):
            self.assertNotEqual(value,raw)
            with self.subTest(digest=hashlib.sha256(value).hexdigest()),self.assertRaises(ValueError):view.source_input(value,view.GUARD)
        for path in (None,Path(view.RUNNER),'../'+view.RUNNER,'/'+view.RUNNER,view.RUNNER+'.other'):
            with self.assertRaises(ValueError):view.source_input((ROOT/view.RUNNER).read_bytes(),path)
        for raw in (None,bytearray(b'x'),'text',b'unknown'):
            with self.assertRaises(ValueError):view.source_input(raw,view.RUNNER)
        with self.assertRaises(ValueError):view.historical_ui_path(ROOT/'tests/gecko/run_device.py')

    def test_only_the_home_history_port_uses_the_ui_projection(self):
        original=view.historical_ui_path(ROOT/view.UI).read_text()
        self.assertEqual(hashlib.sha256(original.encode()).hexdigest(),
                         'b85896aa5b94e33fb40bbada323d239a66f75c12a39bf9adb2a4ff3e3483e14d')
        for relative in ('tests/gecko/run_chrome_collapse.py','tests/gecko/run_chrome_collapse_v2.py',
                         'tests/gecko/ChromeCollapseIntegration.java','tools/gecko/chrome_collapse_contract_v2.py'):
            source=(ROOT/relative).read_text()
            self.assertNotIn('chrome_navigation_v2_source_compatibility',source)
            self.assertNotIn('ui_workspace_v2_source_compatibility',source)


if __name__=='__main__':unittest.main()
