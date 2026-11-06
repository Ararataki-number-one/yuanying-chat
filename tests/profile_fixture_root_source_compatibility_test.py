"""Metadata-only framework-root inverse; never a runtime or device proof.

The fixed before hashes were checked against actual public6ee Git blobs while
generating the reviewed fixture. These controls need no new historical fetch.
"""
import ast
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import profile_fixture_root_source_compatibility as layer

ROOT = Path(__file__).resolve().parents[1]
SHA = lambda raw: hashlib.sha256(raw).hexdigest()
BEFORE = {
    'tests/gecko/FingerprintFollowupIntegrationActivity.java': ('992a155c73c121ca7f7934df2cf18bcaf96ae9dce8780d3e891f957c3753209d', 82624),
    'tests/dual_browser_source_compatibility.py': ('23f51bb9a3ff4ff405de68c5ef0eeba68a8d8c4861efdfd00c82777fa1a03455', 4933),
    'tests/profile_dual_browser_source_compatibility_test.py': ('7df965ca9da87bd418a2edd571edef3d0ff519aae3d7242c21e95619b31f211a', 20409),
    'tests/profile_worker_timezone_source_compatibility_test.py': ('cb1767b9a5bc21fd914f7790e466486bcac2752f10451693d84947f7c27a5fec', 21610),
    'tests/final_browser_source_compatibility.py': ('0c57aeb34471f92629a36cdc8f71447f2353daaac6a7940423c2e85d9141e37d', 16085),
}


def assertions(raw):
    return [ast.dump(node, include_attributes=False) for node in ast.walk(ast.parse(raw))
            if isinstance(node, ast.Assert) or isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute) and node.func.attr.startswith('assert')]


