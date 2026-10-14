"""Counterfeit launcher-state controls only; no actual adb/device is exercised.

The real guard and package parser execute against explicit fake ADB states.
These controls do not establish Android, keyboard, APK, or application readiness.
"""
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT / 'tools/gecko'))
import caret_launcher_guard as guard
import run_caret_editing_phase as phase

PACKAGE = 'com.google.android.apps.nexuslauncher'
NONCE = 'e' * 32
RESTORE = {0:'default-state',1:'enable',2:'disable',3:'disable-user',4:'disable-until-used'}
STATE = {operation:state for state,operation in RESTORE.items()}
HOME_COMMAND = ('shell','cmd','package','resolve-activity','--brief','--user','0',
                '-a','android.intent.action.MAIN','-c','android.intent.category.HOME')
NORMAL_WINDOW = '  mCurrentFocus=Window{fake123 u0 local.pocketchat.test/local.pocketchat.ControlledFixture}\n'


def identity():
    return dict(schema=1,sourceCommit='a'*40,sourceTree='b'*40,runId='12345',runAttempt='1',
                scope='Counterfeit host identity; no installed APK claim')


def package_dump(state,package=PACKAGE,user=0,installed='true'):
    return ('Packages:\n  Package ['+package+'] (fake123):\n    userId=10123\n'
            '    User '+str(user)+': ceDataInode=77 installed='+installed+
            ' hidden=false suspended=false stopped=false notLaunched=false enabled='+str(state)+
            ' instant=false virtual=false\n')


class SyntheticAdbError(RuntimeError):
    def __init__(self,message):
        super().__init__(message)
        self.stdout = b'Synthetic partial package operation\n'
        self.stderr = '原始 synthetic stderr🙂\n'.encode('utf-8')


class FakeAdb:
    """Finite command adapter; unknown commands or package mutations fail loudly."""
    def __init__(self,state=0,present=True,qemu='1',current_user='0',initial_dump=None,before_window=NORMAL_WINDOW,
                 after_window=NORMAL_WINDOW,package_lines=None,disable_error_after_change=False,
                 force_stop_error=False,restore_error_after_change=False,disabled_dump=None,
                 restored_dump=None,restored_home=None,guarded_windows=None):
        self.initial,self.state,self.present,self.qemu = state,state,present,qemu
        self.current_user = current_user
        self.calls,self.pm_changes = [],[]
        self.initial_dump,self.before_window,self.after_window = initial_dump,before_window,after_window
        self.package_lines,self.disabled_dump,self.restored_dump = package_lines,disabled_dump,restored_dump
        self.disable_error_after_change,self.force_stop_error = disable_error_after_change,force_stop_error
        self.restore_error_after_change,self.restored_home = restore_error_after_change,restored_home
        self.guarded_windows = list(guarded_windows or [])
        self.window_reads = 0

    def __call__(self,*parts):
        self.calls.append(parts)
        if parts == ('shell','getprop','ro.kernel.qemu'):
            return self.qemu
        if parts == ('shell','am','get-current-user'):
            return self.current_user
        if parts == ('shell','pm','list','packages',PACKAGE):
            return self.package_lines if self.package_lines is not None else ('package:'+PACKAGE+'\n' if self.present else '')
        if parts == HOME_COMMAND:
            if len(self.pm_changes)>=2 and self.restored_home is not None:
                return self.restored_home
            return (PACKAGE+'/.NexusLauncherActivity\n' if self.state in (0,1)
                    else 'com.android.launcher3/.Launcher\n')
        if parts == ('shell','dumpsys','window','displays'):
            self.window_reads += 1
            if self.window_reads == 1:
                return self.before_window
            return self.guarded_windows.pop(0) if self.guarded_windows else self.after_window
        if parts == ('shell','dumpsys','package',PACKAGE):
            if not self.pm_changes and self.initial_dump is not None:
                return self.initial_dump
            if len(self.pm_changes)==1 and self.disabled_dump is not None:
                return self.disabled_dump
            if len(self.pm_changes)>=2 and self.restored_dump is not None:
                return self.restored_dump
            return package_dump(self.state)
        if len(parts)==6 and parts[:2]==('shell','pm') and parts[2] in STATE:
            if parts[3:] != ('--user','0',PACKAGE):
                raise AssertionError('Only exact NexusLauncher User 0 state may be changed')
            self.state = STATE[parts[2]]
            self.pm_changes.append((parts[2],self.state))
            if len(self.pm_changes)==1 and self.disable_error_after_change:
                raise SyntheticAdbError('Synthetic prepare command failed after disabling launcher')
            if len(self.pm_changes)>=2 and self.restore_error_after_change:
                raise SyntheticAdbError('Synthetic restore command failed after changing launcher state')
            return 'Package '+PACKAGE+' new state: '+parts[2]+'\n'
        if parts == ('shell','am','force-stop','--user','0',PACKAGE):
            if self.force_stop_error:
                raise SyntheticAdbError('Synthetic launcher force-stop failed')
            return ''
        raise AssertionError('Unexpected ADB operation in host guard: '+repr(parts))


