"""Exercise the finite final metadata boundary against real historical objects.

These controls never run Android, behavior hosts, publishing or a network fetch.
Actual workflow and publisher statements below consume current raw source.
"""
import ast
import copy
from functools import lru_cache
import hashlib
import itertools
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import cpu_ip_source_compatibility as cpu
import final_browser_source_compatibility as layer
from profile_fixture_root_source_compatibility import historical_input as fixture_root_input
import profile_ip_timezone_source_compatibility_test as retained_ip
import profile_worker_timezone_source_compatibility_test as retained_worker
import tls_cpu_ip_source_compatibility as tls

ROOT = Path(__file__).resolve().parents[1]
B = 'e20667d7e407e28645a59617683211fdd1345039'
B_TREE = '744dbee43dd4721a026f391b8874c3b7c72d9634'
S = 'e4a20469326f16dc8ff8cfabd4fe67bf3d0148de'
S_TREE = 'cdbe45cb204a655781f4719598ec3d7e88735a6a'
P = '972b7767300587af98b3f4a2088a44dd30af8098'
P_TREE = '7da3a44c2b9c1f2d85623ac908a23154144ea045'
GV = 'app/src/main/java/local/pocketchat/GeckoWebView.java'
CHAT = 'app/src/main/java/local/pocketchat/ChatSession.java'
CPU_FIXTURE = 'tests/fixtures/cpu-ip-source-deltas.json'
OLD_CPU_SHA = '66c9b3643b26edb54b0c371c2053d56e482efcce2035aa1ca067fdead8f48e5a'
IP_FIXTURE = 'tests/fixtures/ip-timezone-source-deltas.json'
IP_SHA = '2a84a6ac4cb8246ea633d314bbcc9b75b8ab9e180507e6a7017533519106c0bb'
FINAL_SHA = '8bb0bb6580879fcef6258f48e57fbdce19304c0d3ea0061131d993b815877a16'
INVENTORY_115_PINS = {'tests/baselines/public-source-history.json': ('3a25f8963e7571f7e8c33f48998d67381d595896bc942aca227a71e48cf5ae17', 34730), 'tools/browser/source_history.py': ('4924f0255fccc91bcbaf34a31a893471ba3d77957420c6f704b524845e22080c', 8992)}

INVENTORY_116_PINS = {'tests/baselines/public-source-history.json': ('84ee908575ae516d65adceac8cfddaafcc0f86a3d8cd82584c689e9b0699b230', 35166), 'tools/browser/source_history.py': ('43d6c0c5778fc1c4fbb4a7ae43e1ddf42a2dc30aa7a7cdffd9ee65cdfc40e33c', 8992)}
INVENTORY_CLEANUP_CONTEXT_COUNTS = {'tests/baselines/public-source-history.json': 12, 'tools/browser/source_history.py': 1}

PUBLISHER_METADATA_PINS = {
    'tests/browser_fingerprint_publish_gate_test.py':
        '40f681d0b10ea17893a93c40b6eb3519b7433196d63b4b393167a15cb8f5c9e8',
    'tests/browser_environment_publish_gate_test.py':
        '0a4e1e86f17fee638613e48980b3f426c37627826ad12f72a8533fcf47e0a97b',
}
CPU_PUBLICATION_PATH = 'tests/browser_cpu_publish_gate_test.py'
CPU_PUBLICATION_SHA = '49e19922d9e253976fc2da4b0092f4701db14a00cb52cb7d32e3f949dccb6301'
CPU_PUBLICATION_BODY_SHA = '8304bd6a9a4acf95aeb64a2f5caa1a97491dfed46b76b02c4e1816414a75e8cb'
B_PATHS = frozenset((GV, 'tests/ip_timezone_source_compatibility.py',
    'tests/profile_ip_timezone_source_compatibility_test.py',
    'tests/baselines/public-source-history.json', 'tools/browser/source_history.py'))
S_PATHS = frozenset(('tests/cpu_ip_source_compatibility.py', CPU_FIXTURE,
    'tests/profile_cpu_ip_source_compatibility_test.py',
    'tests/browser_acceptance_workflow_test.py',
    'tests/gecko-addon-lifecycle-host/AddonHost.java.in',
    'tests/gecko-addon-lifecycle-host/run.py',
    'tests/worker_timezone_host_source_compatibility.py',
    'tests/profile_worker_timezone_host_source_compatibility_test.py',
    'tests/worker_timezone_source_compatibility.py',
    'tests/profile_worker_timezone_source_compatibility_test.py',
    'tests/profile_dual_browser_source_compatibility_test.py',
    'tests/browser_fingerprint_publish_gate_test.py',
    'tests/browser_environment_publish_gate_test.py'))
SHA = lambda raw: hashlib.sha256(raw).hexdigest()


def current_context(relative, row, delta):
    """Map a declared context to its unique span in the exact raw current image."""
    chunk = delta['current'].encode()
    if relative not in INVENTORY_115_PINS:
        return chunk
    current = (ROOT/relative).read_bytes()
    if (SHA(current), len(current)) != (row['reviewedSha256'], row['reviewedBytes']):
        raise ValueError('Current catalog context requires its exact whole image')
    index = next(i for i, item in enumerate(row['deltas']) if item['id'] == delta['id'])
    later = row['deltas'][index+1:]
    phase = current
    for tail in reversed(later):
        after, before = tail['current'].encode(), tail['previous'].encode()
        if phase.count(after) != 1:
            raise ValueError('Catalog context inverse must be unique')
        phase = phase.replace(after, before, 1)
    if phase.count(chunk) != 1:
        raise ValueError('Original catalog context must occur once at its own phase')
    left = phase.index(chunk)
    right = left + len(chunk)
    for tail in later:
        before, after = tail['previous'].encode(), tail['current'].encode()
        if phase.count(before) != 1:
            raise ValueError('Catalog context forward replay must be unique')
        a = phase.index(before)
        b = a + len(before)
        change = len(after) - len(before)
        if b <= left:
            left += change
            right += change
        elif a < right:
            left = min(left, a)
            right = max(right, b) + change
        phase = phase.replace(before, after, 1)
    if phase != current or not 0 <= left < right <= len(current):
        raise ValueError('Catalog context replay did not restore the whole current image')
    mapped = phase[left:right]
    if current.count(mapped) != 1:
        raise ValueError('Mapped catalog context must be unique in raw current source')
    return mapped


def tagged_current_context(relative, row, delta):
    """Independent byte-label oracle for the numeric position replay above."""
    current = (ROOT/relative).read_bytes()
    index = next(i for i, item in enumerate(row['deltas']) if item['id'] == delta['id'])
    later = row['deltas'][index+1:]
    phase = current
    for tail in reversed(later):
        after, before = tail['current'].encode(), tail['previous'].encode()
        if phase.count(after) != 1:
            raise ValueError('Tagged context requires a unique inverse')
        phase = phase.replace(after, before, 1)
    chunk = delta['current'].encode()
    if phase.count(chunk) != 1:
        raise ValueError('Tagged original context must be unique')
    start = phase.index(chunk)
    tags = bytearray(len(phase))
    tags[start:start+len(chunk)] = b'\x01'*len(chunk)
    for tail in later:
        before, after = tail['previous'].encode(), tail['current'].encode()
        if phase.count(before) != 1:
            raise ValueError('Tagged context requires a unique forward edit')
        start = phase.index(before)
        stop = start + len(before)
        inherited = any(tags[start:stop])
        tags[start:stop] = bytes([inherited])*len(after)
        phase = phase.replace(before, after, 1)
    if phase != current or len(tags) != len(current):
        raise ValueError('Tagged replay must restore the complete raw source')
    start = tags.index(1)
    stop = len(tags) - tags[::-1].index(1)
    if not all(tags[start:stop]):
        raise ValueError('Tagged context must remain contiguous')
    return current[start:stop]


def inventory_116_input(raw, relative, value):
    """A strictly checked historical left input for the retained116-tail proof."""
    restored = raw
    for tail in reversed(value['files'][relative]['deltas'][-INVENTORY_CLEANUP_CONTEXT_COUNTS[relative]:]):
        current, previous = tail['current'].encode(), tail['previous'].encode()
        if restored.count(current) != 1:
            raise ValueError('Cleanup catalog tail must occur exactly once')
        restored = restored.replace(current, previous, 1)
    if (SHA(restored), len(restored)) != INVENTORY_116_PINS[relative]:
        raise ValueError('Cleanup catalog tail did not restore the exact116 image')
    return restored


