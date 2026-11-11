"""Controlled failure diagnostics; no real device or acceptance claim."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools/gecko'))
import ui_anr_diagnostic as ANR
import ui_visual_capture as CAPTURE

SOURCE = 'a'*40
NONCE = 'b'*32
ENV = {'CI':'true', 'GITHUB_RUN_ID':'123', 'GITHUB_RUN_ATTEMPT':'1'}
XML = '''<hierarchy><node package="android" class="android.widget.TextView"
 resource-id="android:id/alertTitle" text="元婴期院士 isn't responding"/>
 <node package="android" class="android.widget.Button" resource-id="android:id/aerr_close" enabled="true" clickable="true"/>
 <node package="android" class="android.widget.Button" resource-id="android:id/aerr_wait" enabled="true" clickable="true"/></hierarchy>'''.encode()


def attempt(raw=XML):
    return dict(index=7, commands=[dict(parts=['shell','cat','/sdcard/owned.xml'], exitCode=0,
        completedAtWallTimeMillis=1234,
        stdout=dict(text=raw.decode(), bytes=len(raw), sha256=ANR.digest(raw), truncated=False))])


def stack(pid=42, package='local.pocketchat.test'):
    return (f'----- pid {pid} at 2026-11-09 15:31:20 -----\nCmd line: {package}\n'
            'DALVIK THREADS (1):\n"main" prio=5 tid=1 Native\n'
            '  at android.view.ThreadedRenderer.nSyncAndDrawFrame(Native method)\n'
            f'----- end {pid} -----\n').encode()


def real_shell_executor(directory, payload):
    """Use ADB's literal argv join and a real shell with harmless local commands.

    ADB 35.0.2 client/commandline.cpp joins shell argv with spaces; its daemon
    passes that command to sh -c. No Android device is contacted. Synthetic
    executables reject wrong arguments before emitting fixture data.
    """
    directory=Path(directory);directory.mkdir()
    (directory/'stream.bin').write_bytes(payload)
    programs={
        'getprop':"""import sys
if sys.argv[1:] != ['ro.kernel.qemu']:
    sys.exit('unexpected synthetic getprop arguments')
print('1')
""",
        'dumpsys':"""import json, os, sys
from pathlib import Path
directory=Path(__file__).parent
(directory/'argv.json').write_text(json.dumps(sys.argv[1:]))
if sys.argv[1:] != ['dropbox', '--print', 'data_app_anr']:
    sys.exit('unexpected synthetic dumpsys arguments')
try:
    sys.stdout.buffer.write((directory/'stream.bin').read_bytes())
    sys.stdout.buffer.flush()
except BrokenPipeError:
    os._exit(0)