def harness(**options):
    fake = FakeAdb(**options)
    record = {}
    instance = guard.LauncherGuard(adb=fake,identity=identity(),record=record,nonce=NONCE)
    return fake,record,instance


class EnabledStateParserTest(unittest.TestCase):
    def test_all_five_exact_android_enabled_states_are_preserved(self):
        for state in range(5):
            with self.subTest(state=state):
                self.assertIs(type(guard._enabled_state(package_dump(state))),int)
                self.assertEqual(guard._enabled_state(package_dump(state)),state)

    def test_unsafe_package_headers_user_ownership_and_enabled_tokens_are_rejected(self):
        normal = package_dump(0)
        invalid = [None,b'not decoded',normal.replace('  Package ['+PACKAGE+'] (fake123):\n',''),
            package_dump(0,package='local.pocketchat.test'),normal+normal,
            normal+'  Package [another.package] (foreign):\n',package_dump(0,user=10),
            normal+'    User 0: installed=true enabled=1\n',package_dump(0,installed='false'),
            normal.replace('installed=true','installed=true installed=false'),
            normal.replace('enabled=0','enabled=0 enabled=1')]
        invalid += [package_dump(value) for value in ('-1','5','true','null','1.0','+1','01','')]
        for raw in invalid:
            with self.subTest(raw=raw),self.assertRaises(ValueError):
                guard._enabled_state(raw)


