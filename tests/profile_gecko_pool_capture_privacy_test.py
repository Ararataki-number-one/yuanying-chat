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
import traceback
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
REPORT_EXPORT_IMPORTS = 'from gecko.caret_ime_guard import assert_public_diagnostic_text\nfrom gecko.diagnostic_capture_privacy import safe_error_text\n'
REPORT_EXPORT_FUNCTION = 'def write_diagnostic_report(path, value):\n    """Export a verified JSON derivative without replacing the workload oracle."""\n    if not isinstance(value, dict) or \'reportCapturePrivacy\' in value:\n        raise ValueError(\'Diagnostic report privacy: primary metadata collision\')\n    normalized = json.dumps(value, indent=2) + \'\\n\'\n    sanitized, metadata = capture_diagnostic_text(normalized)\n    public = json.loads(sanitized)\n    public[\'reportCapturePrivacy\'] = dict(schema=1,\n        scope=\'Normalized complete report JSON excluding reportCapturePrivacy itself; known service API-key value derivative. Workload verification uses the original structured object.\',\n        capture=metadata)\n    final = json.dumps(public, indent=2) + \'\\n\'\n    assert_public_diagnostic_text(path, final.encode(\'utf-8\'))\n    path.write_text(final, encoding=\'utf-8\')\n\n\n'
CURRENT_FAILURE_BLOCK = "        except BaseException as error:\n            try:\n                (OUT / 'gecko-pool-failure-log.txt').write_text(capture_text(adb('logcat', '-d')))\n                if (directory / 'server.json').exists():\n                    (OUT / 'gecko-pool-server-failure.json').write_bytes((directory / 'server.json').read_bytes())\n            except Exception:\n                pass  # Secondary capture cannot replace or disclose the primary failure.\n            message = safe_error_text(error, use_repr=False)\n            if message != str(error):\n                raise RuntimeError(type(error).__name__ + ': ' + message) from None\n            raise\n"
LEGACY_FAILURE_BLOCK = "        except BaseException:\n            (OUT / 'gecko-pool-failure-log.txt').write_text(adb('logcat', '-d'))\n            if (directory / 'server.json').exists():\n                (OUT / 'gecko-pool-server-failure.json').write_bytes((directory / 'server.json').read_bytes())\n            raise\n"
CURRENT_REPORT_WRITE = "            write_diagnostic_report(OUT / 'gecko-pool-results.json', report)\n"
PREVIOUS_REPORT_WRITE = "            (OUT / 'gecko-pool-results.json').write_text(json.dumps(report, indent=2) + '\\n')\n"
CURRENT_PERMISSION_WRITE = "            write_diagnostic_report(OUT / 'site-permission-sdk-results.json', dict(evidence=report['sitePermissions'], gestures=permission_gestures,\n                                                                             verification=permission_result,\n                                                                             sourceCommit=report['sourceCommit']))\n"
PREVIOUS_PERMISSION_WRITE = "            (OUT / 'site-permission-sdk-results.json').write_text(json.dumps(dict(evidence=report['sitePermissions'], gestures=permission_gestures,\n                                                                             verification=permission_result,\n                                                                             sourceCommit=report['sourceCommit']), indent=2) + '\\n')\n"
ADDITIONS = ((PERMISSION_IMPORT + IMPORT + REPORT_EXPORT_IMPORTS, PERMISSION_IMPORT),
             (REPORT_EXPORT_FUNCTION + FUNCTION + MAIN, MAIN), (CAPTURES + ADB, ADB),
             (LOG_DEF + LOG, LOG_DEF + OLD_LOG),
             (PERMISSION_REPORT + REPORT, PERMISSION_REPORT),
             (CURRENT_FAILURE_BLOCK, LEGACY_FAILURE_BLOCK),
             (CURRENT_REPORT_WRITE, PREVIOUS_REPORT_WRITE),
             (CURRENT_PERMISSION_WRITE, PREVIOUS_PERMISSION_WRITE))


def original_pool_runner(text):
    """Undo exact producer-only privacy changes; retain the complete original runner hash."""
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


SOURCE = '79b9f31534aed26446e1e8f7368b1ec825bbcd50'
RUNNER = ROOT / 'tests/gecko/run_gecko_pool.py'
NODE_BYTES = b'{"requests":[{"path":"/bytes"}],"webSockets":[{"frames":1}]}\n'


def generated_values():
    return (
        'https://location.services.mozilla.com/v1/country?key=' + 'm' * 36 + '&kept=1',
        'https://safebrowsing.googleapis.com/v5/hashLists:batchGet?key=AIza' + 's' * 35 + '&alt=json',
        'other-provider-setting=AIza' + 'u' * 35,
        'expressive_stickers_api_key=AIza' + 'g' * 35,
    )


