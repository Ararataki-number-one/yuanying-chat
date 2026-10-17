package local.pocketchat;

import org.json.*;
import java.util.*;

/** Stable ordering and legacy download identity, independent of the Android view layer. */
final class DownloadListPolicy {
  /** Read sort fields once per refresh, not on every comparator invocation. */
  private static final class SortRow implements Comparable<SortRow> {
    final JSONObject value;
    final boolean active;
    final long time;
    private String identity;

    SortRow(JSONObject value) {
      this.value=value;
      active=busy(value.optString("state"));
      time=value.optLong("time");
    }

    private String identity() {
      if(identity==null)identity=key(value);
      return identity;
    }

    public int compareTo(SortRow other) {
      int live=Boolean.compare(other.active,active);
      if(live!=0)return live;
      int chronological=Long.compare(other.time,time);
      return chronological!=0?chronological:identity().compareTo(other.identity());
    }
  }

  static JSONArray ordered(JSONArray files,JSONArray tasks){
    List<SortRow> combined=new ArrayList<>(files.length()+tasks.length());Set<String> savedUris=new HashSet<>();
    for(int i=0;i<files.length();i++){JSONObject r=files.optJSONObject(i);if(r==null)continue;combined.add(new SortRow(r));savedUris.add(r.optString("uri"));}
    for(int i=0;i<tasks.length();i++){JSONObject r=tasks.optJSONObject(i);if(r==null)continue;if("saved".equals(r.optString("state"))&&!r.optString("uri").isEmpty()&&savedUris.contains(r.optString("uri")))continue;combined.add(new SortRow(r));}
    Collections.sort(combined);
    JSONArray out=new JSONArray();for(SortRow r:combined)out.put(r.value);return out;
  }
  static String key(JSONObject row){String id=row.optString("id");return row.optInt("slot")+":"+(id.isEmpty()?"uri:"+row.optString("uri"):"id:"+id);}
  static boolean busy(String state){return "preparing".equals(state)||"downloading".equals(state)||"saving".equals(state)||"choosing".equals(state);}
  static boolean matches(JSONObject row,int filter){String state=row.optString("state");return filter==0||filter==1&&busy(state)||filter==2&&"saved".equals(state)||filter==3&&"failed".equals(state);}
  static long preservedTime(JSONObject incoming,JSONObject current){long time=incoming.optLong("time");if(time>0)return time;if(current!=null&&incoming.optString("uri").equals(current.optString("uri"))&&incoming.optString("id").equals(current.optString("id")))return current.optLong("time");return 0;}
}
