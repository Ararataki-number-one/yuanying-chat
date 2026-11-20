"""Current native-observer proof and actual short-input controls on the host.

The Git repository, committed Java/Python bytes and ZIP/readback verifier are
real. Android, DEX execution, compiler outputs and device transport below are
explicitly controlled host fixtures, never original Android acceptance data.
"""
import ast
from collections import Counter
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'tools/gecko'), str(ROOT/'tests/gecko')]
import chrome_collapse_contract_v2 as previous
import chrome_collapse_contract_v3 as current
import run_chrome_collapse_v3 as runner
import ui_hierarchy_driver as driver
import profile_chrome_short_target_test as old_fixture
import chrome_collapse_contract_v4 as v4
import run_chrome_collapse_v4 as v4_runner


def output(raw):
    return dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(),
                text=raw[:8192].decode('utf-8', 'replace'), truncated=len(raw) > 8192)


def controlled_evidence(directory, source, tree):
    """Create declared host-only observations, with actual source and ZIP bytes."""
    directory = Path(directory)
    nonce, run, attempt = '4'*32, '271828', '3'
    compiler_paths = {key: '/host-only/compiler/'+key for key in ('java', 'javac', 'jar', 'androidJar', 'd8')}
    compiler = dict(javaVersion='openjdk version "17.0.0" controlled-host-only',
        platform='android-37.1', buildTools='37.0.0', tools={key: dict(path=value,
        bytes=len(key), sha256=hashlib.sha256(key.encode()).hexdigest()) for key, value in compiler_paths.items()})
    inputs = {path: hashlib.sha256((directory/path).read_bytes()).hexdigest()
              for path in (driver.JAVA_SOURCE, driver.PYTHON_SOURCE)}
    selected = dict(sourceCommit=source, sourceTree=tree, runId=run, runAttempt=attempt, inputs=inputs)
    stamp = dict(schema=1, **selected, backend=driver.BACKEND, entryPoint=driver.ENTRY_POINT,
        executionUid=2000, readOnly=True, toolchain=compiler, supportedApis=[32, 35],
        viewportModes={'32': 'getRealSize', '35': 'getRealSize'}, compressedHierarchy=False,
        globalIdleWait=False, rootPollLimitMillis=1000)
    build_dir = directory/'host-only-compile'
    build_dir.mkdir()
    dex = build_dir/'controlled.dex'
    dex.write_bytes(b'dex\n035\0DECLARED HOST FIXTURE; NOT AN EXECUTABLE ANDROID DEX')
    jar = build_dir/'hierarchy-driver.jar'
    stamp_hash = driver.package_driver(jar, dex, directory/driver.JAVA_SOURCE, stamp)
    raw = jar.read_bytes()
    import base64
    encoded = base64.b64encode(raw).decode('ascii')
    digest = hashlib.sha256(raw).hexdigest()
    remote = '/data/local/tmp/pocketchat-ui-hierarchy-'+source[:12]+'-'+run+'-'+attempt+'-'+nonce+'.jar'
    serial, adb = 'emulator-9998', '/host-only/adb'
    device = dict(uid='2000', api='35', qemu='1', hardware='ranchu',
        fingerprint='host-only/controlled:35/test/fixture:userdebug/test-keys',
        systemJar=driver.SYSTEM_JAR, systemJarSha256=hashlib.sha256(b'controlled system jar').hexdigest(),
        viewportMode='getRealSize', compressedHierarchy=False, globalIdleWait=False)
    commands = []
    def command(parts, timeout, stdout=b'', stderr=b''):
        start = 1000+1000*len(commands)
        commands.append(dict(command=parts, timeoutSeconds=timeout, exitCode=0,
            startedAtUnixNs=start, completedAtUnixNs=start+500,
            stdout=output(stdout), stderr=output(stderr)))
    for parts, value in ((['id', '-u'], device['uid']),
            (['getprop', 'ro.build.version.sdk'], device['api']),
            (['getprop', 'ro.kernel.qemu'], device['qemu']),
            (['getprop', 'ro.hardware'], device['hardware']),
            (['getprop', 'ro.build.fingerprint'], device['fingerprint']),
            (['sha256sum', driver.SYSTEM_JAR], device['systemJarSha256']+'  '+driver.SYSTEM_JAR)):
        command([adb, '-s', serial, 'shell', *parts], 15, (value+'\n').encode())
    command([compiler_paths['javac'], '-encoding', 'UTF-8', '-source', '8', '-target', '8',
             '-classpath', compiler_paths['androidJar'], '-d', str(build_dir/'classes'),
             str(directory/driver.JAVA_SOURCE)], 60)
    command([compiler_paths['jar'], 'cf', str(build_dir/'classes.jar'), '-C', str(build_dir/'classes'), '.'], 30)
    command([compiler_paths['java'], '-cp', compiler_paths['d8'], 'com.android.tools.r8.D8',
             '--lib', compiler_paths['androidJar'], '--min-api', '32', '--output', str(build_dir/'dex'),
             str(build_dir/'classes.jar')], 60)
    command([adb, '-s', serial, 'push', str(jar), remote], 30, b'controlled host-only push\n')
    command([adb, '-s', serial, 'exec-out', 'cat', remote], 30, raw)
    return dict(schema=1, status='verified', backend=driver.BACKEND, readOnly=True,
        executionUid=2000, entryPoint=driver.ENTRY_POINT, preparationNonce=nonce,
        actualAndroidExecution=False, releaseAcceptance=False,
        scope='Declared host-only transport/compiler/DEX fixture; no Android execution.',
        startedAtUnixNs=500, completedAtUnixNs=12000, commands=commands, **selected,
        serial=serial, device=device, toolchain=compiler,
        build=dict(jarPath=str(jar), jarBytes=len(raw), jarSha256=digest,
                   dexSha256=hashlib.sha256(dex.read_bytes()).hexdigest(), stampSha256=stamp_hash,
                   jarBase64=encoded),
        installedJar=dict(remotePath=remote, bytes=len(raw), sha256=digest,
                          readbackBytes=len(raw), readbackSha256=digest, readbackBase64=encoded))


class CurrentNativeShortTargetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix='current-native-short-git-')
        cls.repository = Path(cls.temporary.name)
        for path in (driver.JAVA_SOURCE, driver.PYTHON_SOURCE):
            target = cls.repository/path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT/path).read_bytes())
        env = dict(os.environ, GIT_NO_LAZY_FETCH='1', GIT_OPTIONAL_LOCKS='0')
        def git(*parts):
            return subprocess.check_output(['git', *parts], cwd=cls.repository, env=env,
                                           stderr=subprocess.PIPE).decode().strip()
        git('init', '-q')
        git('add', driver.JAVA_SOURCE, driver.PYTHON_SOURCE)
        git('-c', 'user.name=Host source control', '-c', 'user.email=host-control@invalid.example',
            'commit', '-q', '-m', 'Actual driver sources for declared host-only proof controls')
        cls.source, cls.tree = git('rev-parse', 'HEAD'), git('rev-parse', 'HEAD^{tree}')
        cls.evidence = controlled_evidence(cls.repository, cls.source, cls.tree)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def setUp(self):
        self.addCleanup(mock.patch.stopall)
        mock.patch.object(current, 'ROOT', self.repository).start()

    def identity(self):
        return dict(sourceCommit=self.source, sourceTree=self.tree, apkSha256='c'*64)

    def capture_record(self, xml=None, evidence=None):
        value = old_fixture.capture_record(old_fixture.host_xml() if xml is None else xml)
        selected = copy.deepcopy(self.evidence if evidence is None else evidence)
        observer = driver.HierarchyDriver(selected, self.repository/'unused-host-only-receipt.json')
        value['commands'][0]['parts'] = observer.dump_parts(value['remotePath'], 18.9)
        return value

    def proof(self, *, xml=None, evidence=None, record=None):
        xml = old_fixture.host_xml() if xml is None else xml
        evidence = copy.deepcopy(self.evidence if evidence is None else evidence)
        return current.make_short_target_proof(raw_xml=xml, activity_state=old_fixture.activity(),
            identity=self.identity(), nonce='d'*32, android_user=0, before=old_fixture.before(),
            capture_nonce='e'*32, capture_record=self.capture_record(xml, evidence) if record is None else record,
            acquisition_driver=evidence, action_started_ns=100_000_000_000,
            activity_started_ns=105_000_000_000, activity_completed_ns=106_000_000_000,
            prepared_ns=107_000_000_000)

    def verify(self, proof):
        return current.verify_short_target(proof, identity=self.identity(), nonce='d'*32,
                                           android_user=0, before=old_fixture.before())

    def reject(self, value):
        with self.assertRaises((AssertionError, ValueError, KeyError, TypeError, subprocess.CalledProcessError)):
            self.verify(value)

    def test_actual_git_archive_reader_and_original_commands_are_used_without_projection(self):
        record = self.capture_record()
        original = copy.deepcopy(record)
        with mock.patch.object(driver, 'verify_evidence', wraps=driver.verify_evidence) as verify:
            proof = self.proof(record=record)
            geometry = self.verify(proof)
        self.assertEqual(verify.call_count, 2)
        self.assertEqual(record, original)
        self.assertEqual(proof['captureRecord'], original)
        self.assertEqual(proof['acquisitionDriver'], self.evidence)
        self.assertEqual(proof['schema'], 2)
        self.assertEqual(proof['captureRecord']['commands'][0]['parts'][2], 'app_process')
        self.assertEqual(geometry['from'], [540,684])
        self.assertEqual(geometry['to'], [540,672])
        self.assertEqual((geometry['durationMs'], proof['preparationBudgetMs'], proof['originalActionBudgetMs']), (320,20000,90000))
        self.assertFalse(proof['applicationAcceptance'])
        self.assertFalse(proof['acquisitionDriver']['actualAndroidExecution'])
        with self.assertRaises(AssertionError):
            previous.make_short_target_proof(raw_xml=proof['rawXml'], activity_state=proof['activityState'],
                identity=self.identity(), nonce='d'*32, android_user=0, before=old_fixture.before(),
                capture_nonce='e'*32, capture_record=original, action_started_ns=100_000_000_000,
                activity_started_ns=105_000_000_000, activity_completed_ns=106_000_000_000,
                prepared_ns=107_000_000_000)

    def test_native_proof_keeps_every_old_assertion_except_the_explicit_command_protocol(self):
        def function(path, name):
            return next(node for node in ast.parse(path.read_bytes()).body
                        if isinstance(node, ast.FunctionDef) and node.name == name)
        old = function(ROOT/'tools/gecko/chrome_collapse_contract_v2.py', 'make_short_target_proof')
        new = function(ROOT/'tools/gecko/chrome_collapse_contract_v3.py', 'make_short_target_proof')
        old_asserts = Counter(ast.dump(node.test, include_attributes=False) for node in ast.walk(old) if isinstance(node, ast.Assert))
        command = ast.parse("command['parts'] == (['shell', 'uiautomator', 'dump', remote] if index == 0 else ['shell', 'cat', remote])", mode='eval').body
        key = ast.dump(command, include_attributes=False)
        self.assertEqual(old_asserts.pop(key), 1)
        new_asserts = Counter(ast.dump(node.test, include_attributes=False) for node in ast.walk(new) if isinstance(node, ast.Assert))
        self.assertFalse(old_asserts-new_asserts)
        self.assertEqual(previous.make_short_target_proof.__module__, 'chrome_collapse_contract_v2')
        self.assertEqual(current.make_short_target_proof.__module__, 'chrome_collapse_contract_v3')

    def test_each_native_command_argument_and_command_order_is_bound(self):
        original = self.proof()
        for index in range(13):
            value = copy.deepcopy(original)
            value['captureRecord']['commands'][0]['parts'][index] += '-counterfeit'
            with self.subTest(argument=index): self.reject(value)
        for mutation in ('legacy-command', 'extra-argument', 'extra-command', 'reverse', 'cat-other-path', 'input-command'):
            value = copy.deepcopy(original); commands = value['captureRecord']['commands']
            if mutation == 'legacy-command': commands[0]['parts'] = ['shell','uiautomator','dump',value['captureRecord']['remotePath']]
            if mutation == 'extra-argument': commands[0]['parts'].append('extra')
            if mutation == 'extra-command': commands.append(copy.deepcopy(commands[-1]))
            if mutation == 'reverse': commands.reverse()
            if mutation == 'cat-other-path': commands[1]['parts'][-1] += '.old'
            if mutation == 'input-command': commands[0]['parts'] = ['shell','input','keyevent','KEYCODE_BACK']
            with self.subTest(mutation=mutation): self.reject(value)

    def test_native_budget_cannot_extend_or_replace_the_original_absolute_deadline(self):
        original = self.proof()
        for amount in ('0', '-1', 'NaN', '18.9', '018900', '20001', '90000', '18903'):
            value = copy.deepcopy(original); value['captureRecord']['commands'][0]['parts'][6] = amount
            with self.subTest(milliseconds=amount): self.reject(value)
        changes = [lambda p:p.update(actionStartedAtMonotonicNanos=102_000_000_000),
            lambda p:p.update(activityStartedAtMonotonicNanos=103_000_000_000),
            lambda p:p.update(activityCompletedAtMonotonicNanos=104_000_000_000),
            lambda p:p.update(preparedAtMonotonicNanos=120_000_000_000),
            lambda p:p['captureRecord'].update(existingSceneDeadline=121.0),
            lambda p:p['captureRecord']['commands'][0].update(timeoutSeconds=90),
            lambda p:p['captureRecord']['commands'][1].update(startedAtMonotonicNanos=102_000_000_000),
            lambda p:p['captureRecord'].update(completedAtMonotonicNanos=106_000_000_000)]
        for index, change in enumerate(changes):
            value = copy.deepcopy(original); change(value)
            with self.subTest(order=index): self.reject(value)

    def test_driver_source_tree_run_attempt_and_embedded_source_are_reverified(self):
        original = self.proof()
        changes = [lambda e:e.update(sourceCommit='f'*40), lambda e:e.update(sourceTree='f'*40),
            lambda e:e.update(runId='314159'), lambda e:e.update(runAttempt='4'),
            lambda e:e['inputs'].update({driver.JAVA_SOURCE:'f'*64}),
            lambda e:e['inputs'].update({driver.PYTHON_SOURCE:'f'*64}),
            lambda e:e.update(status='failed'), lambda e:e.update(readOnly=False),
            lambda e:e.update(executionUid=0), lambda e:e.update(actualAndroidExecution=True),
            lambda e:e.update(releaseAcceptance=True), lambda e:e['device'].update(globalIdleWait=True),
            lambda e:e['device'].update(compressedHierarchy=True), lambda e:e['device'].update(viewportMode='getSize'),
            lambda e:e['build'].update(jarSha256='f'*64), lambda e:e['build'].update(stampSha256='f'*64),
            lambda e:e['build'].update(dexSha256='f'*64), lambda e:e['installedJar'].update(readbackSha256='f'*64),
            lambda e:e['installedJar'].update(readbackBase64='ZGlmZmVyZW50'),
            lambda e:e['commands'].pop(), lambda e:e['commands'][10]['stdout'].update(text='fake readback')]
        for index, change in enumerate(changes):
            value = copy.deepcopy(original); change(value['acquisitionDriver'])
            with self.subTest(driver=index): self.reject(value)

    def test_missing_actual_git_objects_cannot_be_replaced_by_claimed_hashes(self):
        original = self.proof()
        with tempfile.TemporaryDirectory() as empty, mock.patch.object(current, 'ROOT', Path(empty)):
            self.reject(original)
        with mock.patch.dict(os.environ, {'GITHUB_RUN_ID':'999999', 'GITHUB_RUN_ATTEMPT':'9'}):
            self.assertEqual(self.verify(original)['from'], [540,684])

    def test_original_xml_activity_metadata_and_computed_target_cannot_be_forged(self):
        original = self.proof()
        changes = [lambda p:p.update(sourceCommit='f'*40), lambda p:p.update(sourceTree='f'*40),
            lambda p:p.update(apkSha256='f'*64), lambda p:p.update(runNonce='f'*32),
            lambda p:p.update(androidUser=10), lambda p:p.update(beforeSnapshotSha256='f'*64),
            lambda p:p.update(xmlSha256='f'*64), lambda p:p.update(xmlBytes=p['xmlBytes']+1),
            lambda p:p.update(activitySha256='f'*64), lambda p:p.update(activityBytes=p['activityBytes']+1),
            lambda p:p['geometry'].update({'from':[540,955]}), lambda p:p['geometry'].update(excludedBounds=[]),
            lambda p:p['geometry'].update(durationMs=640), lambda p:p.update(phase='compactExpand'),
            lambda p:p.update(schema=True), lambda p:p.update(schema=1),
            lambda p:p['geometry'].update(targetContract=True), lambda p:p.update(preEmitOnly=False),
            lambda p:p.update(applicationAcceptance=True), lambda p:p.update(extra='unreviewed'),
            lambda p:p.update(originalActionBudgetMs=90001), lambda p:p.update(preparationBudgetMs=20001),
            lambda p:p.update(captureRunNonce='f'*32), lambda p:p['captureRecord'].update(index=8),
            lambda p:p['captureRecord'].update(status='not-ready'), lambda p:p['captureRecord'].update(xmlSha256='f'*64),
            lambda p:p['captureRecord']['commands'][0].update(exitCode=1),
            lambda p:p['captureRecord']['commands'][1]['stdout'].update(text='counterfeit XML'),
            lambda p:p['captureRecord']['commands'][1]['stdout'].update(truncated=True),
            lambda p:p['captureRecord']['commands'][1].update(stderr=output(b'failure')),
            lambda p:p.update(activityState='mLastPausedActivity=ActivityRecord{abc u0 '+current.ACTIVITY+' t8}\n'),
            lambda p:p.update(activityState=old_fixture.activity().replace('u0','u1')),
            lambda p:p.update(activityState=old_fixture.activity().replace(current.ACTIVITY,current.ENVIRONMENT_ACTIVITY))]
        for index, change in enumerate(changes):
            value = copy.deepcopy(original); change(value)
            with self.subTest(observation=index): self.reject(value)

    def test_driver_does_not_relax_native_ownership_or_editable_safe_geometry(self):
        for xml in (old_fixture.host_xml().replace('package="local.pocketchat.test"','package="foreign.test"'),
                    old_fixture.host_xml().replace('[24,881][971,1115]','[24,477][971,1194]')):
            with self.subTest(xml=hashlib.sha256(xml.encode()).hexdigest()), self.assertRaises(AssertionError):
                self.proof(xml=xml)

    def invoke(self, failure=None):
        commands, reads, diagnostic = [], [], {}
        xml = old_fixture.host_xml()
        with tempfile.TemporaryDirectory() as directory:
            capture = types.SimpleNamespace(nonce='e'*32, count=7, diagnostics=Path(directory)/'capture.json',
                                            report={'acquisitionDriver':copy.deepcopy(self.evidence)})
            def read(*, deadline):
                reads.append(deadline)
                if failure == 'capture': raise OSError('controlled capture failure')
                raw = xml.replace('package="local.pocketchat.test"','package="foreign.test"') if failure == 'xml' else xml
                value = dict(schema=1, sourceCommit=self.source, runNonce=capture.nonce,
                             attemptCount=7, attempts=[self.capture_record(raw)],
                             acquisitionDriver=copy.deepcopy(capture.report['acquisitionDriver']))
                if failure == 'identity': value['sourceCommit'] = 'f'*40
                if failure == 'capture-nonce': value['runNonce'] = 'f'*32
                if failure == 'index': value['attemptCount'] = 8
                if failure == 'saved-driver': value['acquisitionDriver']['runAttempt'] = '4'
                if failure == 'missing-driver': value.pop('acquisitionDriver')
                if failure == 'active-driver':
                    value['acquisitionDriver']['inputs'][driver.JAVA_SOURCE] = 'f'*64
                    capture.report['acquisitionDriver'] = copy.deepcopy(value['acquisitionDriver'])
                capture.diagnostics.write_text(json.dumps(value)+'\n')
                return raw
            capture.read = read
            def command(parts, **kwargs):
                commands.append((parts,kwargs))
                if parts[3:] == ['shell','dumpsys','activity','activities']:
                    if failure == 'activity': raise subprocess.CalledProcessError(1,parts,output=b'controlled failure')
                    return (old_fixture.activity().replace('u0','u1') if failure == 'owner' else old_fixture.activity()).encode()
                self.assertEqual(parts[3:6], ['shell','input','swipe'])
                if failure == 'input': raise subprocess.TimeoutExpired(parts,kwargs['timeout'])
                return b''
            times = iter([121.0] if failure == 'deadline' else [104.5,107.0,107.25,191.0 if failure == 'late-input' else 107.6])
            nanos = iter([100_000_000_000,105_000_000_000,106_000_000_000,
                          121_000_000_000 if failure == 'prepared' else 107_000_000_000,
                          107_300_000_000,191_000_000_000 if failure == 'late-input' else 107_600_000_000])
            clock = types.SimpleNamespace(monotonic=lambda:next(times), monotonic_ns=lambda:next(nanos))
            result, error = None, None
            # Only the runner's transport is controlled. The source verifier
            # still invokes real Git and decodes the original ZIP/readback.
            with mock.patch.object(runner, 'time', clock), \
                 mock.patch.object(runner, 'subprocess', types.SimpleNamespace(check_output=command)):
                try:
                    result = runner.short_swipe_once(capture=capture, prefix=['host-only-adb','-s','host-only-serial'],
                        identity=self.identity(), nonce='d'*32, android_user=0, before=old_fixture.before(), diagnostic=diagnostic)
                except (AssertionError, ValueError, KeyError, OSError, TimeoutError,
                        subprocess.CalledProcessError, subprocess.TimeoutExpired) as caught:
                    error = caught
            return result, error, reads, commands, diagnostic

    def test_actual_current_runner_passes_the_original_native_receipt_before_one_swipe(self):
        result, error, reads, commands, diagnostic = self.invoke()
        self.assertIsNone(error)
        geometry, proof = result
        self.assertEqual(reads, [120.0])
        self.assertEqual(len(commands), 2)
        self.assertEqual(commands[0][0][3:], ['shell','dumpsys','activity','activities'])
        self.assertEqual(commands[0][1]['timeout'], 15.5)
        self.assertEqual(commands[1][0][3:], ['shell','input','swipe','540','684','540','672','320'])
        self.assertEqual(commands[1][1]['timeout'], 82.75)
        self.assertEqual(self.verify(proof), geometry)
        self.assertEqual(diagnostic['targetProof'], proof)
        self.assertEqual(diagnostic['inputInvocations'], 1)
        self.assertEqual(diagnostic['status'], 'input-command-returned')
        self.assertFalse(diagnostic['releaseAcceptance'])

    def test_actual_runner_preparation_failures_never_send_and_input_failure_is_not_retried(self):
        for failure in ('capture','identity','capture-nonce','index','xml','deadline','prepared','activity',
                        'owner','saved-driver','missing-driver','active-driver','input','late-input'):
            with self.subTest(failure=failure):
                result, error, reads, commands, diagnostic = self.invoke(failure)
                self.assertIsNone(result)
                self.assertIsNotNone(error)
                self.assertEqual(reads, [120.0])
                inputs = [row for row in commands if row[0][3:6] == ['shell','input','swipe']]
                self.assertEqual(len(inputs), 1 if failure in ('input','late-input') else 0)
                self.assertLessEqual(len(commands), 2)
                self.assertFalse(diagnostic['releaseAcceptance'])
                if failure == 'input':
                    self.assertEqual(diagnostic['inputInvocations'], 1)
                    self.assertEqual(diagnostic['status'], 'input-command-failed')
                    self.assertEqual(diagnostic['deliveryStatus'], 'not-established')


