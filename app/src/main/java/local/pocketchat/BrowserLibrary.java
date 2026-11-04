package local.pocketchat;

import android.content.Context;
import android.content.SharedPreferences;
import org.json.*;

/** Bounded, environment-local browser history; never stores page bodies or credentials. */
final class BrowserLibrary {
  final SharedPreferences prefs;
  BrowserLibrary(Context context){prefs=context.getSharedPreferences("universal-browser",0);}
  static int limit(String key){if("history".equals(key))return 200;if("bookmarks".equals(key))return 100;throw new IllegalArgumentException("Unknown browser collection");}
  static String title(String value,String url){String text=value==null||value.isEmpty()?url:value;int end=Math.min(text.length(),300);if(end<text.length()&&end>0&&Character.isHighSurrogate(text.charAt(end-1)))end--;return text.substring(0,end);}
  JSONArray list(String key){
    JSONArray clean=new JSONArray();int cap=limit(key);
    try{String raw=prefs.getString(key,"[]");if(raw.length()>2*1024*1024)return clean;JSONArray stored=new JSONArray(raw);
      java.util.HashSet<String> seen=new java.util.HashSet<>();for(int i=0;i<stored.length()&&clean.length()<cap;i++){JSONObject row=stored.optJSONObject(i);if(row==null)continue;String url=row.optString("url");if(BrowserAddressPolicy.allowed(url)&&seen.add(url))clean.put(J.obj("url",url,"title",title(row.optString("title"),url),"time",row.optLong("time")));}
    }catch(JSONException invalid){}return clean;
  }
  void remember(String key,String url,String title,int limit){
    if(!BrowserAddressPolicy.allowed(url))return;
    int cap=Math.max(1,Math.min(limit,limit(key)));JSONArray next=new JSONArray();next.put(J.obj("url",url,"title",title(title,url),"time",System.currentTimeMillis()));
    JSONArray previous=list(key);for(int i=0;i<previous.length()&&next.length()<cap;i++){JSONObject entry=previous.optJSONObject(i);if(entry!=null&&!url.equals(entry.optString("url")))next.put(entry);}
    prefs.edit().putString(key,next.toString()).apply();
  }
  void remove(String key,String url){JSONArray next=new JSONArray(),old=list(key);for(int i=0;i<old.length();i++){JSONObject row=old.optJSONObject(i);if(row!=null&&!url.equals(row.optString("url")))next.put(row);}prefs.edit().putString(key,next.toString()).apply();}
  boolean bookmarked(String url){JSONArray rows=list("bookmarks");for(int i=0;i<rows.length();i++)if(url.equals(rows.optJSONObject(i)==null?"":rows.optJSONObject(i).optString("url")))return true;return false;}
  void clearHistory(){prefs.edit().remove("history").apply();}
}
