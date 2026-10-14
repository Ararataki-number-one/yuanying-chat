"""Controlled IME service and phase ordering against explicit host doubles.

The complete checked-in service runs on a JVM with adversarial Android API
doubles. Coordinator processes/guards and release ZIP contents are synthetic.
No Android, APK signing, IME window, Gecko, or trusted input acceptance is claimed.
"""
import ast
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock
import xml.etree.ElementTree as ET
import zipfile


ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT/'tests/gecko/ControlledCaretInputMethodService.java'
COORDINATOR = ROOT/'tools/gecko/run_caret_editing_phase.py'
RUNNER = ROOT/'tests/gecko/run_gecko_caret_compat.py'
SIGNER = ROOT/'tools/sign-apk.py'
PINNED_JAVA = Path('/workspace/yuanying-chat/work/cloud-setup/jdk/usr/lib/jvm/java-17-openjdk-amd64/bin/java')
ANDROID = '{http://schemas.android.com/apk/res/android}'
COMPONENT = 'local.pocketchat.ControlledCaretInputMethodService'
RESOURCE = 'res/xml/caret_controlled_input_method.xml'
sys.path.insert(0,str(ROOT/'tools/gecko'))
import run_caret_editing_phase as phase
import caret_launcher_guard as launcher
from caret_ime_guard import COMPONENT as IME_COMPONENT, IDENTITY_FIELDS

# Reuse the existing exact-package fake command adapter without executing or
# changing its tests. This keeps the outer restoration control tied to its real
# guard implementation rather than a second local implementation.
LAUNCHER_SPEC = importlib.util.spec_from_file_location('controlled_ime_launcher_host_adapter',
    ROOT/'tests/gecko_caret_launcher_guard_test.py')
LAUNCHER_HOST = importlib.util.module_from_spec(LAUNCHER_SPEC)
LAUNCHER_SPEC.loader.exec_module(LAUNCHER_HOST)


JAVA_DOUBLES = {
    'android/util/DisplayMetrics.java': '''package android.util;
public class DisplayMetrics {public float density=1;}''',
    'android/content/res/Resources.java': '''package android.content.res;
public class Resources {
 public final android.util.DisplayMetrics metrics=new android.util.DisplayMetrics();
 public android.util.DisplayMetrics getDisplayMetrics(){return metrics;}
}''',
    'android/content/Context.java': '''package android.content;
public class Context {
 public final android.content.res.Resources resources=new android.content.res.Resources();
 public android.content.res.Resources getResources(){return resources;}
}''',
    'android/view/KeyEvent.java': '''package android.view;
public class KeyEvent {public final int action,code;public KeyEvent(int action,int code){this.action=action;this.code=code;}}''',
    'android/view/Gravity.java': 'package android.view;public final class Gravity {public static final int CENTER=17;}',
    'android/view/View.java': '''package android.view;
public class View {
 // Adversarial defaults require the actual service to disable every input flag.
 public boolean focusable=true,touchFocusable=true,clickable=true,longClickable=true;
 public int flagWrites;public ViewGroup.LayoutParams params;
 public void setFocusable(boolean value){focusable=value;flagWrites++;}
 public void setFocusableInTouchMode(boolean value){touchFocusable=value;flagWrites++;}
 public void setClickable(boolean value){clickable=value;flagWrites++;}
 public void setLongClickable(boolean value){longClickable=value;flagWrites++;}
 public void setLayoutParams(ViewGroup.LayoutParams value){params=value;}
}''',
    'android/view/ViewGroup.java': '''package android.view;
public class ViewGroup extends View {
 public static class LayoutParams {
  public static final int MATCH_PARENT=-1;public final int width,height;
  public LayoutParams(int width,int height){this.width=width;this.height=height;}
 }
}''',
    'android/widget/TextView.java': '''package android.widget;
public class TextView extends android.view.View {
 public final android.content.Context context;public CharSequence text;public int gravity;
 public TextView(android.content.Context context){this.context=context;}
 public void setText(CharSequence value){text=value;}public void setGravity(int value){gravity=value;}
}''',
    'android/view/inputmethod/EditorInfo.java': '''package android.view.inputmethod;
public class EditorInfo {public int initialSelStart=7,initialSelEnd=3,inputType=17;}''',
    'android/inputmethodservice/InputMethodService.java': '''package android.inputmethodservice;
import android.view.*;import android.view.inputmethod.EditorInfo;
public class InputMethodService extends android.content.Context {
 public int editorGetterCalls,editorWrites,defaultLifecycleCalls,defaultKeyCalls;
 public final SyntheticConnection editor=new SyntheticConnection();
 public class SyntheticConnection {
  public boolean finishComposingText(){editorWrites++;return true;}
  public boolean commitText(CharSequence text,int cursor){editorWrites++;return true;}
  public boolean setSelection(int start,int end){editorWrites++;return true;}
 }
 public SyntheticConnection getCurrentInputConnection(){editorGetterCalls++;return editor;}
 public EditorInfo getCurrentInputEditorInfo(){editorGetterCalls++;return new EditorInfo();}
 public View onCreateInputView(){return null;}
 public boolean onEvaluateInputViewShown(){return false;}
 public boolean onEvaluateFullscreenMode(){return true;}
 public void onStartInput(EditorInfo info,boolean restarting){defaultLifecycleCalls++;}
 public void onStartInputView(EditorInfo info,boolean restarting){defaultLifecycleCalls++;}
 public void onUpdateSelection(int a,int b,int c,int d,int e,int f){defaultLifecycleCalls++;}
 // These two implicit writers model the documented Android default lifecycle
 // paths. The production test service must override both without super calls.
 public void onFinishInput(){defaultLifecycleCalls++;getCurrentInputConnection().finishComposingText();}
 public void onFinishInputView(boolean finishing){defaultLifecycleCalls++;if(!finishing)getCurrentInputConnection().finishComposingText();}
 public boolean onKeyDown(int code,KeyEvent event){defaultKeyCalls++;return true;}
 public boolean onKeyUp(int code,KeyEvent event){defaultKeyCalls++;return true;}
 public boolean onKeyMultiple(int code,int count,KeyEvent event){defaultKeyCalls++;return true;}
 public boolean onKeyLongPress(int code,KeyEvent event){defaultKeyCalls++;return true;}
}''',
}


