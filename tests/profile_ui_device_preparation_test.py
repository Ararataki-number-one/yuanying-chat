"""Current preparation behavior with declared adb/clock boundaries, not device acceptance."""
import importlib.util
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('ui_device_preparation', ROOT / 'tools/gecko/prepare_ui_device.py')
preparation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preparation)
HOME = 'com.google.android.apps.nexuslauncher/com.google.android.apps.nexuslauncher.NexusLauncherActivity'
ACTIVITY = '  topResumedActivity=ActivityRecord{1 u0 ' + HOME + ' t1}\n'
WINDOW = '  mCurrentFocus=Window{2 u0 ' + HOME + '}\n'
# Exact current-focus field from b6 / run 43200807281 / attempt 1 / API 32,
# device-window-displays.txt before application installation. Other test state is synthetic.
CAPTURED_TRANSITION = '  mCurrentFocus=Window{b4c1f9e u0 ImmersiveModeConfirmation}\n'
ANR = '  mCurrentFocus=Window{cc68d45 u0 Application Not Responding: com.android.systemui}\n'


class Clock:
    def __init__(self): self.value = 0
    def now(self): return self.value
    def sleep(self, seconds): self.value += seconds


class Adb:
    def __init__(self, snapshots=None):
        self.snapshots = snapshots or [(HOME, ACTIVITY, WINDOW)]
        self.index = 0
        self.calls = []
        self.after = lambda parts: None
        self.failure = None
        self.qemu = '1'

    def run(self, argv, **options):
        self.calls.append((argv, options))
        if argv[:2] == ['git', 'rev-parse']:
            return subprocess.CompletedProcess(argv, 0, ('a' if argv[2] == 'HEAD' else 'b') * 40 + '\n', '')
        assert argv[:3] == ['adb', '-s', 'emulator-5554']
        parts = tuple(argv[3:])
        frame = self.snapshots[min(self.index, len(self.snapshots) - 1)]
        if parts == ('shell', 'getprop', 'ro.kernel.qemu'): out = self.qemu
        elif parts == ('shell', 'am', 'get-current-user'): out = '0'
        elif parts[:4] == ('shell', 'cmd', 'package', 'resolve-activity'): out = frame[0] + '\n'
        elif parts == ('shell', 'dumpsys', 'activity', 'activities'): out = frame[1]
        elif parts == ('shell', 'dumpsys', 'window', 'displays'):
            out = frame[2]
            self.index += 1
        elif parts == ('shell', 'input', 'keyevent', 'KEYCODE_HOME'): out = ''
        else: raise AssertionError('Unexpected device action: ' + repr(parts))
        self.after(parts)
        if self.failure and parts == self.failure[0]:
            return subprocess.CompletedProcess(argv, 1, self.failure[1], self.failure[2])
        return subprocess.CompletedProcess(argv, 0, out, '')


