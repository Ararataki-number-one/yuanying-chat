"""Finite pure212 CI source prerequisites; never device/release acceptance."""
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

import pure212_ci_source_compatibility as ci

import cpu_source_compatibility as _cpu_history

ROOT = Path(__file__).resolve().parents[1]

class Pure212CiSourceCompatibilityTests(unittest.TestCase):
    def test_exact_four_complete_sources_forward_and_inverse(self):
        value = ci.manifest()
        self.assertEqual(len(value['files']), 4)
        self.assertFalse(value['runtimeAcceptance']);self.assertFalse(value['actualAndroidExecution'])
        for path, row in value['files'].items():
            current = _cpu_history.metadata_input((ROOT/path).read_bytes(), path)
            before = ci.source_input(current, path)
            self.assertEqual((len(before), ci.sha(before)), (row['previousBytes'], row['previousSha256']))
            self.assertIs(ci.source_input(before, path), before)
            for delta in row['deltas']:
                self.assertEqual(before.count(delta['previous'].encode()), 1)
                before = before.replace(delta['previous'].encode(), delta['current'].encode(), 1)
            self.assertEqual(before, current)

    def test_unknown_missing_duplicate_changed_moved_and_types_fail(self):
        for path, row in ci.manifest()['files'].items():
            raw = _cpu_history.metadata_input((ROOT/path).read_bytes(), path)
            values = [raw+b' ', raw[:64], b'']
            for delta in row['deltas']:
                chunk = delta['current'].encode()
                removed = raw.replace(chunk, b'', 1)
                values += [removed, raw.replace(chunk, chunk*2, 1), removed+chunk,
                           raw.replace(chunk, chunk+b' ', 1)]
            for value in values:
                if value == raw:continue
                with self.assertRaises(ValueError):ci.source_input(value, path)
        for raw in (None, True, bytearray(b'raw'), 'raw'):
            with self.assertRaises(ValueError):ci.source_input(raw, next(iter(ci.PATHS)))
        for path in (None, '../tests/file.py', '/tests/file.py', Path('tests/file.py'), 'unknown.py'):
            with self.assertRaises(ValueError):ci.source_input(b'raw', path)

    def test_public_catalog_retains_every_original_pin_without_cpu_or_tls(self):
        path = 'tests/baselines/public-source-history.json'
        raw = _cpu_history.metadata_input((ROOT/path).read_bytes(), path)
        current, before = json.loads(raw), json.loads(ci.source_input(raw, path))
        self.assertEqual((len(before['groups']), sum(len(g['files']) for g in before['groups'])), (16, 91))
        self.assertEqual((len(current['groups']), sum(len(g['files']) for g in current['groups'])), (17, 149))
        now = {g['commit']:g for g in current['groups']}
        for group in before['groups']:
            self.assertEqual(now[group['commit']]['tree'], group['tree'])
            for path, pin in group['files'].items():self.assertEqual(now[group['commit']]['files'][path], pin)
        history = _cpu_history.metadata_input((ROOT/'tools/browser/source_history.py').read_bytes(), 'tools/browser/source_history.py').decode()
        self.assertIn("MANIFEST_SHA256 = '"+ci.sha(raw)+"'", history)
        for group in current['groups']:
            for path in group['files']:
                self.assertNotIn('/gecko-cpu', path);self.assertNotIn('/gecko-tls', path)

    def test_source_oracle_assertion_rhs_and_runtime_import_boundaries(self):
        path = 'tests/profile_ip_timezone_source_compatibility_test.py'
        raw = _cpu_history.metadata_input((ROOT/path).read_bytes(), path);before = ci.source_input(raw, path)
        def rhs(text):
            return [ast.dump(ast.Tuple(elts=node.args[1:],ctx=ast.Load()),include_attributes=False)
                    for node in ast.walk(ast.parse(text)) if isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute) and node.func.attr.startswith('assert')]
        self.assertEqual(rhs(raw), rhs(before))
        for directory in ('app/src/main', 'tools'):
            for file in (ROOT/directory).rglob('*'):
                if file.is_file() and file.suffix in ('.java','.py','.js'):
                    if file.suffix == '.py':
                        for node in ast.walk(ast.parse(file.read_text())):
                            if isinstance(node, ast.ImportFrom):self.assertNotEqual(node.module, 'pure212_ci_source_compatibility')
                            if isinstance(node, ast.Import):self.assertNotIn('pure212_ci_source_compatibility', [value.name for value in node.names])
                    else:self.assertNotIn('pure212_ci_source_compatibility', file.read_text())
        for name in ('gecko-ip-transport-host/run.py','gecko-ip-window-barrier-host/run.py'):
            self.assertNotIn('pure212_ci_source_compatibility', (ROOT/'tests'/name).read_text())

    def test_window_metadata_recognizes_only_the_whole_independent_spinner(self):
        path = ROOT/'tests/gecko-ip-window-barrier-host/run.py'
        spec = importlib.util.spec_from_file_location('actual_window_metadata',path)
        window = importlib.util.module_from_spec(spec);spec.loader.exec_module(window)
        raw = _cpu_history.metadata_input((ROOT/window.SOURCE_PATH).read_bytes(), window.SOURCE_PATH)
        restored = window.preserved_source_input(raw)
        self.assertNotEqual(raw, restored)
        self.assertEqual(hashlib.sha256(restored).hexdigest(), '8812872161d8441e1ff4c41118ccfa50c992490caa703c855245c7ed0019f440')
        unknown = raw+b' '
        self.assertIs(window.preserved_source_input(unknown), unknown)
        self.assertIn("selected = {name: declaration(source.read_text(), name) for name in MEMBERS}",path.read_text())

if __name__ == '__main__':unittest.main(verbosity=2)
