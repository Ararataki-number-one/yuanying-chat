"""Execute the read-only driver at Android/process boundaries and reject forged receipts."""
import base64
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('tested_ui_hierarchy_driver', ROOT/'tools/gecko/ui_hierarchy_driver.py')
DRIVER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DRIVER)


def output(raw):
    return dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(),
                text=raw[:8192].decode('utf-8', 'replace'), truncated=len(raw) > 8192)


class DriverPreparationTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.work = Path(self.temporary.name)
        self.repo = self.work/'repo'
        self.repo.mkdir()
        for name in (DRIVER.JAVA_SOURCE, DRIVER.PYTHON_SOURCE):
            target = self.repo/name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT/name).read_bytes())
        self.git('init', '-q')
        self.git('add', '.')
        self.git('-c', 'user.name=Hierarchy Host', '-c', 'user.email=hierarchy@example.test',
                 'commit', '-qm', 'Current real hierarchy sources')
        self.source = self.git('rev-parse', 'HEAD').strip()
        self.paths = {}
        for key in ('java', 'javac', 'jar', 'androidJar', 'd8'):
            path = self.work/'compiler'/key
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(('boundary dependency ' + key).encode())
            self.paths[key] = path
        self.compiler = dict(javaVersion='openjdk version "17.0.21"', platform='android-37.1', buildTools='37.0.0',
            tools={key: dict(path=str(path), bytes=path.stat().st_size, sha256=DRIVER.sha(path)) for key, path in self.paths.items()})
        self.real_run = subprocess.run
        self.invocations = []
        self.api = '35'
        self.uid = '2000'
        self.qemu = '1'
        self.hardware = 'ranchu'
        self.wrong_readback = False
        self.change_source = False
        self.change_compiler = False

    def git(self, *args):
        return subprocess.check_output(['git', *args], cwd=self.repo, stderr=subprocess.PIPE, text=True)

    def boundary(self, command, **kwargs):
        command = list(map(str, command))
        if command[0] == 'git':
            return self.real_run(command, **kwargs)
        self.invocations.append(command)
        stdout, stderr = b'', b''
        if command[0] == 'test-adb':
            parts = command[3:]
            if parts[:2] == ['shell', 'id']:
                stdout = (self.uid + '\n').encode()
            elif parts[:2] == ['shell', 'getprop']:
                value = {'ro.build.version.sdk': self.api, 'ro.kernel.qemu': self.qemu,
                         'ro.hardware': self.hardware, 'ro.build.fingerprint': 'test/goldfish/boundary'}[parts[2]]
                stdout = (value + '\n').encode()
            elif parts[:2] == ['shell', 'sha256sum']:
                stdout = (('c' * 64) + '  ' + DRIVER.SYSTEM_JAR + '\n').encode()
            elif parts[0] == 'push':
                self.pushed = Path(parts[1]).read_bytes()
                stdout = b'1 file pushed\n'
            elif parts[:2] == ['exec-out', 'cat']:
                stdout = self.pushed + (b'changed' if self.wrong_readback else b'')
            else:
                raise AssertionError('Unexpected or mutating ADB preparation command: ' + repr(command))
        elif command[0] == str(self.paths['java']) and 'com.android.tools.r8.D8' in command:
            directory = Path(command[command.index('--output') + 1])
            (directory/'classes.dex').write_bytes(b'dex\n035\0host-boundary-not-Android-execution')
            if self.change_source:
                with (self.repo/DRIVER.JAVA_SOURCE).open('a') as target:
                    target.write('\n// changed during compilation\n')
            if self.change_compiler:
                self.paths['d8'].write_bytes(b'changed compiler dependency')
        elif command[0] not in [str(self.paths['javac']), str(self.paths['jar'])]:
            raise AssertionError('Unexpected compiler boundary: ' + repr(command))
        return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr=stderr)

    def prepare(self):
        with patch.object(DRIVER, 'ROOT', self.repo), patch.object(DRIVER, 'toolchain', return_value=(self.paths, self.compiler)), \
                patch.dict(os.environ, GITHUB_RUN_ID='1234', GITHUB_RUN_ATTEMPT='2'), \
                patch.object(DRIVER.subprocess, 'run', side_effect=self.boundary):
            return DRIVER.prepare_driver('test-adb', 'emulator-5556', self.source, self.work/'diagnostics')

    def test_real_preparation_binds_git_build_readback_and_root_receipt(self):
        driver = self.prepare()
        value = driver.evidence
        self.assertEqual(value['status'], 'verified')
        self.assertEqual(len(value['commands']), 11)
        self.assertEqual(driver.report_path.parent, self.work/'diagnostics')
        self.assertEqual(json.loads(driver.report_path.read_text()), value)
        self.assertFalse(value['actualAndroidExecution'])
        self.assertEqual(value['device']['viewportMode'], 'getRealSize')
        # Verification deliberately uses a different process run identity.
        with patch.dict(os.environ, GITHUB_RUN_ID='9999', GITHUB_RUN_ATTEMPT='9'):
            DRIVER.verify_evidence(value, self.source, root=self.repo)
        expected = (self.repo/DRIVER.JAVA_SOURCE).read_bytes()
        with zipfile.ZipFile(io.BytesIO(base64.b64decode(value['build']['jarBase64']))) as archive:
            self.assertEqual(archive.read(DRIVER.EMBEDDED_SOURCE), expected)
        self.assertEqual(base64.b64decode(value['installedJar']['readbackBase64']), self.pushed)

    def test_api32_uses_real_screen_coordinates_despite_system_insets(self):
        self.api = '32'
        driver = self.prepare()
        self.assertEqual(driver.evidence['device']['viewportMode'], 'getRealSize')
        DRIVER.verify_evidence(driver.evidence, self.source, root=self.repo)
        clipped = copy.deepcopy(driver.evidence)
        clipped['device']['viewportMode'] = 'getSize'
        with self.assertRaisesRegex(ValueError, 'formatter semantics'):
            DRIVER.verify_evidence(clipped, self.source, root=self.repo)

    def test_unsupported_devices_never_compile_or_push(self):
        for field, value in (('api', '34'), ('api', '36'), ('uid', '0'), ('qemu', '0'), ('hardware', 'physical')):
            with self.subTest(field=field, value=value):
                old = getattr(self, field)
                setattr(self, field, value)
                self.invocations.clear()
                with self.assertRaises(ValueError): self.prepare()
                self.assertTrue(all(command[0] == 'test-adb' for command in self.invocations))
                self.assertFalse(any('push' in command for command in self.invocations))
                setattr(self, field, old)

    def test_source_changes_reject_before_device_install(self):
        self.change_source = True
        with self.assertRaisesRegex(ValueError, 'clean committed'):
            self.prepare()
        self.assertFalse(any('push' in command for command in self.invocations))

    def test_compiler_changes_reject_before_device_install(self):
        self.change_compiler = True
        with self.assertRaisesRegex(ValueError, 'compiler dependency changed'):
            self.prepare()
        self.assertFalse(any('push' in command for command in self.invocations))

    def test_wrong_actual_readback_is_fatal_and_preserves_failed_receipt(self):
        self.wrong_readback = True
        with self.assertRaisesRegex(ValueError, 'Installed hierarchy driver bytes'):
            self.prepare()
        receipt, = (self.work/'diagnostics').glob('ui-hierarchy-driver-*.json')
        self.assertEqual(json.loads(receipt.read_text())['status'], 'failed')

    def test_dirty_or_uncommitted_sources_cannot_prepare(self):
        with (self.repo/DRIVER.JAVA_SOURCE).open('a') as stream: stream.write('\n// dirty\n')
        with self.assertRaisesRegex(ValueError, 'clean committed'): self.prepare()
        self.assertEqual(self.invocations, [])

    def test_duplicate_invalid_path_and_nonfinite_budget_are_rejected(self):
        driver = self.prepare()
        remote = '/sdcard/pocketchat-ui-visual-' + 'a' * 32 + '-1.xml'
        parts = driver.dump_parts(remote, 1.385698830)
        self.assertEqual(parts[0:5], ['shell', 'CLASSPATH=' + driver.evidence['installedJar']['remotePath'] + ':' + DRIVER.SYSTEM_JAR,
                                    'app_process', '/system/bin', DRIVER.ENTRY_POINT])
        self.assertEqual(parts[5:7], [remote, '1385'])
        self.assertEqual(parts[7:], [driver.evidence['installedJar']['sha256'], self.source,
            driver.evidence['sourceTree'], '1234', '2', driver.evidence['device']['systemJarSha256']])
        with self.assertRaisesRegex(ValueError, 'reuse'): driver.dump_parts(remote, 20)
        for path in ('/sdcard/old.xml', remote + '; input tap 1 1', remote.replace('-1.xml', '-0.xml'),
                     '/sdcard/../data/local/tmp/x.xml'):
            with self.subTest(path=path), self.assertRaises(ValueError): driver.dump_parts(path, 20)
        for value in (None, True, 0, -1, float('nan'), float('inf')):
            with self.subTest(value=value), self.assertRaises(ValueError):
                driver.dump_parts(remote.replace('-1.xml', '-2.xml'), value)
        with self.assertRaises(TimeoutError): driver.dump_parts(remote.replace('-1.xml', '-2.xml'), .0009)
        self.assertEqual(driver.dump_parts(remote.replace('-1.xml', '-3.xml'), 120)[6], '90000')

    def test_receipt_mutations_cannot_substitute_source_run_device_or_commands(self):
        baseline = self.prepare().evidence
        mutations = [
            lambda e: e.update(schema=True),
            lambda e: e['commands'][0].update(exitCode=False),
            lambda e: e['commands'][6]['stdout'].update(sha256='f' * 64),
            lambda e: e.update(sourceCommit='0' * 40),
            lambda e: e.update(sourceTree='0' * 40),
            lambda e: e['inputs'].update({DRIVER.JAVA_SOURCE: '0' * 64}),
            lambda e: e.update(runAttempt='7'),
            lambda e: e['device'].update(api='34'),
            lambda e: e['device'].update(viewportMode='getSize'),
            lambda e: e['device'].update(globalIdleWait=True),
            lambda e: e['device'].update(uid='0'),
            lambda e: e['installedJar'].update(remotePath='/data/local/tmp/old.jar'),
            lambda e: e['installedJar'].update(readbackBase64=base64.b64encode(b'changed').decode()),
            lambda e: e['build'].update(jarSha256='0' * 64),
            lambda e: e['toolchain'].update(platform='android-35'),
            lambda e: e['commands'][6]['command'].__setitem__(-1, '/tmp/other.java'),
            lambda e: e['commands'][10]['command'].__setitem__(-1, '/data/local/tmp/old.jar'),
            lambda e: e['commands'][10]['stdout'].update(bytes=0),
            lambda e: e['commands'][9].update(exitCode=1),
            lambda e: e['commands'][6].update(startedAtUnixNs=e['completedAtUnixNs'] + 1),
            lambda e: e['commands'].append(copy.deepcopy(e['commands'][-1])),
        ]
        for number, mutation in enumerate(mutations):
            with self.subTest(number=number):
                value = copy.deepcopy(baseline)
                mutation(value)
                with self.assertRaises((ValueError, KeyError)):
                    DRIVER.verify_evidence(value, self.source, root=self.repo)

    def test_fully_rehashed_wrong_embedded_java_is_still_rejected_by_git(self):
        value = self.prepare().evidence
        raw = base64.b64decode(value['build']['jarBase64'])
        changed = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(raw)) as original, zipfile.ZipFile(changed, 'w', compression=zipfile.ZIP_STORED) as altered:
            for name in original.namelist():
                data = original.read(name)
                if name == DRIVER.EMBEDDED_SOURCE: data += b'\n// altered source\n'
                altered.writestr(name, data)
        raw = changed.getvalue()
        digest = hashlib.sha256(raw).hexdigest()
        value['build'].update(jarBase64=base64.b64encode(raw).decode(), jarBytes=len(raw), jarSha256=digest)
        value['installedJar'].update(readbackBase64=base64.b64encode(raw).decode(), bytes=len(raw),
            readbackBytes=len(raw), sha256=digest, readbackSha256=digest)
        value['commands'][10]['stdout'] = output(raw)
        with self.assertRaisesRegex(ValueError, 'embedded Java differs'):
            DRIVER.verify_evidence(value, self.source, root=self.repo)


