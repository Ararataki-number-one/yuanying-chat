"""Execute browser controller target/diagnostic policy on synthetic host inputs.

These checks do not tap a device, execute Android WebView, or establish picker
acceptance. The real Android workload still has to observe DocumentsUI twice.
"""
import copy
import contextlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    'browser_targeting_controller', ROOT / 'tools/browser/run_integration.py')
controller = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(controller)


class BrowserTargetingTests(unittest.TestCase):
    def current(self, stage='file-picker-1'):
        identifier = 'download' if stage == 'download-click' else 'upload'
        return {
            'stage': stage, 'status': 'running', 'sourceCommit': 'a' * 40,
            'runNonce': 'b' * 32, 'taskId': 2,
            'tapTarget': {
                'id': identifier, 'x': 162, 'y': 380, 'ready': True,
                'stableSamples': 2, 'visualStateComplete': True,
                'nativeFrame': {
                    'screenX': 0, 'screenY': 215, 'width': 324, 'height': 353,
                    'visibleLeft': 0, 'visibleTop': 215,
                    'visibleRight': 324, 'visibleBottom': 568,
                    'shown': True, 'windowFocus': True, 'foreground': True,
                    'layoutRequested': False,
                },
                'dom': {
                    'id': identifier, 'x': 162.0, 'y': 165.0,
                    'left': 8.0, 'top': 140.0, 'right': 316.0,
                    'bottom': 190.0, 'viewportWidth': 324.0,
                    'viewportHeight': 353.0, 'hitTarget': True,
                    'hitId': identifier,
                    'hitTag': 'A' if identifier == 'download' else 'INPUT',
                    'scrollX': 0.0, 'scrollY': 240.0,
                    'devicePixelRatio': 1.0, 'visualScale': 1.0,
                    'url': 'http://browser-fixture.example/second',
                },
            },
        }

    def test_valid_visible_hit_proof_for_each_required_single_tap(self):
        for stage in ('file-picker-1', 'file-picker-2', 'download-click'):
            with self.subTest(stage=stage):
                current = self.current(stage)
                before = copy.deepcopy(current)
                self.assertEqual(controller.validate_tap_target(current), (162, 380))
                self.assertEqual(current, before)

    def test_java_rounding_and_uniform_native_scale_are_preserved(self):
        current = self.current()
        frame, dom = current['tapTarget']['nativeFrame'], current['tapTarget']['dom']
        frame.update(screenX=10, screenY=210, width=648, height=706,
                     visibleLeft=10, visibleTop=210,
                     visibleRight=658, visibleBottom=916)
        dom.update(left=8.25, right=315.25, x=161.75, devicePixelRatio=2.0)
        current['tapTarget'].update(x=334, y=540)
        self.assertEqual(controller.validate_tap_target(current), (334, 540))

    def test_unproved_source5_coordinate_packet_is_rejected(self):
        # These are the observed source5 tap coordinates. Its packet contained
        # no DOM/native visibility or hit proof, so no guessed CSS rect is used.
        current = self.current()
        current['tapTarget'] = {'x': 162, 'y': 467}
        with self.assertRaises(AssertionError):
            controller.validate_tap_target(current)

    def test_invalid_target_inputs_cannot_authorize_a_tap(self):
        mutations = {
            'unknown stage': lambda c: c.update(stage='file-picker-3'),
            'wrong stage id': lambda c: c['tapTarget'].update(id='download'),
            'wrong DOM id': lambda c: c['tapTarget']['dom'].update(id='download'),
            'not ready': lambda c: c['tapTarget'].update(ready=False),
            'string readiness': lambda c: c['tapTarget'].update(ready='true'),
            'one stable sample': lambda c: c['tapTarget'].update(stableSamples=1),
            'boolean sample count': lambda c: c['tapTarget'].update(stableSamples=True),
            'visual frame incomplete': lambda c: c['tapTarget'].update(visualStateComplete=False),
            'hidden native view': lambda c: c['tapTarget']['nativeFrame'].update(shown=False),
            'no window focus': lambda c: c['tapTarget']['nativeFrame'].update(windowFocus=False),
            'background Activity': lambda c: c['tapTarget']['nativeFrame'].update(foreground=False),
            'pending native layout': lambda c: c['tapTarget']['nativeFrame'].update(layoutRequested=True),
            'zero native width': lambda c: c['tapTarget']['nativeFrame'].update(width=0),
            'negative native height': lambda c: c['tapTarget']['nativeFrame'].update(height=-1),
            'boolean native size': lambda c: c['tapTarget']['nativeFrame'].update(width=True),
            'empty native visible rect': lambda c: c['tapTarget']['nativeFrame'].update(visibleRight=0),
            'point clipped by native view': lambda c: c['tapTarget']['nativeFrame'].update(visibleLeft=200),
            'wrong transformed X': lambda c: c['tapTarget'].update(x=163),
            'stale transformed Y': lambda c: c['tapTarget'].update(y=467),
            'boolean screen coordinate': lambda c: c['tapTarget'].update(x=True),
            'float screen coordinate': lambda c: c['tapTarget'].update(y=380.0),
            'DOM hit another element': lambda c: c['tapTarget']['dom'].update(hitTarget=False),
            'zero CSS viewport': lambda c: c['tapTarget']['dom'].update(viewportWidth=0),
            'nonfinite CSS viewport': lambda c: c['tapTarget']['dom'].update(viewportHeight=math.inf),
            'NaN CSS point': lambda c: c['tapTarget']['dom'].update(x=math.nan),
            'boolean CSS point': lambda c: c['tapTarget']['dom'].update(x=True),
            'point no longer rect center': lambda c: c['tapTarget']['dom'].update(x=160.0),
            'inverted element rect': lambda c: c['tapTarget']['dom'].update(right=7.0),
            'point beyond CSS viewport': lambda c: c['tapTarget']['dom'].update(viewportHeight=160.0),
            'missing native frame': lambda c: c['tapTarget'].pop('nativeFrame'),
            'missing DOM proof': lambda c: c['tapTarget'].pop('dom'),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                current = self.current()
                mutate(current)
                with self.assertRaises(AssertionError):
                    controller.validate_tap_target(current)

    def test_failure_diagnostic_preserves_only_controlled_bounded_fields(self):
        current = self.current()
        current.update(cookie='NEVER_LOG_COOKIE', draft='NEVER_LOG_DRAFT',
                       unknown='NEVER_LOG_UNKNOWN')
        current['tapTarget']['dom']['cookie'] = 'NEVER_LOG_DOM_COOKIE'
        current['tapTarget']['nativeFrame']['unknown'] = 'NEVER_LOG_NATIVE_UNKNOWN'
        actions = [{'kind': 'tap', 'stage': 'file-picker-1', 'x': 162, 'y': 380,
                    'cookie': 'NEVER_LOG_ACTION_COOKIE'}]
        resumed = ['topResumedActivity=ActivityRecord{controlled local.pocketchat.test/.BrowserIntegrationActivity}']
        before = copy.deepcopy((current, resumed, actions))
        packet = controller.diagnostic_failure(
            current, AssertionError('Controlled chooser failure'), resumed, actions)
        encoded = json.dumps(packet, ensure_ascii=False, separators=(',', ':'))
        self.assertLessEqual(len(encoded.encode('utf-8')), 16000)
        self.assertIn('file-picker-1', encoded)
        self.assertIn('Controlled chooser failure', encoded)
        self.assertIn('BrowserIntegrationActivity', encoded)
        self.assertNotIn('NEVER_LOG_', encoded)
        self.assertEqual((current, resumed, actions), before)

    def test_oversized_unicode_failure_diagnostic_stays_parseable_and_bounded(self):
        current = self.current()
        current.update(failure='控制失败😀' * 10000,
                       checks=[{'name': 'bounded check ' + ('汉字😀' * 100),
                                'pass': False} for _ in range(200)])
        resumed = ['topResumedActivity=' + ('组件😀' * 1000) for _ in range(300)]
        actions = [{'kind': 'tap', 'stage': 'file-picker-1', 'x': 162, 'y': 380}
                   for _ in range(300)]
        before = copy.deepcopy((current, resumed, actions))
        packet = controller.diagnostic_failure(
            current, RuntimeError('failure 😀' * 10000), resumed, actions)
        encoded = json.dumps(packet, ensure_ascii=False, separators=(',', ':'))
        self.assertLessEqual(len(encoded.encode('utf-8')), 16000)
        self.assertEqual(json.loads(encoded), packet)
        self.assertEqual((current, resumed, actions), before)

    def test_failure_before_first_validated_report_remains_diagnostic_only(self):
        packet = controller.diagnostic_failure(
            None, RuntimeError('Controlled boot failure'), [], [])
        encoded = json.dumps(packet, ensure_ascii=False, separators=(',', ':'))
        self.assertIn('Controlled boot failure', encoded)
        self.assertLessEqual(len(encoded.encode('utf-8')), 16000)

    def run_controller_failure(self, ready):
        """Run the real controller with explicit, failing device boundaries.

        No emulator or build is impersonated as successful acceptance. The
        synthetic device always remains in BrowserIntegrationActivity, so the
        unchanged real DocumentsUI condition must fail after exactly one tap.
        """
        current = self.current()
        current['tapTarget']['ready'] = ready
        identity = {'controlledHostBoundary': True}
        current['buildIdentity'] = identity
        resumed = ('topResumedActivity=ActivityRecord{controlled '
                   'local.pocketchat.test/local.pocketchat.BrowserIntegrationActivity t2}\n')
        calls = []

        def checked_source(args, **kwargs):
            self.assertEqual(kwargs, {'cwd': ROOT, 'text': True})
            if args == ['git', 'status', '--porcelain']:
                return ''
            if args == ['git', 'rev-parse', 'HEAD']:
                return 'a' * 40 + '\n'
            if args == ['git', 'rev-parse', 'HEAD^{tree}']:
                return 'c' * 40 + '\n'
            self.fail('Unexpected source boundary: ' + repr(args))

        def device_boundary(args, **kwargs):
            self.assertEqual(args[:3], ['adb', '-s', 'emulator-5554'])
            self.assertTrue(kwargs.get('capture_output'))
            self.assertIn('timeout', kwargs)
            parts = args[3:]
            calls.append(parts)
            output = b''
            if parts == ['shell', 'getprop', 'ro.kernel.qemu']:
                output = b'1\n'
            elif parts == ['exec-out', 'content', 'read', '--uri',
                           'content://local.pocketchat.test.evidence/build-identity']:
                output = json.dumps(identity).encode()
            elif parts == ['exec-out', 'content', 'read', '--uri',
                           'content://local.pocketchat.test.browser-evidence/result']:
                output = json.dumps(current).encode()
            elif parts == ['shell', 'dumpsys', 'activity', 'activities']:
                output = resumed.encode()
            elif parts[:4] == ['shell', 'settings', 'get', 'system']:
                output = b'null\n'
            elif parts[:4] in (['shell', 'settings', 'put', 'system'],
                               ['shell', 'settings', 'delete', 'system']):
                pass
            elif parts == ['shell', 'am', 'force-stop', 'local.pocketchat.test']:
                pass
            elif parts[:4] == ['shell', 'am', 'start', '-W']:
                pass
            elif parts[:3] == ['shell', 'input', 'tap']:
                pass
            elif parts == ['shell', 'dumpsys', 'webviewupdate']:
                output = b'Controlled host boundary; no Android provider measured\n'
            elif parts == ['exec-out', 'screencap', '-p']:
                output = b''
            else:
                self.fail('Unexpected device boundary: ' + repr(parts))
            return subprocess.CompletedProcess(args, 0, stdout=output, stderr=b'')

        clock = iter(range(1000))
        stdout = io.StringIO()
        with tempfile.TemporaryDirectory(prefix='browser-targeting-host-') as temporary:
            output = Path(temporary)
            with patch.object(controller.subprocess, 'check_output', side_effect=checked_source), \
                    patch.object(controller.subprocess, 'run', side_effect=device_boundary), \
                    patch.object(controller, 'expected_build', return_value=identity), \
                    patch.object(controller, 'verify_installed', side_effect=self.assertEqual), \
                    patch.object(controller.uuid, 'uuid4', return_value=SimpleNamespace(hex='b' * 32)), \
                    patch.object(controller.time, 'monotonic', side_effect=lambda: next(clock)), \
                    patch.object(controller.time, 'sleep'), \
                    patch.object(sys, 'argv', ['browser-controller', '--output', str(output)]), \
                    contextlib.redirect_stdout(stdout):
                with self.assertRaises(AssertionError) as failure:
                    controller.main()
            report = json.loads((output / 'results.json').read_text())
        diagnostic_lines = [line for line in stdout.getvalue().splitlines()
                            if line.startswith('BROWSER_ACCEPTANCE_FAILURE ')]
        self.assertEqual(len(diagnostic_lines), 1)
        diagnostic = json.loads(diagnostic_lines[0].split(' ', 1)[1])
        return str(failure.exception), report, diagnostic, calls

    def test_actual_controller_keeps_one_tap_and_documentsui_failure_gate(self):
        failure, report, diagnostic, calls = self.run_controller_failure(True)
        self.assertEqual(failure, 'The trusted tap did not open Android DocumentsUI: file-picker-1')
        self.assertEqual([row for row in calls if row[:3] == ['shell', 'input', 'tap']],
                         [['shell', 'input', 'tap', '162', '380']])
        self.assertEqual(report['actualAndroidTaps'], 1)
        self.assertEqual(report['status'], 'failed')
        self.assertFalse(report['actualAndroidExecution'])
        self.assertFalse(report['actualAndroidWebViewExecution'])
        self.assertIsNone(report['result'])
        self.assertTrue(report['executionInputsUnchanged'])
        self.assertEqual(report['lastValidatedReport']['stage'], 'file-picker-1')
        self.assertEqual(diagnostic['lastValidatedReport']['tapTarget']['x'], 162)
        self.assertIn('BrowserIntegrationActivity', '\n'.join(diagnostic['lastResumedComponents']))
        self.assertFalse(any(row[:3] == ['shell', 'input', 'keyevent'] for row in calls))

    def test_actual_controller_never_taps_without_stable_target_proof(self):
        failure, report, diagnostic, calls = self.run_controller_failure(False)
        self.assertEqual(failure, 'Trusted target has no stable visual proof')
        self.assertFalse(any(row[:3] == ['shell', 'input', 'tap'] for row in calls))
        self.assertEqual(report['actualAndroidTaps'], 0)
        self.assertEqual(report['status'], 'failed')
        self.assertFalse(report['actualAndroidExecution'])
        self.assertFalse(report['actualAndroidWebViewExecution'])
        self.assertFalse(diagnostic['lastValidatedReport']['tapTarget']['ready'])

    def test_exact_fixture_scripts_scroll_and_observe_without_clicking(self):
        # Only DOM geometry and the hit-test are controlled here. This executes
        # the real Java fixture's JS, but it is not an Android rendering test.
        source = (ROOT / 'tests/gecko/BrowserIntegrationActivity.java').read_text()
        scripts = {}
        for name in ('TARGET_SCROLL_SCRIPT', 'TARGET_SAMPLE_SCRIPT'):
            match = re.search(r'^\s*static final String ' + name
                              + r'\s*=\s*("(?:\\.|[^"\\])*");\s*$',
                              source, re.MULTILINE)
            self.assertIsNotNone(match, 'Expected one exact Java string literal: ' + name)
            scripts[name] = json.loads(match.group(1))
        node = shutil.which('node')
        self.assertIsNotNone(node, 'Node is required for the declared DOM host check')
        jsdom = os.environ.get('JSDOM_MODULE', str(
            ROOT / 'work/chat-smoothness-deps/node_modules/jsdom'))
        program = r'''
const fs=require('node:fs'), {JSDOM}=require(process.env.JSDOM_MODULE);
const code=JSON.parse(fs.readFileSync(0,'utf8'));
const dom=new JSDOM('<!doctype html><input id="upload" type="file" multiple><a id="download"><span id="download-label">Download</span></a><div id="overlay"></div>',
  {url:'http://browser-fixture.example/second',runScripts:'outside-only'});
const w=dom.window, d=w.document, upload=d.getElementById('upload'), download=d.getElementById('download');
Object.defineProperties(w,{innerWidth:{value:324,configurable:true},innerHeight:{value:353,configurable:true},devicePixelRatio:{value:1,configurable:true}});
w.visualViewport={scale:1};let rect={left:8,top:500,right:316,bottom:550,width:308,height:50};
let clicks=0, scrolls=[];
for(const element of [upload,download]){
  element.click=()=>{clicks++;};
  element.getBoundingClientRect=()=>rect;
  element.scrollIntoView=options=>{scrolls.push({id:element.id,...options});rect={left:8,top:140,right:316,bottom:190,width:308,height:50};};
}
d.elementFromPoint=(x,y)=>x>=rect.left&&x<=rect.right&&y>=rect.top&&y<=rect.bottom&&y>=0&&y<353?upload:d.getElementById('overlay');
const scroll=w.eval('('+code.TARGET_SCROLL_SCRIPT+')'), sample=w.eval('('+code.TARGET_SAMPLE_SCRIPT+')');
const before=sample('upload'), scrolled=scroll('upload'), after=sample('upload');
d.elementFromPoint=()=>d.getElementById('overlay');const covered=sample('upload');
d.elementFromPoint=()=>d.getElementById('download-label');const descendant=sample('download');
let missingScroll=false,missingSample=false;
try{scroll('missing');}catch(error){missingScroll=true;}
try{sample('missing');}catch(error){missingSample=true;}
delete w.visualViewport;const withoutVisualViewport=sample('download');
process.stdout.write(JSON.stringify({before,scrolled,after,covered,descendant,scrolls,clicks,missingScroll,missingSample,withoutVisualViewport}));
w.close();
'''
        ran = subprocess.run([node, '-e', program], input=json.dumps(scripts),
                             env=dict(os.environ, JSDOM_MODULE=jsdom),
                             text=True, capture_output=True, timeout=20)
        self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)
        observed = json.loads(ran.stdout)
        self.assertGreater(observed['before']['y'], observed['before']['viewportHeight'])
        self.assertFalse(observed['before']['hitTarget'])
        self.assertEqual(observed['scrolls'], [
            {'id': 'upload', 'block': 'center', 'inline': 'center'}])
        self.assertEqual(observed['scrolled'], {'id': 'upload'})
        self.assertEqual(observed['clicks'], 0)
        self.assertTrue(observed['missingScroll'])
        self.assertTrue(observed['missingSample'])
        self.assertTrue(observed['after']['hitTarget'])
        self.assertFalse(observed['covered']['hitTarget'])
        self.assertTrue(observed['descendant']['hitTarget'])
        self.assertEqual(observed['withoutVisualViewport']['visualScale'], 1)
        current = self.current()
        current['tapTarget']['dom'] = observed['after']
        self.assertEqual(controller.validate_tap_target(current), (162, 380))
        current['tapTarget']['dom'] = observed['covered']
        with self.assertRaises(AssertionError):
            controller.validate_tap_target(current)


if __name__ == '__main__':
    unittest.main(verbosity=2)
