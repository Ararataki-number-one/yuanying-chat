package local.pocketchat;

import org.json.*;
import java.util.*;

/** Additive saved-file facts. Unknown is deliberately different from an empty file. */
final class DownloadMetadataValues {
  static final String[] FIELDS={"savedBytes","sizeSource","metadataCheckedAt","metadataRevision","metadataResult","actualName","actualMime","environmentId","environmentGeneration","environmentName"};
  static long bytes(JSONObject row){Object value=row.opt("savedBytes");return value instanceof Integer||value instanceof Long?Math.max(-1,((Number)value).longValue()):-1;}
  static String name(JSONObject row){return row.optString("actualName",row.optString("name","文件"));}
  static String mime(JSONObject row){return row.optString("actualMime",row.optString("mime","application/octet-stream"));}
  static void copy(JSONObject from,JSONObject to){for(String field:FIELDS)if(from.has(field)&&!from.isNull(field))DownloadTasks.put(to,field,from.opt(field));}
  static boolean identity(JSONObject a,JSONObject b){return b!=null&&a.optInt("slot")==b.optInt("slot")&&a.optLong("time")==b.optLong("time")&&a.optString("id").equals(b.optString("id"))&&a.optString("uri").equals(b.optString("uri"));}
  static String revision(JSONObject row){JSONObject value=new JSONObject();for(String key:new String[]{"slot","id","uri","time","name","mime","location","environmentId","environmentGeneration"})if(row.has(key))DownloadTasks.put(value,key,row.opt(key));return DownloadTaskRevisions.value(value);}
  static boolean checked(JSONObject row){return row.optLong("metadataCheckedAt")>0&&revision(row).equals(row.optString("metadataRevision"));}
  static void checked(JSONObject row,long bytes,String source,String result){if(bytes>=0)DownloadTasks.put(row,"savedBytes",bytes,"sizeSource",source);else{row.remove("savedBytes");row.remove("sizeSource");}DownloadTasks.put(row,"metadataCheckedAt",System.currentTimeMillis(),"metadataRevision",revision(row),"metadataResult",result);}
  static void merge(JSONObject incoming,JSONObject stored){
    if(!identity(incoming,stored))return;
    // Old preference/history scans cannot erase a worker's cached metadata.
    boolean published=bytes(incoming)>=0&&"published-copy".equals(incoming.optString("sizeSource"));
    long publishedBytes=published?bytes(incoming):"published-copy".equals(stored.optString("sizeSource"))?bytes(stored):-1;
    if(stored.optLong("metadataCheckedAt")>=incoming.optLong("metadataCheckedAt")||publishedBytes>=0&&!published){
      for(String key:FIELDS)if(!key.startsWith("environment")&&stored.has(key))DownloadTasks.put(incoming,key,stored.opt(key));
    }
    if(publishedBytes>=0)DownloadTasks.put(incoming,"savedBytes",publishedBytes,"sizeSource","published-copy","metadataResult","known");
    for(String key:new String[]{"environmentId","environmentGeneration","environmentName"})if(!incoming.has(key)&&stored.has(key))DownloadTasks.put(incoming,key,stored.opt(key));
  }
  static boolean same(JSONObject a,JSONObject b){for(String key:FIELDS)if(!DownloadTaskRevisions.value(a.opt(key)).equals(DownloadTaskRevisions.value(b.opt(key))))return false;return true;}
  static String location(JSONObject row){String uri=row.optString("uri"),logical=row.optString("location");if(logical.isEmpty()||logical.equals("你选择的保存位置")||logical.equals("原先选择的保存位置"))return uri.isEmpty()?"保存位置未记录":uri;return uri.isEmpty()||logical.equals(uri)?logical:logical+"\n"+uri;}
}
