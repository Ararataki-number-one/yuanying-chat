"""Exact newest39 -> upload37 -> permission32 -> original reading inverse."""
import hashlib
from pathlib import Path
import unittest

import fingerprint_source_compatibility as compat

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'app/src/main/java/local/pocketchat/GeckoWebView.java'
sha = lambda raw: hashlib.sha256(raw).hexdigest()


class Lifecycle39SourceCompatibilityTest(unittest.TestCase):
    def test_exact_whole_source_chain_preserves_all_older_oracles(self):
        raw = compat.bridge42_preservation_bytes(SOURCE.read_bytes())
        self.assertEqual(sha(raw), compat.LIFECYCLE39_REVIEWED_BROWSER_SHA256)
        parent = compat.lifecycle39_preservation_bytes(raw)
        self.assertEqual(sha(parent), compat.LIFECYCLE39_PRIOR_BROWSER_SHA256)
        self.assertEqual(sha(parent), compat.UPLOAD37_REVIEWED_BROWSER_SHA256)
        self.assertEqual(sha(compat.upload37_preservation_bytes(raw)), compat.UPLOAD37_PRIOR_BROWSER_SHA256)
        self.assertEqual(sha(compat.permission_denial_preservation_bytes(raw)), compat.PERMISSION_PRIOR_BROWSER_SHA256)
        self.assertEqual(sha(compat.reading_preservation_bytes(raw)), compat.BASELINE)
        for addition in compat.PERMISSION_EXACT_ADDITIONS:
            self.assertEqual(raw.count(addition), 1)
            self.assertEqual(parent.count(addition), 1)
        for addition, previous in compat.UPLOAD37_EXACT_REPLACEMENTS:
            self.assertEqual(raw.count(addition), 1)
            self.assertEqual(parent.count(addition), 1)

    def test_known_exact_predecessors_still_pass_without_new39(self):
        parent = compat.lifecycle39_preservation_bytes(SOURCE.read_bytes())
        before37 = compat.upload37_preservation_bytes(parent)
        before32 = compat.permission_denial_preservation_bytes(parent)
        for raw in [parent, before37, before32]:
            self.assertEqual(compat.lifecycle39_preservation_bytes(raw), raw)
            self.assertEqual(sha(compat.reading_preservation_bytes(raw)), compat.BASELINE)

    def test_on_resume_rejects_missing_duplicate_changed_and_relocated(self):
        raw = compat.bridge42_preservation_bytes(SOURCE.read_bytes())
        current, previous = compat.LIFECYCLE39_REVIEWED_ON_RESUME, compat.LIFECYCLE39_PRIOR_ON_RESUME
        self.assertEqual(raw.count(current), 1)
        mutations = [raw.replace(current, previous, 1) + b' ',
                     raw.replace(current, current + current, 1),
                     raw.replace(current, current + b' ', 1),
                     raw.replace(current, b'', 1) + current]
        for mutation in mutations:
            with self.assertRaises(ValueError):
                compat.lifecycle39_preservation_bytes(mutation)
            with self.assertRaises(ValueError):
                compat.reading_preservation_bytes(mutation)

    def test_each_notice_guard_and_v1_network_failure_call_remain_rejected(self):
        raw = compat.bridge42_preservation_bytes(SOURCE.read_bytes())
        resume = compat.LIFECYCLE39_REVIEWED_ON_RESUME
        fields = [b'!destroyed&&failed&&owner.uiVisible', b'owner.pageError.isEmpty()',
                  b'owner.navigating=false;', b'owner.navigationFailed=true;',
                  b'owner.status=owner.pageError;owner.changed();']
        for field in fields:
            self.assertEqual(resume.count(field), 1)
            with self.assertRaises(ValueError):
                compat.lifecycle39_preservation_bytes(raw.replace(resume, resume.replace(field, b'/* mutated */', 1), 1))
        v1 = raw.replace(b'owner.status=owner.pageError;owner.changed();', b'failure(owner.pageError);', 1)
        with self.assertRaises(ValueError):
            compat.lifecycle39_preservation_bytes(v1)

    def test_unlisted_geometry_upload_and_permission_edits_remain_rejected(self):
        raw = compat.bridge42_preservation_bytes(SOURCE.read_bytes())
        geometry = b'Math.abs(next-readingLayout)<.001f'
        self.assertEqual(raw.count(geometry), 1)
        edits = [raw.replace(geometry, b'Math.abs(next-readingLayout)<.002f', 1)]
        edits.extend(raw.replace(addition, addition + b' ', 1) for addition in compat.PERMISSION_EXACT_ADDITIONS)
        edits.extend(raw.replace(addition, addition + b' ', 1) for addition, previous in compat.UPLOAD37_EXACT_REPLACEMENTS)
        for mutation in edits:
            with self.assertRaises(ValueError):
                compat.permission_denial_preservation_bytes(mutation)
            with self.assertRaises(ValueError):
                compat.reading_preservation_bytes(mutation)

    def test_historical_whole_source_and_patch_guards_stay_fixed(self):
        self.assertEqual(compat.BASELINE, '0dba767dde6a574d5d534723a9283613bdf39fc4843252e1ddb6946a3dfceb10')
        self.assertEqual(compat.PATCH_SHA256, 'f831967e6d6a4265ffadc8ffa008402a091da1204812ec71e6593b37256c22b9')
        self.assertEqual(compat.PERMISSION_PRIOR_BROWSER_SHA256, '80b24f3e89b8ebd8e798d1841b92d006387c9131b00d467228a737b110db5001')
        self.assertEqual(sha((ROOT / 'tests/fixtures/fingerprint-gecko-reading-preservation.patch').read_bytes()), compat.PATCH_SHA256)


if __name__ == '__main__':
    unittest.main(verbosity=2)
