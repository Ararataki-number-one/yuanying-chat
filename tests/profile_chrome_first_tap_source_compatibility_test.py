"""Exact historical input preservation only; current readiness hosts stay current."""
import ast
import hashlib
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import chrome_first_tap_source_compatibility as compat
from profile_chrome_home_resume_test import original_header_runner

ROOT = Path(__file__).resolve().parents[1]
RUNNER = 'tests/gecko/run_chrome_collapse.py'
GUARD = 'tests/profile_chrome_home_resume_test.py'
SHA = lambda raw: hashlib.sha256(raw).hexdigest()


class FirstTapHistoricalSourceControls(unittest.TestCase):
    def test_two_whole_sources_inverse_and_forward_equal_real_committed_bytes(self):
        for relative, row in compat.manifest()['files'].items():
            previous = subprocess.check_output(['git', 'show', compat.BASE_COMMIT + ':' + relative], cwd=ROOT)
            current = (ROOT / relative).read_bytes()
            with self.subTest(path=relative):
                self.assertEqual((SHA(previous), len(previous)), (row['previousSha256'], row['previousBytes']))
                self.assertEqual((SHA(current), len(current)), (row['reviewedSha256'], row['reviewedBytes']))
                self.assertEqual(compat.source_input(current, relative), previous)
                self.assertEqual(compat.source_input(previous, relative), previous)
                forward = previous
                for delta in row['deltas']:
                    before, after = delta['previous'].encode(), delta['current'].encode()
                    self.assertEqual((SHA(before), SHA(after)), (delta['previousSha256'], delta['currentSha256']))
                    self.assertEqual(forward.count(before), 1)
                    forward = forward.replace(before, after, 1)
                self.assertEqual(forward, current)

    def test_missing_duplicate_moved_changed_and_unknown_whole_inputs_reject(self):
        rejected = 0
        for relative, row in compat.manifest()['files'].items():
            if relative == 'tools/gecko/chrome_header_readiness.py':
                continue  # The original two rows retain all fourteen old controls.
            raw = (ROOT / relative).read_bytes()
            for delta in row['deltas']:
                chunk = delta['current'].encode()
                remaining = raw.replace(chunk, b'', 1)
                moved = remaining + chunk
                if moved == raw:
                    moved = chunk + remaining
                for candidate in (remaining, raw.replace(chunk, chunk * 2, 1),
                                  raw.replace(chunk, chunk + b' ', 1), moved):
                    self.assertNotEqual(candidate, raw)
                    with self.assertRaisesRegex(ValueError, 'Unreviewed header readiness change'):
                        compat.source_input(candidate, relative)
                    rejected += 1
            for candidate in (raw + b' ', raw[:100], b'unknown source'):
                with self.assertRaises(ValueError):
                    compat.source_input(candidate, relative)
                rejected += 1
        self.assertEqual(rejected, 14)

    def test_reviewed_header_transport_input_has_exact_bounded_negative_controls(self):
        relative = 'tools/gecko/chrome_header_readiness.py'
        row = compat.manifest()['files'][relative]
        current = (ROOT / relative).read_bytes()
        original = subprocess.check_output(['git', 'show', compat.BASE_COMMIT + ':' + relative], cwd=ROOT)
        self.assertEqual(original, subprocess.check_output(['git', 'show', '72e3bcac55285fea483e612ba4481f7e073a5422:' + relative], cwd=ROOT))
        self.assertEqual(compat.source_input(current, relative), original)
        rejected = 0
        for delta in row['deltas']:
            chunk = delta['current'].encode()
            self.assertEqual(current.count(chunk), 1)
            removed = current.replace(chunk, b'', 1)
            moved = removed + chunk
            if moved == current:
                moved = chunk + removed
            for candidate in (removed, current.replace(chunk, chunk * 2, 1),
                              current.replace(chunk, chunk + b' ', 1), moved):
                with self.subTest(delta=delta['id'], mutant=SHA(candidate)):
                    self.assertNotEqual(candidate, current)
                    with self.assertRaisesRegex(ValueError, 'Unreviewed header readiness change'):
                        compat.source_input(candidate, relative)
                    rejected += 1
        for candidate in (current + b' ', current[:100], b'unknown header source'):
            with self.assertRaises(ValueError):
                compat.source_input(candidate, relative)
            rejected += 1
        self.assertEqual(rejected, len(row['deltas']) * 4 + 3)
        for value in (current.decode(), bytearray(current), None):
            with self.assertRaises(ValueError):
                compat.source_input(value, relative)
        for path in ('/' + relative, '../' + relative, relative + '.other', Path(relative), None):
            with self.assertRaises(ValueError):
                compat.source_input(current, path)
        # Actual current runtime and its transport controls never receive this view.
        for path in ('tools/gecko/chrome_header_readiness.py',
                     'tests/profile_chrome_header_readiness_test.py'):
            self.assertNotIn('chrome_first_tap_source_compatibility', (ROOT / path).read_text())

    def test_existing_header_whole_golden_home_ast_and_all_original_assertions_remain(self):
        current = (ROOT / RUNNER).read_text()
        self.assertEqual(SHA(original_header_runner(current).encode()),
                         '47889966ca35c31ab8556a2c987f84378619471103c9720221cc2c3bf2ade1e3')
        old = subprocess.check_output(['git', 'show', compat.BASE_COMMIT + ':' + GUARD], cwd=ROOT)
        current_guard = (ROOT / GUARD).read_bytes()
        self.assertEqual(compat.source_input(current_guard, GUARD), old)
        def assertions(raw):
            return [ast.dump(node, include_attributes=False) for node in ast.walk(ast.parse(raw))
                    if isinstance(node, ast.Assert) or isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute) and node.func.attr.startswith('assert')]
        self.assertEqual(assertions(current_guard), assertions(old))
        def methods(raw):
            return [ast.get_source_segment(raw.decode(), node) for node in ast.walk(ast.parse(raw))
                    if isinstance(node, ast.FunctionDef) and node.name.startswith('test_')]
        self.assertEqual(methods(current_guard), methods(old))
        self.assertIn('b663b22628d1868c5348434823505d2ce23956cbe228a08d3c6e4043f39e83d8', current_guard.decode())

    def test_changed_scope_point_identity_original_deadline_or_oracle_cannot_normalize_away(self):
        source = (ROOT / RUNNER).read_text()
        for before, after in (
                ("if label=='initialChat':", "if label!='initialChat':"),
                ("point=prepared['point']", 'point=[0,0]'),
                ('identity=identity,before=before', 'identity=None,before=before'),
                ('identity=identity,before=before', 'identity=identity,before={}'),
                ('deadline=time.monotonic()+30', 'deadline=time.monotonic()+31'),
                ('return snapshot(label)', 'return before'),
                ('assert value,', 'assert True,'),
                ('start=start,end=end', 'start=end,end=start')):
            self.assertIn(before, source)
            candidate = source.replace(before, after, 1)
            with self.subTest(predicate=before), self.assertRaisesRegex(ValueError, 'Unreviewed header readiness change'):
                original_header_runner(candidate)

    def test_types_owned_paths_excerpt_and_corrupted_fixture_fail_closed(self):
        raw = (ROOT / RUNNER).read_bytes()
        for path in (None, Path(RUNNER), '/' + RUNNER, '../' + RUNNER, RUNNER + '.other'):
            with self.assertRaises(ValueError):
                compat.source_input(raw, path)
        for value in (None, raw.decode(), bytearray(raw), raw[:100]):
            with self.assertRaises(ValueError):
                compat.source_input(value, RUNNER)
        with tempfile.TemporaryDirectory(prefix='first-tap-inverse-negative-') as directory:
            fixture = Path(directory) / 'deltas.json'
            fixture.write_bytes(compat.FIXTURE.read_bytes() + b' ')
            with patch.object(compat, 'FIXTURE', fixture), self.assertRaises(ValueError):
                compat.source_input(raw, RUNNER)

    def test_current_native_readiness_hosts_and_unchanged_header_helper_do_not_use_this_view(self):
        for relative in ('tools/gecko/chrome_first_tap_readiness.py',
                         'tests/profile_chrome_first_tap_readiness_test.py',
                         RUNNER, 'tests/gecko/ChromeCollapseIntegration.java'):
            self.assertNotIn('chrome_first_tap_source_compatibility', (ROOT / relative).read_text())
        relative = 'tools/gecko/chrome_header_readiness.py'
        self.assertEqual(compat.source_input((ROOT / relative).read_bytes(), relative),
                         subprocess.check_output(['git', 'show', compat.BASE_COMMIT + ':' + relative], cwd=ROOT))


if __name__ == '__main__':
    unittest.main(verbosity=2)
