"""Browser startup reader controls using preserved run 43206522905 evidence.

The 09 ready/native JSON remains a failed real observation. Mutations below are
explicit host controls; they are never published as Android acceptance results.
The full current Java readiness overloads execute with controlled View edges.
"""
import ast
import contextlib
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools/gecko'),str(ROOT/'tests/gecko')]
import chrome_collapse_contract_v2 as contract
import chrome_resume_readiness as resume
import gecko_chrome_collapse_v2_test as previous
import profile_chrome_first_tap_readiness_test as first

FIXTURE=ROOT/'tests/fixtures/chrome-browser-cold-09.json'


def recording(): return json.loads(FIXTURE.read_text())


def address_packet(request=first.NONCE+'-1',sequence=1):
    # Controlled View coordinates, not a new device observation.
    return dict(first.packet(request,sequence),schema=2,target='address',expanded=True,
        compactVisibility=8,compactBounds=[0,72,0,72],toolbarBounds=[0,72,1080,642],
        targetBounds=[252,78,828,234],visibleBounds=[252,78,828,234],
        webBounds=[0,642,1080,1566],point=[540,156])


def address_before(): return dict(first.before(),expanded=True,compactTap=None,addressTap=[540,156])


def current_report():
    report=previous.positive();report['browserChrome']=True
    for case in report['cases']:
        case['browserChrome']=True
        case['checks']=[dict(name=name,**{'pass':True}) for name in contract.BROWSER_NAMES]
        case['legacyBehaviorMap']=[list(row) for row in contract.LEGACY_BEHAVIOR_MAP[2:]]
        case['browserStartupMap']=[list(row) for row in contract.BROWSER_STARTUP_MAP]
        case['observations']['ready']=dict(copy.deepcopy(case['observations']['initialChat']),command='ready',compactTap=None)
        case['actualAndroidInputs'][0]['point']=case['observations']['ready']['addressTap']
        case['firstTapReadiness'].update(target='address',scope='chrome-initial-address-tap-only')
        for phase,row in case['nativeUi'].items():
            raw=row['rawXml']
            if phase=='more':raw=raw.replace('会话选项','浏览器菜单')
            if phase in ('environment','drawer','network','downloads'):raw=raw.replace('会话','浏览器')
            row.update(rawXml=raw,xmlBytes=len(raw.encode()),xmlSha256=hashlib.sha256(raw.encode()).hexdigest())
    previous.reseal(report)
    return report


class AddressTransport(first.Transport):
    def checked(self,parts,deadline,**kwargs):
        result=super().checked(parts,deadline,**kwargs)
        if parts[3:6]==['shell','am','broadcast']:
            assert parts[-3:]==['--es','collapseReadinessTarget','address']
            self.current=address_packet(self.current['request'],self.current['sequence'])
        return result
    def run(self,parts,deadline,**kwargs):
        self.assert_prefix(parts);assert parts[3:]==['shell','input','tap','540','156']
        self.taps.append((parts,deadline,self.now));self.now+=self.tap_seconds
        return subprocess.CompletedProcess(parts,self.tap_exit,b'',b'')


JAVA_STUBS={
    'android/graphics/Rect.java': '''package android.graphics;public class Rect{public int left,top,right,bottom;public void offset(int x,int y){left+=x;right+=x;top+=y;bottom+=y;}}''',
    'android/view/View.java': '''package android.view;public class View{
      public int l,t,r,b,rx,ry,visibility;public boolean shown=true,laidOut=true,requested=false;
      public View(int l,int t,int r,int b){this.l=l;this.t=t;this.r=r;this.b=b;}
      public boolean getGlobalVisibleRect(android.graphics.Rect v){v.left=l;v.top=t;v.right=r;v.bottom=b;return shown;}
      public View getRootView(){return this;}public void getLocationOnScreen(int[] p){p[0]=rx;p[1]=ry;}
      public boolean isAttachedToWindow(){return true;}public boolean isShown(){return shown;}public boolean isEnabled(){return true;}
      public boolean isClickable(){return true;}public boolean isLaidOut(){return laidOut;}public boolean isLayoutRequested(){return requested;}
      public boolean hasWindowFocus(){return true;}public int getVisibility(){return visibility;}
    }''',
    'android/os/SystemClock.java':'package android.os;public class SystemClock{public static long elapsedRealtime(){return 1000;}}',
    'android/os/Process.java':'package android.os;public class Process{public static int myPid(){return 4242;}public static int myUid(){return 10209;}}',
    'android/util/Log.java':'''package android.util;public class Log{public static final java.util.ArrayList<String> lines=new java.util.ArrayList<>();public static int i(String tag,String raw){if(!tag.equals("PocketChromeInputReady"))throw new AssertionError("diagnostic tag");lines.add(raw);return 0;}}''',
}

