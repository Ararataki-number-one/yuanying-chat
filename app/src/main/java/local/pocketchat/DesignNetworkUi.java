package local.pocketchat;

import android.app.*;
import android.os.SystemClock;
import android.widget.*;
import org.json.*;

/** Mode-aware network workspace; every operation belongs to the named profile. */
final class DesignNetworkUi {
  static boolean busy(MainActivity a){return ProfileUi.working(a.session)||a.loading.taskRunning;}
  static String mode(MainActivity a){return a.session.internalNetwork()?"内置网络":!a.prefs.getString("proxy","").isEmpty()?"应用专用代理":a.prefs.getBoolean("requireExternalVpn",true)?"手机 VPN":"手机网络";}
  static void render(MainActivity a,LinearLayout box,int tab){
    if(!a.session.internalNetwork()&&(tab==1||tab==2)){tab=0;a.hub.networkTab=0;}
    DesignUi.scope(a,box);
    if(a.loading.taskRunning)DesignUi.action(box,a.loading.taskMessage+" · 查看",false,()->a.loading.showTask());
    int[] targets=a.session.internalNetwork()?new int[]{0,1,2,3,4}:new int[]{0,3,4};
    String[] labels=a.session.internalNetwork()?new String[]{"连接","订阅","线路","出口","诊断"}:new String[]{"连接","出口","诊断"};
    int selected=0;for(int i=0;i<targets.length;i++)if(targets[i]==tab)selected=i;
    box.addView(DesignUi.tabs(a,labels,selected,n->{a.hub.networkTab=targets[n];a.hub.network();}));
    NativeNetwork network=NativeNetwork.get(a);
    if(tab==0)scheme(a,box,network);
    if(tab==1||tab==2){
      if(!a.session.internalNetwork()){
        DesignUi.note(box,"当前使用"+mode(a)+"，无需设置订阅或入口线路。");
        DesignUi.action(box,"选择网络方式",true,()->modes(a));return;
      }
      if(tab==1)subscription(a,box);else nodes(a,box,network);
    }
    if(tab==3)exit(a,box,network);if(tab==4)diagnostics(a,box,network);
  }
  static void scheme(MainActivity a,LinearLayout box,NativeNetwork n){
    LinearLayout card=DesignUi.card(a),head=DesignUi.row(a);
    head.addView(DesignUi.text(a,"当前网络",16,DesignUi.TEXT),new LinearLayout.LayoutParams(0,-2,1));
    String state=a.session.offline?"手机离线":a.session.networkReady?"已连接":a.session.connecting?"连接中":"未连接";
    head.addView(DesignUi.badge(a,state,a.session.networkReady?DesignUi.GREEN:DesignUi.MUTED));card.addView(head);
    LinearLayout modeRow=DesignUi.row(a);modeRow.addView(DesignUi.text(a,"方式",12,DesignUi.MUTED),new LinearLayout.LayoutParams(DesignUi.dp(a,76),-2));
    Button mode=DesignUi.button(a,mode(a)+" ▾",false,()->modes(a));mode.setGravity(android.view.Gravity.START|android.view.Gravity.CENTER_VERTICAL);mode.setPadding(0,0,0,0);
    mode.setBackground(Ui.ripple(a,android.graphics.Color.TRANSPARENT,8));mode.setContentDescription("更换网络方式，当前："+mode(a));modeRow.addView(mode,new LinearLayout.LayoutParams(0,DesignUi.dp(a,48),1));card.addView(modeRow);
    if(a.session.internalNetwork())DesignUi.field(card,"当前线路",n.currentEntry.isEmpty()?"尚未选择":NativeNetwork.display(n.currentEntry));
    if(!a.session.networkIssue.isEmpty())DesignUi.note(card,a.session.networkIssue);
    LinearLayout actions=DesignUi.row(a);
    Button edit=DesignUi.button(a,"修改配置",true,()->{if(a.session.internalNetwork())FeatureDialogs.networkAdvanced(a);else if(a.prefs.getString("proxy","").isEmpty())phone(a);else a.externalNetworkSettings();});
    actions.addView(edit,new LinearLayout.LayoutParams(0,DesignUi.dp(a,48),1));
    Button inspect=DesignUi.button(a,"检查连接",false,()->NetworkStatusUi.show(a));LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(0,DesignUi.dp(a,48),1);p.leftMargin=DesignUi.dp(a,8);actions.addView(inspect,p);
    card.addView(actions);DesignUi.addCard(box,card);
  }
  static void modes(MainActivity a){
    new AlertDialog.Builder(a).setTitle("选择该环境的网络方式").setItems(new String[]{"手机网络 / 手机 VPN","应用专用 HTTP / SOCKS 代理","内置网络：订阅入口 + 固定 SOCKS5 出口"},(d,n)->{
      if(busy(a)){a.status("当前任务结束后再切换网络");return;}
      if(n==0)phone(a);else if(n==1)a.externalNetworkSettings();else FeatureDialogs.networkAdvanced(a);
    }).setNegativeButton("取消",null).show();
  }
  static void phone(MainActivity a){
    CheckBox vpn=new CheckBox(a);vpn.setText("手机 VPN 断开时暂停联网");vpn.setChecked(a.prefs.getBoolean("requireExternalVpn",true));vpn.setPadding(a.dp(20),a.dp(8),a.dp(20),a.dp(8));
    new AlertDialog.Builder(a).setTitle("手机网络 / VPN").setMessage("使用手机当前网络，不设置应用专用代理。").setView(vpn).setPositiveButton("保存并连接",(d,w)->{if(busy(a)){a.status("当前任务结束后再切换网络");return;}a.prefs.edit().putBoolean("networkConfigured",true).putString("networkMode","external").putString("proxy","").putBoolean("requireExternalVpn",vpn.isChecked()).commit();a.session.reconnect();a.hub.refresh();}).setNegativeButton("取消",null).show();
  }
  static void subscription(MainActivity a,LinearLayout box){
    JSONObject saved=new SecretStore(a).settings();DesignUi.section(box,"订阅","");
    LinearLayout card=DesignUi.card(a);DesignUi.field(card,"状态",saved.optString("subscriptionUrl").isEmpty()?"还未设置":"已保存");
    DesignUi.action(card,"编辑订阅与固定出口",true,()->FeatureDialogs.networkAdvanced(a));
    DesignUi.action(card,"更新已保存的订阅",false,()->{
      if(busy(a)){a.status("请等待当前任务结束");return;}
      if(saved.optString("subscriptionUrl").isEmpty()){a.status("请先保存订阅地址");return;}
      a.loading.task("正在更新订阅…");NativeNetwork.get(a).refresh((ok,msg)->{a.loading.dismissTask();a.status(msg);if(ok)a.session.applyProxy(NativeNetwork.get(a).proxy());});
    });DesignUi.addCard(box,card);
  }
  static void nodes(MainActivity a,LinearLayout box,NativeNetwork n){
    DesignUi.action(box,"测速 / 选择线路",true,()->FeatureDialogs.nodes(a));
    if(n.results.length()==0)DesignUi.empty(box,"还没有测速结果","先保存订阅，再检查线路。","",null);
    for(int i=0;i<n.results.length();i++){
      JSONObject r=n.results.optJSONObject(i);String internal=r.optString("internalName");String delay=r.optInt("delay")>0?r.optInt("delay")+" ms":"本次不可用";
      String detail=delay+(r.optInt("samples")>0?" · 成功 "+Math.round(r.optDouble("successRate")*100)+"% · 波动 "+r.optLong("jitter")+" ms":"");
      DesignUi.addCard(box,DesignUi.setting(a,"globe",r.optString("name"),detail,internal.equals(n.currentEntry)?"使用中":"",()->{
        if(busy(a)){a.status("当前任务结束后再切换入口");return;}
        a.loading.task("正在切换并核实线路…");n.select(internal,(ok,msg)->{a.loading.dismissTask();a.status(msg);if(!a.destroyed&&a.hub.page==AppHub.NETWORK)a.hub.refresh();});
      }));
    }
  }
  static void exit(MainActivity a,LinearLayout box,NativeNetwork n){
    DesignUi.section(box,"网站看到的出口","");
    LinearLayout card=DesignUi.card(a);DesignUi.field(card,"出口信息",ExitIpUi.value(a.session,n));DesignUi.addCard(box,card);
    if(a.session.internalNetwork())DesignUi.action(box,"核对出口",true,()->ExitIpUi.show(a));
    DesignUi.action(box,"环境自检",false,()->EnvironmentAuditUi.show(a));
  }
  static void diagnostics(MainActivity a,LinearLayout box,NativeNetwork n){
    LinearLayout summary=DesignUi.card(a);
    DesignUi.field(summary,"连接",NetworkMetricsUi.line(a.session,n,System.currentTimeMillis(),SystemClock.elapsedRealtime()));
    if(a.session.internalNetwork()){
      long now=System.currentTimeMillis();JSONObject q=n.quality.stats(n.currentEntry,now);
      DesignUi.field(summary,"延迟",NetworkMetricsUi.latency(q,now));DesignUi.field(summary,"稳定性",NetworkMetricsUi.stability(q,now));
    }
    DesignUi.addCard(box,summary);
    DesignUi.action(box,"检查连接 / 重新连接",true,()->NetworkStatusUi.show(a));
    if(a.session.internalNetwork())DesignUi.action(box,"重新测量延迟",false,()->{
      if(busy(a)){a.status("请等待当前任务结束");return;}a.loading.task("正在测量线路延迟…");
      n.measureLatency((ok,msg)->{a.loading.dismissTask();a.status(msg);if(!a.destroyed&&a.hub.page==AppHub.NETWORK)a.hub.refresh();});
    });
    LinearLayout details=DesignUi.card(a);
    details.addView(DesignUi.setting(a,"globe","连接详情","", "",()->NetworkStatusUi.show(a)));
    if(a.session.internalNetwork())details.addView(DesignUi.setting(a,"globe","线路统计","", "",()->NetworkMetricsUi.show(a)));
    details.addView(DesignUi.setting(a,"settings","网络日志","", "",()->a.hub.text("网络日志",NetworkJournal.text(a))));
    details.addView(DesignUi.setting(a,"shield","环境自检","", "",()->EnvironmentAuditUi.show(a)));DesignUi.addCard(box,details);
  }
}