def v4_owner(activity_token='abc', pid=4321, process_token='def', window_token='123'):
    """Declared host-only dumpsys shape, not an observed Android instance."""
    activity = 'ActivityRecord{'+activity_token+' u0 '+v4.ACTIVITY+' t8}'
    window = 'Window{'+window_token+' u0 '+v4.ACTIVITY+'}'
    return ('ACTIVITY MANAGER ACTIVITIES (dumpsys activity activities)\n'
        'Display #0 (activities from top to bottom):\n'
        '    topResumedActivity='+activity+'\n'
        '    * Hist  #0: '+activity+'\n'
        '      app=ProcessRecord{'+process_token+' '+str(pid)+':'+v4.PACKAGE+'/u0a209}\n'
        '      windows=['+window+']\n'
        '  ResumedActivity: '+activity+'\n'
        '  mCurrentFocus='+window+'\n'
        '  mFocusedApp='+activity+'\n')


def v4_short_before():
    return dict(command='horizontal', expanded=True, keyboard=False, windowFocus=True,
        page=0, addressDialog={'showing': False}, webX=0, webY=361, webWidth=1080, webHeight=1301,
        toolbarBounds=[0,72,1080,361], browserToolbarBounds=[0,1662,1080,1848],
        environmentName='Host controlled environment')


