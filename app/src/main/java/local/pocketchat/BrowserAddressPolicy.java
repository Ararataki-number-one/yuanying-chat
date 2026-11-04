package local.pocketchat;

import java.net.IDN;
import java.net.InetAddress;
import java.net.URI;
import java.net.URLEncoder;
import java.util.Locale;

/** Address-bar policy for the universal browser. Never resolves a hostname. */
final class BrowserAddressPolicy {
  private static final String HOME="https://chatgpt.com/";
  private BrowserAddressPolicy() {}
  static String home(){return HOME;}

  /** Unsafe explicit addresses fail visibly instead of becoming a search. */
  static String normalizeInput(String input){
    String value=input==null?"":input.trim();if(value.isEmpty())return HOME;
    if(value.length()>8192||hasControl(value))throw new IllegalArgumentException("地址或搜索内容过长，或包含不可见控制字符");
    if(value.startsWith("//"))return normalizeAddress("https:"+value);
    if(value.matches("(?i)^https?://.*"))return normalizeAddress(value);
    if(value.matches("(?i)^(?:site|filetype|ext|intitle|inurl|intext|allintitle|allinurl|allintext|related|cache|before|after):.*"))return search(value);
    if(value.matches("^[A-Za-z][A-Za-z0-9+.-]*:.*")&&!domainWithPort(value))throw new IllegalArgumentException("仅支持 HTTP 或 HTTPS 网页地址");
    if(!hasSpace(value)&&looksLikeAddress(value))return normalizeAddress("https://"+value);
    return search(value);
  }
  private static String search(String value){
    try{return "https://www.google.com/search?q="+URLEncoder.encode(value,"UTF-8");}
    catch(java.io.UnsupportedEncodingException impossible){throw new IllegalStateException(impossible);}
  }

  /** Applies equally to redirects and login pages; never limits an origin to ChatGPT. */
  static boolean allowed(String address){try{normalizeAddress(address);return true;}catch(IllegalArgumentException invalid){return false;}}