class LauncherGuardTest(unittest.TestCase):
    def assert_known_package_only(self,fake):
        for parts in fake.calls:
            if parts[:2]==('shell','pm') and parts[2] in STATE:
                self.assertEqual(parts[3:],('--user','0',PACKAGE))
            if parts[:3]==('shell','am','force-stop'):
                self.assertEqual(parts,('shell','am','force-stop','--user','0',PACKAGE))
        self.assertFalse(any('input' in parts or 'settings' in parts for parts in fake.calls),
                         'The guard must not dismiss errors or modify input policy')

    def test_normal_workloads_restore_exact_states_zero_through_four_before_later_home(self):
        for initial in range(5):
            with self.subTest(initial=initial):
                fake,record,instance = harness(state=initial)
                phases = []
                sentinel = object()

                def workload():
                    phases.extend([('original-wrapper',fake.state),('new-caret',fake.state)])
                    return sentinel

                self.assertIs(instance.run(workload),sentinel)
                phases.append(('later-HOME-suite',fake.state))
                self.assertEqual(phases,[('original-wrapper',3),('new-caret',3),('later-HOME-suite',initial)])
                self.assertEqual(fake.pm_changes,[('disable-user',3),(RESTORE[initial],initial)])
                self.assertEqual(fake.state,initial)
                self.assertEqual(record['initialEnabledState'],initial)
                self.assertEqual(guard._enabled_state(record['restoredPackageRaw']),initial)
                self.assertEqual(record['restoredHome'],record['initialHome'])
                self.assertTrue(record['mutationAttempted']);self.assertTrue(record['restorationVerified'])
                self.assertTrue(record['confirmedUser0'])
                self.assertEqual(record['status'],'passed')
                self.assertEqual(record['identity'],identity());self.assertEqual(record['runNonce'],NONCE)
                self.assertFalse(record['applicationAcceptance']);self.assertFalse(record['physicalPhoneAcceptance'])
                self.assert_known_package_only(fake)

    def test_absent_launcher_runs_without_any_package_mutation(self):
        fake,record,instance = harness(present=False)
        sentinel = {'original-result':'preserved'}
        self.assertIs(instance.run(lambda:sentinel),sentinel)
        self.assertEqual(fake.pm_changes,[])
        self.assertFalse(any(parts[:3]==('shell','am','force-stop') for parts in fake.calls))
        self.assertFalse(record['launcherPresent']);self.assertFalse(record['mutationAttempted'])
        self.assertTrue(record['restorationVerified'])
        self.assert_known_package_only(fake)

    def test_non_emulator_and_ambiguous_package_presence_fail_before_workload_or_mutation(self):
        options = [dict(qemu='0'),dict(qemu=''),dict(qemu='true'),
            dict(package_lines='package:'+PACKAGE+'\npackage:'+PACKAGE+'\n'),
            dict(package_lines='package:'+PACKAGE+'.foreign\n'),
            dict(package_lines='package:'+PACKAGE+'\npackage:local.pocketchat.test\n')]
        for configuration in options:
            with self.subTest(configuration=configuration):
                fake,record,instance = harness(**configuration);ran = []
                with self.assertRaises(ValueError):
                    instance.run(lambda:ran.append(True))
                self.assertEqual(ran,[]);self.assertEqual(fake.pm_changes,[])
                self.assertFalse(record['mutationAttempted'])
                self.assert_known_package_only(fake)

    def test_unsafe_user_zero_snapshot_never_authorizes_launcher_mutation(self):
        for raw in [package_dump(0,package='local.pocketchat.test'),package_dump(0,user=10),
                    package_dump(0,installed='false'),package_dump(5),package_dump('1.0'),
                    package_dump(0)+package_dump(1)]:
            with self.subTest(raw=raw):
                fake,record,instance = harness(initial_dump=raw);ran = []
                with self.assertRaises(ValueError):
                    instance.run(lambda:ran.append(True))
                self.assertEqual(fake.pm_changes,[]);self.assertEqual(ran,[])
                self.assertIn(raw,json.dumps(record,ensure_ascii=False).replace('\\n','\n'))

    def test_nonzero_or_ambiguous_current_user_fails_before_mutation(self):
        for user in ['10','-1','','00','0\n10']:
            fake,record,instance = harness(current_user=user);ran = []
            with self.subTest(user=user),self.assertRaises(ValueError):
                instance.run(lambda:ran.append(True))
            self.assertEqual(ran,[]);self.assertEqual(fake.pm_changes,[])
            self.assertFalse(record['mutationAttempted'])
            self.assertNotIn('confirmedUser0',record)
            self.assertEqual(fake.calls,[('shell','getprop','ro.kernel.qemu'),
                                         ('shell','am','get-current-user')])

    def test_only_exact_known_launcher_anr_is_allowed_before_the_guard(self):
        before = '  mCurrentFocus=Window{fake u0 Application Not Responding: '+PACKAGE+'}\n'
        fake,record,instance = harness(before_window=before)
        self.assertEqual(instance.run(lambda:fake.state),3)
        self.assertEqual(record['initialWindowRaw'],before)
        self.assertEqual(fake.state,0)
        for owner in ['local.pocketchat.test','com.android.systemui',PACKAGE+'.foreign']:
            raw = '  mCurrentFocus=Window{fake u0 Application Not Responding: '+owner+'}\n'
            fake,record,instance = harness(before_window=raw);ran = []
            with self.subTest(owner=owner),self.assertRaises(ValueError):
                instance.run(lambda:ran.append(True))
            self.assertEqual(ran,[]);self.assertEqual(fake.pm_changes,[])
            self.assertEqual(record['initialWindowRaw'],raw)
            self.assert_known_package_only(fake)
        raw = before.replace(' u0 ',' u10 ')
        fake,record,instance = harness(before_window=raw);ran = []
        with self.assertRaises(ValueError):
            instance.run(lambda:ran.append(True))
        self.assertEqual(ran,[]);self.assertEqual(fake.pm_changes,[])

    def test_exact_launcher_anr_may_close_asynchronously_before_workload(self):
        known = '  mCurrentFocus=Window{fake u0 Application Not Responding: '+PACKAGE+'}\n'
        fake,record,instance = harness(before_window=known,
                                      guarded_windows=[known,'  mCurrentFocus=null\n',NORMAL_WINDOW])
        waits = []
        with mock.patch.object(guard.time,'sleep',side_effect=waits.append):
            self.assertEqual(instance.run(lambda:fake.state),3)
        self.assertEqual(waits,[.1,.1])
        self.assertEqual(record['guardedWindowRaw'],NORMAL_WINDOW)
        self.assertEqual(fake.state,0);self.assertTrue(record['restorationVerified'])
        self.assert_known_package_only(fake)

    def test_known_launcher_anr_timeout_is_bounded_and_restores_without_workload(self):
        known = '  mCurrentFocus=Window{fake u0 Application Not Responding: '+PACKAGE+'}\n'
        fake,record,instance = harness(after_window=known);ran = []
        with mock.patch.object(guard.time,'monotonic',side_effect=[100.,105.]), \
             mock.patch.object(guard.time,'sleep',side_effect=AssertionError('No wait after deadline')):
            with self.assertRaisesRegex(ValueError,'foreground window did not become available'):
                instance.run(lambda:ran.append(True))
        self.assertEqual(ran,[]);self.assertEqual(fake.state,0)
        self.assertTrue(record['restorationVerified'])
        self.assert_known_package_only(fake)

    def test_application_crash_and_system_error_windows_are_never_suppressed(self):
        for marker in ['Application Not Responding: local.pocketchat.test',
                       'Application Error: local.pocketchat.test','SYSTEM_ERROR local.pocketchat.test']:
            raw = '  mCurrentFocus=Window{fake u0 '+marker+'}\n'
            fake,record,instance = harness(after_window=raw);ran = []
            with self.subTest(marker=marker),self.assertRaises(ValueError):
                instance.run(lambda:ran.append(True))
            self.assertEqual(ran,[]);self.assertEqual(fake.state,0)
            self.assertEqual(record['guardedWindowRaw'],raw)
            self.assertEqual(record['status'],'failed')
            self.assert_known_package_only(fake)

    def test_disable_command_failure_after_mutation_still_restores_exact_initial_state(self):
        fake,record,instance = harness(state=4,disable_error_after_change=True);ran = []
        with self.assertRaises(SyntheticAdbError):
            instance.run(lambda:ran.append(True))
        self.assertEqual(ran,[])
        self.assertEqual(fake.pm_changes,[('disable-user',3),('disable-until-used',4)])
        self.assertEqual(fake.state,4)
        self.assertTrue(record['mutationAttempted']);self.assertTrue(record['restorationVerified'])
        failed = next(row for row in record['commands'] if row['status']=='failed')
        self.assertEqual(failed['stdout'],'Synthetic partial package operation\n')
        self.assertEqual(failed['stderr'],'原始 synthetic stderr🙂\n')
        self.assertGreaterEqual(failed['completedAtMonotonicNanos'],failed['startedAtMonotonicNanos'])

    def test_force_stop_or_disabled_state_confirmation_failure_restores_before_return(self):
        for configuration in [dict(force_stop_error=True),dict(disabled_dump=package_dump(0))]:
            fake,record,instance = harness(state=2,**configuration);ran = []
            with self.subTest(configuration=configuration),self.assertRaises((SyntheticAdbError,ValueError)):
                instance.run(lambda:ran.append(True))
            self.assertEqual(ran,[]);self.assertEqual(fake.state,2)
            self.assertEqual(fake.pm_changes[-1],('disable',2))
            self.assertTrue(record['restorationVerified'])

    def test_workload_exception_and_keyboard_interrupt_restore_and_propagate_original_error(self):
        for failure in [RuntimeError('Synthetic protected workload failed'),KeyboardInterrupt('Synthetic interrupted workload'),SystemExit(7)]:
            fake,record,instance = harness(state=1)

            def workload():
                self.assertEqual(fake.state,3)
                raise failure

            with self.subTest(failure=failure),self.assertRaises(type(failure)) as caught:
                instance.run(workload)
            self.assertIs(caught.exception,failure)
            self.assertEqual(fake.state,1);self.assertEqual(fake.pm_changes[-1],('enable',1))
            self.assertTrue(record['restorationVerified']);self.assertEqual(record['status'],'failed')
            self.assertEqual(record['error'],str(failure))

    def test_restore_command_failure_keeps_workload_and_restore_errors_and_is_fatal(self):
        fake,record,instance = harness(state=0,restore_error_after_change=True)
        failure = RuntimeError('Synthetic protected workload failed')

        def workload():
            raise failure

        with self.assertRaises(RuntimeError) as caught:
            instance.run(workload)
        self.assertIn('restoration failed',str(caught.exception))
        self.assertIsInstance(caught.exception.__cause__,SyntheticAdbError)
        self.assertEqual(record['error'],str(failure))
        self.assertIn('Synthetic restore command failed',record['restoreError'])
        self.assertEqual(record['status'],'failed');self.assertFalse(record['restorationVerified'])
        self.assertEqual(fake.state,0,'Even a potentially successful write with failed command status stays fatal')

    def test_restoration_state_or_home_mismatch_is_fatal_after_successful_workload(self):
        for configuration in [dict(restored_dump=package_dump(3)),
                              dict(restored_home='com.android.launcher3/.Launcher\n')]:
            fake,record,instance = harness(**configuration);ran = []
            with self.subTest(configuration=configuration),self.assertRaises(RuntimeError):
                instance.run(lambda:ran.append(True))
            self.assertEqual(ran,[True]);self.assertEqual(record['status'],'failed')
            self.assertFalse(record['restorationVerified']);self.assertIn('restoreError',record)

    def test_guard_instance_cannot_replay_the_workload_or_state_changes(self):
        fake,record,instance = harness();ran = []
        instance.run(lambda:ran.append(True));calls = fake.calls[:]
        with self.assertRaises(ValueError):
            instance.run(lambda:ran.append(True))
        self.assertEqual(ran,[True]);self.assertEqual(fake.calls,calls)

    def test_invalid_fixed_serial_identity_and_nonce_cannot_issue_commands(self):
        variants = [dict(serial='real-phone'),dict(nonce='F'*32),dict(nonce='short'),
                    dict(identity=dict(identity(),schema=True)),dict(identity=dict(identity(),runId='0')),
                    dict(identity=dict(identity(),sourceCommit='foreign'))]
        for changed in variants:
            fake = FakeAdb();record = {}
            configuration = dict(adb=fake,identity=identity(),record=record,nonce=NONCE)
            configuration.update(changed)
            with self.subTest(changed=changed),self.assertRaises(ValueError):
                guard.LauncherGuard(**configuration)
            self.assertEqual(fake.calls,[]);self.assertEqual(fake.pm_changes,[])


