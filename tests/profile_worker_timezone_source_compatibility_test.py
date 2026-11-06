"""Exact historical Worker/timezone overlay; never runtime or Android acceptance."""
import ast
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import worker_timezone_source_compatibility as overlay
from phase1_context_fix_source_compatibility import PATHS as context_paths, source_input as context_source_input
import dual_browser_source_compatibility as dual

ROOT = Path(__file__).resolve().parents[1]

import fixture_context_source_compatibility as _fixture_history
SHA = lambda value: hashlib.sha256(value).hexdigest()
DUAL_HOOK = """    if (digest, len(raw)) not in ((row['previousSha256'], row['previousBytes']),
                                  (row['reviewedSha256'], row['reviewedBytes'])):
        from worker_timezone_source_compatibility import PATHS as worker_paths, source_input as worker_source_input
        if relative in worker_paths:
            raw = worker_source_input(raw, relative)
            digest = _sha(raw)
"""
HISTORICAL_TEST_PORT = "            'tests/profile_worker_timezone_source_compatibility_test.py',\n"


def read_hook(indent):
    return (' ' * indent + 'from worker_timezone_source_compatibility import PATHS as worker_paths, source_input as worker_source_input\n'
            + ' ' * indent + 'if relative in worker_paths:\n'
            + ' ' * (indent + 4) + 'current = worker_source_input(current, relative)\n')


def assertions(raw):
    return [ast.dump(node, include_attributes=False) for node in ast.walk(ast.parse(raw))
            if isinstance(node, ast.Assert) or isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute) and node.func.attr.startswith('assert')]


