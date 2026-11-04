"""Real fake-ADB capture controls; no Android, UI acceptance or input execution."""
import ast
import copy
import importlib.util
import json
from pathlib import Path
import re
import stat
import sys
import tempfile
import time
import types
import unittest
from unittest import mock
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('actual_ui_visual_capture', ROOT / 'tools/gecko/ui_visual_capture.py')
CAPTURE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CAPTURE)
MATRIX_SPEC = importlib.util.spec_from_file_location('native_ui_matrix', ROOT / 'tools/gecko/ui_visual_contract.py')
MATRIX = importlib.util.module_from_spec(MATRIX_SPEC)
MATRIX_SPEC.loader.exec_module(MATRIX)
XML = b'<?xml version="1.0"?><hierarchy rotation="0"><node text="fresh current native UI" /></hierarchy>'
RUNNER = ROOT / 'tests/gecko/run_ui_visuals.py'


def runner_functions(*names):
    """Compile actual runner functions without its device/install top-level actions."""
    tree = ast.parse(RUNNER.read_text())
    functions = [copy.deepcopy(n) for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert {n.name for n in functions} == set(names)
    return ast.Module(body=functions, type_ignores=[])


class ModelClock:
    """Deterministic transport model, not Android timing or screenshot evidence."""
    def __init__(self, value=100): self.value = value
    def monotonic(self): return self.value
    def sleep(self, seconds): self.value += seconds


class DownloadReadinessRunnerTest(unittest.TestCase):
    def run_readiness(self, *, reveal_after=1, scene='downloads', scrollable=True, crash=False):
        # Keep the actual setup and complete original readiness loop verbatim in
        # AST form; stop before the downstream Android capture operations.
        module = runner_functions('capture')
        capture = module.body[0]
        end = next(i for i, node in enumerate(capture.body) if isinstance(node, ast.While)) + 1
        capture.body = capture.body[:end] + [ast.parse('return xml,readiness_scrolls,label_nonce,deadline').body[0]]
        ast.fix_missing_locations(module)
        clock = ModelClock(); calls = []; deadlines = []; gestures = []
        target = '项目资料与界面设计说明.pdf'
        def adb(*values):
            calls.append(values)
            if values[:3] == ('shell', 'input', 'swipe'): gestures.append(values)
            if values[:4] == ('logcat', '-d', '-s', 'AndroidRuntime:E'):
                return 'FATAL EXCEPTION: actual fixture failure' if crash else ''
            return ''
        def dump(deadline=None):
            deadlines.append(deadline); clock.value += 1
            visible = reveal_after is not None and len(gestures) >= reveal_after
            text = target if visible else '保存位置'
            return ('<hierarchy><node class="android.widget.ScrollView" scrollable="'
                    + str(scrollable).lower() + '" bounds="[0,264][1920,828]">'
                    + '<node text="'+text+'" /></node></hierarchy>')
        namespace = dict(time=clock, json=json, print=lambda *a, **k: None, adb=adb, dump=dump,
                         last_geometry=(640, 360, 1), records=[], package='local.pocketchat.test',
                         uuid=types.SimpleNamespace(uuid4=lambda: types.SimpleNamespace(hex='a'*32)),
                         ET=ET, re=re)
        exec(compile(module, str(RUNNER), 'exec'), namespace)
        try:
            result = namespace['capture']('current', 640, 360, 1, scene)
        except Exception as failure:
            return failure, gestures, deadlines, clock, calls
        return result, gestures, deadlines, clock, calls

    def test_actual_download_loop_uses_one_real_bounded_viewport_swipe(self):
        result, gestures, deadlines, clock, _ = self.run_readiness()
        self.assertEqual(result[1], 1); self.assertIn('项目资料与界面设计说明.pdf', result[0])
        self.assertEqual(gestures, [('shell','input','swipe','960','715','960','376','350')])
        self.assertEqual(deadlines, [135, 135]); self.assertEqual(result[3], 135)
        self.assertLess(clock.value, 135)

    def test_already_visible_filename_needs_no_scroll(self):
        result, gestures, deadlines, _, _ = self.run_readiness(reveal_after=0)
        self.assertEqual(result[1], 0); self.assertEqual(gestures, []); self.assertEqual(deadlines, [135])

    def test_missing_filename_is_not_replaced_by_save_location_or_eight_swipes(self):
        result, gestures, deadlines, clock, _ = self.run_readiness(reveal_after=None)
        self.assertIsInstance(result, AssertionError); self.assertIn('screen did not appear', str(result))
        self.assertEqual(len(gestures), 8); self.assertEqual(set(deadlines), {135})
        self.assertGreater(clock.value, 135)

    def test_no_scrollable_content_and_other_scene_cannot_fabricate_readiness(self):
        for options in (dict(scrollable=False, reveal_after=None), dict(scene='chat', reveal_after=None)):
            with self.subTest(options=options):
                result, gestures, deadlines, _, _ = self.run_readiness(**options)
                self.assertIsInstance(result, AssertionError); self.assertEqual(gestures, [])
                self.assertEqual(set(deadlines), {135})

    def test_runtime_crash_is_fatal_before_any_readiness_swipe(self):
        result, gestures, _, _, _ = self.run_readiness(crash=True)
        self.assertIsInstance(result, AssertionError); self.assertIn('Android UI crashed', str(result))
        self.assertEqual(gestures, [])


class DownloadFreshObservationRunnerTest(unittest.TestCase):
    def setUp(self):
        self.parent_nonce = 'a'*32; self.fresh_nonce = 'b'*32; self.source = 'c'*40
        self.clock = ModelClock(120); self.commands = []; self.log_reads = 0
        row = dict(downloadLocationNonce=self.parent_nonce, fontScale=1)
        self.initial = NativeCaptureCoverageTest().label(row)
        self.initial.update(sourceCommit=self.source, invocationNonce=self.parent_nonce,
                            activityIdentity=10, rootIdentity=20, buttonIdentity=30,
                            top=750, visibleHeight=78)
        self.fresh = dict(self.initial, nonce=self.fresh_nonce, top=450, visibleHeight=144,
                          startedUptimeMs=120, observedUptimeMs=130)
        self.initial_raw = json.dumps(self.initial, separators=(',', ':'))
        self.fresh_raw = json.dumps(self.fresh, separators=(',', ':'))
        self.initial_log = 'I PocketDownloadLabel: '+self.initial_raw+'\n'
        self.fresh_log = self.initial_log+'I PocketDownloadLabel: '+self.fresh_raw+'\n'
        self.namespace = dict(time=self.clock, json=json, source=self.source,
            args=types.SimpleNamespace(adb='model-adb', serial='emulator-model'), package='local.pocketchat.test',
            subprocess=types.SimpleNamespace(check_output=self.check_output),
            uuid=types.SimpleNamespace(uuid4=lambda: types.SimpleNamespace(hex=self.fresh_nonce)))
        exec(compile(runner_functions('adb_scene','download_label_packets','observe_scrolled_download'), str(RUNNER), 'exec'), self.namespace)

    def check_output(self, values, timeout):
        self.commands.append((values, timeout)); self.clock.value += .1
        if values[3] == 'logcat':
            self.log_reads += 1
            return (self.initial_log if self.log_reads == 1 else self.fresh_log).encode()
        return b'Status: ok\nActivity: local.pocketchat.test/local.pocketchat.UiVisualIntegrationActivity\n'

    def observe(self, deadline=135):
        return self.namespace['observe_scrolled_download'](self.parent_nonce, deadline)

    def replace_fresh(self, **changes):
        value = dict(self.fresh, **changes)
        self.fresh_log = self.initial_log+'I PocketDownloadLabel: '+json.dumps(value)+'\n'

    def test_actual_helpers_keep_clipped_raw_and_request_same_activity_fresh_probe(self):
        nonce, history = self.observe()
        self.assertEqual(nonce, self.fresh_nonce); self.assertEqual(history, [self.initial_raw, self.fresh_raw])
        self.assertEqual(json.loads(history[0])['visibleHeight'], 78)
        launch = self.commands[1][0]
        self.assertEqual(launch[:9], ['model-adb','-s','emulator-model','shell','am','start','-W','--activity-single-top','-n'])
        extras = launch[10:]
        self.assertEqual(extras, ['--es','visualObserveAction','download-location','--es','visualObserveNonce',self.fresh_nonce,
            '--es','visualParentNonce',self.parent_nonce,'--es','visualSourceCommit',self.source])
        self.assertNotIn('visualAction', launch); self.assertNotIn('visualNonce', launch)
        self.assertTrue(all(0 < timeout <= 15 for _, timeout in self.commands))
        row = dict(scene='downloads',downloadLocationNonce=nonce,downloadLocationRaw=history[1],fontScale=1,
                   actualPixels=[1920,1080],densityDpi=480)
        MATRIX.verify_download_location(row, self.source)
        row.update(downloadLocationNonce=self.parent_nonce, downloadLocationRaw=history[0])
        with self.assertRaises(AssertionError): MATRIX.verify_download_location(row, self.source)

    def test_same_activity_root_and_button_are_each_required(self):
        for key in ('activityIdentity','rootIdentity','buttonIdentity'):
            for replacement in (999, '10', True, None):
                with self.subTest(field=key,replacement=replacement):
                    self.log_reads=0;self.clock.value=120;self.replace_fresh(**{key:replacement})
                    with self.assertRaises(AssertionError): self.observe()

    def test_wrong_source_parent_or_failed_probe_is_rejected(self):
        for key, value in (('sourceCommit','d'*40),('invocationNonce','e'*32),('status','rejected'),('status','failed')):
            with self.subTest(field=key, value=value):
                self.log_reads=0;self.clock.value=120;self.replace_fresh(**{key:value})
                with self.assertRaises(AssertionError): self.observe()

    def test_missing_duplicate_or_wrong_initial_packet_never_requests_fresh_probe(self):
        initial=self.initial_log
        for log in ('', initial+initial,
                    'I PocketDownloadLabel: '+json.dumps(dict(self.initial, sourceCommit='d'*40)),
                    'I PocketDownloadLabel: '+json.dumps(dict(self.initial, invocationNonce='e'*32)),
                    'I PocketDownloadLabel: '+json.dumps(dict(self.initial, status='failed'))):
            with self.subTest(log=log[:100]):
                self.initial_log=log;self.log_reads=0;self.commands=[];self.clock.value=120
                with self.assertRaises(AssertionError): self.observe()
                self.assertEqual(len(self.commands),1)

    def test_duplicate_fresh_packet_is_rejected(self):
        self.fresh_log += 'I PocketDownloadLabel: '+self.fresh_raw+'\n'
        with self.assertRaises(AssertionError): self.observe()

    def test_parser_rejects_duplicate_fields_and_nonfinite_values(self):
        parse=self.namespace['download_label_packets']
        for raw, error in ((self.fresh_raw.replace('{','{"schema":1,',1), AssertionError),
                           (self.fresh_raw.replace('"density":3','"density":NaN'), ValueError)):
            with self.subTest(raw=raw[:50]), self.assertRaises(error): parse(raw,self.fresh_nonce)

    def test_old_nonce_only_cannot_satisfy_fresh_observation_and_deadline_is_not_reset(self):
        self.fresh_log=self.initial_log
        with self.assertRaises(TimeoutError): self.observe(deadline=121)
        self.assertLessEqual(self.clock.value,121.1)
        self.assertTrue(all(0 < timeout <= 1 for _, timeout in self.commands))

    def test_expired_existing_scene_budget_runs_no_transport(self):
        with self.assertRaises(TimeoutError): self.observe(deadline=119)
        self.assertEqual(self.commands,[])

    def test_fresh_glyph_or_visibility_failure_still_fails_original_native_gate(self):
        for changes in (dict(visibleHeight=143), dict(lines=[dict(start=0,end=2,left=0,right=140,bottom=86,ellipsisCount=1)])):
            with self.subTest(changes=changes):
                self.log_reads=0;self.clock.value=120;self.replace_fresh(**changes)
                nonce,history=self.observe()
                row=dict(scene='downloads',downloadLocationNonce=nonce,downloadLocationRaw=history[-1],fontScale=1,actualPixels=[1920,1080],densityDpi=480)
                with self.assertRaises(AssertionError): MATRIX.verify_download_location(row,self.source)

    def final_evidence(self, raw=None, deadline=135, history=None):
        capture=runner_functions('capture').body[0]
        actual=next(node for node in capture.body if isinstance(node,ast.If) and
                    any(isinstance(child,ast.Name) and isinstance(child.ctx,ast.Store) and child.id=='label_log'
                        for child in ast.walk(node)))
        function=ast.parse('def final_download_evidence(label_nonce,download_observation_history,deadline,record):\n pass').body[0]
        function.body=[actual,ast.parse('return record').body[0]]
        module=ast.fix_missing_locations(ast.Module(body=[function],type_ignores=[]))
        def check_output(values,timeout):
            self.commands.append((values,timeout))
            return (self.fresh_log.encode() if raw is None else raw)
        with tempfile.TemporaryDirectory(prefix='download-final-evidence-') as directory:
            namespace=dict(self.namespace, variant='current',scene='downloads',stem='model',shots=Path(directory),
                           subprocess=types.SimpleNamespace(check_output=check_output),verify_download_location=MATRIX.verify_download_location)
            exec(compile(module,str(RUNNER),'exec'),namespace)
            row=dict(scene='downloads',fontScale=1,actualPixels=[1920,1080],densityDpi=480)
            return namespace['final_download_evidence'](self.fresh_nonce,
                [self.initial_raw,self.fresh_raw] if history is None else history,deadline,row)

    def test_actual_final_block_keeps_history_strict_utf8_and_remaining_deadline(self):
        row=self.final_evidence()
        self.assertEqual(row['downloadLocationRaw'],self.fresh_raw)
        self.assertEqual(row['downloadLocationObservationHistory'],[self.initial_raw,self.fresh_raw])
        self.assertIs(row['downloadLocationSameActivityRootButton'],True)
        self.assertEqual(self.commands[-1][1],15)
        with self.assertRaises(UnicodeDecodeError): self.final_evidence(raw=b'\xff')
        before=len(self.commands)
        with self.assertRaises(TimeoutError): self.final_evidence(deadline=119)
        self.assertEqual(len(self.commands),before)

    def test_final_log_must_match_original_fresh_raw_not_just_equivalent_json(self):
        reformatted=json.dumps(self.fresh,indent=1).replace('\n',' ')
        self.assertEqual(json.loads(reformatted),json.loads(self.fresh_raw))
        with self.assertRaises(AssertionError): self.final_evidence(raw=('I PocketDownloadLabel: '+reformatted).encode())

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
