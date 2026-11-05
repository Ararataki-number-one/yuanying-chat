package local.pocketchat;

import java.io.IOException;
import java.util.*;
import java.util.concurrent.Executor;
import java.util.function.Consumer;
import org.json.*;

/** Executes the complete current production UI with explicit host boundaries. */
public final class CpuUiHost {
  static final String ID="00000000-0000-0000-0000-000000000001",OTHER="00000000-0000-0000-0000-000000000002";
  static final List<String> checks=new ArrayList<>();
  static void check(String name,boolean pass){if(!pass)throw new AssertionError(name);checks.add(name);}
  static void rejects(String name,Runnable action){boolean rejected=false;try{action.run();}catch(IllegalArgumentException expected){rejected=true;}check(name,rejected);}
  static ChatSession session(String mode){ReferenceUi.Modal.all.clear();ReferenceUi.Modal.last=null;android.widget.Spinner.all.clear();DesignUi.messages.clear();return new ChatSession(new GeckoCpuStore.State(new EnvironmentSpec.Identity(2,4,ID),1,GeckoCpuSpec.of(mode)));}
  static MainActivity activity(ChatSession session){return new MainActivity(session);}
  static ReferenceUi.Modal open(MainActivity a){GeckoCpuUi.show(a);a.session.pump();return ReferenceUi.Modal.last;}
  static android.widget.Spinner choices(){return android.widget.Spinner.all.get(android.widget.Spinner.all.size()-1);}
  static String result(ReferenceUi.Modal modal){return ((android.widget.TextView)modal.body.children.get(modal.body.children.size()-1)).text;}
  static String status(ReferenceUi.Modal modal){return ((android.widget.TextView)modal.body.children.get(modal.body.children.size()-2)).text;}
  static String tasks(ChatSession s){return s.pending.toString()+"|"+s.reply+"|"+s.upload+"|"+s.download+"|"+s.operation+"|"+s.draft+"|"+s.web.nativeWrites+"|"+s.web.reloads+"|"+s.web.restarts;}
  static void selections(){
    check("Automatic selects native default without inventing a physical CPU value",GeckoCpuUi.selection(0).isAutomatic()&&GeckoCpuUi.selection(0).capOrNull()==null);
    check("Visible option one means upper bound one",GeckoCpuUi.selection(1).capOrNull().intValue()==1);
    check("Visible option two means upper bound two",GeckoCpuUi.selection(2).capOrNull().intValue()==2);
    for(int value:new int[]{-1,3,100,Integer.MIN_VALUE,Integer.MAX_VALUE})rejects("Invalid spinner index is rejected "+value,()->GeckoCpuUi.selection(value));
  }
  static void asynchronousEntry(){
    ChatSession s=session("automatic");MainActivity a=activity(s);GeckoCpuUi.show(a);
    check("Opening entry only queues the environment writer",s.environmentIo.size()==1&&s.context.loads==0&&ReferenceUi.Modal.last==null);
    s.environmentIo.run();check("Desired state is loaded on writer before posting UI",s.context.loads==1&&s.handler.size()==1&&ReferenceUi.Modal.last==null&&s.cpu.notifications==0);
    s.handler.run();ReferenceUi.Modal modal=ReferenceUi.Modal.last;
    check("Full production editor opens only after loaded identity validation",modal!=null&&modal.showing&&s.cpu.notifications==1);
    check("Exact visible choices are default one and two",Arrays.equals(choices().labels,new String[]{"内核默认","最多 1","最多 2"})&&choices().position==0);
    check("Visible choice explicitly identifies next cold boot",choices().description.contains("下次冷启动")&&choices().minimumHeight>=48);
    String notes=modal.body.notes.toString();
    check("Editor explains runtime shared scope and absence of per-page isolation",notes.contains("整个 Gecko 运行时共用")&&notes.contains("不是单个网页的独立覆盖")&&notes.contains("不限制手机实际 CPU"));
    check("Editor distinguishes true cold start from closing a page",notes.contains("关闭页面、返回列表或重新打开界面不等于冷启动")&&notes.contains("不会重载网页、结束任务或自动重启"));
    check("Editor preserves RFP and separates native preference from public observations",notes.contains("强化保护保持优先")&&notes.contains("原生偏好回读与页面、Worker 的实际值分别记录"));
    check("Editor exposes deferred save label and no synthetic native confirmation",modal.primary().text.equals("保存供下次冷启动")&&status(modal).contains("尚未取得当前引擎"));
    check("Listener is attached while editor is open",s.cpu.listeners.size()==1);
    modal.cancel();check("Closing editor removes listener without writing desired state",s.cpu.listeners.isEmpty()&&s.context.writes==0&&s.web.nativeWrites==0);
    for(String mode:new String[]{"1","2"}){s=session(mode);modal=open(activity(s));check("Saved cap chooses corresponding visible option "+mode,choices().position==Integer.parseInt(mode));}
  }
  static void summaries(){
    GeckoCpuSpec one=GeckoCpuSpec.of("1");
    String summary=GeckoCpuUi.summary(one,J.obj("nativeSettingReadback",true,"rfpPriority",false,"desiredRevision",2,"activeBootRevision",1,"activeBootMode","automatic"));
    check("Confirmed native preference stays distinct from page and Worker verification",summary.contains("原生偏好已回读")&&summary.contains("页面和 Worker 尚需分别观测"));
    check("New desired revision explicitly waits for true cold start",summary.contains("有新设置等待当前环境下一次真正冷启动"));
    check("Summary separately names saved desired cap and actual startup request",summary.contains("已保存：最多 1")&&summary.contains("当前启动请求：内核默认"));
    check("Summary never describes runtime preference as per-page isolation",summary.contains("整个 Gecko 运行时共用，不是单个网页的独立值"));
    String stringAck=GeckoCpuUi.summary(one,J.obj("nativeSettingReadback","true","rfpPriority",false));
    check("String native ACK cannot coerce confirmation",stringAck.contains("尚未取得当前引擎")&&!stringAck.contains("原生偏好已回读"));
    String rfp=GeckoCpuUi.summary(one,J.obj("nativeSettingReadback",true,"rfpPriority",true));
    check("RFP priority overrides even a confirmed preference in visible summary",rfp.contains("强化保护优先；不以保存值承诺网页可见上限")&&!rfp.contains("原生偏好已回读"));
    String automatic=GeckoCpuUi.summary(GeckoCpuSpec.automatic(),J.obj());check("Unknown automatic state cannot inherit an applied CPU count",automatic.contains("内核默认")&&automatic.contains("尚未取得当前引擎"));
    check("Unknown startup mode cannot be promoted into a fabricated startup request",!GeckoCpuUi.summary(one,J.obj("activeBootMode","999")).contains("当前启动请求"));
  }
  static void actualModalSave(){
    ChatSession s=session("automatic");MainActivity a=activity(s);ReferenceUi.Modal editor=open(a);choices().setSelection(1);String preserved=tasks(s);Object pending=s.pending;
    editor.primary().click();ReferenceUi.Modal confirmation=ReferenceUi.Modal.last;
    check("Actual save button requires a second explicit confirmation",confirmation!=editor&&confirmation.showing&&!editor.primary().enabled);
    check("Preparing confirmation does not write or touch current work",s.environmentIo.size()==0&&s.context.writes==0&&preserved.equals(tasks(s))&&s.pending==pending);
    String notes=confirmation.notes.toString();
    check("Confirmation states scope true cold start and unchanged tasks",notes.contains("整个 Gecko 运行时")&&notes.contains("下一次真正冷启动")&&notes.contains("回复、上传、下载或草稿")&&notes.contains("不会自动重启"));
    check("Confirmation cannot imply old Service Worker coverage or lower RFP",notes.contains("强化保护不会减弱")&&notes.contains("旧 Worker 或 Service Worker 全部验证"));
    confirmation.cancel();check("Actual cancel restores editor availability and preserves state",editor.primary().enabled&&s.context.writes==0&&s.cpu.snapshot().revision==1&&result(editor).contains("已取消")&&preserved.equals(tasks(s)));
    editor.primary().click();ReferenceUi.Modal.last.accept();
    check("Only explicit approval queues a desired write",s.environmentIo.size()==1&&s.context.writes==0&&s.cpu.snapshot().revision==1&&preserved.equals(tasks(s)));
    s.environmentIo.run();check("Writer publication precedes UI status update without changing runtime",s.context.writes==1&&s.context.value.revision==2&&s.cpu.snapshot().revision==1&&s.cpu.bootRevision==1&&s.handler.size()==1&&preserved.equals(tasks(s)));
    s.handler.run();check("Published save updates desired only and displays next cold-start requirement",s.cpu.snapshot().revision==2&&s.cpu.snapshot().spec.capOrNull()==1&&s.cpu.bootRevision==1&&result(editor).contains("等待当前环境下一次真正冷启动")&&status(editor).contains("有新设置等待")&&preserved.equals(tasks(s)));
    check("Busy reply upload download operation and draft remain untouched after save",s.reply&&s.upload&&s.download&&s.operation&&s.draft.equals("unsent live input")&&s.pending==pending&&s.web.nativeWrites==0&&s.web.reloads==0&&s.web.restarts==0);
    choices().setSelection(2);editor.primary().click();ReferenceUi.Modal.last.accept();s.pump();check("Same open editor advances its CAS expectation after its own successful save",s.context.writes==2&&s.cpu.snapshot().revision==3&&s.cpu.snapshot().spec.capOrNull()==2&&result(editor).contains("最多 2"));
    choices().setSelection(100);editor.primary().click();check("Invalid actual picker state remains actionable and does not confirm or save",editor.primary().enabled&&s.context.writes==2&&result(editor).contains("请选择")&&ReferenceUi.Modal.last!=null&&!ReferenceUi.Modal.last.showing);
  }
  static void invalidEntryAndOwner(){
    for(String changed:new String[]{"destroyed","finishing","deleted","replacement"}){
      ChatSession s=session("automatic");MainActivity a=activity(s);GeckoCpuUi.show(a);s.environmentIo.run();
      if(changed.equals("destroyed"))a.destroyed=true;else if(changed.equals("finishing"))a.finishing=true;else if(changed.equals("deleted"))s.deleted=true;else a.session=session("automatic");
      s.handler.run();check("Entry completion ignores stale activity/session "+changed,ReferenceUi.Modal.last==null&&s.cpu.notifications==0&&s.context.writes==0);
    }
    for(String wrong:new String[]{"slot","generation","uuid"}){
      ChatSession s=session("automatic");MainActivity a=activity(s);
      s.context.value=new GeckoCpuStore.State(new EnvironmentSpec.Identity(wrong.equals("slot")?3:2,wrong.equals("generation")?5:4,wrong.equals("uuid")?OTHER:ID),1,GeckoCpuSpec.automatic());
      GeckoCpuUi.show(a);s.pump();check("Loaded foreign desired owner cannot open editor "+wrong,ReferenceUi.Modal.last==null&&s.cpu.notifications==0&&DesignUi.messages.size()==1&&s.context.writes==0);
    }
    ChatSession s=session("automatic");s.context.failLoad=true;GeckoCpuUi.show(activity(s));s.pump();check("Load failure retains original state and reports no new setting",ReferenceUi.Modal.last==null&&s.context.writes==0&&s.cpu.notifications==0&&DesignUi.messages.get(0).contains("没有应用新设置"));
  }
  static void staleSaveAndFailures(){
    for(String changed:new String[]{"destroyed","finishing","deleted","replacement"}){
      ChatSession s=session("automatic");MainActivity a=activity(s);List<String> done=new ArrayList<>();GeckoCpuUi.confirm(a,s,s.context.value,GeckoCpuSpec.of("1"),done::add);ReferenceUi.Modal confirmation=ReferenceUi.Modal.last;
      if(changed.equals("destroyed"))a.destroyed=true;else if(changed.equals("finishing"))a.finishing=true;else if(changed.equals("deleted"))s.deleted=true;else a.session=session("automatic");
      confirmation.accept();check("Confirmation cannot enqueue save after stale UI "+changed,s.environmentIo.size()==0&&s.context.writes==0&&done.size()==1&&done.get(0).contains("未保存"));
    }
    ChatSession s=session("automatic");MainActivity a=activity(s);GeckoCpuStore.State initial=s.context.value;List<String> done=new ArrayList<>();String work=tasks(s);
    GeckoCpuUi.saveDesired(a,s,initial,GeckoCpuSpec.of("1"),done::add);s.context.value=new GeckoCpuStore.State(initial.identity,2,GeckoCpuSpec.of("2"));s.pump();
    check("CAS failure never overwrites newer persisted desired value",s.context.writes==0&&s.context.value.revision==2&&s.context.value.spec.capOrNull()==2&&s.cpu.snapshot().revision==1&&done.size()==1&&done.get(0).contains("版本已变化")&&work.equals(tasks(s)));
    s=session("automatic");a=activity(s);done=new ArrayList<>();s.context.failSave=true;GeckoCpuUi.saveDesired(a,s,s.context.value,GeckoCpuSpec.of("1"),done::add);s.pump();check("Publication failure preserves current desired and does not claim saved",s.context.writes==0&&s.context.value.revision==1&&s.cpu.snapshot().revision==1&&done.get(0).contains("未保存"));
    for(String changed:new String[]{"destroyed","finishing","replacement","deleted"}){
      s=session("automatic");a=activity(s);done=new ArrayList<>();String preserved=tasks(s);GeckoCpuUi.saveDesired(a,s,s.context.value,GeckoCpuSpec.of("1"),done::add);s.environmentIo.run();
      if(changed.equals("destroyed"))a.destroyed=true;else if(changed.equals("finishing"))a.finishing=true;else if(changed.equals("deleted"))s.deleted=true;else a.session=session("automatic");
      s.handler.run();boolean sameOwner=changed.equals("destroyed")||changed.equals("finishing");
      check("Durable save updates only surviving owner's pending cache after UI change "+changed,s.context.value.revision==2&&s.cpu.snapshot().revision==(sameOwner?2:1)&&s.cpu.notifications==(sameOwner?1:0)&&s.cpu.bootRevision==1&&done.get(0).contains("没有改变正在运行的引擎")&&preserved.equals(tasks(s)));
    }
    s=session("automatic");a=activity(s);done=new ArrayList<>();GeckoCpuStore.State foreign=new GeckoCpuStore.State(new EnvironmentSpec.Identity(2,5,ID),1,GeckoCpuSpec.automatic());GeckoCpuUi.saveDesired(a,s,foreign,GeckoCpuSpec.of("1"),done::add);check("Foreign generation is rejected before writer enqueue",s.environmentIo.size()==0&&done.size()==1&&s.context.writes==0);
    s=session("automatic");a=activity(s);done=new ArrayList<>();s.context.badSaveOwner=true;GeckoCpuUi.saveDesired(a,s,s.context.value,GeckoCpuSpec.of("1"),done::add);s.pump();check("Foreign saved owner cannot be projected into active environment",s.cpu.notifications==0&&s.cpu.snapshot().revision==1&&(done.get(0).contains("环境")||done.get(0).contains("未保存")));
    s=session("automatic");a=activity(s);ReferenceUi.Modal editor=open(a);choices().setSelection(1);editor.primary().click();ReferenceUi.Modal.last.accept();s.environmentIo.run();String oldStatus=status(editor),oldResult=result(editor);a.destroyed=true;s.handler.run();
    check("Actual destroyed editor receives no widget writes while durable desired cache is retained",s.cpu.snapshot().revision==2&&s.cpu.bootRevision==1&&status(editor).equals(oldStatus)&&result(editor).equals(oldResult)&&!editor.primary().enabled&&s.web.nativeWrites==0);
  }
  static void concurrentEditors(){
    ChatSession s=session("automatic");MainActivity a=activity(s);ReferenceUi.Modal first=open(a);android.widget.Spinner firstChoices=choices();ReferenceUi.Modal second=open(a);android.widget.Spinner secondChoices=choices();String work=tasks(s);
    check("Each open editor subscribes independently to desired status",s.cpu.listeners.size()==2&&first.showing&&second.showing);
    secondChoices.setSelection(2);second.primary().click();ReferenceUi.Modal.last.accept();s.pump();
    check("Saving another editor refreshes old editor's desired label without claiming active boot changed",s.context.value.revision==2&&status(first).contains("已保存：最多 2")&&status(first).contains("有新设置等待")&&s.cpu.bootRevision==1&&work.equals(tasks(s)));
    firstChoices.setSelection(1);first.primary().click();ReferenceUi.Modal.last.accept();s.pump();
    check("Listener refresh never silently advances stale editor CAS to overwrite newer desired",s.context.writes==1&&s.context.value.revision==2&&s.context.value.spec.capOrNull()==2&&result(first).contains("版本已变化")&&status(first).contains("已保存：最多 2")&&work.equals(tasks(s)));
    second.cancel();check("Dismissing one editor leaves the other status listener intact",s.cpu.listeners.size()==1&&first.showing);
  }
  public static void main(String[] args){selections();asynchronousEntry();summaries();actualModalSave();invalidEntryAndOwner();staleSaveAndFailures();concurrentEditors();System.out.println(J.obj("schema",1,"status","passed","passed",checks.size(),"total",checks.size(),"checks",new JSONArray(checks)));}
}