JAVA_MAIN = r'''
import local.pocketchat.ControlledCaretInputMethodService;
import android.inputmethodservice.InputMethodService;
import android.view.*;import android.view.inputmethod.EditorInfo;import android.widget.TextView;
public final class ControlledImeHostCheck {
 static void require(boolean value,String message){if(!value)throw new AssertionError(message);}
 static void passive(InputMethodService service){
  require(service.editorGetterCalls==0&&service.editorWrites==0,"Service queried or wrote the editor");
  require(service.defaultLifecycleCalls==0&&service.defaultKeyCalls==0,"Service delegated to default lifecycle/key behavior");
 }
 public static void main(String[] args){
  ControlledCaretInputMethodService service=new ControlledCaretInputMethodService();
  switch(args[0]){
   case "default-writer-control":{
    InputMethodService baseline=new InputMethodService();baseline.onFinishInput();baseline.onFinishInputView(false);
    require(baseline.editorGetterCalls==2&&baseline.editorWrites==2,"Host default lifecycle writer adapter was ineffective");
    baseline.onFinishInputView(true);require(baseline.editorWrites==2,"Finishing-view default control changed");
    service.onFinishInput();service.onFinishInputView(false);service.onFinishInputView(true);passive(service);break;
   }
   case "lifecycle-no-editor":{
    EditorInfo info=new EditorInfo();
    for(boolean restart:new boolean[]{false,true}){
     service.onStartInput(info,restart);service.onStartInputView(info,restart);
     service.onUpdateSelection(4,6,6,6,4,6);service.onUpdateSelection(6,6,5,5,-1,-1);
     service.onFinishInputView(false);service.onFinishInputView(true);service.onFinishInput();
    }
    require(info.initialSelStart==7&&info.initialSelEnd==3&&info.inputType==17,"Service rewrote EditorInfo");
    passive(service);break;
   }
   case "hardware-transparent":{
    for(int code:new int[]{0,4,7,21,67,112,9999,Integer.MIN_VALUE}){
     KeyEvent down=new KeyEvent(0,code),up=new KeyEvent(1,code);
     require(!service.onKeyDown(code,down)&&!service.onKeyUp(code,up),"Service consumed hardware DOWN/UP");
     require(!service.onKeyLongPress(code,down),"Service consumed hardware long press");
     for(int count:new int[]{0,1,3})require(!service.onKeyMultiple(code,count,down),"Service consumed hardware multiple event");
    }
    passive(service);break;
   }
   case "passive-panel":{
    for(float density:new float[]{.5f,1f,2.75f}){
     service.resources.metrics.density=density;View view=service.onCreateInputView();
     require(view instanceof TextView,"Passive IME panel is not a text view");TextView panel=(TextView)view;
     require(panel.context==service&&panel.text.toString().equals("Controlled SDK protocol fixture — passive IME panel"),"Panel identity/text differs");
     require(!panel.focusable&&!panel.touchFocusable&&!panel.clickable&&!panel.longClickable&&panel.flagWrites==4,"Panel can take focus or consume clicks");
     require(panel.gravity==Gravity.CENTER&&panel.params.width==ViewGroup.LayoutParams.MATCH_PARENT&&panel.params.height==Math.round(220*density),"Panel dimensions differ");
    }
    passive(service);break;
   }
   case "window-evaluation":{
    require(service.onEvaluateInputViewShown(),"Controlled input view cannot be shown with hardware keyboard");
    require(!service.onEvaluateFullscreenMode(),"Controlled IME can become fullscreen");passive(service);break;
   }
   default:throw new AssertionError("Unknown service host vector");
  }
  System.out.println("PASS "+args[0]+"; explicit host Java doubles only");
 }
}'''


class PassiveServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.java = os.environ.get('PROFILE_JAVA') or (str(PINNED_JAVA) if PINNED_JAVA.exists() else shutil.which('java'))
        if not cls.java:
            raise RuntimeError('Host JDK required for actual controlled IME service source')
        cls.temporary = tempfile.TemporaryDirectory(prefix='controlled-caret-ime-host-')
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.directory = Path(cls.temporary.name)
        files = dict(JAVA_DOUBLES,**{'local/pocketchat/ControlledCaretInputMethodService.java':SERVICE.read_text(),
                                   'ControlledImeHostCheck.java':JAVA_MAIN})
        paths = []
        for name,body in files.items():
            path=cls.directory/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(body);paths.append(str(path))
        compiled=subprocess.run([cls.java,'-m','jdk.compiler/com.sun.tools.javac.Main','-encoding','UTF-8',*paths],
                                text=True,capture_output=True,timeout=30)
        if compiled.returncode:
            raise AssertionError('Actual passive IME service did not compile:\n'+compiled.stdout+compiled.stderr)

    def vector(self,name):
        result=subprocess.run([self.java,'-cp',str(self.directory),'ControlledImeHostCheck',name],
                              text=True,capture_output=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertEqual(result.stdout.strip(),'PASS '+name+'; explicit host Java doubles only')

    def test_default_finish_lifecycle_writers_are_exercised_but_never_called_by_service(self):
        self.vector('default-writer-control')

    def test_start_selection_and_finish_callbacks_never_query_or_write_editor(self):
        self.vector('lifecycle-no-editor')

    def test_hardware_callbacks_return_false_without_default_dispatch(self):
        self.vector('hardware-transparent')

    def test_panel_cannot_take_focus_or_clicks_and_uses_density_scaled_height(self):
        self.vector('passive-panel')

    def test_input_window_is_shown_without_fullscreen_editor(self):
        self.vector('window-evaluation')


def actual_release_assertion(message):
    source=ast.parse(SIGNER.read_text())
    matches=[node for node in ast.walk(source) if isinstance(node,ast.Assert)
             and isinstance(node.msg,ast.Constant) and node.msg.value==message]
    if len(matches)!=1:
        raise AssertionError('One actual release exclusion required: '+message)
    module=ast.Module(body=[copy.deepcopy(matches[0])],type_ignores=[])
    return compile(ast.fix_missing_locations(module),str(SIGNER),'exec')


class IntegrationPackagingTests(unittest.TestCase):
    def test_exact_manifest_service_permission_process_action_and_metadata(self):
        manifest=ET.parse(ROOT/'tests/gecko/AndroidManifest.xml').getroot()
        services=[node for node in manifest.findall('./application/service') if node.get(ANDROID+'name')==COMPONENT]
        self.assertEqual(len(services),1)
        service=services[0]
        self.assertEqual(service.attrib,{ANDROID+'name':COMPONENT,ANDROID+'exported':'true',
            ANDROID+'permission':'android.permission.BIND_INPUT_METHOD',ANDROID+'process':':caret_controlled_ime'})
        self.assertEqual([node.attrib for node in service.findall('./intent-filter/action')],
                         [{ANDROID+'name':'android.view.InputMethod'}])
        self.assertEqual([node.attrib for node in service.findall('./meta-data')],
                         [{ANDROID+'name':'android.view.im',ANDROID+'resource':'@xml/caret_controlled_input_method'}])
        self.assertNotIn('ControlledCaretInputMethodService',(ROOT/'app/src/main/AndroidManifest.xml').read_text())

    def test_metadata_has_no_subtypes_default_or_settings_and_resource_is_integration_only(self):
        metadata=ET.parse(ROOT/'tests/gecko/res/xml/caret_controlled_input_method.xml').getroot()
        self.assertEqual(metadata.tag,'input-method')
        self.assertEqual(metadata.attrib,{ANDROID+'supportsSwitchingToNextInputMethod':'false'})
        self.assertEqual(list(metadata),[])
        settings=(ROOT/'app/build.gradle').read_text()
        source_sets=re.search(r'\bsourceSets\s*\{(.*?)\n\s*\}',settings,re.S).group(1)
        integration=re.search(r'\bintegration\s*\{([^}]*)\}',source_sets).group(1)
        self.assertIn("java.srcDirs = ['../tests/gecko']",integration)
        self.assertIn("res.srcDirs = ['../tests/gecko/res']",integration)
        self.assertIn("manifest.srcFile('../tests/gecko/AndroidManifest.xml')",integration)
        self.assertEqual(settings.count('../tests/gecko/res'),1)
        self.assertNotIn('../tests/gecko',source_sets.replace('integration {'+integration+'}',''))
        self.assertFalse((ROOT/'app/src/main/res/xml/caret_controlled_input_method.xml').exists())
        self.assertFalse((ROOT/'app/src/main/java/local/pocketchat/ControlledCaretInputMethodService.java').exists())

    def test_actual_release_resource_assertion_rejects_synthetic_ime_metadata_zip_entry(self):
        predicate=actual_release_assertion('Controlled caret IME metadata must never appear in production APK')
        for present in (False,True):
            with tempfile.TemporaryDirectory(prefix='controlled-ime-release-zip-') as name:
                path=Path(name)/'synthetic-contents.zip'
                with zipfile.ZipFile(path,'w') as archive:
                    archive.writestr('synthetic.txt','Host ZIP only; no APK or signing claim')
                    if present:archive.writestr(RESOURCE,'Synthetic metadata exclusion control')
                with zipfile.ZipFile(path) as archive,self.subTest(present=present):
                    if present:
                        with self.assertRaises(AssertionError):exec(predicate,{'archive':archive})
                    else:exec(predicate,{'archive':archive})

    def test_actual_release_dex_assertion_rejects_service_and_nested_class_definitions(self):
        predicate=actual_release_assertion('Caret fixture class present in production DEX.')
        exec(predicate,{'definitions':{'Llocal/pocketchat/ProductionSyntheticControl;'}})
        for definition in ('Llocal/pocketchat/ControlledCaretInputMethodService;',
                           'Llocal/pocketchat/ControlledCaretInputMethodService$SyntheticNested;'):
            with self.subTest(definition=definition),self.assertRaises(AssertionError):
                exec(predicate,{'definitions':{'Llocal/pocketchat/ProductionSyntheticControl;',definition}})

    def test_actual_release_manifest_assertion_rejects_service_or_metadata_reference(self):
        predicate=actual_release_assertion('Test component present in release.')
        exec(predicate,{'manifest':'Synthetic production manifest control; no compiled APK'})
        for value in ('ControlledCaretInputMethodService','caret_controlled_input_method'):
            with self.subTest(value=value),self.assertRaises(AssertionError):
                exec(predicate,{'manifest':'Synthetic manifest containing '+value})


def coordinator_args():
    root=Path('/synthetic/controlled IME project');out=root/'work/evidence'
    return SimpleNamespace(root=root,out=out,adb='/synthetic/bin/adb',serial='emulator-5554',
        build_receipt=out/'build.json',sdk_receipt=out/'sdk.json',sdk_aar=out/'modified.aar',
        official_sdk_aar=out/'official.aar',integration_apk=out/'integration.apk',release_apk=out/'release.apk')


class FakeControlledGuard:
    """Ordering adapter only; it deliberately does not model Android IME state."""
    def __init__(self,events):
        self.events=events;self.active=False;self.invocations=0

    def run(self,workload):
        self.invocations+=1;self.events.append('IME.prepare');self.active=True
        try:return workload()
        finally:self.active=False;self.events.append('IME.restore')


def actual_runner_guard_call():
    tree=ast.parse(RUNNER.read_text())
    main=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='main')
    matches=[node for node in ast.walk(main) if isinstance(node,ast.Expr) and isinstance(node.value,ast.Call)
             and ast.unparse(node.value.func)=='ime_guard.run']
    if len(matches)!=1 or ast.unparse(matches[0].value)!='ime_guard.run(run_compatibility)':
        raise AssertionError('Actual caret runner must enclose its once-only compatibility workload')
    return compile(ast.fix_missing_locations(ast.Module(body=[copy.deepcopy(matches[0])],type_ignores=[])),str(RUNNER),'exec')


