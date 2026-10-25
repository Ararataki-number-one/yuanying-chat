package local.pocketchat;

import android.app.Activity;import android.content.*;import android.net.Uri;import android.os.Bundle;import android.widget.*;
import org.json.*;import java.io.*;import java.nio.charset.StandardCharsets;import java.util.*;

/** Synthetic Android/core/encrypted-store integration; never real user credentials. */
public final class NetworkSharingIntegrationActivity extends Activity {
  final JSONArray schemaEvidence=new JSONArray();JSONArray schemaSamples;
  byte[] portableRaw;JSONObject portableEntry;String portableFingerprint;JSONArray portableDetails;
  JSONObject uiConfig,result;String portableSourceId;final Map<String,byte[]> shareSnapshot=new LinkedHashMap<>();
  final JSONArray checks=new JSONArray();JSONObject buildIdentity;JSONObject entry,exit;JSONObject[] records=new JSONObject[2];byte[][] payloads=new byte[2][];NetworkCatalog catalog;String entryId,exitId;Context profile;SecretStore vault;byte[] before;Uri file;NetworkOptimizationIntegrationActivity.HttpFixture site,plain;PreconnectIntegrationActivity.TraceSocks wireEntry,wireExit;
  void check(String name,boolean passed){checks.put(J.obj("name",name,"pass",passed));if(!passed)throw new AssertionError(name);}
  interface Attempt{void run()throws Exception;}
  void rejects(String name,Attempt attempt)throws Exception{boolean rejected=false;try{attempt.run();}catch(Exception expected){rejected=true;}check(name,rejected);}
  @Override public void onCreate(Bundle state){super.onCreate(state);if(!"local.pocketchat.test".equals(getPackageName()))throw new SecurityException();TextView title=new TextView(this);title.setText("网络分享验证");setContentView(title);new Thread(()->{try{model();runOnUiThread(this::portableOriginal);}catch(Throwable e){fail(e);}}).start();}
  void model()throws Exception{
    buildIdentity=IntegrationBuildIdentity.read(this);
    try(InputStream in=getAssets().open("sharing-schema-matrix.json")){schemaSamples=new JSONObject(new String(J.read(in,NetworkShareCodec.LIMIT),StandardCharsets.UTF_8)).getJSONArray("cases");}
    profile=Profiles.context(this,6);ProfileCatalog.get(this).created(6);ProfileCatalog.get(this).rename(6,"Sharing Window");vault=new SecretStore(profile);before=vault.get("network");profile.getSharedPreferences("chat",0).edit().putString("draft","sharing-preserved-draft").commit();
    entry=J.obj("name","Sharing Entry","type","socks5","server","127.0.0.1","port",19131,"username","synthetic","password","空 : @ / \\\n🔐");exit=J.obj("name","Sharing Exit","type","socks5","server","127.0.0.1","port",19132,"username","synthetic","password","");
    for(String kind:new String[]{"entry","exit","route"}){NetworkShareCodec.Bundle b=new NetworkShareCodec.Bundle("Synthetic",kind.equals("exit")?null:entry,kind.equals("entry")?null:exit);NetworkShareCodec.Bundle decoded=NetworkShareCodec.decode(b.encode());check(kind+" roundtrip role",kind.equals(decoded.kind));check(kind+" contains only selected connection data",!b.encode().contains("subscriptionUrl")&&!b.encode().contains("environmentId")&&!b.encode().contains("cookies"));}
    check("Unicode special password preserved",NetworkShareCodec.decode(new NetworkShareCodec.Bundle("Synthetic",entry,exit).encode()).entry.getString("password").equals(entry.getString("password")));
    JSONObject portBad=new JSONObject(exit.toString());portBad.put("port",65536);rejects("Reject invalid port",()->NetworkShareCodec.node(portBad,true));
    JSONObject script=new JSONObject(entry.toString());script.put("dialer-proxy","OTHER");rejects("Reject imported route override",()->NetworkShareCodec.node(script,false));
    JSONObject arbitrary=new JSONObject(entry.toString());arbitrary.put("certificate-path","/private/key");rejects("Reject external file parameter",()->NetworkShareCodec.node(arbitrary,false));
    String valid=new NetworkShareCodec.Bundle("Synthetic",entry,exit).encode();rejects("Reject future schema",()->NetworkShareCodec.decode(valid.replace("\"schemaVersion\":1","\"schemaVersion\":999")));
    rejects("Reject trailing payload",()->NetworkShareCodec.decode(valid+" {}"));rejects("Reject too large input",()->NetworkShareCodec.decode(new String(new char[NetworkShareCodec.LIMIT+1]).replace('\0',' ')));
    rejects("Reject deep input",()->NetworkShareCodec.decode("[[[[[[[[[[[[[[[[[[[[0]]]]]]]]]]]]]]]]]]]]"));
    JSONObject extra=new JSONObject(valid);extra.put("cookies","synthetic-private-marker");rejects("Reject unrelated identity payload",()->NetworkShareCodec.decode(extra.toString()));
    String yaml="proxies:\n  - name: Sharing Entry\n    type: vless\n    server: example.invalid\n    port: 443\n    uuid: 00000000-0000-4000-8000-000000000000\n    tls: true\n    network: ws\n    ws-opts:\n      path: /transport\n      headers:\n        Host: example.invalid\n  - name: Hidden Other\n    type: socks5\n    server: other.invalid\n    port: 1080\n    password: never-export-this\n";
    JSONObject extracted=NetworkShareCodec.extract(yaml.getBytes(StandardCharsets.UTF_8),"Entry|Sharing Entry",NetworkCatalog.ENTRY);check("YAML export preserves nested transport",extracted.getJSONObject("ws-opts").getString("path").equals("/transport"));check("YAML exports no unrelated node",!extracted.toString().contains("never-export-this"));
    rejects("YAML recursive aliases rejected",()->NetworkShareCodec.extract("proxies: [{name: Sharing Entry, type: socks5, server: localhost, port: 1080, ws-opts: &loop {headers: *loop}}]".getBytes(StandardCharsets.UTF_8),"Entry|Sharing Entry",NetworkCatalog.ENTRY));
    rejects("YAML object tags rejected",()->NetworkShareCodec.extract("!!java.net.URL [https://example.invalid]".getBytes(StandardCharsets.UTF_8),"Entry|Sharing Entry",NetworkCatalog.ENTRY));
    NativeProbeIntegrationActivity.TlsFixture tls=new NativeProbeIntegrationActivity.TlsFixture(this,"network-fixture.p12");site=new NetworkOptimizationIntegrationActivity.HttpFixture(tls.context);plain=new NetworkOptimizationIntegrationActivity.HttpFixture(null);site.start();plain.start();
    wireExit=new PreconnectIntegrationActivity.TraceSocks("shared-exit",0,site.port(),plain.port());wireEntry=new PreconnectIntegrationActivity.TraceSocks("shared-entry",0,wireExit.port());wireExit.start();wireEntry.start();
    entry.put("port",wireEntry.port());exit.put("port",wireExit.port());for(JSONObject n:new JSONObject[]{entry,exit}){n.put("username",PreconnectIntegrationActivity.USER);n.put("password",PreconnectIntegrationActivity.PASSWORD);}
    file=NetworkShareProvider.create(this,new NetworkShareCodec.Bundle("Synthetic route",entry,exit).encode());check("Share URI uses dedicated provider",file.getAuthority().equals(getPackageName()+".network-shares"));check("Share file roundtrip",NetworkShareCodec.decode(new String(java.nio.file.Files.readAllBytes(NetworkShareProvider.resolve(this,file).toPath()),StandardCharsets.UTF_8)).kind.equals("route"));
    rejects("Provider path traversal rejected",()->NetworkShareProvider.resolve(this,Uri.parse("content://"+getPackageName()+".network-shares/../network.sealed")));
    rejects("Provider wrong authority rejected",()->NetworkShareProvider.resolve(this,Uri.parse("content://other/"+file.getLastPathSegment())));
    catalog=new NetworkCatalog(this);
    try(InputStream in=getAssets().open("sharing-vless.yaml")){portableRaw=completeProvider(J.read(in,NetworkShareCodec.LIMIT));}
    portableEntry=NetworkShareCodec.extract(portableRaw,"Entry|Portable VLESS",NetworkCatalog.ENTRY);
    check("VLESS encryption XUDP and mux exported without omission",portableEntry.getString("encryption").equals("none")&&portableEntry.getBoolean("xudp")&&portableEntry.getJSONObject("smux").getInt("max-streams")==16);
    check("Complete provider exports only the selected node",!portableEntry.toString().contains("never-export")&&!portableEntry.toString().contains("unrelated"));
  }
  /** Real providers commonly contain shared UI/group metadata beyond their proxies. */
  static byte[] completeProvider(byte[] raw)throws Exception{
    String provider=new String(raw,StandardCharsets.UTF_8);
    if(provider.trim().startsWith("{"))provider="proxies: "+NetworkShareCodec.yamlJson(new JSONObject(provider).getJSONArray("proxies").toString())+"\n";
    StringBuilder full=new StringBuilder(provider).append("\nsharing-labels: &sharing-labels {label: never-export-unrelated}\nsharing-groups:\n");
    for(int i=0;i<100;i++)full.append("  - *sharing-labels\n");
    full.append("sharing-metadata: {label: first, label: second}\nsharing-tagged: !unused [never-export-unrelated]\nsharing-deep: ");
    for(int i=0;i<14;i++)full.append("[");
    full.append("never-export-unrelated");
    for(int i=0;i<14;i++)full.append("]");
    full.append("\n---\nproxies: [{name: never-export-second-document, type: socks5, server: hidden.invalid, port: 1080}]\n");
    return full.toString().getBytes(StandardCharsets.UTF_8);
  }
  void portableOriginal(){NativeNetwork.previewSubscription(this,NetworkCatalog.ENTRY,"",portableRaw,(ok,msg,names,details,bytes)->{try{
    check("Actual core accepts original VLESS subscription with transport options",ok&&details.length()==2);
    portableDetails=details;
    check("Android core accepts complete provider with 100 aliases and unrelated metadata",ok&&Arrays.equals(bytes,portableRaw));
    for(int i=0;i<details.length();i++)if("Entry|Portable VLESS".equals(details.getJSONObject(i).optString("name")))portableFingerprint=details.getJSONObject(i).getString("configFingerprint");
    check("Original VLESS has stable native identity",portableFingerprint!=null&&portableFingerprint.matches("[0-9a-f]{64}"));
    NetworkShareCodec.Bundle decoded=NetworkShareCodec.decode(new NetworkShareCodec.Bundle("Portable route",portableEntry,exit).encode());
    NativeNetwork.previewSubscription(this,NetworkCatalog.ENTRY,"",NetworkShareCodec.provider(decoded.entry),(accepted,message,sharedNames,sharedDetails,sharedBytes)->{try{
      check("Exported VLESS reparses as exactly one node",accepted&&sharedDetails.length()==1);
      check("Export and import preserve actual native VLESS fingerprint",portableFingerprint.equals(sharedDetails.getJSONObject(0).optString("configFingerprint")));
      schemaMatrix(0);
    }catch(Throwable e){fail(e);}});
  }catch(Throwable e){fail(e);}});}
  void schemaMatrix(int index){
    if(index==schemaSamples.length()){parse(0);return;}
    try{JSONObject sample=schemaSamples.getJSONObject(index);String id=sample.getString("id");byte[] raw=sample.getString("source").getBytes(StandardCharsets.UTF_8);
      NativeNetwork.previewSubscription(this,NetworkCatalog.ENTRY,"",raw,(ok,message,names,details,bytes)->{try{
        check("Native original schema accepted: "+id,ok&&details.length()==1);String expected=details.getJSONObject(0).getString("configFingerprint");
        byte[] activeBefore=vault.get("network"),entryBefore=vault.get("subscription"),exitBefore=vault.get("exit-subscription");
        JSONObject item=J.obj("name","Schema "+id,"nodes",names,"nodeDetails",details);NetworkCatalog sourceCatalog=new NetworkCatalog(this);
        String sourceId=sourceCatalog.importLocalSources(item,raw,null,null).getString(NetworkCatalog.ENTRY);JSONObject candidate;
        try{NetworkCatalog restored=new NetworkCatalog(this);JSONObject source=restored.subscription(NetworkCatalog.ENTRY,sourceId);
          candidate=restored.shareCandidate(source,restored.cache(source),"Entry|Selected",expected);
          check("Parser-worker candidate binds original native identity: "+id,candidate!=null&&!source.getJSONArray("nodeDetails").toString().contains("shareCandidate"));
          check("Schema candidate uses encrypted sidecar: "+id,!source.optString("shareCacheSlot").isEmpty()&&candidate!=null);
        }finally{new NetworkCatalog(this).deleteSubscription(NetworkCatalog.ENTRY,sourceId);}
        check("Schema import and cleanup preserve active snapshot: "+id,Arrays.equals(activeBefore,vault.get("network"))&&Arrays.equals(entryBefore,vault.get("subscription"))&&Arrays.equals(exitBefore,vault.get("exit-subscription")));
        JSONObject exported=NetworkShareCodec.decode(new NetworkShareCodec.Bundle(id,NetworkShareCodec.node(candidate,false),null).encode()).entry;byte[] provider=NetworkShareCodec.provider(exported);
        NativeNetwork.previewSubscription(this,NetworkCatalog.ENTRY,"",provider,(accepted,reason,exportNames,exportDetails,exportBytes)->{try{
          check("Native exported schema accepted: "+id,accepted&&exportDetails.length()==1);String actual=exportDetails.getJSONObject(0).getString("configFingerprint");
          check("Native fingerprint preserved for schema: "+id,expected.equals(actual));
          schemaEvidence.put(J.obj("case",id,"sourceHash",NetworkShareSnapshot.hash(raw),"exportHash",NetworkShareSnapshot.hash(provider),"originalFingerprint",expected,"exportFingerprint",actual,"actualNativeFingerprintVerified",true,"actualEncryptedCatalogCandidate",true,"activeSnapshotPreserved",true,"temporarySourceDeleted",true));schemaMatrix(index+1);
        }catch(Throwable error){fail(error);}});
      }catch(Throwable error){fail(error);}});
    }catch(Throwable error){fail(error);}
  }
  void parse(int i){if(i==2){new Thread(()->{try{imported();runOnUiThread(()->{try{ui();}catch(Throwable e){fail(e);}});}catch(Throwable e){fail(e);}}).start();return;}
    JSONObject node=i==0?entry:exit;byte[] raw;
    try{raw=completeProvider(NetworkShareCodec.provider(node));}catch(Exception e){fail(e);return;}
    NativeNetwork.previewSubscription(this,i==0?NetworkCatalog.ENTRY:NetworkCatalog.EXIT,"",raw,(ok,msg,names,details,bytes)->{try{check("Actual native parser accepts shared "+i,ok&&names.length()==1&&details.length()==1);check("Complete provider extraction preserves node "+i,NetworkShareCodec.extract(raw,(i==0?"Entry|":"Exit|")+node.getString("name"),i==0?NetworkCatalog.ENTRY:NetworkCatalog.EXIT).getString("password").equals(node.getString("password")));records[i]=J.obj("name",node.optString("name"),"nodes",names,"nodeDetails",details);payloads[i]=raw;parse(i+1);}catch(Throwable e){fail(e);}});
  }
  void imported()throws Exception{
    JSONObject ids=catalog.importLocalSources(records[0],payloads[0],records[1],payloads[1]);entryId=ids.getString("entry");exitId=ids.getString("exit");NetworkCatalog restored=new NetworkCatalog(this);
    JSONObject e=restored.subscription("entry",entryId),x=restored.subscription("exit",exitId);check("Both local sources atomically readable",e!=null&&x!=null&&NetworkCatalog.local(e)&&NetworkCatalog.local(x));
    check("Local sources use no fabricated HTTP URL",e.getString("url").equals("pocketnet:"+entryId)&&x.getString("url").equals("pocketnet:"+exitId));
    check("Receiver does not inherit verification",!x.has("verifiedIp")&&!x.has("verifiedAt"));
    check("Imported native candidates survive encrypted library storage",restored.shareCandidate(e,payloads[0],"Entry|Sharing Entry",NetworkSourceSelection.fingerprint(e,"Entry|Sharing Entry"))!=null&&restored.shareCandidate(x,payloads[1],"Exit|Sharing Exit",NetworkSourceSelection.fingerprint(x,"Exit|Sharing Exit"))!=null);
    check("Imported public metadata excludes private candidates",!e.optJSONArray("nodeDetails").toString().contains("shareCandidate")&&!x.optJSONArray("nodeDetails").toString().contains("shareCandidate"));
    JSONObject twice=restored.importLocalSources(records[0],payloads[0],records[1],payloads[1]);check("Repeated import reuses exact source IDs",entryId.equals(twice.getString("entry"))&&exitId.equals(twice.getString("exit")));
    check("Library import preserves active network",Arrays.equals(before,vault.get("network")));check("Library import preserves chat draft",profile.getSharedPreferences("chat",0).getString("draft","").equals("sharing-preserved-draft"));
    NetworkDraft draft=new NetworkDraft(6,vault.settings(),restored);draft.subscription(entryId,restored);draft.mode="manual";draft.chooseEntry("Entry|Sharing Entry",restored);draft.exitSubscription(exitId,restored);draft.exitNode(NetworkSourceSelection.fingerprint(x,"Exit|Sharing Exit"),"Exit|Sharing Exit",restored);JSONObject candidate=draft.candidate(restored);
    check("Imported complete route produces validated candidate",entryId.equals(candidate.getString("entrySubscriptionId"))&&exitId.equals(candidate.getString("exitSubscriptionId")));
    NetworkSourceSelection.Sources sources=NetworkSourceSelection.resolve(restored,candidate);check("Resolve uses exact imported encrypted bytes",Arrays.equals(payloads[0],sources.entryBytes)&&Arrays.equals(payloads[1],sources.exitBytes));
    check("Candidate does not write live configuration",Arrays.equals(before,vault.get("network")));
    proveLocalRoute(sources,candidate);
    rejects("Local source cannot refresh remotely",()->restored.beginRefresh("entry",entryId));
    byte[] libraryBefore=restored.store.get("network-catalog");rejects("Partial bundle rejected before publication",()->restored.importLocalSources(records[0],"changed payload".getBytes(StandardCharsets.UTF_8),new JSONObject(),payloads[1]));check("Failed bundle leaves entire prior library",Arrays.equals(libraryBefore,restored.store.get("network-catalog")));
    byte[] sealed=java.nio.file.Files.readAllBytes(restored.store.file(e.getString("cacheSlot")).toPath());check("Credentials not stored as plaintext",!new String(sealed,StandardCharsets.ISO_8859_1).contains("synthetic"));
  }
  void proveLocalRoute(NetworkSourceSelection.Sources sources,JSONObject candidate)throws Exception{
    Context scratch=Profiles.context(this,5);SecretStore store=new SecretStore(scratch);Map<String,byte[]> saved=new LinkedHashMap<>();for(String key:NetworkSourceSelection.ActiveSnapshot.RECORDS)saved.put(key,store.get(key));
    NativeNetwork network=new NativeNetwork(scratch,new File(scratch.getNoBackupFilesDir(),"sharing-route-fixture"),false){
      @Override String exitCheckUrl(){return site.url("/ip");}
      @Override String probeUrl(){return plain.url("/probe");}
      @Override String websiteUrl(){return site.url("/website");}
      @Override java.net.HttpURLConnection openProbeConnection(String url,int port)throws IOException{java.net.HttpURLConnection c=super.openProbeConnection(url,port);if(c instanceof javax.net.ssl.HttpsURLConnection){if(!url.startsWith(site.url("/")))throw new IOException("Controlled detector only");((javax.net.ssl.HttpsURLConnection)c).setSSLSocketFactory(site.tls.getSocketFactory());}return c;}
    };
    try{
      new NetworkSourceSelection.ActiveSnapshot(store).write(sources,candidate);network.startNow();
      check("Local sharing source starts through production core",network.ready&&network.startupCached&&network.currentEntry.equals("Entry|Sharing Entry"));
      check("Receiver verifies exit over the imported authenticated chain",wireEntry.contacts(wireExit.port())>0&&wireExit.contacts(site.port())>0&&network.verifiedRoute!=null);
      JSONObject config=J.parse(new String(java.nio.file.Files.readAllBytes(new File(network.root,"config.json").toPath()),StandardCharsets.UTF_8));
      JSONObject providers=config.getJSONObject("proxy-providers");check("Local sources cannot become HTTP subscription downloads","file".equals(providers.getJSONObject("Subscription").getString("type"))&&"file".equals(providers.getJSONObject("ExitSource").getString("type")));
      check("No sharing test traffic leaves loopback",wireEntry.denied.get()==0&&wireExit.denied.get()==0);
    }finally{network.stopNow();network.worker.shutdownNow();network.probes.shutdownNow();network.closers.shutdownNow();network.traffic.reader.shutdownNow();for(Map.Entry<String,byte[]> row:saved.entrySet())NetworkSourceSelection.restore(store,row.getKey(),row.getValue());for(AutoCloseable f:new AutoCloseable[]{site,plain,wireEntry,wireExit})if(f!=null)f.close();}
  }
  void ui()throws Exception{
    file=NetworkShareProvider.create(this,new NetworkShareCodec.Bundle("Portable route",portableEntry,exit).encode());
    JSONArray portableNames=new JSONArray();for(int i=0;i<portableDetails.length();i++)portableNames.put(portableDetails.getJSONObject(i).getString("name"));
    portableSourceId=catalog.addSubscription("entry","Complete provider","https://sharing.example.invalid/provider").getString("id");
    catalog.parsed(catalog.beginRefresh("entry",portableSourceId),portableNames,portableDetails,portableRaw,System.currentTimeMillis());
    LinearLayout controls=new LinearLayout(this);controls.setOrientation(LinearLayout.VERTICAL);setContentView(controls);
    action(controls,"测试订阅整条线路",()->{
      unchanged("Manual route sharing preserves the active snapshot");
      uiConfig.put("exitSource","subscription");uiConfig.put("exitSubscriptionId",exitId);uiConfig.put("exitSubscriptionUrl","pocketnet:"+exitId);uiConfig.put("exitNodeName","Exit|Sharing Exit");uiConfig.put("exitNodeKey",records[1].getJSONArray("nodeDetails").getJSONObject(0).getString("configFingerprint"));
      NetworkSourceSelection.withActiveSnapshot(vault.context,()->{vault.put("exit-subscription",payloads[1]);vault.save(uiConfig);return null;});rememberSnapshot();openRoute();
    });
    action(controls,"测试入口分享",()->NetworkShareUi.node(this,new NetworkCatalog(this).subscription("entry",portableSourceId),"Entry|Portable VLESS"));
    action(controls,"测试出口分享",()->NetworkShareUi.node(this,new NetworkCatalog(this).subscription("exit",exitId),"Exit|Sharing Exit"));
    action(controls,"测试固定出口分享",()->NetworkShareUi.manual(this,J.obj("name",exit.getString("name"),"host",exit.getString("server"),"port",exit.getInt("port"),"user",exit.getString("username"),"password",exit.getString("password"))));
    action(controls,"测试入口失败后仅分享出口",()->{NetworkSourceSelection.withActiveSnapshot(vault.context,()->{vault.put("subscription","unsupported synthetic source".getBytes(StandardCharsets.UTF_8));return null;});rememberSnapshot();openRoute();});
    action(controls,"恢复分享测试线路",()->{unchanged("Failed entry sharing preserves its captured snapshot");NetworkSourceSelection.withActiveSnapshot(vault.context,()->{vault.put("subscription",portableRaw);return null;});rememberSnapshot();result.put("partialSharePreservesActiveSnapshot",true);saveResult();});
    action(controls,"检查分享未改动线路",()->{unchanged("Subscribed route and individual shares preserve the active snapshot");check("All sharing paths preserve the existing draft","sharing-preserved-draft".equals(profile.getSharedPreferences("chat",0).getString("draft","")));result.put("sharePreparationPreservesActiveSnapshot",true);saveResult();});
    // Exercise the production active-snapshot extraction and fingerprint guard,
    // rather than opening the already prepared dialog directly.
    uiConfig=J.obj("subscriptionUrl","pocketnet:sharing-fixture","entry","Entry|Portable VLESS","entryMode","manual","entryNodeKey",portableFingerprint,"exitName",exit.getString("name"),"exitHost",exit.getString("server"),"exitPort",exit.getInt("port"),"exitUser",exit.getString("username"),"exitPassword",exit.getString("password"));
    NetworkSourceSelection.withActiveSnapshot(vault.context,()->{vault.put("subscription",portableRaw);vault.save(uiConfig);return null;});rememberSnapshot();openRoute();
    result=J.obj("runToken",getIntent().getStringExtra("runToken"),"buildIdentity",buildIdentity,"status","passed","actualAndroidExecution",true,"actualNativeExecution",true,"physicalPhone",false,"schemaFingerprintEvidence",schemaEvidence,"schemaFingerprintCount",schemaEvidence.length(),"checks",checks,"checkCount",checks.length(),"shareUri",file.toString(),"entryId",entryId,"exitId",exitId,"beforeNetworkHash",before==null?"":NetworkSourceSelection.payloadHash(before));
    saveResult();
  }
  void action(LinearLayout controls,String title,Attempt action){Button button=new Button(this);button.setText(title);button.setOnClickListener(v->{try{action.run();}catch(Throwable e){fail(e);}});controls.addView(button);}
  void rememberSnapshot()throws Exception{shareSnapshot.clear();for(String key:NetworkSourceSelection.ActiveSnapshot.RECORDS)shareSnapshot.put(key,vault.get(key));}
  void unchanged(String name)throws Exception{for(Map.Entry<String,byte[]> saved:shareSnapshot.entrySet())check(name+" "+saved.getKey(),Arrays.equals(saved.getValue(),vault.get(saved.getKey())));}
  void openRoute(){
    long now=System.currentTimeMillis();JSONObject row=ProfileCatalog.get(this).item(6);
    JSONObject runtime=J.obj("environmentId",row.opt("environmentId"),"generation",row.opt("generation"),"mode","internal","configured",true,"connected",true,"at",now,"subscriptionId",NativeNetwork.hash(uiConfig.optString("subscriptionUrl")),"entry","Entry|Portable VLESS");
    NetworkShareUi.route(this,new WindowNetworkState(this,row,uiConfig,runtime,true,now));
  }
  void saveResult()throws Exception{result.put("checkCount",checks.length());J.write(new File(getFilesDir(),"network-source-sharing-results.json"),result.toString());}
  void fail(Throwable e){try{J.write(new File(getFilesDir(),"network-source-sharing-results.json"),J.obj("runToken",getIntent().getStringExtra("runToken"),"status","failed","error",e.getClass().getSimpleName(),"checks",checks).toString());}catch(Exception ignored){}android.util.Log.e("PocketSharing","Synthetic sharing check failed",e);}
}
