package local.pocketchat;

import org.json.*;
import java.util.*;

/** Explicit file choices survive searching and paging, with exact publication identities. */
final class DownloadCollection {
  static final int LIMIT=30;
  final Map<String,JSONObject> selected=new LinkedHashMap<>();
  static String key(JSONObject row){return new JSONArray().put(row.optInt("slot")).put(row.optString("id")).put(row.optString("uri")).put(row.optLong("time")).toString();}
  static boolean eligible(JSONObject row){return row!=null&&"saved".equals(row.optString("state"))&&row.optString("uri").startsWith("content://");}
  boolean contains(JSONObject row){return row!=null&&containsKey(key(row));}
  boolean containsKey(String key){return selected.containsKey(key);}
  boolean toggle(JSONObject row){
    if(!eligible(row))return false;String key=key(row);if(selected.remove(key)!=null)return true;
    if(selected.size()>=LIMIT)return false;
    // The same URI cannot be sent twice or silently replaced by a newer publication.
    for(JSONObject prior:selected.values())if(prior.optString("uri").equals(row.optString("uri")))return false;
    try{selected.put(key,new JSONObject(row.toString()));return true;}catch(JSONException invalid){return false;}
  }
  JSONArray snapshot(){JSONArray out=new JSONArray();for(JSONObject row:selected.values())out.put(row);return out;}
  int size(){return selected.size();}
  void clear(){selected.clear();}
  void restore(JSONArray rows){clear();if(rows!=null)for(int i=0;i<rows.length()&&size()<LIMIT;i++)toggle(rows.optJSONObject(i));}
  static String mime(JSONArray rows){String type="";for(int i=0;i<rows.length();i++){JSONObject row=rows.optJSONObject(i);if(row==null)continue;String mime=row.optString("actualMime",row.optString("mime","application/octet-stream"));if(type.isEmpty())type=mime;else if(!type.equals(mime))return "*/*";}return type.isEmpty()?"*/*":type;}
}
