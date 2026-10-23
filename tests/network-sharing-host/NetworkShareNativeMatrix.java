package local.pocketchat;

import org.json.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;

/** Synthetic production-code exports for native parser acceptance comparison.
 * Native fingerprints and real connections are deliberately outside this fixture. */
public final class NetworkShareNativeMatrix {
  interface Verify {void run(JSONObject node)throws Exception;}
  static final class Sample {
    final String id,body;final boolean share,nativeAccept;final Verify verify;
    Sample(String id,String body,boolean share,boolean nativeAccept,Verify verify){this.id=id;this.body=body;this.share=share;this.nativeAccept=nativeAccept;this.verify=verify;}
    String yaml(){return "metadata: {other-account: SYNTHETIC-PRIVATE-MARKER}\nproxies:\n  - {name: Selected, server: 127.0.0.1, "+body+"}\n";}
  }
  static final String UUID="00000000-0000-0000-0000-000000000001";
  static final String VLESS="type: vless, port: 443, uuid: "+UUID;
  static final String VMESS="type: vmess, port: 443, uuid: "+UUID+", alterId: 0, cipher: auto";
  static final String SS="type: ss, port: 443, cipher: aes-128-gcm, password: synthetic";
  static void require(boolean value,String label){if(!value)throw new AssertionError(label);}
  static void value(JSONObject node,String path,Object expected)throws Exception{
    Object got=node;for(String part:path.split("/")){if(got instanceof JSONObject)got=((JSONObject)got).get(part);else if(got instanceof JSONArray)got=((JSONArray)got).get(Integer.parseInt(part));else throw new AssertionError("Missing structured field "+path);}
    if(expected instanceof Number)require(got instanceof Number&&new java.math.BigDecimal(got.toString()).compareTo(new java.math.BigDecimal(expected.toString()))==0,path+" numeric value/type");
    else require(expected.equals(got),path+" exact value/type");
  }
  static Sample yes(String id,String body,Verify verify){return new Sample(id,body,true,true,verify);}
  static Sample no(String id,String body,boolean nativeAccept){return new Sample(id,body,false,nativeAccept,n->{});}
  static List<Sample> samples(){return Arrays.asList(
    yes("numeric-credentials","type: socks5, port: 1080, username: 12345, password: 98765",n->{value(n,"username","12345");value(n,"password","98765");}),
    yes("credential-on","type: socks5, port: 1080, password: on",n->value(n,"password","on")),
    yes("credential-NO","type: socks5, port: 1080, password: NO",n->value(n,"password","NO")),
    no("credential-boolean","type: socks5, port: 1080, password: true",false),
    yes("credential-float","type: socks5, port: 1080, password: 0.25",n->value(n,"password","2.5E-01")),
    yes("port-quoted-octal","type: socks5, port: '01000'",n->value(n,"port",512)),
    yes("port-quoted-hex","type: socks5, port: '0x1bb'",n->value(n,"port",443)),
    no("port-invalid-08","type: socks5, port: '08'",false),
    yes("unique-field-alias","type: socks5, port: 1080, tls: true, skip_cert_verify: true",n->{value(n,"skip-cert-verify",true);require(!n.has("skip_cert_verify"),"Canonical typed alias");}),
    no("conflicting-field-alias","type: socks5, port: 1080, skip-cert-verify: false, skip_cert_verify: true",true),
    yes("integer-boolean","type: socks5, port: 1080, udp: 1",n->value(n,"udp",true)),
    no("quoted-boolean","type: socks5, port: 1080, udp: 'true'",false),
    yes("http-proxy-headers","type: http, port: 8080, headers: {X_Count: 123, Host: synthetic.invalid}",n->{value(n,"headers/X_Count","123");value(n,"headers/Host","synthetic.invalid");require(!n.getJSONObject("headers").has("x-count"),"Header spelling preserved");}),
    yes("ws-headers",VLESS+", network: ws, ws_opts: {path: /socket, headers: {X_Count: 123, Host: synthetic.invalid}}",n->{value(n,"ws-opts/headers/X_Count","123");value(n,"ws-opts/path","/socket");require(!n.has("ws_opts"),"Nested typed alias");}),
    no("ws-header-list",VLESS+", network: ws, ws-opts: {headers: {Host: [synthetic.invalid]}}",false),
    yes("http-transport-header-list",VMESS+", network: http, http-opts: {method: GET, path: [/one, /two], headers: {Host: [synthetic.invalid], X_Count: [123, 'kept']}}",n->{value(n,"http-opts/path/1","/two");value(n,"http-opts/headers/X_Count/0","123");value(n,"http-opts/headers/X_Count/1","kept");}),
    no("http-transport-header-scalar",VMESS+", network: http, http-opts: {headers: {Host: synthetic.invalid}}",false),
    yes("hy2-ports-only","type: hysteria2, ports: '443,8443-8445', password: synthetic, hop-interval: '10-20'",n->{require(!n.has("port"),"No invented port");value(n,"ports","443,8443-8445");value(n,"hop-interval","10-20");}),
    yes("hy2-options","type: hysteria2, port: 443, password: 12345, obfs: salamander, obfs-password: 98765, up: 100, down: '200 Mbps', udp-mtu: 1197, handshake-timeout: 5",n->{value(n,"password","12345");value(n,"obfs-password","98765");value(n,"up","100");value(n,"udp-mtu",1197);}),
    no("hy2-port-range-zero","type: hysteria2, ports: '0', password: synthetic",true),
    yes("tuic-options","type: tuic, port: 443, uuid: "+UUID+", password: 12345, ip: 127.0.0.1, request-timeout: 9000, max-open-streams: 12, udp-over-stream: true, udp-over-stream-version: 2, heartbeat-interval: 3000, disable-mtu-discovery: true",n->{value(n,"password","12345");value(n,"request-timeout",9000);value(n,"max-open-streams",12);value(n,"udp-over-stream",true);value(n,"disable-mtu-discovery",true);}),
    yes("grpc-options",VLESS+", tls: true, network: grpc, grpc_opts: {grpc-service-name: 123, grpc-user-agent: synthetic, ping-interval: 30, max-connections: 2, min-streams: 1, max-streams: 8}",n->{value(n,"grpc-opts/grpc-service-name","123");value(n,"grpc-opts/grpc-user-agent","synthetic");value(n,"grpc-opts/max-streams",8);}),
    yes("ss-plugin-raw-values",SS+", plugin: v2ray-plugin, plugin-opts: {mode: websocket, Host: 123, headers: {X_Count: 321}, mux: 1, v2ray-http-upgrade: true}",n->{value(n,"plugin-opts/Host",123);value(n,"plugin-opts/headers/X_Count",321);value(n,"plugin-opts/mux",1);require(!n.getJSONObject("plugin-opts").has("host"),"Raw plugin key preserved for fingerprint v1");}),
    no("ss-plugin-unsupported-alias",SS+", plugin: v2ray-plugin, plugin-opts: {mode: websocket, skip_cert_verify: true}",true),
    yes("ss-simple-obfs",SS+", plugin: obfs, plugin-opts: {mode: http, host: synthetic.invalid}, udp-over-tcp: true, udp-over-tcp-version: 2",n->{value(n,"plugin-opts/host","synthetic.invalid");value(n,"udp-over-tcp",true);value(n,"udp-over-tcp-version",2);}),
    yes("xhttp-options",VLESS+", network: xhttp, xhttp-opts: {path: /x, host: synthetic.invalid, mode: auto, headers: {X_Count: 7}, no-grpc-header: true, x-padding-bytes: '10-20', x-padding-obfs-mode: true, reuse-settings: {max-concurrency: '2-4', h-keep-alive-period: 30}}",n->{value(n,"xhttp-opts/headers/X_Count","7");value(n,"xhttp-opts/no-grpc-header",true);value(n,"xhttp-opts/x-padding-bytes","10-20");value(n,"xhttp-opts/reuse-settings/h-keep-alive-period",30);}),
    yes("xhttp-download-settings",VLESS+", network: xhttp, xhttp-opts: {path: /up, mode: packet-up, download-settings: {path: /down, server: 127.0.0.2, port: '0x20fb', tls: false, headers: {Host: down.invalid}, reuse-settings: {max-connections: '1-2'}}}",n->{value(n,"xhttp-opts/download-settings/port",8443);value(n,"xhttp-opts/download-settings/server","127.0.0.2");value(n,"xhttp-opts/download-settings/reuse-settings/max-connections","1-2");}),
    no("blocked-external-dialer","type: socks5, port: 1080, dialer-proxy: OtherPrivateRoute",false),
    no("missing-vless-uuid","type: vless, port: 443",false),
    no("protocol-case-mismatch","type: SOCKS5, port: 1080",false)
  );}
  public static void main(String[] args)throws Exception{
    if(args.length!=2)throw new IllegalArgumentException("output-directory and current|baseline required");Path dir=Paths.get(args[0]);Files.createDirectories(dir);boolean baseline=args[1].equals("baseline");JSONArray rows=new JSONArray();int failed=0;
    for(Sample sample:samples()){
      Path input=dir.resolve(sample.id+".yaml");Files.write(input,sample.yaml().getBytes(StandardCharsets.UTF_8));JSONObject row=J.obj("case",sample.id,"expectedShareAccepted",sample.share,"expectedNativeOriginalAccepted",sample.nativeAccept,"input",input.toAbsolutePath().toString());JSONArray assertions=new JSONArray();
      boolean accepted=false,checks=true;
      try{
        JSONObject node=NetworkShareCodec.extract(sample.yaml().getBytes(StandardCharsets.UTF_8),"Entry|Selected",NetworkCatalog.ENTRY);accepted=true;
        byte[] encoded=NetworkShareCodec.provider(node);Path exported=dir.resolve(sample.id+".exported.yaml");Files.write(exported,encoded);row.put("export",exported.toAbsolutePath().toString());row.put("node",node);
        require(!node.toString().contains("SYNTHETIC-PRIVATE-MARKER"),"Unrelated account excluded");assertions.put("Only selected node exported");
        sample.verify.run(node);assertions.put("Case-specific typed/raw values preserved");
        JSONObject again=NetworkShareCodec.extract(encoded,"Entry|Selected",NetworkCatalog.ENTRY);require(same(node,again),"Export/reparse exact structured values");assertions.put("Production export/reparse retains exact values and types");
      }catch(AssertionError error){checks=false;row.put("assertionFailure",error.getMessage());}
      catch(Exception error){if(accepted)checks=false;String safe=NetworkShareCodec.explanation(error);row.put("exceptionClass",error.getClass().getName());row.put("explanation",safe);if(safe.contains("SYNTHETIC-PRIVATE-MARKER")||safe.contains("\n")){checks=false;row.put("assertionFailure","Raw parsing details leaked");}else assertions.put("Failure explanation excludes parser snippets and private marker");}
      boolean pass=accepted==sample.share&&checks;row.put("accepted",accepted);row.put("assertions",assertions);row.put("assertionsPassed",checks);row.put("pass",pass);rows.put(row);if(!pass)failed++;
    }
    JSONObject report=J.obj("mode",baseline?"baseline":"current","cases",rows,"total",rows.length(),"passed",rows.length()-failed,"status",failed==0?"passed":"differences","productionCodecExecuted",true,"pocketFingerprintVerified",false,"actualAndroidExecution",false);
    Files.write(dir.resolve("codec-results.json"),report.toString(2).getBytes(StandardCharsets.UTF_8));System.out.println(report.getString("mode")+": "+(rows.length()-failed)+"/"+rows.length()+" expectations met");
  }
  static boolean same(Object a,Object b)throws Exception{
    if(a instanceof JSONObject&&b instanceof JSONObject){JSONObject x=(JSONObject)a,y=(JSONObject)b;if(x.length()!=y.length())return false;for(Iterator<String> it=x.keys();it.hasNext();){String k=it.next();if(!y.has(k)||!same(x.get(k),y.get(k)))return false;}return true;}
    if(a instanceof JSONArray&&b instanceof JSONArray){JSONArray x=(JSONArray)a,y=(JSONArray)b;if(x.length()!=y.length())return false;for(int i=0;i<x.length();i++)if(!same(x.get(i),y.get(i)))return false;return true;}
    if(a instanceof Number&&b instanceof Number)return new java.math.BigDecimal(a.toString()).compareTo(new java.math.BigDecimal(b.toString()))==0;
    return Objects.equals(a,b);
  }
}
