package local.pocketchat;
import org.json.*;

final class ReplyState {
  static String describe(JSONObject poll,JSONObject job,int stableTicks,long quietMs){
    if("regenerate".equals(job.optString("kind"))&&!job.optBoolean("regenerationObserved"))return quietMs>=120000?"重新生成结果待确认 · 点按检查":"重新生成已请求，正在确认…";
    if(!poll.optBoolean("submitted"))return "发送结果待确认 · 不会自动重发";
    String stage;
    if(poll.optBoolean("searching"))stage="正在搜索资料…";
    else if(poll.optBoolean("thinking"))stage="正在思考…";
    else if(poll.optBoolean("busy"))stage=poll.optString("markdown").trim().isEmpty()?"等待网页开始回复…":"正在生成回复…";
    else if(poll.optBoolean("terminal"))stage="正在确认回复完成…";
    else if(!poll.optString("markdown").trim().isEmpty()&&stableTicks>=8)return "回复内容已稳定，结束状态待确认 · 点按检查";
    else stage="等待网页开始回复…";
    if(quietMs>=120000&&!poll.optBoolean("terminal"))return stage.replace("…","")+" · 等待较久，点按检查";
    return stage;
  }
  static long elapsedSeconds(JSONObject job){return Math.max(0,(System.currentTimeMillis()-job.optLong("startedAt",System.currentTimeMillis()))/1000);}
  static void show(MainActivity a){ChatSession s=a.session;if(s.pending==null){if(!s.networkReady||s.offline)NetworkStatusUi.show(a);else a.status("当前没有等待中的回复");return;}long elapsed=elapsedSeconds(s.pending);String detail=s.status+"\n已等待 "+(elapsed>=60?elapsed/60+" 分 "+elapsed%60+" 秒":elapsed+" 秒")+"\n\n继续检查或恢复连接只读取已有结果，不会重新发送。";new android.app.AlertDialog.Builder(a).setTitle("回复状态").setMessage(detail).setPositiveButton("继续检查",(d,w)->{if(s.offline||!s.networkReady)s.reconnect();else s.sync();}).setNeutralButton("恢复连接",(d,w)->s.reconnect()).setNegativeButton("查看原网页",(d,w)->a.showPage(true)).show();}
}