class WorkerTimezoneSourceCompatibility(unittest.TestCase):
    rejected_sources = 0
    rejected_guard_mutants = 0
    rejected_fixture_shapes = 0
    rejected_transition_guard_mutants = 0

    def test_whole_before_and_after_forward_inverse_equal_real_8a_bytes(self):
        self.assertEqual(subprocess.check_output(['git', 'rev-parse', overlay.BASE_COMMIT + '^{tree}'], cwd=ROOT).decode().strip(), overlay.BASE_TREE)
        manifest = overlay.manifest()
        self.assertEqual(len(manifest['files']), 2)
        self.assertEqual(sum(len(row['deltas']) for row in manifest['files'].values()), 23)
        for relative, row in manifest['files'].items():
            with self.subTest(path=relative):
                before = subprocess.check_output(['git', 'show', overlay.BASE_COMMIT + ':' + relative], cwd=ROOT)
                after = _fixture_history.metadata_input((ROOT / relative).read_bytes(), relative)
                if relative in context_paths:
                    after = context_source_input(after, relative)
                self.assertEqual((SHA(before), len(before)), (row['previousSha256'], row['previousBytes']))
                self.assertEqual((SHA(after), len(after)), (row['reviewedSha256'], row['reviewedBytes']))
                self.assertEqual(overlay.source_input(before, relative), before)
                self.assertEqual(overlay.source_input(after, relative), before)
                forward = before
                for delta in row['deltas']:
                    previous, current = delta['previous'].encode(), delta['current'].encode()
                    self.assertTrue(previous and current and previous != current)
                    self.assertEqual((SHA(previous), SHA(current)), (delta['previousSha256'], delta['currentSha256']))
                    self.assertEqual(forward.count(previous), 1)
                    forward = forward.replace(previous, current, 1)
                self.assertEqual(forward, after)
                self.assertEqual(dual.source_input(after, relative), dual.source_input(before, relative))

    def test_all_missing_duplicate_mutated_moved_truncated_and_unknown_sources_fail(self):
        rejected = 0
        for relative, row in overlay.manifest()['files'].items():
            after = _fixture_history.metadata_input((ROOT / relative).read_bytes(), relative)
            if relative in context_paths:
                after = context_source_input(after, relative)
            for delta in row['deltas']:
                current = delta['current'].encode()
                self.assertEqual(after.count(current), 1)
                remainder = after.replace(current, b'', 1)
                moved = remainder + current
                if moved == after:
                    moved = current + remainder
                for mutant in (remainder, after.replace(current, current * 2, 1),
                               after.replace(current, current + b' ', 1), moved):
                    with self.subTest(path=relative, context=delta['id'], mutation=SHA(mutant)):
                        self.assertNotEqual(mutant, after)
                        with self.assertRaises(ValueError):
                            overlay.source_input(mutant, relative)
                        with self.assertRaises(ValueError):
                            dual.source_input(mutant, relative)
                        rejected += 1
            for mutant in (after[:100], after + b' ', b'unknown full source'):
                with self.assertRaises(ValueError):
                    overlay.source_input(mutant, relative)
                with self.assertRaises(ValueError):
                    dual.source_input(mutant, relative)
                rejected += 1
        self.assertEqual(rejected, 98)
        type(self).rejected_sources = rejected

    def test_native_and_latest_explicit_intent_guards_cannot_be_rewritten(self):
        variants = (
            ('app/src/main/java/local/pocketchat/ChatSession.java',
             'boolean chatAutomationAllowed(){return !deleted&&MainActivity.chatUrl(web.getUrl());}',
             'boolean chatAutomationAllowed(){return true;}'),
            ('app/src/main/java/local/pocketchat/ChatSession.java',
             'return target!=null&&chatAutomationAllowed()&&target.epoch==navigationEpoch',
             'return target!=null&&target.epoch==navigationEpoch'),
            ('app/src/main/java/local/pocketchat/GeckoWebView.java',
             'if(!hasTimeZoneIntent(s))loadSessionUri(s,request.uri);',
             'loadSessionUri(s,request.uri);'),
            ('app/src/main/java/local/pocketchat/GeckoWebView.java',
             'return nativeProtection.allows(owner.privacy.level());', 'return true;'),
        )
        for relative, before, after in variants:
            current = _fixture_history.metadata_input((ROOT / relative).read_bytes(), relative)
            if relative in context_paths:
                current = context_source_input(current, relative)
            self.assertEqual(current.count(before.encode()), 1)
            mutant = current.replace(before.encode(), after.encode(), 1)
            with self.assertRaises(ValueError):
                overlay.source_input(mutant, relative)
            with self.assertRaises(ValueError):
                dual.source_input(mutant, relative)
        type(self).rejected_guard_mutants = len(variants)

    def test_coop_document_http_session_and_addon_guards_cannot_be_normalized_away(self):
        relative = 'app/src/main/java/local/pocketchat/GeckoWebView.java'
        variants = (
            ('gate.documentSerial++;gate.preparing=false;gate.ready=false;gate.revalidating=true;',
             'gate.preparing=false;gate.ready=false;gate.revalidating=true;'),
            ('owner.timeZone.revalidate(session,AppSessionIdentity.id(session),gate.epoch,access,finished);',
             'owner.timeZone.prepare(session,AppSessionIdentity.id(session),gate.epoch,access,finished);'),
            ('public boolean current(){return timeZoneSessionAlive(session)&&timeZoneGates.get(session)==gate&&gate.documentSerial==document&&port!=null&&routePort==port;}',
             'public boolean current(){return timeZoneSessionAlive(session)&&timeZoneGates.get(session)==gate&&port!=null&&routePort==port;}'),
            ('"sessionId",AppSessionIdentity.id(session),"requestToken",token',
             '"sessionId","foreign-session","requestToken",token'),
            ('expectedOpen!=gate||', ''),
            ('&&owner.timeZone.status(session,gate.epoch).optBoolean("nativeSettingReadback"));', ');'),
            ('completeTimeZoneProofs(gate,gate.ready);completeTimeZoneRequests(gate,gate.ready);',
             'completeTimeZoneRequests(gate,gate.ready);completeTimeZoneProofs(gate,gate.ready);'),
            ('if(gate==null||!gate.preparing||!gate.revalidating)return false;',
             'if(gate==null||!gate.preparing)return false;'),
            ('!destroyed&&!failed&&!addonDisabled&&!ready&&extension!=null',
             '!destroyed&&!failed&&!ready&&extension!=null'),
            ('if(rejectDisabledNavigation(current,target))return;queued=target;', 'queued=target;'),
            ('if(destroyed||addonDisabled||!locations.containsKey(s))return;boolean committed=',
             'if(destroyed||!locations.containsKey(s))return;boolean committed='),
            ('if(destroyed||addonDisabled||!locations.containsKey(s))return;appearanceLoads.put',
             'if(destroyed||!locations.containsKey(s))return;appearanceLoads.put'),
            ('if(destroyed||addonDisabled||s!=current||target==null', 'if(destroyed||s!=current||target==null'),
            ('if(destroyed||addonDisabled||session!=current||target==null', 'if(destroyed||session!=current||target==null'),
            ('if(!addonDisabled)return false;', 'return false;'),
            ('if(addonDisabled||!"pocketroute".equals(app)', 'if(!"pocketroute".equals(app)'),
            ('if(read==null||destroyed||failed||!enabled||owner.deleted||!requestHeadersInstalled||current!=read.session||!current.isOpen()',
             'if(read==null||destroyed||failed||!enabled||owner.deleted||!requestHeadersInstalled||current!=read.session'),
            ('if(rejectDisabledNavigation(s,request.uri))return GeckoResult.fromValue(AllowOrDeny.DENY);', ''),
        )
        current = _fixture_history.metadata_input((ROOT / relative).read_bytes(), relative)
        if relative in context_paths:
            current = context_source_input(current, relative)
        for before, after in variants:
            with self.subTest(guard=before):
                self.assertEqual(current.count(before.encode()), 1)
                mutant = current.replace(before.encode(), after.encode(), 1)
                with self.assertRaises(ValueError):
                    overlay.source_input(mutant, relative)
                with self.assertRaises(ValueError):
                    dual.source_input(mutant, relative)
        self.assertEqual(len(variants), 18)
        type(self).rejected_transition_guard_mutants = len(variants)

    def test_source_identity_is_checked_before_any_context_inverse(self):
        relative = 'app/src/main/java/local/pocketchat/GeckoWebView.java'
        row = overlay.manifest()['files'][relative]
        after = _fixture_history.metadata_input((ROOT / relative).read_bytes(), relative)
        if relative in context_paths:
            after = context_source_input(after, relative)
        class ForbiddenContext:
            def encode(self, *args):
                raise AssertionError('An unknown source reached a contextual replacement')
        value = copy.deepcopy(overlay.manifest())
        value['files'][relative]['deltas'][0]['current'] = ForbiddenContext()
        with patch.object(overlay, 'manifest', return_value=value):
            with self.assertRaisesRegex(ValueError, 'unknown whole source'):
                overlay.source_input(after + b' ', relative)
        for value in (after.decode(), bytearray(after), memoryview(after), None):
            with self.assertRaises(ValueError):
                overlay.source_input(value, relative)
        for path in (relative + '.other', '../' + relative, '/' + relative, Path(relative), None,
                     'app/src/main/java/local/pocketchat/BrowserActivity.java'):
            with self.assertRaises(ValueError):
                overlay.source_input(after, path)
        self.assertEqual(row['reviewedSha256'], SHA(after))

    def test_fixture_identity_types_source_pins_and_finite_shape_cannot_be_whitelisted(self):
        original = overlay.manifest()
        relative = 'app/src/main/java/local/pocketchat/GeckoWebView.java'
        variants = []
        def top(key, value):
            changed = copy.deepcopy(original);changed[key] = value;variants.append(changed)
        for key, value in (('schema', True), ('kind', 'runtime-acceptance'), ('baseCommit', 'a' * 40),
                           ('baseTree', 'b' * 40), ('actualAndroidExecution', True), ('runtimeAcceptance', True)):
            top(key, value)
        missing = copy.deepcopy(original);missing['files'].pop(relative);variants.append(missing)
        extra = copy.deepcopy(original);extra['files']['unreviewed.java'] = extra['files'][relative];variants.append(extra)
        for key, value in (('previousBytes', True), ('reviewedBytes', 0), ('reviewedBytes', 128 * 1024 + 1),
                           ('reviewedSha256', 'not-a-source-pin'), ('contextLines', 2), ('contextLines', 17),
                           ('deltas', []), ('deltas', [copy.deepcopy(original['files'][relative]['deltas'][0])] * 33)):
            changed = copy.deepcopy(original);changed['files'][relative][key] = value;variants.append(changed)
        same = copy.deepcopy(original);same['files'][relative]['reviewedSha256'] = same['files'][relative]['previousSha256'];variants.append(same)
        for key, value in (('id', 'context-99'), ('currentSha256', '0' * 64), ('previous', ''), ('current', 'x' * (16 * 1024 + 1))):
            changed = copy.deepcopy(original);changed['files'][relative]['deltas'][0][key] = value;variants.append(changed)
        with tempfile.TemporaryDirectory(prefix='worker-timezone-fixture-negative-') as directory:
            path = Path(directory) / 'unreviewed.json'
            path.write_bytes(overlay.DELTA_PATH.read_bytes() + b' ')
            with patch.object(overlay, 'DELTA_PATH', path), self.assertRaises(ValueError):
                overlay.manifest()
            for value in [[], True, *variants]:
                raw = (json.dumps(value, ensure_ascii=False) + '\n').encode()
                path.write_bytes(raw)
                # Pin override is a test-only counterfactual: even this cannot
                # remove the independent identity/schema/shape bounds.
                with patch.object(overlay, 'DELTA_PATH', path), patch.object(overlay, 'DELTA_SHA256', SHA(raw)), self.assertRaises(ValueError):
                    overlay.manifest()
            path.write_bytes(b' ' * (overlay.MAX_FIXTURE_BYTES + 1))
            with patch.object(overlay, 'DELTA_PATH', path), self.assertRaises(ValueError):
                overlay.manifest()
        type(self).rejected_fixture_shapes = len(variants) + 2

    def test_original_fixture_goldens_assertions_mutants_and_input_ports_remain_exact(self):
        for relative in ('tests/fixtures/dual-browser-source-deltas.json',
                         'tests/fixtures/experience46-source-deltas.json',
                         'tests/fixtures/event-journal-source-deltas.json',
                         'tests/fixtures/reading45-restoration-source-deltas.json',
                         'tests/fixtures/gecko-policy-dependency-source-deltas.json'):
            self.assertEqual(_fixture_history.metadata_input((ROOT / relative).read_bytes(), relative), subprocess.check_output(['git', 'show', overlay.BASE_COMMIT + ':' + relative], cwd=ROOT))
        relative = 'tests/dual_browser_source_compatibility.py'
        before = subprocess.check_output(['git', 'show', overlay.BASE_COMMIT + ':' + relative], cwd=ROOT)
        after = _fixture_history.metadata_input((ROOT / relative).read_bytes(), relative)
        self.assertEqual(after.count(DUAL_HOOK.encode()), 1)
        self.assertEqual(after.replace(DUAL_HOOK.encode(), b'', 1), before)
        relative = 'tests/profile_dual_browser_source_compatibility_test.py'
        before = subprocess.check_output(['git', 'show', overlay.BASE_COMMIT + ':' + relative], cwd=ROOT)
        from page_bridge_budget_source_compatibility import PATHS as budget_paths, source_input as budget_source_input
        after = budget_source_input(_fixture_history.metadata_input((ROOT / relative).read_bytes(), relative), relative) if relative in budget_paths else _fixture_history.metadata_input((ROOT / relative).read_bytes(), relative)
        # Remove only the reviewed host-adapter historical read ports before
        # the original complete-file oracle below; no actual host sees a view.
        host_import = b'        from worker_timezone_host_source_compatibility import PATHS as host_adapter_paths, source_input as host_adapter_source_input\n'
        self.assertEqual(after.count(host_import), 1)
        after = after.replace(host_import, b'', 1)
        host_read = b'current = host_adapter_source_input((ROOT / relative).read_bytes(), relative) if relative in host_adapter_paths else (ROOT / relative).read_bytes()'
        self.assertEqual(after.count(host_read), 2)
        after = after.replace(host_read, b'current = (ROOT / relative).read_bytes()')
        self.assertEqual(assertions(after), assertions(before))
        for indent in (16, 12):
            hook = read_hook(indent).encode()
            self.assertEqual(after.count(hook), 1)
            after = after.replace(hook, b'', 1)
        self.assertEqual(after.count(HISTORICAL_TEST_PORT.encode()), 1)
        after = after.replace(HISTORICAL_TEST_PORT.encode(), b'', 1)
        self.assertEqual(after, before)
        self.assertEqual(SHA(dual.DELTA_PATH.read_bytes()), dual.DELTA_SHA256)
        for relative, row in dual.manifest()['files'].items():
            reviewed = subprocess.check_output(['git', 'show', overlay.BASE_COMMIT + ':' + relative], cwd=ROOT)
            self.assertEqual((SHA(reviewed), len(reviewed)), (row['reviewedSha256'], row['reviewedBytes']))

    def test_only_reviewed_historical_ports_import_the_overlay(self):
        allowed = {'tests/dual_browser_source_compatibility.py',
                   'tests/profile_dual_browser_source_compatibility_test.py',
                   'tests/profile_worker_timezone_source_compatibility_test.py'}
        for folder in ('tests', 'tools'):
            for path in (ROOT / folder).rglob('*.py'):
                raw = path.read_text()
                if 'worker_timezone_source_compatibility' not in raw:
                    continue
                imported = any(isinstance(node, ast.ImportFrom) and node.module == 'worker_timezone_source_compatibility'
                               or isinstance(node, ast.Import) and any(a.name == 'worker_timezone_source_compatibility' for a in node.names)
                               for node in ast.walk(ast.parse(raw)))
                if imported:
                    self.assertIn(path.relative_to(ROOT).as_posix(), allowed)
        for relative in ('tests/profile_native_protection_test.py', 'tests/profile_native_runtime_capabilities_test.py',
                         'tests/gecko-timezone-routing-host/run.py', 'tests/gecko-timezone-host/run.py',
                         'tests/gecko-timezone-flow-host/run.py', 'tests/gecko-request-headers-host/run.py',
                         'tests/chromium-worker-policy-host/run.py', 'tests/chromium-fingerprint-activity-host/run.py',
                         'tests/request-identity-timezone-host/run.py', 'tests/gecko-timezone-http-host/run.py'):
            raw = (ROOT / relative).read_text()
            self.assertNotIn('worker_timezone_source_compatibility', raw, relative)
            self.assertNotIn('dual_browser_source_compatibility', raw, relative)
        self.assertFalse(overlay.manifest()['runtimeAcceptance'])
        self.assertFalse(overlay.manifest()['actualAndroidExecution'])


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(WorkerTimezoneSourceCompatibility)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    report = dict(status='passed' if result.wasSuccessful() else 'failed', tests=result.testsRun,
                  baseCommit=overlay.BASE_COMMIT, baseTree=overlay.BASE_TREE,
                  manifestSha256=overlay.DELTA_SHA256, rows=2, contexts=23,
                  rejectedSourceMutants=WorkerTimezoneSourceCompatibility.rejected_sources + WorkerTimezoneSourceCompatibility.rejected_guard_mutants + WorkerTimezoneSourceCompatibility.rejected_transition_guard_mutants,
                  rejectedContextSourceMutants=WorkerTimezoneSourceCompatibility.rejected_sources,
                  rejectedProtectedGuardMutants=WorkerTimezoneSourceCompatibility.rejected_guard_mutants,
                  rejectedTransitionGuardMutants=WorkerTimezoneSourceCompatibility.rejected_transition_guard_mutants,
                  rejectedFixtureCounterfeits=WorkerTimezoneSourceCompatibility.rejected_fixture_shapes,
                  runtimeAcceptance=False, actualAndroidExecution=False,
                  scope='Exact whole-source historical-input overlay only. Old fixtures, goldens, assertions and mutants remain unchanged; runtime hosts read current sources.')
    output = os.environ.get('WORKER_TIMEZONE_SOURCE_REPORT')
    if output:
        path = Path(output);path.parent.mkdir(parents=True, exist_ok=True);path.write_text(json.dumps(report, indent=2) + '\n')
    raise SystemExit(0 if result.wasSuccessful() else 1)
