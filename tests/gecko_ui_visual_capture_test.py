"""Real fake-ADB capture controls; no Android, UI acceptance or input execution."""
import ast
import copy
import hashlib
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
    if 'capture' in names:
        declarations = [n for n in tree.body if isinstance(n, ast.Assign)
                        and any(isinstance(t, ast.Name) and t.id in ('UI_NAVIGATION_CONTRACT', 'WORKSPACE_LAYOUT_CONTRACT') for t in n.targets)]
        assert len(declarations) == 2, 'Actual browser and workspace declarations required'
        functions.extend(copy.deepcopy(declarations))
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


class EnvironmentPreferencesCaptureTest(unittest.TestCase):
    labels = ('保存本机输入草稿', '恢复网页滚动位置', '仅在 Wi-Fi 下载文件',
              '自动清理 30 天以上的无引用中间文件', '自动检测外部网络响应')

    def observe(self, frames):
        capture = runner_functions('capture').body[0]
        branches = [step for step in capture.body if isinstance(step, ast.If)
                    and ast.unparse(step.test) == "scene == 'preferences'"
                    and any(isinstance(n, ast.For) for n in step.body)]
        self.assertEqual(len(branches), 1)
        def dump():
            controls, note = frames[min(len(reads), len(frames) - 1)]
            root = ET.Element('hierarchy')
            scroll = ET.SubElement(root, 'node', {'class':'android.widget.ScrollView', 'bounds':'[0,0][900,1600]'})
            for label in controls:
                ET.SubElement(scroll, 'node', {'class':'android.widget.CheckBox', 'text':label})
            ET.SubElement(scroll, 'node', {'class':'android.widget.TextView', 'text':note})
            reads.append(1)
            return ET.tostring(root, encoding='unicode')
        reads = []
        namespace = dict(scene='preferences', variant='fixture', xml='', time=ModelClock(),
                         click_editor_tab=lambda *args: 0, dump=dump, ET=ET, re=re, adb=lambda *args: None)
        exec(compile(ast.Module(body=branches, type_ignores=[]), str(RUNNER), 'exec'), namespace)
        return namespace['preference_check']

    def test_actual_preferences_scene_observes_all_five_controls_across_scrolls(self):
        result = self.observe([(self.labels[:2], ''), (self.labels[2:], '')])
        self.assertEqual(result['preferenceControls'], sorted(self.labels))
        self.assertEqual(result['scrollFrames'], 2)
        self.assertTrue(result['removedNoticeControlsAbsent'])

    def test_missing_controls_and_retired_reply_setting_or_explanation_fail(self):
        for frame in ((self.labels[:-1], ''), (self.labels + ('允许此环境的后台回复提醒',), ''),
                      (self.labels, '后台回复检测由应用设置统一控制；关闭检测时不会发出回复完成提醒。')):
            with self.subTest(frame=frame), self.assertRaises(AssertionError):
                self.observe([frame])


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
    if mode in ['idle','stale-idle','idle-nonzero','idle-stdout','idle-prefix','idle-suffix','idle-whitespace']:
        if mode=='stale-idle':local.write_bytes(b'<hierarchy><node text="stale idle attempt" /></hierarchy>')
        value='ERROR: could not get idle state.'
        if mode=='idle-prefix':value='unexpected '+value
        if mode=='idle-suffix':value+=' unexpected'
        if mode=='idle-whitespace':value=' '+value
        if mode=='idle-stdout':print('unexpected stdout')
        print(value,file=sys.stderr);raise SystemExit(1 if mode=='idle-nonzero' else 0)
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


