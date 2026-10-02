package local.pocketchat;

import android.app.*;
import android.os.SystemClock;
import android.widget.*;
import org.json.*;

/** Mode-aware network workspace; every operation belongs to the named profile. */
final class DesignNetworkUi {
  static String mode(MainActivity a){return a.session.internalNetwork()?"内置网络 · 订阅入口 + 固定出口":!a.prefs.getString("proxy","").isEmpty()?"应用专用代理":a.prefs.getBoolean("requireExternalVpn",true)?"手机 VPN":"手机网络";}
  static void render(MainActivity a,LinearLayout box,int tab){
    DesignUi.scope(a,box);
    box.addView(DesignUi.tabs(a,new String[]{"连接配置","订阅入口","节点选择","出口信息","连接诊断"},tab,n->{a.hub.networkTab=n;a.hub.network();}));
    NativeNetwork network=NativeNetwork.get(a);
    if(tab==0)scheme(a,box,network);
    if(tab==1||tab==2){
      if(!a.session.internalNetwork()){
        DesignUi.section(box,"当前使用"+mode(a),"订阅入口和节点选择用于内置网络模式。当前模式的连接状态可在诊断页查看。");
        DesignUi.action(box,"选择网络方式",true,()->modes(a));return;
      }
      if(tab==1)subscription(a,box);else nodes(a,box,network);
    }
    if(tab==3)exit(a,box,network);if(tab==4)diagnostics(a,box,network);
  }
  static void scheme(MainActivity a,LinearLayout box,NativeNetwork n){
    DesignUi.section(box,"当前连接","");LinearLayout card=DesignUi.card(a);
    DesignUi.field(card,"网络方式",mode(a));DesignUi.field(card,"连接状态",NetworkMetricsUi.line(a.session,n,System.currentTimeMillis(),SystemClock.elapsedRealtime()));
    if(a.session.internalNetwork())DesignUi.field(card,"当前入口",n.currentEntry.isEmpty()?"尚未选择":NativeNetwork.display(n.currentEntry));
    DesignUi.action(card,"选择网络方式",true,()->modes(a));DesignUi.action(card,"编辑当前网络参数",false,()->{if(a.session.internalNetwork())FeatureDialogs.networkAdvanced(a);else a.externalNetworkSettings();});DesignUi.addCard(box,card);
    DesignUi.section(box,"连接维护", "切换网络前请先完成当前回复或传输任务。");
    DesignUi.action(box,"查看连接状态 / 重新连接",false,()->NetworkStatusUi.show(a));
    if(a.session.internalNetwork())DesignUi.action(box,"查看线路统计",false,()->NetworkMetricsUi.show(a));
  }
  static void modes(MainActivity a){
    new AlertDialog.Builder(a).setTitle("选择该环境的网络方式").setItems(new String[]{"手机网络 / 手机 VPN","应用专用 HTTP / SOCKS 代理","内置网络：订阅入口 + 固定 SOCKS5 出口"},(d,n)->{
      if(ProfileUi.working(a.session)){a.status("当前任务结束后再切换网络");return;}
      if(n==0)phone(a);else if(n==1)a.externalNetworkSettings();else FeatureDialogs.networkAdvanced(a);
    }).setNegativeButton("取消",null).show();
  }
  static void phone(MainActivity a){
    CheckBox vpn=new CheckBox(a);vpn.setText("手机 VPN 断开时暂停联网");vpn.setChecked(a.prefs.getBoolean("requireExternalVpn",true));vpn.setPadding(a.dp(20),a.dp(8),a.dp(20),a.dp(8));
    new AlertDialog.Builder(a).setTitle("手机网络 / VPN").setMessage("使用手机当前网络，不设置应用专用代理。").setView(vpn).setPositiveButton("保存并连接",(d,w)->{if(ProfileUi.working(a.session)){a.status("当前任务结束后再切换网络");return;}a.prefs.edit().putBoolean("networkConfigured",true).putString("networkMode","external").putString("proxy","").putBoolean("requireExternalVpn",vpn.isChecked()).commit();a.session.reconnect();a.hub.refresh();}).setNegativeButton("取消",null).show();
  }
  static void subscription(MainActivity a,LinearLayout box){
    JSONObject saved=new SecretStore(a).settings();DesignUi.section(box,"订阅与固定出口","每个环境支持一份订阅配置，凭据加密保存。");
    LinearLayout card=DesignUi.card(a);DesignUi.field(card,"配置状态",saved.optString("subscriptionUrl").isEmpty()?"未配置":"已配置");
    DesignUi.action(card,"编辑订阅与固定出口",true,()->FeatureDialogs.networkAdvanced(a));
    DesignUi.action(card,"更新已保存的订阅",false,()->{
      if(ProfileUi.working(a.session)){a.status("请等待当前任务结束");return;}
      if(saved.optString("subscriptionUrl").isEmpty()){a.status("请先保存订阅地址");return;}
      a.loading.task("正在更新订阅…");NativeNetwork.get(a).refresh((ok,msg)->{a.loading.dismissTask();a.status(msg);if(ok)a.session.applyProxy(NativeNetwork.get(a).proxy());});
    });DesignUi.addCard(box,card);
  }
  static void nodes(MainActivity a,LinearLayout box,NativeNetwork n){
    DesignUi.section(box,"入口节点","延迟表示本次实际测量结果。");DesignUi.action(box,"测速 / 选择入口",true,()->FeatureDialogs.nodes(a));
    if(n.results.length()==0)DesignUi.note(box,"还没有测量结果，保存内置网络配置后可进行测速。");
    for(int i=0;i<n.results.length();i++){
      JSONObject r=n.results.optJSONObject(i);String internal=r.optString("internalName");String delay=r.optInt("delay")>0?r.optInt("delay")+" ms":"本次不可用";
      String detail=delay+(r.optInt("samples")>0?" · 成功 "+Math.round(r.optDouble("successRate")*100)+"% · 波动 "+r.optLong("jitter")+" ms":"");
      DesignUi.addCard(box,DesignUi.setting(a,"globe",r.optString("name"),detail,internal.equals(n.currentEntry)?"使用中":"",()->{
        if(ProfileUi.working(a.session)){a.status("当前任务结束后再切换入口");return;}
        a.loading.task("正在切换并核实线路…");n.select(internal,(ok,msg)->{a.loading.dismissTask();a.status(msg);a.hub.network();});
      }));
    }
  }
  static void exit(MainActivity a,LinearLayout box,NativeNetwork n){
    DesignUi.section(box,"出口核对","只显示实际记录的结果；公开出口检查由你手动发起。");
    LinearLayout card=DesignUi.card(a);DesignUi.field(card,"出口信息",ExitIpUi.value(a.session,n));DesignUi.addCard(box,card);
    if(a.session.internalNetwork())DesignUi.action(box,"查看 / 核实固定出口",true,()->ExitIpUi.show(a));
    DesignUi.action(box,"环境自检 / 手动授权出口检查",false,()->EnvironmentAuditUi.show(a));
  }
  static void diagnostics(MainActivity a,LinearLayout box,NativeNetwork n){
    DesignUi.section(box,"连接诊断","");LinearLayout chain=DesignUi.card(a);
    DesignUi.field(chain,"连接链路",a.session.internalNetwork()?"本机 → 入口节点 → 固定出口 → ChatGPT":a.prefs.getString("proxy","").isEmpty()?"手机网络 / VPN → ChatGPT":"本机 → 应用代理 → ChatGPT");DesignUi.addCard(box,chain);
    status(a,box,"当前连接",a.session.offline?"已断开":a.session.networkReady?"已连接":"待确认",a.session.networkReady?DesignUi.GREEN:DesignUi.MUTED);
    if(a.session.internalNetwork()){
      long now=System.currentTimeMillis();JSONObject q=n.quality.stats(n.currentEntry,now);
      status(a,box,"线路延迟",NetworkMetricsUi.latency(q,now),DesignUi.BLUE);status(a,box,"探测稳定性",NetworkMetricsUi.stability(q,now),DesignUi.MUTED);
      DesignUi.action(box,"测量线路延迟",true,()->{if(ProfileUi.working(a.session)){a.status("请等待当前任务结束");return;}n.measureLatency((ok,msg)->{a.status(msg);a.hub.network();});});
    }
    DesignUi.action(box,"查看连接阶段耗时",false,()->NetworkStatusUi.show(a));
    DesignUi.action(box,"查看本机网络事件",false,()->a.hub.text("网络事件",NetworkJournal.text(a)));
    DesignUi.action(box,"环境自检与检查详情",false,()->EnvironmentAuditUi.show(a));
    DesignUi.note(box,"尚未提供 DNS / TCP / TLS 分项测量及完整泄漏检测。");
  }
  static void status(MainActivity a,LinearLayout box,String name,String value,int color){LinearLayout row=DesignUi.card(a);row.addView(DesignUi.text(a,name,12,DesignUi.MUTED));row.addView(DesignUi.text(a,value,14,color));DesignUi.addCard(box,row);}
}
