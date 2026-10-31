package local.pocketchat;
import java.util.*;
import org.mozilla.geckoview.*;
import org.json.JSONObject;
class ChatSession {
 static ChatSession instance;static ChatSession peek(){return instance;}Object context=new Object();GeckoWebView web;String environmentId="environment-A",appliedIdentity="external:http://proxy:8888",proxy="http://proxy:8888",pageError="original-error",pending="original-task",connectionStage="连接中";int environmentGeneration=3;long connectionEpoch=2,navigationEpoch=5;boolean deleted,offline,connecting,recoveryScheduled,browserPaused,internal;boolean networkReady=true;
 Guard guard=new Guard();Privacy privacy=new Privacy();Audit audit=new Audit();Reading reading=new Reading();Queue handler=new Queue();
 boolean internalNetwork(){return internal;}String networkIdentity(){return internal?"internal:receipt":"external:"+proxy;}Prefs prefs=new Prefs();
 class Prefs {String getString(String key,String fallback){return key.equals("proxy")?proxy:fallback;}}
 static class Guard{boolean allowed=true,vpn;boolean allowed(){return allowed;}boolean requiresVpn(){return vpn;}}
 static class Privacy{boolean canNavigate(){return true;}int level(){return 2;}}
 static class Audit{JSONObject report=new JSONObject();boolean current;boolean requestIdentityPageSelected(){return false;}boolean deepObservationCurrent(){return current;}}
 static class Reading{boolean displayHidden,displayPageChanged;void hideDisplay(){displayHidden=true;}void showDisplay(){displayHidden=false;}void viewportMeasured(float v){}}
 static class Queue{List<Runnable> tasks=new ArrayList<>();void removeCallbacks(Runnable r){tasks.remove(r);}void post(Runnable r){tasks.add(r);}void postDelayed(Runnable r,long delay){tasks.add(r);}}
}
class ProfileCatalog {static JSONObject row;static ProfileCatalog get(Object c){return new ProfileCatalog();}JSONObject item(int slot){return row;}boolean available(int slot){return row.optBoolean("created")&&!row.optBoolean("deleting")&&!row.optBoolean("resetting");}}
class Profiles {static int slot(Object c){return 0;}}
class NativeNetwork {static NativeNetwork instance=new NativeNetwork();static int gets;static NativeNetwork get(Object c){gets++;return instance;}static NativeNetwork peek(){return instance;}String exitIp="";long lastVerified;boolean starting;String exitCheckUrl(){return "https://api.ipify.org?format=json";}ExitRouteReceipt verifiedRoute=new ExitRouteReceipt();Transport transport=new Transport();NetworkHealthPolicy.Admission admission=NetworkHealthPolicy.Admission.VERIFIED;NetworkHealthPolicy.Admission connectionAdmission(){return admission;}static class ExitRouteReceipt{boolean matches(NativeNetwork n,JSONObject s){return true;}}static class Transport{JSONObject state=new JSONObject();}}
class MainActivity {static boolean chatUrl(String url){return url.startsWith("https://chatgpt.com/");}}
class LoginPagePolicy {static boolean login(String url){return false;}}
class GeckoPolicyAdapter {static void applySession(GeckoSession s,boolean desktop,int level){s.tracking=level;}}
class SitePermissions {static final int DENY=2;}
class Protection{boolean confirmed=true;long token=3,generation=2;boolean confirmed(){return confirmed;}int level(){return 2;}long token(){return token;}long generation(){return generation;}}
class GeckoSettings{boolean policyAcknowledged=true;JSONObject acceptedBrowserIdentity=new JSONObject();String[] requestedLocales=new String[0];}
class NetworkHealthPolicy{enum Admission{VERIFIED,DEGRADED_VERIFICATION;boolean usable(){return true;}}}
class NetworkRegion{static JSONObject record=new JSONObject();static JSONObject read(Object c){return record;}static String region(Object c,String ip){return ip.equals(record.optString("ip"))?record.optString("region"):"";}}
class BrowserIdentitySpec{static BrowserIdentitySpec from(JSONObject raw){return new BrowserIdentitySpec();}String label(){return "Firefox 标准手机版";}}
class FingerprintObservationHistory{static boolean integer(Object value,long min,long max){return value instanceof Number&&((Number)value).longValue()>=min&&((Number)value).longValue()<=max;}}
class AuditReport{static boolean observedField(JSONObject signal,String key){return signal.opt(key) instanceof String&&!signal.optString(key).isEmpty();}}
