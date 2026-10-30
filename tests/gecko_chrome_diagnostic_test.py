"""Guard selected-source diagnostic reuse; no counterfeit Android success."""
import ast
import copy
import importlib.machinery
import importlib.util
import itertools
import json
from pathlib import Path
import shutil
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


def controlled_key_diagnostic():
    # Generated fixture values only, never credentials or captured raw logs.
    key='AIza'+'A'*35
    return 'benign café prefix '+key+' escaped '+key.replace('A',r'\u0041',1)+' suffix'


def diagnostic_expected(value):
    key='AIza'+'A'*35
    return value.replace(key,'[REDACTED_SERVICE_API_KEY]').replace(key.replace('A',r'\u0041',1),'[REDACTED_SERVICE_API_KEY]')

if __name__=='__main__':unittest.main()
