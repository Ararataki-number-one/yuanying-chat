"""Window-only preparation and delivery observations on JVM boundary doubles.

No Android input, Gecko rendering, timing improvement or old-fault fix is claimed.
"""
import hashlib,json,os
from pathlib import Path
import shutil,subprocess,tempfile,unittest
from unittest.mock import patch
import window_tap_readiness_contract as contract
from reading_zoom_trace_contract import original_reading_fixture_bytes

ROOT=Path(__file__).resolve().parents[1]
FIXTURE=contract.FIXTURE
HELPER='tests/gecko/GeckoWindowTapReadiness.java'
PINS={'desktop':'3ea61b2a06e31edf1c91134fe9106b0ebb16628be169f3db75bc7a2b06b45796','android-json':'dfb7bae2f404cfe0b72b4d23944698cb716b7665171812a0a4d0f5926c0fac79'}

def digest(raw):return hashlib.sha256(raw).hexdigest()
def member(text,needle):
 start=text.index(needle);opening=text.index('{',start);level=0
 for i in range(opening,len(text)):
  if text[i]=='{':level+=1
  elif text[i]=='}':
   level-=1
   if level==0:return text[start:i+1]
 raise ValueError('Unclosed controlled member')

class WindowTapReadinessTest(unittest.TestCase):
 def test_exact_inverse_preserves_whole37_then_original_reading_fixture(self):
  current=(ROOT/FIXTURE).read_bytes();original=contract.strip_reviewed_window_additions(current)
  self.assertEqual(digest(original),'6581b1d35024ce6edcf829575104e5dd3464ebfe20280e1a49d1c4b468325b39')
  self.assertEqual(digest(original_reading_fixture_bytes(current,FIXTURE)),'7d6cc589a2718f629568205c79c290ef713d745b05a62a700a72451846c8d814')
  for signature,value in [('  void windowFlow(long serial){','b1d04434e25942ccfe9cbdcc07b1ca8d8bed74b95819e9862d3247632a872025'),('  void waitWindow(long serial,String step,long deadline,Runnable done){','f22b0cc0a85ee465effb713874f6975fd5a64e963409d3a72bdfea141c714bea'),('  void tapElement(long serial,String id){','4af23acb9cb582a4085ae8bd3e1b2981c12a705273ab1b4de3c15ee7f9ca0639')]:
   self.assertEqual(digest(member(original.decode(),signature).encode()),value)
  self.assertEqual(member(current.decode(),'  void waitWindow(long serial,String step,long deadline,Runnable done){'),member(original.decode(),'  void waitWindow(long serial,String step,long deadline,Runnable done){'))
  flow=member(current.decode(),'  void windowFlow(long serial){');self.assertEqual(flow.count('windowDeadline=SystemClock.elapsedRealtime()+15000'),1);self.assertIn('waitWindow(serial,"three",windowDeadline,()->{',flow)
  self.assertNotIn('tapElement(serial,"popup");',flow)
 def test_missing_changed_duplicated_and_relocated_window_changes_are_rejected(self):
  source=(ROOT/FIXTURE).read_text()
  for item in contract.window_manifest()['changes']:
   added=item.get('inserted',item.get('replacement'));old=item.get('original','');literal=item['before']+added+item['after'];prior=item['before']+old+item['after']
   mutants=[source.replace(literal,prior,1),source.replace(literal,item['before']+added*2+item['after'],1),source.replace(literal,item['before']+added+' '+item['after'],1),source.replace(literal,prior,1)+added]
   for i,value in enumerate(mutants):
    with self.subTest(change=item['id'],kind=i),self.assertRaises(ValueError):contract.strip_reviewed_window_additions(value.encode())
 def test_original_deadline_oracle_and_coordinate_changes_are_not_whitelisted(self):
  source=(ROOT/FIXTURE).read_text()
  for old,new in [('windowDeadline=SystemClock.elapsedRealtime()+15000','windowDeadline=SystemClock.elapsedRealtime()+15001'),('JSONObject.quote(step).equals(raw)&&','true&&'),('if(web.current==parent||web.popups.size()!=1)','if(false)'),('"realPopup",true','"realPopup",false'),('rect.optDouble("x")-rect.optDouble("left")','rect.optDouble("x")+rect.optDouble("left")'),('Math.abs(relative-4.2)<.05','Math.abs(relative-4.2)<.06')]:
   self.assertIn(old,source)
   with self.subTest(mutation=old),self.assertRaises(ValueError):contract.strip_reviewed_window_additions(source.replace(old,new,1).encode())
 def test_manifest_and_external_helper_are_both_bound(self):
  raw=(ROOT/'tests/fixtures/window-tap-readiness-additions.json').read_bytes();helper=(ROOT/HELPER).read_bytes()
  for path,data in [('tests/fixtures/window-tap-readiness-additions.json',raw+b' '),(HELPER,helper.replace(b'polls==256',b'polls==257',1)),(HELPER,helper.replace(b'15000',b'15001',1))]:
   self.assertNotEqual(data,raw if path.endswith('.json') else helper)
   with tempfile.TemporaryDirectory(prefix='window-contract-negative-') as name:
    base=Path(name)
    for relative,value in [('tests/fixtures/window-tap-readiness-additions.json',raw),(HELPER,helper)]:
     p=base/relative;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(value)
    (base/path).write_bytes(data)
    with patch.object(contract,'ROOT',base),self.assertRaises(ValueError):contract.window_manifest()
 def test_old_contract_body_runner_and_other_actions_are_preserved(self):
  added=" if path=='tests/gecko/GeckoIntegrationTestActivity.java':\n  from window_tap_readiness_contract import strip_reviewed_window_additions\n  raw=strip_reviewed_window_additions(raw)\n"
  current=(ROOT/'tests/reading_zoom_trace_contract.py').read_text();self.assertEqual(current.count(added),1)
  self.assertEqual(digest(current.replace(added,'',1).encode()),'2ad6c04e7d6fa27b84ae432039a079b887f673ac1d99474dd4441721f12918cd')
  self.assertEqual(digest((ROOT/'tests/gecko/run_device.py').read_bytes()),'54fa412be9f89e46d61597caf61b0246e451e6c9b5eebca592e36b05686ab8a6')
  self.assertEqual(digest((ROOT/'.github/workflows/gecko-integration.yml').read_bytes()),'10e35f9884e6eac2ea2fc2e0e6d6f6d5d14c55dc7e776cd0128019c75ab3f2f5')
  fixture=(ROOT/FIXTURE).read_text();old=contract.strip_reviewed_window_additions(fixture.encode()).decode()
  self.assertEqual(fixture.count('evaluateJavascript('),old.count('evaluateJavascript('));self.assertEqual(fixture.count('postDelayed('),old.count('postDelayed('))
  dispatch=member(fixture,'    @Override public boolean dispatchTouchEvent(android.view.MotionEvent event){');self.assertEqual(dispatch.count('super.dispatchTouchEvent(event)'),1);self.assertIn('return handled;',dispatch)
  helper=(ROOT/HELPER).read_text()
  for denied in ('input tap','window.open(','.click(','.loadUrl(','.setActive(','.setBlocked(','.setNavigationDelegate('):self.assertNotIn(denied,helper)
  self.assertEqual(helper.count('activity.tapElement(serial,"popup");'),1)
 def test_actual_helper_and_fixture_boundaries_on_both_json_runtimes(self):
  fixture=(ROOT/FIXTURE).read_text();tap=member(fixture,'  void tapElement(long serial,String id){');dispatch=member(fixture,'    @Override public boolean dispatchTouchEvent(android.view.MotionEvent event){')
  sources={HELPER:(ROOT/HELPER).read_bytes(),'tests/gecko/GeckoIntegrationTestActivity.java':(ROOT/FIXTURE).read_bytes(),'app/src/main/java/local/pocketchat/J.java':(ROOT/'app/src/main/java/local/pocketchat/J.java').read_bytes(),str(Path(__file__).relative_to(ROOT)):Path(__file__).read_bytes()}
  before={p:digest(raw) for p,raw in sources.items()};java=os.environ.get('PROFILE_JAVA') or shutil.which('java');self.assertTrue(java,'JDK17 required');runs=[]
  for runtime,filename in [('desktop','json.jar'),('android-json','android-json.jar')]:
   jar=ROOT/'work/profile-host'/filename;self.assertTrue(jar.is_file());self.assertEqual(digest(jar.read_bytes()),PINS[runtime])
   with tempfile.TemporaryDirectory(prefix='window-readiness-host-') as name:
    base=Path(name)
    for relative,data in [('local/pocketchat/GeckoWindowTapReadiness.java',sources[HELPER]),('local/pocketchat/J.java',sources['app/src/main/java/local/pocketchat/J.java']),('local/pocketchat/WindowReadinessHost.java',HOST.replace('/*TAP*/',tap).replace('/*DISPATCH*/',dispatch).encode()),('android/os/SystemClock.java',CLOCK.encode()),('android/view/MotionEvent.java',MOTION.encode()),('org/mozilla/geckoview/GeckoSession.java',SESSION.encode()),('android/webkit/ValueCallback.java',CALLBACK.encode())]:
     path=base/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
    compiled=subprocess.run([java,'-m','jdk.compiler/com.sun.tools.javac.Main','--release','8','-encoding','UTF-8','-cp',str(jar),'-d',str(base),*map(str,base.rglob('*.java'))],capture_output=True,text=True,timeout=45);self.assertEqual(compiled.returncode,0,compiled.stdout+compiled.stderr)
    result=subprocess.run([java,'-cp',str(base)+os.pathsep+str(jar),'local.pocketchat.WindowReadinessHost'],capture_output=True,text=True,timeout=30);self.assertEqual(result.returncode,0,result.stdout+result.stderr);report=json.loads(result.stdout);self.assertEqual(report['checks'],report['passed']);self.assertGreaterEqual(report['checks'],50);runs.append({'runtime':runtime,'jsonSha256':PINS[runtime],'report':report,'compileStdout':compiled.stdout,'compileStderr':compiled.stderr})
  self.assertEqual(before,{p:digest((ROOT/p).read_bytes()) for p in before})
  out=ROOT/'work/window-tap-readiness/host-results.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps({'schema':1,'status':'passed','sourceSha256':before,'runs':runs,'actualAndroidExecution':False,'actualGeckoExecution':False,'nativeInputInjected':False,'releaseAcceptance':False,'physicalPhoneAcceptance':False,'scope':'Actual test helper plus extracted real tapElement/dispatch methods on declared JVM doubles; no claim that the previous Android failure is fixed.'},indent=2)+'\n')

