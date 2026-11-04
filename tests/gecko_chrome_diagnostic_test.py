"""Guard selected-source diagnostic reuse; no counterfeit Android success."""
import ast
import copy
import importlib.machinery
import importlib.util
import itertools
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
path=ROOT/'tests/gecko/run_chrome_collapse_diagnostic.py'
spec=importlib.util.spec_from_file_location('chrome_diagnostic',path)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
source=(ROOT/'tests/gecko/run_ui_visuals.py').read_text()
original=ast.parse(source)

def named(tree,name):
    return next(n for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name==name)
def calls(tree,name):
    return [n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id==name]
def normalized(node):return ast.dump(node,include_attributes=False)

class FocusedDiagnosticTest(unittest.TestCase):
    def test_unknown_scenario_rejected(self):
        with self.assertRaises(ValueError):module.selected_program(source,'retry')
    def test_cold_uses_the_exact_server_and_collapse_call(self):
        selected=module.selected_program(source,'cold')
        self.assertEqual(normalized(named(selected,'ReloadHttp')),normalized(named(original,'ReloadHttp')))
        self.assertEqual([normalized(n) for n in calls(selected,'run_chrome_collapse')],[normalized(n) for n in calls(original,'run_chrome_collapse')])
        self.assertEqual(len(calls(selected,'reload_check')),0)
    def test_reload_uses_all_exact_original_checks_and_taps(self):
        selected=module.selected_program(source,'after-reload')
        self.assertEqual([normalized(n) for n in calls(selected,'reload_check')],[normalized(n) for n in calls(original,'reload_check')])
        self.assertEqual(len(calls(selected,'reload_check')),8)
        self.assertEqual([normalized(n) for n in calls(selected,'reload_tap')],[normalized(n) for n in calls(original,'reload_tap')])
        self.assertEqual(len(calls(selected,'reload_tap')),3)
    def test_reload_functions_and_deadlines_unchanged(self):
        selected=module.selected_program(source,'after-reload')
        for name in ('chrome_event','focus','reload_check','reload_command','reload_tap','reload_ready'):
            self.assertEqual(normalized(named(selected,name)),normalized(named(original,name)))
    def test_both_programs_compile_without_execution(self):
        for scenario in ('cold','after-reload'):
            compile(module.selected_program(source,scenario),'selected-fixture','exec')
    def test_changed_source_shape_fails_closed(self):
        with self.assertRaises(ValueError):module.selected_program(source.replace('class ReloadHttp(', 'class OtherHttp('),'cold')
    def test_partial_reload_persisted_before_collapse(self):
        selected=module.selected_program(source,'after-reload')
        body=next(n for n in selected.body if isinstance(n,ast.Try)).body
        persist=next(i for i,n in enumerate(body) if 'ui-reload-confirmation.json' in ast.unparse(n))
        start=next(i for i,n in enumerate(body) if isinstance(n,ast.ImportFrom) and n.module=='run_chrome_collapse')
        self.assertLess(persist,start)
        self.assertEqual(len([n for n in body[:persist] if calls(n,'reload_check')]),8)
    def test_oracle_is_original_import_without_inlined_replacement(self):
        for scenario in ('cold','after-reload'):
            selected=module.selected_program(source,scenario)
            self.assertFalse(any(isinstance(n,ast.FunctionDef) and n.name=='run_chrome_collapse' for n in ast.walk(selected)))
            self.assertEqual(len([n for n in ast.walk(selected) if isinstance(n,ast.ImportFrom) and n.module=='run_chrome_collapse']),1)


