"""Synthetic console-transport controls only; no application/device acceptance."""
import io
import contextlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import experience46_host_evidence as evidence


class Experience46EvidenceTransport(unittest.TestCase):
    def fixture(self, base):
        expected = {'results.json': b'{"scope":"synthetic host only"}\r\n',
                    'stdout.log': bytes(range(256)) * 97, 'empty.stderr.log': b'',
                    'unicode.tap': '测试\r\n# pass 1\n'.encode()}
        for name, raw in expected.items():
            (base / name).write_bytes(raw)
        return expected

    def encoded(self, root, names):
        stream = io.StringIO()
        evidence.emit_evidence(root, names, label='synthetic-transport', stream=stream)
        return stream.getvalue().splitlines()

    def changed(self, lines, index, **values):
        changed = list(lines)
        event = json.loads(changed[index].split(evidence.PREFIX, 1)[1])
        event.update(values)
        changed[index] = evidence.PREFIX + json.dumps(event)
        return changed

    def test_exact_multichunk_empty_unicode_and_ci_prefix_roundtrip(self):
        with tempfile.TemporaryDirectory(prefix='synthetic46-console-') as directory:
            root = Path(directory)
            expected = self.fixture(root)
            lines = self.encoded(root, [*expected, 'missing.log'])
            archive, = evidence.reassemble(['2026-10-31T00:00:00Z ' + line for line in lines])
            self.assertEqual(archive['files'], expected)
            chunks = [json.loads(line[len(evidence.PREFIX):]) for line in lines if '"kind":"chunk"' in line]
            self.assertTrue(any(chunk['parts'] > 1 for chunk in chunks))
            self.assertTrue(all(len(chunk['data']) <= 8192 for chunk in chunks))

    def test_missing_tampered_duplicate_out_of_range_and_truncated_rejected(self):
        with tempfile.TemporaryDirectory(prefix='synthetic46-counterfeit-') as directory:
            root = Path(directory)
            expected = self.fixture(root)
            lines = self.encoded(root, expected)
            at = next(n for n, line in enumerate(lines) if '"kind":"chunk"' in line and '"stdout.log"' in line)
            chunk = json.loads(lines[at][len(evidence.PREFIX):])
            changed_data = ('A' if chunk['data'][0] != 'A' else 'B') + chunk['data'][1:]
            cases = {
                'missing': lines[:at] + lines[at + 1:],
                'tampered': self.changed(lines, at, data=changed_data),
                'duplicate': lines[:at] + [lines[at]] + lines[at:],
                'range': self.changed(lines, at, part=chunk['parts']),
                'negative-range': self.changed(lines, at, part=-1),
                'undeclared-path': self.changed(lines, at, path='undeclared.log'),
                'wrong-count': self.changed(lines, at, parts=chunk['parts'] + 1),
                'oversized-chunk': self.changed(lines, at, data='A' * 8193),
                'bad-base64': self.changed(lines, at, data='!' * 8192),
                'truncated': lines[:-1],
                'no-manifest': lines[1:],
                'duplicate-manifest': [lines[0], *lines],
                'duplicate-end': [*lines, lines[-1]],
                'bad-final-digest': self.changed(lines, len(lines) - 1, manifestSha256='0' * 64),
            }
            for name, invalid in cases.items():
                with self.subTest(name=name), self.assertRaises((ValueError, TypeError)):
                    evidence.reassemble(invalid)

    def test_path_symlink_duplicates_and_byte_budgets_rejected(self):
        with tempfile.TemporaryDirectory(prefix='synthetic46-path-') as directory:
            root = Path(directory)
            expected = self.fixture(root)
            for name in ('../results.json', '/results.json', 'private.jks', 'nested/../results.json',
                         './results.json', 'private.key', 'a\\results.log', ''):
                with self.subTest(path=name), self.assertRaises(ValueError):
                    self.encoded(root, [name])
            with self.assertRaises(ValueError):
                self.encoded(root, ['results.json', 'results.json'])
            with self.assertRaises(ValueError):
                self.encoded(root, ['x' + str(n) + '.json' for n in range(evidence.MAX_FILES + 1)])
            (root / 'alias.log').symlink_to(root / 'stdout.log')
            with self.assertRaises(ValueError):
                self.encoded(root, ['alias.log'])
            (root / 'linked').symlink_to(root, target_is_directory=True)
            with self.assertRaises(ValueError):
                self.encoded(root, ['linked/results.json'])
            with patch.object(evidence, 'MAX_FILE_BYTES', 10), self.assertRaises(ValueError):
                self.encoded(root, ['results.json'])
            with patch.object(evidence, 'MAX_TOTAL_BYTES', 10), self.assertRaises(ValueError):
                self.encoded(root, ['results.json'])
            # Unlisted ordinary files are not recursively included or read.
            (root / 'unlisted-private.key').write_bytes(b'SYNTHETIC-DO-NOT-EMIT')
            archive, = evidence.reassemble(self.encoded(root, ['results.json']))
            self.assertEqual(archive['files'], {'results.json': expected['results.json']})

    def test_failed_and_timed_out_process_bytes_survive_finally(self):
        with tempfile.TemporaryDirectory(prefix='synthetic46-invocation-') as directory:
            root = Path(directory)
            attempt = evidence.new_attempt(root, 'failure')
            command = [sys.executable, '-c', 'import sys;sys.stdout.buffer.write(b"x"*25000);sys.stderr.buffer.write(b"failure\\r\\n");sys.exit(7)']
            stream = io.StringIO()
            try:
                result = evidence.run_recorded(command, attempt, cwd=root, timeout=10)
                self.assertEqual(result.returncode, 7)
                raise RuntimeError('Synthetic caller failure after execution')
            except RuntimeError:
                pass
            finally:
                evidence.emit_evidence(attempt, evidence.INVOCATION_FILES, label='synthetic-failure', stream=stream)
            archive, = evidence.reassemble(stream.getvalue().splitlines())
            self.assertEqual(archive['files']['invocation.stdout.log'], b'x' * 25000)
            self.assertEqual(archive['files']['invocation.stderr.log'], b'failure\r\n')
            self.assertEqual(json.loads(archive['files']['invocation.result.json'])['returnCode'], 7)
            timeout = evidence.new_attempt(root, 'timeout')
            with self.assertRaises(subprocess.TimeoutExpired):
                evidence.run_recorded([sys.executable, '-c', 'import sys,time;print("before timeout",flush=True);time.sleep(5)'], timeout, cwd=root, timeout=.2)
            archive, = evidence.reassemble(self.encoded(timeout, evidence.INVOCATION_FILES))
            self.assertEqual(archive['files']['invocation.stdout.log'], b'before timeout\n')
            self.assertTrue(json.loads(archive['files']['invocation.result.json'])['timedOut'])

    def test_both_new_host_wrappers_emit_complete_evidence_before_propagating_failure(self):
        import profile_experience46_hosts_test as unified
        import profile_download46_metadata_test as downloads
        with tempfile.TemporaryDirectory(prefix='synthetic46-wrapper-failure-') as directory:
            root = Path(directory)
            expected = b'controlled failure\r\n' * 1100
            def fail_recorded(command, attempt, **unused):
                (attempt / 'results.json').write_bytes(b'{"synthetic":"failed invocation"}\n')
                return evidence.run_recorded([sys.executable, '-c',
                    'import sys;sys.stderr.buffer.write(b"controlled failure\\r\\n"*1100);sys.exit(9)'],
                    attempt, cwd=root, timeout=10)
            first = unified.Experience46Hosts('test_authority_optional_detection_and_bound_network')
            first.output = root / 'unified';first.android = root / 'android.jar';first.home = root
            second = downloads.Download46Behavior('test_current_renderer_bounds_and_byte_labels')
            second.output = root / 'downloads';second.java_home = root;second.jars = [('synthetic', root / 'synthetic.jar')]
            operations = [(unified, lambda: first.host('synthetic', 'unused.py', root / 'desktop.jar')),
                          (downloads, lambda: second.run_host('unused.py'))]
            for module, operation in operations:
                stream = io.StringIO()
                with self.subTest(module=module.__name__), patch.object(module, 'run_recorded', side_effect=fail_recorded), contextlib.redirect_stdout(stream), self.assertRaises(AssertionError):
                    operation()
                archive, = evidence.reassemble(stream.getvalue().splitlines())
                self.assertEqual(archive['files']['invocation.stderr.log'], expected)
                self.assertEqual(archive['files']['results.json'], b'{"synthetic":"failed invocation"}\n')
                self.assertEqual(json.loads(archive['files']['invocation.result.json'])['returnCode'], 9)


if __name__ == '__main__':
    unittest.main(verbosity=2)
