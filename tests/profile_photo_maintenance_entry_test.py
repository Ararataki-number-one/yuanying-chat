"""Maintenance declaration/dependency checks, plus the actual photo child only.

Current 39-group declarations and the exact historical 36-group source are
collected without executing them. The browser retirement replacement and three
additional download suites are explicit. No full-maintenance or Android acceptance
is claimed by this entry-point control.
"""
import ast
from contextlib import redirect_stderr
import hashlib
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT/'tools/browser/check_maintenance.py'
ORIGINAL_DECLARATIONS_SHA256 = '0e9eed7af11b8253986764cd96ca9f51454753a36edfbebce62e242324f84a18'
PHOTO_COMMAND = "        [sys.executable, 'tests/gecko_photo_tap_test.py'],\n"


# Only the historical declaration comparison uses this exact inverse. Actual
# maintenance and photo children always execute the current 39-group runner.
BROWSER_MAINTENANCE_CHANGE = {'previous': (13062, 'a9dd20e53a113278505ad96d0ecf658c4b0d6789a7bee7c93f92329409c565a5'),
 'current': (13919, 'f2bf6629a31138e9c9f72243e1f7089b0778eb3c246ef35e12993959a9982634'),
 'deltas': [('"""Run current-source browser and network regressions without historical source views.\n'
             '\n'
             'This is a focused maintenance check, not the full release or device acceptance.\n'
             'Retained browser behaviors keep their assertions and negative controls. Retired send-result\n'
             'features are explicitly replaced by the 2.1.8 browser retirement contract.\n'
             '"""\n'
             'import argparse\n'
             'from datetime import datetime, timezone\n',
             '"""Run current-source browser and network regressions without historical source views.\n'
             '\n'
             'This is a focused maintenance check, not the full release or device acceptance.\n'
             'Each child retains its original behavioral assertions and negative controls.\n'
             '"""\n'
             'import argparse\n'
             'from datetime import datetime, timezone\n'),
            ('    """Include sibling fixtures, imported runners and assets, not only argv files."""\n'
             "    raw = subprocess.check_output(['git', 'ls-files', '-z', '--cached', '--others',\n"
             "                                   '--exclude-standard', '--', *INPUT_PATHS], cwd=root)\n"
             "    return sorted({root / os.fsdecode(name) for name in raw.split(b'\\0')\n"
             '                   if name and (root / os.fsdecode(name)).is_file()})\n'
             '\n'
             '\n'
             'def main():\n',
             '    """Include sibling fixtures, imported runners and assets, not only argv files."""\n'
             "    raw = subprocess.check_output(['git', 'ls-files', '-z', '--cached', '--others',\n"
             "                                   '--exclude-standard', '--', *INPUT_PATHS], cwd=root)\n"
             "    return sorted({root / os.fsdecode(name) for name in raw.split(b'\\0') if name})\n"
             '\n'
             '\n'
             'def main():\n'),
            ('\n'
             "    host('address-policy', 'tests/browser-address-host/run.py', java)\n"
             "    host('browser-permissions', 'tests/browser-permissions-host/run.py', java)\n"
             "    host('download-content', 'tests/download-content-host/run.py', java)\n"
             "    host('gecko-download-navigation', 'tests/gecko-download-navigation-host/run.py', java)\n"
             "    host('browser-blob', 'tests/browser-blob-host/run.py', [*java, '--json-jar', jar])\n"
             "    host('native-attachment-chooser', 'tests/native-attachment-chooser-host/run.py', [*java, "
             "'--json-jar', jar])\n"
             '    for name, script in [\n'
             "        ('session-navigation', 'tests/gecko-navigation-host/session_navigation.py'),\n",
             '\n'
             "    host('address-policy', 'tests/browser-address-host/run.py', java)\n"
             "    host('browser-permissions', 'tests/browser-permissions-host/run.py', java)\n"
             "    host('native-attachment-chooser', 'tests/native-attachment-chooser-host/run.py', [*java, "
             "'--json-jar', jar])\n"
             '    for name, script in [\n'
             "        ('session-navigation', 'tests/gecko-navigation-host/session_navigation.py'),\n"),
            ("        ('ip-transport', 'tests/gecko-ip-transport-host/run.py'),\n"
             "        ('resource-recovery', 'tests/resource-recovery-host/run.py'),\n"
             "        ('page-lifecycle', 'tests/browser-navigation-lifecycle-host/run.py'),\n"
             '        # Delivery receipt persistence retired with send-result detection.\n'
             '        # page-lifecycle checks pending migration; this suite covers disabled\n'
             '        # old policies, service cleanup, process ownership and retry failures.\n'
             "        ('reply-policy-retirement', 'tests/background-reply-runtime-host/run.py'),\n"
             "        ('download-cancellation', 'tests/download-resume-host/run.py'),\n"
             "        ('download-persistence', 'tests/download-persistence-host/run.py'),\n"
             "        ('download-recovery', 'tests/download-recovery-host/run.py'),\n",
             "        ('ip-transport', 'tests/gecko-ip-transport-host/run.py'),\n"
             "        ('resource-recovery', 'tests/resource-recovery-host/run.py'),\n"
             "        ('page-lifecycle', 'tests/browser-navigation-lifecycle-host/run.py'),\n"
             "        ('reply-task-persistence', 'tests/reply-task-persistence-host/run.py'),\n"
             "        ('download-cancellation', 'tests/download-resume-host/run.py'),\n"
             "        ('download-persistence', 'tests/download-persistence-host/run.py'),\n"
             "        ('download-recovery', 'tests/download-recovery-host/run.py'),\n"),
            ("        [sys.executable, 'tests/profile_navigation_v3_test.py'],\n"
             "        [sys.executable, 'tests/gecko_photo_upload_contract_test.py'],\n"
             "        [sys.executable, 'tests/browser_workspace_device_configuration_test.py'],\n"
             "        [sys.executable, 'tests/profile_ui_device_preparation_test.py'],\n"
             "        [sys.executable, 'tests/profile_browser_header_v5_test.py'],\n"
             "        [sys.executable, 'tests/profile_browser_header_evidence_v5_test.py'],\n"
             "        [sys.executable, 'tests/profile_browser_observation_v2_test.py']], None))\n"
             "    jobs.append(('event-transport', [\n"
             "        [sys.executable, 'tests/gecko_event_transfer_test.py'],\n"
             "        [sys.executable, 'tests/profile_event_journal_discovery_test.py']], None))\n",
             "        [sys.executable, 'tests/profile_navigation_v3_test.py'],\n"
             "        [sys.executable, 'tests/gecko_photo_upload_contract_test.py'],\n"
             "        [sys.executable, 'tests/browser_workspace_device_configuration_test.py'],\n"
             "        [sys.executable, 'tests/profile_ui_device_preparation_test.py']], None))\n"
             "    jobs.append(('event-transport', [\n"
             "        [sys.executable, 'tests/gecko_event_transfer_test.py'],\n"
             "        [sys.executable, 'tests/profile_event_journal_discovery_test.py']], None))\n")]}