class PreparationTests(unittest.TestCase):
    def run_preparation(self, fake, clock=None, timeout=2):
        self.clock = clock or Clock()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'record.json'
            with patch.object(preparation.subprocess, 'run', fake.run), \
                 patch.object(preparation.time, 'monotonic', self.clock.now), \
                 patch.object(preparation.time, 'sleep', self.clock.sleep):
                try:
                    return preparation.prepare('adb', 'emulator-5554', path, timeout)
                finally:
                    self.record = json.loads(path.read_text()) if path.exists() else None

    def test_two_actual_current_snapshots_after_one_home_are_required(self):
        fake = Adb()
        record = self.run_preparation(fake)
        self.assertEqual(record['status'], 'prepared')
        self.assertFalse(record['applicationAcceptance'])
        self.assertEqual(record['homeNavigations'], 1)
        self.assertEqual(fake.index, 3)  # Initial state cannot count as a post-HOME observation.
        self.assertEqual([c[0][-3:] for c in fake.calls if 'input' in c[0]], [['input', 'keyevent', 'KEYCODE_HOME']])
        self.assertTrue(all(c[1]['timeout'] <= 2 for c in fake.calls))

    def test_captured_api32_transition_cannot_pass_even_with_resumed_home(self):
        self.assertFalse(preparation.ready_observation(HOME, ACTIVITY, CAPTURED_TRANSITION)['ready'])
        with self.assertRaises(TimeoutError):
            self.run_preparation(Adb([(HOME, ACTIVITY, CAPTURED_TRANSITION)]), timeout=1)
        self.assertEqual(self.record['status'], 'failed')
        self.assertTrue(any(c.get('stdout') == CAPTURED_TRANSITION for c in self.record['commands']))

    def test_fallback_home_is_never_ready_and_never_navigated(self):
        home = 'com.android.settings/.FallbackHome'
        frame = (home, ACTIVITY.replace(HOME, 'com.android.settings/com.android.settings.FallbackHome'),
                 WINDOW.replace(HOME, 'com.android.settings/com.android.settings.FallbackHome'))
        fake = Adb([frame])
        with self.assertRaises(TimeoutError): self.run_preparation(fake, timeout=1)
        self.assertEqual(self.record['homeNavigations'], 0)

    def test_actual_anr_or_error_focus_fails_without_hiding_or_input(self):
        for focus in [ANR, ANR.replace('Not Responding', 'Error'), ANR.replace('Application Not Responding:', 'SYSTEM_ERROR')]:
            with self.subTest(focus=focus):
                fake = Adb([(HOME, ACTIVITY, focus)])
                with self.assertRaises(ValueError): self.run_preparation(fake)
                self.assertFalse(any('input' in c[0] for c in fake.calls))
                self.assertEqual(self.record['status'], 'failed')

    def test_historical_errors_and_activities_cannot_replace_current_fields(self):
        window = 'Last ANR: com.android.systemui\n' + WINDOW
        self.assertTrue(preparation.ready_observation(HOME, ACTIVITY, window)['ready'])
        self.assertFalse(preparation.ready_observation(HOME, 'lastResumedActivity=' + ACTIVITY, WINDOW)['ready'])
        self.assertFalse(preparation.ready_observation(HOME, ACTIVITY, 'mCurrentFocus=null\n')['ready'])
        for raw in [WINDOW + WINDOW, 'lastFocus=' + WINDOW, '']:
            with self.assertRaises(ValueError): preparation.current_focus(raw)

    def test_one_matching_sample_or_changed_window_does_not_pass(self):
        frames = [(HOME, ACTIVITY, WINDOW), (HOME, ACTIVITY, WINDOW),
                  (HOME, ACTIVITY, CAPTURED_TRANSITION), (HOME, ACTIVITY, WINDOW),
                  (HOME, ACTIVITY, WINDOW.replace('Window{2', 'Window{3')),
                  (HOME, ACTIVITY, WINDOW.replace('Window{2', 'Window{3'))]
        fake = Adb(frames)
        self.assertEqual(self.run_preparation(fake)['status'], 'prepared')
        self.assertEqual(fake.index, 6)

    def test_foreign_emulator_or_ambiguous_home_is_rejected(self):
        fake = Adb(); fake.qemu = '0'
        with self.assertRaises(ValueError): self.run_preparation(fake)
        self.assertFalse(any('input' in c[0] for c in fake.calls))
        for raw in ['', HOME + '\n' + HOME, 'ResolverActivity']:
            with self.assertRaises(ValueError): preparation.home_component(raw)

    def test_command_failure_retains_original_raw_streams(self):
        fake = Adb(); fake.failure = (('shell', 'dumpsys', 'window', 'displays'), 'original output', 'original error')
        with self.assertRaises(subprocess.CalledProcessError): self.run_preparation(fake)
        row = self.record['commands'][-1]
        self.assertEqual((row['stdout'], row['stderr'], row['exitCode']), ('original output', 'original error', 1))

    def test_late_successful_command_cannot_pass(self):
        clock = Clock(); fake = Adb()
        fake.after = lambda parts: setattr(clock, 'value', 3)
        with self.assertRaises(TimeoutError): self.run_preparation(fake, clock)
        self.assertEqual(self.record['status'], 'failed')

    def test_parser_time_is_inside_shared_budget(self):
        clock = Clock(); original = preparation.home_component
        def late(raw):
            value = original(raw); clock.value = 3; return value
        with patch.object(preparation, 'home_component', late):
            with self.assertRaises(TimeoutError): self.run_preparation(Adb(), clock)
        self.assertEqual(self.record['homeNavigations'], 0)

    def test_final_persistence_time_cannot_turn_timeout_into_prepared(self):
        clock = Clock(); original = Path.write_text
        def late(path, text, *args, **kwargs):
            if json.loads(text).get('status') == 'prepared': clock.value = 3
            return original(path, text, *args, **kwargs)
        with patch.object(Path, 'write_text', late):
            with self.assertRaises(TimeoutError): self.run_preparation(Adb(), clock)
        self.assertEqual(self.record['status'], 'failed')

    def test_workflow_keeps_existing_budgets_and_prepares_before_application(self):
        workflow = (ROOT / '.github/workflows/browser-workspace-validation.yml').read_text()
        call = 'python3 tools/gecko/prepare_ui_device.py '
        self.assertEqual(workflow.count(call), 1)
        self.assertLess(workflow.index('> work/glass-navigation/device-window-displays.txt'), workflow.index(call))
        self.assertLess(workflow.index(call), workflow.index('- name: Run real glass rendering'))
        self.assertIn('timeout-minutes: 12', workflow)
        self.assertIn('timeout-minutes: 30', workflow)
        self.assertIn('--timeout 45 --output work/glass-navigation/ui-device-preparation.json', workflow)
        self.assertIn('logcat -b all -d -v threadtime > work/glass-navigation/system-logcat.txt', workflow)


