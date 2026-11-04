package local.pocketchat;

import java.util.*;
import org.json.JSONObject;

/** Verbatim chat-card methods; Android controls and callback queues are adapters. */
public final class ChatProgressPerformanceHost {
  static final boolean baseline=Boolean.getBoolean("baseline");
  static final List<String> checks=new ArrayList<>();
  static void check(String name,boolean value){if(!value)throw new AssertionError(name);checks.add(name);}
  static JSONObject task(String id,String state,long bytes,long total){return J.obj("id",id,"slot",2,"environmentId","owned-environment","environmentGeneration",4,"name","file.zip","state",state,"received",bytes,"total",total);}
  static void noTextProgress(String name){check(name,Metrics.text==0&&Metrics.progress==0&&Metrics.indeterminate==0&&Metrics.colors==0&&Metrics.enabled==0);}
  public static void main(String[] args)throws Exception{
    MainActivity a=new MainActivity();FileDownloads downloads=new FileDownloads();downloads.task=task("first","downloading",25000,100000);
    ChatDownloadProgressUi ui=new ChatDownloadProgressUi(a,downloads);ui.update();
    check("First snapshot shows owned chat card",ui.card.visibility==View.VISIBLE&&ui.name.text.equals("file.zip"));
    check("First snapshot uses actual byte progress",ui.progress.value==250&&!ui.progress.indeterminate);
    check("First snapshot uses original labels and actions",ui.status.text.equals("下载中")&&ui.primary.text.equals("暂停")&&ui.details.visibility==View.VISIBLE&&ui.cancel.visibility==View.VISIBLE);
    check("Visible chat registers one observer",a.resolver.registers==1&&ui.observing);
    Metrics.reset();
    for(int i=0;i<100;i++){if(i%2==0)ui.update();else ui.observer.onChange(false);}
    int steadyText=Metrics.text,steadyProgress=Metrics.progress,steadyIndeterminate=Metrics.indeterminate,steadyColors=Metrics.colors;
    check("100 unchanged notifications have expected text writes",steadyText==(baseline?400:0));
    check("100 unchanged notifications have expected progress writes",steadyProgress==(baseline?100:0));
    check("100 unchanged notifications have expected indeterminate writes",steadyIndeterminate==(baseline?100:0));
    check("100 unchanged notifications have expected color writes",steadyColors==(baseline?100:0));
    check("Unchanged notifications do not duplicate observer registration",a.resolver.registers==1&&a.resolver.unregisters==0);

    downloads.task.put("updated",123456L);Metrics.reset();ui.update();
    if(!baseline)noTextProgress("Non-display timestamp change does not touch controls");
    else check("Baseline repaints unchanged display after timestamp",Metrics.text==4&&Metrics.progress==1);
    downloads.task.put("received",25001L);Metrics.reset();ui.update();
    check("Byte change renders even when progress bucket is unchanged",Metrics.text>=4&&Metrics.progress==1&&ui.progress.value==250);
    downloads.task.put("name","renamed.zip");Metrics.reset();ui.update();
    check("Filename change renders immediately",ui.name.text.equals("renamed.zip")&&Metrics.text>=4);
    downloads.task.put("reason","server note");ui.update();
    check("Reason change renders immediately",ui.amount.text.contains("server note"));
    downloads.task.put("total",50000L);ui.update();
    check("Total-size change recomputes actual progress",ui.progress.value==500&&!ui.progress.indeterminate);
    downloads.task.put("total",-1L);ui.update();
    check("Unknown total changes to indeterminate progress",ui.progress.indeterminate&&ui.amount.text.contains("文件总大小未知"));
    downloads.task.put("state","paused");ui.update();
    check("Pause renders resume action without busy spinner",ui.primary.text.equals("继续")&&!ui.progress.indeterminate&&ui.status.text.equals("已暂停"));
    downloads.task.put("state","saved");ui.update();
    check("Saved transition reaches measured completion and file action",ui.progress.value==1000&&ui.primary.text.equals("查看文件")&&ui.fold.text.equals("关闭")&&ui.cancel.visibility==View.GONE);
    downloads.task.put("state","failed");ui.update();
    check("Failure transition exposes error color and detail action",ui.status.color==DesignUi.RED&&ui.primary.text.equals("查看详情")&&ui.cancel.visibility==View.VISIBLE);
    DesignUi.RED=31;DesignUi.MUTED=42;Metrics.reset();ui.update();
    check("Theme change invalidates cached controls immediately",Metrics.text>=4&&ui.status.color==31);
    Metrics.reset();ui.update();if(!baseline)noTextProgress("Unchanged new theme returns to zero writes");else check("Baseline keeps painting unchanged theme",Metrics.text==4);

    downloads.task=task("second","downloading",1000,10000);ui.collapsed=true;ui.update();
    check("New task resets previous collapse state",!ui.collapsed&&ui.details.visibility==View.VISIBLE&&ui.name.text.equals("file.zip"));
    ui.collapsed=true;Metrics.reset();ui.update();
    check("Collapse change renders immediately",Metrics.text>=4&&ui.details.visibility==View.GONE&&ui.fold.text.equals("展开"));
    Metrics.reset();ui.update();if(!baseline)noTextProgress("Unchanged collapsed card does not repaint");else check("Baseline repaints unchanged collapsed card",Metrics.text==4);
    ui.collapsed=false;ui.update();check("Expand restores details and fold action",ui.details.visibility==View.VISIBLE&&ui.fold.text.equals("收起"));

    downloads.task.put("state","saved");ui.update();ui.dismissed="second";Metrics.reset();ui.update();
    check("Dismissed completed card remains hidden",ui.card.visibility==View.GONE);noTextProgress("Dismissed card does not touch text or progress");
    downloads.task.put("state","downloading");ui.update();
    check("Busy same task clears stale dismissal",ui.dismissed.isEmpty()&&ui.card.visibility==View.VISIBLE);
    downloads.task.put("environmentGeneration",5);Metrics.reset();ui.update();
    check("Stale owner generation hides card",ui.card.visibility==View.GONE);noTextProgress("Stale generation produces no text/progress writes");
    downloads.task.put("environmentGeneration",4);downloads.task.put("environmentId","replacement");Metrics.reset();ui.update();
    check("Replaced environment hides card",ui.card.visibility==View.GONE);noTextProgress("Stale environment produces no text/progress writes");
    downloads.task.put("environmentId","owned-environment");downloads.task.put("slot",3);Metrics.reset();ui.update();
    check("Another slot cannot show the card",ui.card.visibility==View.GONE);noTextProgress("Another slot produces no text/progress writes");
    downloads.task.put("slot",2);a.session.deleted=true;Metrics.reset();ui.update();
    check("Deleted owner hides card",ui.card.visibility==View.GONE);noTextProgress("Deleted owner produces no text/progress writes");
    a.session.deleted=false;a.active=false;Metrics.reset();ui.update();
    check("Background transition unregisters observer and hides card",a.resolver.unregisters==1&&!ui.observing&&ui.card.visibility==View.GONE);noTextProgress("Hidden activity performs no text/progress work");
    a.active=true;ui.update();check("Foreground resume re-registers exactly once",a.resolver.registers==2&&ui.observing&&ui.card.visibility==View.VISIBLE);

    android.os.Looper.main=false;Metrics.reset();ui.update();
    check("Worker notification marshals one update to main",a.handler.jobs.size()==1);noTextProgress("Worker notification does not mutate controls");
    android.os.Looper.main=true;a.handler.one();check("Marshalled update consumes its main callback",a.handler.jobs.isEmpty());
    if(!baseline)noTextProgress("Marshalled unchanged update remains a no-op");else check("Baseline marshalled update repaints",Metrics.text==4);
    a.hub.page=AppHub.SETTINGS;Metrics.reset();ui.update();
    check("Native workspace hides chat card and observer",ui.card.visibility==View.GONE&&!ui.observing);noTextProgress("Native workspace does not render chat progress");
    a.hub.page=AppHub.CHAT;downloads.task=null;Metrics.reset();ui.update();
    check("Missing task hides card",ui.card.visibility==View.GONE);noTextProgress("Missing task performs no text/progress work");
    a.destroyed=true;Metrics.reset();ui.update();check("Destroyed activity unregisters observer",!ui.observing);noTextProgress("Destroyed activity does not render controls");

    System.out.println(J.obj("status","passed","passed",checks.size(),"total",checks.size(),"baseline",baseline,
      "unchangedNotifications",100,"unchangedTextWrites",steadyText,"unchangedProgressWrites",steadyProgress,
      "unchangedIndeterminateWrites",steadyIndeterminate,"unchangedColorWrites",steadyColors,"checks",new org.json.JSONArray(checks)));
  }
}

