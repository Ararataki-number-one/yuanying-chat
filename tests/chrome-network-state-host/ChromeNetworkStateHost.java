package local.pocketchat;
import android.content.*;import android.os.SystemClock;import android.util.Log;import org.json.*;import java.util.*;import java.nio.charset.StandardCharsets;

public final class ChromeNetworkStateHost {
  static final JSONArray checks=new JSONArray(),observations=new JSONArray();static final JSONObject deviceProjection=new JSONObject();
  static void check(String name,boolean value){checks.put(J.obj("name",name,"pass",value));}
  static void observe(String name,DesignChrome c){observations.put(J.obj("case",name,"state",c.last.state,"connected",c.last.connected,"latency",c.last.latency,"timer",c.last.latencyTimer,"catalogReads",ProfileCatalog.reads,"renders",c.renders));}
  static JSONObject copy(JSONObject value){try{return new JSONObject(value.toString());}catch(Exception e){throw new RuntimeException(e);}}
  static JSONObject row(){return J.obj("slot",0,"name","Same title","environmentId","scope-a","generation",2,"created",true,"deleting",false,"resetting",false);}
  static JSONObject observation(){return J.obj("environmentId","scope-a","generation",2,"at",System.currentTimeMillis(),"mode","external","configured",true,"connected",true,"route","controlled-route","delayRoute","controlled-route","delay",42,"delayAt",System.currentTimeMillis(),"delayKind","response","latencyRemaining",120000);}
  static MainActivity activity(){ProfileCatalog.reads=0;ProfileCatalog.failure=false;ProfileCatalog.value=row();DesignUi.Stars.fail=false;DesignUi.Stars.refreshes=0;DesignChrome.metadataReader.clear();SystemClock.now=100000;MainActivity a=new MainActivity();a.runtime=observation();return a;}
  static DesignChrome ready(MainActivity a){DesignChrome c=new DesignChrome(a);c.update();a.handler.drain();DesignChrome.metadataReader.drain();a.handler.drain();return c;}
  static void change(DesignChrome c,JSONObject row){ProfileCatalog.value=row;SystemClock.now+=2000;c.update();c.a.handler.drain();DesignChrome.metadataReader.drain();c.a.handler.drain();}
  static boolean normal(DesignChrome c){return c.last!=null&&c.last.connected&&c.last.state.equals("正常")&&c.last.latency.equals("42 ms")&&c.last.latencyTimer.equals("（02:00）");}
  static void before(){MainActivity a=activity();DesignChrome c=ready(a);observe("historical-production-render",c);check("Existing production compact renderer must retain fresh matching route identity",normal(c));check("Same complete row controls current constructor",new WindowNetworkState(a,row(),new JSONObject(),a.runtime,true,System.currentTimeMillis()).state.equals("正常"));}
  static void current()throws Exception{
    MainActivity a=activity();DesignChrome c=new DesignChrome(a);check("Initial metadata uses one catalogue read",ProfileCatalog.reads==1);c.update();a.handler.drain();DesignChrome.metadataReader.drain();a.handler.drain();observe("current-production-render",c);check("Production renderer shows fresh matching route with 42 ms and unchanged countdown",normal(c));
    int startReads=ProfileCatalog.reads,startRenders=c.renders;for(int i=0;i<100;i++){c.update();a.handler.drain();}check("One hundred hot-path renders do not read catalogue again",ProfileCatalog.reads==startReads&&c.renders-startRenders==100&&DesignChrome.metadataReader.size()==0);check("Hot-path renders retain actual identity and sample",normal(c));
    startRenders=c.renders;for(int i=0;i<100;i++)c.update();a.handler.drain();check("Queued repeated UI updates coalesce without catalogue reads",c.renders==startRenders+1&&ProfileCatalog.reads==startReads);
    JSONObject changed=row();changed.put("generation",3);startRenders=c.renders;change(c,changed);check("Same-name generation change triggers a new render and rejects old runtime",c.renders==startRenders+2&&!c.last.connected&&c.last.state.equals("状态待核实")&&c.title.getText().equals("Same title"));
    a.runtime.put("generation",3);c.update();a.handler.drain();check("Matching new generation restores current display",normal(c));
    changed=copy(changed);changed.put("environmentId","scope-b");startRenders=c.renders;change(c,changed);check("Same-name UUID replacement triggers render and rejects prior environment",c.renders==startRenders+2&&!c.last.connected);a.runtime.put("environmentId","scope-b");c.update();a.handler.drain();check("Matching new UUID restores current display",normal(c));
    for(String key:new String[]{"missing","deleting","resetting","created","slot","environmentId","generation"}){
      a=activity();c=ready(a);JSONObject invalid=row();if(key.equals("missing"))invalid=new JSONObject();else if(key.equals("deleting")||key.equals("resetting"))invalid.put(key,true);else if(key.equals("created"))invalid.put(key,false);else if(key.equals("slot"))invalid.put(key,1);else if(key.equals("environmentId"))invalid.remove(key);else invalid.put(key,-1);change(c,invalid);check("Production metadata rejects unavailable catalogue row "+key,!c.last.connected&&c.last.state.equals("未运行")&&c.last.latencyTimer.equals("（等待连接）"));
    }
    a=activity();c=ready(a);a.runtime.put("at",System.currentTimeMillis()-45001);c.update();a.handler.drain();check("Stale runtime cannot be displayed as connected",!c.last.connected&&c.last.state.equals("状态待核实"));a.runtime.put("at",System.currentTimeMillis()+61000);c.update();a.handler.drain();check("Far future runtime remains rejected",!c.last.connected&&c.last.state.equals("状态待核实"));
    a=activity();c=ready(a);a.runtime.put("delayRoute","another-route");c.update();a.handler.drain();check("A different measurement route never displays current latency",c.last.connected&&c.last.latency.equals("延迟未测"));
    a=activity();c=ready(a);a.runtime.put("delayAt",System.currentTimeMillis()-120001);c.update();a.handler.drain();check("Expired latency remains explicitly historical",c.last.connected&&c.last.latency.equals("42 ms（上次）"));
    a=activity();c=ready(a);String title=c.title.getText().toString();ProfileCatalog.failure=true;SystemClock.now+=2000;c.update();a.handler.drain();int reads=ProfileCatalog.reads;DesignChrome.metadataReader.drain();a.handler.drain();check("Background query failure clears cached identity without losing title",ProfileCatalog.reads==reads+1&&c.profileRow.length()==0&&c.title.getText().equals(title)&&!c.last.connected);ProfileCatalog.failure=false;change(c,row());check("A later successful metadata read recovers normal display",normal(c));
    a=activity();c=ready(a);changed=row();changed.put("generation",3);ProfileCatalog.value=changed;DesignUi.Stars.fail=true;SystemClock.now+=2000;c.update();a.handler.drain();DesignChrome.metadataReader.drain();a.handler.drain();check("Appearance refresh error does not discard a successful catalogue identity",c.profileRow.optInt("generation")==3&&!c.last.connected);DesignUi.Stars.fail=false;
    a=activity();c=ready(a);JSONObject previous=c.profileRow;changed=row();changed.put("generation",3);ProfileCatalog.value=changed;SystemClock.now+=2000;c.update();a.handler.drain();DesignChrome.metadataReader.drain();startRenders=c.renders;a.destroyed=true;a.handler.drain();check("Destroy before metadata delivery does not write cache or schedule render",c.profileRow==previous&&c.renders==startRenders&&a.handler.size()==0);c.update();check("Updates after destroy remain unqueued",a.handler.size()==0);
    a=activity();c=ready(a);SystemClock.now+=2000;startReads=ProfileCatalog.reads;c.update();a.handler.drain();for(int i=0;i<100;i++){c.update();a.handler.drain();}check("An outstanding metadata worker cannot create duplicate queries",DesignChrome.metadataReader.size()==1&&ProfileCatalog.reads==startReads);DesignChrome.metadataReader.drain();a.handler.drain();check("Exactly one background read completes the pending metadata refresh",ProfileCatalog.reads==startReads+1&&normal(c));
    a=activity();c=ready(a);changed=row();changed.put("name","Renamed title");change(c,changed);check("A same-identity rename still updates both visible labels",c.title.getText().equals("Renamed title")&&c.compactTitle.getText().equals("Renamed title")&&normal(c));
    stateMatrix();new DeviceProjection().readModelFreshnessChecks(deviceProjection);
  }