def browser_maintenance_previous(source):
    raw=source.encode()
    item=BROWSER_MAINTENANCE_CHANGE
    identity=(len(raw),hashlib.sha256(raw).hexdigest())
    if identity==item['previous']:
        return source
    assert identity==item['current'],'Unreviewed maintenance declaration change'
    restored=source
    for current,previous in item['deltas']:
        assert restored.count(current)==1
        restored=restored.replace(current,previous,1)
    raw=restored.encode()
    assert (len(raw),hashlib.sha256(raw).hexdigest())==item['previous']
    forward=restored
    for current,previous in item['deltas']:
        assert forward.count(previous)==1
        forward=forward.replace(previous,current,1)
    assert forward==source
    return restored


def original_declarations_digest(source):
    assert source.count(PHOTO_COMMAND)==1
    original=source.replace(PHOTO_COMMAND,'',1)
    main=next(n for n in ast.parse(original).body if isinstance(n,ast.FunctionDef) and n.name=='main')
    start=next(i for i,n in enumerate(main.body) if isinstance(n,ast.Expr) and isinstance(n.value,ast.Call)
               and isinstance(n.value.func,ast.Name) and n.value.func.id=='host')
    normalized=ast.dump(ast.Module(body=main.body[start:boundary(main)],type_ignores=[]),include_attributes=False)
    return hashlib.sha256(normalized.encode()).hexdigest()