def provider_report(diagnostic='controlled benign 前🙂'):
    return dict(status='passed', checks=[dict(name='controlled', **{'pass': True})] * 55,
                routes=[dict(url=diagnostic, route=dict(type='socks', host='127.0.0.1', port=9090))],
                sitePermissions=dict(nestedDiagnostic=diagnostic, nonce='b' * 32, sendCount=0,
                                     sameDocument=True, durationMs=4.25),
                sourceTree='a' * 40, runId='41005249174', runAttempt=1,
                sdkReceiptSha256='e' * 64, integrationApkSha256='f' * 64,
                nonce='c' * 32, pid=3121, port=9090, ready=True, durationMs=2.5,
                unrelated='proxyPassword=controlled;cookie=fixture')


class PoolReportCapturePrivacyTest(unittest.TestCase):
    def drive(self, provider, raw_provider=None, fail_verifier=False,
              failure_capture_refuses=False, counterfeit_final_serialization=False):
        module = load_runner()
        serialized = json.dumps(provider) if raw_provider is None else raw_provider
        event = 'PocketGeckoPool ' + json.dumps(dict(kind='report', value=dict(
            status=provider['status'], checkCount=len(provider['checks'])))) + '\n'
        filtered = event
        commands, verified, permission_verified = [], [], []
        class Process:
            stdout = io.StringIO(json.dumps(dict(ready=True, port=9877, protocol='h2')) + '\n')
            stopped = False
            def terminate(self): self.stopped = True
            def communicate(self, timeout=None): return ('', '')
            def kill(self): self.stopped = True
        process = Process()
        def popen(parts, **kwargs):
            Path(parts[4]).write_bytes(NODE_BYTES)
            return process
        def output(parts, **kwargs):
            if parts[:2] == ['git', 'rev-parse']:
                return SOURCE + '\n'
            command = tuple(parts[3:]); commands.append(command)
            if command[:2] == ('logcat', '-d'):
                return filtered if len(command) > 2 else 'controlled-failure-capture\n'
            if command[:3] == ('exec-out', 'content', 'read'):
                return serialized
            if command == ('shell', 'getprop', 'ro.build.version.sdk'):
                return '35\n'
            return ''
        actual_verify = module.verify
        def verify(report, server):
            verified.append(copy.deepcopy(report))
            if fail_verifier:
                # The production verifier's first failed-status assertion uses
                # the original provider's error value as its exception message.
                return actual_verify(report, server)
        def permission_verify(report, gestures):
            permission_verified.append(copy.deepcopy(report))
            return dict(hostBoundaryStub=True)
        real_capture = module.capture_diagnostic_text
        def capture(value):
            if failure_capture_refuses and value == 'controlled-failure-capture\n':
                raise ValueError('controlled diagnostic capture refusal')
            return real_capture(value)
        original_dumps = json.dumps
        def dumps(value, *args, **kwargs):
            if counterfeit_final_serialization and isinstance(value, dict) and 'reportCapturePrivacy' in value:
                value = dict(value, diagnosticFault=generated_values()[2])
            return original_dumps(value, *args, **kwargs)
        with tempfile.TemporaryDirectory(prefix='pool-report-boundary-') as temporary:
            out = Path(temporary) / 'out'; caught = None
            with patch.object(module, 'OUT', out), patch.object(sys, 'argv', ['pool', '--adb', 'fake-adb']), \
                 patch.object(module.subprocess, 'run'), patch.object(module.subprocess, 'Popen', side_effect=popen), \
                 patch.object(module.subprocess, 'check_output', side_effect=output), \
                 patch.object(module.select, 'select', side_effect=lambda readers, *args: (readers, [], [])), \
                 patch.object(module, 'verify', side_effect=verify), \
                 patch.object(module, 'verify_site_permission_evidence', side_effect=permission_verify), \
                 patch.object(module, 'capture_diagnostic_text', side_effect=capture), \
                 patch.object(module.json, 'dumps', side_effect=dumps), patch.object(sys, 'stdout', io.StringIO()):
                try:
                    module.main()
                except BaseException as error:
                    caught = error
            files = {p.name: p.read_bytes() for p in out.iterdir()}
        self.assertTrue(process.stopped)
        self.assertIn(('reverse', '--remove', 'tcp:9877'), commands)
        return dict(files=files, error=caught, verified=verified,
                    permissionVerified=permission_verified, rawProvider=serialized)

    def assert_export(self, raw):
        G.assert_public_diagnostic_text(Path('export.json'), raw)
        value = json.loads(raw)
        metadata = value.pop('reportCapturePrivacy')
        self.assertEqual(metadata['schema'], 1)
        self.assertIn('excluding reportCapturePrivacy', metadata['scope'])
        normalized = json.dumps(value, indent=2) + '\n'
        self.assertTrue(G.verify_capture_privacy(metadata['capture'], normalized))
        return value, metadata

    def test_generated_provider_values_are_filtered_in_both_real_exports(self):
        for diagnostic in generated_values():
            with self.subTest(kind=G.service_api_key_findings(diagnostic)[0]['kind']):
                provider = provider_report(diagnostic)
                result = self.drive(provider)
                self.assertIsNone(result['error'])
                for name in ('gecko-pool-results.json', 'site-permission-sdk-results.json'):
                    value, metadata = self.assert_export(result['files'][name])
                    self.assertTrue(metadata['capture']['changed'])
                # Publication projection never becomes the workload oracle.
                self.assertEqual(result['verified'][0]['routes'], provider['routes'])
                self.assertEqual(result['permissionVerified'][0], provider['sitePermissions'])

    def test_provider_json_unicode_and_slash_escaping_cannot_bypass_exports(self):
        provider = provider_report(generated_values()[1])
        plain = json.dumps(provider)
        forms = [plain.replace('/', r'\/'), plain.replace('AIza', r'\u0041\u0049\u007a\u0061')]
        for raw in forms:
            with self.subTest(form=forms.index(raw)):
                self.assertEqual(json.loads(raw), provider)
                result = self.drive(provider, raw_provider=raw)
                self.assertIsNone(result['error'])
                self.assert_export(result['files']['gecko-pool-results.json'])
                self.assert_export(result['files']['site-permission-sdk-results.json'])

    def test_benign_structured_values_and_original_verifier_arguments_are_exact(self):
        provider = provider_report()
        result = self.drive(provider)
        self.assertIsNone(result['error'])
        value, metadata = self.assert_export(result['files']['gecko-pool-results.json'])
        self.assertFalse(metadata['capture']['changed'])
        self.assertEqual(metadata['capture']['originalSha256'], metadata['capture']['finalSha256'])
        for key, original in provider.items():
            self.assertEqual(value[key], original, key)
            self.assertEqual(result['verified'][0][key], original, key)
        self.assertEqual(value['sourceCommit'], SOURCE)
        permission, marker = self.assert_export(result['files']['site-permission-sdk-results.json'])
        self.assertEqual(permission['evidence'], provider['sitePermissions'])
        self.assertFalse(marker['capture']['changed'])

    def test_final_serialized_bytes_are_gated_before_public_file_write(self):
        result = self.drive(provider_report(), counterfeit_final_serialization=True)
        self.assertIsInstance(result['error'], ValueError)
        self.assertNotIn('gecko-pool-results.json', result['files'])
        self.assertEqual(result['verified'], [])

    def test_existing_projection_field_cannot_be_overwritten_as_metadata(self):
        provider = provider_report(); provider['reportCapturePrivacy'] = dict(primaryEvidence='must not be lost')
        result = self.drive(provider)
        self.assertIsInstance(result['error'], ValueError)
        self.assertNotIn('gecko-pool-results.json', result['files'])

    def test_raw_provider_failure_remains_failure_without_public_key_text(self):
        provider = provider_report(); provider.update(status='failed', error=generated_values()[0])
        result = self.drive(provider, fail_verifier=True)
        self.assertIsNotNone(result['error'])
        displayed = ''.join(traceback.format_exception(result['error']))
        self.assertEqual(G.service_api_key_findings(displayed), [])
        self.assertIn('AssertionError', displayed)
        self.assertEqual(result['verified'][0]['error'], provider['error'])
        self.assertEqual(result['files']['gecko-pool-server-failure.json'], NODE_BYTES)
        self.assert_export(result['files']['gecko-pool-results.json'])

    def test_secondary_capture_failure_cannot_reveal_primary_provider_error(self):
        provider = provider_report(); provider.update(status='failed', error=generated_values()[1])
        result = self.drive(provider, fail_verifier=True, failure_capture_refuses=True)
        self.assertIsNotNone(result['error'])
        displayed = ''.join(traceback.format_exception(result['error']))
        self.assertEqual(G.service_api_key_findings(displayed), [])
        self.assertIn('AssertionError', displayed)


if __name__ == '__main__':
    unittest.main()