class CoordinatorOrderingTests(unittest.TestCase):
    def expected_commands(self,args):
        return LAUNCHER_HOST.EditingCoordinatorTest().expected_commands(args)

    def harness(self):
        events=[];fake=LAUNCHER_HOST.FakeAdb(state=2);record={}
        def adb(*parts):
            result=fake(*parts)
            if parts[:2]==('shell','pm') and len(fake.pm_changes)>=2 and parts[2] in LAUNCHER_HOST.STATE:
                events.append('launcher.restore')
            return result
        outer=launcher.LauncherGuard(adb=adb,identity=LAUNCHER_HOST.identity(),record=record,nonce=LAUNCHER_HOST.NONCE)
        return events,fake,record,outer,FakeControlledGuard(events)

    def run_process(self,args,events,fake,controlled,outcomes):
        pending=iter(outcomes);commands=self.expected_commands(args)
        def process(command,*,cwd,check):
            index=commands.index(command)
            self.assertEqual(cwd,args.root);self.assertIs(check,False);self.assertEqual(fake.state,3)
            self.assertFalse(controlled.active)
            def workload():
                self.assertEqual(controlled.active,index==1)
                events.append('original.stock' if index==0 else 'caret.controlled')
                result=next(pending)
                if isinstance(result,BaseException):raise result
                return result
            if index==0:return SimpleNamespace(returncode=workload())
            # Execute the actual runner guard invocation with a finite process
            # body adapter. Source controls separately pin the unchanged full
            # callback and prove placement after the actual package reset.
            events.append('caret.package-reset');result=[]
            def run_compatibility():
                value=workload();result.append(value);return value
            exec(actual_runner_guard_call(),dict(ime_guard=controlled,run_compatibility=run_compatibility))
            return SimpleNamespace(returncode=result[0])
        return process

    def verifier(self,events,controlled):
        def verify():
            self.assertFalse(controlled.active,'Receipt must be checked after runner restoration')
            events.append('IME.receipt-verified')
        return verify

    def test_stock_original_once_then_only_new_caret_guarded_and_restored_before_home(self):
        args=coordinator_args();events,fake,record,outer,controlled=self.harness()
        process=self.run_process(args,events,fake,controlled,[0,0])
        with mock.patch.object(phase.subprocess,'run',side_effect=process) as invoked:
            self.assertEqual(outer.run(lambda:phase.run_workloads(args,record,self.verifier(events,controlled))),0)
        events.append('later.HOME')
        self.assertEqual(events,['original.stock','caret.package-reset','IME.prepare','caret.controlled','IME.restore',
                                 'IME.receipt-verified','launcher.restore','later.HOME'])
        self.assertEqual(invoked.call_args_list,[mock.call(command,cwd=args.root,check=False) for command in self.expected_commands(args)])
        self.assertEqual(controlled.invocations,1);self.assertFalse(controlled.active)
        self.assertEqual(fake.state,2);self.assertTrue(record['restorationVerified'])
        self.assertEqual([row['invocationCount'] for row in record['workloads']],[1,1])
        # Default None is only the old host adapter API; it still runs both exact
        # commands once without inventing a controlled IME preparation.
        with mock.patch.object(phase.subprocess,'run',return_value=SimpleNamespace(returncode=0)) as unguarded:
            self.assertEqual(phase.run_workloads(args,{}),0)
        self.assertEqual(unguarded.call_args_list,[mock.call(command,cwd=args.root,check=False) for command in self.expected_commands(args)])

    def test_ordinary_original_failure_still_runs_new_caret_once_under_guard(self):
        for first in (1,7):
            args=coordinator_args();events,fake,record,outer,controlled=self.harness()
            with self.subTest(first=first),mock.patch.object(phase.subprocess,'run',
                    side_effect=self.run_process(args,events,fake,controlled,[first,0])) as invoked:
                self.assertEqual(outer.run(lambda:phase.run_workloads(args,record,self.verifier(events,controlled))),1)
            self.assertEqual(events,['original.stock','caret.package-reset','IME.prepare','caret.controlled','IME.restore',
                                     'IME.receipt-verified','launcher.restore'])
            self.assertEqual(invoked.call_count,2);self.assertEqual(controlled.invocations,1)
            self.assertEqual([row['exitCode'] for row in record['workloads']],[first,0])
            self.assertTrue(record['restorationVerified']);self.assertEqual(fake.state,2)

    def test_fatal_original_exception_or_termination_never_prepares_caret_ime(self):
        for outcome in (-15,RuntimeError('Synthetic original failed'),KeyboardInterrupt('Synthetic original interrupted')):
            args=coordinator_args();events,fake,record,outer,controlled=self.harness()
            expected=type(outcome) if isinstance(outcome,BaseException) else ValueError
            with self.subTest(outcome=outcome),mock.patch.object(phase.subprocess,'run',
                    side_effect=self.run_process(args,events,fake,controlled,[outcome])) as invoked:
                with self.assertRaises(expected) as caught:
                    outer.run(lambda:phase.run_workloads(args,record,self.verifier(events,controlled)))
            if isinstance(outcome,BaseException):self.assertIs(caught.exception,outcome)
            self.assertEqual(events,['original.stock','launcher.restore'])
            self.assertEqual(invoked.call_count,1);self.assertEqual(controlled.invocations,0)
            self.assertTrue(record['restorationVerified']);self.assertEqual(fake.state,2)

    def test_fatal_new_caret_exception_restores_ime_then_launcher_and_aborts_later_home(self):
        for outcome in (-9,RuntimeError('Synthetic caret failed'),KeyboardInterrupt('Synthetic caret interrupted')):
            args=coordinator_args();events,fake,record,outer,controlled=self.harness()
            expected=type(outcome) if isinstance(outcome,BaseException) else ValueError
            with self.subTest(outcome=outcome),mock.patch.object(phase.subprocess,'run',
                    side_effect=self.run_process(args,events,fake,controlled,[0,outcome])) as invoked:
                with self.assertRaises(expected) as caught:
                    outer.run(lambda:phase.run_workloads(args,record,self.verifier(events,controlled)))
                    events.append('later.HOME')
            if isinstance(outcome,BaseException):self.assertIs(caught.exception,outcome)
            self.assertEqual(events,['original.stock','caret.package-reset','IME.prepare','caret.controlled','IME.restore','launcher.restore'])
            self.assertEqual(invoked.call_count,2);self.assertEqual(controlled.invocations,1)
            self.assertFalse(controlled.active);self.assertTrue(record['restorationVerified']);self.assertEqual(fake.state,2)
        # A process rc0 cannot authorize later HOME suites without the new
        # runner's actual restoration proof. Execute the real verifier refusal
        # inside the real outer launcher guard after the inner guard has ended.
        args=coordinator_args();events,fake,record,outer,controlled=self.harness()
        with tempfile.TemporaryDirectory(prefix='controlled-ime-missing-receipt-') as directory:
            def verify_missing():
                self.assertFalse(controlled.active);events.append('IME.receipt-refused')
                phase.verify_caret_ime_environment(Path(directory)/'missing.json',{})
            with mock.patch.object(phase.subprocess,'run',
                    side_effect=self.run_process(args,events,fake,controlled,[0,0])) as invoked:
                with self.assertRaises(ValueError):
                    outer.run(lambda:phase.run_workloads(args,record,verify_missing))
                    events.append('later.HOME')
        self.assertEqual(events,['original.stock','caret.package-reset','IME.prepare','caret.controlled',
                                 'IME.restore','IME.receipt-refused','launcher.restore'])
        self.assertEqual(invoked.call_count,2);self.assertTrue(record['restorationVerified']);self.assertEqual(fake.state,2)