class FocusedMainExecutionTest(unittest.TestCase):
    """Run the real main and selected statements with host-only external edges.

    No Android, browser, timing or privacy acceptance is inferred from these
    controlled fake ADB/server/build responses. The original eight reload
    assertions and three taps execute without replacing their function bodies.
    """
    def execute(self, scenario, diagnostic):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/'source';out=Path(directory)/'diagnostic'
            inputs=('tests/gecko/run_ui_visuals.py','tests/gecko/run_chrome_collapse.py',
                    'tests/gecko/run_chrome_collapse_diagnostic.py',
                    'tests/gecko/ChromeCollapseIntegration.java','tools/gecko/chrome_collapse_contract.py','app/build.gradle',
                    'tests/gecko/CompactChromeIntegrationActivity.java','tests/gecko/ReloadWindowCallbackObservation.java',
                    'tools/gecko/ui_test_device.py','tests/gecko/ui_settings_services_device11.py',
                    'tools/gecko/diagnostic_capture_privacy.py','tools/gecko/caret_ime_guard.py')
            for name in inputs:
                target=root/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target)
            integration=root/'work/gecko-integration';integration.mkdir(parents=True)
            (integration/'ui-current.apk').write_bytes(b'HOST-ONLY-FAKE-BUILD')
            commands=[];events=[];trace=[];servers=[];taps=[];collapse=[];captures=[]
            identity={'hostOnly':True,'apkSha256':'3'*64};state={};run=None;last_command=None;modal_count=0
            package='local.pocketchat.test';component=package+'/local.pocketchat.CompactChromeIntegrationActivity'
            def ready(marker,loads,documents,actual_path):
                actual='http://127.0.0.1:8765'+actual_path;virtual='https://chatgpt.com'+actual_path
                raw={'kind':'documentReady','url':actual}
                return dict(body='controlled reply',draft='unsent controlled browser draft',
                    cookie='session=synthetic-reload',sendCount=0,stops=0,loads=loads,documents=documents,
                    path='/c/reload-B',cachedResumeUrl='https://chatgpt.com/c/reload-A',
                    currentUrl='https://chatgpt.com/c/reload-B',nativeUrl='http://127.0.0.1:8765/c/reload-B',
                    document=marker,visibleDocument=True,nativeSession=1,modal=False,
                    requested='https://chatgpt.com/c/reload-B',draftArchived=True,
                    documentReadyEvidence=dict(acceptedByProduction=True,fixtureRun=run,registeredRun=run,
                        topLevel=True,contentScript=True,nativeSession=1,currentSession=1,rawMessage=raw,
                        senderUrl=actual,actualUrl=actual,visibleUrl=virtual,
                        normalizedMessage=dict(raw,url=virtual),documentMarker=marker))
            def document(marker,loads,documents,actual_path):
                value=ready(marker,loads,documents,actual_path)
                trace.extend([dict(kind='http',path=actual_path,documentMarker=marker),
                              dict(kind='socks',accepted=True,host='127.0.0.1',port=8765)])
                return value
            def event(command,name,value):events.append(dict(command=command,event=name,reload=copy.deepcopy(value)))
            def adb(parts):
                nonlocal state,run,last_command,modal_count
                commands.append(tuple(parts))
                if parts[:3]==['exec-out','screencap','-p']:return b'HOST-ONLY-PNG'
                if parts[:3]==['exec-out','content','read']:return json.dumps(identity).encode()
                if parts[:2]==['logcat','-c']:events.clear();return b''
                if parts[:2]==['logcat','-d']:
                    raw='\n'.join('I PocketCompactChrome: '+json.dumps(value) for value in events)+'\n'+diagnostic
                    captures.append(raw);return raw.encode()
                if parts[:2]==['shell','dumpsys']:return ('mResumedActivity: '+component).encode()
                if parts[:3]==['shell','am','start']:
                    action=parts[parts.index('compactAction')+1];last_command=parts[parts.index('compactCommand')+1]
                    if action=='reloadStart':
                        run=last_command;state=document('a'*32,0,1,'/c/reload-A');name='reloadReady'
                    elif action=='requestReload':
                        modal_count+=1;name='reloadModal';value=dict(centered=True,controls=[
                            dict(label=label,bounds=[0,0,100,100],x=x,y=10,enabled=True,clickable=True)
                            for label,x in [('取消',10),('重新加载',20)]])
                        event(last_command,name,value);return b''
                    elif action=='changeRoute':state['path']='/c/reload-C';name='routeChanged'
                    elif action=='restoreRoute':state['path']='/c/reload-B';name='routeRestored'
                    elif action=='reloadSnapshot':name='reloadSnapshot'
                    elif action=='idleReload':state=document('c'*32,2,3,'/c/reload-B');name='reloaded'
                    else:raise AssertionError(('Unexpected fixture action',action))
                    event(last_command,name,state);return b''
                if parts[:3]==['shell','input','tap']:
                    taps.append(tuple(parts[3:]))
                    if modal_count==3:
                        state=document('b'*32,1,2,'/c/reload-B');event(last_command,'reloaded',state)
                    return b''
                if parts[0]=='reverse' or parts[:2] in (['shell','am'],['shell','wm'],['shell','settings']):return b''
                raise AssertionError(('Unexpected fake ADB command',parts))
            def check_output(command,**kwargs):
                if command==['git','rev-parse','HEAD']:return '1'*40+'\n'
                if command==['git','rev-parse','HEAD^{tree}']:return '2'*40+'\n'
                if command[:2]==['git','status']:return ''
                self.assertEqual(command[:3],['fake-adb','-s','fake-serial'])
                return adb(command[3:])
            class Server:
                def __init__(self,*args):self.stopped=False;servers.append(self)
                def serve_forever(self):raise AssertionError('No real server thread may run')
                def shutdown(self):self.stopped=True
            class Loader:
                def create_module(self,spec):return None
                def exec_module(self,value):
                    value.Fixture=object;value.ThreadedSocks=Server;value.Socks=object;value.TRACE=trace
            original_spec=importlib.util.spec_from_file_location
            def selected_spec(name,path):
                return importlib.machinery.ModuleSpec(name,Loader()) if name=='reload_loopback' else original_spec(name,path)
            build=types.ModuleType('profile_invocation_contract')
            build.expected_build=lambda *args:identity
            build.verify_installed=lambda actual,expected:self.assertEqual(actual,expected)
            runner=types.ModuleType('run_chrome_collapse')
            def run_collapse(adb_text,adb_bytes,source,actual_trace,actual_out,focus):
                self.assertIs(actual_trace,trace);self.assertEqual(actual_out,integration)
                focus('local.pocketchat.CompactChromeIntegrationActivity');collapse.append(True)
                return {'hostOnly':True}
            runner.run=run_collapse
            contract=types.ModuleType('chrome_collapse_contract');contract.verify_auto_collapse=lambda *args:{'hostOnly':True}
            clock=types.SimpleNamespace(monotonic=lambda:1,monotonic_ns=itertools.count(100).__next__,
                sleep=lambda _:self.fail('Controlled successful events must not require a retry'))
            before_path=sys.path[:]
            try:
                with mock.patch.object(module,'ROOT',root),mock.patch.object(module,'time',clock),\
                     mock.patch.dict(module.os.environ,{'CI':'false'},clear=True),\
                     mock.patch.object(module.subprocess,'check_output',side_effect=check_output),\
                     mock.patch.object(module.importlib.util,'spec_from_file_location',side_effect=selected_spec),\
                     mock.patch.object(module.http.server,'ThreadingHTTPServer',Server),\
                     mock.patch.object(module.threading,'Thread',return_value=types.SimpleNamespace(start=lambda:None)),\
                     mock.patch.dict(sys.modules,{'profile_invocation_contract':build,'run_chrome_collapse':runner,'chrome_collapse_contract':contract}),\
                     mock.patch.object(sys,'argv',['focused','--adb','fake-adb','--serial','fake-serial','--scenario',scenario,'--out',str(out)]):
                    module.main()
            finally:sys.path[:]=before_path
            report=json.loads((out/'results.json').read_text())
            self.assertEqual(report['status'],'passed');self.assertTrue(report['sourceInputsUnchanged'])
            self.assertEqual(collapse,[True]);self.assertEqual(len(servers),2)
            self.assertTrue(all(server.stopped for server in servers))
            if scenario=='after-reload':
                self.assertEqual(len(report['completedReloadChecks']),8)
                self.assertTrue(all(value['pass'] for value in report['completedReloadChecks']))
                self.assertEqual(len(report['actualReloadTaps']),3);self.assertEqual(len(taps),3)
                self.assertEqual((out/'ui-reload-log.txt').read_bytes(),(integration/'ui-reload-log.txt').read_bytes())
                self.assertEqual((out/'ui-reload-log.txt').read_text(),diagnostic_expected(captures[-2]))
            self.assertEqual((out/'native-log.txt').read_text(),diagnostic_expected(captures[-1]))
            self.assertEqual(commands[-3:],[('shell','settings','put','system','font_scale','1'),
                                           ('shell','wm','size','reset'),('shell','wm','density','reset')])
    def test_real_main_cold_keeps_benign_diagnostic_text_exact(self):
        self.execute('cold','benign café diagnostic: keep punctuation / = unchanged')
    def test_real_main_reload_keeps_benign_text_and_runs_all_original_reload_assertions(self):
        self.execute('after-reload','benign café diagnostic: keep punctuation / = unchanged')
    def test_real_main_cold_redacts_plain_and_escaped_keys_before_native_write(self):
        self.execute('cold',controlled_key_diagnostic())
    def test_real_main_reload_redacts_selected_write_and_finally_native_write(self):
        self.execute('after-reload',controlled_key_diagnostic())


