package local.pocketchat;

import org.json.*;
import java.io.IOException;
import java.math.*;
import java.util.*;

/** Portable subset of the exact Mihomo v1.19.31 typed options. Unknown fields
 * remain rejected; provider routes, certificate files and scripts never export. */
final class NetworkShareSchema {
  static final Map<String,Map<String,String>> schemas=new LinkedHashMap<>();
  static final Map<String,String> protocols=new HashMap<>(),plugins=new HashMap<>();
  static {
    // adapter/outbound/base.go:193 (Mihomo v1.19.31).
    schema("BasicOption", "tfo:b mptcp:b ip-version:s");
    // adapter/outbound/socks5.go:30 (Mihomo v1.19.31).
    schema("Socks5Option", "name:s server:s port:i username:s password:s tls:b udp:b skip-cert-verify:b name-cert-verify:s fingerprint:s");
    // adapter/outbound/http.go:28 (Mihomo v1.19.31).
    schema("HttpOption", "name:s server:s port:i username:s password:s tls:b sni:s skip-cert-verify:b name-cert-verify:s fingerprint:s headers:headers");
    // adapter/outbound/shadowsocks.go:43 (Mihomo v1.19.31).
    schema("ShadowSocksOption", "name:s server:s port:i password:s cipher:s udp:b plugin:s plugin-opts:plugin udp-over-tcp:b udp-over-tcp-version:i client-fingerprint:s");
    // adapter/outbound/shadowsocksr.go:28 (Mihomo v1.19.31).
    schema("ShadowSocksROption", "name:s server:s port:i password:s cipher:s obfs:s obfs-param:s protocol:s protocol-param:s udp:b");
    // adapter/outbound/vmess.go:53 (Mihomo v1.19.31).
    schema("VmessOption", "name:s server:s port:i uuid:s alterId:i cipher:s udp:b network:s tls:b alpn:list skip-cert-verify:b name-cert-verify:s fingerprint:s servername:s ech-opts:ECHOptions reality-opts:RealityOptions http-opts:HTTPOptions h2-opts:HTTP2Options grpc-opts:GrpcOptions ws-opts:WSOptions packet-addr:b xudp:b packet-encoding:s global-padding:b authenticated-length:b client-fingerprint:s");
    // adapter/outbound/vless.go:58 (Mihomo v1.19.31).
    schema("VlessOption", "name:s server:s port:i uuid:s flow:s tls:b alpn:list udp:b packet-addr:b xudp:b packet-encoding:s encryption:s network:s ech-opts:ECHOptions reality-opts:RealityOptions http-opts:HTTPOptions h2-opts:HTTP2Options grpc-opts:GrpcOptions ws-opts:WSOptions xhttp-opts:XHTTPOptions ws-headers:headers skip-cert-verify:b name-cert-verify:s fingerprint:s servername:s client-fingerprint:s");
    // adapter/outbound/trojan.go:45 (Mihomo v1.19.31).
    schema("TrojanOption", "name:s server:s port:i password:s alpn:list sni:s skip-cert-verify:b name-cert-verify:s fingerprint:s udp:b network:s ech-opts:ECHOptions reality-opts:RealityOptions grpc-opts:GrpcOptions ws-opts:WSOptions ss-opts:TrojanSSOption client-fingerprint:s");
    // adapter/outbound/hysteria2.go:39 (Mihomo v1.19.31).
    schema("Hysteria2Option", "name:s server:s port:i ports:s hop-interval:s up:s down:s password:s obfs:s obfs-password:s obfs-min-packet-size:i obfs-max-packet-size:i sni:s ech-opts:ECHOptions skip-cert-verify:b name-cert-verify:s fingerprint:s alpn:list cwnd:i bbr-profile:s udp-mtu:i handshake-timeout:i initial-stream-receive-window:u64 max-stream-receive-window:u64 initial-connection-receive-window:u64 max-connection-receive-window:u64");
    // adapter/outbound/tuic.go:34 (Mihomo v1.19.31).
    schema("TuicOption", "name:s server:s port:i token:s uuid:s password:s ip:s heartbeat-interval:i alpn:list reduce-rtt:b request-timeout:i udp-relay-mode:s congestion-controller:s disable-sni:b max-udp-relay-packet-size:i fast-open:b max-open-streams:i cwnd:i bbr-profile:s skip-cert-verify:b name-cert-verify:s fingerprint:s recv-window-conn:i recv-window:i disable-mtu-discovery:b max-datagram-frame-size:i sni:s ech-opts:ECHOptions udp-over-stream:b udp-over-stream-version:i");
    // adapter/outbound/vmess.go:165 (Mihomo v1.19.31).
    schema("WSOptions", "path:s headers:headers max-early-data:i early-data-header-name:s v2ray-http-upgrade:b v2ray-http-upgrade-fast-open:b");
    // adapter/outbound/vmess.go:145 (Mihomo v1.19.31).
    schema("HTTPOptions", "method:s path:list headers:headerLists");
    // adapter/outbound/vmess.go:151 (Mihomo v1.19.31).
    schema("HTTP2Options", "host:list path:s");
    // adapter/outbound/vmess.go:156 (Mihomo v1.19.31).
    schema("GrpcOptions", "grpc-service-name:s grpc-user-agent:s ping-interval:i max-connections:i min-streams:i max-streams:i");
    // adapter/outbound/reality.go:13 (Mihomo v1.19.31).
    schema("RealityOptions", "public-key:s short-id:s support-x25519mlkem768:b");
    // adapter/outbound/ech.go:12 (Mihomo v1.19.31).
    schema("ECHOptions", "enable:b config:s query-server-name:s");
    // adapter/outbound/vless.go:93 (Mihomo v1.19.31).
    schema("XHTTPOptions", "path:s host:s mode:s headers:headers no-grpc-header:b x-padding-bytes:s x-padding-obfs-mode:b x-padding-key:s x-padding-header:s x-padding-placement:s x-padding-method:s uplink-http-method:s session-placement:s session-key:s session-table:s session-length:s seq-placement:s seq-key:s uplink-data-placement:s uplink-data-key:s uplink-chunk-size:s sc-max-each-post-bytes:s sc-min-posts-interval-ms:s reuse-settings:XHTTPReuseSettings download-settings:XHTTPDownloadSettings");
    // adapter/outbound/vless.go:121 (Mihomo v1.19.31).
    schema("XHTTPReuseSettings", "max-concurrency:s max-connections:s c-max-reuse-times:s h-max-request-times:s h-max-reusable-secs:s h-keep-alive-period:i");
    // adapter/outbound/vless.go:130 (Mihomo v1.19.31).
    schema("XHTTPDownloadSettings", "path:s host:s headers:headers reuse-settings:XHTTPReuseSettings server:s port:i tls:b alpn:list ech-opts:ECHOptions reality-opts:RealityOptions skip-cert-verify:b name-cert-verify:s fingerprint:s servername:s client-fingerprint:s");
    // adapter/outbound/singmux.go:23 (Mihomo v1.19.31).
    schema("SingMuxOption", "enabled:b protocol:s max-connections:i min-streams:i max-streams:i padding:b statistic:b only-tcp:b brutal-opts:BrutalOption");
    // adapter/outbound/singmux.go:35 (Mihomo v1.19.31).
    schema("BrutalOption", "enabled:b up:s down:s");
    // adapter/outbound/trojan.go:72 (Mihomo v1.19.31).
    schema("TrojanSSOption", "enabled:b method:s password:s");
    // adapter/outbound/shadowsocks.go:58 (Mihomo v1.19.31).
    schema("simpleObfsOption", "mode:s host:s");
    // adapter/outbound/shadowsocks.go:63 (Mihomo v1.19.31).
    schema("v2rayObfsOption", "mode:s host:s path:s tls:b ech-opts:ECHOptions fingerprint:s headers:headers skip-cert-verify:b name-cert-verify:s mux:b v2ray-http-upgrade:b v2ray-http-upgrade-fast-open:b");
    // adapter/outbound/shadowsocks.go:80 (Mihomo v1.19.31).
    schema("gostObfsOption", "mode:s host:s path:s tls:b ech-opts:ECHOptions fingerprint:s headers:headers skip-cert-verify:b name-cert-verify:s mux:b");
    // adapter/outbound/shadowsocks.go:95 (Mihomo v1.19.31).
    schema("shadowTLSOption", "password:s host:s fingerprint:s skip-cert-verify:b name-cert-verify:s version:i alpn:list");
    // adapter/outbound/shadowsocks.go:118 (Mihomo v1.19.31).
    schema("jlsOption", "host:s username:s password:s alpn:list");
    // adapter/outbound/shadowsocks.go:125 (Mihomo v1.19.31).
    schema("kcpTunOption", "key:s crypt:s mode:s conn:i autoexpire:i scavengettl:i mtu:i ratelimit:i sndwnd:i rcvwnd:i datashard:i parityshard:i dscp:i nocomp:b acknodelay:b nodelay:i interval:i resend:i nc:i sockbuf:i smuxver:i smuxbuf:i framesize:i streambuf:i keepalive:i");
    String[] kinds={"socks5:Socks5Option","http:HttpOption","ss:ShadowSocksOption","ssr:ShadowSocksROption","vmess:VmessOption","vless:VlessOption","trojan:TrojanOption","hysteria2:Hysteria2Option","tuic:TuicOption"};
    for(String pair:kinds){String[] p=pair.split(":");protocols.put(p[0],p[1]);Map<String,String> fields=schemas.get(p[1]);fields.putAll(schemas.get("BasicOption"));fields.put("type","s");fields.put("smux","SingMuxOption");}
    String[] extensions={"obfs:simpleObfsOption","v2ray-plugin:v2rayObfsOption","gost-plugin:gostObfsOption","shadow-tls:shadowTLSOption","jls:jlsOption","kcptun:kcpTunOption"};
    for(String pair:extensions){String[] p=pair.split(":");plugins.put(p[0],p[1]);}
  }
  static void schema(String name,String fields){Map<String,String> out=new LinkedHashMap<>();for(String field:fields.split(" ")){String[] parts=field.split(":");out.put(parts[0],parts[1]);}schemas.put(name,out);}
  static String alias(String key,boolean replace){return (replace?key.replace('_','-'):key).toLowerCase(Locale.ROOT);}
  static IOException unsupported(String key){return NetworkShareCodec.failure("分享暂不支持参数"+(key.matches("[A-Za-z][A-Za-z0-9_-]{0,39}")?"「"+key+"」":"")+"，未生成配置；原线路未改变。");}
  static JSONObject object(JSONObject source,String schema,boolean replace,boolean preserve)throws Exception {
    Map<String,String> fields=schemas.get(schema);JSONObject result=new JSONObject();Set<String> seen=new HashSet<>();
    for(Iterator<String> i=source.keys();i.hasNext();){String raw=i.next(),key=null;for(String candidate:fields.keySet())if(alias(raw,replace).equals(alias(candidate,replace))){key=candidate;break;}
      if(key==null||(("type".equals(key)||"smux".equals(key)||"name".equals(key))&&!key.equals(raw)))throw unsupported(raw);
      if(!seen.add(key))throw NetworkShareCodec.failure("节点存在冲突的参数别名，请整理订阅后重试；原线路未改变。");
      Object value=source.opt(raw);Object normalized=convert(value,fields.get(key),source);
      result.put(preserve?raw:key,preserve?value:normalized);
    }
    return result;
  }
  static Object convert(Object value,String kind,JSONObject owner)throws Exception {
    if(value==null||value==JSONObject.NULL)throw NetworkShareCodec.invalid();
    switch(kind){
      case "s":return string(value);
      case "i":return integer(value,64,false);
      case "u32":return integer(value,32,true);
      case "u64":return integer(value,64,true);
      case "b":if(value instanceof Boolean)return value;if(integral(value))return new BigInteger(value.toString()).signum()!=0;throw NetworkShareCodec.invalid();
      case "list":if(!(value instanceof JSONArray))throw NetworkShareCodec.invalid();JSONArray values=(JSONArray)value,out=new JSONArray();for(int i=0;i<values.length();i++)out.put(string(values.opt(i)));return out;
      case "headers":case "headerLists":
        if(!(value instanceof JSONObject))throw NetworkShareCodec.invalid();JSONObject headers=(JSONObject)value,clean=new JSONObject();for(Iterator<String> it=headers.keys();it.hasNext();){String key=it.next();clean.put(key,convert(headers.opt(key),kind.equals("headers")?"s":"list",owner));}return clean;
      case "plugin":
        if(!(value instanceof JSONObject))throw NetworkShareCodec.invalid();Object selected=null;for(Iterator<String> i=owner.keys();i.hasNext();){String key=i.next();if(alias(key,true).equals("plugin"))selected=owner.opt(key);}
        String plugin=string(selected),rule=plugins.get(plugin);if(rule==null)throw NetworkShareCodec.failure("此插件暂不支持独立分享；原线路未改变。");
        // Fingerprint v1 includes the original plugin map, before its second decoder.
        // Validate against that decoder (case folding only), retaining keys and values.
        return object((JSONObject)value,rule,false,true);
      default:if(!(value instanceof JSONObject)||!schemas.containsKey(kind))throw NetworkShareCodec.invalid();return object((JSONObject)value,kind,true,false);
    }
  }
  static boolean integral(Object value){return value instanceof Byte||value instanceof Short||value instanceof Integer||value instanceof Long||value instanceof BigInteger;}
  static String string(Object value)throws IOException {
    if(value instanceof String)return (String)value;
    if(integral(value))return value.toString();
    if(value instanceof Number){double number=((Number)value).doubleValue();if(!Double.isFinite(number))throw NetworkShareCodec.invalid();if(number==0)return (Double.doubleToRawLongBits(number)<0?"-":"")+"0E+00";
      BigDecimal decimal=BigDecimal.valueOf(number).stripTrailingZeros();int exponent=decimal.precision()-decimal.scale()-1;
      return decimal.movePointLeft(exponent).toPlainString()+"E"+(exponent<0?"-":"+")+String.format(Locale.ROOT,"%02d",Math.abs(exponent));}
    throw NetworkShareCodec.invalid();
  }
  static BigInteger parseInteger(String text)throws IOException {
    String sign="";if(text.startsWith("+")||text.startsWith("-")){sign=text.substring(0,1);text=text.substring(1);}int radix=10;String digits=text;
    if(text.startsWith("0x")||text.startsWith("0X")){radix=16;digits=text.substring(2);}else if(text.startsWith("0b")||text.startsWith("0B")){radix=2;digits=text.substring(2);}else if(text.startsWith("0o")||text.startsWith("0O")){radix=8;digits=text.substring(2);}else if(text.length()>1&&text.startsWith("0")){radix=8;digits=text.substring(1);}
    // Go base-0 allows one underscore immediately after a radix prefix (including 0).
    if(radix!=10&&digits.startsWith("_"))digits=digits.substring(1);
    String chars=radix==16?"0-9a-fA-F":radix==8?"0-7":radix==2?"01":"0-9";
    if(!digits.matches("["+chars+"]+(?:_["+chars+"]+)*"))throw NetworkShareCodec.invalid();
    try{return new BigInteger((sign.equals("-")?"-":"")+digits.replace("_",""),radix);}catch(NumberFormatException error){throw NetworkShareCodec.invalid();}
  }
  static Number integer(Object value,int bits,boolean unsigned)throws IOException {
    BigInteger number;
    if(value instanceof String)number=parseInteger((String)value);
    else if(integral(value))number=new BigInteger(value.toString());
    else if(value instanceof Number){double n=((Number)value).doubleValue();if(!Double.isFinite(n))throw NetworkShareCodec.invalid();number=BigDecimal.valueOf(n).toBigInteger();}
    else throw NetworkShareCodec.invalid();
    BigInteger min=unsigned?BigInteger.ZERO:BigInteger.ONE.shiftLeft(bits-1).negate(),max=BigInteger.ONE.shiftLeft(unsigned?bits:bits-1).subtract(BigInteger.ONE);
    if(number.compareTo(min)<0||number.compareTo(max)>0)throw NetworkShareCodec.invalid();return number.bitLength()<63?number.longValue():number;
  }
  static JSONObject node(JSONObject value,boolean exit)throws Exception {
    NetworkShareCodec.scalarTree(value,0);String type=NetworkShareCodec.string(value,"type",32,true);String rule=protocols.get(type);
    if(rule==null||exit&&!"socks5".equals(type))throw NetworkShareCodec.failure(exit?"固定出口只支持 SOCKS5。":"此节点协议暂不支持分享。");
    NetworkShareCodec.string(value,"name",200,true);JSONObject result=object(value,rule,true,false);NetworkShareCodec.string(result,"name",200,true);String host=NetworkShareCodec.string(result,"server",253,true);
    if(host.matches(".*[\\s/\\\\@?#].*")||host.indexOf('\0')>=0)throw NetworkShareCodec.invalid();
    if(type.equals("vless")||type.equals("vmess"))NetworkShareCodec.string(result,"uuid",8192,true);
    if((type.equals("ss")||type.equals("ssr")))NetworkShareCodec.string(result,"cipher",8192,true);
    if(result.has("plugin")&&!result.optString("plugin").isEmpty()&&!plugins.containsKey(result.optString("plugin")))throw NetworkShareCodec.failure("此插件暂不支持独立分享；原线路未改变。");
    long port=result.optLong("port",0);boolean range="hysteria2".equals(type)&&result.has("ports")&&portRanges(result.getString("ports"));
    if(port<0||port>65535||port==0&&!range)throw NetworkShareCodec.invalid();
    if(result.has("ip-version")&&!result.optString("ip-version").isEmpty()&&!NetworkShareCodec.set("dual ipv4 ipv6 ipv4-prefer ipv6-prefer").contains(result.getString("ip-version")))throw NetworkShareCodec.invalid();
    return result;
  }
  static boolean portRanges(String text)throws IOException {
    String value=text.trim();if(value.isEmpty()||value.equals("*"))return false;String[] ranges=value.replace(',','/').split("/",-1);if(ranges.length>28)throw NetworkShareCodec.invalid();boolean any=false;
    for(String range:ranges){if(range.isEmpty())continue;String[] bounds=range.trim().split("-",-1);if(bounds.length>2)throw NetworkShareCodec.invalid();for(String part:bounds){String token=part.replaceAll("^[\\[ ]+|[\\] ]+$","");if(!token.matches("[0-9]+"))throw NetworkShareCodec.invalid();try{long port=Long.parseLong(token);if(port<1||port>65535)throw NetworkShareCodec.invalid();}catch(NumberFormatException error){throw NetworkShareCodec.invalid();}}any=true;}return any;
  }
}