class IdleUiVisualCaptureTest(unittest.TestCase):
    setUp = UiVisualCaptureTest.setUp
    modes = UiVisualCaptureTest.modes
    commands = UiVisualCaptureTest.commands
    report = UiVisualCaptureTest.report
    assert_read_only = UiVisualCaptureTest.assert_read_only

    def test_exact_idle_error_can_only_reacquire_a_fresh_owned_file_within_same_budget(self):
        self.modes('stale-idle','ok')
        deadline=time.monotonic()+3
        self.assertEqual(self.capture.read(deadline=deadline),XML.decode())
        calls=self.commands()
        self.assertEqual(len(calls),3)
        self.assertNotEqual(calls[0][-1],calls[1][-1])
        self.assertEqual(calls[1][-1],calls[2][-1])
        self.assertFalse(any(row[:2]==['shell','cat'] and row[-1]==calls[0][-1] for row in calls))
        rows=self.report()['attempts']
        self.assertEqual([row['status'] for row in rows],['not-ready','captured'])
        self.assertEqual({row['existingSceneDeadline'] for row in rows},{deadline})
        self.assertNotIn('xmlSha256',rows[0])
        self.assertEqual(rows[0]['reason'],CAPTURE.IDLE_NOT_READY)
        self.assert_read_only()

    def test_idle_without_deadline_remains_one_failed_acquisition(self):
        self.modes('idle','ok')
        with self.assertRaises(CAPTURE.CaptureNotReady):self.capture.read()
        self.assertEqual(len(self.commands()),1)
        self.assertNotIn('xmlSha256',self.report()['attempts'][0])
        self.assert_read_only()

    def test_only_exact_observed_idle_stderr_and_success_exit_are_retryable(self):
        for mode in ('idle-nonzero','idle-stdout','idle-prefix','idle-suffix','idle-whitespace'):
            with self.subTest(mode=mode):
                (self.root/'next.txt').unlink(missing_ok=True)
                self.modes(mode,'ok');before=len(self.commands())
                with self.assertRaises((RuntimeError,CAPTURE.subprocess.CalledProcessError)):
                    self.capture.read(deadline=time.monotonic()+3)
                self.assertEqual(len(self.commands()),before+1)
                self.assertEqual(self.report()['attempts'][-1]['status'],'failed')
        self.assert_read_only()

    def test_continuous_idle_cannot_create_a_retry_budget_or_capture_stale_xml(self):
        self.modes('stale-idle')
        deadline=time.monotonic()+.3
        with self.assertRaises(TimeoutError):self.capture.read(deadline=deadline)
        self.assertEqual(len(self.commands()),1)
        self.assertEqual(self.report()['attempts'][0]['existingSceneDeadline'],deadline)
        self.assertNotIn('xmlSha256',self.report()['attempts'][0])
        self.assert_read_only()


class RecordedIdleAcquisitionTest(unittest.TestCase):
    """Original native failures replayed at a mocked process boundary, not new Android evidence."""
    def test_all_six_original_errors_remain_uncaptured_and_keep_the_actual_deadline(self):
        fixtures=(('c6-api32-idle-errors.json','79bc32533a02b3e17faacddc5d66d6de8d4a73ca8836616b510e77b1c3b4dd34',2),
                  ('c6-api35-idle-errors.json','9b912ef31820e681720cc4b2cdd9f3530f964a39950295dba64882c1588c3c71',4))
        for filename,digest,count in fixtures:
            raw=(ROOT/'tests/browser-address-host'/filename).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(),digest)
            fixture=json.loads(raw);self.assertIs(fixture['recordedFailureOnly'],True)
            self.assertEqual(len(fixture['cases']),count)
            for case in fixture['cases']:
                original=case['attempt'];command=original['commands'][0]
                self.assertEqual(original['status'],'failed')
                self.assertEqual(case['callerBudgetSeconds'],20)
                self.assertEqual(len(original['commands']),1)
                self.assertEqual(command['parts'][:3],['shell','uiautomator','dump'])
                self.assertEqual(command['exitCode'],0)
                self.assertEqual(command['stdout']['text'],'')
                self.assertEqual(command['stderr']['text'],'ERROR: could not get idle state.\n')
                for stream in ('stdout','stderr'):
                    payload=command[stream]['text'].encode()
                    self.assertEqual(len(payload),command[stream]['bytes'])
                    self.assertEqual(hashlib.sha256(payload).hexdigest(),command[stream]['sha256'])
                deadline=original['existingSceneDeadline']
                clock=ModelClock(command['startedAtMonotonicNanos']/1e9)
                self.assertGreater(deadline-command['completedAtMonotonicNanos']/1e9,0)
                def process(parts,**options):
                    self.assertEqual(parts[3:6],['shell','uiautomator','dump'])
                    self.assertLessEqual(options['timeout'],command['timeoutSeconds']+.001)
                    clock.value=command['completedAtMonotonicNanos']/1e9
                    return CAPTURE.subprocess.CompletedProcess(parts,command['exitCode'],
                        command['stdout']['text'].encode(),command['stderr']['text'].encode())
                with self.subTest(file=filename,case=case['case']),tempfile.TemporaryDirectory() as temporary:
                    capture=CAPTURE.UiVisualCapture(adb='mocked-read-only-adb',serial='emulator-model',
                        source=fixture['sourceCommit'],diagnostics=Path(temporary)/'attempts.json')
                    with mock.patch.object(CAPTURE.time,'monotonic',side_effect=clock.monotonic),\
                         mock.patch.object(CAPTURE.subprocess,'run',side_effect=process) as boundary:
                        with self.assertRaises(CAPTURE.CaptureNotReady):capture.attempt(deadline)
                    boundary.assert_called_once()
                    row=capture.records[0]
                    self.assertEqual(row['status'],'not-ready')
                    self.assertEqual(row['existingSceneDeadline'],deadline)
                    self.assertNotIn('xmlSha256',row)
                    self.assertEqual(json.loads(raw)['cases'][fixture['cases'].index(case)]['attempt']['status'],'failed')


