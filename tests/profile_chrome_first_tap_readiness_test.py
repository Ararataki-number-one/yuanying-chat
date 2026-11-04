"""Controlled process/ADB edges exercise the real first-tap preparation policy.

These are host controls, not Android input or application qualification. The
existing header-readiness suite independently executes the unchanged real WM
parser. No expected collapse payload, event or successful gesture is fabricated.
"""
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools/gecko'))
spec = importlib.util.spec_from_file_location('tested_first_tap', ROOT/'tools/gecko/chrome_first_tap_readiness.py')
module = importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
SOURCE, TREE, APK, NONCE = 'a'*40, 'b'*40, 'c'*64, 'd'*32
OWNER = dict(pid='4242', uid=10209, startTicks='100', systemUiUid=10181)
IDENTITY = dict(sourceCommit=SOURCE, sourceTree=TREE, apkSha256=APK)
COMPONENT = module.gate.COMPONENT
# Exact typed documentReadyEvidence object from Source9's actual cold ready
# snapshot (d10843d..., run41892126356/job126802060801, raw job-log SHA256
# d378cfd0925423f01e83a776c09ca050f4e706a1b43877eb2cb483d83db3c102).
# The host supplies explicit port/SDK object boundaries and a controlled nonce;
# it does not claim to reproduce the Android identities or create a new token.
COLD_EVIDENCE = {
    'rawMessage': {'appearanceDocument':'b43aff0d-a83e20c2-82d6c412-37ba3466',
        'url':'http://127.0.0.1:8765/c/reload-collapse','kind':'documentReady','appearanceProtocol':1},
    'senderUrl':'http://127.0.0.1:8765/c/reload-collapse','actualUrl':'http://127.0.0.1:8765/c/reload-collapse',
    'visibleUrl':'https://chatgpt.com/c/reload-collapse','nativeSession':131059068,'currentSession':131059068,
    'topLevel':True,'contentScript':True,
    'normalizedMessage':{'appearanceDocument':'b43aff0d-a83e20c2-82d6c412-37ba3466',
        'url':'https://chatgpt.com/c/reload-collapse','kind':'documentReady','appearanceProtocol':1},
    'acceptedByProduction':True,
}


def before():
    return dict(surface=11, sdkSession=12, attachedSession=12, compactTap=[540,114], activityStarts=0, menuOpens=0,
                pending=dict(id='controlled-pending'), documentReadyEvidence=dict(rawMessage=dict(appearanceDocument='e'*32)))


def packet(request=NONCE+'-1', sequence=1):
    return dict(schema=1, kind='nativeInputReadiness', diagnosticOnly=True, releaseAcceptance=False,
        sourceCommit=SOURCE, sourceTree=TREE, apkSha256=APK, runNonce=NONCE, request=request, fixtureAction='chromeCollapse',
        sequence=sequence, observedAtElapsedRealtime=1000+sequence, pid=4242, uid=10209, activityRef=13,
        surface=11, sdkSession=12, attachedSession=12, appearanceDocument='e'*32, documentBinding='fixture-admitted-current-port',documentPort=14,currentPort=14,url=module.TARGET,
        pendingId='controlled-pending', pendingConfirmed=True, windowFocus=True, decorFocus=True, attached=True,
        shown=True, enabled=True, clickable=True, laidOut=True, layoutRequested=False, globallyVisible=True,
        visibleDocument=True, expanded=False, toolbarVisibility=0, compactVisibility=0, page=0,
        activityStarts=0, menuOpens=0, nativeTouchCount=0, hostBounds=[0,72,1080,1920], toolbarBounds=[0,72,1080,210],
        compactBounds=[0,72,1080,156], visibleBounds=[0,72,1080,156], webBounds=[0,210,1080,1665], point=[540,114])


