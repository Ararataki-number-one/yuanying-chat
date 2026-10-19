"""Real fake-ADB capture controls; no Android, UI acceptance or input execution."""
import importlib.util
import json
from pathlib import Path
import stat
import sys
import tempfile
import time
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('actual_ui_visual_capture', ROOT / 'tools/gecko/ui_visual_capture.py')
CAPTURE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CAPTURE)
MATRIX_SPEC = importlib.util.spec_from_file_location('native_ui_matrix', ROOT / 'tools/gecko/ui_visual_contract.py')
MATRIX = importlib.util.module_from_spec(MATRIX_SPEC)
MATRIX_SPEC.loader.exec_module(MATRIX)
XML = b'<?xml version="1.0"?><hierarchy rotation="0"><node text="fresh current native UI" /></hierarchy>'

class NativeCaptureCoverageTest(unittest.TestCase):
    def records(self):
        return [dict(variant='current',theme=theme,logicalViewport=viewport,fontScale=scale,scene=scene)
                for theme,viewport,scale,scene in sorted(MATRIX.required_captures())]

    def test_current_ui_has_one_hundred_cases_and_retains_every_previous_scene(self):
        previous={(viewport,1,scene) for viewport in ('360x640','412x640')
                  for scene in ('chat','environments','network','proxy','entries','browser','preferences')}
        previous|={('360x640',2,scene) for scene in ('chat','proxy','entries','browser','preferences')}
        self.assertEqual(len(self.records()),100)
        self.assertTrue(previous<={(r['logicalViewport'],r['fontScale'],r['scene']) for r in self.records() if r['theme']=='light'})
        MATRIX.verify_captures(self.records())

    def test_missing_dark_ui_is_rejected(self):
        with self.assertRaises(AssertionError):MATRIX.verify_captures([r for r in self.records() if r['theme']=='light'])

    def test_duplicate_cannot_replace_a_required_scene(self):
        records=self.records();records[-1]=records[0]
        with self.assertRaises(AssertionError):MATRIX.verify_captures(records)

    def test_historical_app_cannot_supply_a_current_ui_capture(self):
        records=self.records();records[0]['variant']='baseline'
        with self.assertRaises(AssertionError):MATRIX.verify_captures(records)

    def test_dark_capture_cannot_be_labeled_as_light(self):
        records=self.records()
        for row in records:row['theme']='light'
        with self.assertRaises(AssertionError):MATRIX.verify_captures(records)


FAKE_ADB = r'''import json,pathlib,sys,time
root=pathlib.Path(__file__).parent
parts=sys.argv[1:]
with (root/'commands.jsonl').open('a') as log:log.write(json.dumps(parts)+'\n')
if parts[:2]!=['-s','emulator-5554']:raise SystemExit('Unexpected device')
parts=parts[2:]
config=json.loads((root/'config.json').read_text())
if len(parts)==4 and parts[:3]==['shell','uiautomator','dump']:
    state=root/'next.txt';index=int(state.read_text()) if state.exists() else 0;state.write_text(str(index+1))
    mode=config['modes'][min(index,len(config['modes'])-1)];remote=parts[3]
    if not remote.startswith('/sdcard/pocketchat-ui-visual-'):raise SystemExit('Unowned dump path')
    local=root/pathlib.PurePosixPath(remote).name
    if mode in ['null','stale-null']:
        if mode=='stale-null':local.write_bytes(b'<hierarchy><node text="stale" /></hierarchy>')
        print('ERROR: null root node returned by UiTestAutomationBridge.',file=sys.stderr);raise SystemExit(0)
    if mode=='unknown':
        local.write_bytes(bytes.fromhex(config['xml']));print('ERROR: unknown accessibility error',file=sys.stderr);raise SystemExit(0)
    if mode=='adb-error':print('error: device offline',file=sys.stderr);raise SystemExit(1)
    if mode=='timeout':time.sleep(2)
    if mode not in ['missing','permission']:
        local.write_bytes(b'<not-xml' if mode=='malformed' else bytes.fromhex(config['xml']))
    if mode=='permission':(root/'permission.txt').write_text(remote)
    print('UI hierchary dumped to: '+remote)
elif len(parts)==3 and parts[:2]==['shell','cat']:
    remote=parts[2];local=root/pathlib.PurePosixPath(remote).name
    if (root/'permission.txt').exists():print('cat: '+remote+': Permission denied',file=sys.stderr);raise SystemExit(1)
    if local.exists():sys.stdout.buffer.write(local.read_bytes())
    else:print('cat: '+remote+': No such file or directory',file=sys.stderr);raise SystemExit(1)
else:raise SystemExit('Unexpected non-capture action: '+repr(parts))
'''


class UiVisualCaptureTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='ui-visual-capture-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.adb = self.root / 'fake adb'
        self.adb.write_text('#!' + sys.executable + '\n' + FAKE_ADB)
        self.adb.chmod(self.adb.stat().st_mode | stat.S_IXUSR)
        self.diagnostics = self.root / 'attempts.json'
        self.capture = CAPTURE.UiVisualCapture(adb=self.adb, serial='emulator-5554', source='a'*40,
                                               diagnostics=self.diagnostics)

    def modes(self, *values):
        (self.root / 'config.json').write_text(json.dumps(dict(modes=values, xml=XML.hex())))

    def commands(self):
        path = self.root / 'commands.jsonl'
        return [json.loads(line)[2:] for line in path.read_text().splitlines()] if path.exists() else []

    def report(self):
        return json.loads(self.diagnostics.read_text())

    def assert_read_only(self):
        for row in self.commands():
            self.assertTrue(row[:3] == ['shell', 'uiautomator', 'dump'] or row[:2] == ['shell', 'cat'], row)
            self.assertRegex(row[-1], r'^/sdcard/pocketchat-ui-visual-[0-9a-f]{32}-[1-9][0-9]*\.xml$')

    def test_actual_null_root_then_current_xml_recovers_with_only_read_commands(self):
        self.modes('null', 'ok')
        self.assertEqual(self.capture.read(deadline=time.monotonic()+3), XML.decode())
        calls=self.commands();self.assertEqual(len(calls),3)
        self.assertNotEqual(calls[0][-1],calls[1][-1]);self.assertEqual(calls[1][-1],calls[2][-1])
        report=self.report();self.assertEqual(report['attemptCount'],2)
        self.assertEqual([r['status'] for r in report['attempts']],['not-ready','captured'])
        first=report['attempts'][0]['commands'][0]
        self.assertEqual(first['stderr']['text'],CAPTURE.NULL_ROOT+'\n')
        for row in report['attempts']:
            self.assertGreaterEqual(row['completedAtMonotonicNanos'],row['startedAtMonotonicNanos'])
        self.assert_read_only()

    def test_old_and_null_root_owned_files_cannot_be_accepted_as_success(self):
        (self.root/'ui-visual.xml').write_bytes(b'<hierarchy><node text="old stale UI" /></hierarchy>')
        self.modes('stale-null','ok')
        self.assertEqual(self.capture.read(deadline=time.monotonic()+3),XML.decode())
        first=self.commands()[0][-1]
        self.assertFalse(any(row[:2]==['shell','cat'] and row[-1]==first for row in self.commands()))
        self.assertFalse(any(row[-1]=='/sdcard/ui-visual.xml' for row in self.commands()))
        self.assert_read_only()

    def test_only_missing_exact_current_attempt_file_is_retryable(self):
        self.modes('missing','ok')
        self.assertEqual(self.capture.read(deadline=time.monotonic()+3),XML.decode())
        calls=self.commands();self.assertEqual(len(calls),4)
        self.assertEqual(calls[0][-1],calls[1][-1]);self.assertNotEqual(calls[0][-1],calls[2][-1])
        self.assertEqual(self.report()['attempts'][0]['reason'],'Owned current-attempt hierarchy was not created')
        self.assert_read_only()

    def test_unknown_accessibility_error_is_fatal_even_with_readable_xml(self):
        self.modes('unknown','ok')
        with self.assertRaises(RuntimeError):self.capture.read(deadline=time.monotonic()+3)
        self.assertEqual(len(self.commands()),1)
        self.assertEqual(self.report()['attempts'][0]['status'],'failed')

    def test_adb_transport_failure_is_not_retried(self):
        self.modes('adb-error','ok')
        with self.assertRaises(CAPTURE.subprocess.CalledProcessError):self.capture.read(deadline=time.monotonic()+3)
        self.assertEqual(len(self.commands()),1)

    def test_permission_and_malformed_xml_fail_without_another_attempt(self):
        for mode in ['permission','malformed']:
            with self.subTest(mode=mode):
                self.modes(mode,'ok')
                with self.assertRaises((CAPTURE.subprocess.CalledProcessError, CAPTURE.ET.ParseError)):
                    self.capture.read(deadline=time.monotonic()+3)
                self.assertEqual(self.report()['attempts'][-1]['status'],'failed')
                (self.root/'next.txt').unlink()
                permission=self.root/'permission.txt'
                if permission.exists():permission.unlink()
        self.assertEqual(len(self.commands()),4)

    def test_no_deadline_means_one_acquisition_without_a_new_retry_budget(self):
        self.modes('null','ok')
        with self.assertRaises(CAPTURE.CaptureNotReady):self.capture.read()
        self.assertEqual(len(self.commands()),1)

    def test_expired_existing_deadline_runs_no_adb_commands(self):
        self.modes('ok')
        with self.assertRaises(TimeoutError):self.capture.read(deadline=time.monotonic()-1)
        self.assertEqual(self.commands(),[])

    def test_existing_deadline_bounds_the_real_subprocess(self):
        self.modes('timeout')
        with self.assertRaises(CAPTURE.subprocess.TimeoutExpired):self.capture.read(deadline=time.monotonic()+.1)
        row=self.report()['attempts'][0]['commands'][0]
        self.assertLessEqual(row['timeoutSeconds'],.1)
        self.assertTrue(row['timedOut']);self.assert_read_only()

    def test_not_ready_does_not_start_another_attempt_after_expiry(self):
        self.modes('null','ok')
        with mock.patch.object(CAPTURE.time,'monotonic',side_effect=[1,1,1,3]):
            with self.assertRaises(TimeoutError):self.capture.read(deadline=2)
        self.assertEqual(len(self.commands()),1)

    def test_successful_cat_or_validation_after_absolute_deadline_is_rejected(self):
        self.modes('ok')
        for clock in ([1,1,1,1,3], [1,1,1,1,1,3]):
            with self.subTest(clock=clock):
                before=len(self.commands())
                with mock.patch.object(CAPTURE.time,'monotonic',side_effect=clock):
                    with self.assertRaises(TimeoutError):self.capture.read(deadline=2)
                self.assertEqual(len(self.commands())-before,2)
                row=self.report()['attempts'][-1]
                self.assertEqual(row['status'],'failed')
                self.assertEqual(row['errorType'],'TimeoutError')
                self.assertEqual(row['commands'][-1]['exitCode'],0)
                self.assertNotIn('xmlSha256',row)
        self.assert_read_only()

    def test_diagnostics_retain_bounded_bytes_and_explicit_dropped_attempt_count(self):
        self.modes('ok')
        with mock.patch.object(self.capture,'command') as command:
            command.side_effect=lambda parts,row,deadline: CAPTURE.subprocess.CompletedProcess(parts,0,
                ('UI hierchary dumped to: '+row['remotePath']).encode() if parts[1]=='uiautomator' else XML,b'')
            for unused in range(257):self.capture.read()
        report=self.report();self.assertEqual(report['attemptCount'],257)
        self.assertEqual(len(report['attempts']),256);self.assertEqual(report['droppedAttempts'],1)
        value=self.capture.output(b'x'*10000)
        self.assertEqual(value['bytes'],10000);self.assertEqual(len(value['text']),8192);self.assertTrue(value['truncated'])


if __name__=='__main__':unittest.main()
