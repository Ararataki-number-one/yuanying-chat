"""Finite exact source-input port controls, independent from runtime acceptance."""
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import reading45_source_compatibility as compat

ROOT = Path(__file__).resolve().parents[1]
sha = lambda raw: hashlib.sha256(raw).hexdigest()


def prior(path):
    return subprocess.check_output(['git', 'show', compat.BASE_COMMIT + ':' + path], cwd=ROOT)


class Reading45CompatibilityTests(unittest.TestCase):
    def test_actual_prior_whole_files_and_forward_inverse(self):
        data = compat.DELTA_PATH.read_bytes()
        self.assertEqual(sha(data), compat.DELTA_SHA256)
        manifest = json.loads(data)
        self.assertEqual(subprocess.check_output(['git', 'rev-parse', compat.BASE_COMMIT + '^{tree}'], cwd=ROOT).decode().strip(), compat.BASE_TREE)
        for path, row in manifest['files'].items():
            original, current = prior(path), (ROOT / path).read_bytes()
            self.assertEqual(sha(original), row['previousSha256'])
            self.assertEqual(sha(current), row['reviewedSha256'])
            self.assertEqual(compat.reading45_source_bytes(current, path), original)
            self.assertEqual(compat.reading45_source_bytes(original, path), original)
            forward = original
            for delta in row['deltas']:
                previous, reviewed = delta['previous'].encode(), delta['current'].encode()
                self.assertEqual(forward.count(previous), 1)
                forward = forward.replace(previous, reviewed, 1)
            self.assertEqual(forward, current)

    def test_unknown_missing_duplicate_changed_and_relocated_bytes_rejected(self):
        rejected = 0
        manifest = json.loads(compat.DELTA_PATH.read_bytes())
        for path, row in manifest['files'].items():
            current = (ROOT / path).read_bytes()
            for delta in row['deltas']:
                chunk = delta['current'].encode()
                for unknown in (current.replace(chunk, b'', 1),
                                current.replace(chunk, chunk + chunk, 1),
                                current.replace(chunk, chunk + b' ', 1),
                                current.replace(chunk, b'', 1) + chunk):
                    with self.assertRaises(ValueError):
                        compat.reading45_source_bytes(unknown, path)
                    rejected += 1
            for unknown in (current + b' ', prior(path) + b' ', b'unknown source'):
                with self.assertRaises(ValueError):
                    compat.reading45_source_bytes(unknown, path)
                rejected += 1
        self.assertGreaterEqual(rejected, 35)
        output = os.environ.get('READING45_INVERSE_NEGATIVE_REPORT')
        if output:
            Path(output).write_text(json.dumps(dict(rejected=rejected, wholeFileGuardsPreserved=True, actualAndroidExecution=False), indent=2) + '\n')

    def test_changed_fixture_and_unlisted_path_rejected(self):
        relative = 'app/src/main/java/local/pocketchat/BrowserReading.java'
        raw = (ROOT / relative).read_bytes()
        with tempfile.TemporaryDirectory(prefix='reading45-inverse-fixture-') as tmp:
            fake = Path(tmp) / 'modified.json'
            fake.write_bytes(compat.DELTA_PATH.read_bytes() + b' ')
            with patch.object(compat, 'DELTA_PATH', fake):
                with self.assertRaises(ValueError):
                    compat.reading45_source_bytes(raw, relative)
        with self.assertRaises(ValueError):
            compat.reading45_source_bytes(raw, 'app/src/main/java/local/pocketchat/Unreviewed.java')

    def test_original_goldens_and_executed_production_boundaries_remain(self):
        for relative in ('tests/profile_reading_fit_completion_test.py',
                         'tests/profile_native43_source_compatibility_test.py',
                         'tests/profile_reading_zoom_trace_test.py'):
            original, current = prior(relative), (ROOT / relative).read_bytes()
            for golden in set(re.findall(rb"[0-9a-f]{64}", original)):
                self.assertIn(golden, current)
            self.assertEqual(compat.reading45_source_bytes(current, relative), original)
        relative = 'tests/profile_reading_fit_completion_test.py'
        original, current = prior(relative).decode(), (ROOT / relative).read_text()
        for name in ('execute', 'test_measured_completion_and_failure_controls'):
            def body(text):
                node = next(n for n in ast.walk(ast.parse(text)) if isinstance(n, ast.FunctionDef) and n.name == name)
                return ast.get_source_segment(text, node)
            self.assertEqual(body(original), body(current))
            self.assertNotIn('reading45_source_bytes', body(current))
        for relative in ('app/src/main/java/local/pocketchat/GeckoWebView.java',
                         'app/src/main/java/local/pocketchat/ChatSession.java',
                         'tests/native43_source_compatibility.py',
                         'tests/browser-reading-host/local/pocketchat/ChatSession.java',
                         'tests/browser-reading-host/local/pocketchat/BrowserReadingHostTest.java',
                         'tests/gecko/GeckoIntegrationTestActivity.java',
                         'tests/gecko/run_device.py'):
            self.assertEqual((ROOT / relative).read_bytes(), prior(relative))


if __name__ == '__main__':
    unittest.main(verbosity=2)
