"""Exact source-input hook controls; the original sixteen startup tests remain intact."""
import hashlib
from pathlib import Path
import unittest
import gecko_device_readiness_test as readiness
from experience46_source_compatibility import experience46_source_bytes,manifest46

ROOT=Path(__file__).resolve().parents[1]
FIXTURE='tests/gecko/GeckoIntegrationTestActivity.java'
CONSUMER='tests/gecko_device_readiness_test.py'
BEFORE_SHA256='5a495ed28e55d5031c4991f6e845161248d52f6c09f1fefd0a7e06041c968e06'
HOOK="""    if needle in ('synchronized void command(','protected void onDestroy()'):
        from experience46_source_compatibility import experience46_source_bytes
        source=experience46_source_bytes(source.encode('utf-8'),'tests/gecko/GeckoIntegrationTestActivity.java').decode('utf-8')
"""
NEEDLES=('synchronized void command(','protected void onDestroy()')


class StartupF14Compatibility46(unittest.TestCase):
    def test_only_exact_hook_added_and_both_approved_inputs_keep_original_members(self):
        current=(ROOT/CONSUMER).read_text();self.assertEqual(current.count(HOOK),1)
        self.assertEqual(hashlib.sha256(current.replace(HOOK,'',1).encode()).hexdigest(),BEFORE_SHA256)
        source=(ROOT/FIXTURE).read_bytes();previous=experience46_source_bytes(source,FIXTURE)
        for value in (source,previous):
            for needle in NEEDLES:
                with self.subTest(source=hashlib.sha256(value).hexdigest(),member=needle):
                    self.assertTrue(readiness.verify_startup_member(value.decode(),needle))
        formatted=source.decode().replace('GeckoLocalDraftIntegration.run(this,serial);','GeckoLocalDraftIntegration.run(this, serial);')
        self.assertTrue(readiness.verify_startup_member(formatted,'void waitReady(long serial)'))

    def test_retirement_missing_duplicate_changed_relocated_and_unknown_sources_reject(self):
        source=(ROOT/FIXTURE).read_text();row=manifest46()['files'][FIXTURE]
        changes=[delta['current'] for delta in row['deltas'] if 'retiredVpn=queuedVpn' in delta['current']]
        self.assertEqual(len(changes),2)
        for chunk in changes:
            self.assertEqual(source.count(chunk),1);remaining=source.replace(chunk,'',1);relocated=remaining+chunk
            if relocated==source:relocated=chunk+remaining
            candidates=(remaining,source.replace(chunk,chunk*2,1),source.replace(chunk,chunk+' ',1),relocated)
            for candidate in candidates:
                self.assertNotEqual(candidate,source)
                for needle in NEEDLES:
                    with self.subTest(member=needle,mutant=hashlib.sha256(candidate.encode()).hexdigest()),self.assertRaises(ValueError):
                        readiness.verify_startup_member(candidate,needle)
        for candidate in (source+' ','unknown source'):
            for needle in NEEDLES:
                with self.subTest(member=needle,unknown=candidate[-16:]),self.assertRaises(ValueError):
                    readiness.verify_startup_member(candidate,needle)


if __name__=='__main__':unittest.main(verbosity=2)
