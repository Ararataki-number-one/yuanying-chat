"""Finite TLS metadata closure; no runtime or Android execution projection."""
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

import cpu_ip_source_compatibility as cpu
import tls_cpu_ip_source_compatibility as layer
from final_browser_source_compatibility import metadata_input as final_metadata_input, canonical_cpu_fixture_sha

from final_browser_source_compatibility import p2_input as p2_metadata_input

ROOT = Path(__file__).resolve().parents[1]
SHA = lambda raw: hashlib.sha256(raw).hexdigest()
SUITE = 'tests/profile_cpu_ip_source_compatibility_test.py'


def git(*args):
    return subprocess.check_output(['git', '--no-replace-objects', *args], cwd=ROOT,
        env=dict(os.environ, GIT_NO_LAZY_FETCH='1', GIT_OPTIONAL_LOCKS='0'))


class TlsCpuIpHistoricalClosure(unittest.TestCase):
    def test_real_complete_before_forward_and_inverse_five_rows(self):
        self.assertEqual(git('rev-parse', layer.BASE_COMMIT+'^{tree}').decode().strip(), layer.BASE_TREE)
        value = layer.manifest()
        self.assertEqual(set(value['files']), layer.PATHS)
        self.assertEqual(len(value['files']), 5)
        self.assertEqual(len(layer.TEMPLATE_PATHS), 2)
        self.assertEqual(sum(len(row['deltas']) for row in value['files'].values()), 19)
        for relative, row in value['files'].items():
            before = git('show', layer.BASE_COMMIT+':'+relative)
            after = p2_metadata_input((ROOT/relative).read_bytes(), relative)
            self.assertEqual((SHA(before), len(before)), (row['previousSha256'], row['previousBytes']))
            self.assertEqual((SHA(after), len(after)), (row['reviewedSha256'], row['reviewedBytes']))
            self.assertEqual(layer.source_input(before, relative), before)
            self.assertEqual(layer.source_input(after, relative), before)
            forward = before
            for delta in row['deltas']:
                old, new = delta['previous'].encode(), delta['current'].encode()
                self.assertEqual(forward.count(old), 1)
                self.assertEqual(after.count(new), 1)
                forward = forward.replace(old, new, 1)
            self.assertEqual(forward, after)

    def test_missing_duplicate_changed_moved_truncated_and_unknown_all_reject(self):
        rejected = 0
        for relative, row in layer.manifest()['files'].items():
            after = p2_metadata_input((ROOT/relative).read_bytes(), relative)
            for delta in row['deltas']:
                part = delta['current'].encode()
                self.assertEqual(after.count(part), 1)
                removed = after.replace(part, b'', 1)
                moved = removed+part
                if moved == after:
                    moved = part+removed
                for raw in (removed, after.replace(part, part+part, 1),
                        after.replace(part, part+b' ', 1), moved, after[:-1], b'/* unknown */\n'+after):
                    with self.assertRaises(ValueError):
                        layer.source_input(raw, relative)
                    rejected += 1
        self.assertEqual(rejected, 114)

    def test_owned_paths_types_and_complete_inputs_only(self):
        relative = 'app/src/main/java/local/pocketchat/GeckoWebView.java'
        raw = p2_metadata_input((ROOT/relative).read_bytes(), relative)
        for bad in (None, raw.decode(), bytearray(raw), raw[:100], raw+b'\n'):
            with self.assertRaises(ValueError):
                layer.source_input(bad, relative)
        for bad in (None, Path(relative), '/'+relative, './'+relative, SUITE+'/../'+relative,
                'app/src/main/java/local/pocketchat/MainActivity.java'):
            with self.assertRaises(ValueError):
                layer.source_input(raw, bad)

    def test_fixture_whole_pin_type_size_and_duplicate_keys(self):
        raw = layer.DELTA_PATH.read_bytes()
        for bad in (None, raw.decode(), bytearray(raw), b'', raw+b'\n', b' '+raw,
                raw[:-1], b'x'*(layer.MAX_FIXTURE_BYTES+1)):
            with self.assertRaises(ValueError):
                layer._decode(bad)
        duplicate = raw.replace(b'"schema": 1', b'"schema": 1, "schema": 1', 1)
        with patch.object(layer, 'DELTA_SHA256', SHA(duplicate)), self.assertRaises(ValueError):
            layer._decode(duplicate)

    def test_counterfeit_typed_metadata_and_delta_members_reject(self):
        original = json.loads(layer.DELTA_PATH.read_bytes())
        relative = 'app/src/main/java/local/pocketchat/GeckoWebView.java'
        mutations = []
        for key, value in (('schema', True), ('kind', 'runtime-source'), ('baseCommit', '0'*40),
                ('baseTree', '0'*40), ('actualAndroidExecution', True), ('runtimeAcceptance', True),
                ('oracle', 'replacement')):
            current = copy.deepcopy(original); current[key] = value; mutations.append(current)
        for key, value in (('previousBytes', True), ('reviewedBytes', 131073), ('contextLines', 2),
                ('reviewedSha256', 'x'*64), ('deltas', []), ('oracle', 'replacement')):
            current = copy.deepcopy(original); current['files'][relative][key] = value; mutations.append(current)
        current = copy.deepcopy(original); current['files']['unexpected.java'] = current['files'][relative]; mutations.append(current)
        for key, value in (('id', 'context-01'), ('current', 'corruption'), ('previous', False),
                ('currentSha256', '0'*64), ('oracle', 'replacement')):
            current = copy.deepcopy(original); current['files'][relative]['deltas'][0][key] = value; mutations.append(current)
        for value in mutations:
            raw = json.dumps(value).encode()
            with patch.object(layer, 'DELTA_SHA256', SHA(raw)), self.assertRaises(ValueError):
                layer._decode(raw)
        self.assertEqual(len(mutations), 19)

    def test_fixture_file_and_parent_symlinks_foreign_path_and_bound_reject(self):
        with tempfile.TemporaryDirectory(prefix='tls-cpu-ip-history-') as temporary:
            root = Path(temporary)
            target = root/'ordinary'; target.write_bytes(layer.DELTA_PATH.read_bytes())
            path = root/'tests/fixtures/tls-cpu-ip-source-deltas.json'; path.parent.mkdir(parents=True)
            path.symlink_to(target)
            with patch.object(layer, 'ROOT', root), patch.object(layer, 'DELTA_PATH', path), self.assertRaises(ValueError):
                layer.manifest()
            path.unlink(); path.write_bytes(b'')
            with patch.object(layer, 'ROOT', root), patch.object(layer, 'DELTA_PATH', path), self.assertRaises(ValueError):
                layer.manifest()
            path.write_bytes(b'x'*(layer.MAX_FIXTURE_BYTES+1))
            with patch.object(layer, 'ROOT', root), patch.object(layer, 'DELTA_PATH', path), self.assertRaises(ValueError):
                layer.manifest()
        with tempfile.TemporaryDirectory(prefix='tls-cpu-ip-parent-') as temporary:
            root = Path(temporary); outside = root/'outside'; outside.mkdir()
            (outside/'tls-cpu-ip-source-deltas.json').write_bytes(layer.DELTA_PATH.read_bytes())
            (root/'tests').mkdir(); (root/'tests/fixtures').symlink_to(outside, target_is_directory=True)
            with patch.object(layer, 'ROOT', root), patch.object(layer, 'DELTA_PATH', root/'tests/fixtures/tls-cpu-ip-source-deltas.json'), self.assertRaises(ValueError):
                layer.manifest()
        with patch.object(layer, 'DELTA_PATH', ROOT/'tests/fixtures/unreviewed.json'), self.assertRaises(ValueError):
            layer.manifest()

    def test_removing_only_declared_hooks_restores_the_whole_original_suite_and_assertions(self):
        original = git('show', layer.BASE_COMMIT+':'+SUITE)
        current = (ROOT/SUITE).read_bytes()
        imported = b'from tls_cpu_ip_source_compatibility import source_input as tls_source_input\n'
        final_imported = b'from final_browser_source_compatibility import metadata_input as final_metadata_input\n'
        hooked = b'after=tls_source_input((ROOT/relative).read_bytes(),relative)'
        left_hook = b'final_metadata_input((ROOT/relative).read_bytes(),relative)'
        self.assertEqual(current.count(imported), 1)
        self.assertEqual(current.count(final_imported), 1)
        self.assertEqual(current.count(hooked), 2)
        self.assertEqual(current.count(left_hook), 1)
        restored = current.replace(imported, b'', 1).replace(final_imported, b'', 1).replace(hooked, b'after=(ROOT/relative).read_bytes()').replace(left_hook, b'(ROOT/relative).read_bytes()', 1)
        self.assertEqual(restored, original)
        self.assertEqual(layer.source_input(current, SUITE), original)
        before_ast, after_ast = ast.parse(original), ast.parse(current)
        assertions = lambda tree: [ast.dump(node, include_attributes=False) for node in ast.walk(tree)
            if isinstance(node, ast.Assert) or isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr.startswith('assert')]
        self.assertEqual(assertions(before_ast), assertions(ast.parse(restored)))
        self.assertEqual(len(assertions(before_ast)), 30)
        self.assertEqual(len(assertions(after_ast)), 30)
        self.assertEqual(sum(a != b for a, b in zip(assertions(before_ast), assertions(after_ast))), 1)
        methods = lambda tree: [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name.startswith('test_')]
        self.assertEqual(methods(before_ast), methods(after_ast))
        self.assertEqual(len(methods(after_ast)), 10)

    def test_original_cpu_ip_nine_deltas_compose_to_real_ip_before(self):
        self.assertEqual(canonical_cpu_fixture_sha(cpu.DELTA_SHA256), '66c9b3643b26edb54b0c371c2053d56e482efcce2035aa1ca067fdead8f48e5a')
        self.assertEqual(sum(len(row['deltas']) for row in cpu.manifest()['files'].values()), 9)
        for relative in cpu.PATHS:
            cpu_source = layer.source_input(p2_metadata_input((ROOT/relative).read_bytes(), relative), relative)
            self.assertEqual(cpu_source, git('show', layer.BASE_COMMIT+':'+relative))
            ip_source = cpu.source_input(cpu_source, relative)
            self.assertEqual(ip_source, git('show', cpu.BASE_COMMIT+':'+relative))

    def test_all_prior_fixtures_helpers_and_older_oracles_remain_whole_bytes(self):
        fixtures = git('ls-tree', '-r', '--name-only', layer.BASE_COMMIT, 'tests/fixtures').decode().splitlines()
        originals = ('tests/cpu_ip_source_compatibility.py', 'tests/profile_native_protection_test.py',
            'tests/profile_worker_timezone_host_source_compatibility_test.py',
            'tests/profile_worker_timezone_source_compatibility_test.py',
            'tests/profile_dual_browser_source_compatibility_test.py',
            'tests/worker_timezone_host_source_compatibility.py', 'tests/worker_timezone_source_compatibility.py',
            'tests/gecko-addon-lifecycle-host/AddonHost.java.in', 'tests/gecko-addon-lifecycle-host/run.py',
            'tests/native-protection-host/NativeProtectionControllerHost.java.in',
            'tests/native-runtime-capabilities-host/NativeRuntimeCapabilitiesHost.java')
        self.assertTrue(fixtures)
        for relative in [*fixtures, *originals]:
            with self.subTest(path=relative):
                current = final_metadata_input((ROOT/relative).read_bytes(), relative)
                self.assertEqual(current, git('show', layer.BASE_COMMIT+':'+relative))

    def test_current_templates_unknown_edits_and_nonclosing_reverse_are_independent(self):
        path = ROOT/'tests/tls_cpu_ip_source_compatibility.py'
        source = path.read_text()
        guard = "    if len(raw) != row['previousBytes'] or _sha(raw) != row['previousSha256']:\n        raise ValueError('TLS-on-CPU/IP inverse did not restore the complete original source')\n"
        self.assertEqual(source.count(guard), 1)
        namespace = {'__file__': str(path), '__name__': 'tls_reverse_counterfeit'}
        exec(compile(source.replace(guard, '', 1), '<TLS reverse closure counterfeit>', 'exec'), namespace)
        for relative in layer.TEMPLATE_PATHS:
            current = (ROOT/relative).read_bytes()
            before = git('show', layer.BASE_COMMIT+':'+relative)
            self.assertEqual(layer.source_input(current, relative), before)
            with self.assertRaises(ValueError):
                layer.source_input(current+b' unknown edit', relative)
            value = copy.deepcopy(layer.manifest())
            delta = value['files'][relative]['deltas'][0]
            delta['previous'] += 'NONCLOSING_REVERSE'
            delta['previousSha256'] = SHA(delta['previous'].encode())
            encoded = json.dumps(value).encode()
            with patch.object(layer, 'DELTA_SHA256', SHA(encoded)):
                admitted_metadata = layer._decode(encoded)
            # Only the new test fixture boundary is rebound. The complete
            # public-before file digest remains the original trusted value.
            with patch.object(layer, 'manifest', return_value=admitted_metadata):
                with self.assertRaisesRegex(ValueError, 'did not restore the complete original source'):
                    layer.source_input(current, relative)
            namespace['manifest'] = lambda value=admitted_metadata: value
            with self.assertRaises(AssertionError):
                with self.assertRaisesRegex(ValueError, 'did not restore the complete original source'):
                    namespace['source_input'](current, relative)

    def test_no_runtime_or_behavior_host_imports_the_tls_historical_layer(self):
        for folder in ('app', 'tools', 'tests/gecko-cpu-host', 'tests/gecko-cpu-controller-host',
                'tests/gecko-cpu-ui-host', 'tests/gecko-ip-transport-host', 'tests/gecko-tls-host',
                'tests/gecko-tls-controller-host', 'tests/gecko-tls-ui-host', 'tests/gecko-tls-delete-host',
                'tests/native-protection-host', 'tests/native-runtime-capabilities-host'):
            for path in (ROOT/folder).rglob('*.py'):
                for node in ast.walk(ast.parse(path.read_text())):
                    if isinstance(node, ast.ImportFrom):
                        self.assertNotEqual(node.module, 'tls_cpu_ip_source_compatibility', str(path))
                    elif isinstance(node, ast.Import):
                        self.assertNotIn('tls_cpu_ip_source_compatibility', [entry.name for entry in node.names], str(path))

    def test_independently_compiled_pin_and_duplicate_guard_counterfeits_fail(self):
        path = ROOT/'tests/tls_cpu_ip_source_compatibility.py'
        source = path.read_text(); raw = layer.DELTA_PATH.read_bytes()
        needle = ' or _sha(raw) != DELTA_SHA256'
        self.assertEqual(source.count(needle), 1)
        namespace = {'__file__': str(path), '__name__': 'tls_pin_counterfeit'}
        exec(compile(source.replace(needle, '', 1), '<TLS whole pin counterfeit>', 'exec'), namespace)
        changed = raw+b'\n'
        def original_pin_check(decode):
            with self.assertRaises(ValueError): decode(changed)
        original_pin_check(layer._decode)
        with self.assertRaises(AssertionError): original_pin_check(namespace['_decode'])
        needle = 'json.loads(raw, object_pairs_hook=_unique)'
        self.assertEqual(source.count(needle), 1)
        namespace = {'__file__': str(path), '__name__': 'tls_duplicate_counterfeit'}
        exec(compile(source.replace(needle, 'json.loads(raw)', 1), '<TLS duplicate counterfeit>', 'exec'), namespace)
        duplicate = raw.replace(b'"schema": 1', b'"schema": 1, "schema": 1', 1)
        namespace['DELTA_SHA256'] = SHA(duplicate)
        with patch.object(layer, 'DELTA_SHA256', SHA(duplicate)), self.assertRaises(ValueError):
            layer._decode(duplicate)
        with self.assertRaises(AssertionError):
            with self.assertRaises(ValueError): namespace['_decode'](duplicate)


if __name__ == '__main__': unittest.main(verbosity=2)
