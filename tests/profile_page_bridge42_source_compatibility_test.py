"""Exact sequential 42 -> 39 -> 37 -> 32 inverses and hostile source mutations."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import unittest

import fingerprint_source_compatibility as compat
import page_bridge42_source_compatibility as bridge

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'app/src/main/java/local/pocketchat/GeckoWebView.java'
sha = lambda raw: hashlib.sha256(raw).hexdigest()


class SequentialBridge42CompatibilityTests(unittest.TestCase):
    completed = []

    @classmethod
    def tearDownClass(cls):
        output = os.environ.get('PAGE_BRIDGE42_SOURCE_COMPAT_REPORT')
        if output:
            Path(output).write_text(json.dumps(dict(
                status='passed' if len(cls.completed) == 6 else 'failed',
                cases=cls.completed, expectedCases=6,
                productionSha256=sha(SOURCE.read_bytes()),
                priorIntendedTree=bridge.PREVIOUS_INTENDED_TREE,
                priorWholeSourceSha256=bridge.PREVIOUS_SHA256,
                actualAndroidExecution=False,
                scope='Whole-file exact inverses and deliberately corrupted source controls; no runtime or phone acceptance.'), indent=2) + '\n')

    def test_exact_four_line_inverse_matches_whole_actual_prior41_tree(self):
        raw = bridge.native43_preservation_bytes(SOURCE.read_bytes())
        self.assertEqual(sha(raw), bridge.REVIEWED_SHA256)
        restored = bridge.bridge42_preservation_bytes(raw)
        prior = subprocess.check_output(['git', 'show', bridge.PREVIOUS_INTENDED_TREE + ':app/src/main/java/local/pocketchat/GeckoWebView.java'], cwd=ROOT)
        self.assertEqual(restored, prior)
        self.assertEqual(sha(restored), bridge.PREVIOUS_SHA256)
        for before, after in bridge.DELTAS:
            self.assertEqual(raw.count(after), 1)
        self.completed.append(dict(name='whole-production-inverse', passed=True))

    def test_complete_chain_keeps_all_original_historical_constants(self):
        raw = bridge.native43_preservation_bytes(SOURCE.read_bytes())
        expected = [
            (bridge.bridge42_preservation_bytes, '892af2842f87e20f6cf339f6654ca0651cdef11c9bda9ce0477daeff69ecc9bd'),
            (compat.lifecycle39_preservation_bytes, '586076cab2cddc3cc013801a8dc8461df688f2615da93bef1c0491b8511abd1a'),
            (compat.upload37_preservation_bytes, '231cccc9b77c9b66e16dfeb8b0e45e465aeffc2753ffe6a693058b0b357be4b3'),
            (compat.permission_denial_preservation_bytes, '80b24f3e89b8ebd8e798d1841b92d006387c9131b00d467228a737b110db5001'),
            (compat.reading_preservation_bytes, '0dba767dde6a574d5d534723a9283613bdf39fc4843252e1ddb6946a3dfceb10'),
        ]
        for normalize, digest in expected:
            self.assertEqual(sha(normalize(raw)), digest)
        self.assertEqual(compat.BASELINE, expected[-1][1])
        self.assertEqual(compat.PATCH_SHA256, 'f831967e6d6a4265ffadc8ffa008402a091da1204812ec71e6593b37256c22b9')
        self.assertEqual(sha((ROOT / 'tests/fixtures/fingerprint-gecko-reading-preservation.patch').read_bytes()), compat.PATCH_SHA256)
        self.assertEqual(bridge.FROZEN31_PREVIOUS_SHA256, compat.PERMISSION_PRIOR_BROWSER_SHA256)
        self.completed.append(dict(name='42-39-37-32-historical-chain', passed=True))

    def test_only_exact_known_predecessors_pass_unchanged(self):
        raw = bridge.native43_preservation_bytes(SOURCE.read_bytes())
        ancestors = [normalize(raw) for normalize in (
            bridge.bridge42_preservation_bytes, compat.lifecycle39_preservation_bytes,
            compat.upload37_preservation_bytes, compat.permission_denial_preservation_bytes,
            compat.reading_preservation_bytes)]
        self.assertEqual({sha(value) for value in ancestors}, set(bridge.EXACT_PRE42_SHA256))
        for value in ancestors:
            self.assertEqual(bridge.bridge42_preservation_bytes(value), value)
            with self.assertRaises(ValueError):
                bridge.bridge42_preservation_bytes(value + b' ')
        for unknown in (b'', b'unknown source without any 42 markers'):
            with self.assertRaises(ValueError):
                bridge.bridge42_preservation_bytes(unknown)
        self.completed.append(dict(name='known-predecessors-only', passed=True, rejectedUnknownSources=7))

    def test_each_reviewed_delta_rejects_missing_duplicate_changed_and_relocated(self):
        raw = bridge.native43_preservation_bytes(SOURCE.read_bytes())
        rejected = 0
        for before, after in bridge.DELTAS:
            mutations = [raw.replace(after, before, 1), raw.replace(after, after + after, 1),
                         raw.replace(after, after + b' ', 1), raw.replace(after, b'', 1) + after]
            for mutation in mutations:
                with self.assertRaises(ValueError):
                    bridge.bridge42_preservation_bytes(mutation)
                with self.assertRaises(ValueError):
                    compat.reading_preservation_bytes(mutation)
                rejected += 1
        self.completed.append(dict(name='reviewed-delta-mutations', passed=True, rejectedMutations=rejected))

    def test_unlisted_geometry_and_all_prior_reviewed_deltas_remain_protected(self):
        raw = bridge.native43_preservation_bytes(SOURCE.read_bytes())
        geometry = b'Math.abs(next-readingLayout)<.001f'
        self.assertEqual(raw.count(geometry), 1)
        mutations = [raw.replace(geometry, b'Math.abs(next-readingLayout)<.002f', 1)]
        mutations.extend(raw.replace(value, value + b' ', 1) for value in compat.PERMISSION_EXACT_ADDITIONS)
        mutations.extend(raw.replace(value, value + b' ', 1) for value, previous in compat.UPLOAD37_EXACT_REPLACEMENTS)
        notice = compat.LIFECYCLE39_REVIEWED_ON_RESUME
        self.assertEqual(raw.count(notice), 1)
        mutations.append(raw.replace(notice, notice + b' ', 1))
        for mutation in mutations:
            self.assertNotEqual(mutation, raw)
            with self.assertRaises(ValueError):
                compat.permission_denial_preservation_bytes(mutation)
            with self.assertRaises(ValueError):
                compat.reading_preservation_bytes(mutation)
        self.completed.append(dict(name='all-prior-protections', passed=True, rejectedMutations=len(mutations)))

    def test_compatibility_changes_invert_to_entire_prior41_test_bytes(self):
        relative = 'tests/fingerprint_source_compatibility.py'
        text = (ROOT / relative).read_text()
        replacements = [
            ('import re\n', 'import re\nfrom page_bridge42_source_compatibility import bridge42_preservation_bytes\n'),
            ('def reading_preservation_bytes(raw):\n', 'def reading_preservation_bytes(raw):\n    raw = bridge42_preservation_bytes(raw)\n'),
            ('def lifecycle39_preservation_bytes(raw):\n', 'def lifecycle39_preservation_bytes(raw):\n    raw = bridge42_preservation_bytes(raw)\n'),
        ]
        for before, after in reversed(replacements):
            self.assertEqual(text.count(after), 1)
            text = text.replace(after, before, 1)
        self.assertEqual(text.encode(), subprocess.check_output(['git', 'show', bridge.PREVIOUS_INTENDED_TREE + ':' + relative], cwd=ROOT))
        relative = 'tests/profile_lifecycle39_source_compatibility_test.py'
        text = (ROOT / relative).read_text()
        before = 'raw = SOURCE.read_bytes()'
        after = 'raw = compat.bridge42_preservation_bytes(SOURCE.read_bytes())'
        self.assertEqual(text.count(after), 4)
        self.assertEqual(text.replace(after, before).encode(), subprocess.check_output(['git', 'show', bridge.PREVIOUS_INTENDED_TREE + ':' + relative], cwd=ROOT))
        self.completed.append(dict(name='all-prior-test-assertion-bytes', passed=True))


if __name__ == '__main__':
    unittest.main(verbosity=2)