class DeviceHierarchyAdapterTest(unittest.TestCase):
    """Execute the current adapter; only preparation and OS processes are model boundaries."""
    def test_window_sync_is_opt_in_and_fresh_read_uses_only_the_remaining_budget(self):
        source='a'*40;clock=ModelClock();calls=[]
        driver=types.SimpleNamespace(evidence=dict(status='verified',sourceCommit=source),
            dump_parts=mock.Mock(side_effect=lambda path,remaining,*,sync_window:
                ['shell','native-observer-model',path,'sync-window-input'] if sync_window else []))
        def process(parts,**options):
            action=parts[3:];calls.append((action,options['timeout']))
            if action[1]=='native-observer-model':
                self.assertEqual(action[-1],'sync-window-input');clock.value+=1.25
                return CAPTURE.subprocess.CompletedProcess(parts,0,('UI hierchary dumped to: '+action[2]).encode(),b'')
            self.assertEqual(action[:2],['shell','cat']);clock.value+=.25
            return CAPTURE.subprocess.CompletedProcess(parts,0,XML,b'')
        with tempfile.TemporaryDirectory() as temporary:
            capture=CAPTURE.UiVisualCapture(adb='model-adb',serial='emulator-model',source=source,
                diagnostics=Path(temporary)/'capture.json',acquisition_driver=driver)
            with mock.patch.object(CAPTURE.time,'monotonic',side_effect=clock.monotonic),\
                 mock.patch.object(CAPTURE.subprocess,'run',side_effect=process):
                self.assertEqual(capture.read(deadline=102,sync_window=True),XML.decode())
            driver.dump_parts.assert_called_once_with(calls[0][0][2],2,sync_window=True)
            self.assertEqual([timeout for _,timeout in calls],[2,.75])
            self.assertEqual(calls[0][0][2],calls[1][0][2])
            row=capture.records[0]
            self.assertEqual(row['existingSceneDeadline'],102)
            self.assertEqual(row['windowInputSynchronization'],'UiAutomation.syncInputTransactions')
            self.assertEqual(row['xmlSha256'],hashlib.sha256(XML).hexdigest())

    def test_failed_or_expired_window_sync_never_reads_a_hierarchy(self):
        for outcome in ('failed','expired','timeout'):
            with self.subTest(outcome=outcome),tempfile.TemporaryDirectory() as temporary:
                clock=ModelClock();calls=[]
                driver=types.SimpleNamespace(evidence=dict(sourceCommit='a'*40),
                    dump_parts=mock.Mock(return_value=['shell','native-observer-model','owned.xml','sync-window-input']))
                capture=CAPTURE.UiVisualCapture(adb='model-adb',serial='emulator-model',source='a'*40,
                    diagnostics=Path(temporary)/'capture.json',acquisition_driver=driver)
                def process(parts,**options):
                    calls.append(parts);self.assertEqual(options['timeout'],2)
                    if outcome=='timeout':raise CAPTURE.subprocess.TimeoutExpired(parts,options['timeout'])
                    if outcome=='failed':return CAPTURE.subprocess.CompletedProcess(parts,1,b'',b'window sync failed')
                    clock.value=102
                    return CAPTURE.subprocess.CompletedProcess(parts,0,b'',b'')
                expected={'failed':CAPTURE.subprocess.CalledProcessError,'expired':TimeoutError,
                          'timeout':CAPTURE.subprocess.TimeoutExpired}[outcome]
                with mock.patch.object(CAPTURE.time,'monotonic',side_effect=clock.monotonic),\
                     mock.patch.object(CAPTURE.subprocess,'run',side_effect=process):
                    with self.assertRaises(expected):capture.read(deadline=102,sync_window=True)
                self.assertEqual(len(calls),1)
                self.assertNotIn('xmlSha256',capture.records[0])
                self.assertEqual(capture.records[0]['status'],'failed')

    def test_window_sync_requires_an_explicit_mode_driver_and_existing_deadline(self):
        with tempfile.TemporaryDirectory() as temporary:
            options=dict(adb='model-adb',serial='emulator-model',source='a'*40,
                diagnostics=Path(temporary)/'capture.json')
            driver=types.SimpleNamespace(evidence=dict(sourceCommit='a'*40),dump_parts=mock.Mock())
            for prepared,deadline,mode in ((None,102,True),(driver,None,True),(driver,102,1),
                                          (driver,102,'true'),(driver,102,None)):
                capture=CAPTURE.UiVisualCapture(**options,acquisition_driver=prepared)
                with mock.patch.object(CAPTURE.time,'monotonic',return_value=100),\
                     mock.patch.object(CAPTURE.subprocess,'run') as boundary:
                    with self.assertRaises(ValueError):capture.read(deadline=deadline,sync_window=mode)
                    boundary.assert_not_called();driver.dump_parts.assert_not_called()

    def test_prepared_native_command_and_fresh_xml_use_the_same_parent_deadline(self):
        source='a'*40;clock=ModelClock();calls=[]
        driver=types.SimpleNamespace(evidence=dict(status='verified',sourceCommit=source,sourceTree='b'*40),
            dump_parts=mock.Mock(side_effect=lambda path,remaining:['shell','native-observer-model',path]))
        prepare=mock.Mock(return_value=driver)
        def process(parts,**options):
            action=parts[3:];calls.append((action,options['timeout']));clock.value+=.25
            if action[:2]==['shell','native-observer-model']:
                return CAPTURE.subprocess.CompletedProcess(parts,0,('UI hierchary dumped to: '+action[2]).encode(),b'')
            self.assertEqual(action[:2],['shell','cat'])
            return CAPTURE.subprocess.CompletedProcess(parts,0,XML,b'')
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'capture.json'
            with mock.patch.dict(sys.modules,{'ui_hierarchy_driver':types.SimpleNamespace(prepare_driver=prepare)}):
                capture=CAPTURE.UiVisualCapture.for_device(adb='model-adb',serial='emulator-model',source=source,diagnostics=path)
            prepare.assert_called_once_with(adb='model-adb',serial='emulator-model',source=source,diagnostics_dir=path.parent)
            driver.evidence['additionalNote']='changed after capture initialization'
            self.assertNotIn('additionalNote',capture.report['acquisitionDriver'])
            self.assertEqual(capture.report['acquisitionDriver']['sourceCommit'],source)
            with mock.patch.object(CAPTURE.time,'monotonic',side_effect=clock.monotonic),\
                 mock.patch.object(CAPTURE.subprocess,'run',side_effect=process):
                self.assertEqual(capture.read(deadline=102),XML.decode())
            self.assertEqual([timeout for _,timeout in calls],[2,1.75])
            self.assertEqual(calls[0][0][2],calls[1][0][2])
            driver.dump_parts.assert_called_once_with(calls[0][0][2],2)
            self.assertEqual(capture.records[0]['existingSceneDeadline'],102)
            self.assertEqual(capture.records[0]['xmlSha256'],hashlib.sha256(XML).hexdigest())
            self.assertNotIn('windowInputSynchronization',capture.records[0])

    def test_setup_failure_wrong_source_and_expiry_never_fall_back_or_read_old_xml(self):
        with tempfile.TemporaryDirectory() as temporary:
            options=dict(adb='model-adb',serial='emulator-model',source='a'*40,diagnostics=Path(temporary)/'capture.json')
            prepare=mock.Mock(side_effect=ValueError('Unverified compiled driver'))
            with mock.patch.dict(sys.modules,{'ui_hierarchy_driver':types.SimpleNamespace(prepare_driver=prepare)}),\
                 mock.patch.object(CAPTURE.subprocess,'run') as boundary:
                with self.assertRaisesRegex(ValueError,'Unverified compiled driver'):
                    CAPTURE.UiVisualCapture.for_device(**options)
                boundary.assert_not_called()
            driver=types.SimpleNamespace(evidence=dict(sourceCommit='b'*40),dump_parts=mock.Mock())
            with self.assertRaisesRegex(ValueError,'different source'):
                CAPTURE.UiVisualCapture(**options,acquisition_driver=driver)
            driver.evidence['sourceCommit']='a'*40
            capture=CAPTURE.UiVisualCapture(**options,acquisition_driver=driver)
            with mock.patch.object(CAPTURE.time,'monotonic',return_value=102),\
                 mock.patch.object(CAPTURE.subprocess,'run') as boundary:
                with self.assertRaises(TimeoutError):capture.read(deadline=102)
                boundary.assert_not_called();driver.dump_parts.assert_not_called()


