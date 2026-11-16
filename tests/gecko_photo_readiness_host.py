"""Compile the current photo-dispatch path with controlled Android collaborators.

The copied path starts at the actual waitReady entry and ends at the photo
branch's unconditional return. No readiness code is rewritten. The remainder
of the method is unreachable for this action. This is a JVM host, not Android
or real network evidence.
"""
from pathlib import Path
import subprocess
import tempfile


PHOTO_DISPATCH = 'if("photoProtectionProbe".equals(action)){GeckoPhotoProtectionProbe.run(this,serial);return;}'

ANDROID = {
    'Network.java': '''package android.net;
public class Network {public String name="network-a"; public String toString(){return name;}}''',
    'NetworkCapabilities.java': '''package android.net;
public class NetworkCapabilities {public static final int NET_CAPABILITY_INTERNET=12;
 public boolean internet=true;public boolean hasCapability(int capability){return internet&&capability==12;}}''',
    'ConnectivityManager.java': '''package android.net;
public class ConnectivityManager {public Network network=new Network();public NetworkCapabilities capabilities=new NetworkCapabilities();
 public Network getActiveNetwork(){return network;}public NetworkCapabilities getNetworkCapabilities(Network network){return capabilities;}}''',
}

HOST = '''package local.pocketchat;
import java.util.*;
import java.util.function.Consumer;
public class PhotoReadinessHost {
 static class JSONException extends Exception {}
 static class JSONObject {JSONObject put(String name,Object value)throws JSONException{return this;}}
 static class J {static JSONObject obj(Object... fields){return new JSONObject();}}
 static class SystemClock {static long now;static long elapsedRealtime(){return now;}}
 static class Handler {int posts;long delay;Runnable pending;void postDelayed(Runnable task,long ms){posts++;delay=ms;pending=task;}}
 static class Prefs {String proxy="socks://127.0.0.1:1080";boolean vpn;
  String getString(String name,String fallback){return "proxy".equals(name)?proxy:fallback;}
  boolean getBoolean(String name,boolean fallback){return "requireExternalVpn".equals(name)?vpn:fallback;}}
 static class Guard {boolean blocked=true;void setBlocked(boolean value){blocked=value;}boolean allowed(){return !blocked;}}
 static class GeckoWebView {boolean failed,ready=true;Object startupState;
  static String stateUrl(Object state){return "about:blank";}String route(String target){return "controlled-route";}}
 static class FixtureView extends GeckoWebView {boolean initialRouteReady;Consumer<String> initialRouteReporter;}
 static class Session {GeckoWebView web=new FixtureView();Handler handler=new Handler();Prefs prefs=new Prefs();Guard guard=new Guard();
  boolean offline,networkReady,internal;String networkIdentity="network-a";boolean internalNetwork(){return internal;}}
 static class Context {Prefs getSharedPreferences(String name,int mode){return new Prefs();}}
 static class Profiles {static Context context(Activity activity,int slot){return new Context();}}
 static class GeckoPhotoProtectionProbe {static void run(Activity activity,long serial){activity.photos++;activity.photoSerial=serial;}}
 static class Activity {
  long run=7,initialRouteStableSince,photoSerial;int slot,initialRouteSamples,photos,otherCalls;
  boolean activityResumed=true,foreground=true;String action="photoProtectionProbe",initialRouteNetwork="",eventKind="";
  Session session=new Session();android.net.ConnectivityManager manager=new android.net.ConnectivityManager();
  <T>T getSystemService(Class<T> type){return type.cast(manager);}boolean processForeground(){return foreground;}
  void observeReadiness(long serial,String phase,boolean force){}
  void observeReadinessNetwork(long serial,String identity,boolean available,long now){}
  void event(long serial,String kind,JSONObject value){eventKind=kind;}
  void backgroundSettings(long serial){otherCalls++;}void queuedChanges(long serial){otherCalls++;}
  void privacy(long serial,int mode){otherCalls++;}void completion(long serial){otherCalls++;}
  void desktopImage(long serial){otherCalls++;}void desktopImage(long serial,boolean own){otherCalls++;}
  void sample(long now){SystemClock.now=now;waitReady(run);}
  /* ACTUAL_CURRENT_PHOTO_PATH */
 }
 static int checks;
 static void check(boolean value,String name){checks++;if(!value)throw new AssertionError(name);}
 static Activity fresh(){SystemClock.now=0;return new Activity();}
 static void held(Activity a,long delay,String name){check(a.photos==0,name+": photo held");check(a.session.handler.delay==delay,name+": original retry");}
 static void ready(Activity a,String name){check(a.photos==1&&a.photoSerial==a.run,name+": exact photo dispatch");
  check(a.session.networkReady&&!a.session.guard.blocked&&((FixtureView)a.session.web).initialRouteReady,name+": original admitted route");
  check(a.otherCalls==0,name+": only photo action");}
 public static void main(String[] args){
  Activity a=fresh();a.waitReady(6);check(a.photos==0&&a.session.handler.posts==0,"stale command");
  a=fresh();a.activityResumed=false;a.sample(100);held(a,50,"not resumed");
  a=fresh();a.foreground=false;a.sample(100);held(a,50,"not foreground");
  a=fresh();a.session.web.failed=true;a.sample(100);check(a.photos==0&&"error".equals(a.eventKind),"browser failure");
  a=fresh();a.session.web.ready=false;a.sample(100);held(a,200,"browser not ready");
  a=fresh();a.manager=null;a.sample(100);held(a,100,"manager missing");
  a=fresh();a.manager.network=null;a.sample(100);held(a,100,"network missing");
  a=fresh();a.manager.capabilities.internet=false;a.sample(100);held(a,100,"internet missing");
  a=fresh();a.session.offline=true;a.sample(100);held(a,100,"observer offline");
  a=fresh();a.session.networkIdentity="other-network";a.sample(100);held(a,100,"observer identity differs");
  a=fresh();a.sample(100);held(a,100,"first sample");a.sample(200);held(a,100,"second sample");
  a.sample(599);held(a,100,"three samples before 500ms");a.sample(600);ready(a,"stable route");
  a=fresh();a.sample(100);a.sample(600);held(a,100,"500ms but only two samples");a.sample(600);ready(a,"third stable sample");
  a=fresh();a.sample(100);a.sample(400);a.manager.network.name="network-b";a.session.networkIdentity="network-b";
  a.sample(600);held(a,100,"changed route");check(a.initialRouteSamples==1&&a.initialRouteStableSince==600,"changed route resets samples");
  for(int mode=0;mode<3;mode++){
   a=fresh();if(mode==0)a.session.internal=true;else if(mode==1)a.session.prefs.proxy="http://wrong";else a.session.prefs.vpn=true;
   a.sample(100);a.sample(300);a.sample(600);check(a.photos==0&&"error".equals(a.eventKind),"route policy rejected "+mode);
   check(!a.session.networkReady&&a.session.guard.blocked,"invalid route remains blocked "+mode);
  }
  a=fresh();((FixtureView)a.session.web).initialRouteReady=true;a.session.networkReady=true;a.session.guard.blocked=false;
  a.manager=null;a.sample(100);ready(a,"previously admitted route");
  a=fresh();((FixtureView)a.session.web).initialRouteReady=true;a.session.web.ready=false;a.sample(100);held(a,200,"cached route still needs browser");
  System.out.println("photoReadinessChecks="+checks);
 }
}
'''


def execute_current_photo_path(method):
    if method.count(PHOTO_DISPATCH) != 1:
        raise AssertionError('Exactly one actual photo dispatch is required')
    prefix = method[:method.index(PHOTO_DISPATCH)+len(PHOTO_DISPATCH)]+'\n }'
    with tempfile.TemporaryDirectory(prefix='current-photo-readiness-host-') as temporary:
        root = Path(temporary)
        sources = []
        for name, text in ANDROID.items():
            path = root/'android/net'/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
            sources.append(str(path))
        java = root/'PhotoReadinessHost.java'
        java.write_text(HOST.replace('/* ACTUAL_CURRENT_PHOTO_PATH */', prefix))
        subprocess.run(['javac', '-d', str(root), *sources, str(java)], check=True, capture_output=True, text=True)
        return subprocess.run(['java', '-cp', str(root), 'local.pocketchat.PhotoReadinessHost'],
                              capture_output=True, text=True, timeout=10)
