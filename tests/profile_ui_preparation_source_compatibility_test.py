"""Exact preparation history controls; the actual Observer compiler keeps raw Java."""
import base64
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import ui_checkpoint_source_compatibility as navigation
import ui_observer_source_compatibility as observer
import ui_preparation_source_compatibility as preparation
import ui_visual_preservation_contract as original_ui

ROOT = Path(__file__).resolve().parents[1]


class UiPreparationSourceCompatibilityTests(unittest.TestCase):
    def test_actual_public_blob_whole_inverse_and_forward_roundtrip(self):
        value = preparation.manifest()
        environment = dict(os.environ, GIT_NO_LAZY_FETCH='1')
        def git(*parts):
            return subprocess.check_output(['git', '--no-replace-objects', *parts], cwd=ROOT, env=environment)
        self.assertEqual(git('rev-parse', value['baseCommit'] + '^{tree}').decode().strip(), value['baseTree'])
        self.assertEqual(git('rev-parse', value['baseCommit'] + ':' + preparation.ACTIVITY).decode().strip(), value['previousBlob'])
        previous = git('show', value['baseCommit'] + ':' + preparation.ACTIVITY)
        current = (ROOT / preparation.ACTIVITY).read_bytes()
        self.assertEqual((len(current), preparation.sha(current)), (13638, preparation.CURRENT_SHA256))
        self.assertEqual(preparation.source_input(current, preparation.ACTIVITY), previous)
        self.assertIs(preparation.historical_input(previous), previous)
        with self.assertRaises(AssertionError):preparation.source_input(previous, preparation.ACTIVITY)
        restored = previous
        for delta in value['deltas']:
            before, after = delta['previous'].encode(), delta['current'].encode()
            self.assertEqual(restored.count(before), 1)
            restored = restored.replace(before, after, 1)
        self.assertEqual(restored, current)
        frozen_before = git('show', '03d0c4ace70942a3f6899daffac086cc6682885e:' + preparation.ACTIVITY)
        self.assertEqual(navigation.navigation_source_input(current, preparation.ACTIVITY), frozen_before)
        self.assertEqual(navigation.history_input(current, preparation.ACTIVITY), frozen_before)
        self.assertEqual(preparation.sha(navigation.NAVIGATION_FIXTURE.read_bytes()), '98c2c894fc4eda4adc28d06064943af7b68a99e9c4270b2ed32dafc21bf80775')

    def test_actual_preparation_and_older_semantic_context_mutations_reject(self):
        raw = (ROOT / preparation.ACTIVITY).read_bytes()
        candidates = [raw + b' ', raw[:1024], b'unknown complete source']
        for delta in preparation.manifest()['deltas']:
            current = delta['current'].encode()
            remaining = raw.replace(current, b'', 1)
            moved = remaining + current
            if moved == raw:moved = current + remaining
            candidates.extend((remaining, raw.replace(current, current * 2, 1), moved,
                               raw.replace(current, current + b' ', 1)))
        for before, after in ((b'"glass-display-preparation".equals(action)', b'"downloads".equals(action)'),
                              (b'setContentView(new FrameLayout(this));return;', b'setContentView(new FrameLayout(this));seed();return;'),
                              (b'NavigationTypographyEvidence(this)', b'NavigationTypographyEvidence(null)'),
                              (b'controller.setVisible(false);', b'controller.setVisible(true);'),
                              (b'downloadObservationNonces.contains(nonce)', b'false'),
                              (b'if(workspace!=null)workspace.close();', b'if(workspace!=null)workspace.toString();')):
            self.assertEqual(raw.count(before), 1)
            candidates.append(raw.replace(before, after, 1))
        for candidate in candidates:
            self.assertNotEqual(candidate, raw)
            with self.subTest(sha256=preparation.sha(candidate)):
                with self.assertRaises(AssertionError):preparation.source_input(candidate, preparation.ACTIVITY)
                self.assertIs(preparation.historical_input(candidate), candidate)
                with self.assertRaises(AssertionError):navigation.navigation_source_input(candidate, preparation.ACTIVITY)
                with self.assertRaises(AssertionError):observer.source_input(candidate, preparation.ACTIVITY)
                with self.assertRaises(AssertionError):original_ui.verify_download_visual_fixture_source(candidate)

    def test_actual_overlap_mapping_keeps_every_old_hunk_and_raw_receipt(self):
        raw = (ROOT / preparation.ACTIVITY).read_bytes()
        mapped = []
        for index, delta in enumerate(navigation.navigation_manifest()['deltas']):
            old = delta['current'].encode()
            current = preparation.actual_navigation_context(raw, old)
            self.assertEqual(raw.count(current), 1)
            if index == 1:
                self.assertNotEqual(current, old)
                self.assertIn(b'"glass-display-preparation".equals(action)', current)
                self.assertIn(b'NavigationTypographyEvidence(this)', current)
            else:self.assertEqual(current, old)
            mapped.append(current != old)
        self.assertEqual(mapped, [False, True, False, False, False])
        with self.assertRaises(AssertionError):preparation.actual_navigation_context(raw + b' ', navigation.navigation_manifest()['deltas'][1]['current'].encode())
        receipt = original_ui.verify_download_visual_fixture_source(raw)
        self.assertEqual(receipt['selectedFixtureSha256'], preparation.sha(raw))
        self.assertEqual(preparation.historical_report_sha(raw, receipt['selectedFixtureSha256']), navigation.NAVIGATION_CURRENT_SHA256)
        with self.assertRaises(AssertionError):preparation.historical_report_sha(raw, navigation.NAVIGATION_CURRENT_SHA256)
        self.assertEqual((ROOT / preparation.ACTIVITY).read_bytes(), raw)

    def test_complete_types_paths_and_exact_metadata_remain_strict(self):
        raw = (ROOT / preparation.ACTIVITY).read_bytes()
        for candidate in (None, raw.decode(), bytearray(raw), memoryview(raw), True, b'', raw[:512]):
            with self.assertRaises(AssertionError):preparation.source_input(candidate, preparation.ACTIVITY)
        for path in (None, Path(preparation.ACTIVITY), '/' + preparation.ACTIVITY, '../' + preparation.ACTIVITY, 'tests/other.java'):
            with self.assertRaises(AssertionError):preparation.source_input(raw, path)
            self.assertIs(preparation.historical_input(raw, path), raw)
        value = preparation.manifest()
        metadata = preparation.FIXTURE.read_bytes()
        with tempfile.TemporaryDirectory(prefix='preparation-source-metadata-') as directory:
            root = Path(directory)
            fixture = root / 'tests/fixtures/ui-preparation-source-deltas.json'
            fixture.parent.mkdir(parents=True)
            with patch.object(preparation, 'ROOT', root), patch.object(preparation, 'FIXTURE', fixture):
                for content in (b'', b'unknown metadata', b'x' * 16385):
                    fixture.write_bytes(content)
                    with self.assertRaises(AssertionError):preparation.manifest()
                for content in (b'{"schema":1,' + metadata.lstrip()[1:],
                                metadata.replace(b'"schema": 1', b'"schema": NaN', 1),
                                metadata.replace(b'"schema": 1', b'"schema": true', 1),
                                metadata.replace(b'"previousBytes": 13373', b'"previousBytes": 13372', 1)):
                    fixture.write_bytes(content)
                    with patch.object(preparation, 'FIXTURE_SHA256', preparation.sha(content)), self.assertRaises(AssertionError):
                        preparation.manifest()
                fixture.write_bytes(metadata)
                self.assertEqual(preparation.manifest(), value)
                target = root / 'ordinary'; target.write_bytes(metadata)
                fixture.unlink(); fixture.symlink_to(target)
                with self.assertRaises(AssertionError):preparation.manifest()
            self.assertEqual(value['previousSha256'], preparation.PREVIOUS_SHA256)

    def test_actual_observer_extracts_raw_java_and_binds_all_execution_inputs(self):
        spec = importlib.util.spec_from_file_location('preparation_actual_observer_host', ROOT / 'tests/gecko-ui-download-observer-host/run.py')
        host = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(host)
        raw = (ROOT / preparation.ACTIVITY).read_bytes()
        needles = ('@Override protected void onNewIntent(Intent request)',
                   'String downloadObservationRejection(Intent request)', 'void rejectDownloadObservation(String nonce,String reason)')
        original_member, original_run = host.member, host.subprocess.run
        expected = {needle: original_member(raw.decode(), needle) for needle in needles}
        extracted, compiled = set(), []
        def member(source, needle):
            self.assertEqual(source.encode(), raw)
            extracted.add(needle)
            return original_member(source, needle)
        def run(command, *args, **kwargs):
            if Path(command[0]).name == 'javac':
                path = next(Path(part) for part in command if str(part).endswith('/ObserverCases.java'))
                text = path.read_text()
                for body in expected.values():self.assertIn(body, text)
                compiled.append(path.name)
            return original_run(command, *args, **kwargs)
        java = Path(os.environ.get('PROFILE_JAVA') or shutil.which('java') or '')
        home = java.resolve().parents[1]
        self.assertTrue((home / 'bin/javac').is_file(), 'Mandatory real JDK required')
        with tempfile.TemporaryDirectory(prefix='preparation-current-observer-') as directory:
            folder = Path(directory)
            jar, output = folder / 'json.jar', folder / 'results.json'
            jar.write_bytes(base64.b64decode(b''.join((ROOT / 'tests/persistent-runtime-path-host/json-20240303.jar.b64').read_bytes().splitlines()), validate=True))
            self.assertEqual(preparation.sha(jar.read_bytes()), '3cf6cd6892e32e2b4c1c39e0f52f5248a2f5b37646fdfbb79a66b46b618414ed')
            with patch.object(host, 'member', side_effect=member), patch.object(host.subprocess, 'run', side_effect=run), \
                    patch.object(sys, 'argv', ['observer', '--java-home', str(home), '--json-jar', str(jar), '--output', str(output)]), \
                    contextlib.redirect_stdout(io.StringIO()):
                host.main()
            receipt = json.loads(output.read_bytes())
            self.assertEqual(receipt['status'], 'passed')
            self.assertEqual(receipt['passed'], receipt['total'])
            self.assertTrue(receipt['executionInputsUnchanged'])
            self.assertTrue(receipt['actualJavaFromRawCurrent'])
            self.assertFalse(receipt['sourceHistoryProjectionUsed'])
            self.assertEqual(receipt['sourceSha256']['activity'], preparation.sha(raw))
            self.assertEqual(receipt['historicalSourceGuardSha256'], host.PINS)
            self.assertNotEqual(receipt['sourceSha256']['activity'], host.PINS['activity'])
            for path, digest in receipt['sourceFiles'].items():
                self.assertEqual(preparation.sha((ROOT / path).read_bytes()), digest)
            for path in ('tests/ui_preparation_source_compatibility.py', preparation.FIXTURE.relative_to(ROOT).as_posix(),
                         'tests/ui_checkpoint_source_compatibility.py', 'tests/fixtures/ui-navigation-source-deltas.json',
                         'tests/gradle_transport_source_compatibility.py', 'tests/glass_emulator_navigation_source_compatibility.py',
                         'tests/fixtures/glass-emulator-navigation-source-deltas.json'):
                self.assertIn(path, receipt['sourceFiles'])
        self.assertEqual(extracted, set(needles))
        self.assertEqual(compiled, ['ObserverCases.java'])
        self.assertEqual((ROOT / preparation.ACTIVITY).read_bytes(), raw)


if __name__ == '__main__':
    unittest.main(verbosity=2)