def boundary(main):
    return next(i for i,node in enumerate(main.body) if isinstance(node,ast.Assign)
                and any(isinstance(t,ast.Name) and t.id=='hashes' for t in node.targets))


def declarations(raw, arguments):
    tree=ast.parse(raw)
    main=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main')
    main.body=main.body[:boundary(main)]+[ast.Return(ast.Tuple(
        elts=[ast.Name(id='jobs',ctx=ast.Load()),ast.Name(id='env',ctx=ast.Load())],ctx=ast.Load()))]
    tree.body=[n for n in tree.body if not isinstance(n,ast.If)]
    namespace=dict(__name__='maintenance_declarations',__file__=str(RUNNER))
    with patch.object(sys,'argv',[str(RUNNER),*arguments]):
        exec(compile(ast.fix_missing_locations(tree),str(RUNNER),'exec'),namespace)
        return namespace['main']()


class PhotoMaintenanceEntryTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.out=Path(self.temp.name)
        home=os.environ.get('JAVA_HOME_17_X64') or os.environ.get('JAVA_HOME')
        self.home=Path(home) if home else Path(shutil.which('java') or '').resolve().parents[1]
        self.desktop=Path(os.environ.get('PROFILE_JSON_JAR',ROOT/'work/profile-host/json.jar'))
        self.android=Path(os.environ.get('PROFILE_ANDROID_JSON_JAR',ROOT/'work/profile-host/android-json.jar'))
        self.arguments=['--java-home',str(self.home),'--json-jar',str(self.desktop),
                        '--android-json-jar',str(self.android),'--output',str(self.out)]
        self.raw=RUNNER.read_text()

    def test_original_36_groups_order_commands_and_300_second_budget_are_unchanged(self):
        previous=browser_maintenance_previous(self.raw)
        self.assertEqual(original_declarations_digest(previous),ORIGINAL_DECLARATIONS_SHA256)
        legacy,_=declarations(previous,self.arguments)
        groups,_=declarations(self.raw,self.arguments)
        self.assertEqual(len(legacy),36)
        self.assertEqual(len(groups),39)
        extra=('download-content','gecko-download-navigation','browser-blob')
        self.assertEqual([name for name,_,_ in groups][2:5],list(extra))
        java=['--java-home',str(self.home.resolve())]
        for name in extra:
            report=self.out/(name+'.json')
            arguments=java+(['--json-jar',str(self.desktop.resolve())] if name=='browser-blob' else [])
            expected=(name,[[sys.executable,'tests/'+name+'-host/run.py',*arguments,
                            '--output',str(report)]],report)
            self.assertEqual([group for group in groups if group[0]==name],[expected])
        retired=next(group for group in legacy if group[0]=='reply-task-persistence')
        replacement=next(group for group in groups if group[0]=='reply-policy-retirement')
        new_report=self.out/'reply-policy-retirement.json'
        expected_command=[part.replace('tests/reply-task-persistence-host/run.py',
                                       'tests/background-reply-runtime-host/run.py')
                          .replace(str(retired[2]),str(new_report)) for part in retired[1][0]]
        self.assertEqual(replacement,('reply-policy-retirement',[expected_command],new_report))
        readers=[[sys.executable,'tests/'+name] for name in (
            'profile_browser_header_v5_test.py','profile_browser_header_evidence_v5_test.py',
            'profile_browser_observation_v2_test.py')]
        projected=[]
        for name,commands,report in groups:
            if name in extra:
                continue
            if name=='reply-policy-retirement':
                projected.append(retired)
            elif name=='display-acceptance':
                self.assertEqual(commands[-3:],readers)
                projected.append((name,commands[:-3],report))
            else:
                projected.append((name,commands,report))
        self.assertEqual(projected,legacy)
        photo=next(commands for name,commands,_ in groups if name=='photo-upload-permission')
        self.assertIn([sys.executable,'tests/gecko_photo_tap_test.py'],photo)
        calls=[n for n in ast.walk(ast.parse(self.raw)) if isinstance(n,ast.Call)
               and isinstance(n.func,ast.Attribute) and isinstance(n.func.value,ast.Name)
               and n.func.value.id=='subprocess' and n.func.attr=='run']
        self.assertEqual(len(calls),1)
        self.assertEqual([k.value.value for k in calls[0].keywords if k.arg=='timeout'],[300])

    def test_exact_browser_runner_inverse_preserves_the_original_declaration_digest(self):
        previous=browser_maintenance_previous(self.raw)
        self.assertEqual(browser_maintenance_previous(previous),previous)
        self.assertEqual(original_declarations_digest(previous),ORIGINAL_DECLARATIONS_SHA256)
        self.assertNotEqual(original_declarations_digest(self.raw),ORIGINAL_DECLARATIONS_SHA256)
        for current,_ in BROWSER_MAINTENANCE_CHANGE['deltas']:
            for changed in (self.raw.replace(current,'',1),self.raw.replace(current,current*2,1),
                            self.raw.replace(current,'',1)+current):
                with self.assertRaises(AssertionError):browser_maintenance_previous(changed)
        for before,after in (('timeout=300','timeout=301'),
                             ('tests/gecko_photo_tap_test.py','tests/other_photo_tap_test.py')):
            changed=self.raw.replace(before,after,1)
            self.assertNotEqual(changed,self.raw)
            with self.assertRaises(AssertionError):browser_maintenance_previous(changed)

    def test_actual_photo_child_receives_and_executes_both_explicit_json_runtimes(self):
        groups,env=declarations(self.raw,self.arguments)
        self.assertEqual(env['PROFILE_JSON_JAR'],str(self.desktop.resolve()))
        self.assertEqual(env['PROFILE_ANDROID_JSON_JAR'],str(self.android.resolve()))
        command=next(command for name,commands,_ in groups if name=='photo-upload-permission'
                     for command in commands if 'tests/gecko_photo_tap_test.py' in command)
        result=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn('Ran 1 test',result.stderr)
        dependencies=next(n for n in ast.walk(ast.parse(self.raw)) if isinstance(n,ast.Assign)
                          and any(isinstance(t,ast.Name) and t.id=='dependencies' for t in n.targets))
        self.assertIn("Name(id='android_json'",ast.dump(dependencies))

    def test_missing_unknown_and_desktop_alias_android_dependency_fail_before_children(self):
        missing=self.arguments.copy();index=missing.index('--android-json-jar');del missing[index:index+2]
        for args in (missing,self.arguments[:index+1]+[str(self.out/'missing.jar')]+self.arguments[index+2:],
                     self.arguments[:index+1]+[str(self.desktop)]+self.arguments[index+2:]):
            with self.subTest(arguments=args),redirect_stderr(io.StringIO()),self.assertRaises(SystemExit) as stopped:
                declarations(self.raw,args)
            self.assertEqual(stopped.exception.code,2)
        changed=self.out/'changed.jar';changed.write_bytes(self.android.read_bytes()[:-1]+b'x')
        with redirect_stderr(io.StringIO()),self.assertRaises(SystemExit) as stopped:
            declarations(self.raw,self.arguments[:index+1]+[str(changed)]+self.arguments[index+2:])
        self.assertEqual(stopped.exception.code,2)

    def test_workspace_workflow_and_both_documented_commands_declare_android_json(self):
        workflow=(ROOT/'.github/workflows/browser-workspace-validation.yml').read_text()
        expected='work/browser-maintenance-dependencies/android-json.jar'
        self.assertIn('--android-json-jar '+expected,workflow)
        self.assertEqual(workflow.count('https://repo.maven.apache.org/maven2/com/vaadin/external/google/android-json/0.0.20131108.vaadin1/android-json-0.0.20131108.vaadin1.jar'),1)
        self.assertIn("echo 'dfb7bae2f404cfe0b72b4d23944698cb716b7665171812a0a4d0f5926c0fac79  "+expected+"' | sha256sum -c -",workflow)
        for name in ('MAINTENANCE-VALIDATION.md','MAINTENANCE-AUDIT.md'):
            text=(ROOT/'docs'/name).read_text();command=text.split('python3 tools/browser/check_maintenance.py',1)[1].split('```',1)[0]
            self.assertIn('--android-json-jar /path/to/android-json-0.0.20131108.vaadin1.jar',command)


if __name__=='__main__':unittest.main()
