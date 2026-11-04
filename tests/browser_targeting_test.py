"""Execute browser controller target/diagnostic policy on synthetic host inputs.

These checks do not tap a device, execute Android WebView, or establish picker
acceptance. The real Android workload still has to observe DocumentsUI twice.
"""
import copy
import contextlib
import hashlib
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
                    'nativeScale': 1.0,
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
                    'visualWidth': 324.0, 'visualHeight': 353.0,
                    'visualOffsetLeft': 0.0, 'visualOffsetTop': 0.0,
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
                     visibleRight=658, visibleBottom=916, nativeScale=2.0)
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
            'missing native scale': lambda c: c['tapTarget']['nativeFrame'].pop('nativeScale'),
            'zero native scale': lambda c: c['tapTarget']['nativeFrame'].update(nativeScale=0),
            'negative native scale': lambda c: c['tapTarget']['nativeFrame'].update(nativeScale=-1),
            'nonfinite native scale': lambda c: c['tapTarget']['nativeFrame'].update(nativeScale=math.inf),
            'boolean native scale': lambda c: c['tapTarget']['nativeFrame'].update(nativeScale=True),
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
            'missing visual width': lambda c: c['tapTarget']['dom'].pop('visualWidth'),
            'zero visual height': lambda c: c['tapTarget']['dom'].update(visualHeight=0),
            'nonfinite visual offset': lambda c: c['tapTarget']['dom'].update(visualOffsetTop=math.nan),
            'boolean visual offset': lambda c: c['tapTarget']['dom'].update(visualOffsetLeft=True),
            'negative visual offset': lambda c: c['tapTarget']['dom'].update(visualOffsetLeft=-1),
            'visual frame beyond layout viewport': lambda c: c['tapTarget']['dom'].update(visualOffsetLeft=2),
            'visual frame differs from native size': lambda c: c['tapTarget']['dom'].update(visualWidth=320),
            'layout hit outside visual viewport': lambda c: c['tapTarget']['dom'].update(visualHeight=160.0),
            'missing native frame': lambda c: c['tapTarget'].pop('nativeFrame'),
            'missing DOM proof': lambda c: c['tapTarget'].pop('dom'),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                current = self.current()
                mutate(current)
                with self.assertRaises(AssertionError):
                    controller.validate_tap_target(current)

    def source8_target(self):
        # Exact controlled Android Source8 geometry from run 41881064165.
        # No screenshot or private page is used. Its real nativeScale and visual
        # viewport disproved using nativeWidth / layoutViewportWidth as scale.
        current = self.current()
        current['tapTarget']['nativeFrame'].update(
            screenX=0, screenY=214, width=320, height=350,
            visibleLeft=0, visibleTop=214, visibleRight=320,
            visibleBottom=564, nativeScale=1.0)
        current['tapTarget']['dom'].update(x=263, y=392.875, left=8,
            top=367.875, right=518, bottom=417.875,
            viewportWidth=518, viewportHeight=567, scrollX=0, scrollY=16,
            visualWidth=320, visualHeight=350, visualOffsetLeft=103,
            visualOffsetTop=217, devicePixelRatio=1, visualScale=1)
        current['tapTarget'].update(x=160, y=390)
        return current

    def test_real_source8_visual_pan_projects_to_actual_native_point(self):
        current = self.source8_target()
        self.assertEqual(controller.validate_tap_target(current), (160, 390))
        before = copy.deepcopy(current)
        for stage in ('file-picker-1', 'file-picker-2', 'download-click'):
            with self.subTest(stage=stage):
                current['stage'] = stage
                identifier = 'download' if stage == 'download-click' else 'upload'
                current['tapTarget']['id'] = current['tapTarget']['dom']['id'] = identifier
                self.assertEqual(controller.validate_tap_target(current), (160, 390))
        self.assertEqual(before['tapTarget']['dom']['scrollY'], 16)

    def test_old_layout_width_projection_from_source8_is_rejected(self):
        current = self.source8_target()
        frame, dom = current['tapTarget']['nativeFrame'], current['tapTarget']['dom']
        old_scale = frame['width'] / dom['viewportWidth']
        old_point = (frame['screenX'] + math.floor(dom['x'] * old_scale + .5),
                     frame['screenY'] + math.floor(dom['y'] * old_scale + .5))
        self.assertEqual(old_point, (162, 457))
        current['tapTarget'].update(x=old_point[0], y=old_point[1])
        with self.assertRaisesRegex(AssertionError, 'screen transform differs'):
            controller.validate_tap_target(current)

    def test_pan_and_native_zoom_use_one_scale_with_java_rounding(self):
        current = self.source8_target()
        frame, dom = current['tapTarget']['nativeFrame'], current['tapTarget']['dom']
        frame.update(screenX=10, screenY=210, width=640, height=700,
            visibleLeft=10, visibleTop=210, visibleRight=650,
            visibleBottom=910, nativeScale=2.0)
        dom.update(devicePixelRatio=2.0, visualScale=1.0)
        current['tapTarget'].update(x=330, y=562)
        self.assertEqual(controller.validate_tap_target(current), (330, 562))
        # Pinch zoom changes nativeScale and the actual visual dimensions; DPR
        # stays two and is not multiplied into an already native scale again.
        frame.update(width=960, height=1050, visibleRight=970,
                     visibleBottom=1260, nativeScale=3.0)
        dom.update(visualScale=1.5)
        current['tapTarget'].update(x=490, y=738)
        self.assertEqual(controller.validate_tap_target(current), (490, 738))

    def test_stale_scale_offsets_or_native_visual_size_cannot_authorize_a_tap(self):
        for key, mutate in {
            'stale native scale': lambda n, d: n.update(nativeScale=.625),
            'stale left offset': lambda n, d: d.update(visualOffsetLeft=0),
            'stale top offset': lambda n, d: d.update(visualOffsetTop=0),
            'height discrepancy': lambda n, d: d.update(visualHeight=347),
            'width discrepancy': lambda n, d: d.update(visualWidth=317),
            'center outside visible pan': lambda n, d: d.update(visualOffsetTop=400,
                viewportHeight=800),
        }.items():
            with self.subTest(key=key):
                current = self.source8_target()
                mutate(current['tapTarget']['nativeFrame'], current['tapTarget']['dom'])
                with self.assertRaises(AssertionError):
                    controller.validate_tap_target(current)

    def test_actual_java_geometry_helpers_and_projection_on_both_json_runtimes(self):
        path = ROOT / 'tests/gecko/BrowserIntegrationActivity.java'
        source = path.read_text()
        def method(name):
            start = source.index('  static boolean ' + name + '(')
            opened = source.index('{', start)
            depth = 1
            end = opened + 1
            while depth:
                depth += (source[end] == '{') - (source[end] == '}')
                end += 1
            return source[start:end]
        declarations = '\n'.join(line for line in source.splitlines()
            if 'static final String[] NATIVE_TARGET_FIELDS=' in line
            or 'static final String[] DOM_TARGET_FIELDS=' in line)
        helpers = '\n'.join(method(name) for name in (
            'nativeTargetReady', 'sameNativeTarget', 'sameDomTarget', 'nativeVisualTargetReady'))
        projection = next(line.strip() for line in source.splitlines()
                          if line.strip().startswith('double scale=nativeAfter.getDouble("nativeScale");int x='))
        previous = subprocess.check_output(['git', 'show',
            '89d9b76a093ddd61b548894746b13586a3aad7d1:tests/gecko/BrowserIntegrationActivity.java'],
            cwd=ROOT, text=True)
        old_projection = next(line.strip() for line in previous.splitlines()
                              if line.strip().startswith('double scale=nativeAfter.getInt("width")/'))
        body = r'''
static int checks;static void check(boolean value){if(!value)throw new AssertionError("Geometry check "+checks);checks++;}
static JSONObject copy(JSONObject value)throws Exception{return new JSONObject(value.toString());}
public static void main(String[] args)throws Exception{
 JSONObject packet=new JSONObject(args[0]),n=packet.getJSONObject("nativeFrame"),d=packet.getJSONObject("dom");
 check(nativeTargetReady(n));check(sameNativeTarget(n,copy(n)));check(sameDomTarget(d,copy(d)));check(nativeVisualTargetReady(n,d));
 int[] base=point(n,d),old=oldPoint(n,d);check(base[0]==160&&base[1]==390);check(old[0]==162&&old[1]==457);
 JSONObject changed=copy(n);changed.put("nativeScale",1.0001);check(!sameNativeTarget(n,changed));
 changed=copy(n);changed.put("nativeScale",0);check(!nativeTargetReady(changed));
 for(String key:new String[]{"visualWidth","visualHeight","visualOffsetLeft","visualOffsetTop"}){JSONObject c=copy(d);c.put(key,c.getDouble(key)+.25);check(!sameDomTarget(d,c));}
 changed=copy(n);changed.put("width",323);check(!nativeVisualTargetReady(changed,d));
 changed.put("width",321);check(nativeVisualTargetReady(changed,d));
 JSONObject zoom=copy(n);zoom.put("screenX",10);zoom.put("screenY",210);zoom.put("width",640);zoom.put("height",700);zoom.put("nativeScale",2);
 JSONObject zd=copy(d);zd.put("devicePixelRatio",2);check(nativeVisualTargetReady(zoom,zd));
 int[] twice=point(zoom,zd);check(twice[0]==330&&twice[1]==562);
 zoom.put("width",960);zoom.put("height",1050);zoom.put("nativeScale",3);zd.put("visualScale",1.5);check(nativeVisualTargetReady(zoom,zd));
 int[] pinch=point(zoom,zd);check(pinch[0]==490&&pinch[1]==738);
 JSONObject half=copy(d);half.put("y",392.5);int[] rounded=point(n,half);check(rounded[1]==390);
 System.out.println(new JSONObject().put("checks",checks).put("point",new JSONArray(base)).put("oldPoint",new JSONArray(old)).put("javaVersion",System.getProperty("java.version")).toString());
}
'''
        java_source = ('import org.json.*; public final class TargetGeometryHost {\n'
            + declarations + '\n' + helpers
            + '\nstatic int[] point(JSONObject nativeAfter,JSONObject dom)throws Exception{' + projection + 'return new int[]{x,y};}\n'
            + 'static int[] oldPoint(JSONObject nativeAfter,JSONObject dom)throws Exception{' + old_projection + 'return new int[]{x,y};}\n'
            + body + '\n}')
        home = Path(os.environ.get('JAVA_HOME', str(ROOT / 'work/browser-ci-jdk/jdk-17.0.21+9')))
        javac = str(home / 'bin/javac') if (home / 'bin/javac').is_file() else shutil.which('javac')
        java = str(home / 'bin/java') if (home / 'bin/java').is_file() else shutil.which('java')
        self.assertTrue(java and javac, 'Actual JDK17 is required for native projection controls')
        runtimes = [
            ('desktop', '3cf6cd6892e32e2b4c1c39e0f52f5248a2f5b37646fdfbb79a66b46b618414ed',
             ['work/browser-host-deps/json.jar', 'work/ux-build-deps/json-20240303.jar']),
            ('android-json', 'dfb7bae2f404cfe0b72b4d23944698cb716b7665171812a0a4d0f5926c0fac79',
             ['work/browser-host-deps/android-json.jar', 'work/ux-build-deps/android-json.jar'])]
        reports = []
        for name, digest, candidates in runtimes:
            jar = next((ROOT / value for value in candidates if (ROOT / value).is_file()
                        and hashlib.sha256((ROOT / value).read_bytes()).hexdigest() == digest), None)
            self.assertIsNotNone(jar, 'Pinned real JSON dependency required: ' + name)
            with tempfile.TemporaryDirectory(prefix='browser-native-geometry-host-') as directory:
                temporary = Path(directory)
                (temporary / 'TargetGeometryHost.java').write_text(java_source)
                compiled = subprocess.run([javac, '--release', '17', '-cp', str(jar),
                    '-d', str(temporary), str(temporary / 'TargetGeometryHost.java')],
                    capture_output=True, text=True, timeout=30)
                self.assertEqual(compiled.returncode, 0, compiled.stderr)
                ran = subprocess.run([java, '-cp', str(temporary) + os.pathsep + str(jar),
                    'TargetGeometryHost', json.dumps(self.source8_target()['tapTarget'])],
                    capture_output=True, text=True, timeout=20)
                self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)
                report = json.loads(ran.stdout)
                self.assertEqual(report['checks'], 19)
                self.assertEqual(report['point'], [160, 390])
                self.assertEqual(report['oldPoint'], [162, 457])
                self.assertTrue(report['javaVersion'].startswith('17.'))
                reports.append(dict(runtime=name, jsonJarSha256=digest, **report))
        self.assertEqual(path.read_text(), source)
        print(json.dumps(dict(scope='Actual fixture Java geometry methods and current/previous projection statements on host JVM; explicit native/DOM JSON inputs, no Android execution',
                              actualAndroidExecution=False, reports=reports)))

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

    def run_controller_failure(self, ready, latest=None):
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
        report_reads = 0

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
            nonlocal report_reads
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
                report_reads += 1
                output = json.dumps(latest if latest is not None and report_reads > 1 else current).encode()
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

    def test_failure_refresh_observes_current_trusted_input_without_retrying(self):
        latest = self.current()
        latest['buildIdentity'] = {'controlledHostBoundary': True}
        latest['pickerBarrier'] = dict(matching=True, ordinal=1, completed=0,
            ready=False, afterTask=False, afterFrame=False, rejected=0,
            events=[dict(type='pointerdown', trusted=True, ordinal=1, x=162, y=165, focused=True)])
        latest['nativeInputEvents'] = [dict(stage='file-picker-1', action=0, x=162, y=380, handled=True)]
        failure, report, diagnostic, calls = self.run_controller_failure(True, latest)
        self.assertEqual(failure, 'The trusted tap did not open Android DocumentsUI: file-picker-1')
        self.assertEqual(report['lastValidatedReport']['pickerBarrier'], latest['pickerBarrier'])
        self.assertTrue(diagnostic['lastValidatedReport']['pickerBarrier']['events'][0]['trusted'])
        self.assertEqual(len(diagnostic['lastValidatedReport']['nativeInputEvents']), 1)
        self.assertEqual(len([row for row in calls if row[:3] == ['shell', 'input', 'tap']]), 1)
        self.assertFalse(report['actualAndroidExecution'])

    def test_failure_refresh_rejects_another_run_source_or_installed_apk(self):
        for key, value in [('runNonce', 'f' * 32), ('sourceCommit', 'f' * 40),
                           ('buildIdentity', {'wrongInstalledApk': True})]:
            with self.subTest(key=key):
                latest = self.current()
                latest.update(buildIdentity={'controlledHostBoundary': True}, failure='NEVER_ACCEPT_STALE_REPORT')
                latest[key] = value
                _, report, diagnostic, calls = self.run_controller_failure(True, latest)
                self.assertNotIn('NEVER_ACCEPT_STALE_REPORT', json.dumps(diagnostic))
                self.assertNotIn('failure', report['lastValidatedReport'])
                self.assertEqual(len([row for row in calls if row[:3] == ['shell', 'input', 'tap']]), 1)

    def test_new_input_diagnostics_remain_bounded_and_exclude_payloads(self):
        current = self.current()
        current['pickerBarrier'] = dict(matching=True, ordinal=1, completed=0, ready=False,
            events=[dict(type='pointerdown', trusted=True, x=1, y=2,
                         cookie='NEVER_LOG_INPUT_PAYLOAD', arbitrary='NEVER_LOG_ARBITRARY') for _ in range(1000)])
        current['nativeInputEvents'] = [dict(stage='file-picker-1', action=0, x=1, y=2,
            handled=True, document='NEVER_LOG_NATIVE_DOCUMENT') for _ in range(1000)]
        packet = controller.diagnostic_failure(current, 'controlled failure', [], [])
        encoded = json.dumps(packet, ensure_ascii=False)
        self.assertNotIn('NEVER_LOG_', encoded)
        self.assertEqual(len(packet['lastValidatedReport']['pickerBarrier']['events']), 12)
        self.assertEqual(len(packet['lastValidatedReport']['nativeInputEvents']), 12)
        self.assertLessEqual(len(encoded.encode()), 16000)

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
w.visualViewport={scale:1,width:324,height:353,offsetLeft:0,offsetTop:0};let rect={left:8,top:500,right:316,bottom:550,width:308,height:50};
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
        self.assertIsNone(observed['withoutVisualViewport']['visualWidth'])
        current = self.current()
        current['tapTarget']['dom'] = observed['after']
        self.assertEqual(controller.validate_tap_target(current), (162, 380))
        current['tapTarget']['dom'] = observed['covered']
        with self.assertRaises(AssertionError):
            controller.validate_tap_target(current)


class BrowserPickerBarrierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = (ROOT / 'tests/gecko/BrowserIntegrationActivity.java').read_text()
        scripts = {}
        for name in ('PICKER_ARM_SCRIPT', 'PICKER_OBSERVE_SCRIPT'):
            match = re.search(r'^\s*static final String ' + name
                              + r'\s*=\s*("(?:\\.|[^"\\])*");\s*$', source, re.MULTILINE)
            if match is None:
                raise AssertionError('Missing actual fixture script: ' + name)
            scripts[name] = json.loads(match.group(1))
        program = r'''
const fs=require('node:fs'),{JSDOM}=require(process.env.JSDOM_MODULE),code=JSON.parse(fs.readFileSync(0,'utf8'));
function setup(){
  const dom=new JSDOM('<!doctype html><input id="upload" type="file" multiple><div id="other"></div>',{url:'http://browser-fixture.example/second',runScripts:'outside-only'});
  const w=dom.window,input=w.document.getElementById('upload'),handlers=[],tasks=[],frames=[];
  const original=input.addEventListener.bind(input);
  input.addEventListener=(type,handler,...args)=>{if(type==='cancel')handlers.push(handler);return original(type,handler,...args);};
  w.setTimeout=fn=>{tasks.push(fn);return tasks.length;};w.requestAnimationFrame=fn=>{frames.push(fn);return frames.length;};
  const arm=w.eval('('+code.PICKER_ARM_SCRIPT+')'),observe=w.eval('('+code.PICKER_OBSERVE_SCRIPT+')');
  const binding=n=>({nonce:'a'.repeat(32),source:'b'.repeat(40),url:w.location.href,ordinal:n,token:String(n).repeat(32)});
  const trusted=(handler=handlers.at(-1),target=input)=>handler({type:'cancel',isTrusted:true,target});
  const task=()=>{if(tasks.length)tasks.shift()();},frame=()=>{if(frames.length)frames.shift()();};
  return {dom,w,input,handlers,tasks,frames,arm,observe,binding,trusted,task,frame};
}
const sequence=setup(),b1=sequence.binding(1);sequence.arm(b1);
const initial=sequence.observe(b1);
sequence.input.dispatchEvent(new sequence.w.Event('cancel',{bubbles:true}));
const untrusted=sequence.observe(b1),untrustedTasks=sequence.tasks.length;
sequence.trusted(sequence.handlers[0],sequence.w.document.getElementById('other'));
const wrongInput=sequence.observe(b1);
sequence.trusted();const seen=sequence.observe(b1);
sequence.trusted(sequence.handlers[0]);const taskCountAfterReplay=sequence.tasks.length;
sequence.task();const afterTask=sequence.observe(b1);
sequence.frame();const firstComplete=sequence.observe(b1);
const staleToken=sequence.observe({...b1,token:'f'.repeat(32)});
let duplicateOrdinalRejected=false,reusedTokenRejected=false;
try{sequence.arm(b1);}catch(e){duplicateOrdinalRejected=true;}
try{sequence.arm({...sequence.binding(2),token:b1.token});}catch(e){reusedTokenRejected=true;}
const b2=sequence.binding(2);sequence.arm(b2);
sequence.trusted(sequence.handlers[0]);const oldRequestReplay=sequence.observe(b2),oldReplayTasks=sequence.tasks.length;
sequence.trusted();sequence.task();const secondBeforeFrame=sequence.observe(b2);sequence.frame();const secondComplete=sequence.observe(b2);
const isolation={};
for(const name of ['nonce','source','url','token']){
  const x=setup(),binding=x.binding(1);x.arm(binding);x.trusted();x.task();x.frame();
  const value=name==='url'?'http://browser-fixture.example/other':name==='source'?'c'.repeat(40):'c'.repeat(32);
  isolation[name]=x.observe({...binding,[name]:value});x.dom.window.close();
}
for(const moment of ['beforeEvent','beforeTask','beforeFrame']){
  const x=setup(),binding=x.binding(1);x.arm(binding);
  if(moment!=='beforeEvent')x.trusted();if(moment==='beforeFrame')x.task();
  const replacement=x.w.document.createElement('input');replacement.id='upload';replacement.type='file';x.input.replaceWith(replacement);
  if(moment==='beforeEvent')x.trusted();x.task();x.frame();isolation[moment]=x.observe(binding);x.dom.window.close();
}
const navigation=setup(),navBinding=navigation.binding(1);navigation.arm(navBinding);navigation.trusted();navigation.w.history.pushState({},'','/other');navigation.task();navigation.frame();isolation.navigation=navigation.observe(navBinding);
const wrongStart=setup();let wrongStartRejected=false;try{wrongStart.arm(wrongStart.binding(2));}catch(e){wrongStartRejected=true;}
process.stdout.write(JSON.stringify({scope:'Actual fixture JavaScript on explicitly controlled host event/task/frame boundaries; no Android or trusted browser event claim',actualAndroidExecution:false,initial,untrusted,untrustedTasks,wrongInput,seen,taskCountAfterReplay,afterTask,firstComplete,staleToken,duplicateOrdinalRejected,reusedTokenRejected,oldRequestReplay,oldReplayTasks,secondBeforeFrame,secondComplete,isolation,wrongStartRejected}));
sequence.dom.window.close();navigation.dom.window.close();wrongStart.dom.window.close();
'''
        environment = dict(os.environ, JSDOM_MODULE=os.environ.get(
            'JSDOM_MODULE', str(ROOT / 'work/chat-smoothness-deps/node_modules/jsdom')))
        run = subprocess.run([shutil.which('node'), '-e', program], input=json.dumps(scripts),
                             env=environment, text=True, capture_output=True, timeout=20)
        if run.returncode:
            raise AssertionError(run.stdout + run.stderr)
        cls.observed = json.loads(run.stdout)

    def test_native_release_without_renderer_event_cannot_advance(self):
        self.assertFalse(self.observed['actualAndroidExecution'])
        self.assertFalse(self.observed['initial']['ready'])
        self.assertEqual(self.observed['initial']['completed'], 0)

    def test_untrusted_cancel_and_other_input_cannot_complete_request(self):
        for key in ('untrusted', 'wrongInput'):
            with self.subTest(key=key):
                self.assertFalse(self.observed[key]['ready'])
                self.assertEqual(self.observed[key]['completed'], 0)
                self.assertGreater(self.observed[key]['rejected'], 0)
        self.assertEqual(self.observed['untrustedTasks'], 0)

    def test_cancel_requires_a_later_task_then_a_real_frame_boundary(self):
        seen, task = self.observed['seen'], self.observed['afterTask']
        self.assertFalse(seen['ready'])
        self.assertFalse(seen['afterTask'])
        self.assertFalse(seen['afterFrame'])
        self.assertFalse(task['ready'])
        self.assertTrue(task['afterTask'])
        self.assertFalse(task['afterFrame'])
        self.assertEqual(self.observed['taskCountAfterReplay'], 1)
        self.assertTrue(self.observed['firstComplete']['ready'])
        self.assertTrue(self.observed['firstComplete']['afterTask'])
        self.assertTrue(self.observed['firstComplete']['afterFrame'])

    def test_both_cancellations_require_their_own_ordinal_and_fresh_request(self):
        self.assertEqual(self.observed['firstComplete']['completed'], 1)
        self.assertFalse(self.observed['secondBeforeFrame']['ready'])
        self.assertTrue(self.observed['secondComplete']['ready'])
        self.assertEqual(self.observed['secondComplete']['completed'], 2)
        self.assertTrue(self.observed['duplicateOrdinalRejected'])
        self.assertTrue(self.observed['reusedTokenRejected'])
        self.assertTrue(self.observed['wrongStartRejected'])

    def test_old_request_callback_replay_cannot_complete_second_picker(self):
        self.assertFalse(self.observed['oldRequestReplay']['ready'])
        self.assertEqual(self.observed['oldRequestReplay']['completed'], 1)
        self.assertEqual(self.observed['oldReplayTasks'], 0)
        self.assertFalse(self.observed['staleToken']['ready'])

    def test_wrong_source_nonce_page_token_or_replaced_input_cannot_advance(self):
        for key, value in self.observed['isolation'].items():
            with self.subTest(key=key):
                self.assertFalse(value['ready'])
                if key != 'token':
                    self.assertFalse(value['matching'])

    def test_original_java_checks_and_controller_gates_are_preserved(self):
        def java_checks(text):
            values = []
            for match in re.finditer(r'\bcheck\("', text):
                start = match.start()
                depth, quoted, escaped = 0, False, False
                for index in range(text.index('(', start), len(text)):
                    char = text[index]
                    if quoted:
                        if escaped:
                            escaped = False
                        elif char == '\\':
                            escaped = True
                        elif char == '"':
                            quoted = False
                    elif char == '"':
                        quoted = True
                    elif char == '(':
                        depth += 1
                    elif char == ')':
                        depth -= 1
                        if depth == 0:
                            values.append(text[start:index + 1])
                            break
            return values

        baseline = '03d0c4ace70942a3f6899daffac086cc6682885e'
        fixture = 'tests/gecko/BrowserIntegrationActivity.java'
        before = subprocess.check_output(['git', 'show', baseline + ':' + fixture], cwd=ROOT, text=True)
        current = (ROOT / fixture).read_text()
        self.assertEqual(len(java_checks(before)), 49)
        self.assertEqual(java_checks(current), java_checks(before))
        self.assertIn('double scale=nativeAfter.getInt("width")/dom.getDouble("viewportWidth")', before)
        self.assertNotIn('double scale=nativeAfter.getInt("width")/dom.getDouble("viewportWidth")', current)
        self.assertIn('double scale=nativeAfter.getDouble("nativeScale")', current)
        import ast
        controller_before = subprocess.check_output(
            ['git', 'show', baseline + ':tools/browser/run_integration.py'], cwd=ROOT, text=True)
        def main_raises(text):
            main = next(node for node in ast.parse(text).body
                        if isinstance(node, ast.FunctionDef) and node.name == 'main')
            return [ast.dump(node, include_attributes=False) for node in ast.walk(main)
                    if isinstance(node, ast.Raise)]
        self.assertEqual(len(main_raises(controller_before)), 14)
        self.assertEqual(main_raises((ROOT / 'tools/browser/run_integration.py').read_text()),
                         main_raises(controller_before))

    def test_both_old_native_callbacks_now_require_the_renderer_barrier(self):
        source = (ROOT / 'tests/gecko/BrowserIntegrationActivity.java').read_text()
        before = subprocess.check_output(['git', 'show',
            '03d0c4ace70942a3f6899daffac086cc6682885e:tests/gecko/BrowserIntegrationActivity.java'],
            cwd=ROOT, text=True)
        old = before[before.index('  void preparePicker()'):before.index('  void prepareDownload()')]
        current = source[source.index('  void prepareArmedPicker('):source.index('  void prepareDownload()')]
        # The old fixture could advance from its native callback plus a value
        # already equal to zero. The new path must wait on the actual renderer
        # event/task/frame result for either ordinal before reading that value.
        self.assertNotIn('awaitRendererCancellation', old)
        self.assertLess(current.index('check("Native file chooser'), current.index('awaitRendererCancellation('))
        self.assertLess(current.index('awaitRendererCancellation('), current.index('js("({files:'))
        self.assertIn('if(picker++==1)preparePicker();else prepareDownload();', current)
        self.assertIn('deadline-SystemClock.elapsedRealtime()', current)


if __name__ == '__main__':
    unittest.main(verbosity=2)
