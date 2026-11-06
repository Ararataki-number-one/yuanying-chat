"""Current production bytes and strict resource-recovery historical inputs."""
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

import resource_startup_source_compatibility as layer

ROOT = Path(__file__).resolve().parents[1]
SHA = lambda raw: hashlib.sha256(raw).hexdigest()


class ResourceStartupHistoricalInputs(unittest.TestCase):
    def test_actual_one_condition_fix_restores_the_complete_public_producer(self):
        current = (ROOT/layer.GV).read_bytes()
        previous = subprocess.check_output(['git', '--no-replace-objects', 'show',
            '12a45fb8a1343bbe5767bdf6c3fba54519650fa1:'+layer.GV], cwd=ROOT,
            env=dict(os.environ, GIT_NO_LAZY_FETCH='1'))
        self.assertEqual(SHA(current), '55225a8da3ba67b3be724e243c9b442e635dbc5aa282a2ef0257653e8fb2b364')
        self.assertEqual(SHA(previous), '34a651c3ccc50499dd5c720c370353600ccf20669df5393ccbf68d6a689f9670')
        self.assertEqual(layer.source_input(current, layer.GV), previous)
        self.assertIs(layer.source_input(previous, layer.GV), previous)
        self.assertEqual(len(previous)-len(current), len('&&runtime!=null'))

    def test_all_five_exact_images_have_unique_complete_forward_and_inverse(self):
        cfg = layer.config()
        self.assertEqual(set(cfg['sources']), set(layer.SOURCE_PATHS))
        for relative, row in cfg['sources'].items():
            with self.subTest(path=relative):
                current = (ROOT/relative).read_bytes()
                previous = layer.source_input(current, relative)
                self.assertEqual((SHA(previous), len(previous)), (row['previousSha256'], row['previousBytes']))
                forward = previous
                for delta in row['edits']:
                    before, after = delta['previous'].encode(), delta['current'].encode()
                    self.assertEqual(forward.count(before), 1)
                    forward = forward.replace(before, after, 1)
                self.assertEqual(forward, current)

    def test_original_fixtures_and_every_other_row_stay_whole(self):
        import final_browser_source_compatibility as final
        import profile_fixture_root_source_compatibility as root
        raw = (ROOT/'tests/fixtures/final-browser-source-deltas.json').read_bytes()
        self.assertEqual(SHA(raw), '8bb0bb6580879fcef6258f48e57fbdce19304c0d3ea0061131d993b815877a16')
        before, after = json.loads(raw), final.manifest()
        self.assertEqual(len(after['files']), 19)
        self.assertEqual(sum(len(r['deltas']) for r in after['files'].values()), 59)
        self.assertEqual(layer.frozen_manifest_input(after), before)
        for path in before['files']:
            if path != layer.GV:
                self.assertEqual(before['files'][path], after['files'][path])
        self.assertEqual(SHA((ROOT/'tests/fixtures/profile-fixture-root-source-deltas.json').read_bytes()),
                         'edad6886ab8867e8d76249de55f9ed23d1b664f830039eaf8e04caf9f9f19e1a')
        self.assertEqual(len(root.manifest()['files']), 5)
        self.assertEqual(sum(len(r['deltas']) for r in root.manifest()['files'].values()), 7)
        self.assertFalse(layer.config()['actualAndroidExecution'])
        self.assertFalse(layer.config()['runtimeAcceptance'])

    def test_original_core_guards_decode_and_all_assertion_right_operands_remain(self):
        def method(source, name):
            node = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == name)
            return ast.get_source_segment(source, node)
        for path, names in [(layer.FINAL, ('_decode', 'source_input', '_metadata_path')),
                            (layer.LAYER, ('source_input', '_path'))]:
            current = (ROOT/path).read_bytes()
            previous = layer.source_input(current, path)
            for name in names:
                self.assertEqual(method(current.decode(), name), method(previous.decode(), name))
        for path in (layer.FINALTEST, layer.ROOTTEST):
            current = (ROOT/path).read_bytes()
            previous = layer.source_input(current, path)
            def right_operands(raw):
                return [ast.dump(node.args[1], include_attributes=False)
                        for node in ast.walk(ast.parse(raw)) if isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Attribute) and node.func.attr.startswith('assert')
                        and len(node.args) >= 2]
            self.assertEqual(right_operands(current), right_operands(previous))

    def test_each_missing_duplicate_changed_moved_unknown_and_foreign_image_rejects(self):
        rejected = 0
        for path, row in layer.config()['sources'].items():
            current = (ROOT/path).read_bytes()
            for delta in row['edits']:
                chunk = delta['current'].encode()
                remainder = current.replace(chunk, b'', 1)
                for bad in (remainder, current.replace(chunk, chunk*2, 1),
                            current.replace(chunk, chunk+b' ', 1), remainder+chunk):
                    with self.assertRaises(ValueError):
                        layer.source_input(bad, path)
                    rejected += 1
            for bad in (current[:-1], current+b'unknown', current[:70]):
                with self.assertRaises(ValueError):
                    layer.source_input(bad, path)
                rejected += 1
        self.assertGreaterEqual(rejected, 59)
        current = (ROOT/layer.GV).read_bytes()
        for bad in (None, current.decode(), bytearray(current), memoryview(current), b''):
            with self.assertRaises(ValueError):
                layer.source_input(bad, layer.GV)
        for path in (None, Path(layer.GV), './'+layer.GV, '/'+layer.GV, '../'+layer.GV,
                     'tests/gecko/ResourcePressureIntegrationActivity.java'):
            with self.assertRaises(ValueError):
                layer.source_input(current, path)

    def test_fixture_whole_hash_duplicate_nonfinite_and_alias_are_rejected(self):
        raw = layer.CONFIG.read_bytes()
        with tempfile.TemporaryDirectory(prefix='resource-history-') as temp:
            path = Path(temp)/'input.json'
            for candidate in (raw+b' ', raw[:-1], b'{}', b'x'*(256*1024+1)):
                path.write_bytes(candidate)
                with patch.object(layer, 'CONFIG', path), self.assertRaises(ValueError):
                    layer.config()
            for candidate in (raw.replace(b'"schema": 1', b'"schema": 1, "schema": 1', 1),
                              raw.replace(b'"schema": 1', b'"schema": NaN', 1)):
                path.write_bytes(candidate)
                with patch.object(layer, 'CONFIG', path), patch.object(layer, 'CONFIG_SHA256', SHA(candidate)), self.assertRaises(ValueError):
                    layer.config()
            path.write_bytes(raw)
            alias = Path(temp)/'alias.json'; alias.symlink_to(path)
            with patch.object(layer, 'CONFIG', alias), self.assertRaises(ValueError):
                layer.config()

    def test_whole_source_and_complete_predecessor_guards_remain_independent(self):
        current = (ROOT/layer.GV).read_bytes()
        source = Path(layer.__file__).read_text()
        first = '    if identity != (row["currentSha256"], row["currentBytes"]):\n        raise ValueError("Resource metadata rejects unknown complete source bytes")\n'
        last = '    if (_sha(raw), len(raw)) != (row["previousSha256"], row["previousBytes"]):\n        raise ValueError("Resource metadata failed to restore its complete actual predecessor")\n'
        self.assertEqual(source.count(first), 1)
        self.assertEqual(source.count(last), 1)
        class Forbidden:
            def encode(self, *args):
                raise AssertionError('Unknown bytes reached resource context')
        cfg = copy.deepcopy(layer.config()); cfg['sources'][layer.GV]['edits'][0]['current'] = Forbidden()
        with patch.object(layer, 'config', return_value=cfg), self.assertRaises(ValueError):
            layer.source_input(current+b'unknown', layer.GV)
        namespace = {'__file__':layer.__file__}
        exec(compile(source.replace(first, '', 1), '<unknown-source-counterfeit>', 'exec'), namespace)
        namespace['config'] = lambda: cfg
        with self.assertRaises(AssertionError):
            with self.assertRaises(ValueError):
                namespace['source_input'](current+b'unknown', layer.GV)
        cfg = copy.deepcopy(layer.config()); cfg['sources'][layer.GV]['edits'][0]['previous'] += 'NONCLOSING'
        with patch.object(layer, 'config', return_value=cfg), self.assertRaises(ValueError):
            layer.source_input(current, layer.GV)
        namespace = {'__file__':layer.__file__}
        exec(compile(source.replace(last, '', 1), '<predecessor-counterfeit>', 'exec'), namespace)
        namespace['config'] = lambda: cfg
        with self.assertRaises(AssertionError):
            with self.assertRaises(ValueError):
                namespace['source_input'](current, layer.GV)

    def test_views_reject_unknown_metadata_and_do_not_rewrite_other_p2_mutations(self):
        import final_browser_source_compatibility as final
        current = final.manifest()
        changed = copy.deepcopy(current); changed['files'][layer.GV]['deltas'][0]['current'] = 'unknown original context'
        with self.assertRaises(ValueError):
            layer.frozen_manifest_input(changed)
        row = layer.p2_reference_row(changed['files'][layer.GV])
        self.assertEqual(row['deltas'][0]['current'], 'unknown original context')
        self.assertEqual(row['deltas'][4], layer.config()['finalBefore']['deltas'][4])
        changed = copy.deepcopy(current['files'][layer.GV]); changed['deltas'][4]['current'] += 'unknown resource context'
        with self.assertRaises(ValueError):
            layer.p2_reference_row(changed)
        with self.assertRaises(ValueError):
            layer.root_manifest_input({})
        with self.assertRaises(ValueError):
            layer.final_manifest_input({})

    def test_runtime_device_and_compile_call_sites_never_import_metadata_layer(self):
        allowed = {layer.FINAL, layer.LAYER, layer.FINALTEST, layer.ROOTTEST,
                   'tests/profile_connections_admission_metadata_compatibility_test.py',
                   'tests/profile_resource_startup_source_compatibility_test.py'}
        imports = set()
        for folder in ('app', 'tests', 'tools'):
            for path in (ROOT/folder).rglob('*.py'):
                for node in ast.walk(ast.parse(path.read_bytes())):
                    if (isinstance(node, ast.ImportFrom) and node.module == 'resource_startup_source_compatibility'
                            or isinstance(node, ast.Import) and any(n.name == 'resource_startup_source_compatibility' for n in node.names)):
                        imports.add(path.relative_to(ROOT).as_posix())
        self.assertEqual(imports, allowed)
        host = ROOT/'tests/resource-recovery-host/run.py'
        self.assertTrue(host.is_file())
        self.assertNotIn('source_compatibility', host.read_text())


if __name__ == '__main__':
    unittest.main(verbosity=2)
