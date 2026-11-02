package local.pocketchat;

import com.sun.net.httpserver.HttpServer;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import org.json.*;

/** Production discovery, manifest validation and transfer URLs; synthetic public releases. */
public final class UpdateChannelsHost {
  static final JSONArray checks=new JSONArray();
  static final String HASH="a".repeat(64);
  static void check(boolean ok,String name)throws Exception{if(!ok)throw new AssertionError(name);checks.put(new JSONObject().put("name",name).put("pass",true));}
  interface Checked {void run()throws Exception;}
  static void reject(Checked run,String name)throws Exception{try{run.run();throw new AssertionError(name);}catch(IOException expected){check(true,name);}}
  static JSONObject release(String version,String channel,int number)throws Exception{
    String tag=AppUpdatePolicy.tag(version,channel,number),base="https://github.com/"+AppUpdatePolicy.REPO+"/releases/download/"+tag+"/";
    return new JSONObject().put("draft",false).put("prerelease",channel.equals("candidate")).put("tag_name",tag)
      .put("html_url","https://github.com/"+AppUpdatePolicy.REPO+"/releases/tag/"+tag).put("body","本次更新说明").put("published_at","2026-11-02T00:00:00Z")
      .put("assets",new JSONArray().put(new JSONObject().put("name","release-manifest.json").put("state","uploaded").put("browser_download_url",base+"release-manifest.json"))
        .put(new JSONObject().put("name","PocketChat-"+version+"-gecko-arm64.apk").put("state","uploaded").put("browser_download_url",AppUpdatePolicy.asset(version,channel,number))));
  }
  static JSONObject manifest(String version,String channel,int number)throws Exception{
    return new JSONObject().put("version",version).put("versionCode",100+number).put("channel",channel).put("candidateNumber",channel.equals("candidate")?number:JSONObject.NULL)
      .put("filename","PocketChat-"+version+"-gecko-arm64.apk").put("package","local.pocketchat").put("bytes",4096).put("sha256",HASH).put("signerSha256",AppUpdatePolicy.SIGNER);
  }
  static void policy()throws Exception{
    JSONArray all=new JSONArray().put(release("2.0.9","beta",0)).put(release("2.0.46","beta",0))
      .put(release("2.1","stable",0)).put(release("2.1.1","stable",0)).put(release("2.0.46","candidate",2)).put(release("2.0.46","candidate",3));
    check(AppUpdateCatalog.parse(all.toString(),"stable").size()==2,"Stable channel excludes beta and candidate releases");
    check(AppUpdateCatalog.parse(all.toString(),"beta").size()==2,"2.0.x releases belong only to beta");
    check(AppUpdateCatalog.parse(all.toString(),"candidate").size()==2,"Candidate tags are discoverable even as GitHub prereleases");
    check(AppUpdateCatalog.latest(AppUpdateCatalog.parse(all.toString(),"beta")).version.equals("2.0.46"),"Beta ordering compares version numbers rather than text");
    check(AppUpdateCatalog.latest(AppUpdateCatalog.parse(all.toString(),"candidate")).candidateNumber==3,"Candidate sequence chooses candidate3 over candidate2");
    check(AppUpdateCatalog.latest(AppUpdateCatalog.parse(all.toString(),"stable")).version.equals("2.1.1"),"Two-part stable versions coexist with patch versions");
    check(AppUpdateCatalog.latest(AppUpdateCatalog.parse("[]","stable"))==null,"An empty channel cannot fall back to another channel");
    JSONObject draft=release("2.9","stable",0).put("draft",true),preview=release("2.9","stable",0).put("prerelease",true);
    check(AppUpdateCatalog.release(draft)==null&&AppUpdateCatalog.release(preview)==null,"Drafts and unstable stable-tag releases do not enter stable");
    JSONObject missing=release("2.0.99","beta",0);missing.getJSONArray("assets").remove(0);
    check(AppUpdateCatalog.release(missing)==null,"A release without an exact manifest is unavailable");
    JSONObject foreign=release("2.0.99","candidate",1);foreign.getJSONArray("assets").getJSONObject(0).put("browser_download_url","https://example.invalid/release-manifest.json");
    check(AppUpdateCatalog.release(foreign)==null,"Foreign manifest destinations are rejected before any download");
    AppUpdateCatalog.Release candidate=AppUpdateCatalog.release(release("2.0.46","candidate",2));
    AppUpdateInfo info=new AppUpdateInfo(AppUpdateCatalog.feed(candidate,manifest("2.0.46","candidate",2)));
    check(info.channel.equals("candidate")&&info.candidateNumber==2&&info.url.contains("candidate2-gecko/"),"Candidate manifest binds to its exact candidate2 download path");
    check(info.display().equals("2.0.46 候选2 · 候选版")&&info.notes.equals("本次更新说明"),"Candidate label and release-body notes retain their meaning");
    check(AppUpdateTransfer.officialOrigin(info.url),"The real downloader accepts an exact candidate APK URL");
    check(!AppUpdateTransfer.officialOrigin(info.url.replace("candidate2","candidate0"))&&!AppUpdateTransfer.officialOrigin(info.url+"?redirect=x"),"Invalid candidate and query-altered APK identities are rejected");
    AppUpdateCatalog.Release stable=AppUpdateCatalog.release(release("2.1","stable",0));
    AppUpdateInfo stableInfo=new AppUpdateInfo(AppUpdateCatalog.feed(stable,manifest("2.1","stable",0)));
    check(AppUpdateTransfer.officialOrigin(stableInfo.url)&&stableInfo.channel.equals("stable"),"2.x stable versions pass metadata and transfer validation");
    AppUpdateCatalog.Release beta=AppUpdateCatalog.release(release("2.0.45","beta",0));
    check(new AppUpdateInfo(AppUpdateCatalog.feed(beta,manifest("2.0.45","stable",0))).channel.equals("beta"),"Historical 2.0.x stable labels migrate to the beta channel");
    reject(()->AppUpdateCatalog.feed(candidate,manifest("2.0.46","candidate",1)),"Mismatched candidate sequence cannot authorize a download");
    reject(()->AppUpdateCatalog.feed(candidate,manifest("2.0.46","candidate",2).put("candidateNumber",2.5)),"Fractional candidate sequences cannot be truncated to a different release");
    reject(()->AppUpdateCatalog.feed(candidate,manifest("2.0.46","candidate",2).put("candidateNumber","2")),"Candidate sequence is a number rather than coerced text");
    reject(()->AppUpdateCatalog.feed(candidate,manifest("2.0.45","candidate",2)),"A different version manifest cannot authorize the selected tag");
    reject(()->AppUpdateCatalog.feed(candidate,manifest("2.0.46","candidate",2).put("sha256","tampered")),"An invalid APK checksum is rejected");
    reject(()->AppUpdateCatalog.feed(candidate,manifest("2.0.46","candidate",2).put("signerSha256","b".repeat(64))),"Only the original signing certificate is accepted");
    reject(()->AppUpdateCatalog.feed(candidate,manifest("2.0.46","candidate",2).put("package","other.app")),"A different application package is rejected");
    reject(()->AppUpdateCatalog.feed(candidate,manifest("2.0.46","candidate",2).put("abi","x86_64")),"A mismatched declared ABI cannot be overwritten during normalization");
    reject(()->AppUpdateCatalog.feed(candidate,manifest("2.0.46","candidate",2).put("downloadUrl","https://example.invalid/app.apk")),"A declared foreign download URL cannot be overwritten during normalization");
    reject(()->new AppUpdateInfo(AppUpdateCatalog.feed(candidate,manifest("2.0.46","candidate",2)).put("releaseTag","v2.0.46-candidate3-gecko")),"Metadata cannot relabel candidate2 as candidate3");
    String api=AppUpdateCatalog.url(1);
    check(AppUpdatePolicy.metadataOrigin(api)&&AppUpdatePolicy.metadataTarget(api,api),"Discovery requests use the selected repository releases API");
    check(!AppUpdatePolicy.metadataTarget(api+"&token=private",api)&&!AppUpdatePolicy.metadataTarget("https://example.invalid/",api),"API discovery rejects altered and external redirects");
    check(AppUpdatePolicy.metadataOrigin(candidate.manifestUrl)&&AppUpdatePolicy.metadataTarget("https://release-assets.githubusercontent.com/github-production-release-asset/fixture?signature=x",candidate.manifestUrl),"Manifest download permits the official release-asset redirect");
    check(!AppUpdatePolicy.metadataTarget("http://release-assets.githubusercontent.com/github-production-release-asset/x",candidate.manifestUrl),"Manifest redirects retain HTTPS verification");
    check(!AppUpdatePolicy.metadataOrigin(api.replace("api.github.com","api.github.com.evil.invalid")),"Lookalike discovery hosts are rejected");
    reject(()->AppUpdateCatalog.parse("{}","beta"),"Malformed discovery responses fail the check");
    JSONArray over=new JSONArray();for(int i=0;i<51;i++)over.put(release("2.0.46","candidate",2));
    reject(()->AppUpdateCatalog.parse(over.toString(),"candidate"),"Discovery page count is bounded");
  }
  static void transport()throws Exception{
    HttpServer server=HttpServer.create(new InetSocketAddress("127.0.0.1",0),0);List<String> requests=new ArrayList<>();
    JSONArray rows=new JSONArray().put(release("2.0.46","beta",0)).put(release("2.0.46","candidate",2));
    server.createContext("/",exchange->{try{String path=exchange.getRequestURI().getPath();String text=path.equals("/list")?rows.toString():manifest("2.0.46","candidate",2).toString();byte[] body=text.getBytes(StandardCharsets.UTF_8);exchange.getResponseHeaders().set("Content-Type","application/json");exchange.sendResponseHeaders(200,body.length);exchange.getResponseBody().write(body);}catch(Exception invalid){throw new RuntimeException(invalid);}finally{exchange.close();}});server.start();
    try{
      AppUpdateCatalog.Fetcher fetcher=(url,maximum)->{
        requests.add(url);String path=AppUpdateCatalog.trusted(url)?"/list":"/manifest";
        HttpURLConnection connection=(HttpURLConnection)new URL("http://127.0.0.1:"+server.getAddress().getPort()+path).openConnection();
        try(InputStream in=connection.getInputStream();ByteArrayOutputStream out=new ByteArrayOutputStream()){byte[] buffer=new byte[4096];int count;while((count=in.read(buffer))!=-1){if(out.size()+count>maximum)throw new IOException("fixture exceeds request bound");out.write(buffer,0,count);}return out.toString(StandardCharsets.UTF_8.name());}finally{connection.disconnect();}
      };
      AppUpdateInfo result=new AppUpdateInfo(AppUpdateCatalog.fetch("candidate",fetcher));
      check(result.candidateNumber==2&&requests.equals(Arrays.asList(AppUpdateCatalog.url(1),"https://github.com/"+AppUpdatePolicy.REPO+"/releases/download/v2.0.46-candidate2-gecko/release-manifest.json")),"Actual local HTTP discovery fetches only the selected candidate manifest");
      requests.clear();reject(()->AppUpdateCatalog.fetch("stable",fetcher),"Missing stable release never downloads beta or candidate manifests");
      check(requests.size()==1,"An empty channel stops after the discovery page");
      List<String> pages=new ArrayList<>();JSONObject full=release("2.0.47","beta",0);
      reject(()->AppUpdateCatalog.fetch("stable",(url,max)->{pages.add(url);JSONArray page=new JSONArray();for(int i=0;i<50;i++)page.put(full);return page.toString();}),"Bounded page scan returns no matching release without cross-channel fallback");
      check(pages.size()==AppUpdateCatalog.MAX_PAGES,"Discovery has a fixed maximum number of API requests");
    }finally{server.stop(0);}
  }
  public static void main(String[] args)throws Exception{
    policy();transport();
    if(args.length>0){JSONObject published=new JSONObject(Files.readString(Path.of(args[0])));AppUpdateInfo actual=new AppUpdateInfo(AppUpdateCatalog.feed(AppUpdateCatalog.release(release("2.0.46","candidate",2)),published));check(actual.code==99&&actual.candidateNumber==2,"The existing public candidate2 manifest passes the new update path");}
    System.out.println(new JSONObject().put("status","passed").put("passed",checks.length()).put("checks",checks).put("actualHttpExecution",true).put("actualAndroidExecution",false));
  }
}
