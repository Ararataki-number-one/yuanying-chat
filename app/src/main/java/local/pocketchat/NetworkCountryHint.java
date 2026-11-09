package local.pocketchat;

import java.util.*;
import java.util.regex.Pattern;

/** Offline presentation hints from names/labels, never a claim about an exit IP. */
final class NetworkCountryHint {
  private static final Map<String,String> NAMES=new LinkedHashMap<>(),CODES=new HashMap<>();
  private static final Map<String,String> CACHE=new LinkedHashMap<String,String>(128,.75f,true){
    @Override protected boolean removeEldestEntry(Map.Entry<String,String> entry){return size()>256;}
  };
  private static final Pattern HOST=Pattern.compile("(?i)(?:[a-z0-9-]+\\.)+[a-z]{2,63}(?:\\b|$)|(?:[0-9]{1,3}\\.){3}[0-9]{1,3}");
  static {
    for(String code:Locale.getISOCountries()){
      String name=NodeRegion.country(code);if(name.isEmpty())continue;
      NAMES.put(code,name);CODES.put(name.toLowerCase(Locale.ROOT),code);
      Locale country=new Locale("",code);
      CODES.put(country.getDisplayCountry(Locale.ENGLISH).toLowerCase(Locale.ROOT),code);
      CODES.put(country.getDisplayCountry(Locale.SIMPLIFIED_CHINESE).toLowerCase(Locale.ROOT),code);
    }
  }
  private NetworkCountryHint(){}

  static String code(String label){
    if(label==null)return "";String value=label.trim();
    if(value.startsWith("Entry|"))value=value.substring(6).trim();
    else if(value.startsWith("Exit|"))value=value.substring(5).trim();
    if(value.isEmpty()||value.length()>512)return "";
    synchronized(CACHE){String cached=CACHE.get(value);if(cached!=null)return cached;}
    String result=resolve(value);synchronized(CACHE){CACHE.put(value,result);}return result;
  }

  private static String resolve(String value){
    // Hostnames and endpoints have no geographic authority. In particular,
    // a country-code TLD must not turn an otherwise unknown node into a flag.
    if(value.indexOf(':')>=0||value.indexOf('/')>=0||value.indexOf('\\')>=0||value.indexOf('@')>=0||HOST.matcher(value).find())return "";
    String iso=value.toUpperCase(Locale.ROOT);if(NAMES.containsKey(iso))return iso;
    String exact=CODES.get(value.toLowerCase(Locale.ROOT));if(exact!=null)return exact;
    String name=NodeRegion.identify(value),code=CODES.get(name.toLowerCase(Locale.ROOT));
    if(code==null)return "";
    // Do not silently prefer a flag over a contradictory readable country.
    StringBuilder text=new StringBuilder();boolean flag=false;
    for(int point:value.codePoints().toArray()){
      if(point>=0x1f1e6&&point<=0x1f1ff){flag=true;continue;}text.appendCodePoint(point);
    }
    if(flag){
      String readable=text.toString(),other=NodeRegion.identify(readable);
      if(!other.isEmpty()&&!other.equals(name)||other.isEmpty()&&hasCountryText(readable))return "";
    }
    return code;
  }

  private static boolean hasCountryText(String text){
    // An empty identify() result can mean conflicting hints, not just no hint.
    // Reuse its existing vocabulary only to reject that ambiguous flag case.
    for(Map.Entry<String,String[]> item:NodeRegion.HINTS.entrySet()){
      if(Pattern.compile("(?i)(?<![a-z])"+item.getKey()+"(?![a-z])").matcher(text).find())return true;
      for(String hint:item.getValue()){
        String expression=hint.matches("[a-z ]+")?"(?i)(?<![a-z])"+Pattern.quote(hint)+"(?![a-z])":Pattern.quote(hint);
        if(Pattern.compile(expression).matcher(text).find())return true;
      }
    }
    return false;
  }

  static String code(String name,String region){
    String named=code(name),declared=code(region);
    return !named.isEmpty()&&!declared.isEmpty()&&!named.equals(declared)?"":declared.isEmpty()?named:declared;
  }

  /** A collection gets one flag only when every actual node has the same hint. */
  static String commonCode(Collection<String> labels){
    if(labels==null||labels.isEmpty())return "";String common="";
    for(String label:labels){String next=code(label);if(next.isEmpty()||!common.isEmpty()&&!common.equals(next))return "";common=next;}
    return common;
  }

  static String country(String code){return code==null?"":NAMES.getOrDefault(code.toUpperCase(Locale.ROOT),"");}
  static String flag(String code){
    if(country(code).isEmpty())return "";String iso=code.toUpperCase(Locale.ROOT);
    return new String(Character.toChars(0x1f1e6+iso.charAt(0)-'A'))+new String(Character.toChars(0x1f1e6+iso.charAt(1)-'A'));
  }
}
