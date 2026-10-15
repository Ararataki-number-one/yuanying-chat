package local.pocketchat;

import org.json.*;
import java.util.*;

/** Stable ordering and legacy download identity, independent of the Android view layer. */
final class DownloadListPolicy {
  static JSONArray ordered(JSONArray files,JSONArray tasks){
    List<JSONObject> combined=new ArrayList<>();Set<String> savedUris=new HashSet<>();
    for(int i=0;i<files.length();i++){JSONObject r=files.optJSONObject(i);if(r==null)continue;combined.add(r);savedUris.add(r.optString("uri"));}
    for(int i=0;i<tasks.length();i++){JSONObject r=tasks.optJSONObject(i);if(r==null)continue;if("saved".equals(r.optString("state"))&&!r.optString("uri").isEmpty()&&savedUris.contains(r.optString("uri")))continue;combined.add(r);}
    combined.sort((left,right)->{int live=Boolean.compare(busy(right.optString("state")),busy(left.optString("state")));if(live!=0)return live;int time=Long.compare(right.optLong("time"),left.optLong("time"));return time!=0?time:key(left).compareTo(key(right));});
    JSONArray out=new JSONArray();for(JSONObject r:combined)out.put(r);return out;
  }
  static String key(JSONObject row){String id=row.optString("id");return row.optInt("slot")+":"+(id.isEmpty()?"uri:"+row.optString("uri"):"id:"+id);}
  static boolean busy(String state){return Arrays.asList("preparing","downloading","saving","choosing").contains(state);}
  static boolean matches(JSONObject row,int filter){String state=row.optString("state");return filter==0||filter==1&&busy(state)||filter==2&&"saved".equals(state)||filter==3&&"failed".equals(state);}
  static long preservedTime(JSONObject incoming,JSONObject current){long time=incoming.optLong("time");if(time>0)return time;if(current!=null&&incoming.optString("uri").equals(current.optString("uri"))&&incoming.optString("id").equals(current.optString("id")))return current.optLong("time");return 0;}
}
