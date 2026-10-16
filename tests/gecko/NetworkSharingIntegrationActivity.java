package local.pocketchat;

import android.app.Activity;import android.content.*;import android.net.Uri;import android.os.Bundle;import android.widget.TextView;
import org.json.*;import java.io.*;import java.nio.charset.StandardCharsets;import java.util.*;

/** Synthetic Android/core/encrypted-store integration; never real user credentials. */
public final class NetworkSharingIntegrationActivity extends Activity {
  final JSONArray checks=new JSONArray();JSONObject buildIdentity;JSONObject entry,exit;JSONObject[] records=new JSONObject[2];byte[][] payloads=new byte[2][];NetworkCatalog catalog;String entryId,exitId;Context profile;SecretStore vault;byte[] before;Uri file;
  void check(String name,boolean passed){checks.put(J.obj("name",name,"pass",passed));if(!passed)throw new AssertionError(name);}
  interface Attempt{void run()throws Exception;}
  void rejects(String name,Attempt attempt)throws Exception{boolean rejected=false;try{attempt.run();}catch(Exception expected){rejected=true;}check(name,rejected);}
  @Override public void onCreate(Bundle state){super.onCreate(state);if(!"local.pocketchat.test".equals(getPackageName()))throw new SecurityException();TextView title=new TextView(this);title.setText("网络分享验证");setContentView(title);new Thread(()->{try{model();runOnUiThread(()->parse(0));}catch(Throwable e){fail(e);}}).start();}
  void model()throws Exception{
    buildIdentity=IntegrationBuildIdentity.read(this);
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
    rejects("YAML object tags rejected",()->NetworkShareCodec.extract("!!java.net.URL [https://example.invalid]".getBytes(StandardCharsets.UTF_8),"Entry|Sharing Entry",NetworkCatalog.ENTRY));
    file=NetworkShareProvider.create(this,valid);check("Share URI uses dedicated provider",file.getAuthority().equals(getPackageName()+".network-shares"));check("Share file roundtrip",NetworkShareCodec.decode(new String(java.nio.file.Files.readAllBytes(NetworkShareProvider.resolve(this,file).toPath()),StandardCharsets.UTF_8)).kind.equals("route"));
    rejects("Provider path traversal rejected",()->NetworkShareProvider.resolve(this,Uri.parse("content://"+getPackageName()+".network-shares/../network.sealed")));
    rejects("Provider wrong authority rejected",()->NetworkShareProvider.resolve(this,Uri.parse("content://other/"+file.getLastPathSegment())));
    catalog=new NetworkCatalog(this);
  }
  void parse(int i){if(i==2){new Thread(()->{try{imported();runOnUiThread(()->{try{ui();}catch(Throwable e){fail(e);}});}catch(Throwable e){fail(e);}}).start();return;}
    JSONObject node=i==0?entry:exit;byte[] raw=NetworkShareCodec.provider(node);NativeNetwork.previewSubscription(this,i==0?NetworkCatalog.ENTRY:NetworkCatalog.EXIT,"",raw,(ok,msg,names,details,bytes)->{try{check("Actual native parser accepts shared "+i,ok&&names.length()==1&&details.length()==1);records[i]=J.obj("name",node.optString("name"),"nodes",names,"nodeDetails",details);payloads[i]=raw;parse(i+1);}catch(Throwable e){fail(e);}});
  }
  void imported()throws Exception{
    JSONObject ids=catalog.importLocalSources(records[0],payloads[0],records[1],payloads[1]);entryId=ids.getString("entry");exitId=ids.getString("exit");NetworkCatalog restored=new NetworkCatalog(this);
    JSONObject e=restored.subscription("entry",entryId),x=restored.subscription("exit",exitId);check("Both local sources atomically readable",e!=null&&x!=null&&NetworkCatalog.local(e)&&NetworkCatalog.local(x));
    check("Local sources use no fabricated HTTP URL",e.getString("url").equals("pocketnet:"+entryId)&&x.getString("url").equals("pocketnet:"+exitId));
    check("Receiver does not inherit verification",!x.has("verifiedIp")&&!x.has("verifiedAt"));
    JSONObject twice=restored.importLocalSources(records[0],payloads[0],records[1],payloads[1]);check("Repeated import reuses exact source IDs",entryId.equals(twice.getString("entry"))&&exitId.equals(twice.getString("exit")));
    check("Library import preserves active network",Arrays.equals(before,vault.get("network")));check("Library import preserves chat draft",profile.getSharedPreferences("chat",0).getString("draft","").equals("sharing-preserved-draft"));
    NetworkDraft draft=new NetworkDraft(6,vault.settings(),restored);draft.subscription(entryId,restored);draft.mode="manual";draft.chooseEntry("Entry|Sharing Entry",restored);draft.exitSubscription(exitId,restored);draft.exitNode(NetworkSourceSelection.fingerprint(x,"Exit|Sharing Exit"),"Exit|Sharing Exit",restored);JSONObject candidate=draft.candidate(restored);
    check("Imported complete route produces validated candidate",entryId.equals(candidate.getString("entrySubscriptionId"))&&exitId.equals(candidate.getString("exitSubscriptionId")));
    NetworkSourceSelection.Sources sources=NetworkSourceSelection.resolve(restored,candidate);check("Resolve uses exact imported encrypted bytes",Arrays.equals(payloads[0],sources.entryBytes)&&Arrays.equals(payloads[1],sources.exitBytes));
    check("Candidate does not write live configuration",Arrays.equals(before,vault.get("network")));
    rejects("Local source cannot refresh remotely",()->restored.beginRefresh("entry",entryId));
    byte[] libraryBefore=restored.store.get("network-catalog");rejects("Partial bundle rejected before publication",()->restored.importLocalSources(records[0],"changed payload".getBytes(StandardCharsets.UTF_8),new JSONObject(),payloads[1]));check("Failed bundle leaves entire prior library",Arrays.equals(libraryBefore,restored.store.get("network-catalog")));
    byte[] sealed=java.nio.file.Files.readAllBytes(restored.store.file(e.getString("cacheSlot")).toPath());check("Credentials not stored as plaintext",!new String(sealed,StandardCharsets.ISO_8859_1).contains("synthetic"));
  }
  void ui()throws Exception{
    NetworkShareUi.show(this,new NetworkShareCodec.Bundle("Synthetic route",entry,exit));
    JSONObject result=J.obj("runToken",getIntent().getStringExtra("runToken"),"buildIdentity",buildIdentity,"status","passed","actualAndroidExecution",true,"actualNativeExecution",true,"physicalPhone",false,"checks",checks,"checkCount",checks.length(),"shareUri",file.toString(),"entryId",entryId,"exitId",exitId,"beforeNetworkHash",before==null?"":NetworkSourceSelection.payloadHash(before));
    J.write(new File(getFilesDir(),"network-source-sharing-results.json"),result.toString());
  }
  void fail(Throwable e){try{J.write(new File(getFilesDir(),"network-source-sharing-results.json"),J.obj("runToken",getIntent().getStringExtra("runToken"),"status","failed","error",e.getClass().getSimpleName(),"checks",checks).toString());}catch(Exception ignored){}android.util.Log.e("PocketSharing","Synthetic sharing check failed",e);}
}
