package local.pocketchat;

import android.content.Context;
import android.content.SharedPreferences;
import java.util.*;
import org.json.*;

/** Named navigation scopes contain metadata filters only, never environment configuration. */
final class EnvironmentSavedViews {
  private SharedPreferences prefs(Context context){return Profiles.global(context).getSharedPreferences("environment-workspace-views",0);}
  static JSONObject view(String name,String query,String group,int filter,int sort){return EnvironmentWorkspacePolicy.view(name,query,group,filter,sort);}
  JSONArray list(Context context){JSONArray values=new JSONArray();for(JSONObject value:EnvironmentWorkspacePolicy.savedViews(prefs(context).getString("saved","[]")))values.put(value);return values;}
  JSONObject current(Context context){
    try{JSONObject value=new JSONObject(prefs(context).getString("current","{}"));return view(value.optString("name"),value.optString("query"),value.isNull("group")?null:value.optString("group"),value.optInt("filter"),value.optInt("sort"));}
    catch(JSONException invalid){return view("","",null,0,0);}
  }
  void remember(Context context,JSONObject value){prefs(context).edit().putString("current",value.toString()).apply();}
  JSONObject find(Context context,String name){if(name==null||name.isEmpty())return null;JSONArray values=list(context);for(int i=0;i<values.length();i++){JSONObject value=values.optJSONObject(i);if(name.equals(value.optString("name")))return value;}return null;}
  boolean save(Context context,JSONObject value){
    String name=value.optString("name");if(name.isEmpty())return false;
    JSONArray before=list(context),after=new JSONArray();boolean replaced=false;
    for(int i=0;i<before.length();i++){JSONObject old=before.optJSONObject(i);if(name.equals(old.optString("name"))){after.put(value);replaced=true;}else after.put(old);}
    if(!replaced){if(after.length()>=8)return false;after.put(value);}
    return prefs(context).edit().putString("saved",after.toString()).putString("current",value.toString()).commit();
  }
  void remove(Context context,String name){JSONArray before=list(context),after=new JSONArray();for(int i=0;i<before.length();i++){JSONObject value=before.optJSONObject(i);if(!name.equals(value.optString("name")))after.put(value);}prefs(context).edit().putString("saved",after.toString()).apply();}
  static boolean sameSettings(JSONObject left,JSONObject right){return left.optString("query").equals(right.optString("query"))&&left.isNull("group")==right.isNull("group")&&left.optString("group").equals(right.optString("group"))&&left.optInt("filter")==right.optInt("filter")&&left.optInt("sort")==right.optInt("sort");}
}
