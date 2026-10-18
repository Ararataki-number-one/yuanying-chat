package local.pocketchat;
import org.json.*;import java.nio.file.*;import java.nio.charset.StandardCharsets;
public final class NetworkShareCodecTest {
  static int checks;
  static void check(boolean ok,String name){if(!ok)throw new AssertionError(name);checks++;}
  interface Attempt {void run()throws Exception;}
  static void reject(Attempt action,String name)throws Exception{try{action.run();}catch(Exception e){checks++;return;}throw new AssertionError(name);}
  public static void main(String[] args)throws Exception{
    byte[] raw=Files.readAllBytes(Paths.get("tests/gecko/assets/sharing-vless.yaml"));
    JSONObject e=NetworkShareCodec.extract(raw,"Entry|Portable VLESS","entry");
    check(e.getInt("port")==443,"quoted port");check(e.getString("encryption").equals("none"),"VLESS encryption");check(e.getBoolean("xudp"),"XUDP");
    check(e.getJSONObject("smux").getInt("max-streams")==16,"mux limits");check(e.getJSONObject("ws-headers").getString("Host").equals("sharing.example.invalid"),"legacy WS headers");
    JSONObject x=NetworkShareCodec.manual(J.obj("name","Fixed Exit","host","exit.example.invalid","port",1080,"user","synthetic","password","空 @ \\ :"));
    check(NetworkShareCodec.manual(J.obj("name","","host","exit.example.invalid","port",1080)).getString("name").equals("exit.example.invalid"),"legacy unnamed manual exit");
    for(String kind:new String[]{"entry","exit","route"}){
      NetworkShareCodec.Bundle b=new NetworkShareCodec.Bundle("Route",kind.equals("exit")?null:e,kind.equals("entry")?null:x);
      NetworkShareCodec.Bundle d=NetworkShareCodec.decode(b.encode());check(d.kind.equals(kind),kind+" role");
      if(d.entry!=null)check(d.entry.similar(e),kind+" all parameters preserved");
      if(d.exit!=null)check(d.exit.similar(x),kind+" exit credentials preserved");
      check(!b.encode().contains("never-export-other-node")&&!b.encode().contains("subscriptionUrl"),kind+" only selected nodes");
    }
    JSONObject again=NetworkShareCodec.extract(NetworkShareCodec.provider(e),"Entry|Portable VLESS","entry");check(again.similar(e),"exported provider reparse");
    for(String key:new String[]{"dialer-proxy","interface-name","routing-mark","certificate-path","pocket-preconnect","unknown-option"}){
      JSONObject bad=new JSONObject(e.toString());bad.put(key,"PRIVATE-MARKER");
      try{NetworkShareCodec.node(bad,false);throw new AssertionError(key);}catch(NetworkShareCodec.Failure err){check(!NetworkShareCodec.explanation(err).contains("PRIVATE-MARKER"),"safe error "+key);}
    }
    JSONObject bad=new JSONObject(e.toString());bad.getJSONObject("smux").put("dialer-proxy","OTHER");final JSONObject muxBad=bad;reject(()->NetworkShareCodec.node(muxBad,false),"nested route override");
    bad=new JSONObject(e.toString());bad.getJSONObject("smux").getJSONObject("brutal-opts").put("file","/private");final JSONObject nested=bad;reject(()->NetworkShareCodec.node(nested,false),"nested file field");
    reject(()->NetworkShareCodec.node(e,true),"VLESS cannot become fixed SOCKS exit");
    reject(()->NetworkShareCodec.extract(raw,"Entry|Missing","entry"),"stale selected node");
    reject(()->NetworkShareCodec.extract("!!java.net.URL [https://example.invalid]".getBytes(StandardCharsets.UTF_8),"Entry|Portable VLESS","entry"),"YAML object tags");
    check(!NetworkShareCodec.explanation(new Exception("PRIVATE-MARKER")).contains("PRIVATE-MARKER"),"raw errors hidden");
    System.out.println("Network sharing codec: "+checks+" checks passed");
  }
}
