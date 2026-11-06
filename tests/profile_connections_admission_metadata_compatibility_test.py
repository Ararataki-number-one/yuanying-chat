"""Finite JSON/helper metadata closure; current device/behavior sources stay raw."""
import ast
import copy
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import connections_admission_metadata_compatibility as layer
import final_browser_source_compatibility as final
from resource_startup_source_compatibility import prior_metadata_input

ROOT = Path(__file__).resolve().parents[1]
SHA = lambda raw: hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()


class ConnectionsAdmissionMetadata(unittest.TestCase):
    def callback(self):
        return (ROOT/layer.CALLBACK_PATH).read_bytes()

    def test_current_sidecar_exact_four_additions_restore_the_entire_old_fixture(self):
        raw = self.callback()
        before = layer.callback_metadata_input(raw, layer.CALLBACK_PATH)
        self.assertEqual((SHA(raw), len(raw)), (layer.CALLBACK_CURRENT_SHA256, layer.CALLBACK_CURRENT_BYTES))
        self.assertEqual((SHA(before), len(before)),
                         ('8f4157350dc8eb9bf2b6c8e6d6345b4383f67c5585198ca4299b0134ae56e21c', 13257))
        self.assertIs(layer.callback_metadata_input(before, layer.CALLBACK_PATH), before)
        self.assertEqual(final.metadata_input(raw, layer.CALLBACK_PATH), before)
        old, current = json.loads(before), json.loads(raw)
        forward = copy.deepcopy(old)
        forward['files'][layer.JAVA_ROW]['reviewedSha256'] = layer.JAVA_CURRENT_SHA256
        forward['files'][layer.JAVA_ROW]['deltas'].extend(current['files'][layer.JAVA_ROW]['deltas'][1:])
        self.assertEqual(encoded(forward), raw)
        self.assertEqual(len(current['files'][layer.JAVA_ROW]['deltas']), 5)
        self.assertEqual(len(old['files'][layer.JAVA_ROW]['deltas']), 1)

    def test_old_root_fixture_and_five_rows_seven_contexts_remain_exact(self):
        raw = (ROOT/'tests/fixtures/profile-fixture-root-source-deltas.json').read_bytes()
        self.assertEqual((SHA(raw), len(raw)), (layer.ROOT_MANIFEST_SHA256, layer.ROOT_MANIFEST_BYTES))
        old = json.loads(raw); snapshot = copy.deepcopy(old)
        view = layer.profile_manifest_input(old)
        self.assertEqual(old, snapshot)
        self.assertEqual(len(view['files']), 5)
        self.assertEqual(sum(len(row['deltas']) for row in view['files'].values()), 7)
        for relative, row in old['files'].items():
            if relative != layer.FINAL_HELPER_PATH:
                self.assertEqual(view['files'][relative], row)
        prior, current = old['files'][layer.FINAL_HELPER_PATH], view['files'][layer.FINAL_HELPER_PATH]
        self.assertEqual(current['previousSha256'], prior['previousSha256'])
        self.assertEqual(current['previousBytes'], prior['previousBytes'])
        self.assertEqual(current['deltas'][0]['previous'], prior['deltas'][0]['previous'])
        self.assertEqual(current['deltas'][0]['previousSha256'], prior['deltas'][0]['previousSha256'])

    def test_actual_helper_whole_forward_inverse_and_original_middle_image(self):
        actual_current = (ROOT/layer.FINAL_HELPER_PATH).read_bytes()
        current = prior_metadata_input(actual_current, layer.FINAL_HELPER_PATH)
        self.assertEqual((SHA(current), len(current)), (layer.FINAL_CURRENT_SHA256, layer.FINAL_CURRENT_BYTES))
        branch = layer.FINAL_BRANCH.encode()
        self.assertEqual(current.count(branch), 1)
        middle = current.replace(branch, b'', 1)
        self.assertEqual((SHA(middle), len(middle)),
                         ('118fcc1063e93ca7bd96e9fb5e49580c65541faaed0bf7d017ca88c26fe1f1f7', 16294))
        row = layer.profile_manifest_input(json.loads((ROOT/'tests/fixtures/profile-fixture-root-source-deltas.json').read_bytes()))['files'][layer.FINAL_HELPER_PATH]
        delta = row['deltas'][0]
        self.assertEqual(current.count(delta['current'].encode()), 1)
        before = current.replace(delta['current'].encode(), delta['previous'].encode(), 1)
        self.assertEqual((SHA(before), len(before)),
                         ('0c57aeb34471f92629a36cdc8f71447f2353daaac6a7940423c2e85d9141e37d', 16085))
        self.assertEqual(final.metadata_input(actual_current, layer.FINAL_HELPER_PATH), before)
        self.assertEqual(before.replace(delta['previous'].encode(), delta['current'].encode(), 1), current)

    def test_unknown_types_paths_lengths_whole_images_and_duplicate_json_fail_closed(self):
        raw = self.callback()
        for bad in (None, raw.decode(), bytearray(raw), memoryview(raw), b'', raw[:-1], raw+b' ', b' '+raw,
                    b'x'*(layer.MAX_METADATA_BYTES+1)):
            with self.assertRaises(ValueError):
                layer.callback_metadata_input(bad, layer.CALLBACK_PATH)
        for relative in (None, Path(layer.CALLBACK_PATH), './'+layer.CALLBACK_PATH,
                         '/'+layer.CALLBACK_PATH, '../'+layer.CALLBACK_PATH,
                         layer.CALLBACK_PATH+'/', layer.JAVA_ROW):
            with self.assertRaises(ValueError):
                layer.callback_metadata_input(raw, relative)
        for bad in (raw.replace(b'"schema": 1', b'"schema": 1, "schema": 1', 1),
                    raw.replace(b'"schema": 1', b'"schema": NaN', 1)):
            with patch.object(layer, 'CALLBACK_CURRENT_SHA256', SHA(bad)), \
                    patch.object(layer, 'CALLBACK_CURRENT_BYTES', len(bad)), self.assertRaises(ValueError):
                layer.callback_metadata_input(bad, layer.CALLBACK_PATH)

    def test_each_declared_added_metadata_context_is_independently_fixed(self):
        original = json.loads(self.callback())
        variants = []
        for index in range(1, 5):
            for kind in ('missing', 'duplicate', 'changed', 'moved'):
                value = copy.deepcopy(original); deltas = value['files'][layer.JAVA_ROW]['deltas']
                if kind == 'missing':
                    del deltas[index]
                elif kind == 'duplicate':
                    deltas.insert(index, copy.deepcopy(deltas[index]))
                elif kind == 'changed':
                    deltas[index]['current'] += ' unknown hunk'
                else:
                    deltas.insert(0, deltas.pop(index))
                variants.append(value)
        for value in variants:
            raw = encoded(value)
            with self.assertRaises(ValueError):
                layer.callback_metadata_input(raw, layer.CALLBACK_PATH)
            # Even rebinding the outer test-only pin cannot bless a different
            # declared addition; independent pair hashes still reject it.
            with patch.object(layer, 'CALLBACK_CURRENT_SHA256', SHA(raw)), \
                    patch.object(layer, 'CALLBACK_CURRENT_BYTES', len(raw)), self.assertRaises(ValueError):
                layer.callback_metadata_input(raw, layer.CALLBACK_PATH)
        self.assertEqual(len(variants), 16)

    def test_old_metadata_oracle_or_other_row_cannot_be_rewritten(self):
        original = json.loads(self.callback())
        for kind in ('original-context', 'previous-java-hash', 'other-row'):
            value = copy.deepcopy(original)
            if kind == 'original-context':
                value['files'][layer.JAVA_ROW]['deltas'][0]['current'] += ' changed old oracle'
            elif kind == 'previous-java-hash':
                value['files'][layer.JAVA_ROW]['previousSha256'] = '0'*64
            else:
                relative = next(path for path in value['files'] if path != layer.JAVA_ROW)
                value['files'][relative]['reviewedSha256'] = '0'*64
            raw = encoded(value)
            with patch.object(layer, 'CALLBACK_CURRENT_SHA256', SHA(raw)), \
                    patch.object(layer, 'CALLBACK_CURRENT_BYTES', len(raw)), self.assertRaisesRegex(ValueError, 'complete old sidecar'):
                layer.callback_metadata_input(raw, layer.CALLBACK_PATH)

    def test_root_manifest_view_requires_original_complete_metadata(self):
        original = json.loads((ROOT/'tests/fixtures/profile-fixture-root-source-deltas.json').read_bytes())
        for kind in ('schema', 'extra-row', 'old-oracle', 'context'):
            value = copy.deepcopy(original)
            if kind == 'schema':
                value['schema'] = True
            elif kind == 'extra-row':
                value['files']['unknown'] = {}
            elif kind == 'old-oracle':
                value['files'][layer.FINAL_HELPER_PATH]['previousSha256'] = '0'*64
            else:
                value['files'][layer.FINAL_HELPER_PATH]['deltas'][0]['current'] += ' unknown hunk'
            with self.assertRaises(ValueError):
                layer.profile_manifest_input(value)
        with self.assertRaises(ValueError):
            layer.profile_manifest_input(None)

    def test_missing_duplicate_moved_or_extra_helper_code_rejected_by_original_guards(self):
        current = (ROOT/layer.FINAL_HELPER_PATH).read_bytes(); branch = layer.FINAL_BRANCH.encode()
        missing = current.replace(branch, b'', 1)
        variants = [missing, current.replace(branch, branch*2, 1),
                    current.replace(branch, branch+b' ', 1), missing+branch,
                    current+b'# unknown extra code\n']
        for raw in variants:
            with self.assertRaises(ValueError):
                final.metadata_input(raw, layer.FINAL_HELPER_PATH)
            # The existing complete-preimage and unique-context guards remain
            # necessary even if a counterfeit changes only the current pin.
            with patch.object(layer, 'FINAL_CURRENT_SHA256', SHA(raw)), \
                    patch.object(layer, 'FINAL_CURRENT_BYTES', len(raw)), self.assertRaises(ValueError):
                final.metadata_input(raw, layer.FINAL_HELPER_PATH)

    def test_old_root_guards_and_current_runtime_call_sites_stay_raw(self):
        raw = prior_metadata_input((ROOT/'tests/profile_fixture_root_source_compatibility.py').read_bytes(), 'tests/profile_fixture_root_source_compatibility.py')
        hook = (b'    from connections_admission_metadata_compatibility import profile_manifest_input\n'
                b'    return profile_manifest_input(value)\n')
        self.assertEqual(raw.count(hook), 1)
        restored = raw.replace(hook, b'    return value\n', 1)
        self.assertEqual(SHA(restored), 'b7faf23d5e5771fd09af2cbbaddedc6c370e557b65b3bdd612f56d095a76433f')
        for name in ('source_input', '_path'):
            body = lambda source: next(ast.get_source_segment(source.decode(), node)
                                      for node in ast.parse(source).body
                                      if isinstance(node, ast.FunctionDef) and node.name == name)
            self.assertEqual(body(raw), body(restored))
        runtime = (ROOT/'tests/network-internal-admission-host/run.py').read_text()
        self.assertNotIn('metadata_input', runtime)
        self.assertNotIn('source_compatibility', runtime)
        self.assertIn('source = fixture.read_text()', runtime)
        allowed = {'tests/final_browser_source_compatibility.py',
                   'tests/profile_fixture_root_source_compatibility.py',
                   'tests/profile_connections_admission_metadata_compatibility_test.py'}
        imports = set()
        for folder in ('app', 'tests', 'tools'):
            for path in (ROOT/folder).rglob('*.py'):
                for node in ast.walk(ast.parse(path.read_bytes())):
                    if (isinstance(node, ast.ImportFrom) and node.module == 'connections_admission_metadata_compatibility'
                            or isinstance(node, ast.Import) and any(item.name == 'connections_admission_metadata_compatibility' for item in node.names)):
                        imports.add(path.relative_to(ROOT).as_posix())
        self.assertEqual(imports, allowed)


if __name__ == '__main__':
    unittest.main(verbosity=2)
