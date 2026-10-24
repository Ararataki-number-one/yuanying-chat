package local.pocketchat;
import org.json.*;import java.math.*;import java.nio.file.*;import java.nio.charset.StandardCharsets;
/** The production sharing JSON boundary, with both Android and desktop org.json. */
public final class NetworkShareJsonTest {
  static final JSONArray checks=new JSONArray();
  static void check(String name,boolean pass){checks.put(J.obj("name",name,"pass",pass));if(!pass)throw new AssertionError(name);}
  interface Attempt{void run()throws Exception;}
  static void rejects(String name,Attempt run)throws Exception{boolean failed=false;try{run.run();}catch(Exception expected){failed=true;}check(name,failed);}
  public static void main(String[] args)throws Exception{
    for(String number:new String[]{"-9223372036854775808","9223372036854775807","9223372036854775808","18446744073709551615"}){
      JSONObject object=J.obj("number",new BigInteger(number));JSONObject copied=(JSONObject)NetworkShareJson.copy(object),decoded=(JSONObject)NetworkShareJson.decode(NetworkShareJson.encode(object,1024),1024);
      check("Exact integer copy and wire roundtrip: "+number,copied.get("number").toString().equals(number)&&decoded.get("number").toString().equals(number)&&NetworkShareSchema.integral(decoded.get("number")));
    }
    for(double number:new double[]{0.0,-0.0,1.0,-1.0,0.25,1e23,Double.MIN_VALUE,Double.MIN_NORMAL,Double.MAX_VALUE}){
      JSONObject object=J.obj("number",number);JSONObject decoded=(JSONObject)NetworkShareJson.decode(NetworkShareJson.encode(object,1024),1024);Object raw=decoded.get("number");
      check("Floating scalar kind and bits roundtrip: "+Double.toHexString(number),raw instanceof Double&&Double.doubleToRawLongBits((Double)raw)==Double.doubleToRawLongBits(number));
    }
    String escaped="synthetic \\ / \" \n\t\r\b\f 空 🔐";JSONObject object=J.obj("quoted \" key",J.arr(escaped,JSONObject.NULL,true));JSONObject decoded=(JSONObject)NetworkShareJson.decode(NetworkShareJson.encode(object,1024),1024);
    check("Escaped credentials keys and null retain exact values",decoded.getJSONArray("quoted \" key").getString(0).equals(escaped)&&decoded.getJSONArray("quoted \" key").isNull(1)&&decoded.getJSONArray("quoted \" key").getBoolean(2));
    JSONObject copied=(JSONObject)NetworkShareJson.copy(object);copied.getJSONArray("quoted \" key").put(0,"changed");check("Recursive copy is detached",object.getJSONArray("quoted \" key").getString(0).equals(escaped));
    String[] invalid={"","01","+1","0x1","1.",".5","NaN","Infinity","1e309","{\"a\":1,\"a\":2}","{\"a\":1,}","[1,]","{a:1}","'text'","true false","/*comment*/1","\"bad\\x20\"","\"bad\nline\"","\"\\uZZZZ\"","[".repeat(13)+"0"+"]".repeat(13),"1".repeat(1025)};
    for(int i=0;i<invalid.length;i++){String input=invalid[i];rejects("Reject malformed or unbounded JSON case "+i,()->NetworkShareJson.decode(input,4096));}
    check("Exact maximum JSON depth is supported",NetworkShareJson.decode("[".repeat(12)+"0"+"]".repeat(12),4096) instanceof JSONArray);
    rejects("UTF8 decode limit counts bytes",()->NetworkShareJson.decode("\"空空\"",7));rejects("UTF8 encode limit counts bytes",()->NetworkShareJson.encode("空空",7));
    rejects("Nonfinite values cannot be encoded",()->NetworkShareJson.encode(J.arr(Double.NaN),1024));JSONObject cycle=new JSONObject();cycle.put("cycle",cycle);rejects("Cyclic memory object cannot be encoded",()->NetworkShareJson.encode(cycle,4096));rejects("Cyclic memory object cannot be copied",()->NetworkShareJson.copy(cycle));
    check("Ordinary nested numeric values keep legacy wire support",!NetworkShareJson.requiresExactNumbers(J.obj("port",443,"ratio",0.25,"hugeDouble",1e23,"boundary",Long.MAX_VALUE)));
    for(Object value:new Object[]{new BigInteger("9223372036854775808"),new BigInteger("18446744073709551615"),0.0,-0.0,1.0,Math.scalb(1.0,63)})check("Legacy-lossy number requires new wire: "+value,NetworkShareJson.requiresExactNumbers(J.arr(J.obj("raw",value))));
    JSONObject plugin=NetworkShareCodec.extract("proxies: [{name: Selected, type: ss, server: 127.0.0.1, port: 443, cipher: aes-128-gcm, password: synthetic, plugin: v2ray-plugin, plugin-opts: {mode: websocket, host: 18446744073709551615}}]".getBytes(StandardCharsets.UTF_8),"Entry|Selected",NetworkCatalog.ENTRY);NetworkShareCodec.Bundle precise=new NetworkShareCodec.Bundle("Synthetic",plugin,null);String wire=precise.encode();
    check("Unsafe plugin numbers advertise schema 2",precise.schemaVersion()==2&&((JSONObject)NetworkShareJson.decode(wire,NetworkShareCodec.LIMIT)).getInt("schemaVersion")==2);
    check("New receiver still reads exact legacy schema 1 data",NetworkShareCodec.decode(wire.replace("\"schemaVersion\":2","\"schemaVersion\":1")).entry.getJSONObject("plugin-opts").get("host").toString().equals("18446744073709551615"));
    rejects("Unknown future wire remains rejected",()->NetworkShareCodec.decode(wire.replace("\"schemaVersion\":2","\"schemaVersion\":3")));
    rejects("Prior production receiver rejects unsafe schema 2 before import",()->LegacyShareReceiver.decode(wire));
    JSONObject ordinary=NetworkShareCodec.node(J.obj("name","Ordinary","type","socks5","server","127.0.0.1","port",1080,"password","synthetic"),false);NetworkShareCodec.Bundle compatible=new NetworkShareCodec.Bundle("Ordinary",ordinary,null);
    check("Ordinary schema 1 remains readable by prior production receiver",compatible.schemaVersion()==1&&LegacyShareReceiver.decode(compatible.encode()).entry.getString("password").equals("synthetic"));
    JSONObject fractional=(JSONObject)NetworkShareJson.copy(plugin);fractional.getJSONObject("plugin-opts").put("host",0.25);NetworkShareCodec.Bundle compatibleFloat=new NetworkShareCodec.Bundle("Fractional",fractional,null);
    check("Safe fractional plugin number keeps schema 1 receiver compatibility",compatibleFloat.schemaVersion()==1&&LegacyShareReceiver.decode(compatibleFloat.encode()).entry.getJSONObject("plugin-opts").get("host").toString().equals("0.25"));

    JSONObject result=J.obj("passed",checks.length(),"total",checks.length(),"checks",checks,"actualAndroidExecution",false,"scope","Production sharing-only JSON parser/writer/copy. No native fingerprint or Android runtime execution.");Files.writeString(Paths.get(args[0]),result.toString(2));System.out.println("Network share exact JSON: "+checks.length()+" checks passed");
  }
}