class CoordinatorCliSourceTests(unittest.TestCase):
    def main_tree(self):
        return next(node for node in ast.parse(COORDINATOR.read_text()).body
                    if isinstance(node,ast.FunctionDef) and node.name=='main')

    def test_actual_cli_requires_runner_receipt_and_runner_guard_starts_after_package_reset(self):
        tree=self.main_tree()
        wrappers=[node for node in ast.walk(tree) if isinstance(node,ast.Call)
                  and isinstance(node.func,ast.Attribute) and ast.unparse(node.func)=='guard.run']
        self.assertEqual(len(wrappers),1)
        self.assertEqual(ast.unparse(wrappers[0].args[0]),'lambda: run_workloads(args, record, verify_ime_environment)')
        verifier=next(node for node in ast.walk(tree) if isinstance(node,ast.FunctionDef) and node.name=='verify_ime_environment')
        self.assertIn('verify_caret_ime_environment(ime_path, identity)',ast.unparse(verifier))
        self.assertIn("record['imeEnvironmentReceiptSha256'] = digest(ime_path)",ast.unparse(verifier))
        self.assertIn("record['imeRestorationVerified'] = ime['restorationVerified']",ast.unparse(verifier))
        runner=next(node for node in ast.parse(RUNNER.read_text()).body if isinstance(node,ast.FunctionDef) and node.name=='main')
        constructors=[node for node in ast.walk(runner) if isinstance(node,ast.Call)
                      and isinstance(node.func,ast.Name) and node.func.id=='ControlledImeGuard']
        self.assertEqual(len(constructors),1)
        # PACKAGE is a name in the actual command, so check its first three args
        # and the final bound source identifier separately.
        clears=[node for node in ast.walk(runner) if isinstance(node,ast.Call) and isinstance(node.func,ast.Name)
                and node.func.id=='adb' and [getattr(arg,'value',None) for arg in node.args[:3]]==['shell','pm','clear']]
        self.assertEqual(len(clears),1);self.assertEqual(ast.unparse(clears[0].args[3]),'PACKAGE')
        callback=next(node for node in ast.walk(runner) if isinstance(node,ast.FunctionDef) and node.name=='run_compatibility')
        self.assertLess(clears[0].lineno,constructors[0].lineno)
        self.assertLess(constructors[0].lineno,callback.lineno)
        self.assertFalse(any(isinstance(node,ast.Call) and ast.unparse(node.func)=='adb'
                             and [getattr(arg,'value',None) for arg in node.args[:3]]==['shell','pm','clear']
                             for node in ast.walk(callback)))
        actual_runner_guard_call()

    def test_original_callback_body_is_unchanged_except_explicit_success_return_zero(self):
        # Pinned from committed source 1aaa83ff2b208babbcf8543fbbcf554a667f8dc3.
        # Canonical AST ignores indentation/comments and Python-version-only
        # type_params fields; every original operation/vector/deadline remains.
        runner=next(node for node in ast.parse(RUNNER.read_text()).body if isinstance(node,ast.FunctionDef) and node.name=='main')
        callback=next(node for node in ast.walk(runner) if isinstance(node,ast.FunctionDef) and node.name=='run_compatibility')
        body=[node for node in callback.body if not isinstance(node,ast.Nonlocal)]
        def canonical(node):
            if isinstance(node,ast.AST):return [type(node).__name__,[(key,canonical(value)) for key,value in ast.iter_fields(node) if key!='type_params']]
            if isinstance(node,list):return [canonical(value) for value in node]
            return node
        encoded=json.dumps(canonical(ast.Module(body=body,type_ignores=[])),ensure_ascii=False,separators=(',',':')).encode()
        self.assertEqual(hashlib.sha256(encoded).hexdigest(),'1a2b9ce8930704406d7ac9c1046c357f64852eead279d594554bdb3fad2da93e')

    def test_actual_finally_writes_both_failed_ledgers_atomically_and_links_exact_ime_bytes(self):
        tree=self.main_tree();cleanup=next(node.finalbody for node in tree.body if isinstance(node,ast.Try))
        code=compile(ast.fix_missing_locations(ast.Module(body=copy.deepcopy(cleanup),type_ignores=[])),str(COORDINATOR),'exec')
        runner=next(node for node in ast.parse(RUNNER.read_text()).body if isinstance(node,ast.FunctionDef) and node.name=='main')
        runner_cleanup=next(node.finalbody for node in runner.body if isinstance(node,ast.Try))
        runner_code=compile(ast.fix_missing_locations(ast.Module(body=copy.deepcopy(runner_cleanup),type_ignores=[])),str(RUNNER),'exec')
        for owner in (tree,runner):
            interrupted=next(node for node in ast.walk(owner) if isinstance(node,ast.FunctionDef) and node.name=='interrupted')
            interrupt_code=compile(ast.fix_missing_locations(ast.Module(body=[copy.deepcopy(interrupted)],type_ignores=[])),
                                   str(COORDINATOR if owner is tree else RUNNER),'exec')
            namespace={};exec(interrupt_code,namespace)
            for signum in (15,2):
                with self.assertRaises(KeyboardInterrupt):namespace['interrupted'](signum,None)
        with tempfile.TemporaryDirectory(prefix='controlled-ime-finally-host-') as directory:
            out=Path(directory);caret_out=out/'caret-compat';caret_out.mkdir()
            record=dict(status='failed',applicationAcceptance=False,physicalPhoneAcceptance=False)
            ime_record=dict(status='failed',error='Synthetic cleanup diagnostic 失败🙂',applicationAcceptance=False,
                            physicalPhoneAcceptance=False,scope='Host-only synthetic receipt; no device claim')
            saved_signals={15:object(),2:object()};signal_adapter=SimpleNamespace(signal=mock.Mock())
            exec(runner_code,dict(out=caret_out,ime_record=ime_record,servers=[],signal_handlers=saved_signals,
                                 signal=signal_adapter,json=json))
            self.assertEqual(signal_adapter.signal.call_args_list,[mock.call(key,value) for key,value in saved_signals.items()])
            ime_path=caret_out/'caret-ime-environment.json';ime_bytes=ime_path.read_bytes()
            self.assertEqual(json.loads(ime_bytes),ime_record)
            self.assertIn('失败🙂',ime_bytes.decode())
            # Execute the actual byte-linking verifier closure's assignments
            # using a transport-only receipt verifier adapter.
            verifier=next(node for node in ast.walk(tree) if isinstance(node,ast.FunctionDef) and node.name=='verify_ime_environment')
            link_code=compile(ast.fix_missing_locations(ast.Module(body=copy.deepcopy(verifier.body),type_ignores=[])),str(COORDINATOR),'exec')
            signal_adapter.signal.reset_mock()
            namespace=dict(args=SimpleNamespace(out=out),record=record,handlers=saved_signals,signal=signal_adapter,json=json,
                           digest=phase.digest,ime_path=ime_path,identity={},
                           verify_caret_ime_environment=lambda path,identity:dict(restorationVerified=False))
            exec(link_code,namespace);exec(code,namespace)
            self.assertEqual(signal_adapter.signal.call_args_list,[mock.call(key,value) for key,value in saved_signals.items()])
            outer=json.loads((out/'editing-phase-environment.json').read_bytes())
            self.assertEqual(outer['imeEnvironmentReceipt'],'caret-compat/caret-ime-environment.json')
            self.assertEqual(outer['imeEnvironmentReceiptSha256'],hashlib.sha256(ime_bytes).hexdigest())
            self.assertFalse(outer['applicationAcceptance']);self.assertFalse(outer['physicalPhoneAcceptance'])
            self.assertEqual(sorted(path.name for path in out.iterdir()),['caret-compat','editing-phase-environment.json'])
            self.assertEqual(sorted(path.name for path in caret_out.iterdir()),['caret-ime-environment.json'])


