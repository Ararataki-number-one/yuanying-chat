package local.pocketchat;
import android.app.*;
import android.widget.*;
import android.view.*;
import java.text.SimpleDateFormat;
import java.util.*;

final class NetworkStatusUi {
  static boolean current(MainActivity a,ChatSession s){return a!=null&&s!=null&&!a.isDestroyed()&&!a.isFinishing()&&a.session==s&&!s.deleted&&a.remote==s.web;}
  static boolean connectionReady(ChatSession s){return s.networkReady&&!s.offline&&!s.connecting&&!s.recoveryScheduled&&s.guard.allowed();}
  static String pageStatus(ChatSession s){
    if(!s.pageError.isEmpty())return "需要检查："+s.pageError;
    if(s.websiteConnectionIssue)return "网页连接已中断，需要检查原网页";
    if(s.navigating)return "正在加载当前网页";
    if(!s.web.hasVisibleDocument())return "当前网页尚未显示";
    if(LoginPagePolicy.login(s.web.getUrl()))return "等待在网页完成登录";
    if(s.navigationFailed)return "当前网页加载尚未确认";
    if(s.web.current==null||s.web.ports.get(s.web.current)==null||s.stateEpoch!=s.navigationEpoch||s.lastDocumentId.isEmpty()
        ||!s.lastDocumentId.equals(s.state.optString("documentId"))||!BrowserRuntimePolicy.sameDocument(s.web.getUrl(),s.state.optString("url")))return "当前网页状态尚未确认";
    if(!s.state.optString("error").isEmpty())return "网页反馈："+s.state.optString("error");
    if(s.state.optBoolean("websiteSocketClosed"))return "网页连接已中断，需要检查原网页";
    if(s.state.optBoolean("busy"))return "最近观测：网页正在生成回复";
    return s.state.optBoolean("composer")?"最近观测：已显示网页输入区":"最近观测：输入区尚未确认";
  }
  static String sendStatus(ChatSession s){
    if(s.pending==null)return "当前没有本机等待任务；不代表网页任务已完成";
    if(s.pending.optBoolean("webSuspended"))return "发送结果待核对；本机未自动重发";
    return s.pending.optBoolean("confirmed")?"网页已确认提问；回复完成尚未确认":"已观察到发送操作；网页是否接收尚未确认";
  }
  static void show(MainActivity a){
    ChatSession s=a.session;
    if(!current(a,s))return;
    if(a.networkDialog!=null)a.networkDialog.dismiss();
    LinearLayout box=new LinearLayout(a);box.setOrientation(LinearLayout.VERTICAL);box.setPadding(a.dp(24),a.dp(8),a.dp(24),a.dp(12));
    TextView details=a.label("",15,Ui.INK);details.setLineSpacing(a.dp(6),1);box.addView(details);
    Button copy=new Button(a);copy.setText("复制耗时诊断");copy.setAllCaps(false);box.addView(copy);
    Button reply=new Button(a);reply.setText("查看发送与回复状态");reply.setAllCaps(false);box.addView(reply);
    ScrollView scroll=new ScrollView(a);scroll.addView(box);
    final AlertDialog[] shown={null};
    AlertDialog dialog=AppAppearance.dialog(a).setTitle("连接状态").setView(scroll).setPositiveButton("立即重连",(d,w)->{if(current(a,s)&&shown[0]!=null&&shown[0].isShowing())s.reconnect();}).setNeutralButton("网络设置",(d,w)->{if(current(a,s)&&shown[0]!=null&&shown[0].isShowing())a.networkSettings();}).setNegativeButton("关闭",null).create();
    shown[0]=dialog;a.networkDialog=dialog;
    reply.setOnClickListener(v->{if(!current(a,s)||!dialog.isShowing()||s.pending==null)return;dialog.dismiss();ReplyState.show(a);});
    copy.setOnClickListener(v->{
      copy.setEnabled(false);
      s.trace.copyTextAsync(a,GeckoWebView.active(a.remote),text->{
        if(!current(a,s)||!dialog.isShowing())return;
        copy.setEnabled(true);
        android.content.ClipboardManager clipboard=(android.content.ClipboardManager)a.getSystemService(android.content.Context.CLIPBOARD_SERVICE);
        if(clipboard!=null){clipboard.setPrimaryClip(android.content.ClipData.newPlainText("连接耗时",text));copy.setText("已复制");}
      });
    });
    Runnable update=new Runnable(){public void run(){
      if(!dialog.isShowing())return;
      if(!current(a,s)){dialog.dismiss();return;}
      String proxy="使用已配置的手机网络",verified="";
      if(s.internalNetwork()){
        NativeNetwork n=NativeNetwork.get(a);proxy=n.starting?"正在启动 / 核对":n.ready&&n.coreAlive()?"运行正常":"尚未连接";
        proxy+=" · "+NetworkStatusPolicy.admission(n.connectionAdmission().name());
        verified=n.lastVerified==0?"尚未核实":new SimpleDateFormat("HH:mm:ss",Locale.getDefault()).format(new Date(n.lastVerified));
      }
      details.setText(NetworkMetricsUi.line(s,NativeNetwork.get(a),System.currentTimeMillis(),android.os.SystemClock.elapsedRealtime())
        +"\n\n手机网络："+(s.offline?"已断开":"可用")+"\n应用代理："+proxy+"\n连接恢复进度："+s.connectionStage
        +"\n\n网页状态："+pageStatus(s)+"\n发送状态："+sendStatus(s)
        +(verified.isEmpty()?"":"\n最近出口核实："+verified)+(s.networkIssue.isEmpty()?"":"\n\n"+s.networkIssue)
        +(s.pageError.isEmpty()?"":"\n\n"+s.pageError)+(s.websiteProbeIssue.isEmpty()?"":"\n\n"+s.websiteProbeIssue)
        +(s.entryTiming().isEmpty()?"":"\n\n"+s.entryTiming())+"\n\n"+s.trace.text()
        +"\n\n草稿和待确认发送会保留。重连只恢复连接，不会重复发送消息。");
      reply.setVisibility(s.pending==null?View.GONE:View.VISIBLE);
      dialog.getButton(-1).setEnabled(!s.offline&&!s.connecting);a.handler.postDelayed(this,1000);
    }};
    dialog.setOnShowListener(d->update.run());dialog.setOnDismissListener(d->{a.handler.removeCallbacks(update);if(a.networkDialog==dialog)a.networkDialog=null;});dialog.show();
  }
}