class SnapshotPolicyTest(unittest.TestCase):
    def invoke(self, value, initial=None):
        return module._validate_snapshot(value, source=SOURCE, identity=IDENTITY, nonce=NONCE,
            request=NONCE+'-1', owner=OWNER, before=before() if initial is None else initial)

    def test_exact_owned_visible_focused_geometry_is_ready(self):
        self.assertEqual(set(packet()),module.SNAPSHOT_FIELDS)
        self.assertEqual(self.invoke(packet())['point'],[540,114])

    def test_stale_source_native_owner_document_or_task_is_rejected(self):
        mutations=dict(sourceCommit='f'*40,sourceTree='f'*40,apkSha256='f'*64,runNonce='f'*32,request=NONCE+'-2',
            fixtureAction='other',pid=4243,uid=10210,surface=21,sdkSession=22,attachedSession=22,
            appearanceDocument='f'*32,documentBinding='production-appearance-cache',documentPort=15,currentPort=15,url='https://chatgpt.com/c/other',pendingId='other',pendingConfirmed=False,
            expanded=True,page=1,nativeTouchCount=1,activityStarts=1,menuOpens=1)
        for key,value in mutations.items():
            with self.subTest(key=key),self.assertRaises(module.gate.HeaderReadinessFailure):self.invoke(dict(packet(),**{key:value}))

    def test_missing_unknown_and_type_confused_fields_fail_closed(self):
        for key in module.SNAPSHOT_FIELDS:
            value=packet();del value[key]
            with self.subTest(missing=key),self.assertRaises(module.gate.HeaderReadinessFailure):self.invoke(value)
        for key,value in [('unknown','private text'),('windowFocus',1),('sequence',True),('uid',True),('point',[True,114]),('hostBounds',[0,0,True,200])]:
            with self.subTest(key=key),self.assertRaises(module.gate.HeaderReadinessFailure):self.invoke(dict(packet(),**{key:value}))

    def test_focus_layout_occlusion_or_changed_point_is_not_ready(self):
        for key,value in [('windowFocus',False),('decorFocus',False),('attached',False),('shown',False),('enabled',False),
            ('clickable',False),('laidOut',False),('layoutRequested',True),('globallyVisible',False),
            ('visibleBounds',[0,72,500,156]),('compactBounds',[20,72,1100,156]),('webBounds',[0,0,0,0])]:
            with self.subTest(key=key):self.assertIsNone(self.invoke(dict(packet(),**{key:value})))

    def test_nonzero_root_screen_origin_is_preserved(self):
        value=packet();initial=before();dx,dy=17,29
        for key in ('hostBounds','toolbarBounds','compactBounds','visibleBounds','webBounds'):
            l,t,r,b=value[key];value[key]=[l+dx,t+dy,r+dx,b+dy]
        value['point']=[557,143];initial['compactTap']=[557,143]
        self.assertEqual(self.invoke(value,initial)['point'],[557,143])
        value['visibleBounds']=[0,72,1080,156]
        self.assertIsNone(self.invoke(value,initial))


