"""Exact SurfaceView history guards; both JVM producers retain current raw Java."""
import ast
import base64
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

import gecko_surface_source_compatibility as inputs

ROOT = Path(__file__).resolve().parents[1]


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


path_host = load('surface_actual_path_host', 'tests/browser-profile-path-host/run.py')
window_host = load('surface_actual_window_host', 'tests/gecko-ip-window-barrier-host/run.py')


class GeckoSurfaceHistoricalSourceInputs(unittest.TestCase):
    def test_public_blob_whole_inverse_and_forward_are_exact(self):
        value = json.loads(inputs.FIXTURE.read_bytes())
        env = dict(os.environ, GIT_NO_LAZY_FETCH='1')
        def git(*parts):
            return subprocess.check_output(['git', '--no-replace-objects', *parts], cwd=ROOT, env=env)
        self.assertEqual(git('rev-parse', value['baseCommit'] + '^{tree}').decode().strip(), value['baseTree'])
        self.assertEqual(git('rev-parse', value['baseCommit'] + ':' + inputs.GV).decode().strip(), value['previousBlob'])
        previous = git('show', value['baseCommit'] + ':' + inputs.GV)
        raw = (ROOT / inputs.GV).read_bytes()
        self.assertEqual((len(raw), inputs.sha(raw)), (128871, '3e20d18790110422acb9c622bf3dfd508d893c4a7f87a663b600a36bccc1e12a'))
        self.assertEqual((len(previous), inputs.sha(previous)), (128874, '55225a8da3ba67b3be724e243c9b442e635dbc5aa282a2ef0257653e8fb2b364'))
        self.assertEqual(inputs.source_input(raw, inputs.GV), previous)
        self.assertIs(inputs.historical_input(previous), previous)
        with self.assertRaises(ValueError):inputs.source_input(previous, inputs.GV)
        for delta in value['deltas']:
            before, after = delta['previous'].encode(), delta['current'].encode()
            self.assertEqual(previous.count(before), 1)
            previous = previous.replace(before, after, 1)
        self.assertEqual(previous, raw)

    def test_actual_surface_context_and_existing_semantic_mutants_reject(self):
        raw = (ROOT / inputs.GV).read_bytes()
        value = json.loads(inputs.FIXTURE.read_bytes())
        previous = inputs.historical_input(raw).replace(
            b'initialize();if(!resourceDeferred&&!failed){if(!target.isEmpty())owner.beginNavigation',
            b'initialize();if(!resourceDeferred&&!failed&&runtime!=null){if(!target.isEmpty())owner.beginNavigation', 1)
        changed = [raw + b' ', raw[:1000], b'unknown source']
        for delta in value['deltas']:
            current = delta['current'].encode()
            self.assertEqual(raw.count(current), 1)
            remaining = raw.replace(current, b'', 1)
            moved = remaining + current
            if moved == raw:moved = current + remaining
            changed.extend((remaining, raw.replace(current, current * 2, 1), moved,
                            raw.replace(current, current + b' ', 1)))
        for before, after in ((b'surface.setViewBackend(GeckoView.BACKEND_SURFACE_VIEW);', b''),
                              (b'BACKEND_SURFACE_VIEW', b'BACKEND_TEXTURE_VIEW'),
                              (b'BACKEND_SURFACE_VIEW', b'BACKEND_SURFACE_VIEW_BACKEND_SURFACE_VIEW'),
                              (b'initialize();if(!resourceDeferred&&!failed){if(!target.isEmpty())owner.beginNavigation',
                               b'initialize();if(!failed){if(!target.isEmpty())owner.beginNavigation'),
                              (b'if(!ready||!current()){fail.accept(new IOException("\xe5\x87\xba\xe5\x8f\xa3\xe6\x97\xb6\xe5\x8c\xba\xe6\x9f\xa5\xe8\xaf\xa2\xe4\xb8\x8a\xe4\xb8\x8b\xe6\x96\x87\xe5\xb7\xb2\xe5\x8f\x98\xe5\x8c\x96"))',
                               b'if(!current()){fail.accept(new IOException("\xe5\x87\xba\xe5\x8f\xa3\xe6\x97\xb6\xe5\x8c\xba\xe6\x9f\xa5\xe8\xaf\xa2\xe4\xb8\x8a\xe4\xb8\x8b\xe6\x96\x87\xe5\xb7\xb2\xe5\x8f\x98\xe5\x8c\x96"))')):
            self.assertEqual(raw.count(before), 1)
            changed.append(raw.replace(before, after, 1))
        for candidate in changed:
            self.assertNotEqual(candidate, raw)
            with self.subTest(sha256=inputs.sha(candidate)):
                with self.assertRaises(ValueError):inputs.source_input(candidate, inputs.GV)
                self.assertIs(inputs.historical_input(candidate), candidate)
                with self.assertRaises(ValueError):path_host.verify_factored_raw('GeckoWebView', candidate)
                with self.assertRaises(AssertionError):window_host.verify_recovery_source(candidate, previous)
        for candidate in (None, raw.decode(), bytearray(raw), memoryview(raw), b'', raw[:100]):
            with self.assertRaises(ValueError):inputs.source_input(candidate, inputs.GV)
        for relative in (None, Path(inputs.GV), '/' + inputs.GV, '../' + inputs.GV, 'app/GeckoWebView.java'):
            with self.assertRaises(ValueError):inputs.source_input(raw, relative)

    def test_original_guard_bodies_pins_and_report_identity_are_independent(self):
        raw = (ROOT / inputs.GV).read_bytes()
        self.assertIs(path_host.verify_factored_raw('GeckoWebView', raw), raw)
        self.assertEqual(inputs.historical_report_sha(raw, inputs.sha(raw)), path_host.PINS['GeckoWebView'])
        with self.assertRaises((ValueError, AssertionError)):
            inputs.historical_report_sha(raw, path_host.PINS['GeckoWebView'])
        guards = {
            'tests/browser-profile-path-host/run.py': {
                'verify_factored_raw': 'db16471eae547baac2f23b9efd42f72e5d7171c7577e34a196021a870dc209e2'},
            'tests/gecko-ip-window-barrier-host/run.py': {
                'verify_recovery_source': '1b4ba751bcc8d05af52ca20c21c3e7834e7e411fcafc4b03a7c40382150e5fdb',
                'verify_source_delta': 'a751ca926907ad03af86ce714e419754e24a3a59406f6e3aa66e71519ebee37d'}}
        for path, names in guards.items():
            current = (ROOT / path).read_text()
            for name, expected in names.items():
                node = next(n for n in ast.parse(current).body if isinstance(n, ast.FunctionDef) and n.name == name)
                self.assertEqual(inputs.sha(ast.get_source_segment(current, node).encode()), expected)
        self.assertEqual(path_host.PINS['GeckoWebView'], '55225a8da3ba67b3be724e243c9b442e635dbc5aa282a2ef0257653e8fb2b364')

    def test_actual_hosts_extract_and_compile_raw_and_report_current_files(self):
        raw = (ROOT / inputs.GV).read_bytes()
        original_member, original_declaration = path_host.member, window_host.declaration
        original_run = subprocess.run
        actual_path, actual_window, compiled = [], set(), {'path': 0, 'window': 0}
        expected_path = original_member(raw.decode(), 'void initialize()')
        expected_window = {name: original_declaration(raw.decode(), name) for name in window_host.MEMBERS}
        def member(source, needle):
            if needle == 'void initialize()':
                self.assertEqual(source.encode(), raw)
                actual_path.append(needle)
            return original_member(source, needle)
        def declaration(source, needle):
            if source.encode() == raw and needle in expected_window:actual_window.add(needle)
            return original_declaration(source, needle)
        def run(command, *args, **kwargs):
            if Path(command[0]).name == 'javac':
                paths = [Path(part) for part in command if str(part).endswith('.java')]
                generated = next((p for p in paths if p.name in ('PathHost.java', 'WindowBarrierHost.java')), None)
                if generated is not None:
                    kind = 'path' if generated.name == 'PathHost.java' else 'window'
                    if kind == 'window' and generated.parent.name == 'current':
                        text = generated.read_text()
                        for body in expected_window.values():
                            for before, after in (('GeckoWebView.this', 'WebBoundary.this'), ('WebExtension.Port', 'PortBoundary'),
                                                  ('GeckoSession', 'SessionBoundary'), ('GeckoResult', 'ResultBoundary'),
                                                  ('GeckoTimeZoneController', 'ControllerBoundary'), ('AppSessionIdentity', 'IdentityBoundary')):
                                body = body.replace(before, after)
                            self.assertIn(body, text)
                    compiled[kind] += 1
            return original_run(command, *args, **kwargs)
        java = Path(os.environ.get('PROFILE_JAVA') or shutil.which('java') or '')
        home = java.resolve().parents[1]
        self.assertTrue((home / 'bin/javac').is_file(), 'Real JDK required; no skip')
        with tempfile.TemporaryDirectory(prefix='surface-current-hosts-') as directory:
            folder = Path(directory)
            jar = folder / 'json.jar'
            jar.write_bytes(base64.b64decode(b''.join((ROOT / 'tests/persistent-runtime-path-host/json-20240303.jar.b64').read_bytes().splitlines()), validate=True))
            self.assertEqual(inputs.sha(jar.read_bytes()), '3cf6cd6892e32e2b4c1c39e0f52f5248a2f5b37646fdfbb79a66b46b618414ed')
            for name, host in (('path', path_host), ('window', window_host)):
                output = folder / name / 'results.json'
                argv = [name, '--java-home', str(home), '--output', str(output), '--json-jar', str(jar)]
                with patch.object(path_host, 'member', side_effect=member), \
                        patch.object(window_host, 'declaration', side_effect=declaration), \
                        patch.object(subprocess, 'run', side_effect=run), patch.object(sys, 'argv', argv):
                    host.main()
                result = json.loads(output.read_bytes())
                self.assertEqual(result['status'], 'passed')
                self.assertTrue(result['executionInputsUnchanged'])
                self.assertTrue(result['currentJavaFromRawCurrent'])
                self.assertFalse(result['sourceHistoryProjectionUsed'])
                self.assertEqual(result['sourceFiles'][inputs.GV], inputs.sha(raw))
                self.assertEqual((result['actualRawSha256'], result['actualRawBytes']), (inputs.sha(raw), len(raw)))
                self.assertEqual(result['historicalGeckoSurfaceGuardSha256'], path_host.PINS['GeckoWebView'])
                for path in ('tests/gecko_surface_source_compatibility.py', inputs.FIXTURE.relative_to(ROOT).as_posix()):
                    self.assertEqual(result['sourceFiles'][path], inputs.sha((ROOT / path).read_bytes()))
                if name == 'path':
                    self.assertEqual(len(result['positive']), 2)
                    self.assertEqual(len(result['compiledNegatives']), 5)
                else:
                    self.assertEqual(result['passed'], 67)
                    self.assertEqual(len(result['negativeControls']), 3)
                    self.assertEqual(len(result['sourceMetadataControls']['rejectedInputs']), 7)
                    self.assertEqual(len(result['sourceMetadataControls']['pythonGuardCounterfeits']), 3)
        self.assertEqual(actual_path, ['void initialize()'])
        self.assertIn('File directory=cpuBoot.profile,config=cpuBoot.config;', expected_path)
        self.assertEqual(actual_window, set(window_host.MEMBERS))
        self.assertEqual(compiled, {'path': 6, 'window': 7})
        self.assertEqual((ROOT / inputs.GV).read_bytes(), raw)


if __name__ == '__main__':
    unittest.main(verbosity=2)
