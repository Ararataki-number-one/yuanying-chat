"""Compile the real photo-only tap helper on explicit JVM boundary doubles.

These controls verify coordinate arithmetic, freshness and one-event ownership;
they do not claim Android input delivery or Gecko photo permission success.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT/'tests/gecko/GeckoPhotoTap.java'

STUBS = {
    'android/os/SystemClock.java': '''package android.os; public final class SystemClock {
      public static long now=1000;public static long elapsedRealtime(){return now;}}
    ''',
    'android/webkit/ValueCallback.java': '''package android.webkit; public interface ValueCallback<T>{void onReceiveValue(T value);}''',
    'android/graphics/Matrix.java': '''package android.graphics; public final class Matrix {
      private float[] values={1,0,0,0,1,0,0,0,1};
      public void setValues(float[] v){values=v.clone();}public void getValues(float[] v){System.arraycopy(values,0,v,0,9);}
      public void mapPoints(float[] points){for(int i=0;i<points.length;i+=2){float x=points[i],y=points[i+1];float d=values[6]*x+values[7]*y+values[8];points[i]=(values[0]*x+values[1]*y+values[2])/d;points[i+1]=(values[3]*x+values[4]*y+values[5])/d;}}
    }''',
    'org/mozilla/geckoview/GeckoSession.java': '''package org.mozilla.geckoview; public final class GeckoSession {
      public boolean open=true;public float[] matrix={2.6086957f,0,0,0,2.6086957f,0,0,0,1};public Runnable matrixHook;
      public boolean isOpen(){return open;}public void getClientToSurfaceMatrix(android.graphics.Matrix m){m.setValues(matrix);if(matrixHook!=null){Runnable h=matrixHook;matrixHook=null;h.run();}}
    }''',
    'org/mozilla/geckoview/GeckoView.java': '''package org.mozilla.geckoview; public final class GeckoView {
      public GeckoSession session;public int width=1080,height=1795,x=0,y=125;public boolean focused=true,shown=true,attached=true;public Runnable originHook;
      public GeckoSession getSession(){return session;}public int getWidth(){return width;}public int getHeight(){return height;}
      public boolean hasWindowFocus(){return focused;}public boolean isShown(){return shown;}public boolean isAttachedToWindow(){return attached;}
      public void getLocationOnScreen(int[] o){o[0]=x;o[1]=y;if(originHook!=null){Runnable h=originHook;originHook=null;h.run();}}
    }''',
}

HOST = r'''package local.pocketchat;
import org.json.*;import java.util.*;import android.os.SystemClock;import org.mozilla.geckoview.*;
public final class PhotoTapHost {
  static int checks;
  static void check(boolean value,String label){checks++;if(!value)throw new AssertionError(label);}
  static GeckoIntegrationTestActivity fresh(){SystemClock.now=1000;return new GeckoIntegrationTestActivity();}
  static GeckoPhotoTap begin(GeckoIntegrationTestActivity a){GeckoPhotoTap g=new GeckoPhotoTap(a,5,a.session.web.url,26000);g.poll();return g;}
  static JSONObject rect(GeckoIntegrationTestActivity a){return J.obj("url",a.session.web.url,"runNonce",a.eventStore.nonce,"command",5,"mode","select","document",1000000,
    "ready",true,"ownedTarget",true,"visible",true,"left",8,"right",238,"top",127.4,"bottom",150.6,
    "viewportLeft",0,"viewportTop",0,"viewportWidth",414,"viewportHeight",688.0833,"pageDpr",2,"pageScale",1);}
  static void deliver(GeckoIntegrationTestActivity a,JSONObject value){check(a.session.web.callback!=null,"pending DOM callback");a.session.web.callback.onReceiveValue(value.toString());}
  static void stable(GeckoIntegrationTestActivity a){deliver(a,rect(a));a.session.handler.next();deliver(a,rect(a));}
  static void excluded(String label,java.util.function.Consumer<GeckoIntegrationTestActivity> mutate){
    GeckoIntegrationTestActivity a=fresh();GeckoPhotoTap g=begin(a);JSONObject r=rect(a);android.webkit.ValueCallback<String> pending=a.session.web.callback;mutate.accept(a);pending.onReceiveValue(r.toString());g.poll();check(a.events.isEmpty()&&g.retired,label+" retires before input");
  }
  static void invalid(String key,Object value){GeckoIntegrationTestActivity a=fresh();GeckoPhotoTap g=begin(a);JSONObject r=rect(a);NetworkCatalog.put(r,key,value);deliver(a,r);check(a.events.isEmpty()&&!g.emitted,"invalid rect "+key);}
  public static void main(String[] args)throws Exception{
    GeckoIntegrationTestActivity a=fresh();GeckoPhotoTap g=begin(a);stable(a);
    check(a.events.size()==1&&g.emitted,"two stable samples emit one tap");JSONObject tap=a.events.get(0),e=tap.getJSONObject("photoTap");
    check(tap.getInt("x")==321&&tap.getInt("y")==488,"actual C6 native 2.6086957 transform");
    check(246<621&&246>21&&403<457,"old C6 masked-DPR point misses original AX input");
    check(tap.getInt("x")>21&&tap.getInt("x")<621&&tap.getInt("y")>457&&tap.getInt("y")<518,"new point inside original C6 AX input");
    check(e.getJSONObject("client").getDouble("pageDpr")==2&&e.getJSONObject("geometry").getJSONArray("clientToSurface").getDouble(0)>2.6,"raw masked DPR and actual matrix both retained");
    check(e.getString("target").equals(a.session.web.url)&&e.getString("runNonce").equals(a.eventStore.nonce)&&e.getLong("load")==4&&e.getLong("command")==5,"owned invocation receipt");
    check(e.getBoolean("preEmitOnly")&&!e.getBoolean("injectionFocusGuaranteed")&&e.getLong("originalBudgetMs")==25000,"budget and observation limits");
    deliver(a,rect(a));g.poll();check(a.events.size()==1,"duplicate callback and polls cannot retap");
    a=fresh();g=begin(a);JSONObject r=rect(a);NetworkCatalog.put(r,"pageDpr",10);NetworkCatalog.put(r,"pageScale",99);deliver(a,r);a.session.handler.next();deliver(a,r);
    check(a.events.size()==1&&a.events.get(0).getInt("x")==321&&a.events.get(0).getInt("y")==488,"page identity masks cannot drive native coordinates");
    a=fresh();a.session.web.current.matrix[5]=11;g=begin(a);r=rect(a);
    for(String key:new String[]{"left","right"})NetworkCatalog.put(r,key,r.optDouble(key)+37);
    for(String key:new String[]{"top","bottom"})NetworkCatalog.put(r,key,r.optDouble(key)+23);
    NetworkCatalog.put(r,"viewportLeft",37);NetworkCatalog.put(r,"viewportTop",23);NetworkCatalog.put(r,"scrollX",900);NetworkCatalog.put(r,"scrollY",1700);
    deliver(a,r);a.session.handler.next();deliver(a,r);check(a.events.size()==1&&a.events.get(0).getInt("x")==321&&a.events.get(0).getInt("y")==499,"visual offset once then native client-top translation; no page-scroll double offset");
    a=fresh();a.session.web.height=1732;g=begin(a);stable(a);check(a.events.size()==1,"clipped AX viewport height need not equal raw native surface height");
    a=fresh();a.session.web.current.matrix[0]=a.session.web.current.matrix[4]=2;g=begin(a);deliver(a,rect(a));check(a.events.isEmpty(),"stable stale previous matrix fails viewport/surface agreement");
    a.session.web.current.matrix[0]=a.session.web.current.matrix[4]=2.6086957f;a.session.handler.next();stable(a);check(a.events.size()==1,"current compositor then emits inside original budget");
    a=fresh();g=begin(a);a.session.web.current.matrix[5]=20;deliver(a,rect(a));check(a.events.isEmpty(),"matrix change across async DOM read suppresses tap");
    a=fresh();g=begin(a);a.session.web.surface.x=50;deliver(a,rect(a));check(a.events.isEmpty(),"surface origin change across DOM read suppresses tap");
    a=fresh();g=begin(a);deliver(a,rect(a));a.session.handler.next();r=rect(a);NetworkCatalog.put(r,"document",2000000);deliver(a,r);check(a.events.isEmpty(),"same URL new DOM does not inherit prior stable sample");
    a=fresh();a.session.web.readingLayout=.5f;a.session.web.width=540;a.session.web.height=898;a.session.web.surface.x=17;g=begin(a);stable(a);
    check(a.events.get(0).getInt("x")==177&&a.events.get(0).getInt("y")==306,"native origin plus readingLayout applied exactly once");
    for(int i=0;i<9;i++){a=fresh();a.session.web.current.matrix[i]=Float.NaN;g=begin(a);check(a.events.isEmpty()&&a.session.web.evaluations==0,"nonfinite native matrix "+i);}
    for(float[] m:new float[][]{{0,0,0,0,0,0,0,0,1},{-1,0,0,0,-1,0,0,0,1},{2,1,0,0,2,0,0,0,1},{2,0,0,0,2,0,1,0,1},{2.6086957f,0,1080,0,2.6086957f,0,0,0,1}}){
      a=fresh();a.session.web.current.matrix=m;g=begin(a);if(a.session.web.callback!=null)deliver(a,rect(a));check(a.events.isEmpty(),"degenerate or out of bounds native matrix");
    }
    for(String key:new String[]{"left","top","right","bottom","viewportLeft","viewportTop","viewportWidth","viewportHeight","document"})invalid(key,JSONObject.NULL);
    invalid("right",8);invalid("bottom",127.4);invalid("left",-1);invalid("right",9999);invalid("bottom",9999);invalid("viewportWidth",0);invalid("viewportHeight",-1);
    invalid("ownedTarget",false);invalid("ready",false);invalid("visible",false);invalid("mode","probe");invalid("command",6);invalid("runNonce","foreign");invalid("url","http://127.0.0.1:8765/foreign");
    excluded("serial",v->v.run++);excluded("action",v->v.action="usability");excluded("session",v->v.session=new ChatSession());
    excluded("native session",v->v.session.web.current=new GeckoSession());excluded("closed",v->v.session.web.current.open=false);
    excluded("surface",v->v.session.web.surface=new GeckoView());excluded("surface attachment",v->v.session.web.surface.session=new GeckoSession());
    excluded("port",v->v.session.web.ports.put(v.session.web.current,new Object()));excluded("load",v->v.session.web.appearanceLoads.put(v.session.web.current,5L));
    excluded("location",v->v.session.web.locations.put(v.session.web.current,"foreign"));excluded("navigation",v->v.session.navigationEpoch++);
    excluded("connection",v->v.session.connectionEpoch++);excluded("nonce",v->v.eventStore.nonce="foreign");excluded("deleted",v->v.session.deleted=true);
    excluded("destroyed",v->v.destroyed=true);excluded("deadline",v->SystemClock.now=26000);
    for(int field=0;field<7;field++){
      a=fresh();if(field==0)a.focus=false;if(field==1)a.session.web.focus=false;if(field==2)a.session.web.surface.focused=false;
      if(field==3)a.session.web.surface.attached=false;if(field==4)a.session.web.surface.shown=false;if(field==5)a.session.browserPaused=true;if(field==6)a.session.web.painted.clear();
      g=begin(a);check(a.events.isEmpty()&&a.session.web.evaluations==0,"nonready focus/paint/layout waits "+field);
      a.focus=a.session.web.focus=a.session.web.surface.focused=a.session.web.surface.attached=a.session.web.surface.shown=true;a.session.browserPaused=false;a.session.web.painted.add(a.session.web.current);
      a.session.handler.next();stable(a);check(a.events.size()==1,"ready transition uses same budget "+field);
    }
    a=fresh();g=begin(a);a.focus=false;deliver(a,rect(a));check(a.events.isEmpty(),"focus lost during DOM callback");
    a=fresh();g=begin(a);deliver(a,rect(a));a.session.handler.next();final GeckoIntegrationTestActivity changed=a;a.session.web.surface.originHook=()->changed.session.navigationEpoch++;deliver(a,rect(a));check(a.events.isEmpty(),"owner lost while sampling final native geometry");
    a=fresh();a.focus=false;g=begin(a);int polls=0;while(!a.session.handler.tasks.isEmpty()&&polls++<260)a.session.handler.next();
    check(g.retired&&SystemClock.now==26000&&a.events.isEmpty()&&polls<=250,"same original 25 second budget with no input on unresolved readiness");
    System.out.println(J.obj("status","passed","checks",checks,"actualAndroidExecution",false,"actualGeckoExecution",false,"nativeInputInjected",false));
  }
}
class GeckoIntegrationTestActivity {
  long run=5;String action="desktopImage";ChatSession session=new ChatSession();EventStore eventStore=new EventStore();
  boolean focus=true,destroyed,finishing;final List<JSONObject> events=new ArrayList<>();
  boolean hasWindowFocus(){return focus;}boolean isDestroyed(){return destroyed;}boolean isFinishing(){return finishing;}
  void event(long serial,String kind,JSONObject value){if(serial==run&&"tapNeeded".equals(kind))events.add(value);}
}
class EventStore{String nonce="f4658b6da7a94e6fb95c7e8f07409817";}
class ChatSession{
  GeckoWebView web=new GeckoWebView();boolean navigating,browserPaused,deleted;long navigationEpoch=3,connectionEpoch=2;Handler handler=new Handler();
}
class Handler{
  final ArrayDeque<Runnable> tasks=new ArrayDeque<>();final ArrayDeque<Long> delays=new ArrayDeque<>();
  void postDelayed(Runnable task,long delay){tasks.add(task);delays.add(delay);}
  void next(){PhotoTapHost.check(!tasks.isEmpty(),"expected scheduled preparation");SystemClock.now+=delays.remove();tasks.remove().run();}
}
class GeckoWebView{
  GeckoSession current=new GeckoSession();GeckoView surface=new GeckoView();float readingLayout=1;int width=1080,height=1795,evaluations;
  boolean destroyed,failed,focus=true,shown=true,attached=true,visible=true;
  String url="http://127.0.0.1:8765/browser-image?command=5&nonce=f4658b6da7a94e6fb95c7e8f07409817&privacy=2&mode=select";
  Map<GeckoSession,Object> ports=new IdentityHashMap<>();Map<GeckoSession,Long> appearanceLoads=new IdentityHashMap<>();Map<GeckoSession,String> locations=new IdentityHashMap<>();
  Set<GeckoSession> pendingLoads=new HashSet<>(),painted=new HashSet<>(),measuredCompositors=new HashSet<>();android.webkit.ValueCallback<String> callback;
  GeckoWebView(){surface.session=current;ports.put(current,new Object());appearanceLoads.put(current,4L);locations.put(current,url);painted.add(current);measuredCompositors.add(current);}
  String getUrl(){return url;}boolean hasVisibleDocument(){return visible;}boolean hasWindowFocus(){return focus;}boolean isShown(){return shown;}boolean isAttachedToWindow(){return attached;}
  int getWidth(){return width;}int getHeight(){return height;}
  void evaluateJavascript(String script,android.webkit.ValueCallback<String> callback){evaluations++;PhotoTapHost.check(script.contains(JSONObject.quote(url))&&script.contains("elementFromPoint")&&script.contains("photo-evidence"),"actual DOM expression binds owned input and invocation");this.callback=callback;}
}
class NetworkCatalog{static void put(JSONObject target,String key,Object value){try{target.put(key,value);}catch(JSONException error){throw new IllegalStateException(error);}}}
'''


class PhotoTapTest(unittest.TestCase):
    def test_actual_helper_rejects_stale_geometry_and_foreign_owners_on_both_json_runtimes(self):
        home = os.environ.get('JAVA_HOME_17_X64') or os.environ.get('JAVA_HOME')
        java = Path(home)/'bin/java' if home else Path(shutil.which('java') or '')
        self.assertTrue(java.is_file(), 'JDK17 is required')
        source = HELPER.read_bytes()
        reports = []
        for jarname,variable in (('json.jar','PROFILE_JSON_JAR'), ('android-json.jar','PROFILE_ANDROID_JSON_JAR')):
            jar = Path(os.environ.get(variable, ROOT/'work/profile-host'/jarname))
            self.assertTrue(jar.is_file(), jar)
            with tempfile.TemporaryDirectory(prefix='photo-tap-host-') as temporary:
                base = Path(temporary)
                files = dict(STUBS, **{
                    'local/pocketchat/GeckoPhotoTap.java': source.decode(),
                    'local/pocketchat/J.java': (ROOT/'app/src/main/java/local/pocketchat/J.java').read_text(),
                    'local/pocketchat/PhotoTapHost.java': HOST,
                })
                for name,text in files.items():
                    path=base/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
                built=subprocess.run([str(java),'-m','jdk.compiler/com.sun.tools.javac.Main','--release','8','-encoding','UTF-8','-cp',str(jar),'-d',str(base),*[str(base/name) for name in files]],capture_output=True,text=True,timeout=40)
                self.assertEqual(built.returncode,0,built.stdout+built.stderr)
                result=subprocess.run([str(java),'-cp',str(base)+os.pathsep+str(jar),'local.pocketchat.PhotoTapHost'],capture_output=True,text=True,timeout=20)
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                report=json.loads(result.stdout);self.assertEqual(report['status'],'passed');self.assertGreater(report['checks'],100)
                reports.append(dict(jsonRuntime=jarname,**report))
        self.assertEqual(HELPER.read_bytes(),source)
        path=ROOT/'work/photo-tap/host-results.json';path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(dict(schema=1,helperSha256=hashlib.sha256(source).hexdigest(),runs=reports,
            actualAndroidExecution=False,actualGeckoExecution=False,nativeInputInjected=False),indent=2)+'\n')

if __name__=='__main__':unittest.main()
