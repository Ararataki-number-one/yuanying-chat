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

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'tools/gecko'), str(ROOT/'tests/gecko')]
import chrome_collapse_contract_v2 as previous
import chrome_collapse_contract_v3 as current
import run_chrome_collapse_v3 as runner
import ui_hierarchy_driver as driver
import profile_chrome_short_target_test as old_fixture


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
        viewportModes={'32': 'getSize', '35': 'getRealSize'}, compressedHierarchy=False,
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


if __name__ == '__main__':
    unittest.main(verbosity=2)
