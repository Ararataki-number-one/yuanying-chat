package local.pocketchat;

import org.json.*;
import org.yaml.snakeyaml.LoaderOptions;
import org.yaml.snakeyaml.composer.Composer;
import org.yaml.snakeyaml.constructor.SafeConstructor;
import org.yaml.snakeyaml.error.YAMLException;
import org.yaml.snakeyaml.events.Event;
import org.yaml.snakeyaml.nodes.*;
import org.yaml.snakeyaml.parser.Parser;
import org.yaml.snakeyaml.parser.ParserImpl;
import org.yaml.snakeyaml.reader.StreamReader;
import org.yaml.snakeyaml.resolver.Resolver;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;

/** Portable connection data only; no rules, scripts, files or environment identity. */
final class NetworkShareCodec {
  static final int LIMIT=1024*1024;
  static final String MIME="application/vnd.pocketchat.network";
  static final Set<String> TYPES=set("socks5 http ss ssr vmess vless trojan hysteria2 tuic");
  static final Set<String> FIELDS=set("name type server port username password uuid cipher alterId tls skip-cert-verify servername sni network flow client-fingerprint fingerprint alpn udp packet-encoding ws-opts grpc-opts h2-opts http-opts reality-opts plugin plugin-opts protocol protocol-param obfs obfs-param udp-relay-mode congestion-controller reduce-rtt disable-sni heartbeat-interval fast-open auth-str token up down tfo mptcp ip-version encryption xudp packet-addr smux ws-headers name-cert-verify global-padding authenticated-length");
  static final class Failure extends IOException { Failure(String message){super(message);} }
  static Failure failure(String message){return new Failure(message);}
  static String explanation(Exception error){return error instanceof Failure?error.getMessage():"读取分享配置失败，请重试；原线路未改变。";}
  static Set<String> set(String s){return new HashSet<>(Arrays.asList(s.split(" ")));}
  static IOException invalid(){return failure("分享配置格式不支持或不完整，请重新选择节点后分享。");}
  static void keys(JSONObject o,Set<String> allowed)throws IOException{for(Iterator<String> it=o.keys();it.hasNext();){String key=it.next();if(!allowed.contains(key))throw failure("分享暂不支持参数"+(key.matches("[A-Za-z][A-Za-z0-9-]{0,39}")?"「"+key+"」":"")+"，未生成配置；原线路未改变。");}}
  static String string(JSONObject o,String k,int max,boolean required)throws IOException{Object v=o.opt(k);if(v==null&&!required)return "";if(!(v instanceof String)||((String)v).length()>max||required&&((String)v).isEmpty())throw invalid();return (String)v;}
  static void scalarTree(Object v,int depth)throws IOException{
    if(depth>7)throw invalid();if(v instanceof JSONObject){JSONObject o=(JSONObject)v;if(o.length()>48)throw invalid();for(Iterator<String> i=o.keys();i.hasNext();){String k=i.next();if(k.length()>128)throw invalid();scalarTree(o.opt(k),depth+1);}}
    else if(v instanceof JSONArray){JSONArray a=(JSONArray)v;if(a.length()>64)throw invalid();for(int i=0;i<a.length();i++)scalarTree(a.opt(i),depth+1);}
    else if(v instanceof String){if(((String)v).length()>8192)throw invalid();}
    else if(!(v instanceof Boolean)&&!(v instanceof Number))throw invalid();
  }
  static JSONObject node(JSONObject value,boolean exit)throws Exception{
    keys(value,FIELDS);scalarTree(value,0);String type=string(value,"type",32,true).toLowerCase(Locale.ROOT);
    if(!TYPES.contains(type)||exit&&!"socks5".equals(type))throw failure(exit?"固定出口只支持 SOCKS5。":"此节点协议暂不支持分享。");
    string(value,"name",200,true);String host=string(value,"server",253,true);
    if(host.matches(".*[\\s/\\\\@?#].*")||host.indexOf('\0')>=0)throw invalid();
    Object port=value.opt("port");if(!(port instanceof Number)||((Number)port).doubleValue()!=((Number)port).intValue()||((Number)port).intValue()<1||((Number)port).intValue()>65535)throw invalid();
    for(String k:new String[]{"username","password","uuid","cipher","flow","servername","sni","network","plugin","fingerprint","client-fingerprint","encryption","name-cert-verify"})if(value.has(k))string(value,k,8192,false);
    Map<String,Set<String>> nested=new HashMap<>();
    nested.put("ws-opts",set("path headers max-early-data early-data-header-name v2ray-http-upgrade v2ray-http-upgrade-fast-open"));
    nested.put("grpc-opts",set("grpc-service-name"));nested.put("h2-opts",set("host path"));nested.put("http-opts",set("method path headers"));
    nested.put("reality-opts",set("public-key short-id support-x25519mlkem768"));nested.put("plugin-opts",set("mode host path tls skip-cert-verify mux headers"));
    nested.put("smux",set("enabled protocol max-connections min-streams max-streams padding statistic only-tcp brutal-opts"));
    for(Map.Entry<String,Set<String>> rule:nested.entrySet())if(value.has(rule.getKey())){JSONObject opts=value.optJSONObject(rule.getKey());if(opts==null)throw invalid();keys(opts,rule.getValue());}
    JSONObject mux=value.optJSONObject("smux");if(mux!=null&&mux.has("brutal-opts")){JSONObject opts=mux.optJSONObject("brutal-opts");if(opts==null)throw invalid();keys(opts,set("enabled up down"));}
    if(value.has("ws-headers")){JSONObject headers=value.optJSONObject("ws-headers");if(headers==null)throw invalid();for(Iterator<String> it=headers.keys();it.hasNext();)string(headers,it.next(),8192,false);}
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
  // Android's JSON encoder escapes '/', which Mihomo's YAML reader rejects.
  // Consume escape pairs so literal backslashes in credentials remain intact.
  static String yamlJson(String json){StringBuilder out=new StringBuilder(json.length());for(int i=0;i<json.length();i++){char c=json.charAt(i);if(c=='\\'&&i+1<json.length()){char next=json.charAt(++i);if(next!='/')out.append(c);out.append(next);}else out.append(c);}return out.toString();}
  static byte[] provider(JSONObject node){try{return yamlJson(J.obj("proxies",J.arr(canonical(node))).toString()).getBytes(StandardCharsets.UTF_8);}catch(Exception e){throw new IllegalArgumentException("节点无法编码");}}
  static JSONObject manual(JSONObject row)throws Exception{String name=row.optString("name");if(name.trim().isEmpty())name=row.optString("host");return node(J.obj("name",name,"type","socks5","server",row.optString("host"),"port",row.optInt("port"),"username",row.optString("user"),"password",row.optString("password")),true);}
  static Object yamlValue(Object value,int depth)throws Exception{
    if(depth>7)throw invalid();
    if(value instanceof Map){Map<?,?> source=(Map<?,?>)value;if(source.size()>48)throw invalid();JSONObject result=new JSONObject();for(Map.Entry<?,?> item:source.entrySet()){if(!(item.getKey() instanceof String)||((String)item.getKey()).length()>128)throw invalid();result.put((String)item.getKey(),yamlValue(item.getValue(),depth+1));}return result;}
    if(value instanceof List){List<?> source=(List<?>)value;if(source.size()>64)throw invalid();JSONArray result=new JSONArray();for(Object item:source)result.put(yamlValue(item,depth+1));return result;}
    if(value instanceof String||value instanceof Number||value instanceof Boolean){scalarTree(value,depth);return value;}
    throw invalid();
  }
  /** Compose aliases as references; never construct unrelated subscription data. */
  static final class SelectedConstructor extends SafeConstructor {
    SelectedConstructor(LoaderOptions limits){super(limits);}
    Object selected(Node node){return constructDocument(node);}
  }
  static final class YamlLimit extends YAMLException {YamlLimit(){super("Subscription syntax budget exceeded");}}
  /** Bound allocation while composing, including scalar aliases that are not
   * counted by SnakeYAML's collection-alias limit. Only the first document is read. */
  static final class YamlSyntaxBudget implements Parser {
    final Parser parser;int nodes,aliases;
    YamlSyntaxBudget(Reader input,LoaderOptions limits){parser=new ParserImpl(new StreamReader(input),limits);}
    public boolean checkEvent(Event.ID id){return parser.checkEvent(id);}
    public Event peekEvent(){return parser.peekEvent();}
    public Event getEvent(){
      Event event=parser.getEvent();
      if(event!=null){
        if((event.is(Event.ID.Scalar)||event.is(Event.ID.SequenceStart)||event.is(Event.ID.MappingStart))&&++nodes>65536)throw new YamlLimit();
        if(event.is(Event.ID.Alias)&&++aliases>65536)throw new YamlLimit();
      }
      return event;
    }
  }
  static Failure yamlFailure(){return failure("订阅内容无法解析，请更新订阅后重试；原线路未改变。");}
  static Failure complexYaml(){return failure("订阅或所选节点结构过于复杂，请精简配置后重试；原线路未改变。");}
  static String yamlKey(Node node)throws IOException{
    if(!(node instanceof ScalarNode)||!Tag.STR.equals(node.getTag())&&!Tag.MERGE.equals(node.getTag()))throw yamlFailure();
    return ((ScalarNode)node).getValue();
  }
  static void uniqueYamlKeys(MappingNode node)throws IOException{
    Set<String> seen=new HashSet<>();
    for(NodeTuple field:node.getValue())if(!seen.add(yamlKey(field.getKeyNode())))throw failure("订阅存在重复字段，请更新订阅后重试；原线路未改变。");
  }
  /** YAML merge precedence: explicit values win; earlier sequence maps win.
   * Memoization avoids repeatedly walking shared defaults for every proxy. */
  static final class YamlLookup {
    final String key;int remaining=262144;
    final IdentityHashMap<MappingNode,Node> memo=new IdentityHashMap<>();
    final Set<Node> active=Collections.newSetFromMap(new IdentityHashMap<>());
    YamlLookup(String key){this.key=key;}
    Node find(MappingNode node)throws IOException{
      if(--remaining<0)throw complexYaml();
      if(memo.containsKey(node))return memo.get(node);
      if(!active.add(node))throw failure("所选节点包含循环引用，无法分享；原线路未改变。");
      try{
        if(active.size()>64)throw complexYaml();
        uniqueYamlKeys(node);Node direct=null;List<Node> merges=new ArrayList<>();
        for(NodeTuple field:node.getValue()){
          if(--remaining<0)throw complexYaml();
          if(Tag.MERGE.equals(field.getKeyNode().getTag()))merges.add(field.getValueNode());
          else if(key.equals(yamlKey(field.getKeyNode())))direct=field.getValueNode();
        }
        if(direct!=null){memo.put(node,direct);return direct;}
        Node inherited=null;
        for(Node merge:merges){
          if(merge instanceof MappingNode)inherited=find((MappingNode)merge);
          else if(merge instanceof SequenceNode){for(Node item:((SequenceNode)merge).getValue()){
            if(!(item instanceof MappingNode))throw yamlFailure();
            inherited=find((MappingNode)item);if(inherited!=null)break;
          }}else throw yamlFailure();
          if(inherited!=null)break;
        }
        memo.put(node,inherited);return inherited;
      }finally{active.remove(node);}
    }
  }
  /** Count expanded visits before SafeConstructor can flatten a merge graph.
   * The bound includes repeated aliases, including values later overridden. */
  static final class SelectedYamlBudget {
    int remaining=8192,textUnits;
    final Set<Node> active=Collections.newSetFromMap(new IdentityHashMap<>());
    void inspect(Node node,int depth)throws IOException{
      if(--remaining<0||depth>32)throw complexYaml();
      if(!active.add(node))throw failure("所选节点包含循环引用，无法分享；原线路未改变。");
      try{
        Tag tag=node.getTag();
        boolean mapping=node instanceof MappingNode&&Tag.MAP.equals(tag),sequence=node instanceof SequenceNode&&Tag.SEQ.equals(tag);
        boolean scalar=node instanceof ScalarNode&&(Tag.STR.equals(tag)||Tag.INT.equals(tag)||Tag.FLOAT.equals(tag)||Tag.BOOL.equals(tag)||Tag.NULL.equals(tag)||Tag.MERGE.equals(tag));
        if(!mapping&&!sequence&&!scalar)throw failure("所选节点包含不支持的数据类型，未生成分享配置；原线路未改变。");
        if(node instanceof MappingNode){
          MappingNode map=(MappingNode)node;uniqueYamlKeys(map);
          for(NodeTuple field:map.getValue()){inspect(field.getKeyNode(),depth+1);inspect(field.getValueNode(),depth+1);}
        }else if(node instanceof SequenceNode){for(Node item:((SequenceNode)node).getValue())inspect(item,depth+1);}
        else if(node instanceof ScalarNode){String value=((ScalarNode)node).getValue();textUnits+=value.length();if(value.length()>8192||textUnits>LIMIT)throw complexYaml();}
        else throw yamlFailure();
      }finally{active.remove(node);}
    }
  }
  /** Exactly one node, never its subscription address or other nodes. */
  static JSONObject extract(byte[] bytes,String prefixed,String role)throws Exception{
    if(bytes==null||bytes.length>16*1024*1024)throw failure("已保存的节点不可读取，请先更新订阅。");
    String prefix=NetworkCatalog.EXIT.equals(role)?"Exit|":"Entry|";if(prefixed==null||!prefixed.startsWith(prefix))throw invalid();String name=prefixed.substring(prefix.length());
    LoaderOptions limits=new LoaderOptions();limits.setAllowDuplicateKeys(false);limits.setMaxAliasesForCollections(65536);limits.setNestingDepthLimit(64);limits.setCodePointLimit(16*1024*1024);
    // Tags in ignored sections are syntax only. The selected graph is checked
    // against scalar/container tags before any object construction occurs.
    limits.setTagInspector(tag->true);SelectedConstructor constructor=new SelectedConstructor(limits);
    try{
      Composer documents=new Composer(new YamlSyntaxBudget(new StringReader(new String(bytes,StandardCharsets.UTF_8)),limits),new Resolver(),limits);
      Node raw=documents.checkNode()?documents.getNode():null;
      if(!(raw instanceof MappingNode))throw failure("此订阅缓存暂不支持分享，请使用 Clash / Mihomo YAML 节点。");
      uniqueYamlKeys((MappingNode)raw);Node proxies=new YamlLookup("proxies").find((MappingNode)raw);
      if(!(proxies instanceof SequenceNode))throw failure("此订阅缓存暂不支持分享，请使用 Clash / Mihomo YAML 节点。");
      MappingNode selected=null;YamlLookup names=new YamlLookup("name");
      for(Node candidate:((SequenceNode)proxies).getValue())if(candidate instanceof MappingNode){
        Node candidateName=names.find((MappingNode)candidate);
        if(candidateName instanceof ScalarNode&&name.equals(((ScalarNode)candidateName).getValue())){
          if(selected!=null)throw invalid();selected=(MappingNode)candidate;
        }
      }
      if(selected==null)throw failure("当前节点已变化，请重新选择后分享。");
      new SelectedYamlBudget().inspect(selected,0);
      JSONObject value=(JSONObject)yamlValue(constructor.selected(selected),0);
      if(value.opt("port") instanceof String&&value.optString("port").matches("[0-9]{1,5}"))value.put("port",Integer.parseInt(value.optString("port")));
      return node(value,NetworkCatalog.EXIT.equals(role));
    }catch(YamlLimit limit){throw complexYaml();}catch(YAMLException|NumberFormatException parse){throw yamlFailure();}catch(JSONException value){throw invalid();}
  }
}