final class Queue implements Executor {
  static Queue current;final String name;final ArrayDeque<Runnable> tasks=new ArrayDeque<>();Queue(String name){this.name=name;}public void execute(Runnable task){tasks.add(task);}boolean post(Runnable task){tasks.add(task);return true;}int size(){return tasks.size();}
  void run(){Queue prior=current;current=this;try{while(!tasks.isEmpty())tasks.remove().run();}finally{current=prior;}}
}
final class TestContext {GeckoCpuStore.State value;int loads,writes;boolean failLoad,failSave,badSaveOwner;Queue writer;TestContext(GeckoCpuStore.State state){value=state;}}
final class Profiles {static int slot(TestContext context){return 2;}}
final class GeckoCpuStore {
  static final class State {final EnvironmentSpec.Identity identity;final long revision;final GeckoCpuSpec spec;State(EnvironmentSpec.Identity identity,long revision,GeckoCpuSpec spec){this.identity=identity;this.revision=revision;this.spec=spec;}}
  static void writer(TestContext context){if(Queue.current!=context.writer)throw new AssertionError("Vault boundary must only run on environment writer");}
  static State load(TestContext context)throws IOException{writer(context);context.loads++;if(context.failLoad)throw new IOException("Synthetic vault read failure");return context.value;}
  static State save(TestContext context,EnvironmentSpec.Identity expected,long revision,GeckoCpuSpec desired)throws IOException{writer(context);if(context.failSave||!context.value.identity.equals(expected)||context.value.revision!=revision)throw new IOException("Synthetic CAS/publication rejection");if(context.badSaveOwner)return new State(new EnvironmentSpec.Identity(2,5,CpuUiHost.OTHER),2,desired);if(context.value.spec.equals(desired))return context.value;context.writes++;return context.value=new State(expected,revision+1,desired);}
}
final class GeckoCpuController {
  GeckoCpuStore.State cached;long bootRevision=1;int notifications;final Set<Runnable> listeners=new HashSet<>();Object ack=false,rfp=false;
  GeckoCpuController(GeckoCpuStore.State state){cached=state;}
  void desiredSaved(GeckoCpuStore.State state){if(Queue.current==null||!Queue.current.name.equals("main"))throw new AssertionError("Controller desired cache updates on UI lane");cached=state;notifications++;for(Runnable r:new ArrayList<>(listeners))r.run();}
  JSONObject status(){return J.obj("desiredRevision",cached.revision,"activeBootRevision",bootRevision,"activeBootMode","automatic","nativeSettingReadback",ack,"rfpPriority",rfp,"scope","runtime-wide","workerCoverageVerified",false);}
  GeckoCpuStore.State snapshot(){return cached;}void addListener(Runnable listener){listeners.add(listener);}void removeListener(Runnable listener){listeners.remove(listener);}
}
final class FakeWeb {int nativeWrites,reloads,restarts;}
final class ChatSession {
  final TestContext context;final Queue environmentIo=new Queue("writer"),handler=new Queue("main");final GeckoCpuController cpu;final FakeWeb web=new FakeWeb();
  final String environmentId=CpuUiHost.ID;final int environmentGeneration=4;boolean deleted,reply=true,upload=true,download=true,operation=true;String draft="unsent live input";JSONObject pending=J.obj("job","kept active request");
  ChatSession(GeckoCpuStore.State state){context=new TestContext(state);context.writer=environmentIo;cpu=new GeckoCpuController(state);}
  void pump(){for(int i=0;i<10&&(environmentIo.size()>0||handler.size()>0);i++){environmentIo.run();handler.run();}if(environmentIo.size()+handler.size()>0)throw new AssertionError("Unbounded queue");}
}
final class MainActivity {ChatSession session;boolean destroyed,finishing;MainActivity(ChatSession session){this.session=session;}boolean isDestroyed(){return destroyed;}boolean isFinishing(){return finishing;}}
final class ReferenceUi {
  static final class Modal {
    static Modal last;static final List<Modal> all=new ArrayList<>();final String title;final android.widget.LinearLayout body=new android.widget.LinearLayout();final android.widget.Button primary=new android.widget.Button();final List<String> notes=new ArrayList<>();Consumer<Object> dismissed;Runnable negative;boolean showing;
    Modal(MainActivity activity,String title){this.title=title;all.add(this);}
    void note(String value){notes.add(value);}void setOnDismissListener(Consumer<Object> listener){dismissed=listener;}void buttons(String left,Runnable no,String right,Runnable yes){negative=no;primary.setText(right);primary.setOnClickListener(yes);}android.widget.Button primary(){return primary;}
    void show(){showing=true;last=this;}boolean isShowing(){return showing;}void dismiss(){showing=false;if(dismissed!=null)dismissed.accept(this);}void accept(){primary.click();}void cancel(){negative.run();}
  }
}
final class DesignUi {
  static final int MUTED=1;static final List<String> messages=new ArrayList<>();static void message(MainActivity activity,String title,String text){messages.add(text);}static void note(android.widget.LinearLayout box,String text){box.notes.add(text);}static int dp(MainActivity activity,int value){return value;}
  static Object spinnerAdapter(MainActivity activity,String[] values){return values.clone();}static android.widget.TextView text(MainActivity activity,String text,int size,int color){android.widget.TextView v=new android.widget.TextView();v.setText(text);return v;}
}