class Transport:
    """Only read-only preparation and the one original tap may be issued."""
    def __init__(self):
        self.now=100.;self.commands=[];self.taps=[];self.requests=0;self.wm=0;self.states=[]
        self.frames=[];self.focuses=[];self.owner=copy.deepcopy(OWNER);self.current=None;self.transport_pid=4242
        self.duplicate=False;self.tap_exit=0;self.tap_seconds=0.;self.identity_change=False;self.identity_reads=0
    def clock(self):return self.now
    def sleep(self,value):self.now+=value
    def identity(self,*args):
        self.identity_reads+=1;self.now+=.01
        return dict(self.owner,pid='9999') if self.identity_change and self.identity_reads>1 else self.owner
    def checked(self,parts,deadline,**kwargs):
        self.commands.append((list(parts),deadline));self.now+=.03
        module.gate.need(self.now<deadline,'deadline')
        if parts[0]=='controlled-parser':return self.states.pop(0) if self.states else b'CLEAR\n'
        self.assert_prefix(parts);values=parts[3:]
        if values==['shell','getprop','ro.kernel.qemu']:return b'1\n'
        if values==['shell','getprop','ro.build.version.sdk']:return b'35\n'
        if values==['shell','am','get-current-user']:return b'0\n'
        if values==['shell','getprop','ro.hardware']:return b'ranchu\n'
        if values==['shell','dumpsys','window']:
            self.wm+=1;focus=self.focuses.pop(0) if self.focuses else 'Window{abc u0 '+COMPONENT+'}'
            return ('WINDOW MANAGER\n mCurrentFocus='+focus+'\n').encode()
        if values[:3]==['shell','am','broadcast']:
            assert values[values.index('eventNonce')+1]==NONCE
            request=values[values.index('collapseReadiness')+1];self.requests+=1
            self.current=packet(request,self.requests)
            if self.frames:
                update=self.frames.pop(0)
                self.current.update(update)
            return b'Broadcast completed: result=0\n'
        if values[:3]==['logcat','-d','-v']:
            line=f'11-04 19:18:01.001 {self.transport_pid:5} {self.transport_pid:5} I {module.TAG}: '+json.dumps(self.current)+'\n'
            return (line*(2 if self.duplicate else 1)).encode()
        raise AssertionError(('Unexpected or mutating preparation command',parts))
    def assert_prefix(self,parts):assert parts[:3]==['controlled-adb','-s','emulator-5554']
    def run(self,parts,deadline,**kwargs):
        self.assert_prefix(parts);assert parts[3:]==['shell','input','tap','540','114']
        self.taps.append((parts,deadline,self.now));self.now+=self.tap_seconds
        return subprocess.CompletedProcess(parts,self.tap_exit,b'',b'')