  static WindowNetworkState state(JSONObject runtime,JSONObject config,boolean live,long now){return new WindowNetworkState(new Context(),row(),config,runtime,live,now);}
  static JSONObject runtime(long now){JSONObject value=observation();try{value.put("at",now);value.put("delayAt",now);value.put("ip","192.0.2.42");}catch(JSONException e){throw new RuntimeException(e);}return value;}
  static void matrix(String name,JSONObject runtime,JSONObject config,boolean live,long now,String expected,boolean connected,String latency,String timer)throws Exception{matrix(name,runtime,config,live,now,expected,connected,latency,timer,true);}
  static void matrix(String name,JSONObject runtime,JSONObject config,boolean live,long now,String expected,boolean connected,String latency,String timer,boolean assertSample)throws Exception{
    String beforeRuntime=runtime.toString(),beforeConfig=config.toString();WindowNetworkState result=state(runtime,config,live,now);
    check("State evidence matrix: "+name,result.state.equals(expected)&&result.connected==connected&&(!assertSample||result.latency.equals(latency))&&result.latencyTimer.equals(timer)&&runtime.toString().equals(beforeRuntime)&&config.toString().equals(beforeConfig));
    observations.put(J.obj("case",name,"state",result.state,"connected",result.connected,"latency",result.latency,"timer",result.latencyTimer,"mainline",result.mainline(),"sampleTrustAsserted",assertSample,"runtimeUnchanged",runtime.toString().equals(beforeRuntime),"configUnchanged",config.toString().equals(beforeConfig)));
  }
  static void stateMatrix()throws Exception{
    final long now=1000000;JSONObject config=new JSONObject(),value;
    matrix("fresh matching live route",runtime(now),config,true,now,"正常",true,"42 ms","（02:00）");
    for(long age:new long[]{44999,45000,45001}){value=runtime(now);value.put("at",now-age);boolean fresh=age<45000;matrix("snapshot age "+age,value,config,true,now,fresh?"正常":"状态待核实",fresh,fresh?"42 ms":"42 ms（上次）",fresh?"（02:00）":"（等待连接）");}
    for(long ahead:new long[]{59999,60000,60001}){value=runtime(now);value.put("at",now+ahead);boolean tolerated=ahead<=60000;matrix("existing future clock tolerance "+ahead,value,config,true,now,tolerated?"正常":"状态待核实",tolerated,tolerated?"42 ms":"42 ms（上次）",tolerated?"（02:00）":"（等待连接）");}
    for(String missing:new String[]{"absent","zero","negative"}){value=runtime(10000);if(missing.equals("absent"))value.remove("at");else value.put("at",missing.equals("zero")?0:-1);matrix("timestamp "+missing+" during first45seconds",value,config,true,10000,"状态待核实",false,"42 ms（上次）","（等待连接）");}
    SharedPreferences.networkConfigured=true;try{matrix("missing complete snapshot in configured live environment",new JSONObject(),config,true,10000,"状态待核实",false,"延迟未测","（等待连接）");matrix("missing complete snapshot with no live environment",new JSONObject(),config,false,10000,"未运行",false,"延迟未测","（等待连接）");}finally{SharedPreferences.networkConfigured=false;}
    value=runtime(now);matrix("not live with matching recent snapshot",value,config,false,now,"未运行",false,"42 ms（上次）","（等待连接）");
    value=runtime(now);value.put("at",now-45000);matrix("not live and stale",value,config,false,now,"未运行",false,"42 ms（上次）","（等待连接）");
    for(String key:new String[]{"environmentId","generation"}){value=runtime(now);value.put(key,key.equals("environmentId")?"another-environment":3);matrix("live but different "+key,value,config,true,now,"状态待核实",false,"42 ms（上次）","（等待连接）",false);}
    value=runtime(now);value.remove("environmentId");value.remove("generation");matrix("legacy runtime identity allowance unchanged",value,config,true,now,"正常",true,"42 ms","（02:00）");
    for(String key:new String[]{"offline","blocked","starting","issue","connected"}){
      value=runtime(now);if(key.equals("issue"))value.put(key,"controlled reported issue");else value.put(key,!key.equals("connected"));String expected=key.equals("offline")?"离线":key.equals("blocked")?"出口异常":key.equals("starting")?"连接中":key.equals("issue")?"需检查":"未连接";String timer=key.equals("issue")?"（02:00）":"（等待连接）";
      matrix("fresh original "+key,value,config,true,now,expected,false,"42 ms（上次）",timer);
      value.put("at",now-45000);matrix("stale original "+key,value,config,true,now,"状态待核实",false,"42 ms（上次）","（等待连接）");
    }
    value=runtime(now);value.put("admission","DEGRADED_VERIFICATION");matrix("fresh retained admission",value,config,true,now,"核验待恢复",true,"42 ms","（02:00）");
    value=runtime(now);value.put("delayRoute","different-route");matrix("measurement route mismatch",value,config,true,now,"正常",true,"延迟未测","（02:00）");
    value=runtime(now);value.put("configured",false);value.remove("at");matrix("unconfigured precedence unchanged",value,config,true,now,"未配置",false,"42 ms（上次）","（等待连接）");
    value=runtime(now);value.put("latencyMeasuring",true);value.put("at",now-45000);matrix("stale measuring flag cannot show progress",value,config,true,now,"状态待核实",false,"42 ms（上次）","（等待连接）");
    value=runtime(now);WindowNetworkState fresh=state(value,config,true,now);value.put("at",now-45000);WindowNetworkState stale=state(value,config,true,now);check("Stale live IP and latency remain historical without becoming current",fresh.mainline().contains("192.0.2.42")&&!fresh.mainline().contains("上次 192.0.2.42")&&stale.mainline().contains("上次 192.0.2.42")&&stale.mainline().contains("42 ms（上次）"));
    config=J.obj("exitHost","192.0.2.9","exitPort",1080,"subscriptionUrl","controlled-subscription");
    for(String condition:new String[]{"healthy","health-failed","target-answered","blocked","reported-issue","exit-mismatch","subscription-mismatch"}){
      value=runtime(now);value.put("mode","internal");value.put("exitId",NativeNetwork.exitIdentity(config));value.put("subscriptionId",NativeNetwork.hash(config.optString("subscriptionUrl")));value.put("entry","controlled-entry");value.put("delayEntry","controlled-entry");value.put("healthDelayAt",now);value.put("healthDelay",12);
      if(condition.equals("health-failed")||condition.equals("target-answered"))value.put("healthDelay",-1);
      if(condition.equals("target-answered")){value.put("healthStatus","primary-detector-unavailable");value.put("healthTargetCode",403);value.put("healthObservedAt",now);}
      if(condition.equals("blocked")){value.put("blocked",true);value.put("observedIp","192.0.2.99");}
      if(condition.equals("reported-issue"))value.put("issue","controlled reported issue");
      if(condition.equals("exit-mismatch"))value.put("exitId","another-exit");
      if(condition.equals("subscription-mismatch"))value.put("subscriptionId","another-subscription");
      boolean connected=!condition.equals("health-failed")&&!condition.equals("blocked")&&!condition.equals("reported-issue");String label=condition.equals("blocked")?"出口异常":connected?"正常":"需检查";boolean sampleMatches=!condition.equals("exit-mismatch")&&!condition.equals("subscription-mismatch");
      matrix("internal fresh "+condition,value,config,true,now,label,connected,sampleMatches?connected?"42 ms":"42 ms（上次）":"延迟未测",condition.equals("blocked")?"（等待连接）":"（02:00）");
      value.put("at",now-45000);matrix("internal stale "+condition,value,config,true,now,"状态待核实",false,sampleMatches?"42 ms（上次）":"延迟未测","（等待连接）");
    }
  }
  static class DeviceProjection extends Context{/* DEVICE_READ_MODEL_METHOD */}
  public static void main(String[]args)throws Exception{String executionFailure="";try{if(Boolean.getBoolean("before"))before();else current();}catch(AssertionError failed){executionFailure=failed.toString();}if(deviceProjection.has("networkReadModelFreshness")){JSONArray cases=new JSONArray();for(int i=0;i<checks.length();i++){JSONObject reading=checks.optJSONObject(i).optJSONObject("readModel");if(reading!=null)cases.put(reading);}JSONObject summary=copy(deviceProjection.getJSONObject("networkReadModelFreshness"));summary.put("cases",cases);deviceProjection.put("networkReadModelFreshness",summary);}int passed=0;for(int i=0;i<checks.length();i++)if(checks.optJSONObject(i).optBoolean("pass"))passed++;boolean success=executionFailure.isEmpty()&&passed==checks.length();System.out.println(J.obj("status",success?"passed":"failed","passed",passed,"total",checks.length(),"checks",checks,"observations",observations,"deviceProjectionHostReplay",deviceProjection,"executionFailure",executionFailure));if(!success)System.exit(1);}
}

