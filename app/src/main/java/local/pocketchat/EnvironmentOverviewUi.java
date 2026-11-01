package local.pocketchat;

import android.app.Dialog;
import android.content.*;
import android.os.SystemClock;
import android.view.*;
import android.widget.*;
import java.util.*;
import org.json.*;

/** Only a one-shot environment-list intent can open this native display. */
final class EnvironmentOverviewUi {
  static final String NONCE="manualEnvironmentOverview",ID="overviewEnvironmentId",SLOT="overviewSlot",GENERATION="overviewGeneration",AT="overviewRequestedAt",SOURCE="overviewSource";
  final MainActivity a;final Set<String> consumed=new LinkedHashSet<>();
  Dialog dialog;ChatSession owner;EnvironmentOverviewState state;EnvironmentOverviewDashboard dashboard;long readAt;boolean holding,checking,painted;long checkSequence;
  Runnable firstFrame;View firstDecor;ViewTreeObserver.OnDrawListener firstDraw;
  String checkRoute="";long checkEpoch;
  EnvironmentOverviewUi(MainActivity a){this.a=a;String seen=a.getSharedPreferences("environment-overview-display",0).getString("consumed","");for(String nonce:seen.split("\n"))if(!nonce.isEmpty())consumed.add(nonce);}
  static void mark(Intent intent,Context context,int slot){
    JSONObject row=ProfileCatalog.get(context).item(slot);
    if(!row.optBoolean("created")||row.optBoolean("deleting")||row.optBoolean("resetting"))return;
    intent.putExtra(SOURCE,"environment-list-chat").putExtra(NONCE,UUID.randomUUID().toString()).putExtra(ID,row.optString("environmentId")).putExtra(SLOT,slot).putExtra(GENERATION,row.optInt("generation")).putExtra(AT,SystemClock.elapsedRealtime());
  }
  boolean consume(Intent intent){
    if(intent==null)return false;String source=intent.getStringExtra(SOURCE);String nonce=intent.getStringExtra(NONCE),id=intent.getStringExtra(ID);int slot=intent.getIntExtra(SLOT,-1),generation=intent.getIntExtra(GENERATION,-1);long at=intent.getLongExtra(AT,-1);
    intent.removeExtra(SOURCE);intent.removeExtra(NONCE);intent.removeExtra(ID);intent.removeExtra(SLOT);intent.removeExtra(GENERATION);intent.removeExtra(AT);
    close();if(nonce==null)return false;
    long now=SystemClock.elapsedRealtime();ChatSession selected=a.session;
    if(!"environment-list-chat".equals(source)||!nonce.matches("[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")||consumed.contains(nonce)||at<0||now<at||now-at>60000
        ||id==null||slot!=Profiles.slot(a)||selected!=null&&(!id.equals(selected.environmentId)||generation!=selected.environmentGeneration||!NetworkStatusUi.current(a,selected))
        ||intent.hasExtra("openConversation")||intent.hasExtra("openDownload"))return false;
    JSONObject row=ProfileCatalog.get(a).item(slot);
    if(!id.equals(row.optString("environmentId"))||generation!=row.optInt("generation",-1)||!ProfileCatalog.get(a).available(slot))return false;
    consumed.add(nonce);if(consumed.size()>32)consumed.remove(consumed.iterator().next());
    if(!a.getSharedPreferences("environment-overview-display",0).edit().putString("consumed",android.text.TextUtils.join("\n",consumed)).commit())return false;
    owner=selected;state=new EnvironmentOverviewState(nonce,id,slot,generation);holding=false;painted=false;
    Dialog shown=new ThemedDialog(a){@Override public void onWindowFocusChanged(boolean focused){super.onWindowFocusChanged(focused);if(focused&&dialog==this)tick.run();}};
    dialog=shown;shown.requestWindowFeature(Window.FEATURE_NO_TITLE);
    dashboard=new EnvironmentOverviewDashboard(a,slot,this::checkRoute,this::queryIp,this::inspectIdentity,this::details,this::close,()->{holding=true;render();});
    ReferenceUi.insets(a,dashboard);shown.setContentView(dashboard);shown.setOnDismissListener(unused->{if(dialog==shown)close();});
    shown.show();Window window=shown.getWindow();if(window!=null){window.clearFlags(WindowManager.LayoutParams.FLAG_DIM_BEHIND);window.setDimAmount(0);if(android.os.Build.VERSION.SDK_INT>=30)window.setDecorFitsSystemWindows(false);window.setLayout(-1,-1);AppAppearance.window(window);}
    render();readAt=now;afterFirstFrame(null);a.handler.removeCallbacks(tick);a.handler.post(tick);return true;
  }
  boolean current(){
    if(dialog==null||!dialog.isShowing()||state==null||a.isDestroyed()||a.isFinishing()||Profiles.slot(a)!=state.slot)return false;
    if(owner==null&&a.session!=null)owner=a.session;
    if(owner!=null&&(!NetworkStatusUi.current(a,owner)||!state.matches(owner.environmentId,Profiles.slot(a),owner.environmentGeneration)))return false;
    JSONObject row=ProfileCatalog.get(a).item(state.slot);return ProfileCatalog.get(a).available(state.slot)&&state.environmentId.equals(row.optString("environmentId"))&&state.generation==row.optInt("generation",-1);
  }
  void render(){if(!current()||dashboard==null)return;if(checking&&owner!=null&&(checkEpoch!=owner.connectionEpoch||!checkRoute.equals(owner.networkIdentity()))){checking=false;checkSequence++;}dashboard.render(EnvironmentOverviewInfo.read(owner),ProfileCatalog.get(a).item(state.slot),owner,holding,checking);}
  void afterFirstFrame(Runnable action){
    if(action!=null)firstFrame=action;if(painted||dialog==null||dialog.getWindow()==null){dispatchFirstFrame();return;}if(firstDraw!=null)return;
    firstDecor=dialog.getWindow().getDecorView();firstDraw=()->{painted=true;if(state!=null&&firstDecor!=null&&firstDecor.hasWindowFocus())state.visible(SystemClock.elapsedRealtime());dispatchFirstFrame();};firstDecor.getViewTreeObserver().addOnDrawListener(firstDraw);firstDecor.invalidate();
  }
  void dispatchFirstFrame(){Runnable action=firstFrame;firstFrame=null;View decor=firstDecor;ViewTreeObserver.OnDrawListener draw=firstDraw;firstDecor=null;firstDraw=null;a.handler.post(()->{if(decor!=null&&draw!=null&&decor.getViewTreeObserver().isAlive())decor.getViewTreeObserver().removeOnDrawListener(draw);if(action!=null&&!a.isDestroyed()&&!a.isFinishing())action.run();});}
  void queryIp(){if(!current()||owner==null)return;close();ExitIpPageUi.open(a);}
  void inspectIdentity(){if(!current()||owner==null)return;close();EnvironmentAuditUi.show(a);}
  void details(){if(!current()||owner==null)return;holding=true;String ua=owner.web.getSettings().getUserAgentString();ReferenceUi.message(a,"环境信息与来源",EnvironmentOverviewInfo.text(owner)+(ua==null||ua.isEmpty()?"":"\n\n请求 User Agent：\n"+ua));render();}
  void checkRoute(){
    if(!current()||owner==null||checking||!NetworkStatusUi.connectionReady(owner))return;
    ChatSession selected=owner;long sequence=++checkSequence,epoch=selected.connectionEpoch;String route=selected.networkIdentity();checkEpoch=epoch;checkRoute=route;checking=true;holding=true;render();
    NativeNetwork.Callback done=(ok,message)->{if(!current()||owner!=selected||sequence!=checkSequence||epoch!=selected.connectionEpoch||!route.equals(selected.networkIdentity()))return;checking=false;render();EnvironmentOverviewDashboard.update(dashboard.progress,ok?"当前线路检测完成":"检测未完成，保留上次核验记录");};
    if(selected.internalNetwork()){NativeNetwork network=NativeNetwork.peek();if(network==null){checking=false;render();return;}network.checkExit(done);}else NetworkRegion.refreshLatency(selected,done);
  }
  final Runnable tick=new Runnable(){public void run(){
    a.handler.removeCallbacks(this);if(!current()){close();return;}
    View view=dialog.getWindow()==null?null:dialog.getWindow().getDecorView();long now=SystemClock.elapsedRealtime();
    if(painted&&view!=null&&view.isAttachedToWindow()&&view.isShown()&&view.hasWindowFocus())state.visible(now);
    if(!holding&&state.expired(now)){close();return;}
    EnvironmentOverviewDashboard.update(dashboard.countdown,holding?"查看完毕后，点击进入聊天":(state.remaining(now)+999)/1000+" 秒后进入聊天");
    if(now-readAt>=1000){readAt=now;render();}
    a.handler.postDelayed(this,250);
  }};
  boolean back(){if(dialog==null)return false;close();return true;}
  void close(){a.handler.removeCallbacks(tick);checkSequence++;checking=false;if(state!=null)state.close();Dialog old=dialog;dialog=null;owner=null;state=null;dashboard=null;if(old!=null)old.dismiss();if(firstFrame!=null||firstDraw!=null)dispatchFirstFrame();}
}
