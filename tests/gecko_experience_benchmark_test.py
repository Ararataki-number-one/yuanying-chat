"""Controls for observed Linux CPU accounting, including missing/terminated PIDs."""
import ast
import importlib.util
import os
from pathlib import Path
import subprocess
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
    def test_missing_malformed_or_nonfinite_uptime_is_unavailable_input(self):
        self.assertEqual(BENCH.parse_uptime('120.25 45.5\n'), 120.25)
        tree = ast.parse((ROOT / 'tests/gecko/run_experience_benchmark.py').read_text())
        collect = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == 'process_sample')
        for raw in ('', '\n', 'not-a-time', 'NaN 0', 'inf 0', '-1 0', '99 0'):
            values = ['PID PPID UID NAME\n', '100 0\n', raw]
            bindings = dict(vars(BENCH), adb=lambda *args, **kwargs: values.pop(0))
            exec(compile(ast.Module(body=[collect], type_ignores=[]), '<actual process_sample with invalid end clock>', 'exec'), bindings)
            with self.subTest(raw=raw):
                result = bindings['process_sample']()
                self.assertFalse(result['available']);self.assertEqual(result['rawUptimeEnd'], raw)
                self.assertEqual(result['rawUptimeStart'], '100 0\n');self.assertIn('error', result)

    def observe(self, before=None, name=None, after=None):
        fields = ['R'] + ['0'] * 21
        fields[1], fields[11], fields[12], fields[19], fields[21] = '7', '123', '45', '900', '60'
        raw = '11 (pocketchat.test) ' + ' '.join(fields)
        values = [raw if before is None else before, (BENCH.PACKAGE if name is None else name).encode()+b'\0', raw if after is None else after]
        def adb(*args, **kwargs):
            expected = ('exec-out', 'cat', '/proc/11/' + ('cmdline' if len(values) == 2 else 'stat'))
            self.assertEqual(args, expected)
            self.assertEqual(kwargs.get('binary', False), len(values) == 2)
            return values.pop(0)
        result = BENCH.process_observation(adb, dict(pid=11, ppid=7, uid='u0_a1', process=BENCH.PACKAGE))
        return result, raw

    def test_actual_process_identity_is_bracketed_around_cmdline(self):
        name = Path('/proc/self/cmdline').read_bytes().split(b'\0', 1)[0].decode()
        def read(*args, **kwargs):
            return Path(args[-1]).read_bytes() if kwargs.get('binary') else Path(args[-1]).read_text()
        result = BENCH.process_observation(read, dict(pid=os.getpid(), ppid=os.getppid(), uid=str(os.getuid()), process=name))
        self.assertTrue(result['available'])
        self.assertEqual(result['process']['process'], name)
        self.assertEqual(bytes.fromhex(result['process']['rawCmdlineHex']).split(b'\0', 1)[0].decode(), name)
        self.assertEqual(BENCH.parse_proc_stat(result['process']['rawStatBefore'])['startTicks'], result['process']['startTicks'])

    def test_discovery_to_proc_pid_reuse_cannot_be_counted_as_app_cpu(self):
        result, _ = self.observe(name='unrelated-new-process')
        self.assertFalse(result['available']);self.assertNotIn('process', result)
        self.assertIn('cmdline differs', result['error'])
        self.assertIn('unrelated-new-process', bytes.fromhex(result['rawCmdlineHex']).decode())
        self.assertFalse(BENCH.cpu_summary([dict(result, uptimeSeconds=10), dict(result, uptimeSeconds=11)], 100)['available'])

    def test_lifetime_parent_and_name_races_are_unavailable(self):
        _, raw = self.observe()
        for changed in (raw.replace(' 900 ', ' 901 '), raw.replace('R 7 ', 'R 8 '),
                        raw.replace('(pocketchat.test)', '(other)'), raw.replace('11 (', '12 ('),
                        raw.replace(' 123 ', ' 122 ')):
            result, _ = self.observe(after=changed)
            with self.subTest(raw=changed):
                self.assertFalse(result['available']);self.assertNotIn('process', result)
                self.assertEqual(result['rawStatAfter'], changed)

    def test_denied_actual_identity_cannot_fall_back_to_ps_name(self):
        def denied(*args, **kwargs):
            raise subprocess.CalledProcessError(1, args, output=b'Permission denied')
        result = BENCH.process_observation(denied, dict(pid=11, ppid=7, uid='u0_a1', process=BENCH.PACKAGE))
        self.assertFalse(result['available']);self.assertNotIn('process', result)
        self.assertEqual(result['raw'], 'Permission denied')

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

    def test_reused_pid_is_two_starttime_identities(self):
        result = BENCH.cpu_summary([sample(10, process(1, 1, 100)), sample(11, process(1, 1, 150)),
                                    sample(12, process(1, 1150, 25)), sample(13, process(1, 1150, 50))], 100)
        self.assertEqual(result['cpuSecondsObserved'], 1)
        self.assertEqual([p['startTicks'] for p in result['observedProcessIdentities']], [1, 1150])
        self.assertFalse(result['completeProcessAttributionProven'])
        self.assertFalse(result['observedProcessEndsCovered'])

    def test_decreasing_counter_is_unavailable_not_negative_cpu(self):
        result = BENCH.cpu_summary([sample(10, process(1, 1, 150)), sample(12, process(1, 1, 100))], 100)
        self.assertFalse(result['available'])
        self.assertNotIn('cpuSecondsObserved', result)

    def test_missing_counters_are_not_reported_as_zero_cpu(self):
        self.assertFalse(BENCH.cpu_summary([sample(10), sample(12)], 100)['available'])
        self.assertFalse(BENCH.cpu_summary([{'available': False}], 100)['available'])
        self.assertFalse(BENCH.cpu_summary([sample(10, process(1, 1, 1)), sample(12, process(1, 1, 2))], None)['available'])


if __name__ == '__main__':
    unittest.main()
