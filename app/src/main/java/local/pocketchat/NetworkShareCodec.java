package local.pocketchat;

import org.json.*;
import org.yaml.snakeyaml.LoaderOptions;
import org.yaml.snakeyaml.composer.Composer;
import org.yaml.snakeyaml.constructor.SafeConstructor;
import org.yaml.snakeyaml.constructor.AbstractConstruct;
import java.math.BigInteger;
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
  static class Failure extends IOException { Failure(String message){super(message);} }
  static final class BudgetFailure extends Failure {BudgetFailure(String message){super(message);}}
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
  static JSONObject node(JSONObject value,boolean exit)throws Exception{return NetworkShareSchema.node(value,exit);}
  static final class Bundle {
    final String name,kind;final JSONObject entry,exit;
    Bundle(String name,JSONObject entry,JSONObject exit){this.name=name;this.entry=entry;this.exit=exit;kind=entry!=null&&exit!=null?"route":entry!=null?"entry":"exit";}
    int schemaVersion(){return NetworkShareJson.requiresExactNumbers(entry)||NetworkShareJson.requiresExactNumbers(exit)?2:1;}
    String encode()throws Exception{return NetworkShareJson.encode(J.obj("format","pocketchat-network","schemaVersion",schemaVersion(),"kind",kind,"name",name,"entry",entry,"exit",exit),LIMIT);}
    String summary(){return (entry==null?"":entry.optString("name"))+(entry!=null&&exit!=null?" → ":"")+(exit==null?"":exit.optString("name"))+" → ChatGPT";}
  }
  static Bundle decode(String text)throws Exception{
    if(text==null||text.getBytes(StandardCharsets.UTF_8).length>LIMIT)throw invalid();
    int depth=0;boolean quote=false,escape=false;for(int i=0;i<text.length();i++){char ch=text.charAt(i);if(quote){if(escape)escape=false;else if(ch=='\\')escape=true;else if(ch=='"')quote=false;}else if(ch=='"')quote=true;else if(ch=='{'||ch=='['){if(++depth>12)throw invalid();}else if(ch=='}'||ch==']'){if(--depth<0)throw invalid();}}
    if(depth!=0||quote)throw invalid();Object raw;try{raw=NetworkShareJson.decode(text,LIMIT);}catch(Exception malformed){throw invalid();}if(!(raw instanceof JSONObject))throw invalid();JSONObject o=(JSONObject)raw;
    keys(o,set("format schemaVersion kind name entry exit"));if(!"pocketchat-network".equals(o.optString("format"))||!(o.opt("schemaVersion") instanceof Number)||(o.getDouble("schemaVersion")!=1&&o.getDouble("schemaVersion")!=2))throw new IOException("此分享版本不支持，请更新应用或重新分享。");
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
  static byte[] provider(JSONObject node){try{return yamlJson(NetworkShareJson.encode(J.obj("proxies",J.arr(canonical(node))),LIMIT)).getBytes(StandardCharsets.UTF_8);}catch(Exception e){throw new IllegalArgumentException("节点无法编码");}}
  static JSONObject manual(JSONObject row)throws Exception{String name=row.optString("name");if(name.trim().isEmpty())name=row.optString("host");return node(J.obj("name",name,"type","socks5","server",row.optString("host"),"port",row.optInt("port"),"username",row.optString("user"),"password",row.optString("password")),true);}
  static Object yamlValue(Object value,int depth)throws Exception{
    if(depth>7)throw invalid();
    if(value instanceof Map){Map<?,?> source=(Map<?,?>)value;if(source.size()>48)throw invalid();JSONObject result=new JSONObject();for(Map.Entry<?,?> item:source.entrySet()){if(!(item.getKey() instanceof String)||((String)item.getKey()).length()>128)throw invalid();result.put((String)item.getKey(),yamlValue(item.getValue(),depth+1));}return result;}
    if(value instanceof List){List<?> source=(List<?>)value;if(source.size()>64)throw invalid();JSONArray result=new JSONArray();for(Object item:source)result.put(yamlValue(item,depth+1));return result;}
    if(value instanceof String||value instanceof Number||value instanceof Boolean){scalarTree(value,depth);return value;}
    throw invalid();
  }
  /** Compose aliases as references; never construct unrelated subscription data. */
  static final class NativeResolver extends Resolver {
    static final java.util.regex.Pattern FLOAT=java.util.regex.Pattern.compile("[-+]?(?:[0-9]+(?:\\.[0-9]*)?|\\.[0-9]+)(?:[eE][-+]?[0-9]+)?");
    @Override public Tag resolve(NodeId kind,String value,boolean implicit){
      if(kind!=NodeId.scalar||!implicit)return super.resolve(kind,value,implicit);
      if(value.equals("true")||value.equals("True")||value.equals("TRUE")||value.equals("false")||value.equals("False")||value.equals("FALSE"))return Tag.BOOL;
      if(value.isEmpty()||value.equals("~")||value.equals("null")||value.equals("Null")||value.equals("NULL"))return Tag.NULL;
      if(value.equals("<<"))return Tag.MERGE;
      String numeric=value.replace("_","");
      try{BigInteger number=NetworkShareSchema.parseInteger(numeric);if(number.compareTo(BigInteger.ONE.shiftLeft(63).negate())>=0&&number.compareTo(BigInteger.ONE.shiftLeft(64).subtract(BigInteger.ONE))<=0)return Tag.INT;}catch(IOException ignored){}
      if(FLOAT.matcher(numeric).matches()||numeric.matches("[-+]?[.](?:inf|Inf|INF)|[.](?:nan|NaN|NAN)"))return Tag.FLOAT;
      // yaml.v3 does not implicitly resolve YAML 1.1 yes/no/on/off or sexagesimal numbers.
      Tag old=super.resolve(kind,value,implicit);return Tag.TIMESTAMP.equals(old)?old:Tag.STR;
    }
  }
  static final class SelectedConstructor extends SafeConstructor {
    SelectedConstructor(LoaderOptions limits){super(limits);
      yamlConstructors.put(Tag.BOOL,new AbstractConstruct(){public Object construct(Node raw){String text=((ScalarNode)raw).getValue();if(text.equals("true")||text.equals("True")||text.equals("TRUE"))return true;if(text.equals("false")||text.equals("False")||text.equals("FALSE"))return false;throw new YAMLException("Invalid boolean scalar");}});
      yamlConstructors.put(Tag.INT,new AbstractConstruct(){public Object construct(Node raw){try{BigInteger n=NetworkShareSchema.parseInteger(((ScalarNode)raw).getValue().replace("_",""));return n.bitLength()<63?n.longValue():n;}catch(IOException invalid){throw new YAMLException("Invalid numeric scalar");}}});
      yamlConstructors.put(Tag.FLOAT,new AbstractConstruct(){public Object construct(Node raw){String text=((ScalarNode)raw).getValue().replace("_","");if(!NativeResolver.FLOAT.matcher(text).matches())throw new YAMLException("Invalid numeric scalar");try{double n=Double.parseDouble(text);if(!Double.isFinite(n))throw new NumberFormatException();return n;}catch(NumberFormatException invalid){throw new YAMLException("Invalid numeric scalar");}}});
    }
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
  static Failure complexYaml(){return new BudgetFailure("订阅或所选节点结构过于复杂，请精简配置后重试；原线路未改变。");}
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
  static final class Source {
    final Map<String,MappingNode> byName=new HashMap<>();final Set<String> duplicates=new HashSet<>();final SelectedConstructor constructor;int remaining=262144;
    static Node directName(MappingNode node)throws IOException{
      Node found=null;for(NodeTuple field:node.getValue()){Node key=field.getKeyNode();if(key instanceof ScalarNode&&Tag.STR.equals(key.getTag())&&"name".equals(((ScalarNode)key).getValue())){if(found!=null)throw yamlFailure();found=field.getValueNode();}}return found;
    }
    Source(byte[] bytes)throws Exception {
      if(bytes==null||bytes.length>16*1024*1024)throw failure("已保存的节点不可读取，请先更新订阅。");
      LoaderOptions limits=new LoaderOptions();limits.setAllowDuplicateKeys(false);limits.setMaxAliasesForCollections(65536);limits.setNestingDepthLimit(64);limits.setCodePointLimit(16*1024*1024);limits.setTagInspector(tag->true);constructor=new SelectedConstructor(limits);
      Composer documents=new Composer(new YamlSyntaxBudget(new StringReader(new String(bytes,StandardCharsets.UTF_8)),limits),new NativeResolver(),limits);
      Node raw=documents.checkNode()?documents.getNode():null;
      if(!(raw instanceof MappingNode))throw failure("此来源暂不支持独立分享；请使用 Clash / Mihomo YAML 节点。");
      uniqueYamlKeys((MappingNode)raw);Node proxies=new YamlLookup("proxies").find((MappingNode)raw);
      if(!(proxies instanceof SequenceNode))throw failure("此来源暂不支持独立分享；请使用 Clash / Mihomo YAML 节点。");
      YamlLookup names=new YamlLookup("name");for(Node candidate:((SequenceNode)proxies).getValue())if(candidate instanceof MappingNode){try{Node name=directName((MappingNode)candidate);if(name==null)name=names.find((MappingNode)candidate);if(name instanceof ScalarNode&&Tag.STR.equals(name.getTag())){String key=((ScalarNode)name).getValue();if(byName.put(key,(MappingNode)candidate)!=null)duplicates.add(key);}}catch(IOException unsupportedName){/* One unrelated malformed name graph cannot suppress another native-selected node. */}}
    }
    JSONObject select(String prefixed,String role)throws Exception {
      if(remaining<=0)throw complexYaml();
      String prefix=NetworkCatalog.EXIT.equals(role)?"Exit|":"Entry|";if(prefixed==null||!prefixed.startsWith(prefix))throw invalid();String name=prefixed.substring(prefix.length());
      if(duplicates.contains(name))throw invalid();MappingNode selected=byName.get(name);if(selected==null)throw failure("当前节点已变化，请重新选择后分享。");
      SelectedYamlBudget budget=new SelectedYamlBudget();int allowance=Math.min(remaining,budget.remaining);budget.remaining=allowance;
      try{budget.inspect(selected,0);return node((JSONObject)yamlValue(constructor.selected(selected),0),NetworkCatalog.EXIT.equals(role));}
      // Rejected nodes have spent visits too; optional indexing must account for them.
      finally{remaining-=allowance-budget.remaining;}
    }
  }
  /** Exactly one node, never its subscription address or other nodes. */
  static JSONObject extract(byte[] bytes,String prefixed,String role)throws Exception{
    try{return new Source(bytes).select(prefixed,role);}
    catch(YamlLimit limit){throw complexYaml();}catch(YAMLException|NumberFormatException parse){throw yamlFailure();}catch(JSONException value){throw invalid();}
  }
  /** Called once on the subscription parser worker. Candidates are untrusted until
   * the share UI reparses them with the actual native fingerprint implementation. */
  static JSONArray candidates(byte[] bytes,String role,JSONArray metadata){
    JSONArray out=new JSONArray();Source source=null;String availability="candidate",hash=bytes==null?"":NetworkShareSnapshot.hash(bytes);
    try{source=new Source(bytes);}catch(Exception unavailable){availability=unavailable instanceof BudgetFailure||unavailable instanceof YamlLimit?"budget":"unsupported-format";}
    int total=0;for(int i=0;i<metadata.length();i++){JSONObject detail=metadata.optJSONObject(i);if(detail==null)continue;JSONObject row=J.parse(detail.toString());String status=availability;
      if(source!=null){try{if(i>=4096||total>NetworkShareSnapshot.LIMIT)throw complexYaml();JSONObject candidate=source.select(row.optString("name"),role);total+=candidate.toString().length()*2;row.put("shareCandidate",candidate);row.put("shareSourceHash",hash);row.put("shareVersion",NetworkShareSnapshot.VERSION);}catch(Exception unavailable){status=unavailable instanceof BudgetFailure?"budget":"unsupported-node";}}
      try{row.put("shareAvailability",status);}catch(JSONException impossible){throw new IllegalStateException(impossible);}out.put(row);
    }return out;
  }
}