class DesignChrome {
  final MainActivity a;TextView title,compactTitle;final View compact=new View();String profileName;JSONObject profileRow=new JSONObject();boolean queued,metadataPending;long metadataAt;int renders;WindowNetworkState last;
  static final TaskQueue metadataReader=new TaskQueue();final Runnable render=this::renderLatest;
  DesignChrome(MainActivity a){this.a=a;/* INITIAL_METADATA */}
  void showNetwork(WindowNetworkState state){last=state;renders++;}
  /* CHROME_METHODS */
}
class WindowNetworkState {
  /* STATE_FIELDS */
  /* STATE_CONSTRUCTOR */
  /* STATE_MAINLINE */
  static JSONObject live(Object session,NativeNetwork n){return n.owner.runtime;}
}
class MainActivity extends Context{boolean destroyed;Object session=new Object();JSONObject runtime;TaskQueue handler=new TaskQueue();}
class TaskQueue{final ArrayDeque<Runnable> tasks=new ArrayDeque<>();void post(Runnable r){tasks.add(r);}void execute(Runnable r){tasks.add(r);}int size(){return tasks.size();}void clear(){tasks.clear();}void drain(){int count=0;while(!tasks.isEmpty()){if(++count>1000)throw new AssertionError("Nonterminating callback queue");tasks.remove().run();}}}
class View{CharSequence description="";CharSequence getContentDescription(){return description;}void setContentDescription(CharSequence value){description=value;}}
class TextView extends View{CharSequence text="";CharSequence getText(){return text;}void setText(CharSequence value){text=value;}}
class TextUtils{static boolean equals(CharSequence a,CharSequence b){return Objects.equals(a==null?null:a.toString(),b==null?null:b.toString());}}
class ReferenceUi{static final int TEXT=1;static TextView text(Context a,String value,int size,int color,boolean bold){TextView view=new TextView();view.setText(value);return view;}}
class ProfileCatalog{static JSONObject value;static boolean failure;static int reads;static final ProfileCatalog instance=new ProfileCatalog();static ProfileCatalog get(Context c){return instance;}JSONObject item(int slot){reads++;if(failure)throw new IllegalStateException("controlled catalogue read failure");return ChromeNetworkStateHost.copy(value);}String name(int slot){return item(slot).optString("name");}}
class Profiles{static Context context(Context c,int slot){return c;}static int slot(Context c){return 0;}static String display(Context c,int slot){return ProfileCatalog.get(c).name(slot);}}
class DesignUi{static class Stars{static boolean fail;static int refreshes;static void refresh(Context c){refreshes++;if(fail)throw new IllegalStateException("controlled appearance refresh failure");}}}
class UiPerfStats{static void chromeUpdate(){}static void textChange(){}}
class NetworkRegion{static String region(Context c,String ip){return "";}}
class NetworkCatalog{/* CATALOG_EXIT_ID */static String subscriptionName(JSONObject c){return "controlled subscription";}}
class NativeNetwork{MainActivity owner;JSONObject settings=new JSONObject();static NativeNetwork get(MainActivity a){NativeNetwork n=new NativeNetwork();n.owner=a;return n;}/* NATIVE_METHODS */}
class J{static JSONObject obj(Object...args){JSONObject value=new JSONObject();try{for(int i=0;i<args.length;i+=2)value.put((String)args[i],args[i+1]);}catch(JSONException e){throw new IllegalStateException(e);}return value;}}
