"""Real subprocess controls for binary installed-APK reads; no Android execution."""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    'installed_apk_read', ROOT / 'tools/gecko/installed_apk_read.py')
READER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(READER)

INSTALLED = '/data/app/~~controlled-token/local.pocketchat.test-controlled/base.apk'
SERIAL = 'emulator-5554'
PAYLOAD = bytes(range(256)) * 23 + b'\x00APK\r\n\xff\xfe\x80binary\x00tail\n'

FAKE_ADB = r'''import json, os, pathlib, stat, sys, time
base = pathlib.Path(__file__).parent
config = json.loads((base / 'config.json').read_text())
record = {'argv': sys.argv[1:], 'stdoutIsRegularFile': stat.S_ISREG(os.fstat(1).st_mode)}
with (base / 'commands.jsonl').open('a') as log:
    log.write(json.dumps(record) + '\n')
raw = (base / 'payload.bin').read_bytes()
mode = config['mode']
if mode == 'empty':
    raw = b''
if mode == 'timeout':
    raw = raw[:31]
sys.stdout.buffer.write(raw)
sys.stdout.buffer.flush()
if mode in ('error', 'timeout'):
    sys.stderr.buffer.write(b'controlled adb failure\n')
    sys.stderr.buffer.flush()
if mode == 'large-error':
    sys.stderr.buffer.write(b'E' * 70000)
    sys.stderr.buffer.flush()
if mode == 'timeout':
    time.sleep(5)
if mode in ('error', 'large-error'):
    raise SystemExit(17)
'''


class InstalledApkReadTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='installed-apk-reader-')
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.adb = self.directory / 'fake adb'
        self.adb.write_text('#!' + sys.executable + '\n' + FAKE_ADB)
        self.adb.chmod(self.adb.stat().st_mode | stat.S_IXUSR)
        (self.directory / 'payload.bin').write_bytes(PAYLOAD)
        self.mode('success')
        self.destination = self.directory / 'actual installed.apk'
        self.diagnostics = self.directory / 'read-diagnostics.json'

    def mode(self, value):
        (self.directory / 'config.json').write_text(json.dumps({'mode': value}))

    def commands(self):
        path = self.directory / 'commands.jsonl'
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def read(self, **changes):
        arguments = dict(adb=str(self.adb), serial=SERIAL, installed_path=INSTALLED,
            destination=self.destination, expected_sha256=hashlib.sha256(PAYLOAD).hexdigest(),
            expected_bytes=len(PAYLOAD), diagnostics=self.diagnostics, label='controlled-before')
        arguments.update(changes)
        with contextlib.redirect_stderr(io.StringIO()):
            return READER.read_installed_apk(**arguments)

    def receipt(self):
        return json.loads(self.diagnostics.read_text())

    def assert_once(self):
        self.assertEqual(self.commands(), [dict(argv=['-s', SERIAL, 'exec-out', 'cat', INSTALLED],
                                                stdoutIsRegularFile=True)])

    def assert_failed_cleanup(self, **changes):
        with self.assertRaises(READER.InstalledApkReadError) as caught:
            self.read(**changes)
        self.assertFalse(self.destination.exists(), 'A failed partial APK must not remain usable')
        self.assert_once()
        self.assertTrue(self.diagnostics.is_file(), 'Failure must retain an I/O diagnostic receipt')
        self.assertTrue(self.receipt()['partialCleaned'])
        self.assertEqual(caught.exception.diagnostics, self.receipt())

    def assert_io_receipt(self, receipt, payload):
        self.assertEqual(receipt['command'], [str(self.adb), '-s', SERIAL, 'exec-out', 'cat', INSTALLED])
        self.assertEqual(receipt['stdoutBytes'], len(payload))
        self.assertEqual(receipt['stdoutSha256'], hashlib.sha256(payload).hexdigest())
        for field in ('hostDiskBefore', 'hostDiskAfter'):
            disk = receipt[field]
            self.assertEqual(set(disk), {'total', 'used', 'free'})
            self.assertTrue(all(type(disk[key]) is int and disk[key] >= 0 for key in disk))
            self.assertGreater(disk['total'], 0)
            self.assertLessEqual(disk['free'], disk['total'])

    def test_exact_binary_roundtrip_uses_one_exec_out_cat_and_a_real_output_file(self):
        with patch.object(READER.subprocess, 'run', wraps=subprocess.run) as process:
            receipt = self.read()
        process.assert_called_once()
        command = [str(self.adb), '-s', SERIAL, 'exec-out', 'cat', INSTALLED]
        self.assertEqual(process.call_args.args, (command,))
        parameters = process.call_args.kwargs
        self.assertEqual(parameters['stdout'].name, str(self.destination))
        self.assertEqual(parameters['stdout'].mode, 'xb')
        self.assertEqual(parameters['stderr'], subprocess.PIPE)
        self.assertEqual(parameters['timeout'], 30)
        self.assertIs(parameters['check'], False)
        self.assertFalse(parameters.get('shell', False))
        self.assertEqual(self.destination.read_bytes(), PAYLOAD)
        self.assertEqual(hashlib.sha256(self.destination.read_bytes()).hexdigest(), hashlib.sha256(PAYLOAD).hexdigest())
        self.assert_once()
        self.assertIsInstance(receipt, dict)
        self.assertTrue(self.diagnostics.is_file(), 'Successful read must retain its host I/O receipt')
        self.assertEqual(self.receipt(), receipt)
        self.assertEqual(receipt['status'], 'verified-bytes')
        self.assertTrue(receipt['actualInstalledApkRead'])
        self.assertFalse(receipt['actualAndroidFixtureExecution'])
        self.assertFalse(receipt['retryPerformed'])
        self.assertFalse(receipt['compiledFileFallback'])
        self.assertEqual(receipt['returnCode'], 0)
        self.assertEqual(receipt['timeoutSeconds'], 30)
        self.assertEqual(receipt['stderr'], '')
        self.assertEqual(receipt['stderrBytes'], 0)
        self.assert_io_receipt(receipt, PAYLOAD)

    def test_correct_hash_with_wrong_expected_size_cannot_pass(self):
        self.assert_failed_cleanup(expected_bytes=len(PAYLOAD) + 1)

    def test_correct_size_with_wrong_expected_hash_cannot_pass(self):
        self.assert_failed_cleanup(expected_sha256='0' * 64)

    def test_empty_successful_process_output_cannot_pass(self):
        self.mode('empty')
        self.assert_failed_cleanup()

    def test_nonzero_exit_cannot_pass_even_when_stdout_has_exact_apk_bytes(self):
        self.mode('error')
        self.assert_failed_cleanup()
        receipt = self.receipt()
        self.assertEqual(receipt['returnCode'], 17)
        self.assertEqual(receipt['stderr'], 'controlled adb failure\n')
        self.assertEqual(receipt['stderrBytes'], len(b'controlled adb failure\n'))
        self.assert_io_receipt(receipt, PAYLOAD)

    def test_timeout_removes_flushed_partial_bytes_and_never_retries(self):
        self.mode('timeout')
        self.assert_failed_cleanup(timeout=.5)
        receipt = self.receipt()
        self.assertIn('controlled adb failure', receipt['stderr'])
        self.assert_io_receipt(receipt, PAYLOAD[:31])

    def test_large_stderr_is_bounded_without_losing_its_actual_byte_count(self):
        self.mode('large-error')
        self.assert_failed_cleanup()
        receipt = self.receipt()
        self.assertEqual(receipt['returnCode'], 17)
        self.assertEqual(receipt['stderrBytes'], 70000)
        self.assertLessEqual(len(receipt['stderr'].encode('utf-8')), 64 * 1024)
        self.assertTrue(receipt['stderrTruncated'])
        self.assert_io_receipt(receipt, PAYLOAD)

    def test_unsafe_installed_paths_are_rejected_before_any_command(self):
        paths = ['/sdcard/base.apk', '/data/app/base.apk', '/data/app/../base.apk', '/data/app/x/../base.apk',
                 '/data/app/x/not-base.apk', '/data/app/x/base.apk;id',
                 '/data/app/x/base.apk\n', '/data/app/x/base.apk\x00',
                 '/data/app//x/base.apk', '/data/app/x/./base.apk']
        for path in paths:
            with self.subTest(path=path), self.assertRaises((ValueError, RuntimeError)):
                self.read(installed_path=path)
            self.assertFalse(self.destination.exists())
            self.assertEqual(self.commands(), [])

    def test_invalid_timeouts_are_rejected_before_any_command(self):
        for timeout in (None, True, 0, -1, 31, float('nan'), float('inf')):
            with self.subTest(timeout=timeout), self.assertRaises((ValueError, RuntimeError)):
                self.read(timeout=timeout)
            self.assertFalse(self.destination.exists())
            self.assertEqual(self.commands(), [])

    def test_existing_destination_is_preserved_and_prevents_any_command(self):
        sentinel = b'prior evidence must remain unchanged\x00\xff'
        self.destination.write_bytes(sentinel)
        with self.assertRaises((FileExistsError, ValueError, RuntimeError)):
            self.read()
        self.assertEqual(self.destination.read_bytes(), sentinel)
        self.assertEqual(self.commands(), [])

    def test_destination_symlink_does_not_overwrite_its_target(self):
        target = self.directory / 'prior.apk'
        target.write_bytes(b'prior evidence')
        self.destination.symlink_to(target)
        with self.assertRaises((FileExistsError, ValueError, RuntimeError)):
            self.read()
        self.assertEqual(target.read_bytes(), b'prior evidence')
        self.assertTrue(self.destination.is_symlink())
        self.assertEqual(self.commands(), [])


if __name__ == '__main__':
    unittest.main()