class FocusedDevicePreparationTest(unittest.TestCase):
    """Actual runner control flow with declared host-only device/API boundaries."""
    def execute(self, *, preparation_error=False, workload_error=False, restoration_error=False, sourcehash_error=False, partial_copy_error=False):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/'source';out=Path(directory)/'diagnostic';order=[];record_path=None
            inputs=('tests/gecko/run_ui_visuals.py','tests/gecko/run_chrome_collapse.py',
                'tests/gecko/run_chrome_collapse_diagnostic.py','tests/gecko/ChromeCollapseIntegration.java',
                'tools/gecko/chrome_collapse_contract.py','tests/gecko/CompactChromeIntegrationActivity.java',
                'tests/gecko/ReloadWindowCallbackObservation.java','tools/gecko/ui_test_device.py',
                'tests/gecko/ui_settings_services_device11.py','app/build.gradle')
            for name in inputs:
                target=root/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target)
            integration=root/'work/gecko-integration';integration.mkdir(parents=True)
            (integration/'ui-current.apk').write_bytes(b'HOST-ONLY-FAKE-BUILD')
            identity={'hostOnly':True,'apkSha256':'3'*64};lease=object()
            wellbeing=types.ModuleType('ui_test_device');settings=types.ModuleType('ui_settings_services_device11')
            def prepare_wellbeing(adb,**kwargs):
                self.assertEqual(kwargs,dict(serial='fake-serial',environment=module.os.environ))
                order.append('wellbeing');return {'status':'host-only-control','previousFailureCauseProven':False}
            def prepare_settings(adb,**kwargs):
                nonlocal record_path
                self.assertEqual(kwargs,dict(serial='fake-serial',environment=module.os.environ,root=root,source='1'*40,record_path=out/'ui-settings-services-isolation.json'))
                order.append('settings');record_path=kwargs['record_path']
                record_path.write_text(json.dumps(dict(status='host-only-control',mutationAttempted=False,restorationVerified=preparation_error)))
                if preparation_error:raise RuntimeError('host-only preparation failure after its own restoration')
                return lease
            def finish_settings(actual,report):
                self.assertIs(actual,lease);order.append('restore')
                if restoration_error:raise RuntimeError('host-only restoration failure')
                value=json.loads(record_path.read_text());value['restorationVerified']=True
                record_path.write_text(json.dumps(value))
            wellbeing.prepare_workflow=prepare_wellbeing
            settings.prepare_workflow=prepare_settings;settings.finish_workflow=finish_settings
            def workload():
                self.assertEqual(order,['identity','wellbeing','settings']);order.append('workload')
                if partial_copy_error:(integration/'ui-reload-confirmation.json').write_bytes(b'host-only partial report')
                if workload_error:raise RuntimeError('host-only workload failure')
            original_read,original_write=Path.read_bytes,Path.write_bytes
            def read_bytes(path):
                if sourcehash_error and path==root/inputs[0] and 'workload' in order:
                    raise OSError('host-only source verification read failure')
                return original_read(path)
            def write_bytes(path,value):
                if partial_copy_error and path==out/'ui-reload-confirmation.json':
                    raise OSError('host-only partial report copy failure')
                return original_write(path,value)
            def check_output(command,**kwargs):
                if command==['git','rev-parse','HEAD']:return '1'*40+'\n'
                if command==['git','rev-parse','HEAD^{tree}']:return '2'*40+'\n'
                if command[:2]==['git','status']:return ''
                self.assertEqual(command[:3],['fake-adb','-s','fake-serial'])
                if command[3:6]==['exec-out','content','read']:return json.dumps(identity).encode()
                return b'host-only external response'
            build=types.ModuleType('profile_invocation_contract');build.expected_build=lambda *args:identity
            def verify(actual,expected):self.assertEqual(actual,expected);order.append('identity')
            build.verify_installed=verify
            privacy=types.ModuleType('diagnostic_capture_privacy');privacy.checked_text=lambda value:(value,None)
            contract=types.ModuleType('chrome_collapse_contract');contract.verify_auto_collapse=lambda *args:{'hostOnly':True}
            before_path=sys.path[:];error=None
            try:
                with mock.patch.object(module,'ROOT',root),mock.patch.object(module,'selected_program',return_value=ast.parse("reload_confirmation={'hostOnly':True}\nworkload_boundary()\nauto_collapse={'hostOnly':True}")),\
                     mock.patch.object(module,'workload_boundary',workload,create=True),\
                     mock.patch.object(Path,'read_bytes',read_bytes),mock.patch.object(Path,'write_bytes',write_bytes),\
                     mock.patch.object(module.subprocess,'check_output',side_effect=check_output),\
                     mock.patch.dict(sys.modules,{'profile_invocation_contract':build,'diagnostic_capture_privacy':privacy,
                         'chrome_collapse_contract':contract,'ui_test_device':wellbeing,'ui_settings_services_device11':settings}),\
                     mock.patch.object(sys,'argv',['focused','--adb','fake-adb','--serial','fake-serial','--scenario','after-reload','--out',str(out)]):
                    try:module.main()
                    except Exception as actual:error=actual
            finally:sys.path[:]=before_path
            report=json.loads((out/'results.json').read_text())
            self.assertFalse(report['rootCauseEstablished']);self.assertEqual(report['sourceInputsUnchanged'],not sourcehash_error)
            self.assertFalse(report['deviceIsolation']['previousFailureCauseProven'])
            self.assertEqual(report['settingsServicesIsolation']['restorationVerified'],preparation_error or not restoration_error)
            self.assertEqual(report['status'],'failed' if preparation_error or workload_error or restoration_error or sourcehash_error or partial_copy_error else 'passed')
            self.assertEqual(order,['identity','wellbeing','settings']+([] if preparation_error else ['workload','restore']))
            if preparation_error:self.assertIn('preparation failure',str(error))
            elif workload_error:self.assertIn('workload failure',str(error))
            elif sourcehash_error:self.assertIn('source verification read failure',str(error))
            elif partial_copy_error:self.assertIn('partial report copy failure',str(error))
            elif restoration_error:self.assertIn('restoration failure',str(error))
            else:self.assertIsNone(error)
            if restoration_error:self.assertIn('restoration failure',report['deviceRestorationError'])
            if sourcehash_error:self.assertIn('source verification read failure',report['diagnosticCollectionError'])
            if partial_copy_error:self.assertIn('partial report copy failure',report['diagnosticCollectionError'])
    def test_same_preconditions_run_before_workload_and_restore_after_success(self):self.execute()
    def test_workload_failure_still_restores_and_retains_failure(self):self.execute(workload_error=True)
    def test_preparation_failure_keeps_its_own_restoration_record_without_running_workload(self):self.execute(preparation_error=True)
    def test_restoration_failure_cannot_produce_success(self):self.execute(restoration_error=True)
    def test_restoration_failure_does_not_mask_original_workload_failure(self):self.execute(workload_error=True,restoration_error=True)
    def test_source_read_failure_still_restores_and_cannot_produce_success(self):self.execute(sourcehash_error=True)
    def test_partial_copy_failure_still_restores_and_cannot_produce_success(self):self.execute(partial_copy_error=True)
    def test_collection_and_restoration_failures_do_not_mask_original_workload_failure(self):
        for failure in ('sourcehash_error','partial_copy_error'):
            with self.subTest(failure=failure):self.execute(workload_error=True,restoration_error=True,**{failure:True})


