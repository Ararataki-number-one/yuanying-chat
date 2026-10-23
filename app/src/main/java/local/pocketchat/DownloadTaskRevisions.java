package local.pocketchat;

import org.json.*;
import java.util.*;

/** Merge only this instance's edits; another instance's newer task is authoritative. */
final class DownloadTaskRevisions {
  // JSON object iteration order is not a revision. Re-parsing a saved row must
  // not replace a running task merely because its keys enumerate differently.
  static String value(Object item){
    if(item==null||item==JSONObject.NULL)return "null";
    if(item instanceof JSONObject){JSONObject row=(JSONObject)item;List<String> keys=new ArrayList<>();for(Iterator<String> i=row.keys();i.hasNext();)keys.add(i.next());Collections.sort(keys);StringBuilder out=new StringBuilder("{");for(String key:keys){if(out.length()>1)out.append(',');out.append(JSONObject.quote(key)).append(':').append(value(row.opt(key)));}return out.append('}').toString();}
    if(item instanceof JSONArray){JSONArray rows=(JSONArray)item;StringBuilder out=new StringBuilder("[");for(int i=0;i<rows.length();i++){if(i>0)out.append(',');out.append(value(rows.opt(i)));}return out.append(']').toString();}
    return item instanceof String?JSONObject.quote((String)item):item.toString();
  }
  static Map<String,String> snapshot(JSONArray rows){
    Map<String,String> values=new LinkedHashMap<>();
    for(int i=0;i<rows.length();i++){JSONObject row=rows.optJSONObject(i);if(row!=null)values.put(row.optString("id"),value(row));}
    return values;
  }
  static JSONObject find(JSONArray rows,String id){for(int i=0;i<rows.length();i++){JSONObject row=rows.optJSONObject(i);if(row!=null&&id.equals(row.optString("id")))return row;}return null;}
  static JSONArray merge(JSONArray local,Map<String,String> observed,JSONArray stored){
    Map<String,String> current=snapshot(stored);Set<String> included=new HashSet<>();JSONArray merged=new JSONArray();
    for(int i=0;i<local.length();i++){
      JSONObject row=local.optJSONObject(i);if(row==null)continue;String id=row.optString("id"),before=observed.get(id),now=current.get(id),edited=value(row);
      // Unchanged local rows must follow the store, including removals. A conflicting
      // edit cannot resurrect a recovered, replaced or already deleted task.
      boolean ownChange=!Objects.equals(before,edited)&&Objects.equals(before,now);
      if(ownChange||Objects.equals(edited,now)){merged.put(row);included.add(id);}
      else if(now!=null){merged.put(find(stored,id));included.add(id);}
    }
    for(int i=0;i<stored.length();i++){JSONObject row=stored.optJSONObject(i);if(row!=null&&included.add(row.optString("id")))merged.put(row);}
    return merged;
  }
  static boolean pending(JSONObject row,String uri,String generation){return row!=null&&uri.equals(row.optString("pendingDestination"))&&generation.equals(row.optString("pendingGeneration"));}
  static void clearPending(JSONObject row){row.remove("pendingDestination");row.remove("pendingLocation");row.remove("pendingName");row.remove("pendingGeneration");}
  static void restore(JSONObject row,JSONObject previous){
    List<String> keys=new ArrayList<>();for(Iterator<String> i=row.keys();i.hasNext();)keys.add(i.next());for(String key:keys)row.remove(key);
    try{for(Iterator<String> i=previous.keys();i.hasNext();){String key=i.next();row.put(key,previous.get(key));}}catch(JSONException error){throw new IllegalStateException(error);}
  }
}