final class ChatDownloadProgressUi {
  final MainActivity a;final FileDownloads downloads;
  final View card=new View(),details=new View(),actions=new View();
  final TextView name=new TextView(),status=new TextView(),amount=new TextView();
  final ProgressBar progress=new ProgressBar();final Button fold=new Button(),primary=new Button(),cancel=new Button();
  boolean observing,collapsed;String shown="",dismissed="";final ContentObserver observer;
  ChatDownloadProgress rendered;boolean renderedCollapsed;int renderedRed,renderedMuted;
  ChatDownloadProgressUi(MainActivity a,FileDownloads downloads){this.a=a;this.downloads=downloads;a.card=this;/* OBSERVER_INITIALIZATION */}
  /* PRODUCTION_METHODS */
}
final class Metrics {
  static int text,progress,indeterminate,colors,enabled;
  static void reset(){text=progress=indeterminate=colors=enabled=0;}
}
class View {
  static final int VISIBLE=0,GONE=8;int visibility=VISIBLE;
  void setVisibility(int value){visibility=value;}
}
class TextView extends View {
  String text="";int color;
  void setText(String value){Metrics.text++;text=value;}
  String getText(){return text;}
  void setTextColor(int value){Metrics.colors++;color=value;}
}
final class Button extends TextView {boolean enabled;void setEnabled(boolean value){Metrics.enabled++;enabled=value;}}
final class ProgressBar extends View {
  boolean indeterminate;int value;
  void setIndeterminate(boolean value){Metrics.indeterminate++;indeterminate=value;}
  boolean isIndeterminate(){return indeterminate;}
  void setProgress(int value){Metrics.progress++;this.value=value;}
}
abstract class ContentObserver {ContentObserver(Handler handler){}public abstract void onChange(boolean self);}
final class Handler {final Deque<Runnable> jobs=new ArrayDeque<>();void post(Runnable job){jobs.addLast(job);}void one(){jobs.removeFirst().run();}}
final class Resolver {int registers,unregisters;void registerContentObserver(Object uri,boolean descendants,ContentObserver observer){registers++;}void unregisterContentObserver(ContentObserver observer){unregisters++;}}
final class MainActivity {boolean active=true,destroyed;ChatDownloadProgressUi card;AppHub hub=new AppHub();ChatSession session=new ChatSession();final Handler handler=new Handler();final Resolver resolver=new Resolver();Resolver getContentResolver(){return resolver;}void requestPresentationUi(){if(card!=null)card.update();}}
final class ChatSession {boolean deleted;String environmentId="owned-environment";int environmentGeneration=4;}
final class AppHub {static final int CHAT=0,SETTINGS=3;int page=CHAT;}
final class FileDownloads {JSONObject task;}
final class Profiles {static int slot(MainActivity a){return 2;}}
final class DownloadLibraryChanges {static Object uri(MainActivity a){return "controlled-download-notification";}}
final class DesignUi {static int RED=10,MUTED=20;}
final class DownloadTasks {/* LABEL_METHOD */ /* AMOUNT_METHOD */}
final class Attachments {/* SIZE_METHOD */}