def v4_short_xml(*, pending=False, placeholder=False):
    """Synthetic native chrome with the observed accessibility readiness shapes."""
    tree = ET.Element('hierarchy', rotation='0')
    def node(parent, kind, box, **extra):
        attrs = {'class':kind, 'package':v4.PACKAGE, 'enabled':'true',
            'clickable':'false', 'long-clickable':'false', 'focusable':'false', 'checkable':'false',
            'bounds':f'[{box[0]},{box[1]}][{box[2]},{box[3]}]'}
        attrs.update(extra)
        return ET.SubElement(parent, 'node', attrs)
    owner = tree
    for resource in ('', '', 'android:id/content'):
        owner = node(owner, 'android.widget.FrameLayout', [0,0,1080,1920], **{'resource-id':resource})
    main = node(owner, 'android.widget.LinearLayout', [0,0,1080,1920])
    header = node(main, 'android.widget.LinearLayout', [0,72,1080,361])
    node(header, 'android.widget.Button', [252,78,828,186], text='Host controlled environment',
        **{'content-desc':'当前环境：Host controlled environment，点按切换环境','clickable':'true'})
    node(header, 'android.widget.Button', [48,216,1032,360],
        **{'content-desc':'当前环境网络：Host controlled status','clickable':'true'})
    outer = node(main, 'android.widget.FrameLayout', [0,361,1080,1662])
    inner = node(outer, 'android.widget.FrameLayout', [0,361,1080,1662])
    if placeholder:
        node(inner, 'android.webkit.WebView', [0,0,0,0], enabled='false', index='0', text='',
            **{'resource-id':'', 'content-desc':'', 'checked':'false', 'focused':'false',
               'scrollable':'false', 'password':'false', 'selected':'false'})
    elif not pending:
        web = node(inner, 'android.webkit.WebView', [0,361,1080,1662], focusable='true')
        node(web, 'android.widget.EditText', [24,1150,971,1580], clickable='true', focusable='true')
    footer = node(main, 'android.widget.FrameLayout', [0,1662,1080,1848])
    row = node(footer, 'android.view.ViewGroup', [0,1662,1080,1848])
    for description, box in zip(('打开当前环境主页','网页窗口',
            '当前网址 https://chatgpt.com/c/reload-collapse，点击输入网址或搜索','网页工具','浏览器菜单'),
            ([12,1680,156,1824],[156,1680,300,1824],[312,1680,768,1824],
             [780,1680,924,1824],[924,1680,1068,1824])):
        node(row, 'android.widget.Button', box, **{'content-desc':description,'clickable':'true','focusable':'true'})
    return ET.tostring(tree, encoding='unicode')


