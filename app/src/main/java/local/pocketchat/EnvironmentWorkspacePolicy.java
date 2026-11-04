package local.pocketchat;

import java.util.*;
import org.json.*;

/** Read-only environment projections shared by the inbox, switcher and saved views. */
final class EnvironmentWorkspacePolicy {
  static final int MAX_VIEWS=8;
  static boolean eligible(JSONObject row){
    return row!=null&&Boolean.TRUE.equals(row.opt("created"))&&!row.optBoolean("deleting")&&!row.optBoolean("resetting");
  }
  private static boolean identityNumber(Object value){return (value instanceof Integer||value instanceof Long)&&((Number)value).longValue()>=0&&((Number)value).longValue()<=Integer.MAX_VALUE;}
  static boolean sameIdentity(JSONObject expected,JSONObject actual){
    if(!eligible(expected)||!eligible(actual))return false;
    Object slot=expected.opt("slot"),generation=expected.opt("generation"),id=expected.opt("environmentId");
    return identityNumber(slot)&&identityNumber(generation)&&identityNumber(actual.opt("slot"))&&identityNumber(actual.opt("generation"))
      &&id instanceof String&&!((String)id).isEmpty()&&actual.opt("environmentId") instanceof String
      &&expected.optInt("slot",-1)==actual.optInt("slot",-2)
      &&expected.optInt("generation",-1)==actual.optInt("generation",-2)
      &&id.equals(actual.opt("environmentId"));
  }
  static boolean matches(JSONObject row,String query){
    if(row==null)return false;
    String text=(row.optString("name")+" "+row.optString("group")+" "+row.optString("notes")+" "+String.format(Locale.ROOT,"%02d",row.optInt("slot")+1)).toLowerCase(Locale.ROOT);
    String value=query==null?"":query.trim().toLowerCase(Locale.ROOT);
    if(value.isEmpty())return true;
    for(String token:value.split("\\s+"))if(!text.contains(token))return false;
    return true;
  }
  static boolean running(JSONObject row,Set<Integer> live,long now){
    if(row==null||live==null||row.optInt("pid")<=0||!live.contains(row.optInt("pid")))return false;
    long seen=row.optLong("seen");
    return seen>0&&now>=seen&&now-seen<=60000;
  }
  static int priority(JSONObject row,Set<Integer> live,long now){
    if(row!=null&&!row.optString("problem").trim().isEmpty())return 0;
    if(row!=null&&!row.optString("draft").trim().isEmpty())return 1;
    if(row!=null&&row.optBoolean("waiting")&&running(row,live,now))return 2;
    return 3;
  }
  static String task(JSONObject row,Set<Integer> live,long now){
    int value=priority(row,live,now);
    if(value==0)return "需要检查网络";
    if(value==1)return "有配置草稿";
    if(value==2)return "正在等待回复";
    return row!=null&&row.optBoolean("waiting")?"上次等待状态待核对":"继续会话";
  }
  static List<JSONObject> actionable(JSONArray rows,Set<Integer> live,long now){
    List<JSONObject> out=new ArrayList<>();
    if(rows==null)return out;
    for(int i=0;i<rows.length();i++){
      JSONObject row=rows.optJSONObject(i);
      if(eligible(row)&&priority(row,live,now)<3)out.add(row);
    }
    out.sort((left,right)->{
      int rank=Integer.compare(priority(left,live,now),priority(right,live,now));
      if(rank!=0)return rank;
      int recent=Long.compare(right.optLong("opened"),left.optLong("opened"));
      return recent!=0?recent:Integer.compare(left.optInt("slot"),right.optInt("slot"));
    });
    return out;
  }
  static String bounded(String value,int limit){
    String text=value==null?"":value.trim();
    if(text.length()<=limit)return text;
    int end=limit;
    if(end>0&&Character.isHighSurrogate(text.charAt(end-1)))end--;
    return text.substring(0,end);
  }
  static JSONObject view(String name,String query,String group,int filter,int sort){
    JSONObject value=new JSONObject();
    try{
      value.put("name",bounded(name,24));value.put("query",bounded(query,120));
      value.put("group",group==null?JSONObject.NULL:bounded(group,12));
      value.put("filter",Math.max(0,Math.min(4,filter)));value.put("sort",Math.max(0,Math.min(2,sort)));
    }catch(JSONException impossible){throw new IllegalArgumentException(impossible);}
    return value;
  }
  static List<JSONObject> savedViews(String json){
    List<JSONObject> out=new ArrayList<>();
    if(json==null||json.length()>16384)return out;
    try{
      JSONArray values=new JSONArray(json);Set<String> names=new HashSet<>();
      for(int i=0;i<values.length()&&out.size()<MAX_VIEWS;i++){
        JSONObject value=values.optJSONObject(i);
        if(value==null||!(value.opt("name") instanceof String)||!(value.opt("query") instanceof String)
            ||!value.has("group")||(!value.isNull("group")&&!(value.opt("group") instanceof String))
            ||!(value.opt("filter") instanceof Number)||!(value.opt("sort") instanceof Number))continue;
        String name=bounded(value.optString("name"),24);
        if(name.isEmpty()||!names.add(name))continue;
        out.add(view(name,value.optString("query"),value.isNull("group")?null:value.optString("group"),value.optInt("filter"),value.optInt("sort")));
      }
    }catch(JSONException invalid){}
    return out;
  }
}
