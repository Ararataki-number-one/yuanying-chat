"""Exact diagnostic source history and binding controls; no device claims."""
import ast
import os
from pathlib import Path
from historical_source_inputs import historical_bytes
import subprocess
import unittest

import glass_diagnostic_source_compatibility as inputs
import profile_editing_transport13_diagnostic_test as editing
import profile_native_setup_diagnostic11_test as native

ROOT = Path(__file__).resolve().parents[1]


class GlassDiagnosticSourceCompatibilityTests(unittest.TestCase):
    def test_whole_before_bytes_are_actual_git_and_forward_roundtrips_are_exact(self):
        value = inputs.manifest()
        environment = dict(os.environ, GIT_NO_LAZY_FETCH='1')
        self.assertEqual(subprocess.check_output(['git', '--no-replace-objects', 'rev-parse', value['baseCommit'] + '^{tree}'], cwd=ROOT, env=environment).decode().strip(), value['baseTree'])
        for path, row in value['files'].items():
            current = historical_bytes(path)
            previous = subprocess.check_output(['git', '--no-replace-objects', 'show', value['baseCommit'] + ':' + path], cwd=ROOT, env=environment)
            self.assertEqual(inputs.source_input(current, path), previous)
            self.assertEqual(inputs.sha(previous), inputs.PREVIOUS[path])
            for delta in row['deltas']:
                before, after = delta['previous'].encode(), delta['current'].encode()
                self.assertEqual(previous.count(before), 1)
                previous = previous.replace(before, after, 1)
            self.assertEqual(previous, current)

    def test_current_bindings_run_all_original_function_bodies_and_goldens(self):
        self.assertTrue(hasattr(native.SharedSaveNormalizersInput.restore.__func__, '__wrapped__'))
        self.assertTrue(hasattr(editing.restore_native_setup_shared_save_view, '__wrapped__'))
        current_display = historical_bytes(inputs.DISPLAY)
        current_native = historical_bytes(inputs.NATIVE)
        self.assertEqual(inputs.sha(native.SharedSaveNormalizersInput.restore(current_display)), '3c0f755bf0718db15ecf403d448f4c48a55261b241d1671f6574342f947a34e0')
        self.assertEqual(inputs.sha(editing.restore_native_setup_shared_save_view(current_native)), 'f4f01aa91c2e9f0a31859cf239a0d0e35172abee8267d69478c24a4616d503c5')
        def bodies(raw):
            text = raw.decode()
            return [ast.get_source_segment(text, node) for node in ast.walk(ast.parse(raw)) if isinstance(node, (ast.ClassDef, ast.FunctionDef))]
        for path in (inputs.NATIVE, 'tests/profile_editing_transport13_diagnostic_test.py'):
            current = historical_bytes(path)
            previous = subprocess.check_output(['git', '--no-replace-objects', 'show', inputs.manifest()['baseCommit'] + ':' + path], cwd=ROOT, env=dict(os.environ, GIT_NO_LAZY_FETCH='1'))
            self.assertEqual(bodies(current), bodies(previous))

    def test_after_hunks_missing_duplicate_moved_changed_and_old_semantics_fail_closed(self):
        wrappers = {inputs.DISPLAY: native.SharedSaveNormalizersInput.restore,
                    inputs.NATIVE: editing.restore_native_setup_shared_save_view}
        for path, row in inputs.manifest()['files'].items():
            raw = historical_bytes(path)
            changed = [raw + b'\n', raw[:1024], b'unknown source']
            for delta in row['deltas']:
                current = delta['current'].encode()
                self.assertEqual(raw.count(current), 1)
                remaining = raw.replace(current, b'', 1)
                moved = current + remaining
                if moved == raw:
                    moved = remaining + current
                changed.extend((remaining, raw.replace(current, current * 2, 1), moved,
                                raw.replace(current, current + b' ', 1)))
            if path == inputs.NATIVE:
                changed.extend((raw.replace(b'from glass_diagnostic_source_compatibility import wrap_normalizers_restore as _glass_normalizers_restore\n', b'', 1),
                                raw.replace(b'len(raw) == 51147', b'len(raw) == 51148', 1)))
            else:
                changed.extend((raw.replace(b'now-savedAt<5000', b'now-savedAt<50000', 1),
                                raw.replace(b'checks_failed=1', b'checks_failed=0', 1)))
            for candidate in changed:
                self.assertNotEqual(candidate, raw)
                with self.subTest(path=path, sha256=inputs.sha(candidate)):
                    with self.assertRaises(AssertionError):inputs.source_input(candidate, path)
                    self.assertEqual(inputs.historical_input(candidate, path), candidate)
                    if inputs.sha(candidate) != inputs.PREVIOUS[path]:
                        with self.assertRaises(AssertionError):wrappers[path](candidate)
            # A complete known predecessor retains the original oracle's own
            # behavior; it cannot satisfy source_input's mandatory after-image.
            previous = inputs.source_input(raw, path)
            with self.assertRaises(AssertionError):inputs.source_input(previous, path)
            self.assertEqual(inputs.historical_input(previous, path), previous)

    def test_types_paths_and_incomplete_bytes_cannot_gain_acceptance(self):
        raw = historical_bytes(inputs.DISPLAY)
        for candidate in (None, raw.decode(), bytearray(raw), memoryview(raw), True, b''):
            with self.assertRaises(AssertionError):inputs.source_input(candidate, inputs.DISPLAY)
            with self.assertRaises(AssertionError):native.SharedSaveNormalizersInput.restore(candidate)
        for path in (None, Path(inputs.DISPLAY), '/' + inputs.DISPLAY, '../' + inputs.DISPLAY, 'tests/gecko/run_ui_visuals.py'):
            with self.assertRaises(AssertionError):inputs.source_input(raw, path)


if __name__ == '__main__':
    unittest.main(verbosity=2)
