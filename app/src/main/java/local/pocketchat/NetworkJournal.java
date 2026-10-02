package local.pocketchat;

import android.content.*;
import org.json.*;
import java.util.*;
import java.text.SimpleDateFormat;

/** Fixed event categories only, without subscription URLs, credentials or IPs. */
final class NetworkJournal {
  static final Set<String> STAGES=new HashSet<>(Arrays.asList("未连接","手机网络不可用","等待手机 VPN","代理连接中断","检查应用专用代理","检查网页连接","正在核对网页","已连接","连接未完成","固定出口需要检查","等待重连","需要手动重连"));
  static void record(ChatSession s){String stage=STAGES.contains(s.connectionStage)?s.connectionStage:s.networkReady?"已连接":"状态更新";SharedPreferences p=s.context.getSharedPreferences("network-journal",0);String mode=s.internalNetwork()?"内置网络":s.prefs.getString("proxy","").isEmpty()?"手机网络":"应用代理";String identity=stage+"|"+mode+"|"+s.offline;if(identity.equals(p.getString("last","")))return;JSONArray rows=J.parse(p.getString("data","{}")).optJSONArray("rows"),next=new JSONArray();next.put(J.obj("at",System.currentTimeMillis(),"stage",stage,"mode",mode,"offline",s.offline));if(rows!=null)for(int i=0;i<Math.min(99,rows.length());i++)next.put(rows.optJSONObject(i));p.edit().putString("last",identity).putString("data",J.obj("rows",next).toString()).apply();}
  static String text(Context c){JSONArray rows=J.parse(c.getSharedPreferences("network-journal",0).getString("data","{}")).optJSONArray("rows");if(rows==null||rows.length()==0)return "暂无网络事件记录。";StringBuilder out=new StringBuilder("仅记录本环境最近 100 个状态变化，不含订阅、账号密码、Cookie 或出口地址。\n");for(int i=0;i<rows.length();i++){JSONObject r=rows.optJSONObject(i);out.append("\n").append(new SimpleDateFormat("MM-dd HH:mm:ss",Locale.getDefault()).format(new Date(r.optLong("at")))).append(" · ").append(r.optString("mode")).append(" · ").append(r.optString("stage"));}return out.toString();}
}
