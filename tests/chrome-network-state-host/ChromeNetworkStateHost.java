package local.pocketchat;
import android.content.*;import android.os.SystemClock;import org.json.*;import java.util.*;

public final class ChromeNetworkStateHost {
  static final JSONArray checks=new JSONArray(),observations=new JSONArray();
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
    JSONObject changed=row();changed.put("generation",3);startRenders=c.renders;change(c,changed);check("Same-name generation change triggers a new render and rejects old runtime",c.renders==startRenders+2&&!c.last.connected&&c.last.state.equals("未运行")&&c.title.getText().equals("Same title"));
    a.runtime.put("generation",3);c.update();a.handler.drain();check("Matching new generation restores current display",normal(c));
    changed=copy(changed);changed.put("environmentId","scope-b");startRenders=c.renders;change(c,changed);check("Same-name UUID replacement triggers render and rejects prior environment",c.renders==startRenders+2&&!c.last.connected);a.runtime.put("environmentId","scope-b");c.update();a.handler.drain();check("Matching new UUID restores current display",normal(c));
    for(String key:new String[]{"missing","deleting","resetting","created","slot","environmentId","generation"}){
      a=activity();c=ready(a);JSONObject invalid=row();if(key.equals("missing"))invalid=new JSONObject();else if(key.equals("deleting")||key.equals("resetting"))invalid.put(key,true);else if(key.equals("created"))invalid.put(key,false);else if(key.equals("slot"))invalid.put(key,1);else if(key.equals("environmentId"))invalid.remove(key);else invalid.put(key,-1);change(c,invalid);check("Production metadata rejects unavailable catalogue row "+key,!c.last.connected&&c.last.state.equals("未运行")&&c.last.latencyTimer.equals("（等待连接）"));
    }
    a=activity();c=ready(a);a.runtime.put("at",System.currentTimeMillis()-45001);c.update();a.handler.drain();check("Stale runtime cannot be displayed as connected",!c.last.connected&&c.last.state.equals("未运行"));a.runtime.put("at",System.currentTimeMillis()+61000);c.update();a.handler.drain();check("Far future runtime remains rejected",!c.last.connected&&c.last.state.equals("未运行"));
    a=activity();c=ready(a);a.runtime.put("delayRoute","another-route");c.update();a.handler.drain();check("A different measurement route never displays current latency",c.last.connected&&c.last.latency.equals("延迟未测"));
    a=activity();c=ready(a);a.runtime.put("delayAt",System.currentTimeMillis()-120001);c.update();a.handler.drain();check("Expired latency remains explicitly historical",c.last.connected&&c.last.latency.equals("42 ms（上次）"));
    a=activity();c=ready(a);String title=c.title.getText().toString();ProfileCatalog.failure=true;SystemClock.now+=2000;c.update();a.handler.drain();int reads=ProfileCatalog.reads;DesignChrome.metadataReader.drain();a.handler.drain();check("Background query failure clears cached identity without losing title",ProfileCatalog.reads==reads+1&&c.profileRow.length()==0&&c.title.getText().equals(title)&&!c.last.connected);ProfileCatalog.failure=false;change(c,row());check("A later successful metadata read recovers normal display",normal(c));
    a=activity();c=ready(a);changed=row();changed.put("generation",3);ProfileCatalog.value=changed;DesignUi.Stars.fail=true;SystemClock.now+=2000;c.update();a.handler.drain();DesignChrome.metadataReader.drain();a.handler.drain();check("Appearance refresh error does not discard a successful catalogue identity",c.profileRow.optInt("generation")==3&&!c.last.connected);DesignUi.Stars.fail=false;
    a=activity();c=ready(a);JSONObject previous=c.profileRow;changed=row();changed.put("generation",3);ProfileCatalog.value=changed;SystemClock.now+=2000;c.update();a.handler.drain();DesignChrome.metadataReader.drain();startRenders=c.renders;a.destroyed=true;a.handler.drain();check("Destroy before metadata delivery does not write cache or schedule render",c.profileRow==previous&&c.renders==startRenders&&a.handler.size()==0);c.update();check("Updates after destroy remain unqueued",a.handler.size()==0);
    a=activity();c=ready(a);SystemClock.now+=2000;startReads=ProfileCatalog.reads;c.update();a.handler.drain();for(int i=0;i<100;i++){c.update();a.handler.drain();}check("An outstanding metadata worker cannot create duplicate queries",DesignChrome.metadataReader.size()==1&&ProfileCatalog.reads==startReads);DesignChrome.metadataReader.drain();a.handler.drain();check("Exactly one background read completes the pending metadata refresh",ProfileCatalog.reads==startReads+1&&normal(c));
    a=activity();c=ready(a);changed=row();changed.put("name","Renamed title");change(c,changed);check("A same-identity rename still updates both visible labels",c.title.getText().equals("Renamed title")&&c.compactTitle.getText().equals("Renamed title")&&normal(c));
  }
  public static void main(String[]args)throws Exception{if(Boolean.getBoolean("before"))before();else current();int passed=0;for(int i=0;i<checks.length();i++)if(checks.optJSONObject(i).optBoolean("pass"))passed++;System.out.println(J.obj("status",passed==checks.length()?"passed":"failed","passed",passed,"total",checks.length(),"checks",checks,"observations",observations));if(passed!=checks.length())System.exit(1);}
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
