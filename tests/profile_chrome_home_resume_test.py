"""Real resume functions with a controlled transport/clock; no Android acceptance."""
import ast
import hashlib
import importlib.util
import pathlib
import subprocess
import types
import unittest
from unittest.mock import patch
from ui_visual_preservation_contract import verify_shared_ui_source

ROOT=pathlib.Path(__file__).resolve().parents[1]
RUNNER=ROOT/'tests/gecko/run_chrome_collapse.py'
SHARED=ROOT/'tests/gecko/run_ui_visuals.py'
spec=importlib.util.spec_from_file_location('tested_chrome_resume',RUNNER)
resume=importlib.util.module_from_spec(spec);spec.loader.exec_module(resume)
TARGET='local.pocketchat.test/local.pocketchat.CompactChromeIntegrationActivity'
HOME='different.launcher/different.launcher.HomeActivity'
CLI=['--adb','/controlled tool/adb','--serial','controlled-5554']
# Exact pre-correction sequence from 64be4b4, exercised with the unchanged
# original focus function extracted below, rather than a second focus model.
ORIGINAL_SEQUENCE="""
adb('shell','input','keyevent','KEYCODE_HOME')
adb('shell','am','start','-W','--activity-single-top','-n',component)
focus('local.pocketchat.CompactChromeIntegrationActivity')
"""


def activity(component,user=0):
    return 'topResumedActivity=ActivityRecord{abc u'+str(user)+' '+component+' t8}\n'


class Transport:
    """HOME policy executes after command completion, as in the captured order."""
    def __init__(self):
        self.now=0.;self.calls=[];self.events=[];self.current=TARGET
        self.home_due=None;self.home_applied=False;self.keys=0;self.starts=0
        self.never_home=False;self.never_app=False;self.history_only=False
        self.wrong_home=False;self.wrong_user=False;self.missing_home=False
        self.ambiguous_home=False;self.bad_user=False;self.stall=None
        self.fail_start=False;self.expire_after_home=False

    def clock(self):return self.now

    def advance(self,amount):
        self.now+=amount
        if self.home_due is not None and self.now>=self.home_due:
            self.home_due=None;self.home_applied=True;self.current=HOME
            self.events.append(('home-applied',self.now))

    def sleep(self,amount):
        if not 0<amount<=.2:raise AssertionError(('unexpected blind wait',amount))
        self.advance(amount)

    def run(self,argv,**kw):
        assert argv[:3]==[CLI[1],'-s',CLI[3]],argv
        assert kw.get('check') is True and kw.get('text') is True
        assert kw.get('stdout')==subprocess.PIPE and kw.get('stderr')==subprocess.PIPE
        assert 'shell' not in kw and 0<kw['timeout']<=90
        parts=tuple(argv[3:]);self.calls.append((self.now,parts,kw['timeout']))
        if self.stall==parts or kw['timeout']<.1:
            self.advance(kw['timeout'])
            raise subprocess.TimeoutExpired(argv,kw['timeout'],output='actual controlled partial stdout',stderr='actual controlled stderr')
        self.advance(.1)
        if parts==('shell','am','get-current-user'):
            text='unknown\n' if self.bad_user else '0\n'
        elif parts[:4]==('shell','cmd','package','resolve-activity'):
            assert parts==('shell','cmd','package','resolve-activity','--brief','--user','0','-a','android.intent.action.MAIN','-c','android.intent.category.HOME')
            text='No activity found\n' if self.missing_home else 'priority=0 preferredOrder=0\ndifferent.launcher/.HomeActivity\n'
            if self.ambiguous_home:text+='another.launcher/.Home\n'
        elif parts==('shell','input','keyevent','KEYCODE_HOME'):
            self.keys+=1;self.events.append(('home-command-return',self.now))
            if not self.never_home:self.home_due=self.now+.15
            text=''
        elif parts==('shell','am','start','-W','--activity-single-top','-n',TARGET):
            self.starts+=1;self.events.append(('app-start',self.now))
            if self.fail_start:raise subprocess.CalledProcessError(1,argv,output='controlled start rejection',stderr='actual rejection')
            if self.home_applied and not self.never_app:self.current=TARGET
            text='Status: ok\n'
        elif parts==('shell','dumpsys','activity','activities'):
            if self.expire_after_home and self.home_applied and not self.starts:
                self.now=20.
            current=self.current
            if not self.starts:
                if self.wrong_home:current='other.launcher/other.launcher.Home'
                if self.history_only:
                    text='Hist #0: ActivityRecord{abc u0 '+HOME+' t7}\n'
                    text+='mLastResumedActivity: ActivityRecord{abc u0 '+HOME+' t7}\n'
                    text+=activity(TARGET)
                else:text=activity(current,10 if self.wrong_user else 0)
            else:text=activity(current)
        else:raise AssertionError(('Unexpected command',parts))
        return subprocess.CompletedProcess(argv,0,text,'')

    def legacy_adb(self,*parts):
        return self.run([CLI[1],'-s',CLI[3],*parts],check=True,text=True,
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=90).stdout


