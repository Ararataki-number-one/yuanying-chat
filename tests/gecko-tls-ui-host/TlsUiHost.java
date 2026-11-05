package local.pocketchat;

import java.io.IOException;
import java.util.*;
import java.util.concurrent.Executor;
import java.util.function.Consumer;
import org.json.*;

/** Executes the complete current production UI with explicit host boundaries. */
public final class TlsUiHost {
  static final String ID="00000000-0000-0000-0000-000000000001",OTHER="00000000-0000-0000-0000-000000000002";
  static final List<String> checks=new ArrayList<>();
  static void check(String name,boolean pass){if(!pass)throw new AssertionError(name);checks.add(name);}
  static void rejects(String name,Runnable action){boolean rejected=false;try{action.run();}catch(IllegalArgumentException expected){rejected=true;}check(name,rejected);}
  static ChatSession session(String mode){ReferenceUi.Modal.all.clear();ReferenceUi.Modal.last=null;android.widget.Spinner.all.clear();DesignUi.messages.clear();return new ChatSession(new GeckoTlsStore.State(new EnvironmentSpec.Identity(2,4,ID),1,GeckoTlsSpec.of(mode)));}
  static MainActivity activity(ChatSession session){return new MainActivity(session);}
  static ReferenceUi.Modal open(MainActivity a){GeckoTlsUi.show(a);a.session.pump();return ReferenceUi.Modal.last;}
  static android.widget.Spinner choices(){return android.widget.Spinner.all.get(android.widget.Spinner.all.size()-1);}
  static String result(ReferenceUi.Modal modal){return ((android.widget.TextView)modal.body.children.get(modal.body.children.size()-1)).text;}
  static String status(ReferenceUi.Modal modal){return ((android.widget.TextView)modal.body.children.get(modal.body.children.size()-2)).text;}
  static String tasks(ChatSession s){return s.pending.toString()+"|"+s.reply+"|"+s.upload+"|"+s.download+"|"+s.operation+"|"+s.draft+"|"+s.web.nativeWrites+"|"+s.web.reloads+"|"+s.web.restarts;}
  static void selections(){
    check("Default picker never guesses native TLS min/max",GeckoTlsUi.selection(0).isDefault()&&!GeckoTlsUi.selection(0).requiresTls13());
    check("Strict picker requests TLS13 only",GeckoTlsUi.selection(1).requiresTls13());
    for(int value:new int[]{-1,2,3,100,Integer.MIN_VALUE,Integer.MAX_VALUE})rejects("Invalid picker position rejects "+value,()->GeckoTlsUi.selection(value));
  }
  static void asynchronousEntry(){
    ChatSession s=session("default");MainActivity a=activity(s);GeckoTlsUi.show(a);
    check("Opening editor only queues writer, never native work",s.environmentIo.size()==1&&s.context.loads==0&&ReferenceUi.Modal.last==null&&s.web.nativeWrites==0);
    s.environmentIo.run();check("Writer loads before posting UI",s.context.loads==1&&s.handler.size()==1&&ReferenceUi.Modal.last==null);
    s.handler.run();ReferenceUi.Modal modal=ReferenceUi.Modal.last;
    check("Full editor validates desired owner before display",modal!=null&&modal.showing&&s.tls.notifications==1);
    check("Exactly kernel default and strict TLS13 options are visible",Arrays.equals(choices().labels,new String[]{"内核默认","仅 TLS 1.3"})&&choices().position==0);
    check("Choice has accessible cold-start label",choices().description.contains("下次冷启动")&&choices().minimumHeight>=48);
    String notes=modal.body.notes.toString();
    check("Editor describes runtime scope and legacy site compatibility",notes.contains("整个 Gecko 运行时")&&notes.contains("只支持旧协议的站点"));
    check("Editor limits policy to Gecko web connections and excludes app-owned Java TLS stacks",notes.contains("网页连接")&&notes.contains("应用独立下载器、连接检查、代理入口自身的 Java 或其他 TLS 栈不在此范围内"));
    check("Editor distinguishes cold boot from reopening a page",notes.contains("关闭页面、返回列表或重新打开界面不等于冷启动")&&notes.contains("不会重载网页、结束任务或自动重启"));
    check("Editor separates native readback from handshake and limits fingerprint claims",notes.contains("两项独立证据")&&notes.contains("不代表完整 TLS 指纹隔离")&&notes.contains("不修改强化保护或 HTTP/2、HTTP/3"));
    check("System WebView unsupported scope is explicit",notes.contains("System WebView 暂无独立 TLS")&&notes.contains("此处不会修改它"));
    check("Unconfirmed native status is not promoted by opening editor",status(modal).contains("尚未取得当前引擎")&&status(modal).contains("网络握手：本设置页未验证"));
    check("Listener attaches only to open editor",s.tls.listeners.size()==1);
    modal.cancel();check("Closing editor removes listener without writing",s.tls.listeners.isEmpty()&&s.context.writes==0&&s.web.nativeWrites==0);
    s=session("tls13");modal=open(activity(s));check("Saved strict policy chooses strict option",choices().position==1);
  }
  static JSONObject nativeStatus(String mode){return J.obj("nativeSettingReadback",true,"desiredRevision",2,"activeBootRevision",1,"activeBootMode",mode,"configuredMin",mode.equals("tls13")?4:3,"configuredMax",4,"defaultMin",mode.equals("tls13")?4:3,"defaultMax",4,"hasUserMin",false,"hasUserMax",false,"wireObservationVerified",false);}
  static void summaries()throws Exception{
    GeckoTlsSpec strict=GeckoTlsSpec.of("tls13");JSONObject good=nativeStatus("default");String summary=GeckoTlsUi.summary(strict,good);
    check("Native preference readback never certifies wire handshakes",summary.contains("原生 TLS 偏好已回读")&&summary.contains("网络握手：本设置页未验证"));
    check("Saved policy and active boot request remain distinct",summary.contains("已保存：仅 TLS 1.3")&&summary.contains("当前启动请求：内核默认")&&summary.contains("有新设置等待"));
    check("Kernel default summary uses actual readback rather than a hardcoded range",summary.contains("TLS 1.2 至 TLS 1.3")&&GeckoTlsUi.summary(strict,nativeStatus("tls13")).contains("当前有效范围：TLS 1.3"));
    for(String field:new String[]{"configuredMin","configuredMax","defaultMin","defaultMax","hasUserMin","hasUserMax","activeBootMode"}){JSONObject missing=nativeStatus("default");missing.remove(field);check("Missing native tuple cannot certify preference "+field,!GeckoTlsUi.summary(strict,missing).contains("偏好已回读"));}
    for(String field:new String[]{"nativeSettingReadback","configuredMin","defaultMax","hasUserMin"}){JSONObject coerced=nativeStatus("default");coerced.put(field,coerced.opt(field).toString());check("String coercion cannot certify native tuple "+field,!GeckoTlsUi.summary(strict,coerced).contains("偏好已回读"));}
    for(String field:new String[]{"configuredMin","defaultMin"})for(int value:new int[]{-1,0,1,2,5,999}){JSONObject old=nativeStatus("default");old.put(field,value);check("Unknown or legacy native protocol is not certified "+field+value,!GeckoTlsUi.summary(strict,old).contains("偏好已回读"));}
    for(String field:new String[]{"hasUserMin","hasUserMax"}){JSONObject user=nativeStatus("default");user.put(field,true);String text=GeckoTlsUi.summary(strict,user);check("Residual USER value is visibly unconfirmed "+field,text.contains("残留手动偏好覆盖")&&!text.contains("偏好已回读"));}
    JSONObject mismatch=nativeStatus("default");mismatch.put("defaultMin",4);check("Effective/default mismatch is not certified",!GeckoTlsUi.summary(strict,mismatch).contains("偏好已回读"));
    JSONObject old=nativeStatus("tls13");old.put("configuredMin",3).put("defaultMin",3);check("Strict startup cannot certify a TLS12-capable range",!GeckoTlsUi.summary(strict,old).contains("偏好已回读"));
    old=nativeStatus("default");old.put("activeBootMode","future");check("Unknown startup mode cannot invent readiness or boot request",!GeckoTlsUi.summary(strict,old).contains("偏好已回读")&&!GeckoTlsUi.summary(strict,old).contains("当前启动请求"));
    check("Null status remains explicitly unknown",GeckoTlsUi.summary(strict,null).contains("尚未取得"));
    old=nativeStatus("default");old.put("wireObservationVerified",true);check("A foreign wire flag cannot certify a handshake in this UI",GeckoTlsUi.summary(strict,old).contains("本设置页未验证"));
  }
  static void actualModalSave(){
    ChatSession s=session("default");MainActivity a=activity(s);ReferenceUi.Modal editor=open(a);choices().setSelection(1);String preserved=tasks(s);Object pending=s.pending;
    editor.primary().click();ReferenceUi.Modal confirmation=ReferenceUi.Modal.last;
    check("Actual save button requires a second explicit confirmation",confirmation!=editor&&confirmation.showing&&!editor.primary().enabled);
    check("Preparing confirmation does not write or touch current work",s.environmentIo.size()==0&&s.context.writes==0&&preserved.equals(tasks(s))&&s.pending==pending);
    String notes=confirmation.notes.toString();
    check("Confirmation states scope true cold start and unchanged tasks",notes.contains("整个 Gecko 运行时")&&notes.contains("下一次真正冷启动")&&notes.contains("回复、上传、下载或草稿")&&notes.contains("不会自动重启"));
    check("Confirmation separates compatibility/default reset from actual wire evidence",notes.contains("真实站点握手验证")&&notes.contains("不承诺固定的版本范围"));
    check("Confirmation cannot describe NSS policy as whole-app TLS",notes.contains("网页连接")&&notes.contains("应用独立下载器、连接检查、代理入口自身的 Java 或其他 TLS 栈不受此设置覆盖"));
    confirmation.cancel();check("Actual cancel restores editor availability and preserves state",editor.primary().enabled&&s.context.writes==0&&s.tls.snapshot().revision==1&&result(editor).contains("已取消")&&preserved.equals(tasks(s)));
    editor.primary().click();ReferenceUi.Modal.last.accept();
    check("Only explicit approval queues a desired write",s.environmentIo.size()==1&&s.context.writes==0&&s.tls.snapshot().revision==1&&preserved.equals(tasks(s)));
    s.environmentIo.run();check("Writer publication precedes UI status update without changing runtime",s.context.writes==1&&s.context.value.revision==2&&s.tls.snapshot().revision==1&&s.tls.bootRevision==1&&s.handler.size()==1&&preserved.equals(tasks(s)));
    s.handler.run();check("Published save updates desired only and displays next cold-start requirement",s.tls.snapshot().revision==2&&s.tls.snapshot().spec.requiresTls13()&&s.tls.bootRevision==1&&result(editor).contains("等待当前环境下一次真正冷启动")&&status(editor).contains("有新设置等待")&&preserved.equals(tasks(s)));
    check("Busy reply upload download operation and draft remain untouched after save",s.reply&&s.upload&&s.download&&s.operation&&s.draft.equals("unsent live input")&&s.pending==pending&&s.web.nativeWrites==0&&s.web.reloads==0&&s.web.restarts==0);
    choices().setSelection(0);editor.primary().click();ReferenceUi.Modal.last.accept();s.pump();check("Same open editor advances its CAS expectation after its own successful save",s.context.writes==2&&s.tls.snapshot().revision==3&&s.tls.snapshot().spec.isDefault()&&result(editor).contains("内核默认"));
    choices().setSelection(100);editor.primary().click();check("Invalid actual picker state remains actionable and does not confirm or save",editor.primary().enabled&&s.context.writes==2&&result(editor).contains("请选择")&&ReferenceUi.Modal.last!=null&&!ReferenceUi.Modal.last.showing);
  }
  static void invalidEntryAndOwner(){
    for(String changed:new String[]{"destroyed","finishing","deleted","replacement"}){
      ChatSession s=session("default");MainActivity a=activity(s);GeckoTlsUi.show(a);s.environmentIo.run();
      if(changed.equals("destroyed"))a.destroyed=true;else if(changed.equals("finishing"))a.finishing=true;else if(changed.equals("deleted"))s.deleted=true;else a.session=session("default");
      s.handler.run();check("Entry completion ignores stale activity/session "+changed,ReferenceUi.Modal.last==null&&s.tls.notifications==0&&s.context.writes==0);
    }
    for(String wrong:new String[]{"slot","generation","uuid"}){
      ChatSession s=session("default");MainActivity a=activity(s);
      s.context.value=new GeckoTlsStore.State(new EnvironmentSpec.Identity(wrong.equals("slot")?3:2,wrong.equals("generation")?5:4,wrong.equals("uuid")?OTHER:ID),1,GeckoTlsSpec.defaults());
      GeckoTlsUi.show(a);s.pump();check("Loaded foreign desired owner cannot open editor "+wrong,ReferenceUi.Modal.last==null&&s.tls.notifications==0&&DesignUi.messages.size()==1&&s.context.writes==0);
    }
    ChatSession s=session("default");s.context.failLoad=true;GeckoTlsUi.show(activity(s));s.pump();check("Load failure retains original state and reports no new setting",ReferenceUi.Modal.last==null&&s.context.writes==0&&s.tls.notifications==0&&DesignUi.messages.get(0).contains("没有应用新设置"));
  }
  static void staleSaveAndFailures(){
    for(String changed:new String[]{"destroyed","finishing","deleted","replacement"}){
      ChatSession s=session("default");MainActivity a=activity(s);List<String> done=new ArrayList<>();GeckoTlsUi.confirm(a,s,s.context.value,GeckoTlsSpec.of("tls13"),done::add);ReferenceUi.Modal confirmation=ReferenceUi.Modal.last;
      if(changed.equals("destroyed"))a.destroyed=true;else if(changed.equals("finishing"))a.finishing=true;else if(changed.equals("deleted"))s.deleted=true;else a.session=session("default");
      confirmation.accept();check("Confirmation cannot enqueue save after stale UI "+changed,s.environmentIo.size()==0&&s.context.writes==0&&done.size()==1&&done.get(0).contains("未保存"));
    }
    ChatSession s=session("default");MainActivity a=activity(s);GeckoTlsStore.State initial=s.context.value;List<String> done=new ArrayList<>();String work=tasks(s);
    GeckoTlsUi.saveDesired(a,s,initial,GeckoTlsSpec.of("tls13"),done::add);s.context.value=new GeckoTlsStore.State(initial.identity,2,GeckoTlsSpec.of("default"));s.pump();
    check("CAS failure never overwrites newer persisted desired value",s.context.writes==0&&s.context.value.revision==2&&s.context.value.spec.isDefault()&&s.tls.snapshot().revision==1&&done.size()==1&&done.get(0).contains("版本已变化")&&work.equals(tasks(s)));
    s=session("default");a=activity(s);done=new ArrayList<>();s.context.failSave=true;GeckoTlsUi.saveDesired(a,s,s.context.value,GeckoTlsSpec.of("tls13"),done::add);s.pump();check("Publication failure preserves current desired and does not claim saved",s.context.writes==0&&s.context.value.revision==1&&s.tls.snapshot().revision==1&&done.get(0).contains("未保存"));
    for(String changed:new String[]{"destroyed","finishing","replacement","deleted"}){
      s=session("default");a=activity(s);done=new ArrayList<>();String preserved=tasks(s);GeckoTlsUi.saveDesired(a,s,s.context.value,GeckoTlsSpec.of("tls13"),done::add);s.environmentIo.run();
      if(changed.equals("destroyed"))a.destroyed=true;else if(changed.equals("finishing"))a.finishing=true;else if(changed.equals("deleted"))s.deleted=true;else a.session=session("default");
      s.handler.run();boolean sameOwner=changed.equals("destroyed")||changed.equals("finishing");
      check("Durable save updates only surviving owner's pending cache after UI change "+changed,s.context.value.revision==2&&s.tls.snapshot().revision==(sameOwner?2:1)&&s.tls.notifications==(sameOwner?1:0)&&s.tls.bootRevision==1&&done.get(0).contains("没有改变正在运行的引擎")&&preserved.equals(tasks(s)));
    }
    s=session("default");a=activity(s);done=new ArrayList<>();GeckoTlsStore.State foreign=new GeckoTlsStore.State(new EnvironmentSpec.Identity(2,5,ID),1,GeckoTlsSpec.defaults());GeckoTlsUi.saveDesired(a,s,foreign,GeckoTlsSpec.of("tls13"),done::add);check("Foreign generation is rejected before writer enqueue",s.environmentIo.size()==0&&done.size()==1&&s.context.writes==0);
    s=session("default");a=activity(s);done=new ArrayList<>();s.context.badSaveOwner=true;GeckoTlsUi.saveDesired(a,s,s.context.value,GeckoTlsSpec.of("tls13"),done::add);s.pump();check("Foreign saved owner cannot be projected into active environment",s.tls.notifications==0&&s.tls.snapshot().revision==1&&(done.get(0).contains("环境")||done.get(0).contains("未保存")));
    s=session("default");a=activity(s);ReferenceUi.Modal editor=open(a);choices().setSelection(1);editor.primary().click();ReferenceUi.Modal.last.accept();s.environmentIo.run();String oldStatus=status(editor),oldResult=result(editor);a.destroyed=true;s.handler.run();
    check("Actual destroyed editor receives no widget writes while durable desired cache is retained",s.tls.snapshot().revision==2&&s.tls.bootRevision==1&&status(editor).equals(oldStatus)&&result(editor).equals(oldResult)&&!editor.primary().enabled&&s.web.nativeWrites==0);
  }
  static void concurrentEditors(){
    ChatSession s=session("default");MainActivity a=activity(s);ReferenceUi.Modal first=open(a);android.widget.Spinner firstChoices=choices();ReferenceUi.Modal second=open(a);android.widget.Spinner secondChoices=choices();String work=tasks(s);
    check("Each open editor subscribes independently to desired status",s.tls.listeners.size()==2&&first.showing&&second.showing);
    secondChoices.setSelection(1);second.primary().click();ReferenceUi.Modal.last.accept();s.pump();
    check("Saving another editor refreshes old editor's desired label without claiming active boot changed",s.context.value.revision==2&&status(first).contains("已保存：仅 TLS 1.3")&&status(first).contains("有新设置等待")&&s.tls.bootRevision==1&&work.equals(tasks(s)));
    firstChoices.setSelection(0);first.primary().click();ReferenceUi.Modal.last.accept();s.pump();
    check("Listener refresh never silently advances stale editor CAS to overwrite newer desired",s.context.writes==1&&s.context.value.revision==2&&s.context.value.spec.requiresTls13()&&result(first).contains("版本已变化")&&status(first).contains("已保存：仅 TLS 1.3")&&work.equals(tasks(s)));
    second.cancel();check("Dismissing one editor leaves the other status listener intact",s.tls.listeners.size()==1&&first.showing);
  }
  public static void main(String[] args)throws Exception{selections();asynchronousEntry();summaries();actualModalSave();invalidEntryAndOwner();staleSaveAndFailures();concurrentEditors();System.out.println(J.obj("schema",1,"status","passed","passed",checks.size(),"total",checks.size(),"checks",new JSONArray(checks)));}
}