class ReloadTimeoutObservationTest(unittest.TestCase):
    def test_timeout_keeps_original_deadline_predicate_error_and_adds_read_only_observation(self):
        java=(ROOT/'tests/gecko/CompactChromeIntegrationActivity.java').read_text()
        self.assertIn('reloadCommandDeadline=SystemClock.elapsedRealtime()+10000',java)
        self.assertIn('waitReloadModal(request.deadline)',java)
        self.assertNotIn('waitReloadModal(SystemClock.elapsedRealtime()+10000)',java)
        self.assertIn('if(reloadDialog==modal&&attached&&focused&&laidOut&&controls.length()==2)',java)
        self.assertIn('if(SystemClock.elapsedRealtime()>deadline){reloadModalReadinessTimeout();reloadTrace("modal-timeout",null,null);reloadEvent("error",J.obj("error","Reload confirmation did not appear"));return;}handler.postDelayed(()->waitReloadModal(deadline),50);',java)
        snapshot=java[java.index('  JSONObject reloadReadinessView('):java.index('  void reloadSnapshot(')]
        self.assertIn('Math.min(8,modal.footer.getChildCount())',snapshot)
        self.assertIn('"rootCauseEstablished",false',snapshot)
        self.assertIn('"<outside-fixture>"',snapshot)
        self.assertIn('"host",reloadReadinessView(getWindow().getDecorView())',snapshot)
        for mutation in ('requestFocus(', 'requestLayout(', '.layout(', '.measure(', 'evaluateJavascript(', 'loadUrl(', 'ProfileCatalog', '.set'):
            self.assertNotIn(mutation,snapshot)


