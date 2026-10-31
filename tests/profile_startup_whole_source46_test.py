"""Pinned whole-source inputs for the older startup/reading golden chain."""
import hashlib
from pathlib import Path
import unittest
from startup46_source_compatibility import PATH,PREVIOUS_SHA256,CURRENT_SHA256,HOOK,startup46_source_bytes
from profile_startup_f14_compatibility46_test import HOOK as REVIEWED_HOOK
from experience46_source_compatibility import experience46_source_bytes

ROOT=Path(__file__).resolve().parents[1]
READING='tests/profile_reading_zoom_trace_test.py'
READING45_SHA256='0380c60b94a0512ea95dbb652360dd0090047db7a823342fa8936842a1105009'
GOLDEN='a034b67f5e1e951bc4742f7f866c906516dd5bfa4acacfef616baf434d714c61'


class StartupWholeSource46(unittest.TestCase):
    def test_both_exact_inputs_recover_the_complete_old_consumer_and_golden(self):
        self.assertEqual(HOOK,REVIEWED_HOOK)
        raw=(ROOT/PATH).read_bytes();self.assertEqual(hashlib.sha256(raw).hexdigest(),CURRENT_SHA256)
        previous=startup46_source_bytes(raw,PATH)
        self.assertEqual(hashlib.sha256(previous).hexdigest(),PREVIOUS_SHA256)
        self.assertEqual(startup46_source_bytes(previous,PATH),previous)
        trace="    from reading_zoom_trace_contract import strip_reviewed_reading_trace_additions\n    source=strip_reviewed_reading_trace_additions(source.encode('utf-8'),'tests/gecko/run_device.py').decode('utf-8')\n".encode()
        self.assertEqual(previous.count(trace),1)
        self.assertEqual(hashlib.sha256(previous.replace(trace,b'',1)).hexdigest(),GOLDEN)

    def test_partial_duplicate_moved_changed_and_unknown_whole_inputs_reject(self):
        raw=(ROOT/PATH).read_bytes();hook=HOOK.encode();previous=startup46_source_bytes(raw,PATH)
        candidates=[raw.replace(hook,hook*2,1),previous+hook,raw.replace(hook,hook+b' ',1),raw+b' ',previous+b' ',b'unknown source',raw.replace(b'\n',b'\r\n'),raw.replace(b'ORIGINAL_RUN_AST=',b'ALTERED_RUN_AST=',1)]
        candidates.extend(raw.replace(line,b'',1) for line in hook.splitlines(True))
        for index,value in enumerate(candidates):
            self.assertNotEqual(value,raw);self.assertNotEqual(value,previous)
            with self.subTest(mutant=index),self.assertRaises(ValueError):startup46_source_bytes(value,PATH)
        for path in (PATH+'.other','tests/../'+PATH,'tests/profile_reading_zoom_trace_test.py'):
            with self.subTest(path=path),self.assertRaises(ValueError):startup46_source_bytes(raw,path)

    def test_reading_guard_inverse_cannot_hide_changed_old_golden_or_trace_strip(self):
        raw=(ROOT/READING).read_bytes();previous=experience46_source_bytes(raw,READING)
        self.assertEqual(hashlib.sha256(previous).hexdigest(),READING45_SHA256)
        self.assertIn(GOLDEN.encode(),previous)
        self.assertIn(b"source=strip_reviewed_reading_trace_additions(source.encode('utf-8'),'tests/gecko/run_device.py').decode('utf-8')",previous)
        for value in (raw+b' ',raw.replace(GOLDEN.encode(),b'0'*64,1),raw.replace(b"s=s.replace(",b"s=s.replace('unreviewed','')+s.replace(",1)):
            self.assertNotEqual(value,raw)
            with self.assertRaises(ValueError):experience46_source_bytes(value,READING)


if __name__=='__main__':unittest.main(verbosity=2)
