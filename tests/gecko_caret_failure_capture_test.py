"""Real fake-adb subprocess controls for failure artifacts; no Android execution."""
import hashlib
import importlib.util
import json
from pathlib import Path
import stat
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    'caret_failure_capture_runner', ROOT / 'tests/gecko/run_gecko_caret_compat.py')
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)
SERIAL = 'emulator-5554'
PREFIX = 'gecko-caret-compat-failure-'
ARTIFACTS = {
    'window.txt': 'Controlled window state\n中文\n'.encode(),
    'activity.txt': b'Controlled activities: foreground Pixel Launcher\n',
    'screen.png': b'\x89PNG\r\n\x1a\n\x00\xff\xfe\x80controlled binary pixels\x00',
    'ui.xml': '<hierarchy><node text="受控 UI" /></hierarchy>\n'.encode(),
    'log.txt': b'ANR in com.google.android.apps.nexuslauncher\nOriginal failure remains failed\n',
}

FAKE_ADB = r'''import json, pathlib, sys
base = pathlib.Path(__file__).parent
config = json.loads((base / 'config.json').read_text())
arguments = sys.argv[1:]
with (base / 'commands.jsonl').open('a') as log:
    log.write(json.dumps(arguments) + '\n')
if arguments[:2] != ['-s', 'emulator-5554']:
    raise SystemExit('Wrong selected device')
parts = arguments[2:]
if parts == ['shell', 'dumpsys', 'window']:
    artifact = 'window.txt'
elif parts == ['shell', 'dumpsys', 'activity', 'activities']:
    artifact = 'activity.txt'
elif parts == ['exec-out', 'screencap', '-p']:
    artifact = 'screen.png'
elif len(parts) == 4 and parts[:3] == ['shell', 'uiautomator', 'dump']:
    artifact = 'dump'
elif len(parts) == 3 and parts[:2] == ['exec-out', 'cat']:
    artifact = 'ui.xml'
elif parts == ['logcat', '-d']:
    artifact = 'log.txt'
else:
    raise SystemExit('Unexpected command: ' + repr(parts))
if artifact == config['failedArtifact']:
    sys.stdout.buffer.write(b'controlled failed-command partial bytes')
    sys.stderr.buffer.write(b'controlled capture failure\n')
    raise SystemExit(17)
if artifact == 'dump':
    sys.stdout.buffer.write(b'UI hierarchy dumped to selected path\n')
else:
    sys.stdout.buffer.write((base / artifact).read_bytes())
'''


class CaretFailureCaptureTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='caret-failure-capture-')
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.adb = self.directory / 'fake adb'
        self.adb.write_text('#!' + sys.executable + '\n' + FAKE_ADB)
        self.adb.chmod(self.adb.stat().st_mode | stat.S_IXUSR)
        for artifact, raw in ARTIFACTS.items():
            (self.directory / artifact).write_bytes(raw)
        self.output = self.directory / 'captured evidence'
        self.output.mkdir()
        self.config('none')

    def config(self, failed_artifact):
        (self.directory / 'config.json').write_text(json.dumps({'failedArtifact': failed_artifact}))

    def commands(self):
        return [json.loads(line) for line in (self.directory / 'commands.jsonl').read_text().splitlines()]

    def capture(self):
        return RUNNER.capture_failure_diagnostics(str(self.adb), SERIAL, self.output)

    def assert_read_only_command_order(self):
        commands = self.commands()
        self.assertEqual(len(commands), 6, 'Each requested diagnostic command must execute once')
        self.assertEqual(commands[0], ['-s', SERIAL, 'shell', 'dumpsys', 'window'])
        self.assertEqual(commands[1], ['-s', SERIAL, 'shell', 'dumpsys', 'activity', 'activities'])
        self.assertEqual(commands[2], ['-s', SERIAL, 'exec-out', 'screencap', '-p'])
        self.assertEqual(commands[3][:5], ['-s', SERIAL, 'shell', 'uiautomator', 'dump'])
        self.assertEqual(len(commands[3]), 6)
        remote = commands[3][-1]
        self.assertRegex(remote, r'^/sdcard/gecko-caret-compat-failure-[A-Za-z0-9_-]+\.xml$')
        self.assertEqual(commands[4], ['-s', SERIAL, 'exec-out', 'cat', remote])
        self.assertEqual(commands[5], ['-s', SERIAL, 'logcat', '-d'])

    def assert_saved(self, result, artifact):
        name = PREFIX + artifact
        raw = ARTIFACTS[artifact]
        receipt = result[name]
        self.assertIs(receipt['saved'], True)
        self.assertEqual((self.output / name).read_bytes(), raw)
        self.assertEqual(receipt['bytes'], len(raw))
        self.assertEqual(receipt['sha256'], hashlib.sha256(raw).hexdigest())
        self.assert_timestamps(receipt)

    def assert_timestamps(self, receipt):
        # Exact field names are shared with the runner's existing host ADB timing.
        for field in ('startedAtWallTimeMillis', 'completedAtWallTimeMillis',
                      'startedAtMonotonicNanos', 'completedAtMonotonicNanos'):
            self.assertIs(type(receipt[field]), int)
        self.assertGreater(receipt['startedAtWallTimeMillis'], 0)
        self.assertGreaterEqual(receipt['completedAtWallTimeMillis'], receipt['startedAtWallTimeMillis'])
        self.assertGreater(receipt['startedAtMonotonicNanos'], 0)
        self.assertGreaterEqual(receipt['completedAtMonotonicNanos'], receipt['startedAtMonotonicNanos'])

    def test_captures_all_five_exact_artifacts_with_binary_screen_and_receipts(self):
        result = self.capture()
        self.assertEqual(set(result), {PREFIX + name for name in ARTIFACTS})
        self.assert_read_only_command_order()
        for artifact in ARTIFACTS:
            with self.subTest(artifact=artifact):
                self.assert_saved(result, artifact)

    def test_failed_window_capture_continues_remaining_commands_and_preserves_failure(self):
        failure = b'{"status":"failed","error":"Original Pixel Launcher ANR","releaseAcceptance":false}\n'
        report = self.output / 'gecko-caret-compat-results.json'
        report.write_bytes(failure)
        self.config('window.txt')
        result = self.capture()
        self.assert_read_only_command_order()
        failed = result[PREFIX + 'window.txt']
        self.assertIs(failed['saved'], False)
        self.assertTrue(failed['error'])
        self.assertEqual(failed['stderr'], 'controlled capture failure\n')
        self.assertEqual(failed['output'], 'controlled failed-command partial bytes')
        self.assertFalse((self.output / (PREFIX + 'window.txt')).exists())
        self.assert_timestamps(failed)
        for artifact in set(ARTIFACTS) - {'window.txt'}:
            with self.subTest(artifact=artifact):
                self.assert_saved(result, artifact)
        self.assertEqual(report.read_bytes(), failure)
        self.assertEqual(json.loads(report.read_bytes())['status'], 'failed')


if __name__ == '__main__':
    unittest.main()
