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
  Dialog dialog;ChatSession owner;EnvironmentOverviewState state;TextView info,countdown;long readAt;
  EnvironmentOverviewUi(MainActivity a){this.a=a;String seen=a.getSharedPreferences("environment-overview-display",0).getString("consumed","");for(String nonce:seen.split("\n"))if(!nonce.isEmpty())consumed.add(nonce);}
  static void mark(Intent intent,Context context,int slot){
    JSONObject row=ProfileCatalog.get(context).item(slot);
    if(!row.optBoolean("created")||row.optBoolean("deleting")||row.optBoolean("resetting"))return;
    intent.putExtra(SOURCE,"environment-list-chat").putExtra(NONCE,UUID.randomUUID().toString()).putExtra(ID,row.optString("environmentId")).putExtra(SLOT,slot).putExtra(GENERATION,row.optInt("generation")).putExtra(AT,SystemClock.elapsedRealtime());
  }
  void consume(Intent intent){
    if(intent==null)return;String source=intent.getStringExtra(SOURCE);String nonce=intent.getStringExtra(NONCE),id=intent.getStringExtra(ID);int slot=intent.getIntExtra(SLOT,-1),generation=intent.getIntExtra(GENERATION,-1);long at=intent.getLongExtra(AT,-1);
    intent.removeExtra(SOURCE);intent.removeExtra(NONCE);intent.removeExtra(ID);intent.removeExtra(SLOT);intent.removeExtra(GENERATION);intent.removeExtra(AT);
    close();if(nonce==null)return;
    long now=SystemClock.elapsedRealtime();ChatSession selected=a.session;
    if(!"environment-list-chat".equals(source)||!nonce.matches("[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")||consumed.contains(nonce)||at<0||now<at||now-at>60000||selected==null
        ||id==null||!id.equals(selected.environmentId)||slot!=Profiles.slot(a)||generation!=selected.environmentGeneration
        ||intent.hasExtra("openConversation")||intent.hasExtra("openDownload")||!NetworkStatusUi.current(a,selected))return;
    JSONObject row=ProfileCatalog.get(a).item(slot);
    if(!id.equals(row.optString("environmentId"))||generation!=row.optInt("generation",-1)||!ProfileCatalog.get(a).available(slot))return;
    consumed.add(nonce);if(consumed.size()>32)consumed.remove(consumed.iterator().next());
    if(!a.getSharedPreferences("environment-overview-display",0).edit().putString("consumed",android.text.TextUtils.join("\n",consumed)).commit())return;
    owner=selected;state=new EnvironmentOverviewState(nonce,id,slot,generation);
    Dialog shown=new ThemedDialog(a){@Override public void onWindowFocusChanged(boolean focused){super.onWindowFocusChanged(focused);if(focused&&dialog==this)tick.run();}};
    dialog=shown;shown.requestWindowFeature(Window.FEATURE_NO_TITLE);
    LinearLayout root=DesignUi.screen(a),body=DesignUi.column(a);body.setPadding(a.dp(24),a.dp(28),a.dp(24),a.dp(20));
    body.addView(ReferenceUi.text(a,Profiles.display(a,slot),24,ReferenceUi.TEXT,true));
    body.addView(ReferenceUi.secondary(a,"环境概览"));info=ReferenceUi.text(a,"",15,ReferenceUi.TEXT,false);info.setLineSpacing(a.dp(5),1);info.setPadding(0,a.dp(20),0,a.dp(20));body.addView(info);
    ScrollView scroll=new ScrollView(a);scroll.addView(body);root.addView(scroll,new LinearLayout.LayoutParams(-1,0,1));
    LinearLayout actions=DesignUi.column(a);actions.setPadding(a.dp(24),a.dp(8),a.dp(24),a.dp(16));countdown=ReferenceUi.text(a,"5 秒后进入聊天",13,ReferenceUi.MUTED,false);actions.addView(countdown);
    DesignUi.action(actions,"跳过，进入聊天",true,this::close);root.addView(actions);shown.setContentView(root);shown.setOnDismissListener(unused->{if(dialog==shown)close();});
    info.setText(EnvironmentOverviewInfo.text(owner));readAt=now;shown.show();Window window=shown.getWindow();if(window!=null){window.setLayout(-1,-1);window.setBackgroundDrawable(new android.graphics.drawable.ColorDrawable(ReferenceUi.CHAT_BG));}
    a.handler.removeCallbacks(tick);a.handler.post(tick);
  }
  boolean current(){if(dialog==null||!dialog.isShowing()||state==null||!NetworkStatusUi.current(a,owner)||!state.matches(owner.environmentId,Profiles.slot(a),owner.environmentGeneration))return false;JSONObject row=ProfileCatalog.get(a).item(state.slot);return ProfileCatalog.get(a).available(state.slot)&&state.environmentId.equals(row.optString("environmentId"))&&state.generation==row.optInt("generation",-1);}
  final Runnable tick=new Runnable(){public void run(){
    a.handler.removeCallbacks(this);if(!current()){close();return;}
    View view=dialog.getWindow()==null?null:dialog.getWindow().getDecorView();long now=SystemClock.elapsedRealtime();
    if(view!=null&&view.isAttachedToWindow()&&view.isShown()&&view.hasWindowFocus())state.visible(now);
    if(state.expired(now)){close();return;}
    countdown.setText((state.remaining(now)+999)/1000+" 秒后进入聊天");
    if(now-readAt>=500){readAt=now;info.setText(EnvironmentOverviewInfo.text(owner));}
    a.handler.postDelayed(this,100);
  }};
  boolean back(){if(dialog==null)return false;close();return true;}
  void close(){a.handler.removeCallbacks(tick);if(state!=null)state.close();Dialog old=dialog;dialog=null;owner=null;state=null;if(old!=null)old.dismiss();}
}
