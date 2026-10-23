package local.pocketchat;
import org.json.*;

final class ReplyState {
  static String describe(JSONObject poll,JSONObject job,int stableTicks,long quietMs){
    if("regenerate".equals(job.optString("kind"))&&!job.optBoolean("regenerationObserved"))return quietMs>=120000?"重新生成结果待确认 · 点按检查":"重新生成已请求，正在确认…";
    if(!poll.optBoolean("submitted"))return "发送结果待确认 · 不会自动重发";
    String stage;
    if(poll.optBoolean("searching"))stage="正在搜索资料…";
    else if(poll.optBoolean("thinking"))stage="正在思考…";
    else if(poll.optBoolean("busy"))stage=poll.optString("markdown").trim().isEmpty()&&!poll.optBoolean("hasReply")?"等待网页开始回复…":"正在生成回复…";
    else if(poll.optBoolean("terminal"))stage="正在确认回复完成…";
    else if(!poll.optString("markdown").trim().isEmpty()&&stableTicks>=8)return "回复内容已稳定，结束状态待确认 · 点按检查";
    else stage="等待网页开始回复…";
    if(quietMs>=120000&&!poll.optBoolean("terminal"))return "回复长时间无进展 · 可继续等待或点按检查";
    return stage;
  }
  static long elapsedSeconds(JSONObject job){return Math.max(0,(System.currentTimeMillis()-job.optLong("startedAt",System.currentTimeMillis()))/1000);}
  static void show(MainActivity a){
    ChatSession s=a.session;
    if(s.websiteConnectionIssue||!s.pageError.isEmpty()){websiteConnection(a);return;}
    if(s.pending==null){NetworkStatusUi.show(a);return;}
    long elapsed=elapsedSeconds(s.pending);String detail=s.status+"\n已等待 "+(elapsed>=60?elapsed/60+" 分 "+elapsed%60+" 秒":elapsed+" 秒")+(s.replyHealthStatus.isEmpty()?"":"\n线路诊断："+s.replyHealthStatus)+"\n\n长时间思考仍可能正常。检查连接只做只读诊断；重新加载需要另行确认，不会重新发送。";
    AppAppearance.dialog(a).setTitle("回复状态").setMessage(detail).setPositiveButton("继续检查",(d,w)->{checkWithoutRecovery(s);}).setNeutralButton("恢复网页连接",(d,w)->a.requestReload()).setNegativeButton("查看原网页",(d,w)->a.showPage(true)).show();
  }
  static void checkWithoutRecovery(ChatSession session){
    if(session.offline||!session.networkReady){session.replyHealthStatus="当前线路尚未就绪；请从连接状态恢复线路，原回复继续保留";session.changed();return;}
    session.sync();if(session.replyStalled)session.diagnoseStalledReply();
  }
  static void websiteConnection(MainActivity a){
    AppAppearance.dialog(a).setTitle("网页需要恢复")
      .setMessage((a.session.pageError.isEmpty()?"网页连接需要检查。":a.session.pageError)+"\n\n可以先保存当前草稿，再重新加载这条对话。不会重新发送提问或自动重试网页任务；若仍报错，请在原网页核对工具任务状态。")
      .setPositiveButton("恢复网页连接",(d,w)->a.requestReload())
      .setNeutralButton("继续检查",(d,w)->a.session.sync()).setNegativeButton("暂不恢复",null).show();
  }
}