  private static boolean domainWithPort(String value){
    int colon=value.indexOf(':');if(colon<=0)return false;String before=value.substring(0,colon);
    return before.indexOf('.')>=0||localName(before);
  }
  private static boolean looksLikeAddress(String value){
    int end=value.length();for(char delimiter:new char[]{'/','?','#'}){int found=value.indexOf(delimiter);if(found>=0)end=Math.min(end,found);}
    String authority=value.substring(0,end),host=authority;int colon=host.indexOf(':');if(colon>=0)host=host.substring(0,colon);
    return authority.indexOf('.')>=0||authority.startsWith("[")||authority.indexOf(':')>=0||authority.indexOf('@')>=0||localName(host)||host.matches("(?i)(?:0x[0-9a-f]+|[0-9]+)");
  }
  private static String normalizeAddress(String address){
    if(address==null||address.isEmpty()||address.length()>8192||hasControl(address)||hasSpace(address)||address.indexOf('\\')>=0)throw invalid();
    final URI uri;try{uri=new URI(address);}catch(java.net.URISyntaxException bad){throw invalid();}
    String scheme=uri.getScheme();if(scheme==null||!(scheme.equalsIgnoreCase("http")||scheme.equalsIgnoreCase("https"))||uri.isOpaque())throw invalid();
    String authority=uri.getRawAuthority();if(authority==null||authority.isEmpty()||authority.indexOf('@')>=0||authority.indexOf('%')>=0)throw invalid();
    String host,tail="";boolean ipv6=authority.startsWith("[");
    if(ipv6){int close=authority.indexOf(']');if(close<=1)throw invalid();host=authority.substring(1,close);tail=authority.substring(close+1);if(!publicV6(host))throw privateAddress();host="["+host.toLowerCase(Locale.ROOT)+"]";}
    else{
      int colon=authority.indexOf(':');if(colon>=0){if(colon!=authority.lastIndexOf(':'))throw invalid();host=authority.substring(0,colon);tail=authority.substring(colon);}else host=authority;
      if(host.endsWith("."))host=host.substring(0,host.length()-1);
      try{host=IDN.toASCII(host,IDN.USE_STD3_ASCII_RULES).toLowerCase(Locale.ROOT);}catch(IllegalArgumentException bad){throw invalid();}
      if(host.isEmpty()||host.length()>253||host.startsWith(".")||host.endsWith(".")||host.contains(".."))throw invalid();
      if(localName(host)||!publicV4OrDomain(host))throw privateAddress();
    }
    String port="";if(!tail.isEmpty()){
      if(!tail.matches(":[0-9]{1,5}"))throw invalid();int number;try{number=Integer.parseInt(tail.substring(1));}catch(NumberFormatException bad){throw invalid();}
      if(number<1||number>65535)throw invalid();port=":"+number;
    }
    String path=uri.getRawPath();if(path==null||path.isEmpty())path="/";
    String normalized=scheme.toLowerCase(Locale.ROOT)+"://"+host+port+path+(uri.getRawQuery()==null?"":"?"+uri.getRawQuery())+(uri.getRawFragment()==null?"":"#"+uri.getRawFragment());
    try{return new URI(normalized).toASCIIString();}catch(java.net.URISyntaxException bad){throw invalid();}
  }
  private static boolean localName(String host){
    String value=host.toLowerCase(Locale.ROOT);while(value.endsWith("."))value=value.substring(0,value.length()-1);
    return value.equals("localhost")||value.endsWith(".localhost")||value.endsWith(".local")||value.endsWith(".lan")||value.endsWith(".internal")||value.equals("home.arpa")||value.endsWith(".home.arpa");
  }
  private static boolean publicV4OrDomain(String host){
    if(!host.matches("(?i)(?:0x[0-9a-f]+|[0-9]+)(?:\\.(?:0x[0-9a-f]+|[0-9]+)){0,3}")){
      // Chromium interprets a final numeric label as an IPv4 address. Refuse
      // malformed numeric hosts rather than disagreeing with that URL parser.
      String end=host.substring(host.lastIndexOf('.')+1);return host.indexOf('.')>=0&&!end.matches("(?i)(?:0x[0-9a-f]*|[0-9]+)");
    }
    try{
      String[] parts=host.split("\\.");long address=0;
      for(int i=0;i<parts.length;i++){
        String value=parts[i];int radix=value.toLowerCase(Locale.ROOT).startsWith("0x")?16:value.length()>1&&value.startsWith("0")?8:10;
        long number=Long.parseLong(radix==16?value.substring(2):value,radix);long maximum=i==parts.length-1?(1L<<(8*(5-parts.length)))-1:255;
        if(number<0||number>maximum)return false;address=i==parts.length-1?(address<<(8*(5-parts.length)))|number:(address<<8)|number;
      }
      return publicV4(address);
    }catch(NumberFormatException malformed){return false;}
  }
  private static boolean publicV4(long address){
    int a=(int)(address>>>24)&255,b=(int)(address>>>16)&255,c=(int)(address>>>8)&255;
    return !(a==0||a==10||a==127||a>=224||a==100&&b>=64&&b<=127||a==169&&b==254||a==172&&b>=16&&b<=31||a==192&&b==168||a==198&&(b==18||b==19)||a==192&&b==0&&(c==0||c==2)||a==198&&b==51&&c==100||a==203&&b==0&&c==113);
  }
  private static boolean publicV6(String host){
    if(host.indexOf(':')<0||!host.matches("[0-9A-Fa-f:.]+"))return false;
    try{
      // A colon and this restricted alphabet guarantee a numeric literal;
      // InetAddress cannot send a DNS lookup for these inputs.
      InetAddress address=InetAddress.getByName(host);byte[] bytes=address.getAddress();
      if(bytes.length==4){long v4=0;for(byte value:bytes)v4=(v4<<8)|(value&255);return publicV4(v4);}
      if(address.isAnyLocalAddress()||address.isLoopbackAddress()||address.isLinkLocalAddress()||address.isSiteLocalAddress()||address.isMulticastAddress()||(bytes[0]&254)==252)return false;
      boolean zeroPrefix=true;for(int i=0;i<12;i++)zeroPrefix&=bytes[i]==0;if(zeroPrefix)return false;
      if((bytes[0]&255)==0x20&&(bytes[1]&255)==1&&(bytes[2]&255)==0x0d&&(bytes[3]&255)==0xb8)return false;
      if((bytes[0]&255)==0x20&&(bytes[1]&255)==2){long v4=0;for(int i=2;i<6;i++)v4=(v4<<8)|(bytes[i]&255);if(!publicV4(v4))return false;}
      return true;
    }catch(java.net.UnknownHostException malformed){return false;}
  }
  private static boolean hasControl(String value){for(int i=0;i<value.length();i++){char c=value.charAt(i);if(Character.isISOControl(c)||c=='\u202a'||c=='\u202b'||c=='\u202c'||c=='\u202d'||c=='\u202e'||c>='\u2066'&&c<='\u2069')return true;}return false;}
  private static boolean hasSpace(String value){for(int i=0;i<value.length();i++)if(Character.isWhitespace(value.charAt(i))||Character.isSpaceChar(value.charAt(i)))return true;return false;}
  private static IllegalArgumentException invalid(){return new IllegalArgumentException("请输入有效的公共 HTTP 或 HTTPS 网页地址");}
  private static IllegalArgumentException privateAddress(){return new IllegalArgumentException("暂不支持本机、局域网或保留地址");}
}
