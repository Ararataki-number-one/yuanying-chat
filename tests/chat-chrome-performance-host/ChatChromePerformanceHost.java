package local.pocketchat;

import android.content.*;
import android.os.SystemClock;
import org.json.*;
import java.io.File;
import java.lang.reflect.Field;
import java.nio.charset.StandardCharsets;
import java.util.*;

/** Deterministic scheduling counters; this does not measure native frame time. */
public final class ChatChromePerformanceHost {
  static final JSONArray checks=new JSONArray(),scenarios=new JSONArray();
  static final boolean current=Boolean.getBoolean("frameCoalesced");
  static void check(String name,boolean value){checks.put(J.obj("name",name,"pass",value));}
  static JSONObject row(){return J.obj("slot",0,"name","Controlled environment","environmentId","scope-a","generation",2,"created",true);}
  static JSONObject observation(){return J.obj("at",System.currentTimeMillis(),"mode","external","configured",true,"connected",true,"route","route-a","delayRoute","route-a","delay",42,"delayAt",System.currentTimeMillis(),"delayKind","response","latencyRemaining",120000);}
  static MainActivity setup(){
    DesignChrome.metadataReader.clear();NetworkMetricsUi.refreshes.clear();WindowNetworkState.snapshots.clear();WindowNetworkState.liveCalls=0;WindowNetworkState.savedAt=0;WindowNetworkState.savedSignature="";WindowNetworkState.projected=null;SecretStore.writes=0;SecretStore.last="";UiPerfStats.chrome=0;UiPerfStats.metrics=0;ProfileCatalog.value=row();ProfileCatalog.heartbeats=0;SystemClock.now=100000;
    MainActivity a=new MainActivity();a.runtime=observation();a.designChrome=new DesignChrome(a);a.designChrome.metadataAt=SystemClock.now;return a;
  }
  static void requests(MainActivity a,boolean individualTurns){for(int i=0;i<100;i++){NetworkMetricsUi.update(a);if(individualTurns)a.handler.drain();}}
  static void frame(MainActivity a){a.handler.drain();a.toolbar.frame();a.handler.drain();}
  static void batch(boolean individualTurns){
    MainActivity a=setup();requests(a,individualTurns);a.handler.drain();int before=WindowNetworkState.liveCalls;int frames=a.toolbar.callbacks.size();frame(a);
    int expected=current?1:individualTurns?200:2;
    check((individualTurns?"Separate Handler turns":"One Handler turn")+" uses expected live-projection call count",WindowNetworkState.liveCalls==expected);
    check("Current work waits for a controlled display frame: "+individualTurns,!current||before==0&&frames==1);
    check("The actual constructor and async save capture one identical observation: "+individualTurns,current?a.designChrome.last.runtime==WindowNetworkState.snapshots.captured:a.designChrome.last.runtime!=WindowNetworkState.snapshots.captured);
    check("Actual maintenance count follows coalesced updates: "+individualTurns,UiPerfStats.metrics==(current?1:individualTurns?100:1)&&ProfileCatalog.heartbeats==UiPerfStats.metrics&&a.session.audit.refreshes==UiPerfStats.metrics);
    check("Current display retains actual controlled 42 ms sample: "+individualTurns,a.designChrome.last.connected&&a.designChrome.last.latency.equals("42 ms")&&a.designChrome.last.latencyTimer.equals("（02:00）"));
    scenarios.put(J.obj("scenario",individualTurns?"100 requests in separate Handler turns before one controlled frame":"100 requests together before one controlled frame","requests",100,"projectionCallsBeforeFrame",before,"pendingFrameCallbacks",frames,"projectionCallsAfterFrame",WindowNetworkState.liveCalls,"maintenanceCalls",UiPerfStats.metrics,"chromeRenders",UiPerfStats.chrome,"sameSaveAndConstructorObject",a.designChrome.last.runtime==WindowNetworkState.snapshots.captured));
  }
  static void currentSemantics()throws Exception{
    MainActivity a=setup();a.designChrome.update();NetworkMetricsUi.update(a);frame(a);
    check("A direct update queued first cannot lose a later metrics request",WindowNetworkState.liveCalls==1&&UiPerfStats.metrics==1&&a.session.audit.refreshes==1&&a.designChrome.last.runtime==WindowNetworkState.snapshots.captured);
    JSONObject first=WindowNetworkState.projected;a.runtime.put("issue","Changed after first frame");NetworkMetricsUi.update(a);frame(a);
    check("A new frame derives a new observation instead of retaining the previous snapshot",WindowNetworkState.liveCalls==2&&first!=WindowNetworkState.projected&&a.designChrome.last.runtime==WindowNetworkState.projected);
    check("Current errors are visible in the immediate next frame",a.designChrome.last.state.equals("需检查")&&!a.designChrome.last.connected);
    a.runtime.remove("issue");a.runtime.put("connected",true);NetworkMetricsUi.update(a);frame(a);
    check("Readiness recovery is visible in the immediate next frame",a.designChrome.last.connected&&a.designChrome.last.state.equals("正常"));
    a=setup();NetworkMetricsUi.update(a);a.session=new ChatSession();a.session.environmentId="scope-new";a.session.environmentGeneration=3;frame(a);
    check("Queued requests resolve the current session owner only at frame execution",WindowNetworkState.projected.optString("environmentId").equals("scope-new")&&WindowNetworkState.projected.optInt("generation")==3);
    check("The complete constructor refuses new-owner observations under old catalogue identity",!a.designChrome.last.connected&&a.designChrome.last.runtime.length()==0);
    a.designChrome.profileRow=J.obj("slot",0,"name","Controlled environment","created",true,"environmentId","scope-new","generation",3);NetworkMetricsUi.update(a);frame(a);
    check("A matching current owner and catalogue identity recover without cached observation",a.designChrome.last.connected&&a.designChrome.last.runtime==WindowNetworkState.projected);
    a=setup();NetworkMetricsUi.update(a);a.active=false;frame(a);
    check("A pause before the frame suppresses projection, persistence and maintenance",WindowNetworkState.liveCalls==0&&UiPerfStats.metrics==0&&a.designChrome.last==null&&WindowNetworkState.snapshots.size()==0);
    NetworkMetricsUi.update(a);a.designChrome.update();check("Requests while hidden do not enqueue frame work",a.toolbar.callbacks.isEmpty()&&!a.designChrome.queued&&!a.designChrome.metricsPending);
    a.active=true;a.runtime.put("issue","Latest after resume");NetworkMetricsUi.update(a);frame(a);
    check("Resuming metrics derives the current state after a discarded paused callback",WindowNetworkState.liveCalls==1&&a.designChrome.last.state.equals("需检查"));
    a=setup();NetworkMetricsUi.update(a);a.destroyed=true;frame(a);
    check("Destruction before frame suppresses all projection and maintenance",WindowNetworkState.liveCalls==0&&UiPerfStats.metrics==0&&WindowNetworkState.snapshots.size()==0);
    NetworkMetricsUi.update(a);a.designChrome.update();check("Destroyed callers cannot enqueue later work",a.toolbar.callbacks.isEmpty());
    a=setup();NetworkMetricsUi.update(a);a.designChrome.cancelUpdates();
    check("Cancellation removes scheduled callback and clears both pending flags",a.toolbar.callbacks.isEmpty()&&!a.designChrome.queued&&!a.designChrome.metricsPending);
    frame(a);check("A cancelled frame performs no work",WindowNetworkState.liveCalls==0&&UiPerfStats.metrics==0);
    a.designChrome.update();frame(a);check("An explicit update after cancellation renders without stale maintenance",WindowNetworkState.liveCalls==1&&UiPerfStats.metrics==0&&WindowNetworkState.snapshots.size()==0);
    a=setup();NetworkMetricsUi.updateNow(a);a.handler.drain();check("Direct metrics updateNow also shares the pending frame",WindowNetworkState.liveCalls==0&&a.toolbar.callbacks.size()==1);frame(a);check("Direct metrics updateNow produces only one observation",WindowNetworkState.liveCalls==1&&UiPerfStats.metrics==1);
  }
  static void persistence()throws Exception{
    MainActivity a=setup();NativeNetwork n=NativeNetwork.get(a);WindowNetworkState.save(a,a.session,n);
    check("Legacy three-argument save derives its own one observation",WindowNetworkState.liveCalls==1&&WindowNetworkState.snapshots.size()==1&&SecretStore.writes==0);
    JSONObject first=WindowNetworkState.projected;WindowNetworkState.snapshots.drain();
    check("Actual async persistence serializes its captured observation",SecretStore.writes==1&&new JSONObject(SecretStore.last).optString("environmentId").equals("scope-a"));
    WindowNetworkState.save(a,a.session,n);check("Existing unchanged-signature throttle is preserved",WindowNetworkState.liveCalls==2&&WindowNetworkState.snapshots.size()==0&&SecretStore.writes==1);
    WindowNetworkState.savedAt=System.currentTimeMillis()-5001;WindowNetworkState.save(a,a.session,n);boolean periodic=WindowNetworkState.snapshots.size()==1;WindowNetworkState.snapshots.drain();
    check("An unchanged healthy snapshot persists again after the original five-second interval",periodic&&SecretStore.writes==2&&new JSONObject(SecretStore.last).optBoolean("connected")&&new JSONObject(SecretStore.last).optString("issue").isEmpty());
    a.runtime.put("issue","changed");WindowNetworkState.save(a,a.session,n);check("A changed readiness signature bypasses throttle immediately",WindowNetworkState.snapshots.size()==1);WindowNetworkState.snapshots.drain();
    n.root=new File("test-runtime");int calls=WindowNetworkState.liveCalls;WindowNetworkState.save(a,a.session,n);
    check("Wrong runtime root returns before projection or persistence",WindowNetworkState.liveCalls==calls&&WindowNetworkState.snapshots.size()==0);
    if(current){
      a=setup();n=NativeNetwork.get(a);JSONObject supplied=J.obj("environmentId","scope-a","generation",2,"connected",true,"issue","supplied");WindowNetworkState.save(a,a.session,n,supplied);
      check("Four-argument save never derives another observation",WindowNetworkState.liveCalls==0&&WindowNetworkState.snapshots.size()==1&&WindowNetworkState.snapshots.captured==supplied);
      WindowNetworkState.save(a,a.session,n,supplied);check("Four-argument save preserves the unchanged-signature throttle",WindowNetworkState.snapshots.size()==1);
      WindowNetworkState.snapshots.drain();check("Four-argument save writes exactly the caller-supplied bytes",SecretStore.writes==1&&new JSONObject(SecretStore.last).optString("issue").equals("supplied"));
      WindowNetworkState.savedAt=System.currentTimeMillis()-5001;WindowNetworkState.save(a,a.session,n,supplied);periodic=WindowNetworkState.snapshots.size()==1;WindowNetworkState.snapshots.drain();
      check("Four-argument save retains periodic unchanged-snapshot persistence",periodic&&SecretStore.writes==2&&WindowNetworkState.liveCalls==0&&new JSONObject(SecretStore.last).optString("issue").equals("supplied"));
      n.root=new File("test-runtime");WindowNetworkState.save(a,a.session,n,J.obj("issue","changed"));check("Four-argument overload preserves the runtime root restriction",WindowNetworkState.snapshots.size()==0&&SecretStore.writes==2);
    }
  }
  public static void main(String[]args)throws Exception{
    batch(false);batch(true);if(current)currentSemantics();persistence();int passed=0;for(int i=0;i<checks.length();i++)if(checks.optJSONObject(i).optBoolean("pass"))passed++;
    System.out.println(J.obj("status",passed==checks.length()?"passed":"failed","passed",passed,"total",checks.length(),"frameCoalesced",current,"checks",checks,"scenarios",scenarios,"actualAndroidExecution",false,"actualNativeTiming",false));if(passed!=checks.length())System.exit(1);
  }
}