class BroadcastPreparationTests(unittest.TestCase):
    def exercise(self, *, stdout='Waiting for broadcasts...\nAll broadcast queues are idle!\n', code=0, late=False, expired=False, qemu='1'):
        self.clock=Clock();fake=Adb();fake.qemu=qemu;self.calls=[]
        def run(argv,**options):
            self.calls.append((argv,options))
            if argv[-3:]==['shell','am','wait-for-broadcast-idle']:
                if expired:raise subprocess.TimeoutExpired(argv,options['timeout'],output='still pending',stderr='original detail')
                if late:self.clock.value=121
                return subprocess.CompletedProcess(argv,code,stdout,'original detail')
            return fake.run(argv,**options)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'broadcast.json'
            with patch.object(preparation.subprocess,'run',run),patch.object(preparation.time,'monotonic',self.clock.now):
                try:return preparation.prepare_broadcasts('adb','emulator-5554',path,120)
                finally:self.record=json.loads(path.read_text()) if path.exists() else None

    def test_actual_zero_exit_and_final_completion_line_are_required(self):
        value=self.exercise();self.assertEqual(value['status'],'prepared');self.assertFalse(value['applicationAcceptance'])
        queue=[(a,o) for a,o in self.calls if a[-3:]==['shell','am','wait-for-broadcast-idle']]
        self.assertEqual(len(queue),1);self.assertEqual(queue[0][1]['timeout'],120)

    def test_nonzero_missing_marker_and_expired_process_cannot_prepare(self):
        for options,error in (({'code':1},subprocess.CalledProcessError),({'stdout':'waiting'},ValueError),
                              ({'expired':True},subprocess.TimeoutExpired),({'qemu':'0'},ValueError)):
            with self.subTest(options=options),self.assertRaises(error):self.exercise(**options)
            self.assertEqual(self.record['status'],'failed')

    def test_late_zero_exit_cannot_prepare(self):
        with self.assertRaises(TimeoutError):self.exercise(late=True)
        self.assertEqual(self.record['status'],'failed');self.assertEqual(self.record['commands'][-1]['exitCode'],0)

    def test_broadcast_preparation_does_not_accept_later_anr_or_change_home_budget(self):
        self.exercise()
        with self.assertRaises(ValueError):preparation.ready_observation(HOME,ACTIVITY,ANR)
        source=(ROOT/'tools/gecko/prepare_ui_device.py').read_text().split('def main():',1)[1]
        self.assertLess(source.index('prepare_broadcasts('),source.index('result = prepare('))
        self.assertIn('--broadcast-idle-timeout 120 --timeout 45', (ROOT/'.github/workflows/browser-workspace-validation.yml').read_text())


