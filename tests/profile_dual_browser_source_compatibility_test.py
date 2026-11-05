"""Historical source-oracle preservation; no Android or runtime acceptance."""
import ast
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import dual_browser_source_compatibility as dual

ROOT = Path(__file__).resolve().parents[1]
SHA = lambda raw: hashlib.sha256(raw).hexdigest()


def assertions(raw):
    return [ast.dump(node, include_attributes=False) for node in ast.walk(ast.parse(raw))
            if isinstance(node, ast.Assert) or isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute) and node.func.attr.startswith('assert')]


class DualBrowserSourceCompatibility(unittest.TestCase):
    rejected = 0

    def test_each_whole_inverse_and_forward_equal_the_actual_210_commit(self):
        self.assertEqual(subprocess.check_output(['git', 'rev-parse', dual.BASE_COMMIT + '^{tree}'], cwd=ROOT).decode().strip(), dual.BASE_TREE)
        for relative, row in dual.manifest()['files'].items():
            with self.subTest(path=relative):
                previous = subprocess.check_output(['git', 'show', dual.BASE_COMMIT + ':' + relative], cwd=ROOT)
                current = (ROOT / relative).read_bytes()
                from worker_timezone_source_compatibility import PATHS as worker_paths, source_input as worker_source_input
                if relative in worker_paths:
                    current = worker_source_input(current, relative)
                self.assertEqual((SHA(previous), len(previous)), (row['previousSha256'], row['previousBytes']))
                self.assertEqual((SHA(current), len(current)), (row['reviewedSha256'], row['reviewedBytes']))
                self.assertEqual(dual.source_input(previous, relative), previous)
                self.assertEqual(dual.source_input(current, relative), previous)
                forward = previous
                for delta in row['deltas']:
                    old, new = delta['previous'].encode(), delta['current'].encode()
                    self.assertEqual((SHA(old), SHA(new)), (delta['previousSha256'], delta['currentSha256']))
                    self.assertTrue(old and new and old != new)
                    self.assertEqual(forward.count(old), 1)
                    forward = forward.replace(old, new, 1)
                self.assertEqual(forward, current)

    def test_missing_duplicate_mutated_relocated_and_unknown_sources_are_rejected(self):
        rejected = 0
        for relative, row in dual.manifest()['files'].items():
            current = (ROOT / relative).read_bytes()
            from worker_timezone_source_compatibility import PATHS as worker_paths, source_input as worker_source_input
            if relative in worker_paths:
                current = worker_source_input(current, relative)
            for delta in row['deltas']:
                chunk = delta['current'].encode()
                self.assertEqual(current.count(chunk), 1)
                remaining = current.replace(chunk, b'', 1)
                moved = remaining + chunk
                if moved == current:
                    moved = chunk + remaining
                for candidate in (remaining, current.replace(chunk, chunk * 2, 1),
                                  current.replace(chunk, chunk + b' ', 1), moved):
                    with self.subTest(path=relative, delta=delta['id'], mutant=SHA(candidate)):
                        self.assertNotEqual(candidate, current)
                        with self.assertRaises(ValueError):
                            dual.source_input(candidate, relative)
                        rejected += 1
            for candidate in (current + b' ', b'unknown source', current[:80]):
                with self.assertRaises(ValueError):
                    dual.source_input(candidate, relative)
                rejected += 1
        self.assertEqual(rejected, sum(len(row['deltas']) * 4 + 3 for row in dual.manifest()['files'].values()))
        type(self).rejected = rejected

    def test_original_manifests_goldens_and_python_assertions_remain_complete(self):
        for relative in ('tests/fixtures/experience46-source-deltas.json', 'tests/fixtures/event-journal-source-deltas.json'):
            previous = subprocess.check_output(['git', 'show', dual.BASE_COMMIT + ':' + relative], cwd=ROOT)
            self.assertEqual((ROOT / relative).read_bytes(), previous)
        for relative in sorted(path for path in dual.PATHS if path.endswith('.py')):
            previous = subprocess.check_output(['git', 'show', dual.BASE_COMMIT + ':' + relative], cwd=ROOT)
            current = (ROOT / relative).read_bytes()
            self.assertEqual(assertions(current), assertions(previous), relative)
            self.assertEqual(dual.source_input(current, relative), previous)
        # Only these historical methods see a source view. Removing each exact
        # local import/read hook restores the full original Python file, so the
        # actual callback/native/readers and all old negative controls stay raw.
        ports = (
            ('tests/profile_fingerprint_local_supplement_test.py',
             "        from dual_browser_source_compatibility import source_input\n",
             "        original = inverse_activity(source_input(JAVA.read_bytes(), 'tests/gecko/FingerprintFollowupIntegrationActivity.java').decode('utf-8'))",
             '        original = inverse_activity(JAVA.read_text())'),
            ('tests/profile_manual_snapshot_diagnostic_test.py',
             "  from dual_browser_source_compatibility import source_input\n",
             "  source=source_input(FIXTURE.read_bytes(),'tests/gecko/GeckoPerformanceIntegrationActivity.java').decode('utf-8')",
             '  source=FIXTURE.read_text()'),
        )
        for relative, import_line, new_read, old_read in ports:
            current = (ROOT / relative).read_bytes()
            previous = subprocess.check_output(['git', 'show', dual.BASE_COMMIT + ':' + relative], cwd=ROOT)
            self.assertEqual(assertions(current), assertions(previous), relative)
            self.assertEqual(current.count(import_line.encode()), 1)
            self.assertEqual(current.count(new_read.encode()), 1)
            normalized = current.replace(import_line.encode(), b'', 1).replace(new_read.encode(), old_read.encode(), 1)
            self.assertEqual(normalized, previous, relative)
        import experience46_source_compatibility as experience
        import event_journal_source_compatibility as journal
        self.assertEqual(SHA((ROOT / 'tests/fixtures/experience46-source-deltas.json').read_bytes()), experience.DELTA_SHA256)
        self.assertEqual(SHA((ROOT / 'tests/fixtures/event-journal-source-deltas.json').read_bytes()), journal.DELTA_SHA256)
        for relative in ('app/src/main/java/local/pocketchat/ChatSession.java', 'app/src/main/java/local/pocketchat/GeckoWebView.java', 'tests/gecko/GeckoIntegrationTestActivity.java'):
            current = (ROOT / relative).read_bytes()
            previous = dual.source_input(current, relative)
            self.assertEqual(experience.experience46_source_bytes(current, relative), experience.experience46_source_bytes(previous, relative))

    def test_types_paths_excerpts_and_changed_fixture_cannot_be_whitelisted(self):
        relative = 'app/src/main/java/local/pocketchat/ChatSession.java'
        current = (ROOT / relative).read_bytes()
        for path in (relative + '.other', '../' + relative, '/' + relative, Path(relative), None):
            with self.subTest(path=path), self.assertRaises(ValueError):
                dual.source_input(current, path)
        for value in (current.decode(), bytearray(current), None):
            with self.assertRaises(ValueError):
                dual.source_input(value, relative)
        with tempfile.TemporaryDirectory(prefix='dual-browser-inverse-negative-') as directory:
            path = Path(directory) / 'deltas.json'
            path.write_bytes(dual.DELTA_PATH.read_bytes() + b' ')
            with patch.object(dual, 'DELTA_PATH', path), self.assertRaises(ValueError):
                dual.source_input(current, relative)

    def test_native_protection_and_site_predicate_drift_is_rejected(self):
        targets = (
            ('app/src/main/java/local/pocketchat/GeckoWebView.java',
             'return nativeProtection.allows(owner.privacy.level());', 'return true;'),
            ('app/src/main/java/local/pocketchat/ChatSession.java',
             'if(!driverTargetCurrent(target)||capture&&!replyObservationAllowed())', 'if(false)'),
        )
        for relative, old, new in targets:
            current = (ROOT / relative).read_bytes()
            from cpu_source_compatibility import source_input as cpu_source_input
            current = cpu_source_input(current, relative)
            self.assertIn(old.encode(), current)
            with self.assertRaises(ValueError):
                dual.source_input(current.replace(old.encode(), new.encode(), 1), relative)

    def test_java_policy_dependency_history_is_exact_and_keeps_behavior_tests_current(self):
        import gecko_policy_dependency_source_compatibility as dependency
        from worker_timezone_host_source_compatibility import PATHS as host_adapter_paths, source_input as host_adapter_source_input
        for relative, row in dependency.manifest()['files'].items():
            with self.subTest(path=relative):
                previous = subprocess.check_output(['git', 'show', dependency.BASE_COMMIT + ':' + relative], cwd=ROOT)
                current = (ROOT / relative).read_bytes()
                from cpu_source_compatibility import source_input as cpu_source_input
                if relative == 'tests/profile_native_protection_test.py':
                    current = cpu_source_input(current, relative)
                if relative in host_adapter_paths:
                    current = host_adapter_source_input(current, relative)
                self.assertEqual((SHA(previous), len(previous)), (row['previousSha256'], row['previousBytes']))
                self.assertEqual((SHA(current), len(current)), (row['reviewedSha256'], row['reviewedBytes']))
                self.assertEqual(dependency.source_input(current, relative), previous)
                self.assertEqual(dependency.source_input(previous, relative), previous)
                forward = previous
                for delta in row['deltas']:
                    before, after = delta['previous'].encode(), delta['current'].encode()
                    self.assertEqual(forward.count(before), 1)
                    forward = forward.replace(before, after, 1)
                self.assertEqual(forward, current)
        for relative in ('tests/profile_native_protection_test.py', 'tests/profile_page_bridge_lifecycle_test.py'):
            current = (ROOT / relative).read_bytes()
            from cpu_source_compatibility import source_input as cpu_source_input
            if relative == 'tests/profile_native_protection_test.py':
                current = cpu_source_input(current, relative)
            if relative in host_adapter_paths:
                current = host_adapter_source_input(current, relative)
            previous = subprocess.check_output(['git', 'show', dependency.BASE_COMMIT + ':' + relative], cwd=ROOT)
            self.assertEqual(assertions(current), assertions(previous))
            tree = ast.parse(current)
            old_tree = ast.parse(previous)
            for node in (n for n in ast.walk(old_tree) if isinstance(n, ast.FunctionDef) and n.name.startswith('test_')):
                now = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == node.name)
                self.assertEqual(ast.get_source_segment(current.decode(), now), ast.get_source_segment(previous.decode(), node))
            self.assertNotIn('gecko_policy_dependency_source_compatibility', current.decode())
            self.assertIn('GeckoNavigationPolicy.java', current.decode())
            self.assertIn('BrowserAddressPolicy.java', current.decode())

    def test_java_policy_dependency_sources_reject_all_unknown_contexts(self):
        import gecko_policy_dependency_source_compatibility as dependency
        rejected = 0
        for relative, row in dependency.manifest()['files'].items():
            current = (ROOT / relative).read_bytes()
            for delta in row['deltas']:
                chunk = delta['current'].encode()
                self.assertEqual(current.count(chunk), 1)
                remainder = current.replace(chunk, b'', 1)
                moved = remainder + chunk
                if moved == current:
                    moved = chunk + remainder
                for candidate in (remainder, current.replace(chunk, chunk * 2, 1),
                                  current.replace(chunk, chunk + b' ', 1), moved):
                    self.assertNotEqual(candidate, current)
                    with self.assertRaises(ValueError):
                        dependency.source_input(candidate, relative)
                    rejected += 1
            for candidate in (current + b' ', current[:100], b'unknown source'):
                with self.assertRaises(ValueError):
                    dependency.source_input(candidate, relative)
                rejected += 1
        self.assertEqual(rejected, sum(4 * len(r['deltas']) + 3 for r in dependency.manifest()['files'].values()))
        type(self).dependency_rejected = rejected
        current = (ROOT / 'tests/profile_page_bridge_lifecycle_test.py').read_bytes()
        for relative in ('../tests/profile_page_bridge_lifecycle_test.py', '/tests/profile_page_bridge_lifecycle_test.py',
                         'tests/profile_native_protection_test.py', Path('tests/profile_page_bridge_lifecycle_test.py'), None):
            with self.assertRaises(ValueError):
                dependency.source_input(current, relative)
        for raw in (current.decode(), bytearray(current), None):
            with self.assertRaises(ValueError):
                dependency.source_input(raw, 'tests/profile_page_bridge_lifecycle_test.py')
        with tempfile.TemporaryDirectory(prefix='policy-dependency-fixture-negative-') as directory:
            path = Path(directory) / 'changed.json'
            path.write_bytes(dependency.DELTA_PATH.read_bytes() + b' ')
            with patch.object(dependency, 'DELTA_PATH', path), self.assertRaises(ValueError):
                dependency.source_input(current, 'tests/profile_page_bridge_lifecycle_test.py')

    def test_only_exact_historical_dependency_input_hooks_precede_the_old_goldens(self):
        import gecko_policy_dependency_source_compatibility as dependency
        ports = (
            ('tests/profile_native43_source_compatibility_test.py',
             "source_input((ROOT / relative).read_bytes(),relative) if relative=='tests/profile_page_bridge_lifecycle_test.py' else (ROOT / relative).read_bytes()",
             '(ROOT / relative).read_bytes()'),
            ('tests/profile_original_history12_test.py',
             "source_input((ROOT / path).read_bytes(),path) if path=='tests/profile_native43_source_compatibility_test.py' else (ROOT / path).read_bytes()",
             '(ROOT / path).read_bytes()'),
        )
        import_line = '        from gecko_policy_dependency_source_compatibility import source_input\n'
        for relative, new_read, old_read in ports:
            current = (ROOT / relative).read_bytes()
            previous = subprocess.check_output(['git', 'show', dependency.BASE_COMMIT + ':' + relative], cwd=ROOT)
            self.assertEqual(current.count(import_line.encode()), 1)
            self.assertEqual(current.count(new_read.encode()), 1)
            normalized = current.replace(import_line.encode(), b'', 1).replace(new_read.encode(), old_read.encode(), 1)
            self.assertEqual(normalized, previous)
            self.assertEqual(assertions(normalized), assertions(previous))
        allowed = {'tests/profile_native43_source_compatibility_test.py',
                   'tests/profile_original_history12_test.py', 'tests/experience46_source_compatibility.py',
                   'tests/profile_experience46_source_compatibility_test.py',
                   'tests/profile_dual_browser_source_compatibility_test.py'}
        for folder in ('tests', 'tools'):
            for path in (ROOT / folder).rglob('*.py'):
                tree = ast.parse(path.read_text())
                imported = any(isinstance(n, ast.ImportFrom) and n.module == 'gecko_policy_dependency_source_compatibility'
                               or isinstance(n, ast.Import) and any(a.name == 'gecko_policy_dependency_source_compatibility' for a in n.names)
                               for n in ast.walk(tree))
                if imported:
                    self.assertIn(path.relative_to(ROOT).as_posix(), allowed)

    def test_behavior_hosts_still_compile_and_execute_actual_current_sources(self):
        paths = (
            'tests/gecko-navigation-host/run.py', 'tests/gecko-navigation-host/DriverHost.java.in',
            'tests/gecko-navigation-host/route_hold.py', 'tests/experience46-guards-host/run.py',
            'tests/gecko-navigation-host/session_navigation.py', 'tests/gecko-navigation-host/client_ready.py',
            'tests/generic-download-source-host/run.py', 'tests/runtime-origin-adapter-host/run.py',
            'tests/chromium-fingerprint-store-host/run.py', 'tests/chromium-fingerprint-host/run.py',
            'tests/profile_resource_retained_fixture_test.py', 'tests/profile_resource_async_test.py',
            'tests/profile_queued_document_observation46_test.py', 'tests/browser-runtime/gecko-site-boundary.test.cjs',
        )
        for relative in paths:
            source = (ROOT / relative).read_text()
            self.assertNotIn('dual_browser_source_compatibility', source, relative)
            self.assertNotIn('experience46_source_bytes', source, relative)
            self.assertNotIn('event_journal_source_compatibility', source, relative)
        allowed = {path for path in dual.PATHS if path.endswith('.py')} | {
            'tests/profile_cpu_source_compatibility_test.py',
            'tests/profile_worker_timezone_source_compatibility_test.py',
            'tests/profile_dual_browser_source_compatibility_test.py',
            'tests/profile_fingerprint_local_supplement_test.py',
            'tests/profile_manual_snapshot_diagnostic_test.py'}
        for folder in ('tests', 'tools'):
            for path in (ROOT / folder).rglob('*.py'):
                source = path.read_text()
                if 'dual_browser_source_compatibility' not in source:
                    continue
                imported = any(isinstance(node, ast.Import) and any(alias.name == 'dual_browser_source_compatibility' for alias in node.names)
                               or isinstance(node, ast.ImportFrom) and (node.module == 'dual_browser_source_compatibility'
                                  or any(alias.name == 'dual_browser_source_compatibility' for alias in node.names))
                               for node in ast.walk(ast.parse(source)))
                if imported:
                    self.assertIn(path.relative_to(ROOT).as_posix(), allowed,
                                  'Only the explicitly reviewed historical oracle ports may import this source view')


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(DualBrowserSourceCompatibility)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    output = os.environ.get('DUAL_BROWSER_SOURCE_REPORT')
    if output:
        manifest = dual.manifest()
        report = dict(status='passed' if result.wasSuccessful() else 'failed', tests=result.testsRun,
                      baseCommit=dual.BASE_COMMIT, baseTree=dual.BASE_TREE, manifestSha256=dual.DELTA_SHA256,
                      rows=len(manifest['files']), contextualDeltas=sum(len(row['deltas']) for row in manifest['files'].values()),
                      rejectedSourceMutants=DualBrowserSourceCompatibility.rejected,
                      policyDependencyRows=2, policyDependencyRejectedMutants=getattr(DualBrowserSourceCompatibility, 'dependency_rejected', 0),
                      actualAndroidExecution=False, runtimeAcceptance=False,
                      scope='Exact historical source-input inversion and original oracle preservation only; actual behavior hosts execute current source.')
        path = Path(output);path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2) + '\n')
    raise SystemExit(0 if result.wasSuccessful() else 1)