ANDROID_BOUNDARIES = {
    'android/app/UiAutomation.java': '''package android.app;
import android.view.accessibility.AccessibilityNodeInfo;
public class UiAutomation {
 public static int calls, readyAfter=1; public static boolean fail, late;
 public static AccessibilityNodeInfo node=new AccessibilityNodeInfo();
 public AccessibilityNodeInfo getRootInActiveWindow(){calls++; if(fail)throw new IllegalStateException("unknown root failure");
  if(late)android.os.SystemClock.now+=2000; return calls>=readyAfter?node:null;}
 public void waitForIdle(long a,long b){throw new AssertionError("Global idle wait must never execute");}
}''',
    'android/graphics/Point.java': 'package android.graphics; public class Point { public int x,y; }',
    'android/os/Build.java': 'package android.os; public class Build { public static String HARDWARE="ranchu"; public static class VERSION {public static int SDK_INT=35;} }',
    'android/os/Process.java': 'package android.os; public class Process {public static int uid=2000; public static int myUid(){return uid;}}',
    'android/os/SystemProperties.java': 'package android.os; public class SystemProperties {public static String qemu="1"; public static String get(String name){if(!name.equals("ro.kernel.qemu"))throw new AssertionError(); return qemu;}}',
    'android/os/SystemClock.java': 'package android.os; public class SystemClock {public static long now=100; public static long uptimeMillis(){return now;} public static void sleep(long delay){if(delay<0||delay>40)throw new AssertionError();now+=delay;}}',
    'android/view/Display.java': '''package android.view; import android.graphics.Point;
public class Display {public static final int DEFAULT_DISPLAY=0;public static int ordinary,real;
 public void getSize(Point p){ordinary++;p.x=320;p.y=600;}
 public void getRealSize(Point p){real++;p.x=320;p.y=640;}
 public int getRotation(){return 3;}}
''',
    'android/view/accessibility/AccessibilityNodeInfo.java': 'package android.view.accessibility; public class AccessibilityNodeInfo {public int recycled;public void recycle(){recycled++;}}',
    'android/hardware/display/DisplayManagerGlobal.java': '''package android.hardware.display;import android.view.Display;
public class DisplayManagerGlobal {public static DisplayManagerGlobal getInstance(){return new DisplayManagerGlobal();}
public Display getRealDisplay(int id){if(id!=Display.DEFAULT_DISPLAY)throw new AssertionError();return new Display();}}''',
    'com/android/uiautomator/core/UiAutomationShellWrapper.java': '''package com.android.uiautomator.core; import android.app.UiAutomation;
public class UiAutomationShellWrapper {public static int connected,disconnected;public static Boolean compressed;
public void connect(){connected++;} public void disconnect(){disconnected++;}
public void setCompressedLayoutHierarchy(boolean value){compressed=value;}
public UiAutomation getUiAutomation(){return new UiAutomation();}}''',
    'com/android/uiautomator/core/AccessibilityNodeInfoDumper.java': '''package com.android.uiautomator.core;
import android.view.accessibility.AccessibilityNodeInfo;import java.io.*;
public class AccessibilityNodeInfoDumper {public static int width,height,rotation;public static AccessibilityNodeInfo root;public static String mode="normal";
public static void dumpWindowToFile(AccessibilityNodeInfo node,File file,int r,int w,int h)throws Exception {
root=node;width=w;height=h;rotation=r;if(mode.equals("missing"))return;
try(FileOutputStream out=new FileOutputStream(file)){out.write("<hierarchy rotation=\\\"3\\\"><node content-desc=\\\"live countdown\\\" bounds=\\\"[1,2][3,4]\\\"/></hierarchy>".getBytes("UTF-8"));}
if(mode.equals("late"))android.os.SystemClock.now+=2000;}}
''',
}