class FirstTapControlTest(unittest.TestCase):
    def invoke(self, transport, *, expected_error=None, diagnostic_output=False):
        with tempfile.TemporaryDirectory() as directory:
            out=Path(directory);binding=dict(sourceCommit=SOURCE,sourceTree=TREE,sourceSha256={'old-header':'f'*64})
            classes={'one.class':'c'*64};compiled=dict(cache=out,classes=classes,parserClassesSha256='d'*64)
            report_out=out/'diagnostic' if diagnostic_output else out
            report_out.mkdir(exist_ok=True)
            argv=['--adb','controlled-adb','--serial','emulator-5554']+(['--out',str(report_out)] if diagnostic_output else [])
            result=None;error=None
            with mock.patch.object(module,'_sources',return_value=(binding,{'new-helper':'e'*64})),\
                 mock.patch.object(module.gate,'_compile_parser',return_value=(['controlled-parser'],compiled)),\
                 mock.patch.object(module.gate,'_identity',side_effect=transport.identity),\
                 mock.patch.object(module.gate,'_checked',side_effect=transport.checked),\
                 mock.patch.object(module.gate,'_class_hashes',return_value=classes),\
                 mock.patch.object(module.gate,'_bounded_run',side_effect=transport.run),contextlib.redirect_stdout(io.StringIO()):
                try:result=module.first_tap_once(argv=argv,source=SOURCE,
                    identity=IDENTITY,before=before(),nonce=NONCE,out=out,root=out,clock=transport.clock,sleep=transport.sleep)
                except module.gate.HeaderReadinessFailure as actual:error=actual
            report=json.loads((report_out/('chrome-first-tap-readiness-'+NONCE+'.json')).read_text())
            if diagnostic_output:self.assertFalse((out/('chrome-first-tap-readiness-'+NONCE+'.json')).exists())
            if expected_error is None:
                self.assertIsNone(error);self.assertEqual(result,report);self.assertEqual(report['status'],'passed')
            else:
                self.assertIsNotNone(error);self.assertEqual(error.reason,expected_error);self.assertEqual(report['status'],'failed')
            self.assertEqual(report['tapInvocations'],len(transport.taps))
            self.assertLessEqual(len(report['nativeSnapshots']),4);self.assertLessEqual(len(report['windowObservations']),8)
            self.assertTrue(all(deadline==120. for _,deadline in transport.commands))
            self.assertTrue(all(deadline==190. for _,deadline,_ in transport.taps))
            return report

    def test_two_fresh_owned_snapshots_then_exactly_one_original_tap(self):
        t=Transport();r=self.invoke(t)
        self.assertEqual(t.requests,2);self.assertEqual(len(t.taps),1);self.assertEqual(r['point'],before()['compactTap'])
        self.assertLess(t.taps[0][2],120.)

    def test_focused_diagnostic_keeps_its_source_bound_proof_in_archived_output(self):
        t=Transport();self.invoke(t,diagnostic_output=True);self.assertEqual(len(t.taps),1)

    def test_unfocused_native_snapshot_is_refreshed_without_input(self):
        t=Transport();t.frames=[dict(windowFocus=False),{},{}];self.invoke(t)
        self.assertEqual(t.requests,3);self.assertEqual(len(t.taps),1)

    def test_foreign_focused_owner_is_only_observed_then_revalidated(self):
        t=Transport();t.focuses=['Window{def u0 com.android.systemui/NotificationShade}'];r=self.invoke(t)
        self.assertEqual(r['windowObservations'][0]['currentFocus'],'Window{def u0 com.android.systemui/NotificationShade}')
        self.assertEqual(len(t.taps),1)

    def test_shade_visible_defers_without_mutating_device(self):
        t=Transport();t.states=[b'SHADE_VISIBLE\n',b'CLEAR\n',b'CLEAR\n',b'CLEAR\n'];r=self.invoke(t)
        self.assertEqual(r['windowObservations'][0]['parserState'],'SHADE_VISIBLE');self.assertEqual(len(t.taps),1)

    def test_changed_geometry_requires_two_new_fresh_stable_snapshots(self):
        t=Transport();t.frames=[{},dict(compactBounds=[0,74,1080,154],visibleBounds=[0,74,1080,154]),
                               dict(compactBounds=[0,74,1080,154],visibleBounds=[0,74,1080,154])]
        self.invoke(t);self.assertEqual(t.requests,3)

    def test_changed_original_tap_point_is_not_emitted(self):
        t=Transport();t.frames=[dict(compactBounds=[20,72,1100,156],visibleBounds=[20,72,1100,156],point=[560,114])]*128
        self.invoke(t,expected_error='deadline');self.assertEqual(t.taps,[])

    def test_persistent_foreign_window_expires_without_input_and_retains_actual_owner(self):
        t=Transport();t.focuses=['Window{def u0 com.android.systemui/NotificationShade}']*128
        r=self.invoke(t,expected_error='deadline');self.assertEqual(t.taps,[])
        self.assertIn('com.android.systemui/NotificationShade',r['windowObservations'][-1]['currentFocus'])

    def test_changed_process_or_native_identity_never_emits(self):
        for fault in ('process','surface','token','activity'):
            with self.subTest(fault=fault):
                t=Transport()
                if fault=='process':t.identity_change=True
                elif fault=='surface':t.frames=[dict(surface=21)]
                elif fault=='token':t.frames=[dict(appearanceDocument='f'*32)]
                else:t.frames=[{},dict(activityRef=14)]
                self.invoke(t,expected_error='identity-changed');self.assertEqual(t.taps,[])

    def test_logcat_transport_pid_cannot_be_spoofed_by_json(self):
        t=Transport();t.transport_pid=9999;self.invoke(t,expected_error='identity-changed');self.assertEqual(t.taps,[])

    def test_duplicate_or_regressing_snapshot_is_rejected(self):
        for duplicate in (True,False):
            with self.subTest(duplicate=duplicate):
                t=Transport();t.duplicate=duplicate
                if not duplicate:t.frames=[{},dict(sequence=1)]
                self.invoke(t,expected_error='invalid-observation');self.assertEqual(t.taps,[])

    def test_nonzero_tap_exit_is_preserved_without_retry(self):
        t=Transport();t.tap_exit=1;self.invoke(t,expected_error='action-failed');self.assertEqual(len(t.taps),1)

    def test_original_90_second_action_budget_is_not_extended_by_preparation(self):
        t=Transport();t.tap_seconds=90;self.invoke(t,expected_error='deadline');self.assertEqual(len(t.taps),1)


