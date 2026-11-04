package local.pocketchat;

import java.util.*;
import org.json.*;

/** Display-only values exclude heartbeat timestamps and hidden draft/configuration payloads. */
final class EnvironmentPresentation {
  static String key(JSONObject row){return new JSONArray().put(row.optInt("slot")).put(row.optInt("generation")).put(row.optString("environmentId")).toString();}
  static boolean active(JSONObject row,Set<Integer> running){return running.contains(row.optInt("pid"));}
  static boolean fresh(JSONObject row,long now){long seen=row.optLong("seen");return seen>0&&now>=seen&&now-seen<60000;}
  static String recent(long opened,long now){
    if(opened<=0)return "";long elapsed=Math.max(0,now-opened);
    if(elapsed<60000)return "刚刚";if(elapsed<3600000)return elapsed/60000+" 分钟前";if(elapsed<86400000)return elapsed/3600000+" 小时前";if(elapsed<604800000)return elapsed/86400000+" 天前";
    return new java.text.SimpleDateFormat("MM-dd HH:mm",Locale.getDefault()).format(new Date(opened));
  }
  static String status(JSONObject row,boolean active,boolean fresh){boolean problem=!row.optString("problem").isEmpty();return problem?(active?"需处理":"上次异常"):active?(row.optBoolean("waiting")?"等待回复":fresh?"运行中":"待核对"):"未运行";}
  static String network(JSONObject row,boolean active,boolean fresh){String mode=row.optString("mode");if(mode.isEmpty())return "暂无网络记录";if(!active)return mode;if(!fresh)return mode+" · 状态待核对";String problem=row.optString("problem");return mode+" · "+(!problem.isEmpty()?problem:row.optBoolean("connected")?"已连接":"待连接");}
  static String stamp(JSONObject row,Set<Integer> running,long now,int defaultSlot,boolean selecting,boolean selected){
    boolean active=active(row,running),fresh=fresh(row,now),problem=!row.optString("problem").isEmpty();
    return new JSONArray().put(key(row)).put(row.optString("name")).put(row.optString("group")).put(row.optBoolean("favorite")).put(row.optBoolean("desktopSite"))
      .put(!row.optString("draft").isEmpty()).put(status(row,active,fresh)).put(network(row,active,fresh)).put(problem?"problem":active?"active":"inactive")
      .put(recent(row.optLong("opened"),now)).put(row.optInt("slot")==defaultSlot).put(selecting).put(selecting&&selected).toString();
  }
  static boolean visible(JSONObject row,Set<Integer> running,int filter,String query,String group){
    if(!EnvironmentWorkspacePolicy.eligible(row))return false;boolean active=active(row,running);
    if(filter==1&&!row.optBoolean("favorite")||filter==2&&!active||filter==3&&!(row.optBoolean("waiting")&&active)||filter==4&&row.optString("problem").isEmpty())return false;
    return (group==null||group.equals(row.optString("group")))&&(query==null||query.isEmpty()||EnvironmentWorkspacePolicy.matches(row,query));
  }
  static final class Binding {
    String stamp;boolean changed(String next){if(next.equals(stamp))return false;stamp=next;return true;}
  }
}
