"""Whole-source callback guard controls; current Java is compiled unchanged."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import profile_context_callback_source_compatibility as inputs

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('callback_current_profile_path_host', ROOT / 'tests/browser-profile-path-host/run.py')
host = importlib.util.module_from_spec(spec)
spec.loader.exec_module(host)


class ProfileContextCallbackSourceInputs(unittest.TestCase):
    def test_actual_public_blob_and_entire_forward_roundtrip(self):
        value = inputs.manifest()
        environment = dict(os.environ, GIT_NO_LAZY_FETCH='1')
        def git(*parts):
            return subprocess.check_output(['git', '--no-replace-objects', *parts], cwd=ROOT, env=environment)
        self.assertEqual(git('rev-parse', value['baseCommit'] + '^{tree}').decode().strip(), value['baseTree'])
        self.assertEqual(git('rev-parse', value['baseCommit'] + ':' + inputs.PATH).decode().strip(), value['previousBlob'])
        previous = git('show', value['baseCommit'] + ':' + inputs.PATH)
        current = (ROOT / inputs.PATH).read_bytes()
        self.assertEqual(inputs.source_input(current, inputs.PATH), previous)
        self.assertEqual((inputs.sha(previous), len(previous)), (value['previousSha256'], value['previousBytes']))
        with self.assertRaises(ValueError):inputs.source_input(previous, inputs.PATH)
        self.assertIs(inputs.historical_guard_input(previous, 'ProfileContext'), previous)
        for delta in value['deltas']:
            before, after = delta['previous'].encode(), delta['current'].encode()
            self.assertEqual(previous.count(before), 1)
            previous = previous.replace(before, after, 1)
        self.assertEqual(previous, current)

    def test_unknown_missing_duplicate_moved_changed_and_old_path_semantics_reject(self):
        raw = (ROOT / inputs.PATH).read_bytes()
        changed = [raw + b' ', raw[:1000], b'unknown source']
        for delta in inputs.manifest()['deltas']:
            current = delta['current'].encode()
            self.assertEqual(raw.count(current), 1)
            remaining = raw.replace(current, b'', 1)
            moved = remaining + current
            if moved == raw:moved = current + remaining
            changed.extend((remaining, raw.replace(current, current * 2, 1), moved,
                            raw.replace(current, current + b' ', 1)))
        for before, after in ((b'callbackOwner=Profiles.global(base)', b'callbackOwner=base'),
                              (b'callbackOwner.registerComponentCallbacks(callback);', b''),
                              (b'callbackOwner.unregisterComponentCallbacks(callback);', b''),
                              (b'if(slot==0)return base;', b'if(slot==1)return base;'),
                              (b'return directory(super.getNoBackupFilesDir());', b'return directory(super.getCacheDir());')):
            self.assertEqual(raw.count(before), 1)
            changed.append(raw.replace(before, after, 1))
        for candidate in changed:
            self.assertNotEqual(candidate, raw)
            with self.subTest(sha256=inputs.sha(candidate)):
                with self.assertRaises(ValueError):inputs.source_input(candidate, inputs.PATH)
                self.assertIs(inputs.historical_guard_input(candidate, 'ProfileContext'), candidate)
                with self.assertRaises(ValueError):host.verify_factored_raw('ProfileContext', candidate)

    def test_guard_returns_actual_raw_identity_and_owned_types_and_paths_stay_strict(self):
        raw = (ROOT / inputs.PATH).read_bytes()
        self.assertIs(host.verify_factored_raw('ProfileContext', raw), raw)
        self.assertNotEqual(inputs.historical_guard_input(raw, 'ProfileContext'), raw)
        for name in ('Profiles', 'GeckoWebView', 'UnknownClass', None):
            self.assertIs(inputs.historical_guard_input(raw, name), raw)
        for candidate in (None, raw.decode(), bytearray(raw), memoryview(raw), b'', raw[:100], b'x' * 32769):
            with self.assertRaises(ValueError):inputs.source_input(candidate, inputs.PATH)
        for path in (None, Path(inputs.PATH), '/' + inputs.PATH, '../' + inputs.PATH, 'app/ProfileContext.java'):
            with self.assertRaises(ValueError):inputs.source_input(raw, path)
        self.assertEqual(host.PINS['ProfileContext'], inputs.PREVIOUS_SHA256)
        self.assertEqual(hashlib.sha256(json.dumps({name: value for name, value in host.PINS.items() if name != 'GeckoWebView'},
            sort_keys=True, separators=(',', ':')).encode()).hexdigest(), '24466f4dc00a0b37a8eba66a39bf6ebc5b5b9de190e82579d496bb414dda5683')

    def test_actual_member_extraction_and_javac_receive_current_raw_after_guard_inverse(self):
        current = (ROOT / inputs.PATH).read_bytes()
        original_member, original_run = host.member, host.subprocess.run
        observed_members, compiled = set(), []
        needles = ('File directory(', 'public File getNoBackupFilesDir()')
        expected = {needle: original_member(current.decode(), needle) for needle in needles}
        def member(source, needle):
            if needle in needles:
                self.assertEqual(source.encode(), current)
                observed_members.add(needle)
            return original_member(source, needle)
        def run(command, *args, **kwargs):
            if Path(command[0]).name == 'javac':
                path = next(Path(part) for part in command if str(part).endswith('/PathHost.java'))
                text = path.read_text()
                for body in expected.values():self.assertIn(body, text)
                compiled.append(path.name)
            return original_run(command, *args, **kwargs)
        java = Path(os.environ.get('PROFILE_JAVA') or shutil.which('java') or '')
        home = java.resolve().parents[1]
        self.assertTrue((home / 'bin/javac').is_file(), 'Real JDK required; no skip')
        with tempfile.TemporaryDirectory(prefix='callback-current-profile-path-') as directory:
            output = Path(directory) / 'results.json'
            with patch.object(host, 'member', side_effect=member), patch.object(host.subprocess, 'run', side_effect=run), \
                    patch.object(sys, 'argv', ['path-host', '--java-home', str(home), '--output', str(output)]):
                host.main()
            result = json.loads(output.read_bytes())
            self.assertEqual(result['status'], 'passed')
            self.assertEqual(result['sourceSha256']['ProfileContext'], inputs.sha(current))
            self.assertEqual(result['historicalGuardPins']['ProfileContext'], inputs.PREVIOUS_SHA256)
            self.assertTrue(result['currentJavaFromRawCurrent'])
            self.assertTrue(result['executionInputsUnchanged'])
            self.assertEqual(len(result['compiledNegatives']), 5)
            for path in ('tests/profile_context_callback_source_compatibility.py', 'tests/fixtures/profile-context-callback-source-deltas.json'):
                self.assertEqual(result['sourceFiles'][path], inputs.sha((ROOT / path).read_bytes()))
        self.assertEqual(observed_members, set(needles))
        self.assertEqual(len(compiled), 6)
        self.assertEqual((ROOT / inputs.PATH).read_bytes(), current)


if __name__ == '__main__':
    unittest.main(verbosity=2)