class FormatterReadinessCaptureTest(unittest.TestCase):
    """Synthetic native process outputs; the actual prepared-command adapter remains in use."""
    STACK = (b'java.lang.NullPointerException: synthetic API32 child boundary\n'
             b'\tat com.android.uiautomator.core.AccessibilityNodeInfoDumper.childNafCheck(AccessibilityNodeInfoDumper.java:296)\n')

    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('formatter_capture_driver', ROOT/'tools/gecko/ui_hierarchy_driver.py')
        cls.driver_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.driver_module)

    def make_capture(self, directory, mode='native'):
        source = 'a' * 40
        evidence = dict(status='verified', sourceCommit=source, sourceTree='b' * 40, runId='1234', runAttempt='2',
            installedJar=dict(remotePath='/data/local/tmp/pocketchat-ui-hierarchy-' + 'a' * 12 + '-1234-2-' + 'b' * 32 + '.jar',
                              sha256='c' * 64), device=dict(systemJarSha256='d' * 64),
            scope='Synthetic host preparation boundary, not Android evidence')
        driver = self.driver_module.HierarchyDriver(evidence, Path(directory)/'driver.json')
        if mode == 'unverified':
            driver.evidence['status'] = 'preparing'
        elif mode == 'generic':
            driver = types.SimpleNamespace(evidence=evidence,
                dump_parts=lambda path, remaining: ['shell', 'native-observer-model', path])
        elif mode == 'legacy':
            driver = None
        return CAPTURE.UiVisualCapture(adb='model-adb', serial='emulator-model', source=source,
            diagnostics=Path(directory)/'capture.json', acquisition_driver=driver)

    def marker(self, remote, raw=None):
        raw = self.STACK if raw is None else raw
        return (self.driver_module.FORMATTER_NOT_READY + remote + ' ' + str(len(raw)) + ' '
                + hashlib.sha256(raw).hexdigest() + '\n').encode()

    def test_classified_formatter_reacquires_new_owned_xml_with_same_parent_deadline(self):
        clock = ModelClock(); calls = []
        def process(command, **options):
            parts = command[3:]; calls.append((parts, options['timeout'])); clock.value += .25
            if len(calls) == 1:
                remote = parts[5]
                return CAPTURE.subprocess.CompletedProcess(command, 4, self.marker(remote), self.STACK)
            if len(calls) == 2:
                return CAPTURE.subprocess.CompletedProcess(command, 0,
                    ('UI hierchary dumped to: ' + parts[5] + '\n').encode(), b'')
            self.assertEqual(parts[:2], ['shell', 'cat'])
            return CAPTURE.subprocess.CompletedProcess(command, 0, XML, b'')
        with tempfile.TemporaryDirectory() as directory:
            capture = self.make_capture(directory)
            with mock.patch.object(CAPTURE.time, 'monotonic', side_effect=clock.monotonic), \
                 mock.patch.object(CAPTURE.time, 'sleep', side_effect=clock.sleep) as polling, \
                 mock.patch.object(CAPTURE.subprocess, 'run', side_effect=process):
                self.assertEqual(capture.read(deadline=102), XML.decode())
            self.assertEqual([timeout for _, timeout in calls], [2, 1.25, 1])
            self.assertNotEqual(calls[0][0][5], calls[1][0][5])
            self.assertEqual(calls[2][0], ['shell', 'cat', calls[1][0][5]])
            self.assertEqual([row['status'] for row in capture.records], ['not-ready', 'captured'])
            self.assertEqual({row['existingSceneDeadline'] for row in capture.records}, {102})
            first = capture.records[0]
            self.assertEqual(len(first['commands']), 1)
            self.assertEqual(first['commands'][0]['stderr'], capture.output(self.STACK))
            self.assertEqual(first['commands'][0]['stdout'], capture.output(self.marker(first['remotePath'])))
            self.assertNotIn('xmlSha256', first)
            self.assertNotEqual(first['reason'], CAPTURE.NULL_ROOT)
            polling.assert_called_once_with(.5)  # Existing acquisition polling only.

    def test_legacy_generic_unverified_or_modified_signals_are_fatal_without_cat(self):
        for mode in ('legacy', 'generic', 'unverified', 'wrong-exit', 'extra-stderr', 'empty-stderr',
                     'wrong-path', 'wrong-hash', 'missing-marker', 'extra-stdout'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                capture = self.make_capture(directory, mode)
                calls = []
                def process(command, **options):
                    parts = command[3:]; calls.append(parts)
                    remote = next(part for part in parts if part.startswith('/sdcard/pocketchat-ui-visual-'))
                    code, raw, marker = 4, self.STACK, self.marker(remote)
                    if mode == 'wrong-exit': code = 1
                    if mode == 'extra-stderr': raw += b'additional cleanup failure\n'
                    if mode == 'empty-stderr': raw = b''; marker = self.marker(remote, raw)
                    if mode == 'wrong-path': marker = self.marker(remote.replace('-1.xml', '-2.xml'))
                    if mode == 'wrong-hash': marker = marker[:-65] + b'0' * 64 + b'\n'
                    if mode == 'missing-marker': marker = b''
                    if mode == 'extra-stdout': marker += b'unknown output\n'
                    return CAPTURE.subprocess.CompletedProcess(command, code, marker, raw)
                with mock.patch.object(CAPTURE.time, 'monotonic', return_value=100), \
                     mock.patch.object(CAPTURE.subprocess, 'run', side_effect=process):
                    with self.assertRaises(CAPTURE.subprocess.CalledProcessError):
                        capture.read(deadline=102)
                self.assertEqual(len(calls), 1)
                self.assertEqual(capture.records[0]['status'], 'failed')
                self.assertNotIn('xmlSha256', capture.records[0])

    def test_formatter_signal_does_not_create_a_deadline_or_accept_late_transport(self):
        for mode in ('no-deadline', 'continuous', 'late'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                clock = ModelClock(); capture = self.make_capture(directory); calls = []
                deadline = None if mode == 'no-deadline' else 100.75
                def process(command, **options):
                    parts = command[3:]; calls.append(parts)
                    clock.value += .75 if mode == 'late' else .25
                    return CAPTURE.subprocess.CompletedProcess(command, 4, self.marker(parts[5]), self.STACK)
                with mock.patch.object(CAPTURE.time, 'monotonic', side_effect=clock.monotonic), \
                     mock.patch.object(CAPTURE.time, 'sleep', side_effect=clock.sleep), \
                     mock.patch.object(CAPTURE.subprocess, 'run', side_effect=process):
                    with self.assertRaises(CAPTURE.CaptureNotReady if mode == 'no-deadline' else TimeoutError):
                        capture.read(deadline=deadline)
                self.assertEqual(len(calls), 1)
                self.assertEqual(capture.records[0]['existingSceneDeadline'], deadline)
                self.assertEqual(capture.records[0]['status'], 'failed' if mode == 'late' else 'not-ready')
                self.assertNotIn('xmlSha256', capture.records[0])


class CompactQuickEnvironmentContractTest(unittest.TestCase):
    """Execute actual runner guards on synthetic hierarchies and input boundaries."""
    @staticmethod
    def functions(*names):
        tree=ast.parse(RUNNER.read_text())
        functions=[copy.deepcopy(node) for node in ast.walk(tree) if isinstance(node,ast.FunctionDef) and node.name in names]
        assert {node.name for node in functions}==set(names) and len(functions)==len(names)
        namespace={'ET':ET,'re':re}
        exec(compile(ast.Module(body=functions,type_ignores=[]),'actual-compact-guards','exec'),namespace)
        return namespace

    @staticmethod
    def hierarchy(slot=0):
        root=ET.Element('hierarchy')
        fields=[('TextView','快速切换环境','快速切换环境','false'),
                ('EditText','搜索名称、分组、备注或编号','搜索要切换的环境','false'),
                ('Button','','关闭快速切换环境','false'),
                ('Button',f'{slot+1:02d}  Controlled environment · 当前\n工作 · 继续会话','切换到 Controlled environment，工作 · 继续会话','true')]
        for index,(kind,text,description,selected) in enumerate(fields):
            ET.SubElement(root,'node',{'class':'android.widget.'+kind,'package':'local.pocketchat.test',
                'text':text,'content-desc':description,'selected':selected,'enabled':'true','clickable':'true',
                'bounds':f'[20,{100+index*100}][700,{180+index*100}]'})
        return root

    def parse(self,root,slot=0):
        return self.functions('quick_environment_sheet')['quick_environment_sheet'](ET.tostring(root,encoding='unicode'),slot,'local.pocketchat.test')

    def test_current_production_quick_sheet_requires_title_search_close_and_current_slot(self):
        value=self.parse(self.hierarchy())
        self.assertEqual(value['title'],'快速切换环境');self.assertEqual(value['currentSlot'],0)
        self.assertEqual(value['searchDescription'],'搜索要切换的环境')
        self.assertEqual(value['closeDescription'],'关闭快速切换环境')
        producer=(ROOT/'app/src/main/java/local/pocketchat/EnvironmentSwitcherUi.java').read_text()
        self.assertIn('new ReferenceUi.Modal(activity,"快速切换环境")',producer)
        self.assertIn('search.setContentDescription("搜索要切换的环境")',producer)
        self.assertIn('action.setSelected(current)',producer)
        self.assertEqual(self.parse(self.hierarchy(7),7)['currentSlot'],7)

    def test_missing_ambiguous_old_title_and_wrong_application_are_rejected(self):
        for index in range(4):
            root=self.hierarchy();root.remove(root[index])
            with self.subTest(missing=index),self.assertRaises(AssertionError):self.parse(root)
        for index in range(4):
            root=self.hierarchy();root.append(copy.deepcopy(root[index]))
            with self.subTest(duplicate=index),self.assertRaises(AssertionError):self.parse(root)
            root=self.hierarchy();root[index].set('package','other.application')
            with self.subTest(package=index),self.assertRaises(AssertionError):self.parse(root)
        root=self.hierarchy();root[0].set('text','切换环境');root[0].set('content-desc','切换环境')
        with self.assertRaises(AssertionError):self.parse(root)
        root=self.hierarchy();root[0].set('text','快速切换环境 - different dialog')
        with self.assertRaises(AssertionError):self.parse(root)

    def test_wrong_slot_role_identity_and_noninteractive_controls_are_rejected(self):
        for index,key,value in [(0,'class','android.widget.Button'),(1,'content-desc','wrong search'),
                                (2,'content-desc','关闭其他对话框'),(3,'selected','false'),
                                (3,'text','02  Other · 当前\n工作'),(3,'content-desc','not an environment')]:
            root=self.hierarchy();root[index].set(key,value)
            with self.subTest(index=index,key=key),self.assertRaises(AssertionError):self.parse(root)
        for index in (1,2,3):
            for key in ('enabled','clickable'):
                root=self.hierarchy();root[index].set(key,'false')
                with self.subTest(index=index,key=key),self.assertRaises(AssertionError):self.parse(root)
        for slot in (True,False,-1,8,'0',0.0):
            with self.subTest(slot=slot),self.assertRaises(AssertionError):self.parse(self.hierarchy(),slot)

    def test_empty_inverted_and_missing_rendered_bounds_are_rejected(self):
        for index in range(4):
            for bounds in ('','[0,0][0,1]','[5,8][4,9]','[1,9][2,8]','unobserved'):
                root=self.hierarchy();root[index].set('bounds',bounds)
                with self.subTest(index=index,bounds=bounds),self.assertRaises(AssertionError):self.parse(root)

    def run_controls(self,names=('drawer','environment','more'),home_resumes=True,more_label='浏览器菜单'):
        namespace=self.functions('visible','focus','quick_environment_sheet');clock=ModelClock()
        state={'xml':'<hierarchy/>','resumed':'local.pocketchat.CompactChromeIntegrationActivity','actions':0,'action':''};commands=[]
        targets={name:[10+index*10,20] for index,name in enumerate(('drawer','environment','more'))}
        sample={'controls':[{'name':name,'tap':targets[name]} for name in names]}
        def adb(*command):
            commands.append(command)
            if command[:3]==('shell','input','tap'):
                name=next(name for name,target in targets.items() if command[3:]==tuple(map(str,target)))
                state['actions']+=1;state['action']='activity:local.pocketchat.WindowHomeActivity' if name=='drawer' else name
                if name=='drawer' and home_resumes:state['resumed']='local.pocketchat.WindowHomeActivity'
                if name=='environment':state['xml']=ET.tostring(self.hierarchy(),encoding='unicode')
                if name=='more':state['xml']='<hierarchy><node text="'+more_label+'" /></hierarchy>'
            elif command==('shell','input','keyevent','KEYCODE_BACK'):
                state['resumed']='local.pocketchat.CompactChromeIntegrationActivity';state['xml']='<hierarchy/>'
            elif command==('shell','dumpsys','activity','activities'):return 'topResumedActivity= '+state['resumed']
            return ''
        def event(command,kind):return {'action':state['action'],'actions':state['actions'],'page':0}
        namespace.update(adb=adb,chrome_event=event,dump=lambda:state['xml'],time=clock,package='local.pocketchat.test',component='local.pocketchat.test/local.pocketchat.CompactChromeIntegrationActivity',command='controlled',sample=sample,taps=[],management_navigation=None,environment_sheet=None)
        loop=next(node for node in ast.walk(ast.parse(RUNNER.read_text())) if isinstance(node,ast.For) and ast.unparse(node.target)=='control' and ast.unparse(node.iter)=="sample['controls']" and any(isinstance(value,ast.Name) and value.id=='management_navigation' for value in ast.walk(node)))
        exec(compile(ast.Module(body=[copy.deepcopy(loop)],type_ignores=[]),'actual-compact-input-loop','exec'),namespace)
        return namespace,commands

    def test_three_actual_control_calls_preserve_management_quick_switch_and_close(self):
        namespace,commands=self.run_controls()
        self.assertEqual(len([command for command in commands if command[:3]==('shell','input','tap')]),3)
        self.assertEqual(len([command for command in commands if command==('shell','input','keyevent','KEYCODE_BACK')]),3)
        self.assertEqual([row['control'] for row in namespace['taps']],['drawer','environment','more'])
        self.assertEqual(namespace['management_navigation'],dict(activity='local.pocketchat.WindowHomeActivity',actualDrawerTap=True,resumedThenReturned=True))
        self.assertEqual(namespace['environment_sheet']['currentSlot'],0)

    def test_legacy_conversation_label_cannot_fake_current_browser_menu(self):
        with self.assertRaises(TimeoutError):self.run_controls(more_label='会话选项')

    def test_environment_cannot_replace_missing_or_unresumed_management_navigation(self):
        with self.assertRaises(AssertionError):self.run_controls(('environment','more'))
        with self.assertRaises(TimeoutError):self.run_controls(home_resumes=False)

    def test_exact_visible_gate_and_twenty_second_budget_are_unchanged(self):
        namespace=self.functions('visible');clock=ModelClock()
        namespace.update(time=clock,dump=lambda:'<hierarchy><node text="快速切换环境" /></hierarchy>')
        namespace['visible']('快速切换环境')
        with self.assertRaises(TimeoutError):namespace['visible']('切换环境')
        self.assertGreaterEqual(clock.value,120);self.assertLess(clock.value,120.3)
        clock=ModelClock();namespace['time']=clock
        with self.assertRaises(TimeoutError):namespace['visible']('快速切换环境',False)
        self.assertGreaterEqual(clock.value,120);self.assertLess(clock.value,120.3)

    def test_original_capture_test_methods_and_screenshot_matrix_are_preserved(self):
        import subprocess
        from ui_checkpoint_source_compatibility import require_current_runner
        from historical_source_inputs import historical_bytes
        base='03d0c4ace70942a3f6899daffac086cc6682885e'
        path=Path(__file__).resolve().relative_to(ROOT).as_posix()
        old=subprocess.check_output(['git','show',base+':'+path],cwd=ROOT,text=True)
        def methods(source):
            return {node.name:{child.name:ast.get_source_segment(source,child) for child in node.body if isinstance(child,ast.FunctionDef)}
                    for node in ast.parse(source).body if isinstance(node,ast.ClassDef)}
        before,after=methods(old),methods(Path(__file__).read_text())
        for name,value in before.items():self.assertEqual(after[name],value)
        old=subprocess.check_output(['git','show',base+':tests/gecko/run_ui_visuals.py'],cwd=ROOT,text=True);current=require_current_runner(historical_bytes('tests/gecko/run_ui_visuals.py')).decode()
        def functions(source):return [ast.get_source_segment(source,node) for node in ast.walk(ast.parse(source)) if isinstance(node,ast.FunctionDef)]
        before_functions,after_functions=functions(old),functions(current)
        for function in before_functions:self.assertEqual(after_functions.count(function),before_functions.count(function))
        self.assertIn("for width,scale in [(360,1),(412,1),(360,2)]",current)


# This original v1 fixture executes the actual retained elif from the current
# capture AST. Only its explicit protocol input is fixed; no code is rewritten.
_download_v1_setup = DownloadFreshObservationRunnerTest.setUp
def _configure_download_v1_fixture(self):
    _download_v1_setup(self)
    self.namespace['UI_NAVIGATION_CONTRACT'] = 1
    self.namespace['WORKSPACE_LAYOUT_CONTRACT'] = 1
DownloadFreshObservationRunnerTest.setUp = _configure_download_v1_fixture


if __name__=='__main__':unittest.main()