class NativeReadOnlySourceTest(unittest.TestCase):
    def test_readiness_is_separate_from_original_event_stream_and_has_no_ui_mutators(self):
        java=(ROOT/'tests/gecko/ChromeCollapseIntegration.java').read_text()
        body=java[java.index('  void inputReadiness('):java.index('  ChromeCollapseIntegration(',java.index('  void inputReadiness('))]
        self.assertIn('"local.pocketchat.test".equals(a.getPackageName())',body)
        self.assertIn('request.matches(nonce+"-[1-9][0-9]{0,2}")',body)
        self.assertIn('Log.i("PocketChromeInputReady",raw)',body)
        self.assertIn('length>3500',body)
        for forbidden in ('events.emit','evaluateJavascript','loadUrl','requestFocus','requestLayout','setVisibility','ProfileCatalog','getString("pending"'):
            self.assertNotIn(forbidden,body)

    def test_actual_native_visible_rect_conversion_handles_nonzero_root_origin(self):
        java=(ROOT/'tests/gecko/ChromeCollapseIntegration.java').read_text()
        start=java.index('boolean globallyVisible=compact.getGlobalVisibleRect(visible);',java.index('  void inputReadiness('))
        end=java.index('JSONObject pending=',start);fragment=java[start:end]
        home=os.environ.get('JAVA_HOME_17_X64') or os.environ.get('JAVA_HOME')
        compiler=Path(home)/'bin/javac' if home else Path(shutil.which('javac') or '')
        runtime=compiler.with_name('java');self.assertTrue(compiler.is_file() and runtime.is_file(),'Real JDK required; no skipped controls')
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/'Origin.java'
            target.write_text('''final class Origin {
              static final class Rect {int left,top,right,bottom;void offset(int x,int y){left+=x;right+=x;top+=y;bottom+=y;}}
              static final class View {int x,y;View(int x,int y){this.x=x;this.y=y;}boolean getGlobalVisibleRect(Rect r){r.left=0;r.top=72;r.right=1080;r.bottom=156;return true;}View getRootView(){return this;}void getLocationOnScreen(int[] a){a[0]=x;a[1]=y;}}
              public static void main(String[] args){for(int[] origin:new int[][]{{0,0},{17,29},{-30,100}}){View compact=new View(origin[0],origin[1]);Rect visible=new Rect();
              '''+fragment+'''
              if(!globallyVisible||visible.left!=origin[0]||visible.top!=72+origin[1]||visible.right!=1080+origin[0]||visible.bottom!=156+origin[1])throw new AssertionError("Actual native origin conversion");}System.out.println("3 native source origin controls");}}
            ''')
            built=subprocess.run([str(compiler),'-encoding','UTF-8','-d',directory,str(target)],capture_output=True,text=True,timeout=20)
            self.assertEqual(built.returncode,0,built.stderr)
            ran=subprocess.run([str(runtime),'-cp',directory,'Origin'],capture_output=True,text=True,timeout=10)
            self.assertEqual(ran.returncode,0,ran.stderr);self.assertEqual(ran.stdout.strip(),'3 native source origin controls')

    def test_exact_admission_binding_accepts_recorded_cold_message_and_rejects_stale_owners(self):
        java=(ROOT/'tests/gecko/ChromeCollapseIntegration.java').read_text()
        start=java.index('  static final class InputDocumentBinding {');end=java.index('  ChromeCollapseIntegration(',start)
        actual=java[start:end]
        self.assertNotIn('appearanceDocuments',java[java.index('  void inputReadiness('):start])
        self.assertIn('incoming,ports.get(current),current,System.identityHashCode(current)',java)
        self.assertLess(java.index('original.onPortMessage(forwarded,incoming);',java.index('  static final class CollapseView')),
                        java.index('inputBinding=InputDocumentBinding.admit('))
        self.assertIn('!staleAppearanceConnections.contains(incoming)&&java.util.Objects.equals(appearanceConnections.get(incoming),appearanceLoads.getOrDefault(current,0L))',java)
        home=os.environ.get('JAVA_HOME_17_X64') or os.environ.get('JAVA_HOME')
        compiler=Path(home)/'bin/javac' if home else Path(shutil.which('javac') or '');runtime=compiler.with_name('java')
        jars=[Path(os.environ['PROFILE_JSON_JAR'])] if os.environ.get('PROFILE_JSON_JAR') else []
        jars += [ROOT/'work/gecko-integration/catalog-json.jar',ROOT/'work/ux-build-deps/json-20240303.jar']
        jar=next((path for path in jars if path.is_file()),None)
        self.assertTrue(compiler.is_file() and runtime.is_file() and jar is not None,'Actual JDK and JSON jar required; no skip')
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/'BindingHost.java'
            target.write_text('''import org.json.JSONObject;final class BindingHost {
              static final String TARGET="https://chatgpt.com/c/reload-collapse",LOCAL="http://127.0.0.1:8765/c/reload-collapse";
              static final String NONCE="dddddddddddddddddddddddddddddddd",SOURCE="d10843d321f426cb66a3fef7a232adf52fd0d15e";
            '''+actual+'''
              static int checks;static void check(boolean value){checks++;if(!value)throw new AssertionError("admitted current cold document "+checks);}
              static InputDocumentBinding admit(Object p,Object s,JSONObject e){return InputDocumentBinding.admit(p,p,s,131059068,NONCE,SOURCE,e,LOCAL,TARGET,s,true,true,true);}
              static String current(InputDocumentBinding b,Object p,Object s,JSONObject e){return b.current(p,s,131059068,NONCE,SOURCE,e,LOCAL,TARGET,s,true,true,true);}
              public static void main(String[] args)throws Exception{
                Object p=new Object(),s=new Object();JSONObject e=new JSONObject(args[0]);InputDocumentBinding b=admit(p,s,e);
                check(b!=null);check(current(b,p,s,e).equals(e.getJSONObject("rawMessage").getString("appearanceDocument")));
                check(InputDocumentBinding.admit(p,new Object(),s,131059068,NONCE,SOURCE,e,LOCAL,TARGET,s,true,true,true)==null);
                check(InputDocumentBinding.admit(p,p,s,131059068,NONCE,SOURCE,e,LOCAL,TARGET,new Object(),true,true,true)==null);
                check(InputDocumentBinding.admit(p,p,s,131059068,NONCE,SOURCE,e,LOCAL,TARGET,s,true,true,false)==null);
                check(InputDocumentBinding.admit(p,p,s,131059068,"wrong",SOURCE,e,LOCAL,TARGET,s,true,true,true)==null);
                check(current(b,new Object(),s,e).isEmpty());check(current(b,p,new Object(),e).isEmpty());
                check(current(b,p,s,new JSONObject(e.toString())).isEmpty());
                check(b.current(p,s,131059069,NONCE,SOURCE,e,LOCAL,TARGET,s,true,true,true).isEmpty());
                check(b.current(p,s,131059068,"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",SOURCE,e,LOCAL,TARGET,s,true,true,true).isEmpty());
                check(b.current(p,s,131059068,NONCE,"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",e,LOCAL,TARGET,s,true,true,true).isEmpty());
                check(b.current(p,s,131059068,NONCE,SOURCE,e,LOCAL,TARGET,s,true,true,false).isEmpty());
                check(b.current(p,s,131059068,NONCE,SOURCE,e,LOCAL,TARGET,s,false,true,true).isEmpty());
                check(b.current(p,s,131059068,NONCE,SOURCE,e,LOCAL,TARGET,s,true,false,true).isEmpty());
                check(b.current(p,s,131059068,NONCE,SOURCE,e,"http://foreign.example/",TARGET,s,true,true,true).isEmpty());
                check(b.current(p,s,131059068,NONCE,SOURCE,e,LOCAL,"https://chatgpt.com/c/other",s,true,true,true).isEmpty());
                for(String key:new String[]{"acceptedByProduction","topLevel","contentScript","nativeSession","currentSession","senderUrl","actualUrl","visibleUrl"}){
                  e=new JSONObject(args[0]);b=admit(p,s,e);e.put(key,key.endsWith("Session")?131059069:key.endsWith("Url")?"http://foreign.example/":false);check(current(b,p,s,e).isEmpty());
                }
                e=new JSONObject(args[0]);b=admit(p,s,e);e.getJSONObject("rawMessage").put("appearanceDocument","ffffffffffffffffffffffffffffffff");e.getJSONObject("normalizedMessage").put("appearanceDocument","ffffffffffffffffffffffffffffffff");check(current(b,p,s,e).isEmpty());
                e=new JSONObject(args[0]);e.getJSONObject("rawMessage").put("appearanceDocument","");check(admit(p,s,e)==null);
                System.out.println(checks+" exact binding controls from recorded cold message");
              }}''')
            built=subprocess.run([str(compiler),'-encoding','UTF-8','-cp',str(jar),'-d',directory,str(target)],capture_output=True,text=True,timeout=20)
            self.assertEqual(built.returncode,0,built.stderr)
            ran=subprocess.run([str(runtime),'-cp',directory+os.pathsep+str(jar),'BindingHost',json.dumps(COLD_EVIDENCE)],capture_output=True,text=True,timeout=10)
            self.assertEqual(ran.returncode,0,ran.stderr);self.assertEqual(ran.stdout.strip(),'27 exact binding controls from recorded cold message')


