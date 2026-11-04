package local.pocketchat;

import java.util.*;
import org.json.*;

/** Searchable metadata is normalized once with the worker snapshot, never once per keystroke. */
final class EnvironmentSearchIndex {
  final Map<String,String> text=new HashMap<>();
  EnvironmentSearchIndex(JSONArray rows){for(int i=0;i<rows.length();i++){JSONObject row=rows.optJSONObject(i);if(row!=null)text.put(EnvironmentPresentation.key(row),(row.optString("name")+" "+row.optString("group")+" "+row.optString("notes")+" "+String.format(Locale.ROOT,"%02d",row.optInt("slot")+1)).toLowerCase(Locale.ROOT));}}
  static String[] tokens(String query){String value=query==null?"":query.trim().toLowerCase(Locale.ROOT);return value.isEmpty()?new String[0]:value.split("\\s+");}
  boolean matches(JSONObject row,String[] tokens){String value=text.get(EnvironmentPresentation.key(row));if(value==null)return false;for(String token:tokens)if(!value.contains(token))return false;return true;}
}
