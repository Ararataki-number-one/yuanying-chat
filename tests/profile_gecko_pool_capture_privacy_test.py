"""Host-only pool capture boundary controls; no Android/network workload executes.

Generated service-key shapes exercise the existing bounded privacy policy. This
does not classify the unavailable raw bytes of any earlier CI failure.
"""
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from gecko import caret_ime_guard as G

RUNNER = ROOT / 'tests/gecko/run_gecko_pool.py'
PREVIOUS_RUNNER_SHA256 = '1a7c8bbaccc375aeb872ba4bebde68f48e29d11796d2f3501ba0337e37a95524'
IMPORT = 'from gecko.caret_ime_guard import redact_service_api_keys, verify_capture_privacy, diagnostic_privacy_summary\n'
FUNCTION = '''def capture_diagnostic_text(value):
    """Return a verified derivative capture before parsing, raising or storing it."""
    sanitized, metadata = redact_service_api_keys(value)
    if not verify_capture_privacy(metadata, sanitized):
        raise ValueError('Diagnostic capture privacy: invalid derivative metadata')
    return sanitized, metadata


'''
CAPTURES = '''    privacy_captures = []
    def capture_text(value):
        sanitized, metadata = capture_diagnostic_text(value)
        if len(privacy_captures) >= 4096:
            raise ValueError('Diagnostic capture privacy: capture-count bound')
        privacy_captures.append(metadata)
        return sanitized

'''
LOG = "        return capture_text(adb('logcat', '-d', '-s', 'PocketGeckoPool:I', 'AndroidRuntime:E', '*:S'))\n"
OLD_LOG = "        return adb('logcat', '-d', '-s', 'PocketGeckoPool:I', 'AndroidRuntime:E', '*:S')\n"
REPORT = "            report['capturePrivacy'] = diagnostic_privacy_summary(privacy_captures)\n"
FAILURE = "            (OUT / 'gecko-pool-failure-log.txt').write_text(capture_text(adb('logcat', '-d')))\n"
OLD_FAILURE = "            (OUT / 'gecko-pool-failure-log.txt').write_text(adb('logcat', '-d'))\n"
PERMISSION_IMPORT = 'from gecko.site_permission_evidence import permission_tap_command, verify_site_permission_evidence\n'
MAIN = 'def main():\n'
ADB = '    def adb(*parts, binary=False):\n'
LOG_DEF = '    def log():\n'
PERMISSION_REPORT = "            report['sitePermissionsGestures'] = permission_gestures\n"
EXCEPT = '        except BaseException:\n'
ADDITIONS = ((PERMISSION_IMPORT + IMPORT, PERMISSION_IMPORT),
             (FUNCTION + MAIN, MAIN), (CAPTURES + ADB, ADB),
             (LOG_DEF + LOG, LOG_DEF + OLD_LOG),
             (PERMISSION_REPORT + REPORT, PERMISSION_REPORT),
             (EXCEPT + FAILURE, EXCEPT + OLD_FAILURE))


def original_pool_runner(text):
    """Undo six exact producer changes; callers retain whole-runner hash checks."""
    for added, previous in ADDITIONS:
        if text.count(added) != 1:
            raise ValueError('Missing or repeated exact pool capture-privacy addition')
        text = text.replace(added, previous, 1)
    return text


