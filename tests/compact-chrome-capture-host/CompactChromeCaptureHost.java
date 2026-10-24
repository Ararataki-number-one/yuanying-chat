package local.pocketchat;
import android.content.*;import android.os.SystemClock;import android.text.TextUtils;import org.json.*;import java.lang.reflect.*;import java.util.*;

public final class CompactChromeCaptureHost {
  static final JSONArray checks=new JSONArray(),observations=new JSONArray();
  static void check(String name,boolean value){checks.put(J.obj("name",name,"pass",value));}
  static CompactChromeIntegrationActivity setup(){Scheduler.current=new Scheduler();View.views.clear();Log.values.clear();DesignChrome.metadataReader.clear();ProfileCatalog.value=J.obj("slot",0,"name","Controlled title","environmentId","scope-a","generation",2,"created",true);return new CompactChromeIntegrationActivity();}
  static void realRender(CompactChromeIntegrationActivity a){a.designChrome.update();a.handler.runTo(a.handler.now);}
  static boolean realState(CompactChromeIntegrationActivity a){return a.designChrome.latencyWord.getText().equals("延迟未测（等待连接）")&&a.designChrome.stateWord.getText().equals("未配置");}
  static boolean syntheticState(CompactChromeIntegrationActivity a){return a.designChrome.latencyWord.getText().equals("42 ms（02:00）")&&a.designChrome.stateWord.getText().equals("已连接");}
  static boolean released(CompactChromeIntegrationActivity a){return a.presentation==null&&a.presentationListener==null&&a.presentationExpiry==null&&a.toolbar.observer.listeners.isEmpty()&&a.handler.delayedCount()==0;}
  static boolean frame(CompactChromeIntegrationActivity a){for(View v:new ArrayList<>(View.views))v.layout();return a.toolbar.observer.dispatch();}
  static CompactChromeIntegrationActivity overwritten(String purpose){CompactChromeIntegrationActivity a=setup();a.snapshot("ready");a.handler.runTo(200);check("Original 200 ms step paints the synthetic state: "+purpose,syntheticState(a));a.handler.runTo(250);realRender(a);check("Actual queued production render overwrites at 250 ms: "+purpose,realState(a));a.handler.runTo(300);return a;}
  static void before(){CompactChromeIntegrationActivity a=overwritten("report-window");observations.put(J.obj("case","historical-200-250-300-callback-sequence","reports",a.reports,"state",a.designChrome.stateWord.getText(),"latency",a.designChrome.latencyWord.getText(),"recorded",a.records));check("A report must observe the original synthetic latency after the intervening actual render",a.reports==1&&a.records.optJSONObject(0).optString("latency").equals("42 ms（02:00）"));}
  static void current()throws Exception{
    CompactChromeIntegrationActivity a=overwritten("report-window");check("Current capture waits for a pre-draw frame instead of reporting overwritten UI",a.reports==0&&a.presentation!=null);a.handler.runTo(316);boolean first=frame(a);check("Covered first frame repaints through actual showNetwork and defers its report",!first&&a.reports==0&&syntheticState(a)&&a.toolbar.invalidations>=2);a.handler.runTo(332);boolean second=frame(a);check("Next laid-out matching frame reports the unchanged 42 ms and 02:00",second&&a.reports==1&&a.records.optJSONObject(0).optString("latency").equals("42 ms（02:00）")&&a.records.optJSONObject(0).optString("description").contains("42 ms"));check("Successful report detaches listener and deadline callback",released(a));realRender(a);check("After successful release an actual real render updates the UI normally",realState(a));int reports=a.reports;frame(a);check("Later frames cannot report the old capture twice",a.reports==reports);observations.put(J.obj("case","current-200-250-300-316-332-sequence","reports",a.reports,"recorded",a.records,"afterReleaseLatency",a.designChrome.latencyWord.getText()));
    a=setup();a.snapshot("ready");a.handler.runTo(300);a.toolbar.layoutRequested=true;check("Unlaid frame cannot be captured",!a.toolbar.observer.dispatch()&&a.reports==0);frame(a);check("The same capture succeeds after layout actually completes",a.reports==1&&released(a));
    a=setup();a.snapshot("ready");a.handler.runTo(300);for(View v:new ArrayList<>(View.views))v.layout();a.designChrome.latencyWord.setText(a.designChrome.latencyWord.getText());check("Text pending a requested layout is rejected even when its model matches",!a.toolbar.observer.dispatch()&&a.reports==0);frame(a);check("Completing the requested text layout releases the waiting capture",a.reports==1&&released(a));
    a=setup();a.snapshot("ready");a.handler.runTo(300);for(View v:new ArrayList<>(View.views))v.layout();a.networkLine.layoutAvailable=false;check("A missing real text Layout cannot be reported",!a.toolbar.observer.dispatch()&&a.reports==0);frame(a);check("An available Layout completes the existing capture",a.reports==1&&released(a));
    for(String target:new String[]{"title","address"}){
      a=setup();a.snapshot("ready");a.handler.runTo(300);TextView transformed=target.equals("title")?a.designChrome.title:a.networkLine;transformed.ellipsisStart=4;transformed.ellipsisCount=transformed.getText().length()-4;
      boolean drawn=frame(a);CharSequence displayed=transformed.getLayout().getText();
      check("Legal "+target+" ellipsis preserves source length but transforms actual Layout characters",displayed.length()==transformed.getText().length()&&!TextUtils.equals(displayed,transformed.getText())&&displayed.charAt(4)=='\u2026'&&displayed.charAt(5)=='\uFEFF'&&displayed.subSequence(4,6).toString().equals("\u2026\uFEFF"));
      check("A laid-out "+target+" ellipsis reports exact model text without waiting for timeout",drawn&&a.reports==1&&a.records.optJSONObject(0).optString("latency").equals("42 ms（02:00）")&&released(a));
      a.handler.runTo(20000);observations.put(J.obj("case","legal-"+target+"-ellipsis","sourceText",transformed.getText(),"layoutText",displayed.toString(),"reports",a.reports,"errors",Log.failures(),"released",released(a)));
      check("Legal "+target+" ellipsis does not become a deadline error",a.reports==1&&Log.failures()==0&&released(a));
      realRender(a);check("After "+target+" ellipsis capture production rendering remains authoritative",realState(a));
    }
    a=setup();a.snapshot("ready");a.handler.runTo(300);a.handler.runTo(20000);check("Original 20-second deadline fails closed with no success report",a.reports==0&&Log.failures()==1&&released(a));realRender(a);check("Timeout release does not inhibit subsequent production rendering",realState(a));
    a=setup();a.snapshot("ready");a.handler.runTo(300);a.onDestroy();check("Actual destroy callback releases the pending capture",a.destroyed&&a.reports==0&&released(a));frame(a);check("A late frame after destroy cannot publish the old report",a.reports==0&&Log.failures()==0);
    a=setup();a.snapshot("ready");a.handler.runTo(300);a.onNewIntent(new Intent());check("Actual new-intent callback releases prior command capture",a.command.equals("new-command")&&a.reports==0&&released(a));realRender(a);check("New command release leaves real rendering authoritative",realState(a));frame(a);check("New command cannot receive a stale prior report",a.reports==0);
    a=setup();a.snapshot("old");a.handler.runTo(100);a.onNewIntent(new Intent());a.handler.runTo(300);check("New command before the initial paint rejects stale scheduled callbacks",a.reports==0&&a.presentation==null&&!syntheticState(a));
    for(int stage:new int[]{100,250}){a=setup();a.snapshot("old");a.handler.runTo(stage);Intent same=new Intent();same.command=a.command;same.action="performance";a.onNewIntent(same);realRender(a);a.handler.runTo(350);check("Same-command new action invalidates pending capture at "+stage+" ms",a.reports==0&&a.presentation==null&&realState(a)&&a.performanceCalls==1&&a.toolbar.observer.listeners.isEmpty());}
    a=setup();a.snapshot("old");a.handler.runTo(300);a.snapshot("new");a.handler.runTo(600);frame(a);check("Replacement snapshot releases old ownership and reports only the new event",a.reports==1&&a.records.optJSONObject(0).optString("event").equals("new")&&released(a));
    a=setup();a.snapshot("ready");a.handler.runTo(300);a.failReport=true;frame(a);check("Report exception records failure and releases frame ownership once",a.reports==0&&Log.failures()==1&&released(a));realRender(a);check("Report-error release still permits actual real rendering",realState(a));
    a=overwritten("paint-error");a.designChrome.latencyWord.failSet=true;frame(a);check("A paint exception cannot report success and detaches capture",a.reports==0&&Log.failures()==1&&released(a));a.designChrome.latencyWord.failSet=false;realRender(a);check("Paint-error release leaves subsequent actual updates usable",realState(a));
    a=setup();a.toolbar.observer.failAdd=true;a.snapshot("ready");a.handler.runTo(300);check("Listener registration failure reports an error and leaves no ownership",a.reports==0&&Log.failures()==1&&released(a));
    a=setup();a.snapshot("ready");a.handler.runTo(300);CompactChromePresentationCapture old=a.presentation;a.onNewIntent(new Intent());old.beforeDraw(400);old.expire(30000);check("Cancelled helper ignores late frame and deadline callbacks",a.reports==0&&Log.failures()==0&&released(a));
    a=setup();a.snapshot("ready");a.handler.runTo(300);a.command="replaced-without-intent";frame(a);check("Current-command guard independently rejects stale frame ownership",a.reports==0&&Log.failures()==0&&released(a));
    a=setup();a.handler.runTo(2500);realRender(a);a.snapshot("ready");a.handler.runTo(2800);ProfileCatalog.value.put("name","Metadata callback arrived");DesignChrome.metadataReader.drain();a.handler.runTo(2850);check("The original metadata worker callback executes during capture and updates chrome",a.designChrome.title.getText().equals("Metadata callback arrived")&&realState(a)&&a.reports==0);frame(a);frame(a);check("Capture recovers from the actual metadata render without discarding its new title",a.reports==1&&a.designChrome.title.getText().equals("Metadata callback arrived")&&released(a));
  }
  public static void main(String[]args)throws Exception{if(Boolean.getBoolean("before"))before();else current();int passed=0;for(int i=0;i<checks.length();i++)if(checks.optJSONObject(i).optBoolean("pass"))passed++;System.out.println(J.obj("status",passed==checks.length()?"passed":"failed","passed",passed,"total",checks.length(),"checks",checks,"observations",observations));if(passed!=checks.length())System.exit(1);}
}

