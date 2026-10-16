package local.pocketchat;

import org.json.*;
import org.yaml.snakeyaml.Yaml;
import org.yaml.snakeyaml.LoaderOptions;
import org.yaml.snakeyaml.constructor.SafeConstructor;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;

/** Portable connection data only; no rules, scripts, files or environment identity. */
final class NetworkShareCodec {
  static final int LIMIT=1024*1024;
  static final String MIME="application/vnd.pocketchat.network";
  static final Set<String> TYPES=set("socks5 http ss ssr vmess vless trojan hysteria2 tuic");
  static final Set<String> FIELDS=set("name type server port username password uuid cipher alterId tls skip-cert-verify servername sni network flow client-fingerprint fingerprint alpn udp packet-encoding ws-opts grpc-opts h2-opts http-opts reality-opts plugin plugin-opts protocol protocol-param obfs obfs-param udp-relay-mode congestion-controller reduce-rtt disable-sni heartbeat-interval fast-open auth-str token up down tfo mptcp ip-version");
  static Set<String> set(String s){return new HashSet<>(Arrays.asList(s.split(" ")));}
  static IOException invalid(){return new IOException("分享配置格式不支持或不完整，请让发送方重新分享。");}
  static void keys(JSONObject o,Set<String> allowed)throws IOException{for(Iterator<String> it=o.keys();it.hasNext();)if(!allowed.contains(it.next()))throw invalid();}
  static String string(JSONObject o,String k,int max,boolean required)throws IOException{Object v=o.opt(k);if(v==null&&!required)return "";if(!(v instanceof String)||((String)v).length()>max||required&&((String)v).isEmpty())throw invalid();return (String)v;}
  static void scalarTree(Object v,int depth)throws IOException{
    if(depth>7)throw invalid();if(v instanceof JSONObject){JSONObject o=(JSONObject)v;if(o.length()>48)throw invalid();for(Iterator<String> i=o.keys();i.hasNext();){String k=i.next();if(k.length()>128)throw invalid();scalarTree(o.opt(k),depth+1);}}
    else if(v instanceof JSONArray){JSONArray a=(JSONArray)v;if(a.length()>64)throw invalid();for(int i=0;i<a.length();i++)scalarTree(a.opt(i),depth+1);}
    else if(v instanceof String){if(((String)v).length()>8192)throw invalid();}
    else if(!(v instanceof Boolean)&&!(v instanceof Number))throw invalid();
  }
  static JSONObject node(JSONObject value,boolean exit)throws Exception{
    keys(value,FIELDS);scalarTree(value,0);String type=string(value,"type",32,true).toLowerCase(Locale.ROOT);
    if(!TYPES.contains(type)||exit&&!"socks5".equals(type))throw new IOException(exit?"固定出口只支持 SOCKS5。":"此节点协议暂不支持分享。");
    string(value,"name",200,true);String host=string(value,"server",253,true);
    if(host.matches(".*[\\s/\\\\@?#].*")||host.indexOf('\0')>=0)throw invalid();
    Object port=value.opt("port");if(!(port instanceof Number)||((Number)port).doubleValue()!=((Number)port).intValue()||((Number)port).intValue()<1||((Number)port).intValue()>65535)throw invalid();
    for(String k:new String[]{"username","password","uuid","cipher","flow","servername","sni","network","plugin","fingerprint","client-fingerprint"})if(value.has(k))string(value,k,8192,false);
    Map<String,Set<String>> nested=new HashMap<>();
    nested.put("ws-opts",set("path headers max-early-data early-data-header-name v2ray-http-upgrade v2ray-http-upgrade-fast-open"));
    nested.put("grpc-opts",set("grpc-service-name"));nested.put("h2-opts",set("host path"));nested.put("http-opts",set("method path headers"));
    nested.put("reality-opts",set("public-key short-id support-x25519mlkem768"));nested.put("plugin-opts",set("mode host path tls skip-cert-verify mux headers"));
    for(Map.Entry<String,Set<String>> rule:nested.entrySet())if(value.has(rule.getKey())){JSONObject opts=value.optJSONObject(rule.getKey());if(opts==null)throw invalid();keys(opts,rule.getValue());}
    JSONObject clean=new JSONObject(value.toString());clean.put("type",type);return clean;
  }
  static final class Bundle {
    final String name,kind;final JSONObject entry,exit;
    Bundle(String name,JSONObject entry,JSONObject exit){this.name=name;this.entry=entry;this.exit=exit;kind=entry!=null&&exit!=null?"route":entry!=null?"entry":"exit";}
    String encode()throws Exception{return J.obj("format","pocketchat-network","schemaVersion",1,"kind",kind,"name",name,"entry",entry,"exit",exit).toString();}
    String summary(){return (entry==null?"":entry.optString("name"))+(entry!=null&&exit!=null?" → ":"")+(exit==null?"":exit.optString("name"))+" → ChatGPT";}
  }
  static Bundle decode(String text)throws Exception{
    if(text==null||text.getBytes(StandardCharsets.UTF_8).length>LIMIT)throw invalid();
    int depth=0;boolean quote=false,escape=false;for(int i=0;i<text.length();i++){char ch=text.charAt(i);if(quote){if(escape)escape=false;else if(ch=='\\')escape=true;else if(ch=='"')quote=false;}else if(ch=='"')quote=true;else if(ch=='{'||ch=='['){if(++depth>12)throw invalid();}else if(ch=='}'||ch==']'){if(--depth<0)throw invalid();}}
    if(depth!=0||quote)throw invalid();JSONTokener tok=new JSONTokener(text);Object raw=tok.nextValue();if(!(raw instanceof JSONObject)||tok.nextClean()!=0)throw invalid();JSONObject o=(JSONObject)raw;
    keys(o,set("format schemaVersion kind name entry exit"));if(!"pocketchat-network".equals(o.optString("format"))||!(o.opt("schemaVersion") instanceof Number)||o.getDouble("schemaVersion")!=1)throw new IOException("此分享版本不支持，请更新应用或重新分享。");
    JSONObject e=o.optJSONObject("entry"),x=o.optJSONObject("exit");if(e==null&&x==null||o.has("entry")&&!o.isNull("entry")&&e==null||o.has("exit")&&!o.isNull("exit")&&x==null)throw invalid();
    Bundle b=new Bundle(string(o,"name",200,true),e==null?null:node(e,false),x==null?null:node(x,true));if(!b.kind.equals(o.optString("kind")))throw invalid();return b;
  }
  static Object canonical(Object value)throws Exception{
    if(value instanceof JSONObject){JSONObject out=new JSONObject(),o=(JSONObject)value;List<String> names=new ArrayList<>();for(Iterator<String> it=o.keys();it.hasNext();)names.add(it.next());Collections.sort(names);for(String name:names)out.put(name,canonical(o.opt(name)));return out;}
    if(value instanceof JSONArray){JSONArray out=new JSONArray(),a=(JSONArray)value;for(int i=0;i<a.length();i++)out.put(canonical(a.opt(i)));return out;}return value;
  }
  static byte[] provider(JSONObject node){try{return J.obj("proxies",J.arr(canonical(node))).toString().getBytes(StandardCharsets.UTF_8);}catch(Exception e){throw new IllegalArgumentException("节点无法编码");}}
  static JSONObject manual(JSONObject row)throws Exception{return node(J.obj("name",row.optString("name"),"type","socks5","server",row.optString("host"),"port",row.optInt("port"),"username",row.optString("user"),"password",row.optString("password")),true);}
  /** Exactly one node, never its subscription address or other nodes. */
  static JSONObject extract(byte[] bytes,String prefixed,String role)throws Exception{
    if(bytes==null||bytes.length>16*1024*1024)throw new IOException("已保存的节点不可读取，请先更新订阅。");
    LoaderOptions limits=new LoaderOptions();limits.setAllowDuplicateKeys(false);limits.setMaxAliasesForCollections(32);limits.setNestingDepthLimit(12);limits.setCodePointLimit(16*1024*1024);
    Object raw=new Yaml(new SafeConstructor(limits)).load(new String(bytes,StandardCharsets.UTF_8));
    if(!(raw instanceof Map)||!(((Map<?,?>)raw).get("proxies") instanceof List))throw new IOException("此订阅缓存暂不支持分享，请使用 Clash / Mihomo YAML 节点。");
    String prefix=NetworkCatalog.EXIT.equals(role)?"Exit|":"Entry|";if(!prefixed.startsWith(prefix))throw invalid();String name=prefixed.substring(prefix.length());JSONObject selected=null;
    for(Object obj:(List<?>)((Map<?,?>)raw).get("proxies"))if(obj instanceof Map&&name.equals(((Map<?,?>)obj).get("name"))){if(selected!=null)throw invalid();selected=new JSONObject((Map<?,?>)obj);}
    if(selected==null)throw new IOException("当前节点已变化，请重新选择后分享。");return node(selected,NetworkCatalog.EXIT.equals(role));
  }
}
