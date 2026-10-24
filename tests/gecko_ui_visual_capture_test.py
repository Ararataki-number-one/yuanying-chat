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
        records = []
        for index, (theme, viewport, scale, scene) in enumerate(sorted(MATRIX.required_captures())):
            row = dict(variant='current', theme=theme, logicalViewport=viewport, fontScale=scale, scene=scene)
            if scene == 'downloads':
                row.update(actualPixels=[int(v)*3 for v in viewport.split('x')], densityDpi=480,
                           downloadLocationNonce=f'{index:032x}')
                row['downloadLocationRaw'] = json.dumps(self.label(row))
            records.append(row)
        return records

    def label(self, row):
        # Synthetic parser inputs only; no claim of Android layout execution.
        return dict(schema=1, status='observed', scene='downloads', sourceCommit='a'*40,
            nonce=row['downloadLocationNonce'], fontScale=row['fontScale'], density=3,
            actualAndroidLayout=True, text='保存位置', layoutTextLength=4,
            viewClass='local.pocketchat.DesignUi$ActionButton', layoutClass='android.text.StaticLayout',
            width=420, height=144, contentWidth=348, contentHeight=108, layoutWidth=348, layoutHeight=86,
            left=600, top=250, visibleWidth=420, visibleHeight=144, shown=True, enabled=True,
            clickable=True, windowFocused=True, layoutRequested=False, scrollX=0, scrollY=0,
            startedUptimeMs=100, observedUptimeMs=110,
            lines=[dict(start=0, end=4, left=0, right=288, bottom=86, ellipsisCount=0)])

    def download(self, scale=2):
        return next(row for row in self.records() if row['scene']=='downloads' and row['fontScale']==scale)

    def test_actual_layout_accepts_full_default_large_and_wrapped_text(self):
        for scale in (1, 2): MATRIX.verify_download_location(self.download(scale), 'a'*40)
        row=self.download(); value=json.loads(row['downloadLocationRaw'])
        value['lines']=[dict(start=0,end=2,left=0,right=140,bottom=43,ellipsisCount=0),dict(start=2,end=4,left=0,right=140,bottom=86,ellipsisCount=0)]
        row['downloadLocationRaw']=json.dumps(value); MATRIX.verify_download_location(row,'a'*40)

    def test_full_accessibility_text_does_not_hide_native_layout_clipping(self):
        changes=[lambda v:v['lines'][0].update(end=2),
                 lambda v:v['lines'][0].update(ellipsisCount=1),
                 lambda v:v['lines'][0].update(right=349),
                 lambda v:v.update(layoutHeight=109),
                 lambda v:v.update(visibleHeight=143),
                 lambda v:v.update(height=143,visibleHeight=143),
                 lambda v:v.update(width=143,visibleWidth=143),
                 lambda v:v.update(scrollX=1),lambda v:v.update(layoutRequested=True)]
        for change in changes:
            row=self.download();value=json.loads(row['downloadLocationRaw']);change(value)
            self.assertEqual(value['text'],'保存位置')
            row['downloadLocationRaw']=json.dumps(value)
            with self.subTest(case=changes.index(change)),self.assertRaises(AssertionError):MATRIX.verify_download_location(row,'a'*40)

    def test_download_layout_source_nonce_scale_and_actual_observation_required(self):
        for key,value in [('sourceCommit','b'*40),('nonce','d'*32),('fontScale',1),('density',2),
                          ('actualAndroidLayout',False),('windowFocused',False),('status','failed')]:
            row=self.download();native=json.loads(row['downloadLocationRaw']);native[key]=value;row['downloadLocationRaw']=json.dumps(native)
            with self.subTest(field=key),self.assertRaises(AssertionError):MATRIX.verify_download_location(row,'a'*40)
        rows=self.records();next(row for row in rows if row['scene']=='downloads').pop('downloadLocationRaw')
        with self.assertRaises(KeyError):MATRIX.verify_captures(rows,'a'*40)

    def test_download_layout_duplicate_or_nonfinite_raw_json_rejected(self):
        row=self.download();row['downloadLocationRaw']='{"schema":1,'+row['downloadLocationRaw'][1:]
        with self.assertRaises(AssertionError):MATRIX.verify_download_location(row,'a'*40)
        row=self.download();row['downloadLocationRaw']=row['downloadLocationRaw'].replace('"density": 3','"density": NaN')
        with self.assertRaises(ValueError):MATRIX.verify_download_location(row,'a'*40)

    def test_current_ui_has_full_detail_matrix_and_retains_every_previous_scene(self):
        previous={(viewport,1,scene) for viewport in ('360x640','412x640')
                  for scene in ('chat','environments','network','proxy','entries','browser','preferences')}
        previous|={('360x640',2,scene) for scene in ('chat','proxy','entries','browser','preferences')}
        self.assertEqual(len(self.records()),111)
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
