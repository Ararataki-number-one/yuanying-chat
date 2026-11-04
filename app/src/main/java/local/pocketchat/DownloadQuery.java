package local.pocketchat;

import org.json.*;
import java.text.Normalizer;
import java.util.*;
import java.util.regex.Pattern;

/** Full-library discovery runs before bounded display paging and never grants file access. */
final class DownloadQuery {
  static final String[] KINDS={"全部类型","文档","图片","视频与音频","压缩包","安装包","其他文件"};
  static final String[] SORTS={"任务优先","最新在前","最早在前","大文件优先","按文件名"};
  final String text,owner;final int kind,sort;final String identityKey;final String[] tokens;
  private static final Pattern IMAGE=Pattern.compile(".*\\.(png|jpe?g|gif|webp|heic|heif|bmp|svg|avif)$"),MEDIA=Pattern.compile(".*\\.(mp4|mkv|webm|mov|mp3|m4a|wav|ogg|flac)$"),ARCHIVE=Pattern.compile(".*\\.(zip|rar|7z|tar|gz|xz|bz2)$"),DOCUMENT=Pattern.compile(".*\\.(pdf|txt|md|csv|json|docx?|xlsx?|pptx?|epub|rtf)$");
  DownloadQuery(String text,String owner,int kind,int sort){this.text=text==null?"":text.substring(0,Math.min(200,text.length()));this.owner=owner==null?"":owner;this.kind=Math.max(0,Math.min(KINDS.length-1,kind));this.sort=Math.max(0,Math.min(SORTS.length-1,sort));identityKey=new JSONArray().put(this.text).put(this.owner).put(this.kind).put(this.sort).toString();String normalized=normalize(this.text).trim();tokens=normalized.isEmpty()?new String[0]:normalized.split("\\s+");}
  static DownloadQuery all(){return new DownloadQuery("","",0,0);}
  String key(){return identityKey;}
  boolean restricted(){return !text.trim().isEmpty()||!owner.isEmpty()||kind!=0;}
  DownloadQuery text(String next){return new DownloadQuery(next,owner,kind,sort);}
  DownloadQuery owner(String next){return new DownloadQuery(text,next,kind,sort);}
  DownloadQuery kind(int next){return new DownloadQuery(text,owner,next,sort);}
  DownloadQuery sort(int next){return new DownloadQuery(text,owner,kind,next);}
  static String normalize(String value){return Normalizer.normalize(value,Normalizer.Form.NFKC).toLowerCase(Locale.ROOT);}
  static String identity(JSONObject row){
    String id=row.optString("environmentId");Object generation=row.opt("environmentGeneration");
    if(id.isEmpty()||!(generation instanceof Integer||generation instanceof Long)||((Number)generation).longValue()<0)return "unknown";
    return identity(row.optInt("slot"),id,((Number)generation).longValue());
  }
  static String identity(int slot,String id,long generation){return slot+":"+id+":"+generation;}
  static String identity(DownloadOwnerLabels.Owner owner){return identity(owner.slot,owner.id,owner.generation);}
  static boolean historical(JSONObject row,Map<Integer,DownloadOwnerLabels.Owner> owners){
    String id=identity(row);if("unknown".equals(id))return false;
    DownloadOwnerLabels.Owner owner=owners.get(row.optInt("slot"));
    return owner==null||!owner.created||owner.deleting||owner.resetting||!id.equals(identity(owner));
  }
  static int kind(JSONObject row){
    String mime=normalize(row.optString("actualMime",row.optString("mime","application/octet-stream"))),name=normalize(row.optString("actualName",row.optString("name")));
    if(mime.startsWith("image/")||IMAGE.matcher(name).matches())return 2;
    if(mime.startsWith("video/")||mime.startsWith("audio/")||MEDIA.matcher(name).matches())return 3;
    if(mime.equals("application/vnd.android.package-archive")||name.endsWith(".apk")||name.endsWith(".apks"))return 5;
    if(mime.contains("zip")||mime.contains("compressed")||mime.contains("archive")||ARCHIVE.matcher(name).matches())return 4;
    if(mime.startsWith("text/")||mime.contains("pdf")||mime.contains("officedocument")||mime.contains("msword")||mime.contains("opendocument")||DOCUMENT.matcher(name).matches())return 1;
    return 6;
  }
  boolean matches(JSONObject row,Map<Integer,DownloadOwnerLabels.Owner> owners){
    if(kind!=0&&kind(row)!=kind)return false;
    if(!owner.isEmpty()&&!("historical".equals(owner)?historical(row,owners):owner.equals(identity(row))))return false;
    if(tokens.length==0)return true;
    String haystack=normalize(row.optString("actualName",row.optString("name","文件"))+" "+row.optString("actualMime",row.optString("mime"))+" "+DownloadOwnerLabels.label(row,owners));
    for(String token:tokens)if(!haystack.contains(token))return false;
    return true;
  }
  static long size(JSONObject row){Object value=row.opt("savedBytes");if(value instanceof Integer||value instanceof Long)return Math.max(-1,((Number)value).longValue());return row.optLong("total",-1);}
  private static final class SortValue {
    final JSONObject row;final long time,size;final String name;String key;
    SortValue(JSONObject row,int sort){this.row=row;time=row.optLong("time");size=sort==3?size(row):-1;name=sort==4?normalize(row.optString("actualName",row.optString("name"))):"";}
    String key(){if(key==null)key=DownloadListPolicy.key(row);return key;}
  }
  JSONArray select(JSONArray rows,int filter,Map<Integer,DownloadOwnerLabels.Owner> owners){
    List<JSONObject> values=new ArrayList<>();for(int i=0;i<rows.length();i++){JSONObject row=rows.optJSONObject(i);if(row!=null&&DownloadListPolicy.matches(row,filter)&&matches(row,owners))values.add(row);}
    if(sort>0){List<SortValue> prepared=new ArrayList<>(values.size());for(JSONObject row:values)prepared.add(new SortValue(row,sort));
      Comparator<SortValue> newest=(left,right)->{int time=Long.compare(right.time,left.time);return time!=0?time:left.key().compareTo(right.key());};
      if(sort==1)prepared.sort(newest);
      else if(sort==2)prepared.sort((left,right)->{int time=Long.compare(left.time,right.time);return time!=0?time:left.key().compareTo(right.key());});
      else if(sort==3)prepared.sort((left,right)->{int size=Long.compare(right.size,left.size);return size!=0?size:newest.compare(left,right);});
      else prepared.sort((left,right)->{int name=left.name.compareTo(right.name);return name!=0?name:newest.compare(left,right);});
      values.clear();for(SortValue row:prepared)values.add(row.row);
    }
    JSONArray selected=new JSONArray();for(JSONObject row:values)selected.put(row);return selected;
  }
}