CLOCK='''package android.os; public final class SystemClock {public static long now=1000;public static int calls;public static long elapsedRealtime(){calls++;return now;}}'''
MOTION='''package android.view; public final class MotionEvent {public static final int ACTION_DOWN=0,ACTION_UP=1,ACTION_MOVE=2;final int action;final float x,y;public MotionEvent(int a,float x,float y){action=a;this.x=x;this.y=y;}public int getActionMasked(){return action;}public float getRawX(){return x;}public float getRawY(){return y;}}'''
SESSION='''package org.mozilla.geckoview; public final class GeckoSession {public boolean open=true;public boolean isOpen(){return open;}}'''
CALLBACK='''package android.webkit; public interface ValueCallback<T> {void onReceiveValue(T value);}'''
HOST=r'''package local.pocketchat;
import java.util.*;import org.json.*;import android.os.SystemClock;import android.view.MotionEvent;import org.mozilla.geckoview.GeckoSession;
public final class WindowReadinessHost {
 static int checks;static void check(boolean value,String name){checks++;if(!value)throw new AssertionError(name);}
 static GeckoIntegrationTestActivity fresh(){SystemClock.now=1000;return new GeckoIntegrationTestActivity();}
 static GeckoWindowTapReadiness begin(GeckoIntegrationTestActivity a){GeckoWindowTapReadiness.begin(a,a.run,a.session.web.current,SystemClock.now+15000);return a.session.web.windowTapReadiness;}
 static void deliver(GeckoIntegrationTestActivity a){a.session.web.deliver("{\"x\":12,\"y\":14,\"pixels\":1,\"left\":0,\"top\":0}");}
 static int taps(GeckoIntegrationTestActivity a){return a.events.size();}
 static void finalExcluded(String label,java.util.function.Consumer<GeckoIntegrationTestActivity> change){GeckoIntegrationTestActivity a=fresh();GeckoWindowTapReadiness g=begin(a);a.session.web.surface.originHook=()->change.accept(a);deliver(a);check(taps(a)==0,label+" cannot emit after bounds");}
 static void excluded(String label,java.util.function.Consumer<GeckoIntegrationTestActivity> change){GeckoIntegrationTestActivity a=fresh();GeckoWindowTapReadiness g=begin(a);check(a.session.web.evaluations==1,label+" begins one bounds read");android.webkit.ValueCallback<String> callback=a.session.web.callback;change.accept(a);callback.onReceiveValue("{\"x\":12,\"y\":14,\"pixels\":1,\"left\":0,\"top\":0}");check(taps(a)==0,label+" cannot emit");g.poll();check(g.retired,label+" retires");}
 public static void main(String[]args)throws Exception{
  GeckoIntegrationTestActivity a=fresh();a.focus=false;GeckoWindowTapReadiness g=begin(a);check(a.session.web.evaluations==0&&taps(a)==0,"activity focus false prepares no bounds or tap");a.focus=true;a.session.handler.next();check(a.session.web.evaluations==1&&taps(a)==0,"actual focus true prepares one async bounds");deliver(a);check(taps(a)==1&&g.tapEmitted,"ready actual callback emits once");g.poll();deliver(a);check(taps(a)==1&&a.session.web.evaluations==1,"duplicate callback and poll cannot emit again");
  JSONObject meta=a.events.get(0).getJSONObject("windowTapReadiness");check(meta.getBoolean("beforeBoundsReady")&&meta.getBoolean("afterBoundsReady")&&meta.getBoolean("sameOwner")&&meta.getBoolean("samePort")&&meta.getBoolean("sameDocument"),"event binds before after and identity");check(meta.getBoolean("preEmitOnly")&&!meta.getBoolean("injectionFocusGuaranteed")&&!meta.getBoolean("upIsDomClick"),"focus limitations explicit");
  for(int field=0;field<8;field++){a=fresh();final int f=field;if(f==0)a.focus=false;if(f==1)a.session.web.focus=false;if(f==2)a.session.web.shown=false;if(f==3)a.session.web.attached=false;if(f==4)a.session.web.surface.focus=false;if(f==5)a.session.web.surface.shown=false;if(f==6)a.session.web.surface.attached=false;if(f==7)a.session.browserPaused=true;g=begin(a);check(a.session.web.evaluations==0&&taps(a)==0,"every focus visibility attachment gate waits "+f);a.focus=a.session.web.focus=a.session.web.shown=a.session.web.attached=a.session.web.surface.focus=a.session.web.surface.shown=a.session.web.surface.attached=true;a.session.browserPaused=false;a.session.handler.next();deliver(a);check(taps(a)==1,"ready transition emits once "+f);}
  a=fresh();g=begin(a);a.focus=false;deliver(a);check(taps(a)==0&&!g.tapEmitted&&!g.retired,"async focus loss suppresses tap");a.focus=true;a.session.handler.next();deliver(a);check(taps(a)==1&&g.boundsRequests==2,"regained focus retries preparation only before first tap");
  a=fresh();g=begin(a);final GeckoIntegrationTestActivity late=a;a.session.web.surface.originHook=()->SystemClock.now=16000;deliver(a);check(taps(a)==0&&g.retired,"deadline reached between accepted bounds and final emit blocks tap");
  a=fresh();g=begin(a);a.session.web.surface.originHook=()->lateNoop();final GeckoIntegrationTestActivity focusDrop=a;a.session.web.surface.originHook=()->focusDrop.focus=false;deliver(a);check(taps(a)==0&&!g.tapEmitted&&!g.retired,"final preemit focus loss blocks tap");a.focus=true;a.session.handler.next();deliver(a);check(taps(a)==1,"final focus wait shares original deadline and emits once");
  a=fresh();g=begin(a);final GeckoIntegrationTestActivity docDrop=a;a.session.web.surface.originHook=()->docDrop.session.web.appearanceLoads.put(docDrop.session.web.current,9L);deliver(a);check(taps(a)==0&&g.retired,"document changes after bounds before emit are rejected");
  a=fresh();g=begin(a);final GeckoIntegrationTestActivity nativeDrop=a;a.session.web.surface.originHook=()->nativeDrop.session.web.current=new GeckoSession();deliver(a);check(taps(a)==0&&g.retired,"native owner changes after bounds before emit are rejected");
  finalExcluded("final Activity.session replacement",v->v.session=new ChatSession());finalExcluded("final web replacement",v->v.session.web=new GeckoIntegrationTestActivity.FixtureView(ignored->{}));finalExcluded("final helper cleared",v->v.session.web.windowTapReadiness=null);finalExcluded("final helper foreign serial",v->{GeckoIntegrationTestActivity other=fresh();v.session.web.windowTapReadiness=new GeckoWindowTapReadiness(other,8,other.session.web.current,16000);});
  excluded("stale run",v->v.run++);excluded("stale native session",v->v.session.web.current=new GeckoSession());excluded("closed native session",v->v.session.web.current.open=false);excluded("surface session",v->v.session.web.surface.session=new GeckoSession());excluded("stale port",v->v.session.web.ports.put(v.session.web.current,new Object()));excluded("sameurl newload",v->v.session.web.appearanceLoads.put(v.session.web.current,4L));excluded("pending load",v->v.session.web.pendingLoads.add(v.session.web.current));excluded("paint retired",v->v.session.web.painted.clear());excluded("actual URL",v->v.session.web.url="http://127.0.0.1:8765/browser-window?step=four&command=7");excluded("location map",v->v.session.web.locations.put(v.session.web.current,"foreign"));excluded("navigation",v->v.session.navigationEpoch++);excluded("connection",v->v.session.connectionEpoch++);excluded("deleted",v->v.session.deleted=true);excluded("destroyed",v->v.destroyed=true);excluded("finishing",v->v.finishing=true);excluded("new action",v->v.action="read");excluded("owner replaced",v->v.session=new ChatSession());excluded("view replaced",v->v.session.web=new GeckoIntegrationTestActivity.FixtureView(ignored->{}));excluded("old helper replaced",v->v.session.web.windowTapReadiness=null);excluded("exact deadline",v->SystemClock.now=16000);excluded("past deadline",v->SystemClock.now=16001);
  a=fresh();a.focus=false;g=begin(a);int waits=0;while(!a.session.handler.tasks.isEmpty()&&waits++<200)a.session.handler.next();check(g.retired&&SystemClock.now==16000&&taps(a)==0&&a.session.web.evaluations==0,"never ready exhausts same15s without native request");check(waits<=151,"polling is bounded by original deadline");
  a=fresh();GeckoWindowTapReadiness.begin(a,a.run,a.session.web.current,1000);check(taps(a)==0&&a.session.web.evaluations==0&&a.session.web.windowTapReadiness.retired,"already expired preparation cannot emit");
  a=fresh();a.session.web.appearanceLoads.put(a.session.web.current,0L);g=begin(a);check(g.retired&&a.session.web.evaluations==0,"missing document generation cannot prepare");
  a=fresh();g=begin(a);deliver(a);int clocks=SystemClock.calls;a.focus=false;a.session.web.superHandled=false;boolean downResult=a.session.web.dispatchTouchEvent(new MotionEvent(0,112,214));check(!downResult&&a.session.web.dispatchCalls==1&&g.down==1&&g.downForwarded==1&&!g.downHandled&&!g.downActivityFocused,"delivered down observes falsefocus and original superfalse once");a.focus=true;a.session.web.superHandled=true;boolean upResult=a.session.web.dispatchTouchEvent(new MotionEvent(1,112,214));check(upResult&&a.session.web.dispatchCalls==2&&g.up==1&&g.upForwarded==1&&g.upHandled&&g.upActivityFocused,"delivered up forwards true once without DOMclaim");a.event(a.run,"error",J.obj("error","synthetic"));JSONObject finalMeta=a.last.getJSONObject("windowTapReadiness");check(finalMeta.getInt("nativeDown")==1&&finalMeta.getInt("nativeUp")==1&&!finalMeta.getBoolean("upIsDomClick"),"terminal existing event carries bounded delivered evidence");check(finalMeta.toString().length()<2000,"readiness numeric metadata bounded");for(Iterator<String> keys=finalMeta.keys();keys.hasNext();){Object value=finalMeta.get(keys.next());check(value instanceof Number||value instanceof Boolean,"metadata only numbers and booleans");}
  SystemClock.now=3500;a.event(a.run,"error",J.obj("error","later synthetic"));JSONObject aged=a.last.getJSONObject("windowTapReadiness");check(aged.getLong("elapsedMs")==2500&&aged.getLong("remainingMs")==12500&&aged.getLong("lastSampleAgeMs")==2500&&aged.getBoolean("focusSampleCached"),"terminal clock and explicit cached sample age remain truthful");
  int observed=g.down+g.up;a.session.web.dispatchTouchEvent(new MotionEvent(2,112,214));a.session.web.dispatchTouchEvent(new MotionEvent(0,130,214));a.session.web.dispatchTouchEvent(new MotionEvent(0,Float.NaN,214));check(g.down+g.up==observed&&a.session.web.dispatchCalls==5,"move wrongpoint nonfinite input not reported as matching delivery");
  for(int i=0;i<12;i++)a.session.web.dispatchTouchEvent(new MotionEvent(0,112,214));check(g.down==8&&g.downForwarded==8&&g.overflow,"delivery counters saturate and disclose overflow");check(taps(a)==1,"touch observation never generates additional tap");a.session.web.ports.put(a.session.web.current,new Object());a.session.web.dispatchTouchEvent(new MotionEvent(1,112,214));check(g.retired&&g.up==1,"stale delivery cannot contaminate window evidence");
  a=fresh();a.action="usability";a.tapElement(a.run,"upload");deliver(a);check(taps(a)==1&&!a.events.get(0).has("windowTapReadiness"),"other element path original event unchanged");clocks=SystemClock.calls;a.session.web.superHandled=false;check(!a.session.web.dispatchTouchEvent(new MotionEvent(0,112,214))&&a.session.web.dispatchCalls==1&&SystemClock.calls==clocks,"inactive observer preserves return and no observation clocks");
  a=fresh();g=begin(a);deliver(a);a.run++;a.action="read";a.event(a.run,"tapNeeded",J.obj("id","upload-8","x",1,"y",2));check(g.retired&&!a.last.has("windowTapReadiness"),"newcase retires old observer without changing new event");
  System.out.println(J.obj("status","passed","checks",checks,"passed",checks,"actualAndroidExecution",false,"actualGeckoExecution",false,"nativeInputInjected",false,"releaseAcceptance",false));
 }
 static void lateNoop(){}
}
class GeckoIntegrationTestActivity {
 long run=7;String action="windows";ChatSession session=new ChatSession();boolean focus=true,destroyed,finishing;final List<JSONObject> events=new ArrayList<>();JSONObject last;
 boolean hasWindowFocus(){return focus;}boolean isDestroyed(){return destroyed;}boolean isFinishing(){return finishing;}
 String windowUrl(String step,long serial){return "http://127.0.0.1:8765/browser-window?step="+step+"&command="+serial;}
 void event(long serial,String kind,JSONObject result){if(serial!=run)return;if(!GeckoWindowTapReadiness.beforeEvent(this,serial,kind,result))return;last=result;if("tapNeeded".equals(kind))events.add(J.parse(result.toString()));}
 /*TAP*/
 static final class FixtureView extends GeckoWebView {
  GeckoWindowTapReadiness windowTapReadiness;boolean nativeGeometryActive,nativeGeometrySwipes,nativeGeometryStable;NativeGeometry nativeGeometryPrevious,nativeGeometryExpected;long nativeUnchangedTouchEvents,nativeRedundantTouchSyncs,nativeFirstTouchSyncs=-1;boolean nativeFirstTouchOriginCorrect;Runnable nativeGestureComplete;int nativeGestureCount;
  FixtureView(java.util.function.Consumer<Object> ignored){super();}
  long nativeSyncs(){return 0;}void recordNativeGeometry(String label,NativeGeometry before,NativeGeometry after,long delta,boolean cached){}
  /*DISPATCH*/
 }
}
class ChatSession {GeckoIntegrationTestActivity.FixtureView web;long navigationEpoch=3,connectionEpoch=2;boolean deleted,browserPaused;final Handler handler=new Handler();ChatSession(){web=new GeckoIntegrationTestActivity.FixtureView(v->{});web.owner=this;}}
class Handler {
 final List<Runnable> tasks=new ArrayList<>();final List<Long> times=new ArrayList<>();void postDelayed(Runnable task,long delay){tasks.add(task);times.add(SystemClock.now+delay);}void post(Runnable task){postDelayed(task,0);}void next(){if(tasks.isEmpty())throw new AssertionError("Missing bounded wait");Runnable task=tasks.remove(0);SystemClock.now=Math.max(SystemClock.now,times.remove(0));task.run();}
}
class GeckoWebView {
 ChatSession owner;GeckoSession current=new GeckoSession();final Map<GeckoSession,Object> ports=new IdentityHashMap<>();final Map<GeckoSession,Long> appearanceLoads=new IdentityHashMap<>();final Map<GeckoSession,String> locations=new IdentityHashMap<>();final Set<GeckoSession> pendingLoads=Collections.newSetFromMap(new IdentityHashMap<>()),painted=Collections.newSetFromMap(new IdentityHashMap<>());final Surface surface=new Surface();String url="http://127.0.0.1:8765/browser-window?step=two&command=7";boolean focus=true,shown=true,attached=true,superHandled=true;float readingLayout=1;int evaluations,dispatchCalls;android.webkit.ValueCallback<String> callback;
 GeckoWebView(){ports.put(current,new Object());appearanceLoads.put(current,3L);locations.put(current,url);painted.add(current);surface.session=current;}
 String getUrl(){return url;}boolean hasWindowFocus(){return focus;}boolean isShown(){return shown;}boolean isAttachedToWindow(){return attached;}int getWidth(){return 1080;}int getHeight(){return 1800;}float getScale(){return 1;}
 void evaluateJavascript(String code,android.webkit.ValueCallback<String> result){evaluations++;callback=result;}void deliver(String value){if(callback!=null)callback.onReceiveValue(value);}boolean dispatchTouchEvent(MotionEvent value){dispatchCalls++;return superHandled;}
}
class Surface {GeckoSession session;boolean focus=true,shown=true,attached=true;Runnable originHook;GeckoSession getSession(){return session;}boolean hasWindowFocus(){return focus;}boolean isShown(){return shown;}boolean isAttachedToWindow(){return attached;}void getLocationOnScreen(int[] value){if(originHook!=null){Runnable hook=originHook;originHook=null;hook.run();}value[0]=100;value[1]=200;}}
class NativeGeometry {static NativeGeometry read(Object value){return null;}static boolean cacheMatches(Object value,NativeGeometry before){return false;}boolean same(NativeGeometry other){return true;}}
class NetworkCatalog {static void put(JSONObject value,String name,Object item){try{value.put(name,item);}catch(JSONException error){throw new IllegalStateException(error);}}}
'''
if __name__=='__main__':unittest.main()