class MainActivity extends Context{boolean destroyed,active=true;ChatSession session=new ChatSession();JSONObject runtime;final TaskQueue handler=new TaskQueue();final Toolbar toolbar=new Toolbar();final TextView networkLine=new TextView();DesignChrome designChrome;final NativeNetwork network=new NativeNetwork(this);}
class ChatSession{String environmentId="scope-a";int environmentGeneration=2;boolean offline,networkReady=true;final AuditState audit=new AuditState();boolean internalNetwork(){return true;}}
class AuditState{boolean running;int refreshes;void refresh(boolean force){refreshes++;}boolean canReturnRequestIdentity(){return false;}boolean hasChanges(){return false;}}
class TaskQueue{final ArrayDeque<Runnable> tasks=new ArrayDeque<>();void post(Runnable task){tasks.add(task);}void execute(Runnable task){tasks.add(task);}void clear(){tasks.clear();}int size(){return tasks.size();}void drain(){int count=0;while(!tasks.isEmpty()){if(++count>10000)throw new AssertionError("unbounded callback queue");tasks.remove().run();}}}
class Toolbar{final ArrayDeque<Runnable> callbacks=new ArrayDeque<>();void postOnAnimation(Runnable task){callbacks.add(task);}boolean removeCallbacks(Runnable task){return callbacks.remove(task);}void frame(){List<Runnable> ready=new ArrayList<>(callbacks);callbacks.clear();for(Runnable task:ready)task.run();}}
class View{static final int VISIBLE=0,GONE=8;int visibility=VISIBLE;boolean enabled;CharSequence description="";int getVisibility(){return visibility;}void setVisibility(int value){visibility=value;}void setEnabled(boolean value){enabled=value;}CharSequence getContentDescription(){return description;}void setContentDescription(CharSequence value){description=value;}}
class TextView extends View{CharSequence text="";int color;CharSequence getText(){return text;}void setText(CharSequence value){text=value;}int getCurrentTextColor(){return color;}void setTextColor(int value){color=value;}}
class TextUtils{static boolean equals(CharSequence left,CharSequence right){return Objects.equals(left==null?null:left.toString(),right==null?null:right.toString());}}
class ReferenceUi{static final int TEXT=1;static TextView text(Context context,String text,int size,int color,boolean bold){TextView view=new TextView();view.setText(text);return view;}}
class Ui{static final int MUTED=2;}
class DesignUi{static class Stars{static void refresh(Context context){}}}
class UiPerfStats{static int chrome,metrics;static void chromeUpdate(){chrome++;}static void metricsRefresh(){metrics++;}static void textChange(){}}
class Profiles{static int slot(Context context){return 0;}static Context context(Context context,int slot){return context;}}
class ProfileCatalog{static JSONObject value;static int heartbeats;static final ProfileCatalog instance=new ProfileCatalog();static ProfileCatalog get(Context context){return instance;}JSONObject item(int slot){return J.parse(value.toString());}void heartbeat(ChatSession session,boolean force){heartbeats++;}}
class NetworkRegion{static String region(Context context,String ip){return "";}}
class NetworkCatalog{/* CATALOG_EXIT_ID */static String subscriptionName(JSONObject config){return "controlled subscription";}}
class NativeNetwork{final MainActivity owner;JSONObject settings=new JSONObject();File root=new File("network-runtime");boolean recoveryBlocked;final Traffic traffic=new Traffic();NativeNetwork(MainActivity activity){owner=activity;}static NativeNetwork get(MainActivity activity){return activity.network;}/* NATIVE_METHODS */}
class Traffic{int watches;void watch(boolean value){watches++;}}
class SecretStore{static int writes;static String last;SecretStore(Context context){}void put(String key,byte[] value){if(!key.equals("network-ui"))throw new AssertionError("unexpected persistence key");writes++;last=new String(value,StandardCharsets.UTF_8);}}
class SnapshotExecutor extends TaskQueue{JSONObject captured;@Override void execute(Runnable task){for(Field field:task.getClass().getDeclaredFields())if(JSONObject.class.isAssignableFrom(field.getType()))try{field.setAccessible(true);captured=(JSONObject)field.get(task);}catch(Exception failure){throw new AssertionError(failure);}super.execute(task);}@Override void clear(){super.clear();captured=null;}}
class DesignChrome{
  final MainActivity a;TextView title,compactTitle;final View compact=new View(),diagnosticRow=new View(),diagnosticResults=new View();String profileName;JSONObject profileRow;boolean queued,metricsPending,metadataPending;long metadataAt;WindowNetworkState last;static final TaskQueue metadataReader=new TaskQueue();final Runnable render=this::renderLatest;
  DesignChrome(MainActivity activity){a=activity;/* INITIAL_METADATA */}
  void showNetwork(WindowNetworkState state){last=state;}
  /* CHROME_METHODS */
  /* BASELINE_CHROME_ADAPTER */
}
class NetworkMetricsUi{
  static final WeakHashMap<MainActivity,Refresh> refreshes=new WeakHashMap<>();
  /* METRICS_METHODS */
  static String compact(ChatSession session,NativeNetwork network,long now){return "fallback";}static String line(ChatSession session,NativeNetwork network,long now,long monotonic){return "fallback";}
}
class WindowNetworkState{
  /* STATE_FIELDS */
  /* STATE_IDENTITY */
  /* STATE_CONSTRUCTOR */
  static int liveCalls;static JSONObject projected;static long savedAt;static String savedSignature="";static final SnapshotExecutor snapshots=new SnapshotExecutor();
  static JSONObject live(ChatSession session,NativeNetwork network){liveCalls++;projected=J.parse(network.owner.runtime.toString());NetworkCatalogPut.put(projected,"environmentId",session.environmentId);NetworkCatalogPut.put(projected,"generation",session.environmentGeneration);return projected;}
  /* STATE_SAVE */
  /* BASELINE_SAVE_ADAPTER */
}
class NetworkCatalogPut{static void put(JSONObject object,String key,Object value){try{object.put(key,value);}catch(JSONException failure){throw new IllegalStateException(failure);}}}
class J{static JSONObject obj(Object...args){JSONObject value=new JSONObject();try{for(int i=0;i<args.length;i+=2)value.put((String)args[i],args[i+1]);}catch(JSONException failure){throw new IllegalStateException(failure);}return value;}static JSONObject parse(String text){try{return new JSONObject(text);}catch(JSONException failure){throw new IllegalStateException(failure);}}}
