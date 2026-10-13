package local.pocketchat;

import java.io.IOException;
import java.net.URI;
import java.net.URLDecoder;
import java.nio.ByteBuffer;
import java.nio.charset.CharacterCodingException;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;

/** Deliberately bounded SOCKS5 import, not a general YAML interpreter. No errors include source text. */
final class ExitSubscriptionParser {
  static final int MAX_BYTES=1024*1024,MAX_NODES=256,MAX_LINES=8192;
  static final class Node {
    final String key,name,region,host,user,password,configRevision,credentialRevision;final int port;
    Node(Map<String,String> fields)throws IOException{
      for(String key:fields.keySet())if(!Arrays.asList("name","type","server","port","username","password","udp","tls","region","x-pocket-id").contains(key))throw error("出口包含不支持的字段");
      if(!"socks5".equals(fields.get("type")))throw error("出口订阅首期仅支持 SOCKS5");
      if(fields.containsKey("udp")&&!Arrays.asList("true","false").contains(fields.get("udp")))throw error("udp 应为 true 或 false");
      if(fields.containsKey("tls")&&!"false".equals(fields.get("tls")))throw error("暂不支持 TLS SOCKS5 出口");
      name=clean(fields.get("name"),256,"出口名称");if(name.isEmpty())throw error("出口名称不能为空");
      host=clean(fields.get("server"),255,"服务器");if(host.isEmpty()||!host.matches("[A-Za-z0-9._:\\[\\]-]+"))throw error("服务器应为域名或 IP");
      String rawPort=fields.get("port");if(rawPort==null||!rawPort.matches("[0-9]{1,5}"))throw error("端口应为 1–65535");int value;try{value=Integer.parseInt(rawPort);}catch(NumberFormatException bad){throw error("端口应为 1–65535");}if(value<1||value>65535)throw error("端口应为 1–65535");port=value;
      user=clean(fields.get("username"),255,"用户名");password=clean(fields.get("password"),255,"密码");if(user.getBytes(StandardCharsets.UTF_8).length>255||password.getBytes(StandardCharsets.UTF_8).length>255)throw error("SOCKS5 凭据超过 255 字节");
      if(user.isEmpty()&&!password.isEmpty())throw error("密码需要同时提供用户名");
      region=clean(fields.get("region"),128,"地区");String explicit=clean(fields.get("x-pocket-id"),128,"节点 ID");
      key=explicit.isEmpty()?digest("endpoint",host.toLowerCase(Locale.ROOT),String.valueOf(port),user):digest("explicit",explicit);
      credentialRevision=digest("credentials",user,password);configRevision=digest("route",host.toLowerCase(Locale.ROOT),String.valueOf(port),user,password);
    }
  }
  static IOException error(String message){return new IOException(message+"；旧出口配置已保留");}
  static String clean(String value,int limit,String field)throws IOException{String s=value==null?"":value;if(s.length()>limit)throw error(field+"过长");for(int i=0;i<s.length();i++)if(Character.isISOControl(s.charAt(i)))throw error(field+"包含控制字符");return s;}
  static String digest(String... fields){try{MessageDigest d=MessageDigest.getInstance("SHA-256");for(String f:fields){byte[] bytes=f.getBytes(StandardCharsets.UTF_8);d.update(ByteBuffer.allocate(4).putInt(bytes.length).array());d.update(bytes);}StringBuilder out=new StringBuilder();for(byte b:d.digest())out.append(String.format(Locale.ROOT,"%02x",b&255));return out.toString();}catch(Exception unavailable){throw new IllegalStateException("SHA-256 unavailable");}}
  static List<Node> parse(byte[] bytes)throws IOException{
    if(bytes==null||bytes.length==0||bytes.length>MAX_BYTES)throw error("出口订阅为空或超过 1 MiB");String input;try{input=StandardCharsets.UTF_8.newDecoder().onMalformedInput(CodingErrorAction.REPORT).onUnmappableCharacter(CodingErrorAction.REPORT).decode(ByteBuffer.wrap(bytes)).toString();}catch(CharacterCodingException malformed){throw error("出口订阅必须为 UTF-8");}
    if(input.startsWith("\ufeff"))input=input.substring(1);List<Node> nodes=input.trim().startsWith("socks5://")?uris(input):yaml(input);
    if(nodes.isEmpty())throw error("没有可用的 SOCKS5 出口");if(nodes.size()>MAX_NODES)throw error("出口数量超过 256");Set<String> identities=new HashSet<>();for(Node n:nodes)if(!identities.add(n.key))throw error("出口节点 ID 重复，请使用不同的 x-pocket-id");return Collections.unmodifiableList(nodes);
  }
  static List<Node> uris(String input)throws IOException{
    List<Node> nodes=new ArrayList<>();String[] lines=input.split("\\r?\\n",-1);if(lines.length>MAX_LINES)throw error("出口订阅行数过多");for(String line:lines){line=line.trim();if(line.isEmpty()||line.startsWith("#"))continue;try{URI uri=new URI(line);if(!"socks5".equals(uri.getScheme())||uri.getHost()==null||uri.getPort()<1||uri.getRawQuery()!=null||!(uri.getPath().isEmpty()||"/".equals(uri.getPath())))throw error("SOCKS5 URI 格式不支持");
      Map<String,String> fields=new LinkedHashMap<>();fields.put("type","socks5");String host=uri.getHost();if(host.startsWith("[")&&host.endsWith("]"))host=host.substring(1,host.length()-1);fields.put("server",host);fields.put("port",String.valueOf(uri.getPort()));String credentials=uri.getRawUserInfo();if(credentials!=null){int colon=credentials.indexOf(':');fields.put("username",decode(colon<0?credentials:credentials.substring(0,colon)));fields.put("password",colon<0?"":decode(credentials.substring(colon+1)));}fields.put("name",uri.getRawFragment()==null?host:decode(uri.getRawFragment()));nodes.add(new Node(fields));if(nodes.size()>MAX_NODES)throw error("出口数量超过 256");
    }catch(IOException known){throw known;}catch(Exception bad){throw error("SOCKS5 URI 格式不支持");}}return nodes;
  }
  static String decode(String value)throws Exception{String decoded=URLDecoder.decode(value.replace("+","%2B"),"UTF-8");if(decoded.indexOf('\ufffd')>=0)throw error("SOCKS5 URI 编码必须为 UTF-8");return decoded;}
  static List<Node> yaml(String input)throws IOException{
    List<Node> nodes=new ArrayList<>();String[] lines=input.split("\\r?\\n",-1);if(lines.length>MAX_LINES)throw error("出口订阅行数过多");boolean section=false;int itemIndent=-1,fieldIndent=-1;Map<String,String> current=null;
    for(String raw:lines){if(raw.indexOf('\t')>=0)throw error("YAML 不支持制表符缩进");int indent=0;while(indent<raw.length()&&raw.charAt(indent)==' ')indent++;String line=comment(raw.substring(indent)).trim();if(line.isEmpty())continue;
      if(indent==0&&"proxies:".equals(line)){if(section)throw error("proxies 重复");section=true;continue;}
      if(!section)throw error("YAML 应为 proxies 节点列表");
      boolean item=line.startsWith("- ");if(item){if(itemIndent<0)itemIndent=indent;if(indent!=itemIndent)throw error("YAML 节点缩进不一致");if(current!=null)nodes.add(new Node(current));current=new LinkedHashMap<>();fieldIndent=-1;String rest=line.substring(2).trim();if(rest.startsWith("{")){flow(rest,current);nodes.add(new Node(current));current=null;}else pair(rest,current);}
      else{if(current==null||indent<=itemIndent)throw error("仅支持 proxies 内的平面 SOCKS5 字段");if(fieldIndent<0)fieldIndent=indent;if(indent!=fieldIndent)throw error("YAML 不支持嵌套字段");pair(line,current);}
      if(nodes.size()>MAX_NODES)throw error("出口数量超过 256");
    }
    if(current!=null)nodes.add(new Node(current));return nodes;
  }
  static String comment(String line)throws IOException{char quote=0;boolean escaped=false;for(int i=0;i<line.length();i++){char ch=line.charAt(i);if(quote=='"'&&escaped){escaped=false;continue;}if(quote=='"'&&ch=='\\'){escaped=true;continue;}if(quote!=0){if(ch==quote){if(quote=='\''&&i+1<line.length()&&line.charAt(i+1)=='\''){i++;continue;}quote=0;}continue;}if(ch=='\''||ch=='"')quote=ch;else if(ch=='#'&&(i==0||Character.isWhitespace(line.charAt(i-1))))return line.substring(0,i);}if(quote!=0)throw error("YAML 引号未闭合");return line;}
  static void flow(String line,Map<String,String> fields)throws IOException{if(!line.endsWith("}"))throw error("YAML 流式节点应在同一行闭合");String body=line.substring(1,line.length()-1);int start=0;char quote=0;boolean escaped=false;for(int i=0;i<body.length();i++){char ch=body.charAt(i);if(quote=='"'&&escaped){escaped=false;continue;}if(quote=='"'&&ch=='\\'){escaped=true;continue;}if(quote!=0){if(ch==quote){if(quote=='\''&&i+1<body.length()&&body.charAt(i+1)=='\''){i++;continue;}quote=0;}continue;}if(ch=='\''||ch=='"')quote=ch;else if(ch==','){pair(body.substring(start,i).trim(),fields);start=i+1;}else if(ch=='{'||ch=='}'||ch=='['||ch==']')throw error("YAML 不支持嵌套集合");}if(quote!=0)throw error("YAML 引号未闭合");pair(body.substring(start).trim(),fields);}
  static void pair(String text,Map<String,String> fields)throws IOException{int colon=text.indexOf(':');if(colon<1)throw error("YAML 字段格式不支持");String key=text.substring(0,colon).trim();if(!key.matches("[a-z][a-z0-9-]*")||fields.containsKey(key))throw error("YAML 字段重复或格式不支持");String rest=text.substring(colon+1);if(!rest.isEmpty()&&!Character.isWhitespace(rest.charAt(0)))throw error("YAML 字段冒号后需要空格");String raw=rest.trim();if(!raw.isEmpty()&&raw.charAt(0)!='\''&&raw.charAt(0)!='"'&&!Arrays.asList("port","udp","tls").contains(key)&&(raw.matches("(?i)(null|~|true|false|yes|no|on|off|[+-]?[.]?(inf|nan)|[+-]?0[xob][0-9a-f]+)")||raw.matches("[+-]?([0-9]+([.][0-9]*)?|[.][0-9]+)([eE][+-]?[0-9]+)?")||raw.matches("[0-9]{4}-[0-9]{2}-[0-9]{2}.*")))throw error("YAML 文本字段的特殊值需要引号");fields.put(key,scalar(raw));}
  static String scalar(String s)throws IOException{
    if(s.length()>2048)throw error("YAML 字段过长");if(s.isEmpty())return "";
    char q=s.charAt(0);if(q=='\''||q=='"'){if(s.length()<2||s.charAt(s.length()-1)!=q)throw error("YAML 引号未闭合");String body=s.substring(1,s.length()-1);if(q=='\''){StringBuilder out=new StringBuilder();for(int i=0;i<body.length();i++){char ch=body.charAt(i);if(ch=='\''){if(i+1>=body.length()||body.charAt(i+1)!='\'')throw error("YAML 引号格式不支持");i++;}out.append(ch);}return out.toString();}StringBuilder out=new StringBuilder();for(int i=0;i<body.length();i++){char ch=body.charAt(i);if(ch=='"')throw error("YAML 引号格式不支持");if(ch=='\\'){if(++i>=body.length())throw error("YAML 转义格式不支持");char e=body.charAt(i);if(e=='"'||e=='\\'||e=='/')out.append(e);else throw error("YAML 转义仅支持引号、斜杠和反斜杠");}else out.append(ch);}return out.toString();}
    if("&*!|>{[%,@`".indexOf(q)>=0||s.startsWith("---")||s.startsWith("...")||s.contains(": ")||s.contains(" #")||s.indexOf('{')>=0||s.indexOf('}')>=0||s.indexOf('[')>=0||s.indexOf(']')>=0||s.indexOf('"')>=0||s.indexOf('\'')>=0||s.indexOf(',')>=0)throw error("YAML 标记、集合和多行值不支持");return s;
  }
}