final class Queue implements Executor {
  static Queue current;final String name;final ArrayDeque<Runnable> tasks=new ArrayDeque<>();Queue(String name){this.name=name;}public void execute(Runnable task){tasks.add(task);}boolean post(Runnable task){tasks.add(task);return true;}int size(){return tasks.size();}
  void run(){Queue prior=current;current=this;try{while(!tasks.isEmpty())tasks.remove().run();}finally{current=prior;}}
}
final class TestContext {GeckoTlsStore.State value;int loads,writes;boolean failLoad,failSave,badSaveOwner;Queue writer;TestContext(GeckoTlsStore.State state){value=state;}}
final class Profiles {static int slot(TestContext context){return 2;}}
final class GeckoTlsStore {
  static final class State {final EnvironmentSpec.Identity identity;final long revision;final GeckoTlsSpec spec;State(EnvironmentSpec.Identity identity,long revision,GeckoTlsSpec spec){this.identity=identity;this.revision=revision;this.spec=spec;}}
  static void writer(TestContext context){if(Queue.current!=context.writer)throw new AssertionError("Vault boundary must only run on environment writer");}
  static State load(TestContext context)throws IOException{writer(context);context.loads++;if(context.failLoad)throw new IOException("Synthetic vault read failure");return context.value;}
  static State save(TestContext context,EnvironmentSpec.Identity expected,long revision,GeckoTlsSpec desired)throws IOException{writer(context);if(context.failSave||!context.value.identity.equals(expected)||context.value.revision!=revision)throw new IOException("Synthetic CAS/publication rejection");if(context.badSaveOwner)return new State(new EnvironmentSpec.Identity(2,5,TlsUiHost.OTHER),2,desired);if(context.value.spec.equals(desired))return context.value;context.writes++;return context.value=new State(expected,revision+1,desired);}
}
final class GeckoTlsController {
  GeckoTlsStore.State cached;long bootRevision=1;int notifications;final Set<Runnable> listeners=new HashSet<>();Object ack=false,rfp=false;
  GeckoTlsController(GeckoTlsStore.State state){cached=state;}
  void desiredSaved(GeckoTlsStore.State state){if(Queue.current==null||!Queue.current.name.equals("main"))throw new AssertionError("Controller desired cache updates on UI lane");cached=state;notifications++;for(Runnable r:new ArrayList<>(listeners))r.run();}
  JSONObject status(){return J.obj("desiredRevision",cached.revision,"activeBootRevision",bootRevision,"activeBootMode","default","nativeSettingReadback",ack,"rfpPriority",rfp,"scope","runtime-wide","workerCoverageVerified",false);}
  GeckoTlsStore.State snapshot(){return cached;}void addListener(Runnable listener){listeners.add(listener);}void removeListener(Runnable listener){listeners.remove(listener);}
}
final class FakeWeb {int nativeWrites,reloads,restarts;}
final class ChatSession {
  final TestContext context;final Queue environmentIo=new Queue("writer"),handler=new Queue("main");final GeckoTlsController tls;final FakeWeb web=new FakeWeb();
  final String environmentId=TlsUiHost.ID;final int environmentGeneration=4;boolean deleted,reply=true,upload=true,download=true,operation=true;String draft="unsent live input";JSONObject pending=J.obj("job","kept active request");
  ChatSession(GeckoTlsStore.State state){context=new TestContext(state);context.writer=environmentIo;tls=new GeckoTlsController(state);}
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
