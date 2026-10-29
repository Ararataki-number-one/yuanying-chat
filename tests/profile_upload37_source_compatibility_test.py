"""Exact upload37 -> intended36 -> permission32 -> original reading inverse."""
import hashlib
from pathlib import Path
import unittest

import fingerprint_source_compatibility as compat

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'app/src/main/java/local/pocketchat/GeckoWebView.java'
sha = lambda raw: hashlib.sha256(raw).hexdigest()


class Upload37SourceCompatibilityTest(unittest.TestCase):
    def test_exact_whole_source_chain_preserves_both_older_oracles(self):
        raw = compat.lifecycle39_preservation_bytes(SOURCE.read_bytes())
        self.assertEqual(sha(raw), compat.UPLOAD37_REVIEWED_BROWSER_SHA256)
        parent = compat.upload37_preservation_bytes(raw)
        self.assertEqual(sha(parent), compat.UPLOAD37_PRIOR_BROWSER_SHA256)
        self.assertEqual(sha(parent), compat.PERMISSION_REVIEWED_BROWSER_SHA256)
        self.assertEqual(sha(compat.permission_denial_preservation_bytes(raw)), compat.PERMISSION_PRIOR_BROWSER_SHA256)
        self.assertEqual(sha(compat.reading_preservation_bytes(raw)), compat.BASELINE)
        for addition in compat.PERMISSION_EXACT_ADDITIONS:
            self.assertEqual(raw.count(addition), 1)
            self.assertEqual(parent.count(addition), 1)

    def test_exact_predecessor_and_historical_ancestor_still_pass(self):
        parent = compat.upload37_preservation_bytes(compat.lifecycle39_preservation_bytes(SOURCE.read_bytes()))
        ancestor = compat.permission_denial_preservation_bytes(parent)
        self.assertEqual(compat.upload37_preservation_bytes(parent), parent)
        self.assertEqual(compat.upload37_preservation_bytes(ancestor), ancestor)
        self.assertEqual(sha(compat.reading_preservation_bytes(parent)), compat.BASELINE)
        self.assertEqual(sha(compat.reading_preservation_bytes(ancestor)), compat.BASELINE)

    def test_each_upload_change_rejects_missing_duplicate_modified_and_relocated(self):
        raw = compat.lifecycle39_preservation_bytes(SOURCE.read_bytes())
        for current, prior in compat.UPLOAD37_EXACT_REPLACEMENTS:
            self.assertEqual(raw.count(current), 1)
            changes = [raw.replace(current, prior, 1), raw.replace(current, current + current, 1),
                       raw.replace(current, current + b' ', 1), raw.replace(current, b'', 1) + current]
            for mutation in changes:
                with self.subTest(addition=current[:65], mutation=sha(mutation)):
                    with self.assertRaises(ValueError):
                        compat.upload37_preservation_bytes(mutation)
                    with self.assertRaises(ValueError):
                        compat.reading_preservation_bytes(mutation)

    def test_unlisted_geometry_and_permission_edits_remain_rejected(self):
        raw = compat.lifecycle39_preservation_bytes(SOURCE.read_bytes())
        geometry = b'Math.abs(next-readingLayout)<.001f'
        self.assertEqual(raw.count(geometry), 1)
        edits = [raw.replace(geometry, b'Math.abs(next-readingLayout)<.002f', 1)]
        edits.extend(raw.replace(addition, addition + b' ', 1) for addition in compat.PERMISSION_EXACT_ADDITIONS)
        for mutation in edits:
            with self.assertRaises(ValueError):
                compat.permission_denial_preservation_bytes(mutation)
            with self.assertRaises(ValueError):
                compat.reading_preservation_bytes(mutation)

    def test_original_historical_constants_and_patch_bytes_remain(self):
        self.assertEqual(compat.BASELINE, '0dba767dde6a574d5d534723a9283613bdf39fc4843252e1ddb6946a3dfceb10')
        self.assertEqual(compat.PATCH_SHA256, 'f831967e6d6a4265ffadc8ffa008402a091da1204812ec71e6593b37256c22b9')
        self.assertEqual(compat.PERMISSION_PRIOR_BROWSER_SHA256, '80b24f3e89b8ebd8e798d1841b92d006387c9131b00d467228a737b110db5001')
        self.assertEqual(sha((ROOT / 'tests/fixtures/fingerprint-gecko-reading-preservation.patch').read_bytes()), compat.PATCH_SHA256)


if __name__ == '__main__':
    unittest.main(verbosity=2)
