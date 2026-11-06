"""Finite outer historical source inputs, never runtime/browser qualification."""
import ast
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import ip_timezone_source_compatibility as overlay

import cpu_source_compatibility as _cpu_history

ROOT = Path(__file__).resolve().parents[1]
SHA = lambda raw: hashlib.sha256(raw).hexdigest()
IP_HOOK = """    if (digest, len(raw)) not in ((row['previousSha256'], row['previousBytes']),
                                  (row['reviewedSha256'], row['reviewedBytes'])):
        from ip_timezone_source_compatibility import PATHS as ip_paths, source_input as ip_source_input
        if relative in ip_paths:
            raw = ip_source_input(raw, relative)
            digest = _sha(raw)
"""
READ_IMPORT = b'from ip_timezone_source_compatibility import historical_read\n'


def git(*parts):
    return subprocess.check_output(['git', '--no-replace-objects', *parts], cwd=ROOT,
                                   env=dict(os.environ, GIT_NO_LAZY_FETCH='1'))


def assertions(raw):
    return [ast.dump(node, include_attributes=False) for node in ast.walk(ast.parse(raw))
            if isinstance(node, ast.Assert) or isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute) and node.func.attr.startswith('assert')]


class IpTimezoneHistoricalSources(unittest.TestCase):
    source_negatives = 0
    guard_negatives = 0
    fixture_negatives = 0

    def test_per_row_real_public_commits_full_forward_and_inverse(self):
        from pure212_ci_source_compatibility import metadata_input as reviewed_ci_input
        value = overlay.manifest()
        self.assertEqual(len(value['files']), 7)
        self.assertEqual(sum(len(row['deltas']) for row in value['files'].values()), 42)
        for relative, row in value['files'].items():
            with self.subTest(path=relative):
                self.assertEqual(git('rev-parse', row['previousCommit'] + '^{tree}').decode().strip(), row['previousTree'])
                before = git('show', row['previousCommit'] + ':' + relative)
                after = reviewed_ci_input(_cpu_history.metadata_input((ROOT / relative).read_bytes(), relative), relative)
                self.assertEqual((SHA(before), len(before)), (row['previousSha256'], row['previousBytes']))
                self.assertEqual((SHA(after), len(after)), (row['reviewedSha256'], row['reviewedBytes']))
                self.assertEqual(overlay.source_input(before, relative), before)
                self.assertEqual(overlay.source_input(after, relative), before)
                forward = before
                for delta in row['deltas']:
                    previous, current = delta['previous'].encode(), delta['current'].encode()
                    self.assertEqual((SHA(previous), SHA(current)), (delta['previousSha256'], delta['currentSha256']))
                    self.assertEqual(forward.count(previous), 1)
                    forward = forward.replace(previous, current, 1)
                self.assertEqual(forward, after)

    def test_missing_duplicate_mutated_moved_truncated_unknown_complete_images_reject(self):
        from pure212_ci_source_compatibility import metadata_input as reviewed_ci_input
        rejected = 0
        for relative, row in overlay.manifest()['files'].items():
            current = reviewed_ci_input(_cpu_history.metadata_input((ROOT / relative).read_bytes(), relative), relative)
            for delta in row['deltas']:
                chunk = delta['current'].encode()
                self.assertEqual(current.count(chunk), 1)
                remainder = current.replace(chunk, b'', 1)
                moved = remainder + chunk
                if moved == current:
                    moved = chunk + remainder
                for candidate in (remainder, current.replace(chunk, chunk * 2, 1), current.replace(chunk, chunk + b' ', 1), moved):
                    with self.subTest(path=relative, context=delta['id'], mutation=SHA(candidate)):
                        self.assertNotEqual(candidate, current)
                        with self.assertRaises(ValueError):
                            overlay.source_input(candidate, relative)
                        rejected += 1
            for candidate in (current[:100], current + b' ', b'unknown complete source'):
                with self.assertRaises(ValueError):
                    overlay.source_input(candidate, relative)
                rejected += 1
        self.assertEqual(rejected, 189)
        type(self).source_negatives = rejected

    def test_current_ip_guards_and_native_route_extraction_cannot_be_normalized_away(self):
        view = 'app/src/main/java/local/pocketchat/GeckoWebView.java'
        cases = (
            (view, '&&claim.stamp.equals(ipRouteStamp())', ''),
            (view, '&&owner.timeZone.status().optLong("desiredRevision",-1)==claim.revision', ''),
            (view, 'if(!gate.ready&&ipLookup!=null&&ipLookup.session==session&&ipLookup.gate==gate)cancelIpLookup();', ''),
            (view, '&&identityRequestAllowed(target)&&allowedUrl(target);', ';'),
            (view, 'if(!retryFailedIpNavigation(target))return;', ''),
            (view, 'if(!owner.timeZone.popupAllowed()){blockedPopups.offer(s,target);return GeckoResult.fromValue(null);}', 'if(false){blockedPopups.offer(s,target);return GeckoResult.fromValue(null);}'),
            ('tests/profile_native_protection_test.py', "        '__PROTECTED_ROUTE__':member(source,'JSONObject protectedNetworkRoute(String target)'),\n", ''),
        )
        for relative, before, after in cases:
            raw = _cpu_history.metadata_input((ROOT / relative).read_bytes(), relative)
            self.assertEqual(raw.count(before.encode()), 1, before)
            with self.assertRaises(ValueError):
                overlay.source_input(raw.replace(before.encode(), after.encode(), 1), relative)
        type(self).guard_negatives = len(cases)

    def test_source_types_paths_and_whole_identity_precede_context_access(self):
        relative = 'app/src/main/java/local/pocketchat/GeckoWebView.java'
        raw = _cpu_history.metadata_input((ROOT / relative).read_bytes(), relative)
        for value in (None, raw.decode(), bytearray(raw), memoryview(raw)):
            with self.assertRaises(ValueError):
                overlay.source_input(value, relative)
        for path in (None, Path(relative), '/' + relative, '../' + relative, relative + '.foreign', 'app/src/main/java/local/pocketchat/ChatSession.java'):
            with self.assertRaises(ValueError):
                overlay.source_input(raw, path)
        class Forbidden:
            def encode(self, *args):
                raise AssertionError('Unknown whole source reached context inversion')
        counterfeit = copy.deepcopy(overlay.manifest())
        counterfeit['files'][relative]['deltas'][0]['current'] = Forbidden()
        with patch.object(overlay, 'manifest', return_value=counterfeit), self.assertRaisesRegex(ValueError, 'unknown whole source'):
            overlay.source_input(raw + b' ', relative)

    def test_fixture_pins_row_predecessors_types_and_finite_bounds_are_not_mutable(self):
        original = overlay.manifest()
        relative = 'app/src/main/java/local/pocketchat/GeckoWebView.java'
        variants = []
        for key, value in (('schema', True), ('kind', 'runtime-acceptance'), ('actualAndroidExecution', True), ('runtimeAcceptance', True)):
            changed = copy.deepcopy(original); changed[key] = value; variants.append(changed)
        for key, value in (('previousCommit', overlay.PORTS_BEFORE), ('previousTree', overlay.PORTS_TREE), ('previousBytes', True), ('reviewedBytes', 0), ('reviewedBytes', overlay.MAX_SOURCE_BYTES + 1), ('reviewedSha256', 'not-a-hash'), ('contextLines', 2), ('contextLines', 17), ('deltas', []), ('deltas', [copy.deepcopy(original['files'][relative]['deltas'][0])] * 65)):
            changed = copy.deepcopy(original); changed['files'][relative][key] = value; variants.append(changed)
        port = next(iter(overlay.PORT_PATHS))
        changed = copy.deepcopy(original); changed['files'][port]['previousCommit'] = overlay.PRODUCTION_BEFORE; variants.append(changed)
        changed = copy.deepcopy(original); changed['files'][relative]['reviewedSha256'] = changed['files'][relative]['previousSha256']; variants.append(changed)
        for key, value in (('id', 'context-99'), ('previous', ''), ('current', 'x' * (32 * 1024 + 1)), ('currentSha256', '0' * 64)):
            changed = copy.deepcopy(original); changed['files'][relative]['deltas'][0][key] = value; variants.append(changed)
        changed = copy.deepcopy(original); changed['files'].pop(relative); variants.append(changed)
        changed = copy.deepcopy(original); changed['files']['tests/foreign.py'] = changed['files'][relative]; variants.append(changed)
        changed = copy.deepcopy(original); changed['unknownField'] = True; variants.append(changed)
        with tempfile.TemporaryDirectory(prefix='ip-historical-fixture-negative-') as folder:
            path = Path(folder) / 'counterfeit.json'
            path.write_bytes(overlay.DELTA_PATH.read_bytes() + b' ')
            with patch.object(overlay, 'DELTA_PATH', path), self.assertRaises(ValueError):
                overlay.manifest()
            malformed = [b'{"schema":1,"schema":1}', b'{"schema":NaN}']
            candidates = [(json.dumps(value) + '\n').encode() for value in ([], True, *variants)] + malformed
            for raw in candidates:
                path.write_bytes(raw)
                with patch.object(overlay, 'DELTA_PATH', path), patch.object(overlay, 'DELTA_SHA256', SHA(raw)), self.assertRaises((ValueError, TypeError)):
                    overlay.manifest()
            path.write_bytes(b' ' * (overlay.MAX_FIXTURE_BYTES + 1))
            with patch.object(overlay, 'DELTA_PATH', path), self.assertRaises(ValueError):
                overlay.manifest()
        type(self).fixture_negatives = len(candidates) + 2

    def test_read_port_stripping_restores_whole_public_sources_and_all_original_assertions(self):
        for relative in ('tests/phase1_context_fix_source_compatibility.py', 'tests/worker_timezone_host_source_compatibility.py'):
            before = git('show', overlay.PORTS_BEFORE + ':' + relative)
            current = _cpu_history.metadata_input((ROOT / relative).read_bytes(), relative)
            self.assertEqual(current.count(IP_HOOK.encode()), 1)
            self.assertEqual(current.replace(IP_HOOK.encode(), b'', 1), before)
        for relative, name, count in (
            ('tests/profile_phase1_context_fix_source_compatibility_test.py', 'path', 6),
            ('tests/profile_worker_timezone_host_source_compatibility_test.py', 'relative', 12),
            ('tests/profile_page_bridge_budget_source_compatibility_test.py', 'relative', 9),
        ):
            before = git('show', overlay.PORTS_BEFORE + ':' + relative)
            current = _cpu_history.metadata_input((ROOT / relative).read_bytes(), relative)
            self.assertEqual(assertions(current), assertions(before))
            token = ('historical_read(' + name + ')').encode()
            self.assertEqual(current.count(READ_IMPORT), 1)
            self.assertEqual(current.count(token), count)
            self.assertEqual(current.replace(READ_IMPORT, b'', 1).replace(token, ('(ROOT/' + name + ').read_bytes()').encode()), before)
        for name in ('dual-browser-source-deltas.json', 'worker-timezone-source-deltas.json', 'worker-timezone-host-adapter-source-deltas.json', 'connection-timezone-prerequisite-source-deltas.json', 'phase1-context-fix-source-deltas.json', 'page-bridge-budget-source-deltas.json'):
            relative = 'tests/fixtures/' + name
            self.assertEqual(_cpu_history.metadata_input((ROOT / relative).read_bytes(), relative), git('show', overlay.PORTS_BEFORE + ':' + relative))

    def test_historical_read_never_projects_unowned_source_or_escapes_source_root(self):
        with tempfile.TemporaryDirectory(prefix='ip-historical-read-boundary-') as folder:
            root = Path(folder)
            (root / 'tests').mkdir()
            file = root / 'tests/current-runtime.py'; file.write_bytes(b'actual new runtime stays raw\n')
            with patch.object(overlay, 'ROOT', root):
                self.assertEqual(overlay.historical_read('tests/current-runtime.py'), file.read_bytes())
                owned = root / 'tests/profile_native_protection_test.py'; owned.write_bytes(b'unknown complete source')
                with self.assertRaises(ValueError):
                    overlay.historical_read('tests/profile_native_protection_test.py')
                link = root / 'tests/link.py'; link.symlink_to(file)
                with self.assertRaises(ValueError):
                    overlay.historical_read('tests/link.py')
                for path in (None, Path('tests/current-runtime.py'), '../tests/current-runtime.py', '/tests/current-runtime.py', 'tests/../tests/current-runtime.py', '.git/config'):
                    with self.assertRaises(ValueError):
                        overlay.historical_read(path)

    def test_old_public_inventory_rows_unchanged_and_new_public_predecessors_exact(self):
        previous = json.loads(git('show', overlay.PORTS_BEFORE + ':tests/baselines/public-source-history.json'))
        from pure212_ci_source_compatibility import source_input as reviewed_ci_input
        current = json.loads(reviewed_ci_input(_cpu_history.metadata_input((ROOT / 'tests/baselines/public-source-history.json').read_bytes(), 'tests/baselines/public-source-history.json'), 'tests/baselines/public-source-history.json'))
        before = {row['commit']: row for row in previous['groups']}
        now = {row['commit']: row for row in current['groups']}
        self.assertEqual(len(now), len(before) + 2)
        for source, row in before.items():
            self.assertEqual(now[source], row)
        for source, expected in ((overlay.PRODUCTION_BEFORE, overlay.PRODUCER_PATHS), (overlay.PORTS_BEFORE, overlay.PORT_PATHS)):
            group = now[source]
            self.assertEqual(set(group['files']), expected)
            self.assertEqual(git('rev-parse', source + '^{tree}').decode().strip(), group['tree'])
            for relative, pin in group['files'].items():
                raw = git('show', source + ':' + relative)
                self.assertEqual((SHA(raw), len(raw)), (pin['sha256'], pin['bytes']))
                self.assertEqual(hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest(), pin['blob'])
                self.assertEqual(git('ls-tree', source, '--', relative).decode().split()[0], pin['mode'])
        relative = 'tools/browser/source_history.py'
        before = git('show', overlay.PORTS_BEFORE + ':' + relative)
        after = _cpu_history.metadata_input((ROOT / relative).read_bytes(), relative)
        token = b"MANIFEST_SHA256 = '" + SHA(_cpu_history.metadata_input((ROOT / 'tests/baselines/public-source-history.json').read_bytes(), 'tests/baselines/public-source-history.json')).encode() + b"'"
        self.assertEqual(after.count(token), 1)
        self.assertEqual(re.sub(rb"MANIFEST_SHA256 = '[0-9a-f]{64}'", b"MANIFEST_SHA256 = 'PIN'", after), re.sub(rb"MANIFEST_SHA256 = '[0-9a-f]{64}'", b"MANIFEST_SHA256 = 'PIN'", before))

    def test_only_explicit_historical_ports_import_the_outer_view(self):
        allowed = {'tests/phase1_context_fix_source_compatibility.py', 'tests/worker_timezone_host_source_compatibility.py', 'tests/profile_phase1_context_fix_source_compatibility_test.py', 'tests/profile_worker_timezone_host_source_compatibility_test.py', 'tests/profile_page_bridge_budget_source_compatibility_test.py', 'tests/profile_ip_timezone_source_compatibility_test.py'}
        observed = set()
        for directory in ('tests', 'tools'):
            for path in (ROOT / directory).rglob('*.py'):
                raw = path.read_text()
                if 'ip_timezone_source_compatibility' not in raw:
                    continue
                imports = any(isinstance(node, ast.ImportFrom) and node.module == 'ip_timezone_source_compatibility' or isinstance(node, ast.Import) and any(alias.name == 'ip_timezone_source_compatibility' for alias in node.names) for node in ast.walk(ast.parse(raw)))
                if imports:
                    observed.add(path.relative_to(ROOT).as_posix())
        self.assertEqual(observed, allowed)
        self.assertFalse(overlay.manifest()['runtimeAcceptance'])
        self.assertFalse(overlay.manifest()['actualAndroidExecution'])


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(IpTimezoneHistoricalSources))
    report = dict(schema=1, status='passed' if result.wasSuccessful() else 'failed', tests=result.testsRun,
                  rows=7, contexts=42, fixtureSha256=overlay.DELTA_SHA256,
                  rejectedSourceMutants=IpTimezoneHistoricalSources.source_negatives,
                  rejectedProtectedGuardMutants=IpTimezoneHistoricalSources.guard_negatives,
                  rejectedFixtureCounterfeits=IpTimezoneHistoricalSources.fixture_negatives,
                  actualAndroidExecution=False, runtimeAcceptance=False)
    output = os.environ.get('IP_TIMEZONE_SOURCE_REPORT')
    if output:
        path = Path(output); path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(report, indent=2) + '\n')
    raise SystemExit(0 if result.wasSuccessful() else 1)