HARNESS = '''package local.pocketchat.hierarchydriver;
import java.io.*;import java.nio.file.*;import java.util.zip.*;import android.app.UiAutomation;import android.os.*;
import com.android.uiautomator.core.*;
public class NativeHierarchyHost {
 static void check(boolean ok){if(!ok)throw new AssertionError();}
 public static void main(String[] args)throws Exception {
 String scenario=args[0];File file=new File(args[1]);long deadline=SystemClock.now+2000;
 if(scenario.equals("stamp")){
  try(ZipFile archive=new ZipFile(file)){NativeHierarchyCapture.verifyStamp(archive,args[2],args[3],args[4],args[5]);}
  System.out.println("OK");return;
 }
 if(scenario.equals("api32"))Build.VERSION.SDK_INT=32;
 if(scenario.equals("startup"))UiAutomation.readyAfter=3;
 if(scenario.equals("null")){UiAutomation.readyAfter=Integer.MAX_VALUE;deadline=SystemClock.now+250;}
 if(scenario.equals("unknown"))UiAutomation.fail=true;
 if(scenario.equals("late-root"))UiAutomation.late=true;
 if(scenario.equals("missing"))AccessibilityNodeInfoDumper.mode="missing";
 if(scenario.equals("late-format"))AccessibilityNodeInfoDumper.mode="late";
 if(scenario.equals("stale"))Files.write(file.toPath(),"old".getBytes("UTF-8"));
 if(scenario.startsWith("deny-")){
  if(scenario.equals("deny-uid"))android.os.Process.uid=0;
  if(scenario.equals("deny-api"))Build.VERSION.SDK_INT=34;
  if(scenario.equals("deny-qemu"))SystemProperties.qemu="0";
  if(scenario.equals("deny-hardware"))Build.HARDWARE="phone";
  try{NativeHierarchyCapture.supportedEnvironment();throw new AssertionError();}catch(IllegalArgumentException expected){}
  check(UiAutomationShellWrapper.connected==0);System.out.println("OK");return;
 }
 if(scenario.equals("unknown")||scenario.equals("late-root")||scenario.equals("missing")||scenario.equals("late-format")||scenario.equals("stale")){
  try{NativeHierarchyCapture.capture(file,deadline);throw new AssertionError();}catch(Exception expected){}
  if(scenario.equals("stale")){check(new String(Files.readAllBytes(file.toPath()),"UTF-8").equals("old"));check(UiAutomationShellWrapper.connected==0);}
  else{check(!file.exists());check(UiAutomationShellWrapper.disconnected==1);}
 }else{
  boolean captured=NativeHierarchyCapture.capture(file,deadline);
  check(UiAutomationShellWrapper.connected==1&&UiAutomationShellWrapper.disconnected==1);
  check(Boolean.FALSE.equals(UiAutomationShellWrapper.compressed));
  if(scenario.equals("null")){check(!captured&&!file.exists()&&SystemClock.now==deadline);}
  else{check(captured&&AccessibilityNodeInfoDumper.root==UiAutomation.node&&UiAutomation.node.recycled==1);
   check(AccessibilityNodeInfoDumper.rotation==3&&AccessibilityNodeInfoDumper.width==320);
   check(AccessibilityNodeInfoDumper.height==640);
   check(android.view.Display.ordinary==0);
   check(android.view.Display.real==1);
   if(scenario.equals("startup"))check(UiAutomation.calls==3&&SystemClock.now==180);
   String xml=new String(Files.readAllBytes(file.toPath()),"UTF-8");check(xml.contains("content-desc=\\\"live countdown\\\""));
  }
 }
 System.out.println("OK");
 }
}
'''


class NativeReadOnlyDriverTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.work = Path(cls.temporary.name)
        java_home = os.environ.get('JAVA_HOME')
        cls.java = str(Path(java_home)/'bin/java') if java_home else os.environ.get('PROFILE_JAVA', shutil.which('java'))
        javac = str(Path(cls.java).parent/'javac') if cls.java else None
        if not cls.java or not Path(javac).is_file():
            raise RuntimeError('Actual JDK is required for the native hierarchy host test')
        json_jar = Path(os.environ.get('PROFILE_JSON_JAR', ROOT/'work/profile-host/json.jar'))
        if not json_jar.is_file():
            raise RuntimeError('Actual host JSON jar is required for the hierarchy metadata compilation')
        cls.json_jar = json_jar
        sources = []
        for name, raw in ANDROID_BOUNDARIES.items():
            path = cls.work/'source'/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(raw)
            sources.append(path)
        harness = cls.work/'source/local/pocketchat/hierarchydriver/NativeHierarchyHost.java'
        harness.parent.mkdir(parents=True, exist_ok=True)
        harness.write_text(HARNESS)
        cls.classes = cls.work/'classes'
        command = [javac, '-encoding', 'UTF-8', '-classpath', str(json_jar), '-d', str(cls.classes),
                   *map(str, sources), str(harness), str(ROOT/DRIVER.JAVA_SOURCE)]
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
        if result.returncode:
            raise AssertionError(result.stderr.decode())

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def scenario(self, name):
        path = self.work/(name + '.xml')
        result = subprocess.run([self.java, '-classpath', str(self.classes) + os.pathsep + str(self.json_jar),
            'local.pocketchat.hierarchydriver.NativeHierarchyHost', name, str(path)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual(result.stdout, b'OK\n')

    def test_real_driver_reads_dynamic_root_through_the_original_formatter(self):
        self.scenario('dynamic')

    def test_api32_formatter_receives_real_screen_size(self):
        self.scenario('api32')

    def test_compiled_api32_app_size_mutant_cannot_clip_screen_coordinates(self):
        original = (ROOT/DRIVER.JAVA_SOURCE).read_text()
        self.assertEqual(original.count('display.getRealSize(size);'), 1)
        changed = original.replace('display.getRealSize(size);',
            'if (api == 32) display.getSize(size); else display.getRealSize(size);')
        source = self.work/'app-size-mutant/NativeHierarchyCapture.java'
        source.parent.mkdir()
        source.write_text(changed)
        classes = self.work/'app-size-mutant-classes'
        classpath = str(self.classes) + os.pathsep + str(self.json_jar)
        result = subprocess.run([str(Path(self.java).parent/'javac'), '-encoding', 'UTF-8',
            '-classpath', classpath, '-d', str(classes), str(source)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        # Run the same actual capture/formatter path and API 32 assertion with
        # app size 320x600 versus screen size 320x640. Only the mutant changes.
        result = subprocess.run([self.java, '-classpath', str(classes) + os.pathsep + classpath,
            'local.pocketchat.hierarchydriver.NativeHierarchyHost', 'api32', str(self.work/'mutant-api32.xml')],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b'AssertionError', result.stderr)
        self.assertEqual(result.stdout, b'')

    def test_null_root_polls_only_within_original_remainder(self):
        self.scenario('null')

    def test_bridge_startup_polls_without_global_idle(self):
        self.scenario('startup')

    def test_unknown_read_failure_remains_fatal(self):
        self.scenario('unknown')

    def test_late_root_and_formatter_cannot_produce_success(self):
        self.scenario('late-root')
        self.scenario('late-format')

    def test_formatter_failure_cannot_acknowledge_missing_xml(self):
        self.scenario('missing')

    def test_prior_xml_is_not_overwritten_or_reused(self):
        self.scenario('stale')

    def test_native_execution_rejects_wrong_uid_api_and_physical_device(self):
        for name in ('deny-uid', 'deny-api', 'deny-qemu', 'deny-hardware'):
            with self.subTest(name=name): self.scenario(name)

    def test_actual_native_stamp_reader_binds_source_run_and_embedded_java(self):
        source, tree = 'a' * 40, 'b' * 40
        java = (ROOT/DRIVER.JAVA_SOURCE).read_bytes()
        stamp = dict(schema=1, entryPoint=DRIVER.ENTRY_POINT, executionUid=2000, readOnly=True,
            sourceCommit=source, sourceTree=tree, runId='1234', runAttempt='2',
            inputs={DRIVER.JAVA_SOURCE: hashlib.sha256(java).hexdigest()})
        variants = [('valid', stamp, java, source, tree, '1234', '2', False),
                    ('source', stamp, java, 'c' * 40, tree, '1234', '2', False),
                    ('tree', stamp, java, source, 'c' * 40, '1234', '2', False),
                    ('run', stamp, java, source, tree, '1235', '2', False),
                    ('attempt', stamp, java, source, tree, '1234', '3', False),
                    ('java', stamp, java + b'changed', source, tree, '1234', '2', False),
                    ('extra', stamp, java, source, tree, '1234', '2', True),
                    ('scope', dict(stamp, readOnly=False), java, source, tree, '1234', '2', False)]
        for name, metadata, embedded, expected_source, expected_tree, run, attempt, extra in variants:
            with self.subTest(name=name):
                path = self.work/('native-stamp-' + name + '.jar')
                with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_STORED) as archive:
                    archive.writestr('classes.dex', b'dex\n035\0boundary')
                    archive.writestr(DRIVER.STAMP, json.dumps(metadata).encode())
                    archive.writestr(DRIVER.EMBEDDED_SOURCE, embedded)
                    if extra: archive.writestr('other.dex', b'not allowed')
                result = subprocess.run([self.java, '-classpath', str(self.classes) + os.pathsep + str(self.json_jar),
                    'local.pocketchat.hierarchydriver.NativeHierarchyHost', 'stamp', str(path),
                    expected_source, expected_tree, run, attempt], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
                if name == 'valid':
                    self.assertEqual(result.returncode, 0, result.stderr.decode())
                    self.assertEqual(result.stdout, b'OK\n')
                else:
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(result.stdout, b'')


if __name__ == '__main__':
    unittest.main(verbosity=2)
