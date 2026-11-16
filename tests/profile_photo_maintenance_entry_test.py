"""Maintenance declaration/dependency checks, plus the actual photo child only.

The original 36 maintenance groups are collected without executing them. No
full-maintenance or Android acceptance is claimed by this entry-point control.
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
        self.assertEqual(self.raw.count(PHOTO_COMMAND),1)
        original=self.raw.replace(PHOTO_COMMAND,'',1)
        main=next(n for n in ast.parse(original).body if isinstance(n,ast.FunctionDef) and n.name=='main')
        start=next(i for i,n in enumerate(main.body) if isinstance(n,ast.Expr) and isinstance(n.value,ast.Call)
                   and isinstance(n.value.func,ast.Name) and n.value.func.id=='host')
        normalized=ast.dump(ast.Module(body=main.body[start:boundary(main)],type_ignores=[]),include_attributes=False)
        self.assertEqual(hashlib.sha256(normalized.encode()).hexdigest(),ORIGINAL_DECLARATIONS_SHA256)
        groups,_=declarations(self.raw,self.arguments)
        self.assertEqual(len(groups),36)
        photo=next(commands for name,commands,_ in groups if name=='photo-upload-permission')
        self.assertIn([sys.executable,'tests/gecko_photo_tap_test.py'],photo)
        calls=[n for n in ast.walk(ast.parse(self.raw)) if isinstance(n,ast.Call)
               and isinstance(n.func,ast.Attribute) and isinstance(n.func.value,ast.Name)
               and n.func.value.id=='subprocess' and n.func.attr=='run']
        self.assertEqual(len(calls),1)
        self.assertEqual([k.value.value for k in calls[0].keywords if k.arg=='timeout'],[300])

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
