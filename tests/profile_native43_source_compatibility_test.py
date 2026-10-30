"""Read-only43 exact whole-source inverse and retained42/39/37/32 guards."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import unittest

import fingerprint_source_compatibility as compat
import native43_source_compatibility as native
import page_bridge42_source_compatibility as bridge
from reading45_source_compatibility import reading45_source_bytes

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'app/src/main/java/local/pocketchat/GeckoWebView.java'
sha = lambda raw: hashlib.sha256(raw).hexdigest()


class Native43SourceCompatibilityTests(unittest.TestCase):
    completed = []

    @classmethod
    def tearDownClass(cls):
        output = os.environ.get('NATIVE43_SOURCE_COMPAT_REPORT')
        if output:
            Path(output).write_text(json.dumps(dict(
                status='passed' if len(cls.completed) == 6 else 'failed',
                cases=cls.completed, expectedCases=6,
                productionSha256=sha(SOURCE.read_bytes()),
                priorIntendedTree=native.PREVIOUS_INTENDED_TREE,
                priorWholeSourceSha256=native.PREVIOUS_SHA256,
                assertionsChanged=False, actualAndroidExecution=False,
                actualSdkApiCompile=False, physicalPhoneAcceptance=False), indent=2) + '\n')

    def test_exact_readonly_accessors_restore_entire_prior42_browser(self):
        raw = SOURCE.read_bytes()
        self.assertEqual(sha(raw), native.REVIEWED_SHA256)
        prior = subprocess.check_output(['git', 'show', native.PREVIOUS_INTENDED_TREE + ':app/src/main/java/local/pocketchat/GeckoWebView.java'], cwd=ROOT)
        self.assertEqual(native.native43_preservation_bytes(raw), prior)
        self.assertEqual(sha(prior), native.PREVIOUS_SHA256)
        for addition in native.EXACT_ACCESSORS:
            self.assertEqual(raw.count(addition), 1)
        self.completed.append(dict(name='whole-production-inverse', passed=True))

    def test_entire_reverse_chain_retains_original_oracles(self):
        raw = SOURCE.read_bytes()
        expected = [
            (native.native43_preservation_bytes, '07d027899ad2c4a48d3759fe19080d3aa72027aa75aac6147e470f310bb1a5be'),
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
        self.completed.append(dict(name='43-42-39-37-32-original-chain', passed=True))

    def test_only_exact_known_predecessors_pass_unchanged(self):
        raw = SOURCE.read_bytes()
        ancestors = [fn(raw) for fn in (native.native43_preservation_bytes, bridge.bridge42_preservation_bytes,
                     compat.lifecycle39_preservation_bytes, compat.upload37_preservation_bytes,
                     compat.permission_denial_preservation_bytes, compat.reading_preservation_bytes)]
        self.assertEqual({sha(value) for value in ancestors}, set(native.EXACT_PRE43_SHA256))
        for value in ancestors:
            self.assertEqual(native.native43_preservation_bytes(value), value)
            with self.assertRaises(ValueError):
                native.native43_preservation_bytes(value + b' ')
        for value in (b'', b'unknown source without native accessor markers'):
            with self.assertRaises(ValueError):
                native.native43_preservation_bytes(value)
        self.completed.append(dict(name='known-predecessors-only', passed=True, rejectedUnknownSources=8))

    def test_each_accessor_rejects_missing_duplicate_changed_and_relocated(self):
        raw = SOURCE.read_bytes()
        rejected = 0
        for addition in native.EXACT_ACCESSORS:
            for mutation in (raw.replace(addition, b'', 1), raw.replace(addition, addition + addition, 1),
                             raw.replace(addition, addition + b' ', 1), raw.replace(addition, b'', 1) + addition):
                with self.assertRaises(ValueError):
                    native.native43_preservation_bytes(mutation)
                with self.assertRaises(ValueError):
                    compat.reading_preservation_bytes(mutation)
                rejected += 1
        first, second = native.EXACT_ACCESSORS
        self.assertEqual(raw.count(first + second), 1)
        with self.assertRaises(ValueError):
            compat.reading_preservation_bytes(raw.replace(first + second, second + first, 1))
        self.completed.append(dict(name='accessor-mutations', passed=True, rejectedMutations=rejected + 1))

    def test_prior_bridge_geometry_permission_upload_and_resume_edits_stay_rejected(self):
        raw = SOURCE.read_bytes()
        geometry = b'Math.abs(next-readingLayout)<.001f'
        self.assertEqual(raw.count(geometry), 1)
        mutations = [raw.replace(geometry, b'Math.abs(next-readingLayout)<.002f', 1)]
        mutations.extend(raw.replace(after, after + b' ', 1) for before, after in bridge.DELTAS)
        mutations.extend(raw.replace(value, value + b' ', 1) for value in compat.PERMISSION_EXACT_ADDITIONS)
        mutations.extend(raw.replace(value, value + b' ', 1) for value, previous in compat.UPLOAD37_EXACT_REPLACEMENTS)
        notice = compat.LIFECYCLE39_REVIEWED_ON_RESUME
        self.assertEqual(raw.count(notice), 1)
        mutations.append(raw.replace(notice, notice + b' ', 1))
        for mutation in mutations:
            self.assertNotEqual(mutation, raw)
            with self.assertRaises(ValueError):
                native.native43_preservation_bytes(mutation)
            with self.assertRaises(ValueError):
                compat.reading_preservation_bytes(mutation)
        self.completed.append(dict(name='all-prior-protections', passed=True, rejectedMutations=len(mutations)))

    def test_bounded_test_input_ports_restore_entire_prior42_files(self):
        edits = {
            'tests/page_bridge42_source_compatibility.py': [
                ('import hashlib\n', 'import hashlib\nfrom native43_source_compatibility import native43_preservation_bytes\n', 1),
                ('def bridge42_preservation_bytes(raw):\n', 'def bridge42_preservation_bytes(raw):\n    raw = native43_preservation_bytes(raw)\n', 1),
            ],
            'tests/profile_page_bridge42_source_compatibility_test.py': [
                ('        raw = SOURCE.read_bytes()\n', '        raw = bridge.native43_preservation_bytes(SOURCE.read_bytes())\n', 5),
            ],
        }
        for relative, changes in edits.items():
            text = (ROOT / relative).read_text()
            for before, after, count in reversed(changes):
                self.assertEqual(text.count(after), count)
                text = text.replace(after, before)
            self.assertEqual(text.encode(), subprocess.check_output(['git', 'show', native.PREVIOUS_INTENDED_TREE + ':' + relative], cwd=ROOT))
        for relative in ('tests/fingerprint_source_compatibility.py', 'tests/profile_upload37_source_compatibility_test.py',
                         'tests/profile_lifecycle39_source_compatibility_test.py', 'tests/profile_page_bridge_lifecycle_test.py',
                         'tests/profile_content_permission_decisions_test.py', 'tests/profile_reading_fit_completion_test.py'):
            self.assertEqual(reading45_source_bytes((ROOT / relative).read_bytes(),relative) if relative=='tests/profile_reading_fit_completion_test.py' else (ROOT / relative).read_bytes(), subprocess.check_output(['git', 'show', native.PREVIOUS_INTENDED_TREE + ':' + relative], cwd=ROOT))
        self.completed.append(dict(name='all-prior-test-assertion-bytes', passed=True))


if __name__ == '__main__':
    unittest.main(verbosity=2)
