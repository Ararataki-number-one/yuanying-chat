"""Current runtime hosts admit only the reviewed raw recovery successor.

The local inverse is a whole-source binding proof, never input to javac or a
replacement for the original filesystem/window behavioral assertions.
"""
import ast
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
CURRENT = '55225a8da3ba67b3be724e243c9b442e635dbc5aa282a2ef0257653e8fb2b364'
PREVIOUS = '34a651c3ccc50499dd5c720c370353600ccf20669df5393ccbf68d6a689f9670'
SOURCE_PATH = 'app/src/main/java/local/pocketchat/GeckoWebView.java'
CURRENT_CONTEXT = b'initialize();if(!resourceDeferred&&!failed){if(!target.isEmpty())owner.beginNavigation'
PREVIOUS_CONTEXT = b'initialize();if(!resourceDeferred&&!failed&&runtime!=null){if(!target.isEmpty())owner.beginNavigation'
SHA = lambda raw: hashlib.sha256(raw).hexdigest()


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT/relative)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


PATH_HOST = load('current_profile_raw_binding', 'tests/browser-profile-path-host/run.py')
WINDOW_HOST = load('current_window_raw_binding', 'tests/gecko-ip-window-barrier-host/run.py')


class CurrentRuntimeRawBindings(unittest.TestCase):
    def test_exact_current_raw_and_only_fifteen_byte_whole_predecessor_proof(self):
        raw = (ROOT/SOURCE_PATH).read_bytes()
        self.assertEqual((SHA(raw), len(raw)), (CURRENT, 128874))
        self.assertIs(PATH_HOST.verify_factored_raw('GeckoWebView', raw), raw)
        previous = raw.replace(CURRENT_CONTEXT, PREVIOUS_CONTEXT, 1)
        self.assertEqual((SHA(previous), len(previous)), (PREVIOUS, 128889))
        proof = WINDOW_HOST.verify_recovery_source(raw, previous)
        self.assertEqual(proof, dict(currentSha256=CURRENT, currentBytes=128874,
                                    previousSha256=PREVIOUS, previousBytes=128889,
                                    removedBytes=15, proofOnly=True, currentJavaUnchanged=True))
        with self.assertRaises(ValueError):
            PATH_HOST.verify_factored_raw('GeckoWebView', previous)
        with self.assertRaises(AssertionError):
            WINDOW_HOST.verify_recovery_source(previous, previous)
        self.assertEqual(WINDOW_HOST.COMPOSED_SOURCE, '12a45fb8a1343bbe5767bdf6c3fba54519650fa1')
        self.assertEqual(WINDOW_HOST.COMPOSED_GV_SHA256, PREVIOUS)
        self.assertEqual(WINDOW_HOST.CURRENT_GV_SHA256, CURRENT)

    def test_every_other_original_raw_pin_remains_exact_and_unknown_is_rejected(self):
        pins = dict(PATH_HOST.PINS); pins.pop('GeckoWebView')
        self.assertEqual(len(pins), 13)
        self.assertEqual(SHA(json.dumps(pins, sort_keys=True, separators=(',', ':')).encode()), '24466f4dc00a0b37a8eba66a39bf6ebc5b5b9de190e82579d496bb414dda5683')
        for name, expected in pins.items():
            raw = (ROOT/'app/src/main/java/local/pocketchat'/(name+'.java')).read_bytes()
            self.assertEqual(SHA(raw), expected)
            self.assertIs(PATH_HOST.verify_factored_raw(name, raw), raw)
            for bad in (raw+b' ', raw[:-1], b'unknown', None, bytearray(raw)):
                with self.assertRaises(ValueError):
                    PATH_HOST.verify_factored_raw(name, bad)
        with self.assertRaises(ValueError):
            PATH_HOST.verify_factored_raw('UnknownClass', b'unknown')

    def test_unknown_recovery_hunks_and_forged_outer_pins_cannot_admit_a_new_image(self):
        raw = (ROOT/SOURCE_PATH).read_bytes()
        previous = raw.replace(CURRENT_CONTEXT, PREVIOUS_CONTEXT, 1)
        removed = raw.replace(CURRENT_CONTEXT, b'', 1)
        variants = [raw+b' ', raw[:-1], removed,
                    raw.replace(CURRENT_CONTEXT, CURRENT_CONTEXT*2, 1),
                    raw.replace(CURRENT_CONTEXT, CURRENT_CONTEXT+b' ', 1), removed+CURRENT_CONTEXT,
                    raw.replace(b'resourceRecovery', b'resourceRecoverz', 1) if b'resourceRecovery' in raw
                    else raw.replace(b'private void initialize()', b'private void initializf()', 1)]
        for changed in variants:
            self.assertNotEqual(changed, raw)
            with self.assertRaises(ValueError):
                PATH_HOST.verify_factored_raw('GeckoWebView', changed)
            with self.assertRaises(AssertionError):
                WINDOW_HOST.verify_recovery_source(changed, previous)
            forged = dict(PATH_HOST.PINS, GeckoWebView=SHA(changed))
            with patch.object(PATH_HOST, 'PINS', forged), self.assertRaises(ValueError):
                PATH_HOST.verify_factored_raw('GeckoWebView', changed)
            with patch.object(WINDOW_HOST, 'CURRENT_GV_SHA256', SHA(changed)), self.assertRaises(AssertionError):
                WINDOW_HOST.verify_recovery_source(changed, previous)
        with self.assertRaises(AssertionError):
            WINDOW_HOST.verify_recovery_source(raw, previous+b' ')

    def test_both_current_behavior_hosts_execute_with_each_real_json_library(self):
        java = os.environ.get('PROFILE_JAVA') or shutil.which('java')
        self.assertTrue(java, 'Existing mandatory JDK is required')
        home = Path(java).resolve().parents[1]
        jars = [Path(os.environ.get('PROFILE_JSON_JAR', ROOT/'work/profile-host/json.jar')),
                Path(os.environ.get('PROFILE_ANDROID_JSON_JAR', ROOT/'work/profile-host/android-json.jar'))]
        env = dict(os.environ, GIT_NO_LAZY_FETCH='1', GIT_OPTIONAL_LOCKS='0')
        with tempfile.TemporaryDirectory(prefix='current-runtime-raw-host-') as temporary:
            for index, jar in enumerate(jars):
                self.assertTrue(jar.is_file(), 'Both known real JSON implementations are mandatory')
                for name, script in [('profile', 'tests/browser-profile-path-host/run.py'),
                                     ('window', 'tests/gecko-ip-window-barrier-host/run.py')]:
                    output = Path(temporary)/str(index)/name/'results.json'
                    cmd = [shutil.which('python3'), str(ROOT/script), '--java-home', str(home),
                           '--json-jar', str(jar), '--output', str(output)]
                    run = subprocess.run(cmd, text=True, capture_output=True, env=env, timeout=180)
                    self.assertEqual(run.returncode, 0, run.stderr[-5000:])
                    report = json.loads(output.read_text())
                    self.assertEqual(report['status'], 'passed')
                    self.assertTrue(report['executionInputsUnchanged'])
                    self.assertEqual(report['sourceFiles'][SOURCE_PATH], CURRENT)
                    self.assertEqual(report['jsonJarSha256'], SHA(jar.read_bytes()))
                    if name == 'profile':
                        self.assertEqual(run.stdout.strip(), 'PERSISTENT_PROFILE_PATH_PROOF:factored')
                        self.assertEqual(len(report['positive']), 2)
                        self.assertTrue(all(row['passed'] == 11 and row['runtimeArgumentVerified'] is True for row in report['positive']))
                        self.assertEqual(len(report['compiledNegatives']), 5)
                        self.assertTrue(all(row['compiled'] and row['actualRuntimeArgumentAssertionRejected'] for row in report['compiledNegatives']))
                        self.assertTrue(report['currentJavaFromRawCurrent'])
                        self.assertFalse(report['sourceHistoryProjectionUsed'])
                    else:
                        self.assertEqual(report['passed'], 67)
                        self.assertEqual(len(report['negativeControls']), 3)
                        self.assertEqual(len(report['sourceMetadataControls']['rejectedInputs']), 7)
                        self.assertEqual(len(report['sourceMetadataControls']['pythonGuardCounterfeits']), 3)
                        self.assertEqual(report['resourceRecoveryWholeProof']['currentSha256'], CURRENT)
                        self.assertTrue(report['sourceMetadataControls']['actualCurrentJavaUsesRawSource'])

    def test_default_embedded_dependency_and_reject_unknown_explicit_jar(self):
        java = os.environ.get('PROFILE_JAVA') or shutil.which('java')
        self.assertTrue(java)
        home = Path(java).resolve().parents[1]
        with tempfile.TemporaryDirectory(prefix='profile-explicit-json-refusal-') as temporary:
            folder = Path(temporary); jar = folder/'unknown.jar'; jar.write_bytes(b'unknown test dependency')
            output = folder/'results.json'
            run = subprocess.run([shutil.which('python3'), str(ROOT/'tests/browser-profile-path-host/run.py'),
                                  '--java-home', str(home), '--json-jar', str(jar), '--output', str(output)],
                                 text=True, capture_output=True, env=dict(os.environ, GIT_NO_LAZY_FETCH='1'), timeout=30)
            self.assertNotEqual(run.returncode, 0)
            self.assertFalse(output.exists())
            self.assertIn('Explicit JSON input is not a fixed real test dependency', run.stderr)
        raw = (ROOT/'tests/browser-profile-path-host/run.py').read_text()
        self.assertIn("'exact-public-Maven-20240303-test-fixture'", raw)
        self.assertIn("'3cf6cd6892e32e2b4c1c39e0f52f5248a2f5b37646fdfbb79a66b46b618414ed'", raw)
        self.assertIn("'01e2506eba3d8bb475bfbb4a85714ec5b11f0abc841d45de516fe32ee8e30348'", raw)


if __name__ == '__main__':
    unittest.main(verbosity=2)