JAVA_HOST=r'''import org.json.*;import android.view.View;import android.os.SystemClock;
final class ReadinessHost {
  static final String TARGET="https://chatgpt.com/c/reload-collapse";
  final String nonce="dddddddddddddddddddddddddddddddd";int inputReadinessSequence,activityStarts,menuOpens;
  final JSONArray nativeTouches=new JSONArray();final Host a=new Host();final Events events=new Events();final CollapseView current=new CollapseView();
  static final class J{static JSONObject obj(Object...p){JSONObject o=new JSONObject();for(int i=0;i<p.length;i+=2)o.put((String)p[i],p[i+1]);return o;}}
  static final class Events{JSONObject buildIdentity=J.obj("sourceCommit","aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","sourceTree","bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","apkSha256","cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc");}
  static final class Chrome{boolean expanded=true;View title=new View(252,78,828,234),compact=new View(0,72,0,72);Chrome(){compact.visibility=8;compact.shown=false;compact.laidOut=false;compact.requested=true;}boolean expanded(){return expanded;}}
  static final class Session{JSONObject pending=J.obj("id","controlled-pending","confirmed",true);}
  static final class Hub{int page;}
  static final class Window{View decor=new View(0,0,1080,1920);View getDecorView(){return decor;}}
  static final class Host{Chrome designChrome=new Chrome();Session session=new Session();Hub hub=new Hub();Window window=new Window();View toolbar=new View(0,72,1080,642);String packageName="local.pocketchat.test";
    String getPackageName(){return packageName;}boolean hasWindowFocus(){return true;}Window getWindow(){return window;}
    JSONArray bounds(View v){return new JSONArray(new int[]{v.l+v.rx,v.t+v.ry,v.r+v.rx,v.b+v.ry});}
    JSONArray center(View v){return new JSONArray(new int[]{(v.l+v.r)/2+v.rx,(v.t+v.b)/2+v.ry});}
    JSONArray rect(android.graphics.Rect r){return new JSONArray(new int[]{r.left,r.top,r.right,r.bottom});}
  }
  static final class InputDocumentBinding{final Object port;InputDocumentBinding(Object p){port=p;}}
  static final class Surface{final Object sdk;Surface(Object s){sdk=s;}Object getSession(){return sdk;}}
  static final class CollapseView extends View{Object current=new Object(),port=new Object();Surface surface=new Surface(current);InputDocumentBinding inputBinding=new InputDocumentBinding(port);java.util.Map<Object,Object> ports=new java.util.HashMap<>();
    CollapseView(){super(0,642,1080,1566);ports.put(current,port);}String getUrl(){return TARGET;}boolean hasVisibleDocument(){return true;}
    String inputDocument(String n,String s){return "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee";}
  }
  CollapseView web(){return current;}
__METHODS__
  static int checks;static void check(boolean value,String message){if(!value)throw new AssertionError(message);checks++;}
  static JSONObject last(){return new JSONObject(android.util.Log.lines.get(android.util.Log.lines.size()-1));}
  public static void main(String[] args){ReadinessHost h=new ReadinessHost();JSONObject pending=h.a.session.pending;h.inputReadiness(h.nonce+"-1",true);JSONObject v=last();
    check(v.getInt("schema")==2&&v.getString("target").equals("address"),"explicit address schema");
    check(v.getJSONArray("targetBounds").toString().equals("[252,78,828,234]"),"actual expanded title bounds");
    check(v.getJSONArray("point").toString().equals("[540,156]"),"actual expanded title center");
    check(v.getJSONArray("visibleBounds").toString().equals("[252,78,828,234]"),"actual target visible rectangle");
    check(v.getBoolean("shown")&&v.getBoolean("laidOut")&&!v.getBoolean("layoutRequested")&&v.getInt("compactVisibility")==8&&v.getJSONArray("compactBounds").toString().equals("[0,72,0,72]"),"hidden compact cannot supply address readiness");
    check(v.getInt("sdkSession")==v.getInt("attachedSession")&&v.getInt("documentPort")==v.getInt("currentPort")&&v.getInt("currentPort")>0,"native identity bindings");
    check(v.getInt("sequence")==1&&v.getLong("observedAtElapsedRealtime")==1000,"bounded native observation sequence");
    check(v.getString("request").equals(h.nonce+"-1")&&v.getString("sourceCommit").equals(h.events.buildIdentity.optString("sourceCommit")),"request and source identity");
    h.inputReadiness("invalid",true);check(android.util.Log.lines.size()==1,"invalid nonce ignored");
    h.a.packageName="foreign";h.inputReadiness(h.nonce+"-2",true);check(android.util.Log.lines.size()==1,"foreign package ignored");h.a.packageName="local.pocketchat.test";
    h.inputReadinessSequence=128;h.inputReadiness(h.nonce+"-2",true);check(android.util.Log.lines.size()==1,"bounded snapshot count");h.inputReadinessSequence=1;
    h.a.designChrome.title.rx=17;h.a.designChrome.title.ry=29;h.inputReadiness(h.nonce+"-2",true);v=last();
    check(v.getJSONArray("visibleBounds").toString().equals("[269,107,845,263]")&&v.getJSONArray("point").toString().equals("[557,185]"),"nonzero root origin");
    h.a.designChrome.expanded=false;View c=h.a.designChrome.compact;c.r=1080;c.b=156;c.visibility=0;c.shown=true;c.laidOut=true;c.requested=false;
    h.inputReadiness(h.nonce+"-3");v=last();check(v.getInt("schema")==1&&!v.has("target")&&!v.has("targetBounds"),"legacy overload preserves schema one");
    check(v.getJSONArray("point").toString().equals("[540,114]")&&v.getBoolean("shown")&&!v.getBoolean("expanded"),"legacy compact geometry and state");
    check(h.a.session.pending==pending&&v.getString("appearanceDocument").equals("eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee")&&v.getInt("nativeTouchCount")==0&&h.inputReadinessSequence==3,"observations do not mutate document pending or touches");
    if(checks!=15)throw new AssertionError("all full method controls must execute");System.out.println("15 actual native readiness controls");
  }
}'''