def load_runner():
    spec = importlib.util.spec_from_file_location('pool_capture_privacy_runner', RUNNER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def service_text():
    return ('expressive_stickers_api_key=AIza' + 'g' * 35 + '\n'
            'https://location.services.mozilla.com/v1/country?key=' + 'm' * 36 + '&kept=1\n'
            'https://safebrowsing.googleapis.com/v5/hashLists:batchGet?key=AIza' + 's' * 35 + '&alt=json\n'
            'other-provider-setting=AIza' + 'u' * 35 + '\n')


class PoolCapturePrivacyTest(unittest.TestCase):
    def test_whole_original_runner_and_all_old_workload_bytes_survive(self):
        current = RUNNER.read_text()
        original = original_pool_runner(current)
        self.assertEqual(hashlib.sha256(original.encode()).hexdigest(), PREVIOUS_RUNNER_SHA256)
        for added, previous in ADDITIONS:
            with self.subTest(addition=added.splitlines()[0]), self.assertRaises(ValueError):
                original_pool_runner(current.replace(added, previous, 1))
        for old, new in [('240', '999'), ('time.sleep(1)', 'time.sleep(0)'),
                         ("verify(report, server)", 'pass'),
                         ('verify_site_permission_evidence(report', 'changed_permission_verifier(report')]:
            with self.subTest(mutation=old):
                modified = original_pool_runner(current.replace(old, new, 1))
                self.assertNotEqual(hashlib.sha256(modified.encode()).hexdigest(), PREVIOUS_RUNNER_SHA256)
        misplaced = current.replace(REPORT, '', 1).replace("            report['androidSdk']", REPORT + "            report['androidSdk']", 1)
        with self.assertRaises(ValueError):
            original_pool_runner(misplaced)

    def test_known_classes_and_escaped_values_use_existing_policy(self):
        module = load_runner()
        plain = service_text()
        forms = [plain, plain.replace('/', r'\/'),
                 plain.replace('AIza', r'\u0041\u0049\u007a\u0061'),
                 plain.replace('AIza', '%41%49%7A%61')]
        for value in forms:
            with self.subTest(form=forms.index(value)):
                final, metadata = module.capture_diagnostic_text(value)
                expected, marker = G.redact_service_api_keys(value)
                self.assertEqual((final, metadata), (expected, marker))
                self.assertTrue(G.verify_capture_privacy(metadata, final))
                self.assertEqual(G.service_api_key_findings(final), [])
                self.assertTrue(metadata['changed'])
                self.assertEqual(sum(metadata['replacements'].values()), 4)
                self.assertNotIn('m' * 36, json.dumps(metadata))

    def test_benign_bytes_and_uncovered_fields_are_not_rewritten(self):
        module = load_runner()
        value = '前🙂\r\nPocketGeckoPool {"kind":"report","value":{"status":"passed"}}\nproxyPassword=controlled;cookie=fixture\n'
        final, metadata = module.capture_diagnostic_text(value)
        self.assertEqual(final.encode(), value.encode())
        self.assertFalse(metadata['changed'])
        self.assertEqual(metadata['originalSha256'], metadata['finalSha256'])
        self.assertEqual(metadata['originalBytes'], len(value.encode()))

    def test_remaining_supported_key_or_malformed_marker_fails_closed(self):
        module = load_runner()
        final, metadata = G.redact_service_api_keys('benign')
        for changes in ({'finalSha256': '0' * 64}, {'changed': 1}, {'extra': True}):
            invalid = dict(metadata, **changes)
            with self.subTest(changes=tuple(changes)), patch.object(module, 'redact_service_api_keys', return_value=(final, invalid)), self.assertRaises(ValueError):
                module.capture_diagnostic_text('benign')
        # A counterfeit derivative with internally consistent hashes still must
        # fail if a supported key remains in the complete text.
        remaining = 'unknown-setting=AIza' + 'r' * 35
        forged = copy.deepcopy(metadata)
        forged.update(originalBytes=len(remaining.encode()), finalBytes=len(remaining.encode()),
                      originalSha256=hashlib.sha256(remaining.encode()).hexdigest(),
                      finalSha256=hashlib.sha256(remaining.encode()).hexdigest())
        with patch.object(module, 'redact_service_api_keys', return_value=(remaining, forged)), self.assertRaises(ValueError):
            module.capture_diagnostic_text(remaining)
        for invalid in (None, b'not text', '\ud800', 'x' * (G.PRIVACY_MAX_BYTES + 1)):
            with self.subTest(kind=type(invalid).__name__), self.assertRaises((ValueError, UnicodeEncodeError)):
                module.capture_diagnostic_text(invalid)

    def run_host_producer(self, failure=False):
        """Drive the real main() boundary with fake OS edges, not fake acceptance."""
        module = load_runner()
        raw = service_text()
        report = dict(status='passed', checks=[dict(pass_=True)] * 55, sitePermissions={})
        event = 'PocketGeckoPool {"kind":"report","value":{"status":"passed","checkCount":55}}\n'
        filtered = raw + ('FATAL EXCEPTION\n' if failure else event)
        commands, parsed_lines = [], []
        class Process:
            stdout = io.StringIO(json.dumps(dict(ready=True, port=9877, protocol='h2')) + '\n')
            stopped = False
            def terminate(self): self.stopped = True
            def communicate(self, timeout=None): return ('', '')
            def kill(self): self.stopped = True
        process = Process()
        def popen(parts, **kwargs):
            Path(parts[4]).write_text(json.dumps(dict(requests=[dict(path='/bytes')], webSockets=[dict(frames=1)])))
            return process
        def output(parts, **kwargs):
            if parts[:2] == ['git', 'rev-parse']:
                return '6cd3418f63cf3cb9c65bad102c2eafa525d693be\n'
            command = tuple(parts[3:]); commands.append(command)
            if command[:2] == ('logcat', '-d'):
                return filtered if len(command) > 2 else raw
            if command[:3] == ('exec-out', 'content', 'read'):
                return json.dumps(report)
            if command == ('shell', 'getprop', 'ro.build.version.sdk'):
                return '35\n'
            return ''
        tag = module.TAG_IN_LINE
        def checked_tag(line):
            self.assertEqual(G.service_api_key_findings(line), [])
            parsed_lines.append(line)
            return tag(line)
        with tempfile.TemporaryDirectory(prefix='pool-capture-boundary-') as temporary:
            out = Path(temporary) / 'out'
            with patch.object(module, 'OUT', out), patch.object(sys, 'argv', ['pool', '--adb', 'fake-adb']), \
                 patch.object(module.subprocess, 'run'), patch.object(module.subprocess, 'Popen', side_effect=popen), \
                 patch.object(module.subprocess, 'check_output', side_effect=output), \
                 patch.object(module.select, 'select', side_effect=lambda readers, *args: (readers, [], [])), \
                 patch.object(module, 'verify') as network_verify, patch.object(module, 'verify_site_permission_evidence', return_value={}), \
                 patch.object(module, 'TAG_IN_LINE', side_effect=checked_tag), patch.object(sys, 'stdout', io.StringIO()):
                if failure:
                    with self.assertRaises(AssertionError) as raised:
                        module.main()
                    self.assertEqual(G.service_api_key_findings(str(raised.exception)), [])
                    self.assertNotIn('m' * 36, str(raised.exception))
                    network_verify.assert_not_called()
                else:
                    module.main()
                    network_verify.assert_called_once()
            self.assertTrue(process.stopped)
            self.assertIn(('reverse', '--remove', 'tcp:9877'), commands)
            files = {p.name: p.read_text() for p in out.iterdir()}
            for name, value in files.items():
                self.assertEqual(G.service_api_key_findings(value), [], name)
                self.assertNotIn('m' * 36, value, name)
            self.assertNotIn('gecko-pool-capture-privacy.json', files)
            if failure:
                self.assertEqual(set(files), {'gecko-pool-failure-log.txt', 'gecko-pool-server-failure.json'})
                self.assertEqual(files['gecko-pool-failure-log.txt'], G.redact_service_api_keys(raw)[0])
            else:
                self.assertEqual(set(files), {'gecko-pool-results.json', 'gecko-pool-log.txt', 'site-permission-sdk-results.json'})
                self.assertTrue(parsed_lines)
                self.assertEqual(files['gecko-pool-log.txt'], G.redact_service_api_keys(filtered)[0])
                summary = json.loads(files['gecko-pool-results.json'])['capturePrivacy']
                self.assertEqual((summary['captureCount'], summary['changedCaptureCount']), (1, 1))
                self.assertTrue(G.verify_capture_privacy(summary['captures'][0], files['gecko-pool-log.txt']))

    def test_successful_capture_is_filtered_before_parser_and_storage(self):
        self.run_host_producer()

    def test_failure_capture_and_raised_diagnostic_are_filtered(self):
        self.run_host_producer(failure=True)


if __name__ == '__main__':
    unittest.main()
