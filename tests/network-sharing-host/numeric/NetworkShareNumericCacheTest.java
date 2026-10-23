package local.pocketchat;
import android.content.Context;import org.json.*;import java.nio.charset.StandardCharsets;import java.nio.file.*;import java.util.*;
/** Exact production codec/catalogue/cache chain, explicit unencrypted host store
 * and synthetic fingerprint metadata. Actual native fingerprint is Android-only. */
public final class NetworkShareNumericCacheTest {
 static final String FP="d".repeat(64);static final JSONArray checks=new JSONArray();
 static void check(String name,boolean pass){checks.put(J.obj("name",name,"pass",pass));if(!pass)throw new AssertionError(name);}
 static byte[] bytes(String text){return text.getBytes(StandardCharsets.UTF_8);}
 static JSONArray names(){return J.arr("Entry|Selected");}
 static JSONArray metadata(){return J.arr(J.obj("name","Entry|Selected","type","Synthetic","configFingerprint",FP,"configFingerprintVersion",1));}
 static String yaml(String field,String scalar){return "proxies: [{name: Selected, type: "+(field.equals("password")?"socks5":"hysteria2")+", server: 127.0.0.1, port: 443, "+(field.equals("password")?"username: synthetic, ":"password: synthetic, ")+field+": "+scalar+"}]\n";}
 static void exact(JSONObject node,String field,String expected,boolean string)throws Exception{Object value=node.get(field);check(field+" exact "+expected,expected.equals(value.toString())&&(!string||value instanceof String));}
 static void roundtrip(Context context,String id,String field,String scalar,String expected,boolean string)throws Exception{
  byte[] raw=bytes(yaml(field,scalar));JSONArray ready=NetworkShareCodec.candidates(raw,NetworkCatalog.ENTRY,metadata());NetworkCatalog catalog=new NetworkCatalog(context);
  String sourceId=catalog.addSubscription(NetworkCatalog.ENTRY,id,"https://fixture.invalid/"+id).getString("id");catalog.parsed(catalog.beginRefresh(NetworkCatalog.ENTRY,sourceId),names(),ready,raw,1);
  NetworkCatalog restored=new NetworkCatalog(context);JSONObject row=restored.subscription(NetworkCatalog.ENTRY,sourceId),cached=restored.shareCandidate(row,restored.cache(row),"Entry|Selected",FP);
  check(id+" candidate persisted through real catalog parsed",cached!=null&&!row.optString("shareCacheSlot").isEmpty());exact(cached,field,expected,string);
  JSONObject decoded=NetworkShareCodec.decode(new NetworkShareCodec.Bundle(id,NetworkShareCodec.node(cached,false),null).encode()).entry;exact(NetworkShareCodec.extract(NetworkShareCodec.provider(decoded),"Entry|Selected",NetworkCatalog.ENTRY),field,expected,string);
  check(id+" private candidate excluded from public metadata",!row.getJSONArray("nodeDetails").toString().contains("shareCandidate")&&!row.getJSONArray("nodeDetails").toString().contains(field));
  JSONObject item=J.obj("name",id,"nodes",names(),"nodeDetails",ready);String imported=catalog.importLocalSources(item,raw,null,null).getString(NetworkCatalog.ENTRY);restored=new NetworkCatalog(context);row=restored.subscription(NetworkCatalog.ENTRY,imported);exact(restored.shareCandidate(row,restored.cache(row),"Entry|Selected",FP),field,expected,string);
  SecretStore.failSidecarOnce=true;catalog.parsed(catalog.beginRefresh(NetworkCatalog.ENTRY,sourceId),names(),ready,raw,2);restored=new NetworkCatalog(context);row=restored.subscription(NetworkCatalog.ENTRY,sourceId);check(id+" optional cache write failure preserves usable source",row.optString("shareCacheSlot").isEmpty()&&restored.shareCandidate(row,restored.cache(row),"Entry|Selected",FP)==null);exact(NetworkShareCodec.extract(restored.cache(row),"Entry|Selected",NetworkCatalog.ENTRY),field,expected,string);
 }
 public static void main(String[] args)throws Exception{
  Context context=new Context(Files.createTempDirectory("share-numeric-cache-").toFile(),0);SecretStore active=new SecretStore(Profiles.context(context,3));active.put("network",bytes("synthetic-active-network"));active.put("subscription",bytes("synthetic-active-provider"));
  String[][] floats={{"0.25","2.5E-01"},{"1e23","1E+23"},{"-1e23","-1E+23"},{"4.9406564584124654e-324","5E-324"},{"-0.0","-0E+00"},{"1.7976931348623157e308","1.7976931348623157E+308"},{"2.2250738585072014e-308","2.2250738585072014E-308"},{"2.225073858507201e-308","2.225073858507201E-308"},{"1.0000000000000002","1.0000000000000002E+00"},{"1e-7","1E-07"},{"1000000.0","1E+06"}};
  String[][] binades={{"7.120236347223045e-307","7.120236347223045E-307"},{"-7.120236347223045e-307","-7.120236347223045E-307"},{"6.256509672447191e-148","6.256509672447191E-148"},{"6.518515124270356e91","6.518515124270356E+91"},{"6.386688990511104e293","6.386688990511104E+293"}};
  for(int i=0;i<binades.length;i++)roundtrip(context,"binade-"+i,"password",binades[i][0],binades[i][1],true);
  for(int i=0;i<floats.length;i++)roundtrip(context,"float-"+i,"password",floats[i][0],floats[i][1],true);
  String[] unsigned={"0","1","9007199254740993","9223372036854775807","9223372036854775808","9223372036854775809","18446744073709551615"};
  for(int i=0;i<unsigned.length;i++)roundtrip(context,"unsigned-"+i,"initial-stream-receive-window",unsigned[i],unsigned[i],i>=4);
  roundtrip(context,"unsigned-binary-float","initial-stream-receive-window","9.223372036854776e18","9223372036854775808",true);
  for(String value:new String[]{"'-1'","'18446744073709551616'","18446744073709551616",".inf",".nan"}){boolean rejected=false;try{NetworkShareCodec.extract(bytes(yaml("initial-stream-receive-window",value)),"Entry|Selected",NetworkCatalog.ENTRY);}catch(NetworkShareCodec.Failure expected){rejected=true;}check("Invalid uint64 rejected: "+value,rejected);}
  for(String value:new String[]{".inf","-.inf",".nan"}){boolean rejected=false;try{NetworkShareCodec.extract(bytes(yaml("password",value)),"Entry|Selected",NetworkCatalog.ENTRY);}catch(NetworkShareCodec.Failure expected){rejected=true;}check("Nonfinite credential rejected: "+value,rejected);}
  JSONObject plugin=NetworkShareCodec.extract(bytes("proxies: [{name: Selected, type: ss, server: 127.0.0.1, port: 443, password: synthetic, cipher: aes-128-gcm, plugin: v2ray-plugin, plugin-opts: {mode: websocket, Host: 123, mux: 1}}]"),"Entry|Selected",NetworkCatalog.ENTRY).getJSONObject("plugin-opts");check("Raw plugin numeric values are not stringified",plugin.get("Host") instanceof Number&&plugin.get("mux") instanceof Number);
  check("Numeric cache operations preserve active environment bytes",Arrays.equals(active.get("network"),bytes("synthetic-active-network"))&&Arrays.equals(active.get("subscription"),bytes("synthetic-active-provider")));
  JSONObject result=J.obj("passed",checks.length(),"total",checks.length(),"checks",checks,"actualAndroidExecution",false,"actualNativeFingerprint",false,"actualEncryption",false,"productionCatalogCandidateChain",true,"scope","Production candidates, NetworkCatalog.parsed/importLocalSources/shareCandidate, Snapshot and Bundle/provider roundtrips. Synthetic native identity; host atomic file storage adapter, not Android keystore or native fingerprint proof.");Files.writeString(Paths.get(args[0]),result.toString(2));System.out.println("Network share numeric cache: "+checks.length()+" checks passed");
 }
}