def build_budget_helper_before(raw):
    from profile_fixture_root_source_compatibility import historical_input as fixture_root_input
    raw = fixture_root_input(raw, 'tests/final_browser_source_compatibility.py')
    constants = b'# BEGIN_BUILD_BUDGET_METADATA\nBUILD_BUDGET_PATH = \'tests/browser_acceptance_workflow_test.py\'\nBUILD_BUDGET_PREVIOUS_SHA256 = \'2792c0919de89b13eb9040660be96f7c3ba55cf689e54abd075646f103e479bf\'\nBUILD_BUDGET_PREVIOUS_BYTES = 7205\nBUILD_BUDGET_CURRENT_SHA256 = \'655d7a4a385aa9d0d6684807a177035ee177a8470eb396a6f7da3efe0759db71\'\nBUILD_BUDGET_CURRENT_BYTES = 7668\nBUILD_BUDGET_PREVIOUS = b"        for name,job in self.old[\'jobs\'].items():\\n            with self.subTest(job=name):\\n                current=self.new[\'jobs\'][name];position=0\\n                for step in job[\'steps\']:\\n                    found=next((at for at in range(position,len(current[\'steps\'])) if current[\'steps\'][at]==step),None)\\n                    self.assertIsNotNone(found,(name,step.get(\'name\')));position=found+1\\n                for key,value in job.items():\\n                    if key==\'steps\':continue\\n                    self.assertEqual(current[key],value+[\'browser\',\'tls\'] if name==\'verify\' and key==\'needs\' else value)\\n    def test_single_pipeline_shares_actual_apk_and_gates_browser(self):\\n        self.assertEqual(self.new[\'on\'][\'push\'][\'branches\'],[\'release/browser-2.1.0\',\'release/browser-2.1.0-*\',\'release/browser-2.1.1\',\'release/browser-2.1.1-*\',\'release/browser-2.1.2\',\'release/browser-2.1.2-*\',\'release/browser-2.1.3\',\'release/browser-2.1.3-*\',\'release/browser-2.1.4\',\'release/browser-2.1.4-*\'])\\n        self.assertIn(\'browser\',self.new[\'jobs\'][\'verify\'][\'needs\'])\\n        self.assertEqual(self.new[\'jobs\'][\'browser\'][\'needs\'],\'build\')\\n        browser=self.new[\'jobs\'][\'browser\'];self.assertNotIn(\'continue-on-error\',browser)\\n        body=\'\\\\n\'.join(step.get(\'run\',\'\') for step in browser[\'steps\'])\\n"\nBUILD_BUDGET_CURRENT = b"        for name,job in self.old[\'jobs\'].items():\\n            with self.subTest(job=name):\\n                current=self.new[\'jobs\'][name];position=0\\n                for step in job[\'steps\']:\\n                    found=next((at for at in range(position,len(current[\'steps\'])) if current[\'steps\'][at]==step),None)\\n                    self.assertIsNotNone(found,(name,step.get(\'name\')));position=found+1\\n                if name==\'build\':\\n                    self.assertIn(\'timeout-minutes\',job)\\n                for key,value in job.items():\\n                    if key==\'steps\':continue\\n                    if name==\'build\' and key==\'timeout-minutes\':\\n                        self.assertIs(type(value),int)\\n                        self.assertEqual(value,40)\\n                        self.assertIn(key,current)\\n                        self.assertIs(type(current[key]),int)\\n                        self.assertEqual(current[key],60)\\n                    else:\\n                        self.assertEqual(current[key],value+[\'browser\',\'tls\'] if name==\'verify\' and key==\'needs\' else value)\\n    def test_single_pipeline_shares_actual_apk_and_gates_browser(self):\\n        self.assertEqual(self.new[\'on\'][\'push\'][\'branches\'],[\'release/browser-2.1.0\',\'release/browser-2.1.0-*\',\'release/browser-2.1.1\',\'release/browser-2.1.1-*\',\'release/browser-2.1.2\',\'release/browser-2.1.2-*\',\'release/browser-2.1.3\',\'release/browser-2.1.3-*\',\'release/browser-2.1.4\',\'release/browser-2.1.4-*\'])\\n        self.assertIn(\'browser\',self.new[\'jobs\'][\'verify\'][\'needs\'])\\n        self.assertEqual(self.new[\'jobs\'][\'browser\'][\'needs\'],\'build\')\\n        browser=self.new[\'jobs\'][\'browser\'];self.assertNotIn(\'continue-on-error\',browser)\\n        body=\'\\\\n\'.join(step.get(\'run\',\'\') for step in browser[\'steps\'])\\n"\n# END_BUILD_BUDGET_METADATA\n'
    hook = b"    if (relative == BUILD_BUDGET_PATH and (digest, len(raw)) not in\n            ((row['previousSha256'], row['previousBytes']), (row['reviewedSha256'], row['reviewedBytes']))):\n        raw = build_budget_input(raw, relative)\n        digest = _sha(raw)\n"
    if raw.count(constants) != 1 or raw.count(hook) != 1:
        raise ValueError('Build budget helper declarations differ')
    start = raw.index(b'\ndef build_budget_input(')
    stop = raw.index(b'\ndef p2_input(', start)
    if SHA(raw[start:stop]) != 'dfa10e03705773a047ec4773c530bebbe11b6637aa12f0584784d79cd88dd44f':
        raise ValueError('Build budget helper body differs')
    restored = raw[:start]+raw[stop:]
    restored = restored.replace(constants, b'', 1).replace(hook, b'', 1)
    if SHA(restored) != '0c24e81a178476e79907f84d107c5539e5b7d872bbcff866844d36e81238ef4d':
        raise ValueError('Build budget helper inverse did not restore its complete before image')
    return restored


@lru_cache(maxsize=None)
def git(*parts):
    return subprocess.check_output(['git', '--no-replace-objects', *parts], cwd=ROOT,
        timeout=30, env=dict(os.environ, GIT_NO_LAZY_FETCH='1',
                            GIT_OPTIONAL_LOCKS='0', GIT_TERMINAL_PROMPT='0'))


def assertions(raw):
    return [node for node in ast.walk(ast.parse(raw))
        if isinstance(node, ast.Assert) or isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute) and node.func.attr.startswith('assert')]


def dumps(nodes):
    return [ast.dump(node, include_attributes=False) for node in nodes]


def test_methods(raw):
    return [node.name for node in ast.walk(ast.parse(raw))
        if isinstance(node, ast.FunctionDef) and node.name.startswith('test_')]


def compiled(source, name):
    namespace = {'__file__': str(ROOT/'tests/final_browser_source_compatibility.py'),
                 '__name__': name}
    exec(compile(source, '<'+name+'>', 'exec'), namespace)
    return namespace