class SelectedSourceBindingTest(unittest.TestCase):
    def test_actual_clean_git_bytes_bind_both_new_sources_and_reject_each_tamper(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for name in (module.gate.HELPER,module.gate.CLI,module.gate.ADAPTER,module.ADAPTER,module.FIXTURE):
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,path)
            def git(*args):
                result=subprocess.run(['git','-c','core.hooksPath=/dev/null','-c','commit.gpgsign=false',*args],cwd=root,capture_output=True,text=True,timeout=10)
                self.assertEqual(result.returncode,0,result.stderr);return result.stdout.strip()
            git('init','--quiet');git('config','user.name','Host Source Fixture');git('config','user.email','host@example.invalid')
            git('add','.');git('commit','--quiet','--no-verify','-m','Local synthetic source binding')
            source=git('rev-parse','HEAD');identity=dict(sourceCommit=source,sourceTree=git('rev-parse','HEAD^{tree}'))
            binding,additional=module._sources(root,source,identity,time.monotonic()+20)
            self.assertEqual(set(additional),{module.ADAPTER,module.FIXTURE})
            self.assertEqual(additional,{name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in additional})
            for name in (module.ADAPTER,module.FIXTURE):
                path=root/name;original=path.read_bytes()
                try:
                    path.write_bytes(original+b'\nUNKNOWN SOURCE BYTES\n')
                    with self.subTest(name=name),mock.patch.object(module.gate,'_source_bindings',return_value=binding),self.assertRaises(module.gate.HeaderReadinessFailure):
                        module._sources(root,source,identity,time.monotonic()+20)
                finally:path.write_bytes(original)
                try:
                    path.unlink();path.symlink_to(ROOT/name)
                    with self.subTest(symlink=name),mock.patch.object(module.gate,'_source_bindings',return_value=binding),self.assertRaises(module.gate.HeaderReadinessFailure):
                        module._sources(root,source,identity,time.monotonic()+20)
                finally:path.unlink();path.write_bytes(original)


if __name__=='__main__':unittest.main()