class FixtureRootHistoricalInputs(unittest.TestCase):
    def test_complete_forward_inverse_and_independent_before_hashes(self):
        value = layer.manifest()
        self.assertEqual(value['baseCommit'], '6ee06aced87581e52aa301431f8996ed46d666b8')
        self.assertEqual(value['baseTree'], '19b74a878d2c238cdb209dd51d2fb66076057963')
        self.assertEqual(set(BEFORE), layer.PATHS)
        self.assertEqual(sum(len(r['deltas']) for r in value['files'].values()), 7)
        for relative, row in value['files'].items():
            current = (ROOT/relative).read_bytes()
            previous = layer.source_input(current, relative)
            self.assertEqual((SHA(previous), len(previous)), BEFORE[relative])
            self.assertEqual((SHA(current), len(current)), (row['reviewedSha256'], row['reviewedBytes']))
            self.assertIs(layer.source_input(previous, relative), previous)
            forward = previous
            for delta in row['deltas']:
                before, after = delta['previous'].encode(), delta['current'].encode()
                self.assertEqual(forward.count(before), 1)
                forward = forward.replace(before, after, 1)
            self.assertEqual(forward, current)
            self.assertIs(layer.historical_input(previous, relative), previous)

    def test_missing_duplicate_changed_moved_truncated_and_unknown_owned_images_reject(self):
        rejected = 0
        for relative, row in layer.manifest()['files'].items():
            raw = (ROOT/relative).read_bytes()
            for delta in row['deltas']:
                chunk = delta['current'].encode()
                self.assertEqual(raw.count(chunk), 1)
                remaining = raw.replace(chunk, b'', 1)
                moved = remaining+chunk
                if moved == raw:
                    moved = chunk+remaining
                for bad in (remaining, raw.replace(chunk, chunk+chunk, 1),
                        raw.replace(chunk, chunk+b' ', 1), moved):
                    self.assertNotEqual(raw, bad)
                    with self.assertRaises(ValueError):
                        layer.source_input(bad, relative)
                    rejected += 1
            for bad in (raw[:-1], raw+b'unknown', raw[:80]):
                with self.assertRaises(ValueError):
                    layer.historical_input(bad, relative)
                rejected += 1
        self.assertEqual(rejected, 43)

    def test_source_type_foreign_path_and_whole_pin_precede_context_access(self):
        relative = 'tests/gecko/FingerprintFollowupIntegrationActivity.java'
        raw = (ROOT/relative).read_bytes()
        for bad in (None, raw.decode(), bytearray(raw), memoryview(raw)):
            with self.assertRaises(ValueError):
                layer.source_input(bad, relative)
        for bad in (None, Path(relative), '.', '/'+relative, './'+relative, '../'+relative,
                relative+'/', 'tests/gecko/IdentityAuditIntegrationActivity.java'):
            with self.assertRaises(ValueError):
                layer.source_input(raw, bad)
        class Forbidden:
            def encode(self, *args):
                raise AssertionError('Unknown whole image reached contextual inverse')
        value = copy.deepcopy(layer.manifest())
        value['files'][relative]['deltas'][0]['current'] = Forbidden()
        with patch.object(layer, 'manifest', return_value=value), self.assertRaisesRegex(ValueError, 'unknown complete'):
            layer.source_input(raw+b' ', relative)
        with self.assertRaises(ValueError):
            layer.source_input(b'x'*(layer.MAX_SOURCE_BYTES+1), relative)

    def test_fixture_whole_pin_shape_duplicate_and_provenance_reject(self):
        original = layer.DELTA_PATH.read_bytes()
        value = json.loads(original)
        variants = [original+b' ', b'{"schema":1,"schema":1}', b'{"schema":NaN}']
        for key, bad in [('schema', True), ('baseCommit', '0'*40), ('baseTree', '0'*40),
                ('runtimeAcceptance', True), ('actualAndroidExecution', True), ('files', {})]:
            altered = copy.deepcopy(value); altered[key] = bad
            variants.append((json.dumps(altered, indent=2)+'\n').encode())
        with tempfile.TemporaryDirectory(prefix='fixture-root-meta-') as folder:
            target = Path(folder)/'fixture.json'
            for index, raw in enumerate(variants):
                target.write_bytes(raw)
                with patch.object(layer, 'DELTA_PATH', target), self.assertRaises(ValueError):
                    layer.manifest()
                if index:
                    with patch.object(layer, 'DELTA_PATH', target), patch.object(layer, 'DELTA_SHA256', SHA(raw)), self.assertRaises(ValueError):
                        layer.manifest()
            target.write_bytes(original); alias = Path(folder)/'alias.json'; alias.symlink_to(target)
            with patch.object(layer, 'DELTA_PATH', alias), self.assertRaises(ValueError):
                layer.manifest()

    def test_context_and_complete_preimage_guards_are_necessary(self):
        relative = 'tests/gecko/FingerprintFollowupIntegrationActivity.java'
        raw = (ROOT/relative).read_bytes()
        for change in ('missing', 'nonclosing'):
            value = copy.deepcopy(layer.manifest()); delta = value['files'][relative]['deltas'][0]
            if change == 'missing':
                delta['current'] += 'absent context'
            else:
                delta['previous'] += 'wrong predecessor'
            with patch.object(layer, 'manifest', return_value=value), self.assertRaises(ValueError):
                layer.source_input(raw, relative)

        source = Path(layer.__file__).read_text()
        last_guard = "    if (_sha(raw), len(raw)) != (row['previousSha256'], row['previousBytes']):\n        raise ValueError('Fixture-root metadata did not restore its exact complete predecessor')\n"
        self.assertEqual(source.count(last_guard), 1)
        namespace = {'__file__':layer.__file__, '__name__':'fixture_root_nonclosing_counterfeit'}
        exec(compile(source.replace(last_guard, '', 1), '<fixture-root-preimage-counterfeit>', 'exec'), namespace)
        value = copy.deepcopy(layer.manifest())
        value['files'][relative]['deltas'][0]['previous'] += 'wrong predecessor'
        namespace['manifest'] = lambda: value
        with self.assertRaises(AssertionError):
            with self.assertRaises(ValueError):
                namespace['source_input'](raw, relative)

        first_guard = "    if identity != (row['reviewedSha256'], row['reviewedBytes']):\n        raise ValueError('Fixture-root metadata rejects unknown complete source bytes')\n"
        self.assertEqual(source.count(first_guard), 1)
        namespace = {'__file__':layer.__file__, '__name__':'fixture_root_unknown_counterfeit'}
        exec(compile(source.replace(first_guard, '', 1), '<fixture-root-whole-counterfeit>', 'exec'), namespace)
        class Forbidden:
            def encode(self, *args):
                raise AssertionError('Unknown whole image reached a context')
        value = copy.deepcopy(layer.manifest())
        value['files'][relative]['deltas'][0]['current'] = Forbidden()
        namespace['manifest'] = lambda: value
        with self.assertRaises(AssertionError):
            with self.assertRaises(ValueError):
                namespace['source_input'](raw+b' ', relative)

    def test_final_historical_read_hooks_strip_to_the_complete_prior_suite(self):
        raw = (ROOT/'tests/profile_final_browser_source_compatibility_test.py').read_bytes()
        restored = raw
        global_import = b'from profile_fixture_root_source_compatibility import historical_input as fixture_root_input\n'
        local_hook = (b'    from profile_fixture_root_source_compatibility import historical_input as fixture_root_input\n'
                      b"    raw = fixture_root_input(raw, 'tests/final_browser_source_compatibility.py')\n")
        self.assertEqual(restored.count(local_hook), 1)
        restored = restored.replace(local_hook, b'', 1)
        self.assertEqual(restored.count(global_import), 1)
        restored = restored.replace(global_import, b'', 1)
        read_hook = b'fixture_root_input((ROOT/relative).read_bytes(), relative)'
        self.assertEqual(restored.count(read_hook), 4)
        restored = restored.replace(read_hook, b'(ROOT/relative).read_bytes()')
        self.assertEqual(SHA(restored), '780e1fa91010ae72a05223ea0ed528cc1543498b1a16eb4a568c2df332951a11')
        self.assertEqual(assertions(raw), assertions(restored))

    def test_old_fixtures_assertions_and_runtime_sources_stay_current(self):
        for name, expected in [('dual-browser-source-deltas.json', 'b593b0db2b56b5a5d8143a920fbd15858dafbab21d1cdaf90ca2a5ba164c9933'),
                ('worker-timezone-source-deltas.json', '4eafec08cbeb3beb9098ebf5df7b976423616bb213e47e802a1d39315a27602b'),
                ('final-browser-source-deltas.json', '8bb0bb6580879fcef6258f48e57fbdce19304c0d3ea0061131d993b815877a16')]:
            self.assertEqual(SHA((ROOT/'tests/fixtures'/name).read_bytes()), expected)
        for relative in ('tests/profile_dual_browser_source_compatibility_test.py', 'tests/profile_worker_timezone_source_compatibility_test.py'):
            raw = (ROOT/relative).read_bytes()
            self.assertEqual(assertions(raw), assertions(layer.source_input(raw, relative)))
        self.assertEqual(SHA((ROOT/'tests/gecko/FingerprintFollowupIntegrationActivity.java').read_bytes()),
                         'aac64b137b041b89f6c262b5b52e691fb94a3bb4a0abd5322f4ce5973aad3036')
        aggregator = ast.parse((ROOT/'tools/gecko/run_profile_host_checks.py').read_text())
        main = next(n for n in aggregator.body if isinstance(n, ast.FunctionDef) and n.name == 'main')
        binding = ast.parse('input_paths.add(ROOT / "tests/profile-fixture-root-host/Host.java.in")').body[0]
        self.assertEqual(sum(ast.dump(n, include_attributes=False) == ast.dump(binding, include_attributes=False)
                             for n in main.body), 1)
        allowed = {'tests/dual_browser_source_compatibility.py', 'tests/profile_dual_browser_source_compatibility_test.py',
                   'tests/final_browser_source_compatibility.py', 'tests/profile_final_browser_source_compatibility_test.py',
                   'tests/profile_fixture_root_source_compatibility_test.py'}
        imports = set()
        for folder in ('app', 'tests', 'tools'):
            for path in (ROOT/folder).rglob('*.py'):
                for node in ast.walk(ast.parse(path.read_bytes())):
                    if (isinstance(node, ast.ImportFrom) and node.module == 'profile_fixture_root_source_compatibility'
                            or isinstance(node, ast.Import) and any(a.name == 'profile_fixture_root_source_compatibility' for a in node.names)):
                        imports.add(path.relative_to(ROOT).as_posix())
        self.assertEqual(imports, allowed)
        self.assertFalse(layer.manifest()['runtimeAcceptance'])
        self.assertFalse(layer.manifest()['actualAndroidExecution'])

    def test_unowned_metadata_is_never_projected_and_actual_hosts_keep_real_source(self):
        raw = b'current source must remain byte-identical\r\n'
        for relative in ('app/src/main/java/local/pocketchat/GeckoWebView.java',
                'tools/gecko/run_profile_host_checks.py', 'tests/profile-fixture-root-host/Host.java.in'):
            self.assertIs(layer.historical_input(raw, relative), raw)
            with self.assertRaises(ValueError):
                layer.source_input(raw, relative)
        source = (ROOT/'tests/profile-fixture-root-host/run.py').read_text()
        self.assertNotIn('source_compatibility', source)
        self.assertNotIn('historical_input', source)


if __name__ == '__main__':
    unittest.main(verbosity=2)