def coordinator_args():
    root = Path('/synthetic/launcher guard repository')
    out = root / 'work/synthetic proof'
    return SimpleNamespace(root=root,out=out,adb='/synthetic/bin/adb',serial='emulator-5554',
        build_receipt=out/'build.json',sdk_receipt=out/'sdk.json',sdk_aar=out/'modified.aar',
        official_sdk_aar=out/'official.aar',integration_apk=out/'integration.apk',
        release_apk=out/'release.apk')


class EditingCoordinatorTest(unittest.TestCase):
    def expected_commands(self,args):
        common = ['--adb',args.adb,'--serial','emulator-5554','--root',str(args.root)]
        original = [sys.executable,str(args.root/'tests/gecko/run_caret_bound_performance.py'),
            *common,'--out',str(args.out),'--build-receipt',str(args.build_receipt),
            '--sdk-receipt',str(args.sdk_receipt),'--sdk-aar',str(args.sdk_aar),
            '--official-sdk-aar',str(args.official_sdk_aar),'--integration-apk',str(args.integration_apk)]
        caret = [sys.executable,str(args.root/'tests/gecko/run_gecko_caret_compat.py'),'--normal-acceptance',
            *common,'--out',str(args.out/'caret-compat'),'--sdk-receipt',str(args.sdk_receipt),
            '--build-receipt',str(args.build_receipt),'--sdk-aar',str(args.sdk_aar),
            '--official-sdk-aar',str(args.official_sdk_aar),'--integration-apk',str(args.integration_apk),
            '--release-apk',str(args.release_apk)]
        return [original,caret]

    def assert_workload_times(self,record):
        for row in record['workloads']:
            self.assertEqual(row['invocationCount'],1)
            self.assertIs(type(row['startedAtMonotonicNanos']),int)
            self.assertGreater(row['startedAtMonotonicNanos'],0)
            self.assertGreaterEqual(row['completedAtMonotonicNanos'],row['startedAtMonotonicNanos'])

    def test_both_actual_commands_run_exactly_once_inside_guard_before_home_restore(self):
        args = coordinator_args();fake,record,instance = harness(state=4)
        observed = []

        def fake_run(command,*,cwd,check):
            observed.append((list(command),cwd,check,fake.state))
            return SimpleNamespace(returncode=0)

        with mock.patch.object(phase.subprocess,'run',side_effect=fake_run), \
             mock.patch.object(phase.time,'sleep',side_effect=AssertionError('No fixture input pacing')):
            self.assertEqual(instance.run(lambda:phase.run_workloads(args,record)),0)
        self.assertEqual(observed,[(command,args.root,False,3) for command in self.expected_commands(args)])
        self.assertEqual([row['name'] for row in record['workloads']],
                         ['original-performance-wrapper','caret-compatibility'])
        self.assertEqual([row['exitCode'] for row in record['workloads']],[0,0])
        self.assert_workload_times(record)
        self.assertEqual(fake.state,4);self.assertTrue(record['restorationVerified'])
        self.assertEqual(fake.pm_changes,[('disable-user',3),('disable-until-used',4)])

    def test_ordinary_positive_failure_still_runs_the_second_fixture_once(self):
        for exits in ([1,0],[7,0],[0,1],[1,1]):
            args = coordinator_args();fake,record,instance = harness(state=1)
            with self.subTest(exits=exits),mock.patch.object(phase.subprocess,'run',
                    side_effect=[SimpleNamespace(returncode=code) for code in exits]) as process:
                self.assertEqual(instance.run(lambda:phase.run_workloads(args,record)),1)
            self.assertEqual(process.call_args_list,
                [mock.call(command,cwd=args.root,check=False) for command in self.expected_commands(args)])
            self.assertEqual([row['exitCode'] for row in record['workloads']],exits)
            self.assert_workload_times(record)
            self.assertEqual(fake.state,1);self.assertTrue(record['restorationVerified'])

    def test_terminated_original_fixture_aborts_second_and_restores_guard(self):
        for code in (-15,-9):
            args = coordinator_args();fake,record,instance = harness(state=2)
            with self.subTest(code=code),mock.patch.object(phase.subprocess,'run',
                    return_value=SimpleNamespace(returncode=code)) as process:
                with self.assertRaisesRegex(ValueError,'terminated'):
                    instance.run(lambda:phase.run_workloads(args,record))
            process.assert_called_once_with(self.expected_commands(args)[0],cwd=args.root,check=False)
            self.assertEqual(len(record['workloads']),1)
            self.assertEqual(record['workloads'][0]['exitCode'],code)
            self.assert_workload_times(record)
            self.assertEqual(fake.state,2);self.assertTrue(record['restorationVerified'])

    def test_process_exception_aborts_second_preserves_error_and_restores_guard(self):
        for failure in (RuntimeError('Synthetic fixture launch failed'),KeyboardInterrupt('Synthetic interruption')):
            args = coordinator_args();fake,record,instance = harness()
            with self.subTest(failure=failure),mock.patch.object(phase.subprocess,'run',side_effect=failure) as process:
                with self.assertRaises(type(failure)) as caught:
                    instance.run(lambda:phase.run_workloads(args,record))
            self.assertIs(caught.exception,failure)
            process.assert_called_once_with(self.expected_commands(args)[0],cwd=args.root,check=False)
            self.assertEqual(len(record['workloads']),1)
            self.assertNotIn('exitCode',record['workloads'][0])
            self.assert_workload_times(record)
            self.assertEqual(record['error'],str(failure))
            self.assertEqual(fake.state,0);self.assertTrue(record['restorationVerified'])

    def test_second_fixture_exception_restores_after_both_invocations(self):
        args = coordinator_args();fake,record,instance = harness(state=3)
        failure = RuntimeError('Synthetic second fixture launch failed')
        with mock.patch.object(phase.subprocess,'run',
                side_effect=[SimpleNamespace(returncode=0),failure]) as process:
            with self.assertRaises(RuntimeError) as caught:
                instance.run(lambda:phase.run_workloads(args,record))
        self.assertIs(caught.exception,failure)
        self.assertEqual(process.call_args_list,
            [mock.call(command,cwd=args.root,check=False) for command in self.expected_commands(args)])
        self.assertEqual(len(record['workloads']),2);self.assert_workload_times(record)
        self.assertEqual(fake.state,3);self.assertTrue(record['restorationVerified'])


