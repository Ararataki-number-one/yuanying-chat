package local.pocketchat;
import org.json.*;import java.nio.file.*;import java.nio.charset.StandardCharsets;
public final class NetworkShareCodecTest {
  static int checks;
  static boolean same(Object a,Object b){
    if(a instanceof JSONObject&&b instanceof JSONObject){JSONObject x=(JSONObject)a,y=(JSONObject)b;if(x.length()!=y.length())return false;for(java.util.Iterator<String> it=x.keys();it.hasNext();){String k=it.next();if(!y.has(k)||!same(x.opt(k),y.opt(k)))return false;}return true;}
    if(a instanceof JSONArray&&b instanceof JSONArray){JSONArray x=(JSONArray)a,y=(JSONArray)b;if(x.length()!=y.length())return false;for(int i=0;i<x.length();i++)if(!same(x.opt(i),y.opt(i)))return false;return true;}
    return java.util.Objects.equals(a,b);
  }
  static void check(boolean ok,String name){if(!ok)throw new AssertionError(name);checks++;}
  interface Attempt {void run()throws Exception;}
  static void reject(Attempt action,String name)throws Exception{try{action.run();}catch(Exception e){checks++;return;}throw new AssertionError(name);}
  static JSONObject extract(String yaml,String name)throws Exception{return NetworkShareCodec.extract(yaml.getBytes(StandardCharsets.UTF_8),"Entry|"+name,"entry");}
  static String plain(){return "proxies:\n  - {name: Selected, type: socks5, server: 127.0.0.1, port: 1080}\n";}
  static String aliases(int count){StringBuilder s=new StringBuilder("base: &defaults {type: socks5, server: 127.0.0.1, port: 1080}\nproxies:\n");for(int i=0;i<count;i++)s.append("  - {<<: *defaults, name: ").append(i==0?"Selected":"Other-"+i).append("}\n");return s.toString();}
  static void safeReject(String yaml,String label)throws Exception{
    try{extract(yaml,"Selected");throw new AssertionError(label);}
    catch(NetworkShareCodec.Failure failure){String text=NetworkShareCodec.explanation(failure);check(!text.contains("PRIVATE-MARKER")&&!text.contains("line ")&&!text.contains("\n"),label+" exposes no parser snippet");check(!text.startsWith("读取分享配置失败"),label+" has actionable failure");}
  }
  static void completeSubscriptions()throws Exception{
    for(int count:new int[]{32,33,100}){JSONObject selected=extract(aliases(count),"Selected");check(selected.getInt("port")==1080&&selected.length()==4,"Complete subscription with "+count+" merged nodes shares only selected node");}
    StringBuilder groups=new StringBuilder(plain()+"choices: &choices [DIRECT]\nproxy-groups:\n");for(int i=0;i<100;i++)groups.append("  - {name: Group-").append(i).append(", type: select, proxies: *choices}\n");
    JSONObject selected=extract(groups.toString(),"Selected");check(selected.length()==4&&!selected.toString().contains("Group-"),"Unrelated proxy-group aliases do not prevent sharing");
    for(String unrelated:new String[]{"metadata: {private: PRIVATE-MARKER, private: replacement}\n","metadata: "+"[".repeat(14)+"PRIVATE-MARKER"+"]".repeat(14)+"\n","metadata: !!java.net.URL [https://PRIVATE-MARKER.invalid]\n","metadata: &loop {again: *loop}\n"}){
      JSONObject actual=extract(unrelated+plain(),"Selected");check(actual.length()==4&&!actual.toString().contains("PRIVATE-MARKER"),"Unused metadata is never constructed or exported");
    }
    check(extract(plain()+"---\nmetadata: PRIVATE-MARKER\n","Selected").length()==4,"Read first YAML document as native subscription parser does");
    String inherited="base: &base {name: Inherited, type: socks5, server: 127.0.0.1, port: 1080}\nproxies: [{<<: *base}]\n";
    check(extract(inherited,"Inherited").getString("name").equals("Inherited"),"Select a node whose name comes from merge defaults");
    String first="first: &first {name: First, type: socks5, server: 127.0.0.1, port: 1080}\nsecond: &second {name: Second, port: 1081}\nproxies: [{<<: [*first, *second]}]\n";
    check(extract(first,"First").getInt("port")==1080,"Earlier merge sequence map supplies inherited name and port");
    reject(()->extract(first,"Second"),"Overridden merged name cannot select another route");
    for(String order:new String[]{"name: Selected, <<: *base","<<: *base, name: Selected"}){
      String yaml="base: &base {name: Inherited, type: socks5, server: 127.0.0.1, port: 1080}\nproxies: [{"+order+"}]\n";
      check(extract(yaml,"Selected").getString("name").equals("Selected"),"Explicit name wins regardless of merge order");
    }
    check(extract("base: &base {proxies: [{name: Selected, type: socks5, server: 127.0.0.1, port: 1080}]}\n<<: *base\n","Selected").length()==4,"Root merge can supply provider sequence");
    check(extract("selected-name: &name Selected\nproxies: [{name: *name, type: socks5, server: 127.0.0.1, port: 1080}]\n","Selected").length()==4,"Scalar name aliases preserve exact selected identity");
    safeReject("mixed-port: 7890\nmixed-port: 7891\n"+plain(),"Duplicate top-level keys stay rejected");
    safeReject("proxies: [{name: Selected, type: socks5, server: 127.0.0.1, port: 1080, port: 1081}]\n","Duplicate selected fields stay rejected");
    safeReject("proxies: [!!java.net.URL {name: Selected, type: socks5, server: 127.0.0.1, port: 1080}]\n","Selected custom tags stay rejected");
    safeReject("proxies: [!!seq {name: Selected, type: socks5, server: 127.0.0.1, port: 1080}]\n","A sequence tag cannot construct a selected mapping");
    safeReject("proxies: [{name: Selected, type: socks5, server: 127.0.0.1, port: 1080, password: !!map PRIVATE-MARKER}]\n","A mapping tag cannot construct a selected scalar");
    safeReject("proxies: [{name: Selected, type: socks5, server: 127.0.0.1, port: !!int PRIVATE-MARKER}]\n","Malformed explicit number is safely classified");
    safeReject("proxies: [{name: Selected, type: socks5, server: 127.0.0.1, port: .nan}]\n","Nonfinite number is safely rejected");
    safeReject("base: &loop {<<: *loop, name: Selected, type: socks5, server: 127.0.0.1, port: 1080}\nproxies: [*loop]\n","Selected merge cycle stays rejected");
    safeReject("proxies: [{name: Selected, type: socks5, server: 127.0.0.1, port: 1080, ws-opts: &loop {headers: {x: *loop}}}]\n","Selected nested cycle stays rejected");
    safeReject("base: &base {name: Selected, type: socks5, server: 127.0.0.1, port: 1080}\nproxies: [*base, *base]\n","Duplicate selected names stay rejected");
    safeReject("proxies: [{name: Selected, password: PRIVATE-MARKER, type: socks5, server: [unterminated\n","Malformed YAML is safely classified");
    StringBuilder bomb=new StringBuilder("a: &a [PRIVATE-MARKER"+",x".repeat(9)+"]\n");
    for(char c='b';c<='e';c++)bomb.append(c).append(": &").append(c).append(" [*").append((char)(c-1)).append((",*"+(char)(c-1)).repeat(9)).append("]\n");
    bomb.append("proxies: [{name: Selected, type: socks5, server: 127.0.0.1, port: 1080, alpn: *e}]\n");
    safeReject(bomb.toString(),"Selected alias amplification is rejected before construction");
    StringBuilder chain=new StringBuilder("d0: &d0 {name: Selected, type: socks5, server: 127.0.0.1, port: 1080}\n");for(int i=1;i<=100;i++)chain.append("d").append(i).append(": &d").append(i).append(" {<<: *d").append(i-1).append("}\n");chain.append("proxies: [*d100]\n");
    safeReject(chain.toString(),"Deep inherited-name alias chain is bounded");
    safeReject(plain()+"scalar: &s x\naliases: [*s"+",*s".repeat(65536)+"]\n","Scalar alias syntax allocation is bounded");
    safeReject(plain()+"metadata: [0"+",0".repeat(65536)+"]\n","Whole syntax node allocation is bounded");
    safeReject(plain()+"metadata: "+"[".repeat(70)+"PRIVATE-MARKER"+"]".repeat(70)+"\n","Whole syntax depth is bounded");
  }
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
      if(d.entry!=null)check(same(d.entry,e),kind+" all parameters preserved");
      if(d.exit!=null)check(same(d.exit,x),kind+" exit credentials preserved");
      check(!b.encode().contains("never-export-other-node")&&!b.encode().contains("subscriptionUrl"),kind+" only selected nodes");
    }
    JSONObject again=NetworkShareCodec.extract(NetworkShareCodec.provider(e),"Entry|Portable VLESS","entry");check(same(again,e),"exported provider reparse");
    for(String password:new String[]{"/", "\\/", "\\\\/", "https://example.invalid/path?q=1", "空 / \\ \n 🔐"}){
      JSONObject special=new JSONObject(x.toString());special.put("password",password);
      JSONObject decoded=new JSONObject(new String(NetworkShareCodec.provider(special),StandardCharsets.UTF_8)).getJSONArray("proxies").getJSONObject(0);
      check(decoded.getString("password").equals(password),"JSON/YAML slash normalization preserves credential value");
      check(NetworkShareCodec.extract(NetworkShareCodec.provider(special),"Exit|Fixed Exit","exit").getString("password").equals(password),"YAML parser preserves credential value");
    }
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
    completeSubscriptions();
    System.out.println("Network sharing codec: "+checks+" checks passed");
  }
}