class BrowserColdStartTest(unittest.TestCase):
    def validate(self, value, initial=None, **kwargs):
        return first.module._validate_snapshot(value,source=first.SOURCE,identity=first.IDENTITY,
            nonce=first.NONCE,request=first.NONCE+'-1',owner=first.OWNER,
            before=address_before() if initial is None else initial,target='address',**kwargs)

    def test_recorded_failure_retains_actual_source_artifact_and_raw_native_identity(self):
        value=recording();p=value['provenance'];native=value['nativeObservation'];ready=value['ready']
        self.assertEqual((p['runId'],p['runAttempt'],p['artifactId'],p['artifactBytes']),(43206522905,1,13942950740,320025))
        self.assertEqual(p['artifactSha256'],'c1b2d72559e7f12f0bc8a5752167c87c4aa9f62ab3a37df2eb952cc75e3ed259')
        self.assertEqual(value['sourceCommit'],'09e3db4e9eaf9b2ca353e35479b2d1022487329b')
        self.assertEqual(native,json.loads(value['nativeLogLine'].split('PocketChromeInputReady: ',1)[1]))
        for key in ('sourceCommit','sourceTree','runNonce'):self.assertEqual(native[key],value[key])
        for key in ('surface','sdkSession','attachedSession'):self.assertEqual(native[key],ready[key])
        self.assertEqual(native['appearanceDocument'],ready['documentReadyEvidence']['rawMessage']['appearanceDocument'])
        self.assertEqual(native['pendingId'],ready['pending']['id'])
        self.assertEqual(native['documentPort'],native['currentPort']);self.assertEqual(native['schema'],1)
        self.assertFalse(native['shown']);self.assertFalse(value['releaseAcceptance'])

    def test_real_09_hidden_compact_is_rejected_by_unchanged_legacy_default(self):
        v=recording();native=v['nativeObservation'];owner=dict(pid=str(native['pid']),uid=native['uid'])
        with self.assertRaisesRegex(first.module.gate.HeaderReadinessFailure,'identity-changed'):
            first.module._validate_snapshot(native,source=v['sourceCommit'],identity=v['buildIdentity'],
                nonce=v['runNonce'],request=native['request'],owner=owner,before=v['ready'])

    def test_real_ready_requires_explicit_browser_mode_and_visible_address(self):
        ready=recording()['ready'];contract.verify_cold_start(ready,browser=True)
        self.assertEqual(ready['addressTap'],[540,156]);self.assertIsNone(ready['compactTap'])
        with self.assertRaises(AssertionError):contract.verify_cold_start(ready)
        with self.assertRaises(AssertionError):contract.verify_cold_start(ready,browser=1)

    def test_browser_cold_state_and_actual_touch_geometry_fail_closed(self):
        ready=recording()['ready']
        changes=dict(expanded=False,compactVisibility=0,topVisibility=8,compactTap=[540,156],
            addressTap=[0,0],headerButtonTouch=[0,0,10,10],networkVisibility=8,toolbarVisibility=8)
        for key,value in changes.items():
            with self.subTest(key=key),self.assertRaises(AssertionError):
                contract.verify_cold_start(dict(ready,**{key:value}),browser=True)

    def test_schema_two_address_is_explicit_and_cannot_relabel_old_schema_one(self):
        value=address_packet();self.assertEqual(self.validate(value)['point'],[540,156])
        self.assertEqual(set(value),first.module.ADDRESS_SNAPSHOT_FIELDS)
        for candidate in (dict(value,schema=1),dict(first.packet(),target='address'),first.packet()):
            with self.assertRaises(first.module.gate.HeaderReadinessFailure):self.validate(candidate)
        with self.assertRaises(first.module.gate.HeaderReadinessFailure):
            first.module._validate_snapshot(value,source=first.SOURCE,identity=first.IDENTITY,
                nonce=first.NONCE,request=first.NONCE+'-1',owner=first.OWNER,before=address_before())

    def test_address_readiness_preserves_all_source_document_port_pending_owners(self):
        changes=dict(sourceCommit='f'*40,sourceTree='f'*40,apkSha256='f'*64,runNonce='f'*32,
            request=first.NONCE+'-2',pid=4243,uid=10210,surface=21,sdkSession=22,attachedSession=22,
            appearanceDocument='f'*32,documentBinding='other',documentPort=15,currentPort=15,
            pendingId='other',pendingConfirmed=False,expanded=False,page=1,nativeTouchCount=1,
            activityStarts=1,menuOpens=1,target='compact',url='https://chatgpt.com/c/other')
        for key,value in changes.items():
            with self.subTest(key=key),self.assertRaises(first.module.gate.HeaderReadinessFailure):
                self.validate(dict(address_packet(),**{key:value}))

    def test_unknown_missing_and_type_confused_address_fields_are_rejected(self):
        original=address_packet()
        for key in original:
            value=dict(original);del value[key]
            with self.subTest(missing=key),self.assertRaises(first.module.gate.HeaderReadinessFailure):self.validate(value)
        for key,value in [('unknown',True),('schema',True),('sequence',True),('shown',1),
                          ('targetBounds',[0,0,True,200]),('point',[True,156]),('compactBounds',None)]:
            with self.subTest(key=key),self.assertRaises(first.module.gate.HeaderReadinessFailure):
                self.validate(dict(original,**{key:value}))

    def test_address_focus_layout_visibility_and_center_cannot_be_substituted(self):
        for key,value in [('shown',False),('windowFocus',False),('decorFocus',False),('attached',False),
            ('laidOut',False),('layoutRequested',True),('globallyVisible',False),('point',[541,156]),
            ('visibleBounds',[0,0,0,0]),('targetBounds',[0,72,0,72])]:
            with self.subTest(key=key):self.assertIsNone(self.validate(dict(address_packet(),**{key:value})))

    def test_actual_first_tap_uses_two_fresh_address_queries_one_input_and_original_budgets(self):
        t=AddressTransport();module=first.module
        with tempfile.TemporaryDirectory() as directory:
            out=Path(directory);binding=dict(sourceCommit=first.SOURCE,sourceTree=first.TREE,sourceSha256={'old-header':'f'*64})
            classes={'one.class':'c'*64};compiled=dict(cache=out,classes=classes,parserClassesSha256='d'*64)
            with mock.patch.object(module,'_sources',return_value=(binding,{'new-helper':'e'*64})),\
                 mock.patch.object(module.gate,'_compile_parser',return_value=(['controlled-parser'],compiled)),\
                 mock.patch.object(module.gate,'_identity',side_effect=t.identity),\
                 mock.patch.object(module.gate,'_checked',side_effect=t.checked),\
                 mock.patch.object(module.gate,'_class_hashes',return_value=classes),\
                 mock.patch.object(module.gate,'_bounded_run',side_effect=t.run),contextlib.redirect_stdout(io.StringIO()):
                result=module.first_tap_once(argv=['--adb','controlled-adb','--serial','emulator-5554'],
                    source=first.SOURCE,identity=first.IDENTITY,before=address_before(),nonce=first.NONCE,
                    out=out,root=out,clock=t.clock,sleep=t.sleep,target='address')
            self.assertEqual(result['preparationQueries'],2);self.assertEqual(len(t.taps),1)
            self.assertEqual(result['point'],[540,156]);self.assertEqual(result['target'],'address')
            self.assertTrue(all(deadline==120. for _,deadline in t.commands));self.assertEqual(t.taps[0][1],190.)
            initial=dict(first.before(),command='upBeforeResume',expanded=False,keyboard=False,
                toolbarVisibility=0,compactVisibility=0,page=0,nativeTouches=[{}, {}, {}],
                webX=0,webY=210,webWidth=1080,webHeight=1455)
            owner,snapshot,_,_=resume._original(result,source=first.SOURCE,identity=first.IDENTITY,
                nonce=first.NONCE,before=initial,binding=binding,additional={'new-helper':'e'*64},compiled=compiled)
            packet=dict(first.packet(first.NONCE+'-3',3),nativeTouchCount=3)
            geometry=resume._validate_snapshot(packet,source=first.SOURCE,identity=first.IDENTITY,
                nonce=first.NONCE,request=first.NONCE+'-3',owner=owner,initial=snapshot,before=initial)
            self.assertEqual(geometry['point'],[540,114])

    def test_complete_browser_contract_keeps_twelve_later_protections_and_eight_swipes(self):
        report=current_report();value=contract.verify_auto_collapse_v2(report,'a'*40,'c'*64)
        self.assertEqual((value['retainedLegacyProtections'],value['browserStartupProtections']),(12,2))
        self.assertEqual(value['checks'],66)
        for case in report['cases']:self.assertEqual(sum(r['kind']=='swipe' for r in case['actualAndroidInputs']),8)
        legacy=contract.verify_auto_collapse_v2(previous.positive(),'a'*40,'c'*64)
        self.assertEqual((legacy['retainedLegacyProtections'],legacy['browserStartupProtections']),(14,0))

    def test_browser_report_cannot_keep_old_startup_claims_labels_or_hidden_compact_target(self):
        changes=('names','map','point','scope','target','mode','gesture','menu')
        for change in changes:
            report=current_report();case=report['cases'][0]
            if change=='names':case['checks'][0]['name']=contract.NAMES[0]
            if change=='map':case['legacyBehaviorMap']=[list(row) for row in contract.LEGACY_BEHAVIOR_MAP]
            if change=='point':case['actualAndroidInputs'][0]['point']=[0,72]
            if change=='scope':case['firstTapReadiness']['scope']='chrome-initial-compact-tap-only'
            if change=='target':case['firstTapReadiness']['target']='compact'
            if change=='mode':case.pop('browserChrome')
            if change=='gesture':case['observations']['up']['expanded']=True;previous.reseal(report)
            if change=='menu':
                row=case['nativeUi']['more'];raw=row['rawXml'].replace('浏览器菜单','会话选项')
                row.update(rawXml=raw,xmlBytes=len(raw.encode()),xmlSha256=hashlib.sha256(raw.encode()).hexdigest())
            with self.subTest(change=change),self.assertRaises(AssertionError):contract.verify_auto_collapse_v2(report,'a'*40,'c'*64)

    def test_full_actual_java_overloads_execute_fifteen_controls_and_reject_two_compiled_target_mutations(self):
        source=(ROOT/'tests/gecko/ChromeCollapseIntegration.java').read_text()
        start=source.index('  void inputReadiness(String request)')
        methods=source[start:source.index('  /** The loopback fixture',start)]
        home=os.environ.get('JAVA_HOME_17_X64') or os.environ.get('JAVA_HOME')
        compiler=Path(home)/'bin/javac' if home else Path(shutil.which('javac') or '')
        runtime=compiler.with_name('java');jar=Path(os.environ.get('PROFILE_JSON_JAR',ROOT/'work/gecko-integration/catalog-json.jar'))
        self.assertTrue(compiler.is_file() and runtime.is_file() and jar.is_file(),'Real JDK and JSON jar required')
        variants=[('current',methods,True)]
        for name,old,new in [('wrong-view','target=address?a.designChrome.title:compact','target=compact'),
                ('wrong-bounds','value.put("target","address").put("targetBounds",a.bounds(target))',
                 'value.put("target","address").put("targetBounds",a.bounds(compact))')]:
            self.assertEqual(methods.count(old),1);variants.append((name,methods.replace(old,new,1),False))
        with tempfile.TemporaryDirectory() as directory:
            for name,body,positive in variants:
                output=Path(directory)/name;output.mkdir();files=dict(JAVA_STUBS,**{'ReadinessHost.java':JAVA_HOST.replace('__METHODS__',body)})
                for relative,text in files.items():
                    path=output/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
                result=subprocess.run([str(compiler),'-encoding','UTF-8','-cp',str(jar),'-d',str(output)]+[str(output/p) for p in files],capture_output=True,text=True,timeout=25)
                self.assertEqual(result.returncode,0,result.stderr)
                result=subprocess.run([str(runtime),'-cp',str(output)+os.pathsep+str(jar),'ReadinessHost'],capture_output=True,text=True,timeout=10)
                if positive:self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(result.stdout.strip(),'15 actual native readiness controls')
                else:self.assertNotEqual(result.returncode,0);self.assertIn('actual expanded title bounds',result.stderr)

    def test_current_android_consumer_explicitly_selects_browser_and_preserves_one_home(self):
        tree=ast.parse((ROOT/'tests/gecko/run_chrome_collapse_v2.py').read_text())
        calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name)]
        taps=[n for n in calls if n.func.id=='first_tap_once'];self.assertEqual(len(taps),1)
        self.assertEqual({k.arg:ast.unparse(k.value) for k in taps[0].keywords}['target'],"'address'")
        self.assertEqual(len([n for n in calls if n.func.id=='resume_after_home']),1)
        self.assertEqual(len([n for n in calls if n.func.id=='swipe']),7)
        self.assertEqual(len([n for n in calls if n.func.id=='header_up_once']),1)
        for call in (n for n in calls if n.func.id=='inspect_ui'):
            self.assertEqual({k.arg:ast.unparse(k.value) for k in call.keywords}['browser'],'True')
        source=(ROOT/'tests/gecko/ChromeCollapseIntegration.java').read_text()
        self.assertIn('if(target==null)inputReadiness(readiness);else if("address".equals(target))inputReadiness(readiness,true);',source)


if __name__=='__main__':unittest.main()
