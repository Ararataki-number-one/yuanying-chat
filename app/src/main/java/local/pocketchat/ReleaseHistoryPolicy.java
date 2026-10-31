package local.pocketchat;

import java.io.*;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.*;
import java.util.function.BooleanSupplier;
import java.util.regex.*;
import org.json.*;

/** Descriptive public history is never an APK authorization source. */
final class ReleaseHistoryPolicy {
  static final int PAGE_SIZE=10,MAX_PAGE=100,MAX_ENTRIES=100,MAX_BYTES=512*1024,SCAN_PAGES=4;
  static final String API="https://api.github.com/repos/"+AppUpdatePolicy.REPO+"/releases",WEB="https://github.com/"+AppUpdatePolicy.REPO+"/releases";
  static final Pattern VERSION=Pattern.compile("(0|[1-9][0-9]{0,8})[.](0|[1-9][0-9]{0,8})[.](0|[1-9][0-9]{0,8})");
  static String url(int page){if(page<1||page>MAX_PAGE)throw new IllegalArgumentException("历史页码无效");return API+"?per_page=10&page="+page;}
  static boolean trusted(String url){try{URI uri=new URI(url);String query=uri.getRawQuery();if(!"https".equals(uri.getScheme())||!"api.github.com".equals(uri.getHost())||uri.getPort()!=-1||uri.getUserInfo()!=null||uri.getFragment()!=null||!API.equals("https://"+uri.getRawAuthority()+uri.getRawPath())||query==null||!query.matches("per_page=10&page=[1-9][0-9]{0,2}"))return false;int page=Integer.parseInt(query.substring("per_page=10&page=".length()));return page<=MAX_PAGE&&url.equals(url(page));}catch(Exception ignored){return false;}}
  static int compare(String a,String b){Matcher ma=VERSION.matcher(a),mb=VERSION.matcher(b);if(!ma.matches()||!mb.matches())throw new IllegalArgumentException("版本无效");for(int i=1;i<=3;i++){int c=Integer.compare(Integer.parseInt(ma.group(i)),Integer.parseInt(mb.group(i)));if(c!=0)return c;}return 0;}
  static long time(String value){try{return value!=null&&value.length()<=40&&value.matches("[0-9]{4}-[0-9]{2}-[0-9]{2}T.*Z")?Instant.parse(value).toEpochMilli():0;}catch(Exception ignored){return 0;}}
  static final class Entry {
    final long id,published;final String tag,version,body,url;final ReleaseNotes notes;
    Entry(long id,String tag,String body,long published){this.id=id;this.tag=tag;this.version=tag.substring(1,tag.length()-6);this.body=body;this.published=published;url=WEB+"/tag/"+tag;notes=ReleaseNotes.legacy(body);}
    JSONObject json()throws JSONException{return new JSONObject().put("id",id).put("tag",tag).put("body",body).put("published",published);}
  }
  static boolean stableTag(String tag){return tag!=null&&tag.startsWith("v")&&tag.endsWith("-gecko")&&VERSION.matcher(tag.substring(1,tag.length()-6)).matches();}
  static Entry entry(JSONObject j){
    if(j==null||!Boolean.FALSE.equals(j.opt("draft"))||!Boolean.FALSE.equals(j.opt("prerelease")))return null;
    String tag=j.optString("tag_name",""),name=j.optString("name","");if(!stableTag(tag)||name.length()>512||name.toLowerCase(Locale.ROOT).matches(".*(?:候选|开发版|预览版|\\b(?:candidate|preview|alpha|beta|dev|rc)[0-9]*\\b).*"))return null;
    String page=WEB+"/tag/"+tag;if(!page.equals(j.optString("html_url","")))return null;
    Object value=j.opt("id");if(!(value instanceof Number)||((Number)value).longValue()<=0||((Number)value).doubleValue()!=((Number)value).longValue())return null;
    String body=j.optString("body","");if(body.length()>ReleaseNotes.MAX_TEXT)body="发布说明较长，请查看此版本的官方发布页。";
    return new Entry(((Number)value).longValue(),tag,body,time(j.optString("published_at","")));
  }
  static List<Entry> parse(String raw)throws IOException {try{JSONArray array=new JSONArray(raw);if(array.length()>PAGE_SIZE)throw new IOException("历史记录响应过大");List<Entry> entries=new ArrayList<>();for(int i=0;i<array.length();i++){Entry entry=entry(array.optJSONObject(i));if(entry!=null)entries.add(entry);}return entries;}catch(JSONException invalid){throw new IOException("历史记录格式暂不支持");}}
  static List<Entry> merge(List<Entry> old,List<Entry> added){Map<String,Entry> map=new HashMap<>();for(Entry e:old)map.put(e.tag,e);for(Entry e:added)map.put(e.tag,e);List<Entry> entries=new ArrayList<>(map.values());entries.sort((a,b)->compare(b.version,a.version));if(entries.size()>MAX_ENTRIES)entries=new ArrayList<>(entries.subList(0,MAX_ENTRIES));return Collections.unmodifiableList(entries);}
  static byte[] read(InputStream input,int maximum,BooleanSupplier cancelled)throws IOException {ByteArrayOutputStream out=new ByteArrayOutputStream();byte[] buffer=new byte[4096];int n;while((n=input.read(buffer))!=-1){if(cancelled.getAsBoolean())throw new IOException("历史读取已结束");if(out.size()+n>maximum)throw new IOException("历史记录响应过大");out.write(buffer,0,n);}if(cancelled.getAsBoolean())throw new IOException("历史读取已结束");return out.toByteArray();}
  static boolean jsonType(String type){if(type==null)return false;String mime=type.split(";",2)[0].trim().toLowerCase(Locale.ROOT);return mime.equals("application/json")||mime.equals("application/vnd.github+json");}
  static String text(byte[] bytes){return new String(bytes,StandardCharsets.UTF_8);}
}