class HomeResumeTests(unittest.TestCase):
    def invoke(self,transport):
        with patch.object(resume.time,'monotonic',transport.clock),patch.object(resume.time,'sleep',transport.sleep),patch.object(resume.subprocess,'run',transport.run):
            return resume.resume_after_home(TARGET,CLI)

    def assert_budget(self,transport):
        self.assertLessEqual(transport.now,20.000001)
        for at,_,timeout in transport.calls:
            self.assertGreater(timeout,0);self.assertLessEqual(timeout,20-at+.000001)

    def test_original_pending_home_order_fails_with_actual_original_focus(self):
        transport=Transport()
        tree=ast.parse(SHARED.read_text())
        focus=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='focus')
        program=ast.fix_missing_locations(ast.Module(body=[focus],type_ignores=[]))
        namespace={'adb':transport.legacy_adb,'component':TARGET,
            'time':types.SimpleNamespace(monotonic=transport.clock,sleep=transport.sleep)}
        exec(compile(program,str(SHARED),'exec'),namespace)
        with self.assertRaises(TimeoutError):exec(ORIGINAL_SEQUENCE,namespace)
        self.assertEqual((transport.keys,transport.starts),(1,1))
        self.assertLess(next(t for n,t in transport.events if n=='app-start'),next(t for n,t in transport.events if n=='home-applied'))
        self.assertEqual(transport.current,HOME)

    def test_observation_barrier_orders_one_home_then_one_return(self):
        transport=Transport();self.invoke(transport)
        self.assertEqual((transport.keys,transport.starts),(1,1))
        self.assertLess(next(t for n,t in transport.events if n=='home-applied'),next(t for n,t in transport.events if n=='app-start'))
        self.assertEqual(transport.current,TARGET);self.assert_budget(transport)
        actions=[p for _,p,_ in transport.calls if p[:3] in [('shell','input','keyevent'),('shell','am','start')]]
        self.assertEqual(actions,[('shell','input','keyevent','KEYCODE_HOME'),('shell','am','start','-W','--activity-single-top','-n',TARGET)])

    def test_strict_current_fields_ignore_history_windows_and_other_users(self):
        raw='Hist #0: ActivityRecord{abc u0 '+HOME+' t7}\n'
        raw+='mLastResumedActivity: ActivityRecord{abc u0 '+HOME+' t7}\n'
        raw+='Window{abc u0 '+HOME+'}\n'+activity(TARGET)
        self.assertEqual(resume.current_resumed(raw),{(0,TARGET)})
        self.assertEqual(resume.current_resumed('mResumedActivity: ActivityRecord{abc u10 different.launcher/.HomeActivity t7}\n'),{(10,HOME)})
        self.assertEqual(resume.current_resumed('mResumedActivity=null\n'),set())
        with self.assertRaises(ValueError):resume.current_resumed('topResumedActivity=unrecognized current activity\n')

    def test_unconfirmed_home_never_starts_app(self):
        for flag in ('never_home','history_only','wrong_home','wrong_user'):
            with self.subTest(flag=flag):
                transport=Transport();setattr(transport,flag,True)
                with self.assertRaises(TimeoutError):self.invoke(transport)
                self.assertEqual((transport.keys,transport.starts),(1,0));self.assert_budget(transport)

    def test_app_missing_after_real_home_does_not_retry(self):
        transport=Transport();transport.never_app=True
        with self.assertRaises(TimeoutError):self.invoke(transport)
        self.assertEqual((transport.keys,transport.starts),(1,1));self.assert_budget(transport)

    def test_resolution_failures_issue_no_user_actions(self):
        for flag in ('missing_home','ambiguous_home','bad_user'):
            with self.subTest(flag=flag):
                transport=Transport();setattr(transport,flag,True)
                with self.assertRaises(ValueError):self.invoke(transport)
                self.assertEqual((transport.keys,transport.starts),(0,0));self.assert_budget(transport)

    def test_real_command_timeout_is_bounded_by_remaining_budget(self):
        for command in [('shell','am','get-current-user'),('shell','dumpsys','activity','activities')]:
            with self.subTest(command=command):
                transport=Transport();transport.stall=command
                with self.assertRaises(TimeoutError) as caught:self.invoke(transport)
                self.assertIsInstance(caught.exception.__cause__,subprocess.TimeoutExpired)
                self.assertIn('actual controlled partial stdout',str(caught.exception))
                self.assertEqual(transport.starts,0);self.assert_budget(transport)

    def test_deadline_exhausted_by_home_observation_does_not_start(self):
        transport=Transport();transport.expire_after_home=True
        with self.assertRaises(TimeoutError):self.invoke(transport)
        self.assertEqual((transport.keys,transport.starts),(1,0));self.assert_budget(transport)

    def test_nonzero_start_preserves_actual_error_and_never_retries(self):
        transport=Transport();transport.fail_start=True
        with self.assertRaises(RuntimeError) as caught:self.invoke(transport)
        self.assertIsInstance(caught.exception.__cause__,subprocess.CalledProcessError)
        self.assertIn('controlled start rejection',str(caught.exception))
        self.assertEqual((transport.keys,transport.starts),(1,1));self.assert_budget(transport)

    def test_cli_transport_matches_both_unchanged_entrypoints(self):
        expected=[CLI[1],'-s',CLI[3]]
        self.assertEqual(resume.resume_transport(CLI),expected)
        self.assertEqual(resume.resume_transport(CLI+['--scenario','cold','--out','/some output']),expected)
        with self.assertRaises(ValueError):resume.resume_transport(['--adb','','--serial','chosen'])
        for name in ['tests/gecko/run_ui_visuals.py','tests/gecko/run_chrome_collapse_diagnostic.py']:
            source=(ROOT/name).read_text()
            self.assertIn("add_argument('--adb',required=True)",source)
            self.assertIn("add_argument('--serial',required=True)",source)

    def test_original_shared_runner_and_remaining_workload_preserved(self):
        self.assertTrue(verify_shared_ui_source(SHARED.read_text())['originalWorkloadSemanticsPreserved'])
        tree=ast.parse(RUNNER.read_text());run=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='run')
        loop=next(n for n in run.body if isinstance(n,ast.For))
        replacements=[i for i,n in enumerate(loop.body) if isinstance(n,ast.Expr) and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Name) and n.value.func.id=='resume_after_home']
        self.assertEqual(len(replacements),1);at=replacements[0]
        self.assertEqual(ast.unparse(loop.body[at]),'resume_after_home(component)')
        loop.body[at:at+1]=ast.parse(ORIGINAL_SEQUENCE).body
        self.assertEqual(hashlib.sha256(ast.dump(run,include_attributes=False).encode()).hexdigest(),'b663b22628d1868c5348434823505d2ce23956cbe228a08d3c6e4043f39e83d8')

    def test_owned_download_addition_and_nonsemantic_formatting_are_allowed(self):
        source=SHARED.read_text()
        self.assertTrue(verify_shared_ui_source(source)['authorizedDownloadLabelAddition'])
        formatted='# Formatting does not change the protected workload.\n'+ast.unparse(ast.parse(source))+'\n'
        self.assertTrue(verify_shared_ui_source(formatted)['authorizedDownloadLabelAddition'])

    def test_changed_home_dependencies_capture_or_binding_are_rejected(self):
        source=SHARED.read_text()
        changes=[
            ("def focus(activity):\n        deadline=time.monotonic()+20", "def focus(activity):\n        deadline=time.monotonic()+21"),
            ("timeout=90).decode(errors='replace')", "timeout=91).decode(errors='replace')"),
            ("return ui_capture.read(deadline=deadline)", "return ui_capture.read(deadline=None)"),
            ("deadline=time.monotonic()+35;readiness_scrolls=0", "deadline=time.monotonic()+36;readiness_scrolls=0"),
            ("adb('shell','am','force-stop',package);adb('logcat','-c')", "adb('shell','am','force-stop',package);adb('shell','input','keyevent','KEYCODE_HOME');adb('logcat','-c')"),
            ("timeout=90),source,reload_loopback.TRACE,out,focus)", "timeout=91),source,reload_loopback.TRACE,out,focus)"),
            ("source,reload_loopback.TRACE,out,focus)", "source,reload_loopback.TRACE,out,lambda activity: None)"),
            ("p.add_argument('--serial',required=True)", "p.add_argument('--serial',required=False)"),
            ("['git','rev-parse','HEAD']", "['git','rev-parse','HEAD~1']"),
            ("sample['latency']==sample['expectedLatency']=='42 ms（02:00）'", "True"),
        ]
        for before,after in changes:
            with self.subTest(change=before):
                self.assertIn(before,source)
                with self.assertRaises(AssertionError):verify_shared_ui_source(source.replace(before,after,1))

    def test_encoding_cookie_uses_real_utf8_file_semantics(self):
        source=SHARED.read_text()
        self.assertTrue(verify_shared_ui_source('# coding: utf-8\n'+source)['authorizedDownloadLabelAddition'])
        altered='# coding: latin-1\n'+source
        self.assertNotEqual(ast.dump(ast.parse(altered),include_attributes=False),
            ast.dump(ast.parse(altered.encode('utf-8')),include_attributes=False))
        with self.assertRaises(AssertionError):verify_shared_ui_source(altered)

    def test_only_complete_strict_download_observation_is_allowed(self):
        source=SHARED.read_text()
        changes=[
            ("label_nonce=uuid.uuid4().hex if scene=='downloads' else None", "label_nonce=uuid.uuid4().hex"),
            ("if scene=='downloads':\n        # Small native payload", "if scene in ('downloads','chat'):\n        # Small native payload"),
            ("if label_nonce:launch.extend(['--es','visualNonce',label_nonce])", "if label_nonce:launch.extend(['--es','visualNonce','unowned'])"),
            ("if value.get('nonce')==label_nonce:payloads.append(raw)", "payloads.append(raw)"),
            ("assert len(payloads)==1,", "assert len(payloads)>=0,"),
            (".decode('utf-8')", ".decode('utf-8',errors='replace')"),
            ("        verify_download_location(record,source)", "        pass"),
            ("verify_captures(records,source)", "verify_captures(records)"),
            (", verify_download_location\n", "\n"),
        ]
        for before,after in changes:
            with self.subTest(change=before):
                self.assertIn(before,source)
                with self.assertRaises(AssertionError):verify_shared_ui_source(source.replace(before,after,1))


if __name__=='__main__':unittest.main()
