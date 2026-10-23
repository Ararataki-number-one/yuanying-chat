"""Controls for observed Linux CPU accounting, including missing/terminated PIDs."""
import importlib.util
import os
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('experience_benchmark', ROOT / 'tests/gecko/run_experience_benchmark.py')
BENCH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BENCH)


def process(pid, start, ticks):
    return {'pid': pid, 'startTicks': start, 'userTicks': ticks, 'systemTicks': 0}


def sample(at, *processes):
    return {'available': True, 'uptimeSeconds': at, 'processes': list(processes)}


class ExperienceAccountingTest(unittest.TestCase):
    def test_actual_proc_stat_matches_running_process(self):
        row = BENCH.parse_proc_stat(Path('/proc/self/stat').read_text())
        self.assertEqual(row['pid'], os.getpid())
        self.assertEqual(row['ppid'], os.getppid())
        self.assertGreater(row['startTicks'], 0)
        self.assertGreaterEqual(row['rssPages'], 0)

    def test_parenthesized_names_do_not_shift_cpu_fields(self):
        fields = ['R'] + ['0'] * 21
        fields[1], fields[11], fields[12], fields[19], fields[21] = '7', '123', '45', '900', '60'
        row = BENCH.parse_proc_stat('11 (worker (with spaces)) ' + ' '.join(fields))
        self.assertEqual((row['ppid'], row['userTicks'], row['systemTicks'], row['startTicks'], row['rssPages']), (7, 123, 45, 900, 60))

    def test_new_process_cpu_is_counted_from_birth(self):
        result = BENCH.cpu_summary([sample(10, process(1, 1, 100)), sample(12, process(1, 1, 150), process(2, 1100, 100))], 100)
        self.assertFalse(result['completeProcessLifetimeCoverage'])
        self.assertTrue(result['observedProcessEndsCovered'])
        self.assertEqual(result['cpuSecondsObserved'], 1.5)
        self.assertEqual(result['percentOfOneCore'], 75)

    def test_terminated_process_is_only_a_lower_bound(self):
        result = BENCH.cpu_summary([sample(10, process(1, 1, 100)), sample(11, process(1, 1, 150)), sample(12)], 100)
        self.assertFalse(result['completeProcessLifetimeCoverage'])
        self.assertFalse(result['observedProcessEndsCovered'])
        self.assertEqual(result['cpuSecondsObserved'], .5)
        self.assertEqual(len(result['terminatedBeforeFinalObservation']), 1)

    def test_missing_counters_are_not_reported_as_zero_cpu(self):
        self.assertFalse(BENCH.cpu_summary([sample(10), sample(12)], 100)['available'])
        self.assertFalse(BENCH.cpu_summary([{'available': False}], 100)['available'])
        self.assertFalse(BENCH.cpu_summary([sample(10, process(1, 1, 1)), sample(12, process(1, 1, 2))], None)['available'])


if __name__ == '__main__':
    unittest.main()