class CurrentV4ShortReadinessTests(unittest.TestCase):
    """Run actual v4 readers/loop against explicit host-only transport and clock."""
    setUpClass = classmethod(CurrentNativeShortTargetTests.setUpClass.__func__)
    tearDownClass = classmethod(CurrentNativeShortTargetTests.tearDownClass.__func__)
    identity = CurrentNativeShortTargetTests.identity

    def setUp(self):
        self.addCleanup(mock.patch.stopall)
        mock.patch.object(v4, 'ROOT', self.repository).start()
        mock.patch.object(current, 'ROOT', self.repository).start()

    def invoke(self, frames=None, *, failure=None, owners=None, parsed_late=False, target_late=False):
        frames = [v4_short_xml(pending=True), v4_short_xml()] if frames is None else frames
        clock = types.SimpleNamespace(ns=100_000_000_000)
        clock.monotonic = lambda:clock.ns/1e9
        clock.monotonic_ns = lambda:clock.ns
        clock.sleep = lambda seconds:setattr(clock, 'ns', clock.ns+int(seconds*1e9))
        reads, commands, diagnostic = [], [], {}
        with tempfile.TemporaryDirectory() as directory:
            capture = types.SimpleNamespace(nonce='e'*32, count=0, diagnostics=Path(directory)/'capture.json',
                report={'acquisitionDriver':copy.deepcopy(self.evidence)})
            records = []
            def read(*, deadline):
                reads.append(deadline)
                if failure == 'capture': raise OSError('declared host-only capture failure')
                xml = frames[min(len(reads)-1,len(frames)-1)]
                capture.count += 1
                remote = '/sdcard/pocketchat-ui-visual-'+capture.nonce+'-'+str(capture.count)+'.xml'
                start = clock.ns; clock.ns += 50_000_000
                observer = driver.HierarchyDriver(copy.deepcopy(self.evidence), self.repository/'unused.json')
                def command(parts, raw, first, last):
                    return dict(parts=parts, startedAtMonotonicNanos=first, completedAtMonotonicNanos=last,
                        startedAtWallTimeMillis=first//1_000_000, completedAtWallTimeMillis=last//1_000_000,
                        timeoutSeconds=deadline-first/1e9, exitCode=0, stdout=output(raw), stderr=output(b''))
                parts = observer.dump_parts(remote, deadline-clock.monotonic())
                first = command(parts, ('UI hierchary dumped to: '+remote+'\n').encode(),clock.ns,clock.ns+50_000_000)
                clock.ns += 60_000_000
                last = command(['shell','cat',remote], xml.encode(),clock.ns,clock.ns+50_000_000)
                clock.ns += 60_000_000
                row = dict(index=capture.count, remotePath=remote, commands=[first,last],
                    startedAtMonotonicNanos=start, completedAtMonotonicNanos=clock.ns,
                    existingSceneDeadline=deadline,status='captured',xmlBytes=len(xml.encode()),
                    xmlSha256=hashlib.sha256(xml.encode()).hexdigest())
                if failure == 'raw-hash': row['xmlSha256'] = 'f'*64
                if failure == 'command-path': row['commands'][1]['parts'][-1] += '-old'
                if failure == 'command-output': row['commands'][0]['stderr'] = output(b'unknown actual error')
                if failure == 'same-index' and len(reads)>1:
                    capture.count -= 1; row = copy.deepcopy(records[-1])
                records.append(row)
                value = dict(schema=1,sourceCommit=self.source,runNonce=capture.nonce,
                    attemptCount=capture.count,attempts=copy.deepcopy(records),acquisitionDriver=copy.deepcopy(self.evidence))
                capture.diagnostics.write_text(json.dumps(value)+'\n')
                if failure == 'late-xml':clock.ns=120_000_000_000
                return xml
            capture.read = read
            def command(parts, **kwargs):
                commands.append((parts,kwargs))
                if parts[3:] == ['shell','dumpsys','activity','activities']:
                    if failure == 'activity': raise subprocess.TimeoutExpired(parts,kwargs['timeout'])
                    clock.ns += 50_000_000
                    if failure == 'late-activity':clock.ns=120_000_000_000
                    if failure == 'activity-utf8':return b'\xffdeclared-invalid-utf8'
                    values = [v4_owner()] if owners is None else owners
                    return values[min(len(reads)-1,len(values)-1)].encode()
                self.assertEqual(parts[3:6],['shell','input','swipe'])
                if failure == 'input':raise subprocess.TimeoutExpired(parts,kwargs['timeout'])
                clock.ns += 320_000_000
                return b''
            original_pending = v4.short_webview_pending
            def pending(*args):
                value=original_pending(*args)
                if parsed_late:clock.ns=120_000_000_000
                return value
            original_verify = v4.verify_short_target
            def verify(*args,**kwargs):
                value=original_verify(*args,**kwargs)
                if target_late:clock.ns=120_000_000_000
                return value
            result, error = None, None
            with mock.patch.object(v4_runner,'time',clock), \
                 mock.patch.object(v4_runner,'subprocess',types.SimpleNamespace(check_output=command)), \
                 mock.patch.object(v4_runner,'short_webview_pending',pending), \
                 mock.patch.object(v4_runner,'verify_short_target',verify):
                try:
                    result=v4_runner.short_swipe_once(capture=capture,prefix=['host-only-adb','-s','host-only-serial'],
                        identity=self.identity(),nonce='d'*32,android_user=0,before=v4_short_before(),
                        owner_activity=v4_owner(),diagnostic=diagnostic)
                except Exception as caught:error=caught
            return result,error,reads,commands,diagnostic

    def test_current_ready_proof_matches_every_original_schema2_value(self):
        result,error,reads,commands,diagnostic=self.invoke([v4_short_xml()])
        self.assertIsNone(error); geometry,proof=result
        old=current.make_short_target_proof(raw_xml=proof['rawXml'],activity_state=proof['activityState'],
            identity=self.identity(),nonce='d'*32,android_user=0,before=v4_short_before(),
            capture_nonce=proof['captureRunNonce'],capture_record=proof['captureRecord'],
            acquisition_driver=proof['acquisitionDriver'],action_started_ns=proof['actionStartedAtMonotonicNanos'],
            activity_started_ns=proof['activityStartedAtMonotonicNanos'],
            activity_completed_ns=proof['activityCompletedAtMonotonicNanos'],prepared_ns=proof['preparedAtMonotonicNanos'])
        self.assertEqual(proof,old);self.assertEqual(proof['schema'],2)
        self.assertEqual((proof['preparationBudgetMs'],proof['originalActionBudgetMs'],geometry['durationMs']),(20000,90000,320))
        self.assertEqual(reads,[120.0]);self.assertEqual(len(commands),2)

    def test_current_observation_retains_all_original_proof_assertions_and_live_owner_source(self):
        def function(path,name):
            return next(n for n in ast.parse(path.read_bytes()).body if isinstance(n,ast.FunctionDef) and n.name==name)
        old=function(ROOT/'tools/gecko/chrome_collapse_contract_v3.py','make_short_target_proof')
        new=function(ROOT/'tools/gecko/chrome_collapse_contract_v4.py','short_target_observation')
        assertions=lambda node:Counter(ast.dump(n.test,include_attributes=False) for n in ast.walk(node) if isinstance(n,ast.Assert))
        self.assertEqual(assertions(new),assertions(old))
        run=function(ROOT/'tests/gecko/run_chrome_collapse_v4.py','run_v4')
        call=next(n for n in ast.walk(run) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='short_swipe_once')
        self.assertEqual(ast.unparse(next(v.value for v in call.keywords if v.arg=='owner_activity')),
                         "native_ui['compactExpand']['activityState']")

    def test_empty_then_ready_retains_both_original_frames_and_sends_once_from_latest(self):
        result,error,reads,commands,diagnostic=self.invoke()
        self.assertIsNone(error);geometry,proof=result
        self.assertEqual(reads,[120.0,120.0])
        self.assertEqual([p['status'] for p in diagnostic['preparationSamples']],['not-ready','prepared'])
        self.assertEqual(diagnostic['preparationSamples'][0]['rawXml'],v4_short_xml(pending=True))
        self.assertEqual(diagnostic['preparationSamples'][0]['reason'],'owned-empty-web-content')
        self.assertEqual(diagnostic['preparationSamples'][1]['rawXml'],v4_short_xml())
        self.assertEqual(proof['captureRecord']['index'],2)
        self.assertEqual(proof['rawXml'],v4_short_xml())
        self.assertEqual(len([c for c in commands if c[0][3:6]==['shell','input','swipe']]),1)
        self.assertEqual(len([c for c in commands if c[0][3:]==['shell','dumpsys','activity','activities']]),2)
        self.assertEqual(diagnostic['inputInvocations'],1)
        for sample in diagnostic['preparationSamples']:
            self.assertEqual(sample['activityState'],v4_owner())
            self.assertEqual(sample['captureRecord']['existingSceneDeadline'],120.0)
            self.assertFalse(sample['applicationAcceptance'])

    def test_persistent_empty_view_expires_without_input_or_latest_frame_overwrite(self):
        result,error,reads,commands,diagnostic=self.invoke([v4_short_xml(pending=True)])
        self.assertIsNone(result);self.assertIsInstance(error,TimeoutError)
        self.assertTrue(reads and len(reads)<64);self.assertEqual(set(reads),{120.0})
        self.assertEqual(len(diagnostic['preparationSamples']),len(reads))
        self.assertEqual(diagnostic['inputInvocations'],0)
        self.assertTrue(all(c[0][3:]==['shell','dumpsys','activity','activities'] for c in commands))
        self.assertTrue(all(s['status']=='not-ready' for s in diagnostic['preparationSamples']))

    def test_zero_area_owned_placeholder_waits_then_uses_one_fresh_target(self):
        placeholder=v4_short_xml(placeholder=True)
        ready=v4_short_xml()
        result,error,reads,commands,diagnostic=self.invoke([placeholder,ready])
        self.assertIsNone(error); geometry,proof=result
        self.assertEqual(reads,[120.0,120.0])
        self.assertEqual([sample['status'] for sample in diagnostic['preparationSamples']],
                         ['not-ready','prepared'])
        self.assertEqual(diagnostic['preparationSamples'][0]['rawXml'],placeholder)
        self.assertEqual(proof['rawXml'],ready)
        self.assertEqual(proof['captureRecord']['index'],2)
        self.assertEqual([cmd[0][3:6] for cmd in commands],
            [['shell','dumpsys','activity'],['shell','dumpsys','activity'],['shell','input','swipe']])
        self.assertEqual(geometry['durationMs'],320)
        self.assertEqual(diagnostic['inputInvocations'],1)

    def test_persistent_placeholder_and_changed_owner_never_emit_input(self):
        placeholder=v4_short_xml(placeholder=True)
        for frames,owners,wanted_error in (
                ([placeholder],None,TimeoutError),
                ([placeholder,v4_short_xml()],[v4_owner(),v4_owner(window_token='124')],AssertionError)):
            with self.subTest(wanted_error=wanted_error):
                result,error,reads,commands,diagnostic=self.invoke(frames,owners=owners)
                self.assertIsNone(result);self.assertIsInstance(error,wanted_error)
                self.assertTrue(1<len(reads)<64)
                self.assertTrue(all(cmd[0][3:6]==['shell','dumpsys','activity'] for cmd in commands))
                self.assertEqual(diagnostic['inputInvocations'],0)

    def test_only_the_inert_placeholder_in_the_owned_content_slot_can_wait(self):
        for change in ('sized','offset-zero','child','clickable','focused','visible','absent-enabled',
                       'text','duplicate','foreign','unowned-position','overlay','moved-wrapper'):
            with self.subTest(change=change):
                tree=ET.fromstring(v4_short_xml(placeholder=True))
                content=next(n for n in tree.iter('node') if n.get('resource-id')=='android:id/content')
                main=content[0];inner=main[1][0];web=inner[0]
                if change=='sized':web.set('bounds','[0,361][1080,1662]')
                elif change=='offset-zero':web.set('bounds','[1,1][1,1]')
                elif change=='child':ET.SubElement(web,'node',**{'package':v4.PACKAGE})
                elif change=='clickable':web.set('clickable','true')
                elif change=='focused':web.set('focused','true')
                elif change=='visible':web.set('visible-to-user','true')
                elif change=='absent-enabled':web.attrib.pop('enabled')
                elif change=='text':web.set('text','Host controlled active content')
                elif change=='duplicate':inner.append(copy.deepcopy(web))
                elif change=='foreign':web.set('package','foreign.test')
                elif change=='unowned-position':inner.remove(web);main[0].append(web)
                elif change=='overlay':main.append(copy.deepcopy(main[2]))
                elif change=='moved-wrapper':inner.set('bounds','[0,362][1080,1662]')
                frames=[ET.tostring(tree,encoding='unicode'),v4_short_xml()]
                result,error,reads,commands,diagnostic=self.invoke(frames)
                self.assertIsNone(result);self.assertIsNotNone(error)
                self.assertEqual(reads,[120.0])
                self.assertEqual(diagnostic['inputInvocations'],0)

    def test_repeated_webview_foreign_owner_and_unknown_subtree_are_not_pending(self):
        for change in ('duplicate-web','foreign-web','foreign-ready-sibling','extra-ready-window',
                       'foreign-root','foreign-header','missing-content',
                       'extra-window','extra-overlay','nonempty-inner','wrong-content-bounds','short-footer',
                       'disabled-content','unknown-class','missing-flags','bad-xml'):
            tree=ET.fromstring(v4_short_xml(pending=change not in
                ('duplicate-web','foreign-web','foreign-ready-sibling','extra-ready-window')))
            nodes=list(tree.iter('node'));parents={c:p for p in tree.iter() for c in p}
            content=next(n for n in nodes if n.get('resource-id')=='android:id/content')
            main=content[0];outer=main[1];inner=outer[0]
            if change=='duplicate-web':inner.append(copy.deepcopy(inner[0]))
            elif change=='foreign-web':inner[0].set('package','foreign.test')
            elif change=='foreign-ready-sibling':main[2][0][0].set('package','foreign.test')
            elif change=='extra-ready-window':tree.append(copy.deepcopy(tree[0]))
            elif change=='foreign-root':tree[0].set('package','foreign.test')
            elif change=='foreign-header':main[0][0].set('package','foreign.test')
            elif change=='missing-content':content.set('resource-id','')
            elif change=='extra-window':tree.append(copy.deepcopy(tree[0]))
            elif change=='extra-overlay':main.append(copy.deepcopy(main[2]))
            elif change=='nonempty-inner':inner.append(copy.deepcopy(main[0][0]))
            elif change=='wrong-content-bounds':inner.set('bounds','[0,362][1080,1662]')
            elif change=='short-footer':main[2][0][0].set('bounds','[12,1680][155,1824]')
            elif change=='disabled-content':inner.set('enabled','false')
            elif change=='unknown-class':inner.set('class','android.view.View')
            elif change=='missing-flags':inner.attrib.pop('focusable')
            raw='not XML' if change=='bad-xml' else ET.tostring(tree,encoding='unicode')
            with self.subTest(change=change):
                result,error,reads,commands,diagnostic=self.invoke([raw,v4_short_xml()])
                self.assertIsNone(result);self.assertIsNotNone(error);self.assertEqual(len(reads),1)
                self.assertEqual(diagnostic['inputInvocations'],0)

    def test_changed_activity_process_or_window_owner_cannot_rebind_during_wait(self):
        changed=(v4_owner(activity_token='abd'),v4_owner(pid=4322),v4_owner(process_token='ded'),
            v4_owner(window_token='124'),v4_owner().replace('/u0a209','/u0a210'),
            v4_owner().replace('t8','t9'),v4_owner().replace('u0','u1'),
            v4_owner().replace('      app=ProcessRecord{def 4321:'+v4.PACKAGE+'/u0a209}\n',''),
            v4_owner().replace('      app=', '      app=UNKNOWN\n      app='),
            v4_owner().replace('      windows=', '      windows=[UNKNOWN]\n      windows='),
            v4_owner().replace('mCurrentFocus=Window','mCurrentFocus=OtherWindow'))
        for state in changed:
            with self.subTest(state=state):
                result,error,reads,commands,diagnostic=self.invoke(owners=[v4_owner(),state])
                self.assertIsNone(result);self.assertIsNotNone(error);self.assertEqual(len(reads),2)
                self.assertEqual(diagnostic['inputInvocations'],0)
                self.assertEqual(diagnostic['preparationSamples'][0]['status'],'not-ready')
                self.assertEqual(diagnostic['preparationSamples'][-1]['activityState'],state)

    def test_capture_activity_raw_data_or_unknown_errors_do_not_retry(self):
        for failure in ('capture','raw-hash','command-path','command-output','activity','activity-utf8'):
            with self.subTest(failure=failure):
                result,error,reads,commands,diagnostic=self.invoke(failure=failure)
                self.assertIsNone(result);self.assertIsNotNone(error);self.assertEqual(len(reads),1)
                self.assertEqual(diagnostic['inputInvocations'],0)
                if failure!='capture':self.assertEqual(diagnostic['preparationSamples'][0]['rawXml'],v4_short_xml(pending=True))
                if failure=='activity-utf8':
                    sample=diagnostic['preparationSamples'][0]
                    self.assertEqual(bytes.fromhex(sample['activityRawHex']),b'\xffdeclared-invalid-utf8')
                    self.assertEqual(sample['activitySha256'],hashlib.sha256(bytes.fromhex(sample['activityRawHex'])).hexdigest())

    def test_pending_evidence_limit_fails_without_dropping_any_acquired_frame(self):
        state=v4_owner()+'  Declared host-only long detail: '+'x'*260000+'\n'
        result,error,reads,commands,diagnostic=self.invoke([v4_short_xml(pending=True)],owners=[state])
        self.assertIsNone(result);self.assertIsInstance(error,RuntimeError)
        self.assertIn('evidence byte limit',str(error));self.assertEqual(diagnostic['inputInvocations'],0)
        self.assertEqual(len(diagnostic['preparationSamples']),len(reads))
        self.assertLess(len(reads),64)
        self.assertTrue(all(s['rawXml']==v4_short_xml(pending=True) and s['activityState']==state
                            for s in diagnostic['preparationSamples']))
        self.assertTrue(all(s['status']=='not-ready' for s in diagnostic['preparationSamples'][:-1]))
        self.assertEqual(diagnostic['preparationSamples'][-1]['status'],'failed')

    def test_same_capture_index_cannot_reuse_a_previous_empty_frame(self):
        result,error,reads,commands,diagnostic=self.invoke(failure='same-index')
        self.assertIsNone(result);self.assertIsNotNone(error);self.assertEqual(len(reads),2)
        self.assertEqual(diagnostic['inputInvocations'],0)

    def test_late_xml_activity_parse_and_target_validation_cannot_extend_twenty_seconds(self):
        for options in ({'failure':'late-xml'},{'failure':'late-activity'},
                        {'parsed_late':True},{'target_late':True}):
            with self.subTest(options=options):
                result,error,reads,commands,diagnostic=self.invoke([v4_short_xml()],**options)
                self.assertIsNone(result);self.assertIsNotNone(error);self.assertEqual(reads,[120.0])
                self.assertEqual(diagnostic['inputInvocations'],0)
                self.assertEqual(diagnostic['preparationSamples'][0]['rawXml'],v4_short_xml())

    def test_input_failure_is_never_retried_after_valid_fresh_target(self):
        result,error,reads,commands,diagnostic=self.invoke(failure='input')
        self.assertIsNone(result);self.assertIsInstance(error,subprocess.TimeoutExpired)
        self.assertEqual(reads,[120.0,120.0]);self.assertEqual(diagnostic['inputInvocations'],1)
        self.assertEqual(diagnostic['status'],'input-command-failed')
        self.assertEqual(len([c for c in commands if c[0][3:6]==['shell','input','swipe']]),1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
