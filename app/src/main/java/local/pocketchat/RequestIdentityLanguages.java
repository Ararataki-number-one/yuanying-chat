package local.pocketchat;

import org.json.*;
import java.util.*;

/** Bounded language observations. A difference is not a fingerprint leak verdict. */
final class RequestIdentityLanguages {
  static final int MAX_HEADER=1024,MAX_RANGES=16,MAX_JS_LANGUAGES=8;
  static final class Range {
    final String tag;final int quality,index;
    Range(String tag,int quality,int index){this.tag=tag;this.quality=quality;this.index=index;}
  }
  static final class Parsed {
    final List<Range> values=new ArrayList<>();String reason="";boolean wildcard;
    boolean valid(){return reason.isEmpty();}
    List<Range> effective(){List<Range> out=new ArrayList<>();for(Range range:values)if(range.quality>0&&!range.tag.equals("*"))out.add(range);Collections.sort(out,(a,b)->a.quality==b.quality?Integer.compare(a.index,b.index):Integer.compare(b.quality,a.quality));return out;}
    JSONArray tags(){JSONArray out=new JSONArray();for(Range range:effective())out.put(range.tag);return out;}
    JSONArray ranges(){JSONArray out=new JSONArray();for(Range range:values)out.put(J.obj("language",range.tag,"qualityThousandths",range.quality,"wireIndex",range.index,"excluded",range.quality==0));return out;}
    JSONObject observation(){return J.obj("valid",valid(),"reason",reason,"ranges",ranges(),"effectiveLanguages",tags(),"wildcard",wildcard,"weightSource","HTTP Accept-Language only; JavaScript exposes no q weights");}
  }
  static String tag(Object value){
    if(!(value instanceof String))return "";String raw=(String)value,text=raw.trim();if(!raw.equals(text))return "";
    return text.length()<=128&&text.matches("[A-Za-z]{1,8}(?:-[A-Za-z0-9]{1,8})*")?text.toLowerCase(Locale.ROOT):"";
  }
  static Parsed parse(String header){
    Parsed out=new Parsed();
    if(header==null||header.isEmpty()){out.reason="missing-http-language";return out;}
    if(header.length()>MAX_HEADER){out.reason="http-language-too-large";return out;}
    for(int i=0;i<header.length();i++){char value=header.charAt(i);if(value<32&&value!='\t'||value==127){out.reason="invalid-http-language-character";return out;}}
    String[] parts=header.split(",",-1);if(parts.length>MAX_RANGES){out.reason="too-many-http-language-ranges";return out;}
    Set<String> seen=new HashSet<>();
    for(int i=0;i<parts.length;i++){
      String[] fields=parts[i].trim().split(";",-1);String range=fields[0].trim(),normalized="*".equals(range)?"*":tag(range);
      if(normalized.isEmpty()||fields.length>2){out.reason="invalid-http-language-range";return out;}
      if(!seen.add(normalized)){out.reason="duplicate-http-language-range";return out;}
      int quality=1000;
      if(fields.length==2){
        String weight=fields[1].trim();if(!weight.matches("(?i)q\\s*=\\s*(?:0(?:\\.[0-9]{0,3})?|1(?:\\.0{0,3})?)")){out.reason="invalid-http-language-weight";return out;}
        String value=weight.substring(weight.indexOf('=')+1).trim();
        if(value.charAt(0)=='0'){String fraction=value.length()>2?value.substring(2):"";quality=Integer.parseInt((fraction+"000").substring(0,3));}
      }
      if(normalized.equals("*")&&quality>0)out.wildcard=true;
      out.values.add(new Range(normalized,quality,i));
    }
    return out;
  }
  static JSONArray javascript(JSONArray languages){
    if(languages==null||languages.length()<1||languages.length()>MAX_JS_LANGUAGES)return null;
    JSONArray out=new JSONArray();Set<String> seen=new HashSet<>();
    for(int i=0;i<languages.length();i++){String value=tag(languages.opt(i));if(value.isEmpty()||!seen.add(value))return null;out.put(value);}
    return out;
  }
  static boolean same(JSONArray a,JSONArray b){
    if(a==null||b==null||a.length()!=b.length())return false;for(int i=0;i<a.length();i++)if(!a.optString(i).equals(b.optString(i)))return false;return true;
  }
  static JSONObject compare(String header,JSONArray languages,String primary){
    Parsed parsed=parse(header);JSONArray normalized=javascript(languages);String state="uncovered",reason=parsed.reason;
    if(parsed.valid()){
      if(parsed.wildcard)reason="wildcard-not-comparable-to-explicit-list";
      else if(parsed.effective().isEmpty())reason="no-accepted-http-language";
      else if(normalized==null)reason="javascript-language-list-unavailable";
      else if(tag(primary).isEmpty())reason="primary-language-unavailable";
      else if(!tag(primary).equals(normalized.optString(0))){state="issue";reason="primary-language-not-first-in-list";}
      else{state=same(parsed.tags(),normalized)?"verified":"issue";reason=state.equals("verified")?"normalized-language-preference-order-equal":"normalized-language-preference-order-different";}
    }
    return J.obj("state",state,"reason",reason,"http",parsed.observation(),"javascriptLanguages",normalized==null?new JSONArray():normalized,"javascriptPrimary",tag(primary),"comparison","Case-normalized explicit language preference order after HTTP q sorting; q=0 is excluded, wildcard/duplicate/invalid input is not accepted as a pass","weightAgreementAttested",false,"leakVerdict",false);
  }
  static JSONObject compareHeaders(String first,String second){
    Parsed a=parse(first),b=parse(second);String state="uncovered",reason=!a.valid()?a.reason:!b.valid()?b.reason:"";
    if(a.valid()&&b.valid()){
      if(a.wildcard||b.wildcard)reason="wildcard-semantics-not-attested";
      else{
        boolean order=same(a.tags(),b.tags());Map<String,Integer> left=new TreeMap<>(),right=new TreeMap<>();for(Range value:a.values)left.put(value.tag,value.quality);for(Range value:b.values)right.put(value.tag,value.quality);
        state=order&&left.equals(right)?"verified":"issue";reason=state.equals("verified")?"normalized-http-language-order-and-weights-equal":"normalized-http-language-order-or-weights-different";
      }
    }
    return J.obj("state",state,"reason",reason,"first",a.observation(),"second",b.observation(),"leakVerdict",false,"scope","HTTP language range, preference and exclusion observations only; privacy normalization may legitimately change values");
  }
  static String detail(JSONObject result){
    String state=result.optString("state"),reason=result.optString("reason");
    if(state.equals("verified"))return result.has("first")?"文档与 Worker 的规范化有效语言顺序、q 权重及 q=0 排除项一致；原始 HTTP 值另行保留，仅对应本次请求。":"规范化后的有效语言顺序一致；HTTP 权重与 q=0 排除项单独保留，JavaScript 不提供权重。仅对应本次请求。";
    if(state.equals("issue"))return "规范化后的语言顺序、权重或排除项存在差异；原始值与语义分别保留，隐私标准化也可能导致差异，不直接判断泄漏。";
    if(reason.startsWith("duplicate"))return "语言范围有重复，未擅自选择一个权重作通过判断。";
    if(reason.startsWith("wildcard"))return "HTTP 语言包含有效通配范围，不能与明确的 JavaScript／模板列表作完整一致性判断。";
    if(reason.startsWith("invalid"))return "HTTP 语言范围或权重格式无效，未将部分解析当作完整通过。";
    return "没有取得完整、可比较的 HTTP 和 JavaScript／模板语言列表；本项未覆盖。";
  }
}
