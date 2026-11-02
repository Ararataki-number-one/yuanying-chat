package local.pocketchat;

import java.io.IOException;
import java.util.*;
import java.util.regex.*;
import org.json.*;

/** Release discovery is separate from authorization by the exact signed APK manifest. */
final class AppUpdateCatalog {
  static final class Empty extends IOException {Empty(String channel){super("暂未发现可用的"+AppUpdatePolicy.channelName(channel)+"，可稍后重新检查");}}
  interface Fetcher {String read(String url,int maximum)throws IOException;}
  static final int PAGE_SIZE=50,MAX_PAGES=4,MAX_BYTES=2*1024*1024;
  static final String API="https://api.github.com/repos/"+AppUpdatePolicy.REPO+"/releases";
  static final Pattern TAG=Pattern.compile("v([0-9]+[.][0-9]+(?:[.][0-9]+)?)(?:-candidate([1-9][0-9]{0,2}))?-gecko");
  static String url(int page){if(page<1||page>MAX_PAGES)throw new IllegalArgumentException();return API+"?per_page="+PAGE_SIZE+"&page="+page;}
  static boolean trusted(String url){for(int i=1;i<=MAX_PAGES;i++)if(url(i).equals(url))return true;return false;}
  static final class Release {
    final String version,channel,tag,manifestUrl,apkUrl,publishedAt,notes;final int candidateNumber;
    Release(String version,String channel,int number,String published,String notes){this.version=version;this.channel=channel;candidateNumber=number;tag=AppUpdatePolicy.tag(version,channel,number);publishedAt=published;this.notes=notes.length()<=12000?notes:"发布说明较长，请查看此版本的官方发布页。";String base="https://github.com/"+AppUpdatePolicy.REPO+"/releases/download/"+tag+"/";manifestUrl=base+"release-manifest.json";apkUrl=AppUpdatePolicy.asset(version,channel,number);}
  }
  static Release release(JSONObject row){
    if(row==null||!Boolean.FALSE.equals(row.opt("draft")))return null;
    Matcher tag=TAG.matcher(row.optString("tag_name"));if(!tag.matches()||!AppUpdatePolicy.version(tag.group(1)))return null;
    String version=tag.group(1),channel=tag.group(2)==null?AppUpdatePolicy.versionChannel(version):"candidate";
    if("stable".equals(channel)&&!Boolean.FALSE.equals(row.opt("prerelease")))return null;
    Release r=new Release(version,channel,tag.group(2)==null?0:Integer.parseInt(tag.group(2)),row.optString("published_at"),row.optString("body"));
    if(!("https://github.com/"+AppUpdatePolicy.REPO+"/releases/tag/"+r.tag).equals(row.optString("html_url")))return null;
    JSONArray assets=row.optJSONArray("assets");boolean manifest=false,apk=false;
    if(assets!=null&&assets.length()<=100)for(int i=0;i<assets.length();i++){JSONObject a=assets.optJSONObject(i);if(a==null||!"uploaded".equals(a.optString("state")))continue;String url=a.optString("browser_download_url");if("release-manifest.json".equals(a.optString("name"))&&r.manifestUrl.equals(url))manifest=true;if(("PocketChat-"+version+"-gecko-arm64.apk").equals(a.optString("name"))&&r.apkUrl.equals(url))apk=true;}
    return manifest&&apk?r:null;
  }
  static List<Release> parse(String raw,String channel)throws IOException {
    if(!AppUpdatePolicy.channel(channel))throw new IOException("更新通道无效");
    if(raw==null||raw.getBytes(java.nio.charset.StandardCharsets.UTF_8).length>MAX_BYTES)throw new IOException("更新列表过大");
    try{JSONArray rows=new JSONArray(raw);if(rows.length()>PAGE_SIZE)throw new IOException("更新列表过大");List<Release> out=new ArrayList<>();for(int i=0;i<rows.length();i++){Release r=release(rows.optJSONObject(i));if(r!=null&&channel.equals(r.channel))out.add(r);}return out;}catch(JSONException invalid){throw new IOException("更新列表格式暂不支持",invalid);}
  }
  static int compare(Release a,Release b){String[] av=a.version.split("[.]"),bv=b.version.split("[.]");for(int i=0;i<3;i++){int c=Integer.compare(i<av.length?Integer.parseInt(av[i]):0,i<bv.length?Integer.parseInt(bv[i]):0);if(c!=0)return c;}return Integer.compare(a.candidateNumber,b.candidateNumber);}
  static Release latest(List<Release> releases){Release best=null;for(Release r:releases)if(best==null||compare(r,best)>0)best=r;return best;}
  static JSONObject feed(Release release,JSONObject manifest)throws IOException {
    try{
      if(!release.version.equals(manifest.optString("version"))||!("PocketChat-"+release.version+"-gecko-arm64.apk").equals(manifest.optString("filename")))throw new IOException("发布版本与安装包不符");
      if(manifest.has("abi")&&!"arm64-v8a".equals(manifest.optString("abi")))throw new IOException("安装包架构不符");
      if(manifest.has("downloadUrl")&&!release.apkUrl.equals(manifest.optString("downloadUrl")))throw new IOException("发布版本与下载地址不符");
      // Older 2.0.x releases used the name stable; the public tag now places them in beta.
      String declared=manifest.optString("channel",release.channel);
      if(!release.channel.equals(declared)&&!("beta".equals(release.channel)&&"stable".equals(declared)))throw new IOException("发布版本与更新通道不符");
      Object sequence=manifest.opt("candidateNumber");if("candidate".equals(release.channel)&&(!(sequence instanceof Number)||((Number)sequence).doubleValue()!=release.candidateNumber))throw new IOException("候选版序号不符");
      JSONObject feed=new JSONObject(manifest.toString());feed.put("schema",1).put("channel",release.channel).put("candidateNumber",release.candidateNumber).put("releaseTag",release.tag).put("downloadUrl",release.apkUrl).put("abi","arm64-v8a").put("minSdk",manifest.optInt("minSdk",26)).put("publishedAt",release.publishedAt).put("notes",manifest.optString("notes",release.notes));
      new AppUpdateInfo(feed);return feed;
    }catch(JSONException invalid){throw new IOException("更新清单格式暂不支持",invalid);}
  }
  static JSONObject fetch(String channel,Fetcher fetcher)throws IOException {
    try{List<Release> releases=new ArrayList<>();for(int page=1;page<=MAX_PAGES;page++){String raw=fetcher.read(url(page),MAX_BYTES);releases.addAll(parse(raw,channel));if(new JSONArray(raw).length()<PAGE_SIZE)break;}
      Release release=latest(releases);if(release==null)throw new Empty(channel);return feed(release,new JSONObject(fetcher.read(release.manifestUrl,65536)));
    }catch(JSONException invalid){throw new IOException("更新清单格式暂不支持",invalid);}
  }
}
