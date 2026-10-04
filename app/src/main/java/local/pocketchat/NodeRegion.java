package local.pocketchat;

import java.util.*;
import java.util.regex.Pattern;

/** Labels are hints from the subscription, never a verification of its exit IP. */
final class NodeRegion {
  static final Map<String,String> COUNTRIES=new LinkedHashMap<>();
  static final Map<String,String[]> HINTS=new LinkedHashMap<>();
  static {
    add("HK","中国香港","香港","hong kong");add("TW","中国台湾","台湾","台灣","taiwan","台北");add("MO","中国澳门","澳门","澳門","macau");
    add("JP","日本","日本","东京","東京","大阪","japan","tokyo","osaka");add("KR","韩国","韩国","韓國","首尔","首爾","korea","seoul");
    add("SG","新加坡","新加坡","singapore");add("US","美国","美国","美國","united states","洛杉矶","los angeles","硅谷","西雅图");
    add("GB","英国","英国","英國","united kingdom","london","伦敦");add("DE","德国","德国","德國","germany","frankfurt","法兰克福");
    add("FR","法国","法国","法國","france","paris","巴黎");add("CA","加拿大","加拿大","canada","toronto","多伦多");
    add("AU","澳大利亚","澳大利亚","澳洲","australia","sydney","悉尼");add("NL","荷兰","荷兰","荷蘭","netherlands","amsterdam");
    add("RU","俄罗斯","俄罗斯","俄羅斯","russia","moscow");add("IN","印度","印度","india");add("TH","泰国","泰国","泰國","thailand","bangkok");
    add("MY","马来西亚","马来西亚","malaysia");add("VN","越南","越南","vietnam");add("PH","菲律宾","菲律宾","philippines");
    add("ID","印度尼西亚","印尼","印度尼西亚","indonesia");add("IT","意大利","意大利","italy");add("ES","西班牙","西班牙","spain");
    add("CH","瑞士","瑞士","switzerland");add("SE","瑞典","瑞典","sweden");add("FI","芬兰","芬兰","finland");
    add("BR","巴西","巴西","brazil");add("TR","土耳其","土耳其","turkey");add("AE","阿联酋","阿联酋","迪拜","dubai");
    add("CN","中国大陆","中国","中國","大陆","大陸","china","北京","上海");
  }
  static void add(String code,String name,String... hints){COUNTRIES.put(code,name);HINTS.put(code,hints);}
  static String country(String code){String iso=code.toUpperCase(Locale.ROOT);if(COUNTRIES.containsKey(iso))return COUNTRIES.get(iso);if(!Arrays.asList(Locale.getISOCountries()).contains(iso))return "";return new Locale("",iso).getDisplayCountry(Locale.SIMPLIFIED_CHINESE);}
  static String identify(String name){
    if(name==null)return "";String text=name.toLowerCase(Locale.ROOT);Set<String> matches=new LinkedHashSet<>();
    int[] points=name.codePoints().toArray();for(int i=0;i+1<points.length;i++)if(points[i]>=0x1f1e6&&points[i]<=0x1f1ff&&points[i+1]>=0x1f1e6&&points[i+1]<=0x1f1ff){String code=""+(char)('A'+points[i]-0x1f1e6)+(char)('A'+points[i+1]-0x1f1e6);String value=country(code);if(!value.isEmpty())matches.add(value);i++;}
    if(matches.size()==1)return matches.iterator().next();if(matches.size()>1)return "";
    for(String code:HINTS.keySet()){
      if(Pattern.compile("(?i)(?<![a-z])"+code+"(?![a-z])").matcher(text).find())matches.add(country(code));
      for(String hint:HINTS.get(code))if(Pattern.compile(hint.matches("[a-z ]+")?"(?<![a-z])"+Pattern.quote(hint)+"(?![a-z])":Pattern.quote(hint)).matcher(text).find()){matches.add(country(code));break;}
    }
    // 香港 / 台湾 descriptions often also contain 中国; prefer the specific region.
    if(matches.contains("中国香港")||matches.contains("中国台湾")||matches.contains("中国澳门"))matches.remove("中国大陆");
    return matches.size()==1?matches.iterator().next():"";
  }
  static String label(String name){String region=identify(name);return region.isEmpty()||name.contains(region)?name:name+" · "+region;}
}