class CompactChromeIntegrationActivity extends MainActivity{
  int presentationSerial;CompactChromePresentationCapture presentation;ViewTreeObserver presentationObserver;ViewTreeObserver.OnPreDrawListener presentationListener;Runnable presentationExpiry;String command="compact-original";boolean reloadFixture,failReport;ChromeCollapseIntegration collapse;int reports,performanceCalls;final JSONArray records=new JSONArray();DesignChrome designChrome;
  CompactChromeIntegrationActivity(){designChrome=new DesignChrome(this);}
  void report(String event,WindowNetworkState network){if(failReport)throw new IllegalStateException("controlled report exception");reports++;records.put(J.obj("event",event,"latency",designChrome.latencyWord.getText(),"expectedLatency",network.latency+network.latencyTimer,"state",designChrome.stateWord.getText(),"description",designChrome.networkRow.getContentDescription()));}
  void reloadCommand(String action){}void performance(){performanceCalls++;}
  /* FIXTURE_METHODS */
}
class MainActivity extends Context{boolean destroyed;final Session session=new Session();final Scheduler handler=Scheduler.current;final View toolbar=new View();final TextView networkLine=new TextView();final Runnable ticker=()->{};final Object sessionObserver=new Object();JSONObject runtime=J.obj("environmentId","scope-a","generation",2,"at",System.currentTimeMillis(),"mode","external","configured",false,"connected",false,"route","controlled","delayRoute","controlled","delayAt",0);protected void onDestroy(){destroyed=true;}protected void onNewIntent(Intent i){}}
class Session{void remove(Object observer){}}
class ChromeCollapseIntegration{void close(){}}
class DesignChrome{
  final MainActivity a;TextView title,compactTitle;final View compact=new View(),networkRow=new View();final TextView latencyWord=new TextView(),stateWord=new TextView(),dot=new TextView();String profileName;JSONObject profileRow=new JSONObject();boolean queued,metadataPending;long metadataAt;static final WorkQueue metadataReader=new WorkQueue();final Runnable render=this::renderLatest;
  DesignChrome(MainActivity a){this.a=a;/* INITIAL_METADATA */}
  /* CHROME_METHODS */
}
class WindowNetworkState{/* STATE_FIELDS *//* STATE_IDENTITY *//* STATE_METHODS */static JSONObject live(Session s,NativeNetwork n){return n.owner.runtime;}}
class Scheduler{
  static Scheduler current;long now,sequence;final PriorityQueue<Task> tasks=new PriorityQueue<>();static class Task implements Comparable<Task>{final long at,serial;final Runnable run;Task(long at,long serial,Runnable run){this.at=at;this.serial=serial;this.run=run;}public int compareTo(Task other){int by=Long.compare(at,other.at);return by==0?Long.compare(serial,other.serial):by;}}
  Scheduler(){SystemClock.now=0;}void post(Runnable r){postDelayed(r,0);}void postDelayed(Runnable r,long delay){tasks.add(new Task(now+delay,++sequence,r));}void removeCallbacks(Runnable r){tasks.removeIf(t->t.run==r);}int delayedCount(){return tasks.size();}
  void runTo(long until){int count=0;while(!tasks.isEmpty()&&tasks.peek().at<=until){if(++count>2000)throw new AssertionError("Nonterminating controlled callback queue");Task task=tasks.remove();now=task.at;SystemClock.now=now;task.run.run();}now=until;SystemClock.now=now;}
}
class WorkQueue{final ArrayDeque<Runnable> tasks=new ArrayDeque<>();void execute(Runnable r){tasks.add(r);}void clear(){tasks.clear();}void drain(){int count=0;while(!tasks.isEmpty()){if(++count>1000)throw new AssertionError("Unbounded worker queue");tasks.remove().run();}}}
class View{static final List<View> views=new ArrayList<>();final Scheduler scheduler=Scheduler.current;final ViewTreeObserver observer=new ViewTreeObserver();boolean layoutRequested;int invalidations;CharSequence description="";View(){views.add(this);}void postDelayed(Runnable r,long delay){scheduler.postDelayed(r,delay);}void requestLayout(){layoutRequested=true;}void postInvalidateOnAnimation(){invalidations++;}boolean isLaidOut(){return true;}boolean isLayoutRequested(){return layoutRequested;}int getWidth(){return 412;}int getHeight(){return 56;}ViewTreeObserver getViewTreeObserver(){return observer;}CharSequence getContentDescription(){return description;}void setContentDescription(CharSequence value){description=value;}void layout(){layoutRequested=false;}}
class ViewTreeObserver{interface OnPreDrawListener{boolean onPreDraw();}boolean failAdd;final List<OnPreDrawListener> listeners=new ArrayList<>();boolean isAlive(){return true;}void addOnPreDrawListener(OnPreDrawListener listener){if(failAdd)throw new IllegalStateException("controlled listener failure");listeners.add(listener);}void removeOnPreDrawListener(OnPreDrawListener listener){listeners.remove(listener);}boolean dispatch(){boolean allow=true;for(OnPreDrawListener listener:new ArrayList<>(listeners))allow&=listener.onPreDraw();return allow;}}
class TextView extends View{CharSequence text="",layoutText="";int color,ellipsisStart,ellipsisCount;boolean failSet,layoutAvailable;CharSequence getText(){return text;}void setText(CharSequence value){if(failSet)throw new IllegalStateException("controlled text setter failure");text=value;layoutRequested=true;}int getCurrentTextColor(){return color;}void setTextColor(int value){color=value;}TextLayout getLayout(){return layoutAvailable?new TextLayout(layoutText):null;}void layout(){super.layout();layoutText=ellipsisCount==0?text:new EllipsizedText(text,ellipsisStart,ellipsisCount);layoutAvailable=true;}}
// Narrow character adapter for AOSP android-15.0.0_r1 Layout.Ellipsizer / ellipsize:
// caller-supplied line ellipsis range, no font measurement or Android layout simulation.
class EllipsizedText implements CharSequence {
  final CharSequence original;final int start,count;
  EllipsizedText(CharSequence original,int start,int count){this.original=original;this.start=start;this.count=count;}
  public int length(){return original.length();}
  public char charAt(int offset){char[] chars=new char[1];getChars(offset,offset+1,chars,0);return chars[0];}
  public void getChars(int from,int to,char[] dest,int destoff){
    for(int i=from;i<to;i++)dest[destoff+i-from]=original.charAt(i);
    for(int i=Math.max(0,from-start);i<Math.min(count,to-start);i++)dest[destoff+start+i-from]=i==0?'\u2026':'\uFEFF';
  }
  public CharSequence subSequence(int from,int to){char[] chars=new char[to-from];getChars(from,to,chars,0);return new String(chars);}
  public String toString(){return subSequence(0,length()).toString();}
}
class TextLayout{final CharSequence text;TextLayout(CharSequence value){text=value;}CharSequence getText(){return text;}}
class ReferenceUi{static final int TEXT=1,GREEN=2,RED=3,ORANGE=4,MUTED=5;static TextView text(Context a,String value,int size,int color,boolean bold){TextView v=new TextView();v.setText(value);return v;}}
class ProfileCatalog{static JSONObject value;static final ProfileCatalog instance=new ProfileCatalog();static ProfileCatalog get(Context c){return instance;}JSONObject item(int slot){try{return new JSONObject(value.toString());}catch(Exception e){throw new RuntimeException(e);}}String name(int slot){return item(slot).optString("name");}}
class Profiles{static Context context(Context c,int slot){return c;}static int slot(Context c){return 0;}static String display(Context c,int slot){return ProfileCatalog.get(c).name(slot);}}
class DesignUi{static class Stars{static void refresh(Context c){}}}
class UiPerfStats{static void chromeUpdate(){}static void textChange(){}}
class NetworkRegion{static String region(Context c,String ip){return "";}}
class NetworkCatalog{/* CATALOG_EXIT_ID */static String subscriptionName(JSONObject c){return "controlled subscription";}}
class NativeNetwork{MainActivity owner;JSONObject settings=new JSONObject();static NativeNetwork get(MainActivity a){NativeNetwork n=new NativeNetwork();n.owner=a;return n;}/* NATIVE_METHODS */}
class Log{static final List<JSONObject> values=new ArrayList<>();static void i(String tag,String raw){try{values.add(new JSONObject(raw));}catch(Exception e){throw new RuntimeException(e);}}static int failures(){int count=0;for(JSONObject value:values)if(value.has("error"))count++;return count;}}
class J{static JSONObject obj(Object...args){JSONObject value=new JSONObject();try{for(int i=0;i<args.length;i+=2)value.put((String)args[i],args[i+1]);}catch(JSONException e){throw new IllegalStateException(e);}return value;}}