class ReloadForegroundPreparationTest(unittest.TestCase):
    """Execute exact new Java members with declared clock/window/session edges."""
    def test_actual_shared_deadline_single_invocation_and_stale_command_cancellation(self):
        java=(ROOT/'tests/gecko/CompactChromeIntegrationActivity.java').read_text()
        reader_spec=importlib.util.spec_from_file_location('foreground_member_reader',ROOT/'tests/chrome-network-state-host/run.py')
        reader=importlib.util.module_from_spec(reader_spec);reader_spec.loader.exec_module(reader)
        names=('void beginReloadCommand(','static final class ReloadForegroundRequest','void requestReloadWhenForeground(')
        members='\n'.join(reader.member(java,name) for name in names)
        branch=reader.member(java,'if("requestReload".equals(action))')
        intent=reader.member(java,'protected void onNewIntent(')
        self.assertLess(intent.index('if(reloadFixture)beginReloadCommand();'),intent.index('super.onNewIntent(intent);'))
        self.assertNotIn('SystemClock.elapsedRealtime()+10000',branch)
        self.assertIn('waitReloadModal(request.deadline)',members)
        for forbidden in ('requestFocus(', 'requestLayout(', 'setVisibility(', 'evaluateJavascript(', 'loadUrl(', 'ProfileCatalog'):
            self.assertNotIn(forbidden,members)
        home=os.environ.get('JAVA_HOME_17_X64') or os.environ.get('JAVA_HOME')
        compiler=Path(home)/'bin/javac' if home else Path(shutil.which('javac') or '');runtime=compiler.with_name('java')
        jars=[Path(os.environ['PROFILE_JSON_JAR'])] if os.environ.get('PROFILE_JSON_JAR') else []
        jars += [ROOT/'work/gecko-integration/catalog-json.jar',ROOT/'work/ux-build-deps/json-20240303.jar']
        jar=next((path for path in jars if path.is_file()),None)
        self.assertTrue(compiler.is_file() and runtime.is_file() and jar is not None,'Actual JDK and JSON jar required; no skip')
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/'ReloadForegroundHost.java'
            target.write_text('''package local.pocketchat;import org.json.*;import java.util.*;
              public final class ReloadForegroundHost {
                static int checks;static void check(boolean value){checks++;if(!value)throw new AssertionError("foreground control "+checks);}
                static final class SystemClock {static long now;static long elapsedRealtime(){return now;}}
                static final class View {boolean attached=true,focused=true;boolean isAttachedToWindow(){return attached;}boolean hasWindowFocus(){return focused;}}
                static final class Window {final View decor=new View();View getDecorView(){return decor;}}
                static final class ChatSession {long environmentGeneration=7;boolean deleted;}
                static class GeckoWebView {Object current=new Object();}
                static final class ReloadView extends GeckoWebView {final String reloadRun="recorded-fixture-run";}
                static final class Handler {final ArrayDeque<Runnable> queue=new ArrayDeque<>();void postDelayed(Runnable r,long delay){check(delay==50);queue.add(r);}void next(){queue.remove().run();}}
                boolean reloadFixture=true,destroyed,active=true;Object collapse;int reloadCommandGeneration;long reloadCommandDeadline;ReloadForegroundRequest pendingReloadRequest;
                ChatSession session=new ChatSession();GeckoWebView remote=new ReloadView();String command="owned-command";Handler handler=new Handler();Window window=new Window();
                int reloadCalls,modalCalls,errors,snapshots;long modalDeadline,requestedAt;
                Window getWindow(){return window;}
                void requestReload(){check(active&&window.decor.attached&&window.decor.focused&&!destroyed);reloadCalls++;requestedAt=SystemClock.now;}
                void waitReloadModal(long deadline){modalCalls++;modalDeadline=deadline;}
                void reloadModalReadinessTimeout(){snapshots++;}void reloadTrace(String phase,Object target,Boolean result){}
                void reloadEvent(String event,JSONObject value){check(event.equals("error")&&value.optString("error").equals("Reload request host window is not input-ready"));errors++;}
            '''+members+'\nvoid submit(String action){'+branch+'''}
                static ReloadForegroundHost fresh(boolean ready){SystemClock.now=1000;ReloadForegroundHost h=new ReloadForegroundHost();h.window.decor.focused=ready;h.beginReloadCommand();return h;}
                public static void main(String[] args){
                  ReloadForegroundHost h=fresh(true);SystemClock.now=2500;h.submit("requestReload");check(h.reloadCalls==1&&h.modalCalls==1&&h.modalDeadline==11000&&h.pendingReloadRequest==null);
                  for(int edge=0;edge<3;edge++){
                    h=fresh(true);if(edge==0)h.active=false;if(edge==1)h.window.decor.attached=false;if(edge==2)h.window.decor.focused=false;
                    h.submit("requestReload");ReloadForegroundRequest saved=h.pendingReloadRequest;check(h.reloadCalls==0&&h.handler.queue.size()==1);
                    SystemClock.now=5000;h.handler.next();check(h.reloadCalls==0&&h.handler.queue.size()==1);
                    h.active=true;h.window.decor.attached=true;h.window.decor.focused=true;SystemClock.now=6000;h.handler.next();
                    check(h.reloadCalls==1&&h.modalCalls==1&&h.modalDeadline==11000&&h.requestedAt==6000);h.requestReloadWhenForeground(saved);check(h.reloadCalls==1);
                  }
                  for(int stale=0;stale<11;stale++){
                    h=fresh(false);h.submit("requestReload");ReloadForegroundRequest saved=h.pendingReloadRequest;
                    if(stale==0)h.reloadCommandGeneration++;if(stale==1)h.command="new-command";if(stale==2)h.session=new ChatSession();
                    if(stale==3)h.session.deleted=true;if(stale==4)h.session.environmentGeneration++;if(stale==5)h.remote=new ReloadView();
                    if(stale==6)h.remote.current=new Object();if(stale==7)h.reloadFixture=false;if(stale==8)h.destroyed=true;if(stale==9)h.collapse=new Object();
                    if(stale==10){saved=new ReloadForegroundRequest(saved.deadline,saved.generation,saved.command,saved.owner,saved.browser,saved.sdk,saved.environmentGeneration,"wrong-fixture-run");h.pendingReloadRequest=saved;}
                    h.window.decor.focused=true;h.requestReloadWhenForeground(saved);check(h.reloadCalls==0&&h.modalCalls==0&&h.errors==0&&h.pendingReloadRequest==null);
                  }
                  h=fresh(false);h.submit("requestReload");SystemClock.now=11001;h.window.decor.focused=true;h.handler.next();
                  check(h.reloadCalls==0&&h.modalCalls==0&&h.errors==1&&h.snapshots==1&&h.pendingReloadRequest==null);
                  h=fresh(false);h.submit("requestReload");SystemClock.now=11000;h.window.decor.focused=true;h.handler.next();check(h.reloadCalls==1&&h.modalDeadline==11000);
                  h=fresh(false);h.submit("requestReload");ReloadForegroundRequest old=h.pendingReloadRequest;SystemClock.now=2000;
                  h.beginReloadCommand();h.command="next-command";h.submit("requestReload");ReloadForegroundRequest next=h.pendingReloadRequest;h.window.decor.focused=true;
                  h.handler.next();check(h.reloadCalls==0&&h.pendingReloadRequest==next);h.handler.next();check(h.reloadCalls==1&&h.modalDeadline==12000);
                  h.requestReloadWhenForeground(old);h.requestReloadWhenForeground(next);check(h.reloadCalls==1&&h.modalCalls==1);
                  System.out.println(checks+" exact source foreground checks");
                }}''')
            built=subprocess.run([str(compiler),'-encoding','UTF-8','-cp',str(jar),'-d',directory,str(ROOT/'app/src/main/java/local/pocketchat/J.java'),str(target)],capture_output=True,text=True,timeout=30)
            self.assertEqual(built.returncode,0,built.stderr)
            ran=subprocess.run([str(runtime),'-cp',directory+os.pathsep+str(jar),'local.pocketchat.ReloadForegroundHost'],capture_output=True,text=True,timeout=10)
            self.assertEqual(ran.returncode,0,ran.stderr)
            self.assertIn(' exact source foreground checks',ran.stdout)


def controlled_key_diagnostic():
    # Generated fixture values only, never credentials or captured raw logs.
    key='AIza'+'A'*35
    return 'benign café prefix '+key+' escaped '+key.replace('A',r'\u0041',1)+' suffix'


def diagnostic_expected(value):
    key='AIza'+'A'*35
    return value.replace(key,'[REDACTED_SERVICE_API_KEY]').replace(key.replace('A',r'\u0041',1),'[REDACTED_SERVICE_API_KEY]')

if __name__=='__main__':unittest.main()