class WorkflowEditingExitTest(unittest.TestCase):
    def editing_block(self):
        lines = (ROOT/'.github/workflows/gecko-integration.yml').read_text().splitlines()
        matches = [index for index,line in enumerate(lines)
                   if line.lstrip().startswith('if python3 tools/gecko/run_caret_editing_phase.py ')]
        self.assertEqual(len(matches),1,'Exactly one actual editing coordinator invocation required')
        start = matches[0]
        indent = len(lines[start])-len(lines[start].lstrip())
        end = next(index for index in range(start+1,len(lines))
                   if lines[index] == ' '*indent+'fi')
        return '\n'.join(line[indent:] for line in lines[start:end+1])

    def test_actual_workflow_continues_only_for_zero_or_restored_workload_failure(self):
        block = self.editing_block()
        for code in (0,1,2,137):
            # Only the exact checked-in shell branch runs. Functions replace all
            # process/ADB execution; this cannot launch fixtures or touch a device.
            script = ('set -e\nchecks_failed=0\n'
                      'adb() { :; }\npython3() { return '+str(code)+'; }\n'+block+
                      '\nprintf "LATER_HOME_REACHED checks_failed=%s\\n" "$checks_failed"\n')
            result = subprocess.run(['bash','-c',script],text=True,capture_output=True,timeout=5)
            with self.subTest(code=code):
                if code in (0,1):
                    self.assertEqual(result.returncode,0,result.stderr)
                    self.assertEqual(result.stdout,'LATER_HOME_REACHED checks_failed='+str(code)+'\n')
                else:
                    self.assertEqual(result.returncode,code,result.stderr)
                    self.assertEqual(result.stdout,'')


if __name__ == '__main__':
    unittest.main()