class FinalBrowserHistoricalSources(unittest.TestCase):
    def test_nineteen_real_predecessors_complete_forward_and_inverse(self):
        provenance = {relative: (B, B_TREE) for relative in B_PATHS}
        provenance.update({relative: (S, S_TREE) for relative in S_PATHS})
        provenance[CHAT] = (P, P_TREE)
        self.assertEqual(layer.PROVENANCE, provenance)
        self.assertEqual(layer.PATHS, B_PATHS | S_PATHS | {CHAT})
        self.assertEqual(len(layer.PATHS), 19)
        self.assertEqual(layer.MAX_FIXTURE_BYTES, 1024*1024)
        self.assertEqual(layer.MAX_SOURCE_BYTES, 256*1024)
        value = layer.manifest()
        self.assertEqual(set(value['files']), set(provenance))
        self.assertIs(value['actualAndroidExecution'], False)
        self.assertIs(value['runtimeAcceptance'], False)
        for commit, tree in ((B, B_TREE), (S, S_TREE), (P, P_TREE)):
            self.assertEqual(git('rev-parse', commit+'^{tree}').decode().strip(), tree)
        contexts = 0
        for relative, row in value['files'].items():
            with self.subTest(path=relative):
                commit, tree = provenance[relative]
                self.assertEqual((row['previousCommit'], row['previousTree']), (commit, tree))
                before = git('show', commit+':'+relative)
                current = layer.build_budget_input(fixture_root_input((ROOT/relative).read_bytes(), relative), relative)
                self.assertEqual((SHA(before), len(before)), (row['previousSha256'], row['previousBytes']))
                self.assertEqual((SHA(current), len(current)), (row['reviewedSha256'], row['reviewedBytes']))
                self.assertEqual(row['contextLines'], 6)
                self.assertEqual(layer.source_input(before, relative), before)
                self.assertEqual(layer.source_input(current, relative), before)
                forward, inverse = before, current
                for index, delta in enumerate(row['deltas']):
                    previous, after = delta['previous'].encode(), delta['current'].encode()
                    self.assertEqual(delta['id'], 'context-%02d' % index)
                    self.assertEqual((SHA(previous), SHA(after)),
                        (delta['previousSha256'], delta['currentSha256']))
                    self.assertEqual(forward.count(previous), 1)
                    self.assertEqual(current.count(current_context(relative, row, delta)), 1)
                    forward = forward.replace(previous, after, 1)
                    contexts += 1
                for delta in reversed(row['deltas']):
                    after, previous = delta['current'].encode(), delta['previous'].encode()
                    self.assertEqual(inverse.count(after), 1)
                    inverse = inverse.replace(after, previous, 1)
                self.assertEqual(forward, current)
                self.assertEqual(inverse, before)
        self.assertEqual(contexts - 1 - len(INVENTORY_115_PINS) - sum(INVENTORY_CLEANUP_CONTEXT_COUNTS.values()), 43)
        previous_paths = layer.PATHS-PUBLISHER_METADATA_PINS.keys()
        self.assertEqual(len(previous_paths), 17)
        self.assertEqual(sum(len(value['files'][relative]['deltas']) for relative in previous_paths) - 1 - len(INVENTORY_115_PINS) - sum(INVENTORY_CLEANUP_CONTEXT_COUNTS.values()), 41)

    def test_every_context_rejects_missing_duplicate_changed_moved_and_unknown_images(self):
        rejected = 0
        value = layer.manifest()
        for relative, row in value['files'].items():
            current = layer.build_budget_input(fixture_root_input((ROOT/relative).read_bytes(), relative), relative)
            # The appended P2 context has its own complete-image controls below.
            for delta in (row['deltas'][:-1] if relative == GV else row['deltas'][:-(1 + INVENTORY_CLEANUP_CONTEXT_COUNTS[relative])] if relative in INVENTORY_115_PINS else row['deltas']):
                chunk = current_context(relative, row, delta)
                remainder = current.replace(chunk, b'', 1)
                moved = remainder+chunk
                if moved == current:
                    moved = chunk+remainder
                candidates = (remainder, current.replace(chunk, chunk*2, 1),
                    current.replace(chunk, chunk+b' ', 1), moved,
                    current[:-1], b'unknown complete image\n'+current)
                for candidate in candidates:
                    self.assertNotEqual(candidate, current)
                    with self.subTest(path=relative, context=delta['id'], mutation=SHA(candidate)), self.assertRaises(ValueError):
                        layer.source_input(candidate, relative)
                    rejected += 1
        self.assertEqual(rejected, 258)

    def test_source_types_paths_and_whole_identity_precede_inversion(self):
        raw = (ROOT/GV).read_bytes()
        for bad in (None, raw.decode(), bytearray(raw), memoryview(raw), raw[:100],
                    b'x'*(layer.MAX_SOURCE_BYTES+1)):
            with self.assertRaises(ValueError):
                layer.source_input(bad, GV)
        for bad in (None, Path(GV), '/'+GV, './'+GV, '../'+GV, GV+'/',
                    GV.replace('/', '//', 1), 'tests/../'+GV, 'tests/foreign.py'):
            with self.assertRaises(ValueError):
                layer.source_input(raw, bad)
        class Forbidden:
            def encode(self, *args):
                raise AssertionError('Unknown whole source reached contextual inversion')
        counterfeit = copy.deepcopy(layer.manifest())
        counterfeit['files'][GV]['deltas'][0]['current'] = Forbidden()
        with patch.object(layer, 'manifest', return_value=counterfeit), \
                patch.object(tls, 'source_input', side_effect=AssertionError('Unknown source reached TLS')), \
                patch.object(cpu, 'source_input', side_effect=AssertionError('Unknown source reached CPU')), \
                self.assertRaisesRegex(ValueError, 'unknown whole source'):
            layer.source_input(raw+b' ', GV)

    def test_fixture_whole_pin_types_duplicates_nonfinite_and_json_shape(self):
        raw = layer.DELTA_PATH.read_bytes()
        self.assertEqual(layer.DELTA_SHA256, FINAL_SHA)
        self.assertEqual(SHA(raw), layer.DELTA_SHA256)
        for bad in (None, raw.decode(), bytearray(raw), memoryview(raw), b'',
                    raw+b'\n', b' '+raw, raw[:-1], b'x'*(layer.MAX_FIXTURE_BYTES+1)):
            with self.assertRaises(ValueError):
                layer._decode(bad)
        duplicate = raw.replace(b'"schema": 1', b'"schema": 1, "schema": 1', 1)
        self.assertNotEqual(duplicate, raw)
        nonfinite = [raw.replace(b'"schema": 1', b'"schema": '+word, 1)
                     for word in (b'NaN', b'Infinity', b'-Infinity')]
        for changed in (duplicate, *nonfinite, b'[]', b'true', b'{broken json'):
            with patch.object(layer, 'DELTA_SHA256', SHA(changed)), self.assertRaises(ValueError):
                layer._decode(changed)

    def test_counterfeit_schema_provenance_oracles_types_and_bounds_reject(self):
        original = layer.manifest()
        variants = []
        for key, value in (('schema', True), ('kind', 'runtime-acceptance'),
                ('actualAndroidExecution', True), ('runtimeAcceptance', True),
                ('oracle', 'replacement'), ('baseCommit', B), ('files', [])):
            changed = copy.deepcopy(original); changed[key] = value; variants.append(changed)
        for relative, commit, tree in ((GV, S, S_TREE), (CPU_FIXTURE, B, B_TREE)):
            for key, value in (('previousCommit', commit), ('previousTree', tree),
                    ('previousBytes', True), ('previousBytes', 0),
                    ('reviewedBytes', layer.MAX_SOURCE_BYTES+1), ('contextLines', True),
                    ('contextLines', 2), ('contextLines', 17), ('reviewedSha256', 'x'*64),
                    ('reviewedSha256', original['files'][relative]['previousSha256']),
                    ('deltas', []), ('deltas', [original['files'][relative]['deltas'][0]]*65),
                    ('oracle', 'replacement')):
                changed = copy.deepcopy(original); changed['files'][relative][key] = value; variants.append(changed)
        for key, value in (('id', 'context-99'), ('previous', False), ('previous', ''),
                ('current', 'x'*(32*1024+1)), ('currentSha256', '0'*64),
                ('oracle', 'replacement')):
            changed = copy.deepcopy(original); changed['files'][GV]['deltas'][0][key] = value; variants.append(changed)
        for key, value in (('previousCommit', B), ('previousTree', B_TREE)):
            changed = copy.deepcopy(original); changed['files'][CHAT][key] = value; variants.append(changed)
        changed = copy.deepcopy(original); changed['files'].pop(GV); variants.append(changed)
        changed = copy.deepcopy(original); changed['files']['tests/foreign.py'] = changed['files'][GV]; variants.append(changed)
        for changed in variants:
            raw = json.dumps(changed).encode()
            with patch.object(layer, 'DELTA_SHA256', SHA(raw)), self.assertRaises(ValueError):
                layer._decode(raw)
        self.assertEqual(len(variants), 43)
        changed = copy.deepcopy(original)
        for row in changed['files'].values():
            row['deltas'] = [dict(id='context-%02d' % index,
                previous='previous-%02d' % index, current='current-%02d' % index,
                previousSha256=SHA(('previous-%02d' % index).encode()),
                currentSha256=SHA(('current-%02d' % index).encode())) for index in range(20)]
        raw = json.dumps(changed).encode()
        self.assertLess(len(raw), layer.MAX_FIXTURE_BYTES)
        with patch.object(layer, 'DELTA_SHA256', SHA(raw)), self.assertRaisesRegex(ValueError, 'contexts exceed'):
            layer._decode(raw)

    def test_fixture_symlink_parent_alias_foreign_path_and_file_bound(self):
        raw = layer.DELTA_PATH.read_bytes()
        with tempfile.TemporaryDirectory(prefix='final-history-path-') as folder:
            root = Path(folder)
            path = root/'tests/fixtures/final-browser-source-deltas.json'
            path.parent.mkdir(parents=True)
            target = root/'ordinary'; target.write_bytes(raw)
            path.symlink_to(target)
            with patch.object(layer, 'ROOT', root), patch.object(layer, 'DELTA_PATH', path), self.assertRaises(ValueError):
                layer.manifest()
            path.unlink()
            for changed in (b'', b'x'*(layer.MAX_FIXTURE_BYTES+1)):
                path.write_bytes(changed)
                with patch.object(layer, 'ROOT', root), patch.object(layer, 'DELTA_PATH', path), self.assertRaises(ValueError):
                    layer.manifest()
            path.write_bytes(raw)
            with patch.object(layer, 'ROOT', root), patch.object(layer, 'DELTA_PATH', path):
                from resource_startup_source_compatibility import frozen_manifest_input
                self.assertEqual(frozen_manifest_input(layer.manifest()), layer._decode(raw))
        with tempfile.TemporaryDirectory(prefix='final-history-parent-') as folder:
            root = Path(folder); outside = root/'ordinary'; outside.mkdir()
            (outside/'final-browser-source-deltas.json').write_bytes(raw)
            (root/'tests').mkdir()
            (root/'tests/fixtures').symlink_to(outside, target_is_directory=True)
            with patch.object(layer, 'ROOT', root), patch.object(layer, 'DELTA_PATH', root/'tests/fixtures/final-browser-source-deltas.json'), self.assertRaises(ValueError):
                layer.manifest()
        with patch.object(layer, 'DELTA_PATH', ROOT/'tests/fixtures/unreviewed.json'), self.assertRaises(ValueError):
            layer.manifest()

    def test_metadata_left_inputs_only_and_original_ip_seven_path_boundary(self):
        for relative, row in layer.manifest()['files'].items():
            self.assertEqual(layer.metadata_input((ROOT/relative).read_bytes(), relative),
                git('show', row['previousCommit']+':'+relative))
        for relative in tls.TEMPLATE_PATHS:
            self.assertEqual(layer.metadata_input((ROOT/relative).read_bytes(), relative),
                tls.source_input((ROOT/relative).read_bytes(), relative))
        relative = 'tests/fixtures/unowned-metadata.json'
        for raw in (b'', b'unknown source still faces the original golden',
                    b'x'*(layer.MAX_SOURCE_BYTES+1)):
            self.assertIs(layer.metadata_input(raw, relative), raw)
        for bad in (None, 'source', bytearray(b'source'), b'x'*(layer.MAX_METADATA_BYTES+1)):
            with self.assertRaises(ValueError):
                layer.metadata_input(bad, relative)
        for bad in (None, Path(relative), '/'+relative, './'+relative, '../'+relative,
                    'tests/../'+relative, 'tests//foreign.py', 'tests\\foreign.py',
                    'tests/foreign\0.py', '.git/config', '', '.', 'tests'):
            for entry in (layer.metadata_input, layer.ip_input):
                with self.assertRaises(ValueError):
                    entry(b'raw metadata', bad)
        overlay = retained_ip.overlay
        self.assertEqual(layer.IP_PATHS, overlay.PATHS)
        self.assertEqual(len(layer.IP_PATHS), 7)
        self.assertEqual(layer.ip_input((ROOT/GV).read_bytes(), GV), git('show', B+':'+GV))
        for relative in overlay.PATHS-{GV}:
            raw = (ROOT/relative).read_bytes()
            self.assertIs(layer.ip_input(raw, relative), raw)
            unknown = b'unknown complete source'
            self.assertIs(layer.ip_input(unknown, relative), unknown)
            with self.assertRaises(ValueError):
                overlay.source_input(unknown, relative)
        for relative in ('tests/foreign.py', CPU_FIXTURE, CHAT):
            with self.assertRaises(ValueError):
                layer.ip_input(b'raw', relative)
        self.assertEqual({layer.GV, layer.CHAT}, {GV, CHAT})
        for relative, commit in ((GV, B), (CHAT, P)):
            raw = (ROOT/relative).read_bytes()
            self.assertEqual(layer.producer_input(raw, relative), git('show', commit+':'+relative))
            for bad in (None, raw.decode(), bytearray(raw), memoryview(raw), raw[:100], raw+b' '):
                with self.assertRaises(ValueError):
                    layer.producer_input(bad, relative)
        for relative in ('tests/foreign.py', CPU_FIXTURE, 'tests/worker_timezone_source_compatibility.py',
                         '/'+GV, './'+CHAT, '../'+CHAT, Path(CHAT), None, '.', 'tests'):
            with self.assertRaises(ValueError):
                layer.producer_input(b'raw', relative)

    def test_both_producers_call_actual_tls_then_cpu_and_check_their_independent_inverse(self):
        for relative, commit in ((GV, B), (CHAT, P)):
            after = (ROOT/relative).read_bytes()
            current = layer.p2_input(after, relative)
            cpu_source = git('show', S+':'+relative)
            public_before = git('show', commit+':'+relative)
            calls = []
            actual_tls, actual_cpu = tls.source_input, cpu.source_input
            def traced_tls(raw, path):
                calls.append(('tls', raw, path))
                result = actual_tls(raw, path)
                self.assertEqual(result, cpu_source)
                return result
            def traced_cpu(raw, path):
                calls.append(('cpu', raw, path))
                result = actual_cpu(raw, path)
                self.assertEqual(result, public_before)
                return result
            with patch.object(tls, 'source_input', side_effect=traced_tls), \
                    patch.object(cpu, 'source_input', side_effect=traced_cpu):
                self.assertEqual(layer.source_input(after, relative), public_before)
            self.assertEqual(calls, [('tls', current, relative), ('cpu', cpu_source, relative)])
            with patch.object(cpu, 'source_input', return_value=public_before+b'counterfeit pipeline'), \
                    self.assertRaisesRegex(ValueError, 'TLS and canonical CPU inverse'):
                layer.source_input(after, relative)
            changed = copy.deepcopy(layer.manifest())
            changed['files'][relative]['deltas'][0]['current'] = 'missing independent final context'
            with patch.object(layer, 'manifest', return_value=changed), \
                    patch.object(tls, 'source_input', return_value=cpu_source) as tls_call, \
                    patch.object(cpu, 'source_input', return_value=public_before) as cpu_call, \
                    self.assertRaisesRegex(ValueError, 'each contextual edit exactly once'):
                layer.source_input(after, relative)
            tls_call.assert_called_once_with(current, relative)
            cpu_call.assert_called_once_with(cpu_source, relative)

    def test_canonical_cpu_fixture_actual_pin_and_nine_original_payloads(self):
        current = (ROOT/CPU_FIXTURE).read_bytes()
        previous = git('show', S+':'+CPU_FIXTURE)
        self.assertEqual(SHA(current), cpu.DELTA_SHA256)
        self.assertEqual(SHA(previous), OLD_CPU_SHA)
        self.assertEqual(layer.source_input(current, CPU_FIXTURE), previous)
        self.assertEqual(layer.canonical_cpu_fixture_sha(cpu.DELTA_SHA256), OLD_CPU_SHA)
        before, after = json.loads(previous), json.loads(current)
        self.assertEqual(before['baseCommit'], '114c9a22428ac70f3769cb4f1e3e44a91e9b2ffd')
        self.assertEqual(after['baseCommit'], '972b7767300587af98b3f4a2088a44dd30af8098')
        self.assertEqual(after['baseTree'], '7da3a44c2b9c1f2d85623ac908a23154144ea045')
        after['baseCommit'] = before['baseCommit']
        self.assertEqual(after, before)
        self.assertEqual(current.replace(b'972b7767300587af98b3f4a2088a44dd30af8098',
            b'114c9a22428ac70f3769cb4f1e3e44a91e9b2ffd', 1), previous)
        self.assertEqual(len(before['files']), 2)
        self.assertEqual(sum(len(row['deltas']) for row in before['files'].values()), 9)
        self.assertEqual(cpu.manifest()['files'], before['files'])
        helper = (ROOT/'tests/cpu_ip_source_compatibility.py').read_bytes()
        original_helper = git('show', S+':tests/cpu_ip_source_compatibility.py')
        for current_token, old_token in ((
                b"BASE_COMMIT = '972b7767300587af98b3f4a2088a44dd30af8098'",
                b"BASE_COMMIT = '114c9a22428ac70f3769cb4f1e3e44a91e9b2ffd'"), (
                b"DELTA_SHA256 = '"+cpu.DELTA_SHA256.encode()+b"'",
                b"DELTA_SHA256 = '"+OLD_CPU_SHA.encode()+b"'")):
            self.assertEqual(helper.count(current_token), 1)
            helper = helper.replace(current_token, old_token, 1)
        self.assertEqual(helper, original_helper)
        for bad in (None, True, b'0'*64, '0'*64, OLD_CPU_SHA):
            with patch.object(layer, 'source_input', side_effect=AssertionError('Bad actual pin reached projection')), self.assertRaises(ValueError):
                layer.canonical_cpu_fixture_sha(bad)
        with tempfile.TemporaryDirectory(prefix='final-canonical-cpu-') as folder:
            root = Path(folder)
            foreign = root/'foreign.json'; foreign.write_bytes(current)
            with patch.object(cpu, 'DELTA_PATH', foreign), \
                    patch.object(Path, 'read_bytes', side_effect=AssertionError('Foreign canonical fixture was read')), \
                    self.assertRaises(ValueError):
                layer.canonical_cpu_fixture_sha(cpu.DELTA_SHA256)
            path = root/CPU_FIXTURE; path.parent.mkdir(parents=True)
            path.symlink_to(foreign)
            with patch.object(cpu, 'ROOT', root), patch.object(cpu, 'DELTA_PATH', path), \
                    patch.object(Path, 'read_bytes', side_effect=AssertionError('Symlink canonical fixture was read')), \
                    self.assertRaises(ValueError):
                layer.canonical_cpu_fixture_sha(cpu.DELTA_SHA256)
            path.unlink(); path.write_bytes(current+b'\n')
            with patch.object(cpu, 'ROOT', root), patch.object(cpu, 'DELTA_PATH', path), self.assertRaises(ValueError):
                layer.canonical_cpu_fixture_sha(cpu.DELTA_SHA256)
        with tempfile.TemporaryDirectory(prefix='final-canonical-cpu-parent-') as folder:
            root = Path(folder); ordinary = root/'ordinary'; ordinary.mkdir()
            (ordinary/'cpu-ip-source-deltas.json').write_bytes(current)
            (root/'tests').mkdir()
            (root/'tests/fixtures').symlink_to(ordinary, target_is_directory=True)
            with patch.object(cpu, 'ROOT', root), patch.object(cpu, 'DELTA_PATH', root/CPU_FIXTURE), \
                    patch.object(Path, 'read_bytes', side_effect=AssertionError('Aliased canonical fixture was read')), \
                    self.assertRaises(ValueError):
                layer.canonical_cpu_fixture_sha(cpu.DELTA_SHA256)

    def test_original_ip_fixture_is_still_the_exact_seven_rows_and_forty_two_contexts(self):
        raw = (ROOT/IP_FIXTURE).read_bytes()
        self.assertEqual(SHA(raw), IP_SHA)
        self.assertEqual(raw, git('show', B+':'+IP_FIXTURE))
        overlay = retained_ip.overlay
        self.assertEqual(overlay.DELTA_SHA256, IP_SHA)
        value = overlay.manifest()
        self.assertEqual(len(value['files']), 7)
        self.assertEqual(sum(len(row['deltas']) for row in value['files'].values()), 42)
        for relative, row in value['files'].items():
            current = layer.ip_input((ROOT/relative).read_bytes(), relative)
            self.assertEqual((SHA(current), len(current)), (row['reviewedSha256'], row['reviewedBytes']))
            self.assertEqual(overlay.source_input(current, relative),
                git('show', row['previousCommit']+':'+relative))

    def test_declared_ip_read_hooks_strip_to_whole_B_and_all_nine_original_tests(self):
        helper_path = 'tests/ip_timezone_source_compatibility.py'
        helper = (ROOT/helper_path).read_bytes()
        hook = b"    if (digest, len(raw)) != (row['reviewedSha256'], row['reviewedBytes']):\n        from final_browser_source_compatibility import ip_input\n        raw = ip_input(raw, relative)\n        digest = _sha(raw)\n"
        self.assertEqual(helper.count(hook), 1)
        helper = helper.replace(hook, b'', 1)
        hook = b'    if relative in PATHS:\n        return source_input(raw, relative)\n    from final_browser_source_compatibility import metadata_input\n    return metadata_input(raw, relative)\n'
        self.assertEqual(helper.count(hook), 1)
        helper = helper.replace(hook, b'    return source_input(raw, relative) if relative in PATHS else raw\n', 1)
        self.assertEqual(helper, git('show', B+':'+helper_path))
        relative = 'tests/profile_ip_timezone_source_compatibility_test.py'
        current, previous = (ROOT/relative).read_bytes(), git('show', B+':'+relative)
        restored = current
        for token in (b'from final_browser_source_compatibility import ip_input as final_ip_input, metadata_input as final_metadata_input\n',
                b'                after = final_ip_input(after, relative)\n',
                b'            current = final_ip_input(current, relative)\n',
                b'        after = final_metadata_input(after, relative)\n'):
            self.assertEqual(restored.count(token), 1)
            restored = restored.replace(token, b'', 1)
        token = b"final_metadata_input((ROOT / 'tests/baselines/public-source-history.json').read_bytes(), 'tests/baselines/public-source-history.json')"
        self.assertEqual(restored.count(token), 2)
        restored = restored.replace(token, b"(ROOT / 'tests/baselines/public-source-history.json').read_bytes()")
        self.assertEqual(restored, previous)
        self.assertEqual(dumps(assertions(current)), dumps(assertions(previous)))
        self.assertEqual(test_methods(current), test_methods(previous))
        self.assertEqual(len(test_methods(current)), 9)
        self.assertEqual(len(assertions(current)), 46)

    def test_existing_ip_historical_read_keeps_seven_priority_and_exact_metadata_inputs(self):
        overlay = retained_ip.overlay
        final_only = layer.PATHS-overlay.PATHS
        self.assertEqual(len(final_only), 16)
        with tempfile.TemporaryDirectory(prefix='final-ip-historical-read-') as folder:
            root = Path(folder)
            with patch.object(overlay, 'ROOT', root):
                for relative in final_only:
                    current = (ROOT/relative).read_bytes()
                    path = root/relative; path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(current)
                    commit, tree = layer.PROVENANCE[relative]
                    with patch.object(layer, 'metadata_input', wraps=layer.metadata_input) as delegated:
                        self.assertEqual(overlay.historical_read(relative), git('show', commit+':'+relative))
                    delegated.assert_called_once_with(current, relative)
                    path.write_bytes(current+b'unknown metadata edit')
                    with self.assertRaises(ValueError):
                        overlay.historical_read(relative)
                    path.write_bytes(current)
                for relative, row in overlay.manifest()['files'].items():
                    current = (ROOT/relative).read_bytes()
                    path = root/relative; path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(current)
                    with patch.object(layer, 'metadata_input', side_effect=AssertionError('Old IP-owned path lost priority')):
                        self.assertEqual(overlay.historical_read(relative),
                            git('show', row['previousCommit']+':'+relative))
                        path.write_bytes(current+b'unknown source edit')
                        with self.assertRaises(ValueError):
                            overlay.historical_read(relative)
                relative = 'tests/current-runtime.py'
                current = b'actual unrelated runtime bytes\r\n\x00\xff'
                path = root/relative; path.write_bytes(current)
                with patch.object(layer, 'metadata_input', wraps=layer.metadata_input) as delegated:
                    self.assertEqual(overlay.historical_read(relative), current)
                delegated.assert_called_once_with(current, relative)
                relative = 'tests/profile_dual_browser_source_compatibility_test.py'
                path = root/relative; path.unlink()
                target = root/'ordinary'; target.write_bytes((ROOT/relative).read_bytes())
                path.symlink_to(target)
                with patch.object(layer, 'metadata_input', side_effect=AssertionError('Symlink reached metadata delegation')), self.assertRaises(ValueError):
                    overlay.historical_read(relative)

    def test_cpu_read_hooks_strip_to_whole_S_all_golden_rhs_and_original_budgets(self):
        relative = 'tests/profile_cpu_ip_source_compatibility_test.py'
        current, previous = (ROOT/relative).read_bytes(), git('show', S+':'+relative)
        restored = current
        for token in (b'from tls_cpu_ip_source_compatibility import source_input as tls_source_input\n',
                b'from final_browser_source_compatibility import metadata_input as final_metadata_input\n'):
            self.assertEqual(restored.count(token), 1)
            restored = restored.replace(token, b'', 1)
        token = b'after=tls_source_input((ROOT/relative).read_bytes(),relative)'
        self.assertEqual(restored.count(token), 2)
        restored = restored.replace(token, b'after=(ROOT/relative).read_bytes()')
        token = b'final_metadata_input((ROOT/relative).read_bytes(),relative)'
        self.assertEqual(restored.count(token), 1)
        restored = restored.replace(token, b'(ROOT/relative).read_bytes()', 1)
        self.assertEqual(restored, previous)
        before_asserts, after_asserts = assertions(previous), assertions(current)
        self.assertEqual(dumps(assertions(restored)), dumps(before_asserts))
        self.assertEqual(len(before_asserts), 30)
        self.assertEqual(len(after_asserts), 30)
        self.assertEqual(sum(a != b for a, b in zip(dumps(before_asserts), dumps(after_asserts))), 1)
        for before, after in zip(before_asserts, after_asserts):
            if isinstance(before, ast.Call):
                self.assertEqual(dumps(before.args[1:]), dumps(after.args[1:]))
        self.assertEqual(test_methods(current), test_methods(previous))
        self.assertEqual(len(test_methods(current)), 10)
        for left, right in (('rejected', 54), ('len(mutations)', 13)):
            matches = [node for node in after_asserts if isinstance(node, ast.Call)
                       and node.func.attr == 'assertEqual' and len(node.args) == 2
                       and ast.unparse(node.args[0]) == left]
            self.assertEqual(len(matches), 1)
            self.assertEqual(ast.literal_eval(matches[0].args[1]), right)

    def test_two_publisher_metadata_inputs_restore_S_for_the_unchanged_cpu_goldens(self):
        suite = 'tests/profile_cpu_ip_source_compatibility_test.py'
        current_suite = (ROOT/suite).read_bytes()
        previous_suite = git('show', S+':'+suite)
        whole_method_name = 'test_all_original_fixtures_and_preexisting_test_assertions_remain_whole_bytes'
        methods = [next(node for node in ast.walk(ast.parse(raw)) if isinstance(node, ast.FunctionDef)
                        and node.name == whole_method_name) for raw in (previous_suite, current_suite)]
        current_method = methods[1]
        names = next(node.value for node in current_method.body if isinstance(node, ast.Assign)
                     and any(isinstance(target, ast.Name) and target.id == 'tests' for target in node.targets))
        self.assertTrue(PUBLISHER_METADATA_PINS.keys() <= set(ast.literal_eval(names)))
        checks = [[node for node in ast.walk(method) if isinstance(node, ast.Call)
                   and isinstance(node.func, ast.Attribute) and node.func.attr == 'assertEqual']
                  for method in methods]
        self.assertEqual([len(nodes) for nodes in checks], [1, 1])
        self.assertEqual(dumps(checks[0][0].args[1:]), dumps(checks[1][0].args[1:]))
        expected_left = ast.parse('final_metadata_input((ROOT/relative).read_bytes(),relative)', mode='eval').body
        self.assertEqual(dumps([checks[1][0].args[0]]), dumps([expected_left]))
        self.assertEqual(len(assertions(current_suite)), 30)
        self.assertEqual(len(assertions(previous_suite)), 30)
        for relative, reviewed_sha in PUBLISHER_METADATA_PINS.items():
            with self.subTest(path=relative):
                current = (ROOT/relative).read_bytes()
                previous = git('show', S+':'+relative)
                self.assertEqual(SHA(current), reviewed_sha)
                self.assertEqual(layer.PROVENANCE[relative], (S, S_TREE))
                self.assertNotEqual(current, previous)
                self.assertEqual(previous, git('show', cpu.BASE_COMMIT+':'+relative))
                self.assertEqual(layer.source_input(current, relative), previous)
                self.assertEqual(layer.metadata_input(current, relative), previous)
                for changed in (current+b'unknown publisher edit', current[:-1]):
                    with self.assertRaises(ValueError):
                        layer.metadata_input(changed, relative)
                self.assertEqual((ROOT/relative).read_bytes(), current)
                self.assertEqual(SHA((ROOT/relative).read_bytes()), reviewed_sha)

    def test_actual_publisher_sources_stay_current_and_cpu_nine_bodies_stay_unprojected(self):
        histories = {'final_browser_source_compatibility', 'tls_cpu_ip_source_compatibility',
                     'cpu_ip_source_compatibility', 'ip_timezone_source_compatibility',
                     'worker_timezone_source_compatibility', 'dual_browser_source_compatibility'}
        pins = {**PUBLISHER_METADATA_PINS, CPU_PUBLICATION_PATH: CPU_PUBLICATION_SHA}
        for relative, reviewed_sha in pins.items():
            current = (ROOT/relative).read_bytes()
            self.assertEqual(SHA(current), reviewed_sha)
            for node in ast.walk(ast.parse(current)):
                if isinstance(node, ast.ImportFrom):
                    self.assertNotIn((node.module or '').split('.')[-1], histories, relative)
                    self.assertTrue({'source_input', 'metadata_input', 'historical_read'}.isdisjoint(
                        alias.name for alias in node.names), relative)
                elif isinstance(node, ast.Import):
                    self.assertTrue(histories.isdisjoint(alias.name.split('.')[-1] for alias in node.names), relative)
        for relative, count in (('tests/browser_fingerprint_publish_gate_test.py', 13),
                                ('tests/browser_environment_publish_gate_test.py', 18)):
            current, previous = (ROOT/relative).read_bytes(), git('show', S+':'+relative)
            self.assertEqual(dumps(assertions(current)), dumps(assertions(previous)))
            self.assertEqual(len(assertions(current)), count)
            self.assertEqual(test_methods(current), test_methods(previous))
            self.assertEqual(len(test_methods(current)), 3)
        current = (ROOT/CPU_PUBLICATION_PATH).read_bytes()
        self.assertNotIn(CPU_PUBLICATION_PATH, layer.PATHS)
        self.assertNotIn(CPU_PUBLICATION_PATH, layer.PROVENANCE)
        self.assertIs(layer.metadata_input(current, CPU_PUBLICATION_PATH), current)
        changed = current+b'unknown unowned metadata still stays raw'
        self.assertIs(layer.metadata_input(changed, CPU_PUBLICATION_PATH), changed)
        with self.assertRaises(ValueError):
            layer.source_input(current, CPU_PUBLICATION_PATH)
        def bodies(raw):
            tree = ast.parse(raw)
            classes = [node for node in tree.body if isinstance(node, ast.ClassDef)
                       and node.name == 'CpuPublicationTests']
            self.assertEqual(len(classes), 1)
            methods = [node for node in classes[0].body if isinstance(node, ast.FunctionDef)
                       and node.name.startswith('test_')]
            self.assertEqual(len(methods), 9)
            self.assertEqual(len({node.name for node in methods}), 9)
            self.assertEqual(len(test_methods(raw)), 9)
            return {node.name: ast.get_source_segment(raw, node) for node in methods}
        text = current.decode()
        segments = bodies(text)
        digest = lambda parts: SHA(json.dumps(parts, sort_keys=True, ensure_ascii=False).encode())
        self.assertEqual(digest(segments), CPU_PUBLICATION_BODY_SHA)
        self.assertEqual(segments, bodies(git('show', S+':'+CPU_PUBLICATION_PATH).decode()))
        self.assertEqual(sum(len(assertions(segment)) for segment in segments.values()), 41)
        needle = 'self.assertEqual(len(dependencies),1,'
        self.assertEqual(text.count(needle), 1)
        self.assertNotEqual(digest(bodies(text.replace(needle,
            'self.assertEqual(len(dependencies),2,', 1))), CPU_PUBLICATION_BODY_SHA)
        self.assertEqual(SHA((ROOT/CPU_PUBLICATION_PATH).read_bytes()), CPU_PUBLICATION_SHA)

    def test_worker_producer_hooks_strip_to_whole_S_and_preserve_all_original_oracles(self):
        relative = 'tests/worker_timezone_source_compatibility.py'
        current = (ROOT/relative).read_bytes()
        hook = b"    if ((digest, len(raw)) not in ((row['previousSha256'], row['previousBytes']),\n                                  (row['reviewedSha256'], row['reviewedBytes']))\n            and relative == 'app/src/main/java/local/pocketchat/ChatSession.java'):\n        from final_browser_source_compatibility import producer_input\n        raw = producer_input(raw, relative)\n        digest = _sha(raw)\n"
        self.assertEqual(current.count(hook), 1)
        self.assertEqual(current.replace(hook, b'', 1), git('show', S+':'+relative))
        relative = 'tests/profile_worker_timezone_source_compatibility_test.py'
        current, previous = fixture_root_input((ROOT/relative).read_bytes(), relative), git('show', S+':'+relative)
        imported = b'from final_browser_source_compatibility import producer_input as final_producer_input, metadata_input as final_metadata_input\n'
        self.assertEqual(current.count(imported), 1)
        restored = current.replace(imported, b'', 1)
        for indent in (16, 12):
            hook = (b' '*indent+b"after = final_producer_input(after, relative) if relative == 'app/src/main/java/local/pocketchat/ChatSession.java' else after\n")
            self.assertEqual(restored.count(hook), 1)
            restored = restored.replace(hook, b'', 1)
        hook = b'final_metadata_input((ROOT / relative).read_bytes(), relative)'
        self.assertEqual(restored.count(hook), 2)
        restored = restored.replace(hook, b'(ROOT / relative).read_bytes()')
        self.assertEqual(restored, previous)
        self.assertEqual(dumps(assertions(current)), dumps(assertions(previous)))
        self.assertEqual(len(assertions(current)), 49)
        self.assertEqual(test_methods(current), test_methods(previous))
        self.assertEqual(len(test_methods(current)), 8)
        budgets = [(ast.unparse(node.args[0]), ast.literal_eval(node.args[1]))
            for node in assertions(current) if isinstance(node, ast.Call)
            and node.func.attr == 'assertEqual' and len(node.args) == 2
            and isinstance(node.args[1], ast.Constant) and node.args[1].value in (98, 23, 18)]
        self.assertIn(('rejected', 98), budgets)
        self.assertIn(('len(variants)', 18), budgets)
        self.assertEqual(sum(right == 23 for left, right in budgets), 1)
        fixture = 'tests/fixtures/worker-timezone-source-deltas.json'
        raw = (ROOT/fixture).read_bytes()
        self.assertEqual(SHA(raw), '4eafec08cbeb3beb9098ebf5df7b976423616bb213e47e802a1d39315a27602b')
        self.assertEqual(raw, git('show', S+':'+fixture))
        value = retained_worker.overlay.manifest()
        self.assertEqual(len(value['files']), 2)
        self.assertEqual(sum(len(row['deltas']) for row in value['files'].values()), 23)
        for relative, row in value['files'].items():
            after = layer.producer_input((ROOT/relative).read_bytes(), relative)
            if relative in retained_worker.context_paths:
                after = retained_worker.context_source_input(after, relative)
            self.assertEqual((SHA(after), len(after)), (row['reviewedSha256'], row['reviewedBytes']))
            self.assertEqual(retained_worker.overlay.source_input((ROOT/relative).read_bytes(), relative),
                git('show', retained_worker.overlay.BASE_COMMIT+':'+relative))

    def test_dual_producer_hook_strips_to_whole_S_and_keeps_all_native_guard_targets(self):
        relative = 'tests/profile_dual_browser_source_compatibility_test.py'
        current, previous = fixture_root_input((ROOT/relative).read_bytes(), relative), git('show', S+':'+relative)
        restored = current
        for hook in (b'from final_browser_source_compatibility import producer_input as final_producer_input\n',
                     b'            current = final_producer_input(current, relative)\n'):
            self.assertEqual(restored.count(hook), 1)
            restored = restored.replace(hook, b'', 1)
        self.assertEqual(restored, previous)
        self.assertEqual(dumps(assertions(current)), dumps(assertions(previous)))
        self.assertEqual(len(assertions(current)), 57)
        self.assertEqual(test_methods(current), test_methods(previous))
        self.assertEqual(len(test_methods(current)), 9)
        targets = []
        for raw in (previous, current):
            method = next(node for node in ast.walk(ast.parse(raw)) if isinstance(node, ast.FunctionDef)
                          and node.name == 'test_native_protection_and_site_predicate_drift_is_rejected')
            assignment = next(node for node in method.body if isinstance(node, ast.Assign)
                              and any(isinstance(name, ast.Name) and name.id == 'targets' for name in node.targets))
            targets.append(ast.literal_eval(assignment.value))
        self.assertEqual(targets[0], targets[1])
        self.assertEqual(len(targets[0]), 2)
        for relative, previous, current in targets[0]:
            raw = layer.producer_input((ROOT/relative).read_bytes(), relative)
            self.assertIn(previous.encode(), raw)
            self.assertEqual(retained_worker.dual.source_input(raw, relative),
                git('show', retained_worker.dual.BASE_COMMIT+':'+relative))
            with self.assertRaises(ValueError):
                retained_worker.dual.source_input(raw.replace(previous.encode(), current.encode(), 1), relative)
        fixture = 'tests/fixtures/dual-browser-source-deltas.json'
        raw = (ROOT/fixture).read_bytes()
        self.assertEqual(SHA(raw), 'b593b0db2b56b5a5d8143a920fbd15858dafbab21d1cdaf90ca2a5ba164c9933')
        self.assertEqual(raw, git('show', S+':'+fixture))
        value = retained_worker.dual.manifest()
        self.assertEqual(len(value['files']), 9)
        self.assertEqual(sum(len(row['deltas']) for row in value['files'].values()), 28)

    def test_independently_compiled_whole_pin_and_duplicate_counterfeits_are_detected(self):
        source = (ROOT/'tests/final_browser_source_compatibility.py').read_text()
        raw = layer.DELTA_PATH.read_bytes()
        needle = ' or _sha(raw) != DELTA_SHA256'
        self.assertEqual(source.count(needle), 1)
        counterfeit = compiled(source.replace(needle, '', 1), 'final_pin_counterfeit')
        def require_rejection(decode, raw):
            with self.assertRaises(ValueError):
                decode(raw)
        require_rejection(layer._decode, raw+b'\n')
        with self.assertRaises(AssertionError):
            require_rejection(counterfeit['_decode'], raw+b'\n')
        needle = 'object_pairs_hook=_unique'
        self.assertEqual(source.count(needle), 1)
        counterfeit = compiled(source.replace(needle, 'object_pairs_hook=dict', 1), 'final_duplicate_counterfeit')
        duplicate = raw.replace(b'"schema": 1', b'"schema": 1, "schema": 1', 1)
        counterfeit['DELTA_SHA256'] = SHA(duplicate)
        with patch.object(layer, 'DELTA_SHA256', SHA(duplicate)):
            require_rejection(layer._decode, duplicate)
        with self.assertRaises(AssertionError):
            require_rejection(counterfeit['_decode'], duplicate)

    def test_real_execution_rejects_nonclosing_reverse_with_trusted_whole_before_pin(self):
        relative = 'tools/browser/source_history.py'
        current = (ROOT/relative).read_bytes()
        changed = copy.deepcopy(layer.manifest())
        row = changed['files'][relative]
        original_pin = row['previousSha256']
        row['deltas'][0]['previous'] += '\nNONCLOSING_REVERSE\n'
        row['deltas'][0]['previousSha256'] = SHA(row['deltas'][0]['previous'].encode())
        raw = json.dumps(changed).encode()
        with patch.object(layer, 'DELTA_SHA256', SHA(raw)):
            admitted = layer._decode(raw)
        self.assertEqual(admitted['files'][relative]['previousSha256'], original_pin)
        source = (ROOT/'tests/final_browser_source_compatibility.py').read_text()
        guard = "    if len(raw) != row['previousBytes'] or _sha(raw) != row['previousSha256']:\n        raise ValueError('Final browser inverse did not restore the complete public predecessor')\n"
        self.assertEqual(source.count(guard), 1)
        counterfeit = compiled(source.replace(guard, '', 1), 'final_reverse_counterfeit')
        counterfeit['manifest'] = lambda: admitted
        def require_reverse_rejection(source_input):
            with self.assertRaisesRegex(ValueError, 'did not restore the complete public predecessor'):
                source_input(current, relative)
        with patch.object(layer, 'manifest', return_value=admitted):
            require_reverse_rejection(layer.source_input)
        with self.assertRaises(AssertionError):
            require_reverse_rejection(counterfeit['source_input'])

    def test_p2_preserves_all_original_nineteen_rows_and_forty_three_contexts(self):
        from resource_startup_source_compatibility import frozen_manifest_input
        value = copy.deepcopy(frozen_manifest_input(layer.manifest()))
        for path, (digest, size) in INVENTORY_116_PINS.items():
            inventory = value['files'][path]
            del inventory['deltas'][-INVENTORY_CLEANUP_CONTEXT_COUNTS[path]:]
            inventory['reviewedSha256'], inventory['reviewedBytes'] = digest, size
        for path, (digest, size) in INVENTORY_115_PINS.items():
            inventory = value['files'][path]
            inventory['deltas'].pop()
            inventory['reviewedSha256'], inventory['reviewedBytes'] = digest, size
        row = value['files'][GV]
        delta = row['deltas'].pop()
        self.assertEqual(delta['id'], 'context-08')
        self.assertEqual(delta['previousSha256'], '54e26122abfe62c025b895358b0252760fc18e7cf64de33ce6e512feaf8a92dc')
        self.assertEqual(delta['currentSha256'], 'b1cbe60e41482f020fb84afb7853ffab81f427b148bc9fdaba3f6d414df8a99a')
        row['reviewedSha256'] = layer.P2_PREVIOUS_SHA256
        row['reviewedBytes'] = layer.P2_PREVIOUS_BYTES
        previous_fixture = (json.dumps(value, ensure_ascii=False, indent=2)+'\n').encode()
        self.assertEqual(SHA(previous_fixture), '76726f6bddd10a22e2267ecbcac3e98d904ef6ed2bb4049f036fc7c2a7e38cf4')
        self.assertEqual(sum(len(item['deltas']) for item in value['files'].values()), 43)
        self.assertEqual(len(value['files']), 19)
        self.assertEqual(SHA((ROOT/'tests/fixtures/tls-cpu-ip-source-deltas.json').read_bytes()),
                         '5be9cb62c0470a0db6f3276ac510d7a6916dbb586cde16788aeecfb2cb3c9709')

    def test_p2_whole_image_unique_context_and_frozen_preimage_are_independent(self):
        from resource_startup_source_compatibility import source_input as resource_input
        current = resource_input((ROOT/GV).read_bytes(), GV)
        delta = layer.manifest()['files'][GV]['deltas'][-1]
        before, after = delta['previous'].encode(), delta['current'].encode()
        frozen = current.replace(after, before, 1)
        self.assertEqual((SHA(frozen), len(frozen)), (layer.P2_PREVIOUS_SHA256, layer.P2_PREVIOUS_BYTES))
        with patch.object(tls, 'source_input', side_effect=AssertionError('P2 called TLS recursively')):
            self.assertEqual(layer.p2_input(current, GV), frozen)
            self.assertIs(layer.p2_input(frozen, GV), frozen)
        for relative in (CHAT, 'tests/foreign.py'):
            raw = b'raw unowned left input still faces its retained golden'
            self.assertIs(layer.p2_input(raw, relative), raw)
        removed = current.replace(after, b'', 1)
        candidates = (removed, current.replace(after, after+after, 1),
                      current.replace(after, after+b' ', 1), removed+after,
                      current[:-1], current+b'unknown complete image')
        for raw in candidates:
            self.assertNotEqual(raw, current)
            with self.assertRaises(ValueError):
                layer.p2_input(raw, GV)
        for bad in (None, current.decode(), bytearray(current), memoryview(current)):
            with self.assertRaises(ValueError):
                layer.p2_input(bad, GV)
        for bad in ('/'+GV, './'+GV, '../'+GV, GV+'/', None, Path(GV)):
            with self.assertRaises(ValueError):
                layer.p2_input(current, bad)
        for kind, message in (('id', 'final declared context'), ('missing', 'exact contextual edit once'), ('duplicate', 'exact contextual edit once')):
            changed = copy.deepcopy(layer.manifest())
            test_raw = current
            if kind == 'id':
                changed['files'][GV]['deltas'][-1]['id'] = 'context-99'
            elif kind == 'missing':
                changed['files'][GV]['deltas'][-1]['current'] = 'missing P2 exact chunk'
            else:
                test_raw = current.replace(after, after+after, 1)
                changed['files'][GV]['reviewedSha256'] = SHA(test_raw)
                changed['files'][GV]['reviewedBytes'] = len(test_raw)
            with patch.object(layer, 'manifest', return_value=changed), self.assertRaisesRegex(ValueError, message):
                layer.p2_input(test_raw, GV)
        changed = copy.deepcopy(layer.manifest())
        changed['files'][GV]['deltas'][-1]['previous'] += 'NONCLOSING_P2'
        source = (ROOT/'tests/final_browser_source_compatibility.py').read_text()
        guard = "    if (_sha(restored), len(restored)) != (P2_PREVIOUS_SHA256, P2_PREVIOUS_BYTES):\n        raise ValueError('P2 metadata input did not restore the exact frozen TLS image')\n"
        self.assertEqual(source.count(guard), 1)
        counterfeit = compiled(source.replace(guard, '', 1), 'p2_preimage_counterfeit')
        counterfeit['manifest'] = lambda: changed
        with patch.object(layer, 'manifest', return_value=changed):
            with self.assertRaisesRegex(ValueError, 'exact frozen TLS image'):
                layer.p2_input(current, GV)
        with self.assertRaises(AssertionError):
            with self.assertRaisesRegex(ValueError, 'exact frozen TLS image'):
                counterfeit['p2_input'](current, GV)
        # The whole-image check must run before contextual inspection.
        class Forbidden:
            def encode(self, *args):
                raise AssertionError('Unknown image reached P2 context')
        changed = copy.deepcopy(layer.manifest())
        changed['files'][GV]['deltas'][-1]['current'] = Forbidden()
        with patch.object(layer, 'manifest', return_value=changed), self.assertRaisesRegex(ValueError, 'unknown whole Gecko bytes'):
            layer.p2_input(current+b' ', GV)

    def test_p2_tls_read_hooks_strip_to_the_exact_frozen_metadata_sources(self):
        final = build_budget_helper_before((ROOT/'tests/final_browser_source_compatibility.py').read_bytes())
        constants = (b"P2_PREVIOUS_SHA256 = '98c648b06ef28cd35e01ea0ad8128258d3f171706cc3ef23087bd102f545a510'\n"
                     b"P2_PREVIOUS_BYTES = 128741\nP2_CONTEXT_ID = 'context-08'\n")
        self.assertEqual(final.count(constants), 1)
        start = final.index(b'\ndef p2_input(')
        end = final.index(b'\ndef metadata_input(', start)
        restored_final = final[:start]+final[end:]
        restored_final = restored_final.replace(constants, b'', 1)
        restored_final = restored_final.replace(layer.DELTA_SHA256.encode(), b'76726f6bddd10a22e2267ecbcac3e98d904ef6ed2bb4049f036fc7c2a7e38cf4', 1)
        restored_final = restored_final.replace(b'tls_input(p2_input(raw, relative), relative)', b'tls_input(raw, relative)', 1)
        self.assertEqual(SHA(restored_final), '29ba5853908753e2be9bca7e77f38456a05627c7ae6a1136150d73234eca67b1')
        helper = (ROOT/'tests/tls_cpu_ip_source_compatibility.py').read_bytes()
        hook = b"    if relative == 'app/src/main/java/local/pocketchat/GeckoWebView.java' and (digest, len(raw)) not in ((row['previousSha256'], row['previousBytes']), (row['reviewedSha256'], row['reviewedBytes'])):\n        from final_browser_source_compatibility import p2_input\n        raw = p2_input(raw, relative)\n        digest = _sha(raw)\n"
        self.assertEqual(helper.count(hook), 1)
        self.assertEqual(SHA(helper.replace(hook, b'', 1)), 'aef26cf20a6cc5a9415bc73d53d0e849f14727dc4605bea411eefcd692288608')
        current = (ROOT/'tests/profile_tls_cpu_ip_source_compatibility_test.py').read_bytes()
        imported = b'from final_browser_source_compatibility import p2_input as p2_metadata_input\n\n'
        self.assertEqual(current.count(imported), 1)
        restored = current.replace(imported, b'', 1)
        read_hook = b'p2_metadata_input((ROOT/relative).read_bytes(), relative)'
        self.assertEqual(restored.count(read_hook), 4)
        restored = restored.replace(read_hook, b'(ROOT/relative).read_bytes()')
        self.assertEqual(SHA(restored), '187e3af451f2b7d997b0a3ff82fb454e50177969de6130906a7afbc9b3072bb6')
        self.assertEqual(dumps(assertions(current)), dumps(assertions(restored)))
        self.assertEqual(test_methods(current), test_methods(restored))
        self.assertEqual(len(test_methods(current)), 12)
        # Actual compile/runtime consumers read raw Gecko; no historical input
        # helper can participate in the current IP method host extraction.
        host = (ROOT/'tests/gecko-ip-transport-host/run.py').read_text()
        self.assertIn('text=source.read_text()', host)
        self.assertNotIn('final_browser_source_compatibility', host)
        self.assertNotIn('p2_input', host)

    def test_public_window_catalog_additions_preserve_all_original_forty_four_contexts(self):
        from resource_startup_source_compatibility import frozen_manifest_input
        full = frozen_manifest_input(layer.manifest())
        value = copy.deepcopy(full)
        for relative, (digest, size) in INVENTORY_116_PINS.items():
            row = value['files'][relative]
            del row['deltas'][-INVENTORY_CLEANUP_CONTEXT_COUNTS[relative]:]
            row['reviewedSha256'], row['reviewedBytes'] = digest, size
        rejected = 0
        for relative, (digest, size) in INVENTORY_115_PINS.items():
            row = value['files'][relative]
            delta = row['deltas'].pop()
            current = (ROOT/relative).read_bytes()
            before, after = delta['previous'].encode(), delta['current'].encode()
            phase = inventory_116_input(current, relative, full)
            self.assertEqual(phase.count(after), 1)
            restored = phase.replace(after, before, 1)
            self.assertEqual((SHA(restored), len(restored)), (digest, size))
            row['reviewedSha256'], row['reviewedBytes'] = digest, size
            after = current_context(relative, full['files'][relative], delta)
            removed = current.replace(after, b'', 1)
            moved = removed+after
            if moved == current:
                moved = after+removed
            for candidate in (removed, current.replace(after, after+after, 1),
                    current.replace(after, after+b' ', 1), moved,
                    current[:-1], b'unknown window catalog image'+current):
                with self.assertRaises(ValueError):
                    layer.source_input(candidate, relative)
                rejected += 1
        restored_fixture = (json.dumps(value, ensure_ascii=False, indent=2)+'\n').encode()
        self.assertEqual(SHA(restored_fixture), 'ad897f6a3f9f53913392786788034022d79ab9c1f29a658721005f2fc8443570')
        self.assertEqual(len(value['files']), 19)
        self.assertEqual(sum(len(row['deltas']) for row in value['files'].values()), 44)
        self.assertEqual(sum(len(row['deltas']) for row in layer.manifest()['files'].values()) - sum(INVENTORY_CLEANUP_CONTEXT_COUNTS.values()), 46)
        self.assertEqual(rejected, 12)

    def test_old_inventory_context_attacks_change_the_actual_current_image(self):
        mapped = 0
        rejected = 0
        for relative in INVENTORY_115_PINS:
            row = layer.manifest()['files'][relative]
            current = (ROOT/relative).read_bytes()
            self.assertEqual(layer.source_input(current, relative), git('show', B+':'+relative))
            retained = row['deltas'][:-INVENTORY_CLEANUP_CONTEXT_COUNTS[relative]]
            for delta in retained:
                part = current_context(relative, row, delta)
                self.assertEqual(part, tagged_current_context(relative, row, delta))
                self.assertEqual(current.count(part), 1)
                mapped += part != delta['current'].encode()
                removed = current.replace(part, b'', 1)
                moved = removed+part
                if moved == current:
                    moved = part+removed
                for candidate in (removed, current.replace(part, part+part, 1),
                        current.replace(part, part+b' ', 1), moved,
                        current[:-1], b'unknown current catalog image'+current):
                    self.assertNotEqual(candidate, current)
                    with self.assertRaises(ValueError):
                        layer.source_input(candidate, relative)
                    rejected += 1
        self.assertGreater(mapped, 0)
        self.assertEqual(rejected, 30)
        source = (ROOT/'tests/profile_final_browser_source_compatibility_test.py').read_text()
        function = next(node for node in ast.parse(source).body
                        if isinstance(node, ast.FunctionDef) and node.name == 'current_context')
        body = ast.get_source_segment(source, function)
        positions = "        if b <= left:\n            left += change\n            right += change\n        elif a < right:\n            left = min(left, a)\n            right = max(right, b) + change\n"
        self.assertEqual(body.count(positions), 1)
        bypass = '    if relative not in INVENTORY_115_PINS:'
        self.assertEqual(body.count(bypass), 1)
        def exact_current_mapping(mapper):
            for path in INVENTORY_115_PINS:
                item = layer.manifest()['files'][path]
                retained = item['deltas'][:-INVENTORY_CLEANUP_CONTEXT_COUNTS[path]]
                for context in retained:
                    try:
                        result = mapper(path, item, context)
                    except ValueError as failure:
                        raise AssertionError('Exact raw-current mapping did not complete') from failure
                    self.assertEqual(result, tagged_current_context(path, item, context))
        exact_current_mapping(current_context)
        for label, counterfeit in (('removed-position-replay', body.replace(positions, '', 1)),
                ('bypassed-position-replay', body.replace(bypass, '    if True:', 1))):
            namespace = globals().copy()
            exec(compile(counterfeit, '<'+label+'>', 'exec'), namespace)
            with self.assertRaises(AssertionError):
                exact_current_mapping(namespace['current_context'])

    def test_cleanup_catalog_additions_preserve_all_original_forty_six_contexts(self):
        from resource_startup_source_compatibility import frozen_manifest_input
        value = copy.deepcopy(frozen_manifest_input(layer.manifest()))
        rejected = 0
        for relative, (digest, size) in INVENTORY_116_PINS.items():
            row = value['files'][relative]
            deltas = row['deltas'][-INVENTORY_CLEANUP_CONTEXT_COUNTS[relative]:]
            del row['deltas'][-INVENTORY_CLEANUP_CONTEXT_COUNTS[relative]:]
            current = (ROOT/relative).read_bytes()
            restored = current
            for delta in reversed(deltas):
                before, after = delta['previous'].encode(), delta['current'].encode()
                self.assertEqual(current.count(after), 1)
                self.assertEqual(restored.count(after), 1)
                restored = restored.replace(after, before, 1)
                removed = current.replace(after, b'', 1)
                moved = removed+after
                if moved == current:
                    moved = after+removed
                for candidate in (removed, current.replace(after, after+after, 1),
                        current.replace(after, after+b' ', 1), moved,
                        current[:-1], b'unknown cleanup catalog image'+current):
                    with self.assertRaises(ValueError):
                        layer.source_input(candidate, relative)
                    rejected += 1
            self.assertEqual((SHA(restored), len(restored)), (digest, size))
            row['reviewedSha256'], row['reviewedBytes'] = digest, size
        restored_fixture = (json.dumps(value, ensure_ascii=False, indent=2)+'\n').encode()
        self.assertEqual(SHA(restored_fixture), '167329f7fd195601a9b5cbf50a3e754ea17033daf4b82dd8d75c1b64210d5fb5')
        self.assertEqual(len(value['files']), 19)
        self.assertEqual(sum(len(row['deltas']) for row in value['files'].values()), 46)
        self.assertEqual(sum(len(row['deltas']) for row in layer.manifest()['files'].values()), 59)
        self.assertEqual(rejected, 78)

    def test_build_budget_metadata_adapter_preserves_the_original_fifty_nine_contexts(self):
        relative = layer.BUILD_BUDGET_PATH
        raw = (ROOT/relative).read_bytes()
        restored = layer.build_budget_input(raw, relative)
        self.assertEqual((SHA(restored), len(restored)), ('2792c0919de89b13eb9040660be96f7c3ba55cf689e54abd075646f103e479bf', 7205))
        self.assertIs(layer.build_budget_input(restored, relative), restored)
        row = layer.manifest()['files'][relative]
        self.assertEqual((SHA(restored), len(restored)), (row['reviewedSha256'], row['reviewedBytes']))
        self.assertEqual(layer.source_input(raw, relative), git('show', S+':'+relative))
        self.assertEqual(SHA(layer.DELTA_PATH.read_bytes()), '8bb0bb6580879fcef6258f48e57fbdce19304c0d3ea0061131d993b815877a16')
        self.assertEqual(len(layer.manifest()['files']), 19)
        self.assertEqual(sum(len(item['deltas']) for item in layer.manifest()['files'].values()), 59)
        self.assertEqual(SHA(build_budget_helper_before((ROOT/'tests/final_browser_source_compatibility.py').read_bytes())), '0c24e81a178476e79907f84d107c5539e5b7d872bbcff866844d36e81238ef4d')
        ip_raw = (ROOT/'tests/browser_ip_timezone_publish_gate_test.py').read_bytes()
        ip_current = b"                if name == 'build' and field == 'timeout-minutes':\n                    self.assertIs(type(expected), int)\n                    self.assertEqual(expected, 40)\n                    self.assertIs(type(current['jobs'][name].get(field)), int)\n                    self.assertEqual(current['jobs'][name].get(field), 60)\n                else:\n                    self.assertEqual(current['jobs'][name].get(field), expected, (name, field))\n"
        ip_before = b"                self.assertEqual(current['jobs'][name].get(field), expected, (name, field))\n"
        self.assertEqual(ip_raw.count(ip_current), 1)
        self.assertEqual(SHA(ip_raw.replace(ip_current, ip_before, 1)), '96d61fda98331762c5fa4aaa2290e1f0492dc48bf8f340e0fc16f4a92f062793')
        self.assertNotIn('tests/browser_ip_timezone_publish_gate_test.py', layer.PATHS)
        self.assertIs(layer.build_budget_input(ip_raw, 'tests/browser_ip_timezone_publish_gate_test.py'), ip_raw)

    def test_actual_raw_build_budget_contracts_and_compiled_guard_counterfeits(self):
        import browser_acceptance_workflow_test as workflow
        import browser_ip_timezone_publish_gate_test as ip_gate
        import yaml
        raw_new = yaml.safe_load((ROOT/'.github/workflows/browser-2_1-acceptance.yml').read_text())
        raw_old = yaml.safe_load((ROOT/'.github/workflows/gecko-integration.yml').read_text())
        self.assertIs(type(raw_old['jobs']['build']['timeout-minutes']), int)
        self.assertEqual(raw_old['jobs']['build']['timeout-minutes'], 40)
        self.assertIs(type(raw_new['jobs']['build']['timeout-minutes']), int)
        self.assertEqual(raw_new['jobs']['build']['timeout-minutes'], 60)
        workflow.BrowserWorkflowTests.setUpClass()
        self.assertEqual(workflow.BrowserWorkflowTests.new, raw_new)
        self.assertEqual(workflow.BrowserWorkflowTests.old, raw_old)
        def run_guard(kind, new, old, selected=None):
            if kind == 'workflow':
                selected = selected or workflow.BrowserWorkflowTests
                selected.setUpClass()
                with patch.object(selected, 'new', new), patch.object(selected, 'old', old):
                    selected('test_original_checks_retained_in_order').test_original_checks_retained_in_order()
            else:
                selected = selected or ip_gate.IpTimezonePublishGateTests
                with patch.object(ip_gate.yaml, 'safe_load', side_effect=[new, old]):
                    selected('test_ip_android_step_and_verified_raw_transfer_are_mandatory_without_new_jobs').test_ip_android_step_and_verified_raw_transfer_are_mandatory_without_new_jobs()
        with patch.object(layer, 'metadata_input', side_effect=AssertionError('Actual workflow must not use historical metadata')):
            workflow.BrowserWorkflowTests('test_original_checks_retained_in_order').test_original_checks_retained_in_order()
            ip_gate.IpTimezonePublishGateTests('test_ip_android_step_and_verified_raw_transfer_are_mandatory_without_new_jobs').test_ip_android_step_and_verified_raw_transfer_are_mandatory_without_new_jobs()
        def reject(kind, new, old, selected=None):
            with self.assertRaises(AssertionError):
                run_guard(kind, new, old, selected)
        negative = 0
        for kind in ('workflow', 'ip'):
            run_guard(kind, copy.deepcopy(raw_new), copy.deepcopy(raw_old))
            for value in (39, 41, 60, 40.0, '40', None, True):
                changed = copy.deepcopy(raw_old);changed['jobs']['build']['timeout-minutes'] = value
                reject(kind, copy.deepcopy(raw_new), changed);negative += 1
            for value in (40, 59, 61, 60.0, '60', None, True):
                changed = copy.deepcopy(raw_new);changed['jobs']['build']['timeout-minutes'] = value
                reject(kind, changed, copy.deepcopy(raw_old));negative += 1
            for side in ('old', 'new'):
                new, old = copy.deepcopy(raw_new), copy.deepcopy(raw_old)
                (old if side == 'old' else new)['jobs']['build'].pop('timeout-minutes')
                reject(kind, new, old);negative += 1
            other_build = ('build', 'runs-on', 'unexpected-runner') if kind == 'workflow' else ('build', 'permissions', {'contents':'write','unexpected':'permission'})
            for name, field, value in (other_build,
                    ('chrome-diagnostic', 'timeout-minutes', raw_old['jobs']['chrome-diagnostic']['timeout-minutes']+1), ('verify', 'needs', ['build'])):
                changed = copy.deepcopy(raw_new);changed['jobs'][name][field] = value
                reject(kind, changed, copy.deepcopy(raw_old));negative += 1
        self.assertEqual(negative, 38)
        # Mutated guards still accept the pristine raw40/raw60 pair, but must
        # fail the same strict negative oracle when they admit an invalid value.
        mutants = 0
        for kind, module, class_name, replacements in (
                ('workflow', workflow, 'BrowserWorkflowTests', (
                    ('self.assertEqual(current[key],60)', 'self.assertGreaterEqual(current[key],60)', 'new', 61),
                    ('self.assertEqual(value,40)', 'self.assertGreaterEqual(value,40)', 'old', 41),
                    ('                        self.assertIs(type(current[key]),int)\n', '', 'new', 60.0),
                    ('                        self.assertIs(type(value),int)\n', '', 'old', 40.0))),
                ('ip', ip_gate, 'IpTimezonePublishGateTests', (
                    ("self.assertEqual(current['jobs'][name].get(field), 60)", "self.assertGreaterEqual(current['jobs'][name].get(field), 60)", 'new', 61),
                    ('self.assertEqual(expected, 40)', 'self.assertGreaterEqual(expected, 40)', 'old', 41),
                    ("                    self.assertIs(type(current['jobs'][name].get(field)), int)\n", '', 'new', 60.0),
                    ('                    self.assertIs(type(expected), int)\n', '', 'old', 40.0)))):
            original = Path(module.__file__).read_text()
            for before, after, side, value in replacements:
                self.assertEqual(original.count(before), 1)
                namespace = {'__file__':module.__file__, '__name__':'strict_build_budget_counterfeit'}
                exec(compile(original.replace(before, after, 1), '<strict-build-budget-counterfeit>', 'exec'), namespace)
                selected = namespace[class_name]
                run_guard(kind, copy.deepcopy(raw_new), copy.deepcopy(raw_old), selected)
                new, old = copy.deepcopy(raw_new), copy.deepcopy(raw_old)
                (old if side == 'old' else new)['jobs']['build']['timeout-minutes'] = value
                with self.assertRaises(AssertionError):
                    reject(kind, new, old, selected)
                mutants += 1
        self.assertEqual(mutants, 8)

    def test_build_budget_metadata_unknown_context_and_preimage_counterfeits_reject(self):
        relative = layer.BUILD_BUDGET_PATH
        current = (ROOT/relative).read_bytes()
        chunk = layer.BUILD_BUDGET_CURRENT
        self.assertEqual(current.count(chunk), 1)
        removed = current.replace(chunk, b'', 1)
        moved = removed+chunk
        if moved == current:
            moved = chunk+removed
        for bad in (removed, current.replace(chunk, chunk+chunk, 1),
                current.replace(chunk, chunk+b' ', 1), moved, current[:-1], current+b'unknown',
                current.replace(b'self.assertEqual(current[key],60)', b'self.assertEqual(current[key],61)', 1)):
            self.assertNotEqual(bad, current)
            with self.assertRaises(ValueError):
                layer.build_budget_input(bad, relative)
        for bad in (None, current.decode(), bytearray(current), memoryview(current)):
            with self.assertRaises(ValueError):
                layer.build_budget_input(bad, relative)
        for bad in ('/'+relative, './'+relative, '../'+relative, relative+'/', None, Path(relative)):
            with self.assertRaises(ValueError):
                layer.build_budget_input(current, bad)
        source = (ROOT/'tests/final_browser_source_compatibility.py').read_text()
        guard = "    if (_sha(restored), len(restored)) != (BUILD_BUDGET_PREVIOUS_SHA256, BUILD_BUDGET_PREVIOUS_BYTES):\n        raise ValueError('Build budget metadata did not restore the exact frozen test')\n"
        self.assertEqual(source.count(guard), 1)
        counterfeit = compiled(source.replace(guard, '', 1), 'build_budget_preimage_counterfeit')
        counterfeit['BUILD_BUDGET_PREVIOUS'] = layer.BUILD_BUDGET_PREVIOUS+b'NONCLOSING_BUDGET'
        with patch.object(layer, 'BUILD_BUDGET_PREVIOUS', layer.BUILD_BUDGET_PREVIOUS+b'NONCLOSING_BUDGET'):
            with self.assertRaisesRegex(ValueError, 'exact frozen test'):
                layer.build_budget_input(current, relative)
        with self.assertRaises(AssertionError):
            with self.assertRaisesRegex(ValueError, 'exact frozen test'):
                counterfeit['build_budget_input'](current, relative)
        class Forbidden:
            def __len__(self):
                raise AssertionError('Unknown budget source reached context inspection')
        with patch.object(layer, 'BUILD_BUDGET_CURRENT', Forbidden()), self.assertRaisesRegex(ValueError, 'unknown complete test source'):
            layer.build_budget_input(current+b' ', relative)

    def test_current_workflow_reads_raw_yaml_seven_declared_and_thirteen_expanded_jobs(self):
        import browser_acceptance_workflow_test as workflow
        import yaml
        current = (ROOT/'tests/browser_acceptance_workflow_test.py').read_text()
        self.assertNotIn('final_browser_source_compatibility', current)
        with patch.object(layer, 'metadata_input', side_effect=AssertionError('Actual workflow read was projected')):
            workflow.BrowserWorkflowTests.setUpClass()
            case = workflow.BrowserWorkflowTests()
            case.test_original_checks_retained_in_order()
            case.test_single_pipeline_shares_actual_apk_and_gates_browser()
            case.test_new_host_suites_and_exact_history_are_mandatory()
        raw = yaml.safe_load((ROOT/'.github/workflows/browser-2_1-acceptance.yml').read_text())
        self.assertEqual(workflow.BrowserWorkflowTests.new, raw)
        self.assertEqual(len(raw['jobs']), 7)
        expanded = []
        for name, job in raw['jobs'].items():
            matrix = job.get('strategy', {}).get('matrix', {})
            self.assertNotIn('include', matrix)
            self.assertNotIn('exclude', matrix)
            self.assertTrue(all(type(items) is list and items for items in matrix.values()))
            expanded.extend((name, values) for values in itertools.product(*matrix.values()))
        self.assertEqual(len(expanded), 13)

    def test_actual_publisher_stages_eleven_complete_current_files_without_projection(self):
        tree = ast.parse((ROOT/'tools/publish-gecko-release.py').read_text())
        blocks = [node for node in tree.body if isinstance(node, ast.If)
            and ast.unparse(node.test) in ('browser_release', 'roadmap_release', 'version_code >= 46')
            and any(isinstance(value, ast.Call) and ast.unparse(value.func) == 'shutil.copy2'
                    for value in ast.walk(node))]
        self.assertEqual(len(blocks), 3)
        with tempfile.TemporaryDirectory(prefix='final-actual-publisher-') as folder:
            stage = Path(folder)/'stage'; (stage/'tools/gecko').mkdir(parents=True)
            namespace = dict(browser_release=True, roadmap_release=True, version_code=103,
                             root=ROOT, stage=stage, shutil=shutil)
            with patch.object(layer, 'source_input', side_effect=AssertionError('Publisher source was projected')), \
                    patch.object(layer, 'metadata_input', side_effect=AssertionError('Publisher metadata was projected')):
                exec(compile(ast.Module(body=blocks, type_ignores=[]), '<actual publisher raw copies>', 'exec'), namespace)
            files = [path for path in stage.rglob('*') if path.is_file()]
            self.assertEqual(len(files), 11)
            for path in files:
                self.assertEqual(path.read_bytes(), (ROOT/path.relative_to(stage)).read_bytes())

    def test_actual_browser_publisher_runtime_and_behavior_hosts_never_import_final_history(self):
        prohibited = {'final_browser_source_compatibility', 'tls_cpu_ip_source_compatibility',
                      'cpu_ip_source_compatibility', 'ip_timezone_source_compatibility',
                      'worker_timezone_source_compatibility', 'dual_browser_source_compatibility'}
        paths = set((ROOT/'app').rglob('*.py')) | set((ROOT/'tools').rglob('*.py'))
        paths.update((ROOT/'tests').glob('browser_*test.py'))
        for folder in (ROOT/'tests').glob('*host'):
            if folder.is_dir():
                paths.update(folder.rglob('*.py'))
        self.assertTrue(paths)
        for path in paths:
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    self.assertNotIn((node.module or '').split('.')[-1], prohibited, str(path))
                elif isinstance(node, ast.Import):
                    for entry in node.names:
                        self.assertNotIn(entry.name.split('.')[-1], prohibited, str(path))


if __name__ == '__main__':
    unittest.main(verbosity=2)