class WorkspaceCapacityTests(unittest.TestCase):
    """Run the unchanged full-workflow program at real filesystem/OS boundaries.

    The proc/cgroup and native-adb responses below are explicit host controls;
    they are not an Android execution or evidence that the observed ANR is fixed.
    """
    @classmethod
    def setUpClass(cls):
        import yaml
        cls.raw = (ROOT/'.github/workflows/browser-workspace-validation.yml').read_text()
        cls.workflow = yaml.safe_load(cls.raw)
        cls.program = cls.workflow['env']['ANDROID_CAPACITY_PREFLIGHT']
        cls.full_program = yaml.safe_load((ROOT/'.github/workflows/browser-2_1-acceptance.yml').read_text())['env']['ANDROID_CAPACITY_PREFLIGHT']
        cls.job = cls.workflow['jobs']['glass-device-acceptance']
        cls.setup = next(s['run'] for s in cls.job['steps'] if s.get('id') == 'browser-emulator')

    def exercise(self, *, affinity=(0,1,2,3), nproc=4, current='max 100000',
                 parent='max 100000', outer='max 100000', guest=None,
                 guest_error=None, changed_identity=False):
        source, tree = 'a'*40, 'b'*40
        self.calls = []
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            mount = directory/'cgroup'
            node = mount/'slice/job'
            node.mkdir(parents=True)
            for path, value in ((node,current),(node.parent,parent),(mount,outer)):
                (path/'cpu.max').write_text(value+'\n')
                (path/'cgroup.procs').write_text('123\n')
            original_read = Path.read_text
            def read(path, *args, **kwargs):
                if path == Path('/proc/self/cgroup'):
                    return '0::/slice/job\n'
                if path == Path('/proc/self/mountinfo'):
                    return '31 23 0:29 / '+str(mount)+' rw - cgroup2 cgroup rw\n'
                return original_read(path,*args,**kwargs)
            def command(argv, **options):
                self.calls.append((argv,options))
                if argv == ['git','rev-parse','HEAD']: return source+'\n'
                if argv == ['git','rev-parse','HEAD^{tree}']: return tree+'\n'
                if argv == ['nproc']:
                    self.assertEqual(options['timeout'],5)
                    return str(nproc)+'\n'
                self.assertEqual(argv,['adb','-s','emulator-5554','shell','getconf','_NPROCESSORS_ONLN'])
                self.assertEqual(options['timeout'],8)
                if guest_error is not None: raise guest_error
                return guest
            target = directory/'work/gecko-integration/android-capacity-glass-device-acceptance-workspace-api32.json'
            environment = dict(GITHUB_JOB='glass-device-acceptance',GITHUB_SHA=source,
                               GITHUB_RUN_ID='12345',GITHUB_RUN_ATTEMPT='2')
            previous_cwd = Path.cwd()
            try:
                os.chdir(directory)
                with patch.dict(os.environ,environment), patch.object(os,'sched_getaffinity',return_value=set(affinity)), \
                     patch.object(Path,'read_text',read), patch.object(subprocess,'check_output',command), \
                     contextlib.redirect_stdout(io.StringIO()):
                    def invoke(mode):
                        with patch.object(sys,'argv',['capacity',mode,'workspace-api32']), self.assertRaises(SystemExit) as exited:
                            exec(compile(self.program,'workspace:ANDROID_CAPACITY_PREFLIGHT','exec'),{})
                        return exited.exception.code,json.loads(original_read(target))
                    host_code,host_record = invoke('host')
                    guest_code = guest_record = None
                    if guest is not None or guest_error is not None:
                        self.assertEqual(host_code,0)
                        if changed_identity:
                            altered = dict(host_record,runAttempt='1')
                            target.write_text(json.dumps(altered))
                        guest_code,guest_record = invoke('guest')
                    return host_code,host_record,guest_code,guest_record
            finally:
                os.chdir(previous_cwd)

    def test_reused_program_is_exact_and_only_declared_workflow_delta_is_allowed(self):
        self.assertEqual(self.program,self.full_program)
        self.assertEqual(hashlib.sha256(self.program.encode()).hexdigest(),
                         '6cceab4542155328df5f61444742de7d289c9f5ee59b937fca93dd82218aaa63')
        # C4 b0f0ffb5758b943ccafa082569e7c767438d4d2a whole workflow bytes.
        # Undo only the declared resource provisioning and 2.1.8 branch triggers;
        # every old action/budget remains bound to the original workflow hash.
        before=self.raw
        current_branches="    branches: ['codex/browser-workspace-20261111', 'release/browser-2.1.7', 'release/browser-2.1.7-*', 'release/browser-2.1.8', 'release/browser-2.1.8-*']\n"
        old_branches=current_branches.replace(", 'release/browser-2.1.8', 'release/browser-2.1.8-*'",'')
        self.assertEqual(before.count(current_branches),1)
        before=before.replace(current_branches,old_branches,1)
        block='env:\n  ANDROID_CAPACITY_PREFLIGHT: |\n'+''.join('    '+line for line in self.program.splitlines(keepends=True))
        self.assertEqual(before.count(block),1);before=before.replace(block,'',1)
        for added in (
            '          export PATH="$ANDROID_HOME/platform-tools:$PATH"\n',
            '          test "$(command -v adb)" = "$ANDROID_HOME/platform-tools/adb"\n',
            '          python3 -c "$ANDROID_CAPACITY_PREFLIGHT" host \'workspace-api${{ matrix.device-api }}\'\n',
            '              python3 -c "$ANDROID_CAPACITY_PREFLIGHT" guest \'workspace-api${{ matrix.device-api }}\'\n',
            '            work/gecko-integration/android-capacity-*.json\n',
        ):
            self.assertEqual(before.count(added),1);before=before.replace(added,'',1)
        self.assertEqual(before.count(' -cores 4 '),1)
        before=before.replace(' -cores 4 ',' -cores 2 ',1)
        self.assertEqual(hashlib.sha256(before.encode()).hexdigest(),
                         '4b501a5f01a1bc30a32f5fcecf74f4dc07365c21b843fa7e88bd2b4883db8f5d')

    def test_actual_capacity_guards_precede_launch_and_original_home_with_pinned_adb(self):
        run=self.setup
        verified=run.index('python3 tools/gecko/prepare_platform_tools.py ')
        path=run.index('export PATH="$ANDROID_HOME/platform-tools:$PATH"')
        resolved=run.index('test "$(command -v adb)" = "$ANDROID_HOME/platform-tools/adb"')
        host=run.index('python3 -c "$ANDROID_CAPACITY_PREFLIGHT" host ')
        launch=run.index('nohup bash work/glass-navigation/emulator-supervisor.sh ')
        boot=run.index('for task_glass_attempt in $(seq 1 120); do')
        guest=run.index('python3 -c "$ANDROID_CAPACITY_PREFLIGHT" guest ')
        booted=run.index('task_glass_booted=true')
        home=run.index('python3 tools/gecko/prepare_ui_device.py ')
        self.assertEqual(sorted((verified,path,resolved,host,launch,boot,guest,booted,home)),
                         [verified,path,resolved,host,launch,boot,guest,booted,home])
        self.assertIn('if [ "$(timeout 5 "$ANDROID_HOME/platform-tools/adb" -s emulator-5554 shell getprop sys.boot_completed',run[boot:guest])
        self.assertIn(' -memory 3072 -cores 4 ',run)
        upload=next(s for s in self.job['steps'] if s.get('name')=='Upload glass acceptance cases, recordings and raw diagnostics')
        self.assertEqual(upload['if'],'always()')
        self.assertIn('work/gecko-integration/android-capacity-*.json',upload['with']['path'].splitlines())

    def test_actual_program_accepts_four_available_cpus_and_four_observed_guest_cpus(self):
        hc,host,gc,guest=self.exercise(guest='4\n',outer='400000 100000')
        self.assertEqual((hc,gc),(0,0))
        self.assertEqual((host['status'],guest['status']),('passed','passed'))
        self.assertEqual(host['host']['visibleCapacityCeilingNumerator'],4)
        self.assertEqual(host['host']['visibleCapacityCeilingDenominator'],1)
        self.assertEqual(len(host['host']['cpuMax']),3)
        self.assertEqual(guest['guest']['raw'],'4')
        self.assertEqual(guest['guest']['onlineCpus'],4)
        self.assertEqual((guest['sourceCommit'],guest['sourceTree'],guest['runId'],guest['runAttempt']),('a'*40,'b'*40,'12345','2'))

    def test_actual_program_rejects_low_affinity_nproc_and_every_ancestor_quota(self):
        for options in ({'affinity':(0,1,2)},{'nproc':3},{'current':'300000 100000'},
                        {'parent':'300000 100000'},{'outer':'399999 100000'},{'outer':'invalid'}):
            with self.subTest(options=options):
                code,record,_,_=self.exercise(**options)
                self.assertEqual(code,1);self.assertEqual(record['status'],'failed')
                self.assertFalse(any(argv[0]=='adb' for argv,_ in self.calls))

    def test_actual_program_rejects_wrong_guest_count_and_read_failure_without_fallback(self):
        for options in ({'guest':'2\n'},{'guest':'5\n'},{'guest':''},
                        {'guest_error':subprocess.TimeoutExpired('adb',8)}):
            with self.subTest(options=options):
                _,_,code,record=self.exercise(**options)
                self.assertEqual(code,1);self.assertEqual(record['status'],'failed')
                self.assertEqual(len([argv for argv,_ in self.calls if argv[0]=='adb']),1)

    def test_actual_guest_probe_rejects_a_host_receipt_from_another_attempt(self):
        _,_,code,record=self.exercise(guest='4\n',changed_identity=True)
        self.assertEqual(code,1);self.assertEqual(record['status'],'failed')
        self.assertIn('Capacity source/run differs',record['error'])
        self.assertFalse(any(argv[0]=='adb' for argv,_ in self.calls))


if __name__ == '__main__':
    unittest.main()
