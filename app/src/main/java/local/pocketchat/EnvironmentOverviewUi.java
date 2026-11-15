package local.pocketchat;

import android.app.Dialog;
import android.content.*;
import android.os.SystemClock;
import android.view.*;
import android.widget.*;
import java.util.*;
import org.json.*;

/** Explicit environment openings share one identity-bound native display. */
final class EnvironmentOverviewUi {
  static final String NONCE="manualEnvironmentOverview",ID="overviewEnvironmentId",SLOT="overviewSlot",GENERATION="overviewGeneration",AT="overviewRequestedAt",SOURCE="overviewSource";
  static final String DIRECT="openBrowserDirect";
  final MainActivity a;final Set<String> consumed=new LinkedHashSet<>();
  Dialog dialog;ChatSession owner;EnvironmentOverviewState state;EnvironmentOverviewDashboard dashboard;boolean checking,painted,openingBrowser;long checkSequence;
  Runnable firstFrame;View firstDecor;ViewTreeObserver.OnDrawListener firstDraw;
  String checkRoute="";long checkEpoch;
  EnvironmentOverviewUi(MainActivity a){this.a=a;String seen=a.getSharedPreferences("environment-overview-display",0).getString("consumed","");for(String nonce:seen.split("\n"))if(!nonce.isEmpty())consumed.add(nonce);}
  static Intent opening(Context context,int slot){
    Intent intent=new Intent(context,Profiles.activity(slot)).putExtra("openWindowAction","chat").addFlags(Intent.FLAG_ACTIVITY_NEW_TASK|Intent.FLAG_ACTIVITY_REORDER_TO_FRONT);
    mark(intent,context,slot);return intent;
  }
  /** Browser entry retains the same one-shot identity as the explicit details view. */
  static Intent browserOpening(Context context,int slot){return opening(context,slot).putExtra(DIRECT,true);}
  static Intent detailsOpening(Context context,int slot){return opening(context,slot).putExtra("openWindowAction","overview");}
  static void mark(Intent intent,Context context,int slot){
    JSONObject row=ProfileCatalog.get(context).item(slot);
    if(!row.optBoolean("created")||row.optBoolean("deleting")||row.optBoolean("resetting"))return;
    intent.putExtra(SOURCE,"environment-list-chat").putExtra(NONCE,UUID.randomUUID().toString()).putExtra(ID,row.optString("environmentId")).putExtra(SLOT,slot).putExtra(GENERATION,row.optInt("generation")).putExtra(AT,SystemClock.elapsedRealtime());
  }
  boolean consume(Intent intent){
    if(intent==null)return false;String source=intent.getStringExtra(SOURCE);String nonce=intent.getStringExtra(NONCE),id=intent.getStringExtra(ID);int slot=intent.getIntExtra(SLOT,-1),generation=intent.getIntExtra(GENERATION,-1);long at=intent.getLongExtra(AT,-1);
    boolean direct=intent.getBooleanExtra(DIRECT,false);intent.removeExtra(DIRECT);
    intent.removeExtra(SOURCE);intent.removeExtra(NONCE);intent.removeExtra(ID);intent.removeExtra(SLOT);intent.removeExtra(GENERATION);intent.removeExtra(AT);
    if(nonce==null){String action=intent.getStringExtra("openWindowAction");if(intent.hasExtra("openConversation")||intent.hasExtra("openDownload")||action!=null&&!"chat".equals(action))close();return false;}
    long now=SystemClock.elapsedRealtime();ChatSession selected=a.session;
    if(!"environment-list-chat".equals(source)||!nonce.matches("[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")||consumed.contains(nonce)||at<0||now<at||now-at>60000
        ||id==null||slot!=Profiles.slot(a)||selected!=null&&(!id.equals(selected.environmentId)||generation!=selected.environmentGeneration||!NetworkStatusUi.current(a,selected))
        ||intent.hasExtra("openConversation")||intent.hasExtra("openDownload"))return false;
    JSONObject row=ProfileCatalog.get(a).item(slot);
    if(!id.equals(row.optString("environmentId"))||generation!=row.optInt("generation",-1)||!ProfileCatalog.get(a).available(slot))return false;
    consumed.add(nonce);if(consumed.size()>32)consumed.remove(consumed.iterator().next());
    if(!a.getSharedPreferences("environment-overview-display",0).edit().putString("consumed",android.text.TextUtils.join("\n",consumed)).commit())return false;
    close();
    // Re-entering a live environment must reveal its existing document, without
    // a dashboard, a reload, or navigation back to the configured homepage.
    if(direct&&selected!=null)return false;
    openingBrowser=direct;
    owner=selected;state=new EnvironmentOverviewState(nonce,id,slot,generation);painted=false;
    Dialog shown=new ThemedDialog(a);
    dialog=shown;shown.requestWindowFeature(Window.FEATURE_NO_TITLE);
    if(direct){
      // A cold open still paints a lightweight native frame before Gecko starts.
      // The existing BrowserStartupGate owns foreground and generation checks.
      LinearLayout starting=DesignUi.column(a);starting.setGravity(Gravity.CENTER);starting.setPadding(a.dp(24),a.dp(24),a.dp(24),a.dp(24));starting.setBackgroundColor(ReferenceUi.CHAT_BG);
      TextView title=ReferenceUi.text(a,Profiles.display(a,slot),18,ReferenceUi.TEXT,true);title.setGravity(Gravity.CENTER);starting.addView(title,new LinearLayout.LayoutParams(-1,-2));
      TextView progress=ReferenceUi.text(a,"正在打开浏览器…",14,ReferenceUi.MUTED,false);progress.setGravity(Gravity.CENTER);progress.setPadding(0,a.dp(12),0,0);starting.addView(progress,new LinearLayout.LayoutParams(-1,-2));
      ReferenceUi.insets(a,starting);shown.setContentView(starting);
    }else{
      dashboard=new EnvironmentOverviewDashboard(a,slot,this::checkRoute,this::queryIp,this::inspectIdentity,this::details,this::close);
      ReferenceUi.insets(a,dashboard);shown.setContentView(dashboard);
    }
    shown.setOnDismissListener(unused->{if(dialog==shown)close();});
    shown.show();Window window=shown.getWindow();if(window!=null){window.clearFlags(WindowManager.LayoutParams.FLAG_DIM_BEHIND);window.setDimAmount(0);if(android.os.Build.VERSION.SDK_INT>=30)window.setDecorFitsSystemWindows(false);window.setLayout(-1,-1);AppAppearance.window(window);}
    render();afterFirstFrame(null);resume();return true;
  }
  boolean current(){
    if(dialog==null||!dialog.isShowing()||state==null||a.isDestroyed()||a.isFinishing()||Profiles.slot(a)!=state.slot)return false;
    if(owner==null&&a.session!=null)owner=a.session;
    if(owner!=null&&(!NetworkStatusUi.current(a,owner)||!state.matches(owner.environmentId,Profiles.slot(a),owner.environmentGeneration)))return false;
    JSONObject row=ProfileCatalog.get(a).item(state.slot);return ProfileCatalog.get(a).available(state.slot)&&state.environmentId.equals(row.optString("environmentId"))&&state.generation==row.optInt("generation",-1);
  }
  void render(){if(!current())return;if(openingBrowser){browserReady();return;}if(dashboard==null)return;if(checking&&owner!=null&&(checkEpoch!=owner.connectionEpoch||!checkRoute.equals(owner.networkIdentity()))){checking=false;checkSequence++;}dashboard.render(EnvironmentOverviewInfo.read(owner),ProfileCatalog.get(a).item(state.slot),owner,checking);}
  void browserReady(){if(openingBrowser&&a.session!=null&&current())close();}
  void afterFirstFrame(Runnable action){
    if(action!=null)firstFrame=action;if(painted||dialog==null||dialog.getWindow()==null){dispatchFirstFrame();return;}if(firstDraw!=null)return;
    firstDecor=dialog.getWindow().getDecorView();firstDraw=()->{painted=true;dispatchFirstFrame();};firstDecor.getViewTreeObserver().addOnDrawListener(firstDraw);firstDecor.invalidate();
  }
  void dispatchFirstFrame(){Runnable action=firstFrame;firstFrame=null;View decor=firstDecor;ViewTreeObserver.OnDrawListener draw=firstDraw;firstDecor=null;firstDraw=null;a.handler.post(()->{if(decor!=null&&draw!=null&&decor.getViewTreeObserver().isAlive())decor.getViewTreeObserver().removeOnDrawListener(draw);if(action!=null&&!a.isDestroyed()&&!a.isFinishing())action.run();});}
  void queryIp(){if(!current()||owner==null)return;close();ExitIpPageUi.open(a);}
  void inspectIdentity(){if(!current()||owner==null)return;close();EnvironmentAuditUi.show(a);}
  void details(){if(!current()||owner==null)return;String ua=owner.web.getSettings().getUserAgentString();ReferenceUi.message(a,"环境信息与来源",EnvironmentOverviewInfo.text(owner)+(ua==null||ua.isEmpty()?"":"\n\n请求 User Agent：\n"+ua));render();}
  void checkRoute(){
    if(!current()||owner==null||checking||!NetworkStatusUi.connectionReady(owner))return;
    ChatSession selected=owner;long sequence=++checkSequence,epoch=selected.connectionEpoch;String route=selected.networkIdentity();checkEpoch=epoch;checkRoute=route;checking=true;render();
    NativeNetwork.Callback done=(ok,message)->{if(!current()||owner!=selected||sequence!=checkSequence||epoch!=selected.connectionEpoch||!route.equals(selected.networkIdentity()))return;checking=false;render();EnvironmentOverviewDashboard.update(dashboard.progress,ok?"当前线路检测完成":"检测未完成，保留上次核验记录");};
    if(selected.internalNetwork()){NativeNetwork network=NativeNetwork.peek();if(network==null){checking=false;render();return;}network.checkExit(done);}else NetworkRegion.refreshLatency(selected,done);
  }
  final Runnable tick=new Runnable(){public void run(){
    a.handler.removeCallbacks(this);if(!current()){close();return;}
    render();a.handler.postDelayed(this,1000);
  }};
  void resume(){a.handler.removeCallbacks(tick);if(dialog!=null)a.handler.post(tick);}
  void pause(){a.handler.removeCallbacks(tick);checkSequence++;checking=false;}
  boolean back(){if(dialog==null)return false;close();return true;}
  void close(){a.handler.removeCallbacks(tick);checkSequence++;checking=false;openingBrowser=false;if(state!=null)state.close();Dialog old=dialog;dialog=null;owner=null;state=null;dashboard=null;if(old!=null)old.dismiss();if(firstFrame!=null||firstDraw!=null)dispatchFirstFrame();}
}