class RestorationReceiptTests(unittest.TestCase):
    def test_actual_verifier_accepts_volatile_dump_change_but_rejects_semantic_and_bound_proof_drift(self):
        identity=dict(LAUNCHER_HOST.identity(),integrationApkSha256='c'*64,sdkReceiptSha256='d'*64)
        stock='synthetic.stock/synthetic.stock.Service'
        initial=dict(settings=dict(default_input_method=stock,enabled_input_methods=stock,
                                   selected_input_method_subtype='null',input_methods_subtype_history='null'),
            selectedComponent=stock,enabledComponents=[stock],actualEnabledComponents=[stock],
            registeredComponents=[stock,IME_COMPONENT],actualSelectedComponent=stock,
            allImeListRaw='Synthetic registered IMEs\n',enabledImeListRaw='Synthetic enabled IME\n',
            inputMethodDumpRaw='Synthetic runtime window/token before')
        restored=copy.deepcopy(initial);restored['inputMethodDumpRaw']='Synthetic different runtime window/token after'
        during=copy.deepcopy(initial);during.update(selectedComponent=IME_COMPONENT,actualSelectedComponent=IME_COMPONENT,
            enabledComponents=[stock,IME_COMPONENT],actualEnabledComponents=[stock,IME_COMPONENT])
        during['settings'].update(default_input_method=IME_COMPONENT,enabled_input_methods=stock+':'+IME_COMPONENT)
        valid=dict(schema=1,status='failed',identity=identity,runNonce=LAUNCHER_HOST.NONCE,serial='emulator-5554',user=0,
            exactFixtureComponent=IME_COMPONENT,initial=initial,during=during,restored=restored,
            restorationVerified=True,mutationAttempted=True,workloadInvocationCount=1,failureStage='workload',
            prepareStartedAtMonotonicNanos=1,preparedAtMonotonicNanos=2,workloadStartedAtMonotonicNanos=3,
            workloadCompletedAtMonotonicNanos=4,restoreStartedAtMonotonicNanos=5,restoredAtMonotonicNanos=6,
            applicationAcceptance=False,physicalPhoneAcceptance=False,vendorKeyboardUiAcceptance=False,
            scope='Synthetic host receipt verifier control only')
        with tempfile.TemporaryDirectory(prefix='controlled-ime-receipt-host-') as directory:
            path=Path(directory)/'synthetic-caret-ime-environment.json'
            def write(value):path.write_text(json.dumps(value,ensure_ascii=False))
            write(valid);accepted=phase.verify_caret_ime_environment(path,identity)
            self.assertEqual(accepted,valid)
            self.assertFalse(accepted['applicationAcceptance']);self.assertFalse(accepted['physicalPhoneAcceptance'])
            invalid=[]
            for key in ('settings','selectedComponent','enabledComponents','actualEnabledComponents',
                        'registeredComponents','actualSelectedComponent'):
                changed=copy.deepcopy(valid);changed['restored'][key]='Foreign synthetic restored state';invalid.append(changed)
            for key in IDENTITY_FIELDS:
                changed=copy.deepcopy(valid);changed['identity'][key]='foreign-owner';invalid.append(changed)
            for key,value in [('schema',True),('user',True),('user',10),('serial','real-phone'),
                              ('exactFixtureComponent','foreign/service'),('restorationVerified',False),
                              ('mutationAttempted',False),('workloadInvocationCount',True),('workloadInvocationCount',2),
                              ('fatal',True),('restoreError','Synthetic restore failure'),('initial',{}),('during',{}),
                              ('restored',{}),('failureStage','prepare'),('failureStage','workload-exit'),
                              ('errorType','KeyboardInterrupt'),('errorType','SystemExit'),
                              ('preparedAtMonotonicNanos',0),('preparedAtMonotonicNanos',True),
                              ('preparedAtMonotonicNanos',99),('restoredAtMonotonicNanos',-1)]:
                changed=copy.deepcopy(valid);changed[key]=value;invalid.append(changed)
            for index,changed in enumerate(invalid):
                write(changed)
                with self.subTest(invalid=index),self.assertRaises((ValueError,AssertionError)):
                    phase.verify_caret_ime_environment(path,identity)
            path.unlink()
            with self.assertRaises((ValueError,AssertionError)):
                phase.verify_caret_ime_environment(path,identity)


if __name__=='__main__':
    unittest.main()
