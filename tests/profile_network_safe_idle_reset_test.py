"""Actual fixture reset wait with declared host queue/clock/transport boundaries.

Production JS runs unchanged under the existing JSDOM gesture/timer adapters.
These controls establish the mechanism, not Android execution or a new CI result.
"""
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
ACTIVITY = ROOT / 'tests/gecko/NetworkSafeIdleIntegrationActivity.java'
spec = importlib.util.spec_from_file_location('reset_method_reader', ROOT / 'tests/network-fence-completion-host/run.py')
reader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reader)

NODE_CONTROL = r'''
'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const here=path.join(process.cwd(),'tests');
const source=fs.readFileSync(path.join(here,'resource-web-observer.cjs'),'utf8').split("test('Initial resource state")[0];
const fixture=new Function('require','__dirname',source+'\nreturn fixture;')(require,here);
const f=fixture(),request='12345678-1234-1234-1234-123456789abc';
try {
  f.install('before-reset');f.flush(250);
  const observer=f.window.__pocketWebReplyObserver,documentId=observer.documentId;
  const send=f.window.document.querySelector('[data-testid="send-button"]');
  for(const receive of f.handlers.get('click'))receive({isTrusted:true,target:send});
  const gestureAt=observer.lastGestureAt();f.busy(true);f.advance(1000);
  f.busy(false);f.window.document.querySelector('textarea').value='network fence prompt';
  f.install('after-reset');assert.equal(f.window.__pocketWebReplyObserver,observer);
  observer.requestResources(request);const first=f.resources().at(-1);
  assert.equal(first.busy,true,'Reset/rebind cannot erase the production interaction guard');
  assert.equal(first.resourceBinding,'after-reset');assert.equal(first.documentId,documentId);
  assert.equal(observer.lastGestureAt(),gestureAt);assert.equal(f.scheduled(1500),1);
  f.advance(499);observer.requestResources(request);assert.equal(f.resources().at(-1).busy,true);
  f.advance(1);observer.requestResources(request);const idle=f.resources().at(-1);
  assert.equal(idle.busy,false);assert.equal(idle.resourceSequence,first.resourceSequence+2);
  assert.equal(idle.resourceBinding,'after-reset');assert.equal(idle.documentId,documentId);
  f.busy(true);f.advance(1500);observer.requestResources(request);
  assert.equal(f.resources().at(-1).busy,true,'Elapsed time cannot substitute for actual website idle');
  assert.equal(observer.lastGestureAt(),gestureAt,'Observation must not replay input');
  assert.deepEqual(f.posts.filter(row=>['intent','bound','uncertain','stop'].includes(row.type)),[]);
  console.log('PASS unchanged production JS reset mechanism; synthetic DOM and clock only');
} finally {f.close();}
'''


class SafeIdleResetTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.java = os.environ.get('PROFILE_JAVA') or shutil.which('java')
        cls.node = shutil.which('node')
        if not cls.java or not cls.node:
            raise RuntimeError('Host JDK and Node required; Android evidence is not substituted')
        cls.temporary = tempfile.TemporaryDirectory(prefix='safe-idle-reset-host-')
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.directory = Path(cls.temporary.name)
        fixture = ACTIVITY.read_text()
        production = (ROOT / 'app/src/main/java/local/pocketchat/NetworkUiProvider.java').read_text()
        rendered = (ROOT / 'tests/network-safe-idle-reset-host/ResetIdleHost.java.in').read_text()
        for key, source, signature in (
                ('RESET_CURRENT', fixture, '  static boolean resetGuardCurrent('),
                ('RESET_JSON', fixture, '  static JSONObject resetGuardJson('),
                ('RESET_WAIT', fixture, '  TaskGuardSnapshot awaitResetIdle('),
                ('TASK_IDLE', production, '  static boolean taskIdle(')):
            assert rendered.count('@' + key + '@') == 1
            rendered = rendered.replace('@' + key + '@', reader.method(source, signature))
        harness = cls.directory / 'ResetIdleHost.java'
        harness.write_text(rendered)
        command = [cls.java, '-m', 'jdk.compiler/com.sun.tools.javac.Main', '-encoding', 'UTF-8',
                   '-d', str(cls.directory), str(harness),
                   str(ROOT / 'app/src/main/java/local/pocketchat/TaskGuardSnapshot.java')]
        compiled = subprocess.run(command, text=True, capture_output=True, timeout=30)
        if compiled.returncode:
            raise AssertionError('Actual fixture wait failed to compile:\n' + compiled.stdout + compiled.stderr)

    def control(self, *modes):
        for mode in modes:
            with self.subTest(mode=mode):
                result = subprocess.run([self.java, '-cp', str(self.directory), 'local.pocketchat.ResetIdleHost', mode],
                                        text=True, capture_output=True, timeout=20)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(result.stdout.strip(), 'PASS ' + mode + '; host boundaries only')

    def test_actual_js_rebind_preserves_interaction_guard_until_real_idle(self):
        result = subprocess.run([self.node, '-e', NODE_CONTROL], cwd=ROOT, text=True, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.strip(), 'PASS unchanged production JS reset mechanism; synthetic DOM and clock only')

    def test_fresh_idle_and_busy_to_idle_within_original_deadline(self):
        self.control('idle', 'cooldown', 'unknown-then-idle')

    def test_unknown_and_all_actual_busy_fields_remain_blocking(self):
        self.control('unknown', 'busy', 'file', 'submitting', 'operation', 'downloading', 'route-held')

    def test_foreign_document_epoch_binding_and_environment_never_authorize(self):
        self.control('foreign-document', 'foreign-epoch', 'foreign-binding', 'foreign-slot', 'foreign-generation', 'foreign-environment')

    def test_stale_sequence_or_changed_current_snapshot_never_authorize(self):
        self.control('unchanged-sequence', 'current-changed')

    def test_missing_late_and_queued_callbacks_share_one_five_second_budget(self):
        self.control('missing', 'late', 'delayed-ui')

    def test_caller_keeps_original_idle_assertion_and_records_reset_failure(self):
        source = ACTIVITY.read_text()
        restore = reader.method(source, '  void restoreCase()')
        self.assertIn('TaskGuardSnapshot observed=awaitResetIdle(owner,lastResetPage.getString("documentId"));', restore)
        self.assertIn('if(!NetworkUiProvider.taskIdle(session,observed))throw new IOException("Controlled reset did not obtain a current idle task guard");', restore)
        self.assertIn('"lastResetObservation",lastResetObservation', reader.method(source, '  synchronized void result('))
        self.assertNotIn('1500', restore)


if __name__ == '__main__':
    unittest.main(verbosity=2)