""",
    }
    for name,program in programs.items():
        path=directory/name
        path.write_text('#!'+sys.executable+'\n'+program);path.chmod(0o700)
    calls=[]
    def execute(args,**kwargs):
        assert args[:4]==['controlled-adb','-s','emulator-5554','shell']
        calls.append((args,kwargs))
        environment=dict(os.environ,PATH=str(directory)+os.pathsep+os.defpath)
        return subprocess.run(['/bin/sh','-c',' '.join(args[4:])],env=environment,**kwargs)
    return execute,calls,directory/'argv.json'


class AnrDiagnosticTest(unittest.TestCase):
    def test_complete_system_dialog_is_bound_to_original_xml_bytes(self):
        value=ANR.observed_dialog([attempt()])
        self.assertEqual(value['attempt'],7)
        self.assertEqual(value['xmlSha256'],ANR.digest(XML))
        self.assertEqual(value['xmlBytes'],len(XML))

    def test_title_without_owned_system_actions_does_not_enable_collection(self):
        for raw in (XML.replace(b'android:id/aerr_wait',b'other'),
                    XML.replace(b'package="android"',b'package="local.pocketchat.test"'),
                    XML.replace(b'enabled="true"',b'enabled="false"'),
                    XML.replace('元婴期院士'.encode(),b'Another app')):
            with self.subTest(raw=raw):self.assertIsNone(ANR.observed_dialog([attempt(raw)]))

    def test_truncated_modified_or_foreign_capture_is_rejected(self):
        for field,value in (('truncated',True),('bytes',1),('sha256','0'*64)):
            record=attempt();record['commands'][0]['stdout'][field]=value
            self.assertIsNone(ANR.observed_dialog([record]))
        record=attempt();record['commands'][0]['parts']=['shell','echo','not a capture']
        self.assertIsNone(ANR.observed_dialog([record]))

    def test_only_complete_test_process_art_blocks_are_retained(self):
        raw=b'Unrelated DropBox header\n'+stack(1,'other.package')+stack()+b'Logcat: foreign document payload\n'
        result=ANR.owned_stacks(raw)
        self.assertEqual(result,[(42,stack().rstrip(b'\n'))])
        self.assertNotIn(b'foreign',result[0][1]);self.assertNotIn(b'other.package',result[0][1])

    def test_partial_mixed_owner_and_wrong_end_stacks_are_rejected(self):
        for raw in (stack().replace(b'----- end 42 -----',b'----- end 43 -----'),
                    stack().replace(b'DALVIK THREADS',b'UNKNOWN FORMAT'),
                    stack().replace(b'"main"',b'"other"'),
                    stack().replace(b'Cmd line:',b'Cmd line: other\nCmd line:'),
                    stack().replace(b'  at ',stack(43)+b'  at ')):
            with self.subTest(raw=raw):self.assertEqual(ANR.owned_stacks(raw),[])
        with self.assertRaises(ValueError):ANR.owned_stacks(b'x'*(ANR.MAX_CAPTURE+1))

    def collect(self, directory, execute, **options):
        values=dict(adb='controlled-adb',serial='emulator-5554',source=SOURCE,nonce=NONCE,
                    directory=directory,observation=ANR.observed_dialog([attempt()]),environment=ENV,execute=execute)
        values.update(options)
        return ANR.collect(**values)

    def test_no_ci_or_real_device_runs_no_command(self):
        for values in ({'environment':{}},{'serial':'physical-phone'},{'source':'unknown'},{'nonce':'../x'},{'observation':None}):
            with tempfile.TemporaryDirectory() as tmp:
                execute=mock.Mock(side_effect=AssertionError('unexpected command'))
                result=self.collect(tmp,execute,**values)
                self.assertEqual(result['status'],'not-collected');execute.assert_not_called()
                self.assertEqual(list(Path(tmp).iterdir()),[])

    def test_confirmed_emulator_reads_once_and_preserves_only_owned_stacks(self):
        calls=[]
        def execute(args,**kwargs):
            calls.append((args,kwargs))
            if args[3:]==['shell','getprop','ro.kernel.qemu']:
                return subprocess.CompletedProcess(args,0,b'1\n',b'')
            self.assertEqual(args[3:],['shell','dumpsys dropbox --print data_app_anr | head -c 1048577'])
            return subprocess.CompletedProcess(args,0,stack(1,'other.package')+stack()+b'foreign log payload',b'')
        with tempfile.TemporaryDirectory() as tmp:
            result=self.collect(tmp,execute)
            self.assertEqual(result['status'],'owned-stacks-collected')
            self.assertEqual(len(result['stackFiles']),1)
            row=result['stackFiles'][0];raw=(Path(tmp)/row['file']).read_bytes()
            self.assertEqual(raw,stack().rstrip(b'\n'));self.assertEqual(row['sha256'],ANR.digest(raw))
            self.assertFalse(result['releaseAcceptance']);self.assertTrue(result['diagnosticOnly'])
            self.assertTrue(result['sourceInputsUnchanged'])
            self.assertEqual(set(result['sourceFiles']), {'tools/gecko/' + name for name in
                ('ui_anr_diagnostic.py', 'diagnostic_capture_privacy.py', 'caret_ime_guard.py')})
            for name, metadata in result['sourceFiles'].items():
                raw_source = (ROOT / name).read_bytes()
                self.assertEqual(metadata, dict(bytes=len(raw_source), sha256=ANR.digest(raw_source)))
            self.assertEqual(len(calls),2);self.assertEqual([x[1]['timeout'] for x in calls],[3,7])
            with self.assertRaises(ValueError):self.collect(tmp,execute)
            self.assertEqual(len(calls),2)

    def test_real_shell_preserves_dropbox_arguments_and_collects_owned_stack_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp)/'capture';directory.mkdir()
            execute,calls,argv=real_shell_executor(Path(tmp)/'commands',
                stack(1,'other.package')+stack()+b'foreign log payload')
            result=self.collect(directory,execute)
            self.assertEqual(result['status'],'owned-stacks-collected')
            self.assertEqual(json.loads(argv.read_text()),['dropbox','--print','data_app_anr'])
            self.assertEqual(len(calls),2)
            self.assertEqual([kwargs['timeout'] for _,kwargs in calls],[3,7])
            self.assertEqual([row['parts'] for row in result['commands']],
                [['shell','getprop','ro.kernel.qemu'],
                 ['shell','dumpsys dropbox --print data_app_anr | head -c 1048577']])
            self.assertEqual(len(result['stackFiles']),1)
            raw=(directory/result['stackFiles'][0]['file']).read_bytes()
            self.assertEqual(raw,stack().rstrip(b'\n'))
            self.assertTrue(result['sourceInputsUnchanged'])
            self.assertFalse(result['releaseAcceptance'])
            with self.assertRaises(ValueError):self.collect(directory,execute)
            self.assertEqual(len(calls),2)

    def test_original_nested_shell_loses_arguments_and_cannot_collect(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp)/'capture';directory.mkdir()
            execute,calls,argv=real_shell_executor(Path(tmp)/'commands',stack())
            def nested(args,**kwargs):
                if args[3:]!=['shell','getprop','ro.kernel.qemu']:
                    args=args[:4]+['sh','-c',args[4]]
                return execute(args,**kwargs)
            result=self.collect(directory,nested)
            self.assertEqual(json.loads(argv.read_text()),[])
            self.assertEqual(result['status'],'collection-failed')
            self.assertEqual(result['stackFiles'],[])
            self.assertGreater(result['commands'][-1]['stderrBytes'],0)
            self.assertEqual(len(calls),2)
            self.assertEqual([kwargs['timeout'] for _,kwargs in calls],[3,7])
            self.assertEqual(len(list(directory.iterdir())),1)

    def test_real_shell_head_cap_rejects_complete_stack_inside_oversized_stream(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp)/'capture';directory.mkdir()
            execute,calls,argv=real_shell_executor(Path(tmp)/'commands',
                stack()+b'x'*(ANR.MAX_CAPTURE+128))
            result=self.collect(directory,execute)
            self.assertEqual(json.loads(argv.read_text()),['dropbox','--print','data_app_anr'])
            self.assertEqual(result['commands'][-1]['stdoutBytes'],ANR.MAX_CAPTURE+1)
            self.assertEqual(result['commands'][-1]['stderrBytes'],0)
            self.assertTrue(result['streamTruncated'])
            self.assertEqual(result['status'],'collection-failed')
            self.assertEqual(result['stackFiles'],[])
            self.assertEqual(len(calls),2)
            self.assertEqual([kwargs['timeout'] for _,kwargs in calls],[3,7])
            self.assertEqual(len(list(directory.iterdir())),1)

    def test_unconfirmed_emulator_stops_before_reading_dropbox(self):
        execute=mock.Mock(return_value=subprocess.CompletedProcess([],0,b'0\n',b''))
        with tempfile.TemporaryDirectory() as tmp:
            result=self.collect(tmp,execute)
            self.assertEqual(result['status'],'collection-failed');self.assertEqual(execute.call_count,1)
            self.assertEqual(result['stackFiles'],[])

    def test_truncation_and_error_output_cannot_become_stack_evidence(self):
        for result in (subprocess.CompletedProcess([],0,b'x'*(ANR.MAX_CAPTURE+1),b''),
                       subprocess.CompletedProcess([],1,stack(),b''),
                       subprocess.CompletedProcess([],0,stack(),b'permission denied')):
            execute=mock.Mock(side_effect=[subprocess.CompletedProcess([],0,b'1\n',b''),result])
            with tempfile.TemporaryDirectory() as tmp:
                value=self.collect(tmp,execute)
                self.assertEqual(value['status'],'collection-failed');self.assertEqual(value['stackFiles'],[])
                self.assertEqual(len(list(Path(tmp).iterdir())),1)

    def test_timeout_keeps_partial_stream_hash_without_raw_foreign_text(self):
        error=subprocess.TimeoutExpired(['dumpsys'],7,output=b'foreign document secret',stderr=b'bounded transport failure')
        execute=mock.Mock(side_effect=[subprocess.CompletedProcess([],0,b'1\n',b''),error])
        with tempfile.TemporaryDirectory() as tmp:
            value=self.collect(tmp,execute);last=value['commands'][-1]
            self.assertEqual(value['status'],'collection-failed');self.assertTrue(last['timedOut'])
            self.assertEqual(last['stdoutSha256'],ANR.digest(error.stdout))
            self.assertNotIn('foreign document secret',json.dumps(value))

    def test_capture_failure_and_original_deadline_survive_secondary_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            capture=CAPTURE.UiVisualCapture(adb='unused',serial='emulator-5554',source=SOURCE,diagnostics=Path(tmp)/'capture.json')
            capture.records.append(attempt());capture.count=7
            original=subprocess.TimeoutExpired(['original uiautomator'],1.4)
            with mock.patch.object(capture,'command',side_effect=original) as command, \
                 mock.patch.object(CAPTURE._anr,'collect',side_effect=ValueError('secondary diagnostic failure')) as collect:
                with self.assertRaises(subprocess.TimeoutExpired) as caught:capture.attempt(123.5)
            self.assertIs(caught.exception,original)
            self.assertEqual(command.call_args.args[-1],123.5)
            self.assertEqual(command.call_count,1);self.assertEqual(collect.call_count,1)
            self.assertEqual(capture.report['anrDiagnosticCollectionError'],'ValueError')
            self.assertEqual(capture.records[-1]['status'],'failed')

    def test_other_capture_failures_never_collect_extra_device_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            capture=CAPTURE.UiVisualCapture(adb='unused',serial='emulator-5554',source=SOURCE,diagnostics=Path(tmp)/'capture.json')
            original=RuntimeError('original capture transport failed')
            with mock.patch.object(capture,'command',side_effect=original),mock.patch.object(CAPTURE._anr,'collect') as collect:
                with self.assertRaises(RuntimeError) as caught:capture.attempt(123.5)
            self.assertIs(caught.exception,original);collect.assert_not_called()


if __name__=='__main__':unittest.main()
